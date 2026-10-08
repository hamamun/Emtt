#!/usr/bin/env python3
"""MQL5 include-layout / structural compile smoke check.

MetaEditor is proprietary and is not installed on the Linux CI runner. This
check resolves the real quoted-include graph and rejects common syntax/layout
mistakes before a Windows/MetaEditor compile. If METAEDITOR_PATH is supplied,
it also invokes that compiler and fails on a non-zero result.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "Experts" / "Emtt.mq5"
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*["<]([^">]+)[">]', re.MULTILINE)


def resolve_include_graph(entry: Path) -> list[Path]:
    visited: list[Path] = []
    active: set[Path] = set()

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in active:
            raise RuntimeError(f"recursive include cycle at {path.relative_to(ROOT)}")
        if path in visited:
            return
        if not path.is_file():
            raise FileNotFoundError(f"MQL include does not exist: {path}")
        try:
            path.relative_to(ROOT)
        except ValueError as exc:
            raise RuntimeError(f"include escapes repository: {path}") from exc

        active.add(path)
        source = path.read_text(encoding="utf-8")
        for include in INCLUDE_RE.findall(source):
            candidate = (path.parent / include).resolve()
            visit(candidate)
        active.remove(path)
        visited.append(path)

    visit(entry)
    return visited


def strip_comments_and_strings(source: str) -> str:
    """Blank comments/string contents while preserving newlines and offsets."""
    out = list(source)
    i = 0
    state = "code"
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                out[i] = out[i + 1] = " "
                i += 2
                state = "line"
                continue
            if ch == "/" and nxt == "*":
                out[i] = out[i + 1] = " "
                i += 2
                state = "block"
                continue
            if ch == '"':
                out[i] = " "
                state = "string"
                i += 1
                continue
            if ch == "'":
                # MQL color literals use single quotes; ignore their contents.
                out[i] = " "
                state = "char"
                i += 1
                continue
        elif state == "line":
            if ch == "\n":
                state = "code"
            else:
                out[i] = " "
        elif state == "block":
            if ch == "*" and nxt == "/":
                out[i] = out[i + 1] = " "
                i += 2
                state = "code"
                continue
            if ch != "\n":
                out[i] = " "
        elif state in ("string", "char"):
            delimiter = '"' if state == "string" else "'"
            if ch == "\\" and i + 1 < len(source):
                out[i] = out[i + 1] = " "
                i += 2
                continue
            if ch == delimiter:
                out[i] = " "
                state = "code"
            elif ch != "\n":
                out[i] = " "
        i += 1
    if state in ("block", "string", "char"):
        raise RuntimeError(f"unterminated {state}")
    return "".join(out)


def check_delimiters(path: Path) -> None:
    source = strip_comments_and_strings(path.read_text(encoding="utf-8"))
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[tuple[str, int]] = []
    for offset, ch in enumerate(source):
        if ch in "([{":
            stack.append((ch, offset))
        elif ch in pairs:
            if not stack or stack[-1][0] != pairs[ch]:
                line = source.count("\n", 0, offset) + 1
                raise RuntimeError(f"unbalanced {ch} in {path.relative_to(ROOT)}:{line}")
            stack.pop()
    if stack:
        opening, offset = stack[-1]
        line = source.count("\n", 0, offset) + 1
        raise RuntimeError(f"unclosed {opening} in {path.relative_to(ROOT)}:{line}")


def check_guards(path: Path) -> None:
    if path.suffix.lower() != ".mqh":
        return
    directives = re.findall(r"^\s*#\s*(ifndef|ifdef|if|endif)\b", path.read_text(), re.MULTILINE)
    depth = 0
    for directive in directives:
        if directive in ("ifndef", "ifdef", "if"):
            depth += 1
        else:
            depth -= 1
            if depth < 0:
                raise RuntimeError(f"extra #endif in {path.relative_to(ROOT)}")
    if depth:
        raise RuntimeError(f"unterminated preprocessor conditional in {path.relative_to(ROOT)}")


def check_contract(paths: list[Path]) -> None:
    relative = {path.relative_to(ROOT).as_posix() for path in paths}
    required = {
        "Experts/Emtt.mq5",
        "Include/Emtt/Emtt_Dashboard.mqh",
        "Include/Emtt/Emtt_DynamicParams.mqh",
        "Include/Emtt/Emtt_Regime.mqh",
        "Include/Emtt/Emtt_Supertrend.mqh",
        "Include/Emtt/Emtt_SMC.mqh",
        "Include/Emtt/Emtt_VolumeFlow.mqh",
        "Include/Emtt/Emtt_MTF.mqh",
    }
    missing = required - relative
    if missing:
        raise RuntimeError(f"required source files are not in the EA include graph: {sorted(missing)}")

    ea = ENTRY.read_text(encoding="utf-8")
    for handler in ("OnInit", "OnDeinit", "OnTick", "OnTimer", "OnChartEvent"):
        if not re.search(rf"\b{handler}\s*\(", ea):
            raise RuntimeError(f"missing EA event handler {handler}")
    if '#include "../Include/Emtt/Emtt_Dashboard.mqh"' not in ea:
        raise RuntimeError("Phase-1 dashboard include path changed")
    dashboard = ROOT / "Include" / "Emtt" / "Emtt_Dashboard.mqh"
    digest = hashlib.sha256(dashboard.read_bytes()).hexdigest()
    phase1_digest = "cc4169b5bd8e5fd5e50ca74bef13b5f363579595a52f38707c561e9ea1612f5e"
    if digest != phase1_digest:
        raise RuntimeError("Phase-1 Emtt_Dashboard.mqh must remain unchanged")

    dynamic = (ROOT / "Include" / "Emtt" / "Emtt_DynamicParams.mqh").read_text()
    regime = (ROOT / "Include" / "Emtt" / "Emtt_Regime.mqh").read_text()
    phase2_markers = (
        (dynamic, r"EMTT_VOLATILITY_WINDOW\s+200", "fixed 200-bar volatility window"),
        (dynamic, r"percentile\s*>\s*70\.0", "high-volatility entry margin"),
        (dynamic, r"percentile\s*<\s*67\.0", "high-volatility exit margin"),
        (dynamic, r"percentile\s*<\s*30\.0", "low-volatility entry margin"),
        (dynamic, r"percentile\s*>\s*33\.0", "low-volatility exit margin"),
        (regime, r"efficiency\s*>\s*62\.0", "trending entry threshold"),
        (regime, r"efficiency\s*>=\s*58\.0", "trending exit margin"),
        (regime, r"efficiency\s*<\s*28\.0", "ranging entry threshold"),
        (regime, r"efficiency\s*<=\s*32\.0", "ranging exit margin"),
        (regime, r"atrRatio\s*>\s*1\.5", "volatile entry threshold"),
        (regime, r"atrRatio\s*>=\s*1\.3", "volatile exit margin"),
        (dynamic, r"EMTT_PARAMETER_PAUSE_BARS\s+2", "two-closed-bar parameter pause"),
    )
    for source, pattern, description in phase2_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-2 rule: {description}")

    supertrend = (ROOT / "Include" / "Emtt" / "Emtt_Supertrend.mqh").read_text()
    phase3_markers = (
        (supertrend, r"EMTT_ST_WINDOW_BASE\s+200", "200-bar K-Means training window base"),
        (supertrend, r"EMTT_ST_ATR_BASELINE_BARS\s+50", "50-bar ATR baseline in the history gate"),
        (supertrend, r"EMTT_ST_CLUSTERS\s+3", "three K-Means clusters (Calm/Normal/Wild)"),
        (supertrend, r"EMTT_ST_KMEANS_ITERATIONS\s+20", "Lloyd iteration cap of 20"),
        (supertrend, r"EMTT_ST_MIN_MEMBERS\s+5", "sparse-cluster guard of 5 bars"),
        (supertrend, r"EMTT_ST_MULTIPLIER_MIN\s+2\.0", "candidate multiplier floor 2.0"),
        (supertrend, r"EMTT_ST_MULTIPLIER_MAX\s+4\.0", "candidate multiplier ceiling 4.0"),
        (supertrend, r"EMTT_ST_DEFAULT_MULTIPLIER\s+3\.0", "unlearned-cluster default 3.0"),
        (supertrend, r"EMTT_ST_WHIPSAW_PENALTY\s+0\.10", "fixed whipsaw penalty 0.10"),
        (supertrend, r"EMTT_ST_RETRAIN_DIVISOR\s+20", "retrain cadence window / 20"),
        (supertrend, r"EmttCanChangeAt\(barSequence", "two-closed-bar multiplier pause"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_Supertrend\.mqh"', "quoted repo-relative Phase-3 include"),
        (ea, r"SEmttSupertrendState\s+g_supertrend;", "exactly one Supertrend state instance"),
        (ea, r"EmttSupertrendAdvance\(", "Supertrend advanced on the closed-bar path"),
        (ea, r"EmttWhyWithSupertrend\(", "Row 9 Supertrend clause wired into FillPanel"),
    )
    for source, pattern, description in phase3_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-3 rule: {description}")

    smc = (ROOT / "Include" / "Emtt" / "Emtt_SMC.mqh").read_text()
    phase4_markers = (
        (smc, r"EMTT_SMC_DISPLACEMENT_MULTIPLE\s+1\.5", "1.5x displacement multiple"),
        (smc, r"EMTT_SMC_IMPULSE_BARS\s+3", "three-bar impulse window"),
        (smc, r"EMTT_SMC_EQUAL_TOLERANCE_ATR\s+0\.10", "0.10 ATR equal-level tolerance"),
        (smc, r"EMTT_SMC_ZONE_DEADBAND\s+0\.05", "five-percent zone dead band"),
        (smc, r"EMTT_SMC_MIN_RANGE_ATR\s+1\.0", "one-ATR minimum dealing range"),
        (smc, r"EMTT_SMC_MAX_ZONES\s+8", "eight-zone capacity"),
        (smc, r"EMTT_SMC_MAX_SWINGS\s+64", "64 confirmed-swing bound"),
        (smc, r"EMTT_SMC_WEIGHT_STRUCTURE\s+0\.30", "structure score weight"),
        (smc, r"EMTT_SMC_WEIGHT_FRESHNESS\s+0\.20", "freshness score weight"),
        (smc, r"EMTT_SMC_WEIGHT_ZONE\s+0\.20", "zone score weight"),
        (smc, r"EMTT_SMC_WEIGHT_PROXIMITY\s+0\.15", "proximity score weight"),
        (smc, r"EMTT_SMC_WEIGHT_SWEEP\s+0\.15", "sweep score weight"),
        (smc, r"EMTT_SMC_EVENT_AGE_BARS\s+40", "40-bar event age scale"),
        (smc, r"EMTT_SMC_PROXIMITY_ATRS\s+2\.0", "two-ATR proximity scale"),
        (smc, r"EMTT_SMC_SWEEP_AGE_BARS\s+20", "20-bar sweep age scale"),
        (smc, r"EMTT_SMC_CHOCH_TERM\s+0\.6", "CHoCH structure term"),
        (smc, r"EMTT_SMC_OB_LOOKBACK_DIVISOR\s+3", "OB lookback divisor"),
        (smc, r"EMTT_SMC_OB_LOOKBACK_MIN\s+10", "OB lookback floor"),
        (smc, r"EMTT_SMC_WINDOW_MIN\s+20", "structure window floor"),
        (smc, r"EMTT_SMC_WINDOW_MAX\s+400", "structure window ceiling"),
        (smc, r"EMTT_SMC_STATUS_FRESH_BARS\s+3", "three-bar status freshness"),
        (smc, r"EMTT_SMC_SWEEP_MENTION_BARS\s+10", "ten-bar sweep mention window"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_SMC\.mqh"', "quoted repo-relative Phase-4 include"),
        (ea, r"SEmttSmcState\s+g_smc;", "exactly one SMC state instance"),
        (ea, r"EmttSmcAdvance\(", "SMC advanced on the closed-bar path"),
        (ea, r"EmttWhyWithSmc\(", "Row 9 SMC clause wired into FillPanel"),
        (ea, r"EmttResolveHistoryRequired\(", "combined SMC/Supertrend history gate"),
    )
    for source, pattern, description in phase4_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-4 rule: {description}")
    if len(re.findall(r"\bSEmttSmcState\s+g_smc\s*;", ea)) != 1:
        raise RuntimeError("Phase 4 must declare exactly one EA SMC state instance")
    if ea.find('Emtt_Supertrend.mqh') > ea.find('Emtt_SMC.mqh'):
        raise RuntimeError("Phase-4 include must follow Emtt_Supertrend.mqh")

    # Rule 13.2 is deliberately machine-enforced. The component can calculate
    # levels but never creates a chart artifact; panel rendering remains in the
    # Phase-1 header and its digest is guarded above.
    forbidden_smc = (
        r"\bObjectCreate\s*\(",
        r"\bOBJ_TREND\b",
        r"\bOBJ_RECTANGLE\b",
        r"\bOBJ_HLINE\b",
        r"\bOBJ_ARROW\b",
        r"\bOBJ_TEXT\b",
        r"\bOBJ_FIBO\w*\b",
    )
    for pattern in forbidden_smc:
        if re.search(pattern, smc):
            raise RuntimeError(f"Phase-4 SMC source contains forbidden chart drawing token: {pattern}")

    phase5_volume_flow = (ROOT / "Include" / "Emtt" / "Emtt_VolumeFlow.mqh").read_text()
    phase5_mtf = (ROOT / "Include" / "Emtt" / "Emtt_MTF.mqh").read_text()
    phase5_markers = (
        (phase5_volume_flow, r"EMTT_VF_BINS\s+40", "40 profile bins"),
        (phase5_volume_flow, r"EMTT_VF_VALUE_AREA\s+0\.70", "70 percent value area"),
        (phase5_volume_flow, r"EMTT_VF_CVD_WINDOW\s+10", "10-bar CVD comparison window"),
        (phase5_volume_flow, r"EMTT_VF_CVD_FLIP\s+0\.25", "CVD flip band of 0.25 window volume"),
        (phase5_volume_flow, r"EMTT_VF_CONTROL_SCALE\s+0\.5", "control scale of half the window volume"),
        (phase5_volume_flow, r"EMTT_VF_MAGNET_ATRS\s+3\.0", "three-ATR magnet proximity scale"),
        (phase5_volume_flow, r"EMTT_VF_WEIGHT_CONTROL\s+0\.35", "control score weight"),
        (phase5_volume_flow, r"EMTT_VF_WEIGHT_FAIR\s+0\.25", "fair-price score weight"),
        (phase5_volume_flow, r"EMTT_VF_WEIGHT_VALUE\s+0\.20", "value-area score weight"),
        (phase5_volume_flow, r"EMTT_VF_WEIGHT_MAGNET\s+0\.20", "magnet score weight"),
        (phase5_volume_flow, r"EMTT_VF_WINDOW_MIN\s+50", "profile window floor"),
        (phase5_volume_flow, r"EMTT_VF_WINDOW_MAX\s+400", "profile window ceiling"),
        (phase5_volume_flow, r"EMTT_VF_SESSION_DEPTH\s+160", "160-bar session depth"),
        (phase5_volume_flow, r"EMTT_VF_STATUS_FRESH_BARS\s+3", "three-bar flow status freshness"),
        (phase5_mtf, r"EMTT_MTF_WEIGHT_DIRECTION\s+0\.50", "direction agreement weight"),
        (phase5_mtf, r"EMTT_MTF_WEIGHT_REGIME\s+0\.30", "HTF regime weight"),
        (phase5_mtf, r"EMTT_MTF_WEIGHT_STRUCTURE\s+0\.20", "HTF structure weight"),
        (phase5_mtf, r"EMTT_MTF_FETCH_BUFFER\s+10", "ten-bar HTF fetch buffer"),
        (phase5_mtf, r"EMTT_MTF_STATUS_FRESH_BARS\s+3", "three-bar HTF status freshness"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_VolumeFlow\.mqh"', "quoted repo-relative Phase-5 volume-flow include"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_MTF\.mqh"', "quoted repo-relative Phase-5 MTF include"),
        (ea, r"SEmttVolumeFlowState\s+g_volumeFlow;", "exactly one volume-flow state instance"),
        (ea, r"SEmttMtfState\s+g_mtf;", "exactly one MTF state instance"),
        (ea, r"SEmttMtfContext\s+g_mtfContext;", "exactly one MTF context instance"),
        (ea, r"EmttVolumeFlowAdvance\(", "volume flow advanced on the closed-bar path"),
        (ea, r"EmttMtfAdvance\(", "HTF context polled on the closed-bar and timer paths"),
        (ea, r"EmttWhyWithVolumeFlow\(", "Row 9 volume-flow clause wired into FillPanel"),
        (ea, r"EmttWhyWithMtf\(", "Row 9 MTF clause wired into FillPanel"),
        (ea, r"EmttVfHistoryRequired\(", "combined volume-flow history gate"),
    )
    for source, pattern, description in phase5_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-5 rule: {description}")
    if len(re.findall(r"\bSEmttVolumeFlowState\s+g_volumeFlow\s*;", ea)) != 1:
        raise RuntimeError("Phase 5 must declare exactly one EA volume-flow state instance")
    if len(re.findall(r"\bSEmttMtfState\s+g_mtf\s*;", ea)) != 1:
        raise RuntimeError("Phase 5 must declare exactly one EA MTF state instance")
    if len(re.findall(r"\bSEmttMtfContext\s+g_mtfContext\s*;", ea)) != 1:
        raise RuntimeError("Phase 5 must declare exactly one EA MTF context instance")
    if ea.find("Emtt_SMC.mqh") > ea.find("Emtt_VolumeFlow.mqh"):
        raise RuntimeError("Phase-5 volume-flow include must follow Emtt_SMC.mqh")
    if ea.find("Emtt_VolumeFlow.mqh") > ea.find("Emtt_MTF.mqh"):
        raise RuntimeError("Phase-5 MTF include must follow Emtt_VolumeFlow.mqh")

    # Rule 15.2 stands on 13.2 rule 1: neither new header may create a chart
    # artifact. The Phase-4 forbidden-token list is applied to both.
    for source, name in ((phase5_volume_flow, "volume-flow"), (phase5_mtf, "MTF")):
        for pattern in forbidden_smc:
            if re.search(pattern, source):
                raise RuntimeError(
                    f"Phase-5 {name} source contains forbidden chart drawing token: {pattern}"
                )




def run_metaeditor(paths: list[Path]) -> None:
    compiler = os.environ.get("METAEDITOR_PATH")
    if not compiler:
        return
    log_path = ROOT / "mql5-compile-smoke.log"
    command = [compiler, f"/compile:{ENTRY}", f"/log:{log_path}"]
    result = subprocess.run(command, cwd=ROOT, timeout=180, check=False)
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    if result.returncode != 0 or re.search(r"\b[1-9][0-9]*\s+error", log, re.IGNORECASE):
        raise RuntimeError(f"MetaEditor compile failed (exit {result.returncode}):\n{log}")
    print("MetaEditor compilation passed.")


def main() -> int:
    paths = resolve_include_graph(ENTRY)
    for path in paths:
        check_delimiters(path)
        check_guards(path)
    check_contract(paths)
    run_metaeditor(paths)
    print("MQL5 include-layout / structural compile smoke passed:")
    for path in sorted(paths):
        print(f"  {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # surfaced as a concise CI failure
        print(f"MQL5 smoke check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
