# 📊 Position Advisor - Hold or Sell Analyzer

## 🎯 Purpose

Your friends bought stocks at various times (1 week to 1 year ago) and need to know:
**"Should I HOLD or SELL my position now?"**

This analyzer helps existing stockholders make informed decisions without reading charts.

---

## 🚀 Usage

### Basic Usage (with buy price only)
```bash
cd nepse_ai_trading/tools
python paper_trader.py --hold-or-sell NABIL --buy-price 500
```

### With Buy Date (more accurate analysis)
```bash
python paper_trader.py --hold-or-sell NABIL --buy-price 500 --buy-date 2025-12-01
```

---

## 📊 Output Example

```
======================================================================
📊 POSITION ANALYSIS: NABIL
   You bought at Rs. 500.00 on 2025-12-01
   Holding for ~115 days (3-12 months)
======================================================================

💰 YOUR POSITION
----------------------------------------
   Buy Price:     Rs. 500.00
   Current Price: Rs. 539.00
   P/L:           +7.8% (Rs. +39.00/share) 📈

   If 100 shares: Rs. 50,000 → Rs. 53,900 (+Rs. 3,900)

📈 TECHNICAL POSITION
----------------------------------------
   Trend:         🟢 BULLISH (strength: 95%)
   Momentum:      RSI 70 - NEUTRAL ➖
   EMA Position:  Above 4/4 EMAs ✅ (Perfect alignment)
   Volume:        🔵 ACCUMULATION

🛡️ SUPPORT & RESISTANCE
----------------------------------------
   Nearest Support:     Rs. 517.50 (4.0% below)
   Nearest Resistance:  Rs. 555.00 (3.0% above)

   ✅ YOUR ENTRY ADVANTAGE:
   └── Your entry (Rs. 500.00) is BELOW support (Rs. 517.50)
   └── Even if price drops, your entry is protected!

📊 POSITION HEALTH SCORE
----------------------------------------
   Score: 83/100 [████████████████░░░░] Grade: 🟢 A

======================================================================
💪 VERDICT: STRONG HOLD - Excellent position!
======================================================================

💡 RECOMMENDED ACTIONS:
   1. This is a strong position - let your winners run!
   2. Trail stop to protect gains but give room to grow

🎯 YOUR TRADE PLAN:
   🛑 STOP LOSS:  Rs. 475.00
   🎯 TARGET 1:   Rs. 555.00 (+3.0%)
   🎯 TARGET 2:   Rs. 562.00 (+4.3%)

🚨 EXIT IMMEDIATELY IF:
   • Price closes below Rs. 475.00
   • RSI drops below 40 (weak momentum)
   • Heavy volume on a red day (distribution)
======================================================================
```

---

## 🚦 Understanding the Verdicts

| Verdict | Score | P/L | What It Means | Action |
|---------|-------|-----|---------------|--------|
| 💪 STRONG HOLD | 75+ | Any | Excellent position | Let winners run! |
| 🟢 HOLD | 55-75 | Any | Position healthy | Continue holding |
| 🟡 HOLD CAUTIOUSLY | 35-55 | Any | Watch closely | Tighten stop |
| 🟠 BOOK PARTIAL | 35-50 | Profit >10% | Secure gains | Sell 50% |
| 🔵 AVERAGE DOWN | 45+ | Loss -5% to -15% | Consider adding | Buy more (if confident) |
| 🔴 EXIT | <35 | Any | Trend broken | Cut position |
| 🚨 URGENT EXIT | <25 | Loss >-10% | Position deteriorating | Exit immediately |

---

## 📊 Health Score Breakdown

The Position Health Score (0-100) is calculated from 6 factors:

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| Trend Alignment | 25% | Price vs EMAs (9/21/50/200) |
| Momentum | 20% | RSI position + direction |
| Support Proximity | 20% | Distance from key support |
| Volume Health | 15% | Accumulation vs distribution |
| Profit Buffer | 10% | Unrealized gain cushion |
| Risk/Reward | 10% | Upside vs downside potential |

**Grades:**
- **A** (80-100): Excellent
- **B** (65-79): Good
- **C** (50-64): Fair
- **D** (35-49): Poor
- **F** (<35): Exit

---

## ⏰ Holding Period Matters

The analyzer gives different advice based on how long you've held:

### Very Short Term (< 1 week)
- **Psychology**: Quick scalp
- **Stop**: Tight (1-3% below entry)
- **Advice**: Exit if momentum fades quickly

### Short Term (1-2 weeks)
- **Psychology**: Quick profit
- **Stop**: Tight (3-5% below entry)
- **Advice**: Trail tightly on big gains

### Medium Term (2 weeks - 3 months)
- **Psychology**: Swing trader
- **Stop**: Moderate (5-7% below entry)
- **Advice**: Focus on trend, ignore daily noise

### Long Term (3-12 months)
- **Psychology**: Investor
- **Stop**: Wide (10-15% below entry)
- **Advice**: Use major support levels, be patient

### Very Long Term (1+ year)
- **Psychology**: Long-term investor
- **Stop**: Very wide (at strong support)
- **Advice**: Focus on fundamentals, rebalance if needed

---

## 📋 Real-World Examples

### Example 1: Long-Term Winner
```
Stock: NABIL
Bought: Rs. 400 on 2025-06-01
Current: Rs. 539 (+35%)
Verdict: 💪 STRONG HOLD
Action: Trail stop to Rs. 440 (lock 10% profit), let it run
```

### Example 2: Short-Term Small Loss
```
Stock: NABIL
Bought: Rs. 560 on 2026-03-15
Current: Rs. 539 (-4%)
Verdict: 🟢 HOLD
Action: Set stop at Rs. 503, give it time to recover
```

### Example 3: IPO Big Winner
```
Stock: SOHL
Bought: Rs. 400 on 2026-03-19
Current: Rs. 643 (+61%)
Verdict: 🟢 HOLD with WARNING
Action: Trail tightly, +61% in 1 week is huge - consider partial booking
```

### Example 4: Bearish Position (hypothetical)
```
Stock: XYZ
Bought: Rs. 100 on 2026-01-01
Current: Rs. 80 (-20%)
Trend: BEARISH, below all EMAs
Verdict: 🔴 EXIT
Action: Cut loss at -20% before it gets worse
```

---

## 🔍 Key Features Explained

### 1. Entry vs Support Analysis
The analyzer compares YOUR entry price to current support:

- **Entry BELOW support** ✅: "Your entry is protected - even if price drops to support, you're still in profit"
- **Entry ABOVE support** ⚠️: "Price has room to drop below your entry before hitting support"

### 2. Risk/Reward from Current Price
Shows what happens if you continue holding:
- **Risk**: How much you lose if price drops to support
- **Reward**: How much you gain if price hits resistance
- **R:R Ratio**: Reward ÷ Risk (want > 1.5)

### 3. Weekly Checklist
Things to monitor each week:
- Is price still above 21 EMA?
- Is RSI still above 40?
- Is volume healthy (no distribution)?

If all YES → Continue holding
If any NO → Reassess position

---

## 🤖 Programmatic Usage

```python
from intelligence.position_advisor import PositionAdvisor

advisor = PositionAdvisor()

# Full analysis
result = advisor.analyze(
    symbol="NABIL",
    buy_price=500,
    buy_date="2025-12-01"  # Optional
)
print(result.format_report())

# Quick check (one line)
verdict = advisor.quick_check("NABIL", buy_price=500)
print(verdict)  # → "💪 STRONG HOLD | P/L: +7.8% | Stop: Rs. 475.00"

# Access raw data
print(f"Health Score: {result.health_score}")  # → 83
print(f"Grade: {result.health_grade}")  # → A
print(f"Verdict: {result.verdict}")  # → Verdict.STRONG_HOLD
print(f"Stop Loss: {result.stop_loss}")  # → 475.0
```

---

## ⚠️ Important Notes

1. **This is technical analysis only** - doesn't consider fundamentals
2. **Run weekly** - conditions change, run analysis every week
3. **Don't ignore the stop loss** - capital preservation is key
4. **IPOs need special handling** - limited data means less reliable analysis
5. **Your psychology matters** - don't hold if you can't sleep at night

---

## 📝 Files

- **Analyzer**: `nepse_ai_trading/intelligence/position_advisor.py`
- **CLI Integration**: `nepse_ai_trading/tools/paper_trader.py`
- **This Guide**: `POSITION_ADVISOR_GUIDE.md`

---

## 🔗 Related Tools

| Tool | Command | Use Case |
|------|---------|----------|
| **Position Advisor** | `--hold-or-sell NABIL --buy-price 500` | Should I hold or sell? |
| **IPO Exit Analyzer** | `--ipo-exit SOHL` | When to sell newly listed IPO? |
| **Signal Generator** | `--signal NABIL` | Should I buy this stock? |
| **Trade Calendar** | `--calendar` | Which stocks to buy when? |

---

**Built by**: NEPSE AI Trading Bot  
**Date**: March 2026  
**Tested with**: NABIL, SOHL, and various scenarios
