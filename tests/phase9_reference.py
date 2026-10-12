"""MT5-free mirror of Emtt.md 23.4-23.8 and the Phase 9 EA wiring.

Only the strictness bar is learned. The existing Phase 6 plan builder, Phase
7 feature functions, and Phase 8 trade grammar/labels remain the authorities.
Disk models checked writes, flush/close failures and atomic .tmp replacement;
all journal output is captured. No random source or decision-time clock exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import re
from typing import Optional

import phase6_reference as p6
import phase7_reference as p7
import phase8_reference as p8
from phase2_reference import BULL, BEAR

VERSION = "Emtt_Params v1"
FOLDER = "Emtt_Learning"
SUFFIX = ".params"
MOODS = p7.MOOD_ORDER
BASE_BARS = dict(zip(MOODS, (60, 70, 70, 75)))
CANDIDATES = (60, 70, 75)
MIN_SAMPLES = 20
NEAR_BAND = 10
LOOSE = 0.05
TIGHT = 0.20
MAX_LONG = (1 << 63) - 1
WRITE_EVENTS = ("init_after_load", "decision", "deinit")


def mood_cell(mood: str) -> str:
    return "TRENDING" if mood in (BULL, BEAR) else mood


def path_for(symbol: str, timeframe: str) -> str:
    return f"{FOLDER}\\{p7.sanitize(symbol)}_{p7.sanitize(timeframe)}{SUFFIX}"


@dataclass
class Cell:
    bar: int
    base: int
    a_w: int = 0
    a_l: int = 0
    n_w: int = 0
    n_l: int = 0
    moves: int = 0

    @classmethod
    def fresh(cls, mood: str) -> "Cell":
        return cls(BASE_BARS[mood], BASE_BARS[mood])

    @property
    def accepted(self) -> int:
        return self.a_w + self.a_l

    @property
    def near(self) -> int:
        return self.n_w + self.n_l

    def add_accepted(self, label: int) -> None:
        if label == 1:
            self.a_w += 1
        elif label == 0:
            self.a_l += 1

    def line(self, mood: str) -> str:
        return (f"cell {mood} | bar {self.bar} | base {self.base}"
                f" | accepted {self.a_w}/{self.a_l} | near {self.n_w}/{self.n_l}"
                f" | moves {self.moves}")


def _whole(word: str) -> int:
    if not re.fullmatch(r"[0-9]{1,19}", word):
        raise ValueError("invalid whole number")
    value = int(word)
    if value > MAX_LONG:
        raise ValueError("counter overflow")
    return value


def parse_cell(line: str, mood: str) -> Cell:
    parts = [part.strip() for part in line.split("|")]
    if len(parts) != 6 or parts[0] != "cell " + mood:
        raise ValueError("invalid cell grammar")

    def tail(index: int, key: str) -> str:
        if not parts[index].startswith(key + " "):
            raise ValueError("invalid cell key")
        return parts[index][len(key) + 1:].strip()

    bar = _whole(tail(1, "bar"))
    base = _whole(tail(2, "base"))
    if bar not in CANDIDATES or base != BASE_BARS[mood]:
        raise ValueError("unapproved bar/base")
    accepted = tail(3, "accepted").split("/")
    near = tail(4, "near").split("/")
    if len(accepted) != 2 or len(near) != 2:
        raise ValueError("invalid tally pair")
    a_w, a_l = map(_whole, accepted)
    n_w, n_l = map(_whole, near)
    if a_w + a_l > MAX_LONG or n_w + n_l > MAX_LONG:
        raise ValueError("tally overflow")
    return Cell(bar, base, a_w, a_l, n_w, n_l, _whole(tail(5, "moves")))


def decide(cell: Cell, mood: str, bar_time: datetime, journal: list[str]) -> bool:
    """23.6, inclusive boundaries without floating-point subtraction."""
    accepted, near = cell.accepted, cell.near
    if accepted < MIN_SAMPLES or near < MIN_SAMPLES:
        return False
    lhs = 100 * cell.n_w * accepted
    if lhs >= (100 * cell.a_w - 5 * accepted) * near:
        direction = -1
    elif lhs <= (100 * cell.a_w - 20 * accepted) * near:
        direction = 1
    else:
        return False
    previous = cell.bar
    index = CANDIDATES.index(previous)
    cell.bar = CANDIDATES[max(0, min(2, index + direction))]
    rate_a = p7.mql_round(100 * cell.a_w / accepted)
    rate_n = p7.mql_round(100 * cell.n_w / near)
    rates = (f"accepted {cell.a_w}/{cell.a_l} ({rate_a}%),"
             f" near {cell.n_w}/{cell.n_l} ({rate_n}%)")
    if cell.bar != previous:
        journal.append(f"Emtt | Param bar moved | {mood} {previous} -> {cell.bar}"
                       f" | {rates} | bar {p7.fmt_time(bar_time)}")
    else:
        journal.append(f"Emtt | Param bar held | {mood} at the approved limit {previous}"
                       f" | {rates} | bar {p7.fmt_time(bar_time)}")
    cell.moves += 1
    cell.a_w = cell.a_l = cell.n_w = cell.n_l = 0
    return True


class Disk(p7.Disk):
    """The three siblings share a folder, never a record or rename."""

    def __init__(self):
        super().__init__()
        self.fail_read = False
        self.fail_short_write = False
        self.fail_flush = False
        self.fail_close = False
        self.operations: list[tuple[str, str]] = []

    def exists(self, path):
        self.operations.append(("exists", path))
        return super().exists(path)

    def text(self, path):
        self.operations.append(("read", path))
        if self.fail_read:
            raise OSError("busy")
        return super().text(path)

    def write_tmp(self, path, text):
        self.operations.append(("write_tmp", path + ".tmp"))
        if self.fail_short_write:
            self.files[path + ".tmp"] = text[:len(text) // 2]
            return False
        return super().write_tmp(path, text)

    def flush_close(self, path):
        self.operations.append(("flush_close", path + ".tmp"))
        return not (self.fail_flush or self.fail_close)

    def move_over(self, path):
        self.operations.append(("rename", path))
        return super().move_over(path)


@dataclass
class ParameterFile:
    symbol: str = "EURUSD"
    timeframe: str = "M15"
    cells: dict[str, Cell] = field(default_factory=lambda: {
        mood: Cell.fresh(mood) for mood in MOODS
    })
    loaded: bool = False
    read_only: bool = False
    read_pending: bool = False
    write_failed: bool = False
    damaged_warned: set[str] = field(default_factory=set)
    journal: list[str] = field(default_factory=list)
    write_events: list[str] = field(default_factory=list)

    @property
    def path(self):
        return path_for(self.symbol, self.timeframe)

    def summary(self, bar_time: datetime) -> str:
        tickets = sum(cell.accepted for cell in self.cells.values())
        near = sum(cell.near for cell in self.cells.values())
        moves = sum(cell.moves for cell in self.cells.values())
        return (f"counts tickets {tickets} | near {near} | labeled {tickets + near}"
                f" | moves {moves} | updated {p7.fmt_time(bar_time)}")

    def render(self, bar_time: datetime) -> str:
        lines = [f"{VERSION} | {self.symbol} | {self.timeframe}", self.summary(bar_time)]
        lines.extend(self.cells[mood].line(mood) for mood in MOODS)
        return "\r\n".join(lines) + "\r\n"

    def busy(self, bar_time):
        if not self.write_failed:
            self.journal.append("Emtt | Param file busy | learning kept in memory"
                                f" | bar {p7.fmt_time(bar_time)}")
            self.write_failed = True

    def _read(self, disk: Disk, bar_time: datetime) -> bool:
        if not disk.exists(self.path):
            # Save owns the memory delta even when an unread original
            # disappeared. This is the fresh disk side of one merge.
            self.cells = {mood: Cell.fresh(mood) for mood in MOODS}
            self.read_pending = False
            self.journal.append("Emtt | Param optimization started | no file yet"
                                f" | MQL5\\Files\\{self.path}")
            return True
        try:
            text = disk.text(self.path) or ""
        except OSError:
            self.read_pending = True
            self.busy(bar_time)
            return False
        self.read_pending = False
        lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
        head = [part.strip() for part in lines[0].split("|")]
        if head != [VERSION, self.symbol, self.timeframe]:
            self.read_only = True
            self.journal.append("Emtt | Param version unknown | file untouched, base bars"
                                f" | {self.path} | bar {p7.fmt_time(bar_time)}")
            return True
        seen, broken = set(), set()
        for index, line in enumerate(lines[2:], 2):
            if not line:
                continue
            first = line.split("|")[0].strip()
            mood = first[5:] if first.startswith("cell ") else ""
            if mood not in MOODS:
                if index < 6:
                    broken.add(MOODS[index - 2])
                continue
            try:
                cell = parse_cell(line, mood)
                if mood in seen:
                    raise ValueError("duplicate cell")
                self.cells[mood] = cell
            except ValueError:
                broken.add(mood)
            seen.add(mood)
        for mood in MOODS:
            if mood not in seen or mood in broken:
                self.cells[mood] = Cell.fresh(mood)
                if mood not in self.damaged_warned:
                    self.journal.append(f"Emtt | Param file damaged | {mood} cell starts fresh"
                                        f" | {self.path} | bar {p7.fmt_time(bar_time)}")
                    self.damaged_warned.add(mood)
        moves = sum(cell.moves for cell in self.cells.values())
        self.journal.append(f"Emtt | Param optimization loaded | 4 cells | {moves} moves"
                            f" | TRENDING bar {self.cells['TRENDING'].bar} (base 60)"
                            f" | RANGING bar {self.cells['RANGING'].bar}"
                            f" | VOLATILE bar {self.cells['VOLATILE'].bar}"
                            f" | TRANSITION bar {self.cells['TRANSITION'].bar}")
        return True

    @classmethod
    def load(cls, disk, symbol, timeframe, bar_time):
        state = cls(symbol=symbol, timeframe=timeframe, loaded=True)
        state._read(disk, bar_time)
        return state

    def save(self, disk, bar_time, event):
        if event not in WRITE_EVENTS:
            raise ValueError("not a write event of 23.7")
        if not self.loaded or self.read_only:
            return False
        self.write_events.append(event)
        if self.read_pending:
            delta = {mood: replace(cell) for mood, cell in self.cells.items()}
            if not self._read(disk, bar_time) or self.read_only:
                return False
            for mood, cell in self.cells.items():
                cell.a_w += delta[mood].a_w
                cell.a_l += delta[mood].a_l
                cell.n_w += delta[mood].n_w
                cell.n_l += delta[mood].n_l
        if not disk.write_tmp(self.path, self.render(bar_time)):
            self.busy(bar_time)
            return False
        if not disk.flush_close(self.path) or not disk.move_over(self.path):
            self.busy(bar_time)
            return False
        if self.write_failed:
            self.journal.append(f"Emtt | Param file write recovered | bar {p7.fmt_time(bar_time)}")
            self.write_failed = False
        return True

    def decide(self, bar_time) -> bool:
        if self.read_pending or self.read_only:
            return False
        changed = False
        for mood in MOODS:
            if decide(self.cells[mood], mood, bar_time, self.journal):
                changed = True
        return changed


@dataclass(frozen=True)
class Parameters:
    atr: int
    er: int
    kama: tuple[int, int, int]
    structure_window: int
    volume_window: int
    bar: int
    rr_min: float

    def part(self):
        return (f"par atr {self.atr} er {self.er} kama {','.join(map(str, self.kama))}"
                f" stwin {self.structure_window} vfwin {self.volume_window}"
                f" bar {self.bar} rrmin {self.rr_min:.1f}")


def parse_parameters(tail: str) -> Optional[Parameters]:
    words = tail.split(" ")
    try:
        if (len(words) != 14 or words[::2] !=
                ["atr", "er", "kama", "stwin", "vfwin", "bar", "rrmin"]):
            return None
        def parameter_int(word):
            if not re.fullmatch(r"[0-9]{1,10}", word) or not 0 < int(word) <= (1 << 31) - 1:
                raise ValueError("invalid parameter int")
            return int(word)
        kama = tuple(parameter_int(word) for word in words[5].split(","))
        values = [parameter_int(words[i]) for i in (1, 3, 7, 9, 11)]
        if (len(kama) != 3 or any(value <= 0 for value in kama + tuple(values[:4]))
                or values[4] not in CANDIDATES or words[13] not in ("1.5", "2.0")):
            return None
        return Parameters(values[0], values[1], kama, values[2], values[3],
                          values[4], float(words[13]))
    except ValueError:
        return None


@dataclass
class ParameterTicket:
    trade: p8.TradeTicket
    parameters: Optional[Parameters] = None


def ticket_line(ticket: ParameterTicket, enabled: bool, digits=5) -> str:
    line = p8.trade_ticket_line(ticket.trade, digits)
    if enabled and ticket.parameters is not None:
        line += " | " + ticket.parameters.part()
    return line


def strip_parameter_parts(line: str) -> str:
    """The forward-compatible Phase 8 reader reads past author-only metadata."""
    return " | ".join(part.strip() for part in line.split("|")
                      if part.strip() != "par" and not part.strip().startswith("par "))


def phase8_read_ticket(line, digits=5):
    return p8.parse_trade_ticket_line(strip_parameter_parts(line), digits)


def parse_ticket(line, digits=5):
    trade = phase8_read_ticket(line, digits)
    parameters = None
    for part in line.split("|"):
        if part.strip().startswith("par ") and parameters is None:
            parameters = parse_parameters(part.strip()[4:])
    return ParameterTicket(trade, parameters)


def accepted_label(ticket: p8.TradeTicket) -> Optional[int]:
    """The unchanged MQL5 EmttLearnLabelOf: real net dominates paper levels."""
    if ticket.trade_filled is not None:
        if ticket.trade_closed is None:
            return None
        net = ticket.trade_net_points or 0
        return 1 if net > 0 else 0 if net < 0 else None
    return p7.label_of(ticket.plan)


@dataclass
class Near:
    plan: p6.Plan
    mood: str
    confidence: int
    bar: int
    digits: int
    point: float
    last_bar_time: datetime


@dataclass(frozen=True)
class Accepted:
    key: tuple
    timeframe: str
    mood: str
    label: int
    result_time: datetime


class Optimizer:
    """One EA session; effective bars and private paper state are memory-only."""

    def __init__(self, disk: Disk, bar_time: datetime, *, enabled=True,
                 symbol="EURUSD", timeframe="M15"):
        self.disk = disk
        self.enabled = enabled
        self.symbol = symbol
        self.timeframe = timeframe
        self.replaying = False
        self.live_candle = False
        self.last_live_bar_time = None
        self.file = ParameterFile(symbol=symbol, timeframe=timeframe)
        self.carried_file = None
        self.effective = BASE_BARS.copy()
        self.frozen_bar = None
        self.near = None
        self.pending: list[Accepted] = []
        self.seen: list[tuple] = []
        self.journal: list[str] = []
        if enabled:
            self.file = ParameterFile.load(disk, symbol, timeframe, bar_time)
            self.file.save(disk, bar_time, "init_after_load")
            self.effective = {mood: cell.bar for mood, cell in self.file.cells.items()}

    def learned_bar(self, mood):
        if not self.enabled or not self.file.loaded or mood_cell(mood) not in MOODS:
            return 0
        return self.frozen_bar or self.effective[mood_cell(mood)]

    def gate_bar(self, mood):
        return self.learned_bar(mood) or p6.mood_bar(mood)

    def freeze_at_entry(self, bar):
        if self.enabled and self.frozen_bar is None and bar in CANDIDATES:
            self.frozen_bar = bar

    def trade_entry_bar(self, restored_base, *, position_open):
        # The EA restores this strictness field before calling the otherwise
        # byte-identical Phase 8 manager. No parameter-ticket part is read.
        return self.frozen_bar if self.enabled and position_open and self.frozen_bar else restored_base

    def begin_candle(self, bar_time, position_open=False, entry_bar=0):
        if (not self.enabled or self.replaying or not self.file.loaded
                or self.timeframe not in p6.TIMEFRAME_MINUTES
                or (self.last_live_bar_time is not None and bar_time <= self.last_live_bar_time)):
            return False
        if position_open:
            self.freeze_at_entry(entry_bar)
        else:
            self.frozen_bar = None
            self.effective = {mood: cell.bar for mood, cell in self.file.cells.items()}
        self.last_live_bar_time = bar_time
        self.live_candle = True
        return True

    def queue_accepted(self, ticket: p8.TradeTicket, timeframe, result_time, *, symbol=None):
        label = accepted_label(ticket)
        key = (timeframe, ticket.plan.start_bar_time, ticket.plan.side)
        if (not self.enabled or self.replaying or not self.file.loaded or label is None
                or (symbol is not None and symbol != self.file.symbol)
                or ticket.plan.start_bar_time is None or ticket.plan.side not in (-1, 1)
                or ticket.plan.mood not in MOODS or timeframe not in p6.TIMEFRAME_MINUTES
                or key in self.seen or any(event.key == key for event in self.pending)
                or len(self.pending) >= p7.LEARN_CAP):
            return False
        self.pending.append(Accepted(key, timeframe, ticket.plan.mood, label, result_time))
        return True

    def _take_accepted(self, file, bar_end):
        changed = False
        kept = []
        for event in self.pending:
            if event.timeframe != file.timeframe or event.result_time > bar_end:
                kept.append(event)
                continue
            file.cells[event.mood].add_accepted(event.label)
            self.seen.append(event.key)
            self.seen = self.seen[-p7.LEARN_CAP:]
            changed = True
        self.pending = kept
        return changed

    def _consume_accepted(self, bar_time, *, bar_end=None, allow_decision=True):
        self.pending.sort(key=lambda event: event.result_time)
        if bar_end is None:
            bar_end = bar_time + timedelta(minutes=p6.TIMEFRAME_MINUTES[self.timeframe])
        self._take_accepted(self.file, bar_end)
        for timeframe in p6.TIMEFRAME_MINUTES:
            if timeframe == self.timeframe or not any(
                event.timeframe == timeframe and event.result_time <= bar_end
                for event in self.pending
            ):
                continue
            if self.carried_file is None or self.carried_file.timeframe != timeframe:
                if self.carried_file is not None:
                    self.carried_file.save(self.disk, bar_time, "deinit")
                self.carried_file = ParameterFile.load(self.disk, self.symbol, timeframe, bar_time)
                self.carried_file.save(self.disk, bar_time, "init_after_load")
            self._take_accepted(self.carried_file, bar_end)
            if allow_decision and self.carried_file.decide(bar_time):
                self.carried_file.save(self.disk, bar_time, "decision")

    def end_near(self, result, exit_price, sequence, bar_time, shared=False):
        if not self.enabled or self.near is None:
            return False
        near = self.near
        cell = self.file.cells[near.mood]
        labeled = result in (p7.RESULT_TARGET, p7.RESULT_STOP)
        if labeled and not self.replaying and self.live_candle:
            if result == p7.RESULT_TARGET:
                cell.n_w += 1
            else:
                cell.n_l += 1
        points = p7.mql_round((exit_price - near.plan.entry) * near.plan.side / near.point) \
            if near.point > 0 else 0
        candles = max(0, sequence - near.plan.start_sequence)
        self.journal.append(f"Emtt | Near miss result | {result} | {points:+d} pts"
                            f" | {candles} candles | {near.mood} near {cell.n_w}/{cell.n_l}"
                            f"{' | shared candle' if shared else ''} | bar {p7.fmt_time(bar_time)}")
        self.near = None
        return labeled and not self.replaying and self.live_candle

    def watch_near(self, signal, candle, sequence, bar_time):
        if (not self.enabled or self.replaying or not self.live_candle
                or self.near is None or bar_time <= self.near.plan.start_bar_time
                or bar_time <= self.near.last_bar_time):
            return False
        self.near.last_bar_time = bar_time
        if not signal.views_ready:
            self.end_near(p7.RESULT_CHART, candle.close, sequence, bar_time)
            return True
        plan = self.near.plan
        entry = candle.low <= plan.entry <= candle.high
        stop = candle.low <= plan.stop <= candle.high
        target = candle.low <= plan.target <= candle.high
        shared = sum((entry, stop, target)) > 1
        result, exit_price = p7.RESULT_NONE, candle.close
        if plan.status == p6.PLAN_PENDING:
            if stop:
                result = p7.RESULT_STOP if entry else p7.RESULT_CANCELLED
                exit_price = plan.stop
            elif target:
                result, exit_price = p7.RESULT_MISSED, plan.target
            elif entry:
                plan.status = p6.PLAN_ACTIVE
        else:
            if stop:
                result, exit_price = p7.RESULT_STOP, plan.stop
            elif target:
                result, exit_price = p7.RESULT_TARGET, plan.target
        if result:
            self.end_near(result, exit_price, sequence, bar_time, shared)
            return True
        number = signal.confidence if signal.combined * plan.side > 0 else 0
        if number < signal.mood_bar - p6.SIG_STAY_MARGIN:
            self.end_near(p7.RESULT_SIGNAL, candle.close, sequence, bar_time)
            return True
        return False

    def consider_near(self, signal, trend, structure, flow, atr, candle,
                      bid, ask, sequence, bar_time):
        if (not self.enabled or self.replaying or not self.live_candle
                or signal.plan.active or signal.just_ended or not signal.views_ready
                or signal.mood_bar <= 0 or signal.confidence >= signal.mood_bar
                or signal.confidence < signal.mood_bar - NEAR_BAND):
            return False
        side = 1 if signal.combined > 0 else -1 if signal.combined < 0 else 0
        if not side:
            return False
        plan, fail = p6.build_plan(side, structure, flow, trend, atr, candle.close,
                                   bid, ask, signal.mood, self.timeframe)
        if plan is None or fail:
            return False
        replacing = self.near is not None
        previous = (f" | previous {p6.side_name(self.near.plan.side)} from "
                    f"{p7.fmt_time(self.near.plan.start_bar_time)}") if replacing else ""
        plan.start_sequence = sequence
        plan.start_bar_time = bar_time
        plan.start_close = candle.close
        self.near = Near(plan, mood_cell(signal.mood), signal.confidence,
                         signal.mood_bar, signal.digits, signal.point, bar_time)
        self.journal.append(f"Emtt | Near miss {'replaced' if replacing else 'started'}"
                            f" | {p6.side_name(side)} | confidence {signal.confidence}%, bar {signal.mood_bar}%"
                            f" | entry {p7.fmt_price(plan.entry, signal.digits)}"
                            f" | stop {p7.fmt_price(plan.stop, signal.digits)}"
                            f" | target {p7.fmt_price(plan.target, signal.digits)}"
                            f" | RR 1:{p6.fmt1(plan.risk_reward)}{previous}"
                            f" | bar {p7.fmt_time(bar_time)}")
        return True

    def advance(self, signal, trend, structure, flow, atr, candle, bid, ask,
                sequence, bar_time, *, position_open=False, entry_bar=0, replay=False):
        if replay or not self.begin_candle(bar_time, position_open, entry_bar):
            return False
        # Mirrors only 23.3a: all other fields and real signal/plan events
        # arrive from the existing engine, never from the private near idea.
        signal = replace(signal, mood_bar=self.gate_bar(signal.mood))
        self._consume_accepted(bar_time)
        if not self.watch_near(signal, candle, sequence, bar_time):
            self.consider_near(signal, trend, structure, flow, atr, candle,
                               bid, ask, sequence, bar_time)
        decision = self.file.decide(bar_time)
        if decision:
            self.file.save(self.disk, bar_time, "decision")
        self.live_candle = False
        return decision

    def deinit(self, bar_time):
        if not self.enabled or self.replaying:
            return
        stamp = max([bar_time] + [event.result_time for event in self.pending])
        self._consume_accepted(stamp, bar_end=stamp, allow_decision=False)
        self.file.save(self.disk, stamp, "deinit")
        if self.carried_file is not None:
            self.carried_file.save(self.disk, stamp, "deinit")
        self.near = None  # deliberately not persisted (23.5)
