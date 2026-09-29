"""Concurrent first runs must serialize the spaCy model install (#173).

Two simultaneous first runs, with en_core_web_sm not yet installed, both hit
load_spacy's OSError branch and both called _install_model(): the loser could
die with pip's "Unpack failed: incomplete input" and the model was always
installed twice. The fix serializes the install behind an exclusive flock on
<tmpdir>/timbro-spacy-install-<sha256(sys.prefix)[:12]>.lock and re-checks
spacy.load under the lock, so only the process that actually installs prints
the "downloading" notice.

Tests never trigger a real install: spacy.load and _install_model are
monkeypatched, and tempfile.gettempdir is pointed at a tmp dir so the lock
file lands there.
"""
from __future__ import annotations

import hashlib
import io
import shutil
import sys
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from timbro import spacy_model


def _expected_lock_name() -> str:
    digest = hashlib.sha256(sys.prefix.encode()).hexdigest()[:12]
    return f"timbro-spacy-install-{digest}.lock"


class _LockedStringIO(io.StringIO):
    """StringIO safe for concurrent writes from several threads."""

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()

    def write(self, s):
        with self._lock:
            return super().write(s)


class _InstallRaceHarness:
    """Stateful fakes for spacy.load/_install_model shared across threads.

    spacy.load raises OSError until the (fake) install finishes, exactly like
    a real cold start; _install_model counts calls and then flips that state.
    With threads > 1 a barrier inside the first load attempt of each thread
    makes the race deterministic: every thread sees one OSError before any of
    them can reach the install path.
    """

    def __init__(self, threads: int = 1, install_sleep: float = 0.0):
        self.model = MagicMock(name="loaded_model")
        self.install_calls = 0
        self._install_sleep = install_sleep
        self._state_lock = threading.Lock()
        self._installed = threading.Event()
        self._seen_threads: set[int] = set()
        self._first_attempt = (
            threading.Barrier(threads, timeout=10) if threads > 1 else None
        )

    def fake_load(self, *args, **kwargs):
        if self._installed.is_set():
            return self.model
        first_time = False
        with self._state_lock:
            me = id(threading.current_thread())
            if me not in self._seen_threads:
                self._seen_threads.add(me)
                first_time = True
        if first_time and self._first_attempt is not None:
            self._first_attempt.wait()
        raise OSError("model not installed")

    def fake_install(self):
        with self._state_lock:
            self.install_calls += 1
        if self._install_sleep:
            time.sleep(self._install_sleep)
        self._installed.set()


@contextmanager
def _patched(harness: _InstallRaceHarness, tmp_dir: str):
    """Point the lock dir at tmp_dir, capture stderr, fake spacy.load/install."""
    with ExitStack() as stack:
        stack.enter_context(patch("tempfile.gettempdir", return_value=tmp_dir))
        stderr = _LockedStringIO()
        stack.enter_context(patch("sys.stderr", new=stderr))
        stack.enter_context(patch("spacy.load", new=harness.fake_load))
        stack.enter_context(
            patch.object(spacy_model, "_install_model", new=harness.fake_install)
        )
        yield stderr


class SpacyInstallLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="timbro-173-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)

    def test_two_threads_racing_cold_start_install_once(self):
        harness = _InstallRaceHarness(threads=2, install_sleep=0.05)
        outcomes: dict[str, tuple[str, object]] = {}
        outcomes_lock = threading.Lock()

        def run() -> None:
            try:
                result = spacy_model.load_spacy()
                status, payload = "ok", result
            except Exception as exc:  # noqa: BLE001 - recorded, asserted below
                status, payload = "error", exc
            with outcomes_lock:
                outcomes[threading.current_thread().name] = (status, payload)

        threads = [threading.Thread(target=run, name=f"runner-{i}") for i in range(2)]
        with _patched(harness, self.tmp_dir) as stderr:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)
                self.assertFalse(
                    thread.is_alive(), f"{thread.name} hung: lock not released"
                )

        errors = [payload for status, payload in outcomes.values() if status == "error"]
        self.assertEqual(errors, [], f"threads failed: {errors!r}")
        results = [payload for status, payload in outcomes.values() if status == "ok"]
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r is harness.model for r in results))
        self.assertEqual(
            harness.install_calls,
            1,
            f"expected exactly one install, got {harness.install_calls}",
        )
        self.assertEqual(
            stderr.getvalue().count("downloading spaCy model"),
            1,
            f"notice must print only for the installing process, stderr: {stderr.getvalue()!r}",
        )
        self.assertTrue(
            (Path(self.tmp_dir) / _expected_lock_name()).exists(),
            "install lock file must live in the patched tmp dir",
        )

    def test_single_process_cold_start_installs_once_and_loads(self):
        harness = _InstallRaceHarness()
        with _patched(harness, self.tmp_dir) as stderr:
            result = spacy_model.load_spacy()

        self.assertIs(result, harness.model)
        self.assertEqual(harness.install_calls, 1)
        self.assertEqual(
            stderr.getvalue().count("downloading spaCy model"),
            1,
            f"stderr: {stderr.getvalue()!r}",
        )

    def test_lock_file_lands_in_tmpdir_with_expected_name(self):
        harness = _InstallRaceHarness()
        with _patched(harness, self.tmp_dir):
            spacy_model.load_spacy()

        lock_path = Path(self.tmp_dir) / _expected_lock_name()
        self.assertTrue(lock_path.exists(), f"missing lock file {lock_path}")


if __name__ == "__main__":
    unittest.main()
