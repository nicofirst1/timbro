from __future__ import annotations

from timbro.errors import UserValueError
from timbro.rubrics.document import DocumentRubric
from timbro.rubrics.features import DocumentView
from timbro.rubrics.registry import get_rubric
from timbro.text import strip_markup


def check_text(text: str, rubrics: list[str], profile: str | None = None):
    """Run one or more rubrics over `text`, returning a `RubricResult` per name, in the
    order given. `profile` is only meaningful for the `slop` rubric: it baselines the
    tells against that profile's exemplar corpus (corpus-relative mode), so a draft is
    judged against your own norm instead of against zero."""
    if profile is not None and "slop" not in rubrics:
        raise UserValueError("--profile only affects the slop rubric")

    view: DocumentView | None = None  # built on first need; one parse per call (#192)
    results = []
    for rubric in rubrics:
        if rubric == "slop" and profile is not None:
            from timbro.axes.tells import tell_baseline
            from timbro.profiles import get_profile
            from timbro.rubrics.slop import SlopRubric

            # Profile-aware corpus resolution (#166 R1): an unknown profile
            # raises the spec's unknown-profile error; a missing or empty
            # exemplars dir (git drops empty dirs on sync) raises #161's
            # no-exemplars message from Profile.exemplar_corpus.
            corpus = get_profile(profile).exemplar_corpus()
            results.append(SlopRubric(baseline=tell_baseline(corpus)).check(text))
        else:
            rubric_impl = get_rubric(rubric)
            if isinstance(rubric_impl, DocumentRubric):
                if view is None:
                    view = DocumentView(strip_markup(text))
                results.append(rubric_impl.check(text, view))
            else:
                results.append(rubric_impl.check(text))
    return results


__all__ = ["check_text", "get_rubric"]
