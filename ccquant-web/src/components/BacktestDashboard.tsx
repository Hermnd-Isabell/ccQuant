import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { BacktestResult } from '../types';
import { PayoffChart } from './PayoffChart';
import { GreeksChart } from './GreeksChart';

interface Props {
  result: BacktestResult;
}

function StatCard({ label, value, prefix = '', suffix = '', type = 'neutral' }: {
  label: string;
  value: string | number | undefined | null;
  prefix?: string;
  suffix?: string;
  type?: 'positive' | 'negative' | 'neutral';
}) {
  // 确保值是有效字符串
  const displayValue = value === undefined || value === null || Number.isNaN(value)
    ? '--'
    : String(value);

  return (
    <div className="stat-card-compact">
      <div className={`stat-value-compact ${type}`}>
        {prefix}{displayValue}{suffix}
      </div>
      <div className="stat-label-compact">{label}</div>
    </div>
  );
}

export function BacktestDashboard({ result }: Props) {
  // 防御性编程：确保 result 不为 null/undefined
  if (!result) {
    return (
      <div className="dashboard">
        <div className="dashboard-empty">
          <p>暂无回测结果数据</p>
        </div>
      </div>
    );
  }

  const { statistics, portfolioHistory, trades, payoff } = result;
  const mainChartRef = useRef<HTMLDivElement>(null);
  const mainChartInstance = useRef<echarts.ECharts | null>(null);

  // 主收益曲线
  useEffect(() => {
    if (!mainChartRef.current) return;
    if (!mainChartInstance.current) {
      mainChartInstance.current = echarts.init(mainChartRef.current);
    }

    const history = (portfolioHistory || []).filter((h: any) => h && (h.datetime || h.date));
    const dates = history.map((h: any) => h.datetime?.slice(0, 10));
    const values = history.map((h: any) => {
      const cash = h.cash ?? 0;
      const marketValue = h.totalMarketValue ?? h.total_market_value ?? 0;
      return cash + marketValue;
    });
    const initialValue = values[0] || 1;
    const returns = values.map((v: number) => ((v - initialValue) / initialValue) * 100);

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0];
          return `${p.name}<br/>累计收益: ${Number(p.value).toFixed(2)}%`;
        },
      },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#5f6368', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#5f6368',
          fontSize: 11,
          formatter: (v: number) => `${v.toFixed(1)}%`,
        },
        splitLine: { lineStyle: { color: '#e8eaed', type: 'dashed' } },
      },
      series: [
        {
          name: '累计收益',
          type: 'line',
          data: returns,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 2, color: returns[returns.length - 1] >= 0 ? '#34a853' : '#ea4335' },
          areaStyle: {
            color: new (echarts as any).graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: returns[returns.length - 1] >= 0 ? 'rgba(52, 168, 83, 0.15)' : 'rgba(234, 67, 53, 0.15)' },
              { offset: 1, color: 'transparent' },
            ]),
          },
        },
      ],
    };
    mainChartInstance.current.setOption(option);

    const handleResize = () => mainChartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [portfolioHistory]);

  // 防御性数据访问：支持 camelCase 和 snake_case
  const stats = statistics || {};

  // 兼容两种命名格式
  const totalReturn = (stats.totalReturn ?? stats.total_return ?? 0) as number;
  const annualReturn = (stats.annualReturn ?? stats.annual_return ?? 0) as number;
  const maxDrawdownPct = (stats.maxDrawdownPct ?? stats.max_drawdown_pct ?? stats.maxDrawdown ?? stats.max_drawdown ?? 0) as number;
  const sharpeRatio = (stats.sharpeRatio ?? stats.sharpe_ratio ?? 0) as number;
  const totalTrades = (stats.totalTrades ?? stats.total_trades ?? 0) as number;
  const winRate = (stats.winRate ?? stats.win_rate ?? 0) as number;

  const isPositiveReturn = totalReturn >= 0;
  const isPositiveAnnual = annualReturn >= 0;

  return (
    <div className="dashboard">
      {/* 核心指标区 - 紧凑布局 */}
      <div className="dashboard-hero">
        <div className="hero-main">
          <div className="hero-title">回测结果</div>
          <div className={`hero-return ${isPositiveReturn ? 'positive' : 'negative'}`}>
            {(totalReturn * 100).toFixed(2)}%
          </div>
          <div className="hero-subtitle">总收益率</div>
        </div>
        <div className="hero-stats">
          <StatCard
            label="年化收益"
            value={(annualReturn * 100).toFixed(2)}
            suffix="%"
            type={isPositiveAnnual ? 'positive' : 'negative'}
          />
          <StatCard
            label="最大回撤"
            value={(maxDrawdownPct * 100).toFixed(2)}
            suffix="%"
            type="negative"
          />
          <StatCard
            label="夏普比率"
            value={sharpeRatio.toFixed(2)}
            type={sharpeRatio >= 0 ? 'positive' : 'negative'}
          />
          <StatCard label="交易次数" value={totalTrades} />
          <StatCard
            label="胜率"
            value={winRate ? (winRate * 100).toFixed(1) : '0.0'}
            suffix="%"
          />
        </div>
      </div>

      {/* 图表区 - 双列布局 */}
      <div className="dashboard-charts">
        <div className="chart-panel main-chart">
          <div className="chart-header">
            <h3>收益曲线</h3>
          </div>
          <div ref={mainChartRef} className="chart-body" />
        </div>

        {payoff && (
          <div className="chart-panel">
            <div className="chart-header">
              <h3>到期盈亏图</h3>
            </div>
            <div className="chart-body">
              <PayoffChart data={payoff} compact />
            </div>
          </div>
        )}

        <div className="chart-panel">
          <div className="chart-header">
            <h3>希腊值变化</h3>
          </div>
          <div className="chart-body">
            <GreeksChart history={portfolioHistory} compact />
          </div>
        </div>
      </div>

      {/* 交易记录 - 可折叠 */}
      {trades && trades.length > 0 && (
        <div className="dashboard-trades">
          <details open>
            <summary>
              <span>交易记录</span>
              <span className="trades-count">{trades.length} 笔</span>
            </summary>
            <div className="trades-table-wrap">
              <table className="trades-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>合约</th>
                    <th>方向</th>
                    <th>开平</th>
                    <th>价格</th>
                    <th>数量</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.slice(0, 50).map((t: any, idx: number) => (
                    <tr key={idx}>
                      <td>{t.datetime?.slice(0, 10)}</td>
                      <td className="symbol">{t.vtSymbol ?? t.vt_symbol}</td>
                      <td>
                        <span className={`tag ${(t.direction === 'LONG' || t.direction === '多') ? 'long' : 'short'}`}>
                          {(t.direction === 'LONG' || t.direction === '多') ? '买入' : '卖出'}
                        </span>
                      </td>
                      <td>{(t.offset === 'OPEN' || t.offset === '开') ? '开仓' : '平仓'}</td>
                      <td>¥{(t.price ?? 0).toFixed(4)}</td>
                      <td>{t.volume ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {trades.length > 50 && (
                <div className="trades-more">还有 {trades.length - 50} 笔交易...</div>
              )}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
