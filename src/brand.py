"""The logo files in assets/. Paths start from this file, so the app can run from any folder."""

import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FAVICON = ASSETS / "baton-favicon.png"


def inline_svg(name: str) -> str:
    """An SVG file as one line of markup to paste into a page. HTML doesn't need the namespace, and
    leaving it out means a downloaded page has no URLs in it at all."""
    text = (ASSETS / name).read_text(encoding="utf-8").replace(' xmlns="http://www.w3.org/2000/svg"', "")
    return re.sub(r"\s*\n\s*", "", text).strip()
