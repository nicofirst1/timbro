# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Breaking:** a FAIL check and a rejected accept exit 3 instead of 0. Printed output is unchanged; scripts that branch on the exit code must handle 3 (#142).
- Drafts over 50,000 words are rejected with a clear message instead of scoring for minutes: `timbro: error: draft is N words; timbro scores drafts up to 50,000 words (split it into sections)`. Applies to `score`, `check` and `accept` (#153).
- The packaged sample voice is 8 trimmed posts from the 18F blog (US public domain, CC0 1.0), replacing the 4 synthetic exemplars. The sample now reaches health "ok" and shows a direction; provenance in `src/timbro/sample/README.md` (#163).
- **Breaking:** every expected CLI error prints `timbro: error: ...`; check and learn errors drop the bare `error:` prefix. A malformed settings.json now fails the command with exit 1 instead of being ignored, and a failed first-run spaCy model install prints one clean line instead of a traceback (#191).
- `accept` rejects `--threshold` outside [0, 1] with a clean error and exit 1, instead of silently accepting a value that can never be meaningful (#158).

### Added

- `timbro profiles diagnose` prints a `health:` line (and includes `health` in JSON) plus the thin-corpus evidence warning `score` already shows, so a thin corpus finally has signal to relay (#163).

### Fixed

- `check` parses and embeds each paragraph once, roughly halving its runtime on long drafts (#192).
- Scoring large drafts is faster: features are extracted once per score instead of once per feature name, span paragraph embeddings are batched into one model call, and the flow novelty curve is linear in the number of paragraphs (#153).
- HD-D (richness axis) is computed locally in a deterministic order, so values no longer depend on PYTHONHASHSEED. Values may differ from 0.9.0 in the last digit (~1 ULP) (#123).
- `accept` prints content similarity with 3 decimals, matching the gate's precision (#158).
- Near-duplicate corpora no longer produce absurd standalone-axis z-scores: axis z is capped at 10 and the row is marked saturated (JSON field saturated, text output (saturated)). Directions use the clamped z (#178).
- GFM tables with leading pipes now count in struct_table_count; scores and fitted corpus stats change for any text containing tables. Bug fix, not a retune (#132).

## [0.9.0] — 2026-10-01

New voice axes, interchangeable rubrics, profile sync across machines, and a module layout that matches the architecture (#110). Several changes are **breaking**; see Removed and Changed.

### Added

- `timbro profiles sync [--init <url>]`: syncs the profile root with a private git remote. It never rebases, force-pushes or auto-resolves, and concurrent `runs.jsonl` appends merge losslessly (#118).
- `$TIMBRO_HOME` (default `~/.timbro`) and `<TIMBRO_HOME>/settings.json`, whose `no_log` flag turns off the learn log. `TIMBRO_NO_LOG=1` still overrides it (#116).
- A debug switch: `TIMBRO_DEBUG=1` or `"debug": true` in `settings.json` prints the full traceback behind a one-line CLI error (#137).
- Readability, lexical richness and entropy axis: Coleman-Liau, HD-D and Shannon entropy. Reported only (#88).
- Politeness strategies axis: the 20 Danescu-Niculescu-Mizil 2013 strategies, reported as N/A when none fire. Reported only (#94).
- `VoiceModel.axis_report(name, text)` and one `AxisReport` dataclass for every blend-style axis. A new axis needs only its own file plus an import (#108).

### Changed

- **Breaking:** rubrics are interchangeable peers. `timbro check` runs all of them by default, and `--rubric a,b` narrows it (#98).
- **Breaking:** markdown-axis JSON rows use `reference_mean` instead of `corpus_mean`, matching every other axis. `timbro.MarkdownAxis` is replaced by `timbro.AxisReport` (#108).
- **Breaking:** profiles resolve as `TIMBRO_PROFILE_ROOT` → `$TIMBRO_HOME/profiles`. The XDG (`$XDG_DATA_HOME/timbro/profiles`) fallback and the legacy-dir check are gone. Profiles that 0.8.0 kept under XDG (`~/.local/share/timbro/profiles` by default) no longer show up, and nothing warns about it. Move them with `mkdir -p ~/.timbro/profiles && mv ~/.local/share/timbro/profiles/* ~/.timbro/profiles/` (#116, #138).
- **Breaking for importers:** internal modules moved.
  - `timbro.config` → `timbro.priors` (#116).
  - The axis modules → `timbro.axes.*` (#117).
  - `timbro/model.py` → the `timbro.model` package, with `embedding` and `direction` lenses (#106).
  - `timbro.markdown` → `timbro.axes.markdown` (#106).

  The public API in `timbro/__init__.py` keeps working, and `python -m timbro.model` still runs the smoke test.

- The positioning is voice-first: the README and plugin metadata lead with voice alignment, and slop detection is the entry point (#97).
- The CLI dispatches through one handler per subcommand. Output is unchanged (#109).
- One cached spaCy pipeline loader (#114) and one cosine helper (#115). Scores are unchanged apart from float32-level flow drift, at most about 1e-7.

### Removed

- **Breaking:** the `timbro slop` subcommand. Use `timbro check --rubric slop` (#98).
- **Breaking:** the `timbro analyze` subcommand and its lexicons. It served the SKILL.md paper, which pins `uvx timbro@0.8.0 analyze`; use that version if you need it (#120).

### Fixed

- A first run piped into `head` no longer breaks the spaCy model install. The install's output goes to stderr, not stdout (#136).
- Parallel first runs no longer race the spaCy model install. It is serialized on a per-environment file lock, so the model installs once (#173).
- Offline runs with cached models no longer stall for minutes on hub retries. Both sentence-transformer models load from the local cache first; offline `check` dropped from 2m44s to 4.7s. Cached models no longer auto-update from the hub (#139).
- Expected user errors print one `timbro: error:` line and exit 1 instead of a traceback: a missing file, a non-UTF-8 file, a duplicate `add-file`, an unknown profile, `add-file` on a `.tex` file without `detex`, and any other filesystem error (permission denied, read-only disk, a name that is too long). A decode error names only the file that actually failed (#137, #147, #154).
- An empty or whitespace-only draft is a one-line error with exit 1 in `score`, `check` and `accept`, instead of a result built on `NaN` (#152).
- `--json` output never contains `NaN` or `Infinity`; non-finite numbers are written as `null` (#152).
- `check --profile` with no exemplars names the missing path, the same way `score` does. That error and the sample-voice warning say how to fill or create a managed profile (#161).
- `profiles add-file --dest-name` rejects anything but a plain file name, so it can no longer write outside the profile (#150).
- `add_text`/`add_file` reject an unknown bucket instead of silently filing it into `contrast/` (#165).
- `profiles sync --init` warns when it repoints an existing `origin` to a new URL, instead of doing it silently (#185).
- `profiles sync` works on a machine with no git identity once the remote has commits (#151).
- `profiles sync` on a root with no `origin` stops before committing anything and says to run `profiles sync --init <url>` (#154).
- A profile of near-duplicate exemplars no longer produces z-scores around 1e15 at confidence 1.0. Float-rounding spreads are floored like exact zeros (#160).
- One punctuation-only file in a profile's exemplars no longer makes the richness axis `NaN` for every draft, which had put a literal `NaN` in `score --json` (#177).
- Ingest cleanup no longer fuses a paragraph with a following punctuation block, which could drop the whole paragraph from `extract_prose_excerpt` (#179).
- `content_similarity` stays within [0, 1], and a hung `detex` times out after 60s instead of hanging (#180).
- `flow_report` raises a clear `ValueError` on under 2 paragraphs instead of numpy errors (#164).
- The `pkg_resources` deprecation warning no longer prints on every run (#140).
- PyYAML is a declared dependency. It was imported directly but only installed transitively (#141).
- `scripts/release.sh` refuses to release a `main` that is missing `origin/dev` commits, or a version with no changelog section (#171).
- Docs: the plugin downloads the spaCy model on first run rather than shipping it; PROFILE.md lists `.txt`; the README scopes `--json` to the commands that have it (#162).
- `feature-reference.md` now matches the code: 8 of the 11 markdown-structure rows had been wrong, the Richness and Politeness sections were missing, and several stale references are fixed. Stale comments and docstrings were swept after the layout work (#128).

## [0.8.0] — 2026-08-25

First release to actually ship the metric-axis and edit-loop work that had accumulated on `dev` — earlier tags were cut from a lagging `main`.

### Added

- `timbro profiles learn` — folds accepted edits back into a named profile, closing the score → edit → re-score loop into persistent voice tuning (#69).
- Per-profile run telemetry: `profiles.learn()` appends learn events to `<profile>/runs.jsonl`; opt out with `TIMBRO_NO_LOG=1` (#72).
- `paragraph-opener` dangling-reference check — flags a paragraph that opens on an unresolved referent (#74).
- Discourse-marker / paragraph-opening coherence check (#86).
- `timbro-setup` skill for guided first-run onboarding (#70).
- Portable `uvx timbro@<version>` install path and a "Using Timbro with other coding agents" guide, with CI asserting the shipped pin matches the release tag (#77).
- Feature-reference doc and ADRs 0001–0006 recording the architecture decisions (#71, #100).
- Demo GIF walking the score → edit → re-score loop in ~20s, plus the `assets/demo.tape` source and before/after sample drafts (#67).

### Changed

- SKILL.md reworked into a router and renamed to `timbro-review`; plugin/PyPI metadata now leads with the slop-detection pitch (#13).
- `release.sh` tags and pushes `vX.Y.Z` so the PyPI publish fires, and rewrites the `uvx` pins in the instruction files on each bump (#77, #82).

### Removed

- MCP server — the CLI is the sole interface. **Breaking** for anyone driving Timbro over MCP (#78).

### Fixed

- `eval/rubric_dashboard.py` imported from the removed `timbro.core` module.

## [0.7.1] — 2026-08-10

### Fixed

- Install the `en_core_web_sm` spaCy model with an explicit `--python` target on cold start, so first-run download lands in the right interpreter (#66).

## [0.7.0] — 2026-08-07

- Release/version-bump housekeeping over 0.6.0; no functional changes.

## [0.6.0] — 2026-08-04

First tagged release (#63), consolidating the M6 metric work.

### Added

- `slop` rubric and `timbro slop`, plus corpus-relative mode via `slop --profile` (#10).
- Three Metric axes on the declared-prior protocol: hedge/booster stance (#53), concreteness via Brysbaert norms (#56), and function-word / analytical-thinking (#55).
- Trust signals for outside evaluators: CI workflow + badge, `CONTRIBUTING.md`, and a citable slop-detection benchmark (#51).

### Changed

- Unified scalar metrics onto a shared extractor + declared-prior protocol (#43, #49).
- Centralized lexicons and declared priors into `config.py`; split report/formatting out of `model.py` (#57).
- Grounded `CONCRETENESS_REFERENCE` in Brysbaert norms (#58) and recomputed `FUNCTION_WORD_REFERENCE` over a Gutenberg corpus (#59).
- Moved the default profile root to `$XDG_DATA_HOME/timbro/profiles`, keeping legacy `~/.timbro/profiles` for backward compatibility (#47).

### Fixed

- PyPI packaging blocker: moved `en_core_web_sm` to a lazy runtime download instead of a build-time dependency (#52).
- Pinned `setuptools<81` so `lexical-diversity`'s `pkg_resources` import resolves in `uv tool` installs (#48).
- Replaced the circular slop benchmark with an HC3 held-out subsample (#60).
- Corrected the `CONCRETENESS_REFERENCE` spread unit mismatch (#58).

[Unreleased]: https://github.com/nicofirst1/timbro/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/nicofirst1/timbro/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/nicofirst1/timbro/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/nicofirst1/timbro/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/nicofirst1/timbro/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/nicofirst1/timbro/releases/tag/v0.6.0
