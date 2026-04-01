# NEPSE AI — Complete Trader Playbook

### The System That Beats 99% of Nepali Traders

> **Version:** 3.0 — March 2026  
> **System:** nepse_ai_trading + nepse-chart-extension  
> **Audience:** You — the sole operator of this institutional-grade pipeline  
> **Commitment required:** 15 minutes before market open. Rest is automated.

---

## Table of Contents

1. [Why This System Wins](#1-why-this-system-wins)
2. [System Architecture — What Runs What](#2-system-architecture)
3. [One-Time Setup (Do This Once)](#3-one-time-setup)
4. [The Daily Routine (15 Minutes)](#4-the-daily-routine)
5. [The 6-Gate Expert Analysis — Deep Dive](#5-the-6-gate-expert-analysis)
6. [Stealth Radar — Finding Tomorrow's Winners Today](#6-stealth-radar)
7. [Understanding Every Score](#7-understanding-every-score)
8. [NRB Macro Context — Updating Weekly](#8-nrb-macro-context)
9. [Position Sizing — The Math That Keeps You Alive](#9-position-sizing)
10. [Risk Management Rules (Non-Negotiable)](#10-risk-management-rules)
11. [Sector Rotation Playbook](#11-sector-rotation-playbook)
12. [Market Breadth — Reading the Battlefield](#12-market-breadth)
13. [Backtesting Your Intuition](#13-backtesting)
14. [Decision Trees — What to Do in Every Situation](#14-decision-trees)
15. [The Complete Command Reference](#15-complete-command-reference)
16. [Common Mistakes and How to Avoid Them](#16-common-mistakes)
17. [Performance Tracking](#17-performance-tracking)

---

## 1. Why This System Wins

### The Average Nepali Trader's Reality

| What They Do                                    | Why It Fails                                       |
| ----------------------------------------------- | -------------------------------------------------- |
| Follow TikTok/Facebook groups for tips          | You are the exit liquidity                         |
| Buy on "rumours" of AGM or dividend             | Brokers already positioned before you hear it      |
| Use one indicator (RSI or "golden cross")       | Lagging signals, 60% of moves are already over     |
| No stop-loss ("I'll hold until it comes back")  | Rs. 1L becomes Rs. 40K in a market correction      |
| Buy at 52-week highs "because it's strong"      | Chasing distribution — buying from operators       |
| Hold losing positions, sell winning ones quick  | Cutting flowers and watering weeds                 |
| No position sizing ("all in" on a single stock) | One bad trade wipes 50%; it takes +100% to recover |

### What This System Does Instead

| This System                                        | The Edge It Creates                              |
| -------------------------------------------------- | ------------------------------------------------ |
| 6-Gate verification before any buy                 | Eliminates emotion and FOMO completely           |
| Detects **broker accumulation before price moves** | You buy with operators, not after them           |
| Multi-timeframe alignment across 7 timeframes      | Only enter when the trade structure is confirmed |
| CSS: 6-component entry timing with 30+ indicators  | Enter at the best price, not just any price      |
| 2% capital risk rule via Kelly-calibrated sizing   | A 10-loss streak costs 18%, not 50%              |
| NRB macro + breadth + sector rotation context      | Know if the wind is at your back or in your face |
| Manipulation + distribution detection              | Never step in front of an operator exit          |
| Market regime kill switch (PANIC mode)             | Stays in cash during crashes automatically       |

**The honest summary:** You will not win every trade. But this system will:

1. Make sure every trade you take has a statistical edge
2. Make sure losses are small and recoverable
3. Make sure you never hold dead weight indefinitely
4. Generate data so you can prove your win rate to yourself

---

## 2. System Architecture

```
nepse_ai_trading/               ← The Engine
│
├── tools/expert_analysis.py   ← YOUR PRIMARY TOOL (6-Gate Expert)
├── tools/paper_trader.py      ← Daily scan, stealth radar, portfolio tracking
├── tools/populate_db.py       ← Historical data pipeline for backtesting
├── analysis/
│   ├── master_screener.py     ← 4-Pillar scoring (80+ metrics per stock)
│   └── signal_scorer.py       ← CSS: 6-component entry timing score
├── intelligence/
│   ├── macro_engine.py        ← NRB macroeconomic scoring
│   ├── sector_rotation.py     ← Sector momentum and rotation signals
│   ├── market_breadth.py      ← Advance/decline ratio and heatmap
│   └── order_flow.py          ← Smart money order flow analysis
├── backtesting/engine.py      ← Full backtest with NEPSE cost model
├── risk/position_sizer.py     ← Kelly/risk-based position sizing
└── config/macro.json          ← YOUR MACRO DASHBOARD (update weekly)

nepse-chart-extension/         ← The Chart Intelligence Layer
└── backend/screener.py        ← 13-point checklist + 7-TF + intraday
```

### How They Connect

```
NepseAlpha Chart API ──▶ screener.py (Gate 1 + 2: TA + Multi-TF)
                                          │
ShareHub Broker API  ──▶ master_screener  (Gate 3: 4-Pillar)
                                          │
CSS Engine           ──▶ signal_scorer    (Gate 4: Entry timing)
                                          │
Risk Engine          ──▶ manipulation_det (Gate 5: Risk clearance)
                                          │
Macro + Breadth      ──▶ macro/breadth    (Gate 6: Market regime)
                                          │
                              ▼
                    6-GATE VERDICT: BLIND BUY / STRONG BUY / BUY
                    TRADE PLAN: Entry, Target, SL, Position size
```

---

## 3. One-Time Setup

### 3.1 — Terminal Setup

The `nepse` alias is already configured in `~/.zshrc` — it automatically:

- `cd`s into the right project folder
- Uses the correct venv Python (`nepse_ai_trading/.venv312/bin/python`)
- Runs `tools/paper_trader.py` which dispatches all subcommands

**You never need to `cd` or `source` anything.** Open any terminal and run:

```bash
nepse expert NABIL        # 6-Gate deep analysis of NABIL
nepse expert --scan       # Full market scan through 6 gates
nepse stealth             # Broker accumulation radar
nepse scan                # Daily 4-Pillar scan
nepse status              # Portfolio status
nepse populate            # Fill local DB for backtesting
nepse confirm SYMBOL      # Live 3-trigger entry check
```

If `nepse` stops working (e.g. after a system restart), run once to reload:

```bash
source ~/.zshrc
```

### 3.2 — env File (Required)

```bash
cp .env.example .env
```

Critical keys to fill:

```env
DATABASE_URL=sqlite:///./nepse_data.db

# ShareHub (required for broker intelligence):
SHAREHUB_AUTH_TOKEN=your-bearer-token

# Get it: chrome → sharehub.com → F12 → Network → any API call → Authorization: Bearer XXXXX

# Optional but recommended:
OPENAI_API_KEY=sk-...         # For AI signal validation
TELEGRAM_BOT_TOKEN=xxx        # For trade alerts
TELEGRAM_CHAT_ID=xxx

# Risk parameters (DO NOT change these unless you fully understand Kelly):
RISK_PER_TRADE=0.02            # 2% — the golden rule
MAX_POSITIONS=5
MIN_PRICE=200
```

### 3.3 — Initialize DB

```bash
python main.py --fetch-only
```

`main.py` initializes the DB automatically on every run. `--fetch-only` stops after DB init + price fetch, so it's the fastest way to confirm the DB is ready.

### 3.4 — Populate Historical Price Data (for backtesting)

```bash
# Downloads 2 years of OHLCV for all ~200 NEPSE stocks (~4 minutes)
nepse populate

# OR if you just want a few key stocks to start:
nepse populate --symbols NABIL NICA UPPER SBL PCBL --days 365
```

This fills the SQLite DB so the backtest engine can run. **Without this, backtests return empty.**

After the first run, update daily:

```bash
nepse populate --incremental    # Only fetches missing dates (fast, <30 seconds)
```

### 3.5 — Update Macro Config (Weekly)

Edit `config/macro.json` with data from NRB's monthly publication:

```json
{
  "interbank_rate": 4.5,
  "ccd_ratio": 72.0,
  "inflation_rate": 5.5,
  "remittance_growth": 8.0,
  "base_rate": 7.5
}
```

Source: https://www.nrb.org.np → Publications → Current Macroeconomic Situation

**Default values bring neutral (50/100) macro score. Real data makes Gate 6 prescise.**

---

## 4. The Daily Routine

NEPSE trading hours: **Sunday–Thursday, 11:00 AM – 3:00 PM NST**

```
10:00 AM  ──  Pre-market routine (15 min)
11:00 AM  ──  Market opens — act on watchlist only
12:00 PM  ──  Mid-session check (2 min)
 2:45 PM  ──  Pre-close review (5 min)
----
 Evening  ──  Update portfolio + prepare next day (5 min)
```

### 10:00 AM — Pre-Market (15 Minutes Total)

#### Step 1: Market Breadth Snapshot (2 min)

```bash
nepse expert --scan --sector "Commercial Banks" 2>/dev/null | head -20
```

Or for a quick breadth only:

```bash
nepse --heatmap
```

**Decision:**

| Breadth %                 | Regime     | What to do today                                    |
| ------------------------- | ---------- | --------------------------------------------------- |
| > 60%                     | BULLISH    | Normal day. Run full scan, act on BUY verdicts      |
| 40–60%                    | NEUTRAL    | Be selective. Only STRONG BUY (7+ gates, score ≥70) |
| < 40%                     | BEARISH    | Protect capital. No new entries. Review stops.      |
| < 20%                     | OVERSOLD   | Cash only. Watch for bounce setup tomorrow          |
| Index ↑ but breadth < 45% | DIVERGENCE | Index is lying. This rally is narrow. Do not chase  |

#### Step 2: Check Your Sector (2 min)

```bash
nepse --sector-rotation
```

Trade stocks from **HOT sectors** first. Avoid stocks in COLD sectors unless score is ≥80/100.

#### Step 3: Expert Scan (8 min)

```bash
# Full market scan — runs 6 gates on all technical candidates
nepse expert --scan

# OR scan a specific hot sector today:
nepse expert --scan --sector "Hydro Power"
nepse expert --scan --sector "Commercial Banks"
```

Act only on: **BLIND BUY** or **STRONG BUY** verdicts. Add BUY verdicts to watchlist.

#### Step 4: Deep Analysis on Top Candidates (3 min)

For each BLIND BUY or STRONG BUY from the scan:

```bash
nepse expert NABIL    # Replace NABIL with the symbol
```

Read the full 6-Gate output before placing any order. If you see something you don't understand, do NOT enter.

### 11:00 AM — Market Opens

**Trade only what was in your pre-market plan.** No FOMO buys.

- If a stock was BLIND BUY and entry status was `🟢 ENTRY READY` → Buy at open
- If status was `🟡 ENTRY ZONE` → Set a limit order at the entry price shown
- If status was `🔴 WAIT` → Do not enter yet, re-run at 12:00 PM

**Order placement:**

1. Place buy order at the entry price shown (with slippage already included in the price)
2. **Immediately** set stop-loss at the SL price shown
3. Set price alert at target price
4. Log the trade (see Part 17)

### 12:00 PM — Mid-Session Check (2 min)

```bash
nepse status    # Check if any position hit target or stop
```

If any "WAIT" entries from pre-market have not entered yet, run the 3-trigger live check:

```bash
nepse confirm SYMBOL             # Auto-detects breakout level from swing-high resistance
nepse confirm SYMBOL --breakout-level 430   # Override with specific chart level
```

**Read the output:**

- `2/3 or 3/3 triggers ✅` → Enter now. Price action is confirming.
- `1/3 triggers ✅` → Watch — partial confirmation. Check again at 12:45 PM.
- `0/3 triggers ✅` → Do not enter. The opportunity window has not opened yet.
- Broker flip ✅ but Volume/Price still ❌ → _Stealth window_ — smart money buying before the move. Highest probability setup. Enter partial size (50%) at current price.

If the entry status has fully upgraded, confirm with:

```bash
nepse expert SYMBOL    # Re-run to confirm entry status changed to READY
```

### 2:45 PM — Pre-Close (5 min)

```bash
nepse update    # Auto-checks position outcomes
```

- If target hit → close at market
- If stop triggered → close immediately, no negotiating
- If position is significantly in profit (>7%) but target not reached → consider partial exit

### Evening — End of Day (5 min)

```bash
nepse report    # Full portfolio performance report
nepse populate --incremental    # Update DB with today's prices
```

---

## 5. The 6-Gate Expert Analysis

This is your core decision engine. Run it with `nepse expert SYMBOL`.

```
Gate 1 — Technical Foundation     (max 25 pts)
Gate 2 — Multi-TF Confluence      (max 15 pts)
Gate 3 — 4-Pillar Fundamentals    (max 25 pts)
Gate 4 — CSS Confirmation         (max 15 pts)
Gate 5 — Risk Clearance           (max 10 pts)
Gate 6 — Market Regime + Macro    (max 10 pts)
────────────────────────────────────────────
TOTAL                             (max 100 pts)
```

### Gate 1 — Technical Foundation (25 pts)

Checks 13 specific conditions from the professional WIDGET_GUIDE protocol.

| Score   | Points | Meaning                                  |
| ------- | ------ | ---------------------------------------- |
| ≥ 10/13 | 25     | PASS — Strong technical structure        |
| 8–9/13  | 15     | PARTIAL — Mostly bullish, minor weakness |
| < 8/13  | 0      | FAIL — Technical setup not ready         |

**The 13 checks:**

| #   | Check                        | What it Tests                        |
| --- | ---------------------------- | ------------------------------------ |
| 1   | Verdict BUY                  | AI daily verdict from all indicators |
| 2   | Trend confirmed              | UPTREND + ADX > 20 + EMA10 > EMA30   |
| 3   | RSI 40–70                    | Not overbought, has room to run      |
| 4   | Price > SMA50                | Medium-term structural bull          |
| 5   | MACD Bullish                 | Momentum confirmation                |
| 6   | Multi-TF ≥50% BUY            | Other timeframes agree               |
| 7   | No death cross / RSI 80+     | No red flags present                 |
| 8   | Volume ratio ≥ 1.2x average  | Real buying, not just price drift    |
| 9   | Near support ≤8% or breakout | Good entry location                  |
| 10  | Wyckoff: Accumulation/Markup | Structure stage is favorable         |
| 11  | No operator distribution     | Smart money not selling to you       |
| 12  | Not chasing 52W high         | Not buying at the top                |
| 13  | R:R ≥ 1.5x                   | Reward justifies the risk            |

**Key insight on this gate:** If checks 7, 11, 12 fail (death cross, distribution, 52W high), those are hard stops. Do not override. A stock can fail multiple checks but still pass if those three are clear.

### Gate 2 — Multi-Timeframe Confluence (15 pts)

| Alignment  | Points | Action                                      |
| ---------- | ------ | ------------------------------------------- |
| ≥ 70% BUY  | 15     | PASS — Multi-TF confirmed, strong momentum  |
| 50–69% BUY | 10     | PARTIAL — Wait for more TF alignment        |
| < 50% BUY  | 0      | FAIL — Different timeframes disagree, risky |

**Why this matters:** A stock showing BUY on daily but SELL on weekly is in a short-term recovery within a downtrend. You'd be fighting the larger structure. Only enter when ≥ 5/7 timeframes agree.

**The 7 timeframes checked:** Daily, Bi-Weekly, Weekly, Monthly, Quarterly, Semi-Yearly, Yearly.

### Gate 3 — 4-Pillar Fundamentals (25 pts)

| Master Score | Base Points | Adjustments                          |
| ------------ | ----------- | ------------------------------------ |
| ≥ 70/100     | 25          | +3 if sector HOT / -2 if sector COLD |
| 55–69/100    | 15          | +3 if sector HOT / -2 if sector COLD |
| < 55/100     | 0           | Only sector bonus (max +3)           |

**The 4 pillars:**

**Pillar 1 — Broker Intelligence (max 30 pts):**
The most NEPSE-specific pillar. Analyzes floorsheet data from ShareHub to detect which brokers are net buying vs net selling. Operators always use specific brokers consistently.

- Buyer dominance > 70% for top 3 brokers → high score
- Top broker accumulating in both 1M and 1W timeframes → PASS
- 1M accumulating but 1W distributing → Distribution Divergence (watch out)

**Pillar 2 — Unlock Risk (max 20, can penalize -50):**
If promoter shares unlock within 30 days → instant -50 penalty. This is a trap many traders fall into: stock looks perfect technically but a massive unlock is coming.

- No unlock within 90 days → full 20 pts
- Unlock in 30–90 days → 10 pts
- Unlock < 30 days → -50 pts (stock automatically rejected in most scans)

**Pillar 3 — Fundamentals (max 20 pts):**
PE vs sector median, ROE > 15%, consistent EPS growth, dividend history, PBV.

**Pillar 4 — Technical + Momentum (max 30 pts):**
EMA alignment (9/21/50/200), RSI zone, volume spike, ADX, price vs SMA200.

**Bonus sector context:** If the system detects your stock's sector is currently HOT (leading sector rotation), Gate 3 gets +3 pts. If the sector is COLD, -2 pts. This prevents you from buying great fundamentals in a sector the market is leaving.

### Gate 4 — CSS Confirmation (15 pts)

CSS = _"Is right now a good entry point?"_

| CSS Score + Signal      | Points | Action                                       |
| ----------------------- | ------ | -------------------------------------------- |
| ≥ 0.60 + BUY/STRONG_BUY | 15     | PASS — Enter with confidence                 |
| ≥ 0.45 + not SELL       | 8      | PARTIAL — Entry is suboptimal but acceptable |
| < 0.45 or SELL signal   | 0      | FAIL — Momentum not confirming yet           |

CSS components (what makes up the score):

```
CSS = Trend(25%) + Momentum(20%) + Volume(20%) + Volatility(10%)
    + Operator(15%) + Fundamental(10%)
```

**The pattern that matters most:** When Gate 3 (fundamentals) is high but Gate 4 (CSS) is low — this is the stealth accumulation setup. The fundamentals are strong but the chart hasn't moved yet. This is early. Watch it, wait for CSS to rise above 0.45.

### Gate 5 — Risk Clearance (10 pts)

This gate is a **kill switch**. CRITICAL failures → verdict forced to AVOID regardless of other gate scores.

| Condition                   | Points | Meaning                                           |
| --------------------------- | ------ | ------------------------------------------------- |
| Manipulation: NONE or LOW   | +5     | Safe — no operator games                          |
| Manipulation: MEDIUM        | +2     | Caution                                           |
| Manipulation: HIGH/CRITICAL | FAIL   | **AVOID — operators actively working this stock** |
| Distribution: LOW           | +3     | Safe — brokers not selling aggressively           |
| Distribution: CRITICAL      | FAIL   | **AVOID — brokers are handing shares to retail**  |
| No intraday dump            | +2     | No pump-and-dump pattern today                    |

**Read this gate carefully before entering any trade.** A stock can score 80+ points overall but Gate 5 FAIL → total verdict = AVOID. The system enforces this automatically.

### Gate 6 — Market Regime + Macro + Breadth (10 pts)

| Condition              | Points | Notes                                           |
| ---------------------- | ------ | ----------------------------------------------- |
| BULL + strong macro    | 10     | Full size, full confidence                      |
| NEUTRAL + good breadth | 7–8    | Standard entry                                  |
| BEAR                   | 3–5    | Reduce size 50%, tighter stops                  |
| PANIC                  | 0      | **KILL SWITCH — No buying, all verdicts AVOID** |
| BULL + breadth < 35%   | –2 pts | Narrow rally — caution, reduce size             |
| Macro < 40/100         | –1 pt  | NRB headwinds — reduce size 25%                 |

**Macro contributions to this gate:**

| NRB Macro Signal | Meaning                                       |
| ---------------- | --------------------------------------------- |
| BULLISH (≥70)    | Low interbank rate, CCD room, good remittance |
| MILD_BULLISH     | Most indicators positive                      |
| NEUTRAL          | Mixed signals — no clear direction from NRB   |
| MILD_BEARISH     | Some tightening signals                       |
| BEARISH (< 30)   | High rates, CCD near limit, low remittance    |

### Reading the Final Verdict

| Verdict    | Score | Gates Failed | Meaning + Action                                      |
| ---------- | ----- | ------------ | ----------------------------------------------------- |
| BLIND BUY  | ≥ 85  | 0            | All 6 gates clear, bull market. BUY AT OPEN tomorrow  |
| STRONG BUY | ≥ 70  | ≤ 1          | 5+ gates. Check the PARTIAL gate. Buy with confidence |
| BUY        | ≥ 55  | ≤ 2          | 4+ gates. Review FAIL gates, reduce to half size      |
| RISKY      | ≥ 40  | 3+           | Too many flags. Put on watchlist only                 |
| AVOID      | Any   | Risk/PANIC   | Do not trade. Protect capital.                        |

---

## 6. Stealth Radar

The stealth radar is your most powerful early-warning tool. It detects brokers accumulating before the price moves — you get in **with** smart money, not after.

```bash
nepse stealth                              # All NEPSE stocks
nepse stealth --sector bank                # Banks only
nepse stealth --sector hydro               # Hydro only
```

### What It Detects

A stock appears in stealth radar when:

- Broker score ≥ 18/30 (institutional accumulation detected)
- Technical score ≤ 12/30 (chart has NOT reacted yet)
- Distribution risk = LOW or N/A

This gap between high broker score and low technical score is the accumulation window. The typical timeline: broker accumulation detected → 2–8 weeks → price starts moving → technicals trigger → 90% of traders enter.

**You enter at week 1. They enter at week 3. You exit profitably. They enter into your exit.**

### Stealth Entry Rules

| CSS at Stealth Detection | 1W Net Holdings          | Action                                          |
| ------------------------ | ------------------------ | ----------------------------------------------- |
| BUY or STRONG_BUY        | Positive                 | Enter 50% size NOW. Add full size on EMA cross. |
| HOLD or WEAK_BUY         | Positive                 | Add to watchlist. Wait for RSI to cross 50.     |
| Any                      | Negative 1W              | SKIP — Divergence: brokers may be reversing.    |
| Any                      | Distribution MEDIUM/HIGH | CRITICAL SKIP — Trap setup.                     |

### Stealth to Expert Confirmation Workflow

```
1. nepse stealth          → Find accumulation candidates
2. Wait 2–5 days          → Monitor if 1W accumulation continues
3. nepse expert SYMBOL    → Run 6-Gate when technical setup forms
4. Enter when verdict ≥ BUY + Gate 5 clear
```

---

## 7. Understanding Every Score

### The Score Hierarchy (Most Important → Least)

```
Gate 5 (Risk Clearance)     — BLOCKING: FAIL means AVOID regardless of score
Gate 6 (Regime/PANIC)       — BLOCKING: PANIC means AVOID for ALL stocks
Gate 1 (13-pt Checklist)    — Highest weight (25 pts)
Gate 3 (4-Pillar)           — Highest weight (25 pts)
Gate 2 (Multi-TF)           — Medium weight (15 pts)
Gate 4 (CSS)                — Medium weight (15 pts)
```

### Score vs Action Table

```
90–100 (BLIND BUY, 0 fails)        → BUY AT OPEN. Full position. Set SL immediately.
75–89  (STRONG BUY, ≤1 fail)       → Buy same day. Read the PARTIAL gate. Full or 75% size.
60–74  (BUY, ≤2 fails)             → Buy or use limit order. Half size. Review fails.
45–59  (RISKY)                     → Watchlist only. Track for 3 days.
< 45   (AVOID)                     → Skip. Go to next candidate.
```

### CSS Score Interpretation

| CSS       | Signal           | What the Market is Doing                   |
| --------- | ---------------- | ------------------------------------------ |
| ≥ 0.75    | STRONG_BUY       | All 6 components firing. Rare, act on it.  |
| 0.60–0.74 | BUY              | Strong momentum. Good entry zone.          |
| 0.50–0.59 | WEAK_BUY         | Emerging momentum. Early, use limit order. |
| 0.40–0.49 | HOLD             | Wait. The entry timing is not right yet.   |
| < 0.40    | SELL/STRONG_SELL | Price action deteriorating. Avoid.         |

### 4-Pillar Score Interpretation

| Score    | Meaning                                                               |
| -------- | --------------------------------------------------------------------- |
| ≥ 80/100 | All 4 pillars aligned. Institution-grade quality.                     |
| 70–79    | 3+ pillars strong. High conviction buy.                               |
| 60–69    | 2–3 pillars strong. Buy with reduced size.                            |
| 50–59    | Mixed signals. Speculative. Avoid unless 1 specific pillar very high. |
| < 50     | Filtered out. Never shown.                                            |

---

## 8. NRB Macro Context

### Why NRB Data Matters for NEPSE

NEPSE is **liquidity-driven**. When NRB injects liquidity (low interbank rate, low CCD ratio), banks have money to lend → businesses grow → stocks rise. When NRB tightens (high rates, CCD near 80%), money leaves the market.

The macro engine scores this numerically and feeds it into Gate 6.

### How to Update Weekly

```bash
nano "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading/config/macro.json"
```

Sources for each indicator:

| Indicator           | Where to Find                                     | Update Frequency |
| ------------------- | ------------------------------------------------- | ---------------- |
| `interbank_rate`    | nrb.org.np → Statistics → Money Market            | Daily            |
| `ccd_ratio`         | nrb.org.np → Banking Supervision Quarterly Report | Monthly          |
| `inflation_rate`    | nrb.org.np → Statistics → CPI                     | Monthly          |
| `remittance_growth` | nrb.org.np → Statistics → BOP / Remittance        | Monthly          |
| `base_rate`         | nrb.org.np → Monetary Policy / Base Rate circular | Monthly          |

### Reading the Macro Signal

| Signal       | Score | NEPSE Implication                              | Gate 6 Effect   |
| ------------ | ----- | ---------------------------------------------- | --------------- |
| BULLISH      | ≥ 70  | Low rates, CCD room, strong remittance → Buy   | +full score     |
| MILD_BULLISH | 55–69 | Mostly positive — favorable for equity         | Standard score  |
| NEUTRAL      | 45–54 | No clear direction — stay selective            | Standard score  |
| MILD_BEARISH | 30–44 | Some tightening — reduce all positions 25%     | –1 pt deduction |
| BEARISH      | < 30  | NRB tightening hard — severely reduce exposure | –2 pt deduction |

### NEPSE Macro Calendar

Key dates when NRB events move the market significantly:

| Month            | Event                            | Typical Market Impact               |
| ---------------- | -------------------------------- | ----------------------------------- |
| February         | NRB half-yearly monetary review  | Rate cut → rally; rate hike → dip   |
| July             | Annual monetary policy           | Most important event of NEPSE year  |
| August–September | AGM season (banks, insurance)    | AGM dates drive individual stocks   |
| June–September   | Monsoon (Hydro production peaks) | Hydro stocks often rally seasonally |
| March–April      | Q3 financials                    | Earnings surprises move stocks      |

---

## 9. Position Sizing

**The most important chapter.** This is what separates professionals from gamblers.

### The Golden Rule: Never Risk More Than 2% Per Trade

No matter how confident you are. No matter how "perfect" the setup looks.

Why 2%? Because survival math:

| Risk per trade | 10 losses in a row | Recovery needed        |
| -------------- | ------------------ | ---------------------- |
| 2% per trade   | 18% drawdown       | 22% — recoverable      |
| 5% per trade   | 40% drawdown       | 67% — brutal           |
| 10% per trade  | 65% drawdown       | 186% — near impossible |

### How the System Calculates Your Position

The `expert_analysis.py` output already tells you exactly how many shares to buy, assuming a Rs. 10,00,000 (10 lakh) portfolio:

```
💰 POSITION SIZING  (Rs. 10L portfolio · 2% risk rule)
Buy:          166 shares
Deploy:       Rs. 1,99,200  (19.9% of portfolio)
Max Risk:     Rs.   9,960  (if stop hit)
```

This means: If the stop-loss is hit, you lose Rs. 9,960 — exactly 1% of your Rs. 10L portfolio. The 2% rule is your ceiling, not your target.

### Scaling for Your Actual Portfolio

If your portfolio is **not** Rs. 10 lakhs, multiply shares:

```
Your shares = Shown shares × (Your portfolio / 10,00,000)

Example: You have Rs. 5 lakhs:
  Shown: 166 shares of NABIL at Rs. 1,200
  Your shares = 166 × (5,00,000 / 10,00,000) = 83 shares
```

### Adjusting for Verdict and Market Context

| Verdict    | Market        | Size Modifier       | Actual Risk % |
| ---------- | ------------- | ------------------- | ------------- |
| BLIND BUY  | BULL          | 100% (full size)    | 2.0%          |
| STRONG BUY | BULL          | 75%                 | 1.5%          |
| BUY        | BULL          | 50%                 | 1.0%          |
| Any        | BEAR          | 50% (always halved) | max 1.0%      |
| Any        | breadth < 35% | 50% (narrow market) | max 1.0%      |
| BLIND BUY  | PANIC         | 0% (kill switch)    | 0%            |

### Max Concurrent Positions

```
Portfolio Rs. 5L   → max 3 positions at once
Portfolio Rs. 10L  → max 5 positions at once
Portfolio Rs. 20L+ → max 7 positions at once
```

These limits ensure a catastrophic correlation scenario (all positions drop together) cannot destroy your account.

---

## 10. Risk Management Rules

**These are non-negotiable. No exceptions.**

### The 7 Rules

**Rule 1: Stop-Loss First, Entry Second**
The moment your order is filled, place your stop-loss. Before you check profit. Before you do anything else.

**Rule 2: Never Average Down**
If a stock goes down 5% and you buy more, you are now in a larger losing position. This is how Rs. 1L becomes Rs. 30K. The system gives you a stop-loss price — honor it.

**Rule 3: The 15-Day Rule**
No position should be held beyond 15 trading days unless the thesis has significantly changed to the better (AND you re-run the 6-gate analysis to confirm). Time-based exits prevent capital from being trapped in "waiting to recover" positions.

**Rule 4: 2% Capital Risk Cap (not position size)**
The stop-loss distance determines your shares, not your "conviction" score. A stock 20% below your stop-loss means fewer shares than a stock 3% below. The system calculates this for you.

**Rule 5: Never Enter If Gate 5 Fails**
Distribution risk CRITICAL or manipulation HIGH = AVOID. Always. Even if the score is 82/100.

**Rule 6: PANIC Mode = Cash Only**
When the system shows market regime PANIC, no new entries for any stock. If you have open positions, review stops — consider early exit.

**Rule 7: Do Not Hold Through Unlock Events**
If a stock you hold is approaching an unlock date within 30 days, exit before the unlock unless the 4-Pillar score remains ≥ 70 AND broker accumulation continues post-unlock.

### Stop-Loss Behavior

| Scenario                          | Action                                |
| --------------------------------- | ------------------------------------- |
| Price hits exact stop-loss        | Exit at market. No debate.            |
| Price gaps below stop at open     | Exit at open. Slippage is acceptable  |
| Price drops 5% but not at stop    | Hold. Stop is your only exit signal.  |
| Price up 10% — should I move SL?  | Yes. Trail stop to break-even +2%     |
| Price up 20% — should I trail?    | Move stop to lock in 10% profit       |
| Position approaching 15-day limit | Re-run expert analysis. Decide fresh. |

### Trailing Stop Guide

Once a trade is 10% in profit, trail your stop:

```
Entry:  Rs. 1,200
Stop:   Rs. 1,140  (initial — 5% below)
+10%:   Stock at Rs. 1,320 → Move stop to Rs. 1,260 (break-even +5%)
+15%:   Stock at Rs. 1,380 → Move stop to Rs. 1,320 (lock in 10%)
Target: Rs. 1,380  → Exit. Do not get greedy.
```

---

## 11. Sector Rotation Playbook

### How NEPSE Sectors Rotate

Money moves through NEPSE sectors in predictable cycles based on:

- **Earnings season** (banks release Q results → banking sector leads)
- **Monsoon** (June–September → hydro production peaks → hydro sector)
- **Policy changes** (NRB rate cuts → banking and finance first)
- **AGM season** (August–October → dividend stocks)
- **IQ exports** (Hydro and manufacturing driven by export prices)

### The Rotation Command

```bash
nepse --sector-rotation
```

### Seasonal Calendar for NEPSE

| Month                    | Typically HOT Sectors       | Reason                         |
| ------------------------ | --------------------------- | ------------------------------ |
| Baisakh (Apr-May)        | Banks, Finance, Insurance   | Q3/Q4 results, dividend season |
| Jestha (May-Jun)         | Hydro Power                 | Monsoon approaching            |
| Ashadh-Shrawan (Jun-Aug) | Hydro Power                 | Peak monsoon production        |
| Bhadra-Ashwin (Aug-Oct)  | Banks (AGM), Hydro          | AGM dividends + hydro peak     |
| Mangsir (Nov-Dec)        | Manufacturing, Hotels       | Tourist season + winter demand |
| Magh-Falgun (Jan-Mar)    | Insurance (renewals), Banks | Year-end policy renewals       |

### Sector-Expert Scan Combo

Once you identify HOT sectors from rotation analysis:

```bash
# Scan the hot sector through full 6-Gate verification
nepse expert --scan --sector "Hydro Power"
nepse expert --scan --sector "Commercial Banks"

# Deep dive on the top result
nepse expert UPPER     # or whichever stock topped the scan
```

Gate 3 automatically adjusts for sector phase — a stock in a HOT sector gets +3 pts, COLD sector gets -2 pts.

---

## 12. Market Breadth

### What Breadth Tells You

Breadth = what percentage of ALL NEPSE stocks are advancing today.

The NEPSE index can be UP even when 60% of stocks are DOWN (because large caps like NABIL or UPPER dominate the index weighting). Breadth tells you the truth about what's actually happening.

```bash
nepse --heatmap
```

### Breadth Patterns and What They Mean

**Pattern 1: Bearish Divergence (Most Dangerous)**

```
Index: +0.8%  |  Breadth: 38%
```

The index is rising because 2–3 large-cap stocks are moving. Most stocks are falling. This is distribution — operators are selling out of index heavyweights into retail enthusiasm. **Do not buy into this rally.**

**Pattern 2: Bullish Divergence (Best Buying Opportunity)**

```
Index: -0.5%  |  Breadth: 62%
```

The index fell only because an index-heavy stock dropped. But the majority of stocks advanced. This is accumulation across the board. **This is a buying dip.**

**Pattern 3: Healthy Bull Market**

```
Index: +0.6%  |  Breadth: 68%
```

Most stocks advancing. The rally is broad-based. **Enter freely.**

**Pattern 4: Overbought Warning**

```
Index: +1.2%  |  Breadth: 84%
```

Nearly everyone advancing. This is typically within 3–5 days of a top. **Do not add new positions. Tighten stops on existing ones.**

### Breadth Effect on Gate 6

The system automatically feeds breadth into Gate 6:

- Breadth < 35% in bull market → Gate 6 deducts 2 pts, warns "narrow breadth"
- Breadth > 60% → Gate 6 full score, breadth confirms entry

---

## 13. Backtesting

### Why You Should Backtest Every Setup You Use

Paper trading and backtesting give you one thing Facebook/TikTok tips never can: **a personal win rate**.

When you know your system wins 67% of trades with an average 2.3x R:R over 60 trades, you will stop second-guessing every individual loss. **The loss is a cost of doing business, not evidence the system is broken.**

### Step 1: Populate DB (Required First)

```bash
nepse populate --symbols NABIL NICA UPPER SBL PCBL NIFRA EBL KBL --days 730
```

Wait for completion (~1 minute for 8 symbols).

### Step 2: Run a Backtest

```bash
python main.py --backtest NABIL --backtest-start 2023-01-01 --backtest-end 2025-01-01
```

**What the output tells you:**

```
BacktestResult for NABIL (CSS strategy, 2023-01-01 → 2025-01-01)
────────────────────────────────────────────────────────────────
Total trades:     47
Win rate:         68.1%
Profit factor:    2.34 (every Rs.1 lost, Rs.2.34 gained on wins)
Max drawdown:     -14.3% (worst losing streak)
Sharpe ratio:     1.87 (anything above 1.0 is good)
Total return:     +84.2% vs NEPSE index +31.4%
```

Win rate above 55% + profit factor above 1.5 + Sharpe above 1.0 = validated edge.

### Step 3: Walk-Forward Test (The Serious Validation)

Instead of testing on data used to build the signal, test on fresh data the signal never saw:

```bash
# Split: train on 2022-2023, test on 2024
python main.py --backtest NABIL --backtest-start 2022-01-01 --backtest-end 2023-12-31    # In-sample
python main.py --backtest NABIL --backtest-start 2024-01-01 --backtest-end 2025-01-01    # Out-of-sample
```

If out-of-sample performance is within 20% of in-sample, the edge is real and not curve-fitted.

### What to Backtest

| Priority | What to Test                         | Why                                 |
| -------- | ------------------------------------ | ----------------------------------- |
| 1        | Your most recently traded stock      | See if the 6-Gate would have worked |
| 2        | Current sector candidates            | Validate before entry               |
| 3        | All NEPSE stocks across 2 years      | Build sector-level statistics       |
| 4        | The specific gate combo you're using | Identify which gates add most value |

---

## 14. Decision Trees

### Morning Decision Tree

```
Is breadth > 60%?
├─ YES → Run full scan. Can enter BUY, STRONG BUY, BLIND BUY.
└─ NO  → Is breadth > 40%?
         ├─ YES (40-60%) → Run scan. Enter STRONG BUY and BLIND BUY ONLY.
         └─ NO (<40%)   → No new entries today.
                          Check existing positions.
                          Tighten stops if any.
```

### Stock Selection Decision Tree

```
Run: nepse expert SYMBOL

Step 1: Is Gate 5 (Risk Clearance) = FAIL?
├─ YES (CRITICAL manipulation or distribution) → STOP. Do not enter. Period.
└─ NO → Continue.

Step 2: Is Gate 6 (Regime) = PANIC or FAIL?
├─ YES → STOP. Market regime kill switch. Do not enter.
└─ NO → Continue.

Step 3: What is the total score?
├─ ≥ 85 (BLIND BUY, 0 fails) → Full size. Buy at open tomorrow.
├─ 70-84 (STRONG BUY, ≤1 fail) → 75% size. Check the failing gate. Buy today.
├─ 55-69 (BUY, ≤2 fails) → 50% size. Review fails. Use limit order.
├─ 40-54 (RISKY) → Watchlist only. Check again in 3 days.
└─ <40 (AVOID) → Skip entirely. Move to next candidate.

Step 4: Is entry status ENTRY READY (🟢)?
├─ YES → Buy at open
├─ ENTRY ZONE (🟡) → Use limit order at entry price shown
└─ WAIT (🔴) → Set price alert. Re-run tomorrow morning.
```

### Position Management Tree

```
Is the stock at my target price?
├─ YES → Exit. Full position.
└─ NO → Is it at my stop-loss?
         ├─ YES → Exit. No debate.
         └─ NO → Has it been 15 trading days?
                  ├─ YES → Re-run expert analysis.
                  │         Score ≥ 70? Hold 5 more days.
                  │         Score < 70? Exit within 2 days.
                  └─ NO → Is it up >10% from entry?
                           ├─ YES → Trail stop to break-even +2%
                           └─ NO → Hold. Trust the plan.
```

### Gate Failure Decision Tree

```
Gate 1 FAIL (Technical Foundation)?
├─ Checks 7/11/12 failing (death cross, distribution, 52W high)? → Hard no.
└─ Other checks failing? → Check again in 3–5 days. Wait for setup.

Gate 2 FAIL (Multi-TF)?
└─ Wait for weekly and monthly TF to align. This setup is early.

Gate 3 FAIL (4-Pillar)?
└─ Add to stealth watchlist. Wait for broker accumulation to build.

Gate 4 FAIL (CSS)?
└─ Good stock, bad timing. Set alert for RSI to cross 50. Check daily.

Gate 5 FAIL (Risk) → Never enter. No exceptions.

Gate 6 FAIL (Regime) → Wait. Check market regime in 1–2 weeks.
```

---

## 15. Complete Command Reference

### Expert Analysis (Primary Tool)

```bash
nepse expert NABIL                         # Single stock 6-Gate analysis
nepse expert NABIL NICA SBL                # Multiple stocks
nepse expert --scan                        # Full market scan
nepse expert --scan --sector "Hydro Power" # Sector-filtered scan
nepse expert --scan --sector "Commercial Banks"
nepse expert --scan --top 10               # More candidates per sector
```

### Daily Scan & Screener

```bash
nepse scan                               # Default: value strategy, score ≥ 60
nepse scan --strategy momentum           # Momentum-focused
nepse scan --strategy growth             # Growth-focused
nepse scan --sector bank                 # Banks only
nepse scan --sector hydro                # Hydro only
nepse scan --min-score 70                # High conviction only
nepse scan --quick                       # Fast scan (top stocks by volume)
```

### Entry Confirmation — 3 Live Triggers

Use this during market hours when a stock is in WAIT status. Answers: "Should I enter right now?"

```bash
nepse confirm SGHC                         # Auto-detect breakout level from swing-high resistance
nepse confirm SGHC --breakout-level 430    # Override with specific level
nepse confirm SGHC --broker-threshold 300000   # Lower Rs. 3L threshold (small-cap stocks)
nepse confirm SGHC --volume-threshold 1.2  # Lower volume bar (illiquid stocks)
```

**What it checks:**

- **Trigger 1 — Volume spike:** Today's volume ≥ 1.5x the 20-day average
- **Trigger 2 — Broker flip:** Top-3 brokers net buying > Rs. 5L today (live floorsheet)
- **Trigger 3 — Price breakout:** Price > swing-high resistance (auto-detected) on 15m chart

**Breakout level auto-detection (no manual input needed):**

1. Uses **nearest swing-high resistance** from last 50 days (primary)
2. Falls back to **52-week high** if no swing resistance above price
3. Falls back to **LTP + 1.5%** only if price is already above all resistance levels

**Best time to run:** 11:15 AM, 11:45 AM, 12:15 PM, 2:00 PM

### Stealth Radar

```bash
nepse stealth                            # Full market broker accumulation scan
nepse stealth --sector bank              # Banks stealth
nepse stealth --sector hydro             # Hydro stealth
nepse stealth --sector microfinance      # Microfinance stealth
```

### Portfolio Management

```bash
nepse status                             # Portfolio overview + open positions
nepse update                             # Check if positions hit target/stop
nepse report                             # Detailed performance report
nepse pending                            # Show pending signals (watchlist)
```

### Data Pipeline

```bash
nepse populate                           # Full 2-year historical data download
nepse populate --symbols NABIL NICA      # Specific symbols only
nepse populate --days 365                # 1 year only
nepse populate --incremental             # Only missing dates (daily update)
nepse populate --status                  # Show DB stats
```

### Intelligence Modules (Direct)

```bash
# Market breadth heatmap
python main.py --heatmap

# Sector rotation analysis
python main.py --sector-rotation

# Order flow for a specific stock
python main.py --order-flow NABIL

# Backtest
python main.py --backtest NABIL --backtest-start 2023-01-01

# Run complete pipeline (fetch + screen + notify)
python main.py             # Production mode (sends Telegram)
python main.py --dry-run   # Test mode (no Telegram)
```

---

## 16. Common Mistakes

### Mistake 1: Ignoring Gate 5 Because the Score is High

**What happens:** Stock scores 78/100, you enter. Gate 5 showed CRITICAL distribution. In 3 days, price drops 15% as the operator exits.  
**Rule:** Gate 5 FAIL = AVOID. Always.

### Mistake 2: Entering on DAILY Timeframe Signal Alone

**What happens:** Daily says BUY but weekly is in downtrend. You buy a temporary bounce in a bear wave.  
**Rule:** Gate 2 must be at least PARTIAL (≥50% TF alignment). Prefer ≥70%.

### Mistake 3: Skipping the Stop-Loss ("I'll Watch It")

**What happens:** Stock drops past your SL. "I'll wait for it to recover." It keeps dropping. Rs. 1L becomes Rs. 60K.  
**Rule:** Stop-loss is placed immediately after order fill. Not later. Now.

### Mistake 4: Using All of the Position Size Shown for a BUY (Not BLIND BUY)

**What happens:** Score shows 62/100 (BUY). You deploy the full Rs. 1.99L shown. Two gates failed. The risk is higher.  
**Rule:** BUY = 50% of shown size. STRONG BUY = 75%. BLIND BUY = 100%.

### Mistake 5: Chasing the Score, Ignoring Entry Status

**What happens:** Score is 85/100 (BLIND BUY) but entry status is WAIT (🔴). You buy anyway at a poor intraday moment — poor fill, gap down next day.  
**Rule:** Entry status matters. ENTRY READY = buy. WAIT = limit order or skip for today.

### Mistake 6: Not Updating macro.json for Months

**What happens:** NRB has tightened rates, CCD is at 80%, inflation at 9%. Your macro.json still says favorable defaults. Gate 6 shows full score instead of warning.  
**Rule:** Update `config/macro.json` every month. Takes 5 minutes from nrb.org.np.

### Mistake 7: Trading the Stealth Radar Without Waiting for Confirmation

**What happens:** Broker score is high but CSS is 0.22 (SELL). You enter. Operators haven't finished accumulating yet and price grinds down another 3 weeks.  
**Rule:** Stealth radar = watchlist. Run `nepse expert SYMBOL` before entry. Minimum CSS ≥ 0.40 or Gate 1 ≥ 8/13.

### Mistake 8: Not Running `nepse populate` Before Backtesting

**What happens:** Backtest shows 0 trades for NABIL. "The system is broken."  
**Rule:** DB is empty by default. Run `nepse populate --symbols NABIL --days 730` first. Takes ~5 seconds per symbol.

### Mistake 9: Holding More Than 5 Positions

**What happens:** 7 open positions. Market drops 8%. Every position is in loss simultaneously. You can't think clearly. You panic-sell at the worst moment.  
**Rule:** Max 5 positions (3 if under Rs. 5L portfolio). Concentration = focus + manageable risk.

### Mistake 10: Running Scans During Market Hours Without Acting Pre-Market

**What happens:** You run a scan at 12:30 PM, see NABIL as BUY, buy at an intraday high, stop-loss hits by 2 PM.  
**Rule:** Run scans pre-market (10:00–10:45 AM). Place orders at open. Mid-session scans = information only, no new entries unless it's a breakout stock with clear momentum.

---

## 17. Performance Tracking

### Why Track

Without a log, you have **stories** not data. You'll remember the winning trades and forget the losers. Tracking builds self-honesty and shows you which gate combinations work best for your portfolio.

### What to Log (per trade)

```
Date entered:
Symbol:
Verdict (BLIND BUY / STRONG BUY / BUY):
Final score (X/100):
Gates passed/partial/failed:
Entry price:
Stop-loss:
Target:
Shares:
Capital deployed:
Risk (Rs.):

--- On Exit ---
Exit price:
Exit date:
Exit reason (target / stop / 15-day / manual):
Profit/Loss (Rs.):
Profit/Loss (%):
R achieved (actual R:R):
Was Gate 5 clear? (Y/N):
Notes on what you learned:
```

### Metrics to Review Monthly

| Metric                    | Target | What to do if below                              |
| ------------------------- | ------ | ------------------------------------------------ |
| Win rate                  | ≥ 55%  | Review which gates failed on losing trades       |
| Profit factor (W/L ratio) | ≥ 1.5  | Let winners run more — check if exiting early    |
| Average R achieved        | ≥ 1.5x | Check if stops are too tight                     |
| Max drawdown              | ≤ 20%  | Reduce position size until win rate improves     |
| Trades taken (monthly)    | 4–12   | Under 4 = too restrictive; Over 12 = overtrading |
| Gate 5 failures traded    | 0      | If > 0: discipline failure. Review the rule.     |

### 60-Day Paper Trading Protocol

Before going live with significant capital, paper trade for 60 days:

```
Week 1-2:  Run the system daily. Log every signal. Don't trade real money.
Week 3-4:  Paper buy every BLIND BUY and STRONG BUY signal.
Week 5-6:  Track paper exits (target, stop, 15-day rule).
Week 7-8:  Calculate your paper win rate.

If paper win rate ≥ 55% and profit factor ≥ 1.5 → Start real trading.
If below those numbers → Review what gate combinations led to losses.
```

---

## Quick Reference Card

```
MORNING (10:00 AM):
  1. nepse expert --scan                    → Get today's candidates
  2. nepse expert SYMBOL                    → Deep check on top candidate
  3. Check entry status: 🟢 READY or 🟡 ZONE → place order at open 11 AM
  4. Check breadth > 60%                    → Normal day. 40-60% = selective. <40% = no entries.

AT OPEN (11:00 AM):
  1. Place buy order at entry price shown
  2. Immediately place stop-loss order      ← DO THIS FIRST
  3. Set price alert at target price
  4. Log the trade

MID-SESSION (12:00 PM — 2 min):
  nepse status                              → Any target/stop hit?

PRE-CLOSE (2:45 PM — 5 min):
  nepse update                              → Auto-check outcomes

EVENING (After 3 PM — 5 min):
  nepse report                              → Performance log
  nepse populate --incremental              → Keep DB fresh

WEEKLY:
  Update config/macro.json with NRB data
  Review sector rotation (identify next week's HOT sector)
  Review open positions against 15-day rule
  Log closed trades in your performance tracker

MONTHLY:
  Calculate win rate, profit factor, max drawdown
  Identify which gate combinations work best for you
  Backtest new sector or strategy ideas before trading them
```

---

## Final Principle

> **The system does not eliminate loss. Nothing does.**  
> **The system ensures every loss is small, every win is meaningful, and every decision was rational.**

The 99% of traders you will beat are not bad people. They are making predictable, emotional decisions with no systematic edge. You now have:

- **Institutional-grade analysis** running in 60 seconds
- **Broker intelligence** that detects smart money before price moves
- **Multi-layer risk gates** that prevent catastrophic entries
- **Position sizing math** that keeps losses recoverable
- **Macro + breadth + rotation context** that most fund managers lack access to easily

The only way to lose with this system long-term is to break the rules — particularly Rule 1 (stop-loss placement), Rule 5 (Gate 5 blocking), and the 2% position sizing cap.

Trust the gates. Follow the math. Track everything.
