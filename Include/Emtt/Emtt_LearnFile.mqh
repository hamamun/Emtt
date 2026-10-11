//+------------------------------------------------------------------+
//|                                            Emtt_LearnFile.mqh    |
//| Phase 7: the learning record - one small file per symbol and     |
//| timeframe under MQL5\Files\Emtt_Learning\                        |
//| Spec: Emtt.md section 19.3                                       |
//+------------------------------------------------------------------+
//| This header owns the file only: the folder and the name, the     |
//| line grammar, the load, the whole-file rewrite through a .tmp    |
//| file and the rename, the cap, the version and the malformed-line |
//| rules. It draws nothing, places nothing and reads no chart.      |
//| A leftover .tmp from a crash is consumed by the init write of    |
//| 19.3 event 1: the rename moves it over the record, so the file   |
//| guard of 19.10 can forbid FileDelete and still leave no stale    |
//| .tmp behind after init.                                          |
//| ASCII source only (17.2 rule 9): every dash or glyph would be an |
//| escape, so this file contains no byte above 0x7F.                |
//+------------------------------------------------------------------+
#ifndef EMTT_LEARNFILE_MQH
#define EMTT_LEARNFILE_MQH

//--- 19.3 the file, the version and the cap --------------------------
#define EMTT_LEARN_VERSION "Emtt_Learning v1"
#define EMTT_LEARN_DIR     "Emtt_Learning"
#define EMTT_LEARN_EXT     ".learn"
#define EMTT_LEARN_CAP     500

//--- 19.4 the fixed vocabularies, in their one-hot order -------------
enum EEmttLearnMood
  {
   EMTT_LEARN_MOOD_TRENDING=0,
   EMTT_LEARN_MOOD_RANGING,
   EMTT_LEARN_MOOD_VOLATILE,
   EMTT_LEARN_MOOD_TRANSITION
  };

enum EEmttLearnSession
  {
   EMTT_LEARN_SESSION_ASIA=0,
   EMTT_LEARN_SESSION_LONDON,
   EMTT_LEARN_SESSION_NEWYORK
  };

enum EEmttLearnVol
  {
   EMTT_LEARN_VOL_LOW=0,
   EMTT_LEARN_VOL_NORMAL,
   EMTT_LEARN_VOL_HIGH
  };

//--- 19.3 the result words, in the 17.7 order ------------------------
enum EEmttLearnResult
  {
   EMTT_LEARN_RESULT_NONE=0,
   EMTT_LEARN_RESULT_TARGET,
   EMTT_LEARN_RESULT_STOP,
   EMTT_LEARN_RESULT_MISSED,
   EMTT_LEARN_RESULT_CANCELLED,
   EMTT_LEARN_RESULT_SIGNAL,
   EMTT_LEARN_RESULT_MARKET,
   EMTT_LEARN_RESULT_CHART
  };

//--- 19.3 the ticket state and the Entry kind ------------------------
#define EMTT_LEARN_STATE_PENDING 0
#define EMTT_LEARN_STATE_ACTIVE  1
#define EMTT_LEARN_STATE_CLOSED  2

#define EMTT_LEARN_ENTRY_MARKET 0
#define EMTT_LEARN_ENTRY_BLOCK  1

//+------------------------------------------------------------------+
//| One plan line of 19.3. Every member is a whole number, a double  | 
//| or a datetime, so the ticket is a simple structure: it can be    | 
//| copied by assignment when the cap drops a line.                  | 
//+------------------------------------------------------------------+
struct SEmttLearnTicket
  {
   bool     used;
   datetime startBarTime;   // the plan's start bar
   int      side;           // +1 BUY / -1 SELL
   int      confidence;     // the four-view whole number of 17.3
   int      views[4];       // trend / structure / flow / higher chart
   int      mood;           // EEmttLearnMood
   int      session;        // EEmttLearnSession
   int      vol;            // EEmttLearnVol
   double   entry;
   int      entryKind;      // EMTT_LEARN_ENTRY_MARKET / BLOCK
   double   stop;
   double   target;
   int      est;            // Expected Duration estimate, whole minutes
   int      spread;         // whole points
   int      state;          // pending / active / closed
   datetime reachedBarTime; // 0 until the Entry is reached
   int      result;         // EEmttLearnResult, NONE while open
   bool     shared;         // 17.7 marked the ending candle shared
   double   exitPrice;
   int      points;         // signed whole points
   int      candles;
   long     startSequence;  // memory only, never written (19.3)
  };

//+------------------------------------------------------------------+
//| The record of one symbol and timeframe. The tickets are held in  |
//| file order, oldest first; `openTicket` is the one plan line that |
//| is still pending or active, -1 when there is none.               |
//+------------------------------------------------------------------+
struct SEmttLearnFileState
  {
   string   symbol;         // exact chart symbol, broker suffix included
   string   tfName;         // "M5" / "M15" / "M30"
   string   filePath;       // relative to MQL5\Files
   string   nameText;       // the file's own name part, for the journal
   int      digits;         // the symbol's digits for every price
   bool     loaded;         // Load ran (a fresh start counts as loaded)
   bool     readOnly;       // unknown version: memory only, never overwrite
   bool     versionWarned;  // unknown-version journal already written
   bool     damagedWarned;  // malformed-line journal already written
   bool     writeFailed;    // last save failed, recovery line pending
   SEmttLearnTicket tickets[EMTT_LEARN_CAP];
   int      ticketCount;
   int      openTicket;     // index of the open plan line, -1 when none
   int      labeled;        // target or stop results
   int      wins;           // target results
   int      losses;         // stop results
  };

//+------------------------------------------------------------------+
//| Small local helpers. No EA helper is called from this component. |
//+------------------------------------------------------------------+
void EmttLearnTicketReset(SEmttLearnTicket &ticket)
  {
   ticket.used=false;
   ticket.startBarTime=0;
   ticket.side=0;
   ticket.confidence=0;
   for(int i=0;i<4;i++)
      ticket.views[i]=0;
   ticket.mood=EMTT_LEARN_MOOD_TRENDING;
   ticket.session=EMTT_LEARN_SESSION_ASIA;
   ticket.vol=EMTT_LEARN_VOL_NORMAL;
   ticket.entry=0.0;
   ticket.entryKind=EMTT_LEARN_ENTRY_MARKET;
   ticket.stop=0.0;
   ticket.target=0.0;
   ticket.est=0;
   ticket.spread=0;
   ticket.state=EMTT_LEARN_STATE_PENDING;
   ticket.reachedBarTime=0;
   ticket.result=EMTT_LEARN_RESULT_NONE;
   ticket.shared=false;
   ticket.exitPrice=0.0;
   ticket.points=0;
   ticket.candles=0;
   ticket.startSequence=-1;
  }

void EmttLearnFileReset(SEmttLearnFileState &state)
  {
   state.symbol="";
   state.tfName="";
   state.filePath="";
   state.nameText="";
   state.digits=0;
   state.loaded=false;
   state.readOnly=false;
   state.versionWarned=false;
   state.damagedWarned=false;
   state.writeFailed=false;
   state.ticketCount=0;
   state.openTicket=-1;
   state.labeled=0;
   state.wins=0;
   state.losses=0;
   for(int i=0;i<EMTT_LEARN_CAP;i++)
      EmttLearnTicketReset(state.tickets[i]);
  }

// Chart timeframe to the short name used in the file header and name.
string EmttLearnTfName(const ENUM_TIMEFRAMES timeframe)
  {
   const string name=EnumToString(timeframe);
   if(StringFind(name,"PERIOD_")==0)
      return StringSubstr(name,7);
   return name;
  }

// The 19.3 sanitiser: every character outside A-Z a-z 0-9 _ - . becomes _.
// Character codes keep the source ASCII-only (65-90 A-Z, 97-122 a-z,
// 48-57 0-9, 95 _, 45 -, 46 .).
string EmttLearnSanitize(const string value)
  {
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      const ushort ch=StringGetCharacter(value,i);
      const bool ok=((ch>=65 && ch<=90) || (ch>=97 && ch<=122) ||
                     (ch>=48 && ch<=57) || ch==95 || ch==45 || ch==46);
      out+=(ok ? StringSubstr(value,i,1) : "_");
     }
   return out;
  }

string EmttLearnFilePath(const string symbol,const string tfName)
  {
   return EMTT_LEARN_DIR+"\\"+EmttLearnSanitize(symbol)+"_"+
          EmttLearnSanitize(tfName)+EMTT_LEARN_EXT;
  }

string EmttLearnNameText(const string symbol,const string tfName)
  {
   return EmttLearnSanitize(symbol)+"_"+EmttLearnSanitize(tfName);
  }

// Trim spaces (32), CR (13) and LF (10) from both ends.
string EmttLearnTrim(const string value)
  {
   int from=0;
   int to=StringLen(value)-1;
   while(from<=to)
     {
      const ushort ch=StringGetCharacter(value,from);
      if(ch!=32 && ch!=13 && ch!=10)
         break;
      from++;
     }
   while(to>=from)
     {
      const ushort ch=StringGetCharacter(value,to);
      if(ch!=32 && ch!=13 && ch!=10)
         break;
      to--;
     }
   if(to<from)
      return "";
   return StringSubstr(value,from,to-from+1);
  }

string EmttLearnTimeText(const datetime value)
  {
   return TimeToString(value,TIME_DATE|TIME_MINUTES);
  }

//+------------------------------------------------------------------+
//| 19.3 the words of the grammar                                    |
//+------------------------------------------------------------------+
string EmttLearnMoodWord(const int mood)
  {
   if(mood==EMTT_LEARN_MOOD_TRENDING)   return "TRENDING";
   if(mood==EMTT_LEARN_MOOD_RANGING)    return "RANGING";
   if(mood==EMTT_LEARN_MOOD_VOLATILE)   return "VOLATILE";
   if(mood==EMTT_LEARN_MOOD_TRANSITION) return "TRANSITION";
   return "TRANSITION";
  }

int EmttLearnMoodFromWord(const string word)
  {
   if(word=="TRENDING")   return EMTT_LEARN_MOOD_TRENDING;
   if(word=="RANGING")    return EMTT_LEARN_MOOD_RANGING;
   if(word=="VOLATILE")   return EMTT_LEARN_MOOD_VOLATILE;
   if(word=="TRANSITION") return EMTT_LEARN_MOOD_TRANSITION;
   return -1;
  }

string EmttLearnSessionWord(const int session)
  {
   if(session==EMTT_LEARN_SESSION_ASIA)    return "ASIA";
   if(session==EMTT_LEARN_SESSION_LONDON)  return "LONDON";
   if(session==EMTT_LEARN_SESSION_NEWYORK) return "NEWYORK";
   return "ASIA";
  }

int EmttLearnSessionFromWord(const string word)
  {
   if(word=="ASIA")    return EMTT_LEARN_SESSION_ASIA;
   if(word=="LONDON")  return EMTT_LEARN_SESSION_LONDON;
   if(word=="NEWYORK") return EMTT_LEARN_SESSION_NEWYORK;
   return -1;
  }

string EmttLearnVolWord(const int vol)
  {
   if(vol==EMTT_LEARN_VOL_LOW)    return "LOW";
   if(vol==EMTT_LEARN_VOL_NORMAL) return "NORMAL";
   if(vol==EMTT_LEARN_VOL_HIGH)   return "HIGH";
   return "NORMAL";
  }

int EmttLearnVolFromWord(const string word)
  {
   if(word=="LOW")    return EMTT_LEARN_VOL_LOW;
   if(word=="NORMAL") return EMTT_LEARN_VOL_NORMAL;
   if(word=="HIGH")   return EMTT_LEARN_VOL_HIGH;
   return -1;
  }

string EmttLearnResultWord(const int result)
  {
   if(result==EMTT_LEARN_RESULT_TARGET)    return "target";
   if(result==EMTT_LEARN_RESULT_STOP)      return "stop";
   if(result==EMTT_LEARN_RESULT_MISSED)    return "missed";
   if(result==EMTT_LEARN_RESULT_CANCELLED) return "cancelled";
   if(result==EMTT_LEARN_RESULT_SIGNAL)    return "signal";
   if(result==EMTT_LEARN_RESULT_MARKET)    return "market";
   if(result==EMTT_LEARN_RESULT_CHART)     return "chart";
   return "";
  }

int EmttLearnResultFromWord(const string word)
  {
   if(word=="target")    return EMTT_LEARN_RESULT_TARGET;
   if(word=="stop")      return EMTT_LEARN_RESULT_STOP;
   if(word=="missed")    return EMTT_LEARN_RESULT_MISSED;
   if(word=="cancelled") return EMTT_LEARN_RESULT_CANCELLED;
   if(word=="signal")    return EMTT_LEARN_RESULT_SIGNAL;
   if(word=="market")    return EMTT_LEARN_RESULT_MARKET;
   if(word=="chart")     return EMTT_LEARN_RESULT_CHART;
   return -1;
  }

string EmttLearnEntryWord(const int entryKind)
  {
   return(entryKind==EMTT_LEARN_ENTRY_BLOCK ? "OB" : "market");
  }

string EmttLearnStateWord(const int state)
  {
   if(state==EMTT_LEARN_STATE_ACTIVE) return "active";
   if(state==EMTT_LEARN_STATE_CLOSED) return "closed";
   return "pending";
  }

int EmttLearnStateFromWord(const string word)
  {
   if(word=="pending") return EMTT_LEARN_STATE_PENDING;
   if(word=="active")  return EMTT_LEARN_STATE_ACTIVE;
   if(word=="closed")  return EMTT_LEARN_STATE_CLOSED;
   return -1;
  }

//+------------------------------------------------------------------+
//| The line grammar. A part is "key value"; the tail is the value   |
//| without its key and without the surrounding spaces.              |
//+------------------------------------------------------------------+
bool EmttLearnPartTail(const string part,const string key,string &tail)
  {
   const int keyLength=StringLen(key);
   if(keyLength<=0)
      return false;
   if(StringFind(part,key)!=0)
      return false;
   if(StringLen(part)<=keyLength)
      return false;
   if(StringGetCharacter(part,keyLength)!=32)
      return false;
   tail=EmttLearnTrim(StringSubstr(part,keyLength+1));
   return(StringLen(tail)>0);
  }

bool EmttLearnPartInt(const string part,const string key,int &value)
  {
   string tail="";
   if(!EmttLearnPartTail(part,key,tail))
      return false;
   const ushort first=StringGetCharacter(tail,0);
   if((first<48 || first>57) && first!=45 && first!=43)
      return false;
   for(int i=1;i<StringLen(tail);i++)
     {
      const ushort ch=StringGetCharacter(tail,i);
      if(ch<48 || ch>57)
         return false;
     }
   value=(int)StringToInteger(tail);
   return true;
  }

bool EmttLearnPartPrice(const string part,const string key,double &value)
  {
   string tail="";
   if(!EmttLearnPartTail(part,key,tail))
      return false;
   value=StringToDouble(tail);
   return(MathIsValidNumber(value) && value>0.0);
  }

bool EmttLearnPartTime(const string part,const string key,datetime &value)
  {
   string tail="";
   if(!EmttLearnPartTail(part,key,tail))
      return false;
   if(StringLen(tail)!=16)
      return false;
   if(StringGetCharacter(tail,4)!=46 || StringGetCharacter(tail,7)!=46 ||
      StringGetCharacter(tail,10)!=32 || StringGetCharacter(tail,13)!=58)
      return false;
   value=StringToTime(tail);
   return(value>0);
  }

string EmttLearnTicketLine(const SEmttLearnTicket &ticket,const int digits)
  {
   string line="plan "+EmttLearnTimeText(ticket.startBarTime)+
               " | "+(ticket.side>0 ? "BUY" : "SELL")+
               " | conf "+IntegerToString(ticket.confidence)+
               " | views "+IntegerToString(ticket.views[0])+","+
               IntegerToString(ticket.views[1])+","+
               IntegerToString(ticket.views[2])+","+
               IntegerToString(ticket.views[3])+
               " | mood "+EmttLearnMoodWord(ticket.mood)+
               " | session "+EmttLearnSessionWord(ticket.session)+
               " | vol "+EmttLearnVolWord(ticket.vol)+
               " | entry "+DoubleToString(ticket.entry,digits)+" "+
               EmttLearnEntryWord(ticket.entryKind)+
               " | stop "+DoubleToString(ticket.stop,digits)+
               " | target "+DoubleToString(ticket.target,digits)+
               " | est "+IntegerToString(ticket.est)+
               " | spread "+IntegerToString(ticket.spread)+
               " | state "+EmttLearnStateWord(ticket.state);
   if(ticket.reachedBarTime>0)
      line+=" | reached "+EmttLearnTimeText(ticket.reachedBarTime);
   if(ticket.result!=EMTT_LEARN_RESULT_NONE)
     {
      line+=" | result "+EmttLearnResultWord(ticket.result);
      if(ticket.shared)
         line+=" shared";
      line+=" | exit "+DoubleToString(ticket.exitPrice,digits)+
            " | points "+IntegerToString(ticket.points)+
            " | candles "+IntegerToString(ticket.candles);
     }
   return line;
  }

bool EmttLearnParseTicketLine(const string line,const int digits,
                              SEmttLearnTicket &ticket)
  {
   string parts[];
   const int count=StringSplit(line,'|',parts);
   if(count<13)
      return false;
   for(int i=0;i<count;i++)
      parts[i]=EmttLearnTrim(parts[i]);

   EmttLearnTicketReset(ticket);
   string tail="";

   // part 0: the plan's start bar time
   if(!EmttLearnPartTime(parts[0],"plan",ticket.startBarTime))
      return false;
   // part 1: the side
   if(parts[1]=="BUY")
      ticket.side=1;
   else if(parts[1]=="SELL")
      ticket.side=-1;
   else
      return false;
   // part 2: the four-view number of 17.3
   if(!EmttLearnPartInt(parts[2],"conf",ticket.confidence))
      return false;
   if(ticket.confidence<0 || ticket.confidence>100)
      return false;
   // part 3: the four published directions, in the 17.3 order
   if(!EmttLearnPartTail(parts[3],"views",tail))
      return false;
   string viewWords[];
   if(StringSplit(tail,',',viewWords)!=4)
      return false;
   for(int i=0;i<4;i++)
     {
      int value=(int)StringToInteger(EmttLearnTrim(viewWords[i]));
      if(value<-1 || value>1)
         return false;
      const string word=EmttLearnTrim(viewWords[i]);
      if(word!="1" && word!="0" && word!="-1")
         return false;
      ticket.views[i]=value;
     }
   // part 4: the mood of 17.2 rule 3
   if(!EmttLearnPartTail(parts[4],"mood",tail))
      return false;
   ticket.mood=EmttLearnMoodFromWord(tail);
   if(ticket.mood<0)
      return false;
   // part 5: the session of 15.3
   if(!EmttLearnPartTail(parts[5],"session",tail))
      return false;
   ticket.session=EmttLearnSessionFromWord(tail);
   if(ticket.session<0)
      return false;
   // part 6: the volatility bucket of 9.2
   if(!EmttLearnPartTail(parts[6],"vol",tail))
      return false;
   ticket.vol=EmttLearnVolFromWord(tail);
   if(ticket.vol<0)
      return false;
   // part 7: entry price and the entry kind
   {
      if(!EmttLearnPartTail(parts[7],"entry",tail))
         return false;
      string words[];
      const int wordCount=StringSplit(tail,' ',words);
      if(wordCount!=2)
         return false;
      ticket.entry=StringToDouble(EmttLearnTrim(words[0]));
      if(!MathIsValidNumber(ticket.entry) || ticket.entry<=0.0)
         return false;
      const string kind=EmttLearnTrim(words[1]);
      if(kind=="OB")
         ticket.entryKind=EMTT_LEARN_ENTRY_BLOCK;
      else if(kind=="market")
         ticket.entryKind=EMTT_LEARN_ENTRY_MARKET;
      else
         return false;
   }
   if(!EmttLearnPartPrice(parts[8],"stop",ticket.stop))
      return false;
   if(!EmttLearnPartPrice(parts[9],"target",ticket.target))
      return false;
   if(!EmttLearnPartInt(parts[10],"est",ticket.est))
      return false;
   if(!EmttLearnPartInt(parts[11],"spread",ticket.spread))
      return false;
   if(ticket.est<0 || ticket.spread<0)
      return false;
   // part 12: the state, and the optional parts after it
   if(!EmttLearnPartTail(parts[12],"state",tail))
      return false;
   ticket.state=EmttLearnStateFromWord(tail);
   if(ticket.state<0)
      return false;
   for(int i=13;i<count;i++)
     {
      if(EmttLearnPartTime(parts[i],"reached",ticket.reachedBarTime))
         continue;
      if(EmttLearnPartTail(parts[i],"result",tail))
        {
         string words[];
         const int wordCount=StringSplit(tail,' ',words);
         if(wordCount<1 || wordCount>2)
            return false;
         ticket.result=EmttLearnResultFromWord(EmttLearnTrim(words[0]));
         if(ticket.result<0)
            return false;
         if(wordCount==2)
           {
            if(EmttLearnTrim(words[1])!="shared")
               return false;
            ticket.shared=true;
           }
         continue;
        }
      if(EmttLearnPartPrice(parts[i],"exit",ticket.exitPrice))
         continue;
      if(EmttLearnPartInt(parts[i],"points",ticket.points))
         continue;
      if(EmttLearnPartInt(parts[i],"candles",ticket.candles))
         continue;
      return false;
     }
   if(ticket.state==EMTT_LEARN_STATE_CLOSED &&
      ticket.result==EMTT_LEARN_RESULT_NONE)
      return false;
   if(ticket.state!=EMTT_LEARN_STATE_CLOSED &&
      ticket.result!=EMTT_LEARN_RESULT_NONE)
      return false;
   if(ticket.candles<0)
      return false;
   ticket.used=true;
   return true;
  }

//+------------------------------------------------------------------+
//| The counts are recomputed from the ticket lines, never trusted    |
//| from the summary line (19.3).                                    |
//+------------------------------------------------------------------+
void EmttLearnFileRecomputeCounts(SEmttLearnFileState &state)
  {
   state.labeled=0;
   state.wins=0;
   state.losses=0;
   for(int i=0;i<state.ticketCount;i++)
     {
      const int result=state.tickets[i].result;
      if(result==EMTT_LEARN_RESULT_TARGET)
        {
         state.labeled++;
         state.wins++;
        }
      else if(result==EMTT_LEARN_RESULT_STOP)
        {
         state.labeled++;
         state.losses++;
        }
     }
  }

// The one plan line that is still pending or active, -1 when none.
int EmttLearnFileFindOpen(const SEmttLearnFileState &state)
  {
   for(int i=state.ticketCount-1;i>=0;i--)
      if(state.tickets[i].state!=EMTT_LEARN_STATE_CLOSED)
         return i;
   return -1;
  }

// 19.3 cap: drop the oldest closed ticket until a new line fits. An open
// plan line is never dropped.
void EmttLearnFileApplyCap(SEmttLearnFileState &state)
  {
   while(state.ticketCount>=EMTT_LEARN_CAP)
     {
      int drop=-1;
      for(int i=0;i<state.ticketCount;i++)
         if(state.tickets[i].state==EMTT_LEARN_STATE_CLOSED)
           {
            drop=i;
            break;
           }
      if(drop<0)
         return;
      for(int i=drop;i<state.ticketCount-1;i++)
         state.tickets[i]=state.tickets[i+1];
      EmttLearnTicketReset(state.tickets[state.ticketCount-1]);
      state.ticketCount--;
      if(state.openTicket>drop)
         state.openTicket--;
     }
  }

string EmttLearnCountsLine(const SEmttLearnFileState &state,
                           const datetime barTime)
  {
   const datetime stamp=(barTime>0 ? barTime : TimeCurrent());
   return "counts "+IntegerToString(state.ticketCount)+
          " | labeled "+IntegerToString(state.labeled)+
          " | wins "+IntegerToString(state.wins)+
          " | losses "+IntegerToString(state.losses)+
          " | updated "+EmttLearnTimeText(stamp);
  }

//+------------------------------------------------------------------+
//| Load: read every line, keep the version check of 19.3, skip a     |
//| malformed ticket line (journaled once per session) and recompute  |
//| the counts. A missing file is a fresh start.                     |
//+------------------------------------------------------------------+
int EmttLearnReadLines(const string filePath,string &lines[])
  {
   const int handle=FileOpen(filePath,FILE_READ|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
      return -1;
   int count=0;
   while(!FileIsEnding(handle))
     {
      const string line=EmttLearnTrim(FileReadString(handle));
      if(StringLen(line)==0)
         continue;
      ArrayResize(lines,count+1);
      lines[count]=line;
      count++;
     }
   FileClose(handle);
   return count;
  }

void EmttLearnFileLoad(SEmttLearnFileState &state,const string symbol,
                       const ENUM_TIMEFRAMES timeframe,const int digits,
                       const datetime barTime)
  {
   EmttLearnFileReset(state);
   const string barText=EmttLearnTimeText(barTime>0 ? barTime
                                                    : TimeCurrent());
   state.symbol=symbol;
   state.tfName=EmttLearnTfName(timeframe);
   state.filePath=EmttLearnFilePath(state.symbol,state.tfName);
   state.nameText=EmttLearnNameText(state.symbol,state.tfName);
   state.digits=digits;
   state.loaded=true;

   FolderCreate(EMTT_LEARN_DIR,0);
   string lines[];
   const int lineCount=EmttLearnReadLines(state.filePath,lines);
   if(lineCount<0)
     {
      PrintFormat("Emtt | Learning started | no file yet | %s | bar %s",
                  state.nameText,barText);
      return;
     }
   string head[];
   if(lineCount<1 || StringSplit(lines[0],'|',head)<1 ||
      EmttLearnTrim(head[0])!=EMTT_LEARN_VERSION)
     {
      state.readOnly=true;
      if(!state.versionWarned)
        {
         PrintFormat("Emtt | Learning version unknown | file untouched, memory only | %s | bar %s",
                     state.filePath,barText);
         state.versionWarned=true;
        }
      return;
     }

   int damaged=0;
   for(int i=1;i<lineCount;i++)
     {
      const string record=EmttLearnTrim(lines[i]);
      if(record=="")
         continue;                    // a trailing line end is not damage
      if(StringFind(record,"counts")==0)
         continue;                    // line 2, for the reader only (19.3)
      SEmttLearnTicket ticket;
      if(!EmttLearnParseTicketLine(record,state.digits,ticket))
        {
         damaged++;
         continue;
        }
      if(state.ticketCount>=EMTT_LEARN_CAP)
        {
         damaged++;
         continue;
        }
      state.tickets[state.ticketCount]=ticket;
      state.ticketCount++;
     }
   EmttLearnFileRecomputeCounts(state);
   state.openTicket=EmttLearnFileFindOpen(state);
   if(damaged>0 && !state.damagedWarned)
     {
      PrintFormat("Emtt | Learning file damaged | %d malformed ticket lines skipped, the rest kept | %s | bar %s",
                  damaged,state.filePath,barText);
      state.damagedWarned=true;
     }
   // Line 2 is a summary for the reader only: the counts were recomputed
   // above and a summary that disagrees is ignored (19.3). The warm-up is
   // the 30 of 19.8 (EMTT_LEARN_WARMUP, in Emtt_Learning.mqh, which is
   // included after this header), so the line spells it out.
   PrintFormat("Emtt | Learning loaded | %d plans, %d labeled, %d wins, %d losses | warming %d/30 | bar %s",
               state.ticketCount,state.labeled,state.wins,state.losses,
               state.labeled,barText);
  }

//+------------------------------------------------------------------+
//| Whole-file rewrite through a .tmp file and a rename, so a crash  |
//| or a second instance never leaves a half-written record. Quiet   |
//| on success; one busy line on failure, one recovered line after.  |
//+------------------------------------------------------------------+
bool EmttLearnFileSave(SEmttLearnFileState &state,const datetime barTime)
  {
   if(!state.loaded || state.readOnly || state.filePath=="")
      return false;
   FolderCreate(EMTT_LEARN_DIR,0);
   const string tmpPath=state.filePath+".tmp";
   const string stampText=EmttLearnTimeText(barTime>0 ? barTime
                                                      : TimeCurrent());
   ResetLastError();
   const int handle=FileOpen(tmpPath,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
     {
      if(!state.writeFailed)
        {
         PrintFormat("Emtt | Learning file busy | learning kept in memory | bar %s",
                     stampText);
         state.writeFailed=true;
        }
      return false;
     }
   FileWriteString(handle,EMTT_LEARN_VERSION+" | "+state.symbol+" | "+
                   state.tfName+"\r\n");
   FileWriteString(handle,EmttLearnCountsLine(state,barTime)+"\r\n");
   for(int i=0;i<state.ticketCount;i++)
      FileWriteString(handle,
                      EmttLearnTicketLine(state.tickets[i],state.digits)+
                      "\r\n");
   FileClose(handle);
   if(!FileMove(tmpPath,0,state.filePath,FILE_REWRITE))
     {
      if(!state.writeFailed)
        {
         PrintFormat("Emtt | Learning file busy | learning kept in memory | bar %s",
                     stampText);
         state.writeFailed=true;
        }
      return false;
     }
   if(state.writeFailed)
     {
      PrintFormat("Emtt | Learning write recovered | bar %s",stampText);
      state.writeFailed=false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| The three ticket events of 19.3. Each returns the plan line slot |
//| so the caller can journal and save.                              |
//+------------------------------------------------------------------+
int EmttLearnFileAddPlan(SEmttLearnFileState &state,
                         const SEmttLearnTicket &ticket)
  {
   EmttLearnFileApplyCap(state);
   if(state.ticketCount>=EMTT_LEARN_CAP)
      return -1;
   state.tickets[state.ticketCount]=ticket;
   state.tickets[state.ticketCount].used=true;
   state.ticketCount++;
   state.openTicket=state.ticketCount-1;
   EmttLearnFileRecomputeCounts(state);
   return state.openTicket;
  }

bool EmttLearnFileMarkReached(SEmttLearnFileState &state,const int slot,
                              const datetime barTime)
  {
   if(slot<0 || slot>=state.ticketCount)
      return false;
   if(state.tickets[slot].state!=EMTT_LEARN_STATE_PENDING)
      return false;
   state.tickets[slot].state=EMTT_LEARN_STATE_ACTIVE;
   state.tickets[slot].reachedBarTime=barTime;
   return true;
  }

bool EmttLearnFileCloseTicket(SEmttLearnFileState &state,const int slot,
                              const int result,const bool shared,
                              const double exitPrice,const int points,
                              const int candles)
  {
   if(slot<0 || slot>=state.ticketCount)
      return false;
   if(result==EMTT_LEARN_RESULT_NONE)
      return false;
   state.tickets[slot].state=EMTT_LEARN_STATE_CLOSED;
   state.tickets[slot].result=result;
   state.tickets[slot].shared=shared;
   state.tickets[slot].exitPrice=exitPrice;
   state.tickets[slot].points=points;
   state.tickets[slot].candles=candles;
   if(state.openTicket==slot)
      state.openTicket=-1;
   EmttLearnFileRecomputeCounts(state);
   return true;
  }

#endif // EMTT_LEARNFILE_MQH
