//+------------------------------------------------------------------+
//|                                              Emtt_ParamOpt.mqh   |
//| Phase 9: confidence-bar evidence only (Emtt.md 23.4-23.8)         |
//| Pure logic: no file calls, orders, chart, handles, or clock.      |
//| Measurement and management parameters are never adjusted here.  |
//| ASCII source only; a private paper idea is never a signal/ticket.|
//+------------------------------------------------------------------+
#ifndef EMTT_PARAMOPT_MQH
#define EMTT_PARAMOPT_MQH

#include "Emtt_ParamFile.mqh"
#include "Emtt_Learning.mqh"

#define EMTT_POPT_MIN_SAMPLES 20
#define EMTT_POPT_NEAR_BAND 10
#define EMTT_POPT_LOOSE 0.05
#define EMTT_POPT_TIGHT 0.20

// The only approved confidence bars, in step order: 60 / 70 / 75.
int EmttParamBarStep(const int bar,const int direction)
  {
   const int candidates[3]={60,70,75};
   for(int i=0;i<3;i++)
      if(candidates[i]==bar)
         return candidates[(int)MathMax(0,(int)MathMin(2,i+direction))];
   return bar;
  }

struct SEmttParamAccepted
  {
   string key;
   string tfName;
   int    mood;
   int    label;
   datetime resultTime;
  };

struct SEmttParamOptState
  {
   bool enabled;           // input captured once at init
   bool replaying;         // no evidence enters during any replay
   bool liveCandle;        // set only by BeginCandle on the live path
   datetime lastLiveBarTime;
   SEmttParamFileState file;
   // A trade can outlive its chart timeframe. Its evidence goes only to
   // that original sibling record; it is never pooled into this chart.
   SEmttParamFileState carriedFile;
   int effectiveBars[EMTT_POPT_CELLS];
   bool positionFrozen;
   int frozenBar;          // entry threshold, using the existing EA snapshot
   SEmttTradePlan nearPlan;
   int nearMood;           // captured at start, never revised
   int nearConfidence;
   int nearBar;
   int nearDigits;
   double nearPoint;
   datetime nearLastBarTime;
   // Broker outcomes may arrive between closes. Queue for the next live
   // close; deinit can durably fold already-labeled outcomes, without
   // making a decision or evaluating a near idea. Never from a replay.
   SEmttParamAccepted pending[EMTT_LEARN_CAP];
   int pendingCount;
   string seen[EMTT_LEARN_CAP];
   int seenCount;
   int seenNext;
  };

void EmttParamOptReset(SEmttParamOptState &state,const bool enabled)
  {
   state.enabled=enabled;
   state.replaying=false;
   state.liveCandle=false;
   state.lastLiveBarTime=0;
   EmttParamFileReset(state.file);
   EmttParamFileReset(state.carriedFile);
   for(int i=0;i<EMTT_POPT_CELLS;i++)
      state.effectiveBars[i]=EmttParamBaseBar(i);
   state.positionFrozen=false;
   state.frozenBar=0;
   EmttPlanReset(state.nearPlan);
   state.nearMood=0;
   state.nearConfidence=0;
   state.nearBar=0;
   state.nearDigits=0;
   state.nearPoint=0.0;
   state.nearLastBarTime=0;
   state.pendingCount=0;
   state.seenCount=0;
   state.seenNext=0;
  }

void EmttParamOptUseLoadedBars(SEmttParamOptState &state)
  {
   for(int i=0;i<EMTT_POPT_CELLS;i++)
      state.effectiveBars[i]=state.file.cells[i].bar;
  }

void EmttParamOptFreezeAtEntry(SEmttParamOptState &state,const int entryBar)
  {
   if(!state.enabled || state.positionFrozen || !EmttParamBarApproved(entryBar))
      return;
   state.positionFrozen=true;
   state.frozenBar=entryBar;
  }

int EmttParamOptBar(const SEmttParamOptState &state,const EEmttRegime mood)
  {
   if(!state.enabled || !state.file.loaded || EmttSignalMoodBar(mood)<=0)
      return 0;
   if(state.positionFrozen && state.frozenBar>0) return state.frozenBar;
   return state.effectiveBars[EmttLearnMoodIndex(mood)];
  }

bool EmttParamOptBeginCandle(SEmttParamOptState &state,const datetime barTime,
                            const bool positionOpen,const int entryBar)
  {
   if(!state.enabled || state.replaying || !state.file.loaded ||
      barTime<=0 || barTime<=state.lastLiveBarTime)
      return false;
   if(positionOpen)
      EmttParamOptFreezeAtEntry(state,entryBar);
   else
     {
      state.positionFrozen=false;
      state.frozenBar=0;
      // Desired bars were written at the preceding decision. They take
      // effect here, never on the candle that produced that evidence.
      EmttParamOptUseLoadedBars(state);
     }
   state.lastLiveBarTime=barTime;
   state.liveCandle=true;
   return true;
  }

bool EmttParamOptQueueAccepted(SEmttParamOptState &state,
                              const SEmttLearnTicket &ticket,const string symbol,
                              const string tfName,const datetime resultTime)
  {
   if(!state.enabled || state.replaying || !state.file.loaded ||
      symbol!=state.file.symbol || !ticket.used ||
      ticket.startBarTime<=0 || (ticket.side!=1 && ticket.side!=-1) ||
      ticket.mood<0 || ticket.mood>=4 ||
      (tfName!="M5" && tfName!="M15" && tfName!="M30"))
      return false;
   const int label=EmttLearnLabelOf(ticket);
   if(label<0) return false;
   const string key=tfName+"_"+IntegerToString((long)ticket.startBarTime)+
                    "_"+IntegerToString(ticket.side);
   for(int i=0;i<state.seenCount;i++) if(state.seen[i]==key) return false;
   for(int i=0;i<state.pendingCount;i++)
      if(state.pending[i].key==key) return false;
   if(state.pendingCount>=EMTT_LEARN_CAP) return false;
   const int slot=state.pendingCount++;
   state.pending[slot].key=key;
   state.pending[slot].tfName=tfName;
   state.pending[slot].mood=ticket.mood;
   state.pending[slot].label=label;
   state.pending[slot].resultTime=resultTime;
   return true;
  }

void EmttParamOptRemember(SEmttParamOptState &state,const string key)
  {
   state.seen[state.seenNext]=key;
   state.seenNext=(state.seenNext+1)%EMTT_LEARN_CAP;
   if(state.seenCount<EMTT_LEARN_CAP) state.seenCount++;
  }

void EmttParamOptAddAccepted(SEmttParamCell &cell,const int label)
  {
   if(label==1) cell.aW++;
   else if(label==0) cell.aL++;
  }

// One decision per cell per candle. Scaled cross-products avoid rate
// subtraction at the inclusive 5/20-percent edges. Percent constants stay
// the approved 0.05 / 0.20, not tuning inputs.
bool EmttParamOptDecideCell(SEmttParamCell &cell,const int mood,
                            const datetime barTime)
  {
   const long accepted=cell.aW+cell.aL;
   const long near=cell.nW+cell.nL;
   if(accepted<EMTT_POPT_MIN_SAMPLES || near<EMTT_POPT_MIN_SAMPLES)
      return false;
   const int loosePercent=(int)MathRound(100.0*EMTT_POPT_LOOSE);
   const int tightPercent=(int)MathRound(100.0*EMTT_POPT_TIGHT);
   const double lhs=100.0*(double)cell.nW*(double)accepted;
   const double loose=(100.0*(double)cell.aW-
                        (double)loosePercent*(double)accepted)*(double)near;
   const double tight=(100.0*(double)cell.aW-
                        (double)tightPercent*(double)accepted)*(double)near;
   int direction=0;
   if(lhs>=loose) direction=-1;
   else if(lhs<=tight) direction=1;
   else return false;      // neutral evidence keeps accumulating, silently

   const int previous=cell.bar;
   cell.bar=EmttParamBarStep(previous,direction);
   const int rateA=(int)MathRound(100.0*(double)cell.aW/(double)accepted);
   const int rateN=(int)MathRound(100.0*(double)cell.nW/(double)near);
   if(cell.bar!=previous)
      PrintFormat("Emtt | Param bar moved | %s %d -> %d | accepted %I64d/%I64d (%d%%), near %I64d/%I64d (%d%%) | bar %s",
                  EmttLearnMoodWord(mood),previous,cell.bar,cell.aW,cell.aL,
                  rateA,cell.nW,cell.nL,rateN,EmttLearnTimeText(barTime));
   else
      PrintFormat("Emtt | Param bar held | %s at the approved limit %d | accepted %I64d/%I64d (%d%%), near %I64d/%I64d (%d%%) | bar %s",
                  EmttLearnMoodWord(mood),previous,cell.aW,cell.aL,rateA,
                  cell.nW,cell.nL,rateN,EmttLearnTimeText(barTime));
   cell.moves++;
   cell.aW=0;
   cell.aL=0;
   cell.nW=0;
   cell.nL=0;
   return true;
  }

bool EmttParamOptDecideFile(SEmttParamFileState &file,const datetime barTime)
  {
   if(file.readPending || file.readOnly) return false;
   bool decision=false;
   for(int i=0;i<EMTT_POPT_CELLS;i++)
      if(EmttParamOptDecideCell(file.cells[i],i,barTime)) decision=true;
   return decision;
  }

// No Summary, ticket, model, or real signal event is emitted by this end.
bool EmttParamOptEndNear(SEmttParamOptState &state,const int result,
                         const double exitPrice,const long sequence,
                         const datetime barTime,const bool shared)
  {
   if(!state.enabled || !state.nearPlan.active) return false;
   const SEmttTradePlan plan=state.nearPlan;
   SEmttParamCell cell=state.file.cells[state.nearMood];
   const bool labeled=(result==EMTT_LEARN_RESULT_TARGET ||
                       result==EMTT_LEARN_RESULT_STOP);
   if(labeled && !state.replaying && state.liveCandle)
     {
      if(result==EMTT_LEARN_RESULT_TARGET) cell.nW++;
      else cell.nL++;
      state.file.cells[state.nearMood]=cell;
     }
   const int points=(state.nearPoint>0.0 ?
      (int)MathRound((exitPrice-plan.entry)*plan.side/state.nearPoint) : 0);
   const long candles=(long)MathMax(0,sequence-plan.startSequence);
   PrintFormat("Emtt | Near miss result | %s | %s%d pts | %I64d candles | %s near %I64d/%I64d%s | bar %s",
               EmttLearnResultWord(result),(points>=0 ? "+" : ""),points,
               candles,EmttLearnMoodWord(state.nearMood),cell.nW,cell.nL,
               (shared ? " | shared candle" : ""),EmttLearnTimeText(barTime));
   EmttPlanReset(state.nearPlan);
   return(labeled && !state.replaying && state.liveCandle);
  }

// 17.7 paper lifecycle verbatim in priority: stop > cancelled > missed
// > target, then the side's stay margin. The start candle is never watched.
bool EmttParamOptWatchNear(SEmttParamOptState &state,
                           const SEmttSignalState &signal,
                           const double high,const double low,const double close,
                           const long sequence,const datetime barTime)
  {
   if(!state.enabled || state.replaying || !state.liveCandle ||
      !state.nearPlan.active || barTime<=state.nearPlan.startBarTime ||
      barTime<=state.nearLastBarTime) return false;
   state.nearLastBarTime=barTime;
   // The real engine resets an idea before price checks when its four
   // views are unavailable. Do not manufacture a label from that candle.
   if(!signal.viewsReady)
     {
      EmttParamOptEndNear(state,EMTT_LEARN_RESULT_CHART,close,sequence,barTime,false);
      return true;
     }
   const bool entry=(low<=state.nearPlan.entry && high>=state.nearPlan.entry);
   const bool stop=(low<=state.nearPlan.stop && high>=state.nearPlan.stop);
   const bool target=(low<=state.nearPlan.target && high>=state.nearPlan.target);
   const bool shared=((entry ? 1 : 0)+(stop ? 1 : 0)+(target ? 1 : 0)>1);
   int result=EMTT_LEARN_RESULT_NONE;
   double exitPrice=close;
   if(state.nearPlan.status==EMTT_PLAN_PENDING)
     {
      if(stop)
        {
         result=(entry ? EMTT_LEARN_RESULT_STOP : EMTT_LEARN_RESULT_CANCELLED);
         exitPrice=state.nearPlan.stop;
        }
      else if(target) { result=EMTT_LEARN_RESULT_MISSED; exitPrice=state.nearPlan.target; }
      else if(entry) state.nearPlan.status=EMTT_PLAN_ACTIVE;
     }
   else
     {
      if(stop) { result=EMTT_LEARN_RESULT_STOP; exitPrice=state.nearPlan.stop; }
      else if(target) { result=EMTT_LEARN_RESULT_TARGET; exitPrice=state.nearPlan.target; }
     }
   if(result!=EMTT_LEARN_RESULT_NONE)
     {
      EmttParamOptEndNear(state,result,exitPrice,sequence,barTime,shared);
      return true;
     }
   const int number=(signal.combined*state.nearPlan.side>0.0 ? signal.confidence : 0);
   if(number<signal.moodBar-EMTT_SIG_STAY_MARGIN)
     {
      EmttParamOptEndNear(state,EMTT_LEARN_RESULT_SIGNAL,close,sequence,barTime,false);
      return true;
     }
   return false;
  }

void EmttParamOptConsiderNear(SEmttParamOptState &state,
                              const SEmttSignalState &signal,
                              const SEmttSupertrendState &st,
                              const SEmttSmcState &smc,
                              const SEmttVolumeFlowState &vf,
                              const double atr,const double close,
                              const double bid,const double ask,
                              const ENUM_TIMEFRAMES timeframe,
                              const long sequence,const datetime barTime)
  {
   if(!state.enabled || state.replaying || !state.liveCandle ||
      signal.plan.active || signal.justEnded || !signal.viewsReady ||
      signal.moodBar<=0 || signal.confidence>=signal.moodBar ||
      signal.confidence<signal.moodBar-EMTT_POPT_NEAR_BAND)
      return;
   const int side=(signal.combined>0.0 ? 1 : (signal.combined<0.0 ? -1 : 0));
   if(side==0) return;
   SEmttTradePlan plan;
   EEmttPlanFail fail=EMTT_PLAN_FAIL_NONE;
   if(!EmttPlanBuild(plan,side,smc,vf,st,atr,close,bid,ask,signal.mood,
                     timeframe,fail) || fail!=EMTT_PLAN_FAIL_NONE)
      return;
   const bool replacing=state.nearPlan.active;
   const string previous=(replacing ?
      " | previous "+EmttPlanSideName(state.nearPlan.side)+" from "+
      EmttLearnTimeText(state.nearPlan.startBarTime) : "");
   plan.startSequence=sequence;
   plan.startBarTime=barTime;
   plan.startClose=close;
   state.nearPlan=plan;
   state.nearMood=EmttLearnMoodIndex(signal.mood);
   state.nearConfidence=signal.confidence;
   state.nearBar=signal.moodBar;
   state.nearDigits=signal.digits;
   state.nearPoint=signal.point;
   state.nearLastBarTime=barTime;
   PrintFormat("Emtt | Near miss %s | %s | confidence %d%%, bar %d%% | entry %s | stop %s | target %s | RR 1:%s%s | bar %s",
               (replacing ? "replaced" : "started"),EmttPlanSideName(side),
               signal.confidence,signal.moodBar,DoubleToString(plan.entry,signal.digits),
               DoubleToString(plan.stop,signal.digits),DoubleToString(plan.target,signal.digits),
               DoubleToString(plan.riskReward,1),previous,EmttLearnTimeText(barTime));
  }

// Called once after the real signal consumed its events. A near result
// owns the same next-candle rule as a real plan: no replacement on its end.
void EmttParamOptAdvanceNear(SEmttParamOptState &state,
                             const SEmttSignalState &signal,
                             const SEmttSupertrendState &st,
                             const SEmttSmcState &smc,
                             const SEmttVolumeFlowState &vf,
                             const double atr,const double high,const double low,
                             const double close,const double bid,const double ask,
                             const ENUM_TIMEFRAMES timeframe,const long sequence,
                             const datetime barTime)
  {
   if(!state.enabled || state.replaying || !state.liveCandle) return;
   if(EmttParamOptWatchNear(state,signal,high,low,close,sequence,barTime)) return;
   EmttParamOptConsiderNear(state,signal,st,smc,vf,atr,close,bid,ask,
                            timeframe,sequence,barTime);
  }

#endif // EMTT_PARAMOPT_MQH
