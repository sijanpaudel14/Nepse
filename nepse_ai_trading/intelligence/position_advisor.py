"""
📊 POSITION ADVISOR - Hold or Sell Analyzer

Helps existing stock holders decide whether to HOLD or SELL their position.

This is different from:
- IPO Exit Analyzer → For newly listed stocks (< 30 days)
- Signal Generator → For finding NEW entry opportunities

This tool answers: "I already own this stock. What should I do?"

USAGE:
    python paper_trader.py --hold-or-sell NABIL --buy-price 500
    python paper_trader.py --hold-or-sell NABIL --buy-price 500 --buy-date 2025-12-01

Author: NEPSE AI Trading Bot
Date: March 2026
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any
import pandas as pd
import numpy as np

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger


class HoldingPeriod(Enum):
    """Classification of holding duration."""
    VERY_SHORT = "very_short"    # < 1 week
    SHORT = "short"              # 1-2 weeks
    MEDIUM = "medium"            # 2 weeks - 3 months
    LONG = "long"                # 3-12 months
    VERY_LONG = "very_long"      # > 1 year


class Verdict(Enum):
    """Position recommendation."""
    STRONG_HOLD = "strong_hold"      # Excellent position, keep holding
    HOLD = "hold"                    # Good position, continue holding
    HOLD_CAUTIOUSLY = "hold_cautiously"  # Watch closely, tighten stop
    BOOK_PARTIAL = "book_partial"    # Take some profit
    AVERAGE_DOWN = "average_down"    # Consider adding (for believers)
    EXIT = "exit"                    # Cut the position
    URGENT_EXIT = "urgent_exit"      # Exit immediately


@dataclass
class SupportResistance:
    """Support and resistance levels."""
    immediate_support: float = 0.0
    strong_support: float = 0.0
    immediate_resistance: float = 0.0
    strong_resistance: float = 0.0
    entry_vs_support: str = ""  # "above", "below", "at"


@dataclass
class TechnicalHealth:
    """Technical health indicators."""
    trend: str = "UNKNOWN"          # BULLISH, BEARISH, SIDEWAYS
    trend_strength: int = 0         # 0-100
    rsi: float = 50.0
    rsi_signal: str = "NEUTRAL"     # OVERBOUGHT, OVERSOLD, NEUTRAL
    above_ema_9: bool = False
    above_ema_21: bool = False
    above_ema_50: bool = False
    above_ema_200: bool = False
    volume_trend: str = "NORMAL"    # ACCUMULATION, DISTRIBUTION, NORMAL
    

@dataclass
class RiskReward:
    """Risk/Reward analysis from current price."""
    risk_to_support: float = 0.0       # % drop to support
    reward_to_resistance: float = 0.0  # % gain to resistance
    risk_reward_ratio: float = 0.0     # Reward/Risk
    favorable: bool = False            # R:R > 1.5


@dataclass
class PositionAnalysis:
    """Complete position analysis result."""
    # Basic Info
    symbol: str = ""
    buy_price: float = 0.0
    buy_date: Optional[str] = None
    current_price: float = 0.0
    analysis_date: str = ""
    
    # P/L Info
    pnl_amount: float = 0.0
    pnl_percent: float = 0.0
    is_profitable: bool = False
    
    # Holding Period
    holding_days: int = 0
    trading_days_held: int = 0
    holding_period: HoldingPeriod = HoldingPeriod.MEDIUM
    
    # Technical Analysis
    technical: TechnicalHealth = field(default_factory=TechnicalHealth)
    support_resistance: SupportResistance = field(default_factory=SupportResistance)
    risk_reward: RiskReward = field(default_factory=RiskReward)
    
    # Health Score
    health_score: int = 50  # 0-100
    health_grade: str = "C"  # A, B, C, D, F
    
    # Verdict
    verdict: Verdict = Verdict.HOLD
    verdict_emoji: str = "🟡"
    verdict_text: str = ""
    
    # Recommendations
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    recommended_action: str = ""
    exit_triggers: List[str] = field(default_factory=list)
    hold_checklist: List[str] = field(default_factory=list)
    
    # Warnings
    warnings: List[str] = field(default_factory=list)
    
    def format_report(self) -> str:
        """Format analysis as beautiful console report."""
        lines = []
        w = 70  # Width
        
        # Header
        lines.append("=" * w)
        lines.append(f"📊 POSITION ANALYSIS: {self.symbol}")
        if self.buy_date:
            lines.append(f"   You bought at Rs. {self.buy_price:.2f} on {self.buy_date}")
        else:
            lines.append(f"   You bought at Rs. {self.buy_price:.2f}")
        if self.holding_days > 0:
            lines.append(f"   Holding for ~{self.holding_days} days ({self._holding_period_text()})")
        lines.append("=" * w)
        lines.append("")
        
        # P/L Section
        lines.append("💰 YOUR POSITION")
        lines.append("-" * 40)
        lines.append(f"   Buy Price:     Rs. {self.buy_price:.2f}")
        lines.append(f"   Current Price: Rs. {self.current_price:.2f}")
        
        pnl_sign = "+" if self.pnl_percent >= 0 else ""
        pnl_emoji = "📈" if self.is_profitable else "📉"
        lines.append(f"   P/L:           {pnl_sign}{self.pnl_percent:.1f}% (Rs. {pnl_sign}{self.pnl_amount:.2f}/share) {pnl_emoji}")
        
        # Example calculation
        example_qty = 100
        example_invested = self.buy_price * example_qty
        example_current = self.current_price * example_qty
        example_pnl = example_current - example_invested
        pnl_sign2 = "+" if example_pnl >= 0 else ""
        lines.append(f"")
        lines.append(f"   If {example_qty} shares: Rs. {example_invested:,.0f} → Rs. {example_current:,.0f} ({pnl_sign2}Rs. {example_pnl:,.0f})")
        lines.append("")
        
        # Technical Position
        lines.append("📈 TECHNICAL POSITION")
        lines.append("-" * 40)
        
        trend_emoji = "🟢" if self.technical.trend == "BULLISH" else "🔴" if self.technical.trend == "BEARISH" else "🟡"
        lines.append(f"   Trend:         {trend_emoji} {self.technical.trend} (strength: {self.technical.trend_strength}%)")
        
        rsi_emoji = "🔥" if self.technical.rsi_signal == "OVERBOUGHT" else "❄️" if self.technical.rsi_signal == "OVERSOLD" else "➖"
        lines.append(f"   Momentum:      RSI {self.technical.rsi:.0f} - {self.technical.rsi_signal} {rsi_emoji}")
        
        # EMA alignment
        ema_count = sum([self.technical.above_ema_9, self.technical.above_ema_21, 
                        self.technical.above_ema_50, self.technical.above_ema_200])
        ema_text = f"Above {ema_count}/4 EMAs"
        if ema_count == 4:
            ema_text += " ✅ (Perfect alignment)"
        elif ema_count >= 2:
            ema_text += " (Moderate)"
        else:
            ema_text += " ⚠️ (Weak)"
        lines.append(f"   EMA Position:  {ema_text}")
        
        vol_emoji = "🔵" if self.technical.volume_trend == "ACCUMULATION" else "🔴" if self.technical.volume_trend == "DISTRIBUTION" else "⚪"
        lines.append(f"   Volume:        {vol_emoji} {self.technical.volume_trend}")
        lines.append("")
        
        # Support/Resistance
        lines.append("🛡️ SUPPORT & RESISTANCE")
        lines.append("-" * 40)
        
        support_dist = ((self.current_price - self.support_resistance.immediate_support) / 
                       self.current_price * 100) if self.support_resistance.immediate_support > 0 else 0
        resist_dist = ((self.support_resistance.immediate_resistance - self.current_price) / 
                      self.current_price * 100) if self.support_resistance.immediate_resistance > 0 else 0
        
        lines.append(f"   Nearest Support:     Rs. {self.support_resistance.immediate_support:.2f} ({support_dist:.1f}% below)")
        lines.append(f"   Nearest Resistance:  Rs. {self.support_resistance.immediate_resistance:.2f} ({resist_dist:.1f}% above)")
        lines.append(f"   Strong Support:      Rs. {self.support_resistance.strong_support:.2f}")
        
        # Entry vs Support analysis
        if self.support_resistance.entry_vs_support == "below":
            lines.append(f"")
            lines.append(f"   ✅ YOUR ENTRY ADVANTAGE:")
            lines.append(f"   └── Your entry (Rs. {self.buy_price:.2f}) is BELOW support (Rs. {self.support_resistance.immediate_support:.2f})")
            lines.append(f"   └── Even if price drops, your entry is protected!")
        elif self.support_resistance.entry_vs_support == "above":
            lines.append(f"")
            lines.append(f"   ⚠️ ENTRY RISK:")
            lines.append(f"   └── Your entry (Rs. {self.buy_price:.2f}) is ABOVE support (Rs. {self.support_resistance.immediate_support:.2f})")
            lines.append(f"   └── Price has room to drop before hitting support")
        lines.append("")
        
        # Risk/Reward
        lines.append("⚖️ RISK/REWARD FROM CURRENT PRICE")
        lines.append("-" * 40)
        lines.append(f"   If drops to support:    -{self.risk_reward.risk_to_support:.1f}%")
        lines.append(f"   If hits resistance:     +{self.risk_reward.reward_to_resistance:.1f}%")
        
        rr_emoji = "✅" if self.risk_reward.favorable else "⚠️"
        lines.append(f"   Risk/Reward Ratio:      1:{self.risk_reward.risk_reward_ratio:.1f} {rr_emoji}")
        
        if self.risk_reward.favorable:
            lines.append(f"   → Favorable R:R - more upside than downside")
        else:
            lines.append(f"   → Unfavorable R:R - consider tighter stop")
        lines.append("")
        
        # Health Score
        lines.append("📊 POSITION HEALTH SCORE")
        lines.append("-" * 40)
        
        # Visual score bar
        filled = int(self.health_score / 5)
        empty = 20 - filled
        score_bar = "█" * filled + "░" * empty
        
        grade_color = {"A": "🟢", "B": "🟢", "C": "🟡", "D": "🟠", "F": "🔴"}.get(self.health_grade, "⚪")
        lines.append(f"   Score: {self.health_score}/100 [{score_bar}] Grade: {grade_color} {self.health_grade}")
        lines.append("")
        
        # Main Verdict
        lines.append("=" * w)
        lines.append(f"{self.verdict_emoji} VERDICT: {self.verdict_text}")
        lines.append("=" * w)
        lines.append("")
        
        # Recommended Actions
        lines.append("💡 RECOMMENDED ACTIONS:")
        for i, action in enumerate(self.recommended_action.split('\n'), 1):
            if action.strip():
                lines.append(f"   {i}. {action.strip()}")
        lines.append("")
        
        # Stop Loss & Targets
        lines.append("🎯 YOUR TRADE PLAN:")
        lines.append(f"   🛑 STOP LOSS:  Rs. {self.stop_loss:.2f} ({((self.stop_loss - self.current_price) / self.current_price * 100):.1f}% from current)")
        lines.append(f"   🎯 TARGET 1:   Rs. {self.target_1:.2f} ({((self.target_1 - self.current_price) / self.current_price * 100):+.1f}%)")
        if self.target_2 > self.target_1:
            lines.append(f"   🎯 TARGET 2:   Rs. {self.target_2:.2f} ({((self.target_2 - self.current_price) / self.current_price * 100):+.1f}%)")
        lines.append("")
        
        # Exit Triggers
        if self.exit_triggers:
            lines.append("🚨 EXIT IMMEDIATELY IF:")
            for trigger in self.exit_triggers:
                lines.append(f"   • {trigger}")
            lines.append("")
        
        # Hold Checklist
        if self.hold_checklist:
            lines.append("📋 WEEKLY CHECK-IN (Continue Holding If):")
            for check in self.hold_checklist:
                lines.append(f"   ✓ {check}")
            lines.append("")
        
        # Warnings
        if self.warnings:
            lines.append("⚠️ WARNINGS:")
            for warning in self.warnings:
                lines.append(f"   ⚠️ {warning}")
            lines.append("")
        
        lines.append("=" * w)
        lines.append("💡 Run this analysis weekly to monitor your position.")
        lines.append("=" * w)
        
        return "\n".join(lines)
    
    def _holding_period_text(self) -> str:
        """Get human-readable holding period."""
        mapping = {
            HoldingPeriod.VERY_SHORT: "less than 1 week",
            HoldingPeriod.SHORT: "1-2 weeks",
            HoldingPeriod.MEDIUM: "2 weeks - 3 months",
            HoldingPeriod.LONG: "3-12 months",
            HoldingPeriod.VERY_LONG: "over 1 year"
        }
        return mapping.get(self.holding_period, "unknown duration")
    
    def quick_verdict(self) -> str:
        """Return one-line verdict."""
        pnl_sign = "+" if self.pnl_percent >= 0 else ""
        return f"{self.verdict_emoji} {self.verdict_text} | P/L: {pnl_sign}{self.pnl_percent:.1f}% | Stop: Rs. {self.stop_loss:.2f}"


class PositionAdvisor:
    """
    Analyzes existing positions and recommends HOLD or SELL.
    
    Usage:
        advisor = PositionAdvisor()
        result = advisor.analyze("NABIL", buy_price=500, buy_date="2025-12-01")
        print(result.format_report())
    """
    
    def __init__(self, fetcher=None, sharehub=None):
        """Initialize with optional data sources."""
        self.fetcher = fetcher
        self.sharehub = sharehub
        
        # Lazy load if not provided
        if self.fetcher is None:
            try:
                from data.fetcher import NepseFetcher
                self.fetcher = NepseFetcher()
            except Exception as e:
                logger.warning(f"Could not initialize NepseFetcher: {e}")
        
        if self.sharehub is None:
            try:
                from data.sharehub_api import ShareHubAPI
                token = os.getenv("SHAREHUB_AUTH_TOKEN")
                if token:
                    self.sharehub = ShareHubAPI(auth_token=token)
            except Exception as e:
                logger.debug(f"Could not initialize ShareHubAPI: {e}")
    
    def analyze(
        self,
        symbol: str,
        buy_price: float,
        buy_date: Optional[str] = None,
        current_price: Optional[float] = None
    ) -> PositionAnalysis:
        """
        Analyze a position and recommend HOLD or SELL.
        
        Args:
            symbol: Stock symbol (e.g., "NABIL")
            buy_price: Your purchase price
            buy_date: Optional purchase date (YYYY-MM-DD)
            current_price: Optional current price (fetched if not provided)
            
        Returns:
            PositionAnalysis with complete recommendation
        """
        symbol = symbol.upper()
        logger.info(f"📊 Analyzing position: {symbol} bought at Rs. {buy_price}")
        
        result = PositionAnalysis(
            symbol=symbol,
            buy_price=buy_price,
            buy_date=buy_date,
            analysis_date=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        
        # Fetch price data
        df = self._fetch_price_data(symbol)
        if df is None or df.empty:
            result.warnings.append("Could not fetch price data")
            result.verdict = Verdict.HOLD_CAUTIOUSLY
            result.verdict_emoji = "⚠️"
            result.verdict_text = "INSUFFICIENT DATA - Hold and monitor manually"
            return result
        
        # Get current price - prefer real-time LTP over historical close
        if current_price:
            result.current_price = current_price
        else:
            # Try to get real-time LTP first
            realtime_ltp = self._fetch_realtime_ltp(symbol)
            if realtime_ltp and realtime_ltp > 0:
                result.current_price = realtime_ltp
                logger.info(f"📊 Using real-time LTP: Rs. {realtime_ltp}")
            else:
                # Fallback to last close from historical data
                result.current_price = float(df['close'].iloc[-1])
                result.warnings.append("Using yesterday's close (market may be closed)")
        
        # Calculate P/L
        result.pnl_amount = result.current_price - result.buy_price
        result.pnl_percent = (result.pnl_amount / result.buy_price) * 100
        result.is_profitable = result.pnl_percent > 0
        
        # Calculate holding period
        result.holding_days, result.trading_days_held, result.holding_period = \
            self._calculate_holding_period(buy_date)
        
        # Technical analysis
        result.technical = self._analyze_technical(df)
        
        # Support/Resistance
        result.support_resistance = self._find_support_resistance(df, buy_price)
        
        # Risk/Reward
        result.risk_reward = self._calculate_risk_reward(
            result.current_price,
            result.support_resistance.immediate_support,
            result.support_resistance.immediate_resistance
        )
        
        # Health Score
        result.health_score, result.health_grade = self._calculate_health_score(result)
        
        # Generate verdict and recommendations
        self._generate_verdict(result)
        
        logger.info(f"📊 {symbol}: {result.verdict_text} | Health: {result.health_score}/100")
        
        return result
    
    def _fetch_price_data(self, symbol: str, days: int = 365) -> Optional[pd.DataFrame]:
        """Fetch historical price data."""
        try:
            if self.fetcher:
                df = self.fetcher.fetch_price_history(symbol, days=days)
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"Fetcher failed: {e}")
        
        # Try ShareHub as fallback
        try:
            if self.sharehub:
                from data.sharehub_api import get_price_history_with_open
                df = get_price_history_with_open(symbol, days=days)
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"ShareHub failed: {e}")
        
        return None
    
    def _fetch_realtime_ltp(self, symbol: str) -> Optional[float]:
        """Fetch real-time Last Traded Price (LTP) for today."""
        # Method 1: Try NepseFetcher's live market data (most reliable)
        try:
            if self.fetcher:
                live_df = self.fetcher.fetch_live_market()
                if live_df is not None and not live_df.empty:
                    symbol_upper = symbol.upper()
                    match = live_df[live_df['symbol'].str.upper() == symbol_upper]
                    if not match.empty:
                        # 'close' in live market is actually the LTP
                        ltp = match.iloc[0].get('close') or match.iloc[0].get('ltp')
                        if ltp and float(ltp) > 0:
                            return float(ltp)
        except Exception as e:
            logger.debug(f"Live market failed: {e}")
        
        # Method 2: Try ShareHub real-time quote
        try:
            if self.sharehub:
                quote = self.sharehub.get_stock_quote(symbol)
                if quote and hasattr(quote, 'ltp') and quote.ltp > 0:
                    return float(quote.ltp)
        except Exception as e:
            logger.debug(f"ShareHub quote failed: {e}")
        
        return None
    
    def _calculate_holding_period(
        self, 
        buy_date: Optional[str]
    ) -> Tuple[int, int, HoldingPeriod]:
        """Calculate holding duration and classify it."""
        if not buy_date:
            return 0, 0, HoldingPeriod.MEDIUM  # Default to medium if unknown
        
        try:
            buy_dt = datetime.strptime(buy_date, "%Y-%m-%d")
        except ValueError:
            return 0, 0, HoldingPeriod.MEDIUM
        
        today = datetime.now()
        calendar_days = (today - buy_dt).days
        
        # Count trading days (NEPSE: Sun-Thu, closed Fri-Sat)
        trading_days = 0
        current = buy_dt
        while current < today:
            if current.weekday() not in (4, 5):  # Not Friday, Saturday
                trading_days += 1
            current += timedelta(days=1)
        
        # Classify
        if calendar_days < 7:
            period = HoldingPeriod.VERY_SHORT
        elif calendar_days < 14:
            period = HoldingPeriod.SHORT
        elif calendar_days < 90:
            period = HoldingPeriod.MEDIUM
        elif calendar_days < 365:
            period = HoldingPeriod.LONG
        else:
            period = HoldingPeriod.VERY_LONG
        
        return calendar_days, trading_days, period
    
    def _analyze_technical(self, df: pd.DataFrame) -> TechnicalHealth:
        """Analyze technical indicators."""
        health = TechnicalHealth()
        
        if len(df) < 10:
            return health
        
        close = df['close'].values
        current_price = close[-1]
        
        # Calculate EMAs
        def ema(data, period):
            if len(data) < period:
                return None
            return pd.Series(data).ewm(span=period, adjust=False).mean().iloc[-1]
        
        ema_9 = ema(close, 9)
        ema_21 = ema(close, 21)
        ema_50 = ema(close, 50) if len(close) >= 50 else None
        ema_200 = ema(close, 200) if len(close) >= 200 else None
        
        # Above EMAs
        health.above_ema_9 = current_price > ema_9 if ema_9 else False
        health.above_ema_21 = current_price > ema_21 if ema_21 else False
        health.above_ema_50 = current_price > ema_50 if ema_50 else True  # True if not enough data
        health.above_ema_200 = current_price > ema_200 if ema_200 else True
        
        # Trend determination
        ema_alignment = sum([health.above_ema_9, health.above_ema_21, 
                           health.above_ema_50, health.above_ema_200])
        
        if ema_alignment >= 3:
            health.trend = "BULLISH"
            health.trend_strength = 60 + (ema_alignment - 3) * 20
        elif ema_alignment <= 1:
            health.trend = "BEARISH"
            health.trend_strength = 20 + ema_alignment * 20
        else:
            health.trend = "SIDEWAYS"
            health.trend_strength = 40 + (ema_alignment - 2) * 10
        
        # EMA slope for trend strength
        if ema_21 and len(close) > 5:
            ema_21_5d_ago = ema(close[:-5], 21)
            if ema_21_5d_ago:
                ema_slope = (ema_21 - ema_21_5d_ago) / ema_21_5d_ago * 100
                if ema_slope > 1:
                    health.trend_strength = min(100, health.trend_strength + 15)
                elif ema_slope < -1:
                    health.trend_strength = max(0, health.trend_strength - 15)
        
        # RSI
        if len(close) >= 14:
            delta = pd.Series(close).diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            
            rs = gain.iloc[-1] / max(loss.iloc[-1], 0.001)
            health.rsi = 100 - (100 / (1 + rs))
            
            if health.rsi > 70:
                health.rsi_signal = "OVERBOUGHT"
            elif health.rsi < 30:
                health.rsi_signal = "OVERSOLD"
            else:
                health.rsi_signal = "NEUTRAL"
        
        # Volume trend
        if 'volume' in df.columns and len(df) >= 20:
            recent_vol = df['volume'].iloc[-5:].mean()
            avg_vol = df['volume'].iloc[-20:].mean()
            
            # Check if volume is increasing on up days vs down days
            # Need 'open' column for this analysis
            if 'open' in df.columns:
                last_5 = df.iloc[-5:].copy()
                # Handle None/NaN values
                last_5 = last_5.dropna(subset=['close', 'open'])
                
                if len(last_5) >= 3:
                    up_days = last_5[last_5['close'] > last_5['open']]
                    down_days = last_5[last_5['close'] < last_5['open']]
                    
                    up_vol = up_days['volume'].mean() if len(up_days) > 0 else 0
                    down_vol = down_days['volume'].mean() if len(down_days) > 0 else 0
                    
                    if up_vol > down_vol * 1.3:
                        health.volume_trend = "ACCUMULATION"
                    elif down_vol > up_vol * 1.3:
                        health.volume_trend = "DISTRIBUTION"
                    else:
                        health.volume_trend = "NORMAL"
                else:
                    # Use simple volume trend
                    if recent_vol > avg_vol * 1.5:
                        health.volume_trend = "ACCUMULATION"
                    elif recent_vol < avg_vol * 0.5:
                        health.volume_trend = "DISTRIBUTION"
                    else:
                        health.volume_trend = "NORMAL"
            else:
                # Fallback: just use volume magnitude
                if recent_vol > avg_vol * 1.5:
                    health.volume_trend = "ACCUMULATION"
                elif recent_vol < avg_vol * 0.5:
                    health.volume_trend = "DISTRIBUTION"
                else:
                    health.volume_trend = "NORMAL"
        
        return health
    
    def _find_support_resistance(
        self, 
        df: pd.DataFrame, 
        buy_price: float
    ) -> SupportResistance:
        """Find support and resistance levels."""
        sr = SupportResistance()
        
        close = df['close'].values
        high = df['high'].values if 'high' in df.columns else close
        low = df['low'].values if 'low' in df.columns else close
        current_price = close[-1]
        
        # Handle short data (IPOs)
        if len(df) < 10:
            # Use simple calculations for IPOs
            sr.immediate_support = min(low) * 0.95
            sr.strong_support = min(low) * 0.90
            sr.immediate_resistance = max(high) * 1.05
            sr.strong_resistance = max(high) * 1.10
            
            if buy_price < sr.immediate_support * 0.98:
                sr.entry_vs_support = "below"
            elif buy_price > sr.immediate_support * 1.02:
                sr.entry_vs_support = "above"
            else:
                sr.entry_vs_support = "at"
            return sr
        
        if len(df) < 20:
            # Use available data
            sr.immediate_support = min(low[-len(df):]) * 0.98
            sr.strong_support = min(low) * 0.95
            sr.immediate_resistance = max(high[-len(df):]) * 1.02
            sr.strong_resistance = max(high) * 1.05
            
            if buy_price < sr.immediate_support * 0.98:
                sr.entry_vs_support = "below"
            elif buy_price > sr.immediate_support * 1.02:
                sr.entry_vs_support = "above"
            else:
                sr.entry_vs_support = "at"
            return sr
        
        # Find recent swing lows (supports)
        current_price = close[-1]
        supports = []
        for i in range(5, len(low) - 5):
            if low[i] == min(low[i-5:i+6]):
                supports.append(low[i])
        
        # Find recent swing highs (resistances)
        resistances = []
        for i in range(5, len(high) - 5):
            if high[i] == max(high[i-5:i+6]):
                resistances.append(high[i])
        
        # Add EMA levels as dynamic S/R
        if len(close) >= 50:
            ema_50 = pd.Series(close).ewm(span=50, adjust=False).mean().iloc[-1]
            if ema_50 < current_price:
                supports.append(ema_50)
            else:
                resistances.append(ema_50)
        
        # Find immediate support (closest below current price)
        valid_supports = [s for s in supports if s < current_price * 0.99]
        if valid_supports:
            sr.immediate_support = max(valid_supports)
            sr.strong_support = min(valid_supports) if len(valid_supports) > 1 else sr.immediate_support
        else:
            # Use recent low as support
            sr.immediate_support = min(low[-20:]) * 0.98
            sr.strong_support = min(low) * 0.95
        
        # Find immediate resistance (closest above current price)
        valid_resistances = [r for r in resistances if r > current_price * 1.01]
        if valid_resistances:
            sr.immediate_resistance = min(valid_resistances)
            sr.strong_resistance = max(valid_resistances) if len(valid_resistances) > 1 else sr.immediate_resistance
        else:
            # Use recent high as resistance
            sr.immediate_resistance = max(high[-20:]) * 1.02
            sr.strong_resistance = max(high) * 1.05
        
        # Compare entry to support
        if buy_price < sr.immediate_support * 0.98:
            sr.entry_vs_support = "below"  # Good - entry protected
        elif buy_price > sr.immediate_support * 1.02:
            sr.entry_vs_support = "above"  # Risk - can drop below entry
        else:
            sr.entry_vs_support = "at"
        
        return sr
    
    def _calculate_risk_reward(
        self,
        current_price: float,
        support: float,
        resistance: float
    ) -> RiskReward:
        """Calculate risk/reward from current price."""
        rr = RiskReward()
        
        if support <= 0 or resistance <= 0:
            return rr
        
        # Risk = drop to support
        rr.risk_to_support = ((current_price - support) / current_price) * 100
        
        # Reward = gain to resistance
        rr.reward_to_resistance = ((resistance - current_price) / current_price) * 100
        
        # R:R ratio
        if rr.risk_to_support > 0:
            rr.risk_reward_ratio = rr.reward_to_resistance / rr.risk_to_support
        else:
            rr.risk_reward_ratio = float('inf')
        
        # Favorable if R:R > 1.5
        rr.favorable = rr.risk_reward_ratio >= 1.5
        
        return rr
    
    def _calculate_health_score(self, result: PositionAnalysis) -> Tuple[int, str]:
        """
        Calculate overall position health score (0-100).
        
        Factors:
        - Trend Alignment: 25%
        - Momentum (RSI): 20%
        - Support Proximity: 20%
        - Volume Health: 15%
        - Profit Buffer: 10%
        - Risk/Reward: 10%
        """
        score = 0
        
        # 1. Trend Alignment (25 pts)
        trend_pts = 0
        if result.technical.trend == "BULLISH":
            trend_pts = 20 + (result.technical.trend_strength - 60) * 0.1
        elif result.technical.trend == "SIDEWAYS":
            trend_pts = 12
        else:  # BEARISH
            trend_pts = 5
        
        ema_count = sum([result.technical.above_ema_9, result.technical.above_ema_21,
                        result.technical.above_ema_50, result.technical.above_ema_200])
        trend_pts += ema_count * 1.25  # Up to 5 more points
        
        score += min(25, max(0, trend_pts))
        
        # 2. Momentum (20 pts)
        rsi = result.technical.rsi
        if 45 <= rsi <= 65:
            momentum_pts = 20  # Sweet spot
        elif 35 <= rsi < 45 or 65 < rsi <= 75:
            momentum_pts = 15
        elif 25 <= rsi < 35:
            momentum_pts = 12  # Oversold - potential bounce
        elif 75 < rsi <= 80:
            momentum_pts = 8   # Overbought - caution
        elif rsi > 80:
            momentum_pts = 5   # Very overbought
        else:  # < 25
            momentum_pts = 8   # Deep oversold
        
        score += momentum_pts
        
        # 3. Support Proximity (20 pts)
        support_dist = result.risk_reward.risk_to_support
        if support_dist < 3:
            support_pts = 20  # Very close to support - risky
        elif support_dist < 5:
            support_pts = 18
        elif support_dist < 8:
            support_pts = 15
        elif support_dist < 12:
            support_pts = 12
        else:
            support_pts = 8   # Far from support - less protection
        
        # Bonus if entry is below support
        if result.support_resistance.entry_vs_support == "below":
            support_pts = min(20, support_pts + 5)
        
        score += support_pts
        
        # 4. Volume Health (15 pts)
        if result.technical.volume_trend == "ACCUMULATION":
            volume_pts = 15
        elif result.technical.volume_trend == "NORMAL":
            volume_pts = 10
        else:  # DISTRIBUTION
            volume_pts = 3
        
        score += volume_pts
        
        # 5. Profit Buffer (10 pts)
        pnl = result.pnl_percent
        if pnl >= 20:
            profit_pts = 10  # Great cushion
        elif pnl >= 10:
            profit_pts = 8
        elif pnl >= 5:
            profit_pts = 6
        elif pnl >= 0:
            profit_pts = 4   # Breakeven
        elif pnl >= -5:
            profit_pts = 2   # Small loss
        else:
            profit_pts = 0   # Significant loss
        
        score += profit_pts
        
        # 6. Risk/Reward (10 pts)
        rr = result.risk_reward.risk_reward_ratio
        if rr >= 2.5:
            rr_pts = 10
        elif rr >= 2.0:
            rr_pts = 8
        elif rr >= 1.5:
            rr_pts = 6
        elif rr >= 1.0:
            rr_pts = 4
        else:
            rr_pts = 2
        
        score += rr_pts
        
        # Clamp to 0-100
        score = max(0, min(100, int(score)))
        
        # Grade
        if score >= 80:
            grade = "A"
        elif score >= 65:
            grade = "B"
        elif score >= 50:
            grade = "C"
        elif score >= 35:
            grade = "D"
        else:
            grade = "F"
        
        return score, grade
    
    def _generate_verdict(self, result: PositionAnalysis) -> None:
        """Generate verdict and recommendations based on analysis."""
        
        score = result.health_score
        pnl = result.pnl_percent
        trend = result.technical.trend
        rsi = result.technical.rsi
        volume = result.technical.volume_trend
        holding = result.holding_period
        rr = result.risk_reward.risk_reward_ratio
        
        # Initialize recommendations
        actions = []
        exit_triggers = []
        hold_checklist = []
        warnings = []
        
        # ==== VERDICT LOGIC ====
        
        # URGENT EXIT conditions
        if (score < 25 and pnl < -10) or (trend == "BEARISH" and volume == "DISTRIBUTION" and pnl < 0):
            result.verdict = Verdict.URGENT_EXIT
            result.verdict_emoji = "🚨"
            result.verdict_text = "URGENT EXIT - Position deteriorating"
            actions.append("Exit the entire position immediately")
            actions.append("Do not wait for a bounce - cut your losses")
            actions.append(f"Current loss: {pnl:.1f}% - prevent further damage")
        
        # EXIT conditions
        elif score < 35 or (trend == "BEARISH" and pnl < -5):
            result.verdict = Verdict.EXIT
            result.verdict_emoji = "🔴"
            result.verdict_text = "EXIT - Trend broken, cut position"
            actions.append("Sell your entire position")
            actions.append("Look for re-entry when conditions improve")
            if pnl < 0:
                actions.append(f"Accepting {pnl:.1f}% loss now prevents bigger loss later")
            
        # BOOK PARTIAL conditions
        elif (score >= 35 and score < 50 and pnl > 10) or (rsi > 75 and pnl > 15):
            result.verdict = Verdict.BOOK_PARTIAL
            result.verdict_emoji = "🟠"
            result.verdict_text = "BOOK PARTIAL PROFIT - Secure gains"
            actions.append("Sell 50% of your position now")
            actions.append("Keep remaining 50% with tight stop")
            actions.append(f"You've gained {pnl:.1f}% - secure some of it")
            warnings.append("RSI is overbought - pullback likely" if rsi > 70 else "")
        
        # HOLD CAUTIOUSLY
        elif score >= 35 and score < 55:
            result.verdict = Verdict.HOLD_CAUTIOUSLY
            result.verdict_emoji = "🟡"
            result.verdict_text = "HOLD CAUTIOUSLY - Watch closely"
            actions.append("Set a tight stop loss and monitor daily")
            actions.append("Be ready to exit if conditions worsen")
            if pnl < 0:
                actions.append(f"Current P/L: {pnl:.1f}% - give it time but protect capital")
            hold_checklist.append("Price stays above immediate support")
            hold_checklist.append("No distribution (heavy selling) detected")
        
        # AVERAGE DOWN (for medium/long term holders in loss with good setup)
        elif score >= 45 and pnl < -5 and pnl > -15 and trend != "BEARISH" and holding in [HoldingPeriod.MEDIUM, HoldingPeriod.LONG]:
            result.verdict = Verdict.AVERAGE_DOWN
            result.verdict_emoji = "🔵"
            result.verdict_text = "CONSIDER AVERAGING DOWN"
            actions.append("If you believe in the stock, this could be a good level to add")
            actions.append(f"Current price is {abs(pnl):.1f}% below your entry")
            actions.append("Only add if you can hold for 3+ months")
            warnings.append("Only average down if you have conviction in the company")
            warnings.append("Never average down in a confirmed downtrend")
        
        # HOLD
        elif score >= 55 and score < 75:
            result.verdict = Verdict.HOLD
            result.verdict_emoji = "🟢"
            result.verdict_text = "HOLD - Position is healthy"
            actions.append("Continue holding with trailing stop")
            if pnl > 10:
                actions.append(f"Great job! You're up {pnl:.1f}%")
                actions.append("Trail your stop to lock in profits")
            else:
                actions.append("Position is building - be patient")
            hold_checklist.append("Price remains above 21 EMA")
            hold_checklist.append("RSI stays above 40")
            hold_checklist.append("Volume stays healthy (no distribution)")
        
        # STRONG HOLD
        else:  # score >= 75
            result.verdict = Verdict.STRONG_HOLD
            result.verdict_emoji = "💪"
            result.verdict_text = "STRONG HOLD - Excellent position!"
            actions.append("This is a strong position - let your winners run!")
            if pnl > 20:
                actions.append(f"Excellent! You're up {pnl:.1f}%")
            actions.append("Trail stop to protect gains but give room to grow")
            hold_checklist.append("Trend remains bullish")
            hold_checklist.append("No major resistance until target")
        
        # ==== STOP LOSS CALCULATION ====
        # NOTE: NEPSE has frequent "shakeouts" where operators push price 2-3% below
        # support to trigger retail panic before pumping back. Use 5% buffer minimum.
        
        # Stop loss logic based on holding period and P/L
        if holding in [HoldingPeriod.VERY_SHORT, HoldingPeriod.SHORT]:
            # Short term: moderate stops (NEPSE needs wider buffer for shakeouts)
            if pnl > 5:
                # In profit: stop just below entry
                result.stop_loss = result.buy_price * 0.97  # 3% below entry
            else:
                # Flat or loss: stop 5% below immediate support (survive shakeouts)
                result.stop_loss = min(result.support_resistance.immediate_support * 0.95,
                                      result.buy_price * 0.93)
        elif holding == HoldingPeriod.MEDIUM:
            # Medium term: moderate stops
            if pnl > 10:
                # Good profit: lock in some gains
                result.stop_loss = result.buy_price * 1.03  # 3% above entry
            elif pnl > 0:
                result.stop_loss = result.buy_price * 0.95  # 5% below entry
            else:
                # 5% below support for NEPSE shakeout protection
                result.stop_loss = result.support_resistance.immediate_support * 0.95
        else:
            # Long term: wider stops
            if pnl > 20:
                result.stop_loss = result.buy_price * 1.10  # Lock 10% profit
            elif pnl > 0:
                result.stop_loss = result.buy_price * 0.93  # 7% below entry
            else:
                # 5% below strong support for NEPSE
                result.stop_loss = result.support_resistance.strong_support * 0.95
        
        # ==== TARGETS ====
        
        result.target_1 = result.support_resistance.immediate_resistance
        result.target_2 = result.support_resistance.strong_resistance
        
        # ==== EXIT TRIGGERS ====
        # NOTE: In NEPSE bull runs (Hydropower, Microfinance), RSI can stay overbought
        # for weeks. Dropping from 75 to 49 is often just consolidation, not reversal.
        # Use RSI < 60 for overbought stocks to lock profits before real crash.
        
        exit_triggers.append(f"Price closes below Rs. {result.stop_loss:.2f}")
        if result.technical.rsi > 70:
            # Overbought: exit earlier at RSI 60 (NEPSE-specific)
            exit_triggers.append("RSI drops below 60 (momentum weakening)")
        else:
            exit_triggers.append("RSI drops below 40 (weak momentum)")
        exit_triggers.append("Heavy volume on a red day (distribution)")
        exit_triggers.append("Price closes below 50 EMA on daily chart")
        
        # ==== HOLDING PERIOD SPECIFIC ADVICE ====
        
        if holding == HoldingPeriod.VERY_SHORT:
            if pnl > 5:
                warnings.append(f"Quick {pnl:.1f}% gain in <1 week - consider booking")
            hold_checklist.append("Quick scalp - exit if momentum fades")
        
        elif holding == HoldingPeriod.SHORT:
            if pnl > 10:
                warnings.append(f"Strong {pnl:.1f}% gain in 1-2 weeks - trail tightly")
        
        elif holding == HoldingPeriod.LONG:
            if pnl > 30:
                warnings.append(f"Excellent {pnl:.1f}% gain - consider taking some off")
            hold_checklist.append("Long-term holder: focus on major support, not daily noise")
        
        elif holding == HoldingPeriod.VERY_LONG:
            hold_checklist.append("1+ year holder: you've weathered volatility, stay patient")
            if pnl > 50:
                warnings.append("Consider rebalancing - position may be oversized")
        
        # Filter empty strings
        result.recommended_action = "\n".join([a for a in actions if a])
        result.exit_triggers = [t for t in exit_triggers if t]
        result.hold_checklist = [c for c in hold_checklist if c]
        result.warnings = [w for w in warnings if w] + result.warnings
    
    def quick_check(self, symbol: str, buy_price: float, buy_date: Optional[str] = None) -> str:
        """Return one-line verdict."""
        result = self.analyze(symbol, buy_price, buy_date)
        return result.quick_verdict()


# ============================================================================
# MAIN - For testing
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Example usage
    if len(sys.argv) >= 3:
        symbol = sys.argv[1].upper()
        buy_price = float(sys.argv[2])
        buy_date = sys.argv[3] if len(sys.argv) > 3 else None
    else:
        # Demo with NABIL
        symbol = "NABIL"
        buy_price = 500.0
        buy_date = "2025-12-01"
    
    print(f"\n📊 Analyzing position: {symbol} @ Rs. {buy_price}")
    if buy_date:
        print(f"   Bought on: {buy_date}")
    print()
    
    advisor = PositionAdvisor()
    result = advisor.analyze(symbol, buy_price, buy_date)
    
    print(result.format_report())
