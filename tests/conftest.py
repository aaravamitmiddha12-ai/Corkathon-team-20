import os
import tempfile

import pytest


def pytest_configure(config):
    """Before any test or module-level fixture runs, point the app at a throwaway state folder,
    so the tests never read or write the real data/state (e.g. after a demo rehearsal)."""
    os.environ["HANDOVER_STATE_DIR"] = tempfile.mkdtemp(prefix="handover-state-")


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Every test also gets its own empty state folder, so tests can't affect each other."""
    state = tmp_path / "state"
    monkeypatch.setenv("HANDOVER_STATE_DIR", str(state))
    return state
