"""Portable tests for Emtt Phase 8 (Emtt.md 21.2-21.14, scope of 21.15).

Everything asserted here runs against ``phase8_reference`` with no MT5
dependency, so the exact Phase 8 rules - the ordered safety gate, the Auto /
Minimum sizing, the order construction, the breakeven / partial / trailing
management, the TP1 / TP2 revisions, the never-close-at-loss time exit, the
soft news multipliers, the trade record and the panel text - are exercised on
every CI platform.
"""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta

import phase6_reference as p6
import phase7_reference as p7
import phase8_reference as p8
from phase2_reference import BEAR, BULL, RANGING, TRANSITION, VOLATILE

#--- shared fixture ------------------------------------------------------
POINT = 0.00001
DIGITS = 5
TICK_SIZE = 0.00001
TICK_VALUE = 1.0          # 1.0 account-currency unit per tick per lot
BALANCE = 10000.0
T0 = datetime(2026, 10, 11, 9, 0)
T1 = T0 + timedelta(minutes=15)
T2 = T0 + timedelta(minutes=30)

ENTRY = 1.08450
STOP = 1.08280
TARGET = 1.09120      # 670 points ≈ 1:3.9 from ENTRY


def candidates(*items: tuple) -> list:
    """(price, priority, source) triples in the 17.4 candidate order."""
    return [p8.Candidate(price, priority, source)
            for price, priority, source in items]


def plan_ticket(
    start: datetime = T0,
    side: int = p8.BUY,
    confidence: int = 82,
    views: tuple = (1, 1, 1, 1),
    mood: str = "TRENDING",
    session: str = "LONDON",
    vol: str = "NORMAL",
    entry: float = ENTRY,
    entry_kind: str = p7.ENTRY_MARKET,
    stop: float = STOP,
    target: float = TARGET,
    est: int = 200,
    spread: int = 2,
    state: str = p7.STATE_ACTIVE,
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


def trade_ticket(**kwargs) -> p8.TradeTicket:
    """A ticket of the 19.3 grammar that later gained the trade part."""
    return p8.TradeTicket(plan=plan_ticket(**kwargs))


class GateTests(unittest.TestCase):
    """21.4 - the ordered safety gate, the spread rule and the margin input."""

    def test_every_check_alone_fails_with_its_own_line(self):
        base = p8.GateInput()
        self.assertEqual(p8.gate_first_failure(base), p8.GATE_OK)
        cases = (
            (replace(base, auto_trading=False), p8.GATE_AUTO_OFF),
            (replace(base, terminal_allowed=False), p8.GATE_TERMINAL_OFF),
            (replace(base, account_allowed=False), p8.GATE_TERMINAL_OFF),
            (replace(base, market_open=False), p8.GATE_MARKET_CLOSED),
            (replace(base, own_pending=True), p8.GATE_ALREADY_LIVE),
            (replace(base, own_position=True), p8.GATE_ALREADY_LIVE),
            (replace(base, spread_allowed=False), p8.GATE_SPREAD),
            (replace(base, margin_check=True, margin_fits=False),
             p8.GATE_MARGIN),
        )
        for gate_input, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(p8.gate_first_failure(gate_input), expected)

    def test_first_failure_is_the_first_check_in_order(self):
        # Every check fails at once; the list order decides the line.
        worst = p8.GateInput(auto_trading=False, terminal_allowed=False,
                             account_allowed=False, market_open=False,
                             own_pending=True, own_position=True,
                             spread_allowed=False, margin_check=True,
                             margin_fits=False)
        self.assertEqual(p8.gate_first_failure(worst), p8.GATE_AUTO_OFF)
        self.assertEqual(
            p8.gate_first_failure(replace(worst, auto_trading=True)),
            p8.GATE_TERMINAL_OFF)
        self.assertEqual(
            p8.gate_first_failure(replace(worst, auto_trading=True,
                                          terminal_allowed=True,
                                          account_allowed=True)),
            p8.GATE_MARKET_CLOSED)
        self.assertEqual(
            p8.gate_first_failure(replace(worst, auto_trading=True,
                                          terminal_allowed=True,
                                          account_allowed=True,
                                          market_open=True)),
            p8.GATE_ALREADY_LIVE)
        self.assertEqual(
            p8.gate_first_failure(replace(worst, auto_trading=True,
                                          terminal_allowed=True,
                                          account_allowed=True,
                                          market_open=True,
                                          own_pending=False,
                                          own_position=False)),
            p8.GATE_SPREAD)
        self.assertEqual(
            p8.gate_first_failure(replace(worst, auto_trading=True,
                                          terminal_allowed=True,
                                          account_allowed=True,
                                          market_open=True,
                                          own_pending=False,
                                          own_position=False,
                                          spread_allowed=True)),
            p8.GATE_MARGIN)

    def test_gate_lines_match_the_section_seven_words(self):
        self.assertEqual(p8.gate_status(p8.GATE_AUTO_OFF),
                         f"No trade {p8.DASH} Auto Trading OFF")
        self.assertEqual(p8.gate_status(p8.GATE_TERMINAL_OFF),
                         f"No trade {p8.DASH} terminal algo trading OFF.")
        self.assertEqual(p8.gate_status(p8.GATE_MARKET_CLOSED),
                         f"Paused {p8.DASH} Waiting for market to open")
        self.assertEqual(p8.gate_status(p8.GATE_SPREAD, 7),
                         f"No trade {p8.DASH} spread too wide (7 pts)")
        self.assertEqual(p8.gate_status(p8.GATE_MARGIN),
                         f"No trade {p8.DASH} not enough margin")
        self.assertEqual(p8.gate_status(p8.GATE_OK), "")

    def test_news_and_sessions_never_appear_in_the_gate(self):
        # 21.2 rule 6: the gate's six failures contain no news or session.
        failures = {p8.GATE_AUTO_OFF, p8.GATE_TERMINAL_OFF,
                    p8.GATE_MARKET_CLOSED, p8.GATE_ALREADY_LIVE,
                    p8.GATE_SPREAD, p8.GATE_MARGIN}
        for failure in failures:
            with self.subTest(failure=failure):
                text = p8.gate_status(failure, 3)
                self.assertNotIn("news", text.lower())
                self.assertNotIn("session", text.lower())

    def test_auto_trading_off_still_manages_a_live_position(self):
        for auto in (True, False):
            self.assertTrue(p8.should_manage_position(True, auto))
        self.assertFalse(p8.should_manage_position(False, True))

    def test_spread_gate_bands(self):
        self.assertTrue(p8.spread_allowed(20.0, 10.0, 100))
        self.assertTrue(p8.spread_allowed(10.0, 10.0, 100))
        self.assertFalse(p8.spread_allowed(20.01, 10.0, 100))
        self.assertFalse(p8.spread_allowed(float("nan"), 10.0, 100))
        self.assertFalse(p8.spread_allowed(5.0, float("inf"), 100))

    def test_spread_gate_is_skipped_below_twenty_samples(self):
        for samples in (0, 1, 19):
            self.assertTrue(p8.spread_allowed(500.0, 1.0, samples))
        self.assertFalse(p8.spread_allowed(500.0, 1.0, p8.SPREAD_SAMPLES))
        self.assertEqual(p8.SPREAD_SAMPLES, 20)
        self.assertEqual(p8.SPREAD_WINDOW, 100)

    def test_margin_gate_both_ways(self):
        bypass = p8.GateInput(margin_check=False, margin_fits=False)
        self.assertEqual(p8.gate_first_failure(bypass), p8.GATE_OK)
        checked = p8.GateInput(margin_check=True, margin_fits=False)
        self.assertEqual(p8.gate_first_failure(checked), p8.GATE_MARGIN)
        fits = p8.GateInput(margin_check=True, margin_fits=True)
        self.assertEqual(p8.gate_first_failure(fits), p8.GATE_OK)


class SizingTests(unittest.TestCase):
    """21.5 - the gaeni sizing, the multipliers and the money rows."""

    def test_auto_formula_is_one_percent_over_stop_risk(self):
        # 1% of 10000 = 100; stop distance 170 points -> 170 per lot.
        raw = p8.risk_lots(BALANCE, ENTRY, STOP, TICK_SIZE, TICK_VALUE, 70)
        self.assertAlmostEqual(raw, 100.0 / 170.0, places=12)

    def test_each_confidence_band(self):
        bands = ((95, 1.5), (90, 1.5), (89, 1.2), (80, 1.2), (79, 1.0),
                 (70, 1.0), (69, 0.7), (60, 0.7), (55, 0.7))
        for confidence, expected in bands:
            with self.subTest(confidence=confidence):
                self.assertEqual(
                    p8.confidence_size_multiplier(confidence), expected)

    def test_each_news_multiplier(self):
        self.assertEqual(p8.news_size_multiplier(p8.NEWS_HIGH), 0.5)
        self.assertEqual(p8.news_size_multiplier(p8.NEWS_MEDIUM), 0.75)
        self.assertEqual(p8.news_size_multiplier(p8.NEWS_LOW), 1.0)
        self.assertEqual(p8.news_size_multiplier(p8.NEWS_NONE), 1.0)

    def test_floor_to_step_and_clamp(self):
        # confidence 82 -> x1.2: 0.588235 x 1.2 = 0.705882 -> 0.70.
        self.assertAlmostEqual(
            p8.resolve_lots(p8.MODE_AUTO, BALANCE, ENTRY, STOP, TICK_SIZE,
                            TICK_VALUE, 82, 1.0, 0.01, 100.0, 0.01),
            0.70, places=10)
        # the result never passes the broker's maximum
        self.assertAlmostEqual(
            p8.resolve_lots(p8.MODE_AUTO, BALANCE, ENTRY, STOP, TICK_SIZE,
                            TICK_VALUE, 95, 1.0, 0.01, 0.50, 0.01),
            0.50, places=10)

    def test_below_minimum_uses_the_minimum_lot(self):
        # 1% of a 50-unit balance cannot reach 0.10 lots; minimum applies.
        self.assertAlmostEqual(
            p8.resolve_lots(p8.MODE_AUTO, 50.0, ENTRY, STOP, TICK_SIZE,
                            TICK_VALUE, 60, 1.0, 0.10, 100.0, 0.01),
            0.10, places=10)

    def test_minimum_mode_ignores_every_multiplier(self):
        for confidence in (55, 70, 95):
            for news in (0.5, 0.75, 1.0):
                with self.subTest(confidence=confidence, news=news):
                    self.assertAlmostEqual(
                        p8.resolve_lots(p8.MODE_MINIMUM, BALANCE, ENTRY, STOP,
                                        TICK_SIZE, TICK_VALUE, confidence,
                                        news, 0.03, 100.0, 0.01),
                        0.03, places=10)

    def test_sizing_refuses_broken_symbol_numbers(self):
        self.assertEqual(p8.risk_lots(0.0, ENTRY, STOP, TICK_SIZE,
                                      TICK_VALUE, 80, 1.0), 0.0)
        self.assertEqual(p8.risk_lots(BALANCE, ENTRY, ENTRY, TICK_SIZE,
                                      TICK_VALUE, 80, 1.0), 0.0)
        self.assertEqual(p8.risk_lots(BALANCE, ENTRY, STOP, TICK_SIZE,
                                      TICK_VALUE, 80, 0.0), 0.0)
        self.assertEqual(p8.resolve_lots(p8.MODE_AUTO, BALANCE, ENTRY, STOP,
                                         TICK_SIZE, TICK_VALUE, 80, 1.0,
                                         0.0, 100.0, 0.01), 0.0)
        self.assertEqual(p8.resolve_lots(p8.MODE_AUTO, BALANCE, ENTRY, STOP,
                                         TICK_SIZE, TICK_VALUE, 80, 1.0,
                                         0.01, 0.005, 0.01), 0.0)

    def test_rows_four_to_six_money_amounts(self):
        lots = 0.50
        entry_money, stop_money, target_money = p8.money_rows(
            ENTRY, STOP, TARGET, 1.08400, lots, TICK_SIZE, TICK_VALUE)
        self.assertAlmostEqual(entry_money, 0.00050 / POINT * 0.50, places=10)
        self.assertAlmostEqual(stop_money, 0.00170 / POINT * 0.50, places=10)
        self.assertAlmostEqual(target_money, 0.00670 / POINT * 0.50, places=10)
        self.assertEqual(p8.money_for_distance(0.0, lots, TICK_SIZE,
                                               TICK_VALUE), 0.0)
        self.assertEqual(p8.money_for_distance(0.001, 0.0, TICK_SIZE,
                                               TICK_VALUE), 0.0)


class OrderConstructionTests(unittest.TestCase):
    """21.6 - market or pending limit, the attached levels, TP2 by name only."""

    def test_entry_at_market_prices_at_the_dealing_side(self):
        buy = p8.build_order(p8.BUY, p8.ENTRY_MARKET, ENTRY, STOP, TARGET,
                             1.08440, 1.08460, False, DIGITS)
        self.assertTrue(buy.valid)
        self.assertFalse(buy.pending)
        self.assertEqual(buy.order_type, "BUY")
        self.assertAlmostEqual(buy.price, 1.08460, places=10)
        sell = p8.build_order(p8.SELL, p8.ENTRY_MARKET, 1.08500, 1.08700,
                              1.07900, 1.08440, 1.08460, False, DIGITS)
        self.assertEqual(sell.order_type, "SELL")
        self.assertAlmostEqual(sell.price, 1.08440, places=10)

    def test_block_edge_below_the_market_is_a_buy_limit(self):
        order = p8.build_order(p8.BUY, p8.ENTRY_BLOCK, 1.08300, STOP, TARGET,
                               1.08440, 1.08460, False, DIGITS)
        self.assertTrue(order.pending)
        self.assertEqual(order.order_type, "BUY_LIMIT")
        self.assertAlmostEqual(order.price, 1.08300, places=10)
        self.assertEqual(order.time_in_force, "GTC")

    def test_block_edge_above_the_market_is_a_sell_limit(self):
        order = p8.build_order(p8.SELL, p8.ENTRY_BLOCK, 1.08600, 1.08800,
                               1.08000, 1.08440, 1.08460, False, DIGITS)
        self.assertTrue(order.pending)
        self.assertEqual(order.order_type, "SELL_LIMIT")
        self.assertAlmostEqual(order.price, 1.08600, places=10)

    def test_a_level_tucked_inside_the_market_goes_to_market(self):
        buy = p8.build_order(p8.BUY, p8.ENTRY_BLOCK, 1.08460, STOP, TARGET,
                             1.08440, 1.08460, False, DIGITS)
        self.assertFalse(buy.pending)
        self.assertEqual(buy.order_type, "BUY")
        sell = p8.build_order(p8.SELL, p8.ENTRY_BLOCK, 1.08440, 1.08600,
                              1.08000, 1.08440, 1.08460, False, DIGITS)
        self.assertFalse(sell.pending)
        self.assertEqual(sell.order_type, "SELL")

    def test_sl_is_attached_only_when_the_input_is_true(self):
        without = p8.build_order(p8.BUY, p8.ENTRY_MARKET, ENTRY, STOP, TARGET,
                                 1.08440, 1.08460, False, DIGITS)
        self.assertFalse(without.stop_loss_sent)
        self.assertEqual(without.stop_loss, 0.0)
        with_stop = p8.build_order(p8.BUY, p8.ENTRY_MARKET, ENTRY, STOP,
                                   TARGET, 1.08440, 1.08460, True, DIGITS)
        self.assertTrue(with_stop.stop_loss_sent)
        self.assertAlmostEqual(with_stop.stop_loss, STOP, places=10)

    def test_tp_is_always_tp1_and_tp2_is_never_sent(self):
        for place_stop in (True, False):
            order = p8.build_order(p8.BUY, p8.ENTRY_MARKET, ENTRY, STOP,
                                   TARGET, 1.08440, 1.08460, place_stop,
                                   DIGITS)
            self.assertTrue(order.take_profit_sent)
            self.assertAlmostEqual(order.take_profit, TARGET, places=10)
            self.assertFalse(order.tp2_sent)

    def test_broken_plan_levels_build_nothing(self):
        self.assertFalse(p8.build_order(0, p8.ENTRY_MARKET, ENTRY, STOP,
                                        TARGET, 1.08440, 1.08460, False,
                                        DIGITS).valid)
        self.assertFalse(p8.build_order(p8.BUY, p8.ENTRY_MARKET, 0.0, STOP,
                                        TARGET, 1.08440, 1.08460, False,
                                        DIGITS).valid)
        self.assertFalse(p8.build_order(p8.BUY, p8.ENTRY_MARKET, ENTRY, STOP,
                                        TARGET, 1.08440, 1.08460, False,
                                        -1).valid)

    def test_tp2_is_named_at_open_from_the_candidates(self):
        items = candidates(
            (1.09000, 2, "POC"), (1.09200, 0, "fair value gap"),
            (1.09450, 1, "buy-side pool"))
        # TP1 is 1.09120; the nearest candidate beyond it and the price wins.
        price, source = p8.initial_second_target(p8.BUY, ENTRY, 1.09050,
                                                 TARGET, items)
        self.assertAlmostEqual(price, 1.09200, places=10)
        self.assertEqual(source, "fair value gap")

    def test_tp2_is_dash_when_no_second_candidate_exists(self):
        items = candidates((1.09000, 2, "POC"))
        self.assertEqual(p8.initial_second_target(p8.BUY, ENTRY, 1.08450,
                                                  TARGET, items),
                         (0.0, ""))
        self.assertEqual(p8.initial_second_target(p8.BUY, ENTRY, 1.09050,
                                                  TARGET, items),
                         (0.0, ""))


class ManagementTests(unittest.TestCase):
    """21.7 - breakeven, the TP1 partial, the trailing and the Protect word."""

    def test_breakeven_trigger_is_one_atr_off_the_entry(self):
        atr = 0.00100
        self.assertTrue(p8.breakeven_reached(p8.BUY, ENTRY, ENTRY + atr,
                                             ENTRY - 0.002, atr))
        self.assertFalse(p8.breakeven_reached(p8.BUY, ENTRY,
                                              ENTRY + atr - 0.00001,
                                              ENTRY - 0.002, atr))
        self.assertTrue(p8.breakeven_reached(p8.SELL, ENTRY, ENTRY + 0.002,
                                             ENTRY - atr, atr))
        self.assertFalse(p8.breakeven_reached(p8.SELL, ENTRY, ENTRY + 0.002,
                                              ENTRY - atr + 0.00001, atr))
        self.assertFalse(p8.breakeven_reached(p8.BUY, ENTRY, ENTRY + 0.01,
                                              0.0, 0.0))

    def test_breakeven_attaches_or_moves_the_stop_to_entry(self):
        # 21.7: no sent stop -> the first stop appears at the trigger; a sent
        # stop is moved from the plan's Stop to Entry. Both end at Entry.
        self.assertEqual(p8.breakeven_event(False), "Breakeven attached")
        self.assertEqual(p8.breakeven_event(True), "Breakeven moved")
        self.assertEqual(p8.protect_word(True, True, ""), "Breakeven")

    def test_partial_close_is_half_the_volume(self):
        self.assertAlmostEqual(p8.partial_volume(0.50, 0.01, 0.01), 0.25,
                               places=10)
        self.assertAlmostEqual(p8.partial_volume(0.20, 0.01, 0.01), 0.10,
                               places=10)
        self.assertAlmostEqual(p8.partial_volume(0.03, 0.01, 0.01), 0.01,
                               places=10)

    def test_partial_is_skipped_when_the_halves_are_too_small(self):
        # A single minimum lot cannot be halved.
        self.assertEqual(p8.partial_volume(0.01, 0.01, 0.01), 0.0)
        # Both halves must stay broker-valid.
        self.assertEqual(p8.partial_volume(0.06, 0.05, 0.01), 0.0)
        self.assertEqual(p8.partial_volume(0.0, 0.01, 0.01), 0.0)

    def test_trailing_base_is_shaped_by_the_chart_timeframe(self):
        self.assertEqual(p8.trail_base("M5"), 1.0)
        self.assertEqual(p8.trail_base("M15"), 1.5)
        self.assertEqual(p8.trail_base("M30"), 2.0)
        self.assertEqual(p8.TRAIL_CHANDELIER, 2.5)
        self.assertEqual(p8.TRAIL_FRACTAL_BUFFER, 0.5)

    def test_each_trailing_method_band(self):
        # f is (price - entry) / (tp1 - entry) for BUY.
        target_distance = TARGET - ENTRY
        entry = ENTRY
        tp1 = TARGET
        for fraction, method in ((0.0, "ATR"), (0.4999, "ATR"),
                                 (0.50, "Chandelier"), (0.7999, "Chandelier"),
                                 (0.80, "Fractal"), (1.0, "Fractal")):
            current = entry + fraction * target_distance
            with self.subTest(fraction=fraction):
                result = p8.trail_calculate(
                    p8.BUY, entry, current, tp1, 0.00100, "M15", 80,
                    BULL, False, highest_high=current + 0.0010,
                    lowest_low=0.0, swing_low=current - 0.0020,
                    swing_high=0.0)
                self.assertTrue(result.valid)
                self.assertEqual(result.method, method)
                self.assertAlmostEqual(result.fraction, fraction, places=10)

    def test_segments_are_mirrored_for_sell(self):
        entry = 1.09000
        tp1 = 1.08300
        current = entry - 0.60 * (entry - tp1)   # f = 0.60 -> Chandelier
        result = p8.trail_calculate(
            p8.SELL, entry, current, tp1, 0.00100, "M30", 88, BEAR, False,
            lowest_low=current - 0.0010, swing_high=current + 0.0020)
        self.assertTrue(result.valid)
        self.assertEqual(result.method, "Chandelier")
        # A SELL trail sits above the current price, below entry.
        self.assertGreater(result.stop, current)
        self.assertLess(result.stop, entry)

    def test_chandelier_distance_formula(self):
        current = ENTRY + 0.60 * (TARGET - ENTRY)
        atr = 0.00100
        highest = current + 0.00200
        result = p8.trail_calculate(
            p8.BUY, ENTRY, current, TARGET, atr, "M15", 80, BULL, False,
            highest_high=highest)
        self.assertTrue(result.valid)
        self.assertEqual(result.method, "Chandelier")
        raw = current - (highest - p8.TRAIL_CHANDELIER * atr)
        self.assertAlmostEqual(result.raw_distance, raw, places=12)
        self.assertAlmostEqual(result.distance, raw * 0.9 * 1.0, places=12)

    def test_fractal_distance_formula_needs_a_confirmed_swing(self):
        current = ENTRY + 0.90 * (TARGET - ENTRY)
        atr = 0.00100
        swing = current - 0.00300
        result = p8.trail_calculate(
            p8.BUY, ENTRY, current, TARGET, atr, "M5", 80, BULL, False,
            swing_low=swing)
        self.assertTrue(result.valid)
        self.assertEqual(result.method, "Fractal")
        raw = current - (swing - p8.TRAIL_FRACTAL_BUFFER * atr)
        self.assertAlmostEqual(result.raw_distance, raw, places=12)
        self.assertAlmostEqual(result.distance, raw * 0.9 * 1.0, places=12)
        # No confirmed swing: the method refuses instead of inventing one.
        self.assertFalse(p8.trail_calculate(
            p8.BUY, ENTRY, current, TARGET, atr, "M5", 80, BULL, False,
            swing_low=swing, has_swing=False).valid)

    def test_each_context_multiplier_band(self):
        for confidence, expected in ((90, 1.0), (85, 1.0), (84, 0.9),
                                     (70, 0.9), (69, 0.7), (55, 0.7),
                                     (54, 0.5)):
            with self.subTest(confidence=confidence):
                self.assertEqual(
                    p8.trail_confidence_multiplier(confidence), expected)
        for regime, expected in ((BULL, 1.0), (BEAR, 1.0), (TRANSITION, 0.8),
                                 (VOLATILE, 1.3), (RANGING, 0.6)):
            with self.subTest(regime=regime):
                self.assertEqual(p8.trail_regime_multiplier(regime), expected)

    def test_news_multiplier_and_the_combined_distance(self):
        current = ENTRY + 0.30 * (TARGET - ENTRY)   # ATR trail, f < 0.50
        atr = 0.00100
        result = p8.trail_calculate(
            p8.BUY, ENTRY, current, TARGET, atr, "M15", 90, TRANSITION, True)
        self.assertTrue(result.valid)
        self.assertEqual(result.method, "ATR")
        self.assertAlmostEqual(result.base_distance, 1.5 * atr, places=12)
        self.assertAlmostEqual(result.news_multiplier, p8.NEWS_TRAIL_MULT,
                               places=12)
        self.assertAlmostEqual(
            result.distance,
            result.base_distance * result.confidence_multiplier *
            result.regime_multiplier * result.news_multiplier, places=12)
        self.assertAlmostEqual(result.stop, current - result.distance,
                               places=12)

    def test_trailing_refuses_broken_readings(self):
        current = ENTRY + 0.30 * (TARGET - ENTRY)
        self.assertFalse(p8.trail_calculate(p8.BUY, ENTRY, current,
                                            0.0, 0.001, "M15", 80, BULL,
                                            False).valid)
        self.assertFalse(p8.trail_calculate(p8.BUY, ENTRY, current, TARGET,
                                            0.0, "M15", 80, BULL,
                                            False).valid)
        self.assertFalse(p8.trail_calculate(0, ENTRY, current, TARGET,
                                            0.001, "M15", 80, BULL,
                                            False).valid)
        # Chandelier without a tracked extreme, Fractal without a swing.
        self.assertFalse(p8.trail_calculate(
            p8.BUY, ENTRY, ENTRY + 0.60 * (TARGET - ENTRY), TARGET, 0.001,
            "M15", 80, BULL, False).valid)
        self.assertFalse(p8.trail_calculate(
            p8.BUY, ENTRY, ENTRY + 0.90 * (TARGET - ENTRY), TARGET, 0.001,
            "M5", 80, BULL, False).valid)

    def test_the_stop_never_moves_backwards(self):
        self.assertTrue(p8.stop_improves(p8.BUY, 0.0, ENTRY, POINT))
        self.assertTrue(p8.stop_improves(p8.BUY, ENTRY, ENTRY + POINT, POINT))
        self.assertFalse(p8.stop_improves(p8.BUY, ENTRY, ENTRY, POINT))
        self.assertFalse(p8.stop_improves(p8.BUY, ENTRY, ENTRY - POINT,
                                          POINT))
        self.assertTrue(p8.stop_improves(p8.SELL, ENTRY, ENTRY - POINT,
                                         POINT))
        self.assertFalse(p8.stop_improves(p8.SELL, ENTRY, ENTRY + POINT,
                                          POINT))
        self.assertFalse(p8.stop_improves(p8.SELL, ENTRY, 0.0, POINT))
        self.assertFalse(p8.stop_improves(0, ENTRY, ENTRY + POINT, POINT))

    def test_protect_words_follow_the_lifecycle(self):
        self.assertEqual(p8.protect_word(False, False, ""), "Original")
        self.assertEqual(p8.protect_word(True, False, "ATR"), "Original")
        self.assertEqual(p8.protect_word(True, True, ""), "Breakeven")
        self.assertEqual(p8.protect_word(True, True, "Original"),
                         "Breakeven")
        self.assertEqual(p8.protect_word(True, True, "ATR"), "ATR")
        self.assertEqual(p8.protect_word(True, True, "Chandelier"),
                         "Chandelier")
        self.assertEqual(p8.protect_word(True, True, "Fractal"), "Fractal")


class TargetTests(unittest.TestCase):
    """21.8 - TP1 / TP2 revisions and their invariants."""

    def setUp(self):
        self.items = candidates(
            (1.08600, 4, "VAL"),
            (1.09000, 2, "POC"),
            (1.09200, 0, "fair value gap"),
            (1.09300, 3, "VAH"),
            (1.09450, 1, "buy-side pool"),
            (1.09600, 5, "naked POC"),
        )
        self.stop = 1.08280

    def test_candidates_are_ordered_nearest_first(self):
        ordered = p8.ordered_candidates(p8.BUY, 1.08800, self.items)
        # 1.08600 and 1.09000 are both 20 points away; the 17.4 priority
        # (POC before VAL) breaks the tie.
        self.assertEqual([item.price for item in ordered],
                         [1.09000, 1.08600, 1.09200, 1.09300, 1.09450,
                          1.09600])

    def test_at_most_six_candidates_survive(self):
        many = candidates(*[(1.08000 + 0.00010 * index, 0, "level")
                            for index in range(20)])
        self.assertEqual(len(p8.ordered_candidates(p8.BUY, 1.08500, many)), 6)

    def test_tp1_moves_to_a_nearer_candidate_that_still_pays(self):
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.08800, self.stop, 1.09200, 1.09600,
            confidence=82, stay_threshold=75, in_profit=True,
            momentum_with=True, tp1_hit=False, min_rr=2.0, items=self.items)
        self.assertTrue(result.valid)
        self.assertTrue(result.tp1_changed)
        self.assertAlmostEqual(result.tp1, 1.09000, places=10)
        self.assertEqual(result.tp1_source, "POC")

    def test_tp1_never_moves_further_away(self):
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.09000, self.stop, 1.09300, 0.0,
            confidence=82, stay_threshold=75, in_profit=True,
            momentum_with=True, tp1_hit=False, min_rr=1.0, items=self.items)
        # 1.09200 is nearer than the current 1.09300 and pays; nothing beyond
        # it may ever be taken.
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.tp1, 1.09200, places=10)
        for candidate in self.items:
            if candidate.price > 1.09200:
                self.assertNotAlmostEqual(result.tp1, candidate.price,
                                          places=10)

    def test_tp1_respects_the_minimum_risk_reward(self):
        # 1.09000 pays 1:3.2 and is skipped at 1:3.5; 1.09200 pays 1:4.4.
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.08460, self.stop, 1.09300, 0.0,
            confidence=82, stay_threshold=75, in_profit=True,
            momentum_with=True, tp1_hit=False, min_rr=3.5, items=self.items)
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.tp1, 1.09200, places=10)
        self.assertGreaterEqual(
            abs(result.tp1 - ENTRY) / abs(ENTRY - self.stop), 3.5)
        # With no nearer candidate that pays, TP1 stays where it is: the
        # "never moves further away" rule outranks the revision.
        unchanged = p8.revise_targets(
            p8.BUY, ENTRY, 1.08460, self.stop, 1.09300, 0.0,
            confidence=82, stay_threshold=75, in_profit=True,
            momentum_with=True, tp1_hit=False, min_rr=5.0, items=self.items)
        self.assertTrue(unchanged.valid)
        self.assertAlmostEqual(unchanged.tp1, 1.09300, places=10)
        self.assertFalse(unchanged.tp1_changed)

    def test_confidence_snap_takes_the_nearest_future_candidate(self):
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.08900, self.stop, 1.09450, 1.09600,
            confidence=68, stay_threshold=75, in_profit=True,
            momentum_with=True, tp1_hit=False, min_rr=0.0, items=self.items)
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.tp1, 1.09000, places=10)

    def test_momentum_extends_tp2_to_the_newest_further_candidate(self):
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.08800, self.stop, 1.09200, 1.09450,
            confidence=85, stay_threshold=75, in_profit=True,
            momentum_with=True, tp1_hit=False, min_rr=0.0, items=self.items)
        self.assertTrue(result.valid)
        # 1.09000 is the nearest candidate inside the current TP1.
        self.assertAlmostEqual(result.tp1, 1.09000, places=10)
        self.assertAlmostEqual(result.tp2, 1.09600, places=10)
        self.assertEqual(result.tp2_source, "naked POC")

    def test_weakening_momentum_contracts_tp2_to_the_nearest(self):
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.08800, self.stop, 1.09200, 1.09600,
            confidence=85, stay_threshold=75, in_profit=True,
            momentum_with=False, tp1_hit=False, min_rr=0.0, items=self.items)
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.tp1, 1.09000, places=10)
        self.assertAlmostEqual(result.tp2, 1.09200, places=10)

    def test_after_tp1_hit_tp2_becomes_the_next_candidate(self):
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.09050, self.stop, 1.09200, 1.09600,
            confidence=85, stay_threshold=75, in_profit=True,
            momentum_with=True, tp1_hit=True, min_rr=0.0, items=self.items)
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.tp1, 1.09200, places=10)
        self.assertAlmostEqual(result.tp2, 1.09300, places=10)

    def test_tp2_is_dash_when_no_candidate_remains(self):
        items = candidates((1.09000, 2, "POC"))
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.08800, self.stop, 1.09200, 0.0,
            confidence=85, stay_threshold=75, in_profit=True,
            momentum_with=False, tp1_hit=False, min_rr=0.0, items=items)
        self.assertTrue(result.valid)
        self.assertEqual(result.tp2, 0.0)
        self.assertFalse(result.tp2_changed)

    def test_wrong_side_levels_are_refused(self):
        # A TP1 already behind the current price cannot be the trade's plan.
        result = p8.revise_targets(
            p8.BUY, ENTRY, 1.09300, self.stop, 1.09200, 0.0,
            confidence=85, stay_threshold=75, in_profit=True,
            momentum_with=False, tp1_hit=False, min_rr=0.0, items=self.items)
        self.assertFalse(result.valid)

    def test_invariant_helper_buy_and_sell(self):
        self.assertTrue(p8.targets_invariant(p8.BUY, ENTRY, 1.08800,
                                             1.09200, 1.09450))
        self.assertTrue(p8.targets_invariant(p8.BUY, ENTRY, 1.08800,
                                             1.09200, 0.0))
        self.assertFalse(p8.targets_invariant(p8.BUY, ENTRY, 1.08800,
                                              1.09450, 1.09200))
        self.assertFalse(p8.targets_invariant(p8.BUY, ENTRY, 1.09300,
                                              1.09200, 1.09450))
        self.assertTrue(p8.targets_invariant(p8.SELL, ENTRY, 1.08800,
                                             1.08300, 0.0))
        self.assertFalse(p8.targets_invariant(p8.SELL, ENTRY, 1.08800,
                                              1.09000, 0.0))


class TimeExitTests(unittest.TestCase):
    """21.9 - profit-only exits and the never-close-at-loss hold."""

    def test_close_only_past_the_upper_bound(self):
        self.assertFalse(p8.time_exit_close(239, 240, True, 40.0))
        self.assertTrue(p8.time_exit_close(241, 240, True, -10.0))
        self.assertTrue(p8.time_exit_close(241, 240, False, 1.0))
        self.assertFalse(p8.time_exit_close(241, 240, False, 0.0))
        self.assertFalse(p8.time_exit_close(241, 0, True, 99.0))

    def test_hold_state_is_the_losing_case(self):
        self.assertTrue(p8.time_exit_hold(241, 240, False, 0.0))
        self.assertTrue(p8.time_exit_hold(241, 240, False, -35.0))
        self.assertFalse(p8.time_exit_hold(241, 240, False, 1.0))
        self.assertFalse(p8.time_exit_hold(241, 240, True, -35.0))
        self.assertFalse(p8.time_exit_hold(240, 240, False, 0.0))
        self.assertFalse(p8.time_exit_hold(241, 0, False, 0.0))

    def test_hold_text_is_the_approved_line(self):
        self.assertEqual(p8.time_exit_hold_text(),
                         f"Holding {p8.DASH} past expected duration, "
                         f"not in profit yet.")

    def test_expected_upper_bound_from_the_estimate(self):
        self.assertEqual(p8.expected_upper_minutes(0), 0)
        self.assertEqual(p8.expected_upper_minutes(-5), 0)
        self.assertEqual(p8.expected_upper_minutes(45), 70)
        self.assertEqual(p8.expected_upper_minutes(120), 180)
        self.assertEqual(p8.expected_upper_minutes(200), 300)
        self.assertEqual(p8.expected_upper_minutes(4321), 4320)

    def test_the_hold_line_is_journaled_on_the_state_change_only(self):
        journal = p8.TimeExitJournal()
        first = journal.on_candle(age_minutes=241, upper_minutes=240,
                                  tp1_hit=False, profit_points=0.0,
                                  bar_time=T0)
        self.assertEqual(first, p8.time_exit_hold_line(0.0, T0))
        self.assertIn("not in profit (+0 pts)", first)
        self.assertIn(p7.fmt_time(T0), first)
        quiet = journal.on_candle(age_minutes=242, upper_minutes=240,
                                  tp1_hit=False, profit_points=-12.0,
                                  bar_time=T1)
        self.assertEqual(quiet, "")
        leaving = journal.on_candle(age_minutes=243, upper_minutes=240,
                                    tp1_hit=False, profit_points=25.0,
                                    bar_time=T2)
        self.assertEqual(leaving, "")
        self.assertFalse(journal.holding)
        again = journal.on_candle(age_minutes=400, upper_minutes=240,
                                  tp1_hit=False, profit_points=0.0,
                                  bar_time=T2)
        self.assertEqual(again, p8.time_exit_hold_line(0.0, T2))


class NewsTests(unittest.TestCase):
    """21.10 - the soft multipliers, the window edges and the overlap rule."""

    def test_window_edges_are_inclusive(self):
        now = T0
        inside = p8.NewsEvent("NFP", now + timedelta(minutes=30),
                              p8.NEWS_HIGH)
        after = p8.NewsEvent("NFP", now - timedelta(minutes=30),
                             p8.NEWS_HIGH)
        outside = p8.NewsEvent("NFP", now + timedelta(minutes=30, seconds=1),
                               p8.NEWS_HIGH)
        self.assertTrue(p8.read_news([inside], now).window_open)
        self.assertTrue(p8.read_news([after], now).window_open)
        self.assertFalse(p8.read_news([outside], now).window_open)
        self.assertEqual(p8.NEWS_WINDOW_MIN, 30)

    def test_low_impact_is_ignored(self):
        now = T0
        low = p8.NewsEvent("CPI", now + timedelta(minutes=10), p8.NEWS_LOW)
        reading = p8.read_news([low], now)
        self.assertTrue(reading.available)
        self.assertFalse(reading.window_open)
        self.assertEqual(reading.size_multiplier, 1.0)
        self.assertEqual(reading.trail_multiplier, 1.0)
        self.assertEqual(reading.status, "")

    def test_high_and_medium_multipliers(self):
        now = T0
        high = p8.NewsEvent("NFP", now + timedelta(minutes=15), p8.NEWS_HIGH)
        medium = p8.NewsEvent("Retail Sales", now + timedelta(minutes=5),
                              p8.NEWS_MEDIUM)
        high_reading = p8.read_news([high], now)
        self.assertEqual(high_reading.size_multiplier, 0.5)
        self.assertEqual(high_reading.trail_multiplier, 1.5)
        self.assertEqual(high_reading.minutes, 15)
        self.assertEqual(high_reading.status,
                         f"News {p8.DASH} NFP in 15 min (high impact), "
                         f"size 0.5x.")
        medium_reading = p8.read_news([medium], now)
        self.assertEqual(medium_reading.size_multiplier, 0.75)
        self.assertEqual(medium_reading.trail_multiplier, 1.0)
        self.assertEqual(medium_reading.status,
                         f"News {p8.DASH} Retail Sales in 5 min "
                         f"(medium impact), size 0.75x.")

    def test_overlapping_windows_pick_the_strongest(self):
        now = T0
        high = p8.NewsEvent("NFP", now + timedelta(minutes=20), p8.NEWS_HIGH)
        medium = p8.NewsEvent("Retail Sales", now + timedelta(minutes=2),
                              p8.NEWS_MEDIUM)
        reading = p8.read_news([medium, high], now)
        self.assertEqual(reading.impact, p8.NEWS_HIGH)
        self.assertEqual(reading.size_multiplier, 0.5)
        self.assertEqual(p8.news_strongest(p8.NEWS_LOW, p8.NEWS_HIGH),
                         p8.NEWS_HIGH)
        self.assertEqual(p8.news_strongest(p8.NEWS_MEDIUM, p8.NEWS_LOW),
                         p8.NEWS_MEDIUM)

    def test_equal_impacts_resolve_to_the_nearest_event(self):
        now = T0
        near = p8.NewsEvent("CPI", now + timedelta(minutes=5), p8.NEWS_HIGH)
        far = p8.NewsEvent("NFP", now + timedelta(minutes=25), p8.NEWS_HIGH)
        self.assertEqual(p8.read_news([far, near], now).event, "CPI")

    def test_news_multipliers_never_reach_the_gate(self):
        reading = p8.read_news([], T0)
        self.assertFalse(reading.available)
        self.assertEqual(reading.size_multiplier, 1.0)
        self.assertEqual(reading.trail_multiplier, 1.0)

    def test_unavailable_calendar_is_logged_once_per_session(self):
        journal = p8.NewsUnavailableJournal()
        reading = p8.read_news([], T0)
        self.assertEqual(journal.on_read("LONDON", reading),
                         "Emtt | News calendar unavailable | no effect")
        self.assertEqual(journal.on_read("LONDON", reading), "")
        self.assertEqual(journal.on_read("NEWYORK", reading),
                         "Emtt | News calendar unavailable | no effect")
        self.assertEqual(journal.on_read("NEWYORK", reading), "")

    def test_news_trail_multiplier_only_above_high(self):
        self.assertEqual(p8.news_trail_multiplier(p8.NEWS_HIGH), 1.5)
        self.assertEqual(p8.news_trail_multiplier(p8.NEWS_MEDIUM), 1.0)
        self.assertEqual(p8.news_trail_multiplier(p8.NEWS_LOW), 1.0)


class RecordTests(unittest.TestCase):
    """21.13 - the trade ticket part, the label source and the file events."""

    def test_trade_part_round_trip_filled_only(self):
        ticket = trade_ticket()
        ticket.trade_filled = T1
        line = p8.trade_ticket_line(ticket)
        self.assertIn(f" | trade filled {p7.fmt_time(T1)}", line)
        self.assertNotIn("trade closed", line)
        parsed = p8.parse_trade_ticket_line(line)
        self.assertEqual(parsed.trade_filled, T1)
        self.assertIsNone(parsed.trade_closed)
        self.assertIsNone(parsed.trade_net_points)

    def test_trade_part_round_trip_closed_with_net(self):
        ticket = trade_ticket()
        ticket.trade_filled = T1
        ticket.trade_closed = T2
        ticket.trade_net_points = 670
        line = p8.trade_ticket_line(ticket)
        self.assertIn(f" | trade closed {p7.fmt_time(T2)} | net +670 pts",
                      line)
        parsed = p8.parse_trade_ticket_line(line)
        self.assertEqual(parsed.trade_filled, T1)
        self.assertEqual(parsed.trade_closed, T2)
        self.assertEqual(parsed.trade_net_points, 670)
        losing = replace(ticket, trade_net_points=-125)
        self.assertIn(" | net -125 pts", p8.trade_ticket_line(losing))

    def test_trade_part_rejects_a_broken_grammar(self):
        ticket = trade_ticket()
        ticket.trade_closed = T2
        ticket.trade_net_points = 10
        with self.assertRaises(ValueError):
            p8.trade_ticket_line(ticket)   # a close without a fill
        filled = trade_ticket()
        filled.trade_filled = T2
        filled.trade_closed = T1          # close before fill
        filled.trade_net_points = 5
        with self.assertRaises(ValueError):
            p8.parse_trade_ticket_line(p8.trade_ticket_line(filled))
        with self.assertRaises(ValueError):
            p8.parse_trade_ticket_line(
                p8.trade_ticket_line(filled).replace("net +5 pts", "net 5"))

    def test_real_net_is_the_label_when_a_trade_exists(self):
        winning = trade_ticket(result=p7.RESULT_STOP)   # paper says loss
        winning.trade_filled = T1
        winning.trade_closed = T2
        winning.trade_net_points = 42
        self.assertEqual(p8.label_of(winning), 1)
        losing = trade_ticket(result=p7.RESULT_TARGET)  # paper says win
        losing.trade_filled = T1
        losing.trade_closed = T2
        losing.trade_net_points = -42
        self.assertEqual(p8.label_of(losing), 0)
        flat = trade_ticket()
        flat.trade_filled = T1
        flat.trade_closed = T2
        flat.trade_net_points = 0
        self.assertIsNone(p8.label_of(flat))

    def test_a_filled_trade_waits_for_its_close(self):
        open_trade = trade_ticket(result=p7.RESULT_TARGET)
        open_trade.trade_filled = T1
        self.assertIsNone(p8.label_of(open_trade))

    def test_paper_labels_train_while_emtt_only_watches(self):
        target = trade_ticket(result=p7.RESULT_TARGET, exit_price=TARGET,
                              points=670, candles=8)
        stop = trade_ticket(result=p7.RESULT_STOP, exit_price=STOP,
                            points=-170, candles=5)
        missed = trade_ticket(result=p7.RESULT_MISSED)
        cancelled = trade_ticket(result=p7.RESULT_CANCELLED)
        chart = trade_ticket(result=p7.RESULT_CHART)
        self.assertEqual(p8.label_of(target), 1)
        self.assertEqual(p8.label_of(stop), 0)
        for neither in (missed, cancelled, chart):
            self.assertIsNone(p8.label_of(neither))

    def test_a_label_is_frozen_once_resolved(self):
        ticket = trade_ticket(result=p7.RESULT_TARGET)
        self.assertEqual(p8.label_of(ticket), 1)
        # The paper outcome was the first resolved form; it never relabels.
        ticket.trade_filled = T1
        ticket.trade_closed = T2
        ticket.trade_net_points = -500
        self.assertEqual(p8.label_of(ticket), 1)
        closed = trade_ticket()
        closed.trade_filled = T1
        closed.trade_closed = T2
        closed.trade_net_points = -80
        self.assertEqual(p8.label_of(closed), 0)
        closed.trade_net_points = 900
        self.assertEqual(p8.label_of(closed), 0)

    def test_counts_follow_both_sources(self):
        real_win = trade_ticket()
        real_win.trade_filled = T1
        real_win.trade_closed = T2
        real_win.trade_net_points = 120
        real_loss = trade_ticket()
        real_loss.trade_filled = T1
        real_loss.trade_closed = T2
        real_loss.trade_net_points = -60
        paper_win = trade_ticket(result=p7.RESULT_TARGET)
        paper_loss = trade_ticket(result=p7.RESULT_STOP)
        neither = trade_ticket(result=p7.RESULT_MISSED)
        open_trade = trade_ticket()
        open_trade.trade_filled = T1
        labeled, wins, losses = p8.learning_counts(
            [real_win, real_loss, paper_win, paper_loss, neither,
             open_trade])
        self.assertEqual((labeled, wins, losses), (4, 2, 2))

    def test_the_file_write_events_are_the_four_plus_two(self):
        self.assertEqual(p8.trade_file_write_events(),
                         ("init_after_load", "plan_start", "entry_reached",
                          "plan_end", "trade_filled", "position_closed"))


class PanelTests(unittest.TestCase):
    """21.12 - the STATUS precedence, the live block and the header."""

    def test_status_precedence_is_walked_top_down(self):
        args = dict(incompatible="incompatible", loading="loading",
                    market_closed="market closed", fresh="fresh",
                    time_hold="hold", news="news", gate="gate", live="live",
                    signal="signal", context="context", terminal="terminal")
        keys = ["incompatible", "loading", "market_closed", "fresh",
                "time_hold", "news", "gate", "live", "signal", "context",
                "terminal"]
        for index, key in enumerate(keys):
            remaining = {name: value for name, value in args.items()
                         if name in keys[index:]}
            with self.subTest(first=key):
                self.assertEqual(p8.panel_status(**remaining),
                                 args[key])
        self.assertEqual(p8.panel_status(), "")

    def test_fresh_events_beat_the_time_exit_hold(self):
        self.assertEqual(
            p8.panel_status(fresh=p8.fresh_tp1_status(),
                            time_hold=p8.time_exit_hold_text()), 
            f"TP1 hit {p8.DASH} 50% closed, stop at breakeven.")
        self.assertEqual(
            p8.panel_status(time_hold=p8.time_exit_hold_text(),
                            news=f"News {p8.DASH} NFP in 15 min (high impact), "
                                 f"size 0.5x."),
            p8.time_exit_hold_text())
        self.assertEqual(
            p8.panel_status(news=f"News {p8.DASH} NFP in 15 min (high impact), "
                                 f"size 0.5x.",
                            gate=p8.gate_status(p8.GATE_SPREAD, 7)),
            f"News {p8.DASH} NFP in 15 min (high impact), size 0.5x.")
        self.assertEqual(
            p8.panel_status(gate=p8.gate_status(p8.GATE_SPREAD, 7),
                            live=p8.live_position_status()),
            f"No trade {p8.DASH} spread too wide (7 pts)")
        self.assertEqual(
            p8.panel_status(live=p8.live_pending_status(1.08300, DIGITS),
                            signal="signal"),
            f"Signal active {p8.DASH} pending order at 1.08300, waiting.")

    def test_every_phase_eight_status_string(self):
        self.assertEqual(p8.gate_status(p8.GATE_AUTO_OFF),
                         f"No trade {p8.DASH} Auto Trading OFF")
        self.assertEqual(p8.live_position_status(),
                         f"Signal active {p8.DASH} position open, managing.")
        self.assertEqual(p8.rejected_status(10016),
                         f"Order rejected {p8.DASH} broker error 10016")
        self.assertEqual(p8.fresh_tp1_status(),
                         f"TP1 hit {p8.DASH} 50% closed, stop at breakeven.")
        self.assertEqual(p8.fresh_tp1_status(True, skipped=True),
                         f"TP1 hit {p8.DASH} partial skipped, stop at "
                         f"breakeven.")
        self.assertEqual(p8.fresh_tp1_status(False),
                         f"TP1 hit {p8.DASH} 50% closed, protection update "
                         f"pending.")
        self.assertEqual(p8.fresh_tp1_protection_status(),
                         f"TP1 hit {p8.DASH} protection active at breakeven.")
        self.assertEqual(p8.fresh_breakeven_status(),
                         f"Breakeven {p8.DASH} stop at entry, trailing "
                         f"active.")
        self.assertEqual(p8.fresh_trailing_status(1.08650, 32, DIGITS),
                         f"Trailing {p8.DASH} stop at 1.08650, +32 pts "
                         f"locked.")
        self.assertEqual(
            p8.fresh_position_closed_status(670, 44.00),
            f"Position closed {p8.DASH} +670 pts (+$44.00). Scanning for the "
            f"next setup.")

    def test_live_block_values(self):
        position = p8.LivePosition(
            ticket=48217291, side=p8.BUY, volume=0.50, entry=ENTRY,
            current=ENTRY + 88 * POINT, floating_money=44.00, stop=ENTRY,
            tp1=TARGET, tp2=1.09450, protect_method="Chandelier",
            stop_exists=True, breakeven=True, age_minutes=90,
            expected_duration="~2-4h")
        block = p8.live_block(position, point=POINT, digits=DIGITS,
                              volume_digits=2, timeframe_name="M15")
        self.assertEqual(block["header"],
                         f"{p8.DIAMOND_GLYPH} LIVE TRADE {p8.DASH} On M15")
        self.assertEqual(block["ticket"],
                         "Ticket: 48217291 | BUY 0.50 lots @ 1.08450")
        self.assertEqual(block["floating"],
                         "Floating P/L: +$44.00 (+88 pts)")
        self.assertEqual(block["live_sl"],
                         "Live SL: 1.08450 (88 pts) | TP1: 1.09120 "
                         "TP2: 1.09450")
        self.assertEqual(block["protect"],
                         "Protect: Chandelier | Age: 01:30 / ~2-4h")

    def test_live_block_before_any_stop(self):
        position = p8.LivePosition(
            ticket=7, side=p8.SELL, volume=0.10, entry=1.09000,
            current=1.09055, floating_money=-5.50, stop=0.0, tp1=1.08300,
            protect_method="", stop_exists=False, breakeven=False,
            age_minutes=5, expected_duration="~45-90m")
        block = p8.live_block(position, point=POINT, digits=DIGITS,
                              volume_digits=2)
        self.assertEqual(block["floating"],
                         "Floating P/L: -$5.50 (-55 pts)")
        self.assertEqual(block["live_sl"],
                         "Live SL: -- (-- pts) | TP1: 1.08300 TP2: --")
        self.assertEqual(block["protect"],
                         "Protect: Original | Age: 00:05 / ~45-90m")

    def test_a_pending_order_alone_opens_no_block(self):
        position = p8.LivePosition(ticket=1, side=p8.BUY, volume=0.10,
                                   entry=ENTRY, current=ENTRY,
                                   floating_money=0.0)
        self.assertIsNone(p8.live_block(position, point=POINT,
                                        digits=DIGITS, volume_digits=2,
                                        pending=True))
        self.assertIsNone(p8.live_block(None, point=POINT, digits=DIGITS,
                                        volume_digits=2))

    def test_duration_text_compaction(self):
        self.assertEqual(p6.format_duration(24, "M5"), "~1-3 hours")
        self.assertEqual(p8.compact_duration(p6.format_duration(24, "M5")),
                         "~1-3h")
        self.assertEqual(p8.compact_duration("~45-90 min"), "~45-90m")
        self.assertEqual(p8.compact_duration("> 3 days"), "> 3 days")

    def test_header_follows_the_input(self):
        self.assertEqual(p8.header_auto_trading(True), "Auto Trading: ON")
        self.assertEqual(p8.header_auto_trading(False), "Auto Trading: OFF")


if __name__ == "__main__":
    unittest.main()
