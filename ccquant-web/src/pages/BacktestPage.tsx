import { useEffect, useMemo, useState } from 'react';
import { runBacktest, runOptimization, getUnderlyings, getUnderlyingContracts } from '../api';
import { StrategyParamsForm, STRATEGY_DEFINITIONS, STRATEGY_CATEGORIES } from '../components/StrategyParamsForm';
import { StatisticsPanel } from '../components/StatisticsPanel';
import { BacktesterChart } from '../components/BacktesterChart';
import { TradeDialog, OrderDialog, DailyResultDialog } from '../components/BacktestDialogs';
import type { BacktestResult, OptimizationResult, UnderlyingInfo, ContractInfo } from '../types';

const STRATEGY_CONTRACT_COUNTS: Record<string, number> = {
  BuyCallStrategy: 1,
  StraddleStrategy: 2,
  IronCondorStrategy: 4,
  BullCallSpreadStrategy: 2,
  BearPutSpreadStrategy: 2,
  StrangleStrategy: 2,
  ButterflySpreadStrategy: 3,
  CalendarSpreadStrategy: 2,
  RatioSpreadStrategy: 2,
  SimpleBuyHoldStrategy: 1,
  DualThrustStrategy: 1,
  PairTradingStrategy: 2,
  AtrRsiStrategy: 1,
  BollChannelStrategy: 1,
  DoubleMaStrategy: 1,
  KingKeltnerStrategy: 1,
  MultiSignalStrategy: 1,
  MultiTimeframeStrategy: 1,
  TestStrategy: 1,
  TurtleSignalStrategy: 1,
  IvPredictStrategy: 0,
  IvPredictStrategyAEnhanced: 0,
};

const STRATEGY_CONTRACT_LABELS: Record<string, string[]> = {
  BuyCallStrategy: ['买入合约'],
  StraddleStrategy: ['买入Call', '买入Put'],
  IronCondorStrategy: ['卖出Call', '买入Call', '卖出Put', '买入Put'],
  BullCallSpreadStrategy: ['买入Call(低行权价)', '卖出Call(高行权价)'],
  BearPutSpreadStrategy: ['买入Put(高行权价)', '卖出Put(低行权价)'],
  StrangleStrategy: ['买入Call', '买入Put'],
  ButterflySpreadStrategy: ['买入Call(低)', '卖出Call(中)', '买入Call(高)'],
  CalendarSpreadStrategy: ['卖出近月', '买入远月'],
  RatioSpreadStrategy: ['买入Call(低)', '卖出Call(高)'],
  SimpleBuyHoldStrategy: ['持有合约'],
  DualThrustStrategy: ['交易合约'],
  PairTradingStrategy: ['合约 A', '合约 B'],
  AtrRsiStrategy: ['交易合约'],
  BollChannelStrategy: ['交易合约'],
  DoubleMaStrategy: ['交易合约'],
  KingKeltnerStrategy: ['交易合约'],
  MultiSignalStrategy: ['交易合约'],
  MultiTimeframeStrategy: ['交易合约'],
  TestStrategy: ['交易合约'],
  TurtleSignalStrategy: ['交易合约'],
  IvPredictStrategy: [],
  IvPredictStrategyAEnhanced: [],
};

const STRATEGY_CONTRACT_FILTERS: Record<string, (string | null)[]> = {
  BuyCallStrategy: ['C'],
  StraddleStrategy: ['C', 'P'],
  IronCondorStrategy: ['C', 'C', 'P', 'P'],
  BullCallSpreadStrategy: ['C', 'C'],
  BearPutSpreadStrategy: ['P', 'P'],
  StrangleStrategy: ['C', 'P'],
  ButterflySpreadStrategy: ['C', 'C', 'C'],
  CalendarSpreadStrategy: [null, null],
  RatioSpreadStrategy: ['C', 'C'],
  SimpleBuyHoldStrategy: [null],
  DualThrustStrategy: [null],
  PairTradingStrategy: [null, null],
  AtrRsiStrategy: [null],
  BollChannelStrategy: [null],
  DoubleMaStrategy: [null],
  KingKeltnerStrategy: [null],
  MultiSignalStrategy: [null],
  MultiTimeframeStrategy: [null],
  TestStrategy: [null],
  TurtleSignalStrategy: [null],
  IvPredictStrategy: [],
  IvPredictStrategyAEnhanced: [],
};

const DEFAULT_CATEGORY = 'single_single';
const getDefaultStrategy = (category: string) => STRATEGY_CATEGORIES[category].strategies[0];

export default function BacktestPage() {
  // Category & Strategy
  const [selectedCategory, setSelectedCategory] = useState(DEFAULT_CATEGORY);
  const [selectedStrategy, setSelectedStrategy] = useState(getDefaultStrategy(DEFAULT_CATEGORY));
  const [strategyParams, setStrategyParams] = useState<Record<string, any>>({});

  const neededCount = STRATEGY_CONTRACT_COUNTS[selectedStrategy] ?? 1;
  const contractLabels = STRATEGY_CONTRACT_LABELS[selectedStrategy] ?? [];
  const contractFilters = STRATEGY_CONTRACT_FILTERS[selectedStrategy] ?? [];

  // Underlying & contract selection (per-contract)
  const [underlyings, setUnderlyings] = useState<UnderlyingInfo[]>([]);
  const [selectedUnderlyings, setSelectedUnderlyings] = useState<string[]>([]);
  const [contractsList, setContractsList] = useState<ContractInfo[][]>([]);
  const [selectedContracts, setSelectedContracts] = useState<string[]>([]);
  const [contractLoadingMap, setContractLoadingMap] = useState<Record<number, boolean>>({});

  const [interval, setInterval_] = useState('d');

  const vtSymbolsInput = useMemo(() => {
    return selectedContracts
      .map((symbol, idx) => {
        if (!symbol) return '';
        const underlyingSymbol = selectedUnderlyings[idx];
        const exchange = underlyings.find((u) => u.symbol === underlyingSymbol)?.exchange || 'SSE';
        return `${symbol}.${exchange}`;
      })
      .filter((s) => s.length > 0)
      .join(', ');
  }, [selectedContracts, selectedUnderlyings, underlyings]);

  const vtSymbolsList = useMemo(() => {
    return vtSymbolsInput
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  }, [vtSymbolsInput]);

  // Load underlyings on mount
  useEffect(() => {
    getUnderlyings()
      .then((data) => {
        setUnderlyings(data);
        if (data.length > 0) {
          const defaultSymbol = data[0].symbol;
          setSelectedUnderlyings((prev) => {
            if (prev.length === 0) {
              return Array(neededCount).fill(defaultSymbol);
            }
            return prev;
          });
        }
      })
      .catch(() => {});
  }, []);

  // Load contracts when any selected underlying changes
  useEffect(() => {
    selectedUnderlyings.forEach((underlying, idx) => {
      if (!underlying) {
        setContractsList((prev) => {
          const next = [...prev];
          next[idx] = [];
          return next;
        });
        return;
      }
      setContractLoadingMap((prev) => ({ ...prev, [idx]: true }));
      getUnderlyingContracts(underlying)
        .then((data) => {
          setContractsList((prev) => {
            const next = [...prev];
            next[idx] = data;
            return next;
          });
        })
        .catch(() => {
          setContractsList((prev) => {
            const next = [...prev];
            next[idx] = [];
            return next;
          });
        })
        .finally(() => {
          setContractLoadingMap((prev) => ({ ...prev, [idx]: false }));
        });
    });
  }, [selectedUnderlyings.join(','), selectedStrategy]);

  // Reset selections when strategy changes
  useEffect(() => {
    const count = STRATEGY_CONTRACT_COUNTS[selectedStrategy] ?? 1;
    setSelectedContracts(Array(count).fill(''));
    const defaultSymbol = underlyings[0]?.symbol || '';
    setSelectedUnderlyings(Array(count).fill(defaultSymbol));
    setContractsList([]);
  }, [selectedStrategy, underlyings[0]?.symbol]);

  // Backtest params
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');
  const [initialCapital, setInitialCapital] = useState(1000000);
  const [rate, setRate] = useState(0.0003);
  const [slippage, setSlippage] = useState(0.0);
  const [size, setSize] = useState(10000);
  const [pricetick, setPricetick] = useState(0.0001);

  // State
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Dialogs
  const [showTrades, setShowTrades] = useState(false);
  const [showOrders, setShowOrders] = useState(false);
  const [showDailyResult, setShowDailyResult] = useState(false);
  const [showOptimizeDialog, setShowOptimizeDialog] = useState(false);
  const [optimizeParams, setOptimizeParams] = useState<Record<string, { start: number; end: number; step: number }>>({});
  const [optimizeMethod, setOptimizeMethod] = useState<'brute_force' | 'genetic'>('brute_force');
  const [optimizationResult, setOptimizationResult] = useState<OptimizationResult | null>(null);

  const strategiesAvailable = STRATEGY_CATEGORIES[selectedCategory].strategies;
  const currentStrategyDef = STRATEGY_DEFINITIONS[selectedStrategy] || { parameters: [] };

  // Run backtest
  const handleRunBacktest = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setOptimizationResult(null);
    try {
      const isSingle = vtSymbolsList.length === 1;
      const payload: any = {
        strategy_name: selectedStrategy,
        interval,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        rate, slippage, size, pricetick,
        params: strategyParams,
      };
      if (isSingle) {
        payload.vt_symbol = vtSymbolsList[0];
      } else {
        payload.vt_symbols = vtSymbolsList;
      }
      const response = await runBacktest(payload);
      if (response.success) {
        setResult({
          statistics: response.statistics || {},
          portfolioHistory: [],
          trades: response.trades || [],
          orders: response.orders || [],
          daily_df: response.daily_df || [],
          daily_results: response.daily_results || [],
          logs: response.logs || [],
          chart_json: response.chart_json,
        });
      } else {
        const msg = response.message || '回测失败';
        setError(response.traceback ? `${msg}\n\n${response.traceback}` : msg);
      }
    } catch (err: any) {
      setError(err.message || '回测异常');
    } finally {
      setLoading(false);
    }
  };

  // Run optimization
  const handleRunOptimization = async () => {
    if (Object.keys(optimizeParams).length === 0) {
      setError('请配置至少一个优化参数');
      return;
    }
    setLoading(true);
    setError(null);
    setOptimizationResult(null);
    setShowOptimizeDialog(false);
    try {
      const isSingle = vtSymbolsList.length === 1;
      const payload: any = {
        strategy_name: selectedStrategy,
        interval,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        rate, slippage, size, pricetick,
        params: strategyParams,
        params_range: optimizeParams,
        mode: optimizeMethod === 'genetic' ? 'ga' : 'bf',
      };
      if (isSingle) {
        payload.vt_symbol = vtSymbolsList[0];
      } else {
        payload.vt_symbols = vtSymbolsList;
      }
      const response = await runOptimization(payload);
      if (response.success) {
        setOptimizationResult(response);
      } else {
        setError(response.message || '优化失败');
      }
    } catch (err: any) {
      setError(err.message || '优化异常');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bt-page">
      {/* ===== LEFT COLUMN: Config ===== */}
      <div className="bt-left">
        <div className="bt-left-content">
          {/* Strategy select */}
          <div className="bt-section">
            <div className="bt-section-header">策略配置</div>
            <div className="bt-section-body">
              <div className="form-group">
                <label>策略分类</label>
                <select className="form-select" value={selectedCategory}
                  onChange={(e) => {
                    const cat = e.target.value;
                    setSelectedCategory(cat);
                    const firstStrategy = STRATEGY_CATEGORIES[cat].strategies[0];
                    setSelectedStrategy(firstStrategy);
                    setStrategyParams({});
                  }}>
                  {Object.entries(STRATEGY_CATEGORIES).map(([key, cat]) => (
                    <option key={key} value={key}>{cat.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>交易策略</label>
                <select className="form-select" value={selectedStrategy}
                  onChange={(e) => { setSelectedStrategy(e.target.value); setStrategyParams({}); }}>
                  {strategiesAvailable.map((name) => (
                    <option key={name} value={name}>{STRATEGY_DEFINITIONS[name]?.displayName || name}</option>
                  ))}
                </select>
              </div>

              {Array.from({ length: neededCount }).map((_, idx) => {
                const filterType = contractFilters[idx] ?? null;
                const available = (contractsList[idx] || []).filter((c) => filterType ? c.type === filterType : true);
                const isLoading = contractLoadingMap[idx];
                return (
                  <div key={idx} style={{ marginBottom: 10, padding: 10, background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderLeft: '3px solid var(--primary)', borderRadius: 'var(--radius-sm)' }}>
                    <div className="form-group" style={{ marginBottom: 8 }}>
                      <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>{contractLabels[idx] || `合约 ${idx + 1}`} — 标的</label>
                      <select className="form-select"
                        value={selectedUnderlyings[idx] || ''}
                        onChange={(e) => {
                          const next = [...selectedUnderlyings];
                          next[idx] = e.target.value;
                          setSelectedUnderlyings(next);
                          const nextContracts = [...selectedContracts];
                          nextContracts[idx] = '';
                          setSelectedContracts(nextContracts);
                        }}>
                        {underlyings.map((u) => (
                          <option key={u.symbol} value={u.symbol}>{u.name} ({u.symbol})</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>合约</label>
                      <select className="form-select"
                        value={selectedContracts[idx] || ''}
                        disabled={isLoading || available.length === 0}
                        onChange={(e) => {
                          const next = [...selectedContracts];
                          next[idx] = e.target.value;
                          setSelectedContracts(next);
                        }}>
                        <option value="">{isLoading ? '加载中...' : available.length ? '请选择合约' : '无可用合约'}</option>
                        {available.map((c) => (
                          <option key={c.symbol} value={c.symbol}>
                            {c.symbol} {c.type === 'C' ? 'Call' : c.type === 'P' ? 'Put' : ''} 行权价 {c.strike} 到期 {c.expiry}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                );
              })}

              <div className="form-group">
                <label>本地代码（自动生成）</label>
                <input type="text" className="form-input" value={vtSymbolsInput} readOnly />
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>
                  {(() => {
                    const actual = vtSymbolsList.length;
                    if (actual === neededCount) return `✅ ${selectedStrategy} 需要 ${neededCount} 个合约，已选齐`;
                    if (actual < neededCount) return `⚠️ ${selectedStrategy} 需要 ${neededCount} 个合约，当前仅 ${actual} 个`;
                    return `✅ 当前 ${actual} 个合约`;
                  })()}
                </div>
              </div>
              <div className="form-group">
                <label>K线周期</label>
                <select className="form-select" value={interval} onChange={(e) => setInterval_(e.target.value)}>
                  <option value="1m">1分钟</option>
                  <option value="1h">1小时</option>
                  <option value="d">日线</option>
                </select>
              </div>
            </div>
          </div>

          {/* Strategy params */}
          {currentStrategyDef.parameters.length > 0 && (
            <div className="bt-section">
              <div className="bt-section-header">策略参数</div>
              <div className="bt-section-body">
                <StrategyParamsForm parameters={currentStrategyDef.parameters} values={strategyParams} onChange={setStrategyParams} />
              </div>
            </div>
          )}

          {/* Backtest params */}
          <div className="bt-section">
            <div className="bt-section-header">回测参数</div>
            <div className="bt-section-body">
              <div className="form-group">
                <label>开始日期</label>
                <input type="date" className="form-input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label>结束日期</label>
                <input type="date" className="form-input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label>手续费率</label>
                <input type="number" className="form-input" value={rate} onChange={(e) => setRate(Number(e.target.value))} step={0.0001} min={0} />
              </div>
              <div className="form-group">
                <label>交易滑点</label>
                <input type="number" className="form-input" value={slippage} onChange={(e) => setSlippage(Number(e.target.value))} step={0.0001} min={0} />
              </div>
              <div className="form-group">
                <label>合约乘数</label>
                <input type="number" className="form-input" value={size} onChange={(e) => setSize(Number(e.target.value))} step={100} min={1} />
              </div>
              <div className="form-group">
                <label>价格跳动</label>
                <input type="number" className="form-input" value={pricetick} onChange={(e) => setPricetick(Number(e.target.value))} step={0.0001} min={0} />
              </div>
              <div className="form-group">
                <label>回测资金</label>
                <input type="number" className="form-input" value={initialCapital} onChange={(e) => setInitialCapital(Number(e.target.value))} step={10000} min={0} />
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div style={{ padding: 10, backgroundColor: 'rgba(234,67,53,0.1)', color: '#ea4335', borderRadius: 6, fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', maxHeight: 150, overflowY: 'auto' }}>
              {error}
            </div>
          )}
        </div>

        {/* Buttons */}
        <button className="bt-run-btn" disabled={loading} onClick={handleRunBacktest}>
          {loading ? <><span className="spinner sm" /> 运行中...</> : '开始回测'}
        </button>
        <div className="bt-btn-grid">
          <button disabled={!result} onClick={() => setShowTrades(true)}>成交记录</button>
          <button disabled={!result} onClick={() => setShowOrders(true)}>委托记录</button>
          <button disabled={!result} onClick={() => setShowDailyResult(true)}>每日盈亏</button>
          <button disabled={loading} onClick={() => setShowOptimizeDialog(true)}>参数优化</button>
        </div>
      </div>

      {/* ===== MIDDLE COLUMN: Statistics + Log ===== */}
      <div className="bt-middle">
        <div className="bt-middle-stats">
          <div className="bt-section" style={{ background: 'transparent', boxShadow: 'none' }}>
            <div className="bt-section-header" style={{ background: 'var(--bg-card)' }}>统计指标</div>
            <div className="bt-section-body" style={{ padding: 0, background: 'transparent' }}>
              <StatisticsPanel statistics={result?.statistics || {}} />
            </div>
          </div>
        </div>

        {/* Optimization Result */}
        {optimizationResult && optimizationResult.results && optimizationResult.results.length > 0 && (
          <div className="bt-section" style={{ marginTop: 12, background: 'transparent', boxShadow: 'none' }}>
            <div className="bt-section-header" style={{ background: 'var(--bg-card)' }}>参数优化结果</div>
            <div className="bt-section-body" style={{ padding: 0, background: 'transparent', overflowX: 'auto' }}>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-card)' }}>
                    <th style={{ padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid var(--border-color)' }}>排名</th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid var(--border-color)' }}>参数</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid var(--border-color)' }}>目标值</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid var(--border-color)' }}>总收益</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid var(--border-color)' }}>夏普</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid var(--border-color)' }}>最大回撤</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid var(--border-color)' }}>交易次数</th>
                  </tr>
                </thead>
                <tbody>
                  {optimizationResult.results.slice(0, 20).map((r, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '6px 8px' }}>{i + 1}</td>
                      <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 11, whiteSpace: 'nowrap' }}>
                        {JSON.stringify(r.params).slice(0, 80)}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600 }}>
                        {typeof r.target_value === 'number' ? r.target_value.toFixed(4) : r.target_value}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                        {((r.statistics?.total_return ?? r.statistics?.totalReturn ?? 0)).toFixed(2)}%
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                        {(r.statistics?.sharpe_ratio ?? r.statistics?.sharpeRatio ?? 0).toFixed(2)}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', color: '#ea4335' }}>
                        {(r.statistics?.max_drawdown_pct ?? r.statistics?.maxDrawdownPct ?? 0).toFixed(2)}%
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                        {r.statistics?.total_trades ?? r.statistics?.totalTrades ?? 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {optimizationResult.results.length > 20 && (
                <div style={{ padding: '8px', textAlign: 'center', fontSize: 11, color: 'var(--text-tertiary)' }}>
                  共 {optimizationResult.results.length} 组结果，展示前 20 组
                </div>
              )}
            </div>
          </div>
        )}

        <div className="bt-middle-log">
          <div className="bt-section-header">日志</div>
          <div className="bt-log-area">
            {(result?.logs || []).map((log, i) => {
              const m = log.match(/^(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+(.*)$/);
              if (m) {
                return (
                  <div key={i}>
                    <span className="bt-log-time">{m[1]}</span>
                    <span>{m[2]}</span>
                  </div>
                );
              }
              return <div key={i}>{log}</div>;
            })}
            {!result && <div style={{ color: 'var(--text-tertiary)' }}>运行回测后显示日志...</div>}
          </div>
        </div>
      </div>

      {/* ===== RIGHT COLUMN: Chart ===== */}
      <div className="bt-right">
        <div className="bt-section" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="bt-section-header">回测结果图表</div>
          <div className="bt-right-chart">
            <BacktesterChart dailyDf={result?.daily_df || []} />
          </div>
        </div>
      </div>

      {/* Dialogs */}
      {showTrades && result && <TradeDialog trades={result.trades} onClose={() => setShowTrades(false)} />}
      {showOrders && result && <OrderDialog orders={result.orders} onClose={() => setShowOrders(false)} />}
      {showDailyResult && result && <DailyResultDialog dailyResults={result.daily_results} onClose={() => setShowDailyResult(false)} />}
      {showOptimizeDialog && (
        <OptimizeDialog
          strategyDef={currentStrategyDef}
          optimizeParams={optimizeParams}
          optimizeMethod={optimizeMethod}
          onParamsChange={setOptimizeParams}
          onMethodChange={setOptimizeMethod}
          onConfirm={handleRunOptimization}
          onCancel={() => setShowOptimizeDialog(false)}
          loading={loading}
        />
      )}
    </div>
  );
}

// Optimize Dialog
function OptimizeDialog({
  strategyDef, optimizeParams, optimizeMethod,
  onParamsChange, onMethodChange, onConfirm, onCancel, loading,
}: {
  strategyDef: any;
  optimizeParams: Record<string, any>;
  optimizeMethod: 'brute_force' | 'genetic';
  onParamsChange: (p: Record<string, any>) => void;
  onMethodChange: (m: 'brute_force' | 'genetic') => void;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [tempParams, setTempParams] = useState(optimizeParams);

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: 'white', borderRadius: 8, padding: 24, minWidth: 480, maxHeight: '80vh', overflowY: 'auto' }}>
        <h3 style={{ marginTop: 0 }}>参数优化设置</h3>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 8 }}>优化方法</label>
          <select value={optimizeMethod} onChange={(e) => onMethodChange(e.target.value as any)} className="form-select">
            <option value="brute_force">暴力搜索</option>
            <option value="genetic">遗传算法</option>
          </select>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 12, fontWeight: 600 }}>选择优化参数</label>
          {strategyDef.parameters.filter((p: any) => p.type === 'number').map((p: any) => (
            <div key={p.name} style={{ marginBottom: 12, padding: 10, backgroundColor: '#f5f5f5', borderRadius: 6 }}>
              <label>
                <input type="checkbox" checked={p.name in tempParams}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setTempParams({ ...tempParams, [p.name]: { start: p.min || 0, end: p.max || 1, step: p.step || 0.1 } });
                    } else {
                      const { [p.name]: _, ...rest } = tempParams;
                      setTempParams(rest);
                    }
                  }} />
                <span style={{ marginLeft: 8 }}>{p.displayName}</span>
              </label>
              {p.name in tempParams && (
                <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                  <div>
                    <label style={{ fontSize: 11 }}>开始</label>
                    <input type="number" value={tempParams[p.name].start} className="form-input" style={{ fontSize: 12 }}
                      onChange={(e) => setTempParams({ ...tempParams, [p.name]: { ...tempParams[p.name], start: Number(e.target.value) } })} />
                  </div>
                  <div>
                    <label style={{ fontSize: 11 }}>结束</label>
                    <input type="number" value={tempParams[p.name].end} className="form-input" style={{ fontSize: 12 }}
                      onChange={(e) => setTempParams({ ...tempParams, [p.name]: { ...tempParams[p.name], end: Number(e.target.value) } })} />
                  </div>
                  <div>
                    <label style={{ fontSize: 11 }}>步长</label>
                    <input type="number" value={tempParams[p.name].step} className="form-input" style={{ fontSize: 12 }} step="0.01" min="0.01"
                      onChange={(e) => setTempParams({ ...tempParams, [p.name]: { ...tempParams[p.name], step: Number(e.target.value) } })} />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={onCancel} disabled={loading}>取消</button>
          <button className="bt-run-btn" style={{ margin: 0, width: 'auto', padding: '0 20px' }}
            onClick={() => { onParamsChange(tempParams); onConfirm(); }}
            disabled={loading || Object.keys(tempParams).length === 0}>
            {loading ? '优化中...' : '开始优化'}
          </button>
        </div>
      </div>
    </div>
  );
}
