"""Portable reference functions for Emtt Phase 6's pure decision logic.

Mirrors ``Include/Emtt/Emtt_Signal.mqh`` and ``Include/Emtt/Emtt_TradePlan.mqh``
(Emtt.md 17.2-17.8) with no MT5 dependency, so CI exercises the confidence
combination, the signal gate, the plan builder, the plan lifecycle, the
journal lines and the panel text on every platform. The journal lines are
captured as strings instead of ``PrintFormat``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from phase2_reference import BEAR, BULL, CLOSED, RANGING, TRANSITION, VOLATILE

#--- 17.3 / 17.5 the confidence rows -----------------------------------
SIG_WEIGHT_TREND = 0.30
SIG_WEIGHT_STRUCTURE = 0.30
SIG_WEIGHT_FLOW = 0.20
SIG_WEIGHT_HTF = 0.20
SIG_STAY_MARGIN = 5

#--- 17.5 the trade-plan rows ------------------------------------------
PLAN_STOP_BUFFER_ATR = 0.5
PLAN_STOP_MIN_ATR = 1.0
PLAN_STOP_MAX_ATR = 3.0
PLAN_ENTRY_REACH_ATR = 2.0
PLAN_SPEED_FLOOR = 0.2
PLAN_DURATION_LOW = 0.5
PLAN_DURATION_HIGH = 1.5
PLAN_RR_TREND = 1.5
PLAN_RR_OTHER = 2.0

SIDE_BUY = 1
SIDE_SELL = -1

ENTRY_MARKET = "market"
ENTRY_BLOCK = "block"

PLAN_PENDING = "pending"
PLAN_ACTIVE = "active"

WAIT_NONE = ""
WAIT_BELOW_BAR = "below_bar"
WAIT_BELOW_KEEP = "below_keep"
WAIT_NO_TARGET = "no_target"
WAIT_STOP_FAR = "stop_far"
WAIT_NO_SWING = "no_swing"
WAIT_JUST_ENDED = "just_ended"

FAIL_NONE = ""
FAIL_NO_SWING = "no_swing"
FAIL_STOP_FAR = "stop_far"
FAIL_NO_TARGET = "no_target"

RESULT_NONE = ""
RESULT_TARGET = "target reached"
RESULT_STOP = "stop reached"
RESULT_MISSED = "missed"
RESULT_CANCELLED = "cancelled"
RESULT_SIGNAL = "signal changed"
RESULT_CLOSED = "market closed"
RESULT_CHART = "chart changed"

TIMEFRAME_MINUTES = {"M5": 5, "M15": 15, "M30": 30}

# Panel glyphs (17.6): the pause glyph of the Phase 1 mock-up is not in
# Segoe UI, so WAIT shows a black square.
BUY_GLYPH = "\u25b2"    # ▲
SELL_GLYPH = "\u25bc"   # ▼
WAIT_GLYPH = "\u25a0"   # ■
ARROW_GLYPH = "\u25ba"  # ►
DASH = "\u2014"         # —

RESULT_NAMES = {
    RESULT_TARGET: "target reached",
    RESULT_STOP: "stop reached",
    RESULT_MISSED: "missed",
    RESULT_CANCELLED: "cancelled",
    RESULT_SIGNAL: "signal changed",
    RESULT_CLOSED: "market closed",
    RESULT_CHART: "chart changed",
}


def round_half_up(value: float) -> int:
    """MQL5 MathRound semantics for the positive values used here."""
    return math.floor(value + 0.5)


def fmt1(value: float) -> str:
    """One decimal, halves away from zero - MQL5 DoubleToString(x, 1)."""
    return f"{round_half_up(value * 10) / 10:.1f}"


def fmt_time(bar_time: datetime) -> str:
    """TimeToString(bar_time, TIME_DATE | TIME_MINUTES)."""
    return bar_time.strftime("%Y.%m.%d %H:%M")


@dataclass(frozen=True)
class Candle:
    """The newly closed bar the signal engine reads (never the forming one)."""

    high: float
    low: float
    close: float


@dataclass(frozen=True)
class TrendView:
    """The published Supertrend reading (11.6)."""

    ready: bool = False
    direction: int = 0
    score: float = 0.0
    bars_since_flip: int = 0
    distance_atrs: float = 0.0


@dataclass(frozen=True)
class StructureView:
    """The published SMC readings used by the plan (13.9)."""

    ready: bool = False
    bias: int = 0
    score: float = 0.0
    has_order_block: bool = False
    order_block_bullish: bool = True
    order_block_near_edge: float = 0.0
    order_block_low: float = 0.0
    order_block_high: float = 0.0
    has_swing_low: bool = False
    newest_low_level: float = 0.0
    has_swing_high: bool = False
    newest_high_level: float = 0.0
    has_gap_above: bool = False
    gap_above_near_edge: float = 0.0
    has_gap_below: bool = False
    gap_below_near_edge: float = 0.0
    has_buy_pool: bool = False
    buy_pool_level: float = 0.0
    has_sell_pool: bool = False
    sell_pool_level: float = 0.0


@dataclass(frozen=True)
class FlowView:
    """The published volume-flow readings used by the plan (15.7)."""

    ready: bool = False
    flow_direction: int = 0
    score: float = 0.0
    has_profile: bool = False
    poc: float = 0.0
    vah: float = 0.0
    val: float = 0.0
    prior_poc_available: bool = False
    prior_poc_naked: bool = False
    prior_poc: float = 0.0


@dataclass(frozen=True)
class HtfView:
    """The published higher-chart reading (15.9)."""

    ready: bool = False
    direction: int = 0
    score: float = 0.0


#--- 17.3 the four-view combination ------------------------------------


def views_ready(trend: TrendView, structure: StructureView,
                flow: FlowView, htf: HtfView) -> bool:
    return trend.ready and structure.ready and flow.ready and htf.ready


def combine_views(trend: TrendView, structure: StructureView,
                  flow: FlowView, htf: HtfView) -> float:
    """S = sum(w x s x d); a flat view (d = 0) adds nothing."""
    return (
        SIG_WEIGHT_TREND * trend.score * trend.direction
        + SIG_WEIGHT_STRUCTURE * structure.score * structure.bias
        + SIG_WEIGHT_FLOW * flow.score * flow.flow_direction
        + SIG_WEIGHT_HTF * htf.score * htf.direction
    )


def confidence_number(combined: float) -> int:
    """Row 3: round(100 x |S|), halves rounded up."""
    return round_half_up(100.0 * abs(combined))


def mood_bar(mood: str) -> int:
    """The 9.2.4 bar, read from the mood of 17.2 rule 3."""
    if mood in (BULL, BEAR):
        return 60
    if mood in (RANGING, VOLATILE):
        return 70
    if mood == TRANSITION:
        return 75
    return 0


def mood_word(mood: str) -> str:
    if mood in (BULL, BEAR):
        return "Trending"
    if mood == RANGING:
        return "Ranging"
    if mood == VOLATILE:
        return "Volatile"
    if mood == TRANSITION:
        return "Transition"
    return "--"


def side_name(side: int) -> str:
    return "BUY" if side > 0 else "SELL"


def min_risk_reward(mood: str) -> float:
    """17.5 row g: 1.5 in a clear trend, 2.0 in the other moods."""
    if mood in (BULL, BEAR):
        return PLAN_RR_TREND
    return PLAN_RR_OTHER


#--- 17.4 the trade plan ------------------------------------------------


@dataclass
class Plan:
    active: bool = False
    side: int = 0
    entry_kind: str = ENTRY_MARKET
    status: str = PLAN_PENDING
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    risk_reward: float = 0.0
    entry_source: str = ""
    stop_source: str = ""
    target_source: str = ""
    duration: str = ""
    start_sequence: int = -1
    start_bar_time: Optional[datetime] = None
    start_close: float = 0.0


def plan_reset() -> Plan:
    return Plan()


def format_duration(candles: float, timeframe: str) -> str:
    """The 0.5x-1.5x band: minutes under 2 hours, hours to 3 days."""
    minutes_per_candle = TIMEFRAME_MINUTES.get(timeframe, 0)
    if minutes_per_candle <= 0 or not candles > 0:
        return "--"
    minutes = candles * minutes_per_candle
    if minutes < 120.0:
        low = round_half_up(PLAN_DURATION_LOW * minutes / 5.0) * 5
        high = round_half_up(PLAN_DURATION_HIGH * minutes / 5.0) * 5
        return f"~{low}-{high} min"
    if minutes <= 4320.0:
        hours = minutes / 60.0
        low = round_half_up(PLAN_DURATION_LOW * hours)
        high = round_half_up(PLAN_DURATION_HIGH * hours)
        return f"~{low}-{high} hours"
    return "> 3 days"


def build_plan(
    side: int,
    structure: StructureView,
    flow: FlowView,
    trend: TrendView,
    atr: float,
    close: float,
    bid: float,
    ask: float,
    mood: str,
    timeframe: str,
) -> tuple[Optional[Plan], str]:
    """The 17.4 plan builder. Returns (plan, fail); plan is None on skip."""
    plan = plan_reset()
    fail = FAIL_NONE
    if side not in (SIDE_BUY, SIDE_SELL):
        return None, fail
    if not atr > 0 or close != close or bid != bid or ask != ask:
        return None, fail

    dealing = ask if side > 0 else bid
    min_rr = min_risk_reward(mood)

    # Entry: the same-way order block's near edge within (0, 2.0] ATR of
    # the close, otherwise the dealing price read at the evaluation.
    plan.entry = dealing
    plan.entry_kind = ENTRY_MARKET
    plan.entry_source = "market price"
    block_far_edge = 0.0
    if (
        structure.has_order_block
        and structure.bias == side
        and structure.order_block_bullish == (side > 0)
    ):
        reach = (
            close - structure.order_block_near_edge
            if side > 0
            else structure.order_block_near_edge - close
        )
        if 0.0 < reach <= PLAN_ENTRY_REACH_ATR * atr:
            plan.entry = structure.order_block_near_edge
            plan.entry_kind = ENTRY_BLOCK
            plan.entry_source = "order block edge"
            block_far_edge = (
                structure.order_block_low if side > 0 else structure.order_block_high
            )

    # Stop: the further of the newest confirmed turning point and the
    # block's far edge, plus 0.5 ATR, widened to 1.0 ATR, skipped past 3.0.
    reference = 0.0
    has_reference = False
    stop_source = ""
    if structure.has_swing_low if side > 0 else structure.has_swing_high:
        swing_level = (
            structure.newest_low_level if side > 0 else structure.newest_high_level
        )
        if swing_level < plan.entry if side > 0 else swing_level > plan.entry:
            reference = swing_level
            has_reference = True
            stop_source = "swing low" if side > 0 else "swing high"
    if (
        plan.entry_kind == ENTRY_BLOCK
        and block_far_edge != 0.0
        and (block_far_edge < plan.entry if side > 0 else block_far_edge > plan.entry)
        and (
            not has_reference
            or (block_far_edge < reference if side > 0 else block_far_edge > reference)
        )
    ):
        reference = block_far_edge
        has_reference = True
        stop_source = "order block edge"
    if not has_reference:
        return None, FAIL_NO_SWING
    plan.stop = reference + (
        -PLAN_STOP_BUFFER_ATR * atr if side > 0 else PLAN_STOP_BUFFER_ATR * atr
    )
    if abs(plan.entry - plan.stop) < PLAN_STOP_MIN_ATR * atr:
        plan.stop = plan.entry + (
            -PLAN_STOP_MIN_ATR * atr if side > 0 else PLAN_STOP_MIN_ATR * atr
        )
    if abs(plan.entry - plan.stop) > PLAN_STOP_MAX_ATR * atr:
        return None, FAIL_STOP_FAR
    plan.stop_source = stop_source

    # Target: the nearest same-side candidate giving at least the minimum
    # Risk:Reward. Equal prices keep the 17.4 order.
    candidates: list[tuple[float, int, str]] = []
    if structure.has_gap_above if side > 0 else structure.has_gap_below:
        candidates.append(
            (
                structure.gap_above_near_edge
                if side > 0
                else structure.gap_below_near_edge,
                0,
                "fair value gap",
            )
        )
    if structure.has_buy_pool if side > 0 else structure.has_sell_pool:
        candidates.append(
            (
                structure.buy_pool_level if side > 0 else structure.sell_pool_level,
                1,
                "buy-side pool" if side > 0 else "sell-side pool",
            )
        )
    if flow.has_profile:
        candidates.append((flow.poc, 2, "POC"))
        candidates.append((flow.vah, 3, "VAH"))
        candidates.append((flow.val, 4, "VAL"))
    if flow.prior_poc_available and flow.prior_poc_naked:
        candidates.append((flow.prior_poc, 5, "naked POC"))

    found = False
    best_price = best_distance = best_rr = 0.0
    best_priority = 0
    best_source = ""
    for price, priority, source in candidates:
        if not (price > plan.entry if side > 0 else price < plan.entry):
            continue
        rr = (
            (price - plan.entry) / (plan.entry - plan.stop)
            if side > 0
            else (plan.entry - price) / (plan.stop - plan.entry)
        )
        if rr < min_rr:
            continue
        distance = abs(price - plan.entry)
        if (
            not found
            or distance < best_distance
            or (distance == best_distance and priority < best_priority)
        ):
            found = True
            best_price = price
            best_distance = distance
            best_priority = priority
            best_rr = rr
            best_source = source
    if not found:
        return None, FAIL_NO_TARGET
    plan.target = best_price
    plan.risk_reward = best_rr
    plan.target_source = best_source

    # Expected Duration: Supertrend speed (ATR per candle), floored, banded.
    speed = 0.0
    if trend.direction == side and trend.bars_since_flip > 0:
        speed = trend.distance_atrs / trend.bars_since_flip
    if speed < PLAN_SPEED_FLOOR:
        speed = PLAN_SPEED_FLOOR
    candles = (abs(plan.target - plan.entry) / atr) / speed
    plan.duration = format_duration(candles, timeframe)

    plan.side = side
    plan.status = PLAN_ACTIVE if plan.entry_kind == ENTRY_MARKET else PLAN_PENDING
    plan.active = True
    return plan, fail


#--- 17.6 / 17.8 the Row 10 text ----------------------------------------


def wait_bare(state: "SignalState") -> str:
    if state.wait_reason == WAIT_BELOW_BAR:
        return f"below the {state.mood_bar}% bar"
    if state.wait_reason == WAIT_BELOW_KEEP:
        return (
            f"below the {state.mood_bar - SIG_STAY_MARGIN}% level that keeps a "
            f"{side_name(state.wait_side)}"
        )
    if state.wait_reason == WAIT_NO_TARGET:
        return f"no target gives 1:{fmt1(min_risk_reward(state.mood))}"
    if state.wait_reason == WAIT_STOP_FAR:
        return f"stop would be more than {fmt1(PLAN_STOP_MAX_ATR)} ATR away"
    if state.wait_reason == WAIT_NO_SWING:
        return "no swing point for the stop yet"
    if state.wait_reason == WAIT_JUST_ENDED:
        return "the last idea just ended; a new one can start on the next candle"
    return ""


def wait_text(state: "SignalState") -> str:
    """The full 17.6 WAIT line of Row 10."""
    if state.confidence < 0:
        return ""
    number = f"{state.confidence}%"
    if state.wait_reason == WAIT_BELOW_BAR:
        return f"Watching {DASH} confidence {number}, below the {state.mood_bar}% bar."
    if state.wait_reason == WAIT_BELOW_KEEP:
        return (
            f"Watching {DASH} confidence {number}, below the "
            f"{state.mood_bar - SIG_STAY_MARGIN}% level that keeps a "
            f"{side_name(state.wait_side)}."
        )
    if state.wait_reason == WAIT_NO_TARGET:
        return (
            f"Watching {DASH} confidence {number}, but no target gives "
            f"1:{fmt1(min_risk_reward(state.mood))} yet."
        )
    if state.wait_reason == WAIT_STOP_FAR:
        return (
            f"Watching {DASH} confidence {number}, but the stop would be more "
            f"than {fmt1(PLAN_STOP_MAX_ATR)} ATR away."
        )
    if state.wait_reason == WAIT_NO_SWING:
        return f"Watching {DASH} confidence {number}, but no swing point for the stop yet."
    if state.wait_reason == WAIT_JUST_ENDED:
        return (
            f"Watching {DASH} the last idea just ended; a new one can start on "
            f"the next candle."
        )
    return ""


def wait_detail(state: "SignalState") -> str:
    """The detail of the journal's "Signal WAIT" line (17.8)."""
    if state.wait_reason == WAIT_JUST_ENDED:
        return wait_bare(state)
    return f"confidence {state.confidence}%, {wait_bare(state)}"


def status_text(state: "SignalState", bid: float, ask: float) -> str:
    """Row 10 while the four views are ready (17.6)."""
    if state.plan.active and state.signal != 0:
        side = state.signal
        stop_passed = bid <= state.plan.stop if side > 0 else ask >= state.plan.stop
        target_passed = (
            ask >= state.plan.target if side > 0 else bid <= state.plan.target
        )
        if stop_passed:
            return f"Stop level passed {DASH} signal updates at this candle's close."
        if target_passed:
            return f"Target level passed {DASH} signal updates at this candle's close."
        if state.plan.status == PLAN_PENDING:
            return f"Signal active {DASH} waiting for price to reach entry. No order placed."
        return f"Signal active {DASH} price reached entry. No order placed."
    return wait_text(state)


#--- 17.6 the panel rows -------------------------------------------------

DASH_ROWS = {
    "signal": "SIGNAL: --",
    "confidence": "Confidence: --",
    "entry": "Entry: -- / --  (-- pts away)",
    "stop_loss": "Stop Loss: -- / --  (-- pts)",
    "take_profit": "Take Profit: -- / --  (-- pts)",
    "risk_reward": "Risk:Reward: --",
}


def panel_rows(
    state: "SignalState",
    *,
    bid: float,
    ask: float,
    point: float,
    digits: int,
    session: str,
) -> dict:
    """The EA's FillPanel Phase 6 rows (17.6).

    ``status`` is None while the four views are not all ready: the Phase 3-5
    event lines own Row 10 then. ``session_suffix`` is the part after
    "Session: <name> | Expected Duration:".
    """
    rows = dict(DASH_ROWS)
    rows["session_suffix"] = ""
    rows["status"] = None
    if not state.views_ready:
        return rows
    plan_showing = state.plan.active and state.signal != 0
    if plan_showing:
        rows["session_suffix"] = " " + state.plan.duration
    else:
        rows["session_suffix"] = " --"
    if state.signal > 0:
        rows["signal"] = f"SIGNAL: {BUY_GLYPH} BUY"
    elif state.signal < 0:
        rows["signal"] = f"SIGNAL: {SELL_GLYPH} SELL"
    else:
        rows["signal"] = f"SIGNAL: {WAIT_GLYPH} WAIT"
    rows["confidence"] = f"Confidence: {state.confidence}%"
    if plan_showing:
        dealing = ask if state.signal > 0 else bid
        entry_pts = round_half_up(abs(dealing - state.plan.entry) / point) if point > 0 else 0
        stop_pts = (
            round_half_up(abs(state.plan.entry - state.plan.stop) / point)
            if point > 0
            else 0
        )
        target_pts = (
            round_half_up(abs(state.plan.target - state.plan.entry) / point)
            if point > 0
            else 0
        )
        rows["entry"] = (
            f"Entry: {state.plan.entry:.{digits}f} / --  ({entry_pts} pts away)"
        )
        rows["stop_loss"] = (
            f"Stop Loss: {state.plan.stop:.{digits}f} / --  ({stop_pts} pts)"
        )
        rows["take_profit"] = (
            f"Take Profit: {state.plan.target:.{digits}f} / --  ({target_pts} pts)"
        )
        rows["risk_reward"] = f"Risk:Reward: 1:{fmt1(state.plan.risk_reward)}"
    rows["status"] = status_text(state, bid, ask)
    return rows


def price_row(
    state: "SignalState",
    *,
    bid: float,
    ask: float,
    spread_pts: int,
    digits: int,
) -> str:
    """Rule 2 / 17.6: the arrow marks the dealing side, WAIT has none."""
    plan_showing = state.views_ready and state.plan.active and state.signal != 0
    if plan_showing and state.signal > 0:
        return (
            f"Bid: {bid:.{digits}f}  |  {ARROW_GLYPH}Ask: {ask:.{digits}f}  |  "
            f"Spread: {spread_pts} pts"
        )
    if plan_showing and state.signal < 0:
        return (
            f"{ARROW_GLYPH}Bid: {bid:.{digits}f}  |  Ask: {ask:.{digits}f}  |  "
            f"Spread: {spread_pts} pts"
        )
    return f"Bid: {bid:.{digits}f}  |  Ask: {ask:.{digits}f}  |  Spread: {spread_pts} pts"


#--- 17.7 / 17.8 the signal state and lifecycle --------------------------


@dataclass
class SignalState:
    initialized: bool = False
    views_ready: bool = False
    combined: float = 0.0
    confidence: int = -1
    mood: str = "UNKNOWN"
    mood_bar: int = 0
    signal: int = 0
    previous_signal: int = 0
    just_ended: bool = False
    wait_reason: str = WAIT_NONE
    wait_side: int = 0
    plan: Plan = field(default_factory=Plan)
    last_close: float = 0.0
    last_bar_time: Optional[datetime] = None
    last_sequence: int = -1
    digits: int = 0
    point: float = 0.0
    has_journaled_signal: bool = False
    journaled_signal: int = 0
    has_journaled_wait: bool = False
    journaled_wait_reason: str = WAIT_NONE
    journal: list = field(default_factory=list)


def signal_reset() -> SignalState:
    return SignalState()


class SignalTracker:
    """A portable twin of ``EmttSignalAdvance`` and the plan lifecycle."""

    def __init__(self) -> None:
        self.state = signal_reset()

    #--- journal helpers -------------------------------------------------
    def _journal(self, line: str, journaling: bool) -> None:
        if journaling:
            self.state.journal.append(line)

    def _journal_result(
        self,
        result: str,
        exit_price: float,
        end_sequence: int,
        bar_time: datetime,
        shared: bool,
        journaling: bool,
    ) -> None:
        state = self.state
        if not journaling or not state.plan.active:
            return
        side = state.plan.side
        points = (
            (exit_price - state.plan.entry if side > 0 else state.plan.entry - exit_price)
            / state.point
            if state.point > 0
            else 0.0
        )
        points_whole = round_half_up(points) if points >= 0 else -round_half_up(-points)
        sign = "+" if points_whole >= 0 else "-"
        candles = max(0, end_sequence - state.plan.start_sequence)
        self._journal(
            f"Emtt | Plan {side_name(side)} result | {RESULT_NAMES[result]} | "
            f"exit {exit_price:.{state.digits}f} | {sign}{abs(points_whole)} pts | "
            f"{candles} candles{' | shared candle' if shared else ''} | "
            f"bar {fmt_time(bar_time)}",
            journaling,
        )

    def _end_plan(
        self,
        result: str,
        exit_price: float,
        end_sequence: int,
        bar_time: datetime,
        shared: bool,
        journaling: bool,
    ) -> None:
        state = self.state
        if not state.plan.active:
            return
        side = state.plan.side
        self._journal_result(result, exit_price, end_sequence, bar_time, shared, journaling)
        state.wait_side = side
        state.plan = plan_reset()
        state.signal = 0
        state.just_ended = True

    def _journal_plan_start(self, spread_pts: int, bar_time: datetime,
                            journaling: bool) -> None:
        state = self.state
        if not journaling or not state.plan.active:
            return
        side = state.plan.side
        buffer_text = fmt1(PLAN_STOP_BUFFER_ATR)
        self._journal(
            f"Emtt | Signal {side_name(side)} | confidence {state.confidence}% | "
            f"{mood_word(state.mood)}, bar {state.mood_bar}% | bar {fmt_time(bar_time)}",
            journaling,
        )
        self._journal(
            f"Emtt | Plan {side_name(side)} | confidence {state.confidence}% | "
            f"entry {state.plan.entry:.{state.digits}f} ({state.plan.entry_source}) | "
            f"stop {state.plan.stop:.{state.digits}f} ({state.plan.stop_source} "
            f"{'-' if side > 0 else '+'}{buffer_text} ATR) | "
            f"target {state.plan.target:.{state.digits}f} ({state.plan.target_source}) | "
            f"RR 1:{fmt1(state.plan.risk_reward)} | expected {state.plan.duration} | "
            f"spread {spread_pts} pts | bar {fmt_time(bar_time)}",
            journaling,
        )
        state.has_journaled_signal = True
        state.journaled_signal = state.signal
        state.has_journaled_wait = False
        state.journaled_wait_reason = WAIT_NONE

    #--- the public ends (17.7) -------------------------------------------
    def market_closed(self, journaling: bool = True) -> None:
        """The market closing ends any open plan; not a candle end."""
        state = self.state
        if not state.plan.active:
            return
        self._end_plan(
            RESULT_CLOSED,
            state.last_close,
            state.last_sequence,
            state.last_bar_time,
            False,
            journaling,
        )
        state.signal = 0
        state.previous_signal = 0
        state.just_ended = False
        state.wait_reason = WAIT_NONE
        state.wait_side = 0
        state.has_journaled_signal = False
        state.journaled_signal = 0
        state.has_journaled_wait = False
        state.journaled_wait_reason = WAIT_NONE

    def chart_changed(self, journaling: bool = True) -> None:
        """A symbol or timeframe change ends any open plan (17.7)."""
        state = self.state
        if not state.plan.active:
            return
        self._end_plan(
            RESULT_CHART,
            state.last_close,
            state.last_sequence,
            state.last_bar_time,
            False,
            journaling,
        )
        state.signal = 0
        state.previous_signal = 0
        state.just_ended = False
        state.wait_reason = WAIT_NONE
        state.wait_side = 0
        state.has_journaled_signal = False
        state.journaled_signal = 0
        state.has_journaled_wait = False
        state.journaled_wait_reason = WAIT_NONE

    #--- one closed candle (17.3, 17.6, 17.7) -------------------------------
    def advance(
        self,
        *,
        trend: TrendView,
        structure: StructureView,
        flow: FlowView,
        htf: HtfView,
        mood: str,
        atr: float,
        candle: Candle,
        bid: float,
        ask: float,
        spread_pts: int = 0,
        timeframe: str = "M15",
        sequence: int = 0,
        bar_time: Optional[datetime] = None,
        digits: int = 5,
        point: float = 0.00001,
        journaling: bool = True,
    ) -> None:
        state = self.state
        state.initialized = True
        state.last_close = candle.close
        state.last_bar_time = bar_time
        state.last_sequence = sequence
        state.digits = digits
        state.point = point
        state.mood = mood
        state.mood_bar = mood_bar(mood)
        state.just_ended = False

        ready = (
            views_ready(trend, structure, flow, htf)
            and state.mood_bar > 0
            and atr > 0
        )
        if not ready:
            state.views_ready = False
            state.combined = 0.0
            state.confidence = -1
            state.signal = 0
            state.previous_signal = 0
            state.wait_reason = WAIT_NONE
            state.wait_side = 0
            state.plan = plan_reset()
            state.has_journaled_signal = False
            state.journaled_signal = 0
            state.has_journaled_wait = False
            state.journaled_wait_reason = WAIT_NONE
            return
        state.views_ready = True
        state.combined = combine_views(trend, structure, flow, htf)
        state.confidence = confidence_number(state.combined)
        number = state.confidence
        bar_level = state.mood_bar
        keep_level = bar_level - SIG_STAY_MARGIN
        was_showing = state.previous_signal != 0

        #--- plan lifecycle: the newly closed candle against the levels
        if state.plan.active:
            touches_entry = candle.low <= state.plan.entry <= candle.high
            touches_stop = candle.low <= state.plan.stop <= candle.high
            touches_target = candle.low <= state.plan.target <= candle.high
            touched = (
                (1 if touches_entry else 0)
                + (1 if touches_stop else 0)
                + (1 if touches_target else 0)
            )
            shared = touched > 1
            if state.plan.status == PLAN_PENDING:
                if touches_stop:
                    self._end_plan(
                        RESULT_STOP if touches_entry else RESULT_CANCELLED,
                        state.plan.stop,
                        sequence,
                        bar_time,
                        shared,
                        journaling,
                    )
                elif touches_target:
                    self._end_plan(
                        RESULT_MISSED,
                        state.plan.target,
                        sequence,
                        bar_time,
                        shared,
                        journaling,
                    )
                elif touches_entry:
                    state.plan.status = PLAN_ACTIVE
                    self._journal(
                        f"Emtt | Plan {side_name(state.plan.side)} | entry reached | "
                        f"{state.plan.entry:.{state.digits}f} | bar {fmt_time(bar_time)}",
                        journaling,
                    )
            else:
                if touches_stop:
                    self._end_plan(
                        RESULT_STOP,
                        state.plan.stop,
                        sequence,
                        bar_time,
                        shared,
                        journaling,
                    )
                elif touches_target:
                    self._end_plan(
                        RESULT_TARGET,
                        state.plan.target,
                        sequence,
                        bar_time,
                        shared,
                        journaling,
                    )

        #--- the signal gate, judged on every closed candle
        if state.plan.active:
            side_number = (
                number if state.combined > 0 else 0
                if state.plan.side > 0
                else number if state.combined < 0 else 0
            )
            if side_number >= keep_level:
                state.signal = state.plan.side
                state.wait_reason = WAIT_NONE
                state.wait_side = 0
            else:
                self._end_plan(
                    RESULT_SIGNAL, candle.close, sequence, bar_time, False, journaling
                )
        if not state.plan.active:
            gate_side = (
                SIDE_BUY if state.combined > 0 else SIDE_SELL if state.combined < 0 else 0
            )
            gate_open = gate_side != 0 and number >= bar_level
            fail = FAIL_NONE
            plan: Optional[Plan] = None
            if gate_open:
                plan, fail = build_plan(
                    gate_side, structure, flow, trend, atr, candle.close,
                    bid, ask, mood, timeframe,
                )
            if gate_open and fail == FAIL_NONE and not state.just_ended:
                plan.start_sequence = sequence
                plan.start_bar_time = bar_time
                plan.start_close = candle.close
                state.plan = plan
                state.signal = gate_side
                state.wait_reason = WAIT_NONE
                state.wait_side = 0
                self._journal_plan_start(spread_pts, bar_time, journaling)
            else:
                state.signal = 0
                if was_showing and number < keep_level:
                    state.wait_reason = WAIT_BELOW_KEEP
                    state.wait_side = state.previous_signal
                elif number < bar_level:
                    state.wait_reason = WAIT_BELOW_BAR
                    state.wait_side = 0
                elif fail == FAIL_NO_TARGET:
                    state.wait_reason = WAIT_NO_TARGET
                    state.wait_side = 0
                elif fail == FAIL_STOP_FAR:
                    state.wait_reason = WAIT_STOP_FAR
                    state.wait_side = 0
                elif fail == FAIL_NO_SWING:
                    state.wait_reason = WAIT_NO_SWING
                    state.wait_side = 0
                else:
                    state.wait_reason = WAIT_JUST_ENDED
                    state.wait_side = 0

        #--- journal: state changes, plan events and reason changes only
        if journaling and state.views_ready:
            if not state.has_journaled_signal or state.journaled_signal != state.signal:
                if state.signal != 0:
                    self._journal(
                        f"Emtt | Signal {side_name(state.signal)} | confidence "
                        f"{number}% | {mood_word(mood)}, bar {bar_level}% | "
                        f"bar {fmt_time(bar_time)}",
                        journaling,
                    )
                else:
                    self._journal(
                        f"Emtt | Signal WAIT | {wait_detail(state)} | "
                        f"bar {fmt_time(bar_time)}",
                        journaling,
                    )
                state.has_journaled_signal = True
                state.journaled_signal = state.signal
                if state.signal == 0:
                    state.has_journaled_wait = True
                    state.journaled_wait_reason = state.wait_reason
                else:
                    state.has_journaled_wait = False
                    state.journaled_wait_reason = WAIT_NONE
            elif (
                state.signal == 0
                and state.has_journaled_wait
                and state.journaled_wait_reason != state.wait_reason
            ):
                self._journal(
                    f"Emtt | Signal WAIT | reason changed: {wait_bare(state)} | "
                    f"bar {fmt_time(bar_time)}",
                    journaling,
                )
                state.journaled_wait_reason = state.wait_reason

        state.previous_signal = state.signal
