import { useState, useEffect } from 'react';
import { getStrategies, getStrategyCode, openInIDE } from '../api';
import type { StrategyFile } from '../types';

export default function StrategyEditorPage() {
  const [strategies, setStrategies] = useState<StrategyFile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [codeLoading, setCodeLoading] = useState(false);

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const list = await getStrategies();
      setStrategies(list);
      if (list.length > 0 && !selected) {
        setSelected(list[0].filename);
      }
    } catch {
      console.error('加载策略列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!selected) return;
    setCodeLoading(true);
    getStrategyCode(selected)
      .then(setCode)
      .catch(() => setCode('// 无法加载策略代码'))
      .finally(() => setCodeLoading(false));
  }, [selected]);

  const handleOpenIDE = async () => {
    if (!selected) return;
    try {
      await openInIDE(selected);
    } catch {
      alert('无法打开外部编辑器，请确认后端服务正在运行');
    }
  };

  const selectedStrategy = strategies.find((s) => s.filename === selected);

  return (
    <div className="strategy-page">
      {/* Left: Strategy List */}
      <div className="strategy-list-panel">
        <div className="strategy-list-header">
          <h3>策略列表</h3>
          <span className="tag tag-primary">{strategies.length}</span>
        </div>
        <div className="strategy-list">
          {loading ? (
            <div className="loading-container">
              <div className="spinner" />
            </div>
          ) : strategies.length === 0 ? (
            <div className="empty-state" style={{ minHeight: 200 }}>
              <p>暂无策略文件</p>
              <p style={{ fontSize: 11 }}>策略文件存放在后端 strategies/ 目录</p>
            </div>
          ) : (
            strategies.map((s) => (
              <div
                key={s.filename}
                className={`strategy-item ${selected === s.filename ? 'active' : ''}`}
                onClick={() => setSelected(s.filename)}
              >
                <div className="strategy-item-name">{s.name}</div>
                <div className="strategy-item-desc">{s.description}</div>
                <div className="strategy-item-meta">
                  <span className={`tag ${s.category === 'ml' ? 'tag-warning' : s.category === 'option' ? 'tag-primary' : 'tag-success'}`}>
                    {s.category === 'ml' ? 'ML' : s.category === 'option' ? '期权' : '自定义'}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right: Code Viewer */}
      <div className="strategy-detail-panel">
        {selectedStrategy ? (
          <>
            <div className="strategy-detail-header">
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 600 }}>{selectedStrategy.name}</h3>
                <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>
                  {selectedStrategy.filename} · 修改于 {selectedStrategy.modifiedAt}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" onClick={handleOpenIDE}>
                  在 VSCode 中打开
                </button>
              </div>
            </div>
            <div className="strategy-code-area">
              {codeLoading ? (
                <div className="loading-container" style={{ minHeight: 400 }}>
                  <div className="spinner" />
                </div>
              ) : (
                <pre>{code}</pre>
              )}
            </div>
          </>
        ) : (
          <div className="empty-state" style={{ height: '100%' }}>
            <div className="empty-state-icon">📝</div>
            <h3>选择一个策略查看代码</h3>
            <p>从左侧列表选择策略，或创建新策略</p>
          </div>
        )}
      </div>
    </div>
  );
}
