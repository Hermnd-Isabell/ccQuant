"""Strategy module"""

from ccquant.strategy.template import (
    BuyCallStrategy,
    StraddleStrategy,
    IronCondorStrategy,
    SimpleBuyHoldStrategy,
    get_strategy_class,
)
from ccquant.strategy.iv_predict import (
    IvPredictStrategy,
    IvPredictStrategyA,
    IvPredictStrategyAEnhanced,
    IvPredictStrategyB,
    IvPredictStrategyC,
)

__all__ = [
    'BuyCallStrategy',
    'StraddleStrategy',
    'IronCondorStrategy',
    'SimpleBuyHoldStrategy',
    'get_strategy_class',
    'IvPredictStrategy',
    'IvPredictStrategyA',
    'IvPredictStrategyAEnhanced',
    'IvPredictStrategyB',
    'IvPredictStrategyC',
]
