"""The logo files, and where they show up: the screens, the browser tab, the printable record."""

import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from PIL import Image
from streamlit.testing.v1 import AppTest

from src import brand, record, respond
from src.charts import AMBER, AMBER_BAND
from src.pipeline import run
from ui.components import CSS, chip, logo

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
SVG_NS = "{http://www.w3.org/2000/svg}"
SVGS = ["baton-logo.svg", "baton-logo-dark.svg", "baton-mark.svg", "baton-favicon.svg"]
SLATE, STEEL, SIGNAL_AMBER, PAPER = "#16181D", "#B8BCC4", "#E8A33D", "#F5F5F3"
DIM_STEEL = "#5C606B"  # the far pill on the sheet's dark card
# Anything that would make a downloaded page reach outside itself.
EXTERNAL = re.compile(r"https?:|//[a-z]|src\s*=|href\s*=|url\(|@import|<link|<img|<script|<iframe|<object", re.I)


def shapes(name: str) -> list:
    return list(ET.parse(brand.ASSETS / name).getroot())


def fills(name: str) -> set:
    return {s.get("fill").upper() for s in shapes(name)}


# ---------- the files ----------

@pytest.mark.parametrize("name", SVGS)
def test_svg_is_pure_vector_and_needs_nothing_else(name):
    root = ET.parse(brand.ASSETS / name).getroot()
    assert root.tag == f"{SVG_NS}svg"
    assert {s.tag for s in root} <= {f"{SVG_NS}path", f"{SVG_NS}rect"}     # no <text>, <image>, <style>, gradients
    assert root.get("role") == "img" and root.get("aria-label") == "Baton"
    assert root.get("viewBox")
    # No fonts, and the namespace is the file's only URL (and it's not fetched).
    raw = (brand.ASSETS / name).read_text(encoding="utf-8")
    assert "font" not in raw and not EXTERNAL.search(raw.replace('xmlns="http://www.w3.org/2000/svg"', ""))


@pytest.mark.parametrize("name, expected", [
    ("baton-logo.svg", {SLATE, STEEL, SIGNAL_AMBER}),
    ("baton-logo-dark.svg", {PAPER, DIM_STEEL, SIGNAL_AMBER}),
    ("baton-mark.svg", {SLATE, STEEL, SIGNAL_AMBER}),
])
def test_logos_use_the_sheet_colours_on_a_transparent_background(name, expected):
    assert fills(name) == expected
    assert not any(s.tag == f"{SVG_NS}rect" for s in shapes(name))         # nothing painted behind the logo


def test_both_logo_variants_have_the_same_shapes():
    light, dark = shapes("baton-logo.svg"), shapes("baton-logo-dark.svg")
    assert [s.get("d") for s in light] == [s.get("d") for s in dark]
    assert len(light) == 4                                                 # far pill, near pill, overlap, wordmark


def test_mark_is_the_logo_without_the_wordmark():
    assert len(shapes("baton-mark.svg")) == 3


def test_favicon_is_a_dark_rounded_square_and_two_shapes():
    square, *rest = shapes("baton-favicon.svg")
    assert square.tag == f"{SVG_NS}rect" and square.get("fill").upper() == SLATE and float(square.get("rx")) > 0
    assert [s.get("fill").upper() for s in rest] == [PAPER, SIGNAL_AMBER]  # two shapes, amber on top


def test_favicon_png_is_square_with_transparent_corners():
    img = Image.open(brand.FAVICON)
    assert img.mode == "RGBA" and img.width == img.height >= 32
    assert img.getpixel((0, 0))[3] == 0 and img.getpixel((img.width - 1, img.height - 1))[3] == 0
    assert img.getpixel((img.width // 8, img.height // 2)) == (22, 24, 29, 255)


# ---------- inlining ----------

@pytest.mark.parametrize("name", SVGS)
def test_inlined_svg_has_no_urls_and_one_line(name):
    text = brand.inline_svg(name)
    assert text.startswith("<svg ") and text.endswith("</svg>") and "\n" not in text
    assert not EXTERNAL.search(text)


def test_screen_css_switches_to_exactly_the_dark_file_colours():
    """The screens inline one SVG and let the app's color-scheme pick the colours, so these can't drift."""
    assert f"light-dark({STEEL}, {DIM_STEEL})" in CSS
    assert f"light-dark({SLATE}, {PAPER})" in CSS
    for name in ("baton-logo.svg", "baton-logo-dark.svg"):
        assert re.findall(r'class="(baton-[a-z]+)"', (brand.ASSETS / name).read_text(encoding="utf-8")) == [
            "baton-far", "baton-near", "baton-overlap", "baton-near"]


# ---------- the screens ----------

def screen_html(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


@pytest.mark.parametrize("theme, name", [("dark", "baton-logo-dark.svg"), ("light", "baton-logo.svg"), (None, "baton-logo.svg")])
def test_logo_starts_from_the_file_for_the_theme_the_browser_reported(monkeypatch, theme, name):
    monkeypatch.setattr(st, "context", SimpleNamespace(theme=SimpleNamespace(type=theme)))
    assert logo() == f'<div class="baton-logo">{brand.inline_svg(name)}</div>'


def test_logo_tops_the_sidebar_and_stays_out_of_the_heading():
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception, at.exception
    side = [m.value for m in at.sidebar.markdown]
    assert 'class="baton-logo"' in side[0]                                             # first thing in the sidebar
    assert 'role="img"' in side[0] and 'aria-label="Baton"' in side[0] and "<svg" in side[0]
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", screen_html(at)).group(1)
    assert "<svg" not in h1 and re.sub(r"<[^>]+>", "", h1) == "Baton · Sat 7 Nov, 07:00 handover"


def test_logo_is_on_the_before_you_go_screen_too():
    at = AppTest.from_file(APP, default_timeout=90).run()
    at.button(key="open-before-you-go").click().run()
    assert not at.exception, at.exception
    assert [t.value for t in at.title] == ["Before you go"]
    assert 'class="baton-logo"' in screen_html(at)


def test_page_icon_comes_from_the_file_path_not_the_folder_it_runs_in(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(st, "set_page_config", lambda **kw: seen.update(kw))
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception, at.exception
    icon = Path(seen["page_icon"])
    assert icon.is_absolute() and icon.is_file() and icon == ROOT / "assets" / "baton-favicon.png"
    assert seen["page_title"] == "Baton"


# ---------- the printable record ----------

@pytest.fixture
def signed():
    """A real record, saved the way the app saves it."""
    result = run(mode="manual", shift="night")
    for item in result.top:
        respond.got_it("night", item.asset_id, "S. O'Brien")
    return record.sign_off(run(mode="manual", shift="night"), "S. O'Brien")


def test_record_embeds_the_logo_and_reaches_for_nothing_outside_itself(signed):
    rec, _, html_path = signed
    for page in (record.to_html(rec), html_path.read_text(encoding="utf-8")):
        assert page.count("<svg") == 1 and brand.inline_svg("baton-logo.svg") in page
        assert not EXTERNAL.search(page)


def test_record_logo_sits_above_the_heading_not_inside_it(signed):
    page = record.to_html(signed[0])
    assert page.index("<svg") < page.index("<h1>")
    assert re.search(r"<h1>(.*?)</h1>", page).group(1) == "Handover record"
    assert 'aria-label="Baton"' in page


def test_record_stays_the_light_logo_whatever_the_theme(signed):
    """It is a white page for printing, so it never takes the dark variant."""
    page = record.to_html(signed[0])
    assert PAPER not in page and DIM_STEEL not in page and SLATE in page


# ---------- theme alignment ----------

def test_primary_colour_is_slate():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["theme"]["primaryColor"] == SLATE


def rgb(colour: str) -> tuple:
    return tuple(int(colour.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


def contrast(a: tuple, b: tuple) -> float:
    def lum(c):
        r, g, b = [(v / 255 / 12.92) if v / 255 <= 0.03928 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def over(fg: tuple, bg: tuple, alpha: float) -> tuple:
    return tuple(f * alpha + b * (1 - alpha) for f, b in zip(fg, bg))


def test_amber_is_signal_amber_everywhere():
    assert AMBER == SIGNAL_AMBER
    assert AMBER_BAND.startswith("rgba(232, 163, 61,")
    css = CSS.lower()
    for old in ("#f5a623", "245, 166, 35", "#ffe1a1", "#6b4100"):
        assert old not in css
    assert SIGNAL_AMBER in CSS and "rgba(232, 163, 61," in CSS


def test_chip_text_on_amber_keeps_its_contrast():
    match = re.search(r"\.hc-chip\.clash \{ background: (#\w+); color: (#\w+);", CSS)
    assert match.group(1) == SIGNAL_AMBER
    assert contrast(rgb(match.group(1)), rgb(match.group(2))) >= 4.5
    assert "hc-chip clash" in chip("Notes say OK, data disagrees", "clash")


@pytest.mark.parametrize("band", [0.18, 0.28])     # at rest and on hover
def test_faded_note_text_on_the_amber_band_keeps_its_contrast(band):
    """Time and asset labels are faded, so on a clash note the fade has to leave 4.5:1."""
    assert re.search(rf"\.hc-note\.clash(:hover)? {{ background: rgba\(232, 163, 61, {band}\)", CSS)
    fade = float(re.search(r"\.hc-note\.clash \.hc-time, \.hc-note\.clash \.hc-asset \{ opacity: ([\d.]+);", CSS).group(1))
    text, white = (47, 45, 43), (255, 255, 255)       # Streamlit's body text colour on its light background
    surface = over(rgb(SIGNAL_AMBER), white, band)
    assert contrast(over(text, surface, fade), surface) >= 4.5
