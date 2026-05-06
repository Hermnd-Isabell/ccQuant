/**
 * ccQuant-style statistics panel — KPI cards grid.
 */

interface Props {
  statistics: Record<string, any>;
}

const fmtNum = (v: any, digits = 2) => {
  if (v === undefined || v === null || v === '') return '--';
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

const fmtPct = (v: any, digits = 2) => {
  if (v === undefined || v === null || v === '') return '--';
  return `${Number(v).toFixed(digits)}%`;
};

const fmtInt = (v: any) => {
  if (v === undefined || v === null || v === '') return '--';
  return String(Math.round(Number(v)));
};

export function StatisticsPanel({ statistics }: Props) {
  if (!statistics || Object.keys(statistics).length === 0) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
        暂无统计数据
      </div>
    );
  }

  const totalReturn = Number(statistics.total_return || 0);
  const annualReturn = Number(statistics.annual_return || 0);
  const maxDdpercent = Number(statistics.max_ddpercent || 0);
  const sharpe = Number(statistics.sharpe_ratio || 0);

  return (
    <div className="bt-stats-grid">
      {/* Hero card: total return */}
      <div className="bt-stat-card large">
        <div>
          <div className="bt-stat-label">总收益率</div>
          <div className={`bt-stat-value ${totalReturn >= 0 ? 'positive' : 'negative'}`}>
            {fmtPct(statistics.total_return)}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="bt-stat-label">年化收益</div>
          <div className={`bt-stat-value ${annualReturn >= 0 ? 'positive' : 'negative'}`} style={{ fontSize: 18 }}>
            {fmtPct(statistics.annual_return)}
          </div>
        </div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">结束资金</div>
        <div className="bt-stat-value">{fmtNum(statistics.end_balance)}</div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">总盈亏</div>
        <div className={`bt-stat-value ${Number(statistics.total_net_pnl || 0) >= 0 ? 'positive' : 'negative'}`}>
          {fmtNum(statistics.total_net_pnl)}
        </div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">Sharpe Ratio</div>
        <div className="bt-stat-value" style={{ color: sharpe >= 1 ? '#1a73e8' : 'var(--text-primary)' }}>
          {fmtNum(statistics.sharpe_ratio)}
        </div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">最大回撤</div>
        <div className="bt-stat-value negative">{fmtPct(statistics.max_ddpercent)}</div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">收益回撤比</div>
        <div className="bt-stat-value">{fmtNum(statistics.return_drawdown_ratio)}</div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">总成交笔数</div>
        <div className="bt-stat-value">{fmtInt(statistics.total_trade_count)}</div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">盈利 / 亏损交易日</div>
        <div className="bt-stat-value" style={{ fontSize: 14, marginTop: 2 }}>
          <span style={{ color: '#ef5350' }}>{fmtInt(statistics.profit_days)}</span>
          <span style={{ color: 'var(--text-tertiary)', margin: '0 4px' }}>/</span>
          <span style={{ color: '#26a69a' }}>{fmtInt(statistics.loss_days)}</span>
        </div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">起始资金</div>
        <div className="bt-stat-value">{fmtNum(statistics.capital)}</div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">总手续费</div>
        <div className="bt-stat-value">{fmtNum(statistics.total_commission)}</div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">总滑点</div>
        <div className="bt-stat-value">{fmtNum(statistics.total_slippage)}</div>
      </div>

      <div className="bt-stat-card">
        <div className="bt-stat-label">总成交金额</div>
        <div className="bt-stat-value">{fmtNum(statistics.total_turnover)}</div>
      </div>

      <div className="bt-stat-card" style={{ gridColumn: 'span 2' }}>
        <div className="bt-stat-label">交易周期</div>
        <div className="bt-stat-value" style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-secondary)' }}>
          {statistics.start_date || '--'} ~ {statistics.end_date || '--'} · {fmtInt(statistics.total_days)} 个交易日
        </div>
      </div>
    </div>
  );
}
