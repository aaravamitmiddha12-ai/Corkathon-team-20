"""Runs the real app.py, logging renders of the notes column, so a test can tell a fragment rerun from a full one."""
import os
import runpy
from pathlib import Path

import ui.home as home

LOG = Path(os.environ["BATON_RENDER_LOG"])
if not hasattr(home, "_wrapped_notes"):
    home._wrapped_notes = home.notes_column

    def logged(result):
        with LOG.open("a") as f:
            f.write("full\n")
        home._wrapped_notes(result)

    home.notes_column = logged

runpy.run_path(str(Path(os.environ["BATON_REPO"]) / "app.py"), run_name="__main__")
