---
name: timbro
description: Align a draft to a target writing voice (your own, or a company persona) and keep it consistent. Use when the user asks to "make this sound like me/us", "match our blog voice", "check this is on-brand / in my voice", "keep my writing style consistent", or is drafting copy that must stay stylistically aligned with an existing body of posts. Timbro measures how far the draft sits from the voice and returns named, content-preserving edits; you do the rewriting.
---

# Timbro — voice alignment

LLM prose drifts: today's draft sounds different from last week's, and neither sounds like the human (or company) it's published under. Timbro fixes the *consistency* problem. It scores a draft against a corpus of writing you've accepted as "your voice" and tells you, in named features, which way to revise — without changing what the text says.

You (the agent) are the rewriter. Timbro is the measurer. Run the loop: **score → edit toward the direction → re-score → repeat until the distance stops dropping.**

## Prerequisites (one-time)

Timbro is pointed at a corpus via two env vars:

- `TIMBRO_EXEMPLARS` → a folder of posts that *define* the voice (move TOWARD). 6+ pieces is enough.
- `TIMBRO_CONTRAST` → the "not-this-voice" set (move AWAY FROM). Optional but sharpens the direction.

If unset, Timbro falls back to a small packaged sample voice so it runs, but that is **not** the user's voice — never silently score a real draft against the sample.

## Pick a direction first — always ask

Before scoring, **discover the available example/contrast pairs and let the user choose**:

1. List the profiles in the Timbro repo: `ls data/profiles/*/` (each `<name>/` holds an `exemplars/` to move toward and a `contrast/` to move away from). Also note `data/exemplars` + `data/contrast` if present.
2. Tell the user what's available and **ask which direction to align**: which set to move *toward* (exemplars) and which to move *away from* (contrast). Do not assume — the same draft pulls differently toward "academic" vs "clear" vs "casual".
3. If nothing relevant exists, tell the user to drop good examples in `data/profiles/<name>/exemplars/` and bad ones in `.../contrast/` — don't guess a voice.

Then set the env vars to the chosen pair for the scoring commands below:

```bash
P=data/profiles/<name>
export TIMBRO_EXEMPLARS=$P/exemplars TIMBRO_CONTRAST=$P/contrast
```

## Workflow

1. **Score the draft.** Write the draft to a file (or pipe via stdin) and run:

   ```bash
   TIMBRO_EXEMPLARS=$P/exemplars TIMBRO_CONTRAST=$P/contrast \
     uv run --directory /path/to/timbro timbro score draft.md
   ```

   (Pass the chosen pair inline — env doesn't carry across separate shell calls.)

   You get a `distance` (smaller = more on-voice) and a `direction` — a ranked list of named, confidence-weighted moves like `fewer verbs`, `more conjunctions`, `more nouns`. Higher `confidence` = a more reliable signal; act on those first.

2. **Turn each hint into a concrete edit, preserving meaning.** Hints are POS habits or named AI-tells — translate them:
   - *fewer verbs / more nouns* → nominalize where natural ("we decided to" → "our decision to"); tighten verb-heavy sentences.
   - *more conjunctions* → join short choppy clauses into longer compound sentences.
   - *fewer adjectives / adverbs* → cut intensifiers and hedges.
   - *more / fewer pronouns* → shift between personal ("I/we") and impersonal framing.
   - *fewer <a named tell>* (em/en dashes, "it's not X, it's Y", AI-diction like delve/tapestry, signposting, emoji, …) → just delete the marker. Tells are lexical AI-fingerprints, not style dials; removing them only helps.

   Never change the claims, facts, or argument — only *how* it reads. If the prose is
   published under a persona with its own style rules (a "voice" skill, a brand guide),
   apply those rules as you rewrite — Timbro gives the distance, the rulebook gives the words.

3. **Re-score.** Run `timbro score` on your revision. Confirm `distance` dropped. If it rose, you over-rotated — back off the lowest-confidence edits.

4. **(Optional) verify content was preserved.** If the Timbro MCP server is registered, call `accept_rewrite(original, revised)` — it returns `accepted: true` only when the rewrite moved closer to the voice **and** kept the meaning (semantic similarity > 0.85). Use it as the stop condition.

## When to use this vs. just rewriting

Use Timbro whenever consistency with an *established* body of writing matters: a personal blog, a company's content, a newsletter persona, anything where "does this sound like us?" is a real question. For one-off prose with no reference voice, plain rewriting is fine — Timbro needs a corpus to measure against.
