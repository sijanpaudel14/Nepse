"""
Portfolio Risk Engine — Hard Enforcement (not advisory).

Implements Phase 4 tasks:
  4.4 — PortfolioRiskEngine with hard pre-trade limits
  4.5 — Daily loss tracking with market-open reset
  4.6 — Position persistence via LivePosition model
  4.7 — Circuit breaker proximity alert
  4.8 — T+2 settlement awareness

Every order MUST pass through `pre_trade_check()` before execution.
If it returns False, the trade is BLOCKED — not just warned.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger

from core.config import settings
from core.database import SessionLocal, LivePosition
from risk.atr_stops import StopState, create_stop_state, update_stop_state


# ── NEPSE T+2 settlement: cannot sell within 3 trading days of purchase ──
T_PLUS_2_DAYS = 3  # T+2 = 3 calendar days minimum (Sun buy → Wed earliest sell)

# Circuit breaker: NEPSE has ±10% daily limit
CIRCUIT_BREAKER_PCT = 10.0
CIRCUIT_PROXIMITY_WARN_PCT = 8.0  # Warn when within 2% of circuit


@dataclass
class PreTradeResult:
    """Result of a pre-trade risk check — pass/fail with reason."""
    allowed: bool
    reason: str = ""
    position_size_mult: float = 1.0  # Multiplier applied to size (e.g. 0.5 in caution)


class PortfolioRiskEngine:
    """
    Enforced (not advisory) portfolio-level risk controls.

    Hard limits:
      - Max 2% risk per trade
      - Max 5 concurrent positions
      - Max 30% sector exposure
      - Min 20% cash reserve
      - Max 20% single position
      - Daily loss halt at 3%
      - Drawdown halt at 20%
      - T+2 settlement block

    Usage:
        engine = PortfolioRiskEngine(capital=500_000)
        result = engine.pre_trade_check("NABIL", "Commercial Banks", 120_000)
        if result.allowed:
            # execute trade
        else:
            logger.warning(f"BLOCKED: {result.reason}")
    """

    def __init__(
        self,
        capital: float,
        max_positions: int = 5,
        max_risk_per_trade: float = 0.02,
        max_sector_pct: float = 0.30,
        max_single_pct: float = 0.20,
        min_cash_pct: float = 0.20,
        max_daily_loss_pct: float = 3.0,
        max_drawdown_pct: float = 20.0,
    ):
        self.initial_capital = capital
        self.cash = capital
        self.max_positions = max_positions
        self.max_risk_per_trade = max_risk_per_trade
        self.max_sector_pct = max_sector_pct
        self.max_single_pct = max_single_pct
        self.min_cash_pct = min_cash_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct

        # State
        self.peak_value = capital
        self.day_start_value = capital
        self.daily_loss_halted = False

        # Stop states (symbol → StopState)
        self.stops: Dict[str, StopState] = {}

        # Load persisted positions
        self._positions: Dict[str, LivePosition] = {}
        self._load_positions()

    # ────────────────────────────────────────────
    # Position persistence (Phase 4.6)
    # ────────────────────────────────────────────

    def _load_positions(self):
        """Load open positions from DB on startup."""
        db = SessionLocal()
        try:
            rows = db.query(LivePosition).filter(LivePosition.status == "OPEN").all()
            for r in rows:
                self._positions[r.symbol] = r
                # Rebuild stop states
                self.stops[r.symbol] = StopState(
                    symbol=r.symbol,
                    entry_price=r.entry_price,
                    current_atr=r.current_atr or r.entry_price * 0.03,
                    initial_stop=r.stop_loss,
                    trailing_stop=r.trailing_stop or r.stop_loss,
                    highest_price=r.highest_price or r.entry_price,
                )
            logger.info(f"Loaded {len(self._positions)} open positions from DB")
        finally:
            db.close()

    def persist_position(self, pos: LivePosition):
        """Save/update a position to DB."""
        db = SessionLocal()
        try:
            existing = (
                db.query(LivePosition)
                .filter(LivePosition.symbol == pos.symbol, LivePosition.status == "OPEN")
                .first()
            )
            if existing:
                existing.shares = pos.shares
                existing.stop_loss = pos.stop_loss
                existing.trailing_stop = pos.trailing_stop
                existing.target_price = pos.target_price
                existing.highest_price = pos.highest_price
                existing.current_atr = pos.current_atr
                existing.status = pos.status
                existing.exit_price = pos.exit_price
                existing.exit_date = pos.exit_date
                existing.exit_reason = pos.exit_reason
            else:
                db.add(pos)
            db.commit()
        finally:
            db.close()

    def close_position_db(self, symbol: str, exit_price: float, reason: str):
        """Mark position as CLOSED in DB."""
        db = SessionLocal()
        try:
            pos = (
                db.query(LivePosition)
                .filter(LivePosition.symbol == symbol, LivePosition.status == "OPEN")
                .first()
            )
            if pos:
                pos.status = "CLOSED"
                pos.exit_price = exit_price
                pos.exit_date = date.today()
                pos.exit_reason = reason
                db.commit()
            self._positions.pop(symbol, None)
            self.stops.pop(symbol, None)
        finally:
            db.close()

    # ────────────────────────────────────────────
    # Portfolio state
    # ────────────────────────────────────────────

    @property
    def open_positions(self) -> Dict[str, LivePosition]:
        return self._positions

    @property
    def num_positions(self) -> int:
        return len(self._positions)

    @property
    def positions_value(self) -> float:
        return sum(
            (p.highest_price or p.entry_price) * p.shares
            for p in self._positions.values()
        )

    @property
    def total_value(self) -> float:
        return self.cash + self.positions_value

    @property
    def drawdown_pct(self) -> float:
        if self.peak_value <= 0:
            return 0
        return (self.peak_value - self.total_value) / self.peak_value * 100

    @property
    def daily_pnl_pct(self) -> float:
        if self.day_start_value <= 0:
            return 0
        return (self.total_value - self.day_start_value) / self.day_start_value * 100

    # ────────────────────────────────────────────
    # T+2 Settlement (Phase 4.8)
    # ────────────────────────────────────────────

    def can_sell(self, symbol: str) -> Tuple[bool, str]:
        """Check if position can be sold (T+2 rule)."""
        pos = self._positions.get(symbol)
        if not pos:
            return False, f"No open position in {symbol}"
        days_held = (date.today() - pos.entry_date).days
        if days_held < T_PLUS_2_DAYS:
            return False, f"{symbol}: T+2 block — held {days_held}d, need {T_PLUS_2_DAYS}d"
        return True, "OK"

    # ────────────────────────────────────────────
    # Circuit breaker proximity (Phase 4.7)
    # ────────────────────────────────────────────

    @staticmethod
    def circuit_breaker_check(
        current_price: float,
        prev_close: float,
    ) -> Dict[str, object]:
        """
        Check if stock is near ±10% circuit breaker.

        Returns dict with:
          upper_pct: % from upper circuit
          lower_pct: % from lower circuit
          warning: True if within CIRCUIT_PROXIMITY_WARN_PCT of either
        """
        if prev_close <= 0:
            return {"upper_pct": 0, "lower_pct": 0, "warning": False}
        change_pct = (current_price - prev_close) / prev_close * 100
        return {
            "upper_pct": CIRCUIT_BREAKER_PCT - change_pct,
            "lower_pct": CIRCUIT_BREAKER_PCT + change_pct,
            "change_pct": change_pct,
            "warning": abs(change_pct) >= CIRCUIT_PROXIMITY_WARN_PCT,
        }

    # ────────────────────────────────────────────
    # Pre-trade check — THE ENFORCER
    # ────────────────────────────────────────────

    def pre_trade_check(
        self,
        symbol: str,
        sector: str,
        position_value: float,
        risk_amount: float = 0,
    ) -> PreTradeResult:
        """
        Hard pre-trade risk check.  Returns allowed=False to BLOCK trade.

        Checks (in order):
          1. Max daily loss → halt
          2. Max drawdown → halt
          3. Already have position
          4. Max positions
          5. Max single position size
          6. Max sector exposure
          7. Min cash reserve
          8. Max risk per trade
        """
        # 1. Daily loss halt
        if self.daily_loss_halted or self.daily_pnl_pct <= -self.max_daily_loss_pct:
            self.daily_loss_halted = True
            return PreTradeResult(False, "Daily loss limit reached — trading halted")

        # 2. Drawdown halt
        if self.drawdown_pct >= self.max_drawdown_pct:
            return PreTradeResult(False, f"Drawdown {self.drawdown_pct:.1f}% exceeds {self.max_drawdown_pct}% — halted")

        # 3. Already have position
        if symbol in self._positions:
            return PreTradeResult(False, f"Already have open position in {symbol}")

        # 4. Max positions
        if self.num_positions >= self.max_positions:
            return PreTradeResult(False, f"Max positions ({self.max_positions}) reached")

        # 5. Single position size
        if position_value / self.total_value > self.max_single_pct:
            return PreTradeResult(
                False,
                f"Position {position_value:,.0f} is {position_value / self.total_value:.0%} of portfolio "
                f"(max {self.max_single_pct:.0%})",
            )

        # 6. Sector exposure
        sector_val = sum(
            (p.highest_price or p.entry_price) * p.shares
            for p in self._positions.values()
            if (p.sector or "") == sector
        )
        new_sector_pct = (sector_val + position_value) / self.total_value
        if new_sector_pct > self.max_sector_pct:
            return PreTradeResult(
                False,
                f"Sector '{sector}' would be {new_sector_pct:.0%} (max {self.max_sector_pct:.0%})",
            )

        # 7. Cash reserve
        remaining_cash = self.cash - position_value
        if remaining_cash / self.total_value < self.min_cash_pct:
            return PreTradeResult(
                False,
                f"Would leave {remaining_cash / self.total_value:.0%} cash (min {self.min_cash_pct:.0%})",
            )

        # 8. Risk per trade
        if risk_amount > 0:
            risk_pct = risk_amount / self.total_value
            if risk_pct > self.max_risk_per_trade:
                return PreTradeResult(
                    False,
                    f"Trade risk {risk_pct:.1%} exceeds max {self.max_risk_per_trade:.1%}",
                )

        # Drawdown-based size reduction
        mult = 1.0
        if self.drawdown_pct >= 15:
            mult = 0.25
        elif self.drawdown_pct >= 10:
            mult = 0.50

        return PreTradeResult(True, "OK", position_size_mult=mult)

    # ────────────────────────────────────────────
    # Daily reset (Phase 4.5)
    # ────────────────────────────────────────────

    def reset_daily(self):
        """
        Call at market open (Sun 11:00 AM Nepal time).

        Resets daily P&L tracking and unlocks trading if halted by daily loss.
        """
        self.day_start_value = self.total_value
        self.daily_loss_halted = False
        logger.info(f"Daily reset: start_value={self.day_start_value:,.0f}")

    def update_peak(self):
        """Update peak value for drawdown calculations."""
        if self.total_value > self.peak_value:
            self.peak_value = self.total_value

    # ────────────────────────────────────────────
    # Stop management
    # ────────────────────────────────────────────

    def register_entry(
        self,
        symbol: str,
        shares: int,
        entry_price: float,
        sector: str,
        atr: float,
        css_score: float = 0.0,
        target_price: float = 0.0,
    ):
        """Register a new position and persist it."""
        stop = create_stop_state(symbol, entry_price, atr)
        self.stops[symbol] = stop

        pos = LivePosition(
            symbol=symbol,
            shares=shares,
            entry_price=entry_price,
            entry_date=date.today(),
            sector=sector,
            stop_loss=stop.initial_stop,
            trailing_stop=stop.trailing_stop,
            target_price=target_price,
            highest_price=entry_price,
            current_atr=atr,
            css_score=css_score,
            status="OPEN",
        )
        self._positions[symbol] = pos
        self.cash -= entry_price * shares
        self.persist_position(pos)
        logger.info(
            f"Position opened: {symbol} {shares}@{entry_price:.2f} "
            f"stop={stop.current_stop:.2f} target={target_price:.2f}"
        )

    def update_prices(self, prices: Dict[str, float], atrs: Optional[Dict[str, float]] = None):
        """
        Update all positions with latest prices, adjust trailing stops.

        Returns list of symbols whose stop was hit.
        """
        hit_stops: List[str] = []
        atrs = atrs or {}

        for sym, pos in list(self._positions.items()):
            price = prices.get(sym)
            if price is None:
                continue

            pos.highest_price = max(pos.highest_price or pos.entry_price, price)

            # Update trailing stop
            if sym in self.stops:
                self.stops[sym] = update_stop_state(
                    self.stops[sym],
                    current_price=price,
                    current_atr=atrs.get(sym),
                )
                pos.trailing_stop = self.stops[sym].trailing_stop
                pos.stop_loss = self.stops[sym].current_stop

            # Check stop hit
            if self.stops.get(sym) and price <= self.stops[sym].current_stop:
                hit_stops.append(sym)

        self.update_peak()
        return hit_stops
