# Launch checklist (issue #14)

Ordering matters: each step depends on the one before it being live, not just merged. Don't skip ahead because a PR merged; confirm the thing actually works before moving on.

1. **PyPI live (#9).** `uvx timbro check draft.md` must work on a machine that has never cloned the repo. This blocks everything after it: the blog post's "Try it" section and the Show HN comment both currently point at `git clone` + `uv sync` because there's no verified uvx path yet (see the note in `launch/show-hn.md`). Once #9 ships, swap both drafts to lead with the uvx one-liner, and re-verify by actually running it on a clean machine or container, not just reading the CI log.

2. **GIF in README (#11).** The score-edit-re-score loop, under ~25s, embedded at the top of the README. This depends on #9 being done first, since the GIF should show commands a viewer can copy-paste, i.e. the uvx form. Once it's in the README, the blog post can link straight to it instead of the static distance SVG alone.

3. **Blog post (`launch/blog-post.md`).** Publish once 1 and 2 are live, so every command and link in the post is something a reader can immediately copy and run. Update the "Try it" section to the uvx one-liner before publishing (see step 1). Confirm the README numbers quoted in the post (47 / 9-35 / 86) still match `README.md` at publish time, since #10's positioning work already reshaped that section once.

4. **Show HN (`launch/show-hn.md`).** Submit after the blog post is live, since the first comment links to it. Fill in the uvx one-liner placeholder before posting (currently a NOTE in the draft, not a command). Pick a posting time with good HN traffic (US morning is the usual advice; the human should confirm).

5. **Cross-posts (X thread, LinkedIn).** Not drafted here (issue #14 mentions these but this task's scope was blog post + Show HN only). Should follow the Show HN post, not precede it, so they can link to real traction/comments if any exist yet.

6. **Listings (#13).** MCP registry, mcp.so, PulseMCP, Smithery, awesome-lists, plugin marketplace metadata. Do last, per #13's own acceptance criteria: it explicitly wants to go out after positioning (#10, already closed) and the GIF (#11), so every listing uses the finished pitch and visual instead of a stale one.

## Open blockers as of this draft

- #9 (PyPI/uvx) - open
- #11 (demo GIF) - open, depends on #9
- #13 (listings) - open, depends on #11

Per issue #14's own acceptance criteria, none of the launch artifacts in this folder should go out until #9 and #11 are both live.
