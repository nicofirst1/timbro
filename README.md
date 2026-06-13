# Timbro

**Measure the *timbre* of your writing — the quality that makes a sentence recognizably yours — as a distance in a metric space, and get a named, content-preserving direction to move a draft toward your voice.**

Not an LLM-as-judge. A local, mostly-statistical tool: seed a reference from a handful of posts whose *writing* you love, then score any draft for (1) a **distance** from your voice, (2) a **signed, named revision direction** ("lower NOUN density — fewer nominalizations"), and (3) **flow** metrics (does it circle back?). Built to be called by an LLM over MCP mid-draft.

The name carries the idea: *timbre* (the acoustic quality distinguishing two voices at the same pitch) and Italian *timbro* (a stamp / seal — a signature).

## Status

**Working through Phase 5.** All gates green on a 23-exemplar / 8-contrast corpus:

| Layer | What it gives you | Gate | Result |
|---|---|---|---|
| **Scalar** | distance from your voice | LOO-AUC > 0.80 | **0.86 ✅** |
| **Direction** | named, confidence-weighted moves | beats random | **88% of posts, 1.7× ✅** |
| **Flow** | trajectory + circle-back | order is discriminative | shuffle 100%, insertion 11% vs 2% chance ✅ |
| **Rewrite guard** | content preserved on a rewrite | cosine > 0.85 | paraphrase 0.93 / unrelated 0.06 ✅ |

Phase 4 has **no bundled rewrite engine by design** — Timbro stays the *measurer*; the calling agent rewrites, and `accept_rewrite` judges the result (closer to voice **and** same meaning). See [`PLAN.md`](./PLAN.md) for the full architecture, evaluation protocol, and the research provenance.

## How it works

Voice splits into two layers with opposite needs, plus a guard:

- **Style (scalar "how far")** — a pre-trained [StyleDistance](https://huggingface.co/StyleDistance/styledistance) embedding, mean-pooled over paragraphs, scored by multi-modal **kNN**. Pre-trained style beats hand-coded features you must *fit* from ~15 docs (the small-*n* wall), and kNN fits a multi-register voice that a single Gaussian can't.
- **Direction ("which way", white-box)** — **POS-unigram** rates, z-scored against your corpus and weighted by each feature's discriminative R². Stays fully interpretable: every move maps to a named part-of-speech habit (NOUN/VERB density = nominalization).
- **Flow** — paragraph embeddings → novelty trajectory (speed, volume, circuitousness) + the Schimel "circle-back" (`cos(first, last)`).
- **Content guard** — semantic cosine via a *general* model (all-MiniLM, deliberately not the style model) ensures a rewrite changes *how* it reads, never *what* it says.

> **The honest finding:** against *generic* writers the scalar scores **0.93**; against *other expert AI/ML bloggers* it tops out at **0.86**. Telling your technical voice apart from other technical voices is the hard bar — and classical features alone couldn't clear 0.80 at n≈15, which is why the scalar is a neural embedding while the direction stays classical.

## Install

Requires Python ≥ 3.11 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python -m spacy download en_core_web_sm   # POS tagger (not a pip dep)
```

The two sentence-transformer models (StyleDistance, all-MiniLM) download from the Hugging Face Hub on first use. Everything runs **local and CPU-only** at inference — no API calls.

## Corpus

Bring your own (both dirs are gitignored — your corpora stay private):

```
data/exemplars/   # posts that define your voice (markdown / plain text)
data/contrast/    # other authors' posts — the "not-my-voice" set
```

Markdown YAML frontmatter is stripped automatically.

## Usage

**Run the evaluation gates:**

```bash
uv run python eval/harness.py data/exemplars data/contrast   # scalar AUC + direction sign test
uv run python -m timbro.flow data/exemplars                  # flow order gates
```

**Python API:**

```python
from timbro import VoiceModel, flow_report

model = VoiceModel.from_dir("data/exemplars", contrast="data/contrast")
result = model.score(draft_text)

result.distance              # float: how far from your voice (smaller = closer)
result.direction             # list[FeatureMove]: signed, confidence-weighted, named
result.to_dict()             # JSON-serializable (the MCP payload)

flow_report(draft_text)      # speed, circuitousness, circle_back, ...
```

**MCP server** (stdio):

```bash
uv run timbro-mcp
```

Exposes two tools:
- `score_voice(text)` → `{distance, direction, flow}`
- `accept_rewrite(original, revised)` → `{accepted, content_ok, similarity, distance_before, distance_after, improved}`

The loop: `score_voice` → rewrite toward the direction → `accept_rewrite` → repeat. Point `TIMBRO_EXEMPLARS` / `TIMBRO_CONTRAST` at your corpora (defaults to `data/`).

## Layout

```
src/timbro/
├── core.py          # corpus → POS features + StyleDistance embedding → VoiceModel
├── flow.py          # paragraph trajectory, circle-back, order gates
├── rewrite.py       # content-preservation guard + accept-rewrite loop
└── mcp_server.py    # thin MCP wrapper: score_voice, accept_rewrite
eval/harness.py      # LOO-AUC, permutation baseline, direction sign test
```

## License

MIT.
