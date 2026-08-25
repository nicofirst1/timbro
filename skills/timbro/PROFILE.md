# Match a voice

Use Timbro whenever consistency with an _established_ body of writing matters: a personal blog, a company's content, a newsletter persona, anything where "does this sound like us?" is a real question. For one-off prose with no reference voice, plain rewriting is fine: Timbro needs a corpus to measure against.

`<version>` below is the pin declared at the top of `SKILL.md`.

## Setup (one-time per corpus)

No profiles yet (`profiles list` is empty)? Use the `timbro-setup` skill for a guided walkthrough (purpose → profile → exemplars → contrast) instead of guessing. Never silently score a real draft against the packaged sample. The below is quick reference once a profile already exists.

Point Timbro at a corpus with a managed profile: `uvx timbro@<version> profiles init <name> --about "..."`, then add files with `uvx timbro@<version> profiles add-file <name> <file> --to exemplars` (or `--to contrast`).

list of accepted file input:

- tex
- md

If no profile is set, Timbro falls back to a small packaged sample voice so it runs, but that is **not** the user's voice. Never silently score a real draft against the sample.

## Every run

1. **Pick a direction: always ask.** List profiles with `uvx timbro@<version> profiles list`, tell the user what's available, and ask which set to move _toward_ (exemplars) and which to move _away from_ (contrast). Do not assume.

2. **Score the draft.** Write the draft to a file and run:

   ```bash
   uvx timbro@<version> score draft.md --profile <name>
   ```

   To compare multiple directions in one run:

   ```bash
   uvx timbro@<version> score draft.md --profile academic,clear,casual
   ```

   You get a `distance` (smaller = more on-voice) and a `direction`: a ranked list of named, confidence-weighted moves like `fewer verbs`, `more conjunctions`, `more nouns`. Higher `confidence` = a more reliable signal; act on those first.

   If the draft itself is raw LaTeX source, Timbro will normalize it automatically before scoring when `detex` is installed.

3. **Turn each hint into a concrete edit, preserving meaning.** Never change the claims, facts, or argument: only _how_ it reads. If the prose is published under a persona with its own style rules (a "voice" skill, a brand guide), apply those rules as you rewrite.

4. **Re-score.** Run `timbro score` on your revision. Confirm `distance` dropped. If it rose, you over-rotated: back off the lowest-confidence edits.

5. **(Optional) verify content was preserved.** Save the original and revised text to files and run `uvx timbro@<version> accept original.md revised.md`: it returns `accepted: true` only when the rewrite moved closer to the voice **and** kept the meaning (semantic similarity > 0.85). Use it as the stop condition.

6. **Close the loop: teach the profile (offer, don't assume).** Once the loop converges on an accepted final, offer to save the pair into the profile. Never do this silently. Ask the user to confirm first. On confirmation:

   ```bash
   uvx timbro@<version> profiles learn <name> --draft <original-draft> --final <accepted-final> --title <short-descriptive-slug>
   ```

   The final becomes an exemplar (move-toward), the raw draft becomes contrast (move-away). Because the two are topic-matched, this pair is an unusually clean voice signal, and the profile sharpens with each one you add.

   `learn` reuses the same guard as `timbro accept`: it refuses to save unless the final actually scored closer to the voice **and** preserved meaning. A rejected `learn` is a sign the loop didn't really converge. Go back to step 3.

   Only save finals a human has approved. That human gate is what keeps the profile from drifting toward generic LLM-polished prose over time.
