# 📊 IPO Exit Analyzer Documentation

The **IPO Exit Analyzer** helps you decide **when to sell** newly listed IPO stocks by analyzing volume patterns, broker flows, and price behavior.

---

## 📚 Documentation Files

### 1. [IPO_EXIT_GUIDE.md](./IPO_EXIT_GUIDE.md)
**What it covers:**
- How to use the `--ipo-exit` command
- Understanding the 5 exit signals
- Reading the verdict (STRONG_HOLD to URGENT_SELL)
- Real-world examples (SOHL case study)

**Start here if:** You're new to the IPO Exit Analyzer

---

### 2. [BROKER_FLOW_EXPLAINED.md](./BROKER_FLOW_EXPLAINED.md)
**What it covers:**
- Understanding Net Flow (why it's 0, +5000, -5000)
- Interpreting broker flow for IPOs
- Reading institutional vs retail activity
- Advanced broker flow flip signals

**Read this if:** You want to understand the "🔍 WHO'S TRADING?" section

---

## 🚀 Quick Start

### Basic Usage
```bash
# Analyze IPO exit signals for SOHL
python paper_trader.py --ipo-exit SOHL
```

### What You'll Get
```
📊 IPO EXIT ANALYSIS: SOHL
============================================================
🟡 VERDICT: WATCH CLOSELY
============================================================

💡 ACTION: Hold but monitor daily. Set stop loss at Day 2 low.
🛑 STOP LOSS: Rs. 336.60

📋 REASONS:
   • Volume spike detected - potential distribution
   • Price still in uptrend
```

---

## 🎯 When to Use This Tool

| Scenario | Use IPO Exit Analyzer? |
|----------|------------------------|
| Stock listed < 30 days ago | ✅ YES - Perfect use case |
| Stock sitting on big gain (50%+) | ✅ YES - Know when to exit |
| Stock you bought months ago | ❌ NO - Use Position Advisor instead |
| Looking for new stocks to buy | ❌ NO - Use `--signal` instead |

---

## 📊 The 5 Exit Signals (Weighted Scoring)

| Signal | Weight | What It Detects |
|--------|--------|-----------------|
| Volume Decay | 20 pts | 3+ days declining volume |
| Distribution Day | 25 pts | High volume + price down |
| Broker Flow Flip | 25 pts | Smart money selling |
| Listing Gain Exhaustion | 20 pts | Price breaks Day 2 low |
| Volume Spike | 15 pts | Sudden volume surge |

**Total Score: 0-100**
- 0-25: STRONG_HOLD
- 26-40: HOLD  
- 41-55: WATCH
- 56-70: CONSIDER_PARTIAL
- 71-85: SELL
- 86-100: URGENT_SELL

---

## 🧠 Understanding the Output

### Section 1: Current Status
```
💰 CURRENT STATUS
----------------------------------------
   Current Price:  Rs. 707.10
   Listing Price:  Rs. 330.00
   Gain/Loss:      +114.3%
```
Shows your P/L if you bought at listing.

### Section 2: Volume Trend
```
📈 VOLUME TREND (Last 8 Days)
----------------------------------------
   2026-03-25:     22,360 ████████████████████ ← SPIKE!

   Trend: SPIKE
   🚨 VOLUME SPIKE after quiet period
```
Detects volume patterns (decay, spike, distribution).

### Section 3: Broker Flow
```
🔍 WHO'S TRADING? (1 Week)
----------------------------------------
   Net Flow: +0 shares

   Flow Type: NEUTRAL
   🟡 Neutral flow - Balanced buying and selling
```
Shows if smart money is accumulating or distributing.

### Section 4: Price Pattern
```
📉 PRICE PATTERN
----------------------------------------
   Day 2 Low:    Rs. 336.60
   Buffer:       110.0% above Day 2 low
   Trend:        UPTREND
```
Checks if price is still trending up or breaking down.

---

## ⚠️ Common Questions

### Q: What if "Insufficient data" error?
**A:** Stock needs at least 7 days of trading. If just listed, check back in a few days.

### Q: Net Flow = 0, is that good?
**A:** It means balanced (no accumulation/distribution). For a stock up 100%+, it's a **WARNING** - you'd expect some profit-taking. See [BROKER_FLOW_EXPLAINED.md](./BROKER_FLOW_EXPLAINED.md).

### Q: Should I sell if verdict is "WATCH"?
**A:** No! "WATCH" means monitor daily but don't exit yet. Set stop loss and watch for changes.

### Q: What's the difference vs Position Advisor?
**A:** 
- **IPO Exit**: For stocks < 30 days old
- **Position Advisor**: For stocks you bought weeks/months ago

---

## 🔗 Related Tools

- **Position Advisor** (`--hold-or-sell`) - For existing positions
- **Signal Generator** (`--signal`) - For finding new entries
- **Calendar** (`--calendar`) - For swing trade opportunities

---

## 💡 Pro Tips

1. **Check daily during first 10 days** - IPO behavior is most volatile early
2. **Set stop loss at Day 2 low** - Classic support level
3. **Watch for flow changes** - Neutral → Distribution = Exit signal
4. **Book profits at 50-100% gain** - IPO pumps don't last forever
5. **Volume spike = Decision point** - Monitor closely for next 2-3 days

---

**Need help?** Read the detailed guides above or check examples in the main [docs/README.md](../README.md).
