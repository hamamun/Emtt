//+------------------------------------------------------------------+
//|                                              Emtt_Signal.mqh     |
//| Phase 6: confidence engine, signal gate and trade-plan lifecycle |
//| Spec: Emtt.md sections 17.3, 17.6-17.8                           |
//+------------------------------------------------------------------+
//| Pure logic over the four published states (Supertrend, SMC,     |
//| volume flow, MTF). This phase places no order: nothing here      |
//| sends, modifies, closes or deletes anything - Emtt says what it  |
//| would do, where, and why, and nothing more (17.2 rule 1).        |
//| The header reads no chart, no panel and no EA global.            |
//| ASCII source only (17.2 rule 9): every glyph is an escape, so    |
//| the dash in the panel text is written "\x2014".                  |
//+------------------------------------------------------------------+
#ifndef EMTT_SIGNAL_MQH
#define EMTT_SIGNAL_MQH

#include "Emtt_Regime.mqh"
#include "Emtt_Supertrend.mqh"
#include "Emtt_SMC.mqh"
#include "Emtt_VolumeFlow.mqh"
#include "Emtt_MTF.mqh"
#include "Emtt_TradePlan.mqh"

//--- 17.3 / 17.5 the confidence rows ---------------------------------
#define EMTT_SIG_WEIGHT_TREND     0.30
#define EMTT_SIG_WEIGHT_STRUCTURE 0.30
#define EMTT_SIG_WEIGHT_FLOW      0.20
#define EMTT_SIG_WEIGHT_HTF       0.20
#define EMTT_SIG_STAY_MARGIN      5

// The WAIT glyph of 17.6: a black square. The pause glyph of the Phase 1
// mock-up is not in Segoe UI, so WAIT shows this one instead.
#define EMTT_SIG_GLYPH_WAIT       0x25A0

// The 17.6 WAIT reasons, checked in this order.
enum EEmttSigWait
  {
   EMTT_SIG_WAIT_NONE=0,
   EMTT_SIG_WAIT_BELOW_BAR,
   EMTT_SIG_WAIT_BELOW_KEEP,
   EMTT_SIG_WAIT_NO_TARGET,
   EMTT_SIG_WAIT_STOP_FAR,
   EMTT_SIG_WAIT_NO_SWING,
   EMTT_SIG_WAIT_JUST_ENDED
  };

// The 17.7 plan results.
enum EEmttPlanResult
  {
   EMTT_PLAN_RESULT_NONE=0,
   EMTT_PLAN_RESULT_TARGET,
   EMTT_PLAN_RESULT_STOP,
   EMTT_PLAN_RESULT_MISSED,
   EMTT_PLAN_RESULT_CANCELLED,
   EMTT_PLAN_RESULT_SIGNAL,
   EMTT_PLAN_RESULT_CLOSED,
   EMTT_PLAN_RESULT_CHART
  };

//+------------------------------------------------------------------+
//| Published signal state. One instance lives in the EA; plans live |
//| in memory only and a restart never restores them (17.7).         |
//+------------------------------------------------------------------+
struct SEmttSignalState
  {
   bool            initialized;
   bool            viewsReady;    // all four views ready (17.2 rule 4)
   double          combined;      // S of 17.3, between -1 and +1
   int             confidence;    // the Row 3 whole number, -1 = not ready
   EEmttRegime     mood;          // the 17.2 rule 3 mood of the newest bar
   int             moodBar;       // the 9.2.4 bar for that mood
   int             signal;        // +1 BUY / -1 SELL / 0 WAIT
   int             previousSignal;// the signal shown at the previous candle
   bool            justEnded;     // a plan ended on the newest candle
   EEmttSigWait    waitReason;
   int             waitSide;      // the kept side for the BELOW_KEEP line
   SEmttTradePlan  plan;
   double          lastClose;
   datetime        lastBarTime;
   long            lastSequence;
   int             digits;        // the symbol's digits, stored at evaluation
   double          point;         // the symbol's point, stored at evaluation
   // journal dedup (17.8): state changes and reason changes only
   bool            hasJournaledSignal;
   int             journaledSignal;
   bool            hasJournaledWait;
   EEmttSigWait    journaledWaitReason;
  };

//+------------------------------------------------------------------+
//| Small local helpers. No EA helper is called from this component. |
//+------------------------------------------------------------------+
bool EmttSigValid(const double value)
  {
   return(MathIsValidNumber(value) && value!=EMPTY_VALUE);
  }

bool EmttSigValidPositive(const double value)
  {
   return(EmttSigValid(value) && value>0.0);
  }

void EmttSignalReset(SEmttSignalState &state)
  {
   state.initialized=false;
   state.viewsReady=false;
   state.combined=0.0;
   state.confidence=-1;
   state.mood=EMTT_REGIME_UNKNOWN;
   state.moodBar=0;
   state.signal=0;
   state.previousSignal=0;
   state.justEnded=false;
   state.waitReason=EMTT_SIG_WAIT_NONE;
   state.waitSide=0;
   EmttPlanReset(state.plan);
   state.lastClose=0.0;
   state.lastBarTime=0;
   state.lastSequence=-1;
   state.digits=0;
   state.point=0.0;
   state.hasJournaledSignal=false;
   state.journaledSignal=0;
   state.hasJournaledWait=false;
   state.journaledWaitReason=EMTT_SIG_WAIT_NONE;
  }

// A signal needs all four views ready; no partial confidence is ever
// shown (17.2 rule 4, 15.10).
bool EmttSignalViewsReady(const SEmttSupertrendState &st,
                          const SEmttSmcState &smc,
                          const SEmttVolumeFlowState &vf,
                          const SEmttMtfState &mtf)
  {
   return(st.ready && smc.ready && vf.ready && mtf.ready);
  }

// 17.3: S = sum(w x s x d). The weights sum to exactly 1.0, so S lies
// between -1 and +1; a flat view (d = 0) adds nothing and a view
// pointing the other way pulls S down.
double EmttSignalCombined(const SEmttSupertrendState &st,
                          const SEmttSmcState &smc,
                          const SEmttVolumeFlowState &vf,
                          const SEmttMtfState &mtf)
  {
   return EMTT_SIG_WEIGHT_TREND*st.score*st.direction+
          EMTT_SIG_WEIGHT_STRUCTURE*smc.smcScore*smc.bias+
          EMTT_SIG_WEIGHT_FLOW*vf.volumeFlowScore*vf.flowDirection+
          EMTT_SIG_WEIGHT_HTF*mtf.mtfScore*mtf.htfSupertrendDirection;
  }

// Row 3 shows one whole number, round(100 x |S|), halves rounded up.
int EmttSignalConfidenceNumber(const double combined)
  {
   if(!EmttSigValid(combined))
      return 0;
   return (int)MathRound(100.0*MathAbs(combined));
  }

// The 9.2.4 bar, unchanged, read from the mood of 17.2 rule 3.
int EmttSignalMoodBar(const EEmttRegime mood)
  {
   if(mood==EMTT_REGIME_TRENDING_BULLISH || mood==EMTT_REGIME_TRENDING_BEARISH)
      return 60;
   if(mood==EMTT_REGIME_RANGING || mood==EMTT_REGIME_VOLATILE)
      return 70;
   if(mood==EMTT_REGIME_TRANSITION)
      return 75;
   return 0;
  }

string EmttSignalMoodWord(const EEmttRegime mood)
  {
   if(mood==EMTT_REGIME_TRENDING_BULLISH || mood==EMTT_REGIME_TRENDING_BEARISH)
      return "Trending";
   if(mood==EMTT_REGIME_RANGING)
      return "Ranging";
   if(mood==EMTT_REGIME_VOLATILE)
      return "Volatile";
   if(mood==EMTT_REGIME_TRANSITION)
      return "Transition";
   return "--";
  }

string EmttPlanResultName(const EEmttPlanResult result)
  {
   switch(result)
     {
      case EMTT_PLAN_RESULT_TARGET:    return "target reached";
      case EMTT_PLAN_RESULT_STOP:      return "stop reached";
      case EMTT_PLAN_RESULT_MISSED:    return "missed";
      case EMTT_PLAN_RESULT_CANCELLED: return "cancelled";
      case EMTT_PLAN_RESULT_SIGNAL:    return "signal changed";
      case EMTT_PLAN_RESULT_CLOSED:    return "market closed";
      case EMTT_PLAN_RESULT_CHART:     return "chart changed";
      default:                         return "";
     }
  }

// The bare reason of a 17.6 WAIT line, without the "Watching - " prefix,
// the confidence number or the trailing period. Also the wording of the
// journal's "reason changed:" line.
string EmttSignalWaitBare(const SEmttSignalState &state)
  {
   switch(state.waitReason)
     {
      case EMTT_SIG_WAIT_BELOW_BAR:
         return "below the "+IntegerToString(state.moodBar)+"% bar";
      case EMTT_SIG_WAIT_BELOW_KEEP:
         return "below the "+
                IntegerToString(state.moodBar-EMTT_SIG_STAY_MARGIN)+
                "% level that keeps a "+EmttPlanSideName(state.waitSide);
      case EMTT_SIG_WAIT_NO_TARGET:
         return "no target gives 1:"+
                DoubleToString(EmttPlanMinRiskReward(state.mood),1);
      case EMTT_SIG_WAIT_STOP_FAR:
         return "stop would be more than "+
                DoubleToString(EMTT_PLAN_STOP_MAX_ATR,1)+" ATR away";
      case EMTT_SIG_WAIT_NO_SWING:
         return "no swing point for the stop yet";
      case EMTT_SIG_WAIT_JUST_ENDED:
         return "the last idea just ended; a new one can start on the next candle";
      default:
         return "";
     }
  }

// The full 17.6 WAIT line of Row 10.
string EmttSignalWaitText(const SEmttSignalState &state)
  {
   if(state.confidence<0)
      return "";
   const string number=IntegerToString(state.confidence)+"%";
   switch(state.waitReason)
     {
      case EMTT_SIG_WAIT_BELOW_BAR:
         return "Watching \x2014 confidence "+number+", below the "+
                IntegerToString(state.moodBar)+"% bar.";
      case EMTT_SIG_WAIT_BELOW_KEEP:
         return "Watching \x2014 confidence "+number+", below the "+
                IntegerToString(state.moodBar-EMTT_SIG_STAY_MARGIN)+
                "% level that keeps a "+EmttPlanSideName(state.waitSide)+".";
      case EMTT_SIG_WAIT_NO_TARGET:
         return "Watching \x2014 confidence "+number+
                ", but no target gives 1:"+
                DoubleToString(EmttPlanMinRiskReward(state.mood),1)+" yet.";
      case EMTT_SIG_WAIT_STOP_FAR:
         return "Watching \x2014 confidence "+number+
                ", but the stop would be more than "+
                DoubleToString(EMTT_PLAN_STOP_MAX_ATR,1)+" ATR away.";
      case EMTT_SIG_WAIT_NO_SWING:
         return "Watching \x2014 confidence "+number+
                ", but no swing point for the stop yet.";
      case EMTT_SIG_WAIT_JUST_ENDED:
         return "Watching \x2014 the last idea just ended; a new one can start on the next candle.";
      default:
         return "";
     }
  }

// The detail of the journal's "Signal WAIT" line (17.8).
string EmttSignalWaitDetail(const SEmttSignalState &state)
  {
   if(state.waitReason==EMTT_SIG_WAIT_JUST_ENDED)
      return EmttSignalWaitBare(state);
   return "confidence "+IntegerToString(state.confidence)+"%, "+
          EmttSignalWaitBare(state);
  }

//+------------------------------------------------------------------+
//| Row 10 while the four views are ready (17.6). The level lines are |
//| a display comparison of the live price with a stored level; they  |
//| change no state. A BUY's stop is watched on the Bid and its       |
//| target on the Ask; SELL mirrors it.                               |
//+------------------------------------------------------------------+
string EmttSignalStatusText(const SEmttSignalState &state,
                            const double bid,const double ask)
  {
   if(state.plan.active && state.signal!=0)
     {
      const int side=state.signal;
      const bool stopPassed=(side>0 ? bid<=state.plan.stop
                                    : ask>=state.plan.stop);
      const bool targetPassed=(side>0 ? ask>=state.plan.target
                                      : bid<=state.plan.target);
      if(stopPassed)
         return "Stop level passed \x2014 signal updates at this candle's close.";
      if(targetPassed)
         return "Target level passed \x2014 signal updates at this candle's close.";
      if(state.plan.status==EMTT_PLAN_PENDING)
         return "Signal active \x2014 waiting for price to reach entry. No order placed.";
      return "Signal active \x2014 price reached entry. No order placed.";
     }
   return EmttSignalWaitText(state);
  }

//+------------------------------------------------------------------+
//| 17.8 the result journal line. The exit is the level reached, or  |
//| the candle's close for signal changed / market closed / chart     |
//| changed. The points are signed, whole, and explicit.             |
//+------------------------------------------------------------------+
void EmttSignalJournalResult(SEmttSignalState &state,
                             const EEmttPlanResult result,
                             const double exitPrice,
                             const long endSequence,
                             const datetime barTime,
                             const bool sharedCandle,
                             const bool writeJournal)
  {
   if(!writeJournal || !state.plan.active)
      return;
   const int side=state.plan.side;
   double points=0.0;
   if(state.point>0.0)
      points=((side>0 ? exitPrice-state.plan.entry
                      : state.plan.entry-exitPrice)/state.point);
   const int pointsWhole=(int)MathRound(points);
   const int absPoints=(pointsWhole<0 ? -pointsWhole : pointsWhole);
   const string sign=(pointsWhole>=0 ? "+" : "-");
   long candles=endSequence-state.plan.startSequence;
   if(candles<0)
      candles=0;
   PrintFormat("Emtt | Plan %s result | %s | exit %s | %s%d pts | %d candles%s | bar %s",
               EmttPlanSideName(side),EmttPlanResultName(result),
               DoubleToString(exitPrice,state.digits),sign,absPoints,
               (int)candles,(sharedCandle ? " | shared candle" : ""),
               TimeToString(barTime,TIME_DATE|TIME_MINUTES));
  }

//+------------------------------------------------------------------+
//| End the open plan with exactly one result (17.7), journal it,    |
//| and leave the signal at WAIT. `justEnded` marks the candle that   |
//| ended the plan: it never starts a new one.                       |
//+------------------------------------------------------------------+
void EmttSignalEndPlan(SEmttSignalState &state,
                       const EEmttPlanResult result,
                       const double exitPrice,
                       const long endSequence,
                       const datetime barTime,
                       const bool sharedCandle,
                       const bool writeJournal)
  {
   if(!state.plan.active)
      return;
   const int side=state.plan.side;
   EmttSignalJournalResult(state,result,exitPrice,endSequence,barTime,
                           sharedCandle,writeJournal);
   state.waitSide=side;
   EmttPlanReset(state.plan);
   state.signal=0;
   state.justEnded=true;
  }

// 17.7: the market closing ends any open plan. The exit is the last
// closed candle's close. This end is not a candle end, so the next
// candle after the reopen may start a new idea.
void EmttSignalMarketClosed(SEmttSignalState &state,const bool writeJournal)
  {
   if(!state.plan.active)
      return;
   EmttSignalEndPlan(state,EMTT_PLAN_RESULT_CLOSED,state.lastClose,
                     state.lastSequence,state.lastBarTime,false,
                     writeJournal);
   state.signal=0;
   state.previousSignal=0;
   state.justEnded=false;
   state.waitReason=EMTT_SIG_WAIT_NONE;
   state.waitSide=0;
   state.hasJournaledSignal=false;
   state.journaledSignal=0;
   state.hasJournaledWait=false;
   state.journaledWaitReason=EMTT_SIG_WAIT_NONE;
  }

// 17.7: a symbol or timeframe change ends any open plan the same way.
// Called before the signal state is reset.
void EmttSignalChartChanged(SEmttSignalState &state,const bool writeJournal)
  {
   if(!state.plan.active)
      return;
   EmttSignalEndPlan(state,EMTT_PLAN_RESULT_CHART,state.lastClose,
                     state.lastSequence,state.lastBarTime,false,
                     writeJournal);
   state.signal=0;
   state.previousSignal=0;
   state.justEnded=false;
   state.waitReason=EMTT_SIG_WAIT_NONE;
   state.waitSide=0;
   state.hasJournaledSignal=false;
   state.journaledSignal=0;
   state.hasJournaledWait=false;
   state.journaledWaitReason=EMTT_SIG_WAIT_NONE;
  }

//+------------------------------------------------------------------+
//| 17.8 the plan-start journal lines: the signal line carries the   |
//| confidence, the plan line carries the fixed levels and their     |
//| sources.                                                          |
//+------------------------------------------------------------------+
void EmttSignalJournalPlanStart(SEmttSignalState &state,
                                const int spreadPts,
                                const datetime barTime,
                                const bool writeJournal)
  {
   if(!writeJournal || !state.plan.active)
      return;
   const int side=state.plan.side;
   const string bufferText=DoubleToString(EMTT_PLAN_STOP_BUFFER_ATR,1);
   PrintFormat("Emtt | Signal %s | confidence %d%% | %s, bar %d%% | bar %s",
               EmttPlanSideName(side),state.confidence,
               EmttSignalMoodWord(state.mood),state.moodBar,
               TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   PrintFormat("Emtt | Plan %s | confidence %d%% | entry %s (%s) | stop %s (%s %s%s ATR) | target %s (%s) | RR 1:%s | expected %s | spread %d pts | bar %s",
               EmttPlanSideName(side),state.confidence,
               DoubleToString(state.plan.entry,state.digits),
               state.plan.entrySource,
               DoubleToString(state.plan.stop,state.digits),
               state.plan.stopSource,(side>0 ? "-" : "+"),bufferText,
               DoubleToString(state.plan.target,state.digits),
               state.plan.targetSource,
               DoubleToString(state.plan.riskReward,1),
               state.plan.duration,spreadPts,
               TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   state.hasJournaledSignal=true;
   state.journaledSignal=state.signal;
   state.hasJournaledWait=false;
   state.journaledWaitReason=EMTT_SIG_WAIT_NONE;
  }

//+------------------------------------------------------------------+
//| One closed candle of the signal engine (17.3, 17.6, 17.7). The  |
//| signal changes only at a candle close, with no extra candles.    |
//| barHigh / barLow / barClose are the newly closed candle; the     |
//| forming candle is never read. Called from the closed-bar paths   |
//| only - never on a tick.                                           |
//+------------------------------------------------------------------+
void EmttSignalAdvance(SEmttSignalState &state,
                       const SEmttSupertrendState &st,
                       const SEmttSmcState &smc,
                       const SEmttVolumeFlowState &vf,
                       const SEmttMtfState &mtf,
                       const EEmttRegime mood,
                       const double atr,
                       const double barHigh,
                       const double barLow,
                       const double barClose,
                       const double bid,
                       const double ask,
                       const int spreadPts,
                       const ENUM_TIMEFRAMES timeframe,
                       const long sequence,
                       const datetime barTime,
                       const int digits,
                       const double point,
                       const bool writeJournal)
  {
   state.initialized=true;
   state.lastClose=barClose;
   state.lastBarTime=barTime;
   state.lastSequence=sequence;
   state.digits=digits;
   state.point=point;
   state.mood=mood;
   state.moodBar=EmttSignalMoodBar(mood);
   state.justEnded=false;

   const bool ready=(EmttSignalViewsReady(st,smc,vf,mtf) &&
                     state.moodBar>0 && EmttSigValidPositive(atr));
   if(!ready)
     {
      // No partial confidence is ever shown (17.2 rule 4).
      state.viewsReady=false;
      state.combined=0.0;
      state.confidence=-1;
      state.signal=0;
      state.previousSignal=0;
      state.waitReason=EMTT_SIG_WAIT_NONE;
      state.waitSide=0;
      EmttPlanReset(state.plan);
      state.hasJournaledSignal=false;
      state.journaledSignal=0;
      state.hasJournaledWait=false;
      state.journaledWaitReason=EMTT_SIG_WAIT_NONE;
      return;
     }
   state.viewsReady=true;
   state.combined=EmttSignalCombined(st,smc,vf,mtf);
   state.confidence=EmttSignalConfidenceNumber(state.combined);
   const int number=state.confidence;
   const int barLevel=state.moodBar;
   const int keepLevel=barLevel-EMTT_SIG_STAY_MARGIN;
   const bool wasShowing=(state.previousSignal!=0);

   //--- Plan lifecycle (17.7): the newly closed candle against the
   //--- fixed levels. A candle reaches a level when the level lies
   //--- between its low and high; spread is not added. Checks use only
   //--- candles that closed after the plan started, so the candle that
   //--- started the plan is never checked here.
   if(state.plan.active)
     {
      const bool touchesEntry=(barLow<=state.plan.entry &&
                               barHigh>=state.plan.entry);
      const bool touchesStop=(barLow<=state.plan.stop &&
                              barHigh>=state.plan.stop);
      const bool touchesTarget=(barLow<=state.plan.target &&
                                barHigh>=state.plan.target);
      const int touched=(touchesEntry ? 1 : 0)+(touchesStop ? 1 : 0)+
                        (touchesTarget ? 1 : 0);
      const bool shared=(touched>1);
      if(state.plan.status==EMTT_PLAN_PENDING)
        {
         // One candle, more than one level: the worse result counts,
         // stop reached > cancelled > missed > target reached.
         if(touchesStop)
            EmttSignalEndPlan(state,
                              (touchesEntry ? EMTT_PLAN_RESULT_STOP
                                            : EMTT_PLAN_RESULT_CANCELLED),
                              state.plan.stop,sequence,barTime,shared,
                              writeJournal);
         else if(touchesTarget)
            EmttSignalEndPlan(state,EMTT_PLAN_RESULT_MISSED,
                              state.plan.target,sequence,barTime,shared,
                              writeJournal);
         else if(touchesEntry)
           {
            // A pending plan becomes active on the candle that reaches
            // its order-block edge.
            state.plan.status=EMTT_PLAN_ACTIVE;
            if(writeJournal)
               PrintFormat("Emtt | Plan %s | entry reached | %s | bar %s",
                           EmttPlanSideName(state.plan.side),
                           DoubleToString(state.plan.entry,state.digits),
                           TimeToString(barTime,TIME_DATE|TIME_MINUTES));
           }
        }
      else
        {
         if(touchesStop)
            EmttSignalEndPlan(state,EMTT_PLAN_RESULT_STOP,state.plan.stop,
                              sequence,barTime,shared,writeJournal);
         else if(touchesTarget)
            EmttSignalEndPlan(state,EMTT_PLAN_RESULT_TARGET,
                              state.plan.target,sequence,barTime,shared,
                              writeJournal);
        }
     }

   //--- The signal gate (17.3), judged on every closed candle.
   if(state.plan.active)
     {
      // A showing BUY or SELL stays while its own number is at least
      // bar - 5; entering needs the bar, staying needs bar - 5.
      const int sideNumber=(state.plan.side>0 ?
                            (state.combined>0.0 ? number : 0) :
                            (state.combined<0.0 ? number : 0));
      if(sideNumber>=keepLevel)
        {
         state.signal=state.plan.side;
         state.waitReason=EMTT_SIG_WAIT_NONE;
         state.waitSide=0;
        }
      else
         EmttSignalEndPlan(state,EMTT_PLAN_RESULT_SIGNAL,barClose,sequence,
                           barTime,false,writeJournal);
     }
   if(!state.plan.active)
     {
      const int gateSide=(state.combined>0.0 ? EMTT_PLAN_SIDE_BUY :
                          (state.combined<0.0 ? EMTT_PLAN_SIDE_SELL : 0));
      const bool gateOpen=(gateSide!=0 && number>=barLevel);
      EEmttPlanFail fail=EMTT_PLAN_FAIL_NONE;
      SEmttTradePlan plan;
      EmttPlanReset(plan);
      if(gateOpen)
         EmttPlanBuild(plan,gateSide,smc,vf,st,atr,barClose,bid,ask,mood,
                       timeframe,fail);
      if(gateOpen && fail==EMTT_PLAN_FAIL_NONE && !state.justEnded)
        {
         // A plan starts when a BUY or SELL first appears and passes
         // its checks; its levels are fixed from here (17.2 rule 5).
         plan.startSequence=sequence;
         plan.startBarTime=barTime;
         plan.startClose=barClose;
         state.plan=plan;
         state.signal=gateSide;
         state.waitReason=EMTT_SIG_WAIT_NONE;
         state.waitSide=0;
         EmttSignalJournalPlanStart(state,spreadPts,barTime,writeJournal);
        }
      else
        {
         // WAIT, one reason at a time, in the 17.6 order. The candle
         // that ended a plan never starts one, so a passing gate on
         // that candle falls through to the last reason.
         state.signal=0;
         if(wasShowing && number<keepLevel)
           {
            state.waitReason=EMTT_SIG_WAIT_BELOW_KEEP;
            state.waitSide=state.previousSignal;
           }
         else if(number<barLevel)
           {
            state.waitReason=EMTT_SIG_WAIT_BELOW_BAR;
            state.waitSide=0;
           }
         else if(fail==EMTT_PLAN_FAIL_NO_TARGET)
           {
            state.waitReason=EMTT_SIG_WAIT_NO_TARGET;
            state.waitSide=0;
           }
         else if(fail==EMTT_PLAN_FAIL_STOP_FAR)
           {
            state.waitReason=EMTT_SIG_WAIT_STOP_FAR;
            state.waitSide=0;
           }
         else if(fail==EMTT_PLAN_FAIL_NO_SWING)
           {
            state.waitReason=EMTT_SIG_WAIT_NO_SWING;
            state.waitSide=0;
           }
         else
           {
            state.waitReason=EMTT_SIG_WAIT_JUST_ENDED;
            state.waitSide=0;
           }
        }
     }

   //--- Journal (17.8): state changes, plan events and WAIT reason
   //--- changes only. A WAIT that continues with the same reason, the
   //--- per-candle confidence values and quiet candles write nothing.
   if(writeJournal && state.viewsReady)
     {
      if(!state.hasJournaledSignal || state.journaledSignal!=state.signal)
        {
         if(state.signal!=0)
           {
            // Already journaled with the plan start; this branch covers
            // a signal that appears without a journaled plan line.
            PrintFormat("Emtt | Signal %s | confidence %d%% | %s, bar %d%% | bar %s",
                        EmttPlanSideName(state.signal),number,
                        EmttSignalMoodWord(mood),barLevel,
                        TimeToString(barTime,TIME_DATE|TIME_MINUTES));
           }
         else
            PrintFormat("Emtt | Signal WAIT | %s | bar %s",
                        EmttSignalWaitDetail(state),
                        TimeToString(barTime,TIME_DATE|TIME_MINUTES));
         state.hasJournaledSignal=true;
         state.journaledSignal=state.signal;
         if(state.signal==0)
           {
            state.hasJournaledWait=true;
            state.journaledWaitReason=state.waitReason;
           }
         else
           {
            state.hasJournaledWait=false;
            state.journaledWaitReason=EMTT_SIG_WAIT_NONE;
           }
        }
      else if(state.signal==0 && state.hasJournaledWait &&
              state.journaledWaitReason!=state.waitReason)
        {
         PrintFormat("Emtt | Signal WAIT | reason changed: %s | bar %s",
                     EmttSignalWaitBare(state),
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
         state.journaledWaitReason=state.waitReason;
        }
     }

   state.previousSignal=state.signal;
  }

#endif // EMTT_SIGNAL_MQH
