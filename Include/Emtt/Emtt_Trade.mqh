//+------------------------------------------------------------------+
//|                                               Emtt_Trade.mqh     |
//| Phase 8: pure decisions for live order and trade management      |
//| Spec: Emtt.md sections 21.2-21.14                                |
//+------------------------------------------------------------------+
//| This header reads no chart, sends no order, draws nothing and     |
//| writes no file. Broker interaction belongs to Emtt_TradeManager. |
//| ASCII source only: display dashes are escaped at runtime.        |
//+------------------------------------------------------------------+
#ifndef EMTT_TRADE_MQH
#define EMTT_TRADE_MQH

#include "Emtt_TradePlan.mqh"
#include "Emtt_Tier.mqh"

//--- 21.14 fixed management rows ------------------------------------
#define EMTT_TRADE_RISK                 1.0
#define EMTT_TRADE_BE_ATR               1.0
#define EMTT_TRADE_PARTIAL_PCT         50.0
#define EMTT_TRADE_SPREAD_MULT          2.0
#define EMTT_TRADE_SPREAD_SAMPLES      20
#define EMTT_TRADE_SPREAD_WINDOW      100
#define EMTT_NEWS_WINDOW_MIN           30
#define EMTT_NEWS_SIZE_HIGH             0.5
#define EMTT_NEWS_SIZE_MED              0.75
#define EMTT_NEWS_TRAIL_MULT            1.5
#define EMTT_TRAIL_BASE_M5              1.0
#define EMTT_TRAIL_BASE_M15             1.5
#define EMTT_TRAIL_BASE_M30             2.0
#define EMTT_TRAIL_CHANDELIER           2.5
#define EMTT_TRAIL_FRACTAL_BUFFER       0.5
#define EMTT_TRAIL_PHASE_HI             0.50
#define EMTT_TRAIL_PHASE_TOP            0.80
#define EMTT_TRADE_SIZE_CONF_90         1.5
#define EMTT_TRADE_SIZE_CONF_80         1.2
#define EMTT_TRADE_SIZE_CONF_70         1.0
#define EMTT_TRADE_SIZE_CONF_60         0.7
#define EMTT_TRAIL_CONF_85              1.0
#define EMTT_TRAIL_CONF_70              0.9
#define EMTT_TRAIL_CONF_55              0.7
#define EMTT_TRAIL_CONF_LOW             0.5
#define EMTT_TRAIL_REGIME_TRENDING      1.0
#define EMTT_TRAIL_REGIME_TRANSITION    0.8
#define EMTT_TRAIL_REGIME_VOLATILE      1.3
#define EMTT_TRAIL_REGIME_RANGING       0.6

// 21.3: the only two lot modes exposed to the user. The member comments are
// the input labels MetaEditor shows for the dropdown (Auto / Minimum).
enum ENUM_EMTT_LOT_MODE
  {
   EMTT_LOT_AUTO=0,     // Auto
   EMTT_LOT_MINIMUM=1   // Minimum
  };

enum EEmttTradeGateFailure
  {
   EMTT_TRADE_GATE_OK=0,
   EMTT_TRADE_GATE_AUTO_OFF,
   EMTT_TRADE_GATE_TERMINAL_OFF,
   EMTT_TRADE_GATE_MARKET_CLOSED,
   EMTT_TRADE_GATE_ALREADY_LIVE,
   EMTT_TRADE_GATE_SPREAD,
   EMTT_TRADE_GATE_MARGIN,
   EMTT_TRADE_GATE_BELOW_THRESHOLD   // Phase 11 (28.4)
  };

enum EEmttTradeTrailMethod
  {
   EMTT_TRAIL_METHOD_NONE=0,
   EMTT_TRAIL_METHOD_ATR,
   EMTT_TRAIL_METHOD_CHANDELIER,
   EMTT_TRAIL_METHOD_FRACTAL
  };

enum EEmttNewsImpact
  {
   EMTT_NEWS_IMPACT_NONE=0,
   EMTT_NEWS_IMPACT_LOW,
   EMTT_NEWS_IMPACT_MEDIUM,
   EMTT_NEWS_IMPACT_HIGH
  };

struct SEmttTradeGateInput
  {
   bool   autoTrading;
   bool   terminalAllowed;
   bool   accountAllowed;
   bool   marketOpen;
   bool   ownPending;
   bool   ownPosition;
   bool   spreadAllowed;
   bool   marginCheck;
   bool   marginFits;
   int    confidence;      // Phase 11: displayed confidence
   int    autoTradeAbove;  // Phase 11: "Auto-trade above (%)"
  };

struct SEmttTradeOrderPlan
  {
   bool   valid;
   bool   pending;
   int    side;
   int    orderType;
   double volume;
   double price;
   double stopLoss;
   double takeProfit;
   bool   stopLossSent;
   bool   takeProfitSent;
   bool   tp2Sent;
   int    timeInForce;
  };

struct SEmttTradeCandidate
  {
   double price;
   int    priority;
   string source;
  };

struct SEmttTradeTargetResult
  {
   bool   valid;
   bool   tp1Changed;
   bool   tp2Changed;
   double tp1;
   double tp2;
   string tp1Source;
   string tp2Source;
  };

struct SEmttTradeTrailResult
  {
   bool   valid;
   int    method;
   double profitFraction;
   double baseDistance;
   double rawDistance;
   double confidenceMultiplier;
   double regimeMultiplier;
   double newsMultiplier;
   double distance;
   double stop;
  };

bool EmttTradeValid(const double value)
  {
   return(MathIsValidNumber(value) && value!=EMPTY_VALUE);
  }

bool EmttTradeValidPositive(const double value)
  {
   return(EmttTradeValid(value) && value>0.0);
  }

string EmttTradeDash()
  {
   return "\x2014";
  }

//--- 21.4 ordered safety gate ---------------------------------------
EEmttTradeGateFailure EmttTradeGateFirstFailure(
   const SEmttTradeGateInput &gateInput)
  {
   if(!gateInput.autoTrading)
      return EMTT_TRADE_GATE_AUTO_OFF;
   if(!EmttTierAutoTradeAllowed(gateInput.confidence,
                                gateInput.autoTradeAbove))
      return EMTT_TRADE_GATE_BELOW_THRESHOLD;
   if(!gateInput.terminalAllowed || !gateInput.accountAllowed)
      return EMTT_TRADE_GATE_TERMINAL_OFF;
   if(!gateInput.marketOpen)
      return EMTT_TRADE_GATE_MARKET_CLOSED;
   if(gateInput.ownPending || gateInput.ownPosition)
      return EMTT_TRADE_GATE_ALREADY_LIVE;
   if(!gateInput.spreadAllowed)
      return EMTT_TRADE_GATE_SPREAD;
   if(gateInput.marginCheck && !gateInput.marginFits)
      return EMTT_TRADE_GATE_MARGIN;
   return EMTT_TRADE_GATE_OK;
  }

string EmttTradeGateStatus(const EEmttTradeGateFailure failure,
                           const int spreadPoints,
                           const int confidence=0,const int side=0,
                           const int autoTradeAbove=0)
  {
   switch(failure)
     {
      case EMTT_TRADE_GATE_AUTO_OFF:
         return "No trade "+EmttTradeDash()+" Auto Trading OFF";
      case EMTT_TRADE_GATE_TERMINAL_OFF:
         return "No trade "+EmttTradeDash()+" terminal algo trading OFF.";
      case EMTT_TRADE_GATE_MARKET_CLOSED:
         return EmttStatusForRegime(EMTT_REGIME_MARKET_CLOSED);
      case EMTT_TRADE_GATE_ALREADY_LIVE:
         return "No trade "+EmttTradeDash()+" Emtt trade already live";
      case EMTT_TRADE_GATE_SPREAD:
         return "No trade "+EmttTradeDash()+" spread too wide ("+
                IntegerToString(spreadPoints)+" pts)";
      case EMTT_TRADE_GATE_MARGIN:
         return "No trade "+EmttTradeDash()+" not enough margin";
      case EMTT_TRADE_GATE_BELOW_THRESHOLD:
         return EmttTierBelowThresholdLine(confidence,side,autoTradeAbove);
      default:
         return "";
     }
  }

bool EmttTradeSpreadAllowed(const double currentSpread,
                            const double averageSpread,
                            const int sampleCount)
  {
   if(sampleCount<EMTT_TRADE_SPREAD_SAMPLES)
      return true;
   if(!EmttTradeValid(currentSpread) || !EmttTradeValid(averageSpread) ||
      averageSpread<0.0)
      return false;
   return(currentSpread<=EMTT_TRADE_SPREAD_MULT*averageSpread);
  }

//--- 21.5 sizing -----------------------------------------------------
double EmttTradeConfidenceSizeMultiplier(const int confidence)
  {
   // Phase 11 (28.5): the multiplier follows the displayed tier -
   // Low 0.7 / Normal 1.0 / Confident 1.2 / High 1.5.
   return EmttTierSizeMultiplier(confidence);
  }

double EmttTradeNewsSizeMultiplier(const int impact)
  {
   if(impact==EMTT_NEWS_IMPACT_HIGH)   return EMTT_NEWS_SIZE_HIGH;
   if(impact==EMTT_NEWS_IMPACT_MEDIUM) return EMTT_NEWS_SIZE_MED;
   return 1.0;
  }

double EmttTradeRiskLots(const double balance,const double entry,
                         const double stop,const double tickSize,
                         const double tickValue,const int confidence,
                         const double newsMultiplier)
  {
   if(!EmttTradeValidPositive(balance) || !EmttTradeValid(entry) ||
      !EmttTradeValid(stop) || !EmttTradeValidPositive(tickSize) ||
      !EmttTradeValidPositive(tickValue) ||
      !EmttTradeValidPositive(newsMultiplier))
      return 0.0;
   const double stopDistance=MathAbs(entry-stop);
   if(stopDistance<=0.0)
      return 0.0;
   const double riskMoney=balance*EMTT_TRADE_RISK/100.0;
   const double moneyPerLot=stopDistance/tickSize*tickValue;
   if(!EmttTradeValidPositive(moneyPerLot))
      return 0.0;
   return riskMoney/moneyPerLot*
          EmttTradeConfidenceSizeMultiplier(confidence)*newsMultiplier;
  }

int EmttTradeVolumeDigits(const double step)
  {
   if(!EmttTradeValidPositive(step))
      return 2;
   for(int digits=0;digits<=8;digits++)
      if(MathAbs(step-NormalizeDouble(step,digits))<1e-10)
         return digits;
   return 8;
  }

double EmttTradeFloorToStep(const double volume,const double step)
  {
   if(!EmttTradeValidPositive(volume) || !EmttTradeValidPositive(step))
      return 0.0;
   const double floored=MathFloor((volume+step*1e-10)/step)*step;
   return NormalizeDouble(floored,EmttTradeVolumeDigits(step));
  }

double EmttTradeResolveLots(const int mode,const double balance,
                            const double entry,const double stop,
                            const double tickSize,const double tickValue,
                            const int confidence,const double newsMultiplier,
                            const double minimum,const double maximum,
                            const double step)
  {
   if(!EmttTradeValidPositive(minimum) || maximum<minimum ||
      !EmttTradeValidPositive(step))
      return 0.0;
   if(mode==EMTT_LOT_MINIMUM)
      return NormalizeDouble(minimum,EmttTradeVolumeDigits(step));
   const double raw=EmttTradeRiskLots(balance,entry,stop,tickSize,tickValue,
                                      confidence,newsMultiplier);
   if(raw<=0.0)
      return 0.0;
   double lots=EmttTradeFloorToStep(raw,step);
   if(lots<minimum)
      lots=minimum;
   if(lots>maximum)
      lots=maximum;
   return NormalizeDouble(lots,EmttTradeVolumeDigits(step));
  }

double EmttTradeMoneyForDistance(const double distance,const double lots,
                                 const double tickSize,
                                 const double tickValue)
  {
   if(!EmttTradeValid(distance) || !EmttTradeValidPositive(lots) ||
      !EmttTradeValidPositive(tickSize) ||
      !EmttTradeValidPositive(tickValue))
      return 0.0;
   return MathAbs(distance)/tickSize*tickValue*lots;
  }

void EmttTradeMoneyRows(const double plannedEntry,const double stop,
                        const double target,const double dealingPrice,
                        const double lots,const double tickSize,
                        const double tickValue,double &entryMoney,
                        double &stopMoney,double &targetMoney)
  {
   entryMoney=EmttTradeMoneyForDistance(plannedEntry-dealingPrice,lots,
                                        tickSize,tickValue);
   stopMoney=EmttTradeMoneyForDistance(plannedEntry-stop,lots,
                                       tickSize,tickValue);
   targetMoney=EmttTradeMoneyForDistance(target-plannedEntry,lots,
                                         tickSize,tickValue);
  }

//--- 21.6 order construction ----------------------------------------
void EmttTradeOrderReset(SEmttTradeOrderPlan &order)
  {
   order.valid=false;
   order.pending=false;
   order.side=0;
   order.orderType=-1;
   order.volume=0.0;
   order.price=0.0;
   order.stopLoss=0.0;
   order.takeProfit=0.0;
   order.stopLossSent=false;
   order.takeProfitSent=false;
   order.tp2Sent=false;
   order.timeInForce=0;
  }

bool EmttTradeBuildOrder(const int side,const int entryKind,
                         const double plannedEntry,const double stop,
                         const double tp1,const double bid,const double ask,
                         const bool placeStopLoss,const int digits,
                         SEmttTradeOrderPlan &order)
  {
   EmttTradeOrderReset(order);
   if((side!=1 && side!=-1) || !EmttTradeValidPositive(plannedEntry) ||
      !EmttTradeValidPositive(stop) || !EmttTradeValidPositive(tp1) ||
      !EmttTradeValidPositive(bid) || !EmttTradeValidPositive(ask) ||
      digits<0 || digits>8)
      return false;

   order.side=side;
   order.pending=(entryKind==EMTT_PLAN_ENTRY_BLOCK &&
                  (side>0 ? plannedEntry<ask : plannedEntry>bid));
   if(order.pending)
     {
      order.orderType=(side>0 ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT);
      order.price=NormalizeDouble(plannedEntry,digits);
      order.timeInForce=ORDER_TIME_GTC;
     }
   else
     {
      order.orderType=(side>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      order.price=NormalizeDouble((side>0 ? ask : bid),digits);
      order.timeInForce=ORDER_TIME_GTC;
     }
   order.stopLossSent=placeStopLoss;
   order.stopLoss=(placeStopLoss ? NormalizeDouble(stop,digits) : 0.0);
   order.takeProfitSent=true;
   order.takeProfit=NormalizeDouble(tp1,digits);
   // TP2 is named and managed, but is never sent with the opening order.
   order.tp2Sent=false;
   order.valid=true;
   return true;
  }

//--- 21.7 management -----------------------------------------------
double EmttTradeTrailBase(const ENUM_TIMEFRAMES timeframe)
  {
   if(timeframe==PERIOD_M5)  return EMTT_TRAIL_BASE_M5;
   if(timeframe==PERIOD_M15) return EMTT_TRAIL_BASE_M15;
   if(timeframe==PERIOD_M30) return EMTT_TRAIL_BASE_M30;
   return EMTT_TRAIL_BASE_M15;
  }

double EmttTradeTrailConfidenceMultiplier(const int confidence)
  {
   if(confidence>=85) return EMTT_TRAIL_CONF_85;
   if(confidence>=70) return EMTT_TRAIL_CONF_70;
   if(confidence>=55) return EMTT_TRAIL_CONF_55;
   return EMTT_TRAIL_CONF_LOW;
  }

double EmttTradeTrailRegimeMultiplier(const EEmttRegime regime)
  {
   if(EmttIsTrending(regime)) return EMTT_TRAIL_REGIME_TRENDING;
   if(regime==EMTT_REGIME_TRANSITION) return EMTT_TRAIL_REGIME_TRANSITION;
   if(regime==EMTT_REGIME_VOLATILE) return EMTT_TRAIL_REGIME_VOLATILE;
   return EMTT_TRAIL_REGIME_RANGING;
  }

string EmttTradeTrailMethodName(const int method)
  {
   if(method==EMTT_TRAIL_METHOD_ATR)         return "ATR";
   if(method==EMTT_TRAIL_METHOD_CHANDELIER)  return "Chandelier";
   if(method==EMTT_TRAIL_METHOD_FRACTAL)     return "Fractal";
   return "Original";
  }

string EmttTradeProtectWord(const bool stopExists,const bool breakeven,
                            const int method)
  {
   if(!stopExists) return "Original";
   if(!breakeven)  return "Original";
   if(method==EMTT_TRAIL_METHOD_NONE) return "Breakeven";
   return EmttTradeTrailMethodName(method);
  }

int EmttTradeTrailMethodOf(const double profitFraction)
  {
   if(profitFraction<EMTT_TRAIL_PHASE_HI)
      return EMTT_TRAIL_METHOD_ATR;
   if(profitFraction<EMTT_TRAIL_PHASE_TOP)
      return EMTT_TRAIL_METHOD_CHANDELIER;
   return EMTT_TRAIL_METHOD_FRACTAL;
  }

bool EmttTradeBreakevenReached(const int side,const double entry,
                               const double barHigh,const double barLow,
                               const double atr)
  {
   if(!EmttTradeValidPositive(entry) || !EmttTradeValidPositive(atr))
      return false;
   if(side>0)
      return(barHigh>=entry+EMTT_TRADE_BE_ATR*atr);
   if(side<0)
      return(barLow<=entry-EMTT_TRADE_BE_ATR*atr);
   return false;
  }

// Returns the volume to close; zero means that an exact 50% close cannot
// leave two broker-valid lots. The requested half is rounded to the nearest
// volume step, with a deterministic tie rounded down.
double EmttTradePartialVolume(const double volume,const double minimum,
                              const double step)
  {
   if(!EmttTradeValidPositive(volume) || !EmttTradeValidPositive(minimum) ||
      !EmttTradeValidPositive(step))
      return 0.0;
   const double half=volume*EMTT_TRADE_PARTIAL_PCT/100.0;
   const double closeVolume=MathFloor(half/step+0.5-1e-10)*step;
   const double rounded=NormalizeDouble(closeVolume,EmttTradeVolumeDigits(step));
   const double remainder=NormalizeDouble(volume-rounded,
                                           EmttTradeVolumeDigits(step));
   if(rounded<minimum || remainder<minimum || rounded>=volume)
      return 0.0;
   return rounded;
  }

// Closed-candle ATR fallback for a trade whose original timeframe differs
// from the attached chart. Rates are series-indexed, newest closed first.
double EmttTradeAtrFromRates(const MqlRates &rates[],const int period)
  {
   const int count=ArraySize(rates);
   if(period<1 || count<period+1)
      return 0.0;
   double total=0.0;
   for(int i=period-1;i>=0;i--)
     {
      const double priorClose=rates[i+1].close;
      const double trueRange=MathMax(rates[i].high-rates[i].low,
                           MathMax(MathAbs(rates[i].high-priorClose),
                                   MathAbs(rates[i].low-priorClose)));
      if(!EmttTradeValidPositive(trueRange))
         return 0.0;
      total+=trueRange;
     }
   return total/(double)period;
  }

int EmttTradeExpectedUpperMinutes(const int estimateMinutes)
  {
   if(estimateMinutes<=0)
      return 0;
   if(estimateMinutes<120)
      return (int)MathRound(1.5*(double)estimateMinutes/5.0)*5;
   if(estimateMinutes<=4320)
     {
      int hours=(int)MathRound(1.5*(double)estimateMinutes/60.0);
      if(hours<1) hours=1;
      return hours*60;
     }
   return 4320;
  }

//--- 21.7 trailing distance -----------------------------------------
bool EmttTradeTrailCalculate(const int side,const double entry,
                             const double current,const double tp1,
                             const double atr,
                             const ENUM_TIMEFRAMES timeframe,
                             const int confidence,const EEmttRegime regime,
                             const bool highNews,const double highestHigh,
                             const double lowestLow,const bool hasSwing,
                             const double swingLow,const double swingHigh,
                             SEmttTradeTrailResult &result,
                             const double divergenceMult=1.0)
  {
   result.valid=false;
   result.method=EMTT_TRAIL_METHOD_NONE;
   result.profitFraction=0.0;
   result.baseDistance=0.0;
   result.rawDistance=0.0;
   result.confidenceMultiplier=1.0;
   result.regimeMultiplier=1.0;
   result.newsMultiplier=(highNews ? EMTT_NEWS_TRAIL_MULT : 1.0);
   result.distance=0.0;
   result.stop=0.0;
   if((side!=1 && side!=-1) || !EmttTradeValidPositive(entry) ||
      !EmttTradeValid(current) || !EmttTradeValidPositive(tp1) ||
      !EmttTradeValidPositive(atr))
      return false;
   const double targetDistance=(side>0 ? tp1-entry : entry-tp1);
   if(targetDistance<=0.0)
      return false;
   double favorable=(side>0 ? current-entry : entry-current);
   if(favorable<0.0) favorable=0.0;
   result.profitFraction=favorable/targetDistance;
   result.method=EmttTradeTrailMethodOf(result.profitFraction);
   result.baseDistance=EmttTradeTrailBase(timeframe)*atr;
   if(result.method==EMTT_TRAIL_METHOD_ATR)
      result.rawDistance=result.baseDistance;
   else if(result.method==EMTT_TRAIL_METHOD_CHANDELIER)
     {
      if(side>0 && EmttTradeValidPositive(highestHigh))
         result.rawDistance=current-(highestHigh-EMTT_TRAIL_CHANDELIER*atr);
      else if(side<0 && EmttTradeValidPositive(lowestLow))
         result.rawDistance=(lowestLow+EMTT_TRAIL_CHANDELIER*atr)-current;
      else
         return false;
     }
   else
     {
      if(!hasSwing)
         return false;
      if(side>0 && EmttTradeValidPositive(swingLow))
         result.rawDistance=current-(swingLow-EMTT_TRAIL_FRACTAL_BUFFER*atr);
      else if(side<0 && EmttTradeValidPositive(swingHigh))
         result.rawDistance=(swingHigh+EMTT_TRAIL_FRACTAL_BUFFER*atr)-current;
      else
         return false;
     }
   if(!EmttTradeValidPositive(result.rawDistance))
      return false;
   result.confidenceMultiplier=
      EmttTradeTrailConfidenceMultiplier(confidence);
   result.regimeMultiplier=EmttTradeTrailRegimeMultiplier(regime);
   result.distance=result.rawDistance*result.confidenceMultiplier*
                   result.regimeMultiplier*result.newsMultiplier*divergenceMult;
   if(!EmttTradeValidPositive(result.distance))
      return false;
   result.stop=(side>0 ? current-result.distance : current+result.distance);
   result.valid=EmttTradeValidPositive(result.stop);
   return result.valid;
  }

bool EmttTradeStopImproves(const int side,const double oldStop,
                           const double newStop,const double point)
  {
   if(!EmttTradeValidPositive(newStop))
      return false;
   if(oldStop<=0.0)
      return true;
   const double epsilon=(point>0.0 ? point*0.1 : 1e-10);
   if(side>0)
      return newStop>oldStop+epsilon;
   if(side<0)
      return newStop<oldStop-epsilon;
   return false;
  }

//--- 21.8 target candidates -----------------------------------------
void EmttTradeAddCandidate(SEmttTradeCandidate &items[],int &count,
                           const double price,const int priority,
                           const string source)
  {
   if(!EmttTradeValidPositive(price) || count>=6)
      return;
   for(int i=0;i<count;i++)
      if(MathAbs(items[i].price-price)<1e-12)
         return;
   ArrayResize(items,count+1);
   items[count].price=price;
   items[count].priority=priority;
   items[count].source=source;
   count++;
  }

int EmttTradeCandidates(const int side,const double current,
                        const SEmttSmcState &smc,
                        const SEmttVolumeFlowState &vf,
                        SEmttTradeCandidate &items[])
  {
   ArrayResize(items,0);
   int count=0;
   if(smc.hasGapAbove && side>0)
      EmttTradeAddCandidate(items,count,smc.gapAboveNearEdge,0,
                            "fair value gap");
   if(smc.hasGapBelow && side<0)
      EmttTradeAddCandidate(items,count,smc.gapBelowNearEdge,0,
                            "fair value gap");
   if(side>0 && smc.hasBuyPool)
      EmttTradeAddCandidate(items,count,smc.buyPoolLevel,1,"buy-side pool");
   if(side<0 && smc.hasSellPool)
      EmttTradeAddCandidate(items,count,smc.sellPoolLevel,1,"sell-side pool");
   if(vf.hasProfile)
     {
      EmttTradeAddCandidate(items,count,vf.poc,2,"POC");
      EmttTradeAddCandidate(items,count,vf.vah,3,"VAH");
      EmttTradeAddCandidate(items,count,vf.val,4,"VAL");
     }
   if(vf.priorPocAvailable && vf.priorPocNaked)
      EmttTradeAddCandidate(items,count,vf.priorPoc,5,"naked POC");

   // Nearest first from the current price; ties retain the 17.4 priority.
   for(int i=0;i<count;i++)
      for(int j=i+1;j<count;j++)
        {
         const double a=MathAbs(items[i].price-current);
         const double b=MathAbs(items[j].price-current);
         if(b<a || (b==a && items[j].priority<items[i].priority))
           {
            const SEmttTradeCandidate temp=items[i];
            items[i]=items[j];
            items[j]=temp;
           }
        }
   return count;
  }

bool EmttTradeLevelFuture(const int side,const double price,
                          const double current)
  {
   if(side>0) return price>current;
   if(side<0) return price<current;
   return false;
  }

bool EmttTradeTargetsInvariant(const int side,const double entry,
                               const double current,const double tp1,
                               const double tp2)
  {
   if(side>0)
     {
      if(!(entry<tp1 && tp1>current)) return false;
      return(tp2<=0.0 || (tp1<tp2 && tp2>current));
     }
   if(side<0)
     {
      if(!(entry>tp1 && tp1<current)) return false;
      return(tp2<=0.0 || (tp1>tp2 && tp2<current));
     }
   return false;
  }

bool EmttTradeInitialSecondTarget(const int side,const double entry,
                                  const double current,const double tp1,
                                  const SEmttTradeCandidate &items[],
                                  double &tp2,string &source)
  {
   tp2=0.0;
   source="";
   for(int i=0;i<ArraySize(items);i++)
     {
      const double p=items[i].price;
      const bool beyond=(side>0 ? p>tp1 : p<tp1);
      if(beyond && EmttTradeLevelFuture(side,p,current))
        {
         tp2=p;
         source=items[i].source;
         return true;
        }
     }
   return false;
  }

bool EmttTradeReviseTargets(const int side,const double entry,
                            const double current,const double stop,
                            const double currentTp1,const double currentTp2,
                            const int confidence,const int stayThreshold,
                            const bool inProfit,const bool momentumWith,
                            const bool tp1Hit,const double minimumRiskReward,
                            const SEmttTradeCandidate &items[],
                            SEmttTradeTargetResult &result)
  {
   result.valid=false;
   result.tp1Changed=false;
   result.tp2Changed=false;
   result.tp1=currentTp1;
   result.tp2=currentTp2;
   result.tp1Source="";
   result.tp2Source="";
   if((side!=1 && side!=-1) || !EmttTradeValidPositive(entry) ||
      !EmttTradeValid(current) || !EmttTradeValidPositive(stop) ||
      minimumRiskReward<0.0)
      return false;

   int selectedTp1=-1;
   const bool confidenceSnap=(inProfit && confidence<stayThreshold);
   if(confidenceSnap)
     {
      for(int i=0;i<ArraySize(items);i++)
         if(EmttTradeLevelFuture(side,items[i].price,current) &&
            (side>0 ? items[i].price>entry : items[i].price<entry))
           {
            selectedTp1=i;
            break;
           }
     }
   else if(tp1Hit)
     {
      // After the partial is done, keep both displayed levels ahead of price.
      for(int i=0;i<ArraySize(items);i++)
         if(EmttTradeLevelFuture(side,items[i].price,current) &&
            (side>0 ? items[i].price>entry : items[i].price<entry))
           {
            selectedTp1=i;
            break;
           }
     }
   else
     {
      for(int i=0;i<ArraySize(items);i++)
        {
         const double p=items[i].price;
         const bool nearer=(side>0 ? p<currentTp1 : p>currentTp1);
         if(!nearer || !EmttTradeLevelFuture(side,p,current) ||
            !(side>0 ? p>entry : p<entry))
            continue;
         const double risk=MathAbs(entry-stop);
         if(risk<=0.0)
            continue;
         const double rr=MathAbs(p-entry)/risk;
         if(rr+1e-12<minimumRiskReward)
            continue;
         selectedTp1=i;
         break;
        }
     }

   if(selectedTp1>=0)
     {
      result.tp1=items[selectedTp1].price;
      result.tp1Source=items[selectedTp1].source;
      result.tp1Changed=(MathAbs(result.tp1-currentTp1)>1e-12);
     }
   else if(!EmttTradeLevelFuture(side,currentTp1,current))
      return false;

   if(momentumWith && !tp1Hit)
     {
      int extend=-1;
      for(int i=0;i<ArraySize(items);i++)
        {
         const double p=items[i].price;
         const bool beyondTp1=(side>0 ? p>result.tp1 : p<result.tp1);
         const bool further=(currentTp2<=0.0 ||
                             (side>0 ? p>currentTp2 : p<currentTp2));
         if(beyondTp1 && further &&
            EmttTradeLevelFuture(side,p,current))
           {
            extend=i;
            break;
           }
        }
      if(extend>=0)
        {
         result.tp2=items[extend].price;
         result.tp2Source=items[extend].source;
         result.tp2Changed=(MathAbs(result.tp2-currentTp2)>1e-12);
        }
      else if(currentTp2>0.0 &&
              !EmttTradeLevelFuture(side,currentTp2,current))
         result.tp2=0.0;
     }
   else
     {
      int contract=-1;
      for(int i=0;i<ArraySize(items);i++)
        {
         const double p=items[i].price;
         const bool beyondTp1=(side>0 ? p>result.tp1 : p<result.tp1);
         if(beyondTp1 && EmttTradeLevelFuture(side,p,current))
           {
            contract=i;
            break;
           }
        }
      result.tp2=(contract>=0 ? items[contract].price : 0.0);
      result.tp2Source=(contract>=0 ? items[contract].source : "");
      result.tp2Changed=(MathAbs(result.tp2-currentTp2)>1e-12);
     }

   if(result.tp2>0.0 &&
      !(side>0 ? result.tp1<result.tp2 : result.tp1>result.tp2))
      return false;
   if(!EmttTradeLevelFuture(side,result.tp1,current))
      return false;
   if(result.tp2>0.0 && !EmttTradeLevelFuture(side,result.tp2,current))
      return false;
   result.valid=true;
   return true;
  }

//--- 21.9 time exit --------------------------------------------------
bool EmttTradeTimeExitClose(const int ageMinutes,const int upperMinutes,
                            const bool tp1Hit,const double profitPoints)
  {
   if(upperMinutes<=0 || ageMinutes<=upperMinutes)
      return false;
   return(tp1Hit || profitPoints>0.0);
  }

bool EmttTradeTimeExitHold(const int ageMinutes,const int upperMinutes,
                           const bool tp1Hit,const double profitPoints)
  {
   return(upperMinutes>0 && ageMinutes>upperMinutes && !tp1Hit &&
          profitPoints<=0.0);
  }

string EmttTradeTimeExitHoldText()
  {
   return "Holding "+EmttTradeDash()+
          " past expected duration, not in profit yet.";
  }

//--- 21.10 news ------------------------------------------------------
int EmttTradeNewsStrongest(const int firstImpact,const int secondImpact)
  {
   return (int)MathMax(firstImpact,secondImpact);
  }

double EmttTradeNewsTrailMultiplier(const int impact)
  {
   return(impact==EMTT_NEWS_IMPACT_HIGH ? EMTT_NEWS_TRAIL_MULT : 1.0);
  }

string EmttTradeNewsStatus(const string eventName,const int minutes,
                           const int impact)
  {
   if(impact!=EMTT_NEWS_IMPACT_HIGH && impact!=EMTT_NEWS_IMPACT_MEDIUM)
      return "";
   const string impactName=(impact==EMTT_NEWS_IMPACT_HIGH ? "high" : "medium");
   const double size=EmttTradeNewsSizeMultiplier(impact);
   const int sizeDigits=(impact==EMTT_NEWS_IMPACT_HIGH ? 1 : 2);
   return "News "+EmttTradeDash()+" "+eventName+" in "+
          IntegerToString(minutes)+" min ("+impactName+" impact), size "+
          DoubleToString(size,sizeDigits)+"x.";
  }

//--- 21.12 row/status composition -----------------------------------
string EmttTradePanelStatus(const string incompatibleStatus,
                            const string loadingStatus,
                            const string marketClosedStatus,
                            const string freshStatus,
                            const string timeExitHoldStatus,
                            const string newsStatus,
                            const string gateStatus,
                            const string liveTradeStatus,
                            const string signalStatus,
                            const string contextStatus,
                            const string terminalStatus)
  {
   if(incompatibleStatus!="") return incompatibleStatus;
   if(loadingStatus!="") return loadingStatus;
   if(marketClosedStatus!="") return marketClosedStatus;
   if(freshStatus!="") return freshStatus;
   if(timeExitHoldStatus!="") return timeExitHoldStatus;
   if(newsStatus!="") return newsStatus;
   if(gateStatus!="") return gateStatus;
   if(liveTradeStatus!="") return liveTradeStatus;
   if(signalStatus!="") return signalStatus;
   if(contextStatus!="") return contextStatus;
   return terminalStatus;
  }

#endif // EMTT_TRADE_MQH
