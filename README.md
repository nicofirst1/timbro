# Timbro

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Inference](https://img.shields.io/badge/inference-local%20·%20CPU--only-orange)
![MCP](https://img.shields.io/badge/MCP-ready-8A2BE2)
![Status](https://img.shields.io/badge/status-all%20gates%20green-brightgreen)

**Keep your writing sounding like *you* — even when an LLM is doing the writing.**

LLM prose drifts. Today's draft doesn't sound like last week's, and neither sounds like the human or the company it's published under. Timbro fixes the *consistency* problem: seed it with writing you've accepted as your voice, and it scores any draft for **how far** it sits from that voice and **which way** to revise it — in named features, without changing what it says.

It's built to be called by a coding agent mid-draft: the agent asks Timbro "how off-voice is this, and which way do I move it?", edits, and re-checks until it's aligned.

> *timbre* — the acoustic quality that distinguishes two voices at the same pitch. Italian *timbro* — a stamp, a seal, a signature.

## Why

- **You, consistently.** A personal blog or newsletter should sound like one person across years of posts — not like whichever model wrote each one.
- **A company on-brand.** Marketing, docs, and posts drift across authors and tools. Seed Timbro with your on-brand corpus and every draft gets measured against it.
- **An agent that self-corrects.** LLMs are fluent but stylistically inconsistent. Timbro gives an agent a *measurable target* and a *named direction*, so it can revise toward a voice instead of guessing.

Not an LLM-as-judge — a local, mostly-statistical instrument. Every number traces to something legible: a part-of-speech habit, a paragraph-trajectory metric, a distance you watch drop as you revise.

## What you get

```python
from timbro import VoiceModel
model = VoiceModel.from_dir("data/exemplars", contrast="data/contrast")
print(model.score(draft).to_dict())
```

```jsonc
{
  "distance": 65.0,                       // how far from your voice (smaller = closer)
  "direction": [                          // signed, confidence-weighted, NAMED edits
    { "hint": "more conjunctions", "confidence": 0.20, "current_z": -4.3 },
    { "hint": "fewer verbs",       "confidence": 0.11, "current_z":  6.1 },
    { "hint": "more determiners",  "confidence": 0.07, "current_z": -2.5 }
  ],
  "flow": { "circle_back": 0.14, "circuitousness": 28.3, "speed": 0.50 }
}
```

The loop, run by your agent: **score → edit toward the direction → re-score → repeat until the distance stops dropping.** A separate content guard (semantic similarity > 0.85) blocks any "rewrite" that changed the meaning — distance improvement alone never counts.

## Use it with your agent

### As a Claude Code skill

The fastest path. Copy the skill so the agent knows when and how to use Timbro:

```bash
cp -r skills/timbro ~/.claude/skills/        # personal, or .claude/skills/ per-project
```

Now ask Claude *"make this post sound like my voice"* or *"keep this on-brand with our blog"* — it runs Timbro, reads the direction, and proposes content-preserving edits.

### As an MCP server (Claude Code, Cursor, Windsurf, Claude Desktop, …)

```bash
# Claude Code
claude mcp add timbro \
  -e TIMBRO_EXEMPLARS=$PWD/data/exemplars \
  -e TIMBRO_CONTRAST=$PWD/data/contrast \
  -- uv run --directory $PWD timbro-mcp
```

Or drop this into any agent's `.mcp.json` / MCP settings:

```json
{
  "mcpServers": {
    "timbro": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/timbro", "timbro-mcp"],
      "env": {
        "TIMBRO_EXEMPLARS": "/abs/path/to/timbro/data/exemplars",
        "TIMBRO_CONTRAST": "/abs/path/to/timbro/data/contrast"
      }
    }
  }
}
```

The agent gets two tools:

| Tool | Returns |
|---|---|
| `score_voice(text)` | `{distance, direction, flow}` |
| `accept_rewrite(original, revised)` | `{accepted, content_ok, similarity, distance_before, distance_after, improved}` |

### As a one-shot CLI

No server, no agent — just score a file:

```bash
uv run timbro score draft.md
cat draft.md | uv run timbro score -        # stdin
uv run timbro score draft.md --json         # raw payload
```

## Setup

Requires Python ≥ 3.11 and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:nicofirst1/timbro.git && cd timbro
uv sync
uv run python -m spacy download en_core_web_sm     # POS tagger (not a pip dep)

# bring your own corpus (both dirs are gitignored — your writing stays private)
mkdir -p data/exemplars data/contrast
#   data/exemplars/  → posts that define your (or your company's) voice — 6+ pieces
#   data/contrast/   → other authors' posts (the "not-our-voice" set), optional but sharpens it

uv run python eval/harness.py data/exemplars data/contrast   # confirm it separates your voice
```

The two sentence-transformer models download from Hugging Face on first use. Everything runs **local and CPU-only** at inference — no API calls.

## How it works

Voice splits into two layers with opposite needs, plus a guard:

- **Scalar — "how far"** — a pre-trained [StyleDistance](https://huggingface.co/StyleDistance/styledistance) embedding, mean-pooled over paragraphs, scored by multi-modal **kNN**. Pre-trained style beats hand-coded features you must *fit* from ~15 docs, and kNN fits a multi-register voice a single Gaussian can't.
- **Direction — "which way" (white-box)** — **POS-unigram** rates, z-scored against your corpus and weighted by each feature's discriminative R². Every move maps to a named habit (NOUN/VERB density = nominalization).
- **Flow** — paragraph embeddings → novelty trajectory (speed, volume, circuitousness) + the Schimel "circle-back" (`cos(first, last)`).
- **Content guard** — semantic cosine via a *general* model (all-MiniLM, deliberately not the style model): a rewrite changes *how* it reads, never *what* it says.

> **The honest finding:** against *generic* writers the scalar scores **0.93** (LOO-AUC); against *other expert AI/ML bloggers* it tops out at **0.86**. Telling your technical voice apart from other technical voices is the hard bar — classical features alone couldn't clear 0.80 at n≈15, which is why the scalar is a neural embedding while the direction stays classical and interpretable.

All four gates are green on a 23-exemplar / 8-contrast corpus: scalar AUC **0.86**, direction beats random on **88%** of posts, flow order is discriminative (shuffle 100%, insertion 11% vs 2% chance), content guard separates paraphrase (0.93) from unrelated (0.06).

## FAQ

**Do I need the contrast set?** No, but it sharpens the direction — without it, every feature looks equally informative.

**Will it work on one author / a whole company?** Both. The "voice" is whatever you put in `data/exemplars/`. Mixed registers (blogs + papers) are fine — the scorer is multi-modal.

**Does it rewrite for me?** No, and that's deliberate. Timbro *measures*; your agent rewrites and Timbro judges the result (closer to voice **and** same meaning). Keeps the scoring honest and local.

## Layout

```
src/timbro/
├── core.py          # corpus → POS features + StyleDistance embedding → VoiceModel
├── flow.py          # paragraph trajectory, circle-back, order gates
├── rewrite.py       # content-preservation guard + accept-rewrite loop
├── report.py        # the shared {distance, direction, flow} payload
├── cli.py           # `timbro score`
└── mcp_server.py    # MCP wrapper: score_voice, accept_rewrite
skills/timbro/       # Claude Code skill
eval/harness.py      # LOO-AUC, permutation baseline, direction sign test
```

## Written by an agent — and measured

This README was written by Claude (Opus 4.8), not by me. So I pointed Timbro at it:

| text | distance from my voice |
|---|---|
| my blog posts (leave-one-out avg) | **21** &nbsp;(range 9–35) |
| **← this README** | **37** |
| generic marketing hype | **86** |

It lands just past the edge of my blog range — recognizably *not* my essay voice (it's documentation, and code-heavy markdown inflates the symbol features), but a world away from sales-speak. Timbro can tell the difference, which is the whole point.

The voice it's measuring against: [Horizon AI Fragmentation](https://nicolobrandizzi.com/blog/horizon-analysis/), [Teaching Machines to Think](https://nicolobrandizzi.com/blog/rl-reasoning-llm/), [The Digital Poisoners](https://nicolobrandizzi.com/blog/pravda-grooming/), [The SOTA Trap](https://nicolobrandizzi.com/blog/sota-trap/), [AI Gigafactories](https://nicolobrandizzi.com/blog/ai-gigafactories-tool/) — more at [nicolobrandizzi.com/blog](https://nicolobrandizzi.com/blog/).

## License

[MIT](./LICENSE).
