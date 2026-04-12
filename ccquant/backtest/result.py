"""
Backtest result calculation and formatting.
"""

from dataclasses import dataclass, field
from datetime import datetime
from math import sqrt
from typing import Any

import numpy as np

from ccquant.core.object import TradeData
from ccquant.option.greeks import Greeks


def _safe_float(value: float) -> float:
    if np.isnan(value) or np.isinf(value):
        return 0.0
    return float(value)


@dataclass
class BacktestStatistics:
    """
    Standard backtest performance statistics.
    """

    start_date: datetime | None = None
    end_date: datetime | None = None
    total_days: int = 0

    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "total_days": self.total_days,
            "total_return": _safe_float(self.total_return),
            "annual_return": _safe_float(self.annual_return),
            "max_drawdown": _safe_float(self.max_drawdown),
            "max_drawdown_pct": _safe_float(self.max_drawdown_pct),
            "sharpe_ratio": _safe_float(self.sharpe_ratio),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": _safe_float(self.win_rate),
            "avg_pnl": _safe_float(self.avg_pnl),
            "avg_win": _safe_float(self.avg_win),
            "avg_loss": _safe_float(self.avg_loss),
            "profit_factor": _safe_float(self.profit_factor),
        }


def calculate_statistics(
    daily_values: list[tuple[datetime, float]],
    trades: list[TradeData],
    risk_free_rate: float = 0.0,
) -> BacktestStatistics:
    """
    Calculate performance statistics from daily portfolio values and trade list.
    daily_values: list of (datetime, total_value) sorted by datetime.
    """
    if not daily_values:
        return BacktestStatistics()

    dts = [d[0] for d in daily_values]
    values = np.array([d[1] for d in daily_values], dtype=float)
    returns = np.diff(values) / values[:-1]

    total_return = (values[-1] / values[0]) - 1.0 if values[0] != 0 else 0.0
    total_days = len(dts)
    years = max(total_days / 252.0, 1e-6)
    annual_return = (1.0 + total_return) ** (1.0 / years) - 1.0

    # Max drawdown
    cummax = np.maximum.accumulate(values)
    drawdowns = values - cummax
    max_dd_idx = np.argmin(drawdowns)
    max_drawdown = float(drawdowns[max_dd_idx])
    max_drawdown_pct = (max_drawdown / cummax[max_dd_idx]) if cummax[max_dd_idx] > 0 else 0.0

    # Sharpe
    if len(returns) > 1 and returns.std() > 0:
        sharpe = (returns.mean() - risk_free_rate / 252.0) / returns.std() * sqrt(252.0)
    else:
        sharpe = 0.0

    # Trade stats
    total_trades = len(trades)
    trade_pnls: list[float] = []
    # Note: per-trade PnL from trade objects alone is ambiguous without position context.
    # Here we provide simple counting; full trade PnL should be computed from recorder snapshots.

    stats = BacktestStatistics(
        start_date=dts[0],
        end_date=dts[-1],
        total_days=total_days,
        total_return=total_return,
        annual_return=annual_return,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe,
        total_trades=total_trades,
    )
    return stats


@dataclass
class BacktestResult:
    """
    Aggregated backtest result ready for UI consumption.
    """

    statistics: BacktestStatistics = field(default_factory=BacktestStatistics)
    daily_snapshots: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    portfolio_history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "statistics": self.statistics.to_dict(),
            "daily_snapshots": self.daily_snapshots,
            "trades": self.trades,
            "portfolio_history": self.portfolio_history,
        }
