from datetime import datetime, timedelta, timezone
import unittest

from phase2_reference import (
    BEAR,
    BULL,
    CLOSED,
    HIGH,
    LOW,
    NORMAL,
    RANGING,
    TRANSITION,
    VOLATILE,
    Measurements,
    RegimeTracker,
    initial_volatility_bucket,
    london_dst_utc,
    new_york_dst_utc,
    percentile_rank,
    regime_candidate,
    session_names,
    sydney_dst_utc,
    volatility_target,
)

UTC = timezone.utc


class PercentileTests(unittest.TestCase):
    def test_rank_against_other_199_values(self):
        self.assertAlmostEqual(percentile_rank(199.0, list(range(1, 200))), 99.7487437186)
        self.assertEqual(percentile_rank(1.0, list(range(2, 201))), 0.0)

    def test_ties_use_midrank_and_flat_series_is_normal(self):
        self.assertEqual(percentile_rank(5.0, [5.0] * 199), 50.0)
        self.assertEqual(initial_volatility_bucket(70.0), NORMAL)
        self.assertEqual(initial_volatility_bucket(30.0), NORMAL)
        self.assertEqual(initial_volatility_bucket(70.01), HIGH)
        self.assertEqual(initial_volatility_bucket(29.99), LOW)

    def test_bucket_margins_and_adjacent_transitions(self):
        self.assertEqual(volatility_target(LOW, 33.0), LOW)
        self.assertEqual(volatility_target(LOW, 33.1), NORMAL)
        self.assertEqual(volatility_target(HIGH, 67.0), HIGH)
        self.assertEqual(volatility_target(HIGH, 66.9), NORMAL)
        self.assertEqual(volatility_target(NORMAL, 70.0), NORMAL)
        self.assertEqual(volatility_target(NORMAL, 70.1), HIGH)


class SessionClockTests(unittest.TestCase):
    def test_london_observes_its_own_winter_and_summer_clock(self):
        self.assertFalse(london_dst_utc(datetime(2026, 1, 15, 7, tzinfo=UTC)))
        self.assertTrue(london_dst_utc(datetime(2026, 7, 15, 6, tzinfo=UTC)))
        self.assertEqual(session_names(datetime(2026, 1, 15, 7, tzinfo=UTC)), "Asia/London")
        self.assertEqual(session_names(datetime(2026, 7, 15, 6, tzinfo=UTC)), "Asia/London")

    def test_new_york_overlap_is_named_in_winter_and_summer(self):
        winter = datetime(2026, 1, 15, 12, tzinfo=UTC)
        summer = datetime(2026, 7, 15, 11, tzinfo=UTC)
        self.assertFalse(new_york_dst_utc(winter))
        self.assertTrue(new_york_dst_utc(summer))
        self.assertEqual(session_names(winter), "London/NY")
        self.assertEqual(session_names(summer), "London/NY")

    def test_sydney_dst_dates_are_independent(self):
        before_start = datetime(2026, 10, 3, 15, 59, tzinfo=UTC)
        after_start = datetime(2026, 10, 3, 16, 0, tzinfo=UTC)
        before_end = datetime(2026, 4, 4, 15, 59, tzinfo=UTC)
        after_end = datetime(2026, 4, 4, 16, 0, tzinfo=UTC)
        self.assertFalse(sydney_dst_utc(before_start))
        self.assertTrue(sydney_dst_utc(after_start))
        self.assertTrue(sydney_dst_utc(before_end))
        self.assertFalse(sydney_dst_utc(after_end))

    def test_open_week_has_no_unnamed_moments(self):
        # Sample complete UTC days in both ordinary and DST-transition weeks.
        starts = [
            datetime(2026, 1, 5, tzinfo=UTC),
            datetime(2026, 4, 6, tzinfo=UTC),
            datetime(2026, 7, 6, tzinfo=UTC),
            datetime(2026, 10, 5, tzinfo=UTC),
        ]
        for start in starts:
            for hour in range(24 * 7):
                moment = start + timedelta(hours=hour)
                self.assertTrue(session_names(moment))


class RegimeTests(unittest.TestCase):
    def test_market_closed_has_absolute_precedence(self):
        m = Measurements(90.0, 2.5, direction=1, bands_expanding=True)
        self.assertEqual(regime_candidate(m, market_closed=True), CLOSED)

    def test_trend_precedes_high_volatility(self):
        m = Measurements(80.0, 2.2, direction=1, bands_expanding=True)
        self.assertEqual(regime_candidate(m), BULL)
        self.assertEqual(regime_candidate(
            Measurements(80.0, 2.2, direction=-1, bands_expanding=True)
        ), BEAR)

    def test_volatile_precedes_ranging_when_direction_is_unclear(self):
        m = Measurements(20.0, 1.6, direction=0, bands_expanding=True)
        self.assertEqual(regime_candidate(m), VOLATILE)
        self.assertEqual(regime_candidate(
            Measurements(20.0, 1.6, direction=0, bands_expanding=False)
        ), RANGING)

    def test_entry_exit_margins(self):
        self.assertEqual(regime_candidate(Measurements(60, 1.0, 1)), TRANSITION)
        self.assertEqual(regime_candidate(Measurements(60, 1.0, 1), BULL), BULL)
        self.assertEqual(regime_candidate(Measurements(32, 1.0), RANGING), RANGING)
        self.assertEqual(regime_candidate(Measurements(33, 1.0), RANGING), TRANSITION)
        self.assertEqual(regime_candidate(Measurements(45, 1.3), VOLATILE), VOLATILE)
        self.assertEqual(regime_candidate(Measurements(45, 1.29), VOLATILE), TRANSITION)

    def test_new_state_needs_two_consecutive_closed_bars(self):
        tracker = RegimeTracker()
        self.assertEqual(tracker.advance(Measurements(20, 1.0), first_evaluation=True), RANGING)
        transition = Measurements(45, 1.0)
        self.assertEqual(tracker.advance(transition), RANGING)
        self.assertEqual(tracker.advance(transition), TRANSITION)
        self.assertEqual(tracker.market_closed(), CLOSED)
        self.assertEqual(tracker.advance(Measurements(80, 1.0, 1), first_evaluation=True), BULL)


if __name__ == "__main__":
    unittest.main()
