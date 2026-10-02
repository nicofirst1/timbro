"""API polish (issue #166): no silent profile scaffolding, loud empty corpora,
caller-neutral force wording, and one exit code for learn guard refusals.

Four behaviors pinned here:

1. `add_text`/`add_file` raise on an unknown profile unless called with
   `create=True`; with `create=True` they scaffold exactly as before.
2. `read_corpus` raises on a missing path or a file path instead of returning
   an empty corpus; `list_profiles()` on a missing root still returns [].
3. The learn-guard messages say `--force (force=True from Python)` instead of
   bare `force=True`, so the same line serves CLI and API callers.
4. A refused `learn` exits 3 in both text and --json modes (was 1 text, 0
   json); the empty-profile bootstrap refusal stays exit 1.

Subprocess tests follow tests/test_cli_user_errors.py; every run is sandboxed
under tmp dirs (TIMBRO_HOME, TIMBRO_PROFILE_ROOT, XDG_DATA_HOME), never the
real ~/.timbro.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from timbro.errors import UserError
from timbro.profiles import _check_pair_slots_free, add_file, add_text, init_profile, learn

_TEXT = "The committee reviewed the annual budget with care and approved the plan."

_DRAFT = (
    "The committee reviewed the annual budget. Members raised concerns about research "
    "funding and asked for a revised proposal. After a lot of back and forth, the board "
    "agreed to the plan and scheduled a follow-up meeting for next quarter. Staff will "
    "send out the finalized figures before the next session begins."
)
_FINAL = (
    "The committee reviewed the annual budget with care. Members raised concerns about "
    "research funding and asked for a revised proposal. After careful deliberation, the "
    "board approved the plan and scheduled a follow-up meeting for next quarter. Staff "
    "will circulate the finalized figures before the next session begins."
)
# Semantically unrelated from the final: trips the content gate, so the refusal
# reason carries both the "save anyway" and the "override" wording.
_UNRELATED = "A cat slept on the warm windowsill all afternoon while it rained outside."

_FORCE_HINT = "--force (force=True from Python)"


def _tree(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


def _run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        root = base / "profiles"
        ex = root / "demo" / "exemplars"
        ex.mkdir(parents=True)
        (root / "demo" / "contrast").mkdir()
        for i in range(3):
            (ex / f"seed{i}.md").write_text(_FINAL, encoding="utf-8")
        (root / "empty" / "exemplars").mkdir(parents=True)
        (root / "empty" / "contrast").mkdir()
        (root / "empty" / "README.md").write_text("# empty\n", encoding="utf-8")
        draft = base / "draft.md"
        final = base / "final.md"
        draft.write_text(_DRAFT, encoding="utf-8")
        final.write_text(_FINAL, encoding="utf-8")
        unrelated = base / "unrelated.md"
        unrelated.write_text(_UNRELATED, encoding="utf-8")
        files = {"@DRAFT": draft, "@FINAL": final, "@UNRELATED": unrelated}
        argv = [str(files.get(a, a)) for a in argv]
        env = dict(os.environ)
        env.update(
            {
                "PYTHONHASHSEED": "0",
                "TIMBRO_HOME": str(base / "home"),
                "TIMBRO_PROFILE_ROOT": str(root),
                "XDG_DATA_HOME": str(base / "xdg"),
            }
        )
        return subprocess.run(
            [sys.executable, "-m", "timbro.cli", *argv],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
            check=False,
        )


class UnknownProfileRaiseTests(unittest.TestCase):
    """add_text/add_file refuse an unknown profile unless create=True (#166 item 1)."""

    def test_add_text_unknown_profile_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "profiles"
            before = _tree(td_path)

            with self.assertRaises(FileNotFoundError) as ctx:
                add_text("demo", _TEXT, bucket="exemplars", title="note", root=root)

            expected = (
                f"Unknown profile 'demo': {root / 'demo'} does not exist. "
                "Create it with 'timbro profiles init demo' or pass create=True."
            )
            self.assertEqual(str(ctx.exception), expected)
            self.assertIsInstance(ctx.exception, UserError)
            # Nothing written anywhere: no profile scaffolded, no files at all.
            self.assertEqual(_tree(td_path), before)

    def test_add_file_unknown_profile_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "profiles"
            src = td_path / "note.md"
            src.write_text(_TEXT, encoding="utf-8")
            before = _tree(td_path)

            with self.assertRaises(FileNotFoundError) as ctx:
                add_file("demo", src, bucket="exemplars", root=root)

            expected = (
                f"Unknown profile 'demo': {root / 'demo'} does not exist. "
                "Create it with 'timbro profiles init demo' or pass create=True."
            )
            self.assertEqual(str(ctx.exception), expected)
            self.assertIsInstance(ctx.exception, UserError)
            self.assertEqual(_tree(td_path), before)

    def test_add_text_create_true_scaffolds_exactly_as_before(self):
        # With create=True the scaffold must be byte-for-byte the scaffold
        # init_profile always made: README plus both bucket dirs.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "profiles"

            dst = add_text("demo", _TEXT, bucket="exemplars", title="note", root=root, create=True)

            self.assertEqual(dst, (root / "demo" / "exemplars" / "note.md").resolve())
            self.assertEqual(
                _tree(root),
                {"demo", "demo/README.md", "demo/contrast", "demo/exemplars", "demo/exemplars/note.md"},
            )
            self.assertEqual(dst.read_text(encoding="utf-8"), _TEXT)
            # Same scaffold init_profile makes, no more, no less.
            with tempfile.TemporaryDirectory() as td2:
                ref_root = Path(td2) / "profiles"
                init_profile("demo", root=ref_root)
                self.assertEqual(
                    (root / "demo" / "README.md").read_text(encoding="utf-8"),
                    (ref_root / "demo" / "README.md").read_text(encoding="utf-8"),
                )

    def test_add_file_create_true_scaffolds_exactly_as_before(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "profiles"
            src = td_path / "note.md"
            src.write_text(_TEXT, encoding="utf-8")

            dst = add_file("demo", src, bucket="exemplars", root=root, create=True)

            self.assertEqual(
                _tree(root),
                {"demo", "demo/README.md", "demo/contrast", "demo/exemplars", "demo/exemplars/note.md"},
            )
            self.assertEqual(dst.read_text(encoding="utf-8"), _TEXT)


class ReadCorpusPathTests(unittest.TestCase):
    """read_corpus raises on a missing path or a file path (#166 item 2)."""

    def test_read_corpus_missing_dir_raises_file_not_found(self):
        from timbro.model import read_corpus

        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "no-such-corpus"
            with self.assertRaises(FileNotFoundError) as ctx:
                read_corpus(missing)
            self.assertEqual(str(ctx.exception), f"Corpus directory not found: {missing.resolve()}")

    def test_read_corpus_file_path_raises_not_a_directory(self):
        from timbro.model import read_corpus

        with tempfile.TemporaryDirectory() as td:
            plain_file = Path(td) / "plain.md"
            plain_file.write_text(_TEXT, encoding="utf-8")
            with self.assertRaises(NotADirectoryError) as ctx:
                read_corpus(plain_file)
            self.assertEqual(str(ctx.exception), f"Corpus path is not a directory: {plain_file.resolve()}")

    def test_read_corpus_existing_empty_dir_still_returns_empty(self):
        # The raise is for a missing/wrong path, not for emptiness: an existing
        # empty corpus directory still reads as [] (the #161 error handles that).
        from timbro.model import read_corpus

        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "empty-corpus"
            empty.mkdir()
            self.assertEqual(read_corpus(empty), [])

    def test_list_profiles_missing_root_returns_empty_list(self):
        from timbro.profiles import list_profiles

        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(list_profiles(root=Path(td) / "no-such-root"), [])


class ForceWordingTests(unittest.TestCase):
    """The five guard messages are caller-neutral: --force first, Python kwarg in
    parentheses (#166 item 3)."""

    def test_slots_free_messages_say_dash_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            profile = init_profile("demo", root=root)
            (profile.exemplars_dir / "taken.md").write_text(_TEXT, encoding="utf-8")

            with self.assertRaises(FileExistsError) as ctx:
                _check_pair_slots_free(profile, "taken")
            self.assertIn(f"Destination already exists: {profile.exemplars_dir / 'taken.md'}. ", str(ctx.exception))
            self.assertIn(f"Use {_FORCE_HINT} or a different title.", str(ctx.exception))

            (profile.contrast_dir / "taken.md").write_text(_TEXT, encoding="utf-8")
            (profile.exemplars_dir / "taken.md").unlink()
            with self.assertRaises(FileExistsError) as ctx:
                _check_pair_slots_free(profile, "taken")
            self.assertIn(f"Use {_FORCE_HINT} or a different title.", str(ctx.exception))

    def test_bootstrap_refusal_message_says_dash_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            init_profile("empty", root=root)
            draft = Path(td) / "draft.md"
            final = Path(td) / "final.md"
            draft.write_text(_DRAFT, encoding="utf-8")
            final.write_text(_FINAL, encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                learn("empty", draft, final, root=root)

            self.assertIn(
                f"Seed it first (`profiles add-file`) or use {_FORCE_HINT} to bootstrap it with this pair.",
                str(ctx.exception),
            )

    def test_guard_refusal_reason_says_dash_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            init_profile("demo", root=root)
            for i in range(3):
                (root / "demo" / "exemplars" / f"seed{i}.md").write_text(_FINAL, encoding="utf-8")
            draft = Path(td) / "draft.md"
            final = Path(td) / "final.md"
            draft.write_text(_FINAL, encoding="utf-8")
            final.write_text(_FINAL, encoding="utf-8")

            result = learn("demo", draft, final, title="identical", root=root)

            self.assertFalse(result["saved"])
            self.assertIn(f"Use {_FORCE_HINT} to save anyway.", result["reason"])

    def test_guard_refusal_content_reason_says_dash_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            init_profile("demo", root=root)
            for i in range(3):
                (root / "demo" / "exemplars" / f"seed{i}.md").write_text(_FINAL, encoding="utf-8")
            draft = Path(td) / "draft.md"
            final = Path(td) / "final.md"
            draft.write_text(_FINAL, encoding="utf-8")
            final.write_text(_UNRELATED, encoding="utf-8")

            result = learn("demo", draft, final, title="unrelated", root=root)

            self.assertFalse(result["saved"])
            self.assertIn(f"Use {_FORCE_HINT} to save anyway.", result["reason"])
            self.assertIn(f"Use {_FORCE_HINT} to override.", result["reason"])


class LearnRefusalExitCodeTests(unittest.TestCase):
    """A refused learn exits 3 in both modes; the bootstrap refusal stays 1
    (#166 item 4). Printed bytes are unchanged."""

    def test_refused_learn_exits_3_in_text_mode(self):
        proc = _run_cli(["profiles", "learn", "demo", "--draft", "@FINAL", "--final", "@FINAL", "--title", "refused"])
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("final (distance"), proc.stderr)
        self.assertIn(f"Use {_FORCE_HINT} to save anyway.", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_refused_learn_exits_3_in_json_mode(self):
        proc = _run_cli(
            ["profiles", "learn", "demo", "--draft", "@FINAL", "--final", "@FINAL", "--title", "refused", "--json"]
        )
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(proc.stderr, "")
        payload = json.loads(proc.stdout)
        self.assertIs(payload["saved"], False)
        self.assertIn(f"Use {_FORCE_HINT} to save anyway.", payload["reason"])

    def test_bootstrap_refusal_still_exits_1(self):
        # The empty-profile bootstrap refusal keeps exit 1 (a UserError through
        # the one handler), with the same message wording as the API.
        proc = _run_cli(["profiles", "learn", "empty", "--draft", "@DRAFT", "--final", "@FINAL"])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("timbro: error: "), proc.stderr)
        self.assertIn(f"or use {_FORCE_HINT} to bootstrap it with this pair.", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
