//+------------------------------------------------------------------+
//|                                                       Emtt.mq5   |
//|                Emtt - MT5 Trading Expert Adviser                 |
//|                Phase 1: panel layout with dummy values           |
//|                Spec: Emtt.md | Author: Ham | Coder: Arena        |
//+------------------------------------------------------------------+
#property copyright   "Author: Ham | Coder: Arena"
#property link        ""
#property version     "1.00"
#property description "Emtt V1.0 - MT5 Trading Expert Adviser."
#property description "Phase 1: on-chart panel layout (Emtt.md sections 4-8) with dummy values."
#property description "Allowed chart timeframes: M5 / M15 / M30 only."

#include "../Include/Emtt/Emtt_Dashboard.mqh"

//--- Phase 1 demo panel mode: how the A/B switch is driven -----------
enum ENUM_EMTT_PANEL_MODE
  {
   EMTT_MODE_AUTO,      // Auto: LIVE block follows an Emtt magic-number position (rule 8)
   EMTT_MODE_PANEL_A,   // Panel A: order OPEN (dummy values)
   EMTT_MODE_PANEL_B    // Panel B: no order (dummy values)
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
//| Rule 1: money shown in the real account currency                  |
//+------------------------------------------------------------------+
string CurSign()
  {
   const string c=AccountInfoString(ACCOUNT_CURRENCY);
   if(c=="USD") return "$";
   if(c=="EUR") return EmttGlyph(0x20AC);
   if(c=="GBP") return EmttGlyph(0x00A3);
   if(c=="JPY") return EmttGlyph(0x00A5);
   if(c=="AUD") return "A$";
   if(c=="CAD") return "C$";
   if(c=="NZD") return "NZ$";
   return c+" ";
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
//| Panel A dummy data - order OPEN (spec section 5)                  |
//+------------------------------------------------------------------+
void FillPanelA(SEmttPanelData &d,const string cur,const string dash,int &dealing)
  {
   dealing=1;                                            // BUY demo -> dealing side is Ask
   d.regime="Regime: TRENDING (Bullish)";
   d.signal="SIGNAL: "+EmttGlyph(EMTT_G_BUY)+" BUY";
   d.signalClr=EMTT_CLR_BUY;
   d.signalSize=EMTT_FSIZE_SIG;
   d.confidence="Confidence: 85%";
   d.entry="Entry:        1.08450 / "+cur+"142.50   (90 pts away)";
   d.stopLoss="Stop Loss:    1.08280 / "+cur+"170.00   (170 pts)";
   d.takeProfit="Take Profit:  1.09120 / "+cur+"670.00   (670 pts)";
   d.riskReward="Risk:Reward:  1:3.9";
   d.session="Session: London | Expected Duration: ~2-4 hours";
   d.why="Supertrend bullish + OB support at 1.0845 + CVD rising (buyers dominant) + H1 agrees up";
   d.status="Signal active"+dash+"Price +"+cur+"44.00 toward TP1";
   d.showLive=true;
   d.liveHeader=EmttGlyph(EMTT_G_DIAMOND)+" LIVE TRADE"+dash+"On "+TfName(_Period);
   d.ticket="Ticket: 48217291 | BUY 0.50 lots @ 1.08450";
   d.floatingPL="Floating P/L: +"+cur+"44.00  (+88 pts)";
   d.floatingClr=EMTT_CLR_BUY;
   d.liveSL="Live SL: 1.08455 (83 pts) | TP1: 1.09120 TP2: 1.09450";
   d.protect="Protect: Breakeven | Age: 00:42 / ~2-4h";
  }

//+------------------------------------------------------------------+
//| Panel B dummy data - no order (spec section 5)                    |
//+------------------------------------------------------------------+
void FillPanelB(SEmttPanelData &d,const string cur,const string dash)
  {
   d.regime="Regime: RANGING";
   d.signal="SIGNAL: "+EmttGlyph(EMTT_G_PAUSE)+" WAIT";
   d.signalClr=EMTT_CLR_TEXT;                            // WAIT uses the soft colour
   d.signalSize=EMTT_FSIZE;
   d.confidence="Confidence: 48%";
   d.entry="Entry:        --      / "+cur+"0.00     (-- pts away)";
   d.stopLoss="Stop Loss:    --      / "+cur+"0.00     (-- pts)";
   d.takeProfit="Take Profit:  --      / "+cur+"0.00     (-- pts)";
   d.riskReward="Risk:Reward:  --";
   d.session="Session: London | Expected Duration: --";
   d.why="No agreement"+dash+"Supertrend flat, price mid-range";
   d.status="No trade"+dash+"confidence 48%, below threshold";
   d.showLive=false;
  }

//+------------------------------------------------------------------+
//| Build one full panel snapshot                                     |
//+------------------------------------------------------------------+
void FillPanel(SEmttPanelData &d)
  {
   const bool compatible=TfAllowed();
   const double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   const double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   int spreadPts=0;
   if(_Point>0)
      spreadPts=(int)MathRound((ask-bid)/_Point);
   const string cur=CurSign();
   const string dash=" "+EmttGlyph(EMTT_G_DASH)+" ";

   d.header=EmttHeaderText();
   d.signalClr=EMTT_CLR_TEXT;
   d.signalSize=EMTT_FSIZE;
   d.statusClr=EMTT_CLR_TEXT;
   d.floatingClr=EMTT_CLR_TEXT;
   d.showLive=false;

   int dealing=0;                                        // 0 none | 1 Ask (BUY) | 2 Bid (SELL)

   if(!compatible)
     {
      // rule 19: full panel, every data field blank, live Price Row,
      // red STATUS message; no signal and no new order on this TF
      d.regime="Regime: --";
      d.signal="SIGNAL: --";
      d.confidence="Confidence: --";
      d.entry="Entry:        --";
      d.stopLoss="Stop Loss:    --";
      d.takeProfit="Take Profit:  --";
      d.riskReward="Risk:Reward:  --";
      d.session="Session: -- | Expected Duration: --";
      d.why="--";
      d.status="Incompatible chart. Switch to M5/M15/M30.";
      d.statusClr=EMTT_CLR_SELL;                         // warning red (#EB6F6F)
     }
   else
     {
      bool live=(InpPanelMode==EMTT_MODE_PANEL_A);
      if(InpPanelMode==EMTT_MODE_AUTO)
         live=EmttOwnPositionOpen();
      if(live)
         FillPanelA(d,cur,dash,dealing);
      else
         FillPanelB(d,cur,dash);
     }

   // rule 2: realtime Price Row; arrow marks the dealing side
   string bidLbl="Bid: ";
   string askLbl="Ask: ";
   if(dealing==1)
      askLbl=EmttGlyph(EMTT_G_ARROW)+"Ask: ";
   if(dealing==2)
      bidLbl=EmttGlyph(EMTT_G_ARROW)+"Bid: ";
   d.priceRow=bidLbl+DoubleToString(bid,_Digits)+"  |  "
             +askLbl+DoubleToString(ask,_Digits)+"  |  "
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
