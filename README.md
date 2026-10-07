# Emtt

MT5 Trading Expert Adviser — **Author:** Ham · **Coder:** Arena · Living specification: [`Emtt.md`](Emtt.md)

## Repository layout (mirrors the MT5 data folder)

| Repo path | MT5 data folder |
|---|---|
| `Experts/Emtt.mq5` | `MQL5\Experts\Emtt.mq5` |
| `Include/Emtt/*.mqh` | `MQL5\Include\Emtt\` |

Copy the folders into your MT5 data folder, open `Experts/Emtt.mq5` in MetaEditor and compile,
then attach **Emtt** to a chart. The EA includes its header with the quoted relative path
`../Include/Emtt/Emtt_Dashboard.mqh`, which resolves both in this checkout and inside the
terminal's data folder (spec §4a, §4b).

## Phase 1 — Layout (implemented)

Implements `Emtt.md` sections 4–8:

- **Panel A** (order open) and **Panel B** (no order) render exactly per §5, with dummy values.
- **Price Row** tracks the terminal's Bid / Ask / Spread in realtime; `►` marks the dealing
  side (BUY → Ask, SELL → Bid, WAIT → none) — §6 rule 2.
- **A/B switch:** input *Phase 1 demo panel switch* = `Auto` / `Panel A` / `Panel B`.
  `Auto` follows rule 8 — the LIVE TRADE block appears only while an Emtt position identified
  by the **Magic number** input (default `20251007`) is open.
- **Draggable** panel anchored top-left; 1-second timer refresh plus per-tick price updates
  (rule 14, 15).
- **M5 / M15 / M30 only** (rule 4d, 19): on any other timeframe the panel still draws in full,
  every data field shows `--`, the Price Row stays live, and the STATUS line shows
  `Incompatible chart. Switch to M5/M15/M30.` in red.
- **Clean removal:** all `Emtt_*` chart objects are deleted when the EA leaves the chart
  (Done-When item 4).
- Style per §6: `Segoe UI` (12pt rows, SIGNAL BUY/SELL 14pt), exact colour table, fixed panel
  width, WHY/STATUS text wrapping, no extra rows.

Later phases replace the dummy field values; the panel contract lives in
`SEmttPanelData` (`Include/Emtt/Emtt_Dashboard.mqh`).
