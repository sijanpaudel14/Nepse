# NEPSE AI — Master Trading Guide

### How to Run the System, Analyse Every Signal, and Buy Stocks Profitably

> **Author:** NEPSE AI Quant System v2.1  
> **Date:** March 2026 (updated 30 March 2026)  
> **Audience:** You — the operator of this system  
> **Goal:** Beat 90% of NEPSE traders using systematic, quantitative analysis

---

## ⚡ What Changed in v2.1 (30 March 2026 — Read This First)

Three critical bug fixes and two new tools were shipped. **Your system was not working fully before this update.**

| #   | What Was Fixed / Added               | Effect                                                                                                                                                                                                                    |
| --- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **`fetch_today_prices` crash fixed** | `python main.py --fetch-only` no longer crashes with `AttributeError`. Live data now correctly calls `fetcher.fetch_live_market()`. The root cause: wrong method name in `main.py`.                                       |
| 2   | **Screener completely replaced**     | The old 4-strategy `StockScreener` (confidence 0–10) is **gone**. All scans now go through the full **4-Pillar `MasterStockScreener`** (score 0–100) with broker intelligence, unlock risk, fundamentals, and technicals. |
| 3   | **CSS engine import crash fixed**    | `analysis/signal_scorer.py` was missing `import pandas as pd`, so the entire CSS engine failed silently on every run. Now fixed.                                                                                          |
| 4   | **CSS score on every scan result**   | Every stock returned by the screener now includes a CSS score (0–1) and signal automatically. The 4-Pillar score tells you WHAT to buy; CSS tells you WHEN.                                                               |
| 5   | **`paper_trader.py` created**        | New dedicated entry point with two modes: **Stealth Radar** (detect smart money accumulation before price moves) and **Full Scan** (daily 4-Pillar + CSS).                                                                |

> **If you have old bookmarks:** The output format changed. Scores are now 0–100, not 0–10. See Part 2.3 for the updated output format and Part 2.5 for the new Paper Trader commands.

---

## Part 1 — Setup (Do This Once)

### Step 1.1 — Environment Setup

```bash
# Navigate to the trading engine
cd "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading"

# Activate the Python virtual environment (ALWAYS do this first)
source .venv312/bin/activate

# Verify you are in the right environment
python --version   # Should show Python 3.12.x
which python       # Should show path ending in .venv312/bin/python
```

### Step 1.2 — Create Your .env File

```bash
cp .env.example .env
nano .env    # or use any text editor
```

Fill in these values:

```env
# ── DATABASE ──────────────────────────────
DATABASE_URL=sqlite:///./nepse_data.db

# ── OPENAI (for AI signal validation) ────
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

# ── TELEGRAM (for trade alerts) ──────────
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-personal-chat-id

# ── TRADING PARAMETERS ────────────────────
RISK_PER_TRADE=0.02        # 2% of capital per trade (DO NOT change this)
MAX_POSITIONS=5             # Max 5 open positions
MIN_PRICE=200               # Ignore stocks below Rs. 200

# ── SHAREHUB (required for broker intelligence) ──
SHAREHUB_AUTH_TOKEN=your-bearer-token-from-browser

# ── JWT (set once, keep secret) ──────────
JWT_SECRET_KEY=generate-with-python-c-import-secrets-print-secrets-token-urlsafe-64
```

**How to get SHAREHUB_AUTH_TOKEN:**

1. Open ShareHub.com in Chrome
2. Press F12 → Network tab
3. Click on any API call → Headers
4. Find `Authorization: Bearer xxxxx`
5. Copy that `xxxxx` into `SHAREHUB_AUTH_TOKEN`

### Step 1.3 — Initialize the Database

```bash
cd "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading"
source .venv312/bin/activate

python -c "from core.database import init_db; init_db(); print('Database ready')"
```

Expected output:

```
Database ready
```

### Step 1.4 — Verify Installation

```bash
python -c "
from analysis.quant_indicators import QuantIndicators
from analysis.signal_scorer import compute_css
from risk.portfolio_risk_engine import PortfolioRiskEngine
from backtesting.engine import quick_backtest
print('All modules loaded successfully')
"
```

---

## Part 2 — The Daily Trading Routine (10 Minutes Every Morning)

NEPSE trading session: **Sunday–Thursday, 11:00 AM – 3:00 PM NST**

### Step 2.1 — Run Before Market Opens (10:00–10:30 AM)

```bash
cd "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading"
source .venv312/bin/activate

# STEP 1: Fetch latest market data
python main.py --fetch-only
```

What this does:

- Downloads all NEPSE stock prices from NepseUnofficialApi
- Saves to your local SQLite database (bulk upsert — fast)
- Fetches NEPSE index summary
- Checks data freshness (warns if data is stale)

Expected output:

```
STEP 1: Fetching market data...
Saved 247 price records to database
NEPSE Index: 2,847.23 (+0.45%)
Market: 134 ↑ | 89 ↓ | 24 →
```

### Step 2.2 — Check Market Breadth

```bash
python -c "
from intelligence.market_breadth import MarketBreadthAnalyzer
a = MarketBreadthAnalyzer()
snap = a.get_market_breadth()

# Save to DB for historical tracking
a.save_breadth_snapshot(snap)

# Print today's market state
print(a.format_report(snap))

# Check for divergence warnings
div = a.detect_multi_day_divergence(days=5)
if div:
    print()
    print('DIVERGENCE WARNING:', div)
"
```

**How to read this output:**

| Indicator          | What it Means                     | Action                               |
| ------------------ | --------------------------------- | ------------------------------------ |
| Breadth > 60%      | More than 60% of stocks advancing | Good day to enter                    |
| Breadth 40–60%     | Mixed market                      | Be selective, only HIGH CSS scores   |
| Breadth < 40%      | Most stocks falling               | Stay out, protect capital            |
| Regime = OVERSOLD  | Nearly all stocks down            | Contrarian buy opportunity (careful) |
| BEARISH DIVERGENCE | Index up, breadth weak            | This rally is fake — do NOT chase    |
| BULLISH DIVERGENCE | Index down, breadth strong        | Dip is a buying opportunity          |

### Step 2.3 — Run the Full Signal Scanner

```bash
# Full pipeline: data + screen + signals + notify
python main.py --dry-run    # Dry run: see signals, no Telegram spam
```

OR if you already fetched data:

```bash
python main.py --screen-only
```

**What happens (v2.1):**

1. Every active NEPSE stock is scored through the **4-Pillar Master Screener**
2. Stocks with total score ≥ 60/100 are shortlisted (top 10 returned)
3. Each result **automatically includes a CSS score** (0–1) computed on the same data
4. Final trade plans (entry, target, stop-loss, R:R) are printed for each stock

**Expected output (v2.1 format):**

```
STEP 2: Running 4-Pillar Master Screener...
Found 7 high-scoring stocks (score >= 60)
  1. NABIL: STRONG BUY (score: 74.5/100 | CSS: 0.71)
  2. NICA: BUY (score: 68.2/100 | CSS: 0.63)
  3. SBL: BUY (score: 65.1/100 | CSS: 0.59)

STEP 3: Preparing final signals...
Generated 7 final signals
  STRONG_BUY: NABIL
  BUY: NICA, SBL
  HOLD: UPPER

📊 NEPSE MASTER SCREENER RESULTS
==================================================

1. NABIL — STRONG BUY (74.5/100) | CSS 0.71 [BUY]
   🟢 Buyer dominance 78.2% | EMA9 > EMA21 | RSI 58.3 | Brokers accumulating
   Entry: Rs.505.76  Target: Rs.551.00  SL: Rs.469.50  R:R 2.4x
   Hold: ~10d (max 15d)
   Exit: If price hits Rs.551 OR drops below Rs.469.50 OR after 15d

2. NICA — BUY (68.2/100) | CSS 0.63 [BUY]
   ...
```

> **Note:** Score is now 0–100 (not 0–10 like before). "STRONG BUY" = score ≥ 70. "BUY" = score ≥ 60. See Part 13 for the full decision matrix.

### Step 2.4 — Run with Live Telegram Alerts (Production Mode)

Once you're comfortable:

```bash
# Real alerts sent to your Telegram
python main.py
```

This sends:

- A daily summary at the start
- Individual alert for each STRONG_BUY
- Format: Symbol, 4-Pillar score, CSS, entry price, stop-loss, target, rationale

### Step 2.5 — Paper Trader: Stealth Radar and Targeted Scans

`paper_trader.py` is the dedicated command-line tool for deeper daily analysis. It exposes two modes that `main.py` does not:

#### Mode A — Stealth Radar (find tomorrow's winners today)

This is your biggest edge. While everyone else waits for the EMA golden cross, you detect brokers quietly accumulating **before** the price moves.

**Logic:** If broker score is high (≥ 18/30) but technical score is still low (≤ 12/30), operators are accumulating in the background and the price has not reacted yet. That's your entry window.

```bash
# Detect smart money accumulation across ALL NEPSE stocks
python paper_trader.py stealth

# Narrow to a specific sector
python paper_trader.py stealth --sector bank
python paper_trader.py stealth --sector hydro
python paper_trader.py stealth --sector microfinance
python paper_trader.py stealth --sector life_insurance
```

**Example output:**

```
🕵️  STEALTH ACCUMULATION RADAR  —  2026-03-30
   Filter: Broker≥18 | Tech≤12 | Dist=LOW
======================================================================

1. UPPER  (Hydro Power) | CSS 0.44 [HOLD]
   LTP: Rs.510.00  |  Broker Score: 22.4/30  |  Tech Score: 9.1/30
   Distribution Risk: LOW  |  Broker Avg Cost: Rs.495.20  |  Profit%: +3.0%
   Accumulation Window: +48,200 shares (1M) / +12,500 shares (1W)
   Suggested Entry: Rs.517.65  |  Target: Rs.582.00  |  SL: Rs.488.40
   ⚠️  CSS: Weak technical momentum — early stage, watch closely.

2. NABIL  (Commercial Banks) | CSS 0.69 [BUY]
   LTP: Rs.498.00  |  Broker Score: 24.1/30  |  Tech Score: 10.5/30
   Distribution Risk: LOW  |  Broker Avg Cost: Rs.471.00  |  Profit%: +5.7%
   Accumulation Window: +92,300 shares (1M) / +18,100 shares (1W)
   ✅ CSS CONFIRMS: Technical setup aligning with accumulation!
```

**How to act on stealth results:**

| CSS Signal        | 1W Accumulation                              | Action                                       |
| ----------------- | -------------------------------------------- | -------------------------------------------- |
| BUY or STRONG_BUY | Positive                                     | Enter now, 50% size. Add on EMA crossover.   |
| HOLD or WEAK_BUY  | Positive                                     | Add to watchlist. Enter when RSI crosses 50. |
| Any               | Negative (1W distributing while 1M positive) | Skip — operators taking early profits.       |
| Any               | Distribution Risk = MEDIUM or HIGH           | Skip — not safe.                             |

#### Mode B — Full Scan (daily 4-Pillar + CSS)

```bash
# Default scan: value strategy, min score 60
python paper_trader.py scan

# Momentum scan for hydro sector (hydro season play)
python paper_trader.py scan --strategy momentum --sector hydro

# High conviction only (score ≥ 70/100)
python paper_trader.py scan --min-score 70

# Quick scan — top 50 stocks by volume (2–3 minutes instead of 15)
python paper_trader.py scan --quick

# All strategy options
python paper_trader.py scan --strategy value     # undervalued vs sector PE
python paper_trader.py scan --strategy momentum  # trending and breaking out
python paper_trader.py scan --strategy growth    # earnings growth plays
```

**Example output:**

```
📊 MASTER SCREENER RESULTS  —  2026-03-30
   Strategy: VALUE  |  Min Score: 60
======================================================================

1. NABIL  —  STRONG BUY  (74.5/100) | CSS 0.71 [BUY]
   🟢 Buyer dominance 78.2% | EMA9>EMA21 | RSI 58.3 | PE below sector median
   Entry: Rs.505.76  Target: Rs.551.00  SL: Rs.469.50  R:R 2.4x
   Hold: ~10d (max 15d)
   Exit: If price hits Rs.551 OR drops below Rs.469.50 OR after 15d

2. SBL  —  BUY  (65.1/100) | CSS 0.63 [BUY]
   🟢 Top 3 brokers 54.3% | RSI 52.1 | Volume 2.1x average
   Entry: Rs.340.15  Target: Rs.374.00  SL: Rs.318.40  R:R 2.2x
   Hold: ~8d (max 14d)

✅ CSS-confirmed BUY signals: NABIL, SBL

======================================================================
Total: 4 stock(s) passed (score ≥ 60/100)
```

#### When to Use Each Mode

| Situation                                        | Command                                                          |
| ------------------------------------------------ | ---------------------------------------------------------------- |
| Daily morning scan, want today's actionable list | `python paper_trader.py scan`                                    |
| Want to find stocks before they move             | `python paper_trader.py stealth`                                 |
| Watching only one sector (e.g., hydro season)    | `python paper_trader.py scan --sector hydro --strategy momentum` |
| Limited capital, want only highest conviction    | `python paper_trader.py scan --min-score 70`                     |
| Market just opened, quick 2-minute check         | `python paper_trader.py scan --quick`                            |

---

## Part 3 — Understanding Scores: 4-Pillar (0–100) and CSS (0–1)

The system uses **two scores** that work together. Both are automatically calculated on every scan.

### 3.1 — The 4-Pillar Score (0–100): "Is This Stock Worth Buying?"

Calculated by `MasterStockScreener`. Stocks below 60 are rejected before you see them.

| Score  | Recommendation | What It Means                                    |
| ------ | -------------- | ------------------------------------------------ |
| 70–100 | STRONG BUY     | All pillars aligned. High conviction. Full size. |
| 60–69  | BUY            | Most pillars positive. Normal position size.     |
| 50–59  | SPECULATIVE    | Weak pillar present. Half size, tight stop.      |
| < 50   | REJECTED       | Never shown in output.                           |

**The 4 pillars:**

| Pillar                 | Max | What It Measures                                                  |
| ---------------------- | --- | ----------------------------------------------------------------- |
| Broker / Institutional | 30  | Smart brokers net buying? Top-3 concentration? Distribution risk? |
| Unlock Risk            | 20  | Promoter / MF unlock soon? (−50 penalty if < 30 days away!)       |
| Fundamentals           | 20  | PE vs sector median, ROE, EPS quality, dividend history           |
| Technical & Momentum   | 30  | EMA alignment, RSI zone, volume spike, ADX, 200-day EMA trend     |

Extra layers: market regime penalty (−15 in bear), manipulation detection (−15 to −50), divergence alert.

### 3.2 — The CSS Score (0–1): "Is the Entry Timing Right NOW?"

CSS answers: _"Is price action at a good entry point right now?"_

As of v2.1, every stock that passes the 4-Pillar screen automatically gets a CSS score.

```
CSS = (Trend × 0.25) + (Momentum × 0.20) + (Volume × 0.20)
    + (Volatility × 0.10) + (Operator × 0.15) + (Fundamental × 0.10)
```

**The golden rule: 4-Pillar tells you WHAT to buy. CSS tells you WHEN.**

| 4-Pillar | CSS Signal          | Action                                            |
| -------- | ------------------- | ------------------------------------------------- |
| ≥ 70     | STRONG_BUY or BUY   | ✅ Enter full size                                |
| ≥ 70     | WEAK_BUY            | ✅ Enter half size, set alert                     |
| ≥ 70     | HOLD                | ⏳ Stock is great but entry timing is poor — wait |
| 60–69    | BUY or STRONG_BUY   | ✅ Enter half size                                |
| 60–69    | HOLD or below       | ❌ Skip — fundamentals ok but price action warns  |
| Any      | SELL or STRONG_SELL | ❌ Do not enter; exit if holding                  |

| CSS       | Signal      | Meaning                                     |
| --------- | ----------- | ------------------------------------------- |
| ≥ 0.75    | STRONG_BUY  | All 6 components confirm. Rare — act on it. |
| 0.65–0.74 | BUY         | Strong entry confirmed                      |
| 0.55–0.64 | WEAK_BUY    | Entry ok in BULLISH market only             |
| 0.40–0.54 | HOLD        | Wait for better entry                       |
| < 0.35    | SELL / EXIT | Exit if holding                             |

### 3.3 — How to Get CSS for a Stock (Manual Analysis)

```bash
python -c "
import pandas as pd
from core.database import SessionLocal, Stock, DailyPrice
from analysis.quant_indicators import QuantIndicators
from analysis.signal_scorer import compute_css, analyze_stock_css

# Load data for a specific stock
SYMBOL = 'NABIL'   # Change this to any NEPSE symbol

db = SessionLocal()
stock = db.query(Stock).filter(Stock.symbol == SYMBOL).first()
if not stock:
    print(f'Stock {SYMBOL} not found in database. Run --fetch-only first.')
    exit()

prices = (db.query(DailyPrice)
          .filter(DailyPrice.stock_id == stock.id)
          .order_by(DailyPrice.date.desc())
          .limit(100)
          .all())
db.close()

# Build DataFrame
df = pd.DataFrame([{
    'date': p.date, 'open': p.open, 'high': p.high,
    'low': p.low, 'close': p.close, 'volume': p.volume
} for p in reversed(prices)])
df = df.set_index('date')

# Compute indicators
qi = QuantIndicators()
indicators = qi.get_latest_indicators(df)

# Compute CSS score (swing profile — for 10-20 day trades)
result = analyze_stock_css(SYMBOL, indicators, profile='swing')

print(f'=== {SYMBOL} CSS Analysis ===')
print(f'CSS Score:   {result.css:.3f}')
print(f'Signal:      {result.signal}')
print(f'Confidence:  {result.confidence}')
print()
print('Component Breakdown:')
for k, v in result.components.items():
    bar = int(v * 20)
    print(f'  {k:<15} {v:.2f}  [' + '=' * bar + ' ' * (20-bar) + ']')
"
```

### 3.4 — How to Read the CSS Component Breakdown

**TREND (0–1): Is the stock in an uptrend?**

- Score > 0.7 → EMA10 > EMA30, ADX > 25, Supertrend bullish = strong uptrend
- Score 0.4–0.7 → Mixed signals, trend forming
- Score < 0.4 → Downtrend or sideways — skip

**MOMENTUM (0–1): Is the stock gaining speed?**

- Score > 0.7 → RSI 55–70, StochRSI just crossed up, EMA slope rising
- Score < 0.4 → RSI below 40, momentum fading — dangerous to enter

**VOLUME (0–1): Are big players buying?**

- Score > 0.7 → RVOL > 2.0 (today's volume is 2x the average), OBV rising
- Score < 0.4 → Low volume — price move is NOT confirmed, could fake out

**VOLATILITY (0–1): Is the price in a good entry zone?**

- Score > 0.7 → Bollinger Band squeeze (breakout coming), %B near midzone
- Score < 0.4 → Bollinger %B > 0.9 (overbought at top of band) — late entry risk

**OPERATOR (0–1): Are brokers accumulating?**

- Score > 0.7 → Top 3 brokers control > 50% of volume, net buyers. This is the NEPSE edge.
- Score < 0.4 → Brokers are net sellers or distribution in progress — EXIT

**FUNDAMENTAL (0–1): Is the company reasonably valued?**

- Score > 0.7 → PE below sector median (e.g., for bank: PE < 22), ROE > 15%
- Score < 0.4 → Overvalued or poor ROE — avoid for swing, OK for short-term

---

## Part 4 — How to Analyze a Specific Stock (Deep Dive)

This is your full analysis workflow for any stock before buying.

### 4.1 — Price History and Indicators

```bash
python -c "
SYMBOL = 'NABIL'   # <-- change this

import pandas as pd
from core.database import SessionLocal, Stock, DailyPrice
from analysis.quant_indicators import QuantIndicators

db = SessionLocal()
stock = db.query(Stock).filter(Stock.symbol == SYMBOL).first()
prices = (db.query(DailyPrice)
          .filter(DailyPrice.stock_id == stock.id)
          .order_by(DailyPrice.date.desc()).limit(60).all())
db.close()

df = pd.DataFrame([{
    'date': p.date, 'open': p.open, 'high': p.high,
    'low': p.low, 'close': p.close, 'volume': p.volume
} for p in reversed(prices)])
df.set_index('date', inplace=True)

qi = QuantIndicators()
ind = qi.get_latest_indicators(df)

print(f'=== {SYMBOL} Indicators ===')
print(f'Price:        Rs. {ind[\"close\"]:.2f}')
print(f'EMA10:        Rs. {ind[\"ema10\"]:.2f}   (above = uptrend backbone)')
print(f'EMA30:        Rs. {ind[\"ema30\"]:.2f}   (crossover = trend signal)')
print(f'RSI:          {ind[\"rsi\"]:.1f}        (30=oversold, 70=overbought)')
print(f'RVOL:         {ind[\"rvol\"]:.2f}x      (>1.5 = above-avg volume)')
print(f'ADX:          {ind[\"adx\"]:.1f}        (>25 = strong trend)')
print(f'BB %B:        {ind[\"bb_pctb\"]:.2f}       (0=lower band, 1=upper band)')
print(f'ATR:          Rs. {ind[\"atr\"]:.2f}   (daily volatility range)')
print(f'SuperTrend:   {\"BULLISH\" if ind[\"supertrend_dir\"] > 0 else \"BEARISH\"}')
print(f'Squeeze:      {\"YES — breakout coming!\" if ind[\"squeeze\"] else \"No\"}')
"
```

### 4.2 — Broker Intelligence (Your Edge)

This is what 99% of NEPSE traders cannot see. Run this to check WHO is buying:

```bash
python -c "
# Load ShareHub broker data for a stock
# You need SHAREHUB_AUTH_TOKEN in .env for this

from data.sharehub_api import ShareHubAPI
from intelligence.broker_profiles import build_broker_profiles

SYMBOL = 'NABIL'

try:
    api = ShareHubAPI()
    # Get broker data (last 90 days)
    broker_data = api.get_broker_data(SYMBOL, days=90)
    summary = build_broker_profiles(broker_data, symbol=SYMBOL)

    print(f'=== {SYMBOL} Broker Intelligence ===')
    print(f'Signal Strength:  {summary.signal_strength}')
    print(f'Buyer HHI:        {summary.buyer_concentration_30d:.3f}  (>0.25 = concentrated buying)')
    print(f'Net 30d:          {summary.total_net_30d:+,.0f} shares')
    print(f'Net 60d:          {summary.total_net_60d:+,.0f} shares')
    print()

    if summary.top_buyers:
        print('Top Accumulators (last 30 days):')
        for b in summary.top_buyers[:5]:
            status = '← ACCUMULATING' if b.is_accumulating else ''
            reversal = f' ⚠️ {b.trend_reversal}' if b.trend_reversal else ''
            print(f'  Broker {b.broker_id} ({b.broker_name}):  '
                  f'{b.net_30d:+,} shares {status}{reversal}')

    if summary.top_sellers:
        print()
        print('Top Distributors (last 30 days):')
        for b in summary.top_sellers[:3]:
            print(f'  Broker {b.broker_id}: {b.net_30d:+,} shares ← SELLING')

except Exception as e:
    print(f'Could not load broker data: {e}')
    print('Check SHAREHUB_AUTH_TOKEN in .env')
"
```

**What to look for:**

- `STRONG_ACCUMULATION` → At least 1 top broker accumulating consistently over 30d+60d+90d
- `DISTRIBUTION_START` reversal → A broker that was buying for 90 days is now selling. **Exit warning.**
- `buyer_concentration_30d > 0.25` → Few brokers control the buy side → operator in play → follow them

### 4.3 — Market Breadth Context

```bash
python -c "
from intelligence.market_breadth import MarketBreadthAnalyzer
a = MarketBreadthAnalyzer()

# 5-day divergence check
warn = a.detect_multi_day_divergence(days=5)
print('5-Day Divergence:', warn or 'None — market breadth is healthy')

# 30-day history summary
history = a.get_breadth_history(days=30)
if not history.empty:
    avg_b = history['breadth_pct'].mean()
    recent_b = history['breadth_pct'].tail(5).mean()
    print(f'30-day avg breadth:  {avg_b:.1f}%')
    print(f'Last 5-day avg:      {recent_b:.1f}%')
    if recent_b > avg_b + 10:
        print('CAUTION: Breadth spiking — possible blow-off top')
    elif recent_b < avg_b - 10:
        print('OPPORTUNITY: Breadth below average — potential bounce')
"
```

### 4.4 — Floorsheet Concentration (Operator Trap Detection)

```bash
python -c "
# Requires floorsheet data from NEPSE or ShareHub
# This example shows how to use the analyzer with your data

from intelligence.floorsheet_tracker import analyze_floorsheet_concentration

# Replace with actual floorsheet trades for the stock
# Each entry: {buyer_broker_id, seller_broker_id, quantity}
sample_trades = [
    {'buyer_broker_id': '58', 'seller_broker_id': '12', 'quantity': 5000},
    {'buyer_broker_id': '58', 'seller_broker_id': '34', 'quantity': 3000},
    {'buyer_broker_id': '36', 'seller_broker_id': '22', 'quantity': 2000},
]

result = analyze_floorsheet_concentration(sample_trades, 'NABIL')
print(f'HHI:           {result.hhi:.0f}   (>2500 = operator control)')
print(f'Top-3 share:   {result.top3_share_pct:.1f}%  (>40% = few brokers dominate)')
print(f'Level:         {result.concentration_level}')
print(f'Operator?      {result.is_operator_likely}')
"
```

### 4.5 — NRB Macro Context

Update this weekly with the latest NRB data:

```bash
python -c "
from intelligence.macro_engine import compute_macro_score

# Get these numbers from: https://www.nrb.org.np
score = compute_macro_score(
    interbank_rate=4.5,      # NRB daily interbank rate %
    ccd_ratio=72.0,           # Credit-to-Core-Deposit ratio %
    inflation_rate=5.2,       # Latest CPI inflation %
    remittance_growth=8.0,    # Monthly remittance growth %
    base_rate=7.0,            # NRB base rate %
)

print(f'Macro Signal:       {score.macro_signal}')
print(f'Liquidity Score:    {score.liquidity_score:.0f}/100')
print(f'Banking Health:     {score.banking_health_score:.0f}/100')
print(f'Overall Macro:      {score.overall_macro_score:.0f}/100')
print()
print('Trading implications:')
if score.macro_signal in ['BULLISH', 'MILD_BULLISH']:
    print('  ✅ Macro supports buying banks and finance stocks')
if score.banking_health_score < 40:
    print('  ⚠️ CCD ratio high — banks near lending limit, AVOID new bank positions')
if score.liquidity_score > 70:
    print('  ✅ High liquidity — money flowing into market, good for all sectors')
"
```

---

## Part 5 — The Pre-Trade Risk Check (NEVER Skip This)

Before you execute ANY trade, run this check:

```bash
python -c "
from risk.portfolio_risk_engine import PortfolioRiskEngine

# Initialize with YOUR actual portfolio capital
engine = PortfolioRiskEngine(capital=500000)   # Change to your actual capital

# Check if a specific trade is allowed
SYMBOL = 'NABIL'
PRICE = 500.0       # Current price from ShareHub/NEPSE
SHARES = 50         # How many shares you want to buy
SECTOR = 'Commercial Banks'
ATR = 15.0          # From indicators output above

result = engine.pre_trade_check(
    symbol=SYMBOL,
    price=PRICE,
    shares=SHARES,
    sector=SECTOR,
    atr=ATR,
)

print(f'Trade allowed: {result.allowed}')
if result.allowed:
    print(f'Position size multiplier: {result.position_size_mult:.1f}x')
    print()
    print('APPROVED — You may execute this trade')
    print(f'Entry:       Rs. {PRICE:.2f}')
    stop = PRICE - (2 * ATR)
    target = PRICE + (3 * ATR)
    print(f'Stop Loss:   Rs. {stop:.2f}  ({((stop - PRICE)/PRICE*100):+.1f}%)')
    print(f'Target:      Rs. {target:.2f}  ({((target - PRICE)/PRICE*100):+.1f}%)')
    print(f'Risk Amount: Rs. {SHARES * (PRICE - stop):.0f}')
else:
    print()
    print(f'BLOCKED: {result.reason}')
    print('Do NOT execute this trade.')
"
```

**The 8 gates this check enforces:**

| Gate                | Limit             | If Blocked, Do This                          |
| ------------------- | ----------------- | -------------------------------------------- |
| 1. Daily loss limit | 3% of capital     | Stop trading today. Resume tomorrow.         |
| 2. Max drawdown     | 20% of peak       | Stop trading. Review strategy.               |
| 3. Max positions    | 5 open            | Close one existing position first.           |
| 4. Max per-stock    | 25% of capital    | Reduce shares.                               |
| 5. Sector limit     | 30% in one sector | No more bank stocks if 3 banks already open. |
| 6. Correlation      | Max 3 same sector | Diversify sectors.                           |
| 7. Signal quality   | CSS ≥ 0.60        | Only trade high-quality signals.             |
| 8. Risk budget      | Kelly sizing      | System auto-calculates max safe size.        |

---

## Part 6 — How to Calculate Your Position Size

Never guess how many shares to buy. Use the system:

```bash
python -c "
from risk.position_sizer import PositionSizer

sizer = PositionSizer()

CAPITAL = 500_000   # Your total trading capital in Rs.
PRICE = 500.0       # Stock price
ATR = 15.0          # ATR from indicators output

# Quarter-Kelly risk-based sizing
shares, risk_amount = sizer.calculate_position(
    capital=CAPITAL,
    price=PRICE,
    atr=ATR,
    win_rate=0.55,     # Assume 55% from backtests
    avg_win=0.12,      # 12% average win
    avg_loss=0.06,     # 6% average loss
)

total_cost = shares * PRICE
pct_of_capital = (total_cost / CAPITAL) * 100

print(f'Position Size:    {shares} shares')
print(f'Total Investment: Rs. {total_cost:,.0f}  ({pct_of_capital:.1f}% of capital)')
print(f'Max Risk (Rs.):   Rs. {risk_amount:,.0f}  ({risk_amount/CAPITAL*100:.1f}% of capital)')
print(f'Stop Level:       Rs. {PRICE - (2*ATR):.2f}')
print()
print('NEPSE cost to buy:')
commission = total_cost * 0.0036
sebon = total_cost * 0.00015
print(f'  Broker:  Rs. {commission:.0f}')
print(f'  SEBON:   Rs. {sebon:.0f}')
print(f'  TOTAL:   Rs. {commission + sebon:.0f}')
"
```

**Quick mental sizing rule:**

- Risk per trade = 2% of capital
- If stop is Rs. 10 below entry → buy `(capital × 0.02) ÷ 10` shares maximum
- Example: Capital = Rs. 5 lakh, stop = 10 below → max 1000 shares

---

## Part 7 — How to Validate a Strategy Before Trading Real Money

### Backtest One Stock

```bash
python main.py --backtest NABIL --backtest-start 2023-01-01
```

OR use the detailed Python backtest:

```bash
python -c "
import pandas as pd
from core.database import SessionLocal, Stock, DailyPrice
from backtesting.engine import quick_backtest, walk_forward_backtest

SYMBOL = 'NABIL'
CAPITAL = 500_000

db = SessionLocal()
stock = db.query(Stock).filter(Stock.symbol == SYMBOL).first()
prices = (db.query(DailyPrice)
          .filter(DailyPrice.stock_id == stock.id)
          .order_by(DailyPrice.date).all())
db.close()

df = pd.DataFrame([{
    'date': p.date, 'open': p.open, 'high': p.high,
    'low': p.low, 'close': p.close, 'volume': p.volume
} for p in prices])
df.set_index('date', inplace=True)

print('=== Quick Backtest (CSS Swing) ===')
result = quick_backtest(df, initial_capital=CAPITAL, mode='css_swing')
print(f'Total Return:  {result.total_return_pct:.1f}%')
print(f'CAGR:          {result.cagr_pct:.1f}%')
print(f'Sharpe Ratio:  {result.sharpe_ratio:.2f}  (>1.0 = good, >1.5 = excellent)')
print(f'Max Drawdown:  {result.max_drawdown_pct:.1f}%')
print(f'Win Rate:      {result.win_rate_pct:.1f}%')
print(f'Profit Factor: {result.profit_factor:.2f}  (>1.5 = profitable edge)')
print(f'Total Trades:  {result.total_trades}')
"
```

### Walk-Forward Validation (Trust This More Than Simple Backtest)

```bash
python -c "
import pandas as pd
from core.database import SessionLocal, Stock, DailyPrice
from backtesting.engine import walk_forward_backtest

SYMBOL = 'NICA'
CAPITAL = 500_000

db = SessionLocal()
stock = db.query(Stock).filter(Stock.symbol == SYMBOL).first()
prices = (db.query(DailyPrice)
          .filter(DailyPrice.stock_id == stock.id)
          .order_by(DailyPrice.date).all())
db.close()

df = pd.DataFrame([{
    'date': p.date, 'open': p.open, 'high': p.high,
    'low': p.low, 'close': p.close, 'volume': p.volume
} for p in prices])
df.set_index('date', inplace=True)

results = walk_forward_backtest(df, train_months=6, test_months=2,
                                 initial_capital=CAPITAL, mode='css_swing')

print('=== Walk-Forward Results ===')
print(f'Windows tested: {len(results)}')
print()
for r in results:
    status = '✅' if r.total_return_pct > 0 else '❌'
    print(f'{status} Return: {r.total_return_pct:+.1f}%  |  '
          f'Sharpe: {r.sharpe_ratio:.2f}  |  '
          f'WinRate: {r.win_rate_pct:.0f}%')

wins = sum(1 for r in results if r.total_return_pct > 0)
print()
print(f'Profitable windows: {wins}/{len(results)}')
"
```

**Reading walk-forward results:**

- If > 60% of windows are profitable → the strategy is robust
- If < 50% profitable → strategy is curve-fitted, do NOT trade live

### Monte Carlo Significance Test

```bash
python -c "
import pandas as pd
from core.database import SessionLocal, Stock, DailyPrice
from backtesting.engine import monte_carlo_test

SYMBOL = 'NABIL'
db = SessionLocal()
stock = db.query(Stock).filter(Stock.symbol == SYMBOL).first()
prices = (db.query(DailyPrice)
          .filter(DailyPrice.stock_id == stock.id)
          .order_by(DailyPrice.date).all())
db.close()

df = pd.DataFrame([{
    'date': p.date, 'open': p.open, 'high': p.high,
    'low': p.low, 'close': p.close, 'volume': p.volume
} for p in prices])
df.set_index('date', inplace=True)

stats = monte_carlo_test(df, n_simulations=500, mode='css_swing')
print('=== Monte Carlo Significance ===')
print(f'Actual return:    {stats[\"actual_return\"]:+.1f}%')
print(f'Random 95th pct:  {stats[\"percentile_95\"]:+.1f}%')
print(f'P-value:          {stats[\"p_value\"]:.3f}')
print()
if stats['p_value'] < 0.05:
    print('✅ STATISTICALLY SIGNIFICANT — this edge is real, not luck')
else:
    print('⚠️ NOT statistically significant — may be luck. Use caution.')
"
```

### Compare All Strategies

```bash
python -c "
import pandas as pd
from core.database import SessionLocal, Stock, DailyPrice
from backtesting.engine import compare_strategies

SYMBOL = 'SBL'
db = SessionLocal()
stock = db.query(Stock).filter(Stock.symbol == SYMBOL).first()
prices = (db.query(DailyPrice)
          .filter(DailyPrice.stock_id == stock.id)
          .order_by(DailyPrice.date).all())
db.close()

df = pd.DataFrame([{
    'date': p.date, 'open': p.open, 'high': p.high,
    'low': p.low, 'close': p.close, 'volume': p.volume
} for p in prices])
df.set_index('date', inplace=True)

comparison = compare_strategies(df, initial_capital=500_000)
print(comparison.to_string(index=False))
# Best strategy for this stock is the top row
"
```

---

## Part 8 — How to Buy a Stock (Step-by-Step)

NEPSE has NO API for order placement. All execution is manual via TMS (Trading Management System). The system generates the SIGNAL, YOU execute the TRADE.

### The Complete Buy Process

**STEP 1: Identify the signal (automated by this system)**

The system tells you:

```
STRONG BUY: NABIL
CSS Score: 0.71 (BUY)
Entry Zone: Rs. 495-505
Stop Loss: Rs. 472 (-5.6%)
Target: Rs. 551 (+10.5%)
Holding Period: 10-15 trading days
```

**STEP 2: Verify with your own eyes (5 minutes)**

Go to ShareHub.com and open the NABIL chart. Confirm:

- [ ] Price is above EMA10 (short green line should be above the longer line)
- [ ] Volume today is above average (thick green candles)
- [ ] No news of promoter share unlock in next 2 weeks (check MeroShare)
- [ ] No circuit hit yesterday (price not bouncing off the -10% floor)

**STEP 3: Run the pre-trade check**

```bash
python -c "
from risk.portfolio_risk_engine import PortfolioRiskEngine
engine = PortfolioRiskEngine(capital=500000)
result = engine.pre_trade_check('NABIL', 500.0, 50, 'Commercial Banks', 15.0)
print('ALLOWED:', result.allowed)
if not result.allowed: print('REASON:', result.reason)
"
```

**STEP 4: Calculate exact size**

From the output above:

- Entry: Rs. 505 (ask price, entry on the buy side)
- Stop: Rs. 472 → Risk per share = Rs. 33
- Position = `(Capital × 2%) ÷ Risk per share` = `(500,000 × 0.02) ÷ 33` = **303 shares**
- Round down to nearest 100 for clean lots: **300 shares**
- Total cost = 300 × 505 = **Rs. 1,51,500**
- Broker commission = Rs. 1,51,500 × 0.0036 = **Rs. 545**
- SEBON = Rs. 1,51,500 × 0.00015 = **Rs. 23**
- Total deduction needed = Rs. 1,52,068

**STEP 5: Log the position in the system**

```bash
python -c "
from risk.portfolio_risk_engine import PortfolioRiskEngine
from datetime import date

engine = PortfolioRiskEngine(capital=500000)

# Register the entry so the system tracks your stop
engine.register_entry(
    symbol='NABIL',
    entry_price=505.0,    # Your actual fill price
    shares=300,
    sector='Commercial Banks',
    atr=15.0
)
print('Position registered. Stop and trailing stop are now active.')
"
```

**STEP 6: Execute in TMS**

1. Login to your broker's TMS (meroshare.cdsc.com.np or broker portal)
2. Navigate to: Orders → New Order → Buy
3. Symbol: NABIL
4. Quantity: 300
5. Price: 505.00 (limit order — DO NOT use market order in NEPSE)
6. Confirm order

**STEP 7: Enter your stop mentally**
The system calculated your stop as Rs. 472. Set a price alert on your phone at Rs. 478 (give yourself 2 days to exit above the stop before it's hit). There is no automatic stop-loss in NEPSE TMS.

---

## Part 9 — Position Management (While Holding)

### Daily Stop Check

Every evening after market close, run:

```bash
python -c "
from risk.portfolio_risk_engine import PortfolioRiskEngine

engine = PortfolioRiskEngine(capital=500000)

# Update with today's closing prices
engine.update_prices({
    'NABIL': 515.0,     # Today's close for each open position
    'NICA': 920.0,
    # add all your open positions
})

# System will print:
# - Whether trailing stops were ratcheted up
# - Alerts if any price dropped below stop
# - P&L for each position
"
```

### When the Trailing Stop Ratchets

The ATR trailing stop automatically tightens as profit increases:

| Your Profit | Stop Distance | Effect                             |
| ----------- | ------------- | ---------------------------------- |
| 0-1 ATR     | 2.0 × ATR     | Loose stop — gives room to breathe |
| 1-2 ATR     | 1.5 × ATR     | Tighter — you've got cushion now   |
| 2-3 ATR     | 1.0 × ATR     | Protecting most of your profit     |
| 3+ ATR      | 0.75 × ATR    | Very tight — capturing near peak   |

**Example (NABIL, ATR = Rs.15, Entry = Rs.505):**

- After price hits Rs. 520 (+1 ATR): Stop moves to Rs. 497.50
- After price hits Rs. 535 (+2 ATR): Stop moves to Rs. 512.50 (now profitable even if stopped)
- After price hits Rs. 550 (+3 ATR): Stop moves to Rs. 535 (locked in Rs. 30/share profit)

### When to Exit

Exit when ANY of these occur:

1. **Stop-loss hit**: Price touches your stop level → Sell immediately via TMS
2. **Target reached**: Price hits target (Rs.551 in our example) → Sell 50-75% of position
3. **CSS turns SELL**: Re-run CSS after 5 trading days. If CSS < 0.35 → Exit
4. **Operator flip**: Broker who was accumulating flips to distribution → Exit
5. **Market regime change**: Breadth drops below 30% for 3 days → Defensive exit

### How to Exit (TMS)

1. Orders → New Order → Sell
2. Symbol: NABIL
3. Quantity: 300 (or partial — sell 150 at target, hold 150 with trailing stop)
4. Price: Current bid price or your target
5. Confirm

**IMPORTANT:** You cannot sell within 3 calendar days of purchase (T+2 settlement). The system enforces this — attempting to sell before T+2 will be blocked.

---

## Part 10 — Weekly Routine (Sunday Mornings)

NEPSE is closed Sunday. Use this time for analysis:

```bash
# 1. Compare strategy performance this week
python -c "
# Run backtest comparison on your most-watched stocks
from backtesting.engine import compare_strategies
# ... load df for each stock and compare
"

# 2. Update NRB macro data (check nrb.org.np)
python -c "
from intelligence.macro_engine import compute_macro_score
from core.database import SessionLocal, MacroSnapshot
from datetime import date

score = compute_macro_score(
    interbank_rate=4.5,
    ccd_ratio=72.0,
    inflation_rate=5.2,
    remittance_growth=8.0,
    base_rate=7.0,
)

# Save to database for trend tracking
db = SessionLocal()
snap = MacroSnapshot(
    date=date.today(),
    interbank_rate=4.5,
    ccd_ratio=72.0,
    inflation_rate=5.2,
    remittance_growth=8.0,
    base_rate=7.0,
    liquidity_score=score.liquidity_score,
    banking_health_score=score.banking_health_score,
    overall_macro_score=score.overall_macro_score,
)
db.add(snap)
db.commit()
db.close()
print(f'Macro saved. Signal: {score.macro_signal}')
"

# 3. Save this week's breadth history
python -c "
from intelligence.market_breadth import MarketBreadthAnalyzer
a = MarketBreadthAnalyzer()
history = a.get_breadth_history(days=30)
print(history.tail(10).to_string())
"
```

---

## Part 11 — Running as Automated Scheduler

Set this up to run automatically every trading day:

```bash
# Start the scheduler daemon (runs analysis at 10:30 AM NST every trading day)
python main.py --schedule
```

This runs:

- **10:20 AM**: Fetch market data
- **10:30 AM**: Full analysis pipeline
- **10:45 AM**: Telegram notification of signals
- **3:15 PM**: Post-market summary of filled positions

To run in the background (keep terminal free):

```bash
nohup python main.py --schedule > /tmp/nepse_scheduler.log 2>&1 &
echo "Scheduler started. Check /tmp/nepse_scheduler.log"
```

To check if it's running:

```bash
ps aux | grep "python main.py"
```

---

## Part 12 — Web Dashboard (Optional)

The system has a web API and dashboard:

```bash
# Start the API server
cd "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading"
source .venv312/bin/activate

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Open in browser: `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

Useful API endpoints:
| Endpoint | What it shows |
|----------|--------------|
| `/api/market/summary` | NEPSE index, breadth, top movers |
| `/api/signals` | Today's generated signals |
| `/api/portfolio` | Your open positions and P&L |
| `/api/stocks/{symbol}` | Full data for one stock |
| `/api/fundamentals/{symbol}` | PE, ROE, broker analysis |

---

## Part 13 — Signal Decision Matrix (Quick Reference)

Laminate this and keep it next to your screen:

```
           4-PILLAR SCORE  ×  CSS SIGNAL  ×  MARKET BREADTH

                              MARKET BREADTH
                         < 40%    40-60%    > 60%
                      ┌─────────┬─────────┬─────────┐
 Score ≥ 70 + CSS BUY │  SKIP   │  BUY-S  │  BUY-F  │
 Score ≥ 70 + HOLD CSS│  SKIP   │  SKIP   │  WATCH  │
 Score 60-69 + CSS BUY│  SKIP   │  SKIP   │  BUY-S  │
 Score 60-69 + HOLD   │  SKIP   │  SKIP   │  SKIP   │
 Score < 60 (any)     │  SKIP   │  SKIP   │  SKIP   │
 STEALTH hit + CSS BUY│  SKIP   │  WATCH  │  BUY-S  │
                      └─────────┴─────────┴─────────┘

BUY-F = Buy Full Size    BUY-S = Buy Small (50% size)
WATCH = Watchlist only   SKIP  = Do not trade
```

**Before executing ANY trade, all of these must be true:**

- [ ] Pre-trade check returns `ALLOWED: True`
- [ ] Broker signal is NOT `DISTRIBUTION`
- [ ] No circuit hit in last 3 days
- [ ] At least 20 sessions of data available
- [ ] Not within 5 days of AGM, bonus/right allotment, or FPO

---

## Part 14 — Common Mistakes and How to Avoid Them

| Mistake                          | Why It's Deadly                             | System Fix                                             |
| -------------------------------- | ------------------------------------------- | ------------------------------------------------------ |
| Chasing a stock after +8% day    | Circuit limit leaves only 2% upside         | CSS operator score penalizes this automatically        |
| Buying during BEARISH DIVERGENCE | Narrow rallies reverse hard                 | Breadth divergence detector blocks entry               |
| Overloading one sector           | Sector gets crushed together                | 30% sector limit in pre-trade check                    |
| Ignoring stop-loss               | One loss wipes multiple wins                | ATR stop calculated at entry, system reminds you daily |
| Trading on FOMO/news             | News is priced in by the time you hear it   | CSS freshness decay reduces old-signal confidence      |
| Selling too early                | Miss 80% of the move                        | Trailing stop captures most of trend                   |
| Buying illiquid stocks           | Can't exit when you need to                 | Volume-slippage model shows true cost upfront          |
| Using old screener output        | Score is 0–10 but system now uses 0–100     | Re-run `paper_trader.py scan` — all output is current  |
| Running without activating venv  | `fetch_today_prices` crash or module errors | Always `source .venv312/bin/activate` first            |

---

## Quick Command Reference

```bash
# ── ENVIRONMENT (always first) ──────────────────────────────────
source .venv312/bin/activate

# ── MAIN PIPELINE (main.py) ─────────────────────────────────────
python main.py --fetch-only          # Fetch live market data into database
python main.py --screen-only         # Display top 4-Pillar + CSS picks
python main.py --dry-run             # Full pipeline, no Telegram spam
python main.py                       # Full pipeline + send Telegram alerts
python main.py --schedule            # Run as daily daemon (10:30 AM NST)
python main.py --backtest NABIL --backtest-start 2023-01-01
python main.py --ipo-exit SOHL       # IPO exit signal analysis

# ── PAPER TRADER: STEALTH (paper_trader.py) ─────────────────────
python paper_trader.py stealth                      # Smart money radar, all sectors
python paper_trader.py stealth --sector bank        # Bank sector only
python paper_trader.py stealth --sector hydro       # Hydro sector only

# ── PAPER TRADER: SCAN ───────────────────────────────────────────
python paper_trader.py scan                         # Full 4-Pillar + CSS daily scan
python paper_trader.py scan --strategy value        # Undervalued plays (default)
python paper_trader.py scan --strategy momentum     # Trending / breakout plays
python paper_trader.py scan --sector hydro --strategy momentum
python paper_trader.py scan --min-score 70          # High conviction only
python paper_trader.py scan --quick                 # Fast: top 50 stocks by volume

# ── WEB API ──────────────────────────────────────────────────────
uvicorn api.main:app --host 0.0.0.0 --port 8000

# ── HEALTH CHECKS ────────────────────────────────────────────────
python -c "from core.database import init_db; init_db(); print('DB OK')"
python -c "from analysis.signal_scorer import compute_css; print('CSS OK')"
python -c "from analysis.master_screener import MasterStockScreener; print('Screener OK')"
python -c "from data.fetcher import NepseFetcher; f = NepseFetcher(); print('Fetcher OK')"
```

---

> **Disclaimer:** This system provides analysis and signals based on quantitative algorithms. All trade execution is manual and your responsibility. Past backtested performance does not guarantee future results. Never risk more than you can afford to lose. Start with paper trading for at least 30 days before using real capital.
