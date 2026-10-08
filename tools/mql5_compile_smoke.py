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
