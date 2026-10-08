//+------------------------------------------------------------------+
//|                                            Emtt_VolumeFlow.mqh   |
//| Phase 5: closed-bar volume flow (session VWAP, volume profile,   |
//|          prior-session naked POC, close-position CVD)            |
//| Spec: Emtt.md sections 15.2-15.7, 15.10-15.12                    |
//+------------------------------------------------------------------+
//| Design seam: this component owns only the state passed to it. It |
//| reads no chart, no panel and no EA global, so the later          |
//| confidence phase only ever consumes the published readings and   |
//| the score. It draws nothing: every level it finds is a number in |
//| the Row 9 clause or a journal line (15.2 rule 1).                |
//+------------------------------------------------------------------+
#ifndef EMTT_VOLUMEFLOW_MQH
#define EMTT_VOLUMEFLOW_MQH

// The 9.2.7 session calendar (back-to-back windows, per-market DST) is
// reused, never restated; Layer 2 (EmttLookbackScale) belongs to the
// approved Phase-3 header and is reused through it.
#include "Emtt_Regime.mqh"
#include "Emtt_Supertrend.mqh"

//--- 15.5 / 15.6 / 15.7 fixed measurement constants ----------------
#define EMTT_VF_BINS                40
#define EMTT_VF_VALUE_AREA          0.70
#define EMTT_VF_CVD_WINDOW          10
#define EMTT_VF_CVD_FLIP            0.25
#define EMTT_VF_CONTROL_SCALE       0.5
#define EMTT_VF_MAGNET_ATRS         3.0
#define EMTT_VF_WEIGHT_CONTROL      0.35
#define EMTT_VF_WEIGHT_FAIR         0.25
#define EMTT_VF_WEIGHT_VALUE        0.20
#define EMTT_VF_WEIGHT_MAGNET       0.20

//--- 15.3 / 15.11 fetch depth and guard rails ----------------------
#define EMTT_VF_SESSION_DEPTH       160
#define EMTT_VF_FETCH_BUFFER        10
#define EMTT_VF_WINDOW_MIN          50
#define EMTT_VF_WINDOW_MAX          400
#define EMTT_VF_PRIOR_POC_MIN_BARS  2
#define EMTT_VF_SESSION_ASIA        0
#define EMTT_VF_SESSION_LONDON      1
#define EMTT_VF_SESSION_NY          2

//--- 15.10 presentation freshness ----------------------------------
#define EMTT_VF_STATUS_FRESH_BARS   3

enum EEmttVfSide
  {
   EMTT_VF_SIDE_NONE=0,
   EMTT_VF_SIDE_ABOVE,
   EMTT_VF_SIDE_BELOW
  };

enum EEmttVfMagnet
  {
   EMTT_VF_MAGNET_NONE=0,
   EMTT_VF_MAGNET_POC,
   EMTT_VF_MAGNET_NAKED_POC,
   EMTT_VF_MAGNET_VAH,
   EMTT_VF_MAGNET_VAL
  };

//+------------------------------------------------------------------+
//| Published contract (15.7): the readings, the closed-bar facts    |
//| behind them and the score. One instance lives in the EA.         |
//+------------------------------------------------------------------+
struct SEmttVolumeFlowState
  {
   //--- parameters (15.11: class + timeframe + volatility, paused)  |
   bool                 parametersInitialized;
   EEmttAssetClass      assetClass;
   EEmttVolatility      volatility;
   EEmttVolatility      appliedVolatility;
   int                  profileWindow;
   long                 lastWindowChangeBar;

   //--- lifecycle                                                  |
   bool                 initialized;
   bool                 ready;
   long                 currentSequence;
   int                  atrPeriod;
   double               atrValue;
   double               lastClose;

   //--- session anchor (15.3)                                      |
   datetime             sessionAnchor;
   string               sessionName;
   datetime             lastBarTime;
   int                  barsSinceSessionStart;
   double               sessionVolume;   // sum of tick volume
   double               sessionPv;       // sum of typical price * volume
   double               sessionCvd;      // sum of per-bar deltas

   //--- session VWAP (15.4)                                        |
   bool                 hasVwap;
   double               vwap;
   EEmttVfSide          priceVsVwap;
   double               distanceVwapATRs;

   //--- volume profile (15.5)                                      |
   bool                 hasProfile;
   int                  profileBars;
   double               poc,vah,val;
   double               windowLow,windowHigh;
   double               profileVolume;

   //--- prior-session naked POC (15.5)                             |
   bool                 priorPocAvailable;
   bool                 priorPocNaked;
   double               priorPoc;

   //--- published magnet (15.5)                                    |
   EEmttVfMagnet        magnetKind;
   double               magnetPrice;
   double               distanceMagnetATRs;

   //--- CVD (15.6)                                                 |
   bool                 flowReading;
   int                  flowDirection;      // +1 / -1 / 0
   double               windowVolume;       // Vw
   double               netDelta;           // D
   bool                 flowClassified;     // a classification exists this session
   int                  lastFlowDirection;  // previous classification
   int                  flipDirection;      // newest classification flip
   long                 flipSequence;
   datetime             flipTime;

   //--- score (15.7)                                               |
   double               volumeFlowScore;
  };

//+------------------------------------------------------------------+
//| Small local helpers. No EA helper is called from this component. |
//+------------------------------------------------------------------+
bool EmttVfValid(const double value)
  {
   return(MathIsValidNumber(value) && value!=EMPTY_VALUE);
  }

bool EmttVfValidPositive(const double value)
  {
   return(EmttVfValid(value) && value>0.0);
  }

double EmttVfClamp01(const double value)
  {
   if(!MathIsValidNumber(value))
      return 0.0;
   return MathMax(0.0,MathMin(1.0,value));
  }

int EmttVfAge(const long currentSequence,const long occurredSequence)
  {
   if(occurredSequence<=-1000000 || currentSequence<occurredSequence)
      return 1000000;
   const long age=currentSequence-occurredSequence;
   if(age>2147483647)
      return 2147483647;
   return (int)age;
  }

string EmttVfTimeframeName(const ENUM_TIMEFRAMES timeframe)
  {
   if(timeframe==PERIOD_M5)  return "M5";
   if(timeframe==PERIOD_M15) return "M15";
   if(timeframe==PERIOD_M30) return "M30";
   const string name=EnumToString(timeframe);
   if(StringFind(name,"PERIOD_")==0)
      return StringSubstr(name,7);
   return name;
  }

int EmttVfDigits(const string symbol)
  {
   const int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   return(digits>=0 ? digits : 5);
  }

string EmttVfPriceText(const string symbol,const double price)
  {
   return DoubleToString(price,EmttVfDigits(symbol));
  }

// 15.10: the flow word is a reading, not a signal.
string EmttVfFlowName(const int direction)
  {
   if(direction>0) return "up";
   if(direction<0) return "down";
   return "flat";
  }

string EmttVfMagnetName(const EEmttVfMagnet kind)
  {
   switch(kind)
     {
      case EMTT_VF_MAGNET_POC:       return "POC";
      case EMTT_VF_MAGNET_NAKED_POC: return "naked POC";
      case EMTT_VF_MAGNET_VAH:       return "VAH";
      case EMTT_VF_MAGNET_VAL:       return "VAL";
      default:                       return "";
     }
  }

//+------------------------------------------------------------------+
//| 15.11 Layer 1 base matrix: the volume profile window, the        |
//| Low / Normal / High columns per asset class.                     |
//+------------------------------------------------------------------+
int EmttVfMatrixWindow(const EEmttAssetClass assetClass,
                       const EEmttVolatility volatility)
  {
   const bool low=(volatility==EMTT_VOL_LOW);
   const bool high=(volatility==EMTT_VOL_HIGH);
   switch(assetClass)
     {
      case EMTT_CLASS_METALS:
         return(high ? 300 : (low ? 150 : 200));

      case EMTT_CLASS_INDICES:
         return(high ? 250 : (low ? 150 : 200));

      case EMTT_CLASS_CRYPTO:
         return(high ? 200 : (low ? 100 : 150));

      case EMTT_CLASS_FOREX_MAJOR:
      case EMTT_CLASS_FOREX_CROSS:
      case EMTT_CLASS_GENERIC:
      default:
         return(high ? 300 : 200);
     }
  }

// Layer 2 scales the profile window only - it is the only lookback here.
// MathRound, never a truncation, never banker's rounding (13.10 / 15.11).
int EmttVfWindow(const EEmttAssetClass assetClass,
                 const EEmttVolatility volatility,
                 const ENUM_TIMEFRAMES timeframe)
  {
   const int base=EmttVfMatrixWindow(assetClass,volatility);
   int window=(int)MathRound((double)base*EmttLookbackScale(timeframe));
   if(window<EMTT_VF_WINDOW_MIN) window=EMTT_VF_WINDOW_MIN;
   if(window>EMTT_VF_WINDOW_MAX) window=EMTT_VF_WINDOW_MAX;
   return window;
  }

// 15.11: the gate becomes max(ST, SMC, volume flow) through one code path.
int EmttVfHistoryRequired(const EEmttAssetClass assetClass,
                          const EEmttVolatility volatility,
                          const ENUM_TIMEFRAMES timeframe)
  {
   return EmttVfWindow(assetClass,volatility,timeframe)+2;
  }

// 15.3: the advance copies its own closed-bar window: the profile
// window plus the deepest session plus the fetch buffer.
int EmttVfFetchDepth(const EEmttAssetClass assetClass,
                     const EEmttVolatility volatility,
                     const ENUM_TIMEFRAMES timeframe)
  {
   return EmttVfWindow(assetClass,volatility,timeframe)+
          EMTT_VF_SESSION_DEPTH+EMTT_VF_FETCH_BUFFER;
  }

//+------------------------------------------------------------------+
//| 15.3 session anchor - a pure function of the bar time and the    |
//| 9.2.7 calendar. Asia opens 07:00 Sydney local, London 07:00      |
//| London local, New York 07:00 New York local; each market keeps   |
//| its own daylight saving. The latest open whose window contains   |
//| the time wins, so an overlap anchors to its later session.       |
//+------------------------------------------------------------------+
datetime EmttVfSessionOpen(const int year,const int month,const int day,
                           const int session)
  {
   if(session==EMTT_VF_SESSION_ASIA)
     {
      const int offset=(EmttSydneyDstOnDate(year,month,day) ? 11 : 10);
      return EmttMakeDateTime(year,month,day,7,0,0)-(datetime)(offset*3600);
     }
   if(session==EMTT_VF_SESSION_LONDON)
     {
      const int offset=(EmttLondonDstOnDate(year,month,day) ? 1 : 0);
      return EmttMakeDateTime(year,month,day,7,0,0)-(datetime)(offset*3600);
     }
   const int offset=(EmttNewYorkDstOnDate(year,month,day) ? -4 : -5);
   return EmttMakeDateTime(year,month,day,7,0,0)-(datetime)(offset*3600);
  }

bool EmttVfSessionWindowContains(const datetime utc,const int year,
                                 const int month,const int day,
                                 const int session)
  {
   const datetime open=EmttVfSessionOpen(year,month,day,session);
   if(open<=0)
      return false;
   if(session==EMTT_VF_SESSION_ASIA)
     {
      // Sydney 07:00 -> Tokyo 18:00 local (09:00 UTC, no Tokyo DST).
      const datetime close=EmttMakeDateTime(year,month,day,18,0,0)-
                           (datetime)(9*3600);
      return(utc>=open && utc<close);
     }
   return(utc>=open && utc<open+(datetime)(9*3600));
  }

datetime EmttVfSessionAnchor(const datetime utc)
  {
   if(utc<=0)
      return 0;
   MqlDateTime parts;
   TimeToStruct(utc,parts);
   datetime bestOpen=0;
   bool found=false;
   datetime latestEarlier=0;
   datetime earliestOpen=0;
   // 15.3: candidate days are t's day and the previous day - an open can
   // be up to half a day before t, mirroring the day scan of the clock.
   // The next day is scanned as well: the Asia open (07:00 Sydney local)
   // falls on the previous UTC date, so the late-UTC hours of a Sydney
   // calendar day still anchor to that day's own Asia open.
   for(int dayOffset=1;dayOffset>=-1;dayOffset--)
     {
      const datetime candidateDate=EmttMakeDateTime(parts.year,parts.mon,
                                                    parts.day,0,0,0)+
                                   (datetime)(dayOffset*86400);
      MqlDateTime candidate;
      TimeToStruct(candidateDate,candidate);
      for(int session=EMTT_VF_SESSION_ASIA;session<=EMTT_VF_SESSION_NY;session++)
        {
         const datetime open=EmttVfSessionOpen(candidate.year,candidate.mon,
                                               candidate.day,session);
         if(open<=0)
            continue;
         if(earliestOpen<=0 || open<earliestOpen)
            earliestOpen=open;
         if(EmttVfSessionWindowContains(utc,candidate.year,candidate.mon,
                                        candidate.day,session))
           {
            if(!found || open>bestOpen)
              {
               bestOpen=open;
               found=true;
              }
           }
         if(open<=utc && open>latestEarlier)
            latestEarlier=open;
        }
     }
   if(found)
      return bestOpen;
   // Every open is outside its own window (a daylight-saving seam): stay
   // honest and deterministic - the newest open at or before t, else the
   // oldest candidate open.
   if(latestEarlier>0)
      return latestEarlier;
   return earliestOpen;
  }

// The session whose anchor is the newest one strictly before this anchor.
datetime EmttVfPreviousAnchor(const datetime anchor)
  {
   if(anchor<=0)
      return 0;
   MqlDateTime parts;
   TimeToStruct(anchor,parts);
   datetime previous=0;
   for(int dayOffset=1;dayOffset>=-2;dayOffset--)
     {
      const datetime candidateDate=EmttMakeDateTime(parts.year,parts.mon,
                                                    parts.day,0,0,0)+
                                   (datetime)(dayOffset*86400);
      MqlDateTime candidate;
      TimeToStruct(candidateDate,candidate);
      for(int session=EMTT_VF_SESSION_ASIA;session<=EMTT_VF_SESSION_NY;session++)
        {
         const datetime open=EmttVfSessionOpen(candidate.year,candidate.mon,
                                               candidate.day,session);
         if(open>0 && open<anchor && open>previous)
            previous=open;
        }
     }
   return previous;
  }

string EmttVfSessionLabel(const datetime anchor)
  {
   if(anchor<=0)
      return "--";
   MqlDateTime parts;
   TimeToStruct(anchor,parts);
   for(int dayOffset=1;dayOffset>=-2;dayOffset--)
     {
      const datetime candidateDate=EmttMakeDateTime(parts.year,parts.mon,
                                                    parts.day,0,0,0)+
                                   (datetime)(dayOffset*86400);
      MqlDateTime candidate;
      TimeToStruct(candidateDate,candidate);
      if(anchor==EmttVfSessionOpen(candidate.year,candidate.mon,candidate.day,
                                   EMTT_VF_SESSION_ASIA))
         return "Asia";
      if(anchor==EmttVfSessionOpen(candidate.year,candidate.mon,candidate.day,
                                   EMTT_VF_SESSION_LONDON))
         return "London";
      if(anchor==EmttVfSessionOpen(candidate.year,candidate.mon,candidate.day,
                                   EMTT_VF_SESSION_NY))
         return "NY";
     }
   return "--";
  }

// 15.3: the bars whose anchor is the stored one are one contiguous run in
// series order. The returned index is the exclusive end of that run.
int EmttVfSessionRunEnd(const MqlRates &rates[],const int index,
                        const datetime anchor)
  {
   const int total=ArraySize(rates);
   int current=index;
   while(current<total && EmttVfSessionAnchor(rates[current].time)==anchor)
      current++;
   return current;
  }

//+------------------------------------------------------------------+
//| 15.5 binning and profile. The window runs [rangeLow, rangeHigh)  |
//| in 40 bins; whole tick volume lands in the single bin holding    |
//| the bar's typical price. Degenerate or empty windows publish no  |
//| reading (false) but still report their own low / high / volume.  |
//+------------------------------------------------------------------+
bool EmttVfBinIndex(const double price,const double rangeLow,
                    const double width,int &bin)
  {
   bin=0;
   if(!EmttVfValidPositive(width))
      return false;
   int index=(int)MathFloor((price-rangeLow)/width);
   if(index<0)
      index=0;
   if(index>EMTT_VF_BINS-1)
      index=EMTT_VF_BINS-1;
   bin=index;
   return true;
  }

bool EmttVfComputeProfile(const MqlRates &rates[],const int index,
                          const int count,double &poc,double &vah,
                          double &val,double &rangeLow,double &rangeHigh,
                          double &totalVolume)
  {
   poc=0.0;
   vah=0.0;
   val=0.0;
   rangeLow=0.0;
   rangeHigh=0.0;
   totalVolume=0.0;
   if(index<0 || count<=0 || index+count>ArraySize(rates))
      return false;

   rangeLow=rates[index].low;
   rangeHigh=rates[index].high;
   double volume=0.0;
   for(int current=index;current<index+count;current++)
     {
      if(rates[current].low<rangeLow) rangeLow=rates[current].low;
      if(rates[current].high>rangeHigh) rangeHigh=rates[current].high;
      volume+=rates[current].volume;
     }
   totalVolume=volume;
   if(rangeHigh<=rangeLow || totalVolume<=0.0)
      return false;

   const double width=(rangeHigh-rangeLow)/(double)EMTT_VF_BINS;
   double bins[EMTT_VF_BINS];
   ArrayInitialize(bins,0.0);
   for(int current=index;current<index+count;current++)
     {
      const double typical=(rates[current].high+rates[current].low+
                            rates[current].close)/3.0;
      int bin=0;
      if(!EmttVfBinIndex(typical,rangeLow,width,bin))
         return false;
      bins[bin]+=rates[current].volume;
     }

   int pocBin=0;
   for(int bin=1;bin<EMTT_VF_BINS;bin++)
      if(bins[bin]>bins[pocBin]) // an exact tie keeps the lower-priced bin
         pocBin=bin;

   int topBin=pocBin;
   int bottomBin=pocBin;
   double areaVolume=bins[pocBin];
   const double target=EMTT_VF_VALUE_AREA*totalVolume;
   while(areaVolume<target)
     {
      const bool hasAbove=(topBin+1<EMTT_VF_BINS);
      const bool hasBelow=(bottomBin-1>=0);
      if(!hasAbove && !hasBelow)
         break;
      bool takeAbove=false;
      if(hasAbove && hasBelow)
         takeAbove=(bins[topBin+1]>bins[bottomBin-1]); // a tie adds the lower side
      else
         takeAbove=hasAbove;
      if(takeAbove)
        {
         topBin++;
         areaVolume+=bins[topBin];
        }
      else
        {
         bottomBin--;
         areaVolume+=bins[bottomBin];
        }
     }

   poc=rangeLow+((double)pocBin+0.5)*width;
   vah=rangeLow+((double)topBin+1.0)*width;
   val=rangeLow+(double)bottomBin*width;
   return true;
  }

// 15.5: the POC of one session's own bars, for the naked prior POC.
bool EmttVfComputeRunPoc(const MqlRates &rates[],const int firstIndex,
                         const int count,double &poc,double &levelLow,
                         double &levelHigh,double &volume)
  {
   double vah=0.0;
   double val=0.0;
   return EmttVfComputeProfile(rates,firstIndex,count,poc,vah,val,levelLow,
                               levelHigh,volume);
  }

//+------------------------------------------------------------------+
//| 15.6 close-position delta estimate from closed-bar tick volume.   |
//+------------------------------------------------------------------+
double EmttVfBarDelta(const MqlRates &bar)
  {
   const double range=bar.high-bar.low;
   if(range<=0.0)
      return 0.0;
   return bar.volume*(2.0*(bar.close-bar.low)/range-1.0);
  }

//+------------------------------------------------------------------+
//| Distance to the nearest magnet member, in price units.            |
//| directional=true keeps only levels at or beyond the close in the  |
//| flow direction, the set the score's proximity term reads (15.7).  |
//+------------------------------------------------------------------+
double EmttVfNearestMagnetDistance(const SEmttVolumeFlowState &state,
                                   const bool directional)
  {
   double nearest=-1.0;
   for(int candidate=0;candidate<4;candidate++)
     {
      bool present=false;
      double level=0.0;
      if(candidate==0 && state.priorPocAvailable && state.priorPocNaked)
        {
         present=true;
         level=state.priorPoc;
        }
      else if(candidate==1 && state.hasProfile)
        {
         present=true;
         level=state.poc;
        }
      else if(candidate==2 && state.hasProfile)
        {
         present=true;
         level=state.vah;
        }
      else if(candidate==3 && state.hasProfile)
        {
         present=true;
         level=state.val;
        }
      if(!present)
         continue;
      if(directional && state.flowDirection>0 && level<state.lastClose)
         continue;
      if(directional && state.flowDirection<0 && level>state.lastClose)
         continue;
      const double distance=MathAbs(state.lastClose-level);
      if(nearest<0.0 || distance<nearest)
         nearest=distance;
     }
   return nearest;
  }

//+------------------------------------------------------------------+
//| 15.7 volumeFlowScore. Four terms, weights summing to exactly 1.0.|
//| Computed from closed-bar facts only; clamped to 0.0 ... 1.0.     |
//+------------------------------------------------------------------+
double EmttVfScore(const SEmttVolumeFlowState &state)
  {
   if(!state.ready || state.flowDirection==0 ||
      !EmttVfValidPositive(state.windowVolume))
      return 0.0;

   // Control: net one-sidedness of half the window volume or more scores full.
   const double directionalDelta=(state.flowDirection>0 ? state.netDelta :
                                                          -state.netDelta);
   const double control=EmttVfClamp01(directionalDelta/
                        (EMTT_VF_CONTROL_SCALE*state.windowVolume));

   // Fair price: the close on the flow direction's side of the VWAP.
   double fair=0.0;
   if(state.hasVwap)
     {
      if(state.flowDirection>0 && state.priceVsVwap==EMTT_VF_SIDE_ABOVE)
         fair=1.0;
      else if(state.flowDirection<0 && state.priceVsVwap==EMTT_VF_SIDE_BELOW)
         fair=1.0;
     }

   // Value area: buying under value scores full, buying through value does not.
   // With no profile reading the value and magnet terms are 0 (15.5).
   double area=0.0;
   double magnet=0.0;
   if(state.hasProfile)
     {
      if(state.flowDirection>0)
        {
         if(state.lastClose<state.val)        area=1.0;
         else if(state.lastClose<=state.vah)  area=0.5;
         else                                 area=0.0;
        }
      else
        {
         if(state.lastClose>state.vah)        area=1.0;
         else if(state.lastClose>=state.val)  area=0.5;
         else                                 area=0.0;
        }
      if(EmttVfValidPositive(state.atrValue))
        {
         const double nearest=EmttVfNearestMagnetDistance(state,true);
         if(nearest>=0.0)
            magnet=EmttVfClamp01(1.0-(nearest/state.atrValue)/
                                 EMTT_VF_MAGNET_ATRS);
        }
     }

   return EmttVfClamp01(EMTT_VF_WEIGHT_CONTROL*control+
                        EMTT_VF_WEIGHT_FAIR*fair+
                        EMTT_VF_WEIGHT_VALUE*area+
                        EMTT_VF_WEIGHT_MAGNET*magnet);
  }

//+------------------------------------------------------------------+
//| State lifecycle: parameters reset on a context change, the       |
//| measurements reset on every replay.                              |
//+------------------------------------------------------------------+
void EmttVfClearMeasurement(SEmttVolumeFlowState &state)
  {
   state.initialized=false;
   state.ready=false;
   state.atrPeriod=0;
   state.atrValue=0.0;
   state.lastClose=0.0;

   state.sessionAnchor=0;
   state.sessionName="";
   state.lastBarTime=0;
   state.barsSinceSessionStart=0;
   state.sessionVolume=0.0;
   state.sessionPv=0.0;
   state.sessionCvd=0.0;

   state.hasVwap=false;
   state.vwap=0.0;
   state.priceVsVwap=EMTT_VF_SIDE_NONE;
   state.distanceVwapATRs=0.0;

   state.hasProfile=false;
   state.profileBars=0;
   state.poc=0.0;
   state.vah=0.0;
   state.val=0.0;
   state.windowLow=0.0;
   state.windowHigh=0.0;
   state.profileVolume=0.0;

   state.priorPocAvailable=false;
   state.priorPocNaked=false;
   state.priorPoc=0.0;

   state.magnetKind=EMTT_VF_MAGNET_NONE;
   state.magnetPrice=0.0;
   state.distanceMagnetATRs=0.0;

   state.flowReading=false;
   state.flowDirection=0;
   state.windowVolume=0.0;
   state.netDelta=0.0;
   state.flowClassified=false;
   state.lastFlowDirection=0;
   state.flipDirection=0;
   state.flipSequence=-1000000;
   state.flipTime=0;

   state.volumeFlowScore=0.0;
  }

void EmttVfReset(SEmttVolumeFlowState &state)
  {
   state.parametersInitialized=false;
   state.assetClass=EMTT_CLASS_GENERIC;
   state.volatility=EMTT_VOL_UNKNOWN;
   state.appliedVolatility=EMTT_VOL_UNKNOWN;
   state.profileWindow=0;
   state.lastWindowChangeBar=-1000000;
   state.currentSequence=0;
   EmttVfClearMeasurement(state);
  }

//+------------------------------------------------------------------+
//| 15.11 parameters: matrix, Layer 2, clamping and the existing     |
//| two-closed-bar pause through EmttCanChangeAt(). The pause governs|
//| the window only - every reading stays live.                      |
//+------------------------------------------------------------------+
bool EmttVfApplyParameters(SEmttVolumeFlowState &state,
                           const EEmttAssetClass assetClass,
                           const EEmttVolatility volatility,
                           const ENUM_TIMEFRAMES timeframe,
                           const long barSequence,const datetime barTime,
                           const bool writeJournal,bool &changed)
  {
   changed=false;
   const int window=EmttVfWindow(assetClass,volatility,timeframe);
   if(!state.parametersInitialized)
     {
      state.parametersInitialized=true;
      state.assetClass=assetClass;
      state.volatility=volatility;
      state.appliedVolatility=volatility;
      state.profileWindow=window;
      // Initialization is not a change; the first real change is not
      // artificially delayed by the pause.
      state.lastWindowChangeBar=barSequence-1000000;
      return true;
     }

   state.volatility=volatility;
   const bool windowWanted=(window!=state.profileWindow);
   if(!windowWanted)
     {
      state.assetClass=assetClass;
      state.appliedVolatility=volatility;
      return true;
     }
   if(!EmttCanChangeAt(barSequence,state.lastWindowChangeBar))
      return true;

   if(writeJournal)
      PrintFormat("Emtt | Profile window %d -> %d closed bars | volatility %s -> %s | bar %s",
                  state.profileWindow,window,
                  EmttVolatilityName(state.appliedVolatility),
                  EmttVolatilityName(volatility),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   state.assetClass=assetClass;
   state.appliedVolatility=volatility;
   state.profileWindow=window;
   state.lastWindowChangeBar=barSequence;
   // A window change recomputes, it does not guess: the profile and the
   // score are rebuilt from the new window's bars on this same bar, and no
   // other event is journaled (15.11).
   changed=true;
   return true;
  }

//+------------------------------------------------------------------+
//| 15.5 the previous session's own POC, computed once per session   |
//| from the copied history, and available only while that history   |
//| holds at least two positive-volume previous-session bars.        |
//+------------------------------------------------------------------+
void EmttVfComputePriorPoc(SEmttVolumeFlowState &state,
                           const MqlRates &rates[],const int fromIndex,
                           const datetime anchor)
  {
   state.priorPocAvailable=false;
   state.priorPocNaked=false;
   state.priorPoc=0.0;
   if(fromIndex<=0 || fromIndex>=ArraySize(rates))
      return;

   const datetime previousAnchor=EmttVfPreviousAnchor(anchor);
   if(previousAnchor<=0)
      return;
   if(EmttVfSessionAnchor(rates[fromIndex].time)!=previousAnchor)
      return;

   int positiveBars=0;
   int end=fromIndex;
   while(end<ArraySize(rates) &&
         EmttVfSessionAnchor(rates[end].time)==previousAnchor)
     {
      if(rates[end].volume>0.0)
         positiveBars++;
      end++;
     }
   if(positiveBars<EMTT_VF_PRIOR_POC_MIN_BARS)
      return;

   double poc=0.0;
   double levelLow=0.0;
   double levelHigh=0.0;
   double volume=0.0;
   if(!EmttVfComputeRunPoc(rates,fromIndex,end-fromIndex,poc,levelLow,
                           levelHigh,volume))
      return;
   state.priorPoc=poc;
   state.priorPocAvailable=true;
   state.priorPocNaked=true; // decided by the session's own bars, right after
  }

//+------------------------------------------------------------------+
//| 15.3 / 15.4 / 15.6 the session's own running sums, rebuilt bar   |
//| by bar from the copied window. Runs at a re-anchor, after a gap  |
//| and on a forced replay - never on a normal bar, so the per-bar   |
//| cost stays bounded.                                              |
//+------------------------------------------------------------------+
void EmttVfRebuildSession(SEmttVolumeFlowState &state,
                          const MqlRates &rates[],const int index,
                          const datetime anchor,const bool computePrior)
  {
   state.sessionAnchor=anchor;
   state.sessionName=EmttVfSessionLabel(anchor);
   state.barsSinceSessionStart=0;
   state.sessionVolume=0.0;
   state.sessionPv=0.0;
   state.sessionCvd=0.0;

   const int runEnd=EmttVfSessionRunEnd(rates,index,anchor);
   for(int current=index;current<runEnd;current++)
     {
      const double volume=rates[current].volume;
      const double typical=(rates[current].high+rates[current].low+
                            rates[current].close)/3.0;
      state.sessionVolume+=volume;
      state.sessionPv+=typical*volume;
      state.sessionCvd+=EmttVfBarDelta(rates[current]);
      state.barsSinceSessionStart++;
     }

   if(computePrior)
      EmttVfComputePriorPoc(state,rates,runEnd,anchor);

   // Naked while no closed bar of this session has traded through it. The
   // scan runs after the level is (re)computed, so the re-anchoring bar
   // itself already counts - it is a bar of the current session (15.5).
   if(state.priorPocAvailable)
     {
      state.priorPocNaked=true;
      for(int current=index;current<runEnd;current++)
         if(state.priorPoc>=rates[current].low &&
            state.priorPoc<=rates[current].high)
           {
            state.priorPocNaked=false;
            break;
           }
     }
  }

//+------------------------------------------------------------------+
//| 15.4 / 15.5 / 15.6 / 15.7 the published readings of one closed   |
//| bar: session VWAP, the profile window, the magnet, the score and |
//| the ready flag.                                                  |
//+------------------------------------------------------------------+
void EmttVfPublishReadings(SEmttVolumeFlowState &state,
                           const MqlRates &rates[],const int index)
  {
   const double close=rates[index].close;
   state.lastClose=close;

   //--- 15.4 session VWAP -------------------------------------------
   state.hasVwap=EmttVfValidPositive(state.sessionVolume);
   state.vwap=(state.hasVwap ? state.sessionPv/state.sessionVolume : 0.0);
   state.priceVsVwap=EMTT_VF_SIDE_NONE;
   state.distanceVwapATRs=0.0;
   if(state.hasVwap && EmttVfValidPositive(state.atrValue))
     {
      if(close>state.vwap)
         state.priceVsVwap=EMTT_VF_SIDE_ABOVE;
      else if(close<state.vwap)
         state.priceVsVwap=EMTT_VF_SIDE_BELOW;
      state.distanceVwapATRs=MathAbs(close-state.vwap)/state.atrValue;
     }

   //--- 15.5 volume profile over the current window ------------------
   const int available=ArraySize(rates)-index;
   const int windowBars=(available<state.profileWindow ? available :
                                                     state.profileWindow);
   state.profileBars=windowBars;
   double poc=0.0;
   double vah=0.0;
   double val=0.0;
   double rangeLow=0.0;
   double rangeHigh=0.0;
   double volume=0.0;
   const bool profileComputed=(windowBars>=state.profileWindow &&
                               state.profileWindow>0 &&
                               EmttVfComputeProfile(rates,index,
                                                    state.profileWindow,poc,
                                                    vah,val,rangeLow,
                                                    rangeHigh,volume));
   state.windowLow=rangeLow;
   state.windowHigh=rangeHigh;
   state.profileVolume=volume;
   state.hasProfile=profileComputed;
   if(profileComputed)
     {
      state.poc=poc;
      state.vah=vah;
      state.val=val;
     }
   state.ready=(windowBars>=state.profileWindow && volume>0.0 &&
                EmttVfValidPositive(state.atrValue));

   //--- 15.5 published magnet: the member nearest the close ---------
   state.magnetKind=EMTT_VF_MAGNET_NONE;
   state.magnetPrice=0.0;
   state.distanceMagnetATRs=0.0;
   double bestDistance=0.0;
   for(int candidate=0;candidate<4;candidate++)
     {
      bool present=false;
      EEmttVfMagnet kind=EMTT_VF_MAGNET_NONE;
      double level=0.0;
      if(candidate==0 && state.priorPocAvailable && state.priorPocNaked)
        {
         present=true;
         kind=EMTT_VF_MAGNET_NAKED_POC;
         level=state.priorPoc;
        }
      else if(candidate==1 && state.hasProfile)
        {
         present=true;
         kind=EMTT_VF_MAGNET_POC;
         level=state.poc;
        }
      else if(candidate==2 && state.hasProfile)
        {
         present=true;
         kind=EMTT_VF_MAGNET_VAH;
         level=state.vah;
        }
      else if(candidate==3 && state.hasProfile)
        {
         present=true;
         kind=EMTT_VF_MAGNET_VAL;
         level=state.val;
        }
      if(!present)
         continue;
      const double distance=MathAbs(close-level);
      // An exact distance tie keeps the earlier candidate: the preference
      // order is naked prior POC, session POC, VAH, VAL (15.5).
      if(state.magnetKind==EMTT_VF_MAGNET_NONE || distance<bestDistance)
        {
         state.magnetKind=kind;
         state.magnetPrice=level;
         bestDistance=distance;
        }
     }
   if(state.magnetKind!=EMTT_VF_MAGNET_NONE &&
      EmttVfValidPositive(state.atrValue))
     {
      double directional=MathAbs(close-state.magnetPrice);
      if(state.flowDirection>0)
         directional=MathMax(0.0,state.magnetPrice-close);
      else if(state.flowDirection<0)
         directional=MathMax(0.0,close-state.magnetPrice);
      state.distanceMagnetATRs=directional/state.atrValue;
     }

   state.volumeFlowScore=EmttVfScore(state);
  }

//+------------------------------------------------------------------+
//| 15.6 classification over the newest closed bars of the session.  |
//| Fewer than two session bars, or zero window volume, publish no   |
//| reading at all.                                                  |
//+------------------------------------------------------------------+
void EmttVfClassify(SEmttVolumeFlowState &state,const MqlRates &rates[],
                    const int index)
  {
   state.flowReading=false;
   state.flowDirection=0;
   state.windowVolume=0.0;
   state.netDelta=0.0;

   // The session's bars are one contiguous run in series order, so the
   // stored count is the run length - an O(1) reading, never a rescan.
   if(state.barsSinceSessionStart<=0)
      return;
   const int windowBars=(state.barsSinceSessionStart<EMTT_VF_CVD_WINDOW ?
                         state.barsSinceSessionStart : EMTT_VF_CVD_WINDOW);
   if(windowBars<2)
      return;

   double volumeSum=0.0;
   double deltaSum=0.0;
   for(int current=index;current<index+windowBars;current++)
     {
      volumeSum+=rates[current].volume;
      deltaSum+=EmttVfBarDelta(rates[current]);
     }
   if(volumeSum<=0.0)
      return;

   state.flowReading=true;
   state.windowVolume=volumeSum;
   state.netDelta=deltaSum;
   if(deltaSum>=EMTT_VF_CVD_FLIP*volumeSum)
      state.flowDirection=1;
   else if(deltaSum<=-EMTT_VF_CVD_FLIP*volumeSum)
      state.flowDirection=-1;
   else
      state.flowDirection=0;
  }

//+------------------------------------------------------------------+
//| Public closed-bar entry point (15.3, 15.12). The EA calls this   |
//| from its replay loop and from the incremental closed-bar path,   |
//| after EmttSmcAdvance and before the panel snapshot. Never        |
//| reached from OnTick.                                             |
//+------------------------------------------------------------------+
bool EmttVolumeFlowAdvance(SEmttVolumeFlowState &state,
                           const MqlRates &rates[],const double &atr[],
                           const int index,const string symbol,
                           const EEmttAssetClass assetClass,
                           const int atrPeriod,
                           const EEmttVolatility volatility,
                           const ENUM_TIMEFRAMES timeframe,
                           const long barSequence,const bool forceRebuild,
                           const bool writeJournal)
  {
   if(index<0 || index>=ArraySize(rates) || index>=ArraySize(atr) ||
      atrPeriod<=0)
      return false;
   const double atrValue=atr[index];
   if(!EmttVfValidPositive(atrValue))
      return false;
   const datetime barTime=rates[index].time;
   if(barTime<=0)
      return false;

   state.atrPeriod=atrPeriod;
   state.atrValue=atrValue;
   state.currentSequence=barSequence;

   bool windowChanged=false;
   if(!EmttVfApplyParameters(state,assetClass,volatility,timeframe,
                             barSequence,barTime,writeJournal,windowChanged))
      return false;

   const datetime anchor=EmttVfSessionAnchor(barTime);
   if(anchor<=0)
      return false;
   const bool newSession=(anchor!=state.sessionAnchor);
   int periodSeconds=(int)PeriodSeconds(timeframe);
   if(periodSeconds<1)
      periodSeconds=1;
   const bool gap=(state.lastBarTime>0 && !newSession &&
                   (long)(barTime-state.lastBarTime)>(long)periodSeconds);

   if(!state.initialized || forceRebuild || newSession || gap)
     {
      if(newSession && state.lastBarTime>0 && writeJournal)
         PrintFormat("Emtt | VWAP re-anchored | session %s -> %s | bar %s",
                     (state.sessionName=="" ? "--" : state.sessionName),
                     EmttVfSessionLabel(anchor),
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
      // A new session starts a fresh classification: the first reading of
      // the session is a reading, not a flip.
      if(newSession)
         state.flowClassified=false;
      EmttVfRebuildSession(state,rates,index,anchor,
                           newSession || forceRebuild || !state.initialized);
      state.lastBarTime=barTime;
     }
   else
     {
      const double volume=rates[index].volume;
      const double typical=(rates[index].high+rates[index].low+
                            rates[index].close)/3.0;
      state.sessionVolume+=volume;
      state.sessionPv+=typical*volume;
      state.sessionCvd+=EmttVfBarDelta(rates[index]);
      state.barsSinceSessionStart++;
      if(state.priorPocAvailable && state.priorPocNaked &&
         state.priorPoc>=rates[index].low &&
         state.priorPoc<=rates[index].high)
         state.priorPocNaked=false;
      state.lastBarTime=barTime;
     }

   EmttVfClassify(state,rates,index);

   // A classification flip is journaled once, with its reason (15.12).
   if(state.flowReading)
     {
      if(state.flowClassified &&
         state.flowDirection!=state.lastFlowDirection)
        {
         state.flipDirection=state.flowDirection;
         state.flipSequence=barSequence;
         state.flipTime=barTime;
         if(writeJournal)
            PrintFormat("Emtt | Flow CVD %s -> %s | net %+.2f x window volume | bar %s",
                        EmttVfFlowName(state.lastFlowDirection),
                        EmttVfFlowName(state.flowDirection),
                        state.netDelta/state.windowVolume,
                        TimeToString(barTime,TIME_DATE|TIME_MINUTES));
        }
      state.lastFlowDirection=state.flowDirection;
      state.flowClassified=true;
     }

   EmttVfPublishReadings(state,rates,index);
   state.initialized=true;
   return true;
  }

//+------------------------------------------------------------------+
//| 15.10 panel text. Only the compact clause and the status leave   |
//| this header; every other fact stays available for later phases.  |
//+------------------------------------------------------------------+
string EmttVfClause(const SEmttVolumeFlowState &state,const int digits)
  {
   if(!state.ready)
      return "";
   string clause="";
   int parts=0;

   if(state.flowReading)
     {
      clause="CVD "+EmttVfFlowName(state.flowDirection);
      parts++;
     }
   if(state.hasVwap && state.priceVsVwap!=EMTT_VF_SIDE_NONE)
     {
      const string fair=(state.priceVsVwap==EMTT_VF_SIDE_ABOVE ?
                         "above VWAP" : "below VWAP");
      clause+=(parts>0 ? ", " : "")+fair;
      parts++;
     }
   if(state.hasProfile && state.magnetKind!=EMTT_VF_MAGNET_NONE)
     {
      clause+=(parts>0 ? ", " : "")+EmttVfMagnetName(state.magnetKind)+" "+
              DoubleToString(state.magnetPrice,digits);
      parts++;
     }
   return clause;
  }

string EmttWhyWithVolumeFlow(const string priorWhy,
                             const SEmttVolumeFlowState &state,
                             const int digits)
  {
   const string clause=EmttVfClause(state,digits);
   if(clause=="")
      return priorWhy;
   if(priorWhy=="" || priorWhy=="--")
      return clause;
   return priorWhy+" | "+clause;
  }

// The flip is a reading: a fresh one owns Row 10 ahead of every
// chart-timeframe context line (15.10, item 3).
string EmttStatusForVolumeFlow(const SEmttVolumeFlowState &state)
  {
   if(state.flipSequence<=-1000000)
      return "";
   if(EmttVfAge(state.currentSequence,state.flipSequence)>
      EMTT_VF_STATUS_FRESH_BARS)
      return "";
   return "Watching — CVD turned "+EmttVfFlowName(state.flipDirection);
  }

//--- journal text for the replay summary line (15.12) ---------------
string EmttVfReadingText(const bool available,const string symbol,
                         const double value)
  {
   if(!available)
      return "--";
   return EmttVfPriceText(symbol,value);
  }

string EmttVfFlowText(const SEmttVolumeFlowState &state)
  {
   if(!state.flowReading)
      return "--";
   return EmttVfFlowName(state.flowDirection);
  }

#endif // EMTT_VOLUMEFLOW_MQH
