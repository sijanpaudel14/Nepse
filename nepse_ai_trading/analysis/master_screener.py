"""
🎯 MASTER STOCK SCREENER - The Millionaire Quantitative Engine

This is NOT an API wrapper. This is a proprietary 4-Pillar Scoring Algorithm
that mathematically evaluates every NEPSE stock and returns a 0-100 score.

SCORING ARCHITECTURE:
=====================
┌─────────────────────────────────────────────────────────────────┐
│                    TOTAL SCORE (0-100)                          │
├─────────────────────────────────────────────────────────────────┤
│  Pillar 1: Broker/Institutional (30%)  │  0-30 points          │
│  Pillar 2: Unlock Risk (20%)           │  0-20 points (or -50) │
│  Pillar 3: Fundamental Safety (20%)    │  0-20 points          │
│  Pillar 4: Technical & Momentum (30%)  │  0-30 points          │
└─────────────────────────────────────────────────────────────────┘

CRITICAL RULES:
===============
1. Stocks with unlock within 30 days → INSTANT REJECT (-50 penalty)
2. Stocks with Seller dominance >55% → Heavy penalty (-20)
3. Stocks with PE > 50 → Overvalued penalty
4. Only return stocks with score >= 60

Author: AI Quantitative Engine
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
from loguru import logger
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import asyncio

from data.fetcher import NepseFetcher
from data.sharehub_api import ShareHubAPI
from analysis.indicators import TechnicalIndicators, safe_vwap
from core.config import settings

# News Scraper & AI Advisor (optional - for enhanced analysis)
try:
    from intelligence.news_scraper import NewsScraper, scrape_news_for_stock, PLAYWRIGHT_AVAILABLE
    NEWS_AVAILABLE = PLAYWRIGHT_AVAILABLE
except ImportError:
    NEWS_AVAILABLE = False
    logger.info("📰 News scraper not available (Playwright not installed)")

try:
    from intelligence.ai_advisor import AIAdvisor, get_ai_verdict, OPENAI_AVAILABLE
    AI_AVAILABLE = OPENAI_AVAILABLE
except ImportError:
    AI_AVAILABLE = False
    logger.info("🤖 AI Advisor not available (OpenAI not installed)")

# Manipulation Detector (optional - for operator intelligence)
try:
    from intelligence.manipulation_detector import ManipulationDetector, ManipulationReport
    MANIPULATION_DETECTOR_AVAILABLE = True
except ImportError:
    MANIPULATION_DETECTOR_AVAILABLE = False
    logger.info("🚨 Manipulation detector not available")


@dataclass
class ScoringBreakdown:
    """Detailed breakdown of how a stock was scored."""
    broker_score: float = 0.0
    broker_reasons: List[str] = field(default_factory=list)
    
    unlock_score: float = 0.0
    unlock_reasons: List[str] = field(default_factory=list)
    
    fundamental_score: float = 0.0
    fundamental_reasons: List[str] = field(default_factory=list)
    
    technical_score: float = 0.0
    technical_reasons: List[str] = field(default_factory=list)
    
    penalties: List[str] = field(default_factory=list)
    bonuses: List[str] = field(default_factory=list)


@dataclass
class ScreenedStock:
    """A stock that has been fully evaluated by the 4-Pillar Engine."""
    symbol: str
    name: str = ""
    sector: str = ""  # Stock sector (e.g., "Hydro Power", "Banking")
    
    # Final verdict
    total_score: float = 0.0
    raw_score: float = 0.0  # Uncapped score for sorting
    recommendation: str = ""
    verdict_reason: str = ""
    
    # Pillar scores (weighted)
    pillar1_broker: float = 0.0      # Max 30
    pillar2_unlock: float = 0.0      # Max 20 (or -50 penalty)
    pillar3_fundamental: float = 0.0  # Max 20
    pillar4_technical: float = 0.0    # Max 30
    
    # Override layer (real-world constraints)
    market_regime_penalty: float = 0.0  # -15 if bear market
    is_bear_market: bool = False
    
    # Raw metrics for transparency
    ltp: float = 0.0
    pe_ratio: float = 0.0
    pbv: float = 0.0
    eps: float = 0.0
    roe: float = 0.0
    one_year_yield: float = 0.0
    
    # Broker data
    buyer_dominance_pct: float = 0.0
    top3_broker_holding_pct: float = 0.0
    winner: str = ""  # "Buyer" or "Seller"
    
    # DISTRIBUTION RISK (Broker Profit-Taking Detection)
    broker_avg_cost: float = 0.0        # Estimated average cost for accumulated shares
    broker_avg_cost_1w: float = 0.0     # 1-week avg cost for fine-tune layer
    broker_profit_pct: float = 0.0      # Current price vs average cost (% gain)
    distribution_risk: str = ""         # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    distribution_warning: str = ""      # Detailed explanation for user
    
    # DUAL TIMEFRAME ANALYSIS (Expert Rule)
    net_holdings_1m: int = 0            # Net shares accumulated in 1 month
    net_holdings_1w: int = 0            # Net shares accumulated in 1 week
    distribution_divergence: bool = False  # True if 1M accumulating but 1W distributing
    
    # INTRADAY DISTRIBUTION (Sunday Dump Detection)
    intraday_dump_detected: bool = False  # True if pump-and-dump pattern detected today
    today_open_price: float = 0.0         # Today's open price
    today_vwap: float = 0.0               # Today's VWAP
    open_vs_broker_pct: float = 0.0       # How much open was above broker avg
    close_vs_vwap_pct: float = 0.0        # How much close was below VWAP
    intraday_volume_spike: float = 0.0    # Today's volume vs 20-day avg
    
    # Unlock risk
    days_until_unlock: int = 999
    unlock_type: str = ""  # "MutualFund" or "Promoter" or "None"
    locked_percentage: float = 0.0
    
    # Technical
    rsi: float = 0.0
    ema_signal: str = ""
    volume_spike: float = 0.0
    atr: float = 0.0           # Average True Range for dynamic targets
    high_52w: float = 0.0      # 52-week high for blue sky breakout
    
    # Trade plan (WITH SLIPPAGE - Real-world NEPSE constraints)
    entry_price: float = 0.0           # Raw LTP
    entry_price_with_slippage: float = 0.0  # LTP * 1.015 (1.5% slippage)
    target_price: float = 0.0          # +10% from entry
    stop_loss: float = 0.0             # -5% raw
    stop_loss_with_slippage: float = 0.0    # -6.5% (accounting for slippage)
    risk_reward_ratio: float = 0.0
    
    # T+2 Settlement Warning
    minimum_hold_period: str = "3 Trading Days (T+2)"
    execution_warning: str = ""
    
    # HOLDING PERIOD GUIDANCE (Swing Trading)
    expected_holding_days: int = 7         # Expected days to reach target
    max_holding_days: int = 15             # Exit if neither target nor stop hit
    exit_strategy: str = ""                # Clear exit instruction
    
    # NEWS & AI ANALYSIS (Pillar 5 - Final Intelligence Layer)
    news_headlines: List[str] = field(default_factory=list)
    news_sentiment: str = ""       # BULLISH, NEUTRAL, BEARISH
    news_score_adjustment: float = 0.0  # -5 to +5 based on news
    
    ai_verdict: str = ""           # STRONG_BUY, BUY, RISKY, AVOID
    ai_confidence: float = 0.0     # 1-10
    ai_summary: str = ""           # 3-sentence AI explanation
    ai_risks: str = ""             # Key risks identified by AI
    
    # MANIPULATION DETECTION (Pillar 6 - Operator Intelligence)
    manipulation_risk_score: float = 0.0      # 0-100 (0=clean, 100=extreme)
    manipulation_severity: str = ""           # NONE, LOW, MEDIUM, HIGH, CRITICAL
    operator_phase: str = ""                  # ACCUMULATION, PUMP, DISTRIBUTION, CLEAN
    operator_phase_description: str = ""      # Human-readable phase explanation
    manipulation_alerts: List[str] = field(default_factory=list)
    manipulation_veto_reasons: List[str] = field(default_factory=list)
    broker_concentration_hhi: float = 0.0     # HHI index (>2500 = monopoly)
    top3_broker_control_pct: float = 0.0      # % controlled by top 3 brokers
    circular_trading_pct: float = 0.0         # % volume that's circular
    wash_trading_detected: bool = False       # Wash trading found
    lockup_days_remaining: Optional[int] = None  # Days until promoter unlock
    is_safe_to_trade: bool = True             # Final manipulation verdict
    
    # Detailed breakdown
    breakdown: ScoringBreakdown = field(default_factory=ScoringBreakdown)
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "total_score": round(self.total_score, 1),
            "recommendation": self.recommendation,
            "verdict_reason": self.verdict_reason,
            "pillar_scores": {
                "broker_institutional": round(self.pillar1_broker, 1),
                "unlock_risk": round(self.pillar2_unlock, 1),
                "fundamental": round(self.pillar3_fundamental, 1),
                "technical_momentum": round(self.pillar4_technical, 1),
            },
            "override_layer": {
                "market_regime_penalty": round(self.market_regime_penalty, 1),
                "is_bear_market": self.is_bear_market,
            },
            "metrics": {
                "ltp": self.ltp,
                "pe_ratio": round(self.pe_ratio, 2),
                "pbv": round(self.pbv, 2),
                "eps": round(self.eps, 2),
                "roe": round(self.roe, 2),
                "one_year_yield": round(self.one_year_yield, 2),
            },
            "broker_analysis": {
                "winner": self.winner,
                "buyer_dominance_pct": round(self.buyer_dominance_pct, 1),
                "top3_broker_holding_pct": round(self.top3_broker_holding_pct, 1),
            },
            "unlock_risk": {
                "days_until_unlock": self.days_until_unlock,
                "unlock_type": self.unlock_type,
                "locked_percentage": round(self.locked_percentage, 2),
            },
            "technical": {
                "rsi": round(self.rsi, 1),
                "ema_signal": self.ema_signal,
                "volume_spike": round(self.volume_spike, 2),
            },
            "trade_plan": {
                "raw_ltp": round(self.entry_price, 2),
                "entry_price_with_slippage": round(self.entry_price_with_slippage, 2),
                "target_price": round(self.target_price, 2),
                "stop_loss_raw": round(self.stop_loss, 2),
                "stop_loss_with_slippage": round(self.stop_loss_with_slippage, 2),
                "risk_reward_ratio": round(self.risk_reward_ratio, 2),
                "minimum_hold_period": self.minimum_hold_period,
                "expected_holding_days": self.expected_holding_days,
                "max_holding_days": self.max_holding_days,
                "exit_strategy": self.exit_strategy,
                "execution_warning": self.execution_warning,
            },
            "scoring_breakdown": {
                "broker_reasons": self.breakdown.broker_reasons,
                "unlock_reasons": self.breakdown.unlock_reasons,
                "fundamental_reasons": self.breakdown.fundamental_reasons,
                "technical_reasons": self.breakdown.technical_reasons,
                "penalties": self.breakdown.penalties,
                "bonuses": self.breakdown.bonuses,
            },
            "news_analysis": {
                "headlines": self.news_headlines[:3],  # Top 3 headlines
                "sentiment": self.news_sentiment,
                "score_adjustment": round(self.news_score_adjustment, 1),
            },
            "ai_analysis": {
                "verdict": self.ai_verdict,
                "confidence": round(self.ai_confidence, 1),
                "summary": self.ai_summary,
                "risks": self.ai_risks,
            },
        }


class MasterStockScreener:
    """
    🎯 THE MILLIONAIRE QUANTITATIVE SCORING ENGINE
    
    This class implements a 4-Pillar scoring algorithm that evaluates
    every stock mathematically. It is NOT an API wrapper.
    
    SCORING WEIGHTS:
    ================
    Pillar 1 - Broker/Institutional: 30% (0-30 points)
    Pillar 2 - Unlock Risk: 20% (0-20 points, or -50 penalty!)
    Pillar 3 - Fundamental Safety: 20% (0-20 points)
    Pillar 4 - Technical Momentum: 30% (0-30 points)
    
    USAGE:
    ======
    screener = MasterStockScreener()
    results = screener.run_full_analysis(min_score=60)
    
    for stock in results:
        print(f"{stock.symbol}: {stock.total_score}/100")
        print(f"  Verdict: {stock.verdict_reason}")
    """
    
    # Weight configuration
    WEIGHT_BROKER = 0.30      # 30% for broker/institutional
    WEIGHT_UNLOCK = 0.20      # 20% for unlock risk
    WEIGHT_FUNDAMENTAL = 0.20  # 20% for fundamentals
    WEIGHT_TECHNICAL = 0.30    # 30% for technical
    
    # Thresholds
    MIN_PRICE = 100           # Avoid penny stocks
    MIN_TURNOVER = 10_000_000  # Rs. 1 Crore minimum turnover (liquidity filter)
    UNLOCK_DANGER_DAYS = 30   # Days before unlock = DANGER
    UNLOCK_WARNING_DAYS = 60  # Days before unlock = WARNING
    
    # Real-world NEPSE constraints
    SLIPPAGE_PERCENT = 0.015  # 1.5% slippage on entry/exit
    BEAR_MARKET_PENALTY = -15  # Penalty when NEPSE index < 50-day EMA
    
    # ========== 🛡️ SYSTEMATIC RISK MANAGEMENT ==========
    # Kill Switch thresholds
    PANIC_INTRADAY_DROP = -2.0      # If index drops >2% intraday → PANIC mode
    PANIC_BELOW_EMA20_VOLUME = 1.5  # Index below EMA20 with 1.5x avg volume → PANIC
    
    # Divergence Penalty (Fake Data Detection)
    DIVERGENCE_PENALTY = -15        # Penalty when fundamentals and broker flow contradict
    DIVERGENCE_THRESHOLD_HIGH_FUND = 15.0  # Fundamentals score threshold for "great report"
    DIVERGENCE_THRESHOLD_LOW_BROKER = 10.0 # Broker score threshold for "smart money dumping"
    
    # Cash Dividend Focus (Fake Profit Detection)
    NO_DIVIDEND_PENALTY = -5        # Penalty for high EPS but no dividends in 3 years
    DIVIDEND_BONUS = 3              # Bonus for consistent dividend payers
    
    # ATR-based profit targets for 1:2 Risk-Reward (Dynamic based on regime)
    ATR_STOP_MULTIPLIER = 1.5   # Stop Loss = LTP - (1.5 * ATR) [BULL]
    ATR_TARGET_MULTIPLIER = 3.0  # Target = LTP + (3.0 * ATR) → 1:2 R:R [BULL]
    ATR_STOP_MULTIPLIER_BEAR = 1.0   # Tighter stop in BEAR market
    ATR_TARGET_MULTIPLIER_BEAR = 2.0  # Conservative target in BEAR
    
    # ========== 🚨 VWAP INTRADAY DISTRIBUTION DETECTION (Sunday Dump Fix) ==========
    # Detects when operators pump open price high and dump during the day
    # Example: BARUN 2026-03-22 opened at 400 (+5.4% above broker avg), dumped to 385
    THRESHOLD_OPEN_PREMIUM = 0.05       # Open >= broker_avg * 1.05 (5% above cost = pump signal)
    THRESHOLD_OPEN_CRITICAL = 0.08      # Open >= broker_avg * 1.08 (8% = definite pump-and-dump)
    THRESHOLD_VOLUME_MULTIPLIER = 1.5   # Volume >= 1.5x avg = unusual activity
    THRESHOLD_VOLUME_CRITICAL = 2.0     # Volume >= 2.0x avg = panic dumping
    THRESHOLD_VWAP_CLOSE_RATIO = 1.0    # Close < VWAP = distribution (selling pressure)
    
    # Penalties for intraday distribution detection
    INTRADAY_DIST_PENALTY_CRITICAL = -20  # CRITICAL: Open spike + volume + close < VWAP
    INTRADAY_DIST_PENALTY_HIGH = -15      # HIGH: 3+ conditions met
    INTRADAY_DIST_PENALTY_MEDIUM = -10    # MEDIUM: 2 conditions met
    
    # Momentum score caps when distribution detected
    MOMENTUM_CAP_CRITICAL = 35  # Max momentum score when CRITICAL distribution
    MOMENTUM_CAP_HIGH = 45      # Max momentum score when HIGH distribution
    
    # Market Regime Enum-like constants
    REGIME_BULL = "BULL"
    REGIME_BEAR = "BEAR"
    REGIME_PANIC = "PANIC"  # No BUY signals allowed!
    
    SECTOR_METHOD_MAP = {
        "Commercial Banks": "getDailyBankSubindexGraph",
        "Development Banks": "getDailyDevelopmentBankSubindexGraph",
        "Finance": "getDailyFinanceSubindexGraph",
        "Hotels And Tourism": "getDailyHotelTourismSubindexGraph",
        "Hydro Power": "getDailyHydroSubindexGraph",
        "Hydropower": "getDailyHydroSubindexGraph",
        "Investment": "getDailyInvestmentSubindexGraph",
        "Life Insurance": "getDailyLifeInsuranceSubindexGraph",
        "Manufacturing And Processing": "getDailyManufacturingSubindexGraph",
        "Manufacturing": "getDailyManufacturingSubindexGraph",
        "Microfinance": "getDailyMicrofinanceSubindexGraph",
        "Mutual Fund": "getDailyMutualfundSubindexGraph",
        "Non Life Insurance": "getDailyNonLifeInsuranceSubindexGraph",
        "Others": "getDailyOthersSubindexGraph",
        "Trading": "getDailyTradingSubindexGraph",
    }
    
    # Map CLI keywords to official NEPSE sector names
    SECTOR_MAP = {
        "bank": "Commercial Banks",
        "commercial_bank": "Commercial Banks",
        "devbank": "Development Banks",
        "development_bank": "Development Banks",
        "finance": "Finance",
        "micro": "Microfinance",
        "microfinance": "Microfinance",
        "hydro": "Hydropower",
        "hydropower": "Hydropower",
        "life": "Life Insurance",
        "life_insurance": "Life Insurance",
        "non_life": "Non Life Insurance",
        "non_life_insurance": "Non Life Insurance",
        "insurance": "Life Insurance", # Default to Life if generic
        "hotel": "Hotels And Tourism",
        "tourism": "Hotels And Tourism",
        "manufacturing": "Manufacturing And Processing",
        "production": "Manufacturing And Processing",
        "trading": "Trading",
        "investment": "Investment",
        "others": "Others",
        "mutual_fund": "Mutual Fund"
    }
    
    def __init__(self, sharehub_token: str = None, strategy: str = "value", target_sector: str = None, max_price: float = None, analysis_date: "date" = None):
        """Initialize with optional ShareHub auth token, strategy, target sector, max price budget, and analysis_date for historical mode."""
        import os
        from dotenv import load_dotenv
        from core.config import settings as app_settings
        
        # Explicitly load .env to ensure we get the token
        load_dotenv()
        
        self.strategy = strategy
        # Map legacy strategy names
        if self.strategy == "standard": self.strategy = "value"
        if self.strategy == "hydro": self.strategy = "momentum"
        
        self.target_sector = target_sector
        self.max_price = max_price  # Budget filter: skip stocks above this price
        
        # Resolve target sector name if provided
        if self.target_sector and self.target_sector.lower() in self.SECTOR_MAP:
            self.target_sector = self.SECTOR_MAP[self.target_sector.lower()]
            
        self.fetcher = NepseFetcher()
        self.sharehub_token = sharehub_token or os.getenv("SHAREHUB_AUTH_TOKEN") or app_settings.sharehub_auth_token
        
        # Debug token status
        if self.sharehub_token:
            masked = self.sharehub_token[:10] + "..." + self.sharehub_token[-5:]
            logger.info(f"🔐 ShareHub Token Loaded: {masked}")
        else:
            logger.warning("⚠️ ShareHub Token NOT FOUND in env or settings!")

        self.sharehub = ShareHubAPI(auth_token=self.sharehub_token)
        
        # Pre-loaded market data (reduces API calls)
        self._player_favorites: Dict[str, Dict] = {}
        self._unlock_risks: Dict[str, Dict] = {}
        self._broker_accumulation: Dict[str, Dict] = {}
        self._distribution_risk_cache: Dict[str, Dict] = {}  # NEW: Distribution risk per symbol
        self._fundamentals_cache: Dict[str, Dict] = {}
        self._sector_performance_cache: Dict[str, float] = {}  # Sector 5-day return
        self._sector_trend_cache: Dict[str, float] = {}        # Sector 1-day trend (New)
        self._symbol_sector_map: Dict[str, str] = {}
        self._dividend_history_cache: Dict[str, List] = {}     # Dividend records per symbol
        
        # Market regime state (Enhanced Risk Management)
        self._is_bear_market: bool = False
        self._market_regime: str = self.REGIME_BULL  # BULL, BEAR, or PANIC
        self._market_regime_checked: bool = False
        self._nepse_5d_return: float = 0.0
        self._regulatory_warnings: List[str] = []  # NRB/SEBON notices
        self._using_historical_fallback: bool = False  # True if market closed, using historical data
        
        # ===== HISTORICAL ANALYSIS MODE =====
        # When set, all fetched price dataframes are truncated to <= this date
        # Technical indicators (RSI, EMA, VWAP, ATR) are calculated only on historical data
        # NOTE: Broker data APIs don't support date filtering - broker scores use current data
        self._analysis_date: Optional[date] = analysis_date
        if self._analysis_date:
            logger.info(f"📅 HISTORICAL MODE: Indicators will be calculated as of {self._analysis_date}")
    
    def _fetch_historical_safe(self, symbol: str, days: int = 60, min_rows: int = 14) -> pd.DataFrame:
        """
        Wrapper around fetcher.safe_fetch_data that respects _analysis_date.
        
        When _analysis_date is set, truncates returned data to <= that date,
        ensuring all technical indicators are calculated on historical data only.
        """
        return self.fetcher.safe_fetch_data(
            symbol, 
            days=days, 
            min_rows=min_rows, 
            end_date=self._analysis_date
        )
    
    def _fetch_price_history_historical(self, symbol: str, days: int = 60) -> pd.DataFrame:
        """
        Wrapper around fetcher.fetch_price_history that respects _analysis_date.
        
        When _analysis_date is set, truncates returned data to <= that date.
        """
        df = self.fetcher.fetch_price_history(symbol, days=days)
        if df is None or df.empty or self._analysis_date is None:
            return df if df is not None else pd.DataFrame()
        
        # Truncate to analysis date
        if 'date' in df.columns:
            df = df.copy()
            df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
            df = df[df['date'] <= self._analysis_date]
            logger.debug(f"{symbol}: Truncated price history to {self._analysis_date}, {len(df)} rows")
        return df.reset_index(drop=True)
    
    def check_market_regime(self) -> Tuple[str, str]:
        """
        🛡️ ENHANCED MARKET REGIME CHECK - Bull, Bear, or PANIC Mode
        
        LOGIC:
        1. PANIC MODE (Kill Switch) - No BUY signals allowed:
           - Index drops >2% from previous close (intraday crash)
           - Index breaks below 20-day EMA with above-average volume
        2. BEAR MARKET:
           - Index below 50-day EMA
        3. BULL MARKET:
           - Index above 50-day EMA
        
        Returns:
            Tuple of (regime: str, reason: str) where regime is BULL/BEAR/PANIC
        """
        if self._market_regime_checked:
            return self._market_regime, "Already checked"
        
        try:
            logger.info("📊 Checking Market Regime (Enhanced Kill Switch)...")
            
            # Fetch NEPSE Index history (60 days for EMA calculations)
            index_data = self.fetcher.fetch_index_history(days=60)
            
            if index_data is None or len(index_data) < 50:
                logger.warning("   ⚠️ Insufficient index data, assuming neutral market")
                self._is_bear_market = False
                self._market_regime = self.REGIME_BULL
                self._market_regime_checked = True
                return self.REGIME_BULL, "Insufficient data"
            
            close_prices = index_data['close'].astype(float)
            volume_data = index_data['volume'].astype(float) if 'volume' in index_data.columns else None
            
            # Calculate EMAs
            ema_20 = close_prices.ewm(span=20, adjust=False).mean()
            ema_50 = close_prices.ewm(span=50, adjust=False).mean()
            
            current_index = float(close_prices.iloc[-1])
            previous_close = float(close_prices.iloc[-2]) if len(close_prices) > 1 else current_index
            current_ema_20 = float(ema_20.iloc[-1])
            current_ema_50 = float(ema_50.iloc[-1])
            
            # Calculate daily change (with division-by-zero protection)
            if previous_close > 0:
                daily_change_pct = ((current_index - previous_close) / previous_close) * 100
            else:
                daily_change_pct = 0.0
                logger.warning("Previous close is 0, cannot calculate daily change")
            
            # Calculate volume ratio (today vs 20-day average)
            volume_ratio = 1.0
            if volume_data is not None and len(volume_data) >= 20:
                avg_volume_20 = volume_data.iloc[-20:].mean()
                today_volume = volume_data.iloc[-1]
                volume_ratio = today_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0
            
            # ========== KILL SWITCH: PANIC MODE ==========
            # Condition 1: Index drops more than 2% intraday
            if daily_change_pct <= self.PANIC_INTRADAY_DROP:
                self._is_bear_market = True
                self._market_regime = self.REGIME_PANIC
                reason = f"🚨 PANIC MODE: Index crashed {daily_change_pct:.2f}% today! NO BUY SIGNALS."
                logger.critical(f"   {reason}")
                logger.critical("   🛑 KILL SWITCH ACTIVATED - All BUY recommendations disabled!")
                self._market_regime_checked = True
                return self.REGIME_PANIC, reason
            
            # Condition 2: Index below EMA20 with high volume (distribution)
            if current_index < current_ema_20 and volume_ratio >= self.PANIC_BELOW_EMA20_VOLUME:
                self._is_bear_market = True
                self._market_regime = self.REGIME_PANIC
                reason = f"🚨 PANIC MODE: Index {current_index:.2f} < EMA20 {current_ema_20:.2f} with {volume_ratio:.1f}x volume!"
                logger.critical(f"   {reason}")
                logger.critical("   🛑 KILL SWITCH ACTIVATED - Distribution detected, avoid buying!")
                self._market_regime_checked = True
                return self.REGIME_PANIC, reason
            
            # ========== BEAR MARKET ==========
            if current_index < current_ema_50:
                self._is_bear_market = True
                self._market_regime = self.REGIME_BEAR
                reason = f"🐻 BEAR MARKET: Index {current_index:.2f} < EMA50 {current_ema_50:.2f}"
                logger.warning(f"   {reason}")
                logger.warning(f"   → Applying {self.BEAR_MARKET_PENALTY} penalty to ALL stocks!")
                logger.warning(f"   → Momentum strategy DISABLED. Only VALUE strategy allowed.")
                self._market_regime_checked = True
                return self.REGIME_BEAR, reason
            
            # ========== BULL MARKET ==========
            self._is_bear_market = False
            self._market_regime = self.REGIME_BULL
            reason = f"🐂 BULL MARKET: Index {current_index:.2f} > EMA50 {current_ema_50:.2f}"
            logger.info(f"   {reason}")
            self._market_regime_checked = True
            return self.REGIME_BULL, reason
            
        except Exception as e:
            logger.warning(f"   ⚠️ Market regime check failed: {e}")
            self._is_bear_market = False
            self._market_regime = self.REGIME_BULL
            self._market_regime_checked = True
            return self.REGIME_BULL, f"Error: {e}"
    
    def check_regulatory_notices(self) -> List[str]:
        """
        🏛️ CHECK FOR NEW NRB/SEBON REGULATORY NOTICES
        
        Scrapes the notices pages of NRB and SEBON to detect new circulars
        that could impact the market (e.g., policy changes, margin rules).
        
        Returns:
            List of warning strings if new notices detected
        """
        warnings = []
        
        try:
            import requests
            from datetime import datetime, timedelta
            
            # Check SEBON notices (simpler API-like structure)
            sebon_url = "https://www.sebon.gov.np/notices"
            nrb_url = "https://www.nrb.org.np/notices-circulars/"
            
            # Simple check: Look for today's date in notice titles
            today = datetime.now()
            today_str = today.strftime("%Y-%m-%d")
            yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            # SEBON Check
            try:
                resp = requests.get(sebon_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    content = resp.text.lower()
                    # Check for common keywords
                    if any(kw in content for kw in ['margin', 'circular', 'directive', 'trading halt', 'suspension']):
                        if today_str in resp.text or yesterday_str in resp.text:
                            warnings.append("⚠️ NEW SEBON NOTICE DETECTED: Review sebon.gov.np before trading!")
            except Exception:
                pass  # Silently fail if SEBON is unreachable
            
            # NRB Check
            try:
                resp = requests.get(nrb_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    content = resp.text.lower()
                    if any(kw in content for kw in ['interest rate', 'ccd ratio', 'monetary policy', 'liquidity']):
                        if today_str in resp.text or yesterday_str in resp.text:
                            warnings.append("⚠️ NEW NRB NOTICE DETECTED: Review nrb.org.np before trading!")
            except Exception:
                pass  # Silently fail if NRB is unreachable
            
        except Exception as e:
            logger.debug(f"Regulatory check failed: {e}")
        
        self._regulatory_warnings = warnings
        if warnings:
            for w in warnings:
                logger.warning(w)
        
        return warnings
    
    def run_full_analysis(
        self,
        min_score: float = 60,
        top_n: int = 10,
        include_rejected: bool = False,
        quick_mode: bool = False,
        max_workers: int = 10,
    ) -> List[ScreenedStock]:
        """
        🚀 Run the complete 4-Pillar analysis on ALL NEPSE stocks.
        
        🛡️ RISK MANAGEMENT:
        - PANIC MODE: Returns empty list (no BUY signals)
        - BEAR MARKET: Disables momentum strategy, uses tighter stops
        
        Args:
            min_score: Minimum score to include (default 60)
            top_n: Number of top stocks to return
            include_rejected: Whether to include rejected stocks (for debugging)
            quick_mode: If True, only analyze top 50 stocks by volume (5x faster)
            max_workers: Number of parallel threads for analysis
        
        Returns:
            List of ScreenedStock objects, ranked by total_score
        """
        logger.info("=" * 70)
        logger.info("🎯 MASTER STOCK SCREENER - Starting 4-Pillar Analysis")
        if quick_mode:
            logger.info("⚡ QUICK MODE: Analyzing top 50 stocks by volume only")
        logger.info("=" * 70)
        
        # Step 0: Check market regime (Bull/Bear/PANIC)
        regime, regime_reason = self.check_market_regime()
        
        # 🛑 KILL SWITCH: PANIC MODE - NO BUY SIGNALS!
        if regime == self.REGIME_PANIC:
            logger.critical("=" * 70)
            logger.critical("🚨 KILL SWITCH ACTIVATED: PANIC MODE")
            logger.critical("🛑 NO BUY SIGNALS WILL BE GENERATED TODAY")
            logger.critical(f"   Reason: {regime_reason}")
            logger.critical("=" * 70)
            return []  # Empty list - no recommendations
        
        # 🐻 BEAR MARKET: Disable momentum strategy, force value
        if regime == self.REGIME_BEAR and self.strategy == "momentum":
            logger.warning("=" * 70)
            logger.warning("⚠️ BEAR MARKET OVERRIDE: Momentum strategy DISABLED")
            logger.warning("   → Switching to VALUE strategy (safer in downtrends)")
            logger.warning("   → Using tighter stop-losses (1.0 ATR instead of 1.5 ATR)")
            logger.warning("=" * 70)
            self.strategy = "value"  # Force value strategy in bear market
        
        # Check for regulatory notices
        regulatory_warnings = self.check_regulatory_notices()
        if regulatory_warnings:
            logger.warning("=" * 70)
            for warning in regulatory_warnings:
                logger.warning(warning)
            logger.warning("   → Manual review recommended before executing trades!")
            logger.warning("=" * 70)
        
        # Step 1: Pre-load all market data (reduces API calls)
        self._preload_market_data()
        
        # Step 2: Get all active stocks
        stocks = self._get_active_stocks(quick_mode=quick_mode)
        
        # Quick mode: Only analyze top 50 by volume (much faster)
        if quick_mode:
            stocks = sorted(stocks, key=lambda x: float(x.get("totalTradeQuantity", 0) or 0), reverse=True)[:50]
            logger.info(f"📊 Quick mode: Analyzing top {len(stocks)} stocks by volume")
        else:
            logger.info(f"📊 Found {len(stocks)} active stocks to analyze")
        
        # Step 3: Score each stock through the 4-Pillar Engine (with parallel processing)
        results: List[ScreenedStock] = []
        rejected: List[ScreenedStock] = []
        results_lock = threading.Lock()
        
        def score_single_stock(stock_data: Dict) -> Optional[ScreenedStock]:
            """Thread-safe stock scoring."""
            try:
                return self._score_stock(stock_data)
            except Exception as e:
                logger.debug(f"Error analyzing {stock_data.get('symbol', '')}: {e}")
                return None
        
        # Use parallel processing for faster analysis
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(score_single_stock, stock): stock for stock in stocks}
            completed = 0
            
            for future in as_completed(futures):
                completed += 1
                screened = future.result()
                
                if screened:
                    with results_lock:
                        if screened.total_score >= min_score:
                            results.append(screened)
                        else:
                            rejected.append(screened)
                
                # Progress logging every 50 stocks
                if completed % 50 == 0:
                    logger.info(f"   Analyzed {completed}/{len(stocks)} stocks...")
        
        # Legacy sequential processing (fallback)
        # for i, stock in enumerate(stocks):
        #     symbol = stock.get("symbol", "")
        #     try:
        #         screened = self._score_stock(stock)
        #         if screened.total_score >= min_score:
        #             results.append(screened)
        #         else:
        #             rejected.append(screened)
        #         if (i + 1) % 50 == 0:
        #             logger.info(f"   Analyzed {i + 1}/{len(stocks)} stocks...")
        #     except Exception as e:
        #         logger.debug(f"Error analyzing {symbol}: {e}")
        #         continue
        
        # Step 4: Sort by RAW score for precision (descending)
        results.sort(key=lambda x: x.raw_score, reverse=True)
        
        # Step 5: Assign recommendations
        for stock in results:
            stock.recommendation = self._get_recommendation(stock.total_score)
        
        logger.info("=" * 70)
        logger.info(f"✅ Analysis complete!")
        logger.info(f"   Passed: {len(results)} stocks (score >= {min_score})")
        logger.info(f"   Rejected: {len(rejected)} stocks")
        logger.info("=" * 70)
        
        final_results = results[:top_n]
        if include_rejected:
            return final_results + rejected[:5]
        return final_results
    
    def run_stealth_analysis(
        self,
        top_n: int = 500,
        max_workers: int = 8,
    ) -> List[ScreenedStock]:
        """
        🕵️ STEALTH RADAR MODE - Detect Smart Money Accumulation
        
        This is a SPECIALIZED scan mode that:
        1. BYPASSES the turnover filter (operators accumulate on LOW volume)
        2. Fetches ALL stocks (even historical data when market is closed)
        3. Runs full 4-Pillar scoring
        4. Returns ALL stocks (no min_score filter) for stealth filtering
        
        The caller (paper_trader.py) will filter for:
        - Broker Score > 80% AND Technical Score < 40%
        - Distribution Risk = LOW
        
        Returns:
            All scored stocks without filtering (stealth filtering done externally)
        """
        logger.info("=" * 70)
        logger.info("🕵️ STEALTH RADAR - Smart Money Detection Mode")
        logger.info("   📊 Bypassing turnover filter (operators accumulate quietly)")
        logger.info("=" * 70)
        
        # Pre-load market data
        self._preload_market_data()
        
        # Get ALL stocks with turnover bypass
        stocks = self._get_active_stocks(
            allow_historical_fallback=True,
            bypass_turnover_filter=True,
            for_stealth_scan=True,
        )
        
        logger.info(f"📊 Stealth scan: {len(stocks)} stocks to analyze")
        
        # Score all stocks
        results: List[ScreenedStock] = []
        results_lock = threading.Lock()
        
        def score_single_stock(stock_data: Dict) -> Optional[ScreenedStock]:
            """Thread-safe stock scoring with enhanced error handling."""
            try:
                return self._score_stock(stock_data)
            except Exception as e:
                # DEFENSIVE: Log but don't crash the entire scan
                symbol = stock_data.get('symbol', 'UNKNOWN')
                logger.debug(f"⚠️ Stealth scoring failed for {symbol}: {e}")
                return None
        
        # Parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(score_single_stock, stock): stock for stock in stocks}
            completed = 0
            errors = 0
            
            for future in as_completed(futures):
                completed += 1
                try:
                    screened = future.result()
                    if screened:
                        with results_lock:
                            results.append(screened)
                except Exception as e:
                    errors += 1
                    logger.debug(f"Future error: {e}")
                
                if completed % 100 == 0:
                    logger.info(f"   Stealth analyzed {completed}/{len(stocks)} stocks...")
        
        logger.info("=" * 70)
        logger.info(f"✅ Stealth analysis complete: {len(results)} stocks scored")
        if errors > 0:
            logger.info(f"   ⚠️ {errors} stocks skipped due to errors (graceful degradation)")
        logger.info("=" * 70)
        
        return results
    
    def enrich_with_news_and_ai(
        self,
        stocks: List[ScreenedStock],
        scrape_news: bool = True,
        use_ai: bool = True,
        headless: bool = True,
    ) -> List[ScreenedStock]:
        """
        📰🤖 ENRICH TOP PICKS WITH NEWS SCRAPING AND AI ANALYSIS
        
        This is the FINAL INTELLIGENCE LAYER that:
        1. Scrapes recent news using Playwright (ShareSansar + Merolagani)
        2. Analyzes news sentiment
        3. Calls OpenAI GPT to generate final verdict with human-readable explanation
        4. Adjusts final score based on news sentiment
        
        IMPORTANT: Only call this for TOP 5-10 stocks (to save time & API costs)
        
        Args:
            stocks: List of ScreenedStock objects (top picks only!)
            scrape_news: Whether to scrape news using Playwright browser
            use_ai: Whether to use OpenAI for AI verdict
            headless: Whether to run browser visibly (False) or hidden (True)
        
        Returns:
            Enriched ScreenedStock list with news & AI data
        """
        if not stocks:
            return stocks
        
        logger.info("=" * 70)
        logger.info(f"📰🤖 ENRICHING TOP PICKS WITH NEWS & AI ANALYSIS (Headless: {headless})")
        logger.info("=" * 70)

        # Define async worker to reuse scraper instance
        async def _process_enrichment():
            scraper = None
            try:
                if scrape_news and NEWS_AVAILABLE:
                    try:
                        scraper = NewsScraper(headless=headless)
                        # Pre-load cache ONCE (Batch Fetch)
                        logger.info("      🚀 Batch fetching market news...")
                        await scraper._scrape_market_news()
                    except Exception as e:
                        error_text = str(e)
                        if "Executable doesn't exist" in error_text:
                            logger.warning(
                                "News scraper disabled: Playwright browser is not installed. "
                                "Run: playwright install chromium"
                            )
                        else:
                            logger.error(f"Failed to initialize scraper: {e}")
                        scraper = None

                for i, stock in enumerate(stocks):
                    symbol = stock.symbol
                    logger.info(f"   [{i+1}/{len(stocks)}] Analyzing {symbol}...")

                    # Step 1: Scrape News (using shared scraper)
                    news_items = []
                    if scraper:
                        try:
                            # This uses the cached news from _scrape_market_news
                            news_items = await scraper.scrape_all_sources(symbol, limit=3)

                            stock.news_headlines = [item.title for item in news_items]

                            # Basic sentiment analysis based on keywords
                            stock.news_sentiment, stock.news_score_adjustment = \
                                self._analyze_news_sentiment(news_items)

                            if stock.news_score_adjustment != 0:
                                stock.total_score += stock.news_score_adjustment
                                stock.total_score = min(100, max(0, stock.total_score))
                                stock.breakdown.bonuses.append(
                                    f"📰 News Sentiment: {stock.news_sentiment} ({stock.news_score_adjustment:+.1f} pts)"
                                )
                        except Exception as e:
                            logger.warning(f"      ⚠️ News scrape failed for {symbol}: {e}")

                    # Step 2: AI Verdict (OpenAI)
                    if use_ai and AI_AVAILABLE:
                        try:
                            # Check if we actually have news headlines
                            has_real_news = bool(news_items and len(news_items) > 0)

                            # Format news for AI
                            news_text = ""
                            if has_real_news:
                                news_text = "\n".join([f"- {item.title} ({item.source})" for item in news_items])
                            else:
                                news_text = "No recent news available for this stock."

                            # Add fundamental context to news text
                            fundamental_context = f"\n\nFundamental Data: PE={stock.pe_ratio:.1f}, PBV={stock.pbv:.2f}, ROE={stock.roe:.1f}%"
                            if stock.winner:
                                fundamental_context += f", Broker Signal: {stock.winner}"

                            # Prepare signal data for AI
                            signal_data = {
                                "symbol": symbol,
                                "entry_price": stock.ltp,
                                "target_price": stock.target_price,
                                "stop_loss": stock.stop_loss,
                                "strategy_name": "4-Pillar Quantitative Engine",
                                "confidence": stock.total_score / 10,  # Convert to 1-10
                                "reason": stock.verdict_reason,
                                "indicators": {
                                    "rsi": stock.rsi,
                                    "ema_signal": stock.ema_signal,
                                    "volume_spike": stock.volume_spike,
                                },
                                # Fundamental context
                                "pe_ratio": stock.pe_ratio,
                                "pb_ratio": stock.pbv,
                                "roe": stock.roe,
                                "eps": stock.eps,
                                "valuation": "UNDERVALUED" if stock.pe_ratio < 15 else "FAIR" if stock.pe_ratio < 25 else "OVERVALUED",
                                "broker_signal": stock.winner,
                            }

                            # Call AI Advisor
                            verdict = get_ai_verdict(signal_data, news_text + fundamental_context)

                            if verdict:
                                stock.ai_verdict = verdict.verdict
                                stock.ai_confidence = verdict.confidence

                                # ANTI-HALLUCINATION GATEKEEPER:
                                # If no real news was found, override AI summary to prevent fabrication
                                if not has_real_news:
                                    stock.ai_summary = "No recent news found for this company."
                                    stock.ai_risks = "Technical trading only. Monitor for hidden fundamental risks."
                                else:
                                    stock.ai_summary = verdict.summary
                                    stock.ai_risks = verdict.risks

                                logger.info(f"      ✅ AI Verdict: {stock.ai_verdict} (Confidence: {stock.ai_confidence:.1f}/10)")

                                # Add AI recommendation to bonuses/penalties
                                if "BUY" in stock.ai_verdict:
                                    stock.breakdown.bonuses.append(f"🤖 AI Verdict: {stock.ai_verdict}")
                                elif "SELL" in stock.ai_verdict:
                                    stock.breakdown.penalties.append(f"🤖 AI Verdict: {stock.ai_verdict}")

                        except Exception as e:
                            logger.warning(f"      ⚠️ AI Analysis failed for {symbol}: {e}")
            finally:
                # Cleanup
                if scraper:
                    await scraper._close_browser()

        # Run the async process
        try:
            asyncio.run(_process_enrichment())
        except Exception as e:
            logger.error(f"Enrichment process failed: {e}")

        return stocks
    
    def _analyze_news_sentiment(self, news_items) -> Tuple[str, float]:
        """
        Analyze news sentiment using keyword matching.
        
        Returns:
            Tuple of (sentiment: str, score_adjustment: float)
        """
        if not news_items:
            return "NEUTRAL", 0.0
        
        # Keywords for sentiment analysis
        bullish_keywords = [
            "profit", "dividend", "bonus", "growth", "record", "highest", "strong",
            "expansion", "merger", "acquisition", "positive", "bullish", "upside",
            "लाभ", "बोनस", "लाभांश", "वृद्धि"  # Nepali keywords
        ]
        
        bearish_keywords = [
            "loss", "decline", "fraud", "scam", "negative", "bearish", "downgrade",
            "concern", "risk", "warning", "sell", "drop", "crash", "investigation",
            "घाटा", "जोखिम"  # Nepali keywords
        ]
        
        bullish_count = 0
        bearish_count = 0
        
        for item in news_items:
            text = (item.title + " " + (item.snippet or "")).lower()
            
            for keyword in bullish_keywords:
                if keyword.lower() in text:
                    bullish_count += 1
            
            for keyword in bearish_keywords:
                if keyword.lower() in text:
                    bearish_count += 1
        
        # Determine sentiment
        if bullish_count > bearish_count + 1:
            return "BULLISH", 3.0  # +3 points
        elif bearish_count > bullish_count + 1:
            return "BEARISH", -5.0  # -5 points (asymmetric - bad news hits harder)
        else:
            return "NEUTRAL", 0.0
    
    def _preload_market_data(self, single_symbol: str = None):
        """
        Pre-load all market data to reduce API calls during scoring.
        
        Args:
            single_symbol: If provided, only load data relevant to this one stock
                          (faster for single stock analysis)
        """
        
        # 0. Load Company List for Sector Mapping (Needed for Sector Bonus)
        logger.info("🏭 Loading company list for sector mapping...")
        try:
            companies = self.fetcher.fetch_company_list()
            # Handle if result is list of dicts or objects
            for c in companies:
                if isinstance(c, dict):
                    symbol = c.get("symbol", "")
                    sector = c.get("sectorName", "")
                else:
                    symbol = getattr(c, "symbol", "")
                    # Fetcher uses 'sector' field for StockData object, but also check sectorName just in case
                    sector = getattr(c, "sector", getattr(c, "sectorName", ""))
                    
                if symbol and sector:
                    self._symbol_sector_map[symbol] = sector
            logger.info(f"   ✅ Mapped {len(self._symbol_sector_map)} symbols to sectors")
        except Exception as e:
            logger.warning(f"   ⚠️ Could not load company list: {e}")
            
        # 1. Player Favorites (Buyer/Seller dominance) - NO AUTH NEEDED
        logger.info("📊 Loading Player Favorites (buyer/seller dominance)...")
        try:
            favorites = self.sharehub.get_player_favorites()
            for f in favorites:
                sym = f.get("symbol", "")
                # If single_symbol mode, only load that stock
                if single_symbol and sym != single_symbol:
                    continue
                if sym:
                    self._player_favorites[sym] = {
                        "winner": f.get("winner", ""),
                        "winner_weight": f.get("winnerWeight", 0),
                        "buy_amount": f.get("buyAmount", 0),
                        "sell_amount": f.get("sellAmount", 0),
                        "buy_quantity": f.get("buyQuantity", 0),
                        "sell_quantity": f.get("sellQuantity", 0),
                    }
            logger.info(f"   ✅ Loaded {len(self._player_favorites)} player favorites")
        except Exception as e:
            logger.warning(f"   ⚠️ Could not load player favorites: {e}")
        
        # 2. Unlock Risks (MF + Promoter) - NO AUTH NEEDED
        logger.info("📅 Loading Unlock Risks (MF + Promoter)...")
        try:
            # Type 0 = Promoter, Type 1 = MutualFund
            for lock_type, type_name in [(0, "Promoter"), (1, "MutualFund")]:
                unlocks = self.sharehub.get_promoter_unlock_data(lock_type=lock_type)
                for u in unlocks:
                    if u.remaining_days > 0:
                        sym = u.symbol
                        # If single_symbol mode, only load that stock
                        if single_symbol and sym != single_symbol:
                            continue
                        existing = self._unlock_risks.get(sym, {})
                        
                        # Keep the nearest unlock date
                        if not existing or u.remaining_days < existing.get("days", 999):
                            self._unlock_risks[sym] = {
                                "days": u.remaining_days,
                                "type": type_name,
                                "locked_pct": u.locked_percentage,
                                "locked_shares": u.locked_shares,
                                "is_mf": lock_type == 1,
                            }
            logger.info(f"   ✅ Loaded {len(self._unlock_risks)} unlock risks")
        except Exception as e:
            logger.warning(f"   ⚠️ Could not load unlock risks: {e}")
        
        # 3. Broker Accumulation (REQUIRES AUTH)
        if self.sharehub_token:
            logger.info("🏦 Loading Broker Accumulation (requires auth)...")
            try:
                # Load 1D holdings for current activity
                holdings_1d = self.sharehub.get_broker_aggressive_holdings(duration="1D")
                # Also load 7D holdings to estimate average cost
                holdings_7d = self.sharehub.get_broker_aggressive_holdings(duration="7D")
                
                # Create lookups for 7D data
                holdings_7d_map = {h.get("symbol", ""): h for h in holdings_7d}
                
                for h in holdings_1d:
                    sym = h.get("symbol", "")
                    # If single_symbol mode, only load that stock
                    if single_symbol and sym != single_symbol:
                        continue
                    if sym:
                        ltp = float(h.get("ltp", 0) or 0)
                        change_7d = float(h.get("change", 0) or 0)
                        
                        # Get 7D data if available
                        h_7d = holdings_7d_map.get(sym, {})
                        
                        self._broker_accumulation[sym] = {
                            "top3_pct": h.get("topThreeBrokersHoldingPercentage", 0),
                            "total_brokers": h.get("totalInvolvedBrokers", 0),
                            "hold_quantity": h.get("holdQuantity", 0),
                            "ltp": ltp,
                            "change_pct": h.get("changePercentage", 0),
                        }
                        
                        # Calculate Distribution Risk
                        self._calculate_distribution_risk(sym, ltp, h, h_7d)
                        
                logger.info(f"   ✅ Loaded {len(self._broker_accumulation)} broker holdings")
                logger.info(f"   📊 Calculated distribution risk for {len(self._distribution_risk_cache)} stocks")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not load broker accumulation: {e}")
        else:
            logger.info("   ⏭️ Skipping broker accumulation (no auth token)")

        # 4. Sector Trends (For Bonus Calculation)
        logger.info("🌊 Loading Sector Trends (for bonus)...")
        try:
            self._sector_trend_cache = self.fetcher.fetch_sector_indices()
            logger.info(f"   ✅ Loaded trends for {len(self._sector_trend_cache)} sectors")
        except Exception as e:
            logger.warning(f"   ⚠️ Could not load sector trends: {e}")

        # 4. Sector Performance (If Hydro Strategy)
        if self.strategy == "hydro":
            logger.info("🌊 Hydro Strategy: Loading NEPSE 5-day trend...")
            try:
                self._nepse_5d_return = self._get_nepse_5d_return()
                logger.info(f"   📈 NEPSE 5-day return: {self._nepse_5d_return:.2f}%")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not load NEPSE 5-day return: {e}")

    def _calculate_distribution_risk(self, symbol: str, ltp: float, holdings_1d: Dict, holdings_7d: Dict) -> None:
        """
        🎯 DISTRIBUTION RISK DETECTION - Detect When Big Players Will Sell
        
        LOGIC (How Operators Work in NEPSE):
        =====================================
        1. Big brokers (players/operators) ACCUMULATE stock over 2-3 weeks at LOW prices
        2. They hold to reduce supply → Price goes UP (the pump phase)
        3. Once price reaches their TARGET PROFIT (+15-20%), they START SELLING
        4. This INCREASES supply → Price CRASHES
        
        CALCULATION METHODS (Priority Order):
        =====================================
        1. REAL BROKER DATA: Use ShareHub's broker analysis to get actual avg buy price
           Formula: Avg Buy Price = Total Buy Amount / Total Buy Quantity
        2. VWAP FALLBACK: If broker data unavailable, use VWAP from price history
           Formula: VWAP = Sum(Typical_Price × Volume) / Sum(Volume)
        
        DYNAMIC LOOKBACK (Based on Strategy):
        - MOMENTUM strategy: 14-day lookback (captures fast pump/accumulation cycles)
        - VALUE strategy: 20-day lookback (captures slow, institutional accumulation)
        
        RISK LEVELS:
        - LOW (0-10% above cost): Safe to buy, players still accumulating
        - MEDIUM (10-15% above cost): Caution, players may start distributing
        - HIGH (15-20% above cost): Avoid! Players likely taking profits
        - CRITICAL (>20% or seller dominant): DO NOT BUY! Distribution in progress
        
        Returns:
            Updates self._distribution_risk_cache[symbol] with risk data
        """
        try:
            if ltp <= 0:
                return
            
            # Get player favorites for sell signal
            pf = self._player_favorites.get(symbol, {})
            is_seller_dominant = pf.get("winner") == "Seller" and pf.get("winner_weight", 0) > 55
            seller_weight = pf.get("winner_weight", 0) if pf.get("winner") == "Seller" else 0
            
            # ═══════════════════════════════════════════════════════════════════
            # DUAL TIMEFRAME BROKER ANALYSIS (Expert Rule-Based System)
            # ═══════════════════════════════════════════════════════════════════
            # 
            # RULE 1: Use 1-MONTH as BASELINE trend
            #   - Shows overall accumulation/distribution pattern
            #   - If top brokers net-buying for 1 month → conviction to buy
            # 
            # RULE 2: Use 1-WEEK as FINE-TUNE layer
            #   - Detects recent intraday dumps
            #   - Volume spikes without price follow-through
            #   - If 1W shows distribution even though 1M is good → CAUTION
            # 
            # RULE 3: Broker data NEVER overrides hard filters
            #   - RSI > 70 → Overbought, be cautious
            #   - EPS < 0 → Fundamental weakness
            #   - Heavy distribution day → Exit signal
            # 
            # CALCULATION FIX: Use NET HOLDINGS, not ALL BUYS
            #   - If broker bought 100K and sold 80K, they hold 20K
            #   - Avg cost = weighted avg of shares STILL HELD
            # ═══════════════════════════════════════════════════════════════════
            
            if self.strategy == "momentum":
                vwap_lookback_days = 14  # Short-term VWAP for fallback
            else:
                vwap_lookback_days = 20  # Longer-term VWAP for fallback
            
            broker_avg_cost = None
            broker_avg_cost_1w = None  # For fine-tune layer
            calculation_method = "UNKNOWN"
            lookback_used = vwap_lookback_days
            net_holdings_1m = 0
            net_holdings_1w = 0
            distribution_divergence = False  # 1M accumulating but 1W distributing
            
            def _calc_net_holdings_cost(broker_data):
                """Calculate avg cost for shares STILL HELD (net holdings only)."""
                if not broker_data:
                    return None, 0
                
                total_weighted_cost = 0.0
                total_net_holdings = 0
                
                for b in broker_data:
                    if b.net_quantity > 0 and b.buy_quantity > 0:
                        broker_avg_buy = b.buy_amount / b.buy_quantity
                        total_weighted_cost += broker_avg_buy * b.net_quantity
                        total_net_holdings += b.net_quantity
                
                if total_net_holdings > 0:
                    return total_weighted_cost / total_net_holdings, total_net_holdings
                return None, 0
            
            # === FETCH BOTH TIMEFRAMES ===
            try:
                if self.sharehub_token:
                    # 1-MONTH: Baseline accumulation trend
                    broker_data_1m = self.sharehub.get_broker_analysis(symbol, duration="1M")
                    if broker_data_1m:
                        broker_avg_cost, net_holdings_1m = _calc_net_holdings_cost(broker_data_1m)
                        if broker_avg_cost:
                            calculation_method = "BROKER_NET_HOLDINGS_1M"
                            logger.debug(f"{symbol}: 1M Avg Cost = Rs.{broker_avg_cost:.2f} ({net_holdings_1m:,} shares held)")
                    
                    # 1-WEEK: Fine-tune layer for recent distribution
                    broker_data_1w = self.sharehub.get_broker_analysis(symbol, duration="1W")
                    if broker_data_1w:
                        broker_avg_cost_1w, net_holdings_1w = _calc_net_holdings_cost(broker_data_1w)
                        if broker_avg_cost_1w:
                            logger.debug(f"{symbol}: 1W Avg Cost = Rs.{broker_avg_cost_1w:.2f} ({net_holdings_1w:,} shares held)")
                    
                    # DIVERGENCE CHECK: 1M accumulating but 1W distributing = RED FLAG
                    if net_holdings_1m > 0 and net_holdings_1w < 0:
                        distribution_divergence = True
                        logger.warning(f"{symbol}: ⚠️ DIVERGENCE: 1M accumulating but 1W distributing!")
                        
            except Exception as e:
                logger.debug(f"Could not fetch broker analysis for {symbol}: {e}")
            
            # === METHOD 2: VWAP FROM PRICE HISTORY (Fallback) ===
            if broker_avg_cost is None or broker_avg_cost <= 0:
                try:
                    df = self._fetch_price_history_historical(symbol, days=vwap_lookback_days + 5)
                    
                    if df is not None and not df.empty and len(df) >= 5:
                        df = df.tail(vwap_lookback_days)
                        lookback_used = len(df)
                        
                        # Calculate VWAP = Sum(Typical_Price * Volume) / Sum(Volume)
                        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
                        total_volume = df['volume'].sum()
                        
                        if total_volume > 0:
                            broker_avg_cost = (df['typical_price'] * df['volume']).sum() / total_volume
                            calculation_method = f"VWAP_{lookback_used}D"
                            
                except Exception as e:
                    logger.debug(f"Could not fetch OHLCV for VWAP ({symbol}): {e}")
            
            # === METHOD 3: SIMPLE ESTIMATION (Last Resort) ===
            if broker_avg_cost is None or broker_avg_cost <= 0:
                change_pct = 0.0
                
                if holdings_7d:
                    change_pct = float(holdings_7d.get("changePercentage", 0) or 0)
                
                if change_pct == 0:
                    try:
                        price_summary = self.sharehub.get_price_change_summary(symbol)
                        if price_summary:
                            change_pct = float(getattr(price_summary, 'change_7d_pct', 0) or 0)
                    except Exception:
                        pass
                
                if change_pct > 0:
                    broker_avg_cost = ltp / (1 + (change_pct / 100) * 0.5)
                else:
                    broker_avg_cost = ltp * 1.02
                
                calculation_method = "ESTIMATE"
                lookback_used = 7
            
            # Ensure avg cost is reasonable
            if broker_avg_cost <= 0:
                broker_avg_cost = ltp
            
            # === CALCULATE BROKER PROFIT PERCENTAGE ===
            broker_profit_pct = ((ltp - broker_avg_cost) / broker_avg_cost) * 100 if broker_avg_cost > 0 else 0
            
            # === DETERMINE RISK LEVEL ===
            distribution_risk = "LOW"
            warning = ""
            penalty = 0.0
            
            # ═══════════════════════════════════════════════════════════════════
            # DIVERGENCE CHECK (Expert Rule)
            # If 1M accumulating but 1W distributing → brokers starting to exit
            # This is a RED FLAG that should increase risk level
            # ═══════════════════════════════════════════════════════════════════
            if distribution_divergence:
                distribution_risk = "HIGH"
                warning = f"⚠️ Dump Risk: HIGH – 1M accumulating but 1W DISTRIBUTING! Brokers starting to exit. Avoid new entries."
                penalty = -12.0
                logger.warning(f"{symbol}: Divergence detected - 1M net {net_holdings_1m:,} vs 1W net {net_holdings_1w:,}")
            
            # CRITICAL: Seller dominant with high profit → Distribution in progress
            elif is_seller_dominant and broker_profit_pct > 10:
                distribution_risk = "CRITICAL"
                warning = f"🚨 Dump Risk: CRITICAL – Brokers up {broker_profit_pct:.1f}% AND sellers dominating ({seller_weight:.0f}%). Active distribution in progress!"
                penalty = -15.0
            
            # HIGH: Price significantly above broker cost
            elif broker_profit_pct >= 15:
                distribution_risk = "HIGH"
                warning = f"⚠️ Dump Risk: HIGH – Price {broker_profit_pct:.1f}% above broker avg (Rs.{broker_avg_cost:.0f}). Brokers sitting on big profits; may dump soon."
                penalty = -10.0
            
            # MEDIUM: Moderate profit, watch for distribution signals
            elif broker_profit_pct >= 10:
                distribution_risk = "MEDIUM"
                warning = f"🟡 Dump Risk: MODERATE – Price {broker_profit_pct:.1f}% above broker avg (Rs.{broker_avg_cost:.0f}). A bit above average; still within normal range."
                penalty = -5.0
            
            # LOW: Safe to buy, players still accumulating
            else:
                distribution_risk = "LOW"
                if broker_profit_pct < 5:
                    warning = f"✅ Dump Risk: LOW – Only {broker_profit_pct:.1f}% above broker avg (Rs.{broker_avg_cost:.0f}). Price close to broker average; not a pump-and-dump zone."
                else:
                    warning = f"🟢 Dump Risk: LOW – {broker_profit_pct:.1f}% above broker avg (Rs.{broker_avg_cost:.0f}). Still within normal accumulation range."
            
            # ========== 🚨 INTRADAY DISTRIBUTION DETECTION (Sunday Dump Fix) ==========
            # This detects when operators pump the open price and dump during the day
            # Example: BARUN opened at 400 (+5.4% above broker avg 379), dumped to 385, closed 390
            intraday_risk = self._calculate_intraday_distribution_risk(symbol, broker_avg_cost, ltp)
            
            # Merge intraday risk with existing risk assessment
            # If intraday detection finds higher risk, upgrade the risk level
            if intraday_risk:
                intraday_level = intraday_risk.get("risk_level", "LOW")
                intraday_penalty = intraday_risk.get("penalty", 0)
                intraday_warning = intraday_risk.get("warning", "")
                
                # Risk level hierarchy: CRITICAL > HIGH > MEDIUM > LOW
                risk_hierarchy = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
                
                if risk_hierarchy.get(intraday_level, 0) > risk_hierarchy.get(distribution_risk, 0):
                    distribution_risk = intraday_level
                    warning = intraday_warning
                    penalty = min(penalty, intraday_penalty)  # Take the more severe penalty
                    logger.info(f"   🚨 {symbol}: Intraday dump detected! Upgraded risk to {distribution_risk}")
            
            # Store in cache
            self._distribution_risk_cache[symbol] = {
                "avg_cost": round(broker_avg_cost, 2),
                "avg_cost_1w": round(broker_avg_cost_1w, 2) if broker_avg_cost_1w else None,
                "profit_pct": round(broker_profit_pct, 2),
                "risk_level": distribution_risk,
                "warning": warning,
                "penalty": penalty,
                "is_seller_dominant": is_seller_dominant,
                "seller_weight": seller_weight,
                "lookback_days": lookback_used,
                "calculation_method": calculation_method,
                # Dual timeframe analysis
                "net_holdings_1m": net_holdings_1m,
                "net_holdings_1w": net_holdings_1w,
                "distribution_divergence": distribution_divergence,
                # New intraday distribution data
                "intraday_dump_detected": intraday_risk.get("dump_detected", False) if intraday_risk else False,
                "open_price": intraday_risk.get("open_price", 0) if intraday_risk else 0,
                "open_vs_broker_pct": intraday_risk.get("open_vs_broker_pct", 0) if intraday_risk else 0,
                "close_vs_vwap_pct": intraday_risk.get("close_vs_vwap_pct", 0) if intraday_risk else 0,
                "volume_spike": intraday_risk.get("volume_spike", 0) if intraday_risk else 0,
                "today_vwap": intraday_risk.get("today_vwap", 0) if intraday_risk else 0,
            }
            
            logger.debug(f"{symbol}: Distribution Risk = {distribution_risk} (Profit: {broker_profit_pct:.1f}%, Method: {calculation_method})")
            
        except Exception as e:
            logger.debug(f"Could not calculate distribution risk for {symbol}: {e}")
    
    def _calculate_intraday_distribution_risk(self, symbol: str, broker_avg_cost: float, ltp: float) -> Optional[Dict]:
        """
        🚨 INTRADAY DISTRIBUTION DETECTION - The "Sunday Dump" Fix
        
        WHAT THIS DETECTS:
        ==================
        Operators in NEPSE often:
        1. PUMP the open price high (+5-10% above their cost)
        2. DUMP shares throughout the day on high volume
        3. Price closes BELOW VWAP (selling pressure > buying pressure)
        
        This is classic pump-and-dump that the previous logic missed because
        it only compared LTP (close) to broker_avg. By the time market closes,
        operators have already sold at the higher open/high prices!
        
        IMPORTANT: For dump detection, we always use a LONGER lookback (1M)
        because operators accumulate over weeks/months, not days. Using 1W
        would miss the dump because the avg cost would be too high.
        
        DETECTION CRITERIA:
        ===================
        Condition 1: open_price >= broker_avg * (1 + THRESHOLD_OPEN_PREMIUM)
                     → Operators pumped the open price above their cost
        
        Condition 2: volume_today >= avg_volume * THRESHOLD_VOLUME_MULTIPLIER  
                     → Unusual volume = distribution activity
        
        Condition 3: close_price < VWAP
                     → Price rejected from VWAP = net selling pressure
        
        Condition 4 (bonus): close_price < open_price
                     → Bearish candle = intraday dump confirmed
        
        RISK LEVELS:
        ============
        - CRITICAL: Open +8%+ above broker_avg AND 2+ other conditions
        - HIGH: Open +5%+ above broker_avg AND 2+ other conditions
        - MEDIUM: 2 conditions met
        - LOW: 0-1 conditions met
        
        Args:
            symbol: Stock symbol
            broker_avg_cost: Estimated broker average cost (from VWAP or broker data)
            ltp: Last traded price (close price)
            
        Returns:
            Dict with intraday distribution risk assessment, or None if data unavailable
        """
        try:
            # Fetch today's OHLCV data
            df = self._fetch_price_history_historical(symbol, days=25)
            
            if df is None or df.empty or len(df) < 2:
                return None
            
            # ========== GET LONGER-TERM BROKER AVG FOR DUMP DETECTION ==========
            # For detecting pump-and-dump, we need the operator's ACCUMULATION cost
            # which is over weeks/months, not the recent 1W avg. Use 1M data.
            actual_broker_avg = broker_avg_cost  # Fallback to passed-in value
            
            if self.sharehub_token:
                try:
                    broker_data_1m = self.sharehub.get_broker_analysis(symbol, duration="1M")
                    if broker_data_1m:
                        total_buy_amount = sum(b.buy_amount for b in broker_data_1m if b.buy_amount > 0)
                        total_buy_qty = sum(b.buy_quantity for b in broker_data_1m if b.buy_quantity > 0)
                        
                        if total_buy_qty > 0:
                            actual_broker_avg = total_buy_amount / total_buy_qty
                            logger.debug(f"{symbol}: Using 1M broker avg Rs.{actual_broker_avg:.2f} for dump detection (passed: Rs.{broker_avg_cost:.2f})")
                except Exception as e:
                    logger.debug(f"Could not get 1M broker avg for {symbol}: {e}")
            
            # Get today's data (last row)
            today = df.iloc[-1]
            high_price = float(today.get('high', 0) or 0)
            low_price = float(today.get('low', 0) or 0)
            close_price = float(today.get('close', ltp) or ltp)
            volume_today = float(today.get('volume', 0) or 0)
            
            # ========== FETCH OPEN PRICE FROM SHAREHUB (CRITICAL!) ==========
            # NEPSE API does NOT provide open price, but ShareHub does!
            # This is essential for detecting Sunday Dump where operators pump at open
            open_price = 0
            
            try:
                from data.sharehub_api import get_price_history_with_open
                sharehub_data = get_price_history_with_open(symbol, days=7)
                
                if sharehub_data and len(sharehub_data) > 0:
                    # ShareHub returns latest data first
                    today_sharehub = sharehub_data[0]
                    if today_sharehub.get("open"):
                        open_price = float(today_sharehub["open"])
                        logger.debug(f"{symbol}: Got open={open_price:.2f} from ShareHub")
            except Exception as e:
                logger.debug(f"{symbol}: Could not fetch open from ShareHub: {e}")
            
            # CRITICAL: Do NOT estimate open price - return unavailable if missing
            # Hallucinating open prices creates false distribution risk detection
            if open_price <= 0:
                logger.warning(f"{symbol}: Open price unavailable from ShareHub - skipping intraday distribution analysis")
                return {
                    "risk_level": "UNKNOWN",
                    "penalty": 0,
                    "warning": "⚠️ OPEN PRICE UNAVAILABLE - Cannot assess intraday distribution pattern",
                    "dump_detected": False,
                    "data_available": False,
                    "open_price": None,
                    "reason": "Open price not available from API. Analysis requires real intraday data."
                }
            
            if close_price <= 0 or volume_today <= 0 or high_price <= 0:
                return None
            
            # Use the longer-term broker avg for pump detection
            broker_avg_cost = actual_broker_avg
            
            # Calculate average volume (last 20 days, excluding today)
            historical = df.iloc[:-1].tail(20)
            avg_volume = historical['volume'].mean() if len(historical) > 0 else volume_today
            
            # Calculate today's VWAP (approximate using typical price)
            # VWAP = (High + Low + Close) / 3 for daily approximation
            # For more accuracy, we'd need intraday data, but this is sufficient for detection
            today_vwap = (high_price + low_price + close_price) / 3
            
            # ========== CHECK CONDITIONS ==========
            conditions_met = []
            
            # Condition 1: Open price pumped above broker cost
            open_vs_broker_pct = ((open_price - broker_avg_cost) / broker_avg_cost * 100) if broker_avg_cost > 0 else 0
            is_open_pumped = open_price >= broker_avg_cost * (1 + self.THRESHOLD_OPEN_PREMIUM)
            is_open_critical = open_price >= broker_avg_cost * (1 + self.THRESHOLD_OPEN_CRITICAL)
            
            logger.debug(f"{symbol}: Intraday check - Open={open_price:.2f}, BrokerAvg={broker_avg_cost:.2f}, OpenPremium={open_vs_broker_pct:.1f}%, IsPumped={is_open_pumped}, IsCritical={is_open_critical}")
            
            if is_open_pumped:
                conditions_met.append(f"Open pumped +{open_vs_broker_pct:.1f}% above broker avg")
            
            # Condition 2: Volume spike (unusual activity)
            volume_spike = volume_today / avg_volume if avg_volume > 0 else 1.0
            is_volume_spike = volume_spike >= self.THRESHOLD_VOLUME_MULTIPLIER
            is_volume_critical = volume_spike >= self.THRESHOLD_VOLUME_CRITICAL
            
            if is_volume_spike:
                conditions_met.append(f"Volume spike {volume_spike:.1f}x average")
            
            # Condition 3: Close below VWAP (selling pressure)
            close_vs_vwap_pct = ((close_price - today_vwap) / today_vwap * 100) if today_vwap > 0 else 0
            is_close_below_vwap = close_price < today_vwap * self.THRESHOLD_VWAP_CLOSE_RATIO
            
            if is_close_below_vwap:
                conditions_met.append(f"Close below VWAP ({close_vs_vwap_pct:.1f}%)")
            
            # Condition 4 (bonus): Bearish candle (close < open)
            is_bearish_candle = close_price < open_price
            intraday_drop_pct = ((close_price - open_price) / open_price * 100) if open_price > 0 else 0
            
            if is_bearish_candle:
                conditions_met.append(f"Bearish candle (dropped {abs(intraday_drop_pct):.1f}% intraday)")
            
            # ========== DETERMINE RISK LEVEL ==========
            num_conditions = len(conditions_met)
            
            # CRITICAL: Open spike >= 8% AND 2+ other conditions (definite pump-and-dump)
            if is_open_critical and num_conditions >= 3:
                risk_level = "CRITICAL"
                penalty = self.INTRADAY_DIST_PENALTY_CRITICAL
                warning = f"🚨 CRITICAL RISK: Intraday dump detected! Open pumped +{open_vs_broker_pct:.1f}% above broker avg, volume {volume_spike:.1f}x, close below VWAP. AVOID for momentum trading!"
                dump_detected = True
            
            # HIGH: Open spike >= 5% AND 2+ conditions (likely distribution)
            elif is_open_pumped and num_conditions >= 2:
                risk_level = "HIGH"
                penalty = self.INTRADAY_DIST_PENALTY_HIGH
                warning = f"⚠️ HIGH RISK: Distribution pattern! Open +{open_vs_broker_pct:.1f}% above broker avg with {volume_spike:.1f}x volume. Close rejected from VWAP. Proceed with extreme caution."
                dump_detected = True
            
            # MEDIUM: Volume spike + bearish candle OR close below VWAP (warning sign)
            elif num_conditions >= 2:
                risk_level = "MEDIUM"
                penalty = self.INTRADAY_DIST_PENALTY_MEDIUM
                warning = f"🟡 MODERATE RISK: Possible distribution. Conditions: {', '.join(conditions_met[:2])}. Watch for follow-through."
                dump_detected = False
            
            # LOW: Less than 2 conditions (no clear distribution signal)
            else:
                risk_level = "LOW"
                penalty = 0
                warning = ""
                dump_detected = False
            
            return {
                "risk_level": risk_level,
                "penalty": penalty,
                "warning": warning,
                "dump_detected": dump_detected,
                "conditions_met": conditions_met,
                "num_conditions": num_conditions,
                # Raw data for reporting
                "open_price": open_price,
                "close_price": close_price,
                "high_price": high_price,
                "low_price": low_price,
                "today_vwap": round(today_vwap, 2),
                "volume_today": volume_today,
                "avg_volume": round(avg_volume, 0),
                "volume_spike": round(volume_spike, 2),
                "open_vs_broker_pct": round(open_vs_broker_pct, 2),
                "close_vs_vwap_pct": round(close_vs_vwap_pct, 2),
                "intraday_drop_pct": round(intraday_drop_pct, 2),
            }
            
        except Exception as e:
            logger.debug(f"Could not calculate intraday distribution risk for {symbol}: {e}")
            return None

    def _get_nepse_5d_return(self) -> float:
        """Calculate NEPSE Index 5-day return."""
        try:
            # Get index history
            df = self.fetcher.fetch_index_history(days=10)
            if df.empty or len(df) < 5:
                return 0.0
            
            current = df.iloc[-1]['close']
            prev_5d = df.iloc[-5]['close']
            
            if prev_5d > 0:
                return ((current - prev_5d) / prev_5d) * 100
            return 0.0
        except Exception:
            return 0.0

    def _get_sector_5d_return(self, sector_name: str) -> float:
        """Calculate Sector Index 5-day return."""
        if sector_name in self._sector_performance_cache:
            return self._sector_performance_cache[sector_name]
        
        try:
            method_name = self.SECTOR_METHOD_MAP.get(sector_name)
            if not method_name:
                self._sector_performance_cache[sector_name] = 0.0
                return 0.0
            
            # Call the method dynamically from self.fetcher.nepse
            if not hasattr(self.fetcher.nepse, method_name):
                self._sector_performance_cache[sector_name] = 0.0
                return 0.0
                
            method = getattr(self.fetcher.nepse, method_name)
            data = method()
            
            # Data format is [[timestamp, value], ...]
            if not data or len(data) < 5:
                self._sector_performance_cache[sector_name] = 0.0
                return 0.0
            
            # Sort by timestamp just in case
            data.sort(key=lambda x: x[0])
            
            current = float(data[-1][1])
            prev_5d = float(data[-5][1])
            
            ret = 0.0
            if prev_5d > 0:
                ret = ((current - prev_5d) / prev_5d) * 100
                
            self._sector_performance_cache[sector_name] = ret
            return ret
            
        except Exception as e:
            logger.debug(f"Failed to fetch sector history for {sector_name}: {e}")
            self._sector_performance_cache[sector_name] = 0.0
            return 0.0

    def _calculate_sector_bonus(self, sector_name: str) -> float:
        """
        Check if sector is outperforming NEPSE over 5 days.
        Returns: +10.0 if true, else 0.0
        """
        if not sector_name:
            return 0.0
            
        sector_ret = self._get_sector_5d_return(sector_name)
        nepse_ret = self._nepse_5d_return
        
        # Bonus if Sector Return > NEPSE Return
        if sector_ret > nepse_ret:
            return 10.0
        return 0.0

    def _build_market_data_from_history(
        self,
        for_stealth_scan: bool = False,
        max_symbols: Optional[int] = None,
    ) -> List[Dict]:
        """
        🔄 UNIVERSAL FALLBACK MECHANISM: Build market data from historical price data.
        
        When market is closed, fetch_live_market() returns empty. This method
        builds a synthetic "market data" by fetching the most recent price 
        history for ALL stocks (or relevant subset).
        
        This enables FULL 4-Pillar analysis even at night!
        
        Args:
            for_stealth_scan: If True, fetches ALL sector-mapped stocks for comprehensive scan
        """
        logger.info("   🔄 Building market data from historical prices (market closed mode)...")
        logger.warning("   ⚠️ NEPSE Market Closed: Using historical closing data.")
        
        # Start with stocks that have broker activity (most relevant)
        symbols_to_check = set(self._broker_accumulation.keys())
        
        # Also add any player favorites
        for symbol in self._player_favorites.keys():
            symbols_to_check.add(symbol)
        
        # For comprehensive scans (including stealth), include ALL sector-mapped symbols
        if for_stealth_scan or not symbols_to_check:
            # Get ALL symbols from sector map for comprehensive analysis
            all_symbols = set(self._symbol_sector_map.keys())
            symbols_to_check.update(all_symbols)
            
            # Limit to 500 for performance (should cover most active stocks)
            if len(symbols_to_check) > 500:
                # Prioritize broker-active + player favorites
                priority_symbols = set(self._broker_accumulation.keys()) | set(self._player_favorites.keys())
                remaining = list(all_symbols - priority_symbols)[:500 - len(priority_symbols)]
                symbols_to_check = priority_symbols | set(remaining)
        
        # If sector filter is set, constrain fallback early to that sector only
        if self.target_sector and str(self.target_sector).lower() != "all":
            target_normalized = str(self.target_sector).lower().replace("-", " ").strip()
            filtered_symbols = set()
            for sym in symbols_to_check:
                raw_sector = str(self._symbol_sector_map.get(sym, ""))
                stock_sector_normalized = raw_sector.lower().replace("-", " ").strip()
                if stock_sector_normalized == target_normalized or (
                    "hydro" in target_normalized and "hydro" in stock_sector_normalized
                ):
                    filtered_symbols.add(sym)
            symbols_to_check = filtered_symbols

        # Optional hard limit for quick mode / compact scans
        if max_symbols and len(symbols_to_check) > max_symbols:
            symbols_to_check = set(list(symbols_to_check)[:max_symbols])

        logger.info(f"   📊 Fetching historical data for {len(symbols_to_check)} stocks...")
        
        market_data = []
        errors = 0
        
        for symbol in symbols_to_check:
            try:
                # Fetch recent price history (just need last trading day)
                df = self._fetch_price_history_historical(symbol, days=7)
                
                if df is None or df.empty:
                    continue
                
                # Get the most recent day's data
                latest = df.iloc[-1] if len(df) > 0 else None
                if latest is None:
                    continue
                
                # DEFENSIVE: Safely extract values with fallbacks
                close_price = float(latest.get("close", 0) or 0)
                volume = float(latest.get("volume", 0) or 0)
                
                # Skip invalid data
                if close_price <= 0:
                    continue
                
                # Build market data record similar to live market format
                record = {
                    "symbol": symbol,
                    "securityName": symbol,  # No full name available
                    "sectorName": self._symbol_sector_map.get(symbol, ""),
                    "lastTradedPrice": close_price,
                    "close": close_price,
                    "open": float(latest.get("open", 0) or close_price),  # Fallback to close
                    "high": float(latest.get("high", 0) or close_price),
                    "low": float(latest.get("low", 0) or close_price),
                    "volume": volume,
                    "totalTradeQuantity": volume,
                    "_from_history": True,  # Mark as historical data
                }
                
                market_data.append(record)
                
            except Exception as e:
                errors += 1
                logger.debug(f"   ⚠️ Could not fetch history for {symbol}: {e}")
                continue
        
        logger.info(f"   ✅ Built market data from {len(market_data)} stocks using historical prices")
        if errors > 0:
            logger.debug(f"   ⚠️ Skipped {errors} stocks due to fetch errors")
        return market_data
    
    def _get_active_stocks(
        self, 
        allow_historical_fallback: bool = True,
        bypass_turnover_filter: bool = False,
        for_stealth_scan: bool = False,
        quick_mode: bool = False,
    ) -> List[Dict]:
        """
        Get all actively traded stocks from NEPSE.
        
        FILTERS:
        1. Price >= MIN_PRICE (Rs. 100) - Avoid penny stocks
        2. Price <= max_price (if set) - Budget filter
        3. Turnover >= MIN_TURNOVER (Rs. 1 Crore) - Liquidity filter
        4. Strict Sector Match (if set) - Exact sector name matching
        
        FALLBACK:
        If market is closed (live data empty), uses historical price data
        from the last trading day to enable off-hours analysis.
        
        STEALTH SCAN MODE:
        If for_stealth_scan=True, turnover filter is BYPASSED because
        operators accumulate quietly on low volume.
        
        Stocks with low turnover are illiquidity traps where you
        cannot exit positions quickly without massive slippage.
        """
        try:
            market_data = self.fetcher.fetch_live_market()
            use_historical = False
            if hasattr(market_data, 'to_dict'):
                stocks = market_data.to_dict(orient='records')
            else:
                stocks = market_data if isinstance(market_data, list) else []
            
            # ========== FALLBACK: Use historical data when market is closed ==========
            if not stocks and allow_historical_fallback:
                logger.info("   ⏰ Market closed - using historical price data fallback...")
                history_cap = None
                if quick_mode and not for_stealth_scan:
                    # Keep quick scans quick when market is closed
                    history_cap = 80
                stocks = self._build_market_data_from_history(
                    for_stealth_scan=for_stealth_scan,
                    max_symbols=history_cap,
                )
                use_historical = True
                
                if stocks:
                    logger.info(f"   ✅ Loaded {len(stocks)} stocks from last trading day")
                else:
                    logger.warning("   ⚠️ No historical data available for fallback")
            
            # Store for reference
            self._using_historical_fallback = use_historical
            
            # ========== STEP 1: Price Filters (Min + Max Budget) ==========
            price_filtered = []
            budget_skipped = 0
            for s in stocks:
                ltp = float(s.get("lastTradedPrice", 0) or s.get("close", 0) or 0)
                
                # Skip penny stocks
                if ltp < self.MIN_PRICE:
                    continue
                
                # Budget filter: skip stocks above max_price
                if self.max_price and ltp > self.max_price:
                    budget_skipped += 1
                    continue
                    
                price_filtered.append(s)
            
            if self.max_price:
                logger.info(f"   💰 Budget Filter: Skipped {budget_skipped} stocks above Rs.{self.max_price:.0f}")
            
            stocks = price_filtered
            
            # ========== STEP 2: Liquidity Filter (Turnover) ==========
            # Note: For historical data, we relax the turnover requirement since
            # we're using stocks with broker activity (already pre-filtered for relevance)
            liquid_stocks = []
            min_turnover = self.MIN_TURNOVER if not use_historical else self.MIN_TURNOVER * 0.3  # 30% threshold for historical
            
            for s in stocks:
                volume = float(s.get("volume", 0) or s.get("totalTradeQuantity", 0) or 0)
                price = float(s.get("lastTradedPrice", 0) or s.get("close", 0) or 0)
                approx_turnover = volume * price
                
                s["_calculated_turnover"] = approx_turnover
                
                # STEALTH SCAN BYPASS: Operators accumulate on LOW volume
                # Skip turnover filter entirely for stealth detection
                if bypass_turnover_filter or for_stealth_scan:
                    liquid_stocks.append(s)
                elif approx_turnover >= min_turnover:
                    liquid_stocks.append(s)
            
            if bypass_turnover_filter or for_stealth_scan:
                logger.info(f"   📊 Liquidity filter BYPASSED for stealth scan: {len(stocks)} stocks")
            elif use_historical:
                logger.info(f"   📊 Liquidity filter (relaxed for historical): {len(stocks)} → {len(liquid_stocks)} stocks")
            else:
                logger.info(f"   📊 Liquidity filter: {len(stocks)} → {len(liquid_stocks)} stocks (>= Rs. 1Cr turnover)")
            
            # ========== STEP 3: Strict Sector Filter ==========
            target_sector = self.target_sector
            
            if target_sector and target_sector.lower() != "all":
                filtered_stocks = []
                
                # Normalize the target sector for strict matching
                # This fixes the "Life Insurance" vs "Non Life Insurance" collision
                target_normalized = target_sector.lower().replace("-", " ").strip()
                
                for s in liquid_stocks:
                    symbol = s.get("symbol", "")
                    # Get sector from our map (more reliable) or fallback to stock object
                    raw_sector = self._symbol_sector_map.get(symbol, s.get("sectorName", ""))
                    stock_sector_normalized = str(raw_sector).lower().replace("-", " ").strip()
                    
                    # STRICT MATCHING: Must be exact (prevents Life vs Non-Life collision)
                    if stock_sector_normalized == target_normalized:
                        filtered_stocks.append(s)
                    # Special case for Hydro variations ("Hydro Power" vs "Hydropower")
                    elif "hydro" in target_normalized and "hydro" in stock_sector_normalized:
                        filtered_stocks.append(s)
                
                logger.info(f"   🎯 Sector Filter ({target_sector}): {len(liquid_stocks)} → {len(filtered_stocks)} stocks")
                liquid_stocks = filtered_stocks
                
            return liquid_stocks
            
        except Exception as e:
            logger.error(f"Failed to get active stocks: {e}")
            return []
    
    def _score_stock(self, stock: Dict) -> ScreenedStock:
        """
        🎯 THE CORE SCORING ENGINE
        
        Evaluates a single stock through all 4 Pillars and returns
        a fully scored ScreenedStock object.
        """
        symbol = stock.get("symbol", "")
        name = stock.get("securityName", stock.get("name", ""))
        sector = self._symbol_sector_map.get(symbol, stock.get("sectorName", ""))
        ltp = float(stock.get("lastTradedPrice", 0) or stock.get("close", 0) or stock.get("ltp", 0) or 0)
        
        # CRITICAL: Skip stocks with invalid price data
        if ltp <= 0:
            logger.warning(f"⚠️ {symbol}: Invalid LTP ({ltp}), skipping analysis")
            return None
        
        # Calculate trade plan WITH SLIPPAGE (real-world NEPSE constraints)
        entry_with_slippage = ltp * (1 + self.SLIPPAGE_PERCENT)  # We buy higher
        raw_stop_loss = ltp * 0.95  # -5% target
        stop_loss_with_slippage = ltp * (0.95 - self.SLIPPAGE_PERCENT)  # Exit lower due to panic
        
        # FIX: Use slippage-adjusted entry price as primary, account for exit slippage in target
        target_with_exit_slippage = ltp * 1.10 * (1 - self.SLIPPAGE_PERCENT)  # Net after exit slippage
        
        # Initialize result with real-world trade plan
        result = ScreenedStock(
            symbol=symbol,
            name=name,
            sector=sector,
            ltp=ltp,
            entry_price=entry_with_slippage,  # FIX: Use slippage-adjusted as primary entry
            entry_price_with_slippage=entry_with_slippage,
            target_price=target_with_exit_slippage,  # FIX: Account for exit slippage
            stop_loss=raw_stop_loss,
            stop_loss_with_slippage=stop_loss_with_slippage,
            risk_reward_ratio=2.0,     # 10% gain / 5% loss (raw)
            minimum_hold_period="3 Trading Days (T+2)",
        )
        result.breakdown = ScoringBreakdown()

        # Determine max scores based on strategy
        max_broker = 30.0
        max_unlock = 20.0
        max_fund = 20.0
        max_tech = 30.0
        
        if self.strategy == "momentum":
            max_fund = 10.0  # Reduced importance
            max_tech = 40.0  # Increased importance
        
        # ===== PILLAR 1: BROKER/INSTITUTIONAL =====
        p1_score, p1_reasons = self._score_pillar1_broker(symbol, max_score=max_broker)
        result.pillar1_broker = p1_score
        result.breakdown.broker_score = p1_score
        result.breakdown.broker_reasons = p1_reasons
        
        # ===== PILLAR 2: UNLOCK RISK (WITH BOOK CLOSURE CHECK) =====
        p2_score, p2_reasons, unlock_data = self._score_pillar2_unlock(symbol, max_score=max_unlock)
        result.pillar2_unlock = p2_score
        result.breakdown.unlock_score = p2_score
        result.breakdown.unlock_reasons = p2_reasons
        result.days_until_unlock = unlock_data.get("days", 999)
        result.unlock_type = unlock_data.get("type", "None")
        result.locked_percentage = unlock_data.get("locked_pct", 0)
        
        # Check if BOOK CLOSURE warning exists in reasons
        for r in p2_reasons:
            if "Book Closure" in r:
                result.execution_warning += " | " + r if result.execution_warning else r
        
        # ===== PILLAR 3: FUNDAMENTAL SAFETY =====
        p3_score, p3_reasons, fund_data = self._score_pillar3_fundamental(symbol, ltp, max_score=max_fund)
        result.pillar3_fundamental = p3_score
        result.breakdown.fundamental_score = p3_score
        result.breakdown.fundamental_reasons = p3_reasons
        result.pe_ratio = fund_data.get("pe", 0)
        result.pbv = fund_data.get("pbv", 0)
        result.eps = fund_data.get("eps", 0)
        result.roe = fund_data.get("roe", 0)
        result.one_year_yield = fund_data.get("yield_1y", 0)

        # Hard cap fundamentals for loss-making names in momentum mode.
        if self.strategy == "momentum" and result.eps <= 0:
            if result.pillar3_fundamental > 0:
                logger.warning(
                    f"{symbol}: Momentum fundamental pillar capped to 0 due to non-positive EPS ({result.eps:.2f})"
                )
            result.pillar3_fundamental = 0.0
            result.breakdown.fundamental_score = 0.0
            if "🔴 EPS hard veto applied (pillar capped to 0)" not in result.breakdown.fundamental_reasons:
                result.breakdown.fundamental_reasons.append("🔴 EPS hard veto applied (pillar capped to 0)")
        
        # ===== PILLAR 4: TECHNICAL & MOMENTUM =====
        p4_score, p4_reasons, tech_data = self._score_pillar4_technical(symbol, stock, max_score=max_tech)
        result.pillar4_technical = p4_score
        result.breakdown.technical_score = p4_score
        result.breakdown.technical_reasons = p4_reasons
        result.rsi = tech_data.get("rsi", 0)
        result.ema_signal = tech_data.get("ema_signal", "")
        result.volume_spike = tech_data.get("volume_spike", 0)
        result.atr = tech_data.get("atr", 0)  # Store ATR for display
        result.high_52w = tech_data.get("high_52w", 0)  # Store 52-week high for display
        
        # ===== DYNAMIC TRADE PLAN WITH ATR (1:2 Risk-Reward) =====
        # Use ATR for stop loss and target if available
        atr = tech_data.get("atr", 0)
        high_52w = tech_data.get("high_52w", 0)  # For blue sky breakout
        
        # Get dynamic ATR multipliers based on market regime
        stop_mult, target_mult = self._get_dynamic_atr_multipliers()
        
        if atr and atr > 0:
            # ATR-based stop loss and target for precise R:R
            atr_stop_loss = ltp - (stop_mult * atr)
            atr_target = ltp + (target_mult * atr)
            
            # Update trade plan with ATR-based values
            result.stop_loss = atr_stop_loss
            result.stop_loss_with_slippage = atr_stop_loss * (1 - self.SLIPPAGE_PERCENT)
            result.target_price = atr_target
            
            # Calculate actual R:R ratio
            risk = ltp - result.stop_loss
            reward = result.target_price - ltp
            result.risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 2.0
            
            # Add regime-aware note to breakdown
            regime_note = " [TIGHT BEAR STOPS]" if self._market_regime == self.REGIME_BEAR else ""
            result.breakdown.bonuses.append(f"📊 ATR-based targets: Stop Rs.{atr_stop_loss:.2f}, Target Rs.{atr_target:.2f} (R:R {result.risk_reward_ratio}){regime_note}")
            
            # ===== HOLDING PERIOD CALCULATION =====
            # Expected days to target based on daily ATR movement
            # If ATR is 10 and target is 30 points away, expect ~3 days
            target_distance = result.target_price - ltp
            daily_move = atr * 0.5  # Conservative: assume 50% of ATR daily progress
            # Use minimum threshold to avoid precision issues with tiny ATR values
            if daily_move > 0.1:  # Minimum Rs.0.10 daily movement
                expected_days = max(3, min(15, int(target_distance / daily_move)))
            else:
                expected_days = 7  # Default for swing trading
            
            result.expected_holding_days = expected_days
            
            # Max holding: 2x expected or 15 days max (time-based exit rule)
            result.max_holding_days = min(15, expected_days * 2)
        
        else:
            # Default holding periods when no ATR data
            result.expected_holding_days = 7
            result.max_holding_days = 15
        
        # ===== EXIT STRATEGY TEXT =====
        result.exit_strategy = self._generate_exit_strategy(
            result.expected_holding_days, 
            result.max_holding_days,
            result.target_price,
            result.stop_loss,
            ltp
        )
        
        # Store 52-week high for blue sky check (done in Pillar 4)
        result.high_52w = high_52w
        
        # Store broker data
        pf = self._player_favorites.get(symbol, {})
        result.winner = pf.get("winner", "")
        result.buyer_dominance_pct = pf.get("winner_weight", 0) if pf.get("winner") == "Buyer" else 0
        ba = self._broker_accumulation.get(symbol, {})
        result.top3_broker_holding_pct = ba.get("top3_pct", 0)
        
        # Store DISTRIBUTION RISK data (Broker Profit-Taking Detection)
        dist_risk = self._distribution_risk_cache.get(symbol, {})
        
        # If distribution risk not in cache, calculate it on-demand
        if not dist_risk:
            logger.debug(f"Calculating distribution risk on-demand for {symbol}")
            self._calculate_distribution_risk(symbol, ltp, {}, {})
            dist_risk = self._distribution_risk_cache.get(symbol, {})
        
        if dist_risk:
            result.broker_avg_cost = dist_risk.get("avg_cost", 0)
            result.broker_avg_cost_1w = dist_risk.get("avg_cost_1w") or 0
            result.broker_profit_pct = dist_risk.get("profit_pct", 0)
            result.distribution_risk = dist_risk.get("risk_level", "N/A")
            result.distribution_warning = dist_risk.get("warning", "")
            # Dual timeframe analysis
            result.net_holdings_1m = dist_risk.get("net_holdings_1m", 0)
            result.net_holdings_1w = dist_risk.get("net_holdings_1w", 0)
            result.distribution_divergence = dist_risk.get("distribution_divergence", False)
            # New intraday distribution fields
            result.intraday_dump_detected = dist_risk.get("intraday_dump_detected", False)
            result.today_open_price = dist_risk.get("open_price", 0) if "open_price" in dist_risk else 0
            result.today_vwap = dist_risk.get("today_vwap", 0)
            result.open_vs_broker_pct = dist_risk.get("open_vs_broker_pct", 0)
            result.close_vs_vwap_pct = dist_risk.get("close_vs_vwap_pct", 0)
            result.intraday_volume_spike = dist_risk.get("volume_spike", 0)
        
        # ===== STRATEGY BONUS (Target Sector) =====
        sector_bonus = 0.0
        
        # Identify the sector
        stock_sector = self._symbol_sector_map.get(symbol, stock.get("sectorName", "")).lower()
        
        # Determine active target sector (either from CLI or strategy default)
        target_sector = self.target_sector
        
        # Legacy support: If strategy is "momentum" and NO sector is provided, user likely meant Hydro
        # But for new CLI, they should use --sector. We won't force Hydro for momentum unless it's legacy.
        # However, to keep backward compatibility:
        if self.strategy == "momentum" and not target_sector:
            # We don't default to Hydro anymore in the new CLI design,
            # UNLESS it came from the legacy --hydro flag which sets target_sector="hydro" in paper_trader.py
            pass 
            
        if target_sector and target_sector.lower() != "all":
            target_lower = target_sector.lower()
            is_match = False
            
            # Fuzzy match sector names
            if target_lower in stock_sector or stock_sector in target_lower:
                is_match = True
            # Special handling for "Hydro" spelling variations
            elif "hydro" in target_lower and "hydro" in stock_sector:
                is_match = True
                
            # 1. SECTOR MATCH BONUS (Required but NOT added to score to avoid >100)
            if is_match:
                # We do NOT add points because the filter strictly selects these stocks anyway.
                result.breakdown.bonuses.append(f"🎯 {target_sector.upper()} SECTOR MATCH (Required)")
            
        # 2. Sector Trend Bonus (Momentum) - Only if using Momentum Strategy
        # This applies whether we filtered by sector or not.
        if self.strategy == "momentum":
            # Try to fetch live sector performance if possible
            trend_bonus = self._calculate_sector_bonus(stock_sector)
            if trend_bonus > 0:
                    sector_bonus += trend_bonus
                    result.breakdown.bonuses.append(f"📈 Sector Trend Bonus: +{trend_bonus:.1f} (Outperforming Index)")


        # ===== CALCULATE BASE SCORE (4 Pillars) =====
        # Note: sector_bonus is NOT added to base_score to avoid exceeding 100/100.
        # It serves as a tie-breaker or qualitative bonus in the breakdown.
        base_score = (
            result.pillar1_broker +
            result.pillar2_unlock +
            result.pillar3_fundamental +
            result.pillar4_technical
        )
        
        # ===== 🛡️ RISK MANAGEMENT LAYER =====
        risk_penalty = 0.0
        
        # 1. DIVERGENCE PENALTY (Fake Data Detection)
        # If fundamentals look great but smart money is dumping → LIE DETECTOR
        divergence_penalty = self._check_divergence_penalty(
            result.pillar3_fundamental, 
            result.pillar1_broker,
            symbol
        )
        if divergence_penalty < 0:
            risk_penalty += divergence_penalty
            result.breakdown.penalties.append(
                f"🔴 DIVERGENCE ALERT: Great financials but Smart Money selling ({divergence_penalty})"
            )
        
        # 2. CASH DIVIDEND FOCUS (Fake Profit Detection)
        # High EPS but no dividends for 3 years = potential accounting fraud
        dividend_adjustment = self._check_dividend_reality(symbol, result.pillar3_fundamental)
        if dividend_adjustment != 0:
            risk_penalty += dividend_adjustment
            if dividend_adjustment < 0:
                result.breakdown.penalties.append(
                    f"⚠️ NO CASH DIVIDENDS: High EPS but no payout in 3 years ({dividend_adjustment})"
                )
            else:
                result.breakdown.bonuses.append(
                    f"💰 DIVIDEND PAYER: Consistent cash returns (+{dividend_adjustment})"
                )
        
        # ===== OVERRIDE LAYER: Apply Real-World Constraints =====
        
        # 3. Market Regime Penalty (Bear Market = -15 to ALL stocks)
        result.is_bear_market = self._is_bear_market
        if self._is_bear_market:
            result.market_regime_penalty = self.BEAR_MARKET_PENALTY
            result.breakdown.penalties.append(f"🐻 Bear Market Penalty: {self.BEAR_MARKET_PENALTY} (Index < 50-day EMA)")
        else:
            result.market_regime_penalty = 0.0
        
        # 4. Calculate Final Score (including risk penalties)
        result.total_score = base_score + result.market_regime_penalty + risk_penalty
        
        # ========== 🚨 MANIPULATION DETECTION (Pillar 6) ==========
        # Run advanced operator manipulation detection
        manipulation_penalty = 0.0
        if MANIPULATION_DETECTOR_AVAILABLE:
            try:
                detector = ManipulationDetector()
                manip_report = detector.analyze_stock(symbol)
                
                # Store manipulation data in result
                result.manipulation_risk_score = manip_report.overall_risk_score
                result.manipulation_severity = manip_report.overall_severity.value
                result.operator_phase = manip_report.operator_phase
                result.operator_phase_description = manip_report.operator_phase_description
                result.manipulation_alerts = manip_report.alerts
                result.manipulation_veto_reasons = manip_report.veto_reasons
                result.is_safe_to_trade = manip_report.is_safe_to_trade
                
                # Store detailed metrics
                result.broker_concentration_hhi = manip_report.broker_concentration.hhi_index
                result.top3_broker_control_pct = manip_report.broker_concentration.top3_concentration
                result.circular_trading_pct = manip_report.circular_trading.circular_percentage
                result.wash_trading_detected = manip_report.wash_trading.detected
                result.lockup_days_remaining = manip_report.lockup_risk.days_until_unlock
                
                # Apply manipulation penalty based on severity
                # -50 for CRITICAL, -30 for HIGH, -15 for MEDIUM, 0 for LOW/NONE
                if manip_report.overall_severity.value == "CRITICAL":
                    manipulation_penalty = -50.0
                    result.breakdown.penalties.append(
                        f"🚨 CRITICAL MANIPULATION: Score -{abs(manipulation_penalty):.0f} | {', '.join(manip_report.veto_reasons[:2])}"
                    )
                elif manip_report.overall_severity.value == "HIGH":
                    manipulation_penalty = -30.0
                    result.breakdown.penalties.append(
                        f"⚠️ HIGH MANIPULATION RISK: Score -{abs(manipulation_penalty):.0f} | {', '.join(manip_report.veto_reasons[:2])}"
                    )
                elif manip_report.overall_severity.value == "MEDIUM":
                    manipulation_penalty = -15.0
                    result.breakdown.penalties.append(
                        f"⚡ MEDIUM MANIPULATION RISK: Score -{abs(manipulation_penalty):.0f}"
                    )
                
                # Add operator phase to bonuses/penalties
                if manip_report.pump_dump.phase.value == "ACCUMULATION":
                    result.breakdown.bonuses.append(f"✅ ACCUMULATION PHASE: Operators buying (Early entry opportunity)")
                elif manip_report.pump_dump.phase.value == "DISTRIBUTION":
                    result.breakdown.penalties.append(f"🚨 DISTRIBUTION PHASE: Operators exiting - AVOID")
                elif manip_report.pump_dump.phase.value == "PUMP":
                    result.breakdown.penalties.append(f"⚠️ PUMP PHASE: Late entry risk")
                    
            except Exception as e:
                logger.warning(f"Manipulation detection error for {symbol}: {e}")
        
        # Apply manipulation penalty to total score
        result.total_score += manipulation_penalty
        
        # ========== 🚨 MOMENTUM SCORE CAP FOR INTRADAY DISTRIBUTION ==========
        # If intraday dump detected (Sunday Dump pattern), cap the momentum score
        # This prevents recommending "RISKY - trade with tight stop" for stocks being dumped
        dist_risk = self._distribution_risk_cache.get(symbol, {})
        if self.strategy == "momentum" and dist_risk.get("intraday_dump_detected", False):
            risk_level = dist_risk.get("risk_level", "LOW")
            
            if risk_level == "CRITICAL":
                # CRITICAL: Cap at 35, force NOT RECOMMENDED
                old_score = result.total_score
                result.total_score = min(result.total_score, self.MOMENTUM_CAP_CRITICAL)
                if old_score > self.MOMENTUM_CAP_CRITICAL:
                    logger.warning(f"   🚨 {symbol}: Momentum score capped {old_score:.0f}→{result.total_score:.0f} (CRITICAL intraday dump)")
                result.verdict_reason = f"🔴 NOT RECOMMENDED ({result.total_score:.0f}/100) | Distribution in progress"
                
            elif risk_level == "HIGH":
                # HIGH: Cap at 45, force WEAK
                old_score = result.total_score
                result.total_score = min(result.total_score, self.MOMENTUM_CAP_HIGH)
                if old_score > self.MOMENTUM_CAP_HIGH:
                    logger.warning(f"   ⚠️ {symbol}: Momentum score capped {old_score:.0f}→{result.total_score:.0f} (HIGH intraday dump)")
                result.verdict_reason = f"🔴 WEAK ({result.total_score:.0f}/100) | High distribution risk"
        
        # Store uncapped score for sorting
        result.raw_score = result.total_score
        
        # Cap at 0-100
        result.total_score = max(0, min(100, result.total_score))
        
        # 3. T+2 Warning for volatile stocks
        if result.rsi > 70 or result.volume_spike > 3.0:
            result.execution_warning = "⚠️ HIGH VOLATILITY: Cannot be panic-sold tomorrow due to T+2!"
        else:
            result.execution_warning = "ℹ️ Standard T+2 settlement applies"
        
        # Generate verdict reason
        result.verdict_reason = self._generate_verdict(result)
        
        return result
    
    def _score_pillar1_broker(self, symbol: str, max_score: float = 30.0) -> Tuple[float, List[str]]:
        """
        PILLAR 1: BROKER/INSTITUTIONAL ACCUMULATION (30 points max)
        
        SCORING RULES (PROPORTIONAL):
        - Buyer dominance: Proportional (e.g. 75% -> ~11 pts)
        - Top 3 brokers: Proportional (e.g. 60% -> ~9 pts)
        - Seller dominance: Proportional Penalty
        - No data: 10 points (neutral)
        """
        score = 10.0  # Base score (neutral)
        reasons = []
        
        # === Player Favorites (Buyer/Seller dominance) ===
        pf = self._player_favorites.get(symbol, {})
        
        if pf:
            winner = pf.get("winner", "")
            weight = pf.get("winner_weight", 0)
            
            if winner == "Buyer":
                # PROPORTIONAL SCORING: (weight / 100) * 15.0
                # Example: 85% dominance = 0.85 * 15 = 12.75 points
                dominance_score = (weight / 100.0) * 15.0
                score += dominance_score
                reasons.append(f"🟢 Buyer dominance: {weight:.1f}% (+{dominance_score:.1f})")
            
            elif winner == "Seller":
                # PROPORTIONAL PENALTY: (weight / 100) * 20.0
                # Example: 60% seller = 0.60 * 20 = -12 points
                penalty = (weight / 100.0) * 20.0
                score -= penalty
                reasons.append(f"🔴 Seller dominance: {weight:.1f}% (-{penalty:.1f} PENALTY)")
        else:
            reasons.append("⚪ No player favorite data")
        
        # === Broker Accumulation (Top 3 concentration) ===
        ba = self._broker_accumulation.get(symbol, {})
        
        if ba:
            top3_pct = ba.get("top3_pct", 0)
            
            # PROPORTIONAL SCORING: (top3_pct / 100.0) * 15.0
            # Example: 50% = 0.5 * 15 = 7.5 points
            # If top3_pct is very low (<10), minimal points added.
            if top3_pct > 0:
                concentration_score = (top3_pct / 100.0) * 15.0
                score += concentration_score
                reasons.append(f"🏦 Top 3 holdings: {top3_pct:.1f}% (+{concentration_score:.1f})")
        
        # === DISTRIBUTION RISK (Broker Profit-Taking Detection) ===
        dist_risk = self._distribution_risk_cache.get(symbol, {})
        if dist_risk:
            risk_level = dist_risk.get("risk_level", "LOW")
            penalty = dist_risk.get("penalty", 0)
            profit_pct = dist_risk.get("profit_pct", 0)
            close_vs_vwap_pct = float(dist_risk.get("close_vs_vwap_pct", 0) or 0)
            open_vs_broker_pct = float(dist_risk.get("open_vs_broker_pct", 0) or 0)
            
            if penalty < 0:
                score += penalty  # Negative penalty reduces score
                reasons.append(f"📉 Distribution Risk ({risk_level}): Brokers +{profit_pct:.1f}% ({penalty:.0f})")
            elif risk_level == "LOW" and profit_pct < 5:
                # Small bonus for stocks where brokers are still accumulating
                bonus = 3.0
                score += bonus
                reasons.append(f"📈 Accumulation Phase: Brokers only +{profit_pct:.1f}% (+{bonus:.0f})")

            # VWAP rejection penalty: open pump + close below VWAP is a broker-distribution red flag.
            if open_vs_broker_pct >= 5 and close_vs_vwap_pct < 0:
                score -= 3.0
                reasons.append("🔴 VWAP rejection after open pump (-3.0)")
        
        # Cap at max_score (floor at -20 for extreme distribution cases)
        score = max(-20, min(max_score, score))
        return score, reasons
    
    def _score_pillar2_unlock(self, symbol: str, max_score: float = 20.0) -> Tuple[float, List[str], Dict]:
        """
        PILLAR 2: UNLOCK RISK AVOIDANCE & BOOK CLOSURE (20 points max, or -50 PENALTY!)
        
        SCORING RULES:
        - No unlock risk: +20 points (SAFE!)
        - Unlock > 60 days: +15 points
        - Unlock 30-60 days: +5 points (WARNING)
        - Unlock < 30 days: -50 points (INSTANT REJECT!)
        - Mutual Fund unlock: Extra -10 penalty (they WILL sell!)
        
        NEW TRAP AVOIDANCE:
        - Book Closure in < 7 days: -20 penalty + CRITICAL WARNING
        """
        score = 20.0  # Start with max (assume safe)
        reasons = []
        unlock_data = {"days": 999, "type": "None", "locked_pct": 0}
        
        # --- 1. PROMOTER/MUTUAL FUND UNLOCK ---
        unlock = self._unlock_risks.get(symbol, {})
        
        if unlock:
            days = unlock.get("days", 999)
            unlock_type = unlock.get("type", "Unknown")
            locked_pct = unlock.get("locked_pct", 0)
            is_mf = unlock.get("is_mf", False)
            
            unlock_data = {
                "days": days,
                "type": unlock_type,
                "locked_pct": locked_pct,
            }
            
            if days <= self.UNLOCK_DANGER_DAYS:
                # 🚨 INSTANT REJECT - Unlock within 30 days!
                score = -50  # MASSIVE PENALTY
                reasons.append(f"🚨 DANGER! {unlock_type} unlock in {days} days! (-50 REJECT!)")
                reasons.append(f"   → {locked_pct:.2f}% shares will flood market!")
                
                if is_mf:
                    score -= 10  # Extra penalty for MF
                    reasons.append(f"   → Mutual Fund = WILL sell for profits! (-10 extra)")
            
            elif days <= self.UNLOCK_WARNING_DAYS:
                # ⚠️ WARNING - Unlock within 60 days
                score = 5
                reasons.append(f"⚠️ WARNING: {unlock_type} unlock in {days} days (+5)")
                reasons.append(f"   → Monitor closely, {locked_pct:.2f}% locked")
                
                if is_mf:
                    score -= 5
                    reasons.append(f"   → Mutual Fund involved (-5)")
            
            else:
                # Unlock is > 60 days away, relatively safe
                score = 15
                reasons.append(f"🟡 {unlock_type} unlock in {days} days (+15)")
                reasons.append(f"   → Still safe to hold, {locked_pct:.2f}% locked")
        else:
            reasons.append("✅ NO unlock risk detected (+20 SAFE)")
        
        # --- 2. BOOK CLOSURE TRAP (Dividend Adjustment) ---
        try:
            # Fetch latest dividend to check for book closure
            dividends = self.sharehub.get_dividend_history(symbol, limit=1)
            if dividends:
                last_div = dividends[0]
                if last_div.book_closure_date:
                    # Parse date: "2024-03-25" (ISO format)
                    bc_date_str = str(last_div.book_closure_date).split("T")[0]
                    bc_date = datetime.strptime(bc_date_str, "%Y-%m-%d").date()
                    today = datetime.now().date()
                    
                    days_to_bc = (bc_date - today).days
                    
                    if 0 <= days_to_bc <= 7:
                        # 🚨 DANGER ZONE: Price will drop in < 7 days!
                        score -= 20
                        reasons.append(f"🚨 DANGER: Book Closure in {days_to_bc} days! Price will adjust downwards. DO NOT BUY. (-20)")
                    elif 7 < days_to_bc <= 15:
                         score -= 5
                         reasons.append(f"⚠️ Upcoming Book Closure in {days_to_bc} days. Be careful. (-5)")

        except Exception as e:
            logger.debug(f"Book closure check failed for {symbol}: {e}")
            
        
        # Cap score: Allow controlled negative for dangerous unlocks, but floor at -50
        # This prevents extreme negative scores from corrupting total_score
        score = max(-50, min(max_score, score))
        return score, reasons, unlock_data
    
    def _score_pillar3_fundamental(
        self, symbol: str, ltp: float, max_score: float = 20.0
    ) -> Tuple[float, List[str], Dict]:
        """
        PILLAR 3: FUNDAMENTAL SAFETY (20 points max)
        
        SCORING RULES (NEPSE-SPECIFIC):
        - PE Ratio < 15: +8 points (cheap!)
        - PE Ratio 15-20: +5 points (fair value)
        - PE Ratio 20-35: 0 points (expensive for NEPSE)
        - PE Ratio > 35: -10 penalty (NEPSE is NOT US market!)
        
        - Book Value < 0: -10 INSTANT PENALTY (INSOLVENT!)
        - PBV < 2: +6 points (undervalued)
        - PBV 2-3: +3 points (fair)
        - PBV > 5: -5 penalty
        
        - ROE > 15%: +6 points (efficient)
        - ROE 10-15%: +3 points
        - ROE < 5%: -3 penalty
        """
        score = 10.0  # Base score
        reasons = []
        fund_data = {"pe": 0, "pbv": 0, "eps": 0, "roe": 0, "yield_1y": 0}
        
        try:
            fundamentals = self.sharehub.get_fundamentals(symbol)
            
            if not fundamentals:
                reasons.append("⚪ No fundamental data available")
                # Cap at max_score
                score = max(0, min(max_score, score))
                return score, reasons, fund_data
            
            # Extract metrics
            # CRITICAL: Calculate PE from EPS and current LTP (not pre-set)
            eps = fundamentals.eps_annualized or fundamentals.eps or 0
            pe = fundamentals.calculate_pe(ltp) if eps != 0 else 0  # Allow negative EPS
            roe = fundamentals.roe or 0
            book_value = fundamentals.book_value or 0
            
            # === CRITICAL: Negative Book Value Check (Insolvent Companies!) ===
            # NEPSE has many junk Hydropower companies with negative book values
            if book_value < 0:
                score -= 10  # INSTANT PENALTY
                reasons.append(f"🔴 Negative Book Value: Rs. {book_value:.2f} (INSOLVENT -10)")
                # Still calculate other metrics but company is fundamentally broken
            
            # FIX #3: PBV logic - Use None for invalid book values, don't set to 0
            # Setting to 0 makes it look like the stock has zero price-to-book
            if book_value > 0:
                pbv = ltp / book_value
            else:
                pbv = None  # Invalid book value, can't calculate PBV
            
            fund_data = {
                "pe": pe,
                "pbv": pbv,
                "eps": eps,
                "roe": roe,
                "book_value": book_value,
                "yield_1y": 0,
            }
            
            # === EARNINGS MOMENTUM (QoQ Growth) ===
            # Currently ShareHub API returns standardized EPS. 
            # If we can infer growth, we apply momentum logic.
            # Ideally we would compare EPS with previous quarter.
            # For now, we check if EPS is growing annually if available or simple check.
            
            # Note: A more robust implementation would fetch previous report.
            # Here we apply a simple logic: If EPS is declining year over year
            eps_annualized = getattr(fundamentals, 'eps_annualized', 0)
            if eps_annualized < eps and eps > 0:
                 # If annualized is significantly lower than current, it might indicate a drop
                 # This is a heuristic until we fetch full history
                 pass 
            
            # Explicit Momentum Check if 'growth' field exists (future proofing)
            # if getattr(fundamentals, 'eps_growth', 0) < 0:
            #    score -= 5
            #    reasons.append("📉 Declining Earnings Momentum (-5)")

            # === PE Ratio Scoring (NEPSE-SPECIFIC THRESHOLDS!) ===
            # Nepal market is NOT the US market - PE > 35 is expensive here!
            # CRITICAL FIX: PE = 0 or negative means INVALID data (loss-making or missing)
            if pe > 0:
                if pe < 15:
                    score += 8
                    reasons.append(f"💰 PE {pe:.1f} is CHEAP (+8)")
                elif pe <= 20:
                    score += 5
                    reasons.append(f"✅ PE {pe:.1f} is fair value (+5)")
                elif pe <= 35:
                    reasons.append(f"⚪ PE {pe:.1f} is expensive for NEPSE (0)")
                else:
                    # PE > 35 is OVERVALUED for Nepal market!
                    if self.strategy == "momentum":
                        score -= 5
                        reasons.append(f"🔴 PE {pe:.1f} is HIGH but allowed in Momentum trend (-5)")
                    else:
                        score -= 10
                        reasons.append(f"🔴 PE {pe:.1f} is OVERVALUED for NEPSE (-10)")
            elif pe == 0:
                # PE = 0 means MISSING or LOSS-MAKING company (EPS <= 0)
                score -= 3
                reasons.append("❌ PE ratio = 0 (missing data or negative earnings) (-3)")
            else:  # pe < 0
                # Negative PE means company is loss-making
                score -= 5
                reasons.append(f"🔴 Negative PE {pe:.1f} (company making losses) (-5)")
            
            # === PBV Scoring (only if book value is positive) ===
            # FIX #3: Handle None PBV properly
            if pbv is not None and pbv > 0:
                if pbv < 2:
                    score += 6
                    reasons.append(f"💰 PBV {pbv:.2f} is undervalued (+6)")
                elif pbv <= 3:
                    score += 3
                    reasons.append(f"✅ PBV {pbv:.2f} is fair (+3)")
                elif pbv > 5:
                    score -= 5
                    reasons.append(f"🔴 PBV {pbv:.2f} is expensive (-5)")
            elif book_value <= 0:
                reasons.append(f"⚠️ Cannot calculate PBV (negative book value)")
            
            # === ROE Scoring ===
            if roe > 0:
                if roe >= 15:
                    score += 6
                    reasons.append(f"📈 ROE {roe:.1f}% is excellent (+6)")
                elif roe >= 10:
                    score += 3
                    reasons.append(f"✅ ROE {roe:.1f}% is good (+3)")
            elif roe < 0:
                score -= 5
                reasons.append(f"🔴 Negative ROE: {roe:.1f}% (losing money! -5)")
            elif 0 <= roe < 5:
                score -= 3
                reasons.append(f"⚠️ ROE {roe:.1f}% is weak (-3)")
            
            # === EPS Check ===
            if eps < 0:
                score -= 5
                reasons.append(f"🔴 Negative EPS: Rs. {eps:.2f} (-5)")
            elif eps > 20:
                score += 2
                reasons.append(f"✅ Strong EPS: Rs. {eps:.2f} (+2)")
            
        except Exception as e:
            logger.debug(f"Fundamental scoring error for {symbol}: {e}")
            reasons.append("⚪ Error fetching fundamentals")
        
        # Cap at 0-max_score (can go negative due to penalties, but min 0)
        score = max(0, min(max_score, score))
        return score, reasons, fund_data
    
    def _score_pillar4_technical(
        self, symbol: str, stock: Dict, max_score: float = 30.0
    ) -> Tuple[float, List[str], Dict]:
        """
        PILLAR 4: TECHNICAL & MOMENTUM (30 points max)
        
        Uses REAL pandas-ta calculations on historical OHLCV data:
        
        SCORING RULES:
        - EMA9 > EMA21 (Bullish): +10 points
        - Golden Cross recent: +5 bonus
        - RSI 50-65 (optimal): +8 points
        - RSI 30-40 (oversold bounce): +6 points
        - Volume > 1.5x avg: +7 points
        - Volume > 2x avg: +10 points
        - ADX > 25 (strong trend): +5 points
        - Blue Sky Breakout (within 5% of 52-week high): +5 points
        
        PENALTIES:
        - RSI > 70 (overbought): -5
        - EMA9 < EMA21 (bearish): -5
        """
        score = 15.0  # Base score
        reasons = []
        ltp = float(stock.get("lastTradedPrice", 0) or stock.get("close", 0) or 0)
        tech_data = {"rsi": 0, "ema_signal": "NEUTRAL", "volume_spike": 0, "atr": 0, "high_52w": 0}
        
        try:
            # Fetch 365-day price history (1 year) for accurate 52-week High & Long-term Trends
            # We need enough data for EMA200 and true Blue Sky Breakouts
            df = self._fetch_historical_safe(symbol, days=400, min_rows=21)
            
            if df is None or len(df) < 21:
                # Fallback to basic scoring from current data
                return self._score_technical_fallback(symbol, stock, max_score=max_score)
            
            # Calculate indicators using pandas-ta
            indicators = TechnicalIndicators(df)
            indicators.add_ema()
            indicators.add_rsi()
            indicators.add_macd()
            indicators.add_volume_indicators()
            indicators.add_adx()
            indicators.add_atr()  # Add ATR for dynamic targets
            indicators.detect_golden_cross()
            indicators.add_rsi()
            indicators.add_macd()
            indicators.add_volume_indicators()
            indicators.add_adx()
            indicators.detect_golden_cross()
            
            df = indicators.df
            if len(df) == 0:
                return self._score_technical_fallback(symbol, stock, max_score=max_score)
            
            latest = df.iloc[-1]
            
            # === EMA Crossover ===
            ema_short = settings.ema_short
            ema_long = settings.ema_long
            
            ema9 = latest.get(f"ema_{ema_short}")
            ema21 = latest.get(f"ema_{ema_long}")
            
            # --- 1. FALLING KNIFE PROTECTOR (Macro Downtrend) ---
            # Calculate EMA 200
            if "ema_200" not in df.columns:
                # Add EMA 200 if missing (TechnicalIndicators might not add it by default)
                try:
                   import pandas_ta as ta
                   df["ema_200"] = ta.ema(df["close"], length=200)
                except:
                   pass
            
            latest_full = df.iloc[-1]
            ema200 = latest_full.get("ema_200")
            
            if pd.notna(ema200):
                if ltp < ema200:
                    score -= 10
                    reasons.append(f"🔴 Macro Downtrend: Price {ltp} below 200-day EMA {ema200:.1f} (-10)")
                else:
                    score += 5
                    reasons.append(f"🟢 Macro Uptrend: Price above 200-day EMA (+5)")

            if pd.notna(ema9) and pd.notna(ema21):
                if ema9 > ema21:
                    score += 10
                    tech_data["ema_signal"] = "BULLISH"
                    reasons.append(f"📈 EMA{ema_short} > EMA{ema_long} (Bullish +10)")
                    
                    # Bonus for recent golden cross
                    if latest.get("golden_cross_recent", False):
                        score += 5
                        reasons.append("🌟 Recent Golden Cross! (+5)")
                else:
                    score -= 5
                    tech_data["ema_signal"] = "BEARISH"
                    reasons.append(f"📉 EMA{ema_short} < EMA{ema_long} (Bearish -5)")
            
            # === RSI (GRANULAR) ===
            rsi = latest.get(f"rsi_{settings.rsi_period}")
            if pd.notna(rsi):
                tech_data["rsi"] = rsi
                
                # Granular scoring: Ideal is 60. Max 10 pts.
                # rsi_score = 10 - abs(60 - rsi) * 0.2
                # But penalize OVERBOUGHT (>75) heavily
                
                if rsi > 70:
                    overbought_penalty = min(10.0, 5.0 + max(0.0, (rsi - 70.0) * 0.25))
                    score -= overbought_penalty
                    reasons.append(f"🔴 RSI {rsi:.1f} OVERBOUGHT (-{overbought_penalty:.1f})")
                else:
                    rsi_score = max(0.0, 10.0 - abs(60.0 - rsi) * 0.2)
                    score += rsi_score
                    reasons.append(f"✅ RSI {rsi:.1f} (+{rsi_score:.1f})")

            # === Volume Spike (GRANULAR) ===
            vol_spike = latest.get("volume_spike")
            if pd.notna(vol_spike):
                tech_data["volume_spike"] = vol_spike
                
                # Granular scoring: base + spike * 2.0
                if vol_spike < 0.5:
                    score -= 3.0
                    reasons.append(f"⚠️ Low volume {vol_spike:.1f}x (-3.0)")
                else:
                    # Capped at 10.0 max addition
                    vol_score = min(10.0, vol_spike * 3.0) 
                    score += vol_score
                    reasons.append(f"📊 Volume {vol_spike:.1f}x (+{vol_score:.1f})")
            
            # === ADX (Trend Strength) ===
            adx = latest.get("adx")
            if pd.notna(adx):
                # Granular ADX: (adx / 10.0) -> if 30 -> +3.0
                if adx > 20:
                    adx_score = min(5.0, adx * 0.15)
                    score += adx_score
                    reasons.append(f"💪 ADX {adx:.1f} trend (+{adx_score:.1f})")
                else:
                    score -= 2.0
                    reasons.append(f"⚪ ADX {adx:.1f} weak trend (-2.0)")
            
            # === MACD ===
            macd_hist = latest.get("macd_histogram")
            if pd.notna(macd_hist):
                if macd_hist > 0:
                    score += 3
                    if len(df) > 1:
                        prev_hist = df.iloc[-2].get("macd_histogram", 0)
                        if pd.notna(prev_hist) and macd_hist > prev_hist:
                            score += 2
                            reasons.append("MACD histogram positive & rising (+5)")
                        else:
                            reasons.append("MACD histogram positive (+3)")
                else:
                    score -= 2
                    reasons.append("MACD histogram negative (-2)")
            
            # === ATR (Average True Range) for dynamic targets ===
            atr = latest.get("atr_14") if "atr_14" in df.columns else latest.get("atr")
            if pd.notna(atr) and atr > 0:
                tech_data["atr"] = float(atr)
            
            # === BLUE SKY BREAKOUT (52-week high proximity) ===
            # If price is within 5% of 52-week high = No overhead resistance!
            if "high" in df.columns:
                # Use available history as proxy (ideally 250 days)
                high_52w = df["high"].max()
                tech_data["high_52w"] = float(high_52w) if pd.notna(high_52w) else 0
                
                if high_52w and high_52w > 0 and ltp >= (0.95 * high_52w):
                    score += 5
                    pct_from_high = ((ltp / high_52w) - 1) * 100
                    reasons.append(f"🚀 Blue Sky Breakout! {pct_from_high:+.1f}% from high (no resistance +5)")
            
        except Exception as e:
            logger.debug(f"Technical scoring error for {symbol}: {e}")
            return self._score_technical_fallback(symbol, stock, max_score=max_score)
        
        # Cap at max_score with PROPORTIONAL SCALING
        # The raw score can naturally reach ~50 with bonuses.
        # We scale it down so the "perfect" stock gets exactly max_score.
        raw_tech_score = score
        
        # Scale: 50 raw points = 100% of max_score
        scaled_score = (raw_tech_score / 50.0) * max_score
        
        # Final cap
        score = max(0, min(max_score, scaled_score))
        return score, reasons, tech_data
    
    def _score_technical_fallback(
        self, symbol: str, stock: Dict, max_score: float = 30.0
    ) -> Tuple[float, List[str], Dict]:
        """
        Fallback technical scoring when OHLCV history unavailable.
        
        IMPORTANT: Base score is 5.0 (not 15.0!) to penalize stocks
        that lack proper price history. Missing data = RISK!
        """
        score = 5.0  # LOW base score - missing data is a penalty!
        reasons = ["⚠️ Missing price history - cannot perform full technical analysis (-10 penalty)"]
        tech_data = {"rsi": 0, "ema_signal": "UNKNOWN", "volume_spike": 0, "atr": 0, "high_52w": 0}
        
        # Use current day's volume as only available proxy
        volume = float(stock.get("totalTradeQuantity", 0) or stock.get("volume", 0) or 0)
        
        if volume > 100000:
            score += 5
            reasons.append(f"High volume: {volume:,} (+5)")
        elif volume > 50000:
            score += 3
            reasons.append(f"Moderate volume: {volume:,} (+3)")
        elif volume < 10000:
            score -= 3
            reasons.append(f"⚠️ Low volume: {volume:,} (-3)")
        
        # Cap at max_score
        score = max(0, min(max_score, score))
        return score, reasons, tech_data
    
    def _check_divergence_penalty(
        self, 
        fundamental_score: float, 
        broker_score: float,
        symbol: str
    ) -> float:
        """
        🔍 DIVERGENCE PENALTY: Detect potential fake/manipulated financial reports.
        
        LOGIC: If a company has incredible fundamentals (high score) but
        smart money is secretly dumping (low broker score), the financials
        might be fabricated or the insiders know something bad.
        
        Example: EPS looks great on paper, but big brokers are selling hard.
        
        Returns:
            Negative penalty if divergence detected, 0 otherwise
        """
        # Only apply if fundamentals look "too good" but broker flow is terrible
        if (fundamental_score >= self.DIVERGENCE_THRESHOLD_HIGH_FUND and 
            broker_score <= self.DIVERGENCE_THRESHOLD_LOW_BROKER):
            
            logger.warning(f"   ⚠️ {symbol}: DIVERGENCE DETECTED - Great financials ({fundamental_score:.1f}) but Smart Money dumping ({broker_score:.1f})")
            return self.DIVERGENCE_PENALTY  # -15 penalty
        
        return 0.0
    
    def _check_dividend_reality(self, symbol: str, fundamental_score: float) -> float:
        """
        💰 CASH DIVIDEND FOCUS: Detect potential fake profits.
        
        LOGIC: A company can fake its EPS on paper, but it cannot fake
        a cash dividend deposited directly into shareholders' bank accounts.
        
        RULES:
        1. If high fundamental score but NO dividends in 3 years → PENALTY
        2. If consistent dividend payer → BONUS
        
        Returns:
            Negative penalty or positive bonus
        """
        try:
            # Check cache first
            if symbol in self._dividend_history_cache:
                dividends = self._dividend_history_cache[symbol]
            else:
                # Fetch last 5 years of dividends
                dividends = self.sharehub.get_dividend_history(symbol, limit=5)
                self._dividend_history_cache[symbol] = dividends
            
            # Count cash dividends (not just bonus shares)
            cash_dividend_years = 0
            if dividends:
                for div in dividends:
                    # Check if it's a cash dividend (not just bonus)
                    if hasattr(div, 'cash_dividend') and div.cash_dividend > 0:
                        cash_dividend_years += 1
                    elif hasattr(div, 'dividend_type') and 'cash' in str(div.dividend_type).lower():
                        cash_dividend_years += 1
                    elif hasattr(div, 'total_dividend') and div.total_dividend > 0:
                        # At least some form of dividend
                        cash_dividend_years += 1
            
            # HIGH EPS but NO dividends for 3+ years = suspicious
            if fundamental_score >= 15.0 and cash_dividend_years == 0:
                logger.debug(f"   ⚠️ {symbol}: High fundamentals but NO dividends in history - potential fake profits")
                return self.NO_DIVIDEND_PENALTY  # -5 penalty
            
            # Consistent dividend payer (3+ years) = BONUS
            if cash_dividend_years >= 3:
                logger.debug(f"   💰 {symbol}: Consistent dividend payer ({cash_dividend_years} years) - cash is real")
                return self.DIVIDEND_BONUS  # +3 bonus
            
        except Exception as e:
            logger.debug(f"Dividend check failed for {symbol}: {e}")
        
        return 0.0
    
    def _get_dynamic_atr_multipliers(self) -> Tuple[float, float]:
        """
        📊 DYNAMIC ATR MULTIPLIERS: Adjust risk based on market regime.
        
        BULL MARKET: Wider stops, bigger targets (let winners run)
        BEAR MARKET: Tighter stops, conservative targets (cut losses fast)
        
        Returns:
            Tuple of (stop_multiplier, target_multiplier)
        """
        if self._market_regime == self.REGIME_BEAR:
            return self.ATR_STOP_MULTIPLIER_BEAR, self.ATR_TARGET_MULTIPLIER_BEAR
        else:
            return self.ATR_STOP_MULTIPLIER, self.ATR_TARGET_MULTIPLIER
    
    def _generate_verdict(self, stock: ScreenedStock) -> str:
        """Generate a human-readable verdict explaining the score."""
        parts = []
        
        # Total score assessment
        if stock.total_score >= 80:
            parts.append(f"🏆 EXCELLENT ({stock.total_score:.0f}/100)")
        elif stock.total_score >= 70:
            parts.append(f"✅ GOOD ({stock.total_score:.0f}/100)")
        elif stock.total_score >= 60:
            parts.append(f"🟡 FAIR ({stock.total_score:.0f}/100)")
        else:
            parts.append(f"⚠️ WEAK ({stock.total_score:.0f}/100)")
        
        # Key highlights
        highlights = []
        
        # Check for Critical Warnings first
        if "Book Closure" in stock.execution_warning:
            highlights.append("⚠️ DIVIDEND TRAP AVOIDED")
            
        if stock.buyer_dominance_pct >= 55:
            highlights.append(f"Buyer dominance {stock.buyer_dominance_pct:.0f}%")
        
        if stock.top3_broker_holding_pct >= 50:
            highlights.append(f"Top 3 hold {stock.top3_broker_holding_pct:.0f}%")
        
        if stock.pe_ratio > 0 and stock.pe_ratio < 25:
            highlights.append(f"PE {stock.pe_ratio:.1f}")
        
        if stock.days_until_unlock < 30:
            highlights.append(f"⚠️ UNLOCK in {stock.days_until_unlock}d!")
        
        if stock.ema_signal == "BULLISH":
            highlights.append("Bullish EMA")
        
        if highlights:
            parts.append(" | " + " + ".join(highlights))
        
        return "".join(parts)

    def dual_timeframe_validation(self, stock_data) -> Dict:
        """
        Dual-timeframe hard-veto validation for momentum entries.

        Rules:
        1) 1M baseline must show net accumulation (>0)
        2) 1W fine-tune must not show net distribution when 1M is accumulating
        3) Hard veto if RSI > 70, EPS <= 0, ROE <= 0
        4) Hard veto on heavy dump day or >10% premium vs 14D VWAP
        """
        symbol = getattr(stock_data, "symbol", "") or ""
        ltp = float(getattr(stock_data, "ltp", 0) or 0)
        net_1m = int(getattr(stock_data, "net_holdings_1m", 0) or 0)
        net_1w = int(getattr(stock_data, "net_holdings_1w", 0) or 0)
        rsi = float(getattr(stock_data, "rsi", 0) or 0)
        eps = float(getattr(stock_data, "eps", 0) or 0)
        roe = float(getattr(stock_data, "roe", 0) or 0)
        intraday_dump = bool(getattr(stock_data, "intraday_dump_detected", False))
        open_vs_broker_pct = float(getattr(stock_data, "open_vs_broker_pct", 0) or 0)
        close_vs_vwap_pct = float(getattr(stock_data, "close_vs_vwap_pct", 0) or 0)

        veto_reasons: List[str] = []

        # Rule 1: 1M baseline trend
        if net_1m <= 0:
            veto_reasons.append(f"No 1M accumulation ({net_1m:+,} shares)")

        # Rule 2: 1W fine-tune
        if net_1m > 0 and net_1w <= 0:
            veto_reasons.append(f"1W distribution against 1M trend ({net_1w:+,} shares)")

        # Hard veto: momentum/fundamentals
        if rsi > 70:
            veto_reasons.append(f"RSI overbought ({rsi:.1f})")
        if eps <= 0:
            veto_reasons.append(f"Negative EPS (Rs. {eps:.2f})")
        if roe <= 0:
            veto_reasons.append(f"Weak/Negative ROE ({roe:.1f}%)")

        # Hard veto: heavy dump day
        if intraday_dump or (open_vs_broker_pct >= 5.0 and close_vs_vwap_pct < 0):
            veto_reasons.append("Heavy dump day pattern (open spike + close<VWAP)")

        # Hard veto: >10% premium vs 14D VWAP
        vwap_14d = None
        vwap_premium_pct = 0.0
        if symbol and ltp > 0:
            try:
                hist = self._fetch_historical_safe(symbol, days=20, min_rows=5)
                if not hist.empty:
                    vwap_14d = safe_vwap(hist.tail(14))
                    if vwap_14d and vwap_14d > 0:
                        vwap_premium_pct = ((ltp / vwap_14d) - 1) * 100
                        if vwap_premium_pct > 10:
                            veto_reasons.append(f"VWAP premium too high (+{vwap_premium_pct:.1f}%)")
                    else:
                        veto_reasons.append("14D VWAP unavailable")
            except Exception as e:
                logger.warning(f"{symbol}: dual timeframe VWAP validation failed: {e}")
                veto_reasons.append("14D VWAP unavailable")

        return {
            "status": "PASS" if not veto_reasons else "VETOED",
            "veto_reasons": veto_reasons,
            "1m_net": net_1m,
            "1w_net": net_1w,
            "vwap_14d": round(vwap_14d, 2) if vwap_14d else 0.0,
            "vwap_premium_pct": round(vwap_premium_pct, 2),
        }
    
    def _get_recommendation(self, score: float) -> str:
        """Get recommendation based on total score."""
        if score >= 80:
            return "🟢 STRONG BUY"
        elif score >= 70:
            return "🟢 BUY"
        elif score >= 60:
            return "🟡 HOLD/ACCUMULATE"
        elif score >= 50:
            return "🟠 WEAK - MONITOR"
        else:
            return "🔴 AVOID"


    def _calculate_sector_bonus(self, sector_name: str) -> float:
        """
        Calculate bonus based on sector performance.
        1. +10 if sector is up > 2% today (Immediate Trend)
        2. +10 if sector is outperforming NEPSE over 5 days (Hydro Strategy)
        """
        if not sector_name:
            return 0.0
            
        # 1. Check 1-day trend (Immediate Momentum)
        trend_1d = self._sector_trend_cache.get(sector_name, 0.0)
        
        # Fuzzy match if needed
        if trend_1d == 0.0:
            for k, v in self._sector_trend_cache.items():
                if k.lower() in sector_name.lower() or sector_name.lower() in k.lower():
                    trend_1d = v
                    break
        
        if trend_1d > 2.0:
            return 10.0
            
        # 2. Check 5-day trend (Hydro Strategy - Sector Rotation)
        if self.strategy == "hydro":
             s_ret = self._get_sector_5d_return(sector_name)
             # Bonus if sector is outperforming NEPSE
             if s_ret > self._nepse_5d_return:
                 return 10.0

        return 0.0

    def _generate_exit_strategy(
        self, 
        expected_days: int, 
        max_days: int, 
        target: float, 
        stop: float,
        entry: float
    ) -> str:
        """
        Generate clear exit instructions for the trader.
        
        This tells the user exactly when and how to exit:
        1. Target hit → Sell at target price
        2. Stop loss hit → Cut loss immediately
        3. Time-based exit → If neither hit in max_days, review and decide
        """
        # FIX: Guard against zero entry price
        if entry <= 0:
            return "❌ Invalid entry price - cannot generate exit rules"
        target_gain_pct = ((target / entry) - 1) * 100
        stop_loss_pct = (1 - (stop / entry)) * 100
        
        exit_text = f"""📅 HOLD: {expected_days}-{max_days} trading days
✅ EXIT RULE 1: SELL at Rs.{target:.0f} (Target +{target_gain_pct:.1f}%)
❌ EXIT RULE 2: SELL at Rs.{stop:.0f} (Stop -{stop_loss_pct:.1f}%)
⏰ EXIT RULE 3: After {max_days} days, REVIEW position - if neither target nor stop hit, consider partial exit"""
        
        return exit_text

    def get_rejected_stocks(self, limit: int = 10) -> List[Dict]:
        """
        Get stocks that were REJECTED due to unlock risk or heavy penalties.
        
        Useful for debugging and understanding why stocks were excluded.
        """
        logger.info("🔍 Finding rejected stocks...")
        
        # Pre-load if not already done
        if not self._unlock_risks:
            self._preload_market_data()
        
        rejected = []
        
        # Check stocks with imminent unlock
        for symbol, unlock in self._unlock_risks.items():
            days = unlock.get("days", 999)
            if days <= self.UNLOCK_DANGER_DAYS:
                rejected.append({
                    "symbol": symbol,
                    "reason": f"🚨 {unlock.get('type')} unlock in {days} days!",
                    "days_until": days,
                    "unlock_type": unlock.get("type"),
                    "locked_pct": unlock.get("locked_pct", 0),
                    "penalty": -50 if unlock.get("is_mf") else -40,
                })
        
        # Sort by days until unlock
        rejected.sort(key=lambda x: x.get("days_until", 999))
        
        return rejected[:limit]


def get_best_stocks(
    min_score: float = 65,
    top_n: int = 5,
    with_news: bool = False,
    with_ai: bool = False,
    quick_mode: bool = False,
    headless: bool = True,
) -> List[Dict]:
    """
    🎯 MAIN ENTRY POINT: Get the best stocks to invest in RIGHT NOW.
    
    This runs the full 4-Pillar analysis and returns the top stocks
    with detailed scoring breakdown.
    
    Args:
        min_score: Minimum score threshold (default 65)
        top_n: Number of top stocks to return
        with_news: Enable Playwright news scraping (slower but adds news sentiment)
        with_ai: Enable OpenAI AI verdict (requires OPENAI_API_KEY)
        quick_mode: Use quick mode (top 50 by volume only - 5x faster)
        headless: Run browser invisibly (True) or visibly (False) if with_news is True
    
    Returns:
        List of stock dictionaries with full analysis
    """
    screener = MasterStockScreener()
    results = screener.run_full_analysis(min_score=min_score, top_n=top_n, quick_mode=quick_mode)
    
    # Enrich top picks with news and AI analysis if requested
    if with_news or with_ai:
        results = screener.enrich_with_news_and_ai(
            stocks=results,
            scrape_news=with_news,
            use_ai=with_ai,
            headless=headless,
        )
    
    return [stock.to_dict() for stock in results]


def get_best_stocks_with_full_analysis(min_score: float = 65, top_n: int = 5) -> List[Dict]:
    """
    🎯🤖📰 FULL ANALYSIS: Get best stocks with NEWS SCRAPING + AI VERDICT
    
    This is the ULTIMATE analysis that includes:
    1. 4-Pillar Quantitative Scoring (Broker, Unlock, Fundamental, Technical)
    2. Playwright browser scraping for recent news
    3. OpenAI GPT analysis for human-readable verdict
    
    WARNING: This is slower due to browser automation and API calls.
    Use this for final decision-making, not real-time scanning.
    
    Returns:
        List of fully enriched stock dictionaries
    """
    return get_best_stocks(
        min_score=min_score,
        top_n=top_n,
        with_news=True,
        with_ai=True,
        quick_mode=True,  # Use quick mode for speed
    )


def get_rejected_stocks(limit: int = 10) -> List[Dict]:
    """Get stocks rejected due to unlock risk."""
    screener = MasterStockScreener()
    return screener.get_rejected_stocks(limit=limit)


if __name__ == "__main__":
    # Quick test
    print("🎯 Running Master Stock Screener...")
    stocks = get_best_stocks(min_score=60, top_n=5)
    
    for stock in stocks:
        print(f"\n{'='*60}")
        print(f"#{stocks.index(stock)+1} {stock['symbol']} - {stock['total_score']}/100")
        print(f"Verdict: {stock['verdict_reason']}")
        print(f"Pillar Scores: {stock['pillar_scores']}")
