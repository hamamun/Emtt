"""Portable tests for Emtt Phase 11 (Emtt.md 28): graded confidence tiers.

The tier boundaries and labels, Row 3 in every state, the Row 2 colour /
size / weight per tier, Rows 4-8 from 35%, the 35% enter / keep gate and its
Watching lines, the "Auto-trade above (%)" clamp and gate, the tier lot
multipliers, Row 10 precedence of the below-threshold line, and a final group
that ties the reference to the MQL sources and the smoke contract.
"""
import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import phase8_reference as p8
import phase11_reference as p11
from tools import mql5_compile_smoke as smoke

ROOT = Path(__file__).resolve().parents[1]
INC = ROOT / "Include" / "Emtt"
TIER = INC / "Emtt_Tier.mqh"
EA = ROOT / "Experts" / "Emtt.mq5"
DASH = p11.DASH


class TierBoundaryTests(unittest.TestCase):
    def test_every_whole_number_maps_to_exactly_one_tier(self):
        expected = {}
        for n in range(0, 35):
            expected[n] = p11.TIER_VERY_LOW
        for n in range(35, 46):
            expected[n] = p11.TIER_LOW
        for n in range(46, 56):
            expected[n] = p11.TIER_NORMAL
        for n in range(56, 71):
            expected[n] = p11.TIER_CONFIDENT
        for n in range(71, 101):
            expected[n] = p11.TIER_HIGH
        for n, tier in expected.items():
            with self.subTest(n=n):
                self.assertEqual(p11.tier_of(n), tier)
        self.assertEqual(p11.tier_of(-1), p11.TIER_NONE)

    def test_edges_of_each_band(self):
        for n, label in ((34, "Very low"), (35, "Low confidence"), (45, "Low confidence"),
                         (46, "Normal"), (55, "Normal"), (56, "Confident"),
                         (70, "Confident"), (71, "High confidence"), (100, "High confidence")):
            with self.subTest(n=n):
                self.assertEqual(p11.tier_label(p11.tier_of(n)), label)

    def test_direction_shows_from_35(self):
        self.assertFalse(p11.shows_direction(34))
        self.assertTrue(p11.shows_direction(35))


class Row3Tests(unittest.TestCase):
    def test_real_number_always_shows_with_its_label(self):
        self.assertEqual(p11.confidence_row(28), f"Confidence: 28% {DASH} Very low")
        self.assertEqual(p11.confidence_row(0), f"Confidence: 0% {DASH} Very low")
        self.assertEqual(p11.confidence_row(41), f"Confidence: 41% {DASH} Low confidence")
        self.assertEqual(p11.confidence_row(50), f"Confidence: 50% {DASH} Normal")
        self.assertEqual(p11.confidence_row(63), f"Confidence: 63% {DASH} Confident")
        self.assertEqual(p11.confidence_row(82), f"Confidence: 82% {DASH} High confidence")

    def test_dash_percent_only_without_a_number(self):
        self.assertEqual(p11.confidence_row(-1), "Confidence: --%")
        state = p11.SignalState(confidence=28)
        for kwargs in ({"compatible": False}, {"market_open": False},
                       {"history_ready": False}, {"views_ready": False}):
            with self.subTest(**kwargs):
                self.assertEqual(p11.fill_panel(state, **kwargs).confidence, "Confidence: --%")


class SignalGateTests(unittest.TestCase):
    def test_below_35_is_wait_with_the_real_number(self):
        state = p11.signal_step(p11.SignalState(), 28, 1)
        self.assertEqual(state.signal, 0)
        self.assertEqual(state.wait_reason, p11.WAIT_BELOW_BAR)
        panel = p11.fill_panel(state)
        self.assertEqual(panel.signal, "SIGNAL: \u25A0 WAIT")
        self.assertEqual(panel.signal_clr, p11.CLR_TEXT)
        self.assertEqual(panel.signal_size, p11.FSIZE)
        self.assertEqual(panel.confidence, f"Confidence: 28% {DASH} Very low")
        self.assertFalse(panel.levels)
        self.assertEqual(p11.wait_status(state),
                         f"Watching {DASH} confidence 28% (Very low), no trade.")

    def test_35_and_up_shows_direction_and_levels(self):
        for n in (35, 45, 46, 55, 56, 70, 71, 95):
            with self.subTest(n=n):
                state = p11.signal_step(p11.SignalState(), n, -1)
                self.assertEqual(state.signal, -1)
                panel = p11.fill_panel(state)
                self.assertEqual(panel.signal, "SIGNAL: \u25BC SELL")
                self.assertTrue(panel.levels)
                self.assertEqual(panel.signal_size, p11.FSIZE_SIG)

    def test_keep_level_is_also_35(self):
        state = p11.signal_step(p11.SignalState(), 40, 1)
        state = p11.signal_step(state, 35, 1)
        self.assertEqual(state.signal, 1)
        state = p11.signal_step(state, 34, 1)
        self.assertEqual(state.signal, 0)
        self.assertEqual(state.wait_reason, p11.WAIT_BELOW_KEEP)
        self.assertEqual(p11.wait_bare(state), "below the 35% level that keeps a BUY (Very low)")
        self.assertEqual(p11.wait_status(state),
                         f"Watching {DASH} confidence 34% (Very low), no trade.")

    def test_plan_failure_keeps_its_existing_wait_reason(self):
        state = p11.signal_step(p11.SignalState(), 52, 1, plan_builds=False)
        self.assertEqual(state.signal, 0)
        self.assertEqual(state.wait_reason, p11.WAIT_PLAN_FAIL)
        self.assertEqual(p11.fill_panel(state).confidence, f"Confidence: 52% {DASH} Normal")

    def test_wait_bare_below_bar_wording(self):
        state = p11.signal_step(p11.SignalState(), 12, 0)
        self.assertEqual(p11.wait_bare(state), "below the 35% display level (Very low)")


class SignalStyleTests(unittest.TestCase):
    def test_colour_size_and_weight_per_tier(self):
        cases = (
            (40, 1, p11.CLR_BUY_LOW, False), (40, -1, p11.CLR_SELL_LOW, False),
            (50, 1, p11.CLR_BUY_NORMAL, False), (50, -1, p11.CLR_SELL_NORMAL, False),
            (60, 1, p11.CLR_BUY, False), (60, -1, p11.CLR_SELL, False),
            (75, 1, p11.CLR_BUY, True), (75, -1, p11.CLR_SELL, True),
        )
        for n, side, clr, bold in cases:
            with self.subTest(n=n, side=side):
                self.assertEqual(p11.signal_style(side, n), (clr, p11.FSIZE_SIG, bold))

    def test_shades_sit_between_grey_and_full_colour(self):
        for low, normal, full in ((p11.CLR_BUY_LOW, p11.CLR_BUY_NORMAL, p11.CLR_BUY),
                                  (p11.CLR_SELL_LOW, p11.CLR_SELL_NORMAL, p11.CLR_SELL)):
            for i in range(3):
                lo, hi = sorted((p11.CLR_TEXT[i], full[i]))
                self.assertTrue(lo <= low[i] <= hi and lo <= normal[i] <= hi)
                # Normal is closer to the full colour than Low is.
                self.assertLessEqual(abs(normal[i] - full[i]), abs(low[i] - full[i]))


class ThresholdTests(unittest.TestCase):
    def test_clamp_to_35_100(self):
        for value, clamped in ((0, 35), (34, 35), (35, 35), (56, 56), (100, 100), (150, 100), (-5, 35)):
            with self.subTest(value=value):
                self.assertEqual(p11.auto_trade_above(value), clamped)

    def test_allowed_at_and_above_threshold_only(self):
        self.assertFalse(p11.auto_trade_allowed(55, 56))
        self.assertTrue(p11.auto_trade_allowed(56, 56))
        self.assertTrue(p11.auto_trade_allowed(35, 35))
        self.assertFalse(p11.auto_trade_allowed(34, 35))
        self.assertFalse(p11.auto_trade_allowed(-1, 35))

    def test_gate_order_auto_off_then_threshold_then_existing_gates(self):
        self.assertEqual(p11.gate_first_failure(p8.GateInput(auto_trading=False), 20, 56),
                         p8.GATE_AUTO_OFF)
        self.assertEqual(p11.gate_first_failure(p8.GateInput(market_open=False), 50, 56),
                         p11.GATE_BELOW_THRESHOLD)
        self.assertEqual(p11.gate_first_failure(p8.GateInput(market_open=False), 60, 56),
                         p8.GATE_MARKET_CLOSED)
        self.assertEqual(p11.gate_first_failure(p8.GateInput(spread_allowed=False), 60, 56),
                         p8.GATE_SPREAD)
        self.assertEqual(p11.gate_first_failure(p8.GateInput(), 56, 56), p8.GATE_OK)

    def test_below_threshold_status_line(self):
        self.assertEqual(
            p11.gate_status(p11.GATE_BELOW_THRESHOLD, 0, 41, 1, 56),
            f"Signal active {DASH} Low confidence BUY, watching (auto-trade threshold 56%).")
        self.assertEqual(
            p11.gate_status(p11.GATE_BELOW_THRESHOLD, 0, 50, -1, 60),
            f"Signal active {DASH} Normal SELL, watching (auto-trade threshold 60%).")
        self.assertEqual(p11.gate_status(p8.GATE_SPREAD, 31), f"No trade {DASH} spread too wide (31 pts)")


class SizeTests(unittest.TestCase):
    def test_tier_multipliers(self):
        for n, mult in ((35, 0.7), (45, 0.7), (46, 1.0), (55, 1.0), (56, 1.2),
                        (70, 1.2), (71, 1.5), (100, 1.5)):
            with self.subTest(n=n):
                self.assertEqual(p11.size_multiplier(n), mult)

    def test_risk_lots_scale_with_the_tier(self):
        base = p8.risk_lots(10000, 1.1, 1.099, 0.00001, 1.0, 70)
        for n, mult in ((40, 0.7), (50, 1.0), (60, 1.2), (80, 1.5)):
            with self.subTest(n=n):
                self.assertAlmostEqual(p11.risk_lots(10000, 1.1, 1.099, 0.00001, 1.0, n),
                                       base * mult)


class Row10Tests(unittest.TestCase):
    def test_below_threshold_line_overrides_and_clears_when_plan_ends(self):
        view = p11.TradeView()
        state = p11.signal_step(p11.SignalState(), 41, 1)
        failure = p11.manager_step(view, state, 56)
        self.assertEqual(failure, p11.GATE_BELOW_THRESHOLD)
        self.assertEqual(p11.row10(view, state, "Plan BUY"),
                         f"Signal active {DASH} Low confidence BUY, watching (auto-trade threshold 56%).")
        state = p11.signal_step(state, 20, 1)
        p11.manager_step(view, state, 56)
        self.assertEqual(view.gate_status, "")
        self.assertEqual(p11.row10(view, state),
                         f"Watching {DASH} confidence 20% (Very low), no trade.")

    def test_at_threshold_the_gate_passes(self):
        view = p11.TradeView()
        state = p11.signal_step(p11.SignalState(), 56, -1)
        self.assertEqual(p11.manager_step(view, state, 56), p8.GATE_OK)

    def test_a_live_trade_keeps_its_line(self):
        view = p11.TradeView(gate_status="Order rejected", position_open=True)
        state = p11.signal_step(p11.SignalState(), 10, 0)
        p11.manager_step(view, state, 56)
        self.assertEqual(view.gate_status, "Order rejected")


def mql_int(source: str, name: str) -> str:
    match = re.search(rf"#define\s+{name}\s+([0-9.]+)", source)
    return match.group(1) if match else ""


class MqlMirrorTests(unittest.TestCase):
    def setUp(self):
        self.tier = TIER.read_text(encoding="utf-8")
        self.ea = EA.read_text(encoding="utf-8")

    def test_header_constants_match_the_reference(self):
        for name, value in (("EMTT_TIER_DISPLAY_MIN", p11.DISPLAY_MIN),
                            ("EMTT_TIER_LOW_MAX", p11.LOW_MAX),
                            ("EMTT_TIER_NORMAL_MAX", p11.NORMAL_MAX),
                            ("EMTT_TIER_CONFIDENT_MAX", p11.CONFIDENT_MAX),
                            ("EMTT_TIER_AUTO_MIN", p11.AUTO_MIN),
                            ("EMTT_TIER_AUTO_MAX", p11.AUTO_MAX),
                            ("EMTT_TIER_AUTO_DEFAULT", p11.AUTO_DEFAULT),
                            ("EMTT_TIER_SIZE_LOW", p11.SIZE_LOW),
                            ("EMTT_TIER_SIZE_NORMAL", p11.SIZE_NORMAL),
                            ("EMTT_TIER_SIZE_CONFIDENT", p11.SIZE_CONFIDENT),
                            ("EMTT_TIER_SIZE_HIGH", p11.SIZE_HIGH)):
            with self.subTest(name=name):
                self.assertEqual(float(mql_int(self.tier, name)), float(value))

    def test_labels_and_wording_match(self):
        for label in p11.LABELS.values():
            self.assertIn(f'"{label}"', self.tier)
        self.assertIn('"Confidence: --%"', self.tier)
        self.assertIn('"Watching \\x2014 confidence "', self.tier)
        self.assertIn('"), no trade."', self.tier)
        self.assertIn('", watching (auto-trade threshold "', self.tier)

    def test_palette_matches(self):
        dash = (INC / "Emtt_Dashboard.mqh").read_text(encoding="utf-8")
        for name, rgb in (("EMTT_CLR_BUY_LOW", p11.CLR_BUY_LOW),
                          ("EMTT_CLR_SELL_LOW", p11.CLR_SELL_LOW),
                          ("EMTT_CLR_BUY_NORMAL", p11.CLR_BUY_NORMAL),
                          ("EMTT_CLR_SELL_NORMAL", p11.CLR_SELL_NORMAL),
                          ("EMTT_CLR_BUY", p11.CLR_BUY), ("EMTT_CLR_SELL", p11.CLR_SELL)):
            with self.subTest(name=name):
                self.assertRegex(dash, rf"#define {name}\s+C'{rgb[0]},{rgb[1]},{rgb[2]}'")

    def test_threshold_position_and_pending_followup_input_count(self):
        self.assertRegex(self.ea, r'input group "Auto Trading"\ninput bool InpAutoTrading=false;'
                                  r'[^\n]*\ninput int  InpAutoTradeAbove=56;\s*// Auto-trade above \(%\)')
        self.assertEqual(len(re.findall(r"^input\s+(?!group\b)", self.ea, re.MULTILINE)), 8)
        self.assertRegex(self.ea, r'#property version\s+"1\.90"')

    def test_header_is_ascii_and_pure(self):
        raw = TIER.read_bytes()
        self.assertTrue(raw.isascii())
        code = smoke.strip_comments_and_strings(raw.decode())
        for token in ("OrderSend", "ObjectCreate", "FileOpen", "CopyRates", "CopyBuffer",
                      "SymbolInfo", "TimeCurrent", "Print", "#include"):
            self.assertNotIn(token, code)

    def test_edits_reverse_to_the_frozen_hashes(self):
        cases = (
            ("Emtt_Signal.mqh", smoke.PHASE11_SIGNAL_EDITS,
             "434b27bda44a7985a4126bec1cc0a133c721cc249d8c1e76d61f9d6b1e1582fe"),
            ("Emtt_Dashboard.mqh", smoke.PHASE11_DASHBOARD_EDITS,
             "22392551ed94bb3c38badea5b74e589c5d90f6ca75f41d8cb4ced541b4077b70"),
        )
        for name, edits, digest in cases:
            with self.subTest(name=name):
                text = (INC / name).read_text(encoding="utf-8")
                for _, new in edits:
                    self.assertEqual(text.count(new), 1, new[:60])
                self.assertEqual(hashlib.sha256(smoke.phase11_reverse(text, edits).encode()).hexdigest(),
                                 digest)
        trade = (INC / "Emtt_Trade.mqh").read_text(encoding="utf-8")
        original = smoke.phase10_trade_reverse(smoke.phase11_reverse(trade, smoke.PHASE11_TRADE_EDITS))
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), smoke.PHASE8_TRADE_SHA256)

    def test_contract_includes_phase11_and_rejects_violations(self):
        paths = smoke.resolve_include_graph(smoke.ENTRY)
        self.assertIn("Emtt_Tier.mqh", {p.name for p in paths})
        smoke.check_contract(paths)
        appended = (
            ("Include/Emtt/Emtt_Tier.mqh", "\nvoid Bad(){ OrderSend(); }\n"),
            ("Include/Emtt/Emtt_Tier.mqh", "\nvoid Bad(){ ObjectCreate(); }\n"),
            ("Include/Emtt/Emtt_Tier.mqh", "\nvoid Bad(){ FileOpen(); }\n"),
            ("Include/Emtt/Emtt_Tier.mqh", "\n// non-ASCII: \u2014\n"),
            ("Include/Emtt/Emtt_Signal.mqh", "\n// out-of-scope change\n"),
            ("Include/Emtt/Emtt_Dashboard.mqh", "\n// out-of-scope change\n"),
            ("Include/Emtt/Emtt_Trade.mqh", "\n// out-of-scope change\n"),
            ("Include/Emtt/Emtt_ParamOpt.mqh", "\n// out-of-scope change\n"),
            ("Experts/Emtt.mq5", "\ninput int InpExtra=1;\n"),
        )
        replaced = (
            ("Include/Emtt/Emtt_Tier.mqh", "EMTT_TIER_DISPLAY_MIN     35", "EMTT_TIER_DISPLAY_MIN     40"),
            ("Include/Emtt/Emtt_Tier.mqh", "EMTT_TIER_SIZE_HIGH       1.5", "EMTT_TIER_SIZE_HIGH       2.0"),
            ("Include/Emtt/Emtt_Tier.mqh", "EMTT_TIER_AUTO_DEFAULT    56", "EMTT_TIER_AUTO_DEFAULT    60"),
            ("Include/Emtt/Emtt_Dashboard.mqh", "C'156,204,176'", "C'150,204,176'"),
            ("Include/Emtt/Emtt_Signal.mqh", "const int keepLevel=EMTT_TIER_DISPLAY_MIN;",
             "const int keepLevel=EMTT_TIER_DISPLAY_MIN-5;"),
            ("Experts/Emtt.mq5", "input int  InpAutoTradeAbove=56;", "input int  InpAutoTradeAbove=60;"),
            ("Experts/Emtt.mq5",
             "input bool InpAutoTrading=false;      // Auto Trading ON/OFF\ninput int  InpAutoTradeAbove=56;      // Auto-trade above (%)\n",
             "input int  InpAutoTradeAbove=56;      // Auto-trade above (%)\ninput bool InpAutoTrading=false;      // Auto Trading ON/OFF\n"),
            ("Include/Emtt/Emtt_TradeManager.mqh", "   gate.autoTradeAbove=runtime.autoTradeAbove;\n", ""),
        )
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            shutil.copytree(ROOT / "Include", work / "Include")
            shutil.copytree(ROOT / "Experts", work / "Experts")
            with mock.patch.object(smoke, "ROOT", work), \
                    mock.patch.object(smoke, "ENTRY", work / "Experts/Emtt.mq5"):
                smoke.check_contract(smoke.resolve_include_graph(smoke.ENTRY))
                for name, extra in appended:
                    with self.subTest(name=name, extra=extra):
                        path = work / name
                        saved = path.read_text()
                        path.write_text(saved + extra)
                        try:
                            with self.assertRaises(RuntimeError):
                                smoke.check_contract(smoke.resolve_include_graph(smoke.ENTRY))
                        finally:
                            path.write_text(saved)
                for name, old, new in replaced:
                    with self.subTest(name=name, old=old):
                        path = work / name
                        saved = path.read_text()
                        self.assertIn(old, saved)
                        path.write_text(saved.replace(old, new, 1))
                        try:
                            with self.assertRaises(RuntimeError):
                                smoke.check_contract(smoke.resolve_include_graph(smoke.ENTRY))
                        finally:
                            path.write_text(saved)


if __name__ == "__main__":
    unittest.main()
