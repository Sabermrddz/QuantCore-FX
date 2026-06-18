from typing import Dict, List, Optional, Tuple
from collections import deque
import statistics
import math
import config


class TechnicalAnalyzer:
    def __init__(self, lookback: int = None, timeframe: str = None):
        self.current_timeframe = timeframe or config.DEFAULT_TIMEFRAME
        tf_config = config.TIMEFRAMES.get(self.current_timeframe, config.TIMEFRAMES["M15"])
        if lookback is None:
            lookback = tf_config["bars"]
        self.bar_lookback = lookback
        self.tick_lookback = 20
        self.atr_period = config.SL_ATR_PERIOD

        self.bar_history: Dict[str, deque] = {}
        self.ohlc_history: Dict[str, deque] = {}
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.z_scores: Dict[str, float] = {}
        self.extremes: Dict[str, bool] = {}

        for base in config.CURRENCIES:
            for quote in config.CURRENCIES:
                if base != quote:
                    pair = f"{base}_{quote}"
                    self.bar_history[pair] = deque(maxlen=self.bar_lookback)
                    self.ohlc_history[pair] = deque(maxlen=self.bar_lookback)
                    self.price_history[pair] = deque(maxlen=self.tick_lookback)
                    self.volume_history[pair] = deque(maxlen=self.tick_lookback)
                    self.z_scores[pair] = 0.0
                    self.extremes[pair] = False

    def set_timeframe(self, tf_key: str):
        tf_config = config.TIMEFRAMES.get(tf_key)
        if not tf_config:
            return
        self.current_timeframe = tf_key
        new_lookback = tf_config["bars"]
        if new_lookback != self.bar_lookback:
            self.bar_lookback = new_lookback
            for pair in self.bar_history:
                self.bar_history[pair] = deque(
                    list(self.bar_history[pair])[-new_lookback:],
                    maxlen=new_lookback,
                )
                self.ohlc_history[pair] = deque(
                    list(self.ohlc_history[pair])[-new_lookback:],
                    maxlen=new_lookback,
                )

    def add_bar(self, currency_pair: str, close: float, high: float = None,
                low: float = None, volume: int = 0):
        if currency_pair not in self.bar_history:
            return
        self.bar_history[currency_pair].append(close)
        if high is not None and low is not None:
            self.ohlc_history[currency_pair].append((close, high, low))

    def add_price_data(self, currency_pair: str, close_price: float,
                       volume: float = 0):
        if currency_pair not in self.price_history:
            return
        self.price_history[currency_pair].append(close_price)
        if volume > 0:
            self.volume_history[currency_pair].append(volume)
        self._update_z_score(currency_pair)

    def _get_mean_std(self, currency_pair: str) -> Tuple[float, float]:
        bars = list(self.bar_history[currency_pair])
        if len(bars) >= 2:
            try:
                return (statistics.mean(bars), statistics.stdev(bars))
            except (ValueError, statistics.StatisticsError):
                pass
        ticks = list(self.price_history[currency_pair])
        if len(ticks) >= 2:
            try:
                return (statistics.mean(ticks), statistics.stdev(ticks))
            except (ValueError, statistics.StatisticsError):
                pass
        return (0.0, 0.0)

    def _update_z_score(self, currency_pair: str):
        prices = list(self.price_history[currency_pair])
        if len(prices) < 1:
            self.z_scores[currency_pair] = 0.0
            self.extremes[currency_pair] = False
            return
        mu, sigma = self._get_mean_std(currency_pair)
        if sigma == 0.0:
            self.z_scores[currency_pair] = 0.0
            self.extremes[currency_pair] = False
            return
        current_price = prices[-1]
        z_score = (current_price - mu) / sigma
        self.z_scores[currency_pair] = z_score
        self.extremes[currency_pair] = abs(z_score) >= config.SCALP_Z_SCORE_THRESHOLD

    def get_z_score(self, currency_pair: str) -> float:
        return self.z_scores.get(currency_pair, 0.0)

    def is_extreme(self, currency_pair: str) -> bool:
        return self.extremes.get(currency_pair, False)

    def get_overbought_pairs(self) -> List[str]:
        return [pair for pair, z in self.z_scores.items() if z >= config.SCALP_Z_SCORE_THRESHOLD]

    def get_oversold_pairs(self) -> List[str]:
        return [pair for pair, z in self.z_scores.items() if z <= -config.SCALP_Z_SCORE_THRESHOLD]

    def get_volatility(self, currency_pair: str) -> float:
        bars = list(self.bar_history[currency_pair])
        if len(bars) >= 2:
            try:
                return statistics.stdev(bars)
            except (ValueError, statistics.StatisticsError):
                pass
        ticks = list(self.price_history[currency_pair])
        if len(ticks) >= 2:
            try:
                return statistics.stdev(ticks)
            except (ValueError, statistics.StatisticsError):
                pass
        return 0.0

    def get_mean_price(self, currency_pair: str) -> float:
        bars = list(self.bar_history[currency_pair])
        if len(bars) >= 1:
            return statistics.mean(bars)
        ticks = list(self.price_history[currency_pair])
        if len(ticks) >= 1:
            return statistics.mean(ticks)
        return 0.0

    def is_mean_reverting(self, currency_pair: str, threshold: float = 0.5) -> bool:
        z = self.get_z_score(currency_pair)
        return abs(z) < threshold

    def get_last_price(self, currency_pair: str) -> Optional[float]:
        prices = self.price_history.get(currency_pair)
        if prices and len(prices) > 0:
            return prices[-1]
        return None

    def get_all_z_scores(self) -> Dict[str, float]:
        return self.z_scores.copy()

    def get_status_for_pair(self, currency_pair: str) -> Dict:
        z_score = self.get_z_score(currency_pair)
        volatility = self.get_volatility(currency_pair)
        mean_price = self.get_mean_price(currency_pair)
        is_extreme = self.is_extreme(currency_pair)

        if z_score > 2.5:
            status = "SEVERELY OVERBOUGHT"
        elif z_score > 2.0:
            status = "OVERBOUGHT"
        elif z_score > 0.5:
            status = "Moderately Overbought"
        elif z_score < -2.5:
            status = "SEVERELY OVERSOLD"
        elif z_score < -2.0:
            status = "OVERSOLD"
        elif z_score < -0.5:
            status = "Moderately Oversold"
        else:
            status = "Neutral"

        return {
            'pair': currency_pair,
            'z_score': z_score,
            'volatility': volatility,
            'mean_price': mean_price,
            'is_extreme': is_extreme,
            'status': status,
        }

    def seed_bars(self, historical_bars: Dict[str, List[float]]):
        for pair, closes in historical_bars.items():
            if pair not in self.bar_history:
                continue
            self.bar_history[pair].clear()
            for c in closes[-self.bar_lookback:]:
                self.bar_history[pair].append(c)
            if len(self.bar_history[pair]) >= 2:
                mu, sigma = self._get_mean_std(pair)
                ticks = list(self.price_history[pair])
                if ticks and sigma > 0:
                    z = (ticks[-1] - mu) / sigma
                    self.z_scores[pair] = z
                    self.extremes[pair] = abs(z) >= config.SCALP_Z_SCORE_THRESHOLD

    def seed_ohlc(self, ohlc_data: Dict[str, List[Dict]]):
        """Seed both bar_history and ohlc_history from full candle data.
        Each dict in the list must have 'close', 'high', 'low' keys.
        """
        for pair, candles in ohlc_data.items():
            if pair not in self.bar_history:
                continue
            self.bar_history[pair].clear()
            self.ohlc_history[pair].clear()
            n_bars = min(len(candles), self.bar_lookback)
            for i in range(-n_bars, 0):
                c = candles[i]
                self.bar_history[pair].append(c["close"])
                self.ohlc_history[pair].append((c["close"], c["high"], c["low"]))
            if len(self.bar_history[pair]) >= 2:
                mu, sigma = self._get_mean_std(pair)
                ticks = list(self.price_history[pair])
                if ticks and sigma > 0:
                    z = (ticks[-1] - mu) / sigma
                    self.z_scores[pair] = z
                    self.extremes[pair] = abs(z) >= config.SCALP_Z_SCORE_THRESHOLD

    def clear_history(self):
        for pair in self.bar_history:
            self.bar_history[pair].clear()
            self.ohlc_history[pair].clear()
            self.price_history[pair].clear()
            self.volume_history[pair].clear()
            self.z_scores[pair] = 0.0
            self.extremes[pair] = False

    # ------------------------------------------------------------------
    # ATR + SL/TP
    # ------------------------------------------------------------------
    def calculate_atr(self, pair: str, period: int = None) -> Optional[float]:
        if period is None:
            period = self.atr_period
        ohlc = list(self.ohlc_history.get(pair, []))
        if len(ohlc) < period + 1:
            return None
        tr_values = []
        for i in range(1, len(ohlc)):
            _, h, l = ohlc[i]
            _, prev_c, _ = ohlc[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_values.append(tr)
        if len(tr_values) < period:
            return None
        atr = sum(tr_values[-period:]) / period
        return atr

    def calculate_sl_tp(
        self, pair: str, direction: str, entry_price: float
    ) -> Dict[str, float]:
        atr = self.calculate_atr(pair)
        result = {"entry": entry_price, "sl": None, "tp": None, "atr": atr}

        sl_mult = config.SL_ATR_MULTIPLIER
        rr = config.TRADE_RR_RATIO

        if atr is not None and atr > 0:
            sl_distance = atr * sl_mult
            tp_distance = sl_distance * rr
            if direction == "LONG":
                result["sl"] = entry_price - sl_distance
                result["tp"] = entry_price + tp_distance
            else:
                result["sl"] = entry_price + sl_distance
                result["tp"] = entry_price - tp_distance
        return result


class TechnicalSignal:
    def __init__(self, analyzer: TechnicalAnalyzer):
        self.analyzer = analyzer

    def should_enter_on_extreme(self, currency_pair: str) -> bool:
        return self.analyzer.is_extreme(currency_pair)

    def should_exit_on_mean_reversion(self, currency_pair: str) -> bool:
        return self.analyzer.is_mean_reverting(currency_pair, threshold=0.5)

    def get_signal_strength(self, currency_pair: str) -> float:
        z = self.analyzer.get_z_score(currency_pair)
        return min(abs(z) / 3.0 * 100, 100.0)
