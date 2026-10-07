//+------------------------------------------------------------------+
//|                                      Emtt_DynamicParams.mqh      |
//|          Phase 2: symbol class, volatility buckets, parameters   |
//|                   Spec: Emtt.md sections 9.2.1-4                |
//+------------------------------------------------------------------+
#ifndef EMTT_DYNAMIC_PARAMS_MQH
#define EMTT_DYNAMIC_PARAMS_MQH

#define EMTT_VOLATILITY_WINDOW       200
#define EMTT_PARAMETER_PAUSE_BARS    2
#define EMTT_HISTORY_REQUIRED        (EMTT_VOLATILITY_WINDOW+14)

//--- Shared phase-2 states -----------------------------------------
enum EEmttAssetClass
  {
   EMTT_CLASS_FOREX_MAJOR=0,
   EMTT_CLASS_FOREX_CROSS,
   EMTT_CLASS_METALS,
   EMTT_CLASS_CRYPTO,
   EMTT_CLASS_INDICES,
   EMTT_CLASS_GENERIC
  };

enum EEmttVolatility
  {
   EMTT_VOL_UNKNOWN=-1,
   EMTT_VOL_LOW=0,
   EMTT_VOL_NORMAL=1,
   EMTT_VOL_HIGH=2
  };

enum EEmttRegime
  {
   EMTT_REGIME_UNKNOWN=0,
   EMTT_REGIME_TRENDING_BULLISH,
   EMTT_REGIME_TRENDING_BEARISH,
   EMTT_REGIME_RANGING,
   EMTT_REGIME_VOLATILE,
   EMTT_REGIME_TRANSITION,
   EMTT_REGIME_MARKET_CLOSED
  };

//--- Measurement parameters currently defined by Phase 2 ------------
struct SEmttDynamicState
  {
   bool            initialized;
   EEmttAssetClass assetClass;
   EEmttVolatility volatility;
   int             atrPeriod;
   int             erPeriod;
   int             kamaFast;
   int             kamaMedium;
   int             kamaSlow;
   int             confidenceThreshold;
   bool            thresholdFrozen;
   int             frozenThreshold;
   long            lastAtrChangeBar;
   long            lastErChangeBar;
   long            lastKamaFastChangeBar;
   long            lastKamaMediumChangeBar;
   long            lastKamaSlowChangeBar;
   long            lastThresholdChangeBar;
  };

//+------------------------------------------------------------------+
//| Friendly names used in the journal                               |
//+------------------------------------------------------------------+
string EmttAssetClassName(const EEmttAssetClass assetClass)
  {
   switch(assetClass)
     {
      case EMTT_CLASS_FOREX_MAJOR: return "Forex Major";
      case EMTT_CLASS_FOREX_CROSS: return "Forex Cross";
      case EMTT_CLASS_METALS:      return "Metals";
      case EMTT_CLASS_CRYPTO:      return "Crypto";
      case EMTT_CLASS_INDICES:     return "Indices";
      default:                     return "Generic";
     }
  }

string EmttVolatilityName(const EEmttVolatility volatility)
  {
   switch(volatility)
     {
      case EMTT_VOL_LOW:    return "LOW";
      case EMTT_VOL_NORMAL: return "NORMAL";
      case EMTT_VOL_HIGH:   return "HIGH";
      default:              return "UNKNOWN";
     }
  }

string EmttRegimeContextName(const EEmttRegime regime)
  {
   switch(regime)
     {
      case EMTT_REGIME_TRENDING_BULLISH: return "TRENDING (Bullish)";
      case EMTT_REGIME_TRENDING_BEARISH: return "TRENDING (Bearish)";
      case EMTT_REGIME_RANGING:           return "RANGING";
      case EMTT_REGIME_VOLATILE:          return "VOLATILE";
      case EMTT_REGIME_TRANSITION:        return "TRANSITION";
      case EMTT_REGIME_MARKET_CLOSED:     return "MARKET CLOSED";
      default:                            return "UNKNOWN";
     }
  }

//+------------------------------------------------------------------+
//| Strip the broker suffixes explicitly listed by the specification  |
//+------------------------------------------------------------------+
string EmttNormalizeSymbol(const string source)
  {
   string symbol=source;
   StringToUpper(symbol);
   bool removed=true;
   while(removed && StringLen(symbol)>0)
     {
      removed=false;
      const int length=StringLen(symbol);
      if(length>=4 && StringSubstr(symbol,length-4)==".RAW")
        {
         symbol=StringSubstr(symbol,0,length-4);
         removed=true;
        }
      else if(length>=4 && StringSubstr(symbol,length-4)==".PRO")
        {
         symbol=StringSubstr(symbol,0,length-4);
         removed=true;
        }
      else if(length>=4 && StringSubstr(symbol,length-4)==".ECN")
        {
         symbol=StringSubstr(symbol,0,length-4);
         removed=true;
        }
      else if(length>=2 && (StringSubstr(symbol,length-2)==".I" ||
                            StringSubstr(symbol,length-2)==".R"))
        {
         symbol=StringSubstr(symbol,0,length-2);
         removed=true;
        }
      else if(length>=1 && (StringSubstr(symbol,length-1)=="M" ||
                            StringSubstr(symbol,length-1)=="+" ||
                            StringSubstr(symbol,length-1)=="#"))
        {
         symbol=StringSubstr(symbol,0,length-1);
         removed=true;
        }
     }
   return symbol;
  }

bool EmttIsCurrencyCode(const string code)
  {
   return(code=="EUR" || code=="GBP" || code=="USD" || code=="JPY" ||
          code=="CHF" || code=="CAD" || code=="AUD" || code=="NZD" ||
          code=="SEK" || code=="NOK" || code=="DKK" || code=="SGD" ||
          code=="HKD" || code=="CNH" || code=="CNY" || code=="MXN" ||
          code=="TRY" || code=="ZAR" || code=="PLN" || code=="HUF" ||
          code=="CZK" || code=="THB" || code=="ILS" || code=="KRW" ||
          code=="INR" || code=="RUB");
  }

//+------------------------------------------------------------------+
//| Infer the asset class from the normalized chart symbol            |
//+------------------------------------------------------------------+
EEmttAssetClass EmttClassifySymbol(const string source)
  {
   const string symbol=EmttNormalizeSymbol(source);
   if(StringFind(symbol,"XAU")>=0 || StringFind(symbol,"XAG")>=0 ||
      StringFind(symbol,"XPT")>=0 || StringFind(symbol,"XPD")>=0 ||
      StringFind(symbol,"GOLD")>=0 || StringFind(symbol,"SILVER")>=0 ||
      StringFind(symbol,"PLATINUM")>=0 || StringFind(symbol,"PALLADIUM")>=0)
      return EMTT_CLASS_METALS;
   if(StringFind(symbol,"BTC")>=0 || StringFind(symbol,"ETH")>=0 ||
      StringFind(symbol,"LTC")>=0 || StringFind(symbol,"XRP")>=0 ||
      StringFind(symbol,"DOGE")>=0 || StringFind(symbol,"ADA")>=0 ||
      StringFind(symbol,"SOL")>=0 || StringFind(symbol,"BNB")>=0 ||
      StringFind(symbol,"DOT")>=0 || StringFind(symbol,"AVAX")>=0 ||
      StringFind(symbol,"LINK")>=0 || StringFind(symbol,"CRYPTO")>=0)
      return EMTT_CLASS_CRYPTO;
   if(StringFind(symbol,"US30")>=0 || StringFind(symbol,"NAS")>=0 ||
      StringFind(symbol,"USTEC")>=0 || StringFind(symbol,"US500")>=0 ||
      StringFind(symbol,"US100")>=0 || StringFind(symbol,"DJI")>=0 ||
      StringFind(symbol,"SPX")>=0 || StringFind(symbol,"DAX")>=0 ||
      StringFind(symbol,"DE40")>=0 || StringFind(symbol,"GER")>=0 ||
      StringFind(symbol,"UK100")>=0 || StringFind(symbol,"FTSE")>=0 ||
      StringFind(symbol,"JP225")>=0 || StringFind(symbol,"NIK")>=0 ||
      StringFind(symbol,"AUS200")>=0 || StringFind(symbol,"HK50")>=0 ||
      StringFind(symbol,"EU50")>=0 || StringFind(symbol,"STOXX")>=0 ||
      StringFind(symbol,"CAC")>=0 || StringFind(symbol,"FRA")>=0)
      return EMTT_CLASS_INDICES;

   if(StringLen(symbol)>=6)
     {
      const string base=StringSubstr(symbol,0,3);
      const string quote=StringSubstr(symbol,3,3);
      if(EmttIsCurrencyCode(base) && EmttIsCurrencyCode(quote))
        {
         if(base=="USD" || quote=="USD")
            return EMTT_CLASS_FOREX_MAJOR;
         return EMTT_CLASS_FOREX_CROSS;
        }
     }
   return EMTT_CLASS_GENERIC;
  }

//+------------------------------------------------------------------+
//| Phase 2 matrix. Each tuple is ATR / ER / KAMA fast-medium-slow.  |
//+------------------------------------------------------------------+
void EmttMatrixValues(const EEmttAssetClass assetClass,
                      const EEmttVolatility volatility,
                      int &atrPeriod,int &erPeriod,
                      int &kamaFast,int &kamaMedium,int &kamaSlow)
  {
   const bool low=(volatility==EMTT_VOL_LOW);
   const bool high=(volatility==EMTT_VOL_HIGH);
   kamaSlow=50;

   switch(assetClass)
     {
      case EMTT_CLASS_FOREX_MAJOR:
         if(high) { atrPeriod=14; erPeriod=14; kamaFast=13; kamaMedium=26; }
         else     { atrPeriod=10; erPeriod=10; kamaFast=9;  kamaMedium=21; }
         break;

      case EMTT_CLASS_FOREX_CROSS:
         if(low)  { atrPeriod=10; erPeriod=10; kamaFast=9;  kamaMedium=21; }
         else if(high) { atrPeriod=14; erPeriod=14; kamaFast=13; kamaMedium=26; }
         else     { atrPeriod=14; erPeriod=14; kamaFast=13; kamaMedium=21; }
         break;

      case EMTT_CLASS_METALS:
         if(low)  { atrPeriod=10; erPeriod=14; kamaFast=9;  kamaMedium=21; }
         else if(high) { atrPeriod=21; erPeriod=21; kamaFast=13; kamaMedium=26; }
         else     { atrPeriod=14; erPeriod=14; kamaFast=13; kamaMedium=21; }
         break;

      case EMTT_CLASS_CRYPTO:
         if(low)  { atrPeriod=14; erPeriod=21; kamaFast=13; kamaMedium=26; }
         else if(high) { atrPeriod=28; erPeriod=28; kamaFast=21; kamaMedium=34; }
         else     { atrPeriod=21; erPeriod=21; kamaFast=13; kamaMedium=26; }
         break;

      case EMTT_CLASS_INDICES:
      case EMTT_CLASS_GENERIC:
      default:
         if(low)  { atrPeriod=10; erPeriod=14; kamaFast=9;  kamaMedium=21; }
         else if(high) { atrPeriod=14; erPeriod=21; kamaFast=13; kamaMedium=26; }
         else     { atrPeriod=14; erPeriod=14; kamaFast=13; kamaMedium=21; }
         break;
     }
  }

int EmttMatrixField(const EEmttAssetClass assetClass,
                    const EEmttVolatility volatility,const int field)
  {
   int atr,er,kf,km,ks;
   EmttMatrixValues(assetClass,volatility,atr,er,kf,km,ks);
   if(field==0) return atr;
   if(field==1) return er;
   if(field==2) return kf;
   if(field==3) return km;
   return ks;
  }

int EmttClampMatrixField(const EEmttAssetClass assetClass,
                         const EEmttVolatility volatility,const int field)
  {
   int minimum=2147483647;
   int maximum=0;
   for(int col=EMTT_VOL_LOW;col<=EMTT_VOL_HIGH;col++)
     {
      const int value=EmttMatrixField(assetClass,(EEmttVolatility)col,field);
      minimum=(int)MathMin(minimum,value);
      maximum=(int)MathMax(maximum,value);
     }
   const int selected=EmttMatrixField(assetClass,volatility,field);
   return (int)MathMax(minimum,MathMin(maximum,selected));
  }

//+------------------------------------------------------------------+
//| Resolve the measurement column. No lookback parameter exists yet, |
//| so the timeframe layer has no period to scale in this phase.      |
//+------------------------------------------------------------------+
void EmttResolveMeasurementParams(const EEmttAssetClass assetClass,
                                  const EEmttVolatility volatility,
                                  int &atrPeriod,int &erPeriod,
                                  int &kamaFast,int &kamaMedium,int &kamaSlow)
  {
   EmttMatrixValues(assetClass,volatility,atrPeriod,erPeriod,
                    kamaFast,kamaMedium,kamaSlow);
   atrPeriod=EmttClampMatrixField(assetClass,volatility,0);
   erPeriod=EmttClampMatrixField(assetClass,volatility,1);
   kamaFast=EmttClampMatrixField(assetClass,volatility,2);
   kamaMedium=EmttClampMatrixField(assetClass,volatility,3);
   kamaSlow=EmttClampMatrixField(assetClass,volatility,4);
  }

//+------------------------------------------------------------------+
//| Percentile rank: mid-rank ties against the other 199 observations |
//+------------------------------------------------------------------+
double EmttPercentileRank(const double &values[],const int firstIndex,
                          const int referenceCount)
  {
   if(referenceCount<=0 || firstIndex<0)
      return -1.0;
   const double value=values[firstIndex];
   if(!MathIsValidNumber(value) || value<=0.0)
      return -1.0;
   int below=0;
   int equal=0;
   for(int i=1;i<=referenceCount;i++)
     {
      const double other=values[firstIndex+i];
      if(!MathIsValidNumber(other) || other<=0.0)
         return -1.0;
      if(other<value)
         below++;
      else if(other==value)
         equal++;
     }
   return 100.0*((double)below+0.5*(double)equal)/(double)referenceCount;
  }

EEmttVolatility EmttInitialVolatilityBucket(const double percentile)
  {
   if(percentile>70.0) return EMTT_VOL_HIGH;
   if(percentile<30.0) return EMTT_VOL_LOW;
   return EMTT_VOL_NORMAL;
  }

// The returned target is hysteretic and at most one column from current.
EEmttVolatility EmttVolatilityTarget(const EEmttVolatility current,
                                     const double percentile)
  {
   if(current==EMTT_VOL_LOW)
      return(percentile>33.0 ? EMTT_VOL_NORMAL : EMTT_VOL_LOW);
   if(current==EMTT_VOL_HIGH)
      return(percentile<67.0 ? EMTT_VOL_NORMAL : EMTT_VOL_HIGH);
   if(percentile>70.0)
      return EMTT_VOL_HIGH;
   if(percentile<30.0)
      return EMTT_VOL_LOW;
   return EMTT_VOL_NORMAL;
  }

int EmttConfidenceThreshold(const EEmttRegime regime)
  {
   switch(regime)
     {
      case EMTT_REGIME_TRENDING_BULLISH:
      case EMTT_REGIME_TRENDING_BEARISH: return 60;
      case EMTT_REGIME_RANGING:           return 70;
      case EMTT_REGIME_VOLATILE:          return 70;
      case EMTT_REGIME_TRANSITION:        return 75;
      default:                            return 0;
     }
  }

void EmttDynamicReset(SEmttDynamicState &state)
  {
   state.initialized=false;
   state.assetClass=EMTT_CLASS_GENERIC;
   state.volatility=EMTT_VOL_UNKNOWN;
   state.atrPeriod=0;
   state.erPeriod=0;
   state.kamaFast=0;
   state.kamaMedium=0;
   state.kamaSlow=0;
   state.confidenceThreshold=0;
   state.thresholdFrozen=false;
   state.frozenThreshold=0;
   state.lastAtrChangeBar=-1000000;
   state.lastErChangeBar=-1000000;
   state.lastKamaFastChangeBar=-1000000;
   state.lastKamaMediumChangeBar=-1000000;
   state.lastKamaSlowChangeBar=-1000000;
   state.lastThresholdChangeBar=-1000000;
  }

void EmttDynamicSeed(SEmttDynamicState &state,const EEmttAssetClass assetClass,
                     const EEmttVolatility volatility,const EEmttRegime regime,
                     const long barIndex,const datetime barTime,
                     const bool writeJournal)
  {
   EmttDynamicReset(state);
   state.assetClass=assetClass;
   state.volatility=volatility;
   EmttResolveMeasurementParams(assetClass,volatility,state.atrPeriod,
                                state.erPeriod,state.kamaFast,
                                state.kamaMedium,state.kamaSlow);
   state.confidenceThreshold=EmttConfidenceThreshold(regime);
   state.lastAtrChangeBar=barIndex-1000000;
   state.lastErChangeBar=barIndex-1000000;
   state.lastKamaFastChangeBar=barIndex-1000000;
   state.lastKamaMediumChangeBar=barIndex-1000000;
   state.lastKamaSlowChangeBar=barIndex-1000000;
   state.lastThresholdChangeBar=barIndex-1000000;
   state.initialized=true;
   if(writeJournal)
      PrintFormat("Emtt | Parameters initialized | class %s | volatility %s | ATR %d | ER %d | KAMA %d/%d/%d | confidence threshold %d%% | bar %s",
                  EmttAssetClassName(assetClass),EmttVolatilityName(volatility),
                  state.atrPeriod,state.erPeriod,state.kamaFast,
                  state.kamaMedium,state.kamaSlow,state.confidenceThreshold,
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
  }

bool EmttCanChangeAt(const long currentBar,const long lastChangeBar)
  {
   // A changed parameter stays fixed during each of the next two closed bars.
   return(currentBar-lastChangeBar>EMTT_PARAMETER_PAUSE_BARS);
  }

//+------------------------------------------------------------------+
//| Move no more than one volatility column; change atomically so the |
//| published bucket and all resolved measurement values always agree.|
//+------------------------------------------------------------------+
bool EmttDynamicUpdateVolatility(SEmttDynamicState &state,
                                 const double percentile,const long barIndex,
                                 const datetime barTime,const bool writeJournal)
  {
   if(!state.initialized || percentile<0.0)
      return false;
   const EEmttVolatility target=EmttVolatilityTarget(state.volatility,percentile);
   if(target==state.volatility)
      return false;

   EEmttVolatility next=state.volatility;
   if((int)target>(int)state.volatility)
      next=(EEmttVolatility)((int)state.volatility+1);
   else
      next=(EEmttVolatility)((int)state.volatility-1);

   int atr,er,kf,km,ks;
   EmttResolveMeasurementParams(state.assetClass,next,atr,er,kf,km,ks);
   if(atr!=state.atrPeriod && !EmttCanChangeAt(barIndex,state.lastAtrChangeBar)) return false;
   if(er!=state.erPeriod && !EmttCanChangeAt(barIndex,state.lastErChangeBar)) return false;
   if(kf!=state.kamaFast && !EmttCanChangeAt(barIndex,state.lastKamaFastChangeBar)) return false;
   if(km!=state.kamaMedium && !EmttCanChangeAt(barIndex,state.lastKamaMediumChangeBar)) return false;
   if(ks!=state.kamaSlow && !EmttCanChangeAt(barIndex,state.lastKamaSlowChangeBar)) return false;

   const EEmttVolatility previous=state.volatility;
   if(atr!=state.atrPeriod)
     {
      if(writeJournal)
         PrintFormat("Emtt | ATR period %d -> %d | volatility %s -> %s | percentile %.1f | bar %s",
                     state.atrPeriod,atr,EmttVolatilityName(previous),
                     EmttVolatilityName(next),percentile,
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
      state.atrPeriod=atr;
      state.lastAtrChangeBar=barIndex;
     }
   if(er!=state.erPeriod)
     {
      if(writeJournal)
         PrintFormat("Emtt | Kaufman ER period %d -> %d | volatility %s -> %s | percentile %.1f | bar %s",
                     state.erPeriod,er,EmttVolatilityName(previous),
                     EmttVolatilityName(next),percentile,
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
      state.erPeriod=er;
      state.lastErChangeBar=barIndex;
     }
   if(kf!=state.kamaFast)
     {
      if(writeJournal)
         PrintFormat("Emtt | KAMA fast period %d -> %d | volatility %s -> %s | percentile %.1f | bar %s",
                     state.kamaFast,kf,EmttVolatilityName(previous),
                     EmttVolatilityName(next),percentile,
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
      state.kamaFast=kf;
      state.lastKamaFastChangeBar=barIndex;
     }
   if(km!=state.kamaMedium)
     {
      if(writeJournal)
         PrintFormat("Emtt | KAMA medium period %d -> %d | volatility %s -> %s | percentile %.1f | bar %s",
                     state.kamaMedium,km,EmttVolatilityName(previous),
                     EmttVolatilityName(next),percentile,
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
      state.kamaMedium=km;
      state.lastKamaMediumChangeBar=barIndex;
     }
   if(ks!=state.kamaSlow)
     {
      if(writeJournal)
         PrintFormat("Emtt | KAMA slow period %d -> %d | volatility %s -> %s | percentile %.1f | bar %s",
                     state.kamaSlow,ks,EmttVolatilityName(previous),
                     EmttVolatilityName(next),percentile,
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
      state.kamaSlow=ks;
      state.lastKamaSlowChangeBar=barIndex;
     }
   state.volatility=next;
   if(writeJournal)
      PrintFormat("Emtt | Volatility bucket %s -> %s | ATR(14) percentile %.1f | bar %s",
                  EmttVolatilityName(previous),EmttVolatilityName(next),percentile,
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   return true;
  }

void EmttDynamicUpdateThreshold(SEmttDynamicState &state,
                                const EEmttRegime regime,const long barIndex,
                                const datetime barTime,const bool writeJournal)
  {
   if(!state.initialized || state.thresholdFrozen)
      return;
   const int desired=EmttConfidenceThreshold(regime);
   if(desired<=0)
      return;
   if(state.confidenceThreshold==0)
     {
      state.confidenceThreshold=desired;
      state.lastThresholdChangeBar=barIndex;
      return;
     }
   if(desired==state.confidenceThreshold ||
      !EmttCanChangeAt(barIndex,state.lastThresholdChangeBar))
      return;
   const int previous=state.confidenceThreshold;
   state.confidenceThreshold=desired;
   state.lastThresholdChangeBar=barIndex;
   if(writeJournal)
      PrintFormat("Emtt | Confidence threshold %d%% -> %d%% | regime %s | bar %s",
                  previous,desired,EmttRegimeContextName(regime),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
  }

// Capture this at the order-entry point in the trade phase. Phase 2's EA
// also calls it when it discovers an already-open Emtt position.
void EmttDynamicFreezeAtEntry(SEmttDynamicState &state)
  {
   if(!state.initialized || state.confidenceThreshold<=0 || state.thresholdFrozen)
      return;
   state.frozenThreshold=state.confidenceThreshold;
   state.thresholdFrozen=true;
   PrintFormat("Emtt | Confidence threshold frozen at %d%% for the open position",
               state.frozenThreshold);
  }

void EmttDynamicThawAfterClose(SEmttDynamicState &state)
  {
   if(!state.thresholdFrozen)
      return;
   PrintFormat("Emtt | Confidence threshold unfrozen after position close");
   state.thresholdFrozen=false;
   state.frozenThreshold=0;
  }

int EmttEffectiveConfidenceThreshold(const SEmttDynamicState &state)
  {
   if(state.thresholdFrozen)
      return state.frozenThreshold;
   return state.confidenceThreshold;
  }

#endif // EMTT_DYNAMIC_PARAMS_MQH
