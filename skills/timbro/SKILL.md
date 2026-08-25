---
name: voice-alignment
description: Detect deterministic AI-writing tells ("check for AI slop", "does this read AI-generated", "de-slop this") and align a draft to a target writing voice. Use when the user asks to check whether text sounds LLM-written, strip AI-slop markers (em-dashes, "it's not X, it's Y", delve/tapestry diction), or to "make this sound like me/us", "match our blog voice", "keep my writing style consistent". Timbro measures the draft mechanically (no LLM-as-judge) and returns named, content-preserving edits; you do the rewriting.
---

# Timbro — voice alignment

LLM prose drifts: today's draft sounds different from last week's, and neither sounds like the human (or company) it's published under. Timbro fixes the _consistency_ problem. It scores a draft against a corpus of writing you've accepted as "your voice" and tells you, in named features, which way to revise — without changing what the text says.

You (the agent) are the rewriter. Timbro is the measurer. Run the loop: **score → edit toward the direction → re-score → repeat until the distance stops dropping.**

## Prerequisites (one-time)

Timbro is pointed at a corpus via two env vars:

- `TIMBRO_EXEMPLARS` → a folder of posts that _define_ the voice (move TOWARD). 6+ pieces is enough.
- `TIMBRO_CONTRAST` → the "not-this-voice" set (move AWAY FROM). Optional but sharpens the direction.

If unset, Timbro falls back to a small packaged sample voice so it runs, but that is **not** the user's voice — never silently score a real draft against the sample.

This skill is pinned to `timbro@0.7.1`. Every command below runs `uvx timbro@<version>` against that exact CLI release, no repo clone needed. `npx skills update` pulls newer instructions together with an updated pin, so instructions and CLI version can never drift apart.

## Pick a direction first — always ask

Before scoring, **discover the available example/contrast pairs and let the user choose**:

1. List the profiles with `uvx timbro@<version> profiles list`.
2. Tell the user what's available and **ask which direction to align**: which set to move _toward_ (exemplars) and which to move _away from_ (contrast). Do not assume — the same draft pulls differently toward "academic" vs "clear" vs "casual".
3. If nothing relevant exists, scaffold one with `uvx timbro@<version> profiles init <name> --about "..."`, then add files with `uvx timbro@<version> profiles add-file <name> <file> --to exemplars` or `--to contrast`.
4. `.tex` files are acceptable in `add-file`: if `detex` is installed, Timbro converts them to cleaned Markdown on ingest.

Prefer profile-native scoring over manual env setup:

```bash
uvx timbro@<version> score draft.md --profile <name>
```

## Workflow

1. **Score the draft.** Write the draft to a file (or pipe via stdin) and run:

   ```bash
   uvx timbro@<version> score draft.md --profile <name>
   ```

   To compare multiple directions in one run:

   ```bash
   uvx timbro@<version> score draft.md --profile academic,clear,casual
   ```

   You get a `distance` (smaller = more on-voice) and a `direction` — a ranked list of named, confidence-weighted moves like `fewer verbs`, `more conjunctions`, `more nouns`. Higher `confidence` = a more reliable signal; act on those first.

   If the draft itself is raw LaTeX source, Timbro will normalize it automatically before scoring when `detex` is installed.

2. **Turn each hint into a concrete edit, preserving meaning.** Hints are POS habits or named AI-tells — translate them:
   - _fewer verbs / more nouns_ → nominalize where natural ("we decided to" → "our decision to"); tighten verb-heavy sentences.
   - _more conjunctions_ → join short choppy clauses into longer compound sentences.
   - _fewer adjectives / adverbs_ → cut intensifiers and hedges.
   - _more / fewer pronouns_ → shift between personal ("I/we") and impersonal framing.
   - _fewer <a named tell>_ (em/en dashes, "it's not X, it's Y", AI-diction like delve/tapestry, signposting, emoji, …) → just delete the marker. Tells are lexical AI-fingerprints, not style dials; removing them only helps.

   Never change the claims, facts, or argument — only _how_ it reads. If the prose is published under a persona with its own style rules (a "voice" skill, a brand guide), apply those rules as you rewrite — Timbro gives the distance, the rulebook gives the words.

3. **Re-score.** Run `timbro score` on your revision. Confirm `distance` dropped. If it rose, you over-rotated — back off the lowest-confidence edits.

4. **(Optional) verify content was preserved.** Save the original and revised text to files and run `uvx timbro@<version> accept original.md revised.md` — it returns `accepted: true` only when the rewrite moved closer to the voice **and** kept the meaning (semantic similarity > 0.85). Use it as the stop condition.

5. **Close the loop — teach the profile (offer, don't assume).** Once the loop converges on an accepted final, offer to save the pair into the profile — never do this silently. Ask the user to confirm first. On confirmation:

   ```bash
   uvx timbro@<version> profiles learn <name> --draft <original-draft> --final <accepted-final> --title <short-descriptive-slug>
   ```

   The final becomes an exemplar (move-toward), the raw draft becomes contrast (move-away). Because the two are topic-matched, this pair is an unusually clean voice signal, and the profile sharpens with each one you add.

   `learn` reuses the same guard as `timbro accept`: it refuses to save unless the final actually scored closer to the voice **and** preserved meaning. A rejected `learn` is a sign the loop didn't really converge — go back to step 2.

   Only save finals a human has approved. That human gate is what keeps the profile from drifting toward generic LLM-polished prose over time.

## When to use this vs. just rewriting

Use Timbro whenever consistency with an _established_ body of writing matters: a personal blog, a company's content, a newsletter persona, anything where "does this sound like us?" is a real question. For one-off prose with no reference voice, plain rewriting is fine — Timbro needs a corpus to measure against.

## Detect AI slop (`slop`) — no corpus needed

When the question is _"does this read AI-generated?"_ rather than _"does this sound like the target?"_, run the corpus-free tells rubric:

```bash
uvx timbro@<version> slop draft.md          # human-readable verdict + ranked tells
uvx timbro@<version> slop draft.md --json   # {verdict, dimensions, findings}
```

(`slop` is an alias for `timbro check --rubric slop`.) It flags the mechanical LLM fingerprints — em/en dashes, "it's not X, it's Y", delve/tapestry/leverage diction, signposting and wrap-up phrases, emoji, curly quotes, bold lead-in bullets, colon-lists, and uniform/staccato rhythm — grouped into four dimensions (diction, construction, rhythm, formatting). Pure regex + POS, offline, **no LLM judging LLM prose**. Reach for it on "check for AI slop", "de-slop this", "does this sound like an LLM wrote it". Each flagged tell is a marker to delete or vary, not a style dial — removing it only helps.

**Corpus-relative mode.** By default `slop` measures against zero — any em-dash is a tell. If a voice legitimately uses some tells (an em-dash habit, say), add `--profile <name>` to baseline against that profile's exemplar corpus instead: a tell is flagged only where the draft _overuses_ it relative to your own norm.

```bash
uvx timbro@<version> slop draft.md --profile <name>   # flag only tells you overuse vs your corpus
```

Use absolute mode (no profile) to answer "is this AI-generated?"; use `--profile` to answer "is this driftier than my own writing?".

## Related: the writing rubric (`check`)

Voice alignment answers _"does this sound like the target?"_ (needs a corpus); the slop rubric answers _"does this read AI-generated?"_. A third, corpus-free capability answers _"is this good prose?"_ — `timbro check <file>` runs ~30 deterministic Schimel _Writing Science_ checks (buried subject–verb core, passive voice, comma splices, expletive openings, preposition chains, nominalizations, word-echo repetition, metadiscourse frames, caveat/defensive closings, and more), no model, no voice corpus. Reach for it when the user asks to "check my writing", "run a Schimel pass", or clean up prose quality rather than match a specific voice.

The rubric is deliberately **recall-first**: it over-flags rather than stay silent, and you (the agent) are the precision filter. Treat every finding as "worth a look", not "definitely wrong" — judge each against the text, fix the real ones, and silently drop the false positives instead of contorting good prose to satisfy a flag. Severity is the confidence signal: act on `high` findings first; `low` findings are hints.
