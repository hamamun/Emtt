"""Portable reference logic for Emtt Phase 5 (Emtt.md sections 15.3-15.12).

Phase 5 has two components: the closed-bar **volume flow** (session VWAP,
40-bin volume profile with POC / VAH / VAL, the previous session's naked POC,
the close-position CVD and ``volumeFlowScore``) and the **higher-timeframe
agreement** re-run of the Phase 2 / 3 / 4 stack on the HTF's own closed bars
and its published ``mtfScore``.

Everything here is MT5-free and mirrors the production rules:

* series convention is MQL5's - ``index 0`` is the newest *closed* bar and
  larger indices are older bars, exactly as ``CopyRates`` fills them;
* the session anchor is a pure function of the bar time and the Phase 2
  calendar (Sydney / London / New York DST rules are imported from
  ``phase2_reference`` - never restated);
* Layer 2 scaling uses ``round_half_away`` from ``phase4_reference`` - Python's
  ``round()`` is never used for a resolved parameter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math
from typing import Optional, Sequence

from phase2_reference import (
    BEAR,
    BULL,
    CLOSED,
    HIGH,
    LOW,
    NORMAL,
    RANGING,
    TRANSITION,
    TRENDING,
    UNKNOWN,
    VOLATILE,
    Measurements,
    RegimeTracker,
    _london_dst_on_local_date,
    _new_york_dst_on_local_date,
    _sydney_dst_on_local_date,
)
from phase3_reference import SupertrendTracker, cluster_name, lookback_scale
from phase4_reference import (
    ASSET_CLASSES,
    BOS,
    CHOCH,
    VOLATILITIES,
    SmcTracker,
    can_change_at,
    round_half_away,
    smc_history_required,
    supertrend_history_required,
)

UTC = timezone.utc

#--- 15.5 - 15.11 fixed constants -------------------------------------------
BINS = 40
VALUE_AREA = 0.70
CVD_WINDOW = 10
CVD_FLIP = 0.25
CONTROL_SCALE = 0.5
MAGNET_ATRS = 3.0
WEIGHT_CONTROL = 0.35
WEIGHT_FAIR = 0.25
WEIGHT_VALUE = 0.20
WEIGHT_MAGNET = 0.20
SESSION_DEPTH = 160
FETCH_BUFFER = 10
WINDOW_MIN = 50
WINDOW_MAX = 400
PRIOR_POC_MIN_BARS = 2
STATUS_FRESH_BARS = 3

#--- 15.8 - 15.10 fixed constants -------------------------------------------
MTF_FETCH_BUFFER = 10
MTF_WEIGHT_DIRECTION = 0.50
MTF_WEIGHT_REGIME = 0.30
MTF_WEIGHT_STRUCTURE = 0.20
MTF_STATUS_FRESH_BARS = 3
MTF_MAP = {"M5": "M15", "M15": "H1", "M30": "H4"}

#--- 15.10 panel wording ----------------------------------------------------
ROW10_CONTEXT_ONLY = "Watching — context only, no signal yet"
ROW10_SMC_CONTEXT_ONLY = "Watching — structure context only, no signal yet"
ROW10_INCOMPATIBLE = "Incompatible chart. Switch to M5/M15/M30."
ROW10_LOADING = "Waiting — Loading chart history"
ROW10_MARKET_CLOSED = "Paused — Waiting for market to open"

SESSION_ASIA = 0
SESSION_LONDON = 1
SESSION_NY = 2
SESSION_LABELS = ("Asia", "London", "NY")

FLOW_UP = 1
FLOW_DOWN = -1
FLOW_FLAT = 0
FLOW_NAMES = {FLOW_UP: "up", FLOW_DOWN: "down", FLOW_FLAT: "flat"}

MAGNET_NONE = ""
MAGNET_POC = "POC"
MAGNET_NAKED_POC = "naked POC"
MAGNET_VAH = "VAH"
MAGNET_VAL = "VAL"
# 15.5: an exact distance tie prefers, in this order.
MAGNET_PRIORITY = (MAGNET_NAKED_POC, MAGNET_POC, MAGNET_VAH, MAGNET_VAL)

SIDE_NONE = ""
SIDE_ABOVE = "above"
SIDE_BELOW = "below"

TIMEFRAME_SECONDS = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}

BIG = 1_000_000


@dataclass(frozen=True)
class Bar:
    """A closed bar with its tick volume; series order (0 = newest)."""

    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def period_seconds(timeframe: str) -> int:
    return TIMEFRAME_SECONDS.get(timeframe, 0)


#==== 15.3 session anchor (the 9.2.7 calendar, reused) ======================

def session_open_utc(local_day: date, session: int) -> datetime:
    """07:00 Sydney / London / New York local, expressed in UTC."""
    if session == SESSION_ASIA:
        offset = 11 if _sydney_dst_on_local_date(local_day) else 10
        return datetime.combine(local_day, datetime.min.time(), UTC) + timedelta(
            hours=7 - offset
        )
    if session == SESSION_LONDON:
        offset = 1 if _london_dst_on_local_date(local_day) else 0
        return datetime.combine(local_day, datetime.min.time(), UTC) + timedelta(
            hours=7 - offset
        )
    offset = -4 if _new_york_dst_on_local_date(local_day) else -5
    return datetime.combine(local_day, datetime.min.time(), UTC) + timedelta(
        hours=7 - offset
    )


def session_window_contains(utc: datetime, local_day: date, session: int) -> bool:
    """Asia closes at 18:00 Tokyo (09:00 UTC); London / NY run nine hours."""
    opened = session_open_utc(local_day, session)
    if session == SESSION_ASIA:
        closed = datetime.combine(local_day, datetime.min.time(), UTC) + timedelta(
            hours=18 - 9
        )
    else:
        closed = opened + timedelta(hours=9)
    return opened <= utc < closed


def session_anchor(utc: datetime) -> Optional[datetime]:
    """Latest open among the sessions whose window contains ``utc`` (15.3).

    Candidate days are the time's day, the previous day and the next day: the
    Asia open (07:00 Sydney local) falls on the previous UTC date, so the
    late-UTC hours of a Sydney calendar day still anchor to that day's own
    Asia open. A daylight-saving seam can leave a time inside no window at all;
    the deterministic fallback is the newest open at or before the time, else
    the oldest candidate open.
    """
    best: Optional[datetime] = None
    latest_earlier: Optional[datetime] = None
    earliest: Optional[datetime] = None
    for day_offset in (1, 0, -1):
        local_day = utc.date() + timedelta(days=day_offset)
        for session in (SESSION_ASIA, SESSION_LONDON, SESSION_NY):
            opened = session_open_utc(local_day, session)
            if earliest is None or opened < earliest:
                earliest = opened
            if session_window_contains(utc, local_day, session):
                if best is None or opened > best:
                    best = opened
            if opened <= utc and (latest_earlier is None or opened > latest_earlier):
                latest_earlier = opened
    if best is not None:
        return best
    return latest_earlier if latest_earlier is not None else earliest


def previous_anchor(anchor: datetime) -> Optional[datetime]:
    """The session whose anchor is the newest one strictly before ``anchor``."""
    best: Optional[datetime] = None
    for day_offset in (1, 0, -1, -2):
        local_day = anchor.date() + timedelta(days=day_offset)
        for session in (SESSION_ASIA, SESSION_LONDON, SESSION_NY):
            opened = session_open_utc(local_day, session)
            if opened < anchor and (best is None or opened > best):
                best = opened
    return best


def session_label(anchor: datetime) -> str:
    """The market whose open is this anchor: Asia / London / NY."""
    for day_offset in (1, 0, -1, -2):
        local_day = anchor.date() + timedelta(days=day_offset)
        for session in (SESSION_ASIA, SESSION_LONDON, SESSION_NY):
            if anchor == session_open_utc(local_day, session):
                return SESSION_LABELS[session]
    return "--"


def session_run_end(bars: Sequence[Bar], index: int, anchor: datetime) -> int:
    """Exclusive end of the contiguous run of bars anchored to ``anchor``."""
    current = index
    total = len(bars)
    while current < total and session_anchor(bars[current].time) == anchor:
        current += 1
    return current


#==== 15.5 volume profile ===================================================

@dataclass(frozen=True)
class Profile:
    """One 40-bin profile; ``poc`` is None when the window is not readable."""

    low: float
    high: float
    total_volume: float
    poc: Optional[float] = None
    vah: Optional[float] = None
    val: Optional[float] = None
    poc_bin: int = -1
    top_bin: int = -1
    bottom_bin: int = -1

    @property
    def readable(self) -> bool:
        return self.poc is not None


def bin_index(price: float, range_low: float, width: float) -> int:
    """The single bin holding the price; the top edge is clamped to 39."""
    if width <= 0:
        raise ValueError("bin width must be positive")
    index = math.floor((price - range_low) / width)
    return max(0, min(BINS - 1, index))


def compute_profile(bars: Sequence[Bar]) -> Profile:
    """15.5 binning, POC, the 70% value area and its edge prices."""
    low = min(bar.low for bar in bars)
    high = max(bar.high for bar in bars)
    total = sum(bar.volume for bar in bars)
    if high <= low or total <= 0:
        return Profile(low=low, high=high, total_volume=total)

    width = (high - low) / BINS
    bins = [0.0] * BINS
    for bar in bars:
        typical = (bar.high + bar.low + bar.close) / 3.0
        bins[bin_index(typical, low, width)] += bar.volume

    poc_bin = 0
    for candidate in range(1, BINS):
        if bins[candidate] > bins[poc_bin]:  # an exact tie keeps the lower bin
            poc_bin = candidate

    top_bin = bottom_bin = poc_bin
    area = bins[poc_bin]
    target = VALUE_AREA * total
    while area < target:
        has_above = top_bin + 1 < BINS
        has_below = bottom_bin - 1 >= 0
        if not has_above and not has_below:
            break
        if has_above and has_below:
            take_above = bins[top_bin + 1] > bins[bottom_bin - 1]
        else:
            take_above = has_above
        if take_above:
            top_bin += 1
            area += bins[top_bin]
        else:
            bottom_bin -= 1
            area += bins[bottom_bin]

    return Profile(
        low=low,
        high=high,
        total_volume=total,
        poc=low + (poc_bin + 0.5) * width,
        vah=low + (top_bin + 1) * width,
        val=low + bottom_bin * width,
        poc_bin=poc_bin,
        top_bin=top_bin,
        bottom_bin=bottom_bin,
    )


#==== 15.6 CVD ==============================================================

def bar_delta(bar: Bar) -> float:
    """close-position estimate: +volume at the high, -volume at the low."""
    span = bar.high - bar.low
    if span <= 0:
        return 0.0
    return bar.volume * (2.0 * (bar.close - bar.low) / span - 1.0)


def classify_flow(window_bars: Sequence[Bar]) -> Optional[int]:
    """+1 / -1 / 0 over the newest session bars; None when not readable."""
    if len(window_bars) < 2:
        return None
    window_volume = sum(bar.volume for bar in window_bars)
    net_delta = sum(bar_delta(bar) for bar in window_bars)
    if window_volume <= 0:
        return None
    if net_delta >= CVD_FLIP * window_volume:
        return FLOW_UP
    if net_delta <= -CVD_FLIP * window_volume:
        return FLOW_DOWN
    return FLOW_FLAT


def flow_name(direction: int) -> str:
    return FLOW_NAMES[direction]


#==== 15.5 the magnet set and 15.7 the score ================================

def magnet_members(
    *,
    has_profile: bool,
    poc: Optional[float],
    vah: Optional[float],
    val: Optional[float],
    prior_poc: Optional[float],
    naked: bool,
) -> list[tuple[str, float]]:
    """Present magnet members in the 15.5 tie-preference order."""
    members: list[tuple[str, float]] = []
    if prior_poc is not None and naked:
        members.append((MAGNET_NAKED_POC, prior_poc))
    if has_profile and poc is not None:
        members.append((MAGNET_POC, poc))
        members.append((MAGNET_VAH, vah))
        members.append((MAGNET_VAL, val))
    return members


def published_magnet(
    members: Sequence[tuple[str, float]], close: float
) -> Optional[tuple[str, float]]:
    """Nearest member by |close - level|; a tie keeps the earlier candidate."""
    best: Optional[tuple[str, float]] = None
    best_distance = 0.0
    for kind, level in members:
        distance = abs(close - level)
        if best is None or distance < best_distance:
            best = (kind, level)
            best_distance = distance
    return best


def nearest_directional_magnet(
    members: Sequence[tuple[str, float]], close: float, flow_direction: int
) -> Optional[float]:
    """Distance to the nearest member at or beyond the close, in the flow
    direction - the set the score's proximity term reads (15.7)."""
    best: Optional[float] = None
    for _, level in members:
        if flow_direction > 0 and level < close:
            continue
        if flow_direction < 0 and level > close:
            continue
        distance = abs(close - level)
        if best is None or distance < best:
            best = distance
    return best


def volume_flow_score(
    *,
    ready: bool,
    flow_direction: int,
    net_delta: float,
    window_volume: float,
    has_vwap: bool,
    price_vs_vwap: str,
    has_profile: bool,
    close: float,
    val: Optional[float],
    vah: Optional[float],
    atr_value: float,
    members: Sequence[tuple[str, float]],
) -> float:
    """The four weighted terms of 15.7, clamped, zero when flat or unready."""
    if not ready or flow_direction == 0 or window_volume <= 0:
        return 0.0

    directional = net_delta if flow_direction > 0 else -net_delta
    control = clamp01(directional / (CONTROL_SCALE * window_volume))

    fair = 0.0
    if has_vwap:
        if flow_direction > 0 and price_vs_vwap == SIDE_ABOVE:
            fair = 1.0
        elif flow_direction < 0 and price_vs_vwap == SIDE_BELOW:
            fair = 1.0

    area = 0.0
    magnet = 0.0
    if has_profile and val is not None and vah is not None:
        if flow_direction > 0:
            area = 1.0 if close < val else 0.5 if close <= vah else 0.0
        else:
            area = 1.0 if close > vah else 0.5 if close >= val else 0.0
        if atr_value > 0:
            nearest = nearest_directional_magnet(members, close, flow_direction)
            if nearest is not None:
                magnet = clamp01(1.0 - (nearest / atr_value) / MAGNET_ATRS)

    return clamp01(
        WEIGHT_CONTROL * control
        + WEIGHT_FAIR * fair
        + WEIGHT_VALUE * area
        + WEIGHT_MAGNET * magnet
    )


def clamp01(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


#==== 15.11 parameters ======================================================

def matrix_window(asset_class: str, volatility: str) -> int:
    """Layer 1 base matrix: the volume profile window (closed bars)."""
    high = volatility == HIGH
    low = volatility == LOW
    if asset_class == "Metals":
        return 300 if high else 150 if low else 200
    if asset_class == "Indices":
        return 250 if high else 150 if low else 200
    if asset_class == "Crypto":
        return 200 if high else 100 if low else 150
    # Forex Major, Forex Cross and Generic share this matrix.
    return 300 if high else 200


def profile_window(asset_class: str, volatility: str, timeframe: str) -> int:
    """Layer 2 scales the profile window only; the result is clamped."""
    base = matrix_window(asset_class, volatility)
    window = round_half_away(base * lookback_scale(timeframe))
    return max(WINDOW_MIN, min(WINDOW_MAX, window))


def vf_history_required(asset_class: str, volatility: str, timeframe: str) -> int:
    return profile_window(asset_class, volatility, timeframe) + 2


def vf_fetch_depth(asset_class: str, volatility: str, timeframe: str) -> int:
    return (
        profile_window(asset_class, volatility, timeframe)
        + SESSION_DEPTH
        + FETCH_BUFFER
    )


def smc_history_required_worst(timeframe: str) -> int:
    """The overload used before a bucket exists: the same matrix's maximum."""
    return max(
        smc_history_required(asset_class, volatility, timeframe)
        for asset_class in ASSET_CLASSES
        for volatility in VOLATILITIES
    )


def combined_history_required(asset_class: str, volatility: str, timeframe: str) -> int:
    """15.11: one gate, the three-term max() through one code path."""
    return max(
        supertrend_history_required(timeframe),
        smc_history_required(asset_class, volatility, timeframe),
        vf_history_required(asset_class, volatility, timeframe),
    )


#==== 15.3 - 15.7 the volume-flow lifecycle =================================

@dataclass
class VolumeFlowReading:
    """The published contract of 15.7 (readings plus the facts behind them)."""

    ready: bool = False
    session_anchor: Optional[datetime] = None
    session_name: str = ""
    bars_since_session_start: int = 0
    cvd: float = 0.0
    flow_direction: int = FLOW_FLAT
    flow_reading: bool = False
    window_volume: float = 0.0
    net_delta: float = 0.0
    has_vwap: bool = False
    vwap: float = 0.0
    price_vs_vwap: str = SIDE_NONE
    distance_vwap_atrs: float = 0.0
    has_profile: bool = False
    profile_window: int = 0
    poc: Optional[float] = None
    vah: Optional[float] = None
    val: Optional[float] = None
    window_low: float = 0.0
    window_high: float = 0.0
    profile_volume: float = 0.0
    prior_poc: Optional[float] = None
    prior_poc_naked: bool = False
    magnet_kind: str = MAGNET_NONE
    magnet_price: float = 0.0
    distance_magnet_atrs: float = 0.0
    volume_flow_score: float = 0.0
    atr_period: int = 0
    atr_value: float = 0.0
    last_close: float = 0.0


class VolumeFlowTracker:
    """Closed-bar mirror of ``EmttVolumeFlowAdvance`` (15.3 - 15.7, 15.12)."""

    def __init__(
        self,
        asset_class: str = "Forex Major",
        timeframe: str = "M5",
        volatility: str = NORMAL,
        digits: int = 5,
    ) -> None:
        self.asset_class = asset_class
        self.timeframe = timeframe
        self.volatility = volatility
        self.digits = digits
        self.parameters_initialized = False
        self.applied_volatility = UNKNOWN
        self.window = 0
        self.last_window_change_bar = -BIG
        self.current_sequence = 0
        self.reading = VolumeFlowReading()
        self.initialized = False
        self.last_bar_time: Optional[datetime] = None
        self.last_flow_direction: Optional[int] = None
        self.flip_direction = 0
        self.flip_sequence = -BIG
        self.flip_time: Optional[datetime] = None
        self.journal: list[str] = []

    #--- 15.11 parameters ---------------------------------------------
    def apply_parameters(
        self, bar_sequence: int, bar_time: str, write_journal: bool
    ) -> bool:
        window = profile_window(self.asset_class, self.volatility, self.timeframe)
        if not self.parameters_initialized:
            self.parameters_initialized = True
            self.applied_volatility = self.volatility
            self.window = window
            self.last_window_change_bar = bar_sequence - BIG
            return True
        if window == self.window:
            self.applied_volatility = self.volatility
            return True
        if not can_change_at(bar_sequence, self.last_window_change_bar):
            return True  # the pause governs the window only
        if write_journal:
            self.journal.append(
                "Emtt | Profile window {} -> {} closed bars | volatility {} -> {} | bar {}".format(
                    self.window,
                    window,
                    self.applied_volatility,
                    self.volatility,
                    bar_time,
                )
            )
        self.applied_volatility = self.volatility
        self.window = window
        self.last_window_change_bar = bar_sequence
        return True

    #--- the session sums ---------------------------------------------
    def _rebuild_session(
        self, bars: Sequence[Bar], index: int, anchor: datetime, compute_prior: bool
    ) -> None:
        reading = self.reading
        reading.session_anchor = anchor
        reading.session_name = session_label(anchor)
        reading.bars_since_session_start = 0
        self.session_volume = 0.0
        self.session_pv = 0.0
        self.session_cvd = 0.0
        run_end = session_run_end(bars, index, anchor)
        for current in range(index, run_end):
            bar = bars[current]
            typical = (bar.high + bar.low + bar.close) / 3.0
            self.session_volume += bar.volume
            self.session_pv += typical * bar.volume
            self.session_cvd += bar_delta(bar)
            reading.bars_since_session_start += 1
        if compute_prior:
            self._compute_prior_poc(bars, run_end, anchor)
        if reading.prior_poc is not None:
            reading.prior_poc_naked = True
            for current in range(index, run_end):
                bar = bars[current]
                if bar.low <= reading.prior_poc <= bar.high:
                    reading.prior_poc_naked = False
                    break

    def _compute_prior_poc(
        self, bars: Sequence[Bar], from_index: int, anchor: datetime
    ) -> None:
        """Once per session, from the previous session's own bars (15.5)."""
        reading = self.reading
        reading.prior_poc = None
        reading.prior_poc_naked = False
        if from_index <= 0 or from_index >= len(bars):
            return
        wanted = previous_anchor(anchor)
        if wanted is None or session_anchor(bars[from_index].time) != wanted:
            return
        end = from_index
        positive = 0
        while end < len(bars) and session_anchor(bars[end].time) == wanted:
            if bars[end].volume > 0:
                positive += 1
            end += 1
        if positive < PRIOR_POC_MIN_BARS:
            return
        profile = compute_profile(bars[from_index:end])
        if not profile.readable:
            return
        reading.prior_poc = profile.poc
        reading.prior_poc_naked = True

    #--- the published readings ---------------------------------------
    def _publish(self, bars: Sequence[Bar], index: int) -> None:
        reading = self.reading
        close = bars[index].close
        reading.last_close = close
        atr_value = reading.atr_value

        reading.has_vwap = self.session_volume > 0
        reading.vwap = (
            self.session_pv / self.session_volume if reading.has_vwap else 0.0
        )
        reading.price_vs_vwap = SIDE_NONE
        reading.distance_vwap_atrs = 0.0
        if reading.has_vwap and atr_value > 0:
            if close > reading.vwap:
                reading.price_vs_vwap = SIDE_ABOVE
            elif close < reading.vwap:
                reading.price_vs_vwap = SIDE_BELOW
            reading.distance_vwap_atrs = abs(close - reading.vwap) / atr_value

        available = len(bars) - index
        window_bars = min(available, self.window) if self.window > 0 else 0
        if window_bars >= self.window and self.window > 0:
            profile = compute_profile(bars[index : index + self.window])
        else:
            profile = Profile(low=0.0, high=0.0, total_volume=0.0)
        reading.profile_window = self.window
        reading.window_low = profile.low
        reading.window_high = profile.high
        reading.profile_volume = profile.total_volume
        reading.has_profile = profile.readable
        reading.poc = profile.poc
        reading.vah = profile.vah
        reading.val = profile.val
        reading.ready = (
            window_bars >= self.window
            and profile.total_volume > 0
            and atr_value > 0
        )

        members = magnet_members(
            has_profile=reading.has_profile,
            poc=reading.poc,
            vah=reading.vah,
            val=reading.val,
            prior_poc=reading.prior_poc,
            naked=reading.prior_poc_naked,
        )
        magnet = published_magnet(members, close)
        if magnet is None:
            reading.magnet_kind = MAGNET_NONE
            reading.magnet_price = 0.0
            reading.distance_magnet_atrs = 0.0
        else:
            reading.magnet_kind, reading.magnet_price = magnet
            directional = abs(close - reading.magnet_price)
            if reading.flow_direction > 0:
                directional = max(0.0, reading.magnet_price - close)
            elif reading.flow_direction < 0:
                directional = max(0.0, close - reading.magnet_price)
            reading.distance_magnet_atrs = (
                directional / atr_value if atr_value > 0 else 0.0
            )

        reading.volume_flow_score = volume_flow_score(
            ready=reading.ready,
            flow_direction=reading.flow_direction,
            net_delta=reading.net_delta,
            window_volume=reading.window_volume,
            has_vwap=reading.has_vwap,
            price_vs_vwap=reading.price_vs_vwap,
            has_profile=reading.has_profile,
            close=close,
            val=reading.val,
            vah=reading.vah,
            atr_value=atr_value,
            members=members,
        )

    #--- one closed bar -------------------------------------------------
    def advance(
        self,
        bars: Sequence[Bar],
        index: int,
        atr_value: float,
        atr_period: int = 14,
        bar_sequence: int = 0,
        volatility: Optional[str] = None,
        force_rebuild: bool = False,
        write_journal: bool = True,
    ) -> bool:
        if index < 0 or index >= len(bars) or atr_value <= 0 or atr_period <= 0:
            return False
        bar = bars[index]
        if volatility is not None:
            self.volatility = volatility
        reading = self.reading
        reading.atr_period = atr_period
        reading.atr_value = atr_value
        self.current_sequence = bar_sequence
        if not self.apply_parameters(bar_sequence, bar.time.strftime("%Y.%m.%d %H:%M"), write_journal):
            return False

        anchor = session_anchor(bar.time)
        if anchor is None:
            return False
        new_session = anchor != reading.session_anchor
        seconds = period_seconds(self.timeframe) or 1
        gap = (
            self.last_bar_time is not None
            and not new_session
            and (bar.time - self.last_bar_time).total_seconds() > seconds
        )

        if not self.initialized or force_rebuild or new_session or gap:
            if new_session and self.last_bar_time is not None and write_journal:
                self.journal.append(
                    "Emtt | VWAP re-anchored | session {} -> {} | bar {}".format(
                        reading.session_name or "--",
                        session_label(anchor),
                        bar.time.strftime("%Y.%m.%d %H:%M"),
                    )
                )
            if new_session:
                self.last_flow_direction = None
            self._rebuild_session(
                bars,
                index,
                anchor,
                new_session or force_rebuild or not self.initialized,
            )
            self.last_bar_time = bar.time
        else:
            typical = (bar.high + bar.low + bar.close) / 3.0
            self.session_volume += bar.volume
            self.session_pv += typical * bar.volume
            self.session_cvd += bar_delta(bar)
            reading.bars_since_session_start += 1
            if (
                reading.prior_poc is not None
                and reading.prior_poc_naked
                and bar.low <= reading.prior_poc <= bar.high
            ):
                reading.prior_poc_naked = False
            self.last_bar_time = bar.time

        self._classify(bars, index, anchor)

        if reading.flow_reading:
            if (
                self.last_flow_direction is not None
                and reading.flow_direction != self.last_flow_direction
            ):
                self.flip_direction = reading.flow_direction
                self.flip_sequence = bar_sequence
                self.flip_time = bar.time
                if write_journal:
                    self.journal.append(
                        "Emtt | Flow CVD {} -> {} | net {:+.2f} x window volume | bar {}".format(
                            flow_name(self.last_flow_direction),
                            flow_name(reading.flow_direction),
                            reading.net_delta / reading.window_volume,
                            bar.time.strftime("%Y.%m.%d %H:%M"),
                        )
                    )
            self.last_flow_direction = reading.flow_direction

        self._publish(bars, index)
        self.initialized = True
        return True

    def _classify(self, bars: Sequence[Bar], index: int, anchor: datetime) -> None:
        reading = self.reading
        reading.flow_reading = False
        reading.flow_direction = FLOW_FLAT
        reading.window_volume = 0.0
        reading.net_delta = 0.0
        count = reading.bars_since_session_start
        if count < 2:
            return
        window_bars = bars[index : index + min(count, CVD_WINDOW)]
        direction = classify_flow(window_bars)
        if direction is None:
            return
        reading.flow_reading = True
        reading.flow_direction = direction
        reading.window_volume = sum(bar.volume for bar in window_bars)
        reading.net_delta = sum(bar_delta(bar) for bar in window_bars)

    #--- 15.10 panel text ----------------------------------------------
    def clause(self) -> str:
        reading = self.reading
        if not reading.ready:
            return ""
        parts: list[str] = []
        if reading.flow_reading:
            parts.append("CVD " + flow_name(reading.flow_direction))
        if reading.has_vwap and reading.price_vs_vwap != SIDE_NONE:
            parts.append(
                "above VWAP" if reading.price_vs_vwap == SIDE_ABOVE else "below VWAP"
            )
        if reading.has_profile and reading.magnet_kind != MAGNET_NONE:
            parts.append(
                "{} {:.{}f}".format(
                    reading.magnet_kind, reading.magnet_price, self.digits
                )
            )
        return ", ".join(parts[:3])

    def status(self) -> str:
        if self.flip_sequence <= -BIG or self.flip_direction == 0:
            return ""
        if self.current_sequence - self.flip_sequence > STATUS_FRESH_BARS:
            return ""
        return "Watching — CVD turned " + flow_name(self.flip_direction)


def append_row9(prior: str, clause: str) -> str:
    """One clause is appended as `` | clause``, only when it is non-empty."""
    if not clause:
        return prior
    if prior in ("", "--"):
        return clause
    return f"{prior} | {clause}"


#==== 15.8 - 15.10 the higher-timeframe context =============================

def mtf_timeframe(chart_timeframe: str) -> Optional[str]:
    """The one fixed mapping; any other chart timeframe has no HTF."""
    return MTF_MAP.get(chart_timeframe)


def mtf_history_required(htf: str) -> int:
    return max(supertrend_history_required(htf), smc_history_required_worst(htf))


def mtf_fetch_count(htf: str) -> int:
    return mtf_history_required(htf) + MTF_FETCH_BUFFER


def efficiency_ratio(
    rates: Sequence[Bar], index: int, period: int
) -> Optional[float]:
    """The EA's in-house ER, identical on the HTF (pure function of bars)."""
    if index < 0 or period <= 0 or index + period >= len(rates):
        return None
    net = abs(rates[index].close - rates[index + period].close)
    path = 0.0
    for step in range(period):
        path += abs(rates[index + step].close - rates[index + step + 1].close)
    if path <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * net / path))


@dataclass(frozen=True)
class MtfFacts:
    """One HTF bar's resolved parameters and indicator-buffer values."""

    atr_period: int
    er_period: int
    volatility: str
    atr_value: float
    atr50: float
    kama_fast: float
    kama_medium: float
    kama_slow: float
    band_width: float
    previous_band_width: float


def build_measurements(
    rates: Sequence[Bar], index: int, facts: MtfFacts
) -> Optional[Measurements]:
    """The EA's ``EmttBuildMeasurements`` formulas, HTF arrays as arguments."""
    efficiency = efficiency_ratio(rates, index, facts.er_period)
    if efficiency is None:
        return None
    fast, medium, slow = facts.kama_fast, facts.kama_medium, facts.kama_slow
    direction = 0
    if fast > medium > slow:
        direction = 1
    elif fast < medium < slow:
        direction = -1
    if facts.atr_value <= 0 or facts.atr50 <= 0:
        return None
    if facts.band_width <= 0 or facts.previous_band_width <= 0:
        return None
    return Measurements(
        efficiency=efficiency,
        atr_ratio=facts.atr_value / facts.atr50,
        direction=direction,
        bands_expanding=facts.band_width > facts.previous_band_width,
    )


@dataclass
class MtfReading:
    """The published contract of 15.9."""

    ready: bool = False
    htf: str = ""
    htf_name: str = "--"
    htf_regime: str = UNKNOWN
    htf_direction: int = 0
    htf_cluster: str = "--"
    htf_multiplier: float = 0.0
    htf_bias: int = 0
    htf_zone: str = ""
    agrees: int = 0
    htf_bar_time: Optional[datetime] = None
    htf_atr_period: int = 0
    htf_atr_value: float = 0.0
    htf_bars_fetched: int = 0
    chart_direction: int = 0
    chart_bias: int = 0
    current_sequence: int = 0
    last_flip_sequence: int = -BIG
    last_flip_direction: int = 0
    mtf_score: float = 0.0


def mtf_score(
    *,
    ready: bool,
    htf_regime: str,
    htf_direction: int,
    chart_direction: int,
    htf_bias: int,
    chart_bias: int,
) -> float:
    """Direction 0.50 / regime 0.30 / structure 0.20 (15.9)."""
    if not ready:
        return 0.0
    comparable = htf_direction != 0 and chart_direction != 0
    direction = 1.0 if comparable and htf_direction == chart_direction else 0.0
    if htf_regime in TRENDING:
        regime = 1.0
    elif htf_regime == TRANSITION:
        regime = 0.5
    else:
        regime = 0.0
    if htf_bias != 0 and chart_bias != 0:
        structure = 1.0 if htf_bias == chart_bias else 0.0
    else:
        structure = 0.5  # nothing to compare is neutral, not a disagreement
    return clamp01(
        MTF_WEIGHT_DIRECTION * direction
        + MTF_WEIGHT_REGIME * regime
        + MTF_WEIGHT_STRUCTURE * structure
    )


def mtf_regime_word(htf_name: str, regime: str) -> str:
    """``<HTF> trending up / ranging / volatile / transition / closed``."""
    if regime == BULL:
        return f"{htf_name} trending up"
    if regime == BEAR:
        return f"{htf_name} trending down"
    if regime == RANGING:
        return f"{htf_name} ranging"
    if regime == VOLATILE:
        return f"{htf_name} volatile"
    if regime == TRANSITION:
        return f"{htf_name} transition"
    if regime == CLOSED:
        return f"{htf_name} closed"
    return ""


def mtf_clause(
    *,
    ready: bool,
    htf_name: str,
    htf_regime: str,
    htf_direction: int,
    htf_zone: str,
    chart_direction: int,
) -> str:
    """At most three parts; the agreement word is recomposed live (15.10)."""
    if not ready:
        return ""
    parts: list[str] = []
    regime_part = mtf_regime_word(htf_name, htf_regime)
    if regime_part:
        parts.append(regime_part)
    if htf_direction != 0 and chart_direction != 0:
        parts.append("agrees" if htf_direction == chart_direction else "disagrees")
    if htf_zone:
        parts.append(f"{htf_name} {htf_zone}")
    return ", ".join(parts[:3])


def mtf_status(reading: MtfReading) -> str:
    """``Watching — <HTF> turned <up/down>`` inside three closed chart bars."""
    if not reading.ready or reading.last_flip_direction == 0:
        return ""
    if reading.current_sequence - reading.last_flip_sequence > MTF_STATUS_FRESH_BARS:
        return ""
    word = "up" if reading.last_flip_direction > 0 else "down"
    return f"Watching — {reading.htf_name} turned {word}"


class MtfTracker:
    """A portable twin of the HTF context: Phase 2 / 3 / 4 re-run on HTF bars.

    The per-bar ``facts`` carry the resolved parameters and the indicator
    buffer values (ATR / KAMA / band width) exactly as the MTF context's own
    handle set would supply them; everything else - the ER, the regime, the
    Supertrend walk, the structure - is computed here from the HTF bars.
    """

    def __init__(
        self,
        chart_timeframe: str = "M5",
        asset_class: str = "Forex Major",
        volatility: str = NORMAL,
    ) -> None:
        self.chart_timeframe = chart_timeframe
        self.htf = mtf_timeframe(chart_timeframe)
        self.asset_class = asset_class
        self.volatility = volatility
        self.regime = RegimeTracker()
        self.supertrend = SupertrendTracker(
            timeframe=self.htf or "M15", asset_class=asset_class
        )
        self.smc = SmcTracker(asset_class, volatility, self.htf or "M15")
        self.reading = MtfReading(htf=self.htf or "", htf_name=self.htf or "--")
        self.rebuild_needed = True
        self.evaluated = False
        self.last_htf_bar_time: Optional[datetime] = None
        self.facts: list[MtfFacts] = []
        self.journal: list[str] = []

    #--- the silent walk over the fetched HTF bars ---------------------
    def walk(self, rates: Sequence[Bar], facts: Sequence[MtfFacts]) -> bool:
        if self.htf is None:
            return False
        required = mtf_history_required(self.htf)
        if len(rates) < required or len(facts) != len(rates):
            return False
        self.regime = RegimeTracker()
        self.supertrend = SupertrendTracker(
            timeframe=self.htf, asset_class=self.asset_class
        )
        self.smc = SmcTracker(self.asset_class, self.volatility, self.htf)
        atrs = [fact.atr_value for fact in facts]

        evaluation_count = len(rates) - (required - 1)
        first = True
        previous_time: Optional[datetime] = None
        for index in range(evaluation_count - 1, -1, -1):
            measurements = build_measurements(rates, index, facts[index])
            if measurements is None:
                return False
            after_gap = (
                previous_time is not None
                and (rates[index].time - previous_time).total_seconds()
                > 2 * (period_seconds(self.htf) or 1)
            )
            self.regime.advance(measurements, first or after_gap)
            if not self.supertrend.advance(
                rates,
                atrs,
                index=index,
                bar_sequence=index,
                asset_class=self.asset_class,
                atr_period=facts[index].atr_period,
                volatility=facts[index].volatility,
                force_retrain=first or after_gap,
            ):
                return False
            if not self.smc.advance(
                rates, atrs, index, index, force_first=first or after_gap
            ):
                return False
            previous_time = rates[index].time
            first = False
        self.facts = list(facts)
        self.evaluated = True
        self.last_htf_bar_time = rates[0].time
        return True

    def advance_bar(
        self,
        rates: Sequence[Bar],
        facts: Sequence[MtfFacts],
        chart_sequence: int,
        chart_direction: int,
        chart_bias: int,
        write_journal: bool,
    ) -> bool:
        """One new closed HTF bar, on the same code path."""
        if not self.evaluated or len(rates) != len(facts):
            return False
        before_regime = self.regime.stable
        before_direction = self.supertrend.direction
        before_bias = self.smc.state.bias
        before_event = self.smc.state.event_sequence

        atrs = [fact.atr_value for fact in facts]
        index = 0
        measurements = build_measurements(rates, index, facts[index])
        if measurements is None:
            return False
        after_gap = (
            self.last_htf_bar_time is not None
            and (rates[0].time - self.last_htf_bar_time).total_seconds()
            > 2 * (period_seconds(self.htf or "") or 1)
        )
        self.regime.advance(measurements, after_gap)
        if not self.supertrend.advance(
            rates,
            atrs,
            index=index,
            bar_sequence=0,
            asset_class=self.asset_class,
            atr_period=facts[index].atr_period,
            volatility=facts[index].volatility,
            force_retrain=after_gap,
        ):
            return False
        if not self.smc.advance(rates, atrs, index, 0, force_first=after_gap):
            return False
        self.facts = list(facts)
        self.last_htf_bar_time = rates[0].time

        if write_journal:
            name = self.htf or "--"
            if before_direction != 0 and self.supertrend.direction != before_direction:
                turn = "up" if self.supertrend.direction > 0 else "down"
                self.journal.append(
                    "Emtt | HTF ({}) supertrend turned {} | cluster {}, multiplier {:.1f} | bar {}".format(
                        name,
                        turn,
                        cluster_name(self.supertrend.cluster),
                        self.supertrend.multiplier,
                        rates[0].time.strftime("%Y.%m.%d %H:%M"),
                    )
                )
            if before_regime != UNKNOWN and self.regime.stable != before_regime:
                self.journal.append(
                    "Emtt | HTF ({}) regime {} -> {} | bar {}".format(
                        name,
                        before_regime,
                        self.regime.stable,
                        rates[0].time.strftime("%Y.%m.%d %H:%M"),
                    )
                )
            state = self.smc.state
            # The HTF log carries direction-relevant structure facts only:
            # BOS and CHoCH, never a sweep (15.12).
            if (
                state.event_sequence is not None
                and state.event_sequence != before_event
                and state.event_kind in (BOS, CHOCH)
            ):
                self.journal.append(
                    "Emtt | HTF ({}) structure {} {} | bias {} -> {} | bar {}".format(
                        name,
                        state.event_kind,
                        "up" if state.event_direction > 0 else "down",
                        "up" if before_bias > 0 else "down" if before_bias < 0 else "none",
                        "up" if state.bias > 0 else "down" if state.bias < 0 else "none",
                        rates[0].time.strftime("%Y.%m.%d %H:%M"),
                    )
                )

        if before_direction != 0 and self.supertrend.direction != before_direction:
            self.reading.last_flip_sequence = chart_sequence
            self.reading.last_flip_direction = self.supertrend.direction
        self._publish(rates, chart_direction, chart_bias)
        return True

    #--- the poll of 15.8 ---------------------------------------------
    def advance(
        self,
        rates: Sequence[Bar],
        facts: Sequence[MtfFacts],
        htf_bar_time: datetime,
        chart_sequence: int,
        chart_direction: int,
        chart_bias: int,
        force_rebuild: bool = False,
        write_journal: bool = True,
    ) -> bool:
        self.reading.current_sequence = chart_sequence
        if self.htf is None:
            self.reset()
            return False
        required = mtf_history_required(self.htf)
        if len(rates) < required or len(facts) != len(rates):
            self.reading.ready = False
            self.reading.mtf_score = 0.0
            return False

        bar_changed = htf_bar_time != self.last_htf_bar_time
        if (
            not self.rebuild_needed
            and not force_rebuild
            and not bar_changed
            and self.reading.ready
        ):
            return True  # between closes the state is constant

        rebuild = (
            self.rebuild_needed or force_rebuild or not self.reading.ready or not self.evaluated
        )
        if rebuild:
            if not self.walk(rates, facts):
                self.reading.ready = False
                self.reading.mtf_score = 0.0
                return False
            self._publish(rates, chart_direction, chart_bias)
            if write_journal:
                self.journal.append(self.replay_journal_line(rates[0].time))
            self.rebuild_needed = False
        else:
            if not self.advance_bar(
                rates, facts, chart_sequence, chart_direction, chart_bias, write_journal
            ):
                return False
        self.last_htf_bar_time = htf_bar_time
        return True

    def reset(self) -> None:
        self.reading = MtfReading(htf=self.htf or "", htf_name=self.htf or "--")
        self.rebuild_needed = True
        self.evaluated = False
        self.last_htf_bar_time = None

    def _publish(
        self, rates: Sequence[Bar], chart_direction: int, chart_bias: int
    ) -> None:
        reading = self.reading
        reading.htf = self.htf or ""
        reading.htf_name = self.htf or "--"
        reading.htf_regime = self.regime.stable
        reading.htf_direction = self.supertrend.direction
        reading.htf_cluster = cluster_name(self.supertrend.cluster)
        reading.htf_multiplier = self.supertrend.multiplier
        reading.htf_bias = self.smc.state.bias
        reading.htf_zone = self.smc.state.zone
        reading.htf_bar_time = rates[0].time
        reading.htf_bars_fetched = len(rates)
        reading.htf_atr_period = self.supertrend.atr_period
        reading.htf_atr_value = self.supertrend.atr_value
        reading.chart_direction = chart_direction
        reading.chart_bias = chart_bias
        reading.agrees = 0
        if reading.htf_direction != 0 and chart_direction != 0:
            reading.agrees = 1 if reading.htf_direction == chart_direction else -1
        reading.ready = self.evaluated
        reading.mtf_score = mtf_score(
            ready=reading.ready,
            htf_regime=reading.htf_regime,
            htf_direction=reading.htf_direction,
            chart_direction=chart_direction,
            htf_bias=reading.htf_bias,
            chart_bias=chart_bias,
        )

    def replay_journal_line(self, bar_time: datetime) -> str:
        turn = (
            "up"
            if self.supertrend.direction > 0
            else "down"
            if self.supertrend.direction < 0
            else "flat"
        )
        return (
            "Emtt | MTF context replayed | {} | {} closed bars | regime {} | supertrend {} ({}, {:.1f}) | bias {} | zone {} | score {:.2f} | bar {}".format(
                self.htf or "--",
                len(self.facts),
                self.regime.stable,
                turn,
                cluster_name(self.supertrend.cluster),
                self.supertrend.multiplier,
                "up" if self.smc.state.bias > 0 else "down" if self.smc.state.bias < 0 else "none",
                self.smc.state.zone or "--",
                self.reading.mtf_score,
                bar_time.strftime("%Y.%m.%d %H:%M"),
            )
        )

    def clause(self, chart_direction: int) -> str:
        return mtf_clause(
            ready=self.reading.ready,
            htf_name=self.reading.htf_name,
            htf_regime=self.reading.htf_regime,
            htf_direction=self.reading.htf_direction,
            htf_zone=self.reading.htf_zone,
            chart_direction=chart_direction,
        )

    def status(self) -> str:
        return mtf_status(self.reading)


#==== 15.10 Row 10 composition ==============================================

def row10_status(
    *,
    incompatible: bool = False,
    loading: bool = False,
    market_closed: bool = False,
    phase2_status: str = "",
    supertrend_status: str = "",
    smc_status: str = "",
    smc_fresh: bool = False,
    volume_flow_status: str = "",
    mtf_status_text: str = "",
    full_context: bool = False,
) -> str:
    """The EA's FillPanel composition: MTF flip > SMC > CVD flip > ST > P2.

    ``full_context`` is the EA's ``fullContext`` - every component ready - and
    the terminal line only replaces the Phase 3 wording once nothing is fresh.
    """
    if incompatible:
        return ROW10_INCOMPATIBLE
    if loading:
        return ROW10_LOADING
    if market_closed:
        return ROW10_MARKET_CLOSED
    status = phase2_status
    if supertrend_status:
        status = supertrend_status
    if smc_status:
        status = smc_status
    if (
        full_context
        and not smc_fresh
        and volume_flow_status == ""
        and mtf_status_text == ""
    ):
        return ROW10_CONTEXT_ONLY
    if volume_flow_status:
        status = volume_flow_status
    if smc_fresh:
        status = smc_status
    if mtf_status_text:
        status = mtf_status_text
    return status
