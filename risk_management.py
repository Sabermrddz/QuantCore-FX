from typing import Dict, List, Optional, Tuple, Callable
import threading
import time
import math
import config


def pearson_correlation(x: List[float], y: List[float]) -> float:
    """Compute Pearson correlation coefficient r between two series.

    r = sum((x - x̄)(y - ȳ)) / sqrt(sum(x - x̄)^2 * sum(y - ȳ)^2)

    Returns value in [-1, 1]. |r| > 0.75 indicates strong correlation.
    """
    n = min(len(x), len(y))
    if n < 3:
        return 0.0
    x, y = x[:n], y[:n]
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    den_x = math.sqrt(sum((xi - x_mean) ** 2 for xi in x))
    den_y = math.sqrt(sum((yi - y_mean) ** 2 for yi in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    r = num / (den_x * den_y)
    return max(-1.0, min(1.0, r))


class PositionSizer:
    """Calculates position size based on risk and confluence strength."""

    def __init__(self, account_balance: float = 10000.0, risk_per_trade: float = 0.01):
        self.account_balance = account_balance
        self.risk_per_trade = risk_per_trade
        self.positions = {}

    def calculate_position_size(
        self,
        pair: str,
        confluence_strength: float,
        entry_price: float,
        stop_loss_pips: float = 50,
        bid: float = None,
        ask: float = None,
        spread: float = None,
    ) -> float:
        risk_amount = self.account_balance * self.risk_per_trade
        confidence_multiplier = confluence_strength / 100.0
        pip_value_per_lot = 10.0
        max_loss_per_lot = stop_loss_pips * pip_value_per_lot
        if max_loss_per_lot > 0:
            base_position = risk_amount / max_loss_per_lot
            position_size = base_position * confidence_multiplier
        else:
            position_size = 0.0
        # Spread penalty (Task 2.1): wide spreads reduce size by up to 20%
        if spread is not None and spread > 0:
            spread_penalty = min(spread * 100, 0.2)  # cap at 20% penalty
            position_size *= (1.0 - spread_penalty)
        position_size = max(0.01, min(position_size, 5.0))
        return position_size

    def add_position(self, pair: str, position_size: float, entry_price: float):
        self.positions[pair] = {
            'size': position_size,
            'entry_price': entry_price,
            'status': 'OPEN'
        }

    def close_position(self, pair: str, exit_price: float) -> Optional[Dict]:
        if pair not in self.positions:
            return None
        pos = self.positions[pair]
        price_delta = exit_price - pos['entry_price']
        pl = price_delta * pos['size'] * 100000
        result = {
            'pair': pair,
            'entry': pos['entry_price'],
            'exit': exit_price,
            'size': pos['size'],
            'pnl': pl,
            'pnl_pips': price_delta * 10000
        }
        del self.positions[pair]
        return result


class GridHedging:
    """Grid hedging system for drawdown protection."""

    def __init__(self, grid_levels: int = 3):
        self.grid_levels = grid_levels
        self.hedges = []

    def create_hedge_grid(
        self,
        pair: str,
        entry_price: float,
        position_size: float,
        grid_distance: float = 0.50
    ) -> List[Dict]:
        self.hedges = []
        if self.grid_levels < 2:
            return self.hedges
        hedge_size = position_size * 0.5 / (self.grid_levels - 1)
        for level in range(1, self.grid_levels):
            hedge_price = entry_price - (grid_distance * level / 10000)
            self.hedges.append({
                'pair': pair,
                'level': level,
                'price': hedge_price,
                'size': hedge_size,
                'type': 'HEDGE'
            })
        return self.hedges

    def get_total_hedge_exposure(self) -> float:
        return sum(h['size'] for h in self.hedges)

    def get_hedges_for_pair(self, pair: str) -> List[Dict]:
        return [h for h in self.hedges if h['pair'] == pair]


class PortfolioExposure:
    """Manage portfolio-level exposure and leverage."""

    def __init__(self, max_portfolio_leverage: float = 2.0):
        self.max_leverage = max_portfolio_leverage
        self.positions = {}
        self.total_exposure = 0.0

    def can_add_position(self, position_size: float, account_balance: float) -> bool:
        new_exposure = self.total_exposure + position_size
        max_exposure = account_balance * self.max_leverage
        return new_exposure <= max_exposure

    def add_position(self, pair: str, position_size: float):
        self.positions[pair] = position_size
        self.total_exposure = sum(self.positions.values())

    def remove_position(self, pair: str):
        if pair in self.positions:
            del self.positions[pair]
            self.total_exposure = sum(self.positions.values())

    def get_leverage_ratio(self, account_balance: float) -> float:
        if account_balance <= 0:
            return 0.0
        return self.total_exposure / account_balance

    def get_exposure_percentage(self, pair: str) -> float:
        if self.total_exposure <= 0:
            return 0.0
        return (self.positions.get(pair, 0) / self.total_exposure) * 100


class CorrelationEngine:
    """Rolling Pearson correlation matrix (Task 3.2).

    Replaces the hardcoded CORRELATION_CLUSTERS with a dynamic
    calculation based on the past 30 days of Close prices.
    """

    def __init__(self):
        self.correlation_cache: Dict[Tuple[str, str], float] = {}
        self.last_update = None
        self.price_series: Dict[str, List[float]] = {}

    def update_series(self, historical_closes: Dict[str, List[float]]):
        """Feed 30 days of Close prices for all 28 pairs."""
        self.price_series = historical_closes
        self.correlation_cache.clear()
        self.last_update = time.time()

    def get_correlation(self, pair_a: str, pair_b: str) -> float:
        """Get Pearson r between two pairs."""
        key = tuple(sorted([pair_a, pair_b]))
        if key in self.correlation_cache:
            return self.correlation_cache[key]

        series_a = self.price_series.get(pair_a, [])
        series_b = self.price_series.get(pair_b, [])
        r = pearson_correlation(series_a, series_b)
        self.correlation_cache[key] = r
        return r

    def get_top_correlated(
        self, target_pair: str, n: int = 3, min_r: float = 0.75
    ) -> List[Tuple[str, float]]:
        """Get top N pairs most correlated (|r| >= min_r) with target."""
        results = []
        for pair in self.price_series:
            if pair == target_pair:
                continue
            r = self.get_correlation(target_pair, pair)
            if abs(r) >= min_r:
                results.append((pair, r))
        results.sort(key=lambda x: abs(x[1]), reverse=True)
        return results[:n]


class BasketHedging:
    """Dynamic basket hedging using Pearson correlation (Task 3.2).

    Instead of hardcoded correlation clusters, uses CorrelationEngine
    to select the top 3 pairs with |r| >= 0.75 to the target cross-pair.
    """

    def __init__(self, correlation_engine: CorrelationEngine = None):
        self.basket_positions = []
        self.correlation_engine = correlation_engine or CorrelationEngine()

    def set_correlation_engine(self, engine: CorrelationEngine):
        self.correlation_engine = engine

    def get_correlated_pairs(self, pair: str) -> List[str]:
        """Get dynamically correlated pairs for basket hedging."""
        top = self.correlation_engine.get_top_correlated(pair, n=3, min_r=0.75)
        return [p for p, r in top]

    def create_basket_hedge(
        self,
        primary_pair: str,
        primary_size: float,
        confluence_strength: float,
        current_prices: Dict[str, float] = None
    ) -> List[Dict]:
        correlated = self.get_correlated_pairs(primary_pair)
        self.basket_positions = []

        if not correlated:
            return self.basket_positions

        hedge_ratio = 0.3
        hedge_size = primary_size * hedge_ratio / len(correlated)

        for cp in correlated:
            entry = (current_prices or {}).get(cp, 0)
            self.basket_positions.append({
                'pair': cp,
                'size': hedge_size,
                'entry_price': entry,
                'type': 'BASKET_HEDGE',
                'primary_pair': primary_pair,
            })

        return self.basket_positions

    def get_total_basket_exposure(self) -> float:
        return sum(h['size'] for h in self.basket_positions)


class RiskManagementSystem:
    """Complete risk management system with portfolio-level exit (Task 3.3).

    Features:
    - Position sizing with spread penalty (Task 2.1)
    - Dynamic basket hedging via Pearson correlation (Task 3.2)
    - Aggregate portfolio P&L monitoring with dynamic profit target (Task 3.3)
    - Portfolio-based exit: close ALL trades when basket P&L > target
    """

    def __init__(self, account_balance: float = 10000.0):
        self.account_balance = account_balance
        self.sizer = PositionSizer(account_balance, risk_per_trade=0.01)
        self.hedger = GridHedging(grid_levels=config.GRID_LEVELS)
        self.portfolio = PortfolioExposure(max_portfolio_leverage=config.MAX_PORTFOLIO_LEVERAGE)
        self.correlation_engine = CorrelationEngine()
        self.basket = BasketHedging(self.correlation_engine)
        self.trades = []

        self.current_prices: Dict[str, float] = {}
        self.current_order_books: Dict[str, Dict] = {}

        # Portfolio exit monitor (Task 3.3)
        self._exit_monitor_running = False
        self._exit_monitor_thread: Optional[threading.Thread] = None
        self._exit_callbacks: List[Callable] = []

    def update_prices(self, prices: Dict[str, float]):
        self.current_prices.update(prices)

    def update_order_books(self, order_books: Dict[str, Dict]):
        self.current_order_books.update(order_books)

    def update_correlation_data(self, historical_closes: Dict[str, List[float]]):
        """Feed 30-day close prices for dynamic correlation (Task 3.2)."""
        self.correlation_engine.update_series(historical_closes)

    def execute_signal(
        self,
        pair: str,
        confluence_strength: float,
        entry_price: float,
        use_hedging: bool = True,
        use_basket: bool = True,
        order_book: Dict = None,
    ) -> Optional[Dict]:
        """Execute a confluence signal with full risk management.

        Uses actual bid/ask/spread from order book (Task 2.1) for
        position sizing if available.
        """
        bid = (order_book or {}).get('bid', entry_price)
        ask = (order_book or {}).get('ask', entry_price)
        spread = (order_book or {}).get('spread')

        position_size = self.sizer.calculate_position_size(
            pair, confluence_strength, entry_price,
            stop_loss_pips=50, bid=bid, ask=ask, spread=spread
        )

        if not self.portfolio.can_add_position(position_size, self.account_balance):
            return None

        trade = {
            'pair': pair,
            'entry_price': entry_price,
            'entry_bid': bid,
            'entry_ask': ask,
            'position_size': position_size,
            'confluence_strength': confluence_strength,
            'status': 'OPEN',
        }

        if use_hedging and confluence_strength > 70:
            trade['grid_hedges'] = self.hedger.create_hedge_grid(
                pair, entry_price, position_size
            )

        if use_basket and confluence_strength > 60:
            trade['basket_hedges'] = self.basket.create_basket_hedge(
                pair, position_size, confluence_strength, self.current_prices
            )
            if config.DEBUG:
                n_hedges = len(trade.get('basket_hedges', []))
                print(f"[Risk] Created {n_hedges} dynamic basket hedges for {pair}")

        self.portfolio.add_position(pair, position_size)
        self.trades.append(trade)
        return trade

    def calculate_basket_pnl(self) -> float:
        """Calculate aggregate P&L across ALL open positions and hedges."""
        total = 0.0
        for trade in self.trades:
            if trade['status'] != 'OPEN':
                continue
            pair = trade['pair']
            entry = trade['entry_price']
            current = self.current_prices.get(pair, entry)
            delta = current - entry
            total += delta * trade['position_size'] * 100000

            for hedge in trade.get('grid_hedges', []):
                h_current = self.current_prices.get(hedge['pair'], hedge['price'])
                h_delta = h_current - hedge['price']
                total += h_delta * hedge['size'] * 100000

            for hedge in trade.get('basket_hedges', []):
                h_current = self.current_prices.get(hedge['pair'], hedge['entry_price'])
                h_delta = h_current - hedge['entry_price']
                total += h_delta * hedge['size'] * 100000

        return total

    def get_dynamic_exit_target(self) -> float:
        """Dynamic profit target based on trade confidence (Task 3.3).

        Higher confidence trades get a larger profit target.
        Base: +1% of account balance.
        """
        if not self.trades:
            return self.account_balance * 0.01

        avg_confidence = sum(
            t.get('confluence_strength', 50) for t in self.trades if t['status'] == 'OPEN'
        )
        n_open = max(len([t for t in self.trades if t['status'] == 'OPEN']), 1)
        avg_confidence /= n_open

        base_target = self.account_balance * 0.01
        confidence_mult = avg_confidence / 50.0  # 1.0x at 50%, 2.0x at 100%
        return base_target * confidence_mult

    def _monitor_exit_loop(self):
        """Background loop monitoring basket P&L every second (Task 3.3).

        When aggregate net P&L surpasses the dynamic target,
        fires close_all_trades() automatically.
        """
        while self._exit_monitor_running:
            if not self.trades:
                time.sleep(1)
                continue

            total_pnl = self.calculate_basket_pnl()
            target = self.get_dynamic_exit_target()

            if total_pnl > target:
                if config.DEBUG:
                    print(f"[Risk] Portfolio exit triggered: P&L={total_pnl:.2f} target={target:.2f}")
                for cb in self._exit_callbacks:
                    try:
                        cb(total_pnl)
                    except Exception:
                        pass
                break

            time.sleep(1)

    def start_exit_monitor(self):
        """Start the background portfolio exit monitor (Task 3.3)."""
        if self._exit_monitor_running:
            return
        self._exit_monitor_running = True
        self._exit_monitor_thread = threading.Thread(
            target=self._monitor_exit_loop, daemon=True
        )
        self._exit_monitor_thread.start()
        if config.DEBUG:
            print("[Risk] Portfolio exit monitor started")

    def on_portfolio_exit(self, callback: Callable):
        """Register a callback for when the portfolio exit fires."""
        self._exit_callbacks.append(callback)

    def stop_exit_monitor(self):
        self._exit_monitor_running = False

    def should_exit_portfolio(self) -> Tuple[bool, float]:
        """Check if aggregate portfolio P&L has hit the profit target."""
        total_pnl = self.calculate_basket_pnl()
        if total_pnl > self.get_dynamic_exit_target():
            return True, total_pnl
        return False, total_pnl

    def close_trade(self, pair: str, exit_price: float) -> Optional[Dict]:
        result = self.sizer.close_position(pair, exit_price)
        if result:
            self.portfolio.remove_position(pair)
        return result

    def close_all_trades(self, exit_prices: Dict[str, float]):
        """Close all open trades at given exit prices."""
        results = []
        for trade in list(self.trades):
            if trade['status'] == 'OPEN':
                price = exit_prices.get(trade['pair'], trade['entry_price'])
                result = self.close_trade(trade['pair'], price)
                if result:
                    results.append(result)
        self.stop_exit_monitor()
        return results

    def get_portfolio_summary(self) -> Dict:
        return {
            'total_positions': len(self.portfolio.positions),
            'total_exposure': self.portfolio.total_exposure,
            'leverage_ratio': self.portfolio.get_leverage_ratio(self.account_balance),
            'open_trades': len([t for t in self.trades if t['status'] == 'OPEN']),
            'basket_pnl': self.calculate_basket_pnl(),
            'exit_target': self.get_dynamic_exit_target(),
            'account_balance': self.account_balance,
        }
