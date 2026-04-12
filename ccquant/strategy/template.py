"""
Option strategy template and built-in examples.
"""

from typing import Any

from ccquant.core.constant import Direction, Offset, OptionType
from ccquant.core.object import BarData, TradeData
from ccquant.backtest.engine import BaseOptionStrategy, OptionBacktestEngine


class OptionStrategyTemplate(BaseOptionStrategy):
    """
    Simplified template for option strategies.
    Inherit this class and override on_bars() to implement logic.
    """

    def __init__(self, engine: OptionBacktestEngine, params: dict[str, Any] | None = None) -> None:
        super().__init__(engine, params)
        self.slow_ma_window: int = int(params.get("slow_ma_window", 20)) if params else 20
        self.fast_ma_window: int = int(params.get("fast_ma_window", 5)) if params else 5

    def on_init(self) -> None:
        """
        Override for initialization logic (e.g., load pre-trained models).
        """
        pass

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """
        Override with strategy logic.
        """
        pass

    def on_trade(self, trade: TradeData) -> None:
        """
        Optional: handle post-trade updates.
        """
        pass


class BuyCallStrategy(OptionStrategyTemplate):
    """
    Simple example: buy ATM call on first bar and hold.
    """

    def on_bars(self, bars: dict[str, BarData]) -> None:
        if not self.inited:
            return

        # Example: just buy the first call contract we see
        for vt_symbol, bar in bars.items():
            contract = self.engine.contracts.get(vt_symbol)
            if contract and contract.option_type and contract.option_type.value == "Call":
                leg = self.engine.portfolio.get_leg(vt_symbol)
                if not leg:
                    self.buy(vt_symbol, bar.close_price, 1)
                break


class StraddleStrategy(OptionStrategyTemplate):
    """
    Example: enter a long straddle (buy ATM call + buy ATM put).
    """

    def on_init(self) -> None:
        self.entered: bool = False

    def on_bars(self, bars: dict[str, BarData]) -> None:
        if self.entered:
            return

        # Simple heuristic: pick the first expiry chain and buy ATM strikes
        from ccquant.option.chain import OptionChain
        from datetime import datetime

        # Build a temporary chain from contracts
        chain = OptionChain("")
        for contract in self.engine.contracts.values():
            if contract.product.value == "Option":
                chain.add_contract(contract)

        if not chain.expiries:
            return

        expiry = chain.expiries[0]
        # Find underlying price from bars (fallback to first bar close)
        underlying_price = next(iter(bars.values())).close_price if bars else 0.0

        atm = chain.atm_contracts(expiry, underlying_price)
        call_contract = atm.get(OptionType.CALL) if atm else None
        put_contract = atm.get(OptionType.PUT) if atm else None

        if call_contract and put_contract:
            call_bar = bars.get(call_contract.vt_symbol)
            put_bar = bars.get(put_contract.vt_symbol)
            if call_bar and put_bar:
                self.buy(call_contract.vt_symbol, call_bar.close_price, 1)
                self.buy(put_contract.vt_symbol, put_bar.close_price, 1)
                self.entered = True
                self.write_log(
                    f"Entered straddle at expiry={expiry}, strike={call_contract.option_strike}"
                )


class IronCondorStrategy(OptionStrategyTemplate):
    """
    Example: short iron condor (sell OTM call spread + sell OTM put spread).
    Expects at least 4 strikes per expiry.
    """

    def on_init(self) -> None:
        self.entered: bool = False

    def on_bars(self, bars: dict[str, BarData]) -> None:
        if self.entered:
            return

        from ccquant.option.chain import OptionChain

        chain = OptionChain("")
        for contract in self.engine.contracts.values():
            if contract.product.value == "Option":
                chain.add_contract(contract)

        if not chain.expiries:
            return

        expiry = chain.expiries[0]
        underlying_price = next(iter(bars.values())).close_price if bars else 0.0
        strikes = chain.strikes(expiry)
        if len(strikes) < 4:
            return

        # Sort strikes and pick OTM spreads around ATM
        atm_strike = min(strikes, key=lambda s: abs(s - underlying_price))
        put_strikes = [s for s in strikes if s <= atm_strike]
        call_strikes = [s for s in strikes if s >= atm_strike]
        if len(put_strikes) < 2 or len(call_strikes) < 2:
            return

        put_lower = put_strikes[-2]
        put_higher = put_strikes[-1]
        call_lower = call_strikes[0]
        call_higher = call_strikes[1]

        import ccquant.core.constant as co
        sell_put = chain.get_contract_by_strike(expiry, put_lower, co.OptionType.PUT)
        buy_put = chain.get_contract_by_strike(expiry, put_higher, co.OptionType.PUT)
        sell_call = chain.get_contract_by_strike(expiry, call_lower, co.OptionType.CALL)
        buy_call = chain.get_contract_by_strike(expiry, call_higher, co.OptionType.CALL)

        contracts = [sell_put, buy_put, sell_call, buy_call]
        if any(c is None for c in contracts):
            return

        for c in contracts:
            bar = bars.get(c.vt_symbol)
            if not bar:
                return

        # Sell put spread
        self.sell(sell_put.vt_symbol, bars[sell_put.vt_symbol].close_price, 1, Offset.OPEN)
        self.buy(buy_put.vt_symbol, bars[buy_put.vt_symbol].close_price, 1, Offset.OPEN)
        # Sell call spread
        self.sell(sell_call.vt_symbol, bars[sell_call.vt_symbol].close_price, 1, Offset.OPEN)
        self.buy(buy_call.vt_symbol, bars[buy_call.vt_symbol].close_price, 1, Offset.OPEN)

        self.entered = True
        self.write_log(
            f"Entered iron condor: puts {put_lower}/{put_higher}, calls {call_lower}/{call_higher}"
        )
