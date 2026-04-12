import { useEffect, useRef, useCallback, useState } from 'react';
import * as echarts from 'echarts';
import 'echarts-gl';
import type { VolSurfaceV2Response, Vol3DPoint, AtmIvPoint, SkewPoint } from '../types';
import VolLeftPanels from './VolLeftPanel';

interface Vol3DSurfaceProps {
  data: VolSurfaceV2Response;
  mode: 'raw' | 'synthetic';
  useSvi: boolean;
  xAxisMode: 'strike' | 'moneyness';
}

interface SurfResult {
  surfData: number[][];
  sRange: [number, number];
  dRange: [number, number];
  zRange: [number, number];
  N: number;
  fineS: number[];
  fineD: number[];
  grid: number[][];
}

/* ───── Cubic spline interpolation ───── */
function buildCubicSplineCoeffs(xs: number[], ys: number[]): { a: number[]; b: number[]; c: number[]; d: number[] } {
  const n = xs.length - 1;
  const h: number[] = [];
  for (let i = 0; i < n; i++) h.push(xs[i + 1] - xs[i]);

  const alpha: number[] = new Array(n + 1).fill(0);
  for (let i = 1; i < n; i++) {
    alpha[i] = (3 / h[i]) * (ys[i + 1] - ys[i]) - (3 / h[i - 1]) * (ys[i] - ys[i - 1]);
  }

  const l = new Array(n + 1).fill(1);
  const mu = new Array(n + 1).fill(0);
  const z = new Array(n + 1).fill(0);

  for (let i = 1; i < n; i++) {
    l[i] = 2 * (xs[i + 1] - xs[i - 1]) - h[i - 1] * mu[i - 1];
    mu[i] = h[i] / l[i];
    z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i];
  }

  const c = new Array(n + 1).fill(0);
  const b = new Array(n).fill(0);
  const d = new Array(n).fill(0);

  for (let j = n - 1; j >= 0; j--) {
    c[j] = z[j] - mu[j] * c[j + 1];
    b[j] = (ys[j + 1] - ys[j]) / h[j] - h[j] * (c[j + 1] + 2 * c[j]) / 3;
    d[j] = (c[j + 1] - c[j]) / (3 * h[j]);
  }

  return { a: [...ys], b, c: c.slice(0, n), d };
}

function evalCubicSpline(xs: number[], coeffs: { a: number[]; b: number[]; c: number[]; d: number[] }, x: number): number {
  const n = xs.length - 1;
  let i = 0;
  if (x <= xs[0]) i = 0;
  else if (x >= xs[n]) i = n - 1;
  else {
    let lo = 0, hi = n;
    while (lo < hi - 1) {
      const mid = (lo + hi) >> 1;
      if (xs[mid] <= x) lo = mid; else hi = mid;
    }
    i = lo;
  }
  const dx = x - xs[i];
  return coeffs.a[i] + coeffs.b[i] * dx + coeffs.c[i] * dx * dx + coeffs.d[i] * dx * dx * dx;
}
/* ───── Build smooth surface with cubic spline ───── */
function buildSmoothSurface(src: Vol3DPoint[], xMode: 'strike' | 'moneyness', gridSize = 50): SurfResult | null {
  const dedup = new Map<string, { s: number; n: number; pt: Vol3DPoint }>();
  src.forEach(p => {
    const xVal = xMode === 'moneyness' ? p.moneyness : p.strike;
    const k = `${xVal}_${p.remainingDays}`;
    const e = dedup.get(k);
    if (e) { e.s += p.iv; e.n++; } else dedup.set(k, { s: p.iv, n: 1, pt: p });
  });
  const pts = [...dedup.values()].map(({ s, n, pt }) => ({
    ...pt,
    iv: s / n,
    xVal: xMode === 'moneyness' ? pt.moneyness : pt.strike,
  }));
  if (pts.length < 3) return null;
  const sArr = [...new Set(pts.map(p => p.xVal))].sort((a, b) => a - b);
  const dArr = [...new Set(pts.map(p => p.remainingDays))].sort((a, b) => a - b);
  if (sArr.length < 2 || dArr.length < 2) return null;

  // Build coarse grid
  const lk = new Map<string, number>();
  pts.forEach(p => lk.set(`${p.xVal}_${p.remainingDays}`, p.iv));
  const G: number[][] = Array.from({ length: dArr.length }, (_, di) =>
    Array.from({ length: sArr.length }, (_, si) => lk.get(`${sArr[si]}_${dArr[di]}`) ?? NaN));

  // Cubic spline interpolation along each row (strike direction)
  for (let di = 0; di < dArr.length; di++) {
    const row = G[di];
    const known: [number, number][] = [];
    row.forEach((v, si) => { if (!isNaN(v)) known.push([sArr[si], v]); });
    if (known.length >= 2) {
      const kx = known.map(k => k[0]), ky = known.map(k => k[1]);
      const coeffs = buildCubicSplineCoeffs(kx, ky);
      for (let si = 0; si < sArr.length; si++) {
        if (isNaN(row[si])) row[si] = evalCubicSpline(kx, coeffs, sArr[si]);
      }
    } else if (known.length === 1) {
      row.fill(known[0][1]);
    }
  }
  // Cubic spline along each column (time direction)
  for (let si = 0; si < sArr.length; si++) {
    const known: [number, number][] = [];
    G.forEach((row, di) => { if (!isNaN(row[si])) known.push([dArr[di], row[si]]); });
    if (known.length >= 2) {
      const kx = known.map(k => k[0]), ky = known.map(k => k[1]);
      const coeffs = buildCubicSplineCoeffs(kx, ky);
      G.forEach((row, di) => { if (isNaN(row[si])) row[si] = evalCubicSpline(kx, coeffs, dArr[di]); });
    } else if (known.length === 1) {
      G.forEach(row => { if (isNaN(row[si])) row[si] = known[0][1]; });
    }
  }

  // Fine grid via bicubic interpolation
  const N = gridSize;
  const sMin = sArr[0], sMax = sArr[sArr.length - 1];
  const dMin = dArr[0], dMax = dArr[dArr.length - 1];
  const fineS = Array.from({ length: N }, (_, i) => sMin + i / (N - 1) * (sMax - sMin));
  const fineD = Array.from({ length: N }, (_, i) => dMin + i / (N - 1) * (dMax - dMin));

  // Build spline coefficients for each row of the coarse grid
  const rowSplines = G.map(row => buildCubicSplineCoeffs(sArr, row));

  const surfData: number[][] = [];
  const grid: number[][] = Array.from({ length: N }, () => new Array(N));
  let zMin = Infinity, zMax = -Infinity;
  for (let di = 0; di < N; di++) {
    // Interpolate in time direction for each coarse strike, then in strike direction
    const d = fineD[di];
    // Get IV at each coarse strike for this fine day
    const colVals: number[] = new Array(sArr.length);
    for (let si = 0; si < sArr.length; si++) {
      const colKnown: [number, number][] = [];
      G.forEach((row, ri) => colKnown.push([dArr[ri], row[si]]));
      const colCoeffs = buildCubicSplineCoeffs(colKnown.map(k => k[0]), colKnown.map(k => k[1]));
      colVals[si] = evalCubicSpline(dArr, colCoeffs, d);
    }
    // Now spline across strikes for this day
    const dayCoeffs = buildCubicSplineCoeffs(sArr, colVals);
    for (let si = 0; si < N; si++) {
      const s = fineS[si];
      const iv = evalCubicSpline(sArr, dayCoeffs, s);
      surfData.push([s, d, iv]);
      grid[di][si] = iv;
      if (iv < zMin) zMin = iv;
      if (iv > zMax) zMax = iv;
    }
  }
  return { surfData, sRange: [sMin, sMax], dRange: [dMin, dMax], zRange: [zMin, zMax], N, fineS, fineD, grid };
}

function extractSmile(surf: SurfResult, targetDays: number) {
  const { fineS, fineD, grid, N } = surf;
  let di = 0;
  for (let i = 1; i < N; i++) { if (Math.abs(fineD[i] - targetDays) < Math.abs(fineD[di] - targetDays)) di = i; }
  return { strikes: [...fineS], ivs: grid[di].map(v => v) };
}
function extractTerm(surf: SurfResult, targetStrike: number) {
  const { fineS, fineD, grid, N } = surf;
  let si = 0;
  for (let i = 1; i < N; i++) { if (Math.abs(fineS[i] - targetStrike) < Math.abs(fineS[si] - targetStrike)) si = i; }
  return { days: [...fineD], ivs: grid.map(row => row[si]) };
}
/* ───── Patch OrbitControl ───── */
function patchOrbitControl(chart: echarts.ECharts) {
  try {
    const ecModel = (chart as any).getModel();
    const grid3DModel = ecModel.getComponent('grid3D');
    const coordSys = grid3DModel.coordinateSystem;
    const orbit = coordSys.viewGL._control;
    if (!orbit) return;
    const zr = chart.getZr();
    if (orbit._mouseDownHandler) {
      zr.off('mousedown', orbit._mouseDownHandler);
      orbit._mouseDownHandler = function (e: any) {
        if (this._isAnimating()) return;
        const x = e.offsetX, y = e.offsetY;
        if (this.viewGL && !this.viewGL.containPoint(x, y)) return;
        this.zr.on('mousemove', this._mouseMoveHandler);
        this.zr.on('mouseup', this._mouseUpHandler);
        if (e.event.targetTouches) { if (e.event.targetTouches.length === 1) this._mode = 'rotate'; }
        else {
          const MAP: Record<string, number> = { left: 0, middle: 1, right: 2 };
          if (e.event.button === MAP[this.rotateMouseButton]) this._mode = 'rotate';
          else if (e.event.button === MAP[this.panMouseButton]) this._mode = 'pan';
          else { this._mode = ''; return; }
        }
        this._rotateVelocity.set(0, 0); this._rotating = false;
        if (this.autoRotate) this._startCountingStill();
        this._mouseX = x; this._mouseY = y;
      }.bind(orbit);
      zr.on('mousedown', orbit._mouseDownHandler);
    }
    if (orbit._mouseMoveHandler) {
      const origMove = orbit._mouseMoveHandler;
      orbit._patchedMoveHandler = function (e: any) {
        if (this._isAnimating()) return;
        const rs = Array.isArray(this.rotateSensitivity) ? this.rotateSensitivity : [this.rotateSensitivity, this.rotateSensitivity];
        const ps = Array.isArray(this.panSensitivity) ? this.panSensitivity : [this.panSensitivity, this.panSensitivity];
        if (this._mode === 'rotate') {
          this._rotateVelocity.y = (e.offsetX - this._mouseX) / this.zr.getHeight() * 2 * rs[0];
          this._rotateVelocity.x = (e.offsetY - this._mouseY) / this.zr.getWidth() * 2 * rs[1];
        } else if (this._mode === 'pan') {
          this._panVelocity.x = (e.offsetX - this._mouseX) / this.zr.getWidth() * ps[0] * 400;
          this._panVelocity.y = -(e.offsetY - this._mouseY) / this.zr.getHeight() * ps[1] * 400;
        }
        this._mouseX = e.offsetX; this._mouseY = e.offsetY;
      }.bind(orbit);
      orbit._mouseMoveHandler = orbit._patchedMoveHandler;
      try { zr.off('mousemove', origMove); } catch {}
    }
  } catch { /* patching failed */ }
}

/* ───── cross-section mini chart ───── */
function updateCrossSection(
  chart: echarts.ECharts, title: string,
  xData: number[], yData: number[], xFmt: (v: number) => string,
  highlightX: number,
) {
  const yMin = Math.min(...yData), yMax = Math.max(...yData);
  const yPad = (yMax - yMin) * 0.1 || 0.01;
  chart.setOption({
    title: { text: title, left: 6, top: 2, textStyle: { fontSize: 11, fontWeight: 'bold', color: '#333' } },
    grid: { left: 6, right: 6, top: 26, bottom: 4, containLabel: true },
    xAxis: {
      type: 'value', min: xData[0], max: xData[xData.length - 1],
      axisLabel: { fontSize: 8, color: '#999', formatter: xFmt },
      splitLine: { show: false }, axisLine: { show: true, lineStyle: { color: '#ddd' } },
    },
    yAxis: {
      type: 'value', min: yMin - yPad, max: yMax + yPad,
      axisLabel: { fontSize: 8, color: '#999', formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      splitLine: { lineStyle: { color: '#f5f5f5' } },
    },
    tooltip: { show: false },
    series: [
      {
        type: 'line', data: xData.map((x, i) => [x, yData[i]]),
        symbol: 'none', smooth: true,
        lineStyle: { color: '#7c3aed', width: 1.5 },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(124,58,237,0.15)' }, { offset: 1, color: 'rgba(124,58,237,0.01)' },
        ]) },
      },
      {
        type: 'line', data: [[highlightX, yMin - yPad], [highlightX, yMax + yPad]],
        symbol: 'none', lineStyle: { color: 'rgba(220,80,20,0.6)', width: 1.5, type: 'dashed' },
      },
    ],
  }, true);
}
/* ───── Left panel: now uses shared VolLeftPanels component ───── */
/* ═══════════════════════════════════════════════════════════════
 *  COMPONENT
 * ═══════════════════════════════════════════════════════════════ */
export default function Vol3DSurface({ data, mode: _mode, useSvi, xAxisMode }: Vol3DSurfaceProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const smileRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<HTMLDivElement>(null);
  const surfRef = useRef<SurfResult | null>(null);
  const smileEcRef = useRef<echarts.ECharts | null>(null);
  const termEcRef = useRef<echarts.ECharts | null>(null);
  const [showCross, setShowCross] = useState(false);

  const disposeOne = useCallback((ref: React.MutableRefObject<echarts.ECharts | null>) => {
    if (ref.current) { try { ref.current.dispose(); } catch {} ref.current = null; }
  }, []);

  useEffect(() => () => { disposeOne(chartInstanceRef); }, [disposeOne]);

  /* ── Build left panel data ── */
  const atm = data.atmIvData || [];
  const skew = data.skewData || [];
  const atmRows = atm.map((p: AtmIvPoint) => ({
    expiry: p.expiry, days: p.remainingDays, prev: p.prevAtmIv, cur: p.atmIv,
    diff: p.prevAtmIv != null ? p.atmIv - p.prevAtmIv : null,
  }));
  const skewRows = skew.map((p: SkewPoint) => ({
    expiry: p.expiry, days: p.remainingDays, prev: p.prevSkew, cur: p.skew,
    diff: p.prevSkew != null ? p.skew - p.prevSkew : null,
  }));

  /* ── Left panel charts now handled by shared VolLeftPanels ── */

  /* ── Init cross-section charts ── */
  useEffect(() => {
    if (smileRef.current && !smileEcRef.current) smileEcRef.current = echarts.init(smileRef.current);
    if (termRef.current && !termEcRef.current) termEcRef.current = echarts.init(termRef.current);
    return () => {
      if (smileEcRef.current) { try { smileEcRef.current.dispose(); } catch {} smileEcRef.current = null; }
      if (termEcRef.current) { try { termEcRef.current.dispose(); } catch {} termEcRef.current = null; }
    };
  }, []);
  /* ── Main 3D Surface ── */
  useEffect(() => {
    if (!chartRef.current || !data.points || data.points.length < 3) return;
    disposeOne(chartInstanceRef);
    const chart = echarts.init(chartRef.current);
    chartInstanceRef.current = chart;
    const src = useSvi && data.sviPoints?.length ? data.sviPoints : data.points;
    const surf = buildSmoothSurface(src, xAxisMode, 50);
    if (!surf) return;
    surfRef.current = surf;
    const { surfData, sRange, dRange, zRange, N } = surf;
    const sSpan = sRange[1] - sRange[0] || 0.01;
    const dSpan = dRange[1] - dRange[0] || 1;
    const ivSpan = zRange[1] - zRange[0] || 0.01;

    const isMoneyness = xAxisMode === 'moneyness';
    const xAxisName = isMoneyness ? 'Moneyness' : '行权价';
    const xFmt = isMoneyness
      ? (v: number) => v.toFixed(2)
      : (v: number) => v.toFixed(2);

    const vb = data.volumeBars || [];
    const callBarData: number[][] = [], putBarData: number[][] = [];
    let barReserve = 0;
    if (vb.length > 0) {
      let maxOi = 0;
      for (const b of vb) maxOi = Math.max(maxOi, b.callOi, b.putOi);
      if (maxOi === 0) maxOi = 1;
      barReserve = ivSpan * 0.18;
      const zFloor = zRange[0] - barReserve, off = sSpan * 0.008;
      for (const b of vb) {
        const days = b.T * 365;
        const bx = isMoneyness ? b.moneyness : b.strike;
        if (bx < sRange[0] || bx > sRange[1]) continue;
        if (days < dRange[0] - dSpan * 0.05 || days > dRange[1] + dSpan * 0.05) continue;
        if (b.callOi > 0) callBarData.push([bx + off, days, zFloor + (b.callOi / maxOi) * barReserve * 0.85]);
        if (b.putOi > 0) putBarData.push([bx - off, days, zFloor + (b.putOi / maxOi) * barReserve * 0.85]);
      }
    }
    const ivPad = ivSpan * 0.05;
    const zAxisMin = zRange[0] - barReserve - ivPad, zAxisMax = zRange[1] + ivPad;

    const series: any[] = [{
      type: 'surface',
      wireframe: { show: false },
      shading: 'realistic',
      realisticMaterial: { roughness: 0.45, metalness: 0.0 },
      data: surfData, dataShape: [N, N],
      itemStyle: { opacity: 0.95 }, silent: false,
    }];
    if (callBarData.length > 0) series.push({
      type: 'bar3D', data: callBarData, barSize: 1.5, shading: 'realistic',
      realisticMaterial: { roughness: 0.3, metalness: 0.1 }, name: 'Call OI',
      itemStyle: { color: '#ff7b6b' },
      emphasis: { itemStyle: { color: '#ff9080' }, label: { show: false } },
      label: { show: false }, silent: false,
    });
    if (putBarData.length > 0) series.push({
      type: 'bar3D', data: putBarData, barSize: 1.5, shading: 'realistic',
      realisticMaterial: { roughness: 0.3, metalness: 0.1 }, name: 'Put OI',
      itemStyle: { color: '#5cc87c' },
      emphasis: { itemStyle: { color: '#78d898' }, label: { show: false } },
      label: { show: false }, silent: false,
    });
    chart.setOption({
      tooltip: { show: false },
      visualMap: {
        show: true, min: zRange[0], max: zRange[1], dimension: 2, seriesIndex: 0,
        orient: 'vertical', right: 10, top: 'center', itemHeight: 200, itemWidth: 14,
        text: [`${(zRange[1] * 100).toFixed(0)}%`, `${(zRange[0] * 100).toFixed(0)}%`],
        textStyle: { color: '#444', fontSize: 11 },
        inRange: {
          color: ['#0a0e3d', '#0c1a6e', '#0e3a9e', '#0c4890', '#106088',
                  '#1a6858', '#2a6838', '#6a7820', '#a08018', '#b85828', '#a03030', '#701020'],
        },
      },
      legend: (callBarData.length > 0 || putBarData.length > 0) ? {
        data: [
          ...(callBarData.length > 0 ? [{ name: 'Call OI', icon: 'roundRect' }] : []),
          ...(putBarData.length > 0 ? [{ name: 'Put OI', icon: 'roundRect' }] : []),
        ],
        bottom: 8, left: 'center',
        textStyle: { fontSize: 11, color: '#444' },
        itemWidth: 12, itemHeight: 10, itemGap: 20,
      } : undefined,
      grid3D: {
        viewControl: {
          projection: 'perspective', autoRotate: false,
          distance: 200, alpha: 30, beta: 45,
          rotateSensitivity: 5, zoomSensitivity: 3, panSensitivity: 2, damping: 0.85,
        },
        boxWidth: 160, boxDepth: 120, boxHeight: 80,
        environment: '#fafafa',
        light: {
          main: { intensity: 0.8, shadow: true, shadowQuality: 'medium', alpha: 40, beta: 50 },
          ambient: { intensity: 0.4 },
          ambientCubemap: { exposure: 1, diffuseIntensity: 0.5 },
        },
        postEffect: { enable: true, SSAO: { enable: true, radius: 4, intensity: 1.2, quality: 'medium' } },
        temporalSuperSampling: { enable: true },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: '#333', width: 2.5 } },
        axisTick: { show: true, lineStyle: { color: '#666', width: 1.5 } },
        axisLabel: { color: '#333', fontSize: 13 },
        splitLine: { show: false },
        axisPointer: { show: true, lineStyle: { color: 'rgba(220,80,20,0.85)', width: 2.5 } },
      },
      xAxis3D: {
        type: 'value', name: xAxisName,
        min: sRange[0] - sSpan * 0.02, max: sRange[1] + sSpan * 0.02,
        nameTextStyle: { fontSize: 14, color: '#222', fontWeight: 'bold' },
        axisLabel: { fontSize: 12, color: '#333', formatter: (v: number) => xFmt(v) },
        splitLine: { show: true, lineStyle: { color: 'rgba(0,0,0,0.06)', width: 1 } },
        axisPointer: { show: true, lineStyle: { color: 'rgba(220,80,20,0.8)', width: 2 },
          label: { show: true, formatter: (p: any) => { const v = p?.value; return typeof v === 'number' ? xFmt(v) : String(v ?? ''); }, textStyle: { color: '#FF8C00', fontSize: 12 }, backgroundColor: 'rgba(30,30,30,0.88)', padding: [4, 8], borderWidth: 0 } },
      },
      yAxis3D: {
        type: 'value', name: '到期天数',
        min: dRange[0] - dSpan * 0.03, max: dRange[1] + dSpan * 0.03,
        nameTextStyle: { fontSize: 14, color: '#222', fontWeight: 'bold' },
        axisLabel: { fontSize: 12, color: '#333', formatter: (v: number) => `${Math.round(v)}d` },
        splitLine: { show: true, lineStyle: { color: 'rgba(0,0,0,0.06)', width: 1 } },
        axisPointer: { show: true, lineStyle: { color: 'rgba(220,80,20,0.8)', width: 2 },
          label: { show: true, formatter: (p: any) => { const v = p?.value; return typeof v === 'number' ? `${Math.round(v)}d` : String(v ?? ''); }, textStyle: { color: '#a78bfa', fontSize: 12 }, backgroundColor: 'rgba(30,30,30,0.88)', padding: [4, 8], borderWidth: 0 } },
      },
      zAxis3D: {
        type: 'value', name: 'IV', min: zAxisMin, max: zAxisMax,
        nameTextStyle: { fontSize: 14, color: '#222', fontWeight: 'bold' },
        axisLabel: { fontSize: 12, color: '#333', formatter: (v: number) => v >= zRange[0] - ivPad * 0.5 ? `${(v * 100).toFixed(0)}%` : '' },
        splitNumber: 5, splitLine: { show: false },
        axisPointer: { show: true, lineStyle: { color: 'rgba(220,80,20,0.8)', width: 2 },
          label: { show: true, formatter: (p: any) => { const v = p?.value; return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : String(v ?? ''); }, textStyle: { color: '#87CEEB', fontSize: 12 }, backgroundColor: 'rgba(30,30,30,0.88)', padding: [4, 8], borderWidth: 0 } },
      },
      series,
    });
    patchOrbitControl(chart);
    /* ── Events ── */
    const el = chartRef.current!;
    let tipTimer: ReturnType<typeof setTimeout> | null = null;
    const hideTip = () => { if (tooltipRef.current) tooltipRef.current.style.opacity = '0'; };
    const hideAll = () => { hideTip(); setShowCross(false); };
    const scheduleHide = () => { if (tipTimer) clearTimeout(tipTimer); tipTimer = setTimeout(hideAll, 200); };
    const cancelHide = () => { if (tipTimer) { clearTimeout(tipTimer); tipTimer = null; } };
    const showTip = (t: HTMLDivElement, px: number, py: number, html: string) => {
      cancelHide(); t.style.opacity = '1';
      t.style.left = `${Math.min(px + 16, (el.clientWidth || 800) - 240)}px`;
      t.style.top = `${Math.max(py - 80, 10)}px`;
      t.innerHTML = html;
    };
    const updateCross = (xVal: number, days: number) => {
      const s = surfRef.current; if (!s) return;
      setShowCross(true);
      const xLabel = isMoneyness ? `Moneyness` : `K`;
      const xDisplay = isMoneyness ? xVal.toFixed(3) : xVal.toFixed(2);
      if (smileEcRef.current) { const sm = extractSmile(s, days); updateCrossSection(smileEcRef.current, `波动率微笑 (${Math.round(days)}d)`, sm.strikes, sm.ivs, (v) => xFmt(v), xVal); }
      if (termEcRef.current) { const tm = extractTerm(s, xVal); updateCrossSection(termEcRef.current, `期限结构 (${xLabel}=${xDisplay})`, tm.days, tm.ivs, (v) => `${Math.round(v)}d`, days); }
    };
    chart.on('mouseover', { seriesIndex: 0 }, (p: any) => {
      if (!p.data || !p.event || !tooltipRef.current) return;
      const [xVal, days, iv] = p.data as [number, number, number];
      const xLabel = isMoneyness ? 'Moneyness' : '行权价';
      const xDisplay = isMoneyness ? xVal.toFixed(3) : xVal.toFixed(4);
      showTip(tooltipRef.current, p.event.offsetX, p.event.offsetY,
        `<div style="margin-bottom:3px;border-bottom:1px solid rgba(255,255,255,0.15);padding-bottom:3px">IV: <span style="color:#FF8C00;font-weight:700">${(iv * 100).toFixed(2)}%</span></div>` +
        `<div>${xLabel}: <span style="color:#87CEEB">${xDisplay}</span></div>` +
        `<div>剩余到期: <span style="color:#a78bfa">${Math.round(days)}天</span></div>`);
      updateCross(xVal, days);
    });
    for (let si = 1; si < series.length; si++) {
      chart.on('mouseover', { seriesIndex: si }, (p: any) => {
        if (!p.data || !p.event || !tooltipRef.current) return;
        const [xVal, days] = p.data as [number, number, number];
        const isCall = p.seriesName === 'Call OI';
        const color = isCall ? '#ff7b6b' : '#5cc87c';
        const matched = vb.find(b => {
          const bx = isMoneyness ? b.moneyness : b.strike;
          return Math.abs(bx - xVal) < sSpan * 0.015 && Math.abs(b.T * 365 - days) < 1;
        });
        const oi = matched ? (isCall ? matched.callOi : matched.putOi) : 0;
        showTip(tooltipRef.current!, p.event.offsetX, p.event.offsetY,
          `<div style="margin-bottom:2px"><span style="color:${color};font-weight:700">${isCall ? 'Call' : 'Put'} 持仓量</span></div>` +
          `<div>数量: <b>${oi.toLocaleString()}</b></div><div>${isMoneyness ? 'Moneyness' : '行权价'}: ${xFmt(xVal)}</div><div>剩余到期: ${Math.round(days)}天</div>`);
      });
    }
    chart.on('mouseout', () => { scheduleHide(); });
    chart.on('globalout', () => { hideAll(); });
    el.addEventListener('mouseleave', hideAll);
    el.addEventListener('pointerleave', hideAll);
    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      if (tipTimer) clearTimeout(tipTimer);
      chart.off('mouseover'); chart.off('mouseout'); chart.off('globalout');
      disposeOne(chartInstanceRef);
    };
  }, [data, useSvi, xAxisMode, disposeOne, setShowCross]);

  /* ── Render ── */
  const crossStyle: React.CSSProperties = {
    width: 260, height: 170, borderRadius: 8,
    background: 'rgba(255,255,255,0.92)', border: '1px solid #e0e0e0',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
  };
  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', background: '#fff' }}>
      <VolLeftPanels atmRows={atmRows} skewRows={skewRows} />
      <div style={{ flex: 1, position: 'relative', minWidth: 0 }}>
        <div ref={chartRef} style={{ width: '100%', height: '100%' }} />
        <div ref={tooltipRef} style={{
          position: 'absolute', left: 0, top: 0, opacity: 0,
          background: 'rgba(0,0,0,0.78)', color: '#fff', padding: '6px 12px', borderRadius: 6,
          fontSize: 12, lineHeight: 1.7, pointerEvents: 'none', zIndex: 30,
          backdropFilter: 'blur(4px)', whiteSpace: 'nowrap', transition: 'opacity 0.1s',
        }} />
        {/* Cross-section: top-left */}
        <div style={{ position: 'absolute', top: 10, left: 10, opacity: showCross ? 1 : 0, transition: 'opacity 0.15s', pointerEvents: 'none' }}>
          <div ref={smileRef} style={crossStyle} />
        </div>
        {/* Cross-section: top-right */}
        <div style={{ position: 'absolute', top: 10, right: 50, opacity: showCross ? 1 : 0, transition: 'opacity 0.15s', pointerEvents: 'none' }}>
          <div ref={termRef} style={crossStyle} />
        </div>
      </div>
    </div>
  );
}