"""
Paper Trader — Stealth Accumulation Radar + CSS-Gated Paper Trading

Two modes:
  1. stealth  — Detect stocks where smart money is quietly accumulating
                (broker score high, technical score low → early entry)
  2. scan     — Full 4-Pillar analysis with CSS overlay; print top picks

Usage:
    python paper_trader.py stealth              # stealth accumulation radar
    python paper_trader.py stealth --sector bank
    python paper_trader.py scan                # full master screener results
    python paper_trader.py scan --sector hydro --strategy momentum
    python paper_trader.py scan --min-score 65 --quick
"""

import argparse
import sys
from datetime import date
from loguru import logger

from core.config import settings
from core.database import init_db
from core.logging_config import setup_logging
from analysis.master_screener import MasterStockScreener, ScreenedStock


# ─────────────────────────────────────────────────────────────────────────────
# STEALTH FILTER THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
STEALTH_MIN_BROKER_SCORE = 18.0   # Out of 30 — at least 60 % of broker pillar
STEALTH_MAX_TECH_SCORE = 12.0     # Out of 30 — technical momentum still quiet
STEALTH_DIST_RISK_ALLOW = {"LOW", ""}  # Skip MEDIUM / HIGH distribution risk


def _format_stealth_stock(rank: int, stock: ScreenedStock) -> str:
    css_str = f" | CSS {stock.css_score:.2f} [{stock.css_signal}]" if stock.css_score else ""
    dist = stock.distribution_risk or "N/A"
    lines = [
        f"\n{rank}. {stock.symbol}  ({stock.sector}){css_str}",
        f"   LTP: Rs.{stock.ltp:.2f}  |  Broker Score: {stock.pillar1_broker:.1f}/30"
        f"  |  Tech Score: {stock.pillar4_technical:.1f}/30",
        f"   Distribution Risk: {dist}  |  Broker Avg Cost: Rs.{stock.broker_avg_cost:.2f}"
        + (f"  |  Profit%: {stock.broker_profit_pct:+.1f}%" if stock.broker_profit_pct else ""),
        f"   Accumulation Window: {stock.net_holdings_1m:+,d} shares (1M) "
        f"/ {stock.net_holdings_1w:+,d} shares (1W)",
        f"   Suggested Entry: Rs.{stock.entry_price_with_slippage:.2f}  |  "
        f"Target: Rs.{stock.target_price:.2f}  |  SL: Rs.{stock.stop_loss_with_slippage:.2f}",
    ]
    if stock.css_signal in ("STRONG_BUY", "BUY"):
        lines.append("   ✅ CSS CONFIRMS: Technical setup aligning with accumulation!")
    elif stock.css_signal in ("WEAK_BUY",):
        lines.append("   ⚠️  CSS: Weak technical momentum — early stage, watch closely.")
    return "\n".join(lines)


def _format_scan_stock(rank: int, stock: ScreenedStock) -> str:
    css_str = f" | CSS {stock.css_score:.2f} [{stock.css_signal}]" if stock.css_score else ""
    lines = [
        f"\n{rank}. {stock.symbol}  —  {stock.recommendation}  ({stock.total_score:.1f}/100){css_str}",
        f"   {stock.verdict_reason}",
        f"   Entry: Rs.{stock.entry_price_with_slippage:.2f}  Target: Rs.{stock.target_price:.2f}"
        f"  SL: Rs.{stock.stop_loss_with_slippage:.2f}  R:R {stock.risk_reward_ratio:.1f}x",
        f"   Hold: ~{stock.expected_holding_days}d (max {stock.max_holding_days}d)",
        f"   {stock.exit_strategy}",
    ]
    if stock.execution_warning and stock.execution_warning != "ℹ️ Standard T+2 settlement applies":
        lines.append(f"   {stock.execution_warning}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# MODE: STEALTH RADAR
# ─────────────────────────────────────────────────────────────────────────────

def run_stealth(args) -> None:
    """Detect smart money accumulation before technicals catch up."""
    logger.info("🕵️  STEALTH RADAR — Smart Money Accumulation Detector")
    logger.info("=" * 70)

    screener = MasterStockScreener(
        strategy="value",
        target_sector=args.sector or None,
    )

    all_stocks = screener.run_stealth_analysis(
        top_n=500,
        max_workers=getattr(args, "workers", 12),
    )

    # Apply stealth filter
    stealth_hits = []
    for s in all_stocks:
        broker_ok = s.pillar1_broker >= STEALTH_MIN_BROKER_SCORE
        tech_quiet = s.pillar4_technical <= STEALTH_MAX_TECH_SCORE
        dist_ok = s.distribution_risk in STEALTH_DIST_RISK_ALLOW

        # Additional: exclude stocks where broker profit already too high (>20 %)
        broker_not_overextended = s.broker_profit_pct <= 20
        # Exclude SELL / STRONG_SELL CSS signals
        css_not_bearish = s.css_signal not in ("SELL", "STRONG_SELL") if s.css_signal else True

        if broker_ok and tech_quiet and dist_ok and broker_not_overextended and css_not_bearish:
            stealth_hits.append(s)

    # Sort: primary=broker_score desc, secondary=css_score desc
    stealth_hits.sort(key=lambda x: (x.pillar1_broker, x.css_score), reverse=True)

    print("\n" + "=" * 70)
    print("🕵️  STEALTH ACCUMULATION RADAR  —  " + date.today().isoformat())
    print(f"   Filter: Broker≥{STEALTH_MIN_BROKER_SCORE} | Tech≤{STEALTH_MAX_TECH_SCORE} | Dist=LOW")
    print("=" * 70)

    if not stealth_hits:
        print("\n⚪ No stealth accumulation detected today.")
        print("   Smart money may not be active, or all candidates have HIGH distribution risk.")
        return

    for i, stock in enumerate(stealth_hits[:15], 1):
        print(_format_stealth_stock(i, stock))

    print("\n" + "=" * 70)
    print(f"Total stealth candidates: {len(stealth_hits)}")
    print("💡 Strategy: Enter when technicals start catching up (RSI crosses 50, EMA golden cross).")
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# MODE: FULL SCAN
# ─────────────────────────────────────────────────────────────────────────────

def run_scan(args) -> None:
    """Full 4-Pillar + CSS analysis — standard daily scan."""
    min_score = getattr(args, "min_score", 60)
    quick = getattr(args, "quick", False)
    strategy = getattr(args, "strategy", "value")
    sector = getattr(args, "sector", None)

    screener = MasterStockScreener(
        strategy=strategy,
        target_sector=sector or None,
    )

    results = screener.run_full_analysis(
        min_score=min_score,
        top_n=10,
        quick_mode=quick,
        max_workers=getattr(args, "workers", 12),
    )

    print("\n" + "=" * 70)
    print(f"📊 MASTER SCREENER RESULTS  —  {date.today().isoformat()}")
    print(f"   Strategy: {strategy.upper()}  |  Min Score: {min_score}")
    if sector:
        print(f"   Sector Filter: {sector}")
    print("=" * 70)

    if not results:
        print("\n⚪ No stocks passed the score threshold today.")
        regime = screener._market_regime
        if regime in ("PANIC", "BEAR"):
            print(f"   Market Regime: {regime} — fewer signals expected.")
        return

    for i, stock in enumerate(results, 1):
        print(_format_scan_stock(i, stock))

    # CSS summary
    css_confirmed = [s for s in results if s.css_signal in ("STRONG_BUY", "BUY")]
    if css_confirmed:
        syms = ", ".join(s.symbol for s in css_confirmed)
        print(f"\n✅ CSS-confirmed BUY signals: {syms}")

    print("\n" + "=" * 70)
    print(f"Total: {len(results)} stock(s) passed (score ≥ {min_score}/100)")
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="NEPSE Paper Trader — Stealth Radar & Master Scan",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python paper_trader.py stealth                        # detect smart money
  python paper_trader.py stealth --sector bank          # bank sector only
  python paper_trader.py scan                           # full daily scan
  python paper_trader.py scan --strategy momentum --sector hydro
  python paper_trader.py scan --min-score 65 --quick    # quick top-50 scan
        """,
    )

    subparsers = parser.add_subparsers(dest="mode", help="Operating mode")
    subparsers.required = True

    # ── stealth sub-command ──
    stealth_p = subparsers.add_parser("stealth", help="Stealth accumulation radar")
    stealth_p.add_argument("--sector", type=str, default=None, help="Target sector (e.g. bank, hydro)")
    stealth_p.add_argument("--workers", type=int, default=12, help="Parallel workers")

    # ── scan sub-command ──
    scan_p = subparsers.add_parser("scan", help="Full 4-Pillar + CSS scan")
    scan_p.add_argument("--sector", type=str, default=None, help="Target sector")
    scan_p.add_argument("--strategy", type=str, default="value", choices=["value", "momentum", "growth"],
                        help="Scoring strategy")
    scan_p.add_argument("--min-score", type=float, default=60, dest="min_score",
                        help="Minimum total score threshold (default 60)")
    scan_p.add_argument("--quick", action="store_true", help="Quick mode — top 50 stocks by volume only")
    scan_p.add_argument("--workers", type=int, default=12, help="Parallel workers")

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    return parser.parse_args()


def main():
    args = parse_args()

    import os
    if getattr(args, "verbose", False):
        os.environ["LOG_LEVEL"] = "DEBUG"

    setup_logging()
    init_db()

    if args.mode == "stealth":
        run_stealth(args)
    elif args.mode == "scan":
        run_scan(args)
    else:
        logger.error(f"Unknown mode: {args.mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
