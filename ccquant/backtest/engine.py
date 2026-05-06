"""
Option backtesting engine.
Follows vnpy's BacktestingEngine architecture with daily mark-to-market P&L.
Supports single-underlying single-contract and single-underlying multi-contract.
Designed for future extension to multi-underlying multi-contract (portfolio level).
"""

from __future__ import annotations

from collections import defaultdict
from copy import copy
from datetime import date, datetime, timedelta
from functools import lru_cache, partial
from typing import Any
import traceback

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pandas import DataFrame
from collections.abc import Callable

from ccquant.core.constant import Direction, Exchange, Interval, Offset, OrderType, Status
from ccquant.core.object import (
    BarData,
    ContractData,
    OrderData,
    TradeData,
)
from ccquant.core.utility import extract_vt_symbol, round_to

from .daily_result import ContractDailyResult, PortfolioDailyResult
from .optimization import OptimizationSetting, run_bf_optimization, run_ga_optimization


INTERVAL_DELTA_MAP: dict[Interval, timedelta] = {
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta(days=1),
}


class BacktestingEngine:
    """
    Option backtesting engine with vnpy-style daily mark-to-market P&L.
    Supports per-contract rates/slippages/sizes/priceticks dicts.
    """

    gateway_name: str = "BACKTESTING"

    def __init__(self) -> None:
        self.vt_symbols: list[str] = []
        self.start: datetime = datetime(1970, 1, 1)
        self.end: datetime = datetime(1970, 1, 1)
        self.interval: Interval = Interval.DAILY

        # Per-contract settings (keyed by vt_symbol)
        self.rates: dict[str, float] = {}
        self.slippages: dict[str, float] = {}
        self.sizes: dict[str, float] = {}
        self.priceticks: dict[str, float] = {}

        self.capital: float = 1_000_000
        self.risk_free: float = 0.0
        self.annual_days: int = 240

        # Strategy
        self.strategy_class: type | None = None
        self.strategy: Any = None
        self.bars: dict[str, BarData] = {}
        self.datetime: datetime = datetime(1970, 1, 1)

        # Data
        self.history_data: dict[tuple, BarData] = {}
        self.dts: set[datetime] = set()
        self.days: int = 0

        # Orders & trades
        self.limit_order_count: int = 0
        self.limit_orders: dict[str, OrderData] = {}
        self.active_limit_orders: dict[str, OrderData] = {}
        self.trade_count: int = 0
        self.trades: dict[str, TradeData] = {}

        # Daily P&L
        self.daily_results: dict[date, PortfolioDailyResult] = {}
        self.daily_df: DataFrame | None = None

        # Logs
        self.logs: list[str] = []

    def clear_data(self) -> None:
        """Clear cached data from previous backtest run."""
        self.limit_order_count = 0
        self.limit_orders.clear()
        self.active_limit_orders.clear()
        self.trade_count = 0
        self.trades.clear()
        self.logs.clear()
        self.daily_results.clear()
        self.daily_df = None
        self.bars.clear()

    def set_parameters(
        self,
        vt_symbols: list[str],
        interval: Interval,
        start: datetime,
        rates: dict[str, float],
        slippages: dict[str, float],
        sizes: dict[str, float],
        priceticks: dict[str, float],
        capital: float = 1_000_000,
        end: datetime | None = None,
        risk_free: float = 0.0,
        annual_days: int = 240,
    ) -> None:
        """Set backtest parameters (vnpy-style per-contract dicts)."""
        self.vt_symbols = vt_symbols
        self.interval = interval
        self.rates = rates
        self.slippages = slippages
        self.sizes = sizes
        self.priceticks = priceticks
        self.start = start
        self.end = end.replace(hour=23, minute=59, second=59) if end else datetime.now()
        self.capital = capital
        self.risk_free = risk_free
        self.annual_days = annual_days

    def add_strategy(
        self, strategy_class: type, setting: dict | None = None
    ) -> None:
        """Add strategy class and instantiate it."""
        self.strategy_class = strategy_class
        self.strategy = strategy_class(
            self, strategy_class.__name__, copy(self.vt_symbols), setting or {}
        )

    def load_data(
        self, bars_dict: dict[str, list[BarData]] | None = None
    ) -> None:
        """
        Load historical bar data.
        If bars_dict is provided, use it directly (for testing).
        Otherwise load from database.
        """
        self.output("开始加载历史数据")
        self.history_data.clear()
        self.dts.clear()

        if bars_dict is not None:
            # Direct data injection (testing / external data source)
            for vt_symbol, bars in bars_dict.items():
                for bar in sorted(bars, key=lambda b: b.datetime):
                    self.dts.add(bar.datetime)
                    self.history_data[(bar.datetime, vt_symbol)] = bar
                self.output(f"{vt_symbol}历史数据加载完成，数据量：{len(bars)}")
        else:
            # Load from database (ccQuant DatabaseManager)
            for vt_symbol in self.vt_symbols:
                data = load_bar_data(
                    vt_symbol, self.interval, self.start, self.end
                )
                for bar in data:
                    self.dts.add(bar.datetime)
                    self.history_data[(bar.datetime, vt_symbol)] = bar
                self.output(f"{vt_symbol}历史数据加载完成，数据量：{len(data)}")

        self.output("所有历史数据加载完成")

    def run_backtesting(self) -> None:
        """Run the backtest loop (vnpy-style with init warmup)."""
        self.strategy.on_init()

        dts: list = sorted(self.dts)

        # Warmup phase: feed `self.days` calendar days for indicator init
        day_count: int = 0
        ix: int = 0

        for ix, dt in enumerate(dts):
            if self.datetime and dt.day != self.datetime.day:
                day_count += 1
                if day_count >= self.days:
                    break
            try:
                self.new_bars(dt)
            except Exception:
                self.output("触发异常，回测终止")
                self.output(traceback.format_exc())
                return

        self.strategy.inited = True
        self.output("策略初始化完成")

        self.strategy.on_start()
        self.strategy.trading = True
        self.output("开始回放历史数据")

        # Main backtest phase
        for dt in dts[ix:]:
            try:
                self.new_bars(dt)
            except Exception:
                self.output("触发异常，回测终止")
                self.output(traceback.format_exc())
                return

        self.output("历史数据回放结束")

    def new_bars(self, dt: datetime) -> None:
        """Process a new datetime slice."""
        self.datetime = dt

        bars: dict[str, BarData] = {}
        for vt_symbol in self.vt_symbols:
            bar: BarData | None = self.history_data.get((dt, vt_symbol))

            if bar:
                self.bars[vt_symbol] = bar
                bars[vt_symbol] = bar
            elif vt_symbol in self.bars:
                # Forward-fill with last close price
                old_bar = self.bars[vt_symbol]
                bar = BarData(
                    symbol=old_bar.symbol,
                    exchange=old_bar.exchange,
                    datetime=dt,
                    open_price=old_bar.close_price,
                    high_price=old_bar.close_price,
                    low_price=old_bar.close_price,
                    close_price=old_bar.close_price,
                    gateway_name=old_bar.gateway_name,
                )
                self.bars[vt_symbol] = bar
                bars[vt_symbol] = bar

        self.cross_limit_order()
        self.strategy.on_bars(bars)

        if self.strategy.inited:
            self.update_daily_close(self.bars, dt)

    def cross_limit_order(self) -> None:
        """Cross active limit and stop orders against current bars (vnpy matching)."""
        for order in list(self.active_limit_orders.values()):
            bar: BarData | None = self.bars.get(order.vt_symbol)
            if not bar:
                continue

            # Update order status
            if order.status == Status.SUBMITTING:
                order.status = Status.NOTTRADED
                self.strategy.update_order(order)

            if order.type == OrderType.LIMIT:
                long_cross_price: float = bar.low_price
                short_cross_price: float = bar.high_price
                long_best_price: float = bar.open_price
                short_best_price: float = bar.open_price

                long_cross: bool = (
                    order.direction == Direction.LONG
                    and order.price >= long_cross_price
                    and long_cross_price > 0
                )
                short_cross: bool = (
                    order.direction == Direction.SHORT
                    and order.price <= short_cross_price
                    and short_cross_price > 0
                )

                if not long_cross and not short_cross:
                    continue

                if long_cross:
                    trade_price = min(order.price, long_best_price)
                else:
                    trade_price = max(order.price, short_best_price)

            elif order.type == OrderType.STOP:
                long_cross: bool = (
                    order.direction == Direction.LONG
                    and bar.high_price >= order.price
                    and bar.high_price > 0
                )
                short_cross: bool = (
                    order.direction == Direction.SHORT
                    and bar.low_price <= order.price
                    and bar.low_price > 0
                )

                if not long_cross and not short_cross:
                    continue

                if long_cross:
                    trade_price = max(order.price, bar.open_price)
                else:
                    trade_price = min(order.price, bar.open_price)

            else:
                continue

            # Fill the order
            order.traded = order.volume
            order.status = Status.ALLTRADED
            self.strategy.update_order(order)

            if order.vt_orderid in self.active_limit_orders:
                self.active_limit_orders.pop(order.vt_orderid)

            # Record trade
            self.trade_count += 1
            trade = TradeData(
                symbol=order.symbol,
                exchange=order.exchange,
                orderid=order.orderid,
                tradeid=str(self.trade_count),
                direction=order.direction,
                offset=order.offset,
                price=trade_price,
                volume=order.volume,
                datetime=self.datetime,
                gateway_name=self.gateway_name,
            )

            self.strategy.update_trade(trade)
            self.trades[trade.vt_tradeid] = trade

    def update_daily_close(self, bars: dict[str, BarData], dt: datetime) -> None:
        """Update daily close prices for P&L calculation."""
        d: date = dt.date()
        close_prices: dict[str, float] = {
            bar.vt_symbol: bar.close_price for bar in bars.values()
        }

        daily_result = self.daily_results.get(d)
        if daily_result:
            daily_result.update_close_prices(close_prices)
        else:
            self.daily_results[d] = PortfolioDailyResult(d, close_prices)

    # ------------------------------------------------------------------
    # P&L calculation (vnpy daily mark-to-market)
    # ------------------------------------------------------------------

    def calculate_result(self) -> DataFrame | None:
        """Calculate daily mark-to-market P&L."""
        self.output("开始计算逐日盯市盈亏")

        if not self.daily_results:
            self.output("逐日盈亏数据为空，无法计算")
            return None

        # Assign trades to their respective daily results
        for trade in self.trades.values():
            d: date = trade.datetime.date()
            daily_result = self.daily_results.get(d)
            if daily_result:
                daily_result.add_trade(trade)

        # Calculate P&L day by day, passing forward pre_closes and start_poses
        pre_closes: dict[str, float] = {}
        start_poses: dict[str, float] = {}

        for daily_result in self.daily_results.values():
            daily_result.calculate_pnl(
                pre_closes, start_poses,
                self.sizes, self.rates, self.slippages,
            )
            pre_closes = daily_result.close_prices
            start_poses = daily_result.end_poses

        # Build DataFrame
        results: dict[str, list] = defaultdict(list)
        for daily_result in self.daily_results.values():
            for key in [
                "date", "trade_count", "turnover", "commission",
                "slippage", "trading_pnl", "holding_pnl",
                "total_pnl", "net_pnl",
            ]:
                results[key].append(getattr(daily_result, key))

        if results:
            self.daily_df = DataFrame.from_dict(results).set_index("date")

            # Pre-compute chart columns so they are available for frontend
            self.daily_df["balance"] = self.daily_df["net_pnl"].cumsum() + self.capital
            self.daily_df["return"] = np.log(
                self.daily_df["balance"] / self.daily_df["balance"].shift(1)
            ).fillna(0)
            self.daily_df["highlevel"] = self.daily_df["balance"].rolling(
                min_periods=1, window=len(self.daily_df), center=False
            ).max()
            self.daily_df["drawdown"] = self.daily_df["balance"] - self.daily_df["highlevel"]
            self.daily_df["ddpercent"] = self.daily_df["drawdown"] / self.daily_df["highlevel"] * 100

        self.output("逐日盯市盈亏计算完成")
        return self.daily_df

    def calculate_statistics(
        self, df: DataFrame | None = None, output: bool = True
    ) -> dict:
        """Calculate strategy performance statistics."""
        self.output("开始计算策略统计指标")

        if df is None:
            df = self.daily_df

        # Initialize all stats
        start_date: str = ""
        end_date: str = ""
        total_days: int = 0
        profit_days: int = 0
        loss_days: int = 0
        end_balance: float = 0
        max_drawdown: float = 0
        max_ddpercent: float = 0
        max_drawdown_duration: int = 0
        total_net_pnl: float = 0
        daily_net_pnl: float = 0
        total_commission: float = 0
        daily_commission: float = 0
        total_slippage: float = 0
        daily_slippage: float = 0
        total_turnover: float = 0
        daily_turnover: float = 0
        total_trade_count: int = 0
        daily_trade_count: float = 0
        total_return: float = 0
        annual_return: float = 0
        daily_return: float = 0
        return_std: float = 0
        sharpe_ratio: float = 0
        return_drawdown_ratio: float = 0

        positive_balance: bool = False

        if df is not None and not df.empty:
            # Use pre-computed columns from calculate_result if available
            if "balance" not in df.columns:
                df["balance"] = df["net_pnl"].cumsum() + self.capital
                df["return"] = np.log(
                    df["balance"] / df["balance"].shift(1)
                ).fillna(0)
                df["highlevel"] = df["balance"].rolling(
                    min_periods=1, window=len(df), center=False
                ).max()
                df["drawdown"] = df["balance"] - df["highlevel"]
                df["ddpercent"] = df["drawdown"] / df["highlevel"] * 100

            positive_balance = (df["balance"] > 0).all()
            if not positive_balance:
                self.output("回测中出现爆仓（资金<=0），无法计算统计指标")

        if positive_balance:
            start_date = df.index[0]
            end_date = df.index[-1]
            total_days = len(df)
            profit_days = len(df[df["net_pnl"] > 0])
            loss_days = len(df[df["net_pnl"] < 0])
            end_balance = df["balance"].iloc[-1]
            max_drawdown = df["drawdown"].min()
            max_ddpercent = df["ddpercent"].min()
            max_drawdown_end = df["drawdown"].idxmin()

            if isinstance(max_drawdown_end, date):
                max_drawdown_start = df["balance"][:max_drawdown_end].idxmax()
                max_drawdown_duration = (max_drawdown_end - max_drawdown_start).days
            else:
                max_drawdown_duration = 0

            total_net_pnl = df["net_pnl"].sum()
            daily_net_pnl = total_net_pnl / total_days
            total_commission = df["commission"].sum()
            daily_commission = total_commission / total_days
            total_slippage = df["slippage"].sum()
            daily_slippage = total_slippage / total_days
            total_turnover = df["turnover"].sum()
            daily_turnover = total_turnover / total_days
            total_trade_count = df["trade_count"].sum()
            daily_trade_count = total_trade_count / total_days

            total_return = (end_balance / self.capital - 1) * 100
            annual_return = total_return / total_days * self.annual_days
            daily_return = df["return"].mean() * 100
            return_std = df["return"].std() * 100

            if return_std:
                daily_risk_free = self.risk_free / np.sqrt(self.annual_days)
                sharpe_ratio = (
                    (daily_return - daily_risk_free) / return_std
                    * np.sqrt(self.annual_days)
                )

            if max_drawdown:
                return_drawdown_ratio = -total_net_pnl / max_drawdown

        if output:
            self.output("-" * 30)
            self.output(f"首个交易日：\t{start_date}")
            self.output(f"最后交易日：\t{end_date}")
            self.output(f"总交易日：\t{total_days}")
            self.output(f"盈利交易日：\t{profit_days}")
            self.output(f"亏损交易日：\t{loss_days}")
            self.output(f"起始资金：\t{self.capital:,.2f}")
            self.output(f"结束资金：\t{end_balance:,.2f}")
            self.output(f"总收益率：\t{total_return:,.2f}%")
            self.output(f"年化收益：\t{annual_return:,.2f}%")
            self.output(f"最大回撤：\t{max_drawdown:,.2f}")
            self.output(f"百分比最大回撤：{max_ddpercent:,.2f}%")
            self.output(f"最长回撤天数：\t{max_drawdown_duration}")
            self.output(f"总盈亏：\t{total_net_pnl:,.2f}")
            self.output(f"总手续费：\t{total_commission:,.2f}")
            self.output(f"总滑点：\t{total_slippage:,.2f}")
            self.output(f"总成交金额：\t{total_turnover:,.2f}")
            self.output(f"总成交笔数：\t{total_trade_count}")
            self.output(f"日均盈亏：\t{daily_net_pnl:,.2f}")
            self.output(f"Sharpe Ratio：\t{sharpe_ratio:,.2f}")
            self.output(f"收益回撤比：\t{return_drawdown_ratio:,.2f}")

        statistics: dict = {
            "start_date": start_date,
            "end_date": end_date,
            "total_days": total_days,
            "profit_days": profit_days,
            "loss_days": loss_days,
            "capital": self.capital,
            "end_balance": end_balance,
            "max_drawdown": max_drawdown,
            "max_ddpercent": max_ddpercent,
            "max_drawdown_duration": max_drawdown_duration,
            "total_net_pnl": total_net_pnl,
            "daily_net_pnl": daily_net_pnl,
            "total_commission": total_commission,
            "daily_commission": daily_commission,
            "total_slippage": total_slippage,
            "daily_slippage": daily_slippage,
            "total_turnover": total_turnover,
            "daily_turnover": daily_turnover,
            "total_trade_count": total_trade_count,
            "daily_trade_count": daily_trade_count,
            "total_return": total_return,
            "annual_return": annual_return,
            "daily_return": daily_return,
            "return_std": return_std,
            "sharpe_ratio": sharpe_ratio,
            "return_drawdown_ratio": return_drawdown_ratio,
        }

        for key, value in statistics.items():
            if value in (np.inf, -np.inf):
                value = 0
            # Convert numpy types to Python native types for JSON serialization
            val = np.nan_to_num(value)
            statistics[key] = float(val) if isinstance(val, (np.floating, np.integer)) else val

        self.output("策略统计指标计算完成")
        return statistics

    # ------------------------------------------------------------------
    # Plotly chart (vnpy 4-subplot style)
    # ------------------------------------------------------------------

    def show_chart(self, df: DataFrame | None = None) -> go.Figure | None:
        """Generate vnpy-style 4-subplot Plotly chart. Returns Figure for API use."""
        if df is None:
            df = self.daily_df
        if df is None or df.empty:
            return None

        fig = make_subplots(
            rows=4, cols=1,
            subplot_titles=["Balance", "Drawdown", "Daily Pnl", "Pnl Distribution"],
            vertical_spacing=0.06,
        )

        fig.add_trace(
            go.Scatter(x=df.index, y=df["balance"], mode="lines", name="Balance"),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["drawdown"],
                fillcolor="red", fill="tozeroy", mode="lines", name="Drawdown",
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Bar(x=df.index, y=df["net_pnl"], name="Daily Pnl"),
            row=3, col=1,
        )
        fig.add_trace(
            go.Histogram(x=df["net_pnl"], nbinsx=100, name="Days"),
            row=4, col=1,
        )

        fig.update_layout(height=1000, width=1000)
        return fig

    def get_chart_json(self, df: DataFrame | None = None) -> str | None:
        """Return chart as Plotly JSON string for frontend rendering."""
        fig = self.show_chart(df)
        if fig is None:
            return None
        return fig.to_json()

    # ------------------------------------------------------------------
    # Optimization
    # ------------------------------------------------------------------

    def run_bf_optimization(
        self,
        optimization_setting: OptimizationSetting,
        output: bool = True,
        max_workers: int | None = None,
        bars_dict: dict[str, list[BarData]] | None = None,
    ) -> list:
        """Brute-force parameter optimization."""
        evaluate_func = wrap_evaluate(self, optimization_setting.target_name, bars_dict)
        results = run_bf_optimization(
            evaluate_func, optimization_setting, max_workers, self.output
        )
        if output:
            for result in results:
                self.output(f"参数：{result[0]}, 目标：{result[1]}")
        return results

    run_optimization = run_bf_optimization

    def run_ga_optimization(
        self,
        optimization_setting: OptimizationSetting,
        max_workers: int | None = None,
        ngen: int = 30,
        output: bool = True,
        bars_dict: dict[str, list[BarData]] | None = None,
    ) -> list:
        """Genetic algorithm parameter optimization."""
        evaluate_func = wrap_evaluate(self, optimization_setting.target_name, bars_dict)
        results = run_ga_optimization(
            evaluate_func, optimization_setting, max_workers, ngen,
            output=self.output,
        )
        if output:
            for result in results:
                self.output(f"参数：{result[0]}, 目标：{result[1]}")
        return results

    # ------------------------------------------------------------------
    # Order management (called by strategy template)
    # ------------------------------------------------------------------

    def send_order(
        self,
        strategy: Any,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False,
    ) -> list[str]:
        """Send a limit or stop order (vnpy interface)."""
        price = round_to(price, self.priceticks.get(vt_symbol, 0.0001))
        symbol, exchange = extract_vt_symbol(vt_symbol)

        self.limit_order_count += 1

        order = OrderData(
            symbol=symbol,
            exchange=exchange,
            orderid=str(self.limit_order_count),
            type=OrderType.STOP if stop else OrderType.LIMIT,
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            status=Status.SUBMITTING,
            datetime=self.datetime,
            gateway_name=self.gateway_name,
        )

        self.active_limit_orders[order.vt_orderid] = order
        self.limit_orders[order.vt_orderid] = order
        return [order.vt_orderid]

    def cancel_order(self, strategy: Any, vt_orderid: str) -> None:
        """Cancel an active order."""
        if vt_orderid not in self.active_limit_orders:
            return
        order = self.active_limit_orders.pop(vt_orderid)
        order.status = Status.CANCELLED
        self.strategy.update_order(order)

    # ------------------------------------------------------------------
    # Strategy interface helpers
    # ------------------------------------------------------------------

    def load_bars(self, strategy: Any, days: int, interval: Interval) -> None:
        """Set warmup days for strategy initialization."""
        self.days = days

    def write_log(self, msg: str, strategy: Any = None) -> None:
        msg = f"{self.datetime}\t{msg}"
        self.logs.append(msg)

    def send_email(self, msg: str, strategy: Any = None) -> None:
        pass

    def sync_strategy_data(self, strategy: Any) -> None:
        pass

    def get_pricetick(self, strategy: Any, vt_symbol: str) -> float:
        return self.priceticks.get(vt_symbol, 0.0001)

    def get_size(self, strategy: Any, vt_symbol: str) -> float:
        return self.sizes.get(vt_symbol, 1.0)

    def put_strategy_event(self, strategy: Any) -> None:
        pass

    def output(self, msg: str) -> None:
        print(f"{datetime.now()}\t{msg}")

    # ------------------------------------------------------------------
    # Data accessors
    # ------------------------------------------------------------------

    def get_all_trades(self) -> list[TradeData]:
        return list(self.trades.values())

    def get_all_orders(self) -> list[OrderData]:
        return list(self.limit_orders.values())

    def get_all_daily_results(self) -> list[PortfolioDailyResult]:
        return list(self.daily_results.values())

    def get_trades_df(self) -> list[dict]:
        """Return trades as list of dicts for JSON serialization."""
        return [
            {
                "datetime": t.datetime.isoformat() if t.datetime else None,
                "vt_symbol": t.vt_symbol,
                "direction": t.direction.value if t.direction else None,
                "offset": t.offset.value,
                "price": t.price,
                "volume": t.volume,
                "tradeid": t.tradeid,
                "orderid": t.orderid,
            }
            for t in self.trades.values()
        ]

    def get_orders_df(self) -> list[dict]:
        """Return orders as list of dicts for JSON serialization."""
        return [
            {
                "datetime": o.datetime.isoformat() if o.datetime else None,
                "vt_symbol": o.vt_symbol,
                "direction": o.direction.value if o.direction else None,
                "offset": o.offset.value,
                "price": o.price,
                "volume": o.volume,
                "traded": o.traded,
                "status": o.status.value,
                "orderid": o.orderid,
            }
            for o in self.limit_orders.values()
        ]

    def get_daily_results_df(self) -> list[dict]:
        """Return daily results as list of dicts for JSON serialization."""
        result = []
        for dr in self.daily_results.values():
            result.append({
                "date": str(dr.date),
                "trade_count": int(dr.trade_count) if isinstance(dr.trade_count, (np.integer, int)) else dr.trade_count,
                "turnover": float(dr.turnover) if isinstance(dr.turnover, (np.floating, float)) else dr.turnover,
                "commission": float(dr.commission) if isinstance(dr.commission, (np.floating, float)) else dr.commission,
                "slippage": float(dr.slippage) if isinstance(dr.slippage, (np.floating, float)) else dr.slippage,
                "trading_pnl": float(dr.trading_pnl) if isinstance(dr.trading_pnl, (np.floating, float)) else dr.trading_pnl,
                "holding_pnl": float(dr.holding_pnl) if isinstance(dr.holding_pnl, (np.floating, float)) else dr.holding_pnl,
                "total_pnl": float(dr.total_pnl) if isinstance(dr.total_pnl, (np.floating, float)) else dr.total_pnl,
                "net_pnl": float(dr.net_pnl) if isinstance(dr.net_pnl, (np.floating, float)) else dr.net_pnl,
            })
        return result

    def get_daily_df_records(self) -> list[dict]:
        """Return daily_df (with balance/drawdown/return columns) as list of dicts."""
        if self.daily_df is None or self.daily_df.empty:
            return []
        df = self.daily_df.copy()
        df["date"] = df.index.astype(str)
        records = []
        for _, row in df.iterrows():
            rec = {}
            for col in df.columns:
                val = row[col]
                if isinstance(val, (np.floating, np.integer)):
                    rec[col] = float(val)
                else:
                    rec[col] = val
            records.append(rec)
        return records


# ------------------------------------------------------------------
# Module-level helpers for optimization multiprocessing
# ------------------------------------------------------------------

@lru_cache(maxsize=999)
def load_bar_data(
    vt_symbol: str,
    interval: Interval,
    start: datetime,
    end: datetime,
) -> list[BarData]:
    """Load bar data from ccQuant database."""
    from ccquant.database import db as database_manager

    symbol, exchange = extract_vt_symbol(vt_symbol)
    exchange_str = exchange.value

    # Use ccQuant's DatabaseManager to load data
    import pandas as pd
    df = database_manager.get_option_bars(symbol, start.date(), end.date())

    # Fallback: database may store symbols with exchange suffix (e.g. 10000001.SH)
    if df.empty:
        for suffix in [".SH", ".SZ", ".SSE"]:
            df = database_manager.get_option_bars(symbol + suffix, start.date(), end.date())
            if not df.empty:
                symbol = symbol + suffix
                break

    if df.empty:
        # Try underlying bars
        df = database_manager.get_underlying_bars(symbol, start.date(), end.date())

    if df.empty:
        return []

    bars: list[BarData] = []
    for _, row in df.iterrows():
        bar = BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=datetime.combine(
                pd.to_datetime(row["trade_date"]).date(),
                datetime.min.time(),
            ),
            interval=interval,
            open_price=float(row.get("open", row.get("open_price", 0))),
            high_price=float(row.get("high", row.get("high_price", 0))),
            low_price=float(row.get("low", row.get("low_price", 0))),
            close_price=float(row.get("close", row.get("close_price", 0))),
            volume=float(row.get("volume", 0)),
            gateway_name="DATABASE",
        )
        # Ensure bar.vt_symbol matches the original vt_symbol argument
        # in case suffix fallback changed the local symbol/exchange.
        bar.vt_symbol = vt_symbol
        bars.append(bar)

    return bars


def evaluate(
    target_name: str,
    strategy_class: type,
    vt_symbols: list[str],
    interval: Interval,
    start: datetime,
    rates: dict[str, float],
    slippages: dict[str, float],
    sizes: dict[str, float],
    priceticks: dict[str, float],
    capital: float,
    end: datetime,
    setting: dict,
    bars_dict: dict[str, list[BarData]] | None = None,
) -> tuple:
    """Evaluate a single parameter combination (runs in subprocess)."""
    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbols=vt_symbols,
        interval=interval,
        start=start,
        rates=rates,
        slippages=slippages,
        sizes=sizes,
        priceticks=priceticks,
        capital=capital,
        end=end,
    )
    engine.add_strategy(strategy_class, setting)
    if bars_dict is not None:
        engine.load_data(bars_dict)
    else:
        engine.load_data()
    engine.run_backtesting()
    engine.calculate_result()
    statistics: dict = engine.calculate_statistics(output=False)
    target_value: float = statistics.get(target_name, 0)
    return (str(setting), target_value, statistics)


def wrap_evaluate(
    engine: BacktestingEngine,
    target_name: str,
    bars_dict: dict[str, list[BarData]] | None = None,
) -> Callable:
    """Wrap evaluate with engine's current config for multiprocessing."""
    func = partial(
        evaluate,
        target_name,
        engine.strategy_class,
        engine.vt_symbols,
        engine.interval,
        engine.start,
        engine.rates,
        engine.slippages,
        engine.sizes,
        engine.priceticks,
        engine.capital,
        engine.end,
        bars_dict=bars_dict,
    )
    return func
