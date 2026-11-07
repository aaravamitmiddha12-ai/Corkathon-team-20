import os
import tempfile

import pytest


def pytest_configure(config):
    """Before any test or module-level fixture runs, point the app at a throwaway state folder,
    so the tests never read or write the real data/state (e.g. after a demo rehearsal)."""
    os.environ["HANDOVER_STATE_DIR"] = tempfile.mkdtemp(prefix="handover-state-")
    # Tests never use a real key, even if the machine has one set or saved: no test may call the API.
    for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "LLM_PROVIDER", "LLM_MODEL"):
        os.environ.pop(name, None)
    os.environ["BATON_SECRETS_FILE"] = os.path.join(tempfile.mkdtemp(prefix="baton-secrets-"), "none.toml")


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Every test also gets its own empty state folder, so tests can't affect each other."""
    state = tmp_path / "state"
    monkeypatch.setenv("HANDOVER_STATE_DIR", str(state))
    return state
