"""
Option portfolio management for multi-leg positions.
"""

from dataclasses import dataclass, field
from datetime import datetime

from ccquant.core.constant import Direction
from ccquant.core.object import ContractData

from .greeks import Greeks


@dataclass
class LegPosition:
    """
    Represents a single leg in an option portfolio.
    """

    contract: ContractData
    direction: Direction
    volume: float = 0.0          # positive number of contracts
    avg_price: float = 0.0       # average entry price

    def market_value(self, mark_price: float) -> float:
        """
        Market value of this leg (per contract * volume).
        For longs: positive, for shorts: negative.
        """
        sign = 1.0 if self.direction == Direction.LONG else -1.0
        return sign * self.volume * mark_price * self.contract.size

    def pnl(self, mark_price: float) -> float:
        """
        Unrealized PnL of this leg.
        """
        sign = 1.0 if self.direction == Direction.LONG else -1.0
        return sign * self.volume * (mark_price - self.avg_price) * self.contract.size

    def greeks_notional(self, greeks: Greeks) -> Greeks:
        """
        Scale Greeks by position size and direction.
        """
        sign = 1.0 if self.direction == Direction.LONG else -1.0
        multiplier = sign * self.volume * self.contract.size
        return greeks * multiplier


class OptionPortfolio:
    """
    Manages a portfolio of option legs.
    Supports arbitrary multi-leg strategies (spreads, butterflies, iron condors, etc.).
    """

    def __init__(self) -> None:
        """"""
        self.legs: dict[str, LegPosition] = {}

    def add_trade(
        self,
        contract: ContractData,
        direction: Direction,
        price: float,
        volume: float
    ) -> None:
        """
        Add a trade to the portfolio. Updates average price and volume.
        """
        key = contract.vt_symbol
        existing = self.legs.get(key)

        if existing is None:
            self.legs[key] = LegPosition(
                contract=contract,
                direction=direction,
                volume=volume,
                avg_price=price,
            )
            return

        if existing.direction == direction:
            # Same direction: increase volume and adjust avg price
            total_cost = existing.avg_price * existing.volume + price * volume
            existing.volume += volume
            if existing.volume > 0:
                existing.avg_price = total_cost / existing.volume
        else:
            # Opposite direction: partial or full close
            if volume < existing.volume:
                # Partial close (reduce existing position)
                closed_pnl = (price - existing.avg_price) * volume * existing.contract.size
                if existing.direction == Direction.SHORT:
                    closed_pnl = -closed_pnl
                existing.volume -= volume
            elif volume == existing.volume:
                # Full close
                del self.legs[key]
            else:
                # Flip direction (close all + open new)
                new_volume = volume - existing.volume
                self.legs[key] = LegPosition(
                    contract=contract,
                    direction=direction,
                    volume=new_volume,
                    avg_price=price,
                )

    def remove_leg(self, vt_symbol: str) -> None:
        """
        Remove a leg entirely from the portfolio.
        """
        if vt_symbol in self.legs:
            del self.legs[vt_symbol]

    def get_leg(self, vt_symbol: str) -> LegPosition | None:
        return self.legs.get(vt_symbol)

    def total_greeks(self, greeks_lookup: dict[str, Greeks]) -> Greeks:
        """
        Aggregate Greeks across all legs.
        :param greeks_lookup: dict mapping vt_symbol to its per-contract Greeks.
        """
        total = Greeks()
        for key, leg in self.legs.items():
            greeks = greeks_lookup.get(key)
            if greeks:
                total = total + leg.greeks_notional(greeks)
        return total

    def total_pnl(self, price_lookup: dict[str, float]) -> float:
        """
        Aggregate unrealized PnL across all legs.
        """
        total = 0.0
        for key, leg in self.legs.items():
            price = price_lookup.get(key, 0.0)
            total += leg.pnl(price)
        return total

    def total_market_value(self, price_lookup: dict[str, float]) -> float:
        """
        Aggregate market value across all legs.
        """
        total = 0.0
        for key, leg in self.legs.items():
            price = price_lookup.get(key, 0.0)
            total += leg.market_value(price)
        return total

    def margin_estimate(self, price_lookup: dict[str, float], margin_rate: float = 0.15) -> float:
        """
        Very rough margin estimate based on absolute market value and a rate.
        For production, replace with SPAN margin model.
        """
        total_abs_value = sum(
            abs(leg.market_value(price_lookup.get(key, 0.0)))
            for key, leg in self.legs.items()
        )
        return total_abs_value * margin_rate

    def to_dict(self, price_lookup: dict[str, float], greeks_lookup: dict[str, Greeks] | None = None) -> dict:
        """
        Serialize portfolio state.
        """
        legs_data = []
        for key, leg in self.legs.items():
            price = price_lookup.get(key, 0.0)
            leg_data = {
                "vt_symbol": key,
                "symbol": leg.contract.symbol,
                "strike": leg.contract.option_strike,
                "option_type": leg.contract.option_type.value if leg.contract.option_type else None,
                "expiry": leg.contract.option_expiry.isoformat() if leg.contract.option_expiry else None,
                "direction": leg.direction.value,
                "volume": leg.volume,
                "avg_price": leg.avg_price,
                "mark_price": price,
                "pnl": leg.pnl(price),
                "market_value": leg.market_value(price),
            }
            if greeks_lookup and key in greeks_lookup:
                notional_greeks = leg.greeks_notional(greeks_lookup[key])
                leg_data["greeks"] = notional_greeks.to_dict()
            legs_data.append(leg_data)

        return {
            "legs": legs_data,
            "total_pnl": self.total_pnl(price_lookup),
            "total_market_value": self.total_market_value(price_lookup),
            "total_greeks": (self.total_greeks(greeks_lookup).to_dict() if greeks_lookup else {}),
        }
