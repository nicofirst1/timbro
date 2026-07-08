# Psycholinguistic and corpus-linguistic foundations

**Status:** first pass, compiled 2026-07-06 via seven parallel verified-citation searches (WebSearch/
WebFetch; every entry below was confirmed against a real abstract/publisher page before inclusion).

This review is deliberately **not** about LLMs, prompting, or the agent-skill ecosystem — that
related-work ground is covered in `paper/literature_review.md`. Its job is different: to ground the
`timbro analyze` feature groups (PLAN.md §4 "WS2 — Issue A") and the RQ1 clustering design (README
§"WS3", ADR-0004 "D3 clustering") in the pre-existing psycholinguistics and corpus-linguistics literature
that studies exactly these properties of English text — readability, lexical diversity, syntactic
complexity, cohesion, stance/hedging, register variation, and function-word distributional style —
independent of any LLM or agentic framing. Every feature group in Issue A has a decades-deep, mostly
non-computational lineage; this document is the citation trail for that lineage, organized by
feature group, plus a dedicated section on the single most load-bearing precedent for the whole
paper's clustering design: Biber's Multidimensional Analysis of register variation.

## 1. Readability & text difficulty (`read_*`, `desc_*`)

Readability research splits into two generations. The 1970s produced purely surface-count formulas;
a Coh-Metrix-descended tradition then showed that indices closer to actual cognitive processing load
predict real comprehension and reading time better than syllable/sentence counts alone.

- **Kincaid, Fishburne, Rogers & Chissom (1975)**, Institute for Simulation and Training / Naval
  technical report, "Derivation of New Readability Formulas." Introduced the Flesch-Kincaid Grade
  Level and Automated Readability Index — both pure syllable/word/sentence-count formulas. Direct
  ancestor of `read_flesch_kincaid_grade`.
- **Bailin & Grafstein (2001)**, *Language & Communication*, 21(3), 285–301, "The linguistic
  assumptions underlying readability formulae: a critique." Argues classic formulas conflate surface
  counts with actual processing difficulty, which depends on syntactic and discourse structure the
  formulas never measure. Motivates pairing `read_*` with `syn_*`/`coh_*` rather than reporting a
  single legacy score.
- **Graesser, McNamara, Louwerse & Cai (2004)**, *Behavior Research Methods, Instruments, &
  Computers*, 36, 193–202, "Coh-Metrix: Analysis of text on cohesion and language." Introduced a
  multilevel text-analysis tool computing 100+ cohesion/syntax/lexical indices beyond surface
  readability — the direct methodological ancestor of "Coh-Metrix-style" indices named throughout
  the Issue A spec.
- **Crossley, Skalicky, Dascalu & McNamara (2017)**, *Discourse Processes*, 54(5–6), 340–359,
  "Predicting Text Comprehension, Processing, and Familiarity in Adult Readers." Models combining
  psycholinguistic/cognitive indices (word familiarity, syntactic complexity, cohesion) outperform
  classic formulas at predicting real reading time and comprehension.
- **Crossley, Skalicky & Dascalu (2019)**, *Journal of Research in Reading*, 42(3–4), 541–561,
  "Moving beyond classic readability formulas." Reinforces the above, recommending multi-index
  cognitive/discourse feature sets over single-formula scores — direct justification for treating
  `read_*` as a suite rather than a scalar, and for keeping `log(desc_tokens)` a separate covariate
  rather than a difficulty measure in its own right.

## 2. Lexical diversity & frequency (`lex_*`)

Two sub-literatures ground `lex_*`: a psychometrics-of-vocabulary-diversity tradition that fixes
type-token ratio's (TTR) dependence on text length, and a psycholinguistic word-frequency-effects
tradition justifying rarity as a cognitive/sophistication signal rather than an arbitrary count.

- **Tweedie & Baayen (1998)**, *Computers and the Humanities*, 32, 323–352, "How Variable May a
  Constant Be?" Empirically shows most proposed "length-constant" lexical-richness measures are not
  actually constant across text length — the exact problem MTLD is built to solve, and the reason
  `lex_*` avoids raw TTR.
- **Malvern & Richards (vocd-D)**. Fits a curve of TTR decline against token count, rather than a
  single-sample TTR, as a length-independent diversity estimate; direct ancestor of HD-D.
- **McCarthy & Jarvis (2010)**, *Behavior Research Methods*, 42(2), 381–392, "MTLD, vocd-D, and
  HD-D." The canonical validation paper: shows HD-D is a closed-form hypergeometric approximation of
  vocd-D, and introduces MTLD (mean token-sequence length to reach a fixed 0.72 TTR threshold,
  averaged forward/backward). Direct citation for both `lex_*` measures via the `lexical-diversity`
  package.
- **Laufer & Nation (1995)**, *Applied Linguistics*, 16(3), 307–322, "Vocabulary Size and Use:
  Lexical Richness in L2 Written Production." Introduces the Lexical Frequency Profile — proportion
  of a text's vocabulary outside high-frequency bands as a sophistication measure, validated against
  independent proficiency groups. Grounds "low-frequency proportion = jargon/sophistication" as a
  construct, with `wordfreq`'s continuous scores replacing discrete frequency bands.
- **Brysbaert & New (2009)**, *Behavior Research Methods*, 41, 977–990, "Moving beyond Kučera and
  Francis." Shows modern corpus-derived frequency norms (SUBTLEX) predict lexical-decision latency
  far better than classic word lists; frequency is "arguably the most important variable in
  word-recognition research" — justifies using a modern frequency aggregator (`wordfreq`) rather
  than a stale list.
- **Zipf (1949)**, *Human Behavior and the Principle of Least Effort*, Addison-Wesley. Founding
  statement of the rank-frequency power law; grounds treating rarity as a distributional-rank
  property rather than a flat frequency cutoff.

## 3. Syntactic complexity (`syn_*`)

Two converging traditions ground `syn_*`: dependency-distance psycholinguistics (shorter
head-dependent distances as lower processing cost) and L2/corpus syntactic-complexity metrics
(clausal-embedding and subordination counts as structural-elaboration proxies) — both operationalize
"syntactic complexity" as directly countable from a dependency parse, exactly the shape of our
extraction.

- **Gibson (1998)**, *Cognition*, 68(1), 1–76, "Linguistic complexity: Locality of syntactic
  dependencies." Introduces Dependency Locality Theory: processing cost has an integration
  component (linking a new word to an earlier dependency head) and a storage component (predicted
  heads still owed); longer dependency distance raises integration cost. Theoretical foundation for
  treating raw dependency distance/depth as a processing-difficulty proxy.
- **Liu, Xu & Liang (2017)**, *Physics of Life Reviews*, 21, 171–193, "Dependency distance: A new
  perspective on syntactic patterns in natural languages." Synthesizes evidence for Dependency
  Distance Minimization as a cross-linguistic universal, with an empirical ceiling near 3 words per
  dependency on average — a corpus baseline for sanity-checking `syn_*` distributions.
- ***Journal of Quantitative Linguistics* (2021), 29(4), "Syntactic Complexity of Different Text
  Types: From the Perspective of Dependency Distance Both Linearly and Hierarchically."** Different
  text types show systematically different dependency-distance/tree-depth profiles when measured
  both linearly and hierarchically — direct precedent for using dependency distance *and* tree depth
  together to separate registers, structurally analogous to distinguishing instruction dialects.
- **Lu (2010)**, *International Journal of Corpus Linguistics*, 15(4), 474–496, "Automatic analysis
  of syntactic complexity in second language writing." Introduces the L2 Syntactic Complexity
  Analyzer: 14 automated indices spanning sentence-, clause-, and phrase-level complexity (clauses
  per T-unit, complex-nominal ratio, subordination ratio), validated against hand-coded writing
  samples. Direct methodological ancestor of counting `ccomp/xcomp/advcl/acl/relcl` as a
  clausal-embedding depth measure.

## 4. Cohesion & coherence (`coh_*`)

Coh-Metrix and its associated line of work operationalize cohesion as explicit lexical/referential
overlap and semantic relatedness between adjacent textual units, distinguished from coherence (the
reader-side mental representation cohesion devices support). This is the direct ancestor of a
`coh_*` group built from (a) a deterministic adjacent-sentence lemma/argument-overlap ratio and
(b) an embedding-based coherence score as an LSA-style proxy.

- **Graesser, McNamara, Louwerse & Cai (2004)** — see §1. Introduces cohesion indices (co-reference,
  connectives, LSA-based semantic overlap) alongside readability.
- **McNamara, Louwerse, McCarthy & Graesser (2010)**, *Discourse Processes*, 47(4), 292–330,
  "Coh-Metrix: Capturing Linguistic Features of Cohesion." Catalogs referential, causal, connective,
  and LSA-based cohesion indices and how they diverge from surface readability — grounds the
  conceptual split between `coh_*` and `read_*`/`desc_*`.
- **Graesser, McNamara & Kulikowich (2011)**, *Educational Researcher*, 40(5), "Coh-Metrix: Providing
  Multilevel Analyses of Text Characteristics." Principal-component analysis over 37,520 texts
  isolates referential and causal cohesion as factors independent of syntactic simplicity and
  narrativity — empirical precedent that cohesion is its own measurable axis, not a readability
  subcomponent.
- **Landauer, Foltz & Laham (1998)**, *Discourse Processes*, 25(2–3), 259–284, "Introduction to
  Latent Semantic Analysis." Establishes LSA as a vector-space method for measuring semantic
  relatedness between text spans, including adjacent-sentence coherence — direct precedent for using
  sentence-embedding similarity as the LSA-style half of `coh_*`.
- **Grosz, Joshi & Weinstein (1995)**, *Computational Linguistics*, 21(2), 203–225, "Centering: A
  Framework for Modeling the Local Coherence of Discourse." Foundational symbolic theory: local
  coherence depends on tracking a discourse's most salient entity across adjacent utterances —
  theoretical grounding for why adjacent-sentence entity/lemma overlap is a linguistically motivated
  coherence proxy, not an arbitrary heuristic.
- **Barzilay & Lapata (2008)**, *Computational Linguistics*, 34(1), 1–34, "Modeling Local Coherence:
  An Entity-Based Approach." Operationalizes centering-style local coherence as an entity-grid
  tracking grammatical-role transitions across sentences, validated against text-ordering/coherence
  tasks — the nearest corpus-linguistic precedent for converting entity/argument continuity into a
  numeric coherence score, the same move `coh_*`'s lemma-overlap ratio makes in simplified form.

## 5. Stance, hedging & metadiscourse (`dict_*`)

Hedging and boosting are two poles of a single epistemic-stance axis: writers mark how confidently
they commit to a proposition, and this marking is lexically enumerable, corpus-countable, and
disciplined by genre/field/language background rather than idiosyncratic. Hyland's interactional-
metadiscourse model is the dominant framework operationalizing this and is replicated across many
corpora with consistent hedge/booster asymmetries by genre and field — direct justification for a
`dict_*` design that counts fixed hedge/booster word lists rather than learning stance as a latent
variable.

- **Lakoff (1973)**, *Journal of Philosophical Logic*, 2(4), 458–508, "Hedges: A Study in Meaning
  Criteria and the Logic of Fuzzy Concepts." Foundational coinage of "hedge" as a word that makes
  meaning fuzzier or less fuzzy — the conceptual ancestor of all corpus hedge-counting work, and the
  reason `dict_hedge_per_1k` counts a lexical *class* rather than a single keyword.
- **Hyland (1998)**, *Hedging in Scientific Research Articles*, John Benjamins. Book-length corpus
  study establishing hedges as pervasive, functionally motivated features of scientific prose, not
  noise — justifies treating hedge density as a meaningful, non-error signal in skill-file prose.
- **Hyland (2005)**, *Metadiscourse: Exploring Interaction in Writing*, Continuum. The canonical
  hedges/boosters/attitude-markers/engagement-markers/self-mentions/reader-pronouns taxonomy — the
  direct source of the hedge and booster word lists underlying `dict_hedge_per_1k` and the
  certainty/booster counts (per README §"Issue A": "hedges (Hyland's published hedge list);
  certainty/boosters (Hyland's boosters)").
- **Deng & He (2023)**, *Frontiers in Psychology*. Corpus study (360 research-article conclusions,
  English + Chinese, 4 disciplines) applying Hyland's stance model: English writers hedge far more
  than Chinese writers (24.8% vs. 11.9%) while Chinese writers boost more; soft sciences hedge more,
  hard sciences boost more. Empirical precedent that hedge/booster ratios vary systematically by
  register/field — supports using them as clustering-relevant axes rather than assuming one global
  baseline.
- **Chou, Li & Liu (2023)**, *PLoS One*, "Representation of interactional metadiscourse in
  translated and native English." Corpus-assisted comparison: translated English systematically
  underuses hedges, boosters, and attitude markers relative to native English, modulated by genre —
  a caution that hedge/booster density is sensitive to source population, analogous to a possible
  register shift across tooling ecosystems in our own corpus.
- **Lingard (2020)**, *Perspectives on Medical Education*, "The Academic Hedge Part I: Modal Tuning
  in Your Research Writing." Practitioner-facing account tabulating modal verbs/adverbs/lexical verbs
  along a certainty spectrum — a ready-made weak-to-strong certainty scale usable to extend or
  sanity-check the Hyland-derived certainty/booster lexicon.

## 6. Register variation, multidimensional analysis & instructional-genre studies (RQ1 clustering; `struct_*`/imperative `dict_*`)

This is the single most load-bearing cluster for the paper's methodology. Douglas Biber's
Multidimensional Analysis (MDA) of register variation factor-analyzes a large set of co-occurring
lexico-grammatical features across a corpus, extracts continuous "dimensions" of variation (each a
bundle of features that pattern together), and locates registers as points along those dimensions
rather than as discrete pre-labeled categories. Methodologically this is standardized-feature-vectors-
in, factor/cluster-structure-out — exactly the shape of our own plan to standardize `desc_*`/`syn_*`/
`lex_*`/`dict_*` features and run PCA→HDBSCAN over them to find "instruction dialects" (PLAN.md §4 "WS3",
ADR-0004 "D3 clustering"). A separate, complementary sub-literature analyzes procedural/instructional
registers specifically, giving direct linguistic precedent for the imperative-mood and
conditional-connective features in `dict_*`.

- **Biber (1988)**, *Variation across Speech and Writing*, Cambridge University Press. Founding MDA
  study: factor-analyzes 67 co-occurring lexico-grammatical features across spoken/written registers,
  deriving six continuous functional dimensions (e.g. "involved vs. informational production,"
  "narrative vs. non-narrative discourse") rather than discrete categories. Direct methodological
  ancestor of the PCA→HDBSCAN clustering design, and validation that "cluster a standardized feature
  battery, then name clusters by their most-deviant features" is an established method, not an ad hoc
  choice.
- **Biber & Conrad (2009, 2nd ed. 2019)**, *Register, Genre, and Style*, Cambridge University Press.
  Distinguishes register (situational/functional co-occurrence), genre (conventional structure), and
  style (aesthetic choice) as three complementary lenses — supplies the vocabulary to justify why
  RQ1 targets *register* (feature co-occurrence across ecosystems) rather than genre-structure or
  authorial style.
- **Biber & Egbert (2018)**, *Register Variation Online*, Cambridge University Press (see also Biber
  & Egbert, *ICAME Journal*, 2016, "Register Variation on the Searchable Web"). MDA applied at scale
  to the 1.9-billion-word CORE web corpus (1.8M documents, 27 register categories including FAQs and
  how-to/instructional pages), deriving dimensions of online register variation. The closest
  large-scale precedent for applying MDA-style clustering to heterogeneous, non-curated web text —
  directly analogous to clustering SKILL.md files scraped across GitHub/registries — and evidence
  that instructional/how-to registers are already a recognized category in this framework.
- **Swales (1990)**, *Genre Analysis: English in Academic and Research Settings*, Cambridge
  University Press. Founding ESP genre-analysis text: defines genre via shared communicative purpose
  and discourse-community conventions, with move-structure analysis as the core method — background
  precedent for treating agent-skill files as a genre with a conventional communicative purpose
  (instructing an agent).
- **Vander Linden (1994)**, *Proceedings, 7th International Workshop on Natural Language Generation*,
  "Generating Precondition Expressions in Instructional Text." Corpus-based functional analysis of
  instructional writing (recipes, manuals, application forms), mapping communicative-context features
  to the grammatical forms writers use to express preconditions — direct precedent for treating
  conditional/logical connectives (`if/then/else/when/unless`) as a functionally motivated register
  marker of instructional text.
- **Vander Linden & Di Eugenio (1996)**, *Proceedings of COLING-96*, "A Corpus Study of Negative
  Imperatives in Natural Language Instructions." Coded corpus study of "preventative expressions"
  (warnings/negative imperatives) in instructional texts, with inter-coder reliability and
  correlations between communicative function and grammatical form — the closest existing
  corpus-linguistic precedent specifically for imperative-mood/directive-speech-act analysis in
  procedural text, directly supporting the construct validity of `dict_imperative_ratio` and the
  negation-list feature as established register markers rather than invented ones.

## 7. POS/function-word distributional stylometry (`posdep_*`)

A well-established corpus-linguistic and stylometric tradition holds that the distribution of
high-frequency function words and grammatical categories — not topical content words — carries a
stable, largely unconscious authorial or genre signature. This tradition predates and is
methodologically independent of any NLP-model literature, relying on simple frequency counting and
classical statistics, exactly the deterministic-counting posture `posdep_*` takes.

- **Mosteller & Wallace (1963)**, *Journal of the American Statistical Association*, 58(302),
  275–309, "Inference in an Authorship Problem." Settled the disputed-Federalist-Papers authorship
  question using Bayesian analysis of ~30 function words screened for stable, topic-independent usage
  rates — establishes the core premise `posdep_*` inherits: function-word/grammatical-category
  frequency is a topic-robust style signal.
- **Karlgren & Cutting (1994)**, COLING 1994 (ACL Anthology C94-2174), "Recognizing Text Genres with
  Simple Metrics Using Discriminant Analysis." Classifies documents into genre categories using
  distributional features (pronoun counts, present-tense verb counts) via discriminant analysis —
  direct precedent for using POS-category rates as genre-discriminating features, the same logic
  behind clustering `posdep_*` vectors by ecosystem/register in RQ1.
- **Burrows (2002)**, *Literary and Linguistic Computing*, 17(3), 267–287, "'Delta': A Measure of
  Stylistic Difference and a Guide to Likely Authorship." Introduces Delta: z-score standardized
  frequencies of the most-frequent words compared via Manhattan distance — the canonical method for
  turning a frequency-vector style representation into a quantitative distance/clustering measure,
  methodologically the closest analogue to computing distances between `posdep_*` vectors.
- **Argamon (2008)**, *Literary and Linguistic Computing*, 23(2), 131–147, "Interpreting Burrows's
  Delta: Geometric and Probabilistic Foundations." Provides the geometric/probabilistic theory behind
  Delta variants — relevant to justifying whichever distance/normalization choice underlies our own
  PCA+HDBSCAN clustering of `posdep_*` vectors.
- **Evert, Proisl, Jannidis, Reger, Pielström, Schöch & Vitt (2017)**, *Digital Scholarship in the
  Humanities*, 32(suppl_2), ii4–ii16, "Understanding and Explaining Delta Measures for Authorship
  Attribution." Shows vector normalization (unit-length scaling), not distance-metric choice, is the
  critical factor in Delta variants, and supports a "key profile hypothesis" — style lives in the
  pattern of relative deviations, not absolute frequencies. Directly actionable for how `posdep_*`
  vectors should be normalized before clustering.
- **Stamatatos (2009)**, *Journal of the American Society for Information Science and Technology*,
  60(3), 538–556, "A Survey of Modern Authorship Attribution Methods." Surveys evidence for function
  words and POS n-grams as topic-independent style markers — general justification for treating
  `posdep_*` as a style, not content, signal.

## 8. Synthesis

Every feature group in `timbro analyze` (PLAN.md §4 "WS2 — Issue A") has an independent, pre-LLM
lineage in psycholinguistics or corpus linguistics: `read_*`/`desc_*` in the readability-formula
critique tradition (§1), `lex_*` in vocabulary-diversity psychometrics and word-frequency effects
(§2), `syn_*` in dependency-locality theory and L2 syntactic-complexity indices (§3), `coh_*` in
Coh-Metrix cohesion and centering-theory local coherence (§4), `dict_*`'s hedge/booster half in
Hyland's metadiscourse framework (§5) and its imperative/conditional half in corpus studies of
instructional-text register specifically (§6), and `posdep_*` in the function-word stylometric
tradition running from Mosteller & Wallace through Burrows' Delta (§7). This gives every one of the
five ADR-0004 "confirmatory feature family" members — `dict_imperative_ratio`, `dict_hedge_per_1k`,
`read_flesch_kincaid_grade`, `syn_mean_tree_depth`, `coh_lemma_overlap_adj` — a citable construct-
validity anchor independent of the agent-skill literature.

More importantly, §6 supplies methodological cover for the paper's central empirical move: Biber's
MDA is a *direct*, decades-old precedent for exactly the pipeline RQ1 proposes — standardize a battery
of co-occurring linguistic features, reduce dimensionality, cluster, and name clusters by their most
deviant features — applied previously to speech-vs-writing registers (Biber 1988) and, at web scale,
to a 1.9-billion-word corpus that already includes how-to/instructional pages as a register category
(Biber & Egbert 2018). This means RQ1's "instruction dialects" framing is not a novel analytical
method dressed up in agent-skill clothing; it is a well-tested corpus-linguistic method (MDA) applied
to a corpus (agent-skill instruction files) that register linguistics has not yet studied. That
distinction — established method, new corpus — is worth stating explicitly in the manuscript's
methods section, distinct from the RQ1–RQ3 novelty argument already made against Ling et al. and Cho
et al. in `paper/literature_review.md`.

## 9. Limitations of this pass

- **Single-pass, not exhaustive.** Each of the seven clusters above was searched by one agent in one
  pass; none was cross-checked by a second independent search. A few candidate hits were flagged and
  dropped by the searching agents rather than included with a caveat (e.g. a possible *Text* journal
  article on boosting/hedging that could not be independently verified, several neural/computational
  coherence papers, cross-lingual Coh-Metrix variants, GMO/biomedical hedge-detection papers) — worth
  a follow-up pass if a reviewer asks for more coverage in any one section.
- **Dependency-distance corpus evidence is thin by design.** The syntactic-complexity search
  deliberately excluded most post-2010 quantitative-linguistics papers re-testing Dependency Distance
  Minimization on parsed treebanks, since many sit at the boundary of "pure linguistics" vs.
  "NLP-methods paper." If the manuscript wants a broader empirical base for DDM specifically, that is
  a follow-up search, not covered here.
- **Not yet cross-referenced against `paper/literature_review.md`.** The two documents were kept
  strictly separate per the task's scope (this one: pure psycholinguistics/corpus linguistics; that
  one: agent-skill/LLM related work), but the manuscript's actual related-work section will need to
  weave citations from both where they intersect — most obviously in §6 above, and in
  `literature_review.md` §7's "style representation learning" discussion, which briefly touches
  register/style themes from the opposite (learned-embedding) direction.
- **No full-text verification.** All entries were confirmed to exist via abstract/publisher-page
  fetch (title, author, year, venue), consistent with the whitelist-verification standard used
  elsewhere in this project's literature work, but no full-text read was performed to confirm every
  claimed finding in detail before this document was written. Treat findings summaries as
  abstract-level confidence, not full-text-confirmed, until spot-checked.
