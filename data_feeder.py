"""
APEX Layer 2 — MetaTrader 5 Data Feeder

Fetches forex data from a local MetaTrader 5 terminal.
- Connects via the MetaTrader5 Python package
- Gets real-time bid/ask prices from symbol_info_tick()
- Gets historical candles from copy_rates_from_pos()
- Configurable symbol suffix (e.g., .m for OANDA MT5)

Requirements:
- MetaTrader 5 terminal installed and running with a demo/live account
- pip install MetaTrader5
"""

import time
import threading
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import config


class Mt5DataFeeder:
    """Fetches forex data from MetaTrader 5 terminal.

    Strategy: fetch 7 major USD pairs (every broker has them),
    then derive all 28 cross rates. No need for exotic symbol lookups.
    """

    # Every MT5 broker has these 7 pairs covering all 8 currencies vs USD
    USD_PAIRS = ["EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD",
                  "USD_JPY", "USD_CAD", "USD_CHF"]

    def __init__(self, symbol_suffix: str = None):
        self.symbol_suffix = symbol_suffix if symbol_suffix is not None else config.MT5_SYMBOL_SUFFIX
        self.connected = False
        self.last_error = None
        self._mt5 = None
        self.cached_rates: Dict[str, float] = {}
        self.price_callbacks = []
        self.error_callbacks = []
        self._running = False
        self._symbols_enabled = set()

    def initialize(self) -> bool:
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
            if not mt5.initialize():
                self.last_error = "MT5 terminal not running. Start MetaTrader 5 first."
                self.connected = False
                return False
            self.connected = True
            self.last_error = None
            if config.DEBUG:
                print("[MT5] Initialized successfully")
            return True
        except ImportError:
            self.last_error = (
                "MetaTrader5 package not installed.\n"
                "Run: pip install MetaTrader5"
            )
            self.connected = False
            return False
        except Exception as e:
            self.last_error = f"MT5 init error: {e}"
            self.connected = False
            return False

    def test_connection(self) -> bool:
        return self.initialize()

    def shutdown(self):
        if self._mt5:
            self._mt5.shutdown()
        self.connected = False

    def get_connection_status(self) -> str:
        if self.connected:
            return "Connected"
        return f"Disconnected: {self.last_error or 'Unknown'}"

    def _mt5_pair(self, pair: str) -> str:
        return pair.replace("_", "") + self.symbol_suffix

    def _ensure_symbol(self, symbol: str) -> bool:
        if symbol in self._symbols_enabled:
            return True
        if not self._mt5.symbol_select(symbol, True):
            self.last_error = f"Cannot enable symbol: {symbol}"
            if config.DEBUG:
                print(f"[MT5] Cannot enable symbol: {symbol}")
            return False
        self._symbols_enabled.add(symbol)
        if config.DEBUG:
            print(f"[MT5] Enabled symbol: {symbol}")
        return True

    def get_current_price(self, currency_pair: str) -> Optional[Dict]:
        if not self.connected:
            return None
        mt5_pair = self._mt5_pair(currency_pair)
        if not self._ensure_symbol(mt5_pair):
            return None
        tick = self._mt5.symbol_info_tick(mt5_pair)
        if tick is None:
            self.last_error = f"No tick data for: {mt5_pair}"
            return None
        return {
            "pair": currency_pair,
            "time": datetime.fromtimestamp(tick.time).isoformat(),
            "mid": (tick.bid + tick.ask) / 2,
            "bid": tick.bid,
            "ask": tick.ask,
        }

    def get_all_major_pairs(self) -> List[str]:
        pairs = []
        for base in config.CURRENCIES:
            for quote in config.CURRENCIES:
                if base != quote:
                    pairs.append(f"{base}_{quote}")
        return pairs

    def fetch_all_rates(self) -> Dict[str, float]:
        """Fetch 7 USD pairs and derive all 28 cross rates."""
        if not self.connected:
            return {}

        usd_rates: Dict[str, Optional[float]] = {}
        for pair in self.USD_PAIRS:
            price = self.get_current_price(pair)
            if price is None:
                continue
            base, quote = pair.split("_")
            mid = price["mid"]
            if base == "USD":
                usd_rates[quote] = 1.0 / mid if mid != 0 else None
            else:
                usd_rates[base] = mid

        usd_rates["USD"] = 1.0

        rates = {}
        for base in config.CURRENCIES:
            for quote in config.CURRENCIES:
                if base == quote:
                    continue
                base_val = usd_rates.get(base)
                quote_val = usd_rates.get(quote)
                if base_val is not None and quote_val is not None:
                    rates[f"{base}_{quote}"] = base_val / quote_val

        self.cached_rates.update(rates)
        return rates

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        pair = f"{from_currency}_{to_currency}"
        if pair in self.cached_rates:
            return self.cached_rates[pair]
        if not self.connected:
            return None
        rates = self.fetch_all_rates()
        return rates.get(pair)

    def get_order_book(self, currency_pair: str) -> Optional[Dict]:
        """Fetch live bid/ask/spread for the exact trade symbol (Task 2.1).

        Called by ConfluenceFilter when a pair reaches actionable divergence,
        rather than relying on synthetic mid-price for execution decisions.
        """
        if not self.connected:
            return None
        mt5_pair = self._mt5_pair(currency_pair)
        if not self._ensure_symbol(mt5_pair):
            return None
        tick = self._mt5.symbol_info_tick(mt5_pair)
        if tick is None:
            return None
        symbol_info = self._mt5.symbol_info(mt5_pair)
        spread = (symbol_info.spread if symbol_info else 0) * (
            symbol_info.point if symbol_info else 0.0001
        )
        return {
            "pair": currency_pair,
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": spread,
            "mid": (tick.bid + tick.ask) / 2,
            "time": datetime.fromtimestamp(tick.time).isoformat(),
        }

    def fetch_historical_closes_all_pairs(
        self, days: int = 30, interval: str = "1d"
    ) -> Dict[str, List[float]]:
        """Fetch past N days of Close prices for all 28 pairs (Task 3.2).

        Used by BasketHedging to compute a rolling Pearson correlation matrix.
        Returns dict mapping pair -> list of close prices (oldest first).
        """
        if not self.connected:
            return {}
        timeframe_map = {
            "1min": self._mt5.TIMEFRAME_M1,
            "5min": self._mt5.TIMEFRAME_M5,
            "1d": self._mt5.TIMEFRAME_D1,
        }
        tf = timeframe_map.get(interval, self._mt5.TIMEFRAME_D1)
        count_map = {"1min": 1440 * days, "5min": 288 * days, "1d": days}
        count = count_map.get(interval, days)

        all_closes: Dict[str, List[float]] = {}
        pairs = self.get_all_major_pairs()
        for pair in pairs:
            mt5_pair = self._mt5_pair(pair)
            if not self._ensure_symbol(mt5_pair):
                continue
            rates = self._mt5.copy_rates_from_pos(mt5_pair, tf, 0, count)
            if rates is not None:
                closes = [r["close"] for r in rates]
                all_closes[pair] = closes
        return all_closes

    def get_historical_candles(
        self,
        from_currency: str = "USD",
        to_currency: str = "JPY",
        interval: str = "1h",
        outputsize: str = "compact",
    ) -> Optional[List[Dict]]:
        if not self.connected:
            return None

        timeframe_map = {
            "1min": self._mt5.TIMEFRAME_M1,
            "5min": self._mt5.TIMEFRAME_M5,
            "15min": self._mt5.TIMEFRAME_M15,
            "30min": self._mt5.TIMEFRAME_M30,
            "1h": self._mt5.TIMEFRAME_H1,
            "60min": self._mt5.TIMEFRAME_H1,
            "4h": self._mt5.TIMEFRAME_H4,
            "1d": self._mt5.TIMEFRAME_D1,
            "1w": self._mt5.TIMEFRAME_W1,
        }

        tf = timeframe_map.get(interval)
        if tf is None:
            self.last_error = f"Unknown interval: {interval}"
            return None

        mt5_pair = self._mt5_pair(f"{from_currency}_{to_currency}")
        if not self._ensure_symbol(mt5_pair):
            return None
        count = 100 if outputsize == "full" else 20

        rates = self._mt5.copy_rates_from_pos(mt5_pair, tf, 0, count)
        if rates is None:
            self.last_error = f"No historical data for {mt5_pair} ({interval})"
            return None

        candles = []
        for r in rates:
            candles.append({
                "time": datetime.fromtimestamp(r["time"]).isoformat(),
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
            })
        return candles

    def stream_prices(
        self,
        instruments: List[str],
        callback: Callable = None,
        poll_interval: int = 1,
    ):
        """Poll 7 USD pairs, derive all 28 rates, feed callback for each instrument."""
        if not callback:
            return

        self.price_callbacks.append(callback)
        self._running = True

        def poll_loop():
            while self._running:
                all_rates = self.fetch_all_rates()
                for pair in instruments:
                    rate = all_rates.get(pair)
                    if rate:
                        callback({
                            "pair": pair,
                            "time": datetime.now().isoformat(),
                            "mid": rate,
                            "bid": rate,
                            "ask": rate,
                        })
                time.sleep(poll_interval)

        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()

    def on_price_update(self, callback: Callable):
        self.price_callbacks.append(callback)

    def on_error(self, callback: Callable):
        self.error_callbacks.append(callback)

    def stop_streaming(self):
        self._running = False
        if config.DEBUG:
            print("[MT5] Streaming stopped")



