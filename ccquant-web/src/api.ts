import axios from 'axios';
import type {
  UnderlyingInfo,
  OptionBarRow,
  DailyBarRow,
  MergedBarRow,
  FilteredStats,
  MarketOverview,
  VolSmileGroup,
  Vol3DPoint,
  VolSurfaceResponse,
  VolSurfaceV2Response,
  ContractInfo,
  ContractData,
  StrategyFile,
  OptionChainData,
} from './types';

const api = axios.create({ baseURL: '' });

// ========== 数据库页面 API ==========

/** 获取标的列表 */
export async function getUnderlyings(): Promise<UnderlyingInfo[]> {
  const { data } = await api.get('/api/data/underlyings');
  return data;
}

/** 获取到期日列表 */
export async function getExpiryDates(symbol: string): Promise<string[]> {
  const { data } = await api.get(`/api/data/underlyings/${symbol}/expiries`);
  return data;
}

/** 获取筛选后的统计数据 */
export async function getFilteredStats(params: {
  underlying: string;
  expiry?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}): Promise<FilteredStats> {
  const { data } = await api.get('/api/data/stats', { params });
  return data;
}

/** 获取期权K线（分页 + 筛选） */
export async function getOptionBars(params: {
  underlying: string;
  page?: number;
  page_size?: number;
  expiry?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}): Promise<{ data: OptionBarRow[]; total: number }> {
  const { data } = await api.get('/api/data/option-bars', { params });
  return { data: data.data || [], total: data.total || 0 };
}

/** 获取标的K线（分页） */
export async function getDailyBars(params: {
  symbol: string;
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
}): Promise<{ data: DailyBarRow[]; total: number }> {
  const { data } = await api.get('/api/data/daily-bars', { params });
  return { data: data.data || [], total: data.total || 0 };
}

/** 获取合并K线（期权 + 标的，分页） */
export async function getMergedBars(params: {
  underlying: string;
  page?: number;
  page_size?: number;
  expiry?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}): Promise<{ data: MergedBarRow[]; total: number }> {
  const { data } = await api.get('/api/data/merged-bars', { params });
  return { data: data.data || [], total: data.total || 0 };
}

/** 上传数据文件 */
export async function uploadDataFile(
  file: File,
  dataType: 'option' | 'underlying',
  symbol: string,
  granularity: 'daily' | 'minute',
  onProgress?: (pct: number) => void,
): Promise<{ success: boolean; message: string; imported?: number }> {
  const form = new FormData();
  form.append('file', file);
  form.append('data_type', dataType);
  form.append('symbol', symbol);
  form.append('granularity', granularity);
  const { data } = await api.post('/api/data/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

/** 删除期权K线（支持日期范围和合约筛选） */
export async function deleteOptionBars(
  underlying: string,
  expiry?: string,
  start_date?: string,
  end_date?: string,
  search?: string,
): Promise<{ deleted: number }> {
  const { data } = await api.delete('/api/data/option-bars', {
    params: { underlying, expiry, start_date, end_date, search },
  });
  return data;
}

/** 删除标的K线（支持日期范围） */
export async function deleteDailyBars(
  symbol: string,
  start_date?: string,
  end_date?: string,
): Promise<{ deleted: number }> {
  const { data } = await api.delete('/api/data/daily-bars', {
    params: { symbol, start_date, end_date },
  });
  return data;
}

// ========== 可视化页面 API ==========

export async function getVolSmile(
  underlying: string,
  tradeDate: string,
): Promise<VolSmileGroup[]> {
  const { data } = await api.get(`/api/viz/vol-smile/${underlying}`, {
    params: { trade_date: tradeDate },
  });
  return data;
}

export async function getVolSurface(
  underlying: string,
  tradeDate: string,
  mode: 'raw' | 'svi' = 'raw',
): Promise<VolSurfaceResponse> {
  const { data } = await api.get(`/api/viz/vol-surface/${underlying}`, {
    params: { trade_date: tradeDate, mode },
  });
  // 兼容旧格式: 后端未重启时返回 Vol3DPoint[] 数组
  if (Array.isArray(data)) {
    // 从有效 IV 的 strike 中位数估算 spot
    const validStrikes = data.filter((d: any) => d.iv > 0).map((d: any) => d.strike).sort((a: number, b: number) => a - b);
    const spot = validStrikes.length > 0 ? validStrikes[Math.floor(validStrikes.length / 2)] : 0;
    return { spot, tradeDate, points: data, sviPoints: [], mode: 'raw' };
  }
  return data;
}

export async function getVolSurfaceV2(
  underlying: string,
  tradeDate: string,
  mode: 'raw' | 'synthetic' = 'raw',
): Promise<VolSurfaceV2Response> {
  try {
    const { data } = await api.get(`/api/viz/vol-surface-v2/${underlying}`, {
      params: { trade_date: tradeDate, mode },
    });
    return data;
  } catch (err: any) {
    // Fallback: 如果 v2 端点不存在 (后端未重启), 用旧端点兼容
    if (err?.response?.status === 404 || err?.response?.status === 405) {
      console.warn('vol-surface-v2 not available, falling back to v1');
      const old = await getVolSurface(underlying, tradeDate, 'raw');
      return {
        ...old,
        volumeBars: [],
        atmIvData: [],
        skewData: [],
      };
    }
    throw err;
  }
}

export async function getMarketOverview(
  underlying: string,
  startDate: string,
  endDate: string,
  contractSymbol?: string,
): Promise<MarketOverview> {
  const { data } = await api.get(`/api/viz/market/${underlying}`, {
    params: {
      start_date: startDate,
      end_date: endDate,
      contract_symbol: contractSymbol,
    },
  });
  return data;
}

export async function getTradeDates(underlying: string): Promise<string[]> {
  const { data } = await api.get(`/api/data/underlyings/${underlying}/trade-dates`);
  return data;
}

export async function getUnderlyingContracts(underlying: string, expiry?: string): Promise<ContractInfo[]> {
  const { data } = await api.get(`/api/data/underlyings/${underlying}/contracts`, {
    params: expiry ? { expiry } : undefined,
  });
  return data;
}

export async function getContractData(
  symbol: string,
  startDate: string,
  endDate: string,
): Promise<ContractData> {
  const { data } = await api.get(`/api/viz/contract/${symbol}`, {
    params: { start_date: startDate, end_date: endDate },
  });
  return data;
}

export async function getOptionChain(
  underlying: string,
  tradeDate: string,
  expiry?: string,
): Promise<OptionChainData[]> {
  const { data } = await api.get(`/api/viz/option-chain/${underlying}`, {
    params: { trade_date: tradeDate, expiry },
  });
  return data;
}

// ========== 策略编写页面 API ==========

export async function getStrategies(): Promise<StrategyFile[]> {
  const { data } = await api.get('/api/strategies');
  return data;
}

export async function getStrategyCode(filename: string): Promise<string> {
  const { data } = await api.get(`/api/strategies/${filename}/code`);
  return data.code;
}

export async function saveStrategy(
  filename: string, code: string, name: string, description: string, category: string,
): Promise<{ success: boolean }> {
  const { data } = await api.post(`/api/strategies/${filename}`, { code, name, description, category });
  return data;
}

export async function openInIDE(filename: string): Promise<{ success: boolean }> {
  const { data } = await api.post(`/api/strategies/${filename}/open-ide`);
  return data;
}

// ========== 策略回测页面 API ==========

export async function runBacktest(payload: Record<string, unknown>) {
  const { data } = await api.post('/api/backtest/run', payload);
  return data;
}

export async function runOptimization(payload: Record<string, unknown>) {
  const { data } = await api.post('/api/backtest/optimize', payload);
  return data;
}

export async function getBacktestHistory(limit = 50) {
  const { data } = await api.get('/api/backtest/history', { params: { limit } });
  return data;
}
