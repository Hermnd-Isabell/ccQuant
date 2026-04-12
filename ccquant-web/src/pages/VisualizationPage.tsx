import { useState, useEffect, useRef, useCallback } from 'react';
import * as echarts from 'echarts';
import 'echarts-gl';
import {
  getUnderlyings,
  getMarketOverview,
  getVolSmile,
  getVolSurfaceV2,
  getTradeDates,
  getExpiryDates,
  getUnderlyingContracts,
  getOptionChain,
} from '../api';
import type {
  UnderlyingInfo,
  VisualizationView,
  Granularity,
  MarketOverview,
  VolSmileGroup,
  VolSmileStrike,
  VolSurfaceV2Response,
  Vol3DPoint,
  AtmIvPoint,
  SkewPoint,
  ContractInfo,
  OptionChainData,
} from '../types';
import Vol3DSurface from '../components/Vol3DSurface';
import VolLeftPanels from '../components/VolLeftPanel';

// ========== Helper: dispose all tracked chart instances ==========
function disposeCharts(chartsRef: React.MutableRefObject<echarts.ECharts[]>) {
  chartsRef.current.forEach((c) => {
    try { c.dispose(); } catch { /* ignore */ }
  });
  chartsRef.current = [];
}

// ========== Helper: snap date to nearest valid trade date ==========
function snapToTradeDate(dateStr: string, tradeDates: string[]): string {
  if (tradeDates.length === 0) return dateStr;
  if (tradeDates.includes(dateStr)) return dateStr;
  // find nearest
  let best = tradeDates[tradeDates.length - 1];
  let bestDiff = Infinity;
  const target = new Date(dateStr).getTime();
  for (const d of tradeDates) {
    const diff = Math.abs(new Date(d).getTime() - target);
    if (diff < bestDiff) { bestDiff = diff; best = d; }
  }
  return best;
}

export default function VisualizationPage() {
  const [underlyings, setUnderlyings] = useState<UnderlyingInfo[]>([]);
  const [selectedUnderlying, setSelectedUnderlying] = useState('');
  const [granularity] = useState<Granularity>('daily');
  const [view, setView] = useState<VisualizationView>('market');
  const [loading, setLoading] = useState(false);

  // Trade date picker for vol views
  const [tradeDates, setTradeDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState('');
  const tradeDateSet = useRef<Set<string>>(new Set());

  // Chart data
  const [marketData, setMarketData] = useState<MarketOverview | null>(null);
  const [volSmileData, setVolSmileData] = useState<VolSmileGroup[]>([]);
  const [vol3dData, setVol3dData] = useState<VolSurfaceV2Response | null>(null);
  const [optionChainData, setOptionChainData] = useState<OptionChainData[]>([]);

  // 3D surface mode: raw IV vs synthetic forward
  const [vol3dMode, setVol3dMode] = useState<'raw' | 'synthetic'>('raw');
  // 3D surface: use SVI fitting (default: true)
  const [vol3dUseSvi, setVol3dUseSvi] = useState(true);
  // 3D surface: X-axis mode
  const [vol3dXAxis, setVol3dXAxis] = useState<'strike' | 'moneyness'>('strike');

  // Option chain column visibility
  const [chainColumns, setChainColumns] = useState({
    bid: false,
    ask: false,
    last: true,
    volume: true,
    openInterest: true,
    iv: true,
    delta: true,
    gamma: false,
    theta: false,
    vega: false,
  });

  // Contract selector for market view — two-level: expiry → contract (lazy loaded)
  const [contracts, setContracts] = useState<ContractInfo[]>([]);
  const [selectedContract, setSelectedContract] = useState<string>('all');
  const [contractExpiry, setContractExpiry] = useState<string>('');
  const [contractExpiries, setContractExpiries] = useState<string[]>([]);
  const [contractsLoading, setContractsLoading] = useState(false);

  // Indicator selector dropdown (only for additional indicators, price/volume always shown)
  const [availableIndicators] = useState([
    { id: 'iv', name: 'ATM IV', category: '波动率' },
    { id: 'delta', name: 'Delta', category: 'Greeks' },
    { id: 'gamma', name: 'Gamma', category: 'Greeks' },
    { id: 'theta', name: 'Theta', category: 'Greeks' },
    { id: 'vega', name: 'Vega', category: 'Greeks' },
  ]);
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>(['iv']);

  // Chart DOM refs
  const marketChartRef = useRef<HTMLDivElement>(null);

  // Always-current ref to marketData — avoids stale closure in chart effects/tooltip
  const marketDataRef = useRef<MarketOverview | null>(null);
  useEffect(() => { marketDataRef.current = marketData; }, [marketData]);

  // Centralized chart instance tracking for proper cleanup
  const activeCharts = useRef<echarts.ECharts[]>([]);

  useEffect(() => {
    getUnderlyings()
      .then((u) => {
        setUnderlyings(u);
        if (u.length > 0) setSelectedUnderlying(u[0].symbol);
      })
      .catch(() => {});
  }, []);

  // Load trade dates and contracts
  useEffect(() => {
    if (!selectedUnderlying) return;
    getTradeDates(selectedUnderlying)
      .then((dates) => {
        setTradeDates(dates);
        tradeDateSet.current = new Set(dates);
        if (dates.length > 0) setSelectedDate(dates[dates.length - 1]);
      })
      .catch(() => setTradeDates([]));

    // Only load expiry dates list (lightweight), not all contracts
    getExpiryDates(selectedUnderlying)
      .then((expiries) => {
        setContractExpiries(expiries);
        setContractExpiry('');
        setSelectedContract('all');
        setContracts([]);
      })
      .catch(() => {
        setContractExpiries([]);
      });
  }, [selectedUnderlying]);

  // Lazy load contracts when expiry is selected
  useEffect(() => {
    if (!selectedUnderlying || !contractExpiry) {
      setContracts([]);
      return;
    }
    setContractsLoading(true);
    getUnderlyingContracts(selectedUnderlying, contractExpiry)
      .then((ctrs) => {
        setContracts(ctrs);
        // Auto-select first contract when contracts load
        if (ctrs.length > 0) {
          setSelectedContract(ctrs[0].symbol);
        }
      })
      .catch(() => setContracts([]))
      .finally(() => setContractsLoading(false));
  }, [selectedUnderlying, contractExpiry]);

  // Cleanup all charts on view change
  useEffect(() => {
    return () => disposeCharts(activeCharts);
  }, [view]);

  // Load data based on view
  const loadData = useCallback(async () => {
    if (!selectedUnderlying) return;
    setLoading(true);
    try {
      if (view === 'market') {
        const contractSymbol = selectedContract === 'all' ? undefined : selectedContract;
        const data = await getMarketOverview(selectedUnderlying, '2015-01-01', '2026-12-31', contractSymbol);
        setMarketData(data);
      } else if (view === 'vol2d' && selectedDate) {
        const [smileData, surfResp] = await Promise.all([
          getVolSmile(selectedUnderlying, selectedDate),
          getVolSurfaceV2(selectedUnderlying, selectedDate, vol3dMode).catch(() => null),
        ]);
        setVolSmileData(smileData);
        setVol3dData(surfResp);
      } else if (view === 'vol3d' && selectedDate) {
        const resp = await getVolSurfaceV2(selectedUnderlying, selectedDate, vol3dMode);
        setVol3dData(resp);
      } else if (view === 'chain' && selectedDate) {
        const data = await getOptionChain(selectedUnderlying, selectedDate);
        setOptionChainData(data);
      }
    } catch (e) {
      console.error('加载可视化数据失败:', e);
      // Reset data on error to avoid stale state / blank page
      if (view === 'vol3d') setVol3dData(null);
    } finally {
      setLoading(false);
    }
  }, [selectedUnderlying, view, selectedDate, selectedContract, vol3dMode]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ===================== MARKET: Candlestick + IV + Volume =====================
  useEffect(() => {
    if (view !== 'market' || !marketData || !marketChartRef.current) return;
    disposeCharts(activeCharts);

    const chart = echarts.init(marketChartRef.current);
    activeCharts.current.push(chart);

    const hasOhlc = marketData.ohlc && marketData.ohlc.length > 0;
    const isContractMode = marketData.contractInfo != null;

    const series: any[] = [];
    const legendData: string[] = [];
    const yAxisConfig: any[] = [];

    // ---- Grid layout ----
    // Main chart: top 50px, height 65%
    // Volume: starts at 72%, height 15%, with gap
    const gridConfig = [
      { left: 70, right: 70, top: 50, height: '65%' },
      { left: 70, right: 70, top: '72%', height: '15%' },
    ];

    // ---- Price Y-axis (grid 0, yAxis 0) ----
    yAxisConfig.push({
      gridIndex: 0, type: 'value',
      name: isContractMode ? '期权价格' : '标的价格',
      position: 'left',
      axisLabel: { fontSize: 10 },
      scale: true,
      splitArea: { show: true, areaStyle: { color: ['rgba(250,250,250,0.3)', 'rgba(240,240,240,0.3)'] } },
      splitLine: { show: true, lineStyle: { type: 'dashed', color: '#e0e0e0' } },
    });

    // ---- Price series ----
    if (hasOhlc) {
      series.push({
        name: isContractMode ? '期权价格' : '50ETF',
        type: 'candlestick',
        data: marketData.ohlc,
        xAxisIndex: 0, yAxisIndex: 0,
        large: true,
        itemStyle: { color: '#ef5350', color0: '#26a69a', borderColor: '#ef5350', borderColor0: '#26a69a' },
      });
      legendData.push(isContractMode ? '期权价格' : '50ETF');
    } else {
      series.push({
        name: isContractMode ? '期权价格' : '收盘价',
        type: 'line', data: marketData.prices,
        xAxisIndex: 0, yAxisIndex: 0,
        lineStyle: { width: 1.5 }, symbol: 'none',
        itemStyle: { color: '#1a73e8' },
      });
      legendData.push(isContractMode ? '期权价格' : '收盘价');
    }

    // ---- Indicator Y-axis: single normalized 0-1 axis (hidden, for overlay only) ----
    yAxisConfig.push({
      gridIndex: 0, type: 'value',
      min: 0, max: 1,
      axisLabel: { show: false },
      axisLine: { show: false },
      splitLine: { show: false },
      axisPointer: { show: false, label: { show: false } },
    });

    // ---- Helper: min-max normalize to [0, 1] ----
    const normalize = (data: (number | null)[]): { norm: (number | null)[]; min: number; max: number } => {
      const valid = data.filter((v): v is number => v != null && !isNaN(Number(v)));
      if (valid.length === 0) return { norm: data, min: 0, max: 1 };
      const min = Math.min(...valid);
      const max = Math.max(...valid);
      if (max === min) return { norm: data, min, max };
      const norm = data.map((v) =>
        v != null ? (Number(v) - min) / (max - min) : null
      );
      return { norm, min, max };
    };

    // ---- Color + style map ----
    const indicatorColors: Record<string, string> = {
      iv: '#f9ab00',       // ATM IV — solid
      delta: '#00acc1',    // Delta — dotted
      gamma: '#8e24aa',    // Gamma — dotted
      theta: '#fb8c00',    // Theta — dotted
      vega: '#43a047',     // Vega — dotted
    };
    const lineStyles: Record<string, string | undefined> = {
      iv: undefined,        // solid
      delta: 'dotted',
      gamma: 'dotted',
      theta: 'dotted',
      vega: 'dotted',
    };
    // Raw value accessors — keyed by indicator id
    const rawMap: Record<string, (number | null)[] | undefined> = {
      iv: marketData.ivs,
      delta: marketData.deltas,
      gamma: marketData.gammas,
      theta: marketData.thetas,
      vega: marketData.vegas,
    };
    // Map from display label → indicator id (for tooltip raw-value lookup)
    const labelToRawKey: Record<string, string> = {};

    for (const indId of selectedIndicators) {
      const raw = rawMap[indId];
      if (!raw) continue;
      const { norm } = normalize(raw);
      const color = indicatorColors[indId] || '#999';
      const style = lineStyles[indId];
      const label = indId === 'iv'
        ? (isContractMode ? 'IV' : 'ATM IV')
        : indId.charAt(0).toUpperCase() + indId.slice(1);

      labelToRawKey[label] = indId;

      // Embed raw value into each data point so tooltip always has access
      const dataWithRaw = norm.map((n, i) => (
        n != null ? { value: n, raw: raw[i], indId } : null
      ));

      series.push({
        name: label,
        type: 'line',
        data: dataWithRaw,
        xAxisIndex: 0, yAxisIndex: 1,
        lineStyle: {
          width: 1.5,
          color,
          type: style || 'solid',
        },
        symbol: 'none',
        itemStyle: { color },
        connectNulls: true,
      });
      legendData.push(label);
    }

    // ---- Volume Y-axis (grid 1, hidden label) ----
    const validVolumes = marketData.volumes.filter((v: number) => v > 0);
    const maxVolume = validVolumes.length > 0 ? Math.max(...validVolumes) : 1;
    yAxisConfig.push({
      gridIndex: 1, type: 'value',
      position: 'left', max: maxVolume,
      axisLabel: { show: false },
      axisLine: { show: false },
      splitLine: { show: false },
    });

    // ---- Volume series: color by OI change (positive=red/buying, negative=green/selling) ----
    const ois = marketData.openInterests;
    series.push({
      name: '成交量', type: 'bar',
      data: marketData.volumes,
      xAxisIndex: 1, yAxisIndex: yAxisConfig.length - 1,
      itemStyle: {
        color: (params: { dataIndex: number }) => {
          if (ois && ois.length > 0) {
            const idx = params.dataIndex;
            const oiDelta = idx > 0 ? (ois[idx] - ois[idx - 1]) : 0;
            return oiDelta >= 0 ? 'rgba(239,83,80,0.5)' : 'rgba(38,166,154,0.5)';
          }
          if (!hasOhlc) return 'rgba(26,115,232,0.5)';
          const ohlc = marketData.ohlc[params.dataIndex];
          return ohlc && ohlc[1] >= ohlc[0] ? 'rgba(239,83,80,0.5)' : 'rgba(38,166,154,0.5)';
        },
      },
    });
    legendData.push('成交量');

    chart.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          link: [{ xAxisIndex: [0, 1] }],
        },
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          const dataIndex = params[0].dataIndex;
          const md = marketDataRef.current;
          if (!md) return '';
          const date = md.dates[dataIndex];
          if (!date) return '';
          let html = `<strong>${date}</strong><br/>`;

          for (const p of params) {
            if (p.seriesType === 'candlestick') {
              // Directly read from marketDataRef to avoid ECharts data transformation issues
              const ohlcArr = Array.isArray(md.ohlc[dataIndex]) ? md.ohlc[dataIndex] : null;
              if (!ohlcArr) continue;
              const open = Number(ohlcArr[0]);
              const close = Number(ohlcArr[1]);
              const low = Number(ohlcArr[2]);
              const high = Number(ohlcArr[3]);
              if (isNaN(open) || isNaN(close)) continue;
              const isUp = close >= open;
              const color = isUp ? '#ef5350' : '#26a69a';
              html += `<span style="color:${color}">●</span> <strong>${p.seriesName}</strong><br/>`;
              html += `<span style="color:#999">　　开</span> ${open.toFixed(4)}<br/>`;
              html += `<span style="color:#999">　　收</span> <span style="color:${color}">${close.toFixed(4)}</span><br/>`;
              html += `<span style="color:#999">　　低</span> ${low.toFixed(4)}<br/>`;
              html += `<span style="color:#999">　　高</span> ${high.toFixed(4)}<br/>`;
            } else if (p.data != null && typeof p.data === 'object' && 'raw' in p.data) {
              // Indicator series: raw value is embedded in the data point
              const rawVal = p.data.raw;
              const indId = p.data.indId as string;
              if (rawVal != null) {
                const color = indicatorColors[indId] || p.color || '#999';
                const formatted = Number(rawVal).toFixed(4);
                html += `<span style="color:${color}">●</span> <span style="color:${color}">${p.seriesName}: ${formatted}</span><br/>`;
              }
            } else if (p.seriesName === '成交量') {
              const val = Number(p.data);
              if (!isNaN(val)) {
                html += `<span style="color:rgba(26,115,232,0.7)">●</span> <span style="color:rgba(26,115,232,0.9)">成交量: ${val.toLocaleString()}</span><br/>`;
              }
            } else if (p.data != null) {
              const val = Number(p.data);
              if (!isNaN(val)) {
                const color = p.color || '#999';
                html += `<span style="color:${color}">●</span> <span style="color:${color}">${p.seriesName}: ${val.toFixed(4)}</span><br/>`;
              }
            }
          }

          // Fallback volume from ref
          const volParam = params.find((p: any) => p.seriesName === '成交量');
          if (!volParam) {
            const vol = md.volumes[dataIndex];
            if (vol != null && vol > 0) {
              html += `<span style="color:rgba(26,115,232,0.7)">●</span> <span style="color:rgba(26,115,232,0.9)">成交量: ${Number(vol).toLocaleString()}</span><br/>`;
            }
          }

          return html;
        },
      },
      axisPointer: {
        link: [{ xAxisIndex: [0, 1] }],
        label: { backgroundColor: '#777' },
      },
      legend: {
        data: legendData, top: 10,
        selected: Object.fromEntries(legendData.map(name => [name, true])),
      },
      grid: gridConfig,
      xAxis: [
        {
          gridIndex: 0, type: 'category',
          data: marketData.dates,
          axisLabel: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
          boundaryGap: hasOhlc,
        },
        {
          gridIndex: 1, type: 'category',
          data: marketData.dates,
          axisLabel: { show: false },
          axisTick: { show: false },
          axisPointer: { label: { show: false } },
          boundaryGap: true,
        },
      ],
      yAxis: yAxisConfig,
      series,
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1] },
      ],
    });

    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
    };
  }, [view, marketData, selectedIndicators]);

  // ===================== VOL 2D: per-expiry charts with unified IV =====================
  useEffect(() => {
    if (view !== 'vol2d' || volSmileData.length === 0) return;
    disposeCharts(activeCharts);

    // Small delay to ensure DOM refs are ready after React render
    const timer = setTimeout(() => {
      volSmileData.forEach((group, idx) => {
        const el = document.getElementById(`vol2d-chart-${idx}`);
        if (!el) return;
        const chart = echarts.init(el);
        activeCharts.current.push(chart);
        renderVol2dChart(chart, group, vol3dData, vol3dUseSvi, vol3dXAxis);
      });
    }, 50);

    const onResize = () => activeCharts.current.forEach((c) => c.resize());
    window.addEventListener('resize', onResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', onResize);
    };
  }, [view, volSmileData, vol3dData, vol3dUseSvi, vol3dXAxis]);

  // ===================== VOL 3D: now handled by Vol3DSurface component =====================

  // Date picker handler: snap to nearest valid trade date
  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newDate = e.target.value;
    if (!newDate) return;
    const snapped = snapToTradeDate(newDate, tradeDates);
    setSelectedDate(snapped);
  };

  // Navigate to prev/next trade date
  const navigateDate = (dir: -1 | 1) => {
    if (tradeDates.length === 0) return;
    const idx = tradeDates.indexOf(selectedDate);
    const newIdx = idx + dir;
    if (newIdx >= 0 && newIdx < tradeDates.length) {
      setSelectedDate(tradeDates[newIdx]);
    }
  };

  return (
    <div className="viz-page">
      {/* Toolbar */}
      <div className="viz-toolbar">
        <div className="viz-toolbar-left">
          <div className="form-group">
            <label>标的</label>
            <select
              className="form-select"
              value={selectedUnderlying}
              onChange={(e) => setSelectedUnderlying(e.target.value)}
              style={{ width: 140 }}
            >
              {underlyings.map((u) => (
                <option key={u.symbol} value={u.symbol}>{u.symbol} - {u.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>颗粒度</label>
            <select
              className="form-select"
              value={granularity}
              disabled
              title="分钟数据暂未支持"
              style={{ width: 100, opacity: 0.6 }}
            >
              <option value="daily">日级别</option>
              <option value="minute" disabled>分钟级别</option>
            </select>
          </div>

          {view === 'market' && (
            <>
              <div className="form-group">
                <label>到期日</label>
                <select
                  className="form-select"
                  value={contractExpiry}
                  onChange={(e) => {
                    const newExpiry = e.target.value;
                    setContractExpiry(newExpiry);
                    setContracts([]);
                    // Reset to 'all' when switching back to underlying
                    if (!newExpiry) {
                      setSelectedContract('all');
                    }
                  }}
                  style={{ width: 140 }}
                >
                  <option value="">标的</option>
                  {contractExpiries.map((exp) => (
                    <option key={exp} value={exp}>{exp}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>合约</label>
                <select
                  className="form-select"
                  value={selectedContract}
                  onChange={(e) => {
                    setSelectedContract(e.target.value);
                  }}
                  style={{ width: 220 }}
                  disabled={!contractExpiry || contractsLoading}
                >
                  {!contractExpiry && <option value="all">标的ETF</option>}
                  {contractsLoading ? (
                    <option disabled>加载中...</option>
                  ) : (
                    contracts.map((c) => (
                      <option key={c.symbol} value={c.symbol}>
                        {c.type === 'C' ? 'C' : 'P'} {c.strike} ({c.expiry.slice(5)})
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div className="form-group">
                <label>指标</label>
                <select
                  className="form-select"
                  value=""
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value && !selectedIndicators.includes(value)) {
                      setSelectedIndicators([...selectedIndicators, value]);
                    }
                  }}
                  style={{ width: 180 }}
                >
                  <option value="">添加指标...</option>
                  {availableIndicators
                    .filter(ind => !selectedIndicators.includes(ind.id))
                    .map((ind) => (
                      <option key={ind.id} value={ind.id}>
                        {ind.name}
                      </option>
                    ))}
                </select>
                {selectedIndicators.length > 0 && (
                  <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {selectedIndicators.map((id) => {
                      const ind = availableIndicators.find(i => i.id === id);
                      return ind ? (
                        <span
                          key={id}
                          style={{
                            padding: '2px 8px',
                            fontSize: 12,
                            background: '#e3f2fd',
                            borderRadius: 4,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                          }}
                        >
                          {ind.name}
                          <button
                            onClick={() => setSelectedIndicators(selectedIndicators.filter(i => i !== id))}
                            style={{
                              border: 'none',
                              background: 'transparent',
                              cursor: 'pointer',
                              padding: 0,
                              fontSize: 14,
                              color: '#666',
                            }}
                          >
                            ×
                          </button>
                        </span>
                      ) : null;
                    })}
                  </div>
                )}
              </div>
            </>
          )}

          {(view === 'vol2d' || view === 'vol3d' || view === 'chain') && (
            <div className="form-group">
              <label>交易日</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '4px 8px', fontSize: 12 }}
                  onClick={() => navigateDate(-1)}
                  disabled={tradeDates.indexOf(selectedDate) <= 0}
                  title="上一交易日"
                >&lt;</button>
                <input
                  type="date"
                  className="form-input"
                  value={selectedDate}
                  onChange={handleDateChange}
                  min={tradeDates[0] || ''}
                  max={tradeDates[tradeDates.length - 1] || ''}
                  style={{ width: 150 }}
                />
                <button
                  className="btn btn-secondary"
                  style={{ padding: '4px 8px', fontSize: 12 }}
                  onClick={() => navigateDate(1)}
                  disabled={tradeDates.indexOf(selectedDate) >= tradeDates.length - 1}
                  title="下一交易日"
                >&gt;</button>
              </div>
            </div>
          )}

          {(view === 'vol2d' || view === 'vol3d') && (
            <>
              <div className="form-group">
                <label>IV来源</label>
                <div style={{ display: 'flex', gap: 2, background: 'var(--bg-secondary)', borderRadius: 6, padding: 2 }}>
                  <button
                    style={{
                      padding: '4px 12px', fontSize: 12, border: 'none', borderRadius: 4, cursor: 'pointer',
                      background: vol3dMode === 'raw' ? 'var(--bg-card)' : 'transparent',
                      fontWeight: vol3dMode === 'raw' ? 600 : 400,
                      boxShadow: vol3dMode === 'raw' ? 'var(--shadow-sm)' : 'none',
                      color: 'var(--text-primary)',
                    }}
                    onClick={() => setVol3dMode('raw')}
                  >数据库 IV</button>
                  <button
                    style={{
                      padding: '4px 12px', fontSize: 12, border: 'none', borderRadius: 4, cursor: 'pointer',
                      background: vol3dMode === 'synthetic' ? 'var(--bg-card)' : 'transparent',
                      fontWeight: vol3dMode === 'synthetic' ? 600 : 400,
                      boxShadow: vol3dMode === 'synthetic' ? 'var(--shadow-sm)' : 'none',
                      color: 'var(--text-primary)',
                    }}
                    onClick={() => setVol3dMode('synthetic')}
                  >合成数据</button>
                </div>
              </div>
              <div className="form-group">
                <label>曲面拟合</label>
                <div style={{ display: 'flex', gap: 2, background: 'var(--bg-secondary)', borderRadius: 6, padding: 2 }}>
                  <button
                    style={{
                      padding: '4px 12px', fontSize: 12, border: 'none', borderRadius: 4, cursor: 'pointer',
                      background: vol3dUseSvi ? 'var(--bg-card)' : 'transparent',
                      fontWeight: vol3dUseSvi ? 600 : 400,
                      boxShadow: vol3dUseSvi ? 'var(--shadow-sm)' : 'none',
                      color: 'var(--text-primary)',
                    }}
                    onClick={() => setVol3dUseSvi(true)}
                  >SVI 拟合</button>
                  <button
                    style={{
                      padding: '4px 12px', fontSize: 12, border: 'none', borderRadius: 4, cursor: 'pointer',
                      background: !vol3dUseSvi ? 'var(--bg-card)' : 'transparent',
                      fontWeight: !vol3dUseSvi ? 600 : 400,
                      boxShadow: !vol3dUseSvi ? 'var(--shadow-sm)' : 'none',
                      color: 'var(--text-primary)',
                    }}
                    onClick={() => setVol3dUseSvi(false)}
                  >三次样条</button>
                </div>
              </div>
              <div className="form-group">
                <label>X轴</label>
                <div style={{ display: 'flex', gap: 2, background: 'var(--bg-secondary)', borderRadius: 6, padding: 2 }}>
                  <button
                    style={{
                      padding: '4px 12px', fontSize: 12, border: 'none', borderRadius: 4, cursor: 'pointer',
                      background: vol3dXAxis === 'strike' ? 'var(--bg-card)' : 'transparent',
                      fontWeight: vol3dXAxis === 'strike' ? 600 : 400,
                      boxShadow: vol3dXAxis === 'strike' ? 'var(--shadow-sm)' : 'none',
                      color: 'var(--text-primary)',
                    }}
                    onClick={() => setVol3dXAxis('strike')}
                  >行权价</button>
                  <button
                    style={{
                      padding: '4px 12px', fontSize: 12, border: 'none', borderRadius: 4, cursor: 'pointer',
                      background: vol3dXAxis === 'moneyness' ? 'var(--bg-card)' : 'transparent',
                      fontWeight: vol3dXAxis === 'moneyness' ? 600 : 400,
                      boxShadow: vol3dXAxis === 'moneyness' ? 'var(--shadow-sm)' : 'none',
                      color: 'var(--text-primary)',
                    }}
                    onClick={() => setVol3dXAxis('moneyness')}
                  >Moneyness</button>
                </div>
              </div>
            </>
          )}

          {view === 'chain' && (
            <div className="form-group">
              <label>显示列</label>
              <div style={{ position: 'relative' }}>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '6px 12px', fontSize: 12 }}
                  onClick={(e) => {
                    const menu = e.currentTarget.nextElementSibling as HTMLElement;
                    if (menu) menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
                  }}
                >
                  列选择 ▾
                </button>
                <div
                  style={{
                    display: 'none',
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    marginTop: 4,
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 8,
                    padding: '8px',
                    boxShadow: 'var(--shadow-md)',
                    zIndex: 1000,
                    minWidth: 180,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {[
                    { key: 'bid', label: '买价' },
                    { key: 'ask', label: '卖价' },
                    { key: 'last', label: '最新价' },
                    { key: 'volume', label: '成交量' },
                    { key: 'openInterest', label: '持仓量' },
                    { key: 'iv', label: 'IV' },
                    { key: 'delta', label: 'Delta' },
                    { key: 'gamma', label: 'Gamma' },
                    { key: 'theta', label: 'Theta' },
                    { key: 'vega', label: 'Vega' },
                  ].map((col) => (
                    <label
                      key={col.key}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '4px 8px',
                        cursor: 'pointer',
                        fontSize: 13,
                        gap: 8,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={chainColumns[col.key as keyof typeof chainColumns]}
                        onChange={(e) => {
                          setChainColumns({ ...chainColumns, [col.key]: e.target.checked });
                        }}
                      />
                      {col.label}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="viz-toolbar-right">
          <button
            className={`viz-view-btn ${view === 'market' ? 'active' : ''}`}
            onClick={() => setView('market')}
          >
            行情
          </button>
          <button
            className={`viz-view-btn ${view === 'chain' ? 'active' : ''}`}
            onClick={() => setView('chain')}
          >
            期权链
          </button>
          <button
            className={`viz-view-btn ${view === 'vol2d' ? 'active' : ''}`}
            onClick={() => setView('vol2d')}
          >
            波动率 2D
          </button>
          <button
            className={`viz-view-btn ${view === 'vol3d' ? 'active' : ''}`}
            onClick={() => setView('vol3d')}
          >
            波动率 3D
          </button>
        </div>
      </div>

      {/* Chart Area */}
      <div className="viz-chart-area">
        {loading ? (
          <div className="loading-container" style={{ minHeight: 400 }}>
            <div className="spinner" />
            <span>加载图表数据...</span>
          </div>
        ) : (
          <>
            {view === 'market' && (
              <div ref={marketChartRef} style={{ width: '100%', height: 'calc(100vh - 160px)' }} />
            )}

            {view === 'vol2d' && (
              volSmileData.length > 0 ? (
                <div className="vol2d-container">
                  {/* Left panels: ATM IV + Skew (from vol3d surface data) */}
                  {vol3dData && (
                    <VolLeftPanels
                      atmRows={(vol3dData.atmIvData || []).map((p: AtmIvPoint) => ({
                        expiry: p.expiry, days: p.remainingDays, prev: p.prevAtmIv, cur: p.atmIv,
                        diff: p.prevAtmIv != null ? p.atmIv - p.prevAtmIv : null,
                      }))}
                      skewRows={(vol3dData.skewData || []).map((p: SkewPoint) => ({
                        expiry: p.expiry, days: p.remainingDays, prev: p.prevSkew, cur: p.skew,
                        diff: p.prevSkew != null ? p.skew - p.prevSkew : null,
                      }))}
                    />
                  )}
                  {/* Right side: per-expiry smile charts */}
                  <div className="vol2d-right">
                    <div className="vol2d-grid">
                      {volSmileData.map((group, idx) => {
                        const isSynth = vol3dData?.mode === 'synthetic';
                        const synthFwd = isSynth ? vol3dData?.syntheticForwards?.[group.expiry] : undefined;
                        const refPrice = synthFwd ?? group.todayUnderlyingClose;
                        const ydRefPrice = isSynth
                          ? (vol3dData?.yesterdaySyntheticForwards?.[group.expiry] ?? group.yesterdayUnderlyingClose)
                          : group.yesterdayUnderlyingClose;
                        return (
                        <div key={group.contractMonth} className="vol2d-card">
                          {/* Header bar */}
                          <div className="vol2d-header">
                            <div className="vol2d-header-left">
                              <span className="vol2d-month">{group.contractMonth}</span>
                              <span className="vol2d-expiry">{group.daysToExpiry}天到期</span>
                            </div>
                            <div className="vol2d-header-center">
                              <span className="vol2d-price">
                                标的: {group.todayUnderlyingClose.toFixed(4)}
                              </span>
                              {group.yesterdayUnderlyingClose > 0 && (
                                <span className={
                                  group.todayUnderlyingClose >= group.yesterdayUnderlyingClose
                                    ? 'vol2d-change positive' : 'vol2d-change negative'
                                }>
                                  {((group.todayUnderlyingClose - group.yesterdayUnderlyingClose) / group.yesterdayUnderlyingClose * 100).toFixed(2)}%
                                </span>
                              )}
                              {isSynth && synthFwd != null && (
                                <>
                                  <span className="vol2d-price" style={{ marginLeft: 6, color: '#1a73e8' }}>
                                    合成: {synthFwd.toFixed(4)}
                                  </span>
                                  {(() => {
                                    const ydSynthFwd = vol3dData?.yesterdaySyntheticForwards?.[group.expiry];
                                    return ydSynthFwd != null && ydSynthFwd > 0 ? (
                                      <span className={
                                        synthFwd >= ydSynthFwd
                                          ? 'vol2d-change positive' : 'vol2d-change negative'
                                      }>
                                        {((synthFwd - ydSynthFwd) / ydSynthFwd * 100).toFixed(2)}%
                                      </span>
                                    ) : null;
                                  })()}
                                </>
                              )}
                            </div>
                            <div className="vol2d-header-right">
                              {(() => {
                                const atmStrike = group.strikes.reduce<VolSmileStrike | null>((best, s) => {
                                  if (!best) return s;
                                  return Math.abs(s.strike - refPrice) <
                                         Math.abs(best.strike - refPrice) ? s : best;
                                }, null);
                                const atmIv = atmStrike?.callIv;
                                return atmIv != null ? (
                                  <span className="vol2d-atm">ATM IV: {(atmIv * 100).toFixed(1)}%</span>
                                ) : null;
                              })()}
                            </div>
                          </div>
                          {/* Chart container */}
                          <div id={`vol2d-chart-${idx}`} style={{ width: '100%', height: 360 }} />
                        </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">📈</div>
                  <h3>暂无波动率数据</h3>
                  <p>请选择交易日查看波动率微笑曲线</p>
                </div>
              )
            )}

            {view === 'vol3d' && (
              vol3dData && vol3dData.points.length > 0 ? (
                <div style={{
                  width: '100%', height: 'calc(100vh - 160px)',
                  background: 'var(--bg-card)', borderRadius: 12,
                  boxShadow: 'var(--shadow-sm)', overflow: 'hidden',
                }}>
                  <Vol3DSurface data={vol3dData} mode={vol3dMode} useSvi={vol3dUseSvi} xAxisMode={vol3dXAxis} />
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">🌐</div>
                  <h3>暂无波动率曲面数据</h3>
                  <p>请选择交易日查看波动率曲面</p>
                </div>
              )
            )}

            {view === 'chain' && (
              optionChainData.length > 0 ? (
                <div style={{ padding: '20px', overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }}>
                  {optionChainData.map((chainGroup) => {
                    // Calculate visible columns count
                    const visibleCols = Object.values(chainColumns).filter(Boolean).length;

                    return (
                      <div key={chainGroup.expiry} style={{ marginBottom: 40 }}>
                        <div style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: 12,
                          padding: '8px 12px',
                          background: 'var(--bg-secondary)',
                          borderRadius: 8,
                        }}>
                          <h3 style={{ margin: 0, fontSize: 16 }}>到期日: {chainGroup.expiry}</h3>
                          <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                            标的价格: {chainGroup.underlyingPrice.toFixed(4)}
                          </span>
                        </div>
                        <div style={{ overflowX: 'auto' }}>
                          <table style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            fontSize: 12,
                            background: 'var(--bg-card)',
                            borderRadius: 8,
                            overflow: 'hidden',
                          }}>
                            <thead>
                              <tr style={{ background: 'var(--bg-secondary)' }}>
                                <th colSpan={visibleCols} style={{ padding: '8px', textAlign: 'center', borderRight: '2px solid var(--border-color)' }}>Call</th>
                                <th style={{ padding: '8px', textAlign: 'center', fontWeight: 'bold' }}>行权价</th>
                                <th colSpan={visibleCols} style={{ padding: '8px', textAlign: 'center', borderLeft: '2px solid var(--border-color)' }}>Put</th>
                              </tr>
                              <tr style={{ background: 'var(--bg-tertiary)', fontSize: 11 }}>
                                {chainColumns.bid && <th style={{ padding: '6px 8px', textAlign: 'right' }}>买价</th>}
                                {chainColumns.ask && <th style={{ padding: '6px 8px', textAlign: 'right' }}>卖价</th>}
                                {chainColumns.last && <th style={{ padding: '6px 8px', textAlign: 'right' }}>最新</th>}
                                {chainColumns.volume && <th style={{ padding: '6px 8px', textAlign: 'right' }}>成交量</th>}
                                {chainColumns.openInterest && <th style={{ padding: '6px 8px', textAlign: 'right' }}>持仓</th>}
                                {chainColumns.iv && <th style={{ padding: '6px 8px', textAlign: 'right' }}>IV</th>}
                                {chainColumns.delta && <th style={{ padding: '6px 8px', textAlign: 'right', borderRight: '2px solid var(--border-color)' }}>Delta</th>}
                                {chainColumns.gamma && <th style={{ padding: '6px 8px', textAlign: 'right', borderRight: '2px solid var(--border-color)' }}>Gamma</th>}
                                {chainColumns.theta && <th style={{ padding: '6px 8px', textAlign: 'right', borderRight: '2px solid var(--border-color)' }}>Theta</th>}
                                {chainColumns.vega && <th style={{ padding: '6px 8px', textAlign: 'right', borderRight: '2px solid var(--border-color)' }}>Vega</th>}
                                <th style={{ padding: '6px 8px', textAlign: 'center', fontWeight: 'bold' }}>Strike</th>
                                {chainColumns.vega && <th style={{ padding: '6px 8px', textAlign: 'right', borderLeft: '2px solid var(--border-color)' }}>Vega</th>}
                                {chainColumns.theta && <th style={{ padding: '6px 8px', textAlign: 'right', borderLeft: '2px solid var(--border-color)' }}>Theta</th>}
                                {chainColumns.gamma && <th style={{ padding: '6px 8px', textAlign: 'right', borderLeft: '2px solid var(--border-color)' }}>Gamma</th>}
                                {chainColumns.delta && <th style={{ padding: '6px 8px', textAlign: 'right', borderLeft: '2px solid var(--border-color)' }}>Delta</th>}
                                {chainColumns.iv && <th style={{ padding: '6px 8px', textAlign: 'right' }}>IV</th>}
                                {chainColumns.openInterest && <th style={{ padding: '6px 8px', textAlign: 'right' }}>持仓</th>}
                                {chainColumns.volume && <th style={{ padding: '6px 8px', textAlign: 'right' }}>成交量</th>}
                                {chainColumns.last && <th style={{ padding: '6px 8px', textAlign: 'right' }}>最新</th>}
                                {chainColumns.ask && <th style={{ padding: '6px 8px', textAlign: 'right' }}>卖价</th>}
                                {chainColumns.bid && <th style={{ padding: '6px 8px', textAlign: 'right' }}>买价</th>}
                              </tr>
                            </thead>
                            <tbody>
                              {chainGroup.strikes.map((row) => {
                                const isATM = Math.abs(row.strike - chainGroup.underlyingPrice) < 0.1;
                                const rowStyle = isATM ? { background: 'rgba(26, 115, 232, 0.08)', fontWeight: 500 } : {};

                                return (
                                  <tr key={row.strike} style={rowStyle}>
                                    {/* Call 数据 */}
                                    {chainColumns.bid && <td style={{ padding: '6px 8px', textAlign: 'right' }}>{row.call?.bid?.toFixed(4) || '-'}</td>}
                                    {chainColumns.ask && <td style={{ padding: '6px 8px', textAlign: 'right' }}>{row.call?.ask?.toFixed(4) || '-'}</td>}
                                    {chainColumns.last && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', color: row.call?.last ? '#1a73e8' : undefined }}>
                                        {row.call?.last?.toFixed(4) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.volume && <td style={{ padding: '6px 8px', textAlign: 'right' }}>{row.call?.volume?.toLocaleString() || '-'}</td>}
                                    {chainColumns.openInterest && <td style={{ padding: '6px 8px', textAlign: 'right' }}>{row.call?.openInterest?.toLocaleString() || '-'}</td>}
                                    {chainColumns.iv && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                                        {row.call?.iv ? `${(row.call.iv * 100).toFixed(1)}%` : '-'}
                                      </td>
                                    )}
                                    {chainColumns.delta && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', borderRight: visibleCols === Object.keys(chainColumns).indexOf('delta') + 1 ? '2px solid var(--border-color)' : undefined }}>
                                        {row.call?.delta?.toFixed(3) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.gamma && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', borderRight: '2px solid var(--border-color)' }}>
                                        {row.call?.gamma?.toFixed(4) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.theta && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', borderRight: '2px solid var(--border-color)' }}>
                                        {row.call?.theta?.toFixed(4) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.vega && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', borderRight: '2px solid var(--border-color)' }}>
                                        {row.call?.vega?.toFixed(4) || '-'}
                                      </td>
                                    )}

                                    {/* 行权价 */}
                                    <td style={{ padding: '6px 8px', textAlign: 'center', fontWeight: 'bold', background: isATM ? 'rgba(26, 115, 232, 0.15)' : undefined }}>
                                      {row.strike.toFixed(2)}
                                    </td>

                                    {/* Put 数据 */}
                                    {chainColumns.vega && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', borderLeft: '2px solid var(--border-color)' }}>
                                        {row.put?.vega?.toFixed(4) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.theta && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', borderLeft: '2px solid var(--border-color)' }}>
                                        {row.put?.theta?.toFixed(4) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.gamma && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', borderLeft: '2px solid var(--border-color)' }}>
                                        {row.put?.gamma?.toFixed(4) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.delta && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', borderLeft: '2px solid var(--border-color)' }}>
                                        {row.put?.delta?.toFixed(3) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.iv && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                                        {row.put?.iv ? `${(row.put.iv * 100).toFixed(1)}%` : '-'}
                                      </td>
                                    )}
                                    {chainColumns.openInterest && <td style={{ padding: '6px 8px', textAlign: 'right' }}>{row.put?.openInterest?.toLocaleString() || '-'}</td>}
                                    {chainColumns.volume && <td style={{ padding: '6px 8px', textAlign: 'right' }}>{row.put?.volume?.toLocaleString() || '-'}</td>}
                                    {chainColumns.last && (
                                      <td style={{ padding: '6px 8px', textAlign: 'right', color: row.put?.last ? '#e67e22' : undefined }}>
                                        {row.put?.last?.toFixed(4) || '-'}
                                      </td>
                                    )}
                                    {chainColumns.ask && <td style={{ padding: '6px 8px', textAlign: 'right' }}>{row.put?.ask?.toFixed(4) || '-'}</td>}
                                    {chainColumns.bid && <td style={{ padding: '6px 8px', textAlign: 'right' }}>{row.put?.bid?.toFixed(4) || '-'}</td>}
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">📊</div>
                  <h3>暂无期权链数据</h3>
                  <p>请选择交易日查看期权链</p>
                </div>
              )
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ===================== OTM Priority IV Blending (matches 3D backend logic) =====================

function blendIvOtmPriority(
  strike: number, spot: number,
  callIv: number | null, putIv: number | null,
): number | null {
  if (callIv == null && putIv == null) return null;
  if (spot <= 0) {
    if (callIv != null && putIv != null) return (callIv + putIv) / 2;
    return callIv ?? putIv;
  }
  // OTM priority: 2% band matching backend
  if (strike > spot * 1.02) return callIv ?? putIv;   // OTM call zone
  if (strike < spot * 0.98) return putIv ?? callIv;   // OTM put zone
  // Near-ATM: simple average (no vega available on client)
  if (callIv != null && putIv != null) return (callIv + putIv) / 2;
  return callIv ?? putIv;
}

// ===================== VOL 2D CHART RENDERER (unified with 3D surface) =====================

function renderVol2dChart(
  chart: echarts.ECharts,
  group: VolSmileGroup,
  surfaceData: VolSurfaceV2Response | null,
  useSvi: boolean,
  xAxisMode: 'strike' | 'moneyness',
) {
  const isSynthetic = surfaceData?.mode === 'synthetic';
  const spot = surfaceData?.spot ?? group.todayUnderlyingClose;
  const ydSpot = group.yesterdayUnderlyingClose;
  const strikes = group.strikes.map(s => s.strike);
  const isMoneyness = xAxisMode === 'moneyness';

  // Numeric x-axis values (value axis, not category)
  // Computed after fwd is known — placeholder here, filled below.

  // Synthetic forward prices per expiry (if available)
  const fwd = isSynthetic ? surfaceData?.syntheticForwards?.[group.expiry] ?? spot : spot;
  const ydFwd = isSynthetic
    ? surfaceData?.yesterdaySyntheticForwards?.[group.expiry] ?? ydSpot
    : ydSpot;

  // Reference price for moneyness calculation and vertical lines
  const refPrice = fwd;

  // X-axis numeric values (for value axis) and display labels (for tooltip)
  const xValues = isMoneyness
    ? strikes.map(k => refPrice > 0 ? Math.log(k / refPrice) : k)
    : [...strikes];
  const xLabels = isMoneyness
    ? xValues.map(v => v.toFixed(3))
    : strikes.map(k => k.toFixed(2));

  // === Today's blended IV from surface data (unified with 3D) ===
  const src = useSvi && surfaceData?.sviPoints?.length
    ? surfaceData.sviPoints
    : surfaceData?.points ?? [];
  const expiryPts = src.filter((p: Vol3DPoint) => p.expiry === group.expiry);

  const todayIvs: (number | null)[] = strikes.map((k, i) => {
    // Try matching surface point (within 0.5% of strike)
    let best: Vol3DPoint | null = null;
    let bestDist = Infinity;
    for (const p of expiryPts) {
      const d = Math.abs(p.strike - k);
      if (d < bestDist) { bestDist = d; best = p; }
    }
    if (best && bestDist < k * 0.005) return best.iv * 100;
    // Fallback: client-side OTM priority blending
    const s = group.strikes[i];
    const blended = blendIvOtmPriority(k, refPrice, s.callIv, s.putIv);
    return blended != null ? blended * 100 : null;
  });

  // === Yesterday's blended IV (client-side OTM priority) ===
  const ydRefPrice = ydFwd > 0 ? ydFwd : refPrice;
  const ydIvs: (number | null)[] = group.strikes.map(s => {
    const blended = blendIvOtmPriority(s.strike, ydRefPrice, s.yesterdayCallIv, s.yesterdayPutIv);
    return blended != null ? blended * 100 : null;
  });

  // === OI data: 4 bar series ===
  // Light colors = OI amount (持仓量), Dark colors = OI change (持仓增量, signed)
  // Green = put (看跌, left), Red = call (看涨, right)
  const callOiChanges = group.strikes.map(s => s.callOiChange ?? 0);
  const putOiChanges = group.strikes.map(s => s.putOiChange ?? 0);

  // X-offset so put (left) and call (right) bars don't overlap each other
  const sortedX = [...new Set(xValues)].sort((a, b) => a - b);
  const minGap = sortedX.length > 1
    ? Math.min(...sortedX.slice(1).map((v, i) => v - sortedX[i]))
    : 1;
  const xOff = minGap * 0.12;

  // Light bars: OI amount (always positive)
  const putOiLightBars = group.strikes.map((s, i) => ({
    value: [xValues[i] - xOff, s.putOi ?? 0],
  }));
  const callOiLightBars = group.strikes.map((s, i) => ({
    value: [xValues[i] + xOff, s.callOi ?? 0],
  }));
  // Dark bars: OI change (signed — positive above axis, negative below)
  // Same x as their light counterpart so they overlap visually
  const putOiDarkBars = group.strikes.map((s, i) => ({
    value: [xValues[i] - xOff, putOiChanges[i]],
  }));
  const callOiDarkBars = group.strikes.map((s, i) => ({
    value: [xValues[i] + xOff, callOiChanges[i]],
  }));

  // === Vertical markLines: blue solid = current ref price, gray dashed = yesterday ===
  // With value axis, markLine xAxis uses actual numeric values directly.
  const currentLabel = isSynthetic ? '合成现值' : '现价';
  const prevLabel = isSynthetic ? '合成昨收' : '昨收';

  const vMarkLines: any[] = [];
  if (fwd > 0) {
    vMarkLines.push({
      name: `${currentLabel}: ${fwd.toFixed(4)}`,
      xAxis: isMoneyness ? 0 : fwd,
      label: {
        show: false,
        formatter: '{b}',
      },
      emphasis: {
        lineStyle: { width: 3 },
        label: {
          show: true,
          position: 'insideStartTop',
          fontSize: 11,
          fontWeight: 600,
          color: '#1a73e8',
          backgroundColor: 'rgba(255,255,255,0.92)',
          padding: [3, 6],
          borderRadius: 3,
          borderColor: '#1a73e8',
          borderWidth: 1,
        },
      },
      lineStyle: { color: '#1a73e8', type: 'solid', width: 2 },
    });
  }
  if (ydFwd > 0 && Math.abs(ydFwd - fwd) > 0.0001) {
    vMarkLines.push({
      name: `${prevLabel}: ${ydFwd.toFixed(4)}`,
      xAxis: isMoneyness ? Math.log(ydFwd / refPrice) : ydFwd,
      label: {
        show: false,
        formatter: '{b}',
      },
      emphasis: {
        lineStyle: { width: 2.5 },
        label: {
          show: true,
          position: 'insideStartTop',
          fontSize: 11,
          fontWeight: 600,
          color: '#666',
          backgroundColor: 'rgba(255,255,255,0.92)',
          padding: [3, 6],
          borderRadius: 3,
          borderColor: '#999',
          borderWidth: 1,
        },
      },
      lineStyle: { color: '#999', type: 'dashed', width: 1.5 },
    });
  }

  // === Dynamic right Y-axis (must accommodate negative OI changes) ===
  const allOis = group.strikes.map(s => Math.max(s.callOi ?? 0, s.putOi ?? 0));
  const maxOi = Math.max(...allOis, 1);
  const minOiChange = Math.min(...callOiChanges, ...putOiChanges, 0);
  const rightMax = maxOi * 1.3;
  const rightMin = minOiChange < 0 ? minOiChange * 1.3 : -rightMax * 0.05;

  // Compute bar width: fraction of the minimum gap between adjacent x values (in data coords)
  // ECharts value-axis bars need explicit barWidth; we estimate a reasonable pixel-like width.
  const barWidthPx = strikes.length > 1 ? 6 : 12;

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any[]) => {
        if (!params || params.length === 0) return '';
        // For value axis, find the matching strike index from the x value
        const xVal = params[0].data != null
          ? (Array.isArray(params[0].data) ? params[0].data[0]
            : (typeof params[0].data === 'object' && params[0].data.value ? params[0].data.value[0] : null))
          : null;
        let idx = 0;
        if (xVal != null) {
          let bestDist = Infinity;
          for (let i = 0; i < xValues.length; i++) {
            const d = Math.abs(xValues[i] - xVal);
            if (d < bestDist) { bestDist = d; idx = i; }
          }
        }
        const strike = strikes[idx];
        let html = `<strong>${isMoneyness ? 'M: ' + xLabels[idx] : '行权价: ' + strike}</strong><br/>`;
        const cMap: Record<string, string> = {
          'IV (今)': '#7c3aed', 'IV (昨)': '#bbb',
          '看跌持仓': 'rgba(30,150,60,0.7)', '看涨持仓': 'rgba(220,60,60,0.7)',
          '看跌增量': 'rgba(20,120,40,0.95)', '看涨增量': 'rgba(180,30,30,0.95)',
        };
        // Collect OI data per side for combined tooltip display
        let callOiVal: number | null = null;
        let putOiVal: number | null = null;
        const ivLines: string[] = [];
        params.forEach(p => {
          if (p.data == null || p.seriesName === currentLabel || p.seriesName === prevLabel) return;
          let val: number | null = null;
          if (Array.isArray(p.data)) {
            val = p.data[1];
          } else if (typeof p.data === 'object' && p.data.value) {
            val = Array.isArray(p.data.value) ? p.data.value[1] : p.data.value;
          } else if (typeof p.data === 'number') {
            val = p.data;
          }
          if (val == null) return;
          const c = cMap[p.seriesName] || p.color || '#999';
          if (p.seriesName.includes('IV')) {
            ivLines.push(`<span style="color:${c}">●</span> <span style="color:${c}">${p.seriesName}: ${val.toFixed(2)}%</span><br/>`);
          } else if (p.seriesName === '看涨持仓') {
            callOiVal = val;
          } else if (p.seriesName === '看跌持仓') {
            putOiVal = val;
          }
        });
        ivLines.forEach(l => { html += l; });
        // Call OI + change
        if (callOiVal != null) {
          const chg = callOiChanges[idx];
          const chgColor = chg > 0 ? '#c00' : chg < 0 ? '#090' : '#999';
          const chgStr = chg > 0 ? `+${chg.toLocaleString()}` : chg.toLocaleString();
          html += `<span style="color:rgba(220,60,60,0.9)">●</span> <span style="color:rgba(220,60,60,0.9)">看涨持仓: ${(callOiVal as number).toLocaleString()}</span> (<span style="color:${chgColor}">${chgStr}</span>)<br/>`;
        }
        // Put OI + change
        if (putOiVal != null) {
          const chg = putOiChanges[idx];
          const chgColor = chg > 0 ? '#c00' : chg < 0 ? '#090' : '#999';
          const chgStr = chg > 0 ? `+${chg.toLocaleString()}` : chg.toLocaleString();
          html += `<span style="color:rgba(30,150,60,0.9)">●</span> <span style="color:rgba(30,150,60,0.9)">看跌持仓: ${(putOiVal as number).toLocaleString()}</span> (<span style="color:${chgColor}">${chgStr}</span>)<br/>`;
        }
        return html;
      },
    },
    legend: {
      data: ['IV (今)', 'IV (昨)', currentLabel, prevLabel, '看跌持仓', '看涨持仓', '看跌增量', '看涨增量'],
      top: 5, textStyle: { fontSize: 10 },
    },
    grid: { left: 55, right: 55, top: 50, bottom: 30 },
    xAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 9,
        rotate: isMoneyness ? 0 : 30,
        formatter: (v: number) => isMoneyness ? v.toFixed(3) : v.toFixed(2),
      },
      axisPointer: { show: true },
      scale: true,
    },
    yAxis: [
      {
        type: 'value', name: 'IV%', position: 'left',
        axisLabel: { fontSize: 9, formatter: (v: number) => v.toFixed(1) },
        splitLine: { lineStyle: { type: 'dashed', color: '#eee' } },
        scale: true,
      },
      {
        type: 'value', name: '持仓量', position: 'right',
        axisLabel: { fontSize: 9, formatter: (v: number) => {
          if (Math.abs(v) >= 10000) return (v / 10000).toFixed(1) + '万';
          return v.toLocaleString();
        }},
        splitLine: { show: false },
        min: rightMin, max: rightMax,
      },
    ],
    series: [
      // ── Blended IV (today) ──
      {
        name: 'IV (今)', type: 'line',
        data: todayIvs.map((iv, i) => iv != null ? [xValues[i], iv] : [xValues[i], null]),
        lineStyle: { width: 2.5, color: '#7c3aed' },
        symbol: 'circle', symbolSize: 4,
        itemStyle: { color: '#7c3aed' },
        connectNulls: true, z: 10,
        markLine: vMarkLines.length > 0 ? { silent: false, symbol: 'none', data: vMarkLines } : undefined,
      },
      // ── Blended IV (yesterday) ──
      {
        name: 'IV (昨)', type: 'line',
        data: ydIvs.map((iv, i) => iv != null ? [xValues[i], iv] : [xValues[i], null]),
        lineStyle: { width: 1.5, type: 'dashed', color: '#bbb' },
        symbol: 'none', itemStyle: { color: '#bbb' },
        connectNulls: true, z: 9,
      },
      // ── Dummy legend entries for vertical markLines ──
      {
        name: currentLabel, type: 'line', data: [],
        lineStyle: { color: '#1a73e8', width: 2 },
        itemStyle: { color: '#1a73e8' },
      },
      {
        name: prevLabel, type: 'line', data: [],
        lineStyle: { color: '#999', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#999' },
      },
      // ── Put OI bars (light green, left) ──
      {
        name: '看跌持仓', type: 'bar', yAxisIndex: 1,
        data: putOiLightBars,
        itemStyle: { color: 'rgba(144,210,144,0.55)' },
        barWidth: barWidthPx, barGap: '-100%', z: 1,
      },
      // ── Call OI bars (light red, right) ──
      {
        name: '看涨持仓', type: 'bar', yAxisIndex: 1,
        data: callOiLightBars,
        itemStyle: { color: 'rgba(255,170,170,0.55)' },
        barWidth: barWidthPx, barGap: '-100%', z: 1,
      },
      // ── Put OI change (dark green, overlaps light green) ──
      {
        name: '看跌增量', type: 'bar', yAxisIndex: 1,
        data: putOiDarkBars,
        itemStyle: { color: 'rgba(20,120,40,0.85)' },
        barWidth: barWidthPx, barGap: '-100%', z: 2,
      },
      // ── Call OI change (dark red, overlaps light red) ──
      {
        name: '看涨增量', type: 'bar', yAxisIndex: 1,
        data: callOiDarkBars,
        itemStyle: { color: 'rgba(180,30,30,0.85)' },
        barWidth: barWidthPx, barGap: '-100%', z: 2,
      },
    ],
  });
}
