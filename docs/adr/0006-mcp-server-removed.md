# 6. MCP server removed — the CLI is the sole interface

- **Status:** Accepted (decided 2026-08-25)
- **Relates to:** #76 (discussion), #73 (closed as moot), #13 (Get listed — MCP-registry legs dropped); amends the "MCP accept-rewrite loop" consequence in ADR-0004

## Context

`mcp_server.py` was an 81-line pass-through: its three tools (`score_voice`, `accept_rewrite`, `check_voice`) called `voice_report` / `evaluate_rewrite` / `check_text` — the same functions the CLI already called, and `SKILL.md` already drove the whole workflow through the CLI, mentioning MCP once as optional. So MCP added no capability; its only value was reaching MCP hosts that aren't Claude Code.

But reaching other coding agents doesn't require MCP. Every serious coding agent (Codex, Cursor, Windsurf, aider, Zed) already has a shell tool; the precedent (mattpocock/skills' `skills.sh`) reaches all of them by copying a plain instructions file that shells out to a CLI — no protocol, no running server. The remaining case MCP uniquely serves — a chat-only client with no shell tool (Claude Desktop as a chat app) — isn't a target Timbro has built toward; everything about it (SKILL.md-first, local CLI, no hosted service) is aimed at coding-agent users.

`evaluate_rewrite` (the `accept_rewrite` tool) was the one capability with no CLI equivalent — added as `timbro accept` in the same change, so removing MCP costs nothing.

## Decision

Remove `src/timbro/mcp_server.py`, the `mcp` dependency, and the `timbro-mcp` entry point. The CLI (`timbro score` / `check` / `slop` / `accept`, all with `--json`) is the sole programmatic interface. #73 (an env var that only existed to polish the MCP env-block) closes as moot; #13's MCP-registry submissions are dropped from scope.

## Consequences

- One interface to keep in sync instead of two; SKILL.md's CLI-first design was already the real interface.
- No capability lost: `timbro accept` closes the gap `accept_rewrite` covered.
- Reaching non-Claude-Code coding agents is still open — tracked separately as a portable, CLI-driving instructions file (skills.sh-style), not as an MCP investment.
- If a genuinely chat-only, no-shell audience shows real demand later, MCP (or a hosted API) is the option to revisit — this ADR doesn't rule it out, it just stops investing pre-emptively.

## Summary (ASD-STE100 Simplified Technical English)

Timbro had an MCP server. The MCP server had three tools. The tools called the same code the CLI called. The MCP server added no new function. The MCP server let other chat tools use Timbro. But most coding agents can run shell commands. They do not need MCP. They can call the CLI directly. Only a chat tool with no shell command can not do this. Timbro does not target that kind of tool today. So the MCP server is removed. The CLI is now the only interface. A new CLI command, `timbro accept`, replaces the one MCP tool that had no CLI match. Two related requests are closed because they only existed to support MCP.
