"""Portable reference logic for Emtt Phase 4 market structure (SMC).

The production component consumes MQL5 series arrays, where index 0 is the
newest *closed* candle.  This module keeps that convention and contains no MT5
calls, so the exact structure rules in Emtt.md sections 13.3-13.11 can be
exercised on every CI platform.

It intentionally uses a half-away-from-zero helper rather than Python's
``round``: the Phase-4 window matrix contains 62.5 and 87.5 values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable, Optional, Sequence

# 13.5-13.10 fixed constants -------------------------------------------------
DISPLACEMENT_MULTIPLE = 1.5
IMPULSE_BARS = 3
EQUAL_TOLERANCE_ATR = 0.10
ZONE_DEADBAND = 0.05
MIN_RANGE_ATR = 1.0
MAX_ZONES = 8
MAX_SWINGS = 64

WEIGHT_STRUCTURE = 0.30
WEIGHT_FRESHNESS = 0.20
WEIGHT_ZONE = 0.20
WEIGHT_PROXIMITY = 0.15
WEIGHT_SWEEP = 0.15
EVENT_AGE_BARS = 40
PROXIMITY_ATRS = 2.0
SWEEP_AGE_BARS = 20
CHOCH_TERM = 0.6

OB_LOOKBACK_DIVISOR = 3
OB_LOOKBACK_MIN = 10
WINDOW_MIN = 20
WINDOW_MAX = 400
PARAMETER_PAUSE_BARS = 2
STATUS_FRESH_BARS = 3
SWEEP_MENTION_BARS = 10

LOW = "LOW"
NORMAL = "NORMAL"
HIGH = "HIGH"
VOLATILITIES = (LOW, NORMAL, HIGH)
TIMEFRAME_SCALE = {"M5": 1.0, "M15": 1.25, "M30": 1.5}
ASSET_CLASSES = (
    "Forex Major",
    "Forex Cross",
    "Metals",
    "Crypto",
    "Indices",
    "Generic",
)

EVENT_NONE = ""
BOS = "BOS"
CHOCH = "CHoCH"
ZONE_NONE = ""
DISCOUNT = "Discount"
PREMIUM = "Premium"
EQUILIBRIUM = "Equilibrium"
SWEEP_NONE = ""
BUY_SIDE = "buy"
SELL_SIDE = "sell"

ROW10_STRUCTURE = "Watching — structure context only, no signal yet"
ROW10_INCOMPATIBLE = "Incompatible chart. Switch to M5/M15/M30."


@dataclass(frozen=True)
class Bar:
    """A closed bar; collections are always MQL5 series order."""

    open: float
    high: float
    low: float
    close: float
    time: int = 0


@dataclass(frozen=True)
class Parameters:
    structure_window: int
    swing_strength: int
    body_period: int
    ob_lookback: int


@dataclass
class Swing:
    high: bool
    level: float
    time: int
    sequence: int
    pivot_index: int
    consumed: bool = False
    swept: bool = False


@dataclass
class Pool:
    high: bool
    level: float
    count: int
    newest_sequence: int
    swept: bool = False


@dataclass
class OrderBlock:
    bullish: bool
    low: float
    high: float
    origin_time: int
    origin_sequence: int
    created_sequence: int
    ratio: float
    active: bool = True
    mitigated: bool = False
    invalidated: bool = False
    mitigation_time: int = 0


@dataclass
class Gap:
    bullish: bool
    low: float
    high: float
    origin_time: int
    origin_sequence: int
    created_sequence: int
    active: bool = True
    mitigated: bool = False
    filled: bool = False
    mitigation_time: int = 0


@dataclass
class SmcState:
    """The portable equivalent of the SMC component's published state."""

    params: Parameters
    asset_class: str
    volatility: str
    initialized: bool = False
    ready: bool = False
    atr_period: int = 14
    atr_value: float = 0.0
    swings: list[Swing] = field(default_factory=list)
    pools: list[Pool] = field(default_factory=list)
    blocks: list[OrderBlock] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    bias: int = 0
    event_kind: str = EVENT_NONE
    event_direction: int = 0
    event_sequence: Optional[int] = None
    event_time: int = 0
    last_sweep_side: str = SWEEP_NONE
    last_sweep_level: float = 0.0
    sweep_sequence: Optional[int] = None
    sweep_time: int = 0
    zone: str = ZONE_NONE
    leg_direction: int = 0
    range_low: float = 0.0
    range_high: float = 0.0
    equilibrium: float = 0.0
    zone_position: float = 0.0
    has_order_block: bool = False
    order_block: Optional[OrderBlock] = None
    distance_to_ob_atrs: float = 0.0
    gap_above: Optional[Gap] = None
    gap_below: Optional[Gap] = None
    gap_distance_atrs: float = 0.0
    mitigated_block_count: int = 0
    score: float = 0.0
    journal: list[str] = field(default_factory=list)
    last_window_change: int = -1_000_000
    last_strength_change: int = -1_000_000
    last_body_change: int = -1_000_000
    last_ob_change: int = -1_000_000

    @property
    def bars_since_event(self) -> int:
        return 1_000_000 if self.event_sequence is None else self._current_sequence - self.event_sequence

    @property
    def bars_since_sweep(self) -> int:
        return 1_000_000 if self.sweep_sequence is None else self._current_sequence - self.sweep_sequence

    # Stored by tracker for the two age properties; it is a fact, not a clock.
    _current_sequence: int = 0


# Parameter matrix ------------------------------------------------------------

def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0


def round_half_away(value: float) -> int:
    """Positive Phase-4 values use MQL5 MathRound semantics, never round()."""
    if value >= 0.0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)


def lookback_scale(timeframe: str) -> float:
    return TIMEFRAME_SCALE.get(timeframe, 1.0)


def matrix_values(asset_class: str, volatility: str) -> tuple[int, int, int]:
    """Return unscaled window, pivot strength and body period (13.10)."""
    high = volatility == HIGH
    low = volatility == LOW
    body = 21 if high else 14
    if asset_class == "Metals":
        return (50 if low else 80 if high else 60, 2 if low else 3, body)
    if asset_class == "Crypto":
        return (40 if low else 70 if high else 50, 2 if low else 4 if high else 3, body)
    if asset_class == "Indices":
        return (50 if low else 80 if high else 60, 3 if high else 2, body)
    # Forex Major, Forex Cross and Generic share this matrix.
    return (80 if high else 60, 3 if high else 2, body)


def scaled_window(asset_class: str, volatility: str, timeframe: str) -> int:
    base, _, _ = matrix_values(asset_class, volatility)
    return max(WINDOW_MIN, min(WINDOW_MAX, round_half_away(base * lookback_scale(timeframe))))


def resolve_parameters(asset_class: str, volatility: str, timeframe: str) -> Parameters:
    """Layer 2 scales the window only, then every dynamic value is clamped."""
    windows = [scaled_window(asset_class, bucket, timeframe) for bucket in VOLATILITIES]
    strengths = [matrix_values(asset_class, bucket)[1] for bucket in VOLATILITIES]
    bodies = [matrix_values(asset_class, bucket)[2] for bucket in VOLATILITIES]
    window = scaled_window(asset_class, volatility, timeframe)
    _, strength, body = matrix_values(asset_class, volatility)
    window = max(min(windows), min(max(windows), window))
    strength = max(min(strengths), min(max(strengths), strength))
    body = max(min(bodies), min(max(bodies), body))
    return Parameters(window, strength, body, max(OB_LOOKBACK_MIN, round_half_away(window / OB_LOOKBACK_DIVISOR)))


def smc_history_required(asset_class: str, volatility: str, timeframe: str) -> int:
    p = resolve_parameters(asset_class, volatility, timeframe)
    return p.structure_window + p.swing_strength + p.body_period + 2


def supertrend_history_required(timeframe: str) -> int:
    return round_half_away(200 * lookback_scale(timeframe)) + 50


def combined_history_required(asset_class: str, volatility: str, timeframe: str) -> int:
    return max(supertrend_history_required(timeframe), smc_history_required(asset_class, volatility, timeframe))


def can_change_at(current_bar: int, last_change_bar: int) -> bool:
    return current_bar - last_change_bar > PARAMETER_PAUSE_BARS


# Swings ----------------------------------------------------------------------

def pivot_at(rates: Sequence[Bar], index: int, strength: int, high: bool) -> Optional[tuple[int, float]]:
    """13.3 pivot test, including oldest-bar plateau ownership.

    ``index`` is the newly evaluated closed bar. The newest plateau member
    must be exactly ``strength`` bars older; the returned index is the oldest
    equal-extreme member that owns the published pivot.
    """
    if index < 0 or strength <= 0 or index + strength >= len(rates):
        return None
    newest = index + strength
    level = rates[newest].high if high else rates[newest].low
    if newest > index:
        newer = rates[newest - 1].high if high else rates[newest - 1].low
        if newer == level:
            return None
    oldest = newest
    while oldest + 1 < len(rates):
        neighbour = rates[oldest + 1].high if high else rates[oldest + 1].low
        if neighbour != level:
            break
        oldest += 1
    if oldest + strength >= len(rates):
        return None
    for offset in range(1, strength + 1):
        older = rates[oldest + offset].high if high else rates[oldest + offset].low
        newer = rates[newest - offset].high if high else rates[newest - offset].low
        if high and (level <= older or level <= newer):
            return None
        if not high and (level >= older or level >= newer):
            return None
    return oldest, level


def confirmed_swings(rates: Sequence[Bar], strength: int, window: int) -> list[Swing]:
    """Replay pivots oldest-to-newest and retain only the current window."""
    found: list[Swing] = []
    sequence = 0
    for index in range(len(rates) - 1, -1, -1):
        hp = pivot_at(rates, index, strength, True)
        lp = pivot_at(rates, index, strength, False)
        if hp is None and lp is None:
            sequence += 1
            continue
        # One candidate bar cannot publish both types.
        if hp is not None and lp is not None:
            sequence += 1
            continue
        pivot, level = hp if hp is not None else lp  # type: ignore[misc]
        is_high = hp is not None
        if not any(s.high == is_high and s.time == rates[pivot].time for s in found):
            found.append(Swing(is_high, level, rates[pivot].time, sequence - (pivot - index), pivot - index))
        sequence += 1
    return [s for s in found if sequence - s.sequence < window][-MAX_SWINGS:]


# Order blocks and fair-value gaps -------------------------------------------

def average_body_older_than(rates: Sequence[Bar], candidate: int, body_period: int) -> Optional[float]:
    if candidate < 0 or candidate + body_period >= len(rates):
        return None
    values = [abs(rates[candidate + i].close - rates[candidate + i].open) for i in range(1, body_period + 1)]
    average = sum(values) / len(values)
    return average if average > 0.0 else None


def order_block_candidate(
    rates: Sequence[Bar], index: int, candidate: int, body_period: int, bullish: bool
) -> Optional[tuple[int, float, float, float]]:
    """Return origin index, range and displacement ratio for one candidate."""
    if candidate <= index or candidate >= len(rates):
        return None
    origin = rates[candidate]
    if bullish and origin.close >= origin.open:
        return None
    if not bullish and origin.close <= origin.open:
        return None
    average = average_body_older_than(rates, candidate, body_period)
    if average is None:
        return None
    for displacement in range(candidate - 1, max(index, candidate - IMPULSE_BARS) - 1, -1):
        bar = rates[displacement]
        body = abs(bar.close - bar.open)
        if body < DISPLACEMENT_MULTIPLE * average:
            continue
        if bullish and bar.close > bar.open and bar.close > origin.high:
            return candidate, origin.low, origin.high, body / average
        if not bullish and bar.close < bar.open and bar.close < origin.low:
            return candidate, origin.low, origin.high, body / average
    return None


def newest_order_block_candidate(
    rates: Sequence[Bar], index: int, lookback: int, body_period: int, bullish: bool
) -> Optional[tuple[int, float, float, float]]:
    for candidate in range(index + 1, min(len(rates), index + lookback + 1)):
        result = order_block_candidate(rates, index, candidate, body_period, bullish)
        if result is not None:
            return result
    return None


def fair_value_gap(rates: Sequence[Bar], index: int) -> Optional[tuple[bool, float, float]]:
    if index < 0 or index + 2 >= len(rates):
        return None
    a, c = rates[index + 2], rates[index]
    if c.low > a.high:
        return True, a.high, c.low
    if c.high < a.low:
        return False, c.high, a.low
    return None


def update_block(block: OrderBlock, bar: Bar) -> str:
    """Later-bar state transition; invalidation intentionally wins a touch."""
    if not block.active:
        return "none"
    invalid = bar.close < block.low if block.bullish else bar.close > block.high
    if invalid:
        block.active = False
        block.invalidated = True
        return "invalidated"
    if bar.low <= block.high and bar.high >= block.low:
        block.active = False
        block.mitigated = True
        block.mitigation_time = bar.time
        return "mitigated"
    return "none"


def update_gap(gap: Gap, bar: Bar) -> str:
    if not gap.active:
        return "none"
    filled = bar.close < gap.low if gap.bullish else bar.close > gap.high
    if filled:
        gap.active = False
        gap.filled = True
        return "filled"
    if bar.low <= gap.high and bar.high >= gap.low:
        gap.active = False
        gap.mitigated = True
        gap.mitigation_time = bar.time
        return "mitigated"
    return "none"


def select_order_block(blocks: Iterable[OrderBlock], bias: int, close: float, atr: float) -> tuple[Optional[OrderBlock], float]:
    if bias == 0 or atr <= 0.0:
        return None, 0.0
    eligible: list[OrderBlock] = []
    for block in blocks:
        if not block.active or block.bullish != (bias > 0):
            continue
        if bias > 0 and block.high <= close:
            eligible.append(block)
        if bias < 0 and block.low >= close:
            eligible.append(block)
    if not eligible:
        return None, 0.0
    near = lambda b: b.high if bias > 0 else b.low
    selected = min(eligible, key=lambda b: abs(close - near(b)))
    raw = (close - near(selected)) / atr if bias > 0 else (near(selected) - close) / atr
    return selected, max(0.0, raw)


def select_gaps(gaps: Iterable[Gap], close: float, atr: float) -> tuple[Optional[Gap], Optional[Gap], float, float]:
    """Return nearest active (above, below) gaps and their near-edge distances."""
    above = [gap for gap in gaps if gap.active and gap.low >= close]
    below = [gap for gap in gaps if gap.active and gap.high <= close]
    up = min(above, key=lambda gap: gap.low - close) if above else None
    down = min(below, key=lambda gap: close - gap.high) if below else None
    up_dist = max(0.0, (up.low - close) / atr) if up and atr > 0 else 0.0
    down_dist = max(0.0, (close - down.high) / atr) if down and atr > 0 else 0.0
    return up, down, up_dist, down_dist


# Pools, zones and score ------------------------------------------------------

def pools_from_swings(swings: Sequence[Swing], atr: float) -> list[Pool]:
    """Group same-type confirmed levels with max-min <= 0.10 ATR."""
    if atr <= 0.0:
        return []
    tolerance = EQUAL_TOLERANCE_ATR * atr
    output: list[Pool] = []
    for high in (False, True):
        levels = sorted((s for s in swings if s.high == high), key=lambda s: s.level)
        start = 0
        while start < len(levels):
            end = start
            while end + 1 < len(levels) and levels[end + 1].level - levels[start].level <= tolerance:
                end += 1
            group = levels[start : end + 1]
            if len(group) >= 2:
                output.append(Pool(high, sum(s.level for s in group) / len(group), len(group), max(s.sequence for s in group)))
            start = end + 1
    return output


def select_largest_pool(pools: Iterable[Pool], high: bool) -> Optional[Pool]:
    candidates = [pool for pool in pools if pool.high == high]
    return max(candidates, key=lambda p: (p.count, p.newest_sequence)) if candidates else None


def dealing_zone(swings: Sequence[Swing], close: float, atr: float) -> tuple[str, int, float, float, float, float]:
    """Newest swing plus newest older opposite swing defines the dealing leg."""
    if atr <= 0.0 or not swings:
        return ZONE_NONE, 0, 0.0, 0.0, 0.0, 0.0
    end = max(swings, key=lambda s: s.sequence)
    origins = [s for s in swings if s.high != end.high and s.sequence < end.sequence]
    if not origins:
        return ZONE_NONE, 0, 0.0, 0.0, 0.0, 0.0
    origin = max(origins, key=lambda s: s.sequence)
    low, high = sorted((end.level, origin.level))
    height = high - low
    if height < MIN_RANGE_ATR * atr:
        return ZONE_NONE, 0, 0.0, 0.0, 0.0, 0.0
    equilibrium = (high + low) / 2.0
    margin = ZONE_DEADBAND * height
    zone = DISCOUNT if close < equilibrium - margin else PREMIUM if close > equilibrium + margin else EQUILIBRIUM
    return zone, 1 if end.high else -1, low, high, equilibrium, clamp01((close - low) / height)


def smc_score(
    *,
    bias: int,
    event_kind: str,
    event_direction: int,
    bars_since_event: int,
    zone: str,
    has_order_block: bool,
    distance_to_ob_atrs: float,
    last_sweep_side: str,
    bars_since_sweep: int,
) -> float:
    if bias == 0:
        return 0.0
    structure = 0.0
    if event_direction == bias:
        structure = 1.0 if event_kind == BOS else CHOCH_TERM if event_kind == CHOCH else 0.0
    freshness = clamp01(1.0 - bars_since_event / EVENT_AGE_BARS)
    if bias > 0:
        zone_term = 1.0 if zone == DISCOUNT else 0.5 if zone == EQUILIBRIUM else 0.0
    else:
        zone_term = 1.0 if zone == PREMIUM else 0.5 if zone == EQUILIBRIUM else 0.0
    proximity = clamp01(1.0 - distance_to_ob_atrs / PROXIMITY_ATRS) if has_order_block else 0.0
    opposite = (bias > 0 and last_sweep_side == SELL_SIDE) or (bias < 0 and last_sweep_side == BUY_SIDE)
    sweep = clamp01(1.0 - bars_since_sweep / SWEEP_AGE_BARS) if opposite else 0.0
    return clamp01(
        WEIGHT_STRUCTURE * structure
        + WEIGHT_FRESHNESS * freshness
        + WEIGHT_ZONE * zone_term
        + WEIGHT_PROXIMITY * proximity
        + WEIGHT_SWEEP * sweep
    )


# Panel composition -----------------------------------------------------------

def direction_name(direction: int) -> str:
    return "up" if direction > 0 else "down" if direction < 0 else "none"


def row9_clause(
    *,
    ready: bool,
    zone: str,
    event_kind: str,
    event_direction: int,
    has_order_block: bool,
    order_block_near_edge: float,
    has_gap_above: bool,
    has_gap_below: bool,
    gap_above_near_edge: float,
    gap_below_near_edge: float,
    bias: int,
    last_sweep_side: str,
    bars_since_sweep: int,
    digits: int,
) -> str:
    if not ready:
        return ""
    parts: list[str] = []
    if zone:
        parts.append(zone)
    if event_kind and bias:
        parts.append(f"{event_kind} {direction_name(event_direction)}")
    if has_order_block:
        parts.append(f"OB {order_block_near_edge:.{digits}f}")
    elif bias > 0 and has_gap_above:
        parts.append(f"FVG {gap_above_near_edge:.{digits}f}")
    elif bias < 0 and has_gap_below:
        parts.append(f"FVG {gap_below_near_edge:.{digits}f}")
    elif last_sweep_side == SELL_SIDE and bars_since_sweep <= SWEEP_MENTION_BARS:
        parts.append("swept lows")
    elif last_sweep_side == BUY_SIDE and bars_since_sweep <= SWEEP_MENTION_BARS:
        parts.append("swept highs")
    return ", ".join(parts[:3])


def append_row9(prior: str, clause: str) -> str:
    if not clause:
        return prior
    return clause if prior in ("", "--") else f"{prior} | {clause}"


def row10_status(
    *,
    incompatible: bool = False,
    loading: bool = False,
    market_closed: bool = False,
    ready: bool = False,
    event_kind: str = EVENT_NONE,
    event_direction: int = 0,
    bars_since_event: int = 1_000_000,
    fresh_choch_direction: Optional[int] = None,
    fresh_bos_direction: Optional[int] = None,
    last_sweep_side: str = SWEEP_NONE,
    bars_since_sweep: int = 1_000_000,
    supertrend_ready: bool = False,
    phase2_status: str = "",
) -> str:
    if incompatible:
        return ROW10_INCOMPATIBLE
    if loading:
        return "Waiting — Loading chart history"
    if market_closed:
        return "Paused — Waiting for market to open"
    if ready:
        # The component preserves the last fresh event of each kind for status:
        # an earlier reversal warning outranks a later continuation or sweep.
        if fresh_choch_direction is not None:
            return f"Watching — CHoCH {direction_name(fresh_choch_direction)}, structure may be reversing"
        if fresh_bos_direction is not None:
            return f"Watching — BOS {direction_name(fresh_bos_direction)} confirmed, trend continuing"
        if event_kind == CHOCH and bars_since_event <= STATUS_FRESH_BARS:
            return f"Watching — CHoCH {direction_name(event_direction)}, structure may be reversing"
        if event_kind == BOS and bars_since_event <= STATUS_FRESH_BARS:
            return f"Watching — BOS {direction_name(event_direction)} confirmed, trend continuing"
        if last_sweep_side and bars_since_sweep <= STATUS_FRESH_BARS:
            where = "above" if last_sweep_side == BUY_SIDE else "below"
            return f"Watching — Liquidity swept {where}, no structure break"
        return ROW10_STRUCTURE
    if supertrend_ready:
        return "Watching — Supertrend context only, no signal yet"
    return phase2_status


# Small replay tracker --------------------------------------------------------

class SmcTracker:
    """Closed-bar lifecycle reference used for replay/determinism tests.

    It mirrors the production ordering: existing zones first, close-only
    structure events, wick-only sweeps, confirmed pivots, pools, then new OBs
    and FVGs.  The tracker deliberately accepts a series array and an index so
    index 0 is never a forming bar in either implementation.
    """

    def __init__(self, asset_class: str = "Forex Major", volatility: str = NORMAL, timeframe: str = "M5") -> None:
        self.asset_class = asset_class
        self.volatility = volatility
        self.timeframe = timeframe
        self.state = SmcState(resolve_parameters(asset_class, volatility, timeframe), asset_class, volatility)

    def _inside(self, swing: Swing, sequence: int) -> bool:
        return sequence - swing.sequence < self.state.params.structure_window

    def _trim_swings(self, sequence: int) -> None:
        self.state.swings = [s for s in self.state.swings if self._inside(s, sequence)][-MAX_SWINGS:]

    def _tracked(self, high: bool, sequence: int) -> Optional[Swing]:
        candidates = [s for s in self.state.swings if s.high == high and not s.consumed and self._inside(s, sequence)]
        return max(candidates, key=lambda s: s.sequence) if candidates else None

    def _record_sweep(self, side: str, level: float, bar: Bar, sequence: int) -> None:
        self.state.last_sweep_side = side
        self.state.last_sweep_level = level
        self.state.sweep_sequence = sequence
        self.state.sweep_time = bar.time

    def _update_zones(self, bar: Bar) -> None:
        for block in self.state.blocks:
            if update_block(block, bar) == "mitigated":
                self.state.mitigated_block_count += 1
        for gap in self.state.gaps:
            update_gap(gap, bar)

    def _event_and_sweep(self, bar: Bar, sequence: int, allow_event: bool) -> None:
        high, low = self._tracked(True, sequence), self._tracked(False, sequence)
        if allow_event and high is not None and low is not None:
            if bar.close > high.level:
                self.state.event_kind = CHOCH if self.state.bias < 0 else BOS
                self.state.event_direction = 1
                self.state.event_sequence = sequence
                self.state.event_time = bar.time
                self.state.bias = 1
                high.consumed = True
            elif bar.close < low.level:
                self.state.event_kind = CHOCH if self.state.bias > 0 else BOS
                self.state.event_direction = -1
                self.state.event_sequence = sequence
                self.state.event_time = bar.time
                self.state.bias = -1
                low.consumed = True
        high, low = self._tracked(True, sequence), self._tracked(False, sequence)
        if high and not high.swept and bar.high > high.level and bar.close <= high.level:
            high.swept = True
            self._record_sweep(BUY_SIDE, high.level, bar, sequence)
        elif low and not low.swept and bar.low < low.level and bar.close >= low.level:
            low.swept = True
            self._record_sweep(SELL_SIDE, low.level, bar, sequence)
        else:
            for pool in self.state.pools:
                if pool.swept:
                    continue
                if pool.high and bar.high > pool.level and bar.close <= pool.level:
                    pool.swept = True
                    self._record_sweep(BUY_SIDE, pool.level, bar, sequence)
                    break
                if not pool.high and bar.low < pool.level and bar.close >= pool.level:
                    pool.swept = True
                    self._record_sweep(SELL_SIDE, pool.level, bar, sequence)
                    break

    def _add_pivot(self, rates: Sequence[Bar], index: int, sequence: int) -> None:
        hp = pivot_at(rates, index, self.state.params.swing_strength, True)
        lp = pivot_at(rates, index, self.state.params.swing_strength, False)
        if hp is not None and lp is not None:
            return
        picked = hp if hp is not None else lp
        if picked is None:
            return
        pivot, level = picked
        high = hp is not None
        time = rates[pivot].time
        if not any(s.high == high and s.time == time for s in self.state.swings):
            age = pivot - index
            self.state.swings.append(Swing(high, level, time, sequence - age, age))

    def _rebuild_pools(self, sequence: int) -> None:
        prior = {(pool.high, round(pool.level, 12)): pool for pool in self.state.pools}
        pools = pools_from_swings([s for s in self.state.swings if self._inside(s, sequence)], self.state.atr_value)
        for pool in pools:
            old = prior.get((pool.high, round(pool.level, 12)))
            if old is not None:
                pool.swept = old.swept
        self.state.pools = pools

    def _discover(self, rates: Sequence[Bar], index: int, sequence: int) -> None:
        for bullish in (True, False):
            result = newest_order_block_candidate(rates, index, self.state.params.ob_lookback, self.state.params.body_period, bullish)
            if result is not None:
                candidate, low, high, ratio = result
                origin = rates[candidate]
                if not any(block.bullish == bullish and block.origin_time == origin.time for block in self.state.blocks):
                    same = [block for block in self.state.blocks if block.active and block.bullish == bullish]
                    if len(same) >= MAX_ZONES:
                        oldest = min(same, key=lambda block: block.origin_sequence)
                        self.state.blocks.remove(oldest)
                    self.state.blocks.append(OrderBlock(bullish, low, high, origin.time, sequence - (candidate - index), sequence, ratio))
        found = fair_value_gap(rates, index)
        if found is not None:
            bullish, low, high = found
            origin = rates[index]
            if not any(gap.bullish == bullish and gap.origin_time == origin.time for gap in self.state.gaps):
                active = [gap for gap in self.state.gaps if gap.active]
                if len(active) >= MAX_ZONES:
                    self.state.gaps.remove(min(active, key=lambda gap: gap.origin_sequence))
                self.state.gaps.append(Gap(bullish, low, high, origin.time, sequence, sequence))

    def _publish(self, close: float, sequence: int) -> None:
        self.state._current_sequence = sequence
        zone, leg, low, high, eq, position = dealing_zone(self.state.swings, close, self.state.atr_value)
        self.state.zone, self.state.leg_direction = zone, leg
        self.state.range_low, self.state.range_high = low, high
        self.state.equilibrium, self.state.zone_position = eq, position
        block, distance = select_order_block(self.state.blocks, self.state.bias, close, self.state.atr_value)
        self.state.order_block, self.state.distance_to_ob_atrs = block, distance
        self.state.has_order_block = block is not None
        up, down, up_distance, down_distance = select_gaps(self.state.gaps, close, self.state.atr_value)
        self.state.gap_above, self.state.gap_below = up, down
        self.state.gap_distance_atrs = up_distance if self.state.bias > 0 else down_distance if self.state.bias < 0 else 0.0
        has_high = any(s.high and self._inside(s, sequence) for s in self.state.swings)
        has_low = any(not s.high and self._inside(s, sequence) for s in self.state.swings)
        self.state.ready = has_high and has_low and self.state.atr_value > 0.0
        self.state.score = smc_score(
            bias=self.state.bias,
            event_kind=self.state.event_kind,
            event_direction=self.state.event_direction,
            bars_since_event=self.state.bars_since_event,
            zone=self.state.zone,
            has_order_block=self.state.has_order_block,
            distance_to_ob_atrs=self.state.distance_to_ob_atrs,
            last_sweep_side=self.state.last_sweep_side,
            bars_since_sweep=self.state.bars_since_sweep,
        ) if self.state.ready else 0.0

    def advance(self, rates: Sequence[Bar], atrs: Sequence[float], index: int, sequence: int, force_first: bool = False) -> bool:
        if index < 0 or index >= len(rates) or index >= len(atrs) or atrs[index] <= 0.0:
            return False
        self.state.atr_value = atrs[index]
        self._trim_swings(sequence)
        self._update_zones(rates[index])
        self._event_and_sweep(rates[index], sequence, self.state.initialized and not force_first)
        self._add_pivot(rates, index, sequence)
        self._trim_swings(sequence)
        self._rebuild_pools(sequence)
        self._discover(rates, index, sequence)
        self._publish(rates[index].close, sequence)
        self.state.initialized = True
        return True

    def change_context(self, asset_class: str, volatility: str, timeframe: str, sequence: int) -> bool:
        """Model the four atomic parameters and their existing two-bar pause."""
        desired = resolve_parameters(asset_class, volatility, timeframe)
        old = self.state.params
        changed = desired != old
        if not changed:
            self.asset_class, self.volatility, self.timeframe = asset_class, volatility, timeframe
            return False
        checks = (
            (desired.structure_window == old.structure_window or can_change_at(sequence, self.state.last_window_change)),
            (desired.swing_strength == old.swing_strength or can_change_at(sequence, self.state.last_strength_change)),
            (desired.body_period == old.body_period or can_change_at(sequence, self.state.last_body_change)),
            (desired.ob_lookback == old.ob_lookback or can_change_at(sequence, self.state.last_ob_change)),
        )
        if not all(checks):
            return False
        self.state.params = desired
        self.asset_class, self.volatility, self.timeframe = asset_class, volatility, timeframe
        if desired.structure_window != old.structure_window:
            self.state.last_window_change = sequence
        if desired.swing_strength != old.swing_strength:
            self.state.last_strength_change = sequence
        if desired.body_period != old.body_period:
            self.state.last_body_change = sequence
        if desired.ob_lookback != old.ob_lookback:
            self.state.last_ob_change = sequence
        return True


def replay(
    rates: Sequence[Bar], atrs: Sequence[float], asset_class: str = "Forex Major", volatility: str = NORMAL, timeframe: str = "M5"
) -> SmcState:
    """Replay a complete series in chronological order, exactly once per bar."""
    tracker = SmcTracker(asset_class, volatility, timeframe)
    sequence = 0
    for index in range(len(rates) - 1, -1, -1):
        tracker.advance(rates, atrs, index, sequence)
        sequence += 1
    return tracker.state
