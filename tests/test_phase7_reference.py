"""Portable tests for Emtt Phase 7 (Emtt.md 19.2-19.9, scope of 19.10).

Everything asserted here runs against ``phase7_reference`` with no MT5
dependency, so the exact Phase 7 rules - the record, the features, the model,
the warm-up, the adjusted number, the panel text, the journal lines and the
restart resume - are exercised on every CI platform.
"""
import math
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import phase6_reference as p6
import phase7_reference as p7
from phase2_reference import BEAR, BULL, session_names
from phase2_reference import HIGH as VOL_HIGH, LOW as VOL_LOW, NORMAL as VOL_NORMAL

UTC = timezone.utc

#--- shared fixture ------------------------------------------------------
POINT = 0.00001
DIGITS = 5
T0 = datetime(2026, 10, 9, 14, 30)
T1 = T0 + timedelta(minutes=15)
BAR_60 = 60
BAR_70 = 70


def state_path() -> str:
    """The record of the fixture's symbol + timeframe."""
    return p7.learn_file_path("EURUSD", "M15")


def ticket(
    start: datetime = T0,
    side: int = 1,
    confidence: int = 62,
    views: tuple = (1, 1, 1, 1),
    mood: str = "TRENDING",
    session: str = "LONDON",
    vol: str = "NORMAL",
    entry: float = 1.09000,
    entry_kind: str = p7.ENTRY_MARKET,
    stop: float = 1.08750,
    target: float = 1.09500,
    est: int = 45,
    spread: int = 2,
    state: str = p7.STATE_PENDING,
    reached: datetime = None,
    result: str = p7.RESULT_NONE,
    shared: bool = False,
    exit_price: float = 0.0,
    points: int = 0,
    candles: int = 0,
    start_sequence: int = -1,
) -> p7.Ticket:
    return p7.Ticket(
        start_bar_time=start, side=side, confidence=confidence, views=views,
        mood=mood, session=session, vol=vol, entry=entry,
        entry_kind=entry_kind, stop=stop, target=target, est=est,
        spread=spread, state=state, reached_bar_time=reached, result=result,
        shared=shared, exit_price=exit_price, points=points, candles=candles,
        start_sequence=start_sequence,
    )


def labeled_tickets(count: int, result: str = p7.RESULT_TARGET,
                    side: int = 1) -> list:
    """`count` labeled tickets, one step apart, all with the same label."""
    out = []
    for index in range(count):
        out.append(replace(
            ticket(start=T0 + timedelta(minutes=15 * index), side=side,
                   views=(1, 1, 1, 1), mood="TRENDING", session="LONDON",
                   vol="NORMAL", state=p7.STATE_CLOSED, result=result,
                   exit_price=1.09500, points=500, candles=10),
        ))
    return out


def candle(combined: float, views: tuple = (1, 1, 1, 1),
           mood: str = "TRENDING", session: str = "LONDON",
           vol: str = "NORMAL") -> p7.Candle:
    return p7.Candle(ready=True, combined=combined,
                     raw_number=p6.confidence_number(combined), views=views,
                     mood=mood, session=session, vol=vol)


def model_for(tickets: list) -> tuple:
    return p7.build_model(tickets)


class LearningModelTests(unittest.TestCase):
    """19.4 - the logistic model, the feature builder and the labels."""

    #--- the logistic function, the z clamp and L -----------------------

    def test_logistic_is_the_plain_function_in_range(self):
        for z in (-3.0, -1.0, -0.25, 0.0, 0.7, 2.5):
            expected = 1.0 / (1.0 + math.exp(-z))
            got = p7.probability([0.0] * p7.LEARN_FEATURES, z,
                                 [0.0] * p7.LEARN_FEATURES)
            self.assertAlmostEqual(got, expected, places=12)

    def test_z_is_clamped_to_thirty(self):
        # z beyond +-30 can only be produced by the clamp itself: a bias of
        # 1000 must read exactly like a bias of 30.
        weights = [0.0] * p7.LEARN_FEATURES
        vector = [0.0] * p7.LEARN_FEATURES
        self.assertEqual(p7.probability(weights, 1000.0, vector),
                         p7.probability(weights, p7.LEARN_Z_CLAMP, vector))
        self.assertEqual(p7.probability(weights, -1000.0, vector),
                         p7.probability(weights, -p7.LEARN_Z_CLAMP, vector))
        self.assertLess(p7.probability(weights, p7.LEARN_Z_CLAMP, vector), 1.0)
        self.assertGreater(p7.probability(weights, -p7.LEARN_Z_CLAMP, vector), 0.0)

    def test_learned_term_mapping(self):
        self.assertEqual(p7.term_of(0.5), 0.0)
        self.assertEqual(p7.term_of(1.0), 1.0)
        self.assertEqual(p7.term_of(0.0), -1.0)
        self.assertAlmostEqual(p7.term_of(0.75), 0.5, places=12)
        self.assertAlmostEqual(p7.term_of(0.25), -0.5, places=12)

    #--- one hand-computed SGD step, the lr schedule, the clamp ---------

    def test_one_hand_computed_sgd_step(self):
        one = ticket(result=p7.RESULT_TARGET, state=p7.STATE_CLOSED)
        weights, bias = p7.build_model([one])
        vector = p7.features_from_ticket(one)
        # p = 0.5 before the first step, y = 1, lr = 0.30 / sqrt(1) = 0.30,
        # so every weight is 0.30 x 0.5 x x_i = 0.15 x_i and the bias 0.15.
        for value, expected in zip(weights, vector):
            self.assertAlmostEqual(value, 0.15 * expected, places=12)
        self.assertAlmostEqual(bias, 0.15, places=12)

    def test_loss_step_uses_label_zero(self):
        one = ticket(side=-1, views=(-1, -1, -1, -1), confidence=80,
                     result=p7.RESULT_STOP, state=p7.STATE_CLOSED)
        weights, bias = p7.build_model([one])
        vector = p7.features_from_ticket(one)
        # y = 0, p = 0.5, error = -0.5, so w = -0.15 x_i.
        for value, expected in zip(weights, vector):
            self.assertAlmostEqual(value, -0.15 * expected, places=12)
        self.assertAlmostEqual(bias, -0.15, places=12)

    def test_learning_rate_schedule_is_030_over_sqrt_k(self):
        # Two identical labels: step one uses lr = 0.30, step two 0.30 /
        # sqrt(2). Hand-computed on a single-feature-only ticket (all other
        # features zero except the one-hots), the second weight is
        # w1 + lr2 x (1 - p2) x x1 with p2 the model's own value before it.
        one = ticket(result=p7.RESULT_TARGET, state=p7.STATE_CLOSED,
                     confidence=0)
        vector = p7.features_from_ticket(one)
        weights, bias = p7.build_model([one, one])
        step1_w = [0.15 * value for value in vector]
        step1_b = 0.15
        p2 = p7.probability(step1_w, step1_b, vector)
        lr2 = p7.LEARN_RATE / math.sqrt(2.0)
        for value, expected, start in zip(weights, vector, step1_w):
            self.assertAlmostEqual(
                value, start + lr2 * (1.0 - p2) * expected, places=12)
        self.assertAlmostEqual(bias, step1_b + lr2 * (1.0 - p2), places=12)

    def test_weight_clamp_bounds_every_weight_and_the_bias(self):
        # The clamp itself, then the invariant on a full 500-ticket record:
        # no step may push any weight or the bias outside +-4.
        self.assertEqual(p7.clamp_weight(9.0), p7.LEARN_CLAMP)
        self.assertEqual(p7.clamp_weight(-9.0), -p7.LEARN_CLAMP)
        self.assertEqual(p7.clamp_weight(1.25), 1.25)
        tickets = labeled_tickets(250) + labeled_tickets(
            250, result=p7.RESULT_STOP, side=-1)
        self.assertEqual(len(tickets), p7.LEARN_CAP)
        weights, bias = p7.build_model(tickets)
        for value in weights + [bias]:
            self.assertLessEqual(abs(value), p7.LEARN_CLAMP + 1e-12)

    def test_only_labeled_tickets_train_and_in_file_order(self):
        win = ticket(result=p7.RESULT_TARGET, state=p7.STATE_CLOSED)
        loss = ticket(side=-1, views=(-1, -1, -1, -1),
                      result=p7.RESULT_STOP, state=p7.STATE_CLOSED)
        skip = ticket(result=p7.RESULT_MISSED, state=p7.STATE_CLOSED)
        every = p7.build_model([win, skip, loss])
        self.assertEqual(every, p7.build_model([win, loss]))
        self.assertNotEqual(p7.build_model([win, loss]),
                            p7.build_model([loss, win]))

    #--- the feature builder -------------------------------------------

    def test_all_sixteen_features_of_a_worked_ticket(self):
        worked = ticket(side=1, confidence=62, views=(1, 0, -1, 1),
                        mood="RANGING", session="NEWYORK", vol="HIGH")
        vector = p7.features_from_ticket(worked)
        self.assertEqual(len(vector), p7.LEARN_FEATURES)
        self.assertEqual(vector[0], 1.0)                 # direction BUY
        self.assertAlmostEqual(vector[1], 0.62, places=12)  # confidence / 100
        self.assertEqual(vector[2:6], [1.0, 0.0, -1.0, 1.0])  # agreements
        # mood one-hot TRENDING / RANGING / VOLATILE / TRANSITION
        self.assertEqual(vector[6:10], [0.0, 1.0, 0.0, 0.0])
        # session one-hot ASIA / LONDON / NEWYORK
        self.assertEqual(vector[10:13], [0.0, 0.0, 1.0])
        # volatility one-hot LOW / NORMAL / HIGH
        self.assertEqual(vector[13:16], [0.0, 0.0, 1.0])

    def test_every_one_hot_holds_exactly_one_feature(self):
        for mood in p7.MOOD_ORDER:
            vector = p7.features(1, 50, (0, 0, 0, 0), mood, "ASIA", "LOW")
            self.assertEqual(sum(vector[6:10]), 1.0, mood)
        for session in p7.SESSION_ORDER:
            vector = p7.features(1, 50, (0, 0, 0, 0), "TRENDING", session, "LOW")
            self.assertEqual(sum(vector[10:13]), 1.0, session)
        for vol in p7.VOL_ORDER:
            vector = p7.features(1, 50, (0, 0, 0, 0), "TRENDING", "ASIA", vol)
            self.assertEqual(sum(vector[13:16]), 1.0, vol)

    def test_selection_order_is_the_fixed_one(self):
        # The one-hot index follows MOOD_ORDER / SESSION_ORDER / VOL_ORDER,
        # not the alphabetical or any other order.
        self.assertEqual(p7.MOOD_ORDER, ("TRENDING", "RANGING", "VOLATILE", "TRANSITION"))
        self.assertEqual(p7.SESSION_ORDER, ("ASIA", "LONDON", "NEWYORK"))
        self.assertEqual(p7.VOL_ORDER, ("LOW", "NORMAL", "HIGH"))
        for index, mood in enumerate(p7.MOOD_ORDER):
            vector = p7.features(1, 50, (0, 0, 0, 0), mood, "ASIA", "LOW")
            self.assertEqual(vector[6:10].index(1.0), index, mood)

    def test_agreement_rule(self):
        self.assertEqual(p7.agreement(1, 1), 1)
        self.assertEqual(p7.agreement(-1, 1), -1)
        self.assertEqual(p7.agreement(0, 1), 0)
        self.assertEqual(p7.agreement(-1, -1), 1)
        self.assertEqual(p7.agreement(1, -1), -1)

    def test_session_overlap_takes_the_later_opening_one(self):
        # 15.3's anchor: where London and New York overlap, the later opening
        # one wins, so the label reads NY and the feature must be NEWYORK.
        overlap = datetime(2026, 7, 15, 14, 0, tzinfo=UTC)  # both open
        self.assertEqual(session_names(overlap), "London/NY")
        self.assertEqual(p7.session_index_at(overlap), "NEWYORK")
        london_only = datetime(2026, 7, 15, 9, 0, tzinfo=UTC)
        self.assertEqual(session_names(london_only), "London")
        self.assertEqual(p7.session_index_at(london_only), "LONDON")
        asia = datetime(2026, 7, 15, 3, 0, tzinfo=UTC)
        self.assertEqual(session_names(asia), "Asia")
        self.assertEqual(p7.session_index_at(asia), "ASIA")

    def test_feature_vector_of_the_current_bar_carries_the_four_view_number(self):
        # The current-bar vector exists only while the four views are ready
        # (19.4): an unready candle never produces a vector.
        self.assertEqual(p7.evaluate([0.0] * 16, 0.0, p7.Candle(), 0).ready, False)
        ready = candle(combined=0.62)
        reading = p7.evaluate([0.0] * 16, 0.0, ready, 0)
        self.assertTrue(reading.ready)
        self.assertEqual(reading.raw_number, 62)


class WarmUpTests(unittest.TestCase):
    """19.4 warm-up and 19.5 properties: exactly Phase 6 until labeled >= 30."""

    def test_twenty_nine_labeled_tickets_leave_phase6_numbers(self):
        tickets = labeled_tickets(29)
        weights, bias = p7.build_model(tickets)
        for combined in (0.62, -0.48, 0.10, -0.99, 0.0):
            reading = p7.evaluate(weights, bias, candle(combined),
                                  labeled=29)
            self.assertFalse(reading.warm)
            self.assertEqual(reading.number, p6.confidence_number(combined))
            self.assertEqual(reading.buy.term, 0.0)
            self.assertEqual(reading.sell.term, 0.0)
            self.assertEqual(reading.scale, 1.0)

    def test_thirtieth_labeled_ticket_turns_the_term_live(self):
        tickets = labeled_tickets(30)
        weights, bias = p7.build_model(tickets)
        reading = p7.evaluate(weights, bias, candle(0.62), labeled=30)
        self.assertTrue(reading.warm)
        self.assertNotEqual(reading.buy.probability, 0.5)
        self.assertNotEqual(reading.buy.term, 0.0)

    def test_the_first_warm_candle_does_not_step_the_number(self):
        # A neutral model (p = 0.5 for both sides) leaves the number exactly
        # where Phase 6 puts it, however many labeled tickets there are.
        reading = p7.evaluate([0.0] * p7.LEARN_FEATURES, 0.0, candle(0.62),
                              labeled=p7.LEARN_WARMUP)
        self.assertEqual(reading.buy.term, 0.0)
        self.assertEqual(reading.sell.term, 0.0)
        self.assertEqual(reading.number, 62)
        self.assertEqual(reading.raw_number, 62)

    def test_warm_up_boundary_is_exactly_thirty(self):
        weights, bias = p7.build_model(labeled_tickets(29))
        self.assertFalse(p7.evaluate(weights, bias, candle(0.5), 29).warm)
        self.assertTrue(p7.evaluate(weights, bias, candle(0.5), 30).warm)


class CombinationTests(unittest.TestCase):
    """19.5 - V = S6 x (1 + 0.15 x L), the number, the cap and the bound."""

    def test_value_is_the_four_view_value_scaled(self):
        combined = 0.62
        reading = p7.evaluate([0.0] * p7.LEARN_FEATURES, 0.0, candle(combined),
                              labeled=40)
        self.assertAlmostEqual(reading.buy.value, combined, places=12)
        self.assertAlmostEqual(reading.sell.value, -combined, places=12)

        # A model that favours BUY: p = 0.72 -> L = +0.44, factor 1.066.
        weights = [0.0] * p7.LEARN_FEATURES
        bias = math.log(0.72 / 0.28)
        reading = p7.evaluate(weights, bias, candle(combined), labeled=40)
        self.assertAlmostEqual(reading.buy.term, 0.44, places=9)
        self.assertAlmostEqual(reading.buy.value, combined * 1.066, places=9)
        self.assertEqual(reading.number, 66)          # 0.66092 -> 66
        self.assertEqual(reading.direction, 1)

        # A model that disagrees: p = 0.35 -> L = -0.30, factor 0.955.
        bias = math.log(0.35 / 0.65)
        reading = p7.evaluate(weights, bias, candle(combined), labeled=40)
        self.assertAlmostEqual(reading.buy.term, -0.30, places=9)
        self.assertAlmostEqual(reading.buy.value, combined * 0.955, places=9)
        self.assertEqual(reading.number, 59)          # 0.5921 -> 59
        self.assertEqual(reading.percent, 35)

    def test_the_number_never_passes_one_hundred(self):
        for combined in (0.99, 1.0, 0.95, 0.5):
            bias = math.log(0.99 / 0.01)
            reading = p7.evaluate([0.0] * p7.LEARN_FEATURES, bias,
                                  candle(combined), labeled=40)
            self.assertLessEqual(reading.number, p7.LEARN_CONF_CAP)
            self.assertLessEqual(reading.number, 100)
            # The scale is capped so the four published scores, scaled, can
            # not produce a number above the cap either.
            self.assertEqual(p6.confidence_number(combined * reading.scale),
                             reading.number)

    def test_the_scale_factor_is_the_published_bridge(self):
        # The EA scales the four published scores and lets the Phase 6
        # combination run; that must reproduce the number of 19.5.
        for combined in (0.62, -0.62, 0.07, -0.93, 0.4):
            for probability_value in (0.9, 0.72, 0.5, 0.35, 0.1):
                bias = math.log(probability_value / (1.0 - probability_value))
                reading = p7.evaluate([0.0] * p7.LEARN_FEATURES, bias,
                                      candle(combined), labeled=40)
                self.assertEqual(p6.confidence_number(combined * reading.scale),
                                 reading.number)

    def test_learning_can_never_change_the_side(self):
        for combined in (0.62, -0.62, 0.0):
            for probability_value in (0.99, 0.75, 0.5, 0.25, 0.01):
                bias = math.log(probability_value / (1.0 - probability_value))
                reading = p7.evaluate([0.0] * p7.LEARN_FEATURES, bias,
                                      candle(combined), labeled=40)
                if combined > 0.0:
                    self.assertEqual(reading.direction, 1)
                elif combined < 0.0:
                    self.assertEqual(reading.direction, -1)
                else:
                    self.assertEqual(reading.direction, 0)
                    self.assertEqual(reading.number, 0)

    def test_the_number_stays_inside_fifteen_percent(self):
        for combined in (0.62, -0.62, 0.93, -0.11):
            for probability_value in (0.95, 0.7, 0.5, 0.3, 0.05):
                bias = math.log(probability_value / (1.0 - probability_value))
                reading = p7.evaluate([0.0] * p7.LEARN_FEATURES, bias,
                                      candle(combined), labeled=40)
                raw = p6.confidence_number(combined)
                self.assertLessEqual(reading.number, math.ceil(raw * 1.15))
                self.assertGreaterEqual(reading.number,
                                        math.floor(raw * 0.85))

    def test_factor_is_always_positive(self):
        for probability_value in (0.999, 0.001, 0.5):
            term = p7.term_of(probability_value)
            self.assertGreater(1.0 + p7.LEARN_STRENGTH * term, 0.0)


class LabelTests(unittest.TestCase):
    """19.4 - target is a win, stop a loss, every other result neither."""

    def test_labels(self):
        self.assertEqual(p7.label_of(ticket(result=p7.RESULT_TARGET)), 1)
        self.assertEqual(p7.label_of(ticket(result=p7.RESULT_STOP)), 0)
        for word in (p7.RESULT_MISSED, p7.RESULT_CANCELLED, p7.RESULT_SIGNAL,
                     p7.RESULT_MARKET, p7.RESULT_CHART, p7.RESULT_NONE):
            self.assertIsNone(p7.label_of(ticket(result=word)), word)

    def test_counts(self):
        file_state = p7.LearningFile()
        file_state.tickets = [
            ticket(result=p7.RESULT_TARGET, state=p7.STATE_CLOSED),
            ticket(result=p7.RESULT_STOP, state=p7.STATE_CLOSED),
            ticket(result=p7.RESULT_MISSED, state=p7.STATE_CLOSED),
            ticket(result=p7.RESULT_CANCELLED, state=p7.STATE_CLOSED),
            ticket(result=p7.RESULT_SIGNAL, state=p7.STATE_CLOSED),
            ticket(state=p7.STATE_PENDING),
        ]
        self.assertEqual(file_state.labeled, 2)
        self.assertEqual(file_state.wins, 1)
        self.assertEqual(file_state.losses, 1)
        self.assertEqual(len(file_state.tickets), 6)

    def test_result_words_of_the_plan_enum(self):
        self.assertEqual(p7.result_of_plan_result(p6.RESULT_TARGET), p7.RESULT_TARGET)
        self.assertEqual(p7.result_of_plan_result(p6.RESULT_STOP), p7.RESULT_STOP)
        self.assertEqual(p7.result_of_plan_result(p6.RESULT_MISSED), p7.RESULT_MISSED)
        self.assertEqual(p7.result_of_plan_result(p6.RESULT_CANCELLED), p7.RESULT_CANCELLED)
        self.assertEqual(p7.result_of_plan_result(p6.RESULT_SIGNAL), p7.RESULT_SIGNAL)
        self.assertEqual(p7.result_of_plan_result(p6.RESULT_CLOSED), p7.RESULT_MARKET)
        self.assertEqual(p7.result_of_plan_result(p6.RESULT_CHART), p7.RESULT_CHART)


class GrammarTests(unittest.TestCase):
    """19.3 - the line grammar, the file and the cap."""

    def test_ticket_line_grammar_round_trip(self):
        cases = [
            ticket(),
            ticket(side=-1, views=(-1, 0, -1, 1), mood="RANGING",
                   session="ASIA", vol="LOW", entry=1.08450,
                   entry_kind=p7.ENTRY_BLOCK, stop=1.08280, target=1.09120,
                   est=30, spread=3),
            ticket(state=p7.STATE_ACTIVE, reached=T0 + timedelta(minutes=30)),
            ticket(state=p7.STATE_CLOSED, result=p7.RESULT_TARGET,
                   exit_price=1.09500, points=500, candles=12),
            ticket(state=p7.STATE_CLOSED, result=p7.RESULT_STOP, shared=True,
                   exit_price=1.08750, points=-250, candles=17),
            ticket(state=p7.STATE_CLOSED, result=p7.RESULT_MISSED, shared=True,
                   exit_price=1.09000, points=0, candles=3),
        ]
        for original in cases:
            line = p7.ticket_line(original, DIGITS)
            self.assertEqual(p7.parse_ticket_line(line, DIGITS), original, line)
            # Pending lines carry neither reached nor result, and an open
            # plan line never carries result parts.
            if original.state != p7.STATE_CLOSED:
                self.assertNotIn("| result ", line)
            if original.state == p7.STATE_PENDING:
                self.assertNotIn("| reached ", line)

    def test_plan_line_example_of_the_spec(self):
        line = p7.ticket_line(
            ticket(start=datetime(2026, 10, 9, 14, 30), side=1, confidence=72,
                   views=(1, 1, 1, 1), mood="TRENDING", session="LONDON",
                   vol="NORMAL", entry=1.08450, entry_kind=p7.ENTRY_BLOCK,
                   stop=1.08280, target=1.09120, est=30, spread=2,
                   state=p7.STATE_CLOSED, result=p7.RESULT_TARGET,
                   exit_price=1.09120, points=670, candles=12),
            DIGITS)
        self.assertEqual(
            line,
            "plan 2026.10.09 14:30 | BUY | conf 72 | views 1,1,1,1"
            " | mood TRENDING | session LONDON | vol NORMAL"
            " | entry 1.08450 OB | stop 1.08280 | target 1.09120"
            " | est 30 | spread 2 | state closed | result target"
            " | exit 1.09120 | points 670 | candles 12")

    def test_pending_and_open_line_example_of_the_spec(self):
        line = p7.ticket_line(
            ticket(start=datetime(2026, 10, 11, 9, 0), side=-1, confidence=68,
                   views=(-1, 0, -1, 1), mood="RANGING", session="ASIA",
                   vol="HIGH", entry=1.08562, entry_kind=p7.ENTRY_MARKET,
                   stop=1.08740, target=1.08210, est=45, spread=3,
                   state=p7.STATE_PENDING),
            DIGITS)
        self.assertEqual(
            line,
            "plan 2026.10.11 09:00 | SELL | conf 68 | views -1,0,-1,1"
            " | mood RANGING | session ASIA | vol HIGH"
            " | entry 1.08562 market | stop 1.08740 | target 1.08210"
            " | est 45 | spread 3 | state pending")

    def test_whole_file_round_trip(self):
        disk = p7.Disk()
        state = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        self.assertIn("Learning started", state.journal[0])
        for index in range(3):
            state.add_plan(ticket(start=T0 + timedelta(minutes=15 * index)))
        state.mark_reached(0, T1)
        state.close_ticket(0, p7.RESULT_TARGET, False, 1.09500, 500, 12)
        state.close_ticket(1, p7.RESULT_STOP, True, 1.08750, -250, 9)
        self.assertTrue(state.save(disk, T0))

        reopened = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        self.assertEqual(len(reopened.tickets), 3)
        self.assertEqual(reopened.tickets[0].state, p7.STATE_CLOSED)
        self.assertEqual(reopened.tickets[0].result, p7.RESULT_TARGET)
        self.assertEqual(reopened.tickets[0].reached_bar_time, T1)
        self.assertEqual(reopened.tickets[1].shared, True)
        self.assertEqual(reopened.tickets[2].state, p7.STATE_PENDING)
        self.assertEqual(reopened.labeled, 2)
        self.assertEqual(reopened.wins, 1)
        self.assertEqual(reopened.losses, 1)
        self.assertEqual(reopened.open_index, 2)
        # A second load of the same text is identical: the record is stable.
        self.assertEqual(reopened.render(T0), state.render(T0))

    def test_line_endings_and_ascii(self):
        state = p7.LearningFile()
        state.tickets = [ticket()]
        text = state.render(T0)
        self.assertIn("\r\n", text)
        self.assertTrue(text.endswith("\r\n"))
        self.assertTrue(all(ord(ch) < 128 for ch in text))

    def test_file_path_and_sanitiser(self):
        self.assertEqual(p7.learn_file_path("EURUSD", "M15"),
                         "Emtt_Learning\\EURUSD_M15.learn")
        self.assertEqual(p7.learn_file_path("XAUUSD.pro", "M30"),
                         "Emtt_Learning\\XAUUSD.pro_M30.learn")
        self.assertEqual(p7.sanitize("US 30/ES"), "US_30_ES")
        self.assertEqual(p7.sanitize("a#b$c"), "a_b_c")
        self.assertEqual(p7.sanitize("A-Z_0-9."), "A-Z_0-9.")

    def test_a_malformed_line_is_skipped_and_journaled_once(self):
        disk = p7.Disk()
        good = p7.ticket_line(ticket(), DIGITS)
        text = "\r\n".join([
            "Emtt_Learning v1 | EURUSD | M15",
            p7.counts_line([ticket()], T0),
            good,
            "plan nonsense | not a ticket",
            "plan 2026.10.09 14:30 | BUY | conf 62 | views 1,1,1,1 | mood TRENDING"
            " | session LONDON | vol NORMAL | entry 1.09000 market"
            " | stop 1.08750 | target 1.09500 | est 45 | spread 2"
            " | state closed",
        ]) + "\r\n"
        disk.files[state_path()] = text
        state = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        self.assertEqual(len(state.tickets), 1)
        self.assertEqual(state.tickets[0], ticket())
        self.assertEqual(sum(1 for line in state.journal if "damaged" in line), 1)

    def test_the_summary_line_is_ignored(self):
        disk = p7.Disk()
        text = "\r\n".join([
            "Emtt_Learning v1 | EURUSD | M15",
            "counts 999 | labeled 900 | wins 800 | losses 100 | updated 2026.10.11 09:00",
            p7.ticket_line(ticket(state=p7.STATE_CLOSED,
                                  result=p7.RESULT_TARGET,
                                  exit_price=1.09500, points=500, candles=4),
                           DIGITS),
        ]) + "\r\n"
        disk.files[state_path()] = text
        state = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        self.assertEqual(len(state.tickets), 1)
        self.assertEqual(state.labeled, 1)
        self.assertEqual(state.wins, 1)
        self.assertEqual(state.losses, 0)
        # The next write rewrites the summary from the tickets.
        self.assertIn("counts 1 | labeled 1 | wins 1 | losses 0",
                      state.render(T0))

    def test_cap_drops_the_oldest_closed_ticket_and_never_the_open_plan(self):
        # A full record: 499 closed tickets, then the open plan line, in
        # start order. The 500th line is the open plan.
        state = p7.LearningFile()
        state.tickets = [
            ticket(start=T0 + timedelta(minutes=index),
                   state=p7.STATE_CLOSED, result=p7.RESULT_TARGET,
                   exit_price=1.09500, points=500, candles=5)
            for index in range(p7.LEARN_CAP - 1)
        ]
        state.tickets.append(ticket(start=T0 + timedelta(days=1),
                                    state=p7.STATE_PENDING))
        self.assertEqual(len(state.tickets), p7.LEARN_CAP)
        slot = state.add_plan(ticket(start=T0 + timedelta(days=2)))
        self.assertEqual(slot, p7.LEARN_CAP - 1)
        self.assertEqual(len(state.tickets), p7.LEARN_CAP)
        # The oldest closed ticket went; the open plan line stayed.
        self.assertEqual(state.tickets[0].start_bar_time, T0 + timedelta(minutes=1))
        self.assertEqual(state.tickets[-2].start_bar_time, T0 + timedelta(days=1))
        self.assertEqual(state.tickets[-2].state, p7.STATE_PENDING)
        self.assertEqual(state.open_index, p7.LEARN_CAP - 1)

    def test_cap_keeps_an_open_plan_when_it_is_the_only_left(self):
        state = p7.LearningFile()
        state.tickets = [ticket(state=p7.STATE_PENDING)]
        for _ in range(p7.LEARN_CAP - 2):
            state.add_plan(ticket(state=p7.STATE_CLOSED,
                                  result=p7.RESULT_TARGET,
                                  exit_price=1.09500, points=500, candles=5))
        state.apply_cap()
        self.assertTrue(any(t.state != p7.STATE_CLOSED for t in state.tickets))

    def test_write_is_a_tmp_rename(self):
        disk = p7.Disk()
        state = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        state.add_plan(ticket())
        # A crash between the write and the rename: only the .tmp exists and
        # the real record is untouched.
        disk.write_tmp(state.path, state.render(T0))
        self.assertTrue(disk.exists(state.path + ".tmp"))
        self.assertFalse(disk.exists(state.path))
        # The next save rewrites the .tmp and renames it over the record.
        self.assertTrue(state.save(disk, T0))
        self.assertFalse(disk.exists(state.path + ".tmp"))
        self.assertIn("plan ", disk.text(state.path))
        # A leftover .tmp of an older crash is consumed by the next save too.
        disk.files[state.path + ".tmp"] = "half written"
        self.assertTrue(state.save(disk, T0))
        self.assertNotIn("half written", disk.text(state.path))

    def test_save_failure_keeps_learning_in_memory_and_recovers(self):
        disk = p7.Disk()
        state = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        state.add_plan(ticket())
        disk.fail_move = True
        self.assertFalse(state.save(disk, T0))
        self.assertIn("Learning file busy", state.journal[-1])
        self.assertEqual(len(state.tickets), 1)
        # A second attempt inside the same episode stays quiet.
        self.assertFalse(state.save(disk, T0))
        self.assertEqual(sum(1 for line in state.journal if "busy" in line), 1)
        disk.fail_move = False
        self.assertTrue(state.save(disk, T1))
        self.assertIn("Learning write recovered", state.journal[-1])
        # A later episode journals its own busy line and its own recovery.
        disk.fail_write = True
        self.assertFalse(state.save(disk, T1))
        disk.fail_write = False
        self.assertTrue(state.save(disk, T1))
        self.assertEqual(sum(1 for line in state.journal if "busy" in line), 2)
        self.assertEqual(sum(1 for line in state.journal
                             if "recovered" in line), 2)

    def test_unknown_version_leaves_the_file_untouched(self):
        disk = p7.Disk()
        original = ("Emtt_Learning v9 | EURUSD | M15\r\n"
                    "counts 1 | labeled 1 | wins 1 | losses 0"
                    " | updated 2026.10.11 09:00\r\n" + "plan future\r\n")
        disk.files[state_path()] = original
        state = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        self.assertTrue(state.read_only)
        self.assertEqual(state.tickets, [])
        self.assertIn("version unknown", state.journal[0])
        self.assertFalse(state.save(disk, T0))
        self.assertEqual(disk.text(state_path()), original)
        # Learning still runs for the session: a plan is recorded in memory.
        state.add_plan(ticket())
        self.assertEqual(len(state.tickets), 1)

    def test_missing_file_is_a_fresh_start(self):
        disk = p7.Disk()
        state = p7.LearningFile.load(disk, "GBPUSD", "M5", DIGITS, T0)
        self.assertEqual(state.tickets, [])
        self.assertIn("Emtt | Learning started | no file yet | GBPUSD_M5",
                      state.journal[0])
        state.add_plan(ticket())
        self.assertTrue(state.save(disk, T0))

    def test_loaded_line_reports_the_counts(self):
        disk = p7.Disk()
        text = "\r\n".join([
            "Emtt_Learning v1 | EURUSD | M15",
            "counts 2 | labeled 2 | wins 1 | losses 1 | updated 2026.10.11 09:00",
            p7.ticket_line(ticket(state=p7.STATE_CLOSED,
                                  result=p7.RESULT_TARGET,
                                  exit_price=1.09500, points=500, candles=4),
                           DIGITS),
            p7.ticket_line(ticket(state=p7.STATE_CLOSED,
                                  result=p7.RESULT_STOP,
                                  exit_price=1.08750, points=-250, candles=6),
                           DIGITS),
        ]) + "\r\n"
        disk.files[state_path()] = text
        state = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        self.assertEqual(
            state.journal[-1],
            "Emtt | Learning loaded | 2 plans, 2 labeled, 1 wins, 1 losses"
            " | warming 2/30 | bar 2026.10.09 14:30")


class DeterminismTests(unittest.TestCase):
    """19.9 - the same tickets always give the same weights."""

    def test_same_tickets_twice_give_identical_weights(self):
        tickets = labeled_tickets(12) + [
            ticket(result=p7.RESULT_MISSED, state=p7.STATE_CLOSED),
        ] + labeled_tickets(5, result=p7.RESULT_STOP, side=-1)
        self.assertEqual(p7.build_model(tickets), p7.build_model(tickets))

    def test_a_session_path_and_a_load_path_agree(self):
        # In a session each labeled ticket steps the model as it resolves;
        # at load the same tickets are applied in file order. Both are the
        # same sequential pass over the labeled tickets.
        tickets = labeled_tickets(4) + [
            ticket(result=p7.RESULT_MISSED, state=p7.STATE_CLOSED),
        ] + labeled_tickets(3, result=p7.RESULT_STOP, side=-1)

        weights = [0.0] * p7.LEARN_FEATURES
        bias = 0.0
        step = 0
        for item in tickets:
            label = p7.label_of(item)
            if label is None:
                continue
            step += 1
            vector = p7.features_from_ticket(item)
            p = p7.probability(weights, bias, vector)
            lr = p7.LEARN_RATE / math.sqrt(step)
            weights = [p7.clamp_weight(w + lr * (label - p) * x)
                       for w, x in zip(weights, vector)]
            bias = p7.clamp_weight(bias + lr * (label - p))
        self.assertEqual((weights, bias), p7.build_model(tickets))

    def test_the_model_is_recomputed_never_stored(self):
        tickets = labeled_tickets(3)
        once = p7.build_model(tickets)
        # The tickets are the model: no state is carried between builds.
        self.assertEqual(once, p7.build_model(tickets))
        changed = tickets + [ticket(result=p7.RESULT_STOP,
                                    state=p7.STATE_CLOSED)]
        self.assertNotEqual(once, p7.build_model(changed))


class ResumeTests(unittest.TestCase):
    """19.6 - the plan across a restart."""

    def gap(self, bars: list, start: datetime = T0,
            include_start: bool = True) -> list:
        """Copied history in series order: newest first.

        The start bar itself is the oldest entry unless the caller drops it
        to model a start bar that has fallen out of the copied history.
        """
        rates = [p7.Rate(time=start, high=1.09050, low=1.08900, close=1.09000)]
        rates.extend(
            p7.Rate(time=start + timedelta(minutes=15 * (index + 1)),
                    high=high, low=low, close=close)
            for index, (high, low, close) in enumerate(bars))
        if not include_start:
            rates = rates[1:]
        return list(reversed(rates))

    def test_a_touched_nothing_plan_resumes_untouched(self):
        original = ticket(state=p7.STATE_PENDING)
        rates = self.gap([(1.08950, 1.08800, 1.08850),
                          (1.08920, 1.08850, 1.08900)])
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        self.assertEqual(outcome.result, p7.RESULT_NONE)
        self.assertEqual(outcome.ticket.state, p7.STATE_PENDING)
        self.assertEqual(outcome.ticket.entry, original.entry)
        self.assertEqual(outcome.ticket.stop, original.stop)
        self.assertEqual(outcome.ticket.target, original.target)
        self.assertEqual(outcome.candles_checked, 2)

    def test_a_pending_plan_becomes_active_on_the_reaching_candle(self):
        original = ticket(state=p7.STATE_PENDING)
        rates = self.gap([(1.09100, 1.08980, 1.09050),
                          (1.09100, 1.08950, 1.09000)])
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        self.assertEqual(outcome.result, p7.RESULT_NONE)
        self.assertEqual(outcome.ticket.state, p7.STATE_ACTIVE)
        # The oldest candle that reached the entry is the one that marks it.
        self.assertEqual(outcome.ticket.reached_bar_time,
                         T0 + timedelta(minutes=15))
        self.assertEqual(outcome.candles_checked, 2)

    def test_an_active_plan_resumes_active(self):
        original = ticket(state=p7.STATE_ACTIVE, reached=T0)
        rates = self.gap([(1.08950, 1.08800, 1.08850)])
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        self.assertEqual(outcome.result, p7.RESULT_NONE)
        self.assertEqual(outcome.ticket.state, p7.STATE_ACTIVE)
        self.assertEqual(outcome.ticket.reached_bar_time, T0)

    def test_the_gap_ends_the_plan_on_each_result(self):
        cases = [
            # pending, stop before the entry
            (p7.STATE_PENDING, [(1.08900, 1.08700, 1.08750)],
             p7.RESULT_CANCELLED, 1.08750),
            # pending, entry and stop in one candle: the worse result wins
            (p7.STATE_PENDING, [(1.09050, 1.08700, 1.08800)],
             p7.RESULT_STOP, 1.08750),
            # pending, entry and target in one candle: missed beats target
            (p7.STATE_PENDING, [(1.09600, 1.08900, 1.09500)],
             p7.RESULT_MISSED, 1.09500),
            # active, stop
            (p7.STATE_ACTIVE, [(1.08900, 1.08700, 1.08750)],
             p7.RESULT_STOP, 1.08750),
            # active, target
            (p7.STATE_ACTIVE, [(1.09600, 1.08950, 1.09500)],
             p7.RESULT_TARGET, 1.09500),
            # active, both in one candle: the worse result wins
            (p7.STATE_ACTIVE, [(1.09600, 1.08700, 1.09000)],
             p7.RESULT_STOP, 1.08750),
        ]
        for state, bars, result, price in cases:
            original = ticket(state=state)
            rates = self.gap(bars)
            outcome = p7.resume(original, rates, newest_sequence=100,
                                bar_time=T1)
            self.assertEqual(outcome.result, result, (state, bars))
            self.assertEqual(outcome.end_price, price, (state, bars))

    def test_a_shared_candle_is_marked(self):
        original = ticket(state=p7.STATE_ACTIVE)
        rates = self.gap([(1.09600, 1.08700, 1.09000)])   # stop and target
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        self.assertEqual(outcome.result, p7.RESULT_STOP)
        self.assertTrue(outcome.shared)
        single = self.gap([(1.08900, 1.08700, 1.08750)])   # stop only
        outcome = p7.resume(original, single, newest_sequence=100, bar_time=T1)
        self.assertFalse(outcome.shared)

    def test_the_oldest_matching_candle_ends_the_plan_first(self):
        original = ticket(state=p7.STATE_ACTIVE)
        # Oldest first in the helper: the older candle reached the stop and
        # the newer one the target. The plan ends on the older candle.
        rates = self.gap([(1.08900, 1.08700, 1.08750),
                          (1.09600, 1.08950, 1.09500)])
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        self.assertEqual(outcome.result, p7.RESULT_STOP)
        self.assertEqual(outcome.end_time, T0 + timedelta(minutes=15))

    def test_the_gap_is_never_checked_before_the_start_bar(self):
        original = ticket(state=p7.STATE_ACTIVE)
        # The start bar is the newest rate; no candle closed after it, so
        # nothing can end or advance the plan.
        rates = self.gap([], include_start=True)
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        self.assertEqual(outcome.result, p7.RESULT_NONE)
        self.assertEqual(outcome.candles_checked, 0)

    def test_a_missing_start_bar_ends_the_plan_as_chart(self):
        original = ticket(start=T0 - timedelta(days=5),
                          state=p7.STATE_ACTIVE)
        rates = self.gap([(1.09600, 1.08700, 1.09000)], include_start=False)
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        self.assertEqual(outcome.result, p7.RESULT_CHART)
        self.assertEqual(outcome.end_price, 1.09000)
        self.assertEqual(outcome.end_time, T0 + timedelta(minutes=15))

    def test_closing_the_gap_result_writes_the_line(self):
        original = ticket(state=p7.STATE_ACTIVE, start_sequence=88)
        rates = self.gap([(1.09600, 1.08950, 1.09500)])
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        self.assertEqual(outcome.result, p7.RESULT_TARGET)
        line = p7.journal_result(
            original.side, outcome.result, outcome.end_price, original.entry,
            DIGITS, POINT, outcome.start_sequence, outcome.end_sequence,
            outcome.shared, True, outcome.end_time)
        # The candle touched the entry and the target, so 17.7 marks it
        # shared and the resume adds its own tail: both appear.
        self.assertEqual(
            line,
            "Emtt | Plan BUY result | target reached | exit 1.09500"
            " | +500 pts | 1 candles | shared candle | resumed from file"
            " | bar 2026.10.09 14:45")

    def test_a_restored_open_plan_keeps_its_levels(self):
        original = ticket(state=p7.STATE_PENDING, entry=1.08450,
                          entry_kind=p7.ENTRY_BLOCK, stop=1.08280,
                          target=1.09120)
        rates = self.gap([(1.08400, 1.08300, 1.08350)])
        outcome = p7.resume(original, rates, newest_sequence=100, bar_time=T1)
        reading = p7.evaluate([0.0] * 16, 0.0, candle(0.62), labeled=0)
        state = p7.restore_plan(outcome.ticket, reading, BULL, 1.08350,
                                T0 + timedelta(minutes=15), 100, POINT, DIGITS)
        self.assertTrue(state.plan.active)
        self.assertEqual(state.plan.side, 1)
        self.assertEqual(state.plan.status, p6.PLAN_PENDING)
        self.assertEqual(state.plan.entry, 1.08450)
        self.assertEqual(state.plan.stop, 1.08280)
        self.assertEqual(state.plan.target, 1.09120)
        self.assertEqual(state.plan.entry_kind, p6.ENTRY_BLOCK)
        self.assertEqual(state.signal, 1)
        self.assertEqual(state.plan.start_bar_time, original.start_bar_time)
        # RR is recomputed from the restored levels: (1.09120 - 1.08450) /
        # (1.08450 - 1.08280) = 3.94...
        self.assertAlmostEqual(state.plan.risk_reward, 0.00670 / 0.00170, places=6)

    def test_resume_journal_line(self):
        original = ticket(side=1, state=p7.STATE_PENDING,
                          start=datetime(2026, 10, 11, 9, 0))
        self.assertEqual(
            p7.journal_resumed(original.side, original.state,
                               original.start_bar_time, 6,
                               datetime(2026, 10, 11, 9, 45)),
            "Emtt | Learning resumed | plan BUY pending"
            " | start 2026.10.11 09:00 | 6 candles checked"
            " | bar 2026.10.11 09:45")


class PanelAndJournalTests(unittest.TestCase):
    """19.7 - the clause strings, the Row 10 reason and the journal lines."""

    def test_warming_clause(self):
        reading = p7.evaluate([0.0] * 16, 0.0, candle(0.62), labeled=22)
        self.assertEqual(p7.clause_text(reading), "Learning warming 22/30")

    def test_warm_clause_shows_the_estimate_and_the_labeled_count(self):
        bias = math.log(0.64 / 0.36)
        reading = p7.evaluate([0.0] * 16, bias, candle(0.62), labeled=34)
        self.assertEqual(reading.percent, 64)
        self.assertEqual(p7.clause_text(reading), "Learning 64% (34 plans)")

    def test_warm_clause_with_no_leaning_side(self):
        reading = p7.evaluate([0.0] * 16, 0.0, candle(0.0), labeled=34)
        self.assertEqual(p7.clause_text(reading), "Learning (34 plans)")

    def test_clause_is_empty_when_the_views_are_not_ready(self):
        reading = p7.evaluate([0.0] * 16, 0.0, p7.Candle(), labeled=34)
        self.assertEqual(p7.clause_text(reading), "")

    def test_clause_append_rule(self):
        self.assertEqual(p7.why_append("Prior", "Learning 64% (34 plans)"),
                         "Prior | Learning 64% (34 plans)")
        self.assertEqual(p7.why_append("Prior", ""), "Prior")
        self.assertEqual(p7.why_append("", "Learning warming 2/30"),
                         "Learning warming 2/30")
        self.assertEqual(p7.why_append("--", "Learning warming 2/30"),
                         "Learning warming 2/30")

    def test_plan_start_part(self):
        warming = p7.evaluate([0.0] * 16, 0.0, candle(0.62), labeled=22)
        self.assertEqual(p7.plan_text(warming), "learning warming 22/30")
        bias = math.log(0.64 / 0.36)
        warm = p7.evaluate([0.0] * 16, bias, candle(0.62), labeled=34)
        self.assertEqual(p7.plan_text(warm), "learning 64%")
        self.assertEqual(p7.plan_text(p7.evaluate([0.0] * 16, 0.0,
                                                  candle(0.0), 34)), "")

    def test_plan_start_line_carries_the_learning_part(self):
        warming = p7.evaluate([0.0] * 16, 0.0, candle(0.72), labeled=22)
        lines = p7.journal_plan_start(
            side=1, confidence=72, mood_word="Trending", bar=BAR_60,
            reading=warming, entry=1.08450, entry_source="order block edge",
            stop=1.08280, stop_source="swing low", target=1.09120,
            target_source="fair value gap", risk_reward=3.9,
            duration="~2-4 hours", spread_pts=2, bar_time=T0)
        self.assertEqual(
            lines[1],
            "Emtt | Plan BUY | confidence 72% | learning warming 22/30"
            " | entry 1.08450 (order block edge)"
            " | stop 1.08280 (swing low -0.5 ATR)"
            " | target 1.09120 (fair value gap) | RR 1:3.9"
            " | expected ~2-4 hours | spread 2 pts | bar 2026.10.09 14:30")

    def test_row_ten_reason_is_checked_before_the_phase_six_reasons(self):
        # The four-view number would reach the bar, the adjusted one does not.
        bias = math.log(0.35 / 0.65)
        reading = p7.evaluate([0.0] * 16, bias, candle(0.62), labeled=34)
        self.assertEqual(reading.raw_number, 62)
        self.assertEqual(reading.number, 59)
        phase6_status = "Watching \u2014 confidence 59%, below the 60% bar."
        self.assertEqual(
            p7.status_choice(phase6_status, reading, BAR_60),
            "Watching \u2014 learning 35% holds this one back.")

    def test_row_ten_keeps_the_phase_six_reason_when_learning_holds_nothing(self):
        bias = math.log(0.75 / 0.25)
        reading = p7.evaluate([0.0] * 16, bias, candle(0.62), labeled=34)
        self.assertGreaterEqual(reading.number, BAR_60)
        phase6_status = "Watching \u2014 confidence 71%, below the 75% bar."
        self.assertEqual(p7.status_choice(phase6_status, reading, 75),
                         phase6_status)
        # A model that helps pushes the adjusted number over the bar, so the
        # engine starts the plan and no reason is shown at all.
        self.assertEqual(p7.hold_reason(reading, BAR_60), "")

    def test_row_ten_reason_needs_a_leaning_side_and_a_lower_number(self):
        flat = p7.evaluate([0.0] * 16, 0.0, candle(0.0), labeled=34)
        self.assertEqual(p7.hold_reason(flat, BAR_60), "")
        not_warm = p7.evaluate([0.0] * 16, math.log(0.1 / 0.9),
                               candle(0.62), labeled=29)
        self.assertEqual(p7.hold_reason(not_warm, BAR_60), "")
        ready_to_start = p7.evaluate([0.0] * 16, math.log(0.35 / 0.65),
                                     candle(0.90), labeled=34)
        self.assertEqual(p7.hold_reason(ready_to_start, BAR_60), "")

    def test_the_stay_margin_reads_the_adjusted_number(self):
        # 64% raw, trimmed to 62%: both are at or above the 60% bar, so a
        # plan stays; at the 65% stay level the adjusted number decides.
        bias = math.log(0.35 / 0.65)
        reading = p7.evaluate([0.0] * 16, bias, candle(0.64), labeled=34)
        self.assertEqual(reading.raw_number, 64)
        self.assertEqual(reading.number, 61)
        self.assertEqual(p7.hold_reason(reading, BAR_60), "")
        self.assertEqual(p7.status_choice("kept", reading, BAR_60), "kept")

    def test_updated_journal_line_on_a_labeled_result_only(self):
        self.assertEqual(
            p7.journal_updated(35, 16, 9, datetime(2026, 10, 11, 11, 0)),
            "Emtt | Learning updated | 35 labeled, 16 wins, 9 losses"
            " | bar 2026.10.11 11:00")
        for word in (p7.RESULT_MISSED, p7.RESULT_CANCELLED, p7.RESULT_SIGNAL,
                     p7.RESULT_MARKET, p7.RESULT_CHART):
            self.assertIsNone(p7.label_of(ticket(result=word)), word)

    def test_result_line_words_match_phase_six(self):
        for result, word in (
            (p7.RESULT_TARGET, "target reached"),
            (p7.RESULT_STOP, "stop reached"),
            (p7.RESULT_MISSED, "missed"),
            (p7.RESULT_CANCELLED, "cancelled"),
            (p7.RESULT_SIGNAL, "signal changed"),
            (p7.RESULT_MARKET, "market closed"),
            (p7.RESULT_CHART, "chart changed"),
        ):
            line = p7.journal_result(1, result, 1.09500, 1.09000, DIGITS,
                                     POINT, 80, 92, False, False, T1)
            self.assertIn(f"result | {word} |", line)
            self.assertNotIn("resumed from file", line)

    def test_shared_candle_and_resume_flags_can_both_appear(self):
        line = p7.journal_result(1, p7.RESULT_STOP, 1.08750, 1.09000, DIGITS,
                                 POINT, 80, 92, True, True, T1)
        self.assertIn(" | shared candle | resumed from file |", line)

    def test_never_displayed_values_are_not_in_the_texts(self):
        bias = math.log(0.64 / 0.36)
        reading = p7.evaluate([0.0] * 16, bias, candle(0.62), labeled=34)
        clause = p7.clause_text(reading)
        self.assertEqual(clause, "Learning 64% (34 plans)")
        self.assertNotIn("0.", clause)          # no raw probability
        self.assertNotIn("w", clause)           # no weight
        self.assertNotIn("views", clause)       # no feature values


class FileEventTests(unittest.TestCase):
    """19.3 - the four write events, wired the way the EA wires them."""

    def test_the_four_events_write_the_file(self):
        disk = p7.Disk()
        state = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T0)
        # Event 1: at init, immediately after the load, which normalises
        # the file. An empty record has two lines.
        self.assertTrue(state.save(disk, T0))
        self.assertEqual(len(disk.text(state.path).split("\r\n")), 3)
        self.assertTrue(disk.text(state.path).startswith(
            "Emtt_Learning v1 | EURUSD | M15\r\ncounts 0 | labeled 0"))
        # Event 2: the plan starts.
        slot = state.add_plan(ticket())
        self.assertTrue(state.save(disk, T0))
        self.assertEqual(len(state.tickets), 1)
        # Event 3: the plan reaches its Entry.
        self.assertTrue(state.mark_reached(slot, T1))
        self.assertTrue(state.save(disk, T1))
        self.assertIn("| state active | reached 2026.10.09 14:45",
                      disk.text(state.path))
        # Event 4: the plan ends.
        self.assertTrue(state.close_ticket(slot, p7.RESULT_TARGET, False,
                                           1.09500, 500, 12))
        self.assertTrue(state.save(disk, T1))
        text = disk.text(state.path)
        self.assertIn("| state closed | reached 2026.10.09 14:45"
                      " | result target | exit 1.09500 | points 500"
                      " | candles 12", text)
        self.assertIn("counts 1 | labeled 1 | wins 1 | losses 0", text)
        # Nothing else writes: no tick, no timer.
        reopened = p7.LearningFile.load(disk, "EURUSD", "M15", DIGITS, T1)
        self.assertEqual(len(reopened.tickets), 1)
        self.assertEqual(reopened.labeled, 1)

    def test_an_open_plan_is_never_dropped_by_the_cap(self):
        state = p7.LearningFile()
        state.tickets = [ticket(state=p7.STATE_PENDING)]
        for index in range(p7.LEARN_CAP - 1):
            state.tickets.append(ticket(start=T0 + timedelta(minutes=index),
                                        state=p7.STATE_CLOSED,
                                        result=p7.RESULT_STOP,
                                        exit_price=1.08750, points=-250,
                                        candles=5))
        state.apply_cap()
        self.assertEqual(len(state.tickets), p7.LEARN_CAP - 1)
        self.assertTrue(any(t.state == p7.STATE_PENDING for t in state.tickets))


class PanelDecisionTests(unittest.TestCase):
    """19.5 - the one number a decision changes."""

    def test_the_gate_reads_the_adjusted_number(self):
        # 62% raw, trimmed to 59% by a disagreeing model: Phase 6 would start
        # a plan at the 60% bar, Phase 7 stays at WAIT with the learning
        # reason - and the level set never appears.
        bias = math.log(0.35 / 0.65)
        reading = p7.evaluate([0.0] * 16, bias, candle(0.62), labeled=34)
        self.assertEqual(reading.number, 59)
        self.assertLess(reading.number, BAR_60)
        self.assertNotEqual(p7.hold_reason(reading, BAR_60), "")
        # The reversed case: a model that agrees lifts it over the bar.
        bias = math.log(0.72 / 0.28)
        lifted = p7.evaluate([0.0] * 16, bias, candle(0.58), labeled=34)
        self.assertEqual(lifted.raw_number, 58)
        self.assertEqual(lifted.number, 62)   # 0.58 x 1.066 = 0.6183
        self.assertGreaterEqual(lifted.number, BAR_60)
        self.assertEqual(p7.hold_reason(lifted, BAR_60), "")


class MoodAndBucketTests(unittest.TestCase):
    """19.3 / 19.4 - the fixed vocabularies of the ticket."""

    def test_mood_index(self):
        self.assertEqual(p7.mood_index(BULL), "TRENDING")
        self.assertEqual(p7.mood_index(BEAR), "TRENDING")
        self.assertEqual(p7.mood_index("RANGING"), "RANGING")
        self.assertEqual(p7.mood_index("VOLATILE"), "VOLATILE")
        self.assertEqual(p7.mood_index("TRANSITION"), "TRANSITION")
        self.assertEqual(p7.mood_index("MARKET_CLOSED"), "TRANSITION")
        self.assertEqual(p7.mood_index("UNKNOWN"), "TRANSITION")

    def test_vol_index(self):
        self.assertEqual(p7.vol_index(VOL_LOW), "LOW")
        self.assertEqual(p7.vol_index(VOL_NORMAL), "NORMAL")
        self.assertEqual(p7.vol_index(VOL_HIGH), "HIGH")
        self.assertEqual(p7.vol_index("UNKNOWN"), "NORMAL")

    def test_bar_of_the_mood_is_phase_six(self):
        self.assertEqual(p6.mood_bar(BULL), BAR_60)
        self.assertEqual(p6.mood_bar("RANGING"), BAR_70)
        self.assertEqual(p6.mood_bar("VOLATILE"), BAR_70)
        self.assertEqual(p6.mood_bar("TRANSITION"), 75)


if __name__ == "__main__":
    unittest.main()
