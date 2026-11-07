import pytest


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Every test gets its own empty data/state folder, so tests never touch the real one."""
    state = tmp_path / "state"
    monkeypatch.setenv("HANDOVER_STATE_DIR", str(state))
    return state
