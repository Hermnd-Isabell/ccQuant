import type { ParameterDef } from '../types';

interface Props {
  parameters: ParameterDef[];
  values: Record<string, any>;
  onChange: (values: Record<string, any>) => void;
}

export function StrategyParamsForm({ parameters, values, onChange }: Props) {
  const handleChange = (name: string, value: any) => {
    onChange({ ...values, [name]: value });
  };

  if (parameters.length === 0) {
    return <div className="params-empty">该策略无配置参数</div>;
  }

  return (
    <div className="params-form">
      {parameters.map((param) => (
        <div key={param.name} className="param-field">
          <label className="param-label">
            {param.displayName}
            <span className="param-name">({param.name})</span>
          </label>

          {param.type === 'select' && param.options ? (
            <select
              value={values[param.name] ?? param.default}
              onChange={(e) => handleChange(param.name, e.target.value)}
              className="param-input"
            >
              {param.options.map((opt) => (
                <option key={String(opt.value)} value={String(opt.value)}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : param.type === 'boolean' ? (
            <label className="param-toggle">
              <input
                type="checkbox"
                checked={values[param.name] ?? param.default}
                onChange={(e) => handleChange(param.name, e.target.checked)}
              />
              <span className="toggle-slider" />
            </label>
          ) : param.type === 'number' ? (
            <input
              type="number"
              min={param.min}
              max={param.max}
              step={param.step}
              value={values[param.name] ?? param.default}
              onChange={(e) => handleChange(param.name, parseFloat(e.target.value))}
              className="param-input"
            />
          ) : (
            <input
              type="text"
              value={values[param.name] ?? param.default}
              onChange={(e) => handleChange(param.name, e.target.value)}
              className="param-input"
            />
          )}
        </div>
      ))}
    </div>
  );
}

// 预定义策略配置
export const STRATEGY_DEFINITIONS: Record<string, { displayName: string; description: string; parameters: ParameterDef[] }> = {
  BuyCallStrategy: {
    displayName: '买入看涨期权',
    description: '选择虚值/平值看涨期权买入，适合看多行情',
    parameters: [
      {
        name: 'strike_offset',
        displayName: '行权价偏移',
        type: 'select',
        default: 0,
        options: [
          { label: '实值1档 (-1)', value: -1 },
          { label: '平值 (0)', value: 0 },
          { label: '虚值1档 (+1)', value: 1 },
          { label: '虚值2档 (+2)', value: 2 },
        ],
      },
      {
        name: 'expiry_days',
        displayName: '目标到期天数',
        type: 'number',
        default: 30,
        min: 7,
        max: 90,
        step: 1,
      },
      {
        name: 'position_ratio',
        displayName: '仓位比例',
        type: 'number',
        default: 0.1,
        min: 0.01,
        max: 1,
        step: 0.01,
      },
    ],
  },
  StraddleStrategy: {
    displayName: '买入跨式组合',
    description: '同时买入相同行权价的看涨和看跌期权，适合预期大波动',
    parameters: [
      {
        name: 'strike_offset',
        displayName: '行权价偏移',
        type: 'select',
        default: 0,
        options: [
          { label: '平值 (0)', value: 0 },
          { label: '虚值1档 (+1)', value: 1 },
        ],
      },
      {
        name: 'expiry_days',
        displayName: '目标到期天数',
        type: 'number',
        default: 30,
        min: 7,
        max: 90,
        step: 1,
      },
      {
        name: 'position_ratio',
        displayName: '仓位比例',
        type: 'number',
        default: 0.1,
        min: 0.01,
        max: 1,
        step: 0.01,
      },
    ],
  },
  IronCondorStrategy: {
    displayName: '铁鹰价差策略',
    description: '卖出跨式同时买入宽跨式，适合预期横盘',
    parameters: [
      {
        name: 'short_strike_offset',
        displayName: '卖出行权价偏移',
        type: 'select',
        default: 1,
        options: [
          { label: '虚值1档 (+1)', value: 1 },
          { label: '虚值2档 (+2)', value: 2 },
        ],
      },
      {
        name: 'long_strike_offset',
        displayName: '买入行权价偏移',
        type: 'select',
        default: 2,
        options: [
          { label: '虚值2档 (+2)', value: 2 },
          { label: '虚值3档 (+3)', value: 3 },
        ],
      },
      {
        name: 'expiry_days',
        displayName: '目标到期天数',
        type: 'number',
        default: 30,
        min: 7,
        max: 60,
        step: 1,
      },
      {
        name: 'position_ratio',
        displayName: '仓位比例',
        type: 'number',
        default: 0.1,
        min: 0.01,
        max: 1,
        step: 0.01,
      },
    ],
  },
  BullCallSpreadStrategy: {
    displayName: '牛市看涨价差',
    description: '买入低行权价Call，卖出高行权价Call，适合温和看多',
    parameters: [
      {
        name: 'long_strike_offset',
        displayName: '买入行权价偏移',
        type: 'number',
        default: -0.05,
        min: -0.2,
        max: 0,
        step: 0.01,
      },
      {
        name: 'short_strike_offset',
        displayName: '卖出行权价偏移',
        type: 'number',
        default: 0.05,
        min: 0,
        max: 0.2,
        step: 0.01,
      },
      {
        name: 'quantity',
        displayName: '手数',
        type: 'number',
        default: 1,
        min: 1,
        max: 100,
        step: 1,
      },
    ],
  },
  BearPutSpreadStrategy: {
    displayName: '熊市看跌价差',
    description: '买入高行权价Put，卖出低行权价Put，适合温和看空',
    parameters: [
      {
        name: 'long_strike_offset',
        displayName: '买入行权价偏移',
        type: 'number',
        default: 0.05,
        min: 0,
        max: 0.2,
        step: 0.01,
      },
      {
        name: 'short_strike_offset',
        displayName: '卖出行权价偏移',
        type: 'number',
        default: -0.05,
        min: -0.2,
        max: 0,
        step: 0.01,
      },
      {
        name: 'quantity',
        displayName: '手数',
        type: 'number',
        default: 1,
        min: 1,
        max: 100,
        step: 1,
      },
    ],
  },
  StrangleStrategy: {
    displayName: '买入宽跨式',
    description: '买入虚值Call和虚值Put，成本低于跨式，适合预期大波动',
    parameters: [
      {
        name: 'call_strike_offset',
        displayName: 'Call行权价偏移',
        type: 'number',
        default: 0.05,
        min: 0.02,
        max: 0.15,
        step: 0.01,
      },
      {
        name: 'put_strike_offset',
        displayName: 'Put行权价偏移',
        type: 'number',
        default: -0.05,
        min: -0.15,
        max: -0.02,
        step: 0.01,
      },
      {
        name: 'quantity',
        displayName: '手数',
        type: 'number',
        default: 1,
        min: 1,
        max: 100,
        step: 1,
      },
      {
        name: 'profit_target',
        displayName: '止盈比例',
        type: 'number',
        default: 0.5,
        min: 0.1,
        max: 1.0,
        step: 0.1,
      },
    ],
  },
  ButterflySpreadStrategy: {
    displayName: '蝶式价差策略',
    description: '三腿组合策略，适合预期标的价格在到期时接近中心行权价',
    parameters: [
      {
        name: 'center_strike_offset',
        displayName: '中心行权价偏移',
        type: 'number',
        default: 0.0,
        min: -0.1,
        max: 0.1,
        step: 0.01,
      },
      {
        name: 'wing_width',
        displayName: '翅膀宽度',
        type: 'number',
        default: 0.05,
        min: 0.02,
        max: 0.1,
        step: 0.01,
      },
      {
        name: 'quantity',
        displayName: '手数',
        type: 'number',
        default: 1,
        min: 1,
        max: 100,
        step: 1,
      },
    ],
  },
  CalendarSpreadStrategy: {
    displayName: '日历价差策略',
    description: '卖出近月买入远月，赚取时间价值衰减差异',
    parameters: [
      {
        name: 'strike_offset',
        displayName: '行权价偏移',
        type: 'number',
        default: 0.0,
        min: -0.1,
        max: 0.1,
        step: 0.01,
      },
      {
        name: 'near_month',
        displayName: '近月序号',
        type: 'number',
        default: 0,
        min: 0,
        max: 2,
        step: 1,
      },
      {
        name: 'far_month',
        displayName: '远月序号',
        type: 'number',
        default: 1,
        min: 1,
        max: 3,
        step: 1,
      },
      {
        name: 'quantity',
        displayName: '手数',
        type: 'number',
        default: 1,
        min: 1,
        max: 100,
        step: 1,
      },
    ],
  },
  RatioSpreadStrategy: {
    displayName: '比率价差策略',
    description: '买入1个低行权价Call，卖出N个高行权价Call',
    parameters: [
      {
        name: 'long_strike_offset',
        displayName: '买入行权价偏移',
        type: 'number',
        default: 0.0,
        min: -0.1,
        max: 0.05,
        step: 0.01,
      },
      {
        name: 'short_strike_offset',
        displayName: '卖出行权价偏移',
        type: 'number',
        default: 0.05,
        min: 0.02,
        max: 0.15,
        step: 0.01,
      },
      {
        name: 'ratio',
        displayName: '比率',
        type: 'number',
        default: 2,
        min: 1,
        max: 5,
        step: 1,
      },
      {
        name: 'quantity',
        displayName: '基础手数',
        type: 'number',
        default: 1,
        min: 1,
        max: 100,
        step: 1,
      },
    ],
  },
  DualThrustStrategy: {
    displayName: 'Dual Thrust策略',
    description: '日内突破策略，根据N日最高价/最低价与收盘价的关系计算上下轨，突破上轨做多，突破下轨做空',
    parameters: [
      {
        name: 'k1',
        displayName: '上轨系数',
        type: 'number',
        default: 0.4,
        min: 0.01,
        max: 2.0,
        step: 0.01,
      },
      {
        name: 'k2',
        displayName: '下轨系数',
        type: 'number',
        default: 0.6,
        min: 0.01,
        max: 2.0,
        step: 0.01,
      },
      {
        name: 'fixed_size',
        displayName: '交易数量',
        type: 'number',
        default: 1,
        min: 1,
        max: 100,
        step: 1,
      },
    ],
  },
  PairTradingStrategy: {
    displayName: '配对交易策略',
    description: '基于价差的布林带均值回归策略，做多/做空价差并在回归中轨时平仓',
    parameters: [
      {
        name: 'boll_window',
        displayName: '布林窗口',
        type: 'number',
        default: 20,
        min: 5,
        max: 100,
        step: 1,
      },
      {
        name: 'boll_dev',
        displayName: '布林倍差',
        type: 'number',
        default: 2.0,
        min: 0.5,
        max: 5.0,
        step: 0.1,
      },
      {
        name: 'fixed_size',
        displayName: '交易数量',
        type: 'number',
        default: 1,
        min: 1,
        max: 100,
        step: 1,
      },
    ],
  },
  AtrRsiStrategy: {
    displayName: 'ATR-RSI策略',
    description: '结合ATR波动率与RSI超买超卖信号进行开平仓',
    parameters: [
      { name: 'atr_length', displayName: 'ATR周期', type: 'number', default: 22, min: 5, max: 100, step: 1 },
      { name: 'atr_ma_length', displayName: 'ATR均线周期', type: 'number', default: 10, min: 5, max: 100, step: 1 },
      { name: 'rsi_length', displayName: 'RSI周期', type: 'number', default: 5, min: 2, max: 50, step: 1 },
      { name: 'rsi_entry', displayName: 'RSI入场阈值', type: 'number', default: 16, min: 5, max: 50, step: 1 },
      { name: 'trailing_percent', displayName: '移动止损百分比', type: 'number', default: 0.8, min: 0.1, max: 5.0, step: 0.1 },
      { name: 'fixed_size', displayName: '交易数量', type: 'number', default: 1, min: 1, max: 100, step: 1 },
    ],
  },
  BollChannelStrategy: {
    displayName: '布林通道策略',
    description: '基于布林带、CCI和ATR的综合突破与跟踪止损策略',
    parameters: [
      { name: 'boll_window', displayName: '布林周期', type: 'number', default: 18, min: 5, max: 100, step: 1 },
      { name: 'boll_dev', displayName: '布林标准差倍数', type: 'number', default: 3.4, min: 0.5, max: 10.0, step: 0.1 },
      { name: 'cci_window', displayName: 'CCI周期', type: 'number', default: 10, min: 5, max: 100, step: 1 },
      { name: 'atr_window', displayName: 'ATR周期', type: 'number', default: 30, min: 5, max: 100, step: 1 },
      { name: 'sl_multiplier', displayName: '止损ATR倍数', type: 'number', default: 5.2, min: 0.5, max: 20.0, step: 0.1 },
      { name: 'fixed_size', displayName: '交易数量', type: 'number', default: 1, min: 1, max: 100, step: 1 },
    ],
  },
  DoubleMaStrategy: {
    displayName: '双均线策略',
    description: '快线突破慢线做多，快线跌破慢线做空的经典趋势策略',
    parameters: [
      { name: 'fast_window', displayName: '快线周期', type: 'number', default: 10, min: 2, max: 100, step: 1 },
      { name: 'slow_window', displayName: '慢线周期', type: 'number', default: 20, min: 5, max: 200, step: 1 },
    ],
  },
  KingKeltnerStrategy: {
    displayName: '金肯特纳策略',
    description: '基于Keltner通道突破开仓，结合移动止损离场',
    parameters: [
      { name: 'kk_length', displayName: 'KK周期', type: 'number', default: 11, min: 5, max: 100, step: 1 },
      { name: 'kk_dev', displayName: 'KK标准差倍数', type: 'number', default: 1.6, min: 0.1, max: 10.0, step: 0.1 },
      { name: 'trailing_percent', displayName: '移动止损百分比', type: 'number', default: 0.8, min: 0.1, max: 5.0, step: 0.1 },
      { name: 'fixed_size', displayName: '交易数量', type: 'number', default: 1, min: 1, max: 100, step: 1 },
    ],
  },
  MultiSignalStrategy: {
    displayName: '多信号组合策略',
    description: '综合RSI、CCI和MA三个信号产生目标仓位并自动调仓',
    parameters: [
      { name: 'rsi_window', displayName: 'RSI周期', type: 'number', default: 14, min: 2, max: 100, step: 1 },
      { name: 'rsi_level', displayName: 'RSI阈值', type: 'number', default: 20, min: 5, max: 50, step: 1 },
      { name: 'cci_window', displayName: 'CCI周期', type: 'number', default: 30, min: 5, max: 100, step: 1 },
      { name: 'cci_level', displayName: 'CCI阈值', type: 'number', default: 10, min: 5, max: 50, step: 1 },
      { name: 'fast_window', displayName: '快线周期', type: 'number', default: 5, min: 2, max: 100, step: 1 },
      { name: 'slow_window', displayName: '慢线周期', type: 'number', default: 20, min: 5, max: 200, step: 1 },
    ],
  },
  MultiTimeframeStrategy: {
    displayName: '多周期策略',
    description: '用15分钟K判断MA趋势，5分钟K配合RSI信号入场',
    parameters: [
      { name: 'rsi_signal', displayName: 'RSI信号阈值', type: 'number', default: 20, min: 5, max: 50, step: 1 },
      { name: 'rsi_window', displayName: 'RSI周期', type: 'number', default: 14, min: 2, max: 100, step: 1 },
      { name: 'fast_window', displayName: '快线周期', type: 'number', default: 5, min: 2, max: 100, step: 1 },
      { name: 'slow_window', displayName: '慢线周期', type: 'number', default: 20, min: 5, max: 200, step: 1 },
      { name: 'fixed_size', displayName: '交易数量', type: 'number', default: 1, min: 1, max: 100, step: 1 },
    ],
  },
  TestStrategy: {
    displayName: '测试策略',
    description: '用于测试订单系统的演示策略',
    parameters: [
      { name: 'test_trigger', displayName: '触发计数', type: 'number', default: 10, min: 1, max: 100, step: 1 },
    ],
  },
  TurtleSignalStrategy: {
    displayName: '海龟信号策略',
    description: '经典海龟交易法则，唐奇安通道突破入场，N倍ATR止损',
    parameters: [
      { name: 'entry_window', displayName: '入场窗口', type: 'number', default: 20, min: 5, max: 100, step: 1 },
      { name: 'exit_window', displayName: '出场窗口', type: 'number', default: 10, min: 2, max: 100, step: 1 },
      { name: 'atr_window', displayName: 'ATR周期', type: 'number', default: 20, min: 5, max: 100, step: 1 },
      { name: 'fixed_size', displayName: '交易数量', type: 'number', default: 1, min: 1, max: 100, step: 1 },
    ],
  },
  IvPredictStrategy: {
    displayName: 'IV预测策略',
    description: '基于M-W B-Spline和XGBoost的IV预测策略，包含残差驱动(A)、截面偏差(B)、双信号组合(C)三种子策略',
    parameters: [
      {
        name: 'strategy_type',
        displayName: '策略类型',
        type: 'select',
        default: 'A',
        options: [
          { label: '残差变化驱动 (A)', value: 'A' },
          { label: '截面偏差驱动 (B)', value: 'B' },
          { label: '双信号组合 (C)', value: 'C' },
        ],
      },
      { name: 'data_dir', displayName: '数据目录', type: 'string', default: 'strategy/data' },
      { name: 'model_path', displayName: '模型路径', type: 'string', default: 'strategy/data/output/baseline_xgb/model_abs_iv.pkl' },
      { name: 'fixed_size', displayName: '每腿手数', type: 'number', default: 1, min: 1, max: 100, step: 1 },
      { name: 'signal_threshold', displayName: '信号阈值', type: 'number', default: 0.003, min: 0, max: 0.1, step: 0.001 },
      { name: 'zscore_threshold', displayName: 'Z-Score阈值', type: 'number', default: 1.0, min: 0, max: 5, step: 0.1 },
      { name: 'long_pct', displayName: '多头比例', type: 'number', default: 0.10, min: 0.01, max: 1, step: 0.01 },
      { name: 'short_pct', displayName: '空头比例', type: 'number', default: 0.10, min: 0.01, max: 1, step: 0.01 },
    ],
  },
  IvPredictStrategyAEnhanced: {
    displayName: 'IV预测策略A-Enhanced',
    description: '基于Diffusion增强数据训练的XGBoost残差驱动策略，参数针对增强模型优化（更宽松的阈值和更大的持仓比例）',
    parameters: [
      {
        name: 'strategy_type',
        displayName: '策略类型',
        type: 'select',
        default: 'A',
        options: [
          { label: '残差变化驱动 (A)', value: 'A' },
          { label: '截面偏差驱动 (B)', value: 'B' },
          { label: '双信号组合 (C)', value: 'C' },
        ],
      },
      { name: 'data_dir', displayName: '数据目录', type: 'string', default: 'strategy/data' },
      { name: 'model_path', displayName: '模型路径', type: 'string', default: 'strategy/data/output/baseline_xgb/model_abs_iv_enhanced.pkl' },
      { name: 'fixed_size', displayName: '每腿手数', type: 'number', default: 1, min: 1, max: 100, step: 1 },
      { name: 'signal_threshold', displayName: '信号阈值', type: 'number', default: 0.001, min: 0, max: 0.1, step: 0.001 },
      { name: 'zscore_threshold', displayName: 'Z-Score阈值', type: 'number', default: 1.0, min: 0, max: 5, step: 0.1 },
      { name: 'long_pct', displayName: '多头比例', type: 'number', default: 0.15, min: 0.01, max: 1, step: 0.01 },
      { name: 'short_pct', displayName: '空头比例', type: 'number', default: 0.15, min: 0.01, max: 1, step: 0.01 },
    ],
  },
};

export const STRATEGY_CATEGORIES: Record<string, { label: string; strategies: string[] }> = {
  single_single: {
    label: '单标的单合约',
    strategies: [
      'BuyCallStrategy',
      'SimpleBuyHoldStrategy',
      'AtrRsiStrategy',
      'BollChannelStrategy',
      'DoubleMaStrategy',
      'DualThrustStrategy',
      'KingKeltnerStrategy',
      'MultiSignalStrategy',
      'MultiTimeframeStrategy',
      'TestStrategy',
      'TurtleSignalStrategy',
    ],
  },
  single_multi: {
    label: '单标的多合约',
    strategies: [
      'StraddleStrategy',
      'IronCondorStrategy',
      'BullCallSpreadStrategy',
      'BearPutSpreadStrategy',
      'StrangleStrategy',
      'ButterflySpreadStrategy',
      'CalendarSpreadStrategy',
      'RatioSpreadStrategy',
      'IvPredictStrategy',
      'IvPredictStrategyAEnhanced',
    ],
  },
  multi_multi: {
    label: '多标的多合约',
    strategies: ['PairTradingStrategy'],
  },
};
