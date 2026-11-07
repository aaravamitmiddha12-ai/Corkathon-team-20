"""Responsive and reactive checks for Baton in a real browser: every width with the sidebar open and shut, live
resizing, linked hover, the live label state, and touch sizes. Port 8766.

    BATON_CHANNEL=msedge  <playwright venv>/python handoff/check_reactive.py
"""
import os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("BATON_REPO_DIR", HERE.parent))
SHOTS = Path(os.environ.get("BATON_SHOTS", Path(tempfile.gettempdir()) / "baton-checks")) / "reactive"
SHOTS.mkdir(parents=True, exist_ok=True)
CHANNEL = os.environ.get("BATON_CHANNEL", "chrome")
WIDTHS = [320, 360, 390, 600, 768, 900, 1024, 1280, 1400, 1920]
PORT = 8766
URL = f"http://127.0.0.1:{PORT}/"
LOG = Path(tempfile.mkdtemp()) / "renders.log"
LOG.write_text("")
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if not ok else ""), flush=True)
    if not ok:
        fails.append(name)


def start():
    env = dict(os.environ, PYTHONUTF8="1", PYTHONPATH=str(REPO), BATON_REPO=str(REPO), BATON_RENDER_LOG=str(LOG),
               HANDOVER_STATE_DIR=tempfile.mkdtemp(prefix="baton-state-"))
    proc = subprocess.Popen([str(REPO / ".venv/Scripts/python.exe"), "-m", "streamlit", "run", str(HERE / "baton_launcher.py"),
                             "--server.port", str(PORT), "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                            cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        try:
            urllib.request.urlopen(f"{URL}_stcore/health", timeout=1)
            return proc
        except Exception:
            time.sleep(1)
    raise SystemExit("server did not start")


def settle(page, extra=500):
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=30000)
    page.wait_for_timeout(extra)


def open_home(ctx):
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL)
    page.wait_for_selector(".baton-tl-label", timeout=90000)
    page.wait_for_selector(".st-key-baton-timeline .js-plotly-plot .scatterlayer", timeout=30000)
    settle(page, 800)
    return page


ALIGN = """() => {const gd=document.querySelector('.st-key-baton-timeline .js-plotly-plot'), ya=gd._fullLayout.yaxis, r=gd.getBoundingClientRect();
  return [...document.querySelectorAll('.st-key-baton-timeline .baton-tl-label')].map((l,i)=>{const b=l.getBoundingClientRect();
    return Math.round(Math.abs((b.top+b.bottom)/2-(r.top+ya._offset+ya.l2p(i)))*10)/10})}"""

LAYOUT = """() => {
  const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)], R=e=>e.getBoundingClientRect();
  const gd=q('.st-key-baton-timeline .js-plotly-plot'), col=gd.closest('[data-testid="stColumn"]');
  const ticks=qa('.st-key-baton-timeline .xtick text').filter(t=>getComputedStyle(t).visibility!=='hidden').map(t=>R(t));
  const gr=R(gd), allTicks=qa('.st-key-baton-timeline .xtick text');
  const tickBad=allTicks.filter(t=>(t.getAttribute('transform')||'').includes('rotate') || (getComputedStyle(t).visibility!=='hidden' && (R(t).bottom>gr.bottom+1 || R(t).left<gr.left-1 || R(t).right>gr.right+1))).map(t=>t.textContent);
  let tickHit=false; for(let i=1;i<ticks.length;i++) if(ticks[i].left<ticks[i-1].right+2) tickHit=true;
  const ids=qa('.st-key-baton-timeline .baton-tl-id').map(e=>[e.innerText, e.scrollWidth>e.clientWidth+1]);
  const main=qa('.st-key-baton-main > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]').map(R);
  const top=qa('.st-key-baton-top [data-testid="stColumn"]').filter(c=>getComputedStyle(c).display!=='none').map(R);
  const btn=q('.st-key-open-before-you-go button'); const bt=btn?R(btn):null;
  const h1=getComputedStyle(q('.hc-header h1')).fontSize;
  // Anything poking out past the main pane's right edge (other than in a scroll box).
  const pane=R(q('[data-testid="stMain"]'));
  const sticking=qa('.hc-chip, .baton-limit, .baton-limit-text, .hc-due, [data-testid^="stBaseButton-"], .baton-seg, .baton-legend span, .hc-key')
     .filter(e=>R(e).width>0 && R(e).right>pane.right+1).map(e=>e.className||e.dataset.testid).slice(0,5);
  const segs=qa('.baton-seg').map(e=>Math.round(R(e).width));
  return {over:document.documentElement.scrollWidth-document.documentElement.clientWidth,
          mainOver:q('[data-testid="stMain"]').scrollWidth-q('[data-testid="stMain"]').clientWidth,
          chartW:Math.round(R(gd).width), colW:Math.round(R(col).width), tickHit, tickBad, ticks:ticks.length, idCut:ids.filter(i=>i[1]).map(i=>i[0]),
          stacked: main.length===2 && main[1].top>=main[0].bottom-1, mainW:Math.round(pane.width),
          topRows:new Set(top.map(r=>Math.round(r.top))).size, btnH:bt?Math.round(bt.height):0, btnLines:btn?Math.round(bt.height/22):0,
          h1, sticking, segs};
}"""


def layout_checks(page, tag):
    lay = page.evaluate(LAYOUT)
    align = page.evaluate(ALIGN)
    check(f"{tag}: page never scrolls sideways", lay["over"] <= 0 and lay["mainOver"] <= 0, f"{lay['over']}/{lay['mainOver']}")
    check(f"{tag}: labels line up with rows (<3px)", max(align) < 3, str(align))
    check(f"{tag}: chart fills its column", abs(lay["chartW"] - lay["colW"]) <= 2 and lay["chartW"] > 120, f"{lay['chartW']} in {lay['colW']}")
    check(f"{tag}: timeline ticks don't collide", not lay["tickHit"], str(lay["ticks"]))
    check(f"{tag}: timeline times level and inside the chart", not lay["tickBad"], str(lay["tickBad"]))
    check(f"{tag}: asset ids never truncated", not lay["idCut"], str(lay["idCut"]))
    check(f"{tag}: nothing sticks out of the pane", not lay["sticking"], str(lay["sticking"]))
    segs = lay["segs"]
    check(f"{tag}: progress segments equal width", max(segs) - min(segs) <= 1 and min(segs) >= 40, str(segs))
    if lay["mainW"] < 960:
        check(f"{tag}: notes and list stacked on a {lay['mainW']}px pane", lay["stacked"])
    else:
        check(f"{tag}: notes and list side by side on a {lay['mainW']}px pane", not lay["stacked"])
    return lay


errors = []
proc = start()
try:
    with sync_playwright() as p:
        b = p.chromium.launch(channel=CHANNEL)

        # ---------- every width (from 1024px the sidebar takes 240px of it; below, it's a closed drawer) ----------
        for w in WIDTHS:
            ctx = b.new_context(viewport={"width": w, "height": 900})
            page = open_home(ctx)
            lay = layout_checks(page, str(w))
            side = page.evaluate("""() => {const r=document.querySelector('[data-testid=stSidebar]').getBoundingClientRect(), m=document.querySelector('[data-testid=stMain]').getBoundingClientRect();
                return {right: Math.round(r.right), w: Math.round(r.width), main: Math.round(m.left), bar: Math.round(document.querySelector('.st-key-baton-topbar').getBoundingClientRect().height)}}""")
            if w >= 1024:
                check(f"{w}: 240px sidebar beside the page, no top bar", side["w"] == 240 and side["main"] >= 239 and side["bar"] == 0, str(side))
            else:
                check(f"{w}: sidebar closed, 56px top bar instead", side["right"] <= 0 and side["main"] == 0 and side["bar"] == 56, str(side))
            page.screenshot(path=SHOTS / f"w{w}-top.png")
            ticks = page.eval_on_selector_all(".st-key-baton-timeline .xtick text",
                                              "e=>e.filter(t=>getComputedStyle(t).visibility!=='hidden').map(t=>t.textContent)")
            if w >= 1024:
                check(f"{w}: desktop keeps every 2-hour tick", len(ticks) == 7, str(ticks))
            # One card handled and an evidence box open, then the cards area.
            page.locator(".st-key-got-night-FRZ-12 button").click() if page.locator(".st-key-got-night-FRZ-12").count() else None
            page.wait_for_selector(".st-key-open-night-FRZ-12", timeout=30000)
            settle(page)
            slim = page.evaluate("""() => {const t=document.querySelector('.baton-slim').getBoundingClientRect(), b=document.querySelector('.st-key-open-night-FRZ-12 button').getBoundingClientRect();
                return {sameRow: b.top < t.bottom && b.bottom > t.top, btnW: Math.round(b.width), over: document.documentElement.scrollWidth-document.documentElement.clientWidth}}""")
            check(f"{w}: Open stays on the slim row", slim["sameRow"] and slim["btnW"] >= 28, str(slim))
            exp = page.locator("div[class*='st-key-baton-card-night-WFI-LOOP-1'] [data-testid='stExpander'] summary")
            exp.click()
            page.wait_for_timeout(600)
            box = page.evaluate("""() => {const c=document.querySelector("div[class*='st-key-baton-card-night-WFI-LOOP-1']"), t=c.querySelector('.baton-table-box');
                const cr=c.getBoundingClientRect(), tr=t.getBoundingClientRect(); const ch=c.querySelector('.js-plotly-plot');
                return {inside: tr.right<=cr.right+1, scrolls: getComputedStyle(t).overflowX, chart: ch? ch.getBoundingClientRect().right<=cr.right+1 : true,
                        over: document.documentElement.scrollWidth-document.documentElement.clientWidth}}""")
            check(f"{w}: evidence table stays in its card and scrolls itself", box["inside"] and box["scrolls"] == "auto" and box["chart"] and box["over"] <= 0, str(box))
            page.locator("div[class*='st-key-baton-card-night-WFI-LOOP-1']").scroll_into_view_if_needed()
            page.locator(".st-key-baton-card-night-FRZ-12").scroll_into_view_if_needed()
            page.screenshot(path=SHOTS / f"w{w}-cards.png")
            ctx.close()

        # ---------- live resize, no reload ----------
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        page = open_home(ctx)
        for w in (390, 900, 1920, 600, 1280):
            page.set_viewport_size({"width": w, "height": 900})
            page.wait_for_timeout(900)
            lay = page.evaluate(LAYOUT)
            align = page.evaluate(ALIGN)
            check(f"live resize to {w}: chart re-fits and labels line up",
                  abs(lay["chartW"] - lay["colW"]) <= 2 and max(align) < 3 and lay["over"] <= 0, f"{lay['chartW']}/{lay['colW']} {align}")
        page.set_viewport_size({"width": 1100, "height": 900}); page.wait_for_timeout(900)
        a1 = page.evaluate(LAYOUT)
        page.set_viewport_size({"width": 1000, "height": 900}); page.wait_for_timeout(900)
        a2 = page.evaluate(LAYOUT)
        check("crossing 1024px: the sidebar becomes a drawer and the chart re-fits", abs(a1["chartW"] - a1["colW"]) <= 2
              and abs(a2["chartW"] - a2["colW"]) <= 2 and a2["chartW"] > a1["chartW"], f"{a1['chartW']}/{a1['colW']} -> {a2['chartW']}/{a2['colW']}")
        ctx.close()

        # ---------- linked hover, focus, tooltips, clicks ----------
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        page = open_home(ctx)
        hot = "() => [...document.querySelectorAll('.st-key-baton-timeline .baton-tl-label')].map(e=>e.classList.contains('baton-tl-hot'))"
        bands = "() => [...document.querySelectorAll('.baton-tl-band')].map(e=>[e.classList.contains('baton-tl-hot'), getComputedStyle(e).backgroundColor])"
        page.locator("a.baton-tl-label").nth(1).hover()
        page.wait_for_timeout(300)
        h, bd = page.evaluate(hot), page.evaluate(bands)
        check("hovering a label lights it and its chart row only", h[1] and sum(h) == 1 and bd[1][0] and sum(x[0] for x in bd) == 1, f"{h} {bd}")
        check("highlight is neutral, not amber", "232, 163, 61" not in bd[1][1] and bd[1][1] != "rgba(0, 0, 0, 0)", bd[1][1])
        dur = page.evaluate("getComputedStyle(document.querySelector('.baton-tl-band')).transitionDuration")
        check("highlight sweeps across the row in 250ms", dur.startswith("0.25s"), dur)
        pos = page.evaluate("""() => {const gd=document.querySelector('.st-key-baton-timeline .js-plotly-plot'), xa=gd._fullLayout.xaxis, ya=gd._fullLayout.yaxis, r=gd.getBoundingClientRect();
           return {x:r.left+xa._offset+xa.d2p('2026-11-07 04:58:33'), y:r.top+ya._offset+ya.l2p(1), x2:r.left+xa._offset+xa.d2p('2026-11-06 20:00'), y2:r.top+ya._offset+ya.l2p(2)}}""")
        page.mouse.move(pos["x2"], pos["y2"])
        page.wait_for_timeout(300)
        h = page.evaluate(hot)
        check("hovering a chart row lights its label", h[2] and sum(h) == 1, str(h))
        page.mouse.move(pos["x"], pos["y"])
        page.wait_for_timeout(400)
        tip = page.locator(".st-key-baton-timeline .hoverlayer").text_content()
        check("Plotly tooltip still shows under linked hover", "04:58:33" in tip, tip)
        page.mouse.move(5, 500)
        page.wait_for_timeout(300)
        check("leaving the timeline clears the highlight", not any(page.evaluate(hot)))
        page.locator("a.baton-tl-label").first.focus()
        page.keyboard.press("Tab")
        page.wait_for_timeout(300)
        h = page.evaluate(hot)
        check("keyboard focus lights the focused label", h[1] and sum(h) == 1, str(h))
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)
        check("Enter on a focused label jumps to its card", page.url.endswith("#card-WFI-LOOP-1"), page.url)
        page.screenshot(path=SHOTS / "hover-focus.png")
        ctx.close()

        # ---------- live label state without re-running the timeline ----------
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        page = open_home(ctx)
        tick = """a => {const l=document.querySelector(`.st-key-baton-timeline a.baton-tl-label[href="#card-${a}"]`);
            return [getComputedStyle(l.querySelector('.baton-tl-rank'),'::before').content, getComputedStyle(l.querySelector('.baton-tl-id')).opacity,
                    l.querySelector('.baton-tl-rank').getBoundingClientRect().width]}"""
        state0 = page.evaluate(tick, "BAL-03")
        check("unhandled label: rank, no tick", state0[0] in ("none", "normal") and state0[1] == "1", str(state0))
        page.evaluate("document.querySelector('.st-key-baton-timeline .js-plotly-plot').dataset.mark='same'")
        before = LOG.read_text().count("full")
        page.locator(".st-key-got-night-BAL-03 button").click()
        page.wait_for_selector(".st-key-open-night-BAL-03", timeout=30000)
        settle(page)
        s = page.evaluate(tick, "BAL-03")
        check("handled: label shows a tick and is muted", s[0] == '"✓"' and float(s[1]) < 1, str(s))
        check("handled: rank slot keeps its width", abs(s[2] - state0[2]) < 0.5, f"{state0[2]} -> {s[2]}")
        check("handled: timeline not re-run", LOG.read_text().count("full") == before
              and page.evaluate("document.querySelector('.st-key-baton-timeline .js-plotly-plot').dataset.mark") == "same")
        page.locator(".st-key-open-night-BAL-03 button").click()
        page.wait_for_selector(".st-key-got-night-BAL-03", timeout=30000)
        settle(page)
        s = page.evaluate(tick, "BAL-03")
        check("reopened: tick stays, no longer muted", s[0] == '"✓"' and s[1] == "1", str(s))
        page.locator(".st-key-dis-night-BAL-03 button").click()
        page.wait_for_selector(".st-key-expiry-night-BAL-03", timeout=20000)
        settle(page)
        page.get_by_role("button", name="Save dismissal").click()
        page.wait_for_selector(".st-key-open-night-BAL-03", timeout=30000)
        settle(page)
        s = page.evaluate(tick, "BAL-03")
        check("response changed to dismiss: tick and muted again", s[0] == '"✓"' and float(s[1]) < 1, str(s))
        page.get_by_test_id("stRadioGroup").get_by_text("Sat 19:00").click()
        page.wait_for_function("document.querySelector('.hc-header h1').innerText.includes('19:00')", timeout=30000)
        settle(page, 900)
        day = page.evaluate("""() => [...document.querySelectorAll('.st-key-baton-timeline a.baton-tl-label .baton-tl-rank')]
             .map(r=>getComputedStyle(r,'::before').content)""")
        check("day shift: no ticks carried over", all(c in ("none", "normal") for c in day), str(day))
        page.get_by_test_id("stRadioGroup").get_by_text("Sat 07:00").click()
        page.wait_for_function("document.querySelector('.hc-header h1').innerText.includes('07:00')", timeout=30000)
        settle(page, 900)
        s = page.evaluate(tick, "BAL-03")
        check("back to night: tick is there", s[0] == '"✓"', str(s))
        page.reload()
        page.wait_for_selector(".baton-tl-label", timeout=60000)
        settle(page, 900)
        s = page.evaluate(tick, "BAL-03")
        check("after a reload: tick is there", s[0] == '"✓"', str(s))
        page.get_by_label("Incoming engineer").fill("Someone Else")
        page.get_by_label("Incoming engineer").press("Enter")
        settle(page, 900)
        s = page.evaluate(tick, "BAL-03")
        names = page.evaluate("[...document.querySelectorAll('div[class*=\"st-key-baton-card-\"]')].map(e=>getComputedStyle(e).animationName)")
        check("full rerun (name edit): tick stays, nothing re-animates", s[0] == '"✓"' and all(n in ("none", "baton-flash") for n in names), f"{s} {names}")
        page.screenshot(path=SHOTS / "live-state.png")
        ctx.close()

        # ---------- listeners bound once, however many reruns ----------
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        ctx.add_init_script("""(() => {window.__pm=0; const add=EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener=function(t,...r){ if(t==='pointermove' && this===document) window.__pm++; return add.call(this,t,...r)}})()""")
        page = open_home(ctx)
        first = page.evaluate("window.__pm")
        for a in ("WFI-LOOP-1", "CH-2-P3"):
            page.locator(f".st-key-got-night-{a} button").click()
            page.wait_for_selector(f".st-key-open-night-{a}", timeout=30000)
            settle(page)
        for label in ("Sat 19:00", "Sat 07:00"):
            page.get_by_test_id("stRadioGroup").get_by_text(label).click()
            settle(page, 900)
        frames = page.evaluate("window.frames.length")
        check("hover listener bound once", page.evaluate("window.__pm") == first, f"{first} -> {page.evaluate('window.__pm')}")
        ctx.close()

        # ---------- touch ----------
        ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
        page = open_home(ctx)
        small = page.evaluate("""() => [...document.querySelectorAll('[data-testid^="stBaseButton-"], .st-key-baton-timeline a.baton-tl-label, [data-testid="stExpander"] summary')]
            .filter(e=>e.getBoundingClientRect().width>0).map(e=>[e.innerText.slice(0,20), Math.round(e.getBoundingClientRect().height)]).filter(x=>x[1]<44)""")
        check("touch: every target at least 44px tall", not small, str(small))
        over = page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
        check("touch phone: no sideways scroll", over <= 0, str(over))
        page.screenshot(path=SHOTS / "touch-390.png", full_page=True)
        ctx.close()

        # ---------- sidebar, drawer, scroll-spy, reading progress, Back to top, both themes ----------
        def lum(rgb):
            v = [(c / 255 / 12.92) if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
            return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]

        def contrast(a, b):
            hi, lo = sorted((lum(a), lum(b)), reverse=True)
            return (hi + 0.05) / (lo + 0.05)

        def rgb(css):
            return [float(x) for x in css[css.index("(") + 1:css.index(")")].split(",")[:3]]

        def scroll_to(page, y):
            page.evaluate(f"document.querySelector('[data-testid=stMain]').scrollTo({{top: {y}, behavior: 'instant'}})")
            page.wait_for_timeout(400)

        NAV = """() => {const q=s=>document.querySelector(s), R=e=>e.getBoundingClientRect(), m=q('[data-testid=stMain]'), ind=q('.baton-nav-indicator');
          const act=q('.baton-nav-link.baton-active');
          return {active: act ? act.getAttribute('data-sec') : null, indY: ind ? Math.round(new DOMMatrix(getComputedStyle(ind).transform).m42) : null,
            actY: act ? act.offsetTop : null, indDur: ind ? getComputedStyle(ind).transitionDuration : '',
            read: (()=>{const r=q('.baton-read'); return r ? new DOMMatrix(getComputedStyle(r).transform).a : null})(),
            readLeft: Math.round(R(q('.baton-read')).left), mainLeft: Math.round(R(m).left),
            back: q('.baton-back').classList.contains('baton-show'), backOp: getComputedStyle(q('.baton-back')).opacity,
            scroll: Math.round(m.scrollTop), vh: m.clientHeight}}"""
        STYLE = """() => {const q=s=>document.querySelector(s), c=e=>getComputedStyle(e);
          const h1=q('.hc-header h1'), sub=q('.hc-sub'), eb=[...document.querySelectorAll('.baton-eyebrow')], side=q('[data-testid=stSidebar]');
          const col=q('[data-testid=stMainBlockContainer]'); const pad=parseFloat(c(col).paddingLeft)+parseFloat(c(col).paddingRight);
          return {h1:[c(h1).fontSize, c(h1).fontWeight, c(h1).letterSpacing, c(h1).color], sub:[c(sub).fontSize, c(sub).color],
            eyebrows:eb.map(e=>e.innerText), ebFont:c(eb[0]).fontFamily, ebCase:c(eb[0]).textTransform,
            content:Math.round(col.getBoundingClientRect().width-pad), bg:c(q('[data-testid=stApp]')).backgroundColor,
            muted:c(q('.hc-due') || q('.baton-progress-caption')).color, scheme:c(q('[data-testid=stApp]')).colorScheme,
            primary:(()=>{const b=q('[data-testid=stBaseButton-primary]'); return b?[c(b).backgroundColor,c(b).color]:null})(),
            card:(()=>{const k=q('div[class*="st-key-baton-card-"]'); return [c(k).boxShadow, c(k).borderRadius]})(),
            banner:c(q('.hc-banner')).backgroundColor, sideBg:c(side).backgroundColor, sideBorder:[c(side).borderRightWidth, c(side).borderRightColor],
            navMuted:c(q('.baton-nav-link:not(.baton-active)')).color, sideW:Math.round(side.getBoundingClientRect().width),
            logoH:Math.round(q('[data-testid=stSidebar] .baton-logo svg').getBoundingClientRect().height),
            arrow:getComputedStyle(q('.st-key-open-before-you-go button p'),'::after').content}}"""
        for scheme in ("light", "dark"):
            ctx = b.new_context(viewport={"width": 1920, "height": 1000}, color_scheme=scheme)
            page = open_home(ctx)
            st = page.evaluate(STYLE)
            check(f"{scheme}: theme follows the computer", st["scheme"] == scheme, st["scheme"])
            check(f"{scheme}: hero 48px, heavy, tight", st["h1"][0] == "48px" and int(st["h1"][1]) >= 700 and st["h1"][2].startswith("-"), str(st["h1"]))
            check(f"{scheme}: subtitle smaller and muted", float(st["sub"][0][:-2]) < 48 and st["sub"][1] != st["h1"][3], str(st["sub"]))
            check(f"{scheme}: section labels 01-05 in order, mono uppercase",
                  [e.split(" · ")[0] for e in st["eyebrows"] if " · " in e] == ["01", "02", "03", "04", "05"]
                  and "mono" in st["ebFont"].lower() and st["ebCase"] == "uppercase", str(st["eyebrows"]))
            check(f"{scheme}: content capped at 1200px", st["content"] <= 1200, str(st["content"]))
            check(f"{scheme}: banner is a hairline, not a filled box", st["banner"] in ("rgba(0, 0, 0, 0)", "transparent"), st["banner"])
            check(f"{scheme}: cards have a soft shadow and a 12px radius", st["card"][0] != "none" and st["card"][1] == "12px", str(st["card"]))
            check(f"{scheme}: sidebar 240px, off-white/off-black, 1px right border, 45px logo",
                  st["sideW"] == 240 and st["sideBg"] != st["bg"] and st["sideBorder"][0] == "1px" and st["logoH"] == 45, str(st))
            check(f"{scheme}: Before you go button has its arrow", st["arrow"] == '"→"', st["arrow"])
            bg = rgb(st["bg"])
            check(f"{scheme}: background {'dark' if scheme == 'dark' else 'light'}", (lum(bg) < 0.05) == (scheme == "dark"), st["bg"])
            for name, colour, on, need in [("hero text", st["h1"][3], st["bg"], 7), ("muted text", st["muted"], st["bg"], 4.5),
                                           ("sidebar nav text", st["navMuted"], st["sideBg"], 4.5)]:
                c = contrast(rgb(colour), rgb(on))
                check(f"{scheme}: {name} contrast {c:.1f}:1 >= {need}", c >= need, colour)
            c = contrast(rgb(st["primary"][0]), rgb(st["primary"][1]))
            check(f"{scheme}: primary button text {c:.1f}:1", c >= 4.5, str(st["primary"]))

            page.screenshot(path=SHOTS / f"theme-{scheme}.png")
            if scheme == "light":
                # A shorter window, so the page scrolls well past one screen.
                ctx.close()
                ctx = b.new_context(viewport={"width": 1280, "height": 720})
                page = open_home(ctx)
                n0 = page.evaluate(NAV)
                check("scroll-spy: Start here active at the top, no progress, no Back to top",
                      n0["active"] == "sec-1" and n0["read"] < 0.02 and not n0["back"] and n0["readLeft"] == n0["mainLeft"], str(n0))
                page.locator('.baton-nav-link[data-sec="sec-2"]').click()
                page.wait_for_timeout(1300)
                n2 = page.evaluate(NAV)
                top2 = page.evaluate("Math.round(document.getElementById('sec-2').getBoundingClientRect().top)")
                check("nav click: smooth-scrolls to the section, a little below the top", 8 <= top2 <= 40 and n2["active"] == "sec-2", f"{top2} {n2}")
                check("the indicator slides (transform, 220ms) to the active item", n2["indY"] == n2["actY"] and n2["indDur"].startswith("0.22"), str(n2))
                scroll_to(page, 2600)
                page.wait_for_timeout(600)
                n3 = page.evaluate(NAV)
                check("scrolling on, the spy follows to a later section", n3["active"] in ("sec-3", "sec-4", "sec-5"), str(n3))
                scroll_to(page, 99999)
                page.wait_for_timeout(600)
                n5 = page.evaluate(NAV)
                check("at the very bottom, the last section is active", n5["active"] == "sec-5", str(n5))
                scroll_to(page, 2600)
                page.wait_for_timeout(300)
                n3 = page.evaluate(NAV)
                check("reading progress fills as the page scrolls", 0.2 < n3["read"] <= 1, str(n3["read"]))
                check("Back to top shows after one viewport", n3["back"] and n3["scroll"] > n3["vh"], str(n3))
                page.locator(".baton-back").click()
                page.wait_for_timeout(1300)
                n4 = page.evaluate(NAV)
                check("Back to top returns to the top and hides", n4["scroll"] == 0 and not n4["back"], str(n4))
                # Clicking an item: scrolls to its card, and opens it if it was handled
                # Earlier sections handled the other four items on the same saved state: HPLC-07 is the one left.
                before = page.evaluate("getComputedStyle(document.querySelector('.baton-nav-count'),'::before').content")
                page.locator(".st-key-got-night-HPLC-07 button").click()
                page.wait_for_selector(".st-key-open-night-HPLC-07", timeout=30000)
                settle(page, 900)
                dot = page.evaluate("""() => {const a=document.querySelector('.baton-nav-asset[href="#card-HPLC-07"] .baton-dot'), o=a;
                    return [getComputedStyle(a).backgroundColor, getComputedStyle(o).backgroundColor, getComputedStyle(a).transitionDuration,
                            getComputedStyle(document.querySelector('.baton-nav-count'),'::before').content, new DOMMatrix(getComputedStyle(document.querySelector('.baton-nav-fill')).transform).a]}""")
                check("handled: its sidebar dot fills green, with a transition", "21, 128, 61" in dot[0] and dot[2] != "0s", str(dot))
                check("handled: sidebar progress counts it and the bar is full", before == '"4 of 5 handled"' and dot[3] == '"5 of 5 handled"'
                      and abs(dot[4] - 1) < 0.01, f"{before} {dot}")
                scroll_to(page, 0)
                page.locator('.baton-nav-asset[href="#card-HPLC-07"]').click()
                page.wait_for_selector(".st-key-got-night-HPLC-07", timeout=30000)
                settle(page, 1200)
                vis = page.evaluate("(()=>{const r=document.getElementById('card-HPLC-07').getBoundingClientRect(); return r.top>=0 && r.top<innerHeight})()")
                check("nav item: scrolls to the card and opens the handled step", vis and page.locator(".st-key-got-night-HPLC-07").count() == 1)
            ctx.close()

        # ---------- the drawer below 1024px ----------
        for w in (390, 900):
            ctx = b.new_context(viewport={"width": w, "height": 844})
            page = open_home(ctx)
            DRAWER = """() => {const s=document.querySelector('[data-testid=stSidebar]'), r=s.getBoundingClientRect(), a=document.activeElement, sh=document.querySelector('.baton-shade');
                return {open: document.documentElement.classList.contains('baton-drawer-open'), left: Math.round(r.left), vis: getComputedStyle(s).visibility,
                  shade: getComputedStyle(sh).opacity, focusIn: s.contains(a), focusMenu: !!(a && a.classList && a.classList.contains('baton-menu')),
                  expanded: document.querySelector('.baton-menu').getAttribute('aria-expanded')}}"""
            d0 = page.evaluate(DRAWER)
            check(f"{w} drawer: shut at first, out of the tab order", not d0["open"] and d0["left"] < 0 and d0["vis"] == "hidden", str(d0))
            page.locator(".baton-menu").click()
            page.wait_for_timeout(500)
            d1 = page.evaluate(DRAWER)
            check(f"{w} drawer: menu opens it over a dimmed backdrop, focus inside", d1["open"] and d1["left"] == 0 and float(d1["shade"]) > 0.9
                  and d1["focusIn"] and d1["expanded"] == "true", str(d1))
            for _ in range(25):
                page.keyboard.press("Tab")
            check(f"{w} drawer: Tab stays inside (focus trap)", page.evaluate(DRAWER)["focusIn"])
            for _ in range(25):
                page.keyboard.press("Shift+Tab")
            check(f"{w} drawer: Shift+Tab stays inside too", page.evaluate(DRAWER)["focusIn"])
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            d2 = page.evaluate(DRAWER)
            check(f"{w} drawer: Esc closes it and gives focus back to the menu", not d2["open"] and d2["left"] < 0 and d2["focusMenu"]
                  and d2["expanded"] == "false", str(d2))
            page.locator(".baton-menu").click()
            page.wait_for_timeout(500)
            page.mouse.click(w - 20, 600)
            page.wait_for_timeout(500)
            check(f"{w} drawer: a backdrop click closes it", not page.evaluate(DRAWER)["open"])
            page.locator(".baton-menu").click()
            page.wait_for_timeout(500)
            page.screenshot(path=SHOTS / f"drawer-{w}.png")
            page.locator('.baton-nav-link[data-sec="sec-4"]').click()
            page.wait_for_timeout(1300)
            top4 = page.evaluate("Math.round(document.getElementById('sec-4').getBoundingClientRect().top)")
            check(f"{w} drawer: a nav click closes it and lands below the top bar", not page.evaluate(DRAWER)["open"] and 56 <= top4 <= 100, str(top4))
            bar = page.evaluate("""() => {const t=document.querySelector('.st-key-baton-topbar'); return [Math.round(t.getBoundingClientRect().top), getComputedStyle(t,'::before').backgroundColor]}""")
            check(f"{w}: the top bar stays at the top with a solid background", bar[0] == 0 and bar[1] not in ("rgba(0, 0, 0, 0)", "transparent"), str(bar))
            over = page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
            check(f"{w}: no sideways scroll with the drawer", over <= 0, str(over))
            ctx.close()

        # ---------- hover and scroll polish ----------
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        page = open_home(ctx)
        page.wait_for_timeout(1500)
        page.locator('.baton-nav-link[data-sec="sec-2"]').hover()
        page.wait_for_timeout(400)
        roll = page.evaluate("new DOMMatrix(getComputedStyle(document.querySelector('.baton-nav-link[data-sec=sec-2] .baton-roll > span')).transform).f")
        check("nav label rolls up on hover", roll < -10, str(roll))
        page.locator('.baton-nav-link[data-sec="sec-4"]').focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        page.wait_for_timeout(400)
        roll = page.evaluate("new DOMMatrix(getComputedStyle(document.querySelector('.baton-nav-link[data-sec=sec-4] .baton-roll > span')).transform).f")
        check("…and on keyboard focus", roll < -10, str(roll))
        page.locator("a.baton-tl-label").first.hover()
        page.wait_for_timeout(400)
        row = page.evaluate("""() => {const b=document.querySelector('.st-key-baton-timeline'), pts=[...b.querySelectorAll('.scatterlayer .point')];
            return {hot: b.getAttribute('data-baton-hot'), grown: pts.filter(p=>p.style.transform.includes('scale')).length,
              dim: pts.filter(p=>getComputedStyle(p).opacity==='0.4').length, total: pts.length,
              others: [...b.querySelectorAll('.baton-tl-label:not(.baton-tl-hot)')].every(l=>getComputedStyle(l).opacity==='0.4'),
              shift: new DOMMatrix(getComputedStyle(b.querySelector('.baton-tl-label.baton-tl-hot .baton-tl-id')).transform).e}}""")
        check("timeline row hover: other rows dim to 40%, this row's marks grow, label steps 4px",
              row["hot"] == "0" and row["grown"] > 0 and row["dim"] > 0 and row["grown"] + row["dim"] <= row["total"]
              and row["others"] and row["shift"] == 4, str(row))
        tip = page.locator(".st-key-baton-timeline .js-plotly-plot")
        page.mouse.move(5, 500)
        page.wait_for_timeout(300)
        check("leaving the row restores every mark", page.evaluate("""() => {const b=document.querySelector('.st-key-baton-timeline');
            return !b.hasAttribute('data-baton-hot') && ![...b.querySelectorAll('.scatterlayer .point')].some(p=>p.style.transform)}"""))
        page.evaluate("document.getElementById('sec-4').scrollIntoView({behavior: 'instant'})")
        page.wait_for_timeout(1200)
        page.locator(".hc-note.clash").first.hover()
        page.wait_for_timeout(100)
        note = page.evaluate("""() => ({pulsing: [...document.querySelectorAll('.st-key-baton-timeline .scatterlayer .point')].filter(p=>p.getAnimations().length).length,
            bar: new DOMMatrix(getComputedStyle(document.querySelector('.hc-note.clash'), '::before').transform).d})""")
        check("note hover: its one chart mark pulses, the left bar grows", note["pulsing"] == 1 and note["bar"] > 0.3, str(note))
        card = page.locator("div[class*='st-key-baton-card-night-']").last
        card.scroll_into_view_if_needed()
        card.hover()
        page.wait_for_timeout(400)
        wipe = card.evaluate("e=>[getComputedStyle(e,'::before').transform, getComputedStyle(e,'::before').backgroundColor]")
        check("card hover: a tint wipes up from the bottom", wipe[0] == "none" and wipe[1] not in ("rgba(0, 0, 0, 0)", "transparent"), str(wipe))
        btn = page.locator("[data-testid=stBaseButton-primary]").first
        btn.scroll_into_view_if_needed()
        bb = btn.bounding_box()
        page.mouse.move(bb["x"] + bb["width"] - 3, bb["y"] + bb["height"] / 2)
        page.wait_for_timeout(250)
        pull = btn.evaluate("e=>new DOMMatrix(getComputedStyle(e).transform).e")
        check("primary button leans toward the mouse, at most 4px", 1 < pull <= 4, str(pull))
        scroll_to(page, 0)
        scroll_to(page, 200)
        par = page.evaluate("[document.querySelector('.hc-header').style.transform, parseFloat(document.querySelector('.hc-header').style.opacity)]")
        check("hero drifts and fades a little as it scrolls away", par[0].startswith("translateY(") and 0.6 < par[1] < 1, str(par))
        ctx.close()

        ctx = b.new_context(viewport={"width": 1400, "height": 900}, reduced_motion="reduce")
        page = open_home(ctx)
        page.locator('.baton-nav-link[data-sec="sec-2"]').hover()
        page.wait_for_timeout(300)
        roll = page.evaluate("getComputedStyle(document.querySelector('.baton-nav-link[data-sec=sec-2] .baton-roll > span')).transform")
        btn = page.locator("[data-testid=stBaseButton-primary]").first
        btn.scroll_into_view_if_needed()
        bb = btn.bounding_box()
        page.mouse.move(bb["x"] + bb["width"] - 3, bb["y"] + bb["height"] / 2)
        page.wait_for_timeout(250)
        pull = btn.evaluate("e=>getComputedStyle(e).transform")
        scroll_to(page, 200)
        par = page.evaluate("document.querySelector('.hc-header').style.transform")
        check("reduced motion: no roll, no pull, no parallax", roll == "none" and pull in ("none", "matrix(1, 0, 0, 1, 0, 0)") and not par, f"{roll} {pull} {par}")
        ctx.close()

        # ---------- reduced motion: everything shown at once, the chart already drawn ----------
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, reduced_motion="reduce")
        page = open_home(ctx)
        rm = page.evaluate("""() => ({hidden: [...document.querySelectorAll('[class*=st-key-baton-sec-] > *')].filter(e=>getComputedStyle(e).opacity==='0').length,
            points: [...document.querySelectorAll('.st-key-baton-timeline .scatterlayer .point')].filter(e=>getComputedStyle(e).opacity==='0').length,
            anim: getComputedStyle(document.querySelector('.st-key-baton-timeline .scatterlayer .point')).animationName,
            jump: getComputedStyle(document.querySelector('[data-testid=stMain]')).scrollBehavior,
            ind: getComputedStyle(document.querySelector('.baton-nav-indicator')).transitionDuration})""")
        check("reduced motion: nothing hidden, chart fully drawn, instant jumps", rm["hidden"] == 0 and rm["points"] == 0 and rm["anim"] == "none"
              and rm["jump"] == "auto" and rm["ind"] in ("0s", ""), str(rm))
        ctx.close()

        check("no page errors", not errors, str(errors[:3]))
        b.close()
finally:
    proc.terminate()

print(f"\n{len(fails)} failed" if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
