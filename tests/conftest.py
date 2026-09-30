"""Every test gets an empty, private demo memory (never the real data/memory folder)."""
import pytest

from qm import config, store


@pytest.fixture(autouse=True)
def _isolated_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path / "_memory")
    monkeypatch.setattr(config, "SQLITE_PATH", tmp_path / "_qm.sqlite")
    if store._STORE is not None:
        store._STORE.sync_memory()
    yield
    if store._STORE is not None:
        store._STORE.sync_memory()
