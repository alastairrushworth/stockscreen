/* Small math + formatting helpers shared across the app. */

function mean(arr) {
  if (!arr.length) return 0;
  let s = 0;
  for (const v of arr) s += v;
  return s / arr.length;
}

// Sample standard deviation (n-1). Returns 0 for <2 points.
function std(arr) {
  if (arr.length < 2) return 0;
  const m = mean(arr);
  let s = 0;
  for (const v of arr) s += (v - m) * (v - m);
  return Math.sqrt(s / (arr.length - 1));
}

function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}

/*
 * Cross-sectional z-scores, winsorised to +/-3 sigma. Input may contain
 * null/NaN; those positions return null. Output aligns to the input array.
 */
function zScores(vals) {
  const present = vals.filter((v) => v != null && isFinite(v));
  if (present.length < 3) return vals.map(() => null);
  const m = mean(present);
  const s = std(present);
  if (s === 0) return vals.map(() => null);
  return vals.map((v) =>
    v == null || !isFinite(v) ? null : clamp((v - m) / s, -3, 3)
  );
}

// Compound annual growth rate from an equity multiple over `years`.
function cagr(endMultiple, years) {
  if (years <= 0 || endMultiple <= 0) return null;
  return Math.pow(endMultiple, 1 / years) - 1;
}

// Largest peak-to-trough drawdown of an equity curve (array of multiples).
function maxDrawdown(equity) {
  let peak = -Infinity;
  let mdd = 0;
  for (const v of equity) {
    if (v > peak) peak = v;
    const dd = v / peak - 1;
    if (dd < mdd) mdd = dd;
  }
  return mdd;
}

/* ---- formatting ---- */

function fmtValue(v, type) {
  if (v == null || !isFinite(v)) return "–";
  switch (type) {
    case "pct": return (v * 100).toFixed(1) + "%";
    case "usd": return "$" + v.toFixed(2);
    case "usdB": return "$" + (v / 1e9).toFixed(1) + "B";
    case "x": return v.toFixed(1);
    default: return v.toFixed(2);
  }
}

// Signed percentage with a class hook for colouring gains/losses.
function fmtSignedPct(v) {
  if (v == null || !isFinite(v)) return "–";
  const s = (v * 100).toFixed(1) + "%";
  return v >= 0 ? "+" + s : s;
}

function fmtMetric(row, key) {
  const m = METRIC_BY_KEY[key];
  return fmtValue(row[key], m ? m.fmt : "num");
}
