<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo.svg" width="180" alt="Timbro">
  </picture>
</p>

<h1 align="center">Timbro</h1>

<p align="center">
  <em>Catch AI slop with deterministic, offline checks that never call an LLM. Then keep what's left sounding like you.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-111111?style=flat-square" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/inference-local%20·%20CPU--only-111111?style=flat-square" alt="Local CPU-only inference">
  <img src="https://img.shields.io/badge/MCP-ready-111111?style=flat-square" alt="MCP ready">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license">
</p>

---

**LLM prose has a tell.** Em/en dashes everywhere, "it's not X, it's Y", the _delve / tapestry / seamless_ vocabulary, a tidy wrap-up about the future. A reader feels it, but "sounds AI-written" is not something you can put in CI.

Timbro makes it one. `timbro slop` runs ~19 deterministic detectors (regex + part-of-speech, no model, no network) and returns a verdict, four dimension scores, and the exact markers it found:

```
$ timbro slop draft.md
slop: WARN (0.69)

diction      0.70
construction 0.70
rhythm       0.80
formatting   0.55

Top findings
- formatting: 2× em/en dashes
- diction: 12× AI-tell diction (delve, tapestry, seamless, robust, …)
- construction: signposting phrases, wrap-up phrases
```

Delete the flagged markers, re-run, and it reads `slop: PASS (1.00)`. Same meaning, no tells.

**Why not just ask an LLM "does this read AI-generated?"** Because that is an LLM grading an LLM: nondeterministic, an API call every time, and it can't show you _which_ words tripped it. Timbro is white-box. Every flag is a named marker you can see, cite, and remove; it runs local and CPU-only, gives the same answer every time, and is fast enough for a git hook.

## And a positive target, not just a blocklist

Any regex list can tell you what to strip. Timbro's second act tells you what your writing should sound _like_. Seed it with posts you've accepted as your voice, and it scores any draft for **how far** it sits from that voice and **which way** to revise it, in named features, without changing what it says. That positive target is what separates it from every slop-lister.

- **You, consistently.** A personal blog or newsletter should sound like one person across years of posts — not like whichever model wrote each one.
- **A company on-brand.** Marketing, docs, and posts drift across authors and tools. Seed Timbro with your on-brand corpus and every draft gets measured against it.
- **An agent that self-corrects.** LLMs are fluent but stylistically inconsistent. Timbro gives an agent a _measurable target_ and a _named direction_, so it can revise toward a voice instead of guessing.

## Numbers

This README was written by Claude (Opus 4.8). With Timbro you can see exactly how it scores against [my actual blog voice](https://nicolobrandizzi.com/blog/) — the same number your agent watches as it revises:

<p align="center">
  <img src="assets/distance.svg" width="780" alt="A 0-to-far axis: my blog voice sits in a 9–35 band; this README lands just outside it at 47; marketing hype is far out at 86">
</p>

It lands at 47 — outside my blog range (9–35): recognizably _not_ my essay voice (it's code-heavy docs), but a world away from sales-speak at 86. And Timbro hands back the _direction_ to close the gap: **more conjunctions, fewer abstract nouns, less code-block punctuation**. Scored against: [Horizon AI Fragmentation](https://nicolobrandizzi.com/blog/horizon-analysis/), [Teaching Machines to Think](https://nicolobrandizzi.com/blog/rl-reasoning-llm/), [The Digital Poisoners](https://nicolobrandizzi.com/blog/pravda-grooming/), [The SOTA Trap](https://nicolobrandizzi.com/blog/sota-trap/), [AI Gigafactories](https://nicolobrandizzi.com/blog/ai-gigafactories-tool/).

## How it works

Your agent runs one loop, and Timbro scores every turn of it:

```
score    → how far from your voice, and which way to move
edit     → revise toward the named direction
re-score → distance dropped AND meaning held?
repeat   → until the distance stops falling
```

Each score is three legible layers plus a guard:

- **Scalar — "how far"** — a pre-trained [StyleDistance](https://huggingface.co/StyleDistance/styledistance) embedding, scored by multi-modal **kNN**.
- **Direction — "which way"** — **POS-unigram** rates, z-scored against your corpus and weighted by each feature's R². Every move is a named habit.
- **Flow** — paragraph-embedding trajectory (speed, volume, circuitousness) + the Schimel "circle-back" (`cos(first, last)`).
- **Content guard** — semantic cosine via a _general_ model (all-MiniLM): changes _how_ it reads, never _what_ it says.

## The writing rubric (`check`)

Voice alignment answers _"does this sound like me?"_. The rubric answers a separate question — _"is this good prose?"_ — and needs **no voice corpus**. `timbro check` (and the `check_voice` MCP tool) runs ~30 deterministic checks distilled from Joshua Schimel's _Writing Science_, all linguistic/structural (spaCy dependency parse + POS + counting), **no LLM-as-judge**: buried subject–verb core, passive voice, comma splices, expletive openings, preposition chains, nominalizations, long Latinate words, word-echo repetition, inconsistent terminology, metadiscourse and citation-as-subject frames, caveat/defensive closings, unearned claim words, significance-without-magnitude, and more. It returns a per-dimension score and a ranked findings list — recall-first, so a model consumer filters the occasional false positive. Rubrics are pluggable via a registry (`--rubric <name>`); `schimel` ships today. `uv run python eval/rubric_dashboard.py` prints each rule's findings-per-1000-words on known-good prose, so noisy rules can be spotted and demoted rather than deleted.

```bash
uv run timbro check draft.md            # human-readable
uv run timbro check draft.md --json     # {verdict, overall, dimensions, findings}
```

## Install

### As a Claude Code plugin (one command)

```
/plugin marketplace add nicofirst1/timbro
/plugin install timbro@timbro
```

This installs the **skill** _and_ wires up the **MCP tools** (`score_voice`, `accept_rewrite`, `check_voice`) in one shot. It works immediately on a small **packaged sample voice** — ask Claude _"score this against the Timbro sample voice"_ to see it run.

To use **your** voice, point the MCP server at your own corpus. Edit the `timbro` entry in your MCP config (or the plugin's `plugin.json`) to set absolute paths:

```json
"env": {
  "TIMBRO_EXEMPLARS": "/abs/path/to/your/exemplars",
  "TIMBRO_CONTRAST":  "/abs/path/to/your/contrast"
}
```

The POS model and the sample corpus both ship with the plugin — no manual download step.

### As a skill

Copy just the skill so the agent knows when and how to use Timbro:

```bash
cp -r skills/timbro ~/.claude/skills/        # personal, or .claude/skills/ per-project
```

Now ask Claude the same way — it runs Timbro, reads the direction, and proposes content-preserving edits.

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

The agent gets three tools:

| Tool                                | Returns                                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| `score_voice(text)`                 | `{distance, direction, flow}`                                                         |
| `accept_rewrite(original, revised)` | `{accepted, content_ok, similarity, distance_before, distance_after, improved}`       |
| `check_voice(text)`                 | `{verdict, overall, dimensions, findings}` — the deterministic writing rubric (below) |

### As a one-shot CLI

No server, no agent — just score a file:

```bash
uv run timbro slop draft.md                 # deterministic AI-slop / tells report
uv run timbro score draft.md                # distance from your voice + revision direction
cat draft.md | uv run timbro score -        # stdin
uv run timbro score draft.md --json         # raw payload
uv run timbro check draft.md                # Schimel prose-quality rubric (below)
```

### From source (required for the MCP and CLI options above)

Requires Python ≥ 3.11 and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:nicofirst1/timbro.git && cd timbro
uv sync     # pulls deps + the en_core_web_sm POS model (no manual spacy download)

uv run timbro score draft.md   # runs immediately on the packaged sample voice

# to use your own voice, bring a corpus (both dirs are gitignored — your writing stays private)
mkdir -p data/exemplars data/contrast
#   data/exemplars/  → posts that define your (or your company's) voice — 6+ pieces
#   data/contrast/   → other authors' posts (the "not-our-voice" set), optional but sharpens it

TIMBRO_EXEMPLARS=data/exemplars TIMBRO_CONTRAST=data/contrast uv run timbro score draft.md
uv run python eval/harness.py data/exemplars data/contrast   # confirm it separates your voice
```

The two sentence-transformer models download from Hugging Face on first use. Everything runs **local and CPU-only** at inference — no API calls.

## FAQ

**Do I need the contrast set?** No, but it sharpens the direction — without it, every feature looks equally informative.

**Will it work on one author / a whole company?** Both. The "voice" is whatever you put in `data/exemplars/`. Mixed registers (blogs + papers) are fine — the scorer is multi-modal.

**Can I keep several directions (academic vs. slop, clear vs. jargon)?** Yes — one folder pair per dimension, selected by env var. Profiles live under `~/.timbro/profiles/<name>/{exemplars,contrast}/` by default (override with `TIMBRO_PROFILE_ROOT`). Point the env vars at the one you want for a given task:

```bash
P=~/.timbro/profiles/academic
TIMBRO_EXEMPLARS=$P/exemplars TIMBRO_CONTRAST=$P/contrast uv run timbro score draft.md
```

No code, no flags — collect good/bad examples per dimension and swap the two paths. If you want Timbro to scaffold and manage the local profile layout for you, use the `timbro profiles ...` commands below.

**Can Timbro create and manage profiles for me?** Yes. Use the built-in profile helpers to scaffold a profile, describe it, add files, and print the right env vars:

```bash
uv run timbro profiles init science-clarity --about "Plain-language scientific explanation."
uv run timbro profiles add-file science-clarity notes/pvalue.md --to exemplars
uv run timbro profiles add-file science-clarity sloppy-example.md --to contrast
uv run timbro profiles add-file science-clarity paper.tex --to exemplars
uv run timbro profiles env science-clarity
```

Programmatically:

```python
from timbro.profiles import init_profile, add_file

profile = init_profile("science-clarity", about="Plain-language scientific explanation.")
add_file("science-clarity", "notes/pvalue.md", bucket="exemplars")
add_file("science-clarity", "paper.tex", bucket="exemplars")
print(profile.env)
```

If `detex` is installed, `.tex` files are converted on ingest and raw LaTeX is normalized automatically during scoring.

For scoring, prefer profile-native selection over manual env vars:

```bash
uv run timbro score draft.md --profile science-clarity
uv run timbro score draft.md --profile science-clarity,academic
```

**Does it rewrite for me?** No, and that's deliberate. Timbro _measures_; your agent rewrites and Timbro judges the result (closer to voice **and** same meaning). Keeps the scoring honest and local.

## Layout

```
src/timbro/
├── model.py         # corpus → POS features + StyleDistance embedding → VoiceModel
├── text.py          # shared substrate: split_paragraphs/_sentences, strip_markup, MiniLM embedder
├── flow.py          # paragraph trajectory, circle-back, order gates
├── rewrite.py       # content-preservation guard + accept-rewrite loop
├── report.py        # the shared {distance, direction, flow} payload
├── tells.py         # AI-tell detectors (regex + POS); feed the `slop` rubric and the score direction
├── rubrics/         # `check` (schimel/density) + `slop` (tells) rubrics: features + rules + registry
├── cleanup/         # ingest-time corpus prep (LaTeX/paper extraction — not markdown)
├── cli.py           # `timbro score` + `timbro check` + `timbro slop`
└── mcp_server.py    # MCP wrapper: score_voice, accept_rewrite, check_voice
skills/timbro/       # Claude Code skill
eval/harness.py      # LOO-AUC, permutation baseline, direction sign test
```
