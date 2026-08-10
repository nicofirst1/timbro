# Regenerate: `vhs assets/demo.tape` from the repo root (needs `vhs` and `uvx` on PATH).
# Renders assets/demo.gif — the score -> edit -> re-score loop from issue #11.

Output assets/demo.gif

Require uvx

Set Shell "bash"
Set FontSize 22
Set Width 1280
Set Height 760
Set Padding 20
Set BorderRadius 10
Set WindowBar Colorful
Set TypingSpeed 45ms
Set Theme {"background": "#0B0F1A", "foreground": "#E8EEFF", "cursor": "#22D3EE", "selection": "#334155", "black": "#0B0F1A", "red": "#F87171", "green": "#34D399", "yellow": "#FBBF24", "blue": "#6366F1", "magenta": "#A78BFA", "cyan": "#22D3EE", "white": "#E8EEFF", "brightBlack": "#334155", "brightRed": "#F87171", "brightGreen": "#34D399", "brightYellow": "#FBBF24", "brightBlue": "#818CF8", "brightMagenta": "#C4B5FD", "brightCyan": "#67E8F9", "brightWhite": "#FFFFFF"}

Hide
Type "REPO=$PWD && cd $(mktemp -d) && cp $REPO/assets/demo/draft.before.md draft.md && clear"
Enter
Sleep 500ms
Show

# uvx cold-venv-resolve + spaCy load takes ~4-5s wall-clock; sleep past it
# so typing doesn't race the command's still-streaming output (#11 rerender).
Type "uvx timbro slop draft.md"
Enter
Sleep 6s

Type "# cut the dash, the diction, the wrap-up"
Enter
Sleep 800ms

Hide
Type "cp $REPO/assets/demo/draft.after.md draft.md && clear"
Enter
Sleep 500ms
Show

Type "uvx timbro slop draft.md"
Enter
Sleep 5s
