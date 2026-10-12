//+------------------------------------------------------------------+
//|                                                       Emtt.mq5   |
//|                Emtt - MT5 Trading Expert Adviser                 |
//| Phase 6: signal and trade plan                                    |
//| Phase 7: self-learning signal filter                             |
//| Phase 8: live trading - order, management, record                 |
//| Phase 9: parameter-optimization persistence                       |
//|                Spec: Emtt.md | Author: Ham | Coder: Arena        |
//+------------------------------------------------------------------+
#property copyright   "Author: Ham | Coder: Arena"
#property link        ""
#property version     "1.90"
// Keep combined description text below MQL5's 511-character limit.
#property description "Emtt V1.0 - MT5 Trading Expert Adviser."
#property description "Phase 5: closed-bar volume flow (VWAP, profile, CVD) and higher-timeframe agreement."
#property description "Phase 6: signal and trade plan (no orders)."
#property description "Phase 7: self-learning signal filter."
#property description "Phase 8: live trading - order, management, record."
#property description "Phase 9: parameter-optimization persistence."
#property description "Phase 10: tick-level CVD divergence detection for the trailing stop."
#property description "Phase 11: graded confidence tiers and continuous signal display."
// Panel revamp: WHY removed, STATUS single-line, Summary Today/All-Time, dynamic width.
#property description "Allowed analysis timeframes: M5 / M15 / M30 only."

#include "../Include/Emtt/Emtt_Dashboard.mqh"
#include "../Include/Emtt/Emtt_DynamicParams.mqh"
#include "../Include/Emtt/Emtt_Regime.mqh"
#include "../Include/Emtt/Emtt_Supertrend.mqh"
#include "../Include/Emtt/Emtt_SMC.mqh"
#include "../Include/Emtt/Emtt_VolumeFlow.mqh"
#include "../Include/Emtt/Emtt_MTF.mqh"
#include "../Include/Emtt/Emtt_TradePlan.mqh"
#include "../Include/Emtt/Emtt_Tier.mqh"
#include "../Include/Emtt/Emtt_Signal.mqh"
#include "../Include/Emtt/Emtt_Summary.mqh"
#include "../Include/Emtt/Emtt_LearnFile.mqh"
#include "../Include/Emtt/Emtt_Learning.mqh"
#include "../Include/Emtt/Emtt_ParamFile.mqh"
#include "../Include/Emtt/Emtt_ParamOpt.mqh"
#include "../Include/Emtt/Emtt_TickDivergence.mqh"
#include "../Include/Emtt/Emtt_Trade.mqh"
#include "../Include/Emtt/Emtt_TradeManager.mqh"

input long InpMagicNumber=20251007;   // Magic number
input bool InpParamOptimization=true; // Parameter optimization ON/OFF

input group "Auto Trading"
input bool InpAutoTrading=false;      // Auto Trading ON/OFF
input int  InpAutoTradeAbove=56;      // Auto-trade above (%)
input ENUM_EMTT_LOT_MODE InpLotMode=EMTT_LOT_AUTO;  // Lot size: Auto / Minimum
input bool InpMarginCheck=false;      // Require free-margin check
input bool InpPlaceStopLoss=false;    // Place stop loss with the order
input int InpPendingValidityBars=6;   // Pending entry validity (1-96 bars)

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
SEmttSupertrendState       g_supertrend;
SEmttSmcState              g_smc;
SEmttVolumeFlowState       g_volumeFlow;
SEmttMtfState              g_mtf;
SEmttMtfContext            g_mtfContext;
SEmttSignalState           g_signal;
SEmttSummaryState          g_summary;
SEmttLearningState         g_learning;
SEmttParamOptState g_paramOpt;
SEmttTickDivergenceState g_tickDiv;
// Phase 11 (28.4): the "Auto-trade above (%)" input, clamped to 35..100.
int                        g_autoTradeAbove=EMTT_TIER_AUTO_DEFAULT;
SEmttTradeState            g_trade;
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
// 11.8: the gate is timeframe-derived (training window + ATR(50) baseline),
// so this carries the resolved 250 / 300 / 350 instead of a fixed constant.
int                        g_historyRequired=EMTT_ST_WINDOW_BASE+EMTT_ST_ATR_BASELINE_BARS;

// Phase 4 / 5 keep the one loading gate extensible: before volatility has a
// closed-bar bucket, use the same matrix's worst case for this class. The
// gate is the max() of the Supertrend, structure and volume-flow needs.
int EmttResolveHistoryRequired(const ENUM_TIMEFRAMES timeframe)
  {
   EEmttVolatility bucket=EMTT_VOL_HIGH;
   if(g_dynamic.initialized && g_dynamic.volatility!=EMTT_VOL_UNKNOWN)
      bucket=g_dynamic.volatility;
   const int supertrendRequired=EmttHistoryRequired(timeframe);
   const int smcRequired=EmttSmcHistoryRequired(g_assetClass,bucket,timeframe);
   const int volumeFlowRequired=EmttVfHistoryRequired(g_assetClass,bucket,
                                                      timeframe);
   return (int)MathMax(supertrendRequired,
                       (int)MathMax(smcRequired,volumeFlowRequired));
  }

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

   // 15.1: the HTF handle set belongs to the MTF context only and is
   // released with the chart handles on every context change and on exit.
   EmttMtfFree(g_mtfContext);
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

// 15.3: the volume-flow window is copied up to the requested depth - a
// chart that holds fewer closed bars still reaches the profile window the
// history gate guarantees, and the session parts stay honestly blank.
bool EmttCopyRatesUpTo(const int count,MqlRates &destination[])
  {
   if(count<=0)
      return false;
   ArrayResize(destination,count);
   ArraySetAsSeries(destination,true);
   const int copied=CopyRates(g_symbol,g_timeframe,1,count,destination);
   if(copied<=0)
      return false;
   if(copied<ArraySize(destination))
      ArrayResize(destination,copied);
   return true;
  }

bool EmttCopySeriesUpTo(const int handle,const int buffer,const int count,
                        double &destination[])
  {
   if(handle==INVALID_HANDLE || count<=0)
      return false;
   ArrayResize(destination,count);
   ArraySetAsSeries(destination,true);
   const int copied=CopyBuffer(handle,buffer,1,count,destination);
   if(copied<=0)
      return false;
   if(copied<ArraySize(destination))
      ArrayResize(destination,copied);
   return true;
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
//| 15.10 Row 10 wording. The structure context-only line is not a    |
//| fresh fact: it must not mask a fresh CVD flip or the combined     |
//| context-only line. Its text is owned by EmttStatusForSmc(), which |
//| stays byte-identical; only a comparison lives here.               |
//+------------------------------------------------------------------+
#define EMTT_ROW10_CONTEXT_ONLY "Watching — context only, no signal yet"
#define EMTT_ROW10_SMC_CONTEXT  "Watching — structure context only, no signal yet"

bool EmttSmcStatusIsContextOnly(const string status)
  {
   return(status==EMTT_ROW10_SMC_CONTEXT);
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
      closedBars<g_historyRequired)
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
   g_historyRequired=EmttResolveHistoryRequired(g_timeframe);
   const int totalBars=Bars(g_symbol,g_timeframe);
   int closedBars=totalBars-1;
   if(closedBars<0) closedBars=0;
   g_historyAvailable=closedBars;
   if(g_historyAvailable>g_historyRequired)
      g_historyAvailable=g_historyRequired;
   if(closedBars<g_historyRequired)
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
   SEmttSupertrendState replaySupertrend;
   SEmttSmcState replaySmc;
   EmttDynamicReset(replayDynamic);
   EmttRegimeReset(replayRegime);
   EmttSupertrendReset(replaySupertrend);
   EmttSmcReset(replaySmc);
   // Phase 5 is replayed on the same path from a clean state, so a restart
   // reproduces the same anchor, VWAP, profile, CVD and score (15.12).
   EmttVfReset(g_volumeFlow);
   g_mtfContext.rebuildNeeded=true;

   // Phase 3 is replayed on the same path, so a restart reproduces the same
   // clusters, multiplier, direction, line and score (11.9). The ATR window
   // is rebuilt per bar at the period that bar resolved to.
   const int supertrendWindow=EmttSupertrendWindow(g_timeframe);
   double supertrendAtr[];
   ArrayResize(supertrendAtr,closedBars);
   ArraySetAsSeries(supertrendAtr,true);
   // SMC uses the matrix ATR that each replayed bar resolved to. The fixed
   // ATR(14) initialization is only a valid fallback for pre-evaluation bars
   // during a silent parameter-rebuild horizon.
   double smcAtr[];
   ArrayResize(smcAtr,closedBars);
   ArraySetAsSeries(smcAtr,true);
   for(int k=0;k<closedBars;k++)
      smcAtr[k]=g_atr14[k];

   const int evaluationCount=closedBars-(g_historyRequired-1);
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

      // Phase 3 runs after the bucket and atrPeriod of this bar are known and
      // before the snapshot, exactly as in the incremental path.
      if(index+supertrendWindow<=closedBars)
        {
         for(int k=index;k<index+supertrendWindow;k++)
            supertrendAtr[k]=EmttAtrAt(replayDynamic.atrPeriod,k);
         EmttSupertrendAdvance(replaySupertrend,rates,supertrendAtr,index,
                               g_assetClass,replayDynamic.atrPeriod,
                               replayDynamic.volatility,g_timeframe,sequence,
                               barTime,first || afterGap,false);
        }

      // Phase 4 follows the same closed-bar path, after this bar's bucket and
      // Supertrend context and before the snapshot. Nothing reaches OnTick().
      smcAtr[index]=EmttAtrAt(replayDynamic.atrPeriod,index);
      EmttSmcAdvance(replaySmc,rates,smcAtr,index,g_symbol,g_assetClass,
                     replayDynamic.atrPeriod,replayDynamic.volatility,
                     g_timeframe,sequence,barTime,first || afterGap,false);

      // Phase 5 volume flow follows the same closed-bar path: it sees this
      // bar's bucket and atrPeriod and journals nothing while replaying.
      EmttVolumeFlowAdvance(g_volumeFlow,rates,smcAtr,index,g_symbol,
                            g_assetClass,replayDynamic.atrPeriod,
                            replayDynamic.volatility,g_timeframe,sequence,
                            first || afterGap,false);

      // The higher-timeframe context is polled on the same path; it rebuilds
      // itself once (and journals its summary) and then stays constant until
      // the HTF's last closed bar changes (15.8).
      EmttMtfAdvance(g_mtf,g_mtfContext,g_symbol,g_assetClass,g_timeframe,
                     sequence,replaySupertrend.direction,replaySmc.bias,
                     false,true);

      if(index==0)
         EmttSetSnapshot(measurements,regime,percentile,barTime);
      previousBarTime=barTime;
      first=false;
      sequence++;
     }

   g_dynamic=replayDynamic;
   g_regimeState=replayRegime;
   g_supertrend=replaySupertrend;
   g_smc=replaySmc;
   g_snapshotVolatility=g_dynamic.volatility;
   g_evaluatedBarSequence=sequence;
   // Do not publish a completed replay until the newest closed candle can
   // be evaluated. HTF history/indicator buffers can arrive asynchronously.
   // Retry on the next timer, before any learning load or signal events.
   MqlRates signalReplayBar[1];
   double signalAtr=0.0;
   MqlTick signalTick;
   if(!EmttSignalViewsReady(g_supertrend,g_smc,g_volumeFlow,g_mtf) ||
      CopyRates(g_symbol,g_timeframe,1,1,signalReplayBar)!=1 ||
      signalReplayBar[0].time!=rates[0].time ||
      !EmttCopyOne(EmttAtrHandle(g_dynamic.atrPeriod),0,1,signalAtr) ||
      !EmttSigValidPositive(signalAtr) ||
      !SymbolInfoTick(g_symbol,signalTick) ||
      !EmttSigValidPositive(signalTick.bid) ||
      !EmttSigValidPositive(signalTick.ask))
     {
      g_snapshotReady=false;
      return false;
     }
   g_lastClosedBarTime=rates[0].time;
   g_historyAvailable=g_historyRequired;
   PrintFormat("Emtt | Parameters resolved | symbol %s | class %s | volatility %s | ATR %d | ER %d | KAMA %d/%d/%d | confidence threshold %d%% | regime %s | bar %s",
               g_symbol,EmttAssetClassName(g_dynamic.assetClass),
               EmttVolatilityName(g_dynamic.volatility),g_dynamic.atrPeriod,
               g_dynamic.erPeriod,g_dynamic.kamaFast,g_dynamic.kamaMedium,
               g_dynamic.kamaSlow,g_dynamic.confidenceThreshold,
               EmttRegimeName(g_snapshotRegime),
               TimeToString(g_snapshotBarTime,TIME_DATE|TIME_MINUTES));
   PrintFormat("Emtt | Regime %s | ER %.1f | KAMA %s | ATR ratio %.2f | bar %s",
               EmttRegimeName(g_snapshotRegime),g_snapshotMeasurements.efficiency,
               (g_snapshotMeasurements.direction>0 ? "up" :
                (g_snapshotMeasurements.direction<0 ? "down" : "mixed")),
               g_snapshotMeasurements.atrRatio,
               TimeToString(g_snapshotBarTime,TIME_DATE|TIME_MINUTES));
   if(g_supertrend.ready)
      PrintFormat("Emtt | Supertrend replayed | window %d closed bars (%s x%.2f) | ATR period %d | cluster %s | multiplier %s | direction %s | score %.2f | bar %s",
                  g_supertrend.window,TfName(g_timeframe),
                  EmttLookbackScale(g_timeframe),g_supertrend.atrPeriod,
                  EmttStClusterName(g_supertrend.cluster),
                  EmttStMultiplierText(g_supertrend.multiplier),
                  EmttStDirectionName(g_supertrend.direction),
                  g_supertrend.score,
                  TimeToString(g_snapshotBarTime,TIME_DATE|TIME_MINUTES));
   if(g_volumeFlow.ready)
      PrintFormat("Emtt | Volume flow replayed | window %d closed bars (%s x%.2f) | session %s | VWAP %s | CVD %s | POC %s | naked POC %s | score %.2f | bar %s",
                  g_volumeFlow.profileWindow,TfName(g_timeframe),
                  EmttLookbackScale(g_timeframe),
                  (g_volumeFlow.sessionName=="" ? "--" :
                   g_volumeFlow.sessionName),
                  EmttVfReadingText(g_volumeFlow.hasVwap,g_symbol,
                                    g_volumeFlow.vwap),
                  EmttVfFlowText(g_volumeFlow),
                  EmttVfReadingText(g_volumeFlow.hasProfile,g_symbol,
                                    g_volumeFlow.poc),
                  EmttVfReadingText(g_volumeFlow.priorPocAvailable &&
                                    g_volumeFlow.priorPocNaked,g_symbol,
                                    g_volumeFlow.priorPoc),
                  g_volumeFlow.volumeFlowScore,
                  TimeToString(g_snapshotBarTime,TIME_DATE|TIME_MINUTES));
   if(g_smc.ready)
     {
      string structureZone=EmttSmcZoneName(g_smc.zone);
      if(structureZone=="") structureZone="--";
      string structureOb="--";
      if(g_smc.hasOrderBlock)
         structureOb=DoubleToString(g_smc.orderBlockNearEdge,
                                    (int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS));
      PrintFormat("Emtt | Structure replayed | window %d closed bars (%s x%.2f) | swing strength %d | bias %s | zone %s | OB %s | score %.2f | bar %s",
                  g_smc.structureWindow,TfName(g_timeframe),
                  EmttLookbackScale(g_timeframe),g_smc.swingStrength,
                  EmttSmcBiasName(g_smc.bias),structureZone,structureOb,
                  g_smc.smcScore,
                  TimeToString(g_snapshotBarTime,TIME_DATE|TIME_MINUTES));
     }

   // Phase 7 (19.3, 19.6): the closed-bar replay is complete. The learning
   // record of this symbol + timeframe is bound and loaded - event 1 writes
   // it back normalised and applies the cap - and the learned terms of the
   // newest closed bar are evaluated, so the signal call below sees exactly
   // the number of 19.5.
   // 23.2: the replay uses the init-loaded bar but never collects evidence.
   EmttParamOptEndNear(g_paramOpt,EMTT_LEARN_RESULT_CHART,
                       g_signal.lastClose,g_signal.lastSequence,
                       g_signal.lastBarTime,false);
   g_paramOpt.liveCandle=false;
   g_paramOpt.replaying=true;
   EmttLearningAttachAndLoad(rates[0].time);

   // Phase 6 (17.8): the replay rebuilds the four views and then evaluates
   // the signal once at the newest closed bar; the market-price Entry is the
   // one value that depends on the live quote. Phase 7 (19.6): when the file
   // holds an open plan, that plan is the one that resumes - the evaluation
   // is not run for it, because the gap is checked against the plan's own
   // levels and the signal is next evaluated at the first post-replay
   // closed candle.
   // Inputs were checked before loading persistent learning state above.
     {
      const double signalBid=signalTick.bid;
      const double signalAsk=signalTick.ask;
      const double signalPoint=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
      const int signalDigits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
      int signalSpread=0;
      if(signalPoint>0.0)
         signalSpread=(int)MathRound((signalAsk-signalBid)/signalPoint);
      const EEmttRegime signalMood=
        (g_regimeState.pending!=EMTT_REGIME_UNKNOWN ?
         g_regimeState.pending : g_snapshotRegime);
      EmttLearningReadCandle(signalMood,signalAtr);
      if(!EmttLearningResumePending())
        {
         SEmttLearnScoreSnapshot learningScores;
         EmttLearningSaveScores(learningScores);
         EmttLearningScaleScores(learningScores,g_learning.reading.scale);
         EmttSignalAdvance(g_signal,g_supertrend,g_smc,g_volumeFlow,g_mtf,
                           signalMood,EmttParamOptBar(g_paramOpt,signalMood),
                           signalAtr,signalReplayBar[0].high,
                           signalReplayBar[0].low,signalReplayBar[0].close,
                           signalBid,signalAsk,signalSpread,g_timeframe,
                           g_evaluatedBarSequence-1,rates[0].time,
                           signalDigits,signalPoint,false);
         EmttLearningRestoreScores(learningScores);
         EmttConsumeSignalEvents(rates[0].time,signalReplayBar[0].high,
                                 signalReplayBar[0].low,signalSpread,
                                 signalAtr);
         EmttJournalSignalState(rates[0].time);
        }
      else
         EmttLearningResume(rates[0].time,rates,signalMood);
     }
   g_paramOpt.replaying=false;
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
   g_historyRequired=EmttResolveHistoryRequired(g_timeframe);
   const int totalBars=Bars(g_symbol,g_timeframe);
   int closedBars=totalBars-1;
   if(closedBars<0) closedBars=0;
   g_historyAvailable=closedBars;
   if(g_historyAvailable>g_historyRequired)
      g_historyAvailable=g_historyRequired;
   if(closedBars<g_historyRequired)
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
   const EEmttRegime previousRegime=g_regimeState.stable;
   const EEmttRegime regime=EmttRegimeAdvance(g_regimeState,measurements,
                           forceFirstEvaluation || afterGap);
   if(regime!=previousRegime || forceFirstEvaluation || afterGap)
      PrintFormat("Emtt | Regime %s | ER %.1f | KAMA %s | ATR ratio %.2f | bar %s",
                  EmttRegimeName(regime),measurements.efficiency,
                  (measurements.direction>0 ? "up" :
                   (measurements.direction<0 ? "down" : "mixed")),
                  measurements.atrRatio,
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   EmttDynamicUpdateThreshold(g_dynamic,regime,sequence,barTime,true);

   // Phase 3: after the bucket / atrPeriod of this bar, before the snapshot.
   // Closed bars only - the per-tick path never reaches this function.
   const int supertrendWindow=EmttSupertrendWindow(g_timeframe);
   MqlRates supertrendRates[];
   double supertrendAtr[];
   if(EmttCopyRates(supertrendWindow,supertrendRates) &&
      EmttCopySeries(EmttAtrHandle(g_dynamic.atrPeriod),0,supertrendWindow,
                     supertrendAtr))
      EmttSupertrendAdvance(g_supertrend,supertrendRates,supertrendAtr,0,
                            g_assetClass,g_dynamic.atrPeriod,
                            g_dynamic.volatility,g_timeframe,sequence,barTime,
                            forceFirstEvaluation || afterGap,true);

   // Phase 4 is in-house: it reuses closed MqlRates and the selected ATR
   // buffer, creates no handle and is never reached by the tick handler.
   const int smcBars=EmttSmcHistoryRequired(g_assetClass,g_dynamic.volatility,
                                            g_timeframe);
   MqlRates smcRates[];
   double smcAtr[];
   if(EmttCopyRates(smcBars,smcRates) &&
      EmttCopySeries(EmttAtrHandle(g_dynamic.atrPeriod),0,smcBars,smcAtr))
      EmttSmcAdvance(g_smc,smcRates,smcAtr,0,g_symbol,g_assetClass,
                     g_dynamic.atrPeriod,g_dynamic.volatility,g_timeframe,
                     sequence,barTime,forceFirstEvaluation || afterGap,true);

   // Phase 5 volume flow: its own closed-bar window (the profile window plus
   // the session depth plus the fetch buffer, 15.3) and the same selected
   // ATR buffer. Closed bars only - the tick path never reaches this code.
   const int volumeFlowBars=EmttVfFetchDepth(g_assetClass,
                                             g_dynamic.volatility,g_timeframe);
   MqlRates volumeFlowRates[];
   double volumeFlowAtr[];
   if(EmttCopyRatesUpTo(volumeFlowBars,volumeFlowRates) &&
      EmttCopySeriesUpTo(EmttAtrHandle(g_dynamic.atrPeriod),0,
                         ArraySize(volumeFlowRates),volumeFlowAtr) &&
      ArraySize(volumeFlowAtr)==ArraySize(volumeFlowRates))
      EmttVolumeFlowAdvance(g_volumeFlow,volumeFlowRates,volumeFlowAtr,0,
                            g_symbol,g_assetClass,g_dynamic.atrPeriod,
                            g_dynamic.volatility,g_timeframe,sequence,
                            forceFirstEvaluation || afterGap,true);

   // The higher-timeframe context: the same poll as the replay path, with
   // the chart facts of this evaluation passed in (15.9).
   EmttMtfAdvance(g_mtf,g_mtfContext,g_symbol,g_assetClass,g_timeframe,
                  sequence,g_supertrend.direction,g_smc.bias,
                  forceFirstEvaluation || afterGap,true);

   // Phase 6: the signal gate and plan lifecycle run on this closed bar,
   // after the four component views advanced (17.1). The signal changes
   // only at a candle close; no order is placed here.
   MqlRates signalBar[1];
   if(CopyRates(g_symbol,g_timeframe,1,1,signalBar)==1)
     {
      double signalAtr=0.0;
      EmttCopyOne(EmttAtrHandle(g_dynamic.atrPeriod),0,1,signalAtr);
      MqlTick signalTick;
      double signalBid=0.0,signalAsk=0.0;
      if(SymbolInfoTick(g_symbol,signalTick))
        {
         signalBid=signalTick.bid;
         signalAsk=signalTick.ask;
        }
      else
        {
         signalBid=SymbolInfoDouble(g_symbol,SYMBOL_BID);
         signalAsk=SymbolInfoDouble(g_symbol,SYMBOL_ASK);
        }
      const double signalPoint=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
      const int signalDigits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
      int signalSpread=0;
      if(signalPoint>0.0)
         signalSpread=(int)MathRound((signalAsk-signalBid)/signalPoint);
      // 17.2 rule 3: the mood is the regime's pending candidate when one
      // is open, otherwise its confirmed label.
      const EEmttRegime signalMood=
        (g_regimeState.pending!=EMTT_REGIME_UNKNOWN ?
         g_regimeState.pending : regime);
      // Phase 7 (19.4-19.5): the learned terms of this closed bar. The four
      // published scores carry the learning scale for the one signal call
      // and are restored right after it, so no published reading changes.
      EmttLearningReadCandle(signalMood,signalAtr);
      SEmttLearnScoreSnapshot learningScores;
      EmttLearningSaveScores(learningScores);
      EmttLearningScaleScores(learningScores,g_learning.reading.scale);
      if(g_paramOpt.enabled && signalBar[0].time==barTime)
        {
         const int entryBar=(g_dynamic.thresholdFrozen ? g_dynamic.frozenThreshold :
                             (g_trade.entryMoodBar>0 ? g_trade.entryMoodBar :
                              EmttParamOptBar(g_paramOpt,signalMood)));
         EmttParamOptBeginCandle(g_paramOpt,barTime,EmttOwnPositionOpen(),entryBar);
        }
      EmttSignalAdvance(g_signal,g_supertrend,g_smc,g_volumeFlow,g_mtf,
                        signalMood,EmttParamOptBar(g_paramOpt,signalMood),
                        signalAtr,signalBar[0].high,
                        signalBar[0].low,signalBar[0].close,
                        signalBid,signalAsk,signalSpread,g_timeframe,
                        sequence,barTime,signalDigits,signalPoint,false);
      EmttLearningRestoreScores(learningScores);
      EmttConsumeSignalEvents(barTime,signalBar[0].high,signalBar[0].low,
                              signalSpread,signalAtr);
      EmttParamOptimizationAdvance(signalAtr,signalBar[0].high,signalBar[0].low,
                                    signalBar[0].close,signalBid,signalAsk,
                                    sequence,barTime);
      EmttJournalSignalState(barTime);
     }

   EmttSetSnapshot(measurements,regime,percentile,barTime);
   g_lastClosedBarTime=barTime;
   g_evaluatedBarSequence++;
   return true;
  }

//+------------------------------------------------------------------+
//| Revalidate symbol class every 100 newly processed closed bars    |
//+------------------------------------------------------------------+
// Reset startup bookkeeping without closing plans or writing learning files.
// OnInit must not inherit a ready snapshot from a previous chart context.
void EmttResetFoundationSnapshot()
  {
   g_historyRequired=EmttResolveHistoryRequired(g_timeframe);
   g_marketWasClosed=false;
   g_snapshotReady=false;
   g_snapshotRegime=EMTT_REGIME_UNKNOWN;
   g_snapshotVolatility=EMTT_VOL_UNKNOWN;
   g_snapshotPercentile=-1.0;
   g_snapshotBarTime=0;
   g_lastClosedBarTime=0;
   g_evaluatedBarSequence=0;
   g_historyAvailable=0;
   g_marketOpen=false;
   g_sessionName="--";
  }

void EmttResetMarketState()
  {
   // 17.7: a symbol or timeframe change ends any open plan before the
   // signal state is reset. Phase 7 (19.3): the same end closes the plan's
   // ticket and writes the old file, before the learning state is rebound
   // to the new symbol and timeframe.
   EmttParamOptEndNear(g_paramOpt,EMTT_LEARN_RESULT_CHART,
                       g_signal.lastClose,g_signal.lastSequence,
                       g_signal.lastBarTime,false);
   EmttSignalChartChanged(g_signal,false);
   EmttConsumeSignalEvents(g_signal.lastBarTime,0.0,0.0,0,0.0);
   EmttSignalReset(g_signal);
   EmttLearnStateReset(g_learning);
   EmttDynamicReset(g_dynamic);
   EmttRegimeReset(g_regimeState);
   EmttSupertrendReset(g_supertrend);
   EmttSmcReset(g_smc);
   EmttVfReset(g_volumeFlow);
   EmttMtfReset(g_mtf,g_mtfContext); // frees the HTF handle set as well
   EmttResetFoundationSnapshot();
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
   // New symbol and/or timeframe: bind the Summary counts to its file.
   EmttSummaryInit(g_summary,g_symbol,g_timeframe);
   EmttParamOptimizationAttachAndLoad(iTime(g_symbol,g_timeframe,1));

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
         // 23.6: reuse the existing entry snapshot, not a new GlobalVariable.
         if(g_paramOpt.enabled && EmttParamBarApproved(g_trade.entryMoodBar))
            g_dynamic.confidenceThreshold=g_trade.entryMoodBar;
         EmttDynamicFreezeAtEntry(g_dynamic);
         storeSnapshot=g_dynamic.thresholdFrozen;
        }
      if(g_dynamic.thresholdFrozen && storeSnapshot)
        {
         GlobalVariableSet(key,(double)g_dynamic.frozenThreshold);
         GlobalVariablesFlush();
        }
      if(g_dynamic.thresholdFrozen)
         EmttParamOptFreezeAtEntry(g_paramOpt,g_dynamic.frozenThreshold);
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
      EmttTradeManagerRefresh();
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
      // 17.7: the market closing ends any open plan; no evaluation runs.
      EmttParamOptEndNear(g_paramOpt,EMTT_LEARN_RESULT_MARKET,
                          g_signal.lastClose,g_signal.lastSequence,
                          g_signal.lastBarTime,false);
      EmttSignalMarketClosed(g_signal,false);
      EmttConsumeSignalEvents(g_signal.lastBarTime,0.0,0.0,0,0.0);
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

   // 15.1: one poll per second - a bar-time comparison in front of the
   // panel refresh, never a measurement and never a tick handler.
   EmttMtfAdvance(g_mtf,g_mtfContext,g_symbol,g_assetClass,g_timeframe,
                  g_evaluatedBarSequence,g_supertrend.direction,g_smc.bias,
                  false,true);
   EmttTradeManagerRefresh();
   EmttSyncFrozenPositionContext();
   UpdatePanel();
  }

//+------------------------------------------------------------------+
//| Phase 9: persistence belongs to the headers; the EA only wires  |
//| init / decisions / deinit and the live, post-replay candle path. |
//+------------------------------------------------------------------+
void EmttParamOptimizationSaveOnExit()
  {
   if(!g_paramOpt.enabled || g_paramOpt.replaying) return;
   datetime stamp=(g_paramOpt.lastLiveBarTime>0 ? g_paramOpt.lastLiveBarTime :
                                                g_signal.lastBarTime);
   for(int i=0;i<g_paramOpt.pendingCount;i++)
      if(g_paramOpt.pending[i].resultTime>stamp) stamp=g_paramOpt.pending[i].resultTime;
   // These broker outcomes already have real labels. Flush their evidence
   // before shutdown, without evaluating a candle, a near idea, or a move.
   // Otherwise removing the EA between closes would silently lose a result.
   EmttParamOptimizationConsumeAccepted(stamp,stamp,false);
   EmttParamFileSave(g_paramOpt.file,stamp);
   if(g_paramOpt.carriedFile.loaded)
      EmttParamFileSave(g_paramOpt.carriedFile,stamp);
  }

void EmttParamOptimizationAttachAndLoad(const datetime barTime)
  {
   if(!g_paramOpt.enabled) return;
   const string tfName=EmttLearnTfName(g_timeframe);
   if(g_paramOpt.file.loaded && g_paramOpt.file.symbol==g_symbol &&
      g_paramOpt.file.tfName==tfName) return;
   EmttParamOptimizationSaveOnExit();
   EmttParamOptReset(g_paramOpt,true);
   EmttParamFileLoad(g_paramOpt.file,g_symbol,g_timeframe,barTime);
   EmttParamFileSave(g_paramOpt.file,barTime); // 23.7 init immediately after load
   EmttParamOptUseLoadedBars(g_paramOpt);    // before any measurement replay
  }

bool EmttParamOptimizationTakeAccepted(SEmttParamFileState &file,
                                      const datetime barEnd)
  {
   bool changed=false;
   for(int i=0;i<g_paramOpt.pendingCount;i++)
     {
      if(g_paramOpt.pending[i].label<0 ||
         g_paramOpt.pending[i].tfName!=file.tfName ||
         g_paramOpt.pending[i].resultTime>barEnd) continue;
      EmttParamOptAddAccepted(file.cells[g_paramOpt.pending[i].mood],
                              g_paramOpt.pending[i].label);
      EmttParamOptRemember(g_paramOpt,g_paramOpt.pending[i].key);
      g_paramOpt.pending[i].label=-1;
      changed=true;
     }
   return changed;
  }

// Fold labeled outcomes in order. Only the closed-candle caller may make
// a decision; deinit folds pending real labels solely for its final write.
void EmttParamOptimizationConsumeAccepted(const datetime barTime,
                                          const datetime barEnd,
                                          const bool allowDecision)
  {
   // Keep broker results in candle order even when a save needed a retry.
   for(int i=1;i<g_paramOpt.pendingCount;i++)
     {
      const SEmttParamAccepted item=g_paramOpt.pending[i];
      int j=i-1;
      while(j>=0 && g_paramOpt.pending[j].resultTime>item.resultTime)
        {
         g_paramOpt.pending[j+1]=g_paramOpt.pending[j];
         j--;
        }
      g_paramOpt.pending[j+1]=item;
     }
   EmttParamOptimizationTakeAccepted(g_paramOpt.file,barEnd);
   // A position opened on another chart timeframe still belongs to that
   // file. This does not read/relearn old tickets or pool their evidence.
   const ENUM_TIMEFRAMES sources[3]={PERIOD_M5,PERIOD_M15,PERIOD_M30};
   for(int source=0;source<3;source++)
     {
      const string name=EmttLearnTfName(sources[source]);
      if(name==g_paramOpt.file.tfName) continue;
      bool hasResult=false;
      for(int i=0;i<g_paramOpt.pendingCount;i++)
         if(g_paramOpt.pending[i].label>=0 &&
            g_paramOpt.pending[i].tfName==name &&
            g_paramOpt.pending[i].resultTime<=barEnd) hasResult=true;
      if(!hasResult) continue;
      if(!g_paramOpt.carriedFile.loaded ||
         g_paramOpt.carriedFile.symbol!=g_paramOpt.file.symbol ||
         g_paramOpt.carriedFile.tfName!=name)
        {
         if(g_paramOpt.carriedFile.loaded)
            EmttParamFileSave(g_paramOpt.carriedFile,barTime);
         EmttParamFileLoad(g_paramOpt.carriedFile,g_paramOpt.file.symbol,sources[source],barTime);
         EmttParamFileSave(g_paramOpt.carriedFile,barTime);
        }
      EmttParamOptimizationTakeAccepted(g_paramOpt.carriedFile,barEnd);
      if(allowDecision && EmttParamOptDecideFile(g_paramOpt.carriedFile,barTime))
         EmttParamFileSave(g_paramOpt.carriedFile,barTime);
     }
   int kept=0;
   for(int i=0;i<g_paramOpt.pendingCount;i++)
      if(g_paramOpt.pending[i].label>=0)
         g_paramOpt.pending[kept++]=g_paramOpt.pending[i];
   g_paramOpt.pendingCount=kept;
  }

void EmttParamOptimizationAdvance(const double atr,const double high,
                                  const double low,const double close,
                                  const double bid,const double ask,
                                  const long sequence,const datetime barTime)
  {
   if(!g_paramOpt.enabled || g_paramOpt.replaying || !g_paramOpt.liveCandle ||
      !TfAllowed()) return;
   const datetime barEnd=barTime+PeriodSeconds(g_timeframe);
   EmttParamOptimizationConsumeAccepted(barTime,barEnd,true);

   EmttParamOptAdvanceNear(g_paramOpt,g_signal,g_supertrend,g_smc,g_volumeFlow,
                           atr,high,low,close,bid,ask,g_timeframe,sequence,barTime);
   // 23.7's explicit write events: a tally-only candle is kept in memory;
   // the next move/held move or deinit persists it. Never a periodic rewrite.
   if(EmttParamOptDecideFile(g_paramOpt.file,barTime))
      EmttParamFileSave(g_paramOpt.file,barTime);
   g_paramOpt.liveCandle=false;
  }

//+------------------------------------------------------------------+
//| Phase 7 (19.5): the four published scores carry the learning      |
//| scale for exactly one EmttSignalAdvance call. The scale is applied |
//| just before the call and the real scores are put back right after  |
//| it, so no published reading changes and the plan builder still     |
//| reads the real levels of 17.4. The components are copied by        |
//| nothing: the EA owns one instance of each.                         |
//+------------------------------------------------------------------+
struct SEmttLearnScoreSnapshot
  {
   double trend;
   double structure;
   double flow;
   double htf;
  };

void EmttLearningSaveScores(SEmttLearnScoreSnapshot &saved)
  {
   saved.trend=g_supertrend.score;
   saved.structure=g_smc.smcScore;
   saved.flow=g_volumeFlow.volumeFlowScore;
   saved.htf=g_mtf.mtfScore;
  }

void EmttLearningScaleScores(const SEmttLearnScoreSnapshot &saved,
                             const double scale)
  {
   g_supertrend.score=saved.trend*scale;
   g_smc.smcScore=saved.structure*scale;
   g_volumeFlow.volumeFlowScore=saved.flow*scale;
   g_mtf.mtfScore=saved.htf*scale;
  }

void EmttLearningRestoreScores(const SEmttLearnScoreSnapshot &saved)
  {
   g_supertrend.score=saved.trend;
   g_smc.smcScore=saved.structure;
   g_volumeFlow.volumeFlowScore=saved.flow;
   g_mtf.mtfScore=saved.htf;
  }

//+------------------------------------------------------------------+
//| 19.4-19.5: the learned terms of the newest closed bar. The four   |
//| views, the mood of 17.2 rule 3, the 15.3 anchor session and the   |
//| 9.2 bucket are the same readings the signal uses; the number the  |
//| features carry is the four-view number of 17.3, never the         |
//| adjusted one.                                                     |
//+------------------------------------------------------------------+
void EmttLearningFillCandle(SEmttLearnCandle &candle,
                            const EEmttRegime mood,const double atr)
  {
   candle.ready=false;
   candle.combined=0.0;
   candle.rawNumber=-1;
   candle.trendDirection=0;
   candle.structureDirection=0;
   candle.flowDirection=0;
   candle.htfDirection=0;
   candle.mood=EmttLearnMoodIndex(mood);
   candle.session=EmttLearnSessionIndex(g_volumeFlow.sessionName);
   candle.vol=EmttLearnVolIndex(g_dynamic.volatility);
   if(!(g_supertrend.ready && g_smc.ready && g_volumeFlow.ready &&
        g_mtf.ready))
      return;
   if(EmttSignalMoodBar(mood)<=0 || !EmttValidPositive(atr))
      return;
   candle.combined=EmttSignalCombined(g_supertrend,g_smc,g_volumeFlow,
                                      g_mtf);
   candle.rawNumber=EmttSignalConfidenceNumber(candle.combined);
   candle.trendDirection=g_supertrend.direction;
   candle.structureDirection=g_smc.bias;
   candle.flowDirection=g_volumeFlow.flowDirection;
   candle.htfDirection=g_mtf.htfSupertrendDirection;
   candle.ready=true;
  }

void EmttLearningReadCandle(const EEmttRegime mood,const double atr)
  {
   SEmttLearnCandle candle;
   EmttLearningFillCandle(candle,mood,atr);
   EmttLearnEnsureModel(g_learning);
   EmttLearnEvaluate(g_learning,candle,g_learning.reading);
  }

// 19.3: bind the learning record to this symbol and timeframe and load it.
// The write that follows the load is event 1 of 19.3: it normalises the
// file, applies the cap and consumes a leftover .tmp of a crashed write.
void EmttLearningAttachAndLoad(const datetime barTime)
  {
   const string tfName=EmttLearnTfName(g_timeframe);
   if(g_learning.file.loaded && g_learning.file.symbol==g_symbol &&
      g_learning.file.tfName==tfName)
      return;
   const int digits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
   EmttLearnFileLoad(g_learning.file,g_symbol,g_timeframe,digits,barTime);
   EmttLearnFileSave(g_learning.file,barTime,g_paramOpt.enabled);
   g_learning.modelDirty=true;
   g_learning.modelLabeled=0;
   g_learning.resumeChecked=false;
  }

// 19.6: true once, when the record holds an open plan that has not been
// resumed yet. The caller then resumes it instead of running the
// post-replay evaluation, because the gap is checked against the plan's
// own levels and the signal is next evaluated at the first post-replay
// closed candle.
bool EmttLearningResumePending()
  {
   if(g_learning.file.openTicket<0 || g_learning.resumeChecked)
      return false;
   g_learning.resumeChecked=true;
   return true;
  }

//+------------------------------------------------------------------+
//| 19.7 / 17.8: the journal lines of a plan. Emtt_Signal.mqh is      |
//| byte-identical and prints them only with its own plan in hand,    |
//| so Phase 7 prints them here from the same readings and with the   |
//| same text - and the plan start line can then carry the learning   |
//| part of 19.7.                                                     |
//+------------------------------------------------------------------+
void EmttJournalPlanStart(const datetime barTime,const int spreadPts)
  {
   if(!g_signal.plan.active)
      return;
   const int digits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
   PrintFormat("Emtt | Signal %s | confidence %d%% (%s) | %s, bar %d%% | bar %s",
               EmttPlanSideName(g_signal.plan.side),g_signal.confidence,
               EmttTierLabel(EmttTierOf(g_signal.confidence)),
               EmttSignalMoodWord(g_signal.mood),g_signal.moodBar,
               EmttLearnTimeText(barTime));
   string line="Emtt | Plan "+EmttPlanSideName(g_signal.plan.side)+
               " | confidence "+IntegerToString(g_signal.confidence)+"%";
   const string learningText=EmttLearnPlanText(g_learning,
                                               g_learning.reading);
   if(learningText!="")
      line+=" | "+learningText;
   line+=" | entry "+DoubleToString(g_signal.plan.entry,digits)+" ("+
         g_signal.plan.entrySource+")"+
         " | stop "+DoubleToString(g_signal.plan.stop,digits)+" ("+
         g_signal.plan.stopSource+" "+
         (g_signal.plan.side>0 ? "-" : "+")+
         DoubleToString(EMTT_PLAN_STOP_BUFFER_ATR,1)+" ATR)"+
         " | target "+DoubleToString(g_signal.plan.target,digits)+" ("+
         g_signal.plan.targetSource+")"+
         " | RR 1:"+DoubleToString(g_signal.plan.riskReward,1)+
         " | expected "+g_signal.plan.duration+
         " | spread "+IntegerToString(spreadPts)+" pts"+
         " | bar "+EmttLearnTimeText(barTime);
   Print(line);
   g_signal.hasJournaledSignal=true;
   g_signal.journaledSignal=g_signal.signal;
   g_signal.hasJournaledWait=false;
   g_signal.journaledWaitReason=EMTT_SIG_WAIT_NONE;
  }

void EmttJournalEntryReached(const int side,const double entry,
                             const int digits,const datetime barTime)
  {
   PrintFormat("Emtt | Plan %s | entry reached | %s | bar %s",
               EmttPlanSideName(side),DoubleToString(entry,digits),
               EmttLearnTimeText(barTime));
  }

// The 17.8 result line. `resumedFromFile` marks the 19.6 end of a plan
// that was restored from the record, where 17.8 puts `shared candle`.
void EmttJournalPlanResult(const int side,const int result,
                           const double exitPrice,const double entry,
                           const int digits,const double point,
                           const long startSequence,const long endSequence,
                           const bool sharedCandle,
                           const bool resumedFromFile,
                           const datetime barTime)
  {
   double points=0.0;
   if(point>0.0)
      points=(side>0 ? exitPrice-entry : entry-exitPrice)/point;
   const int pointsWhole=(int)MathRound(points);
   const int absPoints=(pointsWhole<0 ? -pointsWhole : pointsWhole);
   const string sign=(pointsWhole>=0 ? "+" : "-");
   long candles=0;
   if(startSequence>=0 && endSequence>=startSequence)
      candles=endSequence-startSequence;
   string tail="";
   if(sharedCandle)
      tail+=" | shared candle";
   if(resumedFromFile)
      tail+=" | resumed from file";
   PrintFormat("Emtt | Plan %s result | %s | exit %s | %s%d pts | %d candles%s | bar %s",
               EmttPlanSideName(side),
               EmttPlanResultName(EmttLearnPlanResultOf(result)),
               DoubleToString(exitPrice,digits),sign,absPoints,(int)candles,
               tail,EmttLearnTimeText(barTime));
  }

//+------------------------------------------------------------------+
//| 19.3: the three ticket events of the file.                        |
//+------------------------------------------------------------------+
void EmttLearningRecordPlanStart(const datetime barTime,
                                 const int spreadPts,const double atr)
  {
   if(!g_signal.plan.active)
      return;
   const int estimate=EmttLearnEstimateMinutes(g_signal.plan,
                                               g_supertrend.direction,
                                               g_supertrend.barsSinceFlip,
                                               g_supertrend.distanceATRs,atr,
                                               g_timeframe);
   SEmttLearnTicket ticket;
   EmttLearnTicketFromPlan(ticket,g_signal.plan,
                           g_learning.reading.rawNumber,
                           g_supertrend.direction,g_smc.bias,
                           g_volumeFlow.flowDirection,
                           g_mtf.htfSupertrendDirection,
                           EmttLearnMoodIndex(g_signal.mood),
                           EmttLearnSessionIndex(g_volumeFlow.sessionName),
                           EmttLearnVolIndex(g_dynamic.volatility),
                           estimate,spreadPts,g_signal.plan.startSequence);
   if(g_paramOpt.enabled)
     {
      ticket.parRecorded=true;
      ticket.parAtr=g_dynamic.atrPeriod;
      ticket.parEr=g_dynamic.erPeriod;
      ticket.parKamaFast=g_dynamic.kamaFast;
      ticket.parKamaMedium=g_dynamic.kamaMedium;
      ticket.parKamaSlow=g_dynamic.kamaSlow;
      ticket.parStructureWindow=g_smc.structureWindow;
      ticket.parVolumeWindow=g_volumeFlow.profileWindow;
      ticket.parBar=g_signal.moodBar;
      ticket.parMinRR=EmttPlanMinRiskReward(g_signal.mood);
     }
   const int slot=EmttLearnFileAddPlan(g_learning.file,ticket);
   if(slot<0)
      return;
   EmttLearnFileSave(g_learning.file,barTime,g_paramOpt.enabled);
   EmttJournalPlanStart(barTime,spreadPts);
  }

void EmttLearningRecordEntryReached(const datetime barTime)
  {
   const int slot=g_learning.file.openTicket;
   if(slot<0 || !g_signal.plan.active)
      return;
   if(g_learning.file.tickets[slot].state!=EMTT_LEARN_STATE_PENDING)
      return;
   if(g_signal.plan.status!=EMTT_PLAN_ACTIVE)
      return;
   if(g_signal.plan.startBarTime!=g_learning.file.tickets[slot].startBarTime)
      return;
   EmttLearnFileMarkReached(g_learning.file,slot,barTime);
   EmttJournalEntryReached(g_learning.file.tickets[slot].side,
                           g_learning.file.tickets[slot].entry,
                           g_learning.file.digits,barTime);
   EmttLearnFileSave(g_learning.file,barTime,g_paramOpt.enabled);
  }

void EmttLearningRecordPlanEnd(const datetime barTime,const double barHigh,
                               const double barLow)
  {
   const EEmttPlanResult planResult=g_signal.endedResult;
   if(planResult==EMTT_PLAN_RESULT_NONE)
      return;
   const int slot=g_learning.file.openTicket;
   if(slot<0)
      return;
   const SEmttLearnTicket ticket=g_learning.file.tickets[slot];
   const int digits=g_learning.file.digits;
   const double point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   const int result=EmttLearnResultOfPlanResult(planResult);
   double exitPrice=g_signal.lastClose;
   if(result==EMTT_LEARN_RESULT_TARGET || result==EMTT_LEARN_RESULT_MISSED)
      exitPrice=ticket.target;
   else if(result==EMTT_LEARN_RESULT_STOP ||
           result==EMTT_LEARN_RESULT_CANCELLED)
      exitPrice=ticket.stop;
   int points=0;
   if(point>0.0)
      points=(int)MathRound((ticket.side>0 ? exitPrice-ticket.entry
                                           : ticket.entry-exitPrice)/point);
   int candles=0;
   if(ticket.startSequence>=0 &&
      g_signal.lastSequence>=ticket.startSequence)
      candles=(int)(g_signal.lastSequence-ticket.startSequence);
   // 17.7: the ending candle is shared when more than one level lies
   // between its low and its high. Only a level end passes the candle -
   // a signal-changed end, a market-close end and a chart-change end pass
   // none and are never shared, exactly as Emtt_Signal.mqh passes them.
   bool shared=false;
   const bool levelEnd=(result==EMTT_LEARN_RESULT_TARGET ||
                        result==EMTT_LEARN_RESULT_STOP ||
                        result==EMTT_LEARN_RESULT_MISSED ||
                        result==EMTT_LEARN_RESULT_CANCELLED);
   if(levelEnd && barHigh>0.0 && barLow>0.0 && barHigh>=barLow)
     {
      const int touched=((ticket.entry>=barLow && ticket.entry<=barHigh) ? 1 : 0)+
                        ((ticket.stop>=barLow && ticket.stop<=barHigh) ? 1 : 0)+
                        ((ticket.target>=barLow && ticket.target<=barHigh) ? 1 : 0);
      shared=(touched>1);
     }
   EmttLearnFileCloseTicket(g_learning.file,slot,result,shared,exitPrice,
                            points,candles);
   if(g_paramOpt.liveCandle && EmttLearnLabelOf(ticket)<0)
      EmttParamOptQueueAccepted(g_paramOpt,g_learning.file.tickets[slot],
                                g_learning.file.symbol,g_learning.file.tfName,barTime);
   EmttLearnFileSave(g_learning.file,barTime,g_paramOpt.enabled);
   EmttJournalPlanResult(ticket.side,result,exitPrice,ticket.entry,digits,
                         point,ticket.startSequence,g_signal.lastSequence,
                         shared,false,barTime);
   if(result==EMTT_LEARN_RESULT_TARGET || result==EMTT_LEARN_RESULT_STOP)
     {
      // 19.4: a labeled result trains the model at once; the weights are
      // recomputed from the tickets, never stored.
      EmttLearnJournalUpdated(g_learning,barTime);
      g_learning.modelDirty=true;
     }
  }

ENUM_TIMEFRAMES EmttLearningTradeTimeframe()
  {
   if(g_trade.recordTfName=="M5") return PERIOD_M5;
   if(g_trade.recordTfName=="M15") return PERIOD_M15;
   if(g_trade.recordTfName=="M30") return PERIOD_M30;
   if(g_trade.tradeTimeframe!=PERIOD_CURRENT)
      return g_trade.tradeTimeframe;
   return g_timeframe;
  }

bool EmttLearningApplyTradeEvent(SEmttLearnFileState &file,
                                 const bool closing,
                                 const datetime eventTime)
  {
   int slot=EmttLearnFileFindPlan(file,g_trade.planStartBarTime,
                                  g_trade.side);
   const datetime fillMinute=(g_trade.filledAt>0 ?
      StringToTime(EmttLearnTimeText(g_trade.filledAt)) : 0);
   const datetime closeMinute=(g_trade.closedAt>0 ?
      StringToTime(EmttLearnTimeText(g_trade.closedAt)) : 0);
   if(slot<0 && fillMinute>0)
      slot=EmttLearnFileFindOpenTrade(file,fillMinute,g_trade.side);
   if(slot<0 || slot>=file.ticketCount ||
      !file.tickets[slot].used)
      return false;
   if(fillMinute>0 && file.tickets[slot].tradeFilledTime==0)
      EmttLearnFileMarkTradeFilled(file,slot,fillMinute);
   if(closing && closeMinute>0 &&
      file.tickets[slot].tradeClosedTime==0)
     {
      EmttLearnFileMarkTradeClosed(file,slot,closeMinute,g_trade.closedNetPoints);
      // Queue the original ticket's mood and timeframe once. Tallies and
      // decisions run only at the next live close, never in this callback.
      EmttParamOptQueueAccepted(g_paramOpt,file.tickets[slot],file.symbol,file.tfName,eventTime);
     }
   if(g_trade.filledAt>0 &&
      file.tickets[slot].tradeFilledTime==0)
      return false;
   if(closing && g_trade.closedAt>0 &&
      file.tickets[slot].tradeClosedTime==0)
      return false;
   return EmttLearnFileSave(file,eventTime,g_paramOpt.enabled);
  }

bool EmttLearningSaveTradeEvent(const bool closing)
  {
   const datetime eventTime=(closing ? g_trade.closedAt : g_trade.filledAt);
   if(eventTime<=0 || g_trade.planStartBarTime<=0 || g_trade.side==0)
      return false;
   const ENUM_TIMEFRAMES timeframe=EmttLearningTradeTimeframe();
   const string tfName=EmttLearnTfName(timeframe);
   if(g_learning.file.loaded && g_learning.file.symbol==g_symbol &&
      g_learning.file.tfName==tfName)
      return EmttLearningApplyTradeEvent(g_learning.file,closing,eventTime);
   SEmttLearnFileState file;
   const int digits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
   EmttLearnFileLoad(file,g_symbol,timeframe,digits,eventTime);
   if(!file.loaded || file.readOnly)
      return false;
   return EmttLearningApplyTradeEvent(file,closing,eventTime);
  }

void EmttLearningRecordTradeEvents()
  {
   if(g_trade.fillRecordPending && EmttLearningSaveTradeEvent(false))
     {
      EmttTradeManagerAcknowledgeFill(g_trade);
      if(g_learning.file.tfName==g_trade.recordTfName)
        {
         g_learning.modelDirty=true;
         g_learning.modelLabeled=0;
        }
     }
   if(g_trade.closeRecordPending && EmttLearningSaveTradeEvent(true))
     {
      EmttTradeManagerAcknowledgeClose(g_trade);
      if(g_learning.file.tfName==g_trade.recordTfName)
        {
         g_learning.modelDirty=true;
         g_learning.modelLabeled=0;
        }
     }
   if(g_trade.summaryOutcomePending)
     {
      if(g_trade.closedNetPoints>0)
        {
         if(g_summary.loaded && g_summary.symbol==g_symbol &&
            g_summary.tfName==g_trade.recordTfName)
            EmttSummaryOnWin(g_summary);
         else
           {
            SEmttSummaryState summary;
            EmttSummaryInit(summary,g_symbol,EmttLearningTradeTimeframe());
            EmttSummaryOnWin(summary);
           }
        }
      else if(g_trade.closedNetPoints<0)
        {
         if(g_summary.loaded && g_summary.symbol==g_symbol &&
            g_summary.tfName==g_trade.recordTfName)
            EmttSummaryOnLoss(g_summary);
         else
           {
            SEmttSummaryState summary;
            EmttSummaryInit(summary,g_symbol,EmttLearningTradeTimeframe());
            EmttSummaryOnLoss(summary);
           }
        }
      EmttTradeManagerAcknowledgeSummary(g_trade);
     }
  }

void EmttLearningRecoverTradeContext()
  {
   if(!g_trade.positionOpen || g_trade.hasPlanContext ||
      g_trade.recoveryScanned)
      return;
   const datetime fillMinute=(g_trade.filledAt>0 ?
      StringToTime(EmttTradeManagerTimeText(g_trade.filledAt)) : 0);
   if(g_learning.file.loaded && g_learning.file.symbol==g_symbol)
     {
      int slot=EmttLearnFileFindOpenTrade(g_learning.file,fillMinute,
                                          g_trade.side);
      if(slot<0 && fillMinute>0 && g_learning.file.openTicket>=0 &&
         g_learning.file.openTicket<g_learning.file.ticketCount &&
         g_learning.file.tickets[g_learning.file.openTicket].side==g_trade.side &&
         g_learning.file.tickets[g_learning.file.openTicket].startBarTime<=fillMinute)
         slot=g_learning.file.openTicket;
      if(slot>=0)
        {
         const SEmttLearnTicket ticket=g_learning.file.tickets[slot];
         const int atrPeriod=EmttMatrixField(
            g_assetClass,(EEmttVolatility)ticket.vol,0);
         EmttTradeManagerBindTicket(g_trade,ticket,
                                    EmttLearningTradeTimeframe(),atrPeriod);
         g_trade.recoveryScanned=true;
         return;
        }
     }
   const ENUM_TIMEFRAMES sources[3]={PERIOD_M5,PERIOD_M15,PERIOD_M30};
   const int digits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
   for(int i=0;i<3;i++)
     {
      if(EmttLearnTfName(sources[i])==g_learning.file.tfName)
         continue;
      SEmttLearnFileState file;
      EmttLearnFileLoad(file,g_symbol,sources[i],digits,g_trade.filledAt);
      const int slot=EmttLearnFileFindOpenTrade(file,fillMinute,
                                                 g_trade.side);
      if(slot<0)
         continue;
      const SEmttLearnTicket ticket=file.tickets[slot];
      const int atrPeriod=EmttMatrixField(
         g_assetClass,(EEmttVolatility)ticket.vol,0);
      EmttTradeManagerBindTicket(g_trade,ticket,sources[i],atrPeriod);
      g_trade.recoveryScanned=true;
      return;
     }
   g_trade.recoveryScanned=true;
  }

void EmttTradeManagerBuildRuntime(SEmttTradeRuntime &runtime)
  {
   runtime.symbol=g_symbol;
   runtime.timeframe=g_timeframe;
   runtime.magic=InpMagicNumber;
   runtime.autoTrading=InpAutoTrading;
   runtime.autoTradeAbove=g_autoTradeAbove;
   runtime.pendingValidityBars=EmttPendingBars(InpPendingValidityBars);
   runtime.connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   runtime.lotMode=(int)InpLotMode;
   runtime.marginCheck=InpMarginCheck;
   runtime.placeStopLoss=InpPlaceStopLoss;
   runtime.terminalAllowed=((bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
                            (bool)MQLInfoInteger(MQL_TRADE_ALLOWED));
   runtime.accountAllowed=(bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED);
   runtime.chartCompatible=TfAllowed();
   runtime.learningLoaded=(runtime.chartCompatible &&
      g_learning.file.loaded && g_learning.file.symbol==g_symbol &&
      g_learning.file.tfName==EmttLearnTfName(g_timeframe));
   runtime.sessionName=g_sessionName;
   runtime.confidence=(g_signal.viewsReady ? g_signal.confidence : -1);
   runtime.moodBar=(g_signal.viewsReady ? g_signal.moodBar :
                    g_trade.entryMoodBar);
   runtime.mood=(g_signal.viewsReady ? g_signal.mood :
      (g_snapshotReady ? g_snapshotRegime : g_trade.entryMood));
   runtime.volatility=(g_snapshotReady ? g_snapshotVolatility :
                       g_trade.entryVolatility);
   runtime.assetClass=g_assetClass;
   runtime.atrPeriod=(g_dynamic.initialized ? g_dynamic.atrPeriod :
      (g_trade.atrPeriod>0 ? g_trade.atrPeriod :
       EmttMatrixField(g_assetClass,runtime.volatility,0)));
   runtime.atr=0.0;
   if(runtime.chartCompatible && g_dynamic.initialized &&
      runtime.atrPeriod==g_dynamic.atrPeriod)
      EmttCopyOne(EmttAtrHandle(runtime.atrPeriod),0,1,runtime.atr);
   runtime.trendDirection=(g_supertrend.ready ? g_supertrend.direction : 0);
   runtime.flowDirection=(g_volumeFlow.ready ?
                          g_volumeFlow.flowDirection : 0);
   runtime.viewsReady=(g_supertrend.ready && g_smc.ready &&
                       g_volumeFlow.ready && g_mtf.ready);
   runtime.barTime=iTime(g_symbol,g_timeframe,1);
   if(runtime.barTime<=0)
      runtime.barTime=g_lastClosedBarTime;
   runtime.analysisReady=(g_snapshotReady && runtime.viewsReady &&
      g_signal.viewsReady && g_signal.lastBarTime==runtime.barTime &&
      runtime.barTime>0 && g_signal.confidence>=0);
   runtime.quoteFresh=false;
   MqlTick tick;
   if(SymbolInfoTick(g_symbol,tick))
     {
      runtime.bid=tick.bid;
      runtime.ask=tick.ask;
      const datetime quoteNow=(TimeTradeServer()>0 ? TimeTradeServer() : TimeCurrent());
      runtime.quoteFresh=(runtime.connected && tick.time>0 && tick.time<=quoteNow+5 &&
         quoteNow-tick.time<=60 && tick.bid>0.0 && tick.ask>=tick.bid);
     }
   else
     {
      runtime.bid=SymbolInfoDouble(g_symbol,SYMBOL_BID);
      runtime.ask=SymbolInfoDouble(g_symbol,SYMBOL_ASK);
     }
   runtime.point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   runtime.digits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
   ENUM_TIMEFRAMES marketTf=(runtime.chartCompatible ? g_timeframe :
                             g_trade.tradeTimeframe);
   if(marketTf==PERIOD_CURRENT)
      marketTf=g_timeframe;
   const datetime now=(TimeTradeServer()>0 ? TimeTradeServer() :
                                            TimeCurrent());
   runtime.marketOpen=EmttMarketIsOpen(g_symbol,marketTf,now,
                                       iTime(g_symbol,marketTf,0));
   runtime.marketKnown=(runtime.connected && iTime(g_symbol,marketTf,0)>0);
  }

void EmttTradeManagerRefresh()
  {
   SEmttTradeRuntime runtime;
   EmttTradeManagerBuildRuntime(runtime);
   EmttTradeManagerObserve(g_trade,runtime.barTime);
   EmttLearningRecoverTradeContext();
   // 23.6: an adopted trade keeps the actual entry bar from the existing
   // snapshot, not the base bar the Phase 8 ticket binder reconstructs.
   // The author-only `par` values remain unread by every decision.
   if(g_paramOpt.enabled && g_paramOpt.positionFrozen && g_trade.positionOpen)
      g_trade.entryMoodBar=g_paramOpt.frozenBar;
   EmttTradeManagerStep(g_trade,runtime,g_signal.plan,g_supertrend,g_smc,
                        g_volumeFlow,g_learning.file,g_tickDiv);
   EmttLearningRecordTradeEvents();
  }

void EmttTradeManagerPanelStatus(SEmttPanelData &data)
  {
   // Preserve rule-19 incompatible / loading / market-closed precedence.
   if(!TfAllowed() || !g_snapshotReady || !g_marketOpen)
      return;
   datetime tradeBar=g_lastClosedBarTime;
   if(g_trade.tradeTimeframe!=PERIOD_CURRENT)
     {
      const datetime lastTradeBar=iTime(g_symbol,g_trade.tradeTimeframe,1);
      if(lastTradeBar>0)
         tradeBar=lastTradeBar;
     }
   string status="";
   if(g_trade.freshStatus!="" &&
      g_trade.freshStatusBarTime==tradeBar)
      status=g_trade.freshStatus;
   else if(g_trade.holdStatus!="")
      status=g_trade.holdStatus;
   // A cancelled/retired broker attempt must not look like an entry still
   // waiting to be submitted after the paper plan is restored on attach.
   else if(!g_trade.pendingOrder && !g_trade.positionOpen &&
           g_signal.plan.active &&
           g_signal.plan.entryKind==EMTT_PLAN_ENTRY_BLOCK &&
           (g_trade.gateStatus=="" ||
            g_trade.gateStatus=="No trade - this order-block execution attempt is retired") &&
           EmttPendingRetired(g_trade,g_timeframe,g_signal.plan.side,
                              g_signal.plan.entry,
                              SymbolInfoDouble(g_symbol,SYMBOL_POINT)))
      status="No trade - entry attempt ended; new setup needed.";
   // When flat, the concrete reason an active plan cannot trade is more
   // useful than an informational news note.
   else if(g_trade.gateStatus!="" && !g_trade.pendingOrder &&
           !g_trade.positionOpen && g_signal.plan.active)
      status=g_trade.gateStatus;
   else if(g_trade.newsStatus!="")
      status=g_trade.newsStatus;
   else if(g_trade.gateStatus!="")
      status=g_trade.gateStatus;
   else if(g_trade.pendingOrder || g_trade.positionOpen)
      status=g_trade.liveStatus;
   if(status!="")
     {
      data.status=status;
      if(StringFind(status,"No trade")>=0 ||
         StringFind(status,"Order rejected")>=0 ||
         StringFind(status,"Holding")>=0 ||
         StringFind(status,"not allowed")>=0)
         data.statusClr=EMTT_CLR_SELL;
     }
  }

//+------------------------------------------------------------------+
//| 19.7 / 17.8: the journal discipline the engine would run with a   |
//| journalling call - state changes, plan events and WAIT reason     |
//| changes only, never a quiet candle.                               |
//+------------------------------------------------------------------+
void EmttJournalSignalState(const datetime barTime)
  {
   if(!g_signal.viewsReady)
      return;
   if(!g_signal.hasJournaledSignal ||
      g_signal.journaledSignal!=g_signal.signal)
     {
      if(g_signal.signal!=0)
         PrintFormat("Emtt | Signal %s | confidence %d%% (%s) | %s, bar %d%% | bar %s",
                     EmttPlanSideName(g_signal.signal),
                     g_signal.confidence,
                     EmttTierLabel(EmttTierOf(g_signal.confidence)),
                     EmttSignalMoodWord(g_signal.mood),
                     g_signal.moodBar,EmttLearnTimeText(barTime));
      else
         PrintFormat("Emtt | Signal WAIT | %s | bar %s",
                     EmttSignalWaitDetail(g_signal),
                     EmttLearnTimeText(barTime));
      g_signal.hasJournaledSignal=true;
      g_signal.journaledSignal=g_signal.signal;
      if(g_signal.signal==0)
        {
         g_signal.hasJournaledWait=true;
         g_signal.journaledWaitReason=g_signal.waitReason;
        }
      else
        {
         g_signal.hasJournaledWait=false;
         g_signal.journaledWaitReason=EMTT_SIG_WAIT_NONE;
        }
     }
   else if(g_signal.signal==0 && g_signal.hasJournaledWait &&
           g_signal.journaledWaitReason!=g_signal.waitReason)
     {
      PrintFormat("Emtt | Signal WAIT | reason changed: %s | bar %s",
                  EmttSignalWaitBare(g_signal),
                  EmttLearnTimeText(barTime));
      g_signal.journaledWaitReason=g_signal.waitReason;
     }
  }

//+------------------------------------------------------------------+
//| 19.6: restore the file's plan into the signal state, so Row 2 and |
//| Row 3 continue with it and the engine resumes the same plan.      |
//+------------------------------------------------------------------+
void EmttLearningRestorePlan(const SEmttLearnTicket &ticket,
                             const long startSequence,
                             const long newestSequence,
                             const datetime newestBarTime,
                             const double newestClose,
                             const EEmttRegime mood)
  {
   EmttPlanReset(g_signal.plan);
   g_signal.plan.active=true;
   g_signal.plan.side=ticket.side;
   g_signal.plan.entryKind=(ticket.entryKind==EMTT_LEARN_ENTRY_BLOCK ?
                            EMTT_PLAN_ENTRY_BLOCK : EMTT_PLAN_ENTRY_MARKET);
   g_signal.plan.status=(ticket.state==EMTT_LEARN_STATE_ACTIVE ?
                         EMTT_PLAN_ACTIVE : EMTT_PLAN_PENDING);
   g_signal.plan.entry=ticket.entry;
   g_signal.plan.stop=ticket.stop;
   g_signal.plan.target=ticket.target;
   const double risk=MathAbs(ticket.entry-ticket.stop);
   g_signal.plan.riskReward=(risk>0.0 ?
                             MathAbs(ticket.target-ticket.entry)/risk : 0.0);
   g_signal.plan.entrySource=(ticket.entryKind==EMTT_LEARN_ENTRY_BLOCK ?
                              "order block edge" : "market price");
   g_signal.plan.stopSource="";
   g_signal.plan.targetSource="";
   g_signal.plan.duration=EmttLearnDurationFromEstimate(ticket.est,
                                                        g_timeframe);
   g_signal.plan.startSequence=startSequence;
   g_signal.plan.startBarTime=ticket.startBarTime;
   g_signal.plan.startClose=newestClose;

   g_signal.signal=ticket.side;
   g_signal.previousSignal=ticket.side;
   g_signal.justEnded=false;
   g_signal.waitReason=EMTT_SIG_WAIT_NONE;
   g_signal.waitSide=0;
   g_signal.viewsReady=g_learning.reading.ready;
   g_signal.confidence=(g_learning.reading.ready ? g_learning.reading.number
                                                 : -1);
   g_signal.combined=g_learning.reading.combined*
                     g_learning.reading.scale;
   g_signal.mood=mood;
   const int learnedBar=EmttParamOptBar(g_paramOpt,mood);
   g_signal.moodBar=(learnedBar>0 ? learnedBar : EmttSignalMoodBar(mood));
   g_signal.lastClose=newestClose;
   g_signal.lastBarTime=newestBarTime;
   g_signal.lastSequence=newestSequence;
   g_signal.digits=(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS);
   g_signal.point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   g_signal.initialized=true;
   g_signal.hasJournaledSignal=true;
   g_signal.journaledSignal=ticket.side;
   g_signal.hasJournaledWait=false;
   g_signal.journaledWaitReason=EMTT_SIG_WAIT_NONE;
  }

//+------------------------------------------------------------------+
//| 19.6 the plan across a restart. The file's open plan line is the  |
//| durable copy of the plan; the closed candles between its start bar |
//| and the newest closed candle are checked against its levels with   |
//| the 17.7 rules. The gap is never checked against the signals - the |
//| components' per-candle history is not stored, so a signal change   |
//| inside the gap is not reconstructed and the signal is next         |
//| evaluated at the first post-replay closed candle.                  |
//+------------------------------------------------------------------+
void EmttLearningResume(const datetime barTime,const MqlRates &rates[],
                        const EEmttRegime mood)
  {
   const int slot=g_learning.file.openTicket;
   if(slot<0)
      return;
   SEmttLearnTicket ticket=g_learning.file.tickets[slot];
   const int digits=g_learning.file.digits;
   const double point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   const int barCount=ArraySize(rates);
   const long newestSequence=(long)(g_evaluatedBarSequence-1);

   int startIndex=-1;
   for(int i=0;i<barCount;i++)
      if(rates[i].time==ticket.startBarTime)
        {
         startIndex=i;
         break;
        }
   long startSequence=-1;
   if(startIndex>=0)
      startSequence=(long)(newestSequence-(long)startIndex);

   int candlesChecked=0;
   int endedResult=EMTT_LEARN_RESULT_NONE;
   double endPrice=0.0;
   bool endedShared=false;
   datetime endBarTime=barTime;
   long endSequence=newestSequence;
   if(startIndex<0)
     {
      // 19.6: the start bar is no longer in the copied history, so the
      // plan cannot be checked and ends `chart` at the newest closed bar.
      endedResult=EMTT_LEARN_RESULT_CHART;
      if(barCount>0)
        {
         endPrice=rates[0].close;
         endBarTime=rates[0].time;
        }
     }
   else
      for(int i=startIndex-1;i>=0 && endedResult==EMTT_LEARN_RESULT_NONE;i--)
        {
         candlesChecked++;
         const bool touchesEntry=(rates[i].low<=ticket.entry &&
                                  rates[i].high>=ticket.entry);
         const bool touchesStop=(rates[i].low<=ticket.stop &&
                                 rates[i].high>=ticket.stop);
         const bool touchesTarget=(rates[i].low<=ticket.target &&
                                   rates[i].high>=ticket.target);
         if(ticket.state==EMTT_LEARN_STATE_PENDING)
           {
            // 17.7: one candle, more than one level - the worse result
            // counts: stop reached, cancelled, missed, target reached.
            if(touchesStop)
              {
               endedResult=(touchesEntry ? EMTT_LEARN_RESULT_STOP
                                         : EMTT_LEARN_RESULT_CANCELLED);
               endPrice=ticket.stop;
              }
            else if(touchesTarget)
              {
               endedResult=EMTT_LEARN_RESULT_MISSED;
               endPrice=ticket.target;
              }
            else if(touchesEntry)
              {
               ticket.state=EMTT_LEARN_STATE_ACTIVE;
               ticket.reachedBarTime=rates[i].time;
              }
           }
         else
           {
            if(touchesStop)
              {
               endedResult=EMTT_LEARN_RESULT_STOP;
               endPrice=ticket.stop;
              }
            else if(touchesTarget)
              {
               endedResult=EMTT_LEARN_RESULT_TARGET;
               endPrice=ticket.target;
              }
           }
         if(endedResult!=EMTT_LEARN_RESULT_NONE)
           {
            endBarTime=rates[i].time;
            endSequence=(long)(newestSequence-(long)i);
            const int touched=(touchesEntry ? 1 : 0)+(touchesStop ? 1 : 0)+
                              (touchesTarget ? 1 : 0);
            endedShared=(touched>1);
           }
        }

   if(endedResult!=EMTT_LEARN_RESULT_NONE)
     {
      int points=0;
      if(point>0.0)
         points=(int)MathRound((ticket.side>0 ? endPrice-ticket.entry
                                              : ticket.entry-endPrice)/point);
      int candles=0;
      if(startSequence>=0 && endSequence>=startSequence)
         candles=(int)(endSequence-startSequence);
      EmttLearnFileCloseTicket(g_learning.file,slot,endedResult,endedShared,
                               endPrice,points,candles);
      EmttLearnFileSave(g_learning.file,endBarTime,g_paramOpt.enabled);
      EmttJournalPlanResult(ticket.side,endedResult,endPrice,ticket.entry,
                            digits,point,startSequence,endSequence,
                            endedShared,true,endBarTime);
      if(endedResult==EMTT_LEARN_RESULT_TARGET ||
         endedResult==EMTT_LEARN_RESULT_STOP)
        {
         EmttLearnJournalUpdated(g_learning,endBarTime);
         g_learning.modelDirty=true;
        }
     }
   else
     {
      if(ticket.state==EMTT_LEARN_STATE_ACTIVE &&
         g_learning.file.tickets[slot].state==EMTT_LEARN_STATE_PENDING)
        {
         // 19.3 event 3: the gap reached the plan's Entry.
         EmttLearnFileMarkReached(g_learning.file,slot,ticket.reachedBarTime);
         EmttJournalEntryReached(ticket.side,ticket.entry,digits,
                                 ticket.reachedBarTime);
         EmttLearnFileSave(g_learning.file,barTime,g_paramOpt.enabled);
        }
      if(barCount>0)
         EmttLearningRestorePlan(ticket,startSequence,newestSequence,
                                 rates[0].time,rates[0].close,mood);
     }
   EmttLearnJournalResumed(ticket,candlesChecked,barTime);
  }

//+------------------------------------------------------------------+
//| Consume the one-shot events left by the last signal call: the     |
//| Summary counts (a started plan counts a signal, TARGET a win,     |
//| STOP a loss), the three 19.3 ticket events and the 17.8 journal   |
//| lines of a plan start and a plan end. Emtt_Signal.mqh is called   |
//| with writeJournal=false, so Phase 7 prints those lines itself -   |
//| only the plan start line can carry the learning part of 19.7.     |
//| Called right after each EmttSignalAdvance / MarketClosed /        |
//| ChartChanged call, never on a tick.                               |
//+------------------------------------------------------------------+
void EmttConsumeSignalEvents(const datetime barTime,const double barHigh,
                             const double barLow,const int spreadPts,
                             const double atr)
  {
   // Resolve a broker fill before a paper plan end can be labeled; the
   // real trade evidence then takes precedence without a later relabel.
   if(g_trade.initialized)
     {
      EmttTradeManagerObserve(g_trade,barTime);
      EmttLearningRecoverTradeContext();
      EmttLearningRecordTradeEvents();
     }
   if(g_signal.signalStarted)
      EmttSummaryOnSignal(g_summary);
   bool ticketBecameTrade=false;
   if(g_signal.endedResult==EMTT_PLAN_RESULT_TARGET ||
      g_signal.endedResult==EMTT_PLAN_RESULT_STOP)
     {
      int slot=-1;
      if(g_trade.planStartBarTime>0)
         slot=EmttLearnFileFindPlan(g_learning.file,
                                    g_trade.planStartBarTime,g_trade.side);
      if(slot>=0)
        {
         ticketBecameTrade=(
            g_learning.file.tickets[slot].tradeFilledTime>0 ||
            (g_trade.side==g_learning.file.tickets[slot].side &&
             g_trade.planStartBarTime==
                g_learning.file.tickets[slot].startBarTime &&
             (g_trade.positionOpen || g_trade.closeRecordPending)));
        }
     }
   if(!ticketBecameTrade &&
      g_signal.endedResult==EMTT_PLAN_RESULT_TARGET)
      EmttSummaryOnWin(g_summary);
   else if(!ticketBecameTrade &&
           g_signal.endedResult==EMTT_PLAN_RESULT_STOP)
      EmttSummaryOnLoss(g_summary);
   if(g_signal.signalStarted)
      EmttLearningRecordPlanStart(barTime,spreadPts,atr);
   EmttLearningRecordEntryReached(barTime);
   if(g_signal.endedResult!=EMTT_PLAN_RESULT_NONE)
      EmttLearningRecordPlanEnd(barTime,barHigh,barLow);
   g_signal.signalStarted=false;
   g_signal.endedResult=EMTT_PLAN_RESULT_NONE;
  }

//+------------------------------------------------------------------+
//| Build the Phase-2 panel snapshot without changing the renderer    |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Phase 11 (28.2): SIGNAL row colour, size and weight by tier.      |
//| Low = soft shade, Normal = intermediate shade, Confident = full   |
//| colour, High = full colour + bold; every BUY/SELL stays at the    |
//| rule-16 signal size.                                              |
//+------------------------------------------------------------------+
void EmttTierSignalStyle(const int side,const int confidence,
                         SEmttPanelData &d)
  {
   const int tier=EmttTierOf(confidence);
   d.signalSize=EMTT_FSIZE_SIG;
   d.signalBold=(tier==EMTT_TIER_HIGH);
   if(tier==EMTT_TIER_LOW)
      d.signalClr=(side>0 ? EMTT_CLR_BUY_LOW : EMTT_CLR_SELL_LOW);
   else if(tier==EMTT_TIER_NORMAL)
      d.signalClr=(side>0 ? EMTT_CLR_BUY_NORMAL : EMTT_CLR_SELL_NORMAL);
   else
      d.signalClr=(side>0 ? EMTT_CLR_BUY : EMTT_CLR_SELL);
  }

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

   // Phase 6: a signal needs all four views ready; until then Rows 2-7
   // show "--" exactly like the loading state (17.2 rule 4, 17.6).
   const bool sigReady=(g_supertrend.ready && g_smc.ready &&
                        g_volumeFlow.ready && g_mtf.ready);
   const bool planShowing=(sigReady && g_signal.plan.active &&
                           g_signal.signal!=0);

   d.header=EmttHeaderText();
   d.signalClr=EMTT_CLR_TEXT;
   d.signalSize=EMTT_FSIZE;
   d.signalBold=false;
   d.statusClr=EMTT_CLR_TEXT;
   d.floatingClr=EMTT_CLR_TEXT;
   d.showLive=false;

   // Phase 2 fills only the fields it actually measures; Phase 6 fills
   // Rows 2-8 from the signal state. Money values are estimated from proposed
   // volume; the manager replaces them with broker volume when available.
   d.regime="Regime: --";
   d.signal="SIGNAL: --";
   // Phase 11 (28.2): "--%" only while no number exists (loading,
   // market closed, incompatible chart, views not ready).
   d.confidence=EmttTierConfidenceRow(-1);
   d.entry="Entry: -- / --  (-- pts away)";
   d.stopLoss="Stop Loss: -- / --  (-- pts)";
   d.takeProfit="Take Profit: -- / --  (-- pts)";
   d.riskReward="Risk:Reward: --";
   d.session="Session: -- | Expected Duration: --";
   d.why="--";
   d.status="";

   if(!compatible)
     {
      // Rule 19 wins over all state messages on unsupported timeframes.
      d.regime="Regime: --";
      d.session="Session: -- | Expected Duration: --";
      d.why="--";
      d.status="Incompatible chart. Switch to M5/M15/M30.";
      d.statusClr=EMTT_CLR_SELL;
     }
   else if(!g_marketOpen)
     {
      // 17.6: MARKET CLOSED leaves Rows 2-9 at "--".
      d.regime="Regime: MARKET CLOSED";
      d.session="Session: -- | Expected Duration: --";
      d.why="--";
      d.status=EmttStatusForRegime(EMTT_REGIME_MARKET_CLOSED);
     }
   else
     {
      if(!g_snapshotReady)
        {
         d.session="Session: "+g_sessionName+" | Expected Duration:";
         d.regime="Regime: --";
         d.why="--";
         if(g_historyAvailable<g_historyRequired)
            d.status=StringFormat("Waiting — Loading chart history (%d/%d candles)",
                                  g_historyAvailable,g_historyRequired);
         else
            d.status="Waiting — Preparing closed-bar indicators / higher timeframe";
        }
      else
        {
         // Confidence belongs to the evaluated candle, not to plan validity.
         // A stop/target rejection must never hide an already computed number.
         d.confidence=EmttTierConfidenceRow(g_signal.viewsReady ?
                                            g_signal.confidence : -1);
         // Row 8: the session is always measured; the Expected Duration
         // fills only while a plan is showing.
         if(sigReady)
            d.session="Session: "+g_sessionName+" | Expected Duration: "+
                      (planShowing ? g_signal.plan.duration : "--");
         else
            d.session="Session: "+g_sessionName+" | Expected Duration:";

         if(sigReady)
           {
            // Row 2: the signal with its glyph, colour and size (17.6),
            // graded by the Phase 11 tier of the displayed number (28.2).
            if(g_signal.signal>0)
              {
               d.signal="SIGNAL: "+EmttGlyph(EMTT_G_BUY)+" BUY";
               EmttTierSignalStyle(1,g_signal.confidence,d);
              }
            else if(g_signal.signal<0)
              {
               d.signal="SIGNAL: "+EmttGlyph(EMTT_G_SELL)+" SELL";
               EmttTierSignalStyle(-1,g_signal.confidence,d);
              }
            else
               d.signal="SIGNAL: "+EmttGlyph(EMTT_SIG_GLYPH_WAIT)+" WAIT";
            // Row 3: the real number and its tier whenever one exists,
            // including the below-35% WAIT (28.2).
            if(planShowing)
              {
               // Rows 4-7: the fixed plan levels. Row 4's distance is
               // measured from the dealing price and refreshes live;
               // Rows 5-6 are measured from Entry.
               const double dealing=(g_signal.signal>0 ? ask : bid);
               const int entryPts=(point>0.0 ?
                                   (int)MathRound(MathAbs(dealing-
                                                       g_signal.plan.entry)/
                                                  point) : 0);
               const int stopPts=(point>0.0 ?
                                  (int)MathRound(MathAbs(g_signal.plan.entry-
                                                         g_signal.plan.stop)/
                                                 point) : 0);
               const int targetPts=(point>0.0 ?
                                    (int)MathRound(MathAbs(g_signal.plan.target-
                                                           g_signal.plan.entry)/
                                                   point) : 0);
               d.entry="Entry: "+
                       DoubleToString(g_signal.plan.entry,digits)+
                       " / --  ("+IntegerToString(entryPts)+" pts away)";
               d.stopLoss="Stop Loss: "+
                          DoubleToString(g_signal.plan.stop,digits)+
                          " / --  ("+IntegerToString(stopPts)+" pts)";
               d.takeProfit="Take Profit: "+
                            DoubleToString(g_signal.plan.target,digits)+
                            " / --  ("+IntegerToString(targetPts)+" pts)";
               // Signal-only preview: proposed volume, not an executed trade.
               double tickValue=SymbolInfoDouble(g_symbol,SYMBOL_TRADE_TICK_VALUE_LOSS);
               if(tickValue<=0.0)
                  tickValue=SymbolInfoDouble(g_symbol,SYMBOL_TRADE_TICK_VALUE);
               const double previewLots=EmttTradeResolveLots((int)InpLotMode,
                  AccountInfoDouble(ACCOUNT_BALANCE),g_signal.plan.entry,
                  g_signal.plan.stop,SymbolInfoDouble(g_symbol,SYMBOL_TRADE_TICK_SIZE),
                  tickValue,g_signal.confidence,g_trade.newsSizeMultiplier,
                  SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_MIN),
                  SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_MAX),
                  SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_STEP));
               EmttTradeManagerPlanMoney(d,g_symbol,g_signal.plan.side,previewLots,
                  g_signal.plan.entry,g_signal.plan.stop,g_signal.plan.target,
                  dealing,point,digits);
               d.riskReward="Risk:Reward: 1:"+
                            DoubleToString(g_signal.plan.riskReward,1);
              }
           }

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

         // Phase 3 (11.8): Row 9 appends the Supertrend clause and Row 10
         // reads the context status once a direction exists. The score, the
         // trailing reference and the facts are never displayed (rule 11).
         d.why=EmttWhyWithSupertrend(d.why,g_supertrend);
         if(g_supertrend.ready && g_supertrend.direction!=0)
            d.status=EmttStatusForSupertrend();

         // Phase 4 adds one compact structure clause to Row 9 and owns Row
         // 10 only once it has a confirmed high, low and selected ATR. Its
         // status function implements CHoCH > BOS > sweep precedence.
         d.why=EmttWhyWithSmc(d.why,g_smc,digits);
         const string smcStatus=EmttStatusForSmc(g_smc);
         if(smcStatus!="")
            d.status=smcStatus;

         // Phase 5 (15.10) appends the volume-flow clause and then the MTF
         // clause, in this fixed order, each only when it is non-empty. The
         // agreement word is recomposed from the live chart Supertrend
         // direction, so it is never older than the newest closed bar.
         d.why=EmttWhyWithVolumeFlow(d.why,g_volumeFlow,digits);
         d.why=EmttWhyWithMtf(d.why,g_mtf,g_supertrend.direction);

         // Phase 7 (19.7): Row 9 gains one sixth clause, appended last,
         // with the same " | " rule as 15.10 - appended only when it is
         // non-empty, never a trailing " | ". The WHY row itself was
         // retired by the 2026-10-11 panel revamp and the author decided
         // (2026-10-11) that the learning clause is carried by the journal
         // only, so the renderer ignores this field: the clause is built
         // here, exactly as 19.7 writes it, and shown by the journal lines
         // of the plan start, of a labeled result and of a resume.
         d.why=EmttLearnWhyAppend(d.why,
                 EmttLearnWhyClause(g_learning,g_learning.reading));

         // Row 10: the Phase 6 signal line replaces the terminal line of
         // 15.10 once all four views are ready; the Phase 3-5 event lines
         // show only while they are not (17.6).
         if(sigReady)
           {
            d.status=EmttSignalStatusText(g_signal,bid,ask);
            // The signal's pending plan is not a broker order. Keep this
            // one-line panel message short enough for ordinary chart widths;
            // the trade manager below supplies the actual order status.
            if(StringFind(d.status,"waiting for price to reach entry")>=0)
               d.status="Signal plan - entry not reached yet.";
            // Phase 7 (19.7): the one WAIT reason Phase 7 adds is checked
            // before the first reason of 17.6, so that reason can never
            // hide the cause. The stay-margin line above is unchanged and
            // was judged on the adjusted number.
            if(g_signal.signal==0 && !g_signal.plan.active)
              {
               // Phase 11 (28.3): the display gate is the 35% tier floor.
               const string learningStatus=EmttLearnHoldReason(
                  g_learning,g_learning.reading,EMTT_TIER_DISPLAY_MIN);
               if(learningStatus!="")
                  d.status=learningStatus;
              }
           }
         else
           {
            // Phase 5 Row 10 precedence: MTF flip > CHoCH > BOS > sweep >
            // CVD flip > Phase 3 > Phase 2, and the combined context-only
            // line once all four components are ready and nothing is fresh.
            const string volumeFlowStatus=EmttStatusForVolumeFlow(g_volumeFlow);
            const string mtfStatus=EmttStatusForMtf(g_mtf);
            const bool smcFresh=(smcStatus!="" &&
                                 !EmttSmcStatusIsContextOnly(smcStatus));
            const bool fullContext=(g_supertrend.ready &&
                                    g_supertrend.direction!=0 && g_smc.ready &&
                                    g_volumeFlow.ready && g_mtf.ready);
            if(fullContext && !smcFresh && volumeFlowStatus=="" &&
               mtfStatus=="")
               d.status=EMTT_ROW10_CONTEXT_ONLY;
            else
              {
               if(volumeFlowStatus!="")
                  d.status=volumeFlowStatus;
               if(smcFresh)
                  d.status=smcStatus;
               if(mtfStatus!="")
                  d.status=mtfStatus;
              }
           }
        }
     }

   // Summary rows: real Today / All-Time counts from the per-symbol,
   // per-timeframe file. Shown in every state - the file does not
   // depend on the views, the market or the timeframe gate.
   EmttSummaryRollover(g_summary);
   d.summaryToday=EmttSummaryTodayText(g_summary);
   d.summaryAllTime=EmttSummaryAllTimeText(g_summary);

   // A live Emtt position is detected by symbol + magic; manual trades never
   // make the block appear. Phase 2 intentionally does not invent trade data.
   // Phase 8: the manager owns all live broker values; manual positions
   // remain excluded by symbol + magic in EmttTradeManagerFillPanel.
   EmttTradeManagerFillPanel(d,g_trade,g_symbol,InpMagicNumber,g_timeframe,
                             compatible,bid,ask,point,digits);
   EmttTradeManagerPanelStatus(d);

   // Rule 2: the arrow marks the dealing side - Ask for BUY, Bid for
   // SELL, no marker while WAIT or in any "--" state (17.6).
   const string arrow=EmttGlyph(EMTT_G_ARROW);
   if(planShowing && g_signal.signal>0)
      d.priceRow="Bid: "+DoubleToString(bid,digits)+"  |  "+
                 arrow+"Ask: "+DoubleToString(ask,digits)+"  |  "+
                 "Spread: "+IntegerToString(spreadPts)+" pts";
   else if(planShowing && g_signal.signal<0)
      d.priceRow=arrow+"Bid: "+DoubleToString(bid,digits)+"  |  "+
                 "Ask: "+DoubleToString(ask,digits)+"  |  "+
                 "Spread: "+IntegerToString(spreadPts)+" pts";
   else
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
   g_historyRequired=EmttResolveHistoryRequired(g_timeframe);
   EmttDynamicReset(g_dynamic);
   EmttRegimeReset(g_regimeState);
   EmttSupertrendReset(g_supertrend);
   EmttSmcReset(g_smc);
   EmttVfReset(g_volumeFlow);
   EmttMtfReset(g_mtf,g_mtfContext);
   EmttSignalReset(g_signal);
   EmttResetFoundationSnapshot();
   g_symbolValidationBars=0;
   // Phase 7 (19.3): the learning state starts empty; the record of this
   // symbol and timeframe is bound, loaded and rewritten by the replay.
   EmttLearnStateReset(g_learning);
   EmttTradeManagerInit(g_trade,g_symbol,g_timeframe,InpMagicNumber);
   // Phase 10 (25.2 rule 11): the tick buffer starts empty; an adopted
   // position gets a fresh session and warmup on its first tick.
   EmttTickDivReset(g_tickDiv);
   // Phase 11 (28.4): whole numbers 35..100; anything else is clamped once.
   g_autoTradeAbove=EmttTierAutoTradeAbove(InpAutoTradeAbove);
   if(EmttPendingBars(InpPendingValidityBars)!=InpPendingValidityBars)
      PrintFormat("Emtt | Pending validity clamped | requested %d bars | using %d",
                  InpPendingValidityBars,EmttPendingBars(InpPendingValidityBars));
   if(g_autoTradeAbove!=InpAutoTradeAbove)
      PrintFormat("Emtt | Auto-trade above %d%% is outside %d-%d | using %d%%",
                  InpAutoTradeAbove,EMTT_TIER_AUTO_MIN,EMTT_TIER_AUTO_MAX,
                  g_autoTradeAbove);
   EmttParamOptReset(g_paramOpt,InpParamOptimization);
   EmttParamOptimizationAttachAndLoad(iTime(g_symbol,g_timeframe,1));
   if(g_paramOpt.enabled) EmttSyncFrozenPositionContext();
   // Panel revamp: Today / All-Time counts for this symbol + timeframe.
   EmttSummaryInit(g_summary,g_symbol,g_timeframe);
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
   if(g_trade.initialized)
     {
      SEmttTradeRuntime runtime;
      EmttTradeManagerBuildRuntime(runtime);
      EmttTradeManagerObserve(g_trade,runtime.barTime);
      EmttLearningRecoverTradeContext();
      EmttLearningRecordTradeEvents();
     }
   EmttSummarySave(g_summary); // flush the Summary counts
   EmttParamOptimizationSaveOnExit();
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
// Phase 10 (25.1): after the panel, the latest tick feeds the O(1)
// divergence state of an open Emtt position (nothing when flat).
void OnTick()
  {
   UpdatePanel();
   EmttTradeManagerFeedTick(g_trade,g_tickDiv);
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
