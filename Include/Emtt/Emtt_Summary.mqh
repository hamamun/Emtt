//+------------------------------------------------------------------+
//|                                             Emtt_Summary.mqh     |
//| Panel revamp: Today / All-Time signal stats, persisted per       |
//| symbol and timeframe (author direction 2026-10-11)               |
//+------------------------------------------------------------------+
//| Every plan the signal engine starts counts one signal; a plan    |
//| ending at its target counts a win, at its stop a loss, every     |
//| other result neither (the Phase 7 labels of 19.4). Counts live   |
//| in memory and in one small text file per symbol and timeframe    |
//| under MQL5\Files\Emtt_Learning\, the same folder and naming as   |
//| the Phase 7 learning record of 19.3, with a .summary suffix so   |
//| the two records never collide. The file is rewritten whole on    |
//| signal start, win, loss, day rollover, init and deinit - never   |
//| per tick. ASCII source only: no glyph, no dash, no byte > 0x7F.  |
//+------------------------------------------------------------------+
#ifndef EMTT_SUMMARY_MQH
#define EMTT_SUMMARY_MQH

#define EMTT_SUMMARY_VERSION "Emtt_Summary v1"
#define EMTT_SUMMARY_DIR "Emtt_Learning"
#define EMTT_SUMMARY_EXT ".summary"

//+------------------------------------------------------------------+
//| One chart's counts. Today rolls at the server date change;       |
//| All-Time never resets.                                           |
//+------------------------------------------------------------------+
struct SEmttSummaryState
  {
   string symbol;        // raw chart symbol, e.g. "BTCUSDm"
   string tfName;        // "M5" / "M15" / "M30" (or any chart TF)
   string filePath;      // relative to MQL5\Files, e.g. Emtt_Learning\BTCUSDm_M30.summary
   string todayDate;     // "YYYY.MM.DD" of the Today counts
   int    todaySignals;
   int    todayWins;
   int    todayLosses;
   int    allSignals;
   int    allWins;
   int    allLosses;
   bool   loaded;        // Init ran (a fresh start counts as loaded)
   bool   readOnly;      // unknown file version: memory only, never overwrite
   bool   versionWarned; // unknown-version journal already written
   bool   writeFailed;   // last save failed, recovery line pending
  };

void EmttSummaryReset(SEmttSummaryState &state)
  {
   state.symbol="";
   state.tfName="";
   state.filePath="";
   state.todayDate="";
   state.todaySignals=0;
   state.todayWins=0;
   state.todayLosses=0;
   state.allSignals=0;
   state.allWins=0;
   state.allLosses=0;
   state.loaded=false;
   state.readOnly=false;
   state.versionWarned=false;
   state.writeFailed=false;
  }

// Chart timeframe to the short name used in the file header and name.
string EmttSummaryTfName(const ENUM_TIMEFRAMES timeframe)
  {
   const string name=EnumToString(timeframe);
   if(StringFind(name,"PERIOD_")==0)
      return StringSubstr(name,7);
   return name;
  }

// The 19.3 sanitiser: every character outside A-Z a-z 0-9 _ - . becomes _.
// Integer codes keep the source ASCII-only (65-90 A-Z, 97-122 a-z,
// 48-57 0-9, 95 _, 45 -, 46 .).
string EmttSummarySanitize(const string value)
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

string EmttSummaryFilePath(const string symbol,const string tfName)
  {
   return EMTT_SUMMARY_DIR+"\\"+EmttSummarySanitize(symbol)+"_"+
          EmttSummarySanitize(tfName)+EMTT_SUMMARY_EXT;
  }

// Server date as "YYYY.MM.DD"; empty when the terminal has no time yet.
string EmttSummaryCurrentDate()
  {
   datetime now=TimeCurrent();
   if(now<=0)
      now=TimeGMT();
   if(now<=0)
      return "";
   return TimeToString(now,TIME_DATE);
  }

// Trim spaces (32), CR (13) and LF (10) from both ends.
string EmttSummaryTrim(const string value)
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

// The trailing whole number of a "word N" part; -1 when missing or invalid.
int EmttSummaryPartInt(const string part)
  {
   string words[];
   const int n=StringSplit(part,' ',words);
   for(int i=n-1;i>=0;i--)
     {
      if(StringLen(words[i])==0)
         continue;
      const ushort first=StringGetCharacter(words[i],0);
      if((first<48 || first>57) && first!=45)
         return -1;
      return (int)StringToInteger(words[i]);
     }
   return -1;
  }

//+------------------------------------------------------------------+
//| Load the file into the state. A missing file is a fresh start;   |
//| an unknown version leaves the file untouched (memory only for    |
//| the session, the 19.3 rule); a malformed file starts fresh and   |
//| is rewritten clean on the next save.                             |
//+------------------------------------------------------------------+
void EmttSummaryLoad(SEmttSummaryState &state)
  {
   FolderCreate(EMTT_SUMMARY_DIR,0);
   const int handle=FileOpen(state.filePath,FILE_READ|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("Emtt | Summary started | no file yet | %s",state.filePath);
      return;
     }
   string lines[3];
   int count=0;
   while(!FileIsEnding(handle) && count<3)
     {
      lines[count]=FileReadString(handle);
      count++;
     }
   FileClose(handle);

   string head[];
   if(count<1 || StringSplit(lines[0],'|',head)!=3 ||
      EmttSummaryTrim(head[0])!=EMTT_SUMMARY_VERSION)
     {
      state.readOnly=true;
      if(!state.versionWarned)
        {
         PrintFormat("Emtt | Summary version unknown | file untouched, memory only | %s",
                     state.filePath);
         state.versionWarned=true;
        }
      return;
     }

   bool malformed=false;
   string parts[];
   if(count>=2 && StringSplit(lines[1],'|',parts)==4)
     {
      string dateWords[];
      string date="";
      if(StringSplit(EmttSummaryTrim(parts[0]),' ',dateWords)==2)
         date=EmttSummaryTrim(dateWords[1]);
      const int s=EmttSummaryPartInt(parts[1]);
      const int w=EmttSummaryPartInt(parts[2]);
      const int l=EmttSummaryPartInt(parts[3]);
      if(StringLen(date)==10 && StringGetCharacter(date,4)==46 &&
         StringGetCharacter(date,7)==46 && s>=0 && w>=0 && l>=0)
        {
         state.todayDate=date;
         state.todaySignals=s;
         state.todayWins=w;
         state.todayLosses=l;
        }
      else
         malformed=true;
     }
   else
      malformed=true;

   if(count>=3 && StringSplit(lines[2],'|',parts)==3)
     {
      const int s=EmttSummaryPartInt(parts[0]);
      const int w=EmttSummaryPartInt(parts[1]);
      const int l=EmttSummaryPartInt(parts[2]);
      if(s>=0 && w>=0 && l>=0)
        {
         state.allSignals=s;
         state.allWins=w;
         state.allLosses=l;
        }
      else
         malformed=true;
     }
   else
      malformed=true;

   if(malformed)
     {
      // A damaged file never seeds half counts: fresh zeros, rewritten
      // clean on the next save.
      state.todayDate=EmttSummaryCurrentDate();
      state.todaySignals=0;
      state.todayWins=0;
      state.todayLosses=0;
      state.allSignals=0;
      state.allWins=0;
      state.allLosses=0;
      PrintFormat("Emtt | Summary file malformed | starting fresh | %s",
                  state.filePath);
      return;
     }
   PrintFormat("Emtt | Summary loaded | today %s %d signals, %d wins, %d losses | alltime %d signals, %d wins, %d losses",
               state.todayDate,state.todaySignals,state.todayWins,
               state.todayLosses,state.allSignals,state.allWins,
               state.allLosses);
  }

//+------------------------------------------------------------------+
//| Whole-file rewrite through a .tmp file plus rename, so a crash   |
//| or a second instance never leaves a half-written file. Quiet on  |
//| success; one busy line on failure, one recovered line after.     |
//+------------------------------------------------------------------+
bool EmttSummarySave(SEmttSummaryState &state)
  {
   if(!state.loaded || state.readOnly)
      return false;
   if(state.filePath=="")
      return false;
   FolderCreate(EMTT_SUMMARY_DIR,0);
   const string tmpPath=state.filePath+".tmp";
   ResetLastError();
   const int handle=FileOpen(tmpPath,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
     {
      if(!state.writeFailed)
        {
         PrintFormat("Emtt | Summary file busy | kept in memory | %s",
                     state.filePath);
         state.writeFailed=true;
        }
      return false;
     }
   FileWriteString(handle,EMTT_SUMMARY_VERSION+" | "+state.symbol+" | "+
                   state.tfName+"\r\n");
   FileWriteString(handle,"today "+state.todayDate+" | signals "+
                   IntegerToString(state.todaySignals)+" | wins "+
                   IntegerToString(state.todayWins)+" | losses "+
                   IntegerToString(state.todayLosses)+"\r\n");
   FileWriteString(handle,"alltime signals "+
                   IntegerToString(state.allSignals)+" | wins "+
                   IntegerToString(state.allWins)+" | losses "+
                   IntegerToString(state.allLosses)+"\r\n");
   FileClose(handle);
   if(!FileMove(tmpPath,0,state.filePath,FILE_REWRITE))
     {
      if(!state.writeFailed)
        {
         PrintFormat("Emtt | Summary file busy | kept in memory | %s",
                     state.filePath);
         state.writeFailed=true;
        }
      return false;
     }
   if(state.writeFailed)
     {
      PrintFormat("Emtt | Summary write recovered | %s",state.filePath);
      state.writeFailed=false;
     }
   return true;
  }

// Reset the Today counts when the server date changed. True when it rolled.
bool EmttSummaryRollover(SEmttSummaryState &state)
  {
   if(!state.loaded || state.filePath=="")
      return false;
   const string nowDate=EmttSummaryCurrentDate();
   if(nowDate=="" || nowDate==state.todayDate)
      return false;
   state.todayDate=nowDate;
   state.todaySignals=0;
   state.todayWins=0;
   state.todayLosses=0;
   PrintFormat("Emtt | Summary new day | %s | alltime %d signals, %d wins, %d losses",
               nowDate,state.allSignals,state.allWins,state.allLosses);
   EmttSummarySave(state);
   return true;
  }

// Best-effort quiet refresh so two charts on the same symbol + timeframe
// share one file without losing each other's counts. Never journals and
// never resets: a missing or malformed file keeps the memory counts.
void EmttSummaryRefreshQuiet(SEmttSummaryState &state)
  {
   if(!state.loaded || state.readOnly || state.filePath=="")
      return;
   const int handle=FileOpen(state.filePath,FILE_READ|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
      return;
   string lines[3];
   int count=0;
   while(!FileIsEnding(handle) && count<3)
     {
      lines[count]=FileReadString(handle);
      count++;
     }
   FileClose(handle);
   if(count<3)
      return;
   string head[];
   if(StringSplit(lines[0],'|',head)!=3)
      return;
   if(EmttSummaryTrim(head[0])!=EMTT_SUMMARY_VERSION)
      return;
   string parts[];
   if(StringSplit(lines[1],'|',parts)==4)
     {
      string dateWords[];
      string date="";
      if(StringSplit(EmttSummaryTrim(parts[0]),' ',dateWords)==2)
         date=EmttSummaryTrim(dateWords[1]);
      const int s=EmttSummaryPartInt(parts[1]);
      const int w=EmttSummaryPartInt(parts[2]);
      const int l=EmttSummaryPartInt(parts[3]);
      if(StringLen(date)==10 && s>=0 && w>=0 && l>=0)
        {
         state.todayDate=date;
         state.todaySignals=s;
         state.todayWins=w;
         state.todayLosses=l;
        }
     }
   if(StringSplit(lines[2],'|',parts)==3)
     {
      const int s=EmttSummaryPartInt(parts[0]);
      const int w=EmttSummaryPartInt(parts[1]);
      const int l=EmttSummaryPartInt(parts[2]);
      if(s>=0 && w>=0 && l>=0)
        {
         state.allSignals=s;
         state.allWins=w;
         state.allLosses=l;
        }
     }
  }

// A started plan is one signal (Today + All-Time).
void EmttSummaryOnSignal(SEmttSummaryState &state)
  {
   if(!state.loaded)
      return;
   EmttSummaryRefreshQuiet(state);
   EmttSummaryRollover(state);
   state.todaySignals++;
   state.allSignals++;
   EmttSummarySave(state);
  }

// Target reached is a win.
void EmttSummaryOnWin(SEmttSummaryState &state)
  {
   if(!state.loaded)
      return;
   EmttSummaryRefreshQuiet(state);
   EmttSummaryRollover(state);
   state.todayWins++;
   state.allWins++;
   EmttSummarySave(state);
  }

// Stop reached is a loss.
void EmttSummaryOnLoss(SEmttSummaryState &state)
  {
   if(!state.loaded)
      return;
   EmttSummaryRefreshQuiet(state);
   EmttSummaryRollover(state);
   state.todayLosses++;
   state.allLosses++;
   EmttSummarySave(state);
  }

// Bind the state to one symbol + timeframe file and normalise it.
void EmttSummaryInit(SEmttSummaryState &state,const string symbol,
                     const ENUM_TIMEFRAMES timeframe)
  {
   EmttSummaryReset(state);
   state.symbol=symbol;
   state.tfName=EmttSummaryTfName(timeframe);
   state.filePath=EmttSummaryFilePath(symbol,state.tfName);
   state.todayDate=EmttSummaryCurrentDate();
   EmttSummaryLoad(state);
   state.loaded=true;
   EmttSummaryRollover(state);
   EmttSummarySave(state);
  }

string EmttSummaryTodayText(const SEmttSummaryState &state)
  {
   return "Today: Num of Signal: "+IntegerToString(state.todaySignals)+
          ", Win: "+IntegerToString(state.todayWins)+
          ", Loss: "+IntegerToString(state.todayLosses);
  }

string EmttSummaryAllTimeText(const SEmttSummaryState &state)
  {
   return "All Time: Num of Signal: "+IntegerToString(state.allSignals)+
          ", Win: "+IntegerToString(state.allWins)+
          ", Loss: "+IntegerToString(state.allLosses);
  }

#endif // EMTT_SUMMARY_MQH
