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
Portable suite 56/56 passing and `tools/mql5_compile_smoke.py` passing, CI green on the branch. MetaEditor
compilation and the on-chart checks of section 12 remain with the author.

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

**Status: IMPLEMENTED (2026-10-08) — LIVE-CHART VERIFICATION PENDING WITH THE AUTHOR.** Every bullet below is
built and covered by the portable suite (`python -m unittest discover -s tests -v`, 56 tests) and by
`python tools/mql5_compile_smoke.py`, both green in CI on branch `arena/6a5d60aa-emtt`. The MetaEditor compile
and the bullets that can only be judged on a live terminal — panel wrap and colours, `Waiting — Loading chart
history (N/M candles)` against the real M, H1 behaviour, clean object removal, visibly instant initialisation —
are the author's to confirm, exactly as section 10 was.

**Parser check: TESTED AT PARSER AND PASSED (2026-10-08).** Rule 3, `python tools/mql5_parser_check.py`
→ exit `0`, `0 syntax errors`, with the negative control rejected before the sources were accepted;
`Include/Emtt/Emtt_Supertrend.mqh` (sha256 `6b2d6a97abb7`, 6654 nodes) and the Phase 3 wiring in
`Experts/Emtt.mq5` (sha256 `6bff05191904`, 8193 nodes).

**PHASE 3 IMPLEMENTATION DONE (2026-10-08).** The build is complete. Outstanding items are the
author's live-chart confirmation and the MetaEditor compile, neither of which any tool available
here can substitute for.

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
