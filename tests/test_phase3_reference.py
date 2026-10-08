import math
import unittest

from phase3_reference import (
    ATR_BASELINE_BARS,
    CALM,
    CLUSTERS,
    DEFAULT_MULTIPLIER,
    HIGH_VOL,
    LOW,
    MIN_MEMBERS,
    NORMAL,
    NORMAL_VOL,
    PARAMETER_PAUSE_BARS,
    ROW10_INCOMPATIBLE,
    ROW10_SUPERTREND,
    WILD,
    Bar,
    ParameterGate,
    SupertrendTracker,
    can_change_at,
    candidate_multipliers,
    candidate_replays,
    clamp_matrix_field,
    clamp01,
    cluster_name,
    cluster_winners,
    direction_name,
    distance_atrs,
    history_required,
    is_candidate,
    kmeans,
    kmeans_seeds,
    lookback_scale,
    matrix_field,
    nearest_centre,
    quantile_seed,
    retrain_interval,
    resolve_measurement_params,
    row10_status,
    resolve_multiplier,
    row9_why,
    score_candidate,
    score_segments,
    segments,
    select_multiplier,
    supertrend_clause,
    supertrend_score,
    supertrend_walk,
    window_for_timeframe,
)


#=== deterministic fixtures ===========================================
# Every series is written oldest-first and reversed into MQL5 order, where
# index 0 is the newest closed bar.


def market(closes, atrs):
    """Build (rates, atrs) in MQL5 series order from oldest-first lists."""
    rates = [Bar(high=c + a / 2.0, low=c - a / 2.0, close=c) for c, a in zip(closes, atrs)]
    return list(reversed(rates)), list(reversed(atrs))


def ramp_then_reversal(rise=20, fall=20, step=0.0010, start=1.1000, atr=0.0010):
    """A clean trend that reverses: one hand-checkable direction flip."""
    closes = [start + step * i for i in range(rise)]
    top = closes[-1]
    closes += [top - step * i for i in range(1, fall + 1)]
    return market(closes, [atr] * len(closes))


def steady_rise(bars=40, step=0.0010, start=1.1000, atr=0.0010):
    closes = [start + step * i for i in range(bars)]
    return market(closes, [atr] * bars)


def wandering_market(bars=600, start=1.1000):
    """Quiet / normal / wild stretches, so clusters and flips both appear."""
    levels = (0.0010, 0.0020, 0.0040)
    closes, atrs = [], []
    price = start
    for i in range(bars):
        atr = levels[(i // 40) % 3]
        noise = math.sin(i * 12.9898) * 43758.5453
        noise = (noise - math.floor(noise)) * 2.0 - 1.0
        drift = 0.6 * math.sin(i / 11.0)
        price += atr * (drift + 0.9 * noise)
        closes.append(price)
        atrs.append(atr)
    return market(closes, atrs)


def sparse_market():
    """250 bars whose newest ATR sits in a three-bar wild cluster."""
    return grouped_atrs((120, 127, 3), (0.0010, 0.0020, 0.0040))


def grouped_atrs(counts, levels, bars=None, start=1.1000):
    """A price path whose ATR sits in well-separated volatility groups."""
    atrs = []
    for count, level in zip(counts, levels):
        atrs += [level] * count
    if bars is not None:
        atrs = atrs[:bars]
    closes, price = [], start
    for i, atr in enumerate(atrs):
        noise = math.sin(i * 7.13) * 1234.5678
        noise = (noise - math.floor(noise)) * 2.0 - 1.0
        price += atr * (0.5 * math.sin(i / 9.0) + 0.7 * noise)
        closes.append(price)
    return market(closes, atrs)


class SupertrendBandTests(unittest.TestCase):
    """11.3 - band recursion, seeding and the direction rule."""

    def test_oldest_bar_seeds_bullish_and_a_trend_holds(self):
        rates, atrs = steady_rise()
        bands = supertrend_walk(rates, atrs, 2.0, 0, 40)
        self.assertEqual(bands.directions[0], 1)
        self.assertEqual(set(bands.directions), {1})
        self.assertEqual(bands.flip_count, 0)
        self.assertEqual(bands.bars_since_flip, 39)
        self.assertEqual(bands.direction, 1)
        # Bullish publishes the lower band: close - multiplier x ATR.
        self.assertAlmostEqual(bands.line, rates[0].close - 2.0 * atrs[0], places=12)

    def test_direction_flips_only_when_the_close_breaks_the_band(self):
        rates, atrs = ramp_then_reversal()
        bands = supertrend_walk(rates, atrs, 2.0, 0, 40)
        # Oldest-first: 20 rising bars, then the fall. With a 2.0 x 0.0010
        # band the trailing stop sits 0.0020 under the peak, so the third
        # falling bar (position 22) is the first close below it.
        self.assertEqual(bands.directions[21], 1)
        self.assertEqual(bands.directions[22], -1)
        self.assertEqual(bands.flip_count, 1)
        self.assertEqual(bands.bars_since_flip, 40 - 1 - 22)
        self.assertEqual(bands.direction, -1)

    def test_a_wider_multiplier_flips_later(self):
        rates, atrs = ramp_then_reversal()
        tight = supertrend_walk(rates, atrs, 2.0, 0, 40)
        wide = supertrend_walk(rates, atrs, 4.0, 0, 40)
        first_flip = min(i for i, d in enumerate(tight.directions) if d == -1)
        wide_flip = min(i for i, d in enumerate(wide.directions) if d == -1)
        self.assertGreater(wide_flip, first_flip)

    def test_window_must_fit_inside_the_copied_bars(self):
        rates, atrs = steady_rise(bars=40)
        with self.assertRaises(ValueError):
            supertrend_walk(rates, atrs, 2.0, 5, 40)
        with self.assertRaises(ValueError):
            supertrend_walk(rates, atrs, 2.0, 0, 20)


class SegmentTests(unittest.TestCase):
    """11.5 - the flipping bar belongs to the next segment, never this one."""

    def test_maximal_runs_are_the_segments(self):
        self.assertEqual(segments((1, 1, 1, -1, -1, 1)), [(0, 2), (3, 4), (5, 5)])
        self.assertEqual(segments((1,) * 30), [(0, 29)])

    def test_segment_return_uses_its_own_start_and_end(self):
        rates, atrs = ramp_then_reversal()
        bands = supertrend_walk(rates, atrs, 2.0, 0, 40)
        self.assertEqual(segments(bands.directions), [(0, 21), (22, 39)])
        result = score_candidate(rates, atrs, 2.0, 0, 40)
        self.assertIsNotNone(result)
        self.assertEqual(result.segment_count, 2)

        def close_at(position):
            return rates[40 - 1 - position].close

        # Segment 1 runs to the last bullish bar (21); the bar that flips the
        # direction (22) starts segment 2 and never belongs to segment 1.
        expected_first = (close_at(21) - close_at(0)) / atrs[40 - 1 - 0]
        expected_second = -(close_at(39) - close_at(22)) / atrs[40 - 1 - 22]
        self.assertAlmostEqual(
            result.mean_return, (expected_first + expected_second) / 2.0, places=12
        )
        self.assertAlmostEqual(result.noise, 2 / (40 / 10.0), places=12)
        self.assertAlmostEqual(
            result.score, result.mean_return - 0.10 * result.noise, places=12
        )


class KMeansTests(unittest.TestCase):
    """11.4 - nearest-rank seeds, ascending clusters, tie to the calmer."""

    def test_seeds_are_nearest_rank_quantiles_of_the_window(self):
        ordered = [float(i) for i in range(1, 101)]
        self.assertEqual(quantile_seed(ordered, 10.0), 10.0)
        self.assertEqual(quantile_seed(ordered, 50.0), 50.0)
        self.assertEqual(quantile_seed(ordered, 90.0), 90.0)
        small = sorted([3.0, 1.0, 2.0, 5.0, 4.0, 7.0, 6.0])
        self.assertEqual(quantile_seed(small, 10.0), 1.0)
        self.assertEqual(quantile_seed(small, 50.0), 4.0)
        self.assertEqual(quantile_seed(small, 90.0), 7.0)
        self.assertEqual(kmeans_seeds([0.004] * 40 + [0.001] * 40 + [0.002] * 20),
                         (0.001, 0.002, 0.004))

    def test_clusters_come_back_ascending_with_their_members(self):
        values = [0.001] * 40 + [0.002] * 40 + [0.004] * 20
        centres, members = kmeans(values)
        self.assertEqual(centres, sorted(centres))
        self.assertAlmostEqual(centres[0], 0.001, places=12)
        self.assertAlmostEqual(centres[1], 0.002, places=12)
        self.assertAlmostEqual(centres[2], 0.004, places=12)
        self.assertEqual(members, [40, 40, 20])
        self.assertEqual(sum(members), len(values))

    def test_retrain_restarts_from_the_seeds_not_the_previous_centres(self):
        values = [0.001] * 40 + [0.002] * 40 + [0.004] * 20
        self.assertEqual(kmeans(values), kmeans(list(reversed(values))))

    def test_an_exact_tie_resolves_to_the_calmer_centre(self):
        self.assertEqual(nearest_centre([0.001, 0.003], 0.002), 0)
        self.assertEqual(nearest_centre([0.001, 0.0025, 0.004], 0.00325), 1)
        self.assertEqual(nearest_centre([0.001, 0.003], 0.0021), 1)

    def test_a_sparse_cluster_is_counted_but_starved(self):
        values = [0.001] * 3 + [0.002] * 60 + [0.004] * 37
        centres, members = kmeans(values)
        self.assertEqual(members[0], 3)
        self.assertLess(members[0], MIN_MEMBERS)
        self.assertGreaterEqual(members[1], MIN_MEMBERS)


class SparseGuardTests(unittest.TestCase):
    """11.4 - a cluster below five bars never owns a learned multiplier."""

    CENTRES = [0.0010, 0.0020, 0.0040]

    def test_a_populated_cluster_keeps_its_own_multiplier(self):
        self.assertEqual(
            resolve_multiplier(self.CENTRES, [40, 60, 100], [2.5, 3.0, 4.0], 0.0039),
            (2, 4.0, False, 2),
        )

    def test_a_sparse_cluster_borrows_from_the_nearest_populated_one(self):
        cluster, multiplier, sparse, donor = resolve_multiplier(
            self.CENTRES, [3, 60, 100], [2.5, 3.0, 4.0], 0.0011
        )
        self.assertEqual((cluster, sparse, donor), (0, True, 1))
        self.assertEqual(multiplier, 3.0)
        self.assertEqual(cluster_name(cluster), CALM)

    def test_with_no_populated_cluster_the_default_stands(self):
        cluster, multiplier, sparse, donor = resolve_multiplier(
            self.CENTRES, [1, 2, 0], [2.5, 3.5, 4.0], 0.0010
        )
        self.assertEqual((cluster, sparse, donor), (0, True, -1))
        self.assertEqual(multiplier, DEFAULT_MULTIPLIER)


class MultiplierSelectionTests(unittest.TestCase):
    """11.5 - candidates, scoring, ties and the 3.0 default."""

    def test_the_candidate_set_is_the_range(self):
        self.assertEqual(candidate_multipliers(), (2.0, 2.5, 3.0, 3.5, 4.0))
        self.assertTrue(is_candidate(2.0))
        self.assertTrue(is_candidate(4.0))
        self.assertFalse(is_candidate(1.5))
        self.assertFalse(is_candidate(4.5))
        self.assertTrue(is_candidate(DEFAULT_MULTIPLIER))

    def test_an_exact_tie_goes_to_the_larger_multiplier(self):
        # A monotonic rise: every candidate keeps one bullish segment, so the
        # segment return and the noise are identical and all five scores tie.
        rates, atrs = steady_rise()
        scores = {
            m: score_candidate(rates, atrs, m, 0, 40).score for m in candidate_multipliers()
        }
        self.assertEqual(len(set(round(s, 12) for s in scores.values())), 1)
        self.assertEqual(select_multiplier(rates, atrs, 0, 40), 4.0)

    def test_the_winner_never_leaves_the_candidate_set(self):
        rates, atrs = wandering_market(bars=400)
        for index in (0, 17, 53, 91, 140):
            winner = select_multiplier(rates, atrs, index, 200)
            self.assertIn(winner, candidate_multipliers())

    def test_each_cluster_is_scored_on_its_own_segments(self):
        rates, atrs = wandering_market(bars=400)
        values = atrs[:200]
        centres, members = kmeans(values)
        winners = cluster_winners(rates, atrs, centres, 0, 200)
        self.assertEqual(len(winners), CLUSTERS)
        for winner in winners:
            if winner is not None:
                self.assertIn(winner, candidate_multipliers())
        # The clusters must not all read the same segments: attribution is by
        # the cluster of the bar each segment starts on.
        counts = set()
        replays = candidate_replays(rates, atrs, 0, 200)
        for cluster in range(CLUSTERS):
            for multiplier, directions in replays:
                score = score_segments(
                    rates, atrs, 0, 200, directions, centres, cluster, multiplier
                )
                if score is not None:
                    counts.add(score.segment_count)
        self.assertGreater(len(counts), 1)
        # One replay per candidate serves all three clusters.
        self.assertEqual(len(replays), len(candidate_multipliers()))

    def test_an_unlearned_cluster_keeps_the_default_multiplier(self):
        tracker = SupertrendTracker(timeframe="M15")
        self.assertEqual(tracker.multiplier, DEFAULT_MULTIPLIER)
        self.assertEqual(tracker.cluster_multiplier, [DEFAULT_MULTIPLIER] * CLUSTERS)
        rates, atrs = sparse_market()
        self.assertTrue(tracker.advance(rates, atrs, 0, 0, force_retrain=True))
        # The sparse cluster never owns a learned value, so it stays at 3.0,
        # the middle of the candidate set - nothing is invented for it.
        self.assertEqual(tracker.members, [120, 127, 3])
        self.assertFalse(tracker.cluster_learned[2])
        self.assertEqual(tracker.cluster_multiplier[2], DEFAULT_MULTIPLIER)
        self.assertTrue(tracker.cluster_learned[0])
        self.assertTrue(tracker.cluster_learned[1])


class TrackerTests(unittest.TestCase):
    """11.4 / 11.5 / 11.6 - cadence, pause, sparse fallback, contract."""

    def walk(self, timeframe="M15", bars=600):
        rates, atrs = wandering_market(bars=bars)
        window = window_for_timeframe(timeframe)
        tracker = SupertrendTracker(timeframe=timeframe)
        readings = []
        oldest = bars - window
        sequence = 0
        for index in range(oldest, -1, -1):
            self.assertTrue(
                tracker.advance(
                    rates, atrs, index, sequence,
                    bar_time=f"bar{sequence}", force_retrain=(sequence == 0),
                )
            )
            readings.append((index, tracker.reading()))
            sequence += 1
        return tracker, readings, rates, atrs

    def test_the_same_closed_bars_give_the_same_answer(self):
        first, first_readings, _, _ = self.walk()
        second, second_readings, _, _ = self.walk()
        self.assertEqual(
            [(r.direction, round(r.line, 12), r.cluster, r.multiplier, round(r.score, 12))
             for _, r in first_readings],
            [(r.direction, round(r.line, 12), r.cluster, r.multiplier, round(r.score, 12))
             for _, r in second_readings],
        )
        self.assertEqual(first.journal, second.journal)

    def test_retrain_runs_on_the_window_cadence(self):
        tracker, _, _, _ = self.walk()
        trained = [line for line in tracker.journal if line.startswith("Supertrend trained")]
        self.assertGreater(len(trained), 5)
        self.assertIn("window 250 closed bars (M15 x1.25)", trained[0])
        self.assertLessEqual(tracker.bars_since_train, tracker.retrain_every)
        self.assertEqual(tracker.retrain_every, 12)

    def test_the_multiplier_changes_at_most_once_then_waits_two_bars(self):
        tracker, readings, _, _ = self.walk()
        changes = [
            i for i in range(1, len(readings))
            if readings[i][1].multiplier != readings[i - 1][1].multiplier
        ]
        self.assertGreater(len(changes), 0)
        for previous, current in zip(changes, changes[1:]):
            self.assertGreater(current - previous, PARAMETER_PAUSE_BARS)
        for line in tracker.journal:
            if line.startswith("Supertrend multiplier"):
                self.assertIn("cluster", line)
        for _, reading in readings:
            self.assertIn(reading.multiplier, candidate_multipliers())

    def test_readings_are_never_paused_or_damped(self):
        tracker, readings, rates, atrs = self.walk()
        window = window_for_timeframe(tracker.timeframe)
        held = 0
        for index, reading in readings:
            # Every bar re-reads the live multiplier from scratch: nothing is
            # held over, smoothed or delayed by the multiplier pause.
            fresh = supertrend_walk(rates, atrs, reading.multiplier, index, window)
            self.assertEqual(reading.direction, fresh.direction)
            self.assertAlmostEqual(reading.line, fresh.line, places=12)
            self.assertEqual(reading.bars_since_flip, fresh.bars_since_flip)
            self.assertEqual(reading.flip_count, fresh.flip_count)
        for i in range(1, len(readings)):
            previous, current = readings[i - 1][1], readings[i][1]
            if current.multiplier == previous.multiplier:
                held += 1
        self.assertGreater(held, 0)
        # The cluster word and the direction are published on the bar they
        # change, whether or not the multiplier was allowed to move.
        moved = [
            i for i in range(1, len(readings))
            if readings[i][1].cluster != readings[i - 1][1].cluster
            and readings[i][1].multiplier == readings[i - 1][1].multiplier
        ]
        self.assertGreater(len(moved), 0)
        self.assertTrue(
            any(line.startswith("Supertrend direction") for line in tracker.journal)
        )
        self.assertTrue(
            any(line.startswith("Supertrend cluster") for line in tracker.journal)
        )

    def test_a_sparse_cluster_borrows_the_nearest_populated_multiplier(self):
        rates, atrs = sparse_market()
        tracker = SupertrendTracker(timeframe="M15")
        self.assertTrue(tracker.advance(rates, atrs, 0, 0, force_retrain=True))
        # The newest bar sits in the three-bar wild cluster.
        self.assertEqual(tracker.members[2], 3)
        self.assertEqual(tracker.cluster, 2)
        self.assertEqual(cluster_name(tracker.cluster), WILD)
        self.assertTrue(tracker.sparse_fallback)
        # The nearest populated cluster is Normal (centre 0.0020), not Calm.
        self.assertAlmostEqual(tracker.centres[0], 0.0010, places=12)
        self.assertAlmostEqual(tracker.centres[1], 0.0020, places=12)
        self.assertAlmostEqual(tracker.centres[2], 0.0040, places=12)
        self.assertEqual(tracker.multiplier, tracker.cluster_multiplier[1])
        self.assertTrue(
            any("below" in line and "using multiplier" in line for line in tracker.journal)
        )

    def test_the_published_contract_carries_the_facts(self):
        _, readings, rates, atrs = self.walk()
        index, reading = readings[-1]
        self.assertTrue(reading.ready)
        self.assertIn(reading.direction, (-1, 1))
        self.assertEqual(reading.atr_value, atrs[index])
        self.assertEqual(reading.window, 250)
        self.assertGreaterEqual(reading.flip_count, 0)
        self.assertGreaterEqual(reading.bars_since_flip, 0)
        self.assertGreaterEqual(reading.distance_atrs, 0.0)
        self.assertGreater(reading.line, 0.0)
        self.assertLessEqual(reading.score, 1.0)
        expected = supertrend_score(
            reading.direction, reading.distance_atrs,
            reading.bars_since_flip, reading.flip_count,
        )
        self.assertAlmostEqual(reading.score, expected, places=12)

    def test_a_value_resting_on_a_boundary_cannot_flicker_the_clause(self):
        # A flat ATR leaves the centres equal, so every bar is an exact tie:
        # the tie rule must name the same cluster on every bar, and the
        # multiplier must never move.
        closes = [1.1000 + 0.0002 * math.sin(i / 5.0) for i in range(300)]
        rates, atrs = market(closes, [0.0010] * 300)
        tracker = SupertrendTracker(timeframe="M5")
        clusters, multipliers, clauses = [], [], []
        for index in range(100, -1, -1):
            self.assertTrue(
                tracker.advance(rates, atrs, index, 100 - index,
                                force_retrain=(index == 100))
            )
            clusters.append(tracker.cluster)
            multipliers.append(tracker.multiplier)
            clauses.append(supertrend_clause(cluster_name(tracker.cluster),
                                             tracker.direction))
        self.assertEqual(set(clusters), {0})
        self.assertEqual(set(multipliers), {multipliers[0]})
        self.assertEqual(cluster_name(tracker.cluster), CALM)
        self.assertEqual(len(set(clause.rsplit(" ", 1)[0] for clause in clauses)), 1)

    def test_a_timeframe_round_trip_reproduces_the_reading(self):
        rates, atrs = wandering_market(bars=600)

        def run(timeframe):
            tracker = SupertrendTracker(timeframe=timeframe)
            window = window_for_timeframe(timeframe)
            index = 0
            self.assertTrue(tracker.advance(rates, atrs, index, 0, force_retrain=True))
            self.assertEqual(tracker.window, window)
            reading = tracker.reading()
            return (reading.direction, round(reading.line, 12), reading.cluster,
                    reading.multiplier, round(reading.score, 12), window)

        first = run("M5")
        self.assertNotEqual(run("M15"), first)  # its own window, its own read
        self.assertNotEqual(run("M30"), first)
        self.assertEqual(run("M5"), first)  # state is rebuilt, never carried

    def test_a_context_change_retrains_at_once(self):
        rates, atrs = wandering_market(bars=400)
        tracker = SupertrendTracker(timeframe="M5")
        self.assertTrue(tracker.advance(rates, atrs, 0, 0, force_retrain=False))
        self.assertEqual(tracker.window, 200)
        trained_before = len([l for l in tracker.journal if l.startswith("Supertrend trained")])
        # The bucket moved: the clusters are rebuilt on the same bar.
        self.assertTrue(
            tracker.advance(rates, atrs, 0, 1, volatility=HIGH_VOL, force_retrain=False)
        )
        trained_after = len([l for l in tracker.journal if l.startswith("Supertrend trained")])
        self.assertEqual(trained_after, trained_before + 1)


class LayerTwoTests(unittest.TestCase):
    """11.7 / 11.8 - one code path, three timeframes."""

    def test_the_training_window_is_scaled_by_the_timeframe(self):
        self.assertEqual(lookback_scale("M5"), 1.00)
        self.assertEqual(lookback_scale("M15"), 1.25)
        self.assertEqual(lookback_scale("M30"), 1.50)
        self.assertEqual(
            [window_for_timeframe(tf) for tf in ("M5", "M15", "M30")], [200, 250, 300]
        )

    def test_the_history_gate_is_the_window_plus_the_atr_baseline(self):
        self.assertEqual(ATR_BASELINE_BARS, 50)
        self.assertEqual(
            [history_required(tf) for tf in ("M5", "M15", "M30")], [250, 300, 350]
        )
        for tf in ("M5", "M15", "M30"):
            self.assertEqual(
                history_required(tf), window_for_timeframe(tf) + ATR_BASELINE_BARS
            )

    def test_the_retrain_cadence_follows_the_window(self):
        self.assertEqual(
            [retrain_interval(window_for_timeframe(tf)) for tf in ("M5", "M15", "M30")],
            [10, 12, 15],
        )

    def test_the_volatility_window_stays_unscaled(self):
        # 9.2.3: the 200-bar percentile ranking is fixed; only the lookback
        # row of 11.7 is scaled.
        self.assertEqual(window_for_timeframe("M30"), 300)
        self.assertEqual(window_for_timeframe("M5"), 200)


class ScoreTests(unittest.TestCase):
    """11.6 - the single 0.0-1.0 component score."""

    def test_flat_has_no_score(self):
        self.assertEqual(supertrend_score(0, 5.0, 100, 0), 0.0)
        self.assertEqual(distance_atrs(1.10, 1.09, 0.001, 0), 0.0)

    def test_the_formula_and_its_weights(self):
        self.assertAlmostEqual(
            supertrend_score(1, 0.5, 10, 5),
            0.45 * 0.5 + 0.35 * (10 / 20.0) + 0.20 * (1.0 - 5 / 20.0),
            places=12,
        )
        self.assertAlmostEqual(supertrend_score(-1, 2.0, 40, 0), 1.0, places=12)

    def test_the_score_stays_inside_its_bounds(self):
        for direction in (1, -1):
            for distance in (-3.0, 0.0, 0.25, 1.0, 4.0):
                for age in (0, 1, 19, 20, 500):
                    for flips in (0, 1, 19, 20, 400):
                        score = supertrend_score(direction, distance, age, flips)
                        self.assertGreaterEqual(score, 0.0)
                        self.assertLessEqual(score, 1.0)
        self.assertEqual(clamp01(-2.0), 0.0)
        self.assertEqual(clamp01(3.0), 1.0)

    def test_distance_is_zero_once_price_falls_back_through_the_line(self):
        self.assertAlmostEqual(distance_atrs(1.1010, 1.1000, 0.0010, 1), 1.0, places=12)
        self.assertEqual(distance_atrs(1.0990, 1.1000, 0.0010, 1), 0.0)
        self.assertAlmostEqual(distance_atrs(1.0990, 1.1000, 0.0010, -1), 1.0, places=12)


class PanelTextTests(unittest.TestCase):
    """11.8 - the Row 9 clause and the Row 10 precedence."""

    def test_row9_appends_the_clause_after_the_regime_sentence(self):
        regime = "Efficiency 71/100 and KAMAs aligned up; volatility normal"
        self.assertEqual(
            row9_why(regime, WILD, 1),
            "Efficiency 71/100 and KAMAs aligned up; volatility normal | "
            "Wild (Supertrend bullish)",
        )
        self.assertEqual(row9_why(regime, CALM, -1), f"{regime} | Calm (Supertrend bearish)")
        self.assertEqual(row9_why(regime, NORMAL, 1), f"{regime} | Normal (Supertrend bullish)")

    def test_row9_keeps_the_pending_sentence_and_adds_the_clause(self):
        pending = "Candidate RANGING awaiting a second closed bar; Efficiency 20/100"
        self.assertEqual(
            row9_why(pending, NORMAL, -1), f"{pending} | Normal (Supertrend bearish)"
        )

    def test_row9_has_no_clause_without_a_measurement(self):
        # Not ready or flat: no clause, and the regime text is left as it was.
        self.assertEqual(supertrend_clause(CALM, 0), "")
        self.assertEqual(row9_why("--", CALM, 0), "--")
        self.assertEqual(row9_why("Efficiency 40/100", CALM, 0), "Efficiency 40/100")
        self.assertEqual(cluster_name(-1), "--")
        self.assertEqual(direction_name(0), "flat")

    def test_row10_precedence(self):
        self.assertEqual(row10_status(incompatible=True, supertrend_ready=True),
                         ROW10_INCOMPATIBLE)
        self.assertTrue(
            row10_status(loading=True, supertrend_ready=True).startswith(
                "Waiting — Loading chart history"
            )
        )
        self.assertEqual(row10_status(market_closed=True, supertrend_ready=True),
                         "Paused — Waiting for market to open")
        self.assertEqual(row10_status(supertrend_ready=True), ROW10_SUPERTREND)
        self.assertEqual(
            row10_status(phase2_status="Waiting — Market ranging, no high-quality setup"),
            "Waiting — Market ranging, no high-quality setup",
        )


class MatrixTests(unittest.TestCase):
    """9.2.3 - matrix resolution, clamping and the pause rule."""

    def test_the_class_and_bucket_columns(self):
        self.assertEqual(
            [matrix_field("Forex Major", v, 0) for v in (LOW, NORMAL_VOL, HIGH_VOL)],
            [10, 10, 14],
        )
        self.assertEqual(
            [matrix_field("Crypto", v, 0) for v in (LOW, NORMAL_VOL, HIGH_VOL)],
            [14, 21, 28],
        )
        self.assertEqual(
            [matrix_field("Metals", v, 1) for v in (LOW, NORMAL_VOL, HIGH_VOL)],
            [14, 14, 21],
        )
        self.assertEqual(matrix_field("Forex Major", HIGH_VOL, 2), 13)
        self.assertEqual(matrix_field("Crypto", HIGH_VOL, 3), 34)
        self.assertEqual(matrix_field("Generic", LOW, 4), 50)

    def test_resolution_is_clamped_inside_the_class_range(self):
        for asset in ("Forex Major", "Forex Cross", "Metals", "Crypto", "Indices", "Generic"):
            for volatility in (LOW, NORMAL_VOL, HIGH_VOL):
                params = resolve_measurement_params(asset, volatility)
                for field in range(5):
                    values = [matrix_field(asset, v, field)
                              for v in (LOW, NORMAL_VOL, HIGH_VOL)]
                    resolved = list(params.values())[field]
                    self.assertGreaterEqual(resolved, min(values))
                    self.assertLessEqual(resolved, max(values))
                    self.assertEqual(
                        resolved, clamp_matrix_field(asset, volatility, field)
                    )

    def test_indicator_periods_are_not_scaled_by_the_timeframe(self):
        # Layer 2 scales lookbacks only; the timeframe is inside the candles.
        for tf in ("M5", "M15", "M30"):
            self.assertEqual(
                resolve_measurement_params("Forex Major", HIGH_VOL),
                {"atrPeriod": 14, "erPeriod": 14, "kamaFast": 13,
                 "kamaMedium": 26, "kamaSlow": 50},
            )
        self.assertEqual(window_for_timeframe("M30") / window_for_timeframe("M5"), 1.5)

    def test_one_change_then_a_two_closed_bar_pause(self):
        self.assertFalse(can_change_at(2, 0))
        self.assertFalse(can_change_at(2, 1))
        self.assertTrue(can_change_at(3, 0))
        gate = ParameterGate(3.0)
        self.assertTrue(gate.request(10, 2.5))
        self.assertFalse(gate.request(11, 3.5))
        self.assertFalse(gate.request(12, 3.5))
        self.assertTrue(gate.request(13, 3.5))
        self.assertEqual([bar for bar, _, _ in gate.changes], [10, 13])
        self.assertFalse(gate.request(14, 3.5))


if __name__ == "__main__":
    unittest.main()
