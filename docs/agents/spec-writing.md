# Spec writing (coordinator checklist)

Run before writing an Implementer spec into an issue. Three checks, one output each.

1. **Callers.** For every change item that alters what existing code raises, returns or prints: `git grep -n "<name>" src/`, read each caller, and list the states it reaches the changed code in. Decide the new behavior for each state in the spec; a state left undecided becomes the implementer's guess (#166: `read_corpus` tightened, `from_dir`'s optional contrast bucket undecided).
2. **Real state.** Name one data state outside the issue's scenarios (written by another feature, such as a git-synced profile that lost its empty directories; from another machine or platform; or from an older version) and decide its behavior in the spec, explicitly.
3. **Behavior-identical section.** List the outputs to snapshot (the implementer captures exactly this section before changing code), including one probe per state from 1-2. A spec without this section leaves the snapshot surface to the implementer's invention.
