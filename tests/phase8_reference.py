"""Portable reference models for Emtt Phase 8 (Emtt.md 21.2-21.14).

This module is intentionally MT5-free. It mirrors the pure decision layer in
``Include/Emtt/Emtt_Trade.mqh``, the published trade-ticket extension, and the
status / live-block contract. Broker calls are represented as inputs and
outputs so the gate, sizing, management invariants, record grammar, and panel
can be exercised on any platform.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

import phase7_reference as p7
from phase2_reference import BEAR, BULL, TRANSITION, VOLATILE

# 21.14 fixed rows.
RISK_PCT = 1.0
BE_ATR = 1.0
PARTIAL_PCT = 50.0
SPREAD_MULT = 2.0
SPREAD_SAMPLES = 20
SPREAD_WINDOW = 100
NEWS_WINDOW_MIN = 30
NEWS_SIZE_HIGH = 0.5
NEWS_SIZE_MED = 0.75
NEWS_TRAIL_MULT = 1.5
TRAIL_BASES = {"M5": 1.0, "M15": 1.5, "M30": 2.0}
TRAIL_CHANDELIER = 2.5
TRAIL_FRACTAL_BUFFER = 0.5
TRAIL_PHASE_HI = 0.50
TRAIL_PHASE_TOP = 0.80

MODE_AUTO = "Auto"
MODE_MINIMUM = "Minimum"
ENTRY_MARKET = "market"
ENTRY_BLOCK = "OB"
BUY = 1
SELL = -1
DASH = "\u2014"

NEWS_NONE = 0
NEWS_LOW = 1
NEWS_MEDIUM = 2
NEWS_HIGH = 3

GATE_OK = "ok"
GATE_AUTO_OFF = "auto_off"
GATE_TERMINAL_OFF = "terminal_off"
GATE_MARKET_CLOSED = "market_closed"
GATE_ALREADY_LIVE = "already_live"
GATE_SPREAD = "spread"
GATE_MARGIN = "margin"


@dataclass(frozen=True)
class GateInput:
    auto_trading: bool = True
    terminal_allowed: bool = True
    account_allowed: bool = True
    market_open: bool = True
    own_pending: bool = False
    own_position: bool = False
    spread_allowed: bool = True
    margin_check: bool = False
    margin_fits: bool = True


def gate_first_failure(value: GateInput) -> str:
    """21.4 ordered first failure; news and session are deliberately absent."""
    if not value.auto_trading:
        return GATE_AUTO_OFF
    if not value.terminal_allowed or not value.account_allowed:
        return GATE_TERMINAL_OFF
    if not value.market_open:
        return GATE_MARKET_CLOSED
    if value.own_pending or value.own_position:
        return GATE_ALREADY_LIVE
    if not value.spread_allowed:
        return GATE_SPREAD
    if value.margin_check and not value.margin_fits:
        return GATE_MARGIN
    return GATE_OK


def gate_status(failure: str, spread_points: int = 0) -> str:
    return {
        GATE_AUTO_OFF: f"No trade {DASH} Auto Trading OFF",
        GATE_TERMINAL_OFF: f"No trade {DASH} terminal algo trading OFF.",
        GATE_MARKET_CLOSED: f"Paused {DASH} Waiting for market to open",
        GATE_ALREADY_LIVE: f"No trade {DASH} Emtt trade already live",
        GATE_SPREAD: f"No trade {DASH} spread too wide ({spread_points} pts)",
        GATE_MARGIN: f"No trade {DASH} not enough margin",
    }.get(failure, "")


def spread_allowed(current: float, average: float, samples: int) -> bool:
    if samples < SPREAD_SAMPLES:
        return True
    if not math.isfinite(current) or not math.isfinite(average) or average < 0:
        return False
    return current <= SPREAD_MULT * average


def should_manage_position(position_open: bool, auto_trading: bool) -> bool:
    """Auto Trading gates entries only; a live Emtt position stays managed."""
    del auto_trading
    return position_open


def confidence_size_multiplier(confidence: int) -> float:
    if confidence >= 90:
        return 1.5
    if confidence >= 80:
        return 1.2
    if confidence >= 70:
        return 1.0
    return 0.7


def news_size_multiplier(impact: int) -> float:
    if impact == NEWS_HIGH:
        return NEWS_SIZE_HIGH
    if impact == NEWS_MEDIUM:
        return NEWS_SIZE_MED
    return 1.0


def risk_lots(balance: float, entry: float, stop: float, tick_size: float,
              tick_value: float, confidence: int,
              news_multiplier: float = 1.0) -> float:
    values = (balance, tick_size, tick_value, news_multiplier)
    if (not all(math.isfinite(x) for x in values) or balance <= 0 or
            tick_size <= 0 or tick_value <= 0 or news_multiplier <= 0 or
            not math.isfinite(entry) or not math.isfinite(stop)):
        return 0.0
    distance = abs(entry - stop)
    if distance <= 0:
        return 0.0
    risk_money = balance * RISK_PCT / 100.0
    money_per_lot = distance / tick_size * tick_value
    if money_per_lot <= 0 or not math.isfinite(money_per_lot):
        return 0.0
    return (risk_money / money_per_lot *
            confidence_size_multiplier(confidence) * news_multiplier)


def normalize_price(value: float, digits: int) -> float:
    """MQL5 NormalizeDouble: halves away from zero at the given digits."""
    scale = 10 ** digits
    return p7.mql_round(value * scale) / scale


def floor_to_step(volume: float, step: float) -> float:
    if not math.isfinite(volume) or not math.isfinite(step) or volume <= 0 or step <= 0:
        return 0.0
    digits = next((d for d in range(9)
                   if abs(step - round(step, d)) < 1e-10), 8)
    floored = math.floor((volume + step * 1e-10) / step) * step
    return normalize_price(floored, digits)


def resolve_lots(mode: str, balance: float, entry: float, stop: float,
                 tick_size: float, tick_value: float, confidence: int,
                 news_multiplier: float, minimum: float, maximum: float,
                 step: float) -> float:
    if (not math.isfinite(minimum) or not math.isfinite(maximum) or
            not math.isfinite(step) or minimum <= 0 or maximum < minimum or step <= 0):
        return 0.0
    digits = next((d for d in range(9)
                   if abs(step - round(step, d)) < 1e-10), 8)
    if mode == MODE_MINIMUM:
        return normalize_price(minimum, digits)
    raw = risk_lots(balance, entry, stop, tick_size, tick_value,
                    confidence, news_multiplier)
    if raw <= 0:
        return 0.0
    lots = floor_to_step(raw, step)
    lots = max(minimum, min(maximum, lots))
    return normalize_price(lots, digits)


def money_for_distance(distance: float, lots: float,
                       tick_size: float, tick_value: float) -> float:
    if (not all(math.isfinite(x) for x in (distance, lots, tick_size, tick_value))
            or lots <= 0 or tick_size <= 0 or tick_value <= 0):
        return 0.0
    return abs(distance) / tick_size * tick_value * lots


def money_rows(entry: float, stop: float, target: float, dealing: float,
               lots: float, tick_size: float, tick_value: float) -> tuple[float, float, float]:
    return (
        money_for_distance(entry - dealing, lots, tick_size, tick_value),
        money_for_distance(entry - stop, lots, tick_size, tick_value),
        money_for_distance(target - entry, lots, tick_size, tick_value),
    )


@dataclass(frozen=True)
class OrderPlan:
    valid: bool
    pending: bool = False
    side: int = 0
    order_type: str = ""
    volume: float = 0.0
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    stop_loss_sent: bool = False
    take_profit_sent: bool = False
    tp2_sent: bool = False
    time_in_force: str = "GTC"


def build_order(side: int, entry_kind: str, planned_entry: float,
                stop: float, tp1: float, bid: float, ask: float,
                place_stop_loss: bool, digits: int) -> OrderPlan:
    values = (planned_entry, stop, tp1, bid, ask)
    if (side not in (BUY, SELL) or digits < 0 or digits > 8 or
            not all(math.isfinite(x) and x > 0 for x in values)):
        return OrderPlan(False)
    pending = entry_kind == ENTRY_BLOCK and (
        planned_entry < ask if side == BUY else planned_entry > bid)
    if pending:
        order_type = "BUY_LIMIT" if side == BUY else "SELL_LIMIT"
        price = normalize_price(planned_entry, digits)
    else:
        order_type = "BUY" if side == BUY else "SELL"
        price = normalize_price(ask if side == BUY else bid, digits)
    return OrderPlan(
        True, pending, side, order_type, 0.0, price,
        normalize_price(stop, digits) if place_stop_loss else 0.0,
        normalize_price(tp1, digits), place_stop_loss, True, False, "GTC",
    )


def breakeven_event(place_stop_loss: bool) -> str:
    """21.7: with no sent stop the first stop is attached at the trigger;
    with a sent stop the existing one is moved to Entry."""
    return "Breakeven moved" if place_stop_loss else "Breakeven attached"


def breakeven_reached(side: int, entry: float, bar_high: float,
                      bar_low: float, atr: float) -> bool:
    if entry <= 0 or atr <= 0:
        return False
    if side == BUY:
        return bar_high >= entry + BE_ATR * atr
    if side == SELL:
        return bar_low <= entry - BE_ATR * atr
    return False


def partial_volume(volume: float, minimum: float, step: float) -> float:
    if min(volume, minimum, step) <= 0 or not all(
            math.isfinite(x) for x in (volume, minimum, step)):
        return 0.0
    digits = next((d for d in range(9)
                   if abs(step - round(step, d)) < 1e-10), 8)
    half = volume * PARTIAL_PCT / 100.0
    close_volume = math.floor(half / step + 0.5 - 1e-10) * step
    close_volume = normalize_price(close_volume, digits)
    remainder = normalize_price(volume - close_volume, digits)
    if close_volume < minimum or remainder < minimum or close_volume >= volume:
        return 0.0
    return close_volume


def expected_upper_minutes(estimate: int) -> int:
    if estimate <= 0:
        return 0
    if estimate < 120:
        return p7.mql_round(1.5 * estimate / 5.0) * 5
    if estimate <= 4320:
        return max(1, p7.mql_round(1.5 * estimate / 60.0)) * 60
    return 4320


def trail_base(timeframe: str) -> float:
    return TRAIL_BASES.get(timeframe, TRAIL_BASES["M15"])


def trail_confidence_multiplier(confidence: int) -> float:
    if confidence >= 85:
        return 1.0
    if confidence >= 70:
        return 0.9
    if confidence >= 55:
        return 0.7
    return 0.5


def trail_regime_multiplier(regime: str) -> float:
    if regime in (BULL, BEAR):
        return 1.0
    if regime == TRANSITION:
        return 0.8
    if regime == VOLATILE:
        return 1.3
    return 0.6


def trail_method(fraction: float) -> str:
    if fraction < TRAIL_PHASE_HI:
        return "ATR"
    if fraction < TRAIL_PHASE_TOP:
        return "Chandelier"
    return "Fractal"


@dataclass(frozen=True)
class TrailResult:
    valid: bool
    method: str = "Original"
    fraction: float = 0.0
    base_distance: float = 0.0
    raw_distance: float = 0.0
    confidence_multiplier: float = 1.0
    regime_multiplier: float = 1.0
    news_multiplier: float = 1.0
    distance: float = 0.0
    stop: float = 0.0


def trail_calculate(side: int, entry: float, current: float, tp1: float,
                    atr: float, timeframe: str, confidence: int, regime: str,
                    high_news: bool, highest_high: float = 0.0,
                    lowest_low: float = 0.0, swing_low: float = 0.0,
                    swing_high: float = 0.0, has_swing: bool = True) -> TrailResult:
    if (side not in (BUY, SELL) or min(entry, tp1, atr) <= 0 or
            not all(math.isfinite(x) for x in (entry, current, tp1, atr))):
        return TrailResult(False)
    target_distance = tp1 - entry if side == BUY else entry - tp1
    if target_distance <= 0:
        return TrailResult(False)
    favorable = current - entry if side == BUY else entry - current
    fraction = max(0.0, favorable) / target_distance
    method = trail_method(fraction)
    base = trail_base(timeframe) * atr
    if method == "ATR":
        raw = base
    elif method == "Chandelier":
        if side == BUY and highest_high > 0:
            raw = current - (highest_high - TRAIL_CHANDELIER * atr)
        elif side == SELL and lowest_low > 0:
            raw = (lowest_low + TRAIL_CHANDELIER * atr) - current
        else:
            return TrailResult(False)
    elif method == "Fractal":
        # 21.7: the Fractal method needs a confirmed swing point (13.3); the
        # manager passes hasSwing from the SMC state, never an invented level.
        if not has_swing:
            return TrailResult(False)
        if side == BUY and swing_low > 0:
            raw = current - (swing_low - TRAIL_FRACTAL_BUFFER * atr)
        elif side == SELL and swing_high > 0:
            raw = (swing_high + TRAIL_FRACTAL_BUFFER * atr) - current
        else:
            return TrailResult(False)
    else:
        return TrailResult(False)
    if raw <= 0 or not math.isfinite(raw):
        return TrailResult(False)
    conf = trail_confidence_multiplier(confidence)
    regime_mult = trail_regime_multiplier(regime)
    news_mult = NEWS_TRAIL_MULT if high_news else 1.0
    distance = raw * conf * regime_mult * news_mult
    stop = current - distance if side == BUY else current + distance
    return TrailResult(True, method, fraction, base, raw, conf,
                       regime_mult, news_mult, distance, stop)


def stop_improves(side: int, old_stop: float, new_stop: float,
                  point: float) -> bool:
    if side not in (BUY, SELL) or new_stop <= 0 or not math.isfinite(new_stop):
        return False
    if old_stop <= 0:
        return True
    epsilon = point * 0.1 if point > 0 else 1e-10
    return new_stop > old_stop + epsilon if side == BUY else new_stop < old_stop - epsilon


@dataclass(frozen=True)
class Candidate:
    price: float
    priority: int
    source: str


def ordered_candidates(side: int, current: float,
                       values: Iterable[Candidate]) -> list[Candidate]:
    kept: list[Candidate] = []
    for candidate in values:
        if candidate.price <= 0 or not math.isfinite(candidate.price):
            continue
        if any(abs(candidate.price - item.price) < 1e-12 for item in kept):
            continue
        kept.append(candidate)
    kept.sort(key=lambda item: (abs(item.price - current), item.priority))
    return kept[:6]


def level_future(side: int, price: float, current: float) -> bool:
    return price > current if side == BUY else price < current if side == SELL else False


def initial_second_target(side: int, entry: float, current: float, tp1: float,
                          items: Iterable[Candidate]) -> tuple[float, str]:
    """21.6 / 21.8: TP2 is named at open, never sent to the broker.

    The first ordered candidate strictly beyond TP1 and ahead of the current
    price wins; ``(0.0, "")`` means there is no second candidate yet.
    """
    for item in ordered_candidates(side, current, items):
        beyond = item.price > tp1 if side == BUY else item.price < tp1
        if beyond and level_future(side, item.price, current):
            return item.price, item.source
    return 0.0, ""


def targets_invariant(side: int, entry: float, current: float,
                       tp1: float, tp2: float = 0.0) -> bool:
    if side == BUY:
        return entry < tp1 < tp2 and tp1 > current and tp2 > current if tp2 > 0 else entry < tp1 and tp1 > current
    if side == SELL:
        return entry > tp1 > tp2 and tp1 < current and tp2 < current if tp2 > 0 else entry > tp1 and tp1 < current
    return False


@dataclass(frozen=True)
class TargetResult:
    valid: bool
    tp1_changed: bool = False
    tp2_changed: bool = False
    tp1: float = 0.0
    tp2: float = 0.0
    tp1_source: str = ""
    tp2_source: str = ""


def revise_targets(side: int, entry: float, current: float, stop: float,
                   current_tp1: float, current_tp2: float,
                   confidence: int, stay_threshold: int, in_profit: bool,
                   momentum_with: bool, tp1_hit: bool, min_rr: float,
                   items: Iterable[Candidate]) -> TargetResult:
    candidates = ordered_candidates(side, current, items)
    if (side not in (BUY, SELL) or min(entry, stop, current_tp1) <= 0 or
            min_rr < 0 or not math.isfinite(current)):
        return TargetResult(False, tp1=current_tp1, tp2=current_tp2)
    selected: Optional[Candidate] = None
    snap = in_profit and confidence < stay_threshold
    if snap or tp1_hit:
        selected = next((item for item in candidates
                         if level_future(side, item.price, current) and
                         (item.price > entry if side == BUY else item.price < entry)), None)
    else:
        risk = abs(entry - stop)
        for item in candidates:
            nearer = item.price < current_tp1 if side == BUY else item.price > current_tp1
            if (nearer and level_future(side, item.price, current) and
                    (item.price > entry if side == BUY else item.price < entry) and
                    risk > 0 and abs(item.price - entry) / risk + 1e-12 >= min_rr):
                selected = item
                break
    tp1 = selected.price if selected else current_tp1
    tp1_source = selected.source if selected else ""
    if selected is None and not level_future(side, current_tp1, current):
        return TargetResult(False, tp1=current_tp1, tp2=current_tp2)

    tp2 = current_tp2
    tp2_source = ""
    if momentum_with and not tp1_hit:
        extend = next((item for item in candidates
                       if (item.price > tp1 if side == BUY else item.price < tp1) and
                       (current_tp2 <= 0 or
                        (item.price > current_tp2 if side == BUY else item.price < current_tp2)) and
                       level_future(side, item.price, current)), None)
        if extend:
            tp2 = extend.price
            tp2_source = extend.source
        elif current_tp2 > 0 and not level_future(side, current_tp2, current):
            tp2 = 0.0
    else:
        contract = next((item for item in candidates
                         if (item.price > tp1 if side == BUY else item.price < tp1) and
                         level_future(side, item.price, current)), None)
        tp2 = contract.price if contract else 0.0
        tp2_source = contract.source if contract else ""

    if tp2 > 0 and not (tp1 < tp2 if side == BUY else tp1 > tp2):
        return TargetResult(False, tp1=current_tp1, tp2=current_tp2)
    if not level_future(side, tp1, current) or (tp2 > 0 and not level_future(side, tp2, current)):
        return TargetResult(False, tp1=current_tp1, tp2=current_tp2)
    return TargetResult(True, tp1 != current_tp1, tp2 != current_tp2,
                        tp1, tp2, tp1_source, tp2_source)


def time_exit_close(age_minutes: int, upper_minutes: int,
                    tp1_hit: bool, profit_points: float) -> bool:
    return upper_minutes > 0 and age_minutes > upper_minutes and (tp1_hit or profit_points > 0)


def time_exit_hold(age_minutes: int, upper_minutes: int,
                   tp1_hit: bool, profit_points: float) -> bool:
    return upper_minutes > 0 and age_minutes > upper_minutes and not tp1_hit and profit_points <= 0


def time_exit_hold_text() -> str:
    return f"Holding {DASH} past expected duration, not in profit yet."


def time_exit_hold_line(profit_points: float, bar_time: datetime) -> str:
    """21.13: the hold line of the journal (21.9's state change only)."""
    return (f"Emtt | Holding past expected duration | not in profit "
            f"({signed_text(profit_points, 0)} pts) | bar {p7.fmt_time(bar_time)}")


@dataclass
class TimeExitJournal:
    """17.8's discipline on 21.9's hold state: write it when it changes."""
    holding: bool = False

    def on_candle(self, *, age_minutes: int, upper_minutes: int, tp1_hit: bool,
                  profit_points: float, bar_time: datetime) -> str:
        holding = time_exit_hold(age_minutes, upper_minutes, tp1_hit,
                                 profit_points)
        line = ""
        if holding and not self.holding:
            line = time_exit_hold_line(profit_points, bar_time)
        self.holding = holding
        return line


def signed_text(value: float, digits: int) -> str:
    """EmttTradeManagerSigned: an explicit sign and the magnitude."""
    sign = "+" if value >= 0.0 else "-"
    return f"{sign}{abs(value):.{digits}f}"


def money_text(amount: float, currency: str = "$") -> str:
    """EmttTradeManagerMoney: the signed account-currency amount."""
    sign = "+" if amount >= 0.0 else "-"
    return f"{sign}{currency}{abs(amount):.2f}"


def compact_duration(text: str) -> str:
    """The panel's Expected Duration shape (EmttTradeManagerFillPanel)."""
    return text.replace(" hours", "h").replace(" hour", "h").replace(" min", "m")


@dataclass(frozen=True)
class NewsEvent:
    name: str
    time: datetime
    impact: int


@dataclass(frozen=True)
class NewsReading:
    available: bool
    window_open: bool = False
    impact: int = NEWS_NONE
    minutes: int = 0
    event: str = ""
    size_multiplier: float = 1.0
    trail_multiplier: float = 1.0
    status: str = ""
    unavailable_log: str = ""


def news_status(event_name: str, minutes: int, impact: int) -> str:
    if impact not in (NEWS_HIGH, NEWS_MEDIUM):
        return ""
    impact_name = "high" if impact == NEWS_HIGH else "medium"
    size = news_size_multiplier(impact)
    size_text = "0.5" if size == 0.5 else "0.75"
    return f"News {DASH} {event_name} in {minutes} min ({impact_name} impact), size {size_text}x."


def news_strongest(first_impact: int, second_impact: int) -> int:
    """21.10: the strongest multiplier wins when windows overlap."""
    return max(first_impact, second_impact)


def news_trail_multiplier(impact: int) -> float:
    return NEWS_TRAIL_MULT if impact == NEWS_HIGH else 1.0


def read_news(events: Iterable[NewsEvent], now: datetime,
              calendar_available: bool = True) -> NewsReading:
    if not calendar_available:
        return NewsReading(False, unavailable_log="Emtt | News calendar unavailable | no effect")
    values = list(events)
    if not values:
        return NewsReading(False, unavailable_log="Emtt | News calendar unavailable | no effect")
    active = [event for event in values
              if abs((event.time - now).total_seconds()) <= NEWS_WINDOW_MIN * 60]
    if not active:
        return NewsReading(True)
    impactful = [event for event in active if event.impact in (NEWS_MEDIUM, NEWS_HIGH)]
    if not impactful:
        return NewsReading(True)
    chosen = min(impactful, key=lambda event: (-event.impact,
                    abs((event.time - now).total_seconds()), event.name))
    delta = (chosen.time - now).total_seconds()
    minutes = math.ceil(delta / 60.0)
    impact = chosen.impact
    return NewsReading(True, True, impact, minutes, chosen.name,
        news_size_multiplier(impact), NEWS_TRAIL_MULT if impact == NEWS_HIGH else 1.0,
        news_status(chosen.name, minutes, impact))


@dataclass
class NewsUnavailableJournal:
    session: str = ""
    logged: bool = False

    def on_read(self, session: str, reading: NewsReading) -> str:
        if session != self.session:
            self.session = session
            self.logged = False
        if not reading.available and not self.logged:
            self.logged = True
            return reading.unavailable_log
        return ""


@dataclass
class TradeTicket:
    plan: p7.Ticket
    trade_filled: Optional[datetime] = None
    trade_closed: Optional[datetime] = None
    trade_net_points: Optional[int] = None
    label_frozen: bool = False
    resolved_label: Optional[int] = None


def trade_ticket_line(ticket: TradeTicket, digits: int = 5) -> str:
    line = p7.ticket_line(ticket.plan, digits)
    if ticket.trade_filled is not None:
        line += " | trade filled " + p7.fmt_time(ticket.trade_filled)
        if ticket.trade_closed is not None:
            if ticket.trade_net_points is None:
                raise ValueError("a closed trade needs net points")
            net = ticket.trade_net_points
            line += " | trade closed " + p7.fmt_time(ticket.trade_closed)
            line += " | net " + ("+" if net >= 0 else "") + str(net) + " pts"
    elif ticket.trade_closed is not None or ticket.trade_net_points is not None:
        raise ValueError("trade close/net requires a fill")
    return line


_TIME_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}$")
_NET_RE = re.compile(r"^net ([+-]?\d+) pts$")


def _parse_time(text: str) -> datetime:
    if not _TIME_RE.fullmatch(text):
        raise ValueError("bad trade time")
    return datetime.strptime(text, "%Y.%m.%d %H:%M")


def parse_trade_ticket_line(line: str, digits: int = 5) -> TradeTicket:
    pieces = line.split(" | trade filled ")
    if len(pieces) > 2:
        raise ValueError("duplicate trade fill")
    plan = p7.parse_ticket_line(pieces[0], digits)
    ticket = TradeTicket(plan)
    if len(pieces) == 1:
        return ticket
    trade_parts = pieces[1].split(" | ")
    ticket.trade_filled = _parse_time(trade_parts[0])
    if len(trade_parts) == 1:
        return ticket
    if len(trade_parts) != 3 or not trade_parts[1].startswith("trade closed "):
        raise ValueError("incomplete trade close/net part")
    ticket.trade_closed = _parse_time(trade_parts[1][len("trade closed "):])
    net_match = _NET_RE.fullmatch(trade_parts[2])
    if not net_match:
        raise ValueError("invalid net field")
    ticket.trade_net_points = int(net_match.group(1))
    if ticket.trade_closed < ticket.trade_filled:
        raise ValueError("trade close precedes fill")
    return ticket


def label_of(ticket: TradeTicket) -> Optional[int]:
    """Freeze the first resolved evidence: real close, otherwise paper result."""
    if ticket.label_frozen:
        return ticket.resolved_label
    if ticket.trade_filled is not None:
        if ticket.trade_closed is None or ticket.trade_net_points is None:
            return None
        ticket.resolved_label = (1 if ticket.trade_net_points > 0 else
                                 0 if ticket.trade_net_points < 0 else None)
        ticket.label_frozen = True
        return ticket.resolved_label
    if ticket.plan.result != p7.RESULT_NONE:
        ticket.resolved_label = p7.label_of(ticket.plan)
        ticket.label_frozen = True
        return ticket.resolved_label
    return None


def learning_counts(tickets: Iterable[TradeTicket]) -> tuple[int, int, int]:
    labels = [label_of(ticket) for ticket in tickets]
    wins = labels.count(1)
    losses = labels.count(0)
    return wins + losses, wins, losses


def trade_file_write_events() -> tuple[str, ...]:
    """The existing four learning writes plus the two Phase 8 trade events."""
    return ("init_after_load", "plan_start", "entry_reached", "plan_end",
            "trade_filled", "position_closed")


@dataclass(frozen=True)
class LivePosition:
    ticket: int
    side: int
    volume: float
    entry: float
    current: float
    floating_money: float
    stop: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    protect_method: str = "Original"
    stop_exists: bool = False
    breakeven: bool = False
    age_minutes: int = 0
    expected_duration: str = "--"


def protect_word(stop_exists: bool, breakeven: bool, method: str) -> str:
    if not stop_exists or not breakeven:
        return "Original"
    if method in ("", "Original"):
        return "Breakeven"
    return method


DIAMOND_GLYPH = "\u25c6"  # the live-block header mark (Emtt_G_DIAMOND)


def live_block(position: Optional[LivePosition], *, point: float,
               digits: int, volume_digits: int, timeframe_name: str = "M15",
               currency: str = "$", pending: bool = False) -> Optional[dict[str, str]]:
    """Rows 11-14 exist for a live position; a pending order alone shows
    only Row 10 (21.12), so the block is None while nothing is filled."""
    if position is None or pending:
        return None
    side_name = "BUY" if position.side == BUY else "SELL"
    signed_points = ((position.current - position.entry) * position.side / point
                     if point > 0 else 0.0)
    stop_points = (p7.mql_round(abs(position.current - position.stop) / point)
                   if point > 0 and position.stop > 0 else 0)
    stop_text = p7.fmt_price(position.stop, digits) if position.stop > 0 else "--"
    tp1_text = p7.fmt_price(position.tp1, digits) if position.tp1 > 0 else "--"
    tp2_text = p7.fmt_price(position.tp2, digits) if position.tp2 > 0 else "--"
    age = f"{position.age_minutes // 60:02d}:{position.age_minutes % 60:02d}"
    protect = protect_word(position.stop_exists, position.breakeven,
                           position.protect_method)
    return {
        "header": f"{DIAMOND_GLYPH} LIVE TRADE {DASH} On {timeframe_name}",
        "ticket": (f"Ticket: {position.ticket} | {side_name} "
                   f"{position.volume:.{volume_digits}f} lots @ {position.entry:.{digits}f}"),
        "floating": (f"Floating P/L: {money_text(position.floating_money, currency)} "
                     f"({signed_text(signed_points, 0)} pts)"),
        "live_sl": (f"Live SL: {stop_text} "
                    f"({stop_points if position.stop > 0 else '--'} pts) "
                    f"| TP1: {tp1_text} TP2: {tp2_text}"),
        "protect": f"Protect: {protect} | Age: {age} / {position.expected_duration}",
    }


#--- 21.12 the Row 10 status lines --------------------------------------

def rejected_status(code: int) -> str:
    return f"Order rejected {DASH} broker error {code}"


def live_pending_status(price: float, digits: int) -> str:
    return (f"Signal active {DASH} pending order at "
            f"{p7.fmt_price(price, digits)}, waiting.")


def live_position_status() -> str:
    return f"Signal active {DASH} position open, managing."


def fresh_tp1_status(protection_set: bool = True,
                     skipped: bool = False) -> str:
    body = "partial skipped" if skipped else "50% closed"
    tail = "stop at breakeven." if protection_set else "protection update pending."
    return f"TP1 hit {DASH} {body}, {tail}"


def fresh_tp1_protection_status() -> str:
    return f"TP1 hit {DASH} protection active at breakeven."


def fresh_breakeven_status() -> str:
    return f"Breakeven {DASH} stop at entry, trailing active."


def fresh_trailing_status(price: float, locked_points: int, digits: int) -> str:
    return (f"Trailing {DASH} stop at {p7.fmt_price(price, digits)}, "
            f"+{locked_points} pts locked.")


def fresh_position_closed_status(net_points: int, net_money: float,
                                 currency: str = "$") -> str:
    return (f"Position closed {DASH} {signed_text(net_points, 0)} pts "
            f"({money_text(net_money, currency)}). "
            f"Scanning for the next setup.")



def panel_status(*, incompatible: str = "", loading: str = "",
                 market_closed: str = "", fresh: str = "", time_hold: str = "",
                 news: str = "", gate: str = "", live: str = "",
                 signal: str = "", context: str = "", terminal: str = "") -> str:
    """21.12 STATUS precedence, highest-priority non-empty value wins."""
    return next((value for value in (incompatible, loading, market_closed, fresh,
                                     time_hold, news, gate, live, signal, context,
                                     terminal) if value), "")


def header_auto_trading(enabled: bool) -> str:
    return "Auto Trading: ON" if enabled else "Auto Trading: OFF"
