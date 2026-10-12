//+------------------------------------------------------------------+
//|                                             Emtt_Dashboard.mqh   |
//|                   Emtt - Phase 1: on-chart panel layout          |
//| Panel revamp 2026-10-11 (author): WHY removed, STATUS 1 line,   |
//| Summary Today + All-Time, dynamic width, no cap. Rules 11-13 of  |
//| section 6 as written are superseded for these rows.              |
//|                   Spec: Emtt.md sections 4-7                     |
//|                   Author: Ham | Coder: Arena                     |
//+------------------------------------------------------------------+
#property copyright "Author: Ham | Coder: Arena"

#ifndef EMTT_DASHBOARD_MQH
#define EMTT_DASHBOARD_MQH

//--- palette - Emtt.md section 6 colour table -----------------------
#define EMTT_CLR_BG     C'40,40,40'      // panel background        #282828
#define EMTT_CLR_HDR    C'51,51,51'      // header strip background #333333
#define EMTT_CLR_LINE   C'74,74,74'      // border + separators     #4A4A4A
#define EMTT_CLR_TEXT   C'200,200,200'   // all soft text / WAIT    #C8C8C8
#define EMTT_CLR_BUY    C'111,207,151'   // BUY / profit            #6FCF97
#define EMTT_CLR_SELL   C'235,111,111'   // SELL / loss / warning   #EB6F6F
// Phase 11 (28.2): the two intermediate signal shades, blends of the
// signal colour toward the soft text grey C'200,200,200'.
#define EMTT_CLR_BUY_LOW     C'156,204,176'   // Low BUY (50%)     #9CCCB0
#define EMTT_CLR_SELL_LOW    C'218,156,156'   // Low SELL (50%)    #DA9C9C
#define EMTT_CLR_BUY_NORMAL  C'133,205,163'   // Normal BUY (25%)  #85CDA3
#define EMTT_CLR_SELL_NORMAL C'226,133,133'   // Normal SELL (25%) #E28585

//--- typography & geometry - rules 13, 16 ---------------------------
#define EMTT_FONT       "Segoe UI"
#define EMTT_FONT_BOLD  "Segoe UI Bold"  // Phase 11: High-confidence SIGNAL
#define EMTT_FSIZE      12               // every row
#define EMTT_FSIZE_SIG  14               // SIGNAL row when BUY/SELL
#define EMTT_PREFIX     "Emtt_"
#define EMTT_PAD_X      12
#define EMTT_PAD_BOTTOM 8
#define EMTT_HDR_H      26               // header strip height
#define EMTT_ROW_H      20               // normal text row height
#define EMTT_SIG_H      24               // SIGNAL row height (size 14)
#define EMTT_SEP_H      9                // separator slot height
#define EMTT_PRICE_GAP  4                // gap under the header strip

//--- unicode glyphs, built at runtime so the source stays pure ASCII
#define EMTT_G_BUY      0x25B2           // black up-pointing triangle
#define EMTT_G_SELL     0x25BC           // black down-pointing triangle
#define EMTT_G_PAUSE    0x23F8           // pause symbol
#define EMTT_G_DIAMOND  0x25C6           // black diamond
#define EMTT_G_ARROW    0x25BA           // right-pointing triangle (dealing marker)
#define EMTT_G_DASH     0x2014           // em dash

//+------------------------------------------------------------------+
//| One glyph from a unicode code point                               |
//+------------------------------------------------------------------+
string EmttGlyph(const int code)
  {
   ushort a[1];
   a[0]=(ushort)code;
   return ShortArrayToString(a,0,1);
  }

//+------------------------------------------------------------------+
//| Everything the panel needs from the EA for one render pass.       |
//| Phase 1 is layout-only: labels with no values. Later phases fill  |
//| real content here without touching the renderer.                  |
//+------------------------------------------------------------------+
struct SEmttPanelData
  {
   string header;      // "Emtt V1.0 | SYM | TF: M15 | Auto Trading: ON"
   string priceRow;    // rule 2: live Bid / Ask / Spread + dealing marker
   string regime;      // Row 1  (full text incl. "Regime: ")
   string signal;      // Row 2  (full text incl. "SIGNAL: ")
   color  signalClr;   // rule 17: only SIGNAL and Floating P/L are coloured
   int    signalSize;  // rule 16: 14 for BUY/SELL, else 12
   bool   signalBold;  // Phase 11 (28.2): bold for the High tier only
   string confidence;  // Row 3
   string entry;       // Row 4
   string stopLoss;    // Row 5
   string takeProfit;  // Row 6
   string riskReward;  // Row 7
   string session;     // Row 8
   string why;         // deprecated (WHY row removed 2026-10-11): kept so
                       // FillPanel still compiles; the renderer ignores it
   string status;      // STATUS body, shown as one full line (no wrap)
   color  statusClr;   // soft, except red for the incompatible-TF message
   string summaryToday;    // Summary row 1 (full text incl. "Today: ")
   string summaryAllTime;  // Summary row 2 (full text incl. "All Time: ")
   bool   showLive;    // rule 8: LIVE TRADE block present
   string liveHeader;  // "diamond LIVE TRADE - On M15"
   string ticket;      // Row 11
   string floatingPL;  // Row 12
   color  floatingClr; // profit green / loss red
   string liveSL;      // Row 13
   string protect;     // Row 14
  };

//--- panel state -----------------------------------------------------
int    g_panelWidth=0;          // dynamic width, recomputed every render
int    g_panelX=10;             // top-left anchor (rule 14)
int    g_panelY=10;
bool   g_dragging=false;
int    g_grabDX=0;
int    g_grabDY=0;
int    g_mouseX=0;
int    g_mouseY=0;

//--- object pools ----------------------------------------------------
string g_labelNames[];
int    g_labelCount=0;
string g_rectNames[];
int    g_rectCount=0;

//--- text measurement cache -------------------------------------------
string g_mKeys[];
int    g_mVals[];
int    g_mCount=0;

//--- row build buffers -------------------------------------------------
string b_text[];
color  b_clr[];
int    b_size[];
int    b_kind[];                // 0=header text, 1=row text, 2=separator
bool   b_bold[];                // Phase 11: bold face for this row
int    b_n=0;

//+------------------------------------------------------------------+
//| Estimated pixel height of a font size                             |
//+------------------------------------------------------------------+
int EmttFontH(const int size)
  {
   return (int)MathRound(size*16.0/12.0);
  }

//+------------------------------------------------------------------+
//| Measure a text's pixel width (cached, measured via a hidden       |
//| label so wrapping matches the real font metrics)                  |
//+------------------------------------------------------------------+
double EmttTextWidth(const string text,const int size,const bool bold=false)
  {
// Dynamic width measures every render, so the cache is bounded: a quiet
// reset keeps memory flat on tick-heavy symbols with ever-new prices.
   if(g_mCount>=5000)
     {
      ArrayFree(g_mKeys);
      ArrayFree(g_mVals);
      g_mCount=0;
     }
   const string key=(bold ? "B" : "")+IntegerToString(size)+"|"+text;
   for(int i=0;i<g_mCount;i++)
      if(g_mKeys[i]==key)
         return g_mVals[i];
   const string name=EMTT_PREFIX+"msr";
   if(ObjectFind(0,name)<0)
     {
      ObjectCreate(0,name,OBJ_LABEL,0,0,0);
      ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
      ObjectSetInteger(0,name,OBJPROP_XDISTANCE,-10000);
      ObjectSetInteger(0,name,OBJPROP_YDISTANCE,-10000);
     }
   ObjectSetString(0,name,OBJPROP_FONT,(bold ? EMTT_FONT_BOLD : EMTT_FONT));
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   ChartRedraw();
   int w=(int)ObjectGetInteger(0,name,OBJPROP_XSIZE);
   if(w<=0)                                  // defensive fallback estimate
      w=(int)MathCeil(StringLen(text)*size*0.62);
   ArrayResize(g_mKeys,g_mCount+1);
   ArrayResize(g_mVals,g_mCount+1);
   g_mKeys[g_mCount]=key;
   g_mVals[g_mCount]=w;
   g_mCount++;
   return w;
  }

//+------------------------------------------------------------------+
//| Initialise the dashboard: background object + first width guess.  |
//| The width is dynamic (author direction 2026-10-11): every render |
//| remeasures the visible rows and fits the longest one, growing    |
//| and shrinking with no cap. Init only seeds a sane width so the   |
//| very first paint has one.                                         |
//+------------------------------------------------------------------+
void EmttDashboardInit(const string headerSample)
  {
   const string bg=EMTT_PREFIX+"bg";
   if(ObjectFind(0,bg)<0)
      ObjectCreate(0,bg,OBJ_RECTANGLE_LABEL,0,0,0);

   g_panelWidth=(int)EmttTextWidth(headerSample,EMTT_FSIZE)+2*EMTT_PAD_X;
   if(g_panelWidth<2*EMTT_PAD_X+1)
      g_panelWidth=2*EMTT_PAD_X+1;
  }

//+------------------------------------------------------------------+
//| Row build helpers --------------------------------------------------|
//+------------------------------------------------------------------+
void BClear()
  {
   b_n=0;
  }

void BAdd(const string t,const color c,const int sz,const int k,
          const bool bold=false)
  {
   ArrayResize(b_text,b_n+1);
   ArrayResize(b_clr,b_n+1);
   ArrayResize(b_size,b_n+1);
   ArrayResize(b_kind,b_n+1);
   ArrayResize(b_bold,b_n+1);
   b_text[b_n]=t;
   b_clr[b_n]=c;
   b_size[b_n]=sz;
   b_kind[b_n]=k;
   b_bold[b_n]=bold;
   b_n++;
  }

void BSep()
  {
   BAdd("",EMTT_CLR_LINE,0,2);
  }

// NOTE (2026-10-11): wrapping was removed with the WHY row. STATUS is
// one full line and the width is dynamic, so no wrapper is needed.

//+------------------------------------------------------------------+
//| Object pool helpers ------------------------------------------------|
//+------------------------------------------------------------------+
string EmttLabelSlot(const int i)
  {
   if(i<g_labelCount)
      return g_labelNames[i];
   const string name=StringFormat("%st%02d",EMTT_PREFIX,g_labelCount);
   ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ArrayResize(g_labelNames,g_labelCount+1);
   g_labelNames[g_labelCount]=name;
   g_labelCount++;
   return name;
  }

string EmttRectSlot(const int i)
  {
   if(i<g_rectCount)
      return g_rectNames[i];
   const string name=StringFormat("%sr%02d",EMTT_PREFIX,g_rectCount);
   ObjectCreate(0,name,OBJ_RECTANGLE_LABEL,0,0,0);
   ArrayResize(g_rectNames,g_rectCount+1);
   g_rectNames[g_rectCount]=name;
   g_rectCount++;
   return name;
  }

void ApplyLabel(const string name,const int x,const int y,const string text,
                const color clr,const int size,const bool bold=false)
  {
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetString(0,name,OBJPROP_FONT,(bold ? EMTT_FONT_BOLD : EMTT_FONT));
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,true);
   ObjectSetInteger(0,name,OBJPROP_SELECTED,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,false);
   ObjectSetInteger(0,name,OBJPROP_TIMEFRAMES,OBJ_ALL_PERIODS);
  }

void ApplyRect(const string name,const int x,const int y,const int w,const int h,
               const color fill,const color border,const bool framed=false)
  {
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,fill);
   ObjectSetInteger(0,name,OBJPROP_BORDER_TYPE,BORDER_FLAT);
   ObjectSetInteger(0,name,OBJPROP_BORDER_COLOR,framed?border:fill);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,true);
   ObjectSetInteger(0,name,OBJPROP_SELECTED,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,false);
   ObjectSetInteger(0,name,OBJPROP_TIMEFRAMES,OBJ_ALL_PERIODS);
  }

void HideExtras(const int usedLabels,const int usedRects)
  {
   for(int i=usedLabels;i<g_labelCount;i++)
      ObjectSetInteger(0,g_labelNames[i],OBJPROP_TIMEFRAMES,OBJ_NO_PERIODS);
   for(int i=usedRects;i<g_rectCount;i++)
      ObjectSetInteger(0,g_rectNames[i],OBJPROP_TIMEFRAMES,OBJ_NO_PERIODS);
  }

//+------------------------------------------------------------------+
//| Lay the built rows out into chart objects                         |
//+------------------------------------------------------------------+
void EmttLayout()
  {
   const string bg=EMTT_PREFIX+"bg";
   int li=0,ri=0;
   int y=g_panelY;

   // header strip + header text
   string n=EmttRectSlot(ri++);
   ApplyRect(n,g_panelX,y,g_panelWidth,EMTT_HDR_H,EMTT_CLR_HDR,EMTT_CLR_HDR);
   n=EmttLabelSlot(li++);
   ApplyLabel(n,g_panelX+EMTT_PAD_X,y+(EMTT_HDR_H-EmttFontH(EMTT_FSIZE))/2,
              b_text[0],b_clr[0],b_size[0]);
   y+=EMTT_HDR_H+EMTT_PRICE_GAP;

   for(int i=1;i<b_n;i++)
     {
      if(b_kind[i]==2)                       // separator line
        {
         n=EmttRectSlot(ri++);
         ApplyRect(n,g_panelX,y+EMTT_SEP_H/2,g_panelWidth,1,EMTT_CLR_LINE,EMTT_CLR_LINE);
         y+=EMTT_SEP_H;
        }
      else                                   // text row
        {
         const int h=(b_size[i]>=EMTT_FSIZE_SIG)?EMTT_SIG_H:EMTT_ROW_H;
         n=EmttLabelSlot(li++);
         ApplyLabel(n,g_panelX+EMTT_PAD_X,y+(h-EmttFontH(b_size[i]))/2,
                    b_text[i],b_clr[i],b_size[i],b_bold[i]);
         y+=h;
        }
     }

   const int totalH=y-g_panelY+EMTT_PAD_BOTTOM;
   ApplyRect(bg,g_panelX,g_panelY,g_panelWidth,totalH,EMTT_CLR_BG,EMTT_CLR_LINE,true);
   HideExtras(li,ri);
  }

//+------------------------------------------------------------------+
//| Render the full panel from one data snapshot. WHY is gone        |
//| (2026-10-11): STATUS is one full line and Summary adds two rows. |
//| The width is dynamic: the longest visible row sets it, with no   |
//| minimum and no cap.                                               |
//+------------------------------------------------------------------+
void EmttDashboardRender(const SEmttPanelData &d)
  {
   BClear();
   BAdd(d.header,EMTT_CLR_TEXT,EMTT_FSIZE,0);
   BAdd(d.priceRow,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BSep();
   BAdd(d.regime,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BSep();
   BAdd(d.signal,d.signalClr,d.signalSize,1,d.signalBold);
   BAdd(d.confidence,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BSep();
   BAdd(d.entry,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BAdd(d.stopLoss,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BAdd(d.takeProfit,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BAdd(d.riskReward,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BAdd(d.session,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BSep();
   BAdd("STATUS: "+d.status,d.statusClr,EMTT_FSIZE,1);
   BSep();
   BAdd(d.summaryToday,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   BAdd(d.summaryAllTime,EMTT_CLR_TEXT,EMTT_FSIZE,1);
   if(d.showLive)                            // rule 8: block only with an open Emtt trade
     {
      BSep();
      BAdd(d.liveHeader,EMTT_CLR_TEXT,EMTT_FSIZE,1);
      BAdd(d.ticket,EMTT_CLR_TEXT,EMTT_FSIZE,1);
      BAdd(d.floatingPL,d.floatingClr,EMTT_FSIZE,1);
      BAdd(d.liveSL,EMTT_CLR_TEXT,EMTT_FSIZE,1);
      BAdd(d.protect,EMTT_CLR_TEXT,EMTT_FSIZE,1);
     }
// Dynamic width: fit the longest visible row (text rows only,
// separators carry no text). No minimum, no cap.
   int maxw=0;
   for(int i=0;i<b_n;i++)
     {
      if(b_kind[i]==2)
         continue;
      maxw=MathMax(maxw,(int)EmttTextWidth(b_text[i],b_size[i],b_bold[i]));
     }
   g_panelWidth=maxw+2*EMTT_PAD_X;
   if(g_panelWidth<2*EMTT_PAD_X+1)
      g_panelWidth=2*EMTT_PAD_X+1;
   EmttLayout();
  }

//+------------------------------------------------------------------+
//| Dragging (rule 14): move every panel object by a delta            |
//+------------------------------------------------------------------+
void EmttMoveObj(const string name,const int dx,const int dy)
  {
   if(ObjectFind(0,name)<0)
      return;
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,(int)ObjectGetInteger(0,name,OBJPROP_XDISTANCE)+dx);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,(int)ObjectGetInteger(0,name,OBJPROP_YDISTANCE)+dy);
  }

void EmttDashboardMove(const int dx,const int dy)
  {
   if(dx==0 && dy==0)
      return;
   EmttMoveObj(EMTT_PREFIX+"bg",dx,dy);
   for(int i=0;i<g_labelCount;i++)
      EmttMoveObj(g_labelNames[i],dx,dy);
   for(int i=0;i<g_rectCount;i++)
      EmttMoveObj(g_rectNames[i],dx,dy);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| Chart events: track the mouse, drag any Emtt object to move the   |
//| whole panel.                                                      |
//+------------------------------------------------------------------+
void EmttDashboardChartEvent(const int id,const long &lparam,
                             const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_MOUSE_MOVE)
     {
      g_mouseX=(int)lparam;
      g_mouseY=(int)dparam;
      if(StringToInteger(sparam)==0)         // no mouse button held: drag over
         g_dragging=false;
      return;
     }
   if(id==CHARTEVENT_OBJECT_DRAG)
     {
      if(StringFind(sparam,EMTT_PREFIX)!=0)
         return;
      if(sparam==EMTT_PREFIX+"msr")
         return;
      if(!g_dragging)
        {
         g_dragging=true;
         g_grabDX=g_mouseX-g_panelX;
         g_grabDY=g_mouseY-g_panelY;
        }
      const int nx=g_mouseX-g_grabDX;
      const int ny=g_mouseY-g_grabDY;
      if(nx!=g_panelX || ny!=g_panelY)
        {
         EmttDashboardMove(nx-g_panelX,ny-g_panelY);
         g_panelX=nx;
         g_panelY=ny;
        }
      return;
     }
  }

//+------------------------------------------------------------------+
//| Remove every Emtt object cleanly (Done-When item 4)               |
//+------------------------------------------------------------------+
void EmttDashboardShutdown()
  {
   ObjectsDeleteAll(0,EMTT_PREFIX);
   g_labelCount=0;
   g_rectCount=0;
   ArrayFree(g_labelNames);
   ArrayFree(g_rectNames);
   ChartRedraw();
  }

#endif // EMTT_DASHBOARD_MQH
