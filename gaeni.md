**DO NOT WRITE ANY CODE CONSIDERING Gaeni.md.**

# Gaeni EA — Expert Advisor for MT5 Signal System

## Full Project Specification Document
**Created:** 2026-10-04  
**Platform:** MetaTrader 5 (MQL5)  
**Timeframes:** M5, M15, M30 (one EA, adapts behavior per timeframe)  
**Source layout:** the repository mirrors the MT5 data folder — `Experts\Gaeni\Gaeni.mq5` (→ `MQL5\Experts\Gaeni\`) and `Include\Gaeni\Gaeni_*.mqh` (→ `MQL5\Include\Gaeni\`); the EA includes its headers with quoted repo-relative paths (`#include "../../Include/Gaeni/Gaeni_Types.mqh"`), which resolve to the same file in the checkout and after the copy into the terminal (no header install needed to compile). See `README.md` for install/compile steps.

**Implementation status:** **Step 0 (Visual Dashboard Interface & EA Skeleton), Phase 1 (Foundation, Dynamic Parameter Engine & Market Regime Detection), Phase 2 (ML-Adaptive Supertrend), and Phase 3 (SMC Structure Detection) IMPLEMENTED (2026-10-06)** in `Experts/Gaeni/Gaeni.mq5` and `Include/Gaeni/`. Phase 2 learns Calm/Normal/Wild ATR clusters and a cluster-specific Supertrend multiplier from closed-bar returns. Phase 3 detects confirmed swings, displacement Order Blocks, Fair Value Gaps, BOS/CHoCH, liquidity sweeps, and Premium/Discount zones; its summary uses the existing WHY row and its levels are chart overlays. The Section 7 card layout remains unchanged; Phases 4–9 are pending.

---

## 1. PURPOSE

Gaeni is a **fully automated Expert Advisor** that trades according to its own signals. It provides:
- Direction: BUY or SELL
- Entry Price
- Stop Loss (SL)
- Take Profit (TP)
- Expected Duration (calculated dynamically)
- Confidence Score (0–100%)

The EA executes trades automatically when it gives a signal, and manages them through the complete trade lifecycle. All information is displayed on a visual dashboard panel on the chart.

---

## 2. TIMEFRAME BEHAVIOR (DYNAMIC - NOT HARDCODED)

The EA adapts to the timeframe automatically using ATR and volatility calculations. No hardcoded values per timeframe.

### Dynamic Duration Calculation
Instead of fixed duration per timeframe, the EA calculates expected duration based on:

**Formula:**
```
Expected Duration (in bars) = (Distance to TP in price) / (Expected price movement per bar)

Where:
- Expected price movement per bar = ATR(14) × Momentum Factor
- Momentum Factor = Adjusted by current regime strength and CVD direction
- Converted to time: bars × timeframe minutes
```

**Factors that increase duration:**
- Low volatility (small ATR)
- Weak momentum (CVD not strongly confirming)
- Large distance to TP
- Ranging regime (slower progress)

**Factors that decrease duration:**
- High volatility (large ATR)
- Strong momentum (CVD strongly confirming)
- Small distance to TP
- Strong trending regime

### Dynamic Lookback Windows
All calculations scale with current timeframe's ATR:

| Parameter | Calculation |
|-----------|-------------|
| Regime Detection | Last (50 × ATR multiplier) bars |
| SMC Order Blocks | (10 × ATR multiplier) bar lookback |
| K-Means Training | (200 × ATR multiplier) bars |
| Volume Profile | Last 200 bars (fixed, works across all TFs) |

The ATR multiplier ensures the EA "sees" the same amount of price action regardless of timeframe.

### Signal Management (No Fixed Cooldown)

**Instead of time-based cooldown, the EA uses signal invalidation logic:**

1. **Active Signal Phase:** Once a signal is given, it remains active until:
   - Price hits TP (signal successful)
   - Price hits SL (signal failed)
   - Market structure invalidates the signal (CHoCH against the direction)
   - Regime changes (e.g., was Trending, now Ranging)

2. **New Signal Allowed When:**
   - Previous signal is resolved (hit TP/SL/invalidated)
   - OR structure confirms opposite direction (CHoCH + ML-Supertrend flip)
   - AND new signal meets confidence threshold (≥60%)

3. **Protection Against Overtrading:**
   - **Minimum gap between signals:** 1 candle (not 3) - allows quick response when structure changes
   - **Same direction signals:** Only if previous signal hit TP (momentum continuing)
   - **Opposite direction signals:** Only if CHoCH confirms reversal (not just random flip)
   - **Spread filter:** No new signals if spread > 2× average (prevents bad fills during news)

**Example Scenarios:**

| Situation | What Happens |
|-----------|--------------|
| BUY signal given, price moving up | Signal stays active, no new signals |
| Price hits TP1 | Signal closed, EA scans for new setup immediately |
| Price hits SL | Signal closed, EA waits 1 candle then scans again |
| Price moves against BUY, CHoCH forms | Signal invalidated (structure broken), can give SELL signal immediately |
| BUY signal given, next candle forms strong bullish engulfing | No new BUY signal needed (previous signal still valid) |
| BUY signal, price stalls, no movement for 5 candles | Signal still active, waiting for momentum |
| Regime changes from Trending to Ranging | Current signal invalidated, EA shows "WAIT" |

**Why This Is Better Than Fixed Cooldown:**
- M5 chart: 15-minute cooldown means missing 3 candles of action (too long)
- M30 chart: 90-minute cooldown is fine
- Structure-based invalidation: Responds in 1 candle if structure breaks, regardless of timeframe
- Prevents overtrading by requiring structure confirmation, not just time passing

---

## 3. DYNAMIC PARAMETER ENGINE (CONTINUOUS AUTOMATION)

### Foundation: Auto-Detection + Continuous Adaptation

**What:** Before any indicator calculation, the EA automatically detects the symbol type and continuously adjusts ALL parameters based on volatility regime and market conditions. No hardcoded values. No manual optimization needed. This runs on every tick and recalculates continuously.

**This is the foundation layer that feeds into ALL 7 components below.**

### 3.1 Symbol Auto-Detection

The EA analyzes the symbol name and automatically categorizes it into one of 5 asset classes:

| Asset Class | Detection Pattern | Base Volatility Profile |
|-------------|-------------------|------------------------|
| **Forex Major** | Contains "EUR", "GBP", "USD", "JPY", "CHF", "CAD", "AUD", "NZD" | Low-Medium |
| **Forex Cross** | Two non-USD currencies (e.g., EURGBP, AUDNZD) | Medium |
| **Metals** | Contains "XAU", "XAG", "GOLD", "SILVER" | High |
| **Crypto** | Contains "BTC", "ETH", "LTC", "CRYPTO" | Extreme |
| **Indices** | Contains "US30", "NAS", "SPX", "DAX", "NIK" | Session-Based |

**Detection Logic (runs once on OnInit, then continuously validates):**
```
1. Extract symbol name from ChartSymbol()
2. Remove broker suffixes (.pro, .ecn, m, .i, .r, .raw, +, #)
3. Match against asset class patterns
4. If no match → classify as "Generic/Other" (use medium volatility defaults)
5. Store result in global variable: g_symbolClass
```

### 3.2 Continuous Volatility Regime Detection

**What:** Every N bars (adaptive based on timeframe), the EA calculates the current volatility percentile against recent history and classifies the regime.

**Calculation (runs every new bar):**
```
1. Calculate ATR(14) for current bar
2. Calculate ATR values for last 200 bars
3. Calculate percentile: Where does current ATR sit in the 200-bar range?
   
   Volatility Percentile = (Count of bars where ATR < current ATR) / 200 × 100

4. Classify:
   - Percentile 0-30   → LOW VOLATILITY regime
   - Percentile 30-70  → NORMAL VOLATILITY regime
   - Percentile 70-100 → HIGH VOLATILITY regime
```

**This classification drives ALL parameter adjustments.**

### 3.3 Dynamic Parameter Adjustment Matrix

All indicator parameters are calculated dynamically based on: **Symbol Class + Volatility Regime + Market State**

#### ATR Period (for Supertrend, SL/TP, all ATR-based calculations)

| Symbol Class | Low Vol | Normal Vol | High Vol |
|--------------|---------|------------|----------|
| Forex Major  | 10      | 10         | 14       |
| Forex Cross  | 10      | 14         | 14       |
| Metals       | 10      | 14         | 21       |
| Crypto       | 14      | 21         | 28       |
| Indices      | 10      | 14         | 14       |
| Generic      | 10      | 14         | 14       |

#### Kaufman Efficiency Ratio Period (for Regime Detection)

| Symbol Class | Low Vol | Normal Vol | High Vol |
|--------------|---------|------------|----------|
| Forex Major  | 10      | 10         | 14       |
| Forex Cross  | 10      | 14         | 14       |
| Metals       | 14      | 14         | 21       |
| Crypto       | 21      | 21         | 28       |
| Indices      | 14      | 14         | 21       |
| Generic      | 14      | 14         | 21       |

**Kaufman Efficiency Ratio (ER)** ranges from 0-100:
- ER > 60 = Strong trending market
- ER < 30 = Choppy/sideways market
- ER 30-60 = Transitional market

#### KAMA Periods (for Trend Detection: Fast, Medium, Slow)

| Symbol Class | Low Vol | Normal Vol | High Vol |
|--------------|---------|------------|----------|
| Forex Major  | 9, 21, 50   | 9, 21, 50   | 13, 26, 50   |
| Forex Cross  | 9, 21, 50   | 13, 21, 50  | 13, 26, 50   |
| Metals       | 9, 21, 50   | 13, 21, 50  | 13, 26, 50   |
| Crypto       | 13, 26, 50  | 13, 26, 50  | 21, 34, 50   |
| Indices      | 9, 21, 50   | 13, 21, 50  | 13, 26, 50   |
| Generic      | 9, 21, 50   | 13, 21, 50  | 13, 26, 50   |

**KAMA (Kaufman Adaptive Moving Average)** automatically adjusts its sensitivity:
- In trending markets: becomes more responsive like EMA
- In choppy markets: becomes flatter, filters out noise
- No manual parameter optimization needed

#### Supertrend Multiplier Range (for K-Means Adaptive Supertrend)

| Symbol Class | Low Vol Range | Normal Vol Range | High Vol Range |
|--------------|---------------|------------------|----------------|
| Forex Major  | 2.0 – 3.0     | 2.5 – 3.5        | 3.0 – 4.0      |
| Forex Cross  | 2.0 – 3.0     | 2.5 – 3.5        | 3.0 – 4.0      |
| Metals       | 2.5 – 3.5     | 3.0 – 4.0        | 3.5 – 5.0      |
| Crypto       | 3.0 – 4.0     | 3.5 – 5.0        | 4.0 – 6.0      |
| Indices      | 2.0 – 3.0     | 2.5 – 3.5        | 3.0 – 4.5      |
| Generic      | 2.0 – 3.5     | 2.5 – 3.5        | 3.0 – 4.5      |

#### K-Means Training Window (bars for ML Supertrend)

| Symbol Class | Low Vol | Normal Vol | High Vol |
|--------------|---------|------------|----------|
| Forex Major  | 200     | 200        | 300      |
| Forex Cross  | 200     | 200        | 300      |
| Metals       | 150     | 200        | 300      |
| Crypto       | 100     | 150        | 200      |
| Indices      | 150     | 200        | 250      |
| Generic      | 200     | 200        | 300      |

#### SMC Lookback (Order Block, Swing High/Low detection)

| Symbol Class | Low Vol | Normal Vol | High Vol |
|--------------|---------|------------|----------|
| Forex Major  | 10 bars | 10 bars    | 15 bars  |
| Forex Cross  | 10 bars | 10 bars    | 15 bars  |
| Metals       | 8 bars  | 10 bars    | 15 bars  |
| Crypto       | 8 bars  | 10 bars    | 15 bars  |
| Indices      | 8 bars  | 10 bars    | 15 bars  |
| Generic      | 10 bars | 10 bars    | 15 bars  |

#### Volume Profile Bars (for POC, VAH, VAL calculation)

| Symbol Class | Low Vol | Normal Vol | High Vol |
|--------------|---------|------------|----------|
| Forex Major  | 200     | 200        | 300      |
| Forex Cross  | 200     | 200        | 300      |
| Metals       | 150     | 200        | 300      |
| Crypto       | 100     | 150        | 200      |
| Indices      | 150     | 200        | 250      |
| Generic      | 200     | 200        | 300      |

#### Confidence Thresholds (adjusted by market state)

| Market State   | Strong Signal | Moderate Signal | Below Threshold |
|----------------|---------------|-----------------|-----------------|
| Trending       | 70%           | 60%             | No signal       |
| Ranging        | 80%           | 70%             | No signal       |
| Transition     | 85%           | 75%             | No signal       |
| High Volatile  | 80%           | 70%             | No signal       |

### 3.4 Market State Adaptation (Continuous)

On top of symbol + volatility, the EA further adjusts based on detected market state (from Component 1):

```
IF market state = TRENDING:
  → Shorter lookbacks (trend is clear, act faster)
  → Standard ATR multipliers for SL/TP
  → Lower confidence threshold (60% OK)
  → Signal invalidation: Quick (1-2 candles if CHoCH)

IF market state = RANGING:
  → Longer lookbacks (filter noise, wait for clarity)
  → Wider ATR multipliers for SL/TP (avoid stop hunts)
  → Higher confidence threshold (70% minimum)
  → Signal invalidation: Slower (wait for structure break)

IF market state = HIGH VOLATILE:
  → Much longer lookbacks (avoid false signals)
  → Very wide ATR multipliers (give price room)
  → Very high confidence threshold (70% minimum)
  → Signal invalidation: Very slow (high volatility = frequent whipsaws)

IF market state = TRANSITION:
  → Medium lookbacks (market changing, stay alert)
  → Standard ATR multipliers
  → High confidence threshold (75% minimum)
  → Signal invalidation: Medium (watch for new trend)
```

### 3.5 Continuous Self-Optimization Engine (Parameter Performance Tracking)

**What:** The EA tracks which parameter combinations work best for each symbol + volatility + regime combination, and gradually favors the winners.

**How it works (runs after every resolved signal):**

```
1. Record current parameters used:
   - ATR period, Kaufman ER period, KAMA periods, Supertrend multiplier range
   - K-Means window, SMC lookback, Volume Profile bars
   - Confidence thresholds
   
2. Record signal outcome: WIN or LOSS
   
3. Store in parameter performance log:
   {
     SymbolClass: "Metals"
     VolatilityRegime: "High"
     MarketState: "Trending"
     ParametersUsed: {ATR: 21, ER: 21, KAMA: [13,26,50], ...}
     Outcome: WIN
     Timestamp: 2026.10.05 14:30
   }
   
4. After 20+ signals recorded for a specific combination:
   - Calculate win rate for each parameter variation
   - Identify which parameters produced highest win rate
   - Store as "optimal parameters" for that combination
   
5. Next time same combination occurs:
   - Start with base parameters (from matrix above)
   - Blend with learned optimal parameters (70% base, 30% learned)
   - As more data accumulates: shift to 50% base, 50% learned
   - Eventually: 30% base, 70% learned (trust the data)
```

**Data Storage:**
- Saved to: `MQL5/Files/Gaeni_ParameterOptimization/EURUSD_M15_params.dat`
- Separate file per symbol + timeframe combination
- Persists across MT5 restarts
- Can be manually deleted to reset optimization

### 3.6 Recalculation Frequency (Continuous Automation)

The dynamic parameter engine runs on multiple schedules:

| Task | Frequency | Trigger |
|------|-----------|---------|
| Symbol detection | Once on init, then every 100 bars (validation) | OnInit + OnTimer |
| Volatility percentile | Every new bar | OnCalculate (new bar) |
| Parameter adjustment | Every new bar (after volatility update) | OnCalculate (new bar) |
| Market state detection | Every new bar | OnCalculate (new bar) |
| Parameter performance tracking | After each signal resolves | OnTick (when trade closes) |
| Self-optimization blending | After every 5 resolved signals | OnTick (when trade closes) |
| Full parameter recalculation | Every 50 bars (or when regime changes) | OnCalculate + OnTimer |

**Result:** Parameters are NOT static. They adapt continuously as market conditions change. If volatility shifts from low to high mid-session, parameters adjust within 1-2 bars.

---

## 4. SEVEN INNOVATIVE COMPONENTS (ALL INCLUDED)

### Component 1: Market Regime Detection
**What:** Classifies current market into one of 5 states before giving any signal.

| State | Condition | EA Behavior |
|-------|-----------|-------------|
| Market Closed | No new candles forming, weekend/holiday, outside trading hours | Show "Regime: MARKET CLOSED" on dashboard, no signals, no trades |
| Trending | Strong directional movement, ER > 60, aligned KAMAs | Give BUY/SELL signals |
| Ranging | Price bouncing between clear levels, ER < 30 | Show "NO TRADE — Range" |
| Volatile/Choppy | High ATR spikes, mixed signals, whipsaws | Show "NO TRADE — Volatile" |
| Transition | Regime changing (detected by shift in structure) | Show "WAIT — Transition" |

**Implementation:**
- Use Kaufman Efficiency Ratio (14) for trend strength (replaces ADX — faster, more accurate)
- Use ATR (14) vs ATR (50) ratio for volatility regime
- Use KAMA alignment (9, 21, 50) for directional clarity
- Use Bollinger Band width for squeeze/expansion detection
- **Market Closed Detection:** Check if new candles are forming (compare last candle close time with current time). If no new candle for > 2× candle period, or if SymbolInfoInteger shows market closed, display "Market Closed" state.

### Component 2: ML-Adaptive Supertrend (K-Means Clustering)
**What:** Supertrend indicator that auto-adjusts its multiplier based on current volatility regime using K-Means machine learning.

**How it works:**
1. Collect ATR values over training window (150/200/300 bars based on TF)
2. Run K-Means clustering (K=3) to find 3 volatility clusters: calm, normal, wild
3. For each cluster, test which Supertrend multiplier produced best signals historically
4. Use the best multiplier for current conditions
5. Recalculate clusters every N bars (adaptive)

**Output:** Direction (BUY/SELL) + the adaptive Supertrend line value (used as trailing reference)

**Implementation:** Native MQL5 K-Means algorithm (no external libraries needed).

### Component 3: Smart Money Concepts (SMC) Structure
**What:** Detects institutional-level price structures for entry, SL, and TP placement.

**Sub-components:**

| SMC Element | Purpose | How Detected |
|-------------|---------|--------------|
| **Order Blocks (OB)** | Entry zones | Last opposite candle before strong move (>1.5x avg body size) |
| **Fair Value Gaps (FVG)** | TP targets / price magnets | 3-candle pattern where candle 1 and 3 don't overlap |
| **Liquidity Pools** | Where stops cluster (SL placement reference) | Swing highs/lows where price has swept before |
| **Change of Character (CHoCH)** | Trend confirmation | Break of most recent swing structure |
| **Break of Structure (BOS)** | Trend continuation | Price breaking previous high (uptrend) or low (downtrend) |
| **Premium/Discount Zone** | Is price expensive or cheap | 50% level of recent swing range |

**Rules:**
- BUY only when price is in Discount zone (below 50% of range)
- SELL only when price is in Premium zone (above 50% of range)
- Entry near an Order Block in the direction of ML-Supertrend
- SL beyond the Order Block or recent swing
- TP at next FVG or liquidity pool

### Component 4: Volume Profile + CVD + VWAP (Institutional Flow Analysis)
**What:** Uses real trading volume data and institutional benchmarks to find where smart money operates.

**Sub-components:**

| Tool | What It Shows | Usage |
|------|--------------|-------|
| **Point of Control (POC)** | Price level with highest traded volume | TP magnet target — price tends to return here |
| **Value Area High (VAH)** | Upper boundary of 70% volume | Resistance / SELL target area |
| **Value Area Low (VAL)** | Lower boundary of 70% volume | Support / BUY target area |
| **Naked POC** | POC that hasn't been revisited yet | Strong magnet — high probability TP |
| **Cumulative Volume Delta (CVD)** | Net buying vs selling pressure | Confirms direction strength |
| **VWAP (Volume Weighted Average Price)** | Institutional fair value benchmark | Dynamic support/resistance, trend confirmation |
| **Session VWAP** | VWAP anchored to session start (Asia/London/NY) | Shows where institutions are positioned per session |

**Implementation:** Built from tick volume data available in MT5. VWAP calculated using standard institutional formula (cumulative price×volume / cumulative volume). No external data needed.

**VWAP Rules:**
- Price above VWAP → Bullish bias (buyers in control)
- Price below VWAP → Bearish bias (sellers in control)
- VWAP acts as dynamic support in uptrends
- VWAP acts as dynamic resistance in downtrends
- Price far from VWAP → potential mean reversion

**Combined Rules:**
- If CVD is rising (more buyers) → confirms BUY signals
- If CVD is falling (more sellers) → confirms SELL signals
- If price above VWAP + CVD rising → Strong BUY confirmation
- If price below VWAP + CVD falling → Strong SELL confirmation
- If price above VWAP but CVD falling → Weak signal, reduce confidence
- If price below VWAP but CVD rising → Weak signal, reduce confidence
- TP target = nearest POC, Naked POC, or VWAP in the direction of trade
- If CVD and VWAP disagree with signal → reduce confidence score

### Component 5: Multi-Timeframe Agreement
**What:** Higher timeframe must confirm the direction before signal is given.

**Structure:**

| Chart TF | Check TF | Purpose |
|----------|----------|---------|
| M5 | M15 or M30 | Confirm trend alignment |
| M15 | H1 | Confirm trend alignment |
| M30 | H4 | Confirm trend alignment |

**How it works:**
- Run ML-Adaptive Supertrend on the higher timeframe
- Run Market Regime Detection on the higher timeframe
- Both must agree: Higher TF Supertrend direction must match current TF signal
- Higher TF must NOT be in Ranging or Volatile regime

**Implementation:** Using iCustom() or direct iMA/iATR calls with higher timeframe data (built into MQL5 via CopyRates with timeframe parameter).

### Component 6: Confidence Engine (Weighted Multi-Factor Scoring)
**What:** Combines all component scores into one final confidence percentage.

**Scoring Table:**

```
Factor                      Max Weight   Score (0.0–1.0)   Weighted
─────────────────────────────────────────────────────────────────
Market Regime Quality           15%        varies           = weight × score
ML-Adaptive Supertrend          20%        varies           = weight × score
SMC Structure Quality           20%        varies           = weight × score
Volume + VWAP Confirmation      15%        varies           = weight × score
Multi-TF Agreement              15%        varies           = weight × score
Self-Learning Filter            15%        varies           = weight × score
─────────────────────────────────────────────────────────────────
TOTAL CONFIDENCE (0–100%)                          sum of weighted scores
```

**Confidence Classification:**

| Confidence Range | Classification | Action | Position Size | Display Color |
|-----------------|----------------|--------|---------------|---------------|
| **75%+** | Very Strong | Strong signal, trade with confidence | 100% size | Green |
| **65-74%** | Strong | Good signal, trade normally | 85% size | Light Green |
| **55-64%** | Moderate | Decent signal, consider trading | 70% size | Yellow |
| **45-54%** | Normal | Weak signal, trade only if other factors align | 50% size | Orange |
| **40-44%** | Ranging | Very weak, avoid trading | No trade | Light Red |
| **<40%** | Hold | Do not trade, wait for better setup | No trade | Red |

**Dynamic Weight Adjustment:**
- If self-learning filter shows a factor has been accurate lately → increase its weight
- If a factor has been giving false signals → decrease its weight
- Weights are normalized to always sum to 100%

**Continuous Confidence Updates:**
- Confidence score is **recalculated every bar** while a signal is active
- The score is **always visible** on the dashboard, updating in real-time
- When confidence drops significantly (>15% decline), the STATUS line warns: "Confidence dropping — 65% → 48%"
- When confidence rises significantly (>10% increase), the STATUS line updates: "Confidence strengthening — 72% → 85%"
- If confidence falls below 50% during an active trade, the EA suggests: "Consider early exit — confidence weak"
- Final confidence at trade close is recorded for self-learning analysis

### Component 7: Self-Learning Signal Filter
**What:** The EA learns from its own signal history in real-time using online logistic regression.

**How it works:**
1. Every time a signal is given, store the conditions (regime, volatility, session, direction, confidence, all factor scores)
2. After the trade resolves (TP hit or SL hit or duration expired), label it as WIN or LOSS
3. Feed this labeled data back into a simple logistic regression model
4. The model learns which conditions lead to winning signals
5. Future signals are filtered/adjusted based on this learned knowledge

**Implementation:**
- Native MQL5 logistic regression with SGD (Stochastic Gradient Decay)
- Features: regime type, ATR level, session (Asia/London/NY), day of week, CVD direction, TF agreement score
- **Data Storage:** All signal history and model weights are saved to local PC drive in `MQL5/Files/Gaeni_LearningData/` folder. Data persists permanently across MT5 restarts, computer reboots, and EA updates. Each symbol+timeframe combination gets its own learning file (e.g., `EURUSD_M15_learning.dat`).
- Update: After each signal resolves (every N signals based on TF)
- **Data Format:** Binary file containing: signal conditions, outcome labels (WIN/LOSS), model weights, timestamp. Can be deleted manually to reset learning if needed.

**Important:** On first use, the self-learning filter has no history. It starts with neutral weights (all 0.5) and gradually learns. Other components work fully from bar 1.

---

## 5. ADVANCED TRADE MANAGEMENT FEATURES

### 5.1 Partial Take Profit + Intelligent Context-Aware Trailing Stop
**What:** Locks in profit early, protects capital, and lets winners run with intelligent trailing that adapts to timeframe, profit phase, and market conditions.

**How it works:**

**Part A: Partial Close at TP1**
1. When price reaches TP1 (first target, typically 1:1 RR):
   - Close PartialTP_Percentage of position (default 50%)
   - Lock in profit on closed portion
   - Move SL to breakeven for remaining position

**Part B: Intelligent Trailing Stop System (4 Layers)**

**Layer 1: Timeframe Auto-Detection**
The EA automatically adjusts trailing tightness based on the chart timeframe:
- **M5 Chart:** Tight trailing (1.0× ATR default) - captures small 10-50 pip moves
- **M15 Chart:** Medium trailing (1.5× ATR default) - balanced for 50-150 pip moves
- **M30 Chart:** Loose trailing (2.0× ATR default) - allows 100-300+ pip moves to develop

**Layer 2: Multi-Phase Progression (Based on Profit %)**
As profit grows, the trailing method switches to protect more profit:
- **Phase 1 (0-50% profit):** ATR trailing - let trade breathe with loose trail
- **Phase 2 (50-80% profit):** Chandelier Exit - medium trail, locks profit from highest point
- **Phase 3 (80%+ profit):** Fractal trailing - tight trail, protects maximum profit at structure levels

**Layer 3: Context Multipliers (Adapts to Market Conditions)**
Trailing tightness adjusts based on real-time market context:

| Factor | Condition | Multiplier | Effect |
|--------|-----------|------------|--------|
| **Confidence** | 85%+ | 1.0× | Normal trail |
| | 70-84% | 0.9× | Slightly tighter |
| | 55-69% | 0.7× | Much tighter |
| | <55% | 0.5× | Emergency tight |
| **Regime** | Trending | 1.0× | Normal |
| | Transition | 0.8× | Tighter |
| | Volatile | 1.3× | Wider (give room) |
| | Ranging | 0.6× | Very tight |
| **Divergence** | None | 1.0× | Normal |
| | Detected | 0.5× | Emergency tight |
| **News** | None | 1.0× | Normal |
| | <30 min | 1.5× | Very wide (or close) |

**Layer 4: User Override (Optional)**
User can force a specific trailing style regardless of timeframe:
- "Auto" = EA chooses based on timeframe (recommended)
- "Force Tight" = always use M5-style trailing
- "Force Medium" = always use M15-style trailing
- "Force Loose" = always use M30-style trailing

**Final Trailing Distance Calculation:**
```
baseTrail = selected method's distance (e.g., Chandelier 2.5× ATR)
finalTrail = baseTrail × confidence × regime × divergence × news
```

**Example: M15 Chart with Context-Aware Trailing**

```
Trade opens:
  → Profit: 0%
  → Timeframe: M15 (medium trailing)
  → Confidence: 85% (strong)
  → Regime: Trending
  → Phase: 1 (ATR trailing, loose)
  → Trail distance: 1.5× ATR = 30 pips (normal)

Price moves up:
  → Profit: 45% toward TP
  → Confidence: 80% (still strong)
  → Phase: 1 (ATR trailing)
  → Trail distance: 30 pips (still normal)

Getting close to TP:
  → Profit: 55% toward TP
  → Confidence: 75% (dropping slightly)
  → Phase: 2 (switch to Chandelier, medium)
  → Trail distance: 2.5× ATR × 0.9 = 67.5 pips (medium tight)

Warning signs:
  → Profit: 58% toward TP
  → Confidence: DROPPED to 58% (was 75%)
  → CVD: Divergence detected
  → Phase: 2 (Chandelier) BUT emergency tight
  → Trail distance: 67.5 × 0.7 × 0.5 = 23.6 pips (EMERGENCY!)

Price reverses:
  → Hit emergency trail at 23.6 pips
  → Exit with profit locked
  → Instead of waiting for full reversal to SL!
```

**Why this matters:**
- **Solves your frustration:** No more "80% profit wiped out to zero"
- **M5 trades:** Don't get wiped by reversals (tight trail)
- **M30 trades:** Don't get kicked out by pullbacks (loose trail)
- **All trades:** Adapt to profit progression (phased tightening)
- **All trades:** Adapt to market conditions (context-aware)
- **Emergency protection:** Confidence drop + divergence = emergency tight trail

---

### 5.2 Tick-Level CVD Divergence Detection
**What:** Detects early reversal warnings by comparing price action vs. actual buying/selling pressure at tick level.

**How it works:**
1. **Monitor Tick Flow:** Every tick, classify as buyer-initiated or seller-initiated based on bid/ask comparison
2. **Calculate CVD:** Cumulative sum of (buyer ticks - seller ticks) over rolling window
3. **Detect Divergence:**
   - **Bullish Divergence:** Price makes new low, but CVD makes higher low → selling pressure weakening → potential reversal up
   - **Bearish Divergence:** Price makes new high, but CVD makes lower high → buying pressure weakening → potential reversal down
4. **Action:** Based on DivergenceAction setting:
   - "Reduce Confidence" → Lower confidence score by 15-20% (signal still valid but weaker)
   - "Auto Close" → Close position immediately (early exit before reversal confirms)
   - "Warning Only" → Show warning on dashboard, no action

**Example:**
- BUY signal active, price making new highs: 1.08500 → 1.08550 → 1.08600
- But CVD trending down: +120 → +95 → +70 (fewer buyers despite higher price)
- Divergence detected → Confidence drops from 82% to 67%
- If "Auto Close" → position closed at 1.08600 before reversal to 1.08450
- If "Reduce Confidence" → user sees weaker signal, may manually close

**Why this matters:**
- Traditional indicators (EMA, ATR) lag by 2-5 bars
- Tick-level CVD detects weakening momentum immediately
- Can exit 10-30 minutes earlier than waiting for structure break
- Catches "fake breakouts" before they hit SL

---

### 5.3 Time-Based TP Adjustment
**What:** Prevents trades from sitting forever when expected duration passes without TP hit.

**How it works:**
1. **Calculate Expected Duration:** Based on ATR, momentum, distance to TP (already in Gaeni.md)
2. **Monitor Trade Age:** Track how long position has been open
3. **When Trade Age > Expected Duration:**
   - Based on TimeExitAction setting:
     - "Close at Market" → Exit immediately (trade didn't work, cut losses)
     - "Move TP Closer" → Move TP to 50% of remaining distance to original TP
     - "Start Trailing" → Switch to ATR-based trailing stop (recommended)

**Example:**
- BUY signal, expected duration: 2 hours, TP: 1.09120 (67 pips away)
- After 2 hours: price at 1.08800 (35 pips profit, but TP not hit)
- If "Close at Market" → exit at +35 pips (better than waiting for potential reversal)
- If "Move TP Closer" → move TP to 1.08960 (50% of remaining 32 pips = 16 pips)
- If "Start Trailing" → trail SL at 1.5× ATR behind current price, let market decide

**Why this matters:**
- Without time exit: Trade sits for 6 hours, price reverses, hits SL → loss
- With time exit: Exit early at +35 pips or trail to protect profit
- Prevents "hope trades" (hoping price will eventually hit TP)

---

### 5.4 News/Economic Calendar Filter
**What:** Uses MT5's built-in Economic Calendar to avoid trading during high-impact news events.

**How it works:**
1. **Access MT5 Economic Calendar:** Built-in API, no external data needed
2. **Filter Events by Impact:**
   - **High Impact (3-star):** NFP, FOMC, CPI, GDP, Central Bank Rate Decisions
   - **Medium Impact (2-star):** PMI, Retail Sales, Housing Data
   - **Low Impact (1-star):** Minor reports, revisions (ignored)
3. **Apply Blackout Window:** NewsBufferMinutes before and after each event (default 30 min)
4. **Action Based on NewsAction Setting:**
   - "Block All Trading" → No signals, no trades during blackout
   - "Reduce Size 50%" → Trade with half position (allows participation but reduces risk)
   - "Warning Only" → Show warning on dashboard but allow full trading

**Example:**
- NFP release at 13:30 GMT (high impact)
- Blackout: 13:00-14:00 (30 min before + 30 min after)
- If "Block All Trading" → EA shows "News Blackout — NFP in 15 minutes" on dashboard
- If "Reduce Size 50%" → Normal signals but lot size = 0.5× calculated size
- If "Warning Only" → Trade normally but show "High Impact News — NFP" warning

**Why this matters:**
- News events cause 50-200 pip spikes in seconds
- Technical analysis becomes irrelevant during news
- Spread widens 5-10×, causing bad fills
- SL gets hit by spike, then price reverses → "stop hunt" feeling
- News filter prevents these scenarios

---

### 5.5 Trading Session Filter
**What:** Restricts trading to high-liquidity sessions (London, New York) and avoids low-liquidity traps (Asian session for forex/metals).

**How it works:**
1. **Auto-Detect Session Times:** Based on broker server time + GMT offset
2. **Session Windows (auto-calculated):**
   - **Asian Session:** 22:00-07:00 GMT (Tokyo, Sydney, Hong Kong)
   - **London Session:** 07:00-16:00 GMT (London, Frankfurt, Paris)
   - **New York Session:** 12:00-21:00 GMT (New York, Chicago, Toronto)
3. **Apply Filter Based on Inputs:**
   - AllowLondonSession = true → Trade during London (default ON)
   - AllowNewYorkSession = true → Trade during NY (default ON)
   - AllowAsianSession = false → Block Asian session (default OFF for forex/metals)
4. **Crypto Auto-Detection:** If symbol contains "BTC", "ETH", "CRYPTO" → Asian session auto-allowed (crypto is 24hr liquid)

**Example:**
- Forex pair (EURUSD) at 03:00 GMT (Asian session):
  - AllowAsianSession = false → EA shows "Asian Session — Low Liquidity" on dashboard
  - No signals given, no trades placed
- Crypto pair (BTCUSD) at 03:00 GMT:
  - Symbol detected as crypto → Asian session auto-allowed
  - Normal trading, signals given as usual
- Forex pair at 08:00 GMT (London session):
  - AllowLondonSession = true → Normal trading

**Why this matters:**
- Asian session (for forex): 60% lower volume, wider spreads, slower price movement
- Signals during Asian session have 40% lower success rate
- London-NY overlap (12:00-16:00 GMT) has highest liquidity and best price action
- Crypto never sleeps → Asian session is fine for crypto

---

### 5.6 Confidence-Based Adaptive Position Sizing
**What:** Larger position on high-confidence signals, smaller on uncertain ones. Maximizes profit on strong setups, reduces risk on weak ones.

**How it works:**
1. **Calculate Base Lot Size:** From RiskPercentPerTrade (default 1% of balance)
2. **Apply Confidence Multiplier:** Based on SizingProfile selection:

| Confidence | Minimum Lot (0.1x-0.3x) | Conservative (0.5x-1.0x) | Normal (0.7x-1.5x) | Aggressive (0.5x-2.0x) |
|------------|------------------------|--------------------------|--------------------|-----------------------|
| 90%+       | 0.3×                   | 1.0×                     | 1.5×               | 2.0×                  |
| 80-89%     | 0.2×                   | 0.85×                    | 1.2×               | 1.6×                  |
| 70-79%     | 0.15×                  | 0.7×                     | 1.0×               | 1.2×                  |
| 60-69%     | 0.1×                   | 0.5×                     | 0.7×               | 0.5×                  |

3. **Apply Final Lot Size:** Base lot × confidence multiplier
4. **Enforce Broker Limits:** Ensure lot size is within broker's min/max range

**Example:**
- Balance: $10,000, RiskPercent: 1%, SL distance: 20 pips
- Base lot = ($10,000 × 0.01) / (20 pips × $10/pip) = 0.5 lots
- Signal confidence: 85%
- If SizingProfile = "Normal" → multiplier = 1.2× → final lot = 0.6 lots
- If SizingProfile = "Minimum Lot" → multiplier = 0.2× → final lot = 0.1 lots
- If SizingProfile = "Aggressive" → multiplier = 1.6× → final lot = 0.8 lots

**Why this matters:**
- Without adaptive sizing: Every trade risks 1% regardless of quality
- With adaptive sizing: High-confidence (90%) trades risk 1.5-2%, low-confidence (65%) trades risk 0.5-0.7%
- Over 100 trades: Higher profit on winners, lower loss on losers → better overall performance

---

### 5.7 Auto Trading Functions
**What:** Complete automated trade execution and management system that transforms signals into actual trades with full lifecycle management.

**How it works:**

**Part A: Signal-to-Trade Execution**
1. **Signal Validation:** Before executing, EA performs final checks:
   - Confidence score meets minimum threshold (≥60%)
   - No news blackout active
   - Session filter allows trading
   - Spread is acceptable (≤ MaxSpreadMultiplier × average)
   - Account has sufficient margin for calculated lot size
   
2. **Order Placement:**
   - Calculate lot size from RiskPercentPerTrade and SL distance
   - Apply confidence-based adaptive sizing multiplier
   - Apply news-based reduction if news event is nearby
   - Place market order with Entry, SL, TP1, TP2
   - Record trade in signal history for self-learning

**Part B: Active Trade Management**
1. **Real-Time Monitoring:** Every tick, EA monitors:
   - Current price vs. SL/TP1/TP2 levels
   - Floating P/L (profit/loss)
   - Trade duration vs. expected duration
   - Confidence score (recalculated every bar)
   - CVD divergence status
   - News calendar status
   - Market regime status
   
2. **Partial Close Execution:**
   - When price hits TP1: Close PartialTP_Percentage of position
   - Move SL to breakeven + buffer
   - Update dashboard with partial close status
   
3. **Breakeven Trigger:**
   - When floating profit reaches BreakevenTrigger_ATR × ATR
   - Move SL to entry price + small buffer (0.5 pips)
   - Position now has zero risk
   
4. **Intelligent Trailing Stop Execution:**
   - Determine current profit phase (0-50%, 50-80%, 80%+)
   - Select trailing method (ATR → Chandelier → Fractal)
   - Calculate base trailing distance based on timeframe
   - Apply context multipliers (confidence, regime, divergence, news)
   - Calculate final trailing distance
   - Update SL to current price - final trailing distance (for BUY)
   - Only move SL in profit direction (never backward)
   - Execute SL modification order
   
5. **Time-Based Exit Execution:**
   - Monitor trade age vs. expected duration
   - When trade age > expected duration:
     - If TimeExitAction = "Close at Market" → Close position immediately
     - If TimeExitAction = "Move TP Closer" → Modify TP to 50% of remaining distance
     - If TimeExitAction = "Start Trailing" → Switch to trailing mode (already active)

**Part C: Trade Closure and Learning**
1. **Closure Triggers:** Trade closes when any of these occur:
   - Price hits SL (loss or breakeven)
   - Price hits TP1 (partial close) or TP2 (full close)
   - Time-based exit triggered
   - CVD divergence auto-close (if enabled)
   - Manual close by user
   
2. **Trade Outcome Recording:**
   - Record signal conditions at entry (confidence, regime, factors, etc.)
   - Record trade outcome (WIN if profit > 0, LOSS if profit ≤ 0)
   - Record actual P/L, RR achieved, duration held
   - Save to local file: `MQL5/Files/Gaeni_LearningData/[symbol]_[TF]_trades.dat`
   
3. **Self-Learning Update:**
   - Every ModelUpdateFrequency trades, update logistic regression model
   - Analyze which conditions lead to winning signals
   - Adjust confidence weights for future signals
   - Update parameter optimization data

**Part D: Dashboard and Alert Updates**
1. **Real-Time Dashboard Updates:**
   - Update floating P/L (dollar amount)
   - Update current confidence score with trend arrow
   - Update STATUS line (e.g., "Trailing — SL at 1.08650, +$20.10 protected")
   - Show partial close status if applicable
   - Show trailing stop method and distance
   
2. **Alert Triggers:**
   - When TP1 hit: Send alert "TP1 Hit — 50% closed at +$210"
   - When breakeven reached: Send alert "Breakeven — SL moved to entry"
   - When trade closed: Send alert with final P/L
   - When confidence drops significantly: Send warning alert
   - When divergence detected: Send warning alert

**Example: Complete Auto Trading Lifecycle**

```
Signal Given:
  → Confidence: 82%
  → Direction: BUY
  → Entry: 1.08450
  → SL: 1.08280 (17 pips)
  → TP1: 1.08620 (17 pips)
  → TP2: 1.09120 (67 pips)
  → Calculated lot: 0.5 lots (Normal sizing profile)

Trade Executed:
  → Order placed with 0.5 lots
  → SL/TP1/TP2 set
  → Dashboard shows "Signal active — Waiting for price movement"
  → Alert sent: "BUY signal — Entry 1.08450"

Price Moves Up:
  → Price reaches 1.08535 (+8.5 pips)
  → Floating P/L: +$42.50
  → Confidence: 85% (rising)
  → Dashboard shows "Signal active — Price +$42.50 toward TP1"

TP1 Hit:
  → Price reaches 1.08620 (+17 pips)
  → Close 50% (0.25 lots) at +17 pips = +$212.50 profit
  → Move SL to 1.08455 (breakeven + 0.5 pip)
  → Dashboard shows "TP1 hit ✓ (+$212.50) — 50% closed, SL moved to breakeven"
  → Alert sent: "TP1 Hit — 50% closed at +$212.50"

Price Continues:
  → Price reaches 1.08800 (+35 pips from entry)
  → Floating P/L on remaining 0.25 lots: +$87.50
  → Profit phase: 55% toward TP2 → Phase 2 (Chandelier trailing)
  → Trailing distance: 2.5× ATR = 50 pips
  → Context multipliers: 0.9 (confidence 80%) × 1.0 (trending) = 0.9
  → Final trail: 50 × 0.9 = 45 pips
  → SL moved to 1.08650 (45 pips behind current price)
  → Dashboard shows "Trailing — SL at 1.08650, +$20 protected"

Price Reverses:
  → Price drops to 1.08650
  → SL hit at 1.08650
  → Close remaining 0.25 lots at +20 pips = +$50 profit
  → Dashboard shows "Signal closed — Final P/L: +$262.50"
  → Alert sent: "Trade closed — Total profit: +$262.50"
  → Trade recorded in learning database as WIN

Total Result:
  → 50% closed at +17 pips = +$212.50
  → 50% closed at +20 pips = +$50.00
  → Total profit: +$262.50
  → Trade duration: 45 minutes
  → Outcome: WIN
  → Self-learning updated
```

**Why this matters:**
- **Fully automated:** Signal → Trade → Management → Closure → Learning
- **Intelligent execution:** Adapts lot size, trailing, exits to market conditions
- **Profit protection:** Partial close + breakeven + trailing = no more wiped profits
- **Continuous learning:** Every trade improves future signals
- **Transparent:** Dashboard and alerts show every action in real-time
- **Safe:** Multiple protection layers (SL, breakeven, trailing, time exit, divergence)

---

## 6. ENTRY / SL / TP CALCULATION LOGIC

### Entry Point
```
IF BUY signal:
  - Check if price is near a bullish Order Block
  - If YES → Entry = Order Block high (better price)
  - If NO → Entry = Current price

IF SELL signal:
  - Check if price is near a bearish Order Block
  - If YES → Entry = Order Block low (better price)
  - If NO → Entry = Current price
```

### Stop Loss
```
IF BUY:
  - SL = Below the Order Block low OR below recent swing low
  - Minimum SL = 1.0 × ATR (from current timeframe)
  - Ensure SL is below Premium/Discount boundary

IF SELL:
  - SL = Above the Order Block high OR above recent swing high
  - Minimum SL = 1.0 × ATR (from current timeframe)
  - Ensure SL is above Premium/Discount boundary
```

### Take Profit
```
IF BUY:
  - TP1 (conservative) = Nearest FVG above or Value Area High
  - TP2 (standard) = Nearest POC / Naked POC above
  - TP3 (aggressive) = Next major liquidity pool
  - Display the most likely TP based on confidence score:
    - 75%+ confidence → show TP2
    - 60-75% confidence → show TP1

IF SELL:
  - TP1 (conservative) = Nearest FVG below or Value Area Low
  - TP2 (standard) = Nearest POC / Naked POC below
  - TP3 (aggressive) = Next major liquidity pool below
  - Same confidence-based TP selection
```

### Risk-Reward Check
```
- Calculate RR ratio = (TP distance) / (SL distance)
- If RR < 1.5 → reject signal (not worth the risk)
- If RR >= 1.5 → show signal
- If RR >= 2.5 → mark as "HIGH RR" bonus
```

### Expected Duration
```
Based on dynamic calculation (ATR, momentum, distance to TP):
  Formula: Duration = (Distance to TP) / (ATR × Momentum Factor)
  
  Examples (will vary based on actual conditions):
  Low volatility + strong momentum → longer duration
  High volatility + weak momentum → shorter duration
  
  The EA recalculates this for every signal, not hardcoded by timeframe.
```

---

## 7. VISUAL DASHBOARD (On-Chart Panel)

**Implementation status: IMPLEMENTED (Step 0 + Phases 1–3 Live) — `Include/Gaeni/Gaeni_Dashboard.mqh`.**
> Shows **exactly the Section 7 card and nothing else** (no extra panel, button or telemetry drawer).
> - **Palette (user decision 2026-10-06):** one dark grey card with a single soft light-grey text colour
>   (`GAENI_PANEL_BG` #2B2B2B, `GAENI_HEADER_BG` #363636, text `GAENI_TEXT_COLOR` #D3D3D3, separators #787878).
>   **Only the SIGNAL line is coloured** — BUY / SELL / HOLD use the `BullColor` / `BearColor` / `NeutralColor`
>   inputs (default Lime / Red / Gray); regime, confidence, Entry/SL/TP, Risk:Reward, Session, WHY and STATUS all
>   use the same light grey text.
> - **Rows:** Header, Regime, SIGNAL, Confidence, Entry, Stop Loss, Take Profit, Risk:Reward, Session + Expected
>   Duration, WHY (two lines), STATUS. Phase 2 Supertrend and Phase 3 SMC summaries are composed into WHY;
>   OB/FVG rectangles and swing/equal-liquidity/equilibrium levels are chart overlays, not dashboard rows.
>   The `WHY` block wraps onto a second line when needed and the card is one
>   row shorter when it fits on one (the panel keeps a fixed size while trading).
> - **Pending Phase 5/6 data:** until the Signal Engine lands, `SIGNAL` shows `⏸ WAIT`, `Confidence` shows
>   `--% → --% →`, and `Entry / SL / TP / Risk:Reward` show `--` / `$0.00`. Those fields already read from
>   `SGaeniDashboardState`, so Phases 5–6 fill them without any interface change.
> - **Market Closed Mode:** the compact `MARKET CLOSED` card below (Auto Trading forced OFF).

```
╔═══════════════════════════════════════════════════════════╗
║  Gaeni V1.0 | EURUSD | TF: M15 | Auto Trading: ON        ║
║  ──────────────────────────────────────────────────────  ║
║  Regime: TRENDING (Bullish)                              ║
║  ──────────────────────────────────────────────────────  ║
║  SIGNAL: ▲ BUY                                           ║
║  Confidence: 82% → 85% ↑                                ║
║  ──────────────────────────────────────────────────────  ║
║  Entry:        1.08450 / $142.50                         ║
║  Stop Loss:    1.08280 / $170.00                         ║
║  Take Profit:  1.09120 / $670.00                         ║
║  Risk:Reward:  1:3.9                                     ║
║  Session: London | Expected Duration: ~2-4 hours         ║
║  ──────────────────────────────────────────────────────  ║
║  WHY: Supertrend bullish + OB support at 1.0845 +        ║
║       CVD rising (buyers dominant) + H1 agrees up        ║
║  ──────────────────────────────────────────────────────  ║
║  STATUS: Signal active — Price +$45.20 toward TP1        ║
╚═══════════════════════════════════════════════════════════╝
```

### Dashboard Field Descriptions

| Field | What It Shows |
|-------|---------------|
| **Header line** | `Gaeni V1.0` + Symbol + Timeframe + `Auto Trading: ON` or `Auto Trading: OFF` |
| **Regime** | Current market state: `TRENDING (Bullish/Bearish)` / `RANGING` / `VOLATILE` / `TRANSITION` / `MARKET CLOSED` |
| **SIGNAL** | ▲ BUY or ▼ SELL or ⏸ WAIT |
| **Confidence** | Live confidence score that updates every bar. Shows initial → current score with arrow (↑ rising, ↓ falling, → stable). Examples: `82% → 85% ↑` / `72% → 68% ↓` / `79% → 79% →` |
| **Entry** | Price level + dollar amount at risk (lot size × price distance) |
| **Stop Loss** | SL price level + dollar amount at risk from entry |
| **Take Profit** | TP price level + dollar amount of profit if reached |
| **Risk:Reward** | Ratio of potential profit vs risk |
| **Session + Duration** | Current trading session (Asia/London/NY) + how long to expect the signal |
| **WHY** | Plain-language explanation of which factors agree and why this direction was chosen. Updates with every signal change. |
| **STATUS** | Real-time single line showing what EA is doing right now (examples below). |

### Dollar Amount Calculation

Each price level shows both the price and the dollar impact based on current lot size:

```
Entry $amount = Current lot size × Contract size × Price (converted to account currency)
SL    $amount = Current lot size × Contract size × (Entry Price - SL Price)
TP    $amount = Current lot size × Contract size × (TP Price - Entry Price)

For BUY:
  SL dollar = loss if SL hit
  TP dollar = profit if TP hit

For SELL:
  SL dollar = loss if SL hit
  TP dollar = profit if TP hit
```

### Market Closed Display

When market is closed (weekend, holiday, or outside trading hours):

```
╔═══════════════════════════════════════════════════════════╗
║  Gaeni V1.0 | EURUSD | TF: M15 | Auto Trading: OFF       ║
║  ──────────────────────────────────────────────────────  ║
║  Regime: MARKET CLOSED                                   ║
║  ──────────────────────────────────────────────────────  ║
║  SIGNAL: ⏸ NO SIGNAL                                     ║
║  ──────────────────────────────────────────────────────  ║
║  WHY: Market closed — EA paused, no analysis needed      ║
║  ──────────────────────────────────────────────────────  ║
║  STATUS: Paused — Waiting for market to open             ║
╚═══════════════════════════════════════════════════════════╝
```

- Auto Trading shows `OFF` when market is closed
- Regime shows `MARKET CLOSED`
- SIGNAL shows `⏸ NO SIGNAL`
- STATUS shows `Paused — Waiting for market to open`
- EA resumes automatically when market opens (new candle detected)

### STATUS Line Examples

| Situation | STATUS Shows |
|-----------|--------------|
| Signal just given, no movement yet | `Signal active — Waiting for price movement` |
| Price moving toward TP | `Signal active — Price +$45.20 toward TP1` |
| Price near TP | `Signal active — Price $8.50 away from TP1` |
| TP1 hit, partial close done | `TP1 hit ✓ (+$420) — 50% closed, SL moved to breakeven` |
| Breakeven reached, trailing active | `Breakeven ✓ — Trailing SL active, locking profit` |
| Trailing stop active | `Trailing — SL at 1.08650, +$20.10 protected` |
| Price moving against | `Signal active — Price -$32.10, SL intact at 1.08280` |
| Signal resolved (hit TP/SL) | `Signal closed — Scanning for next setup` |
| CVD divergence detected | `⚠ Divergence — Price making new high but CVD weakening, confidence reduced` |
| Time-based exit triggered | `Time expired — Switching to trailing stop` |
| News blackout active | `News Blackout — NFP in 15 minutes, trading blocked` |
| News reduce size active | `News Warning — NFP in 20 minutes, position size reduced 50%` |
| Asian session blocked | `Session Filter — Asian session, low liquidity for forex` |
| Auto Trading OFF by user | `Auto Trading OFF — Signals shown but no trades placed` |
| Confidence rising during active trade | `Signal strong — Confidence up to 87% ↑` |
| Confidence dropping during active trade | `Warning — Confidence down to 58% ↓ — Consider caution` |
| Confidence critically low during trade | `Weak signal — Confidence 42% ↓ — Suggest early exit` |
| Adaptive sizing active (high confidence) | `Strong signal — Position size increased to 1.5× (confidence 88%)` |
| Adaptive sizing active (low confidence) | `Uncertain signal — Position size reduced to 0.7× (confidence 65%)` |
| Waiting for structure to confirm | `Watching — Waiting for CHoCH to confirm reversal` |
| Bad regime, no signal | `Waiting — Market ranging, no high-quality setup` |
| Transition regime | `Watching — Market transitioning, monitoring for new direction` |
| Confidence too low | `Scanning — Factors detected but confidence only 48%` |
| Self-learning updating | `Learning — Updating model from last 5 resolved signals` |
| Volatile market | `Protecting — High volatility detected, signals paused` |
| Market closed | `Paused — Waiting for market to open` |

---

## 8. PHASED DEVELOPMENT PLAN

Each phase produces a testable EA that can be attached to a real MT5 chart for verification.
There is one EA file for the whole project (`Gaeni.mq5`); every phase extends it
instead of adding a new file per phase.

**Progress Overview:**
- **Step 0 (On-Chart Visual Dashboard Interface + EA Skeleton + All Input Parameters):** **IMPLEMENTED** (`Experts/Gaeni/Gaeni.mq5`, `Include/Gaeni/Gaeni_Dashboard.mqh`, `Include/Gaeni/Gaeni_Types.mqh`). The Section 7 card is complete; signal-dependent fields still show waiting values until the signal-generation phases land.
- **Phase 1 (Foundation + Dynamic Parameter Engine + Market Regime Detection):** **IMPLEMENTED** (`Include/Gaeni/Gaeni_DynamicParams.mqh`, `Include/Gaeni/Gaeni_Regime.mqh`, `tests/test_phase1.cpp`). Live data populates `Header`, `Regime`, `Session`, `Expected Duration`, `WHY`, and `STATUS`.
- **Phase 2 (ML-Adaptive Supertrend):** **IMPLEMENTED (2026-10-06)** (`Include/Gaeni/Gaeni_Supertrend.mqh`, `tests/test_phase2.cpp`). Its K-Means volatility cluster, selected multiplier, direction, and trailing reference are shown in the existing `WHY` row; status clarifies that this component is trend context, not a trade signal.
- **Phase 3 (SMC Structure Detection):** **IMPLEMENTED (2026-10-06)** (`Include/Gaeni/Gaeni_SMC.mqh`, `tests/test_phase3.cpp`). Confirmed swings, OB/FVG zones, BOS/CHoCH, liquidity pools/sweeps, and Premium/Discount context populate the existing `WHY` row; price levels are drawn as chart overlays without adding a panel or dashboard row.
- **Phases 4–9:** **PENDING.** The Section 7 card remains the single on-chart panel; future component context will be composed into the existing display rows.

---

### Step 0: Visual Dashboard Interface + EA Skeleton (Foundation UI)
**Status: IMPLEMENTED (2026-10-06)** — Full Section 7 On-Chart Visual Dashboard (`Include/Gaeni/Gaeni_Dashboard.mqh`), all Section 10 input parameters (`Gaeni.mq5`), dollar-impact calculator (`GaeniCalculateDollarAmounts`), Market Closed compact view, two-line WHY block and the user-approved light-grey-on-dark-grey palette (only the SIGNAL line carries colour). No extra panels or buttons.

---

### Phase 1: Foundation + Market Regime Detection
**Status: IMPLEMENTED (2026-10-06)** — Implemented in `Gaeni.mq5`, `Include/Gaeni/Gaeni_DynamicParams.mqh`, and `Include/Gaeni/Gaeni_Regime.mqh`, and verified with `tests/test_phase1.cpp`. Symbol auto-detection, 200-bar ATR volatility percentile, dynamic parameter matrix, market-state lookback adaptation, parameter self-optimization persistence, closed-bar Kaufman ER, ATR(14)/ATR(50), KAMA(Fast/Med/Slow), Bollinger Band Width/Squeeze, Daily & Session VWAP, Session/Spread filters, and 5-state Market Regime Detection (`TRENDING (Bullish/Bearish)`, `RANGING`, `VOLATILE`, `TRANSITION`, `MARKET CLOSED`) are live and populating the dashboard interface.

**What gets built:**
- EA skeleton (OnInit, OnCalculate, OnTimer structure)
- Kaufman ER, ATR, KAMA, Bollinger Band, VWAP calculations
- Market regime classification logic (Trending/Ranging/Volatile/Transition)
- Basic dashboard panel showing ONLY regime status
- Timeframe-adaptive parameters (M5/M15/M30 behavior)

**What you can test on chart:**
- Does regime detection correctly identify market state?
- Does it switch regimes at the right times?
- Does M5/M15/M30 produce different lookback results?

**Layout fix (2026-10-06):** `Gaeni.mq5` moved to `Experts/Gaeni/Gaeni.mq5` and its includes changed to `#include <Gaeni\…>` so MetaEditor resolves them from `MQL5\Include\Gaeni\`; `Gaeni_Dashboard.mqh` moved from `Include/` into `Include/Gaeni/`. Guarded by `tests/check_include_layout.py`, `tests/ea_tu_build.py` and CI.

**Include fix (2026-10-07):** `Gaeni.mq5` now includes the six headers as quoted, repo-relative paths (`#include "../../Include/Gaeni/Gaeni_Types.mqh"`), which MetaEditor resolves relative to the including file (relative `..` segments are documented in the MetaEditor help). Because the repository mirrors the data folder, the identical path resolves to `<repo>\Include\Gaeni\` in the checkout and to `MQL5\Include\Gaeni\` after the copy — so pressing F7 on the checkout compiles with `0 errors, 0 warnings` and no header installation. The previous angle-bracket form (`#include <Gaeni\…>`) searched `MQL5\Include` only and failed on a raw checkout with `file 'Include\Gaeni\Gaeni_Types.mqh' not found   Gaeni.mq5 14 10`. `tests/check_include_layout.py` and `tests/ea_tu_build.py` now reject the angle-bracket form and verify that every quoted include resolves.

**Files produced:** `Gaeni.mq5`, `Include/Gaeni/Gaeni_Types.mqh`, `Include/Gaeni/Gaeni_DynamicParams.mqh`, `Include/Gaeni/Gaeni_Regime.mqh`, `Include/Gaeni/Gaeni_Dashboard.mqh`

---

### Phase 2: ML-Adaptive Supertrend
**Status: IMPLEMENTED (2026-10-06)** — `Include/Gaeni/Gaeni_Supertrend.mqh`, integrated in `Experts/Gaeni/Gaeni.mq5` and verified by `tests/test_phase2.cpp` plus the EA translation-unit smoke test.

**Implemented behavior:**
- Collects closed-bar ATR values over the dynamic K-Means training window and fits three ordered one-dimensional K-Means clusters: Calm, Normal, and Wild.
- Tests five candidate multipliers spanning the symbol/volatility matrix range. For each ATR cluster, it selects the multiplier with the best mean ATR-normalized next-closed-bar directional return; a small direction-flip penalty discourages noisy settings. Sparse clusters use a conservative cluster-position fallback.
- Rebuilds Supertrend final bands and direction from closed bars only. The current line is exposed as a trailing reference; index 0 (the forming bar) is never used.
- Retrains K-Means every `max(1, training window / 20)` closed bars, and immediately when the ATR period, training window, or multiplier range changes.
- Publishes direction, cluster, selected multiplier, and line value through `p2SupertrendLine` and the existing `WHY` row; the existing `STATUS` row labels this as trend context only. The Section 7 card layout remains unchanged and Phase 2 does not create a standalone BUY/SELL trade signal.

**What you can test:**
- Does K-Means separate the recent ATR distribution into ordered volatility groups?
- Does the cluster-specific multiplier adapt after volatility or parameter changes?
- Does the closed-bar Supertrend direction/line follow sustained bull and bear trends without repainting?

**Files integrated into:** `Experts/Gaeni/Gaeni.mq5` + `Include/Gaeni/Gaeni_Supertrend.mqh`

---

### Phase 3: SMC Structure Detection
**Status: IMPLEMENTED (2026-10-06)** — `Include/Gaeni/Gaeni_SMC.mqh`, integrated into `Experts/Gaeni/Gaeni.mq5` and verified by `tests/test_phase3.cpp` plus the EA translation-unit smoke test.

**Implemented behavior:**
- Detects strength-2 swing highs/lows only after both sides are confirmed by closed candles; equal-price plateaus resolve to one pivot.
- Replays confirmed swing levels chronologically. A closed-bar break in the current structural direction is BOS; a break against the established bias is CHoCH. Wick-only breaks are tracked as buy-/sell-side liquidity sweeps, and repeated swing levels within 0.1 ATR are marked as equal-high/low liquidity pools.
- Finds bullish/bearish Order Blocks as the nearest opposing candle before a displacement body at least 1.5× the preceding average body, with the impulse close beyond the block. Blocks are revisited/mitigated on a later closed-bar touch and invalidated only by a close through the far edge.
- Detects three-candle non-overlap FVGs in both directions. A partial revisit is marked mitigated; a gap remains active until a later closed candle fills it through the far edge.
- Calculates the 50% equilibrium of the latest confirmed swing-high/low dealing range and classifies current closed price as Premium, Discount, or Equilibrium.
- Publishes the active structure event, zone, nearest valid OB and FVG summary through `p3SmcLine` into the existing Section 7 `WHY` row. Chart overlays draw active OB/FVG rectangles plus swing, equal-liquidity, and equilibrium levels; no extra dashboard row or telemetry panel is added.
- Uses the dynamic `smcOrderBlockLookback` and never reads index 0 (the forming candle); insufficient history resets state rather than leaving stale levels.

**What you can test on chart:**
- Are Order Blocks correctly identified and invalidated/mitigated as price revisits them?
- Are bullish and bearish FVGs accurate, including partial and full fills?
- Do Premium/Discount zones reflect the latest confirmed swing range?
- Do close-confirmed CHoCH/BOS and wick liquidity sweeps align with observed structure?
- Do overlays track the active zones without changing the Section 7 card layout?

**Files integrated into:** `Experts/Gaeni/Gaeni.mq5`, `Include/Gaeni/Gaeni_Types.mqh`, and `Include/Gaeni/Gaeni_SMC.mqh`; tests: `tests/test_phase3.cpp`

---

### Phase 4: Volume Profile + CVD
**Status: PENDING (Interface Already Created — Data Will Populate Into `p4VolumeLine` and `WHY` on Completion)**

**What gets built:**
- Tick volume data collection
- Volume Profile calculation (POC, VAH, VAL)
- Naked POC detection (unvisited high-volume levels)
- Cumulative Volume Delta (CVD) calculation
- Dashboard update: Populate pre-created `[VOL P4]` row + `WHY` line with POC, VAH/VAL, Naked POC, and CVD buyer/seller pressure

**What you can test on chart:**
- Does POC align with obvious support/resistance?
- Does CVD direction match visible buying/selling?
- Are Naked POCs acting as magnets?

**Files integrated into:** `Gaeni.mq5` + `Include/Gaeni/Gaeni_Volume.mqh`

---

### Phase 5: Multi-Timeframe Agreement
**Status: PENDING (Interface Already Created — Data Will Populate Into `p5MtfLine` and `WHY` on Completion)**

**What gets built:**
- Higher timeframe data fetching (using CopyRates with TF parameter)
- ML-Adaptive Supertrend running on higher TF
- Market Regime Detection on higher TF
- Agreement logic (current TF + higher TF must align)
- Dashboard update: Populate pre-created `[MTF P5]` row + `WHY` line with Higher TF (`M15`/`H1`/`H4`) trend & regime agreement

**What you can test on chart:**
- Does higher TF analysis match what you see on that TF chart?
- Does agreement filtering correctly block bad signals?
- M5→M15, M15→H1, M30→H4 pairs all working?

**Files integrated into:** `Gaeni.mq5` + `Include/Gaeni/Gaeni_MTF.mqh`

---

### Phase 6: Confidence Engine + Signal Output + Auto Trading
**Status: PENDING (Interface Already Created — Data Will Populate Into `SIGNAL`, `Confidence`, `Entry`, `Stop Loss`, `Take Profit`, `Risk:Reward`, `Expected Duration`, `WHY`, `STATUS`, and `p6ConfidenceLine` on Completion)**

**What gets built:**
- Weighted scoring system combining all 5 previous components
- Confidence percentage calculation
- Signal threshold logic (75%+ Very Strong, 65-74% Strong, 55-64% Moderate, 45-54% Normal, 40-44% Ranging, <40% Hold)
- Entry point calculation (Order Block or current price)
- SL calculation (SMC structure + ATR minimum)
- TP calculation (FVG, POC, liquidity levels)
- Risk:Reward ratio check (minimum 1.5)
- Dynamic duration estimation based on ATR, momentum, and distance to TP
- Full dashboard with all signal information (populates pre-created `SIGNAL`, `Confidence`, `Entry/SL/TP` + `$` amounts, `Risk:Reward`, and `[SIG P6]` rows)
- Signal management system (structure invalidation, not fixed cooldown)
- Auto-trading execution (place orders when signal given)
- Trade management (monitor position, update STATUS line)

**What you can test on chart:**
- Do signals appear only when multiple factors agree?
- Are entry/SL/TP levels logical?
- Is the dashboard clear and useful?
- Does structure-based invalidation work correctly?
- Does auto-trading execute properly?

**Files integrated into:** `Gaeni.mq5` + `Include/Gaeni/Gaeni_Confidence.mqh`

---

### Phase 7: Self-Learning Filter
**Status: PENDING (Interface Already Created — Data Will Populate Into `p7LearningLine`, `Confidence`, and `STATUS` on Completion)**

**What gets built:**
- Signal history recording (conditions at time of signal)
- Trade outcome tracking (TP hit / SL hit / duration expired)
- Online logistic regression model (native MQL5 SGD)
- Feature extraction from signal conditions
- Model weight persistence (save/load from file)
- Integration into confidence engine (as 6th factor)
- Dynamic weight adjustment based on self-learning accuracy
- Dashboard update: Populate pre-created `[LRN P7]` row with win/loss history, learned weights, and learning status

**What you can test on chart:**
- Does the EA correctly record signal outcomes?
- Does the model update after each resolution?
- Does it persist across restarts?
- After 20-30 signals, does confidence scoring improve?

**Files integrated into:** `Gaeni.mq5` + `Include/Gaeni/Gaeni_Learning.mqh`

---

### Phase 8: Advanced Trade Management + Auto Trading System
**Status: PENDING (Interface Already Created — Data Will Populate Into `p8TradeMgmtLine`, `Confidence`, and Live `STATUS` on Completion)**

**What gets built:**

**A. Partial TP + Intelligent Context-Aware Trailing Stop:**
- Monitor price vs. TP1 level
- Close PartialTP_Percentage of position when TP1 hit
- Move SL to breakeven when BreakevenTrigger_ATR reached
- **Intelligent Trailing System (4 Layers):**
  - Layer 1: Timeframe auto-detection (M5/M15/M30 → tight/medium/loose)
  - Layer 2: Multi-phase progression based on profit %
    - Phase 1 (0-50% profit) → ATR trailing (loose)
    - Phase 2 (50-80% profit) → Chandelier Exit (medium)
    - Phase 3 (80%+ profit) → Fractal trailing (tight)
  - Layer 3: Context multipliers (confidence/regime/divergence/news)
  - Layer 4: User override via TrailingMode parameter
- Calculate final trailing distance: baseTrail × confidence × regime × divergence × news
- Update SL every bar (not every tick)

**B. Tick-Level CVD Divergence:**
- Tick-by-tick CVD calculation (buyer vs seller classification)
- Divergence detection (price vs CVD disagreement)
- Action based on DivergenceAction setting (reduce confidence/auto close/warning)
- Dashboard warning display

**C. Time-Based Exit:**
- Monitor trade duration vs. expected duration
- Trigger action when time expires based on TimeExitAction setting
- Implement close/move TP/trailing stop logic

**D. News/Economic Calendar Filter:**
- Access MT5 Economic Calendar API
- Filter events by impact level (high/medium/low)
- Apply NewsBufferMinutes blackout window
- Action based on NewsAction setting (block/reduce/warning)
- Dashboard status display

**E. Trading Session Filter:**
- Auto-detect session times based on broker server time
- Filter trades based on AllowLondonSession/AllowNewYorkSession/AllowAsianSession
- Auto-enable Asian session for crypto symbols
- Dashboard status display

**F. Confidence-Based Adaptive Position Sizing:**
- Calculate base lot size from RiskPercentPerTrade
- Apply confidence multiplier based on SizingProfile
- Enforce broker min/max lot limits
- Dashboard display of position size adjustment

**G. Auto Trading Functions:**
- **Signal-to-Trade Execution:**
  - Final validation checks (confidence, news, session, spread, margin)
  - Order placement with calculated lot size
  - Set SL/TP1/TP2 levels
  
- **Active Trade Management:**
  - Real-time monitoring (price, P/L, duration, confidence, CVD, news, regime)
  - Partial close execution at TP1
  - Breakeven trigger execution
  - Intelligent trailing stop execution (4-layer system)
  - Time-based exit execution
  
- **Trade Closure and Learning:**
  - Closure triggers (SL/TP1/TP2 hit, time exit, divergence close, manual)
  - Trade outcome recording (conditions, outcome, P/L, RR, duration)
  - Save to local file: MQL5/Files/Gaeni_LearningData/[symbol]_[TF]_trades.dat
  - Self-learning update (every ModelUpdateFrequency trades)
  
- **Dashboard and Alert Updates:**
  - Real-time dashboard updates (floating P/L, confidence, STATUS line)
  - Alert triggers (TP1 hit, breakeven, trade closed, confidence drop, divergence)

**What you can test on chart:**
- Does partial TP close the correct percentage at TP1?
- Does breakeven move SL correctly when trigger reached?
- Does intelligent trailing system:
  - Auto-detect timeframe and set appropriate tightness?
  - Switch methods at 50% and 80% profit thresholds?
  - Adjust tightness when confidence drops?
  - Go emergency tight when divergence detected?
  - Respect user override (Force Tight/Medium/Loose)?
- Does CVD divergence detect correctly?
- Does time-based exit trigger at expected duration?
- Does news filter block/reduce correctly around high-impact events?
- Does session filter work correctly (Asian session blocked for forex, allowed for crypto)?
- Does adaptive sizing adjust position size based on confidence?
- Does auto trading execute orders correctly with calculated lot size?
- Does trade management system (partial close, breakeven, trailing) work end-to-end?
- Does trade outcome get recorded correctly in learning database?
- Does dashboard show real-time updates (floating P/L, confidence, trailing status)?
- Do alerts fire at correct moments (TP1 hit, breakeven, trade closed)?

**Files integrated into:** `Gaeni.mq5` + `Include/Gaeni/Gaeni_TradeManagement.mqh`

---

### Phase 9: Polish + Optimization
**Status: PENDING (Interface Already Created — Data Will Populate Into `p9StatsLine` and Chart Level Lines on Completion)**

**What gets built:**
- Alert system (popup, push notification, email)
- Sound alerts for signal changes
- Signal history log (CSV export)
- Visual lines on chart (entry, SL, TP drawn as horizontal lines)
- Color coding (green=strong, yellow=moderate, gray=waiting)
- Performance statistics panel (win rate, avg RR, best session — populates pre-created `[STS P9]` row)
- Input parameters for user customization
- Final code cleanup and comments

**What you can test on chart:**
- Full EA running with all features
- Can you customize key parameters?
- Are alerts working?
- Does the chart look clean and informative?

**Files integrated into:** `Gaeni.mq5` + `Include/Gaeni/Gaeni_AlertsAndStats.mqh`

---

## 9. TECHNICAL NOTES

### All Native MQL5 — No External Dependencies
- K-Means: Implemented in pure MQL5 (C++ style arrays)
- Logistic Regression: Implemented in pure MQL5 with SGD
- Volume Profile: Built from MT5 tick volume data (CopyTicks)
- SMC: Pure price action calculations
- No Python, no ONNX, no DLL, no external files needed (except own save file for self-learning model persistence)

### Performance Considerations
- K-Means recalculation: Every N bars (not every tick)
- Volume Profile: Updated on new bar only
- Self-learning: Updated only when signal resolves
- Dashboard: Refreshed every 1 second via OnTimer
- All heavy calculations use closed bars only (no repainting)

### No Repainting Guarantee
- All signals generated on CLOSED bars only
- No indicator uses the current forming bar for decisions
- Signal once given does NOT change until it expires or is invalidated by a new signal
- What you see in history is exactly what appeared in real-time

---

## 10. INPUT PARAMETERS (User Customizable)

### Design Philosophy: Minimal Inputs, Maximum Automation

Gaeni uses a **Dynamic Parameter Engine** that automatically calculates ALL indicator parameters based on:
- Symbol type (Forex, Gold, Crypto, Indices)
- Current volatility regime (Low/Normal/High)
- Market state (Trending/Ranging/Volatile/Transition)
- Historical performance tracking

**The user does NOT need to set any indicator parameters.** The EA figures everything out automatically and adapts continuously. Only high-level behavior controls and display settings are exposed.

```mql5
// ═══════════════════════════════════════════════════════
// TRADING CONTROL
// ═══════════════════════════════════════════════════════
input bool   EnableAutoTrading = true;
// ON: EA places trades automatically when signals meet confidence threshold
// OFF: Signals shown on dashboard but no trades executed (observation mode)

input double RiskPercentPerTrade = 1.0;
// Risk as percentage of account balance per trade (default 1%)
// Used to calculate lot size: LotSize = (Balance × Risk%) / (SL distance in $)

input int    MaxOpenTrades = 1;
// Maximum number of simultaneous open positions (default 1)
// Set to 0 for unlimited (not recommended)

// ═══════════════════════════════════════════════════════
// DYNAMIC PARAMETER ENGINE
// ═══════════════════════════════════════════════════════
input enum ENUM_SYMBOL_CLASS SymbolOverride = SYMBOL_CLASS_AUTO;
// "Auto Detect" = EA detects symbol type automatically (recommended)
// Or manually select: "Forex Major", "Forex Cross", "Metals", "Crypto", "Indices"
// Only change if EA misidentifies your broker's symbol naming

input double VolatilitySensitivity = 1.0;
// Controls how aggressively parameters adapt to volatility changes
// 0.5 = Slower, more conservative adaptation
// 1.0 = Normal adaptation speed (recommended)
// 1.5 = Faster, more aggressive adaptation (may overreact to short spikes)

input bool   EnableParameterOptimization = true;
// ON: EA tracks which parameter combinations work best and gradually favors winners
// OFF: Use only base parameter matrix without learning (loses self-improvement)

// ═══════════════════════════════════════════════════════
// SIGNAL MANAGEMENT
// ═══════════════════════════════════════════════════════
input enum ENUM_INVALIDATION_MODE StructureInvalidation = INVALIDATION_STRUCTURE;
// "Structure Based" = Signals invalidated when market structure breaks (CHoCH) — recommended
// "TP/SL Only" = Signals only close on TP/SL hit — not recommended
// "Structure + Time" = Signals invalidated on CHoCH OR after N candles without progress

input bool   EnableSpreadFilter = true;
// ON: Block signals when spread > 2× average (protects from bad fills)
// OFF: Ignore spread conditions

input int    MinCandlesBetweenSignals = 1;
// Minimum candles between new signals (prevents rapid-fire signals)
// Default 1 = Next signal allowed after 1 candle (fast response)
// Increase to 2-3 for slower, more selective signals

// ═══════════════════════════════════════════════════════
// SELF-LEARNING FILTER
// ═══════════════════════════════════════════════════════
input bool   EnableSelfLearning = true;
// ON: EA learns from signal outcomes and adjusts confidence scoring
// OFF: Confidence scoring based only on static factor weights

input int    ModelUpdateFrequency = 5;
// Update self-learning model after every N resolved signals
// Default 5 = Model updates after every 5 closed trades
// Lower = faster learning but less stable; Higher = slower but more stable

// ═══════════════════════════════════════════════════════
// PARTIAL TP + BREAKEVEN + TRAILING STOP
// ═══════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════
// PARTIAL TP + INTELLIGENT CONTEXT-AWARE TRAILING STOP
// ═══════════════════════════════════════════════════════
input bool   EnablePartialTP = true;
// ON: Close partial position at TP1, move SL to breakeven, let rest run to TP2
// OFF: Hold entire position until TP or SL hit

input double PartialTP_Percentage = 50.0;
// Percentage of position to close at TP1 (default 50%)
// Range: 20-80%. Remaining position runs to TP2 with intelligent trailing stop.

input double BreakevenTrigger_ATR = 1.0;
// Move SL to breakeven when price reaches this multiple of ATR in profit
// Default 1.0 = Move to BE after 1× ATR profit (e.g., if ATR=20 pips, move BE at +20 pips)
// Range: 0.5-2.0. Lower = earlier protection, higher = more room for pullback.

input enum ENUM_TRAILING_MODE TrailingMode = TRAILING_AUTO;
// "Auto" = EA chooses trailing tightness based on timeframe (recommended)
//   M5: Tight (1.0× ATR) - captures small moves
//   M15: Medium (1.5× ATR) - balanced
//   M30: Loose (2.0× ATR) - allows big moves to develop
// "Force Tight" = always use M5-style trailing (tight)
// "Force Medium" = always use M15-style trailing (medium)
// "Force Loose" = always use M30-style trailing (loose)

input bool EnableContextAwareTrailing = true;
// ON: Trailing adapts to confidence, regime, divergence, news (recommended)
//   - Confidence drop → tighter trail
//   - Divergence detected → emergency tight trail
//   - Volatile regime → wider trail
//   - News coming → wider trail or close
// OFF: Trailing uses fixed phase rules only (no context adaptation)

// Intelligent Trailing System (4 Layers):
// Layer 1: Timeframe auto-detection (M5/M15/M30 → tight/medium/loose)
// Layer 2: Multi-phase progression (profit % determines method)
//   Phase 1 (0-50% profit) → ATR trailing (loose, let trade breathe)
//   Phase 2 (50-80% profit) → Chandelier Exit (medium, lock profit)
//   Phase 3 (80%+ profit) → Fractal trailing (tight, protect maximum)
// Layer 3: Context multipliers (confidence/regime/divergence/news adjust tightness)
// Layer 4: User override (TrailingMode parameter above)

// ═══════════════════════════════════════════════════════
// TICK-LEVEL CVD DIVERGENCE
// ═══════════════════════════════════════════════════════
input bool   EnableTickDivergence = true;
// ON: Monitor tick-level CVD divergence for early reversal warnings
// OFF: Feature disabled

input enum ENUM_DIVERGENCE_ACTION DivergenceAction = DIVERGENCE_REDUCE;
// "Reduce Confidence" → lowers signal confidence by 15-20% when divergence detected
// "Auto Close" → closes position immediately when divergence detected
// "Warning Only" → shows warning on dashboard but does nothing

// ═══════════════════════════════════════════════════════
// TIME-BASED TP ADJUSTMENT
// ═══════════════════════════════════════════════════════
input bool   EnableTimeExit = true;
// ON: Auto-manage trades that exceed expected duration
// OFF: Hold until TP or SL hit (not recommended)

input enum ENUM_TIME_EXIT_ACTION TimeExitAction = TIME_EXIT_TRAIL;
// "Close at Market" → exit immediately when time expires
// "Move TP Closer" → move TP to 50% of remaining distance
// "Start Trailing" → switch to ATR-based trailing stop (recommended)

// ═══════════════════════════════════════════════════════
// NEWS/ECONOMIC CALENDAR FILTER
// ═══════════════════════════════════════════════════════
input bool   EnableNewsFilter = true;
// ON: Block/reduce trading around high-impact news events
// OFF: Trade regardless of news (not recommended)

input int    NewsBufferMinutes = 30;
// Minutes before AND after high-impact news to block trading
// Range: 15-60 minutes. Default 30 is industry standard.

input enum ENUM_NEWS_ACTION NewsAction = NEWS_ACTION_REDUCE;
// "Block All Trading" → no signals, no trades during blackout
// "Reduce Size 50%" → trade but with half position size (recommended)
// "Warning Only" → show warning on dashboard but allow full trading

// ═══════════════════════════════════════════════════════
// TRADING SESSION FILTER
// ═══════════════════════════════════════════════════════
input bool   EnableSessionFilter = true;
// ON: Trade only during selected sessions
// OFF: Trade 24 hours (not recommended)

input bool   AllowLondonSession = true;
// Allow trading during London session (07:00-16:00 GMT) - highest liquidity

input bool   AllowNewYorkSession = true;
// Allow trading during New York session (12:00-21:00 GMT) - second highest

input bool   AllowAsianSession = false;
// Allow trading during Asian session (22:00-07:00 GMT)
// Default OFF for forex/metals (low liquidity)
// AUTO-ENABLED for crypto pairs (crypto is 24hr liquid)
// Note: For crypto symbols, this setting is ignored and Asian session is always allowed

// ═══════════════════════════════════════════════════════
// CONFIDENCE-BASED ADAPTIVE POSITION SIZING
// ═══════════════════════════════════════════════════════
input bool   EnableAdaptiveSizing = true;
// ON: Position size scales with confidence score
// OFF: Fixed lot size based on RiskPercentPerTrade

input enum ENUM_SIZING_PROFILE SizingProfile = SIZING_NORMAL;
// "Minimum Lot" → 0.1x to 0.3x (safest, smallest possible position)
// "Conservative" → 0.5x to 1.0x (safer, smaller positions)
// "Normal" → 0.7x to 1.5x (balanced approach)
// "Aggressive" → 0.5x to 2.0x (bigger swings, higher risk)

// ═══════════════════════════════════════════════════════
// DISPLAY SETTINGS
// ═══════════════════════════════════════════════════════
input int    PanelX = 20;
// X position of dashboard panel (pixels from left edge)

input int    PanelY = 30;
// Y position of dashboard panel (pixels from top edge)

input color  BullColor = clrLime;
// Color for BUY signals and bullish elements

input color  BearColor = clrRed;
// Color for SELL signals and bearish elements

input color  NeutralColor = clrGray;
// Color for WAIT signals and neutral elements

input bool   ShowDashboard = true;
// ON: Show dashboard panel on chart
// OFF: Hide dashboard (EA still works, just no visual display)
```

### What the EA Calculates Automatically (NO User Input Needed)

The following parameters are **NOT exposed as inputs** because they are calculated dynamically:

| Parameter | How It's Calculated |
|-----------|---------------------|
| **All indicator parameters** | Based on symbol class + volatility regime (see Section 3.3) |
| ATR Period | Auto-adjusted for symbol + volatility |
| Kaufman ER Period | Auto-adjusted for symbol + volatility (replaces ADX) |
| KAMA Periods (Fast/Medium/Slow) | Auto-adjusted for symbol + volatility (replaces EMA) |
| Supertrend Multiplier Range | Auto-adjusted for symbol + volatility |
| K-Means Training Window | Auto-adjusted for symbol + volatility |
| SMC Lookback (OB, Swing) | Auto-adjusted for symbol + volatility |
| Volume Profile Bars | Auto-adjusted for symbol + volatility |
| VWAP Anchor Points | Auto-calculated per session (Asia/London/NY) |
| Confidence Thresholds | Auto-adjusted for market state (Trending/Ranging/Volatile) |
| SL Multiplier (ATR-based) | Auto-adjusted for market state + current volatility |
| TP Multiplier (ATR-based) | Auto-adjusted for market state + RR ratio target |
| Higher Timeframe for MTF | Auto-selected: M5→M15, M15→H1, M30→H4 |
| K-Means K (number of clusters) | Always 3 (Low/Normal/High volatility groups) |
| **Optimization Learning Rate** | Fixed at normal learning (0.1 internally) |

### Why So Few Inputs?

**Traditional EAs:** Require 30-50 input parameters that must be manually optimized for each symbol/timeframe. This leads to curve-fitting and poor performance when market conditions change.

**Gaeni EA:** Uses a dynamic parameter engine that automatically calculates everything based on real-time market analysis. The EA adapts continuously, so no manual optimization is needed. You attach it to any chart and it works.

**The only inputs you control:**
1. **Risk management** (how much to risk per trade)
2. **Trading mode** (auto-trade or observation only)
3. **Feature toggles** (enable/disable specific components)
4. **Display preferences** (panel position, colors)

This makes Gaeni truly plug-and-play across all symbols and timeframes.

---

## 11. EXPECTED PERFORMANCE

### Realistic Expectations (Not Promises)
- **Signal Quality:** High confidence signals should have 72-78% directional accuracy (improved from 65-75% with news/session filters)
- **TP Hit Rate:** With smart TP placement at liquidity/POC levels, estimated 65-75% TP reach rate (improved from 60-70% with partial TP and time-based exit)
- **Risk-Reward:** Minimum 1:1.5, typically 1:2 to 1:4. With partial TP + trailing stop, effective RR improves to 1:1.8-1:2.2 average
- **Win Rate After Improvements:** 
  - Without partial TP: 65-75% of trades profitable
  - With partial TP: 78-85% of trades profitable (partial closes lock in profit earlier)
- **Drawdown Reduction:** News filter + session filter + divergence detection reduces max drawdown by 30-40%
- **Profit Factor:** Expected 1.8-2.2 (improved from 1.3-1.5 with all advanced features)
- **Signals per day:** 
  - M5: 3-8 signals (many filtered by regime/confidence/session)
  - M15: 1-4 signals
  - M30: 0-2 signals
- **Average Trade Duration:**
  - M5: 15-45 minutes
  - M15: 2-6 hours
  - M30: 6-24 hours

### What Makes This Better Than Basic EAs
1. **Dynamic Parameter Engine** auto-adjusts all settings for symbol, volatility, and market state — no manual optimization needed
2. **Regime filter** eliminates signals in bad conditions
3. **ML-Adaptive Supertrend** adjusts to actual market behavior
4. **SMC levels** give institutional-quality entry/exit
5. **Volume + VWAP confirmation** validates with real money flow and institutional benchmarks
6. **Multi-TF agreement** prevents counter-trend traps
7. **Self-learning** improves over time
8. **Confidence scoring** only shows high-probability setups
9. **Partial TP + Breakeven + Trailing** locks in profit early and protects capital
10. **Tick-level CVD divergence** detects reversals 2-5 bars before indicators confirm
11. **Time-based exit** prevents trades sitting forever
12. **News filter** avoids high-impact event spikes
13. **Session filter** trades only during high-liquidity sessions
14. **Adaptive position sizing** maximizes profit on strong signals, reduces risk on weak ones
15. **Modern indicators** (Kaufman ER, KAMA, VWAP) replace outdated ones (ADX, EMA)

### Honest Limitations
- No EA can guarantee 100% win rate or 100% TP reach
- News filter reduces but doesn't eliminate news-related losses (some news events are unpredictable)
- Very low liquidity periods (holidays, rollover) reduce accuracy
- Self-learning needs 20-30 signals before it adds value
- Performance varies by instrument (works best on liquid pairs and gold)
- Tick-level divergence works best on instruments with reliable tick data (forex majors, gold; less reliable on crypto with sparse ticks)
