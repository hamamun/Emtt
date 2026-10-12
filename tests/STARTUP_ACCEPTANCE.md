# Closed-bar startup / timeframe-switch acceptance

The portable tests and parser do not replace a MetaEditor compile or a terminal test.
Use a demo account with Auto Trading OFF for the display checks.

1. Compile `Experts/Emtt.mq5` in MetaEditor and attach it to M5 mid-candle.
   Once chart/HTF history, ATR and a valid quote are ready, the panel should
   show the last closed candle's confidence without waiting for the open
   candle to close. Temporary loading is expected while data synchronizes.
2. Switch M5 -> M15 -> M30 -> M5 mid-candle. Each initialization must replay
   the new context, rather than taking the incremental path with reset
   component states. Look for `Parameters resolved` and replay summaries.
3. Repeat on a symbol/timeframe without cached HTF history. Until dependencies
   arrive the panel should say it is preparing closed-bar indicators / higher
   timeframe. It must recover on a timer tick even if no new candle closes.
4. For confidence below 35%, expect WAIT with the actual percentage/tier.
   For a >=35% setup rejected by stop/target safety rules, expect WAIT with
   the actual percentage/tier and its existing rejection reason. Do not
   expect a BUY/SELL merely because confidence exceeds 35%.
5. Reattach with an existing saved plan. Verify resume behavior and that
   delayed initialization does not create duplicate plan/learning records.
   Repeat with an existing demo position to check position adoption.
6. Confirm subsequent closed candles still advance normally; keep the EA
   running across a close and verify signal/learning events are not duplicated.

Implementation scope: shared foundation-bookkeeping reset at init/context
change; replay dependency guard before persistence and signal side effects;
confidence rendering independent of the plan-display gate; clearer loading
status. No confidence formulas, stop limits, auto-trade thresholds, tick-CVD
rules, broker-offset rules, or persisted file formats changed.
