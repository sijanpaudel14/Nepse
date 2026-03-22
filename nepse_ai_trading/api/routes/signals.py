"""
Signals Routes - Trading signals and alerts endpoints.

Provides endpoints for:
- Trading signals
- Screening results
- AI-generated verdicts
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

router = APIRouter(prefix="/api/signals", tags=["Signals"])


# ============== Pydantic Models ==============

class ScreenerResultResponse(BaseModel):
    """Screener result response."""
    symbol: str
    name: str
    sector: str
    strategy: str
    signal: str
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    reason: str


# ============== Endpoints ==============

@router.get(
    "/screen",
    summary="Run Stock Screener",
    description="""
    Run the multi-strategy stock screener to find trading opportunities.
    
    Available strategies:
    - **golden_cross**: 9 EMA crossed above 21 EMA
    - **rsi_momentum**: RSI in optimal range (50-65) with volume
    - **volume_breakout**: Volume > 1.5x 20-day average
    - **all**: Run all strategies (default)
    """
)
async def run_screener(
    strategy: str = Query("all", description="Strategy to run"),
    min_price: float = Query(200, ge=0, description="Minimum stock price"),
):
    """Run stock screener."""
    try:
        from analysis.screener import StockScreener
        
        screener = StockScreener()
        
        if strategy == "all":
            results = screener.run_all_screens(min_price=min_price)
        else:
            results = screener.run_screen(strategy_name=strategy, min_price=min_price)
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy,
            "count": len(results),
            "results": [
                ScreenerResultResponse(
                    symbol=r.symbol,
                    name=r.name,
                    sector=r.sector,
                    strategy=r.strategy_name,
                    signal=r.signal_type,
                    confidence=r.confidence,
                    entry_price=r.entry_price,
                    target_price=r.target_price or 0,
                    stop_loss=r.stop_loss or 0,
                    reason=r.reason,
                ).dict()
                for r in results
            ],
        }
        
    except Exception as e:
        logger.error(f"Screener error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/today",
    summary="Get Today's Signals",
    description="Get all trading signals generated today."
)
async def get_todays_signals():
    """Get today's signals."""
    try:
        from analysis.top_picks import TopPicksAnalyzer
        
        # Use top picks as signals
        analyzer = TopPicksAnalyzer()
        picks = analyzer.get_top_picks(top_n=10)
        
        signals = []
        for pick in picks:
            if pick.total_score >= 55:  # Only include decent scores
                signals.append({
                    "symbol": pick.symbol,
                    "name": pick.name,
                    "signal": "BUY" if pick.total_score >= 60 else "WATCH",
                    "score": pick.total_score,
                    "recommendation": pick.recommendation,
                    "entry_price": pick.entry_price,
                    "target_price": pick.target_price,
                    "stop_loss": pick.stop_loss,
                    "reasons": pick.buy_reasons[:3],
                })
        
        return {
            "success": True,
            "date": date.today().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "count": len(signals),
            "signals": signals,
        }
        
    except Exception as e:
        logger.error(f"Today's signals error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sector/{sector}",
    summary="Get Sector Signals",
    description="Get trading signals for a specific sector."
)
async def get_sector_signals(
    sector: str,
    top_n: int = Query(5, ge=1, le=20),
):
    """Get signals for a specific sector."""
    try:
        from analysis.top_picks import TopPicksAnalyzer
        
        analyzer = TopPicksAnalyzer()
        picks = analyzer.get_sector_top_picks(sector=sector, top_n=top_n)
        
        return {
            "success": True,
            "sector": sector,
            "timestamp": datetime.now().isoformat(),
            "count": len(picks),
            "picks": [p.to_dict() for p in picks],
        }
        
    except Exception as e:
        logger.error(f"Sector signals error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/ai-verdict/{symbol}",
    summary="Get AI Verdict",
    description="""
    Get AI-generated trading verdict for a stock.
    
    Uses OpenAI GPT-4o-mini to analyze:
    - Technical indicators
    - Fundamental data
    - Recent news
    
    Returns a clear verdict with reasoning.
    
    **Requires OPENAI_API_KEY environment variable.**
    """
)
async def get_ai_verdict(symbol: str):
    """Get AI verdict for a stock."""
    try:
        from intelligence.ai_advisor import get_ai_verdict
        from analysis.fundamentals import FundamentalAnalyzer
        
        # Get fundamentals first
        analyzer = FundamentalAnalyzer()
        fundamentals = analyzer.get_fundamentals(symbol.upper())
        
        # Prepare context
        context = {
            "symbol": symbol.upper(),
            "ltp": fundamentals.ltp,
            "pe_ratio": fundamentals.pe_ratio,
            "pb_ratio": fundamentals.pb_ratio,
            "roe": fundamentals.roe,
            "eps": fundamentals.eps,
            "week_52_high": fundamentals.week_52_high,
            "week_52_low": fundamentals.week_52_low,
            "valuation_score": fundamentals.valuation_score(),
        }
        
        # Get AI verdict
        verdict = await get_ai_verdict(symbol.upper(), context)
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "timestamp": datetime.now().isoformat(),
            "verdict": verdict.verdict if verdict else "UNABLE_TO_ANALYZE",
            "target_price": verdict.target_price if verdict else None,
            "stop_loss": verdict.stop_loss if verdict else None,
            "reasoning": verdict.reasoning if verdict else "AI analysis unavailable",
            "risk_factors": verdict.risk_factors if verdict else [],
            "confidence": verdict.confidence if verdict else 0,
        }
        
    except Exception as e:
        logger.error(f"AI verdict error for {symbol}: {e}")
        return {
            "success": False,
            "symbol": symbol.upper(),
            "error": str(e),
            "message": "AI analysis requires OPENAI_API_KEY environment variable",
        }
