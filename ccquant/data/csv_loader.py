"""
CSV / Parquet data loader for option backtesting.
"""

from datetime import datetime
from pathlib import Path
from typing import Literal

import polars as pl

from ccquant.core.constant import Exchange, Interval
from ccquant.core.object import BarData, ContractData
from ccquant.core.constant import Product, OptionType


def load_option_bars_from_csv(
    filepath: str | Path,
    symbol_col: str = "symbol",
    exchange_col: str | None = None,
    datetime_col: str = "datetime",
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volume_col: str = "volume",
    dt_format: str | None = None,
    exchange: Exchange = Exchange.SSE,
    interval: Interval = Interval.DAILY,
    implied_vol_col: str | None = None,
) -> list[BarData]:
    """
    Load option bar data from a CSV file into a list of BarData.

    Expected columns (renamable via parameters):
        - symbol, datetime, open, high, low, close, volume
    Optional:
        - implied volatility column for Greeks calculation
    """
    df = pl.read_csv(filepath, try_parse_dates=(dt_format is None))

    if dt_format and df[datetime_col].dtype == pl.Utf8:
        df = df.with_columns(
            pl.col(datetime_col).str.to_datetime(dt_format)
        )

    bars: list[BarData] = []
    for row in df.iter_rows(named=True):
        symbol = row[symbol_col]
        dt = row[datetime_col]
        if not isinstance(dt, datetime):
            dt = datetime.fromisoformat(str(dt))

        extra: dict[str, float] = {}
        if implied_vol_col and implied_vol_col in row:
            extra["implied_vol"] = float(row[implied_vol_col])

        bar = BarData(
            symbol=str(symbol),
            exchange=exchange,
            datetime=dt,
            interval=interval,
            open_price=float(row[open_col]),
            high_price=float(row[high_col]),
            low_price=float(row[low_col]),
            close_price=float(row[close_col]),
            volume=float(row.get(volume_col, 0)),
            gateway_name="CSV",
            extra=extra,
        )
        bars.append(bar)

    return bars


def load_contracts_from_csv(
    filepath: str | Path,
    symbol_col: str = "symbol",
    exchange_col: str = "exchange",
    strike_col: str = "strike",
    option_type_col: str = "option_type",
    expiry_col: str = "expiry",
    underlying_col: str = "underlying",
    size_col: str = "size",
    pricetick_col: str = "pricetick",
    dt_format: str | None = "%Y-%m-%d",
) -> list[ContractData]:
    """
    Load option contract definitions from a CSV file.

    Expected columns:
        symbol, exchange, strike, option_type, expiry, underlying, size, pricetick
    """
    df = pl.read_csv(filepath, try_parse_dates=(dt_format is None))

    if dt_format and df[expiry_col].dtype == pl.Utf8:
        df = df.with_columns(
            pl.col(expiry_col).str.to_datetime(dt_format)
        )

    contracts: list[ContractData] = []
    for row in df.iter_rows(named=True):
        exchange_val = Exchange(row[exchange_col])
        opt_type = OptionType.CALL if str(row[option_type_col]).upper() == "CALL" else OptionType.PUT
        expiry = row[expiry_col]
        if not isinstance(expiry, datetime):
            expiry = datetime.fromisoformat(str(expiry))

        contract = ContractData(
            symbol=str(row[symbol_col]),
            exchange=exchange_val,
            name=str(row[symbol_col]),
            product=Product.OPTION,
            size=float(row[size_col]),
            pricetick=float(row[pricetick_col]),
            option_strike=float(row[strike_col]),
            option_type=opt_type,
            option_expiry=expiry,
            option_underlying=str(row[underlying_col]),
            gateway_name="CSV",
        )
        contracts.append(contract)

    return contracts
