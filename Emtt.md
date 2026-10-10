# Emtt

## Hard Rules — Must Follow

1. Emtt will be built based on this (`Emtt.md`) file.
2. Only include what I explicitly ask for into `Emtt.md`.
3. After each phase, every MQL5 source is tested with the MQL5 parser:
   `python tools/mql5_parser_check.py` must exit `0` before the phase is called done.
   The gate rejects broken MQL5 first (a built-in negative control must fail) and only
   then reports the sources clean. It checks **syntax only** — types, MQL5 built-in
   signatures and `PrintFormat` specifiers are MetaEditor's job, not this tool's.


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

**Parser check: TESTED AT PARSER AND PASSED (2026-10-08, retroactive).** Rule 3,
`python tools/mql5_parser_check.py` → exit `0`, `0 syntax errors` on the Phase 1 sources
`Include/Emtt/Emtt_Dashboard.mqh` (sha256 `cc4169b5bd8e`, 3943 nodes) and `Experts/Emtt.mq5`
(sha256 `6bff05191904`, 8193 nodes — cumulative, shared with Phases 2 and 3). Run after the
fact when rule 3 was added, not at Phase 1 delivery.

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

**Status: IMPLEMENTED (2026-10-07) — VERIFIED BY THE AUTHOR ON A LIVE MT5 CHART (2026-10-08).** Working as specified,
confirmed by Ham. Phase 2 is closed; no later phase reopens it.

**Parser check: TESTED AT PARSER AND PASSED (2026-10-08, retroactive).** Rule 3,
`python tools/mql5_parser_check.py` → exit `0`, `0 syntax errors` on the Phase 2 sources
`Include/Emtt/Emtt_DynamicParams.mqh` (sha256 `24bd3519a4dc`, 5155 nodes) and
`Include/Emtt/Emtt_Regime.mqh` (sha256 `d62dcf089a7b`, 4021 nodes). Syntax only; the live-chart
verification above is the stronger evidence and stands on its own.

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

---

## 11. Phase 3 — ML-Adaptive Supertrend (K-Means)

**Status: SPEC APPROVED (2026-10-08) — BUILD AUTHORISED.** The section 10 gate is cleared: the author verified
Phase 2 on a live MT5 chart on 2026-10-08. Nothing here waits on a further approval.

**Status: IMPLEMENTED (2026-10-08)** — `Include/Emtt/Emtt_Supertrend.mqh` (new: 11.3 bands, 11.4 K-Means,
11.5 per-cluster multiplier, 11.6 contract), wired into `Experts/Emtt.mq5` (`#property version` 1.20) at exactly
the 11.1 wiring points, `tests/phase3_reference.py` + `tests/test_phase3_reference.py`, the CI contract in
`tools/mql5_compile_smoke.py`, and one `README.md` paragraph. `Emtt_Dashboard.mqh` and both Phase 2 headers are
byte-identical; inputs are still Magic number + Auto Trading; no new handle, chart object, file or GlobalVariable.
Portable suite 56/56 passing and `tools/mql5_compile_smoke.py` passing, CI green on the branch.

**Status: VERIFIED BY THE AUTHOR ON A LIVE MT5 CHART (2026-10-08).** Working as specified, confirmed by Ham.
The MetaEditor compile and the on-chart checks of section 12 are settled by that live run. Phase 3 is closed;
no later phase reopens it.

Emtt works out **how** it should read direction: it clusters the symbol's recent volatility, keeps one Supertrend
setting per cluster, and reports the resulting direction as context. Direction is context, not a signal — no BUY/SELL,
no levels, no orders.

### 11.1 Files

| File | Change |
|---|---|
| `Include/Emtt/Emtt_Supertrend.mqh` | new — Supertrend bands, K-Means clusters, per-cluster multiplier |
| `Experts/Emtt.mq5` | wired into the existing closed-bar path and `FillPanel()`; `#property version` → `1.20`, one `#property description` line updated |
| `tests/phase3_reference.py` + `tests/test_phase3_reference.py` | new — MT5-free mirror of 11.3–11.6, same pattern as Phase 2; scope in 11.12 |
| `tools/mql5_compile_smoke.py` | contract list gains the new header; the "dashboard unchanged" guard stays |
| `README.md` | one Phase 3 paragraph |

`Include/Emtt/Emtt_Dashboard.mqh` is **not touched**. Sections 1–10 are **not rewritten** — only status stamps are
appended there as phases are implemented and verified.
Inputs stay **Magic number + Auto Trading** — Phase 3 adds none. No new indicator handle: Supertrend is computed from
the ATR buffers the EA already copies. The panel header string stays `Emtt V1.0` — only the `#property` lines change.

Exact wiring points in `Experts/Emtt.mq5` — Phase 3 adds no others:

- one `SEmttSupertrendState` global, reset in `EmttResetMarketState()` alongside `EmttDynamicReset()` /
  `EmttRegimeReset()`;
- trained + advanced for each bar **inside** the existing `EmttReplayClosedHistory()` loop and again in
  `EmttProcessLatestClosedBar()`, after `EmttBuildMeasurements` / `EmttReadCurrentMeasurements` and after
  `EmttDynamicUpdateVolatility` (so it sees the bucket and `atrPeriod` of that bar), before `EmttSetSnapshot`;
- read only in `FillPanel()` for the Row 9 clause and the Row 10 status choice;
- `OnTick()` gains nothing; `EmttReleaseIndicators()` / `OnDeinit()` gain nothing (no handles, no files to release).
- The header is included as `#include "../Include/Emtt/Emtt_Supertrend.mqh"` — the same quoted, repo-relative form as
  the three existing includes, never an angle-bracket `<…>` path (4b).

**Read in this order before coding:** 4 (where files live, timeframe limit), 5 (the panel contract), 6 (rules 1–21 —
units, points, distances, refresh, palette), 9.2.3 (the four layers and the guard rails Phase 3 must obey), 9.2.8 (the
`--` honesty rule and the loading gate), then 11 in full. **Section 12 is the definition of done** — every bullet in it
must hold before the phase is called implemented.

**Delivery:** one change set containing exactly the rows of the table above — the new header, the EA wiring, the two
test files, the CI contract, `README.md`. No other file, no refactor of Phase 1 or Phase 2 beyond the wiring points
listed. `.github/workflows/phase2.yml` needs no edit and no `phase3.yml` is created: it discovers `tests/` and runs the
smoke check, so the new tests are picked up on their own.

### 11.2 Rules for this phase

1. **Panel only.** Emtt draws no other chart object in this phase — no line, rectangle, arrow or chart label. Its only
   chart objects are the panel objects. This holds for later phases unless the author writes such a rule.
2. **No layout change** — rules 11–17 stand: no new rows, fixed width, `Segoe UI`, sizes, palette, colours all as is.
   WHY keeps its default 2 lines and may wrap.
3. **Rows 2–7 stay label-only.** The LIVE TRADE block keeps its Phase 2 behaviour (detected by magic number, rows 11–14
   label-only). Nothing about orders changes.
4. **Closed bars only**, index 0 never read; the per-tick path stays `UpdatePanel()` only — no measurement on ticks.
5. **Nothing invented** — a field carries a measured value or `--`, as rule 19 and 9.2.8 already require.
6. Supertrend belongs to the **Measurement** class of 9.2.3: adjusted by class + timeframe + volatility, **never by the
   regime**, and it feeds nothing back into the bucket or the regime.

### 11.3 Supertrend — exact definition

ATR used: the matrix `atrPeriod` currently resolved (class + bucket). The fixed ATR(14) measuring stick of 9.2.2 is
**not** used here. Computed in-house from `MqlRates` + ATR — no custom indicator, no `.ex5`, no DLL, no Market download.

Per closed bar `i` (series indexing, `i+1` = the older bar), for multiplier `m`:

- `mid = (high[i] + low[i]) / 2`
- `upRaw = mid + m × ATR[i]`, `dnRaw = mid − m × ATR[i]`
- `up[i] = (upRaw < up[i+1] || close[i+1] > up[i+1]) ? upRaw : up[i+1]`
- `dn[i] = (dnRaw > dn[i+1] || close[i+1] < dn[i+1]) ? dnRaw : dn[i+1]`
- direction: `+1` when `close[i] > up[i+1]`; `−1` when `close[i] < dn[i+1]`; otherwise carry `direction[i+1]`
- line: `dn[i]` when direction is `+1`, `up[i]` when `−1` — published as the trailing reference for the later
  management phase, **displayed nowhere** in this phase (rule 11)
- the oldest bar of the window seeds direction `+1`; `flat` is reported only if no band has been evaluated yet

### 11.4 K-Means — exact definition

- **Input:** the raw ATR values (`atrPeriod`) of the training window's closed bars. No normalisation, no smoothing.
- **K = 3.** Seeds = the 10th / 50th / 90th percentile of that window, taken by **nearest-rank on the window sorted
  ascending**: `seed(q) = sorted[ceil(q / 100 × N) − 1]`, 0-based, `N` = window length. This is a quantile **of the
  set**, not the rank percentile of 9.2.2 — `EmttPercentileRank` must not be reused for it. Standard Lloyd iterations,
  **max 20**, stop when no centre moves more than `1e-9 × window mean`. Centres sorted ascending → **Calm / Normal /
  Wild**; a retrain always restarts from these three seeds, never from the previous centres.
- **Current cluster** = the centre nearest the newest closed bar's ATR; an exact tie resolves to the **calmer** centre.
- **Sparse guard:** a cluster holding fewer than 5 members never owns a learned multiplier — the nearest populated
  cluster's multiplier is used instead and the reason is journaled.
- **Retrain cadence:** every `max(1, window / 20)` closed bars (≈ 10 on M5, 12 on M15, 15 on M30), and immediately when
  the asset class, the resolved `atrPeriod`, the window length, or the volatility bucket changes; also on the first
  evaluation after init, a timeframe switch, market reopen, or a history shortfall reset.

### 11.5 Multiplier selection — exact definition

- **Candidates:** `2.0 / 2.5 / 3.0 / 3.5 / 4.0` ATR multiples. The candidate set **is** the range — identical for every
  asset class, and no value outside it can ever be selected.
- For each candidate, replay 11.3 across the training window and take the maximal runs of equal direction as segments.
  A segment **starts** at the close of the bar whose direction differs from the bar before it and **ends** at the close
  of the last bar still carrying that direction — the bar that flips it away belongs to the next segment, never this one.
  Within a segment:
  - `segReturn = direction × (closeEnd − closeStart) / ATR at segment start`
  - `meanReturn` = mean over segments at least 1 closed bar long
  - `noise = segmentCount / (windowBars / 10)`
  - `score = meanReturn − 0.10 × noise` (a small, fixed whipsaw penalty)
- Winner = highest `score`; a tie goes to the **larger** (smoother) multiplier. One winner is stored per cluster; the
  live value is the winner belonging to the current cluster. `meanReturn` of a window with no completed segment keeps
  the cluster's previous value rather than inventing one; on the very first evaluation an unlearned cluster starts at
  **3.0**, the middle of the candidate set.
- Selection reads closed bars inside the window only — never the bar after the window, never index 0.
- **Guard rails of 9.2.3 apply to this value:** one change, then the same parameter stays put for 2 closed bars, every
  change journaled, never outside the candidate set. The pause governs the **multiplier only** — direction and current
  cluster are readings and are never delayed or damped by it.

### 11.6 What Phase 3 publishes — the component contract

This is the shape every later component phase copies. `Emtt_Supertrend.mqh` owns one `SEmttSupertrendState`, the EA
keeps a single instance of it; nothing in it is displayed beyond what 11.8 allows.

- `direction` (+1 / −1 / 0), `line` (the trailing reference, in price), `cluster` (Calm / Normal / Wild), `multiplier`.
- **Facts, not only a label:** `barsSinceFlip`, `flipCount` in the window, `distanceATRs`
  (`(close − line) / ATR × direction`, so it is positive while price sits on the trade side of the line and clamps to 0
  when it has fallen back through it), and the `atrPeriod` / `atrValue` the reading was made on.
- **`supertrendScore`, a single 0.0–1.0 number**, computed from those closed-bar facts only:

  `score = 0.45 × clamp01(distanceATRs) + 0.35 × clamp01(barsSinceFlip / 20) + 0.20 × clamp01(1 − flipCount / 20)`

  with `clamp01(x) = max(0, min(1, x))`, and `score = 0` when `direction` is 0 (`flat`).
- **Why the score exists now:** Row 3 (rule 6) is one combined figure, and the phase that fills it sums one such score
  per component. Deriving it later inside a finished module means rewriting and re-verifying this one; deriving it here
  costs nothing and changes nothing the user sees.
- **What the score is not:** it gates nothing in this phase, places nothing, and is never shown. It may never adjust a
  parameter, a bucket or a regime — readings are outputs, not inputs, to the engine of 9.2.3. `distanceATRs` and
  `barsSinceFlip` are additionally the momentum inputs the Expected Duration row will read in its own phase.
- Later phases publish the same contract — score + facts + the levels they find — so the confidence phase only ever
  sums weights. It defines no weights and no combining rule here.

### 11.7 Rows Phase 3 adds to the parameter table of 9.2.3

| Parameter | Base | Class | Layer 2 (timeframe) | Layer 3 (bucket) | Layer 4 (regime) |
|---|---|---|---|---|---|
| K-Means training window (lookback, closed bars) | 200 | **lookback** | ×1.0 / ×1.25 / ×1.5 → 200 / 250 / 300, rounded to whole bars | not adjusted | not adjusted |
| Supertrend ATR multiple | learned | measurement | not scaled (not a bar count) | through the `atrPeriod` it is measured on | never |

This is the first **lookback** parameter, so the Layer 2 scaling written in 9.2.3 and deferred by section 10 starts
working here. The **200-bar volatility window stays fixed and unscaled** (9.2.3): on M30 the percentile ranking still
uses 200 bars while K-Means uses 300. Management rows still arrive with their own phases.

### 11.8 Panel wiring

- **Row 9 (WHY):** the Phase 2 regime sentence first, then ` | `, then `<Cluster> (Supertrend <direction>)` — cluster is
  `Calm` / `Normal` / `Wild`, direction is `bullish` / `bearish` / `flat`.
  e.g. `Efficiency 71/100 and KAMAs aligned up; volatility normal | Wild (Supertrend bullish)`.
  The clause is appended whenever the Supertrend measurement is ready, including while a regime label is still in its
  confirmation bars. Not ready, market closed, or incompatible chart → no clause, `--` as today.
- **Regime and Supertrend are never reconciled.** If they disagree, both read as measured; no wording, colour or
  suppression may be used to make them look consistent.
- **Row 10 (STATUS):** precedence stays rule 19 > loading history > `MARKET CLOSED`, then: with a Supertrend direction
  available → `Watching — Supertrend context only, no signal yet`; otherwise the Phase 2 regime/pending lines stay
  exactly as they are. Section 7's `No trade — …` messages still belong to the phase that can place orders.
- **Rows 1–8 and 11–14 unchanged.** `Expected Duration:` still empty. The score, the line and the facts are never
  displayed: rule 11 gives them no row.
- **Required history — one gate for all measurements.** The figure becomes timeframe-derived: training window + the
  50-bar ATR baseline → **250 / 300 / 350** closed bars for M5 / M15 / M30, resolved by the same code path (never
  hardcoded per timeframe). `EMTT_HISTORY_REQUIRED` no longer drives the gate; `g_historyRequired` carries the resolved
  value, and the loading line shows `Waiting — Loading chart history (N/M candles)` with that M. This supersedes
  "about 200" in 9.2.8. While the gate is open, Row 1, Row 9 and Row 10 behave exactly as in Phase 2 — no partial,
  half-measured display.

### 11.9 Determinism, replay, state

- No RNG, no clock, no tick data, no file access in any Phase 3 calculation. Same closed bars in → same clusters, same
  multiplier, same direction, same line, same score, on any machine and at any time.
- All Phase 3 state is **reconstructed by replaying closed bars** on init, on a timeframe or symbol change, on market
  reopen and after any history shortfall reset — using the same replay path Phase 2 already uses. State never carries
  over from a previous session: no new file, no new GlobalVariable (the Phase 2 threshold-freeze key stays as it is).
- The replay **must** retrain on the 11.4 cadence as it walks the bars; that is what makes a restart reproduce the same
  multiplier through the 2-bar pause. Skipping the replay to save time is not allowed. The cost is bounded and small:
  at most `350 × 35 retrains × 5 candidates` band evaluations once, on the timer — nothing may run per tick, where only
  `UpdatePanel()` belongs.
- Journal through the existing `PrintFormat` channel, on the closed bar, with its reason, same shape as Phase 2:
  `Supertrend multiplier 3.0 -> 2.5 | cluster Normal -> Wild | bar 2026.10.08 14:30`. Logged on a multiplier change, a
  current-cluster change or a direction flip, and on the sparse-cluster fallback — never when nothing changed. The panel
  gets no parameter row (rule 11); the journal is the only record. Readings (direction, cluster, score) are never
  journaled as changes — they are re-readable from the chart.

### 11.10 Freeze semantics — unchanged

The frozen set stays exactly as 9.2.3 wrote it (SL / TP multiples, breakeven, trailing, duration, confidence threshold).
Phase 3 adds **nothing** to it and freezes **nothing** new: while an Emtt position is open, the clusters, the multiplier,
the direction and the score keep measuring and keep journaling live, and the panel never freezes.

### 11.11 Design seam for the later Multi-Timeframe phase

`Emtt_Supertrend.mqh` exposes a state struct plus functions that take the symbol, timeframe and closed-bar data as
arguments; the header reads no chart, no panel and no EA global. The EA owns one instance for the chart timeframe.
- The MTF phase must be able to instantiate a second instance for the higher timeframe with **no change to this header**.
- **Phase 3 introduces no new single-timeframe global in `Experts/Emtt.mq5`.** The higher-timeframe check needs the
  regime and the parameter resolution as well as Supertrend, so the two Phase 2 headers keep taking their state as
  arguments and are never given their own globals here.
- Carried forward, **not built now:** the MTF phase owns the change that wraps the Phase 2 and Phase 3 state into one
  context per symbol + timeframe. Writing that constraint now stops it from arriving as a rewrite of an approved phase.

### 11.12 Tests

`tests/phase3_reference.py` mirrors 11.3–11.6 in the same style as Phase 2, with `tests/test_phase3_reference.py`
asserting, without MT5: band and direction rules on a fixed series; seed quantiles, ascending clusters, tie → calmer,
sparse fallback; scoring, tie → larger multiplier, never outside the candidate set; the 2-closed-bar pause on the
multiplier and its absence on readings; the TF-scaled windows 200 / 250 / 300 and the history gate 250 / 300 / 350;
score formula bounds and the `flat → 0` rule; the nearest-rank seed rule; segment boundaries (the flipping bar belongs
to the next segment); the `3.0` default for an unlearned cluster; the Row 9 and Row 10 strings.
Same file also models the 9.2.3 matrix resolution, its clamping and the pause rule — implemented in Phase 2 but never
covered by the portable suite.

### 11.13 Not in this phase

No confidence engine, no weights, no Row 2 / Row 3 values, no Entry / SL / TP, no Risk:Reward, no Expected Duration, no
order placement or management, no SMC, no Volume Profile / CVD / VWAP, no multi-timeframe agreement, no news or session
blocking, no chart overlays, no self-learning or parameter-optimization persistence, no new inputs, no new panel row.

---

## 12. Phase 3 — Done When

**Status: IMPLEMENTED (2026-10-08) — VERIFIED BY THE AUTHOR ON A LIVE MT5 CHART (2026-10-08).** Every bullet below is
built and covered by the portable suite (`python -m unittest discover -s tests -v`, 56 tests) and by
`python tools/mql5_compile_smoke.py`, both green in CI on branch `arena/6a5d60aa-emtt`. The bullets that can only be
judged on a live terminal — panel wrap and colours, `Waiting — Loading chart history (N/M candles)` against the real M,
H1 behaviour, clean object removal, visibly instant initialisation — are confirmed by the author on a live MT5 chart,
together with the MetaEditor compile that live run requires, exactly as section 10 was.

**Parser check: TESTED AT PARSER AND PASSED (2026-10-08).** Rule 3, `python tools/mql5_parser_check.py`
→ exit `0`, `0 syntax errors`, with the negative control rejected before the sources were accepted;
`Include/Emtt/Emtt_Supertrend.mqh` (sha256 `6b2d6a97abb7`, 6654 nodes) and the Phase 3 wiring in
`Experts/Emtt.mq5` (sha256 `6bff05191904`, 8193 nodes).

**PHASE 3 IMPLEMENTATION DONE AND VERIFIED (2026-10-08).** The build is complete and the author has confirmed it
working on a live MT5 chart. Nothing in Phase 3 is outstanding; section 12's gate is cleared, so the next phase may
begin without a further approval.

- Supertrend, clusters, multiplier, direction and score are computed from closed bars only; index 0 is never read, and
  nothing runs on ticks.
- The same closed bars always give the same answer: restart, timeframe round-trip and chart replay reproduce identical
  clusters, multiplier, direction, line and score.
- The winner changes only inside `2.0 … 4.0`, at most once and then not again for 2 closed bars, and every change is in
  the journal with its reason.
- A value resting on a cluster boundary cannot make the multiplier or the panel clause flicker; direction, cluster word
  and score still update live while a trade is open.
- Layer 2 of 9.2.3 visibly works for the first time: on the same symbol, M5 / M15 / M30 train on 200 / 250 / 300 bars
  through one code path, and the journal records the window in use.
- Row 9 reads `<regime sentence> | <Cluster> (Supertrend <direction>)` and wraps within the existing fixed width; no new
  row, no colour, no size, no font change; Rows 2–7 and 11–14 stay label-only; the score and the trailing reference
  appear nowhere on the panel.
- The published state carries `direction / line / cluster / multiplier / score` plus `barsSinceFlip`, `flipCount` and
  `distanceATRs`, and `Emtt_Supertrend.mqh` compiles with no reference to the chart, the panel or an EA global.
- Regime and Supertrend may disagree on chart and both show what they measured.
- With less history than the gate needs, the panel still shows `--` with `Waiting — Loading chart history (N/M candles)`
  and the real M for the timeframe; the Price Row stays live and exact. Initialisation with the full replay stays
  visibly instant, with no stutter on ticks.
- On H1 and other charts rule 19 still wins: `--` fields, red incompatible-timeframe STATUS, nothing measured or shown.
- The EA draws nothing but the panel, and all panel objects are still removed cleanly on removal.
- `python -m unittest discover -s tests -v` and `python tools/mql5_compile_smoke.py` pass, with the Phase 3 header in
  the CI contract, the dashboard guard still enforced, and the Phase 2 matrix / clamp / pause now covered.

---

## 13. Phase 4 — Market Structure Detection (SMC)

**Status: SPEC FINALISED (2026-10-08) — BUILD AUTHORISED.** The section 12 gate is cleared: the author verified
Phase 3 on a live MT5 chart on 2026-10-08. On the same date the author delegated this phase's design and **every
number in it** to the builder ("you are the expert / builder / architecture of Emtt, so you finalize"), together with
four standing decisions that this section carries as rules:

1. **no chart drawing of any kind** — the author asked whether Emtt needs the visual or the calculation behind it, and
   the answer under that delegation is the calculation (13.2 rule 1);
2. **dynamic parameters** — the author's own words: Emtt works from standard values and then respects the symbol type,
   the market condition and the chart timeframe (13.10);
3. **a compact Row 9 clause that may wrap onto more lines**, with the panel showing both what Emtt decided and the
   latest thing it is doing, so the user can understand what is happening (13.11);
4. **the phase is delivered whole** — all of 13.3 to 13.9 in one phase, with nothing left partial and no splitting into
   extra sub-phases, because dropping and re-adding phases is a loss of time (13.1 Delivery).

Nothing here waits on a further approval; the build starts on the author's instruction.

Emtt works out **where price sits inside its own structure**: the confirmed turning points, whether the last break
continued or reversed the trend, the zones price tends to return to, the gaps it tends to fill, the liquidity it has
already taken, and whether price is currently cheap or expensive inside the dealing range. All of it is **context, not
a signal** — no BUY/SELL, no confidence figure, no Entry / SL / TP, no orders.

### 13.1 Files

| File | Change |
|---|---|
| `Include/Emtt/Emtt_SMC.mqh` | new — confirmed swings, BOS / CHoCH, liquidity sweeps and pools, Order Blocks, Fair Value Gaps, Premium / Discount, `smcScore` |
| `Experts/Emtt.mq5` | wired into the existing closed-bar path and `FillPanel()`; `#property version` → `1.30`, one `#property description` line updated |
| `tests/phase4_reference.py` + `tests/test_phase4_reference.py` | new — MT5-free mirror of 13.3–13.11, same pattern as Phases 2 and 3; scope in 13.15 |
| `tools/mql5_compile_smoke.py` | contract list gains the new header plus the Phase 4 markers of 13.15; the Phase 1 dashboard guard and every Phase 2 / Phase 3 marker stay |
| `README.md` | one Phase 4 paragraph |

`Include/Emtt/Emtt_Dashboard.mqh` is **not touched** and stays byte-identical (its sha256 guard in
`tools/mql5_compile_smoke.py` keeps enforcing that): rule 12's wrapping and rule 13's growing height are already in
the renderer, so a three-line WHY needs no renderer change. `Emtt_DynamicParams.mqh`, `Emtt_Regime.mqh` and
`Emtt_Supertrend.mqh` are **not touched** and stay byte-identical — Phase 4 consumes them, it never edits an approved
module. Sections 1–12 are **not rewritten**; only status stamps are appended there as phases are implemented and
verified. Inputs stay **Magic number + Auto Trading** — Phase 4 adds none. No new indicator handle, no new file, no
new GlobalVariable: structure is computed in-house from the `MqlRates` the EA already copies and the ATR buffers it
already reads. The panel header string stays `Emtt V1.0` — only the `#property` lines change.

`.github/workflows/phase2.yml` needs no edit and no `phase4.yml` is created: it discovers `tests/` and runs the smoke
check, so the new tests are picked up on their own.

Exact wiring points in `Experts/Emtt.mq5` — Phase 4 adds no others:

- the header is included as `#include "../Include/Emtt/Emtt_SMC.mqh"`, quoted and repo-relative (4b), placed
  **after** the `Emtt_Supertrend.mqh` include, because 13.10 reuses that header's `EmttLookbackScale()` so Layer 2 of
  9.2.3 stays defined in exactly one place;
- one `SEmttSmcState` global (`g_smc`), reset in `EmttResetMarketState()` alongside `EmttDynamicReset()` /
  `EmttRegimeReset()` / `EmttSupertrendReset()`;
- advanced for each bar **inside** the existing `EmttReplayClosedHistory()` loop and again in
  `EmttProcessLatestClosedBar()`, after `EmttBuildMeasurements` / `EmttReadCurrentMeasurements`, after
  `EmttDynamicUpdateVolatility` (so it sees that bar's bucket and `atrPeriod`) and after `EmttSupertrendAdvance`,
  before `EmttSetSnapshot`;
- the four existing `g_historyRequired=EmttHistoryRequired(g_timeframe);` assignments become
  `g_historyRequired=EmttResolveHistoryRequired(g_timeframe);`, a new EA-local helper that returns the `max()` of
  `EmttHistoryRequired()` and `EmttSmcHistoryRequired()` (13.10). `EmttHistoryRequired()` itself is not edited;
- read only in `FillPanel()` — one Row 9 clause and one Row 10 status choice;
- `OnTick()` gains nothing; `EmttReleaseIndicators()` / `OnDeinit()` gain nothing (no handles, no files to release).

**Read in this order before coding:** 4 (where files live, timeframe limit), 5 (the panel contract), 6 (rules 1–21 —
units, points, distances, refresh, palette, rule 11 "no extra rows", rule 19 incompatible charts), 9.2.3 (the four
layers, the three parameter classes and the guard rails Phase 4 must obey), 9.2.8 (the `--` honesty rule and the
loading gate), 11.6 (the component contract this phase copies), 11.8 (Row 9 / Row 10 composition and the history
gate), then 13 in full. **Section 14 is the definition of done** — every bullet in it must hold before the phase is
called implemented.

**This section is self-contained.** It was written from `Emtt.md` alone: every number, rule, format and journal line
Phase 4 needs is defined here. No other document in this repository is a source for this phase, and nothing outside
`Emtt.md` may be consulted to fill a gap — if a detail is missing, it is missing on purpose and belongs to a later
phase (13.16).

**Delivery:** one change set containing exactly the rows of the table above — the new header, the EA wiring, the two
test files, the CI contract, `README.md`. No other file, no refactor of Phase 1, 2 or 3 beyond the wiring points
listed.

The phase is delivered **whole** (the author's decision of 2026-10-08): 13.3 to 13.9 all land in this one change set —
confirmed swings, BOS / CHoCH, liquidity sweeps and pools, order blocks, fair value gaps, Premium / Discount and the
`smcScore` — with nothing left partial, nothing deferred to a later phase and no split into sub-phases, because
dropping and re-adding phases is a loss of time. A delivery that implements part of this section is not a delivery of
it. What is genuinely **not** in this phase is listed in 13.16, and every item there is a different component, never a
piece of this one.

### 13.2 Rules for this phase

1. **Panel only — a standing decision, not a phase limit.** Emtt draws no chart object other than its panel objects:
   no line, rectangle, arrow, channel or chart label, in this phase **or any later one**, unless the author writes
   such a rule. The author asked on 2026-10-08 whether Emtt needs the visual or the calculation behind the visual, and
   left the answer to the builder; the answer is the **calculation**. Every level this phase finds is consumed as a
   number by later phases, and nothing Emtt decides ever reads a drawing — so a drawing would add work, risk and a new
   rule while changing no decision Emtt makes. Verification is provided instead by the Row 9 clause (13.11) and by the
   journal of 13.12, which carries every level with its price and its bar time.
2. **No layout change** — rules 11–17 stand: no new row, fixed width, `Segoe UI`, sizes, palette, colours all as is.
   WHY keeps its default 2 lines and **may wrap to 3 or more** when the clause makes it long (rule 12 allows it, rule
   13 lets the height grow, and the renderer already does both).
3. **Rows 2–7 stay label-only.** The LIVE TRADE block keeps its Phase 2 / Phase 3 behaviour (detected by magic
   number, rows 11–14 label-only). Nothing about orders changes.
4. **Closed bars only**, index 0 never read; the per-tick path stays `UpdatePanel()` only — no measurement on ticks.
5. **Nothing invented** — a field carries a measured value or `--`, as rule 19 and 9.2.8 already require. A level
   that has not been confirmed by closed bars does not exist, and is never shown, guessed or extrapolated.
6. Structure belongs to the **Measurement** class of 9.2.3: adjusted by class + timeframe + volatility, **never by
   the regime**, and it feeds nothing back into the bucket, the regime or the Supertrend.
7. **Components are never reconciled** (11.8). Regime, Supertrend and structure may all disagree on screen at once,
   and each shows exactly what it measured. No wording, colour, ordering or suppression may be used to make them look
   consistent.
8. **No repainting, ever.** A swing, a break, a sweep, a zone and its mitigation are decided once, from closed bars,
   and never revised. If new bars would have changed an earlier decision, the earlier decision stands and the new bars
   produce their own.

### 13.3 Confirmed swings — exact definition

All indices are series indices over the **closed** bars the EA already copies (`0` = the newest closed bar, larger =
older). Every rule below reads only closed bars.

- **Swing high at bar `i`:** `high[i]` is strictly greater than the high of each of the `swingStrength` bars on both
  sides — `i+1 … i+swingStrength` (older) and `i-1 … i-swingStrength` (newer). **Swing low** mirrors it: `low[i]`
  strictly below the low of the same bars on both sides.
- **Confirmation:** a swing at bar `i` can only be recognised once all `swingStrength` newer bars exist and are
  closed, i.e. when `i >= swingStrength`. Because the EA advances one closed bar at a time, a pivot is therefore
  recognised exactly `swingStrength` closed bars **after** it formed — never earlier, and never revised afterwards.
- **Plateau (equal extremes) resolves to one pivot:** when two or more adjacent bars share the same extreme value
  (exact equality of the copied price), the run counts as a single pivot. The pivot **bar** is the **oldest** bar of
  the run; the `swingStrength` newer bars required for confirmation are counted from the **newest** bar of the run, so
  a plateau is not confirmed until price has stopped touching the extreme. The published level is that shared extreme.
- **One pivot per bar:** a bar can never be both a swing high and a swing low. If both tests pass (only possible on a
  bar whose range is narrower than its neighbours on both sides — an inside bar), the bar is **neither**; no
  tie-break is needed because neither test can pass while the other does, and this rule exists only to forbid one.
- **Published state:** the newest confirmed swing high and the newest confirmed swing low inside the structure window
  of 13.10 — each with its level, its pivot bar time and its pivot index — plus the count of confirmed swings of each
  type inside that window.
- A swing outside the structure window is forgotten: it leaves the state, and leaving is never journaled.

### 13.4 Structure events — BOS, CHoCH and liquidity sweeps

Emtt keeps one structural **bias**: `+1` (up), `-1` (down) or `0` (none yet). The bias starts at `0` and is set only
by a break event below; it is never set by the regime, by Supertrend or by a zone label.

Evaluated once per newly closed bar, using **that bar's close** against the newest confirmed swing levels of 13.3:

- **Up break** — `close > newest confirmed swing high`:
  - bias was `-1` → **CHoCH up** (the first sign the down structure has failed);
  - bias was `+1` or `0` → **BOS up** (the up structure continues).
- **Down break** — `close < newest confirmed swing low`:
  - bias was `+1` → **CHoCH down**;
  - bias was `-1` or `0` → **BOS down**.
- **No break** → no event; the bias is unchanged.

Rules that make this steady and honest:

- **A consumed level can never fire twice.** After any break, the broken swing level is removed from the "newest
  confirmed" pair, and the bias becomes the break direction. The next event needs the **next** confirmed swing on the
  opposite side. This is the anti-flicker mechanism for structure — the close beyond a confirmed pivot **is** the
  confirmation, so events carry **no** 2-bar confirmation of their own (unlike the regime label of 9.2.6, and unlike
  the parameter pause of 9.2.3, which governs parameters only).
- **A wick is not a break.** When a closed bar's high pierces a tracked level but its close does not (or its low
  pierces a level and its close does not), that is a **liquidity sweep** (13.7), not a structure event: the bias is
  unchanged, the level is **not** consumed and stays valid, and the level is marked swept.
- **Both breaks in one bar:** if a single closed bar closes beyond both the newest swing high and the newest swing low
  (only possible when one of them was already consumed in the same bar's evaluation, so this cannot normally happen),
  the **up** break is taken and the down break is ignored; the case exists only to forbid an ambiguity.
- **First evaluation:** no event on the very first bar evaluated after init, a timeframe or symbol change, a market
  reopen or a history shortfall reset — the state must first hold a confirmed swing pair. Until then bias stays `0`,
  the measurement is **not ready**, and 13.11 publishes nothing.

### 13.5 Order Blocks — exact definition

An Order Block (OB) is the zone where price is expected to be met by the orders that caused the move away from it.

- **Average body:** the mean of `|close - open|` over the `bodyPeriod` closed bars **older than** the candidate bar
  (13.10). A bar's own body is never part of the average that judges it.
- **Displacement bar:** a closed bar whose body is at least `1.5 ×` that average body —
  `|close - open| >= 1.5 × averageBody`. The multiple is fixed and identical for every class (13.10).
- **Bullish OB:** the **newest** down bar `o` (`close[o] < open[o]`) inside the OB lookback for which some bar `d`,
  newer than `o` and within `3` closed bars of it, is a **bullish displacement** bar (`close[d] > open[d]`) whose
  close is **above `high[o]`**. The zone is the block candle's **full range**: `[low[o], high[o]]`.
- **Bearish OB:** the mirror — the newest up bar `o` (`close[o] > open[o]`) inside the OB lookback for which some bar
  `d` within `3` closed bars newer is a **bearish displacement** bar closing **below `low[o]`**. Zone `[low[o], high[o]]`.
- **Mitigated:** a later closed bar whose range touches the zone (`low <= zoneHigh && high >= zoneLow`). A mitigated
  zone is no longer offered as the published block, but it stays in state with its mitigation bar recorded, because
  the later management phase reads how many blocks price has already used.
- **Invalidated:** a later closed bar **closes through the far edge** — a bullish OB when `close < zoneLow`, a bearish
  OB when `close > zoneHigh`. An invalidated zone leaves the state at once and can never return.
- **Published block:** for bias `+1`, the nearest **bullish** zone that is active (not mitigated, not invalidated)
  whose `zoneHigh` is **at or below** the newest close; for bias `-1`, the nearest **bearish** zone whose `zoneLow` is
  **at or above** it. "Nearest" is by price distance from the close, not by age. If none qualifies, no block is
  published and the fact reads `hasOrderBlock = false` — the panel then simply omits that part (13.11).
- **Near edge:** the edge price meets first — `zoneHigh` for a bullish block, `zoneLow` for a bearish one. It is the
  price shown in the Row 9 clause and the anchor of `distanceToOBATRs` in 13.9.
- **Capacity:** at most `8` active zones per direction. When a ninth would be added, the **oldest** is dropped. The
  bound is a safety limit only — the OB lookback of 13.10 keeps the natural count far below it — and a capacity drop
  is never journaled.

### 13.6 Fair Value Gaps — exact definition

A Fair Value Gap (FVG) is a hole left by a move fast enough that the outer candles never overlapped.

- Three consecutive **closed** bars `a`, `b`, `c` (`c` the newest of the three), evaluated on the close of `c`:
  - **Bullish FVG** when `low[c] > high[a]` → the zone is `[high[a], low[c]]`;
  - **Bearish FVG** when `high[c] < low[a]` → the zone is `[high[c], low[a]]`.
- **Mitigated** when a later closed bar's range overlaps the zone. Mitigation is recorded in state and is **not**
  journaled — it is a routine touch, and journaling it would flood the log (13.12).
- **Filled** (and removed from the active set) when a later closed bar **closes through the far edge**: a bullish FVG
  when `close < high[a]` (the zone's lower boundary), a bearish FVG when `close > low[a]` (its upper boundary).
- **Published gaps:** the nearest **active** gap whose zone lies **above** the newest close, and the nearest active
  gap whose zone lies **below** it, each with its type, its boundaries and its distance. "Nearest" is by price
  distance from the close. A gap is above when its lower boundary is at or above the close, below when its upper
  boundary is at or below it; a gap the close is standing inside counts as neither and is reported as mitigated.
- **Near edge:** for a gap above, its **lower** boundary; for a gap below, its **upper** boundary — the price that
  meets it first. This is the price shown in the Row 9 clause and the anchor of `gapDistanceATRs` in 13.9.
- **Capacity:** at most `8` active gaps, oldest dropped first, never journaled — the same safety bound as 13.5.

### 13.7 Liquidity — sweeps and pools

- **Sweep:** a closed bar whose **wick** takes out a tracked level while its **close** does not (13.4). Tracked levels
  are the newest confirmed swing high, the newest confirmed swing low, and every pool level of this section that is
  still inside the structure window. A sweep above a level is **buy-side** (the stops resting above the highs were
  taken); a sweep below is **sell-side**.
- A sweep never changes the bias, never consumes the level and never invalidates a zone. It is recorded with its side,
  its level, its bar time and a `barsSinceSweep` counter that increments on every closed bar afterwards.
- **Pool (equal highs / equal lows):** two or more confirmed swings **of the same type** inside the structure window
  whose levels differ by no more than `0.10 × ATR` form one pool. The tolerance is fixed and identical for every
  class (13.10). Pool level = the **mean** of its members' levels; pool count = the number of members; pool side =
  `buy-side` for equal highs, `sell-side` for equal lows. Members that leave the structure window leave the pool, and
  a pool with fewer than 2 remaining members is no longer a pool.
- **Published:** the newest sweep (side, level, `barsSinceSweep`) and the largest pool of each side still inside the
  window (level, count). These are facts for the later SL / TP phase — stops belong beyond liquidity — and are scored
  only as 13.9 says.

ATR used throughout 13.5–13.9: the matrix `atrPeriod` currently resolved for this bar (class + bucket) and its value
at the newest closed bar — the same ATR the Supertrend reads in 11.3. The fixed ATR(14) measuring stick of 9.2.2 is
**not** used here.

### 13.8 Premium / Discount — exact definition

- **Dealing range:** take the newest confirmed swing of 13.3 (the **end** of the current leg) and the newest confirmed
  swing of the **opposite type** older than it (the **origin**). The range is `[min(level), max(level)]` of those two.
  The leg direction is **up** when the end is a swing high, **down** when it is a swing low. Both swings must be
  inside the structure window; if either is missing there is no range and no zone label.
- **Equilibrium** = `(rangeHigh + rangeLow) / 2`.
- **Minimum range:** the range must be at least `1.0 × ATR` tall. Below that the range is noise, no zone is
  classified, and the panel shows no zone word — a two-point range must never produce `Premium` or `Discount`.
- **Zone** from the newest closed bar's close, with `range = rangeHigh - rangeLow`:
  - **Discount** when `close < equilibrium - 0.05 × range`;
  - **Premium** when `close > equilibrium + 0.05 × range`;
  - **Equilibrium** otherwise — the `±5%` band **is** the margin, so a close resting exactly on the midpoint has a
    label of its own and cannot flicker between the other two. No separate entry / exit levels are needed.
- **Zone position** = `clamp01((close - rangeLow) / range)` — 0.0 at the range low, 1.0 at the range high. Published
  as a fact; displayed nowhere.
- The zone is a **reading**, not a gate. The SMC rule "buy only in Discount, sell only in Premium" is expressed in
  this phase **only** as the score term of 13.9; gating belongs to the signal phase.

### 13.9 What Phase 4 publishes — the component contract

This is the same shape 11.6 defined and every later component copies. `Emtt_SMC.mqh` owns one `SEmttSmcState`, the EA
keeps a single instance of it, and nothing in it is displayed beyond what 13.11 allows.

- **Readings:** `bias` (+1 / -1 / 0), `eventKind` (BOS / CHoCH / none), `eventDirection`, `zone`
  (Premium / Discount / Equilibrium / none), `hasOrderBlock` + the block's zone and near edge, `hasGapAbove` /
  `hasGapBelow` + each gap's type, zone and near edge, `lastSweepSide`, `poolSide` + `poolCount`, `legDirection`.
- **Facts, not only labels:** `barsSinceEvent`, `barsSinceSweep`, `distanceToOBATRs`, `gapDistanceATRs`,
  `zonePosition`, `dealingRangeHigh` / `dealingRangeLow` / `equilibrium`, `mitigatedBlockCount`, `activeGapCount`,
  `confirmedSwingCount`, and the `atrPeriod` / `atrValue` / `structureWindow` / `swingStrength` the reading was made
  on.
  - `distanceToOBATRs` = `(close - blockNearEdge) / ATR` for bias `+1`, `(blockNearEdge - close) / ATR` for bias `-1`,
    clamped to 0 when price has already reached or passed into the zone. It is only defined when a block is published.
  - `gapDistanceATRs` = `(gapNearEdge - close) / ATR` for the gap **above**, `(close - gapNearEdge) / ATR` for the gap
    **below**, in the direction of the bias, clamped to 0. Only defined when such a gap exists.
- **`smcScore`, a single 0.0–1.0 number**, computed from those closed-bar facts only. Five terms, weights summing to
  exactly 1.0, `clamp01(x) = max(0, min(1, x))`:

  | Term | Weight | Value |
  |---|---|---|
  | **Structure** | 0.30 | last event is a **BOS** in the bias direction → `1.0`; a **CHoCH** → `0.6`; no event → `0.0` |
  | **Freshness** | 0.20 | `clamp01(1 - barsSinceEvent / 40)` — an event 40 or more closed bars old contributes nothing |
  | **Zone** | 0.20 | bias `+1`: Discount → `1.0`, Equilibrium → `0.5`, Premium → `0.0`. Bias `-1`: Premium → `1.0`, Equilibrium → `0.5`, Discount → `0.0`. No zone → `0.0` |
  | **Entry proximity** | 0.15 | `clamp01(1 - distanceToOBATRs / 2.0)` — a published block within 2 ATRs scores highest; no block → `0.0` |
  | **Sweep confirmation** | 0.15 | `clamp01(1 - barsSinceSweep / 20)` when the newest sweep is on the side **opposite** the bias (sell-side for bias `+1`, buy-side for bias `-1`) — the stop hunt that fuelled the move; otherwise `0.0` |

  `score = 0` whenever `bias` is `0`.
- **Why the score exists now:** Row 3 (rule 6) is one combined figure, and the phase that fills it sums one such score
  per component. Deriving it here costs nothing, changes nothing the user sees, and stops the confidence phase from
  having to rewrite and re-verify a finished module (11.6).
- **What the score is not:** it gates nothing in this phase, places nothing, and is never shown. It may never adjust a
  parameter, a bucket, a regime or a Supertrend value — readings are outputs, not inputs, to the engine of 9.2.3.
- **Ready:** the measurement is ready when the state holds a confirmed swing high **and** a confirmed swing low inside
  the structure window and a valid `atrValue`. Before that, `ready = false`, the score is `0`, and 13.11 publishes
  nothing at all — no partial clause, no half-measured status.
- Later phases publish the same contract, so the confidence phase only ever sums weights. This section defines no
  weights for any other component and no combining rule.

### 13.10 Rows Phase 4 adds to the parameter table of 9.2.3

The author's decision of 2026-10-08: these numbers are **dynamic**. Emtt starts from standard values and then
respects the **symbol type** (asset class), the **market condition** (the live volatility bucket) and the **chart
timeframe** — through the same four layers, the same tables and the same code path as everything else in 9.2.3.
Nothing here is hardcoded per timeframe and no number is fixed by hand for one symbol.

**Layer 1 base matrix (Low / Normal / High volatility):**

| Parameter | Forex Major | Forex Cross | Metals | Crypto | Indices | Generic |
|---|---|---|---|---|---|---|
| Structure window (closed bars, **lookback**) | 60 / 60 / 80 | 60 / 60 / 80 | 50 / 60 / 80 | 40 / 50 / 70 | 50 / 60 / 80 | 60 / 60 / 80 |
| Swing strength (bars each side, **period**) | 2 / 2 / 3 | 2 / 2 / 3 | 2 / 3 / 3 | 2 / 3 / 4 | 2 / 2 / 3 | 2 / 2 / 3 |
| Displacement body period (**period**) | 14 / 14 / 21 | 14 / 14 / 21 | 14 / 14 / 21 | 14 / 14 / 21 | 14 / 14 / 21 | 14 / 14 / 21 |

Why these numbers: a wilder market needs a **longer** window before a range means anything, and a **stronger** pivot
before a turning point counts; crypto is faster and noisier, so its window is shorter (structure goes stale sooner)
while its pivot is stricter. The body period is class-independent — it is a smoothing period, and 14 / 21 matches the
ATR periods already in 9.2.3.

**Layer 2 (timeframe) applies to the structure window only**, because it is the only **lookback** here:
`×1.0 / ×1.25 / ×1.5` for M5 / M15 / M30, through the existing `EmttLookbackScale()`. Swing strength and the body
period are **periods**, not lookbacks, so Layer 2 does **not** scale them — the timeframe is already inside the
candles (9.2.3).

**Rounding is part of the definition:** a scaled window is rounded to a whole bar **half away from zero** — MQL5's
`MathRound`, never a truncation and never banker's rounding. Phase 3 never hit a fractional bar (200 × 1.25 and
200 × 1.5 are both whole); this phase does (`50 × 1.25 = 62.5`, `70 × 1.25 = 87.5`), so the rule is written down:
`62.5 → 63` and `87.5 → 88`. The portable mirror of 13.15 must use the same rule and must **not** use Python's
built-in `round()`, which would give 62 and 88 and silently disagree with the EA.

Resolved structure window, Low / Normal / High volatility, as **M5 / M15 / M30**:

| Class | Low | Normal | High |
|---|---|---|---|
| Forex Major, Forex Cross, Generic | 60 / 75 / 90 | 60 / 75 / 90 | 80 / 100 / 120 |
| Metals, Indices | 50 / 63 / 75 | 60 / 75 / 90 | 80 / 100 / 120 |
| Crypto | 40 / 50 / 60 | 50 / 63 / 75 | 70 / 88 / 105 |

**Derived, not a second matrix:** `OB lookback = max(10, round(structureWindow / 3))` closed bars. It inherits all
three layers through the window it is derived from — e.g. Forex Major on Normal volatility resolves to
`20 / 25 / 30` bars on M5 / M15 / M30.

**Layer 3 (volatility)** reads the Low / Normal / High column for the current bucket, exactly as 9.2.3 says.
**Layer 4 (context / regime)** never touches any of them: all four dynamic values — the structure window, the swing
strength, the body period and the OB lookback derived from the first — are **Measurement** class.

**Fixed, adjusted by no layer** (the same standing as Bollinger (20, 2.0) and the 200-bar volatility window in 9.2.3):
displacement multiple `1.5 ×` average body · impulse window `3` closed bars · equal-level tolerance `0.10 × ATR` ·
zone dead band `±0.05 × range` · minimum dealing range `1.0 × ATR` · zone capacity `8` per direction and `8` gaps ·
the five score weights and their scales `40` / `2.0` / `20` · the CHoCH structure term `0.6` · the Row 10 freshness
window `3` closed bars · the Row 9 sweep mention window `10` closed bars.

**Guard rails of 9.2.3 apply to all four dynamic values:** clamped inside the class table's own Low … High span after
Layer 2 scaling (the structure window never below `20` closed bars, never above `400`); **one change, then the same
parameter stays put for the next 2 closed bars** — reusing the existing `EmttCanChangeAt()`; every change journaled
with its reason. The pause governs the **parameters only** — bias, zone, blocks, gaps, sweeps and the score are
readings and are never delayed or damped by it.

**A parameter change rebuilds, it does not guess:** when the structure window, the swing strength or the body period
changes, the structure state is rebuilt by replaying the new window from the copied closed bars — silently, writing no
event journals, exactly like the init replay of 13.12 — so the bias, the consumed levels and the zones after the
change are the same as they would have been had the new value been in use all along. Only the parameter change itself
is journaled.

**Required history — one gate for all measurements (supersedes 11.8's figure only if it is larger).** The gate becomes
`max(EmttHistoryRequired(timeframe), EmttSmcHistoryRequired(timeframe))`, where
`EmttSmcHistoryRequired = structureWindow + swingStrength + bodyPeriod + 2` closed bars, resolved by the same code
path. On the largest combination this phase can produce (Forex Major / Cross / Generic, High volatility, M30:
`120 + 3 + 21 + 2 = 146`) the Supertrend requirement is still the larger one, so **the gate stays 250 / 300 / 350
closed bars for M5 / M15 / M30 and the loading line's M does not change**. The `max()` is required anyway: one code
path, no hardcoded figure, and the phase that finally raises the gate does not have to retrofit it. While the gate is
open, Rows 1, 9 and 10 behave exactly as they do today — no partial, half-measured display.

### 13.11 Panel wiring

The author's decision of 2026-10-08: the panel must carry both **what Emtt decided** and **the latest thing it is
doing**, in words short enough to read at a glance, so that the user can always understand what is happening. Row 9
carries the decision — the context this component measured — and Row 10 carries the latest action. Wording stays
compact; growing the WHY block onto a third line is explicitly acceptable, while the panel width never changes.

- **Row 9 (WHY):** the Phase 2 regime sentence, then ` | `, then the Phase 3 Supertrend clause, then ` | `, then the
  **structure clause**. The structure clause is compact and has **at most three comma-separated parts**, always in
  this fixed order, each part omitted when it has not been measured:

  | Part | Values | Omitted when |
  |---|---|---|
  | zone | `Discount` / `Premium` / `Equilibrium` | no dealing range, or the range is under `1.0 × ATR` |
  | event | `BOS up` / `BOS down` / `CHoCH up` / `CHoCH down` | no break event yet (bias `0`) |
  | level | `OB <price>` — else `FVG <price>` — else `swept lows` / `swept highs` | no block, no gap in the bias direction, and no sweep inside the last `10` closed bars |

  Only **one** level is ever shown — the first available in that priority order — so the clause stays short (the
  author's decision of 2026-10-08). `<price>` is the near edge of 13.5 / 13.6, formatted with the symbol's own digits,
  the same digits the Price Row uses. `swept lows` is a sell-side sweep, `swept highs` a buy-side one.

  Examples: `Discount, BOS up, OB 1.08450` · `Premium, CHoCH down, FVG 1.09120` ·
  `Equilibrium, BOS down, swept highs` · `Discount` (a range exists, no break yet).
  If **all three** parts are omitted — the measurement is ready but there is no classifiable range, no break yet and
  no level — the clause is empty and **nothing is appended**: Row 9 then reads exactly as it does in Phase 3. An empty
  clause never adds a trailing ` | `.
  Whole Row 9: `Efficiency 71/100 and KAMAs aligned up; volatility normal | Wild (Supertrend bullish) | Discount, BOS up, OB 1.08450`.
  When the structure measurement is not ready, or the market is closed, or the chart is incompatible, **no structure
  clause is appended** and Row 9 shows exactly what it shows today.
- **Row 10 (STATUS):** precedence stays rule 19 > loading history > `MARKET CLOSED`, then the structure statuses below,
  then the Phase 3 Supertrend status, then the Phase 2 regime / pending lines exactly as they are. An event or a sweep
  counts as **fresh** for `3` closed bars after the bar it happened on; when several are fresh, **CHoCH outranks BOS,
  and BOS outranks a sweep** — a reversal warning is more important than a continuation, which is more important than
  a wick:
  - `Watching — CHoCH up, structure may be reversing` / `Watching — CHoCH down, structure may be reversing`
  - `Watching — BOS up confirmed, trend continuing` / `Watching — BOS down confirmed, trend continuing`
  - `Watching — Liquidity swept above, no structure break` / `Watching — Liquidity swept below, no structure break`
  - otherwise, once the measurement is ready: `Watching — structure context only, no signal yet`

  Section 7's `No trade — …` messages still belong to the phase that can place orders.
- **Rows 1–8 and 11–14 unchanged.** `Expected Duration:` stays empty. The score, the bias, the dealing range, the
  equilibrium, the zone boundaries, the pools, the mitigated counts and every fact of 13.9 are **never displayed**:
  rule 11 gives them no row.
- **Incompatible timeframe** (rule 19): unchanged — `--` fields, the red message, the Price Row still live. Rule 19
  wins over every structure state.
- **Nothing invented:** every word in the clause comes from a closed-bar measurement of this phase, and the panel
  never shows a level Emtt has not confirmed.

### 13.12 Determinism, replay, state, journal

- **No RNG, no clock, no tick data, no file access** in any Phase 4 calculation. Same closed bars in → same swings,
  same events, same consumed levels, same sweeps, same pools, same zones and their mitigations, same zone label, same
  score — on any machine, at any time, when replayed.
- All Phase 4 state is **reconstructed by replaying closed bars** on init, on a timeframe or symbol change, on market
  reopen and after any history shortfall reset — using the same replay path Phases 2 and 3 already use. State never
  carries over from a previous session: **no new file, no new GlobalVariable** (the Phase 2 threshold-freeze key stays
  exactly as it is).
- The replay **must** walk the swing / event / zone lifecycle bar by bar — it may not simply recompute the newest bar
  from scratch. That walk is what makes a restart reproduce the same bias, the same already-consumed levels, the same
  mitigated zones and the same 2-bar parameter pause. Skipping the replay to save time is not allowed.
- **Bounded cost.** Per closed bar the work is bounded by a constant: the OB lookback scan (at most `40` bars), the
  active zone lists (at most `16`), the swing test (at most `2 × swingStrength + 1` bars) and the confirmed-swing list
  (at most `64`) — **never** the whole structure window per bar and never the whole copied history. The full init
  replay is therefore bounded by `350 closed bars × that constant`, once, on the timer. Nothing may run per tick,
  where only `UpdatePanel()` belongs. Confirmed swings are kept in that bounded list of `64`, oldest dropped first;
  pools are formed from the list, never from a rescan.
- **Journal** through the existing `PrintFormat` channel, on the closed bar, with its reason, same shape as Phases 2
  and 3 (`Emtt | <what> | <detail> | bar <time>`):
  - `Emtt | Structure CHoCH down | close 1.08240 broke swing high 1.08620 (pivot 2026.10.08 12:15) | bias up -> down | bar 2026.10.08 14:30`
  - `Emtt | Structure BOS up | close 1.08650 broke swing high 1.08620 (pivot 2026.10.08 12:15) | bias up | bar 2026.10.08 14:30`
  - `Emtt | Liquidity swept below 1.08280 | sell-side | wick 1.08265, close held 1.08310 | bar 2026.10.08 14:30`
  - `Emtt | Equal lows pooled at 1.08280 | 3 confirmed swings within 0.10 x ATR | sell-side | bar 2026.10.08 14:30`
    (logged once, when a pool first reaches two members)
  - `Emtt | Order block bullish 1.08410-1.08450 | displacement 1.6x average body | bar 2026.10.08 14:30`
  - `Emtt | Order block bullish invalidated | close 1.08390 through 1.08410 | bar 2026.10.08 14:30`
  - `Emtt | Fair value gap bullish 1.08500-1.08530 | bar 2026.10.08 14:30`
  - `Emtt | Fair value gap bullish filled | close 1.08490 through 1.08500 | bar 2026.10.08 14:30`
  - `Emtt | Structure window 75 -> 100 closed bars | volatility NORMAL -> HIGH | bar 2026.10.08 14:30` — and the same
    shape for `Swing strength 2 -> 3` and `Displacement body period 14 -> 21`
  - one summary line after the init / reset replay, mirroring the Supertrend one:
    `Emtt | Structure replayed | window 75 closed bars (M15 x1.25) | swing strength 2 | bias up | zone Discount | OB 1.08450 | score 0.62 | bar 2026.10.08 14:30`
- **Never journaled:** a zone or gap **mitigation** (a routine touch — recorded in state, and visible in the facts, but
  it would flood the log), a capacity drop, a swing or pool member ageing out of the window, the readings themselves
  (bias, zone, score — they are re-readable from the chart and from the Row 9 clause), and any bar where nothing
  changed. The panel gets no parameter row (rule 11); the journal is the only record, and it must let the author
  reconstruct exactly what Emtt saw, and at which price, at any moment — this is what replaces chart drawing (13.2
  rule 1).

### 13.13 Freeze semantics — unchanged

The frozen set stays exactly as 9.2.3 wrote it (SL / TP multiples, breakeven, trailing, duration, confidence
threshold). Phase 4 adds **nothing** to it and freezes **nothing** new: while an Emtt position is open, the swings,
events, zones, gaps, sweeps, zone label and score keep measuring and keep journaling live, and the panel never
freezes (9.2.3).

### 13.14 Design seam for the later Multi-Timeframe phase

`Emtt_SMC.mqh` exposes a state struct plus functions that take the symbol, timeframe and closed-bar data as arguments;
the header reads no chart, no panel and no EA global — the same discipline 11.11 imposed on Phase 3.

- The MTF phase must be able to instantiate a **second** `SEmttSmcState` for the higher timeframe with **no change to
  this header**.
- **Phase 4 introduces exactly one new global in `Experts/Emtt.mq5`** (`g_smc`) and no other single-timeframe global.
  The Phase 2 and Phase 3 headers keep taking their state as arguments and are never given globals here.
- Layer 2 stays defined once: this header **calls** `EmttLookbackScale()` from `Emtt_Supertrend.mqh` (hence the include
  order fixed in 13.1) and never re-states the `×1.0 / ×1.25 / ×1.5` figures.
- Carried forward, **not built now:** the MTF phase owns the change that wraps the Phase 2, Phase 3 and Phase 4 state
  into one context per symbol + timeframe. Writing that constraint here stops it from arriving as a rewrite of three
  approved phases.

### 13.15 Tests

`tests/phase4_reference.py` mirrors 13.3–13.11 in the same style as Phases 2 and 3, and
`tests/test_phase4_reference.py` asserts, without MT5:

- **Swings:** a pivot needs `swingStrength` closed bars on **both** sides; an unconfirmed extreme is never used; a
  plateau resolves to one pivot at its **oldest** bar with confirmation counted from its **newest**; a bar is never
  both a swing high and a swing low; swings outside the window are forgotten.
- **Events:** BOS vs CHoCH from the prior bias; a consumed level cannot fire twice; a wick-only pierce is a sweep and
  leaves the bias and the level untouched; no event on the first evaluation; `bias 0` until the first break.
- **Order Blocks:** displacement `>= 1.5 ×` the average body of the `bodyPeriod` bars **older** than the candidate;
  the impulse within `3` bars closing beyond the block's extreme; zone = the block candle's full range; mitigation on
  touch; invalidation on a close through the far edge, and never a return; nearest-active selection per bias by price
  distance, not age; the near edge; capacity `8` with oldest-first eviction.
- **Fair Value Gaps:** the three-bar non-overlap test in both directions; mitigation vs filling through the far edge;
  nearest active gap above and below; a gap the close stands inside is neither.
- **Liquidity:** pools from swings of the same type within `0.10 × ATR`; pool level = the mean; count; a pool below two
  members is no longer a pool; sweep side and `barsSinceSweep`.
- **Zone:** the dealing range from the newest confirmed swing plus the newest opposite-type swing older than it;
  equilibrium = the midpoint; the `±0.05 × range` dead band, including a close exactly on the midpoint reading
  `Equilibrium`; the `1.0 × ATR` minimum range producing **no** zone; `zonePosition` bounds.
- **Score:** the five weights sum to exactly `1.0`; every term inside `0.0 … 1.0`; `bias 0 → score 0`; BOS `1.0` vs
  CHoCH `0.6`; the zone term is direction-sensitive (Discount scores for bias up and zero for bias down, and the
  mirror); the `2.0`-ATR proximity scale and the `40` / `20`-bar age scales; the opposite-side sweep rule; a block
  price already reached clamping distance to `0`.
- **Parameters:** the class / bucket matrix of 13.10 for all six classes and three buckets; Layer 2 scaling of the
  structure window only, with **half-away-from-zero** rounding (`62.5 → 63`, `87.5 → 88`) asserted explicitly and
  Python's built-in `round()` never used for it; swing strength and body period **not** scaled;
  `OB lookback = max(10, round(window / 3))`; clamping to `20 … 400`; the 2-closed-bar pause via the existing
  `can_change_at`; a parameter change rebuilding the state to match a from-scratch replay at the new value.
- **History gate:** `max()` of the Supertrend and structure requirements for every class, bucket and timeframe, and
  the assertion that it still resolves to **250 / 300 / 350** on today's numbers.
- **Panel text:** every Row 9 clause format and omission rule, the three-part cap, the single-level priority
  (OB → FVG → sweep), digit formatting; every Row 10 status string and its precedence
  (CHoCH > BOS > sweep > Supertrend > regime) inside the 3-bar freshness window; rule 19 and the loading gate beating
  all of them.
- **Determinism:** the same series replayed twice gives identical state; a restart, a timeframe round-trip and a
  mid-window parameter change all reproduce the same bias, zones and score.

`tools/mql5_compile_smoke.py` gains the new header in its required-source set and asserts at least these Phase 4
markers, alongside every existing Phase 2 and Phase 3 marker and the unchanged Phase 1 dashboard digest:
`EMTT_SMC_DISPLACEMENT_MULTIPLE 1.5`, `EMTT_SMC_IMPULSE_BARS 3`, `EMTT_SMC_EQUAL_TOLERANCE_ATR 0.10`,
`EMTT_SMC_ZONE_DEADBAND 0.05`, `EMTT_SMC_MIN_RANGE_ATR 1.0`, `EMTT_SMC_MAX_ZONES 8`, `EMTT_SMC_MAX_SWINGS 64`,
`EMTT_SMC_WEIGHT_STRUCTURE 0.30`, `EMTT_SMC_WEIGHT_FRESHNESS 0.20`, `EMTT_SMC_WEIGHT_ZONE 0.20`,
`EMTT_SMC_WEIGHT_PROXIMITY 0.15`, `EMTT_SMC_WEIGHT_SWEEP 0.15`, `EMTT_SMC_EVENT_AGE_BARS 40`,
`EMTT_SMC_PROXIMITY_ATRS 2.0`, `EMTT_SMC_SWEEP_AGE_BARS 20`, `EMTT_SMC_CHOCH_TERM 0.6`,
`EMTT_SMC_OB_LOOKBACK_DIVISOR 3`, `EMTT_SMC_OB_LOOKBACK_MIN 10`, `EMTT_SMC_WINDOW_MIN 20`, `EMTT_SMC_WINDOW_MAX 400`,
`EMTT_SMC_STATUS_FRESH_BARS 3`, `EMTT_SMC_SWEEP_MENTION_BARS 10`, and in the EA
`#include "../Include/Emtt/Emtt_SMC.mqh"`, `SEmttSmcState g_smc;`, `EmttSmcAdvance(`, `EmttWhyWithSmc(`,
`EmttResolveHistoryRequired(`, plus a guard that **no chart-drawing call** (`ObjectCreate` with any type other than the
panel's `OBJ_LABEL` / `OBJ_RECTANGLE_LABEL`, and every `OBJ_TREND`, `OBJ_RECTANGLE`, `OBJ_HLINE`, `OBJ_ARROW`,
`OBJ_TEXT`, `OBJ_FIBO*`) appears in `Emtt_SMC.mqh` at all — 13.2 rule 1 enforced by the build, not by memory.

### 13.16 Not in this phase

No confidence engine, no weights for any component, no Row 2 / Row 3 values, no Entry / SL / TP, no Risk:Reward, no
Expected Duration, no order placement or trade management, no Volume Profile / CVD / VWAP, no multi-timeframe
agreement, no news or session blocking, **no chart drawing of any kind**, no alerts, no self-learning or
parameter-optimization persistence, no new inputs, no new panel row, no change to the palette, the font, the panel
width or any approved module.

---

## 14. Phase 4 — Done When

**Status: SPEC FINALISED (2026-10-08) — NOT YET BUILT.** Every bullet below must hold before the phase is called
implemented. The portable bullets are proven by `python -m unittest discover -s tests -v` and
`python tools/mql5_compile_smoke.py`; the live-terminal bullets are the author's to confirm on a real MT5 chart,
exactly as sections 10 and 12 were, and the status stamps of this section are appended only when they pass.

**Status: IMPLEMENTED (2026-10-08) — VERIFIED BY THE AUTHOR.** Working as specified, confirmed by Ham on
2026-10-08; the MetaEditor compile and the on-chart checks of this section are settled by that live run, exactly
as sections 10 and 12 were. Phase 4 is closed; no later phase reopens it. Sources at close:
`Include/Emtt/Emtt_SMC.mqh` (sha256 `1691c9239274`) and the Phase 4 wiring in `Experts/Emtt.mq5`
(sha256 `ca0bf6d396c3`); `python -m unittest discover -s tests -v` → 85 tests, all passing (12 Phase 2 +
44 Phase 3 + 29 Phase 4); `python tools/mql5_compile_smoke.py` green on the branch.

**Parser check: REQUIRED AT DELIVERY (Hard Rule 3).** `python tools/mql5_parser_check.py` must exit `0` with
`0 syntax errors` on the Phase 4 sources — the built-in negative control rejected first, then `Emtt_SMC.mqh` and the
Phase 4 wiring in `Experts/Emtt.mq5` reported clean, with their sha256 and node counts recorded here as they were in
sections 8, 10 and 12.

- Swings, events, sweeps, pools, order blocks, gaps, the zone label and the score come from **closed bars only**; index
  0 is never read, and nothing at all runs on ticks.
- Nothing repaints: a swing, a break, a sweep, a zone and its mitigation are decided once and never revised. Restart,
  timeframe round-trip and chart replay reproduce **identical** bias, events, zones, gaps, zone label and score.
- A wick never breaks structure: only a close beyond a confirmed pivot does, and a consumed level can never fire twice.
- The structure window, the swing strength, the body period and the OB lookback derived from the window follow the
  class / bucket matrix and Layer 2, change at most once and then not again for 2 closed bars, stay clamped, and every
  change appears in the journal with its reason. The bias, the zone, the blocks, the gaps and the score are **never**
  delayed or damped by that pause.
- Layer 2 of 9.2.3 visibly works on a second parameter: on the same symbol, M5 / M15 / M30 resolve the structure
  window through one code path (`60 / 75 / 90` for a Forex Major on Normal volatility), with half-away-from-zero
  rounding, and the journal records the window in use.
- The history gate is the `max()` of both requirements and still resolves to **250 / 300 / 350**; the loading line's M
  is unchanged, and while the gate is open Rows 1, 9 and 10 behave exactly as they do today.
- Row 9 reads `<regime sentence> | <Cluster> (Supertrend <direction>) | <structure clause>`, the structure clause has
  at most three comma parts and only one level, and the whole row wraps inside the existing fixed width with no new
  row, no colour, no size and no font change. Rows 2–7 and 11–14 stay label-only; `Expected Duration:` stays empty.
- Row 10 shows the freshest structural fact with the precedence of 13.11, and section 7's `No trade — …` messages
  still do not appear.
- The score, the bias, the dealing range, the equilibrium, the zone boundaries, the pools and every other fact of
  13.9 appear **nowhere** on the panel.
- Regime, Supertrend and structure may all disagree on screen at the same time, and each shows exactly what it
  measured — nothing is worded, coloured or suppressed to make them look consistent.
- Every level Emtt reports is in the journal with its price and its bar time, so the author can check each one against
  the chart without Emtt drawing anything.
- **The EA still draws nothing but the panel** — no line, rectangle, arrow or chart label of any kind — and all panel
  objects are still removed cleanly when the EA is removed from the chart.
- `Emtt_Dashboard.mqh`, `Emtt_DynamicParams.mqh`, `Emtt_Regime.mqh` and `Emtt_Supertrend.mqh` are byte-identical;
  inputs are still Magic number + Auto Trading; there is no new handle, file, GlobalVariable or chart object; and
  `Emtt_SMC.mqh` compiles with no reference to the chart, the panel or an EA global.
- On H1 and other charts rule 19 still wins: `--` fields, the red incompatible-timeframe STATUS, nothing measured or
  shown, Price Row still live and exact.
- Initialisation with the full replay stays visibly instant, with no stutter on ticks.
- On a live MT5 chart, the author confirms what Emtt now says is what the chart actually did: the peaks and valleys it
  calls swings are the ones visible on screen; a break it calls `BOS` continued the trend and a break it calls `CHoCH`
  really was the turn; the block it names sits where price later reacted; `Discount` / `Premium` matches the half of
  the range price is standing in; and `swept highs` / `swept lows` matches a wick that poked through and came back.
- `python -m unittest discover -s tests -v` and `python tools/mql5_compile_smoke.py` pass, with the Phase 4 header and
  markers in the CI contract, the no-drawing guard enforced, and the Phase 1 dashboard digest plus every Phase 2 and
  Phase 3 marker still asserted.

---

## 15. Phase 5 — Volume Flow (Volume Profile + CVD + VWAP) and Multi-Timeframe Agreement

**Status: SPEC APPROVED (2026-10-08) — BUILD AUTHORISED.** The section 14 gate is cleared: the author confirmed
Phase 4 complete and verified on 2026-10-08. On the same date the author ordered **both** components of this
section — the money-flow reading and the higher-timeframe check — into **one phase**, because both are
observation-only (no orders, no new rows, no new risk) and both follow the exact component pattern of Phases 3
and 4. Design and **every number in this section** remain delegated to the builder (continued from Phase 4:
"you are the expert / builder / architecture of Emtt, so you finalize"), under four standing decisions carried
as rules here:

1. **no chart drawing of any kind** (13.2 rule 1, standing);
2. **dynamic parameters** through the four layers of 9.2.3 (13.10, standing);
3. **compact Row 9 clauses that may wrap**, one level shown, so the user always understands what is happening
   (13.11, standing);
4. **the phase is delivered whole** — all of 15.3 to 15.9 in one change set, nothing partial, no sub-phases
   (13.1 Delivery, standing).

On 2026-10-08 the author finalized the three open design questions of this section by delegation to the builder
("being the architecture and master of creating this EA, you decide what will be good for real money trading"):
the CVD stays the **closed-bar estimate** of 15.6 (tick-level CVD remains with the trade-management phase,
15.16); the naked POC is the **previous session's** unvisited POC (15.5 — session-based, stable for the whole
session, the textbook SMC meaning of the word); and the HTF mapping stays **M5 → M15 / M15 → H1 / M30 → H4**
(15.8). These are carried as rules of this section.

Emtt works out **where the money actually went and whether the bigger chart agrees**: the session's fair price
(VWAP), the price band where most of the session's volume traded (volume profile — POC / value area), the level
price has not revisited yet (naked POC), whether aggressive buying or selling dominates right now (CVD), and —
on the chart one size up — whether the trend, the market mood and the structure there support what the current
chart shows. All of it is **context, not a signal** — no BUY/SELL, no confidence figure, no Entry / SL / TP, no
orders.

### 15.1 Files

| File | Change |
|---|---|
| `Include/Emtt/Emtt_VolumeFlow.mqh` | new — session anchor, session VWAP, volume profile (POC / VAH / VAL), prior-session naked POC, close-position CVD, `volumeFlowScore` |
| `Include/Emtt/Emtt_MTF.mqh` | new — higher-timeframe context (Phase 2 / 3 / 4 state re-run on the HTF's own closed bars), `mtfScore` |
| `Experts/Emtt.mq5` | wired into the existing closed-bar path, the one-second timer, and `FillPanel()`; `#property version` → `1.40`, one `#property description` line updated to `Phase 5: closed-bar volume flow (VWAP, profile, CVD) and higher-timeframe agreement.` |
| `tests/phase5_reference.py` + `tests/test_phase5_reference.py` | new — MT5-free mirror of 15.3–15.10, same pattern as Phases 2–4; scope in 15.15 |
| `tools/mql5_compile_smoke.py` | contract list gains the two new headers plus the Phase 5 markers of 15.15; the Phase 1 dashboard guard and every Phase 2 / 3 / 4 marker stay |
| `README.md` | one Phase 5 paragraph |

`Include/Emtt/Emtt_Dashboard.mqh` is **not touched** and stays byte-identical (its sha256 guard in
`tools/mql5_compile_smoke.py` keeps enforcing that): rule 12's wrapping and rule 13's growing height are already
in the renderer, so a three-line WHY needs no renderer change. `Emtt_DynamicParams.mqh`, `Emtt_Regime.mqh`,
`Emtt_Supertrend.mqh` and `Emtt_SMC.mqh` are **not touched** and stay byte-identical — Phase 5 consumes them,
it never edits an approved module. Sections 1–14 are **not rewritten**; only status stamps are appended there as
phases are implemented and verified. Inputs stay **Magic number + Auto Trading** — Phase 5 adds none. No new
file, no new GlobalVariable (the Phase 2 threshold-freeze key stays exactly as it is). The panel header string
stays `Emtt V1.0` — only the `#property` lines change.

**One deliberate exception to the "no new indicator handle" pattern of Phases 3 and 4:** the higher-timeframe
context cannot read the chart's handles (they belong to the chart timeframe), so the MTF context owns its own
**HTF handle set, an exact mirror of `EmttCreateIndicators()` on the higher timeframe** — `iATR` 10 / 14 / 21 /
28 / 50, `iAMA` 9 / 13 / 21 / 26 / 34 / 50 with the same fixed fast/slow `2, 30` constants, and `iBands` 20 /
2.0, all created on `(g_symbol, htf)`. The set is created lazily when the MTF context first initialises after a
reset and released by `EmttMtfFree()`, which `EmttReleaseIndicators()` calls and which `EmttResetMarketState()`
also calls. No handle is created on the **chart** timeframe beyond the existing twelve, and the MTF context is
the only code that touches its own set.

**.github/workflows/phase2.yml needs no edit** and no `phase5.yml` is created: it discovers `tests/` and runs
the smoke check, so the new tests are picked up on their own.

Exact wiring points in `Experts/Emtt.mq5` — Phase 5 adds no others:

- `#include "../Include/Emtt/Emtt_VolumeFlow.mqh"` is placed **after** the `Emtt_SMC.mqh` include — the header
  reuses the non-static session-window and DST helpers of `Emtt_Regime.mqh` (9.2.7 stays defined in exactly one
  place) and `EmttLookbackScale()` from `Emtt_Supertrend.mqh`;
- `#include "../Include/Emtt/Emtt_MTF.mqh"` is placed **last** — it references the Phase 2 / 3 / 4 state types
  and advance functions, all included before it;
- three new globals, each declared exactly once: `SEmttVolumeFlowState g_volumeFlow;`,
  `SEmttMtfState g_mtf;`, `SEmttMtfContext g_mtfContext;` — reset in `EmttResetMarketState()` alongside the
  existing resets;
- `EmttVolumeFlowAdvance(...)` is called for each bar **inside** the existing `EmttReplayClosedHistory()` loop
  and again in `EmttProcessLatestClosedBar()`, after `EmttSmcAdvance` and before `EmttSetSnapshot` — the same
  loop position pattern as Phases 3 and 4, seeing that bar's bucket and `atrPeriod`;
- `EmttMtfAdvance(g_mtf,g_mtfContext,g_symbol,g_assetClass,g_timeframe,g_evaluatedBarSequence,...)` is called in
  both places immediately after the VolumeFlow advance (it polls the last closed HTF bar and advances only when
  it changed — 15.8), **and** once per second from `EmttRefreshFoundation()` immediately before
  `UpdatePanel()`. The timer call is a bar-time comparison (`iTime`) — a poll, not a measurement; the full
  advance runs only when the HTF's last closed bar time changed and reads only closed HTF bars (rule 4 of 15.2);
- the EA-local `EmttResolveHistoryRequired()` gains one term in its existing `MathMax` —
  `EmttVfHistoryRequired(g_assetClass,bucket,timeframe)` (15.11). `EmttHistoryRequired()` and
  `EmttSmcHistoryRequired()` are not edited;
- `FillPanel()` gains two Row 9 clause appends, two Row 10 status overrides and the terminal line — the exact
  composition of 15.10, no other change to `FillPanel()`;
- `OnTick()` gains nothing (still `UpdatePanel()` only); `OnDeinit()` gains nothing beyond the
  `EmttReleaseIndicators()` chain already present.

**Read in this order before coding:** 4 (where files live, timeframe limit), 5 (the panel contract), 6
(rules 1–21 — units, points, distances, refresh, palette, rule 11 "no extra rows", rule 19 incompatible
charts), 9.2.3 (the four layers, the three parameter classes and the guard rails Phase 5 must obey), 9.2.7
(the session clock the volume flow anchors on), 9.2.8 (the `--` honesty rule and the loading gate), 11.6 and
13.9 (the component contract this phase copies), 11.11 and 13.14 (the design seam this phase closes), 13.11 and
13.12 (clause and journal discipline), then 15 in full. **Section 16 is the definition of done** — every bullet
in it must hold before the phase is called implemented.

**This section is self-contained.** It was written from `Emtt.md` alone: every number, rule, format and journal
line Phase 5 needs is defined here. No other document in this repository is a source for this phase, and nothing
outside `Emtt.md` may be consulted to fill a gap — if a detail is missing, it is missing on purpose and belongs
to a later phase (15.16).

**Delivery:** one change set containing exactly the rows of the table above — the two new headers, the EA
wiring, the two test files, the CI contract, `README.md`. No other file, no refactor of Phase 1, 2, 3 or 4
beyond the wiring points listed. The phase is delivered **whole** (the author's standing decision of 13.1
Delivery): 15.3 to 15.9 all land in this one change set — session anchor, VWAP, profile and naked POC, CVD,
`volumeFlowScore`, the HTF context, `mtfScore` and all panel wiring — with nothing left partial and nothing
deferred. What is genuinely **not** in this phase is listed in 15.16.

### 15.2 Rules for this phase

1. **Panel only — a standing decision, not a phase limit.** Emtt draws no chart object other than its panel
   objects: no line, rectangle, arrow or chart label, in this phase **or any later one**, unless the author
   writes such a rule. Every level this phase finds (VWAP, POC, VAH / VAL, the naked POC, the HTF readings) is
   consumed as a number or a word in the clauses, and verified through the journal of 15.12, which carries every
   anchor, flip and rebuild with its price and its bar time — the same discipline that replaced chart drawing in
   13.2 rule 1.
2. **No layout change** — rules 11–17 stand: no new row, fixed width, `Segoe UI`, sizes, palette, colours all as
   is. WHY keeps its default 2 lines and **may wrap to 3 or more** — the full Row 9 of 15.10 is the longest row
   the panel has carried, and rule 12 / rule 13 already allow the wrap and the height growth; the panel width
   never changes.
3. **Rows 2–7 stay label-only.** The LIVE TRADE block keeps its Phase 2–4 behaviour (detected by magic number,
   rows 11–14 label-only). Nothing about orders changes.
4. **Closed bars only**, index 0 never read; the per-tick path stays `UpdatePanel()` only — no measurement on
   ticks. The MTF poll in the one-second timer is a bar-time comparison, not a measurement, and its advance
   reads only closed HTF bars.
5. **Nothing invented** — a field carries a measured value or `--`, and a clause part that has not been measured
   is omitted, as rule 19 and 9.2.8 already require. A level Emtt has not measured from closed bars does not
   exist, and is never shown, guessed or extrapolated.
6. Both components belong to the **Measurement** class of 9.2.3: adjusted by class + timeframe + volatility,
   **never by the regime**, and they feed nothing back into the bucket, the regime, the Supertrend or the
   structure. The MTF readings are pure outputs — the HTF context writes into its own state only.
7. **Components are never reconciled** (11.8, 13.2 rule 7). Regime, Supertrend, structure, flow and the HTF
   reading may all disagree on screen at once, and each shows exactly what it measured. No wording, colour,
   ordering or suppression may be used to make them look consistent.
8. **No repainting, ever.** A session's VWAP and CVD are running sums over that session's closed bars, reset
   only at the journaled session re-anchor of 15.3 (a rule-driven reset, not a revision); the profile, the
   magnet, the CVD classification and every HTF reading are decided once per closed bar and never revised. If
   new bars change an earlier answer, the earlier answer stands and the new bars produce their own.

### 15.3 Session anchor — shared by VWAP and CVD

The sessions are the back-to-back windows of 9.2.7, each following its own market's clock and its own daylight
saving; this section adds no clock of its own.

- **Session start (UTC):** for a closed bar time `t`, the **anchor** is the latest session open among the
  sessions whose window contains `t`, where Asia opens at **07:00 Sydney local**, London at **07:00 London
  local** and New York at **07:00 New York local** — each candidate day's offsets computed with the DST rules
  already implemented in `Emtt_Regime.mqh` (`EmttSydneyDstOnDate`, `EmttLondonDstOnDate`,
  `EmttNewYorkDstOnDate` and the window tests, reused, never restated). Candidate days are `t`'s day and the
  previous day (an open can be up to half a day before `t`, mirroring the day scan of
  `EmttSessionNameUtc()`). Where two windows overlap (e.g. the London/NY overlap), the **later open wins**, so
  the anchor moves exactly with the label Row 8 shows (`London/NY` → anchored to the NY open).
- **The VWAP and CVD series are session-anchored:** they accumulate only over the closed bars of the current
  session. On the first closed bar whose anchor differs from the stored one, both running sums reset — a
  **re-anchor**, journaled once (15.12).
- **Weekend gap:** no special case. After the weekend the first bar's anchor is simply the open of its session;
  the series start there.
- **Purity:** the anchor is a pure function of the bar time and the 9.2.7 calendar. Same bars in → same anchors
  on any machine at any time (15.12). The anchor is the only time input in the whole phase, and it is a bar
  property, not "now".
- **Fetch depth (incremental path):** the advance copies its own closed-bar window for the session-anchored
  series — `W + EMTT_VF_SESSION_DEPTH + EMTT_VF_FETCH_BUFFER` closed bars via `CopyRates` from shift 1, with
  `EMTT_VF_SESSION_DEPTH = 160` and `EMTT_VF_FETCH_BUFFER = 10`. The 160-bar depth covers the longest session —
  the 13-hour Asia window, 156 bars on M5, the longest case — so the previous session's bars of 15.5 are always
  in reach on every allowed timeframe; the replay path already holds the full history and needs no separate
  fetch.

### 15.4 Session VWAP

- **Definition:** `VWAP = Σ(typicalPrice_i × volume_i) / Σ(volume_i)` over the closed bars of the current
  session, where `typicalPrice_i = (high_i + low_i + close_i) / 3` and `volume_i` is the **tick volume** of the
  closed bar (`MqlRates.tick_volume` — the only volume MT5 carries on a bar; `MqlRates` has no `volume` member,
  `real_volume` is not fetched, and no tick data is read).
- **Running sums:** each closed bar adds `typicalPrice_i × volume_i` and `volume_i` to the session sums; a
  re-anchor resets both. On the replay path the sums are rebuilt bar by bar from the same formula (15.12), so a
  restart reproduces the same VWAP.
- **Ready:** `Σ(volume) > 0` for the session. Before the first positive-volume closed bar there is **no VWAP**
  and the fair-price clause part is omitted (15.10). A zero-volume feed never gets an invented fair price.
- **`priceVsVwap`:** the newest closed bar's close strictly above the VWAP → `above`; strictly below →
  `below`; equal → neither (part omitted).
- **Standing:** the VWAP is a **reading, not a gate**. It is displayed nowhere except the clause words of
  15.10 and the journal, and it gates nothing.

### 15.5 Volume profile — POC / value area, and the prior-session naked POC

- **Profile window `W`** (closed bars): the dynamic **lookback** parameter of 15.11. The **current window** is
  the `W` newest closed bars. The naked POC below is **session-based**, not window-based — it uses the
  previous session's closed bars of 15.3, not a second window.
- **Binning:** `EMTT_VF_BINS = 40` bins span the current window's `[windowLow, windowHigh)`. Bin width =
  `(windowHigh − windowLow) / 40`. Each closed bar's **entire tick volume** is assigned to the **single bin
  containing its typical price** — bin index = `floor((typicalPrice − windowLow) / width)`, clamped to `39`, so
  the bar holding `windowHigh` lands in bin 39. No volume is split between bins.
- **POC** = the bin with the largest volume; an exact tie resolves to the **lower-priced** bin. The published
  POC price is the **midpoint of that bin**: `windowLow + (binIndex + 0.5) × width`.
- **Value area (70 %):** starting with the POC bin, `areaVol = vol[POC]`; while `areaVol < 0.70 × totalVolume`,
  look at the bin immediately **above the area's top** and the bin immediately **below its bottom** (whichever
  exist) and add the side with the **larger bin volume** (exact tie → the **lower** side), `areaVol +=` the added
  bin. `VAH` = `windowLow + (topBin + 1) × width` (top edge of the top bin); `VAL` = `windowLow + bottomBin ×
  width` (bottom edge of the bottom bin). `EMTT_VF_VALUE_AREA = 0.70` is fixed.
- **Not ready (honest blank):** `windowHigh == windowLow` (a flat window) or `totalVolume == 0` → **no profile
  reading at all**: the magnet part is omitted, the score's value and magnet terms are 0, and nothing is
  journaled about the window.
- **Prior-session POC (the naked POC):** the POC of the **previous session's** closed bars — the session whose
  anchor precedes the current anchor (15.3) — computed the same way (40 bins over that session's own
  `[low, high)` and its own total tick volume). It is **naked** while **no closed bar of the current session has
  traded through it** — i.e. for every current-session bar, not `low_i ≤ priorPoc ≤ high_i`. Once any
  current-session bar trades through it, it is not naked for the rest of the session. It is **available** only
  while the copied history holds at least **2 closed bars of the previous session with positive total volume**
  (a one-bar session stub never publishes a level); before that it is simply not part of the published set — a
  reading-level fact, never a gate. The level itself is **fixed for the whole current session**: computed once
  from the previous session's bars, it does not move as bars close — it either stands naked or loses its
  nakedness. It is a **reading**: the clause may show it, and it is never journaled as a change (15.12).
- **Magnet:** the published magnet set is `{ session POC, naked POC, VAH, VAL }`, each member present only
  while its reading exists. The **published magnet** is the member **nearest the newest close** by
  `|close − level|`. An exact distance tie prefers, in order: naked prior POC, session POC, VAH, VAL. The Row 9
  clause shows **one** level — this magnet — with its kind and its price in the symbol's own digits (13.11's
  single-level decision stands).

### 15.6 CVD — close-position estimate from closed-bar tick volume

- **Per-bar delta estimate:** for a closed bar `i`,
  `Δ_i = volume_i × ( 2 × (close_i − low_i) / (high_i − low_i) − 1 )`, and a bar with `high_i == low_i`
  contributes `Δ_i = 0`. A bar closing at its high contributes `+volume_i`, at its low `−volume_i`, at its
  midpoint `0`. This is the closed-bar estimate of aggressive-side volume: where the close sits inside the bar's
  range says which side did the work. It is deterministic from `MqlRates` alone — no tick data. True tick-level
  CVD (classifying individual ticks) is explicitly **out of scope**: it belongs to the trade-management phase
  that is not built, and the only CVD this phase owns is this estimate.
- **CVD** = `Σ Δ_i` over the closed bars of the current session — session-anchored and re-anchored exactly like
  the VWAP (15.3), as a running sum.
- **Classification window:** the last `EMTT_VF_CVD_WINDOW = 10` closed bars of the session, or **all** closed
  bars of the session when it is younger. Fewer than **2** closed bars in the session → **no CVD reading**
  (clause part omitted). Within the window: `Vw = Σ volume_i`, `D = Σ Δ_i` (equivalently `cvd_now −
  cvd_beforeWindow`).
- **Classification:** `D ≥ +0.25 × Vw` → **up**; `D ≤ −0.25 × Vw` → **down**; otherwise → **flat**.
  `Vw == 0` → no reading. The band `EMTT_VF_CVD_FLIP = 0.25` is fixed and identical for every class (adjusted
  by no layer); it keeps a session that trades but drifts from flickering between `up` and `down`.
- **`flowDirection`** = `+1` / `−1` / `0` per the classification. CVD, its value and its classification are
  readings: shown only in the clause; a flip is journaled once (15.12) and drives the 3-bar status of 15.10.

### 15.7 What Phase 5 (volume flow) publishes — the component contract

The same shape 11.6 and 13.9 defined and every later component copies. `Emtt_VolumeFlow.mqh` owns one
`SEmttVolumeFlowState`; the EA keeps a single instance; nothing in it is displayed beyond what 15.10 allows.

- **Readings:** `flowDirection` (+1 / −1 / 0), `vwap` + `priceVsVwap` (above / below / none), `poc`, `vah`,
  `val`, `priorPoc` + `naked`, `magnetKind` + `magnetPrice`, `sessionAnchor` (UTC) + `sessionName`.
- **Facts, not only labels:** `cvd`, `windowVolume` (Vw), `netDelta` (D), `barsSinceSessionStart`,
  `distanceVwapATRs` (`|close − vwap| / ATR`), `distanceMagnetATRs` (distance from the close to the published
  magnet, in the flow direction, clamped to 0 when price has already reached or passed it), and the
  `atrPeriod` / `atrValue` / `profileWindow` the reading was made on.
- **`volumeFlowScore`, a single 0.0–1.0 number**, computed from those closed-bar facts only. Four terms, weights
  summing to exactly 1.0, `clamp01(x) = max(0, min(1, x))`:

  | Term | Weight | Value |
  |---|---|---|
  | **Control** | 0.35 | `clamp01(D / (0.5 × Vw))` with `D` taken in the flow direction (it is positive there by construction) — net one-sidedness of half the window volume or more scores full |
  | **Fair price** | 0.25 | the close on the flowDirection's side of the VWAP (above for +1, below for −1) → `1.0`; on the opposite side → `0.0`; no VWAP → `0.0` |
  | **Value area** | 0.20 | flowDirection +1: close `< VAL` → `1.0`, inside the value area → `0.5`, close `> VAH` → `0.0`. FlowDirection −1 mirrors it (above VAH → `1.0`). No profile → `0.0` |
  | **Magnet proximity** | 0.20 | the nearest magnet **in the flowDirection's direction** (level at or beyond the close): `clamp01(1 − distanceMagnetATRs / 3.0)`; no magnet in that direction → `0.0` |

  `score = 0` whenever `flowDirection` is 0 (flat or no reading).

- **Why the score exists now:** Row 3 (rule 6) is one combined figure, and the phase that fills it sums one such
  score per component (11.6). Deriving it here costs nothing, changes nothing the user sees, and stops the
  confidence phase from having to rewrite and re-verify a finished module.
- **What the score is not:** it gates nothing in this phase, places nothing, and is never shown. It may never
  adjust a parameter, a bucket, a regime or any other component's value — readings are outputs, not inputs, to
  the engine of 9.2.3.
- **Ready:** `ready = true` when the current profile window holds `W` closed bars with `totalVolume > 0` and a
  valid `atrValue`. Before that, `ready = false`, the score is 0, and 15.10 publishes nothing at all — no
  partial clause. (The session-based parts — VWAP, CVD — omit themselves independently while the session is
  young, even once `ready` is true.)
- Later phases publish the same contract, so the confidence phase only ever sums weights. This section defines
  no weights for any other component and no combining rule.

### 15.8 Multi-Timeframe Agreement — the higher-timeframe context

This section closes the design seam of 11.11 and 13.14: the Phase 2 / 3 / 4 headers take their state as
arguments and read no chart, no panel and no EA global, so the **MTF phase owns the change that wraps that
state into one context per symbol + timeframe** — here, for the one higher timeframe.

- **Mapping (fixed, one code path):** M5 → **M15**, M15 → **H1**, M30 → **H4** — `EmttMtfTimeframe(chartTf)`.
  Any other chart timeframe returns "no HTF" and the MTF component never publishes (rule 19 already blocks
  those charts). The mapping is a single table in this one function — nothing elsewhere knows the pairs.
- **The HTF context re-runs the Phase 2 / 3 / 4 stack on the HTF's own closed bars:**
  - one `SEmttDynamicState`, one `SEmttRegimeState`, one `SEmttSupertrendState` and one `SEmttSmcState` for the
    HTF — second instances of the approved headers, which are **not modified** (they take state as arguments);
  - driven by the HTF `MqlRates` from `CopyRates(g_symbol, htf, 1, fetchCount)` and by the HTF indicator
    buffers of 15.1 (ATR 10 / 14 / 21 / 28 / 50, KAMA 9 / 13 / 21 / 26 / 34 / 50, band upper / lower), selected
    by the HTF's own resolved parameters — the HTF bucket comes from the percentile of the **HTF** ATR(14)
    array, the HTF Supertrend window from `EmttSupertrendWindow(htf)`, and the HTF structure window / swing
    strength / body period from the same `EmttSmcResolveParameters()` path with `htf` — on H1 and H4,
    `EmttLookbackScale()` returns the base ×1.0, so the existing function is used as-is and nothing is
    redefined per timeframe;
  - the per-HTF-bar measurements are built by an **HTF-context-local twin of the EA's
    `EmttBuildMeasurements()`** — the identical formulas (in-house ER from the rates, KAMA / ATR / band values
    from the HTF buffers, ATR(14) vs ATR(50) ratio) with the arrays passed **as arguments**; the twin never
    reads the EA's chart-timeframe globals (`g_atr14`, `g_kama*`, `g_band*`), which belong to the chart stack;
  - the HTF walk mirrors the EA's replay loop of `EmttReplayClosedHistory()` bar for bar — percentile →
    dynamic seed / update → measurements → `EmttRegimeAdvance` (with its own after-gap test on HTF bar times) →
    threshold update → `EmttSupertrendAdvance` → `EmttSmcAdvance` — and walks the HTF bars **oldest to
    newest**, starting at the index where the HTF's own requirements are satisfied
    (`htfBarsFetched − (EmttMtfHistoryRequired(htf) − 1)`).
- **HTF history requirement:** `EmttMtfHistoryRequired(htf) = max(EmttHistoryRequired(htf),
  EmttSmcHistoryRequired(htf))` — the existing timeframe-based functions, one code path (with today's matrices
  this resolves to 300 for M15 and 250 for H1 and H4; the figure is computed, never hardcoded).
  `fetchCount = EmttMtfHistoryRequired(htf) + EMTT_MTF_FETCH_BUFFER`, `EMTT_MTF_FETCH_BUFFER = 10`.
- **Cadence:** the HTF context advances **only when the last closed HTF bar changes** — `iTime(g_symbol, htf,
  1)` compared with the stored HTF bar time:
  - **full rebuild** (fresh HTF copy, silent walk of all fetched HTF bars, then the one summary journal line of
    15.12) on init, on a symbol / chart-timeframe change, on market reopen, after a history shortfall reset,
    and whenever the HTF context's asset class or volatility bucket changes (a change is journaled with its
    reason — the `Emtt | HTF (<htf>) context rebuilt | …` line of 15.12 — and the walk itself stays silent);
  - otherwise a **one-HTF-bar advance** per new HTF closed bar, on the same code path, with the MTF header
    journaling the HTF facts that changed (15.12);
  - polled (a) on the chart closed-bar path after the VolumeFlow advance and (b) once per second from
    `EmttRefreshFoundation()` before `UpdatePanel()`. Between HTF closes the MTF state is constant — the
    display is at most one HTF bar old, which is the honest reading: the last **closed** higher bar is the
    latest information.
- **Readiness:** `ready = true` when `htfBarsFetched ≥ EmttMtfHistoryRequired(htf)` **and** every HTF buffer
  has `BarsCalculated ≥ fetchCount` (the same waiting pattern as `EmttIndicatorsCalculated()`, applied to the
  HTF set). Not ready → `mtfScore = 0`, the clause is omitted, and nothing is journaled — no partial HTF
  reading is ever shown.
- **Determinism:** no RNG, no clock (the HTF walk is a pure function of the HTF bars and buffers), no tick
  data, no file access. The same HTF bars in → the same HTF regime, the same HTF clusters / multiplier /
  direction, the same HTF structure and the same `mtfScore`, on any machine, at any time, when replayed.

### 15.9 What Phase 5 (MTF) publishes — the component contract

Same shape again. `Emtt_MTF.mqh` owns one `SEmttMtfState` (the readings and score) and one `SEmttMtfContext`
(the HTF machinery: the HTF state structs, the HTF bars and buffers, the HTF handle set, the stored HTF bar
time, the chart sequence of the last evaluation). The EA keeps one of each; nothing is displayed beyond
15.10.

- **Readings:** `htf` (its name — `M15` / `H1` / `H4`), `htfRegime`, `htfSupertrendDirection` + `htfCluster` +
  `htfMultiplier`, `htfBias` + `htfZone`, `agrees` (1 = the HTF Supertrend direction equals the chart
  Supertrend direction at the last evaluation; −1 = opposite; 0 = nothing comparable — the chart Supertrend is
  flat or not ready), `htfBarTime`.
- **Facts:** `htfAtrPeriod` / `htfAtrValue`, `htfBarsFetched`, `chartSupertrendDirection` and
  `chartSmcBias` at the last evaluation, `lastFlipChartSequence` (for the 3-bar status freshness of 15.10),
  and the HTF measurements behind the HTF regime label.
- **`mtfScore`, a single 0.0–1.0 number**, computed from those closed-bar facts only. Three terms, weights
  summing to exactly 1.0:

  | Term | Weight | Value |
  |---|---|---|
  | **Direction** | 0.50 | HTF Supertrend direction equals the chart Supertrend direction and both are non-zero → `1.0`; opposite → `0.0`; either flat / not ready → `0.0` |
  | **Regime** | 0.30 | HTF regime TRENDING → `1.0`; TRANSITION → `0.5`; RANGING → `0.0`; VOLATILE → `0.0`; MARKET CLOSED / unknown → `0.0` |
  | **Structure** | 0.20 | HTF bias equals the chart SMC bias and both are non-zero → `1.0`; opposite → `0.0`; either one is 0 → `0.5` (nothing to compare is neutral, a broken structure is not) |

  `score = 0` whenever the HTF context is not ready (15.8).
- **Standing:** identical to 11.6 / 13.9 — the score is never displayed, gates nothing, adjusts nothing, and
  the confidence phase only ever sums weights. The agreement word in the clause is recomposed live in
  `EmttWhyWithMtf()` from the stored HTF direction and the **current** chart Supertrend direction passed in as
  an argument, so the word is never older than the chart's newest closed bar; the **score** keeps the closed
  facts of the last evaluation.

### 15.10 Panel wiring

The author's standing decision of 13.11 stands: the panel carries both **what Emtt decided** and **the latest
thing it is doing**, in words short enough to read at a glance; Row 9 carries the decision, Row 10 the latest
fact; wording stays compact; the WHY block may grow; the panel width never changes; **one level is ever shown**.

- **Row 9 (WHY):** the Phase 2 regime sentence, then ` | `, then the Phase 3 Supertrend clause, then ` | `, then
  the Phase 4 structure clause, then ` | `, then the **volume-flow clause**, then ` | `, then the **MTF clause**
  — fixed order. Each clause is appended as ` | <clause>` **only when it is non-empty**; an empty clause appends
  nothing, and an empty clause never adds a trailing ` | `.

  **Volume-flow clause** — compact, **at most three comma-separated parts**, always in this fixed order, each
  part omitted when it has not been measured:

  | Part | Values | Omitted when |
  |---|---|---|
  | flow | `CVD up` / `CVD down` / `CVD flat` | fewer than 2 closed bars in the session, or zero window volume (15.6) |
  | fair | `above VWAP` / `below VWAP` | no session VWAP (15.4) |
  | magnet | `POC <price>` / `naked POC <price>` / `VAH <price>` / `VAL <price>` | no profile reading (15.5) |

  Only **one** level is shown — the published magnet of 15.5 — `<price>` in the symbol's own digits, the same
  digits the Price Row uses. Examples: `CVD up, above VWAP, POC 1.09020` · `CVD down, below VWAP, naked POC
  1.08740` · `CVD flat, below VWAP` (the session is young enough that the profile window is not ready yet, so
  no level part).

  **MTF clause** — compact, **at most three parts**, always in this fixed order:

  | Part | Values | Omitted when |
  |---|---|---|
  | htf regime | `<HTF> trending up` / `<HTF> trending down` / `<HTF> ranging` / `<HTF> volatile` / `<HTF> transition` / `<HTF> closed` | HTF not ready (15.8) |
  | agreement | `agrees` / `disagrees` | HTF not ready, or the chart Supertrend direction is flat (nothing comparable) |
  | htf zone | `<HTF> Discount` / `<HTF> Premium` / `<HTF> Equilibrium` | HTF not ready, or no HTF dealing range |

  Examples: `H1 trending up, agrees` · `H1 ranging, disagrees, H1 Premium` · `M15 transition`.

  **Whole Row 9, everything ready:** `Efficiency 71/100 and KAMAs aligned up; volatility normal | Wild
  (Supertrend bullish) | Discount, BOS up, OB 1.08450 | CVD up, above VWAP, POC 1.09020 | H1 trending up,
  agrees`. It wraps inside the existing fixed width — the WHY block may take its third line (rule 12); the
  width never changes (rule 13). When a component is not ready, or the market is closed, or the chart is
  incompatible, its clause is simply absent and Row 9 shows exactly what it showed in Phase 4.

- **Row 10 (STATUS):** precedence stays rule 19 > loading history > `MARKET CLOSED`, then **first non-empty
  wins**, each inside its own freshness:
  1. `EmttStatusForMtf()` — `Watching — <HTF> turned <up/down>`: an HTF Supertrend direction flip fresh within
     the last **3 closed chart bars** (`EMTT_MTF_STATUS_FRESH_BARS = 3`; the state stores the chart sequence of
     the flip and its own `currentSequence`, the same stored-sequence mechanism as `EmttStatusForSmc()` of
     13.11). The big picture turning outranks every chart-timeframe fact. No fresh flip → empty.
  2. `EmttStatusForSmc()` — Phase 4, unchanged (CHoCH > BOS > sweep inside its own 3-bar window).
  3. `EmttStatusForVolumeFlow()` — `Watching — CVD turned <up/down>`: a flow classification flip (flat → up,
     up → flat, up → down, and every mirror) fresh within the last 3 closed chart bars. No fresh flip → empty.
  4. `EmttStatusForSupertrend()` — Phase 3, unchanged.
  5. The Phase 2 regime / pending lines — unchanged.
  - **Terminal line:** when `EmttStatusForMtf`, `EmttStatusForSmc` and `EmttStatusForVolumeFlow` are all empty
    **and** the chart measurement set is fully ready — Supertrend ready with a direction, SMC ready, volume
    flow ready **and** the HTF ready — the EA sets `Watching — context only, no signal yet`, replacing the
    Phase 3 terminal wording now that all four components are live. If the volume flow or the HTF is not ready,
    the Phase 3 line stays — the panel never claims a completeness that has not been measured.
  - Section 7's `No trade — …` messages still belong to the phase that can place orders.
- **Rows 1–8 and 11–14 unchanged.** `Expected Duration:` stays empty. The scores, the CVD value, the VWAP
  price, the POC / VAH / VAL figures, the magnet distance, the HTF cluster / multiplier / ATR, the agreement
  flag and every other fact of 15.7 / 15.9 appear **nowhere** on the panel beyond the clause words 15.10
  allows: rule 11 gives them no row.
- **Incompatible timeframe** (rule 19): unchanged — `--` fields, the red message, the Price Row still live.
  Rule 19 wins over every volume-flow and MTF state.
- **Market closed:** unchanged — `Regime: MARKET CLOSED`, no clauses appended (Row 9 reads `--` exactly as in
  Phase 4), and the VWAP / CVD series are simply not updated while no bars exist.
- **Nothing invented:** every word in either clause comes from a closed-bar measurement of this phase; the
  panel never shows a level, a side or an agreement Emtt has not measured.

### 15.11 Rows Phase 5 adds to the parameter table of 9.2.3

The standing decision of 13.10 continues: these numbers are **dynamic**. Emtt starts from standard values and
then respects the **symbol type** (asset class), the **market condition** (the live volatility bucket) and the
**chart timeframe** — through the same four layers, the same tables and the same code path as everything else
in 9.2.3. Nothing is hardcoded per timeframe and no number is fixed by hand for one symbol.

**Layer 1 base matrix (Low / Normal / High volatility) — volume profile window (closed bars, lookback):**

| Parameter | Forex Major | Forex Cross | Metals | Crypto | Indices | Generic |
|---|---|---|---|---|---|---|
| Volume profile window | 200 / 200 / 300 | 200 / 200 / 300 | 150 / 200 / 300 | 100 / 150 / 200 | 150 / 200 / 250 | 200 / 200 / 300 |

Why these numbers (the same logic 13.10 gave the structure window): a wilder market needs a **longer** window
before a volume footprint means anything; crypto and indices turn over faster, so their footprints go stale
sooner and their window is shorter. The smoothing-style figures below (bins, value area, CVD window and band,
magnet scale, weights, MTF mapping and weights) are class-independent and fixed, exactly as the displacement
multiple and the impulse window are.

**Layer 2 (timeframe) applies to the profile window only**, because it is the only **lookback** here:
`×1.0 / ×1.25 / ×1.5` for M5 / M15 / M30, through the existing `EmttLookbackScale()`, rounded to a whole bar
**half away from zero** — `MathRound`, never a truncation, never banker's rounding (13.10). Phase 5 hits
fractional bars where Phase 3 did not: Metals / Indices Low on M15 is `150 × 1.25 = 187.5 → 188`, and Forex
High on M30 is `300 × 1.5 = 450` before clamping.

**Layer 3 (volatility)** reads the Low / Normal / High column for the current bucket, exactly as 9.2.3 says.
**Layer 4 (context / regime)** never touches it: the profile window is **Measurement** class.

Resolved volume profile window, Low / Normal / High volatility, as **M5 / M15 / M30**:

| Class | Low | Normal | High |
|---|---|---|---|
| Forex Major, Forex Cross, Generic | 200 / 250 / 300 | 200 / 250 / 300 | 300 / 375 / 400 (450 clamped) |
| Metals, Indices | 150 / 188 / 225 | 200 / 250 / 300 | 300 / 375 / 400 (450 clamped) |
| Crypto | 100 / 125 / 150 | 150 / 188 / 225 | 200 / 250 / 300 |

**Guard rails of 9.2.3 apply to the profile window:** clamped to `EMTT_VF_WINDOW_MIN = 50` …
`EMTT_VF_WINDOW_MAX = 400` closed bars after Layer 2 scaling; **one change, then the same parameter stays put
for the next 2 closed bars** — reusing the existing `EmttCanChangeAt()`; every change journaled with its
reason. The pause governs the **window only** — the VWAP, the profile, the CVD classification and the score
are readings and are never delayed or damped by it. **A window change recomputes, it does not guess:** the profile and the score are recomputed from the new
window's bars — silently, writing no event journals, exactly like the SMC rebuild of 13.10 — so the readings
after the change are the same as they would have been had the new window been in use all along (the naked POC
is session-based and is untouched by a window change). Only the window change itself is journaled.

**Fixed, adjusted by no layer** (the same standing as Bollinger (20, 2.0) and the 200-bar volatility window in
9.2.3): bin count `40` · value area `70%` · CVD comparison window `10` closed bars · CVD flip band
`±0.25 × window volume` · control scale `0.5 × window volume` · magnet proximity scale `3.0` ATR · the four
volume-flow weights `0.35 / 0.25 / 0.20 / 0.20` · the volume-flow fetch depth `160` and buffer `10` · the
prior-session POC minimum of `2` positive-volume bars · the three MTF weights `0.50 / 0.30 / 0.20` · the MTF
fetch buffer `10` · the MTF status freshness window `3` closed chart bars · the HTF mapping (M5 → M15, M15 →
H1, M30 → H4).

**Required history — one gate for all measurements (supersedes 13.10's figure only where it is larger).** The
gate becomes `max(EmttHistoryRequired(tf), EmttSmcHistoryRequired(class,bucket,tf),
EmttVfHistoryRequired(class,bucket,tf))`, in the existing EA-local `EmttResolveHistoryRequired()` — one code
path, no hardcoded figure. `EmttVfHistoryRequired = profileWindow + 2` closed bars, resolved the same way. The previous
session's depth is **not** part of the gate either: while the copied history holds no previous-session bars
meeting the availability rule of 15.5, the naked POC simply is not part of the published magnet set — a
reading-level fact, honestly blank. On the largest
combination Phase 5 can produce (Forex Major / Cross / Generic, High volatility, after clamping: `400 + 2`) the
new gate resolves to **302 / 377 / 402 closed bars for M5 / M15 / M30** — larger than the Phase 3 figure of
250 / 300 / 350, so **the loading line's M changes to the resolved max in exactly those cases**, and it stays
250 / 300 / 350 everywhere the Supertrend requirement is the larger one (e.g. Normal volatility:
`200 / 250 / 300 + 2` below 250 / 300 / 350). The gate re-resolves when a closed-bar bucket first exists,
exactly as it does today. While the gate is open, Rows 1, 9 and 10 behave exactly as they do today — no
partial, half-measured display.

**HTF history is not part of the chart gate.** The HTF context reads its own history through
`CopyRates` and is ready when it holds `EmttMtfHistoryRequired(htf)` closed HTF bars with calculated buffers
(15.8). Until then the MTF clause is omitted — nothing is invented to fill it.

### 15.12 Determinism, replay, state, journal

- **No RNG, no clock (the session anchor of 15.3 excepted — a pure function of bar times and the 9.2.7
  calendar), no tick data, no file access** in any Phase 5 calculation. Same closed bars in → same anchors,
  same VWAP, same POC / VAH / VAL, same prior POC and nakedness, same CVD, same classification, same
  `volumeFlowScore`. Same HTF bars in → same HTF regime, clusters, multiplier, direction, line, structure and
  `mtfScore` — on any machine, at any time, when replayed.
- **Chart-timeframe state (volume flow):** reconstructed by replaying the chart's closed bars on init, on a
  timeframe or symbol change, on market reopen and after any history shortfall reset — using the same replay
  path Phases 2–4 already use, with the advance call in its 15.1 loop position. The anchor during the replay is
  **each bar's own anchor** (15.3), so a restart reproduces the same re-anchors and the same running sums.
- **HTF state:** reconstructed by replaying the HTF's closed bars (15.8) on the same triggers — full rebuild,
  silent walk, one summary line. State never carries over from a previous session: no new file, no new
  GlobalVariable (the Phase 2 threshold-freeze key stays exactly as it is).
- **Bounded cost.** Per closed chart bar the volume-flow work is bounded by `W` bar visits (≤ 400: the current
  window binned) plus the 40-bin value-area walk, the 10-bar CVD sum and an O(1) nakedness check against the
  stored prior-session POC — **never** a rescan of the whole copied history per bar. The prior-session POC
  itself is computed once per session (when the previous session's bars are complete within the fetched depth),
  not per bar. The full init replay is therefore bounded by roughly
  `3 × 10⁵` elementary operations once, on the timer — the HTF rebuild adds at most `260 × (its per-bar
  constant)` once. Nothing may run per tick, where only `UpdatePanel()` belongs; the timer poll is an `iTime`
  comparison, and its advance happens at most once per HTF bar.
- **Journal** through the existing `PrintFormat` channel, on the closed bar, with its reason, same shape as
  Phases 2–4 (`Emtt | <what> | <detail> | bar <time>`):
  - `Emtt | VWAP re-anchored | session Asia -> London | bar 2026.10.08 14:30`
  - `Emtt | Flow CVD flat -> up | net +0.31 x window volume | bar 2026.10.08 14:30`
  - `Emtt | Profile window 200 -> 250 closed bars | volatility NORMAL -> HIGH | bar 2026.10.08 14:30`
  - `Emtt | MTF context replayed | H1 | 260 closed bars | regime TRENDING (Bullish) | supertrend up (Wild, 3.0) | bias up | zone Discount | score 0.66 | bar 2026.10.08 14:30` — one summary line after every full HTF rebuild, including init
  - `Emtt | HTF (H1) context rebuilt | volatility NORMAL -> HIGH | bar 2026.10.08 14:30` — an HTF class / bucket change that forces a silent rebuild
  - `Emtt | HTF (H1) supertrend turned down | cluster Wild, multiplier 3.0 | bar 2026.10.08 15:00` — on the new HTF closed bar that flipped the HTF direction (bar time = that HTF bar's time)
  - `Emtt | HTF (H1) regime TRENDING (Bullish) -> RANGING | bar 2026.10.08 15:00`
  - `Emtt | HTF (H1) structure CHoCH down | bias up -> down | bar 2026.10.08 15:00` — HTF BOS / CHoCH events only; the HTF log carries direction-relevant facts, not HTF sweeps
  - `Emtt | Volume flow replayed | window 250 closed bars (M15 x1.25) | session London | VWAP 1.08612 | CVD up | POC 1.09020 | naked POC -- | score 0.58 | bar 2026.10.08 14:30` — one summary line after the init / reset replay of the chart bars, mirroring the Supertrend and Structure summaries; prices in the symbol's digits, `--` where a reading is not ready
- **Never journaled:** the per-bar readings themselves (VWAP, POC, VAH / VAL, CVD value and classification,
  the magnet selection, the naked POC state, the scores — they are re-readable from the clause and from the
  chart, as 13.12 requires), an HTF re-fetch that produced no change, and any bar where nothing changed. The
  panel gets no parameter row (rule 11); the journal is the only record, and it must let the author
  reconstruct exactly what Emtt saw, and at which price, at any moment — this is what replaces chart drawing
  (13.2 rule 1, standing).

### 15.13 Freeze semantics — unchanged

The frozen set stays exactly as 9.2.3 wrote it (SL / TP multiples, breakeven, trailing, duration, confidence
threshold). Phase 5 adds **nothing** to it and freezes **nothing** new: while an Emtt position is open, the
VWAP, the profile, the CVD, the scores and every HTF reading keep measuring and keep journaling live, and the
panel never freezes (9.2.3, 11.10, 13.13).

### 15.14 Design seam for the later confidence phase

- `Emtt_VolumeFlow.mqh` and `Emtt_MTF.mqh` expose a state struct plus functions that take the symbol,
  timeframe and closed-bar data as arguments; neither header reads the chart, the panel or an EA global — the
  same discipline 11.11 and 13.14 imposed.
- The confidence phase consumes the four published scores — `supertrendScore`, `smcScore`,
  `volumeFlowScore`, `mtfScore` — and the regime threshold of 9.2.4 as-is, and **it defines the weights and
  the combining rule**. No component phase is re-opened for it.
- The HTF mapping is the one MTF owns: a later phase that wants a different relationship (or a second higher
  timeframe) extends the `EmttMtfTimeframe()` table and adds a second context — it never re-derives the HTF
  stack of 15.8.
- Carried forward, **not built now:** the confidence engine, Entry / SL / TP, Risk:Reward, Expected Duration,
  order placement and trade management, self-learning and parameter-optimization persistence — each owns its
  own later phase.

### 15.15 Tests

`tests/phase5_reference.py` mirrors 15.3–15.10 in the same style as Phases 2–4, and
`tests/test_phase5_reference.py` asserts, without MT5:

- **Session anchor:** each session's open on fixed summer and winter dates (Sydney, London and New York DST
  rules reused from the Phase 2 mirror); the later-open-wins rule in an overlap; the re-anchor on the first bar
  of a new session; a weekend gap producing no special state; and the anchor's purity — the same bar time
  always resolves to the same anchor on any run.
- **VWAP:** the weighted typical-price formula on a fixed series (zero-volume bars ignored in both sums); the
  running sum equals a from-scratch recompute at every bar; the session reset; not-ready before the first
  positive-volume bar; `priceVsVwap` above / below / equal.
- **Profile:** 40-bin assignment by typical price, including the bar holding `windowHigh` landing in bin 39;
  POC tie → lower bin; the value-area 70% expansion — larger side wins, tie → lower side, one side exhausted;
  VAH / VAL edge prices; a degenerate window (`windowHigh == windowLow`) and a zero-volume window producing
  **no** reading; the prior-session POC — computed once per session from the previous session's own bars, the
  `≥2` positive-volume previous-session-bar availability rule, and the 15.3 fetch-depth rule; the naked rule
  (a touch by any current-session bar removes nakedness for the rest of the session, and the level itself never
  moves within the session); magnet nearest-selection by price distance and the tie preference order (naked
  POC, session POC, VAH, VAL).
- **CVD:** the close-position delta formula (close at high → `+V`, at low → `−V`, at midpoint → 0,
  `high == low` → 0); the session-anchored sum and its reset; classification at exactly the `±0.25 × Vw`
  thresholds (inclusive) and inside the band → flat; fewer than 2 session bars → no reading; `Vw == 0` → no
  reading; flip detection (flat → up, up → flat, up → down and mirrors).
- **`volumeFlowScore`:** the four weights sum to exactly `1.0`; every term inside `0.0 … 1.0`; `flat → 0`; the
  control scale `0.5 × Vw` (full at `|D| = 0.5 × Vw`); the fair-price term direction-sensitive (above VWAP
  scores for +1 and zero for −1, and the mirror); the value-area term's three levels and its mirror; the
  magnet scale `3.0` ATR, no magnet in the flow direction → 0, a magnet already reached clamping the distance
  to 0.
- **Parameters:** the class / bucket matrix of 15.11 for all six classes and three buckets; Layer 2 scaling of
  the profile window only, with **half-away-from-zero** rounding — `187.5 → 188` asserted explicitly, and
  `450 → 400` clamped — and Python's built-in `round()` never used for it; clamping to `50 … 400`; the
  2-closed-bar pause via the existing `can_change_at`; a window change silently recomputing profile / prior
  POC / score to match a from-scratch replay at the new window.
- **History gate:** the three-term `max()` for every class, bucket and timeframe — resolving to **302 / 377 /
  402** in the worst case and staying **250 / 300 / 350** wherever the Supertrend requirement is the larger
  one (e.g. Normal volatility); `EmttVfHistoryRequired = window + 2`; the naked POC's previous-session
  availability — `≥2` positive-volume previous-session bars in the copied history, reading-level, not a gate.
- **MTF:** the mapping M5 → M15 / M15 → H1 / M30 → H4 and the "no HTF" answer for other timeframes;
  `EmttMtfHistoryRequired` as the `max()` of the two existing timeframe functions (300 for M15, 250 for H1 and
  H4 on today's matrices, via the code path — never a constant); the HTF walk reproducing the Phase 2 / 3 / 4
  state from the same HTF bars (replayed twice → identical regime, direction, bias and score); the direction /
  regime / structure terms (neutral `0.5` for a zero bias, `0.0` for a flat chart direction, `0.0` for a not
  ready context); `mtfScore` bounds and `ready` gating (not ready → clause omitted, score 0, no journal line);
  the live agreement word (stored HTF direction vs a passed-in chart direction, flat chart → part omitted).
- **Panel text:** every volume-flow clause format and omission rule, the three-part cap, the single-level
  priority and the digit formatting; every MTF clause format (`<HTF> trending up / down / ranging / volatile /
  transition / closed`, `agrees` / `disagrees`, `<HTF> Discount / Premium / Equilibrium`) and omission rule;
  every Row 10 status string and its precedence (MTF flip > SMC CHoCH > SMC BOS > SMC sweep > CVD flip > Phase
  3 > Phase 2) inside the 3-closed-bar freshness windows, and the terminal line appearing exactly when all four
  components are ready; rule 19 and the loading gate beating all of them.
- **Determinism:** the same series replayed twice gives an identical volume-flow state; a restart, a
  timeframe round-trip and a mid-window parameter change reproduce the same VWAP, POC, CVD classification and
  score; the HTF context rebuilt twice over the same HTF bars gives the same regime, direction, bias, zone and
  score.

`tools/mql5_compile_smoke.py` gains the two new headers in its required-source set and asserts at least these
Phase 5 markers, alongside every existing Phase 2, 3 and 4 marker and the unchanged Phase 1 dashboard digest:
`EMTT_VF_BINS 40`, `EMTT_VF_VALUE_AREA 0.70`, `EMTT_VF_CVD_WINDOW 10`, `EMTT_VF_CVD_FLIP 0.25`,
`EMTT_VF_CONTROL_SCALE 0.5`, `EMTT_VF_MAGNET_ATRS 3.0`, `EMTT_VF_WEIGHT_CONTROL 0.35`,
`EMTT_VF_WEIGHT_FAIR 0.25`, `EMTT_VF_WEIGHT_VALUE 0.20`, `EMTT_VF_WEIGHT_MAGNET 0.20`,
`EMTT_VF_WINDOW_MIN 50`, `EMTT_VF_WINDOW_MAX 400`, `EMTT_VF_SESSION_DEPTH 160`,
`EMTT_VF_STATUS_FRESH_BARS 3`, and in the MTF header
`EMTT_MTF_WEIGHT_DIRECTION 0.50`, `EMTT_MTF_WEIGHT_REGIME 0.30`, `EMTT_MTF_WEIGHT_STRUCTURE 0.20`,
`EMTT_MTF_FETCH_BUFFER 10`, `EMTT_MTF_STATUS_FRESH_BARS 3`, plus in the EA `#include
"../Include/Emtt/Emtt_VolumeFlow.mqh"`, `#include "../Include/Emtt/Emtt_MTF.mqh"`,
`SEmttVolumeFlowState g_volumeFlow;`, `SEmttMtfState g_mtf;`, `SEmttMtfContext g_mtfContext;`,
`EmttVolumeFlowAdvance(`, `EmttMtfAdvance(`, `EmttWhyWithVolumeFlow(`, `EmttWhyWithMtf(`,
`EmttVfHistoryRequired(`, an include-order guard (VolumeFlow after SMC, MTF after VolumeFlow), and the
no-chart-drawing guard of 15.2 rule 1 **extended to both new headers** — the Phase 4 forbidden-token list
(`ObjectCreate` of any type, `OBJ_TREND`, `OBJ_RECTANGLE`, `OBJ_HLINE`, `OBJ_ARROW`, `OBJ_TEXT`, `OBJ_FIBO*`)
applied to each — 15.2 rule 1 enforced by the build, not by memory.

### 15.16 Not in this phase

No confidence engine, no weights for any component, no Row 2 / Row 3 values, no Entry / SL / TP, no
Risk:Reward, no Expected Duration, no order placement or trade management, no tick-level CVD or divergence
detection (the closed-bar estimate of 15.6 is the only CVD this phase owns), no news or session blocking, no
alerts, **no chart drawing of any kind**, no self-learning or parameter-optimization persistence, no new
inputs, no new panel row, no change to the palette, the font, the panel width or any approved module beyond the
wiring points of 15.1.

---

## 16. Phase 5 — Done When

**Status: SPEC APPROVED (2026-10-08) — NOT YET BUILT.** Every bullet below must hold before the phase is called
implemented. The portable bullets are proven by `python -m unittest discover -s tests -v` and
`python tools/mql5_compile_smoke.py`; the live-terminal bullets are the author's to confirm on a real MT5 chart,
exactly as sections 10, 12 and 14 were, and the status stamps of this section are appended only when they pass.

**Status: PHASE 5 COMPLETE (2026-10-08).** Marked complete at the author's direction on 2026-10-08. Every rule
of 15.3 – 15.11 is built and closed: `Include/Emtt/Emtt_VolumeFlow.mqh` (session anchor, session VWAP, volume
profile, prior-session naked POC, CVD and `volumeFlowScore`), `Include/Emtt/Emtt_MTF.mqh` (the mapped
higher-timeframe context and `mtfScore`) and the Phase 5 wiring in `Experts/Emtt.mq5` — both closed-bar paths,
the one-per-second timer poll, the three-term history gate, the Row 9 clauses and the Row 10 precedence with
its terminal line. The five approved headers are byte-identical (the Phase 1 dashboard digest `cc4169b5bd8e`
included), the inputs are still Magic number + Auto Trading, and no new chart-timeframe handle, file or
GlobalVariable was added. `python -m unittest discover -s tests -v` → 173 tests, all passing (12 Phase 2 +
44 Phase 3 + 29 Phase 4 + 88 Phase 5); `python tools/mql5_compile_smoke.py` green with both new headers, every
Phase 5 marker of 15.15 and the no-drawing guard extended to both. The live-terminal bullets of this section
are the author's own record on a real MT5 chart — the MetaEditor compile and the on-chart checks, exactly as
sections 10, 12 and 14 were — and no later phase reopens Phase 5.

**Spec note (15.11).** One reading of the parameter table needed a judgment call: the Layer 1 base matrix
gives Indices its own row, `150 / 200 / 250`, and its own sentence — "crypto and indices turn over faster, so
their footprints go stale sooner and their window is shorter" — while the resolved-window table below it
groups `Metals, Indices` at `300 / 375 / 400 (450 clamped)`, which would only hold if Indices High were 300.
The Layer 1 row won, so Indices resolves to `150 / 188 / 225` (Low), `200 / 250 / 300` (Normal) and
`250 / 313 / 375` (High, M5 / M15 / M30). If the author means `Metals, Indices` to share the High column, the
only cells that change are Indices High M5 (`250 → 300`), M15 (`313 → 375`) and M30 (`375 → 400`), with the
gate two bars above each.

**Parser check: REQUIRED AT DELIVERY (Hard Rule 3).** `python tools/mql5_parser_check.py` must exit `0` with
`0 syntax errors` on the Phase 5 sources — the built-in negative control rejected first, then
`Emtt_VolumeFlow.mqh`, `Emtt_MTF.mqh` and the Phase 5 wiring in `Experts/Emtt.mq5` reported clean, with their
sha256 and node counts recorded here as they were in sections 8, 10, 12 and 14.

**Parser check: PASSED (2026-10-08).** Rule 3, `python tools/mql5_parser_check.py` → exit `0`,
`0 syntax errors`, the built-in negative control rejected first and then accepted; the Phase 5 sources
`Include/Emtt/Emtt_VolumeFlow.mqh` (sha256 `00fa34cc0fc7`, 8597 nodes), `Include/Emtt/Emtt_MTF.mqh`
(sha256 `e12d61226ce5`, 8729 nodes) and the Phase 5 wiring in `Experts/Emtt.mq5` (sha256 `fe4f4fec2226`,
9888 nodes — cumulative, shared with Phases 1–4) reported clean.

- The VWAP, the POC / VAH / VAL, the prior POC and its nakedness, the CVD and its classification, the
  `volumeFlowScore`, and every HTF reading come from **closed bars only**; index 0 is never read, and nothing
  runs on ticks — the MTF timer poll is a bar-time comparison, and its advance reads only closed HTF bars.
- Nothing repaints: a session's VWAP and CVD are running sums over that session's closed bars, reset only at a
  journaled session re-anchor; the profile, the magnet, the classification and the HTF readings are never
  revised. Restart, timeframe round-trip and chart / HTF replay reproduce **identical** anchors, VWAP, profile,
  CVD classification, score, HTF regime, HTF direction and HTF structure.
- The profile window follows the class / bucket matrix of 15.11 and Layer 2, changes at most once and then not
  again for 2 closed bars, stays clamped to `50 … 400`, and every change appears in the journal with its
  reason. The readings are **never** delayed or damped by that pause.
- The history gate is the three-term `max()` and resolves to **302 / 377 / 402** in the worst case (250 / 300 /
  350 wherever the Supertrend requirement is the larger one); the loading line's M is the resolved value, and
  while the gate is open Rows 1, 9 and 10 behave exactly as they do today.
- Row 9 reads `<regime sentence> | <Supertrend clause> | <structure clause> | <volume-flow clause> | <MTF
  clause>`, each clause at most three parts and only one level, and the whole row wraps inside the existing
  fixed width with no new row, no colour, no size and no font change. Rows 2–7 and 11–14 stay label-only;
  `Expected Duration:` stays empty.
- Row 10 shows the precedence of 15.10 (MTF flip > CHoCH > BOS > sweep > CVD flip > Phase 3 > Phase 2) inside
  the 3-closed-bar freshness windows, the terminal line appears exactly when all four components are ready, and
  section 7's `No trade — …` messages still do not appear.
- The scores, the CVD value, the VWAP price, the POC / VAH / VAL figures, the HTF cluster / multiplier / ATR
  and every other fact of 15.7 / 15.9 appear **nowhere** on the panel beyond the clause words 15.10 allows.
- Regime, Supertrend, structure, flow and the HTF reading may all disagree on screen at the same time, and each
  shows exactly what it measured — nothing is worded, coloured or suppressed to make them look consistent.
- Every session re-anchor, CVD flip, window change, HTF rebuild / flip / regime change / structure event, and
  both replay summary lines are in the journal with their prices and bar times, so the author can check each
  one against the chart without Emtt drawing anything.
- **The EA still draws nothing but the panel** — no line, rectangle, arrow or chart label of any kind — and all
  panel objects are still removed cleanly when the EA is removed from the chart.
- `Emtt_Dashboard.mqh`, `Emtt_DynamicParams.mqh`, `Emtt_Regime.mqh`, `Emtt_Supertrend.mqh` and `Emtt_SMC.mqh`
  are byte-identical; inputs are still Magic number + Auto Trading; there is no new chart-timeframe handle, no
  new file and no new GlobalVariable; and the MTF context's HTF handle set is created, used and released only
  by the MTF context.
- On H1 and other charts rule 19 still wins: `--` fields, red incompatible-timeframe STATUS, nothing measured or
  shown, Price Row still live and exact.
- Initialisation with the full replay — chart **and** HTF — stays visibly instant, with no stutter on ticks.
- On a live MT5 chart, the author confirms what Emtt now says is what the market actually did: the VWAP sits
  where the session's volume-weighted price actually is; the bars behind `CVD up` show more close-near-the-high
  volume than close-near-the-low; the POC / value area match the densest traded band visible on the chart; the
  naked POC is the previous session's densest level, which price has not touched since; and the MTF words match
  what that timeframe's own chart shows — regime, trend direction and zone — checked by opening the M15 / H1 /
  H4 chart side by side.
- `python -m unittest discover -s tests -v` and `python tools/mql5_compile_smoke.py` pass, with the two Phase 5
  headers and markers in the CI contract, the no-drawing guard extended to both, and the Phase 1 dashboard
  digest plus every Phase 2, Phase 3 and Phase 4 marker still asserted.

**Decision (2026-10-09) — Indices volume window.** The author asked the builder to decide. The standard value is used, and the parameter engine moves it only when the symbol class and the market condition require it. Once it moves, it holds for 2 closed bars (the pause in 9.2 item 3). Indices keep their own row from the Layer 1 base matrix: `150 / 188 / 225` (Low), `200 / 250 / 300` (Normal) and `250 / 313 / 375` (High, M5 / M15 / M30). The reason is the 15.11 rationale: indices turn over faster, so their window is shorter than Metals'; in High volatility that is 250 against 300. The grouped `Metals, Indices` High cell (`300 / 375 / 400`) therefore applies to Metals only. This stamp governs the Indices High cell above; no existing text is changed. `Emtt_VolumeFlow.mqh` already builds these values (`EmttVfMatrixWindow`), so the decision needs no code change and no Phase 6 change.

---

## 17. Phase 6 — Signal and Trade Plan (no orders)

**Status: SPEC APPROVED (2026-10-09) — BUILD AUTHORISED.** The author approved the design on 2026-10-09 and asked for the build to start in a new chat from this section. Nothing in this phase places an order. Emtt says what it would do, where, and why, and nothing more.

**Status: IMPLEMENTED (2026-10-09) — PORTABLE GATES GREEN; LIVE-CHART CONFIRMATION PENDING THE AUTHOR.** Built as one change set per the 17.1 table: `Include/Emtt/Emtt_TradePlan.mqh` (Entry, Stop, Target, Risk:Reward and Expected Duration as pure functions of the published readings and the matrix ATR — no level is typed in), `Include/Emtt/Emtt_Signal.mqh` (the four-view combination, the mood bar and the 5-point stay margin, the signal gate, the plan lifecycle and the result journal lines), and the Phase 6 wiring in `Experts/Emtt.mq5` — the incremental closed-bar path, the post-replay evaluation at the newest closed bar, the market-closed and chart-changed plan ends, and `FillPanel()`. `#property version` is `1.50`. The seven approved headers are byte-identical (the Phase 1 dashboard digest `cc4169b5bd8e` included), the inputs are still Magic number + Auto Trading, and no new chart-timeframe handle, data file or GlobalVariable was added. `python -m unittest discover -s tests -v` → 246 tests, all passing (173 of Phases 2–5 + 73 Phase 6); `python tools/mql5_compile_smoke.py` green with both new headers, every Phase 6 marker of 17.9 and the three guards (chart drawing, orders, ASCII). The live-terminal bullets of section 18 are the author's own record on a real MT5 chart, exactly as sections 10, 12, 14 and 16 were.

This phase builds the items that 15.14 carried forward: the **confidence engine**, **Entry / SL / TP**, **Risk:Reward** and **Expected Duration**. It fills the rows that have stayed label-only since Phase 1: Rows 2–7, and `Expected Duration:` in Row 8.

Decisions carried as rules of this section:

1. **Gate (author).** BUY or SELL only when confidence clears the market-mood bar **and** the trade plan passes its checks. Otherwise WAIT, with the reason.
2. **Entry (author).** Calculated by Emtt, never typed in. BUY and SELL always carry an Entry. WAIT carries none.
3. **Stop (author's final decision).** Just beyond the nearest turning point or the order block's far edge, whichever is further from entry, plus 0.5 ATR. It must sit between 1 and 3 ATR from entry. If it would be further than 3 ATR, the idea is skipped.
4. **Target (author).** Calculated by Emtt from real measured levels: fair value gap, volume level or liquidity pool. Never hard-coded, never fabricated. Minimum Risk:Reward is 1.5:1 in a clear trend and 2:1 in the other moods.
5. **Timing (author).** The signal changes only when a candle closes. No waiting for two or three candles.
6. **Builder additions, not yet confirmed by the author.** A 5-point stay margin: once BUY or SELL shows, it stays until confidence falls 5 points below its bar, with no delay. A fixed plan: entry, stop and target do not move while the signal lasts. The plan end rules of 17.7. Money amounts show `--`. The author can change any of these before the build starts.
7. **Standing rules.** No chart drawing of any kind (13.2 rule 1). Every number is a named row of the parameter table (17.5). The phase is delivered whole, in one change set, with no sub-phases (13.1 Delivery).

The numbers in 17.5 are the builder's proposal. They are the starting values for the build unless the author changes them here first.

### 17.1 Files

| File | Change |
|---|---|
| `Include/Emtt/Emtt_TradePlan.mqh` | new — Entry, Stop, Target, Risk:Reward and Expected Duration; pure functions of published readings and the ATR |
| `Include/Emtt/Emtt_Signal.mqh` | new — four-view combination, mood bar and stay margin, signal gate, plan lifecycle and result journal lines; pure logic over the four published states |
| `Experts/Emtt.mq5` | wired into the closed-candle path (after the four components advance) and into `FillPanel()`; `#property version` becomes `1.50`; the description gains `Phase 6: signal and trade plan (no orders).` |
| `tests/phase6_reference.py` + `tests/test_phase6_reference.py` | new — MT5-free mirror of 17.2–17.8, same pattern as Phases 2–5; scope in 17.9 |
| `tools/mql5_compile_smoke.py` | contract gains the two headers, the Phase 6 markers and the three guards of 17.9, applied to both new headers and the EA |
| `README.md` | one Phase 6 paragraph |

`Emtt_Dashboard.mqh`, `Emtt_DynamicParams.mqh`, `Emtt_Regime.mqh`, `Emtt_Supertrend.mqh`, `Emtt_SMC.mqh`, `Emtt_VolumeFlow.mqh` and `Emtt_MTF.mqh` are **not touched** and stay byte-identical. They are consumed, never edited. Sections 1–16 are not rewritten. Inputs stay **Magic number + Auto Trading**. No new chart-timeframe handle, data file or GlobalVariable is added.

### 17.2 Rules for this phase

1. **No orders in this phase.** Nothing in the EA sends, modifies, closes or deletes an order or a position. Auto Trading changes nothing but the header word (6 rule 9). The LIVE TRADE block stays hidden, because Emtt holds no position of its own (6 rule 8).
2. **Closed candles only.** Every decision uses the newest closed candle. The forming candle is never read. Per tick, only the Price Row updates, as today. Row 4's distance and the level lines of 17.6 refresh on the one-second timer.
3. **The signal changes only at a candle close, with no extra candles.** The two-candle confirmation of 9.2.6 belongs to the regime label that Row 1 shows, and the signal does not use it. The mood used in 17.3 is the mood measured at the newest closed candle: the Regime module's pending candidate when one is open, otherwise its confirmed label. `Emtt_Regime.mqh` is read, not edited.
4. **A signal needs all four views ready.** No partial confidence is ever shown (15.10). Until they are ready, Row 2 shows `--`.
5. **The plan is fixed.** When a BUY or SELL first appears, Entry, Stop, Target, Risk:Reward and Expected Duration are set. They do not move until the plan ends (17.7).
6. **Nothing invented.** Every level comes from a published reading (13.3, 13.5, 13.6, 13.7, 15.5, 15.7) or from the ATR. A field with no measured value shows `--` (9.2.8).
7. **Components are not reconciled** (11.8, 13.2 rule 7). The one confidence figure is the combined result (6 rule 6), recomputed at each closed candle. "Updates live" in 6 rule 6 is met by the panel's one-second refresh.
8. **No repainting.** A decision made on a closed candle is final. Later candles make new decisions. They never revise an old one.
9. **ASCII source.** The two new headers contain only ASCII characters. Every glyph or dash is written as an escape, for example `"\x25BA"` for ► and `"\x2014"` for —. The compiler can misread non-ASCII source bytes, and these files are edited outside MetaEditor (17.9).

### 17.3 Confidence and the signal gate

Four views, each already published with a direction and a score. Their modules are not changed.

| View | Direction d | Score s | Weight w (17.5 row i) |
|---|---|---|---|
| Trend | Supertrend `direction` (+1 / −1 / 0) | `supertrendScore` | 0.30 |
| Structure | SMC `bias` (+1 / −1 / 0) | `smcScore` | 0.30 |
| Volume flow | `flowDirection` (+1 / −1 / 0) | `volumeFlowScore` | 0.20 |
| Higher chart | `htfSupertrendDirection` (+1 / −1 / 0) | `mtfScore` | 0.20 |

`mtfScore` carries strength only (15.9); its direction is the HTF Supertrend direction.

- **Combined value:** S = Σ (w × s × d). The weights sum to exactly 1.0, so S lies between −1 and +1. A view pointing the other way pulls S down. A flat view (d = 0) adds nothing.
- **The number:** BUY confidence = 100 × max(0, S). SELL confidence = 100 × max(0, −S). Row 3 shows the larger of the two as one whole number, `round(100 × |S|)`, with halves rounded up.
- **The bar** (9.2.4, unchanged): TRENDING 60%, RANGING 70%, VOLATILE 70%, TRANSITION 75%, read from the mood of 17.2 rule 3. The comparison uses the same whole number that Row 3 shows.
- **Gate:** BUY when S is above 0 and its number is at least the bar. SELL when S is below 0 and its number is at least the bar. Otherwise WAIT, with the reason in 17.6. The gate also needs a valid plan (17.4).
- **Stay margin (no delay, row h of 17.5):** once a BUY or SELL shows, it stays while its number is at least **bar − 5** (5 confidence points, not price points). This stops a value resting on the bar from flipping the signal. Entering needs the bar; staying needs bar − 5. A change of mood moves the bar at the next closed candle.
- **Market closed:** Row 2 shows `--`, no evaluation runs, and any open plan ends (17.7).

### 17.4 Entry, Stop, Target, Risk:Reward and Expected Duration

The rules are written for BUY. SELL is the exact mirror: above and below swap, and Ask and Bid swap.

**ATR:** the matrix `atrPeriod` value at the newest closed candle, the same ATR used by 13.5–13.9 and by the Supertrend (11.3).

**Entry**
- If the published order block points the same way (bias +1) and its near edge lies below the close by more than 0 and by at most `2.0 × ATR` (17.5 row d), Entry = that near edge. Price pulls back into the block.
- Otherwise (no block, a block the other way, a block too far, or price already inside it, which is distance 0 in 13.9), Entry = the current **Ask** for BUY or **Bid** for SELL, read at the evaluation.
- BUY and SELL always carry an Entry. WAIT never does.

**Stop (the author's rule)**
- Two candidates, each used only if it lies below Entry:
  - the nearest confirmed turning point, which is the newest confirmed swing low (13.3);
  - the far edge of the order block, only when Entry came from that block.
- Reference = the candidate **further from Entry**. If only one candidate exists, it is the Reference. If none exists, WAIT (reason in 17.6).
- Stop = Reference − `0.5 × ATR` (17.5 row a).
- If the Stop is closer than `1.0 × ATR` to Entry, it moves out to exactly `1.0 × ATR` (row b). It stays beyond the Reference.
- If the Stop is further than `3.0 × ATR` from Entry (row c), the idea is skipped (WAIT).

**Target (one only)**
- Candidates on the trade side of Entry: the published fair value gap near edge for a gap above (13.6, 13.9); the largest buy-side pool level (13.7, which publishes the pool price); the published POC, VAH and VAL (15.5, 15.7); and the prior-session naked POC while it is still naked (15.5).
- Sort the candidates nearest first. The first one that gives at least the minimum Risk:Reward is the Target. If none does, WAIT.
- Equal prices: fair value gap, buy-side pool, POC, VAH, VAL, naked POC.

**Risk:Reward** = (Target − Entry) ÷ (Entry − Stop), shown as `1:x.x` with one decimal. The minimum is row g of 17.5.

**Expected Duration**
- Speed (ATR per candle) = Supertrend `distanceATRs` ÷ `barsSinceFlip` (11.6 names both as the momentum inputs for this row). `distanceATRs` is measured on the Supertrend's own side, so it describes the trade's move only while the Supertrend points the trade's way. Otherwise speed is 0 and the floor applies. Speed is never below the floor (row e).
- Candles to Target = (distance from Entry to Target ÷ ATR) ÷ speed.
- Shown as a range from `0.5 ×` to `1.5 ×` that estimate (row f). Minutes per candle come from the chart timeframe (M5 = 5, M15 = 15, M30 = 30). Under 2 hours, the range is in minutes (nearest 5). From 2 hours to 3 days, it is in hours (nearest whole). Beyond 3 days, it shows `> 3 days`.
- Fixed when the plan starts.

### 17.5 Parameter rows Phase 6 adds to the table of 9.2.3

Every number in Phase 6 is a named row here. None of them is a lookback, so Layer 2 scales none of them. A row that is the same in every column is fixed by design, the same standing as the displacement multiple (15.11) and the equal-level tolerance (13.7). It stays a named row so that the table is complete.

| Row | Class | Layer 1 standard (every symbol class) | Layer 3 volatility (Low / Normal / High) | Layer 4 regime (four moods) |
|---|---|---|---|---|
| a. Stop buffer beyond the Reference | Management | `0.5 × ATR` | `0.5` in all three | `0.5` in all four |
| b. Stop minimum distance from Entry | Management | `1.0 × ATR` | `1.0` in all three | `1.0` in all four |
| c. Stop maximum distance from Entry (skip above it) | Strictness | `3.0 × ATR` | `3.0` in all three | `3.0` in all four |
| d. Entry reach to the order-block edge | Management | `2.0 × ATR` | `2.0` in all three | `2.0` in all four |
| e. Speed floor for Expected Duration | Management | `0.2 × ATR` per candle | `0.2` in all three | `0.2` in all four |
| f. Duration band around the estimate | Management | `0.5 ×` and `1.5 ×` | the same in all three | the same in all four |
| g. Minimum Risk:Reward | Strictness | `1.5` | `1.5` in all three | TRENDING `1.5`; RANGING, VOLATILE and TRANSITION `2.0` |
| h. Stay margin below the bar | Strictness | `5` confidence points | `5` in all three | `5` in all four |
| i. Confidence weights: Trend / Structure / Volume flow / Higher chart | Strictness | `0.30 / 0.30 / 0.20 / 0.20` | the same in all three | the same in all four |

- **Guard rail (9.2.3):** a row that changes follows one change, then the same value stays put for 2 closed candles. The pause limits how often the value itself moves. The signal is judged on every closed candle against the value in effect; a BUY or SELL is never held back waiting for a pause.
- **Presentation, not parameters:** the display rounding, the 2-hour and 3-day switch points and the Row 3 rounding are fixed text rules.
- **Required history:** no new gate. Phase 6 adds no lookback, and the 302 / 377 / 402 gate of 15.11 already covers every view.

### 17.6 Panel — what the user sees

The layout does not change: same rows, same width, same font, same palette, no new row. The LIVE TRADE block is absent, so the panel ends at Row 10. Only Row 2 takes a signal colour. Every other row keeps the soft colour, except the red incompatible-timeframe message on Row 10 (6 rule 17 and rule 19).

**Glyphs.** The panel font is `Segoe UI` (`EMTT_FONT`), and the panel text is drawn with label objects. ► (U+25BA), ▲ (U+25B2), ▼ (U+25BC) and ■ (U+25A0) are all in Segoe UI. The ⏸ used for WAIT in the Panel B mock-up of section 5 is not in Segoe UI, so it would not display. WAIT shows ■ instead. Each glyph is written as an escape in code (17.2 rule 9).

While a BUY or SELL is shown:
- **Price Row:** `►Ask` for BUY, `►Bid` for SELL.
- **Row 1:** the regime, unchanged.
- **Row 2:** `SIGNAL: ▲ BUY` in the BUY colour at size 14; `SIGNAL: ▼ SELL` in the SELL colour at size 14 (the mirror of Panel A's ▲).
- **Row 3:** `Confidence: NN%`, one whole number.
- **Row 4:** `Entry: <price> / --  (<N> pts away)`, measured from the dealing price.
- **Row 5:** `Stop Loss: <price> / --  (<N> pts)`, measured from Entry.
- **Row 6:** `Take Profit: <price> / --  (<N> pts)`, measured from Entry.
- **Row 7:** `Risk:Reward: 1:x.x`.
- **Row 8:** `Session: <name> | Expected Duration: ~<low>-<high> <unit>`.
- **Row 9:** WHY, unchanged from 15.10.
- **Row 10:** the signal line below.

While WAIT is shown:
- **Price Row:** no marker.
- **Row 2:** `SIGNAL: ■ WAIT` in the soft colour at size 12.
- **Row 3:** `Confidence: NN%`.
- **Rows 4–7:** `Entry: -- / --  (-- pts away)`, `Stop Loss: -- / --  (-- pts)`, `Take Profit: -- / --  (-- pts)`, `Risk:Reward: --`.
- **Row 8:** `Session: <name> | Expected Duration: --`.
- **Row 9:** WHY, unchanged.
- **Row 10:** the WAIT reason below.

While the chart is loading history, or the market is closed, or the chart is incompatible:
- **Loading history:** Row 1 and Row 9 show `--`, and Row 8 shows the session, as 9.2.8 says. Row 2 and Rows 3–7 show `--`. Row 10 shows the existing loading line.
- **Market closed:** Row 1 shows `MARKET CLOSED` (9.2.8). Rows 2–9 show `--`. Row 10 shows the existing Phase 2 market-closed line.
- **Incompatible chart:** rule 19 applies. Every data field shows `--`, the Price Row stays live and the red message shows.

Rules for every state:
- The money part of Rows 4–6 shows `--` in every state. No trade size exists before the safety step. Panel B's `$0.00` is the Phase 1 layout example, and Phase 6 shows no dummy money values.
- Rows 2, 3 and 4–8 change only at a closed candle. The Row 4 distance and the level lines refresh on the one-second timer.
- The header is unchanged. It may still read `Auto Trading: ON`. The pending and active lines say `No order placed.`

STATUS lines (Row 10), used while the four views are ready — exact wording:
- Pending plan: `Signal active — waiting for price to reach entry. No order placed.`
- Active plan: `Signal active — price reached entry. No order placed.`
- WAIT, one reason at a time, checked in this order:
  - `Watching — confidence NN%, below the MM% bar.`
  - `Watching — confidence NN%, below the MM% level that keeps a BUY.` (SELL: keeps a SELL.) Used only when a BUY or SELL was showing and its number has fallen below bar − 5.
  - `Watching — confidence NN%, but no target gives 1:X.X yet.`
  - `Watching — confidence NN%, but the stop would be more than 3.0 ATR away.`
  - `Watching — confidence NN%, but no swing point for the stop yet.`
  - `Watching — the last idea just ended; a new one can start on the next candle.` (17.7)
- Level line, shown only while a plan is open and refreshed on the one-second timer. It is a display comparison of the live price with a stored level and changes no state:
  - `Stop level passed — signal updates at this candle's close.`
  - `Target level passed — signal updates at this candle's close.`

Row 10 precedence: the rule 19 red message first, then the loading line, then MARKET CLOSED, then the signal line. The signal line replaces the terminal line of 15.10. The Phase 3–5 event lines show only while the four views are not all ready. Their facts remain in Row 9 and in the journal.

### 17.7 Plan lifecycle and results

- A plan starts when a BUY or SELL first appears and passes its checks (17.4). Its levels are fixed (17.2 rule 5).
- A plan whose Entry is the market price (Ask or Bid) is **active** from the candle that started it. A plan whose Entry is an order-block edge is **pending** until a candle reaches that edge.
- A candle reaches a level when the level lies between its low and high. **Spread is not added.** Checks use only candles that closed after the plan started.
- A plan ends at the close of the candle that reaches its end level, or at the close where the signal changes.
- Each plan ends with exactly one result:

| Result | When |
|---|---|
| `target reached` | active, and a candle reaches the Target |
| `stop reached` | active, and a candle reaches the Stop |
| `missed` | pending, and a candle reaches the Target before the Entry |
| `cancelled` | pending, and a candle reaches the Stop before the Entry |
| `signal changed` | at a closed candle the signal becomes WAIT or the other side |
| `market closed` or `chart changed` | the market closes, or the symbol or timeframe changes |

- **One candle, more than one level:** the worse result counts. From worst to best the order is: stop reached, cancelled, missed, target reached. So a candle that touches the stop and the entry is recorded as `stop reached`, and a candle that touches the entry and the target while the plan is pending is recorded as `missed`. The journal marks such a candle `shared candle`. The ranking is the builder's reading of "worse"; the author can reorder it.
- **Exit price:** the level reached, or the candle's close for `signal changed`, `market closed` and `chart changed`.
- **Next idea:** after a plan ends, a new idea can start at the **next** closed candle. The candle that ended a plan never starts one. On that candle Row 2 shows WAIT with the reason in 17.6. This is the builder's reading of the agreed rule; the author can allow a same-candle start.
- Plans live in memory only. A restart does not restore them. Nothing is written to a file or a GlobalVariable.

### 17.8 Determinism, state and journal

- The same closed candles give the same four readings, the same confidence number and the same signal. The one value that depends on the live quote is a market-price Entry. It is journaled with its bar time.
- Work per closed candle is bounded. Nothing runs per tick beyond `UpdatePanel()`.
- Journal: the existing `PrintFormat` channel, shape `Emtt | <what> | <detail> | bar <time>`. Lines are written on state changes, plan events and WAIT reason changes only:
  - `Emtt | Signal BUY | confidence 72% | Trending, bar 60% | bar 2026.10.09 14:30`
  - `Emtt | Plan BUY | confidence 72% | entry 1.08450 (order block edge) | stop 1.08280 (swing low -0.5 ATR) | target 1.09120 (fair value gap) | RR 1:3.9 | expected ~2-4 hours | spread 2 pts | bar 2026.10.09 14:30`
  - `Emtt | Plan BUY | entry reached | 1.08450 | bar 2026.10.09 15:00`
  - `Emtt | Plan BUY result | target reached | exit 1.09120 | +670 pts | 12 candles | bar 2026.10.09 17:30`
  - `Emtt | Plan BUY result | stop reached | exit 1.08280 | -170 pts | 6 candles | shared candle | bar 2026.10.09 16:00`
  - `Emtt | Signal WAIT | confidence 66%, no target gives 1:1.5 | bar 2026.10.09 14:45`
  - `Emtt | Signal WAIT | reason changed: stop would be more than 3.0 ATR away | bar 2026.10.09 19:00`
- Never journaled: the per-candle confidence values, a WAIT that continues with the same reason, and any candle where nothing changed.

### 17.9 Tests, gates and guards

`tests/phase6_reference.py` mirrors 17.2–17.8. `tests/test_phase6_reference.py` asserts, without MT5:
- **Combination:** the four weights sum to exactly 1.0; S stays between −1 and +1; a flat view adds nothing; an opposing view lowers the number; Row 3 equals `round(100 × |S|)` with halves rounded up.
- **Gate:** the bar for each mood; the comparison on the whole number; entry at the bar, staying at bar − 5, leaving below it; one closed candle can flip a signal (no hold).
- **Entry:** a block within `(0, 2.0]` ATR gives its near edge; a block the other way, a block too far, price inside a block, or no block gives the market price; the SELL mirror.
- **Stop:** only candidates below Entry are used; the further of the turning point and the block far edge is the Reference; a single candidate is used alone; no candidate gives WAIT; the buffer; widening to `1.0 ATR`; skipping above `3.0 ATR`; the SELL mirror.
- **Target:** the nearest candidate that meets the minimum; candidates below the minimum are skipped; none gives WAIT; the equal-price order.
- **Risk:Reward:** the formula; one decimal; minimum 1.5 when TRENDING, 2.0 otherwise.
- **Expected Duration:** the speed formula; the floor; speed 0 when the Supertrend opposes; the `0.5 ×` / `1.5 ×` band; the switch to hours at 2 hours and to `> 3 days`; rounding; fixed after the start.
- **Lifecycle:** each result of 17.7; the worse-result order for every two-level candle; the next-candle rule; spread not added; candles checked only after the start; the exit prices; a market-price Entry active at once.
- **Journal:** the plan start line carries the confidence; a WAIT reason change is journaled; a WAIT that continues is not.
- **Panel text:** each STATUS line and its trigger; Rows 2–8 for BUY, SELL, WAIT and the `--` states; money parts always `--`; the ► rule; the ■ WAIT glyph.
- **Determinism:** the same closed candles replayed twice give the same confidence, signal and plan.

`tools/mql5_compile_smoke.py` gains the two headers in its required set and asserts these markers: `EMTT_SIG_WEIGHT_TREND 0.30`, `EMTT_SIG_WEIGHT_STRUCTURE 0.30`, `EMTT_SIG_WEIGHT_FLOW 0.20`, `EMTT_SIG_WEIGHT_HTF 0.20`, `EMTT_SIG_STAY_MARGIN 5`, `EMTT_PLAN_STOP_BUFFER_ATR 0.5`, `EMTT_PLAN_STOP_MIN_ATR 1.0`, `EMTT_PLAN_STOP_MAX_ATR 3.0`, `EMTT_PLAN_ENTRY_REACH_ATR 2.0`, `EMTT_PLAN_SPEED_FLOOR 0.2`, `EMTT_PLAN_DURATION_LOW 0.5`, `EMTT_PLAN_DURATION_HIGH 1.5`, `EMTT_PLAN_RR_TREND 1.5`, `EMTT_PLAN_RR_OTHER 2.0`. In the EA it asserts `SEmttSignalState g_signal;`, and the includes `Emtt_TradePlan.mqh` then `Emtt_Signal.mqh`, both after the MTF include. It also asserts the Phase 1 dashboard digest and every Phase 2–5 marker, unchanged.

Three guards apply:
- the chart-drawing guard of 15.2 rule 1 (the Phase 4 forbidden list), applied to both new headers and the EA;
- a **no-order guard**, applied to both new headers and the EA: no `OrderSend`, `OrderSendAsync`, `OrderModify`, `OrderDelete`, `PositionModify`, `PositionClose`, `PositionCloseBy` or `CTrade` token;
- an **ASCII guard**, applied to the two new headers: any byte above 0x7F fails the build (17.2 rule 9).

### 17.10 Not in this phase

No orders of any kind; no lot size; no dollar amounts; no Stop or Take Profit sent to a broker; no LIVE TRADE content; no trade management (breakeven, trailing, partial close, time exit); no news, session or spread blocking; no alerts; no self-learning and no parameter persistence; no signal logic on ticks; no chart drawing; no new input; no new panel row; no change to palette, font or width; no change to any approved module.

---

## 18. Phase 6 — Done When

**Historical status (2026-10-09): SPEC APPROVED — NOT YET BUILT.** This records the phase's state at specification approval; it is superseded by the implementation and closure status below. The checklist still distinguishes portable code gates from live-terminal acceptance checks, which must be confirmed by the author on a real MT5 chart.

**Status: PHASE 6 COMPLETE (2026-10-10, at the author's direction) — CODE IMPLEMENTATION AND PORTABLE GATES GREEN; LIVE-TERMINAL ACCEPTANCE NOT CONFIRMED.** Every portable bullet below holds. `python -m unittest discover -s tests -v` → 246 tests, all passing (173 Phases 2–5, unchanged, + 73 Phase 6). `python tools/mql5_compile_smoke.py` is green: the two new headers are in the required-source set with every Phase 6 marker of 17.9, the include order TradePlan then Signal after the MTF include, exactly one `SEmttSignalState g_signal;`, and the three guards of 17.9 — the chart-drawing list applied to both new headers and the EA, the no-order token list applied to both new headers and the EA, and the ASCII guard on both new headers — alongside the unchanged Phase 1 dashboard digest and every Phase 2–5 marker. The seven approved modules are byte-identical; inputs are still Magic number + Auto Trading; no new chart handle, data file or GlobalVariable exists; no order call exists in the EA or the new headers; nothing but the panel is drawn. The signal changes only at a closed candle (no hold exists in the code), Entry / Stop / Target / Risk:Reward / Expected Duration come from published readings or the ATR with `--` where 17.6 says (money parts included), and every number is a row of 17.5. The panel matches 17.6 — Rows 2–8 and 10 as specified, the ► marker, the ■ WAIT glyph, no LIVE TRADE block, and the ⏸ symbol appears nowhere in the Phase 6 code. The journal lines of 17.8 are written on state changes, plan events and WAIT reason changes only, and the plan start line carries the confidence. The live-terminal bullets (the on-chart M15 demo confirmations and the H1 rule-19 check) are the author's to confirm on a real MT5 chart, exactly as sections 10, 12, 14 and 16 were.

**Closure boundary.** No known Phase 6 code item remains unimplemented within 17.1–17.10; items listed under 17.10 are intentionally excluded, not unfinished. Verification rerun on 2026-10-10: all 246 unit tests pass, the compile smoke passes, and the MQL5 parser accepts all 10 MQL sources with 0 syntax errors. This author-directed completion records implementation and portable verification only: a native MetaEditor compile and the M15/H1 live-terminal checks below were not run here, so they remain unverified acceptance checks.

**Parser check: PASSED (2026-10-10).** Rule 3, `python tools/mql5_parser_check.py` → exit `0`, `0 syntax errors`, the built-in negative control rejected first and then accepted; the Phase 6 sources `Include/Emtt/Emtt_TradePlan.mqh` (sha256 `e52a6005ff2e`, 2573 nodes), `Include/Emtt/Emtt_Signal.mqh` (sha256 `5e440ae8b577`, 4736 nodes) and the Phase 6 wiring in `Experts/Emtt.mq5` (sha256 `8af117198606`, 11529 nodes — cumulative, shared with Phases 1–5) reported clean.

- The 173 existing tests and every new Phase 6 test pass. The compile smoke is green with the two headers, the Phase 6 markers and the three guards (chart drawing, orders, ASCII).
- `python tools/mql5_parser_check.py` exits `0` on the Phase 6 sources, with the built-in negative control rejected first (Hard Rule 3). The sha256 and node counts are recorded here at delivery, as in sections 8, 10, 12, 14 and 16.
- `Emtt_Dashboard.mqh` keeps its digest `cc4169b5bd8e`. The other six approved modules are byte-identical. Inputs are still Magic number + Auto Trading. No new chart handle, data file or GlobalVariable exists.
- No order call exists in the EA or in the new headers. Auto Trading changes nothing but the header word.
- No chart drawing of any kind. All panel objects are still removed cleanly when the EA is removed.
- The signal changes only at a closed candle. No hold of two or three candles exists in the code.
- Entry, Stop, Target, Risk:Reward and Expected Duration are computed from published readings or the ATR. WAIT shows `--` where 17.6 says, money parts included. No level is typed in as a fixed price. Every number is a row of 17.5.
- The panel matches 17.6: Rows 2–8 and 10 as specified, the ► marker, the ■ WAIT glyph, no LIVE TRADE block, and the colours and sizes of the palette and rule 16. The ⏸ symbol appears nowhere in the code.
- The journal lines of 17.8 appear on state changes, plan events and WAIT reason changes only. The plan start line carries the confidence.
- On a live M15 demo chart, the author confirms: (a) SIGNAL and Confidence change only when a candle closes; (b) a BUY's Entry sits on a visible order-block edge or at the Ask; (c) its Stop sits beyond a visible swing low or order-block edge, plus half an ATR; (d) its Target sits on a visible fair value gap, pool or volume level; (e) the journal prices and bar times match the chart; (f) the header reads Auto Trading and no order appears in the Trade tab; (g) Expected Duration is roughly right on a sample of logged plans; (h) ► shows beside Ask or Bid, and ▲, ▼ and ■ show in Row 2 without boxes.
- On an H1 chart, rule 19 still holds: `--` fields, the red message, and the Price Row still live.
