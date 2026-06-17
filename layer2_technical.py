from typing import Dict, List, Optional, Tuple
from collections import deque
import statistics
import config


class TechnicalAnalyzer:
    """Real-time technical analysis with bar-anchored statistics (Task 1.1).

    Maintains two data streams:
    1. Bar history (M1/M5 candles) — the multi-hour statistical anchor
       for μ and σ (config.BAR_LOOKBACK_BARS, default 288 M5 bars = 24h).
    2. Live tick/poll deques — fast recent movement for display.

    Z-score formula (priority):
       If bar history has >= 2 bars:  Z = (tick - μ_bars) / σ_bars
       Otherwise (fallback):           Z = (tick - μ_ticks) / σ_ticks

    μ and σ prefer the multi-hour bar frame, but fall back to tick-based
    statistics when bars haven't been seeded yet.
    """

    def __init__(self, lookback: int = None):
        if lookback is None:
            lookback = config.BAR_LOOKBACK_BARS
        self.bar_lookback = lookback
        self.tick_lookback = 20

        self.bar_history: Dict[str, deque] = {}
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.z_scores: Dict[str, float] = {}
        self.extremes: Dict[str, bool] = {}

        for base in config.CURRENCIES:
            for quote in config.CURRENCIES:
                if base != quote:
                    pair = f"{base}_{quote}"
                    self.bar_history[pair] = deque(maxlen=self.bar_lookback)
                    self.price_history[pair] = deque(maxlen=self.tick_lookback)
                    self.volume_history[pair] = deque(maxlen=self.tick_lookback)
                    self.z_scores[pair] = 0.0
                    self.extremes[pair] = False

    def add_bar(self, currency_pair: str, close: float, high: float = None,
                low: float = None, volume: int = 0):
        """Add a completed M1/M5 bar to the multi-hour historical frame."""
        if currency_pair not in self.bar_history:
            return
        self.bar_history[currency_pair].append(close)

    def add_price_data(self, currency_pair: str, close_price: float,
                       volume: float = 0):
        """Add tick/poll price."""
        if currency_pair not in self.price_history:
            return

        self.price_history[currency_pair].append(close_price)
        if volume > 0:
            self.volume_history[currency_pair].append(volume)

        self._update_z_score(currency_pair)

    def _get_mean_std(self, currency_pair: str) -> Tuple[float, float]:
        """Compute μ and σ, preferring bar history over tick history.

        Falls back to tick data when bars haven't been seeded yet,
        so the system works immediately from the first price update.
        """
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
        self.extremes[currency_pair] = abs(z_score) >= config.Z_SCORE_THRESHOLD

    def get_z_score(self, currency_pair: str) -> float:
        return self.z_scores.get(currency_pair, 0.0)

    def is_extreme(self, currency_pair: str) -> bool:
        return self.extremes.get(currency_pair, False)

    def get_overbought_pairs(self) -> List[str]:
        return [pair for pair, z in self.z_scores.items() if z >= config.Z_SCORE_THRESHOLD]

    def get_oversold_pairs(self) -> List[str]:
        return [pair for pair, z in self.z_scores.items() if z <= -config.Z_SCORE_THRESHOLD]

    def get_volatility(self, currency_pair: str) -> float:
        """Volatility from bar history, falling back to ticks."""
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
        """Mean from bar history, falling back to ticks."""
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
            'status': status
        }

    def seed_bars(self, historical_bars: Dict[str, List[float]]):
        """Seed bar_history with 288 M5 bars (24h) of historical close prices.

        Args:
            historical_bars: dict mapping pair -> list of close prices (oldest first)
        """
        for pair, closes in historical_bars.items():
            if pair in self.bar_history:
                self.bar_history[pair].clear()
                for c in closes[-self.bar_lookback:]:
                    self.bar_history[pair].append(c)
                if len(self.bar_history[pair]) >= 2:
                    mu, sigma = self._get_mean_std(pair)
                    ticks = list(self.price_history[pair])
                    if ticks and sigma > 0:
                        z = (ticks[-1] - mu) / sigma
                        self.z_scores[pair] = z
                        self.extremes[pair] = abs(z) >= config.Z_SCORE_THRESHOLD

    def clear_history(self):
        for pair in self.bar_history:
            self.bar_history[pair].clear()
            self.price_history[pair].clear()
            self.volume_history[pair].clear()
            self.z_scores[pair] = 0.0
            self.extremes[pair] = False


class TechnicalSignal:
    """Generates technical entry/exit signals based on Z-scores."""

    def __init__(self, analyzer: TechnicalAnalyzer):
        self.analyzer = analyzer

    def should_enter_on_extreme(self, currency_pair: str) -> bool:
        return self.analyzer.is_extreme(currency_pair)

    def should_exit_on_mean_reversion(self, currency_pair: str) -> bool:
        return self.analyzer.is_mean_reverting(currency_pair, threshold=0.5)

    def get_signal_strength(self, currency_pair: str) -> float:
        z = self.analyzer.get_z_score(currency_pair)
        return min(abs(z) / 3.0 * 100, 100.0)
