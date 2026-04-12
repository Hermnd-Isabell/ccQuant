import { useState, useMemo, useEffect } from 'react';
import * as echarts from 'echarts';

interface Leg {
  id: string;
  symbol: string;
  optionType: 'C' | 'P';
  strike: number;
  expiry: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
}

interface Props {
  underlying: string;
  spotPrice: number;
}

const PRESET_STRATEGIES = [
  {
    name: '单腿买入',
    legs: [{ optionType: 'C', side: 'buy', quantity: 1 }],
  },
  {
    name: '牛市价差',
    legs: [
      { optionType: 'C', side: 'buy', quantity: 1 },
      { optionType: 'C', side: 'sell', quantity: 1 },
    ],
  },
  {
    name: '熊市价差',
    legs: [
      { optionType: 'P', side: 'buy', quantity: 1 },
      { optionType: 'P', side: 'sell', quantity: 1 },
    ],
  },
  {
    name: '跨式组合',
    legs: [
      { optionType: 'C', side: 'buy', quantity: 1 },
      { optionType: 'P', side: 'buy', quantity: 1 },
    ],
  },
  {
    name: '宽跨式',
    legs: [
      { optionType: 'C', side: 'buy', quantity: 1 },
      { optionType: 'P', side: 'buy', quantity: 1 },
    ],
  },
  {
    name: '铁鹰式',
    legs: [
      { optionType: 'C', side: 'sell', quantity: 1 },
      { optionType: 'C', side: 'buy', quantity: 1 },
      { optionType: 'P', side: 'sell', quantity: 1 },
      { optionType: 'P', side: 'buy', quantity: 1 },
    ],
  },
  {
    name: '蝶式价差',
    legs: [
      { optionType: 'C', side: 'buy', quantity: 1 },
      { optionType: 'C', side: 'sell', quantity: 2 },
      { optionType: 'C', side: 'buy', quantity: 1 },
    ],
  },
  {
    name: '比率价差',
    legs: [
      { optionType: 'C', side: 'buy', quantity: 1 },
      { optionType: 'C', side: 'sell', quantity: 2 },
    ],
  },
];

// 计算期权理论价格（简化版 Black-Scholes）
function calculateOptionPrice(
  S: number,
  K: number,
  T: number,
  r: number,
  sigma: number,
  optionType: 'C' | 'P'
): { price: number; delta: number; gamma: number; theta: number; vega: number } {
  const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T));
  const d2 = d1 - sigma * Math.sqrt(T);

  const nd1 = normalCDF(d1);
  const nd2 = normalCDF(d2);
  const nPrimeD1 = normalPDF(d1);

  let price: number;
  let delta: number;

  if (optionType === 'C') {
    price = S * nd1 - K * Math.exp(-r * T) * nd2;
    delta = nd1;
  } else {
    price = K * Math.exp(-r * T) * (1 - nd2) - S * (1 - nd1);
    delta = nd1 - 1;
  }

  const gamma = nPrimeD1 / (S * sigma * Math.sqrt(T));
  const theta = -(S * nPrimeD1 * sigma) / (2 * Math.sqrt(T));
  const vega = S * nPrimeD1 * Math.sqrt(T) / 100;

  return { price, delta, gamma, theta, vega };
}

function normalCDF(x: number): number {
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x) / Math.sqrt(2);

  const t = 1 / (1 + p * x);
  const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);

  return 0.5 * (1 + sign * y);
}

function normalPDF(x: number): number {
  return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
}

export function StrategyBuilder({ underlying, spotPrice }: Props) {
  const [legs, setLegs] = useState<Leg[]>([]);
  const [selectedExpiry] = useState('2024-12-27');
  const daysToExpiry = 30;
  const ivAdjustment = 0;

  const expiries = ['2024-12-20', '2024-12-27', '2025-01-17', '2025-02-21', '2025-03-21'];

  // 添加腿
  const addLeg = () => {
    const newLeg: Leg = {
      id: Date.now().toString(),
      symbol: `${underlying}_${selectedExpiry}_C_${Math.round(spotPrice)}`,
      optionType: 'C',
      strike: Math.round(spotPrice / 50) * 50,
      expiry: selectedExpiry,
      side: 'buy',
      quantity: 1,
      price: 0,
      iv: 0.2,
      delta: 0,
      gamma: 0,
      theta: 0,
      vega: 0,
    };
    setLegs([...legs, newLeg]);
  };

  // 移除腿
  const removeLeg = (id: string) => {
    setLegs(legs.filter(l => l.id !== id));
  };

  // 更新腿
  const updateLeg = (id: string, updates: Partial<Leg>) => {
    setLegs(legs.map(l => (l.id === id ? { ...l, ...updates } : l)));
  };

  // 加载预设策略
  const loadPreset = (preset: typeof PRESET_STRATEGIES[0]) => {
    const baseStrike = Math.round(spotPrice / 50) * 50;
    const strikes = [baseStrike - 100, baseStrike - 50, baseStrike, baseStrike + 50, baseStrike + 100];

    const newLegs: Leg[] = preset.legs.map((leg, index) => {
      const strike = strikes[index % strikes.length];
      const greeks = calculateOptionPrice(spotPrice, strike, daysToExpiry / 365, 0.03, 0.2, leg.optionType as 'C' | 'P');

      return {
        id: `${Date.now()}_${index}`,
        symbol: `${underlying}_${selectedExpiry}_${leg.optionType}_${strike}`,
        optionType: leg.optionType as 'C' | 'P',
        strike,
        expiry: selectedExpiry,
        side: leg.side as 'buy' | 'sell',
        quantity: leg.quantity,
        price: greeks.price,
        iv: 0.2 + ivAdjustment / 100,
        delta: greeks.delta,
        gamma: greeks.gamma,
        theta: greeks.theta,
        vega: greeks.vega,
      };
    });

    setLegs(newLegs);
  };

  // 计算组合希腊字母
  const portfolioGreeks = useMemo(() => {
    return legs.reduce(
      (acc, leg) => {
        const multiplier = leg.side === 'buy' ? leg.quantity : -leg.quantity;
        acc.delta += leg.delta * multiplier;
        acc.gamma += leg.gamma * multiplier;
        acc.theta += leg.theta * multiplier;
        acc.vega += leg.vega * multiplier;
        acc.premium += leg.price * multiplier;
        return acc;
      },
      { delta: 0, gamma: 0, theta: 0, vega: 0, premium: 0 }
    );
  }, [legs]);

  // 计算盈亏图数据
  const payoffData = useMemo(() => {
    if (legs.length === 0) return { prices: [], payoffs: [] };

    const minPrice = spotPrice * 0.8;
    const maxPrice = spotPrice * 1.2;
    const step = (maxPrice - minPrice) / 50;
    const prices: number[] = [];
    const payoffs: number[] = [];

    for (let p = minPrice; p <= maxPrice; p += step) {
      prices.push(p);

      let payoff = 0;
      legs.forEach(leg => {
        const legPayoff = calculatePayoffAtExpiry(p, leg);
        const multiplier = leg.side === 'buy' ? leg.quantity : -leg.quantity;
        payoff += legPayoff * multiplier;
      });

      payoffs.push(payoff);
    }

    return { prices, payoffs };
  }, [legs, spotPrice]);

  // 计算到期时单腿盈亏
  const calculatePayoffAtExpiry = (underlyingPrice: number, leg: Leg): number => {
    if (leg.optionType === 'C') {
      return Math.max(0, underlyingPrice - leg.strike) - leg.price;
    } else {
      return Math.max(0, leg.strike - underlyingPrice) - leg.price;
    }
  };

  // 计算盈亏平衡点
  const breakEvenPoints = useMemo(() => {
    if (payoffData.prices.length === 0) return [];

    const points: number[] = [];
    for (let i = 1; i < payoffData.payoffs.length; i++) {
      if (payoffData.payoffs[i - 1] * payoffData.payoffs[i] < 0) {
        // 线性插值找零点
        const x1 = payoffData.prices[i - 1];
        const x2 = payoffData.prices[i];
        const y1 = payoffData.payoffs[i - 1];
        const y2 = payoffData.payoffs[i];
        const x = x1 - y1 * (x2 - x1) / (y2 - y1);
        points.push(x);
      }
    }
    return points;
  }, [payoffData]);

  // 绘制盈亏图
  useEffect(() => {
    try {
      if (payoffData.prices.length === 0) return;

      const chartDom = document.getElementById('strategy-payoff-chart');
      if (!chartDom) return;

      // 清理旧图表
      const existingChart = echarts.getInstanceByDom(chartDom);
      if (existingChart) {
        existingChart.dispose();
      }

      const chart = echarts.init(chartDom);

      const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0];
          return `标的价格: ${p.name}<br/>盈亏: ¥${p.value.toFixed(2)}`;
        },
      },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: payoffData.prices.map(p => p.toFixed(0)),
        name: '标的价格',
        nameTextStyle: { color: '#5f6368' },
        axisLine: { lineStyle: { color: '#dadce0' } },
        axisLabel: { color: '#5f6368', interval: 9 },
      },
      yAxis: {
        type: 'value',
        name: '盈亏',
        nameTextStyle: { color: '#5f6368' },
        axisLine: { show: false },
        axisLabel: {
          color: '#5f6368',
          formatter: (v: number) => `¥${v.toFixed(0)}`,
        },
        splitLine: { lineStyle: { color: '#f1f3f4' } },
      },
      series: [
        {
          name: '盈亏',
          type: 'line',
          data: payoffData.payoffs,
          smooth: false,
          lineStyle: {
            width: 3,
            color: portfolioGreeks.premium >= 0 ? '#ea4335' : '#34a853',
          },
          areaStyle: {
            color: new (echarts as any).graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: portfolioGreeks.premium >= 0 ? 'rgba(234, 67, 53, 0.2)' : 'rgba(52, 168, 83, 0.2)' },
              { offset: 1, color: portfolioGreeks.premium >= 0 ? 'rgba(234, 67, 53, 0.02)' : 'rgba(52, 168, 83, 0.02)' },
            ]),
          },
          markLine: {
            silent: true,
            lineStyle: { color: '#ea4335', type: 'dashed', width: 1 },
            data: [{ yAxis: 0 }],
          },
          markPoint: {
            data: [
              { type: 'max', name: '最大盈利', label: { formatter: 'Max: {c}' } },
              { type: 'min', name: '最大亏损', label: { formatter: 'Min: {c}' } },
            ],
          },
        },
      ],
    };

      chart.setOption(option);

      const handleResize = () => chart.resize();
      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        chart.dispose();
      };
    } catch (error) {
      console.error('盈亏图渲染错误:', error);
    }
  }, [payoffData, portfolioGreeks.premium]);

  return (
    <div className="strategy-builder">
      {/* 预设策略快速选择 */}
      <div className="preset-strategies">
        <label>快速选择策略</label>
        <div className="preset-buttons">
          {PRESET_STRATEGIES.map(preset => (
            <button key={preset.name} className="preset-btn" onClick={() => loadPreset(preset)}>
              {preset.name}
            </button>
          ))}
        </div>
      </div>

      <div className="builder-main">
        {/* 左侧：腿配置 */}
        <div className="legs-panel">
          <div className="panel-header">
            <h4>策略腿配置</h4>
            <button className="add-leg-btn" onClick={addLeg}>
              + 添加腿
            </button>
          </div>

          <div className="legs-list">
            {legs.length === 0 && (
              <div className="empty-legs">
                点击上方按钮添加期权腿，或选择预设策略
              </div>
            )}

            {legs.map((leg, index) => (
              <div key={leg.id} className={`leg-card ${leg.side}`}>
                <div className="leg-header">
                  <span className="leg-number">腿 {index + 1}</span>
                  <button className="remove-leg" onClick={() => removeLeg(leg.id)}>
                    ×
                  </button>
                </div>

                <div className="leg-row">
                  <div className="leg-field">
                    <label>类型</label>
                    <select
                      value={leg.optionType}
                      onChange={e => updateLeg(leg.id, { optionType: e.target.value as 'C' | 'P' })}
                    >
                      <option value="C">看涨 Call</option>
                      <option value="P">看跌 Put</option>
                    </select>
                  </div>

                  <div className="leg-field">
                    <label>方向</label>
                    <select
                      value={leg.side}
                      onChange={e => updateLeg(leg.id, { side: e.target.value as 'buy' | 'sell' })}
                    >
                      <option value="buy">买入</option>
                      <option value="sell">卖出</option>
                    </select>
                  </div>
                </div>

                <div className="leg-row">
                  <div className="leg-field">
                    <label>行权价</label>
                    <input
                      type="number"
                      value={leg.strike}
                      onChange={e => updateLeg(leg.id, { strike: Number(e.target.value) })}
                      step={50}
                    />
                  </div>

                  <div className="leg-field">
                    <label>数量</label>
                    <input
                      type="number"
                      value={leg.quantity}
                      onChange={e => updateLeg(leg.id, { quantity: Number(e.target.value) })}
                      min={1}
                    />
                  </div>
                </div>

                <div className="leg-row">
                  <div className="leg-field">
                    <label>IV %</label>
                    <input
                      type="number"
                      value={(leg.iv * 100).toFixed(1)}
                      onChange={e =>
                        updateLeg(leg.id, { iv: Number(e.target.value) / 100 })
                      }
                      step={0.1}
                    />
                  </div>

                  <div className="leg-field">
                    <label>到期日</label>
                    <select
                      value={leg.expiry}
                      onChange={e => updateLeg(leg.id, { expiry: e.target.value })}
                    >
                      {expiries.map(exp => (
                        <option key={exp} value={exp}>
                          {exp}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="leg-greeks">
                  <span>Δ {leg.delta.toFixed(3)}</span>
                  <span>Γ {leg.gamma.toFixed(4)}</span>
                  <span>Θ {leg.theta.toFixed(2)}</span>
                  <span>V {leg.vega.toFixed(3)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 右侧：盈亏图和希腊字母 */}
        <div className="analysis-panel">
          {/* 盈亏图 */}
          <div className="payoff-chart-section">
            <h4>到期盈亏分析</h4>
            {legs.length > 0 ? (
              <div id="strategy-payoff-chart" style={{ width: '100%', height: '300px' }} />
            ) : (
              <div className="empty-chart">添加策略腿后显示盈亏图</div>
            )}
          </div>

          {/* 组合希腊字母 */}
          {legs.length > 0 && (
            <div className="portfolio-greeks">
              <h4>组合希腊字母</h4>
              <div className="greeks-grid">
                <div className="greek-item">
                  <label>净权利金</label>
                  <span className={`greek-value ${portfolioGreeks.premium >= 0 ? 'positive' : 'negative'}`}>
                    {portfolioGreeks.premium >= 0 ? '+' : ''}¥{portfolioGreeks.premium.toFixed(2)}
                  </span>
                </div>
                <div className="greek-item">
                  <label>Delta</label>
                  <span className="greek-value">{portfolioGreeks.delta.toFixed(3)}</span>
                </div>
                <div className="greek-item">
                  <label>Gamma</label>
                  <span className="greek-value">{portfolioGreeks.gamma.toFixed(4)}</span>
                </div>
                <div className="greek-item">
                  <label>Theta (日)</label>
                  <span className="greek-value">{portfolioGreeks.theta.toFixed(2)}</span>
                </div>
                <div className="greek-item">
                  <label>Vega</label>
                  <span className="greek-value">{portfolioGreeks.vega.toFixed(3)}</span>
                </div>
              </div>

              {/* 盈亏平衡点 */}
              {breakEvenPoints.length > 0 && (
                <div className="break-even">
                  <label>盈亏平衡点</label>
                  <div className="be-points">
                    {breakEvenPoints.map((p, i) => (
                      <span key={i} className="be-point">
                        {p.toFixed(2)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 最大盈亏 */}
              <div className="max-pnl">
                <div className="max-item">
                  <label>最大盈利</label>
                  <span className="max-value positive">
                    +¥{Math.max(...payoffData.payoffs).toFixed(2)}
                  </span>
                </div>
                <div className="max-item">
                  <label>最大亏损</label>
                  <span className="max-value negative">
                    ¥{Math.min(...payoffData.payoffs).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
