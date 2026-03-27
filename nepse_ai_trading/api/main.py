"""
FastAPI Application for NEPSE AI Trading Bot.

This is the main API entry point that provides:
- Trading signals and recommendations
- Portfolio tracking
- Market data access
- Backtest results

Future: Will support multi-user authentication for SaaS.
"""

# Apply HTTP/2 patch BEFORE any nepse imports (Docker compatibility)
try:
    from http2_patch import *
except ImportError:
    pass  # Patch not needed on localhost

import os
from pathlib import Path
from datetime import date, datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from loguru import logger

from core.config import settings
from core.database import SessionLocal, Stock, DailyPrice, Signal as TradingSignal

# Get paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
STATIC_DIR = BASE_DIR / "web" / "static"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
# Extra CORS origins from env (comma-separated). Add new domains without rebuilding.
_extra_origins = [o.strip() for o in os.getenv("EXTRA_CORS_ORIGINS", "").split(",") if o.strip()]

# Create FastAPI app
app = FastAPI(
    title="NEPSE AI Trading Bot",
    description="""
    🎯 **AI-Powered Swing Trading Assistant for Nepal Stock Exchange**
    
    This API provides comprehensive stock analysis including:
    
    - **Top Picks**: AI-generated top investment opportunities
    - **Fundamental Analysis**: PE, PB, ROE, EPS, Book Value
    - **Technical Analysis**: RSI, MACD, ADX signals
    - **Price History**: Historical OHLCV data
    - **Dividends**: Dividend history and announcements
    - **Market Data**: Live prices, gainers, losers
    
    Built for traders who want to make data-driven decisions.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Include API routes
from api.routes.analysis import router as analysis_router
from api.routes.stocks import router as stocks_router
from api.routes.signals import router as signals_router
from api.routes.saas import router as saas_router

app.include_router(analysis_router)
app.include_router(stocks_router)
app.include_router(signals_router)
app.include_router(saas_router)  # SaaS endpoints for Next.js frontend

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None

# CORS middleware - Allow all frontend origins
_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    FRONTEND_URL,
    # Azure Storage static website
    "https://nepsestorage4552333.z12.web.core.windows.net",
    # Vercel deployments
    "https://nepse-saas-frontend.vercel.app",
    "https://nepse.sijanpaudel.com.np",
    "https://nepse-saas-frontend-sijan-paudels-projects.vercel.app",
] + _extra_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://nepse-saas-frontend-.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- Pydantic Models -----

class MarketSummary(BaseModel):
    """Market summary response."""
    date: date
    nepse_index: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    advances: int
    declines: int
    unchanged: int
    is_open: bool


class StockPrice(BaseModel):
    """Stock price data."""
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    change_pct: Optional[float]


class TradingSignalResponse(BaseModel):
    """Trading signal response."""
    symbol: str
    signal_type: str  # BUY, SELL, HOLD
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    strategies: List[str]
    ai_verdict: Optional[str]
    news_summary: Optional[str]
    timestamp: datetime


class PositionResponse(BaseModel):
    """Portfolio position response."""
    symbol: str
    shares: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    pnl_pct: float
    sector: str
    holding_days: int


class PortfolioSummary(BaseModel):
    """Portfolio summary response."""
    total_value: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_return_pct: float
    num_positions: int
    max_positions: int


class BacktestRequest(BaseModel):
    """Backtest request parameters."""
    strategy: str = Field(..., description="Strategy name (golden_cross, volume_breakout, etc.)")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    initial_capital: float = 500_000
    symbols: Optional[List[str]] = None


class BacktestResponse(BaseModel):
    """Backtest results response."""
    strategy: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    profit_factor: float
    period_days: int


class AlertSettings(BaseModel):
    """Alert settings."""
    telegram_enabled: bool = True
    telegram_chat_id: Optional[str] = None
    email_enabled: bool = False
    email_address: Optional[str] = None
    min_confidence: float = 60.0


# ----- Database Dependency -----

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----- Health Check -----

@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard(request: Request):
    """Serve the main dashboard."""
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    else:
        return HTMLResponse(content="""
            <html>
            <head><title>NEPSE AI Trading Bot</title></head>
            <body>
                <h1>NEPSE AI Trading Bot</h1>
                <p>Dashboard not available. See <a href="/docs">API Documentation</a></p>
            </body>
            </html>
        """)


@app.get("/api", tags=["Health"])
async def api_root():
    """API root endpoint."""
    return {
        "name": "NEPSE AI Trading Bot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
    }


# ----- Market Data -----

@app.get("/api/market/summary", response_model=MarketSummary, tags=["Market"])
async def get_market_summary():
    """Get current market summary."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        summary = fetcher.fetch_market_summary()
        is_open = fetcher.is_market_open()
        
        return MarketSummary(
            date=summary.date,
            nepse_index=summary.nepse_index,
            change=summary.nepse_change,
            change_pct=summary.nepse_change_pct,
            advances=summary.advances or 0,
            declines=summary.declines or 0,
            unchanged=summary.unchanged or 0,
            is_open=is_open,
        )
    except Exception as e:
        logger.error(f"Failed to get market summary: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch market data")


@app.get("/api/market/live", tags=["Market"])
async def get_live_market(
    limit: int = Query(50, ge=1, le=500),
    sort_by: str = Query("volume", enum=["volume", "change", "turnover"]),
):
    """Get live market data for all stocks."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        df = fetcher.fetch_live_market()
        
        if df.empty:
            return {"data": [], "count": 0}
        
        # Sort
        if sort_by == "volume":
            df = df.sort_values("volume", ascending=False)
        elif sort_by == "turnover":
            df = df.sort_values("turnover", ascending=False)
        
        df = df.head(limit)
        
        return {
            "data": df.to_dict(orient="records"),
            "count": len(df),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get live market: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch live data")


@app.get("/api/market/top-gainers", tags=["Market"])
async def get_top_gainers(limit: int = Query(10, ge=1, le=50)):
    """Get top gaining stocks today."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        df = fetcher.fetch_top_gainers(limit)
        
        return {"data": df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"Failed to get top gainers: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch data")


@app.get("/api/market/top-losers", tags=["Market"])
async def get_top_losers(limit: int = Query(10, ge=1, le=50)):
    """Get top losing stocks today."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        df = fetcher.fetch_top_losers(limit)
        
        return {"data": df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"Failed to get top losers: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch data")


@app.get("/api/market/sectors", tags=["Market"])
async def get_sector_indices():
    """Get sector-wise performance."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        df = fetcher.fetch_sector_indices()
        
        return {"data": df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"Failed to get sectors: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch data")


# ----- Stock Data -----

@app.get("/api/stocks", tags=["Stocks"])
async def get_stocks(
    sector: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    """Get list of stocks."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        stocks = fetcher.fetch_company_list()
        
        # Filter by sector
        if sector:
            stocks = [s for s in stocks if sector.lower() in s.sector.lower()]
        
        # Search by symbol or name
        if search:
            search = search.upper()
            stocks = [s for s in stocks if search in s.symbol or search in s.name.upper()]
        
        stocks = stocks[:limit]
        
        return {
            "data": [{"symbol": s.symbol, "name": s.name, "sector": s.sector} for s in stocks],
            "count": len(stocks),
        }
    except Exception as e:
        logger.error(f"Failed to get stocks: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch stocks")


@app.get("/api/stocks/{symbol}", tags=["Stocks"])
async def get_stock_details(symbol: str):
    """Get detailed info for a stock."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        details = fetcher.fetch_company_details(symbol)
        
        if not details:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
        
        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stock details: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch data")


@app.get("/api/stocks/{symbol}/history", response_model=List[StockPrice], tags=["Stocks"])
async def get_stock_history(
    symbol: str,
    days: int = Query(90, ge=1, le=365),
):
    """Get historical price data for a stock."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        df = fetcher.fetch_price_history(symbol, days)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")
        
        # Calculate daily change
        df["change_pct"] = df["close"].pct_change() * 100
        
        records = []
        for _, row in df.iterrows():
            records.append(StockPrice(
                symbol=symbol,
                date=row["date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=int(row["volume"]),
                change_pct=row.get("change_pct"),
            ))
        
        return records
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get history for {symbol}: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch data")


# ----- Trading Signals -----

@app.get("/api/signals", response_model=List[TradingSignalResponse], tags=["Signals"])
async def get_signals(
    min_confidence: float = Query(60.0, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
):
    """Get today's trading signals."""
    try:
        from analysis.screener import run_all_strategies
        from intelligence.signal_aggregator import aggregate_signals
        
        # Run screening
        candidates = run_all_strategies()
        
        # Filter by confidence
        signals = [s for s in candidates if s.confidence >= min_confidence]
        signals = sorted(signals, key=lambda x: x.confidence, reverse=True)[:limit]
        
        response = []
        for signal in signals:
            response.append(TradingSignalResponse(
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                confidence=signal.confidence,
                entry_price=signal.entry_price,
                target_price=signal.target_price,
                stop_loss=signal.stop_loss,
                strategies=signal.strategies,
                ai_verdict=getattr(signal, "ai_verdict", None),
                news_summary=getattr(signal, "news_summary", None),
                timestamp=datetime.now(),
            ))
        
        return response
    except Exception as e:
        logger.error(f"Failed to get signals: {e}")
        raise HTTPException(status_code=503, detail="Unable to generate signals")


@app.post("/api/signals/scan", tags=["Signals"])
async def run_scan(background_tasks: BackgroundTasks):
    """Trigger a full market scan for signals."""
    # Run in background
    background_tasks.add_task(run_full_scan)
    
    return {
        "status": "started",
        "message": "Scan started in background. Check /api/signals for results.",
    }


async def run_full_scan():
    """Background task to run full market scan."""
    try:
        from analysis.screener import run_all_strategies
        from intelligence.ai_advisor import get_ai_analysis
        from intelligence.news_scraper import scrape_news
        
        logger.info("Starting full market scan...")
        
        # Get TA signals
        candidates = run_all_strategies()
        logger.info(f"Found {len(candidates)} TA candidates")
        
        # Enrich top candidates with news and AI
        for signal in candidates[:10]:
            try:
                # Scrape news
                news = await scrape_news(signal.symbol)
                
                # Get AI analysis
                ai_response = await get_ai_analysis(signal, news)
                
                signal.ai_verdict = ai_response.get("verdict")
                signal.news_summary = ai_response.get("summary")
                
            except Exception as e:
                logger.debug(f"Failed to enrich {signal.symbol}: {e}")
        
        logger.info("Full market scan complete")
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")


# ----- Portfolio -----

@app.get("/api/portfolio", response_model=PortfolioSummary, tags=["Portfolio"])
async def get_portfolio():
    """Get portfolio summary."""
    try:
        from risk.portfolio_manager import PortfolioManager
        
        # In production, this would load from database
        # For now, return mock data
        return PortfolioSummary(
            total_value=500_000,
            cash=200_000,
            positions_value=300_000,
            unrealized_pnl=15_000,
            realized_pnl=25_000,
            total_return_pct=8.0,
            num_positions=3,
            max_positions=5,
        )
    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch portfolio")


@app.get("/api/portfolio/positions", response_model=List[PositionResponse], tags=["Portfolio"])
async def get_positions():
    """Get current positions."""
    # Mock data for now
    return [
        PositionResponse(
            symbol="NABIL",
            shares=100,
            entry_price=1200.0,
            current_price=1250.0,
            unrealized_pnl=5000.0,
            pnl_pct=4.17,
            sector="Commercial Banks",
            holding_days=15,
        ),
    ]


# ----- Backtesting -----

@app.post("/api/backtest", response_model=BacktestResponse, tags=["Backtest"])
async def run_backtest(request: BacktestRequest):
    """Run a backtest for a strategy."""
    try:
        from backtesting import SimpleBacktest, BacktestConfig, MetricsCalculator
        from data.fetcher import NepseFetcher
        
        logger.info(f"Starting backtest for {request.strategy}")
        
        # Get historical data
        fetcher = NepseFetcher()
        
        # Use first symbol or get market data
        if request.symbols:
            df = fetcher.fetch_price_history(request.symbols[0], 365)
        else:
            df = fetcher.fetch_live_market()
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No data available for backtest")
        
        # Configure backtest
        config = BacktestConfig(
            initial_capital=request.initial_capital,
        )
        
        # Run backtest (simplified - full implementation in backtesting module)
        # This is a placeholder - actual implementation uses the strategy engine
        
        return BacktestResponse(
            strategy=request.strategy,
            total_return_pct=25.5,
            sharpe_ratio=1.35,
            max_drawdown_pct=12.3,
            win_rate=58.0,
            total_trades=45,
            profit_factor=1.65,
            period_days=365,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


# ----- Settings -----

@app.get("/api/settings/alerts", response_model=AlertSettings, tags=["Settings"])
async def get_alert_settings():
    """Get alert settings."""
    return AlertSettings(
        telegram_enabled=settings.telegram_bot_token is not None,
        telegram_chat_id=settings.telegram_chat_id,
        email_enabled=False,
        min_confidence=settings.min_signal_confidence,
    )


@app.post("/api/settings/alerts", tags=["Settings"])
async def update_alert_settings(settings_update: AlertSettings):
    """Update alert settings."""
    # In production, save to database
    return {"status": "updated", "settings": settings_update}


# ----- Error Handlers -----

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": str(type(exc).__name__)},
    )


# ----- Fundamental Analysis (NEW) -----

class FundamentalResponse(BaseModel):
    """Fundamental data response."""
    symbol: str
    company_name: str
    sector: str
    pe_ratio: float
    pb_ratio: float
    eps: float
    book_value: float
    roe: float
    market_cap: float
    dividend_yield: float
    valuation_score: float
    valuation_verdict: str


class BrokerAnalysisResponse(BaseModel):
    """Broker analysis response."""
    symbol: str
    total_volume: float
    top_buyers: List[Dict[str, Any]]
    top_sellers: List[Dict[str, Any]]
    buy_sell_ratio: float
    signal: str
    recommendation: str


class MarketDepthResponse(BaseModel):
    """Market depth response."""
    symbol: str
    best_bid: float
    best_ask: float
    spread: float
    spread_pct: float
    total_bid_qty: int
    total_ask_qty: int
    order_imbalance: float
    liquidity_score: float


class ComprehensiveAnalysisResponse(BaseModel):
    """Complete analysis response combining TA + FA."""
    symbol: str
    overall_score: float
    verdict: str
    
    # Technical
    ta_confidence: float
    ta_signals: List[str]
    
    # Fundamental
    pe_ratio: float
    pb_ratio: float
    roe: float
    eps: float
    valuation_verdict: str
    
    # Broker
    broker_signal: str
    top_buyers: List[str]
    top_sellers: List[str]
    
    # Trade Setup
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward: float
    position_size: str


@app.get("/api/fundamentals/{symbol}", response_model=FundamentalResponse, tags=["Fundamentals"])
async def get_fundamentals(symbol: str):
    """
    Get fundamental analysis for a stock.
    
    Returns PE, PB, EPS, ROE, Book Value, Market Cap, and valuation score.
    """
    try:
        from analysis.fundamentals import FundamentalAnalyzer
        
        analyzer = FundamentalAnalyzer()
        data = analyzer.get_fundamentals(symbol)
        
        if not data:
            raise HTTPException(status_code=404, detail=f"No fundamental data for {symbol}")
        
        # Calculate valuation score
        score = analyzer._calculate_valuation_score(data)
        
        # Determine verdict
        if data.pe_ratio < 15 and data.pb_ratio < 2:
            verdict = "UNDERVALUED"
        elif data.pe_ratio > 30 or data.pb_ratio > 4:
            verdict = "OVERVALUED"
        else:
            verdict = "FAIR"
        
        return FundamentalResponse(
            symbol=symbol.upper(),
            company_name=data.company_name,
            sector=data.sector,
            pe_ratio=data.pe_ratio,
            pb_ratio=data.pb_ratio,
            eps=data.eps,
            book_value=data.book_value,
            roe=data.roe,
            market_cap=data.market_cap,
            dividend_yield=data.dividend_yield,
            valuation_score=score,
            valuation_verdict=verdict,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get fundamentals for {symbol}: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch fundamental data")


@app.get("/api/fundamentals/{symbol}/brokers", response_model=BrokerAnalysisResponse, tags=["Fundamentals"])
async def get_broker_analysis(symbol: str):
    """
    Get broker activity analysis from floor sheet.
    
    Shows top buyers/sellers and accumulation/distribution signals.
    """
    try:
        from analysis.fundamentals import FundamentalAnalyzer
        
        analyzer = FundamentalAnalyzer()
        analysis = analyzer.analyze_brokers(symbol)
        
        if not analysis:
            raise HTTPException(status_code=404, detail=f"No broker data for {symbol}")
        
        return BrokerAnalysisResponse(
            symbol=symbol.upper(),
            total_volume=analysis.total_volume,
            top_buyers=[
                {"broker": b[0], "volume": b[1], "pct": b[2]}
                for b in analysis.top_buyers
            ],
            top_sellers=[
                {"broker": s[0], "volume": s[1], "pct": s[2]}
                for s in analysis.top_sellers
            ],
            buy_sell_ratio=analysis.buy_sell_ratio,
            signal=analysis.signal,
            recommendation=analysis.recommendation,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get broker analysis for {symbol}: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch broker data")


@app.get("/api/fundamentals/{symbol}/depth", response_model=MarketDepthResponse, tags=["Fundamentals"])
async def get_market_depth(symbol: str):
    """
    Get market depth (order book) analysis.
    
    Shows bid/ask levels, spread, and liquidity metrics.
    """
    try:
        from analysis.fundamentals import FundamentalAnalyzer
        
        analyzer = FundamentalAnalyzer()
        depth = analyzer.get_market_depth(symbol)
        
        if not depth:
            raise HTTPException(status_code=404, detail=f"No depth data for {symbol}")
        
        return MarketDepthResponse(
            symbol=symbol.upper(),
            best_bid=depth.best_bid,
            best_ask=depth.best_ask,
            spread=depth.spread,
            spread_pct=depth.spread_pct,
            total_bid_qty=depth.total_bid_qty,
            total_ask_qty=depth.total_ask_qty,
            order_imbalance=depth.order_imbalance,
            liquidity_score=depth.liquidity_score,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get market depth for {symbol}: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch depth data")


@app.get("/api/analysis/{symbol}", response_model=ComprehensiveAnalysisResponse, tags=["Analysis"])
async def get_comprehensive_analysis(symbol: str):
    """
    Get comprehensive analysis combining Technical + Fundamental + Broker data.
    
    This is the main endpoint for complete stock analysis with trade recommendations.
    """
    try:
        from analysis.fundamentals import FundamentalAnalyzer
        from analysis.screener import StockScreener
        from intelligence.signal_aggregator import SignalAggregator
        
        symbol = symbol.upper()
        
        # Get fundamental analysis
        fund_analyzer = FundamentalAnalyzer()
        complete_analysis = fund_analyzer.get_complete_analysis(symbol)
        
        # Get technical signals
        screener = StockScreener()
        ta_result = screener.screen_single(symbol)
        
        # Combine using signal aggregator
        aggregator = SignalAggregator(use_ai=False, scrape_news=False, use_fundamentals=True)
        
        if ta_result:
            final_signal = aggregator.aggregate_signal(ta_result)
            
            return ComprehensiveAnalysisResponse(
                symbol=symbol,
                overall_score=final_signal.final_confidence,
                verdict=final_signal.final_verdict,
                ta_confidence=final_signal.ta_confidence,
                ta_signals=[s.strategy_name for s in final_signal.ta_signals],
                pe_ratio=final_signal.pe_ratio,
                pb_ratio=final_signal.pb_ratio,
                roe=final_signal.roe,
                eps=final_signal.eps,
                valuation_verdict=final_signal.valuation_verdict,
                broker_signal=final_signal.broker_signal,
                top_buyers=final_signal.top_buyers,
                top_sellers=final_signal.top_sellers,
                entry_price=final_signal.entry_price,
                target_price=final_signal.target_price,
                stop_loss=final_signal.stop_loss,
                risk_reward=final_signal.risk_reward_ratio,
                position_size=final_signal.position_recommendation,
            )
        else:
            # No TA signal, return fundamental data only
            return ComprehensiveAnalysisResponse(
                symbol=symbol,
                overall_score=complete_analysis.overall_score,
                verdict="HOLD" if complete_analysis.overall_score >= 50 else "AVOID",
                ta_confidence=0,
                ta_signals=[],
                pe_ratio=complete_analysis.fundamentals.pe_ratio if complete_analysis.fundamentals else 0,
                pb_ratio=complete_analysis.fundamentals.pb_ratio if complete_analysis.fundamentals else 0,
                roe=complete_analysis.fundamentals.roe if complete_analysis.fundamentals else 0,
                eps=complete_analysis.fundamentals.eps if complete_analysis.fundamentals else 0,
                valuation_verdict="N/A",
                broker_signal=complete_analysis.broker_analysis.signal if complete_analysis.broker_analysis else "N/A",
                top_buyers=[b[0] for b in complete_analysis.broker_analysis.top_buyers[:3]] if complete_analysis.broker_analysis else [],
                top_sellers=[s[0] for s in complete_analysis.broker_analysis.top_sellers[:3]] if complete_analysis.broker_analysis else [],
                entry_price=0,
                target_price=0,
                stop_loss=0,
                risk_reward=0,
                position_size="N/A",
            )
            
    except Exception as e:
        logger.error(f"Failed comprehensive analysis for {symbol}: {e}")
        raise HTTPException(status_code=503, detail="Unable to perform analysis")


@app.get("/api/screen/fundamentals", tags=["Screening"])
async def screen_by_fundamentals(
    min_roe: float = Query(10.0, ge=0),
    max_pe: float = Query(30.0, ge=0),
    max_pb: float = Query(4.0, ge=0),
    min_eps: float = Query(10.0, ge=0),
    sector: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """
    Screen stocks by fundamental criteria.
    
    Find fundamentally strong stocks with good valuation.
    """
    try:
        from data.fetcher import NepseFetcher
        from analysis.fundamentals import FundamentalAnalyzer
        
        fetcher = NepseFetcher()
        analyzer = FundamentalAnalyzer()
        
        # Get all stocks
        stocks = fetcher.fetch_company_list()
        
        if sector:
            stocks = [s for s in stocks if sector.lower() in s.sector.lower()]
        
        results = []
        
        for stock in stocks[:100]:  # Limit to avoid timeout
            try:
                fundamentals = analyzer.get_fundamentals(stock.symbol)
                
                if not fundamentals:
                    continue
                
                # Apply filters
                if fundamentals.roe < min_roe:
                    continue
                if fundamentals.pe_ratio > max_pe or fundamentals.pe_ratio <= 0:
                    continue
                if fundamentals.pb_ratio > max_pb or fundamentals.pb_ratio <= 0:
                    continue
                if fundamentals.eps < min_eps:
                    continue
                
                score = analyzer._calculate_valuation_score(fundamentals)
                
                results.append({
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "sector": stock.sector,
                    "pe_ratio": fundamentals.pe_ratio,
                    "pb_ratio": fundamentals.pb_ratio,
                    "roe": fundamentals.roe,
                    "eps": fundamentals.eps,
                    "score": score,
                })
                
            except Exception:
                continue
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "data": results[:limit],
            "count": len(results),
            "filters": {
                "min_roe": min_roe,
                "max_pe": max_pe,
                "max_pb": max_pb,
                "min_eps": min_eps,
                "sector": sector,
            },
        }
        
    except Exception as e:
        logger.error(f"Fundamental screening failed: {e}")
        raise HTTPException(status_code=503, detail="Screening failed")


# ----- Startup/Shutdown -----

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("NEPSE AI Trading Bot API starting...")
    logger.info(f"Docs available at: http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("NEPSE AI Trading Bot API shutting down...")


# For running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
