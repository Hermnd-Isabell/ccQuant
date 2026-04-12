"""
Payoff diagram calculation for option portfolios.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np

from ccquant.core.constant import Direction

from .portfolio import OptionPortfolio, LegPosition
from .pricing import PricingContext, black_scholes_price


@dataclass
class PayoffCurve:
    """
    Payoff curve data for plotting.
    """

    underlying_prices: np.ndarray
    payoffs: np.ndarray
    label: str = ""


def payoff_at_expiry(
    portfolio: OptionPortfolio,
    underlying_prices: np.ndarray
) -> PayoffCurve:
    """
    Calculate portfolio payoff at expiration.
    """
    payoffs = np.zeros_like(underlying_prices)

    for leg in portfolio.legs.values():
        sign = 1.0 if leg.direction == Direction.LONG else -1.0
        strike = leg.contract.option_strike or 0.0
        size = leg.contract.size
        multiplier = sign * leg.volume * size

        if leg.contract.option_type and leg.contract.option_type.value == "Call":
            intrinsic = np.maximum(underlying_prices - strike, 0.0)
        else:
            intrinsic = np.maximum(strike - underlying_prices, 0.0)

        leg_payoff = multiplier * intrinsic - multiplier * leg.avg_price
        payoffs += leg_payoff

    return PayoffCurve(
        underlying_prices=underlying_prices,
        payoffs=payoffs,
        label="Payoff at Expiry",
    )


def payoff_at_date(
    portfolio: OptionPortfolio,
    underlying_prices: np.ndarray,
    r: float,
    t: float,
    iv_lookup: dict[str, float],
    q: float = 0.0
) -> PayoffCurve:
    """
    Calculate portfolio theoretical payoff at a given time-to-expiry (t > 0).
    Uses Black-Scholes to mark each leg.
    """
    payoffs = np.zeros_like(underlying_prices)

    for leg in portfolio.legs.values():
        sign = 1.0 if leg.direction == Direction.LONG else -1.0
        strike = leg.contract.option_strike or 0.0
        size = leg.contract.size
        iv = iv_lookup.get(leg.contract.vt_symbol, 0.2)
        opt_type: Literal["CALL", "PUT"] = (
            "CALL" if leg.contract.option_type and leg.contract.option_type.value == "Call" else "PUT"
        )

        # vectorized B-S evaluation
        leg_values = np.zeros_like(underlying_prices)
        for i, s in enumerate(underlying_prices):
            ctx = PricingContext(s=s, k=strike, r=r, t=t, sigma=iv, q=q)
            leg_values[i] = black_scholes_price(ctx, opt_type)

        multiplier = sign * leg.volume * size
        payoffs += multiplier * (leg_values - leg.avg_price)

    return PayoffCurve(
        underlying_prices=underlying_prices,
        payoffs=payoffs,
        label=f"Payoff at TTE={t:.4f}",
    )


def calculate_breakevens(
    underlying_prices: np.ndarray,
    payoffs: np.ndarray,
    threshold: float = 0.0
) -> list[float]:
    """
    Find approximate breakeven points where payoff crosses threshold (default 0).
    """
    diffs = payoffs - threshold
    sign_changes = np.where(np.diff(np.sign(diffs)))[0]
    breakevens: list[float] = []
    for idx in sign_changes:
        x1, x2 = underlying_prices[idx], underlying_prices[idx + 1]
        y1, y2 = diffs[idx], diffs[idx + 1]
        if y2 - y1 != 0:
            x_zero = x1 - y1 * (x2 - x1) / (y2 - y1)
            breakevens.append(float(x_zero))
    return breakevens
