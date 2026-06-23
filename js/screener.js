/*
 * Screener: filters the universe, computes a composite z-score from the
 * selected metrics, and renders a sortable ranking table.
 */
const Screener = (() => {
  let rows = [];                 // full universe (array of records)
  let active = new Set();        // metric keys currently in the composite
  let sortKey = "_score";
  let sortDir = -1;              // -1 desc, 1 asc

  const el = (id) => document.getElementById(id);

  function init(state) {
    rows = state.screen.map((r) => ({ ...r }));
    buildControls();
    applyPreset("Multi-Factor");
  }

  function buildControls() {
    // Preset buttons
    const presetBox = el("presets");
    presetBox.innerHTML = "";
    for (const name of Object.keys(PRESETS)) {
      const b = document.createElement("button");
      b.className = "preset-btn";
      b.textContent = name;
      b.onclick = () => { applyPreset(name); setActivePreset(b); };
      presetBox.appendChild(b);
    }

    // Metric checkboxes grouped by family
    const metricBox = el("metric-toggles");
    metricBox.innerHTML = "";
    for (const group of METRIC_GROUPS) {
      const groupMetrics = METRICS.filter((m) => m.group === group && m.rankable !== false);
      if (!groupMetrics.length) continue;
      const wrap = document.createElement("div");
      wrap.className = "metric-group";
      wrap.innerHTML = `<div class="metric-group-title">${group}</div>`;
      for (const m of groupMetrics) {
        const id = "mt_" + m.key;
        const lab = document.createElement("label");
        lab.className = "metric-check";
        lab.innerHTML =
          `<input type="checkbox" id="${id}" data-key="${m.key}"> ` +
          `<span>${m.label}</span>` +
          `<span class="dir">${m.betterLow ? "↓" : "↑"}</span>`;
        lab.querySelector("input").onchange = (e) => {
          if (e.target.checked) active.add(m.key);
          else active.delete(m.key);
          render();
        };
        wrap.appendChild(lab);
      }
      metricBox.appendChild(wrap);
    }

    // Sector filter
    const sectors = [...new Set(rows.map((r) => r.sector).filter(Boolean))].sort();
    const sel = el("sector-filter");
    sel.innerHTML = `<option value="">All sectors</option>` +
      sectors.map((s) => `<option value="${s}">${s}</option>`).join("");
    sel.onchange = render;

    el("search").oninput = render;
    el("min-mcap").onchange = render;
    el("top-n").onchange = render;
    el("export-csv").onclick = exportCsv;
  }

  function setActivePreset(btn) {
    document.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("on"));
    if (btn) btn.classList.add("on");
  }

  function applyPreset(name) {
    active = new Set(PRESETS[name]);
    // sync checkboxes
    document.querySelectorAll("#metric-toggles input").forEach((cb) => {
      cb.checked = active.has(cb.dataset.key);
    });
    // mark the matching preset button active
    document.querySelectorAll(".preset-btn").forEach((b) => {
      b.classList.toggle("on", b.textContent === name);
    });
    render();
  }

  function filtered() {
    const sector = el("sector-filter").value;
    const q = el("search").value.trim().toLowerCase();
    const minMcap = parseFloat(el("min-mcap").value) || 0;
    return rows.filter((r) => {
      if (sector && r.sector !== sector) return false;
      if (minMcap && (!(r.marketCap >= minMcap * 1e9))) return false;
      if (q && !(`${r.ticker} ${r.name}`.toLowerCase().includes(q))) return false;
      return true;
    });
  }

  function computeScores(data) {
    const keys = [...active];
    const z = {};
    for (const k of keys) z[k] = zScores(data.map((r) => r[k]));
    data.forEach((r, idx) => {
      let sum = 0, wsum = 0;
      for (const k of keys) {
        const zk = z[k][idx];
        if (zk == null) continue;
        const dir = METRIC_BY_KEY[k].betterLow ? -1 : 1;
        sum += dir * zk;
        wsum += 1;
      }
      r._score = wsum > 0 ? sum / wsum : null;
    });
  }

  function render() {
    const data = filtered();
    computeScores(data);

    // sort
    data.sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      av = av == null || !isFinite(av) ? -Infinity : av;
      bv = bv == null || !isFinite(bv) ? -Infinity : bv;
      return (av - bv) * sortDir;
    });

    const topN = parseInt(el("top-n").value, 10) || data.length;
    const shown = data.slice(0, topN);

    const cols = columns();
    const thead = `<tr>${cols.map((c) =>
      `<th data-key="${c.key}" class="${c.num ? "num" : ""} ${sortKey === c.key ? "sorted" : ""}">${c.label}${
        sortKey === c.key ? (sortDir === -1 ? " ▼" : " ▲") : ""
      }</th>`).join("")}</tr>`;

    const body = shown.map((r, i) => {
      const cells = cols.map((c) => {
        if (c.key === "_rank") return `<td class="num rank">${i + 1}</td>`;
        if (c.key === "ticker") return `<td class="ticker">${r.ticker}</td>`;
        if (c.key === "name") return `<td class="name" title="${r.name}">${r.name}</td>`;
        if (c.key === "sector") return `<td class="sector">${r.sector || "–"}</td>`;
        if (c.key === "_score")
          return `<td class="num score">${r._score == null ? "–" : r._score.toFixed(2)}</td>`;
        const m = METRIC_BY_KEY[c.key];
        const raw = r[c.key];
        const cls = m && m.fmt === "pct" && raw != null
          ? (raw >= 0 ? "pos" : "neg") : "";
        return `<td class="num ${cls}">${fmtValue(raw, m ? m.fmt : "num")}</td>`;
      });
      return `<tr>${cells.join("")}</tr>`;
    }).join("");

    el("screen-table").innerHTML =
      `<thead>${thead}</thead><tbody>${body}</tbody>`;
    el("screen-count").textContent =
      `${shown.length} of ${data.length} stocks (${active.size} metrics)`;

    // wire header sorting
    el("screen-table").querySelectorAll("th").forEach((th) => {
      const key = th.dataset.key;
      if (!key) return;
      th.onclick = () => {
        if (sortKey === key) sortDir *= -1;
        else { sortKey = key; sortDir = key === "ticker" || key === "name" ? 1 : -1; }
        render();
      };
    });
  }

  function columns() {
    const base = [
      { key: "_rank", label: "#", num: true },
      { key: "ticker", label: "Ticker" },
      { key: "name", label: "Name" },
      { key: "sector", label: "Sector" },
      { key: "_score", label: "Score", num: true },
      { key: "marketCap", label: "Mkt Cap", num: true },
      { key: "price", label: "Price", num: true },
    ];
    // append active scoring metrics (skip ones already shown)
    const shownKeys = new Set(base.map((c) => c.key));
    for (const k of active) {
      if (shownKeys.has(k)) continue;
      base.push({ key: k, label: METRIC_BY_KEY[k].label, num: true });
    }
    return base;
  }

  function exportCsv() {
    const data = filtered();
    computeScores(data);
    data.sort((a, b) => (b._score ?? -Infinity) - (a._score ?? -Infinity));
    const cols = ["ticker", "name", "sector", "_score", ...METRICS.map((m) => m.key)];
    const head = cols.join(",");
    const lines = data.map((r) =>
      cols.map((c) => {
        const v = c === "_score" ? r._score : r[c];
        if (v == null) return "";
        if (typeof v === "string") return `"${v.replace(/"/g, '""')}"`;
        return v;
      }).join(",")
    );
    const blob = new Blob([head + "\n" + lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "screen.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return { init };
})();
