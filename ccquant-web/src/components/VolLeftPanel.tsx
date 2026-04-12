import { useEffect, useRef, useCallback } from 'react';
import * as echarts from 'echarts';

/* ───── Shared types ───── */
export interface PanelRow {
  expiry: string;
  days: number;
  prev: number | null;
  cur: number;
  diff: number | null;
}

/* ───── Panel chart builder ───── */
export function buildPanelChart(
  el: HTMLDivElement,
  rows: { expiry: string; cur: number; prev: number | null }[],
  fmt: (v: number) => string,
) {
  const chart = echarts.init(el);
  const labels = rows.map(r => r.expiry.slice(5));
  const curData = rows.map(r => r.cur);
  const prevData = rows.map(r => r.prev);
  const allVals = [...curData, ...prevData].filter((v): v is number => v != null && !isNaN(v));
  const yMin = allVals.length ? Math.min(...allVals) : 0;
  const yMax = allVals.length ? Math.max(...allVals) : 1;
  const pad = (yMax - yMin) * 0.12 || 0.01;
  chart.setOption({
    grid: { left: 6, right: 6, top: 8, bottom: 18, containLabel: true },
    xAxis: {
      type: 'category', data: labels, boundaryGap: false,
      axisLabel: { fontSize: 9, color: '#aaa', interval: Math.max(0, Math.floor(labels.length / 4) - 1) },
      axisLine: { show: false }, axisTick: { show: false },
    },
    yAxis: {
      type: 'value', min: yMin - pad, max: yMax + pad,
      splitNumber: 3, splitLine: { lineStyle: { color: '#f0f0f0' } },
      axisLabel: { fontSize: 9, color: '#aaa', formatter: (v: number) => fmt(v) },
    },
    tooltip: {
      trigger: 'axis', backgroundColor: 'rgba(0,0,0,0.78)', borderWidth: 0,
      textStyle: { color: '#fff', fontSize: 11 },
      formatter: (params: any) => {
        const items = Array.isArray(params) ? params : [params];
        let html = `<div style="color:#aaa;margin-bottom:2px">${items[0]?.axisValue || ''}</div>`;
        for (const it of items) {
          if (it.value == null) continue;
          const c = it.seriesName === '昨收' ? '#999' : '#7c3aed';
          html += `<div><span style="color:${c}">${it.seriesName}: ${fmt(it.value)}</span></div>`;
        }
        return html;
      },
    },
    series: [
      { name: '昨收', type: 'line', data: prevData, symbol: 'circle', symbolSize: 4, smooth: false, lineStyle: { color: '#bbb', width: 1.5, type: 'dashed' }, itemStyle: { color: '#bbb' }, z: 1 },
      { name: '现值', type: 'line', data: curData, symbol: 'circle', symbolSize: 5, smooth: false, lineStyle: { color: '#7c3aed', width: 2 }, itemStyle: { color: '#7c3aed' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(124,58,237,0.15)' }, { offset: 1, color: 'rgba(124,58,237,0.01)' },
        ]) }, z: 2 },
    ],
  });
  return chart;
}

/* ───── LeftPanel: table + line chart ───── */
export function LeftPanel({ title, rows, fmt, chartRef }: {
  title: string;
  rows: PanelRow[];
  fmt: (v: number) => string;
  chartRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', borderRadius: 8, border: '1px solid #e8e8e8', background: '#fafafa', overflow: 'hidden' }}>
      <div style={{ padding: '6px 10px', fontWeight: 700, fontSize: 13, color: '#333', borderBottom: '1px solid #eee', background: '#f5f5f5' }}>{title}</div>
      <div style={{ overflowY: 'auto', maxHeight: 140, fontSize: 11 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f0f0f0', position: 'sticky', top: 0, zIndex: 1 }}>
              {['到期日', '天数', '昨收', '现值', '日差'].map(h => (
                <th key={h} style={{ padding: '3px 4px', fontWeight: 600, color: '#555', fontSize: 10, textAlign: 'center', borderBottom: '1px solid #e0e0e0' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const dc = r.diff != null ? (r.diff > 0 ? '#e74c3c' : r.diff < 0 ? '#27ae60' : '#999') : '#999';
              const ds = r.diff != null ? `${r.diff > 0 ? '+' : ''}${fmt(r.diff)}` : '-';
              return (
                <tr key={r.expiry} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '2px 4px', fontWeight: 700, textAlign: 'center', fontSize: 10 }}>{r.expiry.slice(5)}</td>
                  <td style={{ padding: '2px 4px', textAlign: 'center', color: '#666', fontSize: 10 }}>{Math.round(r.days)}</td>
                  <td style={{ padding: '2px 4px', textAlign: 'center', color: '#999', fontSize: 10 }}>{r.prev != null ? fmt(r.prev) : '-'}</td>
                  <td style={{ padding: '2px 4px', textAlign: 'center', color: '#7c3aed', fontWeight: 600, fontSize: 10 }}>{fmt(r.cur)}</td>
                  <td style={{ padding: '2px 4px', textAlign: 'center', color: dc, fontWeight: 600, fontSize: 10 }}>{ds}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div ref={chartRef} style={{ flex: 1, minHeight: 100 }} />
    </div>
  );
}

/* ───── Container: ATM IV + Skew panels with chart lifecycle ───── */
export default function VolLeftPanels({ atmRows, skewRows }: {
  atmRows: PanelRow[];
  skewRows: PanelRow[];
}) {
  const atmChartRef = useRef<HTMLDivElement>(null);
  const skewChartRef = useRef<HTMLDivElement>(null);
  const miniChartsRef = useRef<echarts.ECharts[]>([]);

  const disposeMinis = useCallback(() => {
    miniChartsRef.current.forEach(c => { try { c.dispose(); } catch {} });
    miniChartsRef.current = [];
  }, []);

  useEffect(() => () => { disposeMinis(); }, [disposeMinis]);

  useEffect(() => {
    disposeMinis();
    if (atmChartRef.current && atmRows.length > 0) {
      miniChartsRef.current.push(buildPanelChart(
        atmChartRef.current,
        atmRows.map(r => ({ expiry: r.expiry, cur: r.cur, prev: r.prev })),
        (v) => `${(v * 100).toFixed(1)}%`,
      ));
    }
    if (skewChartRef.current && skewRows.length > 0) {
      miniChartsRef.current.push(buildPanelChart(
        skewChartRef.current,
        skewRows.map(r => ({ expiry: r.expiry, cur: r.cur, prev: r.prev })),
        (v) => v.toFixed(3),
      ));
    }
    return () => { disposeMinis(); };
  }, [atmRows, skewRows, disposeMinis]);

  const showLeft = atmRows.length > 0 || skewRows.length > 0;
  if (!showLeft) return null;

  return (
    <div style={{ width: 280, minWidth: 280, display: 'flex', flexDirection: 'column', gap: 6, padding: '8px 4px 8px 8px' }}>
      {atmRows.length > 0 && <LeftPanel title="平值隐波" rows={atmRows} fmt={(v) => `${(v * 100).toFixed(1)}%`} chartRef={atmChartRef} />}
      {skewRows.length > 0 && <LeftPanel title="25Δ 偏度" rows={skewRows} fmt={(v) => v.toFixed(3)} chartRef={skewChartRef} />}
    </div>
  );
}
