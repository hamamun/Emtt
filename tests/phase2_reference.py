"""Portable reference functions for Phase 2's pure decision logic.

These functions intentionally have no MT5 dependency so CI can exercise the
thresholds and calendar rules on every platform.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

UTC = timezone.utc

LOW = "LOW"
NORMAL = "NORMAL"
HIGH = "HIGH"
UNKNOWN = "UNKNOWN"

BULL = "TRENDING_BULLISH"
BEAR = "TRENDING_BEARISH"
RANGING = "RANGING"
VOLATILE = "VOLATILE"
TRANSITION = "TRANSITION"
CLOSED = "MARKET_CLOSED"
TRENDING = {BULL, BEAR}


def percentile_rank(value: float, references: Iterable[float]) -> float:
    """Mid-rank percentile of a newest value against its reference sample.

    Mid-rank ties make a constant ATR series NORMAL (50th percentile), rather
    than spuriously HIGH because every observation is <= the newest value.
    """
    sample = list(references)
    if not sample or value <= 0 or any(x <= 0 for x in sample):
        raise ValueError("ATR percentile needs positive observations")
    below = sum(x < value for x in sample)
    equal = sum(x == value for x in sample)
    return 100.0 * (below + 0.5 * equal) / len(sample)


def initial_volatility_bucket(percentile: float) -> str:
    if percentile > 70:
        return HIGH
    if percentile < 30:
        return LOW
    return NORMAL


def volatility_target(current: str, percentile: float) -> str:
    """Hysteretic adjacent bucket target; callers also apply cooldowns."""
    if current == LOW:
        return NORMAL if percentile > 33 else LOW
    if current == HIGH:
        return NORMAL if percentile < 67 else HIGH
    if percentile > 70:
        return HIGH
    if percentile < 30:
        return LOW
    return NORMAL


def _first_sunday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7)


def _nth_sunday(year: int, month: int, n: int) -> date:
    return _first_sunday(year, month) + timedelta(days=7 * (n - 1))


def _last_sunday(year: int, month: int) -> date:
    if month == 12:
        first_next = date(year + 1, 1, 1)
    else:
        first_next = date(year, month + 1, 1)
    last = first_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def london_dst_utc(utc: datetime) -> bool:
    utc = utc.astimezone(UTC)
    start = datetime.combine(_last_sunday(utc.year, 3), time(1), UTC)
    end = datetime.combine(_last_sunday(utc.year, 10), time(1), UTC)
    return start <= utc < end


def new_york_dst_utc(utc: datetime) -> bool:
    utc = utc.astimezone(UTC)
    start = datetime.combine(_nth_sunday(utc.year, 3, 2), time(7), UTC)
    end = datetime.combine(_first_sunday(utc.year, 11), time(6), UTC)
    return start <= utc < end


def sydney_dst_utc(utc: datetime) -> bool:
    utc = utc.astimezone(UTC)
    first_october = _first_sunday(utc.year, 10)
    first_april = _first_sunday(utc.year, 4)
    start = datetime.combine(first_october, time(16), UTC) - timedelta(days=1)
    end = datetime.combine(first_april, time(16), UTC) - timedelta(days=1)
    return utc >= start or utc < end


def _local_window_contains(
    utc: datetime, local_day: date, start_hour: int, end_hour: int, offset_hours: int
) -> bool:
    local_midnight_as_utc = datetime.combine(local_day, time(), UTC)
    start = local_midnight_as_utc + timedelta(hours=start_hour - offset_hours)
    end = local_midnight_as_utc + timedelta(hours=end_hour - offset_hours)
    return start <= utc < end


def _sydney_dst_on_local_date(day: date) -> bool:
    start = _first_sunday(day.year, 10)
    end = _first_sunday(day.year, 4)
    if day.month > 10 or day.month < 4:
        return True
    if day.month == 10 and day.day >= start.day:
        return True
    if day.month == 4 and day.day < end.day:
        return True
    return False


def _london_dst_on_local_date(day: date) -> bool:
    if 4 <= day.month <= 9:
        return True
    if day.month == 3:
        return day.day >= _last_sunday(day.year, 3).day
    if day.month == 10:
        return day.day < _last_sunday(day.year, 10).day
    return False


def _new_york_dst_on_local_date(day: date) -> bool:
    if 4 <= day.month <= 10:
        return True
    if day.month == 3:
        return day.day >= _nth_sunday(day.year, 3, 2).day
    if day.month == 11:
        return day.day < _first_sunday(day.year, 11).day
    return False


def session_names(utc: datetime) -> str:
    """Return active session names; an Asia fallback keeps open time named."""
    utc = utc.astimezone(UTC)
    labels: set[str] = set()
    for day_delta in (-1, 0, 1):
        local_day = utc.date() + timedelta(days=day_delta)

        sydney_offset = 11 if _sydney_dst_on_local_date(local_day) else 10
        sydney_open = datetime.combine(local_day, time(7), UTC) - timedelta(
            hours=sydney_offset
        )
        tokyo_close = datetime.combine(local_day, time(18), UTC) - timedelta(hours=9)
        if sydney_open <= utc < tokyo_close:
            labels.add("Asia")

        london_offset = 1 if _london_dst_on_local_date(local_day) else 0
        if _local_window_contains(utc, local_day, 7, 16, london_offset):
            labels.add("London")

        ny_offset = -4 if _new_york_dst_on_local_date(local_day) else -5
        if _local_window_contains(utc, local_day, 7, 16, ny_offset):
            labels.add("NY")

    ordered = [name for name in ("Asia", "London", "NY") if name in labels]
    return "/".join(ordered) if ordered else "Asia"


@dataclass(frozen=True)
class Measurements:
    efficiency: float
    atr_ratio: float
    direction: int = 0
    bands_expanding: bool = False


def regime_candidate(
    m: Measurements, previous: str = UNKNOWN, market_closed: bool = False
) -> str:
    if market_closed:
        return CLOSED

    was_trending = previous in TRENDING
    if was_trending:
        if m.efficiency >= 58 and m.direction:
            return BULL if m.direction > 0 else BEAR
    elif m.efficiency > 62 and m.direction:
        return BULL if m.direction > 0 else BEAR

    if previous == VOLATILE:
        if m.atr_ratio >= 1.3 and not m.direction:
            return VOLATILE
    elif m.atr_ratio > 1.5 and m.bands_expanding and not m.direction:
        return VOLATILE

    if previous == RANGING:
        if m.efficiency <= 32:
            return RANGING
    elif m.efficiency < 28:
        return RANGING
    return TRANSITION


class RegimeTracker:
    """Two-closed-bar regime confirmation with immediate first evaluation."""

    def __init__(self) -> None:
        self.stable = UNKNOWN
        self.pending = UNKNOWN
        self.pending_bars = 0
        self.initialized = False

    def advance(self, m: Measurements, first_evaluation: bool = False) -> str:
        if first_evaluation or not self.initialized:
            self.stable = regime_candidate(m)
            self.pending = UNKNOWN
            self.pending_bars = 0
            self.initialized = True
            return self.stable

        candidate = regime_candidate(m, self.stable)
        if candidate == self.stable:
            self.pending = UNKNOWN
            self.pending_bars = 0
            return self.stable
        if candidate == self.pending:
            self.pending_bars += 1
        else:
            self.pending = candidate
            self.pending_bars = 1
        if self.pending_bars >= 2:
            self.stable = candidate
            self.pending = UNKNOWN
            self.pending_bars = 0
        return self.stable

    def market_closed(self) -> str:
        self.stable = CLOSED
        self.pending = UNKNOWN
        self.pending_bars = 0
        self.initialized = True
        return self.stable
