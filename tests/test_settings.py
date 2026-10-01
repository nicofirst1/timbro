from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timbro.settings import Settings, debug, load_settings, no_log, settings_path, timbro_home


class _HomeCase(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.home = Path(td.name) / "th"
        p = patch.dict(os.environ, {"TIMBRO_HOME": str(self.home)}, clear=False)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("TIMBRO_NO_LOG", None)
        os.environ.pop("TIMBRO_DEBUG", None)

    def write(self, text: str) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        settings_path().write_text(text, encoding="utf-8")


class TimbroHomeTests(unittest.TestCase):
    def test_default_is_dot_timbro(self):
        with tempfile.TemporaryDirectory() as h, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TIMBRO_HOME", None)
            with patch.object(Path, "home", return_value=Path(h)):
                self.assertEqual(timbro_home(), Path(h) / ".timbro")

    def test_env_override(self):
        with patch.dict(os.environ, {"TIMBRO_HOME": "/x/y"}, clear=False):
            self.assertEqual(timbro_home(), Path("/x/y"))


class LoadSettingsTests(_HomeCase):
    def test_seeds_defaults_on_first_run(self):
        self.assertEqual(load_settings(), Settings())
        self.assertEqual(json.loads(settings_path().read_text()), {"no_log": False, "debug": False})

    def test_malformed_json_raises_naming_path(self):
        self.write("{nope")
        with self.assertRaises(ValueError) as cm:
            load_settings()
        self.assertIn(str(settings_path()), str(cm.exception))

    def test_wrong_type_raises(self):
        self.write('{"no_log": "yes"}')
        with self.assertRaises(ValueError):
            load_settings()

    def test_unknown_key_raises(self):
        self.write('{"bogus": 1}')
        with self.assertRaises(ValueError):
            load_settings()

    def test_non_object_raises(self):
        self.write("[]")
        with self.assertRaises(ValueError):
            load_settings()


class NoLogTests(_HomeCase):
    def test_json_true(self):
        self.write('{"no_log": true}')
        self.assertTrue(no_log())

    def test_env_overrides_json_false(self):
        self.write('{"no_log": false}')
        with patch.dict(os.environ, {"TIMBRO_NO_LOG": "1"}, clear=False):
            self.assertTrue(no_log())

    def test_env_unset_json_false(self):
        self.write('{"no_log": false}')
        self.assertFalse(no_log())


class DebugTests(_HomeCase):
    def test_default_off(self):
        self.assertFalse(debug())

    def test_json_true(self):
        self.write('{"debug": true}')
        self.assertTrue(debug())

    def test_env_overrides_json_false(self):
        self.write('{"debug": false}')
        with patch.dict(os.environ, {"TIMBRO_DEBUG": "1"}, clear=False):
            self.assertTrue(debug())


if __name__ == "__main__":
    unittest.main()
