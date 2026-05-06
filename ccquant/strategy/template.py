"""策略模板 - 与新回测引擎兼容"""

from ccquant.backtest.template import StrategyTemplate


class BuyCallStrategy(StrategyTemplate):
    """买入看涨期权并持有"""

    parameters = [
        {'name': 'strike_offset', 'displayName': '行权价偏移', 'type': 'select', 'default': 0},
        {'name': 'expiry_days', 'displayName': '目标到期天数', 'type': 'number', 'default': 30},
        {'name': 'position_ratio', 'displayName': '仓位比例', 'type': 'number', 'default': 0.1},
    ]
    variables = ['entered']

    def on_init(self):
        self.entered = False

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        for vt_symbol in self.vt_symbols:
            bar = bars.get(vt_symbol)
            if bar and not self.get_pos(vt_symbol):
                self.buy(vt_symbol, bar.close_price, 1)
                self.entered = True
                self.write_log(f"买入看涨 {vt_symbol} @ {bar.close_price}")
                break


class StraddleStrategy(StrategyTemplate):
    """跨式组合：同时买入看涨和看跌期权"""

    parameters = [
        {'name': 'strike_offset', 'displayName': '行权价偏移', 'type': 'select', 'default': 0},
        {'name': 'expiry_days', 'displayName': '目标到期天数', 'type': 'number', 'default': 30},
        {'name': 'position_ratio', 'displayName': '仓位比例', 'type': 'number', 'default': 0.1},
    ]
    variables = ['entered']

    def on_init(self):
        self.entered = False

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        if len(self.vt_symbols) < 2:
            raise ValueError(f"StraddleStrategy 需要至少 2 个合约，当前仅 {len(self.vt_symbols)} 个")

        call_symbol = self.vt_symbols[0]
        put_symbol = self.vt_symbols[1]
        call_bar = bars.get(call_symbol)
        put_bar = bars.get(put_symbol)

        if call_bar and put_bar:
            self.buy(call_symbol, call_bar.close_price, 1)
            self.buy(put_symbol, put_bar.close_price, 1)
            self.entered = True
            self.write_log(f"买入跨式：{call_symbol} + {put_symbol}")


class IronCondorStrategy(StrategyTemplate):
    """铁鹰策略：卖出跨式同时买入宽跨式"""

    parameters = [
        {'name': 'short_strike_offset', 'displayName': '卖出行权价偏移', 'type': 'select', 'default': 1},
        {'name': 'long_strike_offset', 'displayName': '买入行权价偏移', 'type': 'select', 'default': 2},
        {'name': 'expiry_days', 'displayName': '目标到期天数', 'type': 'number', 'default': 30},
        {'name': 'position_ratio', 'displayName': '仓位比例', 'type': 'number', 'default': 0.1},
    ]
    variables = ['entered']

    def on_init(self):
        self.entered = False

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        if len(self.vt_symbols) < 4:
            raise ValueError(f"IronCondorStrategy 需要至少 4 个合约，当前仅 {len(self.vt_symbols)} 个")

        symbols = self.vt_symbols[:4]
        all_bars = [bars.get(s) for s in symbols]
        if all(all_bars):
            self.short(symbols[0], all_bars[0].close_price, 1)
            self.buy(symbols[1], all_bars[1].close_price, 1)
            self.short(symbols[2], all_bars[2].close_price, 1)
            self.buy(symbols[3], all_bars[3].close_price, 1)
            self.entered = True
            self.write_log("进入铁鹰策略")


class BullCallSpreadStrategy(StrategyTemplate):
    """牛市看涨价差：买入低行权价Call，卖出高行权价Call"""

    parameters = [
        {'name': 'long_strike_offset', 'displayName': '买入行权价偏移', 'type': 'number', 'default': -0.05},
        {'name': 'short_strike_offset', 'displayName': '卖出行权价偏移', 'type': 'number', 'default': 0.05},
        {'name': 'quantity', 'displayName': '手数', 'type': 'number', 'default': 1},
    ]
    variables = ['entered']

    def on_init(self):
        self.entered = False

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        qty = getattr(self, 'quantity', 1)

        if len(self.vt_symbols) < 2:
            raise ValueError(f"BullCallSpreadStrategy 需要至少 2 个合约，当前仅 {len(self.vt_symbols)} 个")

        long_sym = self.vt_symbols[0]
        short_sym = self.vt_symbols[1]
        long_bar = bars.get(long_sym)
        short_bar = bars.get(short_sym)

        if long_bar and short_bar:
            self.buy(long_sym, long_bar.close_price, qty)
            self.short(short_sym, short_bar.close_price, qty)
            self.entered = True
            self.write_log(f"牛市价差：买{long_sym} 卖{short_sym}")


class BearPutSpreadStrategy(StrategyTemplate):
    """熊市看跌价差：买入高行权价Put，卖出低行权价Put"""

    parameters = [
        {'name': 'long_strike_offset', 'displayName': '买入行权价偏移', 'type': 'number', 'default': 0.05},
        {'name': 'short_strike_offset', 'displayName': '卖出行权价偏移', 'type': 'number', 'default': -0.05},
        {'name': 'quantity', 'displayName': '手数', 'type': 'number', 'default': 1},
    ]
    variables = ['entered']

    def on_init(self):
        self.entered = False

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        qty = getattr(self, 'quantity', 1)

        if len(self.vt_symbols) < 2:
            raise ValueError(f"BearPutSpreadStrategy 需要至少 2 个合约，当前仅 {len(self.vt_symbols)} 个")

        long_sym = self.vt_symbols[0]
        short_sym = self.vt_symbols[1]
        long_bar = bars.get(long_sym)
        short_bar = bars.get(short_sym)

        if long_bar and short_bar:
            self.buy(long_sym, long_bar.close_price, qty)
            self.short(short_sym, short_bar.close_price, qty)
            self.entered = True
            self.write_log(f"熊市价差：买{long_sym} 卖{short_sym}")


class StrangleStrategy(StrategyTemplate):
    """宽跨式：买入虚值Call和虚值Put"""

    parameters = [
        {'name': 'call_strike_offset', 'displayName': 'Call行权价偏移', 'type': 'number', 'default': 0.05},
        {'name': 'put_strike_offset', 'displayName': 'Put行权价偏移', 'type': 'number', 'default': -0.05},
        {'name': 'quantity', 'displayName': '手数', 'type': 'number', 'default': 1},
        {'name': 'profit_target', 'displayName': '止盈比例', 'type': 'number', 'default': 0.5},
    ]
    variables = ['entered', 'entry_cost']

    def on_init(self):
        self.entered = False
        self.entry_cost = 0.0

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        qty = getattr(self, 'quantity', 1)

        if len(self.vt_symbols) < 2:
            raise ValueError(f"StrangleStrategy 需要至少 2 个合约，当前仅 {len(self.vt_symbols)} 个")

        call_sym = self.vt_symbols[0]
        put_sym = self.vt_symbols[1]
        call_bar = bars.get(call_sym)
        put_bar = bars.get(put_sym)

        if call_bar and put_bar:
            self.buy(call_sym, call_bar.close_price, qty)
            self.buy(put_sym, put_bar.close_price, qty)
            self.entry_cost = call_bar.close_price + put_bar.close_price
            self.entered = True
            self.write_log(f"买入宽跨式：{call_sym} + {put_sym}")


class ButterflySpreadStrategy(StrategyTemplate):
    """蝶式价差：买低+买高+卖2中"""

    parameters = [
        {'name': 'center_strike_offset', 'displayName': '中心行权价偏移', 'type': 'number', 'default': 0.0},
        {'name': 'wing_width', 'displayName': '翅膀宽度', 'type': 'number', 'default': 0.05},
        {'name': 'quantity', 'displayName': '手数', 'type': 'number', 'default': 1},
    ]
    variables = ['entered']

    def on_init(self):
        self.entered = False

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        qty = getattr(self, 'quantity', 1)

        if len(self.vt_symbols) < 3:
            raise ValueError(f"ButterflySpreadStrategy 需要至少 3 个合约，当前仅 {len(self.vt_symbols)} 个")

        low_sym = self.vt_symbols[0]
        center_sym = self.vt_symbols[1]
        high_sym = self.vt_symbols[2]
        b_low = bars.get(low_sym)
        b_center = bars.get(center_sym)
        b_high = bars.get(high_sym)

        if b_low and b_center and b_high:
            self.buy(low_sym, b_low.close_price, qty)
            self.short(center_sym, b_center.close_price, qty * 2)
            self.buy(high_sym, b_high.close_price, qty)
            self.entered = True
            self.write_log(f"蝶式价差：买{low_sym} 卖2x{center_sym} 买{high_sym}")


class CalendarSpreadStrategy(StrategyTemplate):
    """日历价差：卖出近月买入远月"""

    parameters = [
        {'name': 'strike_offset', 'displayName': '行权价偏移', 'type': 'number', 'default': 0.0},
        {'name': 'near_month', 'displayName': '近月序号', 'type': 'number', 'default': 0},
        {'name': 'far_month', 'displayName': '远月序号', 'type': 'number', 'default': 1},
        {'name': 'quantity', 'displayName': '手数', 'type': 'number', 'default': 1},
    ]
    variables = ['entered']

    def on_init(self):
        self.entered = False

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        qty = getattr(self, 'quantity', 1)

        if len(self.vt_symbols) < 2:
            raise ValueError(f"CalendarSpreadStrategy 需要至少 2 个合约，当前仅 {len(self.vt_symbols)} 个")

        near_sym = self.vt_symbols[0]
        far_sym = self.vt_symbols[1]
        near_bar = bars.get(near_sym)
        far_bar = bars.get(far_sym)

        if near_bar and far_bar:
            self.short(near_sym, near_bar.close_price, qty)
            self.buy(far_sym, far_bar.close_price, qty)
            self.entered = True
            self.write_log(f"日历价差：卖近月{near_sym} 买远月{far_sym}")


class RatioSpreadStrategy(StrategyTemplate):
    """比率价差：买入1个低行权价Call，卖出N个高行权价Call"""

    parameters = [
        {'name': 'long_strike_offset', 'displayName': '买入行权价偏移', 'type': 'number', 'default': 0.0},
        {'name': 'short_strike_offset', 'displayName': '卖出行权价偏移', 'type': 'number', 'default': 0.05},
        {'name': 'ratio', 'displayName': '比率', 'type': 'number', 'default': 2},
        {'name': 'quantity', 'displayName': '基础手数', 'type': 'number', 'default': 1},
    ]
    variables = ['entered']

    def on_init(self):
        self.entered = False

    def on_bars(self, bars):
        if not self.trading or self.entered:
            return

        qty = getattr(self, 'quantity', 1)
        ratio = getattr(self, 'ratio', 2)

        if len(self.vt_symbols) < 2:
            raise ValueError(f"RatioSpreadStrategy 需要至少 2 个合约，当前仅 {len(self.vt_symbols)} 个")

        long_sym = self.vt_symbols[0]
        short_sym = self.vt_symbols[1]
        long_bar = bars.get(long_sym)
        short_bar = bars.get(short_sym)

        if long_bar and short_bar:
            self.buy(long_sym, long_bar.close_price, qty)
            self.short(short_sym, short_bar.close_price, qty * ratio)
            self.entered = True
            self.write_log(f"比率价差：买{qty}手{long_sym} 卖{qty * ratio}手{short_sym}")


class SimpleBuyHoldStrategy(StrategyTemplate):
    """简单买入持有策略"""

    parameters = []
    variables = []

    def on_init(self):
        self.bought = False

    def on_bars(self, bars):
        if not self.trading:
            return

        if not self.bought and self.vt_symbols:
            symbol = self.vt_symbols[0]
            bar = bars.get(symbol)
            if bar:
                self.buy(symbol, bar.close_price, 1)
                self.bought = True
                self.write_log(f"买入 {symbol}")


class DualThrustStrategy(StrategyTemplate):
    """Dual Thrust 策略 — 从 vnpy_ctastrategy 迁移"""

    author = "用Python的交易员"

    fixed_size: int = 1
    k1: float = 0.4
    k2: float = 0.6

    parameters = [
        {'name': 'k1', 'displayName': '上轨系数', 'type': 'number', 'default': 0.4, 'min': 0.01, 'max': 2.0, 'step': 0.01},
        {'name': 'k2', 'displayName': '下轨系数', 'type': 'number', 'default': 0.6, 'min': 0.01, 'max': 2.0, 'step': 0.01},
        {'name': 'fixed_size', 'displayName': '交易数量', 'type': 'number', 'default': 1, 'min': 1, 'max': 100, 'step': 1},
    ]
    variables = ['day_range', 'long_entry', 'short_entry']

    def on_init(self):
        from datetime import time
        self.write_log("策略初始化")
        self.bars: list = []
        self.exit_time = time(hour=14, minute=55)

        self.day_open: float = 0.0
        self.day_high: float = 0.0
        self.day_low: float = 0.0
        self.day_range: float = 0.0
        self.long_entry: float = 0.0
        self.short_entry: float = 0.0
        self.long_entered: bool = False
        self.short_entered: bool = False

    def on_start(self):
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self):
        self.write_log("策略停止")
        self.put_event()

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return

        self.cancel_all()

        self.bars.append(bar)
        if len(self.bars) <= 2:
            return
        else:
            self.bars.pop(0)
        last_bar = self.bars[-2]

        # Detect new day
        if last_bar.datetime.date() != bar.datetime.date():
            if self.day_high:
                self.day_range = self.day_high - self.day_low
                self.long_entry = bar.open_price + self.k1 * self.day_range
                self.short_entry = bar.open_price - self.k2 * self.day_range

            self.day_open = bar.open_price
            self.day_high = bar.high_price
            self.day_low = bar.low_price

            self.long_entered = False
            self.short_entered = False
        else:
            self.day_high = max(self.day_high, bar.high_price)
            self.day_low = min(self.day_low, bar.low_price)

        if not self.day_range:
            return

        pos = self.get_pos(vt_symbol)

        # Exit before market close
        if bar.datetime.time() >= self.exit_time:
            if pos > 0:
                self.sell(vt_symbol, bar.close_price, abs(pos))
            elif pos < 0:
                self.cover(vt_symbol, bar.close_price, abs(pos))
            self.put_event()
            return

        # Intraday breakout logic with stop orders
        if pos == 0:
            if bar.close_price > self.day_open:
                if not self.long_entered:
                    self.buy(vt_symbol, self.long_entry, self.fixed_size, stop=True)
            else:
                if not self.short_entered:
                    self.short(vt_symbol, self.short_entry, self.fixed_size, stop=True)

        elif pos > 0:
            self.long_entered = True
            self.sell(vt_symbol, self.short_entry, self.fixed_size, stop=True)
            if not self.short_entered:
                self.short(vt_symbol, self.short_entry, self.fixed_size, stop=True)

        elif pos < 0:
            self.short_entered = True
            self.cover(vt_symbol, self.long_entry, self.fixed_size, stop=True)
            if not self.long_entered:
                self.buy(vt_symbol, self.long_entry, self.fixed_size, stop=True)

        self.put_event()

    def on_order(self, order):
        pass

    def on_trade(self, trade):
        self.put_event()


class PairTradingStrategy(StrategyTemplate):
    """配对交易策略：基于价差的布林带均值回归"""

    parameters = [
        {'name': 'boll_window', 'displayName': '布林窗口', 'type': 'number', 'default': 20, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'boll_dev', 'displayName': '布林倍差', 'type': 'number', 'default': 2.0, 'min': 0.5, 'max': 5.0, 'step': 0.1},
        {'name': 'fixed_size', 'displayName': '交易数量', 'type': 'number', 'default': 1, 'min': 1, 'max': 100, 'step': 1},
    ]
    variables = ['boll_up', 'boll_down', 'spread_value']

    def on_init(self):
        self.boll_up: float = 0.0
        self.boll_down: float = 0.0
        self.spread_value: float = 0.0
        self.spread_history: list[float] = []

    def on_bars(self, bars):
        if len(self.vt_symbols) < 2:
            raise ValueError(f"PairTradingStrategy 需要至少 2 个合约，当前仅 {len(self.vt_symbols)} 个")

        vt_symbol_x = self.vt_symbols[0]
        vt_symbol_y = self.vt_symbols[1]
        bar_x = bars.get(vt_symbol_x)
        bar_y = bars.get(vt_symbol_y)

        if not bar_x or not bar_y:
            return

        spread = bar_y.close_price - bar_x.close_price
        self.spread_history.append(spread)
        if len(self.spread_history) > self.boll_window:
            self.spread_history.pop(0)
        if len(self.spread_history) < self.boll_window:
            return

        import numpy as np
        arr = np.array(self.spread_history)
        ma = float(np.mean(arr))
        std = float(np.std(arr, ddof=1))

        self.spread_value = spread
        self.boll_up = ma + self.boll_dev * std
        self.boll_down = ma - self.boll_dev * std

        pos_x = self.get_pos(vt_symbol_x)
        pos_y = self.get_pos(vt_symbol_y)

        # 价差突破上轨 → 做空价差（卖 y 买 x）
        if spread >= self.boll_up:
            if pos_y >= 0:
                self.set_target(vt_symbol_y, -self.fixed_size)
            if pos_x <= 0:
                self.set_target(vt_symbol_x, self.fixed_size)
            self.rebalance_portfolio(bars)
            self.write_log(f"做空价差 {spread:.4f} ≥ {self.boll_up:.4f}")
        # 价差突破下轨 → 做多价差（买 y 卖 x）
        elif spread <= self.boll_down:
            if pos_y <= 0:
                self.set_target(vt_symbol_y, self.fixed_size)
            if pos_x >= 0:
                self.set_target(vt_symbol_x, -self.fixed_size)
            self.rebalance_portfolio(bars)
            self.write_log(f"做多价差 {spread:.4f} ≤ {self.boll_down:.4f}")
        # 回归中轨 → 平仓
        elif self.boll_down < spread < self.boll_up:
            if pos_x != 0 or pos_y != 0:
                self.set_target(vt_symbol_x, 0)
                self.set_target(vt_symbol_y, 0)
                self.rebalance_portfolio(bars)
                self.write_log(f"价差回归 {spread:.4f}，平仓")


def get_strategy_class(strategy_name: str):
    """根据策略名获取策略类"""
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
    from ccquant.strategy.iv_predict import (
        IvPredictStrategy,
        IvPredictStrategyA,
        IvPredictStrategyAEnhanced,
        IvPredictStrategyB,
        IvPredictStrategyC,
    )

    strategies = {
        'BuyCallStrategy': BuyCallStrategy,
        'StraddleStrategy': StraddleStrategy,
        'IronCondorStrategy': IronCondorStrategy,
        'BullCallSpreadStrategy': BullCallSpreadStrategy,
        'BearPutSpreadStrategy': BearPutSpreadStrategy,
        'StrangleStrategy': StrangleStrategy,
        'ButterflySpreadStrategy': ButterflySpreadStrategy,
        'CalendarSpreadStrategy': CalendarSpreadStrategy,
        'RatioSpreadStrategy': RatioSpreadStrategy,
        'SimpleBuyHoldStrategy': SimpleBuyHoldStrategy,
        'DualThrustStrategy': DualThrustStrategy,
        'PairTradingStrategy': PairTradingStrategy,
        'AtrRsiStrategy': AtrRsiStrategy,
        'BollChannelStrategy': BollChannelStrategy,
        'DoubleMaStrategy': DoubleMaStrategy,
        'KingKeltnerStrategy': KingKeltnerStrategy,
        'MultiSignalStrategy': MultiSignalStrategy,
        'MultiTimeframeStrategy': MultiTimeframeStrategy,
        'TestStrategy': TestStrategy,
        'TurtleSignalStrategy': TurtleSignalStrategy,
        'IvPredictStrategy': IvPredictStrategy,
        'IvPredictStrategyA': IvPredictStrategyA,
        'IvPredictStrategyAEnhanced': IvPredictStrategyAEnhanced,
        'IvPredictStrategyB': IvPredictStrategyB,
        'IvPredictStrategyC': IvPredictStrategyC,
    }
    return strategies.get(strategy_name, BuyCallStrategy)
