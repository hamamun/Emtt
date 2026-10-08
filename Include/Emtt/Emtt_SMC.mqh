//+------------------------------------------------------------------+
//|                                                   Emtt_SMC.mqh   |
//| Phase 4: closed-bar market structure context (SMC)               |
//| Spec: Emtt.md sections 13.3-13.14                                |
//+------------------------------------------------------------------+
//| Design seam: this component owns only the state passed to it. It |
//| reads no chart, panel or EA global, so a later MTF context can   |
//| create another SEmttSmcState without changing this header.       |
//+------------------------------------------------------------------+
#ifndef EMTT_SMC_MQH
#define EMTT_SMC_MQH

// EmttLookbackScale(), the shared asset-class enums and EmttCanChangeAt()
// deliberately come from the approved Phase-3 / Phase-2 headers. Layer 2 is
// defined in one place only.
#include "Emtt_Supertrend.mqh"

//--- 13.5-13.10 fixed measurement constants ------------------------
#define EMTT_SMC_DISPLACEMENT_MULTIPLE  1.5
#define EMTT_SMC_IMPULSE_BARS            3
#define EMTT_SMC_EQUAL_TOLERANCE_ATR     0.10
#define EMTT_SMC_ZONE_DEADBAND           0.05
#define EMTT_SMC_MIN_RANGE_ATR           1.0
#define EMTT_SMC_MAX_ZONES                8
#define EMTT_SMC_MAX_SWINGS              64
#define EMTT_SMC_MAX_BLOCK_RECORDS       16
#define EMTT_SMC_MAX_GAP_RECORDS         16

//--- 13.9 score contract --------------------------------------------
#define EMTT_SMC_WEIGHT_STRUCTURE        0.30
#define EMTT_SMC_WEIGHT_FRESHNESS        0.20
#define EMTT_SMC_WEIGHT_ZONE             0.20
#define EMTT_SMC_WEIGHT_PROXIMITY        0.15
#define EMTT_SMC_WEIGHT_SWEEP            0.15
#define EMTT_SMC_EVENT_AGE_BARS          40
#define EMTT_SMC_PROXIMITY_ATRS          2.0
#define EMTT_SMC_SWEEP_AGE_BARS          20
#define EMTT_SMC_CHOCH_TERM              0.6

//--- 13.10 derived parameter guard rails ----------------------------
#define EMTT_SMC_OB_LOOKBACK_DIVISOR     3
#define EMTT_SMC_OB_LOOKBACK_MIN         10
#define EMTT_SMC_WINDOW_MIN              20
#define EMTT_SMC_WINDOW_MAX              400

//--- 13.11 presentation freshness (the values remain measurements) --
#define EMTT_SMC_STATUS_FRESH_BARS       3
#define EMTT_SMC_SWEEP_MENTION_BARS      10

enum EEmttSmcEvent
  {
   EMTT_SMC_EVENT_NONE=0,
   EMTT_SMC_EVENT_BOS,
   EMTT_SMC_EVENT_CHOCH
  };

enum EEmttSmcZone
  {
   EMTT_SMC_ZONE_NONE=0,
   EMTT_SMC_ZONE_DISCOUNT,
   EMTT_SMC_ZONE_PREMIUM,
   EMTT_SMC_ZONE_EQUILIBRIUM
  };

enum EEmttSmcSweepSide
  {
   EMTT_SMC_SWEEP_NONE=0,
   EMTT_SMC_SWEEP_BUY,
   EMTT_SMC_SWEEP_SELL
  };

// A confirmed pivot stays in the bounded list until it leaves the current
// structure window. high=true means a swing high; false means a swing low.
struct SEmttSmcSwing
  {
   bool     active;
   bool     high;
   bool     consumed;
   bool     swept;
   double   level;
   datetime pivotTime;
   long     pivotSequence;
   int      pivotIndex;
  };

// Pools are derived only from the confirmed-swing list, never from a rate
// rescan. A pool can be swept once while it remains a pool.
struct SEmttSmcPool
  {
   bool     active;
   bool     high;
   bool     swept;
   bool     announced;
   double   level;
   int      count;
   datetime newestTime;
   long     newestSequence;
  };

// A mitigated block remains recorded with its mitigation time. An invalidated
// block is no longer active and its origin is retained so it cannot reappear.
struct SEmttSmcOrderBlock
  {
   bool     recorded;
   bool     active;
   bool     bullish;
   bool     mitigated;
   bool     invalidated;
   double   zoneLow;
   double   zoneHigh;
   double   displacementRatio;
   datetime originTime;
   long     originSequence;
   long     createdSequence;
   datetime mitigationTime;
  };

// Filled gaps retain their origin while active gaps are bounded separately.
struct SEmttSmcGap
  {
   bool     recorded;
   bool     active;
   bool     bullish;
   bool     mitigated;
   bool     filled;
   double   zoneLow;
   double   zoneHigh;
   datetime originTime;
   long     originSequence;
   long     createdSequence;
   datetime mitigationTime;
  };

//+------------------------------------------------------------------+
//| Published contract: readings, their closed-bar facts and the     |
//| bounded lifecycle lists needed by subsequent bars.               |
//+------------------------------------------------------------------+
struct SEmttSmcState
  {
   bool                 parametersInitialized;
   bool                 initialized;
   bool                 ready;
   EEmttAssetClass      assetClass;
   EEmttVolatility      volatility;
   EEmttVolatility      appliedVolatility;
   int                  atrPeriod;
   double               atrValue;
   int                  structureWindow;
   int                  swingStrength;
   int                  bodyPeriod;
   int                  obLookback;
   long                 lastWindowChangeBar;
   long                 lastStrengthChangeBar;
   long                 lastBodyPeriodChangeBar;
   long                 lastObLookbackChangeBar;

   SEmttSmcSwing        swings[EMTT_SMC_MAX_SWINGS];
   int                  swingCount;          // bounded internal list count
   int                  confirmedSwingCount; // published count inside window
   int                  confirmedHighCount;
   int                  confirmedLowCount;
   int                  newestHighSlot;
   int                  newestLowSlot;
   double               newestHighLevel;
   double               newestLowLevel;
   datetime             newestHighTime;
   datetime             newestLowTime;
   int                  newestHighPivotIndex;
   int                  newestLowPivotIndex;

   SEmttSmcPool         pools[EMTT_SMC_MAX_SWINGS];
   int                  poolRecordCount; // bounded internal pool list
   EEmttSmcSweepSide    poolSide;        // side of the largest published pool
   int                  poolCount;       // member count of that published pool
   bool                 hasBuyPool;
   bool                 hasSellPool;
   double               buyPoolLevel;
   double               sellPoolLevel;
   int                  buyPoolCount;
   int                  sellPoolCount;

   SEmttSmcOrderBlock   blocks[EMTT_SMC_MAX_BLOCK_RECORDS];
   int                  mitigatedBlockCount;
   bool                 hasOrderBlock;
   bool                 orderBlockBullish;
   double               orderBlockLow;
   double               orderBlockHigh;
   double               orderBlockNearEdge;
   double               distanceToOBATRs;

   SEmttSmcGap          gaps[EMTT_SMC_MAX_GAP_RECORDS];
   int                  activeGapCount;
   bool                 hasGapAbove;
   bool                 hasGapBelow;
   bool                 gapAboveBullish;
   bool                 gapBelowBullish;
   double               gapAboveLow;
   double               gapAboveHigh;
   double               gapBelowLow;
   double               gapBelowHigh;
   double               gapAboveNearEdge;
   double               gapBelowNearEdge;
   double               gapAboveDistanceATRs;
   double               gapBelowDistanceATRs;
   double               gapDistanceATRs;

   int                  bias;
   EEmttSmcEvent        eventKind;       // newest event, used by score/Row 9
   int                  eventDirection;
   datetime             eventTime;
   long                 eventSequence;
   datetime             lastBosTime;     // Row-10 freshness precedence facts
   long                 lastBosSequence;
   int                  lastBosDirection;
   datetime             lastChochTime;
   long                 lastChochSequence;
   int                  lastChochDirection;
   long                 currentSequence;
   int                  barsSinceEvent;
   EEmttSmcSweepSide    lastSweepSide;
   double               lastSweepLevel;
   datetime             lastSweepTime;
   long                 lastSweepSequence;
   int                  barsSinceSweep;

   EEmttSmcZone         zone;
   int                  legDirection;
   double               dealingRangeLow;
   double               dealingRangeHigh;
   double               equilibrium;
   double               zonePosition;
   double               smcScore;
  };

//+------------------------------------------------------------------+
//| Small local helpers. No EA helper is called from this component. |
//+------------------------------------------------------------------+
bool EmttSmcValid(const double value)
  {
   return(MathIsValidNumber(value) && value!=EMPTY_VALUE);
  }

bool EmttSmcValidPositive(const double value)
  {
   return(EmttSmcValid(value) && value>0.0);
  }

double EmttSmcClamp01(const double value)
  {
   if(!MathIsValidNumber(value))
      return 0.0;
   return MathMax(0.0,MathMin(1.0,value));
  }

int EmttSmcAge(const long currentSequence,const long occurredSequence)
  {
   if(occurredSequence<0 || currentSequence<occurredSequence)
      return 1000000;
   const long age=currentSequence-occurredSequence;
   if(age>2147483647)
      return 2147483647;
   return (int)age;
  }

string EmttSmcTimeframeName(const ENUM_TIMEFRAMES timeframe)
  {
   if(timeframe==PERIOD_M5)  return "M5";
   if(timeframe==PERIOD_M15) return "M15";
   if(timeframe==PERIOD_M30) return "M30";
   const string name=EnumToString(timeframe);
   if(StringFind(name,"PERIOD_")==0)
      return StringSubstr(name,7);
   return name;
  }

int EmttSmcDigits(const string symbol)
  {
   const int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   return(digits>=0 ? digits : 5);
  }

string EmttSmcPriceText(const string symbol,const double price)
  {
   return DoubleToString(price,EmttSmcDigits(symbol));
  }

string EmttSmcBiasName(const int bias)
  {
   if(bias>0) return "up";
   if(bias<0) return "down";
   return "none";
  }

string EmttSmcEventName(const EEmttSmcEvent eventKind)
  {
   if(eventKind==EMTT_SMC_EVENT_BOS) return "BOS";
   if(eventKind==EMTT_SMC_EVENT_CHOCH) return "CHoCH";
   return "";
  }

string EmttSmcZoneName(const EEmttSmcZone zone)
  {
   switch(zone)
     {
      case EMTT_SMC_ZONE_DISCOUNT:    return "Discount";
      case EMTT_SMC_ZONE_PREMIUM:     return "Premium";
      case EMTT_SMC_ZONE_EQUILIBRIUM: return "Equilibrium";
      default:                        return "";
     }
  }

//+------------------------------------------------------------------+
//| 13.10 parameter matrix and the one Layer-2 scaling path.        |
//+------------------------------------------------------------------+
void EmttSmcMatrixValues(const EEmttAssetClass assetClass,
                         const EEmttVolatility volatility,
                         int &structureWindow,int &swingStrength,
                         int &bodyPeriod)
  {
   const bool low=(volatility==EMTT_VOL_LOW);
   const bool high=(volatility==EMTT_VOL_HIGH);
   bodyPeriod=(high ? 21 : 14);

   switch(assetClass)
     {
      case EMTT_CLASS_METALS:
         structureWindow=(low ? 50 : (high ? 80 : 60));
         swingStrength=(low ? 2 : 3);
         break;

      case EMTT_CLASS_CRYPTO:
         structureWindow=(low ? 40 : (high ? 70 : 50));
         swingStrength=(low ? 2 : (high ? 4 : 3));
         break;

      case EMTT_CLASS_INDICES:
         structureWindow=(low ? 50 : (high ? 80 : 60));
         swingStrength=(high ? 3 : 2);
         break;

      case EMTT_CLASS_FOREX_MAJOR:
      case EMTT_CLASS_FOREX_CROSS:
      case EMTT_CLASS_GENERIC:
      default:
         structureWindow=(high ? 80 : 60);
         swingStrength=(high ? 3 : 2);
         break;
     }
  }

int EmttSmcMatrixField(const EEmttAssetClass assetClass,
                       const EEmttVolatility volatility,const int field)
  {
   int window,strength,body;
   EmttSmcMatrixValues(assetClass,volatility,window,strength,body);
   if(field==0) return window;
   if(field==1) return strength;
   return body;
  }

int EmttSmcScaledWindow(const EEmttAssetClass assetClass,
                         const EEmttVolatility volatility,
                         const ENUM_TIMEFRAMES timeframe)
  {
   const int base=EmttSmcMatrixField(assetClass,volatility,0);
   int window=(int)MathRound((double)base*EmttLookbackScale(timeframe));
   if(window<EMTT_SMC_WINDOW_MIN) window=EMTT_SMC_WINDOW_MIN;
   if(window>EMTT_SMC_WINDOW_MAX) window=EMTT_SMC_WINDOW_MAX;
   return window;
  }

int EmttSmcClampWindow(const EEmttAssetClass assetClass,
                       const EEmttVolatility volatility,
                       const ENUM_TIMEFRAMES timeframe)
  {
   int minimum=EMTT_SMC_WINDOW_MAX;
   int maximum=EMTT_SMC_WINDOW_MIN;
   for(int column=EMTT_VOL_LOW;column<=EMTT_VOL_HIGH;column++)
     {
      const int value=EmttSmcScaledWindow(assetClass,
                                          (EEmttVolatility)column,timeframe);
      minimum=(int)MathMin(minimum,value);
      maximum=(int)MathMax(maximum,value);
     }
   const int selected=EmttSmcScaledWindow(assetClass,volatility,timeframe);
   return (int)MathMax(minimum,MathMin(maximum,selected));
  }

int EmttSmcClampPeriod(const EEmttAssetClass assetClass,
                       const EEmttVolatility volatility,const int field)
  {
   int minimum=2147483647;
   int maximum=0;
   for(int column=EMTT_VOL_LOW;column<=EMTT_VOL_HIGH;column++)
     {
      const int value=EmttSmcMatrixField(assetClass,
                                         (EEmttVolatility)column,field);
      minimum=(int)MathMin(minimum,value);
      maximum=(int)MathMax(maximum,value);
     }
   const int selected=EmttSmcMatrixField(assetClass,volatility,field);
   return (int)MathMax(minimum,MathMin(maximum,selected));
  }

void EmttSmcResolveParameters(const EEmttAssetClass assetClass,
                              const EEmttVolatility volatility,
                              const ENUM_TIMEFRAMES timeframe,
                              int &structureWindow,int &swingStrength,
                              int &bodyPeriod,int &obLookback)
  {
   structureWindow=EmttSmcClampWindow(assetClass,volatility,timeframe);
   swingStrength=EmttSmcClampPeriod(assetClass,volatility,1);
   bodyPeriod=EmttSmcClampPeriod(assetClass,volatility,2);
   obLookback=(int)MathRound((double)structureWindow/
                             (double)EMTT_SMC_OB_LOOKBACK_DIVISOR);
   if(obLookback<EMTT_SMC_OB_LOOKBACK_MIN)
      obLookback=EMTT_SMC_OB_LOOKBACK_MIN;
  }

// This overload is used when a concrete class and live bucket are known.
int EmttSmcHistoryRequired(const EEmttAssetClass assetClass,
                           const EEmttVolatility volatility,
                           const ENUM_TIMEFRAMES timeframe)
  {
   int window,strength,body,lookback;
   EmttSmcResolveParameters(assetClass,volatility,timeframe,window,strength,
                            body,lookback);
   return window+strength+body+2;
  }

// Before the first bucket exists, the EA uses this maximum across the same
// matrix. It remains one code path and is currently below the ST gate.
int EmttSmcHistoryRequired(const ENUM_TIMEFRAMES timeframe)
  {
   int required=0;
   for(int asset=EMTT_CLASS_FOREX_MAJOR;asset<=EMTT_CLASS_GENERIC;asset++)
      for(int bucket=EMTT_VOL_LOW;bucket<=EMTT_VOL_HIGH;bucket++)
         required=(int)MathMax(required,
             EmttSmcHistoryRequired((EEmttAssetClass)asset,
                                    (EEmttVolatility)bucket,timeframe));
   return required;
  }

//+------------------------------------------------------------------+
//| State lifecycle. Parameter data and measurement data reset on    |
//| different paths so a permitted parameter change can replay facts |
//| silently with its newly resolved values.                          |
//+------------------------------------------------------------------+
void EmttSmcClearMeasurement(SEmttSmcState &state)
  {
   state.initialized=false;
   state.ready=false;
   state.atrValue=0.0;
   state.swingCount=0;
   state.confirmedSwingCount=0;
   state.confirmedHighCount=0;
   state.confirmedLowCount=0;
   state.newestHighSlot=-1;
   state.newestLowSlot=-1;
   state.newestHighLevel=0.0;
   state.newestLowLevel=0.0;
   state.newestHighTime=0;
   state.newestLowTime=0;
   state.newestHighPivotIndex=-1;
   state.newestLowPivotIndex=-1;

   state.poolRecordCount=0;
   state.poolSide=EMTT_SMC_SWEEP_NONE;
   state.poolCount=0;
   state.hasBuyPool=false;
   state.hasSellPool=false;
   state.buyPoolLevel=0.0;
   state.sellPoolLevel=0.0;
   state.buyPoolCount=0;
   state.sellPoolCount=0;

   state.mitigatedBlockCount=0;
   state.hasOrderBlock=false;
   state.orderBlockBullish=false;
   state.orderBlockLow=0.0;
   state.orderBlockHigh=0.0;
   state.orderBlockNearEdge=0.0;
   state.distanceToOBATRs=0.0;

   state.activeGapCount=0;
   state.hasGapAbove=false;
   state.hasGapBelow=false;
   state.gapAboveBullish=false;
   state.gapBelowBullish=false;
   state.gapAboveLow=0.0;
   state.gapAboveHigh=0.0;
   state.gapBelowLow=0.0;
   state.gapBelowHigh=0.0;
   state.gapAboveNearEdge=0.0;
   state.gapBelowNearEdge=0.0;
   state.gapAboveDistanceATRs=0.0;
   state.gapBelowDistanceATRs=0.0;
   state.gapDistanceATRs=0.0;

   state.bias=0;
   state.eventKind=EMTT_SMC_EVENT_NONE;
   state.eventDirection=0;
   state.eventTime=0;
   state.eventSequence=-1000000;
   state.lastBosTime=0;
   state.lastBosSequence=-1000000;
   state.lastBosDirection=0;
   state.lastChochTime=0;
   state.lastChochSequence=-1000000;
   state.lastChochDirection=0;
   state.currentSequence=-1000000;
   state.barsSinceEvent=1000000;
   state.lastSweepSide=EMTT_SMC_SWEEP_NONE;
   state.lastSweepLevel=0.0;
   state.lastSweepTime=0;
   state.lastSweepSequence=-1000000;
   state.barsSinceSweep=1000000;

   state.zone=EMTT_SMC_ZONE_NONE;
   state.legDirection=0;
   state.dealingRangeLow=0.0;
   state.dealingRangeHigh=0.0;
   state.equilibrium=0.0;
   state.zonePosition=0.0;
   state.smcScore=0.0;

   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
     {
      state.swings[i].active=false;
      state.swings[i].high=false;
      state.swings[i].consumed=false;
      state.swings[i].swept=false;
      state.swings[i].level=0.0;
      state.swings[i].pivotTime=0;
      state.swings[i].pivotSequence=-1000000;
      state.swings[i].pivotIndex=-1;

      state.pools[i].active=false;
      state.pools[i].high=false;
      state.pools[i].swept=false;
      state.pools[i].announced=false;
      state.pools[i].level=0.0;
      state.pools[i].count=0;
      state.pools[i].newestTime=0;
      state.pools[i].newestSequence=-1000000;
     }
   for(int i=0;i<EMTT_SMC_MAX_BLOCK_RECORDS;i++)
     {
      state.blocks[i].recorded=false;
      state.blocks[i].active=false;
      state.blocks[i].bullish=false;
      state.blocks[i].mitigated=false;
      state.blocks[i].invalidated=false;
      state.blocks[i].zoneLow=0.0;
      state.blocks[i].zoneHigh=0.0;
      state.blocks[i].displacementRatio=0.0;
      state.blocks[i].originTime=0;
      state.blocks[i].originSequence=-1000000;
      state.blocks[i].createdSequence=-1000000;
      state.blocks[i].mitigationTime=0;
     }
   for(int i=0;i<EMTT_SMC_MAX_GAP_RECORDS;i++)
     {
      state.gaps[i].recorded=false;
      state.gaps[i].active=false;
      state.gaps[i].bullish=false;
      state.gaps[i].mitigated=false;
      state.gaps[i].filled=false;
      state.gaps[i].zoneLow=0.0;
      state.gaps[i].zoneHigh=0.0;
      state.gaps[i].originTime=0;
      state.gaps[i].originSequence=-1000000;
      state.gaps[i].createdSequence=-1000000;
      state.gaps[i].mitigationTime=0;
     }
  }

void EmttSmcReset(SEmttSmcState &state)
  {
   state.parametersInitialized=false;
   state.assetClass=EMTT_CLASS_GENERIC;
   state.volatility=EMTT_VOL_UNKNOWN;
   state.appliedVolatility=EMTT_VOL_UNKNOWN;
   state.atrPeriod=0;
   state.structureWindow=0;
   state.swingStrength=0;
   state.bodyPeriod=0;
   state.obLookback=0;
   state.lastWindowChangeBar=-1000000;
   state.lastStrengthChangeBar=-1000000;
   state.lastBodyPeriodChangeBar=-1000000;
   state.lastObLookbackChangeBar=-1000000;
   EmttSmcClearMeasurement(state);
  }

bool EmttSmcApplyParameters(SEmttSmcState &state,
                            const EEmttAssetClass assetClass,
                            const EEmttVolatility volatility,
                            const ENUM_TIMEFRAMES timeframe,
                            const long barSequence,const datetime barTime,
                            const bool writeJournal,bool &changed)
  {
   changed=false;
   int window,strength,body,lookback;
   EmttSmcResolveParameters(assetClass,volatility,timeframe,window,strength,
                            body,lookback);

   if(!state.parametersInitialized)
     {
      state.parametersInitialized=true;
      state.assetClass=assetClass;
      state.volatility=volatility;
      state.appliedVolatility=volatility;
      state.structureWindow=window;
      state.swingStrength=strength;
      state.bodyPeriod=body;
      state.obLookback=lookback;
      // Initialization is not a change; the first real bucket change is not
      // artificially delayed by the pause.
      state.lastWindowChangeBar=barSequence-1000000;
      state.lastStrengthChangeBar=barSequence-1000000;
      state.lastBodyPeriodChangeBar=barSequence-1000000;
      state.lastObLookbackChangeBar=barSequence-1000000;
      return true;
     }

   state.volatility=volatility;
   const bool windowWanted=(window!=state.structureWindow);
   const bool strengthWanted=(strength!=state.swingStrength);
   const bool bodyWanted=(body!=state.bodyPeriod);
   const bool lookbackWanted=(lookback!=state.obLookback);
   if(!windowWanted && !strengthWanted && !bodyWanted && !lookbackWanted)
     {
      state.assetClass=assetClass;
      state.appliedVolatility=volatility;
      return true;
     }

   // Apply the four values atomically, just as Phase 2 does for its matrix,
   // so no published reading combines columns from two volatility buckets.
   if((windowWanted && !EmttCanChangeAt(barSequence,state.lastWindowChangeBar)) ||
      (strengthWanted && !EmttCanChangeAt(barSequence,state.lastStrengthChangeBar)) ||
      (bodyWanted && !EmttCanChangeAt(barSequence,state.lastBodyPeriodChangeBar)) ||
      (lookbackWanted && !EmttCanChangeAt(barSequence,state.lastObLookbackChangeBar)))
      return true;

   const EEmttVolatility previousVolatility=state.appliedVolatility;
   if(writeJournal && windowWanted)
      PrintFormat("Emtt | Structure window %d -> %d closed bars | volatility %s -> %s | bar %s",
                  state.structureWindow,window,EmttVolatilityName(previousVolatility),
                  EmttVolatilityName(volatility),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   if(writeJournal && strengthWanted)
      PrintFormat("Emtt | Swing strength %d -> %d | volatility %s -> %s | bar %s",
                  state.swingStrength,strength,EmttVolatilityName(previousVolatility),
                  EmttVolatilityName(volatility),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   if(writeJournal && bodyWanted)
      PrintFormat("Emtt | Displacement body period %d -> %d | volatility %s -> %s | bar %s",
                  state.bodyPeriod,body,EmttVolatilityName(previousVolatility),
                  EmttVolatilityName(volatility),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));

   state.assetClass=assetClass;
   state.appliedVolatility=volatility;
   state.structureWindow=window;
   state.swingStrength=strength;
   state.bodyPeriod=body;
   state.obLookback=lookback;
   if(windowWanted) state.lastWindowChangeBar=barSequence;
   if(strengthWanted) state.lastStrengthChangeBar=barSequence;
   if(bodyWanted) state.lastBodyPeriodChangeBar=barSequence;
   if(lookbackWanted) state.lastObLookbackChangeBar=barSequence;
   changed=true;
   return true;
  }

//+------------------------------------------------------------------+
//| Bounded confirmed-swing lifecycle                                |
//+------------------------------------------------------------------+
bool EmttSmcSwingInsideWindow(const SEmttSmcSwing &swing,
                              const long barSequence,const int window)
  {
   if(!swing.active || window<=0 || barSequence<swing.pivotSequence)
      return false;
   return(barSequence-swing.pivotSequence<(long)window);
  }

void EmttSmcExpireSwings(SEmttSmcState &state,const long barSequence)
  {
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
      if(state.swings[i].active &&
         !EmttSmcSwingInsideWindow(state.swings[i],barSequence,
                                   state.structureWindow))
         state.swings[i].active=false;
  }

void EmttSmcRefreshSwingFacts(SEmttSmcState &state,const long barSequence)
  {
   state.swingCount=0;
   state.confirmedSwingCount=0;
   state.confirmedHighCount=0;
   state.confirmedLowCount=0;
   state.newestHighSlot=-1;
   state.newestLowSlot=-1;

   int newestAnyHigh=-1;
   int newestAnyLow=-1;
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
     {
      if(!EmttSmcSwingInsideWindow(state.swings[i],barSequence,
                                   state.structureWindow))
         continue;
      state.swingCount++;
      if(state.swings[i].high)
        {
         state.confirmedHighCount++;
         if(newestAnyHigh<0 || state.swings[i].pivotSequence>
            state.swings[newestAnyHigh].pivotSequence)
            newestAnyHigh=i;
         if(!state.swings[i].consumed &&
            (state.newestHighSlot<0 || state.swings[i].pivotSequence>
             state.swings[state.newestHighSlot].pivotSequence))
            state.newestHighSlot=i;
        }
      else
        {
         state.confirmedLowCount++;
         if(newestAnyLow<0 || state.swings[i].pivotSequence>
            state.swings[newestAnyLow].pivotSequence)
            newestAnyLow=i;
         if(!state.swings[i].consumed &&
            (state.newestLowSlot<0 || state.swings[i].pivotSequence>
             state.swings[state.newestLowSlot].pivotSequence))
            state.newestLowSlot=i;
        }
     }

   state.confirmedSwingCount=state.swingCount;

   // The published newest pair is the still-trackable pair. A consumed level
   // cannot trigger a second event or a second sweep.
   if(state.newestHighSlot>=0)
     {
      const SEmttSmcSwing &swing=state.swings[state.newestHighSlot];
      state.newestHighLevel=swing.level;
      state.newestHighTime=swing.pivotTime;
      state.newestHighPivotIndex=EmttSmcAge(barSequence,swing.pivotSequence);
     }
   else
     {
      state.newestHighLevel=0.0;
      state.newestHighTime=0;
      state.newestHighPivotIndex=-1;
     }
   if(state.newestLowSlot>=0)
     {
      const SEmttSmcSwing &swing=state.swings[state.newestLowSlot];
      state.newestLowLevel=swing.level;
      state.newestLowTime=swing.pivotTime;
      state.newestLowPivotIndex=EmttSmcAge(barSequence,swing.pivotSequence);
     }
   else
     {
      state.newestLowLevel=0.0;
      state.newestLowTime=0;
      state.newestLowPivotIndex=-1;
     }
  }

bool EmttSmcHasSwing(const SEmttSmcState &state,const bool high,
                     const datetime pivotTime)
  {
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
      if(state.swings[i].active && state.swings[i].high==high &&
         state.swings[i].pivotTime==pivotTime)
         return true;
   return false;
  }

void EmttSmcAddSwing(SEmttSmcState &state,const bool high,const double level,
                     const datetime pivotTime,const long pivotSequence,
                     const int pivotIndex)
  {
   if(EmttSmcHasSwing(state,high,pivotTime))
      return;
   int slot=-1;
   long oldest=2147483647;
   int oldestSlot=0;
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
     {
      if(!state.swings[i].active)
        {
         slot=i;
         break;
        }
      if(state.swings[i].pivotSequence<oldest)
        {
         oldest=state.swings[i].pivotSequence;
         oldestSlot=i;
        }
     }
   if(slot<0) slot=oldestSlot; // bounded list: oldest swing leaves first
   state.swings[slot].active=true;
   state.swings[slot].high=high;
   state.swings[slot].consumed=false;
   state.swings[slot].swept=false;
   state.swings[slot].level=level;
   state.swings[slot].pivotTime=pivotTime;
   state.swings[slot].pivotSequence=pivotSequence;
   state.swings[slot].pivotIndex=pivotIndex;
  }

// Tests a candidate whose newest plateau member is exactly swingStrength bars
// older than the current bar. Equal extremes are collapsed to their oldest
// member, and the strict comparisons start outside the plateau on both sides.
bool EmttSmcPivotAt(const MqlRates &rates[],const int index,
                    const int strength,const bool high,
                    int &oldestPivot,double &level)
  {
   oldestPivot=-1;
   level=0.0;
   if(index<0 || strength<=0 || index+strength>=ArraySize(rates))
      return false;

   const int newest=index+strength;
   level=(high ? rates[newest].high : rates[newest].low);
   if(!EmttSmcValid(level))
      return false;

   // If an equal bar is newer, this is not the newest plateau member and its
   // one allowed recognition happened (or will happen) from that newer bar.
   if(newest>index)
     {
      const double newer=(high ? rates[newest-1].high : rates[newest-1].low);
      if(newer==level)
         return false;
     }

   int oldest=newest;
   while(oldest+1<ArraySize(rates))
     {
      const double older=(high ? rates[oldest+1].high : rates[oldest+1].low);
      if(older!=level)
         break;
      oldest++;
     }
   if(oldest+strength>=ArraySize(rates))
      return false;

   for(int offset=1;offset<=strength;offset++)
     {
      const double older=(high ? rates[oldest+offset].high :
                            rates[oldest+offset].low);
      const double newer=(high ? rates[newest-offset].high :
                            rates[newest-offset].low);
      if(!EmttSmcValid(older) || !EmttSmcValid(newer))
         return false;
      if(high && (level<=older || level<=newer)) return false;
      if(!high && (level>=older || level>=newer)) return false;
     }
   oldestPivot=oldest;
   return true;
  }

void EmttSmcRecognizePivot(SEmttSmcState &state,const MqlRates &rates[],
                           const int index,const long barSequence)
  {
   int highPivot,lowPivot;
   double highLevel,lowLevel;
   const bool isHigh=EmttSmcPivotAt(rates,index,state.swingStrength,true,
                                    highPivot,highLevel);
   const bool isLow=EmttSmcPivotAt(rates,index,state.swingStrength,false,
                                   lowPivot,lowLevel);
   // An inside bar may satisfy both mechanical tests. Rule 13.3 publishes
   // neither rather than inventing a tie-break.
   if(isHigh && isLow)
      return;
   if(isHigh)
     {
      const int age=highPivot-index;
      EmttSmcAddSwing(state,true,highLevel,rates[highPivot].time,
                      barSequence-age,age);
     }
   else if(isLow)
     {
      const int age=lowPivot-index;
      EmttSmcAddSwing(state,false,lowLevel,rates[lowPivot].time,
                      barSequence-age,age);
     }
  }

//+------------------------------------------------------------------+
//| Liquidity pools and sweeps                                       |
//+------------------------------------------------------------------+
bool EmttSmcPoolWasKnown(const SEmttSmcState &state,const bool high,
                         const double level,const double tolerance,
                         bool &swept,bool &announced)
  {
   swept=false;
   announced=false;
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
      if(state.pools[i].active && state.pools[i].high==high &&
         MathAbs(state.pools[i].level-level)<=tolerance)
        {
         swept=state.pools[i].swept;
         announced=state.pools[i].announced;
         return true;
        }
   return false;
  }

void EmttSmcRebuildPools(SEmttSmcState &state,const long barSequence,
                         const string symbol,const datetime barTime,
                         const bool writeJournal)
  {
   SEmttSmcPool previous[EMTT_SMC_MAX_SWINGS];
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
      previous[i]=state.pools[i];
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
      state.pools[i].active=false;
   state.poolRecordCount=0;
   state.poolSide=EMTT_SMC_SWEEP_NONE;
   state.poolCount=0;
   state.hasBuyPool=false;
   state.hasSellPool=false;
   state.buyPoolLevel=0.0;
   state.sellPoolLevel=0.0;
   state.buyPoolCount=0;
   state.sellPoolCount=0;

   const double tolerance=EMTT_SMC_EQUAL_TOLERANCE_ATR*state.atrValue;
   if(!EmttSmcValidPositive(tolerance))
      return;

   for(int type=0;type<2;type++)
     {
      const bool high=(type==1);
      int slots[];
      int count=0;
      for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
         if(EmttSmcSwingInsideWindow(state.swings[i],barSequence,
                                    state.structureWindow) &&
            state.swings[i].high==high)
           {
            ArrayResize(slots,count+1);
            slots[count]=i;
            count++;
           }
      // Insertion-sort by level. Grouping a sorted list makes every member of
      // a pool sit within tolerance of the group's lowest level.
      for(int i=1;i<count;i++)
        {
         const int key=slots[i];
         int j=i-1;
         while(j>=0 && state.swings[slots[j]].level>state.swings[key].level)
           {
            slots[j+1]=slots[j];
            j--;
           }
         slots[j+1]=key;
        }

      int start=0;
      while(start<count)
        {
         int end=start;
         const double minimum=state.swings[slots[start]].level;
         while(end+1<count &&
               state.swings[slots[end+1]].level-minimum<=tolerance)
            end++;
         const int members=end-start+1;
         if(members>=2 && state.poolRecordCount<EMTT_SMC_MAX_SWINGS)
           {
            double sum=0.0;
            long newestSequence=-1000000;
            datetime newestTime=0;
            for(int p=start;p<=end;p++)
              {
               const SEmttSmcSwing &swing=state.swings[slots[p]];
               sum+=swing.level;
               if(swing.pivotSequence>newestSequence)
                 {
                  newestSequence=swing.pivotSequence;
                  newestTime=swing.pivotTime;
                 }
              }
            const double level=sum/(double)members;
            bool swept=false,announced=false;
            // Search the saved pools, not the new array being assembled.
            for(int old=0;old<EMTT_SMC_MAX_SWINGS;old++)
               if(previous[old].active && previous[old].high==high &&
                  MathAbs(previous[old].level-level)<=tolerance)
                 {
                  swept=previous[old].swept;
                  announced=previous[old].announced;
                  break;
                 }
            const int slot=state.poolRecordCount;
            state.pools[slot].active=true;
            state.pools[slot].high=high;
            state.pools[slot].swept=swept;
            state.pools[slot].announced=true;
            state.pools[slot].level=level;
            state.pools[slot].count=members;
            state.pools[slot].newestTime=newestTime;
            state.pools[slot].newestSequence=newestSequence;
            state.poolRecordCount++;
            if(writeJournal && !announced)
               PrintFormat("Emtt | Equal %s pooled at %s | %d confirmed swings within %.2f x ATR | %s-side | bar %s",
                           (high ? "highs" : "lows"),EmttSmcPriceText(symbol,level),
                           members,EMTT_SMC_EQUAL_TOLERANCE_ATR,
                           (high ? "buy" : "sell"),
                           TimeToString(barTime,TIME_DATE|TIME_MINUTES));
           }
         start=end+1;
        }
     }

   // Publish the largest pool on each side. A count tie resolves to the newer
   // pool, giving the current structure the more useful fact without age bias.
   long newestBuy=-1000000;
   long newestSell=-1000000;
   for(int i=0;i<state.poolRecordCount;i++)
     {
      const SEmttSmcPool &pool=state.pools[i];
      if(pool.high)
        {
         if(!state.hasBuyPool || pool.count>state.buyPoolCount ||
            (pool.count==state.buyPoolCount && pool.newestSequence>newestBuy))
           {
            state.hasBuyPool=true;
            state.buyPoolLevel=pool.level;
            state.buyPoolCount=pool.count;
            newestBuy=pool.newestSequence;
           }
        }
      else
        {
         if(!state.hasSellPool || pool.count>state.sellPoolCount ||
            (pool.count==state.sellPoolCount && pool.newestSequence>newestSell))
           {
            state.hasSellPool=true;
            state.sellPoolLevel=pool.level;
            state.sellPoolCount=pool.count;
            newestSell=pool.newestSequence;
           }
        }
     }
   if(state.hasBuyPool && (!state.hasSellPool ||
      state.buyPoolCount>state.sellPoolCount ||
      (state.buyPoolCount==state.sellPoolCount && newestBuy>=newestSell)))
     {
      state.poolSide=EMTT_SMC_SWEEP_BUY;
      state.poolCount=state.buyPoolCount;
     }
   else if(state.hasSellPool)
     {
      state.poolSide=EMTT_SMC_SWEEP_SELL;
      state.poolCount=state.sellPoolCount;
     }
  }

void EmttSmcSetSweep(SEmttSmcState &state,const EEmttSmcSweepSide side,
                     const double level,const MqlRates &bar,
                     const long barSequence,const string symbol,
                     const bool writeJournal)
  {
   state.lastSweepSide=side;
   state.lastSweepLevel=level;
   state.lastSweepTime=bar.time;
   state.lastSweepSequence=barSequence;
   state.barsSinceSweep=0;
   if(writeJournal)
      PrintFormat("Emtt | Liquidity swept %s %s | %s-side | wick %s, close held %s | bar %s",
                  (side==EMTT_SMC_SWEEP_BUY ? "above" : "below"),
                  EmttSmcPriceText(symbol,level),
                  (side==EMTT_SMC_SWEEP_BUY ? "buy" : "sell"),
                  EmttSmcPriceText(symbol,(side==EMTT_SMC_SWEEP_BUY ? bar.high : bar.low)),
                  EmttSmcPriceText(symbol,bar.close),
                  TimeToString(bar.time,TIME_DATE|TIME_MINUTES));
  }

bool EmttSmcCheckSweeps(SEmttSmcState &state,const MqlRates &bar,
                        const long barSequence,const string symbol,
                        const bool writeJournal)
  {
   // A deterministic high, low, pool order also guarantees a single newest
   // sweep fact when one extraordinary candle touches several levels.
   if(state.newestHighSlot>=0)
     {
      SEmttSmcSwing &swing=state.swings[state.newestHighSlot];
      if(!swing.swept && bar.high>swing.level && bar.close<=swing.level)
        {
         swing.swept=true;
         EmttSmcSetSweep(state,EMTT_SMC_SWEEP_BUY,swing.level,bar,
                         barSequence,symbol,writeJournal);
         return true;
        }
     }
   if(state.newestLowSlot>=0)
     {
      SEmttSmcSwing &swing=state.swings[state.newestLowSlot];
      if(!swing.swept && bar.low<swing.level && bar.close>=swing.level)
        {
         swing.swept=true;
         EmttSmcSetSweep(state,EMTT_SMC_SWEEP_SELL,swing.level,bar,
                         barSequence,symbol,writeJournal);
         return true;
        }
     }
   for(int i=0;i<state.poolRecordCount;i++)
     {
      SEmttSmcPool &pool=state.pools[i];
      if(pool.swept) continue;
      if(pool.high && bar.high>pool.level && bar.close<=pool.level)
        {
         pool.swept=true;
         EmttSmcSetSweep(state,EMTT_SMC_SWEEP_BUY,pool.level,bar,
                         barSequence,symbol,writeJournal);
         return true;
        }
      if(!pool.high && bar.low<pool.level && bar.close>=pool.level)
        {
         pool.swept=true;
         EmttSmcSetSweep(state,EMTT_SMC_SWEEP_SELL,pool.level,bar,
                         barSequence,symbol,writeJournal);
         return true;
        }
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Order-block lifecycle                                            |
//+------------------------------------------------------------------+
bool EmttSmcBlockKnown(const SEmttSmcState &state,const bool bullish,
                       const datetime originTime)
  {
   for(int i=0;i<EMTT_SMC_MAX_BLOCK_RECORDS;i++)
      if(state.blocks[i].recorded && state.blocks[i].bullish==bullish &&
         state.blocks[i].originTime==originTime)
         return true;
   return false;
  }

int EmttSmcBlockSlot(SEmttSmcState &state,const bool bullish)
  {
   int active=0;
   int oldestActive=-1;
   long oldestActiveSequence=2147483647;
   for(int i=0;i<EMTT_SMC_MAX_BLOCK_RECORDS;i++)
      if(state.blocks[i].recorded && state.blocks[i].active &&
         state.blocks[i].bullish==bullish)
        {
         active++;
         if(state.blocks[i].originSequence<oldestActiveSequence)
           {
            oldestActiveSequence=state.blocks[i].originSequence;
            oldestActive=i;
           }
        }
   if(active>=EMTT_SMC_MAX_ZONES && oldestActive>=0)
      state.blocks[oldestActive].recorded=false; // capacity drops are silent

   int slot=-1;
   int oldestInactive=-1;
   long oldestInactiveSequence=2147483647;
   for(int i=0;i<EMTT_SMC_MAX_BLOCK_RECORDS;i++)
     {
      if(!state.blocks[i].recorded)
         return i;
      if(!state.blocks[i].active &&
         state.blocks[i].originSequence<oldestInactiveSequence)
        {
         oldestInactiveSequence=state.blocks[i].originSequence;
         oldestInactive=i;
        }
     }
   if(oldestInactive>=0) return oldestInactive;

   long oldest=2147483647;
   for(int i=0;i<EMTT_SMC_MAX_BLOCK_RECORDS;i++)
      if(state.blocks[i].originSequence<oldest)
        {
         oldest=state.blocks[i].originSequence;
         slot=i;
        }
   return(slot>=0 ? slot : 0);
  }

void EmttSmcUpdateBlocks(SEmttSmcState &state,const MqlRates &bar,
                         const string symbol,const bool writeJournal)
  {
   for(int i=0;i<EMTT_SMC_MAX_BLOCK_RECORDS;i++)
     {
      SEmttSmcOrderBlock &block=state.blocks[i];
      if(!block.recorded || !block.active)
         continue;
      // Invalidation wins when a bar both touches and closes through a far
      // edge. The invalidated level leaves the offered set at once.
      const bool invalid=(block.bullish ? bar.close<block.zoneLow :
                                           bar.close>block.zoneHigh);
      if(invalid)
        {
         block.active=false;
         block.invalidated=true;
         if(writeJournal)
            PrintFormat("Emtt | Order block %s invalidated | close %s through %s | bar %s",
                        (block.bullish ? "bullish" : "bearish"),
                        EmttSmcPriceText(symbol,bar.close),
                        EmttSmcPriceText(symbol,(block.bullish ? block.zoneLow :
                                                                  block.zoneHigh)),
                        TimeToString(bar.time,TIME_DATE|TIME_MINUTES));
         continue;
        }
      if(bar.low<=block.zoneHigh && bar.high>=block.zoneLow)
        {
         block.active=false;
         block.mitigated=true;
         block.mitigationTime=bar.time;
         state.mitigatedBlockCount++;
        }
     }
  }

bool EmttSmcDisplacement(const MqlRates &rates[],const int candidate,
                         const int displacement,const int bodyPeriod,
                         const bool bullish,double &averageBody,
                         double &ratio)
  {
   averageBody=0.0;
   ratio=0.0;
   if(candidate<0 || displacement<0 || bodyPeriod<=0 ||
      candidate+bodyPeriod>=ArraySize(rates) ||
      displacement>=ArraySize(rates))
      return false;
   for(int i=1;i<=bodyPeriod;i++)
      averageBody+=MathAbs(rates[candidate+i].close-rates[candidate+i].open);
   averageBody/=bodyPeriod;
   if(!EmttSmcValidPositive(averageBody))
      return false;
   const double body=MathAbs(rates[displacement].close-rates[displacement].open);
   ratio=body/averageBody;
   if(bullish && rates[displacement].close<=rates[displacement].open)
      return false;
   if(!bullish && rates[displacement].close>=rates[displacement].open)
      return false;
   return(body>=EMTT_SMC_DISPLACEMENT_MULTIPLE*averageBody);
  }

void EmttSmcDiscoverBlocks(SEmttSmcState &state,const MqlRates &rates[],
                           const int index,const long barSequence,
                           const string symbol,const bool writeJournal)
  {
   if(index<0) return;
   const int last=(int)MathMin(ArraySize(rates)-1,index+state.obLookback);
   for(int type=0;type<2;type++)
     {
      const bool bullish=(type==1);
      for(int candidate=index+1;candidate<=last;candidate++)
        {
         const MqlRates &origin=rates[candidate];
         if((bullish && origin.close>=origin.open) ||
            (!bullish && origin.close<=origin.open))
            continue;
         if(EmttSmcBlockKnown(state,bullish,origin.time))
            continue;

         bool found=false;
         double averageBody=0.0,ratio=0.0;
         const int first=(int)MathMax(index,candidate-EMTT_SMC_IMPULSE_BARS);
         for(int displacement=candidate-1;displacement>=first;displacement--)
           {
            if(!EmttSmcDisplacement(rates,candidate,displacement,state.bodyPeriod,
                                    bullish,averageBody,ratio))
               continue;
            if((bullish && rates[displacement].close>origin.high) ||
               (!bullish && rates[displacement].close<origin.low))
              {
               found=true;
               break;
              }
           }
         if(!found) continue;

         const int slot=EmttSmcBlockSlot(state,bullish);
         SEmttSmcOrderBlock &block=state.blocks[slot];
         block.recorded=true;
         block.active=true;
         block.bullish=bullish;
         block.mitigated=false;
         block.invalidated=false;
         block.zoneLow=origin.low;
         block.zoneHigh=origin.high;
         block.displacementRatio=ratio;
         block.originTime=origin.time;
         block.originSequence=barSequence-(candidate-index);
         block.createdSequence=barSequence;
         block.mitigationTime=0;
         if(writeJournal)
            PrintFormat("Emtt | Order block %s %s-%s | displacement %.1fx average body | bar %s",
                        (bullish ? "bullish" : "bearish"),
                        EmttSmcPriceText(symbol,block.zoneLow),
                        EmttSmcPriceText(symbol,block.zoneHigh),ratio,
                        TimeToString(rates[index].time,TIME_DATE|TIME_MINUTES));
        }
     }
  }

void EmttSmcSelectOrderBlock(SEmttSmcState &state,const double close)
  {
   state.hasOrderBlock=false;
   state.orderBlockBullish=false;
   state.orderBlockLow=0.0;
   state.orderBlockHigh=0.0;
   state.orderBlockNearEdge=0.0;
   state.distanceToOBATRs=0.0;
   if(state.bias==0 || !EmttSmcValidPositive(state.atrValue))
      return;

   double best=DBL_MAX;
   int selected=-1;
   for(int i=0;i<EMTT_SMC_MAX_BLOCK_RECORDS;i++)
     {
      const SEmttSmcOrderBlock &block=state.blocks[i];
      if(!block.recorded || !block.active ||
         (state.bias>0 && !block.bullish) ||
         (state.bias<0 && block.bullish))
         continue;
      const bool eligible=(state.bias>0 ? block.zoneHigh<=close :
                                          block.zoneLow>=close);
      if(!eligible) continue;
      const double near=(state.bias>0 ? block.zoneHigh : block.zoneLow);
      const double distance=MathAbs(close-near);
      if(distance<best)
        {
         best=distance;
         selected=i;
        }
     }
   if(selected<0) return;

   const SEmttSmcOrderBlock &block=state.blocks[selected];
   state.hasOrderBlock=true;
   state.orderBlockBullish=block.bullish;
   state.orderBlockLow=block.zoneLow;
   state.orderBlockHigh=block.zoneHigh;
   state.orderBlockNearEdge=(state.bias>0 ? block.zoneHigh : block.zoneLow);
   const double raw=(state.bias>0 ? close-state.orderBlockNearEdge :
                                    state.orderBlockNearEdge-close)/state.atrValue;
   state.distanceToOBATRs=(raw>0.0 ? raw : 0.0);
  }

//+------------------------------------------------------------------+
//| Fair-value-gap lifecycle                                         |
//+------------------------------------------------------------------+
bool EmttSmcGapKnown(const SEmttSmcState &state,const bool bullish,
                     const datetime originTime)
  {
   for(int i=0;i<EMTT_SMC_MAX_GAP_RECORDS;i++)
      if(state.gaps[i].recorded && state.gaps[i].bullish==bullish &&
         state.gaps[i].originTime==originTime)
         return true;
   return false;
  }

int EmttSmcGapSlot(SEmttSmcState &state)
  {
   int active=0;
   int oldestActive=-1;
   long oldestActiveSequence=2147483647;
   for(int i=0;i<EMTT_SMC_MAX_GAP_RECORDS;i++)
      if(state.gaps[i].recorded && state.gaps[i].active)
        {
         active++;
         if(state.gaps[i].originSequence<oldestActiveSequence)
           {
            oldestActiveSequence=state.gaps[i].originSequence;
            oldestActive=i;
           }
        }
   if(active>=EMTT_SMC_MAX_ZONES && oldestActive>=0)
      state.gaps[oldestActive].recorded=false;

   int oldestInactive=-1;
   long oldestInactiveSequence=2147483647;
   for(int i=0;i<EMTT_SMC_MAX_GAP_RECORDS;i++)
     {
      if(!state.gaps[i].recorded)
         return i;
      if(!state.gaps[i].active &&
         state.gaps[i].originSequence<oldestInactiveSequence)
        {
         oldestInactiveSequence=state.gaps[i].originSequence;
         oldestInactive=i;
        }
     }
   return(oldestInactive>=0 ? oldestInactive : 0);
  }

void EmttSmcUpdateGaps(SEmttSmcState &state,const MqlRates &bar,
                       const string symbol,const bool writeJournal)
  {
   for(int i=0;i<EMTT_SMC_MAX_GAP_RECORDS;i++)
     {
      SEmttSmcGap &gap=state.gaps[i];
      if(!gap.recorded || !gap.active)
         continue;
      const bool filled=(gap.bullish ? bar.close<gap.zoneLow :
                                        bar.close>gap.zoneHigh);
      if(filled)
        {
         gap.active=false;
         gap.filled=true;
         if(writeJournal)
            PrintFormat("Emtt | Fair value gap %s filled | close %s through %s | bar %s",
                        (gap.bullish ? "bullish" : "bearish"),
                        EmttSmcPriceText(symbol,bar.close),
                        EmttSmcPriceText(symbol,(gap.bullish ? gap.zoneLow :
                                                               gap.zoneHigh)),
                        TimeToString(bar.time,TIME_DATE|TIME_MINUTES));
         continue;
        }
      if(bar.low<=gap.zoneHigh && bar.high>=gap.zoneLow)
        {
         gap.active=false;
         gap.mitigated=true;
         gap.mitigationTime=bar.time;
        }
     }
  }

void EmttSmcDiscoverGap(SEmttSmcState &state,const MqlRates &rates[],
                        const int index,const long barSequence,
                        const string symbol,const bool writeJournal)
  {
   if(index<0 || index+2>=ArraySize(rates))
      return;
   const MqlRates &a=rates[index+2];
   const MqlRates &c=rates[index];
   bool bullish=false;
   double low=0.0,high=0.0;
   if(c.low>a.high)
     {
      bullish=true;
      low=a.high;
      high=c.low;
     }
   else if(c.high<a.low)
     {
      bullish=false;
      low=c.high;
      high=a.low;
     }
   else
      return;
   if(EmttSmcGapKnown(state,bullish,c.time))
      return;

   const int slot=EmttSmcGapSlot(state);
   SEmttSmcGap &gap=state.gaps[slot];
   gap.recorded=true;
   gap.active=true;
   gap.bullish=bullish;
   gap.mitigated=false;
   gap.filled=false;
   gap.zoneLow=low;
   gap.zoneHigh=high;
   gap.originTime=c.time;
   gap.originSequence=barSequence;
   gap.createdSequence=barSequence;
   gap.mitigationTime=0;
   if(writeJournal)
      PrintFormat("Emtt | Fair value gap %s %s-%s | bar %s",
                  (bullish ? "bullish" : "bearish"),
                  EmttSmcPriceText(symbol,low),EmttSmcPriceText(symbol,high),
                  TimeToString(c.time,TIME_DATE|TIME_MINUTES));
  }

void EmttSmcSelectGaps(SEmttSmcState &state,const double close)
  {
   state.activeGapCount=0;
   state.hasGapAbove=false;
   state.hasGapBelow=false;
   state.gapAboveBullish=false;
   state.gapBelowBullish=false;
   state.gapAboveLow=0.0;
   state.gapAboveHigh=0.0;
   state.gapBelowLow=0.0;
   state.gapBelowHigh=0.0;
   state.gapAboveNearEdge=0.0;
   state.gapBelowNearEdge=0.0;
   state.gapAboveDistanceATRs=0.0;
   state.gapBelowDistanceATRs=0.0;
   state.gapDistanceATRs=0.0;

   double aboveDistance=DBL_MAX;
   double belowDistance=DBL_MAX;
   int above=-1,below=-1;
   for(int i=0;i<EMTT_SMC_MAX_GAP_RECORDS;i++)
     {
      const SEmttSmcGap &gap=state.gaps[i];
      if(!gap.recorded || !gap.active)
         continue;
      state.activeGapCount++;
      if(gap.zoneLow>=close)
        {
         const double distance=gap.zoneLow-close;
         if(distance<aboveDistance)
           {
            aboveDistance=distance;
            above=i;
           }
        }
      else if(gap.zoneHigh<=close)
        {
         const double distance=close-gap.zoneHigh;
         if(distance<belowDistance)
           {
            belowDistance=distance;
            below=i;
           }
        }
     }
   if(above>=0)
     {
      const SEmttSmcGap &gap=state.gaps[above];
      state.hasGapAbove=true;
      state.gapAboveBullish=gap.bullish;
      state.gapAboveLow=gap.zoneLow;
      state.gapAboveHigh=gap.zoneHigh;
      state.gapAboveNearEdge=gap.zoneLow;
      if(EmttSmcValidPositive(state.atrValue))
        {
         const double raw=(gap.zoneLow-close)/state.atrValue;
         state.gapAboveDistanceATRs=(raw>0.0 ? raw : 0.0);
        }
     }
   if(below>=0)
     {
      const SEmttSmcGap &gap=state.gaps[below];
      state.hasGapBelow=true;
      state.gapBelowBullish=gap.bullish;
      state.gapBelowLow=gap.zoneLow;
      state.gapBelowHigh=gap.zoneHigh;
      state.gapBelowNearEdge=gap.zoneHigh;
      if(EmttSmcValidPositive(state.atrValue))
        {
         const double raw=(close-gap.zoneHigh)/state.atrValue;
         state.gapBelowDistanceATRs=(raw>0.0 ? raw : 0.0);
        }
     }
   if(state.bias>0 && state.hasGapAbove)
      state.gapDistanceATRs=state.gapAboveDistanceATRs;
   else if(state.bias<0 && state.hasGapBelow)
      state.gapDistanceATRs=state.gapBelowDistanceATRs;
  }

//+------------------------------------------------------------------+
//| Event, range and score readings                                  |
//+------------------------------------------------------------------+
void EmttSmcSetEvent(SEmttSmcState &state,const EEmttSmcEvent eventKind,
                     const int direction,const int swingSlot,
                     const MqlRates &bar,const long barSequence,
                     const string symbol,const bool writeJournal)
  {
   const int previousBias=state.bias;
   const SEmttSmcSwing &swing=state.swings[swingSlot];
   state.eventKind=eventKind;
   state.eventDirection=direction;
   state.eventTime=bar.time;
   state.eventSequence=barSequence;
   state.barsSinceEvent=0;
   if(eventKind==EMTT_SMC_EVENT_BOS)
     {
      state.lastBosTime=bar.time;
      state.lastBosSequence=barSequence;
      state.lastBosDirection=direction;
     }
   else if(eventKind==EMTT_SMC_EVENT_CHOCH)
     {
      state.lastChochTime=bar.time;
      state.lastChochSequence=barSequence;
      state.lastChochDirection=direction;
     }
   state.bias=direction;
   state.swings[swingSlot].consumed=true;
   if(writeJournal)
     {
      if(eventKind==EMTT_SMC_EVENT_CHOCH)
         PrintFormat("Emtt | Structure CHoCH %s | close %s broke swing %s %s (pivot %s) | bias %s -> %s | bar %s",
                     EmttSmcBiasName(direction),EmttSmcPriceText(symbol,bar.close),
                     (swing.high ? "high" : "low"),EmttSmcPriceText(symbol,swing.level),
                     TimeToString(swing.pivotTime,TIME_DATE|TIME_MINUTES),
                     EmttSmcBiasName(previousBias),EmttSmcBiasName(direction),
                     TimeToString(bar.time,TIME_DATE|TIME_MINUTES));
      else
         PrintFormat("Emtt | Structure BOS %s | close %s broke swing %s %s (pivot %s) | bias %s | bar %s",
                     EmttSmcBiasName(direction),EmttSmcPriceText(symbol,bar.close),
                     (swing.high ? "high" : "low"),EmttSmcPriceText(symbol,swing.level),
                     TimeToString(swing.pivotTime,TIME_DATE|TIME_MINUTES),
                     EmttSmcBiasName(direction),
                     TimeToString(bar.time,TIME_DATE|TIME_MINUTES));
     }
  }

void EmttSmcEvaluateBreak(SEmttSmcState &state,const MqlRates &bar,
                           const long barSequence,const string symbol,
                           const bool allowEvent,const bool writeJournal)
  {
   if(!allowEvent || state.newestHighSlot<0 || state.newestLowSlot<0)
      return;
   // Rule 13.4 explicitly gives an otherwise impossible dual close to up.
   if(bar.close>state.swings[state.newestHighSlot].level)
     {
      const EEmttSmcEvent kind=(state.bias<0 ? EMTT_SMC_EVENT_CHOCH :
                                               EMTT_SMC_EVENT_BOS);
      EmttSmcSetEvent(state,kind,1,state.newestHighSlot,bar,barSequence,
                      symbol,writeJournal);
      return;
     }
   if(bar.close<state.swings[state.newestLowSlot].level)
     {
      const EEmttSmcEvent kind=(state.bias>0 ? EMTT_SMC_EVENT_CHOCH :
                                               EMTT_SMC_EVENT_BOS);
      EmttSmcSetEvent(state,kind,-1,state.newestLowSlot,bar,barSequence,
                      symbol,writeJournal);
     }
  }

void EmttSmcComputeZone(SEmttSmcState &state,const long barSequence,
                        const double close)
  {
   state.zone=EMTT_SMC_ZONE_NONE;
   state.legDirection=0;
   state.dealingRangeLow=0.0;
   state.dealingRangeHigh=0.0;
   state.equilibrium=0.0;
   state.zonePosition=0.0;

   int end=-1;
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
      if(EmttSmcSwingInsideWindow(state.swings[i],barSequence,
                                  state.structureWindow) &&
         (end<0 || state.swings[i].pivotSequence>
                   state.swings[end].pivotSequence))
         end=i;
   if(end<0) return;

   int origin=-1;
   for(int i=0;i<EMTT_SMC_MAX_SWINGS;i++)
      if(EmttSmcSwingInsideWindow(state.swings[i],barSequence,
                                  state.structureWindow) &&
         state.swings[i].high!=state.swings[end].high &&
         state.swings[i].pivotSequence<state.swings[end].pivotSequence &&
         (origin<0 || state.swings[i].pivotSequence>
                      state.swings[origin].pivotSequence))
         origin=i;
   if(origin<0) return;

   const double first=state.swings[end].level;
   const double second=state.swings[origin].level;
   const double low=MathMin(first,second);
   const double high=MathMax(first,second);
   const double range=high-low;
   if(!EmttSmcValidPositive(range) || !EmttSmcValidPositive(state.atrValue) ||
      range<EMTT_SMC_MIN_RANGE_ATR*state.atrValue)
      return;

   state.legDirection=(state.swings[end].high ? 1 : -1);
   state.dealingRangeLow=low;
   state.dealingRangeHigh=high;
   state.equilibrium=(high+low)*0.5;
   state.zonePosition=EmttSmcClamp01((close-low)/range);
   const double margin=EMTT_SMC_ZONE_DEADBAND*range;
   if(close<state.equilibrium-margin)
      state.zone=EMTT_SMC_ZONE_DISCOUNT;
   else if(close>state.equilibrium+margin)
      state.zone=EMTT_SMC_ZONE_PREMIUM;
   else
      state.zone=EMTT_SMC_ZONE_EQUILIBRIUM;
  }

double EmttSmcScore(const SEmttSmcState &state)
  {
   if(state.bias==0)
      return 0.0;
   double structure=0.0;
   if(state.eventDirection==state.bias)
     {
      if(state.eventKind==EMTT_SMC_EVENT_BOS) structure=1.0;
      else if(state.eventKind==EMTT_SMC_EVENT_CHOCH) structure=EMTT_SMC_CHOCH_TERM;
     }
   const double freshness=EmttSmcClamp01(1.0-
                         (double)state.barsSinceEvent/
                         (double)EMTT_SMC_EVENT_AGE_BARS);
   double zone=0.0;
   if(state.bias>0)
     {
      if(state.zone==EMTT_SMC_ZONE_DISCOUNT) zone=1.0;
      else if(state.zone==EMTT_SMC_ZONE_EQUILIBRIUM) zone=0.5;
     }
   else
     {
      if(state.zone==EMTT_SMC_ZONE_PREMIUM) zone=1.0;
      else if(state.zone==EMTT_SMC_ZONE_EQUILIBRIUM) zone=0.5;
     }
   const double proximity=(state.hasOrderBlock ?
       EmttSmcClamp01(1.0-state.distanceToOBATRs/EMTT_SMC_PROXIMITY_ATRS) : 0.0);
   const bool oppositeSweep=((state.bias>0 &&
                              state.lastSweepSide==EMTT_SMC_SWEEP_SELL) ||
                             (state.bias<0 &&
                              state.lastSweepSide==EMTT_SMC_SWEEP_BUY));
   const double sweep=(oppositeSweep ?
       EmttSmcClamp01(1.0-(double)state.barsSinceSweep/
                       (double)EMTT_SMC_SWEEP_AGE_BARS) : 0.0);
   return EmttSmcClamp01(EMTT_SMC_WEIGHT_STRUCTURE*structure+
                         EMTT_SMC_WEIGHT_FRESHNESS*freshness+
                         EMTT_SMC_WEIGHT_ZONE*zone+
                         EMTT_SMC_WEIGHT_PROXIMITY*proximity+
                         EMTT_SMC_WEIGHT_SWEEP*sweep);
  }

//+------------------------------------------------------------------+
//| One fixed-parameter closed-bar lifecycle step.                   |
//+------------------------------------------------------------------+
bool EmttSmcAdvanceFixed(SEmttSmcState &state,const MqlRates &rates[],
                         const double &atr[],const int index,
                         const int atrPeriod,const long barSequence,
                         const string symbol,const bool forceFirstEvaluation,
                         const bool writeJournal)
  {
   if(index<0 || index>=ArraySize(rates) || index>=ArraySize(atr) ||
      !EmttSmcValidPositive(atr[index]))
      return false;
   state.atrPeriod=atrPeriod;
   state.atrValue=atr[index];
   state.currentSequence=barSequence;
   const MqlRates &bar=rates[index];

   EmttSmcExpireSwings(state,barSequence);
   EmttSmcRefreshSwingFacts(state,barSequence);

   // Existing zones receive the newly closed bar before new zones are found;
   // a creation bar can therefore never mitigate its own zone.
   EmttSmcUpdateBlocks(state,bar,symbol,writeJournal);
   EmttSmcUpdateGaps(state,bar,symbol,writeJournal);

   const bool firstEvaluation=(!state.initialized || forceFirstEvaluation);
   EmttSmcEvaluateBreak(state,bar,barSequence,symbol,!firstEvaluation,
                        writeJournal);
   EmttSmcRefreshSwingFacts(state,barSequence); // a break consumes its level
   EmttSmcCheckSweeps(state,bar,barSequence,symbol,writeJournal);

   EmttSmcRecognizePivot(state,rates,index,barSequence);
   EmttSmcExpireSwings(state,barSequence);
   EmttSmcRefreshSwingFacts(state,barSequence);
   EmttSmcRebuildPools(state,barSequence,symbol,bar.time,writeJournal);
   EmttSmcDiscoverBlocks(state,rates,index,barSequence,symbol,writeJournal);
   EmttSmcDiscoverGap(state,rates,index,barSequence,symbol,writeJournal);

   state.barsSinceEvent=EmttSmcAge(barSequence,state.eventSequence);
   state.barsSinceSweep=EmttSmcAge(barSequence,state.lastSweepSequence);
   EmttSmcComputeZone(state,barSequence,bar.close);
   EmttSmcSelectOrderBlock(state,bar.close);
   EmttSmcSelectGaps(state,bar.close);
   state.ready=(state.confirmedHighCount>0 && state.confirmedLowCount>0 &&
                EmttSmcValidPositive(state.atrValue));
   state.smcScore=(state.ready ? EmttSmcScore(state) : 0.0);
   state.initialized=true;
   return true;
  }

// Replays only the bounded data horizon needed to reconstruct a changed
// parameter's facts. Journals are intentionally suppressed: the parameter
// line already records why the silent state rebuild happened.
bool EmttSmcReplayFixed(SEmttSmcState &state,const MqlRates &rates[],
                        const double &atr[],const int index,
                        const int atrPeriod,const long barSequence,
                        const string symbol,const bool forceFirstEvaluation)
  {
   const int needed=state.structureWindow+state.swingStrength+
                    state.bodyPeriod+2;
   int oldest=index+needed-1;
   if(oldest>=ArraySize(rates)) oldest=ArraySize(rates)-1;
   if(oldest>=ArraySize(atr)) oldest=ArraySize(atr)-1;
   if(oldest<index) return false;
   long sequence=barSequence-(oldest-index);
   bool processed=false;
   for(int current=oldest;current>=index;current--)
     {
      if(EmttSmcAdvanceFixed(state,rates,atr,current,atrPeriod,sequence,
                             symbol,(current==index && forceFirstEvaluation),
                             false))
         processed=true;
      sequence++;
     }
   return processed;
  }

//+------------------------------------------------------------------+
//| Public closed-bar entry point. The EA calls this from its replay |
//| and new-bar path after the volatility bucket and Supertrend.     |
//+------------------------------------------------------------------+
bool EmttSmcAdvance(SEmttSmcState &state,const MqlRates &rates[],
                    const double &atr[],const int index,
                    const string symbol,const EEmttAssetClass assetClass,
                    const int atrPeriod,const EEmttVolatility volatility,
                    const ENUM_TIMEFRAMES timeframe,const long barSequence,
                    const datetime barTime,const bool forceFirstEvaluation,
                    const bool writeJournal)
  {
   if(index<0 || index>=ArraySize(rates) || index>=ArraySize(atr) ||
      atrPeriod<=0 || !EmttSmcValidPositive(atr[index]))
      return false;

   bool changed=false;
   if(!EmttSmcApplyParameters(state,assetClass,volatility,timeframe,
                              barSequence,barTime,writeJournal,changed))
      return false;
   state.atrPeriod=atrPeriod;
   state.volatility=volatility;
   // The first call primes the bounded structure horizon bar by bar. This is
   // essential at the exact history gate too: a current-bar recomputation
   // would lose already-consumed pivots, mitigations and prior events.
   if(!state.initialized || changed || forceFirstEvaluation)
     {
      if(changed || forceFirstEvaluation)
         EmttSmcClearMeasurement(state);
      return EmttSmcReplayFixed(state,rates,atr,index,atrPeriod,barSequence,
                                symbol,forceFirstEvaluation);
     }
   return EmttSmcAdvanceFixed(state,rates,atr,index,atrPeriod,barSequence,
                              symbol,forceFirstEvaluation,writeJournal);
  }

//+------------------------------------------------------------------+
//| 13.11 panel clauses. Only the compact clause and status leave    |
//| this header; all other facts remain available for later phases.  |
//+------------------------------------------------------------------+
string EmttSmcClause(const SEmttSmcState &state,const int digits)
  {
   if(!state.ready)
      return "";
   string clause="";
   int parts=0;
   const string zone=EmttSmcZoneName(state.zone);
   if(zone!="")
     {
      clause=zone;
      parts++;
     }
   if(state.eventKind!=EMTT_SMC_EVENT_NONE && state.bias!=0)
     {
      const string event=EmttSmcEventName(state.eventKind)+" "+
                         EmttSmcBiasName(state.eventDirection);
      clause+=(parts>0 ? ", " : "")+event;
      parts++;
     }

   string level="";
   if(state.hasOrderBlock)
      level="OB "+DoubleToString(state.orderBlockNearEdge,digits);
   else if(state.bias>0 && state.hasGapAbove)
      level="FVG "+DoubleToString(state.gapAboveNearEdge,digits);
   else if(state.bias<0 && state.hasGapBelow)
      level="FVG "+DoubleToString(state.gapBelowNearEdge,digits);
   else if(state.lastSweepSide==EMTT_SMC_SWEEP_SELL &&
           state.barsSinceSweep<=EMTT_SMC_SWEEP_MENTION_BARS)
      level="swept lows";
   else if(state.lastSweepSide==EMTT_SMC_SWEEP_BUY &&
           state.barsSinceSweep<=EMTT_SMC_SWEEP_MENTION_BARS)
      level="swept highs";
   if(level!="")
     {
      clause+=(parts>0 ? ", " : "")+level;
      parts++;
     }
   return clause;
  }

string EmttWhyWithSmc(const string priorWhy,const SEmttSmcState &state,
                      const int digits)
  {
   const string clause=EmttSmcClause(state,digits);
   if(clause=="")
      return priorWhy;
   if(priorWhy=="" || priorWhy=="--")
      return clause;
   return priorWhy+" | "+clause;
  }

string EmttStatusForSmc(const SEmttSmcState &state)
  {
   if(!state.ready)
      return "";
   // The score and clause intentionally use the newest event. Status has a
   // different job: among all fresh facts a reversal warning outranks a later
   // continuation, exactly as 13.11 specifies.
   if(state.lastChochSequence>-1000000 &&
      EmttSmcAge(state.currentSequence,state.lastChochSequence)<=
      EMTT_SMC_STATUS_FRESH_BARS)
      return "Watching — CHoCH "+EmttSmcBiasName(state.lastChochDirection)+
             ", structure may be reversing";
   if(state.lastBosSequence>-1000000 &&
      EmttSmcAge(state.currentSequence,state.lastBosSequence)<=
      EMTT_SMC_STATUS_FRESH_BARS)
      return "Watching — BOS "+EmttSmcBiasName(state.lastBosDirection)+
             " confirmed, trend continuing";
   if(state.lastSweepSide!=EMTT_SMC_SWEEP_NONE &&
      state.barsSinceSweep<=EMTT_SMC_STATUS_FRESH_BARS)
     {
      const string where=(state.lastSweepSide==EMTT_SMC_SWEEP_BUY ?
                          "above" : "below");
      return "Watching — Liquidity swept "+where+", no structure break";
     }
   return "Watching — structure context only, no signal yet";
  }

#endif // EMTT_SMC_MQH
