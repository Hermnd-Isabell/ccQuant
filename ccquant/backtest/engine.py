"""
Option backtesting engine.
Supports multi-leg, multi-underlying option strategies with Greeks tracking.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from ccquant.core.constant import Direction, Interval, Offset, OrderType, Status
from ccquant.core.object import (
    BarData,
    OrderData,
    TradeData,
    OrderRequest,
    CancelRequest,
    ContractData,
)
from ccquant.core.utility import get_digits, round_to
from ccquant.option.portfolio import OptionPortfolio, LegPosition
from ccquant.option.greeks import Greeks
from ccquant.option.pricing import PricingContext, black_scholes_greeks

from .matcher import cross_limit_order, build_order_from_request
from .recorder import BacktestRecorder, PortfolioSnapshot
from .result import BacktestResult, calculate_statistics


class BaseOptionStrategy(ABC):
    """
    Abstract base class for option strategies.
    """

    def __init__(self, engine: "OptionBacktestEngine", params: dict[str, Any] | None = None) -> None:
        """"""
        self.engine: OptionBacktestEngine = engine
        self.inited: bool = False
        self.trading: bool = False
        self.params: dict[str, Any] = params or {}

    @abstractmethod
    def on_init(self) -> None:
        """
        Called once before backtesting starts.
        """
        pass

    @abstractmethod
    def on_bars(self, bars: dict[str, BarData]) -> None:
        """
        Called for every datetime slice with available bars.
        """
        pass

    def on_trade(self, trade: TradeData) -> None:
        """
        Called when a trade is filled.
        """
        pass

    def buy(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        offset: Offset = Offset.OPEN
    ) -> str:
        """
        Send a buy limit order.
        """
        return self.engine.send_order(vt_symbol, Direction.LONG, price, volume, offset)

    def sell(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        offset: Offset = Offset.CLOSE
    ) -> str:
        """
        Send a sell limit order.
        """
        return self.engine.send_order(vt_symbol, Direction.SHORT, price, volume, offset)

    def write_log(self, msg: str) -> None:
        """
        Write log message.
        """
        self.engine.recorder.write_log(msg)


class OptionBacktestEngine:
    """
    Backtesting engine for option strategies.
    """

    def __init__(self) -> None:
        """"""
        # Data
        self.history_data: dict[str, list[BarData]] = {}
        self.contracts: dict[str, ContractData] = {}
        self.dts: list[datetime] = []

        # Current state
        self.datetime: datetime | None = None
        self.bars: dict[str, BarData] = {}
        self.last_closes: dict[str, float] = {}

        # Portfolio
        self.portfolio: OptionPortfolio = OptionPortfolio()
        self.cash: float = 0.0
        self.initial_capital: float = 0.0

        # Orders
        self.active_limit_orders: dict[str, OrderData] = {}
        self.order_count: int = 0
        self.trade_count: int = 0

        # Settings
        self.slippage: float = 0.0
        self.rate: float = 0.0
        self.min_commission: float = 0.0
        self.risk_free_rate: float = 0.03

        # Recorder
        self.recorder: BacktestRecorder = BacktestRecorder()

        # Strategy
        self.strategy: BaseOptionStrategy | None = None

    def set_parameters(
        self,
        initial_capital: float = 1_000_000.0,
        slippage: float = 0.0,
        rate: float = 0.0,
        min_commission: float = 0.0,
        risk_free_rate: float = 0.03,
    ) -> None:
        """
        Set backtest parameters.
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.slippage = slippage
        self.rate = rate
        self.min_commission = min_commission
        self.risk_free_rate = risk_free_rate

    def add_contract(self, contract: ContractData) -> None:
        """
        Register a contract for reference during backtesting.
        """
        self.contracts[contract.vt_symbol] = contract

    def load_data(self, bars_dict: dict[str, list[BarData]]) -> None:
        """
        Load historical bar data for all symbols.
        bars_dict: {vt_symbol: [BarData, ...]}
        """
        all_dts: set[datetime] = set()
        for vt_symbol, bars in bars_dict.items():
            sorted_bars = sorted(bars, key=lambda b: b.datetime)
            self.history_data[vt_symbol] = sorted_bars
            all_dts.update(b.datetime for b in sorted_bars)

        self.dts = sorted(all_dts)

    def run_backtesting(self) -> None:
        """
        Main backtesting loop.
        """
        if not self.strategy:
            raise RuntimeError("Strategy must be set before running backtest")

        self.strategy.on_init()
        self.strategy.inited = True
        self.strategy.trading = True

        for dt in self.dts:
            self.datetime = dt
            self.new_bars(dt)

        self.strategy.trading = False

    def new_bars(self, dt: datetime) -> None:
        """
        Process a new datetime slice.
        """
        # Build bar snapshot for current dt
        self.bars = {}
        for vt_symbol, bars in self.history_data.items():
            bar = self._get_bar_at_dt(bars, dt)
            if bar:
                self.bars[vt_symbol] = bar
                self.last_closes[vt_symbol] = bar.close_price
            else:
                # Forward fill if prior close exists
                last_close = self.last_closes.get(vt_symbol)
                if last_close is not None:
                    self.bars[vt_symbol] = self._fill_bar(vt_symbol, dt, last_close)

        # Cross orders before strategy callback (no lookahead)
        self.cross_orders()

        # Strategy logic
        if self.bars:
            self.strategy.on_bars(self.bars)

        # Record snapshot
        self.record_snapshot(dt)

    def _get_bar_at_dt(self, bars: list[BarData], dt: datetime) -> BarData | None:
        """
        Binary search for exact datetime match (simplified by dict index).
        For clarity, we pre-index bars by datetime on first call.
        """
        if not hasattr(self, "_bar_index"):
            self._bar_index: dict[str, dict[datetime, BarData]] = {}
        vt_symbol = bars[0].vt_symbol if bars else ""
        if vt_symbol not in self._bar_index:
            self._bar_index[vt_symbol] = {b.datetime: b for b in bars}
        return self._bar_index[vt_symbol].get(dt)

    def _fill_bar(self, vt_symbol: str, dt: datetime, close_price: float) -> BarData:
        """
        Create a synthetic bar using last close price.
        """
        contract = self.contracts.get(vt_symbol)
        symbol, exchange_str = vt_symbol.rsplit(".", 1)
        from ccquant.core.constant import Exchange
        exchange = Exchange(exchange_str)
        return BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=dt,
            interval=Interval.MINUTE,
            open_price=close_price,
            high_price=close_price,
            low_price=close_price,
            close_price=close_price,
            gateway_name="BACKTEST",
        )

    def send_order(
        self,
        vt_symbol: str,
        direction: Direction,
        price: float,
        volume: float,
        offset: Offset = Offset.OPEN
    ) -> str:
        """
        Send a limit order in backtest.
        """
        contract = self.contracts.get(vt_symbol)
        if not contract:
            raise ValueError(f"Contract not found: {vt_symbol}")

        ticks = get_digits(contract.pricetick)
        price = round(price, ticks)

        self.order_count += 1
        orderid: str = f"{self.datetime.strftime('%Y%m%d%H%M%S')}_{self.order_count}"

        req = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            offset=offset,
        )
        order = build_order_from_request(req, "BACKTEST", orderid)
        self.active_limit_orders[orderid] = order
        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """
        Cancel an order.
        """
        order = self.active_limit_orders.get(req.orderid)
        if order and order.is_active():
            order.status = Status.CANCELLED
            del self.active_limit_orders[req.orderid]

    def cross_orders(self) -> None:
        """
        Cross all active limit orders against current bars.
        """
        finished_orders: list[str] = []
        for orderid, order in list(self.active_limit_orders.items()):
            bar = self.bars.get(order.vt_symbol)
            if not bar:
                continue

            contract = self.contracts.get(order.vt_symbol)
            size = contract.size if contract else 1.0

            self.trade_count += 1
            trade = cross_limit_order(
                order=order,
                bar=bar,
                trade_counter=self.trade_count,
                size=size,
                slippage=self.slippage,
                rate=self.rate,
                min_commission=self.min_commission,
            )

            if trade:
                # Cash impact
                trade_value = trade.price * trade.volume * size
                commission = max(trade_value * self.rate, self.min_commission)
                if trade.direction == Direction.LONG:
                    self.cash -= trade_value + commission
                else:
                    self.cash += trade_value - commission

                # Update portfolio
                self.portfolio.add_trade(
                    contract=contract,
                    direction=trade.direction,
                    price=trade.price,
                    volume=trade.volume,
                )

                self.recorder.record_trade(trade)
                if self.strategy:
                    self.strategy.on_trade(trade)

            if not order.is_active():
                finished_orders.append(orderid)

        for orderid in finished_orders:
            self.active_limit_orders.pop(orderid, None)

    def record_snapshot(self, dt: datetime) -> None:
        """
        Record portfolio snapshot for current datetime.
        """
        price_lookup: dict[str, float] = {}
        greeks_lookup: dict[str, Greeks] = {}

        for key, leg in self.portfolio.legs.items():
            bar = self.bars.get(key)
            if bar:
                price_lookup[key] = bar.close_price
            else:
                price_lookup[key] = self.last_closes.get(key, leg.avg_price)

            contract = leg.contract
            # Calculate per-contract Greeks if option
            if contract.option_type and contract.option_strike and contract.option_expiry:
                s = price_lookup.get(contract.option_underlying or "", price_lookup.get(key, leg.avg_price))
                k = contract.option_strike
                t = self._time_to_expiry(contract.option_expiry, dt)
                sigma = self._estimate_iv(contract, bar)
                q = 0.0
                opt_type = "CALL" if contract.option_type.value == "Call" else "PUT"
                ctx = PricingContext(s=s, k=k, r=self.risk_free_rate, t=t, sigma=sigma, q=q)
                greeks_lookup[key] = black_scholes_greeks(ctx, opt_type)
            else:
                greeks_lookup[key] = Greeks()

        total_greeks = self.portfolio.total_greeks(greeks_lookup)
        total_pnl = self.portfolio.total_pnl(price_lookup)
        total_mv = self.portfolio.total_market_value(price_lookup)
        margin = self.portfolio.margin_estimate(price_lookup)

        snapshot = PortfolioSnapshot(
            datetime=dt,
            total_pnl=total_pnl,
            total_market_value=total_mv,
            cash=self.cash,
            greeks=total_greeks,
            margin=margin,
        )
        self.recorder.record_snapshot(snapshot)

    def _time_to_expiry(self, expiry: datetime, dt: datetime) -> float:
        """
        Time to expiry in years.
        """
        delta = expiry - dt
        return max(delta.total_seconds() / (365.0 * 24.0 * 3600.0), 1e-6)

    def _estimate_iv(self, contract: ContractData, bar: BarData | None) -> float:
        """
        Estimate implied volatility. Placeholder: try to infer from bar extra data,
        otherwise fallback to a default.
        """
        if bar and bar.extra and "implied_vol" in bar.extra:
            return float(bar.extra["implied_vol"])
        return 0.2

    def get_result(self) -> BacktestResult:
        """
        Compile backtest result.
        """
        snapshots = self.recorder.get_snapshots_df()
        trades = self.recorder.get_trades_df()

        daily_values: list[tuple[datetime, float]] = []
        for snap in self.recorder.snapshots:
            portfolio_value = snap.cash + snap.total_market_value
            daily_values.append((snap.datetime, portfolio_value))

        stats = calculate_statistics(
            daily_values=daily_values,
            trades=self.recorder.trades,
            risk_free_rate=self.risk_free_rate,
        )

        return BacktestResult(
            statistics=stats,
            daily_snapshots=snapshots,
            trades=trades,
            portfolio_history=snapshots,
        )
