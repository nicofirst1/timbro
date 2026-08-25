# Check prose quality

`<version>` below is the pin declared at the top of `SKILL.md`.

Voice alignment answers _"does this sound like the target?"_ (needs a corpus); the slop rubric answers _"does this read AI-generated?"_. This third, corpus-free capability answers _"is this good prose?"_ — `uvx timbro@<version> check <file>` runs ~30 deterministic Schimel _Writing Science_ checks (buried subject–verb core, passive voice, comma splices, expletive openings, preposition chains, nominalizations, word-echo repetition, metadiscourse frames, caveat/defensive closings, and more), no model, no voice corpus. Reach for it when the user asks to "check my writing", "run a Schimel pass", or clean up prose quality rather than match a specific voice.

The rubric is deliberately **recall-first**: it over-flags rather than stay silent, and you (the agent) are the precision filter. Treat every finding as "worth a look", not "definitely wrong" — judge each against the text, fix the real ones, and silently drop the false positives instead of contorting good prose to satisfy a flag. Severity is the confidence signal: act on `high` findings first; `low` findings are hints.
