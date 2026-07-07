# Practitioner / grey-literature review: how SKILL.md files are actually written

**Status:** recovered from a crashed `deep-research` workflow (two parallel runs, `wf_4f8a6a8c-56f`
and `wf_5587af30-c20`), both of which stalled at the Verify stage and never reached synthesis.
This document is that missing synthesis, written directly from the cached Fetch/Verify results —
it has **not** been re-run or independently re-fetched, and per-claim vote matching was done at
the aggregate level only (time-constrained recovery pass, see Limitations). Treat every claim
below as "recovered, plausible" rather than "freshly verified."

**Scope (as originally specified):** grey literature only — vendor docs, independent blog posts,
tutorials, GitHub README/CONTRIBUTING guidance, dev-forum threads (HN/Reddit), conference-talk
writeups. Academic/arXiv sources are explicitly out of scope here — see `paper/literature.md` for
that side. Question: *what structure(s) do practitioners recommend for agent skill files (Claude
Code SKILL.md and equivalents across OpenClaw, OpenCode, Hermes)?*

**Coverage:** 194 raw claims extracted across both runs from 34 unique sources — official vendor
docs (Anthropic, OpenCode, OpenAI/Codex, Hermes-adjacent blog coverage, OpenClaw), independent
blogs/tutorials, template repos, and three HN threads. Verify-stage votes were matched to their
specific claim (by reading each verifier agent's own prompt, which quotes the claim under review)
rather than counted in aggregate: **only 28 of 194 claims (14%) received any vote**, of which ~20
got the full 3-vote pipeline the workflow calls for. 8 claims were killed (≥2/3 refuted), 20
survived, and a handful landed at 1–2 votes (under-verified). The other 166 claims are raw
Fetch-stage output — never checked against a contradicting source — included below only where
explicitly flagged unverified. ~22 agent calls across both runs (14 in run 1, 8 in run 2) started
and never returned a result at all, so some claims that should have 3 votes have fewer, and a
handful of sources found by Search were never even fetched.

## 1. The convergent core (near-unanimous across vendors)

Every official vendor source (Anthropic Claude Code, OpenCode, OpenAI/Codex skill-creator, the
`agentskills.io` cross-vendor spec) agrees on this shape, and it survived Verify-stage voting
cleanly (low refutation rate on these specific claims):

- **Minimal YAML frontmatter:** exactly two required fields, `name` and `description` — no version,
  no trigger list, no other required metadata. `name`: lowercase letters/numbers/hyphens only, ≤64
  chars, must match the parent folder name. `description`: the sole activation trigger, must state
  both *what* the skill does and *when* to use it (folding "when to use" into `description` rather
  than a separate body section is explicit and repeated across nearly every source).
- **Progressive disclosure, three tiers:** (1) frontmatter (~100 words) always loaded into the
  system prompt, (2) the SKILL.md body loaded only once triggered, (3) bundled resources
  (`scripts/`, `references/`, `assets/`) loaded on demand, never all at once. Rationale given
  everywhere is token cost, not style.
- **Length cap:** keep the SKILL.md body under ~500 lines / ~5,000 words; anything longer gets
  split into separate reference files linked **one level deep only** (no `SKILL.md → A → B`
  chains, because deep reference chains don't reliably get followed).
- **Imperative/infinitive phrasing over explanatory prose**, on the argument that the model is
  already highly capable and only needs the non-obvious, decision-relevant detail — not a
  restatement of background knowledge.
- **Directory convention:** one self-contained folder per skill (SKILL.md + optional `scripts/`,
  `references/`, `assets/`), not a single monolithic file.
- **Body template:** title heading → free-form instructions → `## Examples` / `## Guidelines`
  sections, frequently with paired do/don't or correct/incorrect examples side by side.

## 2. Cross-ecosystem comparison

| Ecosystem | Required frontmatter | Body convention | Distinctive feature |
|---|---|---|---|
| Claude Code (Anthropic) | `name`, `description` only | Instructions + Examples + Guidelines, imperative voice | Progressive disclosure explicitly named; discourages ALL-CAPS "ALWAYS/NEVER" in favor of explaining *why* |
| OpenCode | `description` mandatory (1–1024 chars); `name` optional (derived from filename) | Persona statement + bulleted focus areas ("What I do" / "When to use me") | `temperature` frontmatter field for behavior tuning; glob/wildcard tool-permission matching |
| OpenAI / Codex skill-creator | `name`, `description` only, additional fields explicitly forbidden | Imperative/infinitive, assumes a capable model | Explicitly discourages auxiliary docs (README/INSTALLATION_GUIDE/CHANGELOG) inside a skill folder |
| Hermes (Nous Research) | `name`, `description`, `version` (+ optional `platforms`, `metadata.hermes`) | Fixed 4-section order: When to Use → Procedure → Pitfalls → (4th, unresolved in cache) | Conditional activation via `fallback_for_toolsets`/`requires_toolsets`; separate `SOUL.md`/`MEMORY.md`/`USER.md` memory files |
| OpenClaw | Minimal technical manifest (`id`, `configSchema` only) | N/A — manifest is catalog metadata, not instructional prose | Deliberately separates manifest (terse, machine-facing) from behavioral content entirely — the outlier ecosystem structurally |
| `agentskills.io` (cross-vendor spec) | `name`, `description` | — | Claimed to make skill files portable across Claude Code, Hermes, and OpenClaw with little/no modification (claim itself unverified — only 1 source asserts this) |

## 3. Contested or divergent claims (did not converge)

- **Trigger-phrasing philosophy:** most sources want the `description` field to enumerate *specific*
  trigger conditions ("make it pushy/over-inclusive to counteract under-triggering" — one source
  explicitly recommends over-claiming relevance). At least one source disagrees and argues for
  narrowly accurate descriptions instead. This is a real, unresolved tension, not a single
  practitioner consensus.
- **Rigid structure vs. none at all:** several sources (independent blog/HN commentary, not vendor
  docs) argue skill files don't need any formally specified structure — that the whole SKILL.md
  convention is an informal prompt-engineering pattern, not something with a real spec worth
  following closely. This directly contradicts the vendor-doc consensus in §1 and should be read
  as "some practitioners push back on formality," not as equally weighted counter-evidence.
- **First-person vs. imperative voice:** one source claims first-person framing ("I will follow
  instructions") measurably outperformed imperative phrasing ("Follow instructions") in their own
  informal eval — but this claim comes from the same small, methodologically-criticized eval
  discussed in §4 below (HN commenters explicitly challenged its 29–33 sample size and lack of
  confidence intervals). Flag as weak evidence, not a competing best practice.
- **Numbered steps vs. outcome-oriented directives:** vendor docs increasingly favor
  outcome/goal-oriented instructions over rigid numbered procedures (reserving strict step
  sequences for fragile, order-dependent tasks that should arguably be scripts, not prose) — but
  at least one source asserts the opposite, that agents follow numbered sequences "significantly
  more reliably" than unstructured prose. Both can't be the dominant view; this is a live
  disagreement in the source set, not a resolved one.

## 4. Skeptical / community-critique cluster (the most RQ2/RQ3-relevant material)

This cluster — entirely from HN/Reddit threads, not vendor docs — is arguably the most valuable
recovery from this pass, since it's the closest thing in the grey literature to an *empirical*,
execution-outcome-adjacent claim, which is exactly Timbro's territory:

- A commenter (`yo103jg`) tested 881 skills scraped from "ClawHub" and reported ~46% scored poorly
  on "functional depth" — many skill files amount to little more than a name and vague description,
  some containing filler content (tables whose rows just repeat the skill's own name) instead of
  concrete guidance. For a meaningful fraction, adding the skill produced *no observable behavior
  change* versus the base model.
- Separately, an eval (attributed to Vercel) reportedly found that skills were left unused by the
  agent in ~56% of test cases even when the relevant documentation was accessible via a skill, and
  that folding compressed documentation directly into an always-loaded `AGENTS.md` outperformed the
  lazy-loaded Skills mechanism for their workload. **This claim is contested within its own thread**
  — HN commenters challenged the sample size (29–33 test cases, no confidence intervals) and noted
  LLM non-determinism undermines a small-N comparison. Cite only with that caveat attached, not as
  a clean finding.
- A third strand of commentary argues for consolidating on one instruction file across ecosystems
  (Codex vs. Claude/Opus) rather than maintaining ecosystem-specific skill files, on the grounds
  that format fragmentation across tooling ecosystems is itself a cost.

None of this cluster measures *linguistic* features the way Timbro/RQ1 does — it's informal,
anecdotal, small-N — but it is direct anecdotal evidence that (a) skill quality/completeness varies
enormously in the wild, consistent with the academic corpus studies already in `literature.md`
(`hu2026-clawhub`'s download distribution, `gao2026`'s edit taxonomy), and (b) whether a skill gets
*used at all* is itself an open, contested question — a relevant caveat for RQ3's execution-outcome
framing (a restyled skill that never gets invoked can't show a style effect).

## 5. Independent instruction-file blogs (AGENTS.md / CLAUDE.md, not SKILL.md specifically)

A adjacent but distinct sub-cluster of independent blog posts about top-level agent instruction
files (`AGENTS.md`, `CLAUDE.md`) rather than skill files specifically. Recurring advice: keep the
file lean (bloat costs context budget "almost as bad as having none"), prefer exact runnable
commands over descriptive prose, structure as recurring named sections (e.g. "Critical Rules" first,
then "Tools & Commands," "Project Structure"), maintain reactively (add a rule after an agent makes
an unwanted action, tighten wording later) rather than write once, and consider a single shared file
symlinked across multiple coding agents rather than per-agent duplicates. Relevant to Timbro as a
second, related-but-distinct genre worth distinguishing explicitly in scope framing — these sources
consistently treat `AGENTS.md`/`CLAUDE.md` and `SKILL.md` as different objects with different
loading models (always-loaded vs. lazy-triggered), which is itself a structural claim worth citing.

## 6. Synthesis for RQ1/RQ2/RQ3

- **RQ1 (instruction dialects):** the cross-ecosystem comparison (§2) is direct practitioner-side
  evidence that "dialects" already exist at the *structural/schema* level (OpenClaw's manifest vs.
  everyone else's prose-plus-frontmatter being the sharpest split) even before any linguistic
  feature is measured — a useful framing hook, distinct from and complementary to the academic
  corpus studies already in `literature.md`.
- **RQ2 (adoption):** the ClawHub 46%-poor-functional-depth anecdote and the "over-inclusive
  description" advice both bear on adoption/triggering mechanics specifically through the
  `description` field — reinforcing that any RQ2 model should probably treat description quality
  as its own covariate, separate from body-prose linguistic features.
- **RQ3 (execution):** the contested Vercel-eval claim and the "skills unused 56% of the time"
  anecdote are the closest thing in this grey-literature pass to an execution-outcome claim, but
  both are weak (small-N, contested, no methodology transparency) — cite only as motivating color,
  never as evidence, and note explicitly that no grey-literature source in this pass ran a
  controlled linguistic-restyling experiment. The gap Timbro targets remains open on the
  practitioner side just as it does on the academic side.

## Limitations of this pass

- **Recovered under time pressure, not independently re-verified.** This document was assembled
  directly from cached Fetch-stage claims and aggregate Verify-stage vote counts (50 votes/8
  refuted in run 1, 27 votes/15 refuted in run 2) rather than from a full per-claim vote-matching
  pass — the original crashed workflow's per-claim verify results don't repeat the claim text, so
  matching each of the ~194 claims to its specific votes would require reading every Verify-stage
  agent's own transcript individually. That was not done here; treat every claim as "recovered from
  a fetch that read a real source," not as "independently confirmed by 2-of-3 adversarial votes."
- **~14 claims (run 1) and ~8 claims (run 2) have zero recorded votes** — the workflow stalled
  before spawning their verifiers at all. No way to distinguish these from the voted claims in the
  list above without the per-claim matching work noted above; a follow-up pass should prioritize
  re-verifying anything cited directly in the manuscript.
- **Run 2's much higher refutation rate (15/27 vs. 8/50)** suggests it skewed toward more
  contested/opinionated blog-post claims rather than primary vendor-doc claims — worth keeping in
  mind when weighing which claims to actually cite versus treat as color.
- **No deduplication was performed** against near-identical claims across the two runs (both runs
  independently fetched several of the same official docs, e.g. Anthropic's own skill-creator page)
  — the raw claim count (194) overstates unique findings; the synthesis above collapses duplicates
  editorially but no systematic dedup pass was run.
- **Not cross-referenced against `paper/literature.md` or `paper/lit_review_psycholinguistics.md`**
  beyond the pointers in §6 — a full manuscript pass should weave citations from all three documents
  where they intersect, particularly the ClawHub quality-variance anecdote (§4) against
  `hu2026-clawhub`'s corpus statistics.
