# Timbro Feature Reference

## Overview

`timbro score` measures how far a draft sits from a target writing voice. It returns one distance number and a set of named revision moves. It never rewrites the text — it tells you which way to move it.

In plain terms: Timbro reads your exemplar posts, learns what your voice looks like on a few dozen measurable features, and reports where a new draft drifts from that and what to change first.

The design splits into two tools:

- **Scalar distance ("how far")** — one number for how unlike your voice the whole draft reads. A pre-trained StyleDistance embedding scored by nearest-neighbor against your exemplar cloud. Empirically calibrated: LOO-AUC 0.859 on real 15-doc voices, vs. ~0.80 for classical features.
- **Ranked direction ("which way")** — everything else, and all of it white-box. 17 grammar (POS) rates + 21 AI-tell detections, each named and weighted by how reliably it marks your voice. Returned as a ranked list of moves like "fewer adjectives, more verbs."

Separately, these axis groups run independently and never feed the distance or ranked direction:

- Markdown structure (11 axes)
- Hedge/booster stance (2 axes)
- Function words (5 axes)
- Concreteness (1 axis)
- Flow (6 axes, computed only on drafts with ≥4 paragraphs)

And a **spans** report re-scores the top-3 worst paragraphs at paragraph granularity, using the same features.

---

## The Scalar Distance

In plain terms: one number for how far off-voice the whole draft reads. Lower is closer; the fields below just normalize and threshold it.

| Feature      | Meaning                                                                                                                                  | How to Read It                                                                                                                               |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `distance`   | k-nearest-neighbor distance (k=1) in standardized StyleDistance embedding space to the nearest exemplar                                  | Raw embedding distance, unitless. Smaller = closer to your voice cloud.                                                                      |
| `distance_z` | `(distance - exemplar_floor) / exemplar_spread`; how far the draft sits outside the typical exemplar region (if exemplar health is "ok") | Z-score of distance against the exemplar-cloud spread. ≤ 0 is roughly "on voice"; > 1 is increasingly off. Returns `null` if corpus is weak. |
| `on_voice`   | Boolean: is the draft's distance within `exemplar_floor + exemplar_spread`?                                                              | `true` = on target; `false` = off target; `null` if corpus is weak.                                                                          |

**Why the embedding?** The embedding is the only feature that reaches the 0.80+ separation gate at 15 exemplars; classical POS/lexical features alone, when fit to this tiny corpus, add noise faster than signal. The StyleDistance model is pre-trained on a broad corpus of writing and content-invariant (it ignores topic), so it generalizes from small exemplar sets.

---

## The Ranked Direction

In plain terms: Timbro checks every named feature, finds the ones that are both far from your usual value and reliable markers of your voice, and lists the biggest ones to fix first.

Direction is computed by z-scoring each white-box feature against the exemplar corpus mean/std, then ranking by **importance = confidence × |z|**, where confidence is the R² (point-biserial correlation) of that feature with the voice label. Only features with importance > 0 and confidence ≥ 0.20 are returned; tells are one-sided (flagged only when over-represented, z > 0). The top 6 moves are returned. Each move is an imperative hint toward the exemplar corpus mean.

### POS Unigram Rates (17 features)

Length-normalized POS rates via spaCy's `pos_` tag. Length-normalization prevents doc length from confounding the signal. (Emitted feature ids prefix the tag with `pos_`, so `ADJ` is `pos_ADJ`.)

| POS Tag | Label                      | Meaning                                                                                       |
| ------- | -------------------------- | --------------------------------------------------------------------------------------------- |
| ADJ     | adjectives                 | Rate of adjectives per token                                                                  |
| ADP     | prepositions               | Rate of prepositions per token                                                                |
| ADV     | adverbs                    | Rate of adverbs per token                                                                     |
| AUX     | auxiliary verbs            | Rate of auxiliary verbs (be, have, will, etc.) per token                                      |
| CCONJ   | conjunctions               | Rate of coordinating conjunctions (and, but, or) per token                                    |
| DET     | determiners                | Rate of determiners (the, a, this) per token                                                  |
| INTJ    | interjections              | Rate of interjections (oh, ah, wow) per token                                                 |
| NOUN    | nouns                      | Rate of nouns per token (nominalization marker)                                               |
| NUM     | numbers                    | Rate of numeric tokens per token                                                              |
| PART    | particles                  | Rate of particles (up, down, off in phrasal verbs) per token                                  |
| PRON    | pronouns                   | Rate of pronouns per token                                                                    |
| PROPN   | proper nouns               | Rate of proper nouns per token                                                                |
| PUNCT   | punctuation                | Rate of punctuation marks per token                                                           |
| SCONJ   | subordinating conjunctions | Rate of subordinating conjunctions (because, if, while) per token                             |
| SYM     | symbols                    | Rate of symbols (/, @, etc.) per token                                                        |
| VERB    | verbs                      | Rate of verbs per token (nominalization marker: high NOUN / low VERB suggests nominalization) |
| X       | other tokens               | Rate of tokens that don't fit other POS categories per token                                  |

**Nominalization**: High NOUN + low VERB density is a common tell of overly complex prose. These two rates are the most interpretable POS pair in the direction.

### AI-Tell Markers (21 features)

Named detections of lexical and phrasal patterns that show up in LLM prose more than in human writing. Each is length-normalized (per 1000 words). Emitted feature ids prefix the name with `tell_` (so `dash` is `tell_dash`). The tell list, and the confidence floor described below, come from two public compilations of AI-writing giveaways: Wikipedia's "Signs of AI writing" and a 3.2M-post Reddit study.

| Name                | Description                                  | Examples                                                                                                     | Meaning                                                                                       |
| ------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| `dash`              | em/en dashes                                 | `—` `–`                                                                                                      | Overuse is the #1 tell in both source corpora; regex.                                         |
| `diction`           | AI-tell word choice                          | full list in the [`_DICTION` regex](../src/timbro/tells.py#L60): delve, tapestry, leverage, realm, robust, … | Terms over-represented in LLM prose; regex.                                                   |
| `not_x_y`           | "it's not X, it's Y" / "not only … but also" | "it's not just a tool, it's a tapestry"; "not only fast but also…"                                           | The "AI accent"; #2 tell in both corpora; regex.                                              |
| `signpost`          | signposting phrases                          | let's dive in, deep dive, when it comes to, it's important to note                                           | Explicit textual navigation; over-scripted; regex.                                            |
| `conclusion`        | wrap-up phrases                              | in conclusion, to sum up, the future looks bright                                                            | Meta wrap-up filler; regex.                                                                   |
| `sycophancy`        | collaborative / sycophantic filler           | great question, hope this helps, happy to help, absolutely!                                                  | Chatbot politeness markers; regex.                                                            |
| `filler`            | filler phrases                               | in order to, due to the fact that, at this point in time                                                     | Needless verbosity; regex.                                                                    |
| `aphorism`          | authority-trope aphorisms                    | at its core, the real question is, at the end of the day                                                     | False profundity; regex.                                                                      |
| `self_narration`    | essay self-narration / meta-framing          | which brings us to, let me back up, we'll come back to                                                       | The piece narrating its own moves; regex.                                                     |
| `apologetic`        | apologetic / over-hedged stance              | I want to be careful, read this as X not Y, take this with a grain of salt                                   | Performed humility; distinct from hedge-word density; regex.                                  |
| `rule_of_three`     | rule-of-three triads                         | "A, B, and C"                                                                                                | Triadic rhythm; overuse is a tell; regex.                                                     |
| `emoji`             | emoji                                        | 🚀 ✨                                                                                                        | Rare in formal prose; regex.                                                                  |
| `curly_quote`       | curly quotation marks                        | " " ' '                                                                                                      | Smart quotes; often AI text run through a converter; regex.                                   |
| `bold_leadin`       | bold lead-in bullets                         | `**Word:** …`                                                                                                | Over-emphasized list headers; regex.                                                          |
| `hr_divider`        | section dividers                             | `---` `***` `___`                                                                                            | Heavy visual structuring; regex.                                                              |
| `rhetorical_opener` | conversational openers                       | Honestly, Look, Here's the thing, Picture this                                                               | Friendly-chatbot voice; regex.                                                                |
| `quote_punct`       | punctuation inside closing quotes            | `word,"` `word."`                                                                                            | Blind American-convention quoting; regex.                                                     |
| `colon_list`        | colon-then-list                              | sentence: a, b, c                                                                                            | Over-scaffolded structure; regex.                                                             |
| `empty_punch`       | contentless opening fragment                 | "The answer is thin."                                                                                        | Abstract first noun, no proper nouns — a pseudo-profound opener; spaCy tagger + noun lexicon. |
| `dropped_subject`   | dropped-subject opener                       | "Dropped the row."                                                                                           | Bare finite verb, no subject — auto-complete texture; spaCy tagger.                           |
| `staccato_run`      | staccato run                                 | 3+ sentences in a row under 8 words                                                                          | Choppy rhythm; auto-complete tell; spaCy sentencizer + word count.                            |

**Tell confidence floor.** Confidence is how reliably a feature separates your voice from the contrast set (an R², 0–1). Tells have a problem here: a clean exemplar corpus contains almost none of them, so there is nothing for the correlation to measure, and their confidence would round to zero — they'd never surface, even in a draft that is full of them. So each tell gets a _floor_ on its confidence, seeded from outside your corpus.

That floor is what "Reddit frequency" refers to. The two public compilations above rank how often each marker gets _cited_ as an AI tell — not how often it appears in text, but how often people name it as a giveaway. The more often a marker is called out, the higher its floor: em-dash overuse tops both lists at 0.70, "it's not X, it's Y" at 0.55, and so on (see [`TELL_PRIOR`](../src/timbro/config.py#L67)). The floor only lifts a tell's confidence; a strong in-corpus signal can still push it higher.

**One-sidedness.** Tells are flagged only when **over-represented** (z > 0) in the draft. They are not penalized when under-represented, so the direction never says "add em-dashes." A tell is an LLM marker, not a feature to tune toward.

---

## Markdown Structure (11 axes)

Scored independently against the exemplar corpus mean/std (no declared prior). Each axis is z-scored; directions are returned only if |z| ≥ 0.5 (MARKDOWN_Z_TOL).

Runs on the **raw markdown** text (markup intact), not the cleaned text.

| Axis                            | Raw Value                                 | Meaning                                             |
| ------------------------------- | ----------------------------------------- | --------------------------------------------------- |
| `struct_heading_count`          | Count of top-level headings               | How many sections                                   |
| `struct_max_heading_depth`      | Deepest heading level (1-6)               | Section nesting depth                               |
| `struct_code_char_ratio`        | Code-block characters / total characters  | Proportion of content in code blocks                |
| `struct_inline_code_char_ratio` | Inline code characters / total characters | Proportion of inline code                           |
| `struct_list_item_ratio`        | List items / total paragraphs             | Density of list structure                           |
| `struct_bullet_list_ratio`      | Bullet list items / total list items      | Bullet vs. numbered ratio                           |
| `struct_ordered_list_ratio`     | Ordered list items / total list items     | Numbered list ratio                                 |
| `struct_table_count`            | Count of markdown tables                  | How many tables                                     |
| `struct_external_ref_count`     | Count of external hyperlinks              | How many outbound links                             |
| `struct_long_paragraph_ratio`   | Paragraphs > 100 words / total paragraphs | Density of chunky prose                             |
| `struct_prose_ratio`            | Prose paragraphs / total paragraphs       | Proportion that is continuous text (vs. lists/code) |

**When no corpus**: If the model was built without exemplars (e.g., `--check` with no profile), markdown_report returns an empty list.

---

## Hedge/Booster Stance (2 axes)

Per-1000-word rates. Uses declared prior [`HEDGE_BOOSTER_REFERENCE`](../src/timbro/config.py#L56) blended with corpus mean/std via `Reference.blend` (see Shared Mechanics, below). Directions fire only if |z| ≥ 0.5 (HEDGE_Z_TOL).

Runs on the **cleaned text** (markdown stripped).

| Axis           | Rate Unit      | Meaning                                                                                                                                                   |
| -------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hedge_rate`   | Per 1000 words | Hedging words/phrases (might, perhaps, could, seem, suggest, arguably, somewhat, fairly, relatively, likely, presumably, roughly, "I think", "I believe") |
| `booster_rate` | Per 1000 words | Assertion boosters (clearly, obviously, certainly, definitely, undoubtedly, always, never, indeed, must, "of course", "in fact", "without doubt")         |

**Declared Prior**: mean=(6.0, 4.0), spread=(4.0, 4.0). A typical prose passage carries a few hedges and a few boosters per 1000 words; dozens/1000 would read as mealy-mouthed or bombastic. The prior reflects Hyland's research that hedges are more common than boosters in careful prose.

**Reports Even With No Corpus**: Unlike markdown (which is corpus-only), hedge/booster always has a reference (the declared prior). With no corpus, the prior passes through unchanged, so `hedge_report` returns usable advice even with `--check` and no profile.

---

## Function Words (5 axes)

Per-1000-word rates. Uses declared prior [`FUNCTION_WORD_REFERENCE`](../src/timbro/config.py#L138) (derived from 750 chunks of 7 Project Gutenberg texts) blended with corpus mean/std via `Reference.blend`. Directions fire only if |z| ≥ 0.5 (FW_Z_TOL).

Runs on the **cleaned text** (markdown stripped).

| Axis               | Rate Unit      | Meaning                                         |
| ------------------ | -------------- | ----------------------------------------------- |
| `first_person_sg`  | Per 1000 words | First-person singular (I, me, my)               |
| `article_rate`     | Per 1000 words | Articles (a, an, the)                           |
| `preposition_rate` | Per 1000 words | Prepositions (in, on, at, by, from, …)          |
| `conjunction_rate` | Per 1000 words | Conjunctions (and, but, or, nor, yet, so)       |
| `pronoun_rate`     | Per 1000 words | All pronouns (he, she, it, they, this, that, …) |

**Declared Prior** (derived from Gutenberg corpus, mean/spread/strength):

- first_person_sg: mean=27.42, spread=25.14
- article_rate: mean=80.52, spread=20.86
- preposition_rate: mean=122.57, spread=17.99
- conjunction_rate: mean=72.36, spread=13.46
- pronoun_rate: mean=112.81, spread=40.16
- Strength: 2.0 (modest pseudo-count; a 5+ doc profile corpus dominates, but the axis still reports something sane with zero corpus)

**Reports Even With No Corpus**: Function-word rates always have a reference. With no corpus, the prior passes through unchanged.

---

## Concreteness (1 axis)

Mean concreteness score (1–5 scale, where 1 is abstract and 5 is concrete/physical). Uses declared prior [`CONCRETENESS_REFERENCE`](../src/timbro/config.py#L109) blended with corpus mean/std via `Reference.blend`. Directions fire only if |z| ≥ 0.5 (CONCRETENESS_Z_TOL).

Runs on the **cleaned text** (markdown stripped). Word ratings come from Brysbaert, Warriner & Kuperman (2014) concreteness norms (37,058 lemmas, frequency-weighted).

| Axis                | Scale | Meaning                                                                      |
| ------------------- | ----- | ---------------------------------------------------------------------------- |
| `mean_concreteness` | 1–5   | Mean concreteness of the draft's words (1 = abstract; 5 = concrete/physical) |

**Declared Prior**: mean=2.7094 (frequency-weighted over the norms), spread=0.2792 (population stdev of document-level concreteness, not lemma-level; derived from 750 x 1000-word chunks of Gutenberg texts), strength=2.0.

**Reports Even With No Corpus**: Concreteness always has a reference. With no corpus, the prior passes through unchanged.

---

## Flow (6 axes)

Computed **only** on drafts with ≥4 paragraphs. Uses paragraph-level embeddings (cached via a separate model) to measure how ideas move through the text. Not z-scored against a corpus: each axis is reported raw, with no direction given.

| Axis                     | Unit | Meaning                                                                                                           |
| ------------------------ | ---- | ----------------------------------------------------------------------------------------------------------------- |
| `speed`                  | 0–1  | Mean novelty of paragraphs (how fast ideas move; 1 = each para is maximally new vs. the running centroid)         |
| `volume`                 | 0–∞  | Spread of paragraphs in embedding space (how much conceptual ground is covered)                                   |
| `circuitousness`         | 1–∞  | Path length / direct start→end distance (wandering vs. linear progression; 1 = straight line)                     |
| `terminal_initial_ratio` | 0–∞  | Ratio of closing novelty to opening novelty (winding up vs. down; > 1 = ends with more new ideas than it started) |
| `circle_back`            | −1–1 | Cosine similarity of first and last paragraphs (Schimel OCAR bookend; 1 = perfect circle back; −1 = inverse)      |
| `coherence`              | 0–1  | Mean adjacent-paragraph cosine (local smoothness of flow; 1 = perfectly smooth; lower = more jumpy)               |

Flow is reported raw because there is no universal target: a novel circles back more than an essay, and that's fine. These axes let you _see_ your text's narrative structure.

---

## Spans

Top-3 worst paragraphs by distance, each re-scored with the same features (distance, POS direction, tells). Each span includes:

- Paragraph index
- Paragraph distance and distance_z
- First 280 characters of the paragraph
- Local direction (top-2 POS/tell moves for that paragraph)
- The worst sentence in that paragraph (longest at embedding distance, with its own top-2 direction)

No new features: spans reuse the distance and white-box features at paragraph granularity.

---

## Shared Mechanics

### Z-Scoring and Confidence Ranking

Every white-box feature is z-scored against the exemplar corpus:

```
z = (value - corpus_mean) / corpus_std
```

Then importance is computed:

```
importance = confidence × |z|
```

where `confidence` is R² (squared point-biserial correlation with the voice label, measuring how reliably this feature separates exemplars from contrast). Features with importance ≤ 0 or confidence < 0.20 are filtered out. Top 6 are returned as the ranked direction. Tells additionally get a confidence floor so they surface even against a clean or absent contrast set — see [AI-Tell Markers](#ai-tell-markers-21-features) above.

### Prior-Blending for Standalone Axis Groups

Hedge, function-word, and concreteness axes have **declared priors** (`Reference` objects with mean, spread, strength). When a corpus is supplied, the prior is blended with the corpus mean/std via [`Reference.blend`](../src/timbro/metric.py#L31):

```python
w = n / (n + strength)
blended_mean = w * corpus_mean + (1 - w) * prior_mean
blended_spread = w * corpus_std + (1 - w) * prior_spread
```

where `n` is the number of corpus documents and `strength` is the prior's pseudo-count.

**With n = 0 (no corpus)**: The prior passes through unchanged (w = 0), so these axes always report something. **With large n**: The corpus dominates; the prior becomes a weak regularizer.

This pattern lets these axes work in two modes: contrastive (when corpus is present) and absolute (when it's not).

### Tolerance Thresholds (Z_TOL)

Markdown, hedge, function-word, and concreteness axes are only flagged with direction hints if |z| ≥ 0.5. This prevents noise from low-signal axes from cluttering the advice. Set once per axis group; not currently tunable.

---

## Which Features Feed What

| Output               | Features                                                                          |
| -------------------- | --------------------------------------------------------------------------------- |
| `distance`           | StyleDistance embedding only (k-NN)                                               |
| `on_voice`           | Embedding distance only                                                           |
| `direction` (ranked) | POS unigrams (17) + tells (21), ranked by confidence × z                          |
| `markdown`           | Struct axes (11), scored vs. corpus mean/std (no feed to distance/direction)      |
| `hedge`              | Hedge/booster rates (2), scored vs. blended prior (no feed to distance/direction) |
| `fw`                 | Function-word rates (5), scored vs. blended prior (no feed to distance/direction) |
| `concreteness`       | Concreteness (1), scored vs. blended prior (no feed to distance/direction)        |
| `flow`               | Paragraph embeddings (6 axes), no z-score or direction                            |
| `spans`              | Distance + direction at paragraph granularity (reuses all white-box features)     |

---

## Profile Evidence and Reliability

The model rates the profile's evidence level on fit:

- **"ok"** (≥1200 words, ≥8 substantive paragraphs): All features are usable; distance is stable.
- **"weak"** (≥1200 words, ≥8 paras but < 2500 words or < 16 paras): Distance is usable but may be noisy; direction may be unstable.
- **"insufficient"** (< 1200 words or < 8 paras): Distance is very noisy; direction is suppressed.

If no TIMBRO_EXEMPLARS or TIMBRO_CONTRAST is set and no `--profile` is passed, `timbro score` runs against the **packaged sample voice** (a small corpus of plain English examples). In this mode, distance and direction are only meaningful as toy examples: they don't reflect your actual voice.
