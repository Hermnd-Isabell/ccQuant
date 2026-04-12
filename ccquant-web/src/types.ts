// ========== 通用 ==========

export interface ApiResponse<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ========== 数据库页面 ==========

export interface UnderlyingInfo {
  symbol: string;
  name: string;
  type: string;
  exchange: string;
}

export interface OptionContractInfo {
  symbol: string;
  underlying: string;
  type: string;       // C / P
  strike: number;
  expiry: string;     // ISO date
}

export interface DataSummary {
  underlyings: UnderlyingInfo[];
  optionContractCount: number;
  optionBarCount: number;
  dailyBarCount: number;
  dateRange: { start: string; end: string } | null;
}

export interface OptionBarRow {
  trade_date: string;
  symbol: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  iv: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho: number | null;
}

export interface DailyBarRow {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
}

export type Granularity = 'daily' | 'minute';

/** 合并K线行（期权 + 标的） */
export interface MergedBarRow {
  trade_date: string;
  symbol: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  iv: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho: number | null;
  fund_open: number | null;
  fund_high: number | null;
  fund_low: number | null;
  fund_close: number | null;
  fund_volume: number | null;
  fund_amount: number | null;
}

/** 筛选后的统计数据 */
export interface FilteredStats {
  optionContractCount: number;
  optionBarCount: number;
  dailyBarCount: number;
  dateRange: { start: string; end: string } | null;
}

// ========== 可视化页面 ==========

export type VisualizationView = 'market' | 'vol2d' | 'vol3d' | 'chain';

/** 行情概览数据 */
export interface MarketOverview {
  dates: string[];
  ohlc: [number, number, number, number][];
  prices: (number | null)[];
  ivs: (number | null)[];
  avgIvs?: (number | null)[];
  volumes: number[];
  openInterests?: number[];
  underlyingVolumes?: number[];
  deltas?: (number | null)[];
  gammas?: (number | null)[];
  thetas?: (number | null)[];
  vegas?: (number | null)[];
  contractInfo?: {
    symbol: string;
    type: string;
    strike: number;
    expiry: string;
  };
}

/** 波动率微笑 — 单个行权价的完整数据 */
export interface VolSmileStrike {
  strike: number;
  callIv: number | null;
  putIv: number | null;
  callOi: number | null;
  putOi: number | null;
  callOiChange: number | null;
  putOiChange: number | null;
  callVolume: number | null;
  putVolume: number | null;
  callPrice: number | null;
  putPrice: number | null;
  yesterdayCallIv: number | null;
  yesterdayPutIv: number | null;
}

/** 波动率微笑 — 按到期月分组 */
export interface VolSmileGroup {
  expiry: string;
  contractMonth: string;
  daysToExpiry: number;
  todayUnderlyingClose: number;
  yesterdayUnderlyingClose: number;
  strikes: VolSmileStrike[];
}

export interface Vol3DPoint {
  strike: number;
  expiry: string;
  iv: number;
  moneyness: number;
  T: number;
  remainingDays: number;
}

export interface VolSurfaceResponse {
  spot: number;
  tradeDate: string;
  points: Vol3DPoint[];
  sviPoints: Vol3DPoint[];
  mode: string;
}

/** 增强版波动率曲面响应 */
export interface VolumeBar3D {
  strike: number;
  expiry: string;
  moneyness: number;
  T: number;
  callOi: number;
  putOi: number;
  callVolume: number;
  putVolume: number;
}

export interface AtmIvPoint {
  expiry: string;
  T: number;
  remainingDays: number;
  atmIv: number;
  atmStrike: number;
  prevAtmIv: number | null;
}

export interface SkewPoint {
  expiry: string;
  T: number;
  remainingDays: number;
  skew: number;
  prevSkew: number | null;
}

export interface VolSurfaceV2Response {
  spot: number;
  tradeDate: string;
  points: Vol3DPoint[];
  sviPoints: Vol3DPoint[];
  volumeBars: VolumeBar3D[];
  atmIvData: AtmIvPoint[];
  skewData: SkewPoint[];
  mode: string;
  riskFreeRate?: number;
  syntheticForwards?: Record<string, number> | null;
  yesterdaySyntheticForwards?: Record<string, number> | null;
}

export interface ContractInfo {
  symbol: string;
  type: string;
  strike: number;
  expiry: string;
  contractMonth: string;
}

export interface ContractData {
  contract: {
    symbol: string;
    underlying: string;
    type: string;
    strike: number;
    expiry: string;
  };
  dates: string[];
  ohlc: [number, number, number, number][];
  volumes: number[];
  ivs: (number | null)[];
  deltas: (number | null)[];
  gammas: (number | null)[];
  thetas: (number | null)[];
  vegas: (number | null)[];
  underlyingPrices: (number | null)[];
}

/** 期权链 — 单个合约的完整数据 */
export interface OptionChainContract {
  symbol: string;
  strike: number;
  expiry: string;
  type: 'C' | 'P';
  bid: number | null;
  ask: number | null;
  last: number | null;
  volume: number;
  openInterest: number;
  iv: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho: number | null;
}

/** 期权链 — 按到期日分组 */
export interface OptionChainData {
  expiry: string;
  underlyingPrice: number;
  strikes: {
    strike: number;
    call: OptionChainContract | null;
    put: OptionChainContract | null;
  }[];
}

// ========== 策略编写页面 ==========

export interface StrategyFile {
  name: string;
  filename: string;
  description: string;
  createdAt: string;
  modifiedAt: string;
  code: string;
  category: 'option' | 'ml' | 'custom';
}

// ========== 策略回测页面 ==========

export interface UnderlyingConfig {
  symbol: string;
  weight: number;
  enabled: boolean;
}

export interface BacktestConfig {
  strategy: string;
  strategyParams: Record<string, unknown>;
  underlyings: UnderlyingConfig[];
  startDate: string;
  endDate: string;
  initialCapital: number;
  slippage: number;
  rate: number;
}

export interface BacktestResult {
  statistics: Statistics;
  portfolioHistory: PortfolioSnapshot[];
  trades: TradeRecord[];
  payoff?: PayoffData;
}

export interface Statistics {
  totalReturn: number;
  annualReturn: number;
  maxDrawdown: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
}

export interface PortfolioSnapshot {
  datetime: string;
  cash: number;
  totalMarketValue: number;
  margin: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface TradeRecord {
  datetime: string;
  vtSymbol: string;
  direction: 'LONG' | 'SHORT';
  offset: 'OPEN' | 'CLOSE';
  price: number;
  volume: number;
  pnl?: number;
}

export interface PayoffData {
  underlyingPrices: number[];
  payoffs: number[];
  label?: string;
}

export interface StrategyDefinition {
  name: string;
  displayName: string;
  description: string;
  parameters: ParameterDef[];
}

export interface ParameterDef {
  name: string;
  displayName: string;
  type: 'string' | 'number' | 'boolean' | 'select';
  default: unknown;
  options?: { label: string; value: unknown }[];
  min?: number;
  max?: number;
  step?: number;
}
