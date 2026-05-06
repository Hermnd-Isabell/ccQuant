/**
 * Backtest dialog components: Trade, Order, DailyResult tables.
 */
import { useState } from 'react';
import type { TradeRecord, OrderRecord, DailyResultRow } from '../types';

/* ---- shared overlay style ---- */
const overlayStyle: React.CSSProperties = {
  position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
  backgroundColor: 'rgba(0,0,0,0.45)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 1000,
};
const dialogStyle: React.CSSProperties = {
  backgroundColor: 'white', borderRadius: 8, padding: 20,
  width: '80vw', maxWidth: 900, maxHeight: '80vh',
  display: 'flex', flexDirection: 'column',
};
const thStyle: React.CSSProperties = {
  padding: '8px 10px', textAlign: 'left', fontWeight: 600,
  color: '#64748b', fontSize: 12, whiteSpace: 'nowrap',
  borderBottom: '2px solid #e2e8f0', position: 'sticky', top: 0,
  backgroundColor: '#f8fafc',
};
const tdStyle: React.CSSProperties = {
  padding: '6px 10px', fontSize: 12, borderBottom: '1px solid #f1f5f9',
};

/* ---- TradeDialog ---- */
export function TradeDialog({ trades, onClose }: { trades: TradeRecord[]; onClose: () => void }) {
  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={dialogStyle} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>成交记录 ({trades.length})</span>
          <button onClick={onClose} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>✕</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={thStyle}>成交时间</th><th style={thStyle}>合约</th>
              <th style={thStyle}>方向</th><th style={thStyle}>开平</th>
              <th style={{...thStyle, textAlign:'right'}}>价格</th>
              <th style={{...thStyle, textAlign:'right'}}>数量</th>
            </tr></thead>
            <tbody>
              {trades.map((t, i) => (
                <tr key={i}>
                  <td style={tdStyle}>{t.datetime?.slice(0, 19)}</td>
                  <td style={{...tdStyle, fontFamily:'monospace'}}>{t.vtSymbol || (t as any).vt_symbol}</td>
                  <td style={tdStyle}>
                    {(() => {
                      const isLong = t.direction === 'LONG' || t.direction === 'Long' || t.direction === '多';
                      const isShort = t.direction === 'SHORT' || t.direction === 'Short' || t.direction === '空';
                      return (
                        <span style={{ color: isLong ? '#ef4444' : (isShort ? '#22c55e' : '#94a3b8'), fontWeight: 600 }}>
                          {isLong ? '多' : (isShort ? '空' : t.direction)}
                        </span>
                      );
                    })()}
                  </td>
                  <td style={tdStyle}>{(t.offset === 'OPEN' || t.offset === 'Open' || t.offset === '开') ? '开仓' : '平仓'}</td>
                  <td style={{...tdStyle, textAlign:'right', fontFamily:'monospace'}}>{(t.price ?? 0).toFixed(4)}</td>
                  <td style={{...tdStyle, textAlign:'right'}}>{t.volume}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
/* ---- OrderDialog ---- */
export function OrderDialog({ orders, onClose }: { orders: OrderRecord[]; onClose: () => void }) {
  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={dialogStyle} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>委托记录 ({orders.length})</span>
          <button onClick={onClose} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>✕</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={thStyle}>委托时间</th><th style={thStyle}>合约</th>
              <th style={thStyle}>方向</th><th style={thStyle}>开平</th>
              <th style={{...thStyle, textAlign:'right'}}>价格</th>
              <th style={{...thStyle, textAlign:'right'}}>数量</th>
              <th style={{...thStyle, textAlign:'right'}}>成交</th>
              <th style={thStyle}>状态</th>
            </tr></thead>
            <tbody>
              {orders.map((o, i) => (
                <tr key={i}>
                  <td style={tdStyle}>{o.datetime?.slice(0, 19)}</td>
                  <td style={{...tdStyle, fontFamily:'monospace'}}>{o.vt_symbol}</td>
                  <td style={tdStyle}>
                    <span style={{ color: o.direction === 'LONG' || o.direction === '多' ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                      {o.direction === 'LONG' || o.direction === '多' ? '多' : '空'}
                    </span>
                  </td>
                  <td style={tdStyle}>{o.offset === 'OPEN' || o.offset === '开' ? '开仓' : '平仓'}</td>
                  <td style={{...tdStyle, textAlign:'right', fontFamily:'monospace'}}>{(o.price ?? 0).toFixed(4)}</td>
                  <td style={{...tdStyle, textAlign:'right'}}>{o.volume}</td>
                  <td style={{...tdStyle, textAlign:'right'}}>{o.traded}</td>
                  <td style={tdStyle}>{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ---- DailyResultDialog ---- */
export function DailyResultDialog({ dailyResults, onClose }: { dailyResults: DailyResultRow[]; onClose: () => void }) {
  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={dialogStyle} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>每日盈亏 ({dailyResults.length})</span>
          <button onClick={onClose} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>✕</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={thStyle}>日期</th>
              <th style={{...thStyle, textAlign:'right'}}>成交笔数</th>
              <th style={{...thStyle, textAlign:'right'}}>成交金额</th>
              <th style={{...thStyle, textAlign:'right'}}>手续费</th>
              <th style={{...thStyle, textAlign:'right'}}>滑点</th>
              <th style={{...thStyle, textAlign:'right'}}>交易盈亏</th>
              <th style={{...thStyle, textAlign:'right'}}>持仓盈亏</th>
              <th style={{...thStyle, textAlign:'right'}}>总盈亏</th>
              <th style={{...thStyle, textAlign:'right'}}>净盈亏</th>
            </tr></thead>
            <tbody>
              {dailyResults.map((d, i) => (
                <tr key={i}>
                  <td style={tdStyle}>{d.date}</td>
                  <td style={{...tdStyle, textAlign:'right'}}>{d.trade_count}</td>
                  <td style={{...tdStyle, textAlign:'right'}}>{(d.turnover ?? 0).toFixed(2)}</td>
                  <td style={{...tdStyle, textAlign:'right'}}>{(d.commission ?? 0).toFixed(2)}</td>
                  <td style={{...tdStyle, textAlign:'right'}}>{(d.slippage ?? 0).toFixed(2)}</td>
                  <td style={{...tdStyle, textAlign:'right', color: (d.trading_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444'}}>
                    {(d.trading_pnl ?? 0).toFixed(2)}
                  </td>
                  <td style={{...tdStyle, textAlign:'right', color: (d.holding_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444'}}>
                    {(d.holding_pnl ?? 0).toFixed(2)}
                  </td>
                  <td style={{...tdStyle, textAlign:'right', color: (d.total_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444'}}>
                    {(d.total_pnl ?? 0).toFixed(2)}
                  </td>
                  <td style={{...tdStyle, textAlign:'right', fontWeight: 600, color: (d.net_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444'}}>
                    {(d.net_pnl ?? 0).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}