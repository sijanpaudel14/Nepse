# 🔍 Understanding Broker Flow in IPO Exit Analyzer

## What is Broker Flow?

**Broker Flow** shows WHO is buying and selling a stock by tracking individual broker transactions. This reveals whether **institutions** (smart money) or **retail** (regular investors) are in control.

---

## 📊 Key Metrics Explained

### 1. Net Flow
```
Net Flow = Total Buy Quantity - Total Sell Quantity
```

**Example from SOHL:**
```
Net Flow: +0 shares
```

**What This Means:**
- **+0 shares** = Balanced (equal buying and selling)
- **+5,000 shares** = Accumulation (more buying than selling)
- **-5,000 shares** = Distribution (more selling than buying)

---

## 🚦 Interpreting Net Flow for IPOs

| Net Flow | Meaning | IPO Context | Signal |
|----------|---------|-------------|--------|
| **> +3000** | Strong Accumulation | Institutions loading up | 🟢 **BULLISH** - Hold |
| **0 to +3000** | Mild Accumulation | Balanced interest | 🟢 **NEUTRAL-BULLISH** |
| **0** | Perfectly Balanced | Consolidation | 🟡 **NEUTRAL** - Watch |
| **0 to -3000** | Mild Distribution | Some profit-taking | 🟠 **NEUTRAL-BEARISH** |
| **< -3000** | Strong Distribution | Smart money exiting | 🔴 **BEARISH** - Sell |

---

## 🎯 SOHL Case Study

**Scenario:**
- Stock: SOHL
- Days Listed: 8 days
- Current Price: Rs. 707.10
- Gain: +114.3%
- **Net Flow: +0 shares**

**Analysis:**

### Top Buyers (1 Week):
```
• Roadshow Securities: +29,470 shares
• Naasa Securities: +10,950 shares  
• Secured Securities: +2,600 shares
Total: ~42,000 shares bought
```

### Top Sellers (1 Week):
```
• Naasa Securities: -6,120 shares
• Dipshikha Dhitopatra: -5,580 shares
• Online Securities: -3,270 shares
Total: ~15,000 shares sold
```

**Question: Why is Net Flow = 0 if buying > selling?**

**Answer:** The displayed brokers are only the TOP brokers. The Net Flow calculation includes ALL brokers (100+ brokers trade on NEPSE). 

So while top buyers bought 42k and top sellers sold 15k, there must be:
- Other undisplayed brokers selling ~27k shares
- Making total buy = total sell = Net Flow 0

---

## ⚠️ Is Net Flow = 0 Good or Bad for SOHL?

### Context Matters:

**For a Stock Up 114% in 8 Days:**

✅ **GOOD Signs:**
- No panic selling (no negative flow)
- Market is in equilibrium
- Neither bulls nor bears dominating

⚠️ **WARNING Signs:**
- At 114% gain, you'd EXPECT some profit-taking
- Zero flow suggests market is "waiting" for next move
- Could break either way (up or down)

**Verdict: 🟡 NEUTRAL (WATCH CLOSELY)**

---

## 🧠 Reading the Flow Type

The analyzer classifies flow into 5 types:

### 1. 🔵 STRONG ACCUMULATION
- **Criteria:** Net Flow > +5000 shares
- **Meaning:** Institutions aggressively buying
- **Action:** Strong hold, consider adding

### 2. 🟢 ACCUMULATION  
- **Criteria:** Net Flow +1000 to +5000
- **Meaning:** Moderate buying pressure
- **Action:** Hold position

### 3. 🟡 NEUTRAL
- **Criteria:** Net Flow -1000 to +1000 ← **SOHL is here**
- **Meaning:** Balanced, consolidation
- **Action:** Hold but watch closely

### 4. 🟠 DISTRIBUTION
- **Criteria:** Net Flow -1000 to -5000
- **Meaning:** Moderate selling pressure  
- **Action:** Consider taking partial profit

### 5. 🔴 STRONG DISTRIBUTION
- **Criteria:** Net Flow < -5000 shares
- **Meaning:** Smart money exiting hard
- **Action:** Exit position immediately

---

## 💡 Pro Tips

### 1. **Context is Key**
Net Flow = 0 has different meanings based on:
- Stock's P/L (up 10% vs up 114%)
- Days since listing (Day 3 vs Day 10)
- Volume trend (increasing vs decreasing)

### 2. **Watch the Shift**
If flow changes from:
- NEUTRAL → DISTRIBUTION = 🚨 Warning, prepare to exit
- NEUTRAL → ACCUMULATION = ✅ Confidence, continue holding

### 3. **Institutional vs Retail**
Check WHO is buying/selling:
- Institutions selling + Retail buying = 🔴 **Bad** (dumb money buying)
- Institutions buying + Retail selling = 🟢 **Good** (smart money accumulating)

---

## 🔬 Advanced: Broker Flow Flip Signal

The IPO Exit Analyzer has a **Broker Flow Flip** signal (25 points):

**Triggers when:**
- Institutional Selling > 60% of total selling
- Retail Buying > 50% of total buying

**What it means:**
- Smart money (institutions) are exiting
- Dumb money (retail) are catching the falling knife
- **Strong exit signal!**

---

## 📋 SOHL Summary

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Net Flow | 0 shares | Balanced, neither side winning |
| Flow Type | NEUTRAL | Consolidation phase |
| Gain | +114.3% | Massive gain, expect profit-taking |
| Volume | Spike | 2x normal volume |
| **Overall Verdict** | **🟡 WATCH CLOSELY** | Hold but monitor daily |

**Why "Watch Closely"?**
- Gain is huge (+114%)
- Volume spike suggests movement incoming
- Net Flow = 0 means market is "deciding" next direction
- Could pump higher OR crash back

**Recommendation:**
- Set stop loss at Day 2 low (Rs. 336.60)
- Monitor daily for flow changes
- Consider booking 50% profit to secure gains

---

**Built by**: NEPSE AI Trading Bot  
**Date**: March 2026  
**For**: IPO Exit Analyzer Documentation
