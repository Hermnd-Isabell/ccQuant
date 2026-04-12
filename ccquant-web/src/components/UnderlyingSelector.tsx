import { useState, useMemo } from 'react';
import type { UnderlyingConfig } from '../types';

interface Props {
  underlyings: string[];
  value: UnderlyingConfig[];
  onChange: (value: UnderlyingConfig[]) => void;
}

export function UnderlyingSelector({ underlyings, value, onChange }: Props) {
  const [searchTerm, setSearchTerm] = useState('');

  // 过滤未选择的标的
  const availableUnderlyings = useMemo(() => {
    const selected = new Set(value.map(v => v.symbol));
    return underlyings.filter(u => !selected.has(u));
  }, [underlyings, value]);

  // 搜索过滤
  const filteredUnderlyings = useMemo(() => {
    if (!searchTerm) return availableUnderlyings;
    return availableUnderlyings.filter(u =>
      u.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [availableUnderlyings, searchTerm]);

  const addUnderlying = (symbol: string) => {
    if (!symbol || value.find(u => u.symbol === symbol)) return;
    onChange([...value, { symbol, weight: 1, enabled: true }]);
    setSearchTerm('');
  };

  const removeUnderlying = (symbol: string) => {
    onChange(value.filter(u => u.symbol !== symbol));
  };

  const updateWeight = (symbol: string, weight: number) => {
    onChange(value.map(u => u.symbol === symbol ? { ...u, weight } : u));
  };

  const toggleEnabled = (symbol: string) => {
    onChange(value.map(u => u.symbol === symbol ? { ...u, enabled: !u.enabled } : u));
  };

  const totalWeight = value.filter(u => u.enabled).reduce((sum, u) => sum + u.weight, 0);

  return (
    <div className="underlying-selector-modal">
      {/* 搜索添加区 */}
      <div className="search-section">
        <input
          type="text"
          placeholder="搜索标的代码..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        {searchTerm && filteredUnderlyings.length > 0 && (
          <div className="search-results">
            {filteredUnderlyings.slice(0, 10).map(symbol => (
              <button
                key={symbol}
                className="search-result-item"
                onClick={() => addUnderlying(symbol)}
              >
                {symbol}
              </button>
            ))}
            {filteredUnderlyings.length > 10 && (
              <div className="search-more">还有 {filteredUnderlyings.length - 10} 个结果...</div>
            )}
          </div>
        )}
        {searchTerm && filteredUnderlyings.length === 0 && (
          <div className="search-empty">未找到匹配的标的</div>
        )}
      </div>

      {/* 已选标的列表 */}
      <div className="selected-section">
        <div className="selected-header">
          <span>已选标的 ({value.filter(u => u.enabled).length})</span>
          {totalWeight > 0 && (
            <span className="total-weight">总权重: {totalWeight.toFixed(2)}</span>
          )}
        </div>

        <div className="underlying-list">
          {value.length === 0 ? (
            <div className="underlying-empty">请在上方搜索并添加标的</div>
          ) : (
            value.map((item) => (
              <div
                key={item.symbol}
                className={`underlying-item ${!item.enabled ? 'disabled' : ''}`}
              >
                <label className="underlying-checkbox">
                  <input
                    type="checkbox"
                    checked={item.enabled}
                    onChange={() => toggleEnabled(item.symbol)}
                  />
                  <span className="underlying-symbol">{item.symbol}</span>
                </label>
                <div className="underlying-controls">
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    value={item.weight}
                    onChange={(e) => updateWeight(item.symbol, parseFloat(e.target.value) || 0)}
                    className="weight-input"
                    disabled={!item.enabled}
                  />
                  <button
                    onClick={() => removeUnderlying(item.symbol)}
                    className="btn-remove"
                    title="删除"
                  >
                    ×
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
