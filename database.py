"""
APEX Layer 1 — Database Layer

Manages all SQLite database operations:
- Auto-create schema on first run
- Insert/update/select rates (from FRED API)
- Insert/update monthly CPI and PMI data
- Calculate and store scores
- Log trading signals
- Query history by month

All operations use parameterized queries to prevent SQL injection.
"""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import config


class Database:
    """SQLite database manager for APEX Layer 1."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. If None, uses config.DB_PATH.
        
        Raises:
            RuntimeError: If database cannot be created or connected.
        """
        self.db_path = db_path or config.DB_PATH
        
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self._lock = threading.Lock()
            self.conn = sqlite3.connect(
                self.db_path,
                timeout=config.DB_TIMEOUT,
                check_same_thread=False  # Allow access from multiple threads
            )
            self.conn.row_factory = sqlite3.Row  # Return rows as dicts

            # Performance PRAGMAs (Task 2.2 — WAL + synchronous=NORMAL)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA foreign_keys = ON")
            
            if config.DB_AUTO_CREATE:
                self._create_schema()
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to initialize database at {self.db_path}: {e}")
    
    def _create_schema(self):
        """Create database schema if it doesn't exist."""
        try:
            with self._lock:
                cursor = self.conn.cursor()
            
                # Table 1: Interest rates (updated via FRED API)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        currency TEXT NOT NULL UNIQUE,
                        rate REAL NOT NULL,
                        updated_at TEXT NOT NULL,
                        source TEXT DEFAULT 'FRED',
                        CONSTRAINT valid_currency CHECK (currency IN ('USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD'))
                    );
                """)
                
                # Table 2: Monthly manual entries (CPI + PMI)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS monthly_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        month TEXT NOT NULL,
                        currency TEXT NOT NULL,
                        cpi_actual REAL,
                        pmi_actual REAL,
                        entered_at TEXT NOT NULL,
                        UNIQUE(month, currency),
                        CONSTRAINT valid_currency CHECK (currency IN ('USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD')),
                        CONSTRAINT valid_month CHECK (month LIKE '____-__')
                    );
                """)
                
                # Table 3: Calculated scores (generated after each data entry)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        month TEXT NOT NULL,
                        currency TEXT NOT NULL,
                        score_rate REAL,
                        score_cpi REAL,
                        score_pmi REAL,
                        total_score REAL NOT NULL,
                        rank INTEGER NOT NULL,
                        calculated_at TEXT NOT NULL,
                        UNIQUE(month, currency),
                        CONSTRAINT valid_currency CHECK (currency IN ('USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD')),
                        CONSTRAINT valid_month CHECK (month LIKE '____-__')
                    );
                """)
                
                # Table 4: M1/M5 Interval Bar Cache (Task 2.2 — optimized for bar storage)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bar_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pair TEXT NOT NULL,
                        timeframe TEXT NOT NULL CHECK (timeframe IN ('M1', 'M5')),
                        bar_time TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL NOT NULL,
                        volume INTEGER DEFAULT 0,
                        UNIQUE(pair, timeframe, bar_time)
                    );
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_bar_cache_lookup
                    ON bar_cache(pair, timeframe, bar_time);
                """)

                # Table 5: Signal log (one per month)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        generated_at TEXT NOT NULL,
                        month TEXT NOT NULL UNIQUE,
                        strongest TEXT NOT NULL,
                        weakest TEXT NOT NULL,
                        gap REAL NOT NULL,
                        signal TEXT NOT NULL,
                        status TEXT NOT NULL,
                        CONSTRAINT valid_status CHECK (status IN ('ACTIVE', 'NO_TRADE', 'CLOSED')),
                        CONSTRAINT valid_month CHECK (month LIKE '____-__')
                    );
                """)

                # Table 6: Confluence signal audit log (real-time triggers)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS confluence_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        triggered_at TEXT NOT NULL,
                        pair TEXT NOT NULL,
                        signal_type TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        z_score REAL,
                        gap REAL,
                        reason TEXT,
                        layer1_active INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'PENDING'
                    );
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_confluence_log_time
                    ON confluence_log(triggered_at DESC);
                """)
                
                self.conn.commit()
                
                if config.DEBUG:
                    print("[DB] Schema created successfully")
                    
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to create schema: {e}")
    
    # ========================================================================
    # RATES Table Operations
    # ========================================================================
    
    def upsert_rate(self, currency: str, rate: float, source: str = "FRED") -> None:
        """
        Insert or update an interest rate.
        
        Args:
            currency: Currency code (USD, EUR, etc.)
            rate: Interest rate as percentage (e.g., 5.25)
            source: Data source (default "FRED")
        """
        if currency not in config.CURRENCIES:
            raise ValueError(f"Invalid currency: {currency}")
        
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO rates (currency, rate, updated_at, source)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(currency) DO UPDATE SET
                        rate = excluded.rate,
                        updated_at = excluded.updated_at,
                        source = excluded.source
                """, (currency, rate, datetime.now(timezone.utc).isoformat(), source))
                self.conn.commit()
                
                if config.DEBUG:
                    print(f"[DB] Rate updated: {currency} = {rate}% (from {source})")
                    
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to upsert rate for {currency}: {e}")
    
    def get_rate(self, currency: str) -> Optional[float]:
        """
        Get the latest interest rate for a currency.
        
        Args:
            currency: Currency code
            
        Returns:
            Rate as float, or None if not found
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT rate FROM rates WHERE currency = ?", (currency,))
            row = cursor.fetchone()
            return row["rate"] if row else None
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to fetch rate for {currency}: {e}")
    
    def get_all_rates(self) -> Dict[str, Optional[float]]:
        """
        Get all interest rates as a dict.
        
        Returns:
            Dict mapping currency code to rate (or None if missing)
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT currency, rate FROM rates")
            rows = cursor.fetchall()
            rates = {row["currency"]: row["rate"] for row in rows}
            
            # Fill missing currencies with None
            for currency in config.CURRENCIES:
                if currency not in rates:
                    rates[currency] = None
            
            return rates
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to fetch all rates: {e}")
    
    # ========================================================================
    # MONTHLY_DATA Table Operations
    # ========================================================================
    
    def update_monthly_cpi(self, month: str, currency: str, cpi: float) -> None:
        """
        Insert or update CPI data for a currency in a given month.
        
        Args:
            month: Month in format "YYYY-MM"
            currency: Currency code
            cpi: CPI value as percentage (e.g., 3.2)
        """
        if currency not in config.CURRENCIES:
            raise ValueError(f"Invalid currency: {currency}")
        
        try:
            with self._lock:
                cursor = self.conn.cursor()
                # First, get existing PMI if any
                cursor.execute(
                    "SELECT pmi_actual FROM monthly_data WHERE month = ? AND currency = ?",
                    (month, currency)
                )
                row = cursor.fetchone()
                pmi = row["pmi_actual"] if row else None
                
                # Upsert with CPI
                cursor.execute("""
                    INSERT INTO monthly_data (month, currency, cpi_actual, pmi_actual, entered_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(month, currency) DO UPDATE SET
                        cpi_actual = excluded.cpi_actual,
                        entered_at = excluded.entered_at
                """, (month, currency, cpi, pmi, datetime.now(timezone.utc).isoformat()))
                
                self.conn.commit()
                
                if config.DEBUG:
                    print(f"[DB] CPI saved: {month} {currency} = {cpi}%")
                    
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to update CPI for {currency} in {month}: {e}")
    
    def update_monthly_pmi(self, month: str, currency: str, pmi: float) -> None:
        """
        Insert or update PMI data for a currency in a given month.
        
        Args:
            month: Month in format "YYYY-MM"
            currency: Currency code
            pmi: PMI value (e.g., 51.4)
        """
        if currency not in config.CURRENCIES:
            raise ValueError(f"Invalid currency: {currency}")
        
        try:
            with self._lock:
                cursor = self.conn.cursor()
                # First, get existing CPI if any
                cursor.execute(
                    "SELECT cpi_actual FROM monthly_data WHERE month = ? AND currency = ?",
                    (month, currency)
                )
                row = cursor.fetchone()
                cpi = row["cpi_actual"] if row else None
                
                # Upsert with PMI
                cursor.execute("""
                    INSERT INTO monthly_data (month, currency, cpi_actual, pmi_actual, entered_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(month, currency) DO UPDATE SET
                        pmi_actual = excluded.pmi_actual,
                        entered_at = excluded.entered_at
                """, (month, currency, cpi, pmi, datetime.now(timezone.utc).isoformat()))
                
                self.conn.commit()
                
                if config.DEBUG:
                    print(f"[DB] PMI saved: {month} {currency} = {pmi}")
                    
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to update PMI for {currency} in {month}: {e}")
    
    def get_monthly_data(self, month: str) -> Dict[str, Dict]:
        """
        Get all CPI and PMI data for a given month.
        
        Args:
            month: Month in format "YYYY-MM"
            
        Returns:
            Dict mapping currency to {cpi_actual, pmi_actual, entered_at}
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT currency, cpi_actual, pmi_actual, entered_at FROM monthly_data WHERE month = ?",
                (month,)
            )
            rows = cursor.fetchall()
            
            data = {}
            for row in rows:
                data[row["currency"]] = {
                    "cpi_actual": row["cpi_actual"],
                    "pmi_actual": row["pmi_actual"],
                    "entered_at": row["entered_at"]
                }
            
            return data
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to fetch monthly data for {month}: {e}")
    
    def get_month_completeness(self, month: str) -> Tuple[int, int]:
        """
        Check how many of the 16 required fields (8 CPI + 8 PMI) are filled.
        
        Args:
            month: Month in format "YYYY-MM"
            
        Returns:
            Tuple of (filled_count, total_required_16)
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(CASE WHEN cpi_actual IS NOT NULL THEN 1 END) as cpi_filled,
                       COUNT(CASE WHEN pmi_actual IS NOT NULL THEN 1 END) as pmi_filled
                FROM monthly_data
                WHERE month = ?
            """, (month,))
            
            row = cursor.fetchone()
            filled = (row["cpi_filled"] or 0) + (row["pmi_filled"] or 0)
            
            return (filled, 16)
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to check month completeness for {month}: {e}")
    
    # ========================================================================
    # BAR_CACHE Table Operations (Task 2.2)
    # ========================================================================

    def upsert_bar(
        self, pair: str, timeframe: str, bar_time: str,
        open_p: float, high: float, low: float, close: float, volume: int = 0
    ) -> None:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO bar_cache (pair, timeframe, bar_time, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pair, timeframe, bar_time) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
            """, (pair, timeframe, bar_time, open_p, high, low, close, volume))
            self.conn.commit()

    def get_bars(
        self, pair: str, timeframe: str, limit: int = 288
    ) -> List[Dict]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT bar_time, open, high, low, close, volume
                FROM bar_cache
                WHERE pair = ? AND timeframe = ?
                ORDER BY bar_time DESC
                LIMIT ?
            """, (pair, timeframe, limit))
            rows = cursor.fetchall()
            bars = []
            for r in reversed(rows):
                bars.append({
                    "time": r["bar_time"],
                    "open": r["open"],
                    "high": r["high"],
                    "low": r["low"],
                    "close": r["close"],
                    "volume": r["volume"],
                })
            return bars
        except sqlite3.Error as e:
            return []

    def get_latest_bar_time(self, pair: str, timeframe: str) -> Optional[str]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT bar_time FROM bar_cache
                WHERE pair = ? AND timeframe = ?
                ORDER BY bar_time DESC LIMIT 1
            """, (pair, timeframe))
            row = cursor.fetchone()
            return row["bar_time"] if row else None
        except sqlite3.Error:
            return None

    # ========================================================================
    # SCORES Table Operations
    # ========================================================================
    
    def save_scores(self, month: str, scores: Dict[str, Dict]) -> None:
        """
        Save calculated scores for all currencies in a month.
        
        Args:
            month: Month in format "YYYY-MM"
            scores: Dict mapping currency to {score_rate, score_cpi, score_pmi, total_score, rank}
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                for currency, score_data in scores.items():
                    cursor.execute("""
                        INSERT INTO scores (month, currency, score_rate, score_cpi, score_pmi, total_score, rank, calculated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(month, currency) DO UPDATE SET
                            score_rate = excluded.score_rate,
                            score_cpi = excluded.score_cpi,
                            score_pmi = excluded.score_pmi,
                            total_score = excluded.total_score,
                            rank = excluded.rank,
                            calculated_at = excluded.calculated_at
                    """, (
                        month,
                        currency,
                        score_data.get("score_rate"),
                        score_data.get("score_cpi"),
                        score_data.get("score_pmi"),
                        score_data["total_score"],
                        score_data["rank"],
                        datetime.now(timezone.utc).isoformat()
                    ))
                
                self.conn.commit()
                
                if config.DEBUG:
                    print(f"[DB] {len(scores)} scores saved for {month}")
                    
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to save scores for {month}: {e}")
    
    def get_month_scores(self, month: str) -> Dict[str, Dict]:
        """
        Get all scores for a given month, ranked by total_score descending.
        
        Args:
            month: Month in format "YYYY-MM"
            
        Returns:
            Dict mapping currency to score data, ordered by rank
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT currency, score_rate, score_cpi, score_pmi, total_score, rank
                FROM scores
                WHERE month = ?
                ORDER BY rank ASC
            """, (month,))
            
            rows = cursor.fetchall()
            scores = {}
            for row in rows:
                scores[row["currency"]] = {
                    "score_rate": row["score_rate"],
                    "score_cpi": row["score_cpi"],
                    "score_pmi": row["score_pmi"],
                    "total_score": row["total_score"],
                    "rank": row["rank"]
                }
            
            return scores
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to fetch scores for {month}: {e}")
    
    # ========================================================================
    # SIGNALS Table Operations
    # ========================================================================
    
    def save_signal(self, month: str, strongest: str, weakest: str, gap: float, 
                    signal: str, status: str) -> None:
        """
        Save a trading signal for a month.
        
        Args:
            month: Month in format "YYYY-MM"
            strongest: Currency code with highest score
            weakest: Currency code with lowest score
            gap: Score difference (strongest - weakest)
            signal: Signal string (e.g., "SHORT AUD/JPY" or "NO TRADE")
            status: "ACTIVE", "NO_TRADE", or "CLOSED"
        """
        if status not in ("ACTIVE", "NO_TRADE", "CLOSED"):
            raise ValueError(f"Invalid status: {status}")
        
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO signals (generated_at, month, strongest, weakest, gap, signal, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(month) DO UPDATE SET
                        generated_at = excluded.generated_at,
                        strongest = excluded.strongest,
                        weakest = excluded.weakest,
                        gap = excluded.gap,
                        signal = excluded.signal,
                        status = excluded.status
                """, (datetime.now(timezone.utc).isoformat(), month, strongest, weakest, gap, signal, status))
                
                self.conn.commit()
                
                if config.DEBUG:
                    print(f"[DB] Signal saved for {month}: {signal} (status={status})")
                    
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to save signal for {month}: {e}")
    
    def get_signal(self, month: str) -> Optional[Dict]:
        """
        Get the signal for a given month.
        
        Args:
            month: Month in format "YYYY-MM"
            
        Returns:
            Dict with signal data, or None if not found
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT strongest, weakest, gap, signal, status FROM signals WHERE month = ?",
                (month,)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    "strongest": row["strongest"],
                    "weakest": row["weakest"],
                    "gap": row["gap"],
                    "signal": row["signal"],
                    "status": row["status"]
                }
            return None
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to fetch signal for {month}: {e}")
    
    def get_all_signals(self, limit: int = 24) -> List[Dict]:
        """
        Get most recent signals (for history tab).
        
        Args:
            limit: Maximum number of signals to return (default 24 months)
            
        Returns:
            List of signal dicts, ordered by month descending
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT month, strongest, weakest, gap, signal, status
                FROM signals
                ORDER BY month DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            signals = []
            for row in rows:
                signals.append({
                    "month": row["month"],
                    "strongest": row["strongest"],
                    "weakest": row["weakest"],
                    "gap": row["gap"],
                    "signal": row["signal"],
                    "status": row["status"]
                })
            
            return signals
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to fetch signals: {e}")
    
    # ========================================================================
    # CONFLUENCE_LOG Table Operations (Phase 3 audit trail)
    # ========================================================================

    def save_confluence_signal(self, pair: str, signal_type: str, confidence: float,
                               z_score: float = None, gap: float = None,
                               reason: str = None, layer1_active: bool = False) -> None:
        """Persist a real-time confluence trigger to the audit log.

        Unlike save_signal() (monthly Layer 1 signals), this logs every
        live/backtested trigger with sub-second granularity.
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO confluence_log
                        (triggered_at, pair, signal_type, confidence, z_score, gap, reason, layer1_active, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                """, (
                    datetime.now(timezone.utc).isoformat(),
                    pair, signal_type, confidence, z_score, gap, reason,
                    1 if layer1_active else 0
                ))
                self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()

    def get_confluence_log(self, limit: int = 100) -> List[Dict]:
        """Get the most recent confluence triggers."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT triggered_at, pair, signal_type, confidence, z_score, gap, reason, status
                FROM confluence_log
                ORDER BY triggered_at DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []

    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            if config.DEBUG:
                print("[DB] Connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Singleton instance (optional convenience)
_db_instance = None

def get_database() -> Database:
    """Get or create the global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
