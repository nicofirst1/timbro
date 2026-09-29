import pytest


@pytest.fixture(autouse=True)
def _isolated_timbro_home(monkeypatch, tmp_path):
    """Keep tests from seeding or reading the real ~/.timbro."""
    monkeypatch.setenv("TIMBRO_HOME", str(tmp_path / "timbro_home"))
