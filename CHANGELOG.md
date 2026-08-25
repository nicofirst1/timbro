# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `timbro profiles learn` — folds accepted edits back into a named profile, closing the score → edit → re-score loop into persistent voice tuning (#69).
- Demo GIF walking the score → edit → re-score loop in ~20s, plus the `assets/demo.tape` source and before/after sample drafts (#67).

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

[Unreleased]: https://github.com/nicofirst1/timbro/compare/v0.7.1...HEAD
[0.7.1]: https://github.com/nicofirst1/timbro/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/nicofirst1/timbro/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/nicofirst1/timbro/releases/tag/v0.6.0
