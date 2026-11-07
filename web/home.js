// Home page. Every number and sentence comes from out/handover.json, loaded through its
// script copy out/handover.js so the page also works from file:// with no server.
(function () {
  "use strict";

  var DATA_SCRIPT = "../out/handover.js";
  var HANDOVER_PAGE = "handover.html";
  var HOME_TAGS = ["clash", "no_open_ticket", "trend_worsening", "due_today"]; // others stay on the handover screen
  var SVG_NS = "http://www.w3.org/2000/svg";

  var app = document.getElementById("app");
  var help = document.getElementById("help");
  var helpToggle = document.getElementById("help-toggle");
  var tooltip = document.getElementById("tooltip");
  var startLink = null;

  // ---------- DOM helpers: text always goes in as text, never as HTML ----------

  function fill(node, attrs, children) {
    Object.keys(attrs || {}).forEach(function (key) {
      if (attrs[key] !== null && attrs[key] !== undefined) node.setAttribute(key, attrs[key]);
    });
    (children || []).forEach(function (child) {
      if (child !== null && child !== undefined) {
        node.appendChild(typeof child === "object" ? child : document.createTextNode(String(child)));
      }
    });
    return node;
  }
  function el(tag, attrs, children) { return fill(document.createElement(tag), attrs, children); }
  function svg(tag, attrs, children) { return fill(document.createElementNS(SVG_NS, tag), attrs, children); }

  function itemLink(assetId) { return HANDOVER_PAGE + "#" + encodeURIComponent(assetId); }

  // ---------- top bar ----------

  function renderTopbar(data) {
    document.getElementById("site").textContent = data.site;
    document.getElementById("incoming").textContent =
      data.handover.incoming_shift + " · " + data.handover.incoming_engineer;
    setStatus("ready", "Ready");
  }

  function setStatus(state, text) {
    document.getElementById("status").className = "status-pill " + state;
    document.getElementById("status-text").textContent = text;
  }

  // ---------- status card ----------

  function tile(value, label, extraClass) {
    return el("div", { class: "tile " + (extraClass || "") }, [el("strong", {}, [value]), el("span", {}, [label])]);
  }

  function renderStatus(data) {
    var c = data.counts;
    startLink = el("a", { class: "start", href: HANDOVER_PAGE, id: "start" }, [
      "Start handover", el("kbd", { "aria-hidden": "true" }, ["↵"])
    ]);
    return el("section", { class: "card status", "aria-labelledby": "heading" }, [
      el("p", { class: "eyebrow" }, [data.handover.eyebrow]),
      el("h1", { id: "heading" }, [data.heading]),
      el("p", { class: "summary", id: "summary" }, [
        data.summary.lead + (data.summary.clash ? " " : ""),
        data.summary.clash ? el("span", { class: "amber" }, [data.summary.clash]) : null
      ]),
      el("div", { class: "tiles" }, [
        tile(c.top, "Need you first", "top"),
        tile(c.clash, "Notes and data disagree", "clash"),
        tile(c.not_urgent, "Checked, not urgent", "rest")
      ]),
      startLink,
      el("p", { class: "trust", id: "trust" }, [
        (data.handover.outgoing_engineer ? "From " + data.handover.outgoing_engineer + " · " : "") +
        c.alerts + " alerts · " + c.tickets + " tickets · " + c.note_lines + " note lines read"
      ])
    ]);
  }

  // ---------- first in line ----------

  function renderRow(item) {
    var tags = item.tags
      .filter(function (t) { return HOME_TAGS.indexOf(t.key) !== -1; })
      .map(function (t) { return el("span", { class: "tag" + (t.key === "clash" ? " clash" : "") }, [t.label]); });
    if (item.projected_limit_label) {
      tags.push(el("span", { class: "tag countdown", title: "Straight-line estimates: from the last two readings and from all readings" }, [item.projected_limit_label]));
    }
    return el("li", {}, [
      el("a", { class: "row", href: itemLink(item.asset_id), "data-asset": item.asset_id }, [
        el("span", { class: "rank" }, [item.rank]),
        el("span", {}, [
          el("span", { class: "tags" }, tags),
          el("span", { class: "row-title" }, [item.title]),
          el("span", { class: "row-evidence" }, [item.evidence])
        ])
      ])
    ]);
  }

  function renderFirst(data) {
    var more = data.items.length - Math.min(3, data.items.length);
    var parts = [];
    if (more > 0) parts.push("+" + more + " more");
    parts.push(data.counts.not_urgent + " checked, not urgent");
    return el("section", { class: "card first", "aria-labelledby": "first-title" }, [
      el("div", { class: "card-head" }, [el("h2", { id: "first-title" }, ["First in line"])]),
      el("ol", {}, data.items.slice(0, 3).map(renderRow)),
      el("p", { class: "more", id: "more" }, [parts.join(" · ")])
    ]);
  }

  // ---------- timeline ----------

  var ROW_HEIGHT = 56, TREND_ROW_HEIGHT = 84, AXIS_HEIGHT = 26;
  var LABEL_WIDTH = 216, RIGHT_PAD = 20, MIN_WIDTH = 880;
  var NARROW_BELOW = 600, NARROW_LABEL_WIDTH = 124, NARROW_LABEL_CHARS = 19; // phones: more chart, wrapped labels
  var FADE_WINDOW = 250; // + 150ms per dot = 400ms in total
  var QUOTE_CHAR_WIDTH = 5.8; // rough width of an 11px Inter character, for placing labels

  function eventLabel(e) {
    var who = e.asset_id ? e.asset_id + ", " : "";
    var kind = e.kind === "note" ? "note" : e.severity + " alert";
    var flag = !e.clash ? "" : e.kind === "note" ? ". The data disagrees with this note" : ". Came after a note saying it was fine";
    return e.time + ", " + who + kind + ", " + e.system + ": " + e.text + flag;
  }

  // Splits text into at most 2 lines of maxChars, so a long description fits a narrow label column.
  function wrapLabel(text, maxChars) {
    var lines = [""];
    text.split(" ").forEach(function (word) {
      var last = lines.length - 1;
      if (!lines[last] || (lines[last] + " " + word).length <= maxChars) {
        lines[last] = (lines[last] ? lines[last] + " " : "") + word;
      } else {
        lines.push(word);
      }
    });
    if (lines.length > 2) lines = [lines[0], lines.slice(1).join(" ").slice(0, maxChars - 1) + "…"];
    return lines.map(function (line) { return line.replace(/ ·$/, ""); });
  }

  function renderTimelineSvg(data, width, available) {
    var tl = data.timeline;
    var narrow = available < NARROW_BELOW;
    var labelWidth = narrow ? NARROW_LABEL_WIDTH : LABEL_WIDTH;
    var labelX = narrow ? 16 : 20;
    var plot = width - labelWidth - RIGHT_PAD;
    function x(minutes) { return labelWidth + (minutes / tl.minutes) * plot; }
    var height = AXIS_HEIGHT;
    tl.rows.forEach(function (r) { height += r.trend ? TREND_ROW_HEIGHT : ROW_HEIGHT; });

    var root = svg("svg", { width: width, height: height, viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": tl.summary });

    // Hour grid, every 2 hours, starting from the shift start.
    for (var m = 0; m <= tl.minutes; m += 120) {
      var hour = (19 + m / 60) % 24;
      root.appendChild(svg("line", { class: "tl-grid", x1: x(m), x2: x(m), y1: AXIS_HEIGHT, y2: height }));
      root.appendChild(svg("text", {
        class: "tl-hour", x: x(m), y: 17,
        "text-anchor": m === 0 ? "start" : m === tl.minutes ? "end" : "middle"
      }, [(hour < 10 ? "0" : "") + hour + ":00"]));
    }

    var y0 = AXIS_HEIGHT;
    tl.rows.forEach(function (row) {
      root.appendChild(svg("line", { class: "tl-sep", x1: 0, x2: width, y1: y0, y2: y0 }));
      var lines = narrow ? wrapLabel(row.description, NARROW_LABEL_CHARS) : [row.description];
      root.appendChild(svg("text", { class: "tl-id", x: labelX, y: y0 + (narrow ? 17 : 23) }, [row.id]));
      lines.forEach(function (line, i) {
        root.appendChild(svg("text", { class: "tl-desc", x: labelX, y: y0 + (narrow ? 33 : 39) + i * 14 }, [line]));
      });
      drawRow(root, data, row, y0, x, width, labelWidth);
      y0 += row.trend ? TREND_ROW_HEIGHT : ROW_HEIGHT;
    });
    return root;
  }

  function drawRow(root, data, row, y0, x, width, labelWidth) {
    var trend = row.trend;
    var markTop = y0 + (trend ? 56 : 28);
    var quoteY = markTop + 24;
    var yOf = function () { return y0 + 16; };

    if (trend) {
      var values = trend.points.map(function (p) { return p.value; });
      var lo = Math.min.apply(null, values), hi = Math.max.apply(null, values);
      // Worse is always upward, so a climbing line reads the same for ceilings and floors.
      yOf = function (value) {
        if (value === null || value === undefined || hi === lo) return y0 + 36;
        var worse = (value - lo) / (hi - lo);
        return y0 + 48 - 24 * (trend.higher_is_worse ? worse : 1 - worse);
      };
      var line = svg("polyline", {
        class: "tl-trend tl-fade",
        points: trend.points.map(function (p) { return x(p.minutes) + "," + yOf(p.value); }).join(" ")
      });
      line.style.setProperty("--delay", FADE_WINDOW + "ms");
      root.appendChild(line);
      trend.points.forEach(function (p, i) {
        var last = i === trend.points.length - 1;
        root.appendChild(svg("text", {
          class: "tl-value tl-fade", x: last ? x(p.minutes) + 7 : x(p.minutes), y: yOf(p.value) - 10,
          "text-anchor": last ? "end" : i === 0 ? "start" : "middle",
          style: "--delay:" + fadeDelay(p.minutes, data) + "ms"
        }, [p.label]));
      });
    }

    var anchors = quoteAnchors(data, row, x, width, labelWidth);

    data.events.forEach(function (e, index) {
      if (!onRow(e, row, data)) return;
      var px = x(e.minutes);
      var group = svg("g", {
        class: "tl-event tl-fade", tabindex: "0", role: "img", "aria-label": eventLabel(e),
        "data-event": index, "data-kind": e.kind, "data-clash": String(e.clash), "data-row": row.id,
        style: "--delay:" + fadeDelay(e.minutes, data) + "ms"
      });
      if (e.kind === "alert") {
        var py = yOf(e.value);
        group.appendChild(svg("circle", { class: "tl-hit", cx: px, cy: py, r: 11 }));
        group.appendChild(svg("circle", { class: "tl-ring", cx: px, cy: py, r: 8 }));
        group.appendChild(svg("circle", { class: "tl-dot" + (e.clash ? " clash" : ""), cx: px, cy: py, r: 4.5 }));
      } else {
        group.appendChild(svg("rect", { class: "tl-hit", x: px - 10, y: markTop - 4, width: 20, height: 20 }));
        group.appendChild(svg("rect", { class: "tl-ring", x: px - 6, y: markTop - 3, width: 12, height: 18, rx: 3 }));
        group.appendChild(svg("line", { class: "tl-mark" + (e.clash ? " clash" : ""), x1: px, x2: px, y1: markTop, y2: markTop + 12 }));
        group.appendChild(svg("text", {
          class: "tl-quote" + (e.clash ? " clash" : ""),
          x: anchors[index].x, y: quoteY,
          "text-anchor": anchors[index].anchor
        }, ["“" + e.key_words + "”"]));
      }
      root.appendChild(group);
    });
  }

  function onRow(e, row, data) {
    return e.row === row.id && e.minutes !== null && e.minutes >= 0 && e.minutes <= data.timeline.minutes;
  }

  // Centres each quote under its mark unless that would hit the chart's edge or the next quote,
  // working right to left so each quote knows where the one after it starts.
  function quoteAnchors(data, row, x, width, labelWidth) {
    var anchors = {};
    var nextLeft = width - RIGHT_PAD;
    for (var i = data.events.length - 1; i >= 0; i--) {
      var e = data.events[i];
      if (e.kind !== "note" || !onRow(e, row, data)) continue;
      var px = x(e.minutes);
      var textWidth = (e.key_words.length + 2) * QUOTE_CHAR_WIDTH;
      var place = { anchor: "middle", x: px };
      if (px - textWidth / 2 < labelWidth) place = { anchor: "start", x: px - 2 };
      else if (px + textWidth / 2 > nextLeft) place = { anchor: "end", x: Math.min(px + 2, nextLeft) };
      anchors[i] = place;
      nextLeft = (place.anchor === "start" ? place.x : place.anchor === "end" ? place.x - textWidth : place.x - textWidth / 2) - 6;
    }
    return anchors;
  }

  function fadeDelay(minutes, data) {
    return Math.round((minutes / data.timeline.minutes) * FADE_WINDOW);
  }

  function legendItem(symbol, label) { return el("li", {}, [symbol, label]); }

  function renderLegend() {
    function dot(cls) {
      return svg("svg", { width: 10, height: 10, "aria-hidden": "true" }, [svg("circle", { class: cls, cx: 5, cy: 5, r: 4 })]);
    }
    return el("ul", { class: "legend", "aria-label": "Legend" }, [
      legendItem(dot("tl-dot"), "Alert"),
      legendItem(dot("tl-dot clash"), "Alert after a reassuring note"),
      legendItem(svg("svg", { width: 6, height: 12, "aria-hidden": "true" }, [
        svg("line", { class: "tl-mark", x1: 3, x2: 3, y1: 1.5, y2: 10.5 })
      ]), "Note"),
      legendItem(svg("svg", { width: 18, height: 6, "aria-hidden": "true" }, [
        svg("line", { class: "tl-trend", x1: 0, x2: 18, y1: 3, y2: 3 })
      ]), "Trend")
    ]);
  }

  function renderLog(data) {
    var items = data.events.map(function (e) {
      return el("li", { class: e.clash ? "is-clash" : "" }, [
        el("span", { class: "log-time" }, [e.time]),
        el("span", { class: "log-asset" }, [e.asset_id || "General"]),
        el("span", { class: "log-text" }, [
          e.kind === "note" ? "Note: " + e.text : e.system + ": " + e.text,
          e.clash ? el("span", { class: "sr-only" }, [" (notes and data disagree)"]) : null
        ])
      ]);
    });
    var chevron = svg("svg", { width: 12, height: 12, viewBox: "0 0 12 12", "aria-hidden": "true" }, [
      svg("path", { d: "M4.5 2.5 8 6 4.5 9.5", fill: "none", stroke: "currentColor", "stroke-width": 1.5, "stroke-linecap": "round", "stroke-linejoin": "round" })
    ]);
    return el("details", { class: "log", id: "event-log" }, [
      el("summary", {}, [chevron, "Event log ", el("span", { class: "muted" }, ["· " + data.events.length + " events"])]),
      el("ol", {}, items)
    ]);
  }

  function renderTimeline(data) {
    var scroller = el("div", { class: "tl-scroll", tabindex: "0", role: "group", "aria-label": "Timeline, scrolls sideways on small screens" });
    var lastAvailable = 0;
    function draw() {
      var available = Math.floor(scroller.clientWidth);
      if (available === lastAvailable) return;
      if (lastAvailable) scroller.classList.add("no-fade"); // the fade-in only runs once
      lastAvailable = available;
      hideTip();
      scroller.replaceChildren(renderTimelineSvg(data, Math.max(MIN_WIDTH, available), available));
    }
    scroller.addEventListener("scroll", placeTip);
    scroller.addEventListener("mouseover", function (ev) { showTip(ev.target, data); });
    scroller.addEventListener("mouseout", hideTip);
    scroller.addEventListener("focusin", function (ev) { showTip(ev.target, data); });
    scroller.addEventListener("focusout", hideTip);
    new ResizeObserver(draw).observe(scroller);

    return el("section", { class: "card", "aria-labelledby": "night-title" }, [
      el("div", { class: "card-head" }, [el("h2", { id: "night-title" }, ["The night at a glance"]), renderLegend()]),
      scroller,
      renderLog(data)
    ]);
  }

  // ---------- tooltip ----------

  var tipTarget = null;

  function showTip(target, data) {
    var group = target.closest && target.closest(".tl-event");
    if (!group) return;
    var e = data.events[Number(group.getAttribute("data-event"))];
    var head = e.time + " · " + (e.asset_id ? e.asset_id + " · " : "") + e.system;
    tooltip.replaceChildren(el("span", { class: "tip-head" }, [head]), e.text);
    tooltip.hidden = false;
    tipTarget = group;
    placeTip();
  }

  // Also runs on scroll: tabbing to an off-screen dot scrolls the page after the tooltip opens.
  function placeTip() {
    if (!tipTarget) return;
    var mark = tipTarget.querySelector(".tl-ring").getBoundingClientRect();
    var tip = tooltip.getBoundingClientRect();
    var left = Math.min(window.innerWidth - tip.width - 8, Math.max(8, mark.left + mark.width / 2 - tip.width / 2));
    var top = mark.top - tip.height - 8;
    tooltip.style.left = left + "px";
    tooltip.style.top = (top < 8 ? mark.bottom + 8 : top) + "px";
  }

  function hideTip() {
    tooltip.hidden = true;
    tipTarget = null;
  }

  // ---------- recent handovers ----------

  function renderRecent(data) {
    var recent = data.recent_handovers;
    var head = [el("h2", { id: "recent-title" }, ["Recent handovers"])];
    if (recent.sample) head.push(el("span", { class: "sample-note" }, ["Sample data"]));
    return el("section", { class: "card", "aria-labelledby": "recent-title" }, [
      el("div", { class: "card-head" }, head),
      el("ul", {}, recent.rows.map(function (r) {
        return el("li", { class: "recent-row" }, [
          el("span", { class: "mono muted" }, [r.time]),
          el("span", {}, [r.direction]),
          el("span", { class: "ack muted" }, [r.acknowledged + " of " + r.total + " acknowledged"])
        ]);
      }))
    ]);
  }

  // ---------- page ----------

  function render(data) {
    renderTopbar(data);
    var sections = [
      el("div", { class: "top-grid" }, [renderStatus(data), renderFirst(data)]),
      renderTimeline(data),
      renderRecent(data)
    ];
    // Stagger: the two top cards count as sections 0 and 1.
    sections[0].children[0].classList.add("rise");
    sections[0].children[1].classList.add("rise");
    sections[0].children[1].style.setProperty("--i", 1);
    sections[1].classList.add("rise");
    sections[1].style.setProperty("--i", 2);
    sections[2].classList.add("rise");
    sections[2].style.setProperty("--i", 3);
    app.replaceChildren.apply(app, sections);
  }

  function renderMissingData() {
    setStatus("missing", "No data yet");
    app.replaceChildren(el("section", { class: "card message" }, [
      el("h1", {}, ["The night hasn't been read yet."]),
      el("p", { class: "summary" }, ["From the project folder, run ", el("code", {}, ["python -m src.export"]), ", then reload this page."])
    ]));
  }

  function loadData() {
    var script = document.createElement("script");
    script.src = DATA_SCRIPT;
    script.onload = function () {
      if (window.HANDOVER_DATA) render(window.HANDOVER_DATA);
      else renderMissingData();
    };
    script.onerror = renderMissingData;
    document.head.appendChild(script);
  }

  // ---------- keyboard ----------

  function setHelp(open) {
    help.hidden = !open;
    helpToggle.setAttribute("aria-expanded", String(open));
  }

  function moveRow(step) {
    var rows = Array.prototype.slice.call(document.querySelectorAll(".row"));
    if (!rows.length) return;
    var at = rows.indexOf(document.activeElement);
    var next = at === -1 ? (step > 0 ? 0 : rows.length - 1) : Math.min(rows.length - 1, Math.max(0, at + step));
    rows[next].focus();
  }

  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var key = e.key.length === 1 ? e.key.toLowerCase() : e.key;

    if (key === "Escape") {
      setHelp(false);
      hideTip();
    } else if (key === "Enter") {
      // Links, buttons and the event log keep their own Enter.
      if (startLink && !e.target.closest("a, button, summary, [tabindex]")) location.href = startLink.href;
    } else if (key === "j" || key === "k") {
      e.preventDefault();
      moveRow(key === "j" ? 1 : -1);
    } else if (key === "t") {
      window.toggleTheme();
    } else if (key === "?") {
      setHelp(help.hidden);
    }
  });

  document.getElementById("theme-toggle").addEventListener("click", window.toggleTheme);
  helpToggle.addEventListener("click", function (e) {
    e.stopPropagation();
    setHelp(help.hidden);
  });
  document.addEventListener("click", function (e) {
    if (!help.hidden && !help.contains(e.target)) setHelp(false);
  });
  window.addEventListener("scroll", placeTip, { passive: true });

  loadData();
})();
