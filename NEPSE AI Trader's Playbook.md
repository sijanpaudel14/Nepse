***
# 📖 The NEPSE AI Trader's Playbook: Professional Execution Guide

Having the most advanced quantitative code in Nepal is only 50% of the equation. The other 50% is **execution discipline**. Your code is a high-performance engine that finds the right stocks, but *you* are the driver who must manage the money, the risk, and the timing.

This playbook outlines the exact daily routines, portfolio management mathematics, and advanced operator-tracking strategies required to systematically extract wealth from the Nepal Stock Exchange (NEPSE) without relying on luck or emotion.

***

## CHAPTER 1: Portfolio Management & Mathematical Risk

Amateur traders try to get rich on one lucky trade. Professional quants get rich by playing mathematical probabilities over hundreds of trades.

### 1. The "Core & Satellite" Portfolio Design
Never put 100% of your money into a single trading strategy. Because your AI Engine has two distinct "brains" (`Value` and `Momentum`), you must split your capital to match them.

*   **The Core (60% of your Capital):** 
    *   **Command:** `python tools/paper_trader.py --strategy=value --sector=bank`
    *   **The Goal:** Wealth preservation and compounding. You use 60% of your money to buy the top-scoring Commercial Banks or Manufacturing companies. 
    *   **Why?** These are mathematically cheap (P/E < 15), dividend-paying fortresses. You hold these for 6 to 12 months. If the NEPSE index suddenly crashes due to a Nepal Rastra Bank (NRB) policy change, your Core portfolio will drop the least, and the cash dividends will offset your paper losses.
*   **The Satellite (40% of your Capital):**
    *   **Command:** `python tools/paper_trader.py --strategy=momentum --sector=hydro` (or finance/hotels)
    *   **The Goal:** Aggressive capital growth. You use this 40% to ride operator pumps for 1 to 2 weeks. 
    *   **Why?** Momentum trading is highly profitable but inherently risky because the companies are fundamentally garbage. By limiting this to 40% of your capital, a worst-case scenario (like a stock getting halted by SEBON) will never wipe out your main wealth.

### 2. Position Sizing (The "Rule of 5")
The fastest way to destroy your account is putting 100% of your trading capital into the engine's #1 pick. If that specific company delays its quarterly report or gets flagged for insider trading, your entire account is paralyzed.

*   **The Rule:** Never allocate more than **20%** of your active trading capital into a single ticker.
*   **The Mathematics of Winning:** Let’s say you have Rs. 500,000 for your Satellite (Momentum) portfolio. Your engine gives you 5 stocks. You buy exactly Rs. 100,000 of all 5 stocks. 
    *   *Trade 1:* Hits Target (+10%) = + Rs. 10,000
    *   *Trade 2:* Hits Target (+10%) = + Rs. 10,000
    *   *Trade 3:* Hits Target (+10%) = + Rs. 10,000
    *   *Trade 4:* Goes nowhere (Flat) = Rs. 0
    *   *Trade 5:* Hits Stop Loss (-5%) = - Rs. 5,000
    *   **Net Result:** + Rs. 25,000 Profit. You had a failing trade, a dead trade, and you *still* made a 5% total return on your portfolio in two weeks.

### 3. Mechanical Stop-Loss Discipline (Zero Emotion)
Your engine outputs exact mathematical instructions, such as: `❌ EXIT RULE 2: SELL at Rs.288 (Stop -7.5%)`.

*   **Act like a machine:** If the price touches Rs. 288, you log into TMS and sell. Immediately.
*   **The Psychology Trap:** When a stock drops, retail traders panic. They look at the chart hoping it will bounce. They go to ShareSansar to find positive news to justify holding it. They turn a "short-term swing trade" into a "long-term investment."
*   **The Reality:** A professional trader takes a small -5% papercut today to prevent a catastrophic -40% amputation next month. **Let the algorithm take the loss, and move that capital to the next winning setup.**

***

## CHAPTER 2: Market Microstructure & Perfect Timing

In NEPSE, *when* you press the buy button is just as critical as *what* you are buying. Operators use the clock to manipulate retail traders.

### Rule #1: NEVER Buy at 11:00 AM (The Morning Trap)
Do not execute buy orders in the first hour of the market (11:00 AM to 12:00 PM).
*   **The Manipulation:** Operators use the 10:30 AM "Pre-Open" matching session to place massive, fake buy orders. This forces the stock to open +3% or +4% higher. 
*   **The Trap:** At 11:00 AM, the market opens. Retail traders see the stock glowing green on the "Top Gainers" list. They feel extreme FOMO (Fear of Missing Out) and rush to buy. The operators instantly cancel their remaining buy orders and start dumping their shares onto the panicked retail buyers. By 12:00 PM, the stock is red.
*   **The Blindspot:** If you run your engine at 10:00 AM, the AI only knows the data from *yesterday*. It cannot foresee the fake morning gap-up.

### The Optimal Routine: "The Golden Hour" (2:30 PM - 2:45 PM)
Institutional and algorithmic traders do not trade the morning noise. They execute at the end of the day, when the volume has settled and the operators have revealed their true daily intentions.

1.  **2:30 PM (Run the Scan):** Run `python tools/paper_trader.py --action=scan`. At this time, your new VWAP code will capture 3.5 hours of today's live volume. If operators spent the morning dumping, your code will see it and instantly flag the stock as `🚨 CRITICAL RISK`. 
2.  **2:45 PM (Execute):** Review the Top 5 picks. If a stock maintained an 85+ score through the intraday chaos, has strong volume, and a `✅ LOW` distribution risk, place your buy order before the 3:00 PM close.
3.  **The T+2 Advantage:** In NEPSE, you cannot sell a stock for 2 days. By buying at 2:55 PM, you get official credit for holding the stock "Today," pushing you closer to your unlock date, while completely bypassing the risk of today's intraday crashes.

***

## CHAPTER 3: Advanced Sector Rotation Masterclass

In mature markets (like the US), the entire market can rise together because trillions of dollars flow in daily. In Nepal, the daily turnover is only a few Arba (Crores). **There is not enough money in NEPSE to pump Banks, Hydropower, Finance, and Hotels at the same time.**

Operators must play a game of musical chairs. 
1.  **Pump:** They push Hydropower up 30%. Retail FOMO kicks in.
2.  **Dump:** They sell their Hydro shares to retail at the absolute top.
3.  **Rotate:** They take that massive cash pile and secretly move into the **Finance** sector, which is currently at the bottom.
4.  **Repeat:** Next week, Hydro crashes, Finance explodes 30%, and retail traders are left holding the bag, always one step behind.

### The Friday "Heatmap" Protocol
To beat them, you must track where the money is moving *before* the retail crowd notices. Every Friday afternoon, run your scanner on individual sectors to test the temperature:
*   `--sector=hydro` (Result: 1 stock scores > 80)
*   `--sector=finance` (Result: 4 stocks score > 80)
*   `--sector=devbank` (Result: 0 stocks score > 80)
*   **The Intelligence:** The algorithm has detected that the operators have abandoned Hydropower and are heavily injecting their liquidity into Finance. Finance is the active rotation. You focus all your trades here next week.

***

## CHAPTER 4: The Operator Tracking Cheat Codes

Your engine contains two highly advanced, institutional-grade logic gates. Here is how to read them like a professional quant.

### Cheat Code 1: The "Pillar 1" Stealth Radar
Operators accumulate shares quietly. If they buy too fast, the price spikes and other people notice. So, they buy slowly, keeping the price perfectly flat. 

You can spot this invisible accumulation by comparing two numbers in your AI's output:
*   **Pillar 4 (Technicals) = TERRIBLE (e.g., 10/40).** The chart is boring. The RSI is flat. Price isn't moving.
*   **Pillar 1 (Broker/Inst) = PERFECT (e.g., 28/30).** Behind the scenes, the top 3 brokers are sucking up 80% of all supply.

**How to use it:** When you run the `--action=stealth-scan` (or manually spot this divergence in your logs), you have found the "Smart Money" loading their weapons before they pull the trigger. You buy the stock while it is flat, wait a week, and sell it when the technicals finally break out and the retail crowd arrives.

### Cheat Code 2: Defeating the "T+2 Trap" (VWAP)
Because of NEPSE's T+2 settlement rule, if you buy a stock on Sunday, you are locked in until Tuesday or Wednesday. Operators know this, and they weaponize it. If they are ready to dump on Monday, your money is trapped.

Your engine's **VWAP Distribution Risk** is your ultimate shield against this.
*   **The Rule:** ONLY take a momentum trade if the `Broker Profit` is **below +5%**.
*   **The Logic:** If the engine says `Broker Profit: +18%`, the operators have already hit their target. If you buy now, they will dump tomorrow, and you will be stuck in T+2 jail while the price drops 10%. 
*   **The Safety:** If the engine says `Broker Profit: +2%`, you are mathematically safe. The operators have barely made any money yet. They *need* to spend the next 3 to 4 days pumping the stock to reach their 15% goal. This gives your shares plenty of time to settle in your Demat account so you can sell right alongside them at the top!

### Cheat Code 3: 🚨 The 9-Detector Manipulation Radar (NEW!)

Your engine now includes an **advanced manipulation detection system** that runs 9 separate algorithms to identify insider operator games. This is the same type of analysis used by institutional traders who follow the "smart money."

**How to see it:** Run `python tools/paper_trader.py --analyze SYMBOL` and look for the **"MANIPULATION RISK ANALYSIS"** section.

**The 9 Detectors:**

| # | Detector | What It Finds | Red Flag |
|---|----------|---------------|----------|
| 1 | 🔄 **Circular Trading** | Brokers with balanced buy/sell creating fake volume | >20% circular |
| 2 | 🧹 **Wash Trading** | Same broker buying AND selling to itself | >70% match |
| 3 | 📈 **Pump/Dump Phase** | Is the stock in Accumulation, Pump, or Distribution? | Distribution |
| 4 | 🏦 **Broker Concentration** | Top few brokers controlling the stock (HHI Index) | HHI >2500 |
| 5 | 📉 **Price-Volume Divergence** | Big volume but price not moving = absorption | Volume >2x, price <2% |
| 6 | 🕐 **EOD Manipulation** | "Painting the tape" - manipulating close price | Close at 90% of range |
| 7 | 🔗 **Broker Networks** | Coordinated buying by connected brokers | >3 coordinated |
| 8 | 🔓 **Lockup Risk** | Promoter shares about to unlock and dump | <30 days |
| 9 | ❌ **Cross-Trade Detection** | Pre-arranged trades between parties | Unusual patterns |

**Understanding the Output:**

```
🚨 MANIPULATION RISK ANALYSIS (Insider Operator Detection)
----------------------------------------------------------------------

   📊 MANIPULATION RISK SCORE: [███░░░░░░░] 33%
   Severity: MEDIUM
   Trading Status: ✅ SAFE TO TRADE

   📈 OPERATOR PHASE: ✅ CLEAN
      No clear pump/dump pattern detected

   📋 KEY METRICS:
      • Broker Concentration (HHI): 370 ✅ OK
      • Top 3 Brokers Control: 24%
      • Circular Trading: 45% 🚨 FAKE VOLUME!
      • Wash Trading: 🚨 DETECTED
```

**How the Risk Score Affects Your Trade:**

| Risk Score | Severity | Score Penalty | Your Action |
|------------|----------|---------------|-------------|
| ≥70% | 🚨 CRITICAL | -50 points | **DO NOT TRADE** - Paper only |
| 50-70% | ⚠️ HIGH | -30 points | Avoid or tiny position (1%) |
| 30-50% | ⚡ MEDIUM | -15 points | Proceed with caution (2%) |
| <30% | ✅ SAFE | 0 penalty | Normal position sizing (3%) |

**Understanding Operator Phases (CRITICAL KNOWLEDGE):**

1. **ACCUMULATION PHASE** ✅
   - Operators are quietly buying
   - Volume is low, price is flat
   - **Your Action:** This is the BEST time to buy. You're getting in before the pump.

2. **PUMP PHASE** ⚠️
   - Volume exploding, price surging
   - News/rumors spreading on social media
   - **Your Action:** If you're already in, set tight stop. If not, DON'T CHASE.

3. **DISTRIBUTION PHASE** 🚨
   - Operators selling to retail "bag holders"
   - Price still high but volume decreasing
   - **Your Action:** NEVER buy. If holding, EXIT immediately.

4. **CLEAN** ✅
   - No clear manipulation pattern
   - **Your Action:** Analyze fundamentals normally.

**Pro Tip:** When the engine says "ACCUMULATION PHASE" + "Manipulation Risk <30%", you've found a potential goldmine. The operators are loading up, and you can ride alongside them.

***

## CHAPTER 5: Your AI Trading Engine - Complete Command Reference

Your trading bot lives at `nepse_ai_trading/tools/paper_trader.py`. This is your daily weapon. Master every command.

### 🔍 DAILY SCANS (Finding Opportunities)

```bash
# Morning Market Scan - Find today's top opportunities
python tools/paper_trader.py --action=scan --strategy=momentum

# Value Investing Scan - Find undervalued gems for long-term
python tools/paper_trader.py --action=scan --strategy=value

# Sector-Specific Scan (Focus your hunting)
python tools/paper_trader.py --action=scan --strategy=momentum --sector=hydro
python tools/paper_trader.py --action=scan --strategy=value --sector=bank

# Budget-Constrained Scan (Only stocks you can afford)
python tools/paper_trader.py --action=scan --strategy=momentum --max-price=500
```

**Available Sectors:** `bank`, `hydro`, `finance`, `devbank`, `microfinance`, `insurance`, `hotels`, `manufacturing`, `trading`, `others`

### 🕵️ STEALTH RADAR (Finding Smart Money Before the Pump)

```bash
# Detect where operators are quietly accumulating
python tools/paper_trader.py --action=stealth-scan

# Stealth scan specific sector
python tools/paper_trader.py --action=stealth-scan --sector=finance

# Budget-constrained stealth scan
python tools/paper_trader.py --action=stealth-scan --max-price=400
```

**What Stealth Scan Finds:**
- Stocks with LOW Technical Score (price hasn't moved yet)
- Stocks with HIGH Broker Score (heavy institutional buying)
- Stocks with LOW Distribution Risk (brokers not selling)

**Translation:** The operators are loading up quietly. The pump hasn't started. You're early.

### 📊 SINGLE STOCK DEEP ANALYSIS

```bash
# Full analysis of any stock
python tools/paper_trader.py --action=analyze --symbol=NICA

# With specific strategy lens
python tools/paper_trader.py --action=analyze --symbol=NHPC --strategy=momentum
```

**The Output Gives You:**
- Core Scoring + Risk Layers (Broker, Unlock Risk, Fundamentals, Technicals, plus manipulation/news overlays)
- Broker Distribution Risk (Are they about to dump?)
- Exact Entry/Target/Stop-Loss prices with slippage
- Long-term vs Short-term recommendation
- Red flags to watch for

### 📈 PORTFOLIO MANAGEMENT (Strict Holding Rules)

The `--portfolio` command enforces **mathematical discipline** to stop you from over-trading.

#### 🎯 THE THREE IRON RULES

| Rule | Description | Why It Matters |
|------|-------------|----------------|
| **9% MAX** | 3 stocks × 3% each = 9% portfolio | Prevents over-concentration in swing trades |
| **7-DAY HOLD** | No exits during first 7 days | Stops emotional selling; lets trades work |
| **3 EXIT TRIGGERS** | +10% target, -5% stop, 15 days max | Mechanical rules = no emotion |

#### 📊 View Portfolio Status (LIVE Updates!)

```bash
# Quick portfolio check - FETCHES LIVE PRICES automatically!
python tools/paper_trader.py --portfolio
```

**What happens when you run this command:**
1. ✅ Fetches **LIVE LTP** from NEPSE API (during market hours)
2. ✅ Auto-calculates P&L = (LTP - Buy Price) / Buy Price × 100
3. ✅ Updates days held since purchase (trading days only)
4. ✅ Checks exit triggers (+10%, -5%, 15 days)
5. ✅ Shows up/down arrows (↑↓) for price movements

**Output format:**
```
============================================================
📊 PORTFOLIO STATUS (Auto-Updated) (24-Mar)
============================================================

SYMBOL   |    BUY ₹ |   DAYS |   P&L% (LIVE) |   LTP ₹ (LIVE) | STATUS
--------------------------------------------------------------------------------
GVL      |      526 |    1/7 |       +2.8% ↑ |          548 ↑ | 🟢 HOLD (Day 1/7)
PPCL     |      429 |    2/7 |       -1.2% ↓ |          424 ↓ | 🟢 HOLD (Day 2/7)
HPPL     |      522 |    1/7 |       +0.8% ↑ |          526 ↑ | 🟢 HOLD (Day 1/7)
--------------------------------------------------------------------------------
TOTAL: 9.0% allocation | +0.8% P&L | Next review: 30-Mar

⚠️ NO SELL SIGNALS (In hold period)

🔄 AUTO-UPDATE INFO
   ✅ LTP fetched LIVE from NEPSE API
   ✅ P&L calculated automatically
   ✅ Exit signals checked every run
   ✅ Run anytime: Market hours → Live | Closed → Last close

⚠️ EXIT LEVELS
   GVL: +10% target = Rs.579 | -5% stop = Rs.500
```

**Market Hours Handling:**
- **During market (11AM-3PM):** Shows real-time prices ✅
- **After close / weekends:** Shows last closing prices ✅
- **Run anytime:** Command ALWAYS works!

**Daily Monitoring Workflow:**
```bash
10:00 AM: python tools/paper_trader.py --portfolio  # Morning check
12:00 PM: python tools/paper_trader.py --portfolio  # Midday update
3:15 PM:  python tools/paper_trader.py --portfolio  # Close prices
```

#### 🛒 Buy Stocks (With Automatic Limits)

```bash
# Buy specific stocks (3% each, auto-blocked if portfolio full)
python tools/paper_trader.py --buy-picks GVL PPCL HPPL

# Buy top scan picks automatically (runs momentum scan first)
python tools/paper_trader.py --buy-picks
```

**What happens when portfolio is full:**
- New scan results go to **Watchlist only**
- You see: `→ Portfolio FULL (9%) → Watchlist only`
- System blocks any new buys until you sell

#### 🔴 Sell Stocks

```bash
# Sell a position (with exit price)
python tools/paper_trader.py --sell GVL --sell-price 580

# Sell at current market price
python tools/paper_trader.py --sell GVL
```

#### 📋 The 7-Day Hold Rule (No Exceptions!)

This is the **most important rule** to prevent the scanner rotation loop:

| Day | Status | What You Can Do |
|-----|--------|-----------------|
| Day 1-7 | 🟢 HOLD | **NOTHING** - ignore all scanner changes |
| Day 8 | 🟡 REVIEW | Check exit triggers (+10%, -5%) |
| Day 8-15 | 🟡 ACTIVE | Exit triggers apply |
| Day 15+ | ⏰ FORCE EXIT | Review/sell regardless of P&L |

**Example:** You buy GVL on Sunday. On Tuesday, the scanner shows SHEL as better.
- ❌ **WRONG:** Sell GVL, buy SHEL (scanner rotation trap!)
- ✅ **RIGHT:** Keep GVL until Day 7+, add SHEL to watchlist

#### 🎯 Exit Trigger Details

| Trigger | Action | Calculation |
|---------|--------|-------------|
| **+10% Target** | SELL for profit | Buy price × 1.10 |
| **-5% Stop Loss** | SELL to limit loss | Buy price × 0.95 |
| **15-Day Max** | REVIEW position | Force decision |

#### 📁 Data Storage

Portfolio data is saved to `portfolio.json`:

```json
{
  "holdings": [
    {
      "symbol": "GVL",
      "buy_price": 526.0,
      "buy_date": "2026-03-23",
      "allocation": 0.03
    }
  ],
  "watchlist": ["SHEL", "NGPL"],
  "total_allocation": 0.09
}
```

#### 🔄 The Complete Daily Workflow

```bash
# 1. MORNING (11:00 AM) - Check portfolio status
python tools/paper_trader.py --portfolio

# 2. MIDDAY (2:30 PM) - Run momentum scan
python tools/paper_trader.py --scan --strategy=momentum

# 3. IF PORTFOLIO EMPTY - Buy top 3
python tools/paper_trader.py --buy-picks

# 4. IF PORTFOLIO FULL - Just watch
# Scan results automatically added to watchlist

# 5. IF DAY 8+ AND EXIT SIGNAL - Sell
python tools/paper_trader.py --sell GVL --sell-price 580
```

***

## CHAPTER 6: The Core Scoring System Explained

Your engine scores every stock on core pillars, then applies risk/intelligence layers. Understanding these numbers is the difference between gambling and investing.

### 📊 PILLAR 1: Broker/Institutional Score (Max 30 points)

**What It Measures:** Are the big players buying or selling?

| Signal | Score Impact | Meaning |
|--------|--------------|---------|
| Buyer Dominance > 70% | +15 | Institutions are aggressively accumulating |
| Buyer Dominance 55-70% | +8 | Moderate institutional interest |
| Seller Dominance > 55% | -5 to -15 | 🚨 Institutions dumping on retail |
| Distribution Risk HIGH | -10 | Brokers up 15%+, ready to sell |
| Distribution Risk CRITICAL | -15 | 🚨 Active dumping in progress |

**How to Use:**
- Score > 20: Institutions are on your side
- Score < 0: Institutions are your enemy (AVOID)

### 🔓 PILLAR 2: Unlock Risk Score (Max 20 points)

**What It Measures:** Will Mutual Funds or Promoters flood the market with shares?

| Risk | Score Impact | What Happens |
|------|--------------|--------------|
| No Unlock | +20 | Safe - No supply shock coming |
| MF Unlock < 90 days | -5 to -15 | Mutual Funds will dump shares |
| Promoter Unlock Soon | -10 to -20 | Promoters dumping = price crash |

**The Trap:** A stock can look perfect technically, but if 5 Lakhs of locked shares unlock next week, the price will crash regardless of fundamentals.

### 💰 PILLAR 3: Fundamental Score (Max 10-20 points)

**What It Measures:** Is the company actually making money?

| Metric | Good | Bad |
|--------|------|-----|
| PE Ratio | < 15 (Cheap) | > 35 (Overvalued) |
| ROE | > 15% (Profitable) | < 5% (Weak) |
| Book Value | Positive | Negative = INSOLVENT |
| Dividends | Consistent history | Zero = No shareholder returns |

**Strategy Difference:**
- **Momentum:** Fundamentals only 10 points (we care about price action)
- **Value:** Fundamentals 20 points (we care about real value)

### 📈 PILLAR 4: Technical Score (Max 30-40 points)

**What It Measures:** Is the chart saying BUY?

| Signal | Score Impact | Meaning |
|--------|--------------|---------|
| EMA9 > EMA21 (Bullish) | +15 | Uptrend confirmed |
| RSI 50-65 | +10 | Strong momentum, not overbought |
| Volume > 1.5x Average | +10 | Institutional buying volume |
| Golden Cross (recent) | +5 | New uptrend starting |
| Death Cross | -10 | Downtrend - AVOID |
| RSI > 70 | -5 | Overbought - may pull back |

***

## CHAPTER 7: Daily Trading Routine (Copy This Exactly)

### ☀️ MORNING ROUTINE (Before 11:00 AM)

**DO NOT TRADE YET.** Mornings are manipulation time.

1. **9:00 AM - News Check:**
   - Check ShareSansar for overnight announcements
   - Any bonus/dividend news? Any AGM dates?
   - NRB policy changes? (These move the entire market)

2. **10:30 AM - Pre-Open Observation:**
   - Watch the pre-open matching session
   - Note which stocks are gapping up (potential traps)
   - Note which stocks are gapping down (potential opportunities)

### 🌤️ MIDDAY ANALYSIS (12:00 PM - 1:00 PM)

3. **12:30 PM - Run Your First Scan:**
   ```bash
   python tools/paper_trader.py --action=scan --strategy=momentum
   ```
   - Note the top 5 picks
   - Check their Distribution Risk levels
   - Any stocks with CRITICAL risk? Blacklist them.

### 🌅 THE GOLDEN HOUR (2:30 PM - 3:00 PM)

**This is when professionals trade.**

4. **2:30 PM - Final Scan:**
   ```bash
   python tools/paper_trader.py --action=scan --strategy=momentum --max-price=YOUR_BUDGET
   ```
   - The VWAP now includes 3.5 hours of today's trading
   - Distribution Risk is most accurate at this time

5. **2:45 PM - Deep Dive Top Picks:**
   ```bash
   python tools/paper_trader.py --action=analyze --symbol=TOP_PICK
   ```
   - Confirm the score is still > 80
   - Confirm Distribution Risk is LOW or OK
   - Check the suggested Entry/Target/Stop-Loss

6. **2:50 PM - Execute:**
   - Log into TMS
   - Place buy order at suggested Entry Price
   - Set a reminder for Stop-Loss and Target prices

### 🌙 END OF DAY (After 3:00 PM)

7. **3:15 PM - Record Trades:**
   ```bash
   python tools/paper_trader.py --action=buy --symbol=XXXX --quantity=XX --price=XXX
   ```

8. **3:30 PM - Portfolio Review:**
   ```bash
   python tools/paper_trader.py --action=portfolio
   ```
   - Check unrealized P&L
   - Any positions hitting stop-loss? Mark for tomorrow's sell.

***

## CHAPTER 8: Weekly Routines for Wealth Building

### 📅 FRIDAY - Sector Rotation Analysis

Every Friday after market close, run the heatmap:

```bash
# Check which sectors have the most high-scoring stocks
python tools/paper_trader.py --action=scan --strategy=momentum --sector=hydro
python tools/paper_trader.py --action=scan --strategy=momentum --sector=finance
python tools/paper_trader.py --action=scan --strategy=momentum --sector=devbank
python tools/paper_trader.py --action=scan --strategy=momentum --sector=bank
python tools/paper_trader.py --action=scan --strategy=momentum --sector=microfinance
```

**Record Results:**
| Sector | Stocks > 80 Score | Verdict |
|--------|-------------------|---------|
| Hydro | 1 | ❄️ Cold |
| Finance | 4 | 🔥 HOT - Focus here! |
| Bank | 2 | 🌤️ Warming up |

**The Intelligence:** Operators can't pump everything at once. Find where the money is flowing.

### 📅 SATURDAY/SUNDAY - Stealth Hunting

Market is closed. Perfect time to find next week's plays.

```bash
# Find stocks being accumulated quietly
python tools/paper_trader.py --action=stealth-scan

# Deep analyze the stealth candidates
python tools/paper_trader.py --action=analyze --symbol=STEALTH_PICK
```

**What You're Looking For:**
- Broker Score > 80% but Technical Score < 40%
- Distribution Risk = LOW
- Price hasn't moved yet, but big buyers are loading

**Translation:** You found the setup BEFORE the breakout. Buy early, profit when retail FOMO kicks in.

### 📅 MONTHLY - Portfolio Rebalancing

First Sunday of every month:

1. **Review Core Portfolio (60%):**
   ```bash
   python tools/paper_trader.py --action=scan --strategy=value --sector=bank
   ```
   - Any of your holdings dropped below 60 score? Consider rotating.
   - Any new high-scorers emerged? Consider adding.

2. **Review Satellite Performance:**
   - Calculate monthly return on momentum trades
   - If losing money: Tighten stop-losses, reduce position sizes
   - If making money: Maintain discipline, don't get greedy

***

## CHAPTER 9: Reading the AI Output Like a Pro

### 🎯 The Score Breakdown

When you run `--action=analyze`, you get this output:

```
🚀 MOMENTUM STRATEGY (Short-term / Swing Trading)
   🟢 Score: 85/100
   📊 Pillar Scores:
      • Broker/Institutional: 22.0/30
      • Unlock Risk:         20.0/20
      • Fundamentals:        8.0/10
      • Technicals:          35.0/40
```

**How to Read:**
- **Total Score > 85:** 🏆 EXCELLENT - Strong buy signal
- **Total Score 70-84:** 🟢 GOOD - Buy with normal position size
- **Total Score 55-69:** 🟡 AVERAGE - Buy only with tight stop-loss
- **Total Score < 55:** ❌ WEAK - Avoid or short-term only

**Pillar Warning Signs:**
- Broker/Institutional < 0: Institutions are selling. Don't fight them.
- Unlock Risk < 10: Major unlock coming. Price will drop.
- Technicals < 20: No momentum. Wait for breakout.

### 📉 Distribution Risk Interpretation

```
📉 BROKER DISTRIBUTION RISK
   ✅ Risk Level: LOW
   Broker Avg Cost:    Rs. 288.00
   Current LTP:        Rs. 302.00
   Broker Profit:      +4.9%
```

| Risk Level | Broker Profit | Action |
|------------|---------------|--------|
| ✅ LOW | 0-5% | SAFE to buy - operators still accumulating |
| 🟡 MEDIUM | 5-10% | CAUTION - operators near target, may sell soon |
| 🔴 HIGH | 10-15% | RISKY - operators likely taking profits |
| 🚨 CRITICAL | >15% or selling | AVOID - distribution in progress |

### 🎯 Trade Plan Execution

```
🎯 SUGGESTED TRADE PLAN
   Entry Price:   Rs. 306.53 (with 1.5% slippage)
   Target (+10%): Rs. 329.03
   Stop Loss:     Rs. 284.18 (-6.5% with slippage)
```

**Execute Exactly:**
1. **Entry:** Place limit buy at Rs. 306.53 (not market order!)
2. **Target:** Set reminder at Rs. 329 - SELL when hit
3. **Stop-Loss:** Set reminder at Rs. 284 - SELL immediately if hit

**The Math:** Even if only 60% of trades hit target and 40% hit stop-loss:
- 6 winners × 10% = +60%
- 4 losers × -6.5% = -26%
- **Net: +34% return on 10 trades**

***

## CHAPTER 10: Red Flags & When to Override the AI

Your AI is smart, but not omniscient. Here are situations where human judgment overrides:

### 🚨 ALWAYS AVOID (Even if Score > 80)

1. **"Operator Stocks" with Extreme Volume:**
   - If a small hydro suddenly has 10x normal volume, operators are at work
   - High score today = crash tomorrow
   - Rule: Avoid stocks where today's volume > 5x the 20-day average

2. **News-Driven Gaps:**
   - Stock opened +5% on bonus announcement
   - AI can't see morning gaps, only yesterday's close
   - Rule: Never buy a stock that gapped up > 3% at open

3. **SEBON/NRB Announcements:**
   - Regulatory news moves the entire market
   - AI doesn't read news
   - Rule: On policy days, reduce all positions or stay cash

4. **Rights Issue Announcement:**
   - Stock will drop on ex-date as supply increases
   - AI doesn't track corporate actions
   - Rule: Sell before ex-rights date

### 🟡 USE SMALLER POSITION (50% Normal)

1. **Score 70-80 with MEDIUM Distribution Risk:**
   - Operators are getting close to profit-taking
   - Trade, but with half your normal position size

2. **RSI > 65 (Approaching Overbought):**
   - Momentum is strong but may reverse
   - Tighter stop-loss, smaller position

3. **Multiple Stocks in Same Sector:**
   - Don't put 80% of capital in 4 hydro stocks
   - Diversify: max 2 stocks per sector

***

## CHAPTER 11: The Path to Rs. 10 Lakhs Profit

### Starting Capital: Rs. 5,00,000

**Month 1-3: Learning Phase**
- Trade with 25% of capital only (Rs. 1,25,000)
- Max 2 positions at a time
- Goal: Understand the system, not make money
- Expected: Breakeven or small profit

**Month 4-6: Confidence Phase**
- Trade with 50% of capital (Rs. 2,50,000)
- Max 4 positions at a time
- Goal: 5% monthly return
- Expected: Rs. 37,500 profit (7.5% return on total capital)

**Month 7-12: Full Deployment**
- Trade with 80% of capital (Rs. 4,00,000)
- Use full 60/40 Core-Satellite split
- Goal: 7% monthly return
- Expected: Rs. 168,000 profit (6 months × 7% × 4L)

**End of Year 1:**
- Starting: Rs. 5,00,000
- Target: Rs. 7,05,500 (+41% annual return)

**Year 2-3: Compounding**
- Reinvest all profits
- Same discipline, larger positions
- Year 2 End: Rs. 9,94,755
- Year 3 End: Rs. 14,02,604 (You've nearly tripled your money)

### The Compound Interest Formula

```
Future Value = Present Value × (1 + Monthly Return)^Months

With 7% monthly returns:
Rs. 5,00,000 × (1.07)^36 = Rs. 57,53,389 (After 3 years)
```

**Reality Check:** 7% monthly is aggressive. Even 4% monthly:
```
Rs. 5,00,000 × (1.04)^36 = Rs. 20,51,562 (After 3 years)
```

That's still 4x your money using disciplined algorithmic trading.

***

## Quick Reference Card (Print This!)

```
╔══════════════════════════════════════════════════════════════════╗
║           NEPSE AI TRADER - DAILY QUICK REFERENCE               ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  📍 SCAN COMMANDS:                                               ║
║  • Momentum: --action=scan --strategy=momentum                   ║
║  • Value:    --action=scan --strategy=value                      ║
║  • Stealth:  --action=stealth-scan                               ║
║  • Analyze:  --action=analyze --symbol=XXXX                      ║
║                                                                  ║
║  📊 SCORE INTERPRETATION:                                        ║
║  • 85+ = 🏆 EXCELLENT (Full position)                            ║
║  • 70-84 = 🟢 GOOD (Normal position)                             ║
║  • 55-69 = 🟡 RISKY (Half position + tight stop)                 ║
║  • <55 = ❌ AVOID                                                ║
║                                                                  ║
║  📉 DISTRIBUTION RISK:                                           ║
║  • LOW (0-5% profit) = ✅ SAFE to buy                            ║
║  • MEDIUM (5-10%) = ⚠️ CAUTION                                   ║
║  • HIGH (10-15%) = 🔴 RISKY                                      ║
║  • CRITICAL (>15%) = 🚨 DO NOT BUY                               ║
║                                                                  ║
║  ⏰ TRADING HOURS:                                               ║
║  • 11:00-12:00 = ❌ NEVER BUY (Morning trap)                     ║
║  • 12:00-14:00 = 👀 OBSERVE ONLY                                 ║
║  • 14:30-15:00 = ✅ GOLDEN HOUR (Execute here)                   ║
║                                                                  ║
║  💰 POSITION SIZING:                                             ║
║  • Max 20% capital per stock                                     ║
║  • Max 2 stocks per sector                                       ║
║  • 60% Core (Value) / 40% Satellite (Momentum)                   ║
║                                                                  ║
║  🛑 STOP-LOSS RULES:                                             ║
║  • Momentum: -6.5% (with slippage)                               ║
║  • Value: -8% (with slippage)                                    ║
║  • EXECUTE IMMEDIATELY when hit. No exceptions.                  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

***

## Final Words: The Mindset of a Winning Trader

1. **You are not gambling.** You are executing a mathematical system with proven edge.

2. **Losses are tuition.** Every stop-loss hit teaches you something. Log it, learn from it, move on.

3. **Discipline beats intelligence.** A mediocre strategy executed perfectly beats a perfect strategy executed emotionally.

4. **The market will always be there.** Missing one trade doesn't matter. Protecting your capital does.

5. **Compound interest is your weapon.** Small consistent gains beat occasional home runs.

Your AI engine removes emotion from stock selection. Now you must remove emotion from execution.

**Happy Trading. May the algorithms be ever in your favor.** 🚀
