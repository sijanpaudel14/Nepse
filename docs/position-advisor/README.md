# 🎯 Position Advisor Documentation

The **Position Advisor** helps you decide **whether to HOLD or SELL** stocks you already own. Whether you bought 1 week ago or 1 year ago, it gives personalized advice based on your entry price and holding period.

---

## 📚 Documentation Files

### 1. [POSITION_ADVISOR_GUIDE.md](./POSITION_ADVISOR_GUIDE.md)
**What it covers:**
- How to use the `--hold-or-sell` command
- Understanding the Health Score (0-100)
- Reading verdicts (STRONG_HOLD to URGENT_EXIT)
- Real-world examples for different holding periods

**Start here if:** You're new to the Position Advisor

---

## 🚀 Quick Start

### Basic Usage
```bash
# You bought NABIL at Rs. 500, should you hold or sell?
python paper_trader.py --hold-or-sell NABIL --buy-price 500

# Include buy date for holding period context
python paper_trader.py --hold-or-sell NABIL --buy-price 500 --buy-date 2025-12-01
```

### What You'll Get
```
📊 POSITION ANALYSIS: NABIL
   You bought at Rs. 500.00 (~3 months ago)
══════════════════════════════════════════════════════════

💰 YOUR POSITION
   Buy Price:     Rs. 500.00
   Current Price: Rs. 538.00
   P/L:           +7.6% (Rs. +38.00/share)

══════════════════════════════════════════════════════════
🟢 VERDICT: HOLD - TRAIL YOUR STOP
══════════════════════════════════════════════════════════

💡 RECOMMENDED ACTIONS:
   1. Set stop loss at Rs. 495 (just below your entry, -1% risk)
   2. Target: Rs. 580 (+7.8% from here)
```

---

## 🎯 When to Use This Tool

| Scenario | Use Position Advisor? |
|----------|------------------------|
| Bought stock 1 week ago | ✅ YES |
| Bought stock 3 months ago | ✅ YES |
| Bought stock 1 year ago | ✅ YES |
| Friend asks "should I sell?" | ✅ YES - Ask their buy price |
| Stock just listed (IPO) | ❌ NO - Use IPO Exit Analyzer |
| Looking for new entries | ❌ NO - Use `--signal` |

---

## 🧮 How It Works: The Health Score

The Position Advisor calculates a **Health Score (0-100)** from 6 factors:

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| **Trend Alignment** | 25% | Price vs EMAs (9/21/50/200) |
| **Momentum** | 20% | RSI position + direction |
| **Support Proximity** | 20% | Distance from key support |
| **Volume Health** | 15% | Accumulation vs distribution |
| **Profit Buffer** | 10% | Unrealized gain cushion |
| **Risk/Reward** | 10% | Current R:R ratio |

### Example Calculation
```
Trend Alignment:  18/25 (above 20/50 EMA)
Momentum:         12/20 (RSI: 52, neutral)
Support:          15/20 (support nearby)
Volume:           12/15 (healthy volume)
Profit Buffer:     8/10 (+7.6% gain)
Risk/Reward:       8/10 (1:1.5 R:R)
------------------------
TOTAL:            73/100 → HOLD
```

---

## 🚦 The 7 Verdicts

| Score | Verdict | Meaning | Action |
|-------|---------|---------|--------|
| **75-100** | STRONG_HOLD | Winner, let it run | Trail stop, ride trend |
| **55-75** | HOLD | Healthy position | Continue holding |
| **45-55** | HOLD_CAUTIOUSLY | Weakening | Tighten stop, watch |
| **35-45** (profit) | BOOK_PARTIAL | Take some off | Sell 50%, hold rest |
| **35-45** (loss) | AVERAGE_DOWN | Good setup | Consider adding |
| **20-35** | EXIT | Deteriorated | Cut position |
| **0-20** | URGENT_EXIT | Critical | Exit immediately |

---

## 🔍 Understanding the Output

### Section 1: Your Position
```
💰 YOUR POSITION
────────────────────────────────────────
   Buy Price:     Rs. 500.00
   Current Price: Rs. 538.00
   P/L:           +7.6% (Rs. +38.00/share)
   
   If 100 shares: Rs. 50,000 → Rs. 53,800 (+Rs. 3,800)
```
Shows your P/L in both percentage and rupees.

### Section 2: Technical Position
```
📈 TECHNICAL POSITION
────────────────────────────────────────
   Trend:         BULLISH (above 20/50 EMA)
   Momentum:      NEUTRAL (RSI: 52)
   Support:       Rs. 510 (2.0% below entry)
   Resistance:    Rs. 580 (52-week high)
   
   Position Score: 73/100 (STRONG)
```
Shows where you stand technically.

### Section 3: Risk/Reward Analysis
```
⚖️ RISK/REWARD FROM HERE
────────────────────────────────────────
   If price drops to support (Rs. 510):  -5.2%
   If price hits resistance (Rs. 580):   +7.8%
   Risk/Reward: 1:1.5 ✅
   
   Your Entry Advantage:
   └── Entry (Rs. 500) is BELOW support (Rs. 510)
   └── Even if price drops, your entry is protected!
```
Shows your risk from CURRENT price (not entry).

### Section 4: Action Plan
```
💡 RECOMMENDED ACTIONS:
   1. Set stop loss at Rs. 495 (just below your entry)
   2. If price hits Rs. 560: Move stop to Rs. 520
   3. Target: Rs. 580 (+7.8% from here)

🛑 EXIT IMMEDIATELY IF:
   • Price closes below Rs. 495 (stop loss)
   • RSI drops below 40 (momentum loss)
```
Clear, actionable steps.

---

## 🕐 Holding Period Context

The advisor gives different advice based on how long you've held:

### Very Short Term (< 1 week)
- **Focus:** Quick profit (5-7%)
- **Stop Loss:** Tight (below 9 EMA)
- **Exit Trigger:** RSI overbought reversal

### Short Term (1 week - 1 month)
- **Focus:** Swing target (10-15%)
- **Stop Loss:** Below 20 EMA
- **Exit Trigger:** Trend break

### Medium Term (1-3 months)
- **Focus:** Trend continuation (15-25%)
- **Stop Loss:** Below 50 EMA
- **Exit Trigger:** Swing structure break

### Long Term (3+ months)
- **Focus:** Major resistance (30%+)
- **Stop Loss:** Below 200 EMA or major support
- **Exit Trigger:** Trend reversal

---

## 💡 Pro Tips

### 1. **Use Your Entry as Reference**
The advisor shows if your entry price is protected by support:
```
✅ Entry (Rs. 500) is BELOW support (Rs. 510)
   → You have a cushion!

⚠️ Entry (Rs. 550) is ABOVE support (Rs. 510)
   → You're vulnerable to drop
```

### 2. **Tighten Stops on Winners**
If you're up 20%+, move stop loss to at least breakeven to protect gains.

### 3. **Be Patient with Losers (If Healthy)**
If score is 55+ but you're down 5%, the position may recover. Give it time.

### 4. **Book Partial on Weak Winners**
If score drops to 40-50 but you're up 10%, consider selling 50% to lock gains.

### 5. **Average Down Carefully**
Only average down if:
- Score is 50+ (technically healthy)
- Clear support nearby
- You have conviction in the stock

---

## ⚠️ Common Questions

### Q: What if I don't know my buy date?
**A:** Just omit `--buy-date`. The advisor will still work but won't show holding period context.

### Q: Can I use this for IPOs?
**A:** Yes, but for newly listed stocks (< 30 days), the **IPO Exit Analyzer** is better designed for that phase.

### Q: What if I have multiple entries?
**A:** Use your **average buy price**. Example:
- Bought 100 @ Rs. 500
- Bought 50 @ Rs. 550
- Average: (100×500 + 50×550) / 150 = Rs. 516.67

### Q: Should I always follow the verdict?
**A:** The verdict is a **guideline**, not a rule. Consider:
- Your personal risk tolerance
- Portfolio allocation
- Tax implications (if applicable)
- Better opportunities elsewhere

### Q: How often should I check?
- **Very short term (<1 week):** Daily
- **Short term (1 week-1 month):** Every 2-3 days
- **Medium term (1-3 months):** Weekly
- **Long term (3+ months):** Bi-weekly

---

## 🔗 Related Tools

- **IPO Exit Analyzer** (`--ipo-exit`) - For newly listed stocks
- **Signal Generator** (`--signal`) - For finding new entries
- **Calendar** (`--calendar`) - For swing trade opportunities

---

## 📊 Real-World Scenarios

### Scenario 1: Short-Term Winner
```bash
python paper_trader.py --hold-or-sell NABIL --buy-price 500 --buy-date 2026-03-15
```
**Result:** NABIL @ Rs. 530 (+6% in 1 week), RSI: 68 → **BOOK_PARTIAL** (Quick profit, RSI overbought)

### Scenario 2: Medium-Term Loser
```bash
python paper_trader.py --hold-or-sell NABIL --buy-price 550 --buy-date 2026-01-15
```
**Result:** NABIL @ Rs. 520 (-5.5% in 2 months), below 50 EMA → **EXIT** (Trend broken, cut loss)

### Scenario 3: Long-Term Winner
```bash
python paper_trader.py --hold-or-sell NABIL --buy-price 400 --buy-date 2025-07-01
```
**Result:** NABIL @ Rs. 530 (+32.5% in 8 months), strong uptrend → **STRONG_HOLD** (Let winners run)

---

**Need help?** Read the detailed guide [POSITION_ADVISOR_GUIDE.md](./POSITION_ADVISOR_GUIDE.md) or check main [docs/README.md](../README.md).
