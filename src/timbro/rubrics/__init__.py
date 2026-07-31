from __future__ import annotations

from timbro.rubrics.registry import get_rubric


def check_text(text: str, rubric: str = "schimel", profile: str | None = None):
    """Run a rubric over `text`. `profile` is only meaningful for the `slop` rubric: it
    baselines the tells against that profile's exemplar corpus (corpus-relative mode),
    so a draft is judged against your own norm instead of against zero."""
    if profile is not None:
        if rubric != "slop":
            raise ValueError("--profile only affects the slop rubric")
        from timbro.model import read_corpus
        from timbro.profiles import get_profile
        from timbro.rubrics.slop import SlopRubric
        from timbro.tells import tell_baseline

        corpus = read_corpus(get_profile(profile).exemplars_dir)
        return SlopRubric(baseline=tell_baseline(corpus)).check(text)
    return get_rubric(rubric).check(text)


__all__ = ["check_text", "get_rubric"]
