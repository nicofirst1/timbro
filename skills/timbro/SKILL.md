---
name: timbro-review
description: Run a deterministic writing rubric: AI-slop tells ("check for AI slop"), prose quality ("run a Schimel pass"), density/jargon ("too much jargon"); or align a draft to a target voice ("make this sound like me/us").
---

# Timbro

Pinned CLI version: `timbro@0.8.0`. Commands in the files below substitute `<version>` for it; never hand-edit this line, `scripts/release.sh` keeps it in sync with the release tag.

You (the agent) are the rewriter, Timbro is the measurer. Every capability below runs the same loop: **run the check → edit what it flags → re-run → repeat until it stops improving.** They differ only in what "check" means and what "improving" means. Jump to the one that matches the request:

- **Match a voice** (needs a corpus): improving = `distance` drops → `PROFILE.md`.
- **Run a rubric** (no corpus: slop tells, prose quality, or density/jargon): improving = fewer findings → `RUBRICS.md`.
