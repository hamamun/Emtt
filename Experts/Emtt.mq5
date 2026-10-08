//+------------------------------------------------------------------+
//|                                                       Emtt.mq5   |
//|                Emtt - MT5 Trading Expert Adviser                 |
//|          Phase 2: foundation, parameters and market regime        |
//|                Spec: Emtt.md | Author: Ham | Coder: Arena        |
//+------------------------------------------------------------------+
#property copyright   "Author: Ham | Coder: Arena"
#property link        ""
#property version     "1.10"
#property description "Emtt V1.0 - MT5 Trading Expert Adviser."
#property description "Phase 2: dynamic parameters, session clock and market regime."
#property description "Allowed analysis timeframes: M5 / M15 / M30 only."

#include "../Include/Emtt/Emtt_Dashboard.mqh"
#include "../Include/Emtt/Emtt_DynamicParams.mqh"
#include "../Include/Emtt/Emtt_Regime.mqh"

input long InpMagicNumber=20251007;   // Magic number
input bool InpAutoTrading=true;       // Auto Trading ON/OFF

//--- Chart / instrument context -------------------------------------
string          g_symbol="";
ENUM_TIMEFRAMES g_timeframe=PERIOD_CURRENT;
EEmttAssetClass g_assetClass=EMTT_CLASS_GENERIC;
int             g_symbolValidationBars=0;

//--- Terminal indicator handles (all calculations read shift >= 1) --
int g_hAtr10=INVALID_HANDLE;
int g_hAtr14=INVALID_HANDLE;
int g_hAtr21=INVALID_HANDLE;
int g_hAtr28=INVALID_HANDLE;
int g_hAtr50=INVALID_HANDLE;
int g_hKama9=INVALID_HANDLE;
int g_hKama13=INVALID_HANDLE;
int g_hKama21=INVALID_HANDLE;
int g_hKama26=INVALID_HANDLE;
int g_hKama34=INVALID_HANDLE;
int g_hKama50=INVALID_HANDLE;
int g_hBands=INVALID_HANDLE;
bool g_handlesReady=false;

//--- Historical indicator buffers, indexed as series: [0] = shift 1 --
double g_atr10[];
double g_atr14[];
double g_atr21[];
double g_atr28[];
double g_atr50[];
double g_kama9[];
double g_kama13[];
double g_kama21[];
double g_kama26[];
double g_kama34[];
double g_kama50[];
double g_bandUpper[];
double g_bandLower[];

//--- Foundation state -----------------------------------------------
SEmttDynamicState          g_dynamic;
SEmttRegimeState           g_regimeState;
SEmttBrokerOffsetState     g_brokerOffset;
SEmttRegimeMeasurements    g_snapshotMeasurements;
EEmttRegime                g_snapshotRegime=EMTT_REGIME_UNKNOWN;
EEmttVolatility            g_snapshotVolatility=EMTT_VOL_UNKNOWN;
double                     g_snapshotPercentile=-1.0;
datetime                   g_snapshotBarTime=0;
bool                       g_snapshotReady=false;
bool                       g_marketOpen=false;
bool                       g_marketWasClosed=false;
string                     g_sessionName="--";
datetime                   g_lastClosedBarTime=0;
long                       g_evaluatedBarSequence=0;
int                        g_historyAvailable=0;
int                        g_historyRequired=EMTT_HISTORY_REQUIRED;

//+------------------------------------------------------------------+
//| Chart timeframe and header helpers                                |
//+------------------------------------------------------------------+
bool TfAllowed()
  {
   return(g_timeframe==PERIOD_M5 || g_timeframe==PERIOD_M15 ||
          g_timeframe==PERIOD_M30);
  }

string TfName(const ENUM_TIMEFRAMES tf)
  {
   const string name=EnumToString(tf);
   if(StringFind(name,"PERIOD_")==0)
      return StringSubstr(name,7);
   return name;
  }

string EmttHeaderText()
  {
   return StringFormat("Emtt V1.0 | %s | TF: %s | Auto Trading: %s",
                       g_symbol,TfName(g_timeframe),
                       (InpAutoTrading ? "ON" : "OFF"));
  }

//+------------------------------------------------------------------+
//| Find Emtt's position only; manual positions are ignored           |
//+------------------------------------------------------------------+
bool EmttOwnPositionOpen()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const string symbol=PositionGetSymbol(i);
      if(symbol=="")
         continue;
      if(symbol==g_symbol && PositionGetInteger(POSITION_MAGIC)==InpMagicNumber)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Indicator lifecycle                                               |
//+------------------------------------------------------------------+
void EmttReleaseIndicators()
  {
   if(g_hAtr10!=INVALID_HANDLE)  IndicatorRelease(g_hAtr10);
   if(g_hAtr14!=INVALID_HANDLE)  IndicatorRelease(g_hAtr14);
   if(g_hAtr21!=INVALID_HANDLE)  IndicatorRelease(g_hAtr21);
   if(g_hAtr28!=INVALID_HANDLE)  IndicatorRelease(g_hAtr28);
   if(g_hAtr50!=INVALID_HANDLE)  IndicatorRelease(g_hAtr50);
   if(g_hKama9!=INVALID_HANDLE)  IndicatorRelease(g_hKama9);
   if(g_hKama13!=INVALID_HANDLE) IndicatorRelease(g_hKama13);
   if(g_hKama21!=INVALID_HANDLE) IndicatorRelease(g_hKama21);
   if(g_hKama26!=INVALID_HANDLE) IndicatorRelease(g_hKama26);
   if(g_hKama34!=INVALID_HANDLE) IndicatorRelease(g_hKama34);
   if(g_hKama50!=INVALID_HANDLE) IndicatorRelease(g_hKama50);
   if(g_hBands!=INVALID_HANDLE)  IndicatorRelease(g_hBands);

   g_hAtr10=INVALID_HANDLE;
   g_hAtr14=INVALID_HANDLE;
   g_hAtr21=INVALID_HANDLE;
   g_hAtr28=INVALID_HANDLE;
   g_hAtr50=INVALID_HANDLE;
   g_hKama9=INVALID_HANDLE;
   g_hKama13=INVALID_HANDLE;
   g_hKama21=INVALID_HANDLE;
   g_hKama26=INVALID_HANDLE;
   g_hKama34=INVALID_HANDLE;
   g_hKama50=INVALID_HANDLE;
   g_hBands=INVALID_HANDLE;
   g_handlesReady=false;
  }

bool EmttCreateIndicators()
  {
   EmttReleaseIndicators();
   g_hAtr10=iATR(g_symbol,g_timeframe,10);
   g_hAtr14=iATR(g_symbol,g_timeframe,14); // fixed volatility measuring stick
   g_hAtr21=iATR(g_symbol,g_timeframe,21);
   g_hAtr28=iATR(g_symbol,g_timeframe,28);
   g_hAtr50=iATR(g_symbol,g_timeframe,50);

   // The matrix's fast / medium / slow values are KAMA lookback periods.
   // Standard KAMA smoothing constants (fast 2, slow 30) remain fixed.
   g_hKama9=iAMA(g_symbol,g_timeframe,9,2,30,0,PRICE_CLOSE);
   g_hKama13=iAMA(g_symbol,g_timeframe,13,2,30,0,PRICE_CLOSE);
   g_hKama21=iAMA(g_symbol,g_timeframe,21,2,30,0,PRICE_CLOSE);
   g_hKama26=iAMA(g_symbol,g_timeframe,26,2,30,0,PRICE_CLOSE);
   g_hKama34=iAMA(g_symbol,g_timeframe,34,2,30,0,PRICE_CLOSE);
   g_hKama50=iAMA(g_symbol,g_timeframe,50,2,30,0,PRICE_CLOSE);
   g_hBands=iBands(g_symbol,g_timeframe,20,0,2.0,PRICE_CLOSE);

   g_handlesReady=(g_hAtr10!=INVALID_HANDLE && g_hAtr14!=INVALID_HANDLE &&
                   g_hAtr21!=INVALID_HANDLE && g_hAtr28!=INVALID_HANDLE &&
                   g_hAtr50!=INVALID_HANDLE && g_hKama9!=INVALID_HANDLE &&
                   g_hKama13!=INVALID_HANDLE && g_hKama21!=INVALID_HANDLE &&
                   g_hKama26!=INVALID_HANDLE && g_hKama34!=INVALID_HANDLE &&
                   g_hKama50!=INVALID_HANDLE && g_hBands!=INVALID_HANDLE);
   if(!g_handlesReady)
      PrintFormat("Emtt | Indicator initialization is waiting for symbol/timeframe data (%s, %s)",
                  g_symbol,TfName(g_timeframe));
   return g_handlesReady;
  }

bool EmttCopySeries(const int handle,const int buffer,const int count,
                    double &destination[])
  {
   if(handle==INVALID_HANDLE || count<=0)
      return false;
   ArrayResize(destination,count);
   ArraySetAsSeries(destination,true);
   const int copied=CopyBuffer(handle,buffer,1,count,destination);
   return(copied==count);
  }

bool EmttCopyRates(const int count,MqlRates &destination[])
  {
   if(count<=0)
      return false;
   ArrayResize(destination,count);
   ArraySetAsSeries(destination,true);
   const int copied=CopyRates(g_symbol,g_timeframe,1,count,destination);
   return(copied==count);
  }

bool EmttValidValue(const double value)
  {
   return(MathIsValidNumber(value) && value!=EMPTY_VALUE);
  }

bool EmttValidPositive(const double value)
  {
   return(EmttValidValue(value) && value>0.0);
  }

//+------------------------------------------------------------------+
//| Access a pre-created indicator buffer by the chosen matrix period |
//+------------------------------------------------------------------+
int EmttAtrHandle(const int period)
  {
   if(period==10) return g_hAtr10;
   if(period==14) return g_hAtr14;
   if(period==21) return g_hAtr21;
   if(period==28) return g_hAtr28;
   return INVALID_HANDLE;
  }

double EmttAtrAt(const int period,const int index)
  {
   if(index<0) return 0.0;
   if(period==10 && index<ArraySize(g_atr10)) return g_atr10[index];
   if(period==14 && index<ArraySize(g_atr14)) return g_atr14[index];
   if(period==21 && index<ArraySize(g_atr21)) return g_atr21[index];
   if(period==28 && index<ArraySize(g_atr28)) return g_atr28[index];
   return 0.0;
  }

double EmttKamaAt(const int period,const int index)
  {
   if(index<0) return 0.0;
   if(period==9  && index<ArraySize(g_kama9))  return g_kama9[index];
   if(period==13 && index<ArraySize(g_kama13)) return g_kama13[index];
   if(period==21 && index<ArraySize(g_kama21)) return g_kama21[index];
   if(period==26 && index<ArraySize(g_kama26)) return g_kama26[index];
   if(period==34 && index<ArraySize(g_kama34)) return g_kama34[index];
   if(period==50 && index<ArraySize(g_kama50)) return g_kama50[index];
   return 0.0;
  }

int EmttKamaHandle(const int period)
  {
   if(period==9)  return g_hKama9;
   if(period==13) return g_hKama13;
   if(period==21) return g_hKama21;
   if(period==26) return g_hKama26;
   if(period==34) return g_hKama34;
   if(period==50) return g_hKama50;
   return INVALID_HANDLE;
  }

//+------------------------------------------------------------------+
//| Closed-bar measurements                                           |
//+------------------------------------------------------------------+
double EmttEfficiencyRatio(const MqlRates &rates[],const int index,
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

bool EmttBuildMeasurements(const MqlRates &rates[],const int index,
                           const SEmttDynamicState &parameters,
                           SEmttRegimeMeasurements &measurements)
  {
   if(index<0 || index>=ArraySize(rates) || index+1>=ArraySize(g_bandUpper) ||
      index+1>=ArraySize(g_bandLower) || index>=ArraySize(g_atr50))
      return false;

   measurements.efficiency=EmttEfficiencyRatio(rates,index,parameters.erPeriod);
   const double fast=EmttKamaAt(parameters.kamaFast,index);
   const double medium=EmttKamaAt(parameters.kamaMedium,index);
   const double slow=EmttKamaAt(parameters.kamaSlow,index);
   const double atr=EmttAtrAt(parameters.atrPeriod,index);
   const double atr50=g_atr50[index];
   const double width=g_bandUpper[index]-g_bandLower[index];
   const double previousWidth=g_bandUpper[index+1]-g_bandLower[index+1];

   if(measurements.efficiency<0.0 || !EmttValidValue(fast) ||
      !EmttValidValue(medium) || !EmttValidValue(slow) ||
      !EmttValidPositive(atr) || !EmttValidPositive(atr50) ||
      !EmttValidPositive(width) || !EmttValidPositive(previousWidth))
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

bool EmttIndicatorsCalculated(const int count)
  {
   if(!g_handlesReady || count<=0)
      return false;
   if(BarsCalculated(g_hAtr10)<count || BarsCalculated(g_hAtr14)<count ||
      BarsCalculated(g_hAtr21)<count || BarsCalculated(g_hAtr28)<count ||
      BarsCalculated(g_hAtr50)<count || BarsCalculated(g_hKama9)<count ||
      BarsCalculated(g_hKama13)<count || BarsCalculated(g_hKama21)<count ||
      BarsCalculated(g_hKama26)<count || BarsCalculated(g_hKama34)<count ||
      BarsCalculated(g_hKama50)<count || BarsCalculated(g_hBands)<count)
      return false;
   return true;
  }

bool EmttCopyFullHistory(const int closedBars,MqlRates &rates[])
  {
   if(!EmttIndicatorsCalculated(closedBars) ||
      closedBars<EMTT_HISTORY_REQUIRED)
      return false;
   if(!EmttCopyRates(closedBars,rates)) return false;
   if(!EmttCopySeries(g_hAtr10,0,closedBars,g_atr10)) return false;
   if(!EmttCopySeries(g_hAtr14,0,closedBars,g_atr14)) return false;
   if(!EmttCopySeries(g_hAtr21,0,closedBars,g_atr21)) return false;
   if(!EmttCopySeries(g_hAtr28,0,closedBars,g_atr28)) return false;
   if(!EmttCopySeries(g_hAtr50,0,closedBars,g_atr50)) return false;
   if(!EmttCopySeries(g_hKama9,0,closedBars,g_kama9)) return false;
   if(!EmttCopySeries(g_hKama13,0,closedBars,g_kama13)) return false;
   if(!EmttCopySeries(g_hKama21,0,closedBars,g_kama21)) return false;
   if(!EmttCopySeries(g_hKama26,0,closedBars,g_kama26)) return false;
   if(!EmttCopySeries(g_hKama34,0,closedBars,g_kama34)) return false;
   if(!EmttCopySeries(g_hKama50,0,closedBars,g_kama50)) return false;
   if(!EmttCopySeries(g_hBands,1,closedBars,g_bandUpper)) return false;
   if(!EmttCopySeries(g_hBands,2,closedBars,g_bandLower)) return false;
   return true;
  }

void EmttSetSnapshot(const SEmttRegimeMeasurements &measurements,
                     const EEmttRegime regime,const double percentile,
                     const datetime barTime)
  {
   g_snapshotMeasurements=measurements;
   g_snapshotRegime=regime;
   g_snapshotPercentile=percentile;
   g_snapshotVolatility=g_dynamic.volatility;
   g_snapshotBarTime=barTime;
   g_snapshotReady=true;
  }

//+------------------------------------------------------------------+
//| Deterministic replay from the first bar with a full 200-ATR window|
//| This reconstructs volatility margins, parameter pauses and regime|
//| confirmation identically after a restart or timeframe change.   |
//+------------------------------------------------------------------+
bool EmttReplayClosedHistory()
  {
   if(!g_handlesReady && !EmttCreateIndicators())
      return false;
   const int totalBars=Bars(g_symbol,g_timeframe);
   int closedBars=totalBars-1;
   if(closedBars<0) closedBars=0;
   g_historyAvailable=closedBars;
   if(g_historyAvailable>EMTT_HISTORY_REQUIRED)
      g_historyAvailable=EMTT_HISTORY_REQUIRED;
   if(closedBars<EMTT_HISTORY_REQUIRED)
     {
      g_snapshotReady=false;
      return false;
     }

   MqlRates rates[];
   if(!EmttCopyFullHistory(closedBars,rates))
     {
      g_snapshotReady=false;
      return false;
     }

   SEmttDynamicState replayDynamic;
   SEmttRegimeState replayRegime;
   EmttDynamicReset(replayDynamic);
   EmttRegimeReset(replayRegime);

   const int evaluationCount=closedBars-(EMTT_HISTORY_REQUIRED-1);
   const int oldestIndex=evaluationCount-1;
   int periodSeconds=PeriodSeconds(g_timeframe);
   if(periodSeconds<1) periodSeconds=1;
   datetime previousBarTime=0;
   long sequence=0;
   bool first=true;

   for(int index=oldestIndex;index>=0;index--)
     {
      const double percentile=EmttPercentileRank(g_atr14,index,
                                                 EMTT_VOLATILITY_WINDOW-1);
      if(percentile<0.0)
        {
         g_snapshotReady=false;
         return false;
        }
      const datetime barTime=rates[index].time;
      if(first)
        {
         const EEmttVolatility initialBucket=EmttInitialVolatilityBucket(percentile);
         EmttDynamicSeed(replayDynamic,g_assetClass,initialBucket,
                         EMTT_REGIME_UNKNOWN,sequence,barTime,false);
        }
      else
         EmttDynamicUpdateVolatility(replayDynamic,percentile,sequence,
                                     barTime,false);

      SEmttRegimeMeasurements measurements;
      if(!EmttBuildMeasurements(rates,index,replayDynamic,measurements))
        {
         g_snapshotReady=false;
         return false;
        }
      const bool afterGap=(!first &&
                           (long)(barTime-previousBarTime)>(long)(2*periodSeconds));
      const EEmttRegime regime=EmttRegimeAdvance(replayRegime,measurements,
                                                  first || afterGap);
      EmttDynamicUpdateThreshold(replayDynamic,regime,sequence,barTime,false);

      if(index==0)
         EmttSetSnapshot(measurements,regime,percentile,barTime);
      previousBarTime=barTime;
      first=false;
      sequence++;
     }

   g_dynamic=replayDynamic;
   g_regimeState=replayRegime;
   g_snapshotVolatility=g_dynamic.volatility;
   g_evaluatedBarSequence=sequence;
   g_lastClosedBarTime=rates[0].time;
   g_historyAvailable=EMTT_HISTORY_REQUIRED;
   PrintFormat("Emtt | Parameters resolved | symbol %s | class %s | volatility %s | ATR %d | ER %d | KAMA %d/%d/%d | confidence threshold %d%% | regime %s | bar %s",
               g_symbol,EmttAssetClassName(g_dynamic.assetClass),
               EmttVolatilityName(g_dynamic.volatility),g_dynamic.atrPeriod,
               g_dynamic.erPeriod,g_dynamic.kamaFast,g_dynamic.kamaMedium,
               g_dynamic.kamaSlow,g_dynamic.confidenceThreshold,
               EmttRegimeName(g_snapshotRegime),
               TimeToString(g_snapshotBarTime,TIME_DATE|TIME_MINUTES));
   return true;
  }

//+------------------------------------------------------------------+
//| Copy one closed-bar indicator value                               |
//+------------------------------------------------------------------+
bool EmttCopyOne(const int handle,const int buffer,const int shift,
                 double &value)
  {
   if(handle==INVALID_HANDLE)
      return false;
   double one[1];
   if(CopyBuffer(handle,buffer,shift,1,one)!=1)
      return false;
   value=one[0];
   return EmttValidValue(value);
  }

bool EmttReadCurrentMeasurements(SEmttRegimeMeasurements &measurements)
  {
   const int maximumErPeriod=28;
   MqlRates recent[];
   ArrayResize(recent,maximumErPeriod+1);
   ArraySetAsSeries(recent,true);
   if(CopyRates(g_symbol,g_timeframe,1,maximumErPeriod+1,recent)!=maximumErPeriod+1)
      return false;
   measurements.efficiency=EmttEfficiencyRatio(recent,0,g_dynamic.erPeriod);

   double fast,medium,slow,atr,atr50;
   if(!EmttCopyOne(EmttKamaHandle(g_dynamic.kamaFast),0,1,fast) ||
      !EmttCopyOne(EmttKamaHandle(g_dynamic.kamaMedium),0,1,medium) ||
      !EmttCopyOne(EmttKamaHandle(g_dynamic.kamaSlow),0,1,slow) ||
      !EmttCopyOne(EmttAtrHandle(g_dynamic.atrPeriod),0,1,atr) ||
      !EmttCopyOne(g_hAtr50,0,1,atr50))
      return false;

   double upperNow,upperPrevious,lowerNow,lowerPrevious;
   if(!EmttCopyOne(g_hBands,1,1,upperNow) ||
      !EmttCopyOne(g_hBands,1,2,upperPrevious) ||
      !EmttCopyOne(g_hBands,2,1,lowerNow) ||
      !EmttCopyOne(g_hBands,2,2,lowerPrevious))
      return false;

   if(measurements.efficiency<0.0 || !EmttValidPositive(atr) ||
      !EmttValidPositive(atr50))
      return false;
   const double width=upperNow-lowerNow;
   const double previousWidth=upperPrevious-lowerPrevious;
   if(width<=0.0 || previousWidth<=0.0)
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
//| Incremental closed-bar update; never called from OnTick           |
//+------------------------------------------------------------------+
bool EmttProcessLatestClosedBar(const bool forceFirstEvaluation)
  {
   if(!g_handlesReady && !EmttCreateIndicators())
      return false;
   const int totalBars=Bars(g_symbol,g_timeframe);
   int closedBars=totalBars-1;
   if(closedBars<0) closedBars=0;
   g_historyAvailable=closedBars;
   if(g_historyAvailable>EMTT_HISTORY_REQUIRED)
      g_historyAvailable=EMTT_HISTORY_REQUIRED;
   if(closedBars<EMTT_HISTORY_REQUIRED)
     {
      g_snapshotReady=false;
      return false;
     }

   double fixedAtr[];
   if(!EmttCopySeries(g_hAtr14,0,EMTT_VOLATILITY_WINDOW,fixedAtr))
     {
      g_snapshotReady=false;
      return false;
     }
   const double percentile=EmttPercentileRank(fixedAtr,0,
                                                EMTT_VOLATILITY_WINDOW-1);
   if(percentile<0.0)
     {
      g_snapshotReady=false;
      return false;
     }

   const datetime barTime=iTime(g_symbol,g_timeframe,1);
   if(barTime<=0)
      return false;
   const long sequence=g_evaluatedBarSequence;
   if(!g_dynamic.initialized)
     {
      const EEmttVolatility firstBucket=EmttInitialVolatilityBucket(percentile);
      EmttDynamicSeed(g_dynamic,g_assetClass,firstBucket,
                      EMTT_REGIME_UNKNOWN,sequence,barTime,true);
      EmttRegimeReset(g_regimeState);
     }
   else
      EmttDynamicUpdateVolatility(g_dynamic,percentile,sequence,barTime,true);

   SEmttRegimeMeasurements measurements;
   if(!EmttReadCurrentMeasurements(measurements))
     {
      g_snapshotReady=false;
      return false;
     }
   int periodSeconds=PeriodSeconds(g_timeframe);
   if(periodSeconds<1) periodSeconds=1;
   const bool afterGap=(g_lastClosedBarTime>0 &&
                        (long)(barTime-g_lastClosedBarTime)>(long)(2*periodSeconds));
   const EEmttRegime regime=EmttRegimeAdvance(g_regimeState,measurements,
                           forceFirstEvaluation || afterGap);
   EmttDynamicUpdateThreshold(g_dynamic,regime,sequence,barTime,true);

   EmttSetSnapshot(measurements,regime,percentile,barTime);
   g_lastClosedBarTime=barTime;
   g_evaluatedBarSequence++;
   return true;
  }

//+------------------------------------------------------------------+
//| Revalidate symbol class every 100 newly processed closed bars    |
//+------------------------------------------------------------------+
void EmttResetMarketState()
  {
   EmttDynamicReset(g_dynamic);
   EmttRegimeReset(g_regimeState);
   g_marketWasClosed=false;
   g_snapshotReady=false;
   g_snapshotRegime=EMTT_REGIME_UNKNOWN;
   g_snapshotVolatility=EMTT_VOL_UNKNOWN;
   g_snapshotPercentile=-1.0;
   g_snapshotBarTime=0;
   g_lastClosedBarTime=0;
   g_evaluatedBarSequence=0;
   g_historyAvailable=0;
  }

bool EmttAdoptChartContext(const bool journalTimeframeChange)
  {
   const string newSymbol=ChartSymbol(0);
   const ENUM_TIMEFRAMES newTimeframe=(ENUM_TIMEFRAMES)ChartPeriod(0);
   const EEmttAssetClass newClass=EmttClassifySymbol(newSymbol);
   const bool symbolChanged=(newSymbol!=g_symbol);
   const bool timeframeChanged=(newTimeframe!=g_timeframe);
   const bool classChanged=(newClass!=g_assetClass);
   if(!symbolChanged && !timeframeChanged && !classChanged)
      return false;

   const string oldSymbol=g_symbol;
   const ENUM_TIMEFRAMES oldTimeframe=g_timeframe;
   const EEmttAssetClass oldClass=g_assetClass;
   g_symbol=newSymbol;
   g_timeframe=newTimeframe;
   g_assetClass=newClass;
   EmttReleaseIndicators();
   EmttResetMarketState();
   EmttCreateIndicators();
   g_symbolValidationBars=0;

   if(symbolChanged || classChanged)
      PrintFormat("Emtt | Symbol revalidated | %s (%s) -> %s (%s) | closed-bar context rebuilt",
                  oldSymbol,EmttAssetClassName(oldClass),g_symbol,
                  EmttAssetClassName(g_assetClass));
   if(timeframeChanged && journalTimeframeChange)
      PrintFormat("Emtt | Timeframe changed %s -> %s | re-reading closed-bar history and resolving the new context",
                  TfName(oldTimeframe),TfName(g_timeframe));
   return true;
  }

void EmttRevalidateSymbolClass()
  {
   g_symbolValidationBars++;
   if(g_symbolValidationBars<100)
      return;
   g_symbolValidationBars=0;
   const string detectedSymbol=ChartSymbol(0);
   const EEmttAssetClass detectedClass=EmttClassifySymbol(detectedSymbol);
   if(detectedSymbol!=g_symbol || detectedClass!=g_assetClass)
      EmttAdoptChartContext(false);
  }

string EmttFrozenContextKey()
  {
   const string normalized=EmttNormalizeSymbol(g_symbol);
   long hash=0;
   for(int i=0;i<StringLen(normalized);i++)
      hash=(hash*131+(long)StringGetCharacter(normalized,i))%2147483629;
   return StringFormat("Emtt_FP_%I64d_%I64d",InpMagicNumber,hash);
  }

// Persist only the confidence threshold captured for this open position.
// Later management phases can extend this same entry snapshot with their own
// values; this phase deliberately defines no management parameters.
void EmttSyncFrozenPositionContext()
  {
   const string key=EmttFrozenContextKey();
   if(EmttOwnPositionOpen())
     {
      bool storeSnapshot=!GlobalVariableCheck(key);
      if(!storeSnapshot)
        {
         const int saved=(int)GlobalVariableGet(key);
         if(saved>0 && saved<=100)
           {
            g_dynamic.confidenceThreshold=saved;
            g_dynamic.frozenThreshold=saved;
            g_dynamic.thresholdFrozen=true;
           }
         else
            storeSnapshot=true;
        }
      if(!g_dynamic.thresholdFrozen && g_dynamic.initialized)
        {
         EmttDynamicFreezeAtEntry(g_dynamic);
         storeSnapshot=g_dynamic.thresholdFrozen;
        }
      if(g_dynamic.thresholdFrozen && storeSnapshot)
        {
         GlobalVariableSet(key,(double)g_dynamic.frozenThreshold);
         GlobalVariablesFlush();
        }
     }
   else
     {
      EmttDynamicThawAfterClose(g_dynamic);
      if(GlobalVariableCheck(key))
         GlobalVariableDel(key);
     }
  }

//+------------------------------------------------------------------+
//| Volatility/regime/session refresh runs only on the one-second timer|
//+------------------------------------------------------------------+
void EmttRefreshFoundation()
  {
   EmttAdoptChartContext(true);
   const datetime serverNow=(TimeTradeServer()>0 ? TimeTradeServer() : TimeCurrent());
   const datetime gmtNow=TimeGMT();
   const datetime utcNow=EmttSessionUtcNow(g_brokerOffset,serverNow,gmtNow);

   if(!TfAllowed())
     {
      g_marketOpen=false;
      g_sessionName="--";
      EmttSyncFrozenPositionContext();
      UpdatePanel();
      return;
     }

   const datetime formingBar=iTime(g_symbol,g_timeframe,0);
   g_marketOpen=EmttMarketIsOpen(g_symbol,g_timeframe,serverNow,formingBar);
   g_sessionName=(g_marketOpen ? EmttSessionNameUtc(utcNow) : "--");

   if(!g_marketOpen)
     {
      // Closed applies immediately, without waiting for history or a new bar.
      EmttRegimeMarkMarketClosed(g_regimeState);
      g_marketWasClosed=true;
     }
   else
     {
      const datetime latestClosed=iTime(g_symbol,g_timeframe,1);
      if(latestClosed>0 && latestClosed!=g_lastClosedBarTime)
        {
         if(!g_snapshotReady)
           {
            if(EmttReplayClosedHistory())
               g_marketWasClosed=false;
           }
         else
           {
            const bool forceFirst=g_marketWasClosed;
            if(EmttProcessLatestClosedBar(forceFirst))
              {
               g_marketWasClosed=false;
               EmttRevalidateSymbolClass();
              }
           }
        }
      else if(!g_snapshotReady && EmttReplayClosedHistory())
         g_marketWasClosed=false;
     }

   EmttSyncFrozenPositionContext();
   UpdatePanel();
  }

//+------------------------------------------------------------------+
//| Build the Phase-2 panel snapshot without changing the renderer    |
//+------------------------------------------------------------------+
void FillPanel(SEmttPanelData &d)
  {
   const bool compatible=TfAllowed();
   MqlTick tick;
   double bid=0.0,ask=0.0;
   if(SymbolInfoTick(g_symbol,tick))
     {
      bid=tick.bid;
      ask=tick.ask;
     }
   else
     {
      bid=SymbolInfoDouble(g_symbol,SYMBOL_BID);
      ask=SymbolInfoDouble(g_symbol,SYMBOL_ASK);
     }
   const int digits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
   const double point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   int spreadPts=0;
   if(point>0.0)
      spreadPts=(int)MathRound((ask-bid)/point);

   d.header=EmttHeaderText();
   d.signalClr=EMTT_CLR_TEXT;
   d.signalSize=EMTT_FSIZE;
   d.statusClr=EMTT_CLR_TEXT;
   d.floatingClr=EMTT_CLR_TEXT;
   d.showLive=false;

   // Phase 2 fills only the fields it actually measures. Signal/trade values
   // stay label-only until their implementing phases have been requested.
   d.regime="Regime:";
   d.signal="SIGNAL:";
   d.confidence="Confidence:";
   d.entry="Entry:";
   d.stopLoss="Stop Loss:";
   d.takeProfit="Take Profit:";
   d.riskReward="Risk:Reward:";
   d.session="Session:  |  Expected Duration:";
   d.why="--";
   d.status="";

   if(!compatible)
     {
      // Rule 19 wins over all state messages on unsupported timeframes.
      d.regime="Regime: --";
      d.session="Session: -- | Expected Duration:";
      d.why="--";
      d.status="Incompatible chart. Switch to M5/M15/M30.";
      d.statusClr=EMTT_CLR_SELL;
     }
   else if(!g_marketOpen)
     {
      d.regime="Regime: MARKET CLOSED";
      d.session="Session: -- | Expected Duration:";
      d.why="--";
      d.status=EmttStatusForRegime(EMTT_REGIME_MARKET_CLOSED);
     }
   else
     {
      d.session="Session: "+g_sessionName+" | Expected Duration:";
      if(!g_snapshotReady)
        {
         d.regime="Regime: --";
         d.why="--";
         d.status=StringFormat("Waiting — Loading chart history (%d/%d candles)",
                               g_historyAvailable,g_historyRequired);
        }
      else
        {
         d.regime="Regime: "+EmttRegimeName(g_snapshotRegime);
         d.why=EmttRegimeWhyPending(g_regimeState.pending,
                                    g_snapshotMeasurements,
                                    g_snapshotVolatility);
         if(d.why=="")
            d.why=EmttRegimeWhy(g_snapshotRegime,g_snapshotMeasurements,
                                g_snapshotVolatility);
         d.status=EmttStatusForPending(g_regimeState.pending);
         if(d.status=="")
            d.status=EmttStatusForRegime(g_snapshotRegime);
        }
     }

   // A live Emtt position is detected by symbol + magic; manual trades never
   // make the block appear. Phase 2 intentionally does not invent trade data.
   if(EmttOwnPositionOpen())
     {
      d.showLive=true;
      d.liveHeader=EmttGlyph(EMTT_G_DIAMOND)+" LIVE TRADE";
      d.ticket="Ticket:";
      d.floatingPL="Floating P/L:";
      d.liveSL="Live SL:";
      d.protect="Protect:";
     }

   d.priceRow="Bid: "+DoubleToString(bid,digits)+"  |  "+
              "Ask: "+DoubleToString(ask,digits)+"  |  "+
              "Spread: "+IntegerToString(spreadPts)+" pts";
  }

void UpdatePanel()
  {
   SEmttPanelData data;
   FillPanel(data);
   EmttDashboardRender(data);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| Detect a timeframe switch even when the EA is reinitialized       |
//+------------------------------------------------------------------+
void EmttJournalTimeframeContext()
  {
   const string key=StringFormat("Emtt_TF_%I64d",ChartID());
   if(GlobalVariableCheck(key))
     {
      const ENUM_TIMEFRAMES previous=(ENUM_TIMEFRAMES)(int)GlobalVariableGet(key);
      if(previous!=g_timeframe)
         PrintFormat("Emtt | Timeframe changed %s -> %s | re-reading closed-bar history and resolving the new context",
                     TfName(previous),TfName(g_timeframe));
     }
   GlobalVariableSet(key,(double)g_timeframe);
  }

//+------------------------------------------------------------------+
//| Expert initialization / cleanup                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_symbol=ChartSymbol(0);
   g_timeframe=(ENUM_TIMEFRAMES)ChartPeriod(0);
   g_assetClass=EmttClassifySymbol(g_symbol);
   EmttDynamicReset(g_dynamic);
   EmttRegimeReset(g_regimeState);
   EmttJournalTimeframeContext();
   EmttCreateIndicators();

   EmttDashboardInit(EmttHeaderText());
   ChartSetInteger(0,CHART_EVENT_MOUSE_MOVE,true);
   EventSetTimer(1);
   EmttRefreshFoundation();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(EmttOwnPositionOpen() && g_dynamic.thresholdFrozen)
     {
      GlobalVariableSet(EmttFrozenContextKey(),(double)g_dynamic.frozenThreshold);
      GlobalVariablesFlush();
     }
   ChartSetInteger(0,CHART_EVENT_MOUSE_MOVE,false);
   EmttReleaseIndicators();
   EmttDashboardShutdown();
  }

// Ticks update only the live price row / panel; no indicators run here.
void OnTick()
  {
   UpdatePanel();
  }

void OnTimer()
  {
   EmttRefreshFoundation();
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,
                  const string &sparam)
  {
   EmttDashboardChartEvent(id,lparam,dparam,sparam);
  }
//+------------------------------------------------------------------+
