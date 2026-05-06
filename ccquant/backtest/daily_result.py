"""
Daily mark-to-market P&L calculation.
Follows vnpy's ContractDailyResult / PortfolioDailyResult pattern exactly.

Core formula per contract per day:
    holding_pnl = start_pos * (close_price - pre_close) * size
    trading_pnl = sum(pos_change * (close_price - trade_price) * size)
    total_pnl   = holding_pnl + trading_pnl
    net_pnl     = total_pnl - commission - slippage
"""

from __future__ import annotations

from datetime import date

from ccquant.core.constant import Direction
from ccquant.core.object import TradeData


class ContractDailyResult:
    """Single contract daily P&L (mirrors vnpy ContractDailyResult)."""

    def __init__(self, result_date: date, close_price: float) -> None:
        self.date: date = result_date
        self.close_price: float = close_price
        self.pre_close: float = 0.0

        self.trades: list[TradeData] = []
        self.trade_count: int = 0

        self.start_pos: float = 0.0
        self.end_pos: float = 0.0

        self.turnover: float = 0.0
        self.commission: float = 0.0
        self.slippage: float = 0.0

        self.trading_pnl: float = 0.0
        self.holding_pnl: float = 0.0
        self.total_pnl: float = 0.0
        self.net_pnl: float = 0.0

    def add_trade(self, trade: TradeData) -> None:
        self.trades.append(trade)

    def calculate_pnl(
        self,
        pre_close: float,
        start_pos: float,
        size: float,
        rate: float,
        slippage: float,
    ) -> None:
        """Calculate daily P&L using vnpy mark-to-market method."""
        self.pre_close = pre_close
        self.start_pos = start_pos
        self.end_pos = start_pos

        # Holding P&L: position carried from yesterday
        self.holding_pnl = self.start_pos * (self.close_price - self.pre_close) * size

        # Trading P&L: intraday trades
        self.trade_count = len(self.trades)

        for trade in self.trades:
            if trade.direction == Direction.LONG:
                pos_change = trade.volume
            else:
                pos_change = -trade.volume

            self.end_pos += pos_change

            turnover: float = trade.volume * size * trade.price

            self.trading_pnl += pos_change * (self.close_price - trade.price) * size
            self.slippage += trade.volume * size * slippage
            self.turnover += turnover
            self.commission += turnover * rate

        self.total_pnl = self.trading_pnl + self.holding_pnl
        self.net_pnl = self.total_pnl - self.commission - self.slippage

    def update_close_price(self, close_price: float) -> None:
        self.close_price = close_price


class PortfolioDailyResult:
    """Portfolio-level daily P&L aggregating all contracts."""

    def __init__(self, result_date: date, close_prices: dict[str, float]) -> None:
        self.date: date = result_date
        self.close_prices: dict[str, float] = close_prices
        self.pre_closes: dict[str, float] = {}
        self.start_poses: dict[str, float] = {}
        self.end_poses: dict[str, float] = {}

        self.contract_results: dict[str, ContractDailyResult] = {}
        for vt_symbol, close_price in close_prices.items():
            self.contract_results[vt_symbol] = ContractDailyResult(result_date, close_price)

        self.trade_count: int = 0
        self.turnover: float = 0.0
        self.commission: float = 0.0
        self.slippage: float = 0.0
        self.trading_pnl: float = 0.0
        self.holding_pnl: float = 0.0
        self.total_pnl: float = 0.0
        self.net_pnl: float = 0.0

    def add_trade(self, trade: TradeData) -> None:
        contract_result = self.contract_results.get(trade.vt_symbol)
        if contract_result:
            contract_result.add_trade(trade)

    def calculate_pnl(
        self,
        pre_closes: dict[str, float],
        start_poses: dict[str, float],
        sizes: dict[str, float],
        rates: dict[str, float],
        slippages: dict[str, float],
    ) -> None:
        self.pre_closes = pre_closes
        self.start_poses = start_poses

        for vt_symbol, contract_result in self.contract_results.items():
            contract_result.calculate_pnl(
                pre_closes.get(vt_symbol, 0),
                start_poses.get(vt_symbol, 0),
                sizes.get(vt_symbol, 1),
                rates.get(vt_symbol, 0),
                slippages.get(vt_symbol, 0),
            )

            self.trade_count += contract_result.trade_count
            self.turnover += contract_result.turnover
            self.commission += contract_result.commission
            self.slippage += contract_result.slippage
            self.trading_pnl += contract_result.trading_pnl
            self.holding_pnl += contract_result.holding_pnl
            self.total_pnl += contract_result.total_pnl
            self.net_pnl += contract_result.net_pnl

            self.end_poses[vt_symbol] = contract_result.end_pos

    def update_close_prices(self, close_prices: dict[str, float]) -> None:
        self.close_prices.update(close_prices)
        for vt_symbol, close_price in close_prices.items():
            contract_result = self.contract_results.get(vt_symbol)
            if contract_result:
                contract_result.update_close_price(close_price)
            else:
                self.contract_results[vt_symbol] = ContractDailyResult(
                    self.date, close_price
                )
