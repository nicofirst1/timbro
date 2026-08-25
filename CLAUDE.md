# Timbro

Measures a draft's distance from a target voice and returns a named revision direction. Does not rewrite — the agent does. Local, CPU-only.

`README.md` — user-facing docs. `docs/adr/` — why the architecture is what it is. `CONTEXT.md` — the domain glossary. Read on demand; nothing here is imported.

## Active plan — follow the GitHub milestones

All planned work lives in GitHub issues (`gh issue list`), grouped into milestones. **Before starting anything substantive, read the relevant issue and work within it** — don't invent parallel work; if something is missing, add an issue to the right milestone instead.

### Implementer guardrails

Issues are labeled by required capability: `agent:mechanical` = fully specified, follow the "Implementer spec" section literally; `agent:judgment` = has open taste/decision surface — ask the user before deviating or deciding, don't guess.

- One issue per branch/PR. Don't fold in drive-by refactors.
- The "Implementer spec" sections are decisions, not suggestions. If a number or approach in one looks wrong, comment on the issue and stop — do not silently substitute your own.
- Before declaring done, run `uv run pytest` and `uv run ruff check src/` and quote the output in the PR.
- Never retune the tuned constants — `_PENALTY` and the verdict cutoffs in `rubrics/report.py`, `_WEIGHTS` in `rubrics/*/rubric.py`, the curated lexicons/priors in `config.py` — and don't add a dependency, unless the issue explicitly says so.
- Respect issue dependencies. If your issue is blocked, say so instead of working around it.
- New `check` rules are **benchmark-gated**: a semantic-leaning check earns a first-class (Tier A) claim only by beating dumb baselines (position, length, centrality) on a real labelled benchmark; no benchmark caps it at optional/experimental (Tier B) or manual (Tier C). See `docs/adr/0005-benchmark-gated-check-development.md` and `eval/benchmarks/`.

## Commands

- `uv run timbro score draft.md` — score a file (runs on the packaged sample voice if no corpus env vars set)
- `uv run timbro-mcp` — MCP server (stdio)
- `uv run python -m timbro.model` — core smoke test
- `uv run ruff check src/` — lint
- Corpus env: `TIMBRO_EXEMPLARS` (toward) / `TIMBRO_CONTRAST` (away). Named profiles resolve in precedence order: `TIMBRO_PROFILE_ROOT` → legacy `~/.timbro/profiles/` (if present) → `$XDG_DATA_HOME/timbro/profiles/` (XDG defaults to `~/.local/share`), each holding `<name>/{exemplars,contrast}/`.

## Releasing an update

The plugin updater compares by **version string** — without a bump it won't pick up code changes (`already at latest version`). Run `scripts/release.sh <new-version>`; it bumps `plugin.json` + `pyproject.toml` in lockstep, commits, and confirms before pushing to `main`. Read the script for the rest (marketplace clone, cache venv).

## Gotchas

- `en_core_web_sm` is pinned as a direct-URL wheel dep (needs `tool.hatch.metadata.allow-direct-references`). No manual `spacy download`.
- Defaults resolve relative to the package dir (`src/timbro/sample/`), not CWD — so the plugin works inside its cache sandbox.
- `data/` is gitignored (private corpora); the shipped `src/timbro/sample/` is the only corpus that publishes.
- `TIMBRO_NO_LOG=1` disables the per-profile learn-event log (`<profile>/runs.jsonl`, appended by `profiles.learn()` via `profilelog.log_learn`). Unset by default (logging on); it's a user/test opt-out, read from the env, not set anywhere in code.

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues in `nicofirst1/timbro`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: a root `CONTEXT.md` (created lazily by `/domain-modeling`) plus `docs/adr/` record decisions. See `docs/agents/domain.md`.

### Project history

No CHANGELOG — history lives in git tags (`git tag`), the commit log, closed GitHub milestones, and `docs/adr/` (why the architecture is what it is). Check these before assuming how a subsystem got here.
