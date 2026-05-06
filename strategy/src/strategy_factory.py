# -*- coding: utf-8 -*-
"""
策略工厂 — 统一入口

提供：
  1. prepare_engine_data()  — 预加载全部数据对象
  2. create_strategy()      — 根据名称获取配置好的策略类

使用示例:
    from strategy.src.strategy_factory import prepare_engine_data, create_strategy

    # 方式1：预加载数据后传给工厂（推荐，避免重复IO）
    data_bundle = prepare_engine_data(data_dir='strategy/data')
    StrategyClass = create_strategy('A', {
        'data_dir': 'strategy/data',
        **data_bundle,  # 注入预加载对象
    })
    engine.add_strategy(StrategyClass, {'fixed_size': 1})

    # 方式2：让策略内部自行加载数据（简单但慢）
    StrategyClass = create_strategy('B', {'data_dir': 'strategy/data'})
    engine.add_strategy(StrategyClass, {})
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


# =============================================================================
# 1. 预加载数据（供外部一次性调用）
# =============================================================================

def prepare_engine_data(
    data_dir: str = 'strategy/data',
    model_path: str = 'strategy/data/output/baseline_xgb/model_abs_iv.pkl',
) -> Dict[str, Any]:
    """
    一键预加载回测所需的全部数据对象。

    返回字典包含:
        df, forward_table, daily_mw_data, xgb_model, feature_cols,
        bars_dict, vt_symbols, daily_groups
    """
    from .core.data_loader import prepare_backtest_data
    return prepare_backtest_data(data_dir=data_dir, model_path=model_path, use_mw_cache=True)


# =============================================================================
# 2. 策略工厂
# =============================================================================

def create_strategy(name: str, config: Dict[str, Any]) -> type:
    """
    根据策略名称创建配置好的策略类。

    参数:
        name: 'A' | 'B' | 'C'
        config: 配置字典，可包含以下键:
            - data_dir: 数据根目录 (默认 'strategy/data')
            - model_path: XGBoost模型路径 (默认 baseline_xgb/model_abs_iv.pkl)
            - fixed_size: 每腿手数 (默认 1)
            - signal_threshold: 策略A信号阈值 (默认 0.003)
            - zscore_threshold: 策略B/C Z-Score阈值 (默认 1.0)
            - long_pct: 多头分位比例 (默认 0.10)
            - short_pct: 空头分位比例 (默认 0.10)
            - 预加载对象: df, forward_table, daily_mw_data, xgb_model,
              feature_cols, bars_dict, vt_symbols, daily_groups

    返回:
        策略类 (继承自 IvPredictStrategy)，可直接传给 engine.add_strategy()

    示例:
        StrategyClass = create_strategy('A', {'fixed_size': 2, 'signal_threshold': 0.005})
        engine.add_strategy(StrategyClass, {})
    """
    if name not in ('A', 'B', 'C'):
        raise ValueError(f"name 必须是 'A'/'B'/'C'，当前: {name}")

    from .strategies.strategy_adapter import IvPredictStrategy

    # 默认配置
    defaults = {
        'strategy_type': name,
        'data_dir': 'strategy/data',
        'model_path': 'strategy/data/output/baseline_xgb/model_abs_iv.pkl',
        'fixed_size': 1,
        'signal_threshold': 0.003,
        'zscore_threshold': 1.0,
        'long_pct': 0.10,
        'short_pct': 0.10,
    }

    # 用用户配置覆盖默认值
    merged = {**defaults, **config}
    merged['strategy_type'] = name  # 强制锁定

    # 若 config 中包含预加载的大对象，注入类级缓存，避免 on_init 重复IO
    preloaded_keys = [
        'df', 'forward_table', 'daily_mw_data', 'xgb_model',
        'feature_cols', 'bars_dict', 'vt_symbols', 'daily_groups',
    ]
    if any(k in config for k in preloaded_keys):
        cache_key = f"{merged['data_dir']}:{merged['model_path']}"
        cache = {}
        for k in preloaded_keys:
            if k in config:
                cache[k] = config[k]
        # 补全缺失项（若用户只传了一部分）
        if cache:
            IvPredictStrategy._data_cache[cache_key] = cache

    # 构造闭包类：将非数据类配置项注入为类属性，作为默认值
    class _ConfiguredStrategy(IvPredictStrategy):
        pass

    for key, value in merged.items():
        if key in preloaded_keys:
            continue
        if not hasattr(_ConfiguredStrategy, key):
            setattr(_ConfiguredStrategy, key, value)

    # 类名改为可读形式，方便日志和调试
    _ConfiguredStrategy.__name__ = f"IvPredictStrategy{name}"
    _ConfiguredStrategy.__qualname__ = f"IvPredictStrategy{name}"

    return _ConfiguredStrategy


# =============================================================================
# 3. 便捷函数：同时返回策略类和完整数据包
# =============================================================================

def create_strategy_with_data(
    name: str,
    data_dir: str = 'strategy/data',
    model_path: str = 'strategy/data/output/baseline_xgb/model_abs_iv.pkl',
    **overrides: Any,
) -> Tuple[type, Dict[str, Any]]:
    """
    一次性加载数据并创建策略类。

    返回:
        (strategy_class, data_bundle)

    使用示例:
        StrategyClass, data = create_strategy_with_data('A')
        engine.add_strategy(StrategyClass, {'fixed_size': 1})
        engine.load_data(data['bars_dict'])
    """
    data_bundle = prepare_engine_data(data_dir=data_dir, model_path=model_path)
    config = {**data_bundle, **overrides}
    strategy_class = create_strategy(name, config)
    return strategy_class, data_bundle
