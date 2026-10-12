"""Source-contract regressions for asynchronous closed-bar startup.

These checks complement the portable phase models; live buffer readiness and
chart reinitialization still require the MT5 acceptance checks in the notes.
"""
from pathlib import Path
import unittest

EA = (Path(__file__).resolve().parents[1] / "Experts/Emtt.mq5").read_text()


class StartupReadinessTests(unittest.TestCase):
    def test_init_and_chart_change_reset_foundation(self):
        init = EA.split("int OnInit()", 1)[1].split("void OnDeinit", 1)[0]
        change = EA.split("void EmttResetMarketState()", 1)[1].split(
            "bool EmttAdoptChartContext", 1)[0]
        for source in (init, change):
            self.assertIn("EmttResetFoundationSnapshot();", source)
        reset = EA.split("void EmttResetFoundationSnapshot()", 1)[1].split(
            "void EmttResetMarketState", 1)[0]
        for field, value in (("g_snapshotReady", "false"),
                             ("g_lastClosedBarTime", "0"),
                             ("g_evaluatedBarSequence", "0")):
            self.assertIn(f"{field}={value};", reset)
        self.assertNotIn("EmttConsumeSignalEvents", reset)

    def test_replay_checks_inputs_before_persistence_and_events(self):
        replay = EA.split("bool EmttReplayClosedHistory()", 1)[1].split(
            "bool EmttCopyOne", 1)[0]
        guard = replay.index("if(!EmttSignalViewsReady")
        retry = replay.index("g_snapshotReady=false;", guard)
        end = replay.index("return false;", retry)
        for token in ("CopyRates(g_symbol,g_timeframe,1,1,signalReplayBar)",
                      "signalReplayBar[0].time!=rates[0].time",
                      "!EmttCopyOne", "!EmttSigValidPositive(signalAtr)",
                      "!SymbolInfoTick", "signalTick.bid", "signalTick.ask"):
            self.assertIn(token, replay[guard:retry])
        for token in ("g_lastClosedBarTime=rates[0].time;",
                      "EmttLearningAttachAndLoad(rates[0].time);",
                      "EmttSignalAdvance(", "EmttConsumeSignalEvents("):
            self.assertGreater(replay.index(token), end)

    def test_incomplete_replay_retries_without_new_candle(self):
        self.assertIn("else if(!g_snapshotReady && EmttReplayClosedHistory())", EA)

    def test_confidence_is_not_inside_signal_or_plan_gate(self):
        panel = EA.split("void FillPanel", 1)[1].split("void UpdatePanel", 1)[0]
        calculated = panel.index("d.confidence=EmttTierConfidenceRow(g_signal.viewsReady")
        session_gate = panel.index("if(sigReady)")
        self.assertLess(calculated, session_gate)
        self.assertIn('Preparing closed-bar indicators / higher timeframe', panel)


if __name__ == "__main__":
    unittest.main()
