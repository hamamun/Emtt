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

Run the portable checks with:

```sh
python -m unittest discover -s tests -v
python tools/mql5_compile_smoke.py
```

The CI smoke check resolves the MQL5 include graph and validates source structure; if
`METAEDITOR_PATH` is configured it also invokes MetaEditor for a native compile.
