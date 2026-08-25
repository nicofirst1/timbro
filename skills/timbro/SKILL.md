---
name: timbro-review
description: Detect deterministic AI-writing tells ("check for AI slop"); check prose quality independent of voice ("run a Schimel pass"); align a draft to a target writing voice ("make this sound like me/us").
---

# Timbro

Pinned CLI version: `timbro@0.7.1`. Commands in the files below substitute `<version>` for it — never hand-edit this line, `scripts/release.sh` keeps it in sync with the release tag.

Three independent capabilities — jump to the one that matches the request:

- **Match a voice** (needs a corpus) → `PROFILE.md`.
- **Detect AI slop, no corpus** → `SLOP.md`.
- **Check prose quality, no corpus, no voice** → `CHECK.md`.
