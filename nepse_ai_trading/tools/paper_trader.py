"""
📊 PAPER TRADER - Forward Testing Engine for NEPSE AI Trading Bot

This script enables forward-testing (paper trading) of the 4-Pillar algorithm
by tracking virtual portfolio performance over time.

Since historical broker data is unavailable for backtesting, this paper trader
allows you to prove the algorithm's accuracy by:
1. Saving daily top picks to SQLite database
2. Tracking virtual "buys" at algorithm's recommended prices
3. Monitoring actual performance after T+2 settlement
4. Generating accuracy reports over time

USAGE:
------
# Run daily at 3:15 PM after market close
python paper_trader.py --action=scan

# Check portfolio status
python paper_trader.py --action=status

# Generate performance report
python paper_trader.py --action=report

Author: AI Quantitative Engine
Date: 2026-03-21
"""

# Suppress httpx deprecation warnings from openai/telegram libraries
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
import pandas as pd

# Quiet-by-default logging: only show logs when explicitly requested.
def _logs_requested(argv: List[str]) -> bool:
    for i, arg in enumerate(argv):
        if arg == "--logs=show":
            return True
        if arg == "--logs" and i + 1 < len(argv) and argv[i + 1].lower() == "show":
            return True
    return False

if not _logs_requested(sys.argv[1:]):
    os.environ["LOGURU_LEVEL"] = "ERROR"

from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.master_screener import MasterStockScreener, get_best_stocks, ScreenedStock
from analysis.indicators import safe_rsi, safe_vwap
from data.fetcher import NepseFetcher
from data.sharehub_api import get_price_history_with_open
from risk.position_sizer import PositionSizer
from core.config import settings


# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "paper_trading.db")
PORTFOLIO_PATH = os.path.join(os.path.dirname(__file__), "portfolio.json")


# ============================================================================
# PORTFOLIO MANAGER - Enforces strict holding rules
# ============================================================================

@dataclass
class PortfolioHolding:
    """Single portfolio position with holding rules."""
    symbol: str
    buy_price: float
    buy_date: str  # YYYY-MM-DD
    allocation: float  # 0.03 = 3%
    quantity: int = 0  # Optional: actual shares
    
    @property
    def days_held(self) -> int:
        """Calculate trading days held (weekdays only for NEPSE)."""
        buy = datetime.strptime(self.buy_date, "%Y-%m-%d")
        today = datetime.now()
        # Count weekdays (NEPSE is closed Sat)
        days = 0
        current = buy
        while current < today:
            # NEPSE: Sunday-Thursday (weekday 6=Sun, 0-3=Mon-Thu are trading days in Nepal)
            # In Python: Monday=0, Sunday=6
            # NEPSE trades Sun-Thu, closed Fri-Sat
            if current.weekday() not in (4, 5):  # Not Friday, Saturday
                days += 1
            current += timedelta(days=1)
        return max(1, days)  # At least day 1
    
    @property
    def target_price(self) -> float:
        """Exit target: +10%"""
        return round(self.buy_price * 1.10, 2)
    
    @property
    def stop_loss(self) -> float:
        """Exit stop: -5%"""
        return round(self.buy_price * 0.95, 2)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "buy_price": self.buy_price,
            "buy_date": self.buy_date,
            "allocation": self.allocation,
            "quantity": self.quantity,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "PortfolioHolding":
        return cls(
            symbol=d["symbol"],
            buy_price=d["buy_price"],
            buy_date=d["buy_date"],
            allocation=d.get("allocation", 0.03),
            quantity=d.get("quantity", 0),
        )


class PortfolioManager:
    """
    📊 Portfolio Manager with strict holding rules.
    
    RULES:
    1. MAX 9% allocation (3 stocks × 3% each)
    2. 7-DAY HOLD: No exits during first 7 days
    3. EXIT TRIGGERS: +10% target, -5% stop, 15 days max
    """
    
    MAX_ALLOCATION = 0.09  # 9% of portfolio
    MAX_STOCKS = 3
    DEFAULT_ALLOCATION = 0.03  # 3% per stock
    HOLD_DAYS = 7  # Minimum hold period
    MAX_HOLD_DAYS = 15  # Force review after this
    TARGET_PCT = 0.10  # +10% profit target
    STOP_LOSS_PCT = 0.05  # -5% stop loss
    
    def __init__(self, portfolio_path: str = PORTFOLIO_PATH, total_capital: float = 100000):
        self.portfolio_path = portfolio_path
        self.holdings: List[PortfolioHolding] = []
        self.watchlist: List[str] = []
        self.total_capital = total_capital
        # H7 FIX: Initialize PositionSizer for risk validation
        self.sizer = PositionSizer(
            portfolio_value=total_capital,
            max_risk_per_trade=0.02,  # 2% hard limit
        )
        self._load()
    
    def _load(self):
        """Load portfolio from JSON file."""
        if os.path.exists(self.portfolio_path):
            try:
                with open(self.portfolio_path, 'r') as f:
                    data = json.load(f)
                self.holdings = [PortfolioHolding.from_dict(h) for h in data.get("holdings", [])]
                self.watchlist = data.get("watchlist", [])
            except Exception as e:
                logger.warning(f"Could not load portfolio: {e}")
                self.holdings = []
                self.watchlist = []
        else:
            self.holdings = []
            self.watchlist = []
    
    def _save(self):
        """Save portfolio to JSON file."""
        data = {
            "holdings": [h.to_dict() for h in self.holdings],
            "watchlist": self.watchlist,
            "total_allocation": self.total_allocation,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(self.portfolio_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @property
    def total_allocation(self) -> float:
        """Current total allocation percentage."""
        return sum(h.allocation for h in self.holdings)
    
    @property
    def is_full(self) -> bool:
        """Check if portfolio has reached max allocation."""
        return len(self.holdings) >= self.MAX_STOCKS or self.total_allocation >= self.MAX_ALLOCATION
    
    @property
    def available_slots(self) -> int:
        """Number of positions that can still be added."""
        return self.MAX_STOCKS - len(self.holdings)
    
    def can_add_position(self, allocation: float = None) -> bool:
        """Check if a new position can be added."""
        allocation = allocation or self.DEFAULT_ALLOCATION
        if len(self.holdings) >= self.MAX_STOCKS:
            return False
        if self.total_allocation + allocation > self.MAX_ALLOCATION:
            return False
        return True
    
    def add_position(self, symbol: str, buy_price: float, allocation: float = None, quantity: int = 0, stop_loss: float = None) -> bool:
        """
        Add a new position to portfolio.
        
        H7 FIX: Now validates risk with PositionSizer if stop_loss provided.
        
        Returns True if added, False if portfolio full.
        """
        allocation = allocation or self.DEFAULT_ALLOCATION
        symbol = symbol.upper()
        
        # Check if already holding
        if any(h.symbol == symbol for h in self.holdings):
            logger.warning(f"{symbol} already in portfolio")
            return False
        
        if not self.can_add_position(allocation):
            logger.warning(f"Portfolio full ({self.total_allocation*100:.1f}% allocated)")
            self.add_to_watchlist(symbol)
            return False
        
        # H7 FIX: Validate risk if stop loss provided
        if stop_loss and stop_loss > 0 and stop_loss < buy_price:
            position = self.sizer.calculate(
                symbol=symbol,
                entry_price=buy_price,
                stop_loss=stop_loss,
                target_price=buy_price * (1 + self.TARGET_PCT),  # 10% target
            )
            
            if not position.is_valid():
                logger.warning(
                    f"⚠️ {symbol}: Risk {position.risk_percent:.2f}% exceeds 2% limit. "
                    f"Position rejected for safety."
                )
                return False
            
            # Use risk-sized quantity if not provided
            if quantity == 0:
                quantity = position.shares
        
        holding = PortfolioHolding(
            symbol=symbol,
            buy_price=buy_price,
            buy_date=datetime.now().strftime("%Y-%m-%d"),
            allocation=allocation,
            quantity=quantity,
        )
        self.holdings.append(holding)
        
        # Remove from watchlist if present
        if symbol in self.watchlist:
            self.watchlist.remove(symbol)
        
        self._save()
        logger.info(f"✅ Added {symbol} @ Rs.{buy_price:.2f} ({allocation*100:.0f}% allocation)")
        return True
    
    def add_to_watchlist(self, symbol: str):
        """Add symbol to watchlist (for when portfolio is full)."""
        symbol = symbol.upper()
        if symbol not in self.watchlist and not any(h.symbol == symbol for h in self.holdings):
            self.watchlist.append(symbol)
            self._save()
    
    def remove_position(self, symbol: str, exit_price: float = None, reason: str = "MANUAL"):
        """Remove a position from portfolio."""
        symbol = symbol.upper()
        for i, h in enumerate(self.holdings):
            if h.symbol == symbol:
                # Division guard for buy_price
                pnl = ((exit_price / max(h.buy_price, 0.001)) - 1) * 100 if exit_price and h.buy_price > 0 else 0
                logger.info(f"🔴 Sold {symbol} @ Rs.{exit_price:.2f} | P&L: {pnl:+.1f}% | Reason: {reason}")
                self.holdings.pop(i)
                self._save()
                return True
        return False
    
    def get_ltp(self, symbol: str) -> float:
        """Fetch current LTP for a symbol."""
        try:
            price_rows = get_price_history_with_open(symbol, days=1)
            if price_rows:
                return float(price_rows[0].get("close", 0) or price_rows[0].get("open", 0) or 0)
        except:
            pass
        return 0.0
    
    def check_exit_signals(self, holding: PortfolioHolding, ltp: float) -> dict:
        """
        Check exit signals for a holding.
        
        Returns dict with:
        - can_exit: bool (False if within 7-day hold)
        - signal: None | 'TARGET' | 'STOP_LOSS' | 'MAX_HOLD'
        - status: str (display status)
        """
        days = holding.days_held
        pnl_pct = ((ltp / holding.buy_price) - 1) * 100 if ltp > 0 and holding.buy_price > 0 else 0
        
        # Within hold period - NO EXIT regardless of signals
        if days <= self.HOLD_DAYS:
            return {
                "can_exit": False,
                "signal": None,
                "status": f"🟢 HOLD (Day {days}/{self.HOLD_DAYS})",
                "pnl_pct": pnl_pct,
                "days": days,
            }
        
        # After hold period - check exit triggers
        signal = None
        status = "🟡 REVIEW"
        
        if pnl_pct >= self.TARGET_PCT * 100:  # +10%
            signal = "TARGET"
            status = f"🎯 SELL TARGET (+{pnl_pct:.1f}%)"
        elif pnl_pct <= -self.STOP_LOSS_PCT * 100:  # -5%
            signal = "STOP_LOSS"
            status = f"🛑 SELL STOP ({pnl_pct:.1f}%)"
        elif days >= self.MAX_HOLD_DAYS:
            signal = "MAX_HOLD"
            status = f"⏰ SELL/REVIEW (Day {days})"
        else:
            status = f"🟡 Day {days} | P&L: {pnl_pct:+.1f}%"
        
        return {
            "can_exit": True,
            "signal": signal,
            "status": status,
            "pnl_pct": pnl_pct,
            "days": days,
        }
    
    def print_status(self, scan_results: List = None):
        """
        Print portfolio status in the exact required format.
        
        Args:
            scan_results: Optional list of today's scan results to show
        """
        today = datetime.now().strftime("%d-%b")
        
        print("\n" + "=" * 60)
        print(f"📊 PORTFOLIO STATUS (Auto-Updated) ({today})")
        print("=" * 60)
        
        if not self.holdings:
            print("\n   📭 Portfolio EMPTY - Ready to buy TOP 3 from scan")
            print(f"   Max allocation: {self.MAX_ALLOCATION*100:.0f}% ({self.MAX_STOCKS} stocks × {self.DEFAULT_ALLOCATION*100:.0f}% each)")
            print("\n   🔄 Run: python tools/paper_trader.py --buy-picks")
        else:
            print(f"\n{'SYMBOL':<8} | {'BUY ₹':>8} | {'DAYS':>6} | {'P&L% (LIVE)':>13} | {'LTP ₹ (LIVE)':>14} | STATUS")
            print("-" * 80)
            
            total_pnl = 0
            exit_signals = []
            next_review_date = None
            
            for h in self.holdings:
                ltp = self.get_ltp(h.symbol)
                exit_info = self.check_exit_signals(h, ltp)
                pnl = exit_info["pnl_pct"]
                total_pnl += pnl
                
                # Add up/down arrows
                if pnl > 0:
                    pnl_str = f"+{pnl:.1f}% ↑"
                elif pnl < 0:
                    pnl_str = f"{pnl:.1f}% ↓"
                else:
                    pnl_str = f"{pnl:+.1f}%"
                
                ltp_str = f"{ltp:.0f}"
                if pnl > 0:
                    ltp_str += " ↑"
                elif pnl < 0:
                    ltp_str += " ↓"
                
                days_str = f"{exit_info['days']}/{self.HOLD_DAYS}"
                
                print(f"{h.symbol:<8} | {h.buy_price:>8.0f} | {days_str:>6} | {pnl_str:>13} | {ltp_str:>14} | {exit_info['status']}")
                
                # Track exit signals
                if exit_info["signal"]:
                    exit_signals.append((h.symbol, exit_info["signal"], exit_info["status"], pnl))
                
                # Calculate next review date (Day 7)
                if exit_info["days"] < self.HOLD_DAYS:
                    buy_date = datetime.strptime(h.buy_date, "%Y-%m-%d")
                    review_date = buy_date + timedelta(days=self.HOLD_DAYS)
                    if next_review_date is None or review_date < next_review_date:
                        next_review_date = review_date
            
            print("-" * 80)
            avg_pnl = total_pnl / len(self.holdings) if self.holdings else 0
            print(f"TOTAL: {self.total_allocation*100:.1f}% allocation | {avg_pnl:+.1f}% P&L", end="")
            
            if next_review_date:
                print(f" | Next review: {next_review_date.strftime('%d-%b')}")
            else:
                print()
            
            # Show exit signals section
            if exit_signals:
                print("\n" + "=" * 60)
                print("🚨 EXIT SIGNALS (Take Action!)")
                print("=" * 60)
                for sym, signal, status, pnl in exit_signals:
                    if signal == "TARGET":
                        print(f"   ✅ {sym}: {status}")
                        print(f"      → SELL NOW for profit! (+{pnl:.1f}%)")
                    elif signal == "STOP_LOSS":
                        print(f"   🛑 {sym}: {status}")
                        print(f"      → SELL NOW to limit loss! ({pnl:.1f}%)")
                    elif signal == "MAX_HOLD":
                        print(f"   ⏰ {sym}: {status}")
                        print(f"      → Review position, consider exit")
            else:
                # Only show if within hold period
                if any(self.check_exit_signals(h, 0)["days"] <= self.HOLD_DAYS for h in self.holdings):
                    print("\n⚠️ NO SELL SIGNALS (In hold period)")
        
        # Show today's scan results
        if scan_results:
            print("\n" + "=" * 60)
            print("🎯 TODAY'S SCAN RESULTS")
            print("=" * 60)
            
            top_symbols = ", ".join([f"{s.symbol}({s.total_score:.0f})" for s in scan_results[:5]])
            print(f"   Top picks: {top_symbols}")
            
            if self.is_full:
                print(f"   → Portfolio FULL ({self.total_allocation*100:.0f}%) → Watchlist only")
                # Add to watchlist
                for s in scan_results[:5]:
                    self.add_to_watchlist(s.symbol)
            else:
                slots = self.available_slots
                print(f"   → {slots} slot(s) available → Can buy top {slots}")
        
        # Show watchlist
        if self.watchlist:
            print(f"\n   📋 Watchlist: {', '.join(self.watchlist[:10])}")
        
        # Show how live updates work
        if self.holdings:
            print("\n" + "=" * 60)
            print("🔄 AUTO-UPDATE INFO")
            print("=" * 60)
            print("   ✅ LTP fetched LIVE from NEPSE API")
            print("   ✅ P&L calculated automatically")
            print("   ✅ Exit signals checked every run")
            print("   ✅ Run anytime: Market hours → Live | Closed → Last close")

        
        # Show exit levels for each holding
        if self.holdings:
            print("\n" + "=" * 60)
            print("⚠️ EXIT LEVELS")
            print("=" * 60)
            for h in self.holdings:
                print(f"   {h.symbol}: +10% target = Rs.{h.target_price:.0f} | -5% stop = Rs.{h.stop_loss:.0f}")
    
    def buy_top_picks(self, scan_results: List, max_buys: int = None) -> List[str]:
        """
        Buy top picks from scan results up to portfolio limits.
        
        Returns list of symbols bought.
        """
        max_buys = max_buys or self.available_slots
        bought = []
        
        for stock in scan_results:
            if len(bought) >= max_buys:
                break
            if not self.can_add_position():
                break
            
            # Get entry price (use LTP or scan entry price)
            # FIX: Always apply slippage if not already included
            entry_price = getattr(stock, 'entry_price_with_slippage', None)
            if not entry_price or entry_price <= 0:
                raw_ltp = getattr(stock, 'ltp', 0)
                if raw_ltp <= 0:
                    raw_ltp = self.get_ltp(stock.symbol)
                # Always apply 1.5% slippage for NEPSE illiquidity
                entry_price = raw_ltp * 1.015 if raw_ltp > 0 else 0
            
            if entry_price > 0:
                if self.add_position(stock.symbol, entry_price):
                    bought.append(stock.symbol)
        
        return bought


@dataclass
class PaperTrade:
    """Represents a virtual trade in the paper portfolio."""
    id: int
    symbol: str
    scan_date: str
    score: float
    entry_price: float
    entry_price_slippage: float
    target_price: float
    stop_loss: float
    stop_loss_slippage: float
    status: str  # 'RECOMMENDED', 'BOUGHT', 'TARGET_HIT', 'STOPPED_OUT', 'EXPIRED', 'SKIPPED'
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    profit_loss_pct: Optional[float] = None
    hold_days: int = 0


def classify_stock_risk(stock, screener=None) -> dict:
    """
    Risk classification with hard veto rules for momentum workflow.

    Classification (for momentum score >= 70):
    - GOOD: all veto checks pass
    - RISKY: exactly 1 veto reason
    - VETO: 2+ veto reasons
    """
    score = float(getattr(stock, "total_score", 0) or 0)
    eps = float(getattr(stock, "eps", 0) or 0)
    roe = float(getattr(stock, "roe", 0) or 0)
    pe = float(getattr(stock, "pe_ratio", 0) or 0)
    rsi = float(getattr(stock, "rsi", 0) or 0)
    current_price = float(getattr(stock, "ltp", 0) or 0)

    risk_reasons: List[str] = []
    validation = {"status": "VETOED", "veto_reasons": [], "1m_net": 0, "1w_net": 0}

    # Dual-timeframe + hard-veto rules from screener (if available)
    if screener and hasattr(screener, "dual_timeframe_validation"):
        try:
            validation = screener.dual_timeframe_validation(stock)
            risk_reasons.extend(validation.get("veto_reasons", []))
        except Exception as e:
            logger.warning(f"Dual timeframe validation failed for {getattr(stock, 'symbol', 'UNKNOWN')}: {e}")
            risk_reasons.append("Dual timeframe validation unavailable")

    # Technical hard gates
    # FIX #6: Handle RSI=0 and None properly
    if rsi is None or rsi <= 0:
        if screener:
            try:
                hist = screener.fetcher.safe_fetch_data(stock.symbol, days=30, min_rows=15)
                rsi_fallback = safe_rsi(hist["close"], period=14) if not hist.empty else None
                if rsi_fallback is not None:
                    rsi = float(rsi_fallback)
                else:
                    risk_reasons.append("RSI unavailable (insufficient data)")
            except Exception as e:
                logger.debug(f"RSI fallback failed for {stock.symbol}: {e}")
                risk_reasons.append("RSI unavailable")
        else:
            risk_reasons.append("RSI unavailable")
    
    # Now check RSI bounds if we have a valid value
    if rsi is not None and rsi > 0:
        if rsi > 70:
            risk_reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi < 40:
            risk_reasons.append(f"RSI below momentum zone ({rsi:.1f})")

    # Fundamental hard gates
    if eps <= 0:
        risk_reasons.append(f"Negative EPS (Rs. {eps:.2f})")
    if roe <= 0:
        risk_reasons.append(f"Weak/Negative ROE ({roe:.1f}%)")

    # VWAP premium gate (14D)
    # FIX #4: Fix VWAP "unavailable" always triggered logic
    vwap_14d = None
    vwap_premium_pct = 0.0
    vwap_available = False
    
    if screener:
        try:
            hist = screener.fetcher.safe_fetch_data(stock.symbol, days=20, min_rows=5)
            if not hist.empty:
                vwap_14d = safe_vwap(hist.tail(14))
                if vwap_14d is not None and vwap_14d > 0:
                    vwap_available = True
        except Exception as e:
            logger.warning(f"VWAP fetch failed for {stock.symbol}: {e}")

    if vwap_available and current_price > 0:
        # Division guard for vwap_14d
        vwap_premium_pct = ((current_price / max(vwap_14d, 0.001)) - 1) * 100 if vwap_14d > 0 else 0
        if vwap_premium_pct > 10:
            risk_reasons.append(f"Price overextended vs 14D VWAP (+{vwap_premium_pct:.1f}%)")
    elif not vwap_available:
        # Only add this if VWAP truly couldn't be calculated
        risk_reasons.append("14D VWAP unavailable")

    # De-duplicate while preserving order
    seen = set()
    risk_reasons = [r for r in risk_reasons if not (r in seen or seen.add(r))]

    if score < 70:
        risk_tier = "NOT_QUALIFIED"
        entry_allowed = False
        position_guidance = "Not qualified for momentum setup"
    else:
        if len(risk_reasons) == 0:
            risk_tier = "GOOD"
            entry_allowed = True
            position_guidance = "GOOD: 3-5% portfolio"
        elif len(risk_reasons) == 1:
            risk_tier = "RISKY"
            entry_allowed = False
            position_guidance = "RISKY: 1-2% portfolio or paper-trade"
        else:
            risk_tier = "VETO"
            entry_allowed = False
            position_guidance = "VETO: Paper-trade only"

    return {
        "risk_tier": risk_tier,
        "risk_reasons": risk_reasons,
        "position_guidance": position_guidance,
        "entry_allowed": entry_allowed,
        "is_ideal_setup": (risk_tier == "GOOD"),
        "eps": eps,
        "roe": roe,
        "rsi": rsi,
        "pe": pe,
        "vwap_14d": vwap_14d or 0.0,
        "current_price": current_price,
        "vwap_premium_pct": vwap_premium_pct,
        "validation": validation,
    }


def get_sector_alternatives(
    symbol: str,
    sector: str,
    max_price: float = None,
    top_n: int = 5,
    strategy: str = "momentum",
) -> List[dict]:
    """
    Get sector alternatives using the SAME scoring engine as daily scan.
    
    This ensures single-stock analysis shows the exact same top stocks
    that would appear in `python paper_trader.py --scan --sector=hydro`.
    
    Args:
        symbol: Current stock symbol to exclude from results
        sector: Sector name to scan (e.g., "Hydro Power")
        max_price: Optional max price filter
        top_n: Number of alternatives to return
        strategy: Scoring strategy ("momentum" or "value")
    
    Returns:
        List of dicts with symbol, score, risk_tier, ltp, dump_risk
    """
    try:
        # Run full screener analysis for the sector (same as daily scan)
        screener = MasterStockScreener(
            strategy=strategy,
            target_sector=sector,
            max_price=max_price,
        )
        
        # Run the same scoring pipeline as daily scan
        results = screener.run_full_analysis(min_score=0, top_n=50, quick_mode=False)
        
        if not results:
            logger.debug(f"No results from sector scan for {sector}")
            return []
        
        # Build alternatives list (exclude current symbol)
        alternatives = []
        for stock in results:
            if stock.symbol.upper() == symbol.upper():
                continue
            
            # Get risk classification (same as daily scan)
            risk_class = classify_stock_risk(stock, screener=screener)
            
            alternatives.append({
                'symbol': stock.symbol,
                'name': stock.name,
                'score': stock.total_score,
                'risk_tier': risk_class['risk_tier'],
                'dump_risk': stock.distribution_risk,
                'ltp': stock.ltp,
                'entry_price': stock.entry_price_with_slippage,
                'target_price': stock.target_price,
                'risk_reasons': risk_class['risk_reasons'],
                'position_guidance': risk_class['position_guidance'],
            })
            
            if len(alternatives) >= top_n:
                break
        
        return alternatives
        
    except Exception as e:
        logger.warning(f"get_sector_alternatives failed: {e}")
        return []


class PaperTrader:
    """
    📈 Paper Trading Engine for Forward-Testing the Algorithm
    
    WORKFLOW:
    1. `--action=scan` → Recommends stocks, saves as "RECOMMENDED"
    2. `--action=buy --symbol=NICA --price=368` → Confirms purchase, changes to "BOUGHT"
    3. `--action=update` → Only tracks "BOUGHT" positions for target/stop
    4. `--action=skip --symbol=NICA` → Marks as "SKIPPED" (didn't buy)
    """
    
    # Configuration
    STARTING_CAPITAL = 1000000  # Rs. 10 Lakh virtual capital
    MAX_POSITION_PCT = 0.20     # Max 20% per stock
    MIN_SCORE = 75             # Only paper-trade high-confidence picks
    TOP_N = 5                  # Track top 5 picks daily
    HOLD_DAYS_MAX = 10         # Auto-expire after 10 trading days
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.fetcher = NepseFetcher()
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for paper trading records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Daily scans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TEXT NOT NULL,
                scan_time TEXT NOT NULL,
                market_regime TEXT,
                is_bear_market INTEGER,
                total_stocks_analyzed INTEGER,
                stocks_passed INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Paper trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                symbol TEXT NOT NULL,
                name TEXT,
                scan_date TEXT NOT NULL,
                score REAL NOT NULL,
                rank INTEGER,
                entry_price REAL NOT NULL,
                entry_price_slippage REAL NOT NULL,
                target_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                stop_loss_slippage REAL NOT NULL,
                pillar1_broker REAL,
                pillar2_unlock REAL,
                pillar3_fundamental REAL,
                pillar4_technical REAL,
                market_penalty REAL,
                buyer_dominance_pct REAL,
                rsi REAL,
                volume_spike REAL,
                status TEXT DEFAULT 'OPEN',
                exit_price REAL,
                exit_date TEXT,
                profit_loss_pct REAL,
                hold_days INTEGER DEFAULT 0,
                expected_hold_days INTEGER DEFAULT 7,
                max_hold_days INTEGER DEFAULT 15,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scan_id) REFERENCES daily_scans(id)
            )
        """)
        
        # Price tracking table (for monitoring open positions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                close_price REAL NOT NULL,
                high_price REAL,
                low_price REAL,
                volume INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Performance summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                avg_profit_pct REAL,
                avg_loss_pct REAL,
                total_return_pct REAL,
                sharpe_ratio REAL,
                max_drawdown_pct REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migration: Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE paper_trades ADD COLUMN expected_hold_days INTEGER DEFAULT 7")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE paper_trades ADD COLUMN max_hold_days INTEGER DEFAULT 15")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        conn.commit()
        conn.close()
        logger.info(f"📊 Paper trading database initialized: {self.db_path}")
    
    def _print_stakeholder_report(self, results: List[ScreenedStock], total_analyzed: int, strategy: str = "value"):
        """Print a narrative report explaining the selection logic to stakeholders."""
        
        # Determine weights based on strategy
        tech_weight = 30
        fund_weight = 20
        if strategy == "momentum":
            tech_weight = 40
            fund_weight = 10
            
        print("\n" + "=" * 70)
        print(f"🏛️ STAKEHOLDER REPORT: SELECTION LOGIC (Strategy: {strategy.upper()})")
        print("=" * 70)
        print(f"1. UNIVERSE: We started with {total_analyzed} NEPSE listed companies.")
        
        print(f"\n2. FILTERING PROCESS (The Funnel):")
        print(f"   • Removed Illiquid Stocks (Turnover < Rs. 1 Crore)")
        print(f"   • Removed Penny Stocks (Price < Rs. 200)")
        print(f"   • Removed High Risk Promoters (Unlock < 30 days)")
        print(f"   • Removed Bearish Trends (Index < 50 EMA)")
        
        print(f"\n3. SCORING MODEL (The 4 Pillars):")
        print(f"   • Technical ({tech_weight}%): Moving Averages, RSI, MACD")
        print(f"   • Broker (30%): Smart Money Accumulation")
        print(f"   • Fundamentals ({fund_weight}%): PE Ratio, EPS Growth")
        print(f"   • Unlock Risk (20%): Supply Shock Avoidance")
        
        print(f"\n4. FINAL SELECTION (Top {len(results)} Winners):")
        for i, stock in enumerate(results, 1):
            print(f"   #{i} {stock.symbol} ({stock.total_score:.0f}/100) was chosen because:")
            print(f"       • {stock.verdict_reason}")
            
            # Show specific winning factors
            factors = []
            if stock.pillar4_technical >= (tech_weight * 0.66): factors.append(f"Strong Technicals ({stock.pillar4_technical:.0f}/{tech_weight})")
            if stock.pillar1_broker >= 20: factors.append(f"Broker Accumulation ({stock.pillar1_broker:.0f}/30)")
            if stock.pillar3_fundamental >= (fund_weight * 0.75): factors.append(f"Solid Fundamentals ({stock.pillar3_fundamental:.0f}/{fund_weight})")
            
            if factors:
                print(f"       • DRIVERS: {', '.join(factors)}")
                
            if hasattr(stock, 'breakdown') and stock.breakdown.bonuses:
                print(f"       • BONUS: {', '.join(stock.breakdown.bonuses)}")
            
            print(f"       • TARGET: Rs. {stock.target_price:.0f} (+10%) | STOP: Rs. {stock.stop_loss:.0f} (-5%)")
            print("")

    def _print_stakeholder_report_with_classification(
        self,
        results: List[ScreenedStock],
        good_setups: List[ScreenedStock],
        risky_watch: List[ScreenedStock],
        vetoed_watch: List[ScreenedStock],
        not_qualified: List[ScreenedStock],
        total_analyzed: int,
        strategy: str = "value",
    ):
        """
        Print a narrative report with risk classification for stakeholders.
        
        This enhanced report clearly separates GOOD setups from RISKY ones,
        explaining WHY each classification was made.
        """
        
        tech_weight = 40 if strategy == "momentum" else 30
        fund_weight = 10 if strategy == "momentum" else 20
            
        print("\n" + "=" * 70)
        print(f"🏛️ STAKEHOLDER REPORT: RISK-CLASSIFIED ANALYSIS")
        print(f"   Strategy: {strategy.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
        print("=" * 70)
        
        # Summary Stats
        print(f"\n📊 SUMMARY STATISTICS:")
        print(f"   Universe Screened:     {total_analyzed} stocks")
        print(f"   Momentum Qualified:    {len(results)} stocks (Score ≥ 70)")
        print(f"   ✅ Good Setups:         {len(good_setups)} (real-trade eligible)")
        print(f"   ⚠️ Risky Watch:         {len(risky_watch)} (1 veto reason)")
        print(f"   🚫 Veto:                {len(vetoed_watch)} (2+ veto reasons)")
        print(f"   ⚪ Not Qualified:       {len(not_qualified)} (score < 70)")
        
        # Good Setups Criteria
        print(f"\n🎯 GOOD SETUP CRITERIA:")
        print(f"   A stock is classified as 'GOOD' when ALL conditions are met:")
        print(f"   • Momentum Score ≥ 70")
        print(f"   • 1M net holdings > 0 and 1W net holdings > 0")
        print(f"   • RSI ≤ 70")
        print(f"   • EPS > 0 and ROE > 0")
        print(f"   • Price ≤ 10% above 14D VWAP")
        
        print(f"\n⚠️ RISKY CRITERIA:")
        print(f"   Exactly 1 hard-veto reason while score ≥ 70")
        print(f"   • Suggested size: 1-2% or paper trade")
        
        print(f"\n🚫 VETO CRITERIA:")
        print(f"   2+ hard-veto reasons while score ≥ 70")
        print(f"   • Paper-trade only")
        
        # Paper Only Criteria
        print(f"\n⚪ NOT QUALIFIED CRITERIA:")
        print(f"   • Momentum score < 70")
        
        # Good Setups Detail
        if good_setups:
            print(f"\n" + "-" * 70)
            print(f"✅ GOOD SETUPS - Recommended for Real Trades (3-5% portfolio)")
            print("-" * 70)
            for i, stock in enumerate(good_setups, 1):
                risk_class = getattr(stock, '_risk_class', {})
                print(f"\n   #{i} {stock.symbol} ({stock.total_score:.0f}/100)")
                print(f"       Entry: Rs.{stock.entry_price_with_slippage:.2f} → Target: Rs.{stock.target_price:.2f} (+10%)")
                print(f"       Position Size: {risk_class.get('position_guidance', 'Normal')}")
                if risk_class.get('is_ideal_setup'):
                    print(f"       ⭐ IDEAL SETUP - All 4 conditions met perfectly")
        
        # Risky Detail
        if risky_watch:
            print(f"\n" + "-" * 70)
            print(f"⚠️ RISKY WATCH - Limited Position Sizing")
            print("-" * 70)
            for i, stock in enumerate(risky_watch, 1):
                risk_class = getattr(stock, '_risk_class', {})
                print(f"\n   #{i} {stock.symbol} ({stock.total_score:.0f}/100)")
                print(f"       Reason: {', '.join(risk_class.get('risk_reasons', []))}")
                print(f"       Guidance: {risk_class.get('position_guidance', '1-2% or paper')}")

        # Vetoed Detail
        if vetoed_watch:
            print(f"\n" + "-" * 70)
            print(f"🚫 VETO - No Real-Money Auto Entry")
            print("-" * 70)
            for i, stock in enumerate(vetoed_watch, 1):
                risk_class = getattr(stock, '_risk_class', {})
                print(f"\n   #{i} {stock.symbol} ({stock.total_score:.0f}/100)")
                print(f"       Failed Signals: {', '.join(risk_class.get('risk_reasons', []))}")
                print(f"       Guidance: {risk_class.get('position_guidance', 'Paper-trade only')}")
        
        # Not Qualified Detail
        if not_qualified:
            print(f"\n" + "-" * 70)
            print(f"⚪ NOT QUALIFIED - Score below momentum threshold")
            print("-" * 70)
            for i, stock in enumerate(not_qualified, 1):
                print(f"\n   #{i} {stock.symbol} ({stock.total_score:.0f}/100)")
                print(f"       Status: Not qualified for momentum setup")
        
        # Philosophy Note
        print(f"\n" + "=" * 70)
        print(f"💡 PHILOSOPHY")
        print("=" * 70)
        print(f"   • We NEVER hide any momentum-qualified stock from the scan")
        print(f"   • But we RESTRICT auto-pushing risky names as real-money entries")
        print(f"   • Use 'analyze_single_stock' for detailed reports on any stock")
        print(f"   • The detailed report is the final judge for trading decisions")
        print("")
    
    def run_daily_scan(
        self, 
        quick_mode: bool = False,
        with_news: bool = False,
        with_ai: bool = False,
        headless: bool = True,
        strategy: str = "standard",
        target_sector: str = None,
        max_price: float = None,
    ) -> Dict:
        """
        🔍 Run the daily scan and save top picks to database.
        
        This should be run every trading day at 3:15 PM after market close.
        
        Args:
            quick_mode: If True, only analyze top 50 stocks by volume (5x faster)
            with_news: If True, scrape news using Playwright for top picks
            with_ai: If True, get OpenAI AI verdict for top picks
            headless: If False, show browser window (default True)
            strategy: "value" or "momentum" (Trend Following)
            target_sector: Optional sector to filter by (e.g. "bank", "finance")
            max_price: Maximum stock price budget filter (e.g. 500 = skip stocks > Rs.500)
        """
        sector_msg = f" | Sector: {target_sector.upper()}" if target_sector else ""
        price_msg = f" | Max Price: Rs.{max_price:.0f}" if max_price else ""
        logger.info("=" * 70)
        logger.info(f"📊 PAPER TRADER - Running Daily Scan (Strategy: {strategy.upper()}{sector_msg}{price_msg})")
        if quick_mode:
            logger.info("⚡ QUICK MODE ENABLED - Analyzing top 50 stocks only")
        if with_news:
            logger.info(f"📰 NEWS SCRAPING ENABLED - Will scrape news for top picks (Headless: {headless})")
        if with_ai:
            logger.info("🤖 AI ANALYSIS ENABLED - Will get AI verdicts for top picks")
        logger.info("=" * 70)
        
        # Run the 4-Pillar analysis
        screener = MasterStockScreener(strategy=strategy, target_sector=target_sector, max_price=max_price)
        regime, regime_reason = screener.check_market_regime()
        
        # 🛑 KILL SWITCH: PANIC MODE
        if regime == "PANIC":
            logger.critical("=" * 70)
            logger.critical("🚨 KILL SWITCH ACTIVATED: PANIC MODE")
            logger.critical("🛑 NO BUY SIGNALS WILL BE GENERATED TODAY")
            logger.critical(f"   Reason: {regime_reason}")
            logger.critical("=" * 70)
            return {
                "success": False, 
                "message": "PANIC MODE - Kill Switch activated. No trades recommended.",
                "regime": "PANIC",
                "reason": regime_reason
            }
        
        # Map regime to boolean for backward compatibility
        is_bear = regime == "BEAR"
        
        # Set max scores for display based on strategy
        max_broker = 30.0
        max_unlock = 20.0
        max_fund = 20.0
        max_tech = 30.0
        
        if strategy == "momentum":
            max_fund = 10.0
            max_tech = 40.0
            
        results = screener.run_full_analysis(
            min_score=self.MIN_SCORE, 
            top_n=self.TOP_N,
            quick_mode=quick_mode
        )
        
        if not results:
            # Check if it's because of PANIC mode (empty results)
            if regime == "PANIC":
                logger.critical("🛑 KILL SWITCH: No recommendations during PANIC mode!")
                return {"success": False, "message": "PANIC MODE - No trades allowed", "regime": regime}
            logger.warning("No stocks passed the minimum score threshold!")
            return {"success": False, "message": "No qualifying stocks found", "regime": regime}
        
        # Enrich with news and AI analysis if requested
        if with_news or with_ai:
            results = screener.enrich_with_news_and_ai(
                stocks=results,
                scrape_news=with_news,
                use_ai=with_ai,
                headless=headless,
            )
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        scan_date = datetime.now().strftime("%Y-%m-%d")
        scan_time = datetime.now().strftime("%H:%M:%S")
        
        # Insert scan record
        cursor.execute("""
            INSERT INTO daily_scans 
            (scan_date, scan_time, market_regime, is_bear_market, total_stocks_analyzed, stocks_passed)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            scan_date,
            scan_time,
            regime,
            1 if is_bear else 0,
            299,  # Approximate total stocks
            len(results)
        ))
        scan_id = cursor.lastrowid
        
        # Insert paper trades as RECOMMENDED (not yet bought)
        for rank, stock in enumerate(results, 1):
            cursor.execute("""
                INSERT INTO paper_trades 
                (scan_id, symbol, name, scan_date, score, rank,
                 entry_price, entry_price_slippage, target_price, 
                 stop_loss, stop_loss_slippage,
                 pillar1_broker, pillar2_unlock, pillar3_fundamental, pillar4_technical,
                 market_penalty, buyer_dominance_pct, rsi, volume_spike, 
                 expected_hold_days, max_hold_days, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RECOMMENDED')
            """, (
                scan_id,
                stock.symbol,
                stock.name[:50] if stock.name else "",
                scan_date,
                stock.total_score,
                rank,
                stock.entry_price,
                stock.entry_price_with_slippage,
                stock.target_price,
                stock.stop_loss,
                stock.stop_loss_with_slippage,
                stock.pillar1_broker,
                stock.pillar2_unlock,
                stock.pillar3_fundamental,
                stock.pillar4_technical,
                stock.market_regime_penalty,
                stock.buyer_dominance_pct,
                stock.rsi,
                stock.volume_spike,
                getattr(stock, 'expected_holding_days', 7),
                getattr(stock, 'max_holding_days', 15)
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Saved {len(results)} paper trades for {scan_date}")
        
        # ========== RISK CLASSIFICATION ==========
        # Classify each stock into GOOD vs RISKY tiers
        # Philosophy: NEVER hide momentum-qualified stocks, but restrict auto-entry for risky setups
        good_setups = []     # Momentum>=70 and all hard-veto signals pass
        risky_watch = []     # Momentum>=70 with one veto reason
        vetoed_watch = []    # Momentum>=70 with multiple veto reasons
        not_qualified = []   # Momentum<70 (kept visible in detailed section)
        
        for stock in results:
            risk_class = classify_stock_risk(stock, screener=screener)
            stock._risk_class = risk_class  # Attach for later use
            
            if risk_class["risk_tier"] == "GOOD":
                good_setups.append(stock)
            elif risk_class["risk_tier"] == "RISKY":
                risky_watch.append(stock)
            elif risk_class["risk_tier"] == "VETO":
                vetoed_watch.append(stock)
            else:
                not_qualified.append(stock)
        
        # Print summary
        print("\n" + "=" * 70)
        print(f"📊 DAILY SCAN COMPLETE - {scan_date}")
        print("=" * 70)
        print(f"Market Regime: {'🐻 BEAR' if is_bear else '🐂 BULL'}")
        print(f"Stocks Analyzed: {50 if quick_mode else 299} | Momentum Qualified: {len(results)}")
        print(f"✅ GOOD: {len(good_setups)} | ⚠️ RISKY: {len(risky_watch)} | 🚫 VETO: {len(vetoed_watch)}")
        
        # ========== SECTION 1: GOOD SETUPS (Real-money tradeable) ==========
        if good_setups:
            print("\n" + "=" * 70)
            print("✅ GOOD SETUPS (3-5% portfolio)")
            print("   These stocks passed dual timeframe and hard-veto checks")
            print("=" * 70)
            
            for rank, stock in enumerate(good_setups, 1):
                risk_class = stock._risk_class
                raw_info = f"(Raw: {stock.raw_score:.1f})" if hasattr(stock, 'raw_score') and stock.raw_score > 100 else ""
                print(f"\n   #{rank} {stock.symbol:<10} Score: {stock.total_score:.0f}/100 {raw_info}")
                print(f"       💰 Entry: Rs.{stock.entry_price_with_slippage:.2f} | 🎯 Target: Rs.{stock.target_price:.2f} | 🛑 Stop: Rs.{stock.stop_loss_with_slippage:.2f}")
                
                expected_hold = getattr(stock, 'expected_holding_days', 7)
                max_hold = getattr(stock, 'max_holding_days', 15)
                print(f"       📅 HOLD: {expected_hold}-{max_hold} days")
                print(f"       📊 RSI: {stock.rsi:.1f} | EPS: Rs.{risk_class['eps']:.2f} | ROE: {risk_class['roe']:.1f}%")
                print(f"       💼 Position Size: {risk_class['position_guidance']}")
                
                if risk_class.get('is_ideal_setup'):
                    print(f"       ⭐ IDEAL SETUP - All conditions met!")
        
        # ========== SECTION 2: RISKY WATCH (Limited size) ==========
        if risky_watch:
            print("\n" + "=" * 70)
            print("⚠️ RISKY WATCH (1-2% portfolio)")
            print("=" * 70)
            for rank, stock in enumerate(risky_watch, 1):
                risk_class = stock._risk_class
                print(f"\n   #{rank} {stock.symbol:<10} ⚠️ RISKY | Score: {stock.total_score:.0f}/100")
                print(f"       Reason: {', '.join(risk_class['risk_reasons'])}")
                print(f"       Guidance: {risk_class['position_guidance']}")

        # ========== SECTION 3: VETO (No real-money entry) ==========
        if vetoed_watch:
            print("\n" + "=" * 70)
            print("🚫 VETO SETUPS (Paper-trade only)")
            print("=" * 70)
            
            for rank, stock in enumerate(vetoed_watch, 1):
                risk_class = stock._risk_class
                raw_info = f"(Raw: {stock.raw_score:.1f})" if hasattr(stock, 'raw_score') and stock.raw_score > 100 else ""
                print(f"\n   #{rank} {stock.symbol:<10} 🚫 VETO | Score: {stock.total_score:.0f}/100 {raw_info}")
                
                print(f"       🚩 FAILED SIGNALS:")
                for reason in risk_class['risk_reasons']:
                    print(f"          {reason}")
                
                print(f"       🚫 NO AUTO-ENTRY - {risk_class['position_guidance']}")
                
                print(f"       📊 RSI: {stock.rsi:.1f} | EPS: Rs.{risk_class['eps']:.2f} | ROE: {risk_class['roe']:.1f}% | VWAP Premium: +{risk_class.get('vwap_premium_pct', 0):.1f}%")
        
        # ========== SECTION 4: NOT QUALIFIED ==========
        if not_qualified:
            print("\n" + "=" * 70)
            print("⚪ NOT QUALIFIED (Momentum < 70)")
            print("   Visible for transparency, but not actionable.")
            print("=" * 70)
            
            for rank, stock in enumerate(not_qualified, 1):
                risk_class = stock._risk_class
                print(f"\n   #{rank} {stock.symbol:<10} Score: {stock.total_score:.0f}/100")
                print(f"       Status: Not qualified for momentum setup")
        
        # ========== DETAILED ANALYSIS (for all stocks) ==========
        print("\n" + "=" * 70)
        print("📋 DETAILED ANALYSIS (All momentum-qualified stocks)")
        print("=" * 70)
        
        for rank, stock in enumerate(results, 1):
            risk_class = stock._risk_class
            tier_emoji = {"GOOD": "✅", "RISKY": "⚠️", "VETO": "🚫", "NOT_QUALIFIED": "⚪"}.get(risk_class["risk_tier"], "❓")
            raw_info = f"(Raw: {stock.raw_score:.1f})" if hasattr(stock, 'raw_score') and stock.raw_score > 100 else ""
            print(f"\n   #{rank} {stock.symbol:<10} {tier_emoji} {risk_class['risk_tier']} | Score: {stock.total_score:.0f}/100 {raw_info}")
            
            # DISTRIBUTION RISK ALERT (VWAP-Based)
            dist_risk = getattr(stock, 'distribution_risk', '')
            broker_profit = getattr(stock, 'broker_profit_pct', 0)
            vwap_cost = getattr(stock, 'broker_avg_cost', 0)
            dist_warning = getattr(stock, 'distribution_warning', '')
            
            if dist_risk and dist_risk != "N/A":
                risk_emoji = {"LOW": "✅", "MEDIUM": "⚡", "HIGH": "⚠️", "CRITICAL": "🚨"}.get(dist_risk, "❓")
                print(f"       {risk_emoji} DISTRIBUTION RISK: {dist_risk}")
                # Always use 1M for broker avg cost (fixed bug: was using 1W for momentum)
                print(f"          1M Broker Avg: Rs.{vwap_cost:.2f} | Broker Profit: +{broker_profit:.1f}%")
                if dist_risk in ["HIGH", "CRITICAL"] and dist_warning:
                    print(f"          ⚠️ WARNING: {dist_warning}")
            
            # Verdict
            print(f"       🧠 Verdict: {stock.verdict_reason}")
            
            # Pillar Scores
            print(f"       📊 Pillars: Broker {stock.pillar1_broker:.1f}/{max_broker:.0f} | Unlock {stock.pillar2_unlock:.1f}/{max_unlock:.0f} | Fund {stock.pillar3_fundamental:.1f}/{max_fund:.0f} | Tech {stock.pillar4_technical:.1f}/{max_tech:.0f}")
            
            # Show manipulation alerts if detected
            if hasattr(stock, 'manipulation_risk_score') and stock.manipulation_risk_score and stock.manipulation_risk_score > 30:
                manip_emoji = "🚨" if stock.manipulation_risk_score > 50 else "⚠️"
                print(f"       {manip_emoji} MANIPULATION RISK: {stock.manipulation_risk_score:.0f}% | Phase: {stock.operator_phase or 'N/A'}")
                if hasattr(stock, 'manipulation_veto_reasons') and stock.manipulation_veto_reasons:
                    for reason in stock.manipulation_veto_reasons[:2]:
                        print(f"          • {reason}")
            
            # Show News & AI details if available
            if hasattr(stock, 'ai_verdict') and stock.ai_verdict:
                print(f"       🤖 AI Verdict: {stock.ai_verdict}")
        
        # ========== MANIPULATION ALERTS SUMMARY ==========
        # Show stocks with high manipulation risk
        manipulated_stocks = [s for s in results if hasattr(s, 'manipulation_risk_score') and s.manipulation_risk_score and s.manipulation_risk_score > 50]
        if manipulated_stocks:
            print("\n" + "=" * 70)
            print("🚨 MANIPULATION ALERTS (Operator Games Detected)")
            print("=" * 70)
            
            for stock in manipulated_stocks[:5]:
                phase = getattr(stock, 'operator_phase', 'UNKNOWN')
                phase_emoji = {"ACCUMULATION": "✅", "PUMP": "⚠️", "DISTRIBUTION": "🚨", "CLEAN": "✅"}.get(phase, "❓")
                
                print(f"\n   {stock.symbol:<10} Risk: {stock.manipulation_risk_score:.0f}% | {phase_emoji} {phase}")
                
                # Show key metrics
                circular = getattr(stock, 'circular_trading_pct', 0)
                hhi = getattr(stock, 'broker_concentration_hhi', 0)
                top3 = getattr(stock, 'top3_broker_control_pct', 0)
                
                if circular > 20:
                    print(f"       🔴 Circular Trading: {circular:.0f}% (FAKE VOLUME)")
                if hhi > 2500:
                    print(f"       🔴 Broker Concentration: HHI {hhi:.0f} (MONOPOLISTIC)")
                if top3 > 70:
                    print(f"       🔴 Top 3 Brokers Control: {top3:.0f}%")
                
                # Show veto reasons
                veto_reasons = getattr(stock, 'manipulation_veto_reasons', [])
                if veto_reasons:
                    for reason in veto_reasons[:2]:
                        print(f"       ⛔ {reason}")
            
            print("\n   💡 Avoid these stocks or paper-trade only")
        
        # Add Stakeholder Report with classification summary
        self._print_stakeholder_report_with_classification(
            results, good_setups, risky_watch, vetoed_watch, not_qualified,
            total_analyzed=50 if quick_mode else 299, strategy=strategy
        )
        
        return {
            "success": True,
            "scan_date": scan_date,
            "market_regime": "BEAR" if is_bear else "BULL",
            "trades_saved": len(results),
            "symbols": [s.symbol for s in results]
        }
    
    def update_positions(self) -> Dict:
        """
        📈 Update all open positions with current prices.
        
        Checks if any positions have hit target or stop loss.
        """
        logger.info("📊 Updating open positions...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all BOUGHT positions (not RECOMMENDED - those aren't real trades yet)
        cursor.execute("""
            SELECT id, symbol, entry_price_slippage, target_price, 
                   stop_loss_slippage, scan_date, hold_days, 
                   expected_hold_days, max_hold_days
            FROM paper_trades 
            WHERE status = 'BOUGHT'
        """)
        open_trades = cursor.fetchall()
        
        if not open_trades:
            logger.info("No BOUGHT positions to update. Use --action=buy to confirm purchases.")
            conn.close()
            return {"updated": 0, "closed": 0}
        
        updated = 0
        closed = 0
        overdue_alerts = []  # Track positions exceeding max hold
        today = datetime.now().strftime("%Y-%m-%d")
        
        for trade in open_trades:
            trade_id, symbol, entry_price, target, stop_loss, scan_date, hold_days, expected_hold, max_hold = trade
            # Use defaults if columns are NULL (for old records)
            expected_hold = expected_hold or 7
            max_hold = max_hold or 15
            
            try:
                # Fetch current price
                market_data = self.fetcher.fetch_live_market()
                if hasattr(market_data, 'to_dict'):
                    stocks = market_data.to_dict(orient='records')
                else:
                    stocks = market_data if isinstance(market_data, list) else []
                
                current_price = None
                for s in stocks:
                    if s.get('symbol') == symbol:
                        current_price = float(s.get('lastTradedPrice', 0) or s.get('close', 0))
                        break
                
                if not current_price:
                    continue
                
                # Calculate days held
                scan_dt = datetime.strptime(scan_date, "%Y-%m-%d")
                days_held = (datetime.now() - scan_dt).days
                
                # Check exit conditions
                exit_price = None
                status = 'OPEN'
                
                if current_price >= target:
                    status = 'TARGET_HIT'
                    exit_price = current_price
                    logger.info(f"🎯 {symbol}: TARGET HIT at Rs.{current_price:.2f}!")
                elif current_price <= stop_loss:
                    status = 'STOPPED_OUT'
                    exit_price = current_price
                    logger.warning(f"🛑 {symbol}: STOPPED OUT at Rs.{current_price:.2f}!")
                elif days_held >= max_hold:
                    # Time-based exit - use dynamic max_hold_days
                    status = 'EXPIRED'
                    exit_price = current_price
                    logger.info(f"⏰ {symbol}: TIME EXIT after {days_held} days (max: {max_hold}) at Rs.{current_price:.2f}")
                elif days_held >= expected_hold:
                    # Warning: Position exceeding expected hold but still within max
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    overdue_alerts.append({
                        "symbol": symbol,
                        "days_held": days_held,
                        "expected": expected_hold,
                        "max": max_hold,
                        "pnl_pct": pnl_pct,
                        "current_price": current_price
                    })
                    logger.warning(f"⚠️ {symbol}: Day {days_held}/{max_hold} - Consider review (PnL: {pnl_pct:+.1f}%)")
                
                # Update database
                if status != 'OPEN':
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                    cursor.execute("""
                        UPDATE paper_trades 
                        SET status = ?, exit_price = ?, exit_date = ?, 
                            profit_loss_pct = ?, hold_days = ?
                        WHERE id = ?
                    """, (status, exit_price, today, pnl_pct, days_held, trade_id))
                    closed += 1
                else:
                    cursor.execute("""
                        UPDATE paper_trades SET hold_days = ? WHERE id = ?
                    """, (days_held, trade_id))
                
                updated += 1
                
            except Exception as e:
                logger.warning(f"Error updating {symbol}: {e}")
        
        # Print overdue position alerts
        if overdue_alerts:
            print("\n" + "=" * 70)
            print("⏰ HOLDING PERIOD ALERTS - Review These Positions!")
            print("=" * 70)
            for alert in overdue_alerts:
                print(f"   {alert['symbol']:<10} Day {alert['days_held']}/{alert['max']} | PnL: {alert['pnl_pct']:+.1f}% | Rs.{alert['current_price']:.2f}")
                if alert['pnl_pct'] > 0:
                    print(f"               💡 In profit - consider booking partial gains")
                else:
                    print(f"               ⚠️ In loss - decide: hold to max day or cut now")
            print("=" * 70)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Updated {updated} positions, closed {closed}")
        return {"updated": updated, "closed": closed}
    
    def confirm_buy(self, symbol: str, actual_price: float = None, buy_date: str = None) -> Dict:
        """
        📝 Confirm that you actually bought a recommended stock.
        
        This changes the status from 'RECOMMENDED' to 'BOUGHT' and optionally
        updates the entry price to your actual purchase price.
        
        Args:
            symbol: Stock symbol (e.g., "NICA")
            actual_price: Your actual purchase price (if different from recommendation)
            buy_date: The date you bought (defaults to today)
        
        Usage:
            python tools/paper_trader.py --action=buy --symbol=NICA --price=368.50
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find the most recent RECOMMENDED entry for this symbol
        cursor.execute("""
            SELECT id, entry_price_slippage, target_price, stop_loss_slippage, scan_date
            FROM paper_trades 
            WHERE symbol = ? AND status = 'RECOMMENDED'
            ORDER BY scan_date DESC
            LIMIT 1
        """, (symbol.upper(),))
        
        trade = cursor.fetchone()
        
        if not trade:
            conn.close()
            logger.warning(f"❌ No RECOMMENDED position found for {symbol}")
            return {"success": False, "error": f"No pending recommendation for {symbol}"}
        
        trade_id, suggested_price, target, stop_loss, scan_date = trade
        
        # Use actual price if provided, otherwise use suggested price
        final_entry = actual_price if actual_price else suggested_price
        
        # Recalculate target and stop based on actual entry price if different
        if actual_price and actual_price != suggested_price:
            # Preserve the same percentage gains/losses
            target = final_entry * 1.10  # +10%
            stop_loss = final_entry * 0.935  # -6.5% (with slippage)
        
        # Update to BOUGHT status
        # NOTE: We keep original scan_date for accurate days_held calculation
        # buy_date is just for logging purposes
        today = buy_date or datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            UPDATE paper_trades 
            SET status = 'BOUGHT', 
                entry_price_slippage = ?,
                target_price = ?,
                stop_loss_slippage = ?,
                notes = ?
            WHERE id = ?
        """, (final_entry, target, stop_loss, f"Bought on {today}", trade_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Confirmed BUY: {symbol} at Rs.{final_entry:.2f}")
        print(f"\n✅ PURCHASE CONFIRMED: {symbol}")
        print(f"   💰 Entry Price: Rs.{final_entry:.2f}")
        print(f"   🎯 Target: Rs.{target:.2f} (+10%)")
        print(f"   🛑 Stop Loss: Rs.{stop_loss:.2f} (-6.5%)")
        print(f"   📅 Buy Date: {today}")
        print(f"   📊 Days tracked from: {scan_date}")
        
        return {
            "success": True,
            "symbol": symbol,
            "entry_price": final_entry,
            "target": target,
            "stop_loss": stop_loss,
            "buy_date": today,
            "scan_date": scan_date
        }
    
    def skip_stock(self, symbol: str, reason: str = None) -> Dict:
        """
        ⏭️ Mark a recommended stock as SKIPPED (you chose not to buy it).
        
        This is useful for tracking which recommendations you didn't follow.
        
        Args:
            symbol: Stock symbol to skip
            reason: Optional reason for skipping
        
        Usage:
            python tools/paper_trader.py --action=skip --symbol=NICA
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find the most recent RECOMMENDED entry for this symbol
        cursor.execute("""
            UPDATE paper_trades 
            SET status = 'SKIPPED', notes = ?
            WHERE symbol = ? AND status = 'RECOMMENDED'
        """, (reason or "User chose not to buy", symbol.upper()))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if affected > 0:
            logger.info(f"⏭️ Skipped: {symbol}")
            print(f"⏭️ Marked {symbol} as SKIPPED")
            return {"success": True, "symbol": symbol}
        else:
            logger.warning(f"❌ No RECOMMENDED position found for {symbol}")
            return {"success": False, "error": f"No pending recommendation for {symbol}"}
    
    def list_recommendations(self) -> Dict:
        """
        📋 List all pending recommendations that haven't been bought yet.
        
        Usage:
            python tools/paper_trader.py --action=pending
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT symbol, name, scan_date, score, entry_price_slippage, 
                   target_price, stop_loss_slippage
            FROM paper_trades 
            WHERE status = 'RECOMMENDED'
            ORDER BY scan_date DESC, score DESC
        """)
        
        pending = cursor.fetchall()
        conn.close()
        
        if not pending:
            print("\n📋 No pending recommendations. Run --action=scan first.")
            return {"pending": []}
        
        print("\n" + "=" * 70)
        print("📋 PENDING RECOMMENDATIONS (Not yet bought)")
        print("=" * 70)
        print("   To buy: python tools/paper_trader.py --action=buy --symbol=XXX --price=YYY")
        print("   To skip: python tools/paper_trader.py --action=skip --symbol=XXX")
        print("-" * 70)
        
        result = []
        for p in pending:
            symbol, name, scan_date, score, entry, target, stop = p
            print(f"   {symbol:<10} | Score: {score:.0f} | Entry: Rs.{entry:.2f} | Scan: {scan_date}")
            result.append({
                "symbol": symbol,
                "name": name,
                "scan_date": scan_date,
                "score": score,
                "entry": entry,
                "target": target,
                "stop_loss": stop
            })
        
        print("=" * 70)
        return {"pending": result}
    
    def analyze_single_stock(
        self,
        symbol: str,
        with_news: bool = False,
        with_ai: bool = False,
        headless: bool = True,
        historical_date: "date" = None,
    ) -> Dict:
        """
        🔍 DEEP ANALYSIS: Analyze a single stock comprehensively.
        
        This is for when a friend recommends a stock and you want to 
        evaluate it using both VALUE and MOMENTUM strategies.
        
        Works even when market is closed by using historical data.
        
        Args:
            symbol: Stock symbol (e.g., "NHPC")
            with_news: Enable news scraping
            with_ai: Enable AI verdict
            headless: Run browser in headless mode
            historical_date: Optional date object for historical analysis (YYYY-MM-DD)
        
        Returns:
            Comprehensive analysis dict
        """
        from datetime import date as date_type, datetime, timedelta
        
        symbol = symbol.upper()
        logger.info("=" * 70)
        logger.info(f"🔍 DEEP STOCK ANALYSIS: {symbol}")
        if historical_date:
            logger.info(f"📅 HISTORICAL MODE: Analyzing as of {historical_date}")
        logger.info("=" * 70)
        
        print("\n" + "=" * 70)
        print(f"🔍 COMPREHENSIVE ANALYSIS: {symbol}")
        if historical_date:
            print(f"   📅 HISTORICAL ANALYSIS: As of {historical_date}")
            print(f"   ⏰ Note: All scores/technicals are recalculated for that date")
        else:
            print("   Analyzing with BOTH Value & Momentum strategies...")
        print("=" * 70)
        
        # Run analysis with BOTH strategies
        results = {}
        data_source_info = None  # Track if using historical data
        
        for strategy in ["value", "momentum"]:
            logger.info(f"   📊 Running {strategy.upper()} strategy analysis...")
            
            # Pass analysis_date for historical mode - ensures all indicators use historical data
            screener = MasterStockScreener(strategy=strategy, analysis_date=historical_date)
            # Pass single_symbol to only load data for this stock (faster!)
            screener._preload_market_data(single_symbol=symbol)
            
            # Get the specific stock data
            try:
                target_stock = None
                
                # HISTORICAL MODE: Use data from specific date
                if historical_date:
                    logger.info(f"   📅 Historical mode - fetching data as of {historical_date}")
                    
                    # Fetch price history up to the historical date
                    # We need data BEFORE that date to calculate indicators
                    hist_df = self.fetcher.fetch_price_history(symbol, days=400)
                    
                    if hist_df is not None and not hist_df.empty:
                        # Filter to only data up to and including the historical date
                        hist_df['date'] = pd.to_datetime(hist_df['date']).dt.date
                        historical_data = hist_df[hist_df['date'] <= historical_date]
                        
                        if historical_data.empty:
                            print(f"\n❌ No data available for {symbol} on or before {historical_date}")
                            continue
                        
                        # Get the data for the specific date (or closest prior)
                        latest = historical_data.iloc[-1]
                        actual_date = latest.get('date', 'unknown')
                        data_source_info = str(actual_date)
                        
                        target_stock = {
                            'symbol': symbol,
                            'securityName': symbol,
                            'lastTradedPrice': float(latest.get('close') or 0),
                            'close': float(latest.get('close') or 0),
                            'open': float(latest.get('open') or 0),
                            'high': float(latest.get('high') or 0),
                            'low': float(latest.get('low') or 0),
                            'volume': float(latest.get('volume') or 0),
                            'totalTradedValue': float(latest.get('turnover') or 0),
                            'totalTradedQuantity': float(latest.get('volume') or 0),
                            '_data_source': 'historical',
                            '_data_date': str(actual_date),
                            '_historical_mode': True,
                            '_analysis_date': str(historical_date),
                        }
                        
                        # Get company details
                        try:
                            details = self.fetcher.fetch_company_details(symbol)
                            if details:
                                sector_name = ""
                                security = details.get('security', {})
                                company_id = security.get('companyId', {}) if security else {}
                                sector_master = company_id.get('sectorMaster', {}) if company_id else {}
                                if sector_master:
                                    sector_name = sector_master.get('sectorDescription', '')
                                
                                target_stock['sectorName'] = sector_name
                                
                                company_name = ""
                                if company_id:
                                    company_name = company_id.get('companyName', symbol)
                                elif security:
                                    company_name = security.get('securityName', symbol)
                                target_stock['securityName'] = company_name
                                target_stock['name'] = company_name
                        except Exception as e:
                            logger.debug(f"Could not fetch company details: {e}")
                        
                        if strategy == "value":
                            print(f"\n   ℹ️  Using historical data from: {actual_date}")
                            if actual_date != historical_date:
                                print(f"   ⚠️  Closest trading day to {historical_date}")
                            print(f"   📊 Recalculating indicators and scores...")
                
                # LIVE MODE: Use current market data or recent historical
                else:
                    # Try 1: Live market data (works during trading hours)
                    market_data = self.fetcher.fetch_live_market()
                    if hasattr(market_data, 'to_dict'):
                        stocks = market_data.to_dict(orient='records')
                    else:
                        stocks = market_data if isinstance(market_data, list) else []
                    
                    # Find our stock in live data
                    for s in stocks:
                        if s.get('symbol', '').upper() == symbol:
                            target_stock = s
                            break
                    
                    # Try 2: If market closed, construct stock dict from historical
                    if not target_stock:
                        logger.info(f"   📅 Market closed - building stock data from historical prices for {symbol}")
                        
                        hist_df = self.fetcher.fetch_price_history(symbol, days=10)
                        
                        if hist_df is not None and not hist_df.empty:
                            latest = hist_df.iloc[-1]
                            last_date = latest.get('date', 'unknown')
                            data_source_info = str(last_date)
                            
                            target_stock = {
                                'symbol': symbol,
                                'securityName': symbol,
                                'lastTradedPrice': float(latest.get('close') or 0),
                                'close': float(latest.get('close') or 0),
                                'open': float(latest.get('open') or 0),
                                'high': float(latest.get('high') or 0),
                                'low': float(latest.get('low') or 0),
                                'volume': float(latest.get('volume') or 0),
                                'totalTradedValue': float(latest.get('turnover') or 0),
                                'totalTradedQuantity': float(latest.get('volume') or 0),
                                '_data_source': 'historical',
                                '_data_date': str(last_date),
                            }
                            
                            # Get company details
                            try:
                                details = self.fetcher.fetch_company_details(symbol)
                                if details:
                                    sector_name = ""
                                    security = details.get('security', {})
                                    company_id = security.get('companyId', {}) if security else {}
                                    sector_master = company_id.get('sectorMaster', {}) if company_id else {}
                                    if sector_master:
                                        sector_name = sector_master.get('sectorDescription', '')
                                    
                                    target_stock['sectorName'] = sector_name
                                    
                                    company_name = ""
                                    if company_id:
                                        company_name = company_id.get('companyName', symbol)
                                    elif security:
                                        company_name = security.get('securityName', symbol)
                                    target_stock['securityName'] = company_name
                                    target_stock['name'] = company_name
                            except Exception as e:
                                logger.debug(f"Could not fetch company details: {e}")
                            
                            if strategy == "value":
                                print(f"\n   ℹ️  Market is closed. Using data from: {last_date}")
                                print(f"   📊 Running FULL 4-PILLAR ANALYSIS (400-day history, all indicators)...")
                
                if not target_stock:
                    print(f"\n❌ ERROR: Stock '{symbol}' not found.")
                    print("   The symbol may be invalid or the stock is suspended.")
                    return {"success": False, "error": f"Stock {symbol} not found"}
                
                # Run the FULL scoring engine (fetches 400-day history, calculates all indicators)
                scored = screener._score_stock(target_stock)
                
                if scored:
                    results[strategy] = scored
                    logger.info(f"   ✅ {strategy.upper()}: Score = {scored.total_score:.1f}/100")
                else:
                    logger.warning(f"   ⚠️ {strategy.upper()}: Could not score stock")
                    
            except Exception as e:
                logger.error(f"   ❌ {strategy.upper()} analysis failed: {e}")
                import traceback
                traceback.print_exc()
        
        if not results:
            print(f"\n❌ Could not analyze {symbol}. The stock may be suspended or have no data.")
            return {"success": False, "error": "Analysis failed"}
        
        # Get current LTP for PE/PBV calculation
        best_result = results.get("value") or results.get("momentum")
        current_ltp = best_result.ltp if best_result else 0
        
        # Get fundamentals from ShareHub
        fundamentals = None
        try:
            fundamentals = screener.sharehub.get_fundamentals(symbol)
            # Calculate PE and PBV with current LTP
            # Note: get_fundamentals() now calculates accurate annualized EPS from raw financials
            if fundamentals and current_ltp > 0:
                # Use annualized EPS for PE calculation (more accurate)
                if fundamentals.eps_annualized > 0:
                    fundamentals.pe_ratio = current_ltp / fundamentals.eps_annualized
                else:
                    fundamentals.calculate_pe(current_ltp)
                fundamentals.calculate_pbv(current_ltp)
        except Exception:
            pass
        
        # Get dividend history
        dividends = []
        try:
            dividends = screener.sharehub.get_dividend_history(symbol)
        except Exception:
            pass
        
        # Get company details from NEPSE
        company_details = None
        try:
            company_details = screener.fetcher.fetch_company_details(symbol)
        except Exception:
            pass
        
        # Get price history for trend
        price_trend = "N/A"
        try:
            price_summary = screener.sharehub.get_price_change_summary(symbol)
            if price_summary:
                price_trend = {
                    "7d": getattr(price_summary, 'change_7d_pct', 0),
                    "30d": getattr(price_summary, 'change_30d_pct', 0),
                    "90d": getattr(price_summary, 'change_90d_pct', 0),
                    "1y": getattr(price_summary, 'change_52w_pct', 0),
                }
        except Exception:
            pass
        
        # Get top broker holdings with full metadata (for transparency)
        top_brokers_data = []
        broker_data_duration = "1M"  # Use 1M for proper accumulation analysis
        broker_date_range = ""
        broker_total_volume = 0
        broker_total_transactions = 0
        
        try:
            # Use 1M data for comprehensive broker analysis
            broker_response = screener.sharehub.get_broker_analysis_full(symbol, duration="1M")
            if broker_response and broker_response.brokers:
                # Sort by net buy (positive = accumulating)
                top_brokers_data = sorted(
                    broker_response.brokers, 
                    key=lambda b: b.net_quantity, 
                    reverse=True
                )[:5]  # Top 5 brokers
                broker_data_duration = "1M"
                broker_date_range = broker_response.date_range
                broker_total_volume = broker_response.total_quantity
                broker_total_transactions = broker_response.total_transactions
            else:
                # Fallback to 1W
                broker_response = screener.sharehub.get_broker_analysis_full(symbol, duration="1W")
                if broker_response and broker_response.brokers:
                    top_brokers_data = sorted(
                        broker_response.brokers, 
                        key=lambda b: b.net_quantity, 
                        reverse=True
                    )[:5]
                    broker_data_duration = "1W"
                    broker_date_range = broker_response.date_range
                    broker_total_volume = broker_response.total_quantity
                    broker_total_transactions = broker_response.total_transactions
        except Exception as e:
            logger.debug(f"Could not fetch broker analysis for {symbol}: {e}")
        
        # ========== PRINT COMPREHENSIVE REPORT ==========
        value_result = results.get("value")
        momentum_result = results.get("momentum")
        
        # Use the better scored result for display
        best_result = value_result if (value_result and (not momentum_result or value_result.total_score >= momentum_result.total_score)) else momentum_result
        
        print("\n" + "═" * 70)
        print(f"📊 STOCK REPORT: {symbol} - {best_result.name if best_result else 'Unknown'}")
        if data_source_info:
            print(f"   ⚠️ NOTE: Using historical data from {data_source_info} (market closed)")
        print("═" * 70)
        
        # ========== TRAFFIC LIGHT SIGNAL (Quick Decision) ==========
        # Calculate signal first (need scores and risks)
        value_score_preview = value_result.total_score if value_result else 0
        momentum_score_preview = momentum_result.total_score if momentum_result else 0
        best_score_preview = max(value_score_preview, momentum_score_preview)
        dump_risk_preview = best_result.distribution_risk if best_result else "UNKNOWN"
        
        # Determine signal
        signal = "UNKNOWN"
        signal_emoji = "⚪"
        signal_reason = []
        
        if dump_risk_preview in ["HIGH", "CRITICAL"]:
            signal = "REJECT"
            signal_emoji = "🔴"
            signal_reason.append(f"{dump_risk_preview.lower()} distribution risk")
        
        if best_score_preview < 50:
            signal = "REJECT"
            signal_emoji = "🔴"
            if "distribution risk" not in str(signal_reason):
                signal_reason.append("score < 50")
        
        if signal == "REJECT" and not signal_reason:
            signal_reason.append("weak setup")
        
        # If not rejected, check for green signal
        if signal != "REJECT":
            if momentum_score_preview >= 70 and dump_risk_preview == "LOW":
                if value_score_preview >= 70:
                    signal = "BUY"
                    signal_emoji = "🟢"
                    signal_reason = [f"score {best_score_preview:.0f}/100", "low dump risk"]
                else:
                    signal = "SHORT-TERM RISKY, LONG-TERM NEUTRAL"
                    signal_emoji = "🟡"
                    signal_reason = [
                        f"momentum {momentum_score_preview:.0f}/100",
                        f"value {value_score_preview:.0f}/100",
                    ]
            elif best_score_preview >= 60:
                signal = "CAUTION"
                signal_emoji = "🟡"
                signal_reason = [f"score {best_score_preview:.0f}/100", "moderate setup"]
            else:
                signal = "CAUTION"
                signal_emoji = "🟡"
                signal_reason = [f"score {best_score_preview:.0f}/100"]
        
        # Display traffic light
        print()
        print("🚦 TRADING SIGNAL: " + signal_emoji + " " + signal)
        if signal_reason:
            reason_text = " + ".join(signal_reason)
            print(f"   Reason: {reason_text.capitalize()}")
        print()
        
        # ========== ENHANCED HEADER WITH MARKET CONTEXT ==========
        # Extract company details
        company_name = best_result.company_name if hasattr(best_result, 'company_name') else symbol
        sector = best_result.sector if hasattr(best_result, 'sector') else 'N/A'
        
        # Get company financial data from details
        market_cap = 0
        paid_up_capital = 0
        outstanding_shares = 0
        promoter_pct = 0
        public_pct = 0
        free_float_pct = 0
        week_52_high = 0
        week_52_low = 0
        
        if company_details:
            market_cap = company_details.get('marketCapitalization', 0) / 10000000  # Convert to Crores
            paid_up_capital = company_details.get('paidUpCapital', 0) / 10000000
            outstanding_shares = company_details.get('stockListedShares', 0) / 10000000  # In Crores
            promoter_pct = company_details.get('promoterPercentage', 0)
            public_pct = company_details.get('publicPercentage', 0)
            
            # Free float is typically public % minus locked shares (estimate ~70% of public is tradeable)
            free_float_pct = public_pct * 0.7 if public_pct > 0 else public_pct
            
            # Get 52W high/low from security details
            daily_data = company_details.get('securityDailyTradeDto', {})
            week_52_high = daily_data.get('fiftyTwoWeekHigh', 0)
            week_52_low = daily_data.get('fiftyTwoWeekLow', 0)
        
        # Calculate daily turnover (in Crores)
        daily_turnover = 0
        if company_details:
            daily_data = company_details.get('securityDailyTradeDto', {})
            volume = daily_data.get('totalTradeQuantity', 0)
            ltp = daily_data.get('lastTradedPrice', best_result.ltp)
            daily_turnover = (volume * ltp) / 10000000  # Rs. in Crores
        
        # Market cap classification
        if market_cap >= 5000:
            cap_class = "Large-cap"
            cap_emoji = "🟢"
        elif market_cap >= 1000:
            cap_class = "Mid-cap"
            cap_emoji = "🟡"
        else:
            cap_class = "Small-cap"
            cap_emoji = "🔴"
        
        # Liquidity score (0-10)
        liquidity_score = 0
        liquidity_label = "Very Low"
        if daily_turnover > 50:
            liquidity_score = 10
            liquidity_label = "Excellent"
        elif daily_turnover > 20:
            liquidity_score = 8
            liquidity_label = "Very Good"
        elif daily_turnover > 10:
            liquidity_score = 7
            liquidity_label = "Good"
        elif daily_turnover > 5:
            liquidity_score = 6
            liquidity_label = "Moderate"
        elif daily_turnover > 2:
            liquidity_score = 4
            liquidity_label = "Low"
        elif daily_turnover > 0.5:
            liquidity_score = 2
            liquidity_label = "Very Low"
        
        # Print enhanced header
        print(f"\n💰 CURRENT PRICE: Rs. {best_result.ltp:.2f}")
        print(f"   Sector: {sector}")
        if market_cap > 0:
            print(f"   Market Cap: Rs. {market_cap:,.0f} Cr ({cap_emoji} {cap_class})")
        if free_float_pct > 0:
            print(f"   Free Float: {free_float_pct:.1f}% | Daily Avg Turnover: Rs. {daily_turnover:.1f} Cr")
        
        # 52-week high/low context
        if week_52_high > 0 and week_52_low > 0:
            pct_from_high = ((best_result.ltp - week_52_high) / week_52_high * 100)
            pct_from_low = ((best_result.ltp - week_52_low) / week_52_low * 100)
            print(f"\n📈 PRICE LEVELS:")
            print(f"   52W High: Rs. {week_52_high:.2f} ({pct_from_high:+.1f}% from peak)")
            print(f"   52W Low:  Rs. {week_52_low:.2f} ({pct_from_low:+.1f}% from bottom)")
        
        # Price Trend
        if isinstance(price_trend, dict):
            print(f"\n📊 PRICE TREND:")
            print(f"   7 Days:  {price_trend.get('7d', 0):+.2f}%")
            print(f"   30 Days: {price_trend.get('30d', 0):+.2f}%")
            print(f"   90 Days: {price_trend.get('90d', 0):+.2f}%")
            print(f"   1 Year:  {price_trend.get('1y', 0):+.2f}%")
        
        # ========== COMBINED SUMMARY LINE ==========
        # Determine overall verdict label based on best score
        best_score = best_result.total_score if best_result else 0
        if best_score >= 70:
            overall_label = "GOOD"
            overall_emoji = "🟢"
        elif best_score >= 50:
            overall_label = "FAIR"
            overall_emoji = "🟡"
        else:
            overall_label = "WEAK"
            overall_emoji = "🔴"
        
        # Get dump risk label
        dump_risk = best_result.distribution_risk if best_result else "N/A"
        dump_risk_labels = {
            "LOW": "LOW (brokers not dumping yet)",
            "MEDIUM": "MODERATE (ok only for short-term swing)",
            "HIGH": "HIGH (brokers may dump; proceed with caution)",
            "CRITICAL": "CRITICAL (active distribution; avoid)"
        }
        dump_label = dump_risk_labels.get(dump_risk, dump_risk)
        
        print("\n" + "═" * 70)
        print(f"📋 SUMMARY: {overall_emoji} Overall: {overall_label} ({best_score:.0f}/100) | Dump Risk: {dump_label}")
        print("═" * 70)
        
        # ========== COMPANY OVERVIEW SECTION ==========
        if company_details:
            print("\n" + "-" * 70)
            print("🏢 COMPANY OVERVIEW")
            print("-" * 70)
            if paid_up_capital > 0:
                print(f"   Paid-up Capital:    Rs. {paid_up_capital:,.0f} Cr")
            if outstanding_shares > 0:
                print(f"   Outstanding Shares: {outstanding_shares:.2f} Crore shares")
            if promoter_pct > 0:
                print(f"   Promoter Holding:   {promoter_pct:.0f}% | Public: {public_pct:.0f}%")
                print(f"   Free Float:         {free_float_pct:.1f}% (tradeable by retail)")
            
            # Unlock Risk Section
            unlock_info = best_result if hasattr(best_result, 'days_until_unlock') else None
            if unlock_info and unlock_info.days_until_unlock > 0 and unlock_info.days_until_unlock <= 90:
                print(f"\n   🔒 UNLOCK RISK:")
                if unlock_info.days_until_unlock <= 30:
                    risk_emoji = "🚨"
                    risk_label = "HIGH RISK"
                elif unlock_info.days_until_unlock <= 60:
                    risk_emoji = "⚠️"
                    risk_label = "MEDIUM RISK"
                else:
                    risk_emoji = "🟡"
                    risk_label = "LOW RISK"
                
                print(f"      {risk_emoji} {risk_label} - Shares unlock in {unlock_info.days_until_unlock} days")
                
                if unlock_info.unlock_quantity > 0:
                    unlock_value = unlock_info.unlock_quantity * best_result.ltp / 10000000  # in Crores
                    print(f"      Expected selling pressure: ~Rs. {unlock_value:.0f} Cr worth")
                
                print(f"      💡 Historical pattern: Unlocks typically cause 5-15% price drops")
                print(f"         Monitor carefully and consider reducing position before unlock date.")
            elif unlock_info and unlock_info.days_until_unlock > 0:
                print(f"\n   ✅ UNLOCK RISK: LOW - Next unlock in {unlock_info.days_until_unlock} days")
            else:
                print(f"\n   ✅ UNLOCK RISK: NONE - No unlocks scheduled in next 90 days")
            
            # Liquidity Analysis
            print(f"\n   💧 LIQUIDITY ANALYSIS:")
            print(f"      Daily Avg Turnover: Rs. {daily_turnover:.1f} Cr")
            print(f"      Liquidity Score:    {liquidity_score}/10 ({liquidity_label})")
            
            if liquidity_score <= 4:
                print(f"      ⚠️ Warning: Low liquidity. Large orders may move price significantly.")
                print(f"         Exit strategy is crucial - may take multiple days to sell.")
            elif liquidity_score >= 8:
                print(f"      ✅ Good liquidity. Easy to enter and exit positions.")
        
        # Strategy Comparison
        print("\n" + "-" * 70)
        print("📊 STRATEGY COMPARISON (Which approach fits your goal?)")
        print("-" * 70)
        
        # VALUE Strategy
        print("\n🏦 VALUE STRATEGY (Long-term / Fundamental Focus)")
        if value_result:
            score_emoji = "🟢" if value_result.total_score >= 70 else "🟡" if value_result.total_score >= 50 else "🔴"
            print(f"   {score_emoji} Score: {value_result.total_score:.0f}/100")
            print(f"   📊 Pillar Scores:")
            print(f"      • Broker/Institutional: {value_result.pillar1_broker:.1f}/30")
            print(f"      • Unlock Risk:         {value_result.pillar2_unlock:.1f}/20")
            print(f"      • Fundamentals:        {value_result.pillar3_fundamental:.1f}/20")
            print(f"      • Technicals:          {value_result.pillar4_technical:.1f}/30")
            print(f"   💡 Verdict: {value_result.verdict_reason}")
        else:
            print("   ❌ Analysis not available")
        
        # MOMENTUM Strategy
        print("\n🚀 MOMENTUM STRATEGY (Short-term / Swing Trading)")
        if momentum_result:
            score_emoji = "🟢" if momentum_result.total_score >= 70 else "🟡" if momentum_result.total_score >= 50 else "🔴"
            print(f"   {score_emoji} Score: {momentum_result.total_score:.0f}/100")
            print(f"   📊 Pillar Scores:")
            print(f"      • Broker/Institutional: {momentum_result.pillar1_broker:.1f}/30")
            print(f"      • Unlock Risk:         {momentum_result.pillar2_unlock:.1f}/20")
            print(f"      • Fundamentals:        {momentum_result.pillar3_fundamental:.1f}/10")
            print(f"      • Technicals:          {momentum_result.pillar4_technical:.1f}/40")
            print(f"   💡 Verdict: {momentum_result.verdict_reason}")
        else:
            print("   ❌ Analysis not available")
        
        # Fundamentals
        print("\n" + "-" * 70)
        print("📈 FUNDAMENTAL DATA")
        print("-" * 70)
        if fundamentals:
            # PE Ratio check - 0 or negative is BAD (missing data or negative earnings)
            pe = fundamentals.pe_ratio
            if pe <= 0:
                pe_status = " ❌ MISSING/NEGATIVE"
            elif pe > 30:
                pe_status = " ⚠️ HIGH"
            elif pe < 20:
                pe_status = " ✅ OK"
            else:
                pe_status = ""
            print(f"   PE Ratio:    {pe:.2f}" + pe_status)
            # Show EPS with quarter info for clarity
            eps_display = fundamentals.eps_annualized if fundamentals.eps_annualized > 0 else fundamentals.eps
            eps_label = "EPS (Ann.)" if fundamentals.eps_annualized > 0 else "EPS"
            print(f"   {eps_label}:   Rs. {eps_display:.2f}" + (" ❌ NEGATIVE" if eps_display <= 0 else f" ({fundamentals.quarter.upper()})"))
            print(f"   Book Value:  Rs. {fundamentals.book_value:.2f}")
            print(f"   PBV:         {fundamentals.pbv:.2f}" + (" ⚠️ HIGH" if fundamentals.pbv > 3 else " ✅ OK"))
            
            # ROE with educational context
            roe = fundamentals.roe
            if roe > 15:
                roe_status = " ✅ EXCELLENT"
            elif roe > 10:
                roe_status = " ✅ GOOD"
            elif roe >= 5:
                roe_status = " 🟡 AVERAGE"
            else:
                roe_status = " ⚠️ LOW"
            print(f"   ROE:         {roe:.2f}%" + roe_status)
            
            # Educational tooltip for ROE
            print(f"\n   💡 What is ROE? Return on Equity shows how efficiently company uses shareholder money.")
            print(f"      >15% = Excellent | 10-15% = Good | 5-10% = Average | <5% = Poor")
            if roe > 0:
                print(f"      {company_name}'s {roe:.1f}% means Rs. 100 invested generates Rs. {roe:.1f} profit annually.")
        else:
            print("   Fundamental data not available")
        
        # Sector Comparison (Critical for NEPSE context)
        print("\n" + "-" * 70)
        print("📊 SECTOR COMPARISON (How does this compare to peers?)")
        print("-" * 70)
        if fundamentals and sector != 'N/A':
            # Get sector averages from screener (if available)
            sector_avg_pe = 0
            sector_avg_pbv = 0
            sector_avg_roe = 0
            
            # Calculate sector averages from preloaded data or estimate
            # For now, use hardcoded NEPSE sector benchmarks
            sector_benchmarks = {
                'Commercial Banks': {'pe': 12, 'pbv': 1.8, 'roe': 15},
                'Development Banks': {'pe': 15, 'pbv': 1.5, 'roe': 12},
                'Finance': {'pe': 18, 'pbv': 1.3, 'roe': 10},
                'Hydro Power': {'pe': 25, 'pbv': 1.5, 'roe': 8},
                'Life Insurance': {'pe': 20, 'pbv': 2.0, 'roe': 12},
                'Non-Life Insurance': {'pe': 18, 'pbv': 1.8, 'roe': 10},
                'Microfinance': {'pe': 10, 'pbv': 1.2, 'roe': 14},
                'Hotels And Tourism': {'pe': 30, 'pbv': 1.5, 'roe': 6},
                'Manufacturing And Processing': {'pe': 20, 'pbv': 1.4, 'roe': 8},
                'Trading': {'pe': 15, 'pbv': 1.3, 'roe': 10},
                'Others': {'pe': 20, 'pbv': 1.5, 'roe': 8},
            }
            
            benchmark = sector_benchmarks.get(sector, {'pe': 20, 'pbv': 1.5, 'roe': 10})
            sector_avg_pe = benchmark['pe']
            sector_avg_pbv = benchmark['pbv']
            sector_avg_roe = benchmark['roe']
            
            # Compare this stock to sector
            pe = fundamentals.pe_ratio
            pbv = fundamentals.pbv
            roe = fundamentals.roe
            
            print(f"   Sector: {sector}")
            print(f"   Sector Avg: PE {sector_avg_pe:.1f} | PBV {sector_avg_pbv:.1f} | ROE {sector_avg_roe:.1f}%")
            print()
            
            # PE Comparison
            if pe > 0:
                pe_vs_sector = ((pe - sector_avg_pe) / sector_avg_pe) * 100
                if pe_vs_sector > 30:
                    pe_status = f"⚠️ EXPENSIVE ({pe_vs_sector:+.0f}% vs sector)"
                elif pe_vs_sector > 10:
                    pe_status = f"🟡 ABOVE AVG ({pe_vs_sector:+.0f}% vs sector)"
                elif pe_vs_sector < -20:
                    pe_status = f"✅ CHEAP ({pe_vs_sector:+.0f}% vs sector)"
                else:
                    pe_status = f"✅ FAIR ({pe_vs_sector:+.0f}% vs sector)"
                print(f"   PE {pe:.1f}: {pe_status}")
            
            # PBV Comparison
            pbv_vs_sector = ((pbv - sector_avg_pbv) / sector_avg_pbv) * 100
            if pbv_vs_sector > 50:
                pbv_status = f"⚠️ EXPENSIVE ({pbv_vs_sector:+.0f}% vs sector)"
            elif pbv_vs_sector > 20:
                pbv_status = f"🟡 ABOVE AVG ({pbv_vs_sector:+.0f}% vs sector)"
            elif pbv_vs_sector < -20:
                pbv_status = f"✅ CHEAP ({pbv_vs_sector:+.0f}% vs sector)"
            else:
                pbv_status = f"✅ FAIR ({pbv_vs_sector:+.0f}% vs sector)"
            print(f"   PBV {pbv:.1f}: {pbv_status}")
            
            # ROE Comparison
            roe_vs_sector = ((roe - sector_avg_roe) / sector_avg_roe) * 100
            if roe_vs_sector > 20:
                roe_status = f"✅ STRONG ({roe_vs_sector:+.0f}% vs sector)"
            elif roe_vs_sector > 0:
                roe_status = f"✅ ABOVE AVG ({roe_vs_sector:+.0f}% vs sector)"
            elif roe_vs_sector > -20:
                roe_status = f"🟡 BELOW AVG ({roe_vs_sector:+.0f}% vs sector)"
            else:
                roe_status = f"⚠️ WEAK ({roe_vs_sector:+.0f}% vs sector)"
            print(f"   ROE {roe:.1f}%: {roe_status}")
            
            print()
            print(f"   💡 Tip: In {sector}, PE of {sector_avg_pe} is normal.")
            print(f"      {company_name} at PE {pe:.1f} is {pe_status.split('(')[0].strip()}")
        
        # Dividend History
        print("\n" + "-" * 70)
        print("💵 DIVIDEND HISTORY (Last 3 Years)")
        print("-" * 70)
        if dividends:
            total_div = 0
            for div in dividends[:3]:
                cash = getattr(div, 'cash_pct', 0) or 0
                bonus = getattr(div, 'bonus_pct', 0) or 0
                year = getattr(div, 'fiscal_year', 'N/A')
                total = cash + bonus
                total_div += total
                print(f"   FY {year}: Cash {cash:.2f}% + Bonus {bonus:.2f}% = Total {total:.2f}%")
            
            if total_div > 0:
                print(f"   ✅ Dividend payer (Total last 3 years: {total_div:.2f}%)")
            else:
                print(f"   ⚠️ No dividends in recent years")
        else:
            print("   Dividend history not available")
        
        # Distribution Risk
        print("\n" + "-" * 70)
        print("📉 BROKER DISTRIBUTION RISK (Smart Money Dump Indicator)")
        print("-" * 70)
        if best_result.distribution_risk:
            risk_emoji = {"LOW": "✅", "MEDIUM": "🟡", "HIGH": "⚠️", "CRITICAL": "🚨"}.get(best_result.distribution_risk, "❓")
            print(f"   {risk_emoji} Dump Risk Level: {best_result.distribution_risk}")
            
            # Show dual timeframe analysis
            print()
            print("   📅 DUAL TIMEFRAME ANALYSIS (Expert Rule)")
            print("   " + "-" * 50)
            
            # 1-Month baseline
            net_1m = getattr(best_result, 'net_holdings_1m', 0)
            print(f"   1-MONTH (Baseline): Avg Rs. {best_result.broker_avg_cost:.2f} | Net: {net_1m:+,} shares")
            if net_1m > 0:
                print(f"      → 🟢 ACCUMULATING over 1 month")
            elif net_1m < 0:
                print(f"      → 🔴 DISTRIBUTING over 1 month")
            
            # 1-Week fine-tune
            avg_1w = getattr(best_result, 'broker_avg_cost_1w', 0)
            net_1w = getattr(best_result, 'net_holdings_1w', 0)
            if avg_1w and avg_1w > 0:
                print(f"   1-WEEK (Fine-tune): Avg Rs. {avg_1w:.2f} | Net: {net_1w:+,} shares")
                if net_1w > 0:
                    print(f"      → 🟢 ACCUMULATING this week")
                elif net_1w < 0:
                    print(f"      → 🔴 DISTRIBUTING this week")
            
            dual_pass = (net_1m > 0 and net_1w > 0)
            print()
            if dual_pass:
                print("   📊 DUAL TIMEFRAME: ✅ PASS (accumulation confirmed both timeframes)")
            else:
                print("   📊 DUAL TIMEFRAME: ⚠️ MIXED/FAIL (accumulation not confirmed both timeframes)")
            if best_result.distribution_risk in ["HIGH", "CRITICAL"]:
                print(f"      ⚠️ But {best_result.distribution_risk} intraday distribution risk overrides.")
            
            # Divergence warning
            if getattr(best_result, 'distribution_divergence', False):
                print()
                print("   ⚠️ DIVERGENCE DETECTED!")
                print("      1M shows accumulation but 1W shows distribution.")
                print("      → Brokers may be starting to EXIT their positions.")
                print("      → Avoid new entries. Consider reducing existing positions.")
            
            print()
            print(f"   Current LTP:        Rs. {best_result.ltp:.2f}")
            print(f"   Broker Profit:      +{best_result.broker_profit_pct:.1f}%")
            
            # Enhanced explanation based on risk level
            if best_result.distribution_risk in ["HIGH", "CRITICAL"]:
                print()
                print(f"   {risk_emoji} {best_result.distribution_risk} RISK: Distribution pattern detected!")
                
                # Show intraday dump details if available
                if getattr(best_result, 'intraday_dump_detected', False) and getattr(best_result, 'today_open_price', 0) > 0:
                    open_price = best_result.today_open_price
                    open_vs_broker = best_result.open_vs_broker_pct
                    volume_spike = getattr(best_result, 'intraday_volume_spike', 0)
                    close_vs_vwap = getattr(best_result, 'close_vs_vwap_pct', 0)
                    drift_word = "UP" if best_result.ltp >= open_price else "DOWN"
                    
                    print()
                    print("   🚨 Today's Intraday Action:")
                    print(f"      • Open price: Rs. {open_price:.2f} (+{open_vs_broker:.1f}% above broker avg)")
                    if volume_spike > 0:
                        print(f"      • Volume spike: {volume_spike:.2f}x of average daily volume")
                    if getattr(best_result, 'today_vwap', 0) > 0:
                        print(f"      • Close vs VWAP: {close_vs_vwap:.1f}% (below VWAP = selling pressure)")
                    
                    print()
                    print("   ⚠️ Analysis:")
                    print(f"      Smart money likely offloaded shares at open (Rs. {open_price:.2f}),")
                    print(f"      then price drifted {drift_word} to close at Rs. {best_result.ltp:.2f}.")
                    print()
                    print("   🔴 Recommendation: Avoid momentum entry until clear re-accumulation appears.")
                else:
                    print()
                    print("   ⚠️ Analysis:")
                    print(f"      Brokers are sitting on +{best_result.broker_profit_pct:.1f}% profit.")
                    if best_result.broker_profit_pct >= 15:
                        print("      At this profit level, distribution risk is elevated.")
                    print("      Watch for signs of selling pressure (high volume, price rejection).")
                    
            elif best_result.distribution_risk == "MEDIUM":
                print(f"   {best_result.distribution_warning}")
            else:  # LOW
                print(f"   {best_result.distribution_warning}")
            
            # Add explanatory note
            print()
            print("   📌 Note: Dump Risk shows only smart-money dump likelihood.")
            print("      It does NOT mean this is a good trade by itself.")
            print("      Always follow the Overall Score + Strategy verdict.")
        else:
            print("   Distribution risk data not available")
        
        # ========== TOP BROKER HOLDINGS (Smart Money Flow) ==========
        print("\n" + "-" * 70)
        print(f"🏦 TOP BROKER ACTIVITY")
        print("-" * 70)
        if top_brokers_data:
            # Show date range and summary
            if broker_date_range:
                print(f"   📅 Data Period: {broker_date_range}")
            if broker_total_volume > 0:
                print(f"   📊 Total Volume: {broker_total_volume:,} shares | Transactions: {broker_total_transactions:,}")
            print()
            
            # Calculate average cost for shares still held
            total_net_holdings = sum(b.net_quantity for b in top_brokers_data if b.net_quantity > 0)
            total_weighted_cost = 0.0
            for b in top_brokers_data:
                if b.net_quantity > 0 and b.buy_quantity > 0:
                    broker_avg_buy = b.buy_amount / b.buy_quantity
                    total_weighted_cost += broker_avg_buy * b.net_quantity
            
            if total_net_holdings > 0:
                avg_cost_of_holdings = total_weighted_cost / total_net_holdings
                print(f"   💰 Top 5 Brokers Avg Cost (Net Holdings): Rs. {avg_cost_of_holdings:.2f}")
                print()
            
            print("   Broker Code | Broker Name                  | Net Qty   | Avg Buy   | Sell Qty")
            print("   " + "-" * 80)
            for broker in top_brokers_data:
                net_emoji = "🟢" if broker.net_quantity > 0 else "🔴" if broker.net_quantity < 0 else "⚪"
                broker_name = broker.broker_name[:28] if len(broker.broker_name) > 28 else broker.broker_name
                # Calculate their avg buy price
                avg_buy = broker.buy_amount / broker.buy_quantity if broker.buy_quantity > 0 else 0
                print(f"   {net_emoji} {broker.broker_code:>6} | {broker_name:<28} | {broker.net_quantity:>9,} | Rs.{avg_buy:>6.2f} | {broker.sell_quantity:>9,}")
            
            # Calculate totals
            total_net = sum(b.net_quantity for b in top_brokers_data)
            total_buy = sum(b.buy_quantity for b in top_brokers_data)
            total_sell = sum(b.sell_quantity for b in top_brokers_data)
            
            print("   " + "-" * 80)
            net_emoji = "🟢" if total_net > 0 else "🔴" if total_net < 0 else "⚪"
            print(f"   {net_emoji} TOP 5 TOTAL:                              | {total_net:>9,} |           | {total_sell:>9,}")
            
            if total_net > 0:
                print(f"\n   ✅ Smart money ACCUMULATING: Top 5 brokers net +{total_net:,} shares")
            elif total_net < 0:
                print(f"\n   ⚠️ Smart money DISTRIBUTING: Top 5 brokers net {total_net:,} shares")
            else:
                print(f"\n   ⚪ Neutral: Top 5 brokers balanced buying/selling")
            
            # Educational note about broker data
            print()
            print("   💡 Tip: Net Qty = Buy - Sell. Positive means broker is accumulating.")
            print("      Avg Buy shows the broker's entry price. Compare to LTP for their profit.")
        else:
            print("   Broker activity data not available (requires ShareHub authentication)")
        
        # ========== 🚨 MANIPULATION DETECTION (9 DETECTORS) ==========
        print("\n" + "-" * 70)
        print("🚨 MANIPULATION RISK ANALYSIS (Insider Operator Detection)")
        print("-" * 70)
        
        # Display manipulation detection results if available
        if hasattr(best_result, 'manipulation_risk_score') and best_result.manipulation_risk_score is not None:
            risk_score = best_result.manipulation_risk_score
            severity = best_result.manipulation_severity or "UNKNOWN"
            phase = best_result.operator_phase or "UNKNOWN"
            
            # Risk bar visualization
            risk_bar = "█" * int(risk_score / 10) + "░" * (10 - int(risk_score / 10))
            
            print(f"\n   📊 MANIPULATION RISK SCORE: [{risk_bar}] {risk_score:.0f}%")
            print(f"   Severity: {severity}")
            
            # Safe to trade indicator
            is_safe = getattr(best_result, 'is_safe_to_trade', True)
            if is_safe:
                print(f"   Trading Status: ✅ SAFE TO TRADE")
            else:
                print(f"   Trading Status: 🚫 HIGH RISK - Paper trade only")
            
            # Operator phase
            phase_emoji = {
                "ACCUMULATION": "✅",
                "PUMP": "⚠️",
                "DISTRIBUTION": "🚨",
                "CLEAN": "✅",
                "UNKNOWN": "❓"
            }.get(phase, "❓")
            print(f"\n   📈 OPERATOR PHASE: {phase_emoji} {phase}")
            if hasattr(best_result, 'operator_phase_description') and best_result.operator_phase_description:
                print(f"      {best_result.operator_phase_description}")
            
            # Broker concentration metrics
            hhi = getattr(best_result, 'broker_concentration_hhi', 0)
            top3_pct = getattr(best_result, 'top3_broker_control_pct', 0)
            circular_pct = getattr(best_result, 'circular_trading_pct', 0)
            wash_detected = getattr(best_result, 'wash_trading_detected', False)
            lockup_days = getattr(best_result, 'lockup_days_remaining', None)
            
            print(f"\n   📋 KEY METRICS:")
            print(f"      • Broker Concentration (HHI): {hhi:.0f}" + (" ⚠️ HIGH" if hhi > 2500 else " ✅ OK" if hhi > 0 else ""))
            print(f"      • Top 3 Brokers Control: {top3_pct:.0f}%" + (" ⚠️ CONCENTRATED" if top3_pct > 70 else ""))
            print(f"      • Circular Trading: {circular_pct:.0f}%" + (" 🚨 FAKE VOLUME!" if circular_pct > 20 else " ✅ OK"))
            print(f"      • Wash Trading: {'🚨 DETECTED' if wash_detected else '✅ None'}")
            if lockup_days is not None:
                print(f"      • Promoter Lockup: {lockup_days} days" + (" ⚠️ EXPIRES SOON!" if lockup_days < 30 else " ✅ Safe"))
            
            # Alerts from manipulation detector
            alerts = getattr(best_result, 'manipulation_alerts', [])
            veto_reasons = getattr(best_result, 'manipulation_veto_reasons', [])
            
            if alerts:
                print(f"\n   🚨 DETECTED PATTERNS:")
                for alert in alerts[:5]:  # Show top 5 alerts
                    print(f"      {alert}")
            
            if veto_reasons:
                print(f"\n   ⛔ VETO REASONS (Paper-trade only):")
                for reason in veto_reasons[:3]:
                    print(f"      • {reason}")
            
            # Educational note
            print()
            print("   💡 What this means:")
            if veto_reasons:
                print("      Hard manipulation veto(s) detected. Treat as paper-trade / avoid.")
            elif phase == "ACCUMULATION":
                print("      Operators are silently buying. Early entry opportunity if fundamentals support.")
            elif phase == "PUMP":
                print("      Volume spike + price surge = Pump phase. Late entry risk - don't chase.")
            elif phase == "DISTRIBUTION":
                print("      Operators exiting while retail buys. AVOID new positions.")
            else:
                print("      No clear pump/dump phase pattern. Continue normal risk checks.")
        else:
            print("\n   Manipulation analysis not available for this stock.")
            print("   💡 Run: python paper_trader.py --analyze SYMBOL for full analysis")
        
        # ========== RECENT NEWS ==========
        print("\n" + "-" * 70)
        print("📰 RECENT NEWS & ANNOUNCEMENTS")
        print("-" * 70)
        
        # Try to fetch news
        recent_news = []
        try:
            from intelligence.news_scraper import (
                PLAYWRIGHT_AVAILABLE,
                is_playwright_browser_installed,
                scrape_news_for_stock,
            )
            if PLAYWRIGHT_AVAILABLE and is_playwright_browser_installed():
                recent_news = scrape_news_for_stock(symbol, limit=3, headless=True)
            else:
                logger.debug("Skipping news scraping: Playwright browser not installed")
        except Exception as e:
            logger.debug(f"Could not fetch news for {symbol}: {e}")
        
        if recent_news:
            for i, news in enumerate(recent_news[:3], 1):
                print(f"   {i}. {news.title}")
                if news.date:
                    print(f"      📅 {news.date} | 🌐 {news.source}")
                else:
                    print(f"      🌐 {news.source}")
                if news.snippet:
                    snippet = news.snippet[:100] + "..." if len(news.snippet) > 100 else news.snippet
                    print(f"      {snippet}")
                print()
        else:
            print("   No recent news available.")
            print("   💡 Tip: Check ShareSansar or Merolagani for latest company updates.")
        
        # Technical Indicators
        print("\n" + "-" * 70)
        print("📊 TECHNICAL INDICATORS")
        print("-" * 70)
        rsi = best_result.rsi
        rsi_status = " ⚠️ OVERBOUGHT" if rsi > 70 else " ⚠️ OVERSOLD" if rsi < 30 else " ✅ NEUTRAL"
        print(f"   RSI (14):      {rsi:.1f}" + rsi_status)
        print(f"   EMA Signal:    {best_result.ema_signal}")
        print(f"   Volume Spike:  {best_result.volume_spike:.2f}x" + (" 🔥 HIGH" if best_result.volume_spike > 2 else ""))
        # ATR check - 0 means calculation failed
        if best_result.atr > 0:
            print(f"   ATR:           Rs. {best_result.atr:.2f}")
        else:
            print(f"   ATR:           ❌ Could not calculate (insufficient data)")
        
        # Educational tooltip for RSI
        print(f"\n   💡 What is RSI? Relative Strength Index (0-100):")
        print(f"      70-100 = Overbought (price may fall soon)")
        print(f"      30-70  = Neutral range")
        print(f"      0-30   = Oversold (price may bounce)")
        print(f"      {company_name}'s RSI of {rsi:.1f} is {rsi_status.strip().replace('⚠️', '').replace('✅', '').strip()}")
        
        # ========== SUPPORT/RESISTANCE ZONES ==========
        print("\n" + "-" * 70)
        print("📍 SUPPORT & RESISTANCE ZONES (30-day analysis)")
        print("-" * 70)
        
        # Calculate S/R zones from recent price history
        try:
            hist_30d = screener.fetcher.fetch_price_history(symbol, days=30)
            if hist_30d is not None and len(hist_30d) > 10:
                # pd and np already imported at top of file
                import numpy as np
                
                # Get recent highs and lows
                highs = hist_30d['high'].values
                lows = hist_30d['low'].values
                closes = hist_30d['close'].values
                
                # Find resistance (recent high zones that price bounced off)
                resistance_levels = []
                support_levels = []
                
                # Simple method: Find local maxima/minima
                for i in range(2, len(highs) - 2):
                    # Local maximum (resistance)
                    if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                        resistance_levels.append(highs[i])
                    
                    # Local minimum (support)
                    if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                        support_levels.append(lows[i])
                
                # Cluster nearby levels (within 2%)
                def cluster_levels(levels, tolerance=0.02):
                    if not levels:
                        return []
                    levels = sorted(levels)
                    clusters = []
                    current_cluster = [levels[0]]
                    
                    for level in levels[1:]:
                        if abs(level - current_cluster[-1]) / current_cluster[-1] < tolerance:
                            current_cluster.append(level)
                        else:
                            clusters.append(np.mean(current_cluster))
                            current_cluster = [level]
                    
                    clusters.append(np.mean(current_cluster))
                    return clusters
                
                resistance_zones = cluster_levels(resistance_levels)
                support_zones = cluster_levels(support_levels)
                
                # Show top 3 nearest zones
                current_price = best_result.ltp
                
                # Resistance above current price
                nearby_resistance = [r for r in resistance_zones if r > current_price]
                nearby_resistance = sorted(nearby_resistance)[:3]
                
                # Support below current price
                nearby_support = [s for s in support_zones if s < current_price]
                nearby_support = sorted(nearby_support, reverse=True)[:3]
                
                print(f"   Current Price: Rs. {current_price:.2f}")
                print()
                
                if nearby_resistance:
                    print(f"   🔴 RESISTANCE (sell zones above):")
                    for r in nearby_resistance:
                        distance = ((r - current_price) / current_price) * 100
                        print(f"      Rs. {r:.2f} (+{distance:.1f}% away)")
                else:
                    print(f"   🔴 RESISTANCE: No strong resistance detected above")
                
                print()
                
                if nearby_support:
                    print(f"   🟢 SUPPORT (buy zones below):")
                    for s in nearby_support:
                        distance = ((current_price - s) / current_price) * 100
                        print(f"      Rs. {s:.2f} (-{distance:.1f}% away)")
                else:
                    print(f"   🟢 SUPPORT: No strong support detected below")
                
                print()
                print(f"   💡 Tip: Price tends to bounce at support, stall at resistance.")
                print(f"      If price breaks resistance with volume, it may rally further.")
                
            else:
                print("   Insufficient data to calculate support/resistance zones.")
        except Exception as e:
            logger.debug(f"Could not calculate S/R zones: {e}")
            print("   Support/Resistance calculation unavailable.")
        
        # Trade Plan - CONDITIONAL on dump risk and momentum score
        print("\n" + "-" * 70)
        print("🎯 PRICE TARGET ANALYSIS")
        print("-" * 70)
        
        # Calculate intelligent price targets
        try:
            from analysis.price_target_analyzer import PriceTargetAnalyzer
            
            target_analyzer = PriceTargetAnalyzer(fetcher=screener.fetcher, sharehub=screener.sharehub)
            target_analysis = target_analyzer.analyze(symbol, lookback_days=365)
            
            if target_analysis.conservative_target:
                t = target_analysis.conservative_target
                print(f"   🟢 CONSERVATIVE: Rs. {t.level:,.2f} (+{t.upside_percent:.1f}%) | {t.probability:.0f}% prob | ~{t.days_estimate}d")
            
            if target_analysis.moderate_target and target_analysis.moderate_target.level != (target_analysis.conservative_target.level if target_analysis.conservative_target else 0):
                t = target_analysis.moderate_target
                print(f"   🟡 MODERATE:     Rs. {t.level:,.2f} (+{t.upside_percent:.1f}%) | {t.probability:.0f}% prob | ~{t.days_estimate}d")
            
            if target_analysis.aggressive_target:
                t = target_analysis.aggressive_target
                print(f"   🔴 AGGRESSIVE:   Rs. {t.level:,.2f} (+{t.upside_percent:.1f}%) | {t.probability:.0f}% prob | ~{t.days_estimate}d")
            
            if target_analysis.maximum_theoretical:
                t = target_analysis.maximum_theoretical
                print(f"   🚀 MAX THEORY:   Rs. {t.level:,.2f} (+{t.upside_percent:.1f}%)")
            
            # Risk assessment
            print()
            print(f"   📊 Risk Assessment:")
            print(f"      Nearest Support: Rs. {target_analysis.nearest_support:,.2f}")
            print(f"      Downside Risk:   -{target_analysis.downside_risk_percent:.1f}%")
            if target_analysis.risk_reward_ratio > 0:
                print(f"      Risk/Reward:     1:{target_analysis.risk_reward_ratio:.1f}")
            print(f"      Trend: {target_analysis.trend_direction} | Momentum: {target_analysis.momentum_score:.0f}/100")
            
            if target_analysis.warnings:
                print()
                for w in target_analysis.warnings[:2]:  # Show max 2 warnings
                    print(f"   {w}")
        except Exception as e:
            logger.debug(f"Price target analysis failed: {e}")
            print("   Price target analysis unavailable.")
        
        print("\n" + "-" * 70)
        print("🎯 SUGGESTED TRADE PLAN")
        print("-" * 70)
        
        # Check if momentum entry should be blocked
        dump_risk_level = best_result.distribution_risk
        momentum_score_val = momentum_result.total_score if momentum_result else 0
        should_block_entry = (dump_risk_level in ["HIGH", "CRITICAL"]) and (momentum_score_val <= 50)
        
        if should_block_entry:
            # HIGH/CRITICAL dump risk + WEAK momentum = NO ENTRY
            print(f"   ⚠️ NO MOMENTUM ENTRY RECOMMENDED TODAY")
            print(f"   ")
            print(f"   Reason: {dump_risk_level} distribution risk detected.")
            if dump_risk_level == "CRITICAL":
                print(f"   Operators are aggressively dumping shares.")
            else:
                print(f"   Operators likely distributed shares today.")
            print(f"   ")
            print(f"   🔴 ACTION: AVOID momentum entry until:")
            print(f"      • Price stabilizes and re-accumulation is confirmed")
            print(f"      • Distribution risk downgrades to MEDIUM or LOW")
            print(f"      • Wait 1-2 sessions for dust to settle")
        else:
            # Normal case: Show trade plan
            print(f"   Entry Price:   Rs. {best_result.entry_price_with_slippage:.2f} (with 1.5% slippage)")
            print(f"   Target (+10%): Rs. {best_result.target_price:.2f}")
            print(f"   Stop Loss:     Rs. {best_result.stop_loss_with_slippage:.2f} (-6.5% with slippage)")
            print(f"   Expected Hold: {best_result.expected_holding_days}-{best_result.max_holding_days} days")
            print(f"   Exit Strategy: {best_result.exit_strategy}")
        
        # ========== ALTERNATIVE STOCKS (Same logic as daily scan) ==========
        print("\n" + "═" * 70)
        print("💡 SECTOR TOP PICKS (Same as Daily Scan)")
        print("═" * 70)
        
        # Always show sector alternatives - same stocks that would appear in daily scan
        value_score = value_result.total_score if value_result else 0
        momentum_score = momentum_result.total_score if momentum_result else 0
        best_score = max(value_score, momentum_score)
        dump_risk = best_result.distribution_risk
        
        if sector != 'N/A':
            print(f"\n   🔍 Scanning {sector} sector (same scoring as daily scan)...")
            print()
            
            # Get alternatives using the SAME scoring engine as daily scan
            alternatives = get_sector_alternatives(
                symbol=symbol,
                sector=sector,
                max_price=None,  # No price filter for alternatives
                top_n=5,
                strategy="momentum",
            )
            
            if alternatives:
                print(f"   Rank | Symbol | Score | Risk Tier | Dump Risk | Entry Price")
                print(f"   " + "-" * 65)
                
                for rank, alt in enumerate(alternatives, 1):
                    tier_emoji = {
                        "GOOD": "✅",
                        "RISKY": "⚠️",
                        "VETO": "🚫",
                        "NOT_QUALIFIED": "⚪"
                    }.get(alt['risk_tier'], "❓")
                    
                    dump_emoji = {
                        "LOW": "✅",
                        "MEDIUM": "🟡", 
                        "HIGH": "⚠️",
                        "CRITICAL": "🚨"
                    }.get(alt['dump_risk'], "❓")
                    
                    print(f"   #{rank:<3} | {alt['symbol']:<6} | {alt['score']:>5.0f} | {tier_emoji} {alt['risk_tier']:<12} | {dump_emoji} {alt['dump_risk']:<8} | Rs. {alt['entry_price']:.2f}")
                
                # Show which ones are better than current stock
                better_count = sum(1 for a in alternatives if a['score'] > best_score)
                if better_count > 0:
                    print()
                    print(f"   💡 {better_count} stock(s) score higher than {symbol} ({best_score:.0f}/100)")
                    print(f"      Consider these for your sector allocation.")
                else:
                    print()
                    print(f"   ✅ {symbol} is the top scorer in {sector}!")
                
                # Show position guidance summary
                good_alts = [a for a in alternatives if a['risk_tier'] == 'GOOD']
                if good_alts:
                    print()
                    print(f"   🎯 ACTIONABLE PICKS (3-5% portfolio):")
                    for alt in good_alts[:3]:
                        print(f"      • {alt['symbol']} @ Rs.{alt['entry_price']:.2f} → Target Rs.{alt['target_price']:.2f}")
            else:
                print(f"   No qualifying stocks found in {sector} sector.")
                print(f"   Try: python paper_trader.py --scan --sector={sector.lower().replace(' ', '')}")
        else:
            print(f"\n   Sector not identified for {symbol}.")
            print(f"   💡 Run a full scan: python paper_trader.py --scan --strategy=momentum")
        
        # Final Recommendation
        print("\n" + "═" * 70)
        print("🏆 FINAL RECOMMENDATION")
        print("═" * 70)
        
        # Determine overall recommendation
        value_score = value_result.total_score if value_result else 0
        momentum_score = momentum_result.total_score if momentum_result else 0
        avg_score = (value_score + momentum_score) / 2
        
        # Check for red flags
        red_flags = []
        if best_result.distribution_risk in ["HIGH", "CRITICAL"]:
            red_flags.append(f"🚨 High distribution risk ({best_result.distribution_risk})")
        if best_result.days_until_unlock < 30:
            red_flags.append(f"🔓 Unlock risk in {best_result.days_until_unlock} days")
        if best_result.rsi > 70:
            red_flags.append(f"📈 RSI overbought ({best_result.rsi:.0f})")
        if fundamentals:
            if fundamentals.pe_ratio <= 0:
                red_flags.append(f"📊 PE ratio missing/negative (earnings issue)")
            elif fundamentals.pe_ratio > 40:
                red_flags.append(f"💰 PE ratio very high ({fundamentals.pe_ratio:.0f})")
            if fundamentals.eps <= 0:
                red_flags.append(f"📉 Negative EPS (company losing money)")
            if fundamentals.roe < 5 and fundamentals.roe != 0:
                red_flags.append(f"📉 Very low ROE ({fundamentals.roe:.1f}%)")
        
        if red_flags:
            print("\n⚠️ RED FLAGS DETECTED:")
            for flag in red_flags:
                print(f"   {flag}")
        
        # Calculate dividend and ROE for long-term check
        has_dividends = False
        roe_value = 0.0
        if dividends:
            total_div = sum((getattr(d, 'cash_pct', 0) or 0) + (getattr(d, 'bonus_pct', 0) or 0) for d in dividends[:3])
            has_dividends = total_div > 0
        if fundamentals:
            roe_value = fundamentals.roe or 0
        
        # Long-term vs Short-term recommendation
        print(f"\n📅 FOR LONG-TERM INVESTMENT (6+ months):")
        
        # Stricter long-term criteria: Need dividends OR good ROE
        long_term_fundamentals_ok = has_dividends or roe_value >= 10
        
        if value_score >= 70 and long_term_fundamentals_ok:
            print(f"   ✅ RECOMMENDED - Score: {value_score:.0f}/100")
            print(f"   Good fundamentals for holding. Buy on dips.")
        elif value_score >= 70 and not long_term_fundamentals_ok:
            print(f"   🟡 CAUTION - Score: {value_score:.0f}/100")
            print(f"   Technicals OK but weak fundamentals (No dividends, ROE {roe_value:.1f}%).")
            print(f"   Better for short-term trading than long-term holding.")
        elif value_score >= 50:
            print(f"   🟡 NEUTRAL - Score: {value_score:.0f}/100")
            print(f"   Average fundamentals. Consider better alternatives.")
        else:
            print(f"   ❌ NOT RECOMMENDED - Score: {value_score:.0f}/100")
            print(f"   Weak fundamentals. Avoid for long-term.")
        
        print(f"\n🚀 FOR SHORT-TERM SWING TRADE (1-2 weeks):")
        
        # Block momentum entry if dump risk is HIGH/CRITICAL and momentum is WEAK
        if should_block_entry:
            print(f"   ❌ NOT RECOMMENDED - Score: {momentum_score:.0f}/100")
            print(f"   {dump_risk_level} distribution risk. Operators dumped shares.")
            print(f"   Wait 1-2 sessions for dust to settle and re-accumulation to appear before considering any momentum entry.")
        elif momentum_score >= 70 and not red_flags:
            print(f"   ✅ RECOMMENDED - Score: {momentum_score:.0f}/100")
            print(f"   Good technicals. Entry: Rs.{best_result.entry_price_with_slippage:.2f}, Target: Rs.{best_result.target_price:.2f}")
        elif momentum_score >= 50:
            print(f"   🟡 RISKY - Score: {momentum_score:.0f}/100")
            print(f"   Moderate technicals. Only trade with tight stop loss.")
        else:
            print(f"   ❌ NOT RECOMMENDED - Score: {momentum_score:.0f}/100")
            print(f"   Weak momentum. Wait for better entry signals.")
        
        # Friend's recommendation verdict
        print(f"\n💬 YOUR FRIEND'S RECOMMENDATION:")
        if avg_score >= 65 and not red_flags:
            print(f"   ✅ This looks like a GOOD suggestion!")
            print(f"   Average Score: {avg_score:.0f}/100 across both strategies.")
        elif avg_score >= 50:
            print(f"   🟡 This is an AVERAGE pick.")
            print(f"   Score: {avg_score:.0f}/100. There might be better options.")
        else:
            print(f"   ❌ This does NOT look good right now.")
            print(f"   Score: {avg_score:.0f}/100. Ask your friend for their reasoning.")
        
        # ========== POSITION SIZING GUIDE BASED ON SCORE ==========
        print("\n" + "-" * 70)
        print("💼 POSITION SIZING GUIDE (Based on Overall Score)")
        print("-" * 70)
        risk_class_best = classify_stock_risk(best_result, screener=screener) if best_result else {"risk_tier": "NOT_QUALIFIED"}
        if risk_class_best["risk_tier"] == "VETO":
            print("   🚫 VETO: Paper-trade only due to multiple hard risk failures.")
            print("      Position size: 0% real portfolio")
        elif risk_class_best["risk_tier"] == "RISKY":
            print("   ⚠️ RISKY: 1-2% portfolio maximum or paper-trade.")
        elif best_score < 50:
            print("   🔴 Score < 50: AVOID / Paper trade only.")
            print("      Do not risk real capital on this setup.")
        elif best_score < 70:
            print("   🟡 Score 50-69: Small position, short-term swing with tight stop.")
            print("      Maximum 5% of portfolio. Exit quickly if stop is hit.")
        else:
            print("   🟢 Score ≥ 70: Normal position size allowed if risk rules are met.")
            print("      3-5% of portfolio. Follow the suggested target/stop.")
        
        # ========== EDUCATIONAL TIP SECTION ==========
        print("\n" + "-" * 70)
        print("🎓 EDUCATIONAL TIP (For Non-Technical Investors)")
        print("-" * 70)
        
        # Provide context based on today's situation
        if should_block_entry and dump_risk_level == "HIGH":
            print("   Today's Analysis Shows: \"Sunday Dump Pattern\"")
            print()
            print("   What happened?")
            print("   1. Operators bought shares over ~1 month at lower prices")
            if hasattr(best_result, 'broker_avg_cost') and best_result.broker_avg_cost > 0:
                print(f"   2. Their average cost was Rs. {best_result.broker_avg_cost:.2f}")
            if hasattr(best_result, 'today_open_price') and best_result.today_open_price > 0:
                print(f"   3. On Sunday, they pumped price to Rs. {best_result.today_open_price:.2f} at market open")
                print(f"   4. Retail traders saw \"momentum\" and bought at Rs. {best_result.today_open_price - 5:.2f}-{best_result.today_open_price:.2f}")
                print(f"   5. Operators dumped their holdings at Rs. {best_result.today_open_price:.2f}")
            print(f"   6. Price crashed to Rs. {best_result.ltp:.2f} by close")
            print()
            print("   Lesson: When broker avg is low, open spikes high, and volume jumps 2x:")
            print("          → Operators are SELLING, not buying")
            print("          → Avoid entering on such days")
            print("          → Wait 1-2 sessions for dust to settle")
            print()
            print("   This is why the system flagged it as HIGH RISK and blocked entry.")
        
        elif best_score >= 70:
            print("   Today's Analysis Shows: \"Good Opportunity\"")
            print()
            print("   What makes this a good pick?")
            print(f"   • Score: {best_score:.0f}/100 (above 70 = strong setup)")
            print(f"   • Dump Risk: {dump_risk} (operators not actively selling)")
            if fundamentals and fundamentals.roe > 12:
                print(f"   • ROE: {fundamentals.roe:.1f}% (company is profitable)")
            if best_result.rsi < 65:
                print(f"   • RSI: {best_result.rsi:.1f} (not overbought yet)")
            print()
            print("   Investment Approach:")
            print("   • For long-term: Consider accumulating on dips")
            print("   • For short-term: Follow the trade plan with stop loss")
            print(f"   • Position size: {5 if best_score < 80 else 10}% of portfolio maximum")
        
        elif best_score < 50:
            print("   Today's Analysis Shows: \"Weak Setup - Avoid\"")
            print()
            print("   Why is this risky?")
            if best_score < 40:
                print(f"   • Score: {best_score:.0f}/100 (below 40 = very weak)")
            else:
                print(f"   • Score: {best_score:.0f}/100 (below 50 = weak setup)")
            
            if dump_risk in ["HIGH", "CRITICAL"]:
                print(f"   • Dump Risk: {dump_risk} (operators may be selling)")
            if fundamentals and fundamentals.roe < 5:
                print(f"   • ROE: {fundamentals.roe:.1f}% (low profitability)")
            if best_result.rsi > 70:
                print(f"   • RSI: {best_result.rsi:.1f} (overbought)")
            print()
            print("   Better Strategy:")
            print("   • Wait for better entry signals")
            print("   • Look for alternative stocks in same sector")
            print("   • If you already own shares, consider profit-taking")
        
        else:
            print("   Today's Analysis Shows: \"Average Setup - Proceed with Caution\"")
            print()
            print(f"   Score: {best_score:.0f}/100 (50-70 = moderate)")
            print()
            print("   Trading Approach:")
            print("   • Only trade with tight stop loss (6-7%)")
            print("   • Keep position size small (3-5% of portfolio)")
            print("   • Monitor daily for any deterioration in signals")
            print("   • Be ready to exit if dump risk increases")
        
        print("\n" + "═" * 70)
        print("⚠️ DISCLAIMER: This is algorithmic analysis, NOT financial advice.")
        print("   Always do your own research before investing.")
        print("═" * 70 + "\n")
        
        return {
            "success": True,
            "symbol": symbol,
            "value_score": value_score,
            "momentum_score": momentum_score,
            "avg_score": avg_score,
            "red_flags": red_flags,
            "recommendation": {
                "long_term": "RECOMMENDED" if value_score >= 70 else "NEUTRAL" if value_score >= 50 else "AVOID",
                "short_term": "RECOMMENDED" if momentum_score >= 70 and not red_flags else "RISKY" if momentum_score >= 50 else "AVOID",
            }
        }

    def get_portfolio_status(self) -> Dict:
        """📊 Get current portfolio status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # BOUGHT positions (actual purchases)
        cursor.execute("""
            SELECT symbol, scan_date, score, entry_price_slippage, 
                   target_price, stop_loss_slippage, hold_days,
                   expected_hold_days, max_hold_days
            FROM paper_trades 
            WHERE status = 'BOUGHT'
            ORDER BY scan_date DESC
        """)
        bought_trades = cursor.fetchall()
        
        # RECOMMENDED positions (pending confirmation)
        cursor.execute("""
            SELECT symbol, scan_date, score, entry_price_slippage
            FROM paper_trades 
            WHERE status = 'RECOMMENDED'
            ORDER BY scan_date DESC
        """)
        pending_trades = cursor.fetchall()
        
        # Closed positions (TARGET_HIT, STOPPED_OUT, EXPIRED)
        cursor.execute("""
            SELECT symbol, scan_date, exit_date, score, 
                   entry_price_slippage, exit_price, profit_loss_pct, status
            FROM paper_trades 
            WHERE status IN ('TARGET_HIT', 'STOPPED_OUT', 'EXPIRED')
            ORDER BY exit_date DESC
            LIMIT 20
        """)
        closed_trades = cursor.fetchall()
        
        # Performance stats (only from actual trades - BOUGHT that closed)
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss_pct <= 0 THEN 1 ELSE 0 END) as losses,
                AVG(CASE WHEN profit_loss_pct > 0 THEN profit_loss_pct END) as avg_win,
                AVG(CASE WHEN profit_loss_pct <= 0 THEN profit_loss_pct END) as avg_loss,
                AVG(profit_loss_pct) as overall_avg
            FROM paper_trades 
            WHERE status IN ('TARGET_HIT', 'STOPPED_OUT', 'EXPIRED')
        """)
        stats = cursor.fetchone()
        
        conn.close()
        
        return {
            "bought_positions": len(bought_trades),
            "bought_trades": [
                {
                    "symbol": t[0],
                    "buy_date": t[1],
                    "score": t[2],
                    "entry": t[3],
                    "target": t[4],
                    "stop_loss": t[5],
                    "days_held": t[6],
                    "expected_hold": t[7] or 7,
                    "max_hold": t[8] or 15,
                    "status": "⚠️ REVIEW" if (t[6] or 0) >= (t[7] or 7) else "✅ HOLDING"
                }
                for t in bought_trades
            ],
            "pending_recommendations": len(pending_trades),
            "pending": [
                {
                    "symbol": t[0],
                    "scan_date": t[1],
                    "score": t[2],
                    "suggested_entry": t[3]
                }
                for t in pending_trades
            ],
            "closed_trades_count": len(closed_trades),
            "recent_closed": [
                {
                    "symbol": t[0],
                    "scan_date": t[1],
                    "exit_date": t[2],
                    "score": t[3],
                    "entry": t[4],
                    "exit": t[5],
                    "pnl_pct": t[6],
                    "status": t[7]
                }
                for t in closed_trades
            ],
            "performance": {
                "total_closed": stats[0] or 0,
                "wins": stats[1] or 0,
                "losses": stats[2] or 0,
                "win_rate": (stats[1] / stats[0] * 100) if stats[0] else 0,
                "avg_win_pct": stats[3] or 0,
                "avg_loss_pct": stats[4] or 0,
                "overall_avg_pct": stats[5] or 0
            }
        }
    
    def generate_report(self) -> str:
        """📈 Generate performance report."""
        status = self.get_portfolio_status()
        perf = status["performance"]
        
        report = f"""
{'='*70}
📊 PAPER TRADING PERFORMANCE REPORT
{'='*70}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

📈 OVERALL STATISTICS:
├── Total Closed Trades: {perf['total_closed']}
├── Winning Trades: {perf['wins']} ({perf['win_rate']:.1f}%)
├── Losing Trades: {perf['losses']}
├── Avg Win: +{perf['avg_win_pct']:.2f}%
├── Avg Loss: {perf['avg_loss_pct']:.2f}%
└── Overall Avg Return: {perf['overall_avg_pct']:.2f}%

📋 BOUGHT POSITIONS ({status['bought_positions']}):
"""
        for trade in status["bought_trades"]:
            report += f"   • {trade['symbol']}: Entry Rs.{trade['entry']:.2f} | Days: {trade['days_held']}\n"
        
        if status['pending_recommendations'] > 0:
            report += f"\n📋 PENDING RECOMMENDATIONS ({status['pending_recommendations']}):\n"
            for rec in status["pending"][:5]:
                report += f"   • {rec['symbol']}: Score {rec['score']:.0f} | Entry: Rs.{rec['suggested_entry']:.2f}\n"
        
        report += f"""
📜 RECENT CLOSED TRADES:
"""
        for trade in status["recent_closed"][:10]:
            pnl = trade.get("pnl_pct") or 0
            emoji = "✅" if pnl > 0 else "❌"
            report += f"   {emoji} {trade['symbol']}: {pnl:+.2f}% ({trade['status']})\n"
        
        report += f"""
{'='*70}
💡 ALGORITHM VALIDATION:
   Win Rate Target: > 55%
   Current Win Rate: {perf['win_rate']:.1f}%
   Status: {'✅ PROFITABLE' if perf['win_rate'] > 50 else '⚠️ NEEDS TUNING'}
{'='*70}
"""
        return report

    def run_stealth_scan(
        self,
        target_sector: str = None,
        max_price: float = None,
    ) -> Dict:
        """
        🕵️ STEALTH RADAR: Detect Sector Rotation / Smart Money Accumulation
        
        This scan identifies stocks where operators are quietly accumulating
        BEFORE a technical breakout. These are "stealth" positions:
        
        - Price is flat (poor Technical Score) → No breakout yet
        - Broker buying is heavy (excellent Broker Score) → Smart money accumulating
        - Distribution risk is LOW → Brokers haven't started selling yet
        
        The goal is to spot which SECTORS are seeing the most stealth
        accumulation, indicating where smart money is rotating into.
        
        Args:
            target_sector: Optional sector filter (e.g., "hydro", "bank")
            max_price: Optional max price filter
            
        Returns:
            Dict with stealth accumulation summary by sector
        """
        from collections import defaultdict
        
        logger.info("=" * 70)
        logger.info("🕵️ STEALTH RADAR - Detecting Smart Money Accumulation")
        logger.info("=" * 70)
        
        print("\n" + "═" * 70)
        print("🕵️ STEALTH RADAR - Smart Money Sector Rotation Scanner")
        print("═" * 70)
        print("\n📊 Scanning for stocks with:")
        print("   • LOW Technical Score (price hasn't broken out)")
        print("   • HIGH Broker Score (heavy accumulation)")
        print("   • LOW Distribution Risk (brokers not selling)")
        print("\n⏳ Running 4-Pillar analysis on all stocks...")
        
        # Initialize screener (use value strategy as base)
        screener = MasterStockScreener(
            strategy="value",
            target_sector=target_sector,
            max_price=max_price,
        )
        
        # Run full scan - use run_full_analysis with low min_score to get ALL stocks
        all_stocks = screener.run_full_analysis(
            min_score=0,  # Get ALL stocks regardless of score
            top_n=500,    # Get up to 500 stocks
            include_rejected=False,
            quick_mode=False,
        )
        
        # Check if historical fallback was used
        using_historical = getattr(screener, '_using_historical_fallback', False)
        
        if using_historical:
            print("\n   📅 Note: Using last trading day's data (market closed)")
        
        # If still no stocks (no historical data available either)
        if not all_stocks:
            print("\n⚠️  No market data available.")
            print("   This could mean:")
            print("   • Market is closed and no recent historical data")
            print("   • Network/API connectivity issues")
            print("   Run this scan during market hours for best results.")
            return {"success": False, "error": "No data available"}
        
        print(f"\n✅ Analyzed {len(all_stocks)} stocks")
        
        # ========== STEALTH FILTERING CRITERIA ==========
        # Max scores for reference:
        # - Broker/Institutional: 30 points
        # - Technical: 30 points (value strategy)
        
        MAX_BROKER_SCORE = 30.0
        MAX_TECH_SCORE = 30.0
        
        # Thresholds:
        # - Technical < 40% of max (price hasn't broken out) = < 12 points
        # - Broker > 80% of max (heavy accumulation) = > 24 points
        TECH_THRESHOLD = MAX_TECH_SCORE * 0.40  # 12 points
        BROKER_THRESHOLD = MAX_BROKER_SCORE * 0.80  # 24 points
        
        stealth_stocks = []
        
        for stock in all_stocks:
            # Condition 1: Low Technical Score (no breakout yet)
            tech_score = stock.pillar4_technical
            if tech_score >= TECH_THRESHOLD:
                continue  # Price already moving, skip
            
            # Condition 2: High Broker Score (heavy accumulation)
            broker_score = stock.pillar1_broker
            if broker_score < BROKER_THRESHOLD:
                continue  # Not enough broker interest, skip
            
            # Condition 3: Low Distribution Risk (brokers not selling)
            dist_risk = stock.distribution_risk
            if dist_risk and dist_risk.upper() not in ["LOW", ""]:
                continue  # Brokers may be selling, skip
            
            # Stock passes all stealth criteria!
            stealth_stocks.append(stock)
        
        print(f"\n🎯 Found {len(stealth_stocks)} STEALTH stocks matching criteria")
        
        if not stealth_stocks:
            print("\n" + "─" * 70)
            print("📊 NO STEALTH ACCUMULATION DETECTED")
            print("─" * 70)
            print("\n   No stocks currently match the stealth criteria:")
            print(f"   • Technical Score < {TECH_THRESHOLD:.0f} (40% of max)")
            print(f"   • Broker Score > {BROKER_THRESHOLD:.0f} (80% of max)")
            print("   • Distribution Risk = LOW")
            print("\n   This could mean:")
            print("   • Operators are not actively accumulating")
            print("   • Accumulation phase may have ended (prices moving)")
            print("   • Try scanning a specific sector with --sector=hydro")
            return {"success": True, "stealth_stocks": [], "sector_summary": {}}
        
        # ========== GROUP BY SECTOR ==========
        sector_groups = defaultdict(list)
        for stock in stealth_stocks:
            sector = stock.sector if stock.sector else "Unknown"
            sector_groups[sector].append(stock)
        
        # Sort sectors by number of stealth stocks (descending)
        sorted_sectors = sorted(sector_groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        # ========== OUTPUT REPORT ==========
        print("\n" + "═" * 70)
        print("📡 SECTOR ROTATION RADAR - Where Smart Money is Moving")
        print("═" * 70)
        
        sector_summary = {}
        
        for sector, stocks in sorted_sectors:
            stock_count = len(stocks)
            avg_broker_score = sum(s.pillar1_broker for s in stocks) / stock_count
            avg_tech_score = sum(s.pillar4_technical for s in stocks) / stock_count
            total_volume = sum(s.volume_spike for s in stocks if s.volume_spike)
            
            # Sector heat level based on stock count
            if stock_count >= 5:
                heat = "🔥🔥🔥 HOT"
            elif stock_count >= 3:
                heat = "🔥🔥 WARM"
            else:
                heat = "🔥 ACTIVE"
            
            sector_summary[sector] = {
                "stock_count": stock_count,
                "avg_broker_score": round(avg_broker_score, 1),
                "avg_tech_score": round(avg_tech_score, 1),
                "heat_level": heat,
                "stocks": [s.symbol for s in stocks],
            }
            
            print(f"\n{'─' * 70}")
            print(f"📌 {sector.upper()} - {heat}")
            print(f"   Stealth Stocks: {stock_count}")
            print(f"   Avg Broker Score: {avg_broker_score:.1f}/30")
            print(f"   Avg Technical Score: {avg_tech_score:.1f}/30 (low = good for stealth)")
            print(f"\n   Stocks in accumulation:")
            
            # Sort stocks by broker score (highest first)
            stocks_sorted = sorted(stocks, key=lambda s: s.pillar1_broker, reverse=True)
            
            for stock in stocks_sorted[:10]:  # Show top 10 per sector
                broker_pct = (stock.pillar1_broker / MAX_BROKER_SCORE) * 100
                tech_pct = (stock.pillar4_technical / MAX_TECH_SCORE) * 100
                dist = stock.distribution_risk or "N/A"
                
                # Broker profit info
                broker_profit = ""
                if stock.broker_profit_pct:
                    broker_profit = f" | Broker Profit: {stock.broker_profit_pct:+.1f}%"
                
                print(f"   • {stock.symbol:8} | LTP: Rs.{stock.ltp:>7.2f} | "
                      f"Broker: {stock.pillar1_broker:>5.1f} ({broker_pct:.0f}%) | "
                      f"Tech: {stock.pillar4_technical:>5.1f} ({tech_pct:.0f}%) | "
                      f"Risk: {dist}{broker_profit}")
        
        # ========== INTERPRETATION GUIDE ==========
        print("\n" + "═" * 70)
        print("📖 HOW TO USE THIS RADAR")
        print("═" * 70)
        print("""
   🎯 WHAT THIS SHOWS:
   Stocks where "smart money" (brokers/operators) is quietly buying
   BEFORE the price has started moving up. These are early signals.

   📊 INTERPRETING THE RESULTS:
   • 🔥🔥🔥 HOT sectors have 5+ stocks being accumulated
   • High Broker Score = Heavy institutional buying
   • Low Technical Score = Price hasn't broken out yet
   • Low Distribution Risk = Brokers aren't selling yet

   ⚠️ IMPORTANT WARNINGS:
   • This is NOT a buy signal - it's early intelligence
   • Wait for Technical confirmation (EMA crossover, volume spike)
   • Set alerts for these stocks and monitor for breakouts
   • Accumulation can last weeks before a move happens

   💡 SUGGESTED WORKFLOW:
   1. Note the HOT sectors from this radar
   2. Add top stealth stocks to your watchlist
   3. Run --action=scan daily to catch when technicals improve
   4. Enter ONLY when both Broker AND Technical scores are strong
""")
        
        print("═" * 70)
        
        return {
            "success": True,
            "total_analyzed": len(all_stocks),
            "stealth_count": len(stealth_stocks),
            "sector_summary": sector_summary,
            "stealth_stocks": [
                {
                    "symbol": s.symbol,
                    "sector": s.sector,
                    "ltp": s.ltp,
                    "broker_score": s.pillar1_broker,
                    "tech_score": s.pillar4_technical,
                    "distribution_risk": s.distribution_risk,
                    "broker_profit_pct": s.broker_profit_pct,
                }
                for s in stealth_stocks
            ],
        }


def main():
    parser = argparse.ArgumentParser(description="NEPSE Paper Trading Engine")
    parser.add_argument(
        "--action",
        choices=["scan", "update", "status", "report", "buy", "skip", "pending", "analyze", "stealth-scan"],
        default="status",
        help="""Action to perform:
  scan         - Find new stock recommendations
  stealth-scan - Detect smart money sector rotation (accumulation radar)
  update       - Check if BOUGHT positions hit target/stop
  status       - Show portfolio overview
  report       - Generate performance report
  buy          - Confirm a purchase (use with --symbol and --price)
  skip         - Mark a recommendation as skipped
  pending      - List all pending recommendations
  analyze      - Deep analysis of a specific stock (use with --stock=SYMBOL)"""
    )
    # Compatibility aliases for requested two-command workflow:
    # python paper_trader.py --scan --strategy=momentum
    # python paper_trader.py --analyze SYMBOL
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Alias for --action=scan"
    )
    parser.add_argument(
        "--analyze",
        type=str,
        default=None,
        help="Alias for --action=analyze --stock=SYMBOL"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Historical date for analysis (YYYY-MM-DD format). Analyzes as if today was that date."
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Stock symbol for buy/skip actions (e.g., --symbol=NICA)"
    )
    parser.add_argument(
        "--price",
        type=float,
        help="Actual purchase price for buy action (e.g., --price=368.50)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: Only analyze top 50 stocks by volume (5x faster)"
    )
    parser.add_argument(
        "--with-news",
        action="store_true",
        help="Enable Playwright news scraping for top picks (slower)"
    )
    parser.add_argument(
        "--with-ai",
        action="store_true",
        help="Enable OpenAI AI verdict for top picks (requires OPENAI_API_KEY)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full analysis: Enable both news scraping AND AI verdict"
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Run browser in visible mode (not headless) to watch scraping"
    )
    parser.add_argument(
        "--strategy",
        choices=["value", "momentum"],
        default="value",
        help="Trading strategy to apply (value: Balanced/Fundamental, momentum: Trend/Technical)"
    )
    parser.add_argument(
    "--sector",
    type=str,
    default="all",
    choices=[
        "all",
        "bank", "devbank", "finance", "microfinance", 
        "hydro", "life_insurance", "non_life_insurance", 
        "hotel", "manufacturing", "trading", "investment", "others"
    ],
    help="Filter by NEPSE sector (default: all)."
    )
    
    # Budget filter
    parser.add_argument(
        "--max-price",
        type=float,
        default=None,
        help="Maximum stock price you can afford (e.g., --max-price 500). Stocks above this price are skipped."
    )
    
    # Single stock analysis
    parser.add_argument(
        "--stock",
        type=str,
        default=None,
        help="Stock symbol to analyze (e.g., --stock=NHPC). Use with --action=analyze"
    )
    
    # Portfolio management (strict holding rules)
    parser.add_argument(
        "--portfolio",
        action="store_true",
        help="Show portfolio status with holding rules (9%% max, 7-day hold, 3 exit triggers)"
    )
    parser.add_argument(
        "--buy-picks",
        nargs='*',
        metavar='SYMBOL',
        help="Buy top scan picks or specific symbols (e.g., --buy-picks GVL PPCL HPPL)"
    )
    parser.add_argument(
        "--sell",
        type=str,
        default=None,
        metavar='SYMBOL',
        help="Sell a position from portfolio (e.g., --sell GVL)"
    )
    parser.add_argument(
        "--sell-price",
        type=float,
        default=None,
        help="Exit price for --sell command"
    )
    parser.add_argument(
        "--logs",
        choices=["show", "hide"],
        default="hide",
        help="Logger output mode: 'show' for full logs, 'hide' for quiet mode (default, errors only)."
    )
    
    # ========== ADVANCED INTELLIGENCE COMMANDS ==========
    parser.add_argument(
        "--bulk-deals",
        action="store_true",
        help="Track large block trades (>1Cr value or 10K+ shares) - insider/promoter activity"
    )
    parser.add_argument(
        "--sector-rotation",
        action="store_true",
        help="Weekly sector momentum ranking and rotation signals"
    )
    parser.add_argument(
        "--smart-money",
        action="store_true",
        help="Track institutional buying patterns and smart money flow"
    )
    parser.add_argument(
        "--heatmap",
        action="store_true",
        help="NEPSE market breadth heatmap - % stocks green/red by sector"
    )
    parser.add_argument(
        "--tech-score",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="Multi-timeframe technical composite score for a stock"
    )
    parser.add_argument(
        "--order-flow",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="Order flow analysis - delta, absorption, liquidity grabs"
    )
    parser.add_argument(
        "--optimize-portfolio",
        nargs='+',
        metavar="SYMBOL",
        help="Optimize portfolio allocation for given symbols (e.g., --optimize-portfolio GVL PPCL NABIL)"
    )
    parser.add_argument(
        "--dividend-forecast",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="Forecast dividend for a stock based on EPS and historical patterns"
    )
    parser.add_argument(
        "--positioning",
        action="store_true",
        help="Market-wide quant positioning indicators (%% stocks above SMA)"
    )
    parser.add_argument(
        "--broker-intelligence",
        action="store_true",
        help="Advanced broker analysis: Aggressive Holdings, Stockwise Table, Favourites"
    )
    parser.add_argument(
        "--price-targets",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="🎯 Intelligent price target prediction - Fibonacci, ATR, Volume Profile, Resistance levels"
    )
    parser.add_argument(
        "--signal",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="📊 Generate entry/exit trading signal with precise timing (when to buy/sell/hold)"
    )
    parser.add_argument(
        "--calendar",
        action="store_true",
        help="📅 Trade Calendar: Scan all stocks and show which to buy on which dates for the next 30 days"
    )
    parser.add_argument(
        "--calendar-days",
        type=int,
        default=30,
        help="Number of days to look ahead for --calendar (default: 30)"
    )
    parser.add_argument(
        "--calendar-max-stocks",
        type=int,
        default=0,
        help="Max stocks to analyze for --calendar (0 = all stocks, default: 0)"
    )
    parser.add_argument(
        "--ipo-exit",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="📈 Analyze IPO exit signals for newly listed stock (when to sell IPOs)"
    )
    parser.add_argument(
        "--hold-or-sell",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="📊 Analyze existing position: Should you HOLD or SELL? (use with --buy-price)"
    )
    parser.add_argument(
        "--buy-price",
        type=float,
        default=None,
        help="Your purchase price for --hold-or-sell analysis (required)"
    )
    parser.add_argument(
        "--buy-date",
        type=str,
        default=None,
        help="Your purchase date (YYYY-MM-DD) for --hold-or-sell analysis (optional)"
    )

    args = parser.parse_args()

    # Enforce runtime logging level for this process and imported modules.
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if args.logs == "show" else "ERROR",
        enqueue=False
    )

    if args.scan:
        args.action = "scan"
    if args.analyze:
        args.action = "analyze"
        args.stock = args.analyze

    # Normalize "all" sector to no filter for existing workflows
    if args.sector == "all":
        args.sector = None

    def _resolve_current_price(fetcher, symbol: str) -> float:
        """
        Resolve the best available current price with robust fallbacks.

        Priority:
        1) Live market snapshot (during market hours)
        2) Official daily close from price history (preferred after market close)
        3) Intraday scrip graph last contract rate
        4) Latest historical close
        """
        symbol = symbol.upper().strip()
        live_price = None
        eod_price = None
        latest_hist_close = None
        market_open = None

        try:
            market_open = bool(fetcher.is_market_open())
        except Exception:
            market_open = None

        # 1) Live market snapshot
        try:
            live_data = fetcher.fetch_live_market()
            if hasattr(live_data, "to_dict"):
                stocks = live_data.to_dict(orient="records")
            else:
                stocks = live_data if isinstance(live_data, list) else []

            for s in stocks:
                if str(s.get("symbol", "")).upper() == symbol:
                    live_price = float(s.get("lastTradedPrice", 0) or s.get("close", 0) or 0)
                    if live_price > 0:
                        break
        except Exception as e:
            logger.debug(f"{symbol}: live price unavailable: {e}")

        # 2) Historical latest close (also gives official EOD after close)
        try:
            hist_df = fetcher.fetch_price_history(symbol, days=10)
            if hist_df is not None and not hist_df.empty:
                last_row = hist_df.iloc[-1]
                latest_hist_close = float(last_row.get("close", 0) or 0)
                last_date = last_row.get("date")
                today = datetime.now().date()
                if last_date == today and latest_hist_close > 0:
                    eod_price = latest_hist_close
        except Exception as e:
            logger.debug(f"{symbol}: history price fallback unavailable: {e}")

        # Prefer official EOD close after market hours
        if market_open is False and eod_price and eod_price > 0:
            logger.debug(f"{symbol}: using official EOD close Rs.{eod_price:.2f}")
            return eod_price

        if live_price and live_price > 0:
            return live_price

        if eod_price and eod_price > 0:
            return eod_price

        # 3) Intraday graph fallback
        try:
            graph = fetcher.fetch_scrip_price_graph(symbol)
            if isinstance(graph, list) and graph:
                last_rate = float(graph[-1].get("contractRate", 0) or 0)
                if last_rate > 0:
                    logger.debug(f"{symbol}: using intraday graph fallback Rs.{last_rate:.2f}")
                    return last_rate
        except Exception as e:
            logger.debug(f"{symbol}: intraday graph fallback unavailable: {e}")

        # 4) Latest historical close fallback
        if latest_hist_close and latest_hist_close > 0:
            logger.debug(f"{symbol}: using latest historical close Rs.{latest_hist_close:.2f}")
            return latest_hist_close

        return None
    
    # Handle portfolio commands before PaperTrader instantiation
    if args.portfolio or args.buy_picks is not None or args.sell:
        pm = PortfolioManager()
        
        if args.sell:
            # Sell a position
            sell_price = args.sell_price or pm.get_ltp(args.sell)
            if pm.remove_position(args.sell, sell_price, "USER_SELL"):
                print(f"✅ Sold {args.sell} @ Rs.{sell_price:.2f}")
            else:
                print(f"❌ {args.sell} not found in portfolio")
            pm.print_status()
            sys.exit(0)
        
        if args.buy_picks is not None:
            # Buy specific symbols or run scan and buy top picks
            if args.buy_picks:
                # Specific symbols provided
                for symbol in args.buy_picks:
                    ltp = pm.get_ltp(symbol)
                    if ltp > 0:
                        pm.add_position(symbol.upper(), ltp)
                    else:
                        print(f"❌ Could not get price for {symbol}")
            else:
                # No symbols - run scan and buy top picks
                print("🔍 Running scan to find top picks...")
                screener = MasterStockScreener(strategy="momentum")
                results = screener.run_full_analysis(min_score=70, top_n=10)
                if results:
                    bought = pm.buy_top_picks(results)
                    if bought:
                        print(f"✅ Bought: {', '.join(bought)}")
                    else:
                        print("⚠️ Portfolio full or no qualifying stocks")
                else:
                    print("⚠️ No qualifying stocks found")
            pm.print_status()
            sys.exit(0)
        
        if args.portfolio:
            # Just show portfolio status
            # Optionally run a quick scan to show today's picks
            try:
                screener = MasterStockScreener(strategy="momentum")
                results = screener.run_full_analysis(min_score=70, top_n=5, quick_mode=True)
                pm.print_status(scan_results=results)
            except Exception as e:
                logger.debug(f"Could not run scan for portfolio view: {e}")
                pm.print_status()
            sys.exit(0)
    
    # ========== ADVANCED INTELLIGENCE COMMANDS ==========
    # These are standalone intelligence modules that don't need paper trading database
    if args.bulk_deals:
        from intelligence.bulk_deal_analyzer import analyze_bulk_deals
        report = analyze_bulk_deals(sector=args.sector)
        print(report)
        sys.exit(0)
    
    if args.sector_rotation:
        from intelligence.sector_rotation import get_sector_rotation_report
        report = get_sector_rotation_report()
        print(report)
        sys.exit(0)
    
    if args.smart_money:
        from intelligence.smart_money_tracker import get_smart_money_report
        report = get_smart_money_report(sector=args.sector)
        print(report)
        sys.exit(0)
    
    if args.heatmap:
        from intelligence.market_breadth import get_market_heatmap
        report = get_market_heatmap()
        print(report)
        sys.exit(0)
    
    if args.tech_score:
        from intelligence.technical_composite import get_composite_score_report
        report = get_composite_score_report(args.tech_score)
        print(report)
        sys.exit(0)
    
    if args.order_flow:
        from intelligence.order_flow import get_order_flow_report
        report = get_order_flow_report(args.order_flow)
        print(report)
        sys.exit(0)
    
    if args.optimize_portfolio:
        from intelligence.portfolio_optimizer import optimize_portfolio
        report = optimize_portfolio(args.optimize_portfolio)
        print(report)
        sys.exit(0)
    
    if args.dividend_forecast:
        from intelligence.dividend_forecaster import get_dividend_forecast
        report = get_dividend_forecast(args.dividend_forecast)
        print(report)
        sys.exit(0)
    
    if args.positioning:
        from intelligence.quant_positioning import get_positioning_report
        report = get_positioning_report()
        print(report)
        sys.exit(0)
    
    if args.broker_intelligence:
        from intelligence.broker_intelligence import get_broker_intelligence_report
        report = get_broker_intelligence_report(sector=args.sector)
        print(report)
        sys.exit(0)
    
    if args.price_targets:
        from analysis.price_target_analyzer import PriceTargetAnalyzer
        from data.fetcher import NepseFetcher
        from data.sharehub_api import ShareHubAPI
        import os
        
        symbol = args.price_targets.upper()
        print(f"\n🎯 Analyzing price targets for {symbol}...")
        
        # Initialize components
        fetcher = NepseFetcher()
        sharehub_token = os.getenv("SHAREHUB_AUTH_TOKEN")
        sharehub = ShareHubAPI(auth_token=sharehub_token) if sharehub_token else None
        
        current_price = _resolve_current_price(fetcher, symbol)
        if current_price:
            print(f"   📈 Current Price: Rs. {current_price:,.2f}")
        
        # Run analysis with live price
        analyzer = PriceTargetAnalyzer(fetcher=fetcher, sharehub=sharehub)
        analysis = analyzer.analyze(symbol, lookback_days=365, current_price=current_price)
        
        # Print formatted report
        report = analyzer.format_report(analysis)
        print(report)
        sys.exit(0)
    
    # ========== TRADE CALENDAR: Scan all stocks for entry opportunities ==========
    if args.calendar:
        from analysis.technical_signal_engine import TechnicalSignalEngine
        from data.fetcher import NepseFetcher
        from data.sharehub_api import ShareHubAPI
        from datetime import date, timedelta
        import time
        import os
        
        print("\n" + "=" * 70)
        print("📅 TRADE CALENDAR: Scanning all stocks for entry opportunities...")
        print("=" * 70)
        
        # Initialize
        fetcher = NepseFetcher()
        sharehub_token = os.getenv("SHAREHUB_AUTH_TOKEN")
        sharehub = ShareHubAPI(auth_token=sharehub_token) if sharehub_token else None
        engine = TechnicalSignalEngine(fetcher=fetcher, sharehub=sharehub)
        
        # Get all stocks - try live market first, fallback to company list
        print("📊 Fetching market data...")
        all_stocks = []
        try:
            # Try live market first (has volume data)
            live_data = fetcher.fetch_live_market()
            if hasattr(live_data, 'to_dict'):
                all_stocks = live_data.to_dict(orient='records')
            elif isinstance(live_data, list):
                all_stocks = live_data
            
            # If live market empty (market closed), use company list
            if not all_stocks:
                print("   ⚠️ Market closed, using company list...")
                company_list = fetcher.fetch_company_list()
                if isinstance(company_list, list):
                    # Company list returns StockData objects (Pydantic), not dicts
                    for c in company_list:
                        symbol = ""
                        if isinstance(c, dict):
                            symbol = str(c.get("symbol", "")).strip()
                        else:
                            symbol = str(getattr(c, "symbol", "")).strip()
                        if symbol:
                            all_stocks.append({
                                "symbol": symbol,
                                "lastTradedPrice": 0,      # LTP fetched inside signal engine
                                "totalTradedValue": 1000000,  # Synthetic turnover for sorting fallback
                            })
        except Exception as e:
            print(f"❌ Error fetching market data: {e}")
            sys.exit(1)
        
        # Filter stocks - only analyze top 100 by turnover (or first 100 for speed)
        # This is a balance between coverage and speed
        active_stocks = []
        for s in all_stocks:
            try:
                # Support both dict payloads and object payloads
                if isinstance(s, dict):
                    symbol = str(s.get("symbol", "")).strip()
                    price = float(s.get("lastTradedPrice", 0) or s.get("close", 0) or 0)
                    turnover = float(s.get("totalTradedValue", 0) or 0)
                else:
                    symbol = str(getattr(s, "symbol", "")).strip()
                    price = float(getattr(s, "lastTradedPrice", 0) or getattr(s, "close", 0) or 0)
                    turnover = float(getattr(s, "totalTradedValue", 0) or 0)
                
                # Skip if no symbol
                if not symbol:
                    continue
                    
                active_stocks.append({
                    'symbol': symbol,
                    'price': price,
                    'turnover': turnover
                })
            except:
                continue
        
        # Sort by turnover (active first) for processing order only
        active_stocks.sort(key=lambda x: x['turnover'], reverse=True)
        
        # Coverage policy:
        # - Default: analyze ALL stocks (captures bottom-reversal candidates too)
        # - --quick: fast mode with limited universe
        # - --calendar-max-stocks N: explicit cap override
        if args.calendar_max_stocks and args.calendar_max_stocks > 0:
            max_stocks = args.calendar_max_stocks
            active_stocks = active_stocks[:max_stocks]
        elif args.quick:
            max_stocks = 30
            active_stocks = active_stocks[:max_stocks]
        else:
            max_stocks = len(active_stocks)  # all stocks
        
        est_time = len(active_stocks) * 1.5
        mode_label = " (quick mode)" if args.quick else " (full market mode)"
        print(f"📈 Analyzing {len(active_stocks)} stocks{mode_label}...")
        print(f"⏳ Estimated time: {est_time // 60:.0f}m {est_time % 60:.0f}s")
        print()
        
        # Sector alias map for calendar filtering
        sector_alias = {
            "bank": "commercial bank",
            "devbank": "development bank",
            "finance": "finance",
            "microfinance": "microfinance",
            "hydro": "hydro",
            "life_insurance": "life insurance",
            "non_life_insurance": "non life insurance",
            "hotel": "hotel",
            "manufacturing": "manufacturing",
            "trading": "trading",
            "investment": "investment",
            "others": "other",
        }
        target_sector = args.sector
        symbol_sector_map = {}
        if target_sector:
            try:
                company_list = fetcher.fetch_company_list()
                if isinstance(company_list, list):
                    for c in company_list:
                        if isinstance(c, dict):
                            sym = str(c.get("symbol", "")).upper().strip()
                            sec = str(c.get("sector", "")).lower().strip()
                        else:
                            sym = str(getattr(c, "symbol", "")).upper().strip()
                            sec = str(getattr(c, "sector", "")).lower().strip()
                        if sym:
                            symbol_sector_map[sym] = sec
            except Exception as e:
                logger.debug(f"Calendar sector mapping unavailable: {e}")

        # Store per-stock candidates, then rank per day over the full range
        candidate_entries = []
        today = date.today()
        calendar_days = args.calendar_days
        
        # Analyze each stock (with progress)
        total = len(active_stocks)
        for idx, stock_info in enumerate(active_stocks, 1):
            symbol = stock_info['symbol']
            price = stock_info['price']
            
            # Progress bar
            progress = int((idx / total) * 40)
            bar = "█" * progress + "░" * (40 - progress)
            print(f"\r   [{bar}] {idx}/{total} Analyzing {symbol:<8}", end="", flush=True)
            
            try:
                # Optional sector filter
                if target_sector:
                    symbol_sector = symbol_sector_map.get(symbol.upper(), "")
                    sector_key = sector_alias.get(target_sector, target_sector).lower()
                    if sector_key and sector_key not in symbol_sector:
                        continue

                # Get stock sector for momentum calculation
                stock_sector = symbol_sector_map.get(symbol.upper(), "")
                
                # Generate signal with sector-aware momentum
                signal = engine.generate_signal(symbol, current_price=price, sector=stock_sector)
                
                # Only include stocks with entry opportunity in next N days
                if signal.estimated_entry_date and signal.days_until_entry <= calendar_days:
                    entry_date = signal.estimated_entry_date
                    days_away = (entry_date - today).days

                    # Apply affordability filter if requested
                    if args.max_price is not None and signal.entry_zone_low > args.max_price:
                        continue

                    # Store candidate info
                    t1_pct = (signal.target_1 / signal.entry_zone_low - 1) * 100 if signal.entry_zone_low > 0 else 0
                    score = (signal.entry_probability * 0.55) + (signal.t1_probability * 0.25) + (min(15, max(0, t1_pct)) * 1.5)
                    candidate_entries.append({
                        'symbol': symbol,
                        'entry_date': entry_date,
                        'entry_price': signal.entry_zone_low,
                        'current_price': price,
                        'entry_prob': signal.entry_probability,
                        't1_price': signal.target_1,
                        't1_pct': t1_pct,
                        't1_prob': signal.t1_probability,
                        'stop_loss': signal.stop_loss,
                        'days_away': days_away,
                        'signal_type': signal.signal_type.value,
                        'trend_phase': signal.trend_phase.value,
                        'score': score,
                    })
                
                # Small delay for rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue
        
        # Build daily calendar for EVERY day in range (no gaps)
        calendar_data = {}
        for d in range(calendar_days + 1):
            day = today + timedelta(days=d)
            date_key = day.strftime("%Y-%m-%d")
            day_entries = []
            for c in candidate_entries:
                # Distance penalty: prioritize stocks whose expected entry is near this day
                dist = abs((c["entry_date"] - day).days)
                # Strongly favor near-date entries; avoid long-distance carryover noise
                daily_score = c["score"] - (dist * 6.0)
                # Eligibility by distance window (tighter when range is short)
                max_dist = 2 if calendar_days <= 7 else 3
                # Only include if relevant for this day
                if dist <= max_dist and daily_score >= 20:
                    e = dict(c)
                    e["daily_score"] = daily_score
                    day_entries.append(e)
            day_entries.sort(key=lambda x: (-x["daily_score"], -x["entry_prob"], -x["t1_pct"]))
            calendar_data[date_key] = day_entries[:5]

        print("\n\n" + "=" * 70)
        sector_label = f" | Sector: {target_sector.upper()}" if target_sector else ""
        price_label = f" | Max Price: Rs.{args.max_price:.0f}" if args.max_price is not None else ""
        print(f"📅 TRADE CALENDAR - Daily Top Picks (Next {calendar_days} Days){sector_label}{price_label}")
        print("=" * 70)

        total_opportunities = 0
        sorted_dates = sorted(calendar_data.keys())
        for date_key in sorted_dates:
            top_entries = calendar_data[date_key]

            print(f"\n🗓️ {date_key}")
            print("-" * 80)
            print(f"   {'Rank':<5} {'Stock':<8} {'Entry@':<9} {'T1':<14} {'EntryProb':<10} {'T1Prob':<8} {'Score'}")
            print("-" * 80)
            if not top_entries:
                print("   (No suitable picks for this day under current filters)")
            else:
                for i, entry in enumerate(top_entries, 1):
                    total_opportunities += 1
                    t1_txt = f"Rs.{entry['t1_price']:.0f} (+{entry['t1_pct']:.0f}%)"
                    print(f"   #{i:<4} {entry['symbol']:<8} Rs.{entry['entry_price']:<6.0f} {t1_txt:<14} {entry['entry_prob']:.0f}%{'':<6} {entry['t1_prob']:.0f}%{'':<3} {entry['daily_score']:.1f}")

        print("\n" + "=" * 70)
        print(f"📊 SUMMARY: {total_opportunities} picks (max 5/day) in next {calendar_days} days")
        print("=" * 70)
        
        # Quick picks for immediate action (today + next 2 days)
        immediate = []
        for d in sorted_dates[:3]:
            immediate.extend(calendar_data.get(d, []))
        if immediate:
            # Deduplicate symbols across first 3 days
            best_by_symbol = {}
            for e in immediate:
                sym = e["symbol"]
                if sym not in best_by_symbol or e["daily_score"] > best_by_symbol[sym]["daily_score"]:
                    best_by_symbol[sym] = e
            immediate = list(best_by_symbol.values())
            immediate.sort(key=lambda x: (-x['daily_score'], -x['entry_prob'], -x['t1_pct']))
            print("\n🔥 TOP IMMEDIATE PICKS (This Week):")
            print("-" * 50)
            for i, entry in enumerate(immediate[:5], 1):
                print(f"   #{i} {entry['symbol']} → Buy at Rs.{entry['entry_price']:.0f}")
                print(f"      📅 Entry: {entry['entry_date'].strftime('%Y-%m-%d')} | T1: +{entry['t1_pct']:.0f}% | Prob: {entry['entry_prob']:.0f}%")
        
        print("\n💡 Use --signal <SYMBOL> for detailed entry/exit plan.")
        sys.exit(0)
    
    if args.signal:
        from analysis.technical_signal_engine import TechnicalSignalEngine
        from data.fetcher import NepseFetcher
        from data.sharehub_api import ShareHubAPI
        import os
        
        symbol = args.signal.upper()
        print(f"\n📊 Generating trading signal for {symbol}...")
        
        # Initialize components
        fetcher = NepseFetcher()
        sharehub_token = os.getenv("SHAREHUB_AUTH_TOKEN")
        sharehub = ShareHubAPI(auth_token=sharehub_token) if sharehub_token else None
        
        current_price = _resolve_current_price(fetcher, symbol)
        
        # Get sector for momentum calculation
        companies = fetcher.fetch_company_list(active_only=True)
        stock_sector = ""
        for company in companies:
            if company.symbol.upper() == symbol:
                stock_sector = company.sector
                break
        
        # Generate signal with sector-aware momentum
        engine = TechnicalSignalEngine(fetcher=fetcher, sharehub=sharehub)
        signal = engine.generate_signal(symbol, current_price=current_price, sector=stock_sector)
        
        # Print formatted report
        report = engine.format_signal_report(signal)
        print(report)
        sys.exit(0)
    
    if args.ipo_exit:
        from intelligence.ipo_exit_analyzer import IPOExitAnalyzer
        
        symbol = args.ipo_exit.upper()
        print(f"\n📊 Analyzing IPO exit signals for {symbol}...")
        
        analyzer = IPOExitAnalyzer()
        result = analyzer.analyze(symbol)
        print(result.format_report())
        sys.exit(0)
    
    if args.hold_or_sell:
        from intelligence.position_advisor import PositionAdvisor
        
        symbol = args.hold_or_sell.upper()
        
        # Validate required buy_price
        if args.buy_price is None:
            print("\n❌ ERROR: --buy-price is required for --hold-or-sell analysis")
            print("   Usage: python paper_trader.py --hold-or-sell NABIL --buy-price 500")
            print("   Optional: --buy-date 2025-12-01")
            sys.exit(1)
        
        buy_price = args.buy_price
        buy_date = args.buy_date
        
        print(f"\n📊 Analyzing your position in {symbol}...")
        if buy_date:
            print(f"   Bought at Rs. {buy_price:.2f} on {buy_date}")
        else:
            print(f"   Bought at Rs. {buy_price:.2f}")
        print()
        
        advisor = PositionAdvisor()
        result = advisor.analyze(symbol, buy_price=buy_price, buy_date=buy_date)
        print(result.format_report())
        sys.exit(0)
    
    trader = PaperTrader()
    
    # ========== PRODUCTION HEARTBEAT ==========
    start_time = datetime.now()
    logger.info("=" * 70)
    logger.info(f"⚙️ NEPSE AI Trading Bot - {args.action.upper()} Initiated at {start_time.strftime('%H:%M:%S')}")
    logger.info("=" * 70)
    
    try:
        if args.action == "scan":
            strategy = args.strategy
            target_sector = args.sector
            max_price = args.max_price
            
            result = trader.run_daily_scan(
                quick_mode=args.quick,
                with_news=args.with_news or args.full,
                with_ai=args.with_ai or args.full,
                headless=not args.visible,
                strategy=strategy,
                target_sector=target_sector,
                max_price=max_price,
            )
            print(json.dumps(result, indent=2))
            
            # Show reminder to confirm purchases
            print("\n" + "=" * 70)
            print("💡 NEXT STEP: Confirm your purchases!")
            print("   python tools/paper_trader.py --action=buy --symbol=XXX --price=YYY")
            print("   Alias flow: python tools/paper_trader.py --scan --strategy=momentum")
            print("=" * 70)
        
        elif args.action == "buy":
            if not args.symbol:
                print("❌ ERROR: --symbol is required for buy action")
                print("   Example: --action=buy --symbol=NICA --price=368.50")
                sys.exit(1)
            result = trader.confirm_buy(args.symbol, args.price)
            print(json.dumps(result, indent=2))
        
        elif args.action == "skip":
            if not args.symbol:
                print("❌ ERROR: --symbol is required for skip action")
                print("   Example: --action=skip --symbol=NICA")
                sys.exit(1)
            result = trader.skip_stock(args.symbol)
            print(json.dumps(result, indent=2))
        
        elif args.action == "pending":
            result = trader.list_recommendations()
            # Output already printed by the method
        
        elif args.action == "analyze":
            # Deep analysis of a single stock (friend's recommendation)
            stock_symbol = args.stock or args.symbol
            if not stock_symbol:
                print("❌ ERROR: --stock or --symbol is required for analyze action")
                print("   Example: --action=analyze --stock=NHPC")
                sys.exit(1)
            
            # Parse historical date if provided
            historical_date = None
            if args.date:
                try:
                    # datetime already imported at top of file
                    historical_date = datetime.strptime(args.date, "%Y-%m-%d").date()
                    print(f"📅 HISTORICAL ANALYSIS MODE: Analyzing as if today was {args.date}")
                except ValueError:
                    print(f"❌ Invalid date format: {args.date}. Use YYYY-MM-DD")
                    sys.exit(1)
            
            result = trader.analyze_single_stock(
                symbol=stock_symbol.upper(),
                with_news=args.with_news or args.full,
                with_ai=args.with_ai or args.full,
                headless=not args.visible,
                historical_date=historical_date,
            )
            # Output already printed by the method
        
        elif args.action == "stealth-scan":
            # Stealth Radar: Detect smart money sector rotation
            target_sector = args.sector
            max_price = args.max_price
            
            result = trader.run_stealth_scan(
                target_sector=target_sector,
                max_price=max_price,
            )
            # Output already printed by the method
        
        elif args.action == "update":
            result = trader.update_positions()
            print(json.dumps(result, indent=2))
            
            # ========== DATABASE PRUNING ==========
            # Auto-clean closed trades older than 90 days
            try:
                conn = sqlite3.connect(trader.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM paper_trades 
                    WHERE status IN ('TARGET_HIT', 'STOPPED_OUT', 'EXPIRED', 'SKIPPED')
                    AND exit_date < date('now', '-90 days')
                """)
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info(f"🧹 Database pruning: Deleted {deleted} closed trades older than 90 days")
                conn.commit()
                conn.close()
            except Exception as e:
                logger.debug(f"Database pruning skipped: {e}")
        
        elif args.action == "status":
            status = trader.get_portfolio_status()
            print(json.dumps(status, indent=2, default=str))
        
        elif args.action == "report":
            report = trader.generate_report()
            print(report)
        
        # ========== SUCCESS HEARTBEAT ==========
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 70)
        logger.info(f"✅ {args.action.upper()} completed successfully in {elapsed:.1f}s")
        logger.info("=" * 70)
        
    except KeyboardInterrupt:
        logger.warning("⚠️ Operation cancelled by user (Ctrl+C)")
        sys.exit(1)
        
    except Exception as e:
        # ========== CRASH ALERT ==========
        import traceback
        error_trace = traceback.format_exc()
        
        logger.critical("=" * 70)
        logger.critical("🚨 CRITICAL: NEPSE AI Trading Bot CRASHED!")
        logger.critical(f"   Error: {str(e)}")
        logger.critical(f"   Action: {args.action}")
        logger.critical(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.critical("=" * 70)
        logger.error(f"Stack trace:\n{error_trace}")
        
        # Try to send crash notification (if Telegram configured)
        try:
            from core.config import settings
            if settings.telegram_bot_token and settings.telegram_chat_id:
                import requests
                crash_msg = f"""🚨 **NEPSE BOT CRASH ALERT**

Action: `{args.action}`
Error: `{str(e)[:100]}`
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Check server logs for full stack trace."""
                
                requests.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={
                        "chat_id": settings.telegram_chat_id,
                        "text": crash_msg,
                        "parse_mode": "Markdown"
                    },
                    timeout=10
                )
                logger.info("📱 Crash alert sent to Telegram")
        except Exception:
            pass  # Silently fail if Telegram not configured
        
        sys.exit(1)


if __name__ == "__main__":
    main()
