"""
General constant enums used for trading.
"""

from enum import Enum


class Direction(Enum):
    """
    Direction of order/trade/position.
    """
    LONG = "Long"
    SHORT = "Short"
    NET = "Net"


class Offset(Enum):
    """
    Offset of order/trade.
    """
    NONE = ""
    OPEN = "Open"
    CLOSE = "Close"
    CLOSETODAY = "CloseToday"
    CLOSEYESTERDAY = "CloseYesterday"


class Status(Enum):
    """
    Order status.
    """
    SUBMITTING = "Submitting"
    NOTTRADED = "NotTraded"
    PARTTRADED = "PartTraded"
    ALLTRADED = "AllTraded"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


class Product(Enum):
    """
    Product class.
    """
    EQUITY = "Equity"
    FUTURES = "Futures"
    OPTION = "Option"
    INDEX = "Index"
    FOREX = "Forex"
    SPOT = "Spot"
    ETF = "ETF"
    BOND = "Bond"
    WARRANT = "Warrant"
    SPREAD = "Spread"
    FUND = "Fund"
    CFD = "CFD"
    SWAP = "Swap"


class OrderType(Enum):
    """
    Order type.
    """
    LIMIT = "Limit"
    MARKET = "Market"
    STOP = "STOP"
    FAK = "FAK"
    FOK = "FOK"
    RFQ = "RFQ"
    ETF = "ETF"


class OptionType(Enum):
    """
    Option type.
    """
    CALL = "Call"
    PUT = "Put"


class Exchange(Enum):
    """
    Exchange.
    """
    # Chinese
    CFFEX = "CFFEX"
    SHFE = "SHFE"
    CZCE = "CZCE"
    DCE = "DCE"
    INE = "INE"
    GFEX = "GFEX"
    SSE = "SSE"
    SZSE = "SZSE"
    BSE = "BSE"
    SHHK = "SHHK"
    SZHK = "SZHK"
    SGE = "SGE"
    WXE = "WXE"
    CFETS = "CFETS"
    XBOND = "XBOND"

    # Global
    SMART = "SMART"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    ARCA = "ARCA"
    EDGEA = "EDGEA"
    ISLAND = "ISLAND"
    BATS = "BATS"
    IEX = "IEX"
    AMEX = "AMEX"
    TSE = "TSE"
    NYMEX = "NYMEX"
    COMEX = "COMEX"
    GLOBEX = "GLOBEX"
    IDEALPRO = "IDEALPRO"
    CME = "CME"
    ICE = "ICE"
    SEHK = "SEHK"
    HKFE = "HKFE"
    SGX = "SGX"
    CBOT = "CBOT"
    CBOE = "CBOE"
    CFE = "CFE"
    DME = "DME"
    EUREX = "EUX"
    APEX = "APEX"
    LME = "LME"
    BMD = "BMD"
    TOCOM = "TOCOM"
    EUNX = "EUNX"
    KRX = "KRX"
    OTC = "OTC"
    IBKRATS = "IBKRATS"

    # Special
    LOCAL = "LOCAL"
    GLOBAL = "GLOBAL"


class Currency(Enum):
    """
    Currency.
    """
    USD = "USD"
    HKD = "HKD"
    CNY = "CNY"
    CAD = "CAD"


class Interval(Enum):
    """
    Interval of bar data.
    """
    MINUTE = "1m"
    HOUR = "1h"
    DAILY = "d"
    WEEKLY = "w"
    TICK = "tick"
