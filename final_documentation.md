 📚 COMPLETE DOCUMENTATION - HOW THE CODE WORKS

  THE HONEST TRUTH:

  ┌──────┬───────────────────────────────────┬─────────────────────────────────────┐
  │ Step │ What Happens                      │ Proof                               │
  ├──────┼───────────────────────────────────┼─────────────────────────────────────┤
  │ 1    │ Fetch ALL stocks from NEPSE       │ 299 stocks (not 10-15)              │
  ├──────┼───────────────────────────────────┼─────────────────────────────────────┤
  │ 2    │ Loop through EVERY stock          │ for i, stock in enumerate(stocks)   │
  ├──────┼───────────────────────────────────┼─────────────────────────────────────┤
  │ 3    │ Score each through 4 pillars      │ _score_stock() called 299 times     │
  ├──────┼───────────────────────────────────┼─────────────────────────────────────┤
  │ 4    │ Technical analysis with pandas-ta │ EMA, RSI, MACD, ADX calculated      │
  ├──────┼───────────────────────────────────┼─────────────────────────────────────┤
  │ 5    │ Sum pillar scores                 │ total = P1 + P2 + P3 + P4           │
  ├──────┼───────────────────────────────────┼─────────────────────────────────────┤
  │ 6    │ Sort by score, return top N       │ Final ranking is OUR algorithm      │
  └──────┴───────────────────────────────────┴─────────────────────────────────────┘

  -----------------------------------------------------------------------------------------------------

  DATA FLOW DIAGRAM:

   ┌─────────────────────────────────────────────────────────────────────────────┐
   │                        MASTER STOCK SCREENER FLOW                           │
   ├─────────────────────────────────────────────────────────────────────────────┤
   │                                                                             │
   │  STEP 1: FETCH ALL 299 STOCKS FROM NEPSE API                               │
   │          └── NepseFetcher.fetch_live_market() → 299 stocks                 │
   │                                                                             │
   │  STEP 2: FOR EACH STOCK (loop 299 times):                                  │
   │          │                                                                  │
   │          ├── PILLAR 1: Broker Analysis (30 pts max)                        │
   │          │   └── Source: ShareHub Player Favorites (raw data)              │
   │          │   └── OUR ALGORITHM calculates: buyer% → score                  │
   │          │                                                                  │
   │          ├── PILLAR 2: Unlock Risk (20 pts or -50 penalty)                 │
   │          │   └── Source: ShareHub Lock-in Period (raw data)                │
   │          │   └── OUR ALGORITHM calculates: days → penalty                  │
   │          │                                                                  │
   │          ├── PILLAR 3: Fundamentals (20 pts max)                           │
   │          │   └── Source: ShareHub Company Data (raw data)                  │
   │          │   └── OUR ALGORITHM calculates: PE, PBV → score                 │
   │          │                                                                  │
   │          └── PILLAR 4: Technical (30 pts max)                              │
   │              └── Source: NEPSE 60-day OHLCV (raw data)                     │
   │              └── pandas-ta CALCULATES: EMA, RSI, MACD, ADX                 │
   │              └── OUR ALGORITHM applies scoring rules                       │
   │                                                                             │
   │  STEP 3: TOTAL SCORE = P1 + P2 + P3 + P4                                   │
   │                                                                             │
   │  STEP 4: SORT ALL 299 STOCKS BY SCORE (descending)                         │
   │                                                                             │
   │  STEP 5: RETURN TOP N (filtered by min_score threshold)                    │
   │                                                                             │
   └─────────────────────────────────────────────────────────────────────────────┘

  -----------------------------------------------------------------------------------------------------

  REAL EXAMPLE - NABIL STOCK:

   📊 RAW DATA FETCHED:
      - 35 days of OHLCV from NEPSE API
      
   📈 pandas-ta CALCULATIONS:
      - EMA 9:  524.82
      - EMA 21: 515.12  
      - RSI 14: 67.57
      - MACD:   2.5874
      - ADX:    37.61
      - Volume: 2.07x spike
   
   🧮 OUR SCORING:
      - EMA9 > EMA21 → +10 pts (BULLISH)
      - RSI 67.57 → 0 pts (slightly high, not optimal 50-65)
      - Volume 2.07x → +10 pts (HIGH INTEREST!)
      - ADX 37.61 → +5 pts (STRONG TREND)
      - MACD positive → +3 pts
      
      TECHNICAL SCORE = 15 (base) + 10 + 10 + 5 + 3 = 30/30

  THIS IS NOT FOOLING YOU - the code fetches raw data and applies mathematical scoring rules. ShareHub
  doesn't give us "top picks" - we calculate everything ourselves! 🎯