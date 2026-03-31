"""
ATR-Based Dynamic Stops & Trailing Stop Engine.

Replaces fixed-% stops with volatility-adaptive stops:
  - Initial stop: 2× ATR below entry
  - Trailing: tightens as profit increases (progressive)
  - NEPSE-aware: cannot send stop orders (manual execution)

Phase 4 Tasks: 4.2 (dynamic ATR stops) + 4.3 (trailing stops)
"""

from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class StopState:
    """Current stop-loss state for a position."""
    symbol: str
    entry_price: float
    current_atr: float
    initial_stop: float
    trailing_stop: float
    highest_price: float  # Highest price since entry (for trailing)

    @property
    def current_stop(self) -> float:
        """The effective stop is the higher of initial and trailing."""
        return max(self.initial_stop, self.trailing_stop)

    @property
    def risk_pct(self) -> float:
        if self.entry_price <= 0:
            return 0
        return (self.entry_price - self.current_stop) / self.entry_price * 100


def compute_initial_stop(entry_price: float, atr: float, multiplier: float = 2.0) -> float:
    """
    Initial stop = entry - multiplier × ATR.

    Default 2× ATR gives room for normal volatility while capping downside.
    """
    stop = entry_price - multiplier * atr
    return max(stop, entry_price * 0.85)  # Floor: never more than 15% below entry


def compute_trailing_stop(
    entry_price: float,
    highest_price: float,
    atr: float,
    initial_atr_mult: float = 2.0,
) -> float:
    """
    Progressive trailing stop that tightens as profit increases.

    Tightening schedule (profit in ATR multiples):
      0-1 ATR profit  → trail at 2.0× ATR below high   (same as initial)
      1-2 ATR profit  → trail at 1.5× ATR below high   (tighter)
      2-3 ATR profit  → trail at 1.0× ATR below high   (much tighter)
      3+ ATR profit   → trail at 0.75× ATR below high  (lock in gains)

    The stop NEVER moves down — it only ratchets up.
    """
    if atr <= 0:
        return entry_price * 0.95

    unrealized_atr = (highest_price - entry_price) / atr

    if unrealized_atr >= 3.0:
        trail_mult = 0.75
    elif unrealized_atr >= 2.0:
        trail_mult = 1.0
    elif unrealized_atr >= 1.0:
        trail_mult = 1.5
    else:
        trail_mult = initial_atr_mult  # 2.0

    return highest_price - trail_mult * atr


def create_stop_state(
    symbol: str,
    entry_price: float,
    atr: float,
    multiplier: float = 2.0,
) -> StopState:
    """Create initial stop state for a new position."""
    initial = compute_initial_stop(entry_price, atr, multiplier)
    return StopState(
        symbol=symbol,
        entry_price=entry_price,
        current_atr=atr,
        initial_stop=initial,
        trailing_stop=initial,
        highest_price=entry_price,
    )


def update_stop_state(
    state: StopState,
    current_price: float,
    current_atr: Optional[float] = None,
) -> StopState:
    """
    Update stop state with new price data.

    The trailing stop only ratchets UP (never down).
    ATR is updated if provided (adapts to changing volatility).
    """
    atr = current_atr if current_atr and current_atr > 0 else state.current_atr
    new_high = max(state.highest_price, current_price)

    new_trail = compute_trailing_stop(
        entry_price=state.entry_price,
        highest_price=new_high,
        atr=atr,
    )
    # Ratchet: never move stop DOWN
    new_trail = max(state.trailing_stop, new_trail)

    return StopState(
        symbol=state.symbol,
        entry_price=state.entry_price,
        current_atr=atr,
        initial_stop=state.initial_stop,
        trailing_stop=new_trail,
        highest_price=new_high,
    )
