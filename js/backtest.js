/*
 * Backtest: ranks the universe by a chosen factor at each rebalance date and
 * forms an equal-weighted long/short (or long/short-only) quantile portfolio,
 * holding to the next rebalance. Returns are chained into an equity curve and
 * compared against an equal-weight benchmark of the same universe.
 */
const Backtest = (() => {
  let prices = null;       // { dates, series }
  let fundHistory = null;  // { asOf, fields, tickers: { T: [[filed, {raw}], ...] } }
  let fundIndex = null;    // { ticker: [rawObjOrNull per price-date index] }
  let chart = null;

  const el = (id) => document.getElementById(id);

  function init(state) {
    prices = state.prices;
    fundHistory = state.fundHistory || {};
    fundIndex = buildFundIndex();
    chart = new LineChart(el("equity-chart"));
    buildControls();
    run();
  }

  function buildControls() {
    // factor dropdown grouped by Price / Fundamental
    const sel = el("bt-factor");
    const groups = {};
    for (const f of FACTORS) (groups[f.group] ||= []).push(f);
    sel.innerHTML = Object.entries(groups).map(([g, fs]) =>
      `<optgroup label="${g}">` +
      fs.map((f) => `<option value="${f.id}">${f.label}</option>`).join("") +
      `</optgroup>`).join("");
    sel.value = "mom12_1";

    el("bt-run").onclick = run;
    el("bt-log").onchange = () => { if (lastResult) draw(lastResult); };
  }

  // For each ticker, forward-fill its point-in-time raw fundamentals onto every
  // price-date index: index i gets the latest filing with date <= dates[i].
  function buildFundIndex() {
    const dates = prices.dates;
    const tickers = fundHistory.tickers || {};
    const fund = {};
    for (const t in tickers) {
      const entries = tickers[t];               // [[filedDate, rawObj], ...] sorted
      const arr = new Array(dates.length).fill(null);
      let j = 0, current = null;
      for (let i = 0; i < dates.length; i++) {
        while (j < entries.length && entries[j][0] <= dates[i]) {
          current = entries[j][1];
          j++;
        }
        arr[i] = current;
      }
      fund[t] = arr;
    }
    return fund;
  }

  // Count distinct filing dates — a proxy for how much point-in-time history
  // exists, used to warn when fundamental factors aren't yet meaningful.
  function snapshotCount() {
    const set = new Set();
    const tk = fundHistory.tickers || {};
    for (const t in tk) for (const e of tk[t]) set.add(e[0]);
    return set.size;
  }

  let lastResult = null;

  function run() {
    const factor = FACTOR_BY_ID[el("bt-factor").value];
    const step = parseInt(el("bt-step").value, 10);
    const mode = el("bt-mode").value;           // ls | long | short
    const bucket = parseFloat(el("bt-bucket").value);

    const ctx = { series: prices.series, dates: prices.dates, fund: fundIndex };
    const snapCount = snapshotCount();
    const tickers = Object.keys(prices.series);
    const n = prices.dates.length;

    let eq = 1, bench = 1;
    const curve = [{ date: prices.dates[0], strat: 1, bench: 1 }];
    const rets = [];
    let nLong = 0, nShort = 0, rebalances = 0;

    for (let i = 0; i + step < n; i += step) {
      const obs = [];
      for (const t of tickers) {
        const p0 = prices.series[t][i];
        const p1 = prices.series[t][i + step];
        if (p0 == null || p1 == null || p0 <= 0) continue;
        const fv = factor.value(t, i, ctx);
        if (fv == null || !isFinite(fv)) continue;
        obs.push({ fwd: p1 / p0 - 1, fv });
      }
      if (obs.length < 10) continue;

      const benchRet = mean(obs.map((o) => o.fwd));
      // sort so the "best" factor values come first
      obs.sort((a, b) => (factor.betterLow ? a.fv - b.fv : b.fv - a.fv));
      const k = Math.max(1, Math.floor(obs.length * bucket));
      const longs = obs.slice(0, k);
      const shorts = obs.slice(obs.length - k);
      const longRet = mean(longs.map((o) => o.fwd));
      const shortRet = mean(shorts.map((o) => o.fwd));

      let r;
      if (mode === "ls") r = longRet - shortRet;
      else if (mode === "long") r = longRet;
      else r = -shortRet;

      eq *= 1 + r;
      bench *= 1 + benchRet;
      rets.push(r);
      curve.push({ date: prices.dates[i + step], strat: eq, bench });
      nLong = longs.length; nShort = shorts.length; rebalances++;
    }

    const ppy = 12 / step;
    const years = rets.length / ppy;
    const stats = {
      cagr: cagr(eq, years),
      vol: std(rets) * Math.sqrt(ppy),
      sharpe: std(rets) > 0 ? (mean(rets) / std(rets)) * Math.sqrt(ppy) : null,
      maxDd: maxDrawdown(curve.map((c) => c.strat)),
      hit: rets.length ? rets.filter((r) => r > 0).length / rets.length : null,
      rebalances,
      benchCagr: cagr(bench, years),
      nLong, nShort,
    };

    lastResult = { curve, stats, factor, mode, snapCount };
    draw(lastResult);
  }

  function draw(result) {
    const { curve, stats, factor, mode, snapCount } = result;
    const log = el("bt-log").checked;

    // warn when a fundamental factor lacks point-in-time history to test on
    const warn = el("bt-warn");
    const isFund = factor.group === GROUP_FUND;
    if (isFund && (snapCount < 6 || stats.rebalances < 6)) {
      warn.style.display = "block";
      warn.textContent =
        `⚠ "${factor.label}" found only ${snapCount} point-in-time filing date(s)` +
        ` / ${stats.rebalances} rebalance(s). Run ` +
        `scripts/build_history.py to populate SEC EDGAR fundamentals, then this ` +
        `factor backtests over real history. Price factors work today regardless.`;
    } else {
      warn.style.display = "none";
    }

    chart.setData({
      dates: curve.map((c) => c.date),
      log,
      series: [
        { name: `Strategy (${labelMode(mode)})`, color: "#5b9cff",
          values: curve.map((c) => c.strat) },
        { name: "Universe (equal-weight)", color: "#9aa3b8",
          values: curve.map((c) => c.bench) },
      ],
    });

    const cards = [
      ["CAGR", pctOrDash(stats.cagr), stats.cagr >= 0 ? "pos" : "neg"],
      ["Volatility", pctOrDash(stats.vol), ""],
      ["Sharpe", stats.sharpe == null ? "–" : stats.sharpe.toFixed(2),
        stats.sharpe >= 0 ? "pos" : "neg"],
      ["Max Drawdown", pctOrDash(stats.maxDd), "neg"],
      ["Hit Rate", pctOrDash(stats.hit), ""],
      ["Benchmark CAGR", pctOrDash(stats.benchCagr), ""],
      ["Rebalances", String(stats.rebalances), ""],
      ["Names / Side", `${stats.nLong}`, ""],
    ];
    el("bt-stats").innerHTML = cards.map(([k, v, cls]) =>
      `<div class="stat"><div class="stat-k">${k}</div>` +
      `<div class="stat-v ${cls}">${v}</div></div>`).join("");
  }

  const pctOrDash = (v) => (v == null || !isFinite(v) ? "–" : fmtSignedPct(v));
  const labelMode = (m) => (m === "ls" ? "long-short" : m === "long" ? "long-only" : "short-only");

  return { init };
})();
