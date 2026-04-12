"""
ccQuant 数据库模块
支持 SQLite/PostgreSQL，管理期权历史数据和回测结果
"""

import os
from contextlib import contextmanager
from datetime import datetime, date
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    create_engine, Column, String, Float, DateTime, Date,
    Integer, Text, ForeignKey, Index, func, and_
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.pool import StaticPool
import pandas as pd

# 数据库配置
DB_PATH = os.path.expanduser("~/.ccquant/ccquant.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

Base = declarative_base()


# ========== 数据模型 ==========

class Underlying(Base):
    """标的资产"""
    __tablename__ = 'underlyings'

    symbol = Column(String(20), primary_key=True)
    name = Column(String(100))
    underlying_type = Column(String(20), default='ETF')  # ETF/INDEX/STOCK
    exchange = Column(String(20))
    lot_size = Column(Integer, default=10000)
    price_tick = Column(Float, default=0.0001)
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    option_contracts = relationship("OptionContract", back_populates="underlying")
    daily_bars = relationship("DailyBar", back_populates="underlying")


class OptionContract(Base):
    """期权合约定义"""
    __tablename__ = 'option_contracts'

    symbol = Column(String(50), primary_key=True)
    underlying_symbol = Column(String(20), ForeignKey('underlyings.symbol'))
    option_type = Column(String(1))  # C/P
    strike = Column(Float)
    expiry_date = Column(Date)
    contract_month = Column(String(10))
    list_date = Column(Date)  # 上市日期

    # 关联
    underlying = relationship("Underlying", back_populates="option_contracts")
    daily_bars = relationship("OptionDailyBar", back_populates="contract")

    __table_args__ = (
        Index('idx_option_lookup', 'underlying_symbol', 'expiry_date', 'strike'),
    )


class DailyBar(Base):
    """标的历史日K线"""
    __tablename__ = 'daily_bars'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey('underlyings.symbol'))
    trade_date = Column(Date)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Integer)
    amount = Column(Float)  # 成交额

    # 关联
    underlying = relationship("Underlying", back_populates="daily_bars")

    __table_args__ = (
        Index('idx_daily_bar', 'symbol', 'trade_date', unique=True),
    )


class OptionDailyBar(Base):
    """期权历史日K线（包含希腊字母）"""
    __tablename__ = 'option_daily_bars'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(50), ForeignKey('option_contracts.symbol'))
    trade_date = Column(Date)

    # 价格
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Integer)
    amount = Column(Float)
    open_interest = Column(Integer)  # 持仓量
    pre_settle_price = Column(Float)  # 前结算价
    settle_price = Column(Float)  # 结算价
    remaining_time = Column(Integer)  # 剩余到期天数（自然日）

    # 隐含波动率和希腊字母
    iv = Column(Float)
    delta = Column(Float)
    gamma = Column(Float)
    theta = Column(Float)
    vega = Column(Float)
    rho = Column(Float)

    # 关联
    contract = relationship("OptionContract", back_populates="daily_bars")

    __table_args__ = (
        Index('idx_option_daily', 'symbol', 'trade_date', unique=True),
    )


class RiskFreeRate(Base):
    """无风险利率（如十年期国债利率）"""
    __tablename__ = 'risk_free_rates'

    id = Column(Integer, primary_key=True)
    trade_date = Column(Date, nullable=False)
    rate = Column(Float, nullable=False)  # 年化利率，如 0.03 表示 3%
    source = Column(String(50), default='ten_year')  # 来源标识

    __table_args__ = (
        Index('idx_rfr_date_source', 'trade_date', 'source', unique=True),
    )


class BacktestRecord(Base):
    """回测记录"""
    __tablename__ = 'backtest_records'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    strategy_name = Column(String(50))
    strategy_params = Column(Text)  # JSON格式
    underlyings = Column(Text)  # JSON格式
    start_date = Column(Date)
    end_date = Column(Date)
    initial_capital = Column(Float)

    # 结果统计
    total_return = Column(Float)
    annual_return = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    total_trades = Column(Integer)
    win_rate = Column(Float)

    # 详细结果存储路径
    result_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)


# ========== 数据库管理类 ==========

class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_url: Optional[str] = None):
        if db_url is None:
            db_url = f"sqlite:///{DB_PATH}"

        self.db_url = db_url
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

        # 创建表
        Base.metadata.create_all(self.engine)

        # 自动迁移：为已有表添加新列
        self._auto_migrate()

    def _auto_migrate(self) -> None:
        """检查并添加新增的列（ALTER TABLE）"""
        from sqlalchemy import inspect, text
        insp = inspect(self.engine)

        # option_daily_bars 新增列
        if insp.has_table('option_daily_bars'):
            cols = {c['name'] for c in insp.get_columns('option_daily_bars')}
            new_cols = {
                'open_interest': 'INTEGER',
                'pre_settle_price': 'REAL',
                'settle_price': 'REAL',
                'remaining_time': 'INTEGER',
            }
            with self.engine.connect() as conn:
                for col_name, col_type in new_cols.items():
                    if col_name not in cols:
                        conn.execute(text(
                            f"ALTER TABLE option_daily_bars ADD COLUMN {col_name} {col_type}"
                        ))
                conn.commit()

        # option_contracts 新增列
        if insp.has_table('option_contracts'):
            cols = {c['name'] for c in insp.get_columns('option_contracts')}
            if 'list_date' not in cols:
                with self.engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE option_contracts ADD COLUMN list_date DATE"
                    ))
                    conn.commit()

    def _create_engine(self):
        """创建数据库引擎"""
        if self.db_url.startswith('sqlite'):
            return create_engine(
                self.db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False
            )
        else:
            return create_engine(self.db_url, pool_pre_ping=True)

    @contextmanager
    def get_session(self) -> Session:
        """获取数据库会话"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    # ========== 标的操作 ==========

    def add_underlying(self, symbol: str, name: str,
                       underlying_type: str = 'ETF',
                       exchange: str = 'SSE',
                       lot_size: int = 10000) -> Underlying:
        with self.get_session() as session:
            underlying = Underlying(
                symbol=symbol, name=name,
                underlying_type=underlying_type,
                exchange=exchange, lot_size=lot_size
            )
            session.merge(underlying)
            return underlying

    def get_underlyings(self) -> List[Underlying]:
        with self.get_session() as session:
            return session.query(Underlying).all()

    # ========== 期权合约操作 ==========

    def add_option_contract(self, symbol: str, underlying_symbol: str,
                           option_type: str, strike: float,
                           expiry_date: date) -> OptionContract:
        with self.get_session() as session:
            contract = OptionContract(
                symbol=symbol,
                underlying_symbol=underlying_symbol,
                option_type=option_type,
                strike=strike,
                expiry_date=expiry_date,
                contract_month=expiry_date.strftime('%Y%m')
            )
            session.merge(contract)
            return contract

    def get_option_contracts(self, underlying: str,
                            expiry_date: Optional[date] = None) -> List[OptionContract]:
        with self.get_session() as session:
            query = session.query(OptionContract).filter(
                OptionContract.underlying_symbol == underlying
            )
            if expiry_date:
                query = query.filter(OptionContract.expiry_date == expiry_date)
            return query.order_by(OptionContract.strike).all()

    def get_expiry_dates(self, underlying: str) -> List[date]:
        with self.get_session() as session:
            result = session.query(OptionContract.expiry_date).filter(
                OptionContract.underlying_symbol == underlying
            ).distinct().order_by(OptionContract.expiry_date).all()
            return [r[0] for r in result]

    # ========== 历史数据操作 ==========

    def import_underlying_bars(self, df: pd.DataFrame, symbol: str) -> int:
        """
        导入标的历史数据，使用 upsert (INSERT OR REPLACE on unique index)
        df columns: trade_date, open, high, low, close, volume, amount
        """
        with self.get_session() as session:
            count = 0
            for _, row in df.iterrows():
                td = pd.to_datetime(row['trade_date']).date()
                # 先查是否存在
                existing = session.query(DailyBar).filter(
                    DailyBar.symbol == symbol,
                    DailyBar.trade_date == td,
                ).first()
                if existing:
                    existing.open_price = float(row['open'])
                    existing.high_price = float(row['high'])
                    existing.low_price = float(row['low'])
                    existing.close_price = float(row['close'])
                    existing.volume = int(row['volume']) if 'volume' in row else 0
                    existing.amount = float(row['amount']) if 'amount' in row else 0
                else:
                    bar = DailyBar(
                        symbol=symbol,
                        trade_date=td,
                        open_price=float(row['open']),
                        high_price=float(row['high']),
                        low_price=float(row['low']),
                        close_price=float(row['close']),
                        volume=int(row['volume']) if 'volume' in row else 0,
                        amount=float(row['amount']) if 'amount' in row else 0,
                    )
                    session.add(bar)
                count += 1
            return count

    def import_option_bars(self, df: pd.DataFrame, symbol: str) -> int:
        """导入期权历史数据"""
        with self.get_session() as session:
            count = 0
            for _, row in df.iterrows():
                td = pd.to_datetime(row['trade_date']).date()
                existing = session.query(OptionDailyBar).filter(
                    OptionDailyBar.symbol == symbol,
                    OptionDailyBar.trade_date == td,
                ).first()
                vals = dict(
                    open_price=float(row['open']),
                    high_price=float(row['high']),
                    low_price=float(row['low']),
                    close_price=float(row['close']),
                    volume=int(row['volume']) if 'volume' in row else 0,
                    amount=float(row['amount']) if 'amount' in row else 0,
                    iv=float(row['iv']) if 'iv' in row and pd.notna(row['iv']) else None,
                    delta=float(row['delta']) if 'delta' in row and pd.notna(row['delta']) else None,
                    gamma=float(row['gamma']) if 'gamma' in row and pd.notna(row['gamma']) else None,
                    theta=float(row['theta']) if 'theta' in row and pd.notna(row['theta']) else None,
                    vega=float(row['vega']) if 'vega' in row and pd.notna(row['vega']) else None,
                    rho=float(row['rho']) if 'rho' in row and pd.notna(row['rho']) else None,
                )
                if existing:
                    for k, v in vals.items():
                        setattr(existing, k, v)
                else:
                    bar = OptionDailyBar(symbol=symbol, trade_date=td, **vals)
                    session.add(bar)
                count += 1
            return count

    def get_underlying_bars(self, symbol: str,
                           start_date: date,
                           end_date: date) -> pd.DataFrame:
        with self.get_session() as session:
            bars = session.query(DailyBar).filter(
                DailyBar.symbol == symbol,
                DailyBar.trade_date >= start_date,
                DailyBar.trade_date <= end_date
            ).order_by(DailyBar.trade_date).all()

            if not bars:
                return pd.DataFrame()

            data = [{
                'trade_date': b.trade_date,
                'open': b.open_price,
                'high': b.high_price,
                'low': b.low_price,
                'close': b.close_price,
                'volume': b.volume,
                'amount': b.amount
            } for b in bars]

            return pd.DataFrame(data)

    def get_option_bars(self, symbol: str,
                       start_date: date,
                       end_date: date) -> pd.DataFrame:
        with self.get_session() as session:
            bars = session.query(OptionDailyBar).filter(
                OptionDailyBar.symbol == symbol,
                OptionDailyBar.trade_date >= start_date,
                OptionDailyBar.trade_date <= end_date
            ).order_by(OptionDailyBar.trade_date).all()

            if not bars:
                return pd.DataFrame()

            data = [{
                'trade_date': b.trade_date,
                'open': b.open_price,
                'high': b.high_price,
                'low': b.low_price,
                'close': b.close_price,
                'volume': b.volume,
                'amount': b.amount,
                'iv': b.iv,
                'delta': b.delta,
                'gamma': b.gamma,
                'theta': b.theta,
                'vega': b.vega,
                'rho': b.rho
            } for b in bars]

            return pd.DataFrame(data)

    # ========== 查询辅助 ==========

    def count_option_bars(
        self,
        underlying: str,
        expiry: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        symbol_like: Optional[str] = None,
    ) -> int:
        """统计期权K线数量（带筛选条件）"""
        with self.get_session() as session:
            query = (
                session.query(func.count(OptionDailyBar.id))
                .join(OptionContract, OptionDailyBar.symbol == OptionContract.symbol)
                .filter(OptionContract.underlying_symbol == underlying)
            )
            if expiry:
                query = query.filter(OptionContract.expiry_date == expiry)
            if start_date:
                query = query.filter(OptionDailyBar.trade_date >= start_date)
            if end_date:
                query = query.filter(OptionDailyBar.trade_date <= end_date)
            if symbol_like:
                query = query.filter(OptionDailyBar.symbol.contains(symbol_like))
            return query.scalar() or 0

    def count_option_contracts(
        self,
        underlying: str,
        expiry: Optional[date] = None,
    ) -> int:
        """统计期权合约数量（带筛选条件）"""
        with self.get_session() as session:
            query = session.query(func.count(OptionContract.symbol)).filter(
                OptionContract.underlying_symbol == underlying
            )
            if expiry:
                query = query.filter(OptionContract.expiry_date == expiry)
            return query.scalar() or 0

    def query_option_bars_page(
        self,
        underlying: str,
        page: int = 1,
        page_size: int = 200,
        expiry: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        symbol_like: Optional[str] = None,
    ) -> tuple[list[OptionDailyBar], int]:
        """分页查询期权K线，返回 (rows, total)"""
        with self.get_session() as session:
            query = (
                session.query(OptionDailyBar)
                .join(OptionContract, OptionDailyBar.symbol == OptionContract.symbol)
                .filter(OptionContract.underlying_symbol == underlying)
            )
            if expiry:
                query = query.filter(OptionContract.expiry_date == expiry)
            if start_date:
                query = query.filter(OptionDailyBar.trade_date >= start_date)
            if end_date:
                query = query.filter(OptionDailyBar.trade_date <= end_date)
            if symbol_like:
                query = query.filter(OptionDailyBar.symbol.contains(symbol_like))

            query = query.order_by(OptionDailyBar.trade_date.desc(), OptionDailyBar.symbol)
            total = query.count()
            offset = (page - 1) * page_size
            rows = query.offset(offset).limit(page_size).all()
            return rows, total

    def query_merged_bars_page(
        self,
        underlying: str,
        page: int = 1,
        page_size: int = 200,
        expiry: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        symbol_like: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """期权K线 LEFT JOIN 标的K线，按 trade_date 匹配，返回纯 dict 列表（无 ORM 对象）"""
        with self.get_session() as session:
            query = (
                session.query(
                    OptionDailyBar.trade_date,
                    OptionDailyBar.symbol,
                    OptionDailyBar.open_price,
                    OptionDailyBar.high_price,
                    OptionDailyBar.low_price,
                    OptionDailyBar.close_price,
                    OptionDailyBar.volume,
                    OptionDailyBar.amount,
                    OptionDailyBar.iv,
                    OptionDailyBar.delta,
                    OptionDailyBar.gamma,
                    OptionDailyBar.theta,
                    OptionDailyBar.vega,
                    OptionDailyBar.rho,
                    DailyBar.open_price.label('fund_open'),
                    DailyBar.high_price.label('fund_high'),
                    DailyBar.low_price.label('fund_low'),
                    DailyBar.close_price.label('fund_close'),
                    DailyBar.volume.label('fund_volume'),
                    DailyBar.amount.label('fund_amount'),
                )
                .join(OptionContract, OptionDailyBar.symbol == OptionContract.symbol)
                .outerjoin(
                    DailyBar,
                    and_(
                        DailyBar.symbol == underlying,
                        DailyBar.trade_date == OptionDailyBar.trade_date,
                    ),
                )
                .filter(OptionContract.underlying_symbol == underlying)
            )
            if expiry:
                query = query.filter(OptionContract.expiry_date == expiry)
            if start_date:
                query = query.filter(OptionDailyBar.trade_date >= start_date)
            if end_date:
                query = query.filter(OptionDailyBar.trade_date <= end_date)
            if symbol_like:
                query = query.filter(OptionDailyBar.symbol.contains(symbol_like))

            query = query.order_by(OptionDailyBar.trade_date.desc(), OptionDailyBar.symbol)
            total = query.count()
            offset = (page - 1) * page_size
            raw = query.offset(offset).limit(page_size).all()

            rows: list[dict] = []
            for r in raw:
                rows.append({
                    'trade_date': r.trade_date,
                    'symbol': r.symbol,
                    'open_price': r.open_price,
                    'high_price': r.high_price,
                    'low_price': r.low_price,
                    'close_price': r.close_price,
                    'volume': r.volume,
                    'amount': r.amount,
                    'iv': r.iv,
                    'delta': r.delta,
                    'gamma': r.gamma,
                    'theta': r.theta,
                    'vega': r.vega,
                    'rho': r.rho,
                    'fund_open': r.fund_open,
                    'fund_high': r.fund_high,
                    'fund_low': r.fund_low,
                    'fund_close': r.fund_close,
                    'fund_volume': r.fund_volume,
                    'fund_amount': r.fund_amount,
                })
            return rows, total

    def query_daily_bars_page(
        self,
        symbol: str,
        page: int = 1,
        page_size: int = 200,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> tuple[list[DailyBar], int]:
        """分页查询标的K线"""
        with self.get_session() as session:
            query = session.query(DailyBar).filter(DailyBar.symbol == symbol)
            if start_date:
                query = query.filter(DailyBar.trade_date >= start_date)
            if end_date:
                query = query.filter(DailyBar.trade_date <= end_date)
            query = query.order_by(DailyBar.trade_date.desc())
            total = query.count()
            offset = (page - 1) * page_size
            rows = query.offset(offset).limit(page_size).all()
            return rows, total

    def delete_option_bars(self, underlying: str,
                          expiry: Optional[date] = None,
                          start_date: Optional[date] = None,
                          end_date: Optional[date] = None,
                          symbol_like: Optional[str] = None) -> int:
        """删除期权K线数据（支持日期范围和合约筛选）"""
        with self.get_session() as session:
            subq = session.query(OptionContract.symbol).filter(
                OptionContract.underlying_symbol == underlying
            )
            if expiry:
                subq = subq.filter(OptionContract.expiry_date == expiry)

            query = session.query(OptionDailyBar).filter(
                OptionDailyBar.symbol.in_(subq)
            )
            if start_date:
                query = query.filter(OptionDailyBar.trade_date >= start_date)
            if end_date:
                query = query.filter(OptionDailyBar.trade_date <= end_date)
            if symbol_like:
                query = query.filter(OptionDailyBar.symbol.contains(symbol_like))

            count = query.delete(synchronize_session='fetch')
            return count

    def delete_daily_bars(self, symbol: str,
                          start_date: Optional[date] = None,
                          end_date: Optional[date] = None) -> int:
        """删除标的K线数据（支持日期范围）"""
        with self.get_session() as session:
            query = session.query(DailyBar).filter(
                DailyBar.symbol == symbol
            )
            if start_date:
                query = query.filter(DailyBar.trade_date >= start_date)
            if end_date:
                query = query.filter(DailyBar.trade_date <= end_date)
            count = query.delete(synchronize_session='fetch')
            return count

    # ========== 无风险利率操作 ==========

    def get_risk_free_rate(self, trade_date: date, source: str = 'ten_year') -> Optional[float]:
        """获取指定日期的无风险利率，如果当天没有则取最近的前一个交易日"""
        with self.get_session() as session:
            row = (
                session.query(RiskFreeRate.rate)
                .filter(RiskFreeRate.trade_date <= trade_date, RiskFreeRate.source == source)
                .order_by(RiskFreeRate.trade_date.desc())
                .first()
            )
            return float(row[0]) if row else None

    # ========== 回测记录操作 ==========

    def save_backtest(self, name: str, strategy_name: str,
                     strategy_params: Dict, underlyings: List[str],
                     start_date: date, end_date: date,
                     initial_capital: float,
                     statistics: Dict) -> int:
        import json
        with self.get_session() as session:
            record = BacktestRecord(
                name=name,
                strategy_name=strategy_name,
                strategy_params=json.dumps(strategy_params),
                underlyings=json.dumps(underlyings),
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                total_return=statistics.get('total_return'),
                annual_return=statistics.get('annual_return'),
                max_drawdown=statistics.get('max_drawdown'),
                sharpe_ratio=statistics.get('sharpe_ratio'),
                total_trades=statistics.get('total_trades'),
                win_rate=statistics.get('win_rate')
            )
            session.add(record)
            session.flush()
            return record.id

    def get_backtests(self, limit: int = 50) -> List[BacktestRecord]:
        with self.get_session() as session:
            return session.query(BacktestRecord).order_by(
                BacktestRecord.created_at.desc()
            ).limit(limit).all()


# 全局数据库实例
db = DatabaseManager()
