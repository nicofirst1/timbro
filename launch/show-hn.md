## Title options

1. Show HN: Timbro - deterministic AI-slop and voice-drift detection (no LLM judge)
2. Show HN: Timbro - catch AI writing tells without asking an LLM to grade an LLM
3. Show HN: A regex+POS tool that scores how far a draft drifted from your writing voice

Option 1 is the one named in issue #14 and matches the README's positioning (issue #10). Recommend it unless the human wants to test another.

## First comment

Hi HN. I write with an agent now, and the drafts kept sounding like each other instead of like me. Timbro is a small tool I built to make that measurable instead of just annoying.

Two parts:

`timbro slop draft.md` runs about 19 named detectors for AI writing tells (em-dashes, "it's not X, it's Y", delve/tapestry-style diction, staccato sentence runs, dropped-subject openers, colon-then-list constructions) and returns a verdict plus the exact spans that tripped it. Mostly regex; a few (dropped-subject, staccato runs, a "contentless opening fragment" check) run through spaCy's POS tagger because they need sentence structure, not just keywords.

`timbro score draft.md` does the other half: feed it a folder of posts you've accepted as your own voice, and it scores a new draft for how far it sits from that voice and which way to move it, in named features (more conjunctions, fewer abstract nouns, that kind of thing), without touching what the draft says. A pre-trained sentence embedding model (StyleDistance) gives the distance; POS unigram rates z-scored against your corpus give the direction; a separate general-purpose embedding checks that an edit changed how something reads without changing what it says.

Why not just ask an LLM "does this read AI-generated?" Because that's an LLM grading an LLM: nondeterministic, costs a call every time, and can't point at which words did it. Everything in Timbro is deterministic, local, and CPU-only. No API calls at inference.

What it can't do: it doesn't rewrite anything (your agent or you does that; Timbro judges the result). It's recall-first, so some rules fire on prose that's fine, on purpose: a filterable false positive beats a silent miss. There's a small dashboard (`eval/rubric_dashboard.py`) that reports findings-per-1000-words per rule on known-good prose specifically to catch and demote the noisy ones. And it's a voice tool, not a truth tool: clean-scoring prose can still be wrong or boring.

Repo, install instructions, and the numbers on my own blog voice: https://github.com/nicofirst1/timbro

NOTE for human review: issue #14 asks this comment to include "the uvx one-liner (#9)". As of this draft, #9 (PyPI publish / `uvx timbro ...` cold start) is still open, so there is no working uvx command to quote yet. Do not launch until #9 ships and the one-liner is verified to actually run cold, then add a line like `uvx timbro check draft.md` here. Same gap applies to the GIF (#11): the checklist below sequences both before this comment goes out.
