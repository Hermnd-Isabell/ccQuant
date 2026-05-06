"""
Comprehensive tests for the vnpy-style option backtesting engine.
Covers: engine init, data loading, limit order matching, daily P&L,
        strategy lifecycle, multi-contract, statistics, and optimization.
"""

from datetime import datetime, date, timedelta

import pytest

from ccquant.core.constant import Direction, Exchange, Interval, Offset, Status
from ccquant.core.object import BarData, OrderData, TradeData
from ccquant.backtest.daily_result import ContractDailyResult, PortfolioDailyResult
from ccquant.backtest.engine import BacktestingEngine
from ccquant.backtest.template import StrategyTemplate
from ccquant.backtest.optimization import OptimizationSetting


# =====================================================================
# Helpers
# =====================================================================

def make_bar(
    symbol: str,
    exchange: Exchange,
    dt: datetime,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    volume: float = 1000,
) -> BarData:
    return BarData(
        symbol=symbol,
        exchange=exchange,
        datetime=dt,
        interval=Interval.DAILY,
        open_price=open_p,
        high_price=high_p,
        low_price=low_p,
        close_price=close_p,
        volume=volume,
        gateway_name="TEST",
    )


def make_daily_bars(
    symbol: str,
    exchange: Exchange,
    start: datetime,
    prices: list[tuple[float, float, float, float]],
) -> list[BarData]:
    """Create bars from list of (open, high, low, close) tuples."""
    bars = []
    for i, (o, h, l, c) in enumerate(prices):
        dt = start + timedelta(days=i)
        bars.append(make_bar(symbol, exchange, dt, o, h, l, c))
    return bars


# Simple test strategy: buy on first trading bar, sell on third trading bar
class SimpleBuyHoldStrategy(StrategyTemplate):
    author = "test"
    parameters = []
    variables = []

    def __init__(self, engine, name, vt_symbols, setting):
        super().__init__(engine, name, vt_symbols, setting)
        self.trading_bar_count = 0

    def on_init(self):
        self.write_log("SimpleBuyHold init")

    def on_start(self):
        self.write_log("SimpleBuyHold start")

    def on_bars(self, bars: dict[str, BarData]):
        if not self.trading:
            return
        self.trading_bar_count += 1
        for vt_symbol, bar in bars.items():
            if self.trading_bar_count == 1:
                self.buy(vt_symbol, bar.close_price, 1)
            elif self.trading_bar_count == 3:
                self.sell(vt_symbol, bar.close_price, 1)


# Multi-contract strategy: buy both legs on first trading bar
class MultiLegStrategy(StrategyTemplate):
    author = "test"
    parameters = []
    variables = []

    def __init__(self, engine, name, vt_symbols, setting):
        super().__init__(engine, name, vt_symbols, setting)
        self.entered = False

    def on_init(self):
        pass

    def on_bars(self, bars: dict[str, BarData]):
        if not self.trading:
            return
        if not self.entered and len(bars) >= 2:
            for vt_symbol, bar in bars.items():
                self.buy(vt_symbol, bar.close_price, 1)
            self.entered = True


# Parameterized strategy for optimization testing
class ParamStrategy(StrategyTemplate):
    author = "test"
    parameters = ["fast_window", "slow_window"]
    variables = ["signal"]

    fast_window: int = 5
    slow_window: int = 20
    signal: int = 0

    def on_init(self):
        self.load_bars(1)

    def on_bars(self, bars: dict[str, BarData]):
        for vt_symbol, bar in bars.items():
            if self.get_pos(vt_symbol) == 0:
                self.buy(vt_symbol, bar.close_price, 1)


def build_engine(
    vt_symbols: list[str],
    bars_dict: dict[str, list[BarData]],
    capital: float = 1_000_000,
    rate: float = 0.0,
    slippage: float = 0.0,
) -> BacktestingEngine:
    """Helper to build a configured engine."""
    engine = BacktestingEngine()
    rates = {s: rate for s in vt_symbols}
    slippages = {s: slippage for s in vt_symbols}
    sizes = {s: 10000.0 for s in vt_symbols}
    priceticks = {s: 0.0001 for s in vt_symbols}

    engine.set_parameters(
        vt_symbols=vt_symbols,
        interval=Interval.DAILY,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 12, 31),
        rates=rates,
        slippages=slippages,
        sizes=sizes,
        priceticks=priceticks,
        capital=capital,
    )
    engine.load_data(bars_dict)
    return engine


# =====================================================================
# 1. Engine initialization tests
# =====================================================================

class TestEngineInit:
    def test_default_state(self):
        engine = BacktestingEngine()
        assert engine.vt_symbols == []
        assert engine.capital == 1_000_000
        assert engine.trades == {}
        assert engine.daily_df is None

    def test_set_parameters(self):
        engine = BacktestingEngine()
        symbols = ["OPT1.SSE", "OPT2.SSE"]
        engine.set_parameters(
            vt_symbols=symbols,
            interval=Interval.DAILY,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 6, 30),
            rates={"OPT1.SSE": 0.0003, "OPT2.SSE": 0.0003},
            slippages={"OPT1.SSE": 0.0, "OPT2.SSE": 0.0},
            sizes={"OPT1.SSE": 10000, "OPT2.SSE": 10000},
            priceticks={"OPT1.SSE": 0.0001, "OPT2.SSE": 0.0001},
            capital=500_000,
        )
        assert engine.vt_symbols == symbols
        assert engine.capital == 500_000
        assert engine.rates["OPT1.SSE"] == 0.0003

    def test_clear_data(self):
        engine = BacktestingEngine()
        engine.logs.append("test")
        engine.trade_count = 5
        engine.clear_data()
        assert engine.trade_count == 0
        assert engine.logs == []


# =====================================================================
# 2. Data loading tests
# =====================================================================

class TestDataLoading:
    def test_load_bars_dict(self):
        sym = "OPT1.SSE"
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.1, 0.9, 1.05)] * 5,
        )
        engine = build_engine([sym], {sym: bars})
        assert len(engine.dts) == 5
        assert len(engine.history_data) == 5

    def test_multi_symbol_time_alignment(self):
        """Two symbols with overlapping but different dates."""
        sym1 = "OPT1.SSE"
        sym2 = "OPT2.SSE"
        bars1 = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.1, 0.9, 1.0)] * 5,
        )
        bars2 = make_daily_bars(
            "OPT2", Exchange.SSE, datetime(2024, 1, 3),
            [(2.0, 2.1, 1.9, 2.0)] * 3,
        )
        engine = build_engine([sym1, sym2], {sym1: bars1, sym2: bars2})
        # dts should be union: 5 from sym1 + 3 from sym2, but 3 overlap
        assert len(engine.dts) == 5  # Jan 1-5


# =====================================================================
# 3. Limit order matching tests
# =====================================================================

class TestLimitOrderMatching:
    def test_buy_order_fills_when_price_above_low(self):
        """Buy at 1.0 when bar low is 0.9 -> should fill at min(1.0, open)."""
        sym = "OPT1.SSE"
        # Need multiple bars: warmup consumes first bar
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [
                (1.0, 1.2, 0.9, 1.1),  # warmup bar
                (1.0, 1.2, 0.9, 1.1),  # strategy buys here (bar_count=1)
                (1.0, 1.2, 0.9, 1.1),  # order crosses here
            ],
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(SimpleBuyHoldStrategy, {})
        engine.run_backtesting()

        trades = engine.get_all_trades()
        assert len(trades) >= 1
        buy_trade = trades[0]
        assert buy_trade.direction == Direction.LONG
        # Buy price = min(order_price=close=1.1, open_price=1.0) = 1.0
        assert buy_trade.price == 1.0

    def test_sell_order_fills_when_price_below_high(self):
        """Sell at 1.0 when bar high is 1.2 -> should fill at max(1.0, open)."""
        sym = "OPT1.SSE"
        # Need extra bars: warmup + buy on bar1 + hold bar2 + sell bar3
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [
                (1.0, 1.2, 0.9, 1.1),   # warmup
                (1.0, 1.2, 0.9, 1.1),   # trading bar 1: buy
                (1.1, 1.3, 1.0, 1.2),   # trading bar 2: hold
                (1.2, 1.4, 1.1, 1.15),  # trading bar 3: sell order placed
                (1.15, 1.3, 1.0, 1.1),  # trading bar 4: sell order crosses
            ],
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(SimpleBuyHoldStrategy, {})
        engine.run_backtesting()

        trades = engine.get_all_trades()
        assert len(trades) == 2
        sell_trade = trades[1]
        assert sell_trade.direction == Direction.SHORT

    def test_buy_order_not_filled_when_price_below_low(self):
        """Buy at 0.5 when bar low is 0.9 -> should NOT fill."""
        sym = "OPT1.SSE"

        class LowBidStrategy(StrategyTemplate):
            parameters = []
            variables = []

            def __init__(self, engine, name, vt_symbols, setting):
                super().__init__(engine, name, vt_symbols, setting)
                self.sent = False

            def on_bars(self, bars):
                if not self.sent:
                    for vt_symbol in bars:
                        self.buy(vt_symbol, 0.5, 1)  # bid too low
                    self.sent = True

        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.2, 0.9, 1.1)],
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(LowBidStrategy, {})
        engine.run_backtesting()

        assert len(engine.get_all_trades()) == 0


# =====================================================================
# 4. Daily P&L calculation tests
# =====================================================================

class TestDailyPnL:
    def test_contract_daily_result_holding_pnl(self):
        """Verify holding_pnl = start_pos * (close - pre_close) * size."""
        result = ContractDailyResult(date(2024, 1, 2), close_price=10.5)
        result.calculate_pnl(
            pre_close=10.0,
            start_pos=1.0,
            size=10000.0,
            rate=0.0,
            slippage=0.0,
        )
        expected = 1.0 * (10.5 - 10.0) * 10000.0
        assert result.holding_pnl == expected
        assert result.net_pnl == expected  # no trades, no costs

    def test_contract_daily_result_trading_pnl(self):
        """Verify trading_pnl with a buy trade."""
        result = ContractDailyResult(date(2024, 1, 1), close_price=10.5)
        trade = TradeData(
            symbol="OPT1",
            exchange=Exchange.SSE,
            orderid="1",
            tradeid="1",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=10.0,
            volume=1.0,
            datetime=datetime(2024, 1, 1, 10, 0),
            gateway_name="TEST",
        )
        result.add_trade(trade)
        result.calculate_pnl(
            pre_close=0.0,
            start_pos=0.0,
            size=10000.0,
            rate=0.0,
            slippage=0.0,
        )
        # trading_pnl = +1 * (10.5 - 10.0) * 10000 = 5000
        assert result.trading_pnl == 5000.0
        assert result.end_pos == 1.0

    def test_contract_daily_result_commission_and_slippage(self):
        """Verify commission and slippage deduction."""
        result = ContractDailyResult(date(2024, 1, 1), close_price=10.0)
        trade = TradeData(
            symbol="OPT1", exchange=Exchange.SSE,
            orderid="1", tradeid="1",
            direction=Direction.LONG, offset=Offset.OPEN,
            price=10.0, volume=1.0,
            datetime=datetime(2024, 1, 1, 10, 0),
            gateway_name="TEST",
        )
        result.add_trade(trade)
        result.calculate_pnl(
            pre_close=0.0, start_pos=0.0,
            size=10000.0, rate=0.0003, slippage=0.002,
        )
        # turnover = 1 * 10000 * 10.0 = 100000
        # commission = 100000 * 0.0003 = 30
        # slippage = 1 * 10000 * 0.002 = 20
        assert result.commission == pytest.approx(30.0, rel=1e-6)
        assert result.slippage == pytest.approx(20.0, rel=1e-6)
        assert result.net_pnl == pytest.approx(result.total_pnl - 30.0 - 20.0, rel=1e-6)

    def test_portfolio_daily_result_aggregation(self):
        """Verify PortfolioDailyResult aggregates multiple contracts."""
        close_prices = {"OPT1.SSE": 10.5, "OPT2.SSE": 5.2}
        portfolio_result = PortfolioDailyResult(date(2024, 1, 1), close_prices)

        trade1 = TradeData(
            symbol="OPT1", exchange=Exchange.SSE,
            orderid="1", tradeid="1",
            direction=Direction.LONG, offset=Offset.OPEN,
            price=10.0, volume=1.0,
            datetime=datetime(2024, 1, 1), gateway_name="TEST",
        )
        trade2 = TradeData(
            symbol="OPT2", exchange=Exchange.SSE,
            orderid="2", tradeid="2",
            direction=Direction.LONG, offset=Offset.OPEN,
            price=5.0, volume=2.0,
            datetime=datetime(2024, 1, 1), gateway_name="TEST",
        )
        portfolio_result.add_trade(trade1)
        portfolio_result.add_trade(trade2)

        sizes = {"OPT1.SSE": 10000, "OPT2.SSE": 10000}
        rates = {"OPT1.SSE": 0.0, "OPT2.SSE": 0.0}
        slippages = {"OPT1.SSE": 0.0, "OPT2.SSE": 0.0}

        portfolio_result.calculate_pnl({}, {}, sizes, rates, slippages)

        # OPT1: +1 * (10.5 - 10.0) * 10000 = 5000
        # OPT2: +2 * (5.2 - 5.0) * 10000 = 4000
        assert portfolio_result.trading_pnl == pytest.approx(9000.0, rel=1e-6)
        assert portfolio_result.trade_count == 2

    def test_max_drawdown_calculation(self):
        """Construct V-shape balance curve and verify max_drawdown."""
        sym = "OPT1.SSE"
        # Prices: up, up, down, down, up -> V shape
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [
                (1.0, 1.1, 0.9, 1.0),
                (1.0, 1.2, 0.9, 1.1),
                (1.1, 1.2, 0.8, 0.85),
                (0.85, 0.9, 0.7, 0.75),
                (0.75, 1.0, 0.7, 0.95),
            ],
        )
        engine = build_engine([sym], {sym: bars})

        class BuyAndHold(StrategyTemplate):
            parameters = []
            variables = []
            def on_bars(self, bars):
                for s, bar in bars.items():
                    if self.get_pos(s) == 0:
                        self.buy(s, bar.close_price, 1)

        engine.add_strategy(BuyAndHold, {})
        engine.run_backtesting()
        df = engine.calculate_result()
        stats = engine.calculate_statistics(output=False)

        assert stats["max_drawdown"] < 0  # drawdown is negative
        assert stats["total_days"] > 0


# =====================================================================
# 5. Strategy lifecycle tests
# =====================================================================

class TestStrategyLifecycle:
    def test_init_start_bars_sequence(self):
        """Verify on_init -> on_start -> on_bars call order."""
        call_log = []

        class LogStrategy(StrategyTemplate):
            parameters = []
            variables = []
            def on_init(self):
                call_log.append("init")
            def on_start(self):
                call_log.append("start")
            def on_bars(self, bars):
                call_log.append("bars")

        sym = "OPT1.SSE"
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.1, 0.9, 1.0)] * 3,
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(LogStrategy, {})
        engine.run_backtesting()

        assert call_log[0] == "init"
        assert "start" in call_log
        assert "bars" in call_log

    def test_trading_flag_prevents_orders(self):
        """Orders should not be sent when trading=False."""
        sym = "OPT1.SSE"

        class EarlyBuyStrategy(StrategyTemplate):
            parameters = []
            variables = []
            def on_init(self):
                # Try to buy during init (trading=False)
                for s in self.vt_symbols:
                    self.buy(s, 1.0, 1)

        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.1, 0.9, 1.0)] * 3,
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(EarlyBuyStrategy, {})
        engine.run_backtesting()

        # No trades should have been made during init
        assert len(engine.get_all_trades()) == 0

    def test_position_tracking(self):
        """Verify strategy.pos updates correctly after trades."""
        sym = "OPT1.SSE"
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.2, 0.9, 1.1)] * 6,  # warmup(1) + buy(1) + hold(1) + sell(1) + cross(1) + extra
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(SimpleBuyHoldStrategy, {})
        engine.run_backtesting()

        # After buy(1) and sell(1), net pos should be 0
        assert engine.strategy.get_pos(sym) == 0


# =====================================================================
# 6. Multi-contract tests
# =====================================================================

class TestMultiContract:
    def test_two_contracts_simultaneous_buy(self):
        sym1 = "CALL.SSE"
        sym2 = "PUT.SSE"
        bars1 = make_daily_bars(
            "CALL", Exchange.SSE, datetime(2024, 1, 1),
            [(0.5, 0.6, 0.4, 0.55)] * 5,
        )
        bars2 = make_daily_bars(
            "PUT", Exchange.SSE, datetime(2024, 1, 1),
            [(0.3, 0.4, 0.2, 0.35)] * 5,
        )
        engine = build_engine(
            [sym1, sym2], {sym1: bars1, sym2: bars2}
        )
        engine.add_strategy(MultiLegStrategy, {})
        engine.run_backtesting()

        trades = engine.get_all_trades()
        assert len(trades) == 2
        symbols_traded = {t.vt_symbol for t in trades}
        assert sym1 in symbols_traded
        assert sym2 in symbols_traded

    def test_forward_fill_missing_data(self):
        """When one symbol has no data for a dt, it should forward-fill."""
        sym1 = "OPT1.SSE"
        sym2 = "OPT2.SSE"
        # sym1 has 3 days, sym2 only has day 1
        bars1 = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.1, 0.9, 1.0), (1.0, 1.1, 0.9, 1.05), (1.05, 1.2, 1.0, 1.1)],
        )
        bars2 = make_daily_bars(
            "OPT2", Exchange.SSE, datetime(2024, 1, 1),
            [(2.0, 2.1, 1.9, 2.0)],
        )
        engine = build_engine([sym1, sym2], {sym1: bars1, sym2: bars2})
        engine.add_strategy(MultiLegStrategy, {})
        engine.run_backtesting()

        # Engine should have processed all 3 days
        assert len(engine.dts) == 3


# =====================================================================
# 7. Statistics tests
# =====================================================================

class TestStatistics:
    def test_statistics_keys(self):
        sym = "OPT1.SSE"
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.2, 0.9, 1.1)] * 5,
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(SimpleBuyHoldStrategy, {})
        engine.run_backtesting()
        engine.calculate_result()
        stats = engine.calculate_statistics(output=False)

        expected_keys = [
            "start_date", "end_date", "total_days", "profit_days",
            "loss_days", "capital", "end_balance", "max_drawdown",
            "sharpe_ratio", "total_return", "annual_return",
            "return_drawdown_ratio",
        ]
        for key in expected_keys:
            assert key in stats, f"Missing key: {key}"

    def test_chart_generation(self):
        sym = "OPT1.SSE"
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.2, 0.9, 1.1)] * 5,
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(SimpleBuyHoldStrategy, {})
        engine.run_backtesting()
        engine.calculate_result()
        engine.calculate_statistics(output=False)

        fig = engine.show_chart()
        assert fig is not None

        chart_json = engine.get_chart_json()
        assert chart_json is not None
        assert "Balance" in chart_json


# =====================================================================
# 8. Optimization tests
# =====================================================================

class TestOptimization:
    def test_optimization_setting(self):
        setting = OptimizationSetting()
        setting.add_parameter("fast_window", 5, 15, 5)
        setting.add_parameter("slow_window", 20, 40, 10)
        setting.set_target("sharpe_ratio")

        settings = setting.generate_settings()
        # fast: [5, 10, 15] = 3, slow: [20, 30, 40] = 3 -> 9 combos
        assert len(settings) == 9
        assert settings[0]["fast_window"] == 5
        assert settings[0]["slow_window"] == 20

    def test_single_param_optimization(self):
        setting = OptimizationSetting()
        setting.add_parameter("fast_window", 5)
        settings = setting.generate_settings()
        assert len(settings) == 1
        assert settings[0]["fast_window"] == 5


# =====================================================================
# 9. Data accessor tests
# =====================================================================

class TestDataAccessors:
    def test_get_trades_df(self):
        sym = "OPT1.SSE"
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.2, 0.9, 1.1)] * 5,
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(SimpleBuyHoldStrategy, {})
        engine.run_backtesting()

        trades_list = engine.get_trades_df()
        assert isinstance(trades_list, list)
        assert len(trades_list) >= 1
        assert "vt_symbol" in trades_list[0]
        assert "direction" in trades_list[0]

    def test_get_orders_df(self):
        sym = "OPT1.SSE"
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.2, 0.9, 1.1)] * 5,
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(SimpleBuyHoldStrategy, {})
        engine.run_backtesting()

        orders_list = engine.get_orders_df()
        assert isinstance(orders_list, list)
        assert len(orders_list) >= 1

    def test_get_daily_results_df(self):
        sym = "OPT1.SSE"
        bars = make_daily_bars(
            "OPT1", Exchange.SSE, datetime(2024, 1, 1),
            [(1.0, 1.2, 0.9, 1.1)] * 5,
        )
        engine = build_engine([sym], {sym: bars})
        engine.add_strategy(SimpleBuyHoldStrategy, {})
        engine.run_backtesting()
        engine.calculate_result()

        daily_list = engine.get_daily_results_df()
        assert isinstance(daily_list, list)
        for item in daily_list:
            assert "date" in item
            assert "net_pnl" in item
