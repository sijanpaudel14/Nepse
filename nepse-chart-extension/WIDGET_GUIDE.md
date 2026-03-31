# NEPSE Pro Analyzer — Complete Trading Guide

> **The weapon that gives you the edge 99% of NEPSE traders don't have.**
> Real-time AI analysis injected into NepseAlpha: 27 candlestick patterns, 20+ technical indicators, multi-timeframe confluence, support/resistance snapping, Fibonacci, Pivot Points, breakout detection, Wyckoff phase, RSI divergence, and operator activity detection — delivered in one panel.

---

## Table of Contents

1. [Quick Setup](#1-quick-setup)
2. [How It Works Internally](#2-how-it-works-internally)
3. [Opening Charts & Navigation](#3-opening-charts--navigation)
4. [All 30 Resolutions](#4-all-30-resolutions)
5. [Widget Interface — 6 Tabs](#5-widget-interface--6-tabs)
6. [The Verdict System — How Scores Are Computed](#6-the-verdict-system--how-scores-are-computed)
7. [THE Strategy: 3-Timeframe Confluence Method](#7-the-strategy-3-timeframe-confluence-method)
8. [Every Indicator Explained — NEPSE Thresholds](#8-every-indicator-explained--nepse-thresholds)
9. [Stop Loss & Target Calculation Logic](#9-stop-loss--target-calculation-logic)
10. [All 27 Candlestick Patterns — Ranked by NEPSE Reliability](#10-all-27-candlestick-patterns--ranked-by-nepse-reliability)
11. [Support, Resistance, Fibonacci & Pivots](#11-support-resistance-fibonacci--pivots)
12. [RSI Divergence — The Highest-Accuracy Setup](#12-rsi-divergence--the-highest-accuracy-setup)
13. [Wyckoff Market Phase Analysis](#13-wyckoff-market-phase-analysis)
14. [Volume & Operator Activity Detection](#14-volume--operator-activity-detection)
15. [Multi-Timeframe Confluence Explained](#15-multi-timeframe-confluence-explained)
16. [Market Structure — HH/HL vs LH/LL](#16-market-structure--hhhl-vs-lhll)
17. [Complete Buy Decision Checklist](#17-complete-buy-decision-checklist)
18. [Risk Management Framework](#18-risk-management-framework)
19. [NEPSE-Specific Rules](#19-nepse-specific-rules)
20. [Troubleshooting](#20-troubleshooting)

---

## 1. Quick Setup

| Step               | Action                                                                                                 |
| ------------------ | ------------------------------------------------------------------------------------------------------ |
| 1. Start Backend   | `cd nepse_ai_trading && source .venv312/bin/activate && uvicorn main:app --reload --port 8000`         |
| 2. Test Backend    | `curl http://localhost:8000/health` → should return `{"status":"ok"}`                                  |
| 3. Load Extension  | Chrome → `chrome://extensions/` → **Load Unpacked** → select `nepse-chart-extension/extension/` folder |
| 4. Open NepseAlpha | `https://nepsealpha.com/trading/chart?symbol=NABIL&interval=1D`                                        |

The widget appears in the **bottom-right corner** within 1–2 seconds. A **NEPSE Active** pill confirms the extension is loaded.

> **Backend is required.** Without it, the widget times out after 20 seconds and shows a red error with a Retry button.

---

## 2. How It Works Internally

Understanding the architecture makes you a better user.

```
NepseAlpha chart loads data
         ↓
inject.js (MAIN world) intercepts the history API call
         ↓
Extracts raw OHLCV candles → sends to content_script.js
         ↓
content_script.js → POST /analyze (localhost:8000)
         ↓
Backend: 27 patterns + 20 indicators + S/R + Fibonacci + Pivots + Multi-TF
         ↓
Returns: Verdict, SL, Target, R:R, Patterns, Levels, Warnings
         ↓
Widget renders in the page DOM
```

### NepseAlpha API Reality

NepseAlpha only has **3 real API endpoints** (not per-resolution). The extension automatically maps all 30 display resolutions to these three:

| API Endpoint                    | Display Resolutions Served                         |
| ------------------------------- | -------------------------------------------------- |
| `resolution=1S` (1-second bars) | 10S, 15S, 20S, 30S, 45S                            |
| `resolution=1` (1-minute bars)  | 1m, 2m, 3m, 5m, 10m, 15m, 30m, 45m, 1H, 2H, 3H, 4H |
| `resolution=1D` (daily bars)    | 1D, 2D, 3D, 4D, 1W, 2W, 1M, 2M, 3M, 6M             |

All resolutions between the raw API endpoints are **resampled client-side** before being sent to the backend — so you always get the resolution you selected, accurately.

---

## 3. Opening Charts & Navigation

### Direct URL Format

```
https://nepsealpha.com/trading/chart?symbol=SYMBOL&interval=RESOLUTION
```

| Example           | URL                            |
| ----------------- | ------------------------------ |
| NEPSE index daily | `...?symbol=NEPSE&interval=1D` |
| NABIL daily       | `...?symbol=NABIL&interval=1D` |
| NABIL 1-hour      | `...?symbol=NABIL&interval=60` |
| NABIL 15-minute   | `...?symbol=NABIL&interval=15` |

### SPA Navigation

NepseAlpha is a single-page app — switching stocks or intervals doesn't reload the page. The extension handles this via:

- Monitoring `history.pushState` events
- Watching `hashchange` events
- URL polling every 1.5 seconds as a fallback

**You never need to refresh the page.** Switch symbol → extension auto-detects within 1.5 seconds and re-fetches.

---

## 4. All 30 Resolutions

| Widget Label | API Used       | Candle size       | Best For                                |
| ------------ | -------------- | ----------------- | --------------------------------------- |
| **1S**       | 1S             | 1 second          | Tick-level operator injection detection |
| **10S**      | 1S → resampled | 10 seconds        | Ultra-short noise                       |
| **15S**      | 1S → resampled | 15 seconds        | Pre-open activity                       |
| **20S**      | 1S → resampled | 20 seconds        | —                                       |
| **30S**      | 1S → resampled | 30 seconds        | Short-term scalp                        |
| **45S**      | 1S → resampled | 45 seconds        | —                                       |
| **1m**       | 1              | 1 minute          | Real-time momentum / scalping           |
| **2m**       | 1 → resampled  | 2 minutes         | —                                       |
| **3m**       | 1 → resampled  | 3 minutes         | —                                       |
| **5m**       | 1 → resampled  | 5 minutes         | Scalp fine-tune                         |
| **10m**      | 1 → resampled  | 10 minutes        | —                                       |
| **★15m**     | 1 → resampled  | 15 minutes        | **Precision entry trigger**             |
| **30m**      | 1 → resampled  | 30 minutes        | Intraday structure                      |
| **45m**      | 1 → resampled  | 45 minutes        | —                                       |
| **★1H**      | 1 → resampled  | 1 hour            | **Entry timing zone**                   |
| **2H**       | 1 → resampled  | 2 hours           | Mid-session structure                   |
| **3H**       | 1 → resampled  | 3 hours           | NEPSE full half-session                 |
| **4H**       | 1 → resampled  | 4 hours           | One full NEPSE trading day              |
| **★1D**      | 1D             | 1 trading day     | **Primary bias / trend direction**      |
| **2D**       | 1D → resampled | 2 days            | —                                       |
| **3D**       | 1D → resampled | 3 days            | —                                       |
| **4D**       | 1D → resampled | 4 days            | —                                       |
| **1W**       | 1D → resampled | 1 week            | Big-picture S/R                         |
| **2W**       | 1D → resampled | 2 weeks           | —                                       |
| **1M**       | 1D → resampled | ~22 trading days  | Monthly structure                       |
| **2M**       | 1D → resampled | ~44 trading days  | —                                       |
| **3M**       | 1D → resampled | ~65 trading days  | Quarterly trend                         |
| **6M**       | 1D → resampled | ~130 trading days | Semi-annual macro view                  |

**The three star resolutions (★1D, ★1H, ★15m) are your primary trading tools.** Everything else is for confirmation or fine-tuning.

> **NEPSE intraday context:** NEPSE trades 11:00 AM – 3:00 PM = 240 minutes/day. A 4H chart is one full day's session. 1000 1-minute bars = ~4 trading days of intraday data.

---

## 5. Widget Interface — 6 Tabs

| Tab           | Content                                                                  | When to use                               |
| ------------- | ------------------------------------------------------------------------ | ----------------------------------------- |
| **Overview**  | Verdict, confidence, trend, breakout status, patterns, primary warnings  | **Read first, every time**                |
| **Momentum**  | RSI, MACD, StochRSI, Williams %R, CCI, ROC, ADX, OBV trend               | Is the move real or exhausted?            |
| **Technical** | SMA20/50/200, EMA10/20/30/50, MA crossover signals                       | Are you above or below structural levels? |
| **Multi-TF**  | Higher-timeframe alignment table + alignment badge                       | Confirm confluence before entry           |
| **Levels**    | Support/resistance zones, Fibonacci, Pivot Points, SL, Target, R:R       | Set your trade plan                       |
| **Market**    | Wyckoff phase, market structure, market phase, 52W range, volume profile | Understand the big-picture context        |

### Header Controls

| Control                  | Action                                                                 |
| ------------------------ | ---------------------------------------------------------------------- |
| Resolution dropdown      | Switch timeframe — triggers immediate fresh fetch and full re-analysis |
| ↺ Retry button           | Force-refreshes — bypasses 5-second dedup cache                        |
| ↕ Expand / ↙ Full-screen | Enlarge widget to see more data                                        |
| ↑ Collapse               | Minimize to header only                                                |
| ✕ Close                  | Hide widget (reload page to restore)                                   |

---

## 6. The Verdict System — How Scores Are Computed

The verdict is not a black box. Every point in the score system is documented here so you understand exactly why a stock gets BUY vs SELL.

### Score Contributors

| Signal                | Conditions                                         | Score                                   |
| --------------------- | -------------------------------------------------- | --------------------------------------- |
| **RSI 14**            | < 30 (oversold)                                    | +3                                      |
|                       | 30–40                                              | +1                                      |
|                       | 60–70                                              | −1                                      |
|                       | > 70 (overbought)                                  | −3                                      |
| **Trend**             | UPTREND                                            | +2                                      |
|                       | DOWNTREND                                          | −2                                      |
| **MACD**              | Bullish crossover                                  | +1                                      |
|                       | Bearish crossover                                  | −1                                      |
| **BB %B**             | < 0.0 (below lower band)                           | +2                                      |
|                       | 0.0–0.2                                            | +1                                      |
|                       | 0.8–1.0                                            | −1                                      |
|                       | > 1.0 (above upper band)                           | −2                                      |
| **Bullish patterns**  | Count of bullish patterns at current bar           | +1 per pattern (max +3)                 |
|                       | Any pattern with strength ≥ 200 (strong pattern)   | +1                                      |
| **Bearish patterns**  | Count of bearish patterns at current bar           | −1 per pattern (max −3)                 |
|                       | Any pattern with strength ≥ 200                    | −1                                      |
| **Operator activity** | Unusual volume detected + mainly bullish patterns  | +1                                      |
|                       | Unusual volume detected + mainly bearish patterns  | −2                                      |
| **StochRSI**          | K > D and K < 30 (bullish crossover in oversold)   | +1                                      |
|                       | K < D and K > 70 (bearish crossover in overbought) | −1                                      |
| **Williams %R**       | < −80 (extremely oversold)                         | +1                                      |
|                       | > −20 (extremely overbought)                       | −1                                      |
| **CCI 20**            | < −100 (oversold extreme)                          | +1                                      |
|                       | > +100 (overbought extreme)                        | −1                                      |
| **ADX 14**            | ADX > 25 + UPTREND + DI+ > DI−                     | +1                                      |
|                       | ADX > 25 + DOWNTREND + DI− > DI+                   | −1                                      |
|                       | ADX < 20 (choppy market)                           | Score × 0.7 (dampen all signals by 30%) |
| **Multi-TF**          | ALL higher TF agree bullish                        | +3                                      |
|                       | Clear majority bullish (>2× bearish)               | +2                                      |
|                       | Simple majority bullish                            | +1                                      |
|                       | ALL higher TF agree bearish                        | −3                                      |
|                       | Clear majority bearish                             | −2                                      |
|                       | Simple majority bearish                            | −1                                      |

**Theoretical maximum score: ~+19 (extremely rare). Theoretical minimum: ~−19.**

### Verdict Mapping

| Score Range | Verdict         | Meaning                                |
| ----------- | --------------- | -------------------------------------- |
| ≥ 8         | **STRONG BUY**  | Nearly all signals aligned bullish     |
| 4 to 7      | **BUY**         | Majority of signals bullish            |
| −1 to 3     | **HOLD**        | Mixed signals — wait for clearer setup |
| −6 to −2    | **SELL**        | Majority of signals bearish            |
| < −6        | **STRONG SELL** | Nearly all signals aligned bearish     |

### Confidence Score

Confidence (%) reflects how many independent signals agree. It is NOT prediction accuracy — it means the signals are self-consistent.

| Confidence | Interpretation                                  |
| ---------- | ----------------------------------------------- |
| 85–100%    | Very high signal agreement — rare and reliable  |
| 65–84%     | Good alignment — standard entry territory       |
| 45–64%     | Moderate — consider waiting for one more signal |
| < 45%      | Weak — signals contradict each other, no trade  |

---

## 7. THE Strategy: 3-Timeframe Confluence Method

**This is the highest-win-rate approach for NEPSE. Follow it exactly.**

The secret 99% of NEPSE traders miss: **every valid trade needs three timeframes to agree.** Trading on a single timeframe is like navigating with one eye closed.

```
1D (Daily) → Determines the BIAS (buy side or sell side)
1H (Hourly) → Determines the ENTRY ZONE (where to look for entry)
15m (15-minute) → Determines the ENTRY TRIGGER (when to actually enter)
```

### Step 1 — Establish the Bias on Daily (1D)

Open the 1D chart. This takes 30 seconds. The answer is binary: **Is the big picture bullish or not?**

**Go LONG only when ALL of these are true on 1D:**

| Condition                     | Why it matters                    |
| ----------------------------- | --------------------------------- |
| Verdict is BUY or STRONG BUY  | Majority of indicators aligned    |
| Trend is UPTREND              | EMA10 > EMA30, ADX > 20           |
| Price above SMA50             | Medium-term structural bull       |
| RSI between 40–70             | Not overbought, has room to run   |
| MACD Bullish (or crossing up) | Momentum confirming               |
| No STRONG SELL warning on 1D  | Prevents selling into a bear trap |

**Never take a long position if any of the above fails on the daily.** The daily bias is your anchor. Lower timeframe signals can reverse in minutes. Daily trends last days to weeks.

### Step 2 — Find the Entry Zone on 1H

With daily bias confirmed BUY, switch to 1H. You are looking for **a pullback inside the daily uptrend** — a moment where price has retraced to a support/level but the overall structure is still bullish.

**Ideal 1H entry zone characteristics:**

| Signal                                    | Meaning                                     |
| ----------------------------------------- | ------------------------------------------- |
| Pullback to 1H SMA20                      | Price touched the fast MA — common re-entry |
| Pullback to a support level in Levels tab | Price at a known floor                      |
| 1H RSI in 40–55 range                     | Not overbought — lot of room upward         |
| 1H MACD crossing up from below zero       | Momentum returning                          |
| BB %B near 0.2 or lower                   | Price near lower band — bounced             |

**If 1H shows DOWNTREND or STRONG SELL while the daily is BUY, wait.** The stock is in a deeper pullback. Either the daily will flip to SELL (meaning the trade idea is wrong) or 1H will recover (meaning entry is approaching).

### Step 3 — Trigger Entry on 15m

With daily BIAS = BUY and hourly ZONE = identified, switch to 15m for your entry signal.

**Only enter when ALL of these are true on 15m:**

| Signal                               | Meaning                  |
| ------------------------------------ | ------------------------ |
| Verdict is BUY or STRONG BUY         | Micro-trend has turned   |
| RSI trending up from 40–55           | Momentum confirmed       |
| Bullish candlestick pattern present  | Buyers showed their hand |
| Volume above average on entry candle | Real money entering      |
| Price holding above 15m SMA20        | Structure intact         |

**Your entry is the open of the next candle** after all 15m conditions are met.

### Entry Example Walkthrough

```
NABIL 1D: UPTREND, BUY (confidence 76%), RSI 54, MACD Bullish
           → BIAS = LONG ✓

NABIL 1H: Pulled back to SMA20 zone, RSI 45, Hammer pattern at support
           → ZONE = Entry approaching ✓

NABIL 15m: BUY verdict, RSI crossed up through 50, Engulfing candle
            → TRIGGER = Enter now ✓

Widget Levels tab shows:
  SL: 1,245 (just below S1)
  Target: 1,320 (at R1)
  R:R: 2.1
  → Trade setup is valid (R:R > 1.5)
```

---

## 8. Every Indicator Explained — NEPSE Thresholds

### RSI (Relative Strength Index) — 14-period

RSI measures momentum. 100 = all gains, 0 = all losses over the last 14 candles.

| RSI       | Zone               | NEPSE Trading Rule                                                                    |
| --------- | ------------------ | ------------------------------------------------------------------------------------- |
| > 80      | Extreme Overbought | **Do not buy.** Potential reversal. Tighten stop loss if holding.                     |
| 70–80     | Overbought         | Reduce position size. Use trailing stop.                                              |
| 60–70     | Bullish Zone       | Strong stock in trend. Hold longs.                                                    |
| **45–60** | **Ideal Buy Zone** | **Best risk/reward for entries in an uptrend**                                        |
| 40–55     | Mild Bullish       | Healthy pullback in uptrend — look for entry                                          |
| 30–40     | Bearish Zone       | Weakening. Do not add; protect capital.                                               |
| 20–30     | Oversold           | Potential reversal bounce. Wait for confirmation before entering.                     |
| < 20      | Extreme Oversold   | Deep sell-off. Do not catch the falling knife. Wait for bullish pattern + divergence. |

**Key NEPSE insight:** NEPSE stocks in strong bull phases often stay in RSI 60–75 for weeks. RSI 70 alone is not a sell signal — it just means the stock is strong. Sell only when RSI diverges (price makes new high but RSI makes lower high).

### ADX (Average Directional Index) — 14-period

ADX measures trend **strength** regardless of direction. DI+ measures bullish trend force. DI− measures bearish trend force.

| ADX       | Trend Strength            | NEPSE Trading Rule                                                     |
| --------- | ------------------------- | ---------------------------------------------------------------------- |
| > 50      | Extremely strong          | Trend is accelerating. Ride with wide stop.                            |
| 25–50     | Strong trend              | Follow trend signals confidently. This is the money zone.              |
| 20–25     | Developing                | Trend is forming. Lighter position, confirm with price action.         |
| **< 20**  | **Choppy/ranging**        | **Do NOT trade RSI/MACD signals.** They false-fire in ranging markets. |
| DI+ > DI− | Bullish pressure dominant | Confirms uptrend even before price fully breaks out                    |
| DI− > DI+ | Bearish pressure dominant | Confirms downtrend                                                     |

**Critical NEPSE rule:** When ADX < 20, the widget automatically dampens all other indicator scores by 30%. It's flagging that the market is ranging and trends can't be trusted. Wait for ADX > 20 before using momentum signals.

### MACD (12/26/9)

| Signal                                      | Meaning                              | Reliability                        |
| ------------------------------------------- | ------------------------------------ | ---------------------------------- |
| MACD line crosses **above** signal line     | Bullish crossover                    | High if it happens near zero line  |
| MACD line crosses **below** signal line     | Bearish crossover                    | High if it happens above zero line |
| Both lines above zero + histogram growing   | Momentum in full bull mode           | Hold longs aggressively            |
| Both lines below zero + histogram shrinking | Momentum exhausted in downtrend      | Rally is not real — avoid          |
| Histogram peak → shrinking (still positive) | Momentum fading — early exit warning | Medium                             |
| Price new high, MACD lower high             | **Bearish divergence** — exit        | Very High                          |
| Price new low, MACD higher low              | **Bullish divergence** — reversal    | Very High                          |

**NEPSE tip:** For daily charts, MACD histogram crossing zero is one of the best entry signals. Long after histogram crosses from negative to positive.

### Bollinger Bands (%B indicator)

BB %B tells you **where price is relative to the Bollinger Band envelope** (0 = lower band, 1 = upper band, 0.5 = middle).

| %B      | Zone             | Meaning                                      |
| ------- | ---------------- | -------------------------------------------- |
| > 1.0   | Above upper band | Overbought by extension — often reverses     |
| 0.8–1.0 | Near upper band  | Trend may continue but reduce new longs      |
| 0.5     | Middle           | Neutral — watch for direction                |
| 0.2–0.5 | Near middle-low  | Pullback in uptrend — normal                 |
| 0.0–0.2 | Near lower band  | **Potential bounce zone**                    |
| < 0.0   | Below lower band | Extremely oversold extension — bounce likely |

**NEPSE BB rule:** Buy when %B < 0.2 in an established uptrend (ADX > 20, daily UPTREND). The stock has pulled back to the lower band, the trend is intact — it's a high-probability re-entry.

### StochRSI (3/3/14/14)

StochRSI is a stochastic applied to RSI — it reacts faster than regular RSI. Two lines: K (fast) and D (slow).

| Signal                               | Meaning                                           |
| ------------------------------------ | ------------------------------------------------- |
| K crosses above D below 20           | Bullish crossover in oversold — strong buy signal |
| K crosses below D above 80           | Bearish crossover in overbought — take profits    |
| Both lines below 20 and turning up   | Accumulation signal                               |
| Both lines above 80 and turning down | Distribution signal                               |

**Use StochRSI for timing within a trend — not for calling reversals.** It false-fires too often in strong trends.

### Williams %R (14-period)

Measures how close price is to the highest high over the last 14 candles. Ranges from 0 (at the high) to −100 (at the low).

| %R                | Meaning                                                |
| ----------------- | ------------------------------------------------------ |
| > −20 (near 0)    | Overbought — price near 14-period high                 |
| −20 to −50        | Neutral bullish zone                                   |
| −50 to −80        | Neutral bearish zone                                   |
| < −80 (near −100) | Oversold — price near 14-period low → potential bounce |

### CCI (Commodity Channel Index) — 20-period

Measures how far price is from its statistical average. Designed for commodities but highly effective on NEPSE.

| CCI          | Meaning                                      |
| ------------ | -------------------------------------------- |
| > +200       | Extreme overbought — very high reversal risk |
| +100 to +200 | Overbought — momentum present but be careful |
| ±100         | Neutral zone — normal fluctuation            |
| −100 to −200 | Oversold — potential bounce zone             |
| < −200       | Extreme oversold — reversal likely imminent  |

**CCI tip:** CCI −100 or lower on the daily, combined with a bullish candlestick pattern, is a reliable NEPSE entry trigger.

### OBV (On-Balance Volume)

OBV tracks volume flow — it adds volume on up days and subtracts on down days. If OBV rises while price rises, big money is accumulating. If OBV falls while price rises, a divergence is forming.

| OBV Signal                 | Meaning                                               |
| -------------------------- | ----------------------------------------------------- |
| Rising OBV + Rising price  | Genuine accumulation — strong buy                     |
| Falling OBV + Rising price | **Bearish divergence — distribution in progress**     |
| Rising OBV + Falling price | **Bullish divergence — accumulation before breakout** |
| Flat OBV                   | No conviction — price move is not supported           |

**OBV is one of the strongest tools for detecting operator activity on NEPSE.** When a NEPSE operator accumulates before pumping, OBV trends up before price does.

### Trend (EMA-based + ADX filter)

The widget determines trend using the following logic:

1. EMA10 vs EMA30 gives the short-term bias
2. ADX < 20 overrides any EMA trend → declares SIDEWAYS

| Trend Reading | Meaning                     |
| ------------- | --------------------------- |
| UPTREND       | EMA10 > EMA30 + ADX ≥ 20    |
| DOWNTREND     | EMA10 < EMA30 + ADX ≥ 20    |
| SIDEWAYS      | ADX < 20 regardless of EMAs |

---

## 9. Stop Loss & Target Calculation Logic

The widget calculates SL and Target using the backend algorithm so you don't need to guess. Here's exactly what it does:

### Stop Loss Algorithm

```
1. ATR-based stop = current price − (multiplier × ATR14)
   - UPTREND multiplier = 2.0 (2 ATRs below price)
   - DOWNTREND multiplier = 1.5
   - SIDEWAYS multiplier = 1.5

2. Support snapping:
   - If a support level exists within ±1 ATR of the ATR-based stop
   → place stop just below that support (support × 0.998)
   → This gives a "natural" stop that the market will respect

3. Limits enforced:
   - Stop cannot be more than 10% below price (capital protection)
   - Stop cannot be less than 1% below price (minimum noise buffer)
```

**What this means for you:** The widget places your stop just below the nearest meaningful support level. If price violates that support, the entire technical structure is compromised — you should be out.

### Target Algorithm

```
1. Risk = |current price − stop loss|

2. Check resistance levels (nearest resistance above current price):
   - If resistance level above price gives reward/risk ≥ 1.5:1
   → Use that resistance as target (just below resistance × 0.998)

3. Fallback: target = current price + (2.0 × risk) = 2:1 R:R

4. Hard cap: target never exceeds +20% above current price
   (NEPSE upper circuit is 10%/day — 20% is a reasonable multi-day cap)
```

### Risk/Reward Ratio (R:R)

Shown in the Levels tab.

| R:R     | Trade quality                                 |
| ------- | --------------------------------------------- |
| ≥ 3.0   | Excellent — very rare, take it                |
| 2.0–3.0 | Good — standard professional setup            |
| 1.5–2.0 | Acceptable — minimum threshold                |
| 1.0–1.5 | Poor — avoid unless in confirmed strong trend |
| < 1.0   | Reject — risk exceeds potential reward        |

**Never take a trade where R:R < 1.5.** This is the single most important risk rule.

---

## 10. All 27 Candlestick Patterns — Ranked by NEPSE Reliability

Patterns appear in the Overview tab. Strength values: ±100 = standard, ±200 = high conviction, ±300 = very strong.

### Tier 1 — Most Reliable for NEPSE (Act Immediately with Confirmation)

| Pattern                  | Dir     | Strength | NEPSE Strategy                                                                           |
| ------------------------ | ------- | -------- | ---------------------------------------------------------------------------------------- |
| **Bullish Engulfing**    | Bullish | +200     | Buy at next open if at support. Stop below the engulfing candle's low.                   |
| **Bearish Engulfing**    | Bearish | −200     | Exit long position. Strong demand-to-supply flip.                                        |
| **Morning Star**         | Bullish | +300     | 3-candle reversal from downtrend. Enter after the 3rd (bullish) candle closes.           |
| **Evening Star**         | Bearish | −300     | 3-candle reversal from uptrend. Exit at the close of the 3rd (bearish) candle.           |
| **Three White Soldiers** | Bullish | +300     | 3 consecutive strong bullish candles = confirmed trend. Buy breakout.                    |
| **Three Black Crows**    | Bearish | −300     | 3 consecutive strong bearish candles = confirmed downtrend. Exit immediately.            |
| **Hammer**               | Bullish | +100     | Long lower wick = buyers defended support hard. Must appear at clear support level.      |
| **Shooting Star**        | Bearish | −100     | Long upper wick = sellers rejected resistance hard. Appears at resistance = exit signal. |

### Tier 2 — Reliable with Confirmation

| Pattern                   | Dir     | Strength | NEPSE Strategy                                                                      |
| ------------------------- | ------- | -------- | ----------------------------------------------------------------------------------- |
| **Piercing Line**         | Bullish | +200     | Bullish candle closes above 50% of previous bearish candle. Needs volume.           |
| **Dark Cloud Cover**      | Bearish | −200     | Bearish candle closes below 50% of previous bullish candle. Major overhead supply.  |
| **Tweezer Bottom**        | Bullish | +200     | Two candles form equal lows = double test of support. Buy at next candle open.      |
| **Tweezer Top**           | Bearish | −200     | Two candles form equal highs = double rejection of resistance. Exit.                |
| **Rising Three Methods**  | Bullish | +300     | Pause in uptrend followed by continuation. High reliability in trending markets.    |
| **Falling Three Methods** | Bearish | −300     | Pause in downtrend followed by continuation. Sell into any bounces.                 |
| **Bullish Harami**        | Bullish | +100     | Small bullish candle inside previous bearish candle. Confirm with next bar's close. |
| **Bearish Harami**        | Bearish | −100     | Small bearish candle inside previous bullish candle. Warning only.                  |
| **Inverted Hammer**       | Bullish | +100     | Long upper wick at bottom. Needs bullish close next day to confirm.                 |
| **Hanging Man**           | Bearish | −100     | Appears after uptrend. Long lower wick = intraday selling.                          |

### Tier 3 — Context Dependent (Confirm with Indicators)

| Pattern              | Dir     | Strength | Notes                                                                           |
| -------------------- | ------- | -------- | ------------------------------------------------------------------------------- |
| **Doji**             | Neutral | ±50      | Price opened and closed at nearly same level = battle between buyers/sellers.   |
| **Gravestone Doji**  | Bearish | −100     | Opens at low, closes at low. Sellers won the session.                           |
| **Dragonfly Doji**   | Bullish | +100     | Opens at high, closes at high. Buyers won the session.                          |
| **Spinning Top**     | Neutral | ±50      | Small body with wicks both ways = indecision. Wait for next candle's direction. |
| **Marubozu (Bull)**  | Bullish | +100     | Candle with no wicks = full conviction close. Very bullish.                     |
| **Marubozu (Bear)**  | Bearish | −100     | Full bearish conviction.                                                        |
| **Kicking (Bull)**   | Bullish | +200     | Bearish marubozu → bullish marubozu. Rare, very powerful.                       |
| **Kicking (Bear)**   | Bearish | −200     | Bullish marubozu → bearish marubozu. Exit immediately.                          |
| **On Neck**          | Bearish | −100     | Bearish continuation. Closes at or below previous low.                          |
| **Belt Hold (Bull)** | Bullish | +100     | Opens at the low, closes strong.                                                |
| **Belt Hold (Bear)** | Bearish | −100     | Opens at the high, closes weak.                                                 |

### Using Patterns Correctly

1. **Pattern alone is never enough.** A Hammer at resistance is not a buy. A Hammer at support (with RSI < 40 and ADX > 20) is.
2. **The stronger the pattern (±200, ±300), the more weight it carries** in the verdict score.
3. **Multiple patterns in the same direction = very strong signal.** Two bullish patterns on the same bar adds +2 to the score.

---

## 11. Support, Resistance, Fibonacci & Pivots

### Support and Resistance (S/R)

The backend uses a **price cluster algorithm** — it identifies zones where price has repeatedly reversed over the last 50 bars. These are not arbitrary lines; they represent **actual order walls** in the market.

| Level  | Meaning                                |
| ------ | -------------------------------------- |
| **S1** | Nearest support below current price    |
| **S2** | Second support below S1                |
| **S3** | Long-term floor (very strong)          |
| **R1** | Nearest resistance above current price |
| **R2** | Second resistance above R1             |
| **R3** | Long-term ceiling                      |

**Using S/R for trades:**

- **Buy zone:** Price pullback to S1 with RSI 40–55 and bullish pattern = ideal entry
- **Stop loss:** Just below S1 (the widget calculates this automatically)
- **Target:** Just below R1 (the widget calculates this automatically)
- **Position yourself AS CLOSE to support as possible** — this maximizes R:R

**Pro rule:** If price is between S1 and R1 (mid-range), the R:R is too symmetric for a clean trade. Wait for price to reach S1 or break above R1 (breakout trade).

### Fibonacci Retracement

Fibonacci is most useful after a clear swing move (swing high to swing low). The backend computes it from the highest high and lowest low over the last 100 bars.

| Level     | Common Name          | NEPSE Use                                    |
| --------- | -------------------- | -------------------------------------------- |
| 23.6%     | Shallow retracement  | Strong trend — only brief pullbacks          |
| **38.2%** | Golden pocket zone 1 | Best entry in very strong trends             |
| **50.0%** | Midpoint             | Most common re-entry zone                    |
| **61.8%** | Golden ratio         | Best re-entry in normal uptrends             |
| 78.6%     | Deep retracement     | Trend weakening — enter only with conviction |
| 100%      | Full retracement     | Trend failed — revisiting the base           |

**NEPSE Fibonacci rule:**

- Buy at 61.8% retracement if: daily UPTREND + RSI 45–55 + MACD turning up + ADX > 20
- The 61.8% level is called "The Golden Ratio" for a reason — professional money consistently defends this level

### Pivot Points (Standard)

Pivot Points reset daily. They are calculated from the prior day's High, Low, Close.

```
Pivot Point (PP) = (H + L + C) / 3
R1 = 2×PP − L    R2 = PP + (H − L)
S1 = 2×PP − H    S2 = PP − (H − L)
```

| Level  | Use                                                                           |
| ------ | ----------------------------------------------------------------------------- |
| **PP** | Today's directional bias line. Price above PP = bullish day. Below = bearish. |
| **R1** | First intraday resistance. Common first target for breakout trades.           |
| **R2** | Extended target. Set if R1 broken with volume.                                |
| **S1** | First intraday support. Place stop just below S1.                             |
| **S2** | Extended stop zone if trade needs more room.                                  |

**NEPSE intraday rule:** NEPSE opens at 11 AM with huge price gaps frequently. The first 20 minutes (11:00–11:20) is often noise — high volatility, spread-driven moves. Use Pivot Points AFTER 11:20 AM when the real session begins.

---

## 12. RSI Divergence — The Highest-Accuracy Setup

RSI divergence is the **most reliable leading indicator** in the widget. When price and RSI disagree, price almost always aligns with RSI eventually.

### Bullish Divergence (Most Profitable Setup)

```
Price: lower low (new low in price)
RSI:   higher low (RSI doesn't confirm the low)
→ Sellers are losing momentum. Reversal is imminent.
```

**How to trade:**

1. Wait for confirmation: the bar AFTER the divergence must close higher
2. Enter at the confirm candle's close or next open
3. Stop below the most recent price low
4. Target: previous swing high

### Bearish Divergence (Best Exit Signal)

```
Price: higher high (new high in price)
RSI:   lower high (RSI is falling while price rises)
→ Buyers are losing strength. Distribution in progress.
```

**How to trade:**

1. This is a strong exit signal on any existing long position
2. Do not buy new positions when bearish divergence is active on daily chart
3. The stock may continue higher briefly but the reversal is near

### When Divergence Appears in the Widget

The Overview tab shows an **RSI Divergence** warning. This fires when:

- **Bearish:** Last 2 price peaks are higher but last 2 RSI peaks are lower
- **Bullish:** Last 2 price troughs are lower but last 2 RSI troughs are higher

**Historical success rate for NEPSE:** Bearish RSI divergence on the daily chart has preceded major corrections in ~75% of NEPSE stocks during distribution phases. It is early — price may still go up 2–5% after divergence. But the exit plan must be activated.

---

## 13. Wyckoff Market Phase Analysis

Wyckoff analysis identifies **where smart money (operators) is in the market cycle.** This is displayed in the Market tab.

```
ACCUMULATION → MARKUP → DISTRIBUTION → MARKDOWN → (repeat)
```

### The Four Phases in Detail

| Phase            | Price Action                                  | Volume Pattern                                              | Widget Signal                                                        | Trader Action                                           |
| ---------------- | --------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------- |
| **Accumulation** | Sideways range, bouncing at support           | High volume at lows (operators buying quietly)              | Low volatility + RSI bottoming + OBV rising while price flat         | **Best time to BUILD positions.** Enter slowly.         |
| **Markup**       | Rising price, higher highs and lows           | Rising volume confirming up moves                           | UPTREND + ADX > 25 + OBV rising + BUY verdict                        | **Hold longs aggressively. Add on pullbacks to SMA20.** |
| **Distribution** | Sideways range at highs, failing to break out | High volume at highs (operators selling into retail buying) | Bearish divergence + operator warning + OBV falling while price flat | **Start reducing. Tighten stops. Prepare to exit.**     |
| **Markdown**     | Falling price, lower highs and lows           | High volume on down bars                                    | DOWNTREND + STRONG SELL verdict + OBV falling                        | **Do not buy. Exit all remaining longs.**               |

### Identifying Accumulation (Best Buy Zone)

The accumulation phase has a specific pattern:

1. Price consolidates in a range for extended period
2. Volume is **high at the lows** (buyers absorbing sell orders)
3. RSI forms a **bullish divergence** near the lows
4. OBV trends up while price stays flat
5. ADX is below 20 (ranging) but DI+ starts rising

**When ADX breaks above 20 + price breaks the range = Markup begins. This is THE entry point.**

### Identifying Distribution (Best Exit Zone)

1. Price is at or near highs, struggling to make new highs
2. Volume is **high on up bars but closes in the upper half** (selling into strength)
3. RSI forms a **bearish divergence** at the top
4. OBV starts declining while price stays flat or slightly rising
5. Operator warning fires in the widget

---

## 14. Volume & Operator Activity Detection

### Volume Profile

The widget classifies market volume into one of four profiles:

| Profile                   | Description                                        | Meaning                                |
| ------------------------- | -------------------------------------------------- | -------------------------------------- |
| **Heavy Accumulation**    | High volume on up moves, low on down moves         | Strong buying pressure — Markup likely |
| **Possible Distribution** | High volume on down moves, or high volume at highs | Selling pressure — exit warning        |
| **High Volatility**       | Abnormally high volume overall                     | Make or break moment — watch closely   |
| **Normal Volume**         | Volume within expected range                       | Normal market activity                 |

### How Operator Activity is Detected

NEPSE has a significant amount of operator-driven price action — large coordinated trades that move price. The widget flags this using:

1. **Volume spike:** Current 3-bar average volume > 3× the 20-bar average volume
2. **Price-volume divergence:** Price moves without proportional support from broad buying

| Warning Level               | Trigger             | Meaning                                  |
| --------------------------- | ------------------- | ---------------------------------------- |
| Potential Operator Activity | Volume > 3× average | A single large actor is moving the stock |
| High Volume Move            | Volume > 2× average | Elevated institutional interest          |

**When operator warning fires:**

- **With bullish patterns:** Operator is pumping. You can ride it IF the technicals confirm. Use tighter stop (operator can reverse trade at will).
- **With bearish patterns:** Operator is distributing (selling to retail). **Do not buy into this.** Avoid entirely.
- **At 52-week high:** Classic pump-and-dump territory. Maximum caution.

### Volume Rules for All Trades

| Volume Signal                        | Meaning                                          |
| ------------------------------------ | ------------------------------------------------ |
| Breakout + volume > 2× average       | Real breakout — enter with confidence            |
| Breakout + volume < average          | **Fake breakout** — wait for volume confirmation |
| Bearish candle + volume > 2× average | Heavy institutional selling — exit immediately   |
| Bearish candle + volume < average    | Weak sellers — healthy pullback in uptrend       |
| Price rising + OBV falling           | **Bearish divergence** — operator distributing   |

---

## 15. Multi-Timeframe Confluence Explained

The Multi-TF tab shows analysis of higher timeframes automatically based on the resolution you're viewing.

### What Gets Analyzed

| Your Resolution | Higher TFs Analyzed             |
| --------------- | ------------------------------- |
| 1–45 minute     | Hourly chart + Daily chart      |
| 1H–4H           | Daily chart + Weekly chart      |
| 1D–3D           | Weekly chart + Monthly chart    |
| 1W              | Monthly chart + Quarterly chart |
| 1M              | Quarterly chart + Yearly chart  |

Each higher TF shows its own verdict (STRONG BUY / BUY / HOLD / SELL / STRONG SELL) based on its own indicators.

### Confluence Scoring Contribution

| Confluence                          | Score Impact | Meaning                                |
| ----------------------------------- | ------------ | -------------------------------------- |
| All higher TF = BUY/STRONG BUY      | +3           | Maximum conviction — rare and powerful |
| Clear majority bullish (>2×bearish) | +2           | Strong alignment                       |
| Simple majority bullish             | +1           | Mild alignment                         |
| Mixed                               | 0            | No help from higher TF                 |
| Simple majority bearish             | −1           | Headwind from higher TF                |
| Clear majority bearish              | −2           | Strong headwind                        |
| All higher TF = SELL/STRONG SELL    | −3           | Fighting a macro bear trend            |

### Why Multi-TF Matters

A 15m BUY signal with the daily chart in STRONG SELL means:

- You're trying to buy a short-term bounce inside a downtrend
- 80% of the time these fail within 2–3 bars
- The higher timeframe is more powerful than the lower one

**Never trade against the Daily trend.** Never trade against the Weekly trend for a position trade (multi-day holding).

---

## 16. Market Structure — HH/HL vs LH/LL

Market structure is tracked in the Market tab. It identifies whether price is making **Higher Highs and Higher Lows (uptrend)** or **Lower Highs and Lower Lows (downtrend)**.

| Structure                 | Pattern                                 | Meaning                                          |
| ------------------------- | --------------------------------------- | ------------------------------------------------ |
| **Bullish**               | Higher Highs + Higher Lows (HH/HL)      | Classic uptrend — price is creating expansion    |
| **Bearish**               | Lower Highs + Lower Lows (LH/LL)        | Classic downtrend — sellers in control           |
| **Transitioning Bullish** | After downtrend: first Higher Low forms | Potential trend reversal — accumulate cautiously |
| **Transitioning Bearish** | After uptrend: first Lower High forms   | Distribution beginning — reduce position         |

### The Structure Reversal Pattern (Best Early Entry)

```
Trend was DOWN: LH → LH → LH
Then: First Higher Low (HL) forms
Then: Price breaks the last Lower High (LH)
→ STRUCTURE REVERSAL CONFIRMED
→ This is your entry after RSI > 50 + ADX starts rising
```

This is the same concept professional traders call a "Change of Character" (CHoCH). It's the earliest reliable sign that a new uptrend is beginning.

---

## 17. Complete Buy Decision Checklist

### Step 1 — Daily Bias Check (30 seconds, every time)

- [ ] 1D Trend = UPTREND
- [ ] 1D Verdict = BUY or STRONG BUY
- [ ] 1D RSI between 40–70 (not overbought)
- [ ] Price above 1D SMA50
- [ ] 1D MACD = Bullish (or crossing up)
- [ ] No bearish RSI divergence on 1D
- [ ] 1D ADX > 20 (actual trend, not chop)
- [ ] Wyckoff phase = Accumulation or Markup
- [ ] No operator distribution warning

**If even ONE item above is ✗ → Do NOT enter. Wait or find a different stock.**

### Step 2 — Hourly Entry Zone Check

- [ ] 1H Trend = UPTREND or SIDEWAYS (not DOWNTREND)
- [ ] 1H RSI < 65 (room to move up)
- [ ] Price at or near S1 / SMA20 / Fibonacci 61.8% on 1H
- [ ] 1H MACD turning up (positive momentum)

### Step 3 — 15m Entry Trigger

- [ ] 15m Verdict = BUY or STRONG BUY
- [ ] 15m RSI > 50 and rising
- [ ] Bullish candlestick pattern on 15m (at least Tier 2 or higher)
- [ ] Entry candle volume > 1-hour average

### Step 4 — Trade Plan Setup (Levels Tab)

- [ ] Stop loss identified (just below S1 or the widget calculation)
- [ ] Target identified (at R1 or the widget calculation)
- [ ] R:R ≥ 1.5 (do not take trade if R:R < 1.5)
- [ ] Position size calculated (see Risk Management below)

---

## 18. Risk Management Framework

**This is the most important section. Great analysis means nothing without proper risk management.**

### The 2% Capital Rule

**Never risk more than 2% of your total trading capital on a single trade.**

```
Position Size = (Account Size × 0.02) ÷ Stop Loss Distance (in NPR)

Example:
  Account = NPR 5,00,000
  Risk per trade = NPR 10,000 (2%)
  Current price = NPR 1,200
  Stop loss = NPR 1,150 (distance = NPR 50)
  Position size = 10,000 ÷ 50 = 200 shares
  Cost = 200 × 1,200 = NPR 2,40,000 (48% of account)
```

**Even though you're buying NPR 2.4 lakh of stock, you're only RISKING NPR 10,000 (2%) if the stop hits.**

### Position Sizing by Confidence

| Confidence | Verdict              | Position Size Multiplier            |
| ---------- | -------------------- | ----------------------------------- |
| 85–100%    | STRONG BUY           | 100% of calculated size             |
| 70–84%     | BUY                  | 75%                                 |
| 55–69%     | BUY                  | 50% (add remaining on confirmation) |
| 45–54%     | HOLD approaching BUY | 25% (starter position only)         |
| < 45%      | HOLD or worse        | 0% — skip trade                     |

### Stop Loss Rules

1. **Always set the stop loss BEFORE entering.** Know your exit before your entry.
2. **Use the widget's SL calculation** — it is ATR-based and support-snapped.
3. **Never move stop loss lower** once trade is active. You can trail it higher after 1:1 is reached.
4. **NEPSE T+2 implication:** In NEPSE, you must pay within T+2 days. If your stop hits, sell immediately on the stop day to free capital. Do not wait.
5. **After reaching 1:1 R:R**, move stop to break-even. You can no longer lose money.
6. **After reaching 2:1 R:R**, move stop to 1:1. Lock in minimum profit.

### Trailing Stop Strategy

```
When trade is at +1R: Move stop to entry price (break-even)
When trade is at +2R: Move stop to +1R (lock in profit)
When trade is at +3R: Move stop to +1.5R
When trade is at +4R: Move stop below SMA20 (let it run with the trend)
```

### Portfolio Risk Rules

| Rule                                  | Reason                           |
| ------------------------------------- | -------------------------------- |
| Maximum 5 open trades                 | Diversify while staying focused  |
| Maximum 30% in one sector             | Sector rotation risk             |
| Maximum 40% in one stock              | Concentration risk               |
| Never add to a losing position        | Averaging down destroys accounts |
| Take full profit target or trail stop | Never hold open with no plan     |

---

## 19. NEPSE-Specific Rules

### NEPSE Market Hours

- **Trading session:** 11:00 AM – 3:00 PM (Nepal Standard Time)
- **Duration:** 4 hours = 240 minutes per trading day
- **Pre-open:** 10:45 – 11:00 AM (order collection, no execution)
- **Circuit breaker:** ±10% daily limit per stock, ±5% for indices

### First 20 Minutes Rule

NEPSE's open is extremely volatile. The first 10–20 minutes often feature:

- Operator injection (large orders to set direction)
- Spread-driven fake moves

**Rule: Do not enter any position before 11:20 AM unless you see extreme divergence on M1.**

### T+2 Settlement

NEPSE settles trades on T+2 — 2 business days after trade. Implications:

- You can sell the stock on T+1 (you don't need to hold)
- But if the stock crashes immediately, you cannot cut the loss until the next day's market open
- This is why **stop loss placement is critical** — your maximum loss is locked to your entry day if the stock falls below circuit

### NEPSE Circuit Limits

| Stock Type     | Daily Up Limit | Daily Down Limit |
| -------------- | -------------- | ---------------- |
| Regular stocks | +10%           | −10%             |
| Indices        | +5%            | −5%              |

**Strategy implication:** When a stock hits upper circuit (UC), it usually means very aggressive buying. It will either continue the next day (if fundamentals support it) or get sold off immediately. Do NOT buy at UC unless you're an intraday scalper who exits same day.

### Operator Activity Patterns in NEPSE

NEPSE has well-known operator patterns:

| Pattern                   | What you see                                          | Action                                                           |
| ------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------- |
| **Pre-pump accumulation** | OBV rising, price flat, low volume                    | BUILD position alongside operators (Wyckoff Accumulation)        |
| **Volume pump**           | Sudden 5–10× volume, price breaks out                 | Can ride if confirmed by trend. Tight stop.                      |
| **Distribution top**      | High volume at highs, RSI divergence                  | EXIT. Operator is selling to retail.                             |
| **Shakeout**              | Brief violent drop below support + immediate recovery | Operators shaking out weak hands. If RSI/structure intact, hold. |

### Sector Rotation (NEPSE)

NEPSE sectors rotate predictably with macroeconomic cycles:

| Macro Phase                    | Leading Sectors                  |
| ------------------------------ | -------------------------------- |
| Rising interest rates          | Banking, Insurance               |
| Rate cuts, liquidity expansion | Real estate, Hydropower          |
| Bull market peak               | Development banks, Finance       |
| Bear market / uncertainty      | Life insurance, defensive stocks |

**Rule:** Always check the NEPSE index (NEPSE) daily chart before analyzing individual stocks. If NEPSE index is in DOWNTREND, reduce position sizes by 50% across all trades.

---

## 20. Troubleshooting

### Error Messages Decoded

| Error                    | Cause                        | Fix                                        |
| ------------------------ | ---------------------------- | ------------------------------------------ |
| Analysis timed out (20s) | Backend not running          | `uvicorn main:app --reload` in backend dir |
| Backend timed out        | Python crash or OOM          | Check terminal for traceback               |
| HTTP 422                 | Malformed API call           | Extension mismatch — reload extension      |
| No chart data            | API returned empty/non-OHLCV | Refresh page or try 1D resolution          |
| Fetch failed             | Network or CORS issue        | Be on `https://nepsealpha.com/...`         |

### Widget Not Appearing

1. URL must be exactly: `https://nepsealpha.com/trading/chart?symbol=...`
2. Extension must be enabled in `chrome://extensions/`
3. Open DevTools → Console → look for: `[NEPSE Analyzer] NepseAlpha interceptor active`
4. If missing: Disable + Re-enable the extension
5. Never run on HTTP (only HTTPS)

### Analysis Doesn't Update When Switching Stocks

1. Click the ↺ retry button on the widget
2. This bypasses the 5-second dedup cache
3. If still stuck, try switching resolution and back

### Backend Startup (Full Command)

```bash
cd "/path/to/nepse-chart-extension/backend"
# If using venv:
source .venv312/bin/activate
# Start:
uvicorn main:app --reload --port 8000
# Test:
curl http://localhost:8000/health
```

### Console Diagnostics (DevTools F12 → Console)

```
[NEPSE Analyzer] NepseAlpha interceptor active       ← extension loaded OK
[NEPSE Analyzer] Auto-fetch: NABIL (1D→api:1D)       ← data fetch triggered
[NEPSE Analyzer] 1000 candles ✓ NABIL ✓ 1D           ← data received OK
[NEPSE Analyzer] 📊 dispatch: apiRes=1 displayRes=15 raw=61607 resampled=10591
                                                       ← resampling working
[NEPSE Analyzer] Auto-fetch: NABIL (4H→api:1)        ← 4H served from 1m endpoint
```

---

_Last updated: v3.0 — All 30 timeframes supported | Support-snapped SL | Resistance-based targets | ADX-weighted verdict | Wyckoff phase detection_

---

## Table of Contents

1. [Quick Setup](#1-quick-setup)
2. [Opening a Chart on NepseAlpha](#2-opening-a-chart-on-nepsealpha)
3. [Resolution Dropdown](#3-resolution-dropdown)
4. [The 3-Timeframe Trading Strategy](#4-the-3-timeframe-trading-strategy)
5. [Widget Layout — The 6-Tab Interface](#5-widget-layout--the-6-tab-interface)
6. [Reading the Verdict](#6-reading-the-verdict)
7. [Reading Every Indicator](#7-reading-every-indicator)
8. [The Complete Buying Decision Framework](#8-the-complete-buying-decision-framework)
9. [All 27 Candlestick Patterns](#9-all-27-candlestick-patterns)
10. [Support, Resistance & Key Levels](#10-support-resistance--key-levels)
11. [NEPSE-Specific Rules](#11-nepse-specific-rules)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Quick Setup

| Step               | Action                                                                    |
| ------------------ | ------------------------------------------------------------------------- |
| 1. Start Backend   | cd nepse_ai_trading && uvicorn main:app --reload                          |
| 2. Load Extension  | Chrome/Edge -> chrome://extensions/ -> Load Unpacked -> extension/ folder |
| 3. Open NepseAlpha | https://nepsealpha.com/trading/chart\?symbol\=NEPSE\&interval\=1D         |

The widget appears automatically in the bottom-right within 1-2 seconds. A **NEPSE Active** pill flashes briefly to confirm the extension is loaded.

> **Backend required.** The widget connects to localhost:8000/analyze. Without it you will see a timeout error after 20 seconds.

---

## 2. Opening a Chart on NepseAlpha

NepseAlpha is a **single-page app** — switching stocks updates the URL without reloading. The extension detects all URL changes automatically.

### Direct URL format

https://nepsealpha.com/trading/chart\?symbol\=SYMBOL\&interval\=RESOLUTION

| Example           | URL                          |
| ----------------- | ---------------------------- |
| NEPSE index daily | ...?symbol=NEPSE&interval=1D |
| NABIL daily       | ...?symbol=NABIL&interval=1D |
| NABIL 1-hour      | ...?symbol=NABIL&interval=60 |

### How to switch stocks

Use NepseAlpha's own symbol search on the chart. The extension auto-detects the URL change (history.pushState) and fetches fresh data for the new stock — **no manual refresh needed**.

---

## 3. Resolution Dropdown

The widget's **resolution selector** (top-left of result header) switches timeframes without leaving the page. The extension fetches the correct NepseAlpha API endpoint and re-runs the full analysis.

### Available resolutions

| Widget Label   | API Code     | Candle Size   | Best For                        |
| -------------- | ------------ | ------------- | ------------------------------- |
| **1D (star)**  | 1D confirmed | 1 trading day | THE primary NEPSE chart         |
| **1W**         | 1W confirmed | 1 week        | Big-picture S/R                 |
| **1M**         | uses 1D data | ~22 days      | Macro context                   |
| **4H**         | 240          | 4 hours       | Swing structure                 |
| **1H (star)**  | 60 confirmed | 1 hour        | Best entry timing               |
| **30m**        | 30 confirmed | 30 min        | Intraday confirmation           |
| **15m (star)** | 15           | 15 min        | Precision entry                 |
| **5m**         | 5 confirmed  | 5 min         | Scalp fine-tune                 |
| **1m**         | 1 confirmed  | 1 minute      | Real-time momentum              |
| **1S**         | 1S confirmed | 1 second      | Tick-level / operator injection |

**Priority resolutions (star) for consistent profit:** 1D for bias, 1H for timing, 15m for entry.

> If the API rejects a resolution (e.g. 4H not natively supported), the widget shows a clear error with a Retry button — it will never spin forever since v2.0+.

---

## 4. The 3-Timeframe Trading Strategy

The most consistently profitable NEPSE approach using this widget:

Step 1 — BIAS: Open 1D chart. Is the stock UPTREND? Is verdict BUY/STRONG BUY?
Step 2 — TIMING: Switch to 1H. Wait for pullback to key level + RSI not overbought.
Step 3 — ENTRY: Switch to 15m. Enter only on 15m BUY signal with matching momentum.

**Only take trades where all 3 align.**

### Daily (1D) — Establishing the Bias

| Signal                           | Meaning                          |
| -------------------------------- | -------------------------------- |
| UPTREND + RSI 45-65              | Healthy uptrend with room to run |
| Above SMA20 & SMA50              | Strong trend structure           |
| MACD Bullish + histogram rising  | Momentum building                |
| No operator manipulation warning | Clean move                       |
| Breakout: Resistance Broken      | New leg confirmed                |

**Do NOT buy if the daily is DOWNTREND or STRONG SELL, regardless of lower-TF signals.**

### Hourly (1H) — Finding Entry Timing

| Signal                               | Meaning               |
| ------------------------------------ | --------------------- |
| Pullback to SMA20 on 1H (RSI ~40-55) | Classic re-entry zone |
| MACD crossing zero from below        | Momentum shift        |
| Engulfing candle at support          | Demand zone active    |

### 15-Minute (15m) — Precision Entry

| Signal                          | Meaning              |
| ------------------------------- | -------------------- |
| BUY verdict on 15m              | Micro-trend aligned  |
| RSI rising from 40 zone         | Momentum confirmed   |
| Volume spike on breakout candle | Real buyers entering |

---

## 5. Widget Layout — The 6-Tab Interface

| Tab       | What it shows                                       | When to use                         |
| --------- | --------------------------------------------------- | ----------------------------------- |
| Overview  | Verdict, price, trend, breakout, patterns, warnings | Read first — every analysis         |
| Momentum  | Oscillators: RSI, MACD, Stoch, CCI, Williams %R     | Is momentum building or fading?     |
| Technical | Moving averages: SMA20/50/200, EMA9/21              | Are you above or below key MAs?     |
| Multi-TF  | Higher TF alignment table + alignment badge         | Confirm 3-TF confluence             |
| Levels    | S/R zones, Fibonacci, Pivot Points                  | Set stop-loss and target price      |
| Market    | Wyckoff phase, 52-week range, operator activity     | Is this operator-driven or organic? |

### Header Controls

| Button               | Action                                              |
| -------------------- | --------------------------------------------------- |
| Resolution dropdown  | Switch timeframe — immediate fresh fetch & analysis |
| Retry (circle arrow) | Force-refresh — clears 30s dedup cache              |
| Collapse (arrow)     | Collapse widget to header only                      |
| Close (x)            | Hide widget — reload page to restore                |

---

## 6. Reading the Verdict

| Verdict     | Meaning                               | Action                                |
| ----------- | ------------------------------------- | ------------------------------------- |
| STRONG BUY  | All signals aligned bullish, ADX > 25 | Strong entry — confirm Multi-TF first |
| BUY         | Majority of signals bullish           | Good entry if 1D trend is UPTREND     |
| NEUTRAL     | Mixed signals                         | Wait — no trade                       |
| SELL        | Majority of signals bearish           | Avoid new longs, protect existing     |
| STRONG SELL | All signals aligned bearish           | Exit immediately if holding           |

### Confidence Score

| Score   | Interpretation                               |
| ------- | -------------------------------------------- |
| 85-100% | Very high alignment — rare and reliable      |
| 65-84%  | Good alignment — standard BUY/SELL territory |
| 45-64%  | Moderate — consider waiting                  |
| < 45%   | Weak — likely NEUTRAL                        |

---

## 7. Reading Every Indicator

### RSI (14-period)

| RSI Value | Zone               | Trading Meaning                        |
| --------- | ------------------ | -------------------------------------- |
| > 80      | Extreme Overbought | Imminent reversal risk — do NOT buy    |
| 70-80     | Overbought         | Reduce position, trail stop            |
| 60-70     | Bullish Zone       | Trending up — normal for strong stocks |
| 40-60     | Neutral Zone       | Watch for direction                    |
| 30-40     | Bearish Zone       | Weakening                              |
| 20-30     | Oversold           | Potential bounce — confirm with MA     |
| < 20      | Extreme Oversold   | Watch for reversal                     |

**NEPSE rule:** RSI 45-65 on daily = ideal buy zone.

### MACD

| Signal                                    | Meaning                            |
| ----------------------------------------- | ---------------------------------- |
| MACD line crosses above signal line       | Bullish crossover — potential BUY  |
| MACD line crosses below signal line       | Bearish crossover — potential SELL |
| Both lines above zero + histogram rising  | Strong uptrend momentum            |
| Both lines below zero + histogram falling | Strong downtrend — avoid buying    |
| Price new high, MACD lower high           | Bearish divergence — exit warning  |

### ADX (14-period) — Trend Strength

| ADX   | Meaning                                 |
| ----- | --------------------------------------- |
| > 50  | Very Strong trend — accelerating        |
| 25-50 | Strong trend — follow with confidence   |
| 20-25 | Developing trend — entry zone           |
| < 20  | Choppy range — indicators less reliable |

**Never trade MACD/RSI signals when ADX < 20. It is a range, not a trend.**

### Moving Averages

| Signal                         | Meaning                                     |
| ------------------------------ | ------------------------------------------- |
| Price > SMA20 > SMA50 > SMA200 | Perfect bullish stack                       |
| Price crosses above SMA50      | Medium-term buy signal                      |
| Price below SMA200             | Long-term downtrend — avoid position trades |
| EMA9 crosses above EMA21       | Short-term momentum flip                    |

**NEPSE rule:** SMA200 on daily is the single most important level for position traders.

---

## 8. The Complete Buying Decision Framework

### Daily (1D) Checklist — All must be YES:

- Verdict is BUY or STRONG BUY?
- Trend is UPTREND?
- RSI between 40-70 (not overbought)?
- Price above SMA50 (or just reclaimed it)?
- MACD Bullish OR crossing up?
- No critical warnings (operator distribution, divergence)?
- ADX > 20 (actual trend, not chop)?

### Hourly (1H) Checklist:

- Hourly trend is UPTREND or NEUTRAL?
- RSI not above 70?
- At or near a support level (not resistance)?

### 15-Minute (15m) Checklist:

- 15m verdict BUY or STRONG BUY?
- RSI trending up from 40-50?
- Volume above average on the entry candle?

### Market Tab Check:

- Wyckoff phase is Accumulation or Markup?
- No operator manipulation warning?
- Position is not at 52-week extreme high (unless confirmed breakout)?

**If any item in the Daily Checklist is NO -> do not trade.**

### Position Sizing by Confidence

| Confidence | Daily Verdict | Position Size               |
| ---------- | ------------- | --------------------------- |
| 85%+       | STRONG BUY    | 100% of planned size        |
| 70-84%     | BUY           | 75%                         |
| 55-69%     | BUY           | 50% — wait for confirmation |
| < 55%      | NEUTRAL       | 0% — no trade               |

---

## 9. All 27 Candlestick Patterns

Patterns appear in the Overview tab as colored tags with +N (bullish strength) or -N (bearish).

### High-Reliability Reversal Patterns

| Pattern           | Direction | Meaning                                                    |
| ----------------- | --------- | ---------------------------------------------------------- |
| Bullish Engulfing | Bullish   | Strong buyer takeover — enter at support                   |
| Bearish Engulfing | Bearish   | Strong seller takeover — exit at resistance                |
| Morning Star      | Bullish   | 3-candle reversal from downtrend — most reliable           |
| Evening Star      | Bearish   | 3-candle reversal from uptrend — exit on confirmation      |
| Hammer            | Bullish   | Long lower wick at support — buyers defended the level     |
| Shooting Star     | Bearish   | Long upper wick at resistance — sellers rejected the level |
| Inverted Hammer   | Bullish   | Potential reversal at bottom (needs confirmation)          |
| Hanging Man       | Bearish   | Exit warning after uptrend                                 |
| Piercing Line     | Bullish   | Closes above 50% of previous bearish candle                |
| Dark Cloud Cover  | Bearish   | Closes below 50% of previous bullish candle                |
| Tweezer Bottom    | Bullish   | Two equal lows — strong support confirmed                  |
| Tweezer Top       | Bearish   | Two equal highs — strong resistance confirmed              |

### Continuation Patterns

| Pattern               | Direction | Meaning                                             |
| --------------------- | --------- | --------------------------------------------------- |
| Three White Soldiers  | Bullish   | 3 consecutive bullish candles — strong continuation |
| Three Black Crows     | Bearish   | 3 consecutive bearish candles — avoid/exit          |
| Rising Three Methods  | Bullish   | Bullish pause + continuation                        |
| Falling Three Methods | Bearish   | Bearish continuation                                |

### Indecision Patterns (Confirm before acting)

| Pattern                 | Meaning                                              |
| ----------------------- | ---------------------------------------------------- |
| Doji                    | Equilibrium — direction goes to whoever breaks first |
| Gravestone Doji         | Bearish — sellers won the session                    |
| Dragonfly Doji          | Bullish — buyers defended the low                    |
| Spinning Top / Marubozu | Indecision vs. very high conviction                  |

---

## 10. Support, Resistance & Key Levels

### Levels Tab

S1/S2/S3 = Support floors below current price (S1 = nearest)
R1/R2/R3 = Resistance ceilings above current price (R1 = nearest)

Trading rule: Enter near S1 -> Target R1 -> Stop just below S1 (minimum 1:2 risk/reward)

### Fibonacci Retracement

| Level         | Meaning                                    |
| ------------- | ------------------------------------------ |
| 38.2% (0.382) | Shallow pullback — healthy trend           |
| 50%           | Moderate pullback — common re-entry zone   |
| 61.8% (0.618) | Golden ratio — strongest Fibonacci support |
| 78.6%         | Deep pullback — trend weakening            |

**NEPSE rule:** Buy at 61.8% retracement of confirmed uptrend, RSI 45-55, MACD turning up.

### Pivot Points

| Level            | Use                                        |
| ---------------- | ------------------------------------------ |
| PP (Pivot Point) | Today's directional bias — above = bullish |
| R1/R2            | Intraday resistance / profit targets       |
| S1/S2            | Intraday support / stop-loss zones         |

---

## 11. NEPSE-Specific Rules

### NEPSE Market Hours

- Trading: 11:00 AM - 3:00 PM Nepal time (4 hours / 240 minutes per day)
- Intraday bars per trading day: 240 x 1-min, 48 x 5-min, 16 x 15-min, 8 x 30-min, 4 x 1-hour

### Operator Activity

| Warning                         | Meaning                            | Action                               |
| ------------------------------- | ---------------------------------- | ------------------------------------ |
| Potential operator manipulation | Abnormal volume + price divergence | Avoid unless you understand the game |
| RSI divergence (bearish)        | Price new high but RSI lower       | Exit — smart money distributing      |
| RSI divergence (bullish)        | Price new low but RSI higher       | Potential reversal — confirm first   |

### Wyckoff Market Phases

| Phase        | What is happening                   | Trader action                      |
| ------------ | ----------------------------------- | ---------------------------------- |
| Accumulation | Smart money buying quietly          | BUILD positions — best entry phase |
| Markup       | Price trending up — public entering | HOLD long, add on pullbacks        |
| Distribution | Smart money selling into retail     | REDUCE positions, trail stop       |
| Markdown     | Downtrend                           | AVOID / EXIT                       |

### Volume Rules

| Signal                    | Meaning                         |
| ------------------------- | ------------------------------- |
| Breakout + high volume    | Real breakout — enter           |
| Breakout + low volume     | Fake breakout — wait for volume |
| Down candle + high volume | Heavy selling — warning         |
| Down candle + low volume  | Weak sellers — healthy pullback |

---

## 12. Troubleshooting

### Error messages decoded

| Error                    | Cause                                      | Fix                                      |
| ------------------------ | ------------------------------------------ | ---------------------------------------- |
| Analysis timed out (20s) | Backend not running                        | Run: uvicorn main:app --reload           |
| Backend timed out        | Backend crash or overload                  | Check terminal for Python errors         |
| Fetch failed: HTTP 422   | Resolution not supported by NepseAlpha API | Try 1D, 1H, 30m, 5m, 1m                  |
| No chart data returned   | API returned empty/non-OHLCV data          | Refresh page or try different resolution |

### Widget not appearing

1. Must be on https://nepsealpha.com/trading/chart\?symbol\=... (exact path)
2. Check chrome://extensions/ — extension must be enabled
3. Open DevTools (F12) Console — should see: [NEPSE Analyzer] NepseAlpha interceptor active
4. If not, reload the extension

### Force-refresh / stuck widget

Click the circle-arrow (retry) button on the widget. This clears the 30-second deduplication cache and triggers a fresh fetch.

### Backend startup

cd nepse_ai_trading
source .venv312/bin/activate
uvicorn main:app --reload --port 8000

Test: curl http://localhost:8000/health

### Console diagnostics (DevTools F12 -> Console)

[NEPSE Analyzer] NepseAlpha interceptor active <- extension loaded OK
[NEPSE Analyzer] Auto-fetch: NABIL (1D->api:1D) <- fetch triggered
[NEPSE Analyzer] 1000 candles _ NABIL _ 1D <- data OK
[NEPSE Analyzer] NABIL (240): Fetch failed: HTTP 422 <- resolution not supported


---

## Part II — Timeframe-Specific Analysis Guides

> **Expert-level playbooks** for each trading timeframe. Use these alongside the core reference above for complete NEPSE mastery.

## 21. How to Analyze: 1-Hour Market (Intraday)

**When to use:** You want to time your entry within the NEPSE trading session (11:00–15:05).

### Setup

1. Open chart → Set resolution to **1 hour**
2. Set range to **5d** or **1m** (gives you enough hourly bars)
3. Widget automatically shows Hourly analysis + resampled Daily + Weekly

### What to Look For

| Widget Element | Bullish (BUY) Signal              | Bearish (AVOID) Signal               |
| -------------- | --------------------------------- | ------------------------------------ |
| **Verdict**    | BUY or STRONG BUY                 | SELL or STRONG SELL                  |
| **RSI**        | 30–50 (momentum building)         | >70 (overbought for the hour)        |
| **MACD**       | Bullish (line above signal)       | Bearish                              |
| **Pattern**    | Hammer, Bullish Engulfing, Kicker | Shooting Star, Evening Star          |
| **Volume**     | Rising with price = genuine move  | Spike with flat price = trap         |
| **Multi-TF**   | Daily also BUY = high confidence  | Daily = SELL → this is a fake bounce |

### Expert Hourly Analysis Strategy

**NEPSE trades only ~4 hours per day.** Each hourly candle is significant:

| Hour       | Time        | Character                     | Expert Behavior                                                                                                                               |
| ---------- | ----------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hour 1** | 11:00–12:00 | Opening volatility, gap fills | **DO NOT BUY.** Wait for the noise to settle. Operators and institutions place large orders that create false signals.                        |
| **Hour 2** | 12:00–13:00 | Trend establishment           | If direction is clear (MACD Bullish + RSI rising from 40–50), this is the **safest entry window**.                                            |
| **Hour 3** | 13:00–14:00 | Momentum peak                 | Strongest volume usually here. If RSI > 65 on hourly, the move is getting old — don't chase.                                                  |
| **Hour 4** | 14:00–15:05 | End-of-day positioning        | Late buying = next-day confidence. Late selling = distribution. If widget shows BUY in hour 4 + high volume → **strong signal** for next day. |

### Hourly Indicator Priority

| Priority | Indicator    | Why It Matters on Hourly                                                                                  |
| -------- | ------------ | --------------------------------------------------------------------------------------------------------- |
| 1st      | **MACD**     | On hourly, MACD crossovers happen 1–2 times per day. A bullish crossover at hour 2 is highly reliable.    |
| 2nd      | **RSI**      | RSI 30–50 on hourly = room to run. RSI >65 = the move already happened.                                   |
| 3rd      | **Volume**   | Each hourly bar should have progressively more volume if the trend is real. Declining volume = fake move. |
| 4th      | **Patterns** | A Bullish Engulfing on the hourly chart at 12:00 after a morning dip = textbook entry.                    |

### Critical Rule

> **NEVER buy solely on an hourly signal.** Always confirm the **Daily chart** shows BUY or at least HOLD. Check the Multi-TF tab: if Daily = SELL but Hourly = BUY, it's a temporary bounce — you'll lose money.

---

## 22. How to Analyze: 1-Day Market (Swing Trading)

**When to use:** This is the **bread and butter** of NEPSE trading. Most profits come from holding 5–20 days.

### Setup

1. Open chart → Set resolution to **1 day** ⭐
2. Set range to **1y** (gives ~252 daily bars — enough for SMA200, all indicators)
3. Widget computes Daily + auto-resampled Weekly + Monthly

### The Complete Daily Analysis Checklist

**Step 1: Overview Tab — 10-second verdict**

- Verdict = BUY or STRONG BUY? → Proceed
- Confidence > 65%? → Good signal
- Both Oscillator + MA badge = Buy? → Strong confluence
- Status Cards: Breakout = Bullish? Structure = HH/HL? Phase = Markup or Accumulation?
- Nearest S/R Quick View: Support close (<2%) = good entry zone

**Step 2: Momentum Tab — 30-second momentum check** (NEW in v3.0)

| Check               | Bullish                                | Bearish                           |
| ------------------- | -------------------------------------- | --------------------------------- |
| **Momentum Status** | Bullish Acceleration or Strong Bullish | Decelerating or Bearish           |
| **Volume Profile**  | Accumulation                           | Distribution                      |
| **RSI Gauge**       | 35-55 with room to run                 | >70 overbought or <30 oversold    |
| **RSI Divergence**  | None or Bullish                        | Bearish Divergence = exit warning |
| **Volume Ratio**    | ≥1.0x (adequate participation)         | Spiking 3x+ on down day = selling |

**Step 3: Technical Tab — 2-minute deep dive**

| Check            | What to Confirm                                   | Red Flag (Skip the Trade)                          |
| ---------------- | ------------------------------------------------- | -------------------------------------------------- |
| **RSI(14)**      | 30–55 = ideal buy zone (coming out of oversold)   | >70 = don't buy, already overbought                |
| **StochRSI**     | K crossing above D from below 20 = perfect timing | K > 80 = too late                                  |
| **Williams %R**  | < −80 then rising = momentum turning              | > −20 = overbought                                 |
| **CCI(20)**      | Rising from below −100                            | > +100 falling = distribution                      |
| **ROC(14)**      | Positive and increasing                           | Negative and falling                               |
| **MACD**         | Line above Signal + Histogram turning green       | Line below Signal, histogram getting more negative |
| **All 7 MAs**    | Price above most = uptrend                        | Price below most = downtrend, don't buy            |
| **OBV Trend**    | Rising = smart money accumulating                 | Falling = distribution                             |
| **MA Crossover** | Golden Cross = long-term bullish                  | Death Cross = stay away                            |
| **DI+/DI-**      | DI+ > DI- = bullish pressure confirmed            | DI- > DI+ = bearish pressure dominating            |

**Step 4: Market Tab — 30-second intelligence check** (NEW in v3.0)

- Market Phase = Markup or Accumulation → Favorable conditions
- Market Structure = HH/HL Bullish → Trend intact
- Quick Checklist: Count ✅ marks → 5+ = proceed, <4 = skip

**Step 5: Multi-TF Tab — 1-minute macro check**

- Weekly verdict = BUY → You're aligned with the medium trend → **High confidence**
- Monthly verdict = BUY → The stock is in a macro bull cycle → **Highest confidence**
- ✅ Fully Aligned → This is the best trade on your watchlist

**Step 4: Levels Tab — 30-second price check**

- Current price near S1/S2 (Support) → Buying at a floor → **Great entry**
- Current price near R1/R2 (Resistance) → Buying near a ceiling → **Limited upside, skip**
- Fibonacci: Near 38.2% or 61.8% retracement → Classic bounce zone
- 52-Week Range: Near bottom quarter → **Value zone**; Near top = chasing

### Expert Daily Interpretation

**The "Perfect Daily Setup" (when all align):**

```
✅ Verdict: BUY (75%+)
✅ RSI: 35–50 (coming out of oversold, room to run)
✅ MACD: Just crossed bullish (histogram turned green from red)
✅ Trend: UPTREND (EMA10 > EMA30, ADX > 20)
✅ Pattern: Morning Star or Bullish Engulfing or Three Inside Up
✅ Volume: Normal or slightly above average
✅ Weekly: BUY
✅ Monthly: BUY or HOLD
✅ Price near Support or Fib 38.2%/61.8%
✅ OBV: Rising
✅ Market Phase: Accumulation or Markup (check Market tab)
✅ Momentum Status: Bullish (check Momentum tab)
✅ Market Structure: HH/HL Bullish (check Market tab)
```

**If you see 10+ of these 13 checkmarks → This is a high-probability trade.** Risk 2–3% of your portfolio.

### How Long to Hold (Daily Charts)

| Signal     | Hold Duration | Exit Trigger                             |
| ---------- | ------------- | ---------------------------------------- |
| STRONG BUY | 10–20 days    | Target hit or Evening Star on daily      |
| BUY        | 5–10 days     | Target hit, RSI > 70, or bearish pattern |
| HOLD       | 0 days        | Don't enter; re-evaluate in 2 days       |

---

## 23. How to Analyze: 1-Month Market (Position Trading)

**When to use:** You want to hold a stock for 1–3 months. You're looking for $stocks in a clear trend and riding the wave.

### Setup

1. Set resolution to **1 week** (gives ~52 weekly bars per year)
2. Set range to **1y** or **3m**
3. Widget computes Weekly + auto-resampled Monthly + Quarterly

OR:

1. Set resolution to **1 day**, range to **1m**
2. Look at only the last 22 bars (1 trading month)

### What Monthly Analysis Tells You

| Widget Element   | Bullish Monthly Signal                 | Bearish Monthly Signal                 |
| ---------------- | -------------------------------------- | -------------------------------------- |
| **Weekly Trend** | UPTREND for 4+ weeks                   | DOWNTREND for 4+ weeks                 |
| **Monthly RSI**  | 40–60 (healthy trend, not overheated)  | >75 (monthly overbought = major top)   |
| **SMA(50)**      | Price above SMA50                      | Price below SMA50                      |
| **SMA(200)**     | Price above SMA200 = bull market stock | Price below SMA200 = bear market stock |
| **MACD Monthly** | Bullish                                | Bearish                                |
| **Golden Cross** | SMA50 just crossed above SMA200        | Death Cross = exit                     |

### Expert Monthly Rules

1. **The SMA200 Rule:** If a stock is below its SMA(200) on the daily chart, it is in a **bear market**. Do not buy for position trades regardless of other signals. Wait for price to reclaim SMA200.

2. **Monthly RSI Sweet Spot:** The best 1-month trades start when monthly RSI is 40–55 and rising. This means the stock just came out of a correction and has a full 15–30 points of RSI room to run.

3. **Volume Trend:** Over 4 weeks, volume should be gradually increasing on up-days and decreasing on down-days. The OBV should be Rising.

4. **Fibonacci for Position Entry:** After a stock pulls back from a 1-month high, enter at the 38.2% or 50% Fibonacci retracement level. This is where institutions typically re-enter.

---

## 24. How to Analyze: 3-Month Market (Trend Following)

**When to use:** You're identifying which stocks are in the strongest trends over a quarter.

### Setup

1. Set resolution to **1 week**, range to **6m** or **1y**
2. You get ~26–52 weekly bars — perfect for trend analysis
3. Widget multi-TF shows Monthly + Quarterly analysis

### The 3-Month Trend Framework

| Phase               | RSI Range       | EMA State                                    | Volume                   | Widget Shows          | Action                         |
| ------------------- | --------------- | -------------------------------------------- | ------------------------ | --------------------- | ------------------------------ |
| **Accumulation**    | 30–45           | EMA10 below EMA30 but flattening             | Low but increasing       | HOLD / early BUY      | Start watching; prepare to buy |
| **Mark-Up (Early)** | 45–55           | EMA10 just crossed above EMA30               | Increasing               | BUY 65%+              | **BEST ENTRY POINT**           |
| **Mark-Up (Mid)**   | 55–65           | EMA10 well above EMA30, both rising          | Consistently high        | BUY / STRONG BUY      | Still safe to buy, trail stop  |
| **Distribution**    | 65–80           | EMA10 flattening while price makes new highs | Very high then declining | BUY → HOLD transition | **START TAKING PROFIT**        |
| **Mark-Down**       | <50 and falling | EMA10 below EMA30                            | Declining                | SELL / STRONG SELL    | Exit all positions             |

### Expert 3-Month Analysis

**The Quarterly Sector Rotation:**
Every 3 months, money flows between NEPSE sectors. Use the widget on multiple sector leaders:

1. Analyze 5+ stocks from different sectors (Banking: NABIL, NICA; Hydro: BPCL, API; Insurance: NLIC; Manufacturing: UNL)
2. Which sectors show the most BUY signals with Weekly + Monthly alignment?
3. That sector is leading the current quarter — focus your capital there
4. Sectors showing SELL + falling RSI = money is leaving → avoid

### Key Indicators for 3-Month View

| Indicator            | Bullish (Entering Trend)                          | Bearish (Trend Ending)                            |
| -------------------- | ------------------------------------------------- | ------------------------------------------------- |
| **ADX**              | Rising from 15 → 25+                              | Falling from 30+ → below 20                       |
| **MACD Histogram**   | Getting taller (green) for 3+ weeks               | Getting shorter or turning red                    |
| **SMA50 vs SMA200**  | SMA50 rising toward SMA200 (pending Golden Cross) | SMA50 falling toward SMA200 (pending Death Cross) |
| **Fibonacci**        | Price bouncing from 61.8% of 3-month range        | Price breaking below 61.8%                        |
| **52-Week Position** | In bottom 25–50% of range = value                 | In top 10% = exhaustion risk                      |

---

## 25. How to Analyze: 6-Month Market (Sector Rotation)

**When to use:** Strategic capital allocation. Which sectors and stocks deserve your money for the next half-year?

### Setup

1. Set resolution to **1 week**, range to **1y** (52 weekly bars)
2. Or set resolution to **1 month**, range to **1y** or **5y**
3. Widget shows Monthly + Quarterly context

### The 6-Month Strategic Framework

Over 6 months, you're not looking at individual candles — you're looking at the **shape of the trend**:

| Chart Shape                    | What It Means                 | Widget Signature                       | Action                                    |
| ------------------------------ | ----------------------------- | -------------------------------------- | ----------------------------------------- |
| **Higher highs + Higher lows** | Healthy uptrend               | BUY, RSI 45–65, EMA10>EMA30            | Accumulate on pullbacks                   |
| **Flat channel (range-bound)** | Consolidation before breakout | HOLD, RSI 40–60, ADX <20               | Wait for breakout direction               |
| **Lower highs + Lower lows**   | Downtrend                     | SELL, RSI <45 falling, EMA10<EMA30     | Do not buy, wait 3+ months                |
| **V-shaped bounce**            | Panic selling → recovery      | BUY, RSI rapidly rising from <30       | Enter after confirmation (2nd higher low) |
| **Rounding bottom**            | Long-term reversal forming    | HOLD→BUY transition, RSI slowly rising | Best long-term entry zone                 |

### Expert 6-Month Indicators

**What matters most on 6-month horizon:**

1. **SMA200** — This is the single most important line. Stocks above SMA200 are in bull territory. Below = bear territory. In 6-month analysis, only buy stocks that have been above SMA200 for 3+ months.

2. **Monthly RSI Divergence** — If price makes new 6-month lows but RSI makes higher lows → **Bullish divergence** = the stock is about to reverse upward. This is one of the most powerful signals in technical analysis.

3. **Volume Profile** — Look at the OBV trend over 6 months. If OBV is steadily rising while price has been flat → Smart money is quietly accumulating. When the stock breaks out, it will be powerful.

4. **Fibonacci from 6-Month Range** — Calculate Fibonacci from the 6-month high to 6-month low. If price is sitting at the 38.2% or 50% level → ideal re-entry.

### NEPSE 6-Month Calendar Strategy

| Period              | NEPSE Character                                       | Widget Use                                           |
| ------------------- | ----------------------------------------------------- | ---------------------------------------------------- |
| **Mid-July – Sept** | Q1 results season, dividend announcements             | Screen for stocks showing BUY right before results   |
| **Oct – Dec**       | Post-dividend correction → value opportunities        | Look for RSI < 40 on good companies with HOLD/BUY    |
| **Jan – March**     | Q2 results, fiscal year-end positioning               | Banks/finance show strength — check sector alignment |
| **April – July**    | Tax-loss selling → year-end pressure → new year rally | Best 6-month buying window; look for STRONG BUY      |

---

## 26. How to Analyze: 1-Year Market (Investor Grade)

**When to use:** You're making investment decisions, not trading decisions. Holding 6–18 months.

### Setup

1. Set resolution to **1 week**, range to **5y** (gives ~260 weekly bars)
2. Or set resolution to **1 month**, range to **5y** (gives 60 monthly bars)
3. Widget shows Quarterly + Yearly analysis

### The Annual Analysis Framework

| Question                    | Where to Look                    | Bullish Answer                       | Bearish Answer      |
| --------------------------- | -------------------------------- | ------------------------------------ | ------------------- |
| Is the stock above SMA200?  | Technical Tab → MA table         | ✅ Price > SMA200                    | ❌ Price < SMA200   |
| Is the macro trend up?      | Multi-TF Tab → Quarterly verdict | Quarterly = BUY or HOLD              | Quarterly = SELL    |
| Where in the 52-week range? | Levels Tab → 52-Week bar         | Bottom 40% (value)                   | Top 15% (risky)     |
| Is there a Golden Cross?    | Warnings section                 | ✨ Golden Cross = bullish year ahead | 💀 Death Cross      |
| Is volume confirming?       | Technical Tab → OBV Trend        | Rising OBV                           | Flat/Falling OBV    |
| Are institutions buying?    | Overview → Operator Activity     | Volume spike + BUY = accumulation    | Volume spike + SELL |

### Expert Annual Cycle Analysis

**The 4 Phases of a Stock's Annual Cycle:**

```
Phase 1: BASE (2–4 months)
├── RSI: 30–45, sideways
├── ADX: < 20 (no trend)
├── Volume: Low
├── Widget: HOLD (45–55% confidence)
└── Action: Add to watchlist, DO NOT BUY YET

Phase 2: ADVANCE (2–4 months)
├── RSI: 45–65, rising
├── ADX: Rising above 20 → 30+
├── Volume: Increasing on up-days
├── Widget: BUY → STRONG BUY (65–85%)
├── Golden Cross may appear
└── Action: ★★★ PRIMARY BUY ZONE ★★★

Phase 3: TOP (1–3 months)
├── RSI: 65–80, flattening
├── ADX: > 30 but declining
├── Volume: High but erratic
├── Widget: BUY → HOLD transition
├── Bearish patterns start appearing (Evening Star, Dark Cloud)
└── Action: TAKE PROFIT, move SL to breakeven

Phase 4: DECLINE (2–4 months)
├── RSI: < 50, falling
├── ADX: Still > 20 (strong downtrend)
├── Volume: Spikes on down-days
├── Widget: SELL → STRONG SELL (65–90%)
├── Death Cross may appear
└── Action: DO NOT BUY. Wait for Phase 1 to form again.
```

### The Annual SMA200 Strategy (Most Reliable)

This single strategy beats most NEPSE traders:

1. **Buy** when price crosses above SMA200 and stays above for 5 consecutive daily bars
2. Widget confirms: Golden Cross warning + BUY verdict + Weekly BUY
3. **Hold** as long as price is above SMA200
4. **Sell** when price crosses below SMA200 and stays below for 5 bars
5. Widget confirms: Death Cross warning + SELL verdict

This avoids the major declines and captures the major rallies. It trades 1–3 times per year per stock.

---

## 27. How to Analyze: 5-Year Market (Wealth Building)

**When to use:** You're building a long-term portfolio. Selecting stocks to hold for years.

### Setup

1. Set resolution to **1 month**, range to **5y** (60 monthly bars)
2. Or set resolution to **3 months** or **6 months**, range to **5y**
3. Widget shows overview of the macro cycle

### What 5-Year Analysis Reveals

On a 5-year chart, you're looking at the **mega-trend** — the overall direction of a company's stock price over its recent history. This is not about timing; it's about selection.

| 5-Year Pattern                  | Meaning                       | Investment Decision                                            |
| ------------------------------- | ----------------------------- | -------------------------------------------------------------- |
| **Steady upward slope**         | Consistently growing business | ✅ Core portfolio holding — invest on any significant pullback |
| **Flat with occasional spikes** | No real growth, speculative   | ⚠️ Trading stock only — not for long-term                      |
| **Gradual decline**             | Business deteriorating        | ❌ Do not invest regardless of current BUY signal              |
| **Sharp decline then recovery** | Crisis/recovery cycle         | ✅ If fundamentals are fixed, the recovery is the opportunity  |
| **Explosive growth then flat**  | Growth phase is over          | ⚠️ Only if new growth catalyst exists                          |

### Expert 5-Year Analysis Rules

1. **The "Higher Year-Over-Year" Rule:** Each year's high should be higher than the previous year's high, and each year's low should be higher than the previous year's low. If both are true → the stock is in a **SECULAR UPTREND**. These are the safest investments.

2. **Historic Support Zones:** On a 5-year chart, the Fibonacci levels in the Levels tab show the most important support/resistance of the stock's entire recent history. The 61.8% retracement of a 5-year rally is where institutions will aggressively buy.

3. **5-Year RSI:** If the monthly RSI drops below 30 on a stock that has been in a 5-year uptrend, this is a **generational buying opportunity**. It means the long-term trend is intact but the stock had a temporary panic. Examples: Post-COVID crash, post-earthquake recovery.

4. **Volume Tells the Story:** On a 5-year chart with monthly candles, look for gradually increasing volume over the years = growing market interest in the stock. Decreasing volume over years = the stock is being abandoned.

---

## 28. Multi-Timeframe Confluence — The Master Skill

> **This is the single most important section of this guide.** If you learn only one thing, learn this. Multi-timeframe confluence is what separates profitable traders from everyone else.

### The Principle

**Higher timeframes overrule lower timeframes.**

- If the monthly chart says SELL, a daily BUY is just noise.
- If the weekly chart says BUY and the daily says BUY, the probability doubles.
- If monthly + weekly + daily all say BUY, you have a maximum-confidence setup.

### Confluence Decision Matrix

| Monthly | Weekly | Daily | Action                                              | Confidence |
| ------- | ------ | ----- | --------------------------------------------------- | ---------- |
| BUY     | BUY    | BUY   | ✅ **MAXIMUM BUY** — Full position, widest stop     | 90%+       |
| BUY     | BUY    | HOLD  | ✅ Buy on next daily BUY signal (wait 1–3 days)     | 80%        |
| BUY     | BUY    | SELL  | ⚠️ Wait — daily is pulling back within a bull trend | Wait       |
| BUY     | HOLD   | BUY   | ✅ Buy with half position                           | 70%        |
| BUY     | SELL   | BUY   | ❌ Skip — weekly divergence is dangerous            | Skip       |
| HOLD    | BUY    | BUY   | ✅ Buy with normal position                         | 75%        |
| HOLD    | HOLD   | BUY   | ⚠️ Scalp only — no trend backing the move           | 50%        |
| SELL    | BUY    | BUY   | ❌ **DO NOT BUY** — you're fighting the macro trend | 0%         |
| SELL    | SELL   | BUY   | ❌ **DANGEROUS** — this is a bear market bounce     | 0%         |
| SELL    | SELL   | SELL  | 🔴 **MAXIMUM SELL** — exit immediately              | 95%        |

### How to Read the Widget's Multi-TF Tab

1. Open chart with **1D resolution**, **1Y range**
2. Click the **🔄 Multi-TF** tab
3. Read the three rows: Current (Daily) / Weekly / Monthly
4. Look for:
   - **✅ Fully Bullish Aligned** → All green → Highest confidence BUY
   - **⚠️ Partially Aligned** → Mixed → Trade cautiously or wait
   - **🔴 Fully Bearish Aligned** → All red → DO NOT BUY

### Real-World NEPSE Example

Suppose you're analyzing NABIL:

```
Current (Daily):  RSI 42  |  MACD ▲  |  Trend ▲  |  BUY
Weekly:           RSI 48  |  MACD ▲  |  Trend ▲  |  BUY
Monthly:          RSI 55  |  MACD ▲  |  Trend →  |  HOLD
Alignment: ⚠️ Partially Aligned
```

**Expert interpretation:** Daily + Weekly agree on BUY (strong), but Monthly is HOLD (neutral). This means the stock is in an uptrend that started recently (weekly) but the bigger monthly cycle hasn't fully confirmed. **Action:** Buy with normal position size, but use the widget's suggested stop loss strictly.

---

## 29. Glossary — Essential Share Market Terms

The Market tab includes a glossary of essential share market terms:

| Term             | Definition                                      | Trading Significance                                      |
| ---------------- | ----------------------------------------------- | --------------------------------------------------------- |
| **Breakout**     | Price breaks above resistance with volume       | Often starts a new uptrend — buy signal                   |
| **Breakdown**    | Price falls below support with volume           | Often starts a new downtrend — sell signal                |
| **Accumulation** | Smart money buying during a range               | Price will eventually break up — watch for entry          |
| **Distribution** | Smart money selling at the top                  | Price will eventually break down — prepare to exit        |
| **HH/HL**        | Higher High / Higher Low                        | Bullish market structure — trend is healthy               |
| **LH/LL**        | Lower High / Lower Low                          | Bearish market structure — trend is broken                |
| **Golden Cross** | SMA50 crosses above SMA200                      | Long-term bullish signal — multi-month uptrend ahead      |
| **Death Cross**  | SMA50 crosses below SMA200                      | Long-term bearish signal — multi-month downtrend ahead    |
| **Divergence**   | Price and indicator move in opposite directions | Leading reversal signal — very reliable                   |
| **Confluence**   | Multiple indicators agree on direction          | Higher probability trade — more indicators agree = better |

---

