"""
NEPSE AI Trading Bot - Main Orchestrator

This is the main entry point that runs the complete trading analysis pipeline.

Usage:
    python main.py                  # Run full analysis
    python main.py --fetch-only     # Only fetch data
    python main.py --screen-only    # Only run screener
    python main.py --dry-run        # Run without notifications
"""

import argparse
import sys
from datetime import datetime
from loguru import logger

from core.config import settings
from core.database import init_db
from core.logging_config import setup_logging
from core.exceptions import NepseAIException

from data.fetcher import NepseFetcher, save_prices_to_db
from analysis.screener import StockScreener
from analysis.master_screener import MasterStockScreener, ScreenedStock
from intelligence.signal_aggregator import SignalAggregator, FinalSignal
from notifications.telegram_bot import send_telegram_alert, send_daily_summary


def run_data_fetch() -> bool:
    """
    Fetch today's market data.
    
    Returns:
        True if successful
    """
    logger.info("=" * 50)
    logger.info("STEP 1: Fetching market data...")
    logger.info("=" * 50)
    
    try:
        fetcher = NepseFetcher()
        
        # Fetch today's prices
        df = fetcher.fetch_live_market()
        
        if df.empty:
            logger.warning("No price data received. Market may be closed.")
            return False
        
        # Save to database
        saved = save_prices_to_db(df)
        logger.info(f"Saved {saved} price records to database")
        
        # Fetch market summary
        market = fetcher.fetch_market_summary()
        logger.info(f"NEPSE Index: {market.nepse_index} ({market.nepse_change_pct}%)")
        logger.info(f"Market: {market.advances} ↑ | {market.declines} ↓ | {market.unchanged} →")
        
        return True
        
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        return False


def run_screener(strategy: str = "value", sector: str = None, quick_mode: bool = False) -> list:
    """
    Run the 4-Pillar Master Screener.

    Returns:
        List of ScreenedStock objects
    """
    logger.info("=" * 50)
    logger.info("STEP 2: Running 4-Pillar Master Screener...")
    logger.info("=" * 50)

    try:
        screener = MasterStockScreener(strategy=strategy, target_sector=sector)
        results = screener.run_full_analysis(min_score=60, top_n=10, quick_mode=quick_mode)

        if not results:
            logger.info("No stocks passed scoring criteria today.")
            return []

        logger.info(f"Found {len(results)} high-scoring stocks (score >= 60)")

        # Log top signals
        for i, stock in enumerate(results[:5], 1):
            logger.info(
                f"  {i}. {stock.symbol}: {stock.recommendation} "
                f"(score: {stock.total_score:.1f}/100 | CSS: {getattr(stock, 'css_score', 'N/A')})"
            )

        return results

    except Exception as e:
        logger.error(f"Master screener failed: {e}")
        return []


def run_intelligence(results: list) -> list:
    """
    Convert MasterStockScreener results into FinalSignal objects.
    MasterStockScreener already performs comprehensive analysis (4 pillars + manipulation
    detection + distribution risk), so we convert directly without re-running AI analysis.

    Args:
        results: List of ScreenedStock from MasterStockScreener

    Returns:
        List of FinalSignals
    """
    logger.info("=" * 50)
    logger.info("STEP 3: Preparing final signals...")
    logger.info("=" * 50)

    from datetime import date as date_cls

    signals = []

    for stock in results:
        try:
            # Map master screener recommendation to FinalSignal verdict
            verdict_map = {
                "STRONG BUY": "STRONG_BUY",
                "BUY": "BUY",
                "WEAK BUY": "BUY",
                "SPECULATIVE": "HOLD",
            }
            verdict = verdict_map.get(stock.recommendation.upper(), "HOLD")

            signal = FinalSignal(
                symbol=stock.symbol,
                date=date_cls.today(),
                ta_confidence=stock.pillar4_technical / 3.0,  # /30 * 10 → score out of 10
                primary_strategy="MasterScreener",
                pe_ratio=stock.pe_ratio,
                pb_ratio=stock.pbv,
                roe=stock.roe,
                eps=stock.eps,
                final_verdict=verdict,
                final_confidence=stock.total_score / 10.0,  # 0-10 scale
                entry_price=stock.entry_price_with_slippage,
                target_price=stock.target_price,
                stop_loss=stock.stop_loss_with_slippage,
                risk_reward_ratio=stock.risk_reward_ratio,
                reasoning=stock.verdict_reason,
            )
            signals.append(signal)
        except Exception as e:
            logger.error(f"Failed to convert signal for {getattr(stock, 'symbol', '?')}: {e}")
            continue

    signals.sort(key=lambda s: s.final_confidence, reverse=True)
    logger.info(f"Generated {len(signals)} final signals")

    for verdict in ["STRONG_BUY", "BUY", "HOLD"]:
        matching = [s for s in signals if s.final_verdict == verdict]
        if matching:
            syms = ", ".join(s.symbol for s in matching)
            logger.info(f"  {verdict}: {syms}")

    return signals


def run_notifications(signals: list, dry_run: bool = False) -> None:
    """
    Send notifications for generated signals.
    
    Args:
        signals: List of FinalSignals
        dry_run: If True, don't actually send notifications
    """
    logger.info("=" * 50)
    logger.info("STEP 4: Sending notifications...")
    logger.info("=" * 50)
    
    if not signals:
        logger.info("No signals to notify.")
        return
    
    if dry_run:
        logger.info("DRY RUN: Skipping actual notifications")
        # Print what would be sent
        for signal in signals:
            logger.info(f"Would notify: {signal.symbol} - {signal.final_verdict}")
        return
    
    # Send daily summary
    try:
        if send_daily_summary(signals):
            logger.info("Daily summary sent to Telegram")
    except Exception as e:
        logger.error(f"Failed to send daily summary: {e}")
    
    # Send individual alerts for strong buys
    strong_buys = [s for s in signals if s.final_verdict == "STRONG_BUY"]
    
    for signal in strong_buys:
        try:
            if send_telegram_alert(signal):
                logger.info(f"Alert sent for {signal.symbol}")
        except Exception as e:
            logger.error(f"Failed to send alert for {signal.symbol}: {e}")


def run_full_pipeline(dry_run: bool = False) -> list:
    """
    Run the complete trading analysis pipeline.
    
    Args:
        dry_run: If True, don't send notifications
        
    Returns:
        List of FinalSignals
    """
    start_time = datetime.now()
    logger.info(f"🚀 Starting NEPSE AI Trading Bot at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize database
    init_db()
    
    # Step 1: Fetch data
    if not run_data_fetch():
        logger.warning("Continuing with existing data...")
    
    # Step 2: Run screener
    results = run_screener()
    
    if not results:
        logger.info("No signals today. Pipeline complete.")
        return []
    
    # Step 3: Run intelligence
    signals = run_intelligence(results[:10])  # Limit to top 10 for cost
    
    # Step 4: Send notifications
    run_notifications(signals, dry_run=dry_run)
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("=" * 50)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info(f"Signals generated: {len(signals)}")
    logger.info("=" * 50)
    
    return signals


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="NEPSE AI Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                  # Run full analysis
    python main.py --fetch-only     # Only fetch data
    python main.py --screen-only    # Only run screener (with existing data)
    python main.py --dry-run        # Run without sending notifications
    python main.py --schedule       # Run as scheduled daemon
    python main.py --backtest NICA  # Backtest a symbol
        """
    )
    
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only fetch market data, don't run analysis"
    )
    
    parser.add_argument(
        "--screen-only",
        action="store_true",
        help="Only run screener (uses existing data)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis but don't send notifications"
    )
    
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run as a scheduled daemon (pre/post market jobs)"
    )
    
    parser.add_argument(
        "--backtest",
        type=str,
        metavar="SYMBOL",
        help="Run backtest for a symbol (e.g., --backtest NICA)"
    )
    
    parser.add_argument(
        "--backtest-start",
        type=str,
        default="2024-01-01",
        help="Backtest start date (default: 2024-01-01)"
    )
    
    parser.add_argument(
        "--ipo-exit",
        type=str,
        metavar="SYMBOL",
        help="Analyze IPO exit signals for newly listed stock (e.g., --ipo-exit SOHL)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set up logging
    if args.verbose:
        import os
        os.environ["LOG_LEVEL"] = "DEBUG"
    
    setup_logging()
    
    try:
        if args.fetch_only:
            init_db()
            run_data_fetch()
        
        elif args.screen_only:
            init_db()
            results = run_screener()

            # Print formatted results using ScreenedStock fields
            if results:
                print("\n📊 NEPSE MASTER SCREENER RESULTS")
                print("=" * 50)
                for i, stock in enumerate(results, 1):
                    css_str = f" | CSS: {stock.css_score:.2f}" if hasattr(stock, "css_score") and stock.css_score else ""
                    print(f"\n{i}. {stock.symbol} — {stock.recommendation} ({stock.total_score:.1f}/100){css_str}")
                    print(f"   Entry: Rs.{stock.entry_price_with_slippage:.2f} | Target: Rs.{stock.target_price:.2f} | SL: Rs.{stock.stop_loss_with_slippage:.2f}")
                    print(f"   {stock.verdict_reason}")
            else:
                print("No stocks passed screening criteria today.")
        
        elif args.schedule:
            # Run as scheduled daemon
            from scheduler.jobs import run_scheduler
            run_scheduler()
        
        elif args.backtest:
            # Run backtest
            init_db()
            
            from backtesting.engine import quick_backtest
            
            logger.info(f"Running backtest for {args.backtest}...")
            result = quick_backtest(
                symbol=args.backtest,
                start_date=args.backtest_start,
            )
            print(result.summary())
        
        elif args.ipo_exit:
            # Run IPO exit analysis
            from intelligence.ipo_exit_analyzer import IPOExitAnalyzer
            
            print(f"\n📊 Analyzing IPO exit signals for {args.ipo_exit}...")
            analyzer = IPOExitAnalyzer()
            result = analyzer.analyze(args.ipo_exit)
            print(result.format_report())
        
        else:
            run_full_pipeline(dry_run=args.dry_run)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
        
    except NepseAIException as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
