"""ccQuant 策略集合"""

from ccquant.strategy.template import (
    BuyCallStrategy,
    StraddleStrategy,
    IronCondorStrategy,
    BullCallSpreadStrategy,
    BearPutSpreadStrategy,
    StrangleStrategy,
    ButterflySpreadStrategy,
    CalendarSpreadStrategy,
    RatioSpreadStrategy,
    SimpleBuyHoldStrategy,
    DualThrustStrategy,
    PairTradingStrategy,
    get_strategy_class,
)

from ccquant.strategy.cta_strategies import (
    AtrRsiStrategy,
    BollChannelStrategy,
    DoubleMaStrategy,
    KingKeltnerStrategy,
    MultiSignalStrategy,
    MultiTimeframeStrategy,
    TestStrategy,
    TurtleSignalStrategy,
)

__all__ = [
    'BuyCallStrategy',
    'StraddleStrategy',
    'IronCondorStrategy',
    'BullCallSpreadStrategy',
    'BearPutSpreadStrategy',
    'StrangleStrategy',
    'ButterflySpreadStrategy',
    'CalendarSpreadStrategy',
    'RatioSpreadStrategy',
    'SimpleBuyHoldStrategy',
    'DualThrustStrategy',
    'PairTradingStrategy',
    'AtrRsiStrategy',
    'BollChannelStrategy',
    'DoubleMaStrategy',
    'KingKeltnerStrategy',
    'MultiSignalStrategy',
    'MultiTimeframeStrategy',
    'TestStrategy',
    'TurtleSignalStrategy',
    'get_strategy_class',
]
