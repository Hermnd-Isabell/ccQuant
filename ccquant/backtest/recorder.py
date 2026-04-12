"""
Backtest recorder for tracking trades, portfolio snapshots, and Greeks attribution.
"""

from dataclasses import dataclass, field
from datetime import datetime

from ccquant.core.object import TradeData
from ccquant.option.greeks import Greeks


@dataclass
class PortfolioSnapshot:
    """
    Snapshot of portfolio state at a given datetime.
    """

    datetime: datetime
    total_pnl: float = 0.0
    total_market_value: float = 0.0
    cash: float = 0.0
    greeks: Greeks = field(default_factory=Greeks)
    margin: float = 0.0


class BacktestRecorder:
    """
    Records all events during a backtest run for later analysis.
    """

    def __init__(self) -> None:
        """"""
        self.trades: list[TradeData] = []
        self.snapshots: list[PortfolioSnapshot] = []
        self.logs: list[str] = []

    def record_trade(self, trade: TradeData) -> None:
        """
        Record a trade fill.
        """
        self.trades.append(trade)

    def record_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """
        Record a portfolio snapshot (typically per bar or per day).
        """
        self.snapshots.append(snapshot)

    def write_log(self, msg: str) -> None:
        """
        Record a log message.
        """
        self.logs.append(msg)

    def get_trades_df(self) -> list[dict]:
        """
        Convert trades to a list of dicts for frontend/JSON.
        """
        return [
            {
                "datetime": t.datetime.isoformat() if t.datetime else None,
                "vt_symbol": t.vt_symbol,
                "direction": t.direction.value if t.direction else None,
                "offset": t.offset.value,
                "price": t.price,
                "volume": t.volume,
            }
            for t in self.trades
        ]

    def get_snapshots_df(self) -> list[dict]:
        """
        Convert snapshots to a list of dicts.
        """
        return [
            {
                "datetime": s.datetime.isoformat(),
                "total_pnl": s.total_pnl,
                "total_market_value": s.total_market_value,
                "cash": s.cash,
                "margin": s.margin,
                **s.greeks.to_dict(),
            }
            for s in self.snapshots
        ]
