# Emtt discussion and continuation handoff

_Last reviewed: 2026-10-12. This document summarizes this conversation and the cumulative changes submitted with it. Read it before continuing in a new chat._

## 1. Repository / current state

- Repository: `hamamun/Emtt`.
- Working branch: `arena/0bd7bd00-emtt`.
- Starting main commit: `2053932c400f293e40825251411cc85061fb57c9`.
- Main EA: `Experts/Emtt.mq5`; custom modules: `Include/Emtt/`.
- Supported analysis timeframes: M5, M15, M30.
- Source `#property version` is still **1.90**. It was not bumped for these follow-up fixes; a version label alone does not identify the updated build. Compile the current source.
- Changes cover the description warning, startup/readiness, confidence rendering, execution validation, monetary estimates, and pending-order lifecycle.
- No pull request should be considered merged merely because it was opened. Check its actual GitHub status.

## 2. User's goals and working preference

The user is testing Emtt in a real MT5 terminal, sharing observations and Experts logs, and wants careful, logically justified improvements. They approved implementation after discussion, intend to keep posting results, and requested this file so a new chat can continue without losing context.

Avoid promising a perfect or profitable EA. Distinguish confirmed source behavior, likely causes, portable test coverage, and actual broker validation. Do not weaken risk checks or force market entries simply to produce more trades.

## 3. Discussion history and what was done

### A. MetaEditor description warning

User reported:

```text
description is too long    Emtt.mq5    21    11
0 errors, 1 warnings
```

Cause: combined `#property description` text exceeded MQL5's 511-character limit. The panel-revamp description became a source comment, preserving the note without putting it in compiled program metadata. The descriptions now total **494 characters including CRLF separators**. No strategy change was needed. `DealInfo.mqh` in the compiler listing was not itself the reported warning.

### B. Phase 10/11 observations: WAIT, confidence, and startup

User observed missing confidence during WAIT, a 36% reading that still showed WAIT, and apparent waiting for a new candle after M5/M15/M30 switches.

Relevant BTCUSDm log on 2026-10-12:

```text
Signal WAIT | confidence 36%, stop would be more than 3.0 ATR away
```

Conclusions:

- WAIT should retain a calculated confidence number and tier.
- The 35% Phase 11 floor does **not** override plan validity. A 36% setup can legitimately remain WAIT because stop/target/RR checks fail.
- The older logged regime threshold (e.g. 70%) is not the Phase 11 display threshold.
- Startup should use the most recently closed candle (shift 1), once dependencies are ready, without intentionally waiting for the forming candle to close.
- Logs after timeframe changes showed incomplete/different initialization sequences and a transient internal `confidence threshold 0%`; that is not a measured confidence of zero.

Implemented:

- Shared foundation-bookkeeping reset called on initialization and chart-context reset.
- Replay verifies component readiness, the latest closed candle, ATR, and a valid quote before loading persistent learning state and emitting signal events.
- An incomplete replay remains incomplete and retries through the timer, even without a new candle.
- Calculated confidence rendering is independent of the plan-display gate.
- Loading text distinguishes missing history from preparing indicators/higher-timeframe context.

The specific runtime race still needs MT5 acceptance testing. Portable checks alone do not establish the exact cause of every historical panel observation.

### C. Why no separate Indicators-folder files?

Explained to the user:

- Emtt creates MT5 built-in indicator handles for ATR, adaptive moving averages/KAMA, and Bollinger Bands, and reads their buffers.
- Custom Supertrend, structure/SMC, VWAP/profile/CVD, regime, MTF, and tick-divergence calculations reside in `.mqh` modules compiled into the EA.
- They need not be attached visibly to the chart or installed as separate custom indicator programs.
- Earlier Predict_x/other EA source was not available here; no definitive claim was made about those implementations. A separate-indicator design commonly uses `iCustom()`.

No code change was made just for that explanation.

### D. 60% ETH BUY placed a limit order; entry missed

The user supplied ETHUSDm M30 logs from 2026-10-12 around 12:37 terminal time, evaluating the 06:00 server-time candle:

```text
Supertrend: bullish, score 0.96
Volume flow: CVD --, score 0.00
Structure: bias up, Premium, OB 2544.31, score 0.58
H4 context: score 0.70 after an earlier startup log of 0.10
Signal BUY | confidence 60% (Confident) | Ranging, bar 70%
Plan BUY | entry 2544.31 (order block edge)
         | stop 2524.81 | target 2588.04 (VAH) | RR 1:2.2
         | expected ~5-16 hours | spread 100 pts
Order BUY | pending limit 2544.31 | lots 0.80 | GTC
```

Analysis:

- Confidence is a weighted signal score, **not a calibrated probability of winning**.
- Approximately `0.96*0.30 + 0.58*0.30 + 0*0.20 + 0.70*0.20 = 0.602`, consistent with 60% BUY.
- Volume flow contributed no positive confirmation; not every factor agreed.
- Learning was warming at 0/30, not an established learned success model.
- Existing planner prefers an aligned order-block edge on the retracement side within 2 ATR of the closed price; otherwise it starts with a market-price entry.
- Execution chooses Buy Limit below current Ask / Sell Limit above current Bid for a block entry; otherwise market execution. Confidence alone does not choose order type.
- Risk `19.50`, reward `43.73`, RR about `2.24`, so the logged 1:2.2 is consistent.
- A missed pullback does not prove a bad entry calculation. The excerpt lacked ATR and the live submission quote, preventing precise distance validation.

Agreed direction: do not automatically chase a missed pullback or turn a 60% score into a mandatory market order. Revalidate executable geometry and make order details observable instead.

### E. Execution checks and monetary display

Implemented new-submission checks against executable price/current closed-bar ATR:

- Pending entry distance <=2 ATR from the live dealing price.
- Stop and target on the proper side of execution price.
- Stop distance within the existing 1–3 ATR bounds.
- RR meets the existing regime minimum.
- Market-order lot sizing uses the execution quote rather than the older plan entry.
- New submissions also require ready analysis, connectivity, EA/platform trade permission as applicable, and a fresh quote.

Money-display correction: the initial explanation that all money fields were unfinished was too broad. Filled positions already had a monetary-display path. Pending orders and signal-only plans were the missing cases.

Current behavior:

- Signal-only preview uses proposed lot size.
- Pending display uses broker order volume/entry.
- Position display uses actual fill and remaining volume.
- `OrderCalcProfit()` provides account-currency estimates; failures remain `--`, not invented zeroes.
- Entry amount is labeled **gap**, the monetary equivalent of price distance—not margin or floating profit.
- SL/TP estimates use displayed planned levels, excluding commissions, swap, gaps and slippage.
- A planned SL is not proof of a broker-installed SL. Pending protection reads the actual broker SL and says `not set` when absent.
- `InpPlaceStopLoss=false` remains the default. It was not silently changed.

### F. Pending-order discussion: original rules versus revised rules

Originally, orders were GTC with no dedicated deadline. Existing plan lifecycle could cancel on direction/plan changes, confidence below the 35% display-retention floor, market closure and some context mismatches. Target/stop touches were also handled indirectly through closed-candle hypothetical plan logic; the first conversational summary omitted those checks and was later corrected.

Weaknesses discussed:

- An order could stay executable below the user's auto-trade threshold.
- Entry validity was not separate from expected trade duration.
- No persistent pending deadline or offline broker expiry.
- Temporary unavailable data could be confused with invalidation.
- `OrderDelete()` boolean alone was treated as confirmation.
- Missing reconciliation for partial fills and cancel/fill races.
- Cancellation could be followed by re-creation of the same stale setup.

The user approved a lifecycle implementation rather than leaving these as suggestions.

## 4. Current pending-order policy (this supersedes earlier chat descriptions)

### Lifetime

- New input: `InpPendingValidityBars=6`, clamped to **1–96**.
- Default: M5 30 minutes; M15 90 minutes; M30 3 hours.
- Deadline is anchored to **originating signal candle close**, not order-submission or restart time.
- Cap by the setup's upper expected duration when available.
- A setup qualifying late does not receive a fresh lifetime; an already-expired one is not submitted.
- Six bars is a conservative starting configuration, **not a backtested optimum**.

### Broker expiration

- Prefer `ORDER_TIME_SPECIFIED` when supported by the symbol.
- Otherwise permit GTC only if supported, with explicit **EA-only expiry / keep MT5 online** warnings.
- Reject unsupported expiration arrangements rather than silently weakening the policy.
- Do not silently retry a broker-rejected native-expiry request as GTC.
- Neither timer-driven cancellation nor EA-only expiry can work while disconnected or without required trading permission.

### Cancellation conditions

- Partial fill: cancel the unfilled remainder; manage the filled position.
- Emtt Auto Trading input OFF: request removal of owned pending orders, continue position management.
- Deadline reached.
- Confirmed market closure.
- Target or stop invalidation using fresh liquidation-side quotes (Bid for BUY, Ask for SELL).
- Originating signal identity/direction no longer matches.
- Confidence below the configured **auto-trade threshold**, not merely below 35%.
- Closed price invalidates the captured original order-block far edge.
- Closed price moves more than 2 current ATR away on the unfilled retracement side.
- Original setup cannot be validated within the recovery grace.

Confidence/structure/distance use closed data. Quote-level invalidation is polled on the one-second timer, not guaranteed to preempt every intratick fill. Cancellation intent is sticky; a rebound does not undo an invalidation already acted on.

### Recovery and timeframe changes

- Preserve original timeframe, plan timestamp, levels, block edge, ATR, deadline and cancellation intent.
- Do not use the new chart's confidence to validate an old-timeframe order.
- Allow **60 seconds** to recover original analysis. If it remains unavailable, request cancellation.
- Returning to the originating timeframe within grace permits recovery if the setup remains valid.
- No separate background signal engine was added for the old timeframe.
- Ordinary startup loading receives grace, but expiry, Auto Trading OFF and partial-fill cleanup do not wait for it.
- Pre-upgrade orders without trustworthy metadata can be cancelled after bounded recovery; they are not granted an invented new lifetime.

### Persistence and duplicate prevention

- Local MT5 terminal globals hold an execution lease, namespaced by broker server/account/symbol/magic.
- A valid marker is written last and flushed before submission. Receipt information is added after acceptance, with a narrow setup-time/price recovery path for a crash before receipt storage.
- A submitted order-block edge/side/timeframe is retired before sending. Same-edge replay/restart must not recreate that execution attempt.
- A different block edge can qualify as a fresh opportunity. Confirmed submission failures also remain retired; this intentionally favors safety over automatic retry.
- Terminal globals are local to the installation/test environment, have MT5 retention rules, and do not automatically migrate to another VPS/terminal.
- Use **one controlling Emtt instance per symbol/magic**. The existing one-owned-trade model and single lease are not a multi-controller coordination system.

### Broker authority and outcomes

- Inspect delete return code, live order state and terminal order history.
- Missing order-list entry alone is not proof of cancellation; retain unresolved state until history establishes the outcome.
- Retry at most once every **5 seconds**.
- If fill wins the deletion race, adopt/manage the position instead of labelling it safely cancelled.
- Disconnected observations are not treated as confirmed lifecycle events.
- Cancellation/expiry itself does not fabricate a trade fill, trade close or realized loss.
- **Important limitation:** pre-existing hypothetical signal-plan learning/statistics remain candle-based and separate from actual broker execution. They can still label hypothetical outcomes. This work does not turn the Summary/learning system into a broker-only ledger. Future audits must keep that distinction explicit.

### UI

- Expose a **LIVE TRADE — PENDING** block even without a filled position, superseding the old position-only block visibility.
- Show broker order volume/entry, no fictitious pending floating P/L, actual broker SL, remaining entry validity, broker-versus-EA expiry, expected trade duration, and recovery/cancellation status.
- Filled-position exit/management rules and Phase 10 tick-divergence formulas were not redesigned.

## 5. Files and implementation map

| File | Purpose / changes |
|---|---|
| `Experts/Emtt.mq5` | Metadata warning; startup reset/readiness; WAIT confidence; preview money; runtime readiness/quote flags; pending-validity input |
| `Include/Emtt/Emtt_TradeManager.mqh` | Executable geometry validation, quote-based sizing, estimates, persistence/recovery, broker expiry, cancellation reconciliation and pending display |
| `Include/Emtt/Emtt_Pending.mqh` | New pure policy, deadline/clamp functions, cancellation-reason enum/text |
| `Emtt.md` | Follow-up specification and explicit superseding policy/limitations |
| `tests/test_startup_readiness.py` | Startup/source-contract regressions |
| `tests/test_execution_estimates.py` | Production helper harnesses with stubbed broker profit calculations |
| `tests/test_pending_lifecycle.py` | Production policy/lease/cancellation C++ harnesses and wiring checks |
| `tests/phase8_reference.py`, `tests/test_phase8_reference.py` | Updated pending protection-block visibility expectations |
| `tests/test_phase11_reference.py` | Updated input count for the pending-validity follow-up |
| `tools/mql5_compile_smoke.py` | Updated input/lease boundaries; pure pending-policy checks; retained learning-file protections |
| `tests/STARTUP_ACCEPTANCE.md` | MT5 startup/timeframe-change checklist |
| `tests/PENDING_ACCEPTANCE.md` | Broker/demo lifecycle and tuning checklist |
| `discussion.md` | This handoff |

The `.learn`/`.params` file formats, confidence formulas, original plan-builder formulas, broker-offset rules, indicator calculations and Phase 10 divergence formulas were not changed by these fixes.

## 6. Review / validation status

Re-run during the final review on 2026-10-12:

```sh
python -m unittest discover -s tests
python tools/mql5_compile_smoke.py
python tools/mql5_parser_check.py
git diff --check
```

Results:

- **609 tests passed**.
- Structural/include smoke checks passed.
- **20 MQL source files parsed, zero syntax errors**.
- Diff whitespace check passed.
- Combined description length checked at **494/511 characters**.

The parser requires `tree-sitter`; it was run using an external workspace virtual environment, not a committed dependency directory. C++ helper tests require `g++`; they execute production-compatible helpers with broker APIs stubbed. They are not a real MT5 runtime.

**Not performed here:** actual MetaEditor compilation, broker order placement, live/demo partial-fill/cancel races, historical execution backtesting, or proof of profitability. No new `.ex5` was produced here. Compile current sources in MetaEditor and perform the acceptance checklists on demo before live deployment.

## 7. Open questions / next chat priorities

1. Obtain the new MetaEditor compile log and resolve any actual MQL type/API warnings or errors. Syntax parsing is not a substitute.
2. Confirm startup confidence on M5 -> M15 -> M30 without waiting for the forming candle to close.
3. Confirm pending expiry, original-timeframe recovery, Auto Trading OFF behavior, native/GTC support, and no same-edge re-submission on demo.
4. Verify order deletion failures, manual deletion, offline broker expiry, partial fills and cancel/fill races against broker order/deal history, not only chart candles.
5. Verify money rows with the broker's contract specifications and account currency, including partial closes and unavailable profit-calculation data.
6. Investigate original `Broker GMT offset initialized: +0 minutes` against broker server time/UTC. The difference between journal timestamps and candle timestamps alone does not establish an offset bug. No offset change was made.
7. Investigate repeated startup H4 scores (0.10 then 0.70 for the same bar) with full context. Changing chart-context agreement is a plausible explanation, not proof of correctness. No dedicated score-diagnostic fix was made.
8. Phase 10 divergence/trailing performance was **not established** by the supplied flat/pending-order logs. Collect actual managed-position events.
9. Tune pending lifetime and distance policies using out-of-sample data, realistic spreads/commissions/slippage, missed fills and stale-fill outcomes. Six bars is only the initial setting.
10. If the user wants strictly broker-only statistics, review the hypothetical plan learning/Summary path separately rather than assuming this lifecycle patch already converted it.

Useful evidence to request next: complete Experts/Journal excerpts around the issue, symbol/timeframe, EA inputs, account currency, current Bid/Ask and spread, broker order ticket/state/SL/TP/expiration, panel screenshot, and whether MT5 connectivity/Algo Trading were enabled. Do not request account credentials.

## 8. Suggested next-chat starting prompt

> Read discussion.md, Emtt.md's latest follow-up sections, and the acceptance checklists. Review the current PR/branch state. Continue from the pending-lifecycle implementation, using my new MT5 logs to distinguish a code defect, a configured safety gate, a temporary loading state, and broker execution behavior. Do not assume MetaEditor/demo verification or lifetime optimization has already been completed.
