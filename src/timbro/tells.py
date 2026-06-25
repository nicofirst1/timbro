"""AI-tell layer: named lexical/phrasal markers of LLM prose, as white-box features.

The POS direction in `core` measures *grammatical texture* — it is blind to
*lexical* tells. A draft can sit dead-centre in your POS cloud and still say
"delve into the rich tapestry", carry an em-dash, or run "it's not X, it's Y".
Those are exactly the markers two public corpora converge on: Wikipedia's "Signs
of AI writing" (via blader/humanizer, MIT) and a 3.2M-post Reddit frequency study
(JCarterJohnson/vibecoded-design-tells, MIT). Em-dash overuse and "not X, but Y"
are the top two tells in *both*.

Each detector returns a count; `tell_rates` length-normalises to a rate, so a tell
becomes a named feature that flows through the same z-score + confidence machinery
as POS rates. A clean exemplar corpus has ~0 of these, so against AI-slop they
separate sharply; `TELL_PRIOR` (from the Reddit frequency ranks) gives each tell a
confidence floor so it surfaces even with no contrast. Pure regex, no model load.
"""

from __future__ import annotations

import re

# Plain-English labels so a flagged tell reads as advice, not a feature id.
TELL_LABEL = {
    "dash": "em/en dashes",
    "diction": "AI-tell diction (delve, tapestry, leverage, …)",
    "not_x_y": "\"it's not X, it's Y\" / \"not only … but also\" constructions",
    "signpost": "signposting phrases (dive in, when it comes to, …)",
    "conclusion": "wrap-up phrases (in conclusion, the future looks bright)",
    "sycophancy": "sycophantic / collaborative filler (great question, hope this helps)",
    "filler": "filler phrases (in order to, due to the fact that)",
    "aphorism": "authority-trope aphorisms (at its core, the real question is)",
    "rule_of_three": "rule-of-three triads",
    "emoji": "emoji",
    "curly_quote": "curly quotation marks",
    "bold_leadin": "bold lead-in bullets (**Word:** …)",
    "hr_divider": "--- section dividers",
    "rhetorical_opener": "conversational openers (Honestly, Look, Here's the thing)",
}

# Confidence floor in [0,1], seeded from the Reddit study's citation frequency:
# em-dash is "the single most reliable tell"; "not X but Y" is the named "AI accent".
TELL_PRIOR = {
    "dash": 0.70, "not_x_y": 0.55, "diction": 0.50, "sycophancy": 0.40,
    "signpost": 0.35, "hr_divider": 0.35, "conclusion": 0.30, "emoji": 0.30,
    "rhetorical_opener": 0.30, "bold_leadin": 0.25, "rule_of_three": 0.25,
    "filler": 0.25, "aphorism": 0.25, "curly_quote": 0.20,
}

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_WORD = re.compile(r"\b\w+\b")

# High-signal AI diction (word-boundary, case-insensitive). Curated from the two
# corpora's blocklists, kept to terms that are genuinely over-represented in LLM prose.
_DICTION = re.compile(
    r"\b(?:delve|tapestry|leverage|landscape|realm|testament|boasts?|nestled|"
    r"vibrant|showcas(?:e|es|ing|ed)|underscor(?:e|es|ing|ed)|pivotal|intricate|"
    r"robust|comprehensive|nuanced|elevat(?:e|es|ing|ed)|unleash(?:es|ing|ed)?|"
    r"unlock(?:s|ing|ed)?|navigat(?:e|es|ing|ed)|foster(?:s|ing|ed)?|myriad|"
    r"seamless(?:ly)?|game[- ]?changer|ever[- ]evolving|ever[- ]changing|"
    r"revolutioniz(?:e|es|ing|ed)|transformative|utiliz(?:e|es|ing|ed)|embark|"
    r"harness(?:es|ing|ed)?|paramount|plethora|bustling)\b",
    re.IGNORECASE,
)

# Each pattern is *counted* (len of findall) and normalised per word-token.
_PATTERNS: dict[str, re.Pattern] = {
    "not_x_y": re.compile(
        r"\bit'?s not (?:just |only |merely |simply )?[^,.;:]{1,50}[,;] (?:it'?s|but)\b"
        r"|\bnot only\b[^.?!]{1,60}\bbut also\b"
        r"|\bnot just\b[^.?!]{1,50}\bbut\b",
        re.IGNORECASE,
    ),
    "signpost": re.compile(
        r"\b(?:let'?s dive in|deep dive|dive into|when it comes to|"
        r"in today'?s (?:fast[- ]paced |digital )?world|it'?s (?:important|worth) (?:to note|noting)|"
        r"needless to say|here'?s what you need to know|in the realm of)\b",
        re.IGNORECASE,
    ),
    "conclusion": re.compile(
        r"\b(?:in conclusion|in summary|to sum up|to wrap up|"
        r"the future looks bright|exciting times (?:lie ahead|ahead))\b",
        re.IGNORECASE,
    ),
    "sycophancy": re.compile(
        r"\b(?:great question|i hope this helps|hope this helps|let me know if|"
        r"happy to help|glad to help|would you like me to|should i continue)\b"
        r"|\b(?:absolutely|certainly)!",
        re.IGNORECASE,
    ),
    "filler": re.compile(
        r"\b(?:in order to|due to the fact that|at this point in time|"
        r"for all intents and purposes|it goes without saying)\b",
        re.IGNORECASE,
    ),
    "aphorism": re.compile(
        r"\b(?:at its core|the real question is|what really matters|"
        r"at the end of the day|the key takeaway)\b",
        re.IGNORECASE,
    ),
    # Triadic list: "A, B, and C" — a tell only in overuse, so it earns a low prior.
    "rule_of_three": re.compile(r"\b\w+,\s+\w+,\s+and\s+\w+\b"),
    # Conversational opener at the start of a line/sentence.
    "rhetorical_opener": re.compile(
        r"(?:^|[.?!]\s+)(?:Honestly|Look|Here'?s the thing|Let'?s be honest|"
        r"Let'?s face it|Picture this|Imagine this)\b",
    ),
    # Bolded lead-in bullet: "- **Word:** …" or "**Word:**" at line start.
    "bold_leadin": re.compile(r"^\s*(?:[-*+]\s+)?\*\*[^*\n]{1,40}\*\*\s*[:—-]", re.MULTILINE),
}

_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
_CURLY = re.compile("[“”‘’]")
_HR = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE)

TELL_NAMES = tuple(TELL_LABEL)  # stable order for the feature vector


def _counts(text: str) -> dict[str, int]:
    body = _FRONTMATTER.sub("", text)  # drop YAML so its --- isn't read as an HR
    c = {
        "dash": body.count("—") + body.count("–"),
        "diction": len(_DICTION.findall(body)),
        "emoji": len(_EMOJI.findall(body)),
        "curly_quote": len(_CURLY.findall(body)),
        "hr_divider": len(_HR.findall(body)),
    }
    for name, pat in _PATTERNS.items():
        c[name] = len(pat.findall(body))
    return c


def tell_rates(text: str) -> dict[str, float]:
    """Named AI-tell features for one document: occurrences per 1000 word-tokens.

    Length-normalised like the POS rates, so the doc-length confound can't arise.
    Per-1000 (not per-token) keeps the numbers order-1 so a lone tell isn't a
    near-zero that the z-score buries under the POS features. Keys are `tell_<name>`
    to namespace them against `pos_<tag>`.
    """
    n = len(_WORD.findall(_FRONTMATTER.sub("", text))) or 1
    counts = _counts(text)
    return {f"tell_{name}": 1000 * counts[name] / n for name in TELL_NAMES}


if __name__ == "__main__":
    # Smoke test: AI-slop must light up tells a plain human sentence does not.
    slop = ("Honestly? Let's dive in. It's not just a tool, it's a vibrant tapestry. "
            "We delve into the landscape — a testament to seamless, robust design. \U0001F680\n\n"
            "- **Key:** in conclusion, the future looks bright. Great question!")
    clean = "I fixed the parser today. It dropped the last row, so I added a guard and a test."
    rs, rc = tell_rates(slop), tell_rates(clean)
    lit = [k for k, v in rs.items() if v > 0]
    assert rs["tell_dash"] > 0 and rs["tell_not_x_y"] > 0 and rs["tell_diction"] > 0
    assert sum(rc.values()) == 0, f"clean text tripped tells: {rc}"
    print(f"ok: slop lit {len(lit)} tells {sorted(k[5:] for k in lit)}; clean lit 0")
