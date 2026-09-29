"""Dispatch-table wiring for cli.main() (issue #109).

One module-level handler per leaf subparser, wired via set_defaults(func=...);
main() itself must not hand-dispatch on args.cmd / args.profiles_cmd.
"""

from __future__ import annotations

import argparse
import inspect
import unittest
from unittest import mock

import timbro.cli as cli

# Minimal argv per subcommand -> the handler its subparser must wire via set_defaults.
_WIRING = {
    ("score", "draft.md"): "cmd_score",
    ("check", "draft.md"): "cmd_check",
    ("accept", "orig.md", "revised.md"): "cmd_accept",
    ("analyze", "draft.md"): "cmd_analyze",
    ("profiles", "list"): "cmd_profiles_list",
    ("profiles", "init", "name"): "cmd_profiles_init",
    ("profiles", "sync"): "cmd_profiles_sync",
    ("profiles", "add-file", "name", "src.md", "--to", "exemplars"): "cmd_profiles_add_file",
    ("profiles", "env", "name"): "cmd_profiles_env",
    ("profiles", "diagnose", "name"): "cmd_profiles_diagnose",
    ("profiles", "learn", "name", "--draft", "d.md", "--final", "f.md"): "cmd_profiles_learn",
}


class _ParserBuilt(Exception):
    """Sentinel: stop main() right after it reaches ap.parse_args()."""


def _build_parser() -> argparse.ArgumentParser:
    """Build the parser exactly the way main() does.

    main() constructs the parser and immediately parses argv, so intercept
    parse_args, capture the parser, and stop before any dispatch runs.
    """
    captured: dict = {}

    def fake_parse(self, args=None, namespace=None):
        captured["parser"] = self
        raise _ParserBuilt

    with mock.patch.object(argparse.ArgumentParser, "parse_args", fake_parse):
        try:
            cli.main()
        except _ParserBuilt:
            pass
    if "parser" not in captured:
        raise AssertionError("main() never reached ap.parse_args()")
    return captured["parser"]


class HandlerFunctionsExistTests(unittest.TestCase):
    def test_each_subcommand_has_a_module_level_handler(self):
        for handler in _WIRING.values():
            with self.subTest(handler=handler):
                fn = getattr(cli, handler, None)
                self.assertTrue(inspect.isfunction(fn), f"missing module-level handler: {handler}")


class MainHasNoManualDispatchTests(unittest.TestCase):
    def test_main_source_has_no_cmd_or_profiles_cmd_dispatch(self):
        source = inspect.getsource(cli.main)
        self.assertNotIn("args.cmd ==", source)
        self.assertNotIn("args.profiles_cmd ==", source)


class SubparsersWireTheirHandlerTests(unittest.TestCase):
    def test_parsing_each_subcommand_sets_func_to_its_handler(self):
        parser = _build_parser()
        for argv, handler in _WIRING.items():
            with self.subTest(argv=argv):
                ns = parser.parse_args(list(argv))
                fn = getattr(cli, handler, None)
                self.assertIsNotNone(fn, f"missing module-level handler: {handler}")
                self.assertIs(ns.func, fn)


class MainCallsTheWiredHandlerTests(unittest.TestCase):
    def test_main_routes_argv_to_the_handler(self):
        # set_defaults binds the function object at parser build time, so patching the
        # module attribute would not reach it; a namespace whose func is a mock does.
        handler = mock.Mock()
        ns = argparse.Namespace(func=handler)
        with mock.patch.object(argparse.ArgumentParser, "parse_args", return_value=ns):
            cli.main()
        handler.assert_called_once_with(ns)


if __name__ == "__main__":
    unittest.main()
