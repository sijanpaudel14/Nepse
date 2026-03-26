# 📈 IPO Exit Analyzer - Know When to Sell Newly Listed Stocks

## 🎯 Purpose
For newly listed IPO stocks, it's hard to know when to sell if you don't read charts. This analyzer automatically detects exit signals by analyzing:
- Volume trends (initial excitement vs decay)
- Broker flow (who's buying/selling)
- Price patterns (uptrend vs breakdown)

## 🚀 Usage

### Simple Command
```bash
cd nepse_ai_trading/tools
python paper_trader.py --ipo-exit SOHL
```

### Output Example
```
============================================================
📊 IPO EXIT ANALYSIS: SOHL
   Listed 8 trading days ago
============================================================

💰 CURRENT STATUS
----------------------------------------
   Current Price:  Rs. 642.90
   Listing Price:  Rs. 330.00
   Gain/Loss:      +94.8%

📈 VOLUME TREND (Last 8 Days)
----------------------------------------
   2026-03-19:      1,850 █
   2026-03-22:      3,690 ███
   2026-03-23:     10,180 █████████
   2026-03-24:      9,590 ████████
   2026-03-25:     22,360 ████████████████████ ← SPIKE!

   Trend: SPIKE
   🚨 VOLUME SPIKE after quiet period

🔍 WHO'S TRADING? (1 Week)
----------------------------------------
   Top Buyers:
      • Roadshow securities: +29,470 shares
      • Naasa Securities: +10,950 shares

   Top Sellers:
      • Naasa Securities: -6,120 shares
      • Dipshikha Dhitopatra: -5,580 shares

============================================================
🟡 VERDICT: WATCH CLOSELY
============================================================

💡 ACTION: Hold but monitor daily. Set stop loss at Day 2 low.
🛑 STOP LOSS: Rs. 336.60
```

## 📊 Understanding the Verdicts

| Verdict | Score | What It Means | Action |
|---------|-------|---------------|--------|
| 🟢 STRONG HOLD | < 15 | Strong momentum, institutions buying | Hold position |
| 🟢 HOLD | < 15 | Normal conditions | Hold position |
| 🟡 WATCH | 15-30 | Early warning signs (volume spike or selling) | Monitor daily, set stop loss |
| 🟠 CONSIDER PARTIAL SELL | 30-50 | Distribution detected | Sell 50%, hold rest |
| 🔴 SELL | 50-70 | Clear exit signals | Sell entire position |
| 🚨 URGENT SELL | 70+ | Strong distribution, breakdown | Exit immediately |

## 🔍 Exit Signals Detected

### 1. Volume Decay (20 points)
- **What**: 3+ days of declining volume
- **Why bad**: Initial IPO excitement is fading
- **Example**: Day 1: 50k → Day 2: 30k → Day 3: 15k

### 2. Distribution Day (25 points)
- **What**: High volume + price drop
- **Why bad**: Smart money is exiting
- **Example**: Volume spikes 2x but price drops

### 3. Broker Flow Flip (25 points)
- **What**: Institutions selling, retail buying
- **Why bad**: Weak hands replacing strong hands
- **Signals**: 
  - Institutional selling > 60%
  - Retail buying > 50%

### 4. Listing Gain Exhaustion (20 points)
- **What**: Price breaks below Day 2 low
- **Why bad**: Uptrend broken, listing pump over
- **Example**: Listed at Rs.330, Day 2 low Rs.336, now Rs.320

### 5. Volume Spike After Quiet (15 points)
- **What**: Sudden volume after quiet period
- **Why warning**: Could be smart money exiting
- **Example**: Volume 5k for 3 days, then 25k spike

## 💡 How to Use for SOHL Example

**SOHL Analysis (8 days listed):**
- ✅ **Current**: Rs. 642.90 (+95% from listing)
- 🚨 **Warning**: Volume spike (22,360 vs avg ~8,000)
- 🟡 **Broker Flow**: Neutral (balanced)
- ✅ **Price**: Still above Day 2 low (Rs. 336.60)

**Verdict: WATCH CLOSELY**

**What to do:**
1. Set stop loss at Rs. 336.60 (Day 2 low)
2. Monitor daily volume
3. If volume keeps spiking with selling, exit
4. Consider booking 50% profit (+95% is huge!)

## 🤖 Programmatic Usage

```python
from intelligence.ipo_exit_analyzer import IPOExitAnalyzer

analyzer = IPOExitAnalyzer()

# Full analysis
result = analyzer.analyze('SOHL')
print(result.format_report())

# Quick check (just verdict)
verdict = analyzer.quick_check('SOHL')
print(verdict)  # → "🟡 WATCH CLOSELY"

# Access raw data
print(f"Exit Signal: {result.exit_signal}")  # → watch
print(f"Score: {result.score}")  # → 20
print(f"Volume Trend: {result.volume.trend}")  # → spike
```

## ⚠️ Important Notes

1. **Works for newly listed stocks only** (< 30 days)
2. **Requires ShareHub API** for broker flow data
3. **Day 2 low is critical** - it's your safety net
4. **Volume spikes are warnings** - not always bad, but watch closely
5. **Big gains need protection** - use trailing stop loss

## 🎓 Why This Works

IPO stocks follow predictable patterns:
- **Day 1-2**: Listing excitement, high volume
- **Day 3-7**: Consolidation, volume normalizes
- **Day 8-14**: Either breakout or distribution
- **Day 15+**: Becomes normal stock

The analyzer detects when smart money is exiting (distribution) before retail realizes it.

## 📝 Files

- **Analyzer**: `nepse_ai_trading/intelligence/ipo_exit_analyzer.py`
- **CLI Integration**: `nepse_ai_trading/tools/paper_trader.py` (line 3707-3718)
- **This Guide**: `IPO_EXIT_GUIDE.md`

---

**Built by**: NEPSE AI Trading Bot  
**Date**: March 26, 2026  
**Tested with**: SOHL (8 days, +95% gain)
