// The aimport trace viewer (/viewer/traces/<entry>): windows of the written recording from /qa/traces on this
// origin only, drawn with uPlot. Pan and zoom ask for a new window. The bad-channel panel reads the written
// channels.tsv (/qa/channels) and saves marks to it (POST, same origin). Text from the data (channel names,
// event labels, reasons) is set with textContent or input values, never parsed as HTML.
(function () {
  "use strict";
  var MAX_CHANNELS = 64;
  var MAX_WINDOW = 600;
  var BAD = "#a0aec0"; // the engine sends every other colour (channel.colour), one per type; HbO red, HbR blue

  var entry = document.body.getAttribute("data-entry");
  var $ = function (id) { return document.getElementById(id); };
  var state = { t0: 0, len: 10, ch: null, duration: null, all: [] };
  var plot = null;
  var current = null;

  function status(text) { $("tr-status").textContent = text || ""; }

  function url() {
    var q = "t0=" + state.t0.toFixed(4) + "&t1=" + (state.t0 + state.len).toFixed(4);
    if (state.ch) q += "&ch=" + state.ch.join(",");
    return "/qa/traces/" + encodeURIComponent(entry) + "?" + q;
  }

  function json(r) {
    return r.json().catch(function () { return null; }).then(function (body) {
      if (!r.ok) throw new Error(body && typeof body.detail === "string" ? body.detail : "HTTP " + r.status);
      return body;
    });
  }

  function load() {
    status("loading…");
    fetch(url(), { credentials: "same-origin" })
      .then(json)
      .then(function (data) { status(""); show(data); })
      .catch(function (e) { status("Could not load the traces: " + e.message); });
  }

  function median(values) {
    var v = values.filter(function (x) { return x !== null && isFinite(x); }).sort(function (a, b) { return a - b; });
    return v.length ? v[Math.floor(v.length / 2)] : 0;
  }

  function span(values) {
    var v = values.filter(function (x) { return x !== null && isFinite(x); }).sort(function (a, b) { return a - b; });
    if (!v.length) return 0;
    return v[Math.floor(v.length * 0.95)] - v[Math.floor(v.length * 0.05)];
  }

  // rows: one per channel, except NIRS pairs, which share a row
  function layout(data) {
    var rowOf = {};
    var rows = [];
    var pairOf = {};
    data.pairs.forEach(function (p) { pairOf[p[0]] = [p, 0]; pairOf[p[1]] = [p, 1]; });
    data.channels.forEach(function (c) {
      var pair = pairOf[c.i];
      if (pair && rowOf[pair[0][1 - pair[1]]] !== undefined) {
        rowOf[c.i] = rowOf[pair[0][1 - pair[1]]];
        return;
      }
      rowOf[c.i] = rows.length;
      rows.push(pair ? c.name.replace(/ \S+$/, "") : c.name);
    });
    return { rowOf: rowOf, rows: rows, pairOf: pairOf };
  }

  function show(data) {
    current = data;
    state.duration = data.duration;
    state.t0 = data.t0;
    state.all = data.all_channels || state.all;
    if (!state.ch) state.ch = data.channels.map(function (c) { return c.i; });
    $("tr-t0").value = +data.t0.toFixed(3);
    $("tr-len").value = +state.len.toFixed(3);
    $("tr-info").textContent = data.t0.toFixed(2) + "–" + data.t1.toFixed(2) + " s of " + data.duration.toFixed(1) +
      " s · " + data.sfreq + " Hz · " + data.channels.length + " of " + state.all.length + " channels";
    picker();

    var lay = layout(data);
    var scale = {};
    data.channels.forEach(function (c, k) {
      (scale[c.type] = scale[c.type] || []).push(span(data.y[k]));
    });
    Object.keys(scale).forEach(function (t) { scale[t] = median(scale[t]) || 1; });
    $("tr-scales").textContent = Object.keys(scale).sort().map(function (t) {
      var unit = (data.channels.find(function (c) { return c.type === t; }) || {}).unit || "";
      return t + ": " + (+scale[t].toPrecision(3)) + " " + unit + " per row";
    }).join(" · ") + (data.pairs.length ? (data.channels.some(function (c) { return c.type === "hbo"; })
      ? " · HbO red, HbR blue" : " · lower wavelength red, higher blue") : "");

    var series = [{ label: "time (s)" }];
    var columns = [data.x];
    data.channels.forEach(function (c, k) {
      var centre = median(data.y[k]);
      var row = lay.rowOf[c.i];
      columns.push(data.y[k].map(function (v) {
        return v === null ? null : -row + (v - centre) / scale[c.type] * 0.8;
      }));
      series.push({
        label: c.name,
        stroke: c.bad ? BAD : c.colour,
        width: 1,
        dash: c.bad ? [4, 3] : undefined,
        points: { show: false },
      });
    });

    var panel = $("tr-plot");
    var width = Math.max(480, panel.clientWidth || 900);
    var height = Math.max(260, 26 * lay.rows.length + 70);
    var opts = {
      width: width,
      height: height,
      legend: { show: false },
      cursor: { drag: { x: true, y: false, setScale: false } },
      scales: { x: { time: false }, y: { range: [-lay.rows.length + 0.3, 0.9] } },
      axes: [
        { label: "time (s)", stroke: "#718096", grid: { stroke: "#e2e8f0", width: 1 } },
        {
          stroke: "#2d3748", size: 110, grid: { show: false },
          splits: function () { return lay.rows.map(function (_, r) { return -r; }); },
          values: function (u, splits) { return splits.map(function (s) { return lay.rows[-s] || ""; }); },
        },
      ],
      series: series,
      hooks: {
        draw: [markers],
        setSelect: [function (u) {
          if (u.select.width < 4) return;
          var a = u.posToVal(u.select.left, "x");
          var b = u.posToVal(u.select.left + u.select.width, "x");
          u.setSelect({ left: 0, width: 0, top: 0, height: 0 }, false);
          go(a, b - a);
        }],
      },
    };
    if (plot) plot.destroy();
    panel.textContent = "";
    plot = new uPlot(opts, columns, panel);
  }

  // event markers: a dashed line and the label (textContent) at each onset, over the plot
  function markers(u) {
    var over = u.over;
    Array.prototype.slice.call(over.querySelectorAll(".tr-event-line, .tr-event-label")).forEach(function (n) {
      n.remove();
    });
    if (!current) return;
    current.events.forEach(function (e) {
      if (e.onset < current.t0 || e.onset > current.t1) return;
      var left = u.valToPos(e.onset, "x");
      var line = document.createElement("div");
      line.className = "tr-event-line";
      line.style.left = left + "px";
      var label = document.createElement("div");
      label.className = "tr-event-label";
      label.style.left = left + 2 + "px";
      label.textContent = e.label;
      over.appendChild(line);
      over.appendChild(label);
      if (left + 2 + label.offsetWidth > over.clientWidth) label.style.left = left - 2 - label.offsetWidth + "px";
    });
  }

  function picker() {
    var box = $("tr-channels");
    if (box.childElementCount === state.all.length && box.childElementCount) { count(); return; }
    box.textContent = "";
    var on = {};
    (state.ch || []).forEach(function (i) { on[i] = true; });
    state.all.forEach(function (c) {
      var label = document.createElement("label");
      var input = document.createElement("input");
      input.type = "checkbox";
      input.value = String(c.i);
      input.checked = !!on[c.i];
      input.addEventListener("change", count);
      label.appendChild(input);
      label.appendChild(document.createTextNode(" " + c.name + (c.bad ? " (bad)" : "")));
      label.title = c.type;
      if (c.bad) label.className = "tr-bad";
      box.appendChild(label);
    });
    count();
  }

  function checked() {
    return Array.prototype.slice.call($("tr-channels").querySelectorAll("input:checked")).map(function (n) {
      return +n.value;
    });
  }

  function count() {
    var n = checked().length;
    $("tr-count").textContent = "(" + n + " of " + state.all.length + ", at most " + MAX_CHANNELS + ")";
    Array.prototype.slice.call($("tr-channels").querySelectorAll("input")).forEach(function (input) {
      input.disabled = !input.checked && n >= MAX_CHANNELS;
    });
  }

  function go(t0, len) {
    len = Math.min(MAX_WINDOW, Math.max(0.01, len));
    var end = state.duration === null ? Infinity : state.duration;
    t0 = Math.max(0, Math.min(t0, end - len));
    state.t0 = t0;
    state.len = len;
    load();
  }

  // --- bad channels: the written channels.tsv (GET /qa/channels), marked here and saved with POST ---------
  // Only this page's own script sends X-Aimport-Viewer; the engine also checks that the Origin is its own.
  var marks = { rows: [], changed: {}, max: 80 };

  function saveStatus(text) { $("tr-save-status").textContent = text || ""; }

  function loadMarks() {
    fetch("/qa/channels/" + encodeURIComponent(entry), { credentials: "same-origin" })
      .then(json)
      .then(function (body) {
        marks.max = body.max_reason || 80;
        var list = $("tr-reasons");
        list.textContent = "";
        (body.reasons || []).forEach(function (r) {
          var option = document.createElement("option");
          option.value = r;
          list.appendChild(option);
        });
        setRows(body.channels || []);
      })
      .catch(function (e) { saveStatus("Could not load the channel table: " + e.message); });
  }

  function setRows(rows) {
    marks.rows = rows;
    marks.changed = {};
    drawMarks();
  }

  function markOf(row) { return marks.changed[row.name] || row; }

  function badCount() {
    return marks.rows.filter(function (row) { return markOf(row).status === "bad"; }).length;
  }

  function counts() {
    $("tr-bad-count").textContent = "(" + badCount() + " of " + marks.rows.length + " bad" +
      (Object.keys(marks.changed).length ? ", " + Object.keys(marks.changed).length + " unsaved" : "") + ")";
    $("tr-save").disabled = !Object.keys(marks.changed).length;
  }

  function setMark(row, status, reason) {
    var description = status === "bad" ? (reason || "").trim() || null : null;
    if (status === row.status && description === (row.description || null)) delete marks.changed[row.name];
    else marks.changed[row.name] = { name: row.name, status: status, description: description };
    counts();
  }

  function cell(tr, text) {
    var td = document.createElement("td");
    td.textContent = text;
    tr.appendChild(td);
    return td;
  }

  function drawMarks() {
    var body = $("tr-mark-list");
    var filter = ($("tr-mark-filter").value || "").toLowerCase();
    body.textContent = "";
    marks.rows.forEach(function (row) {
      if (filter && row.name.toLowerCase().indexOf(filter) < 0) return;
      var mark = markOf(row);
      var tr = document.createElement("tr");
      tr.className = mark.status === "bad" ? "tr-is-bad" : "";
      cell(tr, row.name).className = "tr-mark-name";
      cell(tr, row.type || "");
      var toggle = document.createElement("input");
      toggle.type = "checkbox";
      toggle.checked = mark.status === "bad";
      toggle.setAttribute("aria-label", "bad: " + row.name);
      cell(tr, "").appendChild(toggle);
      var reason = document.createElement("input");
      reason.type = "text";
      reason.maxLength = marks.max;
      reason.setAttribute("list", "tr-reasons");
      reason.placeholder = "reason (optional)";
      reason.value = mark.description || "";
      reason.disabled = !toggle.checked;
      reason.setAttribute("aria-label", "reason: " + row.name);
      cell(tr, "").appendChild(reason);
      toggle.addEventListener("change", function () {
        reason.disabled = !toggle.checked;
        tr.className = toggle.checked ? "tr-is-bad" : "";
        setMark(row, toggle.checked ? "bad" : "good", reason.value);
        if (toggle.checked) reason.focus();
      });
      reason.addEventListener("input", function () { setMark(row, "bad", reason.value); });
      body.appendChild(tr);
    });
    counts();
  }

  function save() {
    var changed = Object.keys(marks.changed).map(function (name) { return marks.changed[name]; });
    if (!changed.length) return;
    $("tr-save").disabled = true;
    saveStatus("saving, then validating the dataset again…");
    fetch("/qa/channels/" + encodeURIComponent(entry), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Aimport-Viewer": "1" },
      body: JSON.stringify({ channels: changed }),
    })
      .then(json)
      .then(function (body) {
        setRows(body.channels || []);
        var v = body.validation || {};
        saveStatus("Saved: " + body.bad + " bad channel" + (body.bad === 1 ? "" : "s") + " in channels.tsv; " +
          (v.ok ? "the dataset is valid." : "the dataset has " + v.error_count + " validation error(s)."));
        $("tr-channels").textContent = ""; // the picker shows the new (bad) labels
        load();
      })
      .catch(function (e) {
        saveStatus("Not saved: " + e.message);
        counts();
      });
  }

  $("tr-save").addEventListener("click", save);
  $("tr-mark-filter").addEventListener("input", drawMarks);

  $("tr-left").addEventListener("click", function () { go(state.t0 - state.len / 2, state.len); });
  $("tr-right").addEventListener("click", function () { go(state.t0 + state.len / 2, state.len); });
  $("tr-zin").addEventListener("click", function () { go(state.t0 + state.len / 4, state.len / 2); });
  $("tr-zout").addEventListener("click", function () { go(state.t0 - state.len / 2, state.len * 2); });
  $("tr-go").addEventListener("click", function () {
    go(parseFloat($("tr-t0").value) || 0, parseFloat($("tr-len").value) || state.len);
  });
  $("tr-apply").addEventListener("click", function () {
    var picked = checked();
    if (!picked.length) { status("Pick at least one channel."); return; }
    state.ch = picked.slice(0, MAX_CHANNELS);
    $("tr-picker").open = false;
    load();
  });
  document.addEventListener("keydown", function (e) {
    if (e.target && e.target.tagName === "INPUT") return;
    if (e.key === "ArrowLeft") $("tr-left").click();
    else if (e.key === "ArrowRight") $("tr-right").click();
    else if (e.key === "+" || e.key === "=") $("tr-zin").click();
    else if (e.key === "-") $("tr-zout").click();
  });
  window.addEventListener("resize", function () {
    if (plot) plot.setSize({ width: Math.max(480, $("tr-plot").clientWidth || 900), height: plot.height });
  });
  load();
  loadMarks();
})();
