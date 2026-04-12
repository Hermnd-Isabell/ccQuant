"""
FastAPI backend server for ccQuant Web UI.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Any, Literal

import uvicorn
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ccquant.database import db, OptionDailyBar, OptionContract, DailyBar, Underlying, RiskFreeRate

# ========== App Setup ==========

app = FastAPI(title="ccQuant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STRATEGY_DIR = Path(__file__).resolve().parent.parent / "strategy"


# ========== Helper ==========

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _date_str(d: date | None) -> str | None:
    if d is None:
        return None
    return d.isoformat() if hasattr(d, 'isoformat') else str(d)

# ========== Data: Underlyings ==========

@app.get("/api/data/underlyings")
def get_underlyings() -> list[dict]:
    underlyings = db.get_underlyings()
    return [
        {"symbol": u.symbol, "name": u.name, "type": u.underlying_type, "exchange": u.exchange}
        for u in underlyings
    ]


@app.get("/api/data/underlyings/{symbol}/contracts")
def get_underlying_contracts(
    symbol: str,
    expiry: str | None = None,
) -> list[dict]:
    """获取标的下期权合约列表，可按到期日筛选"""
    with db.get_session() as session:
        q = (
            session.query(OptionContract)
            .filter(OptionContract.underlying_symbol == symbol)
        )
        if expiry:
            q = q.filter(OptionContract.expiry_date == _parse_date(expiry))
        contracts = q.order_by(OptionContract.expiry_date, OptionContract.strike).all()
        return [
            {
                "symbol": c.symbol,
                "type": c.option_type,
                "strike": float(c.strike),
                "expiry": _date_str(c.expiry_date),
                "contractMonth": c.contract_month,
            }
            for c in contracts
        ]


@app.get("/api/data/underlyings/{symbol}/expiries")
def get_expiry_dates(symbol: str) -> list[str]:
    dates = db.get_expiry_dates(symbol)
    return [d.isoformat() for d in dates]


@app.get("/api/data/underlyings/{symbol}/trade-dates")
def get_trade_dates(symbol: str) -> list[str]:
    with db.get_session() as session:
        rows = (
            session.query(OptionDailyBar.trade_date)
            .join(OptionContract, OptionDailyBar.symbol == OptionContract.symbol)
            .filter(OptionContract.underlying_symbol == symbol)
            .distinct()
            .order_by(OptionDailyBar.trade_date)
            .all()
        )
        return [_date_str(r[0]) for r in rows]


# ========== Data: Query (with filters) ==========

@app.get("/api/data/option-bars")
def get_option_bars(
    underlying: str = Query(...),
    page: int = 1,
    page_size: int = 200,
    expiry: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """分页查询期权K线，所有筛选条件都生效"""
    rows, total = db.query_option_bars_page(
        underlying=underlying,
        page=page,
        page_size=page_size,
        expiry=_parse_date(expiry),
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        symbol_like=search or None,
    )
    data = [
        {
            "trade_date": _date_str(b.trade_date),
            "symbol": b.symbol,
            "open": b.open_price,
            "high": b.high_price,
            "low": b.low_price,
            "close": b.close_price,
            "volume": b.volume,
            "amount": b.amount,
            "iv": b.iv,
            "delta": b.delta,
            "gamma": b.gamma,
            "theta": b.theta,
            "vega": b.vega,
            "rho": b.rho,
        }
        for b in rows
    ]
    return {"data": data, "total": total}


@app.get("/api/data/merged-bars")
def get_merged_bars(
    underlying: str = Query(...),
    page: int = 1,
    page_size: int = 200,
    expiry: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """期权K线 + 标的K线合并查询，按 trade_date 匹配"""
    rows, total = db.query_merged_bars_page(
        underlying=underlying,
        page=page,
        page_size=page_size,
        expiry=_parse_date(expiry),
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        symbol_like=search or None,
    )
    data = [
        {
            "trade_date": _date_str(r['trade_date']),
            "symbol": r['symbol'],
            "open": r['open_price'],
            "high": r['high_price'],
            "low": r['low_price'],
            "close": r['close_price'],
            "volume": r['volume'],
            "amount": r['amount'],
            "iv": r['iv'],
            "delta": r['delta'],
            "gamma": r['gamma'],
            "theta": r['theta'],
            "vega": r['vega'],
            "rho": r['rho'],
            "fund_open": r['fund_open'],
            "fund_high": r['fund_high'],
            "fund_low": r['fund_low'],
            "fund_close": r['fund_close'],
            "fund_volume": r['fund_volume'],
            "fund_amount": r['fund_amount'],
        }
        for r in rows
    ]
    return {"data": data, "total": total}


@app.get("/api/data/daily-bars")
def get_daily_bars(
    symbol: str = Query(...),
    page: int = 1,
    page_size: int = 200,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """分页查询标的K线"""
    rows, total = db.query_daily_bars_page(
        symbol=symbol,
        page=page,
        page_size=page_size,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )
    data = [
        {
            "trade_date": _date_str(b.trade_date),
            "open": b.open_price,
            "high": b.high_price,
            "low": b.low_price,
            "close": b.close_price,
            "volume": b.volume,
            "amount": b.amount,
        }
        for b in rows
    ]
    return {"data": data, "total": total}


# ========== Data: Stats (filtered) ==========

@app.get("/api/data/stats")
def get_data_stats(
    underlying: str = Query(...),
    expiry: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """返回当前筛选条件下的统计数据"""
    exp = _parse_date(expiry)
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    sl = search or None

    option_bar_count = db.count_option_bars(
        underlying, expiry=exp, start_date=sd, end_date=ed, symbol_like=sl
    )
    contract_count = db.count_option_contracts(underlying, expiry=exp)

    # daily bar count for this underlying
    with db.get_session() as session:
        from sqlalchemy import func
        q = session.query(func.count(DailyBar.id)).filter(DailyBar.symbol == underlying)
        if sd:
            q = q.filter(DailyBar.trade_date >= sd)
        if ed:
            q = q.filter(DailyBar.trade_date <= ed)
        daily_bar_count = q.scalar() or 0

        # date range for filtered option bars
        q2 = (
            session.query(
                func.min(OptionDailyBar.trade_date),
                func.max(OptionDailyBar.trade_date),
            )
            .join(OptionContract, OptionDailyBar.symbol == OptionContract.symbol)
            .filter(OptionContract.underlying_symbol == underlying)
        )
        if exp:
            q2 = q2.filter(OptionContract.expiry_date == exp)
        if sd:
            q2 = q2.filter(OptionDailyBar.trade_date >= sd)
        if ed:
            q2 = q2.filter(OptionDailyBar.trade_date <= ed)
        if sl:
            q2 = q2.filter(OptionDailyBar.symbol.contains(sl))
        row = q2.one()
        date_range = None
        if row[0]:
            date_range = {"start": _date_str(row[0]), "end": _date_str(row[1])}

    return {
        "optionContractCount": contract_count,
        "optionBarCount": option_bar_count,
        "dailyBarCount": daily_bar_count,
        "dateRange": date_range,
    }


# ========== Data: Delete ==========

@app.delete("/api/data/option-bars")
def delete_option_bars(
    underlying: str = Query(...),
    expiry: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    count = db.delete_option_bars(
        underlying,
        expiry=_parse_date(expiry),
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        symbol_like=search or None,
    )
    return {"deleted": count}


@app.delete("/api/data/daily-bars")
def delete_daily_bars(
    symbol: str = Query(...),
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    count = db.delete_daily_bars(
        symbol,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )
    return {"deleted": count}


# ========== Data: Upload ==========

@app.post("/api/data/upload")
async def upload_data_file(
    file: UploadFile = File(...),
    data_type: str = Form("option"),
    symbol: str = Form("510050"),
    granularity: str = Form("daily"),
) -> dict[str, Any]:
    if not file.filename:
        return {"success": False, "message": "未选择文件"}

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".parquet"):
        return {"success": False, "message": "仅支持 CSV / Parquet 格式"}

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if data_type == "option":
            count = _import_option_csv_atomic(tmp_path, symbol)
            return {"success": True, "message": f"导入 {count} 条期权数据", "imported": count}
        elif data_type == "underlying":
            count = _import_underlying_csv_atomic(tmp_path, symbol)
            return {"success": True, "message": f"导入 {count} 条标的K线", "imported": count}
        else:
            return {"success": False, "message": f"未知数据类型: {data_type}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        os.unlink(tmp_path)


def _import_option_csv_atomic(filepath: str, underlying: str) -> int:
    """
    Import 50ETF-style option CSV atomically.
    All database operations happen in a single transaction —
    if any step fails, everything is rolled back.

    ═══════════════════════════════════════════════════════════════
    CSV 列规范 (50ETF 期权数据)
    ═══════════════════════════════════════════════════════════════
    必需列:
      security_id      str    期权合约代码 (如 10000001.SH)     → option_contracts.symbol
      trade_date       int    交易日 YYYYMMDD                   → option_daily_bars.trade_date
      call_put         str    期权类型 C/P                      → option_contracts.option_type
      exercise_price   float  行权价                            → option_contracts.strike
      last_edate       int    到期日 YYYYMMDD                   → option_contracts.expiry_date
      open             float  开盘价                            → option_daily_bars.open_price
      high             float  最高价                            → option_daily_bars.high_price
      low              float  最低价                            → option_daily_bars.low_price
      close            float  收盘价                            → option_daily_bars.close_price
      implc_volatlty   float  隐含波动率 (小数, 如 0.304)       → option_daily_bars.iv

    可选列 (期权行情):
      volume           int    成交量                            → option_daily_bars.volume
      amount           float  成交额                            → option_daily_bars.amount
      open_interest    int    持仓量                            → option_daily_bars.open_interest
      pre_settle_price float  前结算价                          → option_daily_bars.pre_settle_price
      settle_price     float  结算价                            → option_daily_bars.settle_price
      remaining_time   int    剩余到期天数 (自然日)             → option_daily_bars.remaining_time
      list_date        int    合约上市日 YYYYMMDD               → option_contracts.list_date
      delta            float  Delta                             → option_daily_bars.delta
      gamma            float  Gamma                             → option_daily_bars.gamma
      theta            float  Theta                             → option_daily_bars.theta
      vega             float  Vega                              → option_daily_bars.vega
      rho              float  Rho                               → option_daily_bars.rho

    可选列 (标的行情):
      fund_open        float  标的开盘价                        → daily_bars.open_price
      fund_high        float  标的最高价                        → daily_bars.high_price
      fund_low         float  标的最低价                        → daily_bars.low_price
      fund_close       float  标的收盘价                        → daily_bars.close_price
      fund_volume      int    标的成交量                        → daily_bars.volume
      fund_amount      float  标的成交额                        → daily_bars.amount

    可选列 (无风险利率 — 仅首次导入时需要，已入库后无需重复提供):
      ten_year         float  十年期国债利率 (百分比, 如 3.42)  → risk_free_rates.rate (÷100)

    忽略列 (不导入):
      symbol           str    合约中文名称 (仅展示用)
    ═══════════════════════════════════════════════════════════════
    """
    df = pd.read_csv(filepath)

    if "security_id" not in df.columns or "implc_volatlty" not in df.columns:
        raise ValueError("无法识别的CSV格式，需要包含 security_id, implc_volatlty 等列")

    df["trade_date_parsed"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["expiry_date_parsed"] = pd.to_datetime(df["last_edate"], format="%Y%m%d")
    if "list_date" in df.columns:
        df["list_date_parsed"] = pd.to_datetime(df["list_date"], format="%Y%m%d", errors="coerce")

    # Helper: safe float/int extraction
    def _f(row: Any, col: str) -> float | None:
        if col not in row.index:
            return None
        v = row[col]
        return float(v) if pd.notna(v) else None

    def _i(row: Any, col: str) -> int | None:
        if col not in row.index:
            return None
        v = row[col]
        return int(v) if pd.notna(v) else None

    # All DB writes in a single session / transaction
    session = db.SessionLocal()
    try:
        # 1. Upsert underlying
        u = Underlying(
            symbol=underlying, name=underlying,
            underlying_type="ETF", exchange="SSE", lot_size=10000,
        )
        session.merge(u)

        # 2. Add contracts (with list_date)
        contract_cols = ["security_id", "exercise_price", "call_put", "expiry_date_parsed"]
        if "list_date_parsed" in df.columns:
            contract_cols.append("list_date_parsed")
        contracts_df = df[contract_cols].drop_duplicates("security_id")
        for _, row in contracts_df.iterrows():
            c = OptionContract(
                symbol=row["security_id"],
                underlying_symbol=underlying,
                option_type=row["call_put"],
                strike=float(row["exercise_price"]),
                expiry_date=row["expiry_date_parsed"].date(),
                contract_month=row["expiry_date_parsed"].strftime('%Y%m'),
                list_date=row["list_date_parsed"].date() if "list_date_parsed" in row.index and pd.notna(row.get("list_date_parsed")) else None,
            )
            session.merge(c)

        # Flush so FK references resolve, but do NOT commit yet
        session.flush()

        # 3. Import option bars (all available columns)
        total = 0
        for sym, group in df.groupby("security_id"):
            for _, brow in group.iterrows():
                td = brow["trade_date_parsed"].date()
                existing = session.query(OptionDailyBar).filter(
                    OptionDailyBar.symbol == str(sym),
                    OptionDailyBar.trade_date == td,
                ).first()
                vals = dict(
                    open_price=_f(brow, 'open'),
                    high_price=_f(brow, 'high'),
                    low_price=_f(brow, 'low'),
                    close_price=_f(brow, 'close'),
                    volume=_i(brow, 'volume') or 0,
                    amount=_f(brow, 'amount') or 0,
                    open_interest=_i(brow, 'open_interest'),
                    pre_settle_price=_f(brow, 'pre_settle_price'),
                    settle_price=_f(brow, 'settle_price'),
                    remaining_time=_i(brow, 'remaining_time'),
                    iv=_f(brow, 'implc_volatlty'),
                    delta=_f(brow, 'delta'),
                    gamma=_f(brow, 'gamma'),
                    theta=_f(brow, 'theta'),
                    vega=_f(brow, 'vega'),
                    rho=_f(brow, 'rho'),
                )
                if existing:
                    for k, v in vals.items():
                        setattr(existing, k, v)
                else:
                    bar = OptionDailyBar(symbol=str(sym), trade_date=td, **vals)
                    session.add(bar)
                total += 1

        # 4. Import underlying ETF bars from fund_* columns
        if "fund_close" in df.columns:
            fund_df = df[["trade_date_parsed", "fund_open", "fund_high", "fund_low",
                           "fund_close", "fund_volume", "fund_amount"]].drop_duplicates("trade_date_parsed")
            for _, frow in fund_df.iterrows():
                td = frow["trade_date_parsed"].date()
                if pd.isna(frow["fund_close"]):
                    continue
                existing = session.query(DailyBar).filter(
                    DailyBar.symbol == underlying,
                    DailyBar.trade_date == td,
                ).first()
                fvals = dict(
                    open_price=_f(frow, 'fund_open'),
                    high_price=_f(frow, 'fund_high'),
                    low_price=_f(frow, 'fund_low'),
                    close_price=_f(frow, 'fund_close'),
                    volume=_i(frow, 'fund_volume') or 0,
                    amount=_f(frow, 'fund_amount') or 0,
                )
                if existing:
                    for k, v in fvals.items():
                        setattr(existing, k, v)
                else:
                    bar = DailyBar(symbol=underlying, trade_date=td, **fvals)
                    session.add(bar)

        # 5. Import risk-free rate from ten_year column (仅在 CSV 包含该列时导入)
        # 无风险利率已独立存储在 risk_free_rates 表中，后续上传无需重复提供
        # CSV 中 ten_year 为百分比值 (如 3.42 表示 3.42%)，存储时转为小数 (0.0342)
        if "ten_year" in df.columns:
            # 检查是否已有数据，避免重复写入
            existing_count = session.query(RiskFreeRate).filter(
                RiskFreeRate.source == "ten_year"
            ).count()
            if existing_count == 0:
                rfr_df = df[["trade_date_parsed", "ten_year"]].drop_duplicates("trade_date_parsed")
                for _, rrow in rfr_df.iterrows():
                    td = rrow["trade_date_parsed"].date()
                    rate_val = rrow["ten_year"]
                    if pd.isna(rate_val) or float(rate_val) <= 0:
                        continue
                    rate_decimal = float(rate_val) / 100.0  # 百分比 → 小数
                    session.add(RiskFreeRate(
                        trade_date=td, rate=rate_decimal, source="ten_year",
                    ))

        # ALL successful — commit the entire transaction
        session.commit()
        return total

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _import_underlying_csv_atomic(filepath: str, symbol: str) -> int:
    """
    Import underlying daily bar CSV atomically.
    All database operations happen in a single transaction.
    """
    df = pd.read_csv(filepath)
    # Try to detect date column
    date_col = None
    for c in ["trade_date", "date", "Date", "datetime"]:
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        raise ValueError("CSV中未找到日期列 (trade_date / date)")
    df["trade_date"] = pd.to_datetime(df[date_col])

    # Validate required columns
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            raise ValueError(f"CSV中缺少 {col} 列")

    session = db.SessionLocal()
    try:
        # 1. Upsert underlying
        u = Underlying(
            symbol=symbol, name=symbol,
            underlying_type="ETF", exchange="SSE", lot_size=10000,
        )
        session.merge(u)
        session.flush()

        # 2. Import bars
        count = 0
        for _, row in df.iterrows():
            td = row['trade_date'].date()
            existing = session.query(DailyBar).filter(
                DailyBar.symbol == symbol,
                DailyBar.trade_date == td,
            ).first()
            vals = dict(
                open_price=float(row['open']),
                high_price=float(row['high']),
                low_price=float(row['low']),
                close_price=float(row['close']),
                volume=int(row['volume']) if 'volume' in row and pd.notna(row['volume']) else 0,
                amount=float(row['amount']) if 'amount' in row and pd.notna(row['amount']) else 0,
            )
            if existing:
                for k, v in vals.items():
                    setattr(existing, k, v)
            else:
                bar = DailyBar(symbol=symbol, trade_date=td, **vals)
                session.add(bar)
            count += 1

        session.commit()
        return count

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ========== Visualization API ==========

@app.get("/api/viz/market/{underlying}")
def get_market_overview(
    underlying: str,
    contract_symbol: str | None = None,
    start_date: str = "2015-01-01",
    end_date: str = "2026-12-31",
) -> dict[str, Any]:
    """
    行情概览: 返回标的 OHLC + ATM IV 时序数据，或单个合约数据。
    - 如果 contract_symbol 为 None，返回标的ETF + ATM IV
    - 如果指定 contract_symbol，返回该期权合约的数据
    """
    from sqlalchemy import text

    start = _parse_date(start_date)
    end = _parse_date(end_date)

    # 单个合约模式
    if contract_symbol:
        with db.get_session() as session:
            contract = session.query(OptionContract).filter(OptionContract.symbol == contract_symbol).first()
            if not contract:
                raise HTTPException(status_code=404, detail="合约不存在")

            # 获取期权K线
            bars = (
                session.query(OptionDailyBar)
                .filter(
                    OptionDailyBar.symbol == contract_symbol,
                    OptionDailyBar.trade_date >= start,
                    OptionDailyBar.trade_date <= end,
                )
                .order_by(OptionDailyBar.trade_date)
                .all()
            )

            # 获取标的价格
            underlying_bars = (
                session.query(DailyBar)
                .filter(
                    DailyBar.symbol == contract.underlying_symbol,
                    DailyBar.trade_date >= start,
                    DailyBar.trade_date <= end,
                )
                .order_by(DailyBar.trade_date)
                .all()
            )

            underlying_price_map = {
                _date_str(b.trade_date): float(b.close_price) if b.close_price else None
                for b in underlying_bars
            }
            underlying_volume_map = {
                _date_str(b.trade_date): int(b.volume) if b.volume else 0
                for b in underlying_bars
            }

            dates = []
            ohlc = []
            volumes = []
            open_interests = []
            ivs = []
            deltas = []
            gammas = []
            thetas = []
            vegas = []
            underlying_prices = []

            for bar in bars:
                date_str = _date_str(bar.trade_date)
                dates.append(date_str)
                ohlc.append([
                    round(float(bar.open_price), 4),
                    round(float(bar.close_price), 4),
                    round(float(bar.low_price), 4),
                    round(float(bar.high_price), 4),
                ])
                volumes.append(int(bar.volume) if bar.volume else 0)
                open_interests.append(int(bar.open_interest) if bar.open_interest else 0)
                ivs.append(round(float(bar.iv), 4) if bar.iv else None)
                deltas.append(round(float(bar.delta), 4) if bar.delta else None)
                gammas.append(round(float(bar.gamma), 4) if bar.gamma else None)
                thetas.append(round(float(bar.theta), 4) if bar.theta else None)
                vegas.append(round(float(bar.vega), 4) if bar.vega else None)
                underlying_prices.append(underlying_price_map.get(date_str))

            return {
                "dates": dates,
                "ohlc": ohlc,
                "prices": underlying_prices,
                "ivs": ivs,
                "deltas": deltas,
                "gammas": gammas,
                "thetas": thetas,
                "vegas": vegas,
                "volumes": volumes,
                "openInterests": open_interests,
                "underlyingVolumes": [underlying_volume_map.get(d, 0) for d in dates],
                "contractInfo": {
                    "symbol": contract.symbol,
                    "type": contract.option_type,
                    "strike": float(contract.strike),
                    "expiry": _date_str(contract.expiry_date),
                },
            }

    # 全期权模式（标的ETF + ATM IV + 平均IV）
    df = db.get_underlying_bars(underlying, start, end)

    if df.empty:
        return {"dates": [], "ohlc": [], "prices": [], "ivs": [], "avgIvs": [], "volumes": [], "deltas": [], "gammas": [], "thetas": [], "vegas": []}

    dates: list[str] = []
    ohlc: list[list[float]] = []
    prices: list[float] = []
    volumes: list[int] = []
    for _, r in df.iterrows():
        dates.append(_date_str(r["trade_date"]))
        prices.append(round(float(r["close"]), 4))
        volumes.append(int(r["volume"]) if pd.notna(r.get("volume")) else 0)
        # ECharts candlestick: [open, close, low, high]
        ohlc.append([
            round(float(r["open"]), 4),
            round(float(r["close"]), 4),
            round(float(r["low"]), 4),
            round(float(r["high"]), 4),
        ])

    # 一次性查询所有 Call 的 (trade_date, strike, iv, delta, gamma, theta, vega)，在 Python 端找 ATM
    import bisect
    from collections import defaultdict

    atm_sql = text("""
        SELECT odb.trade_date, oc.strike, odb.iv, odb.delta, odb.gamma, odb.theta, odb.vega
        FROM option_daily_bars odb
        JOIN option_contracts oc ON odb.symbol = oc.symbol
        WHERE oc.underlying_symbol = :underlying
          AND oc.option_type = 'C'
          AND odb.iv > 0
          AND odb.trade_date BETWEEN :start_date AND :end_date
        ORDER BY odb.trade_date, oc.strike
    """)

    date_options: dict[str, list[tuple[float, float, float, float, float, float]]] = defaultdict(list)
    with db.get_session() as session:
        rows = session.execute(atm_sql, {
            "underlying": underlying,
            "start_date": start,
            "end_date": end,
        }).fetchall()
        for row in rows:
            # (strike, iv, delta, gamma, theta, vega)
            date_options[_date_str(row[0])].append((
                float(row[1]),
                float(row[2]) if row[2] else 0,
                float(row[3]) if row[3] else 0,
                float(row[4]) if row[4] else 0,
                float(row[5]) if row[5] else 0,
                float(row[6]) if row[6] else 0,
            ))

    price_map: dict[str, float] = dict(zip(dates, prices))

    atm_iv_map: dict[str, float | None] = {}
    atm_delta_map: dict[str, float | None] = {}
    atm_gamma_map: dict[str, float | None] = {}
    atm_theta_map: dict[str, float | None] = {}
    atm_vega_map: dict[str, float | None] = {}
    for d in dates:
        opts = date_options.get(d)
        if not opts:
            atm_iv_map[d] = None
            atm_delta_map[d] = None
            atm_gamma_map[d] = None
            atm_theta_map[d] = None
            atm_vega_map[d] = None
            continue
        close_px = price_map[d]
        strike_list = [o[0] for o in opts]
        idx = bisect.bisect_left(strike_list, close_px)
        if idx == 0:
            best = 0
        elif idx >= len(strike_list):
            best = len(strike_list) - 1
        elif abs(strike_list[idx - 1] - close_px) <= abs(strike_list[idx] - close_px):
            best = idx - 1
        else:
            best = idx
        opt = opts[best]
        atm_iv_map[d] = round(opt[1], 4)
        atm_delta_map[d] = round(opt[2], 4)
        atm_gamma_map[d] = round(opt[3], 4)
        atm_theta_map[d] = round(opt[4], 4)
        atm_vega_map[d] = round(opt[5], 4)

    ivs = [atm_iv_map.get(d) for d in dates]
    deltas = [atm_delta_map.get(d) for d in dates]
    gammas = [atm_gamma_map.get(d) for d in dates]
    thetas = [atm_theta_map.get(d) for d in dates]
    vegas = [atm_vega_map.get(d) for d in dates]

    avg_iv_map: dict[str, float | None] = {}
    with db.get_session() as session:
        avg_iv_sql = text("""
            SELECT odb.trade_date, AVG(odb.iv) as avg_iv
            FROM option_daily_bars odb
            JOIN option_contracts oc ON odb.symbol = oc.symbol
            WHERE oc.underlying_symbol = :underlying
              AND odb.iv > 0
              AND odb.trade_date BETWEEN :start_date AND :end_date
            GROUP BY odb.trade_date
            ORDER BY odb.trade_date
        """)
        rows = session.execute(avg_iv_sql, {
            "underlying": underlying,
            "start_date": start,
            "end_date": end,
        }).fetchall()
        for row in rows:
            avg_iv_map[_date_str(row[0])] = round(float(row[1]), 4) if row[1] else None

    avg_ivs = [avg_iv_map.get(d) for d in dates]

    return {"dates": dates, "ohlc": ohlc, "prices": prices, "ivs": ivs, "avgIvs": avg_ivs, "volumes": volumes,
            "deltas": deltas, "gammas": gammas, "thetas": thetas, "vegas": vegas}


@app.get("/api/viz/vol-smile/{underlying}")
def get_vol_smile(
    underlying: str,
    trade_date: str = Query(...),
) -> list[dict[str, Any]]:
    """
    波动率微笑 (2D): 返回每个到期月的 Call/Put IV 曲线 + 持仓量数据。
    包含今日 vs 昨日对比、标的收盘价、持仓量变化。
    """
    td = _parse_date(trade_date)

    with db.get_session() as session:
        # 找上一个交易日
        prev_row = (
            session.query(OptionDailyBar.trade_date)
            .join(OptionContract, OptionDailyBar.symbol == OptionContract.symbol)
            .filter(OptionContract.underlying_symbol == underlying, OptionDailyBar.trade_date < td)
            .order_by(OptionDailyBar.trade_date.desc())
            .first()
        )
        prev_date = prev_row[0] if prev_row else None

        # 获取标的收盘价（今日 + 昨日）
        today_bar = session.query(DailyBar).filter(
            DailyBar.symbol == underlying, DailyBar.trade_date == td
        ).first()
        today_underlying_close = float(today_bar.close_price) if today_bar and today_bar.close_price else 0

        yesterday_underlying_close = 0.0
        if prev_date:
            yd_bar = session.query(DailyBar).filter(
                DailyBar.symbol == underlying, DailyBar.trade_date == prev_date
            ).first()
            yesterday_underlying_close = float(yd_bar.close_price) if yd_bar and yd_bar.close_price else 0

    today_raw = _get_smile_raw(underlying, td)
    yesterday_raw = _get_smile_raw(underlying, prev_date) if prev_date else {}

    result: list[dict[str, Any]] = []
    for expiry, strike_data in sorted(today_raw.items()):
        yd_strike_map = yesterday_raw.get(expiry, {})

        # 计算到期天数
        from datetime import datetime as _dt
        try:
            exp_date = _dt.strptime(expiry, "%Y-%m-%d").date()
            days_to_expiry = (exp_date - td).days
        except Exception:
            days_to_expiry = 0

        strikes_list: list[dict[str, Any]] = []
        for strike_val in sorted(strike_data.keys()):
            td_info = strike_data[strike_val]
            yd_info = yd_strike_map.get(strike_val, {})

            call_oi = td_info.get("callOi")
            put_oi = td_info.get("putOi")
            yd_call_oi = yd_info.get("callOi")
            yd_put_oi = yd_info.get("putOi")

            strikes_list.append({
                "strike": strike_val,
                "callIv": td_info.get("callIv"),
                "putIv": td_info.get("putIv"),
                "callOi": call_oi,
                "putOi": put_oi,
                "callOiChange": (call_oi - yd_call_oi) if (call_oi is not None and yd_call_oi is not None) else None,
                "putOiChange": (put_oi - yd_put_oi) if (put_oi is not None and yd_put_oi is not None) else None,
                "callVolume": td_info.get("callVolume"),
                "putVolume": td_info.get("putVolume"),
                "callPrice": td_info.get("callPrice"),
                "putPrice": td_info.get("putPrice"),
                "yesterdayCallIv": yd_info.get("callIv"),
                "yesterdayPutIv": yd_info.get("putIv"),
            })

        result.append({
            "expiry": expiry,
            "contractMonth": expiry[:7].replace("-", ""),
            "daysToExpiry": days_to_expiry,
            "todayUnderlyingClose": today_underlying_close,
            "yesterdayUnderlyingClose": yesterday_underlying_close,
            "strikes": strikes_list,
        })

    return result


def _get_smile_raw(
    underlying: str, td: date | None,
) -> dict[str, dict[float, dict[str, Any]]]:
    """
    查询某日全部期权的 IV/OI/volume/price，按到期日→行权价→Call/Put 聚合。
    返回: { expiry_str: { strike: { callIv, putIv, callOi, putOi, ... } } }
    """
    if td is None:
        return {}
    with db.get_session() as session:
        rows = (
            session.query(
                OptionContract.expiry_date,
                OptionContract.strike,
                OptionContract.option_type,
                OptionDailyBar.iv,
                OptionDailyBar.volume,
                OptionDailyBar.open_interest,
                OptionDailyBar.close_price,
            )
            .join(OptionDailyBar, OptionContract.symbol == OptionDailyBar.symbol)
            .filter(
                OptionContract.underlying_symbol == underlying,
                OptionDailyBar.trade_date == td,
            )
            .order_by(OptionContract.expiry_date, OptionContract.strike)
            .all()
        )
    grouped: dict[str, dict[float, dict[str, Any]]] = {}
    for expiry, strike, opt_type, iv, volume, oi, price in rows:
        key = _date_str(expiry)
        if key not in grouped:
            grouped[key] = {}
        s = float(strike)
        if s not in grouped[key]:
            grouped[key][s] = {}
        rec = grouped[key][s]
        iv_val = round(float(iv), 6) if iv else None
        oi_val = int(oi) if oi is not None else None
        vol_val = int(volume) if volume is not None else None
        price_val = round(float(price), 4) if price else None

        if opt_type == "C":
            rec["callIv"] = iv_val
            rec["callOi"] = oi_val
            rec["callVolume"] = vol_val
            rec["callPrice"] = price_val
        else:
            rec["putIv"] = iv_val
            rec["putOi"] = oi_val
            rec["putVolume"] = vol_val
            rec["putPrice"] = price_val
    return grouped


@app.get("/api/viz/vol-surface/{underlying}")
def get_vol_surface(
    underlying: str,
    trade_date: str = Query(...),
    mode: str = Query("raw"),  # "raw" or "svi"
) -> dict[str, Any]:
    import math
    td = _parse_date(trade_date)
    with db.get_session() as session:
        underlying_bar = session.query(DailyBar).filter(
            DailyBar.symbol == underlying, DailyBar.trade_date == td
        ).first()
        spot = float(underlying_bar.close_price) if underlying_bar and underlying_bar.close_price else 0

        rows = (
            session.query(OptionContract.strike, OptionContract.expiry_date, OptionDailyBar.iv)
            .join(OptionDailyBar, OptionContract.symbol == OptionDailyBar.symbol)
            .filter(
                OptionContract.underlying_symbol == underlying,
                OptionDailyBar.trade_date == td,
                OptionDailyBar.iv.isnot(None),
                OptionContract.option_type == "C",
            )
            .order_by(OptionContract.expiry_date, OptionContract.strike)
            .all()
        )

    if spot <= 0 and rows:
        all_strikes = sorted(set(float(r[0]) for r in rows))
        spot = all_strikes[len(all_strikes) // 2]

    # 去重: 同一 (strike, expiry) 取 IV 均值
    from collections import defaultdict
    bucket: dict[tuple[float, str], list[float]] = defaultdict(list)
    for s, e, iv in rows:
        iv_val = float(iv) if iv else 0
        if iv_val <= 0:
            continue
        exp_str = _date_str(e)
        bucket[(float(s), exp_str)].append(iv_val)

    points = []
    for (strike, exp_str) in sorted(bucket.keys(), key=lambda k: (k[1], k[0])):
        ivs = bucket[(strike, exp_str)]
        iv_avg = sum(ivs) / len(ivs)
        expiry_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        remaining_days = (expiry_date - td).days
        if remaining_days <= 0:
            continue
        T = remaining_days / 365.0
        m = math.log(strike / spot) if spot > 0 else 0
        points.append({
            "strike": strike, "expiry": exp_str, "iv": round(iv_avg, 6),
            "moneyness": round(m, 6), "T": round(T, 6), "remainingDays": remaining_days,
        })

    # SVI 拟合模式
    svi_points: list[dict[str, Any]] = []
    if mode == "svi" and len(points) > 5:
        svi_points = _fit_svi_surface(points)

    return {
        "spot": round(spot, 4),
        "tradeDate": _date_str(td),
        "points": points,
        "sviPoints": svi_points,
        "mode": mode,
    }


# ── 无套利检查 ──

def _arbitrage_filter(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    过滤违反无套利条件的数据点：
    1. Butterfly arbitrage: 同一到期日，总方差 w(K) = σ²·T 在 strike 方向应为凸函数
    2. Calendar spread arbitrage: 同一 strike，总方差应随 T 单调递增
    """
    from collections import defaultdict

    if len(points) < 3:
        return points

    # ── Butterfly check (per expiry) ──
    by_expiry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in points:
        by_expiry[p["expiry"]].append(p)

    clean: list[dict[str, Any]] = []
    removed_keys: set[tuple[float, str]] = set()

    for exp, grp in by_expiry.items():
        grp_sorted = sorted(grp, key=lambda x: x["strike"])
        n = len(grp_sorted)
        keep = [True] * n
        for i in range(1, n - 1):
            w_prev = grp_sorted[i - 1]["iv"] ** 2 * grp_sorted[i - 1]["T"]
            w_curr = grp_sorted[i]["iv"] ** 2 * grp_sorted[i]["T"]
            w_next = grp_sorted[i + 1]["iv"] ** 2 * grp_sorted[i + 1]["T"]
            # Convexity check: w(K_i) should be <= linear interpolation of neighbors
            k_prev = grp_sorted[i - 1]["strike"]
            k_curr = grp_sorted[i]["strike"]
            k_next = grp_sorted[i + 1]["strike"]
            if k_next > k_prev:
                w_interp = w_prev + (w_next - w_prev) * (k_curr - k_prev) / (k_next - k_prev)
                if w_curr > w_interp * 1.15:  # 15% tolerance for market noise
                    keep[i] = False
                    removed_keys.add((grp_sorted[i]["strike"], exp))

        for i, p in enumerate(grp_sorted):
            if keep[i]:
                clean.append(p)

    # ── Calendar spread check (per strike) ──
    by_strike: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for p in clean:
        by_strike[p["strike"]].append(p)

    final: list[dict[str, Any]] = []
    for strike, grp in by_strike.items():
        grp_sorted = sorted(grp, key=lambda x: x["T"])
        prev_total_var = -1.0
        for p in grp_sorted:
            total_var = p["iv"] ** 2 * p["T"]
            if total_var >= prev_total_var * 0.95:  # 5% tolerance
                final.append(p)
                prev_total_var = total_var
            # else: skip this point (calendar spread violation)

    return final


# ── Delta-based Skew 计算 ──

def _calc_delta_skew(items: list[dict], spot: float) -> float:
    """
    从前一交易日的期权数据计算 25Δ skew。
    items: list of {"strike", "iv", "delta", "type"}
    返回: 25Δ Put IV - 25Δ Call IV
    """
    puts = [x for x in items if x.get("type") == "P" and x.get("delta") is not None]
    calls = [x for x in items if x.get("type") == "C" and x.get("delta") is not None]

    # 找最接近 -0.25 delta 的 Put
    put_25d_iv = None
    if puts:
        best_put = min(puts, key=lambda x: abs((x["delta"] or 0) - (-0.25)))
        if abs((best_put["delta"] or 0) - (-0.25)) < 0.15:
            put_25d_iv = best_put["iv"]

    # 找最接近 0.25 delta 的 Call
    call_25d_iv = None
    if calls:
        best_call = min(calls, key=lambda x: abs((x["delta"] or 0) - 0.25))
        if abs((best_call["delta"] or 0) - 0.25) < 0.15:
            call_25d_iv = best_call["iv"]

    if put_25d_iv is not None and call_25d_iv is not None:
        return put_25d_iv - call_25d_iv

    # Fallback: 用 moneyness 近似 (K/S 偏移约 5% 对应 ~25Δ)
    sorted_items = sorted(items, key=lambda x: x["strike"])
    if len(sorted_items) < 3 or spot <= 0:
        return 0.0
    target_put_k = spot * 0.95
    target_call_k = spot * 1.05
    put_approx = min(sorted_items, key=lambda x: abs(x["strike"] - target_put_k))
    call_approx = min(sorted_items, key=lambda x: abs(x["strike"] - target_call_k))
    return put_approx["iv"] - call_approx["iv"]


def _calc_delta_skew_from_pairs(pairs: list[dict[str, Any]], spot: float) -> float:
    """
    从当日 pair_data 计算 25Δ skew。
    pairs: list of pair_data dicts with callDelta, putDelta, callIv, putIv
    """
    # 找最接近 25Δ 的 Put
    put_25d_iv = None
    best_put_dist = 999.0
    call_25d_iv = None
    best_call_dist = 999.0

    for d in pairs:
        put_delta = d.get("putDelta")
        put_iv = d.get("putIv")
        if put_delta is not None and put_iv and put_iv > 0:
            dist = abs(put_delta - (-0.25))
            if dist < best_put_dist:
                best_put_dist = dist
                put_25d_iv = put_iv

        call_delta = d.get("callDelta")
        call_iv = d.get("callIv")
        if call_delta is not None and call_iv and call_iv > 0:
            dist = abs(call_delta - 0.25)
            if dist < best_call_dist:
                best_call_dist = dist
                call_25d_iv = call_iv

    if put_25d_iv is not None and call_25d_iv is not None and best_put_dist < 0.15 and best_call_dist < 0.15:
        return put_25d_iv - call_25d_iv

    # Fallback: moneyness 近似
    if not pairs or spot <= 0:
        return 0.0
    target_put_k = spot * 0.95
    target_call_k = spot * 1.05
    put_approx = min(pairs, key=lambda x: abs(x.get("strike", 0) - target_put_k))
    call_approx = min(pairs, key=lambda x: abs(x.get("strike", 0) - target_call_k))
    p_iv = put_approx.get("putIv") or put_approx.get("callIv") or 0
    c_iv = call_approx.get("callIv") or call_approx.get("putIv") or 0
    return (p_iv - c_iv) if p_iv > 0 and c_iv > 0 else 0.0


def _fit_svi_surface(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对每个到期日用 SVI 模型拟合, 然后在细网格上求值生成光滑曲面."""
    import math
    import numpy as np
    from collections import defaultdict

    try:
        from scipy.optimize import least_squares
    except ImportError:
        return []

    by_t: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for p in points:
        by_t[p["T"]].append(p)

    # SVI on total variance: w(k) = a + b*(rho*(k-m) + sqrt((k-m)^2 + sig^2))
    def svi_w(k: np.ndarray, params: np.ndarray) -> np.ndarray:
        a, b, rho, m, sig = params
        dk = k - m
        return a + b * (rho * dk + np.sqrt(dk**2 + sig**2))

    all_m = [p["moneyness"] for p in points]
    m_min, m_max = min(all_m), max(all_m)
    fine_m = np.linspace(m_min, m_max, 30)

    result: list[dict[str, Any]] = []

    for T_val in sorted(by_t.keys()):
        grp = by_t[T_val]
        if len(grp) < 4:
            for p in grp:
                result.append(p)
            continue

        ks = np.array([p["moneyness"] for p in grp])
        ivs = np.array([p["iv"] for p in grp])
        ws = ivs**2 * T_val

        a0 = float(np.mean(ws))
        b0 = float(np.std(ws)) + 1e-4
        x0 = np.array([a0, b0, -0.3, 0.0, 0.1])

        def residuals(params: np.ndarray) -> np.ndarray:
            return svi_w(ks, params) - ws

        try:
            res = least_squares(
                residuals, x0,
                bounds=(
                    [1e-8, 1e-8, -0.999, -1.0, 1e-4],
                    [np.inf, np.inf, 0.999, 1.0, 2.0],
                ),
                method="trf", max_nfev=3000,
            )
            params = res.x
        except Exception:
            for p in grp:
                result.append(p)
            continue

        w_fine = svi_w(fine_m, params)
        w_fine = np.maximum(w_fine, 1e-8)
        iv_fine = np.sqrt(w_fine / T_val)

        # 限制 IV 在合理范围 (原始数据 IV 的 0.5x ~ 2x)
        iv_lo, iv_hi = float(ivs.min()) * 0.5, float(ivs.max()) * 2.0
        iv_fine = np.clip(iv_fine, iv_lo, iv_hi)

        expiry_str = grp[0]["expiry"]
        remaining = grp[0]["remainingDays"]
        spot = grp[0]["strike"] / math.exp(grp[0]["moneyness"]) if grp[0]["moneyness"] != 0 else grp[0]["strike"]

        for i, mk in enumerate(fine_m):
            result.append({
                "strike": round(spot * math.exp(float(mk)), 4),
                "expiry": expiry_str,
                "iv": round(float(iv_fine[i]), 6),
                "moneyness": round(float(mk), 6),
                "T": T_val,
                "remainingDays": remaining,
            })

    return result


def _compute_synthetic_forwards(
    underlying: str, td: date, r_rate: float,
) -> dict[str, float]:
    """
    计算给定交易日每个到期月的合成期货价格 F̂。
    F̂ = K + (C - P) · e^(rT)，按 min(callOi, putOi) 加权平均。
    """
    import math

    with db.get_session() as session:
        rows = (
            session.query(
                OptionContract.strike,
                OptionContract.expiry_date,
                OptionContract.option_type,
                OptionDailyBar.close_price,
                OptionDailyBar.open_interest,
            )
            .join(OptionDailyBar, OptionContract.symbol == OptionDailyBar.symbol)
            .filter(
                OptionContract.underlying_symbol == underlying,
                OptionDailyBar.trade_date == td,
            )
            .order_by(OptionContract.expiry_date, OptionContract.strike)
            .all()
        )

    # 按 (expiry, strike) 分组收集 Call/Put 价格和持仓量
    from collections import defaultdict
    pair: dict[tuple[str, float], dict[str, Any]] = {}
    for strike_val, expiry_d, opt_type, close_p, oi in rows:
        strike_f = float(strike_val)
        exp_str = _date_str(expiry_d)
        if exp_str is None:
            continue
        expiry_date = expiry_d if isinstance(expiry_d, date) else datetime.strptime(exp_str, "%Y-%m-%d").date()
        remaining_days = (expiry_date - td).days
        if remaining_days <= 0:
            continue

        key = (exp_str, strike_f)
        if key not in pair:
            pair[key] = {"T": round(remaining_days / 365.0, 6), "strike": strike_f, "expiry": exp_str}

        close_f = float(close_p) if close_p else 0
        oi_i = int(oi) if oi else 0
        if opt_type == "C":
            pair[key]["callPrice"] = close_f
            pair[key]["callOi"] = oi_i
        else:
            pair[key]["putPrice"] = close_f
            pair[key]["putOi"] = oi_i

    # 按到期日分组计算 F̂
    expiry_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, d in pair.items():
        expiry_groups[d["expiry"]].append(d)

    fwd_map: dict[str, float] = {}
    for exp_str, items in expiry_groups.items():
        f_estimates: list[tuple[float, float]] = []
        for d in items:
            c_price = d.get("callPrice", 0) or 0
            p_price = d.get("putPrice", 0) or 0
            T_val = d["T"]
            strike_f = d["strike"]
            if c_price > 0 and p_price > 0 and T_val > 0:
                f_hat = strike_f + (c_price - p_price) * math.exp(r_rate * T_val)
                if f_hat > 0:
                    w = min(d.get("callOi", 0) or 0, d.get("putOi", 0) or 0)
                    if w <= 0:
                        w = 1.0
                    f_estimates.append((f_hat, w))
        if f_estimates:
            total_w = sum(w for _, w in f_estimates)
            fwd_map[exp_str] = sum(f * w for f, w in f_estimates) / total_w

    return fwd_map


@app.get("/api/viz/vol-surface-v2/{underlying}")
def get_vol_surface_v2(
    underlying: str,
    trade_date: str = Query(...),
    mode: str = Query("raw"),  # "raw" or "synthetic"
) -> dict[str, Any]:
    """
    增强版波动率曲面 API — 返回 Call/Put IV、持仓量、ATM IV、偏度等完整数据。
    mode='raw': 使用数据库中预计算的 IV（OTM 优先 + vega 加权平均）
    mode='synthetic': 使用合成数据（合成远期价格 + Black 模型）重新计算 IV
    """
    import math
    from collections import defaultdict
    from ccquant.option.pricing import PricingContext, implied_volatility, black_scholes_greeks

    td = _parse_date(trade_date)
    if td is None:
        raise HTTPException(400, "Invalid trade_date")

    # ── 获取无风险利率（从数据库读取，回退到 0.03） ──
    r_rate = db.get_risk_free_rate(td) or 0.03

    with db.get_session() as session:
        # 获取标的收盘价
        underlying_bar = session.query(DailyBar).filter(
            DailyBar.symbol == underlying, DailyBar.trade_date == td
        ).first()
        spot = float(underlying_bar.close_price) if underlying_bar and underlying_bar.close_price else 0

        # 查询所有期权数据 (Call + Put)
        rows = (
            session.query(
                OptionContract.strike,
                OptionContract.expiry_date,
                OptionContract.option_type,
                OptionDailyBar.iv,
                OptionDailyBar.close_price,
                OptionDailyBar.volume,
                OptionDailyBar.open_interest,
                OptionDailyBar.delta,
                OptionDailyBar.vega,
            )
            .join(OptionDailyBar, OptionContract.symbol == OptionDailyBar.symbol)
            .filter(
                OptionContract.underlying_symbol == underlying,
                OptionDailyBar.trade_date == td,
            )
            .order_by(OptionContract.expiry_date, OptionContract.strike)
            .all()
        )

    if spot <= 0 and rows:
        all_strikes = sorted(set(float(r[0]) for r in rows))
        spot = all_strikes[len(all_strikes) // 2] if all_strikes else 0

    # ── 按 (strike, expiry) 分组，收集 Call/Put 数据 ──
    pair_data: dict[tuple[float, str], dict[str, Any]] = {}
    for strike_val, expiry_d, opt_type, iv_val, close_p, vol, oi, delta_v, vega_v in rows:
        strike_f = float(strike_val)
        exp_str = _date_str(expiry_d)
        if exp_str is None:
            continue
        expiry_date = expiry_d if isinstance(expiry_d, date) else datetime.strptime(exp_str, "%Y-%m-%d").date()
        remaining_days = (expiry_date - td).days
        if remaining_days <= 0:
            continue

        key = (strike_f, exp_str)
        if key not in pair_data:
            pair_data[key] = {
                "strike": strike_f, "expiry": exp_str,
                "remainingDays": remaining_days, "T": round(remaining_days / 365.0, 6),
            }

        iv_f = float(iv_val) if iv_val else 0
        close_f = float(close_p) if close_p else 0
        vol_i = int(vol) if vol else 0
        oi_i = int(oi) if oi else 0
        delta_f = float(delta_v) if delta_v else None
        vega_f = float(vega_v) if vega_v else None

        if opt_type == "C":
            pair_data[key]["callIv"] = iv_f if iv_f > 0 else None
            pair_data[key]["callPrice"] = close_f
            pair_data[key]["callVolume"] = vol_i
            pair_data[key]["callOi"] = oi_i
            pair_data[key]["callDelta"] = delta_f
            pair_data[key]["callVega"] = vega_f
        else:
            pair_data[key]["putIv"] = iv_f if iv_f > 0 else None
            pair_data[key]["putPrice"] = close_f
            pair_data[key]["putVolume"] = vol_i
            pair_data[key]["putOi"] = oi_i
            pair_data[key]["putDelta"] = delta_f
            pair_data[key]["putVega"] = vega_f

    # ── 计算 moneyness 和 IV (根据模式) ──
    surface_points: list[dict[str, Any]] = []
    volume_bars: list[dict[str, Any]] = []
    fwd_map: dict[str, float] = {}  # 合成期货价格（仅 synthetic 模式填充）

    if mode == "synthetic":
        # ══════════════════════════════════════════════════════════════
        # 合成数据模式：
        #   1) 按到期日分组，用 Put-Call Parity 推算合成期货价格 F̂
        #      F̂ = K + (C - P) · e^(rT)
        #      对多个行权价取加权平均（权重 = min(callOi, putOi)，流动性越好权重越大）
        #   2) 用 Black 模型（BS with S=F̂, r=0, q=0）反求 IV
        #      OTM 优先：K > F̂ 用 Call，K < F̂ 用 Put
        #   3) moneyness = ln(K / F̂)
        # ══════════════════════════════════════════════════════════════
        from collections import defaultdict as _dd

        # Step 1: 按到期日分组
        expiry_groups: dict[str, list[dict[str, Any]]] = _dd(list)
        for key, d in pair_data.items():
            expiry_groups[d["expiry"]].append(d)

        # Step 2: 计算每个到期日的合成期货价格 F̂
        for exp_str, items in expiry_groups.items():
            f_estimates: list[tuple[float, float]] = []  # (F̂, weight)
            for d in items:
                c_price = d.get("callPrice", 0) or 0
                p_price = d.get("putPrice", 0) or 0
                T_val = d["T"]
                strike_f = d["strike"]
                if c_price > 0 and p_price > 0 and T_val > 0:
                    f_hat = strike_f + (c_price - p_price) * math.exp(r_rate * T_val)
                    if f_hat > 0:
                        # 权重：取 Call/Put 持仓量的较小值（流动性代理）
                        w = min(d.get("callOi", 0) or 0, d.get("putOi", 0) or 0)
                        if w <= 0:
                            w = 1.0  # 无持仓量时给最小权重
                        f_estimates.append((f_hat, w))

            if f_estimates:
                total_w = sum(w for _, w in f_estimates)
                fwd_map[exp_str] = sum(f * w for f, w in f_estimates) / total_w
            else:
                fwd_map[exp_str] = spot  # 回退到现货

        # Step 3: 用 F̂ + Black 模型反求 IV
        for key, d in sorted(pair_data.items(), key=lambda x: (x[0][1], x[0][0])):
            strike_f = d["strike"]
            T_val = d["T"]
            exp_str = d["expiry"]
            F_hat = fwd_map.get(exp_str, spot)

            m = math.log(strike_f / F_hat) if F_hat > 0 else 0

            iv_value = None
            c_price = d.get("callPrice", 0) or 0
            p_price = d.get("putPrice", 0) or 0

            if T_val > 0 and F_hat > 0:
                # OTM 优先：K >= F̂ 用 Call，K < F̂ 用 Put
                # Black 模型：BS(S=F̂, K, r=0, T, σ, q=0)
                # 市场价需折算到远期：price_fwd = price_spot · e^(rT)
                ctx = PricingContext(s=F_hat, k=strike_f, r=0.0, t=T_val, sigma=0.2, q=0.0)
                if strike_f >= F_hat:
                    # OTM Call (或 ATM)
                    if c_price > 0:
                        fwd_price = c_price * math.exp(r_rate * T_val)
                        iv_calc = implied_volatility(fwd_price, ctx, "CALL")
                        if iv_calc and 0.005 < iv_calc < 5.0:
                            iv_value = iv_calc
                else:
                    # OTM Put
                    if p_price > 0:
                        fwd_price = p_price * math.exp(r_rate * T_val)
                        iv_calc = implied_volatility(fwd_price, ctx, "PUT")
                        if iv_calc and 0.005 < iv_calc < 5.0:
                            iv_value = iv_calc

                # 如果 OTM 侧失败，尝试另一侧
                if iv_value is None:
                    alt_price = p_price if strike_f >= F_hat else c_price
                    alt_type: Literal["CALL", "PUT"] = "PUT" if strike_f >= F_hat else "CALL"
                    if alt_price > 0:
                        fwd_price = alt_price * math.exp(r_rate * T_val)
                        iv_calc = implied_volatility(fwd_price, ctx, alt_type)
                        if iv_calc and 0.005 < iv_calc < 5.0:
                            iv_value = iv_calc

            if iv_value and iv_value > 0:
                surface_points.append({
                    "strike": strike_f, "expiry": exp_str,
                    "iv": round(iv_value, 6),
                    "moneyness": round(m, 6), "T": T_val,
                    "remainingDays": d["remainingDays"],
                })

            # 持仓量柱形图数据
            call_oi = d.get("callOi", 0) or 0
            put_oi = d.get("putOi", 0) or 0
            if call_oi > 0 or put_oi > 0:
                volume_bars.append({
                    "strike": strike_f, "expiry": exp_str,
                    "moneyness": round(m, 6), "T": T_val,
                    "callOi": call_oi, "putOi": put_oi,
                    "callVolume": d.get("callVolume", 0) or 0,
                    "putVolume": d.get("putVolume", 0) or 0,
                })

    else:
        # ══════════════════════════════════════════════════════════════
        # Raw 模式：使用数据库中预计算的 IV（OTM 优先 + vega 加权平均）
        # ══════════════════════════════════════════════════════════════
        for key, d in sorted(pair_data.items(), key=lambda x: (x[0][1], x[0][0])):
            strike_f = d["strike"]
            T_val = d["T"]
            m = math.log(strike_f / spot) if spot > 0 else 0

            iv_value = None
            call_iv = d.get("callIv")
            put_iv = d.get("putIv")
            call_vega = abs(d.get("callVega") or 0)
            put_vega = abs(d.get("putVega") or 0)

            if spot > 0:
                if strike_f > spot * 1.02:
                    iv_value = call_iv if call_iv and call_iv > 0 else (put_iv if put_iv and put_iv > 0 else None)
                elif strike_f < spot * 0.98:
                    iv_value = put_iv if put_iv and put_iv > 0 else (call_iv if call_iv and call_iv > 0 else None)
                else:
                    if call_iv and call_iv > 0 and put_iv and put_iv > 0:
                        if call_vega > 0 and put_vega > 0:
                            iv_value = (call_iv * call_vega + put_iv * put_vega) / (call_vega + put_vega)
                        else:
                            iv_value = (call_iv + put_iv) / 2.0
                    elif call_iv and call_iv > 0:
                        iv_value = call_iv
                    elif put_iv and put_iv > 0:
                        iv_value = put_iv
            else:
                if call_iv and call_iv > 0 and put_iv and put_iv > 0:
                    iv_value = (call_iv + put_iv) / 2.0
                elif call_iv and call_iv > 0:
                    iv_value = call_iv
                elif put_iv and put_iv > 0:
                    iv_value = put_iv

            if iv_value and iv_value > 0:
                surface_points.append({
                    "strike": strike_f, "expiry": d["expiry"],
                    "iv": round(iv_value, 6),
                    "moneyness": round(m, 6), "T": T_val,
                    "remainingDays": d["remainingDays"],
                })

            call_oi = d.get("callOi", 0) or 0
            put_oi = d.get("putOi", 0) or 0
            if call_oi > 0 or put_oi > 0:
                volume_bars.append({
                    "strike": strike_f, "expiry": d["expiry"],
                    "moneyness": round(m, 6), "T": T_val,
                    "callOi": call_oi, "putOi": put_oi,
                    "callVolume": d.get("callVolume", 0) or 0,
                    "putVolume": d.get("putVolume", 0) or 0,
                })

    # ── 无套利检查：Butterfly + Calendar Spread ──
    surface_points = _arbitrage_filter(surface_points)

    # ── 计算 ATM IV 和 Delta-based Skew (按到期日分组) ──
    by_expiry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in surface_points:
        by_expiry[p["expiry"]].append(p)

    # 获取前一交易日数据用于日差计算
    prev_atm: dict[str, float] = {}
    prev_skew: dict[str, float] = {}
    prev_date: date | None = None
    with db.get_session() as session:
        prev_td = (
            session.query(OptionDailyBar.trade_date)
            .filter(OptionDailyBar.trade_date < td)
            .order_by(OptionDailyBar.trade_date.desc())
            .first()
        )
        if prev_td:
            prev_date = prev_td[0]
            prev_bar = session.query(DailyBar).filter(
                DailyBar.symbol == underlying, DailyBar.trade_date == prev_date
            ).first()
            prev_spot = float(prev_bar.close_price) if prev_bar and prev_bar.close_price else spot

            prev_rows = (
                session.query(
                    OptionContract.strike, OptionContract.expiry_date,
                    OptionContract.option_type, OptionDailyBar.iv, OptionDailyBar.delta,
                )
                .join(OptionDailyBar, OptionContract.symbol == OptionDailyBar.symbol)
                .filter(
                    OptionContract.underlying_symbol == underlying,
                    OptionDailyBar.trade_date == prev_date,
                    OptionDailyBar.iv.isnot(None),
                )
                .all()
            )
            # 按 (expiry, strike) 分组
            prev_by_exp: dict[str, list[dict]] = defaultdict(list)
            for s, e, ot, iv, dlt in prev_rows:
                iv_f = float(iv) if iv else 0
                if iv_f > 0:
                    exp_s = _date_str(e)
                    if exp_s:
                        prev_by_exp[exp_s].append({
                            "strike": float(s), "iv": iv_f,
                            "delta": float(dlt) if dlt else None,
                            "type": ot,
                        })

            for exp_s, items in prev_by_exp.items():
                sorted_items = sorted(items, key=lambda x: x["strike"])
                atm_p = min(sorted_items, key=lambda x: abs(x["strike"] - prev_spot))
                prev_atm[exp_s] = atm_p["iv"]
                prev_skew[exp_s] = _calc_delta_skew(sorted_items, prev_spot)

    atm_iv_data: list[dict[str, Any]] = []
    skew_data: list[dict[str, Any]] = []

    for exp_str in sorted(by_expiry.keys()):
        grp = sorted(by_expiry[exp_str], key=lambda x: x["strike"])
        if not grp:
            continue
        T_val = grp[0]["T"]
        remaining = grp[0]["remainingDays"]

        # ATM: 找最接近参考价的行权价（synthetic 模式用合成期货价格）
        ref_price = fwd_map.get(exp_str, spot) if mode == "synthetic" else spot
        atm_pt = min(grp, key=lambda x: abs(x["strike"] - ref_price))
        atm_iv = atm_pt["iv"]
        prev_iv = prev_atm.get(exp_str)
        atm_iv_data.append({
            "expiry": exp_str, "T": T_val, "remainingDays": remaining,
            "atmIv": round(atm_iv, 6), "atmStrike": atm_pt["strike"],
            "prevAtmIv": round(prev_iv, 6) if prev_iv else None,
        })

        # Delta-based Skew: 25Δ Put IV - 25Δ Call IV
        # 用 pair_data 中的 delta 信息来找 25Δ 合约
        expiry_pairs = [d for k, d in pair_data.items() if k[1] == exp_str]
        skew_val = _calc_delta_skew_from_pairs(expiry_pairs, ref_price)
        prev_sk = prev_skew.get(exp_str)
        skew_data.append({
            "expiry": exp_str, "T": T_val, "remainingDays": remaining,
            "skew": round(skew_val, 6),
            "prevSkew": round(prev_sk, 6) if prev_sk else None,
        })

    # SVI 拟合 (所有模式都提供)
    svi_points: list[dict[str, Any]] = []
    if len(surface_points) > 5:
        svi_points = _fit_svi_surface(surface_points)

    # 计算昨日合成远期
    yd_synth_fwd: dict[str, float] | None = None
    if mode == "synthetic" and prev_date is not None:
        try:
            raw = _compute_synthetic_forwards(underlying, prev_date, r_rate)
            yd_synth_fwd = {k: round(v, 6) for k, v in raw.items()} if raw else None
        except Exception as e:
            import traceback
            traceback.print_exc()
            yd_synth_fwd = None

    return {
        "spot": round(spot, 4),
        "tradeDate": _date_str(td),
        "points": surface_points,
        "sviPoints": svi_points,
        "volumeBars": volume_bars,
        "atmIvData": atm_iv_data,
        "skewData": skew_data,
        "mode": mode,
        "riskFreeRate": round(r_rate, 6),
        "syntheticForwards": {k: round(v, 6) for k, v in fwd_map.items()} if fwd_map else None,
        "yesterdaySyntheticForwards": yd_synth_fwd,
    }


@app.get("/api/viz/option-chain/{underlying}")
def get_option_chain(
    underlying: str,
    trade_date: str = Query(...),
    expiry: str | None = None,
) -> list[dict[str, Any]]:
    """
    期权链数据：返回指定交易日的期权链，按到期日分组。
    如果指定 expiry，只返回该到期日的数据。
    """
    td = _parse_date(trade_date)
    exp_filter = _parse_date(expiry) if expiry else None

    with db.get_session() as session:
        # 获取标的价格
        underlying_bar = session.query(DailyBar).filter(
            DailyBar.symbol == underlying,
            DailyBar.trade_date == td
        ).first()
        underlying_price = float(underlying_bar.close_price) if underlying_bar and underlying_bar.close_price else 0

        # 查询期权数据
        query = (
            session.query(
                OptionContract.symbol,
                OptionContract.strike,
                OptionContract.expiry_date,
                OptionContract.option_type,
                OptionDailyBar.close_price,
                OptionDailyBar.volume,
                OptionDailyBar.open_interest,
                OptionDailyBar.iv,
                OptionDailyBar.delta,
                OptionDailyBar.gamma,
                OptionDailyBar.theta,
                OptionDailyBar.vega,
                OptionDailyBar.rho,
            )
            .join(OptionDailyBar, OptionContract.symbol == OptionDailyBar.symbol)
            .filter(
                OptionContract.underlying_symbol == underlying,
                OptionDailyBar.trade_date == td,
            )
        )

        if exp_filter:
            query = query.filter(OptionContract.expiry_date == exp_filter)

        rows = query.order_by(OptionContract.expiry_date, OptionContract.strike, OptionContract.option_type).all()

    # 按到期日和行权价分组
    grouped: dict[str, dict[float, dict[str, Any]]] = {}
    for symbol, strike, expiry_date, opt_type, close, volume, oi, iv, delta, gamma, theta, vega, rho in rows:
        exp_str = _date_str(expiry_date)
        if exp_str not in grouped:
            grouped[exp_str] = {}

        strike_val = float(strike)
        if strike_val not in grouped[exp_str]:
            grouped[exp_str][strike_val] = {"call": None, "put": None}

        contract_data = {
            "symbol": symbol,
            "strike": strike_val,
            "expiry": exp_str,
            "type": opt_type,
            "bid": None,  # 暂无买卖价数据
            "ask": None,
            "last": float(close) if close else None,
            "volume": int(volume) if volume else 0,
            "openInterest": int(oi) if oi else 0,
            "iv": float(iv) if iv else None,
            "delta": float(delta) if delta else None,
            "gamma": float(gamma) if gamma else None,
            "theta": float(theta) if theta else None,
            "vega": float(vega) if vega else None,
            "rho": float(rho) if rho else None,
        }

        if opt_type == "C":
            grouped[exp_str][strike_val]["call"] = contract_data
        else:
            grouped[exp_str][strike_val]["put"] = contract_data

    # 构建返回结果
    result = []
    for exp_str in sorted(grouped.keys()):
        strikes_list = []
        for strike_val in sorted(grouped[exp_str].keys()):
            strikes_list.append({
                "strike": strike_val,
                "call": grouped[exp_str][strike_val]["call"],
                "put": grouped[exp_str][strike_val]["put"],
            })

        result.append({
            "expiry": exp_str,
            "underlyingPrice": underlying_price,
            "strikes": strikes_list,
        })

    return result


@app.get("/api/viz/contract/{symbol}")
def get_contract_data(
    symbol: str,
    start_date: str = "2015-01-01",
    end_date: str = "2026-12-31",
) -> dict[str, Any]:
    """
    单个期权合约数据查询：返回合约信息 + 历史K线 + 标的价格 + Greeks时序
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    with db.get_session() as session:
        # 1. 获取合约信息
        contract = session.query(OptionContract).filter(OptionContract.symbol == symbol).first()
        if not contract:
            raise HTTPException(status_code=404, detail="合约不存在")

        # 2. 获取期权K线数据
        bars = (
            session.query(OptionDailyBar)
            .filter(
                OptionDailyBar.symbol == symbol,
                OptionDailyBar.trade_date >= start,
                OptionDailyBar.trade_date <= end,
            )
            .order_by(OptionDailyBar.trade_date)
            .all()
        )

        # 3. 获取标的价格数据
        underlying_bars = (
            session.query(DailyBar)
            .filter(
                DailyBar.symbol == contract.underlying_symbol,
                DailyBar.trade_date >= start,
                DailyBar.trade_date <= end,
            )
            .order_by(DailyBar.trade_date)
            .all()
        )

        # 构建标的价格映射
        underlying_price_map = {
            _date_str(b.trade_date): float(b.close_price) if b.close_price else None
            for b in underlying_bars
        }

        # 4. 构建返回数据
        dates = []
        ohlc = []
        volumes = []
        ivs = []
        deltas = []
        gammas = []
        thetas = []
        vegas = []
        underlying_prices = []

        for bar in bars:
            date_str = _date_str(bar.trade_date)
            dates.append(date_str)
            ohlc.append([
                round(float(bar.open_price), 4),
                round(float(bar.close_price), 4),
                round(float(bar.low_price), 4),
                round(float(bar.high_price), 4),
            ])
            volumes.append(int(bar.volume) if bar.volume else 0)
            ivs.append(round(float(bar.iv), 4) if bar.iv else None)
            deltas.append(round(float(bar.delta), 4) if bar.delta else None)
            gammas.append(round(float(bar.gamma), 6) if bar.gamma else None)
            thetas.append(round(float(bar.theta), 4) if bar.theta else None)
            vegas.append(round(float(bar.vega), 4) if bar.vega else None)
            underlying_prices.append(underlying_price_map.get(date_str))

        return {
            "contract": {
                "symbol": contract.symbol,
                "underlying": contract.underlying_symbol,
                "type": contract.option_type,
                "strike": float(contract.strike),
                "expiry": _date_str(contract.expiry_date),
            },
            "dates": dates,
            "ohlc": ohlc,
            "volumes": volumes,
            "ivs": ivs,
            "deltas": deltas,
            "gammas": gammas,
            "thetas": thetas,
            "vegas": vegas,
            "underlyingPrices": underlying_prices,
        }


def backfill_open_interest(csv_path: str) -> int:
    """
    从 CSV 批量回填 open_interest 到已有的 option_daily_bars 记录。
    使用原生 SQL executemany 批量更新，速度比逐行 ORM 快 100x+。
    用法: python -c "from ccquant.ui.server import backfill_open_interest; print(backfill_open_interest('path/to/csv'))"
    """
    from sqlalchemy import text

    df = pd.read_csv(csv_path)
    if 'open_interest' not in df.columns or 'security_id' not in df.columns:
        raise ValueError("CSV 需包含 security_id 和 open_interest 列")

    df["trade_date_parsed"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

    # 过滤掉 open_interest 为空的行
    valid = df.dropna(subset=["open_interest"])

    # 构建批量更新数据
    updates = [
        {
            "sym": str(row["security_id"]),
            "td": row["trade_date_parsed"].date().isoformat(),
            "oi": int(row["open_interest"]),
        }
        for _, row in valid.iterrows()
    ]

    print(f"准备更新 {len(updates)} 条记录...")

    # 分批执行，每批 5000 条
    batch_size = 5000
    total_updated = 0
    with db.engine.connect() as conn:
        update_sql = text(
            "UPDATE option_daily_bars SET open_interest = :oi "
            "WHERE symbol = :sym AND trade_date = :td"
        )
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            conn.execute(update_sql, batch)
            conn.commit()
            total_updated += len(batch)
            print(f"  已更新 {total_updated}/{len(updates)}...")

    return total_updated


# ========== Strategy API ==========

@app.get("/api/strategies")
def list_strategies() -> list[dict[str, Any]]:
    strategies = []
    if not STRATEGY_DIR.exists():
        return strategies
    for py_file in sorted(STRATEGY_DIR.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        stat = py_file.stat()
        content = py_file.read_text(encoding="utf-8", errors="replace")
        description = ""
        category = "option"
        doc_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if doc_match:
            description = doc_match.group(1).strip().split("\n")[0]
        if any(kw in content.lower() for kw in ["lightgbm", "sklearn", "torch", "tensorflow", "keras"]):
            category = "ml"
        strategies.append({
            "name": py_file.stem.replace("_", " ").title(),
            "filename": py_file.name,
            "description": description,
            "category": category,
            "createdAt": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "code": "",
        })
    return strategies


@app.get("/api/strategies/{filename}/code")
def get_strategy_code(filename: str) -> dict[str, str]:
    filepath = STRATEGY_DIR / filename
    if not filepath.exists() or filepath.suffix != ".py":
        return {"code": "# File not found"}
    return {"code": filepath.read_text(encoding="utf-8", errors="replace")}


@app.post("/api/strategies/{filename}/open-ide")
def open_in_ide(filename: str) -> dict[str, bool]:
    filepath = STRATEGY_DIR / filename
    if not filepath.exists():
        return {"success": False}
    try:
        subprocess.Popen(["code", str(filepath)], shell=True)
        return {"success": True}
    except Exception:
        return {"success": False}


# ========== Backtest API ==========

class BacktestRequest(BaseModel):
    strategy_name: str = "BuyCallStrategy"
    initial_capital: float = 1_000_000.0
    slippage: float = 0.0
    rate: float = 0.0003
    underlying: str = "510050"
    params: dict[str, Any] | None = None


@app.post("/api/backtest/run")
def run_backtest(req: BacktestRequest) -> dict[str, Any]:
    try:
        from ccquant.backtest.engine import OptionBacktestEngine
        from ccquant.strategy.strategies import get_strategy_class
        from ccquant.core.object import BarData
        from ccquant.core.constant import Exchange, Interval

        engine = OptionBacktestEngine()
        engine.set_parameters(
            initial_capital=req.initial_capital,
            slippage=req.slippage,
            rate=req.rate,
        )
        bars_dict: dict[str, list[BarData]] = {}
        demo_symbols = [("510050C2401M02500", "SSE"), ("510050P2401M02500", "SSE")]
        for sym, exch in demo_symbols:
            bars = []
            price = 0.1
            for i in range(30):
                dt = datetime(2024, 1, 1, 9, 30) + pd.Timedelta(days=i)
                price = max(0.01, price + (0.005 if i % 5 == 0 else -0.002))
                bar = BarData(
                    symbol=sym, exchange=Exchange(exch), datetime=dt,
                    interval=Interval.DAILY,
                    open_price=price, high_price=price + 0.005,
                    low_price=price - 0.005, close_price=price,
                    gateway_name="BACKTEST",
                )
                bars.append(bar)
            bars_dict[f"{sym}.{exch}"] = bars
        engine.load_data(bars_dict)
        strategy_class = get_strategy_class(req.strategy_name)
        strategy = strategy_class(engine, req.params or {})
        engine.strategy = strategy
        engine.run_backtesting()
        result = engine.get_result()
        return {"success": True, "result": result.to_dict()}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/backtest/history")
def get_backtest_history(limit: int = 50) -> list[dict]:
    records = db.get_backtests(limit)
    return [
        {
            "id": r.id, "name": r.name, "strategy": r.strategy_name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


# ========== Static File Serving ==========

_DIST_PATH = Path(__file__).resolve().parent.parent.parent / "ccquant-web" / "dist"
if _DIST_PATH.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST_PATH / "assets")), name="assets")

    @app.get("/")
    def serve_index():
        return FileResponse(str(_DIST_PATH / "index.html"))

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
        target = _DIST_PATH / full_path
        if target.exists() and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(_DIST_PATH / "index.html"))


if __name__ == "__main__":
    uvicorn.run("ccquant.ui.server:app", host="0.0.0.0", port=8080, reload=False)
