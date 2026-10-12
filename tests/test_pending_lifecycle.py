"""Run production pending policy and cancellation helper in C++ harnesses.

The pure MQL policy is C++ compatible. Broker APIs are stubbed for cancellation
races; MT5 API signatures, server expiry and real partial fills need demo tests.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'Include/Emtt/Emtt_Pending.mqh'
MANAGER = (ROOT / 'Include/Emtt/Emtt_TradeManager.mqh').read_text()


def run_cpp(source):
    with tempfile.TemporaryDirectory() as tmp:
        cpp = Path(tmp) / 'check.cpp'
        exe = Path(tmp) / 'check'
        cpp.write_text(source)
        compiled = subprocess.run(['g++', '-std=c++17', str(cpp), '-o', str(exe)],
                                  capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)


@unittest.skipUnless(shutil.which('g++'), 'C++ compiler required')
class PendingPolicyTests(unittest.TestCase):
    def preamble(self):
        return ('#include <cassert>\n#include <string>\n'
                'using string=std::string; using datetime=long;\n'
                f'#include "{HEADER}"\n')

    def test_deadline_is_bounded_and_anchored_to_setup(self):
        run_cpp(self.preamble() + r'''
int main() {
    assert(EmttPendingBars(-5)==1);
    assert(EmttPendingBars(6)==6);
    assert(EmttPendingBars(1000)==96);
    assert(EmttPendingDeadline(1000,300,6,0)==2800); // M5 30min
    assert(EmttPendingDeadline(1000,900,6,0)==6400); // M15 90min
    assert(EmttPendingDeadline(1000,1800,6,0)==11800); // M30 3h
    assert(EmttPendingDeadline(1000,1800,6,60)==4600); // upper duration cap
    assert(EmttPendingDeadline(0,300,6,0)==0);
    assert(EmttPendingDeadline(1000,0,6,0)==0);
    // Restart/current clock and a new chart do not enter the calculation.
    for(int restart=0; restart<100; ++restart)
        assert(EmttPendingDeadline(1000,300,6,0)==2800);
}
''')

    def test_execution_prerequisites_report_first_blocker_and_log_changes_once(self):
        readiness = MANAGER.split('string EmttTradeManagerEntryReadiness(', 1)[1].split(
            'void EmttTradeManagerTryOrder(', 1)[0].split('{', 1)[1]
        gate = MANAGER.split('void EmttTradeManagerSetGateStatus(', 1)[1].split(
            'bool EmttTradeManagerSendOrder(', 1)[0].split('{', 1)[1]
        run_cpp(r'''
#include <cassert>
#include <string>
using string=std::string; using datetime=long;
struct SEmttTradeRuntime {
    bool chartCompatible=true, learningLoaded=true, analysisReady=true;
    bool connected=true, quoteFresh=true;
    int confidence=55; datetime barTime=100;
};
struct SEmttTradeState { string gateStatus; };
int calls=0;
string EmttTradeManagerTimeText(datetime) { return "time"; }
template<class... T> void PrintFormat(const char*,T...) { ++calls; }
void EmttTradeManagerSetGateStatus(SEmttTradeState &state,
                                   const string reason,const datetime barTime) {'''+gate+r'''
string EmttTradeManagerEntryReadiness(const SEmttTradeRuntime &runtime) {'''+readiness+r'''
int main() {
    SEmttTradeRuntime r;
    assert(EmttTradeManagerEntryReadiness(r)=="");
    r.quoteFresh=false;
    assert(EmttTradeManagerEntryReadiness(r)=="No trade - fresh broker quote unavailable");
    r.connected=false;
    assert(EmttTradeManagerEntryReadiness(r)=="No trade - terminal disconnected");
    r.connected=true; r.learningLoaded=false;
    assert(EmttTradeManagerEntryReadiness(r)=="No trade - learning file not ready");
    r.chartCompatible=false;
    assert(EmttTradeManagerEntryReadiness(r)=="No trade - incompatible chart timeframe");
    r.chartCompatible=true; r.learningLoaded=true; r.analysisReady=false;
    assert(EmttTradeManagerEntryReadiness(r)=="No trade - closed-bar analysis not ready");
    SEmttTradeState s;
    EmttTradeManagerSetGateStatus(s,"No trade - closed-bar analysis not ready",100);
    EmttTradeManagerSetGateStatus(s,"No trade - closed-bar analysis not ready",100);
    assert(calls==1);
    EmttTradeManagerSetGateStatus(s,"No trade - terminal disconnected",100);
    assert(calls==2);
}
''')
        attempt = MANAGER.split('void EmttTradeManagerTryOrder(', 1)[1].split(
            'void EmttTradeManagerBindCurrentOpenTicket(', 1)[0]
        self.assertLess(attempt.index('EmttTradeManagerEntryReadiness(runtime)'),
                        attempt.index('EmttPendingRetired('))
        self.assertLess(attempt.index('EmttPendingRetired('),
                        attempt.index('EmttTradeBuildOrder('))
        self.assertIn('EmttTradeManagerSetGateStatus(state,\n         "No trade - this order-block execution attempt is retired"', attempt)

    def test_panel_distinguishes_retired_entry_from_live_order(self):
        ea = (ROOT / 'Experts/Emtt.mq5').read_text()
        panel = ea.split('void EmttTradeManagerPanelStatus(SEmttPanelData &data)', 1)[1].split(
            'void EmttJournalSignalState(', 1)[0]
        self.assertIn('d.status="Signal plan - entry not reached yet.";', ea)
        run_cpp(r'''
#include <cassert>
#include <string>
using string=std::string; using datetime=long;
const int EMTT_PLAN_ENTRY_BLOCK=1, SYMBOL_POINT=2, EMTT_CLR_SELL=3, PERIOD_CURRENT=0;
struct SEmttPanelData { string status; int statusClr=0; };
struct Plan { bool active=true; int entryKind=EMTT_PLAN_ENTRY_BLOCK; int side=1; double entry=100; };
struct Signal { Plan plan; } g_signal;
struct Trade {
    int tradeTimeframe=0; bool pendingOrder=false, positionOpen=false;
    string freshStatus, holdStatus, newsStatus, gateStatus, liveStatus;
    datetime freshStatusBarTime=0;
} g_trade;
string g_symbol="ETHUSDm";
int g_timeframe=30;
datetime g_lastClosedBarTime=100;
bool g_snapshotReady=true, g_marketOpen=true, retired=false;
bool TfAllowed() { return true; }
datetime iTime(const string&,int,int) { return 100; }
double SymbolInfoDouble(const string&,int) { return 0.01; }
int StringFind(const string& s,const string& needle) {
    auto pos=s.find(needle); return pos==string::npos ? -1 : (int)pos;
}
bool EmttPendingRetired(const Trade&,int tf,int side,double entry,double) {
    return retired && tf==30 && side==1 && entry==100;
}
void EmttTradeManagerPanelStatus(SEmttPanelData &data)'''+panel+r'''
int main() {
    SEmttPanelData d;
    d.status="Signal plan - entry not reached yet.";
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="Signal plan - entry not reached yet.");
    retired=true;
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="No trade - entry attempt ended; new setup needed.");
    assert(d.statusClr==EMTT_CLR_SELL);
    g_trade.gateStatus="No trade - this order-block execution attempt is retired";
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="No trade - entry attempt ended; new setup needed.");
    g_trade.gateStatus="";
    g_trade.pendingOrder=true; g_trade.liveStatus="Pending order at 100";
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="Pending order at 100");
    g_trade.pendingOrder=false; g_trade.positionOpen=true;
    g_trade.liveStatus="Position open";
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="Position open");
    g_trade.positionOpen=false; g_trade.gateStatus="Order rejected - broker error";
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="Order rejected - broker error");
    g_trade.gateStatus=""; g_signal.plan.entry=101; d.status="Signal plan";
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="Signal plan");
    g_trade.newsStatus="News note"; g_trade.gateStatus="No trade - stale quote";
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="No trade - stale quote");
    g_trade.gateStatus=""; EmttTradeManagerPanelStatus(d);
    assert(d.status=="News note");
    g_trade.newsStatus="";
    g_signal.plan.entry=100; g_trade.freshStatus="Recent trade event";
    g_trade.freshStatusBarTime=100;
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="Recent trade event");
    g_trade.freshStatus=""; g_marketOpen=false; d.status="MARKET CLOSED";
    EmttTradeManagerPanelStatus(d);
    assert(d.status=="MARKET CLOSED");
}
''')

    def test_pending_policy_both_directions_and_boundaries(self):
        run_cpp(self.preamble() + r'''
SEmttPendingCheck good(int side=1) {
    SEmttPendingCheck c{};
    c.now=1000; c.deadline=2800; c.autoTrading=true;
    c.metadataReady=true; c.analysisReady=true; c.marketKnown=true;
    c.marketOpen=true; c.quoteReady=true; c.planMatches=true;
    c.confidence=60; c.threshold=56; c.side=side;
    c.entry=100; c.stop=(side==1 ? 80 : 120);
    c.target=(side==1 ? 140 : 60); c.blockFarEdge=(side==1 ? 95 : 105);
    c.bid=(side==1 ? 110 : 89); c.ask=c.bid+1;
    c.closedPrice=(side==1 ? 110 : 90); c.atr=10;
    return c;
}
int main() {
    for(int side: {1,-1}) {
        auto c=good(side);
        assert(EmttPendingDecision(c)==EMTT_PENDING_KEEP);
        c.now=2800; assert(EmttPendingDecision(c)==EMTT_PENDING_EXPIRED);
        c=good(side); c.autoTrading=false;
        assert(EmttPendingDecision(c)==EMTT_PENDING_DISABLED);
        c.partialFill=true;
        assert(EmttPendingDecision(c)==EMTT_PENDING_PARTIAL);
        c=good(side); c.confidence=56;
        assert(EmttPendingDecision(c)==EMTT_PENDING_KEEP);
        c.confidence=55;
        assert(EmttPendingDecision(c)==EMTT_PENDING_CONFIDENCE);
        c.confidence=34;
        assert(EmttPendingDecision(c)==EMTT_PENDING_CONFIDENCE);
        c=good(side); c.planMatches=false;
        assert(EmttPendingDecision(c)==EMTT_PENDING_SIGNAL);
        c=good(side); c.closedPrice=c.blockFarEdge-side;
        assert(EmttPendingDecision(c)==EMTT_PENDING_BLOCK);
        c=good(side); c.closedPrice=c.entry+side*20;
        assert(EmttPendingDecision(c)==EMTT_PENDING_KEEP);
        c.closedPrice+=side*0.01;
        assert(EmttPendingDecision(c)==EMTT_PENDING_DISTANCE);
        c=good(side); if(side==1) c.bid=c.target; else c.ask=c.target;
        assert(EmttPendingDecision(c)==EMTT_PENDING_TARGET);
        c=good(side); if(side==1) c.bid=c.stop; else c.ask=c.stop;
        assert(EmttPendingDecision(c)==EMTT_PENDING_STOP);
        c.quoteReady=false;
        assert(EmttPendingDecision(c)==EMTT_PENDING_KEEP);
        c=good(side); c.marketOpen=false;
        assert(EmttPendingDecision(c)==EMTT_PENDING_MARKET);
        c.marketKnown=false;
        assert(EmttPendingDecision(c)==EMTT_PENDING_KEEP);
    }
}
''')

    def test_loading_grace_does_not_mask_expiry_or_partial_fill(self):
        run_cpp(self.preamble() + r'''
int main() {
    SEmttPendingCheck c{};
    c.now=1000; c.deadline=2000; c.autoTrading=true;
    c.unavailableSince=1000; c.metadataReady=false; c.analysisReady=false;
    c.confidence=-1;
    assert(EmttPendingDecision(c)==EMTT_PENDING_KEEP);
    c.now=1059; assert(EmttPendingDecision(c)==EMTT_PENDING_KEEP);
    c.now=1060; assert(EmttPendingDecision(c)==EMTT_PENDING_RECOVERY);
    c.now=2000; assert(EmttPendingDecision(c)==EMTT_PENDING_EXPIRED);
    c.partialFill=true; assert(EmttPendingDecision(c)==EMTT_PENDING_PARTIAL);
    c.partialFill=false; c.autoTrading=false;
    assert(EmttPendingDecision(c)==EMTT_PENDING_DISABLED);
}
''')

    def test_cancel_confirmation_retry_permissions_and_fill_races(self):
        helper = MANAGER.split('void EmttTradeManagerCancelPending(', 1)[1].split(
            'void EmttTradeManagerUpdateExtremes(', 1)[0]
        run_cpp(self.preamble() + r'''
#include <algorithm>
using uint=unsigned int;
const int TERMINAL_CONNECTED=1, TERMINAL_TRADE_ALLOWED=2, MQL_TRADE_ALLOWED=3,
          ACCOUNT_TRADE_ALLOWED=4, ORDER_STATE=5;
const uint TRADE_RETCODE_DONE=10009;
enum ENUM_ORDER_STATE { ORDER_STATE_CANCELED, ORDER_STATE_EXPIRED,
                       ORDER_STATE_FILLED, ORDER_STATE_REJECTED, ORDER_STATE_STARTED };
struct SEmttTradeState {
    bool pendingOrder=true, pendingMetadataReady=true, hasPlanContext=true, positionOpen=false;
    unsigned long pendingTicket=123; long magic=1;
    datetime pendingCancelAttempt=0;
    int pendingCancelCode=0, tradeTimeframe=5, side=1;
    double plannedEntry=100;
    string gateStatus, liveStatus;
};
long now=1000; bool permission=true, still=true, history=true, filled=false;
int calls=0, observes=0, saves=0, retires=0;
ENUM_ORDER_STATE outcome=ORDER_STATE_CANCELED;
struct Executor {
    bool answer=true; uint code=TRADE_RETCODE_DONE;
    void SetExpertMagicNumber(unsigned long) {}
    void SetAsyncMode(bool) {}
    bool OrderDelete(unsigned long) { ++calls; return answer; }
    uint ResultRetcode() { return code; }
} g_emttTradeExecutor;
long TimeTradeServer() { return now; }
long TimeCurrent() { return now; }
int TerminalInfoInteger(int) { return permission; }
int MQLInfoInteger(int) { return permission; }
int AccountInfoInteger(int) { return permission; }
string EmttPendingKey(const SEmttTradeState&) { return "lease"; }
int GlobalVariableSet(const string&,double) { ++saves; return 1; }
void GlobalVariablesFlush() {}
bool EmttPendingRetire(const SEmttTradeState&,int,int,double) { ++retires; return true; }
bool OrderSelect(unsigned long) { return still; }
bool HistoryOrderSelect(unsigned long) { return history; }
long HistoryOrderGetInteger(unsigned long,int) { return outcome; }
string IntegerToString(int v) { return std::to_string(v); }
string EmttTradeManagerTimeText(long v) { return std::to_string(v); }
template<class... T> void PrintFormat(const char*,T...) {}
void EmttTradeManagerObserve(SEmttTradeState& s, long) {
    ++observes; if(filled) s.positionOpen=true;
}
''' + 'void EmttTradeManagerCancelPending(' + helper + r'''
int main() {
    SEmttTradeState s;
    EmttTradeManagerCancelPending(s,"expired",now);
    assert(s.pendingOrder && calls==1); // boolean + DONE not enough: order still exists
    EmttTradeManagerCancelPending(s,"expired",now);
    assert(calls==1); // retry throttle
    now+=5; still=false; history=false;
    EmttTradeManagerCancelPending(s,"expired",now);
    assert(s.pendingOrder && calls==2); // no authoritative history yet
    now+=5; history=true;
    EmttTradeManagerCancelPending(s,"expired",now);
    assert(!s.pendingOrder && !s.hasPlanContext && observes==1);
    s=SEmttTradeState{}; now+=5;
    g_emttTradeExecutor.answer=false; g_emttTradeExecutor.code=10013;
    outcome=ORDER_STATE_FILLED; filled=true;
    EmttTradeManagerCancelPending(s,"expired",now);
    assert(!s.pendingOrder && s.positionOpen && s.hasPlanContext); // fill won race
    s=SEmttTradeState{}; s.positionOpen=true; now+=5;
    filled=false; outcome=ORDER_STATE_CANCELED;
    EmttTradeManagerCancelPending(s,"partial",now);
    assert(!s.pendingOrder && s.positionOpen && s.hasPlanContext); // preserve filled volume
    s=SEmttTradeState{}; now+=5; permission=false;
    int before=calls;
    EmttTradeManagerCancelPending(s,"disabled",now);
    assert(s.pendingOrder && calls==before && s.pendingCancelCode!=0);
    assert(saves>0 && retires>0); // durable intent before broker request
    permission=true; now+=5; outcome=ORDER_STATE_EXPIRED;
    EmttTradeManagerCancelPending(s,"expired",now);
    assert(!s.pendingOrder && !s.hasPlanContext);
}
''')


    def test_real_lease_helpers_recover_identity_and_reject_torn_writes(self):
        helpers = MANAGER.split('string EmttPendingKey(', 1)[1].split(
            'void EmttTradeManagerObserve(', 1)[0]
        run_cpp(self.preamble() + r'''
#include <map>
#include <cmath>
#include <cstdio>
using ENUM_TIMEFRAMES=int;
const int PERIOD_M5=5, PERIOD_M15=15, PERIOD_M30=30;
const int ACCOUNT_SERVER=1, ACCOUNT_LOGIN=2, SYMBOL_POINT=3,
          ORDER_TIME_SETUP=4, ORDER_PRICE_OPEN=5, ORDER_TYPE=6, ORDER_TYPE_BUY_LIMIT=7;
struct SEmttTradeState {
    string symbol="ETHUSDm", recordTfName;
    long magic=123; int tradeTimeframe=30, side=1, entryKind=0;
    unsigned long pendingTicket=999;
    bool pendingOrder=true, pendingMetadataReady=false, hasPlanContext=false;
    long pendingDeadline=0, pendingCancelAttempt=0, pendingUnavailableSince=0,
         planStartBarTime=0;
    int pendingCancelCode=0;
    double pendingBlockFarEdge=95, plannedEntry=0, plannedStop=0,
           plannedTarget=0, entryAtr=0;
};
struct SEmttTradeRuntime { double point=.01, atr=10; int timeframe=30; };
struct SEmttTradePlan { long startBarTime=100; int side=1; double entry=100, stop=80, target=140; };
struct SEmttSmcState {};
const int EMTT_PLAN_ENTRY_BLOCK=1;
std::map<string,double> globals;
string failKey="", server="broker";
long login=10, brokerSetup=1000;
double brokerEntry=100;
string AccountInfoString(int) { return server; }
long AccountInfoInteger(int) { return login; }
int StringLen(const string& s) { return s.size(); }
int StringGetCharacter(const string& s,int i) { return s[i]; }
template<class... T> string StringFormat(string f,T... args) {
    for(auto pair: {std::pair<string,string>{"%I64d","%ld"}, {"%I64u","%lu"}}) {
        size_t i=0;
        while((i=f.find(pair.first,i))!=string::npos) f.replace(i,pair.first.size(),pair.second);
    }
    char b[256]; std::snprintf(b,sizeof(b),f.c_str(),args...); return b;
}
string EmttTradeManagerTfName(int tf) { return "M"+std::to_string(tf); }
bool GlobalVariableCheck(const string& k) { return globals.count(k)!=0; }
double GlobalVariableGet(const string& k) { return globals[k]; }
long GlobalVariableSet(const string& k,double v) {
    if(k==failKey) return 0;
    globals[k]=v; return 1000;
}
void GlobalVariablesFlush() {}
double MathAbs(double v) { return std::abs(v); }
double MathMax(double a,double b) { return a>b ? a:b; }
bool OrderSelect(unsigned long) { return true; }
long OrderGetInteger(int prop) { return prop==ORDER_TIME_SETUP ? brokerSetup : ORDER_TYPE_BUY_LIMIT; }
double OrderGetDouble(int) { return brokerEntry; }
double SymbolInfoDouble(const string&,int) { return .01; }
''' + 'string EmttPendingKey(' + helpers + r'''
int main() {
    SEmttTradeState s; SEmttTradeRuntime r; SEmttTradePlan p; SEmttSmcState smc;
    assert(EmttPendingSaveLease(s,r,p,smc,11800,1000));
    assert(EmttPendingRetire(s,30,1,100));
    assert(EmttPendingRetired(s,30,1,100,.01));
    assert(!EmttPendingRetired(s,30,-1,100,.01));
    assert(!EmttPendingRetired(s,15,1,100,.01));
    assert(!EmttPendingRetired(s,30,1,101,.01));
    auto key=EmttPendingKey(s);
    login=11; assert(!EmttPendingRetired(s,30,1,100,.01)); login=10;
    server="other"; assert(EmttPendingKey(s)!=key); server="broker";
    SEmttTradeState restarted; restarted.tradeTimeframe=5;
    EmttPendingRecover(restarted);
    assert(restarted.pendingMetadataReady);
    assert(restarted.pendingDeadline==11800 && restarted.tradeTimeframe==30);
    assert(restarted.planStartBarTime==100 && restarted.pendingBlockFarEdge==95);
    globals[key+".cancel"]=EMTT_PENDING_CONFIDENCE;
    globals[key+".unavailable"]=1010;
    EmttPendingRecover(restarted);
    assert(restarted.pendingCancelCode==EMTT_PENDING_CONFIDENCE);
    assert(restarted.pendingUnavailableSince==1010);
    brokerEntry=101; EmttPendingRecover(restarted);
    assert(!restarted.pendingMetadataReady); brokerEntry=100;
    brokerSetup=2000; EmttPendingRecover(restarted);
    assert(!restarted.pendingMetadataReady);
    globals[key+".o999"]=1; EmttPendingRecover(restarted);
    assert(restarted.pendingMetadataReady); // verified receipt survives restart
    brokerSetup=1000;
    failKey=key+".target";
    assert(!EmttPendingSaveLease(s,r,p,smc,20000,1000));
    EmttPendingRecover(restarted);
    assert(!restarted.pendingMetadataReady); // valid marker rejects torn lease
}
''')


class PendingWiringTests(unittest.TestCase):
    def test_lease_written_and_retired_before_send(self):
        send = MANAGER.split('bool EmttTradeManagerSendOrder(', 1)[1].split(
            'void EmttTradeManager', 1)[0]
        for token in ('EmttPendingSaveLease(', 'EmttPendingRetire('):
            self.assertLess(send.index(token), send.index('.BuyLimit('))
        self.assertIn('SYMBOL_EXPIRATION_SPECIFIED', send)
        self.assertIn('ORDER_TIME_SPECIFIED', send)
        self.assertIn('EA-only expiry; offline order can remain active', send)
        self.assertIn('plan.startBarTime+PeriodSeconds(runtime.timeframe)', send)

    def test_recovery_preserves_deadline_and_origin(self):
        recover = MANAGER.split('void EmttPendingRecover(', 1)[1].split(
            'void EmttTradeManagerObserve(', 1)[0]
        self.assertIn('state.pendingDeadline=due;', recover)
        self.assertIn('state.tradeTimeframe=tf;', recover)
        self.assertIn('state.planStartBarTime=plan;', recover)
        self.assertNotIn('EmttPendingDeadline(', recover)
        step = MANAGER.split('void EmttTradeManagerStep(', 1)[1].split(
            'void EmttTradeManagerFeedTick(', 1)[0]
        self.assertIn('runtime.timeframe==state.tradeTimeframe', step)
        self.assertIn('check.partialFill=state.positionOpen;', step)
        self.assertIn('check.threshold=runtime.autoTradeAbove;', step)
        self.assertIn('GlobalVariablesFlush();', step)

    def test_observation_does_not_assume_missing_order_was_cancelled(self):
        observe = MANAGER.split('void EmttTradeManagerObserve(', 1)[1].split(
            'void EmttTradeManagerBindTicket(', 1)[0]
        self.assertIn('!HistoryOrderSelect(state.pendingTicket)', observe)
        self.assertIn('ORDER_STATE_FILLED', observe)
        adopt = MANAGER.split('void EmttTradeManagerAdoptPosition(', 1)[1].split(
            'bool EmttTradeManagerHistoryNet(', 1)[0]
        self.assertNotIn('state.pendingOrder=false;', adopt)
        self.assertNotIn('state.pendingTicket=0;', adopt)

    def test_pending_block_is_visible_for_expiry_and_protection(self):
        panel = MANAGER.split('void EmttTradeManagerFillPanel(', 1)[1]
        pending = panel.split('if(state.pendingOrder)', 1)[1].split('return;', 1)[0]
        self.assertIn('data.showLive=true;', pending)
        self.assertIn('Pending validity:', pending)
        self.assertIn('EA-only; keep MT5 online', pending)

    def test_new_input_and_account_namespace(self):
        ea = (ROOT / 'Experts/Emtt.mq5').read_text()
        self.assertIn('input int InpPendingValidityBars=6;', ea)
        self.assertIn('runtime.analysisReady=(g_snapshotReady', ea)
        key = MANAGER.split('string EmttPendingKey(', 1)[1].split(
            'string EmttPendingBlockKey(', 1)[0]
        for token in ('ACCOUNT_LOGIN', 'ACCOUNT_SERVER', 'state.symbol', 'state.magic'):
            self.assertIn(token, key)


if __name__ == '__main__':
    unittest.main()
