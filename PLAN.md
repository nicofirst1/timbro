# Timbro — Plan, Requirements & Vision

> **Status:** built through Phase 5 (all gates green). The scalar landed on a neural
> style embedding, not the classical primary this plan opened with — see §7 for the
> as-built outcomes and why. This file is the build spec + decision record; `README.md`
> is the user-facing doc.
> **Provenance:** distilled from a four-agent literature + tooling survey. Full research record and citations live in the wiki: `claude_memory/wiki/research/voice-style-metric-space.md`. This file is the build spec; the wiki is the thinking record.

---

## 1. Vision

**Timbro measures the *timbre* of your writing — the quality that makes a sentence recognizably yours — as a position in a metric space, and tells you which way to move a draft to sound more like you, without changing what it says.**

Today, feedback on voice is verbal and lossy ("I like this, not that"). Timbro replaces it with a **measurable target**: seed a reference from a handful of posts whose *writing* you love, embed any new draft into the same space, and get back two things —

1. a **scalar** — how far the draft sits from your accepted style;
2. an **interpretable direction** — the revision, expressed in *named* features ("shorten sentences, fewer nominalizations, close the loop back to your opening"), not opaque latent dimensions.

The name carries the idea: *timbre* (the acoustic quality that distinguishes two voices at the same pitch) and Italian *timbro* (a stamp / seal — a signature).

### Non-negotiable principles

- **Statistical / white-box.** No LLM-as-judge. An LLM returns a verdict; we want coordinates. Every number traces back to a named feature.
- **Local & cheap.** CPU-only, inference-only. No fine-tuning, no API calls. Runs on a laptop.
- **Content-preserving.** We change *how* it reads, never *what* it says.
- **Reuse-first.** The science is largely solved and the tools mostly exist. Novel code target: **~200–400 lines**. Everything else is configuration and glue.
- **MCP-ready from day one.** The core returns plain machine-readable data so an LLM can call Timbro mid-draft ("score this, tell me the direction"). The MCP server is a thin wrapper, not a retrofit.

---

## 2. The two-layer model

Voice splits into two layers with **opposite** representational needs.

| Layer | Measures | Embedding space | Why |
|---|---|---|---|
| **Style (local texture)** | word/sentence-level habits | content-**invariant** | topic must not move you; style is the signal |
| **Flow (global architecture)** | how paragraphs/ideas connect; the arc; the "circle-back" | content-**bearing**, then **centered** | the point is how topics carry across paragraphs — strip content and there's nothing to connect |

Key clarification on the flow layer: the **points** (paragraph embeddings) must carry topic, but the **features** extracted from them (transition smoothness, circle-back, recurrence) are *relational geometry* and therefore content-invariant by construction — like a melody's shape surviving transposition to any key. **Centering** (subtract the corpus-mean embedding) removes the constant "all my posts are about AI" offset so we measure flow, not topic-sameness.

---

## 3. Architecture (post-completeness-audit)

The literature audit flipped the spine of the style layer and simplified it.

**The decisive finding — Valla benchmark (Tyo et al. 2023):** classical n-gram/frequency stylometry *beats* neural style embeddings when per-author samples are few (76.5% vs 66.7% macro-accuracy); neural only wins with lots of text per author. We have ~15 posts. Therefore:

### 3.1 Style layer (primary = classical, white-box)

- **Feature backbone (named, interpretable):** `LFTK` (200+ features) + `BiberPlus` (96 register features) + `Gram2Vec` (POS / punctuation / function-word vectors with per-component distance) + `writeprints-static`. Feature-selected down to a corpus-stable subset.
- **Scoring:** Mahalanobis distance in a regularized feature space (MVP), upgradable to **Andrea Nini's idiolect likelihood-ratio** (`idiolect` R package) — the only framework that formalizes *one author's idiolect from a small corpus*, which is exactly our problem.
- **Region model:** PCA → `LedoitWolf` covariance shrinkage → Mahalanobis. LedoitWolf is *critical* at n≈15 (raw covariance is singular).
- **Embeddings (secondary lens, optional):** `StyleDistance` (content-invariant) or `STAR` (`AIDA-UPM/star`), made interpretable post-hoc via a sparse-autoencoder decomposition or `VADES`-style axis constraints. Added only if the classical layer underperforms.

### 3.2 Flow layer (content-bearing, centered)

- **Trajectory:** embed each paragraph (`all-MiniLM-L6-v2` for speed, `all-mpnet-base-v2` for quality), center against corpus mean, then compute the novelty curve (running-centroid: `1 − cos(e_i, mean(e_{<i}))`) → **speed, volume, circuitousness, terminal/initial ratio** (all established, published metrics).
- **Circle-back (Schimel OCAR, our novel framing):** the cosine **self-similarity matrix** of the paragraph sequence; `cos(e_0, e_N)` = bookend strength; section-open vs section-close at every scale (sections via `wtpsplit` or SBERT-TextTiling).
- **Cohesion features (named, interpretable):** `TAACO 2.0` (168 cohesion indices) + a `Coh-Metrix` subset for causal/temporal/situation-model coherence and narrativity — dimensions no other tool gives.

### 3.3 Multi-scale

Run trajectory + SSM at **sentence and paragraph** granularity. Cross-scale mismatch (smooth sentences, jumpy paragraphs) localizes *where* the writing breaks.

---

## 4. Reuse matrix (everything off-the-shelf is `pip`, local, CPU)

| Role | Tool(s) | Status |
|---|---|---|
| Named style features | `lftk`, `biberplus`, `gram2vec`, `writeprints-static`, `textstat` | reuse |
| Delta scalar | `faststylometry` (MIT, maintained) | reuse |
| Idiolect LR (upgrade) | `idiolect` (R, Nini) | reuse (R extra) |
| Style embedding (secondary) | `StyleDistance`, `AIDA-UPM/star`, LUAR | reuse |
| Paragraph embeddings (flow) | `sentence-transformers` (`all-MiniLM-L6-v2` / `all-mpnet-base-v2`) | reuse |
| Cohesion features (flow) | `TAACO 2.0`, Coh-Metrix port | reuse (some install friction) |
| Segmentation (optional) | `wtpsplit` (EMNLP 2024, MIT) | reuse |
| Region + distance | `scikit-learn` (PCA, `LedoitWolf`), `scipy` (mahalanobis) | reuse |
| Rewrite engine (later) | `TinyStyler` (open weights, ~16-post few-shot, beats GPT-4) | reuse (Phase 4) |
| Content-preservation guard | `bert-score`, sentence-transformers cosine, NLI cross-encoder | reuse (Phase 4) |
| MCP server | `mcp` SDK | reuse |

**End-to-end verdict:** no existing tool does the whole job. Closest misses: `Gram2Vec` (named-feature direction, no region model), IXAM (explains a *classifier*, not a revision direction; needs labeled multi-author data), `StyleDistance` (scalar only), Grammarly Brand Voice / ProWritingAid (closed; neural or hand-coded rules, not corpus-seeded). The gap Timbro fills: **your corpus → named-feature acceptance region → scalar distance → signed per-feature direction → flow trajectory.**

---

## 5. What we actually build (the ~300-line gap)

Everything below is the connective tissue no library ships:

1. **Feature selection + normalization** — pick the corpus-stable, style-relevant subset from ~300+ candidate features (LASSO or correlation-to-Delta). A small-n regularization problem, not a research problem.
2. **Region model + scoring** — PCA → LedoitWolf → Mahalanobis (MVP); Nini LR (upgrade).
3. **Revision direction** — signed per-feature residual × feature importance, **confidence-weighted by each feature's regression R²** so reliable features outrank noisy ones. Does not exist pre-packaged.
4. **Flow integration** — paragraph trajectory + SSM circle-back + TAACO cohesion, fused into (or reported alongside) the joint distance.
5. **MCP-ready report layer** — one `to_dict()` that serializes `{distance, percentile, direction[], flow}` for both humans and tools.

---

## 6. Proposed package layout

```
timbro/
├── pyproject.toml
├── README.md
├── PLAN.md                     # this file
├── src/timbro/
│   ├── __init__.py
│   ├── corpus.py               # load posts (md/txt), segment to sentences + paragraphs
│   ├── features/
│   │   ├── stylometric.py      # LFTK + BiberPlus + Gram2Vec + writeprints → named vector
│   │   └── flow.py             # paragraph embeddings → trajectory, SSM, circle-back, TAACO
│   ├── select.py               # feature selection + normalization (corpus-stable subset)
│   ├── region.py               # fit acceptance region: PCA + LedoitWolf (+ optional Nini LR)
│   ├── score.py                # distance + signed, confidence-weighted direction
│   ├── report.py               # ScoreResult: human string + machine dict (MCP payload)
│   └── mcp_server.py           # thin MCP wrapper exposing `score_voice` (Phase 5)
├── eval/
│   └── harness.py              # LOO-AUC, shuffle test, insertion task, direction sign test
├── data/
│   ├── exemplars/              # the seed posts (define R) — gitignored if private
│   └── contrast/               # other-author corpus (the "not-my-voice" set)
└── tests/
```

### Core API (designed for MCP)

```python
from timbro import VoiceModel

model = VoiceModel.fit("data/exemplars/", contrast="data/contrast/")  # build R
result = model.score(draft_text)

result.distance        # float: std-devs / LR from your voice region
result.percentile      # where this draft sits vs your corpus
result.direction       # list[FeatureMove]: signed, confidence-weighted, named
result.flow            # FlowReport: circle_back, transition_smoothness, recurrence, ...
result.to_dict()       # JSON-serializable — the MCP tool payload
```

```python
@dataclass
class FeatureMove:
    feature: str        # e.g. "mean_sentence_length"
    current_z: float    # draft's z vs your corpus
    target_z: float     # your corpus mean (0)
    delta: float        # how far / which way to move
    confidence: float   # the feature's regression R² (0–1)
    hint: str           # human-legible: "shorten sentences"
```

---

## 7. Phased plan (each phase has a falsifiable gate)

> **As-built (2026-06-13).** All phases shipped; outcomes differed from the plan in
> instructive ways:
> - **Phase 1 scalar:** classical features (POS-unigrams, the best single backbone)
>   topped out at **0.76 LOO-AUC** vs same-domain contrast and could not reach 0.80 —
>   *every* feature combination underperformed its best single member at n≈15 (added
>   dims add noise faster than signal). The plan's secondary track won: a pre-trained
>   **StyleDistance embedding** (kNN) hit **0.86**, clearing the gate. Lesson: Valla's
>   "classical wins at small n" holds for representations you *fit*; a *pre-trained*
>   style embedding doesn't pay the n-tax.
> - **Region model:** a single Gaussian (PCA + LedoitWolf + Mahalanobis) was *falsified*
>   on a multi-register corpus (blogs + papers); replaced with multi-modal **kNN**.
> - **Phase 2 direction:** kept classical/white-box (POS), confidence-weighted by R².
>   Final architecture is **hybrid** — neural scalar, classical direction.
> - **Phase 4 rewrite:** TinyStyler dropped (not pip-installable, domain-mismatched on
>   long essays). Shipped the **content guard + MCP accept-rewrite loop** instead; the
>   rewriting agent is the engine, Timbro is the judge.
> - **Reframe:** 0.86 is the *hard* bar (you vs other expert AI/ML writers). Vs generic
>   writers the scalar is **0.93** — the actual product use case is well-served.


- **Phase 0 — data + harness.** Assemble exemplar set (4–6 posts proud of the *writing*) + contrast set (other AI-researcher blogs). Build the eval harness *first* so every later phase is measured.
- **Phase 0.5 — dependency checkpoint.** Before any feature code, stand up the `core` dep group only and confirm it imports and the `uv` lock resolves. The real cost of §5 is dependency reconciliation (conflicting spaCy/numpy pins across the stylometry libs, git installs, TAACO's desktop backend), not novel code — surface that friction now, not in Phase 3.
- **Phase 1 — MVP scalar.** Start with **one** feature backbone (LFTK alone, or `textstat` + function-word frequencies) → feature-select → PCA + LedoitWolf + Mahalanobis. Add the other backbones (BiberPlus, Gram2Vec, writeprints) **only if this gate fails** — stacking four feature sets at n≈15 buys four dependency surfaces and four overfitting sources before any is shown to be needed.
  **Gate:** leave-one-out AUC **> 0.80** vs contrast, with **feature selection performed inside each LOO fold** (nested CV), not once globally — selecting from 300+ candidates on 15 docs overfits, and a single global selection inflates the AUC. Run a **permutation baseline** on the style AUC too, so you know what chance looks like at your specific n. (**≤ 0.65 falsifies the feature set.**)
- **Phase 2 — interpretable direction.** Signed, confidence-weighted residual.
  **Gate:** direction **sign test beats chance** (moving a contrast post along the direction *decreases* its distance).
- **Phase 3 — flow layer.** Paragraph trajectory + SSM + TAACO, fused. Run the **insertion task (§8.4) first** — it's the stronger discriminator at ~15-paragraph scale; if even insertion is at chance, the global shuffle test won't save the layer.
  **Gate:** **shuffle test** — your real paragraph order beats **> 80%** of random permutations. (**< 60% → drop the flow layer**; order isn't discriminative at this scale.)
- **Phase 4 — rewrite (later).** TinyStyler + content-preservation guard (cosine / BERTScore **> 0.85**).
- **Phase 5 — MCP server.** Wrap the core `score()` as an MCP tool; expose `score_voice(text) → {distance, direction, flow}`.
- **Secondary track (anytime).** Style embeddings (StyleDistance/STAR) + SAE/VADES decomposition — only if the classical layer underperforms.

---

## 8. Evaluation protocol (falsifiable, 15 docs)

Corpus: ~15 in-distribution posts; contrast = 10–15 posts from 2–3 other AI-researcher blogs.

1. **LOO-AUC** — for each post, fit R on the other 14, score held-out (positive) vs all contrast (negative). Target AUC > 0.80.
2. **Direction sign test** — does moving a contrast post along the recommended direction reduce its distance? Binomial over folds.
3. **Shuffle test (flow)** — original order vs 100 permutations; original should beat > 80%.
4. **Insertion task (harder flow)** — remove a middle paragraph, score all re-insertion positions, original rank-1; report top-1 accuracy vs chance.
5. **Content preservation (rewrite)** — semantic cosine(original, revised) > 0.85.
6. **Human A/B (optional)** — 3–5 readers pick "which sounds more like Nico" on 5 (original, revised-toward-direction) pairs.

7. **Topic-leakage control** — function-word/POS frequencies are *mostly* topic-invariant, not fully. If the contrast authors write about different topics than you, the style layer can win on residual topic signal and you'd mislabel it "voice." Keep the contrast set topic-matched, and run a topic-shuffled (or topic-matched-pairs) control: the style layer should still separate when documents are matched on topic. This is the honest test of NFR2.

**Falsifiers:** AUC ≤ 0.65 → features don't separate you from other writers; shuffle < 60% → drop flow; direction at chance → collapse to scalar-only; A/B at chance → direction real but perceptually invisible, reselect features; **topic-matched AUC collapses to chance → the style layer is measuring topic, not voice.**

---

## 9. Requirements

### Functional
- **FR1** Ingest a personal corpus (markdown/plain text); segment into sentences and paragraphs.
- **FR2** Fit an acceptance region from exemplars (+ optional contrast set).
- **FR3** Score a draft → scalar distance + percentile vs corpus.
- **FR4** Produce an interpretable, signed, confidence-weighted revision **direction** in named features.
- **FR5** Flow analysis: trajectory metrics + circle-back + cohesion, at sentence and paragraph scale.
- **FR6** Emit a machine-readable report (`to_dict()` / JSON).
- **FR7** Expose the scorer as an MCP tool.
- **FR8** Eval harness implementing §8.

### Non-functional
- **NFR1** Local, CPU-only, no network/API at inference; no fine-tuning.
- **NFR2** White-box: every output number maps to a named, documented feature.
- **NFR3** Small-corpus robust (n≈15): shrinkage covariance + feature selection; degrade gracefully.
- **NFR4** Reuse-first: minimize novel *logic* (~300 LOC of glue is the target, but the real cost is dependency reconciliation across the reused libs — see Phase 0.5); pin reused tools.
- **NFR5** Deterministic given fixed inputs + model weights (seeded).
- **NFR6** Python ≥ 3.11; `uv`-managed.

### Dependencies (proposed `pyproject` groups)
- **core:** `numpy`, `scipy`, `scikit-learn`, `spacy` (+`en_core_web_sm`), `sentence-transformers`, `lftk`, `biberplus`, `faststylometry`, `textstat`
- **features-extra (git installs):** `gram2vec`, `writeprints-static`
- **flow-cohesion:** `TAACO`/Coh-Metrix port (note: install friction — desktop backend; evaluate a pure-Python subset first)
- **embeddings (optional):** `transformers` (for STAR), StyleDistance via `sentence-transformers`
- **idiolect-lr (optional):** R + `idiolect` via `rpy2` or subprocess
- **rewrite (Phase 4):** `tinystyler`, `bert-score`
- **mcp:** `mcp`
- **dev:** `pytest`, `ruff`

---

## 10. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Scoring method | Mahalanobis (MVP) → Nini LR (upgrade) | simple Python first; LR is more principled |
| D2 | Core language | Python; R only for the optional Nini LR | all primary tools are Python |
| D3 | Repo | standalone package (this repo), MIT | clean eval + reuse value want their own home |
| D4 | Primary discriminator | classical stylometry, not embeddings | Valla: classical wins at small n |
| D5 | Flow score fusion | report alongside style distance first; fuse later | keep layers legible before combining |

### Open questions
- Which secondary embedding — `StyleDistance` vs `STAR` — and is the SAE decomposition worth it?
- TAACO install path — desktop backend vs a re-implemented pure-Python cohesion subset?
- Is `VADES` code released (would let us bake interpretable axes into the embedding directly)?
- Does the flow layer survive its shuffle-test gate on a ~15-paragraph corpus, or is it too short?

---

## 11. Inputs needed to start Phase 0
- **Exemplar posts** (4–6) — proud of the *writing*, not the topic. These define the voice region R.
- **Contrast set** — other AI-researcher blog posts (the "not-my-voice" pile). Sharpens the boundary and feeds the eval harness.

---

## 12. References & research outputs

This plan is distilled from a four-agent literature + tooling survey. Primary records live in the wiki (`claude_memory/wiki/`):

- **Synthesis page (citations, reuse matrix, eval protocol):**
  `wiki/research/voice-style-metric-space.md`
- **Raw agent reports (verbatim, full tables + URLs):** `wiki/research/raw/`
  - `2026-06-13-style-metric-space-survey.md` — style representation literature (Burrows Delta, StyleDistance, Wegmann, LUAR, Terreau probing).
  - `2026-06-13-discourse-structure-survey.md` — flow/coherence literature (novelty trajectory, BBScore, self-similarity matrix, RQA, TextTiling).
  - `2026-06-13-literature-completeness-audit.md` — adversarial gap audit (Valla, Nini idiolect, LFTK, TAACO/Coh-Metrix, VADES, TinyStyler, SAE interpretability).
  - `2026-06-13-tools-and-evaluation-inventory.md` — software reuse matrix, end-to-end verdict, evaluation methodology.

**Key papers:** Burrows 2002 (Delta); Tyo et al. 2023 (Valla); Nini 2023 (*A Theory of Linguistic Individuality*); Lee & Vajjala 2023 (LFTK); Patel et al. 2025 (StyleDistance); Terreau et al. 2021 (probing), 2024 (VADES); Crossley & Kyle 2016 (TAACO); novelty-trajectory arXiv:2603.01791 / 2602.20647 (**⚠ verify — these IDs are future-dated and may be malformed**); Sheng et al. 2024 (BBScore); Foote 1999 (self-similarity matrix); Horvitz et al. 2024 (TinyStyler); Schimel 2012 (*Writing Science*, OCAR).

**Key tools (all reused):** `lftk`, `biberplus`, `gram2vec`, `writeprints-static`, `faststylometry`, `sentence-transformers`, `TAACO`, `wtpsplit`, `scikit-learn`, `tinystyler`, the `mcp` SDK; `idiolect` (R, optional LR scoring).
