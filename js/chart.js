/*
 * Minimal dependency-free line chart for equity curves, drawn on a <canvas>.
 * Supports linear/log y-axis, multiple series, and a hover crosshair tooltip.
 *
 *   const c = new LineChart(canvasEl);
 *   c.setData({ dates: [...], series: [{ name, color, values: [...] }], log });
 */
class LineChart {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.data = null;
    this.hover = null;
    this.pad = { l: 56, r: 16, t: 16, b: 28 };
    canvas.addEventListener("mousemove", (e) => this._onMove(e));
    canvas.addEventListener("mouseleave", () => { this.hover = null; this.render(); });
    window.addEventListener("resize", () => this.render());
  }

  setData(data) {
    this.data = data;
    this.hover = null;
    this.render();
  }

  _plotArea() {
    const r = this.canvas.getBoundingClientRect();
    return {
      w: r.width, h: r.height,
      x0: this.pad.l, x1: r.width - this.pad.r,
      y0: this.pad.t, y1: r.height - this.pad.b,
    };
  }

  _yScale(a) {
    const { log } = this.data;
    let lo = Infinity, hi = -Infinity;
    for (const s of this.data.series) {
      for (const v of s.values) {
        if (v == null || !isFinite(v)) continue;
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
    }
    if (!isFinite(lo)) { lo = 0; hi = 1; }
    if (lo === hi) { hi = lo + 1; }
    if (log) {
      const llo = Math.log(Math.max(lo, 1e-6));
      const lhi = Math.log(hi);
      return (v) => a.y1 - ((Math.log(Math.max(v, 1e-6)) - llo) / (lhi - llo)) * (a.y1 - a.y0);
    }
    const pad = (hi - lo) * 0.05;
    lo -= pad; hi += pad;
    return (v) => a.y1 - ((v - lo) / (hi - lo)) * (a.y1 - a.y0);
  }

  _xScale(a) {
    const n = this.data.dates.length;
    return (i) => a.x0 + (n <= 1 ? 0 : (i / (n - 1)) * (a.x1 - a.x0));
  }

  _ticks() {
    // y-axis reference values (equity multiples)
    let lo = Infinity, hi = -Infinity;
    for (const s of this.data.series)
      for (const v of s.values)
        if (v != null && isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
    if (!isFinite(lo)) return [0, 1];
    const ticks = [];
    const steps = 5;
    for (let k = 0; k <= steps; k++) ticks.push(lo + ((hi - lo) * k) / steps);
    return ticks;
  }

  render() {
    if (!this.data) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    const ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const a = this._plotArea();
    const xs = this._xScale(a);
    const ys = this._yScale(a);
    const css = getComputedStyle(document.documentElement);
    const grid = css.getPropertyValue("--grid").trim() || "#26304a";
    const fg = css.getPropertyValue("--muted").trim() || "#8a94ad";

    // grid + y labels
    ctx.strokeStyle = grid;
    ctx.fillStyle = fg;
    ctx.lineWidth = 1;
    ctx.font = "11px ui-monospace, Menlo, Consolas, monospace";
    ctx.textBaseline = "middle";
    for (const t of this._ticks()) {
      const y = ys(t);
      ctx.globalAlpha = 0.5;
      ctx.beginPath(); ctx.moveTo(a.x0, y); ctx.lineTo(a.x1, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.textAlign = "right";
      ctx.fillText(t.toFixed(2) + "x", a.x0 - 8, y);
    }

    // x labels (a handful of evenly spaced dates)
    const n = this.data.dates.length;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const labels = 6;
    for (let k = 0; k <= labels; k++) {
      const i = Math.round((k / labels) * (n - 1));
      const d = this.data.dates[i];
      if (d) ctx.fillText(d.slice(0, 7), xs(i), a.y1 + 6);
    }

    // series lines
    for (const s of this.data.series) {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < s.values.length; i++) {
        const v = s.values[i];
        if (v == null || !isFinite(v)) continue;
        const x = xs(i), y = ys(v);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // legend
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    let lx = a.x0 + 6;
    for (const s of this.data.series) {
      ctx.fillStyle = s.color;
      ctx.fillRect(lx, a.y0 + 6, 12, 3);
      ctx.fillStyle = fg;
      ctx.fillText(s.name, lx + 16, a.y0 + 7);
      lx += 22 + ctx.measureText(s.name).width + 18;
    }

    if (this.hover != null) this._drawHover(a, xs, ys);
  }

  _drawHover(a, xs, ys) {
    const ctx = this.ctx;
    const i = this.hover;
    const x = xs(i);
    ctx.strokeStyle = "rgba(160,165,170,0.5)"; // subtle vertical crosshair
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, a.y0); ctx.lineTo(x, a.y1); ctx.stroke();

    const lines = [this.data.dates[i]];
    for (const s of this.data.series) {
      const v = s.values[i];
      if (v == null || !isFinite(v)) continue;
      const y = ys(v);
      ctx.fillStyle = s.color;
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
      lines.push(`${s.name}: ${v.toFixed(2)}x`);
    }

    // tooltip box
    ctx.font = "11px ui-monospace, Menlo, Consolas, monospace";
    const w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 16;
    const h = lines.length * 15 + 8;
    let bx = x + 10;
    if (bx + w > a.x1) bx = x - w - 10;
    const by = a.y0 + 8;
    ctx.fillStyle = "rgba(15,17,20,0.95)";
    ctx.strokeStyle = "rgba(160,165,170,0.4)";
    ctx.beginPath();
    ctx.rect(bx, by, w, h);
    ctx.fill(); ctx.stroke();
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillStyle = "#d4d6d9";
    lines.forEach((l, k) => ctx.fillText(l, bx + 8, by + 6 + k * 15));
  }

  _onMove(e) {
    if (!this.data) return;
    const rect = this.canvas.getBoundingClientRect();
    const a = this._plotArea();
    const n = this.data.dates.length;
    const px = e.clientX - rect.left;
    const frac = clamp((px - a.x0) / (a.x1 - a.x0), 0, 1);
    this.hover = Math.round(frac * (n - 1));
    this.render();
  }
}
