# -*- coding: utf-8 -*-
"""
IV Predict 策略适配器 — 将函数式 A/B/C 信号模块包装为 ccQuant StrategyTemplate

使用方式:
    from strategy.src.strategies.strategy_adapter import IvPredictStrategy
    engine.add_strategy(IvPredictStrategy, {
        'strategy_type': 'A',
        'data_dir': 'strategy/data',
        'model_path': 'strategy/data/output/baseline_xgb/model_abs_iv.pkl',
        'fixed_size': 1,
    })
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

import pandas as pd

# ccQuant 策略基类
try:
    from ccquant.backtest.template import StrategyTemplate
except ImportError:
    # 降级保护：若运行环境未安装 ccquant，提供一个虚拟基类用于类型检查/单测
    class StrategyTemplate:  # type: ignore[no-redef]
        parameters: List[Any] = []
        variables: List[Any] = []
        def __init__(self, engine, strategy_name, vt_symbols, setting): ...
        def on_init(self): pass
        def on_start(self): pass
        def on_stop(self): pass
        def on_bars(self, bars): pass
        def on_order(self, order): pass
        def on_trade(self, trade): pass
        def buy(self, vt_symbol, price, volume, stop=False, lock=False, net=False): return []  # type: ignore
        def sell(self, vt_symbol, price, volume, stop=False, lock=False, net=False): return []  # type: ignore
        def short(self, vt_symbol, price, volume, stop=False, lock=False, net=False): return []  # type: ignore
        def cover(self, vt_symbol, price, volume, stop=False, lock=False, net=False): return []  # type: ignore
        def get_pos(self, vt_symbol): return 0  # type: ignore
        def write_log(self, msg): pass  # type: ignore


class IvPredictStrategy(StrategyTemplate):
    """
    IV Predict 策略统一适配器。

    参数说明:
        strategy_type: 'A' | 'B' | 'C'
        data_dir: 数据根目录 (默认 'strategy/data')
        model_path: XGBoost 模型路径 (策略A/C需要)
        fixed_size: 每腿固定手数 (默认 1)
        signal_threshold: 策略A信号阈值 (默认 0.003)
        zscore_threshold: 策略B/C Z-Score阈值 (默认 1.0, 策略C默认内部用1.5)
        long_pct: 多头分位比例 (默认 0.10)
        short_pct: 空头分位比例 (默认 0.10)
    """

    parameters = [
        {'name': 'strategy_type', 'displayName': '策略类型', 'type': 'select', 'default': 'A', 'options': ['A', 'B', 'C']},
        {'name': 'data_dir', 'displayName': '数据目录', 'type': 'str', 'default': 'strategy/data'},
        {'name': 'model_path', 'displayName': '模型路径', 'type': 'str', 'default': 'strategy/data/output/baseline_xgb/model_abs_iv.pkl'},
        {'name': 'fixed_size', 'displayName': '每腿手数', 'type': 'number', 'default': 1},
        {'name': 'signal_threshold', 'displayName': '信号阈值', 'type': 'number', 'default': 0.003},
        {'name': 'zscore_threshold', 'displayName': 'Z-Score阈值', 'type': 'number', 'default': 1.0},
        {'name': 'long_pct', 'displayName': '多头比例', 'type': 'number', 'default': 0.10},
        {'name': 'short_pct', 'displayName': '空头比例', 'type': 'number', 'default': 0.10},
    ]
    variables = ['current_date', 'long_count', 'short_count']

    # 类级缓存，避免参数优化时重复加载大数据
    _data_cache: Dict[str, Any] = {}

    def on_init(self) -> None:
        """初始化：加载数据、模型、预计算每日分组。"""
        self.current_date: Optional[int] = None
        self.long_count: int = 0
        self.short_count: int = 0

        # 参数校验
        if self.strategy_type not in ('A', 'B', 'C'):
            raise ValueError(f"strategy_type 必须是 'A'/'B'/'C'，当前: {self.strategy_type}")

        # 加载数据（带缓存）
        cache_key = f"{self.data_dir}:{self.model_path}"
        if cache_key not in IvPredictStrategy._data_cache:
            from ..core.data_loader import prepare_backtest_data
            IvPredictStrategy._data_cache[cache_key] = prepare_backtest_data(
                data_dir=self.data_dir,
                model_path=self.model_path,
                use_mw_cache=True,
            )

        self._data = IvPredictStrategy._data_cache[cache_key]
        self.daily_groups: Dict[int, pd.DataFrame] = self._data['daily_groups']
        self.forward_table: pd.DataFrame = self._data['forward_table']
        self.daily_mw_data: Dict = self._data['daily_mw_data']
        self.xgb_model: Any = self._data['xgb_model']
        self.feature_cols: List[str] = self._data['feature_cols']

        self.write_log(
            f"IV Predict 策略初始化完成 | 类型={self.strategy_type} | "
            f"交易日数={len(self.daily_groups)} | 特征数={len(self.feature_cols)}"
        )

    def on_start(self) -> None:
        self.write_log("策略启动")

    def on_stop(self) -> None:
        self.write_log("策略停止")

    def on_bars(self, bars: Dict[str, Any]) -> None:
        """
        每日调仓逻辑：
          1. 获取当前日期对应的截面数据
          2. 调用对应策略生成 long_df / short_df
          3. 将目标持仓与当前持仓对齐（先平后开）
        """
        if not self.trading:
            return

        dt = self.engine.datetime
        date_int = int(dt.strftime('%Y%m%d'))

        if date_int == self.current_date:
            # 同一自然日只调仓一次（日频策略）
            return
        self.current_date = date_int

        # 查询当日数据
        df_day = self.daily_groups.get(date_int)
        if df_day is None or len(df_day) == 0:
            # 无数据日：平掉所有持仓
            self._flatten_all(bars)
            self.long_count = 0
            self.short_count = 0
            return

        # 生成信号
        signal_df, long_df, short_df = self._generate_signals(df_day)

        # 转换为 vt_symbol 集合
        target_long: Set[str] = set()
        target_short: Set[str] = set()

        if len(long_df) > 0:
            for sid in long_df['security_id'].astype(str):
                target_long.add(self._to_vt_symbol(sid))

        if len(short_df) > 0:
            for sid in short_df['security_id'].astype(str):
                target_short.add(self._to_vt_symbol(sid))

        # 调仓执行
        self._rebalance(bars, target_long, target_short)

        self.long_count = len(target_long)
        self.short_count = len(target_short)
        self.write_log(
            f"{date_int} 调仓完成 | Long={self.long_count} | Short={self.short_count}"
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _generate_signals(self, df_day: pd.DataFrame):
        """根据 strategy_type 调用对应的信号生成函数。"""
        st = self.strategy_type

        if st == 'A':
            from .strategy_a_residual import generate_signals
            signal_df, long_df, short_df = generate_signals(
                df_day,
                self.xgb_model,
                self.feature_cols,
                self.daily_mw_data,
                self.forward_table,
                signal_threshold=self.signal_threshold,
                long_pct=self.long_pct,
                short_pct=self.short_pct,
            )
            return signal_df, long_df, short_df

        elif st == 'B':
            from .strategy_b_section import generate_signals
            signal_df, long_df, short_df = generate_signals(
                df_day,
                zscore_threshold=self.zscore_threshold,
                long_pct=self.long_pct,
                short_pct=self.short_pct,
            )
            return signal_df, long_df, short_df

        else:  # 'C'
            from .strategy_c_doublesort import generate_signals
            signal_df, long_df, short_df, filter_stats = generate_signals(
                df_day,
                self.xgb_model,
                self.feature_cols,
                self.daily_mw_data,
                self.forward_table,
                zscore_threshold=max(self.zscore_threshold, 1.5),  # 策略C默认需要更高阈值
                long_pct=self.long_pct,
                short_pct=self.short_pct,
            )
            # 记录过滤统计到日志（可选）
            if filter_stats:
                self.write_log(
                    f"  [FilterStats] 高估池={filter_stats.get('n_overvalued_total', 0)} "
                    f"低估池={filter_stats.get('n_undervalued_total', 0)} "
                    f"方向一致率={filter_stats.get('direction_agreement_rate', 0):.2%}"
                )
            return signal_df, long_df, short_df

    def _to_vt_symbol(self, security_id: str) -> str:
        """security_id -> vt_symbol (如 10000001.SH -> 10000001.SH.SSE)。"""
        return f"{security_id}.SSE"

    def _flatten_all(self, bars: Dict[str, Any]) -> None:
        """平掉所有持仓。"""
        for vt_symbol, pos in list(self.pos.items()):
            if pos == 0:
                continue
            bar = bars.get(vt_symbol)
            if not bar:
                continue
            if pos > 0:
                self.sell(vt_symbol, bar.close_price, pos)
            else:
                self.cover(vt_symbol, bar.close_price, abs(pos))

    def _rebalance(
        self,
        bars: Dict[str, Any],
        target_long: Set[str],
        target_short: Set[str],
    ) -> None:
        """
        将当前持仓调整至目标持仓。
        先处理所有平仓，再处理开仓，避免资金/保证金冲突。
        """
        size = float(self.fixed_size)

        # Step 1: 平仓（不在目标持仓中的合约）
        for vt_symbol, pos in list(self.pos.items()):
            if pos == 0:
                continue
            bar = bars.get(vt_symbol)
            if not bar:
                continue

            should_long = vt_symbol in target_long
            should_short = vt_symbol in target_short

            if pos > 0 and not should_long:
                self.sell(vt_symbol, bar.close_price, pos)
            elif pos < 0 and not should_short:
                self.cover(vt_symbol, bar.close_price, abs(pos))

        # Step 2: 空头方向调整（当前空头但应多头，或空头手数不对）
        for vt_symbol in target_short:
            bar = bars.get(vt_symbol)
            if not bar:
                continue
            pos = self.get_pos(vt_symbol)
            if pos > 0:
                # 先平多
                self.sell(vt_symbol, bar.close_price, pos)
                self.short(vt_symbol, bar.close_price, size)
            elif pos == 0:
                self.short(vt_symbol, bar.close_price, size)
            # 若已在空头且手数相同，无需操作（简化：不处理加仓/减仓）

        # Step 3: 多头方向调整
        for vt_symbol in target_long:
            bar = bars.get(vt_symbol)
            if not bar:
                continue
            pos = self.get_pos(vt_symbol)
            if pos < 0:
                # 先平空
                self.cover(vt_symbol, bar.close_price, abs(pos))
                self.buy(vt_symbol, bar.close_price, size)
            elif pos == 0:
                self.buy(vt_symbol, bar.close_price, size)

    def on_order(self, order: Any) -> None:
        pass

    def on_trade(self, trade: Any) -> None:
        pass
