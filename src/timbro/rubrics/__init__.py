from __future__ import annotations

from timbro.errors import UserValueError
from timbro.rubrics.features import DocumentView
from timbro.rubrics.registry import get_rubric
from timbro.text import strip_markup


def check_text(text: str, rubrics: list[str], profile: str | None = None):
    """Run one or more rubrics over `text`, returning a `RubricResult` per name, in the
    order given. One `DocumentView` is built per call and shared by every rubric that
    needs one, so the draft is parsed once (#192); `slop` works on raw text and takes
    no view. `profile` is only meaningful for the `slop` rubric: it baselines the
    tells against that profile's exemplar corpus (corpus-relative mode), so a draft is
    judged against your own norm instead of against zero."""
    if profile is not None and "slop" not in rubrics:
        raise UserValueError("--profile only affects the slop rubric")

    view: DocumentView | None = None  # built on first need; one parse per call (#192)
    results = []
    for rubric in rubrics:
        if rubric == "slop" and profile is not None:
            from timbro.axes.tells import tell_baseline
            from timbro.model import no_exemplars_error, read_corpus
            from timbro.profiles import get_profile
            from timbro.rubrics.slop import SlopRubric

            corpus_dir = get_profile(profile).exemplars_dir
            corpus = read_corpus(corpus_dir)
            if not corpus:  # name the problem, not the internal caller (#161)
                raise no_exemplars_error(corpus_dir)
            results.append(SlopRubric(baseline=tell_baseline(corpus)).check(text))
        elif rubric == "slop":
            results.append(get_rubric(rubric).check(text))
        else:
            rubric_impl = get_rubric(rubric)
            if view is None:
                view = DocumentView(strip_markup(text))
            results.append(rubric_impl.check(text, view))
    return results


__all__ = ["check_text", "get_rubric"]
