//+------------------------------------------------------------------+
//|                                            Emtt_TradePlan.mqh    |
//| Phase 6: Entry, Stop, Target, Risk:Reward, Expected Duration     |
//| Spec: Emtt.md sections 17.4-17.5                                 |
//+------------------------------------------------------------------+
//| Pure functions of the published readings and the ATR. This       |
//| header reads no chart, no panel and no EA global; every level    |
//| comes from a published reading (13.3, 13.5, 13.6, 13.7, 15.5,    |
//| 15.7) or from the ATR - nothing is typed in or fabricated.       |
//| Nothing here sends, modifies, closes or deletes anything.        |
//| ASCII source only (17.2 rule 9): every glyph would be an escape. |
//+------------------------------------------------------------------+
#ifndef EMTT_TRADEPLAN_MQH
#define EMTT_TRADEPLAN_MQH

#include "Emtt_Regime.mqh"
#include "Emtt_Supertrend.mqh"
#include "Emtt_SMC.mqh"
#include "Emtt_VolumeFlow.mqh"

//--- 17.5 parameter rows (Management / Strictness class) ------------
//--- None of them is a lookback, so Layer 2 scales none of them. -----
#define EMTT_PLAN_STOP_BUFFER_ATR  0.5
#define EMTT_PLAN_STOP_MIN_ATR     1.0
#define EMTT_PLAN_STOP_MAX_ATR     3.0
#define EMTT_PLAN_ENTRY_REACH_ATR  2.0
#define EMTT_PLAN_SPEED_FLOOR      0.2
#define EMTT_PLAN_DURATION_LOW     0.5
#define EMTT_PLAN_DURATION_HIGH    1.5
#define EMTT_PLAN_RR_TREND         1.5
#define EMTT_PLAN_RR_OTHER         2.0

//--- plan identity ---------------------------------------------------
#define EMTT_PLAN_SIDE_BUY     1
#define EMTT_PLAN_SIDE_SELL   -1
#define EMTT_PLAN_ENTRY_MARKET 0
#define EMTT_PLAN_ENTRY_BLOCK  1
#define EMTT_PLAN_PENDING      0
#define EMTT_PLAN_ACTIVE       1

// Why a plan could not be built (17.4); each maps to a 17.6 WAIT reason.
enum EEmttPlanFail
  {
   EMTT_PLAN_FAIL_NONE=0,
   EMTT_PLAN_FAIL_NO_SWING,
   EMTT_PLAN_FAIL_STOP_FAR,
   EMTT_PLAN_FAIL_NO_TARGET
  };

//+------------------------------------------------------------------+
//| One trade idea. The levels are fixed while the plan lasts        |
//| (17.2 rule 5); the signal module owns the lifecycle.             |
//+------------------------------------------------------------------+
struct SEmttTradePlan
  {
   bool            active;
   int             side;          // +1 BUY / -1 SELL
   int             entryKind;     // market price / order block edge
   int             status;        // pending / active
   double          entry;
   double          stop;
   double          target;
   double          riskReward;
   string          entrySource;   // journal wording only
   string          stopSource;
   string          targetSource;
   string          duration;      // fixed Expected Duration text
   long            startSequence;
   datetime        startBarTime;
   double          startClose;
  };

//+------------------------------------------------------------------+
//| Small local helpers. No EA helper is called from this component. |
//+------------------------------------------------------------------+
bool EmttPlanValid(const double value)
  {
   return(MathIsValidNumber(value) && value!=EMPTY_VALUE);
  }

bool EmttPlanValidPositive(const double value)
  {
   return(EmttPlanValid(value) && value>0.0);
  }

void EmttPlanReset(SEmttTradePlan &plan)
  {
   plan.active=false;
   plan.side=0;
   plan.entryKind=EMTT_PLAN_ENTRY_MARKET;
   plan.status=EMTT_PLAN_PENDING;
   plan.entry=0.0;
   plan.stop=0.0;
   plan.target=0.0;
   plan.riskReward=0.0;
   plan.entrySource="";
   plan.stopSource="";
   plan.targetSource="";
   plan.duration="";
   plan.startSequence=-1;
   plan.startBarTime=0;
   plan.startClose=0.0;
  }

string EmttPlanSideName(const int side)
  {
   return(side>0 ? "BUY" : "SELL");
  }

// 17.5 row g: 1.5 in a clear trend, 2.0 in the other moods.
double EmttPlanMinRiskReward(const EEmttRegime mood)
  {
   if(mood==EMTT_REGIME_TRENDING_BULLISH || mood==EMTT_REGIME_TRENDING_BEARISH)
      return EMTT_PLAN_RR_TREND;
   return EMTT_PLAN_RR_OTHER;
  }

// Minutes per candle from the chart timeframe: M5 = 5, M15 = 15, M30 = 30.
int EmttPlanMinutesPerCandle(const ENUM_TIMEFRAMES timeframe)
  {
   const int seconds=PeriodSeconds(timeframe);
   if(seconds<60)
      return 0;
   return seconds/60;
  }

// 17.4 Expected Duration: a 0.5x-1.5x band around the candle estimate,
// minutes (nearest 5) under two hours, whole hours to three days, and
// "> 3 days" beyond. MathRound is half away from zero, i.e. halves up.
string EmttPlanDurationText(const double candles,const ENUM_TIMEFRAMES timeframe)
  {
   const int minutesPerCandle=EmttPlanMinutesPerCandle(timeframe);
   if(minutesPerCandle<=0 || !EmttPlanValidPositive(candles))
      return "--";
   const double minutes=candles*(double)minutesPerCandle;
   if(minutes<120.0)
     {
      const int low=(int)MathRound(EMTT_PLAN_DURATION_LOW*minutes/5.0)*5;
      const int high=(int)MathRound(EMTT_PLAN_DURATION_HIGH*minutes/5.0)*5;
      return "~"+IntegerToString(low)+"-"+IntegerToString(high)+" min";
     }
   if(minutes<=4320.0)
     {
      const double hours=minutes/60.0;
      const int low=(int)MathRound(EMTT_PLAN_DURATION_LOW*hours);
      const int high=(int)MathRound(EMTT_PLAN_DURATION_HIGH*hours);
      return "~"+IntegerToString(low)+"-"+IntegerToString(high)+" hours";
     }
   return "> 3 days";
  }

//+------------------------------------------------------------------+
//| 17.4 the plan builder. The rules are written for BUY; SELL is    |
//| the exact mirror: above and below swap, and Ask and Bid swap.    |
//| Returns false with `fail` set when the idea must be skipped.     |
//+------------------------------------------------------------------+
bool EmttPlanBuild(SEmttTradePlan &plan,
                   const int side,
                   const SEmttSmcState &smc,
                   const SEmttVolumeFlowState &vf,
                   const SEmttSupertrendState &st,
                   const double atr,
                   const double close,
                   const double bid,
                   const double ask,
                   const EEmttRegime mood,
                   const ENUM_TIMEFRAMES timeframe,
                   EEmttPlanFail &fail)
  {
   EmttPlanReset(plan);
   fail=EMTT_PLAN_FAIL_NONE;
   if(side!=EMTT_PLAN_SIDE_BUY && side!=EMTT_PLAN_SIDE_SELL)
      return false;
   if(!EmttPlanValidPositive(atr) || !EmttPlanValid(close) ||
      !EmttPlanValid(bid) || !EmttPlanValid(ask))
      return false;

   const double dealing=(side>0 ? ask : bid);
   const double minRR=EmttPlanMinRiskReward(mood);

   //--- Entry: the same-way order block's near edge when it lies more
   //--- than 0 and at most 2.0 ATR away from the close (17.5 row d);
   //--- otherwise the dealing price, read at the evaluation.
   plan.entry=dealing;
   plan.entryKind=EMTT_PLAN_ENTRY_MARKET;
   plan.entrySource="market price";
   double blockFarEdge=0.0;
   if(smc.hasOrderBlock && smc.bias==side &&
      smc.orderBlockBullish==(side>0))
     {
      const double reach=(side>0 ? close-smc.orderBlockNearEdge
                                 : smc.orderBlockNearEdge-close);
      if(reach>0.0 && reach<=EMTT_PLAN_ENTRY_REACH_ATR*atr)
        {
         plan.entry=smc.orderBlockNearEdge;
         plan.entryKind=EMTT_PLAN_ENTRY_BLOCK;
         plan.entrySource="order block edge";
         blockFarEdge=(side>0 ? smc.orderBlockLow : smc.orderBlockHigh);
        }
     }

   //--- Stop (the author's rule): the further of the newest confirmed
   //--- turning point and the block's far edge (only when Entry came
   //--- from that block), plus 0.5 ATR, widened out to 1.0 ATR, skipped
   //--- beyond 3.0 ATR. Each candidate is used only on its own side of
   //--- Entry.
   double reference=0.0;
   bool hasReference=false;
   string stopSource="";
   const bool hasSwing=(side>0 ? smc.newestLowSlot>=0
                               : smc.newestHighSlot>=0);
   const double swingLevel=(side>0 ? smc.newestLowLevel
                                   : smc.newestHighLevel);
   if(hasSwing &&
      (side>0 ? swingLevel<plan.entry : swingLevel>plan.entry))
     {
      reference=swingLevel;
      hasReference=true;
      stopSource=(side>0 ? "swing low" : "swing high");
     }
   if(plan.entryKind==EMTT_PLAN_ENTRY_BLOCK && blockFarEdge!=0.0 &&
      (side>0 ? blockFarEdge<plan.entry : blockFarEdge>plan.entry) &&
      (!hasReference ||
       (side>0 ? blockFarEdge<reference : blockFarEdge>reference)))
     {
      reference=blockFarEdge;
      hasReference=true;
      stopSource="order block edge";
     }
   if(!hasReference)
     {
      fail=EMTT_PLAN_FAIL_NO_SWING;
      return false;
     }
   plan.stop=reference+(side>0 ? -EMTT_PLAN_STOP_BUFFER_ATR*atr
                               :  EMTT_PLAN_STOP_BUFFER_ATR*atr);
   if(MathAbs(plan.entry-plan.stop)<EMTT_PLAN_STOP_MIN_ATR*atr)
      plan.stop=plan.entry+(side>0 ? -EMTT_PLAN_STOP_MIN_ATR*atr
                                   :  EMTT_PLAN_STOP_MIN_ATR*atr);
   if(MathAbs(plan.entry-plan.stop)>EMTT_PLAN_STOP_MAX_ATR*atr)
     {
      fail=EMTT_PLAN_FAIL_STOP_FAR;
      return false;
     }
   plan.stopSource=stopSource;

   //--- Target (one only): the nearest candidate on the trade side of
   //--- Entry that gives at least the minimum Risk:Reward. Equal prices
   //--- keep the 17.4 order: FVG, pool, POC, VAH, VAL, naked POC.
   double candidatePrice[6];
   int candidatePriority[6];
   string candidateSource[6];
   int candidateCount=0;
   if(side>0 ? smc.hasGapAbove : smc.hasGapBelow)
     {
      candidatePrice[candidateCount]=(side>0 ? smc.gapAboveNearEdge
                                             : smc.gapBelowNearEdge);
      candidatePriority[candidateCount]=0;
      candidateSource[candidateCount]="fair value gap";
      candidateCount++;
     }
   if(side>0 ? smc.hasBuyPool : smc.hasSellPool)
     {
      candidatePrice[candidateCount]=(side>0 ? smc.buyPoolLevel
                                             : smc.sellPoolLevel);
      candidatePriority[candidateCount]=1;
      candidateSource[candidateCount]=(side>0 ? "buy-side pool"
                                               : "sell-side pool");
      candidateCount++;
     }
   if(vf.hasProfile)
     {
      candidatePrice[candidateCount]=vf.poc;
      candidatePriority[candidateCount]=2;
      candidateSource[candidateCount]="POC";
      candidateCount++;
      candidatePrice[candidateCount]=vf.vah;
      candidatePriority[candidateCount]=3;
      candidateSource[candidateCount]="VAH";
      candidateCount++;
      candidatePrice[candidateCount]=vf.val;
      candidatePriority[candidateCount]=4;
      candidateSource[candidateCount]="VAL";
      candidateCount++;
     }
   if(vf.priorPocAvailable && vf.priorPocNaked)
     {
      candidatePrice[candidateCount]=vf.priorPoc;
      candidatePriority[candidateCount]=5;
      candidateSource[candidateCount]="naked POC";
      candidateCount++;
     }

   bool found=false;
   double bestPrice=0.0,bestDistance=0.0;
   int bestPriority=0;
   double bestRR=0.0;
   string bestSource="";
   for(int c=0;c<candidateCount;c++)
     {
      const double price=candidatePrice[c];
      if(!(side>0 ? price>plan.entry : price<plan.entry))
         continue;
      const double rr=(side>0 ? (price-plan.entry)/(plan.entry-plan.stop)
                              : (plan.entry-price)/(plan.stop-plan.entry));
      if(rr<minRR)
         continue;
      const double distance=MathAbs(price-plan.entry);
      if(!found || distance<bestDistance ||
         (distance==bestDistance && candidatePriority[c]<bestPriority))
        {
         found=true;
         bestPrice=price;
         bestDistance=distance;
         bestPriority=candidatePriority[c];
         bestRR=rr;
         bestSource=candidateSource[c];
        }
     }
   if(!found)
     {
      fail=EMTT_PLAN_FAIL_NO_TARGET;
      return false;
     }
   plan.target=bestPrice;
   plan.riskReward=bestRR;
   plan.targetSource=bestSource;

   //--- Expected Duration: Supertrend speed (ATR per candle), floored,
   //--- then the 0.5x-1.5x band. The speed describes the trade's move
   //--- only while the Supertrend points the trade's way.
   double speed=0.0;
   if(st.direction==side && st.barsSinceFlip>0)
      speed=st.distanceATRs/(double)st.barsSinceFlip;
   if(speed<EMTT_PLAN_SPEED_FLOOR)
      speed=EMTT_PLAN_SPEED_FLOOR;
   const double candles=(MathAbs(plan.target-plan.entry)/atr)/speed;
   plan.duration=EmttPlanDurationText(candles,timeframe);

   plan.side=side;
   // A market-price Entry is active from the candle that started it; an
   // order-block edge stays pending until a candle reaches that edge.
   plan.status=(plan.entryKind==EMTT_PLAN_ENTRY_MARKET ? EMTT_PLAN_ACTIVE
                                                      : EMTT_PLAN_PENDING);
   plan.active=true;
   return true;
  }

#endif // EMTT_TRADEPLAN_MQH
