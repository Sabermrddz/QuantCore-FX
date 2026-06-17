# APEX — Currency Strength Engine

> **Version:** 1.1.0  
> **Timeframe:** Swing / Position Trading (1–5 day holds)  
> **Architecture:** S.A.T.O.R.I. (Statistical Arbitrage Trading & Orchestrated Reversion Index)  
> **Layer:** Layer 1 (Fundamental) + Layer 2 (Technical/Statistical)  
> **Methodology:** Dr. Giavon's Deconstructed Currency Strength Indexing

---

## 1. Project Overview

APEX is a desktop-based **Currency Strength Engine** that implements institutional-quality **statistical arbitrage (StatArb)** for the forex market. It deconstructs all 28 major cross-pairs to isolate the true strength/weakness of individual currencies, then generates mean-reversion signals when statistical divergences reach extreme thresholds.

### Core Principle

Instead of analyzing EUR/USD as a single entity, APEX decomposes every pair to isolate individual currency strength indices:

```
Individual Currency Strength = Average Z-Score Across ALL 7 Pairs Involving That Currency

EUR_Strength = avg(Z(EUR_USD), Z(EUR_GBP), Z(EUR_JPY), Z(EUR_AUD), Z(EUR_CAD), Z(EUR_CHF), Z(EUR_NZD))
USD_Strength = avg(Z(USD_EUR), Z(USD_GBP), Z(USD_JPY), Z(USD_AUD), Z(USD_CAD), Z(USD_CHF), Z(USD_NZD))
... and so on for all 8 currencies
```

### Trading Philosophy

| Component | Strategy |
|-----------|----------|
| **Timeframe** | Swing / Position — 1 to 5 day holds |
| **Entry Trigger** | Matrix Cross divergence: one currency overbought (Z > +2.0) across ALL pairs, another oversold (Z < -2.0) simultaneously |
| **Execution** | Short the strongest, buy the weakest — bet on mathematical mean reversion |
| **Risk Management** | No single-pair stop losses. Basket hedging across correlated pairs + grid hedging |
| **Exit** | Aggregate portfolio P&L goes net positive (portfolio-based exit, not per-pair) |
| **Z-Score Anchor** | 288 M5 bars = 24 hours of historical data (not tick noise) |
| **Session Tracking** | Tracks Tokyo / London / New York opens with Session Relative Velocity |

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        APEX APPLICATION                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     UI LAYER (6 Tabs)                       │   │
│  │  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────┐  │   │
│  │  │Dashboard │ │Data    │ │Layer 2   │ │Confluence│ │Hist.│  │   │
│  │  │(Fundamen)│ │Entry   │ │Monitor   │ │Signals  │ │     │  │   │
│  │  └────┬─────┘ └────────┘ └────┬─────┘ └────┬────┘ └──────┘  │   │
│  └───────┼───────────────────────┼─────────────┼────────────────┘   │
│          │                       │             │                     │
│  ┌───────▼───────────────────────▼─────────────▼────────────────┐   │
│  │                     BUSINESS LOGIC LAYER                     │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐     │   │
│  │  │ Scoring (L1) │ │Technical (L2)│ │  Matrix Engine   │     │   │
│  │  │ scorer.py    │ │layer2_tech   │ │ currency_strength│     │   │
│  │  │              │ │  .py         │ │  _matrix.py      │     │   │
│  │  └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘     │   │
│  │         │                │                  │               │   │
│  │  ┌──────▼────────────────▼──────────────────▼──────────┐    │   │
│  │  │              CONFLUENCE FILTER                      │    │   │
│  │  │           confluence_filter.py                      │    │   │
│  │  │     Layer 1 + Layer 2 + Matrix = Entry Signal      │    │   │
│  │  └──────────────────────┬──────────────────────────────┘    │   │
│  │                         │                                    │   │
│  │  ┌──────────────────────▼──────────────────────────────┐    │   │
│  │  │           RISK MANAGEMENT SYSTEM                    │    │   │
│  │  │           risk_management.py                        │    │   │
│  │  │  Position Sizing + Grid Hedge + Basket Hedge +     │    │   │
│  │  │  Portfolio P&L Tracking + Aggregate Exit            │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     DATA LAYER                              │   │
│  │  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │   │
│  │  │ FRED API │ │ MT5 Data │ │ SQLite   │ │ Excel Import │  │   │
│  │  │(interest │ │(forex    │ │ Database │ │ (CPI/PMI)    │  │   │
│  │  │ rates)   │ │ prices)  │ │ apex.db  │ │              │  │   │
│  │  └───────────┘ └──────────┘ └──────────┘ └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### The Two Layers

| Layer | Input | Frequency | Output |
|-------|-------|-----------|--------|
| **Layer 1 (Fundamental)** | Interest rates (FRED), CPI, PMI (manual/Excel) | Monthly | Currency scores (0-100), Strongest/Weakest ranking |
| **Layer 2 (Technical)** | 288 M5 bars (24h) + live poll prices | Bar-anchored, tick-displayed | 28 pair Z-scores (anchored to 24h μ/σ), 8 currency strength indices, Matrix Cross |

**Critical design:** Z-scores are NOT calculated over raw tick polls. On connect, the analyzer is seeded with 288 M5 bars of historical close prices. μ and σ are computed from this 24-hour window. Live tick prices are compared against this stable anchor, producing meaningful multi-hour deviation readings that don't flip on every tick.

**Fallback:** If bar data hasn't been seeded yet, the system falls back to a 20-tick deque for immediate display. Once `seed_bars()` is called, the bar anchor takes over permanently.

---

## 3. Directory Structure

```
apex_layer1/
│
├── __init__.py                  # Package marker (v1.0.0)
├── main.py                      # Application entry point
├── main_window.py               # QMainWindow + tab assembly
├── config.py                    # All configuration & constants from .env
│
├── data_feeder.py               # MT5 + Mock data feeders
├── fred_client.py               # FRED interest rate API client
├── database.py                  # SQLite database manager
│
├── scorer.py                    # Layer 1 scoring engine
├── layer2_technical.py          # Layer 2 Z-score engine (28 pairs)
├── currency_strength_matrix.py  # S.A.T.O.R.I. currency strength index
├── confluence_filter.py         # Layer 1 + Layer 2 + Matrix merging
├── risk_management.py           # Position sizing, hedging, portfolio mgmt
│
├── create_excel_template.py     # Excel/CSV template generator
├── requirements.txt             # Python dependencies
│
├── .env                         # Live configuration (API keys)
├── .env.example                 # Configuration template
├── apex.db                      # SQLite database (auto-created)
│
├── ui/
│   ├── __init__.py
│   ├── dashboard_tab.py         # Tab 1: Layer 1 fundamental signals
│   ├── entry_tab.py             # Tab 2: CPI/PMI data entry
│   ├── layer2_monitor_tab.py    # Tab 3: Live Z-scores + Matrix
│   ├── confluence_tab.py        # Tab 4: Merged signals
│   ├── history_tab.py           # Tab 5: Past signals
│   └── settings_tab.py          # Tab 6: Configuration
```

---

## 4. File-by-File Breakdown

### 4.1 Entry Point

#### `main.py`
Launches the PyQt5 application. Validates FRED API key exists, creates `QApplication`, instantiates `MainWindow`, runs event loop.

- **`main()`** — Application entry point. Checks `config.FRED_API_KEY`, creates `QApplication`, shows `MainWindow`, starts event loop.

#### `__init__.py`
Package marker. Exports `__version__ = "1.0.0"`.

---

### 4.2 Configuration

#### `config.py`
Loads `.env` via `python-dotenv`. Defines ALL constants used across the application.

| Constant | Default | Description |
|----------|---------|-------------|
| `CURRENCIES` | `["USD","EUR","GBP","JPY","AUD","CAD","CHF","NZD"]` | The 8 major currencies |
| `CB_TARGETS` | Per-currency dict | Central bank inflation targets (2.0% most, AUD=2.5, CHF=1.5) |
| `FRED_SERIES` | Per-currency dict | FRED series IDs for interest rates |
| `WEIGHT_RATE` | `0.50` | Interest rate weight in L1 scoring |
| `WEIGHT_CPI` | `0.30` | CPI deviation weight in L1 scoring |
| `WEIGHT_PMI` | `0.20` | PMI composite weight in L1 scoring |
| `MIN_GAP_TO_TRADE` | `20` | Minimum score gap required for signal |
| `Z_SCORE_THRESHOLD` | `2.0` | Overbought/oversold threshold (std devs) |
| `Z_SCORE_LOOKBACK` | `20` | Bars for Z-score calculation |
| `MT5_SYMBOL_SUFFIX` | `""` | Broker-specific MT5 suffix (e.g., `.m`) |
| `ACCOUNT_BALANCE` | `10000` | Starting account balance |
| `RISK_PER_TRADE` | `0.01` | 1% risk per trade |
| `MAX_PORTFOLIO_LEVERAGE` | `2.0` | Max 2:1 leverage |
| `GRID_LEVELS` | `3` | Hedge grid levels |
| `USE_GRID_HEDGING` | `true` | Enable grid hedging |
| `DEBUG` | `false` | Debug output toggle |

- **`validate_config()`** — Validates all config on import. Raises `ValueError` if FRED key or critical settings are missing.

---

### 4.3 Data Layer

#### `data_feeder.py`
Two data feeder implementations with the **same interface** (polymorphic):

**Class `Mt5DataFeeder`** — Real data from MetaTrader 5 terminal.

| Method | Returns | Description |
|--------|---------|-------------|
| `initialize()` | `bool` | Connect to MT5 terminal |
| `test_connection()` | `bool` | Alias for initialize |
| `shutdown()` | — | Disconnect MT5 |
| `get_connection_status()` | `str` | Human-readable status |
| `get_current_price(pair)` | `dict\|None` | Bid/ask/mid via `symbol_info_tick()` |
| `fetch_all_rates()` | `dict` | Fetch 7 USD pairs, derive all 28 cross rates |
| `get_all_major_pairs()` | `list[str]` | All 28 pairs (56 permutations) |
| `get_exchange_rate(from, to)` | `float\|None` | Single cross rate |
| `get_historical_candles(...)` | `list[dict]\|None` | OHLC bars via `copy_rates_from_pos()` |
| `stream_prices(...)` | — | Threaded polling loop |
| `stop_streaming()` | — | Stop the poll loop |

**Strategy:** Fetches only 7 major USD pairs (`EUR_USD`, `GBP_USD`, `AUD_USD`, `NZD_USD`, `USD_JPY`, `USD_CAD`, `USD_CHF`), converts each to "how many USD per 1 unit", then derives all 28 cross rates mathematically. This avoids the problem that most MT5 brokers don't have symbols for exotic crosses like `AUDEUR`, `AUDGBP`, etc.

**Key internal:**
```python
USD_PAIRS = ["EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD",
             "USD_JPY", "USD_CAD", "USD_CHF"]

# For EUR_USD: usd_rates["EUR"] = mid_price
# For USD_JPY: usd_rates["JPY"] = 1.0 / mid_price
# Cross rate: rate[base][quote] = usd_rates[base] / usd_rates[quote]
```

**Class `MockDataFeeder`** — Simulates prices with random walk around base prices for 8 major pairs. Same interface as `Mt5DataFeeder` for testability.

---

#### `fred_client.py`
**Class `FredClient`** — Fetches interest rates from FRED API.

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(api_key, timeout)` | — | Validates API key |
| `fetch_rate(currency, max_retries)` | `float\|None` | Single currency rate with exponential backoff |
| `fetch_all_rates(max_retries)` | `dict` | All 8 currencies |
| `get_cached_rate(currency)` | `float\|None` | Cache lookup |
| `clear_cache()` | — | Reset cache |

Uses FRED series IDs from `config.FRED_SERIES`:
- USD → `FEDFUNDS`, EUR → `ECBDFR`, GBP → `BOEBR`, JPY → `IRSTJPN`
- AUD → `RBATCTR`, CAD → `BOCCRT`, CHF → `SNBPOL`, NZD → `RBNZOCR`

---

#### `database.py`
**Class `Database`** — SQLite database with 4 tables.

| Table | Columns | Purpose |
|-------|---------|---------|
| `rates` | `currency, rate, updated_at, source` | Interest rates from FRED |
| `monthly_data` | `month, currency, cpi_actual, pmi_actual, entered_at` | CPI/PMI entries |
| `scores` | `month, currency, score_rate, score_cpi, score_pmi, total_score, rank` | Calculated scores |
| `signals` | `month, strongest, weakest, gap, signal, status` | Trade signals |

All tables use `ON CONFLICT ... DO UPDATE` (upsert) for idempotent writes. Foreign keys enforced via PRAGMA.

Key methods: `upsert_rate()`, `update_monthly_cpi()`, `update_monthly_pmi()`, `save_scores()`, `save_signal()`, `get_month_scores()`, `get_all_signals()`, `get_month_completeness()`.

---

### 4.4 Business Logic — Layer 1 (Fundamental)

#### `scorer.py`
Pure functions (no classes). Implements the scoring formula:

```
Score = (Rate_Differential × 50%) + (CPI_Deviation × 30%) + (PMI × 20%)

Each component is min-max normalized to 0-100 before weighting.
```

| Function | Returns | Description |
|----------|---------|-------------|
| `normalise(values)` | `list[float]` | Min-max scaling to 0-100 |
| `calculate_rate_differentials(rates)` | `dict` | Rate minus G8 average |
| `calculate_cpi_deviations(cpi_values)` | `dict` | Actual CPI minus CB target |
| `score_all_currencies(rates, cpi, pmi)` | `dict` | Full scoring pipeline |
| `get_ranked_list(scores)` | `list[tuples]` | Sorted by score descending |
| `pair_currencies(scores)` | `(strongest, weakest, gap)` | Top vs bottom score |
| `generate_signal(scores)` | `(signal, status, gap_desc)` | "SHORT X/Y" or "NO TRADE" |
| `validate_scores(scores)` | `bool` | Validates all fields and ranges |

---

### 4.5 Business Logic — Layer 2 (Technical)

#### `layer2_technical.py`
**Class `TechnicalAnalyzer`** — Real-time Z-score engine.

Initializes 56 deques (all permutations of 8 currencies) with `maxlen=20`. Each incoming price tick appends to the deque and recalculates the Z-score.

| Method | Description |
|--------|-------------|
| `add_price_data(pair, price, volume)` | Append price, recalculate Z-score |
| `get_z_score(pair)` | Current Z-score for any pair |
| `is_extreme(pair)` | `|Z| >= 2.0` |
| `get_overbought_pairs()` | All pairs with Z >= 2.0 |
| `get_oversold_pairs()` | All pairs with Z <= -2.0 |
| `get_volatility(pair)` | Standard deviation of recent prices |
| `get_mean_price(pair)` | Mean price over lookback |
| `is_mean_reverting(pair)` | `|Z| < 0.5` |
| `get_last_price(pair)` | Most recent price |
| `get_all_z_scores()` | Dict of all 56 pair Z-scores |
| `get_status_for_pair(pair)` | Dict with label (SEVERELY OVERBOUGHT → Neutral) |

**Z-score formula:** `Z = (current_price - mean) / std_dev`

**Class `TechnicalSignal`** — Signal generation from Z-scores.
- `should_enter_on_extreme()` → True if `|Z| >= 2.0`
- `should_exit_on_mean_reversion()` → True if `|Z| < 0.5`
- `get_signal_strength()` → 0-100 scale

---

#### `currency_strength_matrix.py`
**Class `CurrencyStrengthMatrix`** — S.A.T.O.R.I. individual currency strength index.

This is the core mathematical innovation. Deconstructs all 28 pair Z-scores into 8 individual currency strength indices.

**How it works:**

For each currency, collects Z-scores from all 7 pairs where it is the **base**:
```
EUR_Strength = avg(Z(EUR_USD), Z(EUR_GBP), Z(EUR_JPY), Z(EUR_AUD), Z(EUR_CAD), Z(EUR_CHF), Z(EUR_NZD))
USD_Strength = avg(Z(USD_EUR), Z(USD_GBP), Z(USD_JPY), Z(USD_AUD), Z(USD_CAD), Z(USD_CHF), Z(USD_NZD))
```

**Output:**
| Currency | Avg Z-Score | Direction |
|----------|-------------|-----------|
| EUR | +2.3 | **OVERBOUGHT** |
| USD | +1.1 | NEUTRAL |
| ... | ... | ... |
| JPY | -2.5 | **OVERSOLD** |

The **Matrix Cross** = Strongest currency vs Weakest currency (e.g., `EUR_JPY`).

| Method | Description |
|--------|-------------|
| `update(z_scores)` | Recompute from 56 pair Z-scores |
| `get_strongest()` | Highest avg Z-score currency |
| `get_weakest()` | Lowest avg Z-score currency |
| `get_matrix_cross()` | Strongest_Weakest pair |
| `get_divergence_gap()` | strongest_z - weakest_z |
| `has_divergence()` | True if one overbought AND one oversold |
| `get_strong_currencies()` | List of overbought currencies |
| `get_weak_currencies()` | List of oversold currencies |
| `get_ranked_list()` | All 8 sorted by strength |
| `get_report()` | Dict with all matrix data |

---

#### `confluence_filter.py`
**Class `ConfluenceFilter`** — Merges all three signal sources.

**Entry logic** (two-tier):

1. **Primary — Matrix Divergence:**
   - One currency overbought across ALL pairs
   - Another currency oversold across ALL pairs
   - Trade the Matrix Cross (strongest vs weakest)
   - Confidence = spread / 4.0 × 100

2. **Secondary — Layer 1 + Layer 2:**
   - Layer 1 bias (fundamental strongest/weakest)
   - Layer 2 pair extreme (|Z| >= 2.0 on that specific pair)
   - 50% gap confidence + 50% Z confidence

**Exit logic** (two-tier):
1. Matrix divergence gap collapses (divergence no longer exists)
2. Single-pair Z-score mean reverts below 0.5

| Method | Description |
|--------|-------------|
| `set_layer1_bias(strongest, weakest, gap)` | Store current L1 signal |
| `check_entry_confluence()` | `(bool, reason, strength)` |
| `check_exit_confluence()` | `(bool, reason)` |
| `is_conflicting()` | L1 bullish but L2 bearish |
| `get_confluence_report()` | Full report with matrix data |
| `get_all_signals()` | All ranked signals |

**Class `SignalHistory`** — Tracks up to 1000 signals with win-rate calculation.

---

#### `risk_management.py`
Five classes implementing professional risk management:

**Class `PositionSizer`**
- Risk-based position sizing: `size = (balance × 0.01) / (stop_loss × pip_value) × confidence_multiplier`
- Clamped to 0.01–5.0 lots

**Class `GridHedging`**
- Creates N-level hedge grid below entry price
- Each hedge level = 50% × position_size / (N-1)

**Class `PortfolioExposure`**
- Tracks all open positions
- Enforces max leverage (default 2:1)
- Rejects new positions that would exceed limit

**Class `BasketHedging`** — S.A.T.O.R.I. statistical arbitrage hedging.
- Pre-defined correlation clusters:
  - `EUR_USD` → hedges with `EUR_GBP`, `EUR_JPY`, `GBP_USD`
  - `GBP_USD` → hedges with `GBP_JPY`, `EUR_GBP`, `EUR_USD`
  - `USD_JPY` → hedges with `USD_CHF`, `USD_CAD`, `EUR_JPY`
  - `AUD_USD` → hedges with `AUD_JPY`, `NZD_USD`, `AUD_CAD`
  - `NZD_USD` → hedges with `AUD_USD`, `NZD_JPY`, `NZD_CAD`
- Each correlated pair gets 30% of primary size / len(cluster)

**Class `RiskManagementSystem`** — Combines all four.
- `execute_signal()` → full trade execution with sizing + grid + basket
- `calculate_basket_pnl()` → aggregate unrealized P&L across ALL positions + hedges
- `should_exit_portfolio()` → exit when total P&L > 0 (portfolio-based, not per-pair)
- `close_all_trades()` → close all positions at given exit prices
- `get_portfolio_summary()` → positions, exposure, leverage, P&L

---

### 4.6 UI Layer

#### `main_window.py`
**Class `MainWindow(QMainWindow)`** — Application shell.

Creates 6-tab `QTabWidget`, instantiates all tabs, connects inter-tab signals.

**Data flow assembly:**
```
1. Entry tab saves data → Dashboard refreshes
2. Entry tab saves data → History tab refreshes
3. Dashboard generates signal → Confluence tab receives bias
4. Dashboard requests fetch → FredFetchWorker starts
5. FRED completes → Dashboard updates rates
```

**Class `FredFetchWorker(QThread)`** — Background FRED API fetch. Saves rates to DB, emits `rates_fetched` or `error_occurred`.

---

#### `ui/dashboard_tab.py` — Tab 1
**Class `DashboardTab(QWidget)`**

Displays Layer 1 fundamental analysis:
- **Signal card** — Large text: "SHORT JPY/USD" or "NO TRADE", gap score, tier, timestamp
- **Score table** — 8 rows × 8 columns (Rank, Currency🇺🇸, Rate%, CPI%, PMI, Score, Signal, Strength bar)
- Strongest row highlighted green with "BUY" tag
- Weakest row highlighted red with "SELL" tag
- Color-coded score bars (green/red/gray for Rate/CPI/PMI contributions)
- "Fetch Rates (FRED)" button

Signals: `fetch_rates_requested`, `signal_generated(strongest, weakest, gap)`

---

#### `ui/entry_tab.py` — Tab 2
**Class `MonthlyEntryTab(QWidget)`**

Manual data entry for CPI and PMI:
- Month selector (dropdown, 24 months)
- **CPI table**: Currency, Target%, Actual CPI (spinbox), Delta (color-coded), Done
- **PMI table**: Currency, Neutral 50, PMI (spinbox), Signal label (Expanding/Contracting), Done
- Progress bar: X/16 fields filled
- Import Excel button (supports both multi-sheet xlsx and CSV)
- Save button (enabled only when 16/16 complete)
- On save: loads rates from DB → runs `scorer.score_all_currencies()` → saves scores → generates signal → emits `data_saved`

Signals: `data_saved(month)`

---

#### `ui/layer2_monitor_tab.py` — Tab 3
**Class `Layer2MonitorTab(QWidget)`**
**Class `DataStreamerThread(QThread)`**

Real-time technical analysis with S.A.T.O.R.I. matrix:
- **Connection panel**: Source dropdown (MT5 Live / Mock Test), Connect/Disconnect, status indicator
- **Z-score table**: All 28 pairs with Price, Z-Score (red when extreme), Volatility, Mean, Status, Signal
- **Overbought/Oversold alerts**: Comma-separated lists
- **Currency Strength Matrix panel:**
  - Matrix Cross label (strongest vs weakest currency)
  - Divergence Gap (sigma spread)
  - DIVERGENCE DETECTED alert (red) when one currency overbought + one oversold
  - Ranked currency table: 8 rows × 4 columns (Rank, Currency, Strength Z, Direction)
  - Color-coded: OVERBOUGHT (red), OVERSOLD (green)
- Auto-refresh checkbox, Refresh Now button

Data flow: Streamer thread polls feeder → emits `price_updated` → feeds `TechnicalAnalyzer` → recomputes `CurrencyStrengthMatrix` → refreshes display.

---

#### `ui/confluence_tab.py` — Tab 4
**Class `ConfluenceSignalsTab(QWidget)`**

Merged signal display and execution:
- **Status card**: Layer 1 bias (pair, gap), Layer 2 extreme (pair, Z-score), Matrix Cross, Top 3 → Bottom 3 ranked currencies, Confluence result with confidence %
- **Signals table**: 10 rows × 8 columns (Pair, L1 Gap, L2 Z-Score, Status, Confidence, Entry Price, Position Size, Action)
- Matrix divergence signals shown in purple, standard confluence in green
- **Risk panel**: Portfolio exposure progress bar, leverage ratio
- **Buttons**: Refresh, Execute Top Signal (runs `RiskManagementSystem`)
- Auto-refresh every 5 seconds

---

#### `ui/history_tab.py` — Tab 5
**Class `HistoryTab(QWidget)`**

Past signal history:
- Table with 6 columns: Month, Signal, Gap, Strongest (flag), Weakest (flag), Status
- Status color-coded: ACTIVE (green), NO_TRADE (red)
- Click any row → popup with full score breakdown for all 8 currencies
- Auto-refreshes when new data saved

---

#### `ui/settings_tab.py` — Tab 6
**Class `SettingsTab(QWidget)`**
**Class `FredTestWorker(QThread)`**
**Class `Mt5TestWorker(QThread)`**

Configuration interface:
- **FRED API**: Key input (masked), Test Connection button, status
- **MT5**: Symbol suffix input, Test Connection button, status
- **CB Targets**: Read-only display of all 8 targets
- **Scoring Weights**: 3 spinboxes (Rate/CPI/PMI %) with live total validation (must = 100%)
- **Trading Rules**: Minimum gap spinbox (5-100)
- **App Settings**: Auto-fetch checkbox
- **Save**: Writes .env file (requires restart)
- **Reset**: Confirmation dialog, restores defaults

---

### 4.7 Utility

#### `create_excel_template.py`
Generates example Excel/CSV files for data import testing:
- `example_monthly_data.xlsx` (multi-sheet: CPI + PMI)
- `example_monthly_data_single_sheet.xlsx` (all in one sheet)
- `example_monthly_data.csv`

Each contains 8 currencies with example values.

---

## 5. Data Flow Diagrams

### Layer 1 (Fundamental) — Monthly Cycle

```
User enters CPI/PMI
       │
       ▼
Entry Tab → Save Clicked
       │
       ├──► Read all 8 CPI + 8 PMI from spinboxes
       ├──► Load interest rates from DB (from FRED)
       ├──► scorer.score_all_currencies(rates, cpi, pmi)
       │      ├── normalise(rate_differentials) × 0.50
       │      ├── normalise(cpi_deviations) × 0.30
       │      ├── normalise(pmi_raw) × 0.20
       │      └── sum → total_score 0-100
       ├──► scorer.generate_signal(scores)
       │      ├── pair_currencies → strongest, weakest, gap
       │      ├── gap >= 20 → "SHORT {weak}/{strong}"
       │      └── gap < 20 → "NO TRADE"
       ├──► database.save_scores()
       ├──► database.save_signal()
       └──► emit data_saved → Dashboard + History refresh
```

### Layer 2 (Technical) — Real-time with Bar Seeding

```
MT5 Terminal (or Mock)
       │
       ├── On Connect:
       │   generate_mock_bars(288)            ◄── Mock: simulates 24h of M5 data
       │   │     or
       │   fetch_historical_bars(288, M5)      ◄── MT5: real bars from terminal
       │   │
       │   ▼
       │   TechnicalAnalyzer.seed_bars(bars)   ◄── Populates bar_history with 288 closes
       │   │                                   ◄── μ and σ now anchored to 24h
       │   │
       │   ▼
       │   DataStreamerThread.start()
       │
       └──► every 1s:
            fetch_all_rates() → 7 USD pairs → derive 28 crosses
            │
            ├──► emit price_updated(pair, mid)
            │
            ▼
            Layer2MonitorTab._on_price_received
            │
            ├──► TechnicalAnalyzer.add_price_data(pair, price)
            │      └── _update_z_score(pair)
            │             μ, σ = _get_mean_std(pair)
            │             │  priority: bar_history (288 bars) → tick_fallback (20 ticks)
            │             ▼
            │             Z = (current_price - μ) / σ
            │
            ├──► CurrencyStrengthMatrix(z_scores)
            │      └── For each currency: avg Z across 7 base pairs
            │
            └──► _refresh_display()
                   ├── Update 28-pair Z-score table
                   ├── Update currency strength matrix table
                   ├── Update matrix cross / divergence alerts
                   ├── Update overbought/oversold lists
                   └── Show active session (Tokyo/London/New York)
```

### Confluence — Entry Signal

```
Layer 1 (monthly)                 Layer 2 (real-time)
     │                                  │
     ▼                                  ▼
dashboard_tab.signal_generated     ThermalAnalyzer.z_scores
     │                                  │
     ▼                                  ▼
ConfluenceFilter.set_layer1_bias    CurrencyStrengthMatrix
     │                                  │
     └──────────┬───────────────────────┘
                ▼
     ConfluenceFilter.check_entry_confluence()
                │
                ├── Matrix divergence? → YES → Trade matrix cross
                ├── L1 + L2 extreme? → YES → Trade paired pair
                └── Neither? → NO TRADE
                │
                ▼
     RiskManagementSystem.execute_signal()
                │
                ├── PositionSizer → size = f(confidence)
                ├── GridHedging → 3-level hedge grid
                ├── BasketHedging → correlated pair hedges
                └── PortfolioExposure → leverage check
```

---

## 6. Database Schema

```sql
-- Table 1: Interest rates from FRED
CREATE TABLE rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL UNIQUE,
    rate REAL NOT NULL,
    updated_at TEXT NOT NULL,
    source TEXT DEFAULT 'FRED',
    CONSTRAINT valid_currency CHECK (currency IN ('USD','EUR','GBP','JPY','AUD','CAD','CHF','NZD'))
);

-- Table 2: Monthly CPI + PMI entries
CREATE TABLE monthly_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    currency TEXT NOT NULL,
    cpi_actual REAL,
    pmi_actual REAL,
    entered_at TEXT NOT NULL,
    UNIQUE(month, currency),
    CONSTRAINT valid_currency CHECK (currency IN ('USD','EUR','GBP','JPY','AUD','CAD','CHF','NZD')),
    CONSTRAINT valid_month CHECK (month LIKE '____-__')
);

-- Table 3: Calculated scores
CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    currency TEXT NOT NULL,
    score_rate REAL,
    score_cpi REAL,
    score_pmi REAL,
    total_score REAL NOT NULL,
    rank INTEGER NOT NULL,
    calculated_at TEXT NOT NULL,
    UNIQUE(month, currency)
);

-- Table 4: Trade signals
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    month TEXT NOT NULL UNIQUE,
    strongest TEXT NOT NULL,
    weakest TEXT NOT NULL,
    gap REAL NOT NULL,
    signal TEXT NOT NULL,
    status TEXT NOT NULL,
    CONSTRAINT valid_status CHECK (status IN ('ACTIVE', 'NO_TRADE', 'CLOSED'))
);
```

---

## 7. Configuration (.env)

```env
FRED_API_KEY=your_fred_api_key
MT5_SYMBOL_SUFFIX=
DB_PATH=apex.db
DEBUG=true
WEIGHT_RATE=0.50
WEIGHT_CPI=0.30
WEIGHT_PMI=0.20
MIN_GAP=20.0
AUTO_FETCH_RATES_ON_STARTUP=true
Z_SCORE_THRESHOLD=2.0
Z_SCORE_LOOKBACK=20
ACCOUNT_BALANCE=10000.0
RISK_PER_TRADE=0.01
MAX_PORTFOLIO_LEVERAGE=2.0
USE_GRID_HEDGING=true
GRID_LEVELS=3
```

---

## 8. Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.10+ |
| UI Framework | PyQt5 | 5.15.9 |
| Database | SQLite | Built-in |
| HTTP Client | requests | 2.31+ |
| Data Processing | pandas | 2.1+ |
| Excel Support | openpyxl | 3.1+ |
| Environment | python-dotenv | 1.0+ |
| Forex Data | MetaTrader5 | Latest |
| Interest Rates | FRED API | Free tier |
| Packaging | PyInstaller | 6.1+ |

---

## 9. Scoring Formula Reference

### Layer 1 — Fundamental Score

```
rate_diff[i]    = rate[i] - G8_average_rate
cpi_dev[i]      = actual_cpi[i] - cb_target[i]
pmi_raw[i]      = pmi_value[i]

normalize(x)    = (x - min) / (max - min) × 100    // 0-100 scale

score_total[i]  = normalise(rate_diff)[i] × 0.50
                + normalise(cpi_dev)[i] × 0.30
                + normalise(pmi_raw)[i] × 0.20

gap             = score_total[strongest] - score_total[weakest]
```

### Layer 2 — Technical Score (Bar-Anchored)

```
Step 1: Seed bar_history with 288 M5 close prices (24 hours)
Step 2: μ_bars = mean(bar_history), σ_bars = stdev(bar_history)
Step 3: For each incoming tick:

    Z[pair] = (current_tick_price - μ_bars) / σ_bars

    Fallback (if bar_history empty):
    Z[pair] = (current_tick_price - mean(ticks)) / stdev(ticks)

Step 4: Individual Currency Strength = avg(Z[currency_X] over all 7 base pairs)

Step 5: Session Relative Velocity (SRV):
    At session open (Tokyo/London/NY), snapshot all prices.
    SRV[pair] = ((current_price - session_open_price) / session_open_price) × 100
```

### Entry Conditions

```
Matrix Divergence:  any(avg_Z > +2.0) AND any(avg_Z < -2.0)  → Trade Matrix Cross
Pair Confluence:    L1_gap >= 20 AND L2_Z >= 2.0 on same pair → Trade that pair
```

---

## 10. 28 Currency Pairs (Generated)

All 8 currencies produce 56 permutations (28 pairs × 2 directions):

| Base | Pairs (base_quote) |
|------|--------------------|
| USD | USD_EUR, USD_GBP, USD_JPY, USD_AUD, USD_CAD, USD_CHF, USD_NZD |
| EUR | EUR_USD, EUR_GBP, EUR_JPY, EUR_AUD, EUR_CAD, EUR_CHF, EUR_NZD |
| GBP | GBP_USD, GBP_EUR, GBP_JPY, GBP_AUD, GBP_CAD, GBP_CHF, GBP_NZD |
| JPY | JPY_USD, JPY_EUR, JPY_GBP, JPY_AUD, JPY_CAD, JPY_CHF, JPY_NZD |
| AUD | AUD_USD, AUD_EUR, AUD_GBP, AUD_JPY, AUD_CAD, AUD_CHF, AUD_NZD |
| CAD | CAD_USD, CAD_EUR, CAD_GBP, CAD_JPY, CAD_AUD, CAD_CHF, CAD_NZD |
| CHF | CHF_USD, CHF_EUR, CHF_GBP, CHF_JPY, CHF_AUD, CHF_CAD, CHF_NZD |
| NZD | NZD_USD, NZD_EUR, NZD_GBP, NZD_JPY, NZD_AUD, NZD_CAD, NZD_CHF |

Each currency's individual strength is computed from its 7 base pairs.

---

## 11. Refactoring Changelog (Session-Based Quantitative Engine)

### Task 1.1 — Statistical Lookback Window (config.py, layer2_technical.py)
- `config.py`: Added `BAR_TIMEFRAME`, `BAR_LOOKBACK_HOURS`, `BAR_LOOKBACK_BARS`, `HISTORICAL_POLL_INTERVAL` constants. Default lookback changed from 20 ticks to 288 bars (24h of M5 data).
- `layer2_technical.py`: `TechnicalAnalyzer` now maintains **two data streams**:
  - `bar_history` (deque of M1/M5 close prices, length = `BAR_LOOKBACK_BARS`) — the multi-hour statistical anchor
  - `price_history` (short deque of tick/poll data) — for UI display
  - `_get_bar_mean_std()` computes μ/σ from bar history only
  - `_update_z_score()` uses `Z = (current_tick - μ_bars) / σ_bars`
  - `add_bar()` method for feeding completed M1/M5 candles into the historical frame

### Task 1.2 — Session-Based Indexing (currency_strength_matrix.py)
- New `SessionTracker` class:
  - Detects active session from UTC hour (Tokyo 00-08, London 07-16, New York 13-22)
  - On session open, snapshots start prices for all 28 pairs
  - Computes **Session Relative Velocity (SRV)**: `% change = (current - session_start) / session_start × 100`
- `CurrencyStrengthMatrix.update()` now accepts `current_prices` dict for session tracking
- `CurrencyStrength` dataclass has new `session_srv: float` field
- `get_report()` includes `active_session` key

### Task 2.1 — Live Order Book Subscriptions (data_feeder.py)
- `Mt5DataFeeder.get_order_book(pair)` — fetches live bid/ask/spread via `mt5.symbol_info_tick()` + `mt5.symbol_info()` for the exact trade symbol
- `PositionSizer.calculate_position_size()` accepts optional `bid`, `ask`, `spread` params; wide spreads reduce position size by up to 20%
- `MockDataFeeder` has matching `get_order_book()` implementation

### Task 2.2 — SQLite WAL Mode + Bar Cache (database.py)
- Connection now sets: `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL` for concurrent read/write performance
- New `bar_cache` table: `(id, pair, timeframe, bar_time, open, high, low, close, volume)` with unique constraint on `(pair, timeframe, bar_time)` and compound index
- New methods: `upsert_bar()`, `get_bars()`, `get_latest_bar_time()`

### Task 3.1 — Layer 1 as Directional Regime Filter (confluence_filter.py)
- `check_entry_confluence()` now uses Layer 1 as a **Directional Regime Filter**:
  - Primary signal: Matrix divergence (self-sufficient)
  - Secondary: Layer 2 extremes only valid if **aligned** with Layer 1 macro bias
  - Contrarian Layer 2 signals (Z < -threshold opposite Layer 1 direction) → **BLOCKED** with reason
  - Aligned signals capped at 70% confidence (downgraded vs matrix divergence)
- `layer1_is_active` flag replaces raw gap comparison

### Task 3.2 — Dynamic Pearson Correlation (risk_management.py, data_feeder.py)
- New `pearson_correlation(x, y)` function: `r = Σ(x-x̄)(y-ȳ) / √(Σ(x-x̄)² · Σ(y-ȳ)²)`
- New `CorrelationEngine` class:
  - `update_series(historical_closes)` — feeds 30 days of close prices
  - `get_correlation(pair_a, pair_b)` — computes/caches r between any two pairs
  - `get_top_correlated(target, n=3, min_r=0.75)` — returns top N pairs with |r| ≥ 0.75
- `BasketHedging.get_correlated_pairs()` now delegates to `CorrelationEngine` instead of hardcoded dict
- `Mt5DataFeeder.fetch_historical_closes_all_pairs(days=30)` fetches the required data
- `MockDataFeeder` has matching implementation

### Task 3.3 — Aggregate Portfolio Profit Target Exit (risk_management.py)
- `get_dynamic_exit_target()` — confidence-scaled profit target (base = 1% of equity, scales with avg confidence)
- Background monitor thread `_monitor_exit_loop()` polls `calculate_basket_pnl()` every second
- When net aggregate P&L > dynamic target, fires `close_all_trades()` via registered callbacks
- `start_exit_monitor()`, `stop_exit_monitor()`, `on_portfolio_exit()` lifecycle management

### Task 4.1 — Session Visualizations + σ Highlights (ui/layer2_monitor_tab.py)
- Active session indicator label with color-coded background: Tokyo (purple), London (blue), New York (orange), Off-Hours (gray)
- Currency Strength Matrix Z-score cells: solid red background with white text for ≥ +2.0σ, solid green with white text for ≤ -2.0σ
- New 5th column in matrix table: "Session SRV" showing percentage change since session open
- Emoji indicators removed from status labels for cleaner display

---

## 12. Bug Fixes & Stability (Round 2)

### Fix 1 — Bar History Never Seeded (Z-scores always 0.0)
- `layer2_technical.py`: Added `seed_bars(historical_bars)` method to populate `bar_history` with 288 M5 close prices on connect
- `data_feeder.py (Mock)`: Added `generate_mock_bars(n_bars=288)` — generates 24h of simulated M5 data using an Ornstein-Uhlenbeck process (mean reversion + drift + noise) for all 28 pairs via USD pair derivation
- `ui/layer2_monitor_tab.py`: `_connect()` calls `_seed_historical_bars()` before starting the streamer — bars are always seeded first

### Fix 2 — Tick Price Anchored to Initial Base, Not Bar Data
- `data_feeder.py (Mock)`: `_tick_price()` now uses the **last bar close** as its anchor with ±0.0002 noise, instead of the initial base price with ±0.01 noise
- `_current_bar_prices()` returns the last cached bar close for each pair
- This ensures Z-scores reflect the bar position relative to 24h history, not random tick noise

### Fix 3 — Default Source Changed to Mock
- `ui/layer2_monitor_tab.py`: `source_combo` defaults to `"Mock (Test)"` at index 0 to prevent unintended MT5 terminal connections on startup

### Fix 4 — Persistent Matrix Instance
- `ui/layer2_monitor_tab.py`: `CurrencyStrengthMatrix` is now a persistent `self.matrix` instance, recreated only once. `update()` is called each refresh instead of creating a new object, preserving `SessionTracker` state across refreshes

### Fix 5 — FRED Series IDs Updated
- `config.py`: Updated 6 invalid/deprecated FRED series IDs (`BOEBR`, `IRSTJPN`, `RBATCTR`, `BOCCRT`, `SNBPOL`, `RBNZOCR`) to commonly used alternatives (`BOEIR`, `IRSTCI01JPM156N`, `RBATR`, `BOCARR`, `SNBON`, `RBNZR`)
