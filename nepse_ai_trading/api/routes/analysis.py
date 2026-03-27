"""
Analysis Routes - Core analysis endpoints.

Provides endpoints for:
- Top stock picks
- Technical analysis
- Fundamental analysis
- Complete stock overview
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from loguru import logger

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


# ============== Pydantic Models ==============

class StockPickResponse(BaseModel):
    """Stock pick response model."""
    rank: int
    symbol: str
    name: str
    sector: str
    ltp: float
    change_pct: float
    total_score: float
    recommendation: str
    technical_score: float
    fundamental_score: float
    momentum_score: float
    pe_ratio: float
    pb_ratio: float
    roe: float
    eps: float
    return_7d: float
    return_30d: float
    return_52w: float
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float
    buy_reasons: List[str]
    risk_factors: List[str]


class TopPicksResponse(BaseModel):
    """Response for top picks endpoint."""
    success: bool
    timestamp: str
    count: int
    picks: List[StockPickResponse]


class FundamentalResponse(BaseModel):
    """Fundamental data response."""
    symbol: str
    name: str
    sector: str
    ltp: float
    market_cap: float
    pe_ratio: float
    pb_ratio: float
    eps: float
    book_value: float
    roe: float
    roa: float
    week_52_high: float
    week_52_low: float
    promoter_holding: float
    public_holding: float
    valuation_score: float
    recommendation: str
    # Banking specific (optional)
    npl: Optional[float] = None
    cd_ratio: Optional[float] = None
    base_rate: Optional[float] = None
    capital_adequacy: Optional[float] = None


class TechnicalRatingResponse(BaseModel):
    """Technical ratings response."""
    symbol: str
    oscillator_summary: str
    ma_summary: str
    overall_rating: str
    oscillators: List[dict]
    moving_averages: List[dict]


class OverviewResponse(BaseModel):
    """Complete stock overview response."""
    symbol: str
    timestamp: str
    fundamentals: dict
    change_summary: dict
    technical: dict
    last_dividend: Optional[dict]
    last_right_share: Optional[dict]
    announcements: List[dict]
    news: List[dict]


# ============== Endpoints ==============

@router.get(
    "/top-picks",
    response_model=TopPicksResponse,
    summary="Get Top Stock Picks",
    description="""
    🎯 **The Millionaire Stock Scanner**
    
    Analyzes ALL NEPSE stocks and returns the top investment opportunities
    based on comprehensive analysis of:
    
    - **Technical Analysis (35%)**: EMA crossover, RSI, Volume, ShareHub ratings
    - **Fundamental Analysis (30%)**: PE, PB, ROE, EPS, Dividend history
    - **Momentum Analysis (15%)**: 7D, 30D, 52W returns
    - **Broker Activity (20%)**: Volume, turnover, AND broker accumulation data!
    
    🔥 **NEW: Broker Accumulation Analysis!**
    If `SHAREHUB_AUTH_TOKEN` is set, includes institutional buying signals:
    - When top 3 brokers hold >50% of recent trades = BIG MONEY loading up!
    
    Each stock is scored 0-100 and includes:
    - Entry price, Target (+10%), Stop Loss (-5%)
    - Buy reasons and risk factors (including accumulation alerts!)
    - Clear recommendation (STRONG BUY, BUY, HOLD, AVOID)
    
    **Trust this endpoint to find your next winning trade!**
    """
)
async def get_top_picks(
    top_n: int = Query(5, ge=1, le=20, description="Number of top picks to return"),
    sector: Optional[str] = Query(None, description="Filter by sector (e.g., 'Commercial Banks')"),
    min_price: float = Query(100, ge=0, description="Minimum stock price"),
    max_pe: float = Query(30, ge=0, description="Maximum PE ratio (0 = no limit)"),
):
    """Get top stock picks based on comprehensive analysis."""
    from datetime import datetime
    
    try:
        from analysis.top_picks import TopPicksAnalyzer
        
        analyzer = TopPicksAnalyzer()
        
        sectors = [sector] if sector else None
        picks = analyzer.get_top_picks(
            top_n=top_n,
            sectors=sectors,
            min_price=min_price,
            max_pe=max_pe if max_pe > 0 else 0,
        )
        
        return TopPicksResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            count=len(picks),
            picks=[StockPickResponse(**p.to_dict()) for p in picks],
        )
        
    except Exception as e:
        logger.error(f"Top picks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/fundamentals/{symbol}",
    response_model=FundamentalResponse,
    summary="Get Fundamental Analysis",
    description="""
    Get complete fundamental analysis for a stock including:
    
    - **Valuation**: PE Ratio, PB Ratio, Market Cap
    - **Earnings**: EPS, ROE, ROA
    - **Structure**: Promoter/Public holding
    - **Banking**: NPL, CD Ratio, Capital Adequacy (for banks)
    - **Recommendation**: Based on valuation score
    """
)
async def get_fundamentals(symbol: str):
    """Get fundamental analysis for a stock."""
    try:
        from analysis.fundamentals import FundamentalAnalyzer
        
        analyzer = FundamentalAnalyzer()
        fund = analyzer.get_fundamentals(symbol.upper())
        
        response = FundamentalResponse(
            symbol=fund.symbol,
            name=fund.name,
            sector=fund.sector,
            ltp=fund.ltp,
            market_cap=fund.market_cap,
            pe_ratio=fund.pe_ratio,
            pb_ratio=fund.pb_ratio,
            eps=fund.eps,
            book_value=fund.book_value,
            roe=fund.roe,
            roa=fund.roa,
            week_52_high=fund.week_52_high,
            week_52_low=fund.week_52_low,
            promoter_holding=fund.promoter_holding,
            public_holding=fund.public_holding,
            valuation_score=fund.valuation_score(),
            recommendation=fund.get_recommendation(),
        )
        
        # Add banking metrics if available
        if fund.npl is not None:
            response.npl = fund.npl
            response.cd_ratio = fund.cd_ratio
            response.base_rate = fund.base_rate
            response.capital_adequacy = fund.capital_adequacy
        
        return response
        
    except Exception as e:
        logger.error(f"Fundamentals error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/technical/{symbol}",
    response_model=TechnicalRatingResponse,
    summary="Get Technical Ratings",
    description="""
    Get technical indicator ratings from ShareHub:
    
    - **Oscillators**: RSI, MACD, ADX, CCI signals
    - **Moving Averages**: SMA/EMA crossover signals
    - **Summary**: BUY/SELL/NEUTRAL recommendation
    """
)
async def get_technical_ratings(symbol: str):
    """Get technical ratings for a stock."""
    try:
        from data.sharehub_api import ShareHubAPI
        
        api = ShareHubAPI()
        tech = api.get_technical_ratings(symbol.upper())
        
        return TechnicalRatingResponse(
            symbol=symbol.upper(),
            oscillator_summary=str(tech.oscillator_summary),
            ma_summary=tech.ma_summary,
            overall_rating=tech.overall_rating,
            oscillators=[
                {"name": o.name, "value": o.value, "action": o.action}
                for o in tech.oscillators
            ],
            moving_averages=[
                {"name": m.name, "value": m.value, "action": m.action}
                for m in tech.moving_averages
            ],
        )
        
    except Exception as e:
        logger.error(f"Technical ratings error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/overview/{symbol}",
    response_model=OverviewResponse,
    summary="Get Complete Stock Overview",
    description="""
    Get COMPLETE stock overview combining all data sources:
    
    - General Information (Market Cap, 52W Range, etc.)
    - Performance (EPS, PE, ROE, Book Value)
    - Change Summary (3D, 7D, 30D, 90D, 180D, 52W returns)
    - Technical Ratings
    - Last Dividend
    - Last Right Share
    - Recent Announcements
    - Recent News
    
    This matches what ShareHub displays on their company overview page.
    """
)
async def get_stock_overview(symbol: str):
    """Get complete stock overview."""
    try:
        from data.sharehub_api import ShareHubAPI
        
        api = ShareHubAPI()
        overview = api.get_complete_overview(symbol.upper())
        
        return OverviewResponse(
            symbol=overview["symbol"],
            timestamp=overview["timestamp"],
            fundamentals=overview.get("fundamentals", {}),
            change_summary=overview.get("change_summary", {}),
            technical=overview.get("technical", {}),
            last_dividend=overview.get("last_dividend"),
            last_right_share=overview.get("last_right_share"),
            announcements=overview.get("announcements", []),
            news=overview.get("news", []),
        )
        
    except Exception as e:
        logger.error(f"Overview error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/dividends/{symbol}",
    summary="Get Dividend History",
    description="Get dividend history for a stock including bonus and cash dividends."
)
async def get_dividend_history(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Number of records"),
):
    """Get dividend history for a stock."""
    try:
        from analysis.fundamentals import FundamentalAnalyzer
        
        analyzer = FundamentalAnalyzer()
        dividends = analyzer.get_dividend_history(symbol.upper())
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "count": len(dividends),
            "dividends": dividends[:limit],
        }
        
    except Exception as e:
        logger.error(f"Dividend history error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/price-changes/{symbol}",
    summary="Get Price Change Summary",
    description="Get price change summary over different time periods (3D, 7D, 30D, 90D, 180D, 52W)."
)
async def get_price_changes(symbol: str):
    """Get price change summary for a stock."""
    try:
        from analysis.fundamentals import FundamentalAnalyzer
        
        analyzer = FundamentalAnalyzer()
        changes = analyzer.get_price_change_summary(symbol.upper())
        
        return {
            "success": True,
            **changes,
        }
        
    except Exception as e:
        logger.error(f"Price changes error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/broker-accumulated",
    summary="🎯 Broker Accumulated Stocks",
    description="""
    **MILLIONAIRE INSIGHT: Stocks being accumulated by big brokers!**
    
    When top 3 brokers hold >50% of recent trades, it signals institutional buying.
    This often precedes price rises as "smart money" positions before retail.
    
    **Requires SHAREHUB_AUTH_TOKEN environment variable!**
    
    Parameters:
    - duration: "1D", "1W", "1M", "3M", "6M", "1Y"
    - min_holding_pct: Minimum % held by top 3 brokers
    
    Returns:
    - symbol: Stock symbol
    - topThreeBrokersHoldingPercentage: % held by top 3 brokers
    - totalInvolvedBrokers: Number of brokers trading
    - holdQuantity: Total quantity being held
    - topBrokers: List of top 3 brokers with their holdings
    """
)
async def get_broker_accumulated(
    duration: str = Query("1D", description="Duration: 1D, 2D, 3D, 5D, 7D, 1W, 1M, 3M, 6M, 1Y"),
    min_holding_pct: float = Query(50.0, description="Minimum holding % by top 3 brokers"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
):
    """Get stocks being accumulated by big brokers."""
    import os
    
    try:
        from analysis.top_picks import TopPicksAnalyzer
        
        auth_token = os.getenv("SHAREHUB_AUTH_TOKEN")
        if not auth_token:
            raise HTTPException(
                status_code=400,
                detail="SHAREHUB_AUTH_TOKEN environment variable not set!"
            )
        
        analyzer = TopPicksAnalyzer(sharehub_token=auth_token)
        
        accumulated = analyzer.get_broker_accumulated_stocks(
            duration=duration,
            min_holding_pct=min_holding_pct,
            top_n=limit,
        )
        
        return {
            "success": True,
            "duration": duration,
            "min_holding_pct": min_holding_pct,
            "count": len(accumulated),
            "stocks": accumulated,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Broker accumulated error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/unlock-risks",
    summary="🔴 ALL Unlock Risks (MutualFund + Promoter)",
    description="""
    **COMPREHENSIVE: All stocks with upcoming unlock risks!**
    
    Returns BOTH Mutual Fund AND Promoter unlocks because:
    
    📊 **Mutual Fund (type=1)**:
    - Mutual Funds are PROFIT-DRIVEN
    - They WILL sell to book profits
    - High sell probability!
    
    👤 **Promoter (type=2)**:
    - Promoters may hold for strategic reasons
    - But often sell portion for liquidity
    - Medium sell probability
    
    🚨 **DOUBLE TROUBLE**: 
    If BOTH unlock around same time → Stock will DUMP hard!
    
    Parameters:
    - days_threshold: Show stocks unlocking within N days (default: 60)
    """
)
async def get_all_unlock_risks(
    days_threshold: int = Query(60, ge=1, le=365, description="Show stocks unlocking within N days"),
):
    """Get ALL unlock risks - both MutualFund and Promoter."""
    try:
        from data.sharehub_api import ShareHubAPI
        
        api = ShareHubAPI()
        risks = api.get_all_unlock_risks(days_threshold=days_threshold)
        
        # Format response
        mf_stocks = [
            {
                "symbol": u.symbol,
                "name": u.name,
                "remaining_days": u.remaining_days,
                "locked_shares": u.locked_shares,
                "locked_percentage": round(u.locked_percentage, 2),
                "risk_score": u.risk_score,
                "risk_level": u.unlock_risk_level,
            }
            for u in risks["mutual_fund"]
        ]
        
        promoter_stocks = [
            {
                "symbol": u.symbol,
                "name": u.name,
                "remaining_days": u.remaining_days,
                "locked_shares": u.locked_shares,
                "locked_percentage": round(u.locked_percentage, 2),
                "risk_score": u.risk_score,
                "risk_level": u.unlock_risk_level,
            }
            for u in risks["promoter"]
        ]
        
        return {
            "success": True,
            "days_threshold": days_threshold,
            "summary": risks["summary"],
            "warning": f"🚨 {risks['summary']['total_risky']} stocks have unlock risk! ({risks['summary']['mf_count']} MutualFund, {risks['summary']['promoter_count']} Promoter)",
            "mutual_fund_unlocks": mf_stocks,
            "promoter_unlocks": promoter_stocks,
            "all_by_risk": [
                {
                    "symbol": u.symbol,
                    "type": u.type,
                    "remaining_days": u.remaining_days,
                    "risk_score": u.risk_score,
                    "risk_level": u.unlock_risk_level,
                }
                for u in risks["combined"][:20]  # Top 20 riskiest
            ],
        }
        
    except Exception as e:
        logger.error(f"Unlock risks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/promoter-unlock",
    summary="🔴 Stocks to AVOID - Single Type Unlock",
    description="""
    **Get unlock data for a specific type (MutualFund OR Promoter)**
    
    For comprehensive analysis, use `/unlock-risks` instead!
    
    Parameters:
    - days_threshold: Show stocks unlocking within N days (default: 30)
    - lock_type: 1 = MutualFund, 2 = Promoter
    """
)
async def get_promoter_unlock(
    days_threshold: int = Query(30, ge=1, le=365, description="Show stocks unlocking within N days"),
    lock_type: int = Query(1, ge=1, le=2, description="1=MutualFund, 2=Promoter"),
):
    """Get stocks with upcoming unlock by type."""
    try:
        from data.sharehub_api import ShareHubAPI
        
        api = ShareHubAPI()
        unlocks = api.get_promoter_unlock_data(lock_type=lock_type)
        
        # Filter by threshold (only future unlocks)
        risky = [u for u in unlocks if 0 < u.remaining_days <= days_threshold]
        
        type_name = "MutualFund" if lock_type == 1 else "Promoter"
        
        return {
            "success": True,
            "type": type_name,
            "days_threshold": days_threshold,
            "count": len(risky),
            "warning": f"⚠️ {len(risky)} stocks have {type_name} unlock within {days_threshold} days!",
            "stocks": [
                {
                    "symbol": u.symbol,
                    "name": u.name,
                    "type": u.type,
                    "remaining_days": u.remaining_days,
                    "unlock_date": str(u.lock_in_end_date) if u.lock_in_end_date else None,
                    "locked_shares": u.locked_shares,
                    "locked_percentage": round(u.locked_percentage, 2),
                    "risk_score": u.risk_score,
                    "risk_level": u.unlock_risk_level,
                }
                for u in risky
            ],
        }
        
    except Exception as e:
        logger.error(f"Unlock error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/complete/{symbol}",
    summary="Get Complete Analysis",
    description="""
    Get COMPLETE analysis for a stock combining:
    
    - NEPSE API data (Market cap, 52W range, volume)
    - ShareHub fundamentals (PE, EPS, ROE, Book Value)
    - ShareHub dividends
    - ShareHub technical ratings
    - Price change summary
    - Promoter unlock risk check
    
    This is the most comprehensive endpoint for stock analysis.
    """
)
async def get_complete_analysis(symbol: str):
    """Get complete analysis for a stock."""
    try:
        from analysis.fundamentals import FundamentalAnalyzer
        from data.sharehub_api import ShareHubAPI
        
        analyzer = FundamentalAnalyzer()
        analysis = analyzer.get_complete_analysis(symbol.upper())
        
        # Check promoter unlock risk
        api = ShareHubAPI()
        unlock_risk = api.check_promoter_risk(symbol.upper())
        
        if unlock_risk:
            analysis["promoter_unlock_risk"] = {
                "has_risk": True,
                "remaining_days": unlock_risk.remaining_days,
                "unlock_date": str(unlock_risk.lock_in_end_date) if unlock_risk.lock_in_end_date else None,
                "locked_shares": unlock_risk.locked_shares,
                "risk_level": unlock_risk.unlock_risk_level,
            }
        else:
            analysis["promoter_unlock_risk"] = {"has_risk": False}
        
        return {
            "success": True,
            **analysis,
        }
        
    except Exception as e:
        logger.error(f"Complete analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/player-favorites",
    summary="🎯 Player Favorites - Buyer/Seller Dominance",
    description="""
    **MILLIONAIRE INSIGHT: See what BIG PLAYERS are doing!**
    
    This shows buyer vs seller dominance for every stock:
    
    🟢 **Buyer Dominance (winnerWeight > 55%):**
    - Big money is LOADING UP
    - Bullish signal
    - These stocks often rise!
    
    🔴 **Seller Dominance (winnerWeight > 55%):**
    - Smart money is EXITING
    - Bearish signal
    - AVOID these stocks!
    
    NO AUTHENTICATION REQUIRED!
    """
)
async def get_player_favorites(
    filter_type: str = Query(
        "all", 
        description="Filter: 'all', 'buyers' (buyer dominated), 'sellers' (seller dominated)"
    ),
    min_weight: float = Query(55.0, ge=50, le=100, description="Minimum winner weight"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """Get player favorites showing buyer/seller dominance."""
    try:
        from data.sharehub_api import ShareHubAPI
        
        api = ShareHubAPI()
        
        if filter_type == "buyers":
            stocks = api.get_buyer_dominated_stocks(min_weight=min_weight)[:limit]
        elif filter_type == "sellers":
            stocks = api.get_seller_dominated_stocks(min_weight=min_weight)[:limit]
        else:
            stocks = api.get_player_favorites()[:limit]
        
        return {
            "success": True,
            "filter_type": filter_type,
            "min_weight": min_weight if filter_type != "all" else None,
            "count": len(stocks),
            "insight": "🎯 Stocks with Buyer dominance are BULLISH, Seller dominance = AVOID!",
            "stocks": [
                {
                    "symbol": s.get("symbol"),
                    "winner": s.get("winner"),
                    "winner_weight": round(s.get("winnerWeight", 0), 1),
                    "buy_amount": round(s.get("buyAmount", 0)),
                    "sell_amount": round(s.get("sellAmount", 0)),
                    "buy_quantity": s.get("buyQuantity", 0),
                    "sell_quantity": s.get("sellQuantity", 0),
                    "signal": "🟢 BULLISH" if s.get("winner") == "Buyer" else "🔴 BEARISH",
                }
                for s in stocks
            ],
        }
        
    except Exception as e:
        logger.error(f"Player favorites error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/market-sentiment",
    summary="📊 Market Sentiment - Overall Buyer/Seller Analysis",
    description="""
    Get overall market sentiment based on player favorites.
    
    Shows:
    - How many stocks have buyer vs seller dominance
    - Overall market sentiment (bullish/bearish)
    - Top buyer dominated stocks
    - Top seller dominated stocks
    """
)
async def get_market_sentiment():
    """Get overall market sentiment from player favorites."""
    try:
        from data.sharehub_api import ShareHubAPI
        
        api = ShareHubAPI()
        favorites = api.get_player_favorites()
        
        buyer_dominated = [
            f for f in favorites 
            if f.get("winner") == "Buyer" and f.get("winnerWeight", 0) > 55
        ]
        seller_dominated = [
            f for f in favorites
            if f.get("winner") == "Seller" and f.get("winnerWeight", 0) > 55
        ]
        
        buyer_count = len(buyer_dominated)
        seller_count = len(seller_dominated)
        total = len(favorites)
        
        # Determine sentiment
        if buyer_count > seller_count * 1.5:
            sentiment = "🟢 BULLISH"
            sentiment_desc = "Strong buyer activity across the market"
        elif seller_count > buyer_count * 1.5:
            sentiment = "🔴 BEARISH"
            sentiment_desc = "Strong selling pressure across the market"
        elif buyer_count > seller_count:
            sentiment = "🟡 MILDLY BULLISH"
            sentiment_desc = "Slightly more buyers than sellers"
        elif seller_count > buyer_count:
            sentiment = "🟠 MILDLY BEARISH"
            sentiment_desc = "Slightly more sellers than buyers"
        else:
            sentiment = "⚪ NEUTRAL"
            sentiment_desc = "Equal buyer and seller activity"
        
        return {
            "success": True,
            "sentiment": sentiment,
            "description": sentiment_desc,
            "stats": {
                "total_stocks": total,
                "buyer_dominated": buyer_count,
                "seller_dominated": seller_count,
                "neutral": total - buyer_count - seller_count,
                "buyer_pct": round(buyer_count / total * 100, 1) if total > 0 else 0,
                "seller_pct": round(seller_count / total * 100, 1) if total > 0 else 0,
            },
            "top_buyer_stocks": [
                {"symbol": s["symbol"], "weight": round(s["winnerWeight"], 1)}
                for s in sorted(buyer_dominated, key=lambda x: x.get("winnerWeight", 0), reverse=True)[:10]
            ],
            "top_seller_stocks": [
                {"symbol": s["symbol"], "weight": round(s["winnerWeight"], 1)}
                for s in sorted(seller_dominated, key=lambda x: x.get("winnerWeight", 0), reverse=True)[:10]
            ],
        }
        
    except Exception as e:
        logger.error(f"Market sentiment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== 4-PILLAR QUANTITATIVE ENGINE ==============

@router.get(
    "/screener",
    summary="🎯 4-PILLAR QUANTITATIVE STOCK SCREENER",
    description="""
    ## 🏆 THE MILLIONAIRE QUANTITATIVE ENGINE
    
    This is NOT an API wrapper. This is a proprietary 4-Pillar Scoring Algorithm
    that mathematically evaluates every NEPSE stock and returns a 0-100 score.
    
    ### SCORING ARCHITECTURE:
    | Pillar | Weight | What It Measures |
    |--------|--------|-----------------|
    | 1. Broker/Institutional | 30% | Buyer dominance, top 3 broker accumulation |
    | 2. Unlock Risk | 20% | MF/Promoter unlock (< 30 days = REJECT!) |
    | 3. Fundamental Safety | 20% | PE, PBV, ROE, EPS |
    | 4. Technical & Momentum | 30% | EMA crossover, RSI, Volume, MACD, ADX |
    
    ### CRITICAL RULES:
    - ⛔ **Stocks with unlock < 30 days**: INSTANT REJECT (-50 penalty)
    - ⚠️ **Seller dominance > 55%**: Heavy penalty (-20)
    - 🔴 **PE > 50**: Overvalued penalty
    - ✅ **Only stocks with score >= min_score are returned**
    
    ### OUTPUT INCLUDES:
    - Total score (0-100)
    - Pillar-by-pillar breakdown with reasons
    - Entry price, Target (+10%), Stop Loss (-5%)
    - Clear recommendation (STRONG BUY, BUY, HOLD, AVOID)
    
    **This is REAL quantitative analysis, not just API data!**
    """
)
async def get_master_screener(
    min_score: int = Query(65, ge=0, le=100, description="Minimum score to include"),
    top_n: int = Query(10, ge=1, le=50, description="Number of top stocks to return"),
):
    """
    🎯 Run the full 4-Pillar quantitative analysis on ALL NEPSE stocks.
    
    This is the main endpoint for finding investment opportunities.
    Non-blocking: runs in a dedicated thread pool so other endpoints stay responsive.
    """
    from datetime import datetime
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    try:
        from analysis.master_screener import MasterStockScreener
        
        def _do_screener():
            screener = MasterStockScreener()
            return screener.run_full_analysis(min_score=min_score, top_n=top_n, max_workers=50)
        
        loop = asyncio.get_event_loop()
        results = await asyncio.wait_for(
            loop.run_in_executor(None, _do_screener),
            timeout=180.0,
        )
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "algorithm": "4-Pillar Quantitative Scoring Engine",
            "min_score": min_score,
            "count": len(results),
            "stocks": [stock.to_dict() for stock in results],
            "legend": {
                "pillar_1": "Broker/Institutional (30 pts max)",
                "pillar_2": "Unlock Risk (20 pts max, or -50 penalty!)",
                "pillar_3": "Fundamental Safety (20 pts max)",
                "pillar_4": "Technical & Momentum (30 pts max)",
            },
            "score_meaning": {
                "80+": "🟢 STRONG BUY - Excellent across all pillars",
                "70-79": "🟢 BUY - Good opportunity",
                "60-69": "🟡 HOLD/ACCUMULATE - Fair, monitor closely",
                "50-59": "🟠 WEAK - Consider avoiding",
                "0-49": "🔴 AVOID - Major red flags",
            },
        }
        
    except asyncio.TimeoutError:
        logger.error("Master screener timed out after 180s")
        raise HTTPException(status_code=504, detail="Screener timed out. NEPSE API may be slow.")
    except Exception as e:
        logger.error(f"Master screener error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/rejected-stocks",
    summary="🚫 Stocks Rejected by Screener",
    description="""
    Get stocks that were REJECTED by the 4-Pillar screener.
    
    Useful for understanding why certain stocks were excluded.
    
    Common rejection reasons:
    - 🚨 Unlock within 30 days (instant -50 penalty)
    - 🔴 Heavy seller dominance
    - 📉 Poor technical setup
    """
)
async def get_rejected_stocks(
    limit: int = Query(10, ge=1, le=50, description="Max rejected stocks to return"),
):
    """Get stocks rejected due to unlock risk or heavy penalties."""
    try:
        from analysis.master_screener import get_rejected_stocks
        
        rejected = get_rejected_stocks(limit=limit)
        
        return {
            "success": True,
            "count": len(rejected),
            "warning": "⚠️ These stocks were REJECTED - avoid buying!",
            "rejected_stocks": rejected,
        }
        
    except Exception as e:
        logger.error(f"Rejected stocks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
