# NEPSE AI Trading System — Full Documentation

## How This System Works & How to Beat 99% of Nepali Traders

---

## What Is This System?

This is a **fully automated, institutional-grade stock analysis pipeline** built for NEPSE.

Most Nepali traders rely on:

- Tips from Facebook/TikTok groups
- Broker recommendations (conflict of interest)
- Gut feeling and "rumours"
- Checking one indicator on Mero Share or NepseAlpha manually

**This system does what a team of 5 professional analysts would do — in under 60 seconds — for all 269 stocks.**

---

## The 2-Command Workflow

```bash
# Step 1 — Run the full AI scan on a sector
technical_analysis --sector "Hydro Power" --top 5

# Step 2 — Monitor those picks live during market hours
monitor
```

That's it. Everything else is automated.

---

## What Happens Under the Hood

### Phase 1 — Data Fetch (Concurrent, ~10 seconds)

The scanner fetches **1000 daily OHLCV bars** (~4 years of price history) for ALL
stocks in the sector simultaneously using 12 parallel HTTP connections.

- Source: NepseAlpha API (same data your broker uses)
- Rotates 25 different browser fingerprints per request (avoids rate limiting)
- Handles timeouts, circuit-breached stocks, API failures gracefully

---

### Phase 2 — 13-Point Checklist (The Core Filter)

Every stock is scored against a strict **13-point buy checklist** designed from
the WIDGET_GUIDE professional trading protocol. Each point is a specific,
quantifiable condition — no vague "looks bullish" judgements.

| #   | Check                        | What It Tests                                              |
| --- | ---------------------------- | ---------------------------------------------------------- |
| 1   | **Verdict = BUY/STRONG BUY** | Overall AI verdict from 1D indicators                      |
| 2   | **Trend confirmed**          | UPTREND + ADX > 20 + EMA10 > EMA30                         |
| 3   | **RSI 40–70**                | Not overbought, has room to run                            |
| 4   | **Price above SMA50**        | Medium-term structural bull                                |
| 5   | **MACD Bullish**             | Momentum confirming direction                              |
| 6   | **Multi-TF aligned**         | ≥50% of Biweekly/Weekly/Monthly/Quarterly/Yearly TFs = BUY |
| 7   | **No red flags**             | No Death Cross, no RSI ≥ 80, no Bearish RSI Divergence     |
| 8   | **Volume confirmed**         | Volume ratio ≥ 1.2 (smart money is participating)          |
| 9   | **Entry timing**             | Near support (≤ 8% away) OR confirmed bullish breakout     |
| 10  | **Wyckoff phase**            | Accumulation or Markup (not Distribution or Markdown)      |
| 11  | **No operator distribution** | Operators/brokers are NOT actively dumping                 |
| 12  | **Not chasing 52-week top**  | Not within 5% of 52w high without confirmed breakout       |
| 13  | **R:R ≥ 1.5**                | Reward is at least 1.5× the Risk — NEVER trade below this  |

**Result: Score out of 13.**

- **9–13: Strong candidate (Phase 2 analysis)**
- **7–8: Watchable**
- **< 7: Filtered out**

> 99% of Nepali retail traders skip at least 8 of these 13 checks.

---

### Phase 2b — 3-Timeframe Confluence (The Entry Filter)

The daily score tells you WHAT to buy. The 3-TF confluence tells you WHEN.

```
Daily (1D)  →  Is this stock worth watching at all?
    ↓
Hourly (1H) →  Is it in the right zone? (trend ≠ DOWNTREND, RSI < 65)
    ↓
15-Minute   →  Is this the right moment to enter? (verdict BUY + RSI > 50 +
                above SMA20 + bullish pattern + volume surge)
```

**Entry Status:**

| Status        | Meaning                                     | Action                        |
| ------------- | ------------------------------------------- | ----------------------------- |
| `WAIT`        | Daily looks good but 1H or 15m not ready    | Do Nothing                    |
| `ENTRY ZONE`  | Daily + 1H aligned, waiting for 15m trigger | Get ready                     |
| `ENTRY READY` | ALL 3 timeframes confirmed                  | **Enter at next candle open** |

> This is where most people buy wrong. They see a "good stock" on daily charts but
> buy at exactly the wrong time intraday — at resistance, during a 15m downtrend,
> or when volume is drying up. This system prevents that.

---

### Phase 3 — Expert 4-Pillar Intelligence Layer

On top of pure technical analysis, the **MasterStockScreener** runs a 4-pillar
institutional-grade score for each shortlisted candidate:

| Pillar                             | Weight | What It Checks                                           |
| ---------------------------------- | ------ | -------------------------------------------------------- |
| **Pillar 1: Broker/Smart Money**   | 30%    | Which brokers are accumulating? Buyer dominance %?       |
| **Pillar 2: Unlock/Lock-up Risk**  | 20%    | Are 10–20% of shares about to unlock (promoter/IPO)?     |
| **Pillar 3: Fundamentals**         | 20%    | PE ratio, EPS, ROE, PBV — is it actually a good company? |
| **Pillar 4: Technical + Momentum** | 30%    | Momentum score, operator phase, breakout quality         |

**Hard Reject Rules (auto-disqualify no matter how good the chart looks):**

- `🚨 CRITICAL DISTRIBUTION` — Operators are **actively dumping** shares. Chart may look bullish — it's a trap.
- `⚠️ HIGH MANIPULATION RISK` — Stock shows pattern of artificial price inflation.
- `⚠️ UNLOCK IN <30 days` — Large % of locked shares are about to hit the market. Price pressure incoming.

**Sector-aware strategy:**

- Hydro Power scans → automatically uses **MOMENTUM** strategy (Pillar 4 = 40%, Pillar 3 = 10%)
  - Hydro companies have stable earnings from water — PE/ROE matter less than broker accumulation flow
- All other sectors → **VALUE** strategy (balanced weights)

---

### Phase 4 — Market Regime Kill Switch

Before ANY signal is generated, the system checks the overall NEPSE health:

| Regime  | Condition                | Effect                                             |
| ------- | ------------------------ | -------------------------------------------------- |
| `BULL`  | Index in uptrend         | Normal operation                                   |
| `BEAR`  | Index < EMA50 for weeks  | -15 point penalty on all scores, more conservative |
| `PANIC` | Index dropped ≥ 2% today | **KILL SWITCH — zero signals, no buys**            |

> When PANIC fires, the output says "DO NOT TRADE TODAY." This alone saves most
> traders from catching falling knives after a bad market day.

---

### Phase 5 — Composite Score (The Final Ranking)

Each stock gets a **composite score (0–100)** combining all of the above:

- Checklist score (36 pts max)
- Confidence from indicators (19 pts)
- Trend quality + ADX (10 pts)
- RSI zone quality (8 pts)
- Momentum status (5 pts)
- Wyckoff phase (5 pts)
- R:R ratio (5 pts)
- Volume profile (4 pts)
- OBV trend (3 pts)
- Market structure HH/HL (3 pts)
- Breakout status (3 pts)
- Multi-TF alignment by weight (9 pts — Yearly counts 3×, Biweekly counts 1×)
- Golden Cross / Death Cross bonus/penalty
- Bullish candlestick pattern bonus

**Result: Only the top N stocks by composite score are shown per sector.**

---

## The Monitor — Your Real-Time Watchdog

After the scan saves your watchlist, `monitor` tracks all those stocks live:

```bash
monitor          # Full status table (refresh manually during market hours)
monitor --alert  # Show only stocks with actionable changes
```

**What monitor does every time you run it:**

1. Reads `watchlist.json` from the last scan
2. Re-fetches live 1-minute intraday bars for every stock concurrently
3. Re-runs 1H + 15m analysis
4. Compares current entry status vs. status from the scan

**Alert Categories:**

| Alert                | Meaning                                        | Action                               |
| -------------------- | ---------------------------------------------- | ------------------------------------ |
| 🚨 `SL BREACH`       | Live price fell BELOW the calculated Stop Loss | **Exit immediately. No exceptions.** |
| 🟢 `ENTRY READY`     | All 3 TFs just aligned                         | **Enter at next candle open**        |
| 🟡 `STATUS IMPROVED` | WAIT → ENTRY ZONE (getting closer)             | Watch closely                        |
| 🔴 `STATUS DEGRADED` | Setup broke down                               | Don't enter, reassess                |
| ⚪ `NO CHANGE`       | Still watching                                 | Hold position or wait                |

**Market awareness:**

- Detects if NEPSE is open (Nepal Standard Time, UTC+5:45, Sun–Thu 11:00–15:00)
- Shows "MARKET CLOSED" outside hours (intraday data = last session)

---

## Full Command Reference

```bash
# Scan all sectors, top 5 per sector
technical_analysis

# Scan one sector
technical_analysis --sector "Hydro Power"
technical_analysis --sector "Commercial Banks"
technical_analysis --sector "Life Insurance"

# Change number of top picks
technical_analysis --sector "Hydro Power" --top 10

# Skip the expert layer (faster, TA only)
technical_analysis --no-expert

# JSON output (for programmatic use)
technical_analysis --json

# Monitor watchlist (full table)
monitor

# Monitor — alerts only (fast glance)
monitor --alert

# Use a different NepseAlpha session key
technical_analysis --fsk YOUR_KEY
monitor --fsk YOUR_KEY
```

---

## How to Read the Output

### Scan Output Example:

```
══════════════════════════════════════════════════════
  🏆 TOP PICKS — Hydro Power
══════════════════════════════════════════════════════

  #1  HPPL    Rs. 312.0   Score: 12/13   R:R: 2.4
      SL: Rs. 291.20  |  Target: Rs. 350.80
      Status: WAIT (1H: DOWNTREND — wait for flip)
      Expert: Master Score 72/100  |  🐻 Bear market (-15 applied)
      Operator Phase: ACCUMULATION  ← Brokers are buying quietly

  #2  SGHC    Rs. 427.0   Score: 11/13   R:R: 2.1
      SL: Rs. 399.40  |  Target: Rs. 482.70
      Status: ENTRY ZONE (1H ready, waiting for 15m trigger)
```

### Key Fields Explained:

| Field                          | Meaning                                              |
| ------------------------------ | ---------------------------------------------------- |
| `Score: 12/13`                 | 12 of 13 checklist conditions met                    |
| `R:R: 2.4`                     | For every Rs. 1 of risk, potential Rs. 2.40 profit   |
| `SL: Rs. 291.20`               | Place stop-loss HERE. If price hits this, exit.      |
| `Target: Rs. 350.80`           | Take partial/full profit near this price             |
| `WAIT`                         | Do not buy yet — conditions not aligned on lower TFs |
| `ENTRY READY`                  | Buy now at next candle open                          |
| `Operator Phase: ACCUMULATION` | Smart money is loading up                            |
| `🚨 CRITICAL DISTRIBUTION`     | **Do not buy** — operators are selling to retail     |

---

## The Trading Workflow (Step by Step)

### Before Market Opens (10:30–11:00 AM NST)

```bash
technical_analysis --sector "Hydro Power" --top 5
```

1. Note which stocks scored ≥ 9/13
2. Note their SL and Target levels — write them down
3. Note which are `ENTRY ZONE` or `ENTRY READY`
4. Check for `hard_reject` warnings — if present, skip that stock

### During Market Hours (11:00–15:00 NST)

```bash
monitor --watch --interval 60
```

This checks every 60 seconds automatically. Only act when you see:

- 🟢 `ENTRY READY` — Buy at the next candle
- 🚨 `SL BREACH` — Exit immediately if you hold it

### Before Market Closes (14:30 NST)

- Re-run `monitor` one final time
- Reassess any ENTRY ZONE stocks — did they trigger?
- Plan your next morning's scan

---

## Discipline System — How to Become Truly Disciplined

Short answer: **your code gives you structure, but your behavior creates discipline.**

Following the code correctly makes you far more disciplined than most traders, but only if you obey it every day without exceptions.

### Does Following This Code Make You Disciplined?

Use this truth table:

| Your Behavior                                                     | Result                                  |
| ----------------------------------------------------------------- | --------------------------------------- |
| You follow entries, exits, position size, and kill-switch exactly | Yes, discipline grows fast              |
| You override SL, chase FOMO, take random trades outside system    | No, discipline collapses                |
| You follow 8 out of 10 rules                                      | Average result, emotional drift returns |
| You follow 10 out of 10 rules for 90+ days                        | Professional-level discipline           |

Discipline is not a feeling. It is repeated rule execution.

---

## Your Non-Negotiable Trading Constitution

Print this section and keep it next to your desk.

1. I only buy if status is `ENTRY READY`.
2. I never buy `WAIT` or `ENTRY ZONE` out of impatience.
3. I place SL immediately after entry.
4. If SL is hit, I exit immediately. No averaging down.
5. I risk max 1-2% capital per trade.
6. I stop trading for the day after 2 SL hits.
7. I never remove or widen SL after entering.
8. I do not trade PANIC regime days.
9. I never trade rumors, tips, or social media calls.
10. I journal every trade before and after execution.

If you break one rule, your system becomes random trading again.

---

## Daily Discipline Routine (Exact)

### A) Pre-Market Routine (15 minutes)

1. Run scan:

```bash
technical_analysis --sector "Hydro Power" --top 5
```

2. Copy each pick into your plan sheet with:

- Symbol
- Entry status
- SL
- Target
- R:R
- hard_reject flag

3. Remove any stock with hard reject warning.

4. Say this before market opens:
   "I will follow system rules, not my emotions."

### B) Live-Market Routine (Automatic + Human)

1. Start monitor once:

```bash
monitor --watch --interval 60
```

2. Only take action on these events:

- 🟢 BUY ALERT (`ENTRY READY`)
- 🚨 SELL ALERT (`SL BREACH`)

3. Ignore noise between alerts.

4. No manual chart hopping when system says no action.

### C) Post-Market Routine (10 minutes)

1. Record every executed trade.
2. Mark rule adherence: pass/fail.
3. If any rule failed, reduce next-day risk by 50%.
4. If rule adherence is 100% for 5 days, keep normal risk.

This is how discipline compounds.

---

## Position Sizing Formula (Discipline in Math)

Let:

- Capital = total account value
- Risk% = 1% to 2%
- Entry = planned buy price
- SL = stop-loss price

Then:

$$
  ext{Risk Amount} = \text{Capital} \times \text{Risk\%}
$$

$$
  ext{Per-Share Risk} = \text{Entry} - \text{SL}
$$

$$
  ext{Quantity} = \frac{\text{Risk Amount}}{\text{Per-Share Risk}}
$$

If this quantity feels "too small," do not increase risk. That feeling is ego, not edge.

---

## Discipline Scorecard (Track Weekly)

Score yourself every week from 0-100:

1. Rule adherence (40 points)
2. SL obedience (20 points)
3. No impulse trades (20 points)
4. Journal completion (10 points)
5. Daily routine completion (10 points)

Interpretation:

- 90-100: Institutional discipline
- 75-89: Good but still leaking edge
- 60-74: Emotional interference is costly
- <60: Stop trading live, switch to paper mode for 1 week

---

## Anti-Emotion Protocol (When Mind Gets Weak)

Use this whenever you feel fear, greed, or FOMO:

1. Pause for 60 seconds.
2. Read current signal status from monitor.
3. Ask: "Is this ENTRY READY by rule, or emotion-ready by mind?"
4. If rule says no, action is no.
5. Return to watch mode.

One minute of pause prevents many bad trades.

---

## Common Discipline Traps (And Fixes)

1. "It will bounce, I will hold below SL."
   Fix: Exit at SL always; re-entry is allowed later, hope is not.

2. "This looks strong, I will enter before ENTRY READY."
   Fix: Pre-entry is banned. Wait for confirmation.

3. "I lost two trades, I must recover now."
   Fix: Daily stop after 2 SL hits.

4. "Others are making fast money in another stock."
   Fix: No trades outside watchlist.

5. "I know this stock personally."
   Fix: Personal bias is not a signal.

---

## The 90-Day Discipline Plan

1. Days 1-30: Focus only on rule adherence, not profit.
2. Days 31-60: Improve execution speed and consistency.
3. Days 61-90: Optimize only after proving consistency.

Target metric:

$$
  ext{Rule Adherence Rate} = \frac{\text{Rule-Compliant Trades}}{\text{Total Trades}} \times 100
$$

Your goal is >= 95% adherence for 90 days.

Profit follows discipline; discipline does not follow profit.

---

## Stop-Loss — The Most Important Rule

**Never skip the Stop-Loss. This is non-negotiable.**

The system calculates SL using:

- ATR (Average True Range) — volatility-adjusted
- Nearest support level
- Current trend direction

If price breaches SL:

1. The monitor shows 🚨 immediately
2. You exit. Always. No "but I think it will go back up."

> 80% of small investors in NEPSE don't use stop-losses.
> They turn 5% losses into 30% losses by holding and hoping.
> This system removes that emotion entirely.

---

## Risk:Reward — Why R:R ≥ 1.5 Matters

Assume you have 10 trades:

- 5 wins, 5 losses (50% win rate — very normal)
- R:R = 1.0 → Break even. Broker fees put you negative.
- R:R = 1.5 → 5 × 1.5 - 5 × 1 = **+2.5 units profit**
- R:R = 2.0 → 5 × 2.0 - 5 × 1 = **+5 units profit**

The system **filters out all trades where R:R < 1.5** at the checklist stage.
This means even on a 50% win rate, you come out ahead over time.

> Most Nepali traders chase stocks with no defined target.
> They take R:R of 0.5 without realising it — trading for tips and hope.

---

## Swing Hold Logic (1-2 Week Holding Plan)

Short answer: yes, you can hold 1-2 weeks after a buy signal, but only while the trade stays valid by rules.

This system is probability-based. It does not guarantee the future. It gives the highest-probability setup at entry and then manages risk as new data comes in.

### Does the Code Analyze the Future?

It analyzes past and current market structure to estimate future probability.

1. It uses trend, momentum, volume, structure, regime, and risk-reward.
2. It does not know tomorrow's news, operator surprises, or macro shocks.
3. Treat every signal as a favorable bet, not certainty.

In trading terms:

$$
\mathrm{Signal} = \mathrm{Edge}, \quad \mathrm{not} \quad \mathrm{Guarantee}
$$

### Exact 1-2 Week Hold Rules After Buy

After you enter on ENTRY READY, hold the trade only if all of these remain true:

1. Price stays above stop-loss.
2. Daily structure is not broken (no clear lower-low breakdown).
3. Regime does not switch to PANIC.
4. No hard reject appears from expert layer (critical distribution, severe manipulation, near unlock dump).

If any of the above breaks, exit without waiting for 1-2 weeks.

### Time-Based Exit Framework

Use this for consistency:

1. Day 0-2: Let the trade breathe unless SL is hit.
2. Day 3-5: If price is flat and status degrades repeatedly, cut weak positions.
3. Day 6-10: Protect gains by tightening SL to recent support.
4. Day 11-14: If target not hit and momentum weakens, scale out or exit.

This gives you a real swing process instead of random holding.

### Profit-Taking Model (Practical)

Use partial exits:

1. At +1R: book 25% profit and reduce emotional pressure.
2. At +2R: book another 25-50%.
3. Hold remainder only while trend and structure remain healthy.

Where:

$$
R = \text{Entry Price} - \text{Stop Loss}
$$

Example:

1. Entry = Rs. 500
2. SL = Rs. 470
3. Then $R = 30$
4. +1R target = Rs. 530
5. +2R target = Rs. 560

### Weekly Re-Validation Checklist (For Held Trades)

Run once per week for open swing positions:

1. Re-run sector scan.
2. Confirm held stock still scores >= 8/13.
3. Confirm no hard reject flag.
4. Confirm R:R to next target still >= 1.2.
5. If 2 or more checks fail, reduce or exit.

### One-Line Decision Rule

Hold by signal quality, not by calendar.

If signal quality stays strong, a 1-2 week hold is valid.
If signal quality degrades, exit early and protect capital.

---

## What Makes This Better Than What 99% of Traders Use

| What Most Traders Do              | What This System Does                               |
| --------------------------------- | --------------------------------------------------- |
| Check one indicator (RSI or MACD) | 13-point checklist, 30+ indicators                  |
| One timeframe only                | 3-timeframe confluence (1D → 1H → 15m)              |
| Manually check 5–10 stocks        | Auto-scans all 269 NEPSE stocks                     |
| No stop-loss                      | ATR + support-based calculated SL every time        |
| Buy on tips/rumours               | Verified by broker accumulation data (Pillar 1)     |
| No R:R calculation                | R:R ≥ 1.5 required before any signal                |
| Can't detect operator dumping     | Hard-reject: CRITICAL DISTRIBUTION kills the signal |
| No unlock awareness               | Unlock risk in next 30 days = automatic reject      |
| Trade during PANIC days           | Kill switch: PANIC mode = zero signals              |
| Buy at wrong intraday time        | 1H + 15m trigger required before entry              |
| Manual checking                   | `monitor` alerts you the moment conditions change   |

---

## Limitations & Honest Caveats

1. **This is a tool, not a guarantee.** No system is 100% accurate. Markets can be irrational, especially in NEPSE where politically connected brokers can override all technical signals.

2. **PANIC mode is a hard stop.** On days the index falls ≥ 2%, the system generates no signals. This is correct risk management, not a bug.

3. **Hydro sector has unique risk.** Water licensing, government policy, flood damage — these appear nowhere in OHLCV data. Always check news.

4. **Intraday data (1-min bars) covers ~4 trading days only.** This is an API limitation from NepseAlpha. Sufficient for 1H + 15m analysis but not for longer intraday studies.

5. **Bear market penalty is advisory.** The -15 point penalty and Bear regime flag tell you to be more selective, not to stop trading entirely. High-scoring stocks in Bear can still be worth watching.

---

## Quick Reference Card

```
BEFORE BUYING — all 3 must be true:
  ✅ Daily score ≥ 9/13
  ✅ Entry Status = ENTRY READY  (not WAIT, not ENTRY ZONE)
  ✅ No hard_reject warning

POSITION SIZING:
  Risk per trade = 1–2% of your total capital
  Position size = Risk amount ÷ (Entry price − SL price)

AFTER BUYING:
  Set stop-loss order immediately
  Set a price alert at the Target level
  Run `monitor --watch --interval 60` during market hours

TO EXIT:
  Target hit → Take profit (at least partial)
  SL hit → Exit all, no questions
  🚨 alert → Exit immediately
```

---

_Built for the NEPSE AI Trading System. Documentation version: March 2026._
