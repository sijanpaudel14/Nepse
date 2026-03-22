"""
Stock Routes - Market data and stock information endpoints.

Provides endpoints for:
- Market summary
- Live stock prices
- Price history
- Company details
- Sector performance
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

router = APIRouter(prefix="/api/stocks", tags=["Stocks"])


# ============== Pydantic Models ==============

class MarketSummaryResponse(BaseModel):
    """Market summary response."""
    success: bool
    timestamp: str
    nepse_index: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    total_turnover: Optional[float]
    total_volume: Optional[int]
    total_trades: Optional[int]
    advances: int
    declines: int
    unchanged: int


class StockPriceResponse(BaseModel):
    """Stock price response."""
    symbol: str
    name: str
    ltp: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    previous_close: float
    volume: int
    turnover: float


class CompanyInfoResponse(BaseModel):
    """Company information response."""
    symbol: str
    name: str
    sector: str
    market_cap: float
    listed_shares: int
    face_value: float
    week_52_high: float
    week_52_low: float
    promoter_holding: float
    public_holding: float


# ============== Endpoints ==============

@router.get(
    "/market-summary",
    response_model=MarketSummaryResponse,
    summary="Get Market Summary",
    description="Get current NEPSE market summary including index, advances, declines."
)
async def get_market_summary():
    """Get market summary."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        summary = fetcher.fetch_market_summary()
        
        return MarketSummaryResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            nepse_index=summary.get("index"),
            change=summary.get("change"),
            change_pct=summary.get("change_pct"),
            total_turnover=summary.get("turnover"),
            total_volume=summary.get("volume"),
            total_trades=summary.get("trades"),
            advances=summary.get("advances", 0),
            declines=summary.get("declines", 0),
            unchanged=summary.get("unchanged", 0),
        )
        
    except Exception as e:
        logger.error(f"Market summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/live",
    summary="Get Live Market Data",
    description="Get live prices for all actively traded stocks."
)
async def get_live_market(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    min_change: Optional[float] = Query(None, description="Minimum change %"),
    max_change: Optional[float] = Query(None, description="Maximum change %"),
    limit: int = Query(50, ge=1, le=500, description="Number of results"),
):
    """Get live market data."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        data = fetcher.fetch_live_market()
        
        # Apply filters
        if sector:
            data = [d for d in data if sector.lower() in (d.get("sectorName", "") or "").lower()]
        
        if min_change is not None:
            data = [d for d in data if float(d.get("percentageChange", 0) or 0) >= min_change]
        
        if max_change is not None:
            data = [d for d in data if float(d.get("percentageChange", 0) or 0) <= max_change]
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "count": len(data[:limit]),
            "stocks": data[:limit],
        }
        
    except Exception as e:
        logger.error(f"Live market error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/top-gainers",
    summary="Get Top Gainers",
    description="Get stocks with highest positive change today."
)
async def get_top_gainers(limit: int = Query(10, ge=1, le=50)):
    """Get top gainers."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        gainers = fetcher.fetch_top_gainers(limit=limit)
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "count": len(gainers),
            "gainers": gainers,
        }
        
    except Exception as e:
        logger.error(f"Top gainers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/top-losers",
    summary="Get Top Losers",
    description="Get stocks with highest negative change today."
)
async def get_top_losers(limit: int = Query(10, ge=1, le=50)):
    """Get top losers."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        losers = fetcher.fetch_top_losers(limit=limit)
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "count": len(losers),
            "losers": losers,
        }
        
    except Exception as e:
        logger.error(f"Top losers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/price/{symbol}",
    response_model=StockPriceResponse,
    summary="Get Stock Price",
    description="Get current price for a stock."
)
async def get_stock_price(symbol: str):
    """Get current stock price."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        details = fetcher.fetch_company_details(symbol.upper())
        
        if not details:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
        
        trade = details.get("securityDailyTradeDto", {})
        security = details.get("security", {})
        
        return StockPriceResponse(
            symbol=symbol.upper(),
            name=security.get("securityName", ""),
            ltp=float(trade.get("lastTradedPrice", 0) or 0),
            change=float(trade.get("pointChange", 0) or 0),
            change_pct=float(trade.get("percentageChange", 0) or 0),
            open=float(trade.get("openPrice", 0) or 0),
            high=float(trade.get("highPrice", 0) or 0),
            low=float(trade.get("lowPrice", 0) or 0),
            previous_close=float(trade.get("previousClose", 0) or 0),
            volume=int(trade.get("totalTradeQuantity", 0) or 0),
            turnover=float(trade.get("totalTradeValue", 0) or 0),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stock price error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/info/{symbol}",
    response_model=CompanyInfoResponse,
    summary="Get Company Info",
    description="Get company information including market cap, holdings, etc."
)
async def get_company_info(symbol: str):
    """Get company information."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        details = fetcher.fetch_company_details(symbol.upper())
        
        if not details:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
        
        security = details.get("security", {})
        trade = details.get("securityDailyTradeDto", {})
        
        return CompanyInfoResponse(
            symbol=symbol.upper(),
            name=security.get("securityName", ""),
            sector=details.get("sector", {}).get("sectorDescription", ""),
            market_cap=float(details.get("marketCapitalization", 0) or 0),
            listed_shares=int(details.get("stockListedShares", 0) or 0),
            face_value=float(security.get("faceValue", 100) or 100),
            week_52_high=float(trade.get("fiftyTwoWeekHigh", 0) or 0),
            week_52_low=float(trade.get("fiftyTwoWeekLow", 0) or 0),
            promoter_holding=float(details.get("promoterPercentage", 0) or 0),
            public_holding=float(details.get("publicPercentage", 0) or 0),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Company info error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/history/{symbol}",
    summary="Get Price History",
    description="Get historical price data for a stock."
)
async def get_price_history(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
):
    """Get price history."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        history = fetcher.fetch_price_history(symbol.upper(), days=days)
        
        if history.empty:
            return {
                "success": True,
                "symbol": symbol.upper(),
                "count": 0,
                "history": [],
            }
        
        # Convert DataFrame to list of dicts
        history_list = history.to_dict(orient="records")
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "count": len(history_list),
            "history": history_list,
        }
        
    except Exception as e:
        logger.error(f"Price history error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sectors",
    summary="Get All Sectors",
    description="Get list of all sectors in NEPSE."
)
async def get_sectors():
    """Get all sectors."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        sectors = fetcher.fetch_sectors()
        
        return {
            "success": True,
            "count": len(sectors),
            "sectors": sectors,
        }
        
    except Exception as e:
        logger.error(f"Sectors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/companies",
    summary="Get All Companies",
    description="Get list of all companies listed in NEPSE."
)
async def get_companies(
    sector: Optional[str] = Query(None, description="Filter by sector"),
):
    """Get all companies."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        companies = fetcher.fetch_company_list()
        
        if sector:
            companies = [c for c in companies if sector.lower() in (c.get("sectorName", "") or "").lower()]
        
        return {
            "success": True,
            "count": len(companies),
            "companies": companies,
        }
        
    except Exception as e:
        logger.error(f"Companies error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
