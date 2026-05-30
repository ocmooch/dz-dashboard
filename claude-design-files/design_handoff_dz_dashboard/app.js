/* ============================================================
   DANGER ZONE — selector logic + wireframe surfaces
   ============================================================ */
(function () {
  "use strict";

  var modeSeg = document.getElementById("modeSeg");
  var surfSeg = document.getElementById("surfSeg");
  var surfGroup = document.getElementById("surfGroup");
  var frontend = document.getElementById("frontend");
  var wireframe = document.getElementById("wireframe");
  var railHint = document.getElementById("railHint");
  var wireSheets = document.getElementById("wireSheets");

  var state = { mode: "frontend", front: "home", surf: "home" };

  var FRONT_HINTS = {
    home: "Command Center · faithful HUD / cockpit",
    rivalries: "Rivalries · head-to-head matrix"
  };
  var WIRE_HINTS = {
    home: "Wireframe · Home (Command Center) IA",
    standings: "Wireframe · Standings IA",
    rivalries: "Wireframe · Rivalries IA"
  };

  function setOn(seg, attr, val) {
    Array.prototype.forEach.call(seg.querySelectorAll("button"), function (b) {
      b.classList.toggle("on", b.getAttribute(attr) === val);
    });
  }

  function render() {
    var fe = state.mode === "frontend";
    wireframe.classList.toggle("hidden", fe);
    frontend.classList.toggle("hidden", !fe);
    surfGroup.classList.toggle("hidden", fe);
    if (fe) {
      railHint.textContent = FRONT_HINTS[state.front] || "";
      // show the active surface
      Array.prototype.forEach.call(frontend.querySelectorAll(".surface"), function (s) {
        s.hidden = s.getAttribute("data-surface") !== state.front;
      });
      // active nav item
      Array.prototype.forEach.call(frontend.querySelectorAll(".nav-item[data-nav]"), function (n) {
        n.classList.toggle("active", n.getAttribute("data-nav") === state.front);
      });
      if (state.front === "rivalries") buildRivalries();
      window.scrollTo(0, 0);
    } else {
      railHint.textContent = WIRE_HINTS[state.surf];
      wireSheets.innerHTML = WIRE[state.surf]();
    }
  }

  modeSeg.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    state.mode = b.getAttribute("data-mode"); setOn(modeSeg, "data-mode", state.mode); render();
  });
  surfSeg.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    state.surf = b.getAttribute("data-surf"); setOn(surfSeg, "data-surf", state.surf); render();
  });

  /* left-nav drives frontend surface switching */
  frontend.addEventListener("click", function (e) {
    var n = e.target.closest(".nav-item[data-nav]"); if (!n) return;
    state.front = n.getAttribute("data-nav"); render();
  });
  frontend.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var n = e.target.closest(".nav-item[data-nav]"); if (!n) return;
    e.preventDefault(); state.front = n.getAttribute("data-nav"); render();
  });

  /* simple sortable affordance on the standings demo header (visual only) */
  document.addEventListener("click", function (e) {
    var th = e.target.closest(".tbl th"); if (!th) return;
    var row = th.parentNode;
    Array.prototype.forEach.call(row.children, function (c) {
      var s = c.querySelector(".sort"); if (s && c !== th) s.remove();
    });
    if (!th.querySelector(".sort")) {
      var span = document.createElement("span"); span.className = "sort"; span.textContent = "▾";
      th.appendChild(span);
    }
  });

  /* ---------------- WIREFRAME SURFACES ---------------- */
  function topbar() {
    return '' +
    '<div class="wtop">' +
      '<div class="wlogo">DZ</div>' +
      '<div class="label">DANGER ZONE</div>' +
      '<div class="wsearch">⌕ &nbsp;search owner / player / season…</div>' +
      '<div class="wpill">Season: 2019 ▾</div>' +
      '<div class="wpill">⬤ run #56</div>' +
    '</div>';
  }
  function nav(active) {
    var items = [["Home",1],["Standings",1],["Matchups",1],["Teams",0],["Managers",1],["Rivalries",1],["Records",1],["Players",0],["Draft",0]];
    return '<div class="wnav">' + items.map(function (it) {
      var on = it[0].toLowerCase() === active ? " on" : "";
      var soon = it[1] ? "" : " soon";
      return '<div class="wnav-item' + on + soon + '">' + it[0] + (it[1] ? "" : " · soon") + '</div>';
    }).join("") + '</div>';
  }
  function shell(active, main) {
    return topbar() + '<div class="wbody">' + nav(active) + '<div class="wmain">' + main + '</div></div>';
  }

  var WIRE = {
    home: function () {
      var stats = ["SEASONS","SCORED ERA","2019 LEADER","CHAMPION"].map(function (k, i) {
        return '<div class="wstat"><div class="k">' + k + '</div><div class="v">' + (["16","10y","sully","sully"][i]) + '</div></div>';
      }).join("");
      var standRows = ["sully","Dave","harry","Chris","Gregg","Dan"].map(function (n, i) {
        return '<div class="wtable-row"><div class="wcircle">' + (i + 1) + '</div><div class="scribble w-60"></div><div class="num-block">8-5</div><div class="num-block">1,9xx</div></div>';
      }).join("");
      var movers = ["Ben ▲3","sully ▲2","harry ▼2","Tom ▼1"].map(function (m) {
        return '<div class="wtable-row" style="grid-template-columns:1fr 80px"><div class="label" style="font-size:18px">' + m + '</div><div class="scribble w-80 dark"></div></div>';
      }).join("");
      return shell("home",
        '<div class="callout"><div class="label" style="font-size:30px">COMMAND CENTER</div><span class="arrow">←</span><span class="hand-note">owner-first hero: one glance = league pulse</span></div>' +
        '<div class="wrow c4">' + stats + '</div>' +
        '<div class="wcard" style="border-style:dashed">' +
          '<div class="wcard-h"><div class="wcard-t">◍ OWNER SIGNAL</div><span class="wpill">auto-surfaced</span></div>' +
          '<div style="display:grid;grid-template-columns:120px 1fr;gap:18px;align-items:center">' +
            '<div class="wchart" style="height:90px"><div class="ln"></div></div>' +
            '<div><div class="label" style="font-size:24px">"sully closes strongest in the league"</div>' +
            '<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap"><span class="wpill">▲ finisher</span><span class="wpill">elite WR</span><span class="wpill">slow starts</span></div></div>' +
          '</div>' +
          '<div class="callout" style="margin-top:10px"><span class="arrow">↑</span><span class="hand-note">THE differentiator — computed trends, not raw stats</span></div>' +
        '</div>' +
        '<div class="wrow c2">' +
          '<div class="wcard"><div class="wcard-h"><div class="wcard-t">Standings</div><span class="hand-note">full table →</span></div>' + standRows + '</div>' +
          '<div class="wcard"><div class="wcard-h"><div class="wcard-t">Week 14 Matchups</div></div>' +
            '<div class="wtable-row" style="grid-template-columns:1fr 60px 1fr"><div class="label">sully</div><div class="num-block">142-98</div><div class="label" style="text-align:right">Tom</div></div>' +
            '<div class="wtable-row" style="grid-template-columns:1fr 60px 1fr"><div class="label">Dave</div><div class="num-block" style="color:var(--waccent)">● LIVE</div><div class="label" style="text-align:right">harry</div></div>' +
            '<div class="wtable-row" style="grid-template-columns:1fr 60px 1fr"><div class="label">Chris</div><div class="num-block">130-110</div><div class="label" style="text-align:right">Gregg</div></div>' +
          '</div>' +
        '</div>' +
        '<div class="wrow c2">' +
          '<div class="wcard"><div class="wcard-h"><div class="wcard-t">Power Movers</div></div>' + movers + '</div>' +
          '<div class="wcard"><div class="wcard-h"><div class="wcard-t">Rivalry of week</div><span class="hand-note">→ matrix</span></div>' +
            '<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0"><div class="label" style="font-size:26px">sully</div><div class="num-block" style="font-size:30px">11 – 7</div><div class="label" style="font-size:26px">harry</div></div>' +
            '<div class="scribble w-100"></div><div class="scribble w-80" style="margin-top:8px"></div></div>' +
        '</div>' +
        '<div class="wrow c4">' +
          recCell("HIGH SCORE","253.56") + recCell("BEST PLAYER WK","60.90") + recCell("MOST TITLES","4") +
          '<div class="wstat" style="border-style:dashed"><div class="k">LONGEST STREAK</div><div class="wgap">⚠ not scored · pre-2016</div></div>' +
        '</div>' +
        '<div class="callout" style="margin-top:6px"><span class="arrow">↑</span><span class="hand-note">honest data-gap badge — never a fake 0</span></div>'
      );
    },

    standings: function () {
      var rows = [["1","sully","10-3","2,011","W4"],["2","Dave","9-4","1,884","W2"],["3","harry","8-5","1,902","L1"],["4","Chris","8-5","1,640","W1"],["5","Gregg","7-6","1,712","L2"],["6","Dan","7-6","1,588","W1"]].map(function (r) {
        return '<div class="wtable-row" style="grid-template-columns:28px 1fr 70px 70px 60px"><div class="wcircle">' + r[0] + '</div><div class="scribble w-60"></div><div class="num-block">' + r[2] + '</div><div class="num-block">' + r[3] + '</div><div class="wpill" style="padding:2px 8px;font-size:14px">' + r[4] + '</div></div>';
      }).join("");
      return shell("standings",
        '<div class="callout"><div class="label" style="font-size:30px">STANDINGS</div><span class="arrow">←</span><span class="hand-note">sortable · sticky header · mono right-aligned</span></div>' +
        '<div class="wrow c2" style="grid-template-columns:1fr 1fr">' +
          '<div class="wcard"><div class="wcard-h"><div class="wcard-t">Through week ▸ 14</div><span class="hand-note">stepper</span></div>' +
            '<div class="wtable-row" style="grid-template-columns:28px 1fr 70px 70px 60px;border-bottom:2px solid var(--wink)"><div>#</div><div class="label" style="font-size:15px">MANAGER</div><div class="label" style="font-size:15px">W-L</div><div class="label" style="font-size:15px">PF</div><div class="label" style="font-size:15px">STRK</div></div>' +
            rows + '</div>' +
          '<div class="wcard"><div class="wcard-h"><div class="wcard-t">Rank over time</div><span class="hand-note">bump chart</span></div>' +
            '<div class="wchart" style="height:240px">' +
              '<svg viewBox="0 0 300 200" style="width:100%;height:100%" preserveAspectRatio="none">' +
              '<polyline points="10,40 80,20 150,30 220,15 290,10" fill="none" stroke="#2b2b2b" stroke-width="2.5"/>' +
              '<polyline points="10,80 80,60 150,90 220,70 290,55" fill="none" stroke="#8c867a" stroke-width="2.5"/>' +
              '<polyline points="10,120 80,140 150,110 220,130 290,150" fill="none" stroke="#b9b3a6" stroke-width="2.5"/>' +
              '</svg>' +
              '<div class="hand-note" style="position:absolute;bottom:8px;left:12px">each line = one owner\u2019s rank, wk-by-wk</div>' +
            '</div></div>' +
        '</div>' +
        '<div class="callout"><span class="arrow">↘</span><span class="hand-note">< 768px: table → horizontal scroll, sticky first column</span></div>'
      );
    },

    rivalries: function () {
      var names = ["sully","Dave","harry","Chris","Gregg","Dan"];
      var head = '<div class="wheat-cell" style="border:none"></div>' + names.map(function (n) { return '<div class="wheat-cell" style="border:none">' + n.slice(0, 3) + '</div>'; }).join("");
      var grid = names.map(function (n, r) {
        var cells = '<div class="wheat-cell" style="border:none;justify-content:flex-end;padding-right:6px">' + n + '</div>';
        for (var c = 0; c < names.length; c++) {
          if (c === r) cells += '<div class="wheat-cell self"></div>';
          else { var cls = (r + c) % 3 === 0 ? " f3" : ((r + c) % 3 === 1 ? " f2" : ""); cells += '<div class="wheat-cell' + cls + '">' + (50 + ((r * 7 + c * 11) % 40)) + '</div>'; }
        }
        return cells;
      }).join("");
      return shell("rivalries",
        '<div class="callout"><div class="label" style="font-size:30px">RIVALRIES</div><span class="arrow">←</span><span class="hand-note">16-yr emotional payload — make it shine</span></div>' +
        '<div class="wrow c2" style="grid-template-columns:1.3fr 1fr">' +
          '<div class="wcard"><div class="wcard-h"><div class="wcard-t">N×N win-pct matrix</div><span class="hand-note">click cell → H2H page</span></div>' +
            '<div class="wheat" style="grid-template-columns:repeat(7,1fr)">' + head + grid + '</div>' +
            '<div class="callout" style="margin-top:12px"><span class="arrow">↑</span><span class="hand-note">never-met pairs = hatched "—", not 0</span></div>' +
          '</div>' +
          '<div class="wcard"><div class="wcard-h"><div class="wcard-t">Head-to-head</div><span class="hand-note">drill-in</span></div>' +
            '<div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0"><div class="wcircle" style="width:46px;height:46px;font-size:18px">SU</div><div class="num-block" style="font-size:40px">11 – 7</div><div class="wcircle" style="width:46px;height:46px;font-size:18px">HA</div></div>' +
            '<div class="scribble w-100"></div>' +
            '<div class="label" style="margin-top:14px;font-size:18px">Meeting log</div>' +
            '<div class="wtable-row" style="grid-template-columns:80px 1fr 70px"><div class="num-block">2019 w12</div><div class="scribble w-60"></div><div class="num-block">+6.2</div></div>' +
            '<div class="wtable-row" style="grid-template-columns:80px 1fr 70px"><div class="num-block">2018 w03</div><div class="scribble w-60"></div><div class="num-block">-2.1</div></div>' +
            '<div class="wtable-row" style="grid-template-columns:80px 1fr 70px"><div class="num-block">2017 w09</div><div class="scribble w-60"></div><div class="num-block">+18.7</div></div>' +
            '<div class="wgap" style="margin-top:12px">⚠ pre-2016 meetings not scored</div>' +
          '</div>' +
        '</div>'
      );
    }
  };

  function recCell(k, v) {
    return '<div class="wstat"><div class="k">' + k + '</div><div class="v">' + v + '</div></div>';
  }

  /* ================= RIVALRIES (data-driven) ================= */
  var MGRS = [
    { id: "sully", name: "sully", av: "SU" },
    { id: "dave",  name: "Dave",  av: "DA" },
    { id: "harry", name: "harry", av: "HA" },
    { id: "chris", name: "Chris", av: "CH" },
    { id: "gregg", name: "Gregg", av: "GR" },
    { id: "dan",   name: "Dan",   av: "DN" },
    { id: "mike",  name: "Mike",  av: "MI" },
    { id: "nick",  name: "Nick",  av: "NI" },
    { id: "tom",   name: "Tom",   av: "TO" },
    { id: "ben",   name: "Ben",   av: "BE" }
  ];
  var N = MGRS.length;
  var NEVER_MET = { "ben:tom": 1, "mike:nick": 1 };   // demonstrate DataGap
  var SEASONS_POOL = [2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016];

  function rng(seed) {
    var s = seed >>> 0;
    return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  }

  // canonical pairwise series, cached. Stored from the lower-index owner's view.
  var SERIES = {};
  function pairKey(a, b) { return a < b ? a + ":" + b : b + ":" + a; }
  function buildSeries(i, j) {
    var a = Math.min(i, j), b = Math.max(i, j);
    var key = a + "_" + b;
    if (SERIES[key]) return SERIES[key];
    var idKey = pairKey(MGRS[a].id, MGRS[b].id);
    if (NEVER_MET[idKey]) { return (SERIES[key] = { met: false }); }

    var r = rng((a + 1) * 131 + (b + 1) * 977);
    var total = 6 + Math.floor(r() * 17);             // 6..22 meetings
    var bias = 0.30 + r() * 0.40;                     // a's win prob
    var games = [];
    var aw = 0;
    for (var g = 0; g < total; g++) {
      var aWon = r() < bias;
      if (aWon) aw++;
      var margin = +(1 + r() * 41).toFixed(1);        // 1..42
      games.push({ season: SEASONS_POOL[g % SEASONS_POOL.length] - Math.floor(g / SEASONS_POOL.length),
                   week: 1 + Math.floor(r() * 14), aWon: aWon, margin: margin });
    }
    games.sort(function (x, y) { return y.season - x.season || y.week - x.week; });
    var avg = +(games.reduce(function (s2, gm) { return s2 + gm.margin; }, 0) / total).toFixed(1);
    var ser = { met: true, a: a, b: b, total: total, aWins: aw, bWins: total - aw, avg: avg, games: games };
    return (SERIES[key] = ser);
  }

  // featured overrides for narrative pairs
  var FEATURED = {
    "sully_harry": { total: 18, aWins: 11, avg: 8.4 },
    "sully_dan":   { total: 26, aWins: 12, avg: 17.2 },
    "mike_tom":    { total: 13, aWins: 11, avg: 26.5 },
    "dave_chris":  { total: 15, aWins: 11, avg: 19.0 }
  };
  function applyFeatured(ser) {
    if (!ser.met) return ser;
    var aId = MGRS[ser.a].id, bId = MGRS[ser.b].id;
    var f = FEATURED[aId + "_" + bId];
    if (f) { ser.total = f.total; ser.aWins = f.aWins; ser.bWins = f.total - f.aWins; ser.avg = f.avg; }
    return ser;
  }

  // i's perspective vs j
  function h2h(i, j) {
    var ser = applyFeatured(buildSeries(i, j));
    if (!ser.met) return { met: false };
    var iIsA = i === ser.a;
    var iw = iIsA ? ser.aWins : ser.bWins;
    var jw = iIsA ? ser.bWins : ser.aWins;
    return { met: true, total: ser.total, iWins: iw, jWins: jw, avg: ser.avg,
             pct: iw / ser.total, ser: ser, iIsA: iIsA };
  }

  function lerp(a, b, t) { return Math.round(a + (b - a) * t); }
  function heatColor(p) {
    // p: row-owner win-pct. 0 -> loss red, .5 -> steel, 1 -> win green
    var loss = [239, 71, 97], steel = [57, 65, 78], win = [52, 211, 158];
    var c;
    if (p < 0.5) { var t = p / 0.5; c = [lerp(loss[0], steel[0], t), lerp(loss[1], steel[1], t), lerp(loss[2], steel[2], t)]; }
    else { var u = (p - 0.5) / 0.5; c = [lerp(steel[0], win[0], u), lerp(steel[1], win[1], u), lerp(steel[2], win[2], u)]; }
    return "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")";
  }

  var rivBuilt = false, selCell = null;
  function buildRivalries() {
    if (rivBuilt) return; rivBuilt = true;
    var mx = document.getElementById("rivMatrix");
    mx.style.gridTemplateColumns = "110px repeat(" + N + ", 1fr)";

    var html = '<div class="hm-corner hm-head"></div>';
    MGRS.forEach(function (m) { html += '<div class="hm-head" data-col="' + m.id + '">' + m.av + '</div>'; });

    MGRS.forEach(function (rm, i) {
      html += '<div class="hm-rowhead" data-row="' + rm.id + '"><span class="avatar" style="width:24px;height:24px;font-size:10px">' + rm.av + '</span>' + rm.name + '</div>';
      MGRS.forEach(function (cm, j) {
        if (i === j) { html += '<div class="hm-cell diag" aria-hidden="true">·</div>'; return; }
        var d = h2h(i, j);
        if (!d.met) { html += '<div class="hm-cell hm-gap" title="' + rm.name + ' vs ' + cm.name + ' — never met / pre-2016">—</div>'; return; }
        var pctTxt = Math.round(d.pct * 100);
        var col = heatColor(d.pct);
        var strong = Math.abs(d.pct - 0.5) > 0.2;
        html += '<div class="hm-cell" role="gridcell" tabindex="0" data-i="' + i + '" data-j="' + j + '" ' +
                'title="' + rm.name + ' ' + d.iWins + '–' + d.jWins + ' ' + cm.name + '" ' +
                'style="background:' + col + ';color:' + (strong ? "#0b0e13" : "#e7ecf3") + '">' + pctTxt + '</div>';
      });
    });
    mx.innerHTML = html;

    mx.addEventListener("click", function (e) {
      var c = e.target.closest(".hm-cell[data-i]"); if (!c) return; selectCell(c);
    });
    mx.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      var c = e.target.closest(".hm-cell[data-i]"); if (!c) return; e.preventDefault(); selectCell(c);
    });
    // default featured: sully (0) vs harry (2)
    renderH2H(0, 2);
    markSel(0, 2);
  }

  function selectCell(c) {
    var i = +c.getAttribute("data-i"), j = +c.getAttribute("data-j");
    renderH2H(i, j); markSel(i, j);
  }
  function markSel(i, j) {
    var mx = document.getElementById("rivMatrix");
    if (selCell) selCell.classList.remove("sel");
    var c = mx.querySelector('.hm-cell[data-i="' + i + '"][data-j="' + j + '"]');
    if (c) { c.classList.add("sel"); selCell = c; }
  }

  function tag(av) { return '<span class="avatar lg">' + av + '</span>'; }
  function renderH2H(i, j) {
    var ri = MGRS[i], rj = MGRS[j], d = h2h(i, j);
    var panel = document.getElementById("h2hPanel");
    if (!d.met) {
      panel.innerHTML = '<div class="h2h-empty"><div class="datagap" style="margin:0 auto 14px;width:max-content">Never met</div>' +
        '<p>' + ri.name + ' and ' + rj.name + ' have no scored meetings — different eras, or pre-2016.</p></div>';
      return;
    }
    var ser = d.ser;
    // longest streak from i's view
    var streak = 0, run = 0, lastWinner = null;
    ser.games.forEach(function (g) {
      var iWon = (g.aWon === d.iIsA);
      if (iWon === lastWinner) run++; else { run = 1; lastWinner = iWon; }
      if (iWon && run > streak) streak = run;
    });
    var last = ser.games[0];
    var iWonLast = (last.aWon === d.iIsA);
    var lead = d.iWins === d.jWins ? "Series tied" : (d.iWins > d.jWins ? ri.name + " leads" : rj.name + " leads");

    var logRows = ser.games.slice(0, 6).map(function (g) {
      var iWon = (g.aWon === d.iIsA);
      return '<div class="log-row"><span class="log-when">' + g.season + ' · w' + (g.week < 10 ? "0" + g.week : g.week) + '</span>' +
        '<span class="log-result"><span class="log-tag ' + (iWon ? "w" : "l") + '">' + (iWon ? "W" : "L") + '</span>' +
        '<span style="color:var(--text-muted)">' + (iWon ? ri.name + " def " + rj.name : rj.name + " def " + ri.name) + '</span></span>' +
        '<span class="log-margin ' + (iWon ? "w" : "l") + '">' + (iWon ? "+" : "−") + g.margin.toFixed(1) + '</span></div>';
    }).join("");

    panel.innerHTML =
      '<div class="h2h-head">' +
        '<div class="h2h-owner">' + tag(ri.av) + '<span class="chip-name">' + ri.name + '</span></div>' +
        '<div class="h2h-vs">VS</div>' +
        '<div class="h2h-owner">' + tag(rj.av) + '<span class="chip-name">' + rj.name + '</span></div>' +
      '</div>' +
      '<div class="h2h-tally">' +
        '<div class="h2h-big l">' + d.iWins + '</div>' +
        '<div class="h2h-mid"><div class="stat-sub">all-time</div><div class="card-eyebrow" style="margin-top:4px">' + lead + '</div></div>' +
        '<div class="h2h-big r">' + d.jWins + '</div>' +
      '</div>' +
      '<div class="h2h-stats">' +
        '<div class="h2h-stat"><div class="k">Meetings</div><div class="v">' + d.total + '</div></div>' +
        '<div class="h2h-stat"><div class="k">Avg margin</div><div class="v">' + d.avg.toFixed(1) + '</div></div>' +
        '<div class="h2h-stat"><div class="k">' + ri.name + ' win-pct</div><div class="v" style="color:' + (d.pct >= .5 ? "var(--win)" : "var(--loss)") + '">.' + ("" + Math.round(d.pct * 1000)).padStart(3, "0") + '</div></div>' +
        '<div class="h2h-stat"><div class="k">Longest ' + ri.name + ' streak</div><div class="v">' + streak + 'W</div></div>' +
      '</div>' +
      '<div class="h2h-insight">Last met <b>' + last.season + ' · wk ' + last.week + '</b> — ' +
        (iWonLast ? ri.name : rj.name) + ' by ' + last.margin.toFixed(1) + '. ' +
        (d.avg < 12 ? "A genuine coin-flip — decided by single digits more often than not." :
         d.total >= 22 ? "One of the most-played pairings in the league." :
         Math.abs(d.pct - .5) > .25 ? "Historically lopsided." : "Evenly matched over the years.") +
      '</div>' +
      '<div class="h2h-log"><div class="h2h-log-title">Recent meetings · ' + ri.name + "'s view</div>" + logRows +
        '<div class="foot-note" style="margin-top:14px"><span class="datagap sm">pre-2016 meetings not scored</span></div></div>';
  }

  render();
})();
