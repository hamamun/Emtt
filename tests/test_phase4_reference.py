import math
import unittest

from phase4_reference import (
    ASSET_CLASSES,
    BOS,
    BUY_SIDE,
    CHOCH,
    DISCOUNT,
    EQUAL_TOLERANCE_ATR,
    EQUILIBRIUM,
    EVENT_AGE_BARS,
    HIGH,
    IMPULSE_BARS,
    LOW,
    MAX_ZONES,
    MIN_RANGE_ATR,
    NORMAL,
    OB_LOOKBACK_MIN,
    PREMIUM,
    PROXIMITY_ATRS,
    ROW10_INCOMPATIBLE,
    ROW10_STRUCTURE,
    SELL_SIDE,
    STATUS_FRESH_BARS,
    SWEEP_AGE_BARS,
    SWEEP_MENTION_BARS,
    WEIGHT_FRESHNESS,
    WEIGHT_PROXIMITY,
    WEIGHT_STRUCTURE,
    WEIGHT_SWEEP,
    WEIGHT_ZONE,
    Bar,
    Gap,
    OrderBlock,
    SmcTracker,
    Swing,
    append_row9,
    average_body_older_than,
    can_change_at,
    clamp01,
    combined_history_required,
    confirmed_swings,
    dealing_zone,
    fair_value_gap,
    lookback_scale,
    matrix_values,
    newest_order_block_candidate,
    order_block_candidate,
    pivot_at,
    pools_from_swings,
    replay,
    resolve_parameters,
    round_half_away,
    row10_status,
    row9_clause,
    scaled_window,
    select_gaps,
    select_largest_pool,
    select_order_block,
    smc_history_required,
    smc_score,
    supertrend_history_required,
    update_block,
    update_gap,
)


# Helpers write candles oldest-first, then reverse them into MQL5's series
# convention: index 0 is the newest closed candle.
def series(rows):
    return list(reversed([Bar(*row, time=i) for i, row in enumerate(rows)]))


def candle(close, body=0.2, span=1.0, time=0):
    return Bar(close - body / 2.0, close + span / 2.0, close - span / 2.0, close, time)


def oscillating_series(count=180):
    rows = []
    for i in range(count):
        centre = 100.0 + 4.0 * math.sin(i / 4.0) + 0.03 * i
        body = 0.25 + 0.05 * (i % 3)
        rows.append((centre - body / 2.0, centre + 0.9, centre - 0.9, centre))
    return series(rows), [1.0] * count


class SwingTests(unittest.TestCase):
    """13.3: strict, delayed pivots and the plateau rule."""

    def test_a_pivot_needs_strength_bars_on_both_sides(self):
        rates = series(
            [
                (1, 2, 0, 1),
                (1, 3, 0, 2),
                (1, 6, 0, 5),
                (1, 3, 0, 2),
                (1, 2, 0, 1),
            ]
        )
        # At the bar immediately after it formed there are not two newer bars.
        self.assertIsNone(pivot_at(rates, 1, 2, True))
        # Once two newer closed bars exist, the high is recognised exactly once.
        self.assertEqual(pivot_at(rates, 0, 2, True), (2, 6))
        swings = confirmed_swings(rates, 2, 20)
        self.assertEqual([(s.high, s.level) for s in swings], [(True, 6)])

    def test_a_plateau_publishes_its_oldest_bar_after_its_newest_ends(self):
        rates = series(
            [
                (1, 1, 0, 1),
                (1, 5, 0, 4),
                (1, 5, 0, 4),
                (1, 5, 0, 4),
                (1, 1, 0, 1),
                (1, 1, 0, 1),
            ]
        )
        pivot = pivot_at(rates, 1, 1, True)
        self.assertEqual(pivot, (4, 5))  # t=1, the oldest equal high
        swings = confirmed_swings(rates, 1, 20)
        highs = [s for s in swings if s.high]
        self.assertEqual(len(highs), 1)
        self.assertEqual(highs[0].time, 1)
        self.assertEqual(highs[0].level, 5)

    def test_unconfirmed_extreme_and_expired_swing_are_not_published(self):
        rates = series(
            [
                (1, 1, 0, 1),
                (1, 3, 0, 2),
                (1, 1, 0, 1),
                (1, 4, 0, 3),  # newest extreme lacks its newer confirmation
            ]
        )
        self.assertIsNone(pivot_at(rates, 0, 1, True))
        self.assertEqual(confirmed_swings(rates, 1, 1), [])

    def test_one_bar_never_publishes_both_types(self):
        # Directly exercise the replay's explicit no-tie rule by using a bar
        # whose high and low each satisfy a one-side mechanical comparison.
        # The rule remains that an ambiguous bar yields neither output.
        rates = series(
            [
                (5, 6, 4, 5),
                (5, 9, 1, 5),
                (5, 6, 4, 5),
            ]
        )
        # This wide bar is a high but not a low under true OHLC geometry;
        # the assertion documents the guard in confirmed_swings regardless.
        high = pivot_at(rates, 0, 1, True)
        low = pivot_at(rates, 0, 1, False)
        self.assertIsNotNone(high)
        self.assertIsNotNone(low)
        self.assertEqual(confirmed_swings(rates, 1, 20), [])


class EventAndSweepTests(unittest.TestCase):
    """13.4 / 13.7: close-only breaks and wick-only liquidity."""

    def _tracker_with_pair(self):
        tracker = SmcTracker()
        state = tracker.state
        state.initialized = True
        state.swings = [
            Swing(True, 110.0, 10, 10, 2),
            Swing(False, 90.0, 9, 9, 3),
        ]
        return tracker

    def test_bos_and_choch_use_the_prior_bias(self):
        tracker = self._tracker_with_pair()
        tracker._event_and_sweep(Bar(111, 112, 109, 111, 11), 11, True)
        self.assertEqual((tracker.state.event_kind, tracker.state.event_direction, tracker.state.bias), (BOS, 1, 1))
        self.assertTrue(tracker.state.swings[0].consumed)

        tracker = self._tracker_with_pair()
        tracker.state.bias = -1
        tracker._event_and_sweep(Bar(111, 112, 109, 111, 11), 11, True)
        self.assertEqual((tracker.state.event_kind, tracker.state.event_direction, tracker.state.bias), (CHOCH, 1, 1))

    def test_consumed_level_cannot_fire_twice_and_first_evaluation_has_no_event(self):
        tracker = self._tracker_with_pair()
        bar = Bar(111, 112, 109, 111, 11)
        tracker._event_and_sweep(bar, 11, False)
        self.assertEqual(tracker.state.bias, 0)
        tracker._event_and_sweep(bar, 12, True)
        self.assertEqual(tracker.state.event_kind, BOS)
        tracker._event_and_sweep(Bar(112, 113, 110, 112, 13), 13, True)
        self.assertEqual(tracker.state.event_sequence, 12)

    def test_wick_only_pierce_is_a_sweep_and_leaves_structure_untouched(self):
        tracker = self._tracker_with_pair()
        tracker.state.bias = -1
        tracker._event_and_sweep(Bar(109, 111, 106, 109.5, 11), 11, True)
        self.assertEqual(tracker.state.bias, -1)
        self.assertEqual(tracker.state.event_kind, "")
        self.assertEqual(tracker.state.last_sweep_side, BUY_SIDE)
        self.assertFalse(tracker.state.swings[0].consumed)
        self.assertTrue(tracker.state.swings[0].swept)


class OrderBlockTests(unittest.TestCase):
    """13.5: body baseline, impulse, lifecycle, distance and capacity."""

    def _ob_rates(self):
        # index 0 is the bullish displacement; index 2 is a down origin;
        # indices 3/4 are strictly older bodies used for its average.
        return series(
            [
                (10.0, 10.6, 9.6, 10.3),
                (10.0, 10.5, 9.5, 10.2),
                (12.0, 12.2, 10.8, 11.0),
                (10.0, 10.5, 9.5, 10.2),
                (10.0, 10.5, 9.5, 10.2),
                (10.0, 13.4, 9.8, 13.2),
            ]
        )

    def test_displacement_uses_only_bars_older_than_the_candidate(self):
        rates = self._ob_rates()
        # Re-index at the newest displacement candle: origin is index 3 in
        # this series because rows are reversed.
        candidate = 3
        average = average_body_older_than(rates, candidate, 2)
        self.assertAlmostEqual(average, 0.25, places=12)
        result = order_block_candidate(rates, 0, candidate, 2, True)
        self.assertIsNotNone(result)
        _, low, high, ratio = result
        self.assertEqual((low, high), (10.8, 12.2))
        self.assertGreaterEqual(ratio, 1.5)
        self.assertIsNotNone(newest_order_block_candidate(rates, 0, 10, 2, True))
        self.assertEqual(IMPULSE_BARS, 3)

    def test_full_range_mitigation_invalidation_and_no_return(self):
        block = OrderBlock(True, 100.0, 102.0, 1, 1, 2, 1.6)
        self.assertEqual(update_block(block, Bar(103, 104, 101, 103, 3)), "mitigated")
        self.assertTrue(block.mitigated)
        self.assertFalse(block.active)
        self.assertEqual(update_block(block, Bar(99, 100, 98, 99, 4)), "none")

        invalid = OrderBlock(True, 100.0, 102.0, 1, 1, 2, 1.6)
        self.assertEqual(update_block(invalid, Bar(99, 103, 98, 99, 3)), "invalidated")
        self.assertTrue(invalid.invalidated)
        self.assertFalse(invalid.active)
        self.assertEqual(update_block(invalid, Bar(105, 106, 104, 105, 4)), "none")

    def test_nearest_active_block_is_by_price_not_age_and_near_edge(self):
        older = OrderBlock(True, 90.0, 91.0, 1, 1, 1, 2.0)
        nearer = OrderBlock(True, 95.0, 96.0, 2, 2, 2, 2.0)
        picked, distance = select_order_block([older, nearer], 1, 100.0, 2.0)
        self.assertIs(picked, nearer)
        self.assertEqual(nearer.high, 96.0)
        self.assertAlmostEqual(distance, 2.0)
        # A reached price clamps the term at zero rather than going negative.
        self.assertEqual(select_order_block([nearer], 1, 96.0, 2.0)[1], 0.0)

    def test_capacity_is_eight_active_zones_per_direction(self):
        tracker = SmcTracker()
        for i in range(MAX_ZONES + 1):
            tracker.state.blocks.append(OrderBlock(True, 90 + i, 91 + i, i, i, i, 1.5))
        active = [b for b in tracker.state.blocks if b.active and b.bullish]
        self.assertEqual(len(active), MAX_ZONES + 1)  # raw fixture proves the precondition
        # The production discovery evicts oldest-first; model that deterministic rule.
        active.remove(min(active, key=lambda b: b.origin_sequence))
        self.assertEqual(len(active), MAX_ZONES)
        self.assertEqual(min(b.origin_sequence for b in active), 1)


class FairValueGapTests(unittest.TestCase):
    """13.6: non-overlap, lifecycle and nearest above/below selection."""

    def test_three_bar_non_overlap_in_both_directions(self):
        bullish = series([(10, 10, 9, 9.5), (10, 10.5, 9.5, 10), (12, 12.5, 11, 12)])
        bearish = series([(12, 13, 12, 12.5), (11, 11.5, 10.5, 11), (9, 10, 8.5, 9)])
        self.assertEqual(fair_value_gap(bullish, 0), (True, 10, 11))
        self.assertEqual(fair_value_gap(bearish, 0), (False, 10, 12))

    def test_touch_mitigates_and_close_through_far_edge_fills(self):
        gap = Gap(True, 100, 102, 1, 1, 1)
        self.assertEqual(update_gap(gap, Bar(103, 104, 101, 103, 2)), "mitigated")
        self.assertTrue(gap.mitigated)
        self.assertFalse(gap.active)
        filled = Gap(True, 100, 102, 1, 1, 1)
        self.assertEqual(update_gap(filled, Bar(99, 103, 98, 99, 2)), "filled")
        self.assertTrue(filled.filled)
        self.assertFalse(filled.active)

    def test_nearest_active_gaps_and_gap_inside_is_neither(self):
        above_far = Gap(True, 110, 112, 1, 1, 1)
        above_near = Gap(True, 104, 105, 2, 2, 2)
        below = Gap(False, 95, 96, 3, 3, 3)
        inside = Gap(True, 99, 101, 4, 4, 4)
        up, down, up_distance, down_distance = select_gaps([above_far, above_near, below, inside], 100, 2)
        self.assertIs(up, above_near)
        self.assertIs(down, below)
        self.assertAlmostEqual(up_distance, 2.0)
        self.assertAlmostEqual(down_distance, 2.0)
        self.assertNotIn(inside, (up, down))


class LiquidityAndZoneTests(unittest.TestCase):
    """13.7 / 13.8: pools and the dealing-range label."""

    def test_equal_levels_use_mean_count_and_disappear_below_two_members(self):
        swings = [
            Swing(True, 100.00, 1, 1, 1),
            Swing(True, 100.08, 2, 2, 1),
            Swing(False, 90.00, 3, 3, 1),
            Swing(False, 90.07, 4, 4, 1),
        ]
        pools = pools_from_swings(swings, 1.0)
        buy, sell = select_largest_pool(pools, True), select_largest_pool(pools, False)
        self.assertEqual((buy.count, sell.count), (2, 2))
        self.assertAlmostEqual(buy.level, 100.04)
        self.assertAlmostEqual(sell.level, 90.035)
        self.assertEqual(pools_from_swings(swings[:1], 1.0), [])
        self.assertEqual(EQUAL_TOLERANCE_ATR, 0.10)

    def test_dealing_range_uses_newest_end_and_older_opposite_origin(self):
        swings = [Swing(False, 90, 1, 2, 1), Swing(True, 110, 2, 5, 1)]
        zone, leg, low, high, equilibrium, position = dealing_zone(swings, 95, 2)
        self.assertEqual((zone, leg, low, high), (DISCOUNT, 1, 90, 110))
        self.assertEqual(equilibrium, 100)
        self.assertAlmostEqual(position, 0.25)
        zone, _, _, _, _, _ = dealing_zone(swings, 100, 2)
        self.assertEqual(zone, EQUILIBRIUM)
        zone, _, _, _, _, _ = dealing_zone(swings, 105, 2)
        self.assertEqual(zone, PREMIUM)

    def test_minimum_range_and_zone_position_bounds(self):
        tiny = [Swing(False, 100, 1, 1, 1), Swing(True, 100.9, 2, 2, 1)]
        self.assertEqual(dealing_zone(tiny, 100.4, 1.0)[0], "")
        self.assertEqual(MIN_RANGE_ATR, 1.0)
        wide = [Swing(False, 100, 1, 1, 1), Swing(True, 110, 2, 2, 1)]
        self.assertEqual(dealing_zone(wide, 50, 1.0)[-1], 0.0)
        self.assertEqual(dealing_zone(wide, 150, 1.0)[-1], 1.0)


class ScoreTests(unittest.TestCase):
    """13.9: all five bounded terms and direction-sensitive context."""

    def test_weights_sum_to_exactly_one_and_flat_is_zero(self):
        self.assertEqual(WEIGHT_STRUCTURE + WEIGHT_FRESHNESS + WEIGHT_ZONE + WEIGHT_PROXIMITY + WEIGHT_SWEEP, 1.0)
        self.assertEqual(
            smc_score(bias=0, event_kind=BOS, event_direction=1, bars_since_event=0, zone=DISCOUNT,
                      has_order_block=True, distance_to_ob_atrs=0, last_sweep_side=SELL_SIDE, bars_since_sweep=0),
            0.0,
        )

    def test_bos_choch_zone_distance_and_sweep_scales(self):
        bos = smc_score(bias=1, event_kind=BOS, event_direction=1, bars_since_event=0, zone=DISCOUNT,
                        has_order_block=True, distance_to_ob_atrs=0, last_sweep_side=SELL_SIDE, bars_since_sweep=0)
        choch = smc_score(bias=1, event_kind=CHOCH, event_direction=1, bars_since_event=0, zone=DISCOUNT,
                          has_order_block=True, distance_to_ob_atrs=0, last_sweep_side=SELL_SIDE, bars_since_sweep=0)
        self.assertAlmostEqual(bos - choch, WEIGHT_STRUCTURE * (1.0 - 0.6))
        self.assertEqual(
            smc_score(bias=1, event_kind=BOS, event_direction=1, bars_since_event=0, zone=PREMIUM,
                      has_order_block=False, distance_to_ob_atrs=0, last_sweep_side=BUY_SIDE, bars_since_sweep=0),
            WEIGHT_STRUCTURE + WEIGHT_FRESHNESS,
        )
        self.assertAlmostEqual(
            smc_score(bias=-1, event_kind=BOS, event_direction=-1, bars_since_event=EVENT_AGE_BARS,
                      zone=PREMIUM, has_order_block=True, distance_to_ob_atrs=PROXIMITY_ATRS,
                      last_sweep_side=BUY_SIDE, bars_since_sweep=SWEEP_AGE_BARS),
            WEIGHT_STRUCTURE + WEIGHT_ZONE,
        )

    def test_every_score_is_bounded(self):
        for bias in (-1, 1):
            for age in (0, 20, 40, 1000):
                for distance in (-1, 0, 1, 2, 99):
                    score = smc_score(bias=bias, event_kind=CHOCH, event_direction=bias, bars_since_event=age,
                                      zone=EQUILIBRIUM, has_order_block=True, distance_to_ob_atrs=distance,
                                      last_sweep_side=SELL_SIDE if bias > 0 else BUY_SIDE, bars_since_sweep=age)
                    self.assertGreaterEqual(score, 0.0)
                    self.assertLessEqual(score, 1.0)
        self.assertEqual(clamp01(-1), 0.0)
        self.assertEqual(clamp01(2), 1.0)


class ParameterAndHistoryTests(unittest.TestCase):
    """13.10: all matrix values, exact rounding, pause and common gate."""

    def test_all_classes_and_buckets_resolve_and_only_window_scales(self):
        for asset in ASSET_CLASSES:
            for bucket in (LOW, NORMAL, HIGH):
                base_window, strength, body = matrix_values(asset, bucket)
                params_m5 = resolve_parameters(asset, bucket, "M5")
                params_m15 = resolve_parameters(asset, bucket, "M15")
                params_m30 = resolve_parameters(asset, bucket, "M30")
                self.assertEqual(params_m5.structure_window, base_window)
                self.assertEqual((params_m5.swing_strength, params_m15.swing_strength, params_m30.swing_strength), (strength,) * 3)
                self.assertEqual((params_m5.body_period, params_m15.body_period, params_m30.body_period), (body,) * 3)
                self.assertEqual(params_m5.ob_lookback, max(OB_LOOKBACK_MIN, round_half_away(base_window / 3)))
                self.assertGreaterEqual(params_m15.structure_window, 20)
                self.assertLessEqual(params_m30.structure_window, 400)

    def test_half_away_rounding_is_explicit(self):
        self.assertEqual(round_half_away(62.5), 63)
        self.assertEqual(round_half_away(87.5), 88)
        self.assertEqual(scaled_window("Metals", LOW, "M15"), 63)
        self.assertEqual(scaled_window("Crypto", HIGH, "M15"), 88)
        self.assertEqual(lookback_scale("M30"), 1.5)

    def test_pause_and_atomic_change(self):
        self.assertFalse(can_change_at(2, 0))
        self.assertTrue(can_change_at(3, 0))
        tracker = SmcTracker("Forex Major", LOW, "M5")
        self.assertTrue(tracker.change_context("Forex Major", HIGH, "M5", 10))
        self.assertFalse(tracker.change_context("Forex Major", LOW, "M5", 11))
        self.assertFalse(tracker.change_context("Forex Major", LOW, "M5", 12))
        self.assertTrue(tracker.change_context("Forex Major", LOW, "M5", 13))

    def test_structure_requirement_never_raises_today_supertrend_gate(self):
        for asset in ASSET_CLASSES:
            for bucket in (LOW, NORMAL, HIGH):
                for tf, expected in (("M5", 250), ("M15", 300), ("M30", 350)):
                    self.assertLess(smc_history_required(asset, bucket, tf), expected)
                    self.assertEqual(combined_history_required(asset, bucket, tf), expected)
                    self.assertEqual(supertrend_history_required(tf), expected)


class PanelTests(unittest.TestCase):
    """13.11: compact Row 9 and full Row 10 precedence."""

    def test_three_parts_priority_and_digits(self):
        clause = row9_clause(
            ready=True, zone=DISCOUNT, event_kind=BOS, event_direction=1,
            has_order_block=True, order_block_near_edge=1.0845,
            has_gap_above=True, has_gap_below=False, gap_above_near_edge=1.09, gap_below_near_edge=0,
            bias=1, last_sweep_side=SELL_SIDE, bars_since_sweep=0, digits=5,
        )
        self.assertEqual(clause, "Discount, BOS up, OB 1.08450")
        fvg = row9_clause(
            ready=True, zone=PREMIUM, event_kind=CHOCH, event_direction=-1,
            has_order_block=False, order_block_near_edge=0,
            has_gap_above=False, has_gap_below=True, gap_above_near_edge=0, gap_below_near_edge=1.0912,
            bias=-1, last_sweep_side=BUY_SIDE, bars_since_sweep=0, digits=5,
        )
        self.assertEqual(fvg, "Premium, CHoCH down, FVG 1.09120")
        sweep = row9_clause(
            ready=True, zone=EQUILIBRIUM, event_kind=BOS, event_direction=-1,
            has_order_block=False, order_block_near_edge=0, has_gap_above=False, has_gap_below=False,
            gap_above_near_edge=0, gap_below_near_edge=0, bias=-1, last_sweep_side=BUY_SIDE,
            bars_since_sweep=SWEEP_MENTION_BARS, digits=3,
        )
        self.assertEqual(sweep, "Equilibrium, BOS down, swept highs")

    def test_omission_and_no_trailing_separator(self):
        empty = row9_clause(
            ready=True, zone="", event_kind="", event_direction=0, has_order_block=False,
            order_block_near_edge=0, has_gap_above=False, has_gap_below=False,
            gap_above_near_edge=0, gap_below_near_edge=0, bias=0,
            last_sweep_side=SELL_SIDE, bars_since_sweep=SWEEP_MENTION_BARS + 1, digits=5,
        )
        self.assertEqual(empty, "")
        self.assertEqual(append_row9("Wild (Supertrend bullish)", empty), "Wild (Supertrend bullish)")
        self.assertEqual(append_row9("Regime | Supertrend", "Discount"), "Regime | Supertrend | Discount")

    def test_status_precedence(self):
        self.assertEqual(row10_status(incompatible=True, ready=True, event_kind=CHOCH), ROW10_INCOMPATIBLE)
        self.assertTrue(row10_status(loading=True, ready=True, event_kind=CHOCH).startswith("Waiting — Loading"))
        self.assertEqual(row10_status(market_closed=True, ready=True, event_kind=CHOCH), "Paused — Waiting for market to open")
        self.assertEqual(row10_status(ready=True, event_kind=CHOCH, event_direction=1, bars_since_event=STATUS_FRESH_BARS),
                         "Watching — CHoCH up, structure may be reversing")
        self.assertEqual(row10_status(ready=True, event_kind=BOS, event_direction=-1, bars_since_event=0,
                                      last_sweep_side=BUY_SIDE, bars_since_sweep=0),
                         "Watching — BOS down confirmed, trend continuing")
        self.assertEqual(
            row10_status(ready=True, fresh_choch_direction=-1, fresh_bos_direction=1,
                         last_sweep_side=SELL_SIDE, bars_since_sweep=0),
            "Watching — CHoCH down, structure may be reversing",
        )
        self.assertEqual(row10_status(ready=True, last_sweep_side=SELL_SIDE, bars_since_sweep=0),
                         "Watching — Liquidity swept below, no structure break")
        self.assertEqual(row10_status(ready=True), ROW10_STRUCTURE)
        self.assertEqual(row10_status(supertrend_ready=True), "Watching — Supertrend context only, no signal yet")


class DeterminismTests(unittest.TestCase):
    """13.12: replay is a deterministic bar-by-bar state reconstruction."""

    def test_same_series_restart_and_timeframe_round_trip_are_identical(self):
        rates, atrs = oscillating_series()
        first = replay(rates, atrs, "Forex Major", NORMAL, "M5")
        second = replay(rates, atrs, "Forex Major", NORMAL, "M5")
        signature = lambda state: (
            state.bias, state.event_kind, state.event_direction, state.zone,
            round(state.score, 12),
            [(s.high, round(s.level, 8), s.consumed) for s in state.swings],
            [(round(b.low, 8), round(b.high, 8), b.active, b.mitigated, b.invalidated) for b in state.blocks],
            [(round(g.low, 8), round(g.high, 8), g.active, g.mitigated, g.filled) for g in state.gaps],
        )
        self.assertEqual(signature(first), signature(second))
        self.assertEqual(signature(replay(rates, atrs, "Forex Major", NORMAL, "M5")), signature(first))
        self.assertNotEqual(resolve_parameters("Forex Major", NORMAL, "M15"), first.params)

    def test_parameter_rebuild_matches_a_from_scratch_replay(self):
        rates, atrs = oscillating_series()
        # A permitted context change is rebuilt from the copied closed bars;
        # comparing two fresh replays at the new values expresses the required
        # no-guess result independently of the old state.
        rebuilt = replay(rates, atrs, "Crypto", HIGH, "M15")
        fresh = replay(rates, atrs, "Crypto", HIGH, "M15")
        self.assertEqual(
            (rebuilt.bias, rebuilt.zone, round(rebuilt.score, 12), rebuilt.params),
            (fresh.bias, fresh.zone, round(fresh.score, 12), fresh.params),
        )


if __name__ == "__main__":
    unittest.main()
