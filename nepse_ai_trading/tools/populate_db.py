"""
NEPSE Historical Data Pipeline — Populate local DB for backtesting.
====================================================================
Fetches OHLCV price history from NepseAlpha (NepseUnofficialApi) and
stores it in the local SQLite database so the backtest engine can run.

WITHOUT this data, `backtesting/engine.py` returns empty results.
Run this ONCE to backfill 2 years, then daily to keep it current.

Usage:
  python tools/populate_db.py                    # All stocks, 2 years
  python tools/populate_db.py --symbols NABIL NICA SCB
  python tools/populate_db.py --days 365         # 1 year only
  python tools/populate_db.py --incremental      # Only fetch missing dates
  python tools/populate_db.py --dry-run          # Test without saving

Via alias:
  nepse populate                                  # All stocks, incremental

How long it takes:
  ~200 stocks × ~0.8s/stock ≈ 3–4 minutes (with rate limiting)
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import date, timedelta
from typing import List, Optional

# ── Path setup ────────────────────────────────────────────────────────
_TOOLS_DIR = Path(__file__).resolve().parent
_AI_ROOT = _TOOLS_DIR.parent
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_AI_ROOT / ".env", override=True)
except Exception:
    pass

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="WARNING")   # suppress verbose, show errors

from core.database import init_db, SessionLocal, Stock, DailyPrice
from data.fetcher import NepseFetcher, save_prices_to_db
import pandas as pd


# ─────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────

def _get_latest_date(symbol: str) -> Optional[date]:
    """Return the most recent DailyPrice.date for a symbol, or None."""
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
        if not stock:
            return None
        row = (
            db.query(DailyPrice.date)
            .filter(DailyPrice.stock_id == stock.id)
            .order_by(DailyPrice.date.desc())
            .first()
        )
        return row[0] if row else None
    finally:
        db.close()


def _count_rows(symbol: str = None) -> int:
    """Count DailyPrice rows, optionally filtered by symbol."""
    db = SessionLocal()
    try:
        q = db.query(DailyPrice)
        if symbol:
            stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
            if stock:
                q = q.filter(DailyPrice.stock_id == stock.id)
        return q.count()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# Core populate function
# ─────────────────────────────────────────────────────────────────────

def populate_symbol(
    fetcher: NepseFetcher,
    symbol: str,
    days: int = 730,
    incremental: bool = True,
    dry_run: bool = False,
) -> int:
    """
    Fetch and save OHLCV history for one symbol.

    Returns number of rows saved (0 on failure or dry-run).
    """
    symbol = symbol.upper().strip()

    # Incremental: only fetch from last saved date + 1
    fetch_days = days
    if incremental:
        latest = _get_latest_date(symbol)
        if latest:
            missing_days = (date.today() - latest).days
            if missing_days <= 1:
                return 0   # already up-to-date; skip silently
            fetch_days = min(missing_days + 5, days)   # +5 buffer for holidays

    try:
        df = fetcher.fetch_price_history(symbol, days=fetch_days)
    except Exception as e:
        print(f"  ⚠️  {symbol}: fetch failed — {e}")
        return 0

    if df.empty:
        return 0

    # Ensure 'symbol' column present for save_prices_to_db
    df["symbol"] = symbol

    if dry_run:
        print(f"  [DRY-RUN] {symbol}: would save {len(df)} rows "
              f"({df['date'].min()} → {df['date'].max()})")
        return len(df)

    try:
        saved = save_prices_to_db(df)
        return saved
    except Exception as e:
        print(f"  ⚠️  {symbol}: save failed — {e}")
        return 0


def populate_all(
    symbols: Optional[List[str]] = None,
    days: int = 730,
    incremental: bool = True,
    dry_run: bool = False,
    delay: float = 0.5,
) -> None:
    """
    Populate DB for a list of symbols (or all NEPSE stocks if None).
    """
    init_db()
    fetcher = NepseFetcher()

    # Resolve symbol list
    if not symbols:
        print("  ⏳ Fetching full NEPSE company list...")
        try:
            company_list = fetcher.fetch_company_list()
            symbols = [c.symbol for c in company_list if c.symbol]
        except Exception as e:
            print(f"  ❌ Cannot fetch company list: {e}")
            sys.exit(1)
        print(f"  ✅ Found {len(symbols)} listed stocks")

    total = len(symbols)
    rows_before = _count_rows()

    print(f"\n  📥 Populating DB: {total} stocks, {days} days, incremental={incremental}")
    print(f"  Current DB: {rows_before:,} price rows\n")

    total_saved = 0
    skipped = 0
    failed = 0

    for i, symbol in enumerate(symbols, 1):
        saved = populate_symbol(fetcher, symbol, days=days,
                                incremental=incremental, dry_run=dry_run)
        if saved > 0:
            total_saved += saved
            status = f"+{saved:>5} rows"
        elif saved == 0:
            skipped += 1
            status = "up-to-date" if incremental else "no data"
        else:
            failed += 1
            status = "FAILED"

        print(f"  [{i:>3}/{total}] {symbol:<12} {status}", end="")
        if i % 5 == 0 or i == total:
            print()  # newline every 5 stocks
        else:
            print("   ", end="", flush=True)

        # Rate limiting — be nice to the API
        if i < total:
            time.sleep(delay)

    rows_after = _count_rows()
    print(f"\n  ✅ Done!")
    print(f"  Stocks processed: {total}  |  Skipped (current): {skipped}  |  Failed: {failed}")
    print(f"  Rows saved: {total_saved:,}")
    print(f"  DB total: {rows_before:,} → {rows_after:,} price rows")

    if not dry_run:
        print(f"\n  💡 Now run: python main.py --backtest NABIL --backtest-start 2023-01-01")
        print(f"     Or:      python tools/expert_analysis.py NABIL")


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NEPSE Historical Data Pipeline — Populate local DB for backtesting.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/populate_db.py                         # All stocks, 2 years
  python tools/populate_db.py --symbols NABIL NICA    # Specific symbols only
  python tools/populate_db.py --days 365              # 1 year only
  python tools/populate_db.py --incremental           # Only missing dates (fast)
  python tools/populate_db.py --dry-run               # Preview without saving
  python tools/populate_db.py --status                # Show DB stats only

Via alias: nepse populate
        """,
    )
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Specific symbols to fetch (default: all NEPSE stocks)")
    parser.add_argument("--days", type=int, default=730,
                        help="Days of history to fetch (default: 730 = 2 years)")
    parser.add_argument("--incremental", action="store_true", default=True,
                        help="Only fetch dates missing from DB (default: True)")
    parser.add_argument("--full", action="store_true",
                        help="Full re-fetch (overrides --incremental)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be fetched without saving")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Seconds between API calls (default: 0.5)")
    parser.add_argument("--status", action="store_true",
                        help="Show current DB statistics and exit")
    args = parser.parse_args()

    if args.status:
        init_db()
        db = SessionLocal()
        try:
            stock_count = db.query(Stock).count()
            price_count = db.query(DailyPrice).count()
            oldest = db.query(DailyPrice.date).order_by(DailyPrice.date.asc()).first()
            newest = db.query(DailyPrice.date).order_by(DailyPrice.date.desc()).first()
            print(f"\n  📊 DATABASE STATUS")
            print(f"  {'─' * 40}")
            print(f"  Stocks:     {stock_count:,}")
            print(f"  Price rows: {price_count:,}")
            if oldest and newest:
                print(f"  Date range: {oldest[0]} → {newest[0]}")
            else:
                print(f"  Date range: EMPTY — run populate_db.py to fill")
            print()
        finally:
            db.close()
        return

    incremental = not args.full
    populate_all(
        symbols=args.symbols,
        days=args.days,
        incremental=incremental,
        dry_run=args.dry_run,
        delay=args.delay,
    )


if __name__ == "__main__":
    start = time.time()
    main()
    elapsed = time.time() - start
    print(f"  ⏱  Total time: {elapsed:.0f}s\n")
