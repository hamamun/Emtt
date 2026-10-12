"""Portable tests for Emtt Phase 10 (Emtt.md 25.3-25.13).

Everything asserted here runs against ``phase10_reference`` with no MT5
dependency: the tick sign, the fixed ring and its running sums, the 15-minute
expiry, the incremental tick swings, the weak / strong divergence reading and
its confirmation, side filtering, resets and hysteresis, the density gate and
warmup, the breakeven gate, adoption / close resets, the single 25.9 edit to
the trailing distance and determinism. A final group ties the reference to
the MQL header and the smoke contract.
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import phase8_reference as p8
import phase10_reference as p10
from phase2_reference import BULL, RANGING, TRANSITION
from tools import mql5_compile_smoke as smoke

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "Include" / "Emtt" / "Emtt_TickDivergence.mqh"

POINT = 0.00001
BASE = 1.08000
SPREAD = 2 * POINT
T0 = 1_791_795_600_000          # 2026-10-12 09:00:00 UTC in milliseconds
STEP_MS = 200                   # five ticks per second: a liquid feed
ATR = 0.00100                   # 0.10 x ATR = 10 points


def ticks(offsets, start_ms=T0, step_ms=STEP_MS, spread=SPREAD):
    """(bid, ask, msc) triples whose mid follows `offsets` (in points)."""
    out = []
    for i, offset in enumerate(offsets):
        mid = round(BASE + offset * POINT, 6)
        out.append((round(mid - spread / 2, 6), round(mid + spread / 2, 6),
                    start_ms + i * step_ms))
    return out


def ramp(start, stop, step=1):
    """Inclusive-of-stop integer walk, excluding `start`."""
    direction = 1 if stop > start else -1
    return list(range(start + direction * step, stop + direction, direction * step))


def warmup(n=60):
    """A quiet warmup: alternating 0 / 1 points - no strength-5 swing."""
    return [i % 2 for i in range(n)]


def bearish_divergence(strong=True):
    """BUY-side fade: leg 1 to +30 on 30 upticks, pull back, then a higher
    peak printed on a few large upticks so tick-CVD at the new high is lower
    (fake breakout). Ends with enough lower ticks to confirm and settle."""
    path = warmup()
    path += ramp(path[-1], 30)                 # peak0 = +30, cvd +29/+30
    if strong:
        path += ramp(30, 10)                   # pullback 20 downticks
        path += [40, 70]                       # 2 big upticks -> peak1 = +70
    else:
        path += ramp(30, 20)                   # pullback 10 downticks
        path += [40, 50]                       # peak1 = +50
    peak_index = len(path) - 1
    path += ramp(path[-1], path[-1] - 10)      # 10 lower ticks after the peak
    return path, peak_index


def negate(path):
    return [-x for x in path]


class TickSignTests(unittest.TestCase):
    def test_uptick_downtick_zero_and_spread_change(self):
        s = p10.tick_sign
        self.assertEqual(s(1.0, 1.1, 1.01, 1.11), 1)     # both up
        self.assertEqual(s(1.0, 1.1, 0.99, 1.09), -1)    # both down
        self.assertEqual(s(1.0, 1.1, 1.0, 1.1), 0)       # unchanged
        self.assertEqual(s(1.0, 1.1, 0.99, 1.11), 0)     # spread widens
        self.assertEqual(s(1.0, 1.1, 1.01, 1.09), 0)     # spread narrows

    def test_mixed_moves_on_one_side_of_the_quote(self):
        s = p10.tick_sign
        self.assertEqual(s(1.0, 1.1, 1.0, 1.11), 1)      # ask up, bid flat
        self.assertEqual(s(1.0, 1.1, 1.01, 1.1), 1)      # bid up, ask flat
        self.assertEqual(s(1.0, 1.1, 0.99, 1.1), -1)     # bid down, ask flat
        self.assertEqual(s(1.0, 1.1, 1.0, 1.09), -1)     # ask down, bid flat

    def test_first_tick_of_a_session_has_no_direction(self):
        div = p10.run(ticks([0]))
        self.assertEqual(div.sign[0], 0)
        self.assertEqual(div.cvd_now, 0)


class RingBufferTests(unittest.TestCase):
    def brute(self, div):
        window = div.window()
        return sum(t[2] for t in window), sum(1 for t in window if t[2])

    def test_running_sums_match_a_full_rescan_on_every_tick(self):
        import random
        rng = random.Random(10)
        offsets, x = [], 0
        for _ in range(700):
            x += rng.choice((-2, -1, 0, 1, 2))
            offsets.append(x)
        div = p10.TickDivergence()
        div.arm(1, p10.BUY)
        for bid, ask, msc in ticks(offsets):
            div.feed(bid, ask, msc, ATR, True)
            self.assertLessEqual(div.count, p10.TICKS)
            self.assertEqual((div.cvd_now, div.cvd_abs), self.brute(div))
        self.assertEqual(div.count, p10.TICKS)
        self.assertEqual(div.total, 700)

    def test_ring_is_fixed_and_never_grows(self):
        div = p10.run(ticks(list(range(1000))))
        for name in ("msc", "mid", "sign", "cvd", "run_start"):
            self.assertEqual(len(getattr(div, name)), p10.TICKS)
        self.assertEqual(div.count, 300)
        self.assertEqual(div.cvd_now, 300)       # every in-window tick is +1

    def test_fifteen_minute_cap_drops_old_ticks_before_the_buffer_fills(self):
        offsets = [i % 3 for i in range(150)]
        div = p10.run(ticks(offsets, step_ms=10_000))    # one tick per 10 s
        window = div.window()
        self.assertLess(div.count, 300)
        self.assertLessEqual(window[-1][0] - window[0][0], 15 * 60 * 1000)
        self.assertEqual(div.count, 91)                  # 0..900 s inclusive
        self.assertEqual((div.cvd_now, div.cvd_abs), self.brute(div))

    def test_duplicate_and_out_of_order_ticks_are_ignored(self):
        div = p10.TickDivergence()
        div.arm(1, p10.BUY)
        self.assertTrue(div.feed(1.1, 1.1002, T0, ATR, True))
        self.assertFalse(div.feed(1.1, 1.1002, T0, ATR, True))
        self.assertFalse(div.feed(1.2, 1.2002, T0 - 1, ATR, True))
        self.assertTrue(div.feed(1.1001, 1.1003, T0, ATR, True))   # same ms, new quote
        self.assertEqual(div.total, 2)

    def test_empty_state_when_no_position(self):
        div = p10.TickDivergence()
        pos = p10.Position(11, p10.BUY, ATR, True)
        for bid, ask, msc in ticks(list(range(80))):
            p10.manager_feed(div, pos, bid, ask, msc)
        self.assertTrue(div.armed)
        p10.manager_feed(div, None, 1.1, 1.1002, T0 + 999_999)
        self.assertFalse(div.armed)
        self.assertEqual((div.total, div.count, div.cvd_now, div.cvd_abs), (0, 0, 0, 0))
        self.assertEqual(div.multiplier(), 1.0)
        # While flat nothing is fed or journaled.
        before = list(div.journal)
        p10.manager_feed(div, None, 1.1, 1.1002, T0 + 2_000_000)
        self.assertEqual(div.total, 0)
        self.assertEqual(div.journal, before)


class SwingTests(unittest.TestCase):
    def peaks_seen(self, offsets, side=p10.BUY):
        div = p10.TickDivergence()
        div.arm(1, side)
        seen = []
        for i, (bid, ask, msc) in enumerate(ticks(offsets)):
            before = (div.has1, div.seq1)
            div.feed(bid, ask, msc, ATR, True)
            if (div.has1, div.seq1) != before and div.has1:
                seen.append((i, div.seq1, round((div.price_peak1 - BASE) / POINT)))
        return seen, div

    def test_swing_high_confirmed_five_ticks_after_it_forms(self):
        offsets = [0, 1, 2, 3, 4, 5, 10, 5, 4, 3, 2, 1, 0]
        seen, _ = self.peaks_seen(offsets)
        self.assertEqual(seen, [(11, 6, 10)])           # formed at 6, seen at 11

    def test_plateau_resolves_to_one_pivot_at_its_oldest_member(self):
        offsets = [0, 1, 2, 3, 4, 5, 8, 8, 8, 5, 4, 3, 2, 1, 0]
        seen, _ = self.peaks_seen(offsets)
        self.assertEqual(seen, [(13, 6, 8)])

    def test_strength_five_needs_five_strictly_lower_ticks_each_side(self):
        # Only four rising ticks before the high: not a strength-5 swing.
        seen, _ = self.peaks_seen([0, 1, 2, 3, 9, 5, 4, 3, 2, 1, 0])
        self.assertEqual(seen, [])
        # An equal neighbour breaks "strictly".
        seen, _ = self.peaks_seen([0, 1, 2, 3, 4, 9, 9.0, 5, 4, 3, 2, 9, 0])
        self.assertEqual(seen, [])

    def test_single_tick_wiggles_inside_a_trend_are_filtered(self):
        offsets = list(range(0, 40))
        offsets[20] = 18                                # one-tick dip in a rise
        offsets[30] = 31                                # one-tick pop in a rise
        seen, d = self.peaks_seen(offsets)
        self.assertEqual(seen, [])
        self.assertFalse(d.pullback)

    def test_sell_trade_tracks_swing_lows(self):
        offsets = negate([0, 1, 2, 3, 4, 5, 10, 5, 4, 3, 2, 1, 0])
        seen, _ = self.peaks_seen(offsets, side=p10.SELL)
        self.assertEqual(seen, [(11, 6, -10)])
        seen, _ = self.peaks_seen(offsets, side=p10.BUY)
        self.assertEqual(seen, [])


class DivergenceTests(unittest.TestCase):
    def feed_path(self, offsets, side=p10.BUY, breakeven=True, atr=ATR):
        div = p10.TickDivergence()
        div.arm(5, side)
        levels = []
        for bid, ask, msc in ticks(offsets):
            div.feed(bid, ask, msc, atr, breakeven)
            levels.append(div.level)
        return div, levels

    def test_strong_fake_breakout_within_a_few_ticks_of_the_confirmed_peak(self):
        path, peak = bearish_divergence(strong=True)
        div, levels = self.feed_path(path)
        self.assertEqual(div.level, p10.STRONG)
        self.assertEqual(div.multiplier(), 0.5)
        first_strong = levels.index(p10.STRONG)
        # Peak confirmed 5 ticks later, then held for 3 consecutive ticks.
        self.assertEqual(first_strong - peak, p10.SWING_STRENGTH + p10.CONFIRM_TICKS - 1)
        self.assertNotIn(p10.WEAK, levels)              # none -> strong directly
        self.assertGreater(div.price_peak1, div.price_peak0)
        self.assertLessEqual(div.cvd_at_peak1, div.cvd_at_peak0 * 0.5)
        line = [x for x in div.journal if "Divergence strong" in x][0]
        self.assertRegex(line, r"^Emtt \| Divergence strong \| BUY \| new high 1\.08070, "
                               r"CVD exhausted \(cvd \d+ vs \d+\) \| trail 0\.5x \| tick "
                               r"\d{4}\.\d\d\.\d\d \d\d:\d\d:\d\d$")

    def test_weak_divergence_confirmed_after_three_ticks(self):
        path, peak = bearish_divergence(strong=False)
        div, levels = self.feed_path(path)
        self.assertEqual(div.level, p10.WEAK)
        self.assertEqual(div.multiplier(), 0.8)
        confirm = peak + p10.SWING_STRENGTH
        self.assertEqual(levels[confirm], p10.NONE)
        self.assertEqual(levels[confirm + 1], p10.NONE)
        self.assertEqual(levels[confirm + 2], p10.WEAK)
        self.assertTrue(any("Divergence weak | BUY | new high 1.08050, CVD fading" in x
                            and "| trail 0.8x |" in x for x in div.journal))

    def test_leg_must_clear_a_tenth_of_entry_atr(self):
        path, _ = bearish_divergence(strong=True)
        # Peak1 is 40 points above peak0: 0.10 x ATR must not exceed 40 points.
        div, _ = self.feed_path(path, atr=0.0041)
        self.assertEqual(div.level, p10.NONE)
        div, _ = self.feed_path(path, atr=0.0039)
        self.assertEqual(div.level, p10.STRONG)

    def test_rising_cvd_with_price_is_confirmation_not_a_warning(self):
        path = warmup() + ramp(1, 30) + ramp(30, 25) + ramp(25, 60) + ramp(60, 50)
        div, levels = self.feed_path(path)
        self.assertTrue(div.has0 and div.has1)
        self.assertGreater(div.cvd_at_peak1, div.cvd_at_peak0)
        self.assertEqual(set(levels), {p10.NONE})

    def test_side_filtering(self):
        path, _ = bearish_divergence(strong=True)
        div, _ = self.feed_path(path, side=p10.SELL)     # bearish fade on a SELL
        self.assertEqual(div.level, p10.NONE)
        div, _ = self.feed_path(negate(path), side=p10.BUY)   # bullish fade on a BUY
        self.assertEqual(div.level, p10.NONE)
        div, _ = self.feed_path(negate(path), side=p10.SELL)  # mirrored: fires
        self.assertEqual(div.level, p10.STRONG)
        self.assertTrue(any("Divergence strong | SELL | new low 1.07930" in x
                            for x in div.journal))

    def test_never_before_breakeven(self):
        path, _ = bearish_divergence(strong=True)
        div, levels = self.feed_path(path, breakeven=False)
        self.assertEqual(set(levels), {p10.NONE})
        self.assertEqual(div.multiplier(), 1.0)
        self.assertFalse(any("Divergence" in x and "reset" not in x for x in div.journal))

    def test_never_during_warmup(self):
        path, peak = bearish_divergence(strong=True)
        short = path[len(warmup()) - 15:]                # pattern inside 50 ticks
        div, levels = self.feed_path(short[:49])
        self.assertFalse(div.warm)
        self.assertEqual(set(levels), {p10.NONE})
        self.assertEqual(div.multiplier(), 1.0)

    def test_needs_two_confirmed_trade_direction_swings(self):
        path = warmup() + ramp(1, 30) + ramp(30, 20)
        div, levels = self.feed_path(path)
        self.assertTrue(div.has1)
        self.assertFalse(div.has0)
        self.assertEqual(div.candidate(), p10.NONE)

    def test_hysteresis_strong_never_returns_to_weak(self):
        path, _ = bearish_divergence(strong=True)
        div, _ = self.feed_path(path)
        self.assertEqual(div.level, p10.STRONG)
        div.cvd_at_peak1 = int(div.cvd_at_peak0 * 0.8)   # reading now only weak
        self.assertEqual(div.candidate(), p10.WEAK)
        div.cvd_at_peak1 = div.cvd_at_peak0 + 5          # and now none at all
        last = div.last_msc
        for i in range(10):
            div.feed(1.0805 + i * POINT, 1.0805 + i * POINT + SPREAD, last + (i + 1) * 200,
                     ATR, True)
            self.assertEqual(div.level, p10.STRONG)
            self.assertEqual(div.multiplier(), 0.5)

    def test_weak_can_rise_to_strong_on_the_same_leg(self):
        path, _ = bearish_divergence(strong=False)
        div, _ = self.feed_path(path)
        self.assertEqual(div.level, p10.WEAK)
        div.cvd_at_peak1 = int(div.cvd_at_peak0 * 0.5)
        for i in range(3):
            div.feed(1.0803 - i * POINT, 1.0803 - i * POINT + SPREAD,
                     div.last_msc + 200, ATR, True)
        self.assertEqual(div.level, p10.STRONG)

    def test_pullback_swing_then_resume_resets_to_fresh_legs(self):
        path, _ = bearish_divergence(strong=True)
        low = path[-1]
        path += ramp(low, low - 10)                      # deeper pullback
        path += ramp(low - 10, 90)                       # resumes to a new high
        path += ramp(90, 84)                             # confirms it
        div, levels = self.feed_path(path)
        self.assertIn(p10.STRONG, levels)
        self.assertEqual(div.level, p10.NONE)
        self.assertEqual(div.multiplier(), 1.0)
        self.assertTrue(div.has1)
        self.assertFalse(div.has0)                       # comparison restarts
        self.assertTrue(any(x.startswith("Emtt | Divergence reset | BUY | fresh leg after pullback | tick ")
                            for x in div.journal))

    def test_unlatched_pullbacks_keep_the_classic_two_peak_comparison(self):
        path, _ = bearish_divergence(strong=True)
        div, _ = self.feed_path(path)
        # The pullback between peak0 and peak1 confirmed a swing low, yet the
        # unlatched comparison kept peak0 (otherwise no divergence could form).
        self.assertTrue(div.has0)

    def test_stop_move_resets(self):
        path, _ = bearish_divergence(strong=True)
        div, _ = self.feed_path(path)
        div.on_stop_moved(True)
        self.assertEqual(div.level, p10.NONE)
        self.assertFalse(div.has0 or div.has1)
        self.assertTrue(div.journal[-1].startswith("Emtt | Divergence reset | BUY | stop moved | tick "))
        count = len(div.journal)
        div.on_stop_moved(True)                          # nothing latched: silent
        self.assertEqual(len(div.journal), count)

    def test_leg_leaving_the_window_resets(self):
        path, _ = bearish_divergence(strong=True)
        div, _ = self.feed_path(path)
        last = div.last_msc
        div.feed(div.prev_bid, div.prev_ask + POINT, last + 16 * 60 * 1000, ATR, True)
        self.assertEqual(div.level, p10.NONE)
        self.assertFalse(div.has1)
        self.assertTrue(any("| leg left the window | tick " in x for x in div.journal[-2:]))


class DensityAndWarmupTests(unittest.TestCase):
    def test_sparse_feed_is_inactive_and_recovers_at_twenty(self):
        div = p10.TickDivergence()
        div.arm(3, p10.BUY)
        offsets = [i % 2 for i in range(400)]
        msc = T0
        stream = []
        for i in range(60):                              # one tick / 7 s: 9 per minute
            stream.append(msc)
            msc += 7000
        for i in range(60):                              # one tick / 2 s: 30 per minute
            stream.append(msc)
            msc += 2000
        recovered_at = None
        for i, t in enumerate(stream):
            mid = BASE + offsets[i] * POINT
            div.feed(mid - POINT, mid + POINT, t, ATR, True)
            if i == 55:
                self.assertTrue(div.sparse)
                self.assertFalse(div.active())
                self.assertEqual(div.multiplier(), 1.0)
            if recovered_at is None and i >= 60 and not div.sparse:
                recovered_at = i
                self.assertGreaterEqual(div.density, p10.DENSITY_RECOVER)
        self.assertIsNotNone(recovered_at)
        self.assertEqual(div.journal[0][:60],
                         "Emtt | Tick divergence inactive | sparse feed (9 ticks/min) "[:60])
        self.assertTrue(div.journal[1].startswith("Emtt | Tick divergence recovered | 20 ticks/min | bar "))

    def test_no_flicker_between_ten_and_nineteen(self):
        div = p10.TickDivergence()
        div.arm(3, p10.BUY)
        msc = T0
        for i in range(80):                              # dense: 5 per second
            div.feed(1.1 + (i % 2) * POINT, 1.1002 + (i % 2) * POINT, msc, ATR, True)
            msc += 200
        self.assertFalse(div.sparse)
        flips = 0
        state = div.sparse
        for i in range(200):                             # one tick / 4 s: 15 per minute
            msc += 4000
            div.feed(1.1 + (i % 2) * POINT, 1.1002 + (i % 2) * POINT, msc, ATR, True)
            if div.sparse != state:
                flips += 1
                state = div.sparse
        self.assertEqual(flips, 0)                       # 15 is between 10 and 20
        for i in range(30):                              # one tick / 7 s: drops below 10
            msc += 7000
            div.feed(1.1 + (i % 2) * POINT, 1.1002 + (i % 2) * POINT, msc, ATR, True)
        self.assertTrue(div.sparse)
        for i in range(200):                             # 15 per minute again: stays off
            msc += 4000
            div.feed(1.1 + (i % 2) * POINT, 1.1002 + (i % 2) * POINT, msc, ATR, True)
            self.assertTrue(div.sparse)

    def test_self_disables_within_sixty_seconds_of_a_thinning_feed(self):
        div = p10.TickDivergence()
        div.arm(3, p10.BUY)
        msc = T0
        for i in range(100):
            div.feed(1.1 + (i % 2) * POINT, 1.1002 + (i % 2) * POINT, msc, ATR, True)
            msc += 200
        thin_start = msc
        i = 0
        while not div.sparse:
            msc += 10_000
            i += 1
            div.feed(1.1 + (i % 2) * POINT, 1.1002 + (i % 2) * POINT, msc, ATR, True)
        self.assertLessEqual(msc - thin_start, 60_000)

    def test_flip_journal_is_once_per_session(self):
        div = p10.TickDivergence()
        div.arm(3, p10.BUY)
        msc = T0
        def burst(n, gap):
            nonlocal msc
            for i in range(n):
                msc += gap
                div.feed(1.1 + (i % 2) * POINT, 1.1002 + (i % 2) * POINT, msc, ATR, True)
        burst(80, 200)
        for _ in range(3):
            burst(30, 9000)
            burst(60, 500)
        kinds = [x.split(" | ")[1] for x in div.journal]
        self.assertEqual(kinds, ["Tick divergence active", "Tick divergence inactive",
                                 "Tick divergence recovered"])

    def test_warmup_fifty_ticks_then_active_line(self):
        div = p10.TickDivergence()
        div.arm(3, p10.SELL)
        for i, (bid, ask, msc) in enumerate(ticks(warmup(60))):
            div.feed(bid, ask, msc, ATR, True)
            self.assertEqual(div.warm, i + 1 >= p10.WARMUP_TICKS)
            if i + 1 < p10.WARMUP_TICKS:
                self.assertEqual(div.multiplier(), 1.0)
        self.assertEqual(div.journal, [
            "Emtt | Tick divergence active | SELL | warmup 50 ticks complete | bar 2026.10.12 09:00"])


class LifecycleTests(unittest.TestCase):
    def test_reset_on_close_and_fresh_warmup_on_adopt_or_new_ticket(self):
        div = p10.TickDivergence()
        path, _ = bearish_divergence(strong=True)
        pos = p10.Position(21, p10.BUY, ATR, True)
        stream = ticks(path)
        for bid, ask, msc in stream:
            p10.manager_feed(div, pos, bid, ask, msc)
        self.assertEqual(div.level, p10.STRONG)
        # Re-attach: a new EA instance adopts ticket 21 with an empty state.
        adopted = p10.TickDivergence()
        bid, ask, msc = stream[-1]
        p10.manager_feed(adopted, pos, bid, ask, msc + 200)
        self.assertEqual((adopted.total, adopted.warm, adopted.level), (1, False, p10.NONE))
        # A different ticket in the same instance starts fresh as well.
        p10.manager_feed(div, p10.Position(22, p10.BUY, ATR, True), bid, ask, msc + 400)
        self.assertEqual((div.ticket, div.total, div.warm, div.level), (22, 1, False, p10.NONE))
        # Close: everything empties.
        p10.manager_feed(div, None, bid, ask, msc + 600)
        self.assertFalse(div.armed)
        self.assertEqual(div.total, 0)

    def test_determinism_same_stream_same_state_and_journal(self):
        path, _ = bearish_divergence(strong=True)
        path += ramp(path[-1], path[-1] - 10) + ramp(path[-1] - 10, 90) + ramp(90, 80)
        a = p10.run(ticks(path))
        b = p10.run(ticks(path))
        self.assertEqual(a.journal, b.journal)
        self.assertEqual((a.level, a.multiplier(), a.cvd_now, a.cvd_abs, a.window()),
                         (b.level, b.multiplier(), b.cvd_now, b.cvd_abs, b.window()))


class TrailingEditTests(unittest.TestCase):
    # ATR method (a third of the way to TP1): 1.5 ATR x0.9 confidence.
    ARGS = (p10.BUY, 1.08000, 1.08200, 1.08600, 0.00100, "M15", 72, BULL, False)

    def test_default_one_is_byte_identical_to_phase8(self):
        for confidence in (50, 60, 75, 90):
            for regime in (BULL, TRANSITION, RANGING):
                args = self.ARGS[:6] + (confidence, regime, True)
                self.assertEqual(p10.trail_calculate(*args), p8.trail_calculate(*args))
                self.assertEqual(p10.trail_calculate(*args, divergence_mult=1.0),
                                 p8.trail_calculate(*args))

    def test_multiplier_applies_after_confidence_regime_and_news(self):
        base = p8.trail_calculate(*self.ARGS)
        for mult in (p10.WEAK_MULT, p10.STRONG_MULT):
            tight = p10.trail_calculate(*self.ARGS, divergence_mult=mult)
            self.assertAlmostEqual(tight.distance, base.distance * mult, places=12)
            self.assertEqual((tight.confidence_multiplier, tight.regime_multiplier,
                              tight.news_multiplier),
                             (base.confidence_multiplier, base.regime_multiplier,
                              base.news_multiplier))
            self.assertGreater(tight.stop, base.stop)       # BUY: closer to price

    def test_never_moves_the_stop_backwards_and_status_journal_reset(self):
        path, _ = bearish_divergence(strong=True)
        div = p10.run(ticks(path))
        self.assertEqual(div.multiplier(), 0.5)
        trail = p10.trail_calculate(*self.ARGS, divergence_mult=div.multiplier())
        update = p10.trailing_update(p10.BUY, 1.08000, 1.08100, 1.08200, 1.08202, trail,
                                     0.00100, POINT, 5, 32, div, "ATR")
        self.assertTrue(update.moved)
        self.assertEqual(update.status, p10.STATUS_STRONG)
        self.assertIn(" x0.5) | +32 pts locked", update.journal)
        self.assertEqual(div.level, p10.NONE)             # stop move reset
        # Next update at 1.0: the looser stop would be further away - kept.
        loose = p10.trail_calculate(*self.ARGS, divergence_mult=div.multiplier())
        again = p10.trailing_update(p10.BUY, 1.08000, update.stop, 1.08200, 1.08202,
                                    loose, 0.00100, POINT, 5, 32, div, "ATR")
        self.assertFalse(again.moved)
        self.assertEqual(again.stop, update.stop)

    def test_generic_trailing_line_and_no_factor_when_one(self):
        div = p10.TickDivergence()
        trail = p10.trail_calculate(*self.ARGS)
        update = p10.trailing_update(p10.BUY, 1.08000, 1.08000, 1.08200, 1.08202, trail,
                                     0.00100, POINT, 5, 32, div, "ATR")
        self.assertTrue(update.moved)
        self.assertTrue(update.status.startswith("Trailing \u2014 stop at "))
        self.assertNotRegex(update.journal, r" x\d\.\d\)")


class MqlMirrorTests(unittest.TestCase):
    def test_header_constants_match_the_reference(self):
        text = HEADER.read_text()
        expected = {
            "EMTT_DIV_TICKS": p10.TICKS, "EMTT_DIV_MAX_WINDOW_MIN": p10.MAX_WINDOW_MIN,
            "EMTT_DIV_SWING_STRENGTH": p10.SWING_STRENGTH, "EMTT_DIV_DENSITY_MIN": p10.DENSITY_MIN,
            "EMTT_DIV_DENSITY_MIN_TICKS": p10.DENSITY_MIN_TICKS,
            "EMTT_DIV_DENSITY_RECOVER": p10.DENSITY_RECOVER,
            "EMTT_DIV_WARMUP_TICKS": p10.WARMUP_TICKS,
            "EMTT_DIV_PRICE_LEAST_ATR": p10.PRICE_LEAST_ATR,
            "EMTT_DIV_STRONG_RATIO": p10.STRONG_RATIO, "EMTT_DIV_CONFIRM_TICKS": p10.CONFIRM_TICKS,
            "EMTT_DIV_WEAK_MULT": p10.WEAK_MULT, "EMTT_DIV_STRONG_MULT": p10.STRONG_MULT,
        }
        for name, value in expected.items():
            match = re.search(rf"#define {name}\s+([0-9.]+)", text)
            self.assertIsNotNone(match, name)
            self.assertEqual(float(match.group(1)), float(value), name)

    def test_header_status_and_journal_wording_match(self):
        text = HEADER.read_text().replace("\\x2014", "\u2014")
        self.assertIn('"' + p10.STATUS_WEAK + '"', text)
        self.assertIn('"' + p10.STATUS_STRONG + '"', text)
        for fragment in ("Emtt | Tick divergence active | ", " ticks complete | bar ",
                         "Emtt | Tick divergence inactive | sparse feed (", " ticks/min) | bar ",
                         "Emtt | Tick divergence recovered | ", "Emtt | Divergence ",
                         "exhausted", "fading", ") | trail ", "x | tick ",
                         "Emtt | Divergence reset | ", "fresh leg after pullback",
                         "stop moved", "leg left the window"):
            self.assertIn(fragment, text)

    def test_header_is_ascii_and_pure(self):
        raw = HEADER.read_bytes()
        self.assertTrue(raw.isascii())
        code = smoke.strip_comments_and_strings(raw.decode())
        for token in ("OrderSend", "PositionClose", "ObjectCreate", "FileOpen", "CopyRates",
                      "CopyBuffer", "CopyTicks", "ArrayResize", "TimeCurrent", "MathRand"):
            self.assertNotIn(token, code)

    def test_contract_includes_phase10_and_rejects_violations(self):
        paths = smoke.resolve_include_graph(smoke.ENTRY)
        names = {p.name for p in paths}
        self.assertIn("Emtt_TickDivergence.mqh", names)
        smoke.check_contract(paths)
        appended = (
            ("Include/Emtt/Emtt_TickDivergence.mqh", "\nvoid Bad(){ OrderSend(); }\n"),
            ("Include/Emtt/Emtt_TickDivergence.mqh", "\nvoid Bad(){ ObjectCreate(); }\n"),
            ("Include/Emtt/Emtt_TickDivergence.mqh", "\n// non-ASCII: \u2014\n"),
            ("Include/Emtt/Emtt_TickDivergence.mqh", "\nvoid Bad(){ FileOpen(); }\n"),
            ("Include/Emtt/Emtt_TickDivergence.mqh", "\nvoid Bad(){ CopyRates(); }\n"),
            ("Include/Emtt/Emtt_TickDivergence.mqh", "\nvoid Bad(){ GlobalVariableSet(); }\n"),
            ("Include/Emtt/Emtt_TickDivergence.mqh", "\nvoid Bad(){ TimeCurrent(); }\n"),
            ("Include/Emtt/Emtt_Trade.mqh", "\n// a second trade edit\n"),
            ("Include/Emtt/Emtt_ParamOpt.mqh", "\n// out-of-scope change\n"),
            ("Include/Emtt/Emtt_Learning.mqh", "\n// out-of-scope change\n"),
            ("Include/Emtt/Emtt_LearnFile.mqh", "\n// out-of-scope change\n"),
            ("Experts/Emtt.mq5", "\ninput bool InpDivergence=true;\n"),
            ("Experts/Emtt.mq5", "\nSEmttTickDivergenceState g_tickDiv;\n"),
        )
        replaced = (
            ("Include/Emtt/Emtt_TickDivergence.mqh", "EMTT_DIV_TICKS 300", "EMTT_DIV_TICKS 500"),
            ("Include/Emtt/Emtt_TickDivergence.mqh", "EMTT_DIV_STRONG_MULT 0.5", "EMTT_DIV_STRONG_MULT 0.4"),
            ("Include/Emtt/Emtt_Trade.mqh", "const double divergenceMult=1.0)",
             "const double divergenceMult=0.8)"),
            ("Experts/Emtt.mq5", "   UpdatePanel();\n   EmttTradeManagerFeedTick(g_trade,g_tickDiv);",
             "   EmttTradeManagerFeedTick(g_trade,g_tickDiv);\n   UpdatePanel();"),
            ("Experts/Emtt.mq5", "   EmttTradeManagerFeedTick(g_trade,g_tickDiv);\n  }",
             "   EmttTradeManagerFeedTick(g_trade,g_tickDiv);\n   CopyRates(g_symbol,g_timeframe,0,1,g_rates);\n  }"),
            ("Include/Emtt/Emtt_TradeManager.mqh", "   if(!SymbolInfoTick(state.symbol,tick))\n      return;\n   const long timeMsc",
             "   if(!SymbolInfoTick(state.symbol,tick))\n      return;\n   MqlRates r[]; CopyRates(state.symbol,PERIOD_M1,0,1,r);\n   const long timeMsc"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            shutil.copytree(ROOT / "Include", work / "Include")
            shutil.copytree(ROOT / "Experts", work / "Experts")
            with mock.patch.object(smoke, "ROOT", work), \
                    mock.patch.object(smoke, "ENTRY", work / "Experts/Emtt.mq5"):
                smoke.check_contract(smoke.resolve_include_graph(smoke.ENTRY))
                for name, extra in appended:
                    with self.subTest(name=name, extra=extra):
                        path = work / name
                        saved = path.read_text()
                        path.write_text(saved + extra)
                        try:
                            with self.assertRaises(RuntimeError):
                                smoke.check_contract(smoke.resolve_include_graph(smoke.ENTRY))
                        finally:
                            path.write_text(saved)
                for name, old, new in replaced:
                    with self.subTest(name=name, old=old):
                        path = work / name
                        saved = path.read_text()
                        self.assertIn(old, saved)
                        path.write_text(saved.replace(old, new, 1))
                        try:
                            with self.assertRaises(RuntimeError):
                                smoke.check_contract(smoke.resolve_include_graph(smoke.ENTRY))
                        finally:
                            path.write_text(saved)


if __name__ == "__main__":
    unittest.main()
