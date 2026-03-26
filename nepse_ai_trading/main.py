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
        df = fetcher.fetch_today_prices()
        
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


def run_screener() -> list:
    """
    Run the multi-strategy screener.
    
    Returns:
        List of ScreenerResults
    """
    logger.info("=" * 50)
    logger.info("STEP 2: Running technical analysis screener...")
    logger.info("=" * 50)
    
    try:
        screener = StockScreener()
        results = screener.screen_all(min_confidence=5.5)
        
        if not results:
            logger.info("No stocks passed screening criteria today.")
            return []
        
        logger.info(f"Found {len(results)} potential signals")
        
        # Log top signals
        for i, result in enumerate(results[:5], 1):
            signal = result.primary_signal
            logger.info(
                f"  {i}. {result.symbol}: {signal.strategy_name} "
                f"(confidence: {signal.confidence:.1f}/10)"
            )
        
        return results
        
    except Exception as e:
        logger.error(f"Screener failed: {e}")
        return []


def run_intelligence(results: list) -> list:
    """
    Run news scraping and AI analysis.
    
    Args:
        results: ScreenerResults from screener
        
    Returns:
        List of FinalSignals
    """
    logger.info("=" * 50)
    logger.info("STEP 3: Running intelligence analysis...")
    logger.info("=" * 50)
    
    try:
        aggregator = SignalAggregator(
            use_ai=bool(settings.openai_api_key),
            scrape_news=True,
        )
        
        signals = aggregator.aggregate_all(results)
        
        if not signals:
            logger.info("No final signals generated.")
            return []
        
        logger.info(f"Generated {len(signals)} final signals")
        
        # Log signals by verdict
        for verdict in ["STRONG_BUY", "BUY", "RISKY"]:
            matching = [s for s in signals if s.final_verdict == verdict]
            if matching:
                symbols = ", ".join(s.symbol for s in matching)
                logger.info(f"  {verdict}: {symbols}")
        
        return signals
        
    except Exception as e:
        logger.error(f"Intelligence analysis failed: {e}")
        return []


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
            
            # Print formatted results
            screener = StockScreener()
            print(screener.format_results(results))
        
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
