//+------------------------------------------------------------------+
//|                                             Emtt_Regime.mqh      |
//|       Phase 2: regime logic, session clock and market-open check |
//|                   Spec: Emtt.md sections 9.2.5-9                |
//+------------------------------------------------------------------+
#ifndef EMTT_REGIME_MQH
#define EMTT_REGIME_MQH

#include "Emtt_DynamicParams.mqh"

struct SEmttRegimeMeasurements
  {
   double efficiency;       // Kaufman ER, on a 0-100 scale
   double atrRatio;         // matrix-period ATR / ATR(50)
   bool   kamaAligned;
   int    direction;        // +1 bullish, -1 bearish, 0 not aligned
   bool   bandsExpanding;
   bool   bandsSqueezing;
  };

struct SEmttRegimeState
  {
   bool        initialized;
   EEmttRegime stable;
   EEmttRegime pending;
   int         pendingBars;
  };

struct SEmttBrokerOffsetState
  {
   bool     initialized;
   bool     disagreement;
   datetime lastCheckGmt;
   long     lastValidOffsetSeconds;
  };

//+------------------------------------------------------------------+
//| Regime names and direction helpers                                |
//+------------------------------------------------------------------+
bool EmttIsTrending(const EEmttRegime regime)
  {
   return(regime==EMTT_REGIME_TRENDING_BULLISH ||
          regime==EMTT_REGIME_TRENDING_BEARISH);
  }

string EmttRegimeName(const EEmttRegime regime)
  {
   switch(regime)
     {
      case EMTT_REGIME_TRENDING_BULLISH: return "TRENDING (Bullish)";
      case EMTT_REGIME_TRENDING_BEARISH: return "TRENDING (Bearish)";
      case EMTT_REGIME_RANGING:           return "RANGING";
      case EMTT_REGIME_VOLATILE:          return "VOLATILE";
      case EMTT_REGIME_TRANSITION:        return "TRANSITION";
      case EMTT_REGIME_MARKET_CLOSED:     return "MARKET CLOSED";
      default:                            return "--";
     }
  }

EEmttRegime EmttRegimeForDirection(const int direction)
  {
   if(direction>0) return EMTT_REGIME_TRENDING_BULLISH;
   if(direction<0) return EMTT_REGIME_TRENDING_BEARISH;
   return EMTT_REGIME_TRANSITION;
  }

//+------------------------------------------------------------------+
//| Pure regime precedence + entry/exit margins                       |
//+------------------------------------------------------------------+
EEmttRegime EmttRegimeCandidate(const SEmttRegimeMeasurements &m,
                                const EEmttRegime previous,
                                const bool marketClosed)
  {
   if(marketClosed)
      return EMTT_REGIME_MARKET_CLOSED;
   if(EmttIsTrending(previous))
     {
      // Trending enters above 62 ER and, once active, remains until below 58.
      if(m.efficiency>=58.0 && m.kamaAligned)
         return EmttRegimeForDirection(m.direction);
     }
   else if(m.efficiency>62.0 && m.kamaAligned)
      return EmttRegimeForDirection(m.direction);

   // Trending has precedence over volatility; a clear direction stays a trend.
   if(previous==EMTT_REGIME_VOLATILE)
     {
      // The 1.3 exit margin applies after volatility has been established.
      if(m.atrRatio>=1.3 && !m.kamaAligned)
         return EMTT_REGIME_VOLATILE;
     }
   else if(m.atrRatio>1.5 && m.bandsExpanding && !m.kamaAligned)
      return EMTT_REGIME_VOLATILE;

   // Ranging enters below 28 and remains until ER rises above 32.
   if(previous==EMTT_REGIME_RANGING)
     {
      if(m.efficiency<=32.0)
         return EMTT_REGIME_RANGING;
     }
   else if(m.efficiency<28.0)
      return EMTT_REGIME_RANGING;

   return EMTT_REGIME_TRANSITION;
  }

void EmttRegimeReset(SEmttRegimeState &state)
  {
   state.initialized=false;
   state.stable=EMTT_REGIME_UNKNOWN;
   state.pending=EMTT_REGIME_UNKNOWN;
   state.pendingBars=0;
  }

void EmttRegimeMarkMarketClosed(SEmttRegimeState &state)
  {
   state.initialized=true;
   state.stable=EMTT_REGIME_MARKET_CLOSED;
   state.pending=EMTT_REGIME_UNKNOWN;
   state.pendingBars=0;
  }

// First measurement and first measurement after a market gap use entry
// levels immediately. Otherwise a new open-market state needs two closed bars.
EEmttRegime EmttRegimeAdvance(SEmttRegimeState &state,
                              const SEmttRegimeMeasurements &measurements,
                              const bool firstEvaluation)
  {
   if(firstEvaluation || !state.initialized)
     {
      state.stable=EmttRegimeCandidate(measurements,EMTT_REGIME_UNKNOWN,false);
      state.pending=EMTT_REGIME_UNKNOWN;
      state.pendingBars=0;
      state.initialized=true;
      return state.stable;
     }

   const EEmttRegime candidate=EmttRegimeCandidate(measurements,state.stable,false);
   if(candidate==state.stable)
     {
      state.pending=EMTT_REGIME_UNKNOWN;
      state.pendingBars=0;
      return state.stable;
     }

   if(candidate==state.pending)
      state.pendingBars++;
   else
     {
      state.pending=candidate;
      state.pendingBars=1;
     }
   if(state.pendingBars>=2)
     {
      state.stable=candidate;
      state.pending=EMTT_REGIME_UNKNOWN;
      state.pendingBars=0;
     }
   return state.stable;
  }

string EmttRegimeWhy(const EEmttRegime regime,
                     const SEmttRegimeMeasurements &measurements,
                     const EEmttVolatility volatility)
  {
   const string efficiency=DoubleToString(measurements.efficiency,0);
   string volName=EmttVolatilityName(volatility);
   StringToLower(volName);
   string kama="KAMAs not aligned";
   if(measurements.direction>0)
      kama="KAMAs aligned up";
   else if(measurements.direction<0)
      kama="KAMAs aligned down";

   if(EmttIsTrending(regime))
      return "Efficiency "+efficiency+"/100 and "+kama+
             "; volatility "+volName;
   if(regime==EMTT_REGIME_VOLATILE)
      return "ATR ratio "+DoubleToString(measurements.atrRatio,2)+
             " and bands expanding; "+kama+"; volatility "+volName;
   if(regime==EMTT_REGIME_RANGING)
      return "Efficiency "+efficiency+"/100; "+kama+
             "; volatility "+volName;
   if(regime==EMTT_REGIME_TRANSITION)
     {
      string bands="bands steady";
      if(measurements.bandsExpanding) bands="bands expanding";
      else if(measurements.bandsSqueezing) bands="bands squeezing";
      return "Efficiency "+efficiency+"/100; "+kama+
             "; "+bands+", volatility "+volName;
     }
   return "--";
  }

string EmttRegimeWhyPending(const EEmttRegime pending,
                            const SEmttRegimeMeasurements &measurements,
                            const EEmttVolatility volatility)
  {
   if(pending==EMTT_REGIME_UNKNOWN)
      return "";
   return "Candidate "+EmttRegimeName(pending)+
          " awaiting a second closed bar; "+
          EmttRegimeWhy(pending,measurements,volatility);
  }

string EmttStatusForRegime(const EEmttRegime regime)
  {
   switch(regime)
     {
      case EMTT_REGIME_TRENDING_BULLISH:
      case EMTT_REGIME_TRENDING_BEARISH:
         return "Watching — Trending market, monitoring for a quality setup";
      case EMTT_REGIME_RANGING:
         return "Waiting — Market ranging, no high-quality setup";
      case EMTT_REGIME_VOLATILE:
         return "Protecting — High volatility, signals need higher confidence";
      case EMTT_REGIME_TRANSITION:
         return "Watching — Market transitioning, monitoring for new direction";
      case EMTT_REGIME_MARKET_CLOSED:
         return "Paused — Waiting for market to open";
      default:
         return "Waiting — Loading chart history";
     }
  }

string EmttStatusForPending(const EEmttRegime pending)
  {
   if(pending==EMTT_REGIME_UNKNOWN)
      return "";
   return "Watching — Confirming "+EmttRegimeName(pending)+
          " for a second closed bar";
  }

//+------------------------------------------------------------------+
//| Gregorian date helpers for the explicit DST rules in Emtt.md     |
//+------------------------------------------------------------------+
datetime EmttMakeDateTime(const int year,const int month,const int day,
                          const int hour,const int minute,const int second)
  {
   MqlDateTime parts;
   ZeroMemory(parts);
   parts.year=year;
   parts.mon=month;
   parts.day=day;
   parts.hour=hour;
   parts.min=minute;
   parts.sec=second;
   return StructToTime(parts);
  }

int EmttWeekday(const int year,const int month,const int day)
  {
   MqlDateTime parts;
   TimeToStruct(EmttMakeDateTime(year,month,day,0,0,0),parts);
   return parts.day_of_week; // Sunday=0
  }

int EmttFirstSunday(const int year,const int month)
  {
   return 1+((7-EmttWeekday(year,month,1))%7);
  }

int EmttNthSunday(const int year,const int month,const int ordinal)
  {
   return EmttFirstSunday(year,month)+(ordinal-1)*7;
  }

int EmttDaysInMonth(const int year,const int month)
  {
   if(month==2)
     {
      const bool leap=((year%4==0 && year%100!=0) || year%400==0);
      return(leap ? 29 : 28);
     }
   if(month==4 || month==6 || month==9 || month==11)
      return 30;
   return 31;
  }

int EmttLastSunday(const int year,const int month)
  {
   const int last=EmttDaysInMonth(year,month);
   return last-EmttWeekday(year,month,last);
  }

bool EmttLondonDstOnDate(const int year,const int month,const int day)
  {
   const int start=EmttLastSunday(year,3);
   const int finish=EmttLastSunday(year,10);
   if(month>3 && month<10) return true;
   if(month==3 && day>=start) return true;
   if(month==10 && day<finish) return true;
   return false;
  }

bool EmttNewYorkDstOnDate(const int year,const int month,const int day)
  {
   const int start=EmttNthSunday(year,3,2);
   const int finish=EmttFirstSunday(year,11);
   if(month>3 && month<11) return true;
   if(month==3 && day>=start) return true;
   if(month==11 && day<finish) return true;
   return false;
  }

bool EmttSydneyDstOnDate(const int year,const int month,const int day)
  {
   const int start=EmttFirstSunday(year,10);
   const int finish=EmttFirstSunday(year,4);
   if(month>10 || month<4) return true;
   if(month==10 && day>=start) return true;
   if(month==4 && day<finish) return true;
   return false;
  }

bool EmttUtcInsideWindow(const datetime utc,const int year,const int month,
                         const int day,const int startHour,const int endHour,
                         const int offsetHours)
  {
   const datetime localStart=EmttMakeDateTime(year,month,day,startHour,0,0);
   const datetime localEnd=EmttMakeDateTime(year,month,day,endHour,0,0);
   const datetime utcStart=localStart-(datetime)(offsetHours*3600);
   const datetime utcEnd=localEnd-(datetime)(offsetHours*3600);
   return(utc>=utcStart && utc<utcEnd);
  }

bool EmttUtcInsideAsiaWindow(const datetime utc,const int year,const int month,
                             const int day)
  {
   const int sydneyOffset=(EmttSydneyDstOnDate(year,month,day) ? 11 : 10);
   const datetime sydneyOpen=EmttMakeDateTime(year,month,day,7,0,0)-
                              (datetime)(sydneyOffset*3600);
   const datetime tokyoClose=EmttMakeDateTime(year,month,day,18,0,0)-
                              (datetime)(9*3600);
   return(utc>=sydneyOpen && utc<tokyoClose);
  }

// The session clock is GMT-based. The default Asia label fills the small
// inter-session gaps created by markets' independent daylight-saving dates;
// therefore every open trading moment has a display name.
string EmttSessionNameUtc(const datetime utc)
  {
   if(utc<=0)
      return "--";
   MqlDateTime now;
   TimeToStruct(utc,now);
   bool asia=false,london=false,newYork=false;
   for(int dayOffset=-1;dayOffset<=1;dayOffset++)
     {
      const datetime candidateDate=EmttMakeDateTime(now.year,now.mon,now.day,0,0,0)+
                                   (datetime)(dayOffset*86400);
      MqlDateTime candidate;
      TimeToStruct(candidateDate,candidate);
      if(EmttUtcInsideAsiaWindow(utc,candidate.year,candidate.mon,candidate.day))
         asia=true;
      const int londonOffset=(EmttLondonDstOnDate(candidate.year,candidate.mon,candidate.day)?1:0);
      if(EmttUtcInsideWindow(utc,candidate.year,candidate.mon,candidate.day,7,16,londonOffset))
         london=true;
      const int nyOffset=(EmttNewYorkDstOnDate(candidate.year,candidate.mon,candidate.day)?-4:-5);
      if(EmttUtcInsideWindow(utc,candidate.year,candidate.mon,candidate.day,7,16,nyOffset))
         newYork=true;
     }

   string label="";
   if(asia) label="Asia";
   if(london) label+=(label=="" ? "London" : "/London");
   if(newYork) label+=(label=="" ? "NY" : "/NY");
   if(label=="") label="Asia";
   return label;
  }

//+------------------------------------------------------------------+
//| Check the broker's actual SymbolInfoSessionTrade schedule         |
//+------------------------------------------------------------------+
int EmttSessionSeconds(const datetime sessionTime)
  {
   MqlDateTime parts;
   TimeToStruct(sessionTime,parts);
   return parts.hour*3600+parts.min*60+parts.sec;
  }

bool EmttScheduleForDay(const string symbol,const int weekday,
                        const int currentSeconds,const bool currentDay)
  {
   for(uint session=0;session<64;session++)
     {
      datetime from,to;
      if(!SymbolInfoSessionTrade(symbol,(ENUM_DAY_OF_WEEK)weekday,session,from,to))
         break;
      const int fromSeconds=EmttSessionSeconds(from);
      const int toSeconds=EmttSessionSeconds(to);
      if(fromSeconds==toSeconds)
         return true; // a broker may express a full-day session as 00:00-00:00
      if(toSeconds>fromSeconds)
        {
         if(currentDay && currentSeconds>=fromSeconds && currentSeconds<toSeconds)
            return true;
        }
      else
        {
         if(currentDay && currentSeconds>=fromSeconds)
            return true;
         if(!currentDay && currentSeconds<toSeconds)
            return true;
        }
     }
   return false;
  }

bool EmttHasTradingSchedule(const string symbol)
  {
   for(int weekday=0;weekday<7;weekday++)
     {
      for(uint session=0;session<64;session++)
        {
         datetime from,to;
         if(!SymbolInfoSessionTrade(symbol,(ENUM_DAY_OF_WEEK)weekday,session,from,to))
            break;
         return true;
        }
     }
   return false;
  }

bool EmttMarketIsOpen(const string symbol,const ENUM_TIMEFRAMES timeframe,
                      const datetime serverNow,const datetime currentBarOpen)
  {
   long tradeMode=SYMBOL_TRADE_MODE_FULL;
   if(SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE,tradeMode) &&
      tradeMode==SYMBOL_TRADE_MODE_DISABLED)
      return false;

   MqlDateTime now;
   TimeToStruct(serverNow,now);
   const int seconds=now.hour*3600+now.min*60+now.sec;
   const int today=now.day_of_week;
   const int yesterday=(today+6)%7;

   if(EmttHasTradingSchedule(symbol))
      return(EmttScheduleForDay(symbol,today,seconds,true) ||
             EmttScheduleForDay(symbol,yesterday,seconds,false));

   // Only use candle age when the broker exposes no session schedule.
   const int periodSeconds=PeriodSeconds(timeframe);
   if(periodSeconds<=0 || currentBarOpen<=0)
      return false;
   return((long)(serverNow-currentBarOpen)<=(long)(2*periodSeconds));
  }

//+------------------------------------------------------------------+
//| Check broker/server-vs-GMT offset once per day; keep last valid   |
//+------------------------------------------------------------------+
void EmttCheckBrokerOffset(SEmttBrokerOffsetState &state,
                           const datetime serverNow,const datetime gmtNow)
  {
   if(serverNow<=0 || gmtNow<=0)
      return;
   const long observed=(long)(serverNow-gmtNow);
   if(!state.initialized)
     {
      state.initialized=true;
      state.disagreement=false;
      state.lastCheckGmt=gmtNow;
      state.lastValidOffsetSeconds=observed;
      PrintFormat("Emtt | Broker GMT offset initialized: %+d minutes",
                  (int)(observed/60));
      return;
     }
   if(gmtNow-state.lastCheckGmt<86400)
      return;
   if(MathAbs((double)(observed-state.lastValidOffsetSeconds))>60.0)
     {
      state.disagreement=true;
      PrintFormat("Emtt | Broker GMT offset disagreement: observed %+d min, retaining last valid %+d min",
                  (int)(observed/60),(int)(state.lastValidOffsetSeconds/60));
     }
   else
     {
      state.disagreement=false;
      state.lastValidOffsetSeconds=observed;
     }
   state.lastCheckGmt=gmtNow;
  }

datetime EmttSessionUtcNow(SEmttBrokerOffsetState &state,
                           const datetime serverNow,const datetime gmtNow)
  {
   EmttCheckBrokerOffset(state,serverNow,gmtNow);
   if(state.initialized && state.disagreement)
      return serverNow-(datetime)state.lastValidOffsetSeconds;
   if(gmtNow>0)
      return gmtNow;
   if(state.initialized)
      return serverNow-(datetime)state.lastValidOffsetSeconds;
   return 0;
  }

#endif // EMTT_REGIME_MQH
