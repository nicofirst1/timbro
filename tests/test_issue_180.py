"""Issue #180: content_similarity stays in [0, 1]; detex_text times out."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from timbro.cleanup.latex import detex_text
from timbro.rewrite import content_similarity


class ContentSimilarityClampTests(unittest.TestCase):
    def test_self_similarity_never_exceeds_one(self):
        texts = [
            "x",
            "The cat sat on the mat.",
            "The committee approved the budget after a long debate about research funding.",
        ]
        for text in texts:
            with self.subTest(text=text):
                self.assertLessEqual(content_similarity(text, text), 1.0)


class DetexTimeoutTests(unittest.TestCase):
    def test_timeout_raises_runtime_error(self):
        with (
            patch("shutil.which", return_value="/usr/bin/detex"),
            patch(
                "timbro.cleanup.latex.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="detex", timeout=60),
            ),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                detex_text(r"\section{Intro}" "\nHello.")
        self.assertIn("timed out", str(ctx.exception))
