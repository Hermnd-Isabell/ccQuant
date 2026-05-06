"""
Strategy template for vnpy-style backtesting engine.
Mirrors vnpy_portfoliostrategy.template.StrategyTemplate lifecycle:
    on_init() -> on_start() -> on_bars(bars) -> on_stop()
"""

from __future__ import annotations

from copy import copy
from typing import Any

from ccquant.core.constant import Direction, Interval, Offset
from ccquant.core.object import BarData, OrderData, TradeData


class StrategyTemplate:
    """
    vnpy-compatible strategy template for option backtesting.

    Lifecycle:
        on_init()  — called once, use load_bars() to warm up indicators
        on_start() — called when backtesting begins
        on_bars()  — called for each datetime slice with {vt_symbol: BarData}
        on_stop()  — called when backtesting ends

    Trading:
        buy()   — send LONG + OPEN order
        sell()  — send SHORT + CLOSE order
        short() — send SHORT + OPEN order
        cover() — send LONG + CLOSE order
    """

    # Subclass should override these
    author: str = ""
    parameters: list[str] = []
    variables: list[str] = []

    def __init__(
        self,
        engine: Any,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict,
    ) -> None:
        self.engine = engine
        self.strategy_name: str = strategy_name
        self.vt_symbols: list[str] = vt_symbols

        self.inited: bool = False
        self.trading: bool = False
        self.pos: dict[str, float] = {}
        self.target_data: dict[str, float] = {}

        # Active orders tracking
        self.orders: dict[str, OrderData] = {}
        self.active_orderids: set[str] = set()
        self.trades: dict[str, TradeData] = {}

        # Apply setting to parameters
        self.update_setting(setting)

    def update_setting(self, setting: dict) -> None:
        """Apply parameter dict to strategy attributes.

        Supports two ``parameters`` formats:
        1. vnpy-style list of strings: ``["param1", "param2"]``
        2. UI metadata list of dicts:  ``[{"name": "param1", "default": 0, ...}]``
        """
        for item in self.parameters:
            if isinstance(item, dict):
                name = item["name"]
                # Apply default first, then override with user setting
                if not hasattr(self, name):
                    setattr(self, name, item.get("default"))
                if name in setting:
                    setattr(self, name, setting[name])
            else:
                name = item
                if name in setting:
                    setattr(self, name, setting[name])

    def get_parameters(self) -> dict:
        """Return current parameter values."""
        result = {}
        for item in self.parameters:
            name = item["name"] if isinstance(item, dict) else item
            result[name] = getattr(self, name, None)
        return result

    def get_variables(self) -> dict:
        """Return current variable values."""
        result = {}
        for item in self.variables:
            name = item["name"] if isinstance(item, dict) else item
            result[name] = getattr(self, name, None)
        result["inited"] = self.inited
        result["trading"] = self.trading
        result["pos"] = self.pos
        return result

    # ------------------------------------------------------------------
    # Lifecycle callbacks (override in subclass)
    # ------------------------------------------------------------------

    def on_init(self) -> None:
        """Called once before backtesting. Use load_bars() here."""
        pass

    def on_start(self) -> None:
        """Called when backtesting starts."""
        pass

    def on_stop(self) -> None:
        """Called when backtesting ends."""
        pass

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """Called for each datetime slice. Override with strategy logic."""
        pass

    def on_order(self, order: OrderData) -> None:
        """Called when order status changes."""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """Called when a trade is filled."""
        pass

    # ------------------------------------------------------------------
    # Engine callbacks (called by BacktestingEngine)
    # ------------------------------------------------------------------

    def update_order(self, order: OrderData) -> None:
        """Called by engine when order status updates."""
        self.orders[order.vt_orderid] = copy(order)

        if order.is_active():
            self.active_orderids.add(order.vt_orderid)
        elif order.vt_orderid in self.active_orderids:
            self.active_orderids.discard(order.vt_orderid)

        self.on_order(order)

    def update_trade(self, trade: TradeData) -> None:
        """Called by engine when a trade is filled."""
        self.trades[trade.vt_tradeid] = copy(trade)

        # Update position tracking
        if trade.direction == Direction.LONG:
            self.pos[trade.vt_symbol] = self.pos.get(trade.vt_symbol, 0) + trade.volume
        else:
            self.pos[trade.vt_symbol] = self.pos.get(trade.vt_symbol, 0) - trade.volume

        self.on_trade(trade)

    # ------------------------------------------------------------------
    # Trading convenience methods
    # ------------------------------------------------------------------

    def buy(
        self, vt_symbol: str, price: float, volume: float,
        stop: bool = False, lock: bool = False, net: bool = False,
    ) -> list[str]:
        """Send LONG + OPEN order."""
        return self.send_order(vt_symbol, Direction.LONG, Offset.OPEN, price, volume, stop, lock, net)

    def sell(
        self, vt_symbol: str, price: float, volume: float,
        stop: bool = False, lock: bool = False, net: bool = False,
    ) -> list[str]:
        """Send SHORT + CLOSE order."""
        return self.send_order(vt_symbol, Direction.SHORT, Offset.CLOSE, price, volume, stop, lock, net)

    def short(
        self, vt_symbol: str, price: float, volume: float,
        stop: bool = False, lock: bool = False, net: bool = False,
    ) -> list[str]:
        """Send SHORT + OPEN order."""
        return self.send_order(vt_symbol, Direction.SHORT, Offset.OPEN, price, volume, stop, lock, net)

    def cover(
        self, vt_symbol: str, price: float, volume: float,
        stop: bool = False, lock: bool = False, net: bool = False,
    ) -> list[str]:
        """Send LONG + CLOSE order."""
        return self.send_order(vt_symbol, Direction.LONG, Offset.CLOSE, price, volume, stop, lock, net)

    def send_order(
        self,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False,
    ) -> list[str]:
        """Send order through engine."""
        if not self.trading:
            return []
        return self.engine.send_order(self, vt_symbol, direction, offset, price, volume, stop, lock, net)

    def cancel_order(self, vt_orderid: str) -> None:
        """Cancel an active order."""
        if self.trading:
            self.engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        """Cancel all active orders."""
        for vt_orderid in list(self.active_orderids):
            self.cancel_order(vt_orderid)

    # ------------------------------------------------------------------
    # Data & utility methods
    # ------------------------------------------------------------------

    def load_bars(self, days: int, interval: Interval = Interval.DAILY) -> None:
        """Request warmup data for indicator initialization."""
        self.engine.load_bars(self, days, interval)

    def get_pos(self, vt_symbol: str) -> float:
        """Get current position for a symbol."""
        return self.pos.get(vt_symbol, 0)

    def set_target(self, vt_symbol: str, target: float) -> None:
        """Set target position for a symbol."""
        self.target_data[vt_symbol] = target

    def get_target(self, vt_symbol: str) -> float:
        """Get target position for a symbol."""
        return self.target_data.get(vt_symbol, 0)

    def rebalance_portfolio(self, bars: dict[str, BarData]) -> None:
        """Rebalance portfolio to match target positions."""
        for vt_symbol in self.vt_symbols:
            target_pos = self.get_target(vt_symbol)
            current_pos = self.get_pos(vt_symbol)
            diff = target_pos - current_pos
            volume = abs(diff)
            bar = bars.get(vt_symbol)
            if not bar or not volume:
                continue
            if diff > 0:
                if current_pos < 0:
                    cover_vol = min(volume, abs(current_pos))
                    buy_vol = volume - cover_vol
                    self.cover(vt_symbol, bar.close_price, cover_vol)
                    if buy_vol:
                        self.buy(vt_symbol, bar.close_price, buy_vol)
                else:
                    self.buy(vt_symbol, bar.close_price, volume)
            elif diff < 0:
                if current_pos > 0:
                    sell_vol = min(volume, current_pos)
                    short_vol = volume - sell_vol
                    self.sell(vt_symbol, bar.close_price, sell_vol)
                    if short_vol:
                        self.short(vt_symbol, bar.close_price, short_vol)
                else:
                    self.short(vt_symbol, bar.close_price, volume)

    def get_pricetick(self, vt_symbol: str) -> float:
        return self.engine.get_pricetick(self, vt_symbol)

    def get_size(self, vt_symbol: str) -> float:
        return self.engine.get_size(self, vt_symbol)

    def write_log(self, msg: str) -> None:
        self.engine.write_log(msg, self)

    def put_event(self) -> None:
        self.engine.put_strategy_event(self)

    def send_email(self, msg: str) -> None:
        self.engine.send_email(msg, self)

    def sync_data(self) -> None:
        self.engine.sync_strategy_data(self)


class TargetPosTemplate(StrategyTemplate):
    """vnpy-style target position template for single-contract strategies."""

    tick_add: int = 1
    last_bar: BarData | None = None
    target_pos: float = 0

    def __init__(
        self,
        engine: Any,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict,
    ) -> None:
        super().__init__(engine, strategy_name, vt_symbols, setting)
        self.active_orderids: list[str] = []
        self.cancel_orderids: list[str] = []
        self.variables.append("target_pos")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """Store last bar for trade price reference."""
        if self.vt_symbols:
            self.last_bar = bars.get(self.vt_symbols[0])

    def on_order(self, order: OrderData) -> None:
        """Track active order ids."""
        vt_orderid = order.vt_orderid
        if not order.is_active():
            if vt_orderid in self.active_orderids:
                self.active_orderids.remove(vt_orderid)
            if vt_orderid in self.cancel_orderids:
                self.cancel_orderids.remove(vt_orderid)

    def check_order_finished(self) -> bool:
        return len(self.active_orderids) == 0

    def set_target_pos(self, target_pos: float) -> None:
        self.target_pos = target_pos
        self.trade()

    def trade(self) -> None:
        if not self.check_order_finished():
            self.cancel_old_order()
        else:
            self.send_new_order()

    def cancel_old_order(self) -> None:
        for vt_orderid in self.active_orderids:
            if vt_orderid not in self.cancel_orderids:
                self.cancel_order(vt_orderid)
                self.cancel_orderids.append(vt_orderid)

    def send_new_order(self) -> None:
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        pos = self.get_pos(vt_symbol)
        pos_change = self.target_pos - pos
        if not pos_change:
            return

        if self.last_bar:
            if pos_change > 0:
                long_price = self.last_bar.close_price + self.tick_add * self.get_pricetick(vt_symbol)
                if pos < 0:
                    # Cover short first, then buy
                    cover_vol = min(abs(pos_change), abs(pos))
                    buy_vol = abs(pos_change) - cover_vol
                    vt_orderids = self.cover(vt_symbol, long_price, cover_vol)
                    if buy_vol:
                        vt_orderids += self.buy(vt_symbol, long_price, buy_vol)
                else:
                    vt_orderids = self.buy(vt_symbol, long_price, abs(pos_change))
            else:
                short_price = self.last_bar.close_price - self.tick_add * self.get_pricetick(vt_symbol)
                if pos > 0:
                    # Sell long first, then short
                    sell_vol = min(abs(pos_change), pos)
                    short_vol = abs(pos_change) - sell_vol
                    vt_orderids = self.sell(vt_symbol, short_price, sell_vol)
                    if short_vol:
                        vt_orderids += self.short(vt_symbol, short_price, short_vol)
                else:
                    vt_orderids = self.short(vt_symbol, short_price, abs(pos_change))
            self.active_orderids.extend(vt_orderids)
