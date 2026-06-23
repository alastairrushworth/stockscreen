/*
 * Central registry of metrics, screener presets, and backtest factors.
 * Loaded as a plain script — everything hangs off the global scope.
 *
 * Each metric: { key, label, group, fmt, betterLow, rankable }
 *   betterLow = true  -> a LOWER value is "better" (cheap, low-risk, low-debt)
 *   rankable  = false -> display-only, excluded from composite scoring
 */
const METRICS = [
  // Size / price (display only)
  { key: "marketCap", label: "Mkt Cap", group: "Size", fmt: "usdB", betterLow: false, rankable: false },
  { key: "price",     label: "Price",    group: "Size", fmt: "usd",  betterLow: false, rankable: false },

  // Valuation
  { key: "pe",            label: "P/E",         group: "Valuation", fmt: "x",   betterLow: true },
  { key: "forwardPe",     label: "Fwd P/E",     group: "Valuation", fmt: "x",   betterLow: true },
  { key: "pb",            label: "P/B",         group: "Valuation", fmt: "x",   betterLow: true },
  { key: "ps",            label: "P/S",         group: "Valuation", fmt: "x",   betterLow: true },
  { key: "evEbitda",      label: "EV/EBITDA",   group: "Valuation", fmt: "x",   betterLow: true },
  { key: "earningsYield", label: "Earn Yield",  group: "Valuation", fmt: "pct", betterLow: false },
  { key: "fcfYield",      label: "FCF Yield",   group: "Valuation", fmt: "pct", betterLow: false },

  // Quality / profitability
  { key: "roe",          label: "ROE",        group: "Quality", fmt: "pct", betterLow: false },
  { key: "roa",          label: "ROA",        group: "Quality", fmt: "pct", betterLow: false },
  { key: "grossMargin",  label: "Gross Mgn",  group: "Quality", fmt: "pct", betterLow: false },
  { key: "operMargin",   label: "Oper Mgn",   group: "Quality", fmt: "pct", betterLow: false },
  { key: "netMargin",    label: "Net Mgn",    group: "Quality", fmt: "pct", betterLow: false },
  { key: "debtToEquity", label: "Debt/Eq",    group: "Quality", fmt: "x",   betterLow: true },
  { key: "currentRatio", label: "Curr Ratio", group: "Quality", fmt: "x",   betterLow: false },

  // Momentum
  { key: "mom1",    label: "1M Ret",   group: "Momentum", fmt: "pct", betterLow: false },
  { key: "mom3",    label: "3M Ret",   group: "Momentum", fmt: "pct", betterLow: false },
  { key: "mom6",    label: "6M Ret",   group: "Momentum", fmt: "pct", betterLow: false },
  { key: "mom12_1", label: "12-1M Ret", group: "Momentum", fmt: "pct", betterLow: false },
  { key: "retYtd",  label: "YTD Ret",  group: "Momentum", fmt: "pct", betterLow: false },

  // Risk & income
  { key: "vol3m",    label: "Vol 3M",  group: "Risk & Income", fmt: "pct", betterLow: true },
  { key: "vol12m",   label: "Vol 12M", group: "Risk & Income", fmt: "pct", betterLow: true },
  { key: "beta",     label: "Beta",    group: "Risk & Income", fmt: "x",   betterLow: true },
  { key: "divYield", label: "Div Yld", group: "Risk & Income", fmt: "pct", betterLow: false },
  { key: "payout",   label: "Payout",  group: "Risk & Income", fmt: "pct", betterLow: true },

  // Growth
  { key: "revGrowth",  label: "Rev Growth",  group: "Growth", fmt: "pct", betterLow: false },
  { key: "earnGrowth", label: "Earn Growth", group: "Growth", fmt: "pct", betterLow: false },
];

const METRIC_BY_KEY = Object.fromEntries(METRICS.map((m) => [m.key, m]));

// Ordered list of metric groups for building UI sections.
const METRIC_GROUPS = ["Valuation", "Quality", "Momentum", "Risk & Income", "Growth", "Size"];

// Screener presets: metric keys blended with equal weight. Direction is taken
// from each metric's betterLow flag, so we only list which metrics to include.
const PRESETS = {
  "Value":          ["earningsYield", "fcfYield", "pb", "ps", "evEbitda"],
  "Quality":        ["roe", "roa", "grossMargin", "netMargin", "debtToEquity"],
  "Momentum":       ["mom12_1", "mom6", "mom3"],
  "Low Volatility": ["vol12m", "vol3m", "beta"],
  "Dividend":       ["divYield", "fcfYield", "payout"],
  "Multi-Factor":   ["earningsYield", "fcfYield", "roe", "grossMargin", "mom12_1", "vol12m", "debtToEquity"],
};

/*
 * Backtest factors. A factor.value(t, i, ctx) returns the factor value for
 * ticker t at month-index i, or null when undefined at that point in time.
 *   ctx = { series, dates, fundForIndex }  (see backtest.js)
 *
 * Price factors are fully historical. Fundamental factors read from the
 * accumulating point-in-time snapshot history and are only as deep as that
 * history (one snapshot on day one).
 */
function monthlyReturns(s, from, to) {
  // returns array of monthly simple returns for index range [from+1 .. to]
  const out = [];
  for (let j = from + 1; j <= to; j++) {
    const a = s[j - 1], b = s[j];
    if (a == null || b == null || a <= 0) return null;
    out.push(b / a - 1);
  }
  return out;
}

const PRICE_FACTORS = [
  {
    id: "mom12_1", label: "12-1M Momentum", group: "Price factors", betterLow: false,
    value: (t, i, ctx) => {
      const s = ctx.series[t]; if (i < 12) return null;
      const a = s[i - 12], b = s[i - 1];
      return a != null && b != null && a > 0 ? b / a - 1 : null;
    },
  },
  {
    id: "mom6_1", label: "6-1M Momentum", group: "Price factors", betterLow: false,
    value: (t, i, ctx) => {
      const s = ctx.series[t]; if (i < 6) return null;
      const a = s[i - 6], b = s[i - 1];
      return a != null && b != null && a > 0 ? b / a - 1 : null;
    },
  },
  {
    id: "mom3", label: "3M Momentum", group: "Price factors", betterLow: false,
    value: (t, i, ctx) => {
      const s = ctx.series[t]; if (i < 3) return null;
      const a = s[i - 3], b = s[i];
      return a != null && b != null && a > 0 ? b / a - 1 : null;
    },
  },
  {
    id: "rev1", label: "1M Reversal", group: "Price factors", betterLow: true,
    value: (t, i, ctx) => {
      const s = ctx.series[t]; if (i < 1) return null;
      const a = s[i - 1], b = s[i];
      return a != null && b != null && a > 0 ? b / a - 1 : null;
    },
  },
  {
    id: "lowvol12", label: "Low Volatility (12M)", group: "Price factors", betterLow: true,
    value: (t, i, ctx) => {
      const s = ctx.series[t]; if (i < 12) return null;
      const r = monthlyReturns(s, i - 12, i);
      return r ? std(r) : null;
    },
  },
];

/*
 * Fundamental factors are computed from *point-in-time raw items* (SEC EDGAR
 * TTM figures + balance-sheet instants) combined with the month's price, so
 * valuation ratios update monthly even though raw fundamentals change only on
 * filings. ctx.fund[t][i] is the raw item object active at month i (the latest
 * filing on or before that month), or null. Helper `fn(raw, marketCap)`.
 */
const GROUP_FUND = "Fundamental factors (point-in-time)";

function fundFactor(id, label, betterLow, fn) {
  return {
    id, label, group: GROUP_FUND, betterLow,
    value: (t, i, ctx) => {
      const series = ctx.fund[t];
      const raw = series ? series[i] : null;
      if (!raw) return null;
      const px = ctx.series[t][i];
      if (px == null || px <= 0) return null;
      const mc = raw.sh && raw.sh > 0 ? px * raw.sh : null;  // market cap
      const v = fn(raw, mc);
      return v == null || !isFinite(v) ? null : v;
    },
  };
}

// Valuation factors are expressed as yields (higher = cheaper = better) so all
// share a consistent "higher is better" direction.
const FUND_FACTORS = [
  fundFactor("ev_ep", "Earnings Yield (E/P)", false, (r, mc) => (r.ni != null && mc ? r.ni / mc : null)),
  fundFactor("ev_bp", "Book / Price (B/P)", false, (r, mc) => (r.eq > 0 && mc ? r.eq / mc : null)),
  fundFactor("ev_sp", "Sales / Price (S/P)", false, (r, mc) => (r.rev > 0 && mc ? r.rev / mc : null)),
  fundFactor("ev_fcf", "FCF Yield", false, (r, mc) => (r.cfo != null && r.capex != null && mc ? (r.cfo - r.capex) / mc : null)),
  fundFactor("ev_dy", "Dividend Yield", false, (r, mc) => (r.div != null && mc ? r.div / mc : null)),
  fundFactor("q_roe", "ROE", false, (r) => (r.ni != null && r.eq > 0 ? r.ni / r.eq : null)),
  fundFactor("q_roa", "ROA", false, (r) => (r.ni != null && r.assets > 0 ? r.ni / r.assets : null)),
  fundFactor("q_gm", "Gross Margin", false, (r) => (r.gp != null && r.rev > 0 ? r.gp / r.rev : null)),
  fundFactor("q_om", "Operating Margin", false, (r) => (r.oi != null && r.rev > 0 ? r.oi / r.rev : null)),
  fundFactor("q_de", "Low Debt / Equity", true, (r) => (r.debt != null && r.eq > 0 ? r.debt / r.eq : null)),
];

const FACTORS = [...PRICE_FACTORS, ...FUND_FACTORS];
const FACTOR_BY_ID = Object.fromEntries(FACTORS.map((f) => [f.id, f]));
