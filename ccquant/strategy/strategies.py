"""
ccQuant 期权策略集合
包含常用期权策略的实现
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ccquant.strategy.template import OptionStrategyTemplate
from ccquant.backtest.engine import OptionBacktestEngine
from ccquant.option.pricing import black_scholes_greeks


class BullCallSpreadStrategy(OptionStrategyTemplate):
    """
    牛市看涨价差策略
    买入低行权价Call，卖出高行权价Call
    """

    author = "ccQuant"
    strategy_name = "BullCallSpread"

    parameters = [
        {
            "name": "long_strike_offset",
            "type": "float",
            "default": -0.05,
            "min": -0.2,
            "max": 0,
            "step": 0.01,
            "label": "买入行权价偏移",
            "description": "相对于标的价格的偏移比例（负数为虚值）"
        },
        {
            "name": "short_strike_offset",
            "type": "float",
            "default": 0.05,
            "min": 0,
            "max": 0.2,
            "step": 0.01,
            "label": "卖出行权价偏移",
            "description": "相对于标的价格的偏移比例（正数为虚值）"
        },
        {
            "name": "quantity",
            "type": "int",
            "default": 1,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "手数",
            "description": "每腿交易手数"
        },
    ]

    def __init__(self, engine: OptionBacktestEngine, params: Optional[Dict[str, Any]] = None):
        super().__init__(engine, params)
        self.long_strike_offset = self.get_param("long_strike_offset", -0.05)
        self.short_strike_offset = self.get_param("short_strike_offset", 0.05)
        self.quantity = self.get_param("quantity", 1)

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log("牛市看涨价差策略初始化")
        self.write_log(f"参数: 买入偏移={self.long_strike_offset}, 卖出偏移={self.short_strike_offset}")

        # 获取当前标的价格
        underlying_price = self.get_underlying_price()
        if not underlying_price:
            self.write_log("错误: 无法获取标的价格")
            return

        # 计算目标行权价
        long_strike = underlying_price * (1 + self.long_strike_offset)
        short_strike = underlying_price * (1 + self.short_strike_offset)

        # 选择最接近的合约
        long_call = self.select_contract("CALL", long_strike, 0)
        short_call = self.select_contract("CALL", short_strike, 0)

        if long_call and short_call:
            # 构建价差组合
            self.buy(long_call.vt_symbol, self.quantity)
            self.sell(short_call.vt_symbol, self.quantity)
            self.write_log(f"建立牛市看涨价差: 买入{long_call.option_strike}, 卖出{short_call.option_strike}")
        else:
            self.write_log("错误: 无法找到合适的合约")


class BearPutSpreadStrategy(OptionStrategyTemplate):
    """
    熊市看跌价差策略
    买入高行权价Put，卖出低行权价Put
    """

    author = "ccQuant"
    strategy_name = "BearPutSpread"

    parameters = [
        {
            "name": "long_strike_offset",
            "type": "float",
            "default": 0.05,
            "min": 0,
            "max": 0.2,
            "step": 0.01,
            "label": "买入行权价偏移",
            "description": "相对于标的价格的偏移比例"
        },
        {
            "name": "short_strike_offset",
            "type": "float",
            "default": -0.05,
            "min": -0.2,
            "max": 0,
            "step": 0.01,
            "label": "卖出行权价偏移",
            "description": "相对于标的价格的偏移比例"
        },
        {
            "name": "quantity",
            "type": "int",
            "default": 1,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "手数",
            "description": "每腿交易手数"
        },
    ]

    def __init__(self, engine: OptionBacktestEngine, params: Optional[Dict[str, Any]] = None):
        super().__init__(engine, params)
        self.long_strike_offset = self.get_param("long_strike_offset", 0.05)
        self.short_strike_offset = self.get_param("short_strike_offset", -0.05)
        self.quantity = self.get_param("quantity", 1)

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log("熊市看跌价差策略初始化")

        underlying_price = self.get_underlying_price()
        if not underlying_price:
            return

        long_strike = underlying_price * (1 + self.long_strike_offset)
        short_strike = underlying_price * (1 + self.short_strike_offset)

        long_put = self.select_contract("PUT", long_strike, 0)
        short_put = self.select_contract("PUT", short_strike, 0)

        if long_put and short_put:
            self.buy(long_put.vt_symbol, self.quantity)
            self.sell(short_put.vt_symbol, self.quantity)
            self.write_log(f"建立熊市看跌价差: 买入{long_put.option_strike}, 卖出{short_put.option_strike}")


class StrangleStrategy(OptionStrategyTemplate):
    """
    宽跨式组合策略
    同时买入不同行权价的Call和Put（都虚值）
    """

    author = "ccQuant"
    strategy_name = "Strangle"

    parameters = [
        {
            "name": "call_strike_offset",
            "type": "float",
            "default": 0.05,
            "min": 0.02,
            "max": 0.15,
            "step": 0.01,
            "label": "Call行权价偏移",
            "description": "Call虚值程度"
        },
        {
            "name": "put_strike_offset",
            "type": "float",
            "default": -0.05,
            "min": -0.15,
            "max": -0.02,
            "step": 0.01,
            "label": "Put行权价偏移",
            "description": "Put虚值程度"
        },
        {
            "name": "quantity",
            "type": "int",
            "default": 1,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "手数",
            "description": "每腿交易手数"
        },
        {
            "name": "profit_target",
            "type": "float",
            "default": 0.5,
            "min": 0.1,
            "max": 1.0,
            "step": 0.1,
            "label": "止盈比例",
            "description": "权利金收入达到此比例时平仓"
        },
    ]

    def __init__(self, engine: OptionBacktestEngine, params: Optional[Dict[str, Any]] = None):
        super().__init__(engine, params)
        self.call_strike_offset = self.get_param("call_strike_offset", 0.05)
        self.put_strike_offset = self.get_param("put_strike_offset", -0.05)
        self.quantity = self.get_param("quantity", 1)
        self.profit_target = self.get_param("profit_target", 0.5)

        self.entry_premium = 0.0
        self.strangle_opened = False

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log("宽跨式策略初始化")

        underlying_price = self.get_underlying_price()
        if not underlying_price:
            return

        call_strike = underlying_price * (1 + self.call_strike_offset)
        put_strike = underlying_price * (1 + self.put_strike_offset)

        call = self.select_contract("CALL", call_strike, 0)
        put = self.select_contract("PUT", put_strike, 0)

        if call and put:
            # 买入宽跨式
            self.buy(call.vt_symbol, self.quantity)
            self.buy(put.vt_symbol, self.quantity)

            # 记录入场权利金
            call_price = self.get_contract_price(call.vt_symbol)
            put_price = self.get_contract_price(put.vt_symbol)
            self.entry_premium = (call_price + put_price) * self.quantity

            self.strangle_opened = True
            self.write_log(f"建立宽跨式: Call@{call.option_strike}, Put@{put.option_strike}, 权利金={self.entry_premium:.2f}")

    def on_bar(self, bar: Any) -> None:
        """K线更新"""
        if not self.strangle_opened:
            return

        # 计算当前组合价值
        portfolio_value = 0.0
        for leg in self.engine.portfolio.legs.values():
            price = self.get_contract_price(leg.vt_symbol)
            portfolio_value += price * leg.quantity * (1 if leg.is_long else -1)

        # 计算盈亏比例
        if self.entry_premium > 0:
            pnl_ratio = (portfolio_value - self.entry_premium) / self.entry_premium

            # 止盈
            if pnl_ratio >= self.profit_target:
                self.write_log(f"达到止盈目标 {pnl_ratio:.1%}，平仓")
                self.close_all_positions()
                self.strangle_opened = False

            # 止损（权利金损失50%）
            elif pnl_ratio <= -0.5:
                self.write_log(f"触发止损 {pnl_ratio:.1%}，平仓")
                self.close_all_positions()
                self.strangle_opened = False


class ButterflySpreadStrategy(OptionStrategyTemplate):
    """
    蝶式价差策略
    买入1个低行权价Call，卖出2个中行权价Call，买入1个高行权价Call
    """

    author = "ccQuant"
    strategy_name = "ButterflySpread"

    parameters = [
        {
            "name": "center_strike_offset",
            "type": "float",
            "default": 0.0,
            "min": -0.1,
            "max": 0.1,
            "step": 0.01,
            "label": "中心行权价偏移",
            "description": "相对于标的价格的偏移"
        },
        {
            "name": "wing_width",
            "type": "float",
            "default": 0.05,
            "min": 0.02,
            "max": 0.1,
            "step": 0.01,
            "label": "翅膀宽度",
            "description": "两翼与中心的距离"
        },
        {
            "name": "quantity",
            "type": "int",
            "default": 1,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "手数",
            "description": "每腿交易手数"
        },
    ]

    def __init__(self, engine: OptionBacktestEngine, params: Optional[Dict[str, Any]] = None):
        super().__init__(engine, params)
        self.center_strike_offset = self.get_param("center_strike_offset", 0.0)
        self.wing_width = self.get_param("wing_width", 0.05)
        self.quantity = self.get_param("quantity", 1)

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log("蝶式价差策略初始化")

        underlying_price = self.get_underlying_price()
        if not underlying_price:
            return

        center = underlying_price * (1 + self.center_strike_offset)
        low = center * (1 - self.wing_width)
        high = center * (1 + self.wing_width)

        low_call = self.select_contract("CALL", low, 0)
        center_call = self.select_contract("CALL", center, 0)
        high_call = self.select_contract("CALL", high, 0)

        if low_call and center_call and high_call:
            # 买入蝶式: +1低 -2中 +1高
            self.buy(low_call.vt_symbol, self.quantity)
            self.sell(center_call.vt_symbol, self.quantity * 2)
            self.buy(high_call.vt_symbol, self.quantity)
            self.write_log(f"建立蝶式价差: {low_call.option_strike}/{center_call.option_strike}/{high_call.option_strike}")


class CalendarSpreadStrategy(OptionStrategyTemplate):
    """
    日历价差策略
    卖出近月Call，买入远月Call（同一看涨行权价）
    """

    author = "ccQuant"
    strategy_name = "CalendarSpread"

    parameters = [
        {
            "name": "strike_offset",
            "type": "float",
            "default": 0.0,
            "min": -0.1,
            "max": 0.1,
            "step": 0.01,
            "label": "行权价偏移",
            "description": "相对于标的价格的偏移"
        },
        {
            "name": "near_month",
            "type": "int",
            "default": 0,
            "min": 0,
            "max": 2,
            "step": 1,
            "label": "近月序号",
            "description": "0=当月, 1=次月"
        },
        {
            "name": "far_month",
            "type": "int",
            "default": 1,
            "min": 1,
            "max": 3,
            "step": 1,
            "label": "远月序号",
            "description": "1=次月, 2=季月"
        },
        {
            "name": "quantity",
            "type": "int",
            "default": 1,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "手数",
            "description": "每腿交易手数"
        },
    ]

    def __init__(self, engine: OptionBacktestEngine, params: Optional[Dict[str, Any]] = None):
        super().__init__(engine, params)
        self.strike_offset = self.get_param("strike_offset", 0.0)
        self.near_month = self.get_param("near_month", 0)
        self.far_month = self.get_param("far_month", 1)
        self.quantity = self.get_param("quantity", 1)

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log("日历价差策略初始化")

        underlying_price = self.get_underlying_price()
        if not underlying_price:
            return

        target_strike = underlying_price * (1 + self.strike_offset)

        # 选择不同到期月的合约
        near_call = self.select_contract("CALL", target_strike, self.near_month)
        far_call = self.select_contract("CALL", target_strike, self.far_month)

        if near_call and far_call:
            # 卖出近月，买入远月
            self.sell(near_call.vt_symbol, self.quantity)
            self.buy(far_call.vt_symbol, self.quantity)
            self.write_log(f"建立日历价差: 卖出{near_call.option_expiry.strftime('%Y%m')} {near_call.option_strike}, 买入{far_call.option_expiry.strftime('%Y%m')} {far_call.option_strike}")


class RatioSpreadStrategy(OptionStrategyTemplate):
    """
    比率价差策略
    买入1个低行权价Call，卖出N个高行权价Call
    """

    author = "ccQuant"
    strategy_name = "RatioSpread"

    parameters = [
        {
            "name": "long_strike_offset",
            "type": "float",
            "default": 0.0,
            "min": -0.1,
            "max": 0.05,
            "step": 0.01,
            "label": "买入行权价偏移",
            "description": "相对于标的价格的偏移"
        },
        {
            "name": "short_strike_offset",
            "type": "float",
            "default": 0.05,
            "min": 0.02,
            "max": 0.15,
            "step": 0.01,
            "label": "卖出行权价偏移",
            "description": "相对于标的价格的偏移"
        },
        {
            "name": "ratio",
            "type": "int",
            "default": 2,
            "min": 1,
            "max": 5,
            "step": 1,
            "label": "比率",
            "description": "卖出数量/买入数量"
        },
        {
            "name": "quantity",
            "type": "int",
            "default": 1,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "基础手数",
            "description": "买入腿的手数"
        },
    ]

    def __init__(self, engine: OptionBacktestEngine, params: Optional[Dict[str, Any]] = None):
        super().__init__(engine, params)
        self.long_strike_offset = self.get_param("long_strike_offset", 0.0)
        self.short_strike_offset = self.get_param("short_strike_offset", 0.05)
        self.ratio = self.get_param("ratio", 2)
        self.quantity = self.get_param("quantity", 1)

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log(f"比率价差策略初始化 (1:{self.ratio})")

        underlying_price = self.get_underlying_price()
        if not underlying_price:
            return

        long_strike = underlying_price * (1 + self.long_strike_offset)
        short_strike = underlying_price * (1 + self.short_strike_offset)

        long_call = self.select_contract("CALL", long_strike, 0)
        short_call = self.select_contract("CALL", short_strike, 0)

        if long_call and short_call:
            self.buy(long_call.vt_symbol, self.quantity)
            self.sell(short_call.vt_symbol, self.quantity * self.ratio)
            self.write_log(f"建立比率价差: 买入{long_call.option_strike}×{self.quantity}, 卖出{short_call.option_strike}×{self.quantity * self.ratio}")


class DeltaHedgeStrategy(OptionStrategyTemplate):
    """
    Delta对冲策略
    买入期权，通过标的进行Delta对冲
    """

    author = "ccQuant"
    strategy_name = "DeltaHedge"

    parameters = [
        {
            "name": "option_type",
            "type": "str",
            "default": "CALL",
            "options": ["CALL", "PUT"],
            "label": "期权类型",
            "description": "买入的期权类型"
        },
        {
            "name": "strike_offset",
            "type": "float",
            "default": 0.0,
            "min": -0.1,
            "max": 0.1,
            "step": 0.01,
            "label": "行权价偏移",
            "description": "相对于标的价格的偏移"
        },
        {
            "name": "hedge_threshold",
            "type": "float",
            "default": 0.1,
            "min": 0.05,
            "max": 0.3,
            "step": 0.05,
            "label": "对冲阈值",
            "description": "Delta偏离超过此值时调整对冲"
        },
        {
            "name": "option_quantity",
            "type": "int",
            "default": 10,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "期权手数",
            "description": "买入期权的手数"
        },
    ]

    def __init__(self, engine: OptionBacktestEngine, params: Optional[Dict[str, Any]] = None):
        super().__init__(engine, params)
        self.option_type = self.get_param("option_type", "CALL")
        self.strike_offset = self.get_param("strike_offset", 0.0)
        self.hedge_threshold = self.get_param("hedge_threshold", 0.1)
        self.option_quantity = self.get_param("option_quantity", 10)

        self.target_delta = 0.0
        self.last_hedge_delta = 0.0
        self.option_leg = None

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log("Delta对冲策略初始化")

        underlying_price = self.get_underlying_price()
        if not underlying_price:
            return

        target_strike = underlying_price * (1 + self.strike_offset)
        option = self.select_contract(self.option_type, target_strike, 0)

        if option:
            # 买入期权
            self.buy(option.vt_symbol, self.option_quantity)
            self.option_leg = option.vt_symbol

            # 计算初始Delta并建立对冲头寸
            self._adjust_hedge()

            self.write_log(f"建立Delta对冲: 买入{self.option_type}@{option.option_strike}×{self.option_quantity}")

    def on_bar(self, bar: Any) -> None:
        """K线更新 - 检查是否需要调整对冲"""
        if not self.option_leg:
            return

        # 计算当前组合Delta
        portfolio_delta = self.engine.portfolio.total_delta

        # 如果Delta偏离超过阈值，调整对冲
        if abs(portfolio_delta - self.last_hedge_delta) > self.hedge_threshold:
            self._adjust_hedge()

    def _adjust_hedge(self) -> None:
        """调整Delta对冲"""
        # 获取当前Delta
        portfolio_delta = self.engine.portfolio.total_delta

        # 需要对冲的数量（简化处理，假设标的合约乘数为1）
        hedge_quantity = -int(portfolio_delta)

        if hedge_quantity != 0:
            # 先平掉现有对冲头寸（简化处理）
            # 实际应该追踪对冲头寸
            underlying_symbol = self.engine.underlying_symbol
            if underlying_symbol:
                if hedge_quantity > 0:
                    self.buy(underlying_symbol, hedge_quantity)
                else:
                    self.sell(underlying_symbol, abs(hedge_quantity))

                self.last_hedge_delta = portfolio_delta
                self.write_log(f"Delta对冲调整: {hedge_quantity}手, 新Delta={portfolio_delta:.3f}")


# 策略映射表
STRATEGY_MAP = {
    "BuyCallStrategy": "ccquant.strategy.template.BuyCallStrategy",
    "StraddleStrategy": "ccquant.strategy.template.StraddleStrategy",
    "IronCondorStrategy": "ccquant.strategy.template.IronCondorStrategy",
    "BullCallSpreadStrategy": "ccquant.strategy.strategies.BullCallSpreadStrategy",
    "BearPutSpreadStrategy": "ccquant.strategy.strategies.BearPutSpreadStrategy",
    "StrangleStrategy": "ccquant.strategy.strategies.StrangleStrategy",
    "ButterflySpreadStrategy": "ccquant.strategy.strategies.ButterflySpreadStrategy",
    "CalendarSpreadStrategy": "ccquant.strategy.strategies.CalendarSpreadStrategy",
    "RatioSpreadStrategy": "ccquant.strategy.strategies.RatioSpreadStrategy",
    "DeltaHedgeStrategy": "ccquant.strategy.strategies.DeltaHedgeStrategy",
}


def get_strategy_class(name: str):
    """根据名称获取策略类"""
    import importlib

    if name in STRATEGY_MAP:
        module_path, class_name = STRATEGY_MAP[name].rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    # 默认返回买入看涨
    from ccquant.strategy.template import BuyCallStrategy
    return BuyCallStrategy
