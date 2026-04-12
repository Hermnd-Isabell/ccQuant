import { useState } from 'react';

export default function BacktestPage() {
  const [loading] = useState(false);

  return (
    <div className="bt-page">
      {/* Sidebar */}
      <div className="bt-sidebar">
        <div className="bt-sidebar-content">
          <div className="bt-section">
            <div className="bt-section-header">策略配置</div>
            <div className="bt-section-body">
              <div className="form-group">
                <label>选择策略</label>
                <select className="form-select">
                  <option>BuyCallStrategy</option>
                  <option>StraddleStrategy</option>
                  <option>IronCondorStrategy</option>
                </select>
              </div>
            </div>
          </div>

          <div className="bt-section">
            <div className="bt-section-header">标的池</div>
            <div className="bt-section-body">
              <div style={{ padding: 12, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
                点击下方按钮构建标的池
              </div>
              <button className="btn btn-secondary" style={{ width: '100%' }}>
                构建标的池
              </button>
            </div>
          </div>

          <div className="bt-section">
            <div className="bt-section-header">回测参数</div>
            <div className="bt-section-body">
              <div className="form-group">
                <label>时间区间</label>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input type="date" className="form-input" defaultValue="2024-01-01" />
                  <span style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>至</span>
                  <input type="date" className="form-input" defaultValue="2024-12-31" />
                </div>
              </div>
              <div className="form-group">
                <label>初始资金</label>
                <input type="number" className="form-input" defaultValue={1000000} />
              </div>
            </div>
          </div>
        </div>

        <button className="bt-run-btn" disabled={loading}>
          {loading ? (
            <>
              <span className="spinner sm" />
              运行中...
            </>
          ) : (
            '运行回测'
          )}
        </button>
      </div>

      {/* Content */}
      <div className="bt-content">
        <div className="empty-state" style={{ height: '100%' }}>
          <div className="empty-state-icon">📊</div>
          <h3>开始期权策略回测</h3>
          <p>配置左侧参数后点击「运行回测」查看结果</p>
        </div>
      </div>
    </div>
  );
}
