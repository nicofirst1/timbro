from __future__ import annotations

from timbro.rubrics.registry import get_rubric


def check_text(text: str, rubrics: list[str], profile: str | None = None):
    """Run one or more rubrics over `text`, returning a `RubricResult` per name, in the
    order given. `profile` is only meaningful for the `slop` rubric: it baselines the
    tells against that profile's exemplar corpus (corpus-relative mode), so a draft is
    judged against your own norm instead of against zero."""
    if profile is not None and "slop" not in rubrics:
        raise ValueError("--profile only affects the slop rubric")

    results = []
    for rubric in rubrics:
        if rubric == "slop" and profile is not None:
            from timbro.model import read_corpus
            from timbro.profiles import get_profile
            from timbro.rubrics.slop import SlopRubric
            from timbro.tells import tell_baseline

            corpus = read_corpus(get_profile(profile).exemplars_dir)
            results.append(SlopRubric(baseline=tell_baseline(corpus)).check(text))
        else:
            results.append(get_rubric(rubric).check(text))
    return results


__all__ = ["check_text", "get_rubric"]
