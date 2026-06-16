"""
APEX Layer 1 — Scoring Engine

Implements the exact scoring formula from the README:
1. Collect raw values (rates, CPI deviations, PMI)
2. Calculate derived values
3. Normalize each input to 0-100 using min-max scaling
4. Apply weights (Rate 50%, CPI 30%, PMI 20%)
5. Sum to get final score
6. Rank currencies and pair strongest vs weakest
7. Validate gap >= MIN_GAP to trade

All scores are 0-100. Gap must be >= 20 to generate a trade signal.
"""

from typing import Dict, List, Tuple, Optional
import config


def normalise(values: List[float]) -> List[float]:
    """
    Normalize a list of values to 0-100 using min-max scaling.
    
    If all values are equal (no variation), return [50.0] * len(values)
    to represent perfect neutrality.
    
    Args:
        values: List of numeric values
        
    Returns:
        List of normalized values (0.0 to 100.0)
    """
    if not values:
        return []
    
    min_v = min(values)
    max_v = max(values)
    
    # Handle edge case: all values identical
    if max_v == min_v:
        return [50.0] * len(values)
    
    # Min-max scaling to [0, 100]
    return [(v - min_v) / (max_v - min_v) * 100.0 for v in values]


def calculate_rate_differentials(rates: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    """
    Calculate interest rate differential for each currency vs G8 average.
    
    rate_diff[i] = rate[i] - mean(rate)
    
    Args:
        rates: Dict mapping currency to interest rate (% or None)
        
    Returns:
        Dict mapping currency to rate differential
    """
    # Filter out None values for average calculation
    valid_rates = [r for r in rates.values() if r is not None]
    
    if not valid_rates:
        # All rates missing — return zeros
        return {currency: 0.0 for currency in config.CURRENCIES}
    
    avg_rate = sum(valid_rates) / len(valid_rates)
    
    # Calculate differentials (None becomes 0.0)
    differentials = {}
    for currency in config.CURRENCIES:
        rate = rates.get(currency)
        differentials[currency] = (rate - avg_rate) if rate is not None else 0.0
    
    return differentials


def calculate_cpi_deviations(cpi_values: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    """
    Calculate CPI deviation for each currency vs its CB target.
    
    cpi_dev[i] = actual_cpi[i] - target[i]
    
    - Positive deviation (above target) → hawkish pressure (stronger score)
    - Negative deviation (below target) → dovish pressure (weaker score)
    
    Args:
        cpi_values: Dict mapping currency to actual CPI % (or None)
        
    Returns:
        Dict mapping currency to CPI deviation
    """
    deviations = {}
    for currency in config.CURRENCIES:
        cpi = cpi_values.get(currency)
        target = config.CB_TARGETS.get(currency, 2.0)
        
        # None becomes 0.0 deviation (neutral)
        deviations[currency] = (cpi - target) if cpi is not None else 0.0
    
    return deviations


def score_all_currencies(
    rates: Dict[str, Optional[float]],
    cpi_values: Dict[str, Optional[float]],
    pmi_values: Dict[str, Optional[float]]
) -> Dict[str, Dict]:
    """
    Calculate the complete score for all 8 currencies.
    
    Steps:
    1. Calculate rate differentials
    2. Calculate CPI deviations
    3. Normalize each input to 0-100
    4. Apply weights
    5. Sum to get total score
    6. Rank by score
    
    Args:
        rates: Dict currency -> interest rate % (or None)
        cpi_values: Dict currency -> actual CPI % (or None)
        pmi_values: Dict currency -> PMI reading (or None)
        
    Returns:
        Dict mapping currency to:
        {
            'score_rate': float (0-100),
            'score_cpi': float (0-100),
            'score_pmi': float (0-100),
            'total_score': float (0-100),
            'rank': int (1-8)
        }
    """
    # Step 1 & 2: Calculate derived values
    rate_diffs = calculate_rate_differentials(rates)
    cpi_devs = calculate_cpi_deviations(cpi_values)
    pmi_raws = pmi_values.copy()  # Use PMI values as-is
    
    # Extract numeric lists for normalization (skip None values)
    rate_diff_list = [rate_diffs[c] for c in config.CURRENCIES]
    cpi_dev_list = [cpi_devs[c] for c in config.CURRENCIES]
    
    # For PMI, treat None as 50 (neutral) for normalization purposes
    pmi_list = [pmi_raws.get(c) if pmi_raws.get(c) is not None else 50.0 for c in config.CURRENCIES]
    
    # Step 3: Normalize each input to 0-100
    norm_rate = normalise(rate_diff_list)
    norm_cpi = normalise(cpi_dev_list)
    norm_pmi = normalise(pmi_list)
    
    # Step 4 & 5: Apply weights and calculate total scores
    scores_raw = {}
    for i, currency in enumerate(config.CURRENCIES):
        total = (
            norm_rate[i] * config.WEIGHT_RATE +
            norm_cpi[i] * config.WEIGHT_CPI +
            norm_pmi[i] * config.WEIGHT_PMI
        )
        
        scores_raw[currency] = {
            'score_rate': norm_rate[i],
            'score_cpi': norm_cpi[i],
            'score_pmi': norm_pmi[i],
            'total_score': total
        }
    
    # Step 6: Rank by total score (descending)
    sorted_currencies = sorted(
        scores_raw.items(),
        key=lambda x: x[1]['total_score'],
        reverse=True
    )
    
    # Add rank to each score
    final_scores = {}
    for rank, (currency, score_data) in enumerate(sorted_currencies, start=1):
        score_data['rank'] = rank
        final_scores[currency] = score_data
    
    return final_scores


def get_ranked_list(scores: Dict[str, Dict]) -> List[Tuple[str, float, int]]:
    """
    Get currencies sorted by score (highest first).
    
    Args:
        scores: Dict from score_all_currencies()
        
    Returns:
        List of (currency, total_score, rank) tuples
    """
    return sorted(
        [(c, s['total_score'], s['rank']) for c, s in scores.items()],
        key=lambda x: x[1],
        reverse=True
    )


def pair_currencies(scores: Dict[str, Dict]) -> Tuple[str, str, float]:
    """
    Get the strongest and weakest currencies (for pairing).
    
    Returns:
        Tuple of (strongest_currency, weakest_currency, gap)
    """
    ranked = get_ranked_list(scores)
    
    if not ranked or len(ranked) < 2:
        raise ValueError("Cannot pair: insufficient scored currencies")
    
    strongest_currency, strongest_score, _ = ranked[0]
    weakest_currency, weakest_score, _ = ranked[-1]
    gap = strongest_score - weakest_score
    
    return strongest_currency, weakest_currency, gap


def generate_signal(scores: Dict[str, Dict]) -> Tuple[str, str, str]:
    """
    Generate the primary trade signal.
    
    Returns:
        Tuple of (signal_text, status, gap_description)
        
        signal_text: "SHORT {weakest}/{strongest}" or "NO TRADE"
        status: "ACTIVE" or "NO_TRADE"
        gap_description: e.g. "Gap: 74 points · Strong signal"
    """
    strongest, weakest, gap = pair_currencies(scores)
    
    if gap >= config.MIN_GAP_TO_TRADE:
        signal_text = f"SHORT {weakest}/{strongest}"
        status = "ACTIVE"
        
        # Classify gap tier
        if gap >= config.GAP_THRESHOLDS["strong"]:
            tier = "Strong signal"
        elif gap >= config.GAP_THRESHOLDS["standard"]:
            tier = "Standard signal"
        elif gap >= config.GAP_THRESHOLDS["weak"]:
            tier = "Weak signal"
        else:
            tier = "Marginal signal"
        
        gap_desc = f"Gap: {gap:.1f} points · {tier}"
    else:
        signal_text = "NO TRADE"
        status = "NO_TRADE"
        gap_desc = f"Gap: {gap:.1f} points · Too narrow (< {config.MIN_GAP_TO_TRADE})"
    
    return signal_text, status, gap_desc


def get_gap_tier(gap: float) -> str:
    """
    Classify a gap size into trading tiers.
    
    Returns:
        One of: "no_trade", "weak", "standard", "strong"
    """
    if gap < config.GAP_THRESHOLDS["weak"]:
        return "no_trade"
    elif gap < config.GAP_THRESHOLDS["standard"]:
        return "weak"
    elif gap < config.GAP_THRESHOLDS["strong"]:
        return "standard"
    else:
        return "strong"


def validate_scores(scores: Dict[str, Dict]) -> bool:
    """
    Validate that scores dict has all required fields.
    
    Args:
        scores: Dict from score_all_currencies()
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    required_fields = {'score_rate', 'score_cpi', 'score_pmi', 'total_score', 'rank'}
    
    for currency in config.CURRENCIES:
        if currency not in scores:
            raise ValueError(f"Missing scores for {currency}")
        
        score_data = scores[currency]
        missing = required_fields - set(score_data.keys())
        
        if missing:
            raise ValueError(
                f"Missing fields for {currency}: {missing}"
            )
        
        # Check value ranges
        for field in ['score_rate', 'score_cpi', 'score_pmi', 'total_score']:
            value = score_data[field]
            if not (0 <= value <= 100):
                raise ValueError(
                    f"{currency}.{field} out of range [0-100]: {value}"
                )
    
    return True


# Example usage (for testing)
if __name__ == "__main__":
    # Mock data
    test_rates = {
        "USD": 5.25,
        "EUR": 4.50,
        "GBP": 5.25,
        "JPY": 0.10,
        "AUD": 4.35,
        "CAD": 5.00,
        "CHF": 1.75,
        "NZD": 5.50,
    }
    
    test_cpi = {
        "USD": 3.2,
        "EUR": 2.6,
        "GBP": 3.4,
        "JPY": 2.8,
        "AUD": 3.8,
        "CAD": 2.8,
        "CHF": 1.8,
        "NZD": 3.5,
    }
    
    test_pmi = {
        "USD": 54.2,
        "EUR": 48.9,
        "GBP": 52.1,
        "JPY": 51.4,
        "AUD": 46.2,
        "CAD": 49.2,
        "CHF": 49.8,
        "NZD": 47.1,
    }
    
    # Score all currencies
    scores = score_all_currencies(test_rates, test_cpi, test_pmi)
    
    print("Scores:")
    for currency, score_data in sorted(scores.items(), key=lambda x: x[1]['rank']):
        print(f"  {currency}: {score_data}")
    
    # Generate signal
    signal, status, gap_desc = generate_signal(scores)
    print(f"\nSignal: {signal}")
    print(f"Status: {status}")
    print(f"Gap: {gap_desc}")
