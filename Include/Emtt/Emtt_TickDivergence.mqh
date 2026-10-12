//+------------------------------------------------------------------+
//|                                        Emtt_TickDivergence.mqh   |
//| Phase 10: tick-level CVD divergence detection (Emtt.md 25)        |
//| Pure logic: no order call, no chart object, no file, no handle,   |
//| no history copy and no clock read beyond the tick's own time.     |
//| The trade manager feeds one tick at a time; every step is O(1) on |
//| a fixed 300-slot ring that is never grown. ASCII source only.     |
//| Divergence only ever tightens the trailing stop (25.2 rule 1-2).  |
//+------------------------------------------------------------------+
#ifndef EMTT_TICKDIVERGENCE_MQH
#define EMTT_TICKDIVERGENCE_MQH

//--- 25.12 fixed standing constants (rows p - z) --------------------
#define EMTT_DIV_TICKS 300               // p. ring-buffer size (ticks)
#define EMTT_DIV_MAX_WINDOW_MIN 15       // q. max window time (minutes)
#define EMTT_DIV_SWING_STRENGTH 5        // r. tick swing strength each side
#define EMTT_DIV_DENSITY_MIN 60          // density window (seconds)
#define EMTT_DIV_DENSITY_MIN_TICKS 10    // s. active threshold per 60 s
#define EMTT_DIV_DENSITY_RECOVER 20      // t. recovery threshold per 60 s
#define EMTT_DIV_WARMUP_TICKS 50         // u. warmup ticks after open
#define EMTT_DIV_PRICE_LEAST_ATR 0.10    // v. minimum price leg (x entry ATR)
#define EMTT_DIV_STRONG_RATIO 0.5        // w. strong CVD ratio (<= half)
#define EMTT_DIV_CONFIRM_TICKS 3         // x. confirmation ticks
#define EMTT_DIV_WEAK_MULT 0.8           // y. weak divergence multiplier
#define EMTT_DIV_STRONG_MULT 0.5         // z. strong divergence multiplier

enum EEmttDivLevel
  {
   EMTT_DIV_LEVEL_NONE=0,
   EMTT_DIV_LEVEL_WEAK=1,
   EMTT_DIV_LEVEL_STRONG=2
  };

//+------------------------------------------------------------------+
//| One detection session = one Emtt position. The ring arrays are   |
//| fixed-size members, allocated once with the state itself.        |
//+------------------------------------------------------------------+
struct SEmttTickDivergenceState
  {
   bool   armed;          // a position is being watched
   ulong  ticket;         // the watched position ticket
   int    side;           // +1 BUY / -1 SELL
   int    digits;         // price digits for the journal
   //--- the 300-slot ring (25.4 / 25.5); slot = sequence % 300
   long   msc[EMTT_DIV_TICKS];
   double mid[EMTT_DIV_TICKS];
   int    sign[EMTT_DIV_TICKS];
   int    cvd[EMTT_DIV_TICKS];
   long   runStart[EMTT_DIV_TICKS];  // first sequence of the equal-mid run
   long   total;          // ticks accepted this session (next sequence)
   long   oldest;         // sequence of the oldest tick still in the window
   long   densityStart;   // sequence of the oldest tick in the last 60 s
   int    cvdNow;         // rolling tick-CVD over the window
   int    cvdAbs;         // rolling sum of absolute tick signs
   int    density;        // ticks in the last 60 s
   //--- previous quote for the tick sign (25.3)
   bool   hasPrev;
   double prevBid;
   double prevAsk;
   long   lastMsc;
   //--- quality gate (25.6)
   bool   warm;
   bool   sparse;
   bool   sparseJournaled;
   bool   recoverJournaled;
   bool   breakeven;      // last breakeven flag fed by the manager
   double atr;            // the trade's frozen entry ATR
   //--- leg tracking (25.5): two newest trade-direction swing peaks
   bool   has0;
   double pricePeak0;
   int    cvdAtPricePeak0;
   long   seq0;
   bool   has1;
   double pricePeak1;
   int    cvdAtPricePeak1;
   long   seq1;
   bool   pullback;       // an opposite swing confirmed after peak 1
   //--- divergence state (25.7)
   int    level;          // EEmttDivLevel
   int    weakHeld;       // consecutive ticks a weak reading held
   int    strongHeld;     // consecutive ticks a strong reading held
  };

int EmttTickDivSlot(const long sequence)
  {
   return (int)(sequence%EMTT_DIV_TICKS);
  }

string EmttTickDivSideName(const int side)
  {
   return (side>0 ? "BUY" : "SELL");
  }

string EmttTickDivBarText(const long timeMsc)
  {
   return TimeToString((datetime)(timeMsc/1000),TIME_DATE|TIME_MINUTES);
  }

string EmttTickDivTickText(const long timeMsc)
  {
   return TimeToString((datetime)(timeMsc/1000),TIME_DATE|TIME_SECONDS);
  }

// Clears the two tracked legs and the divergence reading only.
void EmttTickDivClearLegs(SEmttTickDivergenceState &state)
  {
   state.has0=false;
   state.pricePeak0=0.0;
   state.cvdAtPricePeak0=0;
   state.seq0=-1;
   state.has1=false;
   state.pricePeak1=0.0;
   state.cvdAtPricePeak1=0;
   state.seq1=-1;
   state.pullback=false;
   state.level=EMTT_DIV_LEVEL_NONE;
   state.weakHeld=0;
   state.strongHeld=0;
  }

// 25.2 rule 11: everything empties when no Emtt position is open.
void EmttTickDivReset(SEmttTickDivergenceState &state)
  {
   state.armed=false;
   state.ticket=0;
   state.side=0;
   state.digits=5;
   for(int i=0;i<EMTT_DIV_TICKS;i++)
     {
      state.msc[i]=0;
      state.mid[i]=0.0;
      state.sign[i]=0;
      state.cvd[i]=0;
      state.runStart[i]=0;
     }
   state.total=0;
   state.oldest=0;
   state.densityStart=0;
   state.cvdNow=0;
   state.cvdAbs=0;
   state.density=0;
   state.hasPrev=false;
   state.prevBid=0.0;
   state.prevAsk=0.0;
   state.lastMsc=0;
   state.warm=false;
   state.sparse=false;
   state.sparseJournaled=false;
   state.recoverJournaled=false;
   state.breakeven=false;
   state.atr=0.0;
   EmttTickDivClearLegs(state);
  }

// A new position (opened or adopted) always starts a fresh session with
// its own warmup; nothing is carried over from an earlier trade.
void EmttTickDivArm(SEmttTickDivergenceState &state,const ulong ticket,
                    const int side,const int digits)
  {
   EmttTickDivReset(state);
   state.armed=(ticket>0 && (side==1 || side==-1));
   state.ticket=(state.armed ? ticket : 0);
   state.side=(state.armed ? side : 0);
   state.digits=(digits>0 ? digits : 5);
  }

//--- 25.3 the tick sign ----------------------------------------------
int EmttTickDivSign(const double prevBid,const double prevAsk,
                    const double bid,const double ask)
  {
   const bool askUp=(ask>prevAsk);
   const bool askDown=(ask<prevAsk);
   const bool bidUp=(bid>prevBid);
   const bool bidDown=(bid<prevBid);
   // Bid and Ask moving in opposite directions is a spread change.
   if((askUp && bidDown) || (askDown && bidUp))
      return 0;
   if(askUp || (bidUp && ask>=prevAsk))
      return 1;
   if(bidDown || (askDown && bid<=prevBid))
      return -1;
   return 0;
  }

double EmttTickDivLevelMultiplier(const int level)
  {
   if(level==EMTT_DIV_LEVEL_STRONG)
      return EMTT_DIV_STRONG_MULT;
   if(level==EMTT_DIV_LEVEL_WEAK)
      return EMTT_DIV_WEAK_MULT;
   return 1.0;
  }

// Detection runs only post-breakeven, after warmup, on a dense feed.
bool EmttTickDivActive(const SEmttTickDivergenceState &state)
  {
   return (state.armed && state.breakeven && state.warm && !state.sparse);
  }

// 25.8: 1.0 whenever detection is inactive or shows no divergence.
double EmttTickDivMultiplier(const SEmttTickDivergenceState &state)
  {
   if(!EmttTickDivActive(state))
      return 1.0;
   return EmttTickDivLevelMultiplier(state.level);
  }

// 25.10: the STATUS line that replaces the generic trailing line for a
// divergence-driven trailing update only.
string EmttTickDivTrailStatus(const int level)
  {
   if(level==EMTT_DIV_LEVEL_STRONG)
      return "Trailing \x2014 momentum exhausted, tightening trail.";
   if(level==EMTT_DIV_LEVEL_WEAK)
      return "Trailing \x2014 momentum fading, tightening trail.";
   return "";
  }

//--- 25.11 journal lines (built here, printed only on state changes) ---
string EmttTickDivActiveLine(const int side,const long timeMsc)
  {
   return "Emtt | Tick divergence active | "+EmttTickDivSideName(side)+
          " | warmup "+IntegerToString(EMTT_DIV_WARMUP_TICKS)+
          " ticks complete | bar "+EmttTickDivBarText(timeMsc);
  }

string EmttTickDivInactiveLine(const int density,const long timeMsc)
  {
   return "Emtt | Tick divergence inactive | sparse feed ("+
          IntegerToString(density)+" ticks/min) | bar "+
          EmttTickDivBarText(timeMsc);
  }

string EmttTickDivRecoveredLine(const int density,const long timeMsc)
  {
   return "Emtt | Tick divergence recovered | "+IntegerToString(density)+
          " ticks/min | bar "+EmttTickDivBarText(timeMsc);
  }

string EmttTickDivLevelLine(const SEmttTickDivergenceState &state,
                            const int level,const long timeMsc)
  {
   const bool strong=(level==EMTT_DIV_LEVEL_STRONG);
   return "Emtt | Divergence "+(strong ? "strong" : "weak")+" | "+
          EmttTickDivSideName(state.side)+" | new "+
          (state.side>0 ? "high " : "low ")+
          DoubleToString(state.pricePeak1,state.digits)+", CVD "+
          (strong ? "exhausted" : "fading")+" (cvd "+
          IntegerToString(state.cvdAtPricePeak1)+" vs "+
          IntegerToString(state.cvdAtPricePeak0)+") | trail "+
          DoubleToString(EmttTickDivLevelMultiplier(level),1)+"x | tick "+
          EmttTickDivTickText(timeMsc);
  }

string EmttTickDivResetLine(const int side,const string reason,
                            const long timeMsc)
  {
   return "Emtt | Divergence reset | "+EmttTickDivSideName(side)+" | "+
          reason+" | tick "+EmttTickDivTickText(timeMsc);
  }

// A latched divergence returns to none only through a reset (25.7).
void EmttTickDivResetLeg(SEmttTickDivergenceState &state,
                         const string reason,const bool writeJournal)
  {
   const bool latched=(state.level!=EMTT_DIV_LEVEL_NONE);
   state.level=EMTT_DIV_LEVEL_NONE;
   state.weakHeld=0;
   state.strongHeld=0;
   if(latched && writeJournal)
      Print(EmttTickDivResetLine(state.side,reason,state.lastMsc));
  }

// 25.7: a trailing stop move gives the next leg fresh eyes.
void EmttTickDivOnStopMoved(SEmttTickDivergenceState &state,
                            const bool writeJournal)
  {
   if(!state.armed)
      return;
   const bool latched=(state.level!=EMTT_DIV_LEVEL_NONE);
   EmttTickDivResetLeg(state,"stop moved",writeJournal);
   if(latched)
     {
      state.has0=false;
      state.has1=false;
      state.pullback=false;
     }
  }

// A confirmed trade-direction peak (a swing high for a BUY).
void EmttTickDivOnPeak(SEmttTickDivergenceState &state,const long sequence,
                       const double price,const int cvdValue,
                       const bool writeJournal)
  {
   if(state.has1 && state.pullback && state.level!=EMTT_DIV_LEVEL_NONE)
     {
      // The latched divergence resolved into a healthy pullback and price
      // resumed: the comparison restarts with fresh legs.
      EmttTickDivResetLeg(state,"fresh leg after pullback",writeJournal);
      state.has1=false;
     }
   if(state.has1)
     {
      state.has0=true;
      state.pricePeak0=state.pricePeak1;
      state.cvdAtPricePeak0=state.cvdAtPricePeak1;
      state.seq0=state.seq1;
     }
   else
      state.has0=false;
   state.has1=true;
   state.pricePeak1=price;
   state.cvdAtPricePeak1=cvdValue;
   state.seq1=sequence;
   state.pullback=false;
  }

// 25.5: incremental tick-swing detection. The newest member of an equal
// mid-price run that formed STRENGTH ticks ago is a swing when the
// STRENGTH ticks after it and the STRENGTH ticks before the run are all
// strictly lower (a high) or strictly higher (a low). A plateau resolves
// to one pivot at its oldest member, mirroring 13.3. Bounded work.
void EmttTickDivDetectSwing(SEmttTickDivergenceState &state,
                            const bool writeJournal)
  {
   const long newest=state.total-1-EMTT_DIV_SWING_STRENGTH;
   if(newest<state.oldest)
      return;
   const int newestSlot=EmttTickDivSlot(newest);
   const long first=state.runStart[newestSlot];
   if(first-EMTT_DIV_SWING_STRENGTH<state.oldest)
      return;
   const double price=state.mid[newestSlot];
   bool isHigh=true;
   bool isLow=true;
   for(int k=1;k<=EMTT_DIV_SWING_STRENGTH;k++)
     {
      const double after=state.mid[EmttTickDivSlot(newest+k)];
      const double before=state.mid[EmttTickDivSlot(first-k)];
      if(!(after<price && before<price))
         isHigh=false;
      if(!(after>price && before>price))
         isLow=false;
      if(!isHigh && !isLow)
         return;
     }
   const int pivotSide=(isHigh ? 1 : -1);
   if(pivotSide==state.side)
      EmttTickDivOnPeak(state,first,price,state.cvd[EmttTickDivSlot(first)],
                        writeJournal);
   else if(state.has1 && first>state.seq1)
      state.pullback=true;
  }

// Drops the oldest tick from the window and both running sums.
void EmttTickDivPop(SEmttTickDivergenceState &state)
  {
   if(state.oldest>=state.total)
      return;
   const int slot=EmttTickDivSlot(state.oldest);
   state.cvdNow-=state.sign[slot];
   state.cvdAbs-=(state.sign[slot]!=0 ? 1 : 0);
   state.oldest++;
  }

//+------------------------------------------------------------------+
//| 25.3 - 25.7: one tick. atr is the trade's frozen entry ATR and    |
//| breakeven the manager's post-breakeven flag. Returns true when    |
//| the tick was accepted (duplicates and out-of-order ticks are      |
//| ignored so the same stream always gives the same state).          |
//+------------------------------------------------------------------+
bool EmttTickDivFeed(SEmttTickDivergenceState &state,const double bid,
                     const double ask,const long timeMsc,const double atr,
                     const bool breakeven,const bool writeJournal)
  {
   if(!state.armed || bid<=0.0 || ask<=0.0 || timeMsc<=0)
      return false;
   if(state.hasPrev)
     {
      if(timeMsc<state.lastMsc)
         return false;
      if(timeMsc==state.lastMsc && bid==state.prevBid && ask==state.prevAsk)
         return false;
     }
   state.breakeven=breakeven;
   state.atr=atr;
   const int tickSign=(state.hasPrev ?
                       EmttTickDivSign(state.prevBid,state.prevAsk,bid,ask) : 0);
   state.hasPrev=true;
   state.prevBid=bid;
   state.prevAsk=ask;
   state.lastMsc=timeMsc;

   //--- 25.4 window: 15-minute cap, then the 300-slot cap
   const long maxAge=(long)EMTT_DIV_MAX_WINDOW_MIN*60*1000;
   while(state.oldest<state.total &&
         timeMsc-state.msc[EmttTickDivSlot(state.oldest)]>maxAge)
      EmttTickDivPop(state);
   if(state.total-state.oldest>=EMTT_DIV_TICKS)
      EmttTickDivPop(state);

   //--- push
   const long sequence=state.total;
   const int slot=EmttTickDivSlot(sequence);
   const double midPrice=(bid+ask)/2.0;
   state.cvdNow+=tickSign;
   state.cvdAbs+=(tickSign!=0 ? 1 : 0);
   state.msc[slot]=timeMsc;
   state.mid[slot]=midPrice;
   state.sign[slot]=tickSign;
   state.cvd[slot]=state.cvdNow;
   if(sequence>state.oldest &&
      state.mid[EmttTickDivSlot(sequence-1)]==midPrice)
      state.runStart[slot]=state.runStart[EmttTickDivSlot(sequence-1)];
   else
      state.runStart[slot]=sequence;
   state.total=sequence+1;

   //--- peaks that left the window
   if(state.has0 && state.seq0<state.oldest)
      state.has0=false;
   if(state.has1 && state.seq1<state.oldest)
     {
      state.has1=false;
      state.pullback=false;
      EmttTickDivResetLeg(state,"leg left the window",writeJournal);
     }

   //--- 25.6 density over the last 60 seconds, with hysteresis
   if(state.densityStart<state.oldest)
      state.densityStart=state.oldest;
   const long densityAge=(long)EMTT_DIV_DENSITY_MIN*1000;
   while(state.densityStart<state.total &&
         timeMsc-state.msc[EmttTickDivSlot(state.densityStart)]>=densityAge)
      state.densityStart++;
   state.density=(int)(state.total-state.densityStart);
   const bool wasSparse=state.sparse;
   if(!state.sparse && state.density<EMTT_DIV_DENSITY_MIN_TICKS)
      state.sparse=true;
   else if(state.sparse && state.density>=EMTT_DIV_DENSITY_RECOVER)
      state.sparse=false;

   //--- warmup and the once-per-session gate journal
   if(!state.warm && state.total>=EMTT_DIV_WARMUP_TICKS)
     {
      state.warm=true;
      if(state.sparse)
        {
         if(writeJournal)
            Print(EmttTickDivInactiveLine(state.density,timeMsc));
         state.sparseJournaled=true;
        }
      else if(writeJournal)
         Print(EmttTickDivActiveLine(state.side,timeMsc));
     }
   else if(state.warm && state.sparse!=wasSparse)
     {
      if(state.sparse && !state.sparseJournaled)
        {
         if(writeJournal)
            Print(EmttTickDivInactiveLine(state.density,timeMsc));
         state.sparseJournaled=true;
        }
      else if(!state.sparse && !state.recoverJournaled)
        {
         if(writeJournal)
            Print(EmttTickDivRecoveredLine(state.density,timeMsc));
         state.recoverJournaled=true;
        }
     }

   //--- 25.5 swings (always tracked, so legs exist when detection opens)
   EmttTickDivDetectSwing(state,writeJournal);

   //--- 25.7 evaluation
   if(!EmttTickDivActive(state))
     {
      // Inactive: state none, multiplier 1.0 (25.6). Legs are kept.
      state.level=EMTT_DIV_LEVEL_NONE;
      state.weakHeld=0;
      state.strongHeld=0;
      return true;
     }
   int candidate=EMTT_DIV_LEVEL_NONE;
   if(state.atr>0.0 && state.has0 && state.has1)
     {
      const double leg=state.side*(state.pricePeak1-state.pricePeak0);
      const double c0=(double)(state.side*state.cvdAtPricePeak0);
      const double c1=(double)(state.side*state.cvdAtPricePeak1);
      if(leg>0.0 && leg>=EMTT_DIV_PRICE_LEAST_ATR*state.atr && c1<c0)
         candidate=(c1<=c0*EMTT_DIV_STRONG_RATIO ? EMTT_DIV_LEVEL_STRONG :
                                                   EMTT_DIV_LEVEL_WEAK);
     }
   state.weakHeld=(candidate>=EMTT_DIV_LEVEL_WEAK ? state.weakHeld+1 : 0);
   state.strongHeld=(candidate>=EMTT_DIV_LEVEL_STRONG ? state.strongHeld+1 : 0);
   // Hysteresis: the level only ever rises on a leg; strong never
   // drops back to weak, and none returns only through a reset.
   if(state.level<EMTT_DIV_LEVEL_STRONG &&
      state.strongHeld>=EMTT_DIV_CONFIRM_TICKS)
     {
      state.level=EMTT_DIV_LEVEL_STRONG;
      if(writeJournal)
         Print(EmttTickDivLevelLine(state,EMTT_DIV_LEVEL_STRONG,timeMsc));
     }
   else if(state.level<EMTT_DIV_LEVEL_WEAK &&
           state.weakHeld>=EMTT_DIV_CONFIRM_TICKS)
     {
      state.level=EMTT_DIV_LEVEL_WEAK;
      if(writeJournal)
         Print(EmttTickDivLevelLine(state,EMTT_DIV_LEVEL_WEAK,timeMsc));
     }
   return true;
  }

#endif // EMTT_TICKDIVERGENCE_MQH
