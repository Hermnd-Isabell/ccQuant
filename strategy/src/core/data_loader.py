# -*- coding: utf-8 -*-
"""
数据加载与预处理模块
封装：原始数据加载、forward_table 计算、M-W B-Spline 拟合、特征工程、模型加载、
      DataFrame -> ccQuant bars_dict 转换
"""

from __future__ import annotations

import os
import pickle
import time
import warnings
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

warnings.filterwarnings('ignore')

# =============================================================================
# 常量
# =============================================================================

# Baseline XGBoost (model_abs_iv.pkl) 特征列
# 注意：必须与训练时的列完全一致（26维），否则 predict 会报 shape mismatch
FEATURE_COLS: List[str] = [
    'moneyness', 'moneyness_squared', 'remaining_time', 'call_put_flag',
    'exercise_price', 'moneyness_remaining_time',
    'fund_return', 'fund_volume', 'fund_high_low_ratio', 'fund_amount',
    'iv_t', 'iv_t_1', 'iv_t_2', 'iv_t_3', 'iv_t_4',
    'iv_ma5', 'iv_std5', 'iv_trend5', 'days_gap',
    'atm_iv_call_lag1', 'iv_mean_all_lag1', 'iv_std_all_lag1',
    'iv_max_all_lag1', 'iv_min_all_lag1', 'iv_vs_atm_lag1',
    'ten_year',
]


# =============================================================================
# 1. 原始数据加载
# =============================================================================

def load_raw_data(csv_path: str) -> pd.DataFrame:
    """读取原始50ETF期权CSV数据。"""
    df = pd.read_csv(csv_path)
    return df


# =============================================================================
# 2. Forward Table (Put-Call Parity 隐含远期)
# =============================================================================

def build_forward_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    全局计算每天每到期月的 F_implied。
    输出: forward_table [trade_date, last_edate, F_implied, F_theory, r, tau, F]
    """
    t0 = pd.Timestamp.now()

    sub = df[['trade_date', 'last_edate', 'exercise_price', 'call_put', 'close']].copy()
    pivoted = sub.pivot_table(
        index=['trade_date', 'last_edate', 'exercise_price'],
        columns='call_put', values='close'
    ).reset_index()
    pivoted = pivoted.dropna(subset=['C', 'P'])

    group_meta = df.groupby(['trade_date', 'last_edate']).first()[
        ['ten_year', 'remaining_time', 'fund_close']
    ]
    group_meta['r'] = group_meta['ten_year'] / 100.0
    group_meta['tau'] = group_meta['remaining_time'] / 365.0
    group_meta['F_theory'] = group_meta['fund_close'] * np.exp(group_meta['r'] * group_meta['tau'])

    merged = pivoted.merge(
        group_meta[['r', 'tau']].reset_index(), on=['trade_date', 'last_edate']
    )
    merged['F'] = merged['exercise_price'] + np.exp(merged['r'] * merged['tau']) * (merged['C'] - merged['P'])

    F_implied = merged.groupby(['trade_date', 'last_edate'])['F'].median().reset_index()
    F_implied.columns = ['trade_date', 'last_edate', 'F_implied']

    forward_table = group_meta[['F_theory']].reset_index().merge(
        F_implied, on=['trade_date', 'last_edate'], how='left'
    )
    forward_table['F_implied'] = forward_table['F_implied'].fillna(forward_table['F_theory'])
    forward_table['F'] = forward_table['F_implied']
    forward_table = forward_table.merge(
        group_meta[['r', 'tau']].reset_index(), on=['trade_date', 'last_edate']
    )

    print(f"    [build_forward_table] elapsed: {(pd.Timestamp.now() - t0).total_seconds():.2f}s")
    return forward_table


# =============================================================================
# 3. M-W B-Spline 曲面拟合 + Residual 计算
# =============================================================================

def fit_mw_surface(
    df_day: pd.DataFrame,
    call_put: str,
    forward_table_day: pd.DataFrame,
) -> Tuple[Dict[Any, Tuple], pd.Series]:
    """
    对单日单类型(C/P)在M-W空间拟合B-Spline。
    返回: spline_dict {last_edate: (M_nodes, W_nodes, cs_object, F_implied, tau_mat)}, baseline_series
    """
    df_sub = df_day[df_day['call_put'] == call_put].copy()
    df_sub = df_sub[(df_sub['remaining_time'] > 0) & (df_sub['implc_volatlty'] > 0)]
    df_sub = df_sub[df_sub['implc_volatlty'] <= 1.0]

    if len(df_sub) == 0:
        return {}, pd.Series(dtype=float)

    baseline = pd.Series(np.nan, index=df_sub.index)
    spline_dict: Dict[Any, Tuple] = {}
    valid_mats: List[float] = []

    for mat, df_mat in df_sub.groupby('last_edate'):
        df_mat = df_mat.sort_values('exercise_price')
        if len(df_mat) < 2:
            continue

        fwd = forward_table_day[forward_table_day['last_edate'] == mat]
        if len(fwd) == 0:
            continue
        F = fwd['F'].values[0]
        tau_mat_val = fwd['tau'].values[0]

        K = df_mat['exercise_price'].values.astype(float)
        IV = df_mat['implc_volatlty'].values.astype(float)

        M = np.log(K / F)
        W = IV ** 2 * tau_mat_val

        uniq = pd.DataFrame({'M': M, 'W': W}).groupby('M')['W'].mean().reset_index().sort_values('M')
        Mu, Wu = uniq['M'].values, uniq['W'].values

        if len(Mu) < 2:
            continue

        if len(Mu) >= 4:
            try:
                cs = CubicSpline(Mu, Wu)
            except Exception:
                cs = None
        else:
            cs = None

        M_query = np.log(df_mat['exercise_price'].values.astype(float) / F)
        W_interp = np.empty(len(M_query))

        if cs is not None:
            in_mask = (M_query >= Mu[0]) & (M_query <= Mu[-1])
            out_mask = ~in_mask
            if np.any(in_mask):
                W_interp[in_mask] = cs(M_query[in_mask])
            if np.any(out_mask):
                W_interp[out_mask] = np.where(M_query[out_mask] <= Mu[0], Wu[0], Wu[-1])
        else:
            W_interp = np.interp(M_query, Mu, Wu, left=Wu[0], right=Wu[-1])

        W_interp = np.maximum(W_interp, 1e-6)
        baseline_IV = np.sqrt(W_interp / tau_mat_val)
        baseline.loc[df_mat.index] = baseline_IV
        valid_mats.append(float(np.mean(baseline_IV)))

        spline_dict[mat] = (Mu, Wu, cs, F, tau_mat_val)

    if baseline.isna().any():
        fill_val = np.mean(valid_mats) if valid_mats else df_sub['implc_volatlty'].mean()
        baseline = baseline.fillna(fill_val)

    return spline_dict, baseline


def build_residual_series(df: pd.DataFrame, forward_table: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    全局计算 baseline_IV 和 residual，同时保存 daily_mw_data。
    输出: df (含 baseline_iv, residual_iv, M), daily_mw_data = {(date, cp, mat): (Mu, Wu, cs, F, tau)}
    """
    t0 = time.time()
    df = df.copy()
    df = df[(df['remaining_time'] > 0) & (df['implc_volatlty'] > 0)].copy()
    df.loc[df['implc_volatlty'] > 1.0, 'implc_volatlty'] = np.nan
    df = df.dropna(subset=['implc_volatlty']).copy()
    df['baseline_iv'] = np.nan
    df['residual_iv'] = np.nan
    df['M'] = np.nan

    fwd_dict: Dict[Tuple, Dict] = {}
    for _, row in forward_table.iterrows():
        fwd_dict[(row['trade_date'], row['last_edate'])] = {'F': row['F'], 'tau': row['tau']}

    daily_mw_data: Dict[Tuple, Tuple] = {}
    fit_days = 0
    total_contracts_fitted = 0
    M_min_all, M_max_all = float('inf'), float('-inf')
    W_min_all, W_max_all = float('inf'), float('-inf')

    groups = list(df.groupby(['trade_date', 'call_put']))
    n_groups = len(groups)
    for i, ((date, cp), group) in enumerate(groups):
        if i % 500 == 0 and i > 0:
            print(f"    ... processed {i}/{n_groups} groups ({time.time()-t0:.1f}s)")

        mats_in_group = group['last_edate'].unique()
        fwd_rows = []
        for mat in mats_in_group:
            key = (date, mat)
            if key in fwd_dict:
                d = fwd_dict[key]
                fwd_rows.append({'last_edate': mat, 'F': d['F'], 'tau': d['tau']})
        if len(fwd_rows) == 0:
            continue
        fwd_day = pd.DataFrame(fwd_rows)
        spline_dict, baseline = fit_mw_surface(group, cp, fwd_day)

        if len(spline_dict) > 0:
            fit_days += 1
            total_contracts_fitted += baseline.notna().sum()
            for mat, (Mu, Wu, cs, F, tau_mat) in spline_dict.items():
                daily_mw_data[(date, cp, mat)] = (Mu, Wu, cs, F, tau_mat)
                M_min_all = min(M_min_all, Mu.min())
                M_max_all = max(M_max_all, Mu.max())
                W_min_all = min(W_min_all, Wu.min())
                W_max_all = max(W_max_all, Wu.max())

            for mat, (Mu, Wu, cs, F, tau_mat) in spline_dict.items():
                mask = (df['trade_date'] == date) & (df['call_put'] == cp) & (df['last_edate'] == mat)
                if mask.any():
                    df.loc[mask, 'M'] = np.log(df.loc[mask, 'exercise_price'].values / F)

        df.loc[baseline.index, 'baseline_iv'] = baseline.values

    df['residual_iv'] = df['implc_volatlty'] - df['baseline_iv']

    n_trade_days = df['trade_date'].nunique()
    print(f"  [MW Spline] elapsed: {time.time()-t0:.1f}s")
    print(f"  [MW Spline] Fit success days: {fit_days}/{n_trade_days}")
    print(f"  [MW Spline] Avg contracts/day/type: {total_contracts_fitted/max(fit_days,1):.1f}")
    print(f"  [MW Spline] Residual stats: mean={df['residual_iv'].mean():.6f}, std={df['residual_iv'].std():.6f}")
    return df, daily_mw_data


# =============================================================================
# 4. 特征工程 (兼容 model_abs_iv.pkl)
# =============================================================================

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    构造 XGBoost 特征列。兼容 baseline_xgb (model_abs_iv.pkl)。
    输入 df 需包含原始列 + baseline_iv/residual_iv（若有）。
    """
    df = df.copy()
    df = df.sort_values(['security_id', 'trade_date']).reset_index(drop=True)

    # D1. 异常值与边界处理
    df = df[(df['remaining_time'] > 0) & (df['implc_volatlty'] > 0)].copy()
    df.loc[df['implc_volatlty'] > 1.0, 'implc_volatlty'] = np.nan
    df = df.dropna(subset=['implc_volatlty']).copy()
    spot_missing_dates = df[df['fund_close'].isna()]['trade_date'].unique()
    df = df[~df['trade_date'].isin(spot_missing_dates)].copy()

    # 1. 合约固有特征
    df['moneyness'] = df['fund_close'] / df['exercise_price']
    df['moneyness_squared'] = df['moneyness'] ** 2
    df['call_put_flag'] = (df['call_put'] == 'C').astype(int)
    df['moneyness_remaining_time'] = df['moneyness'] * df['remaining_time']

    # 2. 标的数据特征
    spot_daily = df[['trade_date', 'fund_close', 'fund_volume', 'fund_amount',
                     'fund_high', 'fund_low']].drop_duplicates('trade_date').sort_values('trade_date')
    spot_daily['fund_return'] = spot_daily['fund_close'].pct_change()
    spot_daily['fund_high_low_ratio'] = (spot_daily['fund_high'] - spot_daily['fund_low']) / spot_daily['fund_close']
    df = df.merge(
        spot_daily[['trade_date', 'fund_return', 'fund_high_low_ratio']],
        on='trade_date', how='left'
    )

    # 3. 历史IV序列特征
    trade_dates = np.sort(df['trade_date'].unique())
    date_map = pd.DataFrame({
        'trade_date': trade_dates,
        'trade_dt': pd.to_datetime(trade_dates, format='%Y%m%d')
    })
    df = df.merge(date_map, on='trade_date', how='left')

    def compute_iv_lags(group):
        group = group.sort_values('trade_date')
        group['iv_t'] = group['implc_volatlty']
        group['iv_t_1'] = group['implc_volatlty'].shift(1)
        group['iv_t_2'] = group['implc_volatlty'].shift(2)
        group['iv_t_3'] = group['implc_volatlty'].shift(3)
        group['iv_t_4'] = group['implc_volatlty'].shift(4)
        group['iv_ma5'] = group['implc_volatlty'].rolling(window=5, min_periods=1).mean()
        group['iv_std5'] = group['implc_volatlty'].rolling(window=5, min_periods=2).std()
        group['iv_trend5'] = group['implc_volatlty'] - group['implc_volatlty'].shift(4)
        group['days_gap'] = (group['trade_dt'] - group['trade_dt'].shift(1)).dt.days
        return group

    df = df.groupby('security_id', group_keys=False).apply(compute_iv_lags)

    # 4. 曲面上下文特征 (t-1日)
    daily_stats = []
    for date, day_df in df.groupby('trade_date'):
        stats = {
            'trade_date': date,
            'iv_mean_all': day_df['implc_volatlty'].mean(),
            'iv_std_all': day_df['implc_volatlty'].std(),
            'iv_max_all': day_df['implc_volatlty'].max(),
            'iv_min_all': day_df['implc_volatlty'].min(),
        }
        call_df = day_df[day_df['call_put'] == 'C'].copy()
        if len(call_df) >= 2:
            call_df = call_df.sort_values('exercise_price')
            fund_close = call_df['fund_close'].iloc[0]
            xp = call_df['exercise_price'].values
            fp = call_df['implc_volatlty'].values
            if np.all(np.diff(xp) > 0):
                atm_iv = np.interp(fund_close, xp, fp)
            else:
                call_agg = call_df.groupby('exercise_price')['implc_volatlty'].mean().reset_index().sort_values('exercise_price')
                atm_iv = np.interp(fund_close, call_agg['exercise_price'].values, call_agg['implc_volatlty'].values)
        else:
            atm_iv = np.nan
        stats['atm_iv_call'] = atm_iv
        daily_stats.append(stats)

    daily_stats_df = pd.DataFrame(daily_stats).sort_values('trade_date')
    daily_stats_lag = daily_stats_df.copy()
    daily_stats_lag['trade_date_dt'] = pd.to_datetime(daily_stats_lag['trade_date'], format='%Y%m%d')
    daily_stats_lag['merge_date'] = (daily_stats_lag['trade_date_dt'] + pd.Timedelta(days=1)).dt.strftime('%Y%m%d').astype(int)
    daily_stats_lag = daily_stats_lag.rename(columns={
        'iv_mean_all': 'iv_mean_all_lag1',
        'iv_std_all': 'iv_std_all_lag1',
        'iv_max_all': 'iv_max_all_lag1',
        'iv_min_all': 'iv_min_all_lag1',
        'atm_iv_call': 'atm_iv_call_lag1',
    })

    df = df.merge(
        daily_stats_lag[['merge_date', 'iv_mean_all_lag1', 'iv_std_all_lag1',
                         'iv_max_all_lag1', 'iv_min_all_lag1', 'atm_iv_call_lag1']],
        left_on='trade_date', right_on='merge_date', how='left'
    ).drop(columns=['merge_date'])

    df['iv_vs_atm_lag1'] = df['implc_volatlty'] - df['atm_iv_call_lag1']

    # 5. 宏观特征
    df['ten_year'] = df['ten_year'] / 100.0

    # 确保所有特征列存在
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = np.nan

    # 填充缺失
    for col in ['atm_iv_call_lag1', 'iv_mean_all_lag1', 'iv_std_all_lag1',
                'iv_max_all_lag1', 'iv_min_all_lag1', 'iv_vs_atm_lag1']:
        df[col] = df[col].fillna(df[col].mean())

    df['days_gap'] = df['days_gap'].fillna(1)
    df['fund_return'] = df['fund_return'].fillna(0)
    for col in ['iv_t_1', 'iv_t_2', 'iv_t_3', 'iv_t_4', 'iv_std5', 'iv_trend5']:
        if col in df.columns:
            df[col] = df[col].fillna(df['iv_t'])

    return df


# =============================================================================
# 5. 目标变量 / next-day 列构造 (策略A T+1插值需要)
# =============================================================================

def build_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    构造 next-day 列，供策略A的 T+1 baseline 插值使用。
    """
    df = df.copy().sort_values(['security_id', 'trade_date']).reset_index(drop=True)
    df['next_trade_date'] = df.groupby('security_id')['trade_date'].shift(-1)
    df['next_last_edate'] = df.groupby('security_id')['last_edate'].shift(-1)
    df['next_residual'] = df.groupby('security_id')['residual_iv'].shift(-1)
    df['next_implc_volatlty'] = df.groupby('security_id')['implc_volatlty'].shift(-1)
    df['next_baseline_iv'] = df.groupby('security_id')['baseline_iv'].shift(-1)
    df['next_remaining_time'] = df.groupby('security_id')['remaining_time'].shift(-1)
    df['next_exercise_price'] = df.groupby('security_id')['exercise_price'].shift(-1)
    df['next_M'] = df.groupby('security_id')['M'].shift(-1)
    return df


# =============================================================================
# 6. 模型加载
# =============================================================================

def load_xgb_model(model_path: str):
    """加载 XGBoost 模型（支持 .pkl 格式）。"""
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    return model


# =============================================================================
# 7. DataFrame -> ccQuant bars_dict 转换
# =============================================================================

def df_to_bars_dict(
    df: pd.DataFrame,
    exchange: Any = None,
) -> Tuple[Dict[str, List[Any]], List[str]]:
    """
    将期权截面 DataFrame 转换为 ccQuant BacktestingEngine 所需的 bars_dict。

    返回:
        bars_dict: {vt_symbol: [BarData, ...]}
        vt_symbols: 所有合约标识列表
    """
    # 延迟 import 避免循环依赖
    try:
        from ccquant.core.object import BarData
        from ccquant.core.constant import Exchange, Interval
    except ImportError:
        # 若 ccquant 未在路径中，提供降级提示
        raise ImportError(
            "无法导入 ccquant 模块。请确保运行目录在项目根目录 (ccQuant/) 且 ccquant 已安装。"
        )

    if exchange is None:
        exchange = Exchange.SSE

    bars_dict: Dict[str, List[Any]] = defaultdict(list)

    for security_id, group in df.groupby('security_id'):
        group = group.sort_values('trade_date')
        symbol = str(security_id)
        # vt_symbol 格式: symbol.exchange
        vt_symbol = f"{symbol}.{exchange.value}"

        for _, row in group.iterrows():
            trade_date = row['trade_date']
            if isinstance(trade_date, int):
                dt = datetime.strptime(str(trade_date), '%Y%m%d')
            else:
                dt = pd.to_datetime(trade_date)

            bar = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                interval=Interval.DAILY,
                open_price=float(row.get('open', 0.0)),
                high_price=float(row.get('high', 0.0)),
                low_price=float(row.get('low', 0.0)),
                close_price=float(row.get('close', 0.0)),
                volume=float(row.get('volume', 0.0)),
                open_interest=float(row.get('open_interest', 0.0)),
                gateway_name="OPTION",
            )
            bars_dict[vt_symbol].append(bar)

    vt_symbols = list(bars_dict.keys())
    return dict(bars_dict), vt_symbols


# =============================================================================
# 8. 一键数据准备 (供回测引擎调用)
# =============================================================================

def prepare_backtest_data(
    data_dir: str = 'strategy/data',
    model_path: str = 'strategy/data/output/baseline_xgb/model_abs_iv.pkl',
    use_mw_cache: bool = True,
) -> Dict[str, Any]:
    """
    一键准备回测所需的全部数据对象。

    返回字典包含:
        - 'df': 带特征的全量 DataFrame
        - 'forward_table': 远期价格表
        - 'daily_mw_data': M-W spline 字典
        - 'xgb_model': 加载的 XGBoost 模型
        - 'feature_cols': 模型特征列名列表
        - 'bars_dict': ccQuant bars 数据
        - 'vt_symbols': 所有合约 vt_symbol 列表
        - 'daily_groups': 按 trade_date 分组的 dict {date: DataFrame}
    """
    print("=" * 60)
    print("[prepare_backtest_data] 开始准备回测数据")
    print("=" * 60)

    raw_csv = os.path.join(data_dir, 'raw', '50etf_options.csv')
    mw_cache_path = os.path.join(data_dir, 'output', 'two_step_v2', 'mw_checkpoint_v2.pkl')
    forward_csv_path = os.path.join(data_dir, 'output', 'two_step_v2', 'forward_table.csv')

    # ------------------------------------------------------------------
    # Step 1: 加载原始数据 + forward_table
    # ------------------------------------------------------------------
    print("\n[Step 1/5] 加载原始数据与 forward_table")
    df_raw = load_raw_data(raw_csv)
    print(f"  - 原始记录数: {len(df_raw)}, 合约数: {df_raw['security_id'].nunique()}, 交易日: {df_raw['trade_date'].nunique()}")

    if os.path.exists(forward_csv_path):
        forward_table = pd.read_csv(forward_csv_path)
        print(f"  - 从缓存加载 forward_table: {len(forward_table)} 条")
    else:
        print("  - 计算 forward_table...")
        forward_table = build_forward_table(df_raw)
        os.makedirs(os.path.dirname(forward_csv_path), exist_ok=True)
        forward_table.to_csv(forward_csv_path, index=False)
        print(f"  - forward_table 已保存至 {forward_csv_path}")

    # ------------------------------------------------------------------
    # Step 2: M-W B-Spline + Residual (优先从 mw_checkpoint 加载)
    # ------------------------------------------------------------------
    print("\n[Step 2/5] M-W B-Spline 拟合与 Residual 计算")
    daily_mw_data: Dict = {}
    if use_mw_cache and os.path.exists(mw_cache_path):
        print(f"  - 从缓存加载: {mw_cache_path}")
        with open(mw_cache_path, 'rb') as f:
            cache = pickle.load(f)
        df = cache['df']
        daily_mw_data = cache['daily_mw_data']
        print(f"  - 加载完成: {len(df)} 条记录, {len(daily_mw_data)} 条 spline")
    else:
        print("  - 重新计算 M-W B-Spline (可能需要几分钟)...")
        df = df_raw.merge(
            forward_table[['trade_date', 'last_edate', 'F_implied', 'F']],
            on=['trade_date', 'last_edate'], how='left'
        )
        df, daily_mw_data = build_residual_series(df, forward_table)
        os.makedirs(os.path.dirname(mw_cache_path), exist_ok=True)
        with open(mw_cache_path, 'wb') as f:
            pickle.dump({'df': df, 'daily_mw_data': daily_mw_data}, f)
        print(f"  - 缓存已保存至 {mw_cache_path}")

    # ------------------------------------------------------------------
    # Step 3: 特征工程
    # ------------------------------------------------------------------
    print("\n[Step 3/5] 特征工程")
    df = build_features(df)
    print(f"  - 特征列数: {len([c for c in FEATURE_COLS if c in df.columns])}/{len(FEATURE_COLS)}")

    # ------------------------------------------------------------------
    # Step 4: next-day 列 (策略A需要)
    # ------------------------------------------------------------------
    print("\n[Step 4/5] 构造 next-day 列")
    df = build_target(df)
    # 剔除没有次日数据的最后一行（每个合约）
    df = df.dropna(subset=['next_trade_date']).copy()
    print(f"  - 有效样本数: {len(df)}")

    # ------------------------------------------------------------------
    # Step 5: 加载模型 + 构造 bars_dict
    # ------------------------------------------------------------------
    print("\n[Step 5/5] 加载模型与构造 bars_dict")
    xgb_model = load_xgb_model(model_path)
    print(f"  - 模型已加载: {type(xgb_model).__name__}")

    bars_dict, vt_symbols = df_to_bars_dict(df)
    print(f"  - bars_dict: {len(vt_symbols)} 个合约")

    # 按天分组（加速策略 on_bars 查询）
    daily_groups = {date: day_df.copy() for date, day_df in df.groupby('trade_date')}
    print(f"  - daily_groups: {len(daily_groups)} 个交易日")

    print("\n" + "=" * 60)
    print("[prepare_backtest_data] 数据准备完成")
    print("=" * 60)

    return {
        'df': df,
        'forward_table': forward_table,
        'daily_mw_data': daily_mw_data,
        'xgb_model': xgb_model,
        'feature_cols': FEATURE_COLS,
        'bars_dict': bars_dict,
        'vt_symbols': vt_symbols,
        'daily_groups': daily_groups,
    }
