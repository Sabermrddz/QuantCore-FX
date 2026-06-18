import sys
import math
sys.path.insert(0, ".")

import pytest
from currency_strength_matrix import CurrencyStrengthMatrix, SessionTracker


def build_synthetic_z_scores(base_vals: dict, quote_vals: dict) -> dict:
    z_scores = {}
    currencies = list(base_vals.keys())
    for base in currencies:
        for quote in currencies:
            if base == quote:
                continue
            pair = f"{base}_{quote}"
            z_scores[pair] = base_vals[base] - quote_vals[quote]
    return z_scores


class TestCurrencyStrengthMatrix:
    def test_strongest_weakest_detection(self):
        base = {"EUR": 2.0, "USD": 1.0, "GBP": 0.5, "JPY": -1.0}
        quote = {"EUR": 0.0, "USD": 0.0, "GBP": 0.0, "JPY": 0.0}
        z = build_synthetic_z_scores(base, quote)
        matrix = CurrencyStrengthMatrix(z)
        assert matrix.get_strongest().name == "EUR"
        assert matrix.get_weakest().name == "JPY"

    def test_divergence_detected(self):
        base = {"EUR": 2.5, "USD": 0.0, "GBP": 0.0, "JPY": -2.5}
        quote = {"EUR": 0.0, "USD": 0.0, "GBP": 0.0, "JPY": 0.0}
        z = build_synthetic_z_scores(base, quote)
        matrix = CurrencyStrengthMatrix(z)
        assert matrix.has_divergence() is True
        assert matrix.get_matrix_cross() == "EUR_JPY"
        assert matrix.get_divergence_gap() == pytest.approx(5.0, abs=0.01)

    def test_no_divergence_within_threshold(self):
        base = {"EUR": 1.5, "USD": 0.0, "GBP": 0.0, "JPY": -1.5}
        quote = {"EUR": 0.0, "USD": 0.0, "GBP": 0.0, "JPY": 0.0}
        z = build_synthetic_z_scores(base, quote)
        matrix = CurrencyStrengthMatrix(z)
        assert matrix.has_divergence() is False

    def test_ranked_list_order(self):
        base = {"EUR": 3.0, "USD": 1.0, "GBP": 2.0, "JPY": 0.0}
        quote = {"EUR": 0.0, "USD": 0.0, "GBP": 0.0, "JPY": 0.0}
        z = build_synthetic_z_scores(base, quote)
        matrix = CurrencyStrengthMatrix(z)
        ranked = matrix.get_ranked_list()
        names = [c.name for c in ranked]
        assert names == ["EUR", "GBP", "USD", "JPY"]

    def test_sign_error_base_quote_inversion(self):
        base = {"EUR": 0.0, "USD": 0.0}
        quote = {"EUR": 0.0, "USD": 0.0}
        z = build_synthetic_z_scores(base, quote)
        z["EUR_USD"] = 2.0
        z["USD_EUR"] = -2.0
        matrix = CurrencyStrengthMatrix(z)
        s = matrix.get_strongest()
        w = matrix.get_weakest()
        assert s is not None and s.name == "EUR"
        assert w is not None and w.name == "USD"

    def test_get_report_structure(self):
        base = {"EUR": 2.0, "USD": 1.0, "GBP": 0.0, "JPY": -2.0}
        quote = {"EUR": 0.0, "USD": 0.0, "GBP": 0.0, "JPY": 0.0}
        z = build_synthetic_z_scores(base, quote)
        matrix = CurrencyStrengthMatrix(z)
        report = matrix.get_report()
        assert "ranked" in report
        assert "strongest" in report
        assert "weakest" in report
        assert "matrix_cross" in report
        assert "divergence_gap" in report
        assert "has_divergence" in report
        assert report["has_divergence"] is False


class TestSessionTracker:
    def test_active_session_returns_string(self):
        tracker = SessionTracker()
        session = tracker.get_active_session()
        assert session in ("Tokyo", "London", "New York", "Off-Hours")

    def test_check_new_session_snapshots_prices(self):
        tracker = SessionTracker()
        prices = {"EUR_USD": 1.08, "USD_JPY": 149.0}
        result = tracker.check_new_session(prices)
        assert result is not None or tracker.current_session is not None

    def test_compute_srv_zero_without_snapshot(self):
        tracker = SessionTracker()
        srv = tracker.compute_srv("EUR_USD", 1.09)
        assert srv == 0.0


class TestDivergenceGap:
    def test_gap_calculation(self):
        base = {"EUR": 3.0, "USD": 0.0, "JPY": -3.0, "GBP": 0.0}
        quote = {"EUR": 0.0, "USD": 0.0, "JPY": 0.0, "GBP": 0.0}
        z = build_synthetic_z_scores(base, quote)
        matrix = CurrencyStrengthMatrix(z)
        gap = matrix.get_divergence_gap()
        assert gap == pytest.approx(6.0, abs=0.01)
