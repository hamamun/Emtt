# Emtt

## Hard Rules — Must Follow

1. Emtt will be built based on this (`Emtt.md`) file.
2. Only include what I explicitly ask for into `Emtt.md`.


---

## 1. Application
MT5 Trading Expert Adviser.

## 2. Author
Ham

## 3. Coder / Programmer
Arena

## 4. Where To Apply Emtt
At MT5 Chart.

- a) Files: `Emtt.mq5` under `Experts` folder
- b) Any `.mqh` file will be under `Include > Emtt` folder
- c) Any Indicators file under `Indicators > Emtt` folder
- d) Emtt allows chart timeframes **M5 / M15 / M30** only. On any other timeframe the
  STATUS line shows, in **red**: `Incompatible chart. Switch to M5/M15/M30.`
  See rule 19 for what the panel shows.

---

## 5. Phase 1 — Layout (APPROVED — IMPLEMENTED 2026-10-07)

### Panel A — order OPEN

```
╔═══════════════════════════════════════════════════════════╗
║  Emtt V1.0 | EURUSD | TF: M15 | Auto Trading: ON          ║  ← Header
║  Bid: 1.08538  |  ►Ask: 1.08540  |  Spread: 2 pts         ║  ← Price Row
║  ───────────────────────────────────────────────────────  ║
║  Regime: TRENDING (Bullish)                               ║  ← Row 1
║  ───────────────────────────────────────────────────────  ║
║  SIGNAL: ▲ BUY                                            ║  ← Row 2
║  Confidence: 85%                                          ║  ← Row 3
║  ───────────────────────────────────────────────────────  ║
║  Entry:        1.08450 / $142.50   (90 pts away)          ║  ← Row 4
║  Stop Loss:    1.08280 / $170.00   (170 pts)              ║  ← Row 5
║  Take Profit:  1.09120 / $670.00   (670 pts)              ║  ← Row 6
║  Risk:Reward:  1:3.9                                      ║  ← Row 7
║  Session: London | Expected Duration: ~2-4 hours          ║  ← Row 8
║  ───────────────────────────────────────────────────────  ║
║  WHY: Supertrend bullish + OB support at 1.0845 +         ║  ← Row 9
║       CVD rising (buyers dominant) + H1 agrees up         ║
║  ───────────────────────────────────────────────────────  ║
║  STATUS: Signal active — Price +$44.00 toward TP1         ║  ← Row 10
║  ───────────────────────────────────────────────────────  ║
║  ◆ LIVE TRADE — On M15                                    ║  ← Block header
║  Ticket: 48217291 | BUY 0.50 lots @ 1.08450               ║  ← Row 11
║  Floating P/L: +$44.00  (+88 pts)                         ║  ← Row 12
║  Live SL: 1.08455 (83 pts) | TP1: 1.09120 TP2: 1.09450    ║  ← Row 13
║  Protect: Breakeven | Age: 00:42 / ~2-4h                  ║  ← Row 14
╚═══════════════════════════════════════════════════════════╝
```

### Panel B — no order

```
╔═══════════════════════════════════════════════════════════╗
║  Emtt V1.0 | EURUSD | TF: M15 | Auto Trading: ON          ║
║  Bid: 1.08538  |  Ask: 1.08540  |  Spread: 2 pts          ║
║  ───────────────────────────────────────────────────────  ║
║  Regime: RANGING                                          ║
║  ───────────────────────────────────────────────────────  ║
║  SIGNAL: ⏸ WAIT                                           ║
║  Confidence: 48%                                          ║
║  ───────────────────────────────────────────────────────  ║
║  Entry:        --      / $0.00     (-- pts away)          ║
║  Stop Loss:    --      / $0.00     (-- pts)               ║
║  Take Profit:  --      / $0.00     (-- pts)               ║
║  Risk:Reward:  --                                         ║
║  Session: London | Expected Duration: --                  ║
║  ───────────────────────────────────────────────────────  ║
║  WHY: No agreement — Supertrend flat, price mid-range     ║
║  ───────────────────────────────────────────────────────  ║
║  STATUS: No trade — confidence 48%, below threshold       ║
╚═══════════════════════════════════════════════════════════╝
```

There are only these two panels. No other panel exists.

---

## 6. Panel Rules & Style

1. **Units:** all distances in **points (pts)**. Never pips. Money in the **real account currency**
   (examples here use `$` because the account is USD).
2. **Price Row:** Bid / Ask / Spread are **realtime and must match the MT5 terminal exactly**.
   `►` marks the dealing side: BUY → `►Ask`, SELL → `►Bid`, WAIT → no marker.
3. **Distances:** Row 4 is measured from the dealing price (Ask for BUY, Bid for SELL).
   Rows 5–6 are measured from Entry. Row 13 SL distance is measured from the current price.
4. **Take Profit:** Row 6 is the **real TP sent with the order** — the maximum achievable target
   Emtt commits to. In the live block it is shown as `TP1`. `TP2` is the extended target Emtt
   aims for if momentum continues after TP1; it exists only while a trade is open.
5. **Row 14 Protect:** one word for what is currently guarding the trade —
   `Original` / `Breakeven` / `Trailing` / `ATR` / `Chandelier` / `Fractal`.
   The state is shown **only here**, never on Row 13.
6. **Confidence (Row 3):** a single confirmed figure, never a range and never two numbers.
   It is the combined result of Emtt's own checks and updates live.
7. **One position at a time.** Emtt opens only one position per symbol and will not open
   another until that one is closed. Row 11 therefore always shows exactly one ticket.
8. **LIVE TRADE block** (header + Rows 11–14) appears **only when Emtt's own position is open**,
   identified by its **magic number** — manual trades are ignored. If the user removes Emtt
   while its trade is still live and re-attaches it later, Emtt finds that position by magic
   number and shows the block again. Otherwise the block is hidden, together with the separator
   above it, and the panel ends at Row 10.
9. **Auto Trading ON/OFF changes nothing in the panel** except the header word. OFF only means
   Emtt will not place new orders. If its position is already open, the LIVE TRADE block still shows.
10. **Market Closed** is shown on Row 1 as `Regime: MARKET CLOSED`. No separate panel.
11. **No extra rows are ever added.** Everything else goes to the **STATUS line (Row 10)** —
   reason no order was placed, divergence warning, news warning, final P/L after close.
12. **WHY and STATUS height:** WHY defaults to 2 lines, STATUS to 1. Either may use more lines
    when the text is long. Text wraps; **the panel width never changes**.
13. **Panel size:** width is fixed and sized to the longest row — all text must fit, no cut-off.
    Height grows and shrinks with the LIVE TRADE block and with WHY / STATUS wrapping.
14. **Position:** anchored top-left of the chart, and **draggable** by the user.
15. **Refresh:** 1-second timer for the whole panel. Price Row and Floating P/L also update on
    every tick so they always match the terminal.
16. **Font:** `Segoe UI` for the whole panel. Size `12` every row, except SIGNAL row BUY/SELL
    text at `14`.
17. **Colour:** only **Row 2 (SIGNAL)** and **Row 12 (Floating P/L)** are coloured.
    Every other row uses the one soft text colour. One exception: the STATUS line turns
    red for the incompatible-timeframe message (see 4d).
18. **Magic number:** an input parameter, default `20251007`. User-changeable in MT5.
19. **Incompatible timeframe:** the panel still draws in full — every row, header and
    separator in its normal place, normal size. Only the data is blank: the header shows
    the real symbol and timeframe (e.g. `TF: H1`), every data field shows `--`
    (`Regime: --`, `SIGNAL: --`, `Confidence: --`, Entry / SL / TP / Risk:Reward / Session /
    Expected Duration / WHY all `--`), and the STATUS line carries the red message from 4d.
    The Price Row keeps showing live Bid / Ask / Spread. Emtt gives no signal and places
    no **new** order on this timeframe.
20. **Block header records the trade's timeframe:** `◆ LIVE TRADE — On M15`, where M15 is
    the timeframe the order was opened on, not the chart's current timeframe.
21. **Changing the chart timeframe never affects a live trade.** The LIVE TRADE block stays
    fully populated and Emtt keeps managing the position — breakeven, trailing, closing —
    even on an incompatible timeframe. Only new signals and new orders stop.

| Use | Hex | MQL5 |
|---|---|---|
| Panel background (whole panel) | `#282828` | `C'40,40,40'` |
| Header strip background | `#333333` | `C'51,51,51'` |
| Border + separator lines | `#4A4A4A` | `C'74,74,74'` |
| All text (soft) | `#C8C8C8` | `C'200,200,200'` |
| BUY / Profit | `#6FCF97` | `C'111,207,151'` |
| SELL / Loss | `#EB6F6F` | `C'235,111,111'` |
| WAIT | `#C8C8C8` | `C'200,200,200'` |
| STATUS warning (incompatible timeframe) | `#EB6F6F` | `C'235,111,111'` |

---

## 7. STATUS Line — "no order placed" messages

- `No trade — confidence NN%, below threshold`
- `No trade — spread too wide (N pts)`
- `No trade — news blackout, <event> in N min`
- `No trade — <session> session blocked`
- `No trade — max open trades reached`
- `No trade — not enough margin`
- `No trade — Auto Trading OFF`
- `Order rejected — broker error <code>`
- `Incompatible chart. Switch to M5/M15/M30.`  *(red)*

---

## 8. Phase 1 — Done When

**Status: IMPLEMENTED (2026-10-07)** — `Experts/Emtt.mq5` + `Include/Emtt/Emtt_Dashboard.mqh`.
Per author instruction the panel shows **labels only, no dummy values**; the fixed width is
measured from the section 5 row formats so the panel keeps its final size. Live data kept:
header, Bid/Ask/Spread Price Row, red incompatible-timeframe STATUS.

- Panel draws on a live MT5 chart with labels only (no dummy values, per author), exactly as Panel A and Panel B above.
- Price Row matches the terminal's Bid / Ask / Spread in realtime.
- Panel switches between A and B correctly, and is draggable.
- All objects are removed cleanly when the EA is removed from the chart.

---

## 9. Phase 2 — Foundation + Dynamic Parameter Engine + Market Regime Detection

**Status: IMPLEMENTED (2026-10-07).**

The foundation every later phase consumes: Emtt first works out **what it is trading** and
**what kind of market it is in**, and derives every internal indicator setting from that.
No signals, no orders, no new rows, no new inputs.

### 9.1 Files

- `Include/Emtt/Emtt_DynamicParams.mqh` — symbol classification, volatility regime, parameter
  matrix, market-state adaptation.
- `Include/Emtt/Emtt_Regime.mqh` — regime classification, session clock, market-open check.
- `Experts/Emtt.mq5` — both wired into the existing `FillPanel()`. The renderer
  (`Emtt_Dashboard.mqh`) is not touched.

### 9.2 What gets built

**1. Symbol auto-detection** — on init, re-validated every 100 bars. Read `ChartSymbol()`,
strip broker suffixes (`.pro`, `.ecn`, `m`, `.i`, `.r`, `.raw`, `+`, `#`), classify into
**Forex Major / Forex Cross / Metals / Crypto / Indices / Generic**.

**2. Volatility regime** — every closed bar. Measure **ATR(14)** — a fixed measuring stick, never
the matrix period — on each of the last 200 closed bars and rank the newest value against the
other 199 → percentile → **LOW (0–30) / NORMAL (30–70) / HIGH (70–100)**. Period and window are
both fixed, so the bucket can never change the measurement that produced it. ATR(50) is the longer
baseline for comparison. The bucket has margins of its own, so a value resting on a line cannot
make it flicker: percentile must exceed **70** to enter HIGH and fall below **67** to leave it;
below **30** to enter LOW and above **33** to leave it. The bucket is its own axis: it is measured
and journaled even when the regime is a trend.

**3. Parameter engine — how every internal number is decided.** Emtt sets its own parameters
from standard values, then adjusts them for timeframe and live market context. Four layers, read
in order — each layer **adjusts** the layer above it, never replaces it, and Layer 1 is always the
base:

| Layer | Reads | Does | Example |
|---|---|---|---|
| **1. Standard** | symbol class | the base values of the matrix below, matched to the asset class. No market input | EURUSD → ATR 10, KAMA 9 / 21 / 50 |
| **2. Timeframe** | chart timeframe | scales only the parameters marked as **lookbacks**, by bar count for the timeframe: M5 = **1.0×**, M15 = **1.25×**, M30 = **1.5×** (rounded to a whole bar). Indicator periods are **not** scaled — the timeframe is already inside the candles: ATR(10) on M5 is 10 five-minute candles, on M30 it is 10 thirty-minute candles. **This phase has no lookback parameter yet**, so the layer is defined now and takes effect in the phase that adds the first one | SMC lookback 10 → 15 on M30 (a later phase's row) |
| **3. Volatility** | Low / Normal / High bucket | reads the column for the current bucket: the Low column on a LOW bucket, Normal on NORMAL, High on HIGH — always inside the range written for that class | ATR 10 → 14 |
| **4. Context** | regime, session, spread | picks the **profile for the current timeframe**: the confidence threshold (item 4) and, in later phases, the management parameters (SL / TP multiples, breakeven, trailing, duration, exits). Context may never adjust a parameter that was used to calculate the context itself | Ranging → threshold 70%, tighter management |

Layer 1 base matrix (Low / Normal / High volatility):

| Parameter | Forex Major | Forex Cross | Metals | Crypto | Indices | Generic |
|---|---|---|---|---|---|---|
| ATR period | 10 / 10 / 14 | 10 / 14 / 14 | 10 / 14 / 21 | 14 / 21 / 28 | 10 / 14 / 14 | 10 / 14 / 14 |
| Kaufman ER period | 10 / 10 / 14 | 10 / 14 / 14 | 14 / 14 / 21 | 21 / 21 / 28 | 14 / 14 / 21 | 14 / 14 / 21 |
| KAMA periods (fast, med, slow) | 9,21,50 / 9,21,50 / 13,26,50 | 9,21,50 / 13,21,50 / 13,26,50 | 9,21,50 / 13,21,50 / 13,26,50 | 13,26,50 / 13,26,50 / 21,34,50 | 9,21,50 / 13,21,50 / 13,26,50 | 9,21,50 / 13,21,50 / 13,26,50 |

Fixed, not adjusted by any layer: Bollinger Band Width (20, 2.0) and the 200-bar volatility window.

**Three classes of parameter — the layers apply differently to each:**

| Class | Examples | Adjusted by |
|---|---|---|
| **Measurement** — produces the context | ATR period, ER period, KAMA periods, Bollinger, the 200-bar volatility window | class + timeframe + volatility. **Never by the regime** — context must not change what measured it |
| **Management** — acts on a signal or a trade | SL / TP ATR multiples, breakeven trigger, trailing distance, expected duration, time-exit behaviour | class + timeframe + volatility + **regime** — these feed nothing back, so the context profile is free to set them. Their rows are added to this table by the phases that build them |
| **Strictness** — gates whether Emtt acts | confidence threshold, spread filter | regime now; session and news in later phases |

**The set is the combination, not any single axis.** Example: EURUSD on **M30** with a bearish
regime and normal volatility resolves to one set. The same symbol switched to **M5**, where the
same bearish backdrop is choppy rather than directional, resolves to a **different** set — shorter
lookbacks, a higher bar to trade, tighter management, shorter expected duration. Same tables, same
code path: the timeframe and the context profile are both inputs to one resolution, and nothing is
hardcoded per timeframe.

Guard rails:

- **Frozen while a trade is open.** While Emtt holds a position, the numbers that manage it —
  SL / TP multiples, breakeven, trailing, duration — and the confidence threshold stay exactly as
  they were at entry, until it closes. This cannot be exercised until the phase that opens trades;
  it is defined now so no later phase has to retrofit it. **The panel is not frozen:** Row 1,
  Row 9 and Row 10 always show the live market, so you can always see what is really happening.
- **One change, then a pause.** A parameter follows its bucket (which is already damped by its own
  margins) and, after any change, the same parameter stays put for the next **2 closed bars** —
  long enough to stop flicker, short enough to keep up with a real volatility shift.
- **Clamped.** Every value stays inside the range written for its class — never above or below.
- **Journal.** Every change is logged on the closed bar with its reason, e.g.
  `ATR period 10 -> 14 | volatility LOW -> HIGH | bar 2026.10.07 14:30`. The journal is the only
  place changes are recorded: the panel shows no parameter row (rule 11), and the log must let
  you reconstruct exactly what Emtt was using at any moment.

**Each later phase adds its own rows to this one table when that phase is written** — nothing is
defined in advance for a component Emtt has not been asked to build.

**4. Market-state adaptation** — the regime sets the **confidence threshold**:
**Trending** 60%, **Ranging** 70%, **Volatile** 70%, **Transition** 75%. It is derived now and
consumed by the later signal phase (Layer 4 of item 3). Context adjusts strictness only: it must
never change the ER / KAMA periods or the volatility window that produced the regime in the first
place.

**5. Indicators** — all on closed bars only, never index 0:
Kaufman Efficiency Ratio (period from matrix, 0–100), KAMA fast / medium / slow (periods from
matrix), Bollinger Band Width (squeeze / expansion), and the ATR ratio that feeds item 6 —
**ATR at the matrix period** against ATR(50). (The volatility bucket in item 2 keeps its own fixed
ATR(14) stick; this is the separate, class-aware pair.)
Every indicator here is used by the regime decision in item 6 — nothing is calculated that this
phase does not use.

**6. Market regime detection — five states.** Each state is decided by its **own measurements**,
never by "what the label was a moment ago", so the same closed bars always produce the same
label — on any machine, at any time, when replayed. Two rules keep it steady:

- **Confirmation:** between the four open-market states the label switches only when the new
  state has held for **2 consecutive closed bars** — one candle can never change it.
  MARKET CLOSED applies at once, and the first state after reopening shows at once.
- **Margins (no boundary flicker):** each threshold has an entry and an exit level, so a value
  sitting exactly on the line cannot flip the label: ER enters TRENDING above **62** / leaves
  below **58**; enters RANGING below **28** / leaves above **32**; VOLATILE enters at
  ATR ratio above **1.5** / leaves below **1.3**.

On the **first evaluation** — right after attaching to a chart, or as soon as enough history is
available — the state is read straight from the entry levels; the margins apply from the second
evaluation onwards, so a label is never withheld because of them.

Precedence, top to bottom:

- **MARKET CLOSED** — Emtt first asks MT5 for the symbol's own trading hours (the broker's exact
  schedule, holidays included) and falls back to the candle check — no new candle for more than
  2× the chart period — when the broker reports no schedule → EA paused.
- **TRENDING (Bullish / Bearish)** — ER above its threshold **and** the three KAMAs aligned
  (fast > medium > slow = Bullish; the reverse = Bearish). Direction is clear, so the market
  counts as trending even when volatility is high — the HIGH bucket is still reported separately.
- **VOLATILE** — volatility clearly elevated (ATR ratio above its threshold, Bollinger
  expanding) **and** direction unclear (the three KAMAs are not aligned).
- **RANGING** — ER below its threshold.
- **TRANSITION** — everything else: ER in the middle band, or KAMAs not aligned.

**7. Session clock (Row 8)** — each session follows **its own market's clock**, so the label is
true in summer and winter: **Asia** = Sydney 07:00 local → Tokyo 18:00 local;
**London** = 07:00–16:00 London local; **New York** = 07:00–16:00 New York local. Daylight saving
is each market's own (Europe: last Sunday in March → last Sunday in October; US: second Sunday in
March → first Sunday in November; Sydney: first Sunday in October → first Sunday in April), so the
windows move with the markets instead of with the calendar. The three windows cover the whole
trading week back to back — there is never a moment with no name; where they meet, both names are
shown (`Asia/London`, `London/NY`). Emtt reads GMT from the terminal and re-checks its offset
against the broker's server time once a day; if the two disagree it keeps the last valid offset and
notes it in the journal. Display only — this phase blocks nothing.

**8. Panel wiring** — no layout, palette or width change (rules 11, 13–17):

**Nothing on this panel is invented.** A field shows a value only when Emtt has measured it;
otherwise it shows `--` — the same `--` rule 19 already uses. While the chart is still loading
history (fewer than the closed candles the measurement set needs, about 200) Row 1 and Row 9 show
`--`, Row 8 shows the session (a clock needs no history) and Row 10 shows
`Waiting — Loading chart history (137/200 candles)`. MARKET CLOSED needs no history either: if the
market is closed, that is what Row 1 says, whatever the history.

- **Row 1:** `Regime: TRENDING (Bullish)` / `RANGING` / `VOLATILE` / `TRANSITION` /
  `MARKET CLOSED` (rule 10) / `--` while loading.
- **Row 8:** the session name in the `Session:` half; `Expected Duration:` stays empty until
  the signal phase. `--` when the market is closed.
- **Row 9:** one plain-language WHY sentence naming the factors that decided the regime —
  e.g. `Efficiency 71/100 and KAMAs aligned up; volatility normal`; `--` while loading.
- **Row 10:** the honest status for the state, e.g. `Waiting — Market ranging, no high-quality
  setup`, `Watching — Market transitioning, monitoring for new direction`,
  `Protecting — High volatility, signals need higher confidence`,
  `Paused — Waiting for market to open`. These are Emtt's **pre-signal states**; section 7's
  `No trade — …` messages belong to the phase that can actually place orders.
- Rows 2–7 stay label-only until the phase that produces their values.
- **Incompatible timeframe** (rule 19): Regime / Session / WHY show `--`, STATUS keeps the red
  message from 4d, Price Row stays live. Rule 19 wins over any state message — on a chart Emtt
  cannot analyse, the red message is the only thing it says.

**9. Refresh & no-repaint rules** — volatility, indicators and regime are recomputed on each new
closed bar; symbol re-validation every 100 bars; the panel keeps its 1-second timer and per-tick
price updates. Nothing heavy runs per tick.

**10. Tests** — unit tests for the pure logic (percentile, session windows, regime precedence)
that run without MT5, plus an include-layout / compile smoke check in CI.

**11. Not in this phase** — ML Supertrend + K-Means, SMC structure, Volume Profile / CVD / VWAP,
multi-timeframe agreement, confidence engine, Entry / SL / TP, order placement, news filter,
session trading block, trade management, self-learning and parameter-optimization persistence.
**No new inputs**: user settings stay Magic number + Auto Trading.

---

## 10. Phase 2 — Done When

**Status: IMPLEMENTED (2026-10-07).**

- Panel shows live Regime (Row 1), session (Row 8), WHY (Row 9) and STATUS (Row 10) on M5 / M15 / M30.
- Regime labels flip at the right times and are stable: the same closed bar always reads the same.
- No one-candle flicker: no regime appears for fewer than 2 closed bars, and a value sitting on a line never flips anything.
- M5 / M15 / M30 behave differently through one code path — nothing is hardcoded per timeframe: the timeframe lives in the candles, so each chart produces its own volatility bucket, its own regime and its own threshold.
- Volatility bucket and parameter set change automatically within 1–2 bars of a real volatility shift.
- Switching M30 → M5 on the same symbol re-reads the market for the new timeframe: its own bucket and regime appear within 2 closed bars of the switch, and the journal shows the change and the reason. (The ×1.0 / ×1.25 / ×1.5 lookback scale starts working in the phase that adds the first lookback parameter.)
- Parameters move one column at a time, never twice within 2 closed bars, and every change appears in the journal with its reason.
- The volatility bucket behaves: it does not flicker around its lines, and the parameters always match the bucket that is showing.
- A freshly attached chart shows no guesswork: Regime and WHY read `--` with `Waiting — Loading chart history` until the measurements exist, then fill in by themselves.
- Every field is either measured live or `--` — nothing is invented, estimated, or carried over from an earlier state.
- Session labels follow each market's own clock: London reports London's hours in both winter and summer, and no moment of the trading week is left unnamed.
- Weekend / closed market → `Regime: MARKET CLOSED`, EA paused; resumes on the next new candle.
- On H1 and other timeframes the Regime / Session / WHY fields show `--` with the red message; Price Row still live.
- No repainting: restarting the EA or replaying the chart shows the same readings.
- All objects are still removed cleanly when the EA is removed from the chart.
