# Contributing

## Setup

```
uv sync
```

That's it — `uv` installs everything, including the pinned spaCy model wheel (no manual `spacy download`).

## Before you start

Read `CLAUDE.md`'s "Active plan" section and the [open issues](https://github.com/nicofirst1/timbro/issues) first. All planned work lives in GitHub issues grouped into milestones — work within an existing issue rather than inventing parallel work. One issue per branch/PR; don't fold in drive-by refactors.

## Test and lint

```
uv run pytest
uv run ruff check src/
```

Both must pass before you open a PR — CI runs the same two commands on push/PR (ubuntu + macos).

## Releasing

See the "Releasing an update" section in `CLAUDE.md` (`scripts/release.sh <new-version>`). Only maintainers cut releases.
