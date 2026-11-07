"""The logo in the real app and the real downloaded record, in Chrome, on the builders' port 8770."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import fitz
from playwright.sync_api import sync_playwright

# Paths come from this file's place in the repo (handoff/). Screenshots go to a temp folder, or BATON_SHOTS.
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("BATON_REPO_DIR", HERE.parent))
SHOTS = Path(os.environ.get("BATON_SHOTS", Path(tempfile.gettempdir()) / "baton-checks")) / "app"
SHOTS.mkdir(parents=True, exist_ok=True)
# "chrome" by default; set BATON_CHANNEL=msedge on a machine that only has Edge (same engine).
CHANNEL = os.environ.get("BATON_CHANNEL", "chrome")
PORT = 8770
URL = f"http://127.0.0.1:{PORT}/"
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if not ok else ""), flush=True)
    if not ok:
        fails.append(name)


def start(*extra):
    env = dict(os.environ, PYTHONUTF8="1", HANDOVER_STATE_DIR=tempfile.mkdtemp(prefix="baton-state-"))
    proc = subprocess.Popen([str(REPO / ".venv/Scripts/python.exe"), "-m", "streamlit", "run", "app.py", "--server.port", str(PORT),
                             "--server.headless", "true", "--browser.gatherUsageStats", "false", *extra],
                            cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        try:
            urllib.request.urlopen(f"{URL}_stcore/health", timeout=1)
            return proc
        except Exception:
            time.sleep(1)
    raise SystemExit("server did not start")


def settle(page):
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=30000)
    page.wait_for_timeout(500)


def open_home(ctx, url=URL):
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_selector(".hc-header h1", timeout=90000)
    page.wait_for_selector(".js-plotly-plot .scatterlayer", timeout=30000)
    settle(page)
    page.wait_for_timeout(600)  # let the entrance finish before a screenshot
    return page


# The logo on show: the sidebar's on a wide screen, the top bar's below 1024px (the sidebar is then a closed drawer).
LOGO_INFO = """() => {const s=[...document.querySelectorAll('.baton-logo svg')].find(e=>{const r=e.getBoundingClientRect(); return r.width>0 && r.right>0 && getComputedStyle(e).visibility==='visible'}); if(!s) return null; const r=s.getBoundingClientRect();
  const g=e=>getComputedStyle(s.querySelector(e)).fill;
  return {w:r.width,h:r.height,left:r.left,top:r.top,right:r.right,far:g('.baton-far'),near:g('.baton-near'),overlap:g('.baton-overlap'),
          word:getComputedStyle(s.querySelectorAll('path')[3]).fill,paths:s.querySelectorAll('path').length,
          scheme:getComputedStyle(document.querySelector('[data-testid="stApp"]')).colorScheme,
          bg:getComputedStyle(document.querySelector('[data-testid="stApp"]')).backgroundColor,
          over:document.documentElement.scrollWidth-document.documentElement.clientWidth,
          heading:!!s.closest('h1,h2,h3,h4,h5,h6'), vw:innerWidth}}"""
LIGHT = dict(far="rgb(184, 188, 196)", near="rgb(22, 24, 29)", overlap="rgb(232, 163, 61)", word="rgb(22, 24, 29)")
DARK = dict(far="rgb(92, 96, 107)", near="rgb(245, 245, 243)", overlap="rgb(232, 163, 61)", word="rgb(245, 245, 243)")


def open_before(page):
    """Below 1024px the button is in the drawer: open it first."""
    if page.locator(".baton-menu").is_visible():
        page.locator(".baton-menu").click()
        page.wait_for_timeout(400)
    page.locator(".st-key-open-before-you-go button").click()


def check_logo(page, label, colours):
    info = page.evaluate(LOGO_INFO)
    check(f"{label}: logo present", info is not None and info["paths"] == 4, str(info))
    if not info:
        return
    check(f"{label}: colours {'dark' if colours is DARK else 'light'}", all(info[k] == v for k, v in colours.items()), str(info))
    check(f"{label}: readable size inside the screen", info["h"] >= 26 and info["right"] <= info["vw"] and info["left"] >= 16, str(info))
    check(f"{label}: not in a heading", not info["heading"])
    check(f"{label}: no sideways scroll", info["over"] <= 0, str(info["over"]))
    check(f"{label}: accessible name", page.get_by_role("img", name="Baton", exact=True).count() == 1)


def lum(rgb):
    v = [(c / 255 / 12.92) if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def contrast(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def nums(css):
    return [float(x) for x in re.findall(r"[\d.]+", css)]


def over(fg, bg):
    a = fg[3] if len(fg) > 3 else 1.0
    return [fg[i] * a + bg[i] * (1 - a) for i in range(3)]


proc = start()
record_file = None
try:
    with sync_playwright() as p:
        b = p.chromium.launch(channel=CHANNEL)

        # ---------- Desktop, light ----------
        ctx = b.new_context(viewport={"width": 1400, "height": 950}, color_scheme="light", accept_downloads=True)
        page = open_home(ctx)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        check_logo(page, "home 1400", LIGHT)
        check("home: title text unchanged", page.inner_text(".hc-header h1") == "Baton · Sat 7 Nov, 07:00 handover", page.inner_text(".hc-header h1"))
        check("home: logo first in the main column", page.evaluate("""() => {const m=document.querySelector('[data-testid="stMainBlockContainer"]');
             const a=document.querySelector('.baton-logo').getBoundingClientRect(); const b=m.querySelector('[data-testid="stHorizontalBlock"]').getBoundingClientRect(); return a.bottom<=b.top}"""))
        lab = page.get_by_text("Handover", exact=True).first.bounding_box()
        check("home: top bar clear of the Streamlit header", lab["y"] >= 60, str(lab))
        # Favicon as the browser gets it
        fav = page.evaluate("""async () => {const l=[...document.querySelectorAll('link[rel*="icon"]')].pop(); const r=await fetch(l.href);
           const b=new Uint8Array(await r.arrayBuffer()); return {href:l.href, type:r.headers.get('content-type'), bytes:[...b]}}""")
        fav_path = SHOTS / "served-favicon.png"
        fav_path.write_bytes(bytes(fav["bytes"]))
        fpix = fitz.Pixmap(str(fav_path))
        check("favicon served as PNG with alpha", fav["type"] == "image/png" and fpix.alpha == 1 and fpix.pixel(0, 0)[3] == 0, f"{fav['type']} alpha={fpix.alpha} corner={fpix.pixel(0, 0)}")
        check("favicon same pixels as the asset", fav_path.read_bytes() == (REPO / "assets/baton-favicon.png").read_bytes() or fpix.pixel(48, 48) == fitz.Pixmap(str(REPO / "assets/baton-favicon.png")).pixel(48, 48))
        print("   favicon href:", fav["href"][:80])
        # Amber and primary, as computed
        amber = page.evaluate("""() => {const s=(q,p)=>getComputedStyle(document.querySelector(q))[p];
          const seen=[...document.querySelectorAll('.js-plotly-plot')][0].data.filter(t=>t.marker&&t.name&&t.name.startsWith('Alert after')).map(t=>t.marker.color);
          const bands=[...document.querySelectorAll('.js-plotly-plot')][0].data.filter(t=>t.type==='bar').map(t=>t.marker.color);
          return {chip:[s('.hc-chip.clash','backgroundColor'),s('.hc-chip.clash','color')],
                  note:[s('.hc-note.clash','backgroundColor'),s('.hc-note.clash','borderLeftColor'),s('.hc-note.clash','color')],
                  time:[s('.hc-note.clash .hc-time','opacity'),s('.hc-note.clash .hc-asset','opacity')],
                  dot:s('.baton-legend .dot.after','backgroundColor'), band:s('.baton-legend .band','backgroundColor'),
                  tick:s('.baton-limit-tick.warn','backgroundColor'), markers:seen, bands:bands,
                  radio:[...document.querySelectorAll('[data-testid="stRadio"] label')].map(l=>{const d=l.querySelector('div');return d?getComputedStyle(d).backgroundColor:null}),
                  primary:(()=>{const b=document.querySelector('.st-key-got-night-FRZ-12 button');return [getComputedStyle(b).backgroundColor,getComputedStyle(b).color]})()}}""")
        print("   ", json.dumps(amber))
        check("chip fill is Signal amber", amber["chip"][0] == "rgb(232, 163, 61)", str(amber["chip"]))
        c = contrast(nums(amber["chip"][0]), nums(amber["chip"][1]))
        check(f"chip text contrast {c:.2f}:1 >= 4.5", c >= 4.5)
        check("note band and edge", amber["note"][0] == "rgba(232, 163, 61, 0.18)" and amber["note"][1] == "rgb(232, 163, 61)", str(amber["note"]))
        surface = over(nums(amber["note"][0]), [255, 255, 255])
        c = contrast(nums(amber["note"][2]), surface)
        check(f"note text on band {c:.2f}:1", c >= 4.5)
        faded = over(nums(amber["note"][2]) + [float(amber["time"][0])], surface)
        c = contrast(faded, surface)
        check(f"faded time on band {c:.2f}:1", c >= 4.5)
        check("legend, markers and bands amber; warning tick neutral", amber["dot"] == "rgb(232, 163, 61)" and "232, 163, 61" not in amber["tick"]
              and "rgba(232, 163, 61, 0.28)" == amber["band"] and set(amber["markers"]) == {"#E8A33D"} and set(amber["bands"]) == {"rgba(232, 163, 61, 0.22)"}, str(amber))
        check("primary button is Slate", amber["primary"][0] == "rgb(22, 24, 29)", str(amber["primary"]))
        c = contrast(nums(amber["primary"][0]), nums(amber["primary"][1]))
        check(f"primary button text {c:.1f}:1", c >= 4.5)
        flash = page.evaluate("""() => {for (const s of document.styleSheets) { try { for (const r of s.cssRules) { if (r.name==='baton-flash') return r.cssText } } catch(e){} } return ''}""")
        # Amber is kept for "notes and data disagree": the jump flash uses the focus colour.
        check("flash is neutral, not amber", "baton-focus" in flash and "232, 163, 61" not in flash, flash)
        page.mouse.move(5, 5)
        page.screenshot(path=SHOTS / "home-1400.png")

        # ---------- Before you go, desktop ----------
        open_before(page)
        page.wait_for_selector(".st-key-back-home", timeout=30000)
        settle(page)
        check_logo(page, "before 1400", LIGHT)
        check("before: heading intact", page.locator("h1", has_text="Before you go").count() == 1 and page.locator("h1 svg").count() == 0
              or page.get_by_role("heading", name="Before you go").count() == 1)
        page.mouse.move(5, 5)
        page.screenshot(path=SHOTS / "before-1400.png")
        page.locator(".st-key-back-home button").click()
        page.wait_for_selector(".hc-header h1", timeout=30000)
        settle(page)

        # ---------- Sign off, take the real downloaded record ----------
        for asset in ["FRZ-12", "WFI-LOOP-1", "CH-2-P3", "HPLC-07", "BAL-03"]:
            page.locator(f".st-key-got-night-{asset} button").click()
            page.wait_for_selector(f".st-key-open-night-{asset}", timeout=30000)
            settle(page)
        page.wait_for_selector(".st-key-signoff-night", timeout=30000)
        settle(page)
        page.locator(".st-key-signoff-night button").click()
        page.wait_for_selector(".hc-banner.done", timeout=30000)
        settle(page)
        with page.expect_download(timeout=30000) as d:
            page.locator(".st-key-download-night button").click()
        record_file = SHOTS / "record.html"
        d.value.save_as(str(record_file))
        check("record downloaded", record_file.stat().st_size > 2000)
        check("no page errors on the way", not errors, str(errors))
        check("no exception box", page.locator('[data-testid="stException"]').count() == 0)
        ctx.close()

        # ---------- The record, offline, at both widths, and printed ----------
        html = record_file.read_text(encoding="utf-8")
        check("record: no URL anywhere", not re.search(r"https?:|//[a-z]|src\s*=|href\s*=|url\(|@import|<link|<img|<script", html, re.I))
        for width, height, name in [(1400, 900, "record-1400"), (390, 844, "record-390")]:
            ctx = b.new_context(viewport={"width": width, "height": height}, color_scheme="light", offline=True)
            page = ctx.new_page()
            requests = []
            page.on("request", lambda r: requests.append(r.url))
            page.goto(record_file.as_uri())
            page.wait_for_timeout(300)
            check(f"{name}: page asks for nothing but itself", len(requests) == 1, str(requests))
            info = page.evaluate("""() => {const s=document.querySelector('.logo svg'), r=s.getBoundingClientRect(), h=document.querySelector('h1').getBoundingClientRect();
               return {w:r.width,h:r.height,right:r.right,vw:innerWidth,above:r.bottom<=h.top,inh1:!!s.closest('h1'),
                 fills:[...s.querySelectorAll('path')].map(p=>getComputedStyle(p).fill), over:document.documentElement.scrollWidth-document.documentElement.clientWidth}}""")
            check(f"{name}: logo above heading, on screen", info["above"] and not info["inh1"] and info["h"] >= 26 and info["right"] <= info["vw"], str(info))
            check(f"{name}: light colours", info["fills"] == [LIGHT["far"], LIGHT["near"], LIGHT["overlap"], LIGHT["word"]], str(info["fills"]))
            check(f"{name}: accessible name", page.get_by_role("img", name="Baton", exact=True).count() == 1)
            print(f"   {name} sideways overflow: {info['over']}")
            page.screenshot(path=SHOTS / f"{name}.png")
            ctx.close()
        # A dark-mode browser must not change the printed record
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, color_scheme="dark", offline=True)
        page = ctx.new_page()
        page.goto(record_file.as_uri())
        fills = page.evaluate("[...document.querySelectorAll('.logo svg path')].map(p=>getComputedStyle(p).fill)")
        check("record in a dark-mode browser keeps the light logo", fills == [LIGHT["far"], LIGHT["near"], LIGHT["overlap"], LIGHT["word"]], str(fills))
        # Print, as a person would: background graphics off.
        page.emulate_media(media="print")
        check("record print: logo still displayed", page.evaluate("getComputedStyle(document.querySelector('.logo svg')).display") == "block")
        pdf = SHOTS / "record.pdf"
        page.pdf(path=str(pdf), print_background=False, format="A4")
        ctx.close()
        doc = fitz.open(str(pdf))
        print("   pdf pages:", len(doc), "images:", len(doc[0].get_images()), "drawings:", len(doc[0].get_drawings()))
        doc[0].get_pixmap(dpi=110).save(str(SHOTS / "record-print.png"))
        pfills = {tuple(round(c * 255) for c in d["fill"]) for d in doc[0].get_drawings() if d.get("fill") and len(d["fill"]) == 3}
        check("record print: logo colours reach the paper as vectors", {(22, 24, 29), (184, 188, 196), (232, 163, 61)} <= pfills, str(pfills))
        doc.close()

        # ---------- Phone, light ----------
        ctx = b.new_context(viewport={"width": 390, "height": 844}, color_scheme="light", device_scale_factor=2)
        page = open_home(ctx)
        check_logo(page, "home 390", LIGHT)
        page.screenshot(path=SHOTS / "home-390.png")
        open_before(page)
        page.wait_for_selector(".st-key-back-home", timeout=30000)
        settle(page)
        check_logo(page, "before 390", LIGHT)
        page.screenshot(path=SHOTS / "before-390.png")
        ctx.close()

        # ---------- Dark: the shipped config has a light and a dark theme, and follows the computer ----------
        for width, height, tag in [(1400, 950, "1400"), (390, 844, "390")]:
            ctx = b.new_context(viewport={"width": width, "height": height}, color_scheme="dark")
            page = open_home(ctx)
            info = page.evaluate(LOGO_INFO)
            check(f"dark {tag}: app really is dark", info["scheme"] == "dark", str(info))
            check_logo(page, f"dark {tag} home", DARK)
            page.screenshot(path=SHOTS / f"dark-home-{tag}.png")
            open_before(page)
            page.wait_for_selector(".st-key-back-home", timeout=30000)
            settle(page)
            check_logo(page, f"dark {tag} before", DARK)
            page.screenshot(path=SHOTS / f"dark-before-{tag}.png")
            ctx.close()
        b.close()
finally:
    proc.terminate()
    proc.wait(timeout=30)

print(f"\n{len(fails)} failed: {fails}" if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
