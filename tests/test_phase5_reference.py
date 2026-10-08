"""Portable tests for Emtt Phase 5 (Emtt.md 15.3-15.12, scope of 15.15).

Everything asserted here runs against ``phase5_reference`` with no MT5
dependency, so the exact Phase 5 rules are exercised on every CI platform.
Series convention matches MQL5: index 0 is the newest closed bar.
"""
import math
import unittest
from datetime import date, datetime, timedelta, timezone

from phase2_reference import (
    BEAR,
    BULL,
    CLOSED,
    HIGH,
    LOW,
    NORMAL,
    RANGING,
    TRANSITION,
    UNKNOWN,
    VOLATILE,
    RegimeTracker,
)
from phase4_reference import (
    VOLATILITIES,
    can_change_at,
    round_half_away,
    smc_history_required,
    supertrend_history_required,
)
from phase5_reference import (
    BINS,
    CONTROL_SCALE,
    CVD_FLIP,
    CVD_WINDOW,
    FETCH_BUFFER,
    MAGNET_ATRS,
    MAGNET_NAKED_POC,
    MAGNET_POC,
    MAGNET_VAH,
    MAGNET_VAL,
    MTF_FETCH_BUFFER,
    MTF_STATUS_FRESH_BARS,
    MTF_WEIGHT_DIRECTION,
    MTF_WEIGHT_REGIME,
    MTF_WEIGHT_STRUCTURE,
    PRIOR_POC_MIN_BARS,
    ROW10_CONTEXT_ONLY,
    ROW10_INCOMPATIBLE,
    ROW10_LOADING,
    ROW10_MARKET_CLOSED,
    ROW10_SMC_CONTEXT_ONLY,
    SESSION_ASIA,
    SESSION_DEPTH,
    SESSION_LONDON,
    SESSION_NY,
    SIDE_ABOVE,
    SIDE_BELOW,
    SIDE_NONE,
    STATUS_FRESH_BARS,
    VALUE_AREA,
    WEIGHT_CONTROL,
    WEIGHT_FAIR,
    WEIGHT_MAGNET,
    WEIGHT_VALUE,
    WINDOW_MAX,
    WINDOW_MIN,
    Bar,
    MtfFacts,
    MtfReading,
    MtfTracker,
    VolumeFlowTracker,
    append_row9,
    bar_delta,
    build_measurements,
    classify_flow,
    combined_history_required,
    compute_profile,
    flow_name,
    magnet_members,
    matrix_window,
    mtf_clause,
    mtf_fetch_count,
    mtf_history_required,
    mtf_regime_word,
    mtf_score,
    mtf_status,
    mtf_timeframe,
    nearest_directional_magnet,
    previous_anchor,
    profile_window,
    published_magnet,
    row10_status,
    session_anchor,
    session_label,
    session_open_utc,
    smc_history_required_worst,
    vf_fetch_depth,
    vf_history_required,
    volume_flow_score,
)

UTC = timezone.utc
ASSET_CLASSES = ("Forex Major", "Forex Cross", "Metals", "Crypto", "Indices", "Generic")
MTF_HISTORY_H1 = 250


def at(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def mkbar(time, high, low, close, volume, open_=None):
    return Bar(
        time=time,
        open=close if open_ is None else open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def flat_bar(time, price, volume):
    """A bar whose typical price is exactly ``price`` (uses no range at all)."""
    return mkbar(time, price, price, price, volume)


def mid_bar(time, low, high, volume, close=None):
    """A bar closing at the midpoint contributes a zero delta estimate."""
    return mkbar(time, high, low, (high + low) / 2.0 if close is None else close, volume)


def wave_series(count, *, tf_minutes=5, end=None, base=1.1000):
    """A deterministic series in MQL5 order (index 0 = newest closed bar)."""
    end = end or at(2026, 6, 10, 12, 0)
    bars = []
    for offset in range(count):
        time = end - timedelta(minutes=tf_minutes * offset)
        close = base + 0.0010 * math.sin(offset / 9.0) + 0.00002 * offset
        high = close + 0.0004
        low = close - 0.0004
        volume = 100.0 + (offset % 7) * 11.0
        bars.append(mkbar(time, high, low, close, volume, open_=close))
    return bars


def htf_series(count=270, *, base=1.1000, end=None):
    """H1 bars for the higher-timeframe walk."""
    end = end or at(2026, 6, 10, 12, 0)
    bars = []
    for offset in range(count):
        time = end - timedelta(hours=offset)
        close = base + 0.0020 * math.sin(offset / 12.0) + 0.00005 * offset
        high = close + 0.0008
        low = close - 0.0008
        bars.append(mkbar(time, high, low, close, 500.0 + offset, open_=close))
    return bars


def htf_facts(count=270, *, direction=1, atr_period=14, er_period=10):
    facts = []
    for offset in range(count):
        atr = 0.0010 * (1.0 + 0.20 * math.sin(offset / 7.0))
        if direction > 0:
            fast, medium, slow = 1.1032, 1.1024, 1.1016
        elif direction < 0:
            fast, medium, slow = 1.1016, 1.1024, 1.1032
        else:
            fast, medium, slow = 1.1024, 1.1032, 1.1016
        width = 0.0020 + 0.0004 * math.sin(offset / 5.0)
        facts.append(
            MtfFacts(
                atr_period=atr_period,
                er_period=er_period,
                volatility=NORMAL,
                atr_value=atr,
                atr50=0.0010,
                kama_fast=fast,
                kama_medium=medium,
                kama_slow=slow,
                band_width=width,
                previous_band_width=0.0020,
            )
        )
    return facts


def replay(tracker, bars, *, atr=0.0010, volatility=None, write_journal=True):
    """Replay a whole series oldest to newest, one bar per call."""
    for index in range(len(bars) - 1, -1, -1):
        if volatility is not None:
            tracker.volatility = volatility
        tracker.advance(
            bars,
            index,
            atr,
            atr_period=14,
            bar_sequence=len(bars) - index,
            write_journal=write_journal,
        )
    return tracker


def reading_tuple(tracker):
    reading = tracker.reading
    return (
        reading.ready,
        reading.session_name,
        reading.bars_since_session_start,
        reading.flow_direction,
        reading.has_vwap,
        round(reading.vwap, 12),
        reading.price_vs_vwap,
        reading.poc,
        reading.vah,
        reading.val,
        reading.prior_poc,
        reading.prior_poc_naked,
        reading.magnet_kind,
        reading.magnet_price,
        round(reading.volume_flow_score, 12),
    )


#=== 15.3 session anchor ====================================================

class SessionAnchorTests(unittest.TestCase):
    def test_summer_opens(self):
        day = date(2026, 6, 10)
        self.assertEqual(session_open_utc(day, SESSION_ASIA), at(2026, 6, 9, 21, 0))
        self.assertEqual(session_open_utc(day, SESSION_LONDON), at(2026, 6, 10, 6, 0))
        self.assertEqual(session_open_utc(day, SESSION_NY), at(2026, 6, 10, 11, 0))

    def test_winter_opens(self):
        day = date(2026, 1, 14)
        self.assertEqual(session_open_utc(day, SESSION_ASIA), at(2026, 1, 13, 20, 0))
        self.assertEqual(session_open_utc(day, SESSION_LONDON), at(2026, 1, 14, 7, 0))
        self.assertEqual(session_open_utc(day, SESSION_NY), at(2026, 1, 14, 12, 0))

    def test_later_open_wins_in_the_overlap(self):
        anchor = session_anchor(at(2026, 6, 10, 14, 0))
        self.assertEqual(anchor, at(2026, 6, 10, 11, 0))
        self.assertEqual(session_label(anchor), "NY")

    def test_late_utc_hours_anchor_to_asia(self):
        for minute in (0, 30, 59):
            anchor = session_anchor(at(2026, 6, 10, 22, minute))
            self.assertEqual(anchor, at(2026, 6, 10, 21, 0))
            self.assertEqual(session_label(anchor), "Asia")

    def test_london_over_asia(self):
        anchor = session_anchor(at(2026, 6, 10, 8, 0))
        self.assertEqual(anchor, at(2026, 6, 10, 6, 0))
        self.assertEqual(session_label(anchor), "London")

    def test_previous_anchor_walks_back_one_session(self):
        self.assertEqual(previous_anchor(at(2026, 6, 10, 11, 0)), at(2026, 6, 10, 6, 0))
        self.assertEqual(previous_anchor(at(2026, 6, 10, 6, 0)), at(2026, 6, 9, 21, 0))
        self.assertEqual(previous_anchor(at(2026, 6, 10, 21, 0)), at(2026, 6, 10, 11, 0))

    def test_anchor_is_pure(self):
        stamp = at(2026, 6, 10, 22, 30)
        self.assertEqual(session_anchor(stamp), session_anchor(stamp))
        self.assertEqual(session_anchor(stamp), at(2026, 6, 10, 21, 0))

    def test_weekend_gap_produces_no_special_state(self):
        # Friday evening and Sunday evening anchor to their own Asia open.
        self.assertEqual(session_anchor(at(2026, 6, 12, 22, 0)), at(2026, 6, 12, 21, 0))
        self.assertEqual(session_anchor(at(2026, 6, 14, 22, 0)), at(2026, 6, 14, 21, 0))
        self.assertEqual(session_anchor(at(2026, 6, 15, 2, 0)), at(2026, 6, 14, 21, 0))

    def test_reanchor_is_visible_in_the_tracker(self):
        bars = [
            mkbar(at(2026, 6, 10, 11, 10), 1.1010, 1.1000, 1.1005, 100.0),
            mkbar(at(2026, 6, 10, 11, 5), 1.1010, 1.1000, 1.1005, 100.0),
            # 11:00 UTC starts the NY anchor; the London anchor ran from 06:00.
            mkbar(at(2026, 6, 10, 11, 0), 1.1010, 1.1000, 1.1005, 100.0),
            mkbar(at(2026, 6, 10, 6, 5), 1.1010, 1.1000, 1.1005, 100.0),
        ]
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), bars, write_journal=True
        )
        self.assertEqual(tracker.reading.session_name, "NY")
        self.assertEqual(tracker.reading.bars_since_session_start, 3)
        self.assertTrue(
            any("VWAP re-anchored" in line for line in tracker.journal), tracker.journal
        )
        self.assertIn("session London -> NY", " ".join(tracker.journal))


#=== 15.4 session VWAP ======================================================

class VwapTests(unittest.TestCase):
    def test_weighted_typical_price_ignores_zero_volume_bars(self):
        bars = [
            mkbar(at(2026, 6, 10, 11, 30), 1.1150, 1.1050, 1.1120, 0.0),
            mkbar(at(2026, 6, 10, 11, 25), 1.1100, 1.1000, 1.1080, 200.0),
            mkbar(at(2026, 6, 10, 11, 20), 1.1050, 1.0950, 1.0980, 100.0),
        ]
        tracker = replay(VolumeFlowTracker(timeframe="M5", volatility=LOW), bars)
        expected = (
            (1.1100 + 1.1000 + 1.1080) / 3.0 * 200.0
            + (1.1050 + 1.0950 + 1.0980) / 3.0 * 100.0
        ) / 300.0
        self.assertTrue(tracker.reading.has_vwap)
        self.assertAlmostEqual(tracker.reading.vwap, expected, places=12)

    def test_no_vwap_before_the_first_positive_volume_bar(self):
        bars = [
            mkbar(at(2026, 6, 10, 11, 30), 1.1150, 1.1050, 1.1120, 0.0),
            mkbar(at(2026, 6, 10, 11, 25), 1.1100, 1.1000, 1.1080, 0.0),
        ]
        tracker = replay(VolumeFlowTracker(timeframe="M5", volatility=LOW), bars)
        self.assertFalse(tracker.reading.has_vwap)
        self.assertEqual(tracker.reading.vwap, 0.0)
        self.assertEqual(tracker.reading.price_vs_vwap, SIDE_NONE)

    def test_price_vs_vwap_above_below_and_equal(self):
        above = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW),
            [mkbar(at(2026, 6, 10, 11, 30), 1.1050, 1.1000, 1.1040, 100.0)],
        )
        self.assertEqual(above.reading.price_vs_vwap, SIDE_ABOVE)

        below = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW),
            [mkbar(at(2026, 6, 10, 11, 30), 1.1050, 1.1000, 1.1010, 100.0)],
        )
        self.assertEqual(below.reading.price_vs_vwap, SIDE_BELOW)

        # close == typical price exactly: neither above nor below.
        equal = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW),
            [mkbar(at(2026, 6, 10, 11, 30), 1.1100, 1.0900, 1.1000, 100.0)],
        )
        self.assertTrue(equal.reading.has_vwap)
        self.assertEqual(equal.reading.price_vs_vwap, SIDE_NONE)

    def test_running_sum_equals_a_from_scratch_recompute(self):
        bars = wave_series(40)
        tracker = VolumeFlowTracker(timeframe="M5", volatility=LOW)
        for index in range(len(bars) - 1, -1, -1):
            tracker.advance(bars, index, 0.0010, bar_sequence=len(bars) - index)
            anchor = session_anchor(bars[index].time)
            # The walk is oldest to newest, so at this point the tracker has
            # seen exactly the bars at and beyond ``index`` in series order.
            session_bars = [
                bar for bar in bars[index:] if session_anchor(bar.time) == anchor
            ]
            volume = sum(bar.volume for bar in session_bars)
            weighted = sum(
                (bar.high + bar.low + bar.close) / 3.0 * bar.volume
                for bar in session_bars
            )
            self.assertEqual(
                tracker.reading.bars_since_session_start, len(session_bars)
            )
            if volume > 0:
                self.assertAlmostEqual(
                    tracker.reading.vwap, weighted / volume, places=12
                )

    def test_reanchor_resets_the_sums(self):
        bars = [
            mkbar(at(2026, 6, 10, 11, 30), 1.1050, 1.1000, 1.1040, 100.0),
            mkbar(at(2026, 6, 10, 11, 25), 1.1050, 1.1000, 1.1040, 100.0),
            mkbar(at(2026, 6, 10, 6, 5), 1.0950, 1.0900, 1.0940, 300.0),
        ]
        tracker = replay(VolumeFlowTracker(timeframe="M5", volatility=LOW), bars)
        self.assertEqual(tracker.reading.bars_since_session_start, 2)
        self.assertAlmostEqual(
            tracker.reading.vwap, (1.1050 + 1.1000 + 1.1040) / 3.0
        )


#=== 15.5 volume profile ====================================================

class ProfileTests(unittest.TestCase):
    def test_40_bins_and_the_top_edge_lands_in_bin_39(self):
        bars = [
            flat_bar(at(2026, 6, 10, 1, 0), 100.0, 10.0),
            flat_bar(at(2026, 6, 10, 0, 30), 20.0, 5.0),
            flat_bar(at(2026, 6, 10, 0, 0), 0.0, 5.0),
        ]
        profile = compute_profile(bars)
        width = 100.0 / BINS
        self.assertTrue(profile.readable)
        self.assertEqual(profile.poc_bin, BINS - 1)
        self.assertAlmostEqual(profile.poc, (BINS - 1 + 0.5) * width)

    def test_poc_tie_resolves_to_the_lower_bin(self):
        bars = [
            flat_bar(at(2026, 6, 10, 1, 0), 90.0, 100.0),
            flat_bar(at(2026, 6, 10, 0, 0), 10.0, 100.0),
        ]
        profile = compute_profile(bars)
        self.assertEqual(profile.poc_bin, 0)
        self.assertAlmostEqual(profile.poc, 10.0 + 0.5 * (80.0 / BINS))

    def test_value_area_grows_towards_the_larger_side(self):
        bars = [
            flat_bar(at(2026, 6, 10, 3, 0), 80.0, 0.0),
            flat_bar(at(2026, 6, 10, 2, 0), 40.0, 30.0),
            flat_bar(at(2026, 6, 10, 1, 0), 38.0, 20.0),
            flat_bar(at(2026, 6, 10, 0, 0), 42.0, 5.0),
            flat_bar(at(2026, 6, 9, 23, 0), 0.0, 5.0),
        ]
        profile = compute_profile(bars)
        width = 80.0 / BINS
        self.assertEqual(profile.poc_bin, 20)
        self.assertEqual(profile.bottom_bin, 19)  # 20 above < 20 below
        self.assertEqual(profile.top_bin, 20)
        self.assertAlmostEqual(profile.vah, 21 * width)
        self.assertAlmostEqual(profile.val, 19 * width)

    def test_value_area_tie_takes_the_lower_side(self):
        bars = [
            flat_bar(at(2026, 6, 10, 3, 0), 80.0, 0.0),
            flat_bar(at(2026, 6, 10, 2, 0), 40.0, 30.0),
            flat_bar(at(2026, 6, 10, 1, 0), 38.0, 20.0),
            flat_bar(at(2026, 6, 10, 0, 0), 42.0, 20.0),
            flat_bar(at(2026, 6, 9, 23, 0), 0.0, 0.0),
        ]
        profile = compute_profile(bars)
        width = 80.0 / BINS
        self.assertEqual(profile.bottom_bin, 19)
        self.assertAlmostEqual(profile.val, 19 * width)

    def test_value_area_walks_through_an_exhausted_side(self):
        bars = [
            flat_bar(at(2026, 6, 10, 1, 0), 80.0, 40.0),
            flat_bar(at(2026, 6, 10, 0, 0), 0.0, 50.0),
        ]
        profile = compute_profile(bars)
        self.assertEqual(profile.bottom_bin, 0)
        self.assertEqual(profile.top_bin, BINS - 1)
        self.assertAlmostEqual(profile.vah, 80.0)
        self.assertAlmostEqual(profile.val, 0.0)

    def test_degenerate_and_empty_windows_publish_no_reading(self):
        degenerate = compute_profile([flat_bar(at(2026, 6, 10, 0, 0), 10.0, 100.0)])
        self.assertFalse(degenerate.readable)
        self.assertEqual(degenerate.total_volume, 100.0)
        self.assertIsNone(degenerate.poc)

        silent = compute_profile([flat_bar(at(2026, 6, 10, 0, 0), 10.0, 0.0)])
        self.assertFalse(silent.readable)
        self.assertEqual(silent.total_volume, 0.0)

    def test_value_area_is_seventy_percent(self):
        self.assertEqual(VALUE_AREA, 0.70)


class PriorPocTests(unittest.TestCase):
    PRIOR = [
        flat_bar(at(2026, 6, 10, 6, 5), 1.0950, 50.0),
        flat_bar(at(2026, 6, 10, 6, 0), 1.1050, 100.0),
    ]

    def test_prior_poc_needs_two_positive_volume_bars(self):
        current = [flat_bar(at(2026, 6, 10, 11, 5), 1.1010, 100.0)]
        stub = [
            flat_bar(at(2026, 6, 10, 6, 5), 1.0950, 0.0),
            flat_bar(at(2026, 6, 10, 6, 0), 1.1050, 100.0),
        ]
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), current + stub
        )
        self.assertIsNone(tracker.reading.prior_poc)

        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), current + self.PRIOR
        )
        self.assertIsNotNone(tracker.reading.prior_poc)
        self.assertTrue(tracker.reading.prior_poc_naked)
        self.assertEqual(PRIOR_POC_MIN_BARS, 2)

    def test_prior_poc_comes_from_the_previous_sessions_own_bars(self):
        current = [flat_bar(at(2026, 6, 10, 11, 5), 1.1010, 100.0)]
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), current + self.PRIOR
        )
        width = (1.1050 - 1.0950) / BINS
        self.assertAlmostEqual(
            tracker.reading.prior_poc, 1.0950 + (BINS - 1 + 0.5) * width
        )

    def test_naked_poc_loses_nakedness_for_the_rest_of_the_session(self):
        current = [
            flat_bar(at(2026, 6, 10, 11, 10), 1.1010, 100.0),
            # A current-session bar trading through the prior POC.
            mkbar(at(2026, 6, 10, 11, 5), 1.1060, 1.0940, 1.1010, 100.0),
        ]
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), current + self.PRIOR
        )
        self.assertIsNotNone(tracker.reading.prior_poc)
        self.assertFalse(tracker.reading.prior_poc_naked)

    def test_the_re_anchoring_bar_itself_can_trade_through(self):
        # The first closed bar of the new session is a bar of the current
        # session, so it already decides the level's nakedness (15.5).
        touched = [
            flat_bar(at(2026, 6, 10, 11, 10), 1.1010, 100.0),
            mkbar(at(2026, 6, 10, 11, 5), 1.1060, 1.0940, 1.1010, 100.0),
        ]
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), touched + self.PRIOR
        )
        self.assertIsNotNone(tracker.reading.prior_poc)
        self.assertFalse(tracker.reading.prior_poc_naked)

        untouched = [
            flat_bar(at(2026, 6, 10, 11, 10), 1.1010, 100.0),
            flat_bar(at(2026, 6, 10, 11, 5), 1.1010, 100.0),
        ]
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), untouched + self.PRIOR
        )
        self.assertIsNotNone(tracker.reading.prior_poc)
        self.assertTrue(tracker.reading.prior_poc_naked)

    def test_the_prior_poc_level_never_moves_within_a_session(self):
        current = [
            flat_bar(at(2026, 6, 10, 11, 5 + 5 * step), 1.1000 + 0.0005 * step, 100.0)
            for step in range(4)
        ]
        bars = current + self.PRIOR
        tracker = VolumeFlowTracker(timeframe="M5", volatility=LOW)
        levels = []
        for index in range(len(bars) - 1, -1, -1):
            tracker.advance(bars, index, 0.0010, bar_sequence=len(bars) - index)
            if tracker.reading.session_name == "NY" and tracker.reading.prior_poc:
                levels.append(round(tracker.reading.prior_poc, 12))
        self.assertEqual(len(levels), 4)
        self.assertEqual(len(set(levels)), 1)


    def test_no_previous_session_inside_the_depth_is_a_blank_reading(self):
        # 100 Crypto M5 bars all inside one NY session: the profile publishes,
        # the naked POC simply is not part of the set - never a gate (15.5).
        end = at(2026, 6, 10, 20, 55)  # the NY session's own last M5 bar
        bars = []
        for offset in range(100):
            bars.append(
                flat_bar(
                    end - timedelta(minutes=5 * offset),
                    1.1000 + 0.00001 * offset,
                    100.0 + offset,
                )
            )
        tracker = replay(
            VolumeFlowTracker(
                asset_class="Crypto", timeframe="M5", volatility=LOW
            ),
            bars,
        )
        self.assertEqual(tracker.reading.session_name, "NY")
        self.assertEqual(tracker.reading.bars_since_session_start, 100)
        self.assertTrue(tracker.reading.has_profile)
        self.assertIsNone(tracker.reading.prior_poc)
        self.assertFalse(tracker.reading.prior_poc_naked)
        self.assertNotEqual(tracker.reading.magnet_kind, MAGNET_NAKED_POC)
        self.assertNotIn("naked POC", tracker.clause())


class MagnetTests(unittest.TestCase):
    def test_members_follow_the_15_5_priority_order(self):
        members = magnet_members(
            has_profile=True,
            poc=1.1000,
            vah=1.1100,
            val=1.0900,
            prior_poc=1.1050,
            naked=True,
        )
        self.assertEqual(
            [kind for kind, _ in members],
            [MAGNET_NAKED_POC, MAGNET_POC, MAGNET_VAH, MAGNET_VAL],
        )

    def test_nearest_member_wins_and_ties_prefer_the_earlier_candidate(self):
        members = [
            (MAGNET_NAKED_POC, 1.1040),
            (MAGNET_POC, 1.1060),
            (MAGNET_VAH, 1.1100),
            (MAGNET_VAL, 1.0900),
        ]
        self.assertEqual(published_magnet(members, 1.1050), (MAGNET_NAKED_POC, 1.1040))
        self.assertEqual(published_magnet(members, 1.1070), (MAGNET_POC, 1.1060))

    def test_only_present_members_are_published(self):
        members = magnet_members(
            has_profile=False,
            poc=None,
            vah=None,
            val=None,
            prior_poc=1.1050,
            naked=True,
        )
        self.assertEqual(members, [(MAGNET_NAKED_POC, 1.1050)])
        self.assertIsNone(published_magnet([], 1.1000))

    def test_not_naked_prior_poc_is_not_a_member(self):
        members = magnet_members(
            has_profile=True,
            poc=1.1000,
            vah=1.1100,
            val=1.0900,
            prior_poc=1.1050,
            naked=False,
        )
        self.assertNotIn(MAGNET_NAKED_POC, [kind for kind, _ in members])

    def test_published_magnet_is_the_trackers_own_member(self):
        current = [flat_bar(at(2026, 6, 10, 11, 5 + 5 * step), 1.1000, 100.0)
                   for step in range(2)]
        prior = [
            flat_bar(at(2026, 6, 10, 6, 5), 1.0990, 50.0),
            flat_bar(at(2026, 6, 10, 6, 0), 1.0992, 100.0),
        ]
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), current + prior
        )
        # The close sits on 1.1000 and the naked prior POC is far below, so the
        # naked POC is the nearest member while the profile is not yet readable.
        self.assertEqual(tracker.reading.magnet_kind, MAGNET_NAKED_POC)


#=== 15.6 CVD ===============================================================

class CvdTests(unittest.TestCase):
    def test_close_position_delta(self):
        self.assertAlmostEqual(
            bar_delta(mkbar(at(2026, 6, 10, 1, 0), 1.1000, 1.0900, 1.1000, 100.0)),
            100.0,
        )
        self.assertAlmostEqual(
            bar_delta(mkbar(at(2026, 6, 10, 1, 0), 1.1000, 1.0900, 1.0900, 100.0)),
            -100.0,
        )
        self.assertAlmostEqual(
            bar_delta(mkbar(at(2026, 6, 10, 1, 0), 1.1000, 1.0900, 1.0950, 100.0)),
            0.0,
        )
        self.assertAlmostEqual(
            bar_delta(mkbar(at(2026, 6, 10, 1, 0), 1.1000, 1.1000, 1.1000, 100.0)),
            0.0,
        )

    def test_classification_thresholds_are_inclusive(self):
        self.assertEqual(CVD_FLIP, 0.25)
        at_high = mkbar(at(2026, 6, 10, 1, 0), 1.1000, 1.0900, 1.1000, 100.0)
        at_low = mkbar(at(2026, 6, 10, 1, 0), 1.1000, 1.0900, 1.0900, 100.0)
        self.assertEqual(classify_flow([at_high, at_high]), 1)
        self.assertEqual(classify_flow([at_low, at_low]), -1)

        # Exactly ±0.25 x window volume is still a reading (inclusive band).
        # The prices are binary-exact so the boundary is exact, not rounded.
        quarter_up = [
            mkbar(at(2026, 6, 10, 0, 55), 1.0, 0.5, 1.0, 25.0),
            mkbar(at(2026, 6, 10, 0, 50), 1.0, 0.5, 0.75, 75.0),
        ]
        self.assertEqual(classify_flow(quarter_up), 1)
        quarter_down = [
            mkbar(at(2026, 6, 10, 0, 55), 1.0, 0.5, 0.5, 25.0),
            mkbar(at(2026, 6, 10, 0, 50), 1.0, 0.5, 0.75, 75.0),
        ]
        self.assertEqual(classify_flow(quarter_down), -1)

        # Just inside the band is flat.
        inside = [
            mkbar(at(2026, 6, 10, 0, 55), 1.0, 0.5, 1.0, 24.0),
            mkbar(at(2026, 6, 10, 0, 50), 1.0, 0.5, 0.75, 76.0),
        ]
        self.assertEqual(classify_flow(inside), 0)

    def test_fewer_than_two_bars_or_zero_volume_read_nothing(self):
        self.assertIsNone(classify_flow([]))
        self.assertIsNone(
            classify_flow([mkbar(at(2026, 6, 10, 1, 0), 1.1000, 1.0900, 1.1000, 10.0)])
        )
        zero = [
            mkbar(at(2026, 6, 10, 1, 0), 1.1000, 1.0900, 1.1000, 0.0),
            mkbar(at(2026, 6, 10, 0, 55), 1.1000, 1.0900, 1.1000, 0.0),
        ]
        self.assertIsNone(classify_flow(zero))

    def test_the_session_cvd_sum_resets_at_the_anchor(self):
        prior = mkbar(at(2026, 6, 10, 6, 5), 1.0, 0.5, 0.5, 300.0)   # -300
        current = [
            mkbar(at(2026, 6, 10, 11, 5), 1.0, 0.5, 0.75, 100.0),  # 0
            mkbar(at(2026, 6, 10, 11, 0), 1.0, 0.5, 1.0, 100.0),   # +100
        ]
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), current + [prior]
        )
        self.assertEqual(tracker.reading.session_name, "NY")
        self.assertAlmostEqual(tracker.session_cvd, 100.0)
        self.assertAlmostEqual(tracker.session_volume, 200.0)

        london_only = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW), [prior]
        )
        self.assertAlmostEqual(london_only.session_cvd, -300.0)

    def test_a_young_session_publishes_no_cvd_reading(self):
        tracker = replay(
            VolumeFlowTracker(timeframe="M5", volatility=LOW),
            [mkbar(at(2026, 6, 10, 11, 30), 1.1000, 1.0900, 1.1000, 100.0)],
        )
        self.assertFalse(tracker.reading.flow_reading)
        self.assertEqual(tracker.reading.flow_direction, 0)

    def test_flip_detection_journals_every_mirror(self):
        tracker = VolumeFlowTracker(timeframe="M5", volatility=LOW)
        # One NY session, oldest to newest: the first classification (up) is a
        # reading, so the two real mirrors are up -> flat and flat -> up.
        bars = [
            mkbar(at(2026, 6, 10, 11, 0), 1.0, 0.5, 1.0, 100.0),
            mkbar(at(2026, 6, 10, 11, 5), 1.0, 0.5, 0.5, 100.0),
            mkbar(at(2026, 6, 10, 11, 10), 1.0, 0.5, 1.0, 100.0),
            mkbar(at(2026, 6, 10, 11, 15), 1.0, 0.5, 0.75, 100.0),
        ]
        for index in (3, 2, 1, 0):
            tracker.advance(bars, index, 0.0010, bar_sequence=10 - index)
        flips = [line for line in tracker.journal if "Flow CVD" in line]
        self.assertEqual(len(flips), 2, tracker.journal)
        self.assertIn("up -> flat", flips[0])
        self.assertIn("flat -> up", flips[1])
        self.assertIn("x window volume", flips[0])
        self.assertEqual(tracker.reading.flow_direction, 1)

    def test_flip_detection_mirrors_down_to_up(self):
        tracker = VolumeFlowTracker(timeframe="M5", volatility=LOW)
        bars = [
            mkbar(at(2026, 6, 10, 11, 0), 1.0, 0.5, 1.0, 100.0),
            mkbar(at(2026, 6, 10, 11, 5), 1.0, 0.5, 1.0, 100.0),
            mkbar(at(2026, 6, 10, 11, 10), 1.0, 0.5, 0.5, 100.0),
            mkbar(at(2026, 6, 10, 11, 15), 1.0, 0.5, 0.75, 100.0),
        ]
        for index in (3, 2, 1, 0):
            tracker.advance(bars, index, 0.0010, bar_sequence=10 - index)
        flips = [line for line in tracker.journal if "Flow CVD" in line]
        self.assertEqual(len(flips), 2, tracker.journal)
        self.assertIn("down -> flat", flips[0])
        self.assertIn("flat -> up", flips[1])
        self.assertEqual(tracker.reading.flow_direction, 1)
        self.assertEqual(tracker.status(), "Watching — CVD turned up")

    def test_the_session_never_flips_on_its_first_classification(self):
        bars = [
            mkbar(at(2026, 6, 10, 11, 10), 1.1000, 1.0900, 1.1000, 100.0),
            mkbar(at(2026, 6, 10, 6, 5), 1.1000, 1.0900, 1.0900, 100.0),
            mkbar(at(2026, 6, 10, 6, 0), 1.1000, 1.0900, 1.0900, 100.0),
        ]
        tracker = replay(VolumeFlowTracker(timeframe="M5", volatility=LOW), bars)
        self.assertEqual(
            [line for line in tracker.journal if "Flow CVD" in line], []
        )
        self.assertEqual(CVD_WINDOW, 10)


#=== 15.7 volumeFlowScore ===================================================

class VolumeFlowScoreTests(unittest.TestCase):
    def test_weights_sum_to_exactly_one(self):
        self.assertEqual(
            WEIGHT_CONTROL + WEIGHT_FAIR + WEIGHT_VALUE + WEIGHT_MAGNET, 1.0
        )

    def test_flat_or_unready_scores_zero(self):
        common = dict(
            net_delta=0.0,
            window_volume=100.0,
            has_vwap=True,
            price_vs_vwap=SIDE_ABOVE,
            has_profile=True,
            close=1.1000,
            val=1.0950,
            vah=1.1050,
            atr_value=0.0010,
            members=[(MAGNET_VAH, 1.1010)],
        )
        self.assertEqual(volume_flow_score(ready=True, flow_direction=0, **common), 0.0)
        self.assertEqual(volume_flow_score(ready=False, flow_direction=1, **common), 0.0)

    def test_control_scores_full_at_half_the_window_volume(self):
        for direction, net in ((1, 50.0), (-1, -50.0)):
            score = volume_flow_score(
                ready=True,
                flow_direction=direction,
                net_delta=net,
                window_volume=100.0,
                has_vwap=False,
                price_vs_vwap=SIDE_NONE,
                has_profile=False,
                close=1.1000,
                val=None,
                vah=None,
                atr_value=0.0010,
                members=[],
            )
            self.assertAlmostEqual(score, WEIGHT_CONTROL)
        self.assertEqual(CONTROL_SCALE, 0.5)

    def test_fair_price_term_is_direction_sensitive(self):
        def score(direction, side):
            return volume_flow_score(
                ready=True,
                flow_direction=direction,
                net_delta=0.0,
                window_volume=100.0,
                has_vwap=True,
                price_vs_vwap=side,
                has_profile=False,
                close=1.1000,
                val=None,
                vah=None,
                atr_value=0.0010,
                members=[],
            )

        self.assertAlmostEqual(score(1, SIDE_ABOVE), WEIGHT_FAIR)
        self.assertAlmostEqual(score(1, SIDE_BELOW), 0.0)
        self.assertAlmostEqual(score(-1, SIDE_BELOW), WEIGHT_FAIR)
        self.assertAlmostEqual(score(-1, SIDE_ABOVE), 0.0)
        self.assertAlmostEqual(score(1, SIDE_NONE), 0.0)

    def test_value_area_three_levels_and_its_mirror(self):
        def score(direction, close):
            return volume_flow_score(
                ready=True,
                flow_direction=direction,
                net_delta=0.0,
                window_volume=100.0,
                has_vwap=False,
                price_vs_vwap=SIDE_NONE,
                has_profile=True,
                close=close,
                val=1.0950,
                vah=1.1050,
                atr_value=0.0010,
                members=[],
            )

        self.assertAlmostEqual(score(1, 1.0900), WEIGHT_VALUE)
        self.assertAlmostEqual(score(1, 1.0950), WEIGHT_VALUE / 2)
        self.assertAlmostEqual(score(1, 1.1000), WEIGHT_VALUE / 2)
        self.assertAlmostEqual(score(1, 1.1060), 0.0)
        self.assertAlmostEqual(score(-1, 1.1100), WEIGHT_VALUE)
        self.assertAlmostEqual(score(-1, 1.1000), WEIGHT_VALUE / 2)
        self.assertAlmostEqual(score(-1, 1.0900), 0.0)

    def test_magnet_proximity_scale_and_direction(self):
        # 15.5: with no profile reading the value and magnet terms are 0, so
        # the proximity term is only reachable with a profile reading present.
        no_profile = dict(
            ready=True,
            flow_direction=1,
            net_delta=0.0,
            window_volume=100.0,
            has_vwap=False,
            price_vs_vwap=SIDE_NONE,
            has_profile=False,
            close=1.1000,
            val=None,
            vah=None,
            atr_value=0.0010,
        )
        self.assertAlmostEqual(
            volume_flow_score(members=[(MAGNET_POC, 1.1000)], **no_profile), 0.0
        )

        common = dict(
            no_profile,
            has_profile=True,
            val=1.0900,
            vah=1.1100,
            close=1.1000,
        )
        # Three ATR away scores nothing, a level on the close scores full, and
        # the term is linear in between (1 ATR -> 2/3). The close sits inside
        # the value area throughout, so the value term contributes its half.
        self.assertAlmostEqual(
            volume_flow_score(members=[(MAGNET_VAH, 1.1030)], **common),
            0.5 * WEIGHT_VALUE,
        )
        self.assertAlmostEqual(
            volume_flow_score(members=[(MAGNET_POC, 1.1000)], **common),
            WEIGHT_MAGNET + 0.5 * WEIGHT_VALUE,
        )
        self.assertAlmostEqual(
            volume_flow_score(members=[(MAGNET_VAH, 1.1010)], **common),
            WEIGHT_MAGNET * (2.0 / 3.0) + 0.5 * WEIGHT_VALUE,
        )
        # A magnet behind a +1 flow is not in that direction at all.
        self.assertIsNone(nearest_directional_magnet([(MAGNET_VAL, 1.0900)], 1.1000, 1))
        self.assertIsNotNone(nearest_directional_magnet([(MAGNET_VAL, 1.0900)], 1.1000, -1))
        self.assertEqual(MAGNET_ATRS, 3.0)

    def test_every_term_stays_inside_zero_and_one(self):
        extremes = (
            (1, 10_000.0, SIDE_ABOVE, 1.1000, 1.1000, 1.1000, 0.0001),
            (-1, -10_000.0, SIDE_BELOW, 1.0900, 1.0950, 1.1050, 0.0001),
            (1, -10_000.0, SIDE_ABOVE, 1.2000, 1.0950, 1.1050, 5.0),
        )
        for direction, net, side, close, val, vah, atr in extremes:
            score = volume_flow_score(
                ready=True,
                flow_direction=direction,
                net_delta=net,
                window_volume=100.0,
                has_vwap=True,
                price_vs_vwap=side,
                has_profile=True,
                close=close,
                val=val,
                vah=vah,
                atr_value=atr,
                members=[(MAGNET_POC, 1.1000), (MAGNET_VAH, 1.1200)],
            )
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


#=== 15.11 parameters =======================================================

class VolumeFlowParametersTests(unittest.TestCase):
    def test_layer_1_matrix(self):
        expected = {
            "Forex Major": (200, 200, 300),
            "Forex Cross": (200, 200, 300),
            "Generic": (200, 200, 300),
            "Metals": (150, 200, 300),
            "Indices": (150, 200, 250),
            "Crypto": (100, 150, 200),
        }
        for asset_class, columns in expected.items():
            for volatility, value in zip((LOW, NORMAL, HIGH), columns):
                self.assertEqual(
                    matrix_window(asset_class, volatility),
                    value,
                    (asset_class, volatility),
                )

    def test_layer_2_scales_the_profile_window_only(self):
        # 150 x 1.25 = 187.5 -> 188, half away from zero (never Python round()).
        self.assertEqual(profile_window("Metals", LOW, "M15"), 188)
        self.assertEqual(profile_window("Indices", LOW, "M15"), 188)
        self.assertEqual(profile_window("Crypto", NORMAL, "M15"), 188)
        # 300 x 1.5 = 450 -> clamped to 400.
        self.assertEqual(profile_window("Forex Major", HIGH, "M30"), 400)
        self.assertEqual(WINDOW_MAX, 400)
        # 250 x 1.5 = 375 stays under the clamp.
        self.assertEqual(profile_window("Indices", HIGH, "M30"), 375)
        # 250 x 1.25 = 312.5 -> 313, half away from zero again. Python's own
        # round() is banker's rounding and would answer 312 - never used here.
        self.assertEqual(profile_window("Indices", HIGH, "M15"), 313)
        self.assertEqual(round(312.5), 312)
        self.assertEqual(round_half_away(312.5), 313)
        self.assertEqual(profile_window("Metals", HIGH, "M30"), 400)

    def test_resolved_window_table(self):
        expected = {
            ("Forex Major", LOW): (200, 250, 300),
            ("Forex Major", NORMAL): (200, 250, 300),
            ("Forex Major", HIGH): (300, 375, 400),
            ("Forex Cross", NORMAL): (200, 250, 300),
            ("Generic", HIGH): (300, 375, 400),
            ("Metals", LOW): (150, 188, 225),
            ("Metals", NORMAL): (200, 250, 300),
            ("Metals", HIGH): (300, 375, 400),
            # 15.11 Layer 1 gives Indices its own row (150 / 200 / 250), which
            # is the shorter High column its own sentence justifies.
            ("Indices", LOW): (150, 188, 225),
            ("Indices", NORMAL): (200, 250, 300),
            ("Indices", HIGH): (250, 313, 375),
            ("Crypto", LOW): (100, 125, 150),
            ("Crypto", NORMAL): (150, 188, 225),
            ("Crypto", HIGH): (200, 250, 300),
        }
        for (asset_class, volatility), columns in expected.items():
            for timeframe, value in zip(("M5", "M15", "M30"), columns):
                self.assertEqual(
                    profile_window(asset_class, volatility, timeframe),
                    value,
                    (asset_class, volatility, timeframe),
                )

    def test_every_resolved_window_is_clamped(self):
        for asset_class in ASSET_CLASSES:
            for volatility in VOLATILITIES:
                for timeframe in ("M5", "M15", "M30"):
                    value = profile_window(asset_class, volatility, timeframe)
                    self.assertGreaterEqual(value, WINDOW_MIN)
                    self.assertLessEqual(value, WINDOW_MAX)

    def test_history_gate_is_the_three_term_max(self):
        self.assertEqual(vf_history_required("Forex Major", HIGH, "M5"), 302)
        self.assertEqual(vf_history_required("Forex Major", HIGH, "M15"), 377)
        self.assertEqual(vf_history_required("Forex Major", HIGH, "M30"), 402)
        for timeframe, worst in (("M5", 302), ("M15", 377), ("M30", 402)):
            self.assertEqual(
                combined_history_required("Forex Major", HIGH, timeframe), worst
            )
        for timeframe, normal in (("M5", 250), ("M15", 300), ("M30", 350)):
            self.assertEqual(
                combined_history_required("Forex Major", NORMAL, timeframe), normal
            )
        for asset_class in ASSET_CLASSES:
            for volatility in VOLATILITIES:
                for timeframe in ("M5", "M15", "M30"):
                    self.assertEqual(
                        combined_history_required(asset_class, volatility, timeframe),
                        max(
                            supertrend_history_required(timeframe),
                            smc_history_required(asset_class, volatility, timeframe),
                            vf_history_required(asset_class, volatility, timeframe),
                        ),
                    )

    def test_fetch_depth_covers_the_longest_session(self):
        for asset_class in ASSET_CLASSES:
            for volatility in VOLATILITIES:
                for timeframe in ("M5", "M15", "M30"):
                    self.assertEqual(
                        vf_fetch_depth(asset_class, volatility, timeframe),
                        profile_window(asset_class, volatility, timeframe)
                        + SESSION_DEPTH
                        + FETCH_BUFFER,
                    )
        self.assertEqual(SESSION_DEPTH, 160)
        self.assertEqual(FETCH_BUFFER, 10)
        # The 13-hour Asia session is 156 M5 bars; the depth always covers it.
        self.assertGreaterEqual(SESSION_DEPTH, 156)

    def test_window_change_pause_and_recompute(self):
        bars = wave_series(320)
        tracker = VolumeFlowTracker(asset_class="Forex Major", timeframe="M5")
        for index in range(len(bars) - 1, -1, -1):
            # LOW for the older bars, HIGH for the newest 60: one change only.
            tracker.volatility = LOW if index >= 60 else HIGH
            tracker.advance(bars, index, 0.0010, bar_sequence=len(bars) - index)
        changes = [line for line in tracker.journal if "Profile window" in line]
        self.assertEqual(len(changes), 1, tracker.journal)
        self.assertIn("200 -> 300 closed bars", changes[0])

        fresh = VolumeFlowTracker(asset_class="Forex Major", timeframe="M5")
        replay(fresh, bars, volatility=HIGH, write_journal=False)
        self.assertEqual(tracker.window, 300)
        self.assertEqual(
            (tracker.reading.poc, tracker.reading.vah, tracker.reading.val),
            (fresh.reading.poc, fresh.reading.vah, fresh.reading.val),
        )
        self.assertAlmostEqual(
            tracker.reading.volume_flow_score, fresh.reading.volume_flow_score
        )
        self.assertAlmostEqual(
            tracker.reading.volume_flow_score, fresh.reading.volume_flow_score, places=12
        )

    def test_pause_uses_the_existing_helper(self):
        self.assertTrue(can_change_at(10, 10 - 3))
        self.assertFalse(can_change_at(10, 10 - 2))


#=== 15.8 the MTF mapping ===================================================

class MtfMappingTests(unittest.TestCase):
    def test_the_fixed_mapping(self):
        self.assertEqual(mtf_timeframe("M5"), "M15")
        self.assertEqual(mtf_timeframe("M15"), "H1")
        self.assertEqual(mtf_timeframe("M30"), "H4")

    def test_other_timeframes_have_no_htf(self):
        for timeframe in ("M1", "H1", "H4", "D1", "W1", "MN1"):
            self.assertIsNone(mtf_timeframe(timeframe))

    def test_history_required_is_the_max_of_the_two_existing_functions(self):
        self.assertEqual(mtf_history_required("M15"), 300)
        self.assertEqual(mtf_history_required("H1"), MTF_HISTORY_H1)
        self.assertEqual(mtf_history_required("H4"), MTF_HISTORY_H1)
        for htf in ("M15", "H1", "H4"):
            self.assertEqual(
                mtf_history_required(htf),
                max(supertrend_history_required(htf), smc_history_required_worst(htf)),
            )
            self.assertEqual(
                mtf_fetch_count(htf), mtf_history_required(htf) + MTF_FETCH_BUFFER
            )
        self.assertEqual(MTF_FETCH_BUFFER, 10)

    def test_the_twin_measurements(self):
        rates = htf_series(40)
        facts = htf_facts(40, direction=1)
        measurements = build_measurements(rates, 5, facts[5])
        self.assertIsNotNone(measurements)
        self.assertEqual(measurements.direction, 1)
        self.assertAlmostEqual(measurements.atr_ratio, facts[5].atr_value / 0.0010)
        self.assertTrue(measurements.bands_expanding)  # sin(1) > 0
        self.assertFalse(build_measurements(rates, 25, facts[25]).bands_expanding)
        self.assertEqual(
            build_measurements(rates, 5, htf_facts(40, direction=-1)[5]).direction, -1
        )
        self.assertEqual(
            build_measurements(rates, 5, htf_facts(40, direction=0)[5]).direction, 0
        )
        # The ER needs ``index + period`` inside the array: no partial read.
        self.assertIsNone(build_measurements(rates, 30, facts[30]))


#=== 15.8 / 15.9 the HTF walk ===============================================

class MtfWalkTests(unittest.TestCase):
    def _walk(self, direction=1, count=270):
        rates = htf_series(count)
        facts = htf_facts(count, direction=direction)
        tracker = MtfTracker("M15", "Forex Major", NORMAL)
        tracker.walk(rates, facts)
        return tracker, rates, facts

    def test_walk_reports_the_htf_state_and_the_phase_2_regime(self):
        tracker, rates, facts = self._walk()
        self.assertTrue(tracker.evaluated)
        self.assertIn(
            tracker.regime.stable, (BULL, BEAR, RANGING, VOLATILE, TRANSITION)
        )
        self.assertIn(tracker.supertrend.direction, (-1, 0, 1))
        self.assertIn(tracker.smc.state.bias, (-1, 0, 1))

        # The regime is exactly a fresh Phase-2 tracker over the same inputs,
        # walked from the same oldest evaluated HTF bar.
        reference = RegimeTracker()
        required = mtf_history_required("H1")
        start = len(rates) - required
        previous = None
        for index in range(start, -1, -1):
            measurements = build_measurements(rates, index, facts[index])
            after_gap = (
                previous is not None
                and (rates[index].time - previous).total_seconds() > 2 * 3600
            )
            reference.advance(measurements, index == start or after_gap)
            previous = rates[index].time
        self.assertEqual(tracker.regime.stable, reference.stable)

    def test_walk_evaluates_the_required_number_of_bars(self):
        rates = htf_series(270)
        facts = htf_facts(270)
        tracker = MtfTracker("M15", "Forex Major", NORMAL)
        tracker.walk(rates, facts)
        self.assertEqual(tracker.reading.htf_name, "H1")
        self.assertEqual(
            len([line for line in tracker.journal if "MTF context" in line]), 0
        )

    def test_replaying_the_same_htf_bars_is_identical(self):
        first, rates, facts = self._walk()
        second = MtfTracker("M15", "Forex Major", NORMAL)
        second.walk(rates, facts)
        self.assertEqual(first.regime.stable, second.regime.stable)
        self.assertEqual(first.supertrend.direction, second.supertrend.direction)
        self.assertEqual(first.supertrend.multiplier, second.supertrend.multiplier)
        self.assertEqual(first.smc.state.bias, second.smc.state.bias)
        self.assertEqual(first.smc.state.zone, second.smc.state.zone)

    def test_ready_publishes_and_the_score_stays_bounded(self):
        tracker, rates, facts = self._walk()
        tracker.advance(
            rates,
            facts,
            htf_bar_time=rates[0].time,
            chart_sequence=100,
            chart_direction=tracker.supertrend.direction,
            chart_bias=tracker.smc.state.bias,
            force_rebuild=True,
        )
        self.assertTrue(tracker.reading.ready)
        self.assertEqual(tracker.reading.htf, "H1")
        self.assertEqual(tracker.reading.htf_bars_fetched, len(rates))
        self.assertGreaterEqual(tracker.reading.mtf_score, 0.0)
        self.assertLessEqual(tracker.reading.mtf_score, 1.0)
        self.assertIn(
            tracker.reading.htf_regime, (BULL, BEAR, RANGING, VOLATILE, TRANSITION)
        )
        self.assertIn("MTF context replayed", " ".join(tracker.journal))
        self.assertIn("{} closed bars".format(len(rates)), tracker.journal[-1])
        self.assertIn("score ", tracker.journal[-1])

    def test_the_published_score_is_stable_and_direction_sensitive(self):
        rates = htf_series(270)
        facts = htf_facts(270)

        def publish(chart_direction):
            tracker = MtfTracker("M15", "Forex Major", NORMAL)
            tracker.advance(
                rates,
                facts,
                htf_bar_time=rates[0].time,
                chart_sequence=50,
                chart_direction=chart_direction,
                chart_bias=1,
            )
            return tracker

        first = publish(1)
        second = publish(1)
        self.assertEqual(
            round(first.reading.mtf_score, 12), round(second.reading.mtf_score, 12)
        )
        self.assertEqual(first.reading.htf_zone, second.reading.htf_zone)
        self.assertEqual(first.reading.htf_bar_time, second.reading.htf_bar_time)

        # Whichever way the HTF itself points, agreeing beats disagreeing.
        htf_direction = first.reading.htf_direction
        self.assertNotEqual(htf_direction, 0)
        agreeing = publish(htf_direction)
        disagreeing = publish(-htf_direction)
        self.assertGreater(agreeing.reading.mtf_score, disagreeing.reading.mtf_score)
        self.assertLess(disagreeing.reading.mtf_score, agreeing.reading.mtf_score)
        self.assertEqual(agreeing.reading.agrees, 1)
        self.assertEqual(disagreeing.reading.agrees, -1)
        self.assertIn("agrees", agreeing.clause(agreeing.reading.chart_direction))
        self.assertIn("disagrees", disagreeing.clause(-htf_direction))

    def test_not_ready_publishes_nothing_at_all(self):
        rates = htf_series(60)  # far below EmttMtfHistoryRequired
        facts = htf_facts(60)
        tracker = MtfTracker("M15", "Forex Major", NORMAL)
        self.assertFalse(
            tracker.advance(
                rates,
                facts,
                htf_bar_time=rates[0].time,
                chart_sequence=1,
                chart_direction=1,
                chart_bias=1,
            )
        )
        self.assertFalse(tracker.reading.ready)
        self.assertEqual(tracker.reading.mtf_score, 0.0)
        self.assertEqual(tracker.clause(1), "")
        self.assertEqual(tracker.status(), "")
        self.assertEqual(
            [line for line in tracker.journal if "MTF context replayed" in line], []
        )

    def test_between_htf_closes_the_state_is_constant(self):
        rates = htf_series(270)
        facts = htf_facts(270)
        tracker = MtfTracker("M15", "Forex Major", NORMAL)
        tracker.advance(
            rates,
            facts,
            htf_bar_time=rates[0].time,
            chart_sequence=10,
            chart_direction=1,
            chart_bias=1,
        )
        before = tracker.reading
        tracker.advance(
            rates,
            facts,
            htf_bar_time=rates[0].time,  # same last closed HTF bar
            chart_sequence=11,
            chart_direction=-1,
            chart_bias=-1,
        )
        self.assertEqual(tracker.reading.current_sequence, 11)
        self.assertEqual(tracker.reading.mtf_score, before.mtf_score)
        self.assertEqual(tracker.reading.htf_direction, before.htf_direction)
        self.assertEqual(
            len([line for line in tracker.journal if "MTF context replayed" in line]), 1
        )
        # The agreement word is recomposed live from the passed-in direction.
        if tracker.reading.htf_direction != 0:
            opposite = -tracker.reading.htf_direction
            self.assertIn("disagrees", tracker.clause(opposite))
            self.assertIn("agrees", tracker.clause(tracker.reading.htf_direction))

    def test_a_new_htf_bar_advances_once_and_journals_the_facts(self):
        rates = htf_series(270)
        facts = htf_facts(270)
        tracker = MtfTracker("M15", "Forex Major", NORMAL)
        tracker.advance(
            rates,
            facts,
            htf_bar_time=rates[0].time,
            chart_sequence=10,
            chart_direction=1,
            chart_bias=1,
        )
        fresh = htf_series(271, end=at(2026, 6, 10, 13, 0))
        fresh_facts = htf_facts(271)
        self.assertEqual(fresh[1].time, rates[0].time)
        self.assertTrue(
            tracker.advance(
                fresh,
                fresh_facts,
                htf_bar_time=fresh[0].time,
                chart_sequence=11,
                chart_direction=1,
                chart_bias=1,
            )
        )
        self.assertEqual(tracker.reading.htf_bar_time, fresh[0].time)
        self.assertEqual(tracker.reading.htf_bars_fetched, 271)
        self.assertEqual(
            len([line for line in tracker.journal if "MTF context replayed" in line]), 1
        )


class MtfScoreTests(unittest.TestCase):
    def score(self, **overrides):
        values = dict(
            ready=True,
            htf_regime=BULL,
            htf_direction=1,
            chart_direction=1,
            htf_bias=1,
            chart_bias=1,
        )
        values.update(overrides)
        return mtf_score(**values)

    def test_weights_sum_to_exactly_one(self):
        self.assertEqual(
            MTF_WEIGHT_DIRECTION + MTF_WEIGHT_REGIME + MTF_WEIGHT_STRUCTURE, 1.0
        )

    def test_direction_term(self):
        self.assertAlmostEqual(self.score(), 1.0)
        self.assertAlmostEqual(
            self.score(htf_direction=-1), 1.0 - MTF_WEIGHT_DIRECTION
        )
        self.assertAlmostEqual(self.score(chart_direction=0), 1.0 - MTF_WEIGHT_DIRECTION)
        self.assertAlmostEqual(self.score(htf_direction=0), 1.0 - MTF_WEIGHT_DIRECTION)

    def test_regime_term(self):
        self.assertAlmostEqual(
            self.score(htf_regime=TRANSITION),
            1.0 - MTF_WEIGHT_REGIME + 0.5 * MTF_WEIGHT_REGIME,
        )
        for regime in (RANGING, VOLATILE, CLOSED, UNKNOWN):
            self.assertAlmostEqual(
                self.score(htf_regime=regime), 1.0 - MTF_WEIGHT_REGIME
            )

    def test_structure_term(self):
        self.assertAlmostEqual(
            self.score(htf_bias=-1), 1.0 - MTF_WEIGHT_STRUCTURE
        )
        self.assertAlmostEqual(
            self.score(htf_bias=0), 1.0 - 0.5 * MTF_WEIGHT_STRUCTURE
        )
        self.assertAlmostEqual(
            self.score(chart_bias=0), 1.0 - 0.5 * MTF_WEIGHT_STRUCTURE
        )

    def test_not_ready_scores_zero(self):
        self.assertEqual(self.score(ready=False), 0.0)

    def test_bounds(self):
        for regime in (BULL, BEAR, RANGING, VOLATILE, TRANSITION, CLOSED, UNKNOWN):
            for htf_direction in (-1, 0, 1):
                for chart_direction in (-1, 0, 1):
                    for htf_bias in (-1, 0, 1):
                        for chart_bias in (-1, 0, 1):
                            value = self.score(
                                htf_regime=regime,
                                htf_direction=htf_direction,
                                chart_direction=chart_direction,
                                htf_bias=htf_bias,
                                chart_bias=chart_bias,
                            )
                            self.assertGreaterEqual(value, 0.0)
                            self.assertLessEqual(value, 1.0)


#=== 15.10 panel text =======================================================

class PanelTextTests(unittest.TestCase):
    def _reading_tracker(self, **fields):
        tracker = VolumeFlowTracker(timeframe="M5", volatility=LOW)
        reading = tracker.reading
        reading.ready = True
        reading.has_vwap = True
        reading.price_vs_vwap = SIDE_ABOVE
        reading.has_profile = True
        reading.magnet_kind = MAGNET_POC
        reading.magnet_price = 1.09020
        reading.poc = 1.09020
        reading.vah = 1.09500
        reading.val = 1.08500
        reading.flow_reading = True
        reading.flow_direction = 1
        for name, value in fields.items():
            setattr(reading, name, value)
        return tracker

    def test_volume_flow_clause_formats(self):
        self.assertEqual(
            self._reading_tracker().clause(), "CVD up, above VWAP, POC 1.09020"
        )
        self.assertEqual(
            self._reading_tracker(
                magnet_kind=MAGNET_NAKED_POC,
                magnet_price=1.08740,
                flow_direction=-1,
                price_vs_vwap=SIDE_BELOW,
            ).clause(),
            "CVD down, below VWAP, naked POC 1.08740",
        )
        self.assertEqual(
            self._reading_tracker(
                magnet_kind=MAGNET_VAH, magnet_price=1.09500
            ).clause(),
            "CVD up, above VWAP, VAH 1.09500",
        )
        self.assertEqual(
            self._reading_tracker(
                magnet_kind=MAGNET_VAL, magnet_price=1.08500
            ).clause(),
            "CVD up, above VWAP, VAL 1.08500",
        )
        self.assertEqual(
            self._reading_tracker(
                flow_direction=0, has_profile=False, magnet_kind=""
            ).clause(),
            "CVD flat, above VWAP",
        )

    def test_volume_flow_clause_omission_rules(self):
        self.assertEqual(self._reading_tracker(ready=False).clause(), "")
        self.assertEqual(
            self._reading_tracker(flow_reading=False).clause(),
            "above VWAP, POC 1.09020",
        )
        self.assertEqual(
            self._reading_tracker(has_vwap=False).clause(), "CVD up, POC 1.09020"
        )
        self.assertEqual(
            self._reading_tracker(has_profile=False, magnet_kind="").clause(),
            "CVD up, above VWAP",
        )
        self.assertEqual(
            self._reading_tracker(
                flow_reading=False, has_vwap=False, has_profile=False, magnet_kind=""
            ).clause(),
            "",
        )

    def test_the_clause_uses_the_symbols_own_digits(self):
        tracker = self._reading_tracker()
        tracker.digits = 3
        self.assertEqual(tracker.clause(), "CVD up, above VWAP, POC 1.090")
        tracker.digits = 2
        self.assertEqual(tracker.clause(), "CVD up, above VWAP, POC 1.09")

    def test_volume_flow_clause_shows_at_most_three_parts(self):
        parts = self._reading_tracker().clause().split(", ")
        self.assertEqual(len(parts), 3)

    def test_appending_keeps_an_empty_clause_invisible(self):
        self.assertEqual(append_row9("regime", ""), "regime")
        self.assertEqual(append_row9("regime", "CVD up"), "regime | CVD up")
        self.assertEqual(append_row9("--", "CVD up"), "CVD up")
        self.assertEqual(append_row9("", "CVD up"), "CVD up")

    def test_mtf_clause_formats(self):
        cases = (
            (BULL, 1, "", 1, "H1 trending up, agrees"),
            (BEAR, -1, "", -1, "H1 trending down, agrees"),
            (RANGING, -1, "Premium", 1, "H1 ranging, disagrees, H1 Premium"),
            (RANGING, 1, "Discount", 1, "H1 ranging, agrees, H1 Discount"),
            (RANGING, 0, "Equilibrium", 1, "H1 ranging, H1 Equilibrium"),
            (VOLATILE, 0, "", 0, "H1 volatile"),
            (TRANSITION, 0, "", 0, "H1 transition"),
            (CLOSED, 0, "", -1, "H1 closed"),
        )
        for regime, htf_direction, zone, chart_direction, expected in cases:
            self.assertEqual(
                mtf_clause(
                    ready=True,
                    htf_name="H1",
                    htf_regime=regime,
                    htf_direction=htf_direction,
                    htf_zone=zone,
                    chart_direction=chart_direction,
                ),
                expected,
            )

    def test_mtf_clause_omission_rules(self):
        self.assertEqual(
            mtf_clause(
                ready=False,
                htf_name="H1",
                htf_regime=BULL,
                htf_direction=1,
                htf_zone="Discount",
                chart_direction=1,
            ),
            "",
        )
        self.assertEqual(mtf_regime_word("H1", UNKNOWN), "")
        self.assertEqual(
            mtf_clause(
                ready=True,
                htf_name="H1",
                htf_regime=BULL,
                htf_direction=0,
                htf_zone="",
                chart_direction=0,
            ),
            "H1 trending up",
        )

    def test_agreement_word_is_recomposed_live(self):
        def clause(chart_direction):
            return mtf_clause(
                ready=True,
                htf_name="H1",
                htf_regime=RANGING,
                htf_direction=1,
                htf_zone="",
                chart_direction=chart_direction,
            )

        self.assertTrue(clause(1).endswith("agrees"))
        self.assertIn("disagrees", clause(-1))
        self.assertEqual(clause(0), "H1 ranging")

    def test_row10_component_statuses(self):
        tracker = VolumeFlowTracker(timeframe="M5", volatility=LOW)
        tracker.flip_direction = 1
        tracker.flip_sequence = 10
        tracker.current_sequence = 10 + STATUS_FRESH_BARS
        self.assertEqual(tracker.status(), "Watching — CVD turned up")
        tracker.current_sequence = 10 + STATUS_FRESH_BARS + 1
        self.assertEqual(tracker.status(), "")
        tracker.flip_direction = -1
        tracker.current_sequence = 10
        self.assertEqual(tracker.status(), "Watching — CVD turned down")
        tracker.flip_direction = 0
        self.assertEqual(tracker.status(), "")

        reading = MtfReading(
            ready=True,
            htf_name="H1",
            last_flip_direction=-1,
            last_flip_sequence=4,
            current_sequence=4 + MTF_STATUS_FRESH_BARS,
        )
        self.assertEqual(mtf_status(reading), "Watching — H1 turned down")
        reading.current_sequence = 4 + MTF_STATUS_FRESH_BARS + 1
        self.assertEqual(mtf_status(reading), "")
        reading.ready = False
        self.assertEqual(mtf_status(reading), "")

    def test_row10_precedence(self):
        base = dict(
            phase2_status="Watching — market transition",
            supertrend_status="Watching — Supertrend bullish, context only",
            volume_flow_status="Watching — CVD turned up",
            mtf_status_text="Watching — H1 turned down",
            full_context=True,
        )
        smc_fresh = "Watching — CHoCH down, structure may be reversing"
        # 1. The big picture turning outranks every chart-timeframe fact.
        self.assertEqual(
            row10_status(smc_status=smc_fresh, smc_fresh=True, **base),
            "Watching — H1 turned down",
        )
        # 2. CHoCH / BOS / sweep outranks the CVD flip.
        chart = dict(base, mtf_status_text="")
        self.assertEqual(
            row10_status(smc_status=smc_fresh, smc_fresh=True, **chart), smc_fresh
        )
        # 3. The CVD flip outranks the structure context-only line and Phase 3.
        self.assertEqual(
            row10_status(smc_status=ROW10_SMC_CONTEXT_ONLY, smc_fresh=False, **chart),
            "Watching — CVD turned up",
        )
        # 4. The terminal line once all four are ready and nothing is fresh.
        self.assertEqual(
            row10_status(
                smc_status=ROW10_SMC_CONTEXT_ONLY,
                smc_fresh=False,
                volume_flow_status="",
                mtf_status_text="",
                full_context=True,
                supertrend_status="Watching — Supertrend bullish, context only",
                phase2_status="Watching — market transition",
            ),
            ROW10_CONTEXT_ONLY,
        )
        # 5. Not all ready: the Phase 3 wording stays.
        self.assertEqual(
            row10_status(
                smc_status="",
                smc_fresh=False,
                volume_flow_status="",
                mtf_status_text="",
                full_context=False,
                supertrend_status="Watching — Supertrend bullish, context only",
                phase2_status="Watching — market transition",
            ),
            "Watching — Supertrend bullish, context only",
        )
        # 6. Phase 2 is the last fallback.
        self.assertEqual(
            row10_status(
                smc_status="",
                smc_fresh=False,
                volume_flow_status="",
                mtf_status_text="",
                full_context=False,
                supertrend_status="",
                phase2_status="Watching — market transition",
            ),
            "Watching — market transition",
        )

    def test_row10_rule19_loading_and_closed_beat_everything(self):
        common = dict(
            phase2_status="Watching — market transition",
            supertrend_status="Watching — Supertrend bullish, context only",
            smc_status="Watching — CHoCH down, structure may be reversing",
            smc_fresh=True,
            volume_flow_status="Watching — CVD turned up",
            mtf_status_text="Watching — H1 turned down",
            full_context=True,
        )
        self.assertEqual(row10_status(incompatible=True, **common), ROW10_INCOMPATIBLE)
        self.assertEqual(row10_status(loading=True, **common), ROW10_LOADING)
        self.assertEqual(row10_status(market_closed=True, **common), ROW10_MARKET_CLOSED)


#=== 15.12 determinism ======================================================

class DeterminismTests(unittest.TestCase):
    def test_a_replay_twice_publishes_the_same_reading(self):
        bars = wave_series(140)
        first = replay(VolumeFlowTracker(timeframe="M5", volatility=LOW), bars)
        second = replay(VolumeFlowTracker(timeframe="M5", volatility=LOW), bars)
        self.assertEqual(reading_tuple(first), reading_tuple(second))

    def test_an_incremental_run_matches_the_full_replay(self):
        bars = wave_series(140)
        full = replay(VolumeFlowTracker(timeframe="M5", volatility=LOW), bars)

        incremental = VolumeFlowTracker(timeframe="M5", volatility=LOW)
        depth = vf_fetch_depth("Forex Major", LOW, "M5")
        for index in range(len(bars) - 1, -1, -1):
            window = bars[index : index + depth]
            incremental.advance(
                window,
                0,
                0.0010,
                bar_sequence=len(bars) - index,
                write_journal=False,
            )
        self.assertEqual(reading_tuple(full), reading_tuple(incremental))

    def test_the_same_bars_give_the_same_anchors_on_any_run(self):
        for bar in wave_series(20):
            self.assertEqual(session_anchor(bar.time), session_anchor(bar.time))

    def test_the_prior_poc_never_moves_within_a_session(self):
        bars = wave_series(320)
        tracker = VolumeFlowTracker(asset_class="Forex Major", timeframe="M5")
        levels: dict = {}
        for index in range(len(bars) - 1, -1, -1):
            tracker.volatility = LOW if index >= 40 else HIGH
            tracker.advance(bars, index, 0.0010, bar_sequence=len(bars) - index)
            reading = tracker.reading
            if reading.prior_poc is not None and reading.session_anchor is not None:
                levels.setdefault(reading.session_anchor, set()).add(
                    round(reading.prior_poc, 12)
                )
        self.assertTrue(levels)
        for anchor, seen in levels.items():
            self.assertEqual(len(seen), 1, (anchor, seen))


if __name__ == "__main__":
    unittest.main()
