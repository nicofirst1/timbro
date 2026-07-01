# Timbro — agent notes

Measures a draft's distance from a target voice and returns a named revision direction. Does not rewrite — the agent does. Local, CPU-only.

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
