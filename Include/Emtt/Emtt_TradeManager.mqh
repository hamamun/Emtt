//+------------------------------------------------------------------+
//|                                       Emtt_TradeManager.mqh      |
//| Phase 8: broker-facing order and position lifecycle              |
//| Spec: Emtt.md sections 21.2-21.13                                 |
//+------------------------------------------------------------------+
//| This is the only header allowed to call trade functions. All      |
//| trade decisions come from Emtt_Trade.mqh; all learning-file       |
//| writes are delegated to the EA's existing learning-file path.    |
//| ASCII source only: display dashes are escaped at runtime.         |
//| Phase 10 (25.1): the per-tick divergence feed lives here and the  |
//| closed-candle trailing step reads its multiplier (25.8).          |
//+------------------------------------------------------------------+
#ifndef EMTT_TRADEMANAGER_MQH
#define EMTT_TRADEMANAGER_MQH

#include <Trade/Trade.mqh>
#include "Emtt_Dashboard.mqh"
#include "Emtt_TickDivergence.mqh"
#include "Emtt_Trade.mqh"
#include "Emtt_LearnFile.mqh"
#include "Emtt_Learning.mqh"

CTrade g_emttTradeExecutor;

struct SEmttTradeRuntime
  {
   string          symbol;
   ENUM_TIMEFRAMES timeframe;
   long            magic;
   bool            autoTrading;
   int             lotMode;
   bool            marginCheck;
   bool            placeStopLoss;
   bool            terminalAllowed;
   bool            accountAllowed;
   bool            marketOpen;
   bool            chartCompatible;
   bool            learningLoaded;
   string          sessionName;
   int             confidence;
   int             moodBar;
   EEmttRegime     mood;
   EEmttVolatility volatility;
   EEmttAssetClass assetClass;
   int             atrPeriod;
   double          atr;
   int             trendDirection;
   int             flowDirection;
   bool            viewsReady;
   datetime        barTime;
   double          bid;
   double          ask;
   double          point;
   int             digits;
  };

struct SEmttTradeState
  {
   string          symbol;
   long            magic;
   ENUM_TIMEFRAMES tradeTimeframe;
   datetime        planStartBarTime;
   datetime        filledAt;
   datetime        closedAt;
   datetime        lastAttemptBarTime;
   datetime        lastManagedBarTime;
   datetime        freshStatusBarTime;
   datetime        newsReadBarTime;
   ulong           pendingTicket;
   ulong           positionTicket;
   long            positionIdentifier;
   int             side;
   int             entryKind;
   int             entryConfidence;
   int             currentConfidence;
   int             entryMoodBar;
   int             expectedMinutes;
   int             expectedUpperMinutes;
   int             atrPeriod;
   EEmttRegime     entryMood;
   EEmttVolatility entryVolatility;
   double          plannedEntry;
   double          plannedStop;
   double          plannedTarget;
   double          tp1;
   double          tp2;
   double          entryPrice;
   double          entryAtr;
   double          initialVolume;
   double          positionVolume;
   double          currentStop;
   double          currentBrokerTarget;
   double          highestHigh;
   double          lowestLow;
   int             trailMethod;
   bool            initialized;
   bool            adoptionScanDone;
   bool            adopted;
   bool            hasPlanContext;
   bool            pendingOrder;
   bool            positionOpen;
   bool            recoveryScanned;
   bool            summaryOutcomePending;
   bool            closeHistoryPending;
   bool            positionHadStop;
   bool            stopExists;
   bool            breakevenReached;
   bool            breakevenPending;
   bool            tp1Hit;
   bool            tp1ProtectionPending;
   bool            partialDone;
   bool            fillRecordPending;
   bool            closeRecordPending;
   bool            sentOrderThisSession;
   bool            newsUnavailableLogged;
   bool            newsAvailable;
   bool            newsWindowOpen;
   bool            highNews;
   int             newsImpact;
   int             newsMinutes;
   double          newsSizeMultiplier;
   double          newsTrailMultiplier;
   string          newsEvent;
   string          newsStatus;
   string          newsUnavailableSession;
   string          freshStatus;
   string          holdStatus;
   string          gateStatus;
   string          liveStatus;
   string          entrySource;
   string          orderMode;
   string          recordTfName;
   int             closedNetPoints;
   double          closedNetMoney;
  };

void EmttTradeManagerReset(SEmttTradeState &state)
  {
   state.symbol="";
   state.magic=0;
   state.tradeTimeframe=PERIOD_CURRENT;
   state.planStartBarTime=0;
   state.filledAt=0;
   state.closedAt=0;
   state.lastAttemptBarTime=0;
   state.lastManagedBarTime=0;
   state.freshStatusBarTime=0;
   state.newsReadBarTime=0;
   state.pendingTicket=0;
   state.positionTicket=0;
   state.positionIdentifier=0;
   state.side=0;
   state.entryKind=EMTT_PLAN_ENTRY_MARKET;
   state.entryConfidence=0;
   state.currentConfidence=0;
   state.entryMoodBar=0;
   state.expectedMinutes=0;
   state.expectedUpperMinutes=0;
   state.atrPeriod=14;
   state.entryMood=EMTT_REGIME_UNKNOWN;
   state.entryVolatility=EMTT_VOL_UNKNOWN;
   state.plannedEntry=0.0;
   state.plannedStop=0.0;
   state.plannedTarget=0.0;
   state.tp1=0.0;
   state.tp2=0.0;
   state.entryPrice=0.0;
   state.entryAtr=0.0;
   state.initialVolume=0.0;
   state.positionVolume=0.0;
   state.currentStop=0.0;
   state.currentBrokerTarget=0.0;
   state.highestHigh=0.0;
   state.lowestLow=0.0;
   state.trailMethod=EMTT_TRAIL_METHOD_NONE;
   state.initialized=false;
   state.adoptionScanDone=false;
   state.adopted=false;
   state.hasPlanContext=false;
   state.pendingOrder=false;
   state.positionOpen=false;
   state.recoveryScanned=false;
   state.summaryOutcomePending=false;
   state.closeHistoryPending=false;
   state.positionHadStop=false;
   state.stopExists=false;
   state.breakevenReached=false;
   state.breakevenPending=false;
   state.tp1Hit=false;
   state.tp1ProtectionPending=false;
   state.partialDone=false;
   state.fillRecordPending=false;
   state.closeRecordPending=false;
   state.sentOrderThisSession=false;
   state.newsUnavailableLogged=false;
   state.newsAvailable=false;
   state.newsWindowOpen=false;
   state.highNews=false;
   state.newsImpact=EMTT_NEWS_IMPACT_NONE;
   state.newsMinutes=0;
   state.newsSizeMultiplier=1.0;
   state.newsTrailMultiplier=1.0;
   state.newsEvent="";
   state.newsStatus="";
   state.newsUnavailableSession="";
   state.freshStatus="";
   state.holdStatus="";
   state.gateStatus="";
   state.liveStatus="";
   state.entrySource="market price";
   state.orderMode="";
   state.recordTfName="";
   state.closedNetPoints=0;
   state.closedNetMoney=0.0;
  }

string EmttTradeManagerTfName(const ENUM_TIMEFRAMES timeframe)
  {
   const string name=EnumToString(timeframe);
   if(StringFind(name,"PERIOD_")==0)
      return StringSubstr(name,7);
   return name;
  }

string EmttTradeManagerTimeText(const datetime value)
  {
   return TimeToString(value,TIME_DATE|TIME_MINUTES);
  }

ENUM_TIMEFRAMES EmttTradeManagerTfFromName(const string name,
                                           const ENUM_TIMEFRAMES fallback)
  {
   if(name=="M5") return PERIOD_M5;
   if(name=="M15") return PERIOD_M15;
   if(name=="M30") return PERIOD_M30;
   return fallback;
  }

string EmttTradeManagerSigned(const double value,const int digits)
  {
   return (value>=0.0 ? "+" : "-")+DoubleToString(MathAbs(value),digits);
  }

string EmttTradeManagerMoney(const double amount)
  {
   const string currency=AccountInfoString(ACCOUNT_CURRENCY);
   return (amount>=0.0 ? "+" : "-")+currency+" "+
          DoubleToString(MathAbs(amount),2);
  }

string EmttTradeManagerRetcodeText(const uint code)
  {
   return IntegerToString((int)code);
  }

bool EmttTradeManagerRetcodeOK(const uint code)
  {
   return(code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_PLACED ||
          code==TRADE_RETCODE_DONE_PARTIAL);
  }

void EmttTradeManagerInit(SEmttTradeState &state,const string symbol,
                          const ENUM_TIMEFRAMES timeframe,const long magic)
  {
   EmttTradeManagerReset(state);
   state.symbol=symbol;
   state.tradeTimeframe=timeframe;
   state.magic=magic;
   state.initialized=true;
   g_emttTradeExecutor.SetExpertMagicNumber((ulong)magic);
   g_emttTradeExecutor.SetAsyncMode(false);
   g_emttTradeExecutor.SetTypeFillingBySymbol(symbol);
  }

bool EmttTradeManagerFindPosition(const string symbol,const long magic,
                                  ulong &ticket)
  {
   ticket=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const string foundSymbol=PositionGetSymbol(i);
      if(foundSymbol=="" || foundSymbol!=symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC)!=(long)magic)
         continue;
      ticket=(ulong)PositionGetInteger(POSITION_TICKET);
      return(ticket>0);
     }
   return false;
  }

bool EmttTradeManagerFindPending(const string symbol,const long magic,
                                 ulong &ticket,int &side,double &price)
  {
   ticket=0;
   side=0;
   price=0.0;
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      const ulong candidate=OrderGetTicket(i);
      if(candidate==0)
         continue;
      if(OrderGetString(ORDER_SYMBOL)!=symbol ||
         OrderGetInteger(ORDER_MAGIC)!=(long)magic)
         continue;
      const ENUM_ORDER_TYPE type=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type!=ORDER_TYPE_BUY_LIMIT && type!=ORDER_TYPE_SELL_LIMIT)
         continue;
      ticket=candidate;
      side=(type==ORDER_TYPE_BUY_LIMIT ? 1 : -1);
      price=OrderGetDouble(ORDER_PRICE_OPEN);
      return true;
     }
   return false;
  }

void EmttTradeManagerAdoptPosition(SEmttTradeState &state,
                                   const ulong ticket,const bool atInit,
                                   const datetime barTime)
  {
   if(ticket==0 || !PositionSelectByTicket(ticket))
      return;
   const bool firstPosition=!state.positionOpen;
   state.positionTicket=ticket;
   state.positionIdentifier=(long)PositionGetInteger(POSITION_IDENTIFIER);
   state.side=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1);
   state.positionVolume=PositionGetDouble(POSITION_VOLUME);
   state.entryPrice=PositionGetDouble(POSITION_PRICE_OPEN);
   state.filledAt=(datetime)PositionGetInteger(POSITION_TIME);
   state.currentStop=PositionGetDouble(POSITION_SL);
   state.currentBrokerTarget=PositionGetDouble(POSITION_TP);
   state.stopExists=(state.currentStop>0.0);
   if(firstPosition)
     {
      state.initialVolume=state.positionVolume;
      state.positionHadStop=state.stopExists;
      state.adopted=(atInit && !state.sentOrderThisSession);
      state.fillRecordPending=true;
      state.lastManagedBarTime=0;
      if(!state.hasPlanContext)
        {
         state.plannedEntry=state.entryPrice;
         state.plannedStop=state.currentStop;
         state.plannedTarget=state.currentBrokerTarget;
         state.tp1=state.currentBrokerTarget;
         state.tp2=0.0;
         state.tradeTimeframe=(state.tradeTimeframe==PERIOD_CURRENT ?
                               PERIOD_M15 : state.tradeTimeframe);
         state.recordTfName=EmttTradeManagerTfName(state.tradeTimeframe);
        }
      if(state.stopExists && state.plannedEntry>0.0 &&
         MathAbs(state.currentStop-state.entryPrice)<=
         SymbolInfoDouble(state.symbol,SYMBOL_POINT)*0.5)
        {
         state.breakevenReached=true;
         state.trailMethod=EMTT_TRAIL_METHOD_NONE;
        }
      if(state.adopted)
         PrintFormat("Emtt | Order adopted | position %I64u found on attach | bar %s",
                     ticket,EmttTradeManagerTimeText(barTime));
      else
         PrintFormat("Emtt | Order filled | ticket %I64u | %s | bar %s",
                     ticket,DoubleToString(state.entryPrice,
                           (int)SymbolInfoInteger(state.symbol,SYMBOL_DIGITS)),
                     EmttTradeManagerTimeText(barTime));
     }
   state.positionOpen=true;
   state.pendingOrder=false;
   state.pendingTicket=0;
   state.liveStatus="Signal active "+EmttTradeDash()+
                    " position open, managing.";
  }

bool EmttTradeManagerHistoryNet(const SEmttTradeState &state,
                               double &netMoney,int &netPoints)
  {
   netMoney=0.0;
   netPoints=0;
   if(state.positionIdentifier<=0 ||
      !HistorySelectByPosition((ulong)state.positionIdentifier))
      return false;
   const int total=HistoryDealsTotal();
   double entryVolume=0.0;
   for(int i=0;i<total;i++)
     {
      const ulong deal=HistoryDealGetTicket(i);
      if(deal==0)
         continue;
      netMoney+=HistoryDealGetDouble(deal,DEAL_PROFIT);
      netMoney+=HistoryDealGetDouble(deal,DEAL_SWAP);
      netMoney+=HistoryDealGetDouble(deal,DEAL_COMMISSION);
      const ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(
                                     deal,DEAL_ENTRY);
      if(entry==DEAL_ENTRY_IN || entry==DEAL_ENTRY_INOUT)
         entryVolume+=HistoryDealGetDouble(deal,DEAL_VOLUME);
     }
   const double tickSize=SymbolInfoDouble(state.symbol,SYMBOL_TRADE_TICK_SIZE);
   const double tickValue=SymbolInfoDouble(state.symbol,SYMBOL_TRADE_TICK_VALUE);
   const double point=SymbolInfoDouble(state.symbol,SYMBOL_POINT);
   const double lots=(entryVolume>0.0 ? entryVolume :
                      (state.initialVolume>0.0 ? state.initialVolume :
                                                 state.positionVolume));
   if(total<=0)
      return false;
   if(tickSize>0.0 && tickValue>0.0 && point>0.0 && lots>0.0)
     {
      const double moneyPerPoint=tickValue*point/tickSize*lots;
      if(moneyPerPoint>0.0)
         netPoints=(int)MathRound(netMoney/moneyPerPoint);
     }
   return true;
  }

void EmttTradeManagerObserve(SEmttTradeState &state,
                             const datetime barTime)
  {
   ulong position=0;
   if(EmttTradeManagerFindPosition(state.symbol,state.magic,position))
      EmttTradeManagerAdoptPosition(state,position,
                                    !state.adoptionScanDone,barTime);
   else if(state.positionOpen)
     {
      state.positionOpen=false;
      state.positionTicket=0;
      state.closedAt=(TimeTradeServer()>0 ? TimeTradeServer() : TimeCurrent());
      state.closeHistoryPending=true;
      state.pendingOrder=false;
      state.pendingTicket=0;
      state.holdStatus="";
      state.gateStatus="";
      state.liveStatus="";
      state.hasPlanContext=false;
     }
   if(state.closeHistoryPending)
     {
      double money=0.0;
      int points=0;
      if(EmttTradeManagerHistoryNet(state,money,points))
        {
         state.closeHistoryPending=false;
         state.closedNetMoney=money;
         state.closedNetPoints=points;
         state.closeRecordPending=true;
         state.summaryOutcomePending=true;
         state.freshStatus="Position closed "+EmttTradeDash()+" "+
            EmttTradeManagerSigned((double)points,0)+" pts ("+
            EmttTradeManagerMoney(money)+"). Scanning for the next setup.";
         state.freshStatusBarTime=barTime;
         PrintFormat("Emtt | Position closed | %s pts (%s) | bar %s",
                     EmttTradeManagerSigned((double)points,0),
                     EmttTradeManagerMoney(money),
                     EmttTradeManagerTimeText(barTime));
        }
     }

   ulong pending=0;
   int pendingSide=0;
   double pendingPrice=0.0;
   const bool foundPending=EmttTradeManagerFindPending(state.symbol,
                                state.magic,pending,pendingSide,pendingPrice);
   if(foundPending)
     {
      const bool firstPending=!state.pendingOrder;
      state.pendingTicket=pending;
      state.pendingOrder=true;
      state.side=pendingSide;
      state.liveStatus="Signal active "+EmttTradeDash()+
         " pending order at "+DoubleToString(pendingPrice,
           (int)SymbolInfoInteger(state.symbol,SYMBOL_DIGITS))+", waiting.";
      if(firstPending && !state.adoptionScanDone)
        {
         state.adopted=true;
         PrintFormat("Emtt | Order adopted | pending %I64u found on attach | bar %s",
                     pending,EmttTradeManagerTimeText(barTime));
        }
     }
   else if(state.pendingOrder)
     {
      state.pendingOrder=false;
      state.pendingTicket=0;
      if(state.positionOpen)
         state.liveStatus="Signal active "+EmttTradeDash()+
                          " position open, managing.";
      else
         state.liveStatus="";
     }
   state.adoptionScanDone=true;
  }

void EmttTradeManagerBindTicket(SEmttTradeState &state,
                                const SEmttLearnTicket &ticket,
                                const ENUM_TIMEFRAMES timeframe,
                                const int atrPeriod)
  {
   if(!ticket.used)
      return;
   if(state.hasPlanContext && state.planStartBarTime==ticket.startBarTime &&
      state.recordTfName==EmttTradeManagerTfName(timeframe))
     {
      if(state.expectedMinutes<=0 && ticket.est>0)
        {
         state.expectedMinutes=ticket.est;
         state.expectedUpperMinutes=EmttTradeExpectedUpperMinutes(ticket.est);
        }
      if(ticket.tradeFilledTime>0)
        {
         state.filledAt=ticket.tradeFilledTime;
         state.fillRecordPending=false;
        }
      return;
     }
   state.planStartBarTime=ticket.startBarTime;
   state.tradeTimeframe=timeframe;
   state.recordTfName=EmttTradeManagerTfName(timeframe);
   state.side=ticket.side;
   state.entryKind=(ticket.entryKind==EMTT_LEARN_ENTRY_BLOCK ?
                    EMTT_PLAN_ENTRY_BLOCK : EMTT_PLAN_ENTRY_MARKET);
   state.entryConfidence=ticket.confidence;
   state.currentConfidence=ticket.confidence;
   state.expectedMinutes=ticket.est;
   state.expectedUpperMinutes=EmttTradeExpectedUpperMinutes(ticket.est);
   state.atrPeriod=(atrPeriod>0 ? atrPeriod : 14);
   state.plannedEntry=ticket.entry;
   state.plannedStop=ticket.stop;
   state.plannedTarget=ticket.target;
   state.tp1=ticket.target;
   state.entrySource=(ticket.entryKind==EMTT_LEARN_ENTRY_BLOCK ?
                      "order block edge" : "market price");
   state.entryMood=EMTT_REGIME_TRANSITION;
   if(ticket.mood==EMTT_LEARN_MOOD_TRENDING)
      state.entryMood=(ticket.side>0 ? EMTT_REGIME_TRENDING_BULLISH :
                                      EMTT_REGIME_TRENDING_BEARISH);
   else if(ticket.mood==EMTT_LEARN_MOOD_RANGING)
      state.entryMood=EMTT_REGIME_RANGING;
   else if(ticket.mood==EMTT_LEARN_MOOD_VOLATILE)
      state.entryMood=EMTT_REGIME_VOLATILE;
   state.entryMoodBar=(ticket.mood==EMTT_LEARN_MOOD_TRENDING ? 60 :
                       (ticket.mood==EMTT_LEARN_MOOD_TRANSITION ? 75 : 70));
   state.entryVolatility=(EEmttVolatility)ticket.vol;
   state.hasPlanContext=true;
   state.tp2=0.0;
   if(ticket.tradeFilledTime>0)
     {
      state.filledAt=ticket.tradeFilledTime;
      state.fillRecordPending=false;
     }
   if(state.positionOpen)
     {
      if(state.currentBrokerTarget>0.0)
        {
         if(MathAbs(state.currentBrokerTarget-ticket.target)>
            SymbolInfoDouble(state.symbol,SYMBOL_POINT)*0.5)
           {
            state.tp1=ticket.target;
            state.tp2=state.currentBrokerTarget;
            state.tp1Hit=true;
            state.partialDone=true;
           }
         else
            state.tp1=state.currentBrokerTarget;
        }
      state.stopExists=(state.currentStop>0.0);
      if(state.stopExists && state.entryPrice>0.0 &&
         MathAbs(state.currentStop-state.entryPrice)<=
         SymbolInfoDouble(state.symbol,SYMBOL_POINT)*0.5)
         state.breakevenReached=true;
     }
  }

void EmttTradeManagerAcknowledgeFill(SEmttTradeState &state)
  {
   state.fillRecordPending=false;
  }

void EmttTradeManagerAcknowledgeClose(SEmttTradeState &state)
  {
   state.closeRecordPending=false;
  }

void EmttTradeManagerAcknowledgeSummary(SEmttTradeState &state)
  {
   state.summaryOutcomePending=false;
  }

string EmttTradeManagerNewsImpactName(const int impact)
  {
   if(impact==EMTT_NEWS_IMPACT_HIGH) return "high";
   if(impact==EMTT_NEWS_IMPACT_MEDIUM) return "medium";
   if(impact==EMTT_NEWS_IMPACT_LOW) return "low";
   return "none";
  }

bool EmttTradeManagerReadNews(const string symbol,const datetime now,
                              SEmttTradeState &state,
                              const datetime barTime)
  {
   state.newsAvailable=false;
   state.newsWindowOpen=false;
   state.highNews=false;
   state.newsImpact=EMTT_NEWS_IMPACT_NONE;
   state.newsSizeMultiplier=1.0;
   state.newsTrailMultiplier=1.0;
   state.newsEvent="";
   state.newsMinutes=0;
   state.newsStatus="";

   string currencies[2];
   int currencyCount=0;
   const string baseCurrency=SymbolInfoString(symbol,SYMBOL_CURRENCY_BASE);
   const string profitCurrency=SymbolInfoString(symbol,SYMBOL_CURRENCY_PROFIT);
   if(baseCurrency!="")
      currencies[currencyCount++]=baseCurrency;
   if(profitCurrency!="" && profitCurrency!=baseCurrency)
      currencies[currencyCount++]=profitCurrency;
   if(currencyCount==0)
     {
      if(!state.newsUnavailableLogged)
        {
         PrintFormat("Emtt | News calendar unavailable | no effect | bar %s",
                     EmttTradeManagerTimeText(barTime));
         state.newsUnavailableLogged=true;
        }
      return false;
     }

   bool anyValues=false;
   const datetime from=now-EMTT_NEWS_WINDOW_MIN*60;
   const datetime to=now+EMTT_NEWS_WINDOW_MIN*60;
   for(int currencyIndex=0;currencyIndex<currencyCount;currencyIndex++)
     {
      const string currency=currencies[currencyIndex];
      if(currency=="")
         continue;
      MqlCalendarValue values[];
      ResetLastError();
      const int valueCount=CalendarValueHistory(values,from,to,"",currency);
      if(valueCount<0)
         continue;
      if(valueCount<=0)
         continue;
      anyValues=true;
      for(int i=0;i<valueCount;i++)
        {
         MqlCalendarEvent event;
         if(!CalendarEventById(values[i].event_id,event))
            continue;
         int impact=EMTT_NEWS_IMPACT_LOW;
         if(event.importance==CALENDAR_IMPORTANCE_HIGH)
            impact=EMTT_NEWS_IMPACT_HIGH;
         else if(event.importance==CALENDAR_IMPORTANCE_MODERATE)
            impact=EMTT_NEWS_IMPACT_MEDIUM;
         if(impact==EMTT_NEWS_IMPACT_LOW)
            continue;
         const long delta=(long)(values[i].time-now);
         const long absolute=(delta<0 ? -delta : delta);
         const long chosenDelta=(long)(state.newsMinutes*60);
         const long chosenAbsolute=(chosenDelta<0 ? -chosenDelta : chosenDelta);
         const bool stronger=(impact>state.newsImpact);
         const bool nearer=(impact==state.newsImpact &&
                            (state.newsImpact==EMTT_NEWS_IMPACT_NONE ||
                             absolute<chosenAbsolute));
         const bool stableTie=(impact==state.newsImpact &&
                              absolute==chosenAbsolute &&
                              StringCompare(event.name,state.newsEvent)<0);
         if(stronger || nearer || stableTie)
           {
            state.newsImpact=impact;
            state.newsEvent=event.name;
            state.newsMinutes=(int)MathCeil((double)delta/60.0);
           }
        }
     }

   state.newsAvailable=anyValues;
   if(!state.newsAvailable)
     {
      if(!state.newsUnavailableLogged)
        {
         PrintFormat("Emtt | News calendar unavailable | no effect | bar %s",
                     EmttTradeManagerTimeText(barTime));
         state.newsUnavailableLogged=true;
        }
      return false;
     }
   if(state.newsImpact==EMTT_NEWS_IMPACT_NONE)
      return true;
   state.newsWindowOpen=true;
   state.highNews=(state.newsImpact==EMTT_NEWS_IMPACT_HIGH);
   state.newsSizeMultiplier=EmttTradeNewsSizeMultiplier(state.newsImpact);
   state.newsTrailMultiplier=EmttTradeNewsTrailMultiplier(state.newsImpact);
   state.newsStatus=EmttTradeNewsStatus(state.newsEvent,state.newsMinutes,
                                        state.newsImpact);
   return true;
  }

void EmttTradeManagerRefreshNews(const SEmttTradeRuntime &runtime,
                                 SEmttTradeState &state,
                                 const datetime closedBarTime)
  {
   if(runtime.sessionName!=state.newsUnavailableSession)
     {
      state.newsUnavailableSession=runtime.sessionName;
      state.newsUnavailableLogged=false;
     }
   if(closedBarTime<=0 || state.newsReadBarTime==closedBarTime)
      return;
   state.newsReadBarTime=closedBarTime;
   const datetime now=(TimeTradeServer()>0 ? TimeTradeServer() : TimeCurrent());
   EmttTradeManagerReadNews(runtime.symbol,now,state,closedBarTime);
  }

void EmttTradeManagerSetFresh(SEmttTradeState &state,const string status,
                              const datetime barTime,const string journal)
  {
   state.freshStatus=status;
   state.freshStatusBarTime=barTime;
   if(journal!="")
      Print("Emtt | "+journal+" | bar "+
            EmttTradeManagerTimeText(barTime));
  }

bool EmttTradeManagerModify(SEmttTradeState &state,const double stop,
                            const double target,const datetime barTime)
  {
   if(!state.positionOpen || state.positionTicket==0)
      return false;
   g_emttTradeExecutor.SetExpertMagicNumber((ulong)state.magic);
   const bool sent=g_emttTradeExecutor.PositionModify(state.positionTicket,
                                                       stop,target);
   if(!sent || !EmttTradeManagerRetcodeOK(g_emttTradeExecutor.ResultRetcode()))
     {
      const uint code=g_emttTradeExecutor.ResultRetcode();
      state.gateStatus="Order rejected "+EmttTradeDash()+
                       " broker error "+EmttTradeManagerRetcodeText(code);
      return false;
     }
   state.currentStop=stop;
   state.currentBrokerTarget=target;
   state.stopExists=(stop>0.0);
   state.gateStatus="";
   return true;
  }

void EmttTradeManagerCancelPending(SEmttTradeState &state,
                                   const string reason,
                                   const datetime barTime)
  {
   if(!state.pendingOrder || state.pendingTicket==0)
      return;
   g_emttTradeExecutor.SetExpertMagicNumber((ulong)state.magic);
   if(g_emttTradeExecutor.OrderDelete(state.pendingTicket))
     {
      PrintFormat("Emtt | Pending cancelled | %s | bar %s",reason,
                  EmttTradeManagerTimeText(barTime));
      state.pendingOrder=false;
      state.pendingTicket=0;
      state.liveStatus="";
      state.hasPlanContext=false;
     }
   else
     {
      const uint code=g_emttTradeExecutor.ResultRetcode();
      state.gateStatus="Order rejected "+EmttTradeDash()+
                       " broker error "+EmttTradeManagerRetcodeText(code);
     }
  }

void EmttTradeManagerUpdateExtremes(SEmttTradeState &state,
                                    const MqlRates &rates[],
                                    const int count)
  {
   for(int i=0;i<count;i++)
     {
      if(state.filledAt>0 && rates[i].time<state.filledAt)
         continue;
      if(state.highestHigh<=0.0 || rates[i].high>state.highestHigh)
         state.highestHigh=rates[i].high;
      if(state.lowestLow<=0.0 || rates[i].low<state.lowestLow)
         state.lowestLow=rates[i].low;
     }
  }

void EmttTradeManagerHistoryExtremes(SEmttTradeState &state,
                                    MqlRates &rates[],
                                    const int requested)
  {
   int count=requested;
   if(count<2) count=2;
   if(state.filledAt>0)
     {
      const int seconds=PeriodSeconds(state.tradeTimeframe);
      const datetime from=state.filledAt-(seconds>0 ? seconds : 60);
      const datetime to=(TimeTradeServer()>0 ? TimeTradeServer() : TimeCurrent());
      count=Bars(state.symbol,state.tradeTimeframe,from,to)+3;
      if(count<requested) count=requested;
      if(count>5000) count=5000;
     }
   ArrayResize(rates,count);
   ArraySetAsSeries(rates,true);
   const int copied=CopyRates(state.symbol,state.tradeTimeframe,1,count,rates);
   if(copied>0)
     {
      if(copied<ArraySize(rates))
         ArrayResize(rates,copied);
      EmttTradeManagerUpdateExtremes(state,rates,copied);
     }
  }

bool EmttTradeManagerSendOrder(SEmttTradeState &state,
                               const SEmttTradeRuntime &runtime,
                               const SEmttTradePlan &plan,
                               const SEmttSmcState &smc,
                               const SEmttVolumeFlowState &vf,
                               const double currentSpread,
                               const double lots,
                               const SEmttTradeOrderPlan &order,
                               const datetime barTime)
  {
   const string comment="Emtt "+EmttPlanSideName(order.side)+" "+
                        EmttTradeManagerTfName(runtime.timeframe);
   g_emttTradeExecutor.SetExpertMagicNumber((ulong)runtime.magic);
   g_emttTradeExecutor.SetAsyncMode(false);
   g_emttTradeExecutor.SetTypeFillingBySymbol(runtime.symbol);
   bool sent=false;
   if(order.pending)
     {
      if(order.side>0)
         sent=g_emttTradeExecutor.BuyLimit(lots,order.price,runtime.symbol,
                    order.stopLoss,order.takeProfit,ORDER_TIME_GTC,0,comment);
      else
         sent=g_emttTradeExecutor.SellLimit(lots,order.price,runtime.symbol,
                    order.stopLoss,order.takeProfit,ORDER_TIME_GTC,0,comment);
     }
   else
     {
      if(order.side>0)
         sent=g_emttTradeExecutor.Buy(lots,runtime.symbol,order.price,
                    order.stopLoss,order.takeProfit,comment);
      else
         sent=g_emttTradeExecutor.Sell(lots,runtime.symbol,order.price,
                    order.stopLoss,order.takeProfit,comment);
     }
   const uint retcode=g_emttTradeExecutor.ResultRetcode();
   if(!sent || !EmttTradeManagerRetcodeOK(retcode))
     {
      state.gateStatus="Order rejected "+EmttTradeDash()+
                       " broker error "+EmttTradeManagerRetcodeText(retcode);
      PrintFormat("Emtt | Order rejected | broker error %u | lots %s | bar %s",
                  retcode,DoubleToString(lots,2),
                  EmttTradeManagerTimeText(barTime));
      return false;
     }

   state.sentOrderThisSession=true;
   state.side=order.side;
   state.tradeTimeframe=runtime.timeframe;
   state.recordTfName=EmttTradeManagerTfName(runtime.timeframe);
   state.planStartBarTime=plan.startBarTime;
   state.plannedEntry=plan.entry;
   state.plannedStop=plan.stop;
   state.plannedTarget=plan.target;
   state.tp1=plan.target;
   state.tp2=0.0;
   state.entryKind=plan.entryKind;
   state.entryConfidence=runtime.confidence;
   state.currentConfidence=runtime.confidence;
   state.entryMood=runtime.mood;
   state.entryMoodBar=runtime.moodBar;
   state.entryVolatility=runtime.volatility;
   state.atrPeriod=runtime.atrPeriod;
   state.entryAtr=runtime.atr;
   state.entryPrice=(order.pending ? plan.entry : order.price);
   state.initialVolume=lots;
   state.positionVolume=0.0;
   state.positionHadStop=order.stopLossSent;
   state.stopExists=order.stopLossSent;
   state.currentStop=order.stopLoss;
   state.currentBrokerTarget=order.takeProfit;
   state.breakevenReached=false;
   state.breakevenPending=false;
   state.tp1Hit=false;
   state.tp1ProtectionPending=false;
   state.partialDone=false;
   state.trailMethod=EMTT_TRAIL_METHOD_NONE;
   state.highestHigh=0.0;
   state.lowestLow=0.0;
   state.hasPlanContext=true;
   state.gateStatus="";
   state.holdStatus="";

   SEmttTradeCandidate candidates[];
   string tp2Source="";
   const double targetReference=(order.side>0 ? runtime.bid : runtime.ask);
   EmttTradeCandidates(order.side,targetReference,smc,vf,candidates);
   EmttTradeInitialSecondTarget(order.side,plan.entry,targetReference,
       plan.target,candidates,state.tp2,tp2Source);
   state.orderMode=(order.pending ? "pending limit" : "market");
   if(order.pending)
     {
      state.pendingTicket=g_emttTradeExecutor.ResultOrder();
      state.pendingOrder=true;
      state.liveStatus="Signal active "+EmttTradeDash()+" pending order at "+
         DoubleToString(order.price,runtime.digits)+", waiting.";
      PrintFormat("Emtt | Order %s | pending limit %s | lots %s | GTC | bar %s",
                  EmttPlanSideName(order.side),
                  DoubleToString(order.price,runtime.digits),
                  DoubleToString(lots,2),EmttTradeManagerTimeText(barTime));
     }
   else
     {
      state.pendingOrder=false;
      state.pendingTicket=0;
      const string stopText=(order.stopLossSent ?
         DoubleToString(order.stopLoss,runtime.digits) : "not sent");
      const string sizeText=(runtime.lotMode==EMTT_LOT_MINIMUM ?
         "minimum" : "auto: risk 1.0%, conf "+
         IntegerToString(runtime.confidence)+"%, news "+
         DoubleToString(state.newsSizeMultiplier,2));
      PrintFormat("Emtt | Order %s | market | lots %s (%s) | entry %s (%s) | stop %s | TP1 %s | TP2 %s | RR 1:%s | spread %d pts | bar %s",
                  EmttPlanSideName(order.side),DoubleToString(lots,2),sizeText,
                  DoubleToString(order.price,runtime.digits),plan.entrySource,
                  stopText,DoubleToString(plan.target,runtime.digits),
                  (state.tp2>0.0 ? DoubleToString(state.tp2,runtime.digits) : "--"),
                  DoubleToString(plan.riskReward,1),(int)MathRound(currentSpread),
                  EmttTradeManagerTimeText(barTime));
     }
   return true;
  }

void EmttTradeManagerManagePosition(SEmttTradeState &state,
                                    const SEmttTradeRuntime &runtime,
                                    const SEmttSupertrendState &st,
                                    const SEmttSmcState &smc,
                                    const SEmttVolumeFlowState &vf,
                                    const datetime barTime,
                                    SEmttTickDivergenceState &div)
  {
   if(!state.positionOpen || state.tradeTimeframe==PERIOD_CURRENT)
      return;
   const datetime closedTime=iTime(state.symbol,state.tradeTimeframe,1);
   if(closedTime<=0 || closedTime==state.lastManagedBarTime)
      return;
   int requested=state.atrPeriod*6+EMTT_TRADE_SPREAD_WINDOW+5;
   if(requested<150) requested=150;
   if(requested>1200) requested=1200;
   MqlRates rates[];
   EmttTradeManagerHistoryExtremes(state,rates,requested);
   if(ArraySize(rates)<state.atrPeriod+1)
      return;
   const MqlRates bar=rates[0];
   const double atr=(runtime.timeframe==state.tradeTimeframe &&
                     runtime.atrPeriod==state.atrPeriod && runtime.atr>0.0 ?
                     runtime.atr : EmttTradeAtrFromRates(rates,state.atrPeriod));
   if(atr<=0.0)
      return;
   state.lastManagedBarTime=closedTime;
   if(state.entryAtr<=0.0)
      state.entryAtr=atr;
   state.currentConfidence=(runtime.confidence>=0 ? runtime.confidence :
                            state.entryConfidence);

   MqlTick tick;
   double bid=bar.close,ask=bar.close;
   if(SymbolInfoTick(state.symbol,tick))
     {
      bid=tick.bid;
      ask=tick.ask;
     }
   const double current=(state.side>0 ? bid : ask);
   const double favorablePoints=(state.side>0 ? current-state.entryPrice :
                                                 state.entryPrice-current)/
                                runtime.point;
   const bool inProfit=(favorablePoints>0.0);

   EmttTradeManagerRefreshNews(runtime,state,closedTime);

   // 21.7 step 1: the breakeven trigger is frozen at the ATR in effect
   // at entry. A disabled initial stop is attached here; otherwise it moves.
   if(!state.breakevenReached && !state.breakevenPending &&
      EmttTradeBreakevenReached(state.side,state.entryPrice,bar.high,bar.low,
                                state.entryAtr))
      state.breakevenPending=true;
   if(state.breakevenPending && !state.tp1Hit)
     {
      const double oldStop=state.currentStop;
      if(EmttTradeManagerModify(state,state.entryPrice,
                                state.currentBrokerTarget,closedTime))
        {
         state.breakevenPending=false;
         state.breakevenReached=true;
         state.trailMethod=EMTT_TRAIL_METHOD_NONE;
         const string event=(oldStop<=0.0 ? "Breakeven attached" :
                                            "Breakeven moved");
         EmttTradeManagerSetFresh(state,
            "Breakeven "+EmttTradeDash()+" stop at entry, trailing active.",
            closedTime,event+" | stop "+
            DoubleToString(state.entryPrice,runtime.digits)+
            " | trigger +1.0 ATR");
        }
     }

   // 21.7 step 2: TP1 is checked before it can be revised. A small
   // position skips only the partial amount; its protection still moves.
   const bool touchedTp1=(state.tp1>0.0 &&
      (state.side>0 ? bar.high>=state.tp1 : bar.low<=state.tp1));
   if(touchedTp1 && !state.tp1Hit)
     {
      const double minimum=SymbolInfoDouble(state.symbol,SYMBOL_VOLUME_MIN);
      const double step=SymbolInfoDouble(state.symbol,SYMBOL_VOLUME_STEP);
      const double closeVolume=EmttTradePartialVolume(state.positionVolume,
                                                       minimum,step);
      const bool partialSkipped=(closeVolume<=0.0);
      bool partialOK=partialSkipped;
      if(closeVolume>0.0)
        {
         const bool partialSent=g_emttTradeExecutor.PositionClosePartial(
                                   state.positionTicket,closeVolume);
         partialOK=partialSent && EmttTradeManagerRetcodeOK(
                       g_emttTradeExecutor.ResultRetcode());
         if(partialOK)
           {
            state.positionVolume-=closeVolume;
            state.partialDone=true;
           }
        }
      if(partialOK)
        {
         if(closeVolume>0.0 &&
            PositionSelectByTicket(state.positionTicket))
            state.positionVolume=PositionGetDouble(POSITION_VOLUME);
         state.tp1Hit=true;
         state.tp1ProtectionPending=true;
         state.trailMethod=EMTT_TRAIL_METHOD_NONE;
         double protectStop=state.currentStop;
         if(protectStop<=0.0 ||
            (state.side>0 ? protectStop<state.entryPrice :
                            protectStop>state.entryPrice))
            protectStop=state.entryPrice;
         const bool protectionSet=EmttTradeManagerModify(state,protectStop,
                                                      state.tp2,closedTime);
         if(protectionSet)
           {
            state.tp1ProtectionPending=false;
            state.breakevenPending=false;
            state.breakevenReached=true;
           }
         if(partialSkipped)
            EmttTradeManagerSetFresh(state,
               "TP1 hit "+EmttTradeDash()+
               (protectionSet ? " partial skipped, stop at breakeven." :
                            " partial skipped, protection update pending."),
               closedTime,"TP1 hit | partial skipped (volume too small)"+
               (protectionSet ? " | stop to "+
                DoubleToString(state.entryPrice,runtime.digits) :
                " | protection update pending"));
         else
            EmttTradeManagerSetFresh(state,
               "TP1 hit "+EmttTradeDash()+
               (protectionSet ? " 50% closed, stop at breakeven." :
                            " 50% closed, protection update pending."),
               closedTime,"TP1 hit | 50% closed"+
               (protectionSet ? " | stop to "+
                DoubleToString(state.entryPrice,runtime.digits) :
                " | protection update pending"));
        }
      else
        {
         state.gateStatus="Order rejected "+EmttTradeDash()+
            " broker error "+EmttTradeManagerRetcodeText(
               g_emttTradeExecutor.ResultRetcode());
        }
     }

   // 21.8 TP candidates are derived from the same closed-bar SMC / profile
   // facts as the plan. News and sessions never block management.
   if(smc.ready && vf.ready && state.tp1>0.0)
     {
      SEmttTradeCandidate candidates[];
      EmttTradeCandidates(state.side,current,smc,vf,candidates);
      const bool flowAllows=(vf.flowDirection==0 ||
                             vf.flowDirection==state.side);
      const int stay=(runtime.moodBar>0 ? runtime.moodBar-5 :
                                          state.entryMoodBar-5);
      const bool momentum=(st.ready && st.direction==state.side &&
                           flowAllows && state.currentConfidence>=stay);
      const double minRR=EmttPlanMinRiskReward(state.entryMood);
      SEmttTradeTargetResult targets;
      if(EmttTradeReviseTargets(state.side,state.entryPrice,current,
          (state.plannedStop>0.0 ? state.plannedStop : state.entryPrice),
          state.tp1,state.tp2,state.currentConfidence,stay,inProfit,momentum,
          state.tp1Hit,minRR,candidates,targets))
        {
         const double oldTp1=state.tp1;
         const double oldTp2=state.tp2;
         if(targets.tp1Changed)
           {
            state.tp1=targets.tp1;
            EmttTradeManagerSetFresh(state,
              "TP1 revised "+EmttTradeDash()+" "+
              DoubleToString(oldTp1,runtime.digits)+" to "+
              DoubleToString(state.tp1,runtime.digits)+".",
              closedTime,"TP1 revised | "+
              DoubleToString(oldTp1,runtime.digits)+" -> "+
              DoubleToString(state.tp1,runtime.digits)+" ("+
              targets.tp1Source+")");
           }
         if(targets.tp2Changed)
           {
            state.tp2=targets.tp2;
            if(!targets.tp1Changed)
               EmttTradeManagerSetFresh(state,
                  "TP2 revised "+EmttTradeDash()+" "+
                  (oldTp2>0.0 ? DoubleToString(oldTp2,runtime.digits) : "--")+
                  " to "+(state.tp2>0.0 ?
                  DoubleToString(state.tp2,runtime.digits) : "--")+".",
                  closedTime,"TP2 revised | "+
                  (oldTp2>0.0 ? DoubleToString(oldTp2,runtime.digits) : "--")+
                  " -> "+(state.tp2>0.0 ?
                  DoubleToString(state.tp2,runtime.digits) : "--"));
           }
         const double brokerTarget=(state.tp1Hit ? state.tp2 : state.tp1);
         if(targets.tp1Changed || targets.tp2Changed)
            EmttTradeManagerModify(state,state.currentStop,brokerTarget,
                                   closedTime);
        }
     }

   // Retry any broker-side stop/TP update that failed on an earlier
   // closed-candle attempt; state changes are journaled only on success.
   const double desiredTarget=(state.tp1Hit ? state.tp2 : state.tp1);
   double desiredStop=state.currentStop;
   if((state.tp1Hit || state.breakevenPending) &&
      (desiredStop<=0.0 ||
       (state.side>0 ? desiredStop<state.entryPrice :
                       desiredStop>state.entryPrice)))
      desiredStop=state.entryPrice;
   const double priceTolerance=(runtime.point>0.0 ? runtime.point*0.5 : 1e-10);
   const bool stopMismatch=(MathAbs(desiredStop-state.currentStop)>
                            priceTolerance);
   const bool targetMismatch=(MathAbs(desiredTarget-
                              state.currentBrokerTarget)>priceTolerance);
   if(stopMismatch || targetMismatch)
     {
      const double oldStop=state.currentStop;
      if(EmttTradeManagerModify(state,desiredStop,desiredTarget,closedTime))
        {
         if(state.tp1ProtectionPending)
           {
            state.tp1ProtectionPending=false;
            state.breakevenPending=false;
            state.breakevenReached=true;
            EmttTradeManagerSetFresh(state,
               "TP1 hit "+EmttTradeDash()+
               " protection active at breakeven.",closedTime,
               "TP1 protection updated | stop to "+
               DoubleToString(state.entryPrice,runtime.digits)+
               " | TP2 "+(state.tp2>0.0 ?
               DoubleToString(state.tp2,runtime.digits) : "--"));
           }
         else if(state.breakevenPending)
           {
            state.breakevenPending=false;
            state.breakevenReached=true;
            state.trailMethod=EMTT_TRAIL_METHOD_NONE;
            const string event=(oldStop<=0.0 ? "Breakeven attached" :
                                               "Breakeven moved");
            EmttTradeManagerSetFresh(state,
               "Breakeven "+EmttTradeDash()+
               " stop at entry, trailing active.",closedTime,
               event+" | stop "+
               DoubleToString(state.entryPrice,runtime.digits)+
               " | trigger +1.0 ATR");
           }
        }
     }

   // 21.7 step 3: trailing begins only after breakeven. The stop can only
   // improve, including after the news/context multipliers are applied.
   if(state.breakevenReached)
     {
      const bool hasSwing=(smc.ready &&
                           (state.side>0 ? smc.newestLowSlot>=0 :
                                           smc.newestHighSlot>=0));
      SEmttTradeTrailResult trail;
      // 25.8: the latched tick-divergence multiplier (1.0 when detection
      // is inactive or shows no divergence) multiplies the final distance.
      const double divMult=EmttTickDivMultiplier(div);
      const int divLevel=(divMult<1.0 ? div.level : (int)EMTT_DIV_LEVEL_NONE);
      if(EmttTradeTrailCalculate(state.side,state.entryPrice,current,state.tp1,
          atr,state.tradeTimeframe,state.currentConfidence,
          (runtime.mood!=EMTT_REGIME_UNKNOWN ? runtime.mood : state.entryMood),
          state.highNews,state.highestHigh,state.lowestLow,hasSwing,
          smc.newestLowLevel,smc.newestHighLevel,trail,divMult))
        {
         double proposed=trail.stop;
         if(state.side>0 && proposed<state.entryPrice)
            proposed=state.entryPrice;
         if(state.side<0 && proposed>state.entryPrice)
            proposed=state.entryPrice;
         proposed=NormalizeDouble(proposed,runtime.digits);
         state.trailMethod=trail.method;
         if(EmttTradeStopImproves(state.side,state.currentStop,proposed,
                                  runtime.point) &&
            (state.side>0 ? proposed<bid : proposed>ask))
           {
            const int locked=(int)MathRound((state.side>0 ?
                        proposed-state.entryPrice :
                        state.entryPrice-proposed)/runtime.point);
            if(EmttTradeManagerModify(state,proposed,
                  (state.tp1Hit ? state.tp2 : state.tp1),closedTime))
              {
               // 25.10: a divergence-driven update shows its own line for
               // this update only; 25.11: the journal carries the factor.
               const string trailStatus=(divLevel!=EMTT_DIV_LEVEL_NONE ?
                  EmttTickDivTrailStatus(divLevel) :
                  "Trailing "+EmttTradeDash()+" stop at "+
                  DoubleToString(proposed,runtime.digits)+", +"+
                  IntegerToString(locked)+" pts locked.");
               EmttTradeManagerSetFresh(state,trailStatus,closedTime,
                  "Trailing updated | "+
                  EmttTradeTrailMethodName(trail.method)+" | stop "+
                  DoubleToString(proposed,runtime.digits)+" ("+
                  DoubleToString(trail.rawDistance/atr,1)+" ATR x"+
                  DoubleToString(trail.confidenceMultiplier*
                    trail.regimeMultiplier*trail.newsMultiplier,2)+
                  (divMult!=1.0 ? " x"+DoubleToString(divMult,1) : "")+
                  ") | +"+IntegerToString(locked)+" pts locked");
               // 25.7: a trailing stop move resets the reading.
               EmttTickDivOnStopMoved(div,true);
              }
           }
        }
     }

   const int ageMinutes=(state.filledAt>0 ?
      (int)MathMax(0,(long)((TimeTradeServer()>0 ? TimeTradeServer() :
                       TimeCurrent())-state.filledAt)/60) : 0);
   if(EmttTradeTimeExitHold(ageMinutes,state.expectedUpperMinutes,
                            state.tp1Hit,inProfit))
     {
      if(state.holdStatus!=EmttTradeTimeExitHoldText())
         PrintFormat("Emtt | Holding past expected duration | not in profit (%s pts) | bar %s",
                     EmttTradeManagerSigned(favorablePoints,0),
                     EmttTradeManagerTimeText(closedTime));
      state.holdStatus=EmttTradeTimeExitHoldText();
     }
   else
      state.holdStatus="";
   if(EmttTradeTimeExitClose(ageMinutes,state.expectedUpperMinutes,
                             state.tp1Hit,favorablePoints))
     {
      const string duration=(state.expectedMinutes>0 ?
         EmttLearnDurationFromEstimate(state.expectedMinutes,
                                       state.tradeTimeframe) : "--");
      PrintFormat("Emtt | Time exit | past %s, in profit %s pts | closed at market | bar %s",
                  duration,EmttTradeManagerSigned(favorablePoints,0),
                  EmttTradeManagerTimeText(closedTime));
      g_emttTradeExecutor.SetExpertMagicNumber((ulong)state.magic);
      const bool closed=g_emttTradeExecutor.PositionClose(
                           state.positionTicket);
      if(!closed || !EmttTradeManagerRetcodeOK(
                         g_emttTradeExecutor.ResultRetcode()))
         state.gateStatus="Order rejected "+EmttTradeDash()+
            " broker error "+EmttTradeManagerRetcodeText(
               g_emttTradeExecutor.ResultRetcode());
     }
  }

void EmttTradeManagerSetSignalPlan(SEmttTradeState &state,
                                   const SEmttTradeRuntime &runtime,
                                   const SEmttTradePlan &plan,
                                   const SEmttSmcState &smc,
                                   const SEmttVolumeFlowState &vf)
  {
   if(!runtime.chartCompatible || !plan.active || runtime.confidence<0)
      return;
   const bool replacing=(state.hasPlanContext &&
                         state.planStartBarTime!=plan.startBarTime);
   const bool newContext=(!state.hasPlanContext || replacing);
   if((!state.positionOpen && !state.pendingOrder) || replacing)
     {
      if(newContext)
        {
         state.planStartBarTime=plan.startBarTime;
         state.tradeTimeframe=runtime.timeframe;
         state.recordTfName=EmttTradeManagerTfName(runtime.timeframe);
         state.side=plan.side;
         state.entryKind=plan.entryKind;
         state.entryConfidence=runtime.confidence;
         state.entryMood=runtime.mood;
         state.entryMoodBar=runtime.moodBar;
         state.entryVolatility=runtime.volatility;
         state.atrPeriod=runtime.atrPeriod;
         state.entryAtr=runtime.atr;
         state.plannedEntry=plan.entry;
         state.plannedStop=plan.stop;
         state.plannedTarget=plan.target;
         state.tp1=plan.target;
         state.tp2=0.0;
         state.expectedMinutes=0;
         state.expectedUpperMinutes=0;
         state.entrySource=plan.entrySource;
         state.hasPlanContext=true;
        }
      state.currentConfidence=runtime.confidence;
      if(newContext || state.tp2<=0.0)
        {
         SEmttTradeCandidate candidates[];
         EmttTradeCandidates(plan.side,
            (plan.side>0 ? runtime.bid : runtime.ask),smc,vf,candidates);
         string source="";
         double target2=0.0;
         EmttTradeInitialSecondTarget(plan.side,plan.entry,
            (plan.side>0 ? runtime.bid : runtime.ask),plan.target,
            candidates,target2,source);
         if(target2>0.0)
            state.tp2=target2;
        }
     }
   if(replacing && state.pendingOrder)
      EmttTradeManagerCancelPending(state,"new plan replaced it",runtime.barTime);
  }

void EmttTradeManagerTryOrder(SEmttTradeState &state,
                              const SEmttTradeRuntime &runtime,
                              const SEmttTradePlan &plan,
                              const SEmttSmcState &smc,
                              const SEmttVolumeFlowState &vf)
  {
   if(!runtime.chartCompatible || !runtime.learningLoaded ||
      !plan.active || runtime.confidence<0 || runtime.barTime<=0)
     {
      if(!plan.active)
         state.gateStatus="";
      return;
     }
   if(plan.side!=1 && plan.side!=-1)
      return;
   if(state.lastAttemptBarTime==runtime.barTime)
      return;
   if(state.positionOpen || state.pendingOrder)
      return;
   state.lastAttemptBarTime=runtime.barTime;

   EmttTradeManagerSetSignalPlan(state,runtime,plan,smc,vf);
   if(!state.hasPlanContext)
      return;

   const int digits=runtime.digits;
   const double currentSpread=(runtime.point>0.0 ?
      (runtime.ask-runtime.bid)/runtime.point : 0.0);
   MqlRates spreadBars[];
   ArraySetAsSeries(spreadBars,true);
   const int copied=CopyRates(runtime.symbol,runtime.timeframe,1,
                              EMTT_TRADE_SPREAD_WINDOW,spreadBars);
   double averageSpread=0.0;
   int spreadSamples=(copied>0 ? copied : 0);
   for(int i=0;i<spreadSamples;i++)
      averageSpread+=(double)spreadBars[i].spread;
   if(spreadSamples>0)
      averageSpread/=(double)spreadSamples;
   const bool spreadAllowed=EmttTradeSpreadAllowed(currentSpread,
                                                    averageSpread,
                                                    spreadSamples);

   SEmttTradeOrderPlan order;
   if(!EmttTradeBuildOrder(plan.side,plan.entryKind,plan.entry,plan.stop,
         plan.target,runtime.bid,runtime.ask,runtime.placeStopLoss,digits,order))
     {
      state.gateStatus="No trade "+EmttTradeDash()+" invalid plan levels";
      return;
     }

   const double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   const double tickSize=SymbolInfoDouble(runtime.symbol,SYMBOL_TRADE_TICK_SIZE);
   double tickValue=SymbolInfoDouble(runtime.symbol,SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue<=0.0)
      tickValue=SymbolInfoDouble(runtime.symbol,SYMBOL_TRADE_TICK_VALUE);
   const double minimum=SymbolInfoDouble(runtime.symbol,SYMBOL_VOLUME_MIN);
   const double maximum=SymbolInfoDouble(runtime.symbol,SYMBOL_VOLUME_MAX);
   const double step=SymbolInfoDouble(runtime.symbol,SYMBOL_VOLUME_STEP);
   const double lots=EmttTradeResolveLots(runtime.lotMode,balance,plan.entry,
      plan.stop,tickSize,tickValue,runtime.confidence,
      state.newsSizeMultiplier,minimum,maximum,step);
   if(lots<=0.0)
     {
      state.gateStatus="No trade "+EmttTradeDash()+" invalid lot sizing";
      return;
     }
   order.volume=lots;
   double margin=0.0;
   bool marginFits=true;
   if(runtime.marginCheck)
     {
      const bool calculated=OrderCalcMargin((ENUM_ORDER_TYPE)order.orderType,
         runtime.symbol,lots,order.price,margin);
      marginFits=(calculated &&
                  margin<=AccountInfoDouble(ACCOUNT_MARGIN_FREE));
     }

   SEmttTradeGateInput gate;
   gate.autoTrading=runtime.autoTrading;
   gate.terminalAllowed=runtime.terminalAllowed;
   gate.accountAllowed=runtime.accountAllowed;
   gate.marketOpen=runtime.marketOpen;
   gate.ownPending=state.pendingOrder;
   gate.ownPosition=state.positionOpen;
   gate.spreadAllowed=spreadAllowed;
   gate.marginCheck=runtime.marginCheck;
   gate.marginFits=marginFits;
   const EEmttTradeGateFailure failure=EmttTradeGateFirstFailure(gate);
   const string reason=EmttTradeGateStatus(failure,
                                           (int)MathRound(currentSpread));
   if(failure!=EMTT_TRADE_GATE_OK)
     {
      if(reason!=state.gateStatus)
         PrintFormat("Emtt | Trade gate | %s | bar %s",reason,
                     EmttTradeManagerTimeText(runtime.barTime));
      state.gateStatus=reason;
      return;
     }
   if(state.gateStatus!="")
      state.gateStatus="";
   EmttTradeManagerSendOrder(state,runtime,plan,smc,vf,currentSpread,lots,
                             order,runtime.barTime);
  }

void EmttTradeManagerBindCurrentOpenTicket(
   SEmttTradeState &state,const SEmttTradeRuntime &runtime,
   const SEmttTradePlan &plan,const SEmttLearnFileState &file)
  {
   if(state.positionOpen && state.hasPlanContext)
      return;
   int slot=-1;
   if(state.positionOpen)
     {
      const datetime fillMinute=(state.filledAt>0 ?
         StringToTime(EmttTradeManagerTimeText(state.filledAt)) : 0);
      slot=EmttLearnFileFindOpenTrade(file,fillMinute,state.side);
      if(slot<0 && fillMinute>0 && file.openTicket>=0 &&
         file.openTicket<file.ticketCount &&
         file.tickets[file.openTicket].side==state.side &&
         file.tickets[file.openTicket].startBarTime<=fillMinute)
         slot=file.openTicket;
     }
   else if(file.openTicket>=0 && file.openTicket<file.ticketCount)
      slot=file.openTicket;
   if(slot<0 || slot>=file.ticketCount)
      return;
   const SEmttLearnTicket ticket=file.tickets[slot];
   if(!ticket.used)
      return;
   const ENUM_TIMEFRAMES sourceTf=EmttTradeManagerTfFromName(
                                   file.tfName,runtime.timeframe);
   const int fileAtrPeriod=EmttMatrixField(runtime.assetClass,
                               (EEmttVolatility)ticket.vol,0);
   const int sourceAtrPeriod=(fileAtrPeriod>0 ? fileAtrPeriod :
                                               runtime.atrPeriod);
   if(state.pendingOrder)
     {
      if(ticket.state==EMTT_LEARN_STATE_CLOSED)
         return;
      ulong ticketNumber=state.pendingTicket;
      if(ticketNumber==0 || !OrderSelect(ticketNumber))
         return;
      const ENUM_ORDER_TYPE kind=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      const int orderSide=(kind==ORDER_TYPE_BUY_LIMIT ? 1 : -1);
      const double orderPrice=OrderGetDouble(ORDER_PRICE_OPEN);
      const double tolerance=SymbolInfoDouble(state.symbol,SYMBOL_POINT)*0.5;
      if(ticket.side!=orderSide ||
         MathAbs(ticket.entry-orderPrice)>tolerance ||
         ticket.startBarTime<=0)
         return;
      EmttTradeManagerBindTicket(state,ticket,sourceTf,sourceAtrPeriod);
     }
   else if(state.positionOpen)
     {
      if(ticket.side!=state.side || ticket.startBarTime<=0)
         return;
      EmttTradeManagerBindTicket(state,ticket,sourceTf,sourceAtrPeriod);
     }
   else if(plan.active && ticket.startBarTime==plan.startBarTime &&
           ticket.side==plan.side)
      EmttTradeManagerBindTicket(state,ticket,sourceTf,sourceAtrPeriod);
  }

void EmttTradeManagerStep(SEmttTradeState &state,
                          const SEmttTradeRuntime &runtime,
                          const SEmttTradePlan &plan,
                          const SEmttSupertrendState &st,
                          const SEmttSmcState &smc,
                          const SEmttVolumeFlowState &vf,
                          const SEmttLearnFileState &learningFile,
                          SEmttTickDivergenceState &div)
  {
   if(!state.initialized)
      EmttTradeManagerInit(state,runtime.symbol,runtime.timeframe,
                           runtime.magic);
   state.currentConfidence=runtime.confidence;
   EmttTradeManagerObserve(state,runtime.barTime);
   EmttTradeManagerBindCurrentOpenTicket(state,runtime,plan,learningFile);

   if(state.pendingOrder)
     {
      const bool matched=(runtime.learningLoaded && state.hasPlanContext &&
         learningFile.openTicket>=0 &&
         learningFile.openTicket<learningFile.ticketCount &&
         learningFile.tickets[learningFile.openTicket].startBarTime==
            state.planStartBarTime);
      if(!runtime.chartCompatible)
         EmttTradeManagerCancelPending(state,
            "no matching open plan in learning file",runtime.barTime);
      else if(runtime.learningLoaded && state.adopted && !matched)
         EmttTradeManagerCancelPending(state,
            "no matching open plan in learning file",runtime.barTime);
      else if(!runtime.marketOpen)
         EmttTradeManagerCancelPending(state,"market closed",runtime.barTime);
      else if(!plan.active || runtime.confidence<0)
         EmttTradeManagerCancelPending(state,"signal changed",runtime.barTime);
      else if(state.hasPlanContext &&
              (plan.side!=state.side ||
               plan.startBarTime!=state.planStartBarTime))
         EmttTradeManagerCancelPending(state,"signal changed",runtime.barTime);
     }
   else if(!state.positionOpen)
     {
      EmttTradeManagerSetSignalPlan(state,runtime,plan,smc,vf);
      EmttTradeManagerBindCurrentOpenTicket(state,runtime,plan,learningFile);
     }

   if(state.positionOpen)
      EmttTradeManagerManagePosition(state,runtime,st,smc,vf,runtime.barTime,
                                     div);
   else if(!state.pendingOrder && !state.closeHistoryPending &&
           !state.closeRecordPending && !state.summaryOutcomePending &&
           runtime.chartCompatible && runtime.learningLoaded && plan.active)
     {
      EmttTradeManagerRefreshNews(runtime,state,runtime.barTime);
      EmttTradeManagerTryOrder(state,runtime,plan,smc,vf);
     }
   if(!state.positionOpen && !state.pendingOrder)
      state.liveStatus="";
  }

//+------------------------------------------------------------------+
//| Phase 10 (25.1 / 25.3): the per-tick divergence feed, called from |
//| OnTick after the panel refresh. Only SymbolInfoTick is read; no   |
//| history copy, no indicator and no order call happens here. A new  |
//| or adopted position starts a fresh session with its own warmup;   |
//| everything resets silently when no Emtt position is open.         |
//+------------------------------------------------------------------+
void EmttTradeManagerFeedTick(const SEmttTradeState &state,
                              SEmttTickDivergenceState &div)
  {
   if(!state.initialized || !state.positionOpen ||
      state.positionTicket==0 || (state.side!=1 && state.side!=-1))
     {
      if(div.armed)
         EmttTickDivReset(div);
      return;
     }
   if(!div.armed || div.ticket!=state.positionTicket || div.side!=state.side)
      EmttTickDivArm(div,state.positionTicket,state.side,
                     (int)SymbolInfoInteger(state.symbol,SYMBOL_DIGITS));
   MqlTick tick;
   if(!SymbolInfoTick(state.symbol,tick))
      return;
   const long timeMsc=(tick.time_msc>0 ? (long)tick.time_msc :
                       (long)tick.time*1000);
   EmttTickDivFeed(div,tick.bid,tick.ask,timeMsc,state.entryAtr,
                   state.breakevenReached,true);
  }

void EmttTradeManagerFillPanel(SEmttPanelData &data,
                               SEmttTradeState &state,
                               const string symbol,const long magic,
                               const ENUM_TIMEFRAMES chartTimeframe,
                               const bool compatible,const double bid,
                               const double ask,const double point,
                               const int digits)
  {
   ulong ticket=0;
   if(!EmttTradeManagerFindPosition(symbol,magic,ticket))
     {
      if(state.pendingOrder)
        {
         state.liveStatus="Signal active "+EmttTradeDash()+
            " pending order at "+DoubleToString(state.plannedEntry,digits)+
            ", waiting.";
         data.liveHeader=EmttGlyph(EMTT_G_DIAMOND)+" LIVE TRADE "+ 
                         EmttTradeDash()+" PENDING";
         double pendingPrice=state.plannedEntry;
         double pendingVolume=state.initialVolume;
         if(state.pendingTicket>0 && OrderSelect(state.pendingTicket))
           {
            pendingPrice=OrderGetDouble(ORDER_PRICE_OPEN);
            pendingVolume=OrderGetDouble(ORDER_VOLUME_CURRENT);
           }
         const int volumeDigits=EmttTradeVolumeDigits(
                                SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP));
         data.ticket="Order: "+StringFormat("%I64u",state.pendingTicket)+
            " | "+EmttPlanSideName(state.side)+" "+
            DoubleToString(pendingVolume,volumeDigits)+" lots @ "+
            DoubleToString(pendingPrice,digits);
         data.floatingPL="Floating P/L: -- (pending order)";
         data.liveSL="Live SL: "+(state.plannedStop>0.0 ?
            DoubleToString(state.plannedStop,digits) : "--")+
            " | TP1: "+(state.plannedTarget>0.0 ?
            DoubleToString(state.plannedTarget,digits) : "--")+
            " TP2: --";
         const string duration=(state.expectedMinutes>0 ?
            EmttLearnDurationFromEstimate(state.expectedMinutes,
               (state.tradeTimeframe!=PERIOD_CURRENT ? state.tradeTimeframe :
                                                      chartTimeframe)) : "--");
         data.protect="Protect: Pending | Age: -- / "+duration;
         data.status=state.liveStatus;
        }
      return;
     }
   if(!PositionSelectByTicket(ticket))
      return;
   state.positionOpen=true;
   state.positionTicket=ticket;
   state.positionVolume=PositionGetDouble(POSITION_VOLUME);
   state.entryPrice=PositionGetDouble(POSITION_PRICE_OPEN);
   state.side=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1);
   state.currentStop=PositionGetDouble(POSITION_SL);
   state.currentBrokerTarget=PositionGetDouble(POSITION_TP);
   state.stopExists=(state.currentStop>0.0);
   const double profit=PositionGetDouble(POSITION_PROFIT)+
                       PositionGetDouble(POSITION_SWAP);
   const double current=(state.side>0 ? bid : ask);
   const int points=(point>0.0 ? (int)MathRound((state.side>0 ?
                       current-state.entryPrice :
                       state.entryPrice-current)/point) : 0);
   const string sideName=EmttPlanSideName(state.side);
   const string tfName=(state.tradeTimeframe!=PERIOD_CURRENT ?
                        EmttTradeManagerTfName(state.tradeTimeframe) :
                        EmttTradeManagerTfName(chartTimeframe));
   const int volumeDigits=EmttTradeVolumeDigits(
                           SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP));
   data.showLive=true;
   data.liveHeader=EmttGlyph(EMTT_G_DIAMOND)+" LIVE TRADE "+
                   EmttTradeDash()+" On "+tfName;
   data.ticket="Ticket: "+StringFormat("%I64u",ticket)+" | "+sideName+" "+
      DoubleToString(state.positionVolume,volumeDigits)+" lots @ "+ 
      DoubleToString(state.entryPrice,digits);
   data.floatingPL="Floating P/L: "+EmttTradeManagerMoney(profit)+" ("+
                    EmttTradeManagerSigned((double)points,0)+" pts)";
   data.floatingClr=(profit>=0.0 ? EMTT_CLR_BUY : EMTT_CLR_SELL);
   const int stopPoints=(point>0.0 && state.currentStop>0.0 ?
      (int)MathRound(MathAbs(current-state.currentStop)/point) : 0);
   data.liveSL="Live SL: "+(state.currentStop>0.0 ?
      DoubleToString(state.currentStop,digits) : "--")+" ("+
      (state.currentStop>0.0 ? IntegerToString(stopPoints) : "--")+
      " pts) | TP1: "+(state.tp1>0.0 ?
      DoubleToString(state.tp1,digits) :
      (state.currentBrokerTarget>0.0 ?
       DoubleToString(state.currentBrokerTarget,digits) : "--"))+
      " TP2: "+(state.tp2>0.0 ? DoubleToString(state.tp2,digits) : "--");
   const datetime now=(TimeTradeServer()>0 ? TimeTradeServer() : TimeCurrent());
   const datetime opened=(state.filledAt>0 ? state.filledAt :
                          (datetime)PositionGetInteger(POSITION_TIME));
   int minutes=(opened>0 ? (int)MathMax(0,(long)(now-opened)/60) : 0);
   int hours=minutes/60;
   minutes%=60;
   string age=StringFormat("%02d:%02d",hours,minutes);
   string duration=(state.expectedMinutes>0 ?
      EmttLearnDurationFromEstimate(state.expectedMinutes,
         (state.tradeTimeframe!=PERIOD_CURRENT ? state.tradeTimeframe :
                                                chartTimeframe)) : "--");
   StringReplace(duration," hours","h");
   StringReplace(duration," hour","h");
   StringReplace(duration," min","m");
   data.protect="Protect: "+EmttTradeProtectWord(state.stopExists,
      state.breakevenReached,state.trailMethod)+" | Age: "+age+" / "+duration;
   state.liveStatus="Signal active "+EmttTradeDash()+
                    " position open, managing.";

   // The approved panel rows show dollar amounts only for Emtt's own
   // position. Incompatible charts keep their required blank data fields.
   if(compatible && state.hasPlanContext)
     {
      const double tickSize=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
      double tickValue=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE);
      if(tickValue<=0.0)
         tickValue=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE_PROFIT);
      double entryMoney=0.0,stopMoney=0.0,targetMoney=0.0;
      EmttTradeMoneyRows(state.plannedEntry,state.plannedStop,
         state.plannedTarget,(state.side>0 ? ask : bid),
         state.positionVolume,tickSize,tickValue,
         entryMoney,stopMoney,targetMoney);
      const int entryPts=(point>0.0 ? (int)MathRound(MathAbs(
         (state.side>0 ? ask : bid)-state.plannedEntry)/point) : 0);
      const int stopDistance=(point>0.0 ? (int)MathRound(MathAbs(
         state.plannedEntry-state.plannedStop)/point) : 0);
      const int targetDistance=(point>0.0 ? (int)MathRound(MathAbs(
         state.plannedTarget-state.plannedEntry)/point) : 0);
      data.entry="Entry: "+DoubleToString(state.plannedEntry,digits)+" / "+
         EmttTradeManagerMoney(entryMoney)+" ("+IntegerToString(entryPts)+
         " pts away)";
      data.stopLoss="Stop Loss: "+DoubleToString(state.plannedStop,digits)+
         " / "+EmttTradeManagerMoney(stopMoney)+" ("+
         IntegerToString(stopDistance)+" pts)";
      data.takeProfit="Take Profit: "+
         DoubleToString(state.plannedTarget,digits)+" / "+
         EmttTradeManagerMoney(targetMoney)+" ("+
         IntegerToString(targetDistance)+" pts)";
     }
  }

#endif // EMTT_TRADEMANAGER_MQH
