# Detect AI slop

`<version>` below is the pin declared at the top of `SKILL.md`.

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
