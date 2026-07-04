import os
import pytest


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr("state_manager.STATE_FILE", str(tmp_path / "state.json"))
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    yield tmp_path
