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

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import json

from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.master_screener import MasterStockScreener, get_best_stocks, ScreenedStock
from data.fetcher import NepseFetcher


# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "paper_trading.db")


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
        
        # Print summary
        print("\n" + "=" * 70)
        print(f"📊 DAILY SCAN COMPLETE - {scan_date}")
        print("=" * 70)
        print(f"Market Regime: {'🐻 BEAR' if is_bear else '🐂 BULL'}")
        print(f"Stocks Saved: {len(results)}")
        print("\n📋 TODAY'S PAPER TRADES & ANALYSIS:")
        for rank, stock in enumerate(results, 1):
            raw_info = f"(Raw: {stock.raw_score:.1f})" if hasattr(stock, 'raw_score') and stock.raw_score > 100 else ""
            print(f"\n   #{rank} {stock.symbol:<10} Score: {stock.total_score:.0f}/100 {raw_info} | Entry: Rs.{stock.entry_price_with_slippage:.2f}")
            print(f"       🎯 Target: Rs.{stock.target_price:.2f} | 🛑 Stop: Rs.{stock.stop_loss_with_slippage:.2f}")
            
            # HOLDING PERIOD GUIDANCE (NEW!)
            expected_hold = getattr(stock, 'expected_holding_days', 7)
            max_hold = getattr(stock, 'max_holding_days', 15)
            exit_strategy = getattr(stock, 'exit_strategy', '')
            print(f"       📅 HOLD: {expected_hold}-{max_hold} days | ⏰ Exit if no movement by Day {max_hold}")
            
            # DISTRIBUTION RISK ALERT (VWAP-Based)
            dist_risk = getattr(stock, 'distribution_risk', '')
            broker_profit = getattr(stock, 'broker_profit_pct', 0)
            vwap_cost = getattr(stock, 'broker_avg_cost', 0)  # This is now VWAP
            dist_warning = getattr(stock, 'distribution_warning', '')
            
            if dist_risk and dist_risk != "N/A":
                risk_emoji = {"LOW": "✅", "MEDIUM": "⚡", "HIGH": "⚠️", "CRITICAL": "🚨"}.get(dist_risk, "❓")
                print(f"       {risk_emoji} DISTRIBUTION RISK: {dist_risk}")
                lookback = "14D" if strategy == "momentum" else "20D"
                print(f"          {lookback} VWAP: Rs.{vwap_cost:.2f} | Price Above VWAP: +{broker_profit:.1f}%")
                if dist_risk in ["HIGH", "CRITICAL"] and dist_warning:
                    print(f"          ⚠️ WARNING: {dist_warning}")
            
            # Detailed Breakdown for Stakeholders
            print(f"       🧠 WHY THIS STOCK? (Analysis Breakdown)")
            print(f"       ---------------------------------------")
            print(f"       1. Verdict: {stock.verdict_reason}")
            
            # Pillar Scores
            print(f"       2. Pillar Scores:")
            print(f"          • Broker/Inst: {stock.pillar1_broker:.1f}/{max_broker:.0f} (Buyer Dominance: {stock.buyer_dominance_pct:.1f}%)")
            print(f"          • Unlock Risk: {stock.pillar2_unlock:.1f}/{max_unlock:.0f} (Locked: {stock.locked_percentage:.1f}%)")
            print(f"          • Fundamental: {stock.pillar3_fundamental:.1f}/{max_fund:.0f} (PE: {stock.pe_ratio:.1f})")
            print(f"          • Technicals:  {stock.pillar4_technical:.1f}/{max_tech:.0f} (RSI: {stock.rsi:.1f})")
            
            # Specific Reasons
            if hasattr(stock, 'breakdown'):
                if stock.breakdown.technical_reasons:
                    print(f"       3. Key Signals: {', '.join(stock.breakdown.technical_reasons[:2])}")
                if stock.breakdown.bonuses:
                    print(f"       4. Bonuses: {', '.join(stock.breakdown.bonuses)}")
            
            # Show News & AI details if available
            if hasattr(stock, 'news_headlines') and stock.news_headlines:
                print(f"       📰 News Analysis: {stock.news_sentiment} ({len(stock.news_headlines)} articles)")
            
            if hasattr(stock, 'ai_verdict') and stock.ai_verdict:
                print(f"       🤖 AI Analyst Verdict: {stock.ai_verdict}")
                if hasattr(stock, 'ai_summary') and stock.ai_summary:
                    print(f"          Summary: \"{stock.ai_summary}\"")
                if hasattr(stock, 'ai_risks') and stock.ai_risks:
                    print(f"          Risks: \"{stock.ai_risks}\"")
        
        # Add Stakeholder Report
        self._print_stakeholder_report(results, total_analyzed=50 if quick_mode else 299, strategy=strategy)
        
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
        
        Returns:
            Comprehensive analysis dict
        """
        symbol = symbol.upper()
        logger.info("=" * 70)
        logger.info(f"🔍 DEEP STOCK ANALYSIS: {symbol}")
        logger.info("=" * 70)
        
        print("\n" + "=" * 70)
        print(f"🔍 COMPREHENSIVE ANALYSIS: {symbol}")
        print("   Analyzing with BOTH Value & Momentum strategies...")
        print("=" * 70)
        
        # Run analysis with BOTH strategies
        results = {}
        data_source_info = None  # Track if using historical data
        
        for strategy in ["value", "momentum"]:
            logger.info(f"   📊 Running {strategy.upper()} strategy analysis...")
            
            screener = MasterStockScreener(strategy=strategy)
            # Pass single_symbol to only load data for this stock (faster!)
            screener._preload_market_data(single_symbol=symbol)
            
            # Get the specific stock data - try live market first, fallback to historical
            try:
                target_stock = None
                
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
                
                # Try 2: If market closed, construct stock dict from historical + company details
                if not target_stock:
                    logger.info(f"   📅 Market closed - building stock data from historical prices for {symbol}")
                    
                    # Fetch recent historical OHLCV to get the last trading day's price
                    hist_df = self.fetcher.fetch_price_history(symbol, days=10)
                    
                    if hist_df is not None and not hist_df.empty:
                        # Get the most recent trading day
                        latest = hist_df.iloc[-1]
                        last_date = latest.get('date', 'unknown')
                        data_source_info = str(last_date)
                        
                        # Construct a minimal stock dict (handle None values)
                        # The full analysis (400-day history, indicators) happens inside _score_stock()
                        target_stock = {
                            'symbol': symbol,
                            'securityName': symbol,  # Will be updated below
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
                        
                        # Get company details for sector and name
                        try:
                            details = self.fetcher.fetch_company_details(symbol)
                            if details:
                                # Extract sector from nested structure
                                sector_name = ""
                                security = details.get('security', {})
                                company_id = security.get('companyId', {}) if security else {}
                                sector_master = company_id.get('sectorMaster', {}) if company_id else {}
                                if sector_master:
                                    sector_name = sector_master.get('sectorDescription', '')
                                
                                target_stock['sectorName'] = sector_name
                                
                                # Get company name
                                company_name = ""
                                if company_id:
                                    company_name = company_id.get('companyName', symbol)
                                elif security:
                                    company_name = security.get('securityName', symbol)
                                target_stock['securityName'] = company_name
                                target_stock['name'] = company_name
                        except Exception as e:
                            logger.debug(f"Could not fetch company details: {e}")
                        
                        if strategy == "value":  # Only print once
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
        
        # Basic Info
        print(f"\n💰 CURRENT PRICE: Rs. {best_result.ltp:.2f}")
        print(f"   Sector: {best_result.sector if hasattr(best_result, 'sector') else 'N/A'}")
        
        # Price Trend
        if isinstance(price_trend, dict):
            print(f"\n📈 PRICE TREND:")
            print(f"   7 Days:  {price_trend.get('7d', 0):+.2f}%")
            print(f"   30 Days: {price_trend.get('30d', 0):+.2f}%")
            print(f"   90 Days: {price_trend.get('90d', 0):+.2f}%")
            print(f"   1 Year:  {price_trend.get('1y', 0):+.2f}%")
        
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
            print(f"   ROE:         {fundamentals.roe:.2f}%" + (" ✅ GOOD" if fundamentals.roe > 12 else " ⚠️ LOW" if fundamentals.roe < 5 else ""))
        else:
            print("   Fundamental data not available")
        
        # Dividend History
        print("\n" + "-" * 70)
        print("💵 DIVIDEND HISTORY (Last 3 Years)")
        print("-" * 70)
        if dividends:
            total_div = 0
            for div in dividends[:3]:
                cash = getattr(div, 'cash_dividend', 0) or 0
                bonus = getattr(div, 'bonus_dividend', 0) or 0
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
        print("📉 BROKER DISTRIBUTION RISK")
        print("-" * 70)
        if best_result.distribution_risk:
            risk_emoji = {"LOW": "✅", "MEDIUM": "⚡", "HIGH": "⚠️", "CRITICAL": "🚨"}.get(best_result.distribution_risk, "❓")
            print(f"   {risk_emoji} Risk Level: {best_result.distribution_risk}")
            print(f"   Broker Avg Cost:    Rs. {best_result.broker_avg_cost:.2f}")
            print(f"   Current LTP:        Rs. {best_result.ltp:.2f}")
            print(f"   Broker Profit:      +{best_result.broker_profit_pct:.1f}%")
            if best_result.distribution_warning:
                print(f"   {best_result.distribution_warning}")
        else:
            print("   Distribution risk data not available")
        
        # Technical Indicators
        print("\n" + "-" * 70)
        print("📊 TECHNICAL INDICATORS")
        print("-" * 70)
        print(f"   RSI (14):      {best_result.rsi:.1f}" + (" ⚠️ OVERBOUGHT" if best_result.rsi > 70 else " ⚠️ OVERSOLD" if best_result.rsi < 30 else " ✅ NEUTRAL"))
        print(f"   EMA Signal:    {best_result.ema_signal}")
        print(f"   Volume Spike:  {best_result.volume_spike:.2f}x" + (" 🔥 HIGH" if best_result.volume_spike > 2 else ""))
        # ATR check - 0 means calculation failed
        if best_result.atr > 0:
            print(f"   ATR:           Rs. {best_result.atr:.2f}")
        else:
            print(f"   ATR:           ❌ Could not calculate (insufficient data)")
        
        # Trade Plan
        print("\n" + "-" * 70)
        print("🎯 SUGGESTED TRADE PLAN")
        print("-" * 70)
        print(f"   Entry Price:   Rs. {best_result.entry_price_with_slippage:.2f} (with 1.5% slippage)")
        print(f"   Target (+10%): Rs. {best_result.target_price:.2f}")
        print(f"   Stop Loss:     Rs. {best_result.stop_loss_with_slippage:.2f} (-6.5% with slippage)")
        print(f"   Expected Hold: {best_result.expected_holding_days}-{best_result.max_holding_days} days")
        print(f"   Exit Strategy: {best_result.exit_strategy}")
        
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
            total_div = sum((getattr(d, 'cash_dividend', 0) or 0) + (getattr(d, 'bonus_dividend', 0) or 0) for d in dividends[:3])
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
        if momentum_score >= 70 and not red_flags:
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
    default=None,
    choices=[
        "bank", "devbank", "finance", "microfinance", 
        "hydro", "life_insurance", "non_life_insurance", 
        "hotel", "manufacturing", "trading", "investment", "others"
    ],
    help="Filter scan by a specific NEPSE sector (e.g., 'hydro', 'finance')."
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

    args = parser.parse_args()
    
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
            
            result = trader.analyze_single_stock(
                symbol=stock_symbol.upper(),
                with_news=args.with_news or args.full,
                with_ai=args.with_ai or args.full,
                headless=not args.visible,
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
