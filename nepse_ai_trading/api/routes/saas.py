"""
SaaS API Routes - Core endpoints for the Next.js frontend.

Provides clean JSON endpoints for:
- Market Scanner (4-Pillar Analysis)
- Stealth Radar (Sector Rotation)
- Portfolio Management
- Single Stock Analysis
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import math

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from loguru import logger

router = APIRouter(prefix="/api", tags=["SaaS"])


def _normalize_company_list(company_list: Any) -> List[Dict[str, Any]]:
    """
    Normalize company list into dict records so API routes can safely access keys.
    NepseFetcher.fetch_company_list() returns List[StockData], while older code
    expected a pandas DataFrame; this bridge prevents runtime type crashes.
    """
    normalized: List[Dict[str, Any]] = []
    if not company_list:
        return normalized

    for item in company_list:
        if isinstance(item, dict):
            symbol = str(item.get("symbol", "")).upper()
            if symbol:
                normalized.append({
                    "symbol": symbol,
                    "name": item.get("name", item.get("securityName", item.get("companyName", symbol))),
                    "sector": item.get("sector", item.get("sectorName", "Unknown")) or "Unknown",
                })
            continue

        symbol = str(getattr(item, "symbol", "")).upper()
        if symbol:
            normalized.append({
                "symbol": symbol,
                "name": getattr(item, "name", symbol) or symbol,
                "sector": getattr(item, "sector", "Unknown") or "Unknown",
            })

    return normalized


def _to_float(value: Any, default: float = 0.0) -> float:
    """Best-effort numeric conversion for mixed API payloads."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_live_price(row: Any) -> float:
    """
    Extract a usable market price from live market row data.
    Supports mixed payloads where price may come as ltp/close/lastTradedPrice.
    """
    if row is None:
        return 0.0

    # pandas.Series supports `.get`, sqlite row / dict support item access
    get_value = row.get if hasattr(row, "get") else lambda key, default=None: row[key] if key in row else default
    for key in ("ltp", "close", "lastTradedPrice", "last_traded_price", "open"):
        price = _to_float(get_value(key, 0.0), 0.0)
        if price > 0:
            return price
    return 0.0


def _is_valid_price(value: Any) -> bool:
    """True only for finite positive prices."""
    price = _to_float(value, 0.0)
    return math.isfinite(price) and price > 0


# ============== Pydantic Models ==============

class PillarScore(BaseModel):
    """Individual pillar score."""
    name: str
    score: float
    max_score: float
    percentage: float


class StockScanResult(BaseModel):
    """Stock scan result for frontend table."""
    rank: int
    symbol: str
    name: str = ""
    sector: str
    ltp: float
    score: int
    verdict: str
    verdict_emoji: str
    
    # Trade Plan
    entry_price: float
    target_price: float
    stop_loss: float
    hold_days: str
    
    # Pillar Breakdown
    pillar_broker: float
    pillar_unlock: float
    pillar_fundamental: float
    pillar_technical: float
    
    # Risk Data
    distribution_risk: str
    distribution_risk_emoji: str
    broker_profit_pct: float
    vwap_cost: float
    
    # Additional
    rsi: float
    volume_spike: float
    buyer_dominance: float
    pe_ratio: float
    roe: float
    
    # Signals
    key_signals: List[str] = []
    red_flags: List[str] = []


class ScanResponse(BaseModel):
    """Response for scan endpoint."""
    success: bool
    timestamp: str
    market_regime: str
    market_regime_emoji: str
    strategy: str
    sector: Optional[str]
    total_analyzed: int
    results: List[StockScanResult]


class StealthStock(BaseModel):
    """Stock with stealth accumulation detected."""
    symbol: str
    sector: str
    ltp: float
    broker_score: float
    broker_score_pct: float
    technical_score: float
    technical_score_pct: float
    distribution_risk: str
    broker_profit_pct: float
    buyer_dominance: float


class SectorRotation(BaseModel):
    """Sector with stealth accumulation activity."""
    sector: str
    stock_count: int
    avg_broker_score: float
    stocks: List[StealthStock]


class StealthResponse(BaseModel):
    """Response for stealth-scan endpoint."""
    success: bool
    timestamp: str
    total_stealth_stocks: int
    sectors: List[SectorRotation]


class PortfolioPosition(BaseModel):
    """Open position in portfolio."""
    id: int
    symbol: str
    entry_date: str
    entry_price: float
    quantity: int
    current_price: float
    target_price: float
    stop_loss: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    days_held: int
    status: str  # "OPEN", "TARGET_HIT", "STOP_HIT", "EXPIRED"


class PortfolioStats(BaseModel):
    """Portfolio statistics."""
    total_trades: int
    open_positions: int
    closed_positions: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float


class PortfolioResponse(BaseModel):
    """Response for portfolio status."""
    success: bool
    timestamp: str
    stats: PortfolioStats
    positions: List[PortfolioPosition]


class SingleStockAnalysis(BaseModel):
    """Deep analysis for a single stock."""
    symbol: str
    name: str
    sector: str
    ltp: float
    
    # Overall Scores
    momentum_score: int
    value_score: int
    momentum_verdict: str
    value_verdict: str
    
    # Pillar Details (for visualization)
    pillars: Dict[str, PillarScore]
    
    # Fundamentals
    pe_ratio: float
    pe_status: str
    eps: float
    eps_annualized: float
    book_value: float
    pbv: float
    roe: float
    roe_status: str
    
    # Technical
    rsi: float
    rsi_status: str
    ema_signal: str
    volume_spike: float
    atr: float
    
    # Distribution Risk
    distribution_risk: str
    broker_avg_cost: float
    broker_profit_pct: float
    distribution_warning: str
    
    # Trade Plan
    entry_price: float
    target_price: float
    stop_loss: float
    hold_days: str
    
    # Recommendations
    long_term_recommendation: str
    short_term_recommendation: str
    friend_recommendation: str
    
    # Red Flags
    red_flags: List[str]
    
    # Price History (for mini chart)
    price_history_7d: List[Dict[str, Any]] = []
    price_trend_7d: float
    price_trend_30d: float
    price_trend_90d: float


class AnalyzeResponse(BaseModel):
    """Response for single stock analysis."""
    success: bool
    timestamp: str
    data: SingleStockAnalysis


class MarketRegimeResponse(BaseModel):
    """Current market regime."""
    regime: str
    regime_emoji: str
    reason: str
    nepse_index: float
    ema50: float
    timestamp: str


# ============== API Endpoints ==============

@router.get("/scan", response_model=ScanResponse)
async def run_market_scan(
    strategy: str = Query("momentum", enum=["momentum", "value"]),
    sector: Optional[str] = Query(None),
    quick: bool = Query(True),
    max_price: Optional[float] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Run the 4-Pillar AI Market Scanner.
    
    Returns top stocks based on the selected strategy.
    """
    try:
        from analysis.master_screener import MasterStockScreener
        
        logger.info(f"API Scan: strategy={strategy}, sector={sector}, quick={quick}")
        
        # Initialize screener
        screener = MasterStockScreener(
            strategy=strategy,
            target_sector=sector,
            max_price=max_price
        )
        
        # Check market regime
        regime, regime_reason = screener.check_market_regime()
        regime_emoji = {"BULL": "🐂", "BEAR": "🐻", "PANIC": "🚨"}.get(regime, "⚪")
        
        # Run analysis
        results = screener.run_full_analysis(quick_mode=quick)
        
        # Convert to response format
        scan_results = []
        for i, stock in enumerate(results[:limit], 1):
            # Determine verdict emoji
            score = stock.total_score
            if score >= 85:
                verdict_emoji = "🏆"
                verdict = "EXCELLENT"
            elif score >= 70:
                verdict_emoji = "🟢"
                verdict = "GOOD"
            elif score >= 55:
                verdict_emoji = "🟡"
                verdict = "AVERAGE"
            else:
                verdict_emoji = "🔴"
                verdict = "WEAK"
            
            # Distribution risk emoji
            dist_risk = getattr(stock, 'distribution_risk', 'N/A')
            dist_emoji = {"LOW": "✅", "MEDIUM": "⚡", "HIGH": "⚠️", "CRITICAL": "🚨"}.get(dist_risk, "❓")
            
            scan_results.append(StockScanResult(
                rank=i,
                symbol=stock.symbol,
                name=getattr(stock, 'name', ''),
                sector=stock.sector,
                ltp=stock.ltp,
                score=int(stock.total_score),
                verdict=verdict,
                verdict_emoji=verdict_emoji,
                entry_price=stock.entry_price,
                target_price=stock.target_price,
                stop_loss=stock.stop_loss,
                hold_days=stock.exit_strategy.split(':')[0].replace('📅 ', '') if hasattr(stock, 'exit_strategy') else "5-10 days",
                pillar_broker=stock.pillar1_broker,
                pillar_unlock=stock.pillar2_unlock,
                pillar_fundamental=stock.pillar3_fundamental,
                pillar_technical=stock.pillar4_technical,
                distribution_risk=dist_risk,
                distribution_risk_emoji=dist_emoji,
                broker_profit_pct=getattr(stock, 'broker_profit_pct', 0),
                vwap_cost=getattr(stock, 'broker_avg_cost', 0),
                rsi=stock.rsi,
                volume_spike=stock.volume_spike,
                buyer_dominance=stock.buyer_dominance_pct,
                pe_ratio=stock.pe_ratio,
                roe=stock.roe,
                key_signals=getattr(stock, 'key_signals', []),
                red_flags=getattr(stock, 'red_flags', []),
            ))
        
        return ScanResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            market_regime=regime,
            market_regime_emoji=regime_emoji,
            strategy=strategy.upper(),
            sector=sector,
            total_analyzed=len(results),
            results=scan_results,
        )
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stealth-scan", response_model=StealthResponse)
async def run_stealth_scan(
    sector: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
):
    """
    Run the Stealth Radar - Detect Smart Money Accumulation.
    
    Finds stocks where:
    - Technical Score is LOW (price hasn't broken out)
    - Broker Score is HIGH (heavy institutional buying)
    - Distribution Risk is LOW (brokers not selling)
    """
    try:
        from analysis.master_screener import MasterStockScreener
        
        logger.info(f"API Stealth Scan: sector={sector}")
        
        # Initialize screener
        screener = MasterStockScreener(
            strategy="momentum",
            target_sector=sector,
            max_price=max_price
        )
        
        # Run full analysis to get all scores
        results = screener.run_full_analysis(quick_mode=False)
        
        # Filter for stealth criteria
        stealth_stocks = []
        for stock in results:
            tech_score = stock.pillar4_technical
            broker_score = stock.pillar1_broker
            dist_risk = getattr(stock, 'distribution_risk', 'N/A')
            
            # Stealth criteria: Low tech (<40%), High broker (>80%), Low risk
            max_tech = 40.0  # Max for momentum
            max_broker = 30.0
            
            tech_pct = (tech_score / max_tech) * 100 if max_tech > 0 else 0
            broker_pct = (broker_score / max_broker) * 100 if max_broker > 0 else 0
            
            if tech_pct < 40 and broker_pct > 70 and dist_risk == "LOW":
                stealth_stocks.append(StealthStock(
                    symbol=stock.symbol,
                    sector=stock.sector,
                    ltp=stock.ltp,
                    broker_score=broker_score,
                    broker_score_pct=broker_pct,
                    technical_score=tech_score,
                    technical_score_pct=tech_pct,
                    distribution_risk=dist_risk,
                    broker_profit_pct=getattr(stock, 'broker_profit_pct', 0),
                    buyer_dominance=stock.buyer_dominance_pct,
                ))
        
        # Group by sector
        sector_map: Dict[str, List[StealthStock]] = {}
        for stock in stealth_stocks:
            if stock.sector not in sector_map:
                sector_map[stock.sector] = []
            sector_map[stock.sector].append(stock)
        
        sectors = []
        for sector_name, stocks in sorted(sector_map.items(), key=lambda x: -len(x[1])):
            avg_broker = sum(s.broker_score for s in stocks) / len(stocks) if stocks else 0
            sectors.append(SectorRotation(
                sector=sector_name,
                stock_count=len(stocks),
                avg_broker_score=round(avg_broker, 1),
                stocks=stocks,
            ))
        
        return StealthResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            total_stealth_stocks=len(stealth_stocks),
            sectors=sectors,
        )
        
    except Exception as e:
        logger.error(f"Stealth scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-regime", response_model=MarketRegimeResponse)
async def get_market_regime():
    """Get current market regime (Bull/Bear/Panic)."""
    try:
        from analysis.master_screener import MasterStockScreener
        
        screener = MasterStockScreener(strategy="momentum")
        regime, reason = screener.check_market_regime()
        
        # Get NEPSE index data
        from data.fetcher import NepseFetcher
        fetcher = NepseFetcher()
        index_df = fetcher.fetch_index_history(days=60)
        
        nepse_index = float(index_df['close'].iloc[-1]) if not index_df.empty else 0
        ema50 = float(index_df['close'].ewm(span=50).mean().iloc[-1]) if len(index_df) >= 50 else 0
        
        regime_emoji = {"BULL": "🐂", "BEAR": "🐻", "PANIC": "🚨"}.get(regime, "⚪")
        
        return MarketRegimeResponse(
            regime=regime,
            regime_emoji=regime_emoji,
            reason=reason,
            nepse_index=round(nepse_index, 2),
            ema50=round(ema50, 2),
            timestamp=datetime.now().isoformat(),
        )
        
    except Exception as e:
        logger.error(f"Market regime check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/status", response_model=PortfolioResponse)
async def get_portfolio_status():
    """Get current portfolio status and statistics."""
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        
        # Create empty portfolio response helper
        def empty_portfolio():
            return PortfolioResponse(
                success=True,
                timestamp=datetime.now().isoformat(),
                stats=PortfolioStats(
                    total_trades=0,
                    open_positions=0,
                    closed_positions=0,
                    wins=0,
                    losses=0,
                    win_rate=0.0,
                    total_pnl=0.0,
                    avg_win=0.0,
                    avg_loss=0.0,
                    best_trade=0.0,
                    worst_trade=0.0,
                ),
                positions=[],
            )
        
        if not db_path.exists():
            return empty_portfolio()
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if trades table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if not cursor.fetchone():
            conn.close()
            return empty_portfolio()
        
        # Get open positions
        cursor.execute("""
            SELECT * FROM trades 
            WHERE status = 'OPEN' 
            ORDER BY entry_date DESC
        """)
        open_trades = cursor.fetchall()
        
        # Get closed trades for stats
        cursor.execute("""
            SELECT * FROM trades 
            WHERE status != 'OPEN'
        """)
        closed_trades = cursor.fetchall()
        
        # Calculate stats
        wins = sum(1 for t in closed_trades if t['pnl'] and t['pnl'] > 0)
        losses = sum(1 for t in closed_trades if t['pnl'] and t['pnl'] < 0)
        total_pnl = sum(t['pnl'] or 0 for t in closed_trades)
        
        win_pnls = [t['pnl'] for t in closed_trades if t['pnl'] and t['pnl'] > 0]
        loss_pnls = [t['pnl'] for t in closed_trades if t['pnl'] and t['pnl'] < 0]
        
        # Get current prices for open positions (skip if no open trades)
        positions = []
        if open_trades:
            from data.fetcher import NepseFetcher
            fetcher = NepseFetcher()
            live_data = fetcher.fetch_live_market()
            
            price_map = {}
            if not live_data.empty:
                for _, row in live_data.iterrows():
                    symbol = str(row.get('symbol', '')).upper()
                    if not symbol:
                        continue
                    live_price = _extract_live_price(row)
                    if live_price > 0:
                        price_map[symbol] = live_price
            
            for trade in open_trades:
                current_price = price_map.get(trade['symbol'], trade['entry_price'])
                unrealized_pnl = (current_price - trade['entry_price']) * trade['quantity']
                unrealized_pnl_pct = ((current_price / trade['entry_price']) - 1) * 100
                
                entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d')
                days_held = (datetime.now() - entry_date).days
                
                positions.append(PortfolioPosition(
                    id=trade['id'],
                    symbol=trade['symbol'],
                    entry_date=trade['entry_date'],
                    entry_price=trade['entry_price'],
                    quantity=trade['quantity'],
                    current_price=current_price,
                    target_price=trade['target_price'],
                    stop_loss=trade['stop_loss'],
                    unrealized_pnl=round(unrealized_pnl, 2),
                    unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
                    days_held=days_held,
                    status="OPEN",
                ))
        
        conn.close()
        
        return PortfolioResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            stats=PortfolioStats(
                total_trades=len(open_trades) + len(closed_trades),
                open_positions=len(open_trades),
                closed_positions=len(closed_trades),
                wins=wins,
                losses=losses,
                win_rate=round((wins / len(closed_trades) * 100) if closed_trades else 0, 1),
                total_pnl=round(total_pnl, 2),
                avg_win=round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0,
                avg_loss=round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0,
                best_trade=round(max(win_pnls), 2) if win_pnls else 0,
                worst_trade=round(min(loss_pnls), 2) if loss_pnls else 0,
            ),
            positions=positions,
        )
        
    except Exception as e:
        logger.error(f"Portfolio status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/update")
async def update_portfolio():
    """
    Check all open positions against current prices.
    Updates status if target or stop-loss is hit.
    """
    try:
        import sqlite3
        from pathlib import Path
        from data.fetcher import NepseFetcher
        
        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        
        if not db_path.exists():
            return {"success": True, "message": "No portfolio database found", "updates": []}
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if trades table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if not cursor.fetchone():
            conn.close()
            return {"success": True, "message": "No trades yet - portfolio empty", "updates": []}
        
        # Get open positions
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
        open_trades = cursor.fetchall()
        
        if not open_trades:
            conn.close()
            return {"success": True, "message": "No open positions", "updates": []}
        
        # Get current prices
        fetcher = NepseFetcher()
        live_data = fetcher.fetch_live_market()
        
        price_map = {}
        if not live_data.empty:
            for _, row in live_data.iterrows():
                symbol = str(row.get('symbol', '')).upper()
                if not symbol:
                    continue
                live_price = _extract_live_price(row)
                if live_price > 0:
                    price_map[symbol] = live_price
        
        updates = []
        for trade in open_trades:
            current_price = price_map.get(trade['symbol'])
            if current_price is None:
                continue
            
            new_status = None
            pnl = 0
            
            if current_price >= trade['target_price']:
                new_status = "TARGET_HIT"
                pnl = (trade['target_price'] - trade['entry_price']) * trade['quantity']
            elif current_price <= trade['stop_loss']:
                new_status = "STOP_HIT"
                pnl = (trade['stop_loss'] - trade['entry_price']) * trade['quantity']
            
            if new_status:
                cursor.execute("""
                    UPDATE trades 
                    SET status = ?, exit_price = ?, exit_date = ?, pnl = ?
                    WHERE id = ?
                """, (new_status, current_price, datetime.now().strftime('%Y-%m-%d'), pnl, trade['id']))
                
                updates.append({
                    "symbol": trade['symbol'],
                    "old_status": "OPEN",
                    "new_status": new_status,
                    "pnl": round(pnl, 2),
                })
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "updates": updates,
            "message": f"Updated {len(updates)} positions",
        }
        
    except Exception as e:
        logger.error(f"Portfolio update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/{symbol}", response_model=AnalyzeResponse)
async def analyze_single_stock(
    symbol: str,
    strategy: str = Query("momentum", enum=["momentum", "value"]),
):
    """
    Deep 4-Pillar analysis for a single stock.
    
    Returns comprehensive data including:
    - All 4 pillar scores with breakdown
    - Fundamentals (PE, EPS, ROE, etc.)
    - Technical indicators (RSI, EMA, Volume)
    - Distribution risk analysis
    - Trade plan with entry/target/stop-loss
    - Red flags and recommendations
    """
    try:
        from analysis.master_screener import MasterStockScreener
        from data.fetcher import NepseFetcher
        
        symbol = symbol.upper()
        logger.info(f"API Analyze: symbol={symbol}, strategy={strategy}")
        
        # Initialize screener
        screener = MasterStockScreener(strategy=strategy)
        
        # Get live price
        fetcher = NepseFetcher()
        live_data = fetcher.fetch_live_market()
        
        ltp = 0.0
        if not live_data.empty:
            stock_row = live_data[live_data['symbol'] == symbol]
            if not stock_row.empty:
                ltp = _extract_live_price(stock_row.iloc[0])
        
        # If no live data, try historical
        if not _is_valid_price(ltp):
            history = fetcher.fetch_price_history(symbol, days=7)
            if history is not None and not history.empty:
                ltp = _to_float(history['close'].iloc[-1], 0.0)
        
        if not _is_valid_price(ltp):
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
        
        # Get company info
        company_list = fetcher.fetch_company_list()
        normalized_companies = _normalize_company_list(company_list)
        company_info = next((c for c in normalized_companies if c["symbol"] == symbol), None)
        name = company_info["name"] if company_info else symbol
        sector = company_info["sector"] if company_info else "Unknown"
        
        # Run scoring
        screener._preload_market_data()
        
        # Build minimal market data for single stock
        market_data = [{
            'symbol': symbol,
            'ltp': ltp,
            'lastTradedPrice': ltp,
            'close': ltp,
            'open': ltp,
            'high': ltp,
            'low': ltp,
            'volume': 0,
            'turnover': 0,
            'change_pct': 0,
        }]
        
        # Score the stock
        stock_result = screener._score_stock(market_data[0])
        
        if not stock_result:
            raise HTTPException(status_code=404, detail=f"Insufficient market data for {symbol}")
        
        # Get price history for trends
        history = fetcher.fetch_price_history(symbol, days=100)
        price_trend_7d = 0
        price_trend_30d = 0
        price_trend_90d = 0
        price_history_7d = []
        
        if history is not None and not history.empty:
            if len(history) >= 7:
                price_trend_7d = ((ltp / history['close'].iloc[-7]) - 1) * 100
                price_history_7d = [
                    {"date": str(row['date']), "close": row['close']}
                    for _, row in history.tail(7).iterrows()
                ]
            if len(history) >= 30:
                price_trend_30d = ((ltp / history['close'].iloc[-30]) - 1) * 100
            if len(history) >= 90:
                price_trend_90d = ((ltp / history['close'].iloc[-90]) - 1) * 100
        
        # Build pillar details
        max_broker = 30.0
        max_unlock = 20.0
        max_fund = 20.0 if strategy == "value" else 10.0
        max_tech = 30.0 if strategy == "value" else 40.0
        
        pillars = {
            "broker": PillarScore(
                name="Broker/Institutional",
                score=stock_result.pillar1_broker,
                max_score=max_broker,
                percentage=round((stock_result.pillar1_broker / max_broker) * 100, 1),
            ),
            "unlock": PillarScore(
                name="Unlock Risk",
                score=stock_result.pillar2_unlock,
                max_score=max_unlock,
                percentage=round((stock_result.pillar2_unlock / max_unlock) * 100, 1),
            ),
            "fundamental": PillarScore(
                name="Fundamentals",
                score=stock_result.pillar3_fundamental,
                max_score=max_fund,
                percentage=round((stock_result.pillar3_fundamental / max_fund) * 100, 1),
            ),
            "technical": PillarScore(
                name="Technicals",
                score=stock_result.pillar4_technical,
                max_score=max_tech,
                percentage=round((stock_result.pillar4_technical / max_tech) * 100, 1),
            ),
        }
        
        # Determine statuses
        pe_ratio = stock_result.pe_ratio
        if pe_ratio <= 0:
            pe_status = "❌ MISSING/NEGATIVE"
        elif pe_ratio < 15:
            pe_status = "✅ CHEAP"
        elif pe_ratio <= 25:
            pe_status = "✅ FAIR"
        elif pe_ratio <= 40:
            pe_status = "⚠️ EXPENSIVE"
        else:
            pe_status = "🔴 OVERVALUED"
        
        roe = stock_result.roe
        if roe >= 15:
            roe_status = "✅ EXCELLENT"
        elif roe >= 10:
            roe_status = "✅ GOOD"
        elif roe >= 5:
            roe_status = "⚠️ AVERAGE"
        else:
            roe_status = "🔴 POOR"
        
        rsi = stock_result.rsi
        if rsi > 70:
            rsi_status = "⚠️ OVERBOUGHT"
        elif rsi < 30:
            rsi_status = "⚠️ OVERSOLD"
        elif 50 <= rsi <= 65:
            rsi_status = "✅ BULLISH MOMENTUM"
        else:
            rsi_status = "✅ NEUTRAL"
        
        # Recommendations
        score = stock_result.total_score
        momentum_verdict = "🏆 EXCELLENT" if score >= 85 else "🟢 GOOD" if score >= 70 else "🟡 AVERAGE" if score >= 55 else "🔴 WEAK"
        
        # Build red flags
        red_flags = getattr(stock_result, 'red_flags', [])
        
        # Long/Short term recommendations
        if score >= 70 and roe >= 10:
            long_term_rec = "✅ RECOMMENDED"
        elif score >= 55:
            long_term_rec = "🟡 CAUTION"
        else:
            long_term_rec = "❌ NOT RECOMMENDED"
        
        if score >= 75:
            short_term_rec = "✅ GOOD ENTRY"
        elif score >= 60:
            short_term_rec = "🟡 RISKY"
        else:
            short_term_rec = "❌ AVOID"
        
        friend_rec = "🟢 Good pick!" if score >= 75 else "🟡 Average" if score >= 55 else "🔴 Better options exist"
        
        analysis = SingleStockAnalysis(
            symbol=symbol,
            name=name,
            sector=sector,
            ltp=ltp,
            momentum_score=int(stock_result.total_score),
            value_score=int(stock_result.total_score),  # Would need separate run
            momentum_verdict=momentum_verdict,
            value_verdict=momentum_verdict,
            pillars=pillars,
            pe_ratio=pe_ratio,
            pe_status=pe_status,
            eps=getattr(stock_result, 'eps', 0),
            eps_annualized=getattr(stock_result, 'eps_annualized', 0),
            book_value=getattr(stock_result, 'book_value', 0),
            pbv=getattr(stock_result, 'pbv', 0),
            roe=roe,
            roe_status=roe_status,
            rsi=rsi,
            rsi_status=rsi_status,
            ema_signal=stock_result.ema_signal,
            volume_spike=stock_result.volume_spike,
            atr=getattr(stock_result, 'atr', 0),
            distribution_risk=getattr(stock_result, 'distribution_risk', 'N/A'),
            broker_avg_cost=getattr(stock_result, 'broker_avg_cost', 0),
            broker_profit_pct=getattr(stock_result, 'broker_profit_pct', 0),
            distribution_warning=getattr(stock_result, 'distribution_warning', ''),
            entry_price=stock_result.entry_price,
            target_price=stock_result.target_price,
            stop_loss=stock_result.stop_loss,
            hold_days=stock_result.exit_strategy.split(':')[0].replace('📅 ', '') if hasattr(stock_result, 'exit_strategy') else "5-10 days",
            long_term_recommendation=long_term_rec,
            short_term_recommendation=short_term_rec,
            friend_recommendation=friend_rec,
            red_flags=red_flags,
            price_history_7d=price_history_7d,
            price_trend_7d=round(price_trend_7d, 2),
            price_trend_30d=round(price_trend_30d, 2),
            price_trend_90d=round(price_trend_90d, 2),
        )
        
        return AnalyzeResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data=analysis,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/buy")
async def add_to_portfolio(
    symbol: str = Body(...),
    quantity: int = Body(...),
    price: float = Body(...),
):
    """Add a stock to the paper trading portfolio."""
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        
        # Initialize DB if needed
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                target_price REAL,
                stop_loss REAL,
                exit_date TEXT,
                exit_price REAL,
                pnl REAL,
                status TEXT DEFAULT 'OPEN'
            )
        """)
        
        # Calculate target and stop-loss (10% and -6.5%)
        target_price = round(price * 1.10, 2)
        stop_loss = round(price * 0.935, 2)
        
        cursor.execute("""
            INSERT INTO trades (symbol, entry_date, entry_price, quantity, target_price, stop_loss, status)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN')
        """, (symbol.upper(), datetime.now().strftime('%Y-%m-%d'), price, quantity, target_price, stop_loss))
        
        conn.commit()
        trade_id = cursor.lastrowid
        conn.close()
        
        return {
            "success": True,
            "message": f"Added {quantity} shares of {symbol} at Rs.{price}",
            "trade_id": trade_id,
            "target_price": target_price,
            "stop_loss": stop_loss,
        }
        
    except Exception as e:
        logger.error(f"Buy failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
