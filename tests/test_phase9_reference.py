"""Portable Phase 9 acceptance tests (Emtt.md 23.10 and 24).

Tests exercise the same plan builder and label sources as Phases 6-8, plus
persistence, event wiring, inclusive rate edges, frozen entry gates, and the
actual MQL source contract (with negative mutation controls).
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import phase6_reference as p6
import phase7_reference as p7
import phase8_reference as p8
import phase9_reference as p9
from phase2_reference import BEAR, BULL, RANGING, TRANSITION, VOLATILE
from tools import mql5_compile_smoke as smoke

T0 = datetime(2026, 10, 11, 9, 0)
T1 = T0 + timedelta(minutes=15)
T2 = T0 + timedelta(minutes=30)
T3 = T0 + timedelta(minutes=45)
POINT = 0.01


def context(side=1, pending=False):
    trend = p6.TrendView(ready=True, direction=side, score=0.63,
                         bars_since_flip=4, distance_atrs=2.0)
    structure = p6.StructureView(
        ready=True, bias=side, score=0.63, has_swing_low=True,
        newest_low_level=95.0, has_swing_high=True, newest_high_level=105.0,
        has_gap_above=True, gap_above_near_edge=125.0,
        has_gap_below=True, gap_below_near_edge=75.0,
        has_order_block=pending, order_block_bullish=side > 0,
        order_block_near_edge=100.0, order_block_low=95.0, order_block_high=105.0,
    )
    flow = p6.FlowView(ready=True, flow_direction=side, score=0.63)
    return trend, structure, flow


def signal(number=63, mood=RANGING, side=1, **kwargs):
    return p6.SignalState(views_ready=True, combined=side * number / 100,
                          confidence=number, mood=mood, mood_bar=p6.mood_bar(mood),
                          digits=2, point=POINT, **kwargs)


def ticket(result=p7.RESULT_TARGET, *, start=T0, mood="RANGING", side=1,
           filled=False, closed=False, net=10):
    plan = p7.Ticket(start, side, 82, (side,) * 4, mood, "LONDON", "NORMAL",
                      100.0, stop=90.0 if side > 0 else 110.0,
                      target=125.0 if side > 0 else 75.0, est=120,
                      state=p7.STATE_CLOSED if result else p7.STATE_ACTIVE,
                      result=result, exit_price=125.0, points=2500, candles=4)
    return p8.TradeTicket(plan, trade_filled=T0 if filled else None,
                          trade_closed=T1 if closed else None,
                          trade_net_points=net if closed else None)


def optimizer(**kwargs):
    disk = kwargs.pop("disk", p9.Disk())
    return p9.Optimizer(disk, T0, **kwargs)


def close(opt, *, reading=None, candle=None, bar=T1, sequence=1,
          side=1, pending=False, position_open=False, entry_bar=0, replay=False,
          views=None):
    trend, structure, flow = views or context(side, pending)
    return opt.advance(reading or signal(side=side), trend, structure, flow,
                       10.0, candle or p6.Candle(101.0, 99.0, 100.0),
                       100.0, 100.0, sequence, bar,
                       position_open=position_open, entry_bar=entry_bar, replay=replay)


def seed_near(opt, *, side=1, pending=False, mood="RANGING"):
    plan = p6.Plan(active=True, side=side,
                   entry_kind=p6.ENTRY_BLOCK if pending else p6.ENTRY_MARKET,
                   status=p6.PLAN_PENDING if pending else p6.PLAN_ACTIVE,
                   entry=100.0, stop=90.0 if side > 0 else 110.0,
                   target=125.0 if side > 0 else 75.0, risk_reward=2.5,
                   start_sequence=0, start_bar_time=T0, start_close=100.0)
    opt.near = p9.Near(plan, mood, 63, 70, 2, POINT, T0)
    opt.live_candle = True
    return plan


def evidence(bar=70, base=70, a=(14, 6), n=(13, 7), moves=0):
    return p9.Cell(bar, base, *a, *n, moves)


class InputAndScopeTests(unittest.TestCase):
    def test_default_input_enables_all_four_base_cells(self):
        opt = optimizer()
        self.assertTrue(opt.enabled)
        self.assertEqual({m: c.bar for m, c in opt.file.cells.items()}, p9.BASE_BARS)
        self.assertIn(opt.file.path, opt.disk.files)

    def test_off_never_creates_reads_or_writes_params(self):
        disk = p9.Disk()
        path = p9.path_for("EURUSD", "M15")
        disk.files[path] = "untouched version and contents"
        opt = optimizer(disk=disk, enabled=False)
        self.assertFalse(opt.queue_accepted(ticket(), "M15", T1))
        close(opt)
        opt.deinit(T2)
        self.assertIsNone(opt.near)
        self.assertEqual(disk.files[path], "untouched version and contents")
        self.assertEqual(disk.operations, [])
        self.assertEqual(opt.journal, [])
        self.assertEqual(opt.file.journal, [])

    def test_off_supplies_zero_so_every_phase_eight_base_gate_is_unchanged(self):
        opt = optimizer(enabled=False)
        for mood in (BULL, BEAR, RANGING, VOLATILE, TRANSITION, "UNKNOWN"):
            with self.subTest(mood=mood):
                self.assertEqual(opt.learned_bar(mood), 0)
                self.assertEqual(opt.gate_bar(mood), p6.mood_bar(mood))

    def test_toggling_off_then_on_resumes_without_deleting_file(self):
        disk = p9.Disk()
        on = optimizer(disk=disk)
        on.file.cells["RANGING"].bar = 60
        on.file.cells["RANGING"].a_w = 7
        on.deinit(T1)
        saved = disk.files.copy()
        off = optimizer(disk=disk, enabled=False)
        close(off)
        off.deinit(T2)
        self.assertEqual(disk.files, saved)
        again = optimizer(disk=disk)
        self.assertEqual(again.gate_bar(RANGING), 60)
        self.assertEqual(again.file.cells["RANGING"].a_w, 7)

    def test_input_is_a_session_snapshot_not_a_trading_toggle(self):
        opt = optimizer()
        for auto_trading in (False, True):
            self.assertEqual(p8.header_auto_trading(auto_trading),
                             "Auto Trading: ON" if auto_trading else "Auto Trading: OFF")
            self.assertTrue(opt.enabled)
        self.assertEqual(p9.CANDIDATES, (60, 70, 75))

    def test_unknown_mood_has_no_learned_bar(self):
        self.assertEqual(optimizer().learned_bar("UNKNOWN"), 0)

    def test_near_does_not_mutate_the_real_signal_or_learning_tickets(self):
        opt = optimizer()
        actual = signal()
        saved = deepcopy(actual)
        record = p7.LearningFile(tickets=[ticket().plan])
        before = deepcopy(record.tickets)
        model = p7.build_model(record.tickets)
        close(opt, reading=actual)
        self.assertIsNotNone(opt.near)
        self.assertEqual(actual, saved)
        self.assertEqual(record.tickets, before)
        self.assertEqual(p7.build_model(record.tickets), model)
        self.assertFalse(actual.plan.active)
        self.assertEqual(actual.signal, 0)
        self.assertIsNone(p8.live_block(None, point=POINT, digits=2, volume_digits=2))

    def test_incompatible_charts_never_evaluate_near_or_move(self):
        for timeframe in ("H1", "H4", "M1"):
            with self.subTest(timeframe=timeframe):
                opt = optimizer(timeframe=timeframe)
                opt.file.cells["RANGING"] = evidence()
                before = deepcopy(opt.file.cells)
                close(opt)
                self.assertEqual(opt.file.cells, before)
                self.assertIsNone(opt.near)


class DecisionRuleTests(unittest.TestCase):
    def test_twenty_is_required_in_both_populations(self):
        for a, n in (((13, 6), (13, 7)), ((14, 6), (12, 7)), ((13, 6), (12, 7))):
            with self.subTest(a=a, n=n):
                cell = evidence(a=a, n=n)
                saved = deepcopy(cell)
                journal = []
                self.assertFalse(p9.decide(cell, "RANGING", T1, journal))
                self.assertEqual(cell, saved)
                self.assertEqual(journal, [])

    def test_exactly_twenty_in_each_population_can_decide(self):
        cell = evidence(a=(14, 6), n=(13, 7))
        self.assertTrue(p9.decide(cell, "RANGING", T1, []))
        self.assertEqual(cell.bar, 60)

    def test_exact_five_percent_edge_loosens(self):
        cell = evidence(a=(14, 6), n=(13, 7))
        journal = []
        p9.decide(cell, "RANGING", T1, journal)
        self.assertEqual(cell.bar, 60)
        self.assertIn("accepted 14/6 (70%), near 13/7 (65%)", journal[0])

    def test_exact_twenty_percent_edge_tightens_even_at_float_roundoff_case(self):
        # 0.7 - 0.2 is not represented exactly; no subtraction comparison.
        cell = evidence(a=(14, 6), n=(10, 10))
        self.assertTrue(p9.decide(cell, "RANGING", T1, []))
        self.assertEqual(cell.bar, 75)

    def test_neutral_band_holds_and_preserves_tallies(self):
        for wins in (11, 12):
            cell = evidence(n=(wins, 20 - wins))
            saved = deepcopy(cell)
            journal = []
            self.assertFalse(p9.decide(cell, "RANGING", T1, journal))
            self.assertEqual(cell, saved)
            self.assertEqual(journal, [])

    def test_all_twenty_sample_pairs_match_exact_rational_rule(self):
        for a_w in range(21):
            for n_w in range(21):
                with self.subTest(a_w=a_w, n_w=n_w):
                    a, n = Fraction(a_w, 20), Fraction(n_w, 20)
                    direction = -1 if n >= a - Fraction(5, 100) else (
                        1 if n <= a - Fraction(20, 100) else 0)
                    cell = evidence(a=(a_w, 20 - a_w), n=(n_w, 20 - n_w))
                    did = p9.decide(cell, "RANGING", T1, [])
                    self.assertEqual(did, direction != 0)
                    self.assertEqual(cell.bar, 60 if direction < 0 else 75 if direction > 0 else 70)

    def test_different_population_sizes_use_rates_not_win_counts(self):
        # 80% accepted; 75% near, exactly the inclusive loosen edge.
        cell = evidence(a=(80, 20), n=(15, 5))
        p9.decide(cell, "RANGING", T1, [])
        self.assertEqual(cell.bar, 60)

    def test_only_one_candidate_step_per_decision(self):
        for bar, a, n, expected in (
            (75, (20, 0), (20, 0), 70),
            (70, (20, 0), (20, 0), 60),
            (60, (20, 0), (0, 20), 70),
            (70, (20, 0), (0, 20), 75),
        ):
            with self.subTest(bar=bar, expected=expected):
                cell = evidence(bar=bar, a=a, n=n)
                p9.decide(cell, "RANGING", T1, [])
                self.assertEqual(cell.bar, expected)
                self.assertIn(cell.bar, p9.CANDIDATES)

    def test_lower_limit_is_a_held_decision_with_reset(self):
        cell = evidence(bar=60, base=60)
        journal = []
        self.assertTrue(p9.decide(cell, "TRENDING", T1, journal))
        self.assertEqual(cell.bar, 60)
        self.assertEqual((cell.accepted, cell.near, cell.moves), (0, 0, 1))
        self.assertIn("Param bar held | TRENDING at the approved limit 60", journal[0])

    def test_upper_limit_is_a_held_decision_with_reset(self):
        cell = evidence(bar=75, base=75, n=(10, 10))
        journal = []
        self.assertTrue(p9.decide(cell, "TRANSITION", T1, journal))
        self.assertEqual(cell.bar, 75)
        self.assertEqual((cell.accepted, cell.near, cell.moves), (0, 0, 1))
        self.assertIn("approved limit 75", journal[0])

    def test_move_resets_both_tallies_and_requires_forty_fresh_results(self):
        cell = evidence()
        p9.decide(cell, "RANGING", T1, [])
        self.assertEqual((cell.a_w, cell.a_l, cell.n_w, cell.n_l), (0, 0, 0, 0))
        self.assertFalse(p9.decide(cell, "RANGING", T2, []))
        cell.a_w, cell.n_w = 19, 20
        self.assertFalse(p9.decide(cell, "RANGING", T2, []))
        cell.a_w = 20
        self.assertTrue(p9.decide(cell, "RANGING", T3, []))
        self.assertEqual(cell.moves, 2)

    def test_four_cells_are_independent(self):
        opt = optimizer()
        opt.file.cells["RANGING"] = evidence()
        before = {m: deepcopy(opt.file.cells[m]) for m in p9.MOODS if m != "RANGING"}
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        for mood, cell in before.items():
            self.assertEqual(opt.file.cells[mood], cell)
        self.assertEqual(opt.file.cells["RANGING"].bar, 60)

    def test_two_moods_can_move_on_one_candle_and_are_journaled_separately(self):
        opt = optimizer()
        opt.file.cells["RANGING"] = evidence()
        opt.file.cells["VOLATILE"] = evidence(n=(10, 10))
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.cells["RANGING"].bar, 60)
        self.assertEqual(opt.file.cells["VOLATILE"].bar, 75)
        moved = [line for line in opt.file.journal if "Param bar moved" in line]
        self.assertEqual(len(moved), 2)
        self.assertEqual(opt.file.write_events, ["init_after_load", "decision"])

    def test_move_applies_on_next_close_not_on_the_decision_candle(self):
        opt = optimizer()
        opt.file.cells["RANGING"] = evidence()
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.cells["RANGING"].bar, 60)
        self.assertEqual(opt.gate_bar(RANGING), 70)
        close(opt, bar=T2, sequence=2, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.gate_bar(RANGING), 60)

    def test_decision_is_saved_but_does_not_change_an_open_positions_bar(self):
        opt = optimizer()
        opt.file.cells["RANGING"] = evidence()
        close(opt, reading=signal(100, plan=p6.Plan(active=True)), position_open=True, entry_bar=70)
        self.assertEqual(opt.gate_bar(RANGING), 70)
        self.assertEqual(opt.file.cells["RANGING"].bar, 60)
        saved = p9.ParameterFile.load(opt.disk, "EURUSD", "M15", T1)
        self.assertEqual(saved.cells["RANGING"].bar, 60)
        close(opt, bar=T2, sequence=2, position_open=True, entry_bar=60,
              reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.gate_bar(RANGING), 70)
        close(opt, bar=T3, sequence=3, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.gate_bar(RANGING), 60)

    def test_frozen_entry_bar_stays_frozen_even_if_market_mood_changes(self):
        opt = optimizer()
        opt.freeze_at_entry(70)
        opt.freeze_at_entry(75)
        self.assertEqual(opt.gate_bar(BULL), 70)
        self.assertEqual(opt.gate_bar(TRANSITION), 70)

    def test_existing_entry_snapshot_can_restore_freeze_after_restart(self):
        disk = p9.Disk()
        original = optimizer(disk=disk)
        original.file.cells["RANGING"].bar = 60
        original.deinit(T1)
        restored = optimizer(disk=disk)
        restored.freeze_at_entry(70)  # the existing GlobalVariable, no new one
        self.assertEqual(restored.gate_bar(RANGING), 70)
        close(restored, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(restored.gate_bar(RANGING), 60)

    def test_recovered_trade_keeps_its_entry_bar_not_the_ticket_binders_base(self):
        opt = optimizer()
        opt.file.cells["RANGING"].bar = 75  # a pending decision, not the entry
        opt.freeze_at_entry(60)  # the existing entry snapshot on re-attach
        self.assertEqual(opt.trade_entry_bar(70, position_open=True), 60)
        self.assertEqual(opt.trade_entry_bar(70, position_open=False), 70)
        self.assertEqual(opt.gate_bar(RANGING), 60)

    def test_off_never_overrides_the_phase_eight_trade_binder(self):
        opt = optimizer(enabled=False)
        opt.freeze_at_entry(60)
        self.assertEqual(opt.trade_entry_bar(70, position_open=True), 70)
        self.assertEqual(opt.learned_bar(RANGING), 0)

    def test_stay_margin_and_wait_wording_read_the_actual_learned_bar(self):
        opt = optimizer()
        opt.file.cells["RANGING"].bar = 60
        opt.begin_candle(T1)
        state = signal(58, wait_reason=p6.WAIT_BELOW_BAR)
        state.mood_bar = opt.gate_bar(RANGING)
        self.assertEqual(state.confidence, 58)
        self.assertIn("below the 60% bar", p6.wait_text(state))
        state.wait_reason = p6.WAIT_BELOW_KEEP
        state.wait_side = 1
        self.assertIn("below the 55% level", p6.wait_text(state))


class NearQualificationTests(unittest.TestCase):
    def test_true_input_is_required(self):
        opt = optimizer(enabled=False)
        close(opt)
        self.assertIsNone(opt.near)

    def test_an_active_real_plan_rejects_a_near_miss(self):
        opt = optimizer()
        close(opt, reading=signal(plan=p6.Plan(active=True)))
        self.assertIsNone(opt.near)

    def test_a_candle_that_just_ended_a_real_plan_rejects_a_near_miss(self):
        opt = optimizer()
        close(opt, reading=signal(just_ended=True))
        self.assertIsNone(opt.near)

    def test_four_ready_views_are_required(self):
        opt = optimizer()
        close(opt, reading=replace(signal(), views_ready=False))
        self.assertIsNone(opt.near)

    def test_a_four_view_side_is_required(self):
        opt = optimizer()
        close(opt, reading=replace(signal(), combined=0.0))
        self.assertIsNone(opt.near)

    def test_band_edges_are_inclusive_at_ten_but_exclusive_at_the_bar(self):
        for number, expected in ((59, False), (60, True), (69, True), (70, False), (71, False)):
            with self.subTest(number=number):
                opt = optimizer()
                close(opt, reading=signal(number))
                self.assertEqual(opt.near is not None, expected)

    def test_trending_and_transition_use_their_own_band_edges(self):
        for mood, number, expected in ((BULL, 50, True), (BEAR, 49, False),
                                       (TRANSITION, 65, True), (TRANSITION, 64, False)):
            opt = optimizer()
            close(opt, reading=signal(number, mood))
            self.assertEqual(opt.near is not None, expected)

    def test_a_learned_bar_defines_the_near_population(self):
        opt = optimizer()
        opt.file.cells["RANGING"].bar = 75
        close(opt, reading=signal(64))
        self.assertIsNone(opt.near)
        close(opt, reading=signal(65), bar=T2, sequence=2)
        self.assertIsNotNone(opt.near)
        self.assertEqual(opt.near.bar, 75)

    def test_no_swing_rejects_a_near_miss(self):
        trend, structure, flow = context()
        opt = optimizer()
        close(opt, views=(trend, replace(structure, has_swing_low=False), flow))
        self.assertIsNone(opt.near)

    def test_stop_too_far_rejects_a_near_miss(self):
        trend, structure, flow = context()
        opt = optimizer()
        close(opt, views=(trend, replace(structure, newest_low_level=60.0), flow))
        self.assertIsNone(opt.near)

    def test_no_real_target_rejects_a_near_miss(self):
        trend, structure, flow = context()
        opt = optimizer()
        close(opt, views=(trend, replace(structure, has_gap_above=False), flow))
        self.assertIsNone(opt.near)

    def test_plan_build_false_is_rejected_even_without_a_failure_word(self):
        opt = optimizer()
        opt.live_candle = True
        trend, structure, flow = context()
        self.assertFalse(opt.consider_near(signal(), trend, structure, flow, 0.0,
                                           p6.Candle(101, 99, 100), 100, 100, 1, T1))
        self.assertIsNone(opt.near)

    def test_levels_are_exactly_the_existing_plan_builders_levels(self):
        opt = optimizer()
        trend, structure, flow = context()
        built, fail = p6.build_plan(1, structure, flow, trend, 10, 100, 100, 100, RANGING, "M15")
        close(opt)
        self.assertEqual(fail, p6.FAIL_NONE)
        for name in ("entry", "stop", "target", "risk_reward", "duration", "entry_kind", "status"):
            self.assertEqual(getattr(opt.near.plan, name), getattr(built, name))
        self.assertIn("entry 100.00 | stop 90.00 | target 125.00 | RR 1:2.5", opt.journal[0])

    def test_sell_is_the_exact_mirror(self):
        opt = optimizer()
        close(opt, side=-1)
        self.assertEqual((opt.near.plan.entry, opt.near.plan.stop, opt.near.plan.target), (100, 110, 75))
        self.assertIn("Near miss started | SELL", opt.journal[0])

    def test_an_order_block_entry_is_pending_not_a_real_order(self):
        opt = optimizer()
        close(opt, pending=True, candle=p6.Candle(106, 104, 105))
        self.assertEqual(opt.near.plan.status, p6.PLAN_PENDING)
        self.assertEqual(opt.near.plan.entry_kind, p6.ENTRY_BLOCK)

    def test_start_candle_is_never_checked_against_its_own_levels(self):
        opt = optimizer()
        close(opt, candle=p6.Candle(130, 80, 100))
        self.assertIsNotNone(opt.near)
        self.assertEqual(opt.file.cells["RANGING"].near, 0)
        close(opt, candle=p6.Candle(130, 80, 100))
        self.assertEqual(opt.file.cells["RANGING"].near, 0)

    def test_an_unresolved_near_miss_is_replaced_and_journaled(self):
        opt = optimizer()
        close(opt)
        first = opt.near.plan.start_bar_time
        close(opt, reading=signal(65), bar=T2, sequence=2)
        self.assertEqual(first, T1)
        self.assertEqual(opt.near.plan.start_bar_time, T2)
        self.assertEqual(opt.near.confidence, 65)
        self.assertIn("Near miss replaced", opt.journal[-1])
        self.assertIn("previous BUY from 2026.10.11 09:15", opt.journal[-1])
        self.assertEqual(opt.file.cells["RANGING"].near, 0)

    def test_a_watch_that_does_not_change_is_not_journaled(self):
        opt = optimizer()
        seed_near(opt)
        before = opt.journal.copy()
        self.assertFalse(opt.watch_near(signal(65), p6.Candle(102, 101, 101), 1, T1))
        self.assertEqual(opt.journal, before)

    def test_same_or_older_candle_is_not_evaluated_twice(self):
        opt = optimizer()
        close(opt)
        count = len(opt.journal)
        close(opt, reading=signal(65), bar=T1)
        close(opt, reading=signal(65), bar=T0)
        self.assertEqual(len(opt.journal), count)


class NearLifecycleTests(unittest.TestCase):
    def test_watch_cannot_run_during_replay_or_outside_a_live_candle(self):
        opt = optimizer()
        seed_near(opt)
        opt.replaying = True
        self.assertFalse(opt.watch_near(signal(65), p6.Candle(126, 89, 100), 1, T1))
        opt.replaying = False
        opt.live_candle = False
        self.assertFalse(opt.watch_near(signal(65), p6.Candle(126, 89, 100), 1, T1))
        self.assertIsNotNone(opt.near)
        self.assertEqual(opt.file.cells["RANGING"].near, 0)
        self.assertEqual(opt.journal, [])

    def test_missing_views_cannot_manufacture_a_label_from_price_touches(self):
        opt = optimizer()
        seed_near(opt)
        opt.watch_near(replace(signal(65), views_ready=False), p6.Candle(126, 89, 100), 1, T1)
        self.assertIsNone(opt.near)
        self.assertEqual(opt.file.cells["RANGING"].near, 0)
        self.assertIn("chart", opt.journal[-1])

    def test_active_target_is_a_win_with_points_and_candles(self):
        opt = optimizer()
        seed_near(opt)
        opt.watch_near(signal(65), p6.Candle(126, 124, 125), 12, T1)
        self.assertEqual(opt.file.cells["RANGING"].n_w, 1)
        self.assertIsNone(opt.near)
        self.assertIn("target | +2500 pts | 12 candles | RANGING near 1/0", opt.journal[-1])

    def test_active_stop_is_a_loss(self):
        opt = optimizer()
        seed_near(opt)
        opt.watch_near(signal(65), p6.Candle(91, 89, 90), 1, T1)
        self.assertEqual(opt.file.cells["RANGING"].n_l, 1)
        self.assertIn("stop | -1000 pts", opt.journal[-1])

    def test_active_sell_target_and_stop_have_correct_signed_points(self):
        for candle, result, points in ((p6.Candle(76, 74, 75), "target", "+2500"),
                                        (p6.Candle(111, 109, 110), "stop", "-1000")):
            opt = optimizer()
            seed_near(opt, side=-1)
            opt.watch_near(signal(65, side=-1), candle, 1, T1)
            self.assertIn(f"{result} | {points} pts", opt.journal[-1])

    def test_stop_wins_when_active_candle_touches_both_end_levels(self):
        opt = optimizer()
        seed_near(opt)
        opt.watch_near(signal(65), p6.Candle(126, 89, 100), 1, T1)
        self.assertEqual((opt.file.cells["RANGING"].n_w, opt.file.cells["RANGING"].n_l), (0, 1))
        self.assertIn("shared candle", opt.journal[-1])

    def test_pending_stop_without_entry_is_cancelled_not_a_loss(self):
        opt = optimizer()
        seed_near(opt, pending=True)
        opt.watch_near(signal(65), p6.Candle(91, 89, 90), 1, T1)
        self.assertEqual(opt.file.cells["RANGING"].near, 0)
        self.assertIn("cancelled", opt.journal[-1])

    def test_pending_entry_plus_stop_is_a_shared_loss(self):
        opt = optimizer()
        seed_near(opt, pending=True)
        opt.watch_near(signal(65), p6.Candle(101, 89, 100), 1, T1)
        self.assertEqual(opt.file.cells["RANGING"].n_l, 1)
        self.assertIn("shared candle", opt.journal[-1])

    def test_pending_target_is_missed_even_when_entry_shares_the_candle(self):
        for candle in (p6.Candle(126, 124, 125), p6.Candle(126, 99, 100)):
            opt = optimizer()
            seed_near(opt, pending=True)
            opt.watch_near(signal(65), candle, 1, T1)
            self.assertEqual(opt.file.cells["RANGING"].near, 0)
            self.assertIn("missed", opt.journal[-1])

    def test_pending_candle_touching_all_levels_is_a_shared_stop(self):
        opt = optimizer()
        seed_near(opt, pending=True)
        opt.watch_near(signal(65), p6.Candle(126, 89, 100), 1, T1)
        self.assertEqual(opt.file.cells["RANGING"].n_l, 1)
        self.assertIn("stop", opt.journal[-1])
        self.assertIn("shared candle", opt.journal[-1])

    def test_pending_entry_becomes_active_then_can_win(self):
        opt = optimizer()
        seed_near(opt, pending=True)
        self.assertFalse(opt.watch_near(signal(65), p6.Candle(101, 99, 100), 1, T1))
        self.assertEqual(opt.near.plan.status, p6.PLAN_ACTIVE)
        opt.watch_near(signal(65), p6.Candle(126, 124, 125), 2, T2)
        self.assertEqual(opt.file.cells["RANGING"].n_w, 1)

    def test_active_entry_and_target_marks_a_shared_win(self):
        opt = optimizer()
        seed_near(opt)
        opt.watch_near(signal(65), p6.Candle(126, 99, 125), 1, T1)
        self.assertEqual(opt.file.cells["RANGING"].n_w, 1)
        self.assertIn("shared candle", opt.journal[-1])

    def test_signal_change_or_below_stay_margin_has_no_tally(self):
        for reading in (signal(64), signal(65, side=-1)):
            opt = optimizer()
            seed_near(opt)
            opt.watch_near(reading, p6.Candle(102, 101, 101), 1, T1)
            self.assertEqual(opt.file.cells["RANGING"].near, 0)
            self.assertIn("signal", opt.journal[-1])

    def test_exact_stay_margin_keeps_near_alive(self):
        opt = optimizer()
        seed_near(opt)
        self.assertFalse(opt.watch_near(signal(65), p6.Candle(102, 101, 101), 1, T1))
        self.assertIsNotNone(opt.near)

    def test_price_end_has_precedence_over_confidence_failure(self):
        opt = optimizer()
        seed_near(opt)
        opt.watch_near(signal(0), p6.Candle(126, 124, 125), 1, T1)
        self.assertEqual(opt.file.cells["RANGING"].n_w, 1)

    def test_market_chart_and_other_nonlabels_do_not_change_tallies(self):
        for result in (p7.RESULT_MISSED, p7.RESULT_CANCELLED, p7.RESULT_SIGNAL,
                       p7.RESULT_MARKET, p7.RESULT_CHART):
            opt = optimizer()
            seed_near(opt)
            opt.end_near(result, 101.0, 1, T1)
            self.assertEqual(opt.file.cells["RANGING"].near, 0)

    def test_level_must_lie_in_candle_range_not_just_be_passed_by_a_gap(self):
        opt = optimizer()
        seed_near(opt)
        self.assertFalse(opt.watch_near(signal(65), p6.Candle(127, 126, 126), 1, T1))
        self.assertIsNotNone(opt.near)
        self.assertEqual(opt.file.cells["RANGING"].near, 0)

    def test_no_new_near_on_the_candle_that_ended_the_old_near(self):
        opt = optimizer()
        seed_near(opt)
        opt.live_candle = False
        close(opt, reading=signal(65), candle=p6.Candle(126, 124, 125))
        self.assertIsNone(opt.near)
        self.assertEqual(opt.file.cells["RANGING"].n_w, 1)
        self.assertNotIn("replaced", "\n".join(opt.journal))

    def test_result_belongs_to_start_mood_not_current_market_mood(self):
        opt = optimizer()
        seed_near(opt, mood="RANGING")
        opt.watch_near(signal(70, TRANSITION), p6.Candle(126, 124, 125), 1, T1)
        self.assertEqual(opt.file.cells["RANGING"].n_w, 1)
        self.assertEqual(opt.file.cells["TRANSITION"].near, 0)

    def test_unresolved_near_is_deliberately_lost_on_restart(self):
        opt = optimizer()
        close(opt)
        opt.deinit(T1)
        restarted = optimizer(disk=opt.disk)
        self.assertIsNone(restarted.near)
        self.assertEqual(restarted.file.cells["RANGING"].near, 0)


class AcceptedEvidenceTests(unittest.TestCase):
    def test_paper_target_and_stop_labels_use_ticket_start_mood(self):
        opt = optimizer()
        opt.queue_accepted(ticket(start=T0, result="target"), "M15", T1)
        opt.queue_accepted(ticket(start=T0 - timedelta(minutes=15), result="stop"), "M15", T1)
        close(opt, reading=signal(80, VOLATILE, plan=p6.Plan(active=True)))
        self.assertEqual((opt.file.cells["RANGING"].a_w, opt.file.cells["RANGING"].a_l), (1, 1))
        self.assertEqual(opt.file.cells["VOLATILE"].accepted, 0)

    def test_real_net_overrides_paper_target_or_stop(self):
        cases = (("stop", 10, 1), ("target", -5, 0), ("target", 0, None))
        for result, net, expected in cases:
            actual = ticket(result, filled=True, closed=True, net=net)
            self.assertEqual(p9.accepted_label(actual), expected)

    def test_a_live_filled_trade_does_not_use_its_paper_label(self):
        opt = optimizer()
        self.assertFalse(opt.queue_accepted(ticket(filled=True), "M15", T1))
        self.assertEqual(opt.file.cells["RANGING"].accepted, 0)

    def test_other_paper_results_are_unlabeled(self):
        for result in ("", "missed", "cancelled", "signal", "market", "chart"):
            self.assertIsNone(p9.accepted_label(ticket(result)))

    def test_broker_result_waits_for_a_live_closed_candle(self):
        opt = optimizer()
        self.assertTrue(opt.queue_accepted(ticket(filled=True, closed=True), "M15", T1))
        self.assertEqual(opt.file.cells["RANGING"].accepted, 0)
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.cells["RANGING"].a_w, 1)

    def test_future_result_is_not_consumed_before_its_candle_closed(self):
        opt = optimizer()
        opt.queue_accepted(ticket(), "M15", T0 + timedelta(minutes=40))
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.cells["RANGING"].accepted, 0)
        close(opt, reading=signal(100, plan=p6.Plan(active=True)), bar=T2, sequence=2)
        self.assertEqual(opt.file.cells["RANGING"].accepted, 1)

    def test_retry_before_and_after_consumption_never_counts_a_ticket_twice(self):
        opt = optimizer()
        item = ticket(filled=True, closed=True)
        self.assertTrue(opt.queue_accepted(item, "M15", T1))
        self.assertFalse(opt.queue_accepted(item, "M15", T1))
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertFalse(opt.queue_accepted(item, "M15", T2))
        self.assertEqual(opt.file.cells["RANGING"].accepted, 1)

    def test_trade_from_another_chart_timeframe_goes_only_to_original_file(self):
        opt = optimizer(timeframe="M5")
        opt.queue_accepted(ticket(filled=True, closed=True), "M15", T1)
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.cells["RANGING"].accepted, 0)
        self.assertEqual(opt.carried_file.cells["RANGING"].accepted, 1)
        opt.deinit(T2)
        saved = p9.ParameterFile.load(opt.disk, "EURUSD", "M15", T2)
        self.assertEqual(saved.cells["RANGING"].accepted, 1)

    def test_shutdown_flushes_labeled_broker_results_without_a_move_or_near_evaluation(self):
        opt = optimizer()
        opt.file.cells["RANGING"] = evidence(a=(13, 6))
        opt.queue_accepted(ticket(filled=True, closed=True), "M15", T1)
        seed_near(opt)
        opt.live_candle = False
        opt.deinit(T1)
        saved = p9.ParameterFile.load(opt.disk, "EURUSD", "M15", T1)
        self.assertEqual(saved.cells["RANGING"].accepted, 20)
        self.assertEqual(saved.cells["RANGING"].near, 20)
        self.assertEqual(saved.cells["RANGING"].bar, 70)
        self.assertEqual(saved.cells["RANGING"].moves, 0)
        self.assertEqual(opt.journal, [])
        resumed = optimizer(disk=opt.disk)
        close(resumed, replay=True)
        self.assertEqual(resumed.file.cells["RANGING"].accepted, 20)
        close(resumed, reading=signal(100, plan=p6.Plan(active=True)), bar=T2, sequence=2)
        self.assertEqual(resumed.file.cells["RANGING"].bar, 60)

    def test_shutdown_keeps_foreign_trade_evidence_in_its_own_file_on_h1(self):
        opt = optimizer(timeframe="H1")
        opt.queue_accepted(ticket(filled=True, closed=True), "M15", T1)
        opt.deinit(T1)
        self.assertEqual(opt.file.cells["RANGING"].accepted, 0)
        source = p9.ParameterFile.load(opt.disk, "EURUSD", "M15", T1)
        self.assertEqual(source.cells["RANGING"].accepted, 1)
        self.assertEqual(source.cells["RANGING"].moves, 0)
        self.assertIsNone(opt.near)

    def test_malformed_ticket_side_or_start_is_not_evidence(self):
        opt = optimizer()
        item = ticket()
        item.plan.side = 0
        self.assertFalse(opt.queue_accepted(item, "M15", T1))
        item.plan.side = 1
        item.plan.start_bar_time = None
        self.assertFalse(opt.queue_accepted(item, "M15", T1))

    def test_symbols_and_broker_suffixes_never_pool_evidence(self):
        opt = optimizer(symbol="EURUSD.pro")
        self.assertFalse(opt.queue_accepted(ticket(), "M15", T1, symbol="EURUSD"))
        self.assertFalse(opt.queue_accepted(ticket(), "M15", T1, symbol="GBPUSD"))
        self.assertTrue(opt.queue_accepted(ticket(), "M15", T1, symbol="EURUSD.pro"))
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.cells["RANGING"].accepted, 1)
        self.assertEqual(set(opt.disk.files), {p9.path_for("EURUSD.pro", "M15")})

    def test_saved_accepted_tallies_are_independent_per_symbol(self):
        disk = p9.Disk()
        first = optimizer(disk=disk, symbol="EURUSD")
        first.queue_accepted(ticket(), "M15", T1, symbol="EURUSD")
        first.deinit(T1)
        second = optimizer(disk=disk, symbol="GBPUSD")
        self.assertEqual(second.file.cells["RANGING"].accepted, 0)
        first_again = optimizer(disk=disk, symbol="EURUSD")
        self.assertEqual(first_again.file.cells["RANGING"].accepted, 1)

    def test_no_evidence_is_queued_during_replay(self):
        opt = optimizer()
        opt.replaying = True
        self.assertFalse(opt.queue_accepted(ticket(), "M15", T1))
        self.assertEqual(opt.pending, [])

    def test_replay_does_not_consume_queued_evidence_or_evaluate_near(self):
        opt = optimizer()
        opt.queue_accepted(ticket(), "M15", T1)
        before = deepcopy(opt.file.cells)
        writes = list(opt.file.write_events)
        close(opt, replay=True)
        self.assertEqual(opt.file.cells, before)
        self.assertEqual(len(opt.pending), 1)
        self.assertIsNone(opt.near)
        self.assertEqual(opt.file.write_events, writes)

    def test_replay_does_not_decide_even_when_both_populations_are_ready(self):
        opt = optimizer()
        opt.file.cells["RANGING"] = evidence()
        before = deepcopy(opt.file.cells)
        close(opt, replay=True)
        self.assertEqual(opt.file.cells, before)
        self.assertEqual(opt.gate_bar(RANGING), 70)


class ParameterFileTests(unittest.TestCase):
    def test_six_line_ascii_crlf_roundtrip_with_fixed_cell_order(self):
        opt = optimizer(symbol="XAUUSD.pro")
        opt.file.cells["RANGING"] = evidence(moves=2)
        text = opt.file.render(T1)
        self.assertTrue(text.isascii())
        self.assertEqual(text.count("\r\n"), 6)
        self.assertEqual(text.splitlines()[0], "Emtt_Params v1 | XAUUSD.pro | M15")
        self.assertEqual([line.split(" |")[0] for line in text.splitlines()[2:]],
                         ["cell " + mood for mood in p9.MOODS])
        opt.file.save(opt.disk, T1, "deinit")
        loaded = p9.ParameterFile.load(opt.disk, "XAUUSD.pro", "M15", T1)
        self.assertEqual(loaded.cells, opt.file.cells)
        self.assertEqual(loaded.render(T1), text)

    def test_filename_reuses_learning_sanitizer_and_preserves_broker_suffixes(self):
        for symbol in ("XAUUSD.pro", "USD/JPY", "../EURUSD", "BTC USD", "\u20acUSD"):
            self.assertEqual(p9.path_for(symbol, "M30"),
                             p7.learn_file_path(symbol, "M30").replace(".learn", ".params"))
        self.assertEqual(p9.path_for("XAUUSD.pro", "M30"), "Emtt_Learning\\XAUUSD.pro_M30.params")

    def test_summary_is_recomputed_from_cells_not_trusted(self):
        disk = p9.Disk()
        state = p9.ParameterFile(loaded=True)
        state.cells["RANGING"] = evidence(moves=2)
        lines = state.render(T1).splitlines()
        lines[1] = "counts tickets 999 | near 999 | labeled 999 | moves 999 | updated nonsense"
        disk.files[state.path] = "\r\n".join(lines) + "\r\n"
        loaded = p9.ParameterFile.load(disk, "EURUSD", "M15", T1)
        self.assertEqual(loaded.summary(T1),
                         "counts tickets 20 | near 20 | labeled 40 | moves 2 | updated 2026.10.11 09:15")
        loaded.save(disk, T1, "init_after_load")
        self.assertNotIn("999", disk.files[state.path])

    def test_malformed_cell_starts_only_that_mood_fresh(self):
        disk = p9.Disk()
        state = p9.ParameterFile(loaded=True)
        for mood in p9.MOODS:
            state.cells[mood].a_w = 3
        lines = state.render(T1).splitlines()
        lines[3] = lines[3].replace("bar 70", "bar 62.5")
        disk.files[state.path] = "\r\n".join(lines) + "\r\n"
        loaded = p9.ParameterFile.load(disk, "EURUSD", "M15", T1)
        self.assertEqual(loaded.cells["RANGING"], p9.Cell.fresh("RANGING"))
        self.assertEqual([loaded.cells[m].a_w for m in ("TRENDING", "VOLATILE", "TRANSITION")], [3, 3, 3])
        self.assertEqual(loaded.damaged_warned, {"RANGING"})

    def test_unknown_version_leaves_real_and_tmp_files_untouched(self):
        disk = p9.Disk()
        path = p9.path_for("EURUSD", "M15")
        disk.files[path] = "Emtt_Params v2 | EURUSD | M15\r\nfuture data\r\n"
        disk.files[path + ".tmp"] = "future tmp"
        saved = disk.files.copy()
        opt = optimizer(disk=disk)
        opt.deinit(T1)
        self.assertTrue(opt.file.read_only)
        self.assertEqual(disk.files, saved)
        self.assertEqual(opt.effective, p9.BASE_BARS)
        self.assertEqual(sum("version unknown" in line for line in opt.file.journal), 1)

    def test_unknown_version_keeps_base_bars_for_the_entire_session(self):
        disk = p9.Disk()
        path = p9.path_for("EURUSD", "M15")
        disk.files[path] = "Emtt_Params v2 | EURUSD | M15\r\nfuture data\r\n"
        before = disk.files.copy()
        opt = optimizer(disk=disk)
        opt.file.cells["RANGING"] = evidence()
        self.assertFalse(close(opt, reading=signal(100, plan=p6.Plan(active=True))))
        self.assertFalse(close(opt, bar=T2, sequence=2,
                               reading=signal(100, plan=p6.Plan(active=True))))
        self.assertEqual(opt.gate_bar(RANGING), 70)
        self.assertEqual(opt.file.cells["RANGING"].moves, 0)
        opt.deinit(T2)
        self.assertEqual(disk.files, before)
        self.assertFalse(any("Param bar moved" in line for line in opt.file.journal))

    def test_symbol_or_timeframe_identity_mismatch_is_never_imported(self):
        for header in ("Emtt_Params v1 | GBPUSD | M15", "Emtt_Params v1 | EURUSD | M30"):
            disk = p9.Disk()
            path = p9.path_for("EURUSD", "M15")
            disk.files[path] = header + "\r\n"
            opt = optimizer(disk=disk)
            self.assertTrue(opt.file.read_only)
            self.assertEqual(disk.files[path], header + "\r\n")

    def test_missing_file_starts_fresh_and_journals_full_location(self):
        opt = optimizer()
        self.assertEqual(opt.file.cells["TRENDING"].bar, 60)
        self.assertEqual(opt.file.cells["TRANSITION"].bar, 75)
        self.assertEqual(opt.file.journal[0],
                         "Emtt | Param optimization started | no file yet | MQL5\\Files\\Emtt_Learning\\EURUSD_M15.params")

    def test_missing_cell_does_not_drop_the_other_cells(self):
        disk = p9.Disk()
        state = p9.ParameterFile(loaded=True)
        for cell in state.cells.values():
            cell.a_w = 5
        lines = state.render(T0).splitlines()
        del lines[3]
        disk.files[state.path] = "\r\n".join(lines) + "\r\n"
        loaded = p9.ParameterFile.load(disk, "EURUSD", "M15", T1)
        self.assertEqual(loaded.cells["RANGING"].a_w, 0)
        self.assertEqual(loaded.cells["VOLATILE"].a_w, 5)
        self.assertEqual(loaded.cells["TRANSITION"].a_w, 5)

    def test_duplicate_cell_is_only_that_cells_damage(self):
        disk = p9.Disk()
        state = p9.ParameterFile(loaded=True)
        text = state.render(T0) + state.cells["RANGING"].line("RANGING") + "\r\n"
        disk.files[state.path] = text
        loaded = p9.ParameterFile.load(disk, "EURUSD", "M15", T1)
        self.assertEqual(loaded.damaged_warned, {"RANGING"})

    def test_cell_parser_rejects_bad_base_bar_counters_keys_and_overflow(self):
        valid = evidence().line("RANGING")
        for bad in (valid.replace("bar 70", "bar 62"), valid.replace("base 70", "base 60"),
                    valid.replace("14/6", "-14/6"), valid.replace("14/6", "14junk/6"),
                    valid.replace("14/6", "+/6"), valid.replace("14/6", "14/6/0"),
                    valid.replace("moves 0", "moves 9223372036854775808"),
                    valid.replace("accepted", "accept"), valid + " | ignored 1"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p9.parse_cell(bad, "RANGING")

    def test_atomic_rename_consumes_a_crashed_tmp_without_touching_siblings(self):
        disk = p9.Disk()
        path = p9.path_for("EURUSD", "M15")
        disk.files[path + ".tmp"] = "partial crashed write"
        disk.files[path.replace(".params", ".learn")] = "learning tickets"
        disk.files[path.replace(".params", ".summary")] = "summary totals"
        opt = optimizer(disk=disk)
        self.assertNotIn(path + ".tmp", disk.files)
        self.assertEqual(len(disk.files[path].splitlines()), 6)
        self.assertEqual(disk.files[path.replace(".params", ".learn")], "learning tickets")
        self.assertEqual(disk.files[path.replace(".params", ".summary")], "summary totals")
        self.assertIn(("rename", path), disk.operations)

    def test_write_events_are_init_decision_and_deinit_not_periodic(self):
        opt = optimizer()
        opt.queue_accepted(ticket(), "M15", T1)
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.write_events, ["init_after_load"])
        close(opt, reading=signal(100, plan=p6.Plan(active=True)), bar=T2, sequence=2)
        self.assertEqual(opt.file.write_events, ["init_after_load"])
        opt.deinit(T2)
        self.assertEqual(opt.file.write_events, ["init_after_load", "deinit"])
        with self.assertRaises(ValueError):
            opt.file.save(opt.disk, T3, "timer")

    def test_neutral_evidence_keeps_accumulating_without_a_write(self):
        opt = optimizer()
        opt.file.cells["RANGING"] = evidence(n=(12, 8))
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.write_events, ["init_after_load"])
        self.assertEqual(opt.file.cells["RANGING"].accepted, 20)

    def test_a_held_move_is_also_a_write_event(self):
        opt = optimizer()
        opt.file.cells["TRENDING"] = evidence(bar=60, base=60)
        close(opt, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(opt.file.write_events, ["init_after_load", "decision"])
        saved = p9.ParameterFile.load(opt.disk, "EURUSD", "M15", T1)
        self.assertEqual(saved.cells["TRENDING"].moves, 1)
        self.assertEqual(saved.cells["TRENDING"].accepted, 0)

    def test_all_write_failures_leave_destination_whole_and_learning_in_memory(self):
        for failure in ("fail_write", "fail_short_write", "fail_flush", "fail_close", "fail_move"):
            with self.subTest(failure=failure):
                opt = optimizer()
                saved = opt.disk.files[opt.file.path]
                opt.file.cells["RANGING"] = evidence()
                setattr(opt.disk, failure, True)
                close(opt, reading=signal(100, plan=p6.Plan(active=True)))
                self.assertEqual(opt.disk.files[opt.file.path], saved)
                self.assertEqual(opt.file.cells["RANGING"].bar, 60)
                self.assertTrue(opt.file.write_failed)
                self.assertEqual(sum("Param file busy" in l for l in opt.file.journal), 1)
                opt.deinit(T1)
                self.assertEqual(sum("Param file busy" in l for l in opt.file.journal), 1)
                setattr(opt.disk, failure, False)
                opt.deinit(T2)
                self.assertIn("bar 60 | base 70", opt.disk.files[opt.file.path])
                self.assertFalse(opt.file.write_failed)
                self.assertEqual(sum("write recovered" in l for l in opt.file.journal), 1)

    def test_busy_read_never_overwrites_unread_file_and_retries_on_write_event(self):
        disk = p9.Disk()
        saved = p9.ParameterFile(loaded=True)
        saved.cells["RANGING"].a_w = 5
        disk.files[saved.path] = saved.render(T0)
        before = disk.files.copy()
        disk.fail_read = True
        opt = optimizer(disk=disk)
        opt.file.cells["RANGING"].a_w = 3
        self.assertEqual(disk.files, before)
        self.assertTrue(opt.file.read_pending)
        disk.fail_read = False
        opt.deinit(T1)
        self.assertEqual(opt.file.cells["RANGING"].a_w, 8)
        self.assertIn("accepted 8/0", disk.files[saved.path])

    def test_busy_read_recovery_after_original_removal_merges_memory_once(self):
        disk = p9.Disk()
        saved = p9.ParameterFile(loaded=True)
        saved.cells["RANGING"] = evidence(moves=4)
        disk.files[saved.path] = saved.render(T0)
        before = disk.files.copy()
        disk.fail_read = True
        opt = optimizer(disk=disk)
        opt.file.cells["RANGING"].a_w = 3
        opt.file.cells["RANGING"].n_l = 2
        opt.deinit(T1)  # another failed read keeps the delta in memory
        self.assertEqual(disk.files, before)
        self.assertEqual(opt.file.cells["RANGING"].a_w, 3)
        disk.files.pop(saved.path)  # external removal, not an EA deletion
        disk.fail_read = False
        opt.deinit(T2)
        cell = opt.file.cells["RANGING"]
        self.assertEqual((cell.a_w, cell.a_l, cell.n_w, cell.n_l, cell.moves),
                         (3, 0, 0, 2, 0))
        self.assertFalse(opt.file.read_pending)
        self.assertFalse(opt.file.write_failed)
        opt.deinit(T3)  # a subsequent save must not merge that delta again
        loaded = p9.ParameterFile.load(disk, "EURUSD", "M15", T3)
        self.assertEqual(loaded.cells["RANGING"], cell)
        self.assertEqual(sum("Param file busy" in line for line in opt.file.journal), 1)
        self.assertEqual(sum("write recovered" in line for line in opt.file.journal), 1)

    def test_restart_continues_evidence_without_relearning_old_tickets(self):
        opt = optimizer()
        opt.file.cells["RANGING"] = evidence(a=(13, 6), n=(13, 7))
        opt.deinit(T0)
        restarted = optimizer(disk=opt.disk)
        self.assertEqual(restarted.file.cells["RANGING"].accepted, 19)
        close(restarted, replay=True)
        self.assertEqual(restarted.file.cells["RANGING"].accepted, 19)
        restarted.queue_accepted(ticket(start=T1), "M15", T2)
        close(restarted, bar=T2, sequence=2, reading=signal(100, plan=p6.Plan(active=True)))
        self.assertEqual(restarted.file.cells["RANGING"].bar, 60)
        self.assertEqual(restarted.file.cells["RANGING"].moves, 1)

    def test_same_file_plus_same_ordered_candles_is_deterministic(self):
        initial = p9.ParameterFile(loaded=True)
        initial.cells["RANGING"] = evidence(a=(13, 6), n=(13, 7))
        results = []
        for _ in range(2):
            disk = p9.Disk()
            disk.files[initial.path] = initial.render(T0)
            opt = optimizer(disk=disk)
            opt.queue_accepted(ticket(start=T0), "M15", T1)
            close(opt, reading=signal(100, plan=p6.Plan(active=True)))
            close(opt, bar=T2, sequence=2, reading=signal(55))
            opt.deinit(T3)
            results.append((opt.file.cells, opt.effective, opt.file.journal, opt.journal, disk.files))
        self.assertEqual(results[0], results[1])

    def test_replay_does_not_change_loaded_bars(self):
        opt = optimizer()
        opt.file.cells["RANGING"].bar = 60
        opt.deinit(T0)
        restarted = optimizer(disk=opt.disk)
        close(restarted, replay=True)
        self.assertEqual(restarted.gate_bar(RANGING), 60)
        self.assertIsNone(restarted.near)


class TicketParameterPartTests(unittest.TestCase):
    PARAMS = p9.Parameters(21, 21, (13, 26, 50), 75, 300, 70, 2.0)

    def test_optional_part_matches_exact_approved_grammar(self):
        line = p9.ticket_line(p9.ParameterTicket(ticket(""), self.PARAMS), True)
        self.assertTrue(line.endswith(" | par atr 21 er 21 kama 13,26,50 stwin 75 vfwin 300 bar 70 rrmin 2.0"))
        self.assertEqual(p9.parse_ticket(line).parameters, self.PARAMS)

    def test_off_is_byte_identical_to_phase_eight_even_for_old_metadata(self):
        trade = ticket(filled=True, closed=True, net=-7)
        line = p9.ticket_line(p9.ParameterTicket(trade, self.PARAMS), False)
        self.assertEqual(line, p8.trade_ticket_line(trade))
        self.assertNotIn(" | par ", line)

    def test_phase_eight_reader_ignores_the_part_and_keeps_real_label(self):
        trade = ticket("stop", filled=True, closed=True, net=10)
        extended = p9.ticket_line(p9.ParameterTicket(trade, self.PARAMS), True)
        parsed = p9.phase8_read_ticket(extended)
        self.assertEqual(parsed.plan, p8.parse_trade_ticket_line(p8.trade_ticket_line(trade)).plan)
        self.assertEqual(p9.accepted_label(parsed), 1)

    def test_existing_phase_eight_lines_still_roundtrip_without_any_change(self):
        trade = ticket("stop", filled=True, closed=True, net=-8)
        line = p8.trade_ticket_line(trade)
        parsed = p9.parse_ticket(line)
        self.assertIsNone(parsed.parameters)
        self.assertEqual(p9.ticket_line(parsed, True), line)

    def test_metadata_survives_fill_and_close_whole_file_rewrites(self):
        item = p9.ParameterTicket(ticket(""), self.PARAMS)
        start_line = p9.ticket_line(item, True)
        item = p9.parse_ticket(start_line)
        item.trade.trade_filled = T1
        item = p9.parse_ticket(p9.ticket_line(item, True))
        item.trade.trade_closed = T2
        item.trade.trade_net_points = 11
        parsed = p9.parse_ticket(p9.ticket_line(item, True))
        self.assertEqual(parsed.parameters, self.PARAMS)
        self.assertEqual(p9.accepted_label(parsed.trade), 1)

    def test_model_features_weights_and_counts_never_read_metadata(self):
        original = ticket().plan
        for params in (self.PARAMS, replace(self.PARAMS, atr=28, er=28, bar=60,
                                           kama=(21, 34, 50), rr_min=1.5)):
            item = p9.ParameterTicket(p8.TradeTicket(original), params)
            parsed = p9.parse_ticket(p9.ticket_line(item, True))
            self.assertEqual(p7.features_from_ticket(parsed.trade.plan), p7.features_from_ticket(original))
            self.assertEqual(p7.build_model([parsed.trade.plan]), p7.build_model([original]))
            self.assertEqual(p8.learning_counts([parsed.trade]), (1, 1, 0))

    def test_optimizer_uses_only_ticket_mood_and_label_not_par_values(self):
        results = []
        for params in (self.PARAMS, replace(self.PARAMS, bar=60, atr=28, rr_min=1.5)):
            opt = optimizer()
            parsed = p9.parse_ticket(p9.ticket_line(p9.ParameterTicket(ticket(), params), True))
            opt.queue_accepted(parsed.trade, "M15", T1)
            close(opt, reading=signal(100, plan=p6.Plan(active=True)))
            results.append(opt.file.cells)
        self.assertEqual(results[0], results[1])

    def test_damaged_optional_part_does_not_destroy_training_evidence(self):
        line = p8.trade_ticket_line(ticket()) + " | par damaged author-only evidence"
        parsed = p9.parse_ticket(line)
        self.assertIsNone(parsed.parameters)
        self.assertEqual(p9.accepted_label(parsed.trade), 1)
        self.assertEqual(len(p7.features_from_ticket(parsed.trade.plan)), 16)

    def test_empty_signed_fractional_or_overflowing_metadata_is_ignored(self):
        baseline = p8.trade_ticket_line(ticket())
        valid = self.PARAMS.part()
        for part in ("par", valid.replace("atr 21", "atr +21"),
                     valid.replace("atr 21", "atr 21.0"),
                     valid.replace("atr 21", "atr 4294967317"),
                     valid.replace("bar 70", "bar 62")):
            with self.subTest(part=part):
                parsed = p9.parse_ticket(baseline + " | " + part)
                self.assertIsNone(parsed.parameters)
                self.assertEqual(p9.accepted_label(parsed.trade), 1)

    def test_part_can_be_read_past_before_or_after_trade_extension(self):
        item = p9.ParameterTicket(ticket(filled=True, closed=True, net=-3), self.PARAMS)
        line = p9.ticket_line(item, True)
        without = p9.strip_parameter_parts(line)
        alternate = without.replace(" | trade filled", " | " + self.PARAMS.part() + " | trade filled", 1)
        self.assertEqual(p9.parse_ticket(line).parameters, p9.parse_ticket(alternate).parameters)
        self.assertEqual(p9.accepted_label(p9.parse_ticket(alternate).trade), 0)


class MqlContractTests(unittest.TestCase):
    def test_actual_include_graph_and_all_phase_two_through_nine_guards_pass(self):
        paths = smoke.resolve_include_graph(smoke.ENTRY)
        # Phase 10+ add headers; the Phase 2-9 set is still required.
        self.assertGreaterEqual(len(paths), 17)
        smoke.check_contract(paths)
        for path in paths:
            smoke.check_delimiters(path)
            smoke.check_guards(path)

    def test_contract_negative_controls_reject_phase_nine_scope_violations(self):
        root = Path(__file__).resolve().parents[1]
        mutations = (
            ("Include/Emtt/Emtt_ParamOpt.mqh", "\nvoid Bad(){ OrderSend(); }\n"),
            ("Include/Emtt/Emtt_ParamOpt.mqh", "\nvoid Bad(){ ObjectCreate(); }\n"),
            ("Include/Emtt/Emtt_ParamOpt.mqh", "\n// non-ASCII: \u2014\n"),
            ("Include/Emtt/Emtt_ParamOpt.mqh", "\nvoid Bad(){ FileOpen(); }\n"),
            ("Include/Emtt/Emtt_ParamOpt.mqh", "\nvoid Bad(){ MathRand(); }\n"),
            ("Include/Emtt/Emtt_ParamOpt.mqh", "\nvoid Bad(){ GetMicrosecondCount(); }\n"),
            ("Include/Emtt/Emtt_ParamFile.mqh", "\nvoid Bad(){ FileOpen(); }\n"),
            ("Include/Emtt/Emtt_ParamFile.mqh", "\nvoid Bad(){ FolderClean(); }\n"),
            ("Include/Emtt/Emtt_ParamFile.mqh", "\nvoid Bad(){ FileDelete(); }\n"),
            ("Include/Emtt/Emtt_ParamFile.mqh", "\nvoid Bad(){ FileMove(); }\n"),
            ("Include/Emtt/Emtt_ParamFile.mqh", "\nvoid Bad(){ GlobalVariableSet(); }\n"),
            ("Include/Emtt/Emtt_ParamFile.mqh", '\nvoid Bad(){ FileOpen("extra.csv",FILE_WRITE); }\n'),
            ("Include/Emtt/Emtt_DynamicParams.mqh", "\n// out-of-scope change\n"),
            ("Include/Emtt/Emtt_Signal.mqh", "\n// third signal edit\n"),
            ("Include/Emtt/Emtt_Learning.mqh", "\n// model edit\n"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            shutil.copytree(root / "Include", work / "Include")
            shutil.copytree(root / "Experts", work / "Experts")
            with mock.patch.object(smoke, "ROOT", work), mock.patch.object(smoke, "ENTRY", work / "Experts/Emtt.mq5"):
                for name, extra in mutations:
                    with self.subTest(name=name, extra=extra):
                        path = work / name
                        saved = path.read_text()
                        path.write_text(saved + extra)
                        try:
                            with self.assertRaises(RuntimeError):
                                smoke.check_contract(smoke.resolve_include_graph(smoke.ENTRY))
                        finally:
                            path.write_text(saved)

    def test_contract_rejects_wrong_input_default_suffix_and_candidate_set(self):
        root = Path(__file__).resolve().parents[1]
        mutations = (
            ("Experts/Emtt.mq5", "InpParamOptimization=true", "InpParamOptimization=false"),
            ("Include/Emtt/Emtt_ParamFile.mqh", 'EMTT_POPT_SUFFIX ".params"', 'EMTT_POPT_SUFFIX ".csv"'),
            ("Include/Emtt/Emtt_ParamOpt.mqh", "candidates[3]={60,70,75}", "candidates[3]={60,65,75}"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            shutil.copytree(root / "Include", work / "Include")
            shutil.copytree(root / "Experts", work / "Experts")
            with mock.patch.object(smoke, "ROOT", work), mock.patch.object(smoke, "ENTRY", work / "Experts/Emtt.mq5"):
                for name, old, new in mutations:
                    path = work / name
                    saved = path.read_text()
                    self.assertIn(old, saved)
                    path.write_text(saved.replace(old, new))
                    try:
                        with self.assertRaises(RuntimeError):
                            smoke.check_contract(smoke.resolve_include_graph(smoke.ENTRY))
                    finally:
                        path.write_text(saved)

    def test_near_is_only_wired_into_incremental_closed_candle_path(self):
        ea = smoke.ENTRY.read_text()
        replay = ea.split("bool EmttReplayClosedHistory()", 1)[1].split("bool EmttCopyOne", 1)[0]
        live = ea.split("bool EmttProcessLatestClosedBar", 1)[1].split("void EmttResetMarketState", 1)[0]
        tick = ea.split("void OnTick()", 1)[1].split("void OnTimer()", 1)[0]
        self.assertNotIn("EmttParamOptimizationAdvance(", replay)
        self.assertIn("g_paramOpt.replaying=true", replay)
        self.assertIn("g_paramOpt.replaying=false", replay)
        self.assertIn("EmttParamOptBeginCandle(", live)
        self.assertIn("EmttParamOptimizationAdvance(", live)
        self.assertNotIn("Param", tick)
        self.assertNotIn("Learn", tick)


if __name__ == "__main__":
    unittest.main()
