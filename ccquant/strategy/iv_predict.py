"""
IV Predict 策略 — 适配 ccQuant 回测引擎

将 strategy/src/ 下的 A/B/C 信号模块接入 ccquant.strategy 体系。
策略在 on_init 时从 strategy/data/ 加载数据、模型和预计算对象。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ------------------------------------------------------------------
# 确保项目根目录及 strategy/src/ 在 sys.path 中
# （strategy.src.* 使用绝对导入 src.xxx，需要 strategy/src/ 在路径中）
# ------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_SRC_ROOT = _PROJECT_ROOT / "strategy" / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import pandas as pd

from ccquant.backtest.template import StrategyTemplate


class IvPredictStrategy(StrategyTemplate):
    """
    IV Predict 统一适配器（A/B/C 三策略合一）。

    参数说明:
        strategy_type: 'A' | 'B' | 'C'
        data_dir: 数据根目录 (默认 'strategy/data')
        model_path: XGBoost 模型路径
        fixed_size: 每腿固定手数 (默认 1)
        signal_threshold: 策略A信号阈值 (默认 0.003)
        zscore_threshold: 策略B/C Z-Score阈值 (默认 1.0)
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

        if self.strategy_type not in ('A', 'B', 'C'):
            raise ValueError(f"strategy_type 必须是 'A'/'B'/'C'，当前: {self.strategy_type}")

        # 加载数据（带缓存）
        cache_key = f"{self.data_dir}:{self.model_path}"
        if cache_key not in IvPredictStrategy._data_cache:
            from strategy.src.core.data_loader import prepare_backtest_data
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
        if not self.trading:
            return

        dt = self.engine.datetime
        date_int = int(dt.strftime('%Y%m%d'))

        if date_int == self.current_date:
            return
        self.current_date = date_int

        df_day = self.daily_groups.get(date_int)
        if df_day is None or len(df_day) == 0:
            self._flatten_all(bars)
            self.long_count = 0
            self.short_count = 0
            return

        signal_df, long_df, short_df = self._generate_signals(df_day)

        target_long: Set[str] = set()
        target_short: Set[str] = set()

        if len(long_df) > 0:
            for sid in long_df['security_id'].astype(str):
                target_long.add(self._to_vt_symbol(sid))

        if len(short_df) > 0:
            for sid in short_df['security_id'].astype(str):
                target_short.add(self._to_vt_symbol(sid))

        self._rebalance(bars, target_long, target_short)

        self.long_count = len(target_long)
        self.short_count = len(target_short)
        self.write_log(
            f"{date_int} 调仓完成 | Long={self.long_count} | Short={self.short_count}"
        )

    def _generate_signals(self, df_day: pd.DataFrame):
        st = self.strategy_type

        if st == 'A':
            from strategy.src.strategies.strategy_a_residual import generate_signals
            return generate_signals(
                df_day, self.xgb_model, self.feature_cols,
                self.daily_mw_data, self.forward_table,
                signal_threshold=self.signal_threshold,
                long_pct=self.long_pct, short_pct=self.short_pct,
            )

        if st == 'B':
            from strategy.src.strategies.strategy_b_section import generate_signals
            return generate_signals(
                df_day,
                zscore_threshold=self.zscore_threshold,
                long_pct=self.long_pct, short_pct=self.short_pct,
            )

        # 'C'
        from strategy.src.strategies.strategy_c_doublesort import generate_signals
        signal_df, long_df, short_df, stats = generate_signals(
            df_day,
            zscore_threshold=max(self.zscore_threshold, 1.5),
            long_pct=self.long_pct, short_pct=self.short_pct,
        )
        if stats:
            self.write_log(
                f"  [Stats] 高估池={stats.get('n_overvalued_total', 0)} "
                f"低估池={stats.get('n_undervalued_total', 0)} "
                f"多头={stats.get('n_long_passed', 0)} 空头={stats.get('n_short_passed', 0)}"
            )
        return signal_df, long_df, short_df

    def _to_vt_symbol(self, security_id: str) -> str:
        return f"{security_id}.SSE"

    def _flatten_all(self, bars: Dict[str, Any]) -> None:
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
        size = float(self.fixed_size)

        # 平仓
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

        # 空头方向调整
        for vt_symbol in target_short:
            bar = bars.get(vt_symbol)
            if not bar:
                continue
            pos = self.get_pos(vt_symbol)
            if pos > 0:
                self.sell(vt_symbol, bar.close_price, pos)
                self.short(vt_symbol, bar.close_price, size)
            elif pos == 0:
                self.short(vt_symbol, bar.close_price, size)

        # 多头方向调整
        for vt_symbol in target_long:
            bar = bars.get(vt_symbol)
            if not bar:
                continue
            pos = self.get_pos(vt_symbol)
            if pos < 0:
                self.cover(vt_symbol, bar.close_price, abs(pos))
                self.buy(vt_symbol, bar.close_price, size)
            elif pos == 0:
                self.buy(vt_symbol, bar.close_price, size)

    def on_order(self, order: Any) -> None:
        pass

    def on_trade(self, trade: Any) -> None:
        pass


# 便捷别名，方便 get_strategy_class() 直接引用
class IvPredictStrategyA(IvPredictStrategy):
    """策略A：XGBoost残差变化驱动（原始模型）"""
    pass


class IvPredictStrategyAEnhanced(IvPredictStrategy):
    """策略A-Enhanced：XGBoost残差变化驱动（Diffusion增强模型）

    使用 Diffusion 增强数据训练的模型，参数已针对增强模型特性调整：
      - signal_threshold 放宽（0.001 vs 0.003）以补偿增强模型残差幅度变化
      - long_pct / short_pct 扩大（0.15 vs 0.10）以捕获更多交易机会
    """

    parameters = [
        {'name': 'strategy_type', 'displayName': '策略类型', 'type': 'select', 'default': 'A', 'options': ['A', 'B', 'C']},
        {'name': 'data_dir', 'displayName': '数据目录', 'type': 'str', 'default': 'strategy/data'},
        {'name': 'model_path', 'displayName': '模型路径', 'type': 'str', 'default': 'strategy/data/output/baseline_xgb/model_abs_iv_enhanced.pkl'},
        {'name': 'fixed_size', 'displayName': '每腿手数', 'type': 'number', 'default': 1},
        {'name': 'signal_threshold', 'displayName': '信号阈值', 'type': 'number', 'default': 0.001},
        {'name': 'zscore_threshold', 'displayName': 'Z-Score阈值', 'type': 'number', 'default': 1.0},
        {'name': 'long_pct', 'displayName': '多头比例', 'type': 'number', 'default': 0.15},
        {'name': 'short_pct', 'displayName': '空头比例', 'type': 'number', 'default': 0.15},
    ]


class IvPredictStrategyB(IvPredictStrategy):
    """策略B：B-Spline截面偏差驱动"""
    pass


class IvPredictStrategyC(IvPredictStrategy):
    """策略C：Double-Sort双信号组合"""
    pass
