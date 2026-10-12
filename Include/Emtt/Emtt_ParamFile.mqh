//+------------------------------------------------------------------+
//|                                             Emtt_ParamFile.mqh   |
//| Phase 9: isolated, six-line parameter record (Emtt.md 23.7)       |
//| ASCII only. No chart, orders, model, or measurement changes.     |
//| As in 19.3, the init rewrite consumes a stale .tmp by truncating  |
//| it and renaming it, without a deletion API (23.10 file guard).   |
//+------------------------------------------------------------------+
#ifndef EMTT_PARAMFILE_MQH
#define EMTT_PARAMFILE_MQH

#include "Emtt_LearnFile.mqh"

#define EMTT_POPT_VERSION "Emtt_Params v1"
#define EMTT_POPT_DIR "Emtt_Learning"
#define EMTT_POPT_SUFFIX ".params"
#define EMTT_POPT_CELLS 4

struct SEmttParamCell
  {
   int  bar;
   int  base;
   long aW;
   long aL;
   long nW;
   long nL;
   long moves;
  };

struct SEmttParamFileState
  {
   string symbol;
   string tfName;
   string filePath;
   bool   loaded;
   bool   readOnly;
   bool   readPending;     // never overwrite a record we could not read
   bool   writeFailed;
   bool   damagedWarned[EMTT_POPT_CELLS];
   SEmttParamCell cells[EMTT_POPT_CELLS];
  };

int EmttParamBaseBar(const int mood)
  {
   if(mood==EMTT_LEARN_MOOD_TRENDING) return 60;
   if(mood==EMTT_LEARN_MOOD_TRANSITION) return 75;
   return 70;
  }

bool EmttParamBarApproved(const int bar)
  {
   return(bar==60 || bar==70 || bar==75);
  }

void EmttParamCellReset(SEmttParamCell &cell,const int mood)
  {
   cell.base=EmttParamBaseBar(mood);
   cell.bar=cell.base;
   cell.aW=0;
   cell.aL=0;
   cell.nW=0;
   cell.nL=0;
   cell.moves=0;
  }

void EmttParamFileReset(SEmttParamFileState &state)
  {
   state.symbol="";
   state.tfName="";
   state.filePath="";
   state.loaded=false;
   state.readOnly=false;
   state.readPending=false;
   state.writeFailed=false;
   for(int i=0;i<EMTT_POPT_CELLS;i++)
     {
      EmttParamCellReset(state.cells[i],i);
      state.damagedWarned[i]=false;
     }
  }

string EmttParamFilePath(const string symbol,const string tfName)
  {
   return EMTT_POPT_DIR+"\\"+EmttLearnSanitize(symbol)+"_"+
          EmttLearnSanitize(tfName)+EMTT_POPT_SUFFIX;
  }

// Non-negative 64-bit integers, not StringToInteger's permissive prefix
// conversion. The round-trip also rejects overflow and a sign without digits.
bool EmttParamWhole(const string word,long &value)
  {
   const int length=StringLen(word);
   if(length<1 || length>19) return false;
   for(int i=0;i<length;i++)
     {
      const ushort ch=StringGetCharacter(word,i);
      if(ch<48 || ch>57) return false;
     }
   int first=0;
   while(first<length-1 && StringGetCharacter(word,first)==48) first++;
   value=StringToInteger(word);
   return(value>=0 && IntegerToString(value)==StringSubstr(word,first));
  }

bool EmttParamPartWhole(const string part,const string key,long &value)
  {
   string tail="";
   return(EmttLearnPartTail(part,key,tail) && EmttParamWhole(tail,value));
  }

bool EmttParamPair(const string part,const string key,long &wins,long &losses)
  {
   string tail="",words[];
   if(!EmttLearnPartTail(part,key,tail) || StringSplit(tail,'/',words)!=2)
      return false;
   if(!EmttParamWhole(words[0],wins) || !EmttParamWhole(words[1],losses))
      return false;
   return(wins<=LONG_MAX-losses);
  }

string EmttParamCellLine(const SEmttParamCell &cell,const int mood)
  {
   return "cell "+EmttLearnMoodWord(mood)+
          " | bar "+IntegerToString(cell.bar)+
          " | base "+IntegerToString(cell.base)+
          " | accepted "+IntegerToString(cell.aW)+"/"+IntegerToString(cell.aL)+
          " | near "+IntegerToString(cell.nW)+"/"+IntegerToString(cell.nL)+
          " | moves "+IntegerToString(cell.moves);
  }

bool EmttParamParseCell(const string line,const int mood,SEmttParamCell &cell)
  {
   string parts[];
   if(StringSplit(line,'|',parts)!=6) return false;
   for(int i=0;i<6;i++) parts[i]=EmttLearnTrim(parts[i]);
   if(parts[0]!="cell "+EmttLearnMoodWord(mood)) return false;
   long bar=0,base=0;
   SEmttParamCell parsed;
   EmttParamCellReset(parsed,mood);
   if(!EmttParamPartWhole(parts[1],"bar",bar) ||
      !EmttParamPartWhole(parts[2],"base",base) ||
      (bar!=60 && bar!=70 && bar!=75) || base!=parsed.base ||
      !EmttParamPair(parts[3],"accepted",parsed.aW,parsed.aL) ||
      !EmttParamPair(parts[4],"near",parsed.nW,parsed.nL) ||
      !EmttParamPartWhole(parts[5],"moves",parsed.moves))
      return false;
   parsed.bar=(int)bar;
   cell=parsed;
   return true;
  }

// Line 2 is evidence still present in the cells, not lifetime totals:
// tickets = labeled accepted, near = labeled near, labeled = both.
// Decisions reset those tallies; only moves survives a decision.
string EmttParamCountsLine(const SEmttParamFileState &state,const datetime barTime)
  {
   long tickets=0,near=0,moves=0;
   for(int i=0;i<EMTT_POPT_CELLS;i++)
     {
      tickets+=state.cells[i].aW+state.cells[i].aL;
      near+=state.cells[i].nW+state.cells[i].nL;
      moves+=state.cells[i].moves;
     }
   return "counts tickets "+IntegerToString(tickets)+
          " | near "+IntegerToString(near)+
          " | labeled "+IntegerToString(tickets+near)+
          " | moves "+IntegerToString(moves)+
          " | updated "+EmttLearnTimeText(barTime);
  }

string EmttParamFileText(const SEmttParamFileState &state,const datetime barTime)
  {
   string text=EMTT_POPT_VERSION+" | "+state.symbol+" | "+state.tfName+"\r\n"+
               EmttParamCountsLine(state,barTime)+"\r\n";
   for(int i=0;i<EMTT_POPT_CELLS;i++)
      text+=EmttParamCellLine(state.cells[i],i)+"\r\n";
   return text;
  }

void EmttParamFileBusy(SEmttParamFileState &state,const datetime barTime)
  {
   if(state.writeFailed) return;
   PrintFormat("Emtt | Param file busy | learning kept in memory | bar %s",
               EmttLearnTimeText(barTime));
   state.writeFailed=true;
  }

void EmttParamFileRecovered(SEmttParamFileState &state,const datetime barTime)
  {
   if(!state.writeFailed) return;
   PrintFormat("Emtt | Param file write recovered | bar %s",
               EmttLearnTimeText(barTime));
   state.writeFailed=false;
  }

void EmttParamFileDamaged(SEmttParamFileState &state,const int mood,
                          const datetime barTime)
  {
   if(state.damagedWarned[mood]) return;
   PrintFormat("Emtt | Param file damaged | %s cell starts fresh | %s | bar %s",
               EmttLearnMoodWord(mood),state.filePath,EmttLearnTimeText(barTime));
   state.damagedWarned[mood]=true;
  }

// Internal reader also serves the retry on a write event after a busy load.
// Failure never opens the destination for writing. Line 2 is always ignored.
bool EmttParamFileRead(SEmttParamFileState &state,const datetime barTime)
  {
   if(!FileIsExist(state.filePath,0))
     {
      // A busy initial read may recover after the original disappears.
      // Save owns the memory delta; start the disk side from zero so it
      // is merged exactly once, not added back to itself.
      for(int i=0;i<EMTT_POPT_CELLS;i++) EmttParamCellReset(state.cells[i],i);
      PrintFormat("Emtt | Param optimization started | no file yet | MQL5\\Files\\%s",
                  state.filePath);
      state.readPending=false;
      return true;
     }
   ResetLastError();
   const int handle=FileOpen(state.filePath,FILE_READ|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
     {
      state.readPending=true;
      EmttParamFileBusy(state,barTime);
      return false;
     }
   string lines[];
   int count=0;
   bool ok=true;
   while(!FileIsEnding(handle))
     {
      ResetLastError();
      const string line=FileReadString(handle);
      if(GetLastError()!=0) { ok=false; break; }
      ArrayResize(lines,count+1);
      lines[count++]=EmttLearnTrim(line);
     }
   ResetLastError();
   FileClose(handle);
   if(GetLastError()!=0) ok=false;
   if(!ok)
     {
      state.readPending=true;
      EmttParamFileBusy(state,barTime);
      return false;
     }
   state.readPending=false;
   string head[];
   if(count<1 || StringSplit(lines[0],'|',head)!=3 ||
      EmttLearnTrim(head[0])!=EMTT_POPT_VERSION ||
      EmttLearnTrim(head[1])!=state.symbol ||
      EmttLearnTrim(head[2])!=state.tfName)
     {
      state.readOnly=true;
      PrintFormat("Emtt | Param version unknown | file untouched, base bars | %s | bar %s",
                  state.filePath,EmttLearnTimeText(barTime));
      return true;
     }
   bool seen[EMTT_POPT_CELLS];
   bool broken[EMTT_POPT_CELLS];
   for(int i=0;i<EMTT_POPT_CELLS;i++) { seen[i]=false; broken[i]=false; }
   for(int i=2;i<count;i++)
     {
      if(lines[i]=="") continue;
      string parts[],tail="";
      int mood=-1;
      if(StringSplit(lines[i],'|',parts)>0 &&
         EmttLearnPartTail(EmttLearnTrim(parts[0]),"cell",tail))
         mood=EmttLearnMoodFromWord(tail);
      if(mood<0)
        {
         // Fixed-order grammar identifies even a damaged mood word.
         if(i<2+EMTT_POPT_CELLS) broken[i-2]=true;
         continue;
        }
      SEmttParamCell cell;
      if(seen[mood] || !EmttParamParseCell(lines[i],mood,cell))
         broken[mood]=true;
      else
         state.cells[mood]=cell;
      seen[mood]=true;
     }
   long moves=0;
   for(int i=0;i<EMTT_POPT_CELLS;i++)
     {
      if(!seen[i] || broken[i])
        {
         EmttParamCellReset(state.cells[i],i);
         EmttParamFileDamaged(state,i,barTime);
        }
      moves+=state.cells[i].moves;
     }
   PrintFormat("Emtt | Param optimization loaded | 4 cells | %I64d moves | TRENDING bar %d (base 60) | RANGING bar %d | VOLATILE bar %d | TRANSITION bar %d",
               moves,state.cells[0].bar,state.cells[1].bar,
               state.cells[2].bar,state.cells[3].bar);
   return true;
  }

void EmttParamFileLoad(SEmttParamFileState &state,const string symbol,
                       const ENUM_TIMEFRAMES timeframe,const datetime barTime)
  {
   EmttParamFileReset(state);
   state.symbol=symbol;
   state.tfName=EmttLearnTfName(timeframe);
   state.filePath=EmttParamFilePath(symbol,state.tfName);
   state.loaded=true;
   EmttParamFileRead(state,barTime);
  }

// 23.7: init after load, a move/held move, deinit. No periodic save.
// Every write/flush/close is checked before the single atomic rename.
bool EmttParamFileSave(SEmttParamFileState &state,const datetime barTime)
  {
   if(!state.loaded || state.readOnly || state.filePath=="") return false;
   if(state.readPending)
     {
      // No decisions run until a busy initial read recovers. Preserve the
      // evidence accumulated in memory and merge it into the loaded cells.
      SEmttParamCell delta[EMTT_POPT_CELLS];
      for(int i=0;i<EMTT_POPT_CELLS;i++) delta[i]=state.cells[i];
      if(!EmttParamFileRead(state,barTime) || state.readOnly) return false;
      for(int i=0;i<EMTT_POPT_CELLS;i++)
        {
         state.cells[i].aW+=delta[i].aW;
         state.cells[i].aL+=delta[i].aL;
         state.cells[i].nW+=delta[i].nW;
         state.cells[i].nL+=delta[i].nL;
        }
     }
   // A successful destination read already establishes the folder. For a
   // fresh path FolderCreate uses the same local sandbox as 19.3.
   if(!FileIsExist(state.filePath,0) && !FolderCreate(EMTT_POPT_DIR,0))
      EmttParamFileBusy(state,barTime);
   const string tmpPath=state.filePath+".tmp";
   const string text=EmttParamFileText(state,barTime);
   ResetLastError();
   const int handle=FileOpen(tmpPath,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE) { EmttParamFileBusy(state,barTime); return false; }
   ResetLastError();
   const uint written=FileWriteString(handle,text);
   bool ok=(written==(uint)StringLen(text) && GetLastError()==0);
   ResetLastError();
   FileFlush(handle);
   if(GetLastError()!=0) ok=false;
   ResetLastError();
   FileClose(handle);
   if(GetLastError()!=0) ok=false;
   if(!ok) { EmttParamFileBusy(state,barTime); return false; }
   if(!FileMove(tmpPath,0,state.filePath,FILE_REWRITE))
     { EmttParamFileBusy(state,barTime); return false; }
   EmttParamFileRecovered(state,barTime);
   return true;
  }

#endif // EMTT_PARAMFILE_MQH
