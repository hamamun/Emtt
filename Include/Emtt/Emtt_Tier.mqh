//+------------------------------------------------------------------+
//|                                                Emtt_Tier.mqh     |
//| Phase 11: graded confidence tiers and the auto-trade threshold    |
//| (Emtt.md 27 / 28). Pure logic: no order call, no chart object,    |
//| no file, no handle, no clock. ASCII source only; display dashes   |
//| are escaped at runtime.                                           |
//+------------------------------------------------------------------+
//| The tiers grade the displayed confidence number. They change only |
//| what the panel shows and which displayed plans may be traded; the |
//| confidence number itself, the four views, the plan builder and    |
//| every management parameter are untouched.                        |
//+------------------------------------------------------------------+
#ifndef EMTT_TIER_MQH
#define EMTT_TIER_MQH

//--- 28.2 tier boundaries (whole-number confidence) -------------------
#define EMTT_TIER_DISPLAY_MIN     35     // below: WAIT, "Very low"
#define EMTT_TIER_LOW_MAX         45     // 35-45 Low confidence
#define EMTT_TIER_NORMAL_MAX      55     // 46-55 Normal
#define EMTT_TIER_CONFIDENT_MAX   70     // 56-70 Confident, 71+ High
//--- 28.4 the "Auto-trade above (%)" input ----------------------------
#define EMTT_TIER_AUTO_MIN        35
#define EMTT_TIER_AUTO_MAX        100
#define EMTT_TIER_AUTO_DEFAULT    56
//--- 28.5 lot-size multipliers by tier (21.5 row b) -------------------
#define EMTT_TIER_SIZE_LOW        0.7
#define EMTT_TIER_SIZE_NORMAL     1.0
#define EMTT_TIER_SIZE_CONFIDENT  1.2
#define EMTT_TIER_SIZE_HIGH       1.5

enum EEmttTier
  {
   EMTT_TIER_NONE=0,        // no number (loading / closed / incompatible)
   EMTT_TIER_VERY_LOW=1,    // < 35: WAIT
   EMTT_TIER_LOW=2,         // 35-45
   EMTT_TIER_NORMAL=3,      // 46-55
   EMTT_TIER_CONFIDENT=4,   // 56-70
   EMTT_TIER_HIGH=5         // 71+
  };

int EmttTierOf(const int confidence)
  {
   if(confidence<0)
      return EMTT_TIER_NONE;
   if(confidence<EMTT_TIER_DISPLAY_MIN)
      return EMTT_TIER_VERY_LOW;
   if(confidence<=EMTT_TIER_LOW_MAX)
      return EMTT_TIER_LOW;
   if(confidence<=EMTT_TIER_NORMAL_MAX)
      return EMTT_TIER_NORMAL;
   if(confidence<=EMTT_TIER_CONFIDENT_MAX)
      return EMTT_TIER_CONFIDENT;
   return EMTT_TIER_HIGH;
  }

// The Row 3 label of each tier.
string EmttTierLabel(const int tier)
  {
   switch(tier)
     {
      case EMTT_TIER_VERY_LOW:  return "Very low";
      case EMTT_TIER_LOW:       return "Low confidence";
      case EMTT_TIER_NORMAL:    return "Normal";
      case EMTT_TIER_CONFIDENT: return "Confident";
      case EMTT_TIER_HIGH:      return "High confidence";
      default:                  return "";
     }
  }

// Every tier from 35% shows its direction; below 35% the SIGNAL is WAIT.
bool EmttTierShowsDirection(const int confidence)
  {
   return (confidence>=EMTT_TIER_DISPLAY_MIN);
  }

// Row 3: one line whenever a number exists, "--%" only when none does.
string EmttTierConfidenceRow(const int confidence)
  {
   if(confidence<0)
      return "Confidence: --%";
   return "Confidence: "+IntegerToString(confidence)+"% \x2014 "+
          EmttTierLabel(EmttTierOf(confidence));
  }

// 28.5: the lot multiplier of the tier a displayed plan is traded at.
double EmttTierSizeMultiplier(const int confidence)
  {
   const int tier=EmttTierOf(confidence);
   if(tier==EMTT_TIER_HIGH)      return EMTT_TIER_SIZE_HIGH;
   if(tier==EMTT_TIER_CONFIDENT) return EMTT_TIER_SIZE_CONFIDENT;
   if(tier==EMTT_TIER_NORMAL)    return EMTT_TIER_SIZE_NORMAL;
   // Low; a below-35 number never reaches an order (threshold >= 35).
   return EMTT_TIER_SIZE_LOW;
  }

// 28.4: whole numbers 35..100; anything outside is clamped.
int EmttTierAutoTradeAbove(const int value)
  {
   if(value<EMTT_TIER_AUTO_MIN)
      return EMTT_TIER_AUTO_MIN;
   if(value>EMTT_TIER_AUTO_MAX)
      return EMTT_TIER_AUTO_MAX;
   return value;
  }

// An order may be sent when the displayed confidence reaches the input.
bool EmttTierAutoTradeAllowed(const int confidence,const int autoTradeAbove)
  {
   return (confidence>=EMTT_TIER_DISPLAY_MIN && confidence>=autoTradeAbove);
  }

string EmttTierSideName(const int side)
  {
   return (side>0 ? "BUY" : (side<0 ? "SELL" : "WAIT"));
  }

// 28.6 STATUS: the below-35% WAIT line with the real number.
string EmttTierWatchingLine(const int confidence)
  {
   return "Watching \x2014 confidence "+IntegerToString(confidence)+"% ("+
          EmttTierLabel(EMTT_TIER_VERY_LOW)+"), no trade.";
  }

// 28.6 STATUS: a displayed tier below the user's auto-trade threshold.
string EmttTierBelowThresholdLine(const int confidence,const int side,
                                  const int autoTradeAbove)
  {
   return "Signal active \x2014 "+EmttTierLabel(EmttTierOf(confidence))+" "+
          EmttTierSideName(side)+", watching (auto-trade threshold "+
          IntegerToString(autoTradeAbove)+"%).";
  }

#endif // EMTT_TIER_MQH
