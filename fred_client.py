"""
APEX Layer 1 — FRED API Client

Fetches interest rates from the Federal Reserve Economic Data (FRED) API.

API Endpoint: https://api.stlouisfed.org/fred/series/observations

Features:
- Caches the most recent rate per currency
- Handles API errors gracefully
- Returns None for unavailable series
- Implements exponential backoff for retries
- Non-blocking when called from QThread

Setup:
1. Go to fred.stlouisfed.org
2. Register for a free account
3. Generate an API key
4. Store in .env as FRED_API_KEY
"""

import requests
from typing import Dict, Optional
import config
import time


class FredClient:
    """FRED API client for fetching interest rates."""
    
    def __init__(self, api_key: str = None, timeout: int = 10):
        """
        Initialize FRED client.
        
        Args:
            api_key: FRED API key. If None, uses config.FRED_API_KEY
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or config.FRED_API_KEY
        self.timeout = timeout
        self.base_url = config.FRED_BASE_URL
        self.cache = {}  # Cache: {currency: {rate, timestamp}}
        self.last_error = None
        
        if not self.api_key:
            raise ValueError(
                "FRED_API_KEY not configured. "
                "Set it in .env or pass as argument."
            )
    
    def fetch_rate(self, currency: str, max_retries: int = 2) -> Optional[float]:
        """
        Fetch the latest interest rate for a single currency.
        
        Args:
            currency: Currency code (USD, EUR, etc.)
            max_retries: Number of retry attempts on failure
            
        Returns:
            Interest rate as float (%), or None if fetch fails
        """
        if currency not in config.FRED_SERIES:
            self.last_error = f"Unknown currency: {currency}"
            return None
        
        series_id = config.FRED_SERIES[currency]
        
        for attempt in range(max_retries):
            try:
                rate = self._fetch_series_last_value(series_id)
                
                # Cache successful fetch
                self.cache[currency] = {
                    'rate': rate,
                    'source': 'FRED',
                    'timestamp': time.time()
                }
                
                if config.DEBUG:
                    print(f"[FRED] {currency}: {rate}% (from series {series_id})")
                
                return rate
                
            except requests.Timeout:
                self.last_error = f"{currency}: API timeout (attempt {attempt + 1}/{max_retries})"
                if config.DEBUG:
                    print(f"[FRED] {self.last_error}")
                time.sleep(0.5 ** attempt)  # Exponential backoff
                
            except requests.ConnectionError:
                self.last_error = f"{currency}: Connection error (attempt {attempt + 1}/{max_retries})"
                if config.DEBUG:
                    print(f"[FRED] {self.last_error}")
                time.sleep(0.5 ** attempt)
                
            except ValueError as e:
                self.last_error = f"{currency}: {str(e)}"
                if config.DEBUG:
                    print(f"[FRED] {self.last_error}")
                break  # Don't retry on parsing errors
                
            except Exception as e:
                self.last_error = f"{currency}: Unexpected error: {str(e)}"
                if config.DEBUG:
                    print(f"[FRED] {self.last_error}")
                break
        
        # Return cached value if available
        if currency in self.cache:
            if config.DEBUG:
                print(f"[FRED] {currency}: Using cached value {self.cache[currency]['rate']}%")
            return self.cache[currency]['rate']
        
        return None
    
    def fetch_all_rates(self, max_retries: int = 2) -> Dict[str, Optional[float]]:
        """
        Fetch interest rates for all 8 currencies.
        
        Args:
            max_retries: Number of retry attempts per currency
            
        Returns:
            Dict mapping currency to rate (float or None)
        """
        rates = {}
        for currency in config.CURRENCIES:
            rates[currency] = self.fetch_rate(currency, max_retries)
        
        return rates
    
    def _fetch_series_last_value(self, series_id: str) -> float:
        """
        Fetch the last observation of a FRED series.
        
        Args:
            series_id: FRED series ID (e.g., "FEDFUNDS")
            
        Returns:
            Latest numeric value from the series
            
        Raises:
            requests.RequestException: On network error
            ValueError: If series not found or parsing fails
        """
        url = f"{self.base_url}/series/observations"
        
        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'sort_order': 'desc',
            'limit': 1,
            'file_type': 'json'
        }
        
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()  # Raise exception for bad status codes
        
        data = response.json()
        
        # Check for FRED API error
        if 'error_code' in data:
            raise ValueError(
                f"FRED API error ({data['error_code']}): {data.get('error_message', 'Unknown error')}"
            )
        
        # Extract last observation
        observations = data.get('observations', [])
        if not observations:
            raise ValueError(f"No data available for series {series_id}")
        
        last_obs = observations[0]
        value = last_obs.get('value')
        
        if value is None or value == '.':
            raise ValueError(f"No numeric value in latest observation for {series_id}")
        
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot parse value as float: {value}")
    
    def get_cached_rate(self, currency: str) -> Optional[float]:
        """
        Get a cached rate without making a new API call.
        
        Args:
            currency: Currency code
            
        Returns:
            Cached rate, or None if not in cache
        """
        return self.cache.get(currency, {}).get('rate')
    
    def clear_cache(self):
        """Clear the rate cache."""
        self.cache.clear()
        if config.DEBUG:
            print("[FRED] Cache cleared")


# Global singleton instance (optional convenience)
_client_instance = None

def get_fred_client() -> FredClient:
    """Get or create the global FRED client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = FredClient()
    return _client_instance


# Example usage (for testing)
if __name__ == "__main__":
    import os
    
    # For testing, you need a FRED API key
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        print("ERROR: FRED_API_KEY not set in environment")
        print("Get a key from: https://fred.stlouisfed.org")
        exit(1)
    
    client = FredClient(api_key)
    
    print("Fetching all rates from FRED...")
    rates = client.fetch_all_rates()
    
    print("\nResults:")
    for currency, rate in rates.items():
        if rate is not None:
            print(f"  {currency}: {rate}%")
        else:
            print(f"  {currency}: ERROR or no data")
    
    if client.last_error:
        print(f"\nLast error: {client.last_error}")
