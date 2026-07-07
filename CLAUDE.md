# Timbro — agent notes

Measures a draft's distance from a target voice and returns a named revision direction. Does not rewrite — the agent does. Local, CPU-only.

## Active plan — follow the GitHub milestones

All planned work lives in GitHub issues (`gh issue list`), grouped into milestones. **Before starting anything substantive, read the relevant issue and work within it** — don't invent parallel work; if something is missing, add an issue to the right milestone instead.


### Implementer guardrails

Issues are labeled by required capability: `agent:mechanical` = fully specified, follow the "Implementer spec" section literally; `agent:judgment` = has open taste/decision surface — ask the user before deviating or deciding, don't guess.

- One issue per branch/PR. Don't fold in drive-by refactors.
- The "Implementer spec" sections are decisions, not suggestions. If a number or approach in one looks wrong, comment on the issue and stop — do not silently substitute your own.
- Before declaring done, run `uv run pytest` and `uv run ruff check src/` and quote the output in the PR.
- Never touch `_PENALTY` / `_WEIGHTS` values, the verdict thresholds in `report.py`, or add a dependency, unless the issue explicitly says so.
- Respect issue dependencies. If your issue is blocked, say so instead of working around it.

## Commands

- `uv run timbro score draft.md` — score a file (runs on the packaged sample voice if no corpus env vars set)
- `uv run timbro-mcp` — MCP server (stdio)
- `uv run python -m timbro.model` — core smoke test
- `uv run ruff check src/` — lint
- Corpus: `TIMBRO_EXEMPLARS` (toward) / `TIMBRO_CONTRAST` (away). Named profiles live in `~/.timbro/profiles/<name>/{exemplars,contrast}/` by default (override with `TIMBRO_PROFILE_ROOT`).

## Releasing an update

The plugin updater compares by **version string**, so without a bump it will not pick up code changes (`already at latest version`).

Run `scripts/release.sh <new-version>` — it bumps both `.claude-plugin/plugin.json` and `pyproject.toml` (and fails loud if they end up mismatched), `uv lock`s, commits, confirms before pushing to `main`, then refreshes the marketplace clone, updates the plugin, and syncs the new cache venv.

## Gotchas

- `en_core_web_sm` is pinned as a direct-URL wheel dep (needs `tool.hatch.metadata.allow-direct-references`). No manual `spacy download`.
- Defaults resolve relative to the package dir (`src/timbro/sample/`), not CWD — so the plugin works inside its cache sandbox.
- `data/` is gitignored (private corpora); the shipped `src/timbro/sample/` is the only corpus that publishes.
