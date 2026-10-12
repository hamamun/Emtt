"""Portable reference for Emtt Phase 11 (Emtt.md 28): graded confidence tiers.

A line-for-line Python mirror of ``Include/Emtt/Emtt_Tier.mqh`` plus the
places Phase 11 wires it in: the 35% signal gate of ``Emtt_Signal.mqh``, the
Row 2 / Row 3 styling of ``FillPanel``, the threshold gate and tier lot
multiplier of ``Emtt_Trade.mqh`` and the Row 10 precedence of the manager's
gate line. No MT5 dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import phase8_reference as p8

DASH = "\u2014"

DISPLAY_MIN = 35
LOW_MAX = 45
NORMAL_MAX = 55
CONFIDENT_MAX = 70
AUTO_MIN = 35
AUTO_MAX = 100
AUTO_DEFAULT = 56
SIZE_LOW = 0.7
SIZE_NORMAL = 1.0
SIZE_CONFIDENT = 1.2
SIZE_HIGH = 1.5

TIER_NONE = 0
TIER_VERY_LOW = 1
TIER_LOW = 2
TIER_NORMAL = 3
TIER_CONFIDENT = 4
TIER_HIGH = 5

LABELS = {
    TIER_VERY_LOW: "Very low",
    TIER_LOW: "Low confidence",
    TIER_NORMAL: "Normal",
    TIER_CONFIDENT: "Confident",
    TIER_HIGH: "High confidence",
}

# Emtt_Dashboard.mqh palette (RGB).
CLR_TEXT = (200, 200, 200)
CLR_BUY = (111, 207, 151)
CLR_SELL = (235, 111, 111)
CLR_BUY_LOW = (156, 204, 176)
CLR_SELL_LOW = (218, 156, 156)
CLR_BUY_NORMAL = (133, 205, 163)
CLR_SELL_NORMAL = (226, 133, 133)
FSIZE = 12
FSIZE_SIG = 14

GATE_BELOW_THRESHOLD = "below_threshold"

WAIT_NONE = "none"
WAIT_BELOW_BAR = "below_bar"
WAIT_BELOW_KEEP = "below_keep"
WAIT_PLAN_FAIL = "plan_fail"
WAIT_JUST_ENDED = "just_ended"


def tier_of(confidence: int) -> int:
    if confidence < 0:
        return TIER_NONE
    if confidence < DISPLAY_MIN:
        return TIER_VERY_LOW
    if confidence <= LOW_MAX:
        return TIER_LOW
    if confidence <= NORMAL_MAX:
        return TIER_NORMAL
    if confidence <= CONFIDENT_MAX:
        return TIER_CONFIDENT
    return TIER_HIGH


def tier_label(tier: int) -> str:
    return LABELS.get(tier, "")


def shows_direction(confidence: int) -> bool:
    return confidence >= DISPLAY_MIN


def confidence_row(confidence: int) -> str:
    if confidence < 0:
        return "Confidence: --%"
    return f"Confidence: {confidence}% {DASH} {tier_label(tier_of(confidence))}"


def size_multiplier(confidence: int) -> float:
    tier = tier_of(confidence)
    if tier == TIER_HIGH:
        return SIZE_HIGH
    if tier == TIER_CONFIDENT:
        return SIZE_CONFIDENT
    if tier == TIER_NORMAL:
        return SIZE_NORMAL
    return SIZE_LOW


def auto_trade_above(value: int) -> int:
    return max(AUTO_MIN, min(AUTO_MAX, value))


def auto_trade_allowed(confidence: int, threshold: int) -> bool:
    return confidence >= DISPLAY_MIN and confidence >= threshold


def side_name(side: int) -> str:
    return "BUY" if side > 0 else ("SELL" if side < 0 else "WAIT")


def watching_line(confidence: int) -> str:
    return f"Watching {DASH} confidence {confidence}% (Very low), no trade."


def below_threshold_line(confidence: int, side: int, threshold: int) -> str:
    return (f"Signal active {DASH} {tier_label(tier_of(confidence))} {side_name(side)}, "
            f"watching (auto-trade threshold {threshold}%).")


# --- Emtt_Trade.mqh: the ordered gate with the Phase 11 threshold ---------
def gate_first_failure(value: p8.GateInput, confidence: int, threshold: int) -> str:
    if not value.auto_trading:
        return p8.GATE_AUTO_OFF
    if not auto_trade_allowed(confidence, threshold):
        return GATE_BELOW_THRESHOLD
    return p8.gate_first_failure(value)


def gate_status(failure: str, spread_points: int = 0, confidence: int = 0,
                side: int = 0, threshold: int = 0) -> str:
    if failure == GATE_BELOW_THRESHOLD:
        return below_threshold_line(confidence, side, threshold)
    return p8.gate_status(failure, spread_points)


def risk_lots(balance: float, entry: float, stop: float, tick_size: float,
              tick_value: float, confidence: int, news_multiplier: float = 1.0) -> float:
    """p8.risk_lots with the tier multiplier in place of the 60/70/80/90 steps."""
    # Confidence 70 carries the Phase 8 multiplier 1.0, i.e. the bare risk.
    base = p8.risk_lots(balance, entry, stop, tick_size, tick_value, 70, news_multiplier)
    return base * size_multiplier(confidence)


# --- Emtt_Signal.mqh: the 35% enter / keep gate ---------------------------
@dataclass
class SignalState:
    signal: int = 0
    plan_side: int = 0
    plan_active: bool = False
    previous_signal: int = 0
    wait_reason: str = WAIT_NONE
    wait_side: int = 0
    confidence: int = -1
    just_ended: bool = False


def signal_step(state: SignalState, number: int, combined_side: int,
                plan_builds: bool = True) -> SignalState:
    """One closed candle of the display gate (barLevel = keepLevel = 35)."""
    was_showing = state.signal != 0
    state.previous_signal = state.signal
    state.confidence = number
    state.just_ended = False
    if state.plan_active:
        side_number = number if combined_side == state.plan_side else 0
        if side_number >= DISPLAY_MIN:
            state.signal = state.plan_side
            state.wait_reason = WAIT_NONE
            state.wait_side = 0
        else:
            state.plan_active = False
            state.just_ended = True
    if not state.plan_active:
        gate_open = combined_side != 0 and number >= DISPLAY_MIN
        if gate_open and plan_builds and not state.just_ended:
            state.plan_active = True
            state.plan_side = combined_side
            state.signal = combined_side
            state.wait_reason = WAIT_NONE
            state.wait_side = 0
        else:
            state.signal = 0
            if was_showing and number < DISPLAY_MIN:
                state.wait_reason = WAIT_BELOW_KEEP
                state.wait_side = state.previous_signal
            elif number < DISPLAY_MIN:
                state.wait_reason = WAIT_BELOW_BAR
                state.wait_side = 0
            elif state.just_ended:
                state.wait_reason = WAIT_JUST_ENDED
            else:
                state.wait_reason = WAIT_PLAN_FAIL
    return state


def wait_bare(state: SignalState) -> str:
    if state.wait_reason == WAIT_BELOW_BAR:
        return "below the 35% display level (Very low)"
    if state.wait_reason == WAIT_BELOW_KEEP:
        return f"below the 35% level that keeps a {side_name(state.wait_side)} (Very low)"
    return ""


def wait_status(state: SignalState) -> str:
    if state.wait_reason in (WAIT_BELOW_BAR, WAIT_BELOW_KEEP):
        return watching_line(state.confidence)
    return ""


# --- FillPanel: Rows 2-8 --------------------------------------------------
@dataclass
class Panel:
    signal: str = "SIGNAL: --"
    signal_clr: tuple = CLR_TEXT
    signal_size: int = FSIZE
    signal_bold: bool = False
    confidence: str = "Confidence: --%"
    levels: bool = False   # Rows 4-8 carry the plan levels (else "--")


def signal_style(side: int, confidence: int) -> tuple[tuple, int, bool]:
    tier = tier_of(confidence)
    if tier == TIER_LOW:
        clr = CLR_BUY_LOW if side > 0 else CLR_SELL_LOW
    elif tier == TIER_NORMAL:
        clr = CLR_BUY_NORMAL if side > 0 else CLR_SELL_NORMAL
    else:
        clr = CLR_BUY if side > 0 else CLR_SELL
    return clr, FSIZE_SIG, tier == TIER_HIGH


def fill_panel(state: Optional[SignalState], *, compatible: bool = True,
               market_open: bool = True, history_ready: bool = True,
               views_ready: bool = True) -> Panel:
    panel = Panel()
    if not compatible or not market_open or not history_ready or state is None:
        return panel
    if not views_ready:
        return panel
    if state.signal > 0:
        panel.signal = "SIGNAL: \u25B2 BUY"
    elif state.signal < 0:
        panel.signal = "SIGNAL: \u25BC SELL"
    else:
        panel.signal = "SIGNAL: \u25A0 WAIT"
    if state.signal != 0:
        panel.signal_clr, panel.signal_size, panel.signal_bold = signal_style(
            state.signal, state.confidence)
    panel.confidence = confidence_row(state.confidence)
    panel.levels = state.plan_active and state.signal != 0
    return panel


# --- Row 10: the manager's gate line over the signal line -----------------
@dataclass
class TradeView:
    gate_status: str = ""
    position_open: bool = False
    pending_order: bool = False


def try_order(view: TradeView, state: SignalState, threshold: int,
              gate: p8.GateInput) -> str:
    """Return the gate failure and record its line, as TryOrder does."""
    if not state.plan_active:
        view.gate_status = ""
        return p8.GATE_OK
    failure = gate_first_failure(gate, state.confidence, threshold)
    view.gate_status = gate_status(failure, 0, state.confidence, state.plan_side, threshold)
    return failure


def manager_step(view: TradeView, state: SignalState, threshold: int,
                 gate: Optional[p8.GateInput] = None) -> str:
    failure = p8.GATE_OK
    if not view.position_open and not view.pending_order and state.plan_active:
        failure = try_order(view, state, threshold, gate or p8.GateInput())
    if not state.plan_active and not view.position_open and not view.pending_order:
        view.gate_status = ""
    return failure


def row10(view: TradeView, state: SignalState, signal_line: str = "") -> str:
    if view.gate_status:
        return view.gate_status
    if state.signal == 0:
        return wait_status(state) or signal_line
    return signal_line
