# Run a rubric (no corpus, no voice)

`<version>` below is the pin declared at the top of `SKILL.md`.

`timbro check <file>` runs three deterministic rubrics as peers: no model, no voice corpus, pure regex/POS/wordfreq. All three share the same **recall-first** philosophy and the same loop: run → fix the real findings, silently drop the false positives → re-run → repeat until the finding count stops dropping. Severity is the confidence signal: act on `high`/`medium` findings first, `low` findings are hints. They differ only in what they flag.

Bare `check` runs **all three** — there is no default rubric. Narrow to one or more with `--rubric <name>[,<name>...]`:

- **"Is this good prose?"** → `--rubric schimel`.
- **"Does this read AI-generated?"** → `--rubric slop`.
- **"Is this too dense / jargon-heavy?"** → `--rubric density`.

```bash
uvx timbro@<version> check draft.md                      # all three rubrics, combined worst-of verdict up top
uvx timbro@<version> check draft.md --rubric slop         # just one
uvx timbro@<version> check draft.md --rubric slop,density # a comma list
uvx timbro@<version> check draft.md --json                # {verdict, rubrics: {<name>: {...}}}
```

## Schimel — prose quality

```bash
uvx timbro@<version> check draft.md --rubric schimel
```

Runs ~30 deterministic Schimel _Writing Science_ checks: buried subject–verb core, passive voice, comma splices, expletive openings, preposition chains, nominalizations, word-echo repetition, metadiscourse frames, caveat/defensive closings, and more. Reach for it on "check my writing", "run a Schimel pass", or general prose-quality cleanup.

## Slop — AI-writing tells

```bash
uvx timbro@<version> check draft.md --rubric slop          # human-readable verdict + ranked tells
uvx timbro@<version> check draft.md --rubric slop --json   # {verdict, rubrics: {slop: {...}}}
```

Flags mechanical LLM fingerprints (em/en dashes, "it's not X, it's Y", delve/tapestry/leverage diction, signposting and wrap-up phrases, emoji, curly quotes, bold lead-in bullets, colon-lists, uniform/staccato rhythm) across four dimensions (diction, construction, rhythm, formatting). **No LLM judging LLM prose.** Reach for it on "check for AI slop", "de-slop this", "does this sound like an LLM wrote it". Each flagged tell is a marker to delete or vary, not a style dial: removing it only helps.

**Corpus-relative mode.** By default the slop rubric measures against zero: any em-dash is a tell. If a voice legitimately uses some tells (an em-dash habit, say), add `--profile <name>` to baseline against that profile's exemplar corpus instead: a tell is flagged only where the draft _overuses_ it relative to your own norm. `--profile` only affects the slop rubric — pair it with `--rubric slop` (or leave slop in the mix on a bare/multi-rubric run).

```bash
uvx timbro@<version> check draft.md --rubric slop --profile <name>   # flag only tells you overuse vs your corpus
```

Use absolute mode (no profile) to answer "is this AI-generated?"; use `--profile` to answer "is this driftier than my own writing?".

## Density — jargon and padding

```bash
uvx timbro@<version> check draft.md --rubric density
```

Flags two things: **padding paragraphs** (a paragraph's content-word ratio trails the document's own mean; that's filler to tighten or cut) and **jargon clusters** (a sentence packs 3+ rare/technical terms, zipf frequency below 3.0, that may not earn their keep or need unpacking for the reader). Reach for it when the ask is "is this too dense", "too much jargon", or "does this pad itself out".
