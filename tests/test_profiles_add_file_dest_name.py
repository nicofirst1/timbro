"""`--dest-name` must be a plain file name (issue #150).

`profiles.add_file` used `--dest-name` verbatim (`dst = target_dir / name`),
so `../x.md` wrote outside the bucket, an absolute path wrote anywhere, and
`subdir/x.md` crashed with a FileNotFoundError traceback. `add_file` must
reject anything that is not a plain file name before any write, and the CLI
must surface the rejection as one clean `timbro: error:` line, like #147.
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timbro.cli import main
from timbro.profiles import add_file


def _run(argv: list[str]) -> tuple[str, str, int]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            with patch("sys.argv", ["timbro", *argv]):
                main()
        except SystemExit as exc:
            code = exc.code or 0
    return stdout.getvalue(), stderr.getvalue(), code


def _tree(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


class AddFileDestNameValidationTests(unittest.TestCase):
    """add_file rejects dest_name values that are not plain file names."""

    def test_escape_paths_rejected_before_any_write(self):
        for bad in ["../escaped.md", "a/b.md"]:
            with self.subTest(dest_name=bad):
                with tempfile.TemporaryDirectory() as td:
                    td_path = Path(td)
                    root = td_path / "profiles"
                    src = td_path / "draft.md"
                    src.write_text("draft text\n", encoding="utf-8")
                    before = _tree(td_path)

                    with self.assertRaises(ValueError) as ctx:
                        add_file("demo", src, bucket="exemplars", dest_name=bad, root=root)

                    self.assertEqual(
                        str(ctx.exception),
                        f"--dest-name must be a plain file name, got '{bad}'",
                    )
                    # Nothing written anywhere: no bucket file, no escape, no profile.
                    self.assertEqual(_tree(td_path), before)

    def test_absolute_path_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "profiles"
            outside = td_path / "outside"
            outside.mkdir()
            src = td_path / "draft.md"
            src.write_text("draft text\n", encoding="utf-8")
            before = _tree(td_path)

            with self.assertRaises(ValueError) as ctx:
                add_file(
                    "demo", src, bucket="exemplars",
                    dest_name=str(outside / "escaped.md"), root=root,
                )

            self.assertEqual(
                str(ctx.exception),
                f"--dest-name must be a plain file name, got '{outside / 'escaped.md'}'",
            )
            self.assertEqual(_tree(td_path), before)
            self.assertFalse((outside / "escaped.md").exists())

    def test_empty_dot_and_dotdot_rejected(self):
        for bad in ["", ".", ".."]:
            with self.subTest(dest_name=bad):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td) / "profiles"
                    src = Path(td) / "draft.md"
                    src.write_text("draft text\n", encoding="utf-8")

                    with self.assertRaises(ValueError) as ctx:
                        add_file("demo", src, bucket="exemplars", dest_name=bad, root=root)

                    self.assertEqual(
                        str(ctx.exception),
                        f"--dest-name must be a plain file name, got '{bad}'",
                    )

    def test_nul_byte_rejected_before_any_write(self):
        # NUL cannot arrive through real argv, so this is API-only (review R1,
        # issue #150 round 2): a NUL name is a plain name by the Path.name rule
        # but must still be rejected with the --dest-name message, before
        # init_profile's side effects.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "profiles"
            src = td_path / "draft.md"
            src.write_text("draft text\n", encoding="utf-8")
            before = _tree(td_path)

            with self.assertRaises(ValueError) as ctx:
                add_file("demo", src, bucket="exemplars", dest_name="plain\x00.md", root=root)

            self.assertEqual(
                str(ctx.exception),
                "--dest-name must be a plain file name, got 'plain\x00.md'",
            )
            # Nothing written anywhere: no profile, no bucket file, no escape.
            self.assertEqual(_tree(td_path), before)

    def test_plain_name_still_works(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "profiles"
            src = td_path / "draft.md"
            src.write_text("draft text\n", encoding="utf-8")

            dst = add_file("demo", src, bucket="exemplars", dest_name="plain.md", root=root, create=True)

            # profile_root() resolves the root, so compare resolved paths.
            self.assertEqual(
                dst.resolve(),
                (root / "demo" / "exemplars" / "plain.md").resolve(),
            )
            self.assertEqual(dst.read_text(encoding="utf-8"), "draft text\n")


class AddFileDestNameCliTests(unittest.TestCase):
    """cmd_profiles_add_file surfaces the rejection as one clean error line."""

    def test_bad_dest_names_exit_1_with_one_error_line(self):
        for label, bad in [
            ("dotdot", "../escaped.md"),
            ("subdir", "subdir/inner.md"),
        ]:
            with self.subTest(dest_name=bad):
                with tempfile.TemporaryDirectory() as td:
                    src = Path(td) / "draft.md"
                    src.write_text("draft text\n", encoding="utf-8")

                    out, err, code = _run(
                        ["profiles", "add-file", "demo", str(src),
                         "--to", "exemplars", "--dest-name", bad]
                    )

                self.assertEqual(code, 1)
                self.assertNotIn("Traceback", err)
                self.assertEqual(err.count("\n"), 1, f"expected a single stderr line, got: {err!r}")
                self.assertEqual(
                    err,
                    f"timbro: error: --dest-name must be a plain file name, got '{bad}'\n",
                )
                self.assertEqual(out, "")
                # Nothing written outside the bucket in the tmp home.
                home = Path(os.environ["TIMBRO_HOME"])
                self.assertEqual([str(p) for p in home.rglob("escaped.md")], [])

    def test_absolute_dest_name_exit_1_and_no_escape_file(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outside = td_path / "outside"
            outside.mkdir()
            src = td_path / "draft.md"
            src.write_text("draft text\n", encoding="utf-8")

            out, err, code = _run(
                ["profiles", "add-file", "demo", str(src),
                 "--to", "exemplars", "--dest-name", str(outside / "escaped.md")]
            )

            self.assertEqual(code, 1)
            self.assertNotIn("Traceback", err)
            self.assertEqual(err.count("\n"), 1, f"expected a single stderr line, got: {err!r}")
            self.assertEqual(
                err,
                f"timbro: error: --dest-name must be a plain file name, got '{outside / 'escaped.md'}'\n",
            )
            self.assertEqual(out, "")
            self.assertFalse((outside / "escaped.md").exists())

    def test_plain_dest_name_still_exits_0(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "draft.md"
            src.write_text("draft text\n", encoding="utf-8")

            out, err, code = _run(
                ["profiles", "add-file", "demo", str(src),
                 "--to", "exemplars", "--dest-name", "plain.md"]
            )

            self.assertEqual(code, 0)
            # #166: add-file scaffolds on purpose and says so on stderr.
            self.assertEqual(err, "created profile demo\n", f"unexpected stderr: {err!r}")
            self.assertTrue(out.endswith("plain.md\n"), f"unexpected stdout: {out!r}")
