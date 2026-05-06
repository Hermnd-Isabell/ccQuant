"""vnpy CTA 策略迁移到 ccQuant（适配 on_bars 接口）"""

from ccquant.backtest.template import StrategyTemplate, TargetPosTemplate
from ccquant.core.object import BarData
from ccquant.core.utility import BarGenerator, ArrayManager


class AtrRsiStrategy(StrategyTemplate):
    """ATR-RSI策略"""

    author = "用Python的交易员"

    parameters = [
        {'name': 'atr_length', 'displayName': 'ATR周期', 'type': 'number', 'default': 22, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'atr_ma_length', 'displayName': 'ATR均线周期', 'type': 'number', 'default': 10, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'rsi_length', 'displayName': 'RSI周期', 'type': 'number', 'default': 5, 'min': 2, 'max': 50, 'step': 1},
        {'name': 'rsi_entry', 'displayName': 'RSI入场阈值', 'type': 'number', 'default': 16, 'min': 5, 'max': 50, 'step': 1},
        {'name': 'trailing_percent', 'displayName': '移动止损百分比', 'type': 'number', 'default': 0.8, 'min': 0.1, 'max': 5.0, 'step': 0.1},
        {'name': 'fixed_size', 'displayName': '交易数量', 'type': 'number', 'default': 1, 'min': 1, 'max': 100, 'step': 1},
    ]
    variables = [
        'atr_value', 'atr_ma', 'rsi_value', 'rsi_buy', 'rsi_sell',
        'intra_trade_high', 'intra_trade_low'
    ]

    def on_init(self):
        self.write_log("策略初始化")
        self.am = ArrayManager()
        self.rsi_buy = 50 + self.rsi_entry
        self.rsi_sell = 50 - self.rsi_entry
        self.atr_value = 0.0
        self.atr_ma = 0.0
        self.rsi_value = 0.0
        self.intra_trade_high = 0.0
        self.intra_trade_low = 0.0

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return

        self.cancel_all()
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        import numpy as np
        atr_array = np.array(self.am.atr(self.atr_length, array=True) or [0.0])
        self.atr_value = float(atr_array[-1])
        self.atr_ma = float(atr_array[-self.atr_ma_length:].mean()) if len(atr_array) >= self.atr_ma_length else self.atr_value
        self.rsi_value = self.am.rsi(self.rsi_length)

        pos = self.get_pos(vt_symbol)

        if pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            if self.atr_value > self.atr_ma:
                if self.rsi_value > self.rsi_buy:
                    self.buy(vt_symbol, bar.close_price + 5, self.fixed_size)
                elif self.rsi_value < self.rsi_sell:
                    self.short(vt_symbol, bar.close_price - 5, self.fixed_size)

        elif pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price
            long_stop = self.intra_trade_high * (1 - self.trailing_percent / 100)
            self.sell(vt_symbol, long_stop, abs(pos))

        elif pos < 0:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            self.intra_trade_high = bar.high_price
            short_stop = self.intra_trade_low * (1 + self.trailing_percent / 100)
            self.cover(vt_symbol, short_stop, abs(pos))

        self.put_event()

    def on_order(self, order):
        pass

    def on_trade(self, trade):
        self.put_event()


class BollChannelStrategy(StrategyTemplate):
    """布林通道策略"""

    author = "用Python的交易员"

    parameters = [
        {'name': 'boll_window', 'displayName': '布林周期', 'type': 'number', 'default': 18, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'boll_dev', 'displayName': '布林标准差倍数', 'type': 'number', 'default': 3.4, 'min': 0.5, 'max': 10.0, 'step': 0.1},
        {'name': 'cci_window', 'displayName': 'CCI周期', 'type': 'number', 'default': 10, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'atr_window', 'displayName': 'ATR周期', 'type': 'number', 'default': 30, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'sl_multiplier', 'displayName': '止损ATR倍数', 'type': 'number', 'default': 5.2, 'min': 0.5, 'max': 20.0, 'step': 0.1},
        {'name': 'fixed_size', 'displayName': '交易数量', 'type': 'number', 'default': 1, 'min': 1, 'max': 100, 'step': 1},
    ]
    variables = [
        'boll_up', 'boll_down', 'cci_value', 'atr_value',
        'intra_trade_high', 'intra_trade_low', 'long_stop', 'short_stop'
    ]

    def on_init(self):
        self.write_log("策略初始化")
        self.bg = BarGenerator(self._on_bar, 15, self.on_15min_bar)
        self.am = ArrayManager()
        self.boll_up = 0.0
        self.boll_down = 0.0
        self.cci_value = 0.0
        self.atr_value = 0.0
        self.intra_trade_high = 0.0
        self.intra_trade_low = 0.0
        self.long_stop = 0.0
        self.short_stop = 0.0

    def _on_bar(self, bar):
        """1分钟bar回调占位"""
        pass

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return
        self.bg.update_bar(bar)

    def on_15min_bar(self, bar):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        self.cancel_all()

        self.am.update_bar(bar)
        if not self.am.inited:
            return

        self.boll_up, self.boll_down = self.am.boll(self.boll_window, self.boll_dev)
        self.cci_value = self.am.cci(self.cci_window)
        self.atr_value = self.am.atr(self.atr_window)

        pos = self.get_pos(vt_symbol)

        if pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            if self.cci_value > 0:
                self.buy(vt_symbol, self.boll_up, self.fixed_size)
            elif self.cci_value < 0:
                self.short(vt_symbol, self.boll_down, self.fixed_size)

        elif pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price
            self.long_stop = self.intra_trade_high - self.atr_value * self.sl_multiplier
            self.sell(vt_symbol, self.long_stop, abs(pos))

        elif pos < 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            self.short_stop = self.intra_trade_low + self.atr_value * self.sl_multiplier
            self.cover(vt_symbol, self.short_stop, abs(pos))

        self.put_event()

    def on_order(self, order):
        pass

    def on_trade(self, trade):
        self.put_event()


class DoubleMaStrategy(StrategyTemplate):
    """双均线策略"""

    author = "用Python的交易员"

    parameters = [
        {'name': 'fast_window', 'displayName': '快线周期', 'type': 'number', 'default': 10, 'min': 2, 'max': 100, 'step': 1},
        {'name': 'slow_window', 'displayName': '慢线周期', 'type': 'number', 'default': 20, 'min': 5, 'max': 200, 'step': 1},
    ]
    variables = ['fast_ma0', 'fast_ma1', 'slow_ma0', 'slow_ma1']

    def on_init(self):
        self.write_log("策略初始化")
        self.am = ArrayManager()
        self.fast_ma0 = 0.0
        self.fast_ma1 = 0.0
        self.slow_ma0 = 0.0
        self.slow_ma1 = 0.0

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return

        self.cancel_all()
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        import numpy as np
        fast_ma = np.array(self.am.sma(self.fast_window, array=True) or [0.0])
        self.fast_ma0 = float(fast_ma[-1])
        self.fast_ma1 = float(fast_ma[-2]) if len(fast_ma) > 1 else self.fast_ma0

        slow_ma = np.array(self.am.sma(self.slow_window, array=True) or [0.0])
        self.slow_ma0 = float(slow_ma[-1])
        self.slow_ma1 = float(slow_ma[-2]) if len(slow_ma) > 1 else self.slow_ma0

        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 < self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 > self.slow_ma1

        pos = self.get_pos(vt_symbol)

        if cross_over:
            if pos == 0:
                self.buy(vt_symbol, bar.close_price, 1)
            elif pos < 0:
                self.cover(vt_symbol, bar.close_price, 1)
                self.buy(vt_symbol, bar.close_price, 1)

        elif cross_below:
            if pos == 0:
                self.short(vt_symbol, bar.close_price, 1)
            elif pos > 0:
                self.sell(vt_symbol, bar.close_price, 1)
                self.short(vt_symbol, bar.close_price, 1)

        self.put_event()

    def on_order(self, order):
        pass

    def on_trade(self, trade):
        self.put_event()


class KingKeltnerStrategy(StrategyTemplate):
    """金肯特纳策略"""

    author = "用Python的交易员"

    parameters = [
        {'name': 'kk_length', 'displayName': 'KK周期', 'type': 'number', 'default': 11, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'kk_dev', 'displayName': 'KK标准差倍数', 'type': 'number', 'default': 1.6, 'min': 0.1, 'max': 10.0, 'step': 0.1},
        {'name': 'trailing_percent', 'displayName': '移动止损百分比', 'type': 'number', 'default': 0.8, 'min': 0.1, 'max': 5.0, 'step': 0.1},
        {'name': 'fixed_size', 'displayName': '交易数量', 'type': 'number', 'default': 1, 'min': 1, 'max': 100, 'step': 1},
    ]
    variables = ['kk_up', 'kk_down', 'intra_trade_high', 'intra_trade_low']

    def on_init(self):
        self.write_log("策略初始化")
        self.bg = BarGenerator(self._on_bar, 5, self.on_5min_bar)
        self.am = ArrayManager()
        self.kk_up = 0.0
        self.kk_down = 0.0
        self.intra_trade_high = 0.0
        self.intra_trade_low = 0.0
        self.long_vt_orderids = []
        self.short_vt_orderids = []
        self.vt_orderids = []

    def _on_bar(self, bar):
        pass

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return
        self.bg.update_bar(bar)

    def on_5min_bar(self, bar):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]

        for orderid in self.vt_orderids:
            self.cancel_order(orderid)
        self.vt_orderids.clear()

        self.am.update_bar(bar)
        if not self.am.inited:
            return

        self.kk_up, self.kk_down = self.am.keltner(self.kk_length, self.kk_dev)
        pos = self.get_pos(vt_symbol)

        if pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price
            self.send_oco_order(vt_symbol, self.kk_up, self.kk_down, self.fixed_size)

        elif pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price
            sell_orderids = self.sell(
                vt_symbol,
                self.intra_trade_high * (1 - self.trailing_percent / 100),
                abs(pos),
            )
            self.vt_orderids.extend(sell_orderids)

        elif pos < 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            cover_orderids = self.cover(
                vt_symbol,
                self.intra_trade_low * (1 + self.trailing_percent / 100),
                abs(pos),
            )
            self.vt_orderids.extend(cover_orderids)

        self.put_event()

    def send_oco_order(self, vt_symbol, buy_price, short_price, volume):
        self.long_vt_orderids = self.buy(vt_symbol, buy_price, volume)
        self.short_vt_orderids = self.short(vt_symbol, short_price, volume)
        self.vt_orderids.extend(self.long_vt_orderids)
        self.vt_orderids.extend(self.short_vt_orderids)

    def on_order(self, order):
        pass

    def on_trade(self, trade):
        if self.get_pos(trade.vt_symbol) != 0:
            # 成交后撤销OCO反向单
            pos = self.get_pos(trade.vt_symbol)
            if pos > 0:
                for short_orderid in self.short_vt_orderids:
                    self.cancel_order(short_orderid)
            elif pos < 0:
                for buy_orderid in self.long_vt_orderids:
                    self.cancel_order(buy_orderid)
            for orderid in (self.long_vt_orderids + self.short_vt_orderids):
                if orderid in self.vt_orderids:
                    self.vt_orderids.remove(orderid)
        self.put_event()


class _RsiSignal:
    def __init__(self, rsi_window, rsi_level):
        self.rsi_window = rsi_window
        self.rsi_level = rsi_level
        self.rsi_long = 50 + rsi_level
        self.rsi_short = 50 - rsi_level
        self.am = ArrayManager()
        self.signal_pos = 0

    def on_bar(self, bar):
        self.am.update_bar(bar)
        if not self.am.inited:
            self.signal_pos = 0
            return
        rsi_value = self.am.rsi(self.rsi_window)
        if rsi_value >= self.rsi_long:
            self.signal_pos = 1
        elif rsi_value <= self.rsi_short:
            self.signal_pos = -1
        else:
            self.signal_pos = 0

    def get_signal_pos(self):
        return self.signal_pos


class _CciSignal:
    def __init__(self, cci_window, cci_level):
        self.cci_window = cci_window
        self.cci_level = cci_level
        self.cci_long = cci_level
        self.cci_short = -cci_level
        self.am = ArrayManager()
        self.signal_pos = 0

    def on_bar(self, bar):
        self.am.update_bar(bar)
        if not self.am.inited:
            self.signal_pos = 0
            return
        cci_value = self.am.cci(self.cci_window)
        if cci_value >= self.cci_long:
            self.signal_pos = 1
        elif cci_value <= self.cci_short:
            self.signal_pos = -1
        else:
            self.signal_pos = 0

    def get_signal_pos(self):
        return self.signal_pos


class _MaSignal:
    def __init__(self, fast_window, slow_window):
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.bg = BarGenerator(self._on_bar, 5, self.on_5min_bar)
        self.am = ArrayManager()
        self.signal_pos = 0

    def _on_bar(self, bar):
        pass

    def on_bar(self, bar):
        self.bg.update_bar(bar)

    def on_5min_bar(self, bar):
        self.am.update_bar(bar)
        if not self.am.inited:
            self.signal_pos = 0
            return
        fast_ma = self.am.sma(self.fast_window)
        slow_ma = self.am.sma(self.slow_window)
        if fast_ma > slow_ma:
            self.signal_pos = 1
        elif fast_ma < slow_ma:
            self.signal_pos = -1
        else:
            self.signal_pos = 0

    def get_signal_pos(self):
        return self.signal_pos


class MultiSignalStrategy(TargetPosTemplate):
    """多信号组合策略"""

    author = "用Python的交易员"

    parameters = [
        {'name': 'rsi_window', 'displayName': 'RSI周期', 'type': 'number', 'default': 14, 'min': 2, 'max': 100, 'step': 1},
        {'name': 'rsi_level', 'displayName': 'RSI阈值', 'type': 'number', 'default': 20, 'min': 5, 'max': 50, 'step': 1},
        {'name': 'cci_window', 'displayName': 'CCI周期', 'type': 'number', 'default': 30, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'cci_level', 'displayName': 'CCI阈值', 'type': 'number', 'default': 10, 'min': 5, 'max': 50, 'step': 1},
        {'name': 'fast_window', 'displayName': '快线周期', 'type': 'number', 'default': 5, 'min': 2, 'max': 100, 'step': 1},
        {'name': 'slow_window', 'displayName': '慢线周期', 'type': 'number', 'default': 20, 'min': 5, 'max': 200, 'step': 1},
    ]
    variables = ['signal_pos']

    def on_init(self):
        self.write_log("策略初始化")
        self.rsi_signal = _RsiSignal(self.rsi_window, self.rsi_level)
        self.cci_signal = _CciSignal(self.cci_window, self.cci_level)
        self.ma_signal = _MaSignal(self.fast_window, self.slow_window)
        self.signal_pos = {"rsi": 0, "cci": 0, "ma": 0}

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return

        # Update last_bar for TargetPosTemplate
        super().on_bars(bars)

        self.rsi_signal.on_bar(bar)
        self.cci_signal.on_bar(bar)
        self.ma_signal.on_bar(bar)

        self.calculate_target_pos()

    def calculate_target_pos(self):
        self.signal_pos["rsi"] = self.rsi_signal.get_signal_pos()
        self.signal_pos["cci"] = self.cci_signal.get_signal_pos()
        self.signal_pos["ma"] = self.ma_signal.get_signal_pos()

        target_pos = sum(self.signal_pos.values())
        self.set_target_pos(target_pos)

    def on_trade(self, trade):
        self.put_event()

    def on_order(self, order):
        pass

    def on_trade(self, trade):
        self.put_event()


class MultiTimeframeStrategy(StrategyTemplate):
    """多周期策略"""

    author = "用Python的交易员"

    parameters = [
        {'name': 'rsi_signal', 'displayName': 'RSI信号阈值', 'type': 'number', 'default': 20, 'min': 5, 'max': 50, 'step': 1},
        {'name': 'rsi_window', 'displayName': 'RSI周期', 'type': 'number', 'default': 14, 'min': 2, 'max': 100, 'step': 1},
        {'name': 'fast_window', 'displayName': '快线周期', 'type': 'number', 'default': 5, 'min': 2, 'max': 100, 'step': 1},
        {'name': 'slow_window', 'displayName': '慢线周期', 'type': 'number', 'default': 20, 'min': 5, 'max': 200, 'step': 1},
        {'name': 'fixed_size', 'displayName': '交易数量', 'type': 'number', 'default': 1, 'min': 1, 'max': 100, 'step': 1},
    ]
    variables = [
        'rsi_value', 'rsi_long', 'rsi_short',
        'fast_ma', 'slow_ma', 'ma_trend'
    ]

    def on_init(self):
        self.write_log("策略初始化")
        self.rsi_long = 50 + self.rsi_signal
        self.rsi_short = 50 - self.rsi_signal
        self.bg5 = BarGenerator(self._on_bar, 5, self.on_5min_bar)
        self.am5 = ArrayManager()
        self.bg15 = BarGenerator(self._on_bar, 15, self.on_15min_bar)
        self.am15 = ArrayManager()
        self.rsi_value = 0.0
        self.fast_ma = 0.0
        self.slow_ma = 0.0
        self.ma_trend = 0

    def _on_bar(self, bar):
        pass

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return
        self.bg5.update_bar(bar)
        self.bg15.update_bar(bar)

    def on_5min_bar(self, bar):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        self.cancel_all()

        self.am5.update_bar(bar)
        if not self.am5.inited:
            return

        if not self.ma_trend:
            return

        self.rsi_value = self.am5.rsi(self.rsi_window)
        pos = self.get_pos(vt_symbol)

        if pos == 0:
            if self.ma_trend > 0 and self.rsi_value >= self.rsi_long:
                self.buy(vt_symbol, bar.close_price + 5, self.fixed_size)
            elif self.ma_trend < 0 and self.rsi_value <= self.rsi_short:
                self.short(vt_symbol, bar.close_price - 5, self.fixed_size)

        elif pos > 0:
            if self.ma_trend < 0 or self.rsi_value < 50:
                self.sell(vt_symbol, bar.close_price - 5, abs(pos))

        elif pos < 0:
            if self.ma_trend > 0 or self.rsi_value > 50:
                self.cover(vt_symbol, bar.close_price + 5, abs(pos))

        self.put_event()

    def on_15min_bar(self, bar):
        self.am15.update_bar(bar)
        if not self.am15.inited:
            return

        self.fast_ma = self.am15.sma(self.fast_window)
        self.slow_ma = self.am15.sma(self.slow_window)

        if self.fast_ma > self.slow_ma:
            self.ma_trend = 1
        else:
            self.ma_trend = -1

    def on_order(self, order):
        pass

    def on_trade(self, trade):
        self.put_event()


class TestStrategy(StrategyTemplate):
    """测试策略"""

    author = "用Python的交易员"

    parameters = [
        {'name': 'test_trigger', 'displayName': '触发计数', 'type': 'number', 'default': 10, 'min': 1, 'max': 100, 'step': 1},
    ]
    variables = ['tick_count', 'test_all_done']

    def on_init(self):
        self.write_log("策略初始化")
        self.test_funcs = [
            self.test_market_order,
            self.test_limit_order,
            self.test_cancel_all,
            self.test_stop_order,
        ]
        self.tick_count = 0
        self.test_all_done = False
        self.last_bar = None

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return

        if self.test_all_done:
            return

        self.last_bar = bar
        self.tick_count += 1

        if self.tick_count >= self.test_trigger:
            self.tick_count = 0
            if self.test_funcs:
                test_func = self.test_funcs.pop(0)
                test_func(vt_symbol)
            else:
                self.write_log("测试已全部完成")
                self.test_all_done = True

        self.put_event()

    def on_order(self, order):
        self.put_event()

    def on_trade(self, trade):
        self.put_event()

    def test_market_order(self, vt_symbol):
        if not self.last_bar:
            self.write_log("没有最新bar数据")
            return
        self.buy(vt_symbol, self.last_bar.close_price, 1)
        self.write_log("执行市价单测试")

    def test_limit_order(self, vt_symbol):
        if not self.last_bar:
            self.write_log("没有最新bar数据")
            return
        self.buy(vt_symbol, self.last_bar.close_price * 0.99, 1)
        self.write_log("执行限价单测试")

    def test_stop_order(self, vt_symbol):
        if not self.last_bar:
            self.write_log("没有最新bar数据")
            return
        self.buy(vt_symbol, self.last_bar.close_price * 1.01, 1)
        self.write_log("执行停止单测试")

    def test_cancel_all(self):
        self.cancel_all()
        self.write_log("执行全部撤单测试")


class TurtleSignalStrategy(StrategyTemplate):
    """海龟信号策略"""

    author = "用Python的交易员"

    parameters = [
        {'name': 'entry_window', 'displayName': '入场窗口', 'type': 'number', 'default': 20, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'exit_window', 'displayName': '出场窗口', 'type': 'number', 'default': 10, 'min': 2, 'max': 100, 'step': 1},
        {'name': 'atr_window', 'displayName': 'ATR周期', 'type': 'number', 'default': 20, 'min': 5, 'max': 100, 'step': 1},
        {'name': 'fixed_size', 'displayName': '交易数量', 'type': 'number', 'default': 1, 'min': 1, 'max': 100, 'step': 1},
    ]
    variables = [
        'entry_up', 'entry_down', 'exit_up', 'exit_down', 'atr_value',
        'long_entry', 'short_entry', 'long_stop', 'short_stop'
    ]

    def on_init(self):
        self.write_log("策略初始化")
        self.am = ArrayManager()
        self.entry_up = 0.0
        self.entry_down = 0.0
        self.exit_up = 0.0
        self.exit_down = 0.0
        self.atr_value = 0.0
        self.long_entry = 0.0
        self.short_entry = 0.0
        self.long_stop = 0.0
        self.short_stop = 0.0

    def on_bars(self, bars):
        if not self.vt_symbols:
            return
        vt_symbol = self.vt_symbols[0]
        bar = bars.get(vt_symbol)
        if not bar:
            return

        self.cancel_all()
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        pos = self.get_pos(vt_symbol)

        if not pos:
            self.entry_up, self.entry_down = self.am.donchian(self.entry_window)

        self.exit_up, self.exit_down = self.am.donchian(self.exit_window)

        if not pos:
            self.atr_value = self.am.atr(self.atr_window)
            self.long_entry = 0.0
            self.short_entry = 0.0
            self.long_stop = 0.0
            self.short_stop = 0.0
            self.send_buy_orders(vt_symbol, self.entry_up)
            self.send_short_orders(vt_symbol, self.entry_down)

        elif pos > 0:
            self.send_buy_orders(vt_symbol, self.entry_up)
            sell_price = max(self.long_stop, self.exit_down)
            self.sell(vt_symbol, sell_price, abs(pos))

        elif pos < 0:
            self.send_short_orders(vt_symbol, self.entry_down)
            cover_price = min(self.short_stop, self.exit_up)
            self.cover(vt_symbol, cover_price, abs(pos))

        self.put_event()

    def on_trade(self, trade):
        if trade.direction.value == "多":  # LONG in ccQuant Chinese
            self.long_entry = trade.price
            self.long_stop = self.long_entry - 2 * self.atr_value
        else:
            self.short_entry = trade.price
            self.short_stop = self.short_entry + 2 * self.atr_value

    def on_order(self, order):
        pass

    def send_buy_orders(self, vt_symbol, price):
        t = self.get_pos(vt_symbol) / self.fixed_size
        if t < 1:
            self.buy(vt_symbol, price, self.fixed_size)
        if t < 2:
            self.buy(vt_symbol, price + self.atr_value * 0.5, self.fixed_size)
        if t < 3:
            self.buy(vt_symbol, price + self.atr_value, self.fixed_size)
        if t < 4:
            self.buy(vt_symbol, price + self.atr_value * 1.5, self.fixed_size)

    def send_short_orders(self, vt_symbol, price):
        t = self.get_pos(vt_symbol) / self.fixed_size
        if t > -1:
            self.short(vt_symbol, price, self.fixed_size)
        if t > -2:
            self.short(vt_symbol, price - self.atr_value * 0.5, self.fixed_size)
        if t > -3:
            self.short(vt_symbol, price - self.atr_value, self.fixed_size)
        if t > -4:
            self.short(vt_symbol, price - self.atr_value * 1.5, self.fixed_size)
