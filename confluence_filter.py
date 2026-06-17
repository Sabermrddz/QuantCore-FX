from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import config
from layer2_technical import TechnicalAnalyzer, TechnicalSignal
from currency_strength_matrix import CurrencyStrengthMatrix


class ConfluenceFilter:
    """Merges Layer 1 + Layer 2 with macro directional boundary enforcement.

    Layer 1 produces a permanent monthly directional bias matrix:
        STRONG (top 2)  — can only be longed, never shorted
        WEAK   (bottom 2) — can only be shorted, never longed
        NEUTRAL (middle 4) — no restriction

    Layer 2 operates freely — any short-term divergence can generate an entry,
    provided it does not CROSS or VIOLATE the Layer 1 macro boundary.
    """

    def __init__(self, technical_analyzer: TechnicalAnalyzer):
        self.tech_analyzer = technical_analyzer
        self.tech_signal = TechnicalSignal(technical_analyzer)

        # Layer 1 directional bias matrix (set monthly from fundamental scores)
        self.bias_matrix: Dict[str, Dict] = {}
        self.layer1_strongest = None
        self.layer1_weakest = None
        self.layer1_gap = 0.0
        self.layer1_timestamp = None
        self.layer1_is_active = False

        self.last_confluence_check = None
        self.confluence_strength = 0.0

        self.matrix: Optional[CurrencyStrengthMatrix] = None
        self.matrix_cross_pair = None

    def _build_matrix(self, current_prices: Dict[str, float] = None):
        z_scores = self.tech_analyzer.get_all_z_scores()
        if self.matrix is None:
            self.matrix = CurrencyStrengthMatrix()
        self.matrix.update(z_scores, current_prices=current_prices)
        self.matrix_cross_pair = self.matrix.get_matrix_cross()

    def set_layer1_bias(
        self,
        strongest: str,
        weakest: str,
        gap: float,
        bias_matrix: dict = None,
        timestamp: datetime = None
    ):
        """Set the monthly directional bias matrix from Layer 1 fundamental scores.

        Args:
            strongest: Top-ranked currency from fundamental scoring
            weakest: Bottom-ranked currency
            gap: Score spread between strongest and weakest
            bias_matrix: Dict of {currency: {direction, score, rank}} —
                         the permanent macro boundary for the month
        """
        self.bias_matrix = bias_matrix or {}
        self.layer1_strongest = strongest
        self.layer1_weakest = weakest
        self.layer1_gap = gap
        self.layer1_timestamp = timestamp or datetime.now()
        self.layer1_is_active = gap >= config.MIN_GAP_TO_TRADE

        if config.DEBUG:
            directions = {c: v["direction"] for c, v in self.bias_matrix.items()}
            print(f"[Confluence] Monthly bias matrix set: {directions}")

    def _check_boundary(self, short_ccy: str, long_ccy: str) -> Tuple[bool, str]:
        """Check if a proposed trade crosses the Layer 1 macro boundary.

        A trade proposes SHORT short_ccy + LONG long_ccy.
        Boundary rules:
          - STRONG currencies cannot be shorted
          - WEAK currencies cannot be longed
          - NEUTRAL currencies have no restriction

        Returns:
            (allowed: bool, reason: str)
        """
        if not self.bias_matrix:
            return True, "No macro bias set"

        short_dir = self.bias_matrix.get(short_ccy, {}).get("direction", "NEUTRAL")
        long_dir = self.bias_matrix.get(long_ccy, {}).get("direction", "NEUTRAL")

        if short_dir == "STRONG":
            return (
                False,
                f"Cannot short {short_ccy}: classified STRONG by Layer 1 macro bias"
            )
        if long_dir == "WEAK":
            return (
                False,
                f"Cannot long {long_ccy}: classified WEAK by Layer 1 macro bias"
            )
        return True, "Within macro boundary"

    def check_entry_confluence(self, current_prices: Dict[str, float] = None
                               ) -> Tuple[bool, str, float]:
        """Check entry conditions.

        Layer 2 operates freely. The ONLY constraint is the Layer 1
        macro directional boundary: STRONG currencies can't be shorted,
        WEAK currencies can't be longed.

        Priority:
        1. Matrix divergence (currency-level) — checked against boundary
        2. Pair extreme Z-score (pair-level) — checked against boundary

        Returns:
            (should_enter, reason, confluence_strength)
        """
        self._build_matrix(current_prices)

        # === PRIMARY: Matrix divergence ===
        # If one currency is overbought across ALL pairs and another is
        # oversold across ALL pairs, we have a genuine S.A.T.O.R.I. signal.
        if self.matrix and self.matrix.has_divergence():
            mc = self.matrix.get_matrix_cross()
            gap = self.matrix.get_divergence_gap()

            if mc and "_" in mc:
                short_ccy, long_ccy = mc.split("_", 1)
                allowed, reason = self._check_boundary(short_ccy, long_ccy)
                if allowed:
                    confidence = min(abs(gap) / 4.0, 1.0) * 100
                    self.confluence_strength = confidence
                    self.last_confluence_check = datetime.now()
                    return (
                        True,
                        f"MATRIX DIVERGENCE: {mc} "
                        f"(Gap: {gap:.1f}σ, Strength: {confidence:.0f}%)",
                        confidence,
                    )
                else:
                    self.confluence_strength = 0.0
                    self.last_confluence_check = datetime.now()
                    return False, f"MATRIX DIVERGENCE BLOCKED — {reason}", 0.0

        # === SECONDARY: Any extreme pair Z-score, checked against boundary ===
        all_z = self.tech_analyzer.get_all_z_scores()
        sorted_pairs = sorted(all_z.items(), key=lambda x: abs(x[1]), reverse=True)

        for pair, z_score in sorted_pairs:
            if abs(z_score) < config.Z_SCORE_THRESHOLD:
                continue

            base, quote = pair.split("_")
            if z_score > 0:
                short_ccy, long_ccy = base, quote
            else:
                short_ccy, long_ccy = quote, base

            allowed, reason = self._check_boundary(short_ccy, long_ccy)
            if allowed:
                confidence = min(abs(z_score) / 3.0, 1.0) * 100
                self.confluence_strength = confidence
                self.last_confluence_check = datetime.now()
                return (
                    True,
                    f"PAIR EXTREME: {pair} Z={z_score:.2f} "
                    f"(Strength: {confidence:.0f}%)",
                    confidence,
                )

        return False, "No valid signals within macro boundary", 0.0

    def check_exit_confluence(self) -> Tuple[bool, str]:
        """Check if position should exit (mean reversion / boundary shift)."""
        self._build_matrix()

        if self.matrix and not self.matrix.has_divergence():
            gap = self.matrix.get_divergence_gap()
            return True, f"EXIT: Matrix divergence collapsed (gap: {gap:.2f}σ)"

        if self.layer1_strongest and self.layer1_weakest:
            pair = f"{self.layer1_strongest}_{self.layer1_weakest}"
            if self.tech_signal.should_exit_on_mean_reversion(pair):
                z = self.tech_analyzer.get_z_score(pair)
                return True, f"EXIT: {pair} mean reversion (Z-score: {z:.2f})"

        return False, "Position still valid"

    def is_conflicting(self) -> bool:
        """Check if any extreme Layer 2 signal crosses the macro boundary."""
        if not self.bias_matrix:
            return False

        all_z = self.tech_analyzer.get_all_z_scores()
        for pair, z_score in all_z.items():
            if abs(z_score) < config.Z_SCORE_THRESHOLD:
                continue
            base, quote = pair.split("_")
            if z_score > 0:
                short_dir = self.bias_matrix.get(base, {}).get("direction", "NEUTRAL")
                long_dir = self.bias_matrix.get(quote, {}).get("direction", "NEUTRAL")
            else:
                short_dir = self.bias_matrix.get(quote, {}).get("direction", "NEUTRAL")
                long_dir = self.bias_matrix.get(base, {}).get("direction", "NEUTRAL")
            if short_dir == "STRONG" or long_dir == "WEAK":
                return True
        return False

    def get_confluence_report(self, current_prices: Dict[str, float] = None) -> Dict:
        """Get detailed confluence analysis report including matrix status."""
        self._build_matrix(current_prices)
        matrix_report = self.matrix.get_report() if self.matrix else {}
        pair = f"{self.layer1_strongest}_{self.layer1_weakest}" if self.layer1_strongest else "N/A"

        mc = matrix_report.get("matrix_cross", "N/A")
        mc_z = self.tech_analyzer.get_z_score(mc) if mc and mc != "N/A" else 0.0

        if pair != "N/A":
            z_score = self.tech_analyzer.get_z_score(pair)
            volatility = self.tech_analyzer.get_volatility(pair)
            mean_price = self.tech_analyzer.get_mean_price(pair)
        else:
            z_score = 0.0
            volatility = 0.0
            mean_price = 0.0

        return {
            'pair': pair,
            'layer1_gap': self.layer1_gap,
            'layer1_status': 'ACTIVE' if self.layer1_is_active else 'NO_TRADE',
            'layer2_z_score': z_score,
            'layer2_is_extreme': self.tech_analyzer.is_extreme(pair) if pair != "N/A" else False,
            'layer2_volatility': volatility,
            'layer2_mean_price': mean_price,
            'confluence_strength': self.confluence_strength,
            'last_check': self.last_confluence_check,
            'is_conflicting': self.is_conflicting(),
            'matrix_cross': mc,
            'matrix_cross_z': mc_z,
            'divergence_gap': matrix_report.get("divergence_gap", 0),
            'has_matrix_divergence': matrix_report.get("has_divergence", False),
            'matrix_ranked': matrix_report.get("ranked", []),
            'active_session': matrix_report.get("active_session", "N/A"),
            'bias_matrix': {
                c: v["direction"] for c, v in self.bias_matrix.items()
            } if self.bias_matrix else {},
        }

    def get_all_signals(self, current_prices: Dict[str, float] = None) -> Dict[str, Dict]:
        """Get all available signals ranked by strength."""
        signals = {}
        self._build_matrix(current_prices)

        if self.matrix and self.matrix.has_divergence():
            mc = self.matrix.get_matrix_cross()
            if mc:
                gap = self.matrix.get_divergence_gap()
                strength = min(abs(gap) / 4.0, 1.0) * 100
                mc_z = self.tech_analyzer.get_z_score(mc)

                short_ccy, long_ccy = mc.split("_", 1)
                allowed, _ = self._check_boundary(short_ccy, long_ccy)
                if allowed:
                    signals[mc] = {
                        'pair': mc,
                        'type': 'MATRIX_DIVERGENCE',
                        'strength': strength,
                        'reason': f"Matrix cross {mc} (spread: {gap:.2f}σ)",
                        'direction': 'SHORT' if strength > 50 else 'LONG',
                    }

        # Scan all extreme pairs
        for pair, z_score in sorted(
            self.tech_analyzer.get_all_z_scores().items(),
            key=lambda x: abs(x[1]), reverse=True
        ):
            if abs(z_score) < config.Z_SCORE_THRESHOLD:
                continue
            if pair in signals:
                continue

            base, quote = pair.split("_")
            if z_score > 0:
                short_ccy, long_ccy = base, quote
            else:
                short_ccy, long_ccy = quote, base

            allowed, _ = self._check_boundary(short_ccy, long_ccy)
            if allowed:
                strength = min(abs(z_score) / 3.0, 1.0) * 100
                signals[pair] = {
                    'pair': pair,
                    'type': 'PAIR_EXTREME',
                    'strength': strength,
                    'reason': f"{pair} Z={z_score:.2f} within macro boundary",
                    'direction': 'SHORT' if z_score > 0 else 'LONG',
                }

        return signals


class SignalHistory:
    """Track historical confluence signals for analysis."""

    def __init__(self):
        self.signals = []
        self.max_history = 1000

    def add_signal(self, signal: Dict):
        signal['timestamp'] = datetime.now()
        self.signals.append(signal)
        if len(self.signals) > self.max_history:
            self.signals = self.signals[-self.max_history:]

    def get_signals_for_pair(self, pair: str) -> list:
        return [s for s in self.signals if s.get('pair') == pair]

    def get_recent_signals(self, hours: int = 24) -> list:
        cutoff = datetime.now().timestamp() - (hours * 3600)
        return [s for s in self.signals if s['timestamp'].timestamp() > cutoff]

    def get_win_rate(self, pair: str = None) -> float:
        if pair:
            sigs = self.get_signals_for_pair(pair)
        else:
            sigs = self.signals
        if not sigs:
            return 0.0
        wins = sum(1 for s in sigs if s.get('result') == 'WIN')
        return (wins / len(sigs)) * 100

    def clear(self):
        self.signals = []
