//+------------------------------------------------------------------+
//|                                                       Emtt.mq5   |
//|                Emtt - MT5 Trading Expert Adviser                 |
//|                Phase 1: panel layout only - labels, no values    |
//|                Spec: Emtt.md | Author: Ham | Coder: Arena        |
//+------------------------------------------------------------------+
#property copyright   "Author: Ham | Coder: Arena"
#property link        ""
#property version     "1.00"
#property description "Emtt V1.0 - MT5 Trading Expert Adviser."
#property description "Phase 1: on-chart panel layout (Emtt.md sections 4-8) - labels only, no dummy values."
#property description "Allowed chart timeframes: M5 / M15 / M30 only."

#include "../Include/Emtt/Emtt_Dashboard.mqh"

//--- Phase 1 demo panel mode: how the A/B switch is driven -----------
enum ENUM_EMTT_PANEL_MODE
  {
   EMTT_MODE_AUTO,      // Auto: LIVE block follows an Emtt magic-number position (rule 8)
   EMTT_MODE_PANEL_A,   // Panel A: layout with the LIVE TRADE block
   EMTT_MODE_PANEL_B    // Panel B: layout without the LIVE TRADE block
  };

input long                 InpMagicNumber=20251007;      // Magic number (rule 18)
input bool                 InpAutoTrading=true;          // Auto Trading ON/OFF (rule 9)
input ENUM_EMTT_PANEL_MODE InpPanelMode=EMTT_MODE_AUTO;  // Phase 1 demo panel switch

//+------------------------------------------------------------------+
//| Timeframe gate - rule 4d: M5 / M15 / M30 only                     |
//+------------------------------------------------------------------+
bool TfAllowed()
  {
   return(_Period==PERIOD_M5 || _Period==PERIOD_M15 || _Period==PERIOD_M30);
  }

//+------------------------------------------------------------------+
//| "PERIOD_M15" -> "M15"                                             |
//+------------------------------------------------------------------+
string TfName(const ENUM_TIMEFRAMES tf)
  {
   return StringSubstr(EnumToString(tf),7);
  }

//+------------------------------------------------------------------+
//| Header text - real symbol, real TF, Auto Trading word (rule 9)    |
//+------------------------------------------------------------------+
string EmttHeaderText()
  {
   return StringFormat("Emtt V1.0 | %s | TF: %s | Auto Trading: %s",
                       _Symbol,TfName(_Period),(InpAutoTrading?"ON":"OFF"));
  }

//+------------------------------------------------------------------+
//| Rule 8: find Emtt's own position by magic number                  |
//+------------------------------------------------------------------+
bool EmttOwnPositionOpen()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const string s=PositionGetSymbol(i);
      if(s=="")
         continue;
      if(s==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagicNumber)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Build one full panel snapshot.                                    |
//| Phase 1 is layout-only: every row shows its label and no value.   |
//| There is no dummy data anywhere - later phases fill real values.  |
//+------------------------------------------------------------------+
void FillPanel(SEmttPanelData &d)
  {
   const bool compatible=TfAllowed();
   const double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   const double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   int spreadPts=0;
   if(_Point>0)
      spreadPts=(int)MathRound((ask-bid)/_Point);

   d.header=EmttHeaderText();
   d.signalClr=EMTT_CLR_TEXT;
   d.signalSize=EMTT_FSIZE;
   d.statusClr=EMTT_CLR_TEXT;
   d.floatingClr=EMTT_CLR_TEXT;
   d.showLive=false;

   //--- row labels only - the values arrive with later phases
   d.regime="Regime:";
   d.signal="SIGNAL:";
   d.confidence="Confidence:";
   d.entry="Entry:";
   d.stopLoss="Stop Loss:";
   d.takeProfit="Take Profit:";
   d.riskReward="Risk:Reward:";
   d.session="Session:  |  Expected Duration:";
   d.why="";
   d.status="";

   if(!compatible)
     {
      // rule 19: same full panel, data blank, red STATUS message;
      // no signal and no new order on this timeframe
      d.status="Incompatible chart. Switch to M5/M15/M30.";
      d.statusClr=EMTT_CLR_SELL;                         // warning red (#EB6F6F)
     }
   else
     {
      bool live=(InpPanelMode==EMTT_MODE_PANEL_A);
      if(InpPanelMode==EMTT_MODE_AUTO)
         live=EmttOwnPositionOpen();
      if(live)
        {
         // LIVE TRADE block labels (rule 8)
         d.showLive=true;
         d.liveHeader=EmttGlyph(EMTT_G_DIAMOND)+" LIVE TRADE";
         d.ticket="Ticket:";
         d.floatingPL="Floating P/L:";
         d.liveSL="Live SL:";
         d.protect="Protect:";
        }
     }

   // rule 2: realtime Price Row - live terminal data, never dummy
   d.priceRow="Bid: "+DoubleToString(bid,_Digits)+"  |  "
             +"Ask: "+DoubleToString(ask,_Digits)+"  |  "
             +IntegerToString(spreadPts)+" pts";
  }

//+------------------------------------------------------------------+
//| Render one snapshot + push to the chart                            |
//+------------------------------------------------------------------+
void UpdatePanel()
  {
   SEmttPanelData d;
   FillPanel(d);
   EmttDashboardRender(d);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| Expert initialisation                                              |
//+------------------------------------------------------------------+
int OnInit()
  {
   EmttDashboardInit(EmttHeaderText());
   ChartSetInteger(0,CHART_EVENT_MOUSE_MOVE,true);       // needed for dragging
   EventSetTimer(1);                                     // rule 15: 1-second refresh
   UpdatePanel();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialisation - clean removal of all objects            |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ChartSetInteger(0,CHART_EVENT_MOUSE_MOVE,false);
   EmttDashboardShutdown();
  }

//+------------------------------------------------------------------+
//| Ticks: Price Row / Floating P/L must match the terminal (rule 15) |
//+------------------------------------------------------------------+
void OnTick()
  {
   UpdatePanel();
  }

//+------------------------------------------------------------------+
//| Timer: full panel refresh every second (rule 15)                  |
//+------------------------------------------------------------------+
void OnTimer()
  {
   UpdatePanel();
  }

//+------------------------------------------------------------------+
//| Chart events: panel dragging (rule 14)                            |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   EmttDashboardChartEvent(id,lparam,dparam,sparam);
  }
//+------------------------------------------------------------------+
