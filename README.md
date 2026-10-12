# Emtt

MT5 Trading Expert Adviser — **Author:** Ham · **Coder:** Arena · Living specification: [`Emtt.md`](Emtt.md)

## Repository layout (mirrors the MT5 data folder)

| Repo path | MT5 data folder |
|---|---|
| `Experts/Emtt.mq5` | `MQL5\Experts\Emtt.mq5` |
| `Include/Emtt/*.mqh` | `MQL5\Include\Emtt\` |

Copy the folders into your MT5 data folder, open `Experts/Emtt.mq5` in MetaEditor and compile,
then attach **Emtt** to a chart. The EA includes its headers with quoted relative paths, which
resolve both in this checkout and inside the terminal's data folder (spec §4a, §4b).

## Phase 1 — Layout (implemented)

`Include/Emtt/Emtt_Dashboard.mqh` remains the renderer and owns the fixed panel layout.
It provides the draggable, wrapped, fixed-width panel, palette, labels, and clean chart-object
removal. The renderer was not changed for Phase 2.

- The Phase-1 A/B layout still follows the Emtt magic-number position; manual trades are ignored.
- The Price Row uses the terminal's current Bid / Ask / Spread. A dealing-side marker waits for
  a signal-producing phase.
- M5 / M15 / M30 are the only analysis timeframes. Other charts retain the full panel, live
  Price Row, and red incompatible-timeframe STATUS.
- The existing settings remain **Magic number** (`20251007`) and **Auto Trading**.

## Phase 2 — Foundation and regime detection (implemented)

`Emtt_DynamicParams.mqh` classifies normalized symbols, ranks fixed ATR(14) readings into
hysteretic volatility buckets, resolves the approved class/bucket parameter matrix, applies the
regime confidence threshold, and journals changes. The parameter state is replayed from closed-bar
history on initialization so restarts and timeframe changes reconstruct the same state.

`Emtt_Regime.mqh` implements the closed-bar regime precedence and two-bar confirmation, broker
trading-session checks, the GMT-based Asia/London/New York clock with each market's DST rules, and
pre-signal WHY / STATUS text. `Experts/Emtt.mq5` wires these measurements into the existing panel
contract. Phase 2 adds no signal, order, or trade-management logic and no new inputs.

## Phase 3 — ML-adaptive Supertrend (implemented)

`Include/Emtt/Emtt_Supertrend.mqh` computes Supertrend bands in-house from the closed bars and the
ATR buffers the EA already copies — no custom indicator, no `.ex5`, no DLL. It clusters the training
window's raw ATR values with K-Means (K = 3, seeded from the window's own 10th / 50th / 90th
nearest-rank percentiles, max 20 Lloyd iterations) into **Calm / Normal / Wild**, learns one ATR
multiple per cluster from the candidates `2.0 / 2.5 / 3.0 / 3.5 / 4.0`, and publishes
`direction / line / cluster / multiplier / score` plus `barsSinceFlip`, `flipCount` and
`distanceATRs`. The training window is Emtt's first **lookback** parameter, so layer 2 of the
parameter engine scales it to 200 / 250 / 300 closed bars on M5 / M15 / M30 and the single history
gate becomes 250 / 300 / 350 candles. The multiplier obeys the 9.2.3 guard rails — one change, then
two quiet closed bars, every change journaled, never outside the candidate set — while direction,
cluster and score stay live readings.

Direction is context, not a signal: Row 9 gains ` | <Cluster> (Supertrend <direction>)` and Row 10
reads `Watching — Supertrend context only, no signal yet`. Rows 2–7 and 11–14 stay label-only, the
score and the trailing reference are never displayed, and the EA still draws nothing but the panel.
State is rebuilt by replaying closed bars, so a restart, a timeframe round-trip or a chart replay
reproduces the same clusters, multiplier, direction, line and score.

## Phase 4 — Market structure detection (implemented)

`Emtt_SMC.mqh` derives confirmed closed-bar swings, BOS / CHoCH, wick-only liquidity sweeps and equal-level pools,
Order Blocks, Fair Value Gaps, and Premium / Discount / Equilibrium from the selected matrix ATR. Its class, volatility
and timeframe-aware structure window, pivot strength, body period and derived OB lookback obey the existing two-bar
parameter pause and replay silently whenever they change. The component publishes bounded, deterministic facts and an
internal `smcScore`; it never draws on the chart or places a trade. Row 9 adds at most three compact structure facts
(zone, event and one priority level), while Row 10 gives fresh CHoCH, BOS and sweep updates precedence over the existing
Supertrend/regime status. All state is rebuilt from closed bars on initialization, reset, history recovery and context
changes, so chart replay and a restart reproduce the same structure context.

## Phase 5 — Volume flow and higher-timeframe agreement (implemented)

`Include/Emtt/Emtt_VolumeFlow.mqh` measures the closed-bar session VWAP, a 40-bin volume profile
(POC / VAH / VAL), the previous session's naked POC and the close-position CVD estimate, and
publishes the weighted `volumeFlowScore`. `Include/Emtt/Emtt_MTF.mqh` re-runs the regime,
Supertrend and structure stack on the mapped higher timeframe (M5 → M15, M15 → H1, M30 → H4) and
publishes that HTF context plus `mtfScore`. Both components read closed bars only, keep their own
session / HTF clocks, never draw, and journal every re-anchor, window change, CVD flip, replay
summary and HTF rebuild / turn / regime / structure event. Row 9 gains
` | <volume-flow clause> | <MTF clause>`, Row 10 gains the CVD and MTF flip precedence with the
combined `Watching — context only, no signal yet` line, and the profile window is a dynamic
lookback, so the single history gate is now `max(Supertrend, structure, volume flow)` —
302 / 377 / 402 candles in the worst case.

## Phase 6 — Signal and trade plan (implemented)

`Include/Emtt/Emtt_Signal.mqh` combines the four published views into one confidence figure
(weights 0.30 trend / 0.30 structure / 0.20 volume flow / 0.20 higher chart), gates it against the
market-mood bar with a 5-point stay margin, and runs the plan lifecycle with its result journal;
`Include/Emtt/Emtt_TradePlan.mqh` builds Entry, Stop, Target, Risk:Reward and Expected Duration
from the published readings and the matrix ATR only — never a typed-in price. The signal changes
only at a candle close, a plan's levels are fixed while it lasts, and no order is ever sent. Rows
2–8 fill for the first time: SIGNAL with ▲ / ▼ / ■, the confidence number, Entry / Stop / Take
Profit with `--` money parts, Risk:Reward and Expected Duration, and Row 10 carries the pending /
active / WAIT-reason / level-passed lines, each plan line ending `No order placed.` The LIVE TRADE
block stays hidden, the seven approved headers stay byte-identical, and the inputs are still
Magic number + Auto Trading.

## Phase 7 — Self-learning signal filter (implemented)

`Include/Emtt/Emtt_LearnFile.mqh` keeps one small ASCII record per symbol and timeframe
(`MQL5\Files\Emtt_Learning\<symbol>_<TF>.learn`, whole-file rewrite through a `.tmp` rename, cap
500, oldest closed ticket dropped first) holding one line per plan — its 16 published readings at
the start bar, its fixed levels and, once it resolves, its result. `Include/Emtt/Emtt_Learning.mqh`
turns those lines into a 16-feature logistic model: bias plus one weight per feature, one SGD step
per labeled ticket in file order at `0.30 / sqrt(k)`, weights clamped to ±4 and never stored,
recomputed from the tickets on every load. The learned term `L = clamp(2p - 1, ±1)` is live only
from the 30th labeled ticket; before that every number is exactly Phase 6, and the first warm candle
does not step the number. It can trim or support the four-view number by at most 15 % and can never
change the side. The record holds the open plan too, so a restart resumes the plan instead of losing
it: the closed candles since its start bar are checked against its own levels with the worse-result
order of 17.7, a candle that reached an end level ends the plan there, and a start bar that has
fallen out of the copied history ends it as `chart`. Row 3's number is the only reading that
changes; Row 10 gains `Watching — learning NN% holds this one back.` checked before the first 17.6
reason, the stay margin reads the adjusted number, and — per the author's 2026-10-11 decision — the
Row 9 learning clause is journal only, because the panel revamp retired that row. The Phase 8 ticket
extension adds broker fill/close times and signed net points; closed real trades train from net points,
while plans that were only watched retain Phase 7's paper target/stop label.

## Phase 8 — Live trading, management, and trade records (implemented)

`Emtt_Trade.mqh` contains pure safety, sizing, order-plan, target, trailing, time-exit, and news decisions; `Emtt_TradeManager.mqh` is the broker-facing lifecycle owner. Auto Trading is grouped with the new lot mode, margin-check, and initial-stop inputs and defaults to OFF. When enabled, orders still require the ordered terminal/account/market/live-position/spread/margin checks; sessions and news never block. The manager adopts Emtt positions, manages breakeven, TP1 partials, TP1/TP2 revisions, one-way trailing and profit-only time exits on closed candles, while ticks refresh only display data. The panel uses the existing LIVE TRADE block and live status fields. Learning records attach fill/close times and net points: real completed trades use their net result, open trades stay unlabeled, and unfilled plans retain paper target/stop labels. The author confirmed the live-terminal acceptance checks on a real MT5 demo chart on 2026-10-11 (recorded in `Emtt.md` section 22), and the portable gates were re-run on that tree: 404 unit tests passing, the compile smoke green over all 15 sources, and the parser gate exit `0` with `0 syntax errors` and every digest unchanged from delivery.

## Phase 9 — Parameter-optimization persistence (code delivered)

`Emtt_ParamOpt.mqh` and `Emtt_ParamFile.mqh` learn only the confidence bar, independently for the four moods and each symbol/timeframe, choosing one step within **60 / 70 / 75** after at least 20 accepted and 20 private near-miss results. The new **Parameter optimization** input defaults to ON directly below Magic number, above Auto Trading. Learned bars and tallies live in a six-line `.params` sibling beside `.learn`; it loads before replay and rewrites atomically at init, a move/held move, and deinit (§23.7). Tally-only changes remain in memory until the next write event. Changes apply on the next live closed candle, with the entry bar frozen while a position lives. Replay never collects evidence, near-misses never become signals/training rows/orders, and optional ticket `par` metadata is author-only. OFF preserves the Phase 8 gates/serialization and never touches `.params`. All eleven protected headers remain byte-identical. Delivery has 522 passing tests and syntax checks over all 17 sources; native MetaEditor compilation and MT5 demo acceptance remain pending in `Emtt.md` §24.

## Phase 10 — Tick-level CVD divergence for the trailing stop (code delivered)

`Emtt_TickDivergence.mqh` is pure logic. While an Emtt position is open, `OnTick` first refreshes the panel and then passes the latest `SymbolInfoTick` to the trade manager. Each tick gets a sign (+1 / −1 / 0) from its Bid/Ask moves and goes into a fixed 300-slot ring (15-minute cap) that keeps running `cvdNow` / `cvdAbs` sums, so each tick costs O(1). Swing highs and lows of strength 5 are detected incrementally on the mid price.

Divergence is evaluated only when all of these hold:

- breakeven has been reached;
- the 50-tick warmup is done;
- the feed is dense enough (at least 10 ticks per 60 s; after it goes sparse it switches back on at 20).

A new peak on the trade side that is at least 0.10 × the entry ATR beyond the previous one, with lower tick-CVD, is **weak** (0.8×). If the CVD is half or less, it is **strong** (0.5×). Either reading must hold for 3 ticks, and strong never drops back to weak. The reading resets when price pulls back with an opposite swing and then resumes, when the trailing stop moves, or when the leg leaves the window. Everything resets when the position closes or is adopted.

The only edit to `Emtt_Trade.mqh` is the `divergenceMult=1.0` argument, which multiplies the final trailing distance after the confidence, regime and news factors. The stop still only ever moves in the trade's favour. STATUS shows `Trailing — momentum fading/exhausted, tightening trail.` only after a divergence-driven trailing move, and the trailing journal line shows the extra factor. There is no new input, row, file, handle or GlobalVariable. Native MetaEditor compilation and MT5 demo acceptance are still pending in `Emtt.md` §26.

## Phase 11 — Graded confidence tiers and continuous signal display (code delivered)

Emtt now always shows its lean once the four views give a number. The new pure header `Emtt_Tier.mqh` grades the displayed confidence into five tiers:

| Confidence | SIGNAL row | Row 3 |
|---|---|---|
| below 35% | ■ WAIT, grey; Rows 4–8 `--` | `Confidence: 28% — Very low` |
| 35–45% | ▲ BUY / ▼ SELL, soft shade | `Confidence: NN% — Low confidence` |
| 46–55% | ▲ BUY / ▼ SELL, intermediate shade | `Confidence: NN% — Normal` |
| 56–70% | ▲ BUY / ▼ SELL, full colour | `Confidence: NN% — Confident` |
| 71%+ | ▲ BUY / ▼ SELL, full colour, bold | `Confidence: NN% — High confidence` |

`Confidence: --%` remains only while there is no number: history loading, market closed, incompatible chart. From 35% up, Rows 4–8 carry the unchanged 17.4 plan levels. The signal engine enters and keeps a plan at the fixed 35% floor. The mood bar and the Phase 9 learned bar stay internal: they still feed the journal, the `.params` near-miss logic and the ticket, but they no longer gate the display.

The new input **Auto-trade above (%)**, default 56, sits directly below Auto Trading ON/OFF. It takes whole numbers from 35 to 100 and clamps anything outside that range. An order is sent only when the displayed confidence reaches it and every Phase 8 safety gate passes. Market or pending orders still follow 21.6. A displayed tier below the threshold shows `Signal active — Low confidence BUY, watching (auto-trade threshold 56%).`, and below 35% STATUS reads `Watching — confidence 28% (Very low), no trade.` Lot size follows the tier: 0.7× / 1.0× / 1.2× / 1.5×.

`Emtt_Signal.mqh`, `Emtt_Trade.mqh` and `Emtt_Dashboard.mqh` change only through small listed edits. The smoke contract reverses those edits to the frozen hashes, so any other change fails. Phase 9's files and decision rule are untouched. Native MetaEditor compilation and MT5 demo acceptance are still pending in `Emtt.md` §29.

Run the portable checks with:

```sh
python -m unittest discover -s tests -v
python tools/mql5_compile_smoke.py
python tools/mql5_parser_check.py
```

The CI smoke check resolves the MQL5 include graph and validates source structure; if
`METAEDITOR_PATH` is configured it also invokes MetaEditor for a native compile.

The parser check is the Hard Rule 3 gate: it parses every MQL5 source with the real
[tree-sitter-mql5](https://github.com/mskelton/tree-sitter-mql5) grammar (pinned, cloned and
compiled into a cache directory on first use) and exits non-zero on any syntax error. It needs
`pip install tree-sitter`, `git` and a C/C++ compiler; without them it fails loudly rather than
passing silently. It proves syntax only — types, MQL5 built-in signatures and `PrintFormat`
specifiers still need MetaEditor.
