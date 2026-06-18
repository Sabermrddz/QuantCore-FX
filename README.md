# APEX — Currency Strength Engine (QuantCore FX)

Desktop-based **Currency Strength Engine** implementing institutional-quality **statistical arbitrage (StatArb)** for the forex market across 8 major currencies and 56 directional pairs.

## Architecture

Full documentation: [`project_structure_and_resume.md`](project_structure_and_resume.md)

### Layers
- **Layer 1 (Fundamental)** — Interest rates (FRED), CPI, PMI → currency scores 0–100
- **Layer 2 (Technical)** — Bar-anchored Z-scores (288 M5 bars = 24h) across all 28 pairs → S.A.T.O.R.I. currency strength matrix

### Quick Start
```bash
pip install -r requirements.txt
cp .env.example .env  # add your FRED_API_KEY
python main.py
```

> **Warning:** This system generates trading signals for educational/paper-trading use. Live execution (Phase 4) defaults to **disabled**. See rebuild plan for details.
