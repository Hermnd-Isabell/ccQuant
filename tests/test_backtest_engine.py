"""
Tests for option backtest engine.
"""

from datetime import datetime, timedelta

from ccquant.core.constant import Exchange, Product, OptionType, Interval, Direction
from ccquant.core.object import ContractData, BarData
from ccquant.backtest.engine import OptionBacktestEngine
from ccquant.strategy.template import BuyCallStrategy


def _make_bars(symbol: str, exchange: Exchange, start: datetime, days: int, price: float = 0.1):
    bars = []
    for i in range(days):
        dt = start + timedelta(days=i)
        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                interval=Interval.DAILY,
                open_price=price,
                high_price=price + 0.005,
                low_price=price - 0.005,
                close_price=price,
                gateway_name="BACKTEST",
            )
        )
    return bars


def test_engine_buy_call():
    engine = OptionBacktestEngine()
    engine.set_parameters(initial_capital=1_000_000.0, slippage=0, rate=0)

    expiry = datetime(2024, 1, 24)
    call_contract = ContractData(
        symbol="510050C2401M02500",
        exchange=Exchange.SSE,
        name="510050C2401M02500",
        product=Product.OPTION,
        size=10000,
        pricetick=0.0001,
        option_strike=2.5,
        option_type=OptionType.CALL,
        option_expiry=expiry,
        option_underlying="510050.SSE",
        gateway_name="BACKTEST",
    )
    engine.add_contract(call_contract)

    start = datetime(2024, 1, 1)
    bars_dict = {
        "510050C2401M02500.SSE": _make_bars("510050C2401M02500", Exchange.SSE, start, 10, price=0.1),
    }
    engine.load_data(bars_dict)

    strategy = BuyCallStrategy(engine)
    engine.strategy = strategy
    engine.run_backtesting()

    result = engine.get_result()
    stats = result.statistics
    assert stats.total_trades >= 1
    assert len(result.trades) >= 1
    assert len(result.daily_snapshots) == 10
