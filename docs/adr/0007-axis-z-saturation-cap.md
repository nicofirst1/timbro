# 7. Axis z saturation cap — a modelling constant, not a user setting

- **Status:** Accepted (decided 2026-10-01)
- **Relates to:** #178 (near-duplicate corpora), #160 (float-noise spread guard); decided during review of PR #193

## Context

Standalone-axis z-scores divide by a blended reference spread. #160 added a noise
floor for float-noise spreads on the embedding `distance_z` path, and `axis_report`
guards an exact-zero spread (`spread = ref_spread[i] or 1.0`); neither covers a
spread that is tiny but real. Markdown's prior strength is 0, so its spread is the
corpus std alone, and a near-duplicate corpus (two files one character apart) has a
real std of 1e-5 to 1e-9. A draft far from such a corpus then z-scored into the
1e3-1e5 range: the 2-file repro gives `struct_prose_ratio` z = 3040, the worst
release-fuzzing sweep case was -272,787.6, and 62 of 160 fuzzed corpora passed 1e3.

The number is correct arithmetic over a degenerate corpus, but as report output it
carries no advice: the direction string depends only on the sign of z once |z|
passes the near-target tolerance, so z = 300 and z = 30000 name the same revision.

## Decision

Cap every blend-style axis z at |z| = 10 and mark the row saturated. `axis_report`
computes the raw z, clamps it on its own line, and sets
`saturated = abs(raw_z) > 10`; the direction logic consumes the clamped z. The cap
lives in `priors.py` as the public, documented constant `AXIS_Z_SATURATION = 10.0`,
next to the declared priors. Every axis JSON row carries `saturated`; text output
prints `(saturated)` right after the z. The embedding path (distance/distance_z,
#160's fix) and the POS direction are not clamped.

The cap is a modelling constant, not a user setting: it must not vary per user, so
it does not live in settings.json.

## Alternatives considered

- **Minimum corpus size via the health gate** (suppress z and direction when the
  corpus is too small): misses the failure case — near-duplicate corpora have
  enough words; only their spread is degenerate.
- **Per-axis minimum spread** (fall back to a default spread when the corpus spread
  falls below a fraction of the axis's typical range): needs a hand-picked scale per
  axis, which is close to tuning the priors it tries not to touch.
- **A weak markdown prior** (nonzero strength, so `Reference.blend` never returns a
  pure corpus std on a tiny corpus): retunes priors; prior strengths are tuned
  constants this decision must not touch.
- **A user setting in settings.json**: rejected outright — a modelling constant
  must not vary per user; scores must stay comparable across machines.

## Consequences

- Magnitude above 10 is lost: a raw z of -44.19 and one of -1e6 both print
  `-10.00 (saturated)` with the same direction. This fires on legitimate inputs,
  not only on pathological corpora: a code-heavy draft scored against the packaged
  sample voice has `struct_prose_ratio` raw z = -44.19 and now prints
  `-10.00 (saturated)` where it printed `-44.19` before.
- `saturated` therefore means "at least 10 spreads off the reference", not "the
  corpus is pathological".
- The raw z is not recoverable from a saturated row (the blended spread is not part
  of the report); the row records only that the raw |z| exceeded the cap.

## Summary (ASD-STE100 Simplified Technical English)

A small corpus of near-same texts gave axis z-scores of 1000 to 100000. The math was
correct, but the spread was very small, so #160's fix for zero spreads did not
cover it. Also, the advice text does not use the size of the score: any score past
a small limit gives the same advice. So now every axis z-score stops at 10 in each
direction, and the report marks the row "saturated" past the cap. The cap is fixed
in the code, not a setting, so scores stay the same on every machine. Real
differences above 10 lose their size. The distance score and the part-of-speech
advice are not capped.
