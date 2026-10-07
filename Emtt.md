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
