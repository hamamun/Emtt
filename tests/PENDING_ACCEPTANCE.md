# Pending lifecycle demo acceptance

Compile in MetaEditor first. Use a demo account and one EA controller per
symbol/magic. Do not deploy this lifecycle change straight to a live account.
The new input is Pending entry validity (1–96 bars), default 6.

## Policy tests (BUY and SELL)

- Place a valid block-limit setup. Check original timeframe, exact server-time
  expiry, broker SL/TP and native-vs-EA-only expiry in the Experts journal.
- Verify expiry is based on signal candle close, not attach time; delay
  qualification and verify the deadline does not move. A stale setup must not send.
- Use a short validity on demo; verify broker expiry where supported. For GTC
  fallback, keep MT5 online and verify cancellation. Test offline expiry only
  with broker-native expiry; EA-only orders cannot be guaranteed offline.
- Lower confidence below the configured auto-trade threshold on a closed bar:
  request cancellation even if still above 35%. A later rebound must not recreate
  the same block entry. A genuinely different block edge may qualify later.
- Cross target/stop before a fill, break the original block on a closed candle,
  and move the closed price beyond 2 ATR. Verify explicit cancellation reasons.
  Brief live-price excursions beyond 2 ATR alone must not trigger that rule.
- Disable Emtt's Auto Trading input: pending orders cancel, filled positions
  remain managed. Disable platform Algo Trading instead: panel must say that
  cancellation is waiting, NOT that the order was deleted.

## Recovery / broker authority

- Reattach, restart terminal and change inputs. Preserve original deadline,
  plan identity and cancellation intent; do not reset order age.
- Switch to another timeframe: no use of the new chart's confidence to validate
  the old order. Return within the 60-second grace and recover. Stay away longer
  and verify cancellation. Do not expect an old-TF background signal engine.
- Delay history/indicators for less than 60 seconds: do not cancel merely because
  confidence is temporarily unavailable. A hard expiry still wins during loading.
- With a pre-upgrade order/missing lease, verify bounded recovery then safe
  cancellation, not an invented new deadline. Verify an unrelated order price,
  side, account, or broker cannot bind to a saved lease.
- Make deletion fail, then restore permission/connectivity. Keep order tracked,
  retry no faster than every five seconds, and confirm actual broker removal.
- Trigger a fill during deletion: adopt/manage it; never report the filled
  volume as cancelled. Where the broker supports partial fills, cancel the
  unfilled remainder while preserving position volume, management and learning.
- Manually remove a pending order or let the broker expire it while disconnected.
  On reconnection reconcile history and do not re-submit the same block edge.
- Check actual broker-order/deal history, not only OHLC-based hypothetical plan
  messages. Unfilled deletion is not a position-loss event; hypothetical plan
  learning remains separate from real trade execution.

## Evidence for tuning (not completed by portable tests)

Collect order creation/expiry/cancel timestamps, reason, ATR distance, source
regime/timeframe, fills, slippage, and realized outcomes. Compare candidate
lifetimes on out-of-sample periods with realistic spreads and commissions.
Evaluate missed entries and stale fills, not just trade count or raw win rate.
