# Timbro — agent notes

Measures a draft's distance from a target voice and returns a named revision direction. Does not rewrite — the agent does. Local, CPU-only.

## Active plan — follow the GitHub milestones

All planned work lives in GitHub issues #1–#15 (`gh issue list`), grouped into four milestones. **Before starting anything substantive, read the relevant issue and work within it** — don't invent parallel work; if something is missing, add an issue to the right milestone instead.

- **M1 — Recall-first findings** (#1 per-occurrence findings + locations, #2 looser thresholds, #3 severity-ranked output). Do this first; pure refactor, no new deps.
- **M2 — Density rubric** (#4 Leitwort leading-word detector → #5 `density` rubric with lexical density + `wordfreq` jargon flagging → #6 annotate repetition findings; #7 zlib check is deferred, don't start it). #4 blocks #5 and #6.
- **M3 — Calibration** (#8 false-positive dashboard in `eval/`).
- **M4 — Adoption** (#9 PyPI + `uvx` cold start, #10 AI-slop repositioning, #11 demo GIF, #12 GitHub Action, #13 registry/awesome-list submissions, #14 launch post + Show HN, #15 CI badge/CONTRIBUTING/benchmark). Ordering matters: #9 unblocks #11/#12; #14 (launch) only after #9, #10, #11 are done — don't burn the launch on a repo without a 10-second trial path.

Design policy for all rubric code (the issues repeat it): **prefer false positives over false negatives** — the consumer is an LLM that judges findings itself. Never suppress a finding to look precise; annotate it (see #6) or demote it to `low` severity when the #8 dashboard shows it's noisy on known-good prose. Everything stays deterministic: spaCy/regex/counting, no LLM-as-judge, no network at check time. Threshold or rule PRs quote before/after findings-per-1000-words from the dashboard.

### Implementer guardrails

Issues are labeled by required capability: `agent:mechanical` = fully specified, follow the "Implementer spec" section literally; `agent:judgment` = has open taste/decision surface — ask the user before deviating or deciding, don't guess.

- One issue per branch/PR. Don't fold in drive-by refactors.
- The "Implementer spec" sections are decisions, not suggestions. If a number or approach in one looks wrong, comment on the issue and stop — do not silently substitute your own.
- Before declaring done, run `uv run pytest` and `uv run ruff check src/` and quote the output in the PR.
- Never touch `_PENALTY` / `_WEIGHTS` values, the verdict thresholds in `report.py`, or add a dependency, unless the issue explicitly says so.
- Respect issue dependencies (#4 → #5/#6; #9 → #11/#12; #8 → #15's benchmark). If your issue is blocked, say so instead of working around it.

## Commands

- `uv run timbro score draft.md` — score a file (runs on the packaged sample voice if no corpus env vars set)
- `uv run timbro-mcp` — MCP server (stdio)
- `uv run python -m timbro.core` — core smoke test
- `uv run ruff check src/` — lint
- Corpus: `TIMBRO_EXEMPLARS` (toward) / `TIMBRO_CONTRAST` (away). Named profiles live in `~/.timbro/profiles/<name>/{exemplars,contrast}/` by default (override with `TIMBRO_PROFILE_ROOT`).

## Releasing an update (do this EVERY time the package changes)

The plugin updater compares by **version string**, so without a bump it will not pick up code changes (`already at latest version`).

1. Bump the version in **both** `.claude-plugin/plugin.json` and `pyproject.toml` (keep them identical).
2. `uv lock` if deps changed, then commit + push to `main`.
3. `claude plugin marketplace update timbro` — refresh the marketplace clone.
4. `claude plugin update timbro@timbro` — pulls the new version into the cache.
5. `uv sync --directory ~/.claude/plugins/cache/timbro/timbro/<version>` — prime the new install's venv (deps + the en_core_web_sm model).
6. Restart Claude Code to load the new MCP server.

## Gotchas

- `en_core_web_sm` is pinned as a direct-URL wheel dep (needs `tool.hatch.metadata.allow-direct-references`). No manual `spacy download`.
- Defaults resolve relative to the package dir (`src/timbro/sample/`), not CWD — so the plugin works inside its cache sandbox.
- `data/` is gitignored (private corpora); the shipped `src/timbro/sample/` is the only corpus that publishes.
