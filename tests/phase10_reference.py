"""Portable reference model for Emtt Phase 10 (Emtt.md 25.3-25.11).

This module is intentionally MT5-free. It mirrors
``Include/Emtt/Emtt_TickDivergence.mqh`` statement for statement - the tick
sign, the fixed 300-slot ring with its two running sums and 15-minute
expiry, the incremental strength-5 tick swings, the density gate with
hysteresis, the 50-tick warmup, the weak / strong divergence reading with
3-tick confirmation, the resets and the hysteresis - plus the single 25.9
edit to the Phase 8 trailing distance and the manager's STATUS / journal
wording. Feeding the same tick stream always produces the same state,
multiplier and journal lines.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Iterable, Optional

import phase8_reference as p8

# 25.12 rows p - z.
TICKS = 300
MAX_WINDOW_MIN = 15
SWING_STRENGTH = 5
DENSITY_MIN = 60
DENSITY_MIN_TICKS = 10
DENSITY_RECOVER = 20
WARMUP_TICKS = 50
PRICE_LEAST_ATR = 0.10
STRONG_RATIO = 0.5
CONFIRM_TICKS = 3
WEAK_MULT = 0.8
STRONG_MULT = 0.5

NONE = 0
WEAK = 1
STRONG = 2

BUY = 1
SELL = -1
DASH = "\u2014"

STATUS_WEAK = f"Trailing {DASH} momentum fading, tightening trail."
STATUS_STRONG = f"Trailing {DASH} momentum exhausted, tightening trail."


def tick_sign(prev_bid: float, prev_ask: float, bid: float, ask: float) -> int:
    """25.3: +1 aggressive buying, -1 aggressive selling, 0 otherwise."""
    ask_up, ask_down = ask > prev_ask, ask < prev_ask
    bid_up, bid_down = bid > prev_bid, bid < prev_bid
    if (ask_up and bid_down) or (ask_down and bid_up):
        return 0
    if ask_up or (bid_up and ask >= prev_ask):
        return 1
    if bid_down or (ask_down and bid <= prev_bid):
        return -1
    return 0


def level_multiplier(level: int) -> float:
    if level == STRONG:
        return STRONG_MULT
    if level == WEAK:
        return WEAK_MULT
    return 1.0


def trail_status(level: int) -> str:
    if level == STRONG:
        return STATUS_STRONG
    if level == WEAK:
        return STATUS_WEAK
    return ""


def side_name(side: int) -> str:
    return "BUY" if side > 0 else "SELL"


def mql_time(msc: int, seconds: bool) -> str:
    """TimeToString(msc/1000, TIME_DATE|TIME_MINUTES or |TIME_SECONDS)."""
    stamp = datetime.fromtimestamp(msc // 1000, tz=timezone.utc)
    return stamp.strftime("%Y.%m.%d %H:%M:%S" if seconds else "%Y.%m.%d %H:%M")


def active_line(side: int, msc: int) -> str:
    return (f"Emtt | Tick divergence active | {side_name(side)} | warmup "
            f"{WARMUP_TICKS} ticks complete | bar {mql_time(msc, False)}")


def inactive_line(density: int, msc: int) -> str:
    return (f"Emtt | Tick divergence inactive | sparse feed ({density} ticks/min)"
            f" | bar {mql_time(msc, False)}")


def recovered_line(density: int, msc: int) -> str:
    return (f"Emtt | Tick divergence recovered | {density} ticks/min | bar "
            f"{mql_time(msc, False)}")


def reset_line(side: int, reason: str, msc: int) -> str:
    return (f"Emtt | Divergence reset | {side_name(side)} | {reason} | tick "
            f"{mql_time(msc, True)}")


@dataclass
class TickDivergence:
    """SEmttTickDivergenceState with the functions of 25.3-25.7."""

    armed: bool = False
    ticket: int = 0
    side: int = 0
    digits: int = 5
    msc: list = field(default_factory=lambda: [0] * TICKS)
    mid: list = field(default_factory=lambda: [0.0] * TICKS)
    sign: list = field(default_factory=lambda: [0] * TICKS)
    cvd: list = field(default_factory=lambda: [0] * TICKS)
    run_start: list = field(default_factory=lambda: [0] * TICKS)
    total: int = 0
    oldest: int = 0
    density_start: int = 0
    cvd_now: int = 0
    cvd_abs: int = 0
    density: int = 0
    has_prev: bool = False
    prev_bid: float = 0.0
    prev_ask: float = 0.0
    last_msc: int = 0
    warm: bool = False
    sparse: bool = False
    sparse_journaled: bool = False
    recover_journaled: bool = False
    breakeven: bool = False
    atr: float = 0.0
    has0: bool = False
    price_peak0: float = 0.0
    cvd_at_peak0: int = 0
    seq0: int = -1
    has1: bool = False
    price_peak1: float = 0.0
    cvd_at_peak1: int = 0
    seq1: int = -1
    pullback: bool = False
    level: int = NONE
    weak_held: int = 0
    strong_held: int = 0
    journal: list = field(default_factory=list)

    #--- lifecycle -----------------------------------------------------
    def reset(self) -> None:
        journal = self.journal
        fresh = TickDivergence()
        self.__dict__.update(fresh.__dict__)
        self.journal = journal

    def arm(self, ticket: int, side: int, digits: int = 5) -> None:
        self.reset()
        self.armed = ticket > 0 and side in (BUY, SELL)
        self.ticket = ticket if self.armed else 0
        self.side = side if self.armed else 0
        self.digits = digits if digits > 0 else 5

    def clear_legs(self) -> None:
        self.has0 = self.has1 = False
        self.price_peak0 = self.price_peak1 = 0.0
        self.cvd_at_peak0 = self.cvd_at_peak1 = 0
        self.seq0 = self.seq1 = -1
        self.pullback = False
        self.level = NONE
        self.weak_held = self.strong_held = 0

    #--- reading -------------------------------------------------------
    @property
    def count(self) -> int:
        return self.total - self.oldest

    def active(self) -> bool:
        return self.armed and self.breakeven and self.warm and not self.sparse

    def multiplier(self) -> float:
        return level_multiplier(self.level) if self.active() else 1.0

    def window(self) -> list:
        """(msc, mid, sign, cvd) of every tick in the window, oldest first."""
        return [(self.msc[s % TICKS], self.mid[s % TICKS], self.sign[s % TICKS],
                 self.cvd[s % TICKS]) for s in range(self.oldest, self.total)]

    def level_line(self, level: int, msc: int) -> str:
        strong = level == STRONG
        return (f"Emtt | Divergence {'strong' if strong else 'weak'} | "
                f"{side_name(self.side)} | new {'high' if self.side > 0 else 'low'} "
                f"{self.price_peak1:.{self.digits}f}, CVD "
                f"{'exhausted' if strong else 'fading'} (cvd {self.cvd_at_peak1} vs "
                f"{self.cvd_at_peak0}) | trail {level_multiplier(level):.1f}x | tick "
                f"{mql_time(msc, True)}")

    #--- resets --------------------------------------------------------
    def _reset_leg(self, reason: str, write: bool) -> None:
        latched = self.level != NONE
        self.level = NONE
        self.weak_held = self.strong_held = 0
        if latched and write:
            self.journal.append(reset_line(self.side, reason, self.last_msc))

    def on_stop_moved(self, write: bool = True) -> None:
        if not self.armed:
            return
        latched = self.level != NONE
        self._reset_leg("stop moved", write)
        if latched:
            self.has0 = self.has1 = False
            self.pullback = False

    def _on_peak(self, sequence: int, price: float, cvd_value: int, write: bool) -> None:
        if self.has1 and self.pullback and self.level != NONE:
            self._reset_leg("fresh leg after pullback", write)
            self.has1 = False
        if self.has1:
            self.has0 = True
            self.price_peak0 = self.price_peak1
            self.cvd_at_peak0 = self.cvd_at_peak1
            self.seq0 = self.seq1
        else:
            self.has0 = False
        self.has1 = True
        self.price_peak1 = price
        self.cvd_at_peak1 = cvd_value
        self.seq1 = sequence
        self.pullback = False

    def _detect_swing(self, write: bool) -> Optional[tuple]:
        newest = self.total - 1 - SWING_STRENGTH
        if newest < self.oldest:
            return None
        first = self.run_start[newest % TICKS]
        if first - SWING_STRENGTH < self.oldest:
            return None
        price = self.mid[newest % TICKS]
        is_high = is_low = True
        for k in range(1, SWING_STRENGTH + 1):
            after = self.mid[(newest + k) % TICKS]
            before = self.mid[(first - k) % TICKS]
            if not (after < price and before < price):
                is_high = False
            if not (after > price and before > price):
                is_low = False
            if not is_high and not is_low:
                return None
        pivot_side = 1 if is_high else -1
        if pivot_side == self.side:
            self._on_peak(first, price, self.cvd[first % TICKS], write)
        elif self.has1 and first > self.seq1:
            self.pullback = True
        return (pivot_side, first, price)

    def _pop(self) -> None:
        if self.oldest >= self.total:
            return
        slot = self.oldest % TICKS
        self.cvd_now -= self.sign[slot]
        self.cvd_abs -= 1 if self.sign[slot] != 0 else 0
        self.oldest += 1

    #--- one tick ------------------------------------------------------
    def feed(self, bid: float, ask: float, msc: int, atr: float,
             breakeven: bool, write: bool = True) -> bool:
        if not self.armed or bid <= 0.0 or ask <= 0.0 or msc <= 0:
            return False
        if self.has_prev:
            if msc < self.last_msc:
                return False
            if msc == self.last_msc and bid == self.prev_bid and ask == self.prev_ask:
                return False
        self.breakeven = breakeven
        self.atr = atr
        sign = tick_sign(self.prev_bid, self.prev_ask, bid, ask) if self.has_prev else 0
        self.has_prev = True
        self.prev_bid, self.prev_ask, self.last_msc = bid, ask, msc

        max_age = MAX_WINDOW_MIN * 60 * 1000
        while self.oldest < self.total and msc - self.msc[self.oldest % TICKS] > max_age:
            self._pop()
        if self.total - self.oldest >= TICKS:
            self._pop()

        sequence = self.total
        slot = sequence % TICKS
        mid = (bid + ask) / 2.0
        self.cvd_now += sign
        self.cvd_abs += 1 if sign != 0 else 0
        self.msc[slot] = msc
        self.mid[slot] = mid
        self.sign[slot] = sign
        self.cvd[slot] = self.cvd_now
        if sequence > self.oldest and self.mid[(sequence - 1) % TICKS] == mid:
            self.run_start[slot] = self.run_start[(sequence - 1) % TICKS]
        else:
            self.run_start[slot] = sequence
        self.total = sequence + 1

        if self.has0 and self.seq0 < self.oldest:
            self.has0 = False
        if self.has1 and self.seq1 < self.oldest:
            self.has1 = False
            self.pullback = False
            self._reset_leg("leg left the window", write)

        if self.density_start < self.oldest:
            self.density_start = self.oldest
        density_age = DENSITY_MIN * 1000
        while (self.density_start < self.total and
               msc - self.msc[self.density_start % TICKS] >= density_age):
            self.density_start += 1
        self.density = self.total - self.density_start
        was_sparse = self.sparse
        if not self.sparse and self.density < DENSITY_MIN_TICKS:
            self.sparse = True
        elif self.sparse and self.density >= DENSITY_RECOVER:
            self.sparse = False

        if not self.warm and self.total >= WARMUP_TICKS:
            self.warm = True
            if self.sparse:
                if write:
                    self.journal.append(inactive_line(self.density, msc))
                self.sparse_journaled = True
            elif write:
                self.journal.append(active_line(self.side, msc))
        elif self.warm and self.sparse != was_sparse:
            if self.sparse and not self.sparse_journaled:
                if write:
                    self.journal.append(inactive_line(self.density, msc))
                self.sparse_journaled = True
            elif not self.sparse and not self.recover_journaled:
                if write:
                    self.journal.append(recovered_line(self.density, msc))
                self.recover_journaled = True

        self._detect_swing(write)

        if not self.active():
            self.level = NONE
            self.weak_held = self.strong_held = 0
            return True
        candidate = self.candidate()
        self.weak_held = self.weak_held + 1 if candidate >= WEAK else 0
        self.strong_held = self.strong_held + 1 if candidate >= STRONG else 0
        if self.level < STRONG and self.strong_held >= CONFIRM_TICKS:
            self.level = STRONG
            if write:
                self.journal.append(self.level_line(STRONG, msc))
        elif self.level < WEAK and self.weak_held >= CONFIRM_TICKS:
            self.level = WEAK
            if write:
                self.journal.append(self.level_line(WEAK, msc))
        return True

    def candidate(self) -> int:
        """25.7 the unconfirmed reading of the two tracked legs."""
        if not (self.atr > 0.0 and self.has0 and self.has1):
            return NONE
        leg = self.side * (self.price_peak1 - self.price_peak0)
        c0 = float(self.side * self.cvd_at_peak0)
        c1 = float(self.side * self.cvd_at_peak1)
        if leg > 0.0 and leg >= PRICE_LEAST_ATR * self.atr and c1 < c0:
            return STRONG if c1 <= c0 * STRONG_RATIO else WEAK
        return NONE


#--- the manager's per-tick feed (25.1) ---------------------------------
@dataclass(frozen=True)
class Position:
    ticket: int
    side: int
    entry_atr: float
    breakeven: bool


def manager_feed(div: TickDivergence, position: Optional[Position],
                 bid: float, ask: float, msc: int, digits: int = 5) -> None:
    """EmttTradeManagerFeedTick: arm on a new / adopted ticket, reset when flat."""
    if position is None or position.ticket == 0 or position.side not in (BUY, SELL):
        if div.armed:
            div.reset()
        return
    if not div.armed or div.ticket != position.ticket or div.side != position.side:
        div.arm(position.ticket, position.side, digits)
    div.feed(bid, ask, msc, position.entry_atr, position.breakeven, True)


#--- 25.9: the one edit to the Phase 8 trailing distance -----------------
def trail_calculate(*args, divergence_mult: float = 1.0, **kwargs) -> p8.TrailResult:
    """Phase 8 trail_calculate with the final distance times divergenceMult."""
    base = p8.trail_calculate(*args, **kwargs)
    if not base.valid:
        return base
    distance = (base.raw_distance * base.confidence_multiplier *
                base.regime_multiplier * base.news_multiplier * divergence_mult)
    if distance <= 0 or not math.isfinite(distance):
        return p8.TrailResult(False)
    side = args[0] if args else kwargs["side"]
    current = args[2] if len(args) > 2 else kwargs["current"]
    stop = current - distance if side == BUY else current + distance
    return replace(base, distance=distance, stop=stop)


@dataclass(frozen=True)
class TrailUpdate:
    moved: bool
    stop: float
    status: str = ""
    journal: str = ""


def trailing_update(side: int, entry: float, current_stop: float, bid: float,
                    ask: float, trail: p8.TrailResult, atr: float, point: float,
                    digits: int, locked_points: int, div: TickDivergence,
                    method_name: str = "ATR") -> TrailUpdate:
    """The manager's 21.7 step 3 with the 25.8 multiplier already applied.

    Mirrors the clamp to entry, the never-backwards guard, the 25.10 STATUS
    replacement, the 25.11 journal factor and the 25.7 stop-move reset.
    """
    div_mult = div.multiplier()
    div_level = div.level if div_mult < 1.0 else NONE
    if not trail.valid:
        return TrailUpdate(False, current_stop)
    proposed = trail.stop
    if side > 0 and proposed < entry:
        proposed = entry
    if side < 0 and proposed > entry:
        proposed = entry
    proposed = round(proposed, digits)
    if not (p8.stop_improves(side, current_stop, proposed, point) and
            (proposed < bid if side > 0 else proposed > ask)):
        return TrailUpdate(False, current_stop)
    status = (trail_status(div_level) if div_level != NONE else
              f"Trailing {DASH} stop at {proposed:.{digits}f}, +{locked_points} pts locked.")
    factor = trail.confidence_multiplier * trail.regime_multiplier * trail.news_multiplier
    journal = (f"Trailing updated | {method_name} | stop {proposed:.{digits}f} "
               f"({trail.raw_distance / atr:.1f} ATR x{factor:.2f}"
               f"{f' x{div_mult:.1f}' if div_mult != 1.0 else ''}) | +{locked_points} pts locked")
    div.on_stop_moved(True)
    return TrailUpdate(True, proposed, status, journal)


def run(ticks: Iterable[tuple], side: int = BUY, atr: float = 0.001,
        breakeven: bool = True, ticket: int = 7) -> TickDivergence:
    """Feed (bid, ask, msc) triples into a freshly armed session."""
    div = TickDivergence()
    div.arm(ticket, side)
    for bid, ask, msc in ticks:
        div.feed(bid, ask, msc, atr, breakeven)
    return div
