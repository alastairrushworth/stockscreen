/* App bootstrap: load data, wire tabs, init the screener and backtest. */

async function loadJson(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");
  tabs.forEach((t) => {
    t.onclick = () => {
      tabs.forEach((x) => x.classList.remove("on"));
      panels.forEach((p) => p.classList.remove("on"));
      t.classList.add("on");
      document.getElementById(t.dataset.panel).classList.add("on");
    };
  });
}

function showMeta(meta) {
  const bar = document.getElementById("meta-bar");
  const parts = [
    `<strong>${meta.universe}</strong>`,
    `${meta.priced}/${meta.count} priced`,
    `prices ${meta.priceStart} → ${meta.priceEnd}`,
    `updated ${meta.updated}`,
    `source: ${meta.source}`,
  ];
  bar.innerHTML = parts.join(" &nbsp;·&nbsp; ");
  if (meta.sample) {
    const note = document.getElementById("sample-note");
    note.style.display = "block";
    note.innerHTML =
      "⚠ Showing <strong>synthetic sample data</strong>. Numbers are random and " +
      "for demo only. Enable the GitHub Actions job (or run " +
      "<code>python scripts/fetch_data.py</code>) to populate real S&P 500 data.";
  }
}

async function main() {
  setupTabs();
  try {
    const [meta, screen, prices, fundHistory] = await Promise.all([
      loadJson("data/meta.json"),
      loadJson("data/screen.json"),
      loadJson("data/prices_monthly.json"),
      loadJson("data/fundamentals_history.json").catch(() => ({})),
    ]);
    showMeta(meta);
    const state = { meta, screen, prices, fundHistory };
    Screener.init(state);
    Backtest.init(state);
  } catch (err) {
    document.getElementById("meta-bar").innerHTML =
      `<span class="error">Failed to load data: ${err.message}. ` +
      `If running locally, serve over HTTP (e.g. <code>python -m http.server</code>) ` +
      `rather than opening the file directly.</span>`;
    console.error(err);
  }
}

main();
