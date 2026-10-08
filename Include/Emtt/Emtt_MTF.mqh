//+------------------------------------------------------------------+
//|                                                   Emtt_MTF.mqh   |
//| Phase 5: Multi-Timeframe Agreement - the higher-timeframe context|
//| Spec: Emtt.md sections 15.8-15.12                                |
//+------------------------------------------------------------------+
//| This header closes the design seam of 11.11 / 13.14: the Phase 2 |
//| / 3 / 4 headers take their state as arguments, so the HTF context|
//| is a second instance of each of them, re-run on the higher        |
//| timeframe's own closed bars.                                      |
//| It owns its own HTF indicator handles (an exact mirror of the     |
//| EA's chart handle set, created on the higher timeframe), its own  |
//| HTF rates and buffers, and it draws nothing.                      |
//+------------------------------------------------------------------+
#ifndef EMTT_MTF_MQH
#define EMTT_MTF_MQH

#include "Emtt_Regime.mqh"
#include "Emtt_Supertrend.mqh"
#include "Emtt_SMC.mqh"

//--- 15.8 / 15.9 fixed constants -----------------------------------
#define EMTT_MTF_FETCH_BUFFER       10
#define EMTT_MTF_WEIGHT_DIRECTION   0.50
#define EMTT_MTF_WEIGHT_REGIME      0.30
#define EMTT_MTF_WEIGHT_STRUCTURE   0.20
#define EMTT_MTF_STATUS_FRESH_BARS  3

//+------------------------------------------------------------------+
//| The readings and the score (15.9). One instance lives in the EA. |
//+------------------------------------------------------------------+
struct SEmttMtfState
  {
   bool                 ready;
   ENUM_TIMEFRAMES      htf;
   string               htfName;
   EEmttRegime          htfRegime;
   int                  htfSupertrendDirection;
   EEmttStCluster       htfCluster;
   double               htfMultiplier;
   int                  htfBias;
   EEmttSmcZone         htfZone;
   int                  agrees;          // 1 / -1 / 0 at the last evaluation
   datetime             htfBarTime;

   int                  htfAtrPeriod;
   double               htfAtrValue;
   int                  htfBarsFetched;
   int                  chartSupertrendDirection; // at the last evaluation
   int                  chartSmcBias;             // at the last evaluation
   long                 currentSequence;
   long                 lastFlipChartSequence;
   int                  lastFlipDirection;
   SEmttRegimeMeasurements htfMeasurements;
   double               mtfScore;
  };

//+------------------------------------------------------------------+
//| The HTF machinery (15.8): the second instances of the approved   |
//| component states, the HTF bars and buffers, the HTF handle set   |
//| and the stored HTF bar time.                                     |
//+------------------------------------------------------------------+
struct SEmttMtfContext
  {
   bool                 handlesReady;
   ENUM_TIMEFRAMES      htf;          // PERIOD_CURRENT = no higher timeframe
   string               symbol;
   EEmttAssetClass      assetClass;
   bool                 evaluated;
   bool                 rebuildNeeded;
   int                  fetchCount;
   int                  htfBarsFetched;
   long                 htfSequence;
   datetime             lastHtfBarTime;

   int                  hAtr10;
   int                  hAtr14;
   int                  hAtr21;
   int                  hAtr28;
   int                  hAtr50;
   int                  hKama9;
   int                  hKama13;
   int                  hKama21;
   int                  hKama26;
   int                  hKama34;
   int                  hKama50;
   int                  hBands;

   SEmttDynamicState    dynamic;
   SEmttRegimeState     regime;
   SEmttSupertrendState supertrend;
   SEmttSmcState        smc;

   MqlRates             rates[];
   double               atr10[];
   double               atr14[];
   double               atr21[];
   double               atr28[];
   double               atr50[];
   double               kama9[];
   double               kama13[];
   double               kama21[];
   double               kama26[];
   double               kama34[];
   double               kama50[];
   double               bandUpper[];
   double               bandLower[];

   SEmttRegimeMeasurements measurements;
  };

//+------------------------------------------------------------------+
//| 15.8 the fixed mapping, one table in one function.               |
//| Any other chart timeframe returns "no HTF" and the component     |
//| never publishes (rule 19 already blocks those charts).           |
//+------------------------------------------------------------------+
ENUM_TIMEFRAMES EmttMtfTimeframe(const ENUM_TIMEFRAMES chartTimeframe)
  {
   if(chartTimeframe==PERIOD_M5)  return PERIOD_M15;
   if(chartTimeframe==PERIOD_M15) return PERIOD_H1;
   if(chartTimeframe==PERIOD_M30) return PERIOD_H4;
   return PERIOD_CURRENT;
  }

string EmttMtfName(const ENUM_TIMEFRAMES htf)
  {
   if(htf==PERIOD_M15) return "M15";
   if(htf==PERIOD_H1)  return "H1";
   if(htf==PERIOD_H4)  return "H4";
   return "--";
  }

// 15.8: the existing timeframe-based requirements, one code path.
// With today's matrices this is 300 for M15 and 250 for H1 and H4.
int EmttMtfHistoryRequired(const ENUM_TIMEFRAMES htf)
  {
   return (int)MathMax(EmttHistoryRequired(htf),EmttSmcHistoryRequired(htf));
  }

int EmttMtfFetchCount(const ENUM_TIMEFRAMES htf)
  {
   return EmttMtfHistoryRequired(htf)+EMTT_MTF_FETCH_BUFFER;
  }

//+------------------------------------------------------------------+
//| Small local helpers                                               |
//+------------------------------------------------------------------+
double EmttMtfClamp01(const double value)
  {
   if(!MathIsValidNumber(value))
      return 0.0;
   return MathMax(0.0,MathMin(1.0,value));
  }

int EmttMtfAge(const long currentSequence,const long occurredSequence)
  {
   if(occurredSequence<=-1000000 || currentSequence<occurredSequence)
      return 1000000;
   const long age=currentSequence-occurredSequence;
   if(age>2147483647)
      return 2147483647;
   return (int)age;
  }

//+------------------------------------------------------------------+
//| The HTF handle set - an exact mirror of the EA's chart handles,  |
//| created on (symbol, htf). Created lazily by the MTF context and  |
//| released only by EmttMtfFree().                                  |
//+------------------------------------------------------------------+
void EmttMtfFree(SEmttMtfContext &context)
  {
   // Handles are always positive; 0 means "never created" on a fresh chart.
   if(context.hAtr10>0)  IndicatorRelease(context.hAtr10);
   if(context.hAtr14>0)  IndicatorRelease(context.hAtr14);
   if(context.hAtr21>0)  IndicatorRelease(context.hAtr21);
   if(context.hAtr28>0)  IndicatorRelease(context.hAtr28);
   if(context.hAtr50>0)  IndicatorRelease(context.hAtr50);
   if(context.hKama9>0)  IndicatorRelease(context.hKama9);
   if(context.hKama13>0) IndicatorRelease(context.hKama13);
   if(context.hKama21>0) IndicatorRelease(context.hKama21);
   if(context.hKama26>0) IndicatorRelease(context.hKama26);
   if(context.hKama34>0) IndicatorRelease(context.hKama34);
   if(context.hKama50>0) IndicatorRelease(context.hKama50);
   if(context.hBands>0)  IndicatorRelease(context.hBands);

   context.hAtr10=INVALID_HANDLE;
   context.hAtr14=INVALID_HANDLE;
   context.hAtr21=INVALID_HANDLE;
   context.hAtr28=INVALID_HANDLE;
   context.hAtr50=INVALID_HANDLE;
   context.hKama9=INVALID_HANDLE;
   context.hKama13=INVALID_HANDLE;
   context.hKama21=INVALID_HANDLE;
   context.hKama26=INVALID_HANDLE;
   context.hKama34=INVALID_HANDLE;
   context.hKama50=INVALID_HANDLE;
   context.hBands=INVALID_HANDLE;
   context.handlesReady=false;
   context.htf=PERIOD_CURRENT;
   context.evaluated=false;
   context.rebuildNeeded=true;
  }

void EmttMtfClearData(SEmttMtfContext &context)
  {
   context.fetchCount=0;
   context.htfBarsFetched=0;
   context.htfSequence=0;
   context.lastHtfBarTime=0;
   ArrayResize(context.rates,0);
   ArrayResize(context.atr10,0);
   ArrayResize(context.atr14,0);
   ArrayResize(context.atr21,0);
   ArrayResize(context.atr28,0);
   ArrayResize(context.atr50,0);
   ArrayResize(context.kama9,0);
   ArrayResize(context.kama13,0);
   ArrayResize(context.kama21,0);
   ArrayResize(context.kama26,0);
   ArrayResize(context.kama34,0);
   ArrayResize(context.kama50,0);
   ArrayResize(context.bandUpper,0);
   ArrayResize(context.bandLower,0);
   EmttDynamicReset(context.dynamic);
   EmttRegimeReset(context.regime);
   EmttSupertrendReset(context.supertrend);
   EmttSmcReset(context.smc);
  }

void EmttMtfClearState(SEmttMtfState &state)
  {
   state.ready=false;
   state.htf=PERIOD_CURRENT;
   state.htfName="--";
   state.htfRegime=EMTT_REGIME_UNKNOWN;
   state.htfSupertrendDirection=0;
   state.htfCluster=EMTT_ST_CLUSTER_NONE;
   state.htfMultiplier=0.0;
   state.htfBias=0;
   state.htfZone=EMTT_SMC_ZONE_NONE;
   state.agrees=0;
   state.htfBarTime=0;
   state.htfAtrPeriod=0;
   state.htfAtrValue=0.0;
   state.htfBarsFetched=0;
   state.chartSupertrendDirection=0;
   state.chartSmcBias=0;
   state.currentSequence=0;
   state.lastFlipChartSequence=-1000000;
   state.lastFlipDirection=0;
   state.mtfScore=0.0;
  }

// The EA calls this from EmttReleaseIndicators() (OnDeinit and every chart
// context change) and from EmttResetMarketState().
void EmttMtfReset(SEmttMtfState &state,SEmttMtfContext &context)
  {
   EmttMtfFree(context);
   EmttMtfClearData(context);
   context.symbol="";
   context.assetClass=EMTT_CLASS_GENERIC;
   EmttMtfClearState(state);
  }

bool EmttMtfCreateHandles(SEmttMtfContext &context,const string symbol,
                          const ENUM_TIMEFRAMES htf)
  {
   EmttMtfFree(context);
   context.htf=htf;
   context.symbol=symbol;
   context.hAtr10=iATR(symbol,htf,10);
   context.hAtr14=iATR(symbol,htf,14); // the fixed volatility measuring stick
   context.hAtr21=iATR(symbol,htf,21);
   context.hAtr28=iATR(symbol,htf,28);
   context.hAtr50=iATR(symbol,htf,50);
   context.hKama9=iAMA(symbol,htf,9,2,30,0,PRICE_CLOSE);
   context.hKama13=iAMA(symbol,htf,13,2,30,0,PRICE_CLOSE);
   context.hKama21=iAMA(symbol,htf,21,2,30,0,PRICE_CLOSE);
   context.hKama26=iAMA(symbol,htf,26,2,30,0,PRICE_CLOSE);
   context.hKama34=iAMA(symbol,htf,34,2,30,0,PRICE_CLOSE);
   context.hKama50=iAMA(symbol,htf,50,2,30,0,PRICE_CLOSE);
   context.hBands=iBands(symbol,htf,20,0,2.0,PRICE_CLOSE);

   context.handlesReady=(context.hAtr10!=INVALID_HANDLE &&
                         context.hAtr14!=INVALID_HANDLE &&
                         context.hAtr21!=INVALID_HANDLE &&
                         context.hAtr28!=INVALID_HANDLE &&
                         context.hAtr50!=INVALID_HANDLE &&
                         context.hKama9!=INVALID_HANDLE &&
                         context.hKama13!=INVALID_HANDLE &&
                         context.hKama21!=INVALID_HANDLE &&
                         context.hKama26!=INVALID_HANDLE &&
                         context.hKama34!=INVALID_HANDLE &&
                         context.hKama50!=INVALID_HANDLE &&
                         context.hBands!=INVALID_HANDLE);
   return context.handlesReady;
  }

bool EmttMtfEnsureHandles(SEmttMtfContext &context,const string symbol,
                          const ENUM_TIMEFRAMES htf)
  {
   if(context.handlesReady && context.htf==htf && context.symbol==symbol)
      return true;
   return EmttMtfCreateHandles(context,symbol,htf);
  }

// 15.8 readiness - the same waiting pattern as EmttIndicatorsCalculated(),
// applied to the HTF set.
bool EmttMtfBuffersCalculated(SEmttMtfContext &context,const int count)
  {
   if(!context.handlesReady || count<=0)
      return false;
   if(BarsCalculated(context.hAtr10)<count ||
      BarsCalculated(context.hAtr14)<count ||
      BarsCalculated(context.hAtr21)<count ||
      BarsCalculated(context.hAtr28)<count ||
      BarsCalculated(context.hAtr50)<count ||
      BarsCalculated(context.hKama9)<count ||
      BarsCalculated(context.hKama13)<count ||
      BarsCalculated(context.hKama21)<count ||
      BarsCalculated(context.hKama26)<count ||
      BarsCalculated(context.hKama34)<count ||
      BarsCalculated(context.hKama50)<count ||
      BarsCalculated(context.hBands)<count)
      return false;
   return true;
  }

bool EmttMtfCopySeries(const int handle,const int buffer,const int count,
                       double &destination[])
  {
   if(handle==INVALID_HANDLE || count<=0)
      return false;
   if(ArrayResize(destination,count)!=count)
      return false;
   ArraySetAsSeries(destination,true);
   const int copied=CopyBuffer(handle,buffer,1,count,destination);
   if(copied!=count)
      return false;
   return true;
  }

//+------------------------------------------------------------------+
//| The per-HTF-bar measurements - the identical formulas of the EA's |
//| EmttBuildMeasurements(), with the HTF arrays passed as arguments. |
//| The twin never reads an EA chart-timeframe global.                |
//+------------------------------------------------------------------+
double EmttMtfEfficiencyRatio(const MqlRates &rates[],const int index,
                              const int period)
  {
   if(index<0 || period<=0 || index+period>=ArraySize(rates))
      return -1.0;
   const double net=MathAbs(rates[index].close-rates[index+period].close);
   double path=0.0;
   for(int i=0;i<period;i++)
      path+=MathAbs(rates[index+i].close-rates[index+i+1].close);
   if(path<=0.0)
      return 0.0;
   return MathMax(0.0,MathMin(100.0,100.0*net/path));
  }

double EmttMtfAtrAt(SEmttMtfContext &context,const int period,const int index)
  {
   if(index<0)
      return 0.0;
   if(period==10 && index<ArraySize(context.atr10)) return context.atr10[index];
   if(period==14 && index<ArraySize(context.atr14)) return context.atr14[index];
   if(period==21 && index<ArraySize(context.atr21)) return context.atr21[index];
   if(period==28 && index<ArraySize(context.atr28)) return context.atr28[index];
   if(period==50 && index<ArraySize(context.atr50)) return context.atr50[index];
   return 0.0;
  }

double EmttMtfKamaAt(SEmttMtfContext &context,const int period,
                     const int index)
  {
   if(index<0)
      return 0.0;
   if(period==9  && index<ArraySize(context.kama9))  return context.kama9[index];
   if(period==13 && index<ArraySize(context.kama13)) return context.kama13[index];
   if(period==21 && index<ArraySize(context.kama21)) return context.kama21[index];
   if(period==26 && index<ArraySize(context.kama26)) return context.kama26[index];
   if(period==34 && index<ArraySize(context.kama34)) return context.kama34[index];
   if(period==50 && index<ArraySize(context.kama50)) return context.kama50[index];
   return 0.0;
  }

bool EmttMtfCopyArray(const double &source[],const int count,
                      double &destination[])
  {
   if(count<=0 || count>ArraySize(source))
      return false;
   if(ArrayResize(destination,count)!=count)
      return false;
   for(int i=0;i<count;i++)
      destination[i]=source[i];
   return true;
  }

// One contiguous ATR slice at the resolved matrix period, for the Phase 3
// and Phase 4 advances of the HTF walk.
bool EmttMtfFillAtr(SEmttMtfContext &context,const int period,
                    const int count,double &destination[])
  {
   if(period==10) return EmttMtfCopyArray(context.atr10,count,destination);
   if(period==14) return EmttMtfCopyArray(context.atr14,count,destination);
   if(period==21) return EmttMtfCopyArray(context.atr21,count,destination);
   if(period==28) return EmttMtfCopyArray(context.atr28,count,destination);
   if(period==50) return EmttMtfCopyArray(context.atr50,count,destination);
   return false;
  }

bool EmttMtfBuildMeasurements(SEmttMtfContext &context,const int index,
                              const SEmttDynamicState &parameters,
                              SEmttRegimeMeasurements &measurements)
  {
   if(index<0 || index>=ArraySize(context.rates) ||
      index+1>=ArraySize(context.bandUpper) ||
      index+1>=ArraySize(context.bandLower) ||
      index>=ArraySize(context.atr50))
      return false;

   measurements.efficiency=EmttMtfEfficiencyRatio(context.rates,index,
                                                  parameters.erPeriod);
   const double fast=EmttMtfKamaAt(context,parameters.kamaFast,index);
   const double medium=EmttMtfKamaAt(context,parameters.kamaMedium,index);
   const double slow=EmttMtfKamaAt(context,parameters.kamaSlow,index);
   const double atr=EmttMtfAtrAt(context,parameters.atrPeriod,index);
   const double atr50=context.atr50[index];
   const double width=context.bandUpper[index]-context.bandLower[index];
   const double previousWidth=context.bandUpper[index+1]-
                              context.bandLower[index+1];

   if(measurements.efficiency<0.0 || !MathIsValidNumber(fast) ||
      !MathIsValidNumber(medium) || !MathIsValidNumber(slow) ||
      !MathIsValidNumber(atr) || atr<=0.0 ||
      !MathIsValidNumber(atr50) || atr50<=0.0 ||
      !MathIsValidNumber(width) || width<=0.0 ||
      !MathIsValidNumber(previousWidth) || previousWidth<=0.0)
      return false;

   measurements.direction=0;
   measurements.kamaAligned=false;
   if(fast>medium && medium>slow)
     {
      measurements.direction=1;
      measurements.kamaAligned=true;
     }
   else if(fast<medium && medium<slow)
     {
      measurements.direction=-1;
      measurements.kamaAligned=true;
     }
   measurements.atrRatio=atr/atr50;
   measurements.bandsExpanding=(width>previousWidth);
   measurements.bandsSqueezing=(width<previousWidth);
   return MathIsValidNumber(measurements.atrRatio);
  }

//+------------------------------------------------------------------+
//| Fetch the HTF history the context needs: closed HTF bars, the    |
//| ATR / KAMA / band buffers and the readiness of the whole set.    |
//+------------------------------------------------------------------+
bool EmttMtfFetchData(SEmttMtfContext &context,const string symbol,
                      const ENUM_TIMEFRAMES htf,const int fetchCount)
  {
   context.fetchCount=fetchCount;
   context.htfBarsFetched=0;
   if(!EmttMtfBuffersCalculated(context,fetchCount))
      return false;

   ArrayResize(context.rates,fetchCount);
   ArraySetAsSeries(context.rates,true);
   int copied=CopyRates(symbol,htf,1,fetchCount,context.rates);
   if(copied<EmttMtfHistoryRequired(htf))
      return false;
   if(copied<ArraySize(context.rates))
      ArrayResize(context.rates,copied);
   context.htfBarsFetched=copied;

   if(!EmttMtfCopySeries(context.hAtr10,0,copied,context.atr10) ||
      !EmttMtfCopySeries(context.hAtr14,0,copied,context.atr14) ||
      !EmttMtfCopySeries(context.hAtr21,0,copied,context.atr21) ||
      !EmttMtfCopySeries(context.hAtr28,0,copied,context.atr28) ||
      !EmttMtfCopySeries(context.hAtr50,0,copied,context.atr50) ||
      !EmttMtfCopySeries(context.hKama9,0,copied,context.kama9) ||
      !EmttMtfCopySeries(context.hKama13,0,copied,context.kama13) ||
      !EmttMtfCopySeries(context.hKama21,0,copied,context.kama21) ||
      !EmttMtfCopySeries(context.hKama26,0,copied,context.kama26) ||
      !EmttMtfCopySeries(context.hKama34,0,copied,context.kama34) ||
      !EmttMtfCopySeries(context.hKama50,0,copied,context.kama50) ||
      !EmttMtfCopySeries(context.hBands,1,copied,context.bandUpper) ||
      !EmttMtfCopySeries(context.hBands,2,copied,context.bandLower))
      return false;
   return true;
  }

//+------------------------------------------------------------------+
//| 15.8 the full rebuild: a fresh HTF copy, a silent walk over all  |
//| fetched HTF bars oldest to newest, mirroring the EA's chart      |
//| replay loop bar for bar. The walk itself writes nothing.         |
//+------------------------------------------------------------------+
bool EmttMtfWalk(SEmttMtfContext &context,const string symbol,
                 const EEmttAssetClass assetClass,
                 const ENUM_TIMEFRAMES htf)
  {
   const int required=EmttMtfHistoryRequired(htf);
   if(context.htfBarsFetched<required)
      return false;

   EmttDynamicReset(context.dynamic);
   EmttRegimeReset(context.regime);
   EmttSupertrendReset(context.supertrend);
   EmttSmcReset(context.smc);

   const int evaluationCount=context.htfBarsFetched-(required-1);
   const int oldestIndex=evaluationCount-1;
   if(oldestIndex<0)
      return false;
   int periodSeconds=(int)PeriodSeconds(htf);
   if(periodSeconds<1)
      periodSeconds=1;

   double atrSlice[];
   int atrSlicePeriod=-1;
   datetime previousBarTime=0;
   long sequence=0;
   bool first=true;
   int evaluated=0;

   for(int index=oldestIndex;index>=0;index--)
     {
      const double percentile=EmttPercentileRank(context.atr14,index,
                                                 EMTT_VOLATILITY_WINDOW-1);
      if(percentile<0.0)
         return false;
      const datetime barTime=context.rates[index].time;
      if(first)
         EmttDynamicSeed(context.dynamic,assetClass,
                         EmttInitialVolatilityBucket(percentile),
                         EMTT_REGIME_UNKNOWN,sequence,barTime,false);
      else
         EmttDynamicUpdateVolatility(context.dynamic,percentile,sequence,
                                     barTime,false);

      SEmttRegimeMeasurements measurements;
      if(!EmttMtfBuildMeasurements(context,index,context.dynamic,
                                   measurements))
         return false;
      const bool afterGap=(!first &&
                           (long)(barTime-previousBarTime)>
                           (long)(2*periodSeconds));
      const EEmttRegime regime=EmttRegimeAdvance(context.regime,measurements,
                                                 first||afterGap);
      EmttDynamicUpdateThreshold(context.dynamic,regime,sequence,barTime,
                                 false);

      if(atrSlicePeriod!=context.dynamic.atrPeriod)
        {
         if(!EmttMtfFillAtr(context,context.dynamic.atrPeriod,
                            context.htfBarsFetched,atrSlice))
            return false;
         atrSlicePeriod=context.dynamic.atrPeriod;
        }

      EmttSupertrendAdvance(context.supertrend,context.rates,atrSlice,index,
                            assetClass,context.dynamic.atrPeriod,
                            context.dynamic.volatility,htf,sequence,barTime,
                            first||afterGap,false);
      EmttSmcAdvance(context.smc,context.rates,atrSlice,index,symbol,
                     assetClass,context.dynamic.atrPeriod,
                     context.dynamic.volatility,htf,sequence,barTime,
                     first||afterGap,false);

      context.measurements=measurements;
      previousBarTime=barTime;
      first=false;
      sequence++;
      evaluated++;
     }

   context.htfSequence=sequence;
   context.lastHtfBarTime=context.rates[0].time;
   context.evaluated=(evaluated>0);
   return context.evaluated;
  }

//+------------------------------------------------------------------+
//| 15.9 the published readings and the score of the last evaluation.|
//+------------------------------------------------------------------+
double EmttMtfScore(const SEmttMtfState &state)
  {
   if(!state.ready)
      return 0.0;

   const bool comparable=(state.htfSupertrendDirection!=0 &&
                          state.chartSupertrendDirection!=0);
   const double direction=(comparable &&
                           state.htfSupertrendDirection==
                           state.chartSupertrendDirection ? 1.0 : 0.0);

   double regime=0.0;
   if(EmttIsTrending(state.htfRegime))
      regime=1.0;
   else if(state.htfRegime==EMTT_REGIME_TRANSITION)
      regime=0.5;

   // Nothing to compare on one side is neutral, not a disagreement.
   double structure=0.5;
   if(state.htfBias!=0 && state.chartSmcBias!=0)
      structure=(state.htfBias==state.chartSmcBias ? 1.0 : 0.0);

   return EmttMtfClamp01(EMTT_MTF_WEIGHT_DIRECTION*direction+
                         EMTT_MTF_WEIGHT_REGIME*regime+
                         EMTT_MTF_WEIGHT_STRUCTURE*structure);
  }

void EmttMtfPublish(SEmttMtfState &state,SEmttMtfContext &context,
                    const ENUM_TIMEFRAMES htf,
                    const int chartSupertrendDirection,
                    const int chartSmcBias,const bool ready)
  {
   state.htf=htf;
   state.htfName=EmttMtfName(htf);
   state.htfRegime=context.regime.stable;
   state.htfSupertrendDirection=context.supertrend.direction;
   state.htfCluster=context.supertrend.cluster;
   state.htfMultiplier=context.supertrend.multiplier;
   state.htfBias=context.smc.bias;
   state.htfZone=context.smc.zone;
   state.htfAtrPeriod=context.dynamic.atrPeriod;
   state.htfAtrValue=context.supertrend.atrValue;
   state.htfBarsFetched=context.htfBarsFetched;
   state.chartSupertrendDirection=chartSupertrendDirection;
   state.chartSmcBias=chartSmcBias;
   state.htfBarTime=(ArraySize(context.rates)>0 ? context.rates[0].time : 0);
   state.htfMeasurements=context.measurements;
   state.agrees=0;
   if(state.htfSupertrendDirection!=0 && chartSupertrendDirection!=0)
      state.agrees=(state.htfSupertrendDirection==chartSupertrendDirection ?
                    1 : -1);
   state.ready=ready && context.evaluated;
   state.mtfScore=EmttMtfScore(state);
  }

//+------------------------------------------------------------------+
//| 15.12 journal lines of a full rebuild and of one new HTF bar.    |
//+------------------------------------------------------------------+
void EmttMtfJournalReplay(const SEmttMtfState &state)
  {
   // One summary line after every full rebuild, including init. The reason
   // line of a bucket change is written by the caller before this one, so
   // the summary always comes last.
   PrintFormat("Emtt | MTF context replayed | %s | %d closed bars | regime %s | supertrend %s (%s, %s) | bias %s | zone %s | score %.2f | bar %s",
               state.htfName,state.htfBarsFetched,
               EmttRegimeName(state.htfRegime),
               (state.htfSupertrendDirection>0 ? "up" :
                (state.htfSupertrendDirection<0 ? "down" : "flat")),
               EmttStClusterName(state.htfCluster),
               EmttStMultiplierText(state.htfMultiplier),
               EmttSmcBiasName(state.htfBias),
               (EmttSmcZoneName(state.htfZone)=="" ? "--" :
                EmttSmcZoneName(state.htfZone)),
               state.mtfScore,
               TimeToString(state.htfBarTime,TIME_DATE|TIME_MINUTES));
  }

void EmttMtfJournalBar(SEmttMtfContext &context,
                       const ENUM_TIMEFRAMES htf,
                       const EEmttRegime regimeBefore,
                       const int directionBefore,
                       const int biasBefore,
                       const long chochBefore,const long bosBefore)
  {
   const string name=EmttMtfName(htf);
   const datetime barTime=(ArraySize(context.rates)>0 ?
                           context.rates[0].time : 0);
   if(directionBefore!=0 &&
      context.supertrend.direction!=directionBefore)
      PrintFormat("Emtt | HTF (%s) supertrend turned %s | cluster %s, multiplier %s | bar %s",
                  name,(context.supertrend.direction>0 ? "up" : "down"),
                  EmttStClusterName(context.supertrend.cluster),
                  EmttStMultiplierText(context.supertrend.multiplier),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   if(regimeBefore!=EMTT_REGIME_UNKNOWN &&
      context.regime.stable!=regimeBefore)
      PrintFormat("Emtt | HTF (%s) regime %s -> %s | bar %s",
                  name,EmttRegimeName(regimeBefore),
                  EmttRegimeName(context.regime.stable),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   // The HTF log carries the direction-relevant structure facts only:
   // BOS and CHoCH, never a sweep.
   if(context.smc.lastChochSequence!=chochBefore &&
      context.smc.lastChochSequence>-1000000)
      PrintFormat("Emtt | HTF (%s) structure CHoCH %s | bias %s -> %s | bar %s",
                  name,EmttSmcBiasName(context.smc.lastChochDirection),
                  EmttSmcBiasName(biasBefore),
                  EmttSmcBiasName(context.smc.bias),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   if(context.smc.lastBosSequence!=bosBefore &&
      context.smc.lastBosSequence>-1000000)
      PrintFormat("Emtt | HTF (%s) structure BOS %s | bias %s -> %s | bar %s",
                  name,EmttSmcBiasName(context.smc.lastBosDirection),
                  EmttSmcBiasName(biasBefore),
                  EmttSmcBiasName(context.smc.bias),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
  }

//+------------------------------------------------------------------+
//| 15.8 one new closed HTF bar, on the same code path as the EA's   |
//| own incremental closed-bar update.                               |
//+------------------------------------------------------------------+
bool EmttMtfAdvanceBar(SEmttMtfState &state,SEmttMtfContext &context,
                       const string symbol,
                       const EEmttAssetClass assetClass,
                       const ENUM_TIMEFRAMES htf,
                       const int chartSupertrendDirection,
                       const int chartSmcBias,const bool writeJournal,
                       const bool readyData)
  {
   const EEmttRegime regimeBefore=context.regime.stable;
   const int directionBefore=context.supertrend.direction;
   const int biasBefore=context.smc.bias;
   const long chochBefore=context.smc.lastChochSequence;
   const long bosBefore=context.smc.lastBosSequence;

   const int index=0;
   const long sequence=context.htfSequence;
   const double percentile=EmttPercentileRank(context.atr14,index,
                                              EMTT_VOLATILITY_WINDOW-1);
   if(percentile<0.0)
      return false;
   const datetime barTime=context.rates[index].time;
   int periodSeconds=(int)PeriodSeconds(htf);
   if(periodSeconds<1)
      periodSeconds=1;
   const bool afterGap=(context.lastHtfBarTime>0 &&
                        (long)(barTime-context.lastHtfBarTime)>
                        (long)(2*periodSeconds));

   if(!context.dynamic.initialized)
      EmttDynamicSeed(context.dynamic,assetClass,
                      EmttInitialVolatilityBucket(percentile),
                      EMTT_REGIME_UNKNOWN,sequence,barTime,false);
   else
      EmttDynamicUpdateVolatility(context.dynamic,percentile,sequence,
                                  barTime,false);

   SEmttRegimeMeasurements measurements;
   if(!EmttMtfBuildMeasurements(context,index,context.dynamic,measurements))
      return false;
   const EEmttRegime regime=EmttRegimeAdvance(context.regime,measurements,
                                              afterGap);
   EmttDynamicUpdateThreshold(context.dynamic,regime,sequence,barTime,false);

   double atrSlice[];
   if(!EmttMtfFillAtr(context,context.dynamic.atrPeriod,
                      context.htfBarsFetched,atrSlice))
      return false;
   EmttSupertrendAdvance(context.supertrend,context.rates,atrSlice,index,
                         assetClass,context.dynamic.atrPeriod,
                         context.dynamic.volatility,htf,sequence,barTime,
                         afterGap,false);
   EmttSmcAdvance(context.smc,context.rates,atrSlice,index,symbol,assetClass,
                  context.dynamic.atrPeriod,context.dynamic.volatility,htf,
                  sequence,barTime,afterGap,false);

   context.measurements=measurements;
   context.htfSequence=sequence+1;
   context.lastHtfBarTime=barTime;
   context.evaluated=true;

   if(writeJournal)
      EmttMtfJournalBar(context,htf,regimeBefore,directionBefore,biasBefore,
                        chochBefore,bosBefore);

   // The direction flip is the fact Row 10 reports: it is recorded with
   // the chart sequence of this evaluation (15.10).
   if(directionBefore!=0 &&
      context.supertrend.direction!=directionBefore)
     {
      state.lastFlipChartSequence=state.currentSequence;
      state.lastFlipDirection=context.supertrend.direction;
     }

   EmttMtfPublish(state,context,htf,chartSupertrendDirection,chartSmcBias,
                  readyData);
   return true;
  }

//+------------------------------------------------------------------+
//| Public entry point (15.8). Polled from the chart closed-bar path |
//| after the VolumeFlow advance and once per second by the timer.   |
//| Between HTF closes the MTF state is constant: the poll is an     |
//| iTime comparison, not a measurement.                             |
//+------------------------------------------------------------------+
bool EmttMtfAdvance(SEmttMtfState &state,SEmttMtfContext &context,
                    const string symbol,
                    const EEmttAssetClass assetClass,
                    const ENUM_TIMEFRAMES chartTimeframe,
                    const long chartSequence,
                    const int chartSupertrendDirection,
                    const int chartSmcBias,const bool forceRebuild,
                    const bool writeJournal)
  {
   state.currentSequence=chartSequence;

   const ENUM_TIMEFRAMES htf=EmttMtfTimeframe(chartTimeframe);
   if(htf==PERIOD_CURRENT)
     {
      // Rule 19: no higher timeframe, nothing published, nothing journaled.
      if(context.htf!=PERIOD_CURRENT || state.ready)
         EmttMtfReset(state,context);
      return false;
     }

   if(context.htf!=htf || context.symbol!=symbol)
     {
      if(!EmttMtfCreateHandles(context,symbol,htf))
         return false;
      context.rebuildNeeded=true;
     }
   if(context.assetClass!=assetClass)
     {
      context.assetClass=assetClass;
      context.rebuildNeeded=true;
     }
   if(!EmttMtfEnsureHandles(context,symbol,htf))
      return false;

   const int required=EmttMtfHistoryRequired(htf);
   const int fetchCount=EmttMtfFetchCount(htf);
   const datetime htfBarTime=iTime(symbol,htf,1);
   if(htfBarTime<=0)
      return false;

   const bool barChanged=(htfBarTime!=context.lastHtfBarTime);
   if(!context.rebuildNeeded && !forceRebuild && !barChanged && state.ready)
      return true;
   if(Bars(symbol,htf)<required)
     {
      // Not ready publishes nothing at all - no partial reading, no journal.
      state.ready=false;
      state.mtfScore=0.0;
      return false;
     }

   // Not ready publishes nothing at all - no partial reading, no journal.
   if(!EmttMtfFetchData(context,symbol,htf,fetchCount))
     {
      state.ready=false;
      state.mtfScore=0.0;
      return false;
     }
   const bool readyData=(context.htfBarsFetched>=required &&
                         EmttMtfBuffersCalculated(context,fetchCount));

   const bool rebuild=(context.rebuildNeeded || forceRebuild ||
                       !state.ready || !context.evaluated);
   if(rebuild)
     {
      const EEmttVolatility bucketBefore=context.dynamic.volatility;
      if(!EmttMtfWalk(context,symbol,assetClass,htf))
        {
         state.ready=false;
         state.mtfScore=0.0;
         return false;
        }
      EmttMtfPublish(state,context,htf,chartSupertrendDirection,chartSmcBias,
                     readyData);
      if(writeJournal && bucketBefore!=EMTT_VOL_UNKNOWN &&
         bucketBefore!=context.dynamic.volatility)
         PrintFormat("Emtt | HTF (%s) context rebuilt | volatility %s -> %s | bar %s",
                     EmttMtfName(htf),EmttVolatilityName(bucketBefore),
                     EmttVolatilityName(context.dynamic.volatility),
                     TimeToString(state.htfBarTime,TIME_DATE|TIME_MINUTES));
      if(writeJournal)
         EmttMtfJournalReplay(state);
      context.rebuildNeeded=false;
      context.lastHtfBarTime=htfBarTime;
      return true;
     }

   const EEmttVolatility bucketBefore=context.dynamic.volatility;
   if(!EmttMtfAdvanceBar(state,context,symbol,assetClass,htf,
                         chartSupertrendDirection,chartSmcBias,writeJournal,
                         readyData))
      return false;
   context.lastHtfBarTime=htfBarTime;

   // A changed HTF volatility bucket re-walks the HTF history silently and
   // journals the reason once, exactly as 15.8 requires.
   if(context.dynamic.volatility!=bucketBefore)
     {
      const EEmttVolatility changedFrom=bucketBefore;
      if(!EmttMtfWalk(context,symbol,assetClass,htf))
         return false;
      EmttMtfPublish(state,context,htf,chartSupertrendDirection,chartSmcBias,
                     readyData);
      if(writeJournal)
        {
         PrintFormat("Emtt | HTF (%s) context rebuilt | volatility %s -> %s | bar %s",
                     EmttMtfName(htf),EmttVolatilityName(changedFrom),
                     EmttVolatilityName(context.dynamic.volatility),
                     TimeToString(state.htfBarTime,TIME_DATE|TIME_MINUTES));
         EmttMtfJournalReplay(state);
        }
      context.rebuildNeeded=false;
      context.lastHtfBarTime=htfBarTime;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| 15.10 panel text. The agreement word is recomposed live from the |
//| stored HTF direction and the current chart direction, so it is   |
//| never older than the chart's newest closed bar.                  |
//+------------------------------------------------------------------+
string EmttMtfClause(const SEmttMtfState &state,
                     const int chartSupertrendDirection)
  {
   if(!state.ready)
      return "";
   string clause="";
   int parts=0;

   string regimePart="";
   if(EmttIsTrending(state.htfRegime))
      regimePart=state.htfName+" trending "+
                 (state.htfRegime==EMTT_REGIME_TRENDING_BULLISH ?
                  "up" : "down");
   else if(state.htfRegime==EMTT_REGIME_RANGING)
      regimePart=state.htfName+" ranging";
   else if(state.htfRegime==EMTT_REGIME_VOLATILE)
      regimePart=state.htfName+" volatile";
   else if(state.htfRegime==EMTT_REGIME_TRANSITION)
      regimePart=state.htfName+" transition";
   else if(state.htfRegime==EMTT_REGIME_MARKET_CLOSED)
      regimePart=state.htfName+" closed";
   if(regimePart!="")
     {
      clause=regimePart;
      parts++;
     }

   if(state.htfSupertrendDirection!=0 && chartSupertrendDirection!=0)
     {
      const bool equal=(state.htfSupertrendDirection==
                        chartSupertrendDirection);
      clause+=(parts>0 ? ", " : "")+(equal ? "agrees" : "disagrees");
      parts++;
     }

   const string zone=EmttSmcZoneName(state.htfZone);
   if(zone!="")
     {
      clause+=(parts>0 ? ", " : "")+state.htfName+" "+zone;
      parts++;
     }
   return clause;
  }

string EmttWhyWithMtf(const string priorWhy,const SEmttMtfState &state,
                      const int chartSupertrendDirection)
  {
   const string clause=EmttMtfClause(state,chartSupertrendDirection);
   if(clause=="")
      return priorWhy;
   if(priorWhy=="" || priorWhy=="--")
      return clause;
   return priorWhy+" | "+clause;
  }

// The big picture turning outranks every chart-timeframe fact (15.10).
string EmttStatusForMtf(const SEmttMtfState &state)
  {
   if(!state.ready || state.lastFlipDirection==0)
      return "";
   if(EmttMtfAge(state.currentSequence,state.lastFlipChartSequence)>
      EMTT_MTF_STATUS_FRESH_BARS)
      return "";
   return "Watching — "+state.htfName+" turned "+
          (state.lastFlipDirection>0 ? "up" : "down");
  }

#endif // EMTT_MTF_MQH
