"""
General utility functions.
"""

import json
import sys
from datetime import datetime, time
from pathlib import Path
from collections.abc import Callable
from decimal import Decimal
from math import floor, ceil

from .object import BarData, TickData
from .constant import Exchange, Interval


def extract_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    """
    :return: (symbol, exchange)
    """
    symbol, exchange_str = vt_symbol.rsplit(".", 1)
    return symbol, Exchange(exchange_str)


def generate_vt_symbol(symbol: str, exchange: Exchange) -> str:
    """
    return vt_symbol
    """
    return f"{symbol}.{exchange.value}"


def _get_trader_dir(temp_name: str) -> tuple[Path, Path]:
    """
    Get path where trader is running in.
    """
    cwd: Path = Path.cwd()
    temp_path: Path = cwd.joinpath(temp_name)

    if temp_path.exists():
        return cwd, temp_path

    home_path: Path = Path.home()
    temp_path = home_path.joinpath(temp_name)

    if not temp_path.exists():
        temp_path.mkdir()

    return home_path, temp_path


TRADER_DIR, TEMP_DIR = _get_trader_dir(".ccquant")
sys.path.append(str(TRADER_DIR))


def get_file_path(filename: str) -> Path:
    """
    Get path for temp file with filename.
    """
    return TEMP_DIR.joinpath(filename)


def get_folder_path(folder_name: str) -> Path:
    """
    Get path for temp folder with folder name.
    """
    folder_path: Path = TEMP_DIR.joinpath(folder_name)
    if not folder_path.exists():
        folder_path.mkdir()
    return folder_path


def load_json(filename: str) -> dict:
    """
    Load data from json file in temp path.
    """
    filepath: Path = get_file_path(filename)

    if filepath.exists():
        with open(filepath, encoding="UTF-8") as f:
            data: dict = json.load(f)
        return data
    else:
        save_json(filename, {})
        return {}


def save_json(filename: str, data: dict) -> None:
    """
    Save data into json file in temp path.
    """
    filepath: Path = get_file_path(filename)
    with open(filepath, mode="w+", encoding="UTF-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )


def round_to(value: float, target: float) -> float:
    """
    Round price to price tick value.
    """
    decimal_value: Decimal = Decimal(str(value))
    decimal_target: Decimal = Decimal(str(target))
    rounded: float = float(int(round(decimal_value / decimal_target)) * decimal_target)
    return rounded


def floor_to(value: float, target: float) -> float:
    """
    Similar to math.floor function, but to target float number.
    """
    decimal_value: Decimal = Decimal(str(value))
    decimal_target: Decimal = Decimal(str(target))
    result: float = float(int(floor(decimal_value / decimal_target)) * decimal_target)
    return result


def ceil_to(value: float, target: float) -> float:
    """
    Similar to math.ceil function, but to target float number.
    """
    decimal_value: Decimal = Decimal(str(value))
    decimal_target: Decimal = Decimal(str(target))
    result: float = float(int(ceil(decimal_value / decimal_target)) * decimal_target)
    return result


def get_digits(value: float) -> int:
    """
    Get number of digits after decimal point.
    """
    value_str: str = str(value)

    if "e-" in value_str:
        _, buf = value_str.split("e-")
        return int(buf)
    elif "." in value_str:
        _, buf = value_str.split(".")
        return len(buf)
    else:
        return 0


class BarGenerator:
    """
    For:
    1. generating 1 minute bar data from tick data
    2. generating x minute bar/x hour bar data from 1 minute data
    Notice:
    1. for x minute bar, x must be able to divide 60: 2, 3, 5, 6, 10, 15, 20, 30
    2. for x hour bar, x can be any number
    """

    def __init__(
        self,
        on_bar: Callable,
        window: int = 0,
        on_window_bar: Callable | None = None,
        interval: Interval = Interval.MINUTE,
        daily_end: time | None = None
    ) -> None:
        """Constructor"""
        self.bar: BarData | None = None
        self.on_bar: Callable = on_bar

        self.interval: Interval = interval
        self.interval_count: int = 0

        self.hour_bar: BarData | None = None
        self.daily_bar: BarData | None = None

        self.window: int = window
        self.window_bar: BarData | None = None
        self.on_window_bar: Callable | None = on_window_bar

        self.last_tick: TickData | None = None

        self.daily_end: time | None = daily_end
        if self.interval == Interval.DAILY and not self.daily_end:
            raise RuntimeError("daily_end is required for daily bar generation")

    def update_tick(self, tick: TickData) -> None:
        """
        Update new tick data into generator.
        """
        new_minute: bool = False

        if not tick.last_price:
            return

        if not self.bar:
            new_minute = True
        elif (
            (self.bar.datetime.minute != tick.datetime.minute)
            or (self.bar.datetime.hour != tick.datetime.hour)
        ):
            self.bar.datetime = self.bar.datetime.replace(
                second=0, microsecond=0
            )
            self.on_bar(self.bar)

            new_minute = True

        if new_minute:
            self.bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.MINUTE,
                datetime=tick.datetime,
                gateway_name=tick.gateway_name,
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                open_interest=tick.open_interest
            )
        elif self.bar:
            self.bar.high_price = max(self.bar.high_price, tick.last_price)
            if self.last_tick and tick.high_price > self.last_tick.high_price:
                self.bar.high_price = max(self.bar.high_price, tick.high_price)

            self.bar.low_price = min(self.bar.low_price, tick.last_price)
            if self.last_tick and tick.low_price < self.last_tick.low_price:
                self.bar.low_price = min(self.bar.low_price, tick.low_price)

            self.bar.close_price = tick.last_price
            self.bar.open_interest = tick.open_interest
            self.bar.datetime = tick.datetime

        if self.last_tick and self.bar:
            volume_change: float = tick.volume - self.last_tick.volume
            self.bar.volume += max(volume_change, 0)

            turnover_change: float = tick.turnover - self.last_tick.turnover
            self.bar.turnover += max(turnover_change, 0)

        self.last_tick = tick

    def update_bar(self, bar: BarData) -> None:
        """
        Update 1 minute bar into generator
        """
        if self.interval == Interval.MINUTE:
            self.update_bar_minute_window(bar)
        elif self.interval == Interval.HOUR:
            self.update_bar_hour_window(bar)
        else:
            self.update_bar_daily_window(bar)

    def update_bar_minute_window(self, bar: BarData) -> None:
        """"""
        if not self.window_bar:
            dt: datetime = bar.datetime.replace(second=0, microsecond=0)
            self.window_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        else:
            self.window_bar.high_price = max(
                self.window_bar.high_price,
                bar.high_price
            )
            self.window_bar.low_price = min(
                self.window_bar.low_price,
                bar.low_price
            )

        self.window_bar.close_price = bar.close_price
        self.window_bar.volume += bar.volume
        self.window_bar.turnover += bar.turnover
        self.window_bar.open_interest = bar.open_interest

        self.interval_count += 1
        if not self.interval_count % self.window:
            self.on_window_bar(self.window_bar)
            self.window_bar = None

    def update_bar_hour_window(self, bar: BarData) -> None:
        """"""
        if not self.hour_bar:
            dt: datetime = bar.datetime.replace(minute=0, second=0, microsecond=0)
            self.hour_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        else:
            self.hour_bar.high_price = max(
                self.hour_bar.high_price,
                bar.high_price
            )
            self.hour_bar.low_price = min(
                self.hour_bar.low_price,
                bar.low_price
            )

        self.hour_bar.close_price = bar.close_price
        self.hour_bar.volume += bar.volume
        self.hour_bar.turnover += bar.turnover
        self.hour_bar.open_interest = bar.open_interest

        self.interval_count += 1
        if not self.interval_count % self.window:
            self.on_window_bar(self.hour_bar)
            self.hour_bar = None

    def update_bar_daily_window(self, bar: BarData) -> None:
        """"""
        if not self.daily_bar:
            dt: datetime = bar.datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            self.daily_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        else:
            self.daily_bar.high_price = max(
                self.daily_bar.high_price,
                bar.high_price
            )
            self.daily_bar.low_price = min(
                self.daily_bar.low_price,
                bar.low_price
            )

        self.daily_bar.close_price = bar.close_price
        self.daily_bar.volume += bar.volume
        self.daily_bar.turnover += bar.turnover
        self.daily_bar.open_interest = bar.open_interest

        if bar.datetime.time() == self.daily_end:
            self.on_window_bar(self.daily_bar)
            self.daily_bar = None


class ArrayManager:
    """
    Lightweight technical indicator calculator for backtesting.
    Mirrors vnpy's ArrayManager interface.
    """

    def __init__(self, size: int = 100) -> None:
        self.count: int = 0
        self.size: int = size
        self.inited: bool = False
        self.close_array: list[float] = []
        self.high_array: list[float] = []
        self.low_array: list[float] = []
        self.open_array: list[float] = []
        self.volume_array: list[float] = []

    def update_bar(self, bar: BarData) -> None:
        """Append new bar data."""
        self.count += 1

        self.close_array.append(bar.close_price)
        self.high_array.append(bar.high_price)
        self.low_array.append(bar.low_price)
        self.open_array.append(bar.open_price)
        self.volume_array.append(bar.volume)

        # Keep fixed size window
        if len(self.close_array) > self.size:
            self.close_array.pop(0)
            self.high_array.pop(0)
            self.low_array.pop(0)
            self.open_array.pop(0)
            self.volume_array.pop(0)

        if not self.inited and self.count >= self.size:
            self.inited = True

    @property
    def open(self) -> list[float]:
        return self.open_array

    @property
    def high(self) -> list[float]:
        return self.high_array

    @property
    def low(self) -> list[float]:
        return self.low_array

    @property
    def close(self) -> list[float]:
        return self.close_array

    @property
    def volume(self) -> list[float]:
        return self.volume_array

    def sma(self, n: int, array: bool = False) -> float | list[float]:
        """Simple moving average."""
        import numpy as np
        result = np.convolve(self.close_array, np.ones(n) / n, mode='valid')
        if array:
            return result.tolist()
        return float(result[-1]) if len(result) > 0 else 0.0

    def std(self, n: int, array: bool = False) -> float | list[float]:
        """Standard deviation."""
        import numpy as np
        if len(self.close_array) < n:
            return 0.0 if not array else []
        result = np.array([
            np.std(self.close_array[i - n:i], ddof=1)
            for i in range(n, len(self.close_array) + 1)
        ])
        if array:
            return result.tolist()
        return float(result[-1]) if len(result) > 0 else 0.0

    def ema(self, n: int, array: bool = False) -> float | list[float]:
        """Exponential moving average."""
        import numpy as np
        if len(self.close_array) < n:
            return 0.0 if not array else []
        weights = np.exp(np.linspace(-1., 0., n))
        weights /= weights.sum()
        result = np.convolve(self.close_array, weights, mode='valid')
        if array:
            return result.tolist()
        return float(result[-1]) if len(result) > 0 else 0.0

    def atr(self, n: int, array: bool = False) -> float | list[float]:
        """Average true range."""
        import numpy as np
        if len(self.close_array) < n + 1:
            return 0.0 if not array else []
        prev_close = np.array(self.close_array[:-1])
        high = np.array(self.high_array[1:])
        low = np.array(self.low_array[1:])
        tr1 = high - low
        tr2 = np.abs(high - prev_close)
        tr3 = np.abs(low - prev_close)
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        result = np.convolve(tr, np.ones(n) / n, mode='valid')
        if array:
            return result.tolist()
        return float(result[-1]) if len(result) > 0 else 0.0

    def rsi(self, n: int, array: bool = False) -> float | list[float]:
        """Relative strength index."""
        import numpy as np
        if len(self.close_array) < n + 1:
            return 0.0 if not array else []
        deltas = np.diff(self.close_array)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gains = np.convolve(gains, np.ones(n) / n, mode='valid')
        avg_losses = np.convolve(losses, np.ones(n) / n, mode='valid')
        rs = avg_gains / (avg_losses + 1e-10)
        result = 100 - (100 / (1 + rs))
        if array:
            return result.tolist()
        return float(result[-1]) if len(result) > 0 else 0.0

    def cci(self, n: int, array: bool = False) -> float | list[float]:
        """Commodity channel index."""
        import numpy as np
        if len(self.close_array) < n:
            return 0.0 if not array else []
        tp = (np.array(self.high_array) + np.array(self.low_array) + np.array(self.close_array)) / 3
        ma = np.convolve(tp, np.ones(n) / n, mode='valid')
        std = np.array([np.std(tp[i - n:i], ddof=1) for i in range(n, len(tp) + 1)])
        result = (tp[n - 1:] - ma) / (0.015 * (std + 1e-10))
        if array:
            return result.tolist()
        return float(result[-1]) if len(result) > 0 else 0.0

    def boll(self, n: int, dev: float, array: bool = False) -> tuple[float, float] | tuple[list[float], list[float]]:
        """Bollinger bands."""
        import numpy as np
        if len(self.close_array) < n:
            return 0.0, 0.0 if not array else ([], [])
        closes = np.array(self.close_array)
        ma = np.convolve(closes, np.ones(n) / n, mode='valid')
        std = np.array([np.std(closes[i - n:i], ddof=1) for i in range(n, len(closes) + 1)])
        up = ma + dev * std
        down = ma - dev * std
        if array:
            return up.tolist(), down.tolist()
        return float(up[-1]), float(down[-1])

    def keltner(self, n: int, dev: float, array: bool = False) -> tuple[float, float] | tuple[list[float], list[float]]:
        """Keltner channel."""
        import numpy as np
        if len(self.close_array) < n:
            return 0.0, 0.0 if not array else ([], [])
        closes = np.array(self.close_array)
        ma = np.convolve(closes, np.ones(n) / n, mode='valid')
        atr_vals = np.array(self.atr(n, array=True) or [0.0])
        up = ma + dev * atr_vals
        down = ma - dev * atr_vals
        if array:
            return up.tolist(), down.tolist()
        return float(up[-1]), float(down[-1])

    def donchian(self, n: int, array: bool = False) -> tuple[float, float] | tuple[list[float], list[float]]:
        """Donchian channel."""
        import numpy as np
        if len(self.high_array) < n:
            return 0.0, 0.0 if not array else ([], [])
        high = np.array(self.high_array)
        low = np.array(self.low_array)
        up = np.array([np.max(high[i - n + 1:i + 1]) for i in range(n - 1, len(high))])
        down = np.array([np.min(low[i - n + 1:i + 1]) for i in range(n - 1, len(low))])
        if array:
            return up.tolist(), down.tolist()
        return float(up[-1]), float(down[-1])
