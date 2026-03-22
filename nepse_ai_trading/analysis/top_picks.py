"""
🎯 TOP PICKS ANALYZER - The Millionaire Stock Scanner

This module scans ALL NEPSE stocks and identifies the TOP investment opportunities
based on comprehensive analysis of:

1. TECHNICAL ANALYSIS (40% weight)
   - EMA crossover (9 > 21)
   - RSI in optimal range (50-65)
   - Volume breakout (> 1.5x 20-day avg)
   - ShareHub technical ratings

2. FUNDAMENTAL ANALYSIS (35% weight)
   - PE Ratio (lower is better, < 20 preferred)
   - PB Ratio (< 2.5 preferred)
   - ROE (> 12% preferred)
   - EPS growth
   - Dividend history

3. MOMENTUM ANALYSIS (15% weight)
   - 7-day return
   - 30-day return
   - 52-week return
   - Near 52-week low (value opportunity)

4. BROKER/INSTITUTIONAL ACTIVITY (10% weight)
   - Large transaction volume
   - Institutional accumulation signals

USAGE:
======
    from analysis.top_picks import TopPicksAnalyzer

    analyzer = TopPicksAnalyzer()
    
    # Get top 5 investment picks
    picks = analyzer.get_top_picks(top_n=5)
    
    for pick in picks:
        print(f"{pick['rank']}. {pick['symbol']} - Score: {pick['total_score']}")
        print(f"   Recommendation: {pick['recommendation']}")
        print(f"   Entry: Rs. {pick['entry_price']}, Target: Rs. {pick['target_price']}")
"""

import time
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from loguru import logger
import pandas as pd

from data.fetcher import NepseFetcher
from data.sharehub_api import ShareHubAPI
from analysis.fundamentals import FundamentalAnalyzer
from analysis.indicators import TechnicalIndicators
from core.config import settings


@dataclass
class StockPick:
    """Represents a stock pick with all analysis scores."""
    rank: int
    symbol: str
    name: str
    sector: str
    
    # Current price data
    ltp: float
    change_pct: float
    volume: int
    
    # Technical scores (0-100)
    technical_score: float = 0.0
    ta_signal: str = "NEUTRAL"  # BUY, SELL, NEUTRAL
    
    # Fundamental scores (0-100)
    fundamental_score: float = 0.0
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    roe: float = 0.0
    eps: float = 0.0
    
    # Momentum scores (0-100)
    momentum_score: float = 0.0
    return_7d: float = 0.0
    return_30d: float = 0.0
    return_52w: float = 0.0
    
    # Broker activity score (0-100)
    broker_score: float = 0.0
    broker_accumulation_pct: float = 0.0  # % held by top 3 brokers
    
    # Combined
    total_score: float = 0.0
    recommendation: str = ""  # STRONG BUY, BUY, HOLD, AVOID
    
    # Trading targets
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    
    # Risk/Reward
    risk_reward_ratio: float = 0.0
    
    # Reasons
    buy_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "rank": self.rank,
            "symbol": self.symbol,
            "name": self.name,
            "sector": self.sector,
            "ltp": self.ltp,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "total_score": round(self.total_score, 1),
            "technical_score": round(self.technical_score, 1),
            "fundamental_score": round(self.fundamental_score, 1),
            "momentum_score": round(self.momentum_score, 1),
            "broker_score": round(self.broker_score, 1),
            "broker_accumulation_pct": round(self.broker_accumulation_pct, 1),
            "ta_signal": self.ta_signal,
            "recommendation": self.recommendation,
            "pe_ratio": round(self.pe_ratio, 2),
            "pb_ratio": round(self.pb_ratio, 2),
            "roe": round(self.roe, 2),
            "eps": round(self.eps, 2),
            "return_7d": round(self.return_7d, 2),
            "return_30d": round(self.return_30d, 2),
            "return_52w": round(self.return_52w, 2),
            "entry_price": round(self.entry_price, 2),
            "target_price": round(self.target_price, 2),
            "stop_loss": round(self.stop_loss, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "buy_reasons": self.buy_reasons,
            "risk_factors": self.risk_factors,
        }


class TopPicksAnalyzer:
    """
    The Millionaire Stock Scanner.
    
    Scans all NEPSE stocks and identifies top investment opportunities.
    
    🎯 KEY INSIGHT: When big brokers accumulate >50% of recent trades,
    it signals institutional buying = potential price rise!
    """
    
    # Weight distribution (adjusted to include broker accumulation)
    WEIGHT_TECHNICAL = 0.35
    WEIGHT_FUNDAMENTAL = 0.30
    WEIGHT_MOMENTUM = 0.15
    WEIGHT_BROKER = 0.20  # Increased for broker accumulation data!
    
    # Minimum criteria
    MIN_PRICE = 100  # Avoid penny stocks
    MIN_VOLUME = 1000  # Minimum daily volume
    
    def __init__(self, sharehub_token: str = None):
        """
        Initialize analyzer.
        
        Args:
            sharehub_token: ShareHub auth token for broker analysis
                           (Set SHAREHUB_AUTH_TOKEN env var)
        """
        import os
        
        self.fetcher = NepseFetcher()
        self.sharehub_token = sharehub_token or os.getenv("SHAREHUB_AUTH_TOKEN")
        self.sharehub = ShareHubAPI(auth_token=self.sharehub_token)
        self.fundamental_analyzer = FundamentalAnalyzer()
        
        # Cache for analysis
        self._stock_cache: Dict[str, Dict] = {}
        
        # Cache broker accumulation data (reduces API calls)
        self._broker_accumulation: Dict[str, Dict] = {}
        
        # Cache promoter unlock risk (CRITICAL for avoiding bad stocks!)
        self._promoter_unlock_risk: Dict[str, Dict] = {}
        
        # Cache player favorites (buyer/seller dominance)
        self._player_favorites: Dict[str, Dict] = {}
    
    def get_top_picks(
        self,
        top_n: int = 5,
        sectors: List[str] = None,
        min_price: float = None,
        max_pe: float = 30,
        include_analysis: bool = True,
        include_broker_accumulation: bool = True,
        avoid_promoter_unlock: bool = True,
        use_player_favorites: bool = True,
    ) -> List[StockPick]:
        """
        Get top N stock picks based on comprehensive analysis.
        
        Args:
            top_n: Number of top picks to return
            sectors: Filter by sectors (None = all)
            min_price: Minimum stock price
            max_pe: Maximum PE ratio to consider
            include_analysis: Whether to include detailed analysis
            include_broker_accumulation: Use broker accumulation data (requires auth token)
            avoid_promoter_unlock: Filter out stocks with upcoming promoter unlock
            use_player_favorites: Use player favorite data (buyer/seller dominance)
        
        Returns:
            List of StockPick objects ranked by total score
        """
        logger.info(f"🔍 Starting Top Picks Analysis (top {top_n})...")
        start_time = time.time()
        
        min_price = min_price or self.MIN_PRICE
        
        # Step 0a: Fetch broker accumulation data if auth token available
        if include_broker_accumulation and self.sharehub_token:
            self._load_broker_accumulation_data()
        
        # Step 0b: Load promoter unlock risk data
        if avoid_promoter_unlock:
            self._load_promoter_unlock_risk()
        
        # Step 0c: Load player favorites (no auth required!)
        if use_player_favorites:
            self._load_player_favorites()
        
        # Step 1: Get all tradeable stocks
        stocks = self._get_active_stocks()
        logger.info(f"Found {len(stocks)} active stocks")
        
        # Step 2: Apply initial filters
        filtered = self._apply_initial_filters(stocks, min_price, sectors)
        logger.info(f"After initial filters: {len(filtered)} stocks")
        
        # Step 3: Analyze each stock
        analyzed = []
        for i, stock in enumerate(filtered):
            symbol = stock.get("symbol", "")
            try:
                pick = self._analyze_stock(stock)
                if pick and pick.total_score > 40:  # Only include decent scores
                    if max_pe == 0 or pick.pe_ratio == 0 or pick.pe_ratio <= max_pe:
                        analyzed.append(pick)
                
                # Progress logging
                if (i + 1) % 20 == 0:
                    logger.info(f"Analyzed {i + 1}/{len(filtered)} stocks...")
                    
            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue
        
        # Step 4: Sort by total score
        analyzed.sort(key=lambda x: x.total_score, reverse=True)
        
        # Step 5: Assign ranks and get top N
        top_picks = []
        for rank, pick in enumerate(analyzed[:top_n], 1):
            pick.rank = rank
            pick.recommendation = self._get_recommendation(pick.total_score)
            top_picks.append(pick)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Analysis complete in {elapsed:.1f}s. Found {len(top_picks)} top picks.")
        
        return top_picks
    
    def _load_broker_accumulation_data(self):
        """
        🎯 MILLIONAIRE INSIGHT: Pre-load broker accumulation data.
        
        Stocks where top 3 brokers hold >50% of trades = institutional buying!
        """
        try:
            logger.info("📊 Fetching broker accumulation data...")
            
            # Get 1-day accumulation data
            holdings = self.sharehub.get_broker_aggressive_holdings(duration="1D")
            
            for h in holdings:
                symbol = h.get("symbol", "")
                if symbol:
                    self._broker_accumulation[symbol] = {
                        "top_three_holding_pct": h.get("topThreeBrokersHoldingPercentage", 0),
                        "total_involved_brokers": h.get("totalInvolvedBrokers", 0),
                        "hold_quantity": h.get("holdQuantity", 0),
                        "public_trade_pct": h.get("publicTradePercentage", 0),
                        "top_brokers": h.get("topBrokers", []),
                        "ltp": h.get("ltp", 0),
                        "change_pct": h.get("changePercentage", 0),
                    }
            
            logger.info(f"✅ Loaded accumulation data for {len(self._broker_accumulation)} stocks")
            
        except Exception as e:
            logger.warning(f"Could not load broker accumulation: {e}")

    def _load_promoter_unlock_risk(self):
        """
        🔴 CRITICAL: Load promoter unlock schedule.
        
        Stocks with upcoming promoter unlock are RISKY because:
        - Promoters often sell to cash out
        - Increased supply → price drops
        - Smart traders AVOID these stocks!
        
        NOW INCLUDES BOTH:
        - Mutual Fund unlocks (type=1) - HIGH sell probability!
        - Promoter unlocks (type=2) - Medium sell probability
        """
        try:
            logger.info("📅 Fetching ALL unlock schedules (MF + Promoter)...")
            
            # Get both types of unlocks
            for lock_type in [1, 2]:
                type_name = "MutualFund" if lock_type == 1 else "Promoter"
                unlocks = self.sharehub.get_promoter_unlock_data(lock_type=lock_type)
                
                for u in unlocks:
                    if u.symbol and u.remaining_days > 0:  # Only future unlocks
                        # If stock already has risk, accumulate
                        existing = self._promoter_unlock_risk.get(u.symbol, {})
                        existing_score = existing.get("risk_score", 0)
                        
                        self._promoter_unlock_risk[u.symbol] = {
                            "remaining_days": min(
                                u.remaining_days, 
                                existing.get("remaining_days", 999)
                            ),
                            "locked_shares": u.locked_shares + existing.get("locked_shares", 0),
                            "locked_percentage": u.locked_percentage + existing.get("locked_percentage", 0),
                            "unlock_date": str(u.lock_in_end_date) if u.lock_in_end_date else existing.get("unlock_date"),
                            "risk_level": u.unlock_risk_level,
                            "risk_score": u.risk_score + existing_score,  # Accumulate risk!
                            "type": f"{existing.get('type', '')}+{type_name}" if existing else type_name,
                            "is_mutual_fund": u.is_mutual_fund or existing.get("is_mutual_fund", False),
                        }
            
            # Count risky stocks
            risky_30d = sum(1 for v in self._promoter_unlock_risk.values() 
                          if v.get("remaining_days", 999) <= 30)
            mf_count = sum(1 for v in self._promoter_unlock_risk.values()
                         if v.get("is_mutual_fund", False))
            
            logger.info(f"✅ Loaded unlock data for {len(self._promoter_unlock_risk)} stocks")
            logger.info(f"   ⚠️  {risky_30d} stocks have unlock within 30 days")
            logger.info(f"   💰 {mf_count} involve Mutual Fund (HIGH sell probability)")
            
        except Exception as e:
            logger.warning(f"Could not load unlock data: {e}")

    def _load_player_favorites(self):
        """
        🎯 MILLIONAIRE INSIGHT: Load player favorites (buyer/seller dominance).
        
        This is FREE data (no auth needed!) showing:
        - Which stocks have heavy BUYER activity (bullish!)
        - Which stocks have SELLER dominance (avoid!)
        
        TRADING RULES:
        • winnerWeight > 60% BUYER → Strong institutional buying → BIG BONUS
        • winnerWeight > 55% BUYER → Moderate buying → Small bonus
        • winnerWeight > 55% SELLER → Sellers dominating → PENALTY
        """
        try:
            logger.info("🎯 Fetching player favorites (buyer/seller dominance)...")
            
            favorites = self.sharehub.get_player_favorites()
            
            for f in favorites:
                symbol = f.get("symbol", "")
                if symbol:
                    winner = f.get("winner", "")
                    weight = f.get("winnerWeight", 0)
                    
                    self._player_favorites[symbol] = {
                        "winner": winner,
                        "winner_weight": weight,
                        "buy_amount": f.get("buyAmount", 0),
                        "sell_amount": f.get("sellAmount", 0),
                        "buy_quantity": f.get("buyQuantity", 0),
                        "sell_quantity": f.get("sellQuantity", 0),
                        "buy_transactions": f.get("buyTransactions", 0),
                        "sell_transactions": f.get("sellTransactions", 0),
                        # Calculated bonus/penalty
                        "score_modifier": self._calculate_player_fav_modifier(winner, weight),
                    }
            
            # Stats
            buyer_dominated = sum(1 for v in self._player_favorites.values() 
                                 if v.get("winner") == "Buyer" and v.get("winner_weight", 0) > 55)
            seller_dominated = sum(1 for v in self._player_favorites.values()
                                  if v.get("winner") == "Seller" and v.get("winner_weight", 0) > 55)
            
            logger.info(f"✅ Loaded player favorites for {len(self._player_favorites)} stocks")
            logger.info(f"   🟢 {buyer_dominated} stocks with buyer dominance (bullish)")
            logger.info(f"   🔴 {seller_dominated} stocks with seller dominance (avoid)")
            
        except Exception as e:
            logger.warning(f"Could not load player favorites: {e}")
    
    def _calculate_player_fav_modifier(self, winner: str, weight: float) -> float:
        """
        Calculate score modifier based on buyer/seller dominance.
        
        Returns:
            Positive value = bonus (buyers dominating)
            Negative value = penalty (sellers dominating)
        """
        if not winner or weight < 52:
            return 0  # No clear winner
        
        if winner == "Buyer":
            # Buyers dominating = bullish signal
            if weight >= 65:
                return 15  # Very strong buyer activity
            elif weight >= 60:
                return 10  # Strong buyer activity
            elif weight >= 55:
                return 5   # Moderate buyer activity
            else:
                return 2   # Slight buyer edge
        else:
            # Sellers dominating = bearish signal
            if weight >= 65:
                return -15  # Heavy selling pressure
            elif weight >= 60:
                return -10  # Strong selling
            elif weight >= 55:
                return -5   # Moderate selling
            else:
                return -2   # Slight seller edge
    
    def _get_active_stocks(self) -> List[Dict]:
        """Get all actively traded stocks."""
        try:
            # Get live market data
            market_data = self.fetcher.fetch_live_market()
            
            # Handle DataFrame
            if hasattr(market_data, 'to_dict'):
                # It's a DataFrame, convert to list of dicts
                return market_data.to_dict(orient='records')
            elif isinstance(market_data, list) and len(market_data) > 0:
                return market_data
            
            # Fallback to company list
            companies = self.fetcher.fetch_company_list()
            if hasattr(companies, 'to_dict'):
                return companies.to_dict(orient='records')
            return companies
            
        except Exception as e:
            logger.error(f"Failed to get active stocks: {e}")
            companies = self.fetcher.fetch_company_list()
            if hasattr(companies, 'to_dict'):
                return companies.to_dict(orient='records')
            return companies
    
    def _apply_initial_filters(
        self,
        stocks: List[Dict],
        min_price: float,
        sectors: List[str] = None
    ) -> List[Dict]:
        """Apply initial filters to reduce analysis scope."""
        filtered = []
        
        for stock in stocks:
            try:
                symbol = stock.get("symbol", "")
                
                # Get price - handle multiple possible column names
                ltp = float(
                    stock.get("lastTradedPrice") or 
                    stock.get("ltp") or 
                    stock.get("close") or 
                    stock.get("closePrice") or 0
                )
                
                # Price filter
                if ltp < min_price:
                    continue
                
                # Volume filter - handle multiple possible column names
                volume = int(
                    stock.get("totalTradeQuantity") or 
                    stock.get("volume") or 
                    stock.get("tradedQuantity") or 0
                )
                if volume < self.MIN_VOLUME:
                    continue
                
                # Sector filter
                if sectors:
                    sector = stock.get("sectorName", "") or stock.get("sector", "")
                    if not any(s.lower() in sector.lower() for s in sectors):
                        continue
                
                # 🔴 PROMOTER UNLOCK FILTER - Avoid risky stocks!
                if symbol in self._promoter_unlock_risk:
                    unlock_data = self._promoter_unlock_risk[symbol]
                    remaining_days = unlock_data.get("remaining_days", 999)
                    
                    # Skip stocks unlocking within 14 days (HIGH RISK)
                    if remaining_days <= 14:
                        logger.debug(f"⚠️ Skipping {symbol}: Promoter unlock in {remaining_days} days")
                        continue
                
                filtered.append(stock)
                
            except Exception:
                continue
        
        return filtered
    
    def _analyze_stock(self, stock: Dict) -> Optional[StockPick]:
        """Perform comprehensive analysis on a single stock."""
        symbol = stock.get("symbol", "")
        if not symbol:
            return None
        
        # Basic info - handle multiple column name formats
        ltp = float(
            stock.get("lastTradedPrice") or 
            stock.get("ltp") or 
            stock.get("close") or 0
        )
        
        pick = StockPick(
            rank=0,
            symbol=symbol,
            name=stock.get("securityName") or stock.get("companyName") or symbol,
            sector=stock.get("sectorName") or stock.get("sector") or "",
            ltp=ltp,
            change_pct=float(stock.get("percentageChange") or stock.get("change_pct") or 0),
            volume=int(stock.get("totalTradeQuantity") or stock.get("volume") or 0),
        )
        
        if pick.ltp <= 0:
            return None
        
        # 1. Technical Analysis Score
        pick.technical_score, pick.ta_signal = self._calculate_technical_score(symbol)
        
        # 2. Fundamental Analysis Score
        fund_result = self._calculate_fundamental_score(symbol, pick.ltp)
        pick.fundamental_score = fund_result["score"]
        pick.pe_ratio = fund_result["pe"]
        pick.pb_ratio = fund_result["pb"]
        pick.roe = fund_result["roe"]
        pick.eps = fund_result["eps"]
        pick.buy_reasons.extend(fund_result.get("reasons", []))
        pick.risk_factors.extend(fund_result.get("risks", []))
        
        # 3. Momentum Score
        mom_result = self._calculate_momentum_score(symbol)
        pick.momentum_score = mom_result["score"]
        pick.return_7d = mom_result["7d"]
        pick.return_30d = mom_result["30d"]
        pick.return_52w = mom_result["52w"]
        pick.buy_reasons.extend(mom_result.get("reasons", []))
        
        # 4. Broker Activity Score (NOW WITH ACCUMULATION DATA!)
        broker_result = self._calculate_broker_score(stock)
        pick.broker_score = broker_result["score"]
        pick.buy_reasons.extend(broker_result.get("reasons", []))
        
        # Calculate total weighted score
        pick.total_score = (
            pick.technical_score * self.WEIGHT_TECHNICAL +
            pick.fundamental_score * self.WEIGHT_FUNDAMENTAL +
            pick.momentum_score * self.WEIGHT_MOMENTUM +
            pick.broker_score * self.WEIGHT_BROKER
        )
        
        # Calculate trading targets
        pick.entry_price = pick.ltp
        pick.target_price = pick.ltp * 1.10  # 10% target
        pick.stop_loss = pick.ltp * 0.95  # 5% stop loss
        
        # Risk/Reward ratio
        potential_gain = pick.target_price - pick.entry_price
        potential_loss = pick.entry_price - pick.stop_loss
        if potential_loss > 0:
            pick.risk_reward_ratio = potential_gain / potential_loss
        
        return pick
    
    def _calculate_technical_score(self, symbol: str) -> Tuple[float, str]:
        """
        🔥 REAL Technical Analysis using pandas-ta!
        
        Calculates indicators from ACTUAL price history:
        1. EMA 9/21 Crossover (Golden Cross detection)
        2. RSI 14 (Momentum check: 50-65 = bullish)
        3. MACD histogram (Positive = bullish momentum)
        4. Volume spike (>1.5x avg = institutional interest)
        5. ADX (>25 = strong trend)
        
        Also uses ShareHub's pre-computed ratings as SECONDARY confirmation.
        """
        score = 50.0  # Base score
        signal = "NEUTRAL"
        reasons = []
        
        try:
            # === STEP 1: Fetch historical OHLCV data ===
            df = self.fetcher.fetch_price_history(symbol, days=60)  # 60 days for indicators
            
            if df is None or len(df) < 21:  # Need at least 21 days for EMA 21
                # Fallback to ShareHub ratings only
                return self._calculate_technical_score_fallback(symbol)
            
            # === STEP 2: Calculate indicators using pandas-ta ===
            indicators = TechnicalIndicators(df)
            indicators.add_all_indicators()
            indicators.detect_golden_cross()
            
            df = indicators.df
            latest = df.iloc[-1]  # Most recent day
            
            # === SCORING BASED ON REAL INDICATORS ===
            
            # 1. EMA Crossover (Golden Cross) - 20 points max
            ema_short = settings.ema_short  # 9
            ema_long = settings.ema_long    # 21
            
            if f"ema_{ema_short}" in df.columns and f"ema_{ema_long}" in df.columns:
                short_ema = latest[f"ema_{ema_short}"]
                long_ema = latest[f"ema_{ema_long}"]
                
                if pd.notna(short_ema) and pd.notna(long_ema):
                    if short_ema > long_ema:
                        # Short EMA above Long EMA = BULLISH
                        score += 15
                        reasons.append(f"EMA{ema_short} > EMA{ema_long} (Bullish)")
                        
                        # Extra bonus for recent Golden Cross
                        if latest.get("golden_cross_recent", False):
                            score += 10
                            reasons.append("🌟 Recent Golden Cross!")
                            signal = "BUY"
                    else:
                        score -= 10
                        reasons.append(f"EMA{ema_short} < EMA{ema_long} (Bearish)")
            
            # 2. RSI (14) - 15 points max
            rsi_col = f"rsi_{settings.rsi_period}"
            if rsi_col in df.columns:
                rsi = latest[rsi_col]
                if pd.notna(rsi):
                    if 50 <= rsi <= 65:
                        score += 15  # Optimal bullish zone
                        reasons.append(f"RSI {rsi:.1f} (Optimal 50-65)")
                    elif 40 <= rsi < 50:
                        score += 5   # Building momentum
                    elif 30 <= rsi < 40:
                        score += 10  # Oversold, potential bounce
                        reasons.append(f"RSI {rsi:.1f} (Oversold bounce)")
                    elif rsi > 70:
                        score -= 10  # Overbought
                        reasons.append(f"RSI {rsi:.1f} (Overbought - risky)")
                    elif rsi < 30:
                        score -= 5   # Very oversold, may continue falling
            
            # 3. MACD Histogram - 15 points max
            if "macd_histogram" in df.columns:
                macd_hist = latest["macd_histogram"]
                if pd.notna(macd_hist):
                    if macd_hist > 0:
                        score += 10
                        # Check if histogram is increasing (momentum building)
                        prev_hist = df.iloc[-2]["macd_histogram"] if len(df) > 1 else 0
                        if pd.notna(prev_hist) and macd_hist > prev_hist:
                            score += 5
                            reasons.append("MACD histogram positive & rising")
                        else:
                            reasons.append("MACD histogram positive")
                    else:
                        score -= 5
            
            # 4. Volume Spike - 15 points max
            if "volume_spike" in df.columns:
                vol_spike = latest["volume_spike"]
                if pd.notna(vol_spike):
                    if vol_spike >= 2.0:
                        score += 15  # Volume 2x+ avg = big institutional interest!
                        reasons.append(f"🔥 Volume {vol_spike:.1f}x avg (Big Interest!)")
                    elif vol_spike >= 1.5:
                        score += 10  # Standard filter passed
                        reasons.append(f"Volume {vol_spike:.1f}x avg")
                    elif vol_spike >= 1.0:
                        score += 5
                    elif vol_spike < 0.5:
                        score -= 5  # Very low volume
            
            # 5. ADX (Trend Strength) - 10 points max
            if "adx" in df.columns:
                adx = latest["adx"]
                if pd.notna(adx):
                    if adx > 30:
                        score += 10  # Strong trend
                        reasons.append(f"ADX {adx:.1f} (Strong trend)")
                    elif adx > 25:
                        score += 5   # Trending
                    elif adx < 20:
                        score -= 5   # Weak/no trend
            
            # 6. Price position vs Bollinger Bands - 5 points
            if "bb_lower" in df.columns and "bb_upper" in df.columns:
                close = latest["close"]
                bb_lower = latest["bb_lower"]
                bb_upper = latest["bb_upper"]
                
                if pd.notna(close) and pd.notna(bb_lower) and pd.notna(bb_upper):
                    bb_range = bb_upper - bb_lower
                    if bb_range > 0:
                        position = (close - bb_lower) / bb_range
                        if 0.2 <= position <= 0.5:
                            score += 5  # Near lower band = value entry
                            reasons.append("Near BB lower (value entry)")
                        elif position > 0.9:
                            score -= 5  # Near upper band = overextended
            
            # === STEP 3: Secondary confirmation from ShareHub ===
            try:
                tech = self.sharehub.get_technical_ratings(symbol)
                if tech:
                    # Only use for small adjustment (+/- 5)
                    overall = tech.overall_rating
                    if overall in ["BUY", "STRONG_BUY"]:
                        score += 5
                        if signal != "BUY":
                            signal = "BUY" if overall == "STRONG_BUY" else signal
                    elif overall in ["SELL", "STRONG_SELL"]:
                        score -= 5
                        signal = "SELL" if overall == "STRONG_SELL" else signal
            except:
                pass  # ShareHub is secondary, don't fail if it errors
            
            # === DETERMINE FINAL SIGNAL ===
            if score >= 70:
                signal = "STRONG_BUY" if signal != "SELL" else signal
            elif score >= 60:
                signal = "BUY" if signal != "SELL" else "NEUTRAL"
            elif score <= 35:
                signal = "SELL"
            
            return max(0, min(100, score)), signal
            
        except Exception as e:
            logger.debug(f"Technical score error for {symbol}: {e}")
            # Fallback to ShareHub only
            return self._calculate_technical_score_fallback(symbol)
    
    def _calculate_technical_score_fallback(self, symbol: str) -> Tuple[float, str]:
        """Fallback to ShareHub ratings when OHLCV data unavailable."""
        try:
            tech = self.sharehub.get_technical_ratings(symbol)
            
            if not tech:
                return 50.0, "NEUTRAL"
            
            score = 50.0
            
            # Oscillator summary
            osc_summary = tech.oscillator_summary
            if isinstance(osc_summary, dict):
                buy_count = osc_summary.get("buy", 0)
                sell_count = osc_summary.get("sell", 0)
                total = osc_summary.get("total", 1)
                if total > 0:
                    buy_ratio = buy_count / total
                    score += (buy_ratio - 0.5) * 30
            elif osc_summary == "BUY":
                score += 15
            elif osc_summary == "SELL":
                score -= 15
            
            # MA summary
            ma_summary = tech.ma_summary
            if ma_summary == "BUY":
                score += 20
            elif ma_summary == "SELL":
                score -= 20
            
            # Overall rating
            overall = tech.overall_rating
            if overall in ["BUY", "STRONG_BUY"]:
                signal = "BUY"
                score += 10
            elif overall in ["SELL", "STRONG_SELL"]:
                signal = "SELL"
                score -= 10
            else:
                signal = "NEUTRAL"
            
            return max(0, min(100, score)), signal
            
        except Exception as e:
            return 50.0, "NEUTRAL"

    
    def _calculate_fundamental_score(self, symbol: str, ltp: float) -> Dict:
        """Calculate fundamental analysis score."""
        result = {
            "score": 50.0,
            "pe": 0.0,
            "pb": 0.0,
            "roe": 0.0,
            "eps": 0.0,
            "reasons": [],
            "risks": [],
        }
        
        try:
            fundamentals = self.sharehub.get_fundamentals(symbol)
            
            if not fundamentals:
                return result
            
            score = 50.0
            
            # EPS
            result["eps"] = fundamentals.eps
            if fundamentals.eps > 0:
                score += 10
                result["reasons"].append(f"Positive EPS: Rs. {fundamentals.eps:.2f}")
            else:
                score -= 15
                result["risks"].append("Negative EPS")
            
            # ROE
            result["roe"] = fundamentals.roe
            if fundamentals.roe >= 15:
                score += 15
                result["reasons"].append(f"Strong ROE: {fundamentals.roe:.1f}%")
            elif fundamentals.roe >= 10:
                score += 8
            elif fundamentals.roe < 5 and fundamentals.roe > 0:
                score -= 10
                result["risks"].append(f"Low ROE: {fundamentals.roe:.1f}%")
            
            # Calculate PE
            if fundamentals.eps > 0 and ltp > 0:
                pe = ltp / fundamentals.eps
                result["pe"] = pe
                
                if pe < 10:
                    score += 20
                    result["reasons"].append(f"Attractive PE: {pe:.1f}")
                elif pe < 15:
                    score += 12
                    result["reasons"].append(f"Fair PE: {pe:.1f}")
                elif pe < 25:
                    score += 5
                elif pe > 40:
                    score -= 15
                    result["risks"].append(f"High PE: {pe:.1f}")
            
            # Calculate PB
            if fundamentals.book_value > 0 and ltp > 0:
                pb = ltp / fundamentals.book_value
                result["pb"] = pb
                
                if pb < 1:
                    score += 15
                    result["reasons"].append(f"Below Book Value! PB: {pb:.2f}")
                elif pb < 2:
                    score += 8
                elif pb > 4:
                    score -= 10
                    result["risks"].append(f"High PB: {pb:.2f}")
            
            # Banking-specific: NPL check
            if fundamentals.npl > 0:
                if fundamentals.npl < 2:
                    score += 10
                    result["reasons"].append(f"Low NPL: {fundamentals.npl:.2f}%")
                elif fundamentals.npl > 5:
                    score -= 15
                    result["risks"].append(f"High NPL: {fundamentals.npl:.2f}%")
            
            # 🔴 UNLOCK RISK PENALTY (MutualFund + Promoter)
            if symbol in self._promoter_unlock_risk:
                unlock_data = self._promoter_unlock_risk[symbol]
                remaining_days = unlock_data.get("remaining_days", 999)
                risk_score = unlock_data.get("risk_score", 0)
                is_mf = unlock_data.get("is_mutual_fund", False)
                unlock_type = unlock_data.get("type", "Unknown")
                
                # Use the calculated risk score for penalty
                if risk_score >= 50:
                    score -= 30
                    mf_warning = " (MF - HIGH SELL RISK!)" if is_mf else ""
                    result["risks"].append(f"🚨 {unlock_type} unlock in {remaining_days} days{mf_warning}")
                elif risk_score >= 30:
                    score -= 20
                    result["risks"].append(f"⚠️ {unlock_type} unlock in {remaining_days} days")
                elif risk_score >= 15:
                    score -= 10
                    result["risks"].append(f"📅 {unlock_type} unlock in {remaining_days} days")
                elif risk_score > 0:
                    score -= 5
            
            result["score"] = max(0, min(100, score))
            return result
            
        except Exception as e:
            logger.debug(f"Fundamental score error for {symbol}: {e}")
            return result
    
    def _calculate_momentum_score(self, symbol: str) -> Dict:
        """Calculate momentum score based on price returns."""
        result = {
            "score": 50.0,
            "7d": 0.0,
            "30d": 0.0,
            "52w": 0.0,
            "reasons": [],
        }
        
        try:
            price_changes = self.sharehub.get_price_change_summary(symbol)
            
            if not price_changes:
                return result
            
            score = 50.0
            
            # 7-day return
            result["7d"] = price_changes.change_7d_pct
            if price_changes.change_7d_pct > 5:
                score += 10
                result["reasons"].append(f"Strong 7D momentum: +{price_changes.change_7d_pct:.1f}%")
            elif price_changes.change_7d_pct > 0:
                score += 5
            elif price_changes.change_7d_pct < -5:
                score -= 10
            
            # 30-day return
            result["30d"] = price_changes.change_30d_pct
            if price_changes.change_30d_pct > 15:
                score += 15
                result["reasons"].append(f"Excellent 30D return: +{price_changes.change_30d_pct:.1f}%")
            elif price_changes.change_30d_pct > 5:
                score += 10
            elif price_changes.change_30d_pct < -10:
                score -= 10
            
            # 52-week return
            result["52w"] = price_changes.change_52w_pct
            if price_changes.change_52w_pct > 30:
                score += 15
                result["reasons"].append(f"Strong yearly return: +{price_changes.change_52w_pct:.1f}%")
            elif price_changes.change_52w_pct > 10:
                score += 8
            elif price_changes.change_52w_pct < -20:
                score -= 10
            
            result["score"] = max(0, min(100, score))
            return result
            
        except Exception as e:
            logger.debug(f"Momentum score error for {symbol}: {e}")
            return result
    
    def _calculate_broker_score(self, stock: Dict) -> Dict:
        """
        🎯 MILLIONAIRE INSIGHT: Calculate broker activity score.
        
        KEY FACTORS:
        1. Top 3 broker holding >50% = Institutional accumulation!
        2. High volume = Active interest
        3. High turnover = Big money moving
        """
        symbol = stock.get("symbol", "")
        result = {
            "score": 50.0,
            "accumulation_pct": 0.0,
            "top_brokers": [],
            "reasons": [],
        }
        
        try:
            # Get volume and turnover from current stock data
            volume = int(stock.get("totalTradeQuantity", 0) or 
                        stock.get("volume", 0) or 0)
            turnover = float(stock.get("totalTradeValue", 0) or 
                            stock.get("turnover", 0) or 0)
            
            score = 50.0
            
            # === BROKER ACCUMULATION DATA (from ShareHub API) ===
            if symbol in self._broker_accumulation:
                accum = self._broker_accumulation[symbol]
                top_three_pct = accum.get("top_three_holding_pct", 0)
                top_brokers = accum.get("top_brokers", [])
                
                result["accumulation_pct"] = top_three_pct
                result["top_brokers"] = [b.get("name", "")[:20] for b in top_brokers[:3]]
                
                # 🎯 KEY SCORING: High concentration = institutional buying!
                if top_three_pct >= 80:
                    score += 35  # EXTREME accumulation - big players loading up!
                    result["reasons"].append(f"🔴 EXTREME: Top 3 brokers hold {top_three_pct:.1f}%!")
                elif top_three_pct >= 60:
                    score += 25
                    result["reasons"].append(f"🟠 STRONG: Top 3 hold {top_three_pct:.1f}%")
                elif top_three_pct >= 40:
                    score += 15
                    result["reasons"].append(f"🟡 MODERATE: Top 3 hold {top_three_pct:.1f}%")
                elif top_three_pct < 20:
                    score -= 5  # Distributed = less institutional interest
                
                # Bonus for low broker count (concentrated buying)
                total_brokers = accum.get("total_involved_brokers", 0)
                if total_brokers < 20 and top_three_pct >= 50:
                    score += 10
                    result["reasons"].append(f"Few brokers ({total_brokers}) = concentrated")
            
            # === VOLUME SCORING ===
            if volume > 100000:
                score += 15
                result["reasons"].append(f"Very high volume: {volume:,}")
            elif volume > 50000:
                score += 10
            elif volume > 20000:
                score += 5
            elif volume < 5000:
                score -= 10
            
            # === TURNOVER SCORING ===
            if turnover > 50000000:  # > 5 crore
                score += 10
                result["reasons"].append(f"5+ crore turnover!")
            elif turnover > 10000000:  # > 1 crore
                score += 5
            
            # === PLAYER FAVORITES SCORING (Buyer/Seller dominance) ===
            if symbol in self._player_favorites:
                pf = self._player_favorites[symbol]
                modifier = pf.get("score_modifier", 0)
                winner = pf.get("winner", "")
                weight = pf.get("winner_weight", 0)
                
                score += modifier
                
                if modifier > 0:
                    result["reasons"].append(f"🟢 {winner} dominant ({weight:.1f}%)")
                elif modifier < 0:
                    result["reasons"].append(f"🔴 {winner} dominant ({weight:.1f}%) - CAUTION!")
            
            result["score"] = max(0, min(100, score))
            return result
            
        except Exception as e:
            logger.debug(f"Broker score error for {symbol}: {e}")
            return result
    
    def get_broker_accumulated_stocks(
        self,
        duration: str = "1D",
        min_holding_pct: float = 50.0,
        top_n: int = 10,
    ) -> List[Dict]:
        """
        🎯 GOLDMINE: Get stocks being accumulated by big brokers.
        
        Args:
            duration: "1D", "1W", "1M" etc.
            min_holding_pct: Minimum % held by top 3 brokers
            top_n: Number of results
        
        Returns:
            List of stocks with broker accumulation info
        """
        if not self.sharehub_token:
            logger.warning("Auth token required for broker accumulation!")
            return []
        
        holdings = self.sharehub.get_top_accumulated_stocks(
            duration=duration,
            min_holding_pct=min_holding_pct,
            limit=top_n,
        )
        
        return holdings
    
    def _get_recommendation(self, score: float) -> str:
        """Get recommendation based on total score."""
        if score >= 75:
            return "🟢 STRONG BUY"
        elif score >= 60:
            return "🟢 BUY"
        elif score >= 45:
            return "🟡 HOLD"
        elif score >= 30:
            return "🟠 WEAK"
        else:
            return "🔴 AVOID"
    
    def get_sector_top_picks(self, sector: str, top_n: int = 3) -> List[StockPick]:
        """Get top picks for a specific sector."""
        return self.get_top_picks(
            top_n=top_n,
            sectors=[sector],
        )
    
    def print_top_picks(self, picks: List[StockPick]) -> str:
        """Format top picks for display."""
        if not picks:
            return "No top picks found matching criteria."
        
        lines = [
            "═" * 70,
            "🎯 TOP STOCK PICKS - NEPSE AI TRADING BOT",
            "═" * 70,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "─" * 70,
        ]
        
        for pick in picks:
            lines.extend([
                f"\n#{pick.rank} {pick.symbol} - {pick.name[:30]}",
                f"   Sector: {pick.sector}",
                f"   LTP: Rs. {pick.ltp:,.2f} | Change: {pick.change_pct:+.2f}%",
                f"   ╔══════════════════════════════════════════════╗",
                f"   ║ TOTAL SCORE: {pick.total_score:5.1f}/100  {pick.recommendation:15} ║",
                f"   ╚══════════════════════════════════════════════╝",
                f"   📊 Technical: {pick.technical_score:.0f}/100 ({pick.ta_signal})",
                f"   📈 Fundamental: {pick.fundamental_score:.0f}/100",
                f"      PE: {pick.pe_ratio:.1f} | PB: {pick.pb_ratio:.2f} | ROE: {pick.roe:.1f}%",
                f"   🚀 Momentum: {pick.momentum_score:.0f}/100",
                f"      7D: {pick.return_7d:+.1f}% | 30D: {pick.return_30d:+.1f}% | 52W: {pick.return_52w:+.1f}%",
                f"   ═══════════════════════════════════════════════",
                f"   💰 TRADING LEVELS:",
                f"      Entry: Rs. {pick.entry_price:,.2f}",
                f"      Target (+10%): Rs. {pick.target_price:,.2f}",
                f"      Stop Loss (-5%): Rs. {pick.stop_loss:,.2f}",
                f"      Risk/Reward: {pick.risk_reward_ratio:.1f}:1",
            ])
            
            if pick.buy_reasons:
                lines.append(f"   ✅ BUY REASONS:")
                for reason in pick.buy_reasons[:3]:
                    lines.append(f"      • {reason}")
            
            if pick.risk_factors:
                lines.append(f"   ⚠️  RISK FACTORS:")
                for risk in pick.risk_factors[:2]:
                    lines.append(f"      • {risk}")
            
            lines.append("")
        
        lines.extend([
            "═" * 70,
            "⚠️  DISCLAIMER: This is AI-generated analysis, not financial advice.",
            "   Always do your own research before investing.",
            "═" * 70,
        ])
        
        return "\n".join(lines)


# Convenience function
def get_top_picks(top_n: int = 5) -> List[Dict]:
    """
    Quick function to get top stock picks.
    
    Usage:
        from analysis.top_picks import get_top_picks
        picks = get_top_picks(5)
    """
    analyzer = TopPicksAnalyzer()
    picks = analyzer.get_top_picks(top_n=top_n)
    return [p.to_dict() for p in picks]
