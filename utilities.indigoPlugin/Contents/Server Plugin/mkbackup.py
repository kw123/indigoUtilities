#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
import time, datetime
import sys, subprocess, os, pwd
import operator
try:
	unicode("x")
except:
	unicode = str



####-------------------------------------------------------------------------####
def readPopen( cmd):
		try:
			ret, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
			return ret.decode('utf_8'), err.decode('utf_8')
		except Exception as e:
			self.exceptionHandler(40,e)

####-----------------  exception logging ---------
def exceptionHandler(level, exception_error_message):

		try:
			try: 
				if u"{}".format(exception_error_message).find("None") >-1: return exception_error_message
			except: 
				pass

			filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
			#module = filename.split('/')
			log_message = "'{}'".format(exception_error_message )
			log_message +=  "\n{} @line {}: '{}'".format(method, line_number, statement)
			if level > 0:
				myLog(10, log_message)
			return "'{}'".format(log_message )
		except Exception as e:
			indigo.server.log( "{}".format(e))

####----------------- print to logfile if > debuglevel ---------
def myLog(debug,text):
		global debugLevel,logF
		if True or debug >= debugLevel:
			logF.write(text+"\n")
			logF.flush()

####----------------- print progress dots ---------
def myDots(debug):
		global debugLevel
		if debug >= debugLevel:
			sys.stdout.write("."); sys.stdout.flush()


####----------------- get path to indigo programs ---------
def getIndigoPath(myPath):
		global indigoPath
		
		if len(myPath) > 15:
			pp= myPath.find("Plugins/utilities.i")
			if pp >- 1:
				 indigoPath = myPath[0:pp]
				 return
				 
		found=False
		indigoVersion = 0
		if os.path.isdir(indigoPath): found = True
		if not found:
			for indi in range(5,100):  # we are optimistic for the future of indigo, starting with V5
				if found:
					if os.path.isdir("/Library/Application Support/Perceptive Automation/Indigo "+str(indi)): continue
					else:
						indigoVersion = indi-1
						break
				else:
					if os.path.isdir("/Library/Application Support/Perceptive Automation/Indigo "+str(indi)): found = True

			indigoPath	=	"/Library/Application Support/Perceptive Automation/Indigo "+str(indigoVersion)+"/"


####----------------- doStepRename ---------
def doStepCopy(inFile, outFile):
	global indigoPath
	try:        
		tt = time.time()
		myLog(255," ")
		logSteps("copy")
		if os.path.isfile(indigoPath+outFile):
				os.remove(indigoPath+outFile)
		cmd="cp '"+indigoPath+inFile+"' '"+indigoPath+outFile+"'"
		myLog(255,"stepCopy cmd: "+ cmd)
		out, err =readPopen(cmd)
		if err == "": retCode = "0"
		else: retCode=unicode(err).strip("\n")
	except:
		retCode="1"    
	myLog(255,"stepCopy seconds used      :" + str(int(time.time()-tt)) + ";  error= "+retCode)
	logretCode("copy= ",unicode(retCode))
	return retCode

####----------------- doStepDump ---------
def doStepDump(inFile,outFile):
	global indigoPath
	try:        
		tt=time.time()
		myLog(255," ")
		logSteps("dump")
		myLog(255,"stepDump started           :" + str(datetime.datetime.now()))
		cmd = "/usr/bin/sqlite3  '"+indigoPath+inFile+"' .dump > '"+indigoPath+outFile+"'"
		myLog(255,"stepDump cmd: "+ cmd)
		out, err =readPopen(cmd)
		if err=="": retCode= "0"
		else: retCode=unicode(err).strip("\n")
	except:
		retCode="1"    
	myLog(255,"stepDump seconds used      :" + str(int(time.time()-tt)) + ";  error= "+retCode)
	logretCode("dump= ",unicode(retCode))
	return retCode

####----------------- doStepDump ---------
def doStepTest(inFile,test):
	global indigoPath
	try:        
		tt=time.time()
		myLog(255," ")
		logSteps("test")
		myLog(255,"stepTest started           :" + str(datetime.datetime.now()))
		if test =="" or len(test) < 5:
			myLog(255,"stepTest failed            :" + str(datetime.datetime.now())+" bad test string: " + test)
			return "bad test string"
		cmd = "/usr/bin/sqlite3  '"+indigoPath+inFile+"' \"Select * from "+test+";\""
		myLog(255,"stepTest cmd: "+ cmd)
		out, err =readPopen(cmd)
		if err=="": retCode= "0"
		else: retCode=unicode(err).strip("\n")
	except:
		retCode="1"    
	myLog(255,"stepTest seconds used      :" + str(int(time.time()-tt)) + ";  error= "+retCode)
	logretCode("test= ",unicode(retCode))
	return retCode



####----------------- doStepRename ---------
def	doStepRename(inFile,outFile,keep=""):
	global indigoPath
	try:    
		tt=time.time()
		myLog(255," ")
		logSteps("rename")
		myLog(255,"stepRename from to:       : "+ inFile+ " "+outFile )
		if keep !="":
			if os.path.isfile(indigoPath+outFile+keep):
				os.remove(indigoPath+outFile+keep)
			if os.path.isfile(indigoPath+outFile):
				os.rename(indigoPath+outFile,indigoPath+outFile+keep)

		if os.path.isfile(indigoPath+outFile):
			os.remove(indigoPath+outFile)
		if os.path.isfile(indigoPath+inFile):
			os.rename(indigoPath+inFile,indigoPath+outFile)
		retCode= "0"
	except:
		retCode="1"    
	myLog(255,"stepRename seconds used    :" + str(int(time.time()-tt)) + ";  error= "+retCode)
	logretCode("rename= ",unicode(retCode))
	return retCode

####----------------- doStepRecreate ---------
def	doStepRecreate(inFile, outFile):
	global indigoPath
	try:
		tt=time.time()
		myLog(255," ")
		logSteps("recreate")
		myLog(255,"stepRecreate started       :" + str(datetime.datetime.now() ))
		if os.path.isfile(indigoPath+outFile):
				os.remove(indigoPath+outFile)
		cmd= "/usr/bin/sqlite3  '"+indigoPath+outFile+"' < '"+indigoPath+inFile+"'"
		myLog(255,"stepRecreate cmd: " + cmd)
		out, err =readPopen(cmd)
		if err=="": retCode= "0"
		else: retCode=unicode(err).strip("\n")
		myLog(255,"stepRecreate seconds used  :" + str(int(time.time()-tt)) + ";  error= "+retCode)
		logretCode("recreate= ",unicode(retCode))
		return retCode
	except:
		return "1"        

####----------------- doStepCleanup ---------
def	doStepCleanup(files):
	global indigoPath
	try:
		myLog(255," ")
		logSteps("cleanup")
		myLog(255,"stepCleanup files:         : "+ unicode(files) )
		tt=time.time()
		for file in files:
			if os.path.isfile(indigoPath+file):
				os.remove(indigoPath+file)
	except:
		return "1"        
	myLog(255,"stepCleanup seconds used   :" +str(int(time.time()-tt)))


####----------------- doStepRecreate ---------
def	logSteps(text,finish=False):
		global indigoPath, utilPath
		f=open(utilPath+"steps","a")
		if finish:
			f.write(text.ljust(15)+" finished at "+ str(datetime.datetime.now())+"\n")
		else:
			f.write(text.ljust(15)+" started  at "+ str(datetime.datetime.now())+"\n")
		f.close()
####----------------- doStepRecreate ---------
def logretCode(text,retCode):
	global indigoPath, utilPath
	try:    
		if retCode =="0": return "0"
		f=open(utilPath+"retcode","a")
		f.write(text+retCode+"\n")
		f.close()
	except:
		return "1"        



####----------------- processItem ---------
def processItem(records,g):
	global nreadT,nread,nwritten,nVar,nVar2,nDev,nDev2,nLog,nLog2,dateSkip,bigGapSkip,badIndex
	try:
		if len(records)<1: return "0"
		index=0
		lastID=-1
		written=False
		dateLast=""
		line=""
		devVar=[0,0,0]
		lineLast=""
		bigGap=False
		lastID=0
		errorId0=0
		errorId1=0
		#sRecords = sorted(records)
		sRecords = sorted(records, key=operator.itemgetter(0, 1))
		for n in range(len(records)):
			if int(records[n][1]) <lastID:
				errorId1=n
				break
			lastID=int(records[n][1])
		
		if errorId1 >0:
			for n in range(errorId1):
				if int(records[errorId1-n][1]) < int(records[errorId1][1]):
					errorId0 = errorId1-n
					break
		if  errorId1 >0:
			myLog(255, "errorids "+str(errorId0)+ " "+str(errorId1)+"  nrecs: " + str(len(records)))
			myLog(255, " ".join(records[max(0,errorId0-1)]).strip("\n"))
			myLog(255, " ".join(records[errorId0]).strip("\n"))
			myLog(255, " ".join(records[errorId0+1]).strip("\n"))
			myLog(255, " ".join(records[errorId1-1]).strip("\n"))
			myLog(255, " ".join(records[errorId1]).strip("\n"))
			myLog(255, " ".join(records[min(errorId1+1,len(records)-1)]).strip("\n"))
		recs=0    
		lastDate=""
		lastRec=[]
		nr=0
		for rec in sRecords:
			nr+=1
			if rec[0] == lastDate and len(lastRec[3]) > 15: 
				lastRec=rec
				continue
			else:
				recs+=1
				if recs >1:
					g.write(lastRec[2]+str(recs)+","+lastRec[0]+","+lastRec[3])
			lastRec=rec
			lastDate=rec[0]
		g.write(lastRec[2]+str(recs+1)+","+lastRec[0]+","+lastRec[3])
		myLog(255, "recs read, written :" +str(nr)+" "+str(recs))
		nwritten=recs+1
		nread+=len(records)
		return "0"   
	except:
		return "1"        

####----------------- doStepfixDump ---------
def doStepfixDump(inFile,outFile):
	global nreadT,nread,nwritten,nVar,nVar2,nDev,nDev2,nLog,nLog2,dateSkip,bigGapSkip,badIndex
	global indigoPath
	try:
		tt=time.time()
		myLog(255," ")
		myLog(255,"doStepfixDump started       :" + str(datetime.datetime.now()))
		f=open(indigoPath+inFile,"r")
		g=open(indigoPath+outFile,"w")
		nreadT  =0
		nread   =0
		nwritten=0
		nVar	=0
		nVar2	=0
		nDev	=0
		nDev2	=0
		nLog	=0
		nLog2	=0
		tt = time.time()
		outLine=[]

# lines in dump file
#PRAGMA foreign_keys=OFF;
#BEGIN TRANSACTION;
#CREATE TABLE device_history_943187748 ( id INTEGER PRIMARY KEY, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "onoffstate" BOOL);
#INSERT INTO "device_history_943187748" VALUES(1534,'2014-11-07 06:59:16','True');
# an event log line:
#INSERT INTO "eventlog_history" VALUES(4279342,'2015-10-29 23:16:20','False',5,'INDIGOplotD','/usr/bin/sqlite3 -separator " " indigo_history.sqlite " SELECT id, strftime(''%Y%m%d%H%M%S'',ts,''localtime'') ,counter from device_history_1534950270 WHERE  ID > 127333 LIMIT 10000000;"  2>/Users/HomeServerII/Documents/INDIGOplotD/sql/1534950270-counter.error | awk ''NF>2 && !/data unavailable/ {print}''  > /Users/HomeServerII/Docu
#COMMIT;        
		
		line=True
		lineTotal=""
		records=[]
		dev=""
		while line :
			nreadT+=1
			line = f.readline()
			if line.find("PRAGMA foreign_keys=OFF") ==0 or line.find("BEGIN TRANSACTION") ==0 or line.find("CREATE TABLE") ==0 or line.find("COMMIT") ==0:  
				if len(records) > 0: myLog(255,"calling process with " +dev.strip("\n")+ " # of lines: " + str(len(records)))
				if lineTotal !="": 
					parts=lineTotal.split('" VALUES(')
					values=parts[1].split(",")
					ll = len(values[0]+","+values[1])
					rest= parts[1][ll+1:]
					records.append([values[1],values[0], parts[0]+'" VALUES(' ,rest])
					processItem(records,g)
				if line.find("CREATE TABLE")==0: dev=line    
				lineTotal=""
				records=[]
				g.write(line)
				if line.find("COMMIT;")==0: 
					break
			else:
				if len(line) ==1: continue # skip empty lines
				if line.find("INSERT INTO ") ==0:
					if len(lineTotal) >1: 
						parts=lineTotal.split('" VALUES(')
						values=parts[1].split(",")
						ll = len(values[0]+","+values[1])
						rest= parts[1][ll+1:]
						records.append([values[1],values[0], parts[0]+'" VALUES(' ,rest])
					lineTotal=line
				else:
					lineTotal+=line

		f.close()
		g.close()

		myLog(255,"")
		myLog(255,"total read                 :" +str(nreadT))
		myLog(255,"insert commands read       :" +str(nread))
		myLog(255,"insert commands written    :" +str(nwritten))

		myLog(255,"bigGapSkip                 :" +str(bigGapSkip))
		myLog(255,"badIndex                   :" +str(badIndex))

		myLog(255,"Variables read             :" +str(nVar))
		myLog(255,"Variables records written  :" +str(nVar2))

		myLog(255,"Devices read               :" +str(nDev))
		myLog(255,"Devices records written    :" +str(nDev2))
		myLog(255,"logs    read               :" +str(nLog))
		myLog(255,"logs    records written    :" +str(nLog2))


		retCode= "0"
	except:
		retCode= "1"
	myLog(255,"stepCompress seconds used  :" +str(int(time.time()-tt)) + ";  error= "+unicode(retCode))
	return retCode



####----------------- doStepCompress ---------
def doStepCompress(inFile,outFile,pruneVariables="",pruneDevices={} ):
	global nreadT,nread,nwritten,nVar,nVar2,nDev,nDev2,nLog,nLog2,dateSkip,bigGapSkip,badIndex
	global indigoPath
	try:
		tt=time.time()
		myLog(255," ")
		myLog(255,"stepCompress started       :" + str(datetime.datetime.now()))
		f=open(indigoPath+inFile,"r")
		g=open(indigoPath+outFile,"w")
		n=0
		idL=0
		dateLast=""
		lineLast=""
		lineLast2=""
		written=False

		nreadT  =0
		nread   =0
		nwritten=0
		nVpruned=0
		nVar	=0
		nVar2	=0
		nDev	=0
		nDev2	=0
		nDpruned=0
		nDevNotPruned=0
		nVarNotPruned=0
		lastID =0
		shortLine=0
		shortLineFixed=0
		devVar=[0,0,0]
		new = False
		m=0
		tt = time.time()
		line =True
		while line :
			nreadT+=1
			line = f.readline()
			if line.find("INSERT INTO ") >-1:  # this is for line that a a \n in their values
				if line[len(line)-5:].find(");")==-1: ## is it properly terminated?
					shortLine+=1
					line2 = f.readline()				## if not add the next line to it
					if line2.find("INSERT INTO ") ==-1: ## but only if it is a new line
						line= line.strip("\n")+line2    ## the add the next line and remove the \n in the middle
						shortLineFixed+=1
						myLog(64,"fixed line: "+line)
					else:
						myLog(255,"bad line#: "+str(nreadT))
						myLog(255,"bad lineP: "+lineLast2.strip("\n"))
						myLog(255,"bad line : "+line.strip("\n"))
						continue
		
			if len(line) < 6:
				myLog(255,"bad line#: "+str(nreadT))
				myLog(255,"bad lineP: "+ lineLast2.strip("\n"))
				myLog(255,"bad line : "+ line.strip("\n"))
				continue
			if line.find("CREATE TABLE ") >-1: new =True; n+=1; index=1

			if nreadT %1000000 ==0: m+=1 ;	myLog(255,str(m)+" million records")
			elif nreadT %20000 ==0:			myDots(255)

			if line.find("INSERT INTO ") ==-1:
				if n>1 and not written:
					nwritten+=1
					if lineLast != "":
						
						if devVar[0] =="variable": nVar2+=1
						if devVar[0] =="device":   nDev2+=1
						g.write(lineLast)
						lineLast=""
					written = True
				g.write(line)
				if line.find("COMMIT;")==0:
					break
				continue

			nread+=1
			written=False


			parts = line.split('" VALUES(')
			if len(parts) < 2:
				myLog(255," bad record "+line)
				continue
			xx=parts[0].split('"')
			if len(xx) < 2:
				myLog(255," bad record "+line)
				continue
			devVar=xx[1].split("_")
			if len(devVar) < 3:
				myLog(255," bad record "+line)
				continue
			values = parts[1].split(",")
			if len(values) < 3:
				myLog(255," bad record "+line )
				continue
			date = values[1]
			if not new and lastID > int(values[0]):
				myLog(255,"bad index last:"+ str(lastID))
				myLog(255,line.strip("\n"))
				myLog(255,lineLast2.strip("\n"))
				
				continue
			lastID=int(values[0])

			if devVar[0]=="variable":
				nVar+=1
				if pruneVariables !="":
					if values[1].strip("'") < pruneVariables:
						nVpruned+=1
						continue
				nVarNotPruned+=1
			if devVar[0]=="device":
				nDev+=1
				if devVar[2] in pruneDevices:
					if values[1].strip("'") < pruneDevices[devVar[2]]:
						#if nVpruned < 100:	myLog(255,"pruned"
						nDpruned+=1
						continue
				nDevNotPruned+=1


			if not new and (date != dateLast or len(values)<6):
				index+=1
				nwritten+=1
				if not written:
					if devVar[0] =="variable": nVar2+=1
					if devVar[0] =="device":   nDev2+=1
					g.write(lineLast)

				
			new=False
			lineLast=line
			lineLast2=line
			dateLast=date
		f.close()
		g.close()

		myLog(255,"")
		myLog(255,"total read                 :" +str(nreadT))
		myLog(255,"insert commands read       :" +str(nread))
		myLog(255,"insert commands written    :" +str(nwritten))

		myLog(255,"Variables read             :" +str(nVar))
		myLog(255,"Variables pruned           :" +str(nVpruned))
		myLog(255,"Variables Not pruned       :" +str(nVarNotPruned))
		myLog(255,"Variables records written  :" +str(nVar2))

		myLog(255,"Devices read               :" +str(nDev))
		myLog(255,"Devices pruned             :" +str(nDpruned))
		myLog(255,"Devices Not pruned         :" +str(nDevNotPruned))
		myLog(255,"Devices records written    :" +str(nDev2))

		myLog(255,"shortLine                  :" +str(shortLine))
		myLog(255,"shortLineFixed             :" +str(shortLineFixed))

		retCode= "0"
	except:
		retCode= "1"
	myLog(255,"stepCompress seconds used  :" +str(int(time.time()-tt)) + ";  error= "+unicode(retCode))
	return retCode


####----------------- doAllSteps ---------
def doAllSteps(args,test,pruneVariables,pruneDevices):
	global indigoPath,utilPath, sqliteDB
	global nreadT,nread,nwritten,nVar,nVar2,nDev,nDev2,nLog,nLog2,dateSkip,bigGapSkip,badIndex,noOfBackupCopies

	if "backup" in args:
				if doStepCopy(sqliteDB+".sqlite","a.cp")							!="0": return
				if doStepTest("a.cp",test)											!="0": return
				for j in range(1,noOfBackupCopies):
					i= noOfBackupCopies-j
					doStepRename(sqliteDB+"-"+str(i)+".sqlite",sqliteDB+"-"+str(i+1)+".sqlite")
				doStepRename("a.cp",sqliteDB+"-1.sqlite")
				doStepCleanup(["a.cp"])
				return

	if "fix" in args:
				if doStepCopy(sqliteDB+".sqlite","a.cp")							!="0": return
				if doStepDump("a.cp","a.dump")				            			!="0": return
				if doStepfixDump("a.dump","b.dump")				                    !="0": return
				if doStepRecreate("b.dump","c-fixed.sqlite")	        			!="0": return
				if test!="":
					if doStepTest("c-fixed.sqlite",test)						    !="0": return
				if doStepRename("c-fixed.sqlite",sqliteDB+"-fixed.sqlite","")       !="0": return
				doStepCleanup(["c-fixed.sqlite","a.cp","a.dump","b.dump"])
				return

	if "compress" in args:
				if doStepCopy(sqliteDB+".sqlite","a.cp")							!="0": return
				if doStepDump("a.cp","a.dump")										!="0": return
				if doStepCompress("a.dump","a.compr",pruneVariables,pruneDevices)	!="0": return
				if doStepRecreate("a.compr",sqliteDB+"-compressed.sqlite")			!="0": return
				doStepCleanup(["a.cp","a.compr","a.dump"])
				return

############################# MAIN PGM ##########
global debugLevel, indigoPath, logF, utilPath, sqliteDB
global nreadT,nread,nwritten,nVar,nVar2,nDev,nDev2,nLog,nLog2,dateSkip,bigGapSkip,badIndex,noOfBackupCopies
debugLevel=255

nreadT=0;nread=0;nwritten=0;nVar=0;nVar2=0;nDev=0;nDev2=0;nLog=0;nLog2=0;dateSkip=0;bigGapSkip=0;badIndex=0

try:
	myPath = sys.argv[0]
except:
	myPath = ""

try:
	arg1 = [sys.argv[1]]
except:
	arg1=["backup"]
try:
	test = sys.argv[2]
except:
	test=""
try:
	noOfBackupCopies = int(sys.argv[3])
except:
	noOfBackupCopies=2




userName = pwd.getpwuid( os.getuid() )[ 0 ]
MAChome  = os.path.expanduser(u"~")

utilPath = MAChome+"/indigo/Utilities/"

if os.path.isfile(utilPath+"backup.log"):
	if os.path.getsize(utilPath+"backup.log")> 1000000:
		if os.path.isfile(utilPath+"backup-1.log"):
			os.remove(utilPath+"backup-1.log")
		os.rename(utilPath+"backup.log", utilPath+"backup-1.log")



logF= open(utilPath+"backup.log","a")


getIndigoPath(myPath)
indigoPath+="logs/"
sqliteDB = "indigo_history"
##indigoPath="./"



try:
	f=open(utilPath+"pruneVariables","r")
	pruneVariables=json.loads(f.read())
	f.close()
except:
	pruneVariables="2015-08-15 05:37:18"
try:
	f=open(utilPath+"pruneDevices","r")
	pruneDevices=json.loads(f.read())
	f.close()
except:
	pruneDevices={
		 "549525270"   :"2015-08-01 00:00:00"
		,"89122477"    :"2015-08-01 00:00:00"
		}

retF	=open(utilPath+"retcodes","w")

if os.path.isfile(utilPath+"steps"):
	os.remove(utilPath+"steps")

startF	=open(utilPath+"steps","w")


print ("starting indigo sqlite utility job "+ str(datetime.datetime.now()) + " parameters " + unicode(arg1) +" "+ test)
print ("starting indigo sys.argv {}".format(sys.argv))
tTotal=time.time()
myLog(255,"----------------------------------------------------------------" )
myLog(255,"starting indigo sqlite utility job "+ str(datetime.datetime.now()) + " parameters " + unicode(arg1) +" "+ test)


doAllSteps(arg1, test, pruneVariables, pruneDevices)
logSteps("ALL",finish=True)

myLog(255,"finished indigo sqlite job :"+ str(datetime.datetime.now()))
myLog(255,"total seconds used         :" +str(int(time.time()-tTotal)))
myLog(255,"----------------------------------------------------------------" )

retF.close()
logF.close()


