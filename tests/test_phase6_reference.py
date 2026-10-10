"""Portable tests for Emtt Phase 6 (Emtt.md 17.2-17.8, scope of 17.9).

Everything asserted here runs against ``phase6_reference`` with no MT5
dependency, so the exact Phase 6 rules are exercised on every CI platform.
"""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta

from phase2_reference import BEAR, BULL, RANGING, TRANSITION, VOLATILE
from phase6_reference import (
    ARROW_GLYPH,
    BUY_GLYPH,
    DASH,
    PLAN_ACTIVE,
    PLAN_PENDING,
    PLAN_RR_OTHER,
    PLAN_RR_TREND,
    SELL_GLYPH,
    SIG_WEIGHT_FLOW,
    SIG_WEIGHT_HTF,
    SIG_WEIGHT_STRUCTURE,
    SIG_WEIGHT_TREND,
    WAIT_GLYPH,
    Candle,
    FlowView,
    HtfView,
    SignalTracker,
    StructureView,
    TrendView,
    build_plan,
    combine_views,
    confidence_number,
    format_duration,
    min_risk_reward,
    mood_bar,
    panel_rows,
    price_row,
    status_text,
    wait_text,
)

#--- shared fixture ------------------------------------------------------
# A 5-digit symbol: point 0.00001, one ATR = 0.00100 = 100 points. The
# standard BUY plan enters at the Ask; every level below is exact.
POINT = 0.00001
DIGITS = 5
ATR = 0.00100
CLOSE = 1.09000
BID = 1.08990
ASK = 1.09010
SPREAD_PTS = 2
T0 = datetime(2026, 10, 9, 14, 30)

SWING_LOW = ASK - 2.0 * ATR     # 1.08810
PLAN_STOP = ASK - 2.5 * ATR     # 1.08760, the swing low - 0.5 ATR
GAP_ABOVE = ASK + 4.0 * ATR     # 1.09410, RR 1.6
POOL_BUY = ASK + 7.0 * ATR
POC = ASK + 5.0 * ATR
VAH = ASK + 6.0 * ATR
VAL = ASK - 1.0 * ATR           # below the entry: never a BUY target
NAKED_POC = ASK + 8.0 * ATR
PLAN_TARGET = GAP_ABOVE

# The SELL mirror: the plan enters at the Bid.
SELL_SWING_HIGH = BID + 2.0 * ATR
SELL_STOP = BID + 2.5 * ATR
SELL_GAP = BID - 4.0 * ATR       # RR 1.6
SELL_POOL = BID - 7.0 * ATR
SELL_POC = BID - 5.0 * ATR
SELL_VAH = BID - 4.5 * ATR
SELL_VAL = BID + 1.0 * ATR
SELL_NAKED = BID - 8.0 * ATR


def trend_view(direction=1, score=0.72, bars_since_flip=4, distance_atrs=1.2,
               ready=True):
    return TrendView(ready=ready, direction=direction, score=score,
                     bars_since_flip=bars_since_flip, distance_atrs=distance_atrs)


def structure_view(**over):
    values = dict(
        ready=True, bias=1, score=0.72,
        has_swing_low=True, newest_low_level=SWING_LOW,
        has_swing_high=False, newest_high_level=0.0,
        has_gap_above=True, gap_above_near_edge=GAP_ABOVE,
        has_gap_below=False, gap_below_near_edge=0.0,
        has_buy_pool=True, buy_pool_level=POOL_BUY,
        has_sell_pool=False, sell_pool_level=0.0,
        has_order_block=False, order_block_bullish=True,
        order_block_near_edge=0.0, order_block_low=0.0, order_block_high=0.0,
    )
    values.update(over)
    return StructureView(**values)


def flow_view(**over):
    values = dict(
        ready=True, flow_direction=1, score=0.72,
        has_profile=True, poc=POC, vah=VAH, val=VAL,
        prior_poc_available=True, prior_poc_naked=True, prior_poc=NAKED_POC,
    )
    values.update(over)
    return FlowView(**values)


def sell_structure(**over):
    values = dict(
        ready=True, bias=-1, score=0.72,
        has_swing_low=False, newest_low_level=0.0,
        has_swing_high=True, newest_high_level=SELL_SWING_HIGH,
        has_gap_above=False, gap_above_near_edge=0.0,
        has_gap_below=True, gap_below_near_edge=SELL_GAP,
        has_buy_pool=False, buy_pool_level=0.0,
        has_sell_pool=True, sell_pool_level=SELL_POOL,
        has_order_block=False, order_block_bullish=False,
        order_block_near_edge=0.0, order_block_low=0.0, order_block_high=0.0,
    )
    values.update(over)
    return StructureView(**values)


def sell_flow(**over):
    values = dict(
        ready=True, flow_direction=-1, score=0.72,
        has_profile=True, poc=SELL_POC, vah=SELL_VAH, val=SELL_VAL,
        prior_poc_available=True, prior_poc_naked=True, prior_poc=SELL_NAKED,
    )
    values.update(over)
    return FlowView(**values)


def htf_view(**over):
    values = dict(ready=True, direction=1, score=0.72)
    values.update(over)
    return HtfView(**values)


def aligned_views(score=0.72, direction=1):
    """Four views aligned on one direction: S equals the shared score."""
    return (
        trend_view(direction=direction, score=score),
        structure_view(score=score, bias=direction),
        flow_view(score=score, flow_direction=direction),
        htf_view(direction=direction, score=score),
    )


def step(tracker, high, low, close, *, score=0.72, mood=BULL, direction=1,
         seq=0, bid=BID, ask=ASK, atr=ATR, spread_pts=SPREAD_PTS,
         bar_time=None, trend=None, structure=None, flow=None, htf=None,
         journaling=True, timeframe="M15", digits=DIGITS, point=POINT):
    if trend is None:
        trend = trend_view(direction=direction, score=score)
    if structure is None:
        structure = (structure_view(score=score) if direction > 0
                     else sell_structure(score=score))
    if flow is None:
        flow = flow_view(score=score) if direction > 0 else sell_flow(score=score)
    if htf is None:
        htf = htf_view(direction=direction, score=score)
    tracker.advance(
        trend=trend, structure=structure, flow=flow, htf=htf, mood=mood,
        atr=atr, candle=Candle(high=high, low=low, close=close), bid=bid,
        ask=ask, spread_pts=spread_pts, timeframe=timeframe, sequence=seq,
        bar_time=bar_time if bar_time is not None else T0, digits=digits,
        point=point, journaling=journaling,
    )


def start_buy(tracker, *, score=0.72, mood=BULL, seq=0, close=CLOSE, ask=ASK,
              bid=BID, **over):
    """Run one closed candle that should start a BUY plan."""
    step(tracker, high=close + 0.0002, low=close - 0.0002, close=close,
         score=score, mood=mood, direction=1, seq=seq, ask=ask, bid=bid, **over)
    return tracker.state


def start_sell(tracker, *, score=0.72, mood=BULL, seq=0, close=CLOSE, **over):
    """Run one closed candle that should start a SELL plan."""
    step(tracker, high=close + 0.0002, low=close - 0.0002, close=close,
         score=score, mood=mood, direction=-1, seq=seq,
         structure=sell_structure(score=score), flow=sell_flow(score=score),
         htf=htf_view(direction=-1, score=score), **over)
    return tracker.state


def result_lines(tracker):
    return [line for line in tracker.state.journal if " result | " in line]


#--- 17.3 combination ----------------------------------------------------


class TestCombination(unittest.TestCase):
    def test_weights_sum_to_exactly_one(self):
        self.assertEqual(
            SIG_WEIGHT_TREND + SIG_WEIGHT_STRUCTURE + SIG_WEIGHT_FLOW
            + SIG_WEIGHT_HTF,
            1.0,
        )

    def test_combined_stays_between_minus_one_and_one(self):
        for score in (1.0, 0.5, 0.0):
            for direction in (1, -1):
                trend, structure, flow, htf = aligned_views(score, direction)
                value = combine_views(trend, structure, flow, htf)
                self.assertGreaterEqual(value, -1.0)
                self.assertLessEqual(value, 1.0)
        trend, structure, flow, htf = aligned_views(1.0, 1)
        self.assertAlmostEqual(combine_views(trend, structure, flow, htf), 1.0)
        trend, structure, flow, htf = aligned_views(1.0, -1)
        self.assertAlmostEqual(combine_views(trend, structure, flow, htf), -1.0)

    def test_flat_view_adds_nothing(self):
        trend, structure, flow, htf = aligned_views(0.6, 1)
        flat = replace(trend, direction=0, score=1.0)
        # A flat view contributes nothing whatever its score...
        self.assertAlmostEqual(
            combine_views(flat, structure, flow, htf),
            combine_views(replace(trend, direction=0, score=0.0),
                          structure, flow, htf),
        )
        # ...exactly the sum of the other three views.
        self.assertAlmostEqual(
            combine_views(flat, structure, flow, htf),
            SIG_WEIGHT_STRUCTURE * 0.6 + SIG_WEIGHT_FLOW * 0.6
            + SIG_WEIGHT_HTF * 0.6,
        )

    def test_opposing_view_lowers_the_number(self):
        trend, structure, flow, htf = aligned_views(0.6, 1)
        before = combine_views(trend, structure, flow, htf)
        after = combine_views(trend, structure, flow,
                              replace(htf, direction=-1))
        self.assertLess(after, before)

    def test_row3_rounds_halves_up(self):
        self.assertEqual(confidence_number(0.665), 67)   # 66.5 -> 67
        self.assertEqual(confidence_number(0.664), 66)
        self.assertEqual(confidence_number(-0.665), 67)
        self.assertEqual(confidence_number(0.0), 0)
        self.assertEqual(confidence_number(1.0), 100)


#--- 17.3 the gate --------------------------------------------------------


class TestGate(unittest.TestCase):
    def test_mood_bar_mapping(self):
        self.assertEqual(mood_bar(BULL), 60)
        self.assertEqual(mood_bar(BEAR), 60)
        self.assertEqual(mood_bar(RANGING), 70)
        self.assertEqual(mood_bar(VOLATILE), 70)
        self.assertEqual(mood_bar(TRANSITION), 75)

    def test_entry_needs_the_bar(self):
        tracker = SignalTracker()
        state = start_buy(tracker, score=0.59)   # 59 < 60
        self.assertEqual(state.signal, 0)
        self.assertEqual(state.confidence, 59)
        tracker = SignalTracker()
        state = start_buy(tracker, score=0.60)   # 60 >= 60
        self.assertEqual(state.signal, 1)

    def test_the_comparison_uses_the_whole_number(self):
        # 0.5951 x 100 = 59.51 rounds up to 60: the bar is met on the
        # shown whole number even though the raw figure is below it.
        tracker = SignalTracker()
        state = start_buy(tracker, score=0.5951)
        self.assertEqual(state.confidence, 60)
        self.assertEqual(state.signal, 1)

    def test_staying_needs_bar_minus_five(self):
        tracker = SignalTracker()
        state = start_buy(tracker, score=0.62, seq=0)
        self.assertEqual(state.signal, 1)
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.61,
             seq=1)                                   # 61 >= 55: stays
        self.assertEqual(tracker.state.signal, 1)
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.55,
             seq=2)                                   # 55 >= 55: still stays
        self.assertEqual(tracker.state.signal, 1)
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.54,
             seq=3)                                   # 54 < 55: ends at once
        self.assertEqual(tracker.state.signal, 0)
        self.assertFalse(tracker.state.plan.active)

    def test_one_candle_can_flip_the_signal(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        self.assertEqual(tracker.state.signal, 1)
        # The very next candle points the other way at full strength.
        step(tracker, high=CLOSE + 0.0002, low=CLOSE - 0.0002, close=CLOSE,
             score=0.72, direction=-1, seq=1)
        state = tracker.state
        self.assertEqual(state.signal, 0)          # WAIT on the flip candle
        self.assertFalse(state.plan.active)
        self.assertTrue(state.just_ended)
        self.assertEqual(
            result_lines(tracker),
            [f"Emtt | Plan BUY result | signal changed | exit {CLOSE:.5f} | "
             f"-10 pts | 1 candles | bar 2026.10.09 14:30"],
        )
        # The next candle can start the other side at once.
        start_sell(tracker, score=0.72, seq=2)
        self.assertEqual(tracker.state.signal, -1)

    def test_mood_change_moves_the_bar_at_the_next_candle(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.62, mood=BULL, seq=0)   # bar 60, keep 55
        self.assertEqual(tracker.state.signal, 1)
        # TRANSITION raises the bar to 75, so keeping needs 70.
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE,
             score=0.62, mood=TRANSITION, seq=1)
        state = tracker.state
        self.assertEqual(state.signal, 0)
        self.assertEqual(
            wait_text(state),
            f"Watching {DASH} confidence 62%, below the 70% level that keeps a BUY.",
        )


#--- 17.4 entry -----------------------------------------------------------


class TestEntry(unittest.TestCase):
    def build(self, side, structure, **over):
        return build_plan(
            side, structure, flow_view(), trend_view(), ATR, CLOSE, BID, ASK,
            over.pop("mood", BULL), over.pop("timeframe", "M15"),
        )[0]

    def test_block_within_reach_gives_its_near_edge(self):
        # Bullish block: near edge (zoneHigh) 1.0 ATR below the close.
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 1.5 * ATR,
            order_block_high=CLOSE - ATR,
        )
        plan = self.build(1, structure)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.entry, CLOSE - ATR)
        self.assertEqual(plan.entry_kind, "block")
        self.assertEqual(plan.entry_source, "order block edge")
        self.assertEqual(plan.status, PLAN_PENDING)

    def test_block_at_the_reach_limit_is_used(self):
        # One point inside the 2.0 ATR reach: the block edge is the Entry.
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - 2.0 * ATR + POINT,
            order_block_low=CLOSE - 2.5 * ATR,
            order_block_high=CLOSE - 2.0 * ATR + POINT,
        )
        plan = self.build(1, structure)
        self.assertEqual(plan.entry, CLOSE - 2.0 * ATR + POINT)
        self.assertEqual(plan.entry_kind, "block")

    def test_block_too_far_gives_the_market_price(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - 2.0 * ATR - POINT,
            order_block_low=CLOSE - 2.5 * ATR,
            order_block_high=CLOSE - 2.0 * ATR,
        )
        plan = self.build(1, structure)
        self.assertEqual(plan.entry, ASK)
        self.assertEqual(plan.entry_kind, "market")

    def test_price_inside_the_block_gives_the_market_price(self):
        # The near edge is at the close: distance 0, not "more than 0".
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE, order_block_low=CLOSE - ATR,
            order_block_high=CLOSE,
        )
        plan = self.build(1, structure)
        self.assertEqual(plan.entry, ASK)

    def test_block_the_other_way_gives_the_market_price(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=False, bias=-1,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - ATR,
            order_block_high=CLOSE - 0.5 * ATR,
        )
        plan = self.build(1, structure)
        self.assertEqual(plan.entry, ASK)

    def test_no_block_gives_the_market_price(self):
        plan = self.build(1, structure_view())
        self.assertEqual(plan.entry, ASK)
        self.assertEqual(plan.entry_kind, "market")
        self.assertEqual(plan.status, PLAN_ACTIVE)

    def test_sell_mirror_uses_the_bid_and_the_block_low(self):
        structure = sell_structure(
            has_order_block=True, order_block_bullish=False,
            order_block_near_edge=CLOSE + ATR, order_block_low=CLOSE + ATR,
            order_block_high=CLOSE + 1.5 * ATR,
        )
        plan, fail = build_plan(-1, structure, sell_flow(),
                                trend_view(direction=-1), ATR, CLOSE,
                                BID, ASK, BULL, "M15")
        self.assertEqual(fail, "")
        self.assertEqual(plan.entry, CLOSE + ATR)     # the block's near edge
        self.assertEqual(plan.entry_kind, "block")
        # Stop: the further of the swing high and the block's far edge.
        self.assertEqual(plan.stop, SELL_SWING_HIGH + 0.5 * ATR)
        self.assertEqual(plan.stop_source, "swing high")
        self.assertEqual(plan.target, SELL_GAP)
        self.assertEqual(plan.target_source, "fair value gap")


#--- 17.4 stop ------------------------------------------------------------


class TestStop(unittest.TestCase):
    def build(self, side, structure, **over):
        return build_plan(
            side, structure, flow_view(), trend_view(), ATR, CLOSE, BID, ASK,
            over.pop("mood", BULL), over.pop("timeframe", "M15"),
        )

    def test_swing_low_is_the_reference_and_gets_the_buffer(self):
        plan, fail = self.build(1, structure_view())
        self.assertEqual(fail, "")
        self.assertEqual(plan.stop, SWING_LOW - 0.5 * ATR)
        self.assertEqual(plan.stop_source, "swing low")

    def test_only_candidates_below_entry_are_used(self):
        # A swing low above the entry is not a stop candidate.
        structure = structure_view(newest_low_level=CLOSE + ATR)
        plan, fail = self.build(1, structure)
        self.assertIsNone(plan)
        self.assertEqual(fail, "no_swing")

    def test_the_further_candidate_is_the_reference(self):
        # Block entry: the block's far edge is below the swing low.
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 2.6 * ATR,
            order_block_high=CLOSE - ATR,
        )
        plan, fail = self.build(1, structure)
        self.assertEqual(fail, "")
        self.assertEqual(plan.stop_source, "order block edge")
        self.assertEqual(plan.stop, (CLOSE - 2.6 * ATR) - 0.5 * ATR)

    def test_a_single_candidate_is_used_alone(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 1.6 * ATR,
            order_block_high=CLOSE - ATR, has_swing_low=False,
        )
        plan, fail = self.build(1, structure)
        self.assertEqual(fail, "")
        self.assertEqual(plan.stop_source, "order block edge")
        self.assertEqual(plan.stop, (CLOSE - 1.6 * ATR) - 0.5 * ATR)

    def test_no_candidate_gives_wait(self):
        plan, fail = self.build(1, structure_view(has_swing_low=False))
        self.assertIsNone(plan)
        self.assertEqual(fail, "no_swing")

    def test_stop_widens_out_to_one_atr(self):
        # Swing low 0.3 ATR below the entry: the buffered stop would be
        # 0.8 ATR away, so it moves out to exactly 1.0 ATR.
        structure = structure_view(newest_low_level=ASK - 0.3 * ATR)
        plan, fail = self.build(1, structure)
        self.assertEqual(fail, "")
        self.assertEqual(plan.stop, ASK - 1.0 * ATR)

    def test_stop_beyond_three_atr_is_skipped(self):
        # entry - swing = 2.6 ATR -> stop distance 3.1 ATR > 3.0 ATR.
        structure = structure_view(newest_low_level=ASK - 2.6 * ATR)
        plan, fail = self.build(1, structure)
        self.assertIsNone(plan)
        self.assertEqual(fail, "stop_far")

    def test_stop_exactly_three_atr_is_kept(self):
        structure = structure_view(newest_low_level=PLAN_STOP)
        plan, fail = self.build(1, structure)
        self.assertEqual(fail, "")
        self.assertEqual(plan.stop, ASK - 3.0 * ATR)

    def test_sell_mirror(self):
        plan, fail = self.build(-1, sell_structure())
        self.assertEqual(fail, "")
        self.assertEqual(plan.stop, SELL_SWING_HIGH + 0.5 * ATR)
        self.assertEqual(plan.stop_source, "swing high")


#--- 17.4 target ----------------------------------------------------------


class TestTarget(unittest.TestCase):
    def build(self, side, structure, flow=None, mood=BULL):
        return build_plan(side, structure, flow or flow_view(),
                          trend_view(), ATR, CLOSE, BID, ASK, mood, "M15")

    def test_the_nearest_candidate_meeting_the_minimum_wins(self):
        # The gap (RR 1.6) is the nearest candidate that meets 1.5.
        plan, fail = self.build(1, structure_view())
        self.assertEqual(fail, "")
        self.assertEqual(plan.target, GAP_ABOVE)
        self.assertEqual(plan.target_source, "fair value gap")

    def test_candidates_below_the_minimum_are_skipped(self):
        # A gap 1.2 ATR above the entry gives RR 0.48: skipped.
        structure = structure_view(
            has_gap_above=True, gap_above_near_edge=ASK + 1.2 * ATR,
            has_buy_pool=False,
        )
        flow = flow_view(has_profile=False, prior_poc_available=False)
        plan, fail = self.build(1, structure, flow)
        self.assertIsNone(plan)
        self.assertEqual(fail, "no_target")

    def test_none_meeting_the_minimum_gives_wait(self):
        structure = structure_view(has_gap_above=False, has_buy_pool=False)
        flow = flow_view(has_profile=False, prior_poc_available=False)
        plan, fail = self.build(1, structure, flow)
        self.assertIsNone(plan)
        self.assertEqual(fail, "no_target")

    def test_equal_prices_keep_the_documented_order(self):
        # Gap, pool, POC, VAH, VAL and naked POC all at the same price.
        level = ASK + 4.0 * ATR
        flow = flow_view(poc=level, vah=level, val=level, prior_poc=level)
        structure = structure_view(
            has_gap_above=True, gap_above_near_edge=level,
            has_buy_pool=True, buy_pool_level=level,
        )
        plan, fail = self.build(1, structure, flow)
        self.assertEqual(plan.target, level)
        self.assertEqual(plan.target_source, "fair value gap")
        # Without the gap, the pool wins the same tie.
        structure = structure_view(has_gap_above=False, has_buy_pool=True,
                                   buy_pool_level=level)
        plan, _ = self.build(1, structure, flow)
        self.assertEqual(plan.target_source, "buy-side pool")
        # Without the pool, the POC wins.
        structure = structure_view(has_gap_above=False, has_buy_pool=False)
        plan, _ = self.build(1, structure, flow)
        self.assertEqual(plan.target_source, "POC")

    def test_naked_poc_is_a_candidate_only_while_naked(self):
        flow = flow_view(poc=ASK + 9.0 * ATR, vah=ASK + 9.0 * ATR,
                         val=ASK - 9.0 * ATR, prior_poc=ASK + 4.0 * ATR)
        structure = structure_view(has_gap_above=False, has_buy_pool=False)
        plan, fail = self.build(1, structure, flow)
        self.assertEqual(plan.target, ASK + 4.0 * ATR)
        self.assertEqual(plan.target_source, "naked POC")
        # Once visited it is excluded and the POC takes over.
        flow = replace(flow, prior_poc_naked=False)
        plan, fail = self.build(1, structure, flow)
        self.assertEqual(plan.target, ASK + 9.0 * ATR)
        self.assertEqual(plan.target_source, "POC")

    def test_sell_mirror_uses_the_levels_below(self):
        plan, fail = self.build(-1, sell_structure(), sell_flow())
        self.assertEqual(fail, "")
        self.assertEqual(plan.target, SELL_GAP)
        self.assertEqual(plan.target_source, "fair value gap")


#--- 17.4 risk:reward -----------------------------------------------------


class TestRiskReward(unittest.TestCase):
    def test_formula_and_one_decimal(self):
        plan, fail = build_plan(1, structure_view(), flow_view(),
                                trend_view(), ATR, CLOSE, BID, ASK, BULL, "M15")
        self.assertEqual(fail, "")
        self.assertAlmostEqual(
            plan.risk_reward, (GAP_ABOVE - ASK) / (ASK - PLAN_STOP)
        )
        self.assertAlmostEqual(plan.risk_reward, 1.6)

    def test_minimum_is_1_5_in_a_trend_and_2_0_otherwise(self):
        self.assertEqual(min_risk_reward(BULL), PLAN_RR_TREND)
        self.assertEqual(min_risk_reward(BEAR), PLAN_RR_TREND)
        self.assertEqual(min_risk_reward(RANGING), PLAN_RR_OTHER)
        self.assertEqual(min_risk_reward(VOLATILE), PLAN_RR_OTHER)
        self.assertEqual(min_risk_reward(TRANSITION), PLAN_RR_OTHER)
        # The gap alone gives RR 1.6: it passes in a trend but not while
        # ranging, where the minimum is 2.0.
        structure = structure_view(has_buy_pool=False)
        flow = flow_view(has_profile=False, prior_poc_available=False)
        plan, fail = build_plan(1, structure, flow, trend_view(),
                                ATR, CLOSE, BID, ASK, BULL, "M15")
        self.assertEqual(fail, "")
        plan, fail = build_plan(1, structure, flow, trend_view(),
                                ATR, CLOSE, BID, ASK, RANGING, "M15")
        self.assertIsNone(plan)
        self.assertEqual(fail, "no_target")


#--- 17.4 expected duration -----------------------------------------------


class TestExpectedDuration(unittest.TestCase):
    def build(self, trend, timeframe="M15"):
        return build_plan(1, structure_view(), flow_view(), trend,
                          ATR, CLOSE, BID, ASK, BULL, timeframe)

    def test_speed_is_distance_over_bars_since_flip(self):
        # speed = 1.2 / 4 = 0.3; candles = 4.0 / 0.3 = 13.33; x15 = 200 min.
        plan, _ = self.build(trend_view(bars_since_flip=4, distance_atrs=1.2))
        self.assertEqual(plan.duration, "~2-5 hours")

    def test_speed_floor_applies(self):
        # barsSinceFlip 0 -> speed 0 -> floor 0.2: candles 20 -> 300 min.
        plan, _ = self.build(trend_view(bars_since_flip=0, distance_atrs=0.0))
        self.assertEqual(plan.duration, "~3-8 hours")

    def test_speed_is_zero_when_the_supertrend_opposes(self):
        plan, _ = self.build(trend_view(direction=-1, bars_since_flip=4,
                                        distance_atrs=1.2))
        self.assertEqual(plan.duration, "~3-8 hours")   # the floor's band

    def test_band_is_half_and_one_point_five(self):
        # speed = 1.0 / 2 = 0.5; candles = 8; x15 = 120 min = 2 hours.
        plan, _ = self.build(trend_view(bars_since_flip=2, distance_atrs=1.0))
        self.assertEqual(plan.duration, "~1-3 hours")

    def test_minutes_under_two_hours_round_to_nearest_five(self):
        # speed = 1/3; candles = 12; x5 = 60 min -> ~30-90 min.
        plan, _ = self.build(trend_view(bars_since_flip=3, distance_atrs=1.0),
                             timeframe="M5")
        self.assertEqual(plan.duration, "~30-90 min")

    def test_minutes_per_candle_come_from_the_timeframe(self):
        self.assertEqual(format_duration(8.0, "M5"), "~20-60 min")
        self.assertEqual(format_duration(8.0, "M15"), "~1-3 hours")
        self.assertEqual(format_duration(8.0, "M30"), "~2-6 hours")

    def test_hours_up_to_three_days_then_the_caption(self):
        # 288 candles x 15 min = 4320 min = exactly 3 days: still hours.
        self.assertEqual(format_duration(288.0, "M15"), "~36-108 hours")
        self.assertEqual(format_duration(288.5, "M15"), "> 3 days")
        self.assertEqual(format_duration(400.0, "M15"), "> 3 days")

    def test_duration_is_fixed_when_the_plan_starts(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        frozen = tracker.state.plan.duration
        self.assertNotEqual(frozen, "")
        # A much faster Supertrend afterwards must not move the plan.
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, seq=1,
             trend=trend_view(bars_since_flip=1, distance_atrs=4.0))
        self.assertEqual(tracker.state.plan.duration, frozen)


#--- 17.7 the plan lifecycle ----------------------------------------------


class TestLifecycle(unittest.TestCase):
    def test_market_entry_is_active_from_the_starting_candle(self):
        tracker = SignalTracker()
        state = start_buy(tracker, score=0.72, seq=0)
        self.assertEqual(state.signal, 1)
        self.assertTrue(state.plan.active)
        self.assertEqual(state.plan.status, PLAN_ACTIVE)

    def test_target_reached(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        step(tracker, high=PLAN_TARGET + 0.0001, low=ASK + POINT,
             close=PLAN_TARGET, score=0.72, seq=1,
             bar_time=T0 + timedelta(minutes=15))
        state = tracker.state
        self.assertEqual(state.signal, 0)
        self.assertFalse(state.plan.active)
        self.assertEqual(
            result_lines(tracker),
            [f"Emtt | Plan BUY result | target reached | exit {PLAN_TARGET:.5f} | "
             f"+400 pts | 1 candles | bar 2026.10.09 14:45"],
        )

    def test_stop_reached(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        step(tracker, high=CLOSE, low=PLAN_STOP - 0.0001, close=PLAN_STOP,
             score=0.72, seq=1, bar_time=T0 + timedelta(minutes=15))
        self.assertEqual(
            result_lines(tracker),
            [f"Emtt | Plan BUY result | stop reached | exit {PLAN_STOP:.5f} | "
             f"-250 pts | 1 candles | bar 2026.10.09 14:45"],
        )

    def test_pending_plan_activates_when_a_candle_reaches_the_entry(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 2.6 * ATR,
            order_block_high=CLOSE - ATR,
        )
        tracker = SignalTracker()
        step(tracker, high=CLOSE + 0.0002, low=CLOSE - 0.0002, close=CLOSE,
             score=0.72, seq=0, structure=structure)
        state = tracker.state
        self.assertEqual(state.signal, 1)
        self.assertEqual(state.plan.status, PLAN_PENDING)
        self.assertEqual(state.plan.entry, CLOSE - ATR)
        # A candle whose range contains the edge activates the plan.
        step(tracker, high=CLOSE, low=CLOSE - 1.5 * ATR, close=CLOSE - ATR,
             score=0.72, seq=1, structure=structure,
             bar_time=T0 + timedelta(minutes=15))
        self.assertEqual(tracker.state.plan.status, PLAN_ACTIVE)
        self.assertTrue(any("entry reached" in line
                            for line in tracker.state.journal))

    def test_pending_plan_missed_when_the_target_comes_first(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 2.6 * ATR,
            order_block_high=CLOSE - ATR,
        )
        tracker = SignalTracker()
        step(tracker, high=CLOSE + 0.0002, low=CLOSE - 0.0002, close=CLOSE,
             score=0.72, seq=0, structure=structure)
        # The candle spans the target but stays above the entry.
        step(tracker, high=PLAN_TARGET + 0.001, low=CLOSE + ATR,
             close=PLAN_TARGET, score=0.72, seq=1, structure=structure,
             bar_time=T0 + timedelta(minutes=15))
        self.assertEqual(
            result_lines(tracker),
            [f"Emtt | Plan BUY result | missed | exit {PLAN_TARGET:.5f} | "
             f"+510 pts | 1 candles | bar 2026.10.09 14:45"],
        )

    def test_pending_plan_cancelled_when_the_stop_comes_first(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 2.6 * ATR,
            order_block_high=CLOSE - ATR,
        )
        stop = (CLOSE - 2.6 * ATR) - 0.5 * ATR
        tracker = SignalTracker()
        step(tracker, high=CLOSE + 0.0002, low=CLOSE - 0.0002, close=CLOSE,
             score=0.72, seq=0, structure=structure)
        # The candle reaches the stop but stays below the entry.
        step(tracker, high=CLOSE - 1.1 * ATR, low=stop - 0.001, close=stop,
             score=0.72, seq=1, structure=structure,
             bar_time=T0 + timedelta(minutes=15))
        self.assertEqual(
            result_lines(tracker),
            [f"Emtt | Plan BUY result | cancelled | exit {stop:.5f} | "
             f"-210 pts | 1 candles | bar 2026.10.09 14:45"],
        )

    def pending_plan_tracker(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 2.6 * ATR,
            order_block_high=CLOSE - ATR,
        )
        tracker = SignalTracker()
        step(tracker, high=CLOSE + 0.0002, low=CLOSE - 0.0002, close=CLOSE,
             score=0.72, seq=0, structure=structure)
        return tracker, structure

    def test_worse_result_counts_for_every_two_level_candle(self):
        entry = CLOSE - ATR
        stop = (CLOSE - 2.6 * ATR) - 0.5 * ATR
        # Pending, candle touches the stop and the entry: stop reached.
        tracker, structure = self.pending_plan_tracker()
        step(tracker, high=entry, low=stop - 0.0005, close=entry, score=0.72,
             seq=1, structure=structure, bar_time=T0 + timedelta(minutes=15))
        self.assertIn("stop reached", result_lines(tracker)[-1])
        self.assertIn("shared candle", result_lines(tracker)[-1])
        # Pending, candle touches the entry and the target: missed.
        tracker, structure = self.pending_plan_tracker()
        step(tracker, high=PLAN_TARGET, low=entry - 0.0005, close=PLAN_TARGET,
             score=0.72, seq=1, structure=structure,
             bar_time=T0 + timedelta(minutes=15))
        self.assertIn("missed", result_lines(tracker)[-1])
        self.assertIn("shared candle", result_lines(tracker)[-1])
        # Pending, candle touches all three levels: stop reached.
        tracker, structure = self.pending_plan_tracker()
        step(tracker, high=PLAN_TARGET, low=stop - 0.0005, close=CLOSE,
             score=0.72, seq=1, structure=structure,
             bar_time=T0 + timedelta(minutes=15))
        self.assertIn("stop reached", result_lines(tracker)[-1])
        self.assertIn("shared candle", result_lines(tracker)[-1])
        # Active, candle touches the stop and the target: stop reached.
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        step(tracker, high=PLAN_TARGET, low=PLAN_STOP - 0.0005, close=CLOSE,
             score=0.72, seq=1, bar_time=T0 + timedelta(minutes=15))
        self.assertIn("stop reached", result_lines(tracker)[-1])
        self.assertIn("shared candle", result_lines(tracker)[-1])

    def test_signal_changed_exits_at_the_candle_close(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE - 0.0001,
             score=0.50, seq=1, bar_time=T0 + timedelta(minutes=15))
        self.assertEqual(
            result_lines(tracker),
            [f"Emtt | Plan BUY result | signal changed | exit {CLOSE - 0.0001:.5f} | "
             f"-20 pts | 1 candles | bar 2026.10.09 14:45"],
        )

    def test_market_closed_ends_the_plan_at_the_last_close(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        tracker.market_closed()
        state = tracker.state
        self.assertEqual(state.signal, 0)
        self.assertFalse(state.plan.active)
        self.assertEqual(
            result_lines(tracker),
            [f"Emtt | Plan BUY result | market closed | exit {CLOSE:.5f} | "
             f"-10 pts | 0 candles | bar 2026.10.09 14:30"],
        )
        # Idempotent: a second call writes nothing.
        tracker.market_closed()
        self.assertEqual(len(result_lines(tracker)), 1)

    def test_chart_changed_ends_the_plan(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        tracker.chart_changed()
        self.assertIn("chart changed", result_lines(tracker)[-1])
        self.assertEqual(tracker.state.signal, 0)

    def test_the_next_idea_starts_on_the_next_candle_only(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        step(tracker, high=PLAN_TARGET + 0.0001, low=CLOSE, close=PLAN_TARGET,
             score=0.72, seq=1, bar_time=T0 + timedelta(minutes=15))
        state = tracker.state
        # The candle that ended the plan shows WAIT with the 17.6 reason.
        self.assertEqual(state.signal, 0)
        self.assertEqual(
            wait_text(state),
            f"Watching {DASH} the last idea just ended; a new one can start "
            f"on the next candle.",
        )
        # The next candle starts a fresh plan at once.
        start_buy(tracker, score=0.72, seq=2,
                  bar_time=T0 + timedelta(minutes=30))
        self.assertEqual(tracker.state.signal, 1)
        self.assertTrue(tracker.state.plan.active)

    def test_spread_is_not_added(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        # The candle's low sits one point above the stop: not reached.
        step(tracker, high=CLOSE, low=PLAN_STOP + POINT, close=CLOSE,
             score=0.72, seq=1)
        self.assertTrue(tracker.state.plan.active)
        # Exactly at the stop: reached (the level lies between low and high).
        step(tracker, high=CLOSE, low=PLAN_STOP, close=CLOSE, score=0.72, seq=2,
             bar_time=T0 + timedelta(minutes=15))
        self.assertIn("stop reached", result_lines(tracker)[-1])

    def test_checks_use_only_candles_after_the_start(self):
        # The starting candle's own range spans the stop, but the plan is
        # not checked against it: it started at that candle's close.
        tracker = SignalTracker()
        step(tracker, high=CLOSE + 0.0002, low=PLAN_STOP - 0.001, close=CLOSE,
             score=0.72, seq=0)
        self.assertTrue(tracker.state.plan.active)
        self.assertEqual(result_lines(tracker), [])

    def test_candles_count_from_the_start(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        for seq in (1, 2, 3):
            step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE,
                 score=0.72, seq=seq, bar_time=T0 + timedelta(minutes=15 * seq))
        step(tracker, high=PLAN_TARGET, low=CLOSE, close=PLAN_TARGET,
             score=0.72, seq=4, bar_time=T0 + timedelta(minutes=60))
        self.assertIn("4 candles", result_lines(tracker)[-1])


#--- 17.8 the journal -----------------------------------------------------


class TestJournal(unittest.TestCase):
    def test_plan_start_lines_carry_the_confidence(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        lines = tracker.state.journal
        self.assertEqual(
            lines[0],
            "Emtt | Signal BUY | confidence 72% | Trending, bar 60% | "
            "bar 2026.10.09 14:30",
        )
        self.assertEqual(
            lines[1],
            f"Emtt | Plan BUY | confidence 72% | entry {ASK:.5f} (market price) | "
            f"stop {PLAN_STOP:.5f} (swing low -0.5 ATR) | "
            f"target {PLAN_TARGET:.5f} (fair value gap) | RR 1:1.6 | "
            f"expected ~2-5 hours | spread 2 pts | bar 2026.10.09 14:30",
        )

    def test_wait_reason_change_is_journaled(self):
        tracker = SignalTracker()
        # 66%: below the 70% bar of a ranging market.
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.66,
             mood=RANGING, seq=0)
        self.assertEqual(
            tracker.state.journal,
            ["Emtt | Signal WAIT | confidence 66%, below the 70% bar | "
             "bar 2026.10.09 14:30"],
        )
        # Same reason on the next candle: nothing new is written.
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.65,
             mood=RANGING, seq=1, bar_time=T0 + timedelta(minutes=15))
        self.assertEqual(len(tracker.state.journal), 1)
        # The reason changes to "no target": journaled as a change.
        structure = structure_view(has_gap_above=False, has_buy_pool=False)
        flow = flow_view(has_profile=False, prior_poc_available=False)
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.75,
             mood=RANGING, seq=2, structure=structure, flow=flow,
             bar_time=T0 + timedelta(minutes=30))
        self.assertEqual(
            tracker.state.journal[-1],
            "Emtt | Signal WAIT | reason changed: no target gives 1:2.0 | "
            "bar 2026.10.09 15:00",
        )

    def test_continuing_wait_is_not_journaled(self):
        tracker = SignalTracker()
        for seq in range(3):
            step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE,
                 score=0.50, mood=BULL, seq=seq,
                 bar_time=T0 + timedelta(minutes=15 * seq))
        self.assertEqual(len(tracker.state.journal), 1)

    def test_no_journal_while_the_views_are_not_ready(self):
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.72,
             seq=0, trend=trend_view(ready=False))
        self.assertEqual(tracker.state.journal, [])
        self.assertEqual(tracker.state.confidence, -1)
        self.assertEqual(tracker.state.signal, 0)


#--- 17.6 the panel text --------------------------------------------------


class TestPanelText(unittest.TestCase):
    def rows(self, tracker, bid=BID, ask=ASK):
        return panel_rows(tracker.state, bid=bid, ask=ask, point=POINT,
                          digits=DIGITS, session="London")

    def test_buy_rows(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        rows = self.rows(tracker)
        self.assertEqual(rows["signal"], f"SIGNAL: {BUY_GLYPH} BUY")
        self.assertEqual(rows["confidence"], "Confidence: 72%")
        self.assertEqual(rows["entry"], f"Entry: {ASK:.5f} / --  (0 pts away)")
        self.assertEqual(
            rows["stop_loss"],
            f"Stop Loss: {PLAN_STOP:.5f} / --  (250 pts)",
        )
        self.assertEqual(
            rows["take_profit"],
            f"Take Profit: {PLAN_TARGET:.5f} / --  (400 pts)",
        )
        self.assertEqual(rows["risk_reward"], "Risk:Reward: 1:1.6")
        self.assertEqual(rows["session_suffix"], " ~2-5 hours")
        self.assertEqual(
            rows["status"],
            f"Signal active {DASH} price reached entry. No order placed.",
        )

    def test_sell_rows(self):
        tracker = SignalTracker()
        start_sell(tracker, score=0.72, seq=0)
        rows = self.rows(tracker)
        self.assertEqual(rows["signal"], f"SIGNAL: {SELL_GLYPH} SELL")
        self.assertEqual(rows["confidence"], "Confidence: 72%")
        self.assertEqual(rows["entry"], f"Entry: {BID:.5f} / --  (0 pts away)")
        self.assertEqual(rows["risk_reward"], "Risk:Reward: 1:1.6")

    def test_wait_rows(self):
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.50,
             mood=BULL, seq=0)
        rows = self.rows(tracker)
        self.assertEqual(rows["signal"], f"SIGNAL: {WAIT_GLYPH} WAIT")
        self.assertEqual(rows["confidence"], "Confidence: 50%")
        self.assertEqual(rows["entry"], "Entry: -- / --  (-- pts away)")
        self.assertEqual(rows["stop_loss"], "Stop Loss: -- / --  (-- pts)")
        self.assertEqual(rows["take_profit"], "Take Profit: -- / --  (-- pts)")
        self.assertEqual(rows["risk_reward"], "Risk:Reward: --")
        self.assertEqual(rows["session_suffix"], " --")
        self.assertEqual(
            rows["status"],
            f"Watching {DASH} confidence 50%, below the 60% bar.",
        )

    def test_dash_rows_while_the_views_are_not_ready(self):
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.72,
             seq=0, htf=htf_view(ready=False))
        rows = self.rows(tracker)
        self.assertEqual(rows["signal"], "SIGNAL: --")
        self.assertEqual(rows["confidence"], "Confidence: --")
        self.assertEqual(rows["entry"], "Entry: -- / --  (-- pts away)")
        self.assertEqual(rows["risk_reward"], "Risk:Reward: --")
        self.assertEqual(rows["session_suffix"], "")
        # Row 10 belongs to the Phase 3-5 event lines until the views are ready.
        self.assertIsNone(rows["status"])

    def test_money_parts_are_always_dashes(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        rows = self.rows(tracker)
        for key in ("entry", "stop_loss", "take_profit"):
            self.assertIn(" / --  (", rows[key])

    def test_pending_plan_status_line(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 2.6 * ATR,
            order_block_high=CLOSE - ATR,
        )
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.72,
             seq=0, structure=structure)
        self.assertEqual(
            status_text(tracker.state, BID, ASK),
            f"Signal active {DASH} waiting for price to reach entry. "
            f"No order placed.",
        )

    def test_level_lines_refresh_on_the_live_price(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        # The Bid at the stop: the stop line shows.
        self.assertEqual(
            status_text(tracker.state, PLAN_STOP, ASK),
            f"Stop level passed {DASH} signal updates at this candle's close.",
        )
        # The Ask at the target: the target line shows.
        self.assertEqual(
            status_text(tracker.state, BID, PLAN_TARGET),
            f"Target level passed {DASH} signal updates at this candle's close.",
        )
        # Both passed in one tick: the stop line wins (the worse outcome).
        self.assertEqual(
            status_text(tracker.state, PLAN_STOP, PLAN_TARGET),
            f"Stop level passed {DASH} signal updates at this candle's close.",
        )
        # Neither: the active line shows.
        self.assertEqual(
            status_text(tracker.state, BID, ASK),
            f"Signal active {DASH} price reached entry. No order placed.",
        )

    def test_each_wait_reason_line(self):
        # Below the bar.
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.50,
             mood=BULL, seq=0)
        self.assertEqual(
            wait_text(tracker.state),
            f"Watching {DASH} confidence 50%, below the 60% bar.",
        )
        # No swing point for the stop.
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.72,
             seq=0, structure=structure_view(has_swing_low=False))
        self.assertEqual(
            wait_text(tracker.state),
            f"Watching {DASH} confidence 72%, but no swing point for the stop yet.",
        )
        # The stop would be too far.
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.72,
             seq=0, structure=structure_view(newest_low_level=ASK - 2.6 * ATR))
        self.assertEqual(
            wait_text(tracker.state),
            f"Watching {DASH} confidence 72%, but the stop would be more than "
            f"3.0 ATR away.",
        )
        # No target gives the minimum (ranging needs 2.0, the gap gives 1.6).
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.72,
             mood=RANGING, seq=0, structure=structure_view(has_buy_pool=False),
             flow=flow_view(has_profile=False, prior_poc_available=False))
        self.assertEqual(
            wait_text(tracker.state),
            f"Watching {DASH} confidence 72%, but no target gives 1:2.0 yet.",
        )
        # The keep-level line after a showing BUY decayed.
        tracker = SignalTracker()
        start_buy(tracker, score=0.62, seq=0)
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.54,
             seq=1)
        self.assertEqual(
            wait_text(tracker.state),
            f"Watching {DASH} confidence 54%, below the 55% level that keeps "
            f"a BUY.",
        )
        # The SELL mirror of the keep-level line.
        tracker = SignalTracker()
        start_sell(tracker, score=0.62, seq=0)
        self.assertEqual(tracker.state.signal, -1)
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.54,
             direction=-1, seq=1, structure=sell_structure(score=0.54),
             flow=sell_flow(score=0.54), htf=htf_view(direction=-1, score=0.54))
        self.assertEqual(
            wait_text(tracker.state),
            f"Watching {DASH} confidence 54%, below the 55% level that keeps "
            f"a SELL.",
        )

    def test_price_row_marker_rule(self):
        tracker = SignalTracker()
        # WAIT: no marker.
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.50,
             seq=0)
        self.assertEqual(
            price_row(tracker.state, bid=BID, ask=ASK, spread_pts=SPREAD_PTS,
                      digits=DIGITS),
            f"Bid: {BID:.5f}  |  Ask: {ASK:.5f}  |  Spread: 2 pts",
        )
        # BUY: the arrow marks the Ask.
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        self.assertEqual(
            price_row(tracker.state, bid=BID, ask=ASK, spread_pts=SPREAD_PTS,
                      digits=DIGITS),
            f"Bid: {BID:.5f}  |  {ARROW_GLYPH}Ask: {ASK:.5f}  |  Spread: 2 pts",
        )
        # SELL: the arrow marks the Bid.
        tracker = SignalTracker()
        start_sell(tracker, score=0.72, seq=0)
        self.assertEqual(
            price_row(tracker.state, bid=BID, ask=ASK, spread_pts=SPREAD_PTS,
                      digits=DIGITS),
            f"{ARROW_GLYPH}Bid: {BID:.5f}  |  Ask: {ASK:.5f}  |  Spread: 2 pts",
        )

    def test_row4_distance_is_measured_from_the_dealing_price(self):
        structure = structure_view(
            has_order_block=True, order_block_bullish=True,
            order_block_near_edge=CLOSE - ATR, order_block_low=CLOSE - 2.6 * ATR,
            order_block_high=CLOSE - ATR,
        )
        tracker = SignalTracker()
        step(tracker, high=CLOSE, low=CLOSE - 0.0002, close=CLOSE, score=0.72,
             seq=0, structure=structure)
        rows = panel_rows(tracker.state, bid=BID, ask=ASK, point=POINT,
                          digits=DIGITS, session="London")
        # The block edge is 1.0 ATR = 100 points below the Ask, plus the
        # 10-point half-spread: 110 points away.
        self.assertEqual(
            rows["entry"],
            f"Entry: {CLOSE - ATR:.5f} / --  (110 pts away)",
        )


#--- 17.8 determinism -----------------------------------------------------


class TestDeterminism(unittest.TestCase):
    def run_sequence(self):
        tracker = SignalTracker()
        start_buy(tracker, score=0.72, seq=0)
        step(tracker, high=CLOSE + 0.0003, low=CLOSE - 0.0002, close=CLOSE,
             score=0.68, seq=1, bar_time=T0 + timedelta(minutes=15))
        step(tracker, high=PLAN_TARGET + 0.0001, low=CLOSE - 0.0001,
             close=PLAN_TARGET, score=0.66, seq=2,
             bar_time=T0 + timedelta(minutes=30))
        start_buy(tracker, score=0.72, seq=3,
                  bar_time=T0 + timedelta(minutes=45))
        return tracker

    def test_same_candles_give_the_same_confidence_signal_and_plan(self):
        first = self.run_sequence()
        second = self.run_sequence()
        self.assertEqual(first.state.combined, second.state.combined)
        self.assertEqual(first.state.confidence, second.state.confidence)
        self.assertEqual(first.state.signal, second.state.signal)
        self.assertEqual(first.state.plan, second.state.plan)
        self.assertEqual(first.state.journal, second.state.journal)

    def test_replaying_the_history_reproduces_the_readings(self):
        # A restart replays the same closed candles: the confidence and the
        # signal reproduce, and a fresh plan starts at the newest bar.
        tracker = self.run_sequence()
        replayed = SignalTracker()
        start_buy(replayed, score=0.72, seq=3,
                  bar_time=T0 + timedelta(minutes=45))
        self.assertEqual(replayed.state.confidence, tracker.state.confidence)
        self.assertEqual(replayed.state.signal, tracker.state.signal)


if __name__ == "__main__":
    unittest.main()
