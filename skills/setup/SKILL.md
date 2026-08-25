---
name: timbro-setup
description: 'Guided first-run setup for Timbro: pick a purpose, scaffold a voice profile, and ingest exemplars before using score/slop/check for real. Use when the user asks to "set up Timbro", "get started with Timbro", or "onboard me to Timbro" -- or when skills/timbro/SKILL.md''s Match-a-voice flow finds no profiles yet. Run once per profile; re-run to add another purpose.'
disable-model-invocation: true
---

# Timbro setup

Turn "I just installed Timbro" into "I have a usable profile pointed at my own writing." This is a conversation, not a deterministic script -- ask, don't assume.

Pinned CLI version: `timbro@0.7.1`. Commands below substitute `<version>` for it.

## Process

### 1. Check

List existing profiles:

```bash
uvx timbro@<version> profiles list
```

If one already fits the user's purpose, stop here and point them at `skills/timbro/PROFILE.md` for everyday use. Otherwise continue -- this run scaffolds a new one.

### 2. Ask purpose

Ask what they're writing: a personal blog, LinkedIn posts, academic prose, company copy, or something else. Don't assume. The stated purpose becomes the profile's name and `--about` description.

### 3. Scaffold the profile

```bash
uvx timbro@<version> profiles init <name> --about "<purpose, one paragraph>"
```

### 4. Ingest exemplars

Ask for writing that already sounds the way they want to sound -- file paths, a folder, or pasted text saved to a file first. Add each:

```bash
uvx timbro@<version> profiles add-file <name> <file> --to exemplars
```

`.tex` files are accepted; Timbro converts them to cleaned Markdown on ingest if `detex` is installed.

### 5. Seed contrast, then nudge

Seed the new profile's contrast set from Timbro's packaged generic AI-slop examples, pinned to the same release as the CLI so the fetched files always match what's running:

```bash
for f in 01-synergy.md 02-revolutionize.md 03-paradigm.md; do
  curl -sL -o "$f" "https://raw.githubusercontent.com/nicofirst1/timbro/v<version>/src/timbro/sample/contrast/$f"
  uvx timbro@<version> profiles add-file <name> "$f" --to contrast
  rm "$f"
done
```

This makes the profile usable on day one with no curation from the user. Then explicitly nudge: ask if they have a couple of drafts they'd call _off-voice_ -- topic-matched contrast sharpens the profile far more than the generic seed. Point them at `profiles learn` (`skills/timbro/PROFILE.md`, step 6) for accumulating pairs over time as they keep using Timbro.

### 6. Report readiness -- no numeric gate

```bash
uvx timbro@<version> profiles diagnose <name>
```

Surface the output verbatim -- exemplar count, coherence, any warning. Let the user decide when it's good enough; nudge for more exemplars, never force a count.

**The one hard refusal:** zero exemplars (`diagnose` reports "No exemplar files found.") means there is no voice to move toward -- say so plainly, and offer corpus-free `slop`/`check` in the meantime rather than scoring against nothing.

From one exemplar up, there's no cutoff -- score if asked, but relay `diagnose`'s signal honestly (thin corpus, low coherence) instead of presenting a shaky distance as gospel.

### 7. Done

Tell the user the profile is ready, and that `skills/timbro/PROFILE.md`'s workflow now uses it via `--profile <name>`. Re-running this skill scaffolds another profile for a different purpose -- it doesn't touch this one.
