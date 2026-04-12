"""
Tests for option core modules.
"""

from datetime import datetime

from ccquant.core.constant import Exchange, Product, OptionType, Direction
from ccquant.core.object import ContractData, BarData
from ccquant.option.chain import OptionChain
from ccquant.option.pricing import PricingContext, black_scholes_price, black_scholes_greeks
from ccquant.option.portfolio import OptionPortfolio
from ccquant.option.greeks import Greeks
from ccquant.option.payoff import payoff_at_expiry

import numpy as np


def test_black_scholes_call():
    ctx = PricingContext(s=100, k=100, r=0.05, t=0.25, sigma=0.2, q=0)
    price = black_scholes_price(ctx, "CALL")
    assert price > 0
    assert price > max(ctx.s - ctx.k, 0)  # time value exists


def test_black_scholes_put():
    ctx = PricingContext(s=100, k=100, r=0.05, t=0.25, sigma=0.2, q=0)
    price = black_scholes_price(ctx, "PUT")
    assert price > 0


def test_greeks_call_delta():
    ctx = PricingContext(s=100, k=100, r=0.05, t=0.25, sigma=0.2, q=0)
    greeks = black_scholes_greeks(ctx, "CALL")
    assert 0 < greeks.delta < 1
    assert greeks.gamma > 0
    assert greeks.vega > 0


def test_option_chain():
    chain = OptionChain("510050.SSE")
    expiry = datetime(2024, 1, 24)
    c = ContractData(
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
    chain.add_contract(c)
    assert len(chain) == 1
    assert chain.expiries == [expiry]
    assert chain.strikes(expiry) == [2.5]


def test_portfolio_multi_leg():
    portfolio = OptionPortfolio()
    expiry = datetime(2024, 1, 24)
    call = ContractData(
        symbol="C2500",
        exchange=Exchange.SSE,
        name="C2500",
        product=Product.OPTION,
        size=10000,
        pricetick=0.0001,
        option_strike=2.5,
        option_type=OptionType.CALL,
        option_expiry=expiry,
        gateway_name="BACKTEST",
    )
    put = ContractData(
        symbol="P2500",
        exchange=Exchange.SSE,
        name="P2500",
        product=Product.OPTION,
        size=10000,
        pricetick=0.0001,
        option_strike=2.5,
        option_type=OptionType.PUT,
        option_expiry=expiry,
        gateway_name="BACKTEST",
    )
    portfolio.add_trade(call, Direction.LONG, 0.1, 1)
    portfolio.add_trade(put, Direction.LONG, 0.08, 1)

    price_lookup = {"C2500.SSE": 0.12, "P2500.SSE": 0.07}
    pnl = portfolio.total_pnl(price_lookup)
    assert pnl == (0.12 - 0.1) * 10000 + (0.07 - 0.08) * 10000


def test_payoff_straddle():
    portfolio = OptionPortfolio()
    expiry = datetime(2024, 1, 24)
    call = ContractData(
        symbol="C2500",
        exchange=Exchange.SSE,
        name="C2500",
        product=Product.OPTION,
        size=10000,
        pricetick=0.0001,
        option_strike=2.5,
        option_type=OptionType.CALL,
        option_expiry=expiry,
        gateway_name="BACKTEST",
    )
    put = ContractData(
        symbol="P2500",
        exchange=Exchange.SSE,
        name="P2500",
        product=Product.OPTION,
        size=10000,
        pricetick=0.0001,
        option_strike=2.5,
        option_type=OptionType.PUT,
        option_expiry=expiry,
        gateway_name="BACKTEST",
    )
    portfolio.add_trade(call, Direction.LONG, 0.1, 1)
    portfolio.add_trade(put, Direction.LONG, 0.08, 1)

    prices = np.array([2.3, 2.4, 2.5, 2.6, 2.7])
    curve = payoff_at_expiry(portfolio, prices)
    # At exactly strike, payoff should be negative (premium paid)
    assert curve.payoffs[2] < 0
    # Far ITM on either side should have positive payoff
    assert curve.payoffs[0] > 0 or curve.payoffs[4] > 0
