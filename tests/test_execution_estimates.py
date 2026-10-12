"""Execute extracted MQL-compatible helpers in C++ with broker calls stubbed.
This validates helper logic, not MT5 API signatures or real broker contracts.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / 'Include/Emtt/Emtt_TradeManager.mqh').read_text()


class ExecutionEstimateTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('g++'), 'C++ compiler required for helper harness')
    def test_actual_helpers_with_stubbed_broker(self):
        estimate = MANAGER.split('string EmttTradeManagerEstimate(', 1)[1].split(
            'void EmttTradeManagerPlanMoney(', 1)[0]
        execution = MANAGER.split('string EmttTradeManagerExecutionReason(', 1)[1].split(
            'string EmttTradeManagerRetcodeText(', 1)[0]
        preamble = r'''
#include <cassert>
#include <cmath>
#include <string>
using string=std::string;
using ENUM_ORDER_TYPE=int;
const int ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1;
const double EMTT_PLAN_ENTRY_REACH_ATR=2, EMTT_PLAN_STOP_MIN_ATR=1,
             EMTT_PLAN_STOP_MAX_ATR=3;
bool MathIsValidNumber(double v) { return std::isfinite(v); }
double MathAbs(double v) { return std::abs(v); }
bool EmttTradeValidPositive(double v) { return std::isfinite(v) && v>0; }
double EmttPlanMinRiskReward(int mood) { return mood==1 ? 1.5 : 2; }
struct SEmttTradeOrderPlan { bool pending; double price; };
struct SEmttTradeRuntime { double atr, ask, bid; int mood; };
struct SEmttTradePlan { int side; double stop, target; };
bool brokerReady=true;
bool OrderCalcProfit(int type, const string&, double volume, double entry,
                     double exit, double& amount) {
    if(!brokerReady) return false;
    amount=(type==ORDER_TYPE_BUY ? 1 : -1)*(exit-entry)*volume;
    return true;
}
string EmttTradeManagerMoney(double amount) { return std::to_string(amount); }
'''
        cases = r'''
int main() {
    SEmttTradeOrderPlan o{true,100};
    SEmttTradeRuntime r{10,120,119,0};
    SEmttTradePlan p{1,80,140};
    assert(EmttTradeManagerExecutionReason(o,r,p).empty()); // 2 ATR inclusive
    r.ask=120.01;
    assert(EmttTradeManagerExecutionReason(o,r,p).find("pending entry")!=string::npos);
    r.ask=120; r.atr=0;
    assert(!EmttTradeManagerExecutionReason(o,r,p).empty());
    r.atr=10; o.pending=false; o.price=110;
    assert(EmttTradeManagerExecutionReason(o,r,p).find("reward/risk")!=string::npos);
    o.price=100; p.stop=100;
    assert(EmttTradeManagerExecutionReason(o,r,p).find("wrong side")!=string::npos);
    p.stop=95;
    assert(EmttTradeManagerExecutionReason(o,r,p).find("closer")!=string::npos);
    p.stop=69;
    assert(EmttTradeManagerExecutionReason(o,r,p).find("farther")!=string::npos);
    p={-1,120,60}; r.bid=80; o.pending=true;
    assert(EmttTradeManagerExecutionReason(o,r,p).empty()); // sell symmetry
    r.bid=79.99;
    assert(EmttTradeManagerExecutionReason(o,r,p).find("pending entry")!=string::npos);
    r.bid=80; o.pending=false; p={1,80,130}; r.mood=1;
    assert(EmttTradeManagerExecutionReason(o,r,p).empty()); // trend 1.5 RR
    r.mood=0;
    assert(!EmttTradeManagerExecutionReason(o,r,p).empty());
    assert(EmttTradeManagerEstimate("X",1,2,100,90)=="est. -20.000000");
    assert(EmttTradeManagerEstimate("X",-1,2,100,90)=="est. 20.000000");
    assert(EmttTradeManagerEstimate("X",1,2,100,90,true)=="est. 20.000000");
    assert(EmttTradeManagerEstimate("X",1,0,100,90)=="--");
    brokerReady=false;
    assert(EmttTradeManagerEstimate("X",1,2,100,90)=="--");
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'helpers.cpp'
            binary = Path(tmp) / 'helpers'
            source.write_text(preamble + 'string EmttTradeManagerEstimate(' + estimate
                              + 'string EmttTradeManagerExecutionReason(' + execution + cases)
            subprocess.run(['g++', '-std=c++17', str(source), '-o', str(binary)], check=True,
                           capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)

    def test_execution_guard_precedes_send_and_sizes_at_execution_price(self):
        body = MANAGER.split('void EmttTradeManagerTryOrder(', 1)[1].split(
            'void EmttTradeManagerBindCurrentOpenTicket(', 1)[0]
        self.assertLess(body.index('EmttTradeManagerExecutionReason('),
                        body.index('EmttTradeManagerSendOrder('))
        self.assertIn('EmttTradeResolveLots(runtime.lotMode,balance,order.price,', body)

    def test_pending_and_position_use_broker_volume(self):
        self.assertIn('data,symbol,state.side,pendingVolume,', MANAGER)
        self.assertIn('data,symbol,state.side,state.positionVolume,', MANAGER)
        self.assertIn('OrderGetDouble(ORDER_SL)', MANAGER)
        self.assertIn('Pending validity | ticket', MANAGER)


if __name__ == '__main__':
    unittest.main()
