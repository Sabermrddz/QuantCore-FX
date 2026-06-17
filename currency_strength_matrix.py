from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
import statistics
import config


@dataclass
class CurrencyStrength:
    name: str
    avg_z_score: float
    rank: int
    is_overbought: bool
    is_oversold: bool
    direction: str
    session_srv: float = 0.0  # Session Relative Velocity (Task 1.2)


class SessionTracker:
    """Detects the active trading session and tracks session-start snapshots.

    Sessions (UTC):
        Tokyo:    00:00–08:00
        London:   07:00–16:00
        New York: 13:00–22:00
    Overlapping hours are resolved as London (the dominant session).
    """

    TOKYO = "Tokyo"
    LONDON = "London"
    NEWYORK = "New York"

    def __init__(self):
        self.current_session: Optional[str] = None
        self.session_start_prices: Dict[str, float] = {}  # pair -> price at session open
        self.session_open_time: Optional[datetime] = None

    def get_active_session(self, utc_hour: int = None) -> str:
        if utc_hour is None:
            utc_hour = datetime.now(timezone.utc).hour
        if config.SESSION_LONDON_OPEN <= utc_hour < config.SESSION_LONDON_CLOSE:
            return self.LONDON
        if config.SESSION_TOKYO_OPEN <= utc_hour < config.SESSION_TOKYO_CLOSE:
            return self.TOKYO
        if config.SESSION_NEWYORK_OPEN <= utc_hour < config.SESSION_NEWYORK_CLOSE:
            return self.NEWYORK
        return "Off-Hours"

    def check_new_session(self, current_prices: Dict[str, float]) -> Optional[str]:
        """Detect if a new session has started and snapshot prices."""
        now = datetime.now(timezone.utc)
        session = self.get_active_session(now.hour)
        if session != self.current_session and session != "Off-Hours":
            self.current_session = session
            self.session_start_prices = dict(current_prices)
            self.session_open_time = now
            return session
        if self.current_session is None:
            self.current_session = session
            if session != "Off-Hours":
                self.session_start_prices = dict(current_prices)
                self.session_open_time = now
        return None

    def compute_srv(self, pair: str, current_price: float) -> float:
        """Session Relative Velocity: % change from session open to now."""
        start = self.session_start_prices.get(pair)
        if start is None or start == 0:
            return 0.0
        return ((current_price - start) / start) * 100.0


class CurrencyStrengthMatrix:
    """Computes individual currency strength indices from pair Z-scores.

    Includes Session-Based Indexing (Task 1.2):
    - Tracks performance since Tokyo/London/NY session opens
    - Session Relative Velocity (SRV) per currency
    """

    def __init__(self, z_scores: Dict[str, float] = None):
        self.currencies = config.CURRENCIES
        self.threshold = config.Z_SCORE_THRESHOLD
        self._raw_scores: Dict[str, List[float]] = {}
        self._strengths: Dict[str, CurrencyStrength] = {}
        self.session_tracker = SessionTracker()
        self._srv_map: Dict[str, float] = {}  # currency -> avg SRV
        if z_scores:
            self.update(z_scores)

    def update(self, z_scores: Dict[str, float], current_prices: Dict[str, float] = None):
        """Recompute all currency strengths from 28 pair Z-scores.

        If current_prices is provided, also updates session tracking
        and computes Session Relative Velocity.
        """
        self._raw_scores = {}
        for ccy in self.currencies:
            scores = []
            for other in self.currencies:
                if other == ccy:
                    continue
                pair = f"{ccy}_{other}"
                z = z_scores.get(pair)
                if z is not None:
                    scores.append(z)
            self._raw_scores[ccy] = scores

        strengths = {}
        for ccy, scores in self._raw_scores.items():
            avg_z = statistics.mean(scores) if scores else 0.0
            strengths[ccy] = CurrencyStrength(
                name=ccy,
                avg_z_score=avg_z,
                rank=0,
                is_overbought=avg_z >= self.threshold,
                is_oversold=avg_z <= -self.threshold,
                direction="OVERBOUGHT" if avg_z >= self.threshold else ("OVERSOLD" if avg_z <= -self.threshold else "NEUTRAL"),
            )

        sorted_ccys = sorted(strengths.keys(), key=lambda c: strengths[c].avg_z_score, reverse=True)
        for rank, ccy in enumerate(sorted_ccys, 1):
            strengths[ccy].rank = rank

        # Session tracking (Task 1.2)
        if current_prices:
            new_session = self.session_tracker.check_new_session(current_prices)
            self._compute_srv(current_prices, strengths)

        self._strengths = strengths

    def _compute_srv(self, current_prices: Dict[str, float],
                     strengths: Dict[str, CurrencyStrength]):
        """Compute average Session Relative Velocity per currency."""
        srv_scores: Dict[str, List[float]] = {c: [] for c in self.currencies}
        for ccy in self.currencies:
            for other in self.currencies:
                if other == ccy:
                    continue
                pair = f"{ccy}_{other}"
                price = current_prices.get(pair)
                if price is not None:
                    srv = self.session_tracker.compute_srv(pair, price)
                    srv_scores[ccy].append(srv)
        for ccy in self.currencies:
            scores = srv_scores[ccy]
            self._srv_map[ccy] = statistics.mean(scores) if scores else 0.0
            if ccy in strengths:
                strengths[ccy].session_srv = self._srv_map[ccy]

    def get_strongest(self) -> Optional[CurrencyStrength]:
        return max(self._strengths.values(), key=lambda s: s.avg_z_score) if self._strengths else None

    def get_weakest(self) -> Optional[CurrencyStrength]:
        return min(self._strengths.values(), key=lambda s: s.avg_z_score) if self._strengths else None

    def get_matrix_cross(self) -> Optional[str]:
        s = self.get_strongest()
        w = self.get_weakest()
        if s and w and s.name != w.name:
            return f"{s.name}_{w.name}"
        return None

    def get_divergence_gap(self) -> float:
        s = self.get_strongest()
        w = self.get_weakest()
        return (s.avg_z_score - w.avg_z_score) if s and w else 0.0

    def has_divergence(self) -> bool:
        s = self.get_strongest()
        w = self.get_weakest()
        return bool(s and w and s.is_overbought and w.is_oversold)

    def get_strong_currencies(self) -> List[str]:
        return [c.name for c in self._strengths.values() if c.is_overbought]

    def get_weak_currencies(self) -> List[str]:
        return [c.name for c in self._strengths.values() if c.is_oversold]

    def get_ranked_list(self) -> List[CurrencyStrength]:
        return sorted(self._strengths.values(), key=lambda s: s.rank)

    def get_active_session(self) -> str:
        return self.session_tracker.get_active_session()

    def get_srv_map(self) -> Dict[str, float]:
        return dict(self._srv_map)

    def get_report(self) -> Dict:
        ranked = self.get_ranked_list()
        s = self.get_strongest()
        w = self.get_weakest()
        return {
            "ranked": [(c.name, round(c.avg_z_score, 2), c.direction, round(c.session_srv, 4)) for c in ranked],
            "strongest": s.name if s else None,
            "strongest_z": round(s.avg_z_score, 2) if s else 0,
            "weakest": w.name if w else None,
            "weakest_z": round(w.avg_z_score, 2) if w else 0,
            "matrix_cross": self.get_matrix_cross(),
            "divergence_gap": round(self.get_divergence_gap(), 2),
            "has_divergence": self.has_divergence(),
            "overbought": self.get_strong_currencies(),
            "oversold": self.get_weak_currencies(),
            "active_session": self.get_active_session(),
        }
