"""
NEPSE Expert Analysis — 6-Gate Buy Verification Engine
======================================================
Combines 3-Timeframe Technical Analysis (NepseAlpha chart data)
with 4-Pillar Fundamental Scoring (ShareHub broker/fundamental/unlock)
to produce a single definitive BUY/AVOID verdict.

Gates:
  1. Technical Foundation   (25 pts)  — 13-Point WIDGET_GUIDE Checklist
  2. Multi-TF Confluence    (15 pts)  — 7-Timeframe Alignment
  3. 4-Pillar Fundamentals  (25 pts)  — Broker + Unlock + PE/ROE + Technicals
  4. CSS Confirmation       (15 pts)  — Composite Signal Score (trend+momentum+volume+operator)
  5. Risk Clearance         (10 pts)  — Manipulation + Distribution + Dump Detection
  6. Market Regime          (10 pts)  — BULL / BEAR / PANIC Kill Switch

Verdicts:
  BLIND BUY  — All 6 gates clear, score ≥ 85, bull market. Execute immediately.
  STRONG BUY — 5+ gates clear, score ≥ 70. One minor flag — acceptable risk.
  BUY        — 4+ gates clear, score ≥ 55. Manual review recommended.
  RISKY      — 2-3 gates, score ≥ 40. Too many red flags.
  AVOID      — <40, PANIC mode, or CRITICAL manipulation/distribution.

Usage:
  python expert_analysis.py NABIL                       # Single stock deep analysis
  python expert_analysis.py --scan                      # Full market scan
  python expert_analysis.py --scan --sector "Commercial Banks"
  python expert_analysis.py --scan --top 10             # More per sector

  nepse expert NABIL                                    # Via alias
  nepse expert --scan                                   # Via alias
"""

import sys
import asyncio
import argparse
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime, timezone

# ── Path Setup ───────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent          # tools/
_AI_ROOT = _THIS_DIR.parent                          # nepse_ai_trading/
_CHART_BACKEND = _AI_ROOT.parent / "nepse-chart-extension" / "backend"

# Chart backend MUST be inserted AFTER AI root so screener.py's
# `sys.path.insert(0, ...)` at import time places it first — ensuring
# `from main import ...` resolves to the chart extension's main.py.
for _p in [str(_AI_ROOT), str(_CHART_BACKEND)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load .env for ShareHub / OpenAI credentials
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_AI_ROOT / ".env", override=True)
except Exception:
    pass

# ── Technical Analysis (chart extension's screener.py) ───────────────
import aiohttp
from screener import (
    fetch_ohlcv,
    run_analysis,
    compute_checklist_score,
    compute_composite_score,
    fetch_intraday_ohlcv,
    analyze_intraday,
    compute_intraday_checks,
    scan_all_stocks,
    save_watchlist,
    _fsk,
)

# ── Fundamental Analysis (nepse_ai_trading) ──────────────────────────
from analysis.master_screener import MasterStockScreener, ScreenedStock
from core.database import init_db

# Suppress noisy logs — expert tool has its own progress output
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="ERROR")


# ═════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═════════════════════════════════════════════════════════════════════

@dataclass
class GateResult:
    """Result of a single gate evaluation."""
    name: str
    score: float
    max_score: float
    status: str  # PASS, PARTIAL, FAIL
    details: List[str] = field(default_factory=list)


@dataclass
class ExpertVerdict:
    """Combined verdict from all 6 gates."""
    symbol: str
    sector: str = ""
    company_name: str = ""
    ltp: float = 0.0

    final_score: float = 0.0
    verdict: str = ""  # BLIND BUY, STRONG BUY, BUY, RISKY, AVOID

    gates: List[GateResult] = field(default_factory=list)
    gates_passed: int = 0
    gates_partial: int = 0
    gates_failed: int = 0

    # Trade plan
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    risk_reward: float = 0.0
    entry_status: str = "DAILY ONLY"
    holding_days: int = 7

    # Summary fields for scan display
    checklist_score: int = 0
    composite_score: float = 0.0
    p1_broker: float = 0.0
    p2_unlock: float = 0.0
    p3_fundamental: float = 0.0
    p4_technical: float = 0.0
    master_score: float = 0.0
    css_score: float = 0.0
    css_signal: str = ""


# ═════════════════════════════════════════════════════════════════════
# 6-GATE FUNCTIONS
# ═════════════════════════════════════════════════════════════════════

def _gate1_technical(chk: dict) -> GateResult:
    """Gate 1: Technical Foundation — 13-Point WIDGET_GUIDE Checklist (max 25)."""
    score_13 = chk.get("total_score", 0)
    keys = [
        ("verdict_buy", "Verdict BUY"),
        ("trend_confirmed", "Trend + ADX>20 + EMA10>EMA30"),
        ("rsi_safe", "RSI 40-70"),
        ("price_above_sma50", "Price > SMA50"),
        ("macd_bullish", "MACD Bullish"),
        ("multi_tf_aligned", "Multi-TF ≥50% BUY"),
        ("no_red_flags", "No Death Cross / RSI 80+ / Bear Div"),
        ("volume_confirmed", "Volume ratio ≥ 1.2"),
        ("entry_timing", "Near support ≤8% or breakout"),
        ("wyckoff_favorable", "Accumulation / Markup phase"),
        ("no_operator_distribution", "No operator distribution"),
        ("not_chasing_52w_top", "Not chasing 52w high"),
        ("rr_ratio_ok", "R:R ≥ 1.5"),
    ]
    details = [f"Checklist: {score_13}/13"]
    for k, label in keys:
        icon = "✅" if chk.get(k, False) else "❌"
        details.append(f"{icon} {label}")

    if score_13 >= 10:
        return GateResult("Technical Foundation", 25, 25, "PASS", details)
    if score_13 >= 8:
        return GateResult("Technical Foundation", 15, 25, "PARTIAL", details)
    return GateResult("Technical Foundation", 0, 25, "FAIL", details)


def _gate2_multi_tf(ta: dict) -> GateResult:
    """Gate 2: Multi-Timeframe Confluence — 7 TF alignment (max 15)."""
    tfs = [
        ("Daily", ta.get("verdict")),
        ("Bi-Weekly", ta.get("biweekly_verdict")),
        ("Weekly", ta.get("weekly_verdict")),
        ("Monthly", ta.get("monthly_verdict")),
        ("Quarterly", ta.get("quarterly_verdict")),
        ("Semi-Yr", ta.get("semi_yearly_verdict")),
        ("Yearly", ta.get("yearly_verdict")),
    ]
    buy = sum(1 for _, v in tfs if v in ("BUY", "STRONG BUY"))
    total = sum(1 for _, v in tfs if v)
    details = []
    for name, v in tfs:
        icon = "✅" if v in ("BUY", "STRONG BUY") else ("❌" if v else "⚪")
        details.append(f"{icon} {name}={v or '—'}")
    details.append(f"Aligned: {buy}/{total}")

    ratio = buy / total if total else 0
    if ratio >= 0.7:
        return GateResult("Multi-TF Confluence", 15, 15, "PASS", details)
    if ratio >= 0.5:
        return GateResult("Multi-TF Confluence", 10, 15, "PARTIAL", details)
    return GateResult("Multi-TF Confluence", 0, 15, "FAIL", details)


def _gate3_four_pillar(s: Optional[ScreenedStock]) -> GateResult:
    """Gate 3: 4-Pillar Fundamentals — Broker+Unlock+Fundamental+Technical (max 25)."""
    if not s:
        return GateResult("4-Pillar Fundamentals", 0, 25, "FAIL", ["❌ 4-Pillar scoring unavailable"])

    ms = s.total_score
    details = [
        f"Master Score: {ms:.1f}/100",
        f"  Broker      {_bar(s.pillar1_broker, 30, 10)}  {s.pillar1_broker:.1f}/30",
        f"  Unlock      {_bar(s.pillar2_unlock, 20, 10)}  {s.pillar2_unlock:.1f}/20",
        f"  Fundamental {_bar(s.pillar3_fundamental, 20, 10)}  {s.pillar3_fundamental:.1f}/20",
        f"  Technical   {_bar(s.pillar4_technical, 30, 10)}  {s.pillar4_technical:.1f}/30",
    ]
    if s.pe_ratio > 0:
        details.append(f"  PE {s.pe_ratio:.1f}x | EPS Rs.{s.eps:.2f} | ROE {s.roe:.1f}% | PBV {s.pbv:.2f}x")
    winner = getattr(s, "winner", "")
    buyer_dom = getattr(s, "buyer_dominance_pct", 0)
    if winner:
        details.append(f"  Broker Dominance: {winner} ({buyer_dom:.0f}%)")

    if ms >= 70:
        return GateResult("4-Pillar Fundamentals", 25, 25, "PASS", details)
    if ms >= 55:
        return GateResult("4-Pillar Fundamentals", 15, 25, "PARTIAL", details)
    return GateResult("4-Pillar Fundamentals", 0, 25, "FAIL", details)


def _gate4_css(s: Optional[ScreenedStock]) -> GateResult:
    """Gate 4: CSS Confirmation — Composite Signal Score (max 15)."""
    if not s or not s.css_score:
        return GateResult("CSS Confirmation", 0, 15, "FAIL", ["❌ CSS engine unavailable or no data"])

    css = s.css_score
    sig = s.css_signal
    conf = s.css_confidence
    details = [f"CSS: {css:.3f} [{sig}] confidence {conf:.0f}%"]

    if css >= 0.60 and sig in ("STRONG_BUY", "BUY"):
        return GateResult("CSS Confirmation", 15, 15, "PASS", details)
    if css >= 0.45 and sig not in ("SELL", "STRONG_SELL"):
        return GateResult("CSS Confirmation", 8, 15, "PARTIAL", details)
    return GateResult("CSS Confirmation", 0, 15, "FAIL", details)


def _gate5_risk(s: Optional[ScreenedStock]) -> GateResult:
    """Gate 5: Risk Clearance — Manipulation + Distribution + Dump (max 10)."""
    if not s:
        return GateResult("Risk Clearance", 5, 10, "PARTIAL", ["⚪ Risk data unavailable — TA only"])

    pts = 0.0
    details = []

    # Manipulation (5 pts)
    manip = str(getattr(s, "manipulation_severity", "NONE") or "NONE")
    if manip in ("NONE", "LOW"):
        pts += 5
        details.append(f"✅ Manipulation: {manip}")
    elif manip == "MEDIUM":
        pts += 2
        details.append("🟡 Manipulation: MEDIUM")
    else:
        details.append(f"🚨 Manipulation: {manip}")
        return GateResult("Risk Clearance", 0, 10, "FAIL", details)

    # Distribution risk (3 pts)
    dist = str(getattr(s, "distribution_risk", "") or "")
    bpp = getattr(s, "broker_profit_pct", 0) or 0
    if dist in ("LOW", "N/A", ""):
        pts += 3
        details.append(f"✅ Distribution: {dist or 'N/A'}" + (f" (brokers {bpp:+.1f}%)" if bpp else ""))
    elif dist == "MEDIUM":
        pts += 1
        details.append(f"🟡 Distribution: MEDIUM (brokers {bpp:+.1f}%)")
    elif dist == "CRITICAL":
        details.append(f"🚨 Distribution: CRITICAL (brokers {bpp:+.1f}%)")
        return GateResult("Risk Clearance", 0, 10, "FAIL", details)
    else:
        details.append(f"🔴 Distribution: {dist} (brokers {bpp:+.1f}%)")

    # Intraday dump (2 pts)
    if not getattr(s, "intraday_dump_detected", False):
        pts += 2
        details.append("✅ No intraday dump pattern")
    else:
        details.append("🔴 Intraday pump-and-dump detected!")

    status = "PASS" if pts >= 8 else ("PARTIAL" if pts >= 4 else "FAIL")
    return GateResult("Risk Clearance", pts, 10, status, details)


def _gate6_regime(regime: str, reason: str = "") -> GateResult:
    """Gate 6: Market Regime — BULL/BEAR/PANIC kill switch (max 10)."""
    details = [f"Regime: {regime}"]
    if reason:
        details.append(reason)

    if regime == "PANIC":
        details.append("🚨 KILL SWITCH — No buying allowed")
        return GateResult("Market Regime", 0, 10, "FAIL", details)
    if regime == "BEAR":
        details.append("🐻 Bear market — tight stops, reduce size 50%")
        return GateResult("Market Regime", 3, 10, "PARTIAL", details)
    details.append("🐂 Favorable environment")
    return GateResult("Market Regime", 10 if regime == "BULL" else 7, 10, "PASS", details)


# ═════════════════════════════════════════════════════════════════════
# VERDICT ENGINE
# ═════════════════════════════════════════════════════════════════════

def _compute_verdict(
    symbol: str,
    ta: dict,
    chk: dict,
    screened: Optional[ScreenedStock],
    regime: str,
    regime_reason: str,
    entry_status: str = "DAILY ONLY",
) -> ExpertVerdict:
    """Compute the 6-Gate Expert Verdict for one stock."""

    gates = [
        _gate1_technical(chk),
        _gate2_multi_tf(ta),
        _gate3_four_pillar(screened),
        _gate4_css(screened),
        _gate5_risk(screened),
        _gate6_regime(regime, regime_reason),
    ]

    total = sum(g.score for g in gates)
    passed = sum(1 for g in gates if g.status == "PASS")
    partial = sum(1 for g in gates if g.status == "PARTIAL")
    failed = sum(1 for g in gates if g.status == "FAIL")

    risk_fail = any(g.name == "Risk Clearance" and g.status == "FAIL" for g in gates)

    # Verdict determination — strict gated logic
    if regime == "PANIC" or risk_fail:
        verdict = "AVOID"
    elif total >= 85 and failed == 0 and regime not in ("BEAR",):
        verdict = "BLIND BUY"
    elif total >= 70 and failed <= 1:
        verdict = "STRONG BUY"
    elif total >= 55 and failed <= 2:
        verdict = "BUY"
    elif total >= 40:
        verdict = "RISKY"
    else:
        verdict = "AVOID"

    # Trade plan — prefer 4-Pillar (realistic slippage-adjusted)
    ltp = ta.get("current_price", 0)
    if screened and screened.entry_price_with_slippage > 0:
        entry = screened.entry_price_with_slippage
        target = screened.target_price
        sl = screened.stop_loss_with_slippage
        rr = screened.risk_reward_ratio
        hold = screened.expected_holding_days
    else:
        entry = ltp
        target = ta.get("suggested_target", ltp * 1.10)
        sl = ta.get("suggested_sl", ltp * 0.95)
        risk_ = abs(ltp - sl) if sl else 1
        rr = round(abs(target - ltp) / risk_, 2) if risk_ > 0 else 0
        hold = 7

    return ExpertVerdict(
        symbol=symbol,
        sector=ta.get("sector", ""),
        company_name=ta.get("company_name", symbol),
        ltp=ltp,
        final_score=round(total, 1),
        verdict=verdict,
        gates=gates,
        gates_passed=passed,
        gates_partial=partial,
        gates_failed=failed,
        entry_price=round(entry, 2),
        target_price=round(target, 2),
        stop_loss=round(sl, 2),
        risk_reward=rr,
        entry_status=entry_status,
        holding_days=hold,
        checklist_score=chk.get("total_score", 0),
        composite_score=ta.get("composite_score", 0),
        p1_broker=screened.pillar1_broker if screened else 0,
        p2_unlock=screened.pillar2_unlock if screened else 0,
        p3_fundamental=screened.pillar3_fundamental if screened else 0,
        p4_technical=screened.pillar4_technical if screened else 0,
        master_score=screened.total_score if screened else 0,
        css_score=screened.css_score if screened else 0,
        css_signal=screened.css_signal if screened else "",
    )


# ═════════════════════════════════════════════════════════════════════
# SCREENER HELPERS
# ═════════════════════════════════════════════════════════════════════

def _init_screener():
    """Init MasterStockScreener, return (screener, regime, regime_reason)."""
    init_db()
    ms = MasterStockScreener(strategy="value")
    regime, reason = ms.check_market_regime()
    if regime != "PANIC":
        ms._preload_market_data()
        if ms.sharehub and hasattr(ms.sharehub, "auth_token") and ms.sharehub.auth_token:
            ms.sharehub_token = ms.sharehub.auth_token
    return ms, regime, reason


def _score_with_screener(
    ms: MasterStockScreener, symbol: str, ltp: float, sector: str = ""
) -> Optional[ScreenedStock]:
    """Score one stock through MasterStockScreener's 4-Pillar + CSS engine."""
    try:
        holdings = ms._broker_accumulation.get(symbol, {})
        ms._calculate_distribution_risk(symbol, ltp, holdings, {})
    except Exception:
        pass
    row = {
        "symbol": symbol,
        "securityName": symbol,
        "sectorName": sector,
        "lastTradedPrice": ltp,
        "totalTradeQuantity": 0,
    }
    try:
        return ms._score_stock(row)
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════
# SINGLE STOCK ANALYSIS
# ═════════════════════════════════════════════════════════════════════

async def analyze_single(symbol: str) -> Optional[ExpertVerdict]:
    """Full 6-Gate analysis for one stock."""
    symbol = symbol.upper().strip()

    print(f"\n{'═' * 70}")
    print(f"  🎯 NEPSE EXPERT ANALYSIS — {symbol}")
    print(f"     6-Gate Buy Verification Engine")
    print(f"     {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═' * 70}")

    # ── Phase 1: Technical Analysis (NepseAlpha) ─────────────────────
    print(f"\n  ⏳ Phase 1: Chart data + 13-Point Checklist + Multi-TF...")
    entry_status = "DAILY ONLY"

    async with aiohttp.ClientSession() as session:
        bars = await fetch_ohlcv(session, symbol)
        if not bars:
            print(f"  ❌ Could not fetch chart data for {symbol}. Check the symbol.")
            return None

        ta = run_analysis(symbol, bars)
        if not ta:
            print(f"  ❌ Technical analysis failed for {symbol}.")
            return None

        chk = compute_checklist_score(ta)
        ta["checklist"] = chk
        ta["checklist_score"] = chk["total_score"]
        ta["composite_score"] = compute_composite_score(ta, chk)

        # Intraday (1H + 15m)
        try:
            intra_bars = await fetch_intraday_ohlcv(session, symbol)
            if intra_bars:
                intra = analyze_intraday(intra_bars)
                ic = compute_intraday_checks(intra)
                if ic.get("hourly_zone_ok") and ic.get("intraday_trigger_ok"):
                    entry_status = "ENTRY READY"
                elif ic.get("hourly_zone_ok"):
                    entry_status = "ENTRY ZONE"
                else:
                    entry_status = "WAIT"
        except Exception:
            pass

    print(f"  ✅ Phase 1 complete:")
    print(f"     Checklist {chk['total_score']}/13 | Composite {ta['composite_score']:.1f}")
    print(f"     Verdict: {ta['verdict']} | Trend: {ta['trend']} | RSI: {ta.get('rsi_14', 0):.1f}")
    print(f"     Multi-TF: Daily={ta['verdict']} Wk={ta.get('weekly_verdict', '—')}"
          f" Mon={ta.get('monthly_verdict', '—')} Yr={ta.get('yearly_verdict', '—')}")

    # ── Phase 2: 4-Pillar + CSS (ShareHub) ───────────────────────────
    print(f"\n  ⏳ Phase 2: 4-Pillar Fundamental + CSS scoring...")
    screened = None
    regime, regime_reason = "UNKNOWN", ""

    try:
        ms, regime, regime_reason = _init_screener()
        regime_icon = {"PANIC": "🚨", "BEAR": "🐻", "BULL": "🐂"}.get(regime, "📊")
        print(f"     {regime_icon} Market Regime: {regime} — {regime_reason}")

        if regime == "PANIC":
            print(f"  🚨 PANIC MODE — All verdicts forced to AVOID.")
        else:
            screened = _score_with_screener(ms, symbol, ta["current_price"], ta.get("sector", ""))
            if screened:
                print(f"  ✅ Phase 2 complete:")
                print(f"     Master Score: {screened.total_score:.1f}/100")
                print(f"     Broker {screened.pillar1_broker:.1f}/30 | Unlock {screened.pillar2_unlock:.1f}/20"
                      f" | Fund {screened.pillar3_fundamental:.1f}/20 | Tech {screened.pillar4_technical:.1f}/30")
                if screened.css_score:
                    print(f"     CSS: {screened.css_score:.3f} [{screened.css_signal}]")
                dist = getattr(screened, "distribution_risk", "N/A") or "N/A"
                print(f"     Distribution: {dist} | Manipulation: "
                      f"{getattr(screened, 'manipulation_severity', 'N/A') or 'N/A'}")
            else:
                print(f"  ⚠️  4-Pillar scoring failed — using TA-only verdict.")
    except Exception as e:
        print(f"  ⚠️  4-Pillar unavailable ({e}) — TA-only verdict.")

    # ── Phase 3: 6-Gate Verdict ──────────────────────────────────────
    return _compute_verdict(symbol, ta, chk, screened, regime, regime_reason, entry_status)


# ═════════════════════════════════════════════════════════════════════
# SCAN MODE
# ═════════════════════════════════════════════════════════════════════

async def scan_expert(sector: str = None, top_n: int = 5) -> List[ExpertVerdict]:
    """Full market scan with 6-Gate verification on all candidates."""

    print(f"\n{'═' * 70}")
    print(f"  🎯 NEPSE EXPERT SCAN — 6-Gate Buy Verification")
    print(f"     {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═' * 70}")

    # ── Phase 1: Technical Analysis scan ─────────────────────────────
    print(f"\n  Phase 1: Full market TA scan (NepseAlpha)...")
    scan_top = max(top_n, 10)  # Get at least 10 per sector for better candidate pool
    result = await scan_all_stocks(sector_filter=sector, top_n=scan_top)
    save_watchlist(result)

    # Collect all stocks with checklist ≥ 5
    candidates = []
    for sec_stocks in result.get("sectors", {}).values():
        for s in sec_stocks:
            if s.get("checklist_score", 0) >= 5:
                candidates.append(s)
    candidates.sort(key=lambda x: x.get("composite_score", 0), reverse=True)

    if not candidates:
        print(f"  ⚪ No candidates with checklist ≥ 5/13. Market conditions very weak.")
        return []

    print(f"  ✅ Phase 1 complete: {len(candidates)} candidates (checklist ≥ 5/13)")

    # ── Phase 2: 4-Pillar + CSS scoring ──────────────────────────────
    print(f"\n  Phase 2: 4-Pillar + CSS scoring for {len(candidates)} candidates...")
    regime, regime_reason = "UNKNOWN", ""
    ms = None

    try:
        ms, regime, regime_reason = _init_screener()
        regime_icon = {"PANIC": "🚨", "BEAR": "🐻", "BULL": "🐂"}.get(regime, "📊")
        print(f"  {regime_icon}  Market Regime: {regime} — {regime_reason}")
    except Exception as e:
        print(f"  ⚠️  4-Pillar init failed: {e}. Using TA-only verdicts.")

    if regime == "PANIC":
        print(f"  🚨 PANIC MODE ACTIVE — All verdicts = AVOID\n")
        return [
            _compute_verdict(
                s["symbol"], s, s.get("checklist", {}), None,
                "PANIC", regime_reason, s.get("entry_status", "")
            )
            for s in candidates
        ]

    verdicts = []
    for i, s in enumerate(candidates, 1):
        sym = s["symbol"]
        ltp = float(s["current_price"])
        print(f"\r  [{i:3d}/{len(candidates)}] Scoring {sym:<12}", end="", flush=True)

        screened = _score_with_screener(ms, sym, ltp, s.get("sector", "")) if ms else None
        v = _compute_verdict(
            sym, s, s.get("checklist", {}), screened,
            regime, regime_reason, s.get("entry_status", "DAILY ONLY"),
        )
        v.company_name = s.get("company_name", sym)
        verdicts.append(v)

    print(f"\n  ✅ Phase 2 complete: {len(verdicts)} stocks scored.\n")

    verdicts.sort(key=lambda x: x.final_score, reverse=True)
    return verdicts


# ═════════════════════════════════════════════════════════════════════
# DISPLAY
# ═════════════════════════════════════════════════════════════════════

def _bar(val: float, mx: float, w: int = 10) -> str:
    """Unicode bar chart: ███░░░."""
    n = int((val / mx) * w) if mx > 0 else 0
    return "█" * min(n, w) + "░" * max(0, w - n)


_VERDICT_ICONS = {
    "BLIND BUY": "🟢", "STRONG BUY": "🔵", "BUY": "🟡",
    "RISKY": "🟠", "AVOID": "🔴",
}
_STATUS_ICONS = {"PASS": "✅", "PARTIAL": "🟡", "FAIL": "❌"}


def print_verdict(v: ExpertVerdict):
    """Print beautiful single-stock 6-Gate verdict."""
    icon = _VERDICT_ICONS.get(v.verdict, "⚪")
    bar = _bar(v.final_score, 100, 40)

    print(f"\n{'═' * 70}")
    print(f"  {icon}  {v.verdict}  —  {v.symbol}  ({v.company_name})")
    print(f"  Rs. {v.ltp:,.2f}  |  {v.sector}")
    print(f"  [{bar}]  {v.final_score}/100")
    print(f"  Gates: {v.gates_passed} PASS  {v.gates_partial} PARTIAL  {v.gates_failed} FAIL")
    print(f"{'═' * 70}")

    for g in v.gates:
        si = _STATUS_ICONS.get(g.status, "⚪")
        print(f"\n  ─── {g.name:<28} {si} {g.status:<8} {g.score:.0f}/{g.max_score:.0f}")
        for d in g.details:
            print(f"       {d}")

    # Trade plan
    if v.verdict not in ("AVOID",):
        gain_pct = ((v.target_price - v.entry_price) / v.entry_price * 100) if v.entry_price > 0 else 0
        loss_pct = ((v.stop_loss - v.entry_price) / v.entry_price * 100) if v.entry_price > 0 else 0
        entry_icons = {"ENTRY READY": "🟢", "ENTRY ZONE": "🟡", "WAIT": "🔴"}
        ei = entry_icons.get(v.entry_status, "⚪")

        print(f"\n{'═' * 70}")
        print(f"  📋 TRADE PLAN")
        print(f"{'─' * 70}")
        print(f"  LTP:        Rs. {v.ltp:>10,.2f}")
        print(f"  Entry:      Rs. {v.entry_price:>10,.2f}  (with slippage)")
        print(f"  Target:     Rs. {v.target_price:>10,.2f}  ({gain_pct:>+.1f}%)")
        print(f"  Stop Loss:  Rs. {v.stop_loss:>10,.2f}  ({loss_pct:>+.1f}%)")
        print(f"  R:R:        {v.risk_reward:.1f}x")
        print(f"  Hold:       ~{v.holding_days} trading days (max 15d)")
        print(f"  Entry:      {ei} {v.entry_status}")

        if v.verdict == "BLIND BUY":
            print(f"\n  ✅ ALL 6 GATES PASSED — This is as good as it gets.")
            print(f"  ✅ Execute at next market open. Set stop-loss immediately after fill.")
        elif v.verdict == "STRONG BUY":
            print(f"\n  🔵 5+ gates passed — Strong setup with one minor caveat.")
            print(f"  🔵 Check the 🟡 PARTIAL gate above, then decide.")
        elif v.verdict == "BUY":
            print(f"\n  🟡 4+ gates passed — Good setup. Review FAIL gates before executing.")
        elif v.verdict == "RISKY":
            print(f"\n  🟠 Multiple gates failed — High risk. Consider waiting for better setup.")

        print(f"{'═' * 70}")
    else:
        print(f"\n{'═' * 70}")
        print(f"  ⛔ DO NOT TRADE — Too many risk flags or PANIC market.")
        print(f"  ⛔ Wait for conditions to improve. Cash is a position.")
        print(f"{'═' * 70}")

    print()


def print_scan(verdicts: List[ExpertVerdict]):
    """Print scan results grouped by verdict tier."""
    tiers = ["BLIND BUY", "STRONG BUY", "BUY", "RISKY", "AVOID"]
    counts = {t: sum(1 for v in verdicts if v.verdict == t) for t in tiers}

    print(f"\n{'═' * 90}")
    print(f"  🎯 EXPERT SCAN RESULTS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Analyzed: {len(verdicts)} candidates through 6-Gate verification")
    print(f"{'─' * 90}")
    print(f"  🟢 BLIND BUY: {counts['BLIND BUY']:>3}   🔵 STRONG BUY: {counts['STRONG BUY']:>3}   "
          f"🟡 BUY: {counts['BUY']:>3}   🟠 RISKY: {counts['RISKY']:>3}   🔴 AVOID: {counts['AVOID']:>3}")
    print(f"{'═' * 90}")

    # Actionable tiers with details
    for tier in ["BLIND BUY", "STRONG BUY", "BUY"]:
        stocks = [v for v in verdicts if v.verdict == tier]
        if not stocks:
            continue

        icon = _VERDICT_ICONS[tier]
        print(f"\n  {icon}  {tier}  ({len(stocks)} stocks)")
        print(f"  {'─' * 86}")
        print(f"  {'#':<4} {'Symbol':<10} {'Score':>6} {'Gates':>7} {'Chk':>5} {'4-Pillar':>8} "
              f"{'CSS':>6} {'R:R':>5} {'Entry':<12} {'Sector'}")
        print(f"  {'─' * 4} {'─' * 10} {'─' * 6} {'─' * 7} {'─' * 5} {'─' * 8} "
              f"{'─' * 6} {'─' * 5} {'─' * 12} {'─' * 18}")

        for i, v in enumerate(stocks, 1):
            gates_str = f"{v.gates_passed}/{v.gates_passed + v.gates_partial + v.gates_failed}"
            css_str = f"{v.css_score:.2f}" if v.css_score else "  —"
            ms_str = f"{v.master_score:.0f}" if v.master_score else " —"
            sec = (v.sector or "—")[:18]
            ei = {"ENTRY READY": "🟢", "ENTRY ZONE": "🟡", "WAIT": "🔴"}.get(v.entry_status, "⚪")

            print(f"  {i:<4} {v.symbol:<10} {v.final_score:>5.1f} {gates_str:>7} "
                  f"{v.checklist_score:>3}/13 {ms_str:>6}/100 {css_str:>6} "
                  f"{v.risk_reward:>5.1f} {ei}{v.entry_status:<11} {sec}")

        # Detailed view for top 3 in each tier
        for v in stocks[:3]:
            gain_pct = ((v.target_price - v.entry_price) / v.entry_price * 100) if v.entry_price > 0 else 0
            print(f"\n     📌 {v.symbol} — Rs. {v.ltp:,.2f} → "
                  f"Target Rs. {v.target_price:,.2f} ({gain_pct:+.1f}%) "
                  f"SL Rs. {v.stop_loss:,.2f} | R:R {v.risk_reward:.1f}x | ~{v.holding_days}d")
            for g in v.gates:
                si = _STATUS_ICONS.get(g.status, "⚪")
                print(f"        {si} {g.name}: {g.score:.0f}/{g.max_score:.0f}")

    # Quick list of risky/avoid
    risky = [v for v in verdicts if v.verdict == "RISKY"]
    avoid = [v for v in verdicts if v.verdict == "AVOID"]
    if risky:
        print(f"\n  🟠 RISKY ({len(risky)}): {', '.join(v.symbol for v in risky[:15])}")
    if avoid:
        print(f"  🔴 AVOID ({len(avoid)}): {', '.join(v.symbol for v in avoid[:15])}")

    actionable = counts["BLIND BUY"] + counts["STRONG BUY"] + counts["BUY"]
    if not actionable:
        print(f"\n  ⚪ No actionable signals today. Cash is a position — wait for better setups.")
    else:
        print(f"\n  ✅ {actionable} actionable signal(s) found.")

    print(f"\n{'═' * 90}\n")


# ═════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="NEPSE Expert Analysis — 6-Gate Buy Verification Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s NABIL                            # Deep analysis of NABIL
  %(prog)s --scan                           # Full market scan
  %(prog)s --scan --sector "Commercial Banks"
  %(prog)s --scan --top 10                  # More stocks per sector

Via alias:
  nepse expert NABIL
  nepse expert --scan
        """,
    )
    parser.add_argument("symbol", nargs="?", default=None,
                        help="Stock symbol to analyze (e.g. NABIL, NICA)")
    parser.add_argument("--scan", action="store_true",
                        help="Scan entire market through 6-Gate verification")
    parser.add_argument("--sector", type=str, default=None,
                        help="Filter by sector name (e.g. 'Commercial Banks')")
    parser.add_argument("--top", type=int, default=5,
                        help="Top N stocks per sector for TA phase (default 5)")
    args = parser.parse_args()

    if not args.scan and not args.symbol:
        parser.print_help()
        sys.exit(1)

    start = time.time()

    if args.scan:
        verdicts = asyncio.run(scan_expert(sector=args.sector, top_n=args.top))
        print_scan(verdicts)
    else:
        v = asyncio.run(analyze_single(args.symbol))
        if v:
            print_verdict(v)
        else:
            print(f"\n  ❌ Analysis failed for {args.symbol}. Check symbol and try again.")
            sys.exit(1)

    elapsed = time.time() - start
    print(f"  ⏱  Total time: {elapsed:.1f}s\n")


if __name__ == "__main__":
    main()
