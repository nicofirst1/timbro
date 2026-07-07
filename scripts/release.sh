#!/usr/bin/env bash
# Bump timbro's version everywhere it needs to match, push, then refresh the
# local plugin install. See CLAUDE.md "Releasing an update" for the manual
# version this automates.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <new-version>" >&2
  exit 1
fi

VERSION="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: working tree is dirty, commit or stash first" >&2
  exit 1
fi

branch="$(git branch --show-current)"
if [[ "$branch" != "main" ]]; then
  echo "error: on branch '$branch', release from main" >&2
  exit 1
fi

echo "==> bumping version to $VERSION"
uv version "$VERSION"
python3 - "$VERSION" <<'EOF'
import json, sys
path = ".claude-plugin/plugin.json"
data = json.load(open(path))
data["version"] = sys.argv[1]
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
EOF

pyproject_version="$(uv version --short)"
plugin_version="$(python3 -c 'import json; print(json.load(open(".claude-plugin/plugin.json"))["version"])')"
if [[ "$pyproject_version" != "$plugin_version" ]]; then
  echo "error: version mismatch after bump (pyproject=$pyproject_version plugin=$plugin_version)" >&2
  exit 1
fi

echo "==> uv lock"
uv lock

echo "==> commit + push"
git add pyproject.toml uv.lock .claude-plugin/plugin.json
git commit -m "chore: bump to $VERSION"
read -p "push to main? [y/N] " confirm
if [[ "$confirm" != "y" ]]; then
  echo "stopped before push; commit is local only"
  exit 0
fi
git push

echo "==> refreshing plugin install"
claude plugin marketplace update timbro
claude plugin update timbro@timbro
uv sync --directory "$HOME/.claude/plugins/cache/timbro/timbro/$VERSION"

echo "==> done. Restart Claude Code to load the new MCP server."
