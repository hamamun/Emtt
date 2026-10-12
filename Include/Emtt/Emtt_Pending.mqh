// Pending execution policy. Pure logic; broker state remains authoritative.
#ifndef EMTT_PENDING_MQH
#define EMTT_PENDING_MQH

#define EMTT_PENDING_RECOVERY_SECONDS 60
#define EMTT_PENDING_RETRY_SECONDS    5
#define EMTT_PENDING_DEFAULT_BARS     6
#define EMTT_PENDING_MAX_BARS         96

enum EEmttPendingReason
  {
   EMTT_PENDING_KEEP=0,
   EMTT_PENDING_EXPIRED,
   EMTT_PENDING_DISABLED,
   EMTT_PENDING_PARTIAL,
   EMTT_PENDING_RECOVERY,
   EMTT_PENDING_MARKET,
   EMTT_PENDING_TARGET,
   EMTT_PENDING_STOP,
   EMTT_PENDING_BLOCK,
   EMTT_PENDING_SIGNAL,
   EMTT_PENDING_CONFIDENCE,
   EMTT_PENDING_DISTANCE
  };

struct SEmttPendingCheck
  {
   datetime now;
   datetime deadline;
   datetime unavailableSince;
   bool autoTrading;
   bool partialFill;
   bool metadataReady;
   bool analysisReady;
   bool marketKnown;
   bool marketOpen;
   bool quoteReady;
   bool planMatches;
   int confidence;
   int threshold;
   int side;
   double entry;
   double stop;
   double target;
   double blockFarEdge;
   double bid;
   double ask;
   double closedPrice;
   double atr;
  };

int EmttPendingBars(const int requested)
  {
   if(requested<1) return 1;
   if(requested>EMTT_PENDING_MAX_BARS) return EMTT_PENDING_MAX_BARS;
   return requested;
  }

datetime EmttPendingDeadline(const datetime eligibleAt,const int periodSeconds,
                             const int bars,const int expectedUpperMinutes)
  {
   if(eligibleAt<=0 || periodSeconds<=0) return 0;
   long lifetime=(long)periodSeconds*EmttPendingBars(bars);
   if(expectedUpperMinutes>0 && (long)expectedUpperMinutes*60<lifetime)
      lifetime=(long)expectedUpperMinutes*60;
   return eligibleAt+lifetime;
  }

EEmttPendingReason EmttPendingDecision(const SEmttPendingCheck &c)
  {
   if(c.partialFill) return EMTT_PENDING_PARTIAL;
   if(!c.autoTrading) return EMTT_PENDING_DISABLED;
   if(c.deadline>0 && c.now>=c.deadline) return EMTT_PENDING_EXPIRED;
   // Absence of a quote or a component during loading is not invalidation.
   if(c.metadataReady && c.quoteReady)
     {
      const double liquidation=(c.side>0 ? c.bid : c.ask);
      if(c.target>0.0 && c.side*(liquidation-c.target)>=0.0)
         return EMTT_PENDING_TARGET;
      if(c.stop>0.0 && c.side*(liquidation-c.stop)<=0.0)
         return EMTT_PENDING_STOP;
     }
   if(c.marketKnown && !c.marketOpen) return EMTT_PENDING_MARKET;
   if(!c.metadataReady || !c.analysisReady)
     {
      if(c.unavailableSince>0 && c.now-c.unavailableSince>=EMTT_PENDING_RECOVERY_SECONDS)
         return EMTT_PENDING_RECOVERY;
      return EMTT_PENDING_KEEP;
     }
   if(!c.planMatches) return EMTT_PENDING_SIGNAL;
   if(c.confidence<c.threshold) return EMTT_PENDING_CONFIDENCE;
   if(c.blockFarEdge>0.0 && c.closedPrice>0.0 &&
      c.side*(c.closedPrice-c.blockFarEdge)<0.0)
      return EMTT_PENDING_BLOCK;
   // Distance reassessment uses a closed candle, never a transient tick.
   if(c.atr>0.0 && c.closedPrice>0.0 &&
      c.side*(c.closedPrice-c.entry)>2.0*c.atr)
      return EMTT_PENDING_DISTANCE;
   return EMTT_PENDING_KEEP;
  }

string EmttPendingReasonText(const EEmttPendingReason reason)
  {
   switch(reason)
     {
      case EMTT_PENDING_EXPIRED: return "entry validity expired";
      case EMTT_PENDING_DISABLED: return "Auto Trading OFF";
      case EMTT_PENDING_PARTIAL: return "partial fill: cancelling unfilled remainder";
      case EMTT_PENDING_RECOVERY: return "original setup could not be validated within 60 seconds";
      case EMTT_PENDING_MARKET: return "market closed";
      case EMTT_PENDING_TARGET: return "target reached before fill";
      case EMTT_PENDING_STOP: return "setup stop breached before fill";
      case EMTT_PENDING_BLOCK: return "originating order block invalidated";
      case EMTT_PENDING_SIGNAL: return "originating signal ended or reversed";
      case EMTT_PENDING_CONFIDENCE: return "confidence below auto-trade threshold";
      case EMTT_PENDING_DISTANCE: return "closed price moved beyond 2 ATR entry reach";
      default: return "";
     }
  }
#endif // EMTT_PENDING_MQH
