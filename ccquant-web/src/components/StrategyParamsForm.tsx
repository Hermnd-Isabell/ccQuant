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
                <option key={opt.value} value={opt.value}>
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
};
