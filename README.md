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
