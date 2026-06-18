"""
APEX Layer 1 — Configuration and Constants

This module loads all configuration from the .env file and defines
all hardcoded constants for the Currency Strength Engine.

Responsibilities:
- Load API keys and settings from .env
- Define the 8 major currencies tracked
- Define CB inflation targets (hardcoded — only change if CB mandate changes)
- Define FRED series IDs for interest rates
- Define scoring weights
- Define minimum gap threshold for trading
- Validate configuration on startup
"""

import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# Load .env file from project root
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ============================================================================
# FRED API Configuration
# ============================================================================
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# ============================================================================
# Database Configuration
# ============================================================================
DB_PATH = os.getenv("DB_PATH", "apex.db")

# ============================================================================
# The 8 Major Currencies
# ============================================================================
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
NUM_CURRENCIES = len(CURRENCIES)

# ============================================================================
# Central Bank Inflation Targets (%)
# ============================================================================
# These are hardcoded constants. They almost never change.
# If a central bank officially revises its mandate, update it here manually.
CB_TARGETS = {
    "USD": 2.0,   # Federal Reserve
    "EUR": 2.0,   # ECB
    "GBP": 2.0,   # Bank of England
    "JPY": 2.0,   # Bank of Japan
    "AUD": 2.5,   # RBA
    "CAD": 2.0,   # Bank of Canada
    "CHF": 1.5,   # SNB
    "NZD": 2.0,   # RBNZ
}

# ============================================================================
# FRED Series IDs for Interest Rates
# ============================================================================
# These map each currency to its FRED series ID.
# If FRED returns an error, the app will fall back to manual entry (see settings).
FRED_SERIES = {
    "USD": "FEDFUNDS",  # US Federal Funds Rate
    "EUR": "ECBDFR",    # ECB Deposit Rate
    "GBP": "BOEIR",     # Bank of England Interest Rate
    "JPY": "IRSTCI01JPM156N",  # Japan Short-Term Interest Rate
    "AUD": "RBATR",     # RBA Target Cash Rate
    "CAD": "BOCARR",    # Bank of Canada Overnight Rate
    "CHF": "SNBON",     # SNB Policy Rate
    "NZD": "RBNZR",     # RBNZ Official Cash Rate
}

# ============================================================================
# Scoring Configuration
# ============================================================================
WEIGHT_RATE = float(os.getenv("WEIGHT_RATE", 0.50))  # Interest rate diff: 50%
WEIGHT_CPI = float(os.getenv("WEIGHT_CPI", 0.30))    # CPI deviation: 30%
WEIGHT_PMI = float(os.getenv("WEIGHT_PMI", 0.20))    # PMI composite: 20%

# Verify weights sum to 1.0 (with tolerance for floating point precision)
TOTAL_WEIGHT = WEIGHT_RATE + WEIGHT_CPI + WEIGHT_PMI
if not (0.99 <= TOTAL_WEIGHT <= 1.01):
    raise ValueError(
        f"Weights must sum to 1.0. "
        f"Current: RATE={WEIGHT_RATE}, CPI={WEIGHT_CPI}, PMI={WEIGHT_PMI} "
        f"(total={TOTAL_WEIGHT})"
    )

# ============================================================================
# Trading Rules
# ============================================================================
MIN_GAP_TO_TRADE = float(os.getenv("MIN_GAP", 20))  # Minimum 20-point gap

# Gap threshold tiers (used for UI display and Layer 2+ position sizing)
GAP_THRESHOLDS = {
    "no_trade": 20,        # Gap < 20: NO TRADE
    "weak": 40,            # Gap 20-40: Weak signal, max 0.5%
    "standard": 60,        # Gap 40-60: Standard signal, max 1.0%
    "strong": float("inf")  # Gap > 60: Strong signal (Layer 5+ for full sizing)
}

# ============================================================================
# Auto-fetch Settings
# ============================================================================
AUTO_FETCH_RATES_ON_STARTUP = os.getenv("AUTO_FETCH_RATES_ON_STARTUP", "true").lower() == "true"
FRED_FETCH_TIMEOUT = 10  # seconds

# ============================================================================
# Data Validation Rules
# ============================================================================
RATE_MIN = -5.0  # Some CBs have negative rates
RATE_MAX = 20.0  # Reasonable upper bound
CPI_MIN = float(os.getenv("CPI_MIN", -5.0))
CPI_MAX = float(os.getenv("CPI_MAX", 10.0))
PMI_MIN = float(os.getenv("PMI_MIN", 0.0))
PMI_MAX = float(os.getenv("PMI_MAX", 100.0))

# ============================================================================
# Database Settings
# ============================================================================
DB_AUTO_CREATE = True  # Automatically create schema if DB doesn't exist
DB_TIMEOUT = 5  # Connection timeout in seconds

# ============================================================================
# Validation Function
# ============================================================================
def validate_config():
    """
    Validate configuration on startup.
    Raises ValueError if critical settings are missing or invalid.
    """
    errors = []
    
    if not FRED_API_KEY:
        errors.append(
            "FRED_API_KEY not set in .env file. "
            "Get a free key from fred.stlouisfed.org and add to .env"
        )
    
    if not DB_PATH:
        errors.append("DB_PATH not configured in .env or config.py")
    
    for currency in CURRENCIES:
        if currency not in CB_TARGETS:
            errors.append(f"Missing CB target for {currency}")
        if currency not in FRED_SERIES:
            errors.append(f"Missing FRED series ID for {currency}")
    
    if errors:
        raise ValueError(
            "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


# ============================================================================
# Debug Mode
# ============================================================================
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ============================================================================
# Logging Configuration (Phase 5)
# ============================================================================
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE = os.getenv("LOG_FILE", "apex.log")

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("apex")

# ============================================================================
# UI Configuration
# ============================================================================
APP_TITLE = "APEX — Currency Strength Engine"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 850

TAB_NAMES = {
    "dashboard": "📊 Dashboard",
    "entry": "📝 Data Entry",
    "layer2": "📈 Layer 2 (Technical)",
    "confluence": "🎯 Confluence Signals",
    "history": "📜 History",
    "settings": "⚙️ Settings"
}

# Currency emojis for UI
CURRENCY_EMOJIS = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "GBP": "🇬🇧",
    "JPY": "🇯🇵",
    "AUD": "🇦🇺",
    "CAD": "🇨🇦",
    "CHF": "🇨🇭",
    "NZD": "🇳🇿",
}

# ============================================================================
# LAYER 2 — Technical Analysis Configuration
# ============================================================================
# MetaTrader 5 (local terminal, no API key needed)
# Symbol suffix varies by broker (e.g., .m for OANDA MT5)
MT5_SYMBOL_SUFFIX = os.getenv("MT5_SYMBOL_SUFFIX", "")

# Technical Analysis Settings
Z_SCORE_THRESHOLD = float(os.getenv("Z_SCORE_THRESHOLD", 2.0))  # Overbought/oversold level (legacy/macro)
SCALP_Z_SCORE_THRESHOLD = float(os.getenv("SCALP_Z_SCORE_THRESHOLD", 1.5))  # Intraday threshold (more sensitive)
SCALP_MIN_GAP_TO_TRADE = float(os.getenv("SCALP_MIN_GAP", 2.0))  # Intraday min gap (sigma units)

# Multi-timeframe configuration (short lookbacks for scalping)
TIMEFRAMES = {
    "M5":  {"interval": "5min",  "bars": 48,  "label": "5 min"},
    "M15": {"interval": "15min", "bars": 16,  "label": "15 min"},
    "H1":  {"interval": "1h",    "bars": 12,  "label": "1 hour"},
    "H4":  {"interval": "4h",    "bars": 6,   "label": "4 hour"},
}
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "M5")

# Historical bar config (backward compat)
BAR_TIMEFRAME = os.getenv("BAR_TIMEFRAME", "M5")
BAR_LOOKBACK_HOURS = int(os.getenv("BAR_LOOKBACK_HOURS", 48))
HISTORICAL_POLL_INTERVAL = int(os.getenv("HISTORICAL_POLL_INTERVAL", 300))  # 5 min in seconds

# SL/TP based on ATR
SL_ATR_PERIOD = 14
SL_ATR_MULTIPLIER = float(os.getenv("SL_ATR_MULTIPLIER", "2.0"))
TRADE_RR_RATIO = float(os.getenv("TRADE_RR_RATIO", "1.4"))

# Session Detection
SESSION_TOKYO_OPEN = 0    # 00:00 UTC
SESSION_TOKYO_CLOSE = 8   # 08:00 UTC
SESSION_LONDON_OPEN = 7   # 07:00 UTC
SESSION_LONDON_CLOSE = 16 # 16:00 UTC
SESSION_NEWYORK_OPEN = 13 # 13:00 UTC
SESSION_NEWYORK_CLOSE = 21# 21:00 UTC

# ============================================================================
# Confluence Layer Weights (Scalper Profile)
# ============================================================================
# Effective weight distribution for signal display:
#   - Market Structure + Order Flow (Currency Strength Matrix / Z-scores): ~65%
#   - Currency Power Matrix (Session SRV + momentum): ~25%
#   - Macro / Fundamental Backdrop (Layer 1 scorer, advisory only): ~10%
#
# The macro layer is DISPLAY ONLY — it never blocks or vetoes a trade signal.
# Currency Power Matrix refers to CurrencyStrengthMatrix (this engine).
# ============================================================================
CONFLUENCE_ENABLED = os.getenv("CONFLUENCE_ENABLED", "true").lower() == "true"
MIN_CONFLUENCE_STRENGTH = float(os.getenv("MIN_CONFLUENCE_STRENGTH", 60.0))  # 60% confidence threshold

# Risk Management
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", 10000.0))  # Starting balance
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", 0.01))  # 1% per trade
MAX_PORTFOLIO_LEVERAGE = float(os.getenv("MAX_PORTFOLIO_LEVERAGE", 2.0))  # Max 2:1 leverage
USE_GRID_HEDGING = os.getenv("USE_GRID_HEDGING", "true").lower() == "true"
GRID_LEVELS = int(os.getenv("GRID_LEVELS", 3))  # Number of hedging levels

# Live Execution (Phase 4) — OFF by default
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", 0.05))
MAX_BASKET_EXPOSURE_PCT = float(os.getenv("MAX_BASKET_EXPOSURE_PCT", 0.20))

if DEBUG:
    print("[CONFIG] Debug mode enabled")
    print(f"[CONFIG] FRED API Key: {FRED_API_KEY[:10]}..." if FRED_API_KEY else "[CONFIG] FRED API Key: NOT SET")
    print(f"[CONFIG] MT5 symbol suffix: '{MT5_SYMBOL_SUFFIX}'")
    print(f"[CONFIG] Database: {DB_PATH}")
    print(f"[CONFIG] Weights: Rate={WEIGHT_RATE}, CPI={WEIGHT_CPI}, PMI={WEIGHT_PMI}")
    print(f"[CONFIG] Min gap to trade: {MIN_GAP_TO_TRADE}")
    print(f"[CONFIG] Z-score threshold: {Z_SCORE_THRESHOLD}")
    print(f"[CONFIG] Confluence enabled: {CONFLUENCE_ENABLED}")


# Call validation on import (fail early if config is broken)
try:
    validate_config()
except ValueError as e:
    print(f"[ERROR] Configuration validation failed:\n{e}")
    raise
