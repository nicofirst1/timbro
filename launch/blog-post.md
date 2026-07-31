> **TL;DR;** LLM drafts read fluent and sound like nobody, including you. I built a tool that measures the distance instead of arguing about it, and hands back the named edits to close it.
>
> ```
> This post was drafted with help from an AI agent, reviewed and edited by a human.
> ```

I write with an agent now. Most of a first draft comes from Claude, and I edit it down. That's a fine way to work until you notice the drafts all start sounding like each other, and none of them sound like you.

The tells are familiar if you've read enough AI output: the em-dash doing the work three different punctuation marks used to split between them, "it's not just a tool, it's a philosophy", the reflexive reach for _delve_ and _tapestry_ and _robust_, a tidy little "in conclusion" bow at the end whether the piece earned one or not. You can feel it. What you can't do easily is put it in CI, or hand an agent a rule it can check against itself before it hands the draft back to you.

## Deterministic instead of another LLM judge

The obvious fix is to ask an LLM "does this sound AI-written?". I don't like that answer, for three reasons that all trace back to the same problem: you're using an LLM to grade an LLM. It's nondeterministic (ask twice, get two verdicts). It costs an API call every time, which rules out a pre-commit hook or a tight edit loop. And when it says "yes, this reads AI", it can't show you which four words did it, so you're left guessing at the fix.

So I built [Timbro](https://github.com/nicofirst1/timbro) to do the opposite: white-box, deterministic, local. `timbro slop draft.md` runs about nineteen named detectors, mostly regex and part-of-speech tags via spaCy, no model call, no network, and returns a verdict plus the exact spans that tripped it:

```
$ timbro slop draft.md
slop: WARN (0.69)

diction      0.70
construction 0.70
rhythm       0.80
formatting   0.55

Top findings
- formatting: 2× em/en dashes
- diction: 12× AI-tell diction (delve, tapestry, seamless, robust, …)
- construction: signposting phrases, wrap-up phrases
```

Delete what it flagged, run it again, get `slop: PASS`. Same meaning, no tells. That loop, score then edit then re-score, is the whole workflow, and it's fast enough to run on every turn of an agent's editing pass, not just once at the end.

Some of the detectors are close to plain regex (the em-dash count, the curly-quote count, a blocklist of over-used diction). A few need more than a keyword match. "Dropped-subject" openers ("Consider the alternative", "Ran the tests twice") and staccato runs of short declaratives both need to know the sentence's actual grammatical structure, not just its words, so those run through spaCy's part-of-speech tagger and sentence boundaries instead of a pattern. I tried something fancier first: scoring perplexity under a small local language model, on the theory that AI filler would look "more predictable" to a language model than real prose. It didn't hold up. Cuttable filler and confident real prose look about equally predictable to a small LM. Part-of-speech and dependency structure caught what perplexity couldn't, so that's what shipped, and I dropped the perplexity path rather than keep two-thirds of a feature.

## A positive target, not just a blocklist

Any regex list can tell you what to strip, but a blocklist doesn't put a voice back. After a few rounds of deletion, a draft can be clean of every tell and still not sound like the person it's supposed to be under.

That's the second half of the tool, and the one I actually reach for more. Feed Timbro a folder of posts you've accepted as your own voice, and it scores a new draft for how far it sits from that voice, plus which way to move it, in named features, without touching what the draft says. Under the hood: a pre-trained sentence-embedding model (StyleDistance) scores the "how far" as a scalar via k-nearest-neighbors against your corpus; a set of part-of-speech unigram rates, z-scored against the same corpus and weighted by how much each one predicts your voice, gives the "which way" as a list of named habits (more conjunctions, fewer abstract nouns, whatever your corpus says); a separate general-purpose embedding model checks that an edit changed _how_ something reads without changing _what_ it says, so the tool can't accidentally reward you for cutting content along with the tells.

I run this against my own blog, and the project's own README makes the number public: it was drafted by Claude, and against my actual blog voice it lands at 47 on a 0-to-far scale where my own essays sit in a 9-35 band and straight marketing copy sits at 86. Recognizably not my essay voice (it reads as code-heavy docs, which is what it is), but nowhere near sales-speak either. The direction Timbro handed back for closing that gap: more conjunctions, fewer abstract nouns, less code-block-style punctuation. I didn't take the README all the way to my own voice band on purpose, since it's documentation and not an essay, but the number and the direction are both real and reproducible from the repo against the five posts it's scored against.

There's a companion rubric, `timbro check`, that asks a different question: not "does this sound like me" but "is this good prose", independent of any voice corpus at all. It's about thirty checks distilled from Joshua Schimel's _Writing Science_: buried subject-verb cores, passive voice, comma splices, nominalizations, word-echo repetition, unearned claim words. Also deterministic, also no LLM judge, same spaCy substrate.

## What it can't do

It's worth being honest about the shape of the false positives, because "recall-first" is a real tradeoff, not a marketing line. Every rubric in Timbro is tuned to prefer flagging too much over missing something: a rule that fires on decent prose stays in at low severity rather than getting deleted, on the theory that a model or a human filtering findings is cheaper than a tool that goes silent on real slop. I built a small dashboard (`eval/rubric_dashboard.py`) that runs every rule against known-good prose and prints findings-per-1000-words per rule, so a rule that's noisy on good writing gets demoted instead of trusted by default. That dashboard exists because early versions of some rules fired constantly on prose I'd already signed off on, which is exactly the failure mode a recall-first tool has to watch for and admit to.

It also doesn't rewrite anything. That's deliberate, not a missing feature. Timbro measures; your agent, or you, does the rewriting, and then Timbro judges the result on two axes at once: closer to voice, and the same meaning. That split, scoring in one hand and editing in the other, is what keeps the scoring honest.

And it's a voice tool, not a truth tool. Clean prose by Timbro's numbers can still be wrong, boring, or badly argued. It tells you whether a draft sounds like you. It has no opinion on whether what you said was worth saying.

## Try it

```
git clone git@github.com:nicofirst1/timbro.git && cd timbro
uv sync
uv run timbro slop draft.md
uv run timbro score draft.md   # runs on a packaged sample voice out of the box
```

It's a [Claude Code plugin](https://github.com/nicofirst1/timbro) too, or an MCP server for any agent that speaks MCP. More at the repo.
