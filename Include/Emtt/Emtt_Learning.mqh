//+------------------------------------------------------------------+
//|                                             Emtt_Learning.mqh    |
//| Phase 7: the self-learning signal filter - the 16 features, the  |
//| logistic model and its SGD update, the warm-up, the learned term |
//| L, the adjusted number and the learning clause text             |
//| Spec: Emtt.md sections 19.4-19.7                                 |
//+------------------------------------------------------------------+
//| Pure logic over the tickets of 19.3 and the four published       |
//| states. No file access, no chart, no order, no EA global. The    |
//| weights are never stored: they are recomputed from the tickets   |
//| in file order, so the same tickets always give the same terms    |
//| (19.2 rule 6). ASCII source only (17.2 rule 9): the dash of the  |
//| Row 10 line is written "\x2014".                                 |
//+------------------------------------------------------------------+
#ifndef EMTT_LEARNING_MQH
#define EMTT_LEARNING_MQH

#include "Emtt_LearnFile.mqh"
#include "Emtt_Signal.mqh"

//--- 19.8 the parameter rows of this phase ---------------------------
//--- None of them is a lookback, so Layer 2 scales none of them. -----
#define EMTT_LEARN_FEATURES   16
#define EMTT_LEARN_WARMUP     30
#define EMTT_LEARN_STRENGTH   0.15
#define EMTT_LEARN_RATE       0.30
#define EMTT_LEARN_CLAMP      4.0
#define EMTT_LEARN_Z_CLAMP    30
#define EMTT_LEARN_CONF_CAP   100

//+------------------------------------------------------------------+
//| One side's numbers.                                              |
//+------------------------------------------------------------------+
struct SEmttLearnSide
  {
   double probability;   // the model's own value for this side
   double term;          // L = clamp(2p - 1, -1, +1); exactly 0 before warm-up
   double value;         // V = S6(side) x (1 + 0.15 x L)
  };

//+------------------------------------------------------------------+
//| The newest closed bar's reading (19.5).                          |
//+------------------------------------------------------------------+
struct SEmttLearnReading
  {
   bool   ready;         // the four views are ready (17.2 rule 4)
   double combined;      // S6, the signed value of 17.3
   int    rawNumber;     // the four-view whole number, -1 when not ready
   bool   warm;          // labeled >= EMTT_LEARN_WARMUP
   int    labeled;
   int    direction;     // the side with the larger V, 0 when equal
   int    number;        // Row 3 after learning, capped at 100
   int    percent;       // the leaning side's estimate, -1 when not warm
   double scale;         // the factor applied to the four scores
   SEmttLearnSide buy;
   SEmttLearnSide sell;
  };

//+------------------------------------------------------------------+
//| The newest closed bar's inputs, in the 17.3 order (19.4).        |
//+------------------------------------------------------------------+
struct SEmttLearnCandle
  {
   bool   ready;         // the four views are ready
   double combined;      // S6, the signed value of 17.3
   int    rawNumber;     // the four-view whole number
   int    trendDirection;
   int    structureDirection;
   int    flowDirection;
   int    htfDirection;
   int    mood;          // EEmttLearnMood
   int    session;       // EEmttLearnSession
   int    vol;           // EEmttLearnVol
  };

//+------------------------------------------------------------------+
//| The phase state: the record, the recomputed model and the last   |
//| reading. No weight is ever written anywhere (19.4).              |
//+------------------------------------------------------------------+
struct SEmttLearningState
  {
   SEmttLearnFileState file;
   double   weights[EMTT_LEARN_FEATURES];
   double   bias;
   bool     modelDirty;    // the tickets changed: recompute before use
   int      modelLabeled;  // labeled tickets the current weights saw
   bool     resumeChecked; // the open plan of this file was resumed once
   SEmttLearnReading reading;
  };

//+------------------------------------------------------------------+
//| Small local helpers. No EA helper is called from this component. |
//+------------------------------------------------------------------+
double EmttLearnClampWeight(const double value)
  {
   if(value>EMTT_LEARN_CLAMP)
      return EMTT_LEARN_CLAMP;
   if(value<-EMTT_LEARN_CLAMP)
      return -EMTT_LEARN_CLAMP;
   return value;
  }

// z is clamped to [-30, +30] before the logistic (19.4).
double EmttLearnProbabilityAt(const double &weights[],const double bias,
                              const double &x[])
  {
   double z=bias;
   for(int i=0;i<EMTT_LEARN_FEATURES;i++)
      z+=weights[i]*x[i];
   if(z>EMTT_LEARN_Z_CLAMP)
      z=EMTT_LEARN_Z_CLAMP;
   if(z<-EMTT_LEARN_Z_CLAMP)
      z=-EMTT_LEARN_Z_CLAMP;
   return 1.0/(1.0+MathExp(-z));
  }

double EmttLearnTermOf(const double probability)
  {
   double term=2.0*probability-1.0;
   if(term>1.0)
      term=1.0;
   if(term<-1.0)
      term=-1.0;
   return term;
  }

void EmttLearnReadingReset(SEmttLearnReading &reading)
  {
   reading.ready=false;
   reading.combined=0.0;
   reading.rawNumber=-1;
   reading.warm=false;
   reading.labeled=0;
   reading.direction=0;
   reading.number=-1;
   reading.percent=-1;
   reading.scale=1.0;
   reading.buy.probability=0.5;
   reading.buy.term=0.0;
   reading.buy.value=0.0;
   reading.sell.probability=0.5;
   reading.sell.term=0.0;
   reading.sell.value=0.0;
  }

void EmttLearnStateReset(SEmttLearningState &state)
  {
   EmttLearnFileReset(state.file);
   for(int i=0;i<EMTT_LEARN_FEATURES;i++)
      state.weights[i]=0.0;
   state.bias=0.0;
   state.modelDirty=true;
   state.modelLabeled=0;
   state.resumeChecked=false;
   EmttLearnReadingReset(state.reading);
  }

//+------------------------------------------------------------------+
//| 19.4 the 16 features. Fixed order: direction, confidence, the    |
//| four agreements, the four moods, the three sessions, the three   |
//| volatility buckets.                                              |
//+------------------------------------------------------------------+
void EmttLearnFeatures(const int side,const int confidenceNumber,
                       const int trendDirection,const int structureDirection,
                       const int flowDirection,const int htfDirection,
                       const int mood,const int session,const int vol,
                       double &x[])
  {
   ArrayResize(x,EMTT_LEARN_FEATURES);
   for(int i=0;i<EMTT_LEARN_FEATURES;i++)
      x[i]=0.0;
   x[0]=(side>0 ? 1.0 : -1.0);
   x[1]=(double)confidenceNumber/100.0;
   x[2]=(double)(trendDirection*side);
   x[3]=(double)(structureDirection*side);
   x[4]=(double)(flowDirection*side);
   x[5]=(double)(htfDirection*side);
   const int moodIndex=(mood>=0 && mood<4 ? mood : 3);
   x[6+moodIndex]=1.0;
   const int sessionIndex=(session>=0 && session<3 ? session : 0);
   x[10+sessionIndex]=1.0;
   const int volIndex=(vol>=0 && vol<3 ? vol : 1);
   x[13+volIndex]=1.0;
  }

void EmttLearnFeaturesFromTicket(const SEmttLearnTicket &ticket,
                                 double &x[])
  {
   EmttLearnFeatures(ticket.side,ticket.confidence,ticket.views[0],
                     ticket.views[1],ticket.views[2],ticket.views[3],
                     ticket.mood,ticket.session,ticket.vol,x);
  }

// 19.4: the ticket's label. A target is a win (1), a stop a loss (0);
// every other result is neither and never trains.
int EmttLearnLabelOf(const SEmttLearnTicket &ticket)
  {
   if(ticket.result==EMTT_LEARN_RESULT_TARGET)
      return 1;
   if(ticket.result==EMTT_LEARN_RESULT_STOP)
      return 0;
   return -1;
  }

//+------------------------------------------------------------------+
//| 19.4 training: one SGD step per labeled ticket, in file order,   |
//| with lr = 0.30 / sqrt(k) for the k-th labeled ticket. The weights |
//| start at zero and are recomputed, never stored.                  |
//+------------------------------------------------------------------+
void EmttLearnBuildModel(SEmttLearningState &state)
  {
   for(int i=0;i<EMTT_LEARN_FEATURES;i++)
      state.weights[i]=0.0;
   state.bias=0.0;
   int k=0;
   double x[EMTT_LEARN_FEATURES];
   for(int ticketIndex=0;ticketIndex<state.file.ticketCount;ticketIndex++)
     {
      const SEmttLearnTicket ticket=state.file.tickets[ticketIndex];
      const int label=EmttLearnLabelOf(ticket);
      if(label<0)
         continue;
      k++;
      EmttLearnFeaturesFromTicket(ticket,x);
      const double p=EmttLearnProbabilityAt(state.weights,state.bias,x);
      const double lr=EMTT_LEARN_RATE/MathSqrt((double)k);
      const double error=(double)label-p;
      for(int i=0;i<EMTT_LEARN_FEATURES;i++)
         state.weights[i]=EmttLearnClampWeight(state.weights[i]+
                                               lr*error*x[i]);
      state.bias=EmttLearnClampWeight(state.bias+lr*error);
     }
   state.modelLabeled=k;
   state.modelDirty=false;
  }

void EmttLearnEnsureModel(SEmttLearningState &state)
  {
   if(state.modelDirty || state.modelLabeled!=state.file.labeled)
      EmttLearnBuildModel(state);
  }

//+------------------------------------------------------------------+
//| 19.5 the adjusted reading of one closed bar. The warm-up gates   |
//| the learned term: before it L is exactly 0 for both sides, so    |
//| every number and every decision is exactly Phase 6.              |
//+------------------------------------------------------------------+
void EmttLearnEvaluate(SEmttLearningState &state,
                       const SEmttLearnCandle &candle,
                       SEmttLearnReading &reading)
  {
   EmttLearnReadingReset(reading);
   reading.ready=candle.ready;
   reading.rawNumber=candle.rawNumber;
   reading.combined=candle.combined;
   reading.labeled=state.file.labeled;
   reading.warm=(state.file.labeled>=EMTT_LEARN_WARMUP);
   reading.number=candle.rawNumber;
   if(!candle.ready)
      return;

   double x[EMTT_LEARN_FEATURES];
   EmttLearnFeatures(1,candle.rawNumber,candle.trendDirection,
                     candle.structureDirection,candle.flowDirection,
                     candle.htfDirection,candle.mood,candle.session,
                     candle.vol,x);
   reading.buy.probability=EmttLearnProbabilityAt(state.weights,
                                                  state.bias,x);
   EmttLearnFeatures(-1,candle.rawNumber,candle.trendDirection,
                     candle.structureDirection,candle.flowDirection,
                     candle.htfDirection,candle.mood,candle.session,
                     candle.vol,x);
   reading.sell.probability=EmttLearnProbabilityAt(state.weights,
                                                   state.bias,x);
   reading.buy.term=(reading.warm ?
                     EmttLearnTermOf(reading.buy.probability) : 0.0);
   reading.sell.term=(reading.warm ?
                      EmttLearnTermOf(reading.sell.probability) : 0.0);
   reading.buy.value=candle.combined*(1.0+EMTT_LEARN_STRENGTH*
                                      reading.buy.term);
   reading.sell.value=-candle.combined*(1.0+EMTT_LEARN_STRENGTH*
                                        reading.sell.term);

   if(reading.buy.value>reading.sell.value)
      reading.direction=1;
   else if(reading.sell.value>reading.buy.value)
      reading.direction=-1;
   else
      reading.direction=0;

   const double best=MathMax(0.0,MathMax(reading.buy.value,
                                         reading.sell.value));
   reading.number=(int)MathRound(100.0*best);
   if(reading.number>EMTT_LEARN_CONF_CAP)
      reading.number=EMTT_LEARN_CONF_CAP;

   if(reading.direction!=0)
     {
      const double probability=(reading.direction>0 ?
                                reading.buy.probability :
                                reading.sell.probability);
      reading.percent=(reading.warm ?
                       (int)MathRound(100.0*probability) : -1);
      if(MathAbs(candle.combined)>0.0)
        {
         const double term=(reading.direction>0 ? reading.buy.term
                                                : reading.sell.term);
         // 19.5: the number is capped at 100, so the scale never pushes
         // the four-view value past 1.0; the 0.15 strength is the bound.
         const double factor=1.0+EMTT_LEARN_STRENGTH*term;
         const double cap=1.0/MathAbs(candle.combined);
         reading.scale=MathMin(factor,cap);
         if(reading.scale<0.0)
            reading.scale=0.0;
        }
     }
  }

//+------------------------------------------------------------------+
//| The mappings from the published readings into the file's fixed   |
//| vocabularies (19.3, 19.4). The session comes from the 15.3       |
//| anchor: where two sessions overlap, the later opening one wins.  |
//+------------------------------------------------------------------+
int EmttLearnMoodIndex(const EEmttRegime mood)
  {
   if(mood==EMTT_REGIME_TRENDING_BULLISH || mood==EMTT_REGIME_TRENDING_BEARISH)
      return EMTT_LEARN_MOOD_TRENDING;
   if(mood==EMTT_REGIME_RANGING)
      return EMTT_LEARN_MOOD_RANGING;
   if(mood==EMTT_REGIME_VOLATILE)
      return EMTT_LEARN_MOOD_VOLATILE;
   return EMTT_LEARN_MOOD_TRANSITION;
  }

int EmttLearnSessionIndex(const string sessionName)
  {
   if(StringFind(sessionName,"NY")>=0)
      return EMTT_LEARN_SESSION_NEWYORK;
   if(StringFind(sessionName,"London")>=0)
      return EMTT_LEARN_SESSION_LONDON;
   return EMTT_LEARN_SESSION_ASIA;
  }

int EmttLearnVolIndex(const EEmttVolatility volatility)
  {
   if(volatility==EMTT_VOL_LOW)
      return EMTT_LEARN_VOL_LOW;
   if(volatility==EMTT_VOL_HIGH)
      return EMTT_LEARN_VOL_HIGH;
   return EMTT_LEARN_VOL_NORMAL;
  }

// The 17.8 wording comes from Emtt_Signal.mqh's own names; this maps a
// stored result word back to that enum.
EEmttPlanResult EmttLearnPlanResultOf(const int learnResult)
  {
   if(learnResult==EMTT_LEARN_RESULT_TARGET)    return EMTT_PLAN_RESULT_TARGET;
   if(learnResult==EMTT_LEARN_RESULT_STOP)      return EMTT_PLAN_RESULT_STOP;
   if(learnResult==EMTT_LEARN_RESULT_MISSED)    return EMTT_PLAN_RESULT_MISSED;
   if(learnResult==EMTT_LEARN_RESULT_CANCELLED) return EMTT_PLAN_RESULT_CANCELLED;
   if(learnResult==EMTT_LEARN_RESULT_SIGNAL)    return EMTT_PLAN_RESULT_SIGNAL;
   if(learnResult==EMTT_LEARN_RESULT_MARKET)    return EMTT_PLAN_RESULT_CLOSED;
   if(learnResult==EMTT_LEARN_RESULT_CHART)     return EMTT_PLAN_RESULT_CHART;
   return EMTT_PLAN_RESULT_NONE;
  }

int EmttLearnResultOfPlanResult(const EEmttPlanResult result)
  {
   if(result==EMTT_PLAN_RESULT_TARGET)    return EMTT_LEARN_RESULT_TARGET;
   if(result==EMTT_PLAN_RESULT_STOP)      return EMTT_LEARN_RESULT_STOP;
   if(result==EMTT_PLAN_RESULT_MISSED)    return EMTT_LEARN_RESULT_MISSED;
   if(result==EMTT_PLAN_RESULT_CANCELLED) return EMTT_LEARN_RESULT_CANCELLED;
   if(result==EMTT_PLAN_RESULT_SIGNAL)    return EMTT_LEARN_RESULT_SIGNAL;
   if(result==EMTT_PLAN_RESULT_CLOSED)    return EMTT_LEARN_RESULT_MARKET;
   if(result==EMTT_PLAN_RESULT_CHART)     return EMTT_LEARN_RESULT_CHART;
   return EMTT_LEARN_RESULT_NONE;
  }

// 17.4's Expected Duration estimate, whole minutes - the value the
// ticket's `est` field carries. It is a pure function of the plan's
// own levels and the published Supertrend speed, so the same bar
// always gives the same number.
int EmttLearnEstimateMinutes(const SEmttTradePlan &plan,
                             const int trendDirection,
                             const int barsSinceFlip,
                             const double distanceAtrs,const double atr,
                             const ENUM_TIMEFRAMES timeframe)
  {
   const int minutesPerCandle=EmttPlanMinutesPerCandle(timeframe);
   if(minutesPerCandle<=0 || !EmttPlanValidPositive(atr) || plan.side==0)
      return 0;
   double speed=0.0;
   if(trendDirection==plan.side && barsSinceFlip>0)
      speed=distanceAtrs/(double)barsSinceFlip;
   if(speed<EMTT_PLAN_SPEED_FLOOR)
      speed=EMTT_PLAN_SPEED_FLOOR;
   const double candles=(MathAbs(plan.target-plan.entry)/atr)/speed;
   const double minutes=candles*(double)minutesPerCandle;
   if(minutes<=0.0)
      return 0;
   return (int)MathRound(minutes);
  }

// The Expected Duration text of a resumed plan, rebuilt from the file's
// whole-minute estimate with the 17.4 band rules.
string EmttLearnDurationFromEstimate(const int estimate,
                                     const ENUM_TIMEFRAMES timeframe)
  {
   const int minutesPerCandle=EmttPlanMinutesPerCandle(timeframe);
   if(minutesPerCandle<=0 || estimate<=0)
      return "--";
   return EmttPlanDurationText((double)estimate/(double)minutesPerCandle,
                               timeframe);
  }

//+------------------------------------------------------------------+
//| 19.3: the ticket of a plan that starts at this closed bar. Every |
//| field is a published reading of the start bar or the plan itself. |
//+------------------------------------------------------------------+
void EmttLearnTicketFromPlan(SEmttLearnTicket &ticket,
                             const SEmttTradePlan &plan,
                             const int confidenceNumber,
                             const int trendDirection,
                             const int structureDirection,
                             const int flowDirection,
                             const int htfDirection,
                             const int mood,const int session,const int vol,
                             const int estimateMinutes,const int spreadPoints,
                             const long startSequence)
  {
   EmttLearnTicketReset(ticket);
   ticket.used=true;
   ticket.startBarTime=plan.startBarTime;
   ticket.side=plan.side;
   ticket.confidence=confidenceNumber;
   ticket.views[0]=trendDirection;
   ticket.views[1]=structureDirection;
   ticket.views[2]=flowDirection;
   ticket.views[3]=htfDirection;
   ticket.mood=mood;
   ticket.session=session;
   ticket.vol=vol;
   ticket.entry=plan.entry;
   ticket.entryKind=(plan.entryKind==EMTT_PLAN_ENTRY_BLOCK ?
                     EMTT_LEARN_ENTRY_BLOCK : EMTT_LEARN_ENTRY_MARKET);
   ticket.stop=plan.stop;
   ticket.target=plan.target;
   ticket.est=estimateMinutes;
   ticket.spread=spreadPoints;
   ticket.state=(plan.status==EMTT_PLAN_ACTIVE ? EMTT_LEARN_STATE_ACTIVE :
                                               EMTT_LEARN_STATE_PENDING);
   ticket.startSequence=startSequence;
  }

//+------------------------------------------------------------------+
//| 19.7 the Row 9 clause: warming before the warm-up, the leaning   |
//| side's estimate after it, empty when the bar has no leaning side.|
//+------------------------------------------------------------------+
string EmttLearnWarmingText(const SEmttLearningState &state)
  {
   return "warming "+IntegerToString(state.file.labeled)+"/"+
          IntegerToString(EMTT_LEARN_WARMUP);
  }

string EmttLearnWhyClause(const SEmttLearningState &state,
                          const SEmttLearnReading &reading)
  {
   if(!reading.ready)
      return "";
   if(!reading.warm)
      return "Learning "+EmttLearnWarmingText(state);
   if(reading.direction!=0 && reading.percent>=0)
      return "Learning "+IntegerToString(reading.percent)+"% ("+
             IntegerToString(reading.labeled)+" plans)";
   return "Learning ("+IntegerToString(reading.labeled)+" plans)";
  }

string EmttLearnWhyAppend(const string priorWhy,
                          const string clause)
  {
   if(clause=="")
      return priorWhy;
   if(priorWhy=="" || priorWhy=="--")
      return clause;
   return priorWhy+" | "+clause;
  }

// 19.7 the plan start line's last part: "learning 64%" or
// "learning warming 22/30". Empty when there is nothing to say, so the
// caller can leave the part out with no empty separator.
string EmttLearnPlanText(const SEmttLearningState &state,
                         const SEmttLearnReading &reading)
  {
   if(!reading.warm)
      return "learning "+EmttLearnWarmingText(state);
   if(reading.direction!=0 && reading.percent>=0)
      return "learning "+IntegerToString(reading.percent)+"%";
   return "";
  }

// 19.7 the one WAIT reason Phase 7 adds, checked before the first reason
// of 17.6: the four-view number would reach the bar while the adjusted
// number does not. Empty in every other state.
string EmttLearnHoldReason(const SEmttLearningState &state,
                           const SEmttLearnReading &reading,
                           const int moodBar)
  {
   if(!reading.ready || !reading.warm || reading.direction==0)
      return "";
   if(moodBar<=0 || reading.percent<0)
      return "";
   if(reading.rawNumber<moodBar)
      return "";
   if(reading.number>=moodBar)
      return "";
   return "Watching \x2014 learning "+IntegerToString(reading.percent)+
          "% holds this one back.";
  }

//+------------------------------------------------------------------+
//| 19.7 the learning journal lines. One line per labeled result, and |
//| one when only the clause of the dashboard changes (19.3 event 3:  |
//| the entry was reached, the leaning side of the same bar does not  |
//| move). The weights, the features and the per-candle probabilities |
//| never appear anywhere.                                            |
//+------------------------------------------------------------------+
void EmttLearnJournalUpdated(const SEmttLearningState &state,
                             const datetime barTime)
  {
   PrintFormat("Emtt | Learning updated | %d labeled, %d wins, %d losses | bar %s",
               state.file.labeled,state.file.wins,state.file.losses,
               EmttLearnTimeText(barTime));
  }

void EmttLearnJournalResumed(const SEmttLearnTicket &ticket,
                             const int candlesChecked,
                             const datetime barTime)
  {
   PrintFormat("Emtt | Learning resumed | plan %s %s | start %s | %d candles checked | bar %s",
               EmttPlanSideName(ticket.side),
               EmttLearnStateWord(ticket.state),
               EmttLearnTimeText(ticket.startBarTime),candlesChecked,
               EmttLearnTimeText(barTime));
  }

#endif // EMTT_LEARNING_MQH
