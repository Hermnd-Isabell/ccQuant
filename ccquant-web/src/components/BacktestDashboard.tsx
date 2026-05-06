import { useEffect, useRef, useState } from 'react';
import type { BacktestResult } from '../types';

interface Props {
  result: BacktestResult;
}

function StatCard({
  label,
  value,
  suffix = '',
  type = 'neutral',
}: {
  label: string;
  value: string | number | undefined | null;
  suffix?: string;
  type?: 'positive' | 'negative' | 'neutral';
}) {
  const displayValue = value === undefined || value === null || Number.isNaN(value) ? '--' : String(value);

  const colors: Record<string, { bg: string; text: string; border: string }> = {
    positive: { bg: '#f0fdf4', text: '#22c55e', border: '#dcfce7' },
    negative: { bg: '#fef2f2', text: '#ef4444', border: '#fee2e2' },
    neutral: { bg: '#f8f9fa', text: '#64748b', border: '#e2e8f0' },
  };

  const color = colors[type];

  return (
    <div
      style={{
        backgroundColor: color.bg,
        border: `1px solid ${color.border}`,
        borderRadius: 8,
        padding: 16,
        textAlign: 'center',
        minWidth: 120,
      }}
    >
      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8, fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 'bold', color: color.text }}>
        {displayValue}
        {suffix}
      </div>
    </div>
  );
}

export function BacktestDashboard({ result }: Props) {
  if (!result) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>
        暂无回测结果数据
      </div>
    );
  }

  const { statistics = {} } = result;
  const stats = statistics || {};

  // 兼容 snake_case 和 camelCase
  const totalReturn = ((stats.total_return ?? stats.totalReturn ?? 0) * 100) as number;
  const annualReturn = ((stats.annual_return ?? stats.annualReturn ?? 0) * 100) as number;
  const maxDrawdownPct = ((stats.max_drawdown_pct ?? stats.maxDrawdownPct ?? stats.max_drawdown ?? 0) * 100) as number;
  const sharpeRatio = (stats.sharpe_ratio ?? stats.sharpeRatio ?? 0) as number;
  const totalTrades = (stats.total_trades ?? stats.totalTrades ?? 0) as number;
  const winRate = ((stats.win_rate ?? stats.winRate ?? 0) * 100) as number;
  const totalNetPnl = (stats.total_net_pnl ?? stats.totalNetPnl ?? 0) as number;
  const maxDrawdown = (stats.max_drawdown ?? stats.maxDrawdown ?? 0) as number;
  const startDate = (stats.start_date ?? stats.startDate ?? '-') as string;
  const endDate = (stats.end_date ?? stats.endDate ?? '-') as string;
  const totalDays = (stats.total_days ?? stats.totalDays ?? 0) as number;

  const isPositiveReturn = totalReturn >= 0;
  const isPositiveAnnual = annualReturn >= 0;

  const [tradesSorted, setTradesSorted] = useState(result.trades || []);
  const [sortKey, setSortKey] = useState<'datetime' | 'vtSymbol' | 'direction'>('datetime');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const handleSort = (key: 'datetime' | 'vtSymbol' | 'direction') => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };

  useEffect(() => {
    let sorted = [...(result.trades || [])];
    sorted.sort((a: any, b: any) => {
      let aVal = a[sortKey];
      let bVal = b[sortKey];
      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
    setTradesSorted(sorted);
  }, [sortKey, sortOrder, result.trades]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* 顶部：关键指标 */}
      <div style={{ padding: 24, borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8f9fa' }}>
        <div style={{ marginBottom: 20, display: 'grid', gridTemplateColumns: '1fr auto', gap: 20, alignItems: 'start' }}>
          <div>
            <div style={{ fontSize: 14, color: '#64748b', marginBottom: 8 }}>策略收益</div>
            <div style={{ fontSize: 36, fontWeight: 'bold', color: isPositiveReturn ? '#22c55e' : '#ef4444' }}>
              {totalReturn.toFixed(2)}%
            </div>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 8 }}>
              {String(startDate).slice(0, 10)} 至 {String(endDate).slice(0, 10)} ({totalDays} 天)
            </div>
          </div>
          <div style={{ textAlign: 'right', fontSize: 12, color: '#64748b' }}>
            <div>总盈亏: <span style={{ color: totalNetPnl >= 0 ? '#22c55e' : '#ef4444', fontWeight: 'bold' }}>¥{totalNetPnl.toFixed(2)}</span></div>
            <div style={{ marginTop: 4 }}>交易次数: <span style={{ fontWeight: 'bold' }}>{totalTrades}</span></div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12 }}>
          <StatCard label="年化收益" value={annualReturn.toFixed(2)} suffix="%" type={isPositiveAnnual ? 'positive' : 'negative'} />
          <StatCard label="最大回撤" value={maxDrawdownPct.toFixed(2)} suffix="%" type="negative" />
          <StatCard label="夏普比率" value={sharpeRatio.toFixed(2)} type={sharpeRatio >= 0 ? 'positive' : 'negative'} />
          <StatCard label="胜率" value={winRate.toFixed(1)} suffix="%" type="neutral" />
        </div>
      </div>

      {/* 中部：图表区域 */}
      {result && (
        <div style={{ flex: 1, padding: 24, overflowY: 'auto', borderBottom: '1px solid #e2e8f0' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: 14, fontWeight: 'bold', color: '#1e293b' }}>回测结果图表</h3>
          <div style={{ width: '100%', height: 450, backgroundColor: 'white', borderRadius: 8, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
            <ChartViewer chartJson={result} />
          </div>
        </div>
      )}

      {/* 下部：交易记录表 */}
      <div style={{ flex: 1, padding: 24, overflowY: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 'bold', color: '#1e293b' }}>交易记录 ({tradesSorted.length} 笔)</h3>
        </div>

        {tradesSorted.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 24, color: '#64748b', fontSize: 12 }}>暂无交易记录</div>
        ) : (
          <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid #e2e8f0' }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 12,
                backgroundColor: 'white',
              }}
            >
              <thead>
                <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #e2e8f0' }}>
                  <th
                    style={{
                      padding: 12,
                      textAlign: 'left',
                      fontWeight: 'bold',
                      color: '#64748b',
                      cursor: 'pointer',
                      userSelect: 'none',
                    }}
                    onClick={() => handleSort('datetime')}
                  >
                    交易日期 {sortKey === 'datetime' && (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    style={{
                      padding: 12,
                      textAlign: 'left',
                      fontWeight: 'bold',
                      color: '#64748b',
                      cursor: 'pointer',
                      userSelect: 'none',
                    }}
                    onClick={() => handleSort('vtSymbol')}
                  >
                    合约 {sortKey === 'vtSymbol' && (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold', color: '#64748b' }}>方向</th>
                  <th style={{ padding: 12, textAlign: 'right', fontWeight: 'bold', color: '#64748b' }}>价格</th>
                  <th style={{ padding: 12, textAlign: 'right', fontWeight: 'bold', color: '#64748b' }}>数量</th>
                  <th style={{ padding: 12, textAlign: 'right', fontWeight: 'bold', color: '#64748b' }}>开平</th>
                </tr>
              </thead>
              <tbody>
                {tradesSorted.slice(0, 50).map((trade: any, idx: number) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: 12, color: '#1e293b' }}>{trade.datetime?.slice(0, 10) || '-'}</td>
                    <td style={{ padding: 12, color: '#1e293b', fontFamily: 'monospace', fontWeight: 500 }}>
                      {trade.vtSymbol || trade.vt_symbol || '-'}
                    </td>
                    <td style={{ padding: 12 }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '4px 8px',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 'bold',
                          backgroundColor: trade.direction === 'LONG' || trade.direction === '多' ? '#dcfce7' : '#fee2e2',
                          color: trade.direction === 'LONG' || trade.direction === '多' ? '#22c55e' : '#ef4444',
                        }}
                      >
                        {trade.direction === 'LONG' || trade.direction === '多' ? '买' : '卖'}
                      </span>
                    </td>
                    <td style={{ padding: 12, textAlign: 'right', color: '#1e293b' }}>¥{(trade.price ?? 0).toFixed(4)}</td>
                    <td style={{ padding: 12, textAlign: 'right', color: '#1e293b' }}>{trade.volume ?? 0}</td>
                    <td style={{ padding: 12, textAlign: 'right', color: '#64748b', fontSize: 11 }}>
                      {trade.offset === 'OPEN' || trade.offset === '开' ? '开仓' : '平仓'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {tradesSorted.length > 50 && (
              <div style={{ padding: 12, textAlign: 'center', color: '#64748b', fontSize: 12 }}>
                还有 {tradesSorted.length - 50} 笔交易未显示
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ChartViewer({ chartJson }: { chartJson: BacktestResult }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !chartJson) return;

    try {
      // 使用 Plotly.js 渲染
      if (typeof window !== 'undefined' && (window as any).Plotly) {
        const Plotly = (window as any).Plotly;

        // 解析后端返回的 Plotly JSON
        if (chartJson && typeof chartJson === 'object') {
          // 简单的演示图表：资产净值曲线
          const portfolioHistory = (chartJson as any).portfolioHistory || [];

          if (portfolioHistory.length > 0) {
            const dates = portfolioHistory.map((p: any) => p.datetime?.slice(0, 10));
            const balances = portfolioHistory.map((p: any) => (p.cash ?? 0) + (p.totalMarketValue ?? 0));

            const trace = {
              x: dates,
              y: balances,
              type: 'scatter',
              mode: 'lines',
              name: '资产净值',
              line: { color: '#3b82f6', width: 2 },
              fill: 'tozeroy',
              fillcolor: 'rgba(59, 130, 246, 0.1)',
            };

            const layout = {
              title: '',
              xaxis: { title: '日期' },
              yaxis: { title: '资产净值' },
              hovermode: 'x unified',
              plot_bgcolor: '#ffffff',
              paper_bgcolor: '#ffffff',
              font: { size: 12, color: '#64748b' },
              margin: { l: 60, r: 20, t: 20, b: 40 },
            };

            Plotly.newPlot(ref.current, [trace], layout, { responsive: true, displayModeBar: false });
          }
        }
      } else {
        // Fallback: 使用简单的Canvas绘制
        console.warn('Plotly.js not loaded, using fallback chart');
      }
    } catch (error) {
      console.error('Chart render error:', error);
    }
  }, [chartJson]);

  return <div ref={ref} style={{ width: '100%', height: '100%' }} />;
}
