//+------------------------------------------------------------------+
//|                                            Emtt_Supertrend.mqh   |
//|     Phase 3: ML-adaptive Supertrend - bands, K-Means clusters    |
//|                  and the per-cluster ATR multiplier              |
//|                   Spec: Emtt.md sections 11.3-11.11              |
//+------------------------------------------------------------------+
//| Design seam (11.11): every function here takes the timeframe and |
//| the closed-bar data as arguments. This header reads no chart, no |
//| panel and no EA global, so the multi-timeframe phase can create a|
//| second instance for a higher timeframe without changing it.      |
//+------------------------------------------------------------------+
#ifndef EMTT_SUPERTREND_MQH
#define EMTT_SUPERTREND_MQH

#include "Emtt_DynamicParams.mqh"

//--- 11.7: the training window is the first lookback parameter ------
#define EMTT_ST_WINDOW_BASE        200   // closed bars, before layer 2
#define EMTT_ST_ATR_BASELINE_BARS  50    // 11.8: gate = window + ATR(50)
#define EMTT_ST_MIN_WINDOW_BARS    30    // safety floor for a usable window

//--- 11.4: K-Means --------------------------------------------------
#define EMTT_ST_CLUSTERS           3     // Calm / Normal / Wild
#define EMTT_ST_KMEANS_ITERATIONS  20
#define EMTT_ST_MIN_MEMBERS        5     // sparse-cluster guard
#define EMTT_ST_RETRAIN_DIVISOR    20    // retrain every window / 20 bars

//--- 11.5: multiplier candidates ------------------------------------
#define EMTT_ST_MULTIPLIER_MIN     2.0
#define EMTT_ST_MULTIPLIER_MAX     4.0
#define EMTT_ST_MULTIPLIER_STEP    0.5
#define EMTT_ST_DEFAULT_MULTIPLIER 3.0   // unlearned cluster, set midpoint
#define EMTT_ST_WHIPSAW_PENALTY    0.10
#define EMTT_ST_SCORE_TIE          1e-12

//--- 11.6: the published 0.0-1.0 component score --------------------
#define EMTT_ST_WEIGHT_DISTANCE    0.45
#define EMTT_ST_WEIGHT_AGE         0.35
#define EMTT_ST_WEIGHT_FLIPS       0.20
#define EMTT_ST_AGE_SCALE_BARS     20.0
#define EMTT_ST_FLIP_SCALE_COUNT   20.0

enum EEmttStCluster
  {
   EMTT_ST_CLUSTER_NONE=-1,
   EMTT_ST_CLUSTER_CALM=0,
   EMTT_ST_CLUSTER_NORMAL=1,
   EMTT_ST_CLUSTER_WILD=2
  };

//+------------------------------------------------------------------+
//| The component contract of 11.6: readings plus the facts behind   |
//| them. Nothing here is displayed except the Row 9 clause of 11.8. |
//+------------------------------------------------------------------+
struct SEmttSupertrendState
  {
   bool            initialized;
   bool            ready;              // a measurement exists
   int             window;             // training window, closed bars
   int             retrainInterval;    // max(1, window / 20)
   int             barsSinceTrain;
   EEmttAssetClass assetClass;         // context that triggers a retrain
   int             atrPeriod;          // matrix period the reading uses
   EEmttVolatility volatility;
   double          centre[EMTT_ST_CLUSTERS];
   int             members[EMTT_ST_CLUSTERS];
   double          clusterMultiplier[EMTT_ST_CLUSTERS];
   bool            clusterLearned[EMTT_ST_CLUSTERS];
   EEmttStCluster  cluster;            // Calm / Normal / Wild
   double          multiplier;         // live ATR multiple in use
   int             direction;          // +1 / -1 / 0 (0 = flat)
   double          line;               // trailing reference, in price
   double          score;              // 0.0-1.0, never displayed
   int             barsSinceFlip;
   int             flipCount;          // direction flips inside the window
   double          distanceATRs;
   double          atrValue;           // newest closed bar's ATR
   bool            sparseFallback;     // a sparse cluster borrowed a value
   long            lastMultiplierChangeBar;
  };

//+------------------------------------------------------------------+
//| Value validation is local: this header never calls an EA helper  |
//+------------------------------------------------------------------+
bool EmttStValid(const double value)
  {
   return(MathIsValidNumber(value) && value!=EMPTY_VALUE);
  }

bool EmttStValidPositive(const double value)
  {
   return(EmttStValid(value) && value>0.0);
  }

double EmttStClamp01(const double value)
  {
   if(!MathIsValidNumber(value))
      return 0.0;
   return MathMax(0.0,MathMin(1.0,value));
  }

//+------------------------------------------------------------------+
//| Layer 2 of 9.2.3: lookback scaling for the chart timeframe.      |
//| M5 = 1.0x, M15 = 1.25x, M30 = 1.5x, rounded to a whole bar.      |
//+------------------------------------------------------------------+
double EmttLookbackScale(const ENUM_TIMEFRAMES timeframe)
  {
   if(timeframe==PERIOD_M15)
      return 1.25;
   if(timeframe==PERIOD_M30)
      return 1.50;
   return 1.00; // M5 keeps the base lookback
  }

// Local on purpose: the journal must not reach into an EA helper.
string EmttStTimeframeName(const ENUM_TIMEFRAMES timeframe)
  {
   if(timeframe==PERIOD_M5)  return "M5";
   if(timeframe==PERIOD_M15) return "M15";
   if(timeframe==PERIOD_M30) return "M30";
   const string name=EnumToString(timeframe);
   if(StringFind(name,"PERIOD_")==0)
      return StringSubstr(name,7);
   return name;
  }

int EmttSupertrendWindow(const ENUM_TIMEFRAMES timeframe)
  {
   const double scaled=(double)EMTT_ST_WINDOW_BASE*EmttLookbackScale(timeframe);
   int window=(int)MathRound(scaled);
   if(window<EMTT_ST_MIN_WINDOW_BARS)
      window=EMTT_ST_MIN_WINDOW_BARS;
   return window;
  }

// 11.8: one history gate for every measurement - the training window
// plus the 50-bar ATR baseline it is measured on.
int EmttHistoryRequired(const ENUM_TIMEFRAMES timeframe)
  {
   return EmttSupertrendWindow(timeframe)+EMTT_ST_ATR_BASELINE_BARS;
  }

int EmttSupertrendRetrainInterval(const int window)
  {
   const int interval=window/EMTT_ST_RETRAIN_DIVISOR;
   return(interval<1 ? 1 : interval);
  }

//+------------------------------------------------------------------+
//| Names used by the journal and by the Row 9 clause                |
//+------------------------------------------------------------------+
string EmttStClusterName(const EEmttStCluster cluster)
  {
   switch(cluster)
     {
      case EMTT_ST_CLUSTER_CALM:   return "Calm";
      case EMTT_ST_CLUSTER_NORMAL: return "Normal";
      case EMTT_ST_CLUSTER_WILD:   return "Wild";
      default:                     return "--";
     }
  }

string EmttStDirectionName(const int direction)
  {
   if(direction>0) return "bullish";
   if(direction<0) return "bearish";
   return "flat";
  }

string EmttStMultiplierText(const double multiplier)
  {
   return DoubleToString(multiplier,1);
  }

//+------------------------------------------------------------------+
//| 11.5: the candidate set is the range - identical for every class |
//+------------------------------------------------------------------+
int EmttSupertrendCandidates(double &candidates[])
  {
   int count=0;
   for(double value=EMTT_ST_MULTIPLIER_MIN;
       value<=EMTT_ST_MULTIPLIER_MAX+EMTT_ST_SCORE_TIE;
       value+=EMTT_ST_MULTIPLIER_STEP)
     {
      count++;
      if(ArrayResize(candidates,count)!=count)
         break;
      candidates[count-1]=value;
     }
   return count;
  }

bool EmttStIsCandidate(const double multiplier)
  {
   double candidates[];
   const int count=EmttSupertrendCandidates(candidates);
   for(int i=0;i<count;i++)
      if(MathAbs(candidates[i]-multiplier)<=EMTT_ST_SCORE_TIE)
         return true;
   return false;
  }

//+------------------------------------------------------------------+
//| 11.3: Supertrend bands over the window. Series indexing: index is|
//| the bar being read and index+offset the older bars. The returned |
//| direction array is oldest-first, so segment walking reads left to|
//| right. Returns false without publishing anything when any bar in |
//| the window is unusable - nothing is invented.                    |
//+------------------------------------------------------------------+
bool EmttSupertrendWalk(const MqlRates &rates[],const double &atr[],
                        const int index,const int window,
                        const double multiplier,int &directions[],
                        int &directionOut,double &lineOut,
                        int &barsSinceFlipOut,int &flipCountOut)
  {
   directionOut=0;
   lineOut=0.0;
   barsSinceFlipOut=0;
   flipCountOut=0;
   if(index<0 || window<EMTT_ST_MIN_WINDOW_BARS || multiplier<=0.0)
      return false;
   if(index+window>ArraySize(rates) || index+window>ArraySize(atr))
      return false;
   if(ArrayResize(directions,window)!=window)
      return false;

   double previousUp=0.0;
   double previousDown=0.0;
   double previousClose=0.0;
   int    previousDirection=0;
   int    flipCount=0;
   int    lastFlipOffset=window-1;

   for(int offset=window-1;offset>=0;offset--)
     {
      const int i=index+offset;
      const double atrValue=atr[i];
      const double high=rates[i].high;
      const double low=rates[i].low;
      const double close=rates[i].close;
      if(!EmttStValidPositive(atrValue) || !EmttStValid(high) ||
         !EmttStValid(low) || !EmttStValidPositive(close))
         return false;

      const double mid=(high+low)*0.5;
      const double upRaw=mid+multiplier*atrValue;
      const double downRaw=mid-multiplier*atrValue;
      double up,down;
      int current;
      if(offset==window-1)
        {
         // The oldest bar of the window seeds direction +1.
         up=upRaw;
         down=downRaw;
         current=1;
        }
      else
        {
         up=((upRaw<previousUp || previousClose>previousUp) ? upRaw : previousUp);
         down=((downRaw>previousDown || previousClose<previousDown) ?
               downRaw : previousDown);
         if(close>previousUp)
            current=1;
         else if(close<previousDown)
            current=-1;
         else
            current=previousDirection;
        }

      directions[window-1-offset]=current;
      if(offset<window-1 && current!=previousDirection)
        {
         flipCount++;
         lastFlipOffset=offset;
        }
      previousUp=up;
      previousDown=down;
      previousClose=close;
      previousDirection=current;

      if(offset==0)
        {
         directionOut=current;
         lineOut=(current>0 ? down : up);
        }
     }

   flipCountOut=flipCount;
   barsSinceFlipOut=lastFlipOffset;
   return true;
  }

//+------------------------------------------------------------------+
//| 11.4: nearest-rank quantile of the window itself. This is a      |
//| quantile of the set, not the rank percentile of 9.2.2, so        |
//| EmttPercentileRank is deliberately not used here.                |
//+------------------------------------------------------------------+
double EmttStQuantileSeed(const double &sorted[],const int count,
                          const double quantile)
  {
   if(count<=0)
      return 0.0;
   int rank=(int)MathCeil(quantile/100.0*(double)count);
   if(rank<1)
      rank=1;
   if(rank>count)
      rank=count;
   return sorted[rank-1];
  }

// Nearest centre wins; an exact tie resolves to the calmer centre.
int EmttStNearestCentre(const double &centre[],const int count,
                        const double value)
  {
   int best=0;
   double bestDistance=0.0;
   for(int c=0;c<count;c++)
     {
      const double distance=MathAbs(value-centre[c]);
      if(c==0 || distance<bestDistance)
        {
         best=c;
         bestDistance=distance;
        }
     }
   return best;
  }

// The same rule reading the state directly, so no function here ever has
// to receive a struct member as an array reference.
int EmttStNearestCentreOf(const SEmttSupertrendState &state,const double value)
  {
   int best=0;
   double bestDistance=0.0;
   for(int c=0;c<EMTT_ST_CLUSTERS;c++)
     {
      const double distance=MathAbs(value-state.centre[c]);
      if(c==0 || distance<bestDistance)
        {
         best=c;
         bestDistance=distance;
        }
     }
   return best;
  }

//+------------------------------------------------------------------+
//| 11.4 sparse guard: a cluster holding fewer than 5 bars never owns|
//| a learned multiplier, so the nearest populated cluster lends its |
//| value and the reason is journaled by the caller.                 |
//+------------------------------------------------------------------+
void EmttStResolveMultiplier(const SEmttSupertrendState &state,
                             const double atrValue,int &clusterOut,
                             double &multiplierOut,int &donorOut)
  {
   clusterOut=EmttStNearestCentreOf(state,atrValue);
   donorOut=clusterOut;
   if(state.members[clusterOut]>=EMTT_ST_MIN_MEMBERS)
     {
      multiplierOut=state.clusterMultiplier[clusterOut];
      return;
     }
   donorOut=-1;
   double bestDistance=0.0;
   for(int c=0;c<EMTT_ST_CLUSTERS;c++)
     {
      if(state.members[c]<EMTT_ST_MIN_MEMBERS)
         continue;
      const double distance=MathAbs(atrValue-state.centre[c]);
      if(donorOut<0 || distance<bestDistance)
        {
         donorOut=c;
         bestDistance=distance;
        }
     }
   multiplierOut=(donorOut>=0 ? state.clusterMultiplier[donorOut] :
                                EMTT_ST_DEFAULT_MULTIPLIER);
  }

//+------------------------------------------------------------------+
//| 11.5: score the segments of one candidate replay. A segment is   |
//| attributed to the cluster of the bar it starts on, so each       |
//| cluster learns the multiplier that served its own volatility     |
//| state while the bands themselves are replayed once across the    |
//| whole window. Pass clusterIndex<0 to score every segment.        |
//+------------------------------------------------------------------+
bool EmttSupertrendScoreSegments(const MqlRates &rates[],const double &atr[],
                                 const int index,const int window,
                                 const int &directions[],
                                 const double &centre[],
                                 const int clusterIndex,
                                 double &meanReturnOut,int &segmentCountOut,
                                 double &scoreOut)
  {
   meanReturnOut=0.0;
   segmentCountOut=0;
   scoreOut=0.0;
   double sum=0.0;
   int segments=0;
   int start=0;
   while(start<window)
     {
      int end=start;
      while(end+1<window && directions[end+1]==directions[start])
         end++;
      const int startIndex=index+window-1-start;
      const int endIndex=index+window-1-end;
      const int segmentDirection=directions[start];
      const double atrStart=atr[startIndex];
      const bool wanted=(clusterIndex<0 ||
                         EmttStNearestCentre(centre,EMTT_ST_CLUSTERS,
                                             atrStart)==clusterIndex);
      // A segment is at least one closed bar long.
      if(segmentDirection!=0 && EmttStValidPositive(atrStart) &&
         end>=start && wanted)
        {
         sum+=(double)segmentDirection*
              (rates[endIndex].close-rates[startIndex].close)/atrStart;
         segments++;
        }
      start=end+1;
     }

   if(segments<=0)
      return false; // no completed segment: the previous value stands
   meanReturnOut=sum/(double)segments;
   segmentCountOut=segments;
   const double noise=(double)segments/((double)window/10.0);
   scoreOut=meanReturnOut-EMTT_ST_WHIPSAW_PENALTY*noise;
   return true;
  }

//+------------------------------------------------------------------+
//| One oldest-first replay per candidate across the whole window,   |
//| flattened to candidateIndex * window + bar so the bands are      |
//| computed once and reused for all three clusters.                 |
//+------------------------------------------------------------------+
bool EmttSupertrendReplayCandidates(const MqlRates &rates[],
                                    const double &atr[],const int index,
                                    const int window,int &directions[])
  {
   double candidates[];
   const int count=EmttSupertrendCandidates(candidates);
   if(ArrayResize(directions,count*window)!=count*window)
      return false;
   for(int c=0;c<count;c++)
     {
      int slice[];
      int direction;
      double line;
      int barsSinceFlip,flipCount;
      if(!EmttSupertrendWalk(rates,atr,index,window,candidates[c],slice,
                             direction,line,barsSinceFlip,flipCount))
         return false;
      for(int j=0;j<window;j++)
         directions[c*window+j]=slice[j];
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Winner for one cluster: highest score, an exact tie going to the |
//| larger, smoother multiplier. The result can only ever be one of  |
//| the candidates. Returns false when the cluster has no completed  |
//| segment, so the caller keeps the cluster's previous value.       |
//+------------------------------------------------------------------+
bool EmttSupertrendSelectForCluster(const MqlRates &rates[],
                                    const double &atr[],const int index,
                                    const int window,
                                    const int &directions[],
                                    const double &centre[],
                                    const int clusterIndex,
                                    double &winnerOut)
  {
   winnerOut=EMTT_ST_DEFAULT_MULTIPLIER;
   double candidates[];
   const int count=EmttSupertrendCandidates(candidates);
   bool found=false;
   double bestScore=0.0;
   double bestMultiplier=EMTT_ST_DEFAULT_MULTIPLIER;
   for(int c=0;c<count;c++)
     {
      int slice[];
      if(ArrayResize(slice,window)!=window)
         return false;
      for(int j=0;j<window;j++)
         slice[j]=directions[c*window+j];
      double meanReturn;
      int segments;
      double score;
      if(!EmttSupertrendScoreSegments(rates,atr,index,window,slice,centre,
                                      clusterIndex,meanReturn,segments,score))
         continue;
      const bool better=(!found ||
                         score>bestScore+EMTT_ST_SCORE_TIE ||
                         (MathAbs(score-bestScore)<=EMTT_ST_SCORE_TIE &&
                          candidates[c]>bestMultiplier));
      if(better)
        {
         found=true;
         bestScore=score;
         bestMultiplier=candidates[c];
        }
     }
   if(!found)
      return false;
   winnerOut=bestMultiplier;
   return true;
  }

//+------------------------------------------------------------------+
//| 11.4: standard Lloyd iterations, max 20, always restarted from   |
//| the 10th / 50th / 90th percentile seeds - never from the previous|
//| centres. Centres are returned sorted ascending: Calm/Normal/Wild.|
//+------------------------------------------------------------------+
bool EmttSupertrendCluster(const double &values[],const int count,
                           double &centreOut[],int &membersOut[])
  {
   if(count<EMTT_ST_CLUSTERS)
      return false;
   double sorted[];
   if(ArrayResize(sorted,count)!=count)
      return false;
   double mean=0.0;
   for(int i=0;i<count;i++)
     {
      if(!EmttStValidPositive(values[i]))
         return false;
      sorted[i]=values[i];
      mean+=values[i];
     }
   mean/=(double)count;
   if(!EmttStValidPositive(mean))
      return false;
   ArraySort(sorted);

   double centre[];
   if(ArrayResize(centre,EMTT_ST_CLUSTERS)!=EMTT_ST_CLUSTERS)
      return false;
   centre[0]=EmttStQuantileSeed(sorted,count,10.0);
   centre[1]=EmttStQuantileSeed(sorted,count,50.0);
   centre[2]=EmttStQuantileSeed(sorted,count,90.0);

   const double tolerance=1e-9*mean;
   for(int iteration=0;iteration<EMTT_ST_KMEANS_ITERATIONS;iteration++)
     {
      double sum[EMTT_ST_CLUSTERS];
      int    members[EMTT_ST_CLUSTERS];
      for(int c=0;c<EMTT_ST_CLUSTERS;c++)
        {
         sum[c]=0.0;
         members[c]=0;
        }
      for(int i=0;i<count;i++)
        {
         const int c=EmttStNearestCentre(centre,EMTT_ST_CLUSTERS,values[i]);
         sum[c]+=values[i];
         members[c]++;
        }
      double moved=0.0;
      for(int c=0;c<EMTT_ST_CLUSTERS;c++)
        {
         if(members[c]<=0)
            continue; // an empty cluster keeps its centre
         const double next=sum[c]/(double)members[c];
         moved=MathMax(moved,MathAbs(next-centre[c]));
         centre[c]=next;
        }
      if(moved<=tolerance)
         break;
     }

   // The final assignment against the settled centres gives the counts, and
   // the pairs are sorted ascending so index 0 is always Calm and index 2 is
   // always Wild - Lloyd alone does not guarantee that order.
   if(ArrayResize(centreOut,EMTT_ST_CLUSTERS)!=EMTT_ST_CLUSTERS)
      return false;
   if(ArrayResize(membersOut,EMTT_ST_CLUSTERS)!=EMTT_ST_CLUSTERS)
      return false;
   int finalMembers[EMTT_ST_CLUSTERS];
   for(int c=0;c<EMTT_ST_CLUSTERS;c++)
     {
      centreOut[c]=centre[c];
      finalMembers[c]=0;
     }
   for(int i=0;i<count;i++)
      finalMembers[EmttStNearestCentre(centreOut,EMTT_ST_CLUSTERS,values[i])]++;
   for(int a=1;a<EMTT_ST_CLUSTERS;a++)
     {
      const double keyCentre=centreOut[a];
      const int keyMembers=finalMembers[a];
      int b=a-1;
      while(b>=0 && centreOut[b]>keyCentre)
        {
         centreOut[b+1]=centreOut[b];
         finalMembers[b+1]=finalMembers[b];
         b--;
        }
      centreOut[b+1]=keyCentre;
      finalMembers[b+1]=keyMembers;
     }
   for(int c=0;c<EMTT_ST_CLUSTERS;c++)
      membersOut[c]=finalMembers[c];
   return true;
  }

//+------------------------------------------------------------------+
//| State lifecycle. The 3.0 default is the middle of the candidate  |
//| set, so an unlearned cluster is never outside the allowed range. |
//+------------------------------------------------------------------+
void EmttSupertrendReset(SEmttSupertrendState &state)
  {
   state.initialized=false;
   state.ready=false;
   state.window=0;
   state.retrainInterval=1;
   state.barsSinceTrain=0;
   state.assetClass=EMTT_CLASS_GENERIC;
   state.atrPeriod=0;
   state.volatility=EMTT_VOL_UNKNOWN;
   state.cluster=EMTT_ST_CLUSTER_NONE;
   state.multiplier=EMTT_ST_DEFAULT_MULTIPLIER;
   state.direction=0;
   state.line=0.0;
   state.score=0.0;
   state.barsSinceFlip=0;
   state.flipCount=0;
   state.distanceATRs=0.0;
   state.atrValue=0.0;
   state.sparseFallback=false;
   state.lastMultiplierChangeBar=-1000000;
   for(int c=0;c<EMTT_ST_CLUSTERS;c++)
     {
      state.centre[c]=0.0;
      state.members[c]=0;
      state.clusterMultiplier[c]=EMTT_ST_DEFAULT_MULTIPLIER;
      state.clusterLearned[c]=false;
     }
  }

//+------------------------------------------------------------------+
//| 11.6: the single 0.0-1.0 component score, from closed-bar facts  |
//| only. Flat has no score. It gates nothing in this phase and is   |
//| never shown; later phases sum one such score per component.      |
//+------------------------------------------------------------------+
double EmttSupertrendScore(const int direction,const double distanceATRs,
                           const int barsSinceFlip,const int flipCount)
  {
   if(direction==0)
      return 0.0;
   const double distancePart=EmttStClamp01(distanceATRs);
   const double agePart=EmttStClamp01((double)barsSinceFlip/EMTT_ST_AGE_SCALE_BARS);
   const double flipPart=EmttStClamp01(1.0-(double)flipCount/EMTT_ST_FLIP_SCALE_COUNT);
   return EMTT_ST_WEIGHT_DISTANCE*distancePart+
          EMTT_ST_WEIGHT_AGE*agePart+
          EMTT_ST_WEIGHT_FLIPS*flipPart;
  }

double EmttSupertrendDistanceATRs(const double close,const double line,
                                  const double atr,const int direction)
  {
   if(direction==0 || !EmttStValidPositive(atr) || !EmttStValid(line) ||
      !EmttStValid(close))
      return 0.0;
   const double raw=((close-line)/atr)*(double)direction;
   // Positive on the trade side of the line; 0 once price falls back
   // through it.
   return(raw>0.0 ? raw : 0.0);
  }

//+------------------------------------------------------------------+
//| 11.4 + 11.5: one retrain of the window's clusters and winners.   |
//+------------------------------------------------------------------+
bool EmttSupertrendTrain(SEmttSupertrendState &state,
                         const MqlRates &rates[],const double &atr[],
                         const int index,const int window,
                         const ENUM_TIMEFRAMES timeframe,
                         const datetime barTime,const bool writeJournal)
  {
   double values[];
   if(ArrayResize(values,window)!=window)
      return false;
   for(int k=0;k<window;k++)
     {
      values[k]=atr[index+k];
      if(!EmttStValidPositive(values[k]))
         return false;
     }

   double centre[];
   int members[];
   if(!EmttSupertrendCluster(values,window,centre,members))
      return false;

   int directions[];
   if(!EmttSupertrendReplayCandidates(rates,atr,index,window,directions))
      return false;

   for(int c=0;c<EMTT_ST_CLUSTERS;c++)
     {
      state.centre[c]=centre[c];
      state.members[c]=members[c];
      // Sparse guard: fewer than 5 bars never owns a learned multiplier.
      if(members[c]<EMTT_ST_MIN_MEMBERS)
         continue;
      double winner;
      if(EmttSupertrendSelectForCluster(rates,atr,index,window,directions,
                                        centre,c,winner))
        {
         state.clusterMultiplier[c]=winner;
         state.clusterLearned[c]=true;
        }
      // No completed segment for this cluster: its previous value stands.
     }

   if(writeJournal)
      PrintFormat("Emtt | Supertrend trained | window %d closed bars (%s x%.2f) | ATR period %d | clusters Calm %.6f (%d bars, %s) / Normal %.6f (%d bars, %s) / Wild %.6f (%d bars, %s) | bar %s",
                  window,EmttStTimeframeName(timeframe),
                  EmttLookbackScale(timeframe),state.atrPeriod,
                  state.centre[0],state.members[0],
                  EmttStMultiplierText(state.clusterMultiplier[0]),
                  state.centre[1],state.members[1],
                  EmttStMultiplierText(state.clusterMultiplier[1]),
                  state.centre[2],state.members[2],
                  EmttStMultiplierText(state.clusterMultiplier[2]),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   return true;
  }

//+------------------------------------------------------------------+
//| One closed bar of Supertrend context. Called from the replay and |
//| from the incremental closed-bar path only - never on a tick.     |
//| rates[] and atr[] are series-indexed (index 0 = newest closed    |
//| bar); atr[] holds ATR at atrPeriod for those same bars.          |
//+------------------------------------------------------------------+
bool EmttSupertrendAdvance(SEmttSupertrendState &state,
                           const MqlRates &rates[],const double &atr[],
                           const int index,
                           const EEmttAssetClass assetClass,
                           const int atrPeriod,
                           const EEmttVolatility volatility,
                           const ENUM_TIMEFRAMES timeframe,
                           const long barSequence,
                           const datetime barTime,
                           const bool forceRetrain,const bool writeJournal)
  {
   const int window=EmttSupertrendWindow(timeframe);
   if(index<0 || atrPeriod<=0 ||
      index+window>ArraySize(rates) || index+window>ArraySize(atr))
      return false;
   const double atrValue=atr[index];
   if(!EmttStValidPositive(atrValue))
      return false;

   state.atrValue=atrValue;
   state.retrainInterval=EmttSupertrendRetrainInterval(window);

   // 11.4 retrain cadence: the interval, or at once when the context that
   // produced the clusters changes, or after init / reopen / a reset.
   const bool contextChanged=(!state.initialized ||
                              state.assetClass!=assetClass ||
                              state.atrPeriod!=atrPeriod ||
                              state.window!=window ||
                              state.volatility!=volatility);
   const bool due=(contextChanged || forceRetrain ||
                   state.barsSinceTrain>=state.retrainInterval);
   if(due)
     {
      const int previousWindow=state.window;
      state.assetClass=assetClass;
      state.atrPeriod=atrPeriod;
      state.volatility=volatility;
      state.window=window;
      if(!EmttSupertrendTrain(state,rates,atr,index,window,timeframe,
                              barTime,writeJournal))
        {
         state.ready=false;
         return false;
        }
      state.barsSinceTrain=0;
      if(writeJournal && previousWindow>0 && previousWindow!=window)
         PrintFormat("Emtt | Supertrend training window %d -> %d closed bars | %s x%.2f | bar %s",
                     previousWindow,window,EmttStTimeframeName(timeframe),
                     EmttLookbackScale(timeframe),
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
     }
   else
      state.barsSinceTrain++;

   // Current cluster: nearest centre, an exact tie resolving to the calmer.
   // A sparse cluster borrows the nearest populated cluster's multiplier.
   const EEmttStCluster previousCluster=state.cluster;
   int nearestIndex,donor;
   double desired;
   EmttStResolveMultiplier(state,atrValue,nearestIndex,desired,donor);
   const EEmttStCluster nearest=(EEmttStCluster)nearestIndex;
   const bool sparse=(donor!=nearestIndex);
   if(sparse && writeJournal && !state.sparseFallback)
      PrintFormat("Emtt | Supertrend cluster %s holds %d bars, below %d | using multiplier %s from cluster %s | bar %s",
                  EmttStClusterName(nearest),state.members[nearestIndex],
                  EMTT_ST_MIN_MEMBERS,EmttStMultiplierText(desired),
                  EmttStClusterName((EEmttStCluster)donor),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   state.sparseFallback=sparse;
   state.cluster=nearest;

   // 9.2.3 guard rails: one change, then the same value stays put for two
   // closed bars. The pause governs the multiplier only - direction,
   // cluster and score are readings and are never delayed by it.
   if(!EmttStIsCandidate(desired))
      desired=EMTT_ST_DEFAULT_MULTIPLIER;
   const bool multiplierWanted=(MathAbs(desired-state.multiplier)>
                                EMTT_ST_SCORE_TIE);
   bool multiplierChanged=false;
   if(!state.initialized || previousCluster==EMTT_ST_CLUSTER_NONE)
     {
      state.multiplier=desired;
      state.lastMultiplierChangeBar=barSequence;
     }
   else if(multiplierWanted &&
           EmttCanChangeAt(barSequence,state.lastMultiplierChangeBar))
     {
      if(writeJournal)
         PrintFormat("Emtt | Supertrend multiplier %s -> %s | cluster %s -> %s | bar %s",
                     EmttStMultiplierText(state.multiplier),
                     EmttStMultiplierText(desired),
                     EmttStClusterName(previousCluster),
                     EmttStClusterName(nearest),
                     TimeToString(barTime,TIME_DATE|TIME_MINUTES));
      state.multiplier=desired;
      state.lastMultiplierChangeBar=barSequence;
      multiplierChanged=true;
     }

   // A cluster change is a reading: it is journaled even while the
   // multiplier itself is still inside its two-closed-bar pause.
   if(writeJournal && !multiplierChanged && nearest!=previousCluster &&
      previousCluster!=EMTT_ST_CLUSTER_NONE)
      PrintFormat("Emtt | Supertrend cluster %s -> %s | multiplier %s%s | bar %s",
                  EmttStClusterName(previousCluster),
                  EmttStClusterName(nearest),
                  EmttStMultiplierText(state.multiplier),
                  (multiplierWanted ? ", change waiting for its pause" : ""),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));

   // Readings from the live multiplier, on closed bars inside the window.
   const int previousDirection=state.direction;
   int directions[];
   int direction;
   double line;
   int barsSinceFlip,flipCount;
   if(!EmttSupertrendWalk(rates,atr,index,window,state.multiplier,directions,
                          direction,line,barsSinceFlip,flipCount))
     {
      state.ready=false;
      return false;
     }

   state.direction=direction;
   state.line=line;
   state.barsSinceFlip=barsSinceFlip;
   state.flipCount=flipCount;
   state.distanceATRs=EmttSupertrendDistanceATRs(rates[index].close,line,
                                                 atrValue,direction);
   state.score=EmttSupertrendScore(direction,state.distanceATRs,
                                   barsSinceFlip,flipCount);
   state.ready=true;
   state.initialized=true;

   if(writeJournal && previousDirection!=0 && direction!=previousDirection)
      PrintFormat("Emtt | Supertrend direction %s -> %s | cluster %s | multiplier %s | line %s | bar %s",
                  EmttStDirectionName(previousDirection),
                  EmttStDirectionName(direction),
                  EmttStClusterName(state.cluster),
                  EmttStMultiplierText(state.multiplier),
                  DoubleToString(line,5),
                  TimeToString(barTime,TIME_DATE|TIME_MINUTES));
   return true;
  }

//+------------------------------------------------------------------+
//| Panel text (11.8). Regime and Supertrend are never reconciled:   |
//| the clause states only what this component measured.             |
//+------------------------------------------------------------------+
string EmttSupertrendClause(const SEmttSupertrendState &state)
  {
   if(!state.ready || state.direction==0)
      return "";
   return EmttStClusterName(state.cluster)+" (Supertrend "+
          EmttStDirectionName(state.direction)+")";
  }

// Row 9 joins the Phase 2 regime sentence with this clause using " | ".
string EmttWhyWithSupertrend(const string regimeWhy,
                             const SEmttSupertrendState &state)
  {
   const string clause=EmttSupertrendClause(state);
   if(clause=="")
      return regimeWhy;
   if(regimeWhy=="" || regimeWhy=="--")
      return clause;
   return regimeWhy+" | "+clause;
  }

string EmttStatusForSupertrend()
  {
   return "Watching — Supertrend context only, no signal yet";
  }

#endif // EMTT_SUPERTREND_MQH
