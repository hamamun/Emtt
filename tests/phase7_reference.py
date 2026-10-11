"""Portable reference functions for Emtt Phase 7's learning logic (Emtt.md 19.2-19.9).

Mirrors ``Include/Emtt/Emtt_Learning.mqh`` and ``Include/Emtt/Emtt_LearnFile.mqh``
with no MT5 dependency, so CI exercises the ticket record, the file grammar, the
16 features, the logistic model and its SGD update, the warm-up, the learned
term, the adjusted number, the panel text, the journal lines and the restart
resume on every platform. File access is modelled by ``Disk``, an in-memory
``<path>.tmp`` + rename folder, and every ``PrintFormat`` is captured as a
string instead.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Optional

import phase6_reference as p6
from phase2_reference import BEAR, BULL, RANGING, TRANSITION, VOLATILE
from phase2_reference import HIGH, LOW, NORMAL, session_names

#--- 19.8 the Phase 7 rows ---------------------------------------------
LEARN_FEATURES = 16
LEARN_WARMUP = 30
LEARN_STRENGTH = 0.15
LEARN_RATE = 0.30
LEARN_CLAMP = 4.0
LEARN_Z_CLAMP = 30.0
LEARN_CAP = 500
LEARN_CONF_CAP = 100

#--- 19.3 the file ------------------------------------------------------
LEARN_VERSION = "Emtt_Learning v1"
LEARN_DIR = "Emtt_Learning"
LEARN_EXT = ".learn"

STATE_PENDING = "pending"
STATE_ACTIVE = "active"
STATE_CLOSED = "closed"

ENTRY_MARKET = "market"
ENTRY_BLOCK = "OB"

RESULT_NONE = ""
RESULT_TARGET = "target"
RESULT_STOP = "stop"
RESULT_MISSED = "missed"
RESULT_CANCELLED = "cancelled"
RESULT_SIGNAL = "signal"
RESULT_MARKET = "market"
RESULT_CHART = "chart"
RESULT_WORDS = (
    RESULT_TARGET,
    RESULT_STOP,
    RESULT_MISSED,
    RESULT_CANCELLED,
    RESULT_SIGNAL,
    RESULT_MARKET,
    RESULT_CHART,
)

# One-hot orders of 19.4, fixed by design.
MOOD_ORDER = ("TRENDING", "RANGING", "VOLATILE", "TRANSITION")
SESSION_ORDER = ("ASIA", "LONDON", "NEWYORK")
VOL_ORDER = ("LOW", "NORMAL", "HIGH")

# 19.7 the em dash of the STATUS line (ASCII source, escape at build time).
DASH = "\u2014"


def mql_round(value: float) -> int:
    """MQL5 MathRound: halves away from zero."""
    if value >= 0.0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)


def fmt_price(value: float, digits: int) -> str:
    """MQL5 DoubleToString(value, digits)."""
    scale = 10 ** digits
    return f"{mql_round(value * scale) / scale:.{digits}f}"


def fmt_time(bar_time: datetime) -> str:
    """TimeToString(bar_time, TIME_DATE | TIME_MINUTES)."""
    return bar_time.strftime("%Y.%m.%d %H:%M")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def tick_name(timeframe: str) -> str:
    """EmttLearnTfName: PERIOD_M15 -> M15."""
    return timeframe


def sanitize(value: str) -> str:
    """19.3 sanitiser: outside A-Z a-z 0-9 _ - . every character becomes _."""
    out = []
    for ch in value:
        if ch.isascii() and (ch.isalnum() or ch in "_-."):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)


def learn_name_text(symbol: str, timeframe: str) -> str:
    return f"{sanitize(symbol)}_{sanitize(tick_name(timeframe))}"


def learn_file_path(symbol: str, timeframe: str) -> str:
    return f"{LEARN_DIR}\\{learn_name_text(symbol, timeframe)}{LEARN_EXT}"


#--- 19.4 the fixed vocabularies ---------------------------------------


def mood_index(mood: str) -> str:
    if mood in (BULL, BEAR):
        return "TRENDING"
    if mood == RANGING:
        return "RANGING"
    if mood == VOLATILE:
        return "VOLATILE"
    return "TRANSITION"


def session_index(label: str) -> str:
    """The 15.3 anchor label; where two overlap the later opening one wins."""
    if "NY" in label:
        return "NEWYORK"
    if "London" in label:
        return "LONDON"
    return "ASIA"


def vol_index(volatility: str) -> str:
    if volatility == LOW:
        return "LOW"
    if volatility == HIGH:
        return "HIGH"
    return "NORMAL"


def session_index_at(utc: datetime) -> str:
    """The session of 19.3 read from the 15.3 anchor rule through the clock."""
    return session_index(session_names(utc))


PLAN_RESULT_OF_LEARN = {
    RESULT_TARGET: p6.RESULT_TARGET,
    RESULT_STOP: p6.RESULT_STOP,
    RESULT_MISSED: p6.RESULT_MISSED,
    RESULT_CANCELLED: p6.RESULT_CANCELLED,
    RESULT_SIGNAL: p6.RESULT_SIGNAL,
    RESULT_MARKET: p6.RESULT_CLOSED,
    RESULT_CHART: p6.RESULT_CHART,
}


def result_of_plan_result(result: str) -> str:
    """The 17.7 result word -> the file's short word of 19.3."""
    return {value: key for key, value in PLAN_RESULT_OF_LEARN.items()}[result]


#--- 19.3 the ticket ----------------------------------------------------


@dataclass
class Ticket:
    """One plan line: every field of 19.3's grammar."""

    start_bar_time: datetime
    side: int
    confidence: int
    views: tuple[int, int, int, int]
    mood: str
    session: str
    vol: str
    entry: float
    entry_kind: str = ENTRY_MARKET
    stop: float = 0.0
    target: float = 0.0
    est: int = 0
    spread: int = 0
    state: str = STATE_PENDING
    reached_bar_time: Optional[datetime] = None
    result: str = RESULT_NONE
    shared: bool = False
    exit_price: float = 0.0
    points: int = 0
    candles: int = 0
    start_sequence: int = -1


def label_of(ticket: Ticket) -> Optional[int]:
    """19.4: target is a win, stop a loss, every other result neither."""
    if ticket.result == RESULT_TARGET:
        return 1
    if ticket.result == RESULT_STOP:
        return 0
    return None


def ticket_line(ticket: Ticket, digits: int) -> str:
    views = ",".join(str(v) for v in ticket.views)
    line = (
        f"plan {fmt_time(ticket.start_bar_time)}"
        f" | {'BUY' if ticket.side > 0 else 'SELL'}"
        f" | conf {ticket.confidence}"
        f" | views {views}"
        f" | mood {ticket.mood}"
        f" | session {ticket.session}"
        f" | vol {ticket.vol}"
        f" | entry {fmt_price(ticket.entry, digits)} {ticket.entry_kind}"
        f" | stop {fmt_price(ticket.stop, digits)}"
        f" | target {fmt_price(ticket.target, digits)}"
        f" | est {ticket.est}"
        f" | spread {ticket.spread}"
        f" | state {ticket.state}"
    )
    if ticket.reached_bar_time is not None:
        line += f" | reached {fmt_time(ticket.reached_bar_time)}"
    if ticket.result != RESULT_NONE:
        line += f" | result {ticket.result}"
        if ticket.shared:
            line += " shared"
        line += (
            f" | exit {fmt_price(ticket.exit_price, digits)}"
            f" | points {ticket.points}"
            f" | candles {ticket.candles}"
        )
    return line


class MalformedTicket(ValueError):
    """A ticket line that does not follow the grammar of 19.3."""


def _part_tail(part: str, key: str) -> str:
    if not part.startswith(key + " "):
        raise MalformedTicket(f"part does not start with {key!r}: {part!r}")
    tail = part[len(key) + 1:].strip()
    if not tail:
        raise MalformedTicket(f"empty {key!r} tail: {part!r}")
    return tail


def _part_int(part: str, key: str) -> int:
    tail = _part_tail(part, key)
    digits = tail[1:] if tail[0] in "+-" else tail
    if not digits.isdigit():
        raise MalformedTicket(f"{key!r} is not a whole number: {tail!r}")
    return int(tail)


def _part_price(part: str, key: str) -> float:
    tail = _part_tail(part, key)
    value = float(tail)
    if not math.isfinite(value) or value <= 0.0:
        raise MalformedTicket(f"{key!r} is not a price: {tail!r}")
    return value


def _part_time(part: str, key: str) -> datetime:
    tail = _part_tail(part, key)
    if len(tail) != 16 or tail[4] != "." or tail[7] != "." or tail[10] != " " or tail[13] != ":":
        raise MalformedTicket(f"{key!r} is not a bar time: {tail!r}")
    return datetime.strptime(tail, "%Y.%m.%d %H:%M")


def parse_ticket_line(line: str, digits: int = 5) -> Ticket:
    """The inverse of ``ticket_line``; a malformed line raises."""
    parts = [part.strip() for part in line.split("|")]
    if len(parts) < 13:
        raise MalformedTicket(f"too few parts: {line!r}")
    views = [word.strip() for word in _part_tail(parts[3], "views").split(",")]
    if len(views) != 4 or any(word not in ("1", "0", "-1") for word in views):
        raise MalformedTicket(f"views are not four -1/0/+1: {views!r}")
    entry_words = _part_tail(parts[7], "entry").split(" ")
    if len([word for word in entry_words if word]) != 2:
        raise MalformedTicket(f"entry is not '<price> OB|market': {parts[7]!r}")
    entry_price = float(entry_words[0])
    entry_kind = entry_words[-1]
    if entry_kind not in (ENTRY_MARKET, ENTRY_BLOCK):
        raise MalformedTicket(f"unknown entry kind: {entry_kind!r}")
    state = _part_tail(parts[12], "state")
    if state not in (STATE_PENDING, STATE_ACTIVE, STATE_CLOSED):
        raise MalformedTicket(f"unknown state: {state!r}")
    confidence = _part_int(parts[2], "conf")
    if confidence < 0 or confidence > 100:
        raise MalformedTicket(f"confidence out of range: {confidence}")
    mood = _part_tail(parts[4], "mood")
    session = _part_tail(parts[5], "session")
    vol = _part_tail(parts[6], "vol")
    if mood not in MOOD_ORDER or session not in SESSION_ORDER or vol not in VOL_ORDER:
        raise MalformedTicket("unknown mood/session/vol word")

    ticket = Ticket(
        start_bar_time=_part_time(parts[0], "plan"),
        side=1 if parts[1] == "BUY" else -1 if parts[1] == "SELL" else _raise_side(parts[1]),
        confidence=confidence,
        views=(int(views[0]), int(views[1]), int(views[2]), int(views[3])),
        mood=mood,
        session=session,
        vol=vol,
        entry=entry_price,
        entry_kind=entry_kind,
        stop=_part_price(parts[8], "stop"),
        target=_part_price(parts[9], "target"),
        est=_part_int(parts[10], "est"),
        spread=_part_int(parts[11], "spread"),
        state=state,
    )
    if ticket.est < 0 or ticket.spread < 0:
        raise MalformedTicket("negative est/spread")
    for part in parts[13:]:
        try:
            ticket.reached_bar_time = _part_time(part, "reached")
            continue
        except MalformedTicket:
            pass
        if part.startswith("result "):
            words = _part_tail(part, "result").split(" ")
            if len(words) > 2 or words[0] not in RESULT_WORDS:
                raise MalformedTicket(f"bad result part: {part!r}")
            ticket.result = words[0]
            if len(words) == 2:
                if words[1] != "shared":
                    raise MalformedTicket(f"bad result tail: {part!r}")
                ticket.shared = True
            continue
        try:
            ticket.exit_price = _part_price(part, "exit")
            continue
        except MalformedTicket:
            pass
        try:
            ticket.points = _part_int(part, "points")
            continue
        except MalformedTicket:
            pass
        try:
            ticket.candles = _part_int(part, "candles")
            continue
        except MalformedTicket:
            pass
        raise MalformedTicket(f"unknown part: {part!r}")
    if ticket.state == STATE_CLOSED and ticket.result == RESULT_NONE:
        raise MalformedTicket("a closed ticket carries a result")
    if ticket.state != STATE_CLOSED and ticket.result != RESULT_NONE:
        raise MalformedTicket("an open ticket carries no result")
    if ticket.candles < 0:
        raise MalformedTicket("negative candles")
    return ticket


def _raise_side(word: str) -> int:
    raise MalformedTicket(f"unknown side: {word!r}")


def counts_line(tickets: list[Ticket], bar_time: Optional[datetime]) -> str:
    labeled = sum(1 for t in tickets if label_of(t) is not None)
    wins = sum(1 for t in tickets if label_of(t) == 1)
    losses = sum(1 for t in tickets if label_of(t) == 0)
    stamp = fmt_time(bar_time) if bar_time is not None else fmt_time(datetime(2000, 1, 1))
    return (
        f"counts {len(tickets)} | labeled {labeled} | wins {wins}"
        f" | losses {losses} | updated {stamp}"
    )


class Disk:
    """The MQL5\\Files\\Emtt_Learning folder, modelled in memory."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.fail_write = False
        self.fail_move = False

    def exists(self, path: str) -> bool:
        return path in self.files

    def text(self, path: str) -> Optional[str]:
        return self.files.get(path)

    def write_tmp(self, path: str, text: str) -> bool:
        if self.fail_write:
            return False
        self.files[path + ".tmp"] = text
        return True

    def move_over(self, path: str) -> bool:
        """FileMove(path + '.tmp', path, FILE_REWRITE)."""
        if self.fail_move:
            return False
        tmp = path + ".tmp"
        if tmp not in self.files:
            return False
        self.files[path] = self.files.pop(tmp)
        return True


#--- 19.3 the record ----------------------------------------------------


@dataclass
class LearningFile:
    """The per-symbol, per-timeframe record and its five events."""

    symbol: str = "EURUSD"
    timeframe: str = "M15"
    digits: int = 5
    tickets: list[Ticket] = field(default_factory=list)
    loaded: bool = False
    read_only: bool = False
    version_warned: bool = False
    damaged_warned: bool = False
    write_failed: bool = False
    journal: list[str] = field(default_factory=list)

    #--- derived -------------------------------------------------------
    @property
    def path(self) -> str:
        return learn_file_path(self.symbol, self.timeframe)

    @property
    def name_text(self) -> str:
        return learn_name_text(self.symbol, self.timeframe)

    @property
    def labeled(self) -> int:
        return sum(1 for t in self.tickets if label_of(t) is not None)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.tickets if label_of(t) == 1)

    @property
    def losses(self) -> int:
        return sum(1 for t in self.tickets if label_of(t) == 0)

    @property
    def open_index(self) -> int:
        for index in range(len(self.tickets) - 1, -1, -1):
            if self.tickets[index].state != STATE_CLOSED:
                return index
        return -1

    #--- the grammar ----------------------------------------------------
    def render(self, bar_time: Optional[datetime] = None) -> str:
        lines = [f"{LEARN_VERSION} | {self.symbol} | {self.timeframe}"]
        lines.append(counts_line(self.tickets, bar_time))
        lines.extend(ticket_line(ticket, self.digits) for ticket in self.tickets)
        return "\r\n".join(lines) + "\r\n"

    @classmethod
    def load(cls, disk: Disk, symbol: str, timeframe: str, digits: int,
             bar_time: datetime) -> "LearningFile":
        """19.3 event flow, load half: read, check the version, parse."""
        state = cls(symbol=symbol, timeframe=timeframe, digits=digits)
        state.loaded = True
        if not disk.exists(state.path):
            state.journal.append(
                f"Emtt | Learning started | no file yet | {state.name_text}"
                f" | bar {fmt_time(bar_time)}"
            )
            return state
        text = disk.text(state.path) or ""
        lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
        lines = [line for line in lines if line]
        if not lines or lines[0].split("|")[0].strip() != LEARN_VERSION:
            state.read_only = True
            if not state.version_warned:
                state.journal.append(
                    "Emtt | Learning version unknown | file untouched,"
                    f" memory only | {state.path} | bar {fmt_time(bar_time)}"
                )
                state.version_warned = True
            return state
        damaged = 0
        for line in lines[1:]:
            if line.startswith("counts"):
                continue
            try:
                ticket = parse_ticket_line(line, digits)
            except (MalformedTicket, ValueError):
                damaged += 1
                continue
            if len(state.tickets) >= LEARN_CAP:
                damaged += 1
                continue
            state.tickets.append(ticket)
        if damaged and not state.damaged_warned:
            state.journal.append(
                f"Emtt | Learning file damaged | {damaged} malformed ticket"
                f" lines skipped, the rest kept | {state.path}"
                f" | bar {fmt_time(bar_time)}"
            )
            state.damaged_warned = True
        state.journal.append(
            f"Emtt | Learning loaded | {len(state.tickets)} plans,"
            f" {state.labeled} labeled, {state.wins} wins, {state.losses} losses"
            f" | {warming_text(state.labeled)} | bar {fmt_time(bar_time)}"
        )
        return state

    def save(self, disk: Disk, bar_time: datetime) -> bool:
        """19.3: whole-file rewrite through <path>.tmp and a rename."""
        if not self.loaded or self.read_only:
            return False
        stamp = fmt_time(bar_time)
        if not disk.write_tmp(self.path, self.render(bar_time)):
            if not self.write_failed:
                self.journal.append(
                    "Emtt | Learning file busy | learning kept in memory"
                    f" | bar {stamp}"
                )
                self.write_failed = True
            return False
        if not disk.move_over(self.path):
            if not self.write_failed:
                self.journal.append(
                    "Emtt | Learning file busy | learning kept in memory"
                    f" | bar {stamp}"
                )
                self.write_failed = True
            return False
        if self.write_failed:
            self.journal.append(f"Emtt | Learning write recovered | bar {stamp}")
            self.write_failed = False
        return True

    #--- 19.3 the cap ---------------------------------------------------
    def apply_cap(self) -> None:
        while len(self.tickets) >= LEARN_CAP:
            drop = next(
                (i for i, t in enumerate(self.tickets) if t.state == STATE_CLOSED),
                -1,
            )
            if drop < 0:
                return
            del self.tickets[drop]

    #--- 19.3 the three ticket events -----------------------------------
    def add_plan(self, ticket: Ticket) -> int:
        self.apply_cap()
        if len(self.tickets) >= LEARN_CAP:
            return -1
        self.tickets.append(ticket)
        return len(self.tickets) - 1

    def mark_reached(self, slot: int, bar_time: datetime) -> bool:
        if slot < 0 or slot >= len(self.tickets):
            return False
        if self.tickets[slot].state != STATE_PENDING:
            return False
        self.tickets[slot] = replace(
            self.tickets[slot], state=STATE_ACTIVE, reached_bar_time=bar_time
        )
        return True

    def close_ticket(self, slot: int, result: str, shared: bool,
                     exit_price: float, points: int, candles: int) -> bool:
        if slot < 0 or slot >= len(self.tickets):
            return False
        if result == RESULT_NONE:
            return False
        self.tickets[slot] = replace(
            self.tickets[slot],
            state=STATE_CLOSED,
            result=result,
            shared=shared,
            exit_price=exit_price,
            points=points,
            candles=candles,
        )
        return True


#--- 19.4 the 16 features ----------------------------------------------

VIEW_NAMES = ("trend", "structure", "flow", "htf")


def agreement(view_direction: int, side: int) -> int:
    """+1 same, 0 flat, -1 opposite."""
    if view_direction == 0:
        return 0
    return 1 if view_direction == side else -1


def features(side: int, confidence_number: int, views: tuple[int, int, int, int],
             mood: str, session: str, vol: str) -> list[float]:
    """The 16 features of 19.4, in the fixed order."""
    vector = [
        float(side),
        confidence_number / 100.0,
    ]
    vector.extend(float(agreement(view, side)) for view in views)
    vector.extend(1.0 if mood == word else 0.0 for word in MOOD_ORDER)
    vector.extend(1.0 if session == word else 0.0 for word in SESSION_ORDER)
    vector.extend(1.0 if vol == word else 0.0 for word in VOL_ORDER)
    return vector


def features_from_ticket(ticket: Ticket) -> list[float]:
    return features(ticket.side, ticket.confidence, ticket.views, ticket.mood,
                    ticket.session, ticket.vol)


#--- 19.4 the model -----------------------------------------------------


def clamp_z(z: float) -> float:
    return clamp(z, -LEARN_Z_CLAMP, LEARN_Z_CLAMP)


def probability(weights: list[float], bias: float, vector: list[float]) -> float:
    """p = 1 / (1 + e^(-z)) with z clamped to [-30, +30]."""
    z = clamp_z(bias + sum(w * x for w, x in zip(weights, vector)))
    return 1.0 / (1.0 + math.exp(-z))


def term_of(probability_value: float) -> float:
    """L = clamp(2p - 1, -1, +1); exactly 0 at p = 0.5."""
    return clamp(2.0 * probability_value - 1.0, -1.0, 1.0)


def clamp_weight(value: float) -> float:
    return clamp(value, -LEARN_CLAMP, LEARN_CLAMP)


def build_model(tickets: list[Ticket]) -> tuple[list[float], float]:
    """One SGD step per labeled ticket, in file order, lr = 0.30 / sqrt(k)."""
    weights = [0.0] * LEARN_FEATURES
    bias = 0.0
    step = 0
    for ticket in tickets:
        label = label_of(ticket)
        if label is None:
            continue
        step += 1
        vector = features_from_ticket(ticket)
        p = probability(weights, bias, vector)
        lr = LEARN_RATE / math.sqrt(step)
        error = label - p
        weights = [clamp_weight(w + lr * error * x)
                   for w, x in zip(weights, vector)]
        bias = clamp_weight(bias + lr * error * 1.0)
    return weights, bias


#--- 19.5 the adjusted number ------------------------------------------


@dataclass(frozen=True)
class Side:
    probability: float = 0.5
    term: float = 0.0
    value: float = 0.0


@dataclass(frozen=True)
class Reading:
    ready: bool = False
    combined: float = 0.0
    raw_number: int = -1
    warm: bool = False
    labeled: int = 0
    direction: int = 0
    number: int = -1
    percent: int = -1
    scale: float = 1.0
    buy: Side = field(default_factory=Side)
    sell: Side = field(default_factory=Side)


@dataclass(frozen=True)
class Candle:
    """The newest closed bar's published readings (19.4)."""

    ready: bool = False
    combined: float = 0.0
    raw_number: int = -1
    views: tuple[int, int, int, int] = (0, 0, 0, 0)
    mood: str = "TRANSITION"
    session: str = "ASIA"
    vol: str = "NORMAL"


def evaluate(weights: list[float], bias: float, candle: Candle,
             labeled: int) -> Reading:
    """The reading of 19.5 for one closed bar."""
    warm = labeled >= LEARN_WARMUP
    if not candle.ready:
        return Reading(ready=False, labeled=labeled, warm=warm)
    if candle.raw_number < 0:
        return Reading(ready=False, labeled=labeled, warm=warm)
    buy_p = probability(weights, bias,
                        features(1, candle.raw_number, candle.views,
                                 candle.mood, candle.session, candle.vol))
    sell_p = probability(weights, bias,
                         features(-1, candle.raw_number, candle.views,
                                  candle.mood, candle.session, candle.vol))
    buy_term = term_of(buy_p) if warm else 0.0
    sell_term = term_of(sell_p) if warm else 0.0
    buy = Side(buy_p, buy_term, candle.combined * (1.0 + LEARN_STRENGTH * buy_term))
    sell = Side(sell_p, sell_term,
                -candle.combined * (1.0 + LEARN_STRENGTH * sell_term))
    if buy.value > sell.value:
        direction = 1
    elif sell.value > buy.value:
        direction = -1
    else:
        direction = 0
    best = max(0.0, buy.value, sell.value)
    number = min(LEARN_CONF_CAP, mql_round(100.0 * best))
    percent = -1
    scale = 1.0
    if direction != 0:
        chosen = buy if direction > 0 else sell
        percent = mql_round(100.0 * chosen.probability) if warm else -1
        if abs(candle.combined) > 0.0:
            factor = 1.0 + LEARN_STRENGTH * chosen.term
            scale = max(0.0, min(factor, 1.0 / abs(candle.combined)))
    return Reading(ready=True, combined=candle.combined,
                   raw_number=candle.raw_number, warm=warm, labeled=labeled,
                   direction=direction, number=number, percent=percent,
                   scale=scale, buy=buy, sell=sell)


#--- 19.7 the text ------------------------------------------------------


def warming_text(labeled: int) -> str:
    return f"warming {labeled}/{LEARN_WARMUP}"


def clause_text(reading: Reading) -> str:
    """The Row 9 clause; the author's 2026-10-11 decision keeps it journal-only."""
    if not reading.ready:
        return ""
    if not reading.warm:
        return f"Learning {warming_text(reading.labeled)}"
    if reading.direction != 0 and reading.percent >= 0:
        return f"Learning {reading.percent}% ({reading.labeled} plans)"
    return f"Learning ({reading.labeled} plans)"


def why_append(prior: str, clause: str) -> str:
    if clause == "":
        return prior
    if prior == "" or prior == "--":
        return clause
    return f"{prior} | {clause}"


def plan_text(reading: Reading) -> str:
    """The plan start line's last part of 19.7."""
    if not reading.warm:
        return f"learning {warming_text(reading.labeled)}"
    if reading.direction != 0 and reading.percent >= 0:
        return f"learning {reading.percent}%"
    return ""


def hold_reason(reading: Reading, bar: int) -> str:
    """The one WAIT reason Phase 7 adds, checked before the first of 17.6."""
    if not reading.ready or not reading.warm or reading.direction == 0:
        return ""
    if bar <= 0 or reading.percent < 0:
        return ""
    if reading.raw_number < bar:
        return ""
    if reading.number >= bar:
        return ""
    return f"Watching {DASH} learning {reading.percent}% holds this one back."


def status_choice(phase6_status: str, reading: Reading, bar: int) -> str:
    """Row 10: the learning reason wins over the 17.6 reasons when it applies."""
    reason = hold_reason(reading, bar)
    return reason if reason else phase6_status


#--- 19.7 the journal lines --------------------------------------------


def journal_plan_start(side: int, confidence: int, mood_word: str, bar: int,
                       reading: Reading, entry: float, entry_source: str,
                       stop: float, stop_source: str, target: float,
                       target_source: str, risk_reward: float, duration: str,
                       spread_pts: int, bar_time: datetime,
                       digits: int = 5) -> list[str]:
    """The two 17.8 lines, with the learning part of 19.7 inserted."""
    lines = [
        f"Emtt | Signal {p6.side_name(side)} | confidence {confidence}%"
        f" | {mood_word}, bar {bar}% | bar {fmt_time(bar_time)}"
    ]
    line = (f"Emtt | Plan {p6.side_name(side)} | confidence {confidence}%")
    learning = plan_text(reading)
    if learning:
        line += f" | {learning}"
    line += (
        f" | entry {fmt_price(entry, digits)} ({entry_source})"
        f" | stop {fmt_price(stop, digits)} ({stop_source} "
        f"{'-' if side > 0 else '+'}{p6.fmt1(p6.PLAN_STOP_BUFFER_ATR)} ATR)"
        f" | target {fmt_price(target, digits)} ({target_source})"
        f" | RR 1:{p6.fmt1(risk_reward)}"
        f" | expected {duration}"
        f" | spread {spread_pts} pts"
        f" | bar {fmt_time(bar_time)}"
    )
    lines.append(line)
    return lines


def journal_updated(labeled: int, wins: int, losses: int,
                    bar_time: datetime) -> str:
    return (
        f"Emtt | Learning updated | {labeled} labeled, {wins} wins,"
        f" {losses} losses | bar {fmt_time(bar_time)}"
    )


def journal_resumed(side: int, state: str, start_time: datetime,
                    candles_checked: int, bar_time: datetime) -> str:
    return (
        f"Emtt | Learning resumed | plan {p6.side_name(side)} {state}"
        f" | start {fmt_time(start_time)} | {candles_checked} candles checked"
        f" | bar {fmt_time(bar_time)}"
    )


def journal_result(side: int, result: str, exit_price: float, entry: float,
                   digits: int, point: float, start_sequence: int,
                   end_sequence: int, shared: bool, resumed_from_file: bool,
                   bar_time: datetime) -> str:
    """The 17.8 result line; a resume carries `resumed from file`."""
    points = 0.0
    if point > 0.0:
        points = ((exit_price - entry) if side > 0 else (entry - exit_price)) / point
    whole = mql_round(points)
    tail = ""
    if shared:
        tail += " | shared candle"
    if resumed_from_file:
        tail += " | resumed from file"
    candles = max(0, end_sequence - start_sequence)
    return (
        f"Emtt | Plan {p6.side_name(side)} result"
        f" | {p6.RESULT_NAMES[PLAN_RESULT_OF_LEARN[result]]}"
        f" | exit {fmt_price(exit_price, digits)}"
        f" | {'+' if whole >= 0 else '-'}{abs(whole)} pts | {candles} candles"
        f"{tail} | bar {fmt_time(bar_time)}"
    )


#--- 19.6 the plan across a restart ------------------------------------


@dataclass(frozen=True)
class Rate:
    """One closed candle of the copied history (series order, newest first)."""

    time: datetime
    high: float
    low: float
    close: float


@dataclass
class ResumeOutcome:
    ticket: Ticket
    result: str = RESULT_NONE
    end_price: float = 0.0
    end_time: Optional[datetime] = None
    shared: bool = False
    candles_checked: int = 0
    start_sequence: int = -1
    end_sequence: int = -1


def resume(ticket: Ticket, rates: list[Rate], newest_sequence: int,
           bar_time: datetime) -> ResumeOutcome:
    """19.6: check the gap against the plan's levels with the 17.7 rules.

    ``rates`` is the copied history in series order (index 0 = newest closed
    bar), exactly as ``CopyRates`` hands it to the replay.
    """
    outcome = ResumeOutcome(ticket=ticket)
    start_index = next(
        (i for i, rate in enumerate(rates) if rate.time == ticket.start_bar_time),
        -1,
    )
    if start_index < 0:
        outcome.result = RESULT_CHART
        if rates:
            outcome.end_price = rates[0].close
            outcome.end_time = rates[0].time
        else:
            outcome.end_time = bar_time
        return outcome
    outcome.start_sequence = newest_sequence - start_index
    working = ticket
    for index in range(start_index - 1, -1, -1):
        rate = rates[index]
        outcome.candles_checked += 1
        touches_entry = rate.low <= working.entry <= rate.high
        touches_stop = rate.low <= working.stop <= rate.high
        touches_target = rate.low <= working.target <= rate.high
        result = RESULT_NONE
        price = 0.0
        if working.state == STATE_PENDING:
            # 17.7 worse result first: stop > cancelled > missed > target.
            if touches_stop:
                result = RESULT_STOP if touches_entry else RESULT_CANCELLED
                price = working.stop
            elif touches_target:
                result = RESULT_MISSED
                price = working.target
            elif touches_entry:
                working = replace(working, state=STATE_ACTIVE,
                                  reached_bar_time=rate.time)
        else:
            if touches_stop:
                result = RESULT_STOP
                price = working.stop
            elif touches_target:
                result = RESULT_TARGET
                price = working.target
        if result != RESULT_NONE:
            touched = int(touches_entry) + int(touches_stop) + int(touches_target)
            outcome.result = result
            outcome.end_price = price
            outcome.end_time = rate.time
            outcome.shared = touched > 1
            outcome.end_sequence = newest_sequence - index
            break
    outcome.ticket = working
    return outcome


def restore_plan(ticket: Ticket, reading: Reading, mood: str,
                 newest_close: float, newest_time: datetime,
                 newest_sequence: int, point: float, digits: int) -> p6.SignalState:
    """19.6: the file's open plan becomes the live plan the panel continues with."""
    state = p6.signal_reset()
    plan = p6.plan_reset()
    plan.active = True
    plan.side = ticket.side
    plan.entry_kind = (
        p6.ENTRY_BLOCK if ticket.entry_kind == ENTRY_BLOCK else p6.ENTRY_MARKET
    )
    plan.status = STATE_ACTIVE if ticket.state == STATE_ACTIVE else STATE_PENDING
    plan.entry = ticket.entry
    plan.stop = ticket.stop
    plan.target = ticket.target
    risk = abs(ticket.entry - ticket.stop)
    plan.risk_reward = abs(ticket.target - ticket.entry) / risk if risk > 0 else 0.0
    plan.entry_source = "order block edge" if ticket.entry_kind == ENTRY_BLOCK else "market price"
    plan.start_bar_time = ticket.start_bar_time
    state.plan = plan
    state.signal = ticket.side
    state.previous_signal = ticket.side
    state.views_ready = reading.ready
    state.confidence = reading.number if reading.ready else -1
    state.combined = reading.combined * reading.scale
    state.mood = mood
    state.mood_bar = p6.mood_bar(mood)
    state.last_close = newest_close
    state.last_bar_time = newest_time
    state.last_sequence = newest_sequence
    state.point = point
    state.digits = digits
    state.initialized = True
    return state
