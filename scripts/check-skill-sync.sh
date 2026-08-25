#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): warn when the CLI surface changed but
# skills/timbro/SKILL.md and .claude-plugin/plugin.json -- which document
# that surface -- weren't also touched in this working tree.
set -euo pipefail

f=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')

case "$f" in
  *src/timbro/cli.py | *src/timbro/rubrics/*) ;;
  *) exit 0 ;;
esac

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
changed=$(git -C "$root" status --porcelain -- skills/timbro/SKILL.md .claude-plugin/plugin.json 2>/dev/null)

if [ -z "$changed" ]; then
  jq -n --arg f "$f" '{
    systemMessage: ("CLI surface changed (" + $f + ") but skills/timbro/SKILL.md and .claude-plugin/plugin.json are untouched in this working tree -- check they still describe it."),
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: ("skills/timbro/SKILL.md and .claude-plugin/plugin.json document the CLI surface and may now be stale after editing " + $f + ".")
    }
  }'
fi
