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
from dotenv import load_dotenv
from pathlib import Path

# Load .env file from project root
env_path = Path(__file__).parent.parent / ".env"
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
    "GBP": "BOEBR",     # Bank of England Base Rate
    "JPY": "IRSTJPN",   # Japan Policy Rate (or manual from BOJ website)
    "AUD": "RBATCTR",   # RBA Cash Target Rate
    "CAD": "BOCCRT",    # BOC Policy Interest Rate
    "CHF": "SNBPOL",    # SNB Policy Rate
    "NZD": "RBNZOCR",   # RBNZ Official Cash Rate
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
# UI Settings
# ============================================================================
APP_TITLE = "APEX Layer 1 — Currency Strength Engine"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
TAB_NAMES = {
    "dashboard": "Dashboard",
    "entry": "Monthly Entry",
    "history": "History",
    "settings": "Settings",
}

# Currency display format (with flags for nice UI)
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
# Data Validation Rules
# ============================================================================
# For CPI entry
CPI_MIN = -10.0  # Reasonable lower bound for inflation
CPI_MAX = 50.0   # Reasonable upper bound (hyperinflation)

# For PMI entry
PMI_MIN = 0.0    # PMI is 0-100
PMI_MAX = 100.0

# For interest rates
RATE_MIN = -5.0  # Some CBs have negative rates
RATE_MAX = 20.0  # Reasonable upper bound

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

if DEBUG:
    print("[CONFIG] Debug mode enabled")
    print(f"[CONFIG] FRED API Key: {FRED_API_KEY[:10]}..." if FRED_API_KEY else "[CONFIG] FRED API Key: NOT SET")
    print(f"[CONFIG] Database: {DB_PATH}")
    print(f"[CONFIG] Weights: Rate={WEIGHT_RATE}, CPI={WEIGHT_CPI}, PMI={WEIGHT_PMI}")
    print(f"[CONFIG] Min gap to trade: {MIN_GAP_TO_TRADE}")


# Call validation on import (fail early if config is broken)
try:
    validate_config()
except ValueError as e:
    print(f"[ERROR] Configuration validation failed:\n{e}")
    raise
