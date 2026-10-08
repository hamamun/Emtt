"""Portable reference functions for Phase 3's pure decision logic.

This mirrors Emtt.md 11.3-11.6 (Supertrend bands, K-Means clusters,
per-cluster multiplier selection and the published component contract) with
no MT5 dependency, so CI can exercise the rules on every platform. It also
models the 9.2.3 matrix resolution, its clamping and the two-closed-bar pause
rule, which Phase 2 implemented in MQL5 but the portable suite never covered.

Series convention matches MQL5: index 0 is the newest closed bar and larger
indices are older bars, exactly as ``CopyRates`` / ``CopyBuffer`` fill them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Optional, Sequence

#--- 11.7: the training window is the first lookback parameter ----------
WINDOW_BASE = 200
ATR_BASELINE_BARS = 50  # 11.8: gate = window + the 50-bar ATR baseline
MIN_WINDOW_BARS = 30
TIMEFRAME_SCALE = {"M5": 1.00, "M15": 1.25, "M30": 1.50}

#--- 11.4: K-Means ------------------------------------------------------
CLUSTERS = 3
KMEANS_ITERATIONS = 20
MIN_MEMBERS = 5  # sparse-cluster guard
RETRAIN_DIVISOR = 20  # retrain every window / 20 closed bars

#--- 11.5: multiplier candidates ---------------------------------------
MULTIPLIER_MIN = 2.0
MULTIPLIER_MAX = 4.0
MULTIPLIER_STEP = 0.5
DEFAULT_MULTIPLIER = 3.0  # unlearned cluster, the middle of the set
WHIPSAW_PENALTY = 0.10
SCORE_TIE = 1e-12

#--- 11.6: the published 0.0-1.0 component score ------------------------
WEIGHT_DISTANCE = 0.45
WEIGHT_AGE = 0.35
WEIGHT_FLIPS = 0.20
AGE_SCALE_BARS = 20.0
FLIP_SCALE_COUNT = 20.0

#--- 9.2.3 guard rails --------------------------------------------------
PARAMETER_PAUSE_BARS = 2

CALM = "Calm"
NORMAL = "Normal"
WILD = "Wild"
CLUSTER_NAMES = (CALM, NORMAL, WILD)

ROW10_SUPERTREND = "Watching — Supertrend context only, no signal yet"
ROW10_INCOMPATIBLE = "Incompatible chart. Switch to M5/M15/M30."


@dataclass(frozen=True)
class Bar:
    """One closed bar. Index 0 of a series is the newest closed bar."""

    high: float
    low: float
    close: float


def candidate_multipliers() -> tuple[float, ...]:
    """11.5: the candidate set is the range - nothing outside it can win."""
    values: list[float] = []
    value = MULTIPLIER_MIN
    while value <= MULTIPLIER_MAX + SCORE_TIE:
        values.append(round(value, 10))
        value += MULTIPLIER_STEP
    return tuple(values)


def is_candidate(multiplier: float) -> bool:
    return any(abs(multiplier - c) <= SCORE_TIE for c in candidate_multipliers())


#=== 11.7 lookback scaling and the single history gate ==================


def lookback_scale(timeframe: str) -> float:
    return TIMEFRAME_SCALE.get(timeframe, 1.00)


def window_for_timeframe(timeframe: str) -> int:
    return max(MIN_WINDOW_BARS, round(WINDOW_BASE * lookback_scale(timeframe)))


def history_required(timeframe: str) -> int:
    """11.8: training window + the 50-bar ATR baseline, one code path."""
    return window_for_timeframe(timeframe) + ATR_BASELINE_BARS


def retrain_interval(window: int) -> int:
    return max(1, window // RETRAIN_DIVISOR)


#=== 11.3 Supertrend bands =============================================


@dataclass(frozen=True)
class Bands:
    directions: tuple[int, ...]  # oldest-first
    direction: int
    line: float
    bars_since_flip: int
    flip_count: int


def supertrend_walk(
    rates: Sequence[Bar],
    atrs: Sequence[float],
    multiplier: float,
    index: int = 0,
    window: Optional[int] = None,
) -> Bands:
    """Replay 11.3 across the window; index 0 of the result is the oldest bar.

    The oldest bar of the window seeds direction +1; ``flat`` (0) is reported
    only when no band has been evaluated at all.
    """
    if window is None:
        window = len(rates) - index
    if index < 0 or window < MIN_WINDOW_BARS or multiplier <= 0:
        raise ValueError("Supertrend needs a usable window and multiplier")
    if index + window > len(rates) or index + window > len(atrs):
        raise ValueError("window reaches past the copied closed bars")

    directions = [0] * window
    previous_up = 0.0
    previous_down = 0.0
    previous_close = 0.0
    previous_direction = 0
    flip_count = 0
    last_flip_offset = window - 1
    direction = 0
    line = 0.0

    for offset in range(window - 1, -1, -1):
        i = index + offset
        atr_value = atrs[i]
        high, low, close = rates[i].high, rates[i].low, rates[i].close
        if atr_value <= 0 or close <= 0:
            raise ValueError("Supertrend needs positive ATR and close values")

        mid = (high + low) * 0.5
        up_raw = mid + multiplier * atr_value
        down_raw = mid - multiplier * atr_value
        if offset == window - 1:
            up, down, current = up_raw, down_raw, 1
        else:
            up = up_raw if (up_raw < previous_up or previous_close > previous_up) else previous_up
            down = (
                down_raw
                if (down_raw > previous_down or previous_close < previous_down)
                else previous_down
            )
            if close > previous_up:
                current = 1
            elif close < previous_down:
                current = -1
            else:
                current = previous_direction

        directions[window - 1 - offset] = current
        if offset < window - 1 and current != previous_direction:
            flip_count += 1
            last_flip_offset = offset
        previous_up, previous_down = up, down
        previous_close = close
        previous_direction = current
        if offset == 0:
            direction = current
            line = down if current > 0 else up

    return Bands(
        directions=tuple(directions),
        direction=direction,
        line=line,
        bars_since_flip=last_flip_offset,
        flip_count=flip_count,
    )


def segments(directions: Sequence[int]) -> list[tuple[int, int]]:
    """Maximal runs of equal direction, oldest-first, inclusive bounds.

    A segment starts at the bar whose direction differs from the bar before it
    and ends at the last bar still carrying that direction: the bar that flips
    the direction away belongs to the next segment, never this one.
    """
    out: list[tuple[int, int]] = []
    start = 0
    while start < len(directions):
        end = start
        while end + 1 < len(directions) and directions[end + 1] == directions[start]:
            end += 1
        out.append((start, end))
        start = end + 1
    return out


#=== 11.5 multiplier selection =========================================


@dataclass(frozen=True)
class CandidateScore:
    multiplier: float
    mean_return: float
    segment_count: int
    noise: float
    score: float


def score_segments(
    rates: Sequence[Bar],
    atrs: Sequence[float],
    index: int,
    window: int,
    directions: Sequence[int],
    centres: Optional[Sequence[float]] = None,
    cluster: Optional[int] = None,
    multiplier: float = 0.0,
) -> Optional[CandidateScore]:
    """Score the segments of one candidate replay.

    A segment is attributed to the cluster of the bar it starts on, so each
    cluster learns the multiplier that served its own volatility state while
    the bands themselves are replayed once across the whole window. Pass no
    cluster to score every segment in the window.
    """
    total = 0.0
    count = 0
    for start, end in segments(directions):
        start_index = index + window - 1 - start
        end_index = index + window - 1 - end
        atr_start = atrs[start_index]
        direction = directions[start]
        if direction == 0 or atr_start <= 0 or end < start:
            continue
        if cluster is not None and nearest_centre(centres, atr_start) != cluster:
            continue
        total += direction * (rates[end_index].close - rates[start_index].close) / atr_start
        count += 1
    if count <= 0:
        return None  # no completed segment: the previous value stands
    mean_return = total / count
    noise = count / (window / 10.0)
    return CandidateScore(
        multiplier=multiplier,
        mean_return=mean_return,
        segment_count=count,
        noise=noise,
        score=mean_return - WHIPSAW_PENALTY * noise,
    )


def score_candidate(
    rates: Sequence[Bar],
    atrs: Sequence[float],
    multiplier: float,
    index: int = 0,
    window: Optional[int] = None,
) -> Optional[CandidateScore]:
    """Score every segment of one candidate across the window."""
    if window is None:
        window = len(rates) - index
    bands = supertrend_walk(rates, atrs, multiplier, index, window)
    return score_segments(
        rates, atrs, index, window, bands.directions, multiplier=multiplier
    )


def candidate_replays(
    rates: Sequence[Bar],
    atrs: Sequence[float],
    index: int = 0,
    window: Optional[int] = None,
) -> list[tuple[float, tuple[int, ...]]]:
    """One band replay per candidate, reused for all three clusters."""
    if window is None:
        window = len(rates) - index
    return [
        (multiplier, supertrend_walk(rates, atrs, multiplier, index, window).directions)
        for multiplier in candidate_multipliers()
    ]


def _best_score(
    rates: Sequence[Bar],
    atrs: Sequence[float],
    index: int,
    window: int,
    replays: Sequence[tuple[float, tuple[int, ...]]],
    centres: Optional[Sequence[float]],
    cluster: Optional[int],
) -> Optional[CandidateScore]:
    best: Optional[CandidateScore] = None
    for multiplier, directions in replays:
        result = score_segments(
            rates, atrs, index, window, directions, centres, cluster, multiplier
        )
        if result is None:
            continue
        if best is None:
            best = result
            continue
        tied = abs(result.score - best.score) <= SCORE_TIE
        if result.score > best.score + SCORE_TIE or (tied and multiplier > best.multiplier):
            best = result
    return best


def select_multiplier(
    rates: Sequence[Bar],
    atrs: Sequence[float],
    index: int = 0,
    window: Optional[int] = None,
    centres: Optional[Sequence[float]] = None,
    cluster: Optional[int] = None,
) -> Optional[float]:
    """Highest score wins; an exact tie goes to the larger, smoother value."""
    if window is None:
        window = len(rates) - index
    best = _best_score(
        rates, atrs, index, window,
        candidate_replays(rates, atrs, index, window), centres, cluster,
    )
    return None if best is None else best.multiplier


def cluster_winners(
    rates: Sequence[Bar],
    atrs: Sequence[float],
    centres: Sequence[float],
    index: int = 0,
    window: Optional[int] = None,
) -> list[Optional[float]]:
    """One winner per cluster, from one replay per candidate (11.5).

    A cluster with no completed segment gets ``None``: the caller keeps that
    cluster's previous value rather than inventing one.
    """
    if window is None:
        window = len(rates) - index
    replays = candidate_replays(rates, atrs, index, window)
    winners: list[Optional[float]] = []
    for c in range(CLUSTERS):
        best = _best_score(rates, atrs, index, window, replays, centres, c)
        winners.append(None if best is None else best.multiplier)
    return winners



#=== 11.4 K-Means =======================================================


def quantile_seed(sorted_values: Sequence[float], quantile: float) -> float:
    """Nearest-rank quantile of the window itself: sorted[ceil(q/100*N)-1].

    This is a quantile of the set, not the rank percentile of 9.2.2, so the
    Phase 2 mid-rank ``percentile_rank`` is deliberately not reused here.
    """
    count = len(sorted_values)
    if count == 0:
        raise ValueError("quantile seed needs a non-empty window")
    rank = math.ceil(quantile / 100.0 * count)
    rank = min(max(rank, 1), count)
    return sorted_values[rank - 1]


def kmeans_seeds(values: Sequence[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    return (
        quantile_seed(ordered, 10.0),
        quantile_seed(ordered, 50.0),
        quantile_seed(ordered, 90.0),
    )


def nearest_centre(centres: Sequence[float], value: float) -> int:
    """Nearest centre; an exact tie resolves to the calmer centre."""
    best = 0
    best_distance = 0.0
    for i, centre in enumerate(centres):
        distance = abs(value - centre)
        if i == 0 or distance < best_distance:
            best = i
            best_distance = distance
    return best


def kmeans(values: Sequence[float]) -> tuple[list[float], list[int]]:
    """Lloyd iterations, max 20, always restarted from the percentile seeds.

    Returns centres sorted ascending (Calm / Normal / Wild) and their member
    counts. An empty cluster keeps its centre; convergence stops when no
    centre moves more than 1e-9 x the window mean.
    """
    if len(values) < CLUSTERS or any(v <= 0 for v in values):
        raise ValueError("K-Means needs positive ATR values")
    mean = sum(values) / len(values)
    centres = list(kmeans_seeds(values))
    tolerance = 1e-9 * mean

    for _ in range(KMEANS_ITERATIONS):
        sums = [0.0] * CLUSTERS
        members = [0] * CLUSTERS
        for value in values:
            c = nearest_centre(centres, value)
            sums[c] += value
            members[c] += 1
        moved = 0.0
        for c in range(CLUSTERS):
            if members[c] <= 0:
                continue
            nxt = sums[c] / members[c]
            moved = max(moved, abs(nxt - centres[c]))
            centres[c] = nxt
        if moved <= tolerance:
            break

    members = [0] * CLUSTERS
    for value in values:
        members[nearest_centre(centres, value)] += 1
    # Sorted ascending so index 0 is always Calm and index 2 always Wild -
    # Lloyd alone does not guarantee that order.
    pairs = sorted(zip(centres, members), key=lambda pair: pair[0])
    return [centre for centre, _ in pairs], [count for _, count in pairs]


def resolve_multiplier(
    centres: Sequence[float],
    members: Sequence[int],
    cluster_multipliers: Sequence[float],
    atr_value: float,
) -> tuple[int, float, bool, int]:
    """11.4 sparse guard.

    Returns (cluster, multiplier, sparse, donor). A cluster holding fewer than
    5 bars never owns a learned multiplier: the nearest populated cluster
    lends its value instead.
    """
    cluster = nearest_centre(centres, atr_value)
    if members[cluster] >= MIN_MEMBERS:
        return cluster, cluster_multipliers[cluster], False, cluster
    donor = -1
    best_distance = 0.0
    for c in range(CLUSTERS):
        if members[c] < MIN_MEMBERS:
            continue
        distance = abs(atr_value - centres[c])
        if donor < 0 or distance < best_distance:
            donor = c
            best_distance = distance
    multiplier = cluster_multipliers[donor] if donor >= 0 else DEFAULT_MULTIPLIER
    return cluster, multiplier, True, donor


#=== 11.6 published readings ===========================================


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def distance_atrs(close: float, line: float, atr: float, direction: int) -> float:
    """Positive on the trade side of the line; 0 once price falls back."""
    if direction == 0 or atr <= 0:
        return 0.0
    raw = ((close - line) / atr) * direction
    return raw if raw > 0 else 0.0


def supertrend_score(
    direction: int, distance: float, bars_since_flip: int, flip_count: int
) -> float:
    if direction == 0:
        return 0.0
    return (
        WEIGHT_DISTANCE * clamp01(distance)
        + WEIGHT_AGE * clamp01(bars_since_flip / AGE_SCALE_BARS)
        + WEIGHT_FLIPS * clamp01(1.0 - flip_count / FLIP_SCALE_COUNT)
    )


def direction_name(direction: int) -> str:
    if direction > 0:
        return "bullish"
    if direction < 0:
        return "bearish"
    return "flat"


def cluster_name(index: int) -> str:
    if 0 <= index < len(CLUSTER_NAMES):
        return CLUSTER_NAMES[index]
    return "--"


#=== 11.8 panel strings =================================================


def supertrend_clause(cluster: str, direction: int) -> str:
    if direction == 0:
        return ""
    return f"{cluster} (Supertrend {direction_name(direction)})"


def row9_why(regime_sentence: str, cluster: str, direction: int) -> str:
    """Row 9: the regime sentence first, then ' | ', then the clause."""
    clause = supertrend_clause(cluster, direction)
    if not clause:
        return regime_sentence
    if regime_sentence in ("", "--"):
        return clause
    return f"{regime_sentence} | {clause}"


def row10_status(
    *,
    incompatible: bool = False,
    loading: bool = False,
    market_closed: bool = False,
    supertrend_ready: bool = False,
    phase2_status: str = "",
) -> str:
    """Row 10 precedence: rule 19 > loading history > MARKET CLOSED > Phase 3."""
    if incompatible:
        return ROW10_INCOMPATIBLE
    if loading:
        return "Waiting — Loading chart history"
    if market_closed:
        return "Paused — Waiting for market to open"
    if supertrend_ready:
        return ROW10_SUPERTREND
    return phase2_status


#=== The Phase 3 component, walked bar by bar ==========================


@dataclass
class SupertrendReading:
    ready: bool = False
    direction: int = 0
    line: float = 0.0
    cluster: str = "--"
    multiplier: float = DEFAULT_MULTIPLIER
    score: float = 0.0
    bars_since_flip: int = 0
    flip_count: int = 0
    distance_atrs: float = 0.0
    atr_period: int = 0
    atr_value: float = 0.0
    window: int = 0
    bars_since_train: int = 0
    sparse_fallback: bool = False


@dataclass
class SupertrendTracker:
    """Mirror of EmttSupertrendAdvance: clusters, multiplier, readings.

    ``journal`` collects the events 11.9 requires - a multiplier change, a
    current-cluster change, a direction flip and the sparse-cluster fallback -
    and stays empty when nothing changed.
    """

    timeframe: str = "M15"
    asset_class: str = "Forex Major"
    atr_period: int = 10
    volatility: str = "NORMAL"
    window: int = 0
    retrain_every: int = 1
    bars_since_train: int = 0
    initialized: bool = False
    centres: list[float] = field(default_factory=lambda: [0.0] * CLUSTERS)
    members: list[int] = field(default_factory=lambda: [0] * CLUSTERS)
    cluster_multiplier: list[float] = field(
        default_factory=lambda: [DEFAULT_MULTIPLIER] * CLUSTERS
    )
    cluster_learned: list[bool] = field(default_factory=lambda: [False] * CLUSTERS)
    cluster: int = -1
    multiplier: float = DEFAULT_MULTIPLIER
    direction: int = 0
    line: float = 0.0
    score: float = 0.0
    bars_since_flip: int = 0
    flip_count: int = 0
    distance_atrs: float = 0.0
    atr_value: float = 0.0
    sparse_fallback: bool = False
    last_multiplier_change_bar: int = -1_000_000
    context: tuple = field(default_factory=tuple)
    journal: list[str] = field(default_factory=list)

    #--- readings published by 11.6 -----------------------------------
    @property
    def ready(self) -> bool:
        return self.initialized and self.direction != 0

    def reading(self) -> SupertrendReading:
        return SupertrendReading(
            ready=self.ready,
            direction=self.direction,
            line=self.line,
            cluster=cluster_name(self.cluster),
            multiplier=self.multiplier,
            score=self.score,
            bars_since_flip=self.bars_since_flip,
            flip_count=self.flip_count,
            distance_atrs=self.distance_atrs,
            atr_period=self.atr_period,
            atr_value=self.atr_value,
            window=self.window,
            bars_since_train=self.bars_since_train,
            sparse_fallback=self.sparse_fallback,
        )

    #--- 11.4 + 11.5: one retrain -------------------------------------
    def train(self, rates: Sequence[Bar], atrs: Sequence[float], index: int) -> bool:
        values = [atrs[index + k] for k in range(self.window)]
        if any(v <= 0 for v in values):
            return False
        centres, members = kmeans(values)
        self.centres = centres
        self.members = members
        winners = cluster_winners(rates, atrs, centres, index, self.window)
        for c in range(CLUSTERS):
            # Sparse guard: fewer than 5 bars never owns a learned multiplier.
            if members[c] < MIN_MEMBERS:
                continue
            # No completed segment: the cluster keeps its previous value.
            if winners[c] is None:
                continue
            self.cluster_multiplier[c] = winners[c]
            self.cluster_learned[c] = True
        self.journal.append(
            "Supertrend trained | window {} closed bars ({} x{:.2f}) | ATR period {}".format(
                self.window, self.timeframe, lookback_scale(self.timeframe), self.atr_period
            )
        )
        return True

    #--- one closed bar -----------------------------------------------
    def advance(
        self,
        rates: Sequence[Bar],
        atrs: Sequence[float],
        index: int = 0,
        bar_sequence: int = 0,
        bar_time: str = "",
        force_retrain: bool = False,
        asset_class: Optional[str] = None,
        atr_period: Optional[int] = None,
        volatility: Optional[str] = None,
    ) -> bool:
        if asset_class is not None:
            self.asset_class = asset_class
        if atr_period is not None:
            self.atr_period = atr_period
        if volatility is not None:
            self.volatility = volatility

        window = window_for_timeframe(self.timeframe)
        if index < 0 or index + window > len(rates) or index + window > len(atrs):
            return False
        atr_value = atrs[index]
        if atr_value <= 0:
            return False

        self.atr_value = atr_value
        self.retrain_every = retrain_interval(window)
        # 11.4 retrain cadence: the interval, or at once when the context that
        # produced the clusters changes, or after init / reopen / a reset.
        context = (self.asset_class, self.atr_period, window, self.volatility)
        context_changed = not self.initialized or self.context != context
        due = context_changed or force_retrain or self.bars_since_train >= self.retrain_every
        if due:
            previous_window = self.window
            self.context = context
            self.window = window
            if not self.train(rates, atrs, index):
                return False
            self.bars_since_train = 0
            if previous_window and previous_window != window:
                self.journal.append(
                    f"Supertrend training window {previous_window} -> {window} closed bars"
                )
        else:
            self.bars_since_train += 1

        previous_cluster = self.cluster
        # Nearest centre, an exact tie resolving to the calmer; a sparse
        # cluster borrows the nearest populated cluster's multiplier.
        nearest, desired, sparse, donor = resolve_multiplier(
            self.centres, self.members, self.cluster_multiplier, atr_value
        )
        if sparse and not self.sparse_fallback:
            self.journal.append(
                "Supertrend cluster {} holds {} bars, below {} | using multiplier {:.1f} "
                "from cluster {}".format(
                    cluster_name(nearest),
                    self.members[nearest],
                    MIN_MEMBERS,
                    desired,
                    cluster_name(donor),
                )
            )
        self.sparse_fallback = sparse
        self.cluster = nearest

        if not is_candidate(desired):
            desired = DEFAULT_MULTIPLIER
        multiplier_wanted = abs(desired - self.multiplier) > SCORE_TIE
        multiplier_changed = False
        if not self.initialized or previous_cluster < 0:
            self.multiplier = desired
            self.last_multiplier_change_bar = bar_sequence
        elif multiplier_wanted and can_change_at(
            bar_sequence, self.last_multiplier_change_bar
        ):
            self.journal.append(
                "Supertrend multiplier {:.1f} -> {:.1f} | cluster {} -> {} | bar {}".format(
                    self.multiplier,
                    desired,
                    cluster_name(previous_cluster),
                    cluster_name(nearest),
                    bar_time,
                )
            )
            self.multiplier = desired
            self.last_multiplier_change_bar = bar_sequence
            multiplier_changed = True

        # A cluster change is a reading: it is journaled even while the
        # multiplier itself waits out its two-closed-bar pause.
        if not multiplier_changed and nearest != previous_cluster and previous_cluster >= 0:
            note = ", change waiting for its pause" if multiplier_wanted else ""
            self.journal.append(
                "Supertrend cluster {} -> {} | multiplier {:.1f}{} | bar {}".format(
                    cluster_name(previous_cluster),
                    cluster_name(nearest),
                    self.multiplier,
                    note,
                    bar_time,
                )
            )

        previous_direction = self.direction
        bands = supertrend_walk(rates, atrs, self.multiplier, index, window)
        self.direction = bands.direction
        self.line = bands.line
        self.bars_since_flip = bands.bars_since_flip
        self.flip_count = bands.flip_count
        self.distance_atrs = distance_atrs(
            rates[index].close, bands.line, atr_value, bands.direction
        )
        self.score = supertrend_score(
            bands.direction, self.distance_atrs, bands.bars_since_flip, bands.flip_count
        )
        self.initialized = True

        if previous_direction != 0 and bands.direction != previous_direction:
            self.journal.append(
                "Supertrend direction {} -> {} | cluster {} | multiplier {:.1f} | bar {}".format(
                    direction_name(previous_direction),
                    direction_name(bands.direction),
                    cluster_name(self.cluster),
                    self.multiplier,
                    bar_time,
                )
            )
        return True


#=== 9.2.3 matrix resolution, clamping and the pause rule ==============

LOW, NORMAL_VOL, HIGH_VOL = "LOW", "NORMAL", "HIGH"
VOLATILITY_COLUMNS = (LOW, NORMAL_VOL, HIGH_VOL)

# (ATR period, ER period, KAMA fast/medium/slow) per volatility column.
MATRIX: dict[str, dict[str, tuple]] = {
    "Forex Major": {
        LOW: (10, 10, (9, 21, 50)),
        NORMAL_VOL: (10, 10, (9, 21, 50)),
        HIGH_VOL: (14, 14, (13, 26, 50)),
    },
    "Forex Cross": {
        LOW: (10, 10, (9, 21, 50)),
        NORMAL_VOL: (14, 14, (13, 21, 50)),
        HIGH_VOL: (14, 14, (13, 26, 50)),
    },
    "Metals": {
        LOW: (10, 14, (9, 21, 50)),
        NORMAL_VOL: (14, 14, (13, 21, 50)),
        HIGH_VOL: (21, 21, (13, 26, 50)),
    },
    "Crypto": {
        LOW: (14, 21, (13, 26, 50)),
        NORMAL_VOL: (21, 21, (13, 26, 50)),
        HIGH_VOL: (28, 28, (21, 34, 50)),
    },
    "Indices": {
        LOW: (10, 14, (9, 21, 50)),
        NORMAL_VOL: (14, 14, (13, 21, 50)),
        HIGH_VOL: (14, 21, (13, 26, 50)),
    },
    "Generic": {
        LOW: (10, 14, (9, 21, 50)),
        NORMAL_VOL: (14, 14, (13, 21, 50)),
        HIGH_VOL: (14, 21, (13, 26, 50)),
    },
}

FIELD_ATR, FIELD_ER, FIELD_KAMA_FAST, FIELD_KAMA_MEDIUM, FIELD_KAMA_SLOW = range(5)


def matrix_field(asset_class: str, volatility: str, field: int) -> int:
    atr, er, kama = MATRIX[asset_class][volatility]
    if field == FIELD_ATR:
        return atr
    if field == FIELD_ER:
        return er
    if field == FIELD_KAMA_FAST:
        return kama[0]
    if field == FIELD_KAMA_MEDIUM:
        return kama[1]
    return kama[2]


def clamp_matrix_field(asset_class: str, volatility: str, field: int) -> int:
    """Every value stays inside the range written for its class."""
    values = [
        matrix_field(asset_class, column, field) for column in VOLATILITY_COLUMNS
    ]
    return max(min(values), min(max(values), matrix_field(asset_class, volatility, field)))


def resolve_measurement_params(asset_class: str, volatility: str) -> dict[str, int]:
    """Layers 1 + 3: the class base column, clamped to the class range.

    Indicator periods are not scaled by the timeframe layer - the timeframe is
    already inside the candles (9.2.3).
    """
    return {
        "atrPeriod": clamp_matrix_field(asset_class, volatility, FIELD_ATR),
        "erPeriod": clamp_matrix_field(asset_class, volatility, FIELD_ER),
        "kamaFast": clamp_matrix_field(asset_class, volatility, FIELD_KAMA_FAST),
        "kamaMedium": clamp_matrix_field(asset_class, volatility, FIELD_KAMA_MEDIUM),
        "kamaSlow": clamp_matrix_field(asset_class, volatility, FIELD_KAMA_SLOW),
    }


def can_change_at(current_bar: int, last_change_bar: int, pause: int = PARAMETER_PAUSE_BARS) -> bool:
    """One change, then the same parameter stays put for the next 2 closed bars."""
    return current_bar - last_change_bar > pause


class ParameterGate:
    """Applies the 9.2.3 pause to one parameter, whatever it measures."""

    def __init__(self, value: float, pause: int = PARAMETER_PAUSE_BARS) -> None:
        self.value = value
        self.pause = pause
        self.last_change_bar = -1_000_000
        self.changes: list[tuple[int, float, float]] = []

    def request(self, bar: int, wanted: float) -> bool:
        if wanted == self.value:
            return False
        if not can_change_at(bar, self.last_change_bar, self.pause):
            return False
        previous = self.value
        self.value = wanted
        self.last_change_bar = bar
        self.changes.append((bar, previous, wanted))
        return True
