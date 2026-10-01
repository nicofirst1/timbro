import pytest


@pytest.fixture(autouse=True)
def _isolated_timbro_home(monkeypatch, tmp_path):
    """Keep tests hermetic to timbro's environment variables (issue #202).

    A developer's exported shell settings used to leak into the suite. The
    fixture isolates every variable that redirects where timbro reads and
    writes, or that changes behavior when set:

    - ``TIMBRO_HOME``: pointed at a per-test tmp dir, so tests never seed or
      read the real ``~/.timbro``.
    - ``XDG_DATA_HOME``: pointed at a per-test tmp dir (#202). Nothing in
      timbro or its dependencies reads it today; it guards the pre-0.9.0
      XDG profile location. Model caches follow ``HF_HOME`` /
      ``XDG_CACHE_HOME``, which stay unsandboxed on purpose so tests reuse
      the downloaded models.
    - ``TIMBRO_PROFILE_ROOT``: deleted. It takes precedence over
      ``$TIMBRO_HOME/profiles``, so an inherited value would send test
      writes (e.g. ``profiles add-file``) into the developer's real
      profile root, which ``profiles sync`` may then push.
    - ``TIMBRO_EXEMPLARS`` / ``TIMBRO_CONTRAST``: deleted. Inherited corpus
      paths would silently swap the scored corpus.
    - ``TIMBRO_NO_LOG`` / ``TIMBRO_DEBUG``: deleted. Inherited flags would
      change behavior (learn-log opt-out, debug traces).

    Tests that need one of these set it themselves (``monkeypatch`` /
    ``patch.dict``); they keep working because they run after this autouse
    fixture.
    """
    monkeypatch.setenv("TIMBRO_HOME", str(tmp_path / "timbro_home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))
    for var in (
        "TIMBRO_PROFILE_ROOT",
        "TIMBRO_EXEMPLARS",
        "TIMBRO_CONTRAST",
        "TIMBRO_NO_LOG",
        "TIMBRO_DEBUG",
    ):
        monkeypatch.delenv(var, raising=False)
