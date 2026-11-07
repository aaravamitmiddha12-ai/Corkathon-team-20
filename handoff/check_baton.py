"""Drives the real Baton app in Chrome."""
import os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(r"C:\Users\ksole\Corkathon-team-20")
HERE = Path(__file__).parent
SHOTS = HERE / "baton"
SHOTS.mkdir(exist_ok=True)
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if not ok else ""), flush=True)
    if not ok:
        fails.append(name)


def start(port):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONPATH=str(REPO), BATON_REPO=str(REPO),
               HANDOVER_STATE_DIR=tempfile.mkdtemp(prefix="baton-state-"),
               BATON_RENDER_LOG=str(LOG))
    proc = subprocess.Popen([str(REPO / ".venv/Scripts/python.exe"), "-m", "streamlit", "run", str(HERE / "baton_launcher.py"),
                             "--server.port", str(port), "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                            cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1)
            return proc
        except Exception:
            time.sleep(1)
    raise SystemExit("server did not start")


LOG = Path(tempfile.mkdtemp()) / "renders.log"
LOG.write_text("")
PORT = 8765
proc = start(PORT)
URL = f"http://127.0.0.1:{PORT}/"


def renders():
    return LOG.read_text().count("full")


def settle(page):
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=30000)
    page.wait_for_timeout(500)


def got_it(page, asset):
    page.locator(f".st-key-got-night-{asset} button").click()
    page.wait_for_selector(f".st-key-open-night-{asset}", timeout=30000)
    settle(page)


try:
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        ctx = b.new_context(viewport={"width": 1400, "height": 950}, color_scheme="light")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_selector(".baton-tl-label", timeout=90000)
        page.wait_for_selector(".js-plotly-plot .scatterlayer", timeout=30000)
        settle(page)

        # Header
        body = page.inner_text("body")
        check("title", page.inner_text(".hc-header h1") == "Baton · Sat 7 Nov, 07:00 handover", page.inner_text(".hc-header h1"))
        check("subtitle", page.inner_text(".hc-sub") == "From D. Murphy · night shift", page.inner_text(".hc-sub"))
        check("tab title", page.title() == "Baton", page.title())
        check("no expert badge", "expert ranking" not in body)
        check("no Tally or old name on screen", "Tally" not in body and "Handover Check" not in body)

        # Logo
        check("one logo, with its accessible name", page.get_by_role("img", name="Baton", exact=True).count() == 1)
        check("logo drawn, not an empty box", page.locator(".baton-logo svg path").count() == 4)
        # Streamlit puts its own hover link-anchor (an svg) in every heading; nothing else may be there.
        extra = page.evaluate("""() => [...document.querySelectorAll('.hc-header h1 svg')]
           .filter(s => !s.closest('[data-testid="stHeaderActionElements"]')).map(s => s.outerHTML.slice(0, 80))""")
        check("no icon inside the title (besides Streamlit's anchor link)", extra == [], str(extra))
        place = page.evaluate("""() => {const r=document.querySelector('.baton-logo svg').getBoundingClientRect(), t=document.querySelector('.hc-header h1').getBoundingClientRect();
           return [r.bottom<=t.top, r.height, r.left, t.left]}""")
        check("logo above the title, on its left edge", place[0] and abs(place[2] - place[3]) < 1 and 24 <= place[1] <= 40, str(place))
        fav = page.evaluate("""async () => {const l=[...document.querySelectorAll('link[rel*="icon"]')].pop(); const r=await fetch(l.href);
           const b=new Uint8Array(await r.arrayBuffer()); return [l.href, r.headers.get('content-type'), [...b.slice(0,4)]]}""")
        check("browser tab shows the favicon file", fav[1] == "image/png" and fav[2] == [137, 80, 78, 71], str(fav))

        # Timeline labels
        labels = page.eval_on_selector_all(".baton-tl-label", "e=>e.map(x=>x.innerText.replace(/\\s+/g,' ').trim())")
        check("row labels in rank order, Other last", labels[0] == "1 FRZ-12 freezer" and labels[1] == "2 WFI-LOOP-1 water loop"
              and labels[2] == "3 CH-2-P3 chiller pump" and labels[-1].startswith("Other ("), str(labels))
        # Labels line up with the row lines
        align = page.evaluate("""() => {
          const gd=document.querySelector('.st-key-baton-timeline .js-plotly-plot'), ya=gd._fullLayout.yaxis, r=gd.getBoundingClientRect();
          return [...document.querySelectorAll('.baton-tl-label')].map((l,i)=>{const b=l.getBoundingClientRect();
            return Math.abs((b.top+b.bottom)/2-(r.top+ya._offset+ya.l2p(i)))})}""")
        check("labels line up with chart rows (<3px)", max(align) < 3, str(align))
        check("no Plotly legend", page.evaluate("document.querySelector('.st-key-baton-timeline .js-plotly-plot')._fullLayout.showlegend") is False)
        legend = page.inner_text(".baton-legend").replace("\n", " · ")
        check("legend text", all(t in legend for t in ["Alert", "Alert after a note said it was fine", "Note written", "Said fine, kept alerting"]), legend)
        check("handover label", "Handover 07:00" in page.inner_text(".st-key-baton-timeline"))
        ticks = page.eval_on_selector_all(".st-key-baton-timeline .xtick text", "e=>e.map(x=>x.textContent)")
        check("ticks every 2h from 19:00 to 07:00", ticks == ["19:00","21:00","23:00","01:00","03:00","05:00","07:00"], str(ticks))
        lab = page.get_by_text("Handover", exact=True).first.bounding_box()
        check("top label clear of the Streamlit header", lab["y"] >= 60, str(lab))
        check("amber band drawn", page.locator(".js-plotly-plot .barlayer .point").count() >= 2)
        # Hover
        box = page.evaluate("""() => {const gd=document.querySelector('.st-key-baton-timeline .js-plotly-plot'), xa=gd._fullLayout.xaxis, ya=gd._fullLayout.yaxis, r=gd.getBoundingClientRect();
           return {x:r.left+xa._offset+xa.d2p('2026-11-07 04:58:33'), y:r.top+ya._offset+ya.l2p(1)}}""")
        page.mouse.move(box["x"], box["y"])
        page.wait_for_timeout(300)
        hover = page.locator(".st-key-baton-timeline .js-plotly-plot .hoverlayer").text_content()
        check("hover shows exact time and message", "04:58:33" in hover and "Conductivity 1.4" in hover, hover)
        page.mouse.move(5, 5)
        page.screenshot(path=SHOTS / "1-top.png")

        # Tags, key
        chips = page.eval_on_selector_all(".hc-chip", "e=>e.map(x=>[x.className, getComputedStyle(x).backgroundColor, !!x.querySelector('svg')])")
        check("every chip has an icon (svg survives markdown)", all(c[2] for c in chips))
        check("only clash chips are filled", all((c[1] != "rgba(0, 0, 0, 0)") == ("clash" in c[0]) for c in chips), str(chips[:4]))

        # Progress + bars
        check("5 segments", page.locator(".baton-seg").count() == 5)
        check("caption", page.inner_text(".baton-progress-caption") == "0 of 5 handled")
        check("bars only on readings with limits", page.locator(".baton-limit").count() == 3)
        text = page.eval_on_selector_all(".baton-limit-text", "e=>e.map(x=>x.innerText)")
        check("bar text", "8.1 / 9.0 mm/s" in text and "-61.9 / -70.0 °C" in text, str(text))
        red = page.evaluate("""() => [...document.querySelectorAll('.baton-limit')].map(l=>[l.innerText, getComputedStyle(l.querySelector('.baton-limit-fill')).backgroundColor])""")
        check("fill red only over limit", all(("198, 40, 40" in c) == (not t.startswith("8.1")) for t, c in red), str(red))
        check("warning tick on chiller only", page.locator(".baton-limit-tick.warn").count() == 1)

        # Card hover border
        card = page.locator("div[class*='st-key-baton-card-night-BAL-03']")
        before = card.evaluate("e=>[getComputedStyle(e).borderTopColor,getComputedStyle(e).borderTopWidth,getComputedStyle(e).transitionDuration]")
        card.hover()
        page.wait_for_timeout(300)
        after = card.evaluate("e=>getComputedStyle(e).borderTopColor")
        check("card has a real border and a 150ms transition", before[1] != "0px" and "0.15s" in before[2], str(before))
        check("card border stronger on hover", before[0] != after, f"{before[0]} -> {after}")
        check("note hover transition", "0.15s" in page.locator(".hc-note").first.evaluate("e=>getComputedStyle(e).transitionDuration"))

        # Jump: label
        page.locator("a.baton-tl-label", has_text="HPLC-07").click()
        page.wait_for_timeout(250)
        check("label sets the anchor", page.url.endswith("#card-HPLC-07"), page.url)
        flash = page.locator("div[class*='st-key-baton-card-night-HPLC-07']").evaluate("e=>getComputedStyle(e).animationName")
        check("target card flashes", flash == "baton-flash", flash)
        page.wait_for_timeout(1100)
        vis = page.evaluate("(()=>{const r=document.getElementById('card-HPLC-07').getBoundingClientRect();return r.top>=0&&r.top<innerHeight})()")
        check("label scrolls to the card", vis)
        page.screenshot(path=SHOTS / "2-jump.png")
        scroller = page.evaluate("""() => {const s=document.querySelector('[data-testid="stMain"]'); return [getComputedStyle(s).scrollBehavior, s.scrollTop]}""")
        check("smooth scroll on the real scroller", scroller[0] == "smooth", str(scroller))

        # Jump: click in a chart row
        page.evaluate("""() => document.querySelector('[data-testid="stMain"]').scrollTo({top:0,behavior:'instant'})""")
        page.wait_for_timeout(300)
        pos = page.evaluate("""() => {const gd=document.querySelector('.st-key-baton-timeline .js-plotly-plot'), xa=gd._fullLayout.xaxis, ya=gd._fullLayout.yaxis, r=gd.getBoundingClientRect();
           return {x:r.left+xa._offset+xa.d2p('2026-11-06 20:00'), y:r.top+ya._offset+ya.l2p(2)}}""")
        page.mouse.click(pos["x"], pos["y"])
        page.wait_for_timeout(1200)
        check("chart row click jumps to its card", page.url.endswith("#card-CH-2-P3"), page.url)

        # Entrance only once, fragment reruns
        full_before = renders()
        got_it(page, "FRZ-12")
        check("a response re-runs only the section", renders() == full_before, f"{full_before} -> {renders()}")
        slim = page.inner_text(".baton-slim")
        check("slim row text", slim.startswith("✓ FRZ-12 · Got it · "), slim)
        check("slim row is one line", page.locator(".baton-slim").evaluate("e=>e.getBoundingClientRect().height") < 30)
        mid = page.evaluate("""() => {const m=e=>{const r=e.getBoundingClientRect();return (r.top+r.bottom)/2}; return Math.abs(m(document.querySelector('.baton-slim'))-m(document.querySelector('.st-key-open-night-FRZ-12 button')))}""")
        check("slim text lines up with its button", mid < 4, str(mid))
        check("caption after one", page.inner_text(".baton-progress-caption") == "1 of 5 handled · 1 got it")
        check("segment green with tick", page.locator(".baton-seg.got_it svg").count() == 1)
        check("no sign-off yet", page.locator(".st-key-signoff-night").count() == 0)
        names = page.evaluate("[...document.querySelectorAll('div[class*=\"st-key-baton-card-\"]')].map(e=>getComputedStyle(e).animationName)")
        check("entrance does not replay", all(n in ("none", "baton-flash") for n in names), str(names))
        page.screenshot(path=SHOTS / "3-one-done.png")

        # just_changed moves
        got_it(page, "WFI-LOOP-1")
        anim = page.eval_on_selector_all(".baton-slim", "e=>e.map(x=>x.innerText.split(' · ')[0]+':'+getComputedStyle(x).animationName)")
        check("only the newest slim row animates", anim == ["✓ FRZ-12:none", "✓ WFI-LOOP-1:baton-done"], str(anim))
        check("only one segment animates", page.locator(".baton-seg-new").count() == 1)

        # Dismiss through the form, inside the fragment
        full_before = renders()
        page.locator(".st-key-dis-night-HPLC-07 button").click()
        page.wait_for_selector(".st-key-expiry-night-HPLC-07", timeout=20000)
        settle(page)
        page.get_by_role("button", name="Save dismissal").click()
        page.wait_for_selector(".st-key-open-night-HPLC-07", timeout=30000)
        settle(page)
        check("dismiss form stays inside the section", renders() == full_before)
        check("dismissed segment dashed with minus", page.locator(".baton-seg.dismissed svg").count() == 1
              and page.locator(".baton-seg.dismissed").evaluate("e=>getComputedStyle(e).borderTopStyle") == "dashed")

        # Draft stays open until closed
        page.locator(".st-key-draft-night-CH-2-P3 button").click()
        page.wait_for_selector("text=DRAFT TICKET", timeout=30000)
        settle(page)
        check("drafted ticket stays visible", page.locator("text=DRAFT TICKET").count() >= 1)
        check("ticket segment has an icon", page.locator(".baton-seg.ticket_drafted svg").count() == 1)
        page.locator(".st-key-draft-night-CH-2-P3 button").click()
        page.wait_for_selector(".st-key-open-night-CH-2-P3", timeout=30000)
        settle(page)
        cap = page.inner_text(".baton-progress-caption")
        check("mixed caption", cap == "4 of 5 handled · 2 got it · 1 dismissed · 1 ticket drafted", cap)

        # Reopen
        page.locator(".st-key-open-night-FRZ-12 button").click()
        page.wait_for_selector(".st-key-got-night-FRZ-12", timeout=30000)
        settle(page)
        check("reopened card shows evidence", page.locator("div[class*='st-key-baton-card-night-FRZ-12']").get_by_text("Evidence").count() == 1)
        page.locator(".st-key-collapse-night-FRZ-12 button").click()
        page.wait_for_selector(".st-key-open-night-FRZ-12", timeout=30000)
        settle(page)

        # Fifth → sign-off fades in
        page.locator(".st-key-got-night-BAL-03 button").click()
        page.wait_for_selector(".st-key-signoff-night", timeout=30000)
        check("sign-off fades in on the fifth", page.locator(".st-key-baton-signoff").evaluate("e=>getComputedStyle(e).animationName") == "baton-in")
        settle(page)
        page.locator(".st-key-baton-signoff").scroll_into_view_if_needed()
        page.screenshot(path=SHOTS / "4-all-done.png")
        check("sign-off sits above the lower lists", page.evaluate("""() => {
           const s=document.querySelector('.st-key-baton-signoff').getBoundingClientRect();
           const e=[...document.querySelectorAll('[data-testid="stExpander"]')].pop().getBoundingClientRect(); return s.top<e.top}"""))
        page.locator(".st-key-signoff-night button").click()
        try:
            page.wait_for_selector(".hc-banner.done", timeout=20000)
        except Exception:
            page.screenshot(path=SHOTS / "signoff-fail.png", full_page=True)
        settle(page)
        check("signing off works", "read-only" in page.inner_text("body"), page.inner_text(".st-key-baton-signoff")[:200])
        check("no page errors", not errors, str(errors))
        check("no exception box", page.locator('[data-testid="stException"]').count() == 0)
        ctx.close()

        # Intro animation on first load
        ctx = b.new_context(viewport={"width": 1400, "height": 950})
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_function("document.querySelectorAll('div[class*=st-key-baton-card-night-]').length >= 5", timeout=60000)
        intro = page.evaluate("""() => [...document.querySelectorAll('div[class*="st-key-baton-card-"]')].map(e=>[getComputedStyle(e).animationName,getComputedStyle(e).animationDelay])""")
        check("entrance runs on first load, staggered 50ms", intro[0] == ["baton-in", "0.05s"] and intro[1] == ["baton-in", "0.1s"], str(intro[:2]))
        check("progress bar enters first", page.locator(".baton-segments.baton-enter").count() == 1)
        ctx.close()

        # Dark, phone, reduced motion, day shift
        for name, kw in [("day-switch", dict(viewport={"width": 1400, "height": 950})),
                         ("phone", dict(viewport={"width": 390, "height": 844}, color_scheme="light")),
                         ("reduced", dict(viewport={"width": 1400, "height": 950}, reduced_motion="reduce"))]:
            ctx = b.new_context(**kw)
            page = ctx.new_page()
            page.goto(URL)
            page.wait_for_selector(".baton-tl-label", timeout=60000)
            page.wait_for_selector(".js-plotly-plot .scatterlayer", timeout=30000)
            settle(page)
            over = page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
            check(f"{name}: no sideways page scroll", over <= 0, str(over))
            if name == "phone":
                align = page.evaluate("""() => {
                  const gd=document.querySelector('.st-key-baton-timeline .js-plotly-plot'), ya=gd._fullLayout.yaxis, r=gd.getBoundingClientRect();
                  return [...document.querySelectorAll('.baton-tl-label')].map((l,i)=>{const b=l.getBoundingClientRect();
                    return Math.abs((b.top+b.bottom)/2-(r.top+ya._offset+ya.l2p(i)))})}""")
                check("phone: labels still line up", max(align) < 3, str(align))
                check("phone: chart has real width", page.evaluate("document.querySelector('.st-key-baton-timeline .js-plotly-plot').getBoundingClientRect().width") > 150)
            if name == "reduced":
                vals = page.evaluate("""() => {const c=document.querySelector('.baton-seg'),m=document.querySelector('[data-testid="stMain"]');
                   return [getComputedStyle(c).animationName,getComputedStyle(document.querySelector('.hc-note')).transitionDuration,getComputedStyle(m).scrollBehavior]}""")
                check("reduced motion turns everything off", vals[0] == "none" and vals[1] in ("0s", "") and vals[2] == "auto", str(vals))
            page.screenshot(path=SHOTS / f"5-{name}.png", full_page=name != "phone")
            if name == "day-switch":
                page.get_by_text("Sat 19:00 handover").click()
                page.wait_for_function("document.querySelector('.hc-header h1').innerText.includes('19:00')", timeout=30000)
                page.wait_for_selector(".js-plotly-plot .scatterlayer", timeout=30000)
                settle(page)
                check("day shift subtitle", " · day shift" in page.inner_text(".hc-sub"), page.inner_text(".hc-sub"))
                check("day handover label", "Handover 19:00" in page.inner_text(".st-key-baton-timeline"))
                check("day: no exception", page.locator('[data-testid="stException"]').count() == 0)
                page.screenshot(path=SHOTS / "6-day.png", full_page=True)
            ctx.close()
        b.close()
finally:
    proc.terminate()

print(f"\n{len(fails)} failed" if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
