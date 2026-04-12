import { useState, useEffect, useMemo } from 'react';
import * as echarts from 'echarts';

interface OptionContract {
  symbol: string;
  strike: number;
  expiry: string;
  optionType: 'C' | 'P';
  price?: number;
  iv?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  volume?: number;
  openInterest?: number;
}

interface Props {
  underlying: string;
  onSelect?: (contracts: OptionContract[]) => void;
  selectedContracts?: OptionContract[];
}

// 模拟期权链数据生成
function generateMockChain(underlying: string, spotPrice: number): OptionContract[] {
  const contracts: OptionContract[] = [];
  const expiries = ['2024-12-20', '2024-12-27', '2025-01-17', '2025-02-21'];
  const strikes: number[] = [];

  // 生成行权价
  const baseStrike = Math.round(spotPrice / 50) * 50;
  for (let i = -5; i <= 5; i++) {
    strikes.push(baseStrike + i * 50);
  }

  expiries.forEach(expiry => {
    strikes.forEach(strike => {
      // Call
      const callPrice = Math.max(0.01, spotPrice - strike + Math.random() * 10);
      const callIV = 0.15 + Math.random() * 0.25;
      contracts.push({
        symbol: `${underlying}_${expiry}_C_${strike}`,
        strike,
        expiry,
        optionType: 'C',
        price: callPrice,
        iv: callIV,
        delta: Math.min(0.95, Math.max(0.05, (spotPrice / strike) * 0.5 + Math.random() * 0.2)),
        gamma: Math.random() * 0.05,
        theta: -Math.random() * 2,
        vega: Math.random() * 0.5,
        volume: Math.floor(Math.random() * 1000),
        openInterest: Math.floor(Math.random() * 5000),
      });

      // Put
      const putPrice = Math.max(0.01, strike - spotPrice + Math.random() * 10);
      const putIV = 0.15 + Math.random() * 0.25;
      contracts.push({
        symbol: `${underlying}_${expiry}_P_${strike}`,
        strike,
        expiry,
        optionType: 'P',
        price: putPrice,
        iv: putIV,
        delta: -Math.min(0.95, Math.max(0.05, (strike / spotPrice) * 0.5 + Math.random() * 0.2)),
        gamma: Math.random() * 0.05,
        theta: -Math.random() * 2,
        vega: Math.random() * 0.5,
        volume: Math.floor(Math.random() * 1000),
        openInterest: Math.floor(Math.random() * 5000),
      });
    });
  });

  return contracts;
}

export function OptionChainViewer({ underlying, onSelect, selectedContracts = [] }: Props) {
  const [contracts, setContracts] = useState<OptionContract[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState<string>('');
  const [spotPrice, setSpotPrice] = useState(2650);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'chain' | 'iv'>('chain');

  // 加载期权链数据
  useEffect(() => {
    setLoading(true);
    // 模拟API调用
    setTimeout(() => {
      const data = generateMockChain(underlying, spotPrice);
      setContracts(data);
      const expiries = [...new Set(data.map(c => c.expiry))].sort();
      if (expiries.length > 0 && !selectedExpiry) {
        setSelectedExpiry(expiries[0]);
      }
      setLoading(false);
    }, 500);
  }, [underlying, spotPrice]);

  // 获取到期日列表
  const expiries = useMemo(() => {
    return [...new Set(contracts.map(c => c.expiry))].sort();
  }, [contracts]);

  // 筛选当前到期日的合约
  const currentContracts = useMemo(() => {
    return contracts.filter(c => c.expiry === selectedExpiry);
  }, [contracts, selectedExpiry]);

  // 按行权价分组
  const chainData = useMemo(() => {
    const strikes = [...new Set(currentContracts.map(c => c.strike))].sort((a, b) => a - b);
    return strikes.map(strike => {
      const call = currentContracts.find(c => c.strike === strike && c.optionType === 'C');
      const put = currentContracts.find(c => c.strike === strike && c.optionType === 'P');
      return { strike, call, put };
    });
  }, [currentContracts]);

  // 计算IV偏度数据
  const ivSkewData = useMemo(() => {
    const strikes = [...new Set(currentContracts.map(c => c.strike))].sort((a, b) => a - b);
    return strikes.map(strike => {
      const call = currentContracts.find(c => c.strike === strike && c.optionType === 'C');
      const put = currentContracts.find(c => c.strike === strike && c.optionType === 'P');
      return {
        strike,
        callIV: call?.iv || 0,
        putIV: put?.iv || 0,
        avgIV: ((call?.iv || 0) + (put?.iv || 0)) / 2,
      };
    });
  }, [currentContracts]);

  // 是否选中
  const isSelected = (contract: OptionContract) => {
    return selectedContracts.some(c => c.symbol === contract.symbol);
  };

  // 切换选择
  const toggleSelection = (contract: OptionContract) => {
    if (!onSelect) return;
    const exists = isSelected(contract);
    if (exists) {
      onSelect(selectedContracts.filter(c => c.symbol !== contract.symbol));
    } else {
      onSelect([...selectedContracts, contract]);
    }
  };

  // 渲染IV偏度图
  useEffect(() => {
    if (viewMode !== 'iv' || ivSkewData.length === 0) return;

    const chartDom = document.getElementById('iv-skew-chart');
    if (!chartDom) return;

    const chart = echarts.init(chartDom);
    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#dadce0',
        textStyle: { color: '#3c4043' },
      },
      legend: {
        data: ['Call IV', 'Put IV'],
        bottom: 0,
        textStyle: { color: '#5f6368' },
      },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ivSkewData.map(d => d.strike.toString()),
        name: '行权价',
        nameTextStyle: { color: '#5f6368' },
        axisLine: { lineStyle: { color: '#dadce0' } },
        axisLabel: { color: '#5f6368' },
      },
      yAxis: {
        type: 'value',
        name: '隐含波动率',
        nameTextStyle: { color: '#5f6368' },
        axisLine: { show: false },
        axisLabel: { color: '#5f6368', formatter: (v: number) => `${(v * 100).toFixed(1)}%` },
        splitLine: { lineStyle: { color: '#f1f3f4' } },
      },
      series: [
        {
          name: 'Call IV',
          type: 'line',
          data: ivSkewData.map(d => d.callIV),
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2, color: '#34a853' },
          itemStyle: { color: '#34a853' },
        },
        {
          name: 'Put IV',
          type: 'line',
          data: ivSkewData.map(d => d.putIV),
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2, color: '#ea4335' },
          itemStyle: { color: '#ea4335' },
        },
      ],
    };
    chart.setOption(option);

    return () => chart.dispose();
  }, [ivSkewData, viewMode]);

  if (loading) {
    return (
      <div className="option-chain-loading">
        <div className="spinner" />
        <span>加载期权链数据...</span>
      </div>
    );
  }

  return (
    <div className="option-chain-viewer">
      {/* 工具栏 */}
      <div className="chain-toolbar">
        <div className="spot-price">
          <label>标的价格</label>
          <input
            type="number"
            value={spotPrice}
            onChange={(e) => setSpotPrice(Number(e.target.value))}
            step={0.01}
          />
        </div>

        <div className="expiry-selector">
          <label>到期日</label>
          <select value={selectedExpiry} onChange={(e) => setSelectedExpiry(e.target.value)}>
            {expiries.map(exp => (
              <option key={exp} value={exp}>{exp}</option>
            ))}
          </select>
        </div>

        <div className="view-toggle">
          <button
            className={viewMode === 'chain' ? 'active' : ''}
            onClick={() => setViewMode('chain')}
          >
            期权链
          </button>
          <button
            className={viewMode === 'iv' ? 'active' : ''}
            onClick={() => setViewMode('iv')}
          >
            IV偏度
          </button>
        </div>
      </div>

      {/* 选中合约摘要 */}
      {selectedContracts.length > 0 && (
        <div className="selected-summary">
          <h4>已选合约 ({selectedContracts.length})</h4>
          <div className="selected-tags">
            {selectedContracts.map(c => (
              <span key={c.symbol} className={`selected-tag ${c.optionType === 'C' ? 'call' : 'put'}`}>
                {c.optionType === 'C' ? 'C' : 'P'}{c.strike}
                <button onClick={() => toggleSelection(c)}>×</button>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 内容区 */}
      {viewMode === 'chain' ? (
        <div className="chain-table-container">
          <table className="option-chain-table">
            <thead>
              <tr>
                <th colSpan={6} className="call-header">看涨期权 Call</th>
                <th rowSpan={2} className="strike-col">行权价</th>
                <th colSpan={6} className="put-header">看跌期权 Put</th>
              </tr>
              <tr>
                <th>价格</th>
                <th>IV</th>
                <th>Delta</th>
                <th>Gamma</th>
                <th>Volume</th>
                <th>OI</th>
                <th>价格</th>
                <th>IV</th>
                <th>Delta</th>
                <th>Gamma</th>
                <th>Volume</th>
                <th>OI</th>
              </tr>
            </thead>
            <tbody>
              {chainData.map(({ strike, call, put }) => {
                const isAtm = Math.abs(strike - spotPrice) < 25;
                return (
                  <tr key={strike} className={isAtm ? 'atm-row' : ''}>
                    {/* Call */}
                    <td
                      className={`price-cell ${isSelected(call!) ? 'selected' : ''}`}
                      onClick={() => call && toggleSelection(call)}
                    >
                      <span className="price">{call?.price?.toFixed(4)}</span>
                    </td>
                    <td className="iv-cell">{call?.iv ? `${(call.iv * 100).toFixed(1)}%` : '-'}</td>
                    <td className="greek-cell">{call?.delta?.toFixed(2)}</td>
                    <td className="greek-cell">{call?.gamma?.toFixed(4)}</td>
                    <td className="volume-cell">{call?.volume}</td>
                    <td className="oi-cell">{call?.openInterest}</td>

                    {/* Strike */}
                    <td className="strike-cell">{strike}</td>

                    {/* Put */}
                    <td
                      className={`price-cell ${isSelected(put!) ? 'selected' : ''}`}
                      onClick={() => put && toggleSelection(put)}
                    >
                      <span className="price">{put?.price?.toFixed(4)}</span>
                    </td>
                    <td className="iv-cell">{put?.iv ? `${(put.iv * 100).toFixed(1)}%` : '-'}</td>
                    <td className="greek-cell">{put?.delta?.toFixed(2)}</td>
                    <td className="greek-cell">{put?.gamma?.toFixed(4)}</td>
                    <td className="volume-cell">{put?.volume}</td>
                    <td className="oi-cell">{put?.openInterest}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="iv-skew-container">
          <div id="iv-skew-chart" style={{ width: '100%', height: '400px' }} />
          <div className="iv-analysis">
            <h4>波动率分析</h4>
            <div className="iv-stats">
              <div className="iv-stat">
                <label>ATM IV</label>
                <span className="stat-value">
                  {(() => {
                    const atm = ivSkewData.find(d => Math.abs(d.strike - spotPrice) < 25);
                    return atm ? `${(atm.avgIV * 100).toFixed(1)}%` : '-';
                  })()}
                </span>
              </div>
              <div className="iv-stat">
                <label>IV Skew (90/110)</label>
                <span className="stat-value">
                  {(() => {
                    const lowStrike = ivSkewData.find(d => d.strike <= spotPrice * 0.9);
                    const highStrike = ivSkewData.find(d => d.strike >= spotPrice * 1.1);
                    if (lowStrike && highStrike) {
                      const skew = (lowStrike.avgIV - highStrike.avgIV) * 100;
                      return `${skew.toFixed(1)}%`;
                    }
                    return '-';
                  })()}
                </span>
              </div>
              <div className="iv-stat">
                <label>Call/Put IV Ratio</label>
                <span className="stat-value">
                  {(() => {
                    const avgCallIV = ivSkewData.reduce((sum, d) => sum + d.callIV, 0) / ivSkewData.length;
                    const avgPutIV = ivSkewData.reduce((sum, d) => sum + d.putIV, 0) / ivSkewData.length;
                    return (avgCallIV / avgPutIV).toFixed(2);
                  })()}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
