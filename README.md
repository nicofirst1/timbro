# Timbro

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Inference](https://img.shields.io/badge/inference-local%20·%20CPU--only-orange)
![Status](https://img.shields.io/badge/status-phase%205%20·%20all%20gates%20green-brightgreen)

**Measure the *timbre* of your writing — the quality that makes a sentence recognizably yours — as a distance in a metric space, and get a named, content-preserving direction to move a draft toward your voice.**

Not an LLM-as-judge. A local tool that seeds a reference from a handful of posts whose *writing* you love, then scores any draft for **how far** it sits from your voice, **which way** to revise it (in named features, not opaque dimensions), and **how it flows**. Designed to be called by a CLI coding agent over MCP, mid-draft.

> *timbre* — the acoustic quality that distinguishes two voices at the same pitch. Italian *timbro* — a stamp, a seal, a signature.

## Quick start

```bash
git clone git@github.com:nicofirst1/timbro.git && cd timbro
uv sync
uv run python -m spacy download en_core_web_sm     # POS tagger (not a pip dep)

# bring your own corpus (both dirs are gitignored)
mkdir -p data/exemplars data/contrast
#   data/exemplars/  → posts that define your voice
#   data/contrast/   → other authors' posts (the "not-my-voice" set)

uv run python eval/harness.py data/exemplars data/contrast   # check it separates your voice
```

The two sentence-transformer models download from Hugging Face on first use. Everything runs **local and CPU-only** at inference — no API calls.

## What you get

```python
from timbro import VoiceModel
model = VoiceModel.from_dir("data/exemplars", contrast="data/contrast")
print(model.score(my_draft).to_dict())
```

```jsonc
{
  "distance": 50.6,                       // how far from your voice (smaller = closer)
  "direction": [                          // signed, confidence-weighted, NAMED
    { "hint": "more conjunctions", "confidence": 0.20, "current_z": -4.3 },
    { "hint": "fewer verbs",       "confidence": 0.11, "current_z":  6.1 },
    { "hint": "more other tokens", "confidence": 0.19, "current_z": -2.5 }
  ],
  "flow": { "circle_back": 0.14, "circuitousness": 28.3, "speed": 0.50, "...": null }
}
```

Every number traces to something legible: a part-of-speech habit, a paragraph-trajectory metric, a distance you can watch drop as you revise.

## Use it as an MCP plugin (CLI agents)

Timbro ships an MCP server (`timbro-mcp`) so an agent can score and guide rewrites without leaving your editor. `uv run --directory` makes it runnable from anywhere — no `cd`, no venv activation.

**Claude Code** (or any MCP-capable CLI agent):

```bash
claude mcp add timbro \
  -e TIMBRO_EXEMPLARS=$PWD/data/exemplars \
  -e TIMBRO_CONTRAST=$PWD/data/contrast \
  -- uv run --directory $PWD timbro-mcp
```

**Generic `.mcp.json`** (Cursor, Claude Desktop, Windsurf, …):

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

**The loop:** `score_voice` → rewrite toward the direction → `accept_rewrite` → repeat. A rewrite is accepted only if it moved **closer to your voice** *and* **kept the meaning** (semantic cosine > 0.85) — distance improvement alone never suffices.

## How it works

Voice splits into two layers with opposite needs, plus a guard:

- **Scalar — "how far"** — a pre-trained [StyleDistance](https://huggingface.co/StyleDistance/styledistance) embedding, mean-pooled over paragraphs, scored by multi-modal **kNN**. Pre-trained style beats hand-coded features you must *fit* from ~15 docs, and kNN fits a multi-register voice a single Gaussian can't.
- **Direction — "which way" (white-box)** — **POS-unigram** rates, z-scored against your corpus and weighted by each feature's discriminative R². Every move maps to a named habit (NOUN/VERB density = nominalization).
- **Flow** — paragraph embeddings → novelty trajectory (speed, volume, circuitousness) + the Schimel "circle-back" (`cos(first, last)`).
- **Content guard** — semantic cosine via a *general* model (all-MiniLM, deliberately not the style model): a rewrite changes *how* it reads, never *what* it says.

> **The honest finding:** against *generic* writers the scalar scores **0.93** (LOO-AUC); against *other expert AI/ML bloggers* it tops out at **0.86**. Telling your technical voice apart from other technical voices is the hard bar — classical features alone couldn't clear 0.80 at n≈15, which is why the scalar is a neural embedding while the direction stays classical and interpretable.

All four gates are green on a 23-exemplar / 8-contrast corpus: scalar AUC **0.86**, direction beats random on **88%** of posts, flow order is discriminative (shuffle 100%, insertion 11% vs 2% chance), content guard separates paraphrase (0.93) from unrelated (0.06).

## CLI & API reference

```bash
uv run python eval/harness.py data/exemplars data/contrast   # scalar AUC + direction sign test
uv run python -m timbro.flow data/exemplars                  # flow order gates
uv run timbro-mcp                                            # MCP server (stdio)
```

```python
from timbro import VoiceModel, flow_report
model  = VoiceModel.from_dir("data/exemplars", contrast="data/contrast")
result = model.score(draft)          # .distance, .direction, .to_dict()
flow   = flow_report(draft)          # .circle_back, .circuitousness, .speed, ...
```

## Layout

```
src/timbro/
├── core.py          # corpus → POS features + StyleDistance embedding → VoiceModel
├── flow.py          # paragraph trajectory, circle-back, order gates
├── rewrite.py       # content-preservation guard + accept-rewrite loop
└── mcp_server.py    # thin MCP wrapper: score_voice, accept_rewrite
eval/harness.py      # LOO-AUC, permutation baseline, direction sign test
```

See [`PLAN.md`](./PLAN.md) for the full architecture, evaluation protocol, as-built decisions, and research provenance.

## Contributing

Issues and PRs welcome. Keep the core reuse-first and white-box where it can be; run `uv run ruff check src/ eval/` and the eval gates before opening a PR.

## License

MIT.
