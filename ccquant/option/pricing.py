"""
Option pricing models.
"""

from dataclasses import dataclass
from math import exp, log, sqrt
from typing import Literal

from scipy.stats import norm


@dataclass
class PricingContext:
    """
    Context for option pricing.
    """

    s: float          # underlying price
    k: float          # strike price
    r: float          # risk-free rate
    t: float          # time to expiry in years
    sigma: float      # implied volatility
    q: float = 0.0    # dividend yield


def black_scholes_price(
    ctx: PricingContext,
    option_type: Literal["CALL", "PUT"]
) -> float:
    """
    Black-Scholes price for European options.
    """
    if ctx.t <= 0 or ctx.sigma <= 0:
        if option_type == "CALL":
            return max(ctx.s - ctx.k, 0.0)
        else:
            return max(ctx.k - ctx.s, 0.0)

    d1 = _d1(ctx)
    d2 = _d2(ctx)

    if option_type == "CALL":
        price = (
            ctx.s * exp(-ctx.q * ctx.t) * norm.cdf(d1)
            - ctx.k * exp(-ctx.r * ctx.t) * norm.cdf(d2)
        )
    else:
        price = (
            ctx.k * exp(-ctx.r * ctx.t) * norm.cdf(-d2)
            - ctx.s * exp(-ctx.q * ctx.t) * norm.cdf(-d1)
        )

    return price


def black_scholes_greeks(
    ctx: PricingContext,
    option_type: Literal["CALL", "PUT"]
) -> "Greeks":
    """
    Calculate Greeks using Black-Scholes analytic formulas.
    """
    from .greeks import Greeks

    if ctx.t <= 0 or ctx.sigma <= 0:
        intrinsic = max(ctx.s - ctx.k, 0.0) if option_type == "CALL" else max(ctx.k - ctx.s, 0.0)
        return Greeks(
            delta=1.0 if option_type == "CALL" and intrinsic > 0 else (-1.0 if option_type == "PUT" and intrinsic > 0 else 0.0),
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
        )

    d1 = _d1(ctx)
    d2 = _d2(ctx)
    sqrt_t = sqrt(ctx.t)

    nd1 = norm.cdf(d1)
    nd2 = norm.cdf(d2)
    n_pdf_d1 = norm.pdf(d1)

    if option_type == "CALL":
        delta = exp(-ctx.q * ctx.t) * nd1
        theta = (
            -ctx.s * exp(-ctx.q * ctx.t) * n_pdf_d1 * ctx.sigma / (2 * sqrt_t)
            - ctx.r * ctx.k * exp(-ctx.r * ctx.t) * nd2
            + ctx.q * ctx.s * exp(-ctx.q * ctx.t) * nd1
        ) / 365.0
        rho = ctx.k * ctx.t * exp(-ctx.r * ctx.t) * nd2 / 100.0
    else:
        delta = -exp(-ctx.q * ctx.t) * norm.cdf(-d1)
        theta = (
            -ctx.s * exp(-ctx.q * ctx.t) * n_pdf_d1 * ctx.sigma / (2 * sqrt_t)
            + ctx.r * ctx.k * exp(-ctx.r * ctx.t) * norm.cdf(-d2)
            - ctx.q * ctx.s * exp(-ctx.q * ctx.t) * norm.cdf(-d1)
        ) / 365.0
        rho = -ctx.k * ctx.t * exp(-ctx.r * ctx.t) * norm.cdf(-d2) / 100.0

    gamma = exp(-ctx.q * ctx.t) * n_pdf_d1 / (ctx.s * ctx.sigma * sqrt_t)
    vega = ctx.s * exp(-ctx.q * ctx.t) * n_pdf_d1 * sqrt_t / 100.0

    return Greeks(
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=rho,
    )


def _d1(ctx: PricingContext) -> float:
    return (log(ctx.s / ctx.k) + (ctx.r - ctx.q + 0.5 * ctx.sigma ** 2) * ctx.t) / (ctx.sigma * sqrt(ctx.t))


def _d2(ctx: PricingContext) -> float:
    return _d1(ctx) - ctx.sigma * sqrt(ctx.t)


def implied_volatility(
    market_price: float,
    ctx: PricingContext,
    option_type: Literal["CALL", "PUT"],
    max_iter: int = 100,
    precision: float = 1e-5
) -> float | None:
    """
    Calculate implied volatility via Newton-Raphson method.
    Returns None if convergence fails.
    """
    if market_price <= 0 or ctx.t <= 0 or ctx.s <= 0 or ctx.k <= 0:
        return None

    sigma = 0.3
    for _ in range(max_iter):
        ctx_sigma = PricingContext(
            s=ctx.s, k=ctx.k, r=ctx.r, t=ctx.t, sigma=sigma, q=ctx.q
        )
        price = black_scholes_price(ctx_sigma, option_type)

        diff = price - market_price
        if abs(diff) < precision:
            return sigma

        # Use raw BS vega (dC/dσ) for Newton-Raphson, NOT the /100 trader convention.
        # greeks.vega is scaled by /100 for display, so we compute raw vega here.
        d1 = _d1(ctx_sigma)
        sqrt_t = sqrt(ctx_sigma.t)
        raw_vega = ctx_sigma.s * exp(-ctx_sigma.q * ctx_sigma.t) * norm.pdf(d1) * sqrt_t

        if raw_vega < 1e-12:
            break

        sigma = sigma - diff / raw_vega
        if sigma <= 0.001:
            sigma = 0.001
        elif sigma > 10.0:
            break

    return None
