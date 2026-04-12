"""
Order matcher for backtesting.
Follows vnpy's bar-matching logic to avoid lookahead bias.
"""

from datetime import datetime

from ccquant.core.constant import Direction, Offset, Status
from ccquant.core.object import BarData, OrderData, TradeData, OrderRequest


def cross_limit_order(
    order: OrderData,
    bar: BarData,
    trade_counter: int,
    size: float = 1.0,
    slippage: float = 0.0,
    rate: float = 0.0,
    min_commission: float = 0.0
) -> TradeData | None:
    """
    Try to cross a limit order against a bar.
    Returns TradeData if filled, otherwise None.
    Match logic (bar mode):
        - Long limit fills if order.price >= bar.low_price
        - Short limit fills if order.price <= bar.high_price
        - Fill price is bounded by open_price to avoid lookahead bias.
    """
    if order.status in {Status.ALLTRADED, Status.CANCELLED, Status.REJECTED}:
        return None

    remaining: float = order.volume - order.traded
    if remaining <= 0:
        return None

    # Buy limit
    if order.direction == Direction.LONG:
        if order.price >= bar.low_price:
            trade_price: float = min(order.price, bar.open_price)
        else:
            return None
    # Sell limit
    elif order.direction == Direction.SHORT:
        if order.price <= bar.high_price:
            trade_price = max(order.price, bar.open_price)
        else:
            return None
    else:
        return None

    # Apply slippage
    if slippage:
        if order.direction == Direction.LONG:
            trade_price += slippage
        else:
            trade_price -= slippage

    trade_price = round(trade_price, 4)

    trade: TradeData = TradeData(
        symbol=order.symbol,
        exchange=order.exchange,
        orderid=order.orderid,
        tradeid=str(trade_counter),
        direction=order.direction,
        offset=order.offset or Offset.OPEN,
        price=trade_price,
        volume=remaining,
        datetime=bar.datetime,
        gateway_name=order.gateway_name,
    )

    # Update order status
    order.traded += remaining
    order.status = Status.ALLTRADED

    return trade


def build_order_from_request(req: OrderRequest, gateway_name: str, orderid: str) -> OrderData:
    """
    Build an OrderData from an OrderRequest for backtesting.
    """
    return req.create_order_data(orderid, gateway_name)
