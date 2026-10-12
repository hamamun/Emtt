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

# --- Phase 11 (Emtt.md 28.1): the only edits to three frozen headers. ---
# Each pair is (Phase 10 text, Phase 11 text). Reversing them must give
# back the frozen hash byte-for-byte, so any other change fails.
PHASE11_SIGNAL_EDITS = (
    ('#include "Emtt_TradePlan.mqh"\n\n//--- 17.3',
     '#include "Emtt_TradePlan.mqh"\n#include "Emtt_Tier.mqh"\n\n//--- 17.3'),
    ('      case EMTT_SIG_WAIT_BELOW_BAR:\n'
     '         return "below the "+IntegerToString(state.moodBar)+"% bar";\n'
     '      case EMTT_SIG_WAIT_BELOW_KEEP:\n'
     '         return "below the "+\n'
     '                IntegerToString(state.moodBar-EMTT_SIG_STAY_MARGIN)+\n'
     '                "% level that keeps a "+EmttPlanSideName(state.waitSide);\n',
     '      case EMTT_SIG_WAIT_BELOW_BAR:\n'
     '         return "below the "+IntegerToString(EMTT_TIER_DISPLAY_MIN)+\n'
     '                "% display level (Very low)";\n'
     '      case EMTT_SIG_WAIT_BELOW_KEEP:\n'
     '         return "below the "+IntegerToString(EMTT_TIER_DISPLAY_MIN)+\n'
     '                "% level that keeps a "+EmttPlanSideName(state.waitSide)+\n'
     '                " (Very low)";\n'),
    ('      case EMTT_SIG_WAIT_BELOW_BAR:\n'
     '         return "Watching \\x2014 confidence "+number+", below the "+\n'
     '                IntegerToString(state.moodBar)+"% bar.";\n'
     '      case EMTT_SIG_WAIT_BELOW_KEEP:\n'
     '         return "Watching \\x2014 confidence "+number+", below the "+\n'
     '                IntegerToString(state.moodBar-EMTT_SIG_STAY_MARGIN)+\n'
     '                "% level that keeps a "+EmttPlanSideName(state.waitSide)+".";\n',
     '      case EMTT_SIG_WAIT_BELOW_BAR:\n'
     '      case EMTT_SIG_WAIT_BELOW_KEEP:\n'
     '         // Phase 11 (28.6): below 35% the real number and tier show.\n'
     '         return EmttTierWatchingLine(state.confidence);\n'),
    ('   const int barLevel=state.moodBar;\n'
     '   const int keepLevel=barLevel-EMTT_SIG_STAY_MARGIN;\n',
     '   // Phase 11 (28.3): the display gate is the fixed 35% tier floor for\n'
     '   // entering and keeping; the mood / learned bar stays internal.\n'
     '   const int barLevel=EMTT_TIER_DISPLAY_MIN;\n'
     '   const int keepLevel=EMTT_TIER_DISPLAY_MIN;\n'),
    ('      // A showing BUY or SELL stays while its own number is at least\n'
     '      // bar - 5; entering needs the bar, staying needs bar - 5.\n',
     '      // A showing BUY or SELL stays while its own number is at least\n'
     '      // 35%; Phase 11 (28.3) enters and keeps at the same tier floor.\n'),
    ('                        EmttSignalMoodWord(mood),barLevel,\n',
     '                        EmttSignalMoodWord(mood),state.moodBar,\n'),
)

PHASE11_TRADE_EDITS = (
    ('#include "Emtt_TradePlan.mqh"\n',
     '#include "Emtt_TradePlan.mqh"\n#include "Emtt_Tier.mqh"\n'),
    ('   EMTT_TRADE_GATE_MARGIN\n  };',
     '   EMTT_TRADE_GATE_MARGIN,\n   EMTT_TRADE_GATE_BELOW_THRESHOLD   // Phase 11 (28.4)\n  };'),
    ('   bool   marginFits;\n  };',
     '   bool   marginFits;\n   int    confidence;      // Phase 11: displayed confidence\n'
     '   int    autoTradeAbove;  // Phase 11: "Auto-trade above (%)"\n  };'),
    ('      return EMTT_TRADE_GATE_AUTO_OFF;\n   if(!gateInput.terminalAllowed',
     '      return EMTT_TRADE_GATE_AUTO_OFF;\n'
     '   if(!EmttTierAutoTradeAllowed(gateInput.confidence,\n'
     '                                gateInput.autoTradeAbove))\n'
     '      return EMTT_TRADE_GATE_BELOW_THRESHOLD;\n'
     '   if(!gateInput.terminalAllowed'),
    ('string EmttTradeGateStatus(const EEmttTradeGateFailure failure,\n'
     '                           const int spreadPoints)\n',
     'string EmttTradeGateStatus(const EEmttTradeGateFailure failure,\n'
     '                           const int spreadPoints,\n'
     '                           const int confidence=0,const int side=0,\n'
     '                           const int autoTradeAbove=0)\n'),
    ('         return "No trade "+EmttTradeDash()+" not enough margin";\n      default:',
     '         return "No trade "+EmttTradeDash()+" not enough margin";\n'
     '      case EMTT_TRADE_GATE_BELOW_THRESHOLD:\n'
     '         return EmttTierBelowThresholdLine(confidence,side,autoTradeAbove);\n'
     '      default:'),
    ('   if(confidence>=90) return EMTT_TRADE_SIZE_CONF_90;\n'
     '   if(confidence>=80) return EMTT_TRADE_SIZE_CONF_80;\n'
     '   if(confidence>=70) return EMTT_TRADE_SIZE_CONF_70;\n'
     '   // The stay band can hold a plan at 55-59. Use the lowest approved\n'
     '   // confidence multiplier there; a new plan itself still met its bar.\n'
     '   return EMTT_TRADE_SIZE_CONF_60;\n',
     '   // Phase 11 (28.5): the multiplier follows the displayed tier -\n'
     '   // Low 0.7 / Normal 1.0 / Confident 1.2 / High 1.5.\n'
     '   return EmttTierSizeMultiplier(confidence);\n'),
)

PHASE11_DASHBOARD_EDITS = (
    ("#define EMTT_CLR_SELL   C'235,111,111'   // SELL / loss / warning   #EB6F6F\n",
     "#define EMTT_CLR_SELL   C'235,111,111'   // SELL / loss / warning   #EB6F6F\n"
     "// Phase 11 (28.2): the two intermediate signal shades, blends of the\n"
     "// signal colour toward the soft text grey C'200,200,200'.\n"
     "#define EMTT_CLR_BUY_LOW     C'156,204,176'   // Low BUY (50%)     #9CCCB0\n"
     "#define EMTT_CLR_SELL_LOW    C'218,156,156'   // Low SELL (50%)    #DA9C9C\n"
     "#define EMTT_CLR_BUY_NORMAL  C'133,205,163'   // Normal BUY (25%)  #85CDA3\n"
     "#define EMTT_CLR_SELL_NORMAL C'226,133,133'   // Normal SELL (25%) #E28585\n"),
    ('#define EMTT_FONT       "Segoe UI"\n',
     '#define EMTT_FONT       "Segoe UI"\n'
     '#define EMTT_FONT_BOLD  "Segoe UI Bold"  // Phase 11: High-confidence SIGNAL\n'),
    ('   int    signalSize;  // rule 16: 14 for BUY/SELL, else 12\n',
     '   int    signalSize;  // rule 16: 14 for BUY/SELL, else 12\n'
     '   bool   signalBold;  // Phase 11 (28.2): bold for the High tier only\n'),
    ('int    b_kind[];                // 0=header text, 1=row text, 2=separator\n',
     'int    b_kind[];                // 0=header text, 1=row text, 2=separator\n'
     'bool   b_bold[];                // Phase 11: bold face for this row\n'),
    ('double EmttTextWidth(const string text,const int size)\n',
     'double EmttTextWidth(const string text,const int size,const bool bold=false)\n'),
    ('   const string key=IntegerToString(size)+"|"+text;\n',
     '   const string key=(bold ? "B" : "")+IntegerToString(size)+"|"+text;\n'),
    ('   ObjectSetString(0,name,OBJPROP_FONT,EMTT_FONT);\n'
     '   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);\n'
     '   ObjectSetString(0,name,OBJPROP_TEXT,text);\n'
     '   ChartRedraw();\n',
     '   ObjectSetString(0,name,OBJPROP_FONT,(bold ? EMTT_FONT_BOLD : EMTT_FONT));\n'
     '   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);\n'
     '   ObjectSetString(0,name,OBJPROP_TEXT,text);\n'
     '   ChartRedraw();\n'),
    ('void BAdd(const string t,const color c,const int sz,const int k)\n'
     '  {\n'
     '   ArrayResize(b_text,b_n+1);\n'
     '   ArrayResize(b_clr,b_n+1);\n'
     '   ArrayResize(b_size,b_n+1);\n'
     '   ArrayResize(b_kind,b_n+1);\n'
     '   b_text[b_n]=t;\n'
     '   b_clr[b_n]=c;\n'
     '   b_size[b_n]=sz;\n'
     '   b_kind[b_n]=k;\n',
     'void BAdd(const string t,const color c,const int sz,const int k,\n'
     '          const bool bold=false)\n'
     '  {\n'
     '   ArrayResize(b_text,b_n+1);\n'
     '   ArrayResize(b_clr,b_n+1);\n'
     '   ArrayResize(b_size,b_n+1);\n'
     '   ArrayResize(b_kind,b_n+1);\n'
     '   ArrayResize(b_bold,b_n+1);\n'
     '   b_text[b_n]=t;\n'
     '   b_clr[b_n]=c;\n'
     '   b_size[b_n]=sz;\n'
     '   b_kind[b_n]=k;\n'
     '   b_bold[b_n]=bold;\n'),
    ('void ApplyLabel(const string name,const int x,const int y,const string text,\n'
     '                const color clr,const int size)\n'
     '  {\n'
     '   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);\n'
     '   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);\n'
     '   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);\n'
     '   ObjectSetString(0,name,OBJPROP_FONT,EMTT_FONT);\n',
     'void ApplyLabel(const string name,const int x,const int y,const string text,\n'
     '                const color clr,const int size,const bool bold=false)\n'
     '  {\n'
     '   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);\n'
     '   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);\n'
     '   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);\n'
     '   ObjectSetString(0,name,OBJPROP_FONT,(bold ? EMTT_FONT_BOLD : EMTT_FONT));\n'),
    ('                    b_text[i],b_clr[i],b_size[i]);\n',
     '                    b_text[i],b_clr[i],b_size[i],b_bold[i]);\n'),
    ('   BAdd(d.signal,d.signalClr,d.signalSize,1);\n',
     '   BAdd(d.signal,d.signalClr,d.signalSize,1,d.signalBold);\n'),
    ('      maxw=MathMax(maxw,(int)EmttTextWidth(b_text[i],b_size[i]));\n',
     '      maxw=MathMax(maxw,(int)EmttTextWidth(b_text[i],b_size[i],b_bold[i]));\n'),
)


def phase11_reverse(text: str, edits: tuple) -> str:
    """Undo the Phase 11 edit pairs, last first."""
    for old, new in reversed(edits):
        text = text.replace(new, old, 1)
    return text
# Resolve only repo-relative quoted includes. MetaEditor owns angle-bracket
# standard-library headers such as <Trade/Trade.mqh>.
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"', re.MULTILINE)


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


RATES_VARIABLE_RE = re.compile(r"\bMqlRates\s*&?\s*([A-Za-z_]\w*)")
RATES_VOLUME_MEMBER_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\.\s*volume\b(?!\w)")


def check_mqlrates_volume(paths: list[Path]) -> None:
    """Reject `MqlRates.volume`, which is not an MQL5 member.

    A bar carries `tick_volume` (what the spec's `volume_i` means) and
    `real_volume`; there is no `volume` field. Phase 5 reads the volume
    through EmttVfBarVolume() in Emtt_VolumeFlow.mqh, so any `.volume` access
    on a rates record is the spec-wording typo that broke the MetaEditor
    build with seven `undeclared identifier 'volume'` errors. Comments and
    string literals are blanked first, so only code can trip this.
    """
    for path in paths:
        if path.suffix.lower() not in (".mqh", ".mq5"):
            continue
        source = strip_comments_and_strings(path.read_text(encoding="utf-8"))
        rates_names = {match.group(1) for match in RATES_VARIABLE_RE.finditer(source)}
        match = None
        for member in RATES_VOLUME_MEMBER_RE.finditer(source):
            if member.group(1) in rates_names:
                match = member
                break
        if match:
            line = source.count("\n", 0, match.start()) + 1
            raise RuntimeError(
                f"{path.relative_to(ROOT)}:{line} reads a `.volume` member; "
                "MqlRates has tick_volume / real_volume only"
            )


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
        "Include/Emtt/Emtt_TradePlan.mqh",
        "Include/Emtt/Emtt_Tier.mqh",
        "Include/Emtt/Emtt_Signal.mqh",
        "Include/Emtt/Emtt_Summary.mqh",
        "Include/Emtt/Emtt_LearnFile.mqh",
        "Include/Emtt/Emtt_Learning.mqh",
        "Include/Emtt/Emtt_ParamFile.mqh",
        "Include/Emtt/Emtt_ParamOpt.mqh",
        "Include/Emtt/Emtt_TickDivergence.mqh",
        "Include/Emtt/Emtt_Trade.mqh",
        "Include/Emtt/Emtt_TradeManager.mqh",
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
    # Phase 11 (28.2) adds only two shades, a bold face and its plumbing.
    digest = hashlib.sha256(phase11_reverse(dashboard.read_text(encoding="utf-8"),
                                            PHASE11_DASHBOARD_EDITS).encode()).hexdigest()
    # Phase-1 digest cc4169b5... superseded by the author-approved panel
    # revamp of 2026-10-11 (WHY removed, STATUS single-line, Summary
    # Today/All-Time, dynamic width, no cap).
    panel_digest = "22392551ed94bb3c38badea5b74e589c5d90f6ca75f41d8cb4ced541b4077b70"
    if digest != panel_digest:
        raise RuntimeError("Emtt_Dashboard.mqh changed without updating the panel digest")

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
        (phase5_volume_flow, r"EmttVfBarVolume\(", "single MqlRates.tick_volume reader"),
        (phase5_volume_flow, r"tick_volume", "tick volume as the bar volume source"),
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

    #--- Phase 6 (17.9) -------------------------------------------------
    phase6_trade_plan = (ROOT / "Include" / "Emtt" / "Emtt_TradePlan.mqh").read_text()
    # Phase 11 (28.3) edits are reversed first, so every earlier check
    # still reads the signal header it froze.
    phase6_signal = phase11_reverse((ROOT / "Include" / "Emtt" / "Emtt_Signal.mqh").read_text(),
                                    PHASE11_SIGNAL_EDITS)
    phase6_markers = (
        (phase6_signal, r"EMTT_SIG_WEIGHT_TREND\s+0\.30", "trend confidence weight"),
        (phase6_signal, r"EMTT_SIG_WEIGHT_STRUCTURE\s+0\.30", "structure confidence weight"),
        (phase6_signal, r"EMTT_SIG_WEIGHT_FLOW\s+0\.20", "volume-flow confidence weight"),
        (phase6_signal, r"EMTT_SIG_WEIGHT_HTF\s+0\.20", "higher-chart confidence weight"),
        (phase6_signal, r"EMTT_SIG_STAY_MARGIN\s+5", "five-point stay margin"),
        (phase6_trade_plan, r"EMTT_PLAN_STOP_BUFFER_ATR\s+0\.5", "stop buffer beyond the reference"),
        (phase6_trade_plan, r"EMTT_PLAN_STOP_MIN_ATR\s+1\.0", "stop minimum distance from entry"),
        (phase6_trade_plan, r"EMTT_PLAN_STOP_MAX_ATR\s+3\.0", "stop maximum distance from entry"),
        (phase6_trade_plan, r"EMTT_PLAN_ENTRY_REACH_ATR\s+2\.0", "entry reach to the block edge"),
        (phase6_trade_plan, r"EMTT_PLAN_SPEED_FLOOR\s+0\.2", "expected-duration speed floor"),
        (phase6_trade_plan, r"EMTT_PLAN_DURATION_LOW\s+0\.5", "duration band low multiple"),
        (phase6_trade_plan, r"EMTT_PLAN_DURATION_HIGH\s+1\.5", "duration band high multiple"),
        (phase6_trade_plan, r"EMTT_PLAN_RR_TREND\s+1\.5", "minimum risk:reward in a trend"),
        (phase6_trade_plan, r"EMTT_PLAN_RR_OTHER\s+2\.0", "minimum risk:reward in other moods"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_TradePlan\.mqh"', "quoted repo-relative Phase-6 trade-plan include"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_Signal\.mqh"', "quoted repo-relative Phase-6 signal include"),
        (ea, r"SEmttSignalState\s+g_signal;", "exactly one signal state instance"),
        (ea, r"EmttSignalAdvance\(", "signal advanced on the closed-bar path"),
        (ea, r"EmttSignalStatusText\(", "Row 10 signal line wired into FillPanel"),
    )
    for source, pattern, description in phase6_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-6 rule: {description}")
    if len(re.findall(r"\bSEmttSignalState\s+g_signal\s*;", ea)) != 1:
        raise RuntimeError("Phase 6 must declare exactly one EA signal state instance")
    if ea.find("Emtt_MTF.mqh") > ea.find("Emtt_TradePlan.mqh"):
        raise RuntimeError("Phase-6 trade-plan include must follow Emtt_MTF.mqh")
    if ea.find("Emtt_TradePlan.mqh") > ea.find("Emtt_Signal.mqh"):
        raise RuntimeError("Phase-6 signal include must follow Emtt_TradePlan.mqh")

    # 17.9 guard 1: the chart-drawing guard of 15.2 rule 1 (the Phase-4
    # forbidden list), applied to both new headers and the EA.
    for source, name in (
        (phase6_trade_plan, "trade-plan"),
        (phase6_signal, "signal"),
        (ea, "EA"),
    ):
        for pattern in forbidden_smc:
            if re.search(pattern, source):
                raise RuntimeError(
                    f"Phase-6 {name} source contains forbidden chart drawing token: {pattern}"
                )

    # 17.9 guard 2: the no-order guard, applied to both new headers and
    # the EA. Phase 6 says what Emtt would do; nothing sends, modifies,
    # closes or deletes an order or a position.
    forbidden_orders = (
        r"\bOrderSend\b",
        r"\bOrderSendAsync\b",
        r"\bOrderModify\b",
        r"\bOrderDelete\b",
        r"\bPositionModify\b",
        r"\bPositionClose\b",
        r"\bPositionCloseBy\b",
        r"\bCTrade\b",
    )
    for source, name in (
        (phase6_trade_plan, "trade-plan"),
        (phase6_signal, "signal"),
        (ea, "EA"),
    ):
        for pattern in forbidden_orders:
            if re.search(pattern, source):
                raise RuntimeError(
                    f"Phase-6 {name} source contains a forbidden order token: {pattern}"
                )

    # 17.9 guard 3: the ASCII guard (17.2 rule 9), applied to the two new
    # headers - any byte above 0x7F fails the build.
    for path, name in (
        (ROOT / "Include" / "Emtt" / "Emtt_TradePlan.mqh", "trade-plan"),
        (ROOT / "Include" / "Emtt" / "Emtt_Signal.mqh", "signal"),
    ):
        raw = path.read_bytes()
        for index, byte in enumerate(raw):
            if byte > 0x7F:
                line = raw.count(b"\n", 0, index) + 1
                raise RuntimeError(
                    f"Phase-6 {name} header is not ASCII-only: byte 0x{byte:02X} at line {line}"
                )

    # --- Panel revamp (2026-10-11, author direction) --------------------
    dashboard_text = dashboard.read_text(encoding="utf-8")
    summary_path = ROOT / "Include" / "Emtt" / "Emtt_Summary.mqh"
    summary = summary_path.read_text(encoding="utf-8")
    revamp_markers = (
        (dashboard_text, r"summaryToday", "Summary Today row in the panel data"),
        (dashboard_text, r"summaryAllTime", "Summary All-Time row in the panel data"),
        (dashboard_text, r'BAdd\("STATUS: "\+d\.status', "single-line STATUS (no wrap)"),
        (dashboard_text, r"g_panelWidth=maxw\+2\*EMTT_PAD_X", "dynamic width from the longest row"),
        (summary, r'EMTT_SUMMARY_VERSION\s+"Emtt_Summary v1"', "summary file version"),
        (summary, r'EMTT_SUMMARY_DIR\s+"Emtt_Learning"', "summary folder (shared with learning)"),
        (summary, r'EMTT_SUMMARY_EXT\s+"\.summary"', "summary file suffix"),
        (summary, r"FileMove\(tmpPath,0,state\.filePath,FILE_REWRITE\)", ".tmp whole-file rewrite"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_Summary\.mqh"', "quoted repo-relative summary include"),
        (ea, r"SEmttSummaryState\s+g_summary;", "exactly one summary state instance"),
        (ea, r"EmttSummaryInit\(", "summary loaded on init / context change"),
        (ea, r"EmttSummaryOnSignal\(", "signal counted on plan start"),
        (ea, r"EmttSummaryOnWin\(", "win counted on target"),
        (ea, r"EmttSummaryOnLoss\(", "loss counted on stop"),
        (ea, r"EmttConsumeSignalEvents\(", "signal events consumed after each advance"),
    )
    for source, pattern, description in revamp_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing panel-revamp rule: {description}")
    if len(re.findall(r"\bSEmttSummaryState\s+g_summary\s*;", ea)) != 1:
        raise RuntimeError("Panel revamp must declare exactly one EA summary state instance")
    if ea.find("Emtt_Signal.mqh") > ea.find("Emtt_Summary.mqh"):
        raise RuntimeError("Summary include must follow Emtt_Signal.mqh")
    if "VAddWrapped" in dashboard_text:
        raise RuntimeError("Panel revamp removed wrapping; VAddWrapped must be gone")
    if '"WHY: "' in dashboard_text:
        raise RuntimeError("Panel revamp removed the WHY row; no WHY label may render")

    # Revamp guards on the new header: the Phase-6 ASCII / no-order /
    # no-drawing guards, plus a file guard (the record lives only under
    # Emtt_Learning\, no deletes/copies, no shared-folder access).
    raw_summary = summary_path.read_bytes()
    for index, byte in enumerate(raw_summary):
        if byte > 0x7F:
            line = raw_summary.count(b"\n", 0, index) + 1
            raise RuntimeError(
                f"Panel-revamp summary header is not ASCII-only: byte 0x{byte:02X} at line {line}"
            )
    for pattern in forbidden_smc:
        if re.search(pattern, summary):
            raise RuntimeError(
                f"Panel-revamp summary source contains forbidden chart drawing token: {pattern}"
            )
    for pattern in forbidden_orders:
        if re.search(pattern, summary):
            raise RuntimeError(
                f"Panel-revamp summary source contains a forbidden order token: {pattern}"
            )
    forbidden_summary_files = (
        r"\bGlobalVariable\w*\s*\(",
        r"\bFileDelete\s*\(",
        r"\bFolderDelete\s*\(",
        r"\bFileCopy\s*\(",
        r"\bFILE_COMMON\b",
    )
    for pattern in forbidden_summary_files:
        if re.search(pattern, summary):
            raise RuntimeError(
                f"Panel-revamp summary source contains forbidden file token: {pattern}"
            )


    #--- Phase 7 (19.10) -------------------------------------------------
    phase7_learn_file = (ROOT / "Include" / "Emtt" / "Emtt_LearnFile.mqh").read_text()
    phase7_learning = (ROOT / "Include" / "Emtt" / "Emtt_Learning.mqh").read_text()
    phase7_markers = (
        (phase7_learning, r"EMTT_LEARN_FEATURES\s+16", "16-feature vector"),
        (phase7_learning, r"EMTT_LEARN_WARMUP\s+30", "30-labeled-ticket warm-up"),
        (phase7_learning, r"EMTT_LEARN_STRENGTH\s+0\.15", "0.15 learning strength"),
        (phase7_learning, r"EMTT_LEARN_RATE\s+0\.30", "0.30 / sqrt(k) learning rate"),
        (phase7_learning, r"EMTT_LEARN_CLAMP\s+4\.0", "weight clamp of +-4.0"),
        (phase7_learning, r"EMTT_LEARN_Z_CLAMP\s+30", "logistic clamp of +-30"),
        (phase7_learning, r"EMTT_LEARN_CONF_CAP\s+100", "confidence cap of 100"),
        (phase7_learn_file, r"EMTT_LEARN_CAP\s+500", "500-ticket cap"),
        (phase7_learn_file, r'EMTT_LEARN_VERSION\s+"Emtt_Learning v1"', "file version"),
        (phase7_learn_file, r'EMTT_LEARN_DIR\s+"Emtt_Learning"', "file folder"),
        (phase7_learn_file, r'EMTT_LEARN_EXT\s+"\.learn"', "file suffix"),
        (phase7_learning, r"EmttLearnBuildModel\(", "SGD build from the tickets"),
        (phase7_learning, r"EmttLearnWhyClause\(", "Row 9 clause text"),
        (phase7_learning, r"EmttLearnHoldReason\(", "Row 10 learning WAIT reason"),
        (phase7_learn_file, r"EmttLearnFileLoad\(", "load and recompute at init"),
        (phase7_learn_file, r"EmttLearnFileSave\(", "whole-file rewrite"),
        (phase7_learn_file, r"EmttLearnFileAddPlan\(", "plan start event"),
        (phase7_learn_file, r"EmttLearnFileMarkReached\(", "entry reach event"),
        (phase7_learn_file, r"EmttLearnFileCloseTicket\(", "plan end event"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_LearnFile\.mqh"', "quoted repo-relative learning-file include"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_Learning\.mqh"', "quoted repo-relative learning include"),
        (ea, r"SEmttLearningState\s+g_learning;", "exactly one learning state instance"),
        (ea, r"EmttLearningAttachAndLoad\(", "record bound and loaded by the replay"),
        (ea, r"EmttLearningReadCandle\(", "learned terms read on each closed candle"),
        (ea, r"EmttLearnPlanText\(", "plan-start journal learning part"),
        (ea, r"EmttLearnWhyAppend\(", "Row 9 learning clause appended last"),
        (ea, r"EmttLearningResume\(", "19.6 plan resume after the replay"),
        (ea, r"EmttLearnJournalResumed\(", "Learning resumed journal line"),
        (ea, r"EmttLearnFileSave\(g_learning\.file,", "the four write events save the record"),
        (ea, r'#property version\s+"1\.(?:60|70|80|90)"', "Phase 7 version stamp"),
        (ea, r'#property description "Phase 7: self-learning signal filter\."',
         "Phase 7 description line"),
    )
    for source, pattern, description in phase7_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-7 rule: {description}")
    if len(re.findall(r"\bSEmttLearningState\s+g_learning\s*;", ea)) != 1:
        raise RuntimeError("Phase 7 must declare exactly one EA learning state instance")
    if ea.find("Emtt_Signal.mqh") > ea.find("Emtt_LearnFile.mqh"):
        raise RuntimeError("Phase-7 learning-file include must follow Emtt_Signal.mqh")
    if ea.find("Emtt_LearnFile.mqh") > ea.find("Emtt_Learning.mqh"):
        raise RuntimeError("Phase-7 learning include must follow Emtt_LearnFile.mqh")
    if phase7_learning.find("Emtt_LearnFile.mqh") > phase7_learning.find("Emtt_Signal.mqh"):
        raise RuntimeError("Emtt_Learning.mqh must include the record before the signal")

    # 19.10 guards 1-3 on the two new headers: no chart drawing (15.2 rule
    # 1), no order token (17.9) and ASCII-only source (17.2 rule 9).
    for path, name in (
        (ROOT / "Include" / "Emtt" / "Emtt_LearnFile.mqh", "learning-file"),
        (ROOT / "Include" / "Emtt" / "Emtt_Learning.mqh", "learning"),
    ):
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_smc:
            if re.search(pattern, text):
                raise RuntimeError(
                    f"Phase-7 {name} source contains forbidden chart drawing token: {pattern}"
                )
        for pattern in forbidden_orders:
            if re.search(pattern, text):
                raise RuntimeError(
                    f"Phase-7 {name} source contains a forbidden order token: {pattern}"
                )
        raw = path.read_bytes()
        for index, byte in enumerate(raw):
            if byte > 0x7F:
                line = raw.count(b"\n", 0, index) + 1
                raise RuntimeError(
                    f"Phase-7 {name} header is not ASCII-only: byte 0x{byte:02X} at line {line}"
                )

    # 19.10 guard 4: the file guard. The record is the only thing the phase
    # writes, it lives only under Emtt_Learning\, the whole-file rewrite is
    # the one .tmp rename, and nothing is deleted or copied.
    for text, name in ((phase7_learn_file, "learning-file"),
                       (phase7_learning, "learning")):
        for pattern in (r"\bGlobalVariable\w*\s*\(", r"\bFileDelete\s*\(",
                        r"\bFolderDelete\s*\(", r"\bFileCopy\s*\(",
                        r"\bFolderCreate\s*\([^)]*\bFILE_COMMON\b",
                        r"\bFILE_COMMON\b", r"\bTerminalInfoString\s*\(",
                        r'\bFileOpen\s*\(\s*"'):
            if re.search(pattern, text):
                raise RuntimeError(
                    f"Phase-7 {name} source contains forbidden file token: {pattern}"
                )
        moves = re.findall(r"\bFileMove\s*\([^;]*\)", text)
        if name == "learning":
            if moves:
                raise RuntimeError("Phase-7 learning source must not move a file")
        else:
            if len(moves) != 1 or "FILE_REWRITE" not in moves[0]:
                raise RuntimeError(
                    "Phase-7 learning-file source must hold exactly one .tmp rename"
                )
            if "tmpPath" not in moves[0] or "state.filePath" not in moves[0]:
                raise RuntimeError("Phase-7 .tmp rename must be the record's own rename")
    # No path outside Emtt_Learning\: after every escape the grammar
    # needs (the folder separator, the \r\n line ends and the \x2014 dash of
    # 19.7) is stripped, no backslash may remain in any literal of either
    # header, so no other folder or file name can be built.
    escape_re = re.compile(r'\\(?:x[0-9A-Fa-f]{2,4}|[rnt\\])')
    for text, name in ((phase7_learn_file, "learning-file"),
                       (phase7_learning, "learning")):
        for literal in re.findall(r'"([^"\n]*\[^"\n]*)"', text):
            if chr(92) in escape_re.sub("", literal):
                raise RuntimeError(
                    f"Phase-7 {name} source builds a path outside Emtt_Learning\\: {literal!r}"
                )
    if re.search(r"\bFileMove\s*\([^)]*FILE_REWRITE", ea):
        raise RuntimeError("the EA must not rewrite a file itself in Phase 7")
    for pattern in (r"\bFileOpen\s*\(", r"\bFileWrite\w*\s*\(",
                    r"\bFileRead\w*\s*\(", r"\bFileClose\s*\(",
                    r"\bFileMove\s*\(", r"\bFileDelete\s*\(",
                    r"\bFolderDelete\s*\(", r"\bFileCopy\s*\("):
        if re.search(pattern, ea):
            raise RuntimeError(
                f"Phase-7 EA reaches the file system directly: {pattern}"
            )
    # No new GlobalVariable: the EA count stays at the Phase 2/6 baseline.
    global_calls = re.findall(r"\bGlobalVariable\w*\s*\(", ea)
    if len(global_calls) != 11:
        raise RuntimeError(
            "Phase-7 EA GlobalVariable use changed (Phase 2/6 baseline is 11 calls)"
        )



    #--- Phase 8 (21.15) -----------------------------------------------
    trade_path = ROOT / "Include" / "Emtt" / "Emtt_Trade.mqh"
    manager_path = ROOT / "Include" / "Emtt" / "Emtt_TradeManager.mqh"
    trade = trade_path.read_text(encoding="utf-8")
    manager = manager_path.read_text(encoding="utf-8")
    phase8_markers = (
        (trade, r"EMTT_TRADE_RISK\s+1\.0", "1.0 percent fixed risk"),
        (trade, r"EMTT_TRADE_BE_ATR\s+1\.0", "breakeven at 1.0 ATR"),
        (trade, r"EMTT_TRADE_PARTIAL_PCT\s+50\.0", "50 percent TP1 partial"),
        (trade, r"EMTT_TRAIL_BASE_M5\s+1\.0", "M5 trailing base"),
        (trade, r"EMTT_TRAIL_BASE_M15\s+1\.5", "M15 trailing base"),
        (trade, r"EMTT_TRAIL_BASE_M30\s+2\.0", "M30 trailing base"),
        (trade, r"EMTT_TRAIL_CHANDELIER\s+2\.5", "2.5 ATR Chandelier"),
        (trade, r"EMTT_TRAIL_FRACTAL_BUFFER\s+0\.5", "0.5 ATR Fractal buffer"),
        (trade, r"EMTT_TRAIL_PHASE_HI\s+0\.50", "ATR/Chandelier phase boundary"),
        (trade, r"EMTT_TRAIL_PHASE_TOP\s+0\.80", "Chandelier/Fractal phase boundary"),
        (trade, r"EMTT_TRADE_SPREAD_MULT\s+2\.0", "2.0 average-spread multiplier"),
        (trade, r"EMTT_TRADE_SPREAD_SAMPLES\s+20", "20-sample spread skip"),
        (trade, r"EMTT_NEWS_WINDOW_MIN\s+30", "30-minute before/after news window"),
        (trade, r"EMTT_NEWS_SIZE_HIGH\s+0\.5", "high-impact half size"),
        (trade, r"EMTT_NEWS_SIZE_MED\s+0\.75", "medium-impact 0.75 size"),
        (trade, r"EMTT_NEWS_TRAIL_MULT\s+1\.5", "high-impact 1.5 trail multiplier"),
        (ea, r"input long InpMagicNumber\s*=\s*20251007", "magic input and default"),
        (ea, r'input group\s+"Auto Trading"', "Auto Trading input group"),
        (ea, r"input bool InpAutoTrading\s*=\s*false", "watch-only default"),
        (ea, r"input ENUM_EMTT_LOT_MODE InpLotMode\s*=\s*EMTT_LOT_AUTO", "Auto lot-size default"),
        (ea, r"input bool InpMarginCheck\s*=\s*false", "margin-check bypass default"),
        (ea, r"input bool InpPlaceStopLoss\s*=\s*false", "initial stop-loss default"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_Trade\.mqh"', "quoted pure-trade include"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_TradeManager\.mqh"', "quoted trade-manager include"),
        (ea, r"SEmttTradeState\s+g_trade;", "exactly one trade manager state"),
        (trade, r"EmttTradeGateFirstFailure\(", "ordered safety gate"),
        (trade, r"EmttTradeResolveLots\(", "Auto/Minimum lot sizing"),
        (trade, r"EmttTradeBuildOrder\(", "market/pending order construction"),
        (trade, r"EmttTradeTrailCalculate\(", "trailing distance and context"),
        (trade, r"EmttTradeReviseTargets\(", "TP1/TP2 revisions"),
        (trade, r"EmttTradeTimeExitClose\(", "profit-only time exit"),
        (manager, r"CalendarValueHistory\(", "MT5 economic calendar"),
        (manager, r"PositionClosePartial\(", "TP1 partial close"),
        (manager, r"EmttTradeManagerObserve\(", "broker adoption/fill/close lifecycle"),
        (manager, r"EmttTradeManagerFillPanel\(", "live block panel wiring"),
        (phase7_learn_file,
         r"trade filled|trade closed|tradeNetPoints", "trade ticket grammar"),
        (phase7_learning, r"ticket\.tradeNetPoints", "real-net learning label"),
        (ea, r'#property version\s+"1\.(?:60|70|80|90)"', "Phase 8 version stamp"),
        (ea, r'#property description "Phase 8: live trading - order, management, record\."',
         "Phase 8 description line"),
    )
    for source, pattern, description in phase8_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-8 rule: {description}")
    if len(re.findall(r"\bSEmttTradeState\s+g_trade\s*;", ea)) != 1:
        raise RuntimeError("Phase 8 must declare exactly one EA trade state instance")
    if not (ea.find("Emtt_Learning.mqh") < ea.find("Emtt_Trade.mqh") <
            ea.find("Emtt_TradeManager.mqh")):
        raise RuntimeError("Phase-8 trade includes must follow learning, pure trade first")
    if not (ea.find("Emtt_LearnFile.mqh") < ea.find("Emtt_Learning.mqh")):
        raise RuntimeError("Phase-8 trade includes must follow both learning headers")

    # The trade-scope guard is the Phase-6 no-order list re-scoped for
    # 21.2: only the broker manager and EA are allowed to contain calls.
    phase8_order_tokens = forbidden_orders + (r"\bOrderCalcMargin\b",)
    allowed_trade_scope = {
        "Experts/Emtt.mq5",
        "Include/Emtt/Emtt_TradeManager.mqh",
    }
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        if rel in allowed_trade_scope:
            continue
        code = strip_comments_and_strings(path.read_text(encoding="utf-8"))
        for pattern in phase8_order_tokens:
            if re.search(pattern, code):
                raise RuntimeError(
                    f"Phase-8 trade-scope violation in {rel}: {pattern}"
                )
    # The pure-decision header remains subject to the full no-order guard.
    pure_code = strip_comments_and_strings(trade)
    for pattern in phase8_order_tokens:
        if re.search(pattern, pure_code):
            raise RuntimeError(f"Phase-8 pure-trade header contains order token: {pattern}")

    for source, name in ((trade, "trade"), (manager, "trade-manager")):
        for pattern in forbidden_smc:
            if re.search(pattern, source):
                raise RuntimeError(
                    f"Phase-8 {name} source contains forbidden chart drawing token: {pattern}"
                )
    for path, name in ((trade_path, "trade"), (manager_path, "trade-manager")):
        raw = path.read_bytes()
        for index, byte in enumerate(raw):
            if byte > 0x7F:
                line = raw.count(b"\n", 0, index) + 1
                raise RuntimeError(
                    f"Phase-8 {name} header is not ASCII-only: byte 0x{byte:02X} at line {line}"
                )

    # 21.15 keeps the Phase-7 file boundary and introduces no extra path,
    # global variable or direct file access in either trade header.
    forbidden_phase8_files = (
        r"\bGlobalVariable\w*\s*\(", r"\bFileOpen\s*\(",
        r"\bFileWrite\w*\s*\(", r"\bFileRead\w*\s*\(",
        r"\bFileClose\s*\(", r"\bFileMove\s*\(",
        r"\bFileDelete\s*\(", r"\bFolderCreate\s*\(",
        r"\bFolderDelete\s*\(", r"\bFileCopy\s*\(",
        r"\bFILE_COMMON\b",
    )
    for source, name in ((trade, "trade"), (manager, "trade-manager")):
        code = strip_comments_and_strings(source)
        for pattern in forbidden_phase8_files:
            # Pending lifecycle follow-up: only the broker-facing manager may
            # persist its isolated execution lease in terminal globals. The
            # learning files and pure trading header remain protected.
            if name == "trade-manager" and "GlobalVariable" in pattern:
                continue
            if re.search(pattern, code):
                raise RuntimeError(
                    f"Phase-8 {name} source breaks the learning-file boundary: {pattern}"
                )

    #--- Phase 9 (23.10): narrowly scoped parameter persistence ---------
    param_file_path = ROOT / "Include" / "Emtt" / "Emtt_ParamFile.mqh"
    param_opt_path = ROOT / "Include" / "Emtt" / "Emtt_ParamOpt.mqh"
    param_file = param_file_path.read_text(encoding="utf-8")
    param_opt = param_opt_path.read_text(encoding="utf-8")
    phase9_markers = (
        (param_file, r'EMTT_POPT_SUFFIX\s+"\.params"', "isolated .params suffix"),
        (param_file, r'EMTT_POPT_VERSION\s+"Emtt_Params v1"', "six-line version"),
        (param_file, r'EMTT_POPT_DIR\s+"Emtt_Learning"', "shared learning folder"),
        (param_file, r"EMTT_POPT_CELLS\s+4", "four independent mood cells"),
        (param_opt, r"EMTT_POPT_MIN_SAMPLES\s+20", "20/20 evidence gate"),
        (param_opt, r"EMTT_POPT_NEAR_BAND\s+10", "10-point near-miss band"),
        (param_opt, r"EMTT_POPT_LOOSE\s+0\.05", "inclusive loosen edge"),
        (param_opt, r"EMTT_POPT_TIGHT\s+0\.20", "inclusive tighten edge"),
        (param_opt, r"candidates\[3\]=\{60,70,75\}", "only approved bar candidates"),
        (param_opt, r"EmttParamOptBeginCandle\(", "next-candle application and freeze"),
        (param_opt, r"EmttParamOptAdvanceNear\(", "private paper near-miss lifecycle"),
        (param_opt, r"EmttParamOptQueueAccepted\(", "live-only, deduplicated accepted evidence"),
        (param_file, r"EmttParamFileLoad\(", "versioned load with cell-local recovery"),
        (param_file, r"EmttParamFileSave\(", "whole-file persistence"),
        (param_file, r"written==\(uint\)StringLen\(text\)", "partial writes rejected before rename"),
        (ea, r"input bool InpParamOptimization\s*=\s*true", "enabled-by-default input"),
        (ea, r"SEmttParamOptState g_paramOpt;", "one parameter-optimization state"),
        (ea, r'Emtt_ParamFile\.mqh', "parameter-file include"),
        (ea, r'Emtt_ParamOpt\.mqh', "pure optimizer include"),
        (ea, r'\bEmttParamOptimizationAttachAndLoad\(', "load before replay"),
        (ea, r'\bEmttParamOptimizationAdvance\(', "closed-candle wiring"),
        (ea, r'\bEmttParamOptimizationSaveOnExit\(', "deinit persistence"),
        (phase6_signal, r"const int learnedBar,", "23.3a learned-bar argument"),
        (phase6_signal, r"state\.moodBar=\(learnedBar>0 \? learnedBar : EmttSignalMoodBar\(mood\)\);",
         "23.3a single gate-line edit"),
        (phase7_learn_file, r'"par atr "', "author-only parameter ticket part"),
        (phase7_learn_file, r'EmttLearnPartTail\(parts\[i\],"par",tail\)', "reader skips optional part"),
        (ea, r"ticket\.parBar=g_signal\.moodBar", "record the actual bar at plan start"),
        (ea, r'#property version\s+"1\.(?:70|80|90)"', "Phase 9 version stamp"),
        (ea, r'#property description "Phase 9: parameter-optimization persistence\."',
         "Phase 9 description line"),
    )
    for source, pattern, description in phase9_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-9 rule: {description}")
    if len(re.findall(r"\bSEmttParamOptState\s+g_paramOpt\s*;", ea)) != 1:
        raise RuntimeError("Phase 9 must declare exactly one EA parameter-optimization state")
    if not re.search(
        r"input long InpMagicNumber[^\n]*\ninput bool InpParamOptimization[^\n]*\n\s*"
        r'input group "Auto Trading"', ea
    ):
        raise RuntimeError("Parameter optimization must sit directly below magic, above Auto Trading")
    if not (ea.find("Emtt_Learning.mqh") < ea.find("Emtt_ParamFile.mqh") <
            ea.find("Emtt_ParamOpt.mqh") < ea.find("Emtt_Trade.mqh")):
        raise RuntimeError("Phase-9 includes must follow learning: file, optimizer, then trade")

    # 23.1: the eleven protected modules are byte-identical. The signal's
    # only permitted changes can be reversed to its Phase-8 delivery hash.
    frozen_phase8 = {
        "Emtt_Dashboard.mqh": panel_digest,
        "Emtt_DynamicParams.mqh": "24bd3519a4dccd6414474e6ff5854f9042a4237e96dd058ac4cccbde368ffdb8",
        "Emtt_Regime.mqh": "d62dcf089a7baf51e7d40e68b8c960ecc1327735e7be630652f39edc8a97c01d",
        "Emtt_Supertrend.mqh": "6b2d6a97abb7f4e683499da73d9012986da40f54dd013102daf83a6e5a115888",
        "Emtt_SMC.mqh": "1691c923927429979c369be2c62e14b89afc834764f36f7fea33da6bc7146324",
        "Emtt_VolumeFlow.mqh": "5f311e6fa62bc67f4235e9316cf9a4f295354487f3f77d3b54d16d571f0e2eb3",
        "Emtt_MTF.mqh": "e12d61226ce59eb29a0a2ed8855e7eb7feeb59a3407f21cfcf9a6528a7665a88",
        "Emtt_TradePlan.mqh": "e52a6005ff2ef2a7e75cef3c847c7ee80504bbf73fd6aa7028b03103fe2ba415",
        "Emtt_Summary.mqh": "ade2b7e66f647c7595ef03d9bbf6640fdd19b2317f357678a474d6a1537e98f1",
        # Emtt_Trade.mqh (00eee02d...) and Emtt_TradeManager.mqh (8cb5dd5e...)
        # were frozen through Phase 9. Phase 10 (25.1 / 25.1a) supersedes
        # both hashes: the trade header must reverse to 00eee02d... below,
        # and the manager carries the Phase 10 feed markers.
    }
    for name, expected in frozen_phase8.items():
        raw = (ROOT / "Include" / "Emtt" / name).read_bytes()
        if name == "Emtt_Dashboard.mqh":
            raw = phase11_reverse(raw.decode("utf-8"), PHASE11_DASHBOARD_EDITS).encode()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError(f"Phase-9 scope violation: protected {name} changed")
    signal_original = phase6_signal.replace("                       const int learnedBar,\n", "", 1)
    signal_original = signal_original.replace(
        "state.moodBar=(learnedBar>0 ? learnedBar : EmttSignalMoodBar(mood));",
        "state.moodBar=EmttSignalMoodBar(mood);", 1
    )
    if hashlib.sha256(signal_original.encode()).hexdigest() != (
        "3ef858d8261338f5d78013ec3c3b9ac8787dd7b1a80d23c5c0d2373ceeb6cb92"
    ):
        raise RuntimeError("Emtt_Signal.mqh changed beyond the argument and gate line of 23.3a")
    learning_original = phase7_learning.replace(
        "// 23.8: the grammar reads past `par`; the model deliberately ignores it.\n", "", 1
    )
    if hashlib.sha256(learning_original.encode()).hexdigest() != (
        "2bd1c3eae2f85d1b9a939423470ba5d816a84428cadf983595b66db9c5e08acd"
    ):
        raise RuntimeError("Phase-9 learning features, weights, labels or model changed")

    # The five guards of 23.10, retaining every Phase 2-8 guard above.
    for path, source, name in (
        (param_file_path, param_file, "parameter-file"),
        (param_opt_path, param_opt, "parameter-optimization"),
    ):
        if not path.read_bytes().isascii():
            raise RuntimeError(f"Phase-9 {name} header is not ASCII-only")
        for pattern in forbidden_smc + phase8_order_tokens:
            if re.search(pattern, strip_comments_and_strings(source)):
                raise RuntimeError(f"Phase-9 {name} contains forbidden drawing/order token: {pattern}")
        for pattern in forbidden_summary_files + (
            r'\bTerminalInfoString\s*\(', r'\bFolderClean\s*\(',
        ):
            if re.search(pattern, strip_comments_and_strings(source)):
                raise RuntimeError(f"Phase-9 {name} contains forbidden file/global token: {pattern}")
    for pattern in forbidden_smc:
        if re.search(pattern, ea):
            raise RuntimeError(f"Phase-9 EA contains forbidden chart drawing token: {pattern}")
    pure_opt_code = strip_comments_and_strings(param_opt)
    if re.search(r"\b(?:File\w+|Folder\w+)\s*\(", pure_opt_code):
        raise RuntimeError("Phase-9 pure optimizer reaches the file system directly")
    if re.search(r"\b(?:iATR|iAMA|iBands|iCustom|CopyRates|CopyBuffer|TimeCurrent|TimeGMT|"
                 r"TimeTradeServer|MathRand|MathSrand|GetTickCount|GetMicrosecondCount)\s*\(",
                 pure_opt_code):
        raise RuntimeError("Phase-9 pure optimizer creates measurements or reads a clock/chart")
    for name, text in (("parameter-file", param_file), ("parameter-optimization", param_opt)):
        for literal in re.findall(r'"([^"\n]*\[^"\n]*)"', text):
            if chr(92) in escape_re.sub("", literal):
                raise RuntimeError(f"Phase-9 {name} builds a path outside Emtt_Learning\\")

    # Exactly three writable siblings, and exactly one .tmp rename in each.
    writers = {
        "Emtt_LearnFile.mqh": (phase7_learn_file, "EMTT_LEARN_EXT", ".learn"),
        "Emtt_Summary.mqh": (summary, "EMTT_SUMMARY_EXT", ".summary"),
        "Emtt_ParamFile.mqh": (param_file, "EMTT_POPT_SUFFIX", ".params"),
    }
    for name, (source, suffix_macro, suffix) in writers.items():
        # Writing headers may open only their own temporary destination,
        # or their own record for reading. A fourth suffix cannot slip in
        # through an extra FileOpen while retaining the approved macro.
        writer_code = strip_comments_and_strings(source)
        for arguments in re.findall(r"\bFileOpen\s*\(([^)]*)\)", writer_code):
            pieces = arguments.split(",")
            if len(pieces) < 2:
                raise RuntimeError(f"Phase-9 file guard: invalid FileOpen in {name}")
            file_arg, flags = pieces[0].strip(), pieces[1].strip()
            own_read = file_arg in ("filePath", "state.filePath") and (
                "FILE_READ" in flags and "FILE_WRITE" not in flags
            )
            own_write = file_arg == "tmpPath" and (
                "FILE_WRITE" in flags and "FILE_READ" not in flags
            )
            if not (own_read or own_write):
                raise RuntimeError(f"Phase-9 file guard: {name} opens a non-record path")
        if not re.search(rf'{suffix_macro}\s+"{re.escape(suffix)}"', source):
            raise RuntimeError(f"Phase-9 file guard: unexpected suffix in {name}")
        if 'state.filePath+".tmp"' not in source:
            raise RuntimeError(f"Phase-9 file guard: {name} must write its own .tmp")
        moves = re.findall(r"\bFileMove\s*\([^;]*\)", source)
        if len(moves) != 1 or "tmpPath,0,state.filePath,FILE_REWRITE" not in moves[0]:
            raise RuntimeError(f"Phase-9 file guard: {name} needs exactly one own-file rename")
        for pattern in forbidden_summary_files + (r"\bFolderClean\s*\(",):
            if re.search(pattern, source):
                raise RuntimeError(f"Phase-9 file guard violation in {name}: {pattern}")
    for path in paths:
        code = strip_comments_and_strings(path.read_text(encoding="utf-8"))
        if path.name not in writers and re.search(r"\b(?:File|Folder)\w+\s*\(", code):
            raise RuntimeError(f"Phase-9 file access outside the three writing headers: {path.name}")
    ea_code = strip_comments_and_strings(ea)
    for api, count in (("iATR", 5), ("iAMA", 6), ("iBands", 1)):
        if len(re.findall(rf"\b{api}\s*\(", ea_code)) != count:
            raise RuntimeError("Phase-9 changed the existing chart-timeframe indicator handles")
    if len(re.findall(r"\bGlobalVariable\w*\s*\(", ea)) != 11:
        raise RuntimeError("Phase-9 GlobalVariable count must remain the Phase-2/6 baseline of 11")
    if re.search(r"\.par[A-Z]\w*", strip_comments_and_strings(phase7_learning + param_opt)):
        raise RuntimeError("Phase-9 ticket evidence is read by the model or decision rule")

    check_phase10(paths, ea, trade, manager)


def phase10_trade_reverse(trade: str) -> str:
    """Undo the single 25.1a edit (argument + one multiplication)."""
    text = trade.replace(
        "                             SEmttTradeTrailResult &result,\n"
        "                             const double divergenceMult=1.0)\n",
        "                             SEmttTradeTrailResult &result)\n", 1)
    return text.replace("result.newsMultiplier*divergenceMult;",
                        "result.newsMultiplier;", 1)


PHASE8_TRADE_SHA256 = "00eee02dc193fd4674483ab8b78d2b2bad9e0c2fdda83706f969f6451dbc2eb4"


def function_body(source: str, signature: str) -> str:
    """Text of one top-level MQL function, from its signature to the next."""
    start = source.find(signature)
    if start < 0:
        return ""
    following = re.search(r"\n(?:void|bool|int|long|double|string|datetime)\s+\w+\(",
                          source[start + len(signature):])
    end = start + len(signature) + following.start() if following else len(source)
    return source[start:end]


def check_phase10(paths: list[Path], ea: str, trade: str, manager: str) -> None:
    """25.13: tick-level CVD divergence for the trailing stop."""
    div_path = ROOT / "Include" / "Emtt" / "Emtt_TickDivergence.mqh"
    div = div_path.read_text(encoding="utf-8")
    phase10_markers = (
        (div, r"EMTT_DIV_TICKS\s+300\b", "300-tick ring buffer"),
        (div, r"EMTT_DIV_MAX_WINDOW_MIN\s+15\b", "15-minute window cap"),
        (div, r"EMTT_DIV_SWING_STRENGTH\s+5\b", "tick swing strength 5"),
        (div, r"EMTT_DIV_DENSITY_MIN\s+60\b", "60-second density window"),
        (div, r"EMTT_DIV_DENSITY_MIN_TICKS\s+10\b", "10 ticks/60 s active threshold"),
        (div, r"EMTT_DIV_DENSITY_RECOVER\s+20\b", "20 ticks/60 s recovery"),
        (div, r"EMTT_DIV_WARMUP_TICKS\s+50\b", "50-tick warmup"),
        (div, r"EMTT_DIV_PRICE_LEAST_ATR\s+0\.10\b", "0.10 entry-ATR minimum leg"),
        (div, r"EMTT_DIV_STRONG_RATIO\s+0\.5\b", "strong CVD ratio 0.5"),
        (div, r"EMTT_DIV_CONFIRM_TICKS\s+3\b", "3-tick confirmation"),
        (div, r"EMTT_DIV_WEAK_MULT\s+0\.8\b", "weak multiplier 0.8"),
        (div, r"EMTT_DIV_STRONG_MULT\s+0\.5\b", "strong multiplier 0.5"),
        (div, r"struct SEmttTickDivergenceState", "pure divergence state"),
        (div, r"long\s+msc\[EMTT_DIV_TICKS\];", "fixed ring allocated with the state"),
        (div, r"int\s+cvdNow;", "rolling tick-CVD sum"),
        (div, r"int\s+cvdAbs;", "rolling absolute-sign sum"),
        (div, r"EmttTickDivSign\(", "25.3 tick sign"),
        (div, r"EmttTickDivDetectSwing\(", "25.5 incremental tick swings"),
        (div, r"EmttTickDivFeed\(", "25.3-25.7 per-tick update"),
        (div, r"EmttTickDivMultiplier\(", "25.8 multiplier"),
        (div, r"EmttTickDivOnStopMoved\(", "25.7 stop-move reset"),
        (div, r"momentum fading, tightening trail\.", "weak STATUS line"),
        (div, r"momentum exhausted, tightening trail\.", "strong STATUS line"),
        (trade, r"SEmttTradeTrailResult &result,\s*const double divergenceMult=1\.0\)",
         "25.9 divergenceMult argument with a 1.0 default"),
        (trade, r"result\.newsMultiplier\*divergenceMult;",
         "25.9 divergence multiplies the final distance after conf/regime/news"),
        (manager, r'#include "Emtt_TickDivergence\.mqh"', "manager sees the divergence state"),
        (manager, r"void EmttTradeManagerFeedTick\(", "per-tick divergence feed"),
        (manager, r"EmttTickDivMultiplier\(div\)", "closed-candle trailing reads the multiplier"),
        (manager, r"smc\.newestLowLevel,smc\.newestHighLevel,trail,divMult\)",
         "live trailing passes the multiplier"),
        (manager, r"EmttTickDivOnStopMoved\(div,", "stop move resets the reading"),
        (manager, r'" x"\+DoubleToString\(divMult,1\)', "trailing journal carries a non-1.0 factor"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_TickDivergence\.mqh"', "quoted divergence include"),
        (ea, r"SEmttTickDivergenceState g_tickDiv;", "one divergence state"),
        (ea, r"EmttTickDivReset\(g_tickDiv\)", "empty buffer at init"),
        (ea, r"g_learning\.file,g_tickDiv\)", "closed-candle step receives the state"),
        (ea, r'#property version\s+"1\.(?:80|90)"', "Phase 10 version stamp"),
        (ea, r'#property description "Phase 10: tick-level CVD divergence detection for the trailing stop\."',
         "Phase 10 description line"),
    )
    for source, pattern, description in phase10_markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-10 rule: {description}")
    if len(re.findall(r"\bSEmttTickDivergenceState\s+g_tickDiv\s*;", ea)) != 1:
        raise RuntimeError("Phase 10 must declare exactly one EA divergence state")
    order = [ea.find(name) for name in (
        "Emtt_ParamFile.mqh", "Emtt_ParamOpt.mqh", "Emtt_TickDivergence.mqh",
        "Emtt_Trade.mqh", "Emtt_TradeManager.mqh")]
    if min(order) < 0 or order != sorted(order):
        raise RuntimeError("Phase-10 includes must be ParamFile, ParamOpt, TickDivergence, Trade, TradeManager")

    # 25.1a: the trade header carries only the argument and the one
    # multiplication; reversing them restores the Phase 8/9 delivery.
    if hashlib.sha256(phase10_trade_reverse(phase11_reverse(trade, PHASE11_TRADE_EDITS))
                      .encode()).hexdigest() != PHASE8_TRADE_SHA256:
        raise RuntimeError("Emtt_Trade.mqh changed beyond the 25.1a divergenceMult edit")
    if len(re.findall(r"\bEmttTradeTrailCalculate\s*\(", manager)) != 1:
        raise RuntimeError("Phase-10 trailing must have exactly one live call site")

    # 25.1: the fourteen untouched headers stay byte-identical.
    frozen_phase9 = {
        "Emtt_DynamicParams.mqh": "24bd3519a4dccd6414474e6ff5854f9042a4237e96dd058ac4cccbde368ffdb8",
        "Emtt_Regime.mqh": "d62dcf089a7baf51e7d40e68b8c960ecc1327735e7be630652f39edc8a97c01d",
        "Emtt_Supertrend.mqh": "6b2d6a97abb7f4e683499da73d9012986da40f54dd013102daf83a6e5a115888",
        "Emtt_SMC.mqh": "1691c923927429979c369be2c62e14b89afc834764f36f7fea33da6bc7146324",
        "Emtt_VolumeFlow.mqh": "5f311e6fa62bc67f4235e9316cf9a4f295354487f3f77d3b54d16d571f0e2eb3",
        "Emtt_MTF.mqh": "e12d61226ce59eb29a0a2ed8855e7eb7feeb59a3407f21cfcf9a6528a7665a88",
        "Emtt_TradePlan.mqh": "e52a6005ff2ef2a7e75cef3c847c7ee80504bbf73fd6aa7028b03103fe2ba415",
        "Emtt_Summary.mqh": "ade2b7e66f647c7595ef03d9bbf6640fdd19b2317f357678a474d6a1537e98f1",
        "Emtt_LearnFile.mqh": "08ec0b308a3b1ba321e652ea657739eb884c7b41b42d72d6132fdd6e36ea2f5f",
        "Emtt_Learning.mqh": "936289a3709cbb61ca961567f53c36b632efded9e0672fd9d9e3e4882373b773",
        "Emtt_ParamFile.mqh": "051586fe54e02fdfe0114c9c29a7a9c073840377480cce2b561f910f6a1f153a",
        "Emtt_ParamOpt.mqh": "854845beb8a5d26a4c153c740d6b6eb859bcc564c04f7247b8d6f03b31233f22",
        "Emtt_Signal.mqh": "434b27bda44a7985a4126bec1cc0a133c721cc249d8c1e76d61f9d6b1e1582fe",
        "Emtt_Dashboard.mqh": "22392551ed94bb3c38badea5b74e589c5d90f6ca75f41d8cb4ced541b4077b70",
    }
    phase11_reversals = {"Emtt_Signal.mqh": PHASE11_SIGNAL_EDITS,
                         "Emtt_Dashboard.mqh": PHASE11_DASHBOARD_EDITS}
    for name, expected in frozen_phase9.items():
        raw = (ROOT / "Include" / "Emtt" / name).read_bytes()
        if name in phase11_reversals:  # Phase 11 (28.1) reversible edits
            raw = phase11_reverse(raw.decode("utf-8"), phase11_reversals[name]).encode()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError(f"Phase-10 scope violation: protected {name} changed")

    # 25.2 / 25.13: no new input, handle, file or GlobalVariable.
    inputs = re.findall(r"^input\s+(?!group\b)(?![^\n]*InpAutoTradeAbove)(?![^\n]*InpPendingValidityBars)", ea, re.MULTILINE)
    if len(inputs) != 6:
        raise RuntimeError("Phase 10 adds no input: six inputs total")
    if re.search(r"^input[^\n]*(?:[Dd]iverg|[Tt]ick)", ea, re.MULTILINE):
        raise RuntimeError("Phase 10 must not add a divergence input")

    # The per-tick path: OnTick refreshes the panel, then feeds the tick.
    tick_body = function_body(ea, "void OnTick()")
    if not re.search(r"UpdatePanel\(\);\s*EmttTradeManagerFeedTick\(g_trade,g_tickDiv\);", tick_body):
        raise RuntimeError("Phase-10 feed must follow UpdatePanel() in OnTick")
    per_tick_forbidden = (r"\bCopyRates\s*\(", r"\bCopyBuffer\s*\(", r"\bCopyTicks\w*\s*\(",
                          r"\bi(?:ATR|AMA|Bands|Custom|MA|Time|Close|High|Low)\s*\(",
                          r"\bOrderSend\b", r"\bPositionClose\w*\b", r"\bPositionModify\b")
    feed_body = function_body(manager, "void EmttTradeManagerFeedTick(")
    if "SymbolInfoTick(" not in feed_body or "EmttTickDivFeed(" not in feed_body:
        raise RuntimeError("Phase-10 feed must read SymbolInfoTick and update the state")
    for body, name in ((strip_comments_and_strings(tick_body), "OnTick"),
                       (strip_comments_and_strings(feed_body), "manager feed")):
        for pattern in per_tick_forbidden:
            if re.search(pattern, body):
                raise RuntimeError(f"Phase-10 per-tick path ({name}) contains {pattern}")

    # Guards: drawing, trade scope, ASCII, file; the header is pure logic.
    if not div_path.read_bytes().isascii():
        raise RuntimeError("Phase-10 divergence header is not ASCII-only")
    div_code = strip_comments_and_strings(div)
    forbidden_div = (
        r"\bObjectCreate\s*\(", r"\bOBJ_\w+", r"\bChart\w+\s*\(",
        r"\bOrder\w*\s*\(", r"\bPosition\w*\s*\(", r"\bCTrade\b", r"\bHistory\w+\s*\(",
        r"\b(?:File|Folder)\w+\s*\(", r"\bGlobalVariable\w*\s*\(",
        r"\bCopy\w+\s*\(", r"\bSymbolInfo\w*\s*\(", r"\bi(?:ATR|AMA|Bands|Custom|MA)\s*\(",
        r"\b(?:TimeCurrent|TimeGMT|TimeLocal|TimeTradeServer|GetTickCount\w*|"
        r"GetMicrosecondCount|MathRand|MathSrand)\s*\(",
        r"\bArrayResize\s*\(", r"#include",
    )
    for pattern in forbidden_div:
        if re.search(pattern, div_code):
            raise RuntimeError(f"Phase-10 divergence header is not pure logic: {pattern}")
    for pattern in (r"\bObjectCreate\s*\(", r"\bOBJ_(?:TREND|RECTANGLE|HLINE|ARROW|TEXT|FIBO\w*)\b"):
        if re.search(pattern, ea):
            raise RuntimeError(f"Phase-10 EA contains forbidden chart drawing token: {pattern}")
    for path in paths:
        code = strip_comments_and_strings(path.read_text(encoding="utf-8"))
        if path.name != "Emtt_TradeManager.mqh" and re.search(r"\bCopyTicks\w*\s*\(", code):
            raise RuntimeError(f"Phase-10 CopyTicks outside the trade manager: {path.name}")

    check_phase11(paths, ea, trade, manager)


def check_phase11(paths: list[Path], ea: str, trade: str, manager: str) -> None:
    """28.8: graded confidence tiers and continuous signal display."""
    tier_path = ROOT / "Include" / "Emtt" / "Emtt_Tier.mqh"
    tier = tier_path.read_text(encoding="utf-8")
    signal = (ROOT / "Include" / "Emtt" / "Emtt_Signal.mqh").read_text(encoding="utf-8")
    dashboard = (ROOT / "Include" / "Emtt" / "Emtt_Dashboard.mqh").read_text(encoding="utf-8")
    markers = (
        (tier, r"EMTT_TIER_DISPLAY_MIN\s+35\b", "35% display floor"),
        (tier, r"EMTT_TIER_LOW_MAX\s+45\b", "Low tier 35-45"),
        (tier, r"EMTT_TIER_NORMAL_MAX\s+55\b", "Normal tier 46-55"),
        (tier, r"EMTT_TIER_CONFIDENT_MAX\s+70\b", "Confident tier 56-70, High 71+"),
        (tier, r"EMTT_TIER_AUTO_MIN\s+35\b", "auto-trade minimum 35"),
        (tier, r"EMTT_TIER_AUTO_MAX\s+100\b", "auto-trade maximum 100"),
        (tier, r"EMTT_TIER_AUTO_DEFAULT\s+56\b", "auto-trade default 56"),
        (tier, r"EMTT_TIER_SIZE_LOW\s+0\.7\b", "Low 0.7 lots multiplier"),
        (tier, r"EMTT_TIER_SIZE_NORMAL\s+1\.0\b", "Normal 1.0 lots multiplier"),
        (tier, r"EMTT_TIER_SIZE_CONFIDENT\s+1\.2\b", "Confident 1.2 lots multiplier"),
        (tier, r"EMTT_TIER_SIZE_HIGH\s+1\.5\b", "High 1.5 lots multiplier"),
        (tier, r'"Very low"', "Very low label"),
        (tier, r'"Low confidence"', "Low label"),
        (tier, r'"Normal"', "Normal label"),
        (tier, r'"Confident"', "Confident label"),
        (tier, r'"High confidence"', "High label"),
        (tier, r'"Confidence: --%"', "no-number Row 3"),
        (tier, r'"Watching \\x2014 confidence "', "below-35 Watching line"),
        (tier, r'"Signal active \\x2014 "', "below-threshold Signal active line"),
        (tier, r'", watching \(auto-trade threshold "', "threshold wording"),
        (signal, r'#include "Emtt_Tier\.mqh"', "signal sees the tiers"),
        (signal, r"const int barLevel=EMTT_TIER_DISPLAY_MIN;", "35% entering level"),
        (signal, r"const int keepLevel=EMTT_TIER_DISPLAY_MIN;", "35% keeping level"),
        (signal, r"EmttTierWatchingLine\(state\.confidence\)", "below-35 STATUS line"),
        (trade, r'#include "Emtt_Tier\.mqh"', "trade sees the tiers"),
        (trade, r"EMTT_TRADE_GATE_BELOW_THRESHOLD", "threshold gate"),
        (trade, r"return EmttTierSizeMultiplier\(confidence\);", "tier lot multiplier"),
        (manager, r"gate\.autoTradeAbove=runtime\.autoTradeAbove;", "threshold reaches the gate"),
        (manager, r"gate\.confidence=runtime\.confidence;", "displayed number reaches the gate"),
        (dashboard, r"EMTT_CLR_BUY_LOW\s+C'156,204,176'", "Low BUY shade"),
        (dashboard, r"EMTT_CLR_SELL_LOW\s+C'218,156,156'", "Low SELL shade"),
        (dashboard, r"EMTT_CLR_BUY_NORMAL\s+C'133,205,163'", "Normal BUY shade"),
        (dashboard, r"EMTT_CLR_SELL_NORMAL\s+C'226,133,133'", "Normal SELL shade"),
        (dashboard, r'EMTT_FONT_BOLD\s+"Segoe UI Bold"', "High-tier bold face"),
        (ea, r'#include "\.\./Include/Emtt/Emtt_Tier\.mqh"', "quoted tier include"),
        (ea, r"input int  InpAutoTradeAbove=56;\s*// Auto-trade above \(%\)", "threshold input"),
        (ea, r"g_autoTradeAbove=EmttTierAutoTradeAbove\(InpAutoTradeAbove\);", "threshold clamp"),
        (ea, r"runtime\.autoTradeAbove=g_autoTradeAbove;", "threshold reaches the manager"),
        (ea, r"EmttTierConfidenceRow\(", "tiered Row 3"),
        (ea, r"EmttTierSignalStyle\(", "tiered Row 2 style"),
        (ea, r'#property version\s+"1\.90"', "Phase 11 version stamp"),
        (ea, r'#property description "Phase 11: graded confidence tiers and continuous signal display\."',
         "Phase 11 description line"),
    )
    for source, pattern, description in markers:
        if not re.search(pattern, source):
            raise RuntimeError(f"missing Phase-11 rule: {description}")
    if not re.search(r'input bool InpAutoTrading=false;[^\n]*\ninput int  InpAutoTradeAbove=56;', ea):
        raise RuntimeError("Auto-trade above (%) must sit directly below Auto Trading ON/OFF")
    order = [ea.find(name) for name in ("Emtt_TradePlan.mqh", "Emtt_Tier.mqh", "Emtt_Signal.mqh")]
    if min(order) < 0 or order != sorted(order):
        raise RuntimeError("Phase-11 tier include must sit between TradePlan and Signal")
    inputs = re.findall(r"^input\s+(?!group\b)", ea, re.MULTILINE)
    if len(inputs) != 8:
        raise RuntimeError("Phase 11 plus pending validity: eight inputs total")
    if not re.search(r"^input int InpPendingValidityBars=6;", ea, re.MULTILINE):
        raise RuntimeError("Pending validity default must be six bars")
    pending_path = ROOT / "Include" / "Emtt" / "Emtt_Pending.mqh"
    if "Emtt_Pending.mqh" not in {path.name for path in paths}:
        raise RuntimeError("Pending policy must be in the include graph")
    pending_code = strip_comments_and_strings(pending_path.read_text())
    if re.search(r"\b(?:Order|Position|File|Folder|GlobalVariable|SymbolInfo|Copy|TimeCurrent|TimeTradeServer)\w*\s*\(", pending_code):
        raise RuntimeError("Pending policy must remain pure logic")
    if '"Emtt_P_%I64d_%I64d"' not in manager or "ACCOUNT_LOGIN" not in manager or "ACCOUNT_SERVER" not in manager:
        raise RuntimeError("Pending lease must be namespaced by broker/account")
    if "Emtt_Tier.mqh" not in {path.name for path in paths}:
        raise RuntimeError("Emtt_Tier.mqh is not in the EA include graph")
    if not tier_path.read_bytes().isascii():
        raise RuntimeError("Phase-11 tier header is not ASCII-only")
    tier_code = strip_comments_and_strings(tier)
    for pattern in (
        r"\bObject\w*\s*\(", r"\bOBJ_\w+", r"\bChart\w+\s*\(", r"\bOrder\w*\s*\(",
        r"\bPosition\w*\s*\(", r"\bCTrade\b", r"\bHistory\w+\s*\(",
        r"\b(?:File|Folder)\w+\s*\(", r"\bGlobalVariable\w*\s*\(", r"\bCopy\w+\s*\(",
        r"\bSymbolInfo\w*\s*\(", r"\bi(?:ATR|AMA|Bands|Custom|MA)\s*\(", r"\bPrint\w*\s*\(",
        r"\b(?:TimeCurrent|TimeGMT|TimeLocal|TimeTradeServer|GetTickCount\w*)\s*\(",
        r"#include",
    ):
        if re.search(pattern, tier_code):
            raise RuntimeError(f"Phase-11 tier header is not pure logic: {pattern}")
    # 28.1: Phase 9's files and decision rule are untouched by the tiers.
    for path in paths:
        if path.name in ("Emtt_ParamFile.mqh", "Emtt_ParamOpt.mqh", "Emtt_Learning.mqh",
                         "Emtt_LearnFile.mqh") and "EmttTier" in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"Phase-11 tiers leaked into {path.name}")


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
    check_mqlrates_volume(paths)
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
