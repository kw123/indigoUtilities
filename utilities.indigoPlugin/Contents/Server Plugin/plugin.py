#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# show sql data in logfile  Plugin
# Developed by Karl Wachs
# karlwachs@me.com

import os, sys, subprocess, pwd, copy, datetime, time
import plistlib
import versionCheck.versionCheck as VS
import json
import cProfile
import pstats
import myLogPgms.myLogPgms 
import traceback

try:
	unicode("a")
except:
	unicode = str

import codecs

'''
options:
A) print all devices / states and variables / states
B) print all zwave network connection / neiFts_ghbors
C) Print all Device names and IDs to support you have ID which name is it
D) create backup of sqlite and test if it works, keep last 2 files
E)  try to fix sql dab: copy, dump, create, test file


F)
== for sql queries
0. in config select SQL version (SQLite or postGRES)
1. select variable or device / state in menu to be retrived from SQL
2. then issue sql command
3. print to logfile or file


== for compress (not implemented yet)
make a copy
create a dump
remove records that have the same value several time / second
remove all variable history < date xx
immport into new sqlite db .compressed
run a test query select * from variable_history_12345 against the new db

'''


################################################################################
class Plugin(indigo.PluginBase):

	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		##self.errorLog( os.getcwd())
		self.pathToPlugin = os.getcwd() + "/"
		## = /Library/Application Support/Perceptive Automation/Indigo 6/Plugins/piBeacon.indigoPlugin/Contents/Server Plugin
		p = max(0, self.pathToPlugin.lower().find("/plugins/")) + 1
		self.indigoPath 		= self.pathToPlugin[:p]
		self.pluginVersion      = pluginVersion
		self.pluginId           = pluginId
		self.pluginName         = pluginId.split(".")[-1]

		#self.errorLog(self.indigoPath)
		#self.errorLog(self.pathToPlugin)


	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)
	
	########################################
	def startup(self):


		if self.pathToPlugin.find("/" + self.pluginName + ".indigoPlugin/") == -1:
			self.errorLog(u"--------------------------------------------------------------------------------------------------------------")
			self.errorLog(u"The pluginname is not correct, please reinstall or rename")
			self.errorLog(u"It should be   /Libray/....../Plugins/" + self.pluginName + ".indigPlugin")
			p = max(0, self.pathToPlugin.find("/Contents/Server"))
			self.errorLog(u"It is: " + self.pathToPlugin[:p])
			self.errorLog(u"please check your download folder, delete old *.indigoPlugin files or this will happen again during next update")
			self.errorLog(u"---------------------------------------------------------------------------------------------------------------")
			self.sleep(2000)
			exit(1)
			return

		self.MACuserName				= pwd.getpwuid(os.getuid())[0]
		self.MAChome					= os.path.expanduser("~")
		self.userIndigoDir				= self.MAChome + "/indigo/"
		self.userIndigoPluginDir		= self.userIndigoDir + u"utilities/"
		self.oldIndigoDir				= self.MAChome + u"/documents/indigoUtilities/"

		self.getInstallFolderPath		= indigo.server.getInstallFolderPath()+"/"
		self.indigoRootPath 			= indigo.server.getInstallFolderPath().split("Indigo")[0]
		self.indigoPreferencesPluginDir = self.getInstallFolderPath+"Preferences/Plugins/"+self.pluginId+"/"
		if not os.path.isdir(self.indigoPreferencesPluginDir): 
			os.mkdir(self.indigoPreferencesPluginDir)
		self.indigoLogPluginDir 		= self.getInstallFolderPath+"Logs/Plugins/"+self.pluginId+"/"
		
		self.localeLanguage     		= self.pluginPrefs.get(		"localeLanguage",	"en_US")
		self.enccodingChar      		= self.pluginPrefs.get(		"enccodingChar","utf-8")
		self.userName           		= pwd.getpwuid( os.getuid() )[ 0 ]
		self.debugLevel					= int(self.pluginPrefs.get(	"debugLevel",		255))
		self.liteOrPsql					= self.pluginPrefs.get(		"liteOrPsql",		"sqlite")
		self.liteOrPsqlString			= self.pluginPrefs.get(		"liteOrPsqlString",	"/Library/PostgreSQL/bin/psql indigo_history postgres ")
		self.postgresUserId				= self.pluginPrefs.get(		"postgresUserId",	"postgres")
		self.postgresPassword			= self.pluginPrefs.get(		"postgresPassword",	"")
		if self.postgresPassword != "" and self.liteOrPsql.find("psql") >-1: 
			self.postgresPasscode 		= "PGPASSWORD="+self.postgresPassword +" "
		else: self.postgresPasscode 	= ""

		self.orderByID					= self.pluginPrefs.get(		"orderByID",	"no")
		self.noOfBackupCopies			= self.pluginPrefs.get(		"noOfBackupCopies",	"2")
		self.maxSQLlength       		= self.pluginPrefs.get(		"maxSQLlength",	"200000")
		self.PLUGINSallCalcCPU  		= self.pluginPrefs.get(		"PLUGINSallCalcCPU","0") == "1"
		self.devID 						= 0
		self.varID 						= 0
		self.quitNow					= "" # set to !="" when plugin should exit ie to restart, needed for subscription -> loop model
		self.printNumberOfRecords 		= 0
		if os.path.isfile(u"/Library/Frameworks/Python.framework/Versions/Current/bin/python3"):
			self.pythonPath				= u"/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
		elif os.path.isfile(u"/usr/local/bin/python"):
			self.pythonPath				= u"/usr/local/bin/python"
		elif os.path.isfile(u"/usr/bin/python2.7"):
			self.pythonPath				= u"/usr/bin/python2.7"
		else:
			self.errorLog(u"FATAL error:  none of python versions 2.7 3.x is installed  ==>  stopping INDIGOplotD")
			self.quitNOW = "none of python versions 2.7 3.x is installed "
			return
		indigo.server.log(u"using '" +self.pythonPath +"' for utily programs")

		self.PLUGINSusedForCPUlimts, raw = self.readJson(self.indigoPreferencesPluginDir+"PLUGINSusedForCPUlimts.json")
		if len(raw) < 10: 
			self.PLUGINSusedForCPUlimts = {}
			try: 	self.PLUGINSusedForCPUlimts = json.loads(self.pluginPrefs.get("PLUGINSusedForCPUlimts",""))
			except: pass
		try: 	del self.pluginPrefs["PLUGINSusedForCPUlimts"]
		except: pass

		self.lastPluginCpuCheck     = 0



		self.fixSQLStarted=False
		self.fixSQLSteps=0
		self.backupStarted=False
		self.backupSteps=""
		self.executeDatabaseSqueezeCommand = ""
		self.postgresBackupStarted =0
		self.lastVersionCheck = -1

		self.cpuTempFreq   = self.pluginPrefs.get(		"cpuTempFreq",	"0")
		self.cpuTempUnit   = self.pluginPrefs.get(		"cpuTempUnit",	"0")
		self.cpuTempFormat = self.pluginPrefs.get(		"cpuTempFormat",	"%.1f")
		self.lastcpuTemp   = 0
		self.getDebugLevels()
		
		self.triggerList   = []
		
		try:
			indigo.variables.folder.create("SQLoutput")
		except:
			pass
		try:
			indigo.variable.create("SQLLineOutput","","SQLoutput")
		except:
			pass
		try:
			indigo.variable.create("SQLValueOutput","","SQLoutput")
		except:
			pass



		if not os.path.exists(self.userIndigoDir):
			os.mkdir(self.userIndigoDir)

		if not os.path.exists(self.userIndigoPluginDir):
			os.mkdir(self.userIndigoPluginDir)

		try:
			self.printDeviceStatesDictLast= self.pluginPrefs["printDeviceStates"]
		except:
			self.printDeviceStatesDictLast=indigo.Dict()

		self.checkcProfile()

		self.ML = myLogPgms.myLogPgms.MLX()

		self.setLogfile(self.pluginPrefs.get("logFileActive2", "standard"))
		self.ML.myLog( text=u"initialized")

		return

####-------------------------------------------------------------------------####
	def getDebugLevels(self):
		self.debugLevel			= []
		for d in ["Logic","SQL","all"]:
			if self.pluginPrefs.get(u"debug"+d, False): self.debugLevel.append(d)
		return


	########################################
	def deviceStartComm(self, dev):
		return
	
	########################################
	def deviceStopComm(self, dev):
		return
	########################################
	#def stopConcurrentThread(self):
	#    self.ML.myLog( text=u"stopConcurrentThread called " + str(self.stopConcurrentCounter))
	#    self.stopConcurrentCounter +=1
	#    if self.stopConcurrentCounter ==1:
	#        self.stopThread = True




####-----------------  set the geneeral config parameters---------
	def validatePrefsConfigUi(self, valuesDict):

		self.debugLevel			= []
		for d in ["Logic","SQL","all"]:
			if valuesDict[u"debug"+d]: self.debugLevel.append(d)

		self.setLogfile(valuesDict[u"logFileActive2"])
		self.localeLanguage     = valuesDict[u"localeLanguage"]
		self.enccodingChar      = valuesDict[u"enccodingChar"]
		self.liteOrPsql			= valuesDict["liteOrPsql"]
		self.liteOrPsqlString	= valuesDict["liteOrPsqlString"]
		self.postgresUserId		= valuesDict["postgresUserId"]
		self.postgresPassword	= valuesDict["postgresPassword"]
		if self.postgresPassword != "" and self.liteOrPsql.find("psql") >-1: 
			self.postgresPasscode 		= "PGPASSWORD="+self.postgresPassword +" "
		else: self.postgresPasscode 	= ""
		self.orderByID			= valuesDict["orderByID"]
		self.noOfBackupCopies	= valuesDict["noOfBackupCopies"]
		try:
			self.maxSQLlength = str(int(valuesDict["maxSQLlength"]))
		except:    
			valuesDict["maxSQLlength"] = 200000
			self.maxSQLlength = 200000
			
		self.cpuTempFreq        = valuesDict["cpuTempFreq"]
		self.cpuTempUnit        = valuesDict["cpuTempUnit"]
		self.cpuTempFormat      = valuesDict["cpuTempFormat"]
		self.PLUGINSallCalcCPU = valuesDict["PLUGINSallCalcCPU"]=="1"
		
		return True, valuesDict

	####-----------------	 ---------
	def setLogfile(self,lgFile):
		self.logFileActive =lgFile
		if   self.logFileActive =="standard":	self.logFile = ""
		else:									self.logFile = self.indigoLogPluginDir +"plugin.log"
		self.ML.myLogSet(debugLevel = self.debugLevel ,logFileActive=self.logFileActive, logFile = self.logFile, pluginSelf=self)


####-----------------  print dev var names and id's ---------
	def inpPrintdevNamesIds(self):


		indigo.server.log(u"\n                 ============== Print variables and devices names/ids logfile =============" ," ")
		listV=[]
		for var in indigo.variables:
			listV.append((var.name,str(var.id)))
		listV= sorted(listV)
		nn=0
		out=""
		line="[Variable Name - Variable ID]\n"
		for pair in listV:
			nn+=1
			if nn ==4:
				line+=out+"\n"
				nn=1
				out=""
			out+= ("["+pair[0]+"--"+pair[1]+"]").ljust(60)
		if nn !=0:
			line+=out+"\n"
		indigo.server.log(line)


		listV=[]
		indigo.server.log(u" "," ")
		for dev in indigo.devices:
			listV.append((dev.name,str(dev.id)))
		listV= sorted(listV)
		nn=0
		out=""
		line="[Device Name - Device ID]\n"
		for pair in listV:
			nn+=1
			if nn ==4:
				line+=out+"\n"
				nn=1
				out=""
			out+= ("["+pair[0]+"--"+pair[1]+"]").ljust(60)
		if nn !=0:
			line+=out+"\n"
		indigo.server.log(line)

		return


####-----------------  print device / variable states .. ---------
	def printmakepluginDateList(self):
		self.taskList +="makepluginDateList"
		return

	def getOpenFiles(self):
		#xx = subprocess.Popen("/usr/sbin/lsof | grep -v 'com.apple.' | grep -v 'Support/Perceptive Automation/' | grep -v '>localhost:indigo-server' | grep -v '/System/Library/' | grep -v '/Python.framework/' | grep -v '/CoreServices/' | grep -v '/usr/lib/' | grep -v '/usr/share/'  | grep -v '/private/var/db/'  | grep -v '/dev/null'  | grep -v '/dev/urandom'  ",
		ret, err = self.readPopen("/usr/sbin/lsof | grep -v 'com.apple.' | grep -v '>localhost:indigo-server' | grep -v '/System/Library/' | grep -v '/Python.framework/' | grep -v '/CoreServices/' | grep -v '/usr/lib/' | grep -v '/usr/share/'  | grep -v '/private/var/db/'  | grep -v '/dev/null'  | grep -v '/dev/urandom'  ")
		xx = ret.strip("\n").split("\n")
		fileList ={}
		for m in xx:
			mm = m.split()
			try: int(mm[1])
			except: continue
			if len(mm) > 8:
				if mm[1] not in fileList: fileList[mm[1]] =[]
				if len(mm[8]) > 5:      ### exclude std files 
					fileList[mm[1]].append(" ".join(mm[8:])) # file name
		#indigo.server.log("getOpenFiles {}".format(fileList))
		return  fileList


	def getActivePlugins(self,psef):

		plugList= {}
		try:
			lines = psef.strip(u"\n").split(u"\n")
			version =" "
			for line in lines:
				#indigo.server.log(line)
				if len(line) < 40: continue
				#if line.find("ndigo") == -1: continue
				items = line.split()
				if len(items) < 7: continue
				#self.ML.myLog( text=unicode(items))
				pCPU    = items[6]
				pID     = items[1]
				pType   = "plugin"
				plugId  = "0"
				version = "0"
				if line.find("MacOS/IndigoPluginHost") > -1:
					SPLIT = "-f"
					if    " -f" in line: SPLIT = " -f"
					elif  " -e" in line: SPLIT = " -e"
					else: continue
					pName = (line.split(SPLIT)[1]).split(".indigoPlugin")[0]
					pType ="plugin"
					try:
						if sys.version_info[0]  > 2:
							f = open(self.indigoPath+u"Plugins/"+pName+u".indigoPlugin/Contents/Info.plist","r", encoding="utf-8")
						else:
							f = codecs.open(self.indigoPath+u"Plugins/"+pName+u".indigoPlugin/Contents/Info.plist","r", "utf-8")
						xmlLines = f.read()
						temp = xmlLines.split("CFBundleIdentifier</key>")
						if len(temp) >1:
							plugId = temp[1].split("</string>")[0].split("<string>")[1]
						else: plugId = ""
						temp = xmlLines.split("PluginVersion</key>")
						if len(temp) >1:
							version = temp[1].split("</string>")[0].split("<string>")[1]
						else: version = ""

					except  Exception as e:
						if unicode(e).find("No such file or directory") > -1:
							plugId   = pName
							version  = "noVer."
						else:
							self.exceptionHandler(40,e)
							continue
				elif line.find("/Applications/Indigo ") > -1 and line.find(".app/Contents/MacOS/Indigo ") > -1: 
					pType  = "IndigoClient"
					pName  = "IndigoClient"
					plugId = "IndigoClient"
					
				elif line.find("IndigoServer.app/") > -1: 
					pType  = "IndigoServer"
					pName  = "IndigoServer"
					plugId = "IndigoServer"
					
				elif line.find("/IndigoWebServer/") > -1: 
					pType  = "IndigoWebServer"
					pName  = "IndigoWebServer"
					plugId = "IndigoWebServer"
				elif line.find("/Postgres") > -1: 
					pType  = "postgres"
					pName  = "postgres"
					plugId = "postgres"
				elif line.find("VBox") > -1: 
					pType  = "VBox"
					pName  = "VBox"
					plugId = "VBox"
				elif line.find("fing.bin") > -1: 
					pType  = "fing"
					pName  = "fing"
					plugId = "fing"
				else:
					continue
					
						
				plugList[plugId]= { "plugName":pName,"cpu":pCPU,"pid":pID,"version":version,"pType":pType,"subprocessesPid":{} }
				## now do subprocesses
				## for fingscan it is only the shell that calls fing which has a different pid parent ie 1 = root  
				if pName.find("fingscan") == -1:
					nSub =0
					for subLine in lines:
						subp = subLine.split()
						if len(subp) < 8: continue
						if subp[2] == pID:
							nSub +=1
							if subp[1] not in plugList[plugId]["subprocessesPid"]:   plugList[plugId]["subprocessesPid"][subp[1]] = {}
							plugList[plugId]["subprocessesPid"][subp[1]] =  {"cpu":subp[6], "name":" ".join(subp[7:])}

				#indigo.server.log (plugId+"  :" +unicode(plugList[plugId]))
								
		except  Exception as e:
			self.exceptionHandler(40,e)
				
		return plugList





####-----------------  print device / variable states .. ---------
	def printMACtemperaturesAction(self, action,typeId="",devId=""):
		self.printMACtemperatures()
		
####-----------------  print device / variable states .. ---------
	def printMACtemperatures(self):
		out ="\nTemperatures and fan speeds of indigo MAC \n"
		ret, err = self.readPopen("'"+self.pathToPlugin+"osx-temp-fan'")
		ll = ret.strip("\n")
		for line in ll.split("\n"):
			if line.find("-99") >-1: continue
			items = line.split(":")
			if len(items) !=2:       continue
			if items[0].find("fan") >-1: 
				val = items[1].split(".")[0]+"[r/m]" # only integer part
			else:                        
				t = float(items[1])
				if self.cpuTempUnit == "F": 
					val = "%.1f"%(t*9./5 +32)+"[ºF]"
				else:
					val ="%.1f"%t +"[ºC]"
			out += (items[0]+":").ljust(30)+ val +"\n"
		indigo.server.log(out)
		return
		

####-----------------  print device / variable states .. ---------
	def printPluginidNamestoLogfileAction(self, action,typeId="",devId=""):
		self.printPluginidNamestoLogfile()
		
####-----------------  print device / variable states .. ---------
	def printPluginidNamestoLogfile(self):

		indigo.server.log("starting print plugin names, id, mem cpu  daughter processes . . . takes a little time,  using lsof, ps -ef, ps aux")
		psaux  = self.getPSAUX()
		psef   = self.getPSEF(grep="ndigo")
		memList ={}
		for m in psaux.split("\n"):
			mm = m.split()
			try: int(mm[4])
			except: continue
			memList[mm[1]]= [mm[3],str(int(mm[4])/1024),str(int(mm[5])/1024)] # %mem,virt mem, real mem in MB
			#indigo.server.log(unicode( memList[mm[1]]))

		fileList = self.getOpenFiles()
		plugList = self.getActivePlugins(psef)
		
		out=["\n    PID    CPU-total  Mem-% -Virt -Real  version       pluginName ------------------------  .. + sub processes and non std open files \n"]
		for plID in  plugList:
			item = plugList[plID]
			try:
				if item["pType"] !="plugin": continue
				pName   = item["plugName"]
				pCPU    = item["cpu"]
				pID     = item["pid"]
				version = item["version"]
				if pID in memList:    mem = memList[pID][0].rjust(6)+memList[pID][1].rjust(6)+memList[pID][2].rjust(6)
				else:                 mem = " ".rjust(18)
				out.append(pID.rjust(7)+"  "+pCPU.rjust(11)+" "+mem+"  "+version.ljust(10)+"   "+ pName +"\n")
				ret2 = []
				for line in psef.split("\n"):
					if (" "+pID+" ") not in line: continue
					ret2.append(line)
				if ret2 == []: continue
				
				for dPID in item["subprocessesPid"]:
					items2 = item["subprocessesPid"][dPID]
					name = items2["name"]
					if len(name) < 10: continue
					dCPU = items2["cpu"]
					doughterProcess= "             SubProcess: "+name.replace("/Library/Application Support/Perceptive Automation/Indigo"," ...")
					if pID in memList:    mem = memList[pID][0].rjust(6)+memList[pID][1].rjust(6)+memList[pID][2].rjust(6)
					else:                 mem = " ".rjust(18)
					out.append( dPID.rjust(7)+"  "+dCPU.rjust(11)+" "+mem+"   "+ doughterProcess+"\n")
				if pID in fileList and len(fileList[pID]) > 0:
					for ff in fileList[pID]:
						out.append(" ".ljust(7+2+11+1+19+2)+"             openFile:   "+ff+"\n")                
			except  Exception as e:
				self.exceptionHandler(40,e)
		indigo.server.log("".join(out))



####-----------------  print device / variable states .. ---------
	def makepluginDateList(self):

			self.taskList =""
			psef  = self.getPSEF(grep="ndigo")
			plugList = self.getActivePlugins(psef)
			tDay = datetime.datetime.now().day
			if self.lastVersionCheck == tDay:
				self.ML.myLog( text="plugin version check already ran today, try again tomorrow")
				return
			self.lastVersionCheck = tDay

			self.ML.myLog( text="Plugin name -------------------    installed Version   StoreVers ")
			for plID in  plugList:
				item = plugList[plID]
				if item["pType"] !="plugin": continue
				pName   = item["plugName"]
				pID     = item["pid"]
				version = item["version"]
				exVersion ="not available" 
				if item["version"].find("no") ==-1:
					exVersion =   VS.versionCheck(plID,"0.0.0",indigo,0,0, printToLog="no",force =True)
				self.ML.myLog( text=pName.ljust(35)+str(version).ljust(20)+str(exVersion))
				time.sleep(1.5)
			self.ML.myLog( text="Plugin name -------------------    END")


####-----------------  print device / variable states .. ---------
	def inpPrintTriggers(self):


		triggers={}
		for trig in indigo.triggers:
			#self.ML.myLog( text="tr id "+ unicode(trig.id))
			tId= str(trig.id)
			tName=trig.name
			triggers[tName]={}
			triggers[tName]["id"]=tId
			triggers[tName]["id2"]=""
			triggers[tName]["vdName"]=""
			triggers[tName]["other"]=""
			triggers[tName]["type"]="other"
			
			
			type=""
			try:
				triggers[tName]["id2"]=unicode(trig.variableId)
				triggers[tName]["vdName"]=indigo.variables[trig.variableId].name
				triggers[tName]["type"]="variable"
				type="variable"
			except:
				pass
			try:
				triggers[tName]["id2"]=unicode(trig.interface)
				type="Interface"
				triggers[tName]["type"]="interface"
			except:
				pass
			try:
				triggers[tName]["id2"]=unicode(trig.pluginId)
				triggers[tName]["vdName"]=unicode(trig.pluginTypeId)
				type="plugin"
				triggers[tName]["type"]="plugin"
			except:
				pass
			try:
				triggers[tName]["id2"]=unicode(trig.emailFilter)
				type="email"
			except:
				pass



			if type == "variable":
				try:
					triggers[tName]["other"]+= "chgType: "+ unicode(trig.variableChangeType)
					triggers[tName]["other"]+= "-- compareTo: "+ unicode(trig.variableValue)
				except:
					pass    
			elif type == "interface":
				pass
			elif type == "email":
				try:
					triggers[tName]["vdName"]="from: "+unicode(trig.emailFrom)
					triggers[tName]["other"] ="Subj: "+unicode(trig.emailSubject)
					triggers[tName]["type"]  ="emailIncoming"
				except:
					pass
			elif type == "plugin":
				try:
					triggers[tName]["vdName"]=unicode(trig.pluginTypeId)
					triggers[tName]["type"]="plugin"
					try:
						triggers[tName]["other"]+= unicode(trig.globalProps[trig.pluginId]["description"])
						#triggers[tName]["vdName"]+= ";  targedev "+ indigo.devices[int(trig.globalProps[trig.pluginId]["targetDev"])].name
					except:
						pass    
					if  unicode(trig.pluginTypeId).find(zwave)>-1:
						triggers[tName]["type"]="device-Zwave"
				except:
					pass

			else:  ## must be device
				type="device"
				try:
					triggers[tName]["id2"]=unicode(trig.deviceId)
					triggers[tName]["vdName"]+=indigo.devices[trig.deviceId].name
					triggers[tName]["type"]="device"
				except:
					pass    

			try:
				triggers[tName]["other"]+= "cmd: "+ unicode(trig.command)
				triggers[tName]["other"]+= "-- button/Group: "+ unicode(trig.buttonOrGroup)
			except:
				pass    
			try:
				triggers[tName]["other"]+= "state: "+ unicode(trig.stateSelector)
				triggers[tName]["other"]+= "-- changeType: "+ unicode(trig.stateChangeType)
				triggers[tName]["other"]+= "-- compareTo: "+ unicode(trig.stateValue)
			except:
				pass    



		tList=sorted(triggers)  
		indigo.server.log(u"\n                 ============== Print for each Trigger  devices/variables that trigger them      =============" ," ")
		indigo.server.log("Trig.ID      Trig.SourceType Dev/Var/Plugin-ID           Source-D/V/P-Name         Other info", type="Trigger Name")
		for tName in tList:
			indigo.server.log(triggers[tName]["id"].ljust(12)+" "+triggers[tName]["type"].ljust(15)+" "+triggers[tName]["id2"].ljust(27)[-27:] +" "+  triggers[tName]["vdName"].ljust(25)[:25]+" "+  triggers[tName]["other"],type=tName[:30]  )
		return


####-----------------  print device / variable states .. ---------
	def inpPrintdevzWave(self):
	
	
		indigo.server.log(u"\n                 ============== Print zwave info of devices to logfile =============" ," ")
		nList=[]
		for dev in indigo.devices:
			if unicode(dev.protocol).find("ZWave")==-1:	continue
			if "com.perceptiveautomation.indigoplugin.zwave" not in dev.globalProps:
				indigo.server.log(" zwave not working for device" + dev.name)
				continue
			if "zwNodeNeighborsStr" not in dev.globalProps["com.perceptiveautomation.indigoplugin.zwave"]: continue
			neighb = unicode(dev.globalProps["com.perceptiveautomation.indigoplugin.zwave"]["zwNodeNeighborsStr"])
			if len(neighb)< 1: continue
			address= unicode(dev.globalProps["com.perceptiveautomation.indigoplugin.zwave"]["address"]).rjust(4)
			nList.append((address,(dev.name+"-"+address).rjust(45)+":  "+neighb,str(dev.id)))
		
		indigo.server.log(("  --------------------------device Name -addr").rjust(40)+":  neighbors","Device ID")
		nList=sorted(nList)
		for out in nList:
			indigo.server.log( out[1],out[2])  #["zwNodeNeighborsStr"])


		indigo.server.log(u"creating .dot file for GRAPHVIZ" )
		nList=[]
		for dev in indigo.devices:
			if unicode(dev.protocol).find("ZWave")==-1:	continue
			if "com.perceptiveautomation.indigoplugin.zwave" not in dev.globalProps: continue
			if "zwNodeNeighborsStr" not in dev.globalProps["com.perceptiveautomation.indigoplugin.zwave"]: continue
			neighb = unicode(dev.globalProps["com.perceptiveautomation.indigoplugin.zwave"]["zwNodeNeighborsStr"])
			if len(neighb)< 1: continue
			address= unicode(dev.globalProps["com.perceptiveautomation.indigoplugin.zwave"]["address"]).rjust(4)
			for out in neighb.split(", "):
				nList.append((address,dev.name,out.rjust(4)))
		
		nList=sorted(nList)

		f=open(self.userIndigoPluginDir+"zWave.dot","w")
		f.write("digraph hierarchy {\n")
		f.write("    node [shape = circle];\n")
		currentDev=""
		for out in nList:
				if currentDev==out[0]: continue
				###indigo.server.log(unicode(out))
				f.write((u"    "+(out[0])+u" [label=\""+unicode(out[0]).lstrip()+u" - "+(out[1])+u"\"]\n").encode("utf-8"))
				currentDev=out[0]
		for out in nList:
			if out[2].find(u"none")==-1:
				f.write((u"        "+out[0]+u" ->"+out[2]+u";\n").encode("utf-8"))
		f.write(u"}\n")
		f.close()
		indigo.server.log(    u"Created graphviz input file:   \""+self.userIndigoPluginDir+"zWave.dot\"")
		
		if os.path.isfile("/usr/local/bin/dot"):
			subprocess.Popen("/usr/local/bin/dot -Tsvg "+self.userIndigoPluginDir+"zWave.dot > "+self.userIndigoPluginDir+"zWave.svg ",shell=True).communicate()
			indigo.server.log(u"Created graphviz outpout file: \""+self.userIndigoPluginDir+"zWave.svg\"")

		return
	
####-----------------  print device / variable states .. ---------
	def inpPrintdevStates(self):


		indigo.server.log(u"\n                 ============== Print variables and devices to logfile =============" ," ")
		indigo.server.log(("-----------------------------variables").rjust(40)+":  Value","Variable ID")
		for var in indigo.variables:
			name=var.name
			id=var.id
			try:
				val= var.value
			except:
				val=""
			indigo.server.log(name.rjust(40)+":  "+unicode(val),str(id))


		indigo.server.log(u"\n "," ")
		indigo.server.log(("  ---------------------------device Name").rjust(40)+":  State(Value), State(Value), ...","Device ID")
		for dev in indigo.devices:
			name=dev.name
			id =str(dev.id)
		
			theStates = dev.states.keys()
			retList=[]
			count=0
			for test in theStates:
				val= dev.states[test]
				count+=1
				retList.append(test+"(\""+unicode(val)[:20]+"\"), ")
			first= (name).rjust(40)+":  "
			for ii in range(0,count,5):
				out=""
				for jj in range(ii,min(ii+5,count),1):
					out+=retList[jj]
				indigo.server.log(first+out,id)
				first= u" ".rjust(40)+":  "
				id=" "

		return



####-----------------  ---------
	def executeFIXAction(self, action,typeId="",devId=""):
		valuesDict=action.props
		valuesDict, error = self.executeSQL(valuesDict,typeId,devId,"fix")
		self.fixSQLStarted=True
		self.fixSQLSteps=0
		return
####-----------------  ---------
	def executeFIX(self, valuesDict=""):
		
		self.fixSQLStarted=1
		self.fixSQLSteps=0
		return valuesDict
####-----------------  ---------
	def executeFIXCancel(self, valuesDict=""):
		
		self.fixSQLStarted=99
		self.fixSQLSteps=0
		return valuesDict

####-----------------  ---------
	def executeBACKUPindigoAction(self, action,typeId="",devId=""):
		self.executeBACKUPindigo()
		return
####-----------------  ---------
	def executeBACKUPindigo(self, valuesDict="",typeId="",devId=""):
		cmd="cp -R  '"+self.indigoPath+"databases' '" +self.userIndigoPluginDir+"'"
		if self.ML.decideMyLog("Logic"): self.ML.myLog( text=u" indigo backup: " + cmd)
		subprocess.Popen(cmd, shell=True)
		cmd="cp -R  '"+self.indigoPath+"Preferences' '" +self.userIndigoPluginDir+"'"
		if self.ML.decideMyLog("Logic"): self.ML.myLog( text=u" indigo backup: " + cmd)
		subprocess.Popen(cmd, shell=True)
		return valuesDict

####-----------------  ---------
	def executeBACKUPAction(self, action,typeId="",devId=""):
		valuesDict=action.props
		valuesDict, error = self.executeSQL(valuesDict,typeId,devId,"backup")
		self.backupStarted=True
		self.backupSteps=0
		return
####-----------------  ---------
	def executeBACKUP(self, valuesDict="",typeId="",devId=""):
		
		valuesDict, error = self.executeSQL(valuesDict,typeId,devId,"backup")
		self.backupStarted=True
		self.backupSteps=0
		return valuesDict


####-----------------  ---------
	def executeBACKUPpostgresAction(self, valuesDict="",typeId="",devId=""):
		self.executeBACKUPpostgres()

####-----------------  ---------
	def executeBACKUPpostgres(self, valuesDict="",typeId="",devId=""):
		ret, err = self.readPopen("ps -ef | grep '/pg_dump ' | grep -v grep ")
		if len(ret)>20:
			self.ML.myLog( text=u"previous postgres backup dump  job still running, please wait until finished ")
			return 

		## move last dump  to dump-1 file
		if os.path.isfile(self.userIndigoPluginDir+"postgresBackup.zip-1"):
			os.remove(self.userIndigoPluginDir+"postgresBackup.zip-1")
		if os.path.isfile(self.userIndigoPluginDir+"postgresBackup.zip"):
			os.system("mv "+self.userIndigoPluginDir+"postgresBackup.zip  "+self.userIndigoPluginDir+"postgresBackup.zip-1")

		commandLineForDump = self.postgresPasscode + self.liteOrPsqlString.replace("psql","pg_dump")
		if self.postgresUserId != "" and self.postgresUserId !="postgres": commandLineForDump = commandLineForDump.replace(" postgres "," "+self.postgresUserId+" ")
		
		# add zip, doing dump and zip together eats too much CPU, need to do it in 2 steps , then remove temp file  ( dump && gzip && rm ... )
		cmd= commandLineForDump+"  > "+  self.userIndigoPluginDir+"postgresBackup.dmp  &&  gzip "+ self.userIndigoPluginDir+"postgresBackup.dmp  > " + self.userIndigoPluginDir+"postgresBackup.zip  &&  rm "+ self.userIndigoPluginDir+"postgresBackup.dmp  &"
		self.ML.myLog( text=cmd)
		subprocess.Popen(cmd, shell=True)
		self.ML.myLog( text='to restore: 1. in pgadmin: "DROP DATABASE indigo_history;"   "CREATE DATABASE indigo_history template = template0;"  2.unzip postgresBackup.zip ; 3. "pathtopostgresapp/psql indigo_history -U postgres < postgresBackup"' )
		self.postgresBackupStarted = time.time() 

			 
		return valuesDict

####-----------------  ---------
	def executeSQL(self, valuesDict,typeId,devId,mode):
		ret, err = self.readPopen("ps -ef | grep 'Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' | grep -v grep ")

		if len(ret)>20:
			self.ML.myLog( text=u"previous SQLite job still running, please wait until finished ")
			return (valuesDict, u"previous SQLite job still running, please wait until finished ")

		try:
			os.remove(self.userIndigoPluginDir+"steps")
		except:
			pass
		test=""
		ii=0
		for var in indigo.variables:
			ii+=1
			if ii==3:  ## pick the third variable
				test = "variable_history_"+str(var.id)
				break
		cmd=self.pythonPath+ " '"+self.indigoPath+"Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' "+mode+" "+test+" "+self.noOfBackupCopies
		self.ML.myLog( text=u"starting SQLite job "+cmd )
		self.ML.myLog( text=u"...                       started  at "+ str(datetime.datetime.now()) )
		subprocess.Popen(cmd, shell=True)
		return (valuesDict, 0)


	def getMenuActionConfigUiValues(self, menuId):
		
		if menuId == "printDeviceStates":
			valuesDict = copy.copy(self.printDeviceStatesDictLast)
		elif menuId == "SQLbackup":
			valuesDict = indigo.Dict()
			valuesDict["msgbkup"]="click EXECUTE, then CLOSE - or just CLOSE to not start BACKUP"
		elif menuId == "fixSQL":
			valuesDict = indigo.Dict()
			valuesDict["msgbkup"]="click EXECUTE, then CLOSE - or just CLOSE to not start FIX"

		else:
			valuesDict = indigo.Dict()
		
		errorMsgDict = indigo.Dict()

		return (valuesDict, errorMsgDict)


####-----------------   for event           ---------



####-----------------             ---------
	def buttonConfirmPluginCALLBACK(self,valuesDict="",typeId="", targetId=0):
		if valuesDict["devOrVar"] =="dev":
			valuesDict["msg"]="select device"
		else:
			valuesDict["msg"]="select variable"
		
		return valuesDict


######################################################################################
	####-----------------  event trigger fior cpu of plugin > xx
######################################################################################
 
	def filterPlugin(self,  filter="", valuesDict=None, typeId="", targetId=0):

		retList = []
		psef  = self.getPSEF(grep="ndigo")
		plugList = self.getActivePlugins(psef)
		
		if filter =="new":
			for plID in  plugList:
				plug = plugList[plID]
				if plug["pType"] !="plugin": continue
				pName   = plug["plugName"]
				if plID in self.PLUGINSusedForCPUlimts: continue
				retList.append((plID,pName) )
			retList = sorted( retList, key=lambda x:(x[1]) )
		if filter =="existing":
			for plID in  plugList:
				plug = plugList[plID]
				pName   = plug["plugName"]
				if plug["pType"] !="plugin": continue
				if plID not in self.PLUGINSusedForCPUlimts: continue
				retList.append((plID,pName) )
			retList = sorted( retList, key=lambda x:(x[1]) )
		return retList


	####-----------------  ---------
	def buttonconfirmRemovePluginCALLBACK(self, valuesDict=None, typeId="", targetId=0):
		plug  = valuesDict["selectExistingPlugin"]
		if len(plug) < 2: return valuesDict
		if plug in self.PLUGINSusedForCPUlimts:
			del self.PLUGINSusedForCPUlimts[plug]
		self.writeJson(self.indigoPreferencesPluginDir+"PLUGINSusedForCPUlimts.json", self.PLUGINSusedForCPUlimts)
		return valuesDict
	####-----------------  ---------
	def buttonConfirmPluginCALLBACK(self, valuesDict=None, typeId="", eventId=0):
		if valuesDict["newOrExistingPlugin"]  == "new":
			plug  = valuesDict["selectNewPlugin"]
		if valuesDict["newOrExistingPlugin"]  == "existing":
			plug  = valuesDict["selectExistingPlugin"]
		if len(plug) < 2: return valuesDict
		if plug not in self.PLUGINSusedForCPUlimts:
			self.PLUGINSusedForCPUlimts[plug] = {"evID":eventId, "lastCPU":0, "lastTime":0, "cpuThreshold": float(valuesDict["cpuThreshold"]), "lastCPUsub":{} }
		self.writeJson(self.indigoPreferencesPluginDir+"PLUGINSusedForCPUlimts.json", self.PLUGINSusedForCPUlimts)
		return valuesDict

	####-----------------  ---------
	def validateEventConfigUi(self, valuesDict=None, typeId="", eventId=0):
		self.writeJson(self.indigoPreferencesPluginDir+"PLUGINSusedForCPUlimts.json", self.PLUGINSusedForCPUlimts)
		return (True, valuesDict)
		

	####-----------------  
	def getPSEF(self,useEncode=True, grep=""):
		ret =""
		try:
			if grep !="":
				GREP= " | grep -v grep | grep '"+grep+"' "
			else: 
				GREP=" "
			if useEncode:
				try: 
					ret, err = self.readPopen("export LANG="+self.localeLanguage+"."+self.enccodingChar+" &&/bin/ps -ef"+GREP)
				except: 
					useEncode = False
			if not useEncode:
				ret, err = self.readPopen("/bin/ps -ef "+GREP)
			
			ret  = ret.strip("\n")
		except  Exception as e:
			self.exceptionHandler(40,e)
		#self.ML.myLog( text= "getPSEF {} ".format(ret))
		return ret

	####-----------------  
	def getPSAUX(self,useEncode=False, grep=""):
		ret =""
		try:
			if grep !="":
				GREP= " | grep -v grep | grep '"+grep+"' "
			else: 
				GREP=" "
			if useEncode:
				try: 
					ret, err = self.readPopen("export LANG="+self.localeLanguage+"."+self.enccodingChar+" &&/bin/ps aux"+GREP)
				except: 
					useEncode = False
			if not useEncode:
				ret, err = self.readPopen("/bin/ps aux"+GREP)
			ret  = ret.strip("\n")
		except  Exception as e:
			self.exceptionHandler(40,e)
		return ret

	####-----------------  
	def addremovePlugin(self,plugID,plugList):
			if self.PLUGINSallCalcCPU:
				if plugID not in self.PLUGINSusedForCPUlimts:
					if plugID in plugList:
						self.PLUGINSusedForCPUlimts[plugID] = {"evID":0, "lastCPU":0, "lastCPUsub":{}, "lastTime":0, "cpuThreshold": 99999999999, "plugData":plugList[plugID]}
				if plugID in self.PLUGINSusedForCPUlimts:
					if plugID in plugList:
						if "plugData" not in self.PLUGINSusedForCPUlimts:
							self.PLUGINSusedForCPUlimts[plugID]["plugData"]= plugList[plugID]
						if "lastCPUsub" not in self.PLUGINSusedForCPUlimts[plugID]:
							self.PLUGINSusedForCPUlimts[plugID]["lastCPUsub"]= {}

			else:
				if plugID  in self.PLUGINSusedForCPUlimts:
					if self.PLUGINSusedForCPUlimts[plugID]["evID"] == "0":
						del self.PLUGINSusedForCPUlimts[plugID] 

	
	####-----------------  
	def checkPluginCPU(self):
		if not self.PLUGINSallCalcCPU: return 
		if time.time() - self.lastPluginCpuCheck < 100: return 
		try:
			psef     = self.getPSEF()
			plugList = self.getActivePlugins(psef)
			self.addremovePlugin("IndigoServer",plugList)
			self.addremovePlugin("IndigoClient",plugList)
			self.addremovePlugin("IndigoWebServer",plugList)
			self.addremovePlugin("postgres",plugList)
			self.addremovePlugin("VBox",plugList)
			self.addremovePlugin("fing",plugList)


			plugListALL = copy.copy(plugList)
			for plugID in self.PLUGINSusedForCPUlimts:
				if plugID in plugList: 
					if "plugData" in self.PLUGINSusedForCPUlimts[plugID]: 
						if "cpu" not in self.PLUGINSusedForCPUlimts[plugID]["plugData"]:
							self.PLUGINSusedForCPUlimts[plugID]["plugData"] = plugList[plugID]
				else:
					self.PLUGINSusedForCPUlimts[plugID]["lastCPU"] = 0
					if "plugData" not in self.PLUGINSusedForCPUlimts[plugID]: continue
					plugListALL[plugID]                            = self.PLUGINSusedForCPUlimts[plugID]["plugData"]
					plugListALL[plugID]["cpu"]                     = "0:0.0"

			totalDelta = 0
			for plugID in  plugListALL:
				plug = plugListALL[plugID]
				###indigo.server.log(" doing "+ str(plug))
				if len(plugID) < 3: continue
				self.addremovePlugin(plugID,plugListALL)
				if plugID not in self.PLUGINSusedForCPUlimts: continue
				cpu = self.calcCPU(plug["cpu"])
			
				deltaT    = time.time() - self.PLUGINSusedForCPUlimts[plugID]["lastTime"]
				factor    = max(0.01,deltaT/100.)
				deltaCPU  = max(0, (cpu - self.PLUGINSusedForCPUlimts[plugID]["lastCPU"]) / factor )
				totalDelta += deltaCPU
				if self.ML.decideMyLog("Logic"): self.ML.myLog( text="plugID: "+plugID+"  cpu: "+ unicode(cpu)+";  deltaCPU: "+unicode(deltaCPU)+";  deltaT: "+unicode(deltaT) +";  lastCPU: "+ unicode(self.PLUGINSusedForCPUlimts[plugID]["lastCPU"]) +";  cpuThreshold: "+ unicode(self.PLUGINSusedForCPUlimts[plugID]["cpuThreshold"]) )
				if deltaCPU > self.PLUGINSusedForCPUlimts[plugID]["cpuThreshold"]:
					if self.ML.decideMyLog("Logic"): self.ML.myLog( text="triggering > threshold for "+plugID )
					self.triggerEvent(self.PLUGINSusedForCPUlimts[plugID]["evID"])
				self.PLUGINSusedForCPUlimts[plugID]["lastTime"] = time.time()
				self.PLUGINSusedForCPUlimts[plugID]["lastCPU"]  = cpu

					
				# store result in variable CPU_usage_short_plugID
				plugID = plugID.replace(" ","-")
				ss = plugID.split(".")
				plugidShort = ""



				deltaCPUsub = 0
				update = False
				if len(plug["subprocessesPid"]) > 0 and plug["pType"] in ["plugin","postgres"]:
					update= True
					for subPLid in plug["subprocessesPid"]:
						cpu = self.calcCPU(plug["subprocessesPid"][subPLid]["cpu"])
						if subPLid not in self.PLUGINSusedForCPUlimts[plugID]["lastCPUsub"]:
							self.PLUGINSusedForCPUlimts[plugID]["lastCPUsub"][subPLid] = cpu
						deltaCPUsub += cpu - self.PLUGINSusedForCPUlimts[plugID]["lastCPUsub"][subPLid]
						self.PLUGINSusedForCPUlimts[plugID]["lastCPUsub"][subPLid] = cpu
				deltaCPUsub  = max(0, deltaCPUsub / factor )
					
				#try:  ## add cpu to main    
				#    var = indigo.variables["CPU_usage_"+plugidShort+"_sub"]
				#    indigo.variable.updateValue("CPU_usage_"+plugidShort+"_sub","%.2f"%deltaCPUsub)
				#except: 
				#    if update: 
				#        indigo.variable.create("CPU_usage_"+plugidShort+"_sub","%.2f"%deltaCPUsub,"")



				for n in range(2,len(ss)):
					if ss[n] in ["com","org","net","perceptiveautomation","indigoplugin","indiPref"]: continue
					plugidShort+=ss[n]+"."
				plugidShort = plugidShort.strip(".").replace(" ","_")
				if len(plugidShort)< 2:
					plugidShort = plugID
				try:     
					var = indigo.variables["CPU_usage_"+plugidShort]
					indigo.variable.updateValue("CPU_usage_"+plugidShort,"%.2f"%(deltaCPU+deltaCPUsub))
				except:  
					indigo.variable.create("CPU_usage_"+plugidShort,"%.2f"%(deltaCPU+deltaCPUsub),"")

				totalDelta +=deltaCPUsub
					
				
			self.writeJson(self.indigoPreferencesPluginDir+"PLUGINSusedForCPUlimts.json", self.PLUGINSusedForCPUlimts)
			if self.PLUGINSallCalcCPU:
				try:     
					var = indigo.variables["CPU_usage_AllIndigoAndPlugins"]
					indigo.variable.updateValue("CPU_usage_AllIndigoAndPlugins","%.2f"%totalDelta)
				except:  
					indigo.variable.create("CPU_usage_AllIndigoAndPlugins","%.2f"%totalDelta,"")
			self.lastPluginCpuCheck = time.time()
		except  Exception as e:
			self.exceptionHandler(40,e)
		return 


####-----------------   for menue aded --- lines          ---------
	def calcCPU(self, cpu):
		newCPU = cpu.split(":")
		if len(newCPU) ==2:
			cpu = float(newCPU[0])*60 + float(newCPU[1]) 
		else:
			cpu =  float(newCPU[1])
		return cpu
	 
####-----------------   for menue aded --- lines          ---------
	def dummyCALLBACK(self):
		
		return

####-----------------   get number of records for each device / variable and print to logfile          ---------
		## this needs to be done in batch as it might take some time
	def executePrintNumberOfRecords(self,valuesDict="",typeId="",devId=""):
		self.printNumberOfRecords =1
		indigo.server.log("started print # of records for devices and variables ")
		return
####-----------------             ---------
	def devOrVarCALLBACKAction(self,action1,typeId="",devId=""):
		self.devOrVarCALLBACK(action1)
		return

####-----------------   devOrVarCALLBACK          ---------
	def devOrVarCALLBACK(self,valuesDict="",typeId="",devId=""):
		if valuesDict["devOrVar"] =="dev":
			valuesDict["msg"]="select device"
		else:
			valuesDict["msg"]="select variable"
		
		return valuesDict

####-----------------   create list of devcies that have states          ---------
	def filterDevices(self,filter="",valuesDict="",typeId="",devId=""):
		retList=[]
		for dev in indigo.devices:
			for state in dev.states.keys():
				retList.append((dev.id, dev.name))# if we are here we found a state that can be selected
				break
		return retList
	
####-----------------   pickDeviceCALLBACK          ---------
	def pickDeviceCALLBACKAction(self,action1="",typeId="",devId=""):
		self.pickDeviceCALLBACK(action1)
		return

####-----------------   pickDeviceCALLBACK          ---------
	def pickDeviceCALLBACK(self,valuesDict="",typeId="",devId=""):
		if self.ML.decideMyLog("Logic"): self.ML.myLog( text=unicode(valuesDict))
		self.devID= int(valuesDict["device"])
		self.varID= 0
		valuesDict["msg"]="select states for device selected"
		
		return valuesDict
####-----------------   pickVariableCALLBACK          ---------
	def pickVariableCALLBACKAction(self,action1="",typeId="",devId=""):
		self.pickVariableCALLBACK(action1)
		return

####-----------------   pickVariableCALLBACK          ---------
	def pickVariableCALLBACK(self,valuesDict="",typeId="",devId=""):
		self.varID= int(valuesDict["variable"])
		self.devID= 0
		valuesDict["msg"]=""
		
		return valuesDict

####-----------------   ipnumberOfDeviceCallback          ---------
	def ipnumberOfDeviceCallback(self,valuesDict="",typeId=""):
		ipNumber= valuesDict["ipDevice"]
		self.ML.myLog( text="\nping result for /sbin/ping -c 2 -W 2  "+ipNumber+"    -------------- START")
		ret, err = self.readPopen("/sbin/ping -c 2 -W 2  "+ipNumber)
		indigo.server.log("\n"+ret,type=" ")
		if len(ret) >2: self.ML.myLog( text="ping error:"+ ret, mType=" ")
		self.ML.myLog( text="ping           ------------------ END", mType=" ")
		return valuesDict


####-----------------   create state list for first state, add * as option          ---------
	def filterStates0(self,filter="",valuesDict="",typeId="",devId=""):
		if self.devID ==0: return [("0","")]
		retList=[]
		dev =  indigo.devices[self.devID]
		for state in dev.states.keys():
			retList.append((state, state))
		retList.append(("*","* = all"))
		return retList
		
####-----------------   create state list for other states          ---------
	def filterStates(self,filter="",valuesDict="",typeId="",devId=""):
		if self.devID ==0: return [("0","--- do not use ---")]
		retList=[]
		dev =  indigo.devices[self.devID]
		for state in dev.states.keys():
			retList.append((state, state))
		retList.append(("0","--- do not use ---"))
		return retList


####-----------------   collect all info and call print         ---------
	def pruneDevsandVarsAction(self,action):
		try:
			valuesDict=action.props
			if "deleteBeforeThisDays" not in valuesDict: 
				self.ML.myLog( text="pruneDevsandVarsaction error  deleteBeforeThisDays missing ")
				return
			if "devOrVar" not in valuesDict:     
				self.ML.myLog( text="pruneDevsandVarsaction error  devOrVar missing ")
				return
			if valuesDict["devOrVar"] =="var" and  "variable" not in valuesDict:       
				self.ML.myLog( text="pruneDevsandVarsaction error  variable missing ")
				return
			if  valuesDict["devOrVar"] =="dev" and "device" not in valuesDict:       
				self.ML.myLog( text="pruneDevsandVarsaction error  device missing ")
				return

			if  valuesDict["devOrVar"] =="var":
				try:
					id =    indigo.variables[int(valuesDict["variable"])]
				except:
					try:
						id =    indigo.variables[valuesDict["variable"]].id
						valuesDict["variable"] = str(id)
					except:
						self.ML.myLog( text="pruneDevsandVarsaction  variable "+valuesDict["variable"]+ " does not exist")
						return  

			if  valuesDict["devOrVar"] =="dev":
				try:
					id =    indigo.variables[int(valuesDict["device"])]
				except:
					try:
						id =    indigo.devices[valuesDict["device"]].id
						valuesDict["device"] = str(id)
					except:
						self.ML.myLog( text="pruneDevsandVarsaction  device "+valuesDict["device"]+ " does not exist")
						return    

			if self.ML.decideMyLog("Logic"): self.ML.myLog( text="pruneDevsandVarsaction  "+unicode(valuesDict))
			self.executePruneDatabase(valuesDict,test=False)
		
		except Exception as e:
			self.exceptionHandler(40,e)



####-----------------   collect all info and call print         ---------
	def executePruneDatabaseTEST(self,valuesDict="",typeId="",devId=""):
		self.executePruneDatabase(valuesDict,test=True)
		
####-----------------   collect all info and call print         ---------
	def executePruneDatabase(self,valuesDict="",typeId="",devId="",test=False):
		
		if test: loglevel="all"
		else:    loglevel="SQL"
		
		try:
			devOrVar         = valuesDict["devOrVar"]
			if devOrVar =="var":
				table         = "variable_history_"+valuesDict["variable"]
				name= indigo.variables[int(valuesDict["variable"])].name
			else:   
				table         = "device_history_"+valuesDict["device"]
				name = indigo.devices[int(valuesDict["device"])].name
			deleteBeforeThisDays = int(valuesDict["deleteBeforeThisDays"])
			nowTS =datetime.datetime.now() 
			dateCutOff = (nowTS-datetime.timedelta(deleteBeforeThisDays,hours=nowTS.hour,minutes=nowTS.minute,seconds=nowTS.second)).strftime("%Y%m%d%H%M%S")
			if self.ML.decideMyLog(loglevel): self.ML.myLog( text="prune records for device / var = "+ name +" before "+ dateCutOff)
			
			orderby = ""
			if self.orderByID =="yes":
				orderby = " ORDER by id "

			
			if self.liteOrPsql =="sqlite":
				ret, err = self.readPopen("/bin/ps -ef | grep sqlite3 | grep -v grep ")
				if len(ret) > 10:
					self.ML.myLog( text= "SQLITE3 is still running please stop before using prune database")
					return
					
			if self.liteOrPsql =="sqlite": 
				cmd=    "/usr/bin/sqlite3  -separator \" \" '"+self.indigoPath+ "logs/indigo_history.sqlite' \"SELECT id,strftime('%Y%m%D%H%M%S',ts,'localtime') FROM "+table+orderby+";\"\n"
			else:    
				cmd= self.liteOrPsqlString+ " -t -A -F ' ' -c \"SELECT id, to_char(ts,'YYYYmmddHH24MIss') FROM "+table+orderby+";\"\n"
				if self.postgresUserId != "" and self.postgresUserId != "postgres": cmd = cmd.replace(" postgres "," "+self.postgresUserId+" ")

			ret, err = self.readPopen(cmd)
			lines = ret.split("\n")
			
			firstIDtoKeep          = 0
			nn                     = 0
			timeWOmsec             = ""
			for line in lines:
				nn+=1
				#if nn < 100: self.ML.myLog( text="line# "+ str(nn)+"  "+ line)
				if len(line)< 2: continue
				try:
					items = line.split()
					if len(items) != 2:
						continue
					firstIDtoKeep = int(items[0])  # test if integer
					ts= items[1].split(".")[0]   # = HH:MM:SS
					timeWOmsec= ts.split(".")[0]
					if timeWOmsec >= dateCutOff:
						break
				except  Exception as e:#
					self.exceptionHandler(40,e)
						
			if self.ML.decideMyLog(loglevel): self.ML.myLog( text= "first record found that is above cut off at "+ timeWOmsec+"; id: "+ str(firstIDtoKeep)+"; that is the "+str(nn) +"th record out of " +str(len(lines))+ " total records" )
			if self.liteOrPsql =="sqlite": 
					sqlDeleteCommands=    "/usr/bin/sqlite3 '"+self.indigoPath+ "logs/indigo_history.sqlite' "
			else:    
					sqlDeleteCommands= self.postgresPasscode + self.liteOrPsqlString+ "  -c "
					
			sqlDeleteCommands+="\"DELETE FROM "+table+ " WHERE id < " +str(firstIDtoKeep)+";\""
			if self.ML.decideMyLog(loglevel): self.ML.myLog( text="cmd= "+ sqlDeleteCommands)
			if not test: 
				ret, err = self.readPopen(sqlDeleteCommands)
				if self.ML.decideMyLog("SQL"): self.ML.myLog( text= "SQL returned: "+ ret+"-"+err)

		except Exception as e:
			self.exceptionHandler(40,e)


####-----------------   squeeze postgres database         ---------
	def actionDatabaseSqueeze(self,valuesDict="",typeId="",devId=""):
		if self.executeDatabaseSqueezeCommand.find("EXECUTING") >-1:
			self.ML.myLog( text= "delete duplicate SQL records still running, please wait until finished")
			return 
		self.executeDatabaseSqueeze({"execOrTest":"exec"},typeId="",devId="")

####-----------------   squeeze postgres database         ---------
	def actionDatabaseSqueezeQuiet(self,valuesDict="",typeId="",devId=""):
		if self.executeDatabaseSqueezeCommand.find("EXECUTING") >-1:
			self.ML.myLog( text= "delete duplicate SQL records still running, please wait until finished")
			return 
		self.executeDatabaseSqueeze({"execOrTest":"execquiet"},typeId="",devId="")

####-----------------   squeeze postgres database         ---------
	def executeDatabaseSqueeze(self,valuesDict="",typeId="",devId=""):
		if  valuesDict["execOrTest"] =="stop":
			self.executeDatabaseSqueezeCommand = "stop"
			self.ML.myLog( text= "delete duplicate SQL records stop requested, finishing current table")
			return
		if self.executeDatabaseSqueezeCommand.find("EXECUTING") >-1:
			self.ML.myLog( text= "delete duplicate SQL records still running, please wait until finished")
			return 
			
		self.executeDatabaseSqueezeCommand = valuesDict["execOrTest"]
		
####-----------------   squeeze postgres database         ---------
	def executeDatabaseSqueezeDoitNOW(self):

		execOrTest =  self.executeDatabaseSqueezeCommand    

		if execOrTest.find("EXECUTING") >-1: 
			return

		if execOrTest.find("stop") >-1: 
			return


		if execOrTest == "doNothing": 
			self.executeDatabaseSqueezeCommand =""
			return


		if self.liteOrPsql =="sqlite":
			ret, err = self.readPopen("/bin/ps -ef | grep sqlite3 | grep -v grep ")

			if len(ret) > 10:
				self.ML.myLog( text= "SQLITE3 is still running please stop before using delete duplicate records")
				self.executeDatabaseSqueezeCommand =""
				return

		self.executeDatabaseSqueezeCommand = "EXECUTING"


		if execOrTest == "test": 
			gg=open(self.userIndigoPluginDir+"squeezeSQLall","w")
			
			
		
		self.ML.myLog( text= "Starting to squeeze / delete records with same time stamp from data base, keep only last of each these record ... this can take SEVERAL minutes ..\n SQL  command in:  "+self.userIndigoPluginDir+ "squeezeSQL(all)")
		nAllIn =0
		nAllDelete = 0
		devTables=[]
		for dd in indigo.devices:
			devTables.append(["device_history_" +str(dd.id),dd.name])
		nDEVS = len(devTables)
		nnn=0
		ndevsWdelete = 0
		if execOrTest == "exec": 
			self.ML.myLog( text="del-act/del-pot/totalRECS; SQL ==================----------............" ,mType="#  Device Name " )
			
		for xx in devTables:
			if self.executeDatabaseSqueezeCommand.find("stop") >-1:
				self.ML.myLog( text="HARD stop requested" )
				self.executeDatabaseSqueezeCommand = ""
				break
			table   = xx[0] 
			name    = xx[1]
			#self.ML.myLog( text=" getting duplicate records " +name ,mType="#  Device Name " )
			nnn+=1
			try:
				if self.liteOrPsql =="sqlite": 
					cmd=    "/usr/bin/sqlite3  -separator \" \" '"+self.indigoPath+ "logs/indigo_history.sqlite' \"SELECT id,strftime('%H:%M:%S',ts,'localtime') FROM "+table+";\"\n"
				else:    
					cmd= self.liteOrPsqlString+ " -t -A -F ' ' -c \"SELECT id, to_char(ts,'HH24:MI:ss') FROM "+table+";\"\n"
					if self.postgresUserId != "postgres" and self.postgresUserId != "": 
						cmd	= self.postgresPasscode + cmd.replace(" postgres "," "+self.postgresUserId+" ")
					else:
						cmd	= self.postgresPasscode + cmd

				#self.ML.myLog( text=cmd)
				ret, err = self.readPopen(cmd)
				lines = ret.split("\n")
				#print lines
				idsToDelete     = [] 
				lasttimeWOmsec  = ""
				lastId          = "0"
				nDelete         = 0
				nIn          = 0
				for line in lines:
					if len(line)< 2: continue
					try:
						items = line.split()
						if len(items) != 2:
							continue
						id = str(int(items[0]))  # gest if integer
						ts= items[1].split(".")[0]   # = HH:MM:SS
						timeWOmsec= ts.split(".")[0]
						nIn+=1
						if lasttimeWOmsec == timeWOmsec:  ## pick the ones with same HH:MM:SS
							if lastId != "0":
								idsToDelete.append(lastId)
								#self.ML.myLog( text= line)
								nDelete+=1
						else:   
							lasttimeWOmsec = timeWOmsec
						lastId=id    
					except  Exception as e:
						self.exceptionHandler(40,e)
						 
				if  nDelete == 0: continue

				if self.liteOrPsql =="sqlite": 
					sqlDeleteCommands=    "/usr/bin/sqlite3 '"+self.indigoPath+ "logs/indigo_history.sqlite' "
				else:    
					sqlDeleteCommands = self.postgresPasscode + self.liteOrPsqlString+ "  -c "
					if self.postgresUserId !="" and self.postgresUserId !="postgres": sqlDeleteCommands = sqlDeleteCommands.replace(" postgres "," "+self.postgresUserId+" ")
				sqlDeleteCommands+="\"DELETE FROM "+table+ " WHERE id IN ( " 
				iDstart = 0
				#if os.path.isfile(self.userIndigoPluginDir+"steps"):
				#    os.remove(self.userIndigoPluginDir+"squeezeSQL")  
					
				while True:
					if iDstart >= len(idsToDelete): break
					idString=""
					nIDs =0
					for id in idsToDelete[iDstart:]:
						if len(idString) > int(self.maxSQLlength)-300: 
							self.ML.myLog( text= table +" more than "+str(self.maxSQLlength)+" bytes in sql string, stopping at "+str(self.maxSQLlength), mType=str(nnn)+"-"+name)
							break
						nIDs+=1
						idString += id+ ","
						
					iDstart += nIDs    
					cmd = sqlDeleteCommands +   idString.strip(",")+");\""
				
					if execOrTest =="test":  
						gg.write(cmd+"\n")
						
					elif execOrTest =="exec":  
						self.ML.myLog( text=str(nIDs).rjust(7)+"/"+str(nDelete).rjust(7)+ "/" + str(nIn).ljust(9)+"; "+cmd[0:min(len(cmd),170)]+ "..)\"; ", mType=str(nnn)+"-"+name )

					if execOrTest.find("exec")>-1:
						f=open(self.userIndigoPluginDir+"squeezeSQL","w")  
						f.write(cmd+"\n")
						f.close()
						ret, err = self.readPopen("chmod +xxx "+ self.userIndigoPluginDir+ "squeezeSQL")

					nAllIn       += nIn
					nAllDelete   += nIDs
					ndevsWdelete +=1
					if execOrTest.find("exec") >-1:
						ret, err = self.readPopen(self.userIndigoPluginDir+ "squeezeSQL")
						if execOrTest.find("quiet")==-1 :
							self.ML.myLog( text= ret.strip("\n")+"-"+err.strip("\n"), mType="... sql response:" )
						if ret.lower().find("error")>-1:
							self.ML.myLog( text="stopping due to error you might need to kill sqlite3 processes \n"+ ret.strip("\n")+"-"+err.strip("\n"), mType="... sql error:" )
							break
					
			except Exception as e:
				self.exceptionHandler(40,e)
		if execOrTest.find("exec") >-1:
			self.ML.myLog( text= "Number of devices:"+ str(nDEVS)+"; devices where records where deleted: " +str(ndevsWdelete)+"; TOTAL  # of records deleted: " +str(nAllDelete)+ ";  out of: " + str(nAllIn) +" records  ===============\n", mType="================")

		if execOrTest == "test": 
			try:
				gg.close()
			except:
				pass    
			self.ML.myLog( text= "Test run: Number of devices:"+ str(nDEVS)+"; devices where records should be deleted: " +str(ndevsWdelete)+"; TOTAL  # of records (to be) deleted: " +str(nAllDelete)+ " out of " + str(nAllIn) +" records  ===============\n check out:  "+self.userIndigoPluginDir+"squeezeSQL", mType="================")
		self.executeDatabaseSqueezeCommand = ""
		return    

####-----------------   collect all info and call print         ---------
	def printSQLaction(self,action):
		try:
			valuesDict=action.props
			if self.ML.decideMyLog("Logic"): self.ML.myLog( text="printSQLaction  "+unicode(valuesDict))


			if "id"			not in valuesDict: valuesDict["id"] =""
			if "device"		not in valuesDict: valuesDict["device"] =0
			if "variable"	not in valuesDict: valuesDict["variable"] =0
			if "separator"	not in valuesDict: valuesDict["separator"] =""
			if "printFile"	not in valuesDict: valuesDict["printFile"] =""
			if "state0"		not in valuesDict: valuesDict["state0"] =""
			if "state0Condition" not in valuesDict: valuesDict["state0Condition"] ="any"
			if "state0Value"not in valuesDict: valuesDict["state0Value"] =""
			if "state1Condition" not in valuesDict: valuesDict["state1Condition"] ="any"
			if "state1Value"not in valuesDict: valuesDict["state1Value"] =""
			if "state1"		not in valuesDict: valuesDict["state1"] =""
			if "state2"		not in valuesDict: valuesDict["state2"] =""
			if "state3"		not in valuesDict: valuesDict["state3"] =""
			if "state4"		not in valuesDict: valuesDict["state4"] =""
			if "state5"		not in valuesDict: valuesDict["state5"] =""
			if "state6"		not in valuesDict: valuesDict["state6"] =""
			if "state7"		not in valuesDict: valuesDict["state7"] =""
			if "state8"		not in valuesDict: valuesDict["state8"] =""
			if "devOrVar"	not in valuesDict: valuesDict["devOrVar"] ="dev"
			if "header"		not in valuesDict: valuesDict["header"] ="yes"
			if "numberOfRecords" not in valuesDict: valuesDict["numberOfRecords"] ="1"
			if valuesDict["numberOfRecords"] =="0":
				self.ML.myLog( text=" printSQLaction   numberOfRecords must not be 0")
				return
			

			if valuesDict["devOrVar"] =="dev":
				devId = valuesDict["device"]
				try:
					self.devID= int(devId)
					valuesDict["device"] = self.devID
					valuesDict["variable"] =0
					self.varID= 0
				except:
					try:
						self.devID= indigo.devices[devId].id
						valuesDict["device"] = self.devID
						valuesDict["variable"] =0
						self.varID= 0
					except:
						pass
		
			elif valuesDict["devOrVar"] =="var":
				varId = valuesDict["variable"]
				try:
					self.varID= int(devId)
					valuesDict["variable"] = self.varID
					valuesDict["device"] =0
					self.devID= 0
				except:
					try:
						self.varID= indigo.variables[varId].id
						valuesDict["variable"] = self.varID
						valuesDict["device"] =0
						self.devID= 0
					except:
						pass
			else:
				self.ML.myLog( text=" printSQLaction   variable or dev not specified: "+valuesDict["devOrVar"], errorType="smallErr")

			self.printDeviceStates(valuesDict)
		except  Exception as e:
			self.exceptionHandler(40,e)
		self.executeDatabaseSqueezeCommand = ""        
		return

####-----------------   collect all info and call print         ---------
	def executeprintDeviceStates(self,valuesDict="",typeId="",devId=""):
		self.printDeviceStatesDictLast= copy.copy(valuesDict)
		self.pluginPrefs["printDeviceStates"] =self.printDeviceStatesDictLast
		self.printDeviceStatesDictLast= copy.copy(valuesDict)
		self.printDeviceStates(valuesDict,typeId,devId)
	
####-----------------   collect all info and call print 2         ---------
	def printDeviceStates(self,valuesDict=[],typeId="",devId=""):
		self.printDeviceStatesDictLast= copy.copy(valuesDict)
		self.pluginPrefs["printDeviceStates"] =self.printDeviceStatesDictLast
		self.printDeviceStatesDictLast= copy.copy(valuesDict)
		try:
			indigo.variable.updateValue("SQLValueOutput","")
			indigo.variable.updateValue("SQLLineOutput","")

			devId = valuesDict["device"]
			varId = valuesDict["variable"]
			dev=""
			var=""
			valuesDict["msg"]=""
			states=["","","","","","","","","","","","","","",""]
			if self.ML.decideMyLog("Logic"): self.ML.myLog( text="executeCALLBACK valuesDict: "+unicode(valuesDict))
			if valuesDict["devOrVar"]=="dev":
				if self.devID !=0:
					varId=0
					try:
						devId = int(devId)
					except:
						self.ML.myLog( text="bad data selected, wrong device id "+str(devId), errorType="bigErr")
						valuesDict["msg"]="wrong device id"
						return valuesDict
					if valuesDict["state0"] =="*":
						states=["*"]
					else:
						try:
							states[0] = valuesDict["state0"]
							xx=indigo.devices[devId].states[states[0]]
						except:
							self.ML.myLog( text="bad data selected, wrong device state "+states[0], errorType="bigErr")
							valuesDict["msg"]="wrong device state"
							return valuesDict
						for ii in range(1,10):
							try:
								states[ii] = valuesDict["state"+str(ii)]
								xx=indigo.devices[devId].states[states[ii]]
							except:
								states[ii] = ""
								pass

			elif valuesDict["devOrVar"]=="var":
				if self.varID !=0:
					devId=0
					try:
						varId = int(varId)
						var=indigo.variables[varId]
					except:
						self.ML.myLog( text="bad data selected, wrong variable id "+str(varId), errorType="bigErr")
						valuesDict["msg"]="wrong variable id"
						return valuesDict

					states = ["value"]
			else:
				self.ML.myLog( text="no device or variable selected", errorType="bigErr")
				valuesDict["msg"]="no device or variable selected"
				return valuesDict


			numberOfRecords = str(valuesDict["numberOfRecords"])
				
			
			id = valuesDict["id"]
			try:
				x=int(id)
			except:
				id=""
				
			valuesDict= self.printSQL(devId,varId,states,numberOfRecords,id,valuesDict["separator"],valuesDict["header"],valuesDict)

		except  Exception as e:
			self.exceptionHandler(40,e)
		return valuesDict

####-----------------   create sql statement, execute it and print outpout to logfile          ---------
	def printSQL(self,devId,varId,states,numberOfRecords,id,separator,header,valuesDict):


		try:
			if separator =="tab": separator="	"
		
		
			if separator =="":
				if header !="yes":
					sqlitePGM	= "/usr/bin/sqlite3   -column '"+self.indigoPath+ "logs/indigo_history.sqlite'"
					postGrePGM	= self.liteOrPsqlString +"-t  -c "
				else:
					sqlitePGM	= "/usr/bin/sqlite3  -header -column '"+self.indigoPath+ "logs/indigo_history.sqlite'"
					postGrePGM	= self.liteOrPsqlString +" -c "
			else:
				if header !="yes":
					sqlitePGM	= "/usr/bin/sqlite3  -separator \""+separator+"\" '"+self.indigoPath+ "logs/indigo_history.sqlite'"
					postGrePGM	= self.liteOrPsqlString +" -t -A -F '" +separator+"' -c "
				else:
					sqlitePGM	= "/usr/bin/sqlite3 -header -separator \"" +separator+"\" '"+self.indigoPath+ "logs/indigo_history.sqlite'"
					postGrePGM	= self.liteOrPsqlString +"  -A -F '" +separator+"' -c "


			if self.liteOrPsql =="sqlite":
				ts	= "strftime('%Y-%m-%d-%H:%M:%S',ts,'localtime') as 'ts_local'"
				pgm	= sqlitePGM
			else:
				ts	= "to_char(ts,'YYYY-mm-dd-HH24:MI:ss') as ts"
				if self.postgresUserId != "postgres" and self.postgresUserId != "": 
					pgm	= self.postgresPasscode + postGrePGM.replace(" postgres "," "+self.postgresUserId+" ")
				else:
					pgm	= self.postgresPasscode + postGrePGM


			
			if devId !=0:
				idStr=str(devId)
				if self.ML.decideMyLog("SQL"): self.ML.myLog( text="print SQL data for device "+idStr+"/"+indigo.devices[devId].name+" states: "  +  str(states))
				devOrVar ="device_history_"
			elif varId !=0:
				idStr=str(varId)
				if self.ML.decideMyLog("SQL"): self.ML.myLog( text="print SQL data for variable "+idStr+"/"+indigo.variables[varId].name)
				devOrVar ="variable_history_"
			else:
				self.ML.myLog( text="print SQL data  no variable or device given", errorType="bigErr")
				valuesDict["msg"]="no device or variable given"
				return valuesDict

	## a more complex way with limit and offset if problem with few records and OFSET becomes negative     in  OFFSET (SELECT COUNT(*) FROM "+devOrVar+ idStr+")-"+numberOfRecords
	## sqlite with limt and id >
	# /usr/bin/sqlite3	-header -column '/Library/Application Support/Perceptive Automation/Indigo 6/logs/indigo_history.sqlite' "WITH t AS (SELECT id, datetime(ts,'localtime'),Signal from device_history_1040551329 WHERE ID > 2) SELECT * from t LIMIT 20;"
	## same with psql
	# /Library/PostgreSQL/bin/psql indigo_history postgres  -c  "WITH t AS (SELECT id,  to_char(ts,'YYYY-mm-dd HH24:MI:ss'),Signal from device_history_1040551329 WHERE ID > 0) SELECT * from t LIMIT 20;"

			if self.orderByID =="yes":
				orderby = " ORDER by id "
			else:
				orderby = ""
			fixOutput = False

			for ss in range(len(states)):
				if states[ss] != "*" and states[ss] != "":
					if self.liteOrPsql == "sqlite":
						states[ss] = "["+states[ss].lower()+"]"
					else:
						states[ss] = '\\"'+states[ss].lower()+'\\"'
			
			sqlCommandText=  pgm
			if states[0] == "*":
				if self.liteOrPsql =="sqlite":
					sqlCommandText+=  " \"SELECT "+ts+" , * "
					fixOutput = True
				else:
					sqlCommandText+=  " \"SELECT * "
			else:
				sqlCommandText+=  " \"SELECT id, "+ts
				for st in states:
					if st != "":
						sqlCommandText+=","+st.replace(".","_")
			sqlCommandText+=  " from "+devOrVar+ idStr
			
			where =""
			andWhere =" WHERE"


			if states[0] !="*":
				if valuesDict["state0Condition"] !="any" and valuesDict["state0Condition"] !="" and valuesDict["state0Value"] !="":
					andWhere =" AND "
					if valuesDict["state0Condition"] =="eq"  :      
						where = " WHERE "+states[0]+" = '"+valuesDict["state0Value"]+"' "    
					elif valuesDict["state0Condition"] =="ne":  
						where = " WHERE "+states[0]+" != '"+valuesDict["state0Value"]+"' "    
					elif valuesDict["state0Condition"] =="notNULL": 
						where = " WHERE "+states[0]+" IS NOT NULL "
					else:
						andWhere =""
						pass
					if andWhere !="": # only if state 1 is constrained too 
						if valuesDict["state1Condition"] != "any" and valuesDict["state1Condition"] != "" and valuesDict["state1Value"] != "":
							if valuesDict["state1Condition"] =="eq"  :      
								where += " AND "+states[1]+" = '"+valuesDict["state1Value"]+"' "    
							elif valuesDict["state1Condition"] =="ne":  
								where += " AND "+states[1]+" != '"+valuesDict["state1Value"]+"' "    
							elif valuesDict["state1Condition"] =="notNULL": 
								where += " AND "+states[1]+" IS NOT NULL "

			if id =="": # regular menue input
				if numberOfRecords !="noLimit":
					sqlCommandText+=  where + orderby+" LIMIT " + str(numberOfRecords)+" OFFSET (SELECT COUNT(*) FROM "+devOrVar+ idStr+where+")-"+numberOfRecords
				else:
					sqlCommandText+=  where + orderby
			else:  # action input will send and ID 
				if numberOfRecords !="noLimit":
					sqlCommandText+= where +  andWhere+ " ID > " +str(max(0,(int(id)-1)))+orderby +" LIMIT " + numberOfRecords
				else:
					sqlCommandText+= where +  andWhere+ " ID > " +str(max(0,(int(id)-1)))+orderby

			sqlCommandText+=";\""

			if self.ML.decideMyLog("SQL"): self.ML.myLog( text=sqlCommandText , mType="SQL command= " )
			extraMsg =""
			ret, err = self.readPopen(sqlCommandText)
			if err.find("is locked")>-1:
				if self.ML.decideMyLog("SQL"): self.ML.myLog( text="error in querry data base looked trying again" )
				self.sleep(0.5)
				ret, err = self.readPopen(sqlCommandText)
				if err.find("is locked")>-1:
					if self.ML.decideMyLog("SQL"): self.ML.myLog( text="error in querry data base looked trying again" )
					self.sleep(0.5)
					ret, err = self.readPopen(sqlCommandText)


			if len(err) > 1:
				valuesDict["msg"]="error in querry, check logfile"
				self.ML.myLog( text="error in querry:\n" +err , mType="OUTPUT: ", errorType="bigErr" )

			else:
				result=copy.copy(ret)
				fFile=False
				if separator!="" and states[0]!="*":## remove spaces before and after items and add headerline if requested
					if separator!="":
						lines=result.split("\n")
						result=""
						for line in lines:
							if len(line) < 5 or (line.find("rows)") >-1 and line.find("rows)") <10): continue# skip empty lines and (xxx rows) line at end of postgres
							items = line.split(separator)
							lineout=""
							for item in items:
								lineout+=item.strip()+separator
							result+=lineout.strip(separator)+"\n"

				
				if fixOutput:
					 
					lines=result.split("\n")
					result=""
					if separator!="": 
						sep = separator
						for line in lines:
							if len(line) < 5 or (line.find("rows)") >-1 and line.find("rows)") <10): continue# skip empty lines and (xxx rows) line at end of postgres
							items = line.split(sep)
							lineout=""
							del items[2]
							temp = items[1]
							items[1] = items[0]
							items[0] = temp
							for item in items:
								lineout+=item.strip()+sep
							result+=lineout+"\n"

					else:             
						if header =="yes":
							items = lines[1].split("  ")
							start = 0
							itemlength =[]
							itemstart  =[]
							for item in items:
								itemstart.append(start)
								itemlength.append(len(item)+2)
								start += len(item) +2
						
							for line in lines:
								if len(line) < 5 or (line.find("rows)") >-1 and line.find("rows)") <10): continue# skip empty lines and (xxx rows) line at end of postgres
								items =[]
								for nn in range(len(itemstart)):
									item = line[itemstart[nn]:itemstart[nn]+itemlength[nn]]
									items.append(item)
								del items[2]
								temp = items[1]
								items[1] = items[0]
								items[0] = temp
								lineout = ""
								for item in items:
									lineout+=item
								result += lineout+"\n"
						else:
							for line in lines:
								if len(line) < 5 or (line.find("rows)") >-1 and line.find("rows)") <10): continue# skip empty lines and (xxx rows) line at end of postgres
								result += line+"\n"
							extraMsg = "===== re-aranging columns does not work with seperator blank and no header  switch on header or use eg separator =;  ====\n" 
						
						


				if "printFile" in valuesDict:
					if valuesDict["printFile"] !="":
						if self.ML.decideMyLog("Logic"): self.ML.myLog( text="print to file '"+self.userIndigoPluginDir+ valuesDict["printFile"]+"'")
						fFile=True
						try:
							f=open(self.userIndigoPluginDir+valuesDict["printFile"],"w")
							f.write(result)
							if extraMsg !="":
								f.write(extraMsg+"\n")
							f.close()
							valuesDict["msg"]="check INDIGO logfile for output"
						except:
							valuesDict["msg"]="error in printing to file"+self.userIndigoPluginDir+valuesDict["printFile"]
							self.ML.myLog( text="error in printing to file  "+self.userIndigoPluginDir+valuesDict["printFile"], errorType="smallErr")

				if not fFile:
					valuesDict["msg"]="check INDIGO logfile for output"
					self.ML.myLog( text="\n" +result , mType="SQL-OUTPUT: " )
					if extraMsg !="":
						self.ML.myLog( text=extraMsg , mType="SQL-OUTPUT: " )


				lines = result.strip("\n").split("\n")
				error = True

				if len(str(id).strip(" ")) ==0:  ## put  last-1 record to variable
					try:
						nn= len(lines)-2
						if self.liteOrPsql !="sqlite" and header=="yes" and separator =="":	nn-=1
						nn = max(nn,0)
						if self.ML.decideMyLog("SQL"): self.ML.myLog( text=" last -1 record:   "+lines[nn])
						if separator=="":
							theSplit = lines[nn].split()
							if len(theSplit) >2:
								value1=theSplit[2]
							else:
								value1=  lines[nn] 
						else:
							theSplit = lines[nn].split(separator)
							if len(theSplit) >2:
								value1=thesplit[2]
							else:
								value1=  lines[nn] 
						indigo.variable.updateValue("SQLValueOutput",value1)
						indigo.variable.updateValue("SQLLineOutput",lines[nn])
						error = False
					except  Exception as e:
						self.exceptionHandler(40,e)
				else:							## put   record #id to variable
					nn=0
					if header =="yes": nn+=1
					if separator =="" and header =="yes": nn+=1
					if self.liteOrPsql !="sqlite":	nn+=1
					if len(lines) >nn+1:
						try:
							if self.ML.decideMyLog("SQL"): self.ML.myLog( text="record id# "+str(id)+"  "+lines[nn])
							if separator=="":
								value1 = lines[nn].split()[2]
							else:
								value1 = lines[nn].split(separator)[2]
							indigo.variable.updateValue("SQLValueOutput",value1)
							indigo.variable.updateValue("SQLLineOutput",lines[nn])
							error = False
						except  Exception as e:
							self.ML.myLog( text="printSQL error in  Line '%s' ;  error='%s'" % (sys.exc_info()[2].tb_lineno, e))

				if error:
					self.ML.myLog( text="printSQL error  sql output - no string returned for "+states[0]+"  number of lines returned: "+  str(len(lines)) +" \n"+out[0], errorType="smallErr")
					valuesDict["msg"]="printSQL error  sql output - no string returned for "+states[0]
	

		except  Exception as e:
				self.ML.myLog( text="printSQL error in  Line '%s' ;  error='%s'" % (sys.exc_info()[2].tb_lineno, e), errorType="smallErr")
		return valuesDict


####-----------------   create sql statement, execute it and print outpout to logfile          ---------
	def printnOfRecords(self):

		try:
			sqlitePGM	= "/usr/bin/sqlite3   '"+self.indigoPath+ "logs/indigo_history.sqlite'"
			postGrePGM	= self.postgresPasscode + self.liteOrPsqlString +" -t -c "
			if self.postgresUserId !="" and self.postgresUserId !="postgres": postGrePGM = postGrePGM.replace(" postgres "," "+self.postgresUserId+" ")

			if self.liteOrPsql =="sqlite":
				pgm	= sqlitePGM
			else:
				pgm	= postGrePGM
			devList=[]
			for dd in indigo.devices:
						id = dd.id
						name=dd.name
						sqlCommandText= pgm+ " \"SELECT COUNT(*) FROM device_history_"+str(id)+";\""
						if self.ML.decideMyLog("SQL"): self.ML.myLog( text=sqlCommandText , mType="SQL command= " )
						ret, err = self.readPopen(sqlCommandText)
						#self.ML.myLog( text=name+" "+ unicode(out))
						if err.find("is locked")>-1:
							if self.ML.decideMyLog("SQL"): self.ML.myLog( text="error in querry data base looked trying again" )
							self.sleep(0.5)
							ret, err = self.readPopen(sqlCommandText)
							if err.find("is locked")>-1:
								if self.ML.decideMyLog("SQL"): self.ML.myLog( text="error in querry data base looked trying again" )
								self.sleep(0.5)
								ret, err = self.readPopen(sqlCommandText)
						if len(err) >0:
								if self.ML.decideMyLog("SQL"): self.ML.myLog( text="error in querry data base: {}".format(err) )
						try:
							ii = int(ret.strip("\n"))
						except:
							ii=0
						devList.append([ii,str(id).rjust(12)+" / "+name])
			devList=sorted(devList)


			varList=[]
			for dd in indigo.variables:
						id = dd.id
						name=dd.name
						sqlCommandText= pgm+ " \"SELECT COUNT(*) FROM variable_history_"+str(id)+";\""
						if self.ML.decideMyLog("SQL"): self.ML.myLog( text=sqlCommandText , mType="SQL command= " )
						ret, err = self.readPopen(sqlCommandText)
						if err.find("is locked")>-1:
							if self.ML.decideMyLog("SQL"): self.ML.myLog( text="error in querry data base looked trying again" )
							self.sleep(0.5)
							ret, err = self.readPopen(sqlCommandText)
							if err.find("is locked")>-1:
								if self.ML.decideMyLog("SQL"): self.ML.myLog( text="error in querry data base looked trying again" )
								self.sleep(0.5)
								ret, err = self.readPopen(sqlCommandText)
						if len(err) >0:
								if self.ML.decideMyLog("SQL"): self.ML.myLog( text="error in querry data base: "+ unicode(out[1]) )
						
						try:
							ii = int(ret.strip("\n"))
						except:
							ii=0
						varList.append([ii,str(id).rjust(12)+" / "+name])
						## self.ML.myLog( text=(out[0].strip("\n")).rjust(15) +"  records in  "+name+"/"+str(id)+" "+out[1].strip("\n"))
			varList=sorted(varList)
			self.ML.myLog( text="   # of records        devId /  Name             for DEVICES")
			for dd in devList:
				self.ML.myLog( text=str(dd[0]).rjust(15)+" "+dd[1]  )
			self.ML.myLog( text="   # of records        varId /  Name             for VARIABLES")
			for dd in varList:
				self.ML.myLog( text=str(dd[0]).rjust(15)+" "+dd[1]  )

		except  Exception as e:
			self.exceptionHandler(40,e)
		return




	###########################	   cProfile stuff   ############################ START
	####-----------------  ---------
	def getcProfileVariable(self):

		try:
			if self.timeTrVarName in indigo.variables:
				xx = (indigo.variables[self.timeTrVarName].value).strip().lower().split("-")
				if len(xx) ==1: 
					cmd = xx[0]
					pri = ""
				elif len(xx) == 2:
					cmd = xx[0]
					pri = xx[1]
				else:
					cmd = "off"
					pri  = ""
				self.timeTrackWaitTime = 20
				return cmd, pri
		except	Exception as e:
			pass

		self.timeTrackWaitTime = 60
		return "off",""

	####-----------------            ---------
	def printcProfileStats(self,pri=""):
		try:
			if pri !="": pick = pri
			else:		 pick = 'cumtime'
			outFile		= self.userIndigoPluginDir+"timeStats"
			indigo.server.log(" print time track stats to: "+outFile+".dump / txt  with option: "+pick)
			self.pr.dump_stats(outFile+".dump")
			sys.stdout 	= open(outFile+".txt", "w")
			stats 		= pstats.Stats(outFile+".dump")
			stats.strip_dirs()
			stats.sort_stats(pick)
			stats.print_stats()
			sys.stdout = sys.__stdout__
		except: pass
		"""
		'calls'			call count
		'cumtime'		cumulative time
		'file'			file name
		'filename'		file name
		'module'		file name
		'pcalls'		primitive call count
		'line'			line number
		'name'			function name
		'nfl'			name/file/line
		'stdname'		standard name
		'time'			internal time
		"""

	####-----------------            ---------
	def checkcProfile(self):
		try: 
			if time.time() - self.lastTimegetcProfileVariable < self.timeTrackWaitTime: 
				return 
		except: 
			self.cProfileVariableLoaded = 0
			self.do_cProfile  			= "x"
			self.timeTrVarName 			= "enableTimeTracking_"+self.pluginName
			indigo.server.log("testing if variable "+self.timeTrVarName+" is == on/off/print-option to enable/end/print time tracking of all functions and methods (option:'',calls,cumtime,pcalls,time)")

		self.lastTimegetcProfileVariable = time.time()

		cmd, pri = self.getcProfileVariable()
		if self.do_cProfile != cmd:
			if cmd == "on": 
				if  self.cProfileVariableLoaded ==0:
					indigo.server.log("======>>>>   loading cProfile & pstats libs for time tracking;  starting w cProfile ")
					self.pr = cProfile.Profile()
					self.pr.enable()
					self.cProfileVariableLoaded = 2
				elif  self.cProfileVariableLoaded >1:
					self.quitNow = " restart due to change  ON  requested for print cProfile timers"
			elif cmd == "off" and self.cProfileVariableLoaded >0:
					self.pr.disable()
					self.quitNow = " restart due to  OFF  request for print cProfile timers "
		if cmd == "print"  and self.cProfileVariableLoaded >0:
				self.pr.disable()
				self.printcProfileStats(pri=pri)
				self.pr.enable()
				indigo.variable.updateValue(self.timeTrVarName,"done")

		self.do_cProfile = cmd
		return 

	####-----------------            ---------
	def checkcProfileEND(self):
		if self.do_cProfile in["on","print"] and self.cProfileVariableLoaded >0:
			self.printcProfileStats(pri="")
		return
	###########################	   cProfile stuff   ############################ END



####-----------------   main loop          ---------
	def runConcurrentThread(self):

		self.dorunConcurrentThread()
		self.checkcProfileEND()

		self.sleep(1)
		if self.quitNow !="":
			indigo.server.log( u"runConcurrentThread stopping plugin due to:  ::::: " + self.quitNow + " :::::")
			serverPlugin = indigo.server.getPlugin(self.pluginId)
			serverPlugin.restart(waitUntilDone=False)

		return

		
####-----------------   main loop          ---------
	def dorunConcurrentThread(self): 
		self.stopConcurrentCounter = 0
		self.ML.myLog( text="Utilities plugin initialized, ==> select  action from plugin menu" )
		nlines =0
		lastnlines=0
		if os.path.isfile(self.userIndigoPluginDir+"steps"):os.remove(self.userIndigoPluginDir+"steps")
		loopCounter=0
		self.taskList =""
		try:
			while self.quitNow =="":
				self.sleep(5)

				loopCounter+=1
				
				self.checkcProfile()
				
				self.checkPluginCPU()

				if self.taskList.find("makepluginDateList") > -1:
					self.makepluginDateList()
				
				if self.printNumberOfRecords ==1:
					self.printnOfRecords()
					self.printNumberOfRecords =0

				if self.postgresBackupStarted !=0:
					ret, err = self.readPopen("ps -ef | grep '/pg_dump ' | grep -v grep ")
					if len(ret)<5:
						self.ML.myLog( text=u" postgres backup dump  finished after " + str(int(time.time()-self.postgresBackupStarted))+"  seconds" )
						self.postgresBackupStarted =0

				if self.executeDatabaseSqueezeCommand != "":
					self.executeDatabaseSqueezeDoitNOW()

				##  print status of steps in sql python program
				if loopCounter %5 ==0:
					VS.versionCheck(self.pluginId,self.pluginVersion,indigo,14,50,printToLog="log")
					if os.path.isfile(self.userIndigoPluginDir+"steps"):
						ll= os.path.getsize(self.userIndigoPluginDir+"steps")
						if ll==0: continue
						ret, err = self.readPopen("cat '"+self.userIndigoPluginDir+"steps'")
						lines = steps.strip("\n").split("\n")
						nlines = len(lines)
						if nlines == lastnlines: continue
						for n in range(lastnlines, nlines):
							if self.ML.decideMyLog("SQL"): self.ML.myLog( text="SQL step: "+lines[n])
						lastnlines = nlines
	
				if self.cpuTempFreq !="": 
					self.cpuTempFanUpdate()
				## if backup started check if finished
				if self.backupStarted:
						ret, err = self.readPopen("ps -ef | grep 'Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' | grep -v grep ")
						if len(ret)>20: continue
						if not os.path.isfile(self.userIndigoPluginDir+"retcodes"): continue
						if os.path.getsize(self.userIndigoPluginDir+"retcodes") >1:
							self.ML.myLog( text="BACKUP of SQLite failed, check logfile: "+self.userIndigoPluginDir+"backup.log")
							self.triggerEvent(u"badBackup")
						else:
							if self.ML.decideMyLog("SQL"): self.ML.myLog( text="BACKUP files are: ")
							if os.path.isfile(self.indigoPath+"logs/indigo_history-1.sqlite"):
								if self.ML.decideMyLog("SQL"): self.ML.myLog( text=self.indigoPath+"logs/indigo_history-1.sqlite")
								if os.path.isfile(self.indigoPath+"logs/indigo_history-2.sqlite"):
									if self.ML.decideMyLog("SQL"): self.ML.myLog( text=self.indigoPath+"logs/indigo_history-2.sqlite")
									if os.path.isfile(self.indigoPath+"logs/indigo_history-3.sqlite"):
										if self.ML.decideMyLog("SQL"): self.ML.myLog( text=self.indigoPath+"logs/indigo_history-3.sqlite")
										if os.path.isfile(self.indigoPath+"logs/indigo_history-4.sqlite"):
											if self.ML.decideMyLog("SQL"): self.ML.myLog( text=self.indigoPath+"logs/indigo_history-4.sqlite")
								self.ML.myLog( text="backup of SQLite finished at "+ str(datetime.datetime.now()))
							else:
								self.ML.myLog( text="BACKUP of SQLite failed, check logfile: "+self.userIndigoPluginDir+"backup.log  SQLITE file  "+self.indigoPath+"logs/indigo_history-1.sqlite   not created")
								self.triggerEvent(u"badBackup")
				
						self.backupStarted = False
						if os.path.isfile(self.userIndigoPluginDir+"steps"):os.remove(self.userIndigoPluginDir+"steps")


				## if FIX SQL  started check if finished
				if self.fixSQLStarted >0:

					if self.fixSQLStarted ==99: #  request to cancel
						self.fixSQLStarted = 0
						pids, err = self.readPopen("ps -ef | grep 'Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' | grep -v grep ")
						if len(pids) >20:
							pid = pids.split()
							if len(pid)> 2 and int(pid[1]) >100:
								ret, err = self.readPopen("kill -9 "+str(pid[1]))
								if len(err) >0:
									self.ML.myLog( text="FIX of SQLite cancel reqquest job failed")
									continue
								self.ML.myLog( text="FIX of SQLite cancel request done")
						else:      
							self.ML.myLog( text="FIX of SQLite cancel request: job is already gone")
						continue
								
					ret, err = self.readPopen("ps -ef | grep 'Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' | grep -v grep ")
					if len(ret)>20: 
						if loopCounter %50 ==0:
							self.ML.myLog( text="FIX of SQLite still running, check ~/indigo/Utilities/backup.log/  for detailed info")
						self.fixSQLStarted =2
						continue
					if self.fixSQLStarted ==1: #  request to start job 
						ret, err = self.readPopen("ps -ef | grep 'SQL Logger.indigoPlugin' | grep -v grep ")
						if len(ret)>20: 
							self.ML.myLog( text="FIX SQL not started, please shutdown sql logger first")
							continue                    
						self.executeSQL([],0,0,"fix")
						self.ML.myLog( text="FIX SQL job submitted, check ~/indigo/Utilities/backup.log/  for detailed info, this might take a long time (~ 1 hour for 8GByte on Mac-Mini 2014)")
						self.fixSQLStarted =2
						continue

					if not os.path.isfile(self.userIndigoPluginDir+"retcodes"): continue
					if os.path.getsize(self.userIndigoPluginDir+"retcodes") >1:
						self.ML.myLog( text="FIX of SQLite failed, check logfile: "+self.userIndigoPluginDir+"backup.log")
						self.fixSQLStarted = 0
					else:
						if os.path.isfile(self.indigoPath+"logs/indigo_history-fixed.sqlite"):
							self.ML.myLog( text="FIX of SQLite finished successfully, fixed file is : "+self.indigoPath+"logs/indigo_history-fixed.sqlite")
							self.ML.myLog( text=" to use fixed database:")
							self.ML.myLog( text="  -- make sure sqllogger is disabled")
							self.ML.myLog( text="  -- rename indigo_history.sqlite file to eg indigo_history.backup")
							self.ML.myLog( text="  -- rename indigo_history-fixed.sqlite to indigo_history.sqlite")
							self.ML.myLog( text="  -- re-start SQLlogger")
							self.ML.myLog( text=" if it does not work, stop sqllogger, delte indigo_history.sqlite and rename  indigo_history.backup to indigo_history.sqlite, re-start SQLlogger")
						else:
							self.ML.myLog( text="FIX of SQLite failed, check logfile: "+self.userIndigoPluginDir+"backup.log  .. "+  self.indigoPath+"logs/indigo_history-fixed.sqlite file not created")
					self.ML.myLog( text="FIX of SQLite finished at "+ str(datetime.datetime.now()))
					self.fixSQLStarted = 0
					if os.path.isfile(self.userIndigoPluginDir+"steps"):os.remove(self.userIndigoPluginDir+"steps")


			self.stopConcurrentCounter = 1
		except  Exception as e:
			self.exceptionHandler(40,e)
		return

####----------------- trigger stuff for bad backup  ---------

	######################################################################################
	# Indigo Trigger Start/Stop
	######################################################################################

	def triggerStartProcessing(self, trigger):
	#		self.myLog(4,u"<<-- entering triggerStartProcessing: %s (%d)" % (trigger.name, trigger.id) )iDeviceHomeDistance
		self.triggerList.append(trigger.id)
	#		self.myLog(4,u"exiting triggerStartProcessing -->>")

	def triggerStopProcessing(self, trigger):
	#		self.myLog(4,u"<<-- entering triggerStopProcessing: %s (%d)" % (trigger.name, trigger.id))
		if trigger.id in self.triggerList:
	#			self.myLog(4,u"TRIGGER FOUND")
			self.triggerList.remove(trigger.id)
	#		self.myLog(4, u"exiting triggerStopProcessing -->>")

	#def triggerUpdated(self, origDev, newDev):
	#	self.logger.log(4, u"<<-- entering triggerUpdated: %s" % origDev.name)
	#	self.triggerStopProcessing(origDev)
	#	self.triggerStartProcessing(newDev)


	######################################################################################
	# Indigo Trigger Firing
	######################################################################################

	def triggerEvent(self, eventId):
		#self.myLog(4,u"<<-- entering triggerEvent: %s " % eventId)
		for trigId in self.triggerList:
			#self.myLog(4,u"<<-- trigId: %s " % trigId)
			trigger = indigo.triggers[trigId]
			if trigId == eventId:
				indigo.trigger.execute(trigger)
		return

	######################################################################################
	#amc cpu temp and fan speeds 
	######################################################################################
	def cpuTempFanUpdate(self):

		try:
			if self.cpuTempFreq == "" or self.cpuTempFreq == "0": return
			if time.time() - self.lastcpuTemp < float(self.cpuTempFreq): return
			self.lastcpuTemp  = time.time()
		
			ret, err = self.readPopen("'"+self.pathToPlugin+"osx-temp-fan'")
			#self.ML.myLog( text=" data fan:"+unicode(data) )
			data = ret.strip("\n").split("\n")
			for line in data:
				ll = line.split(":")
				if len(ll) < 2: continue
				if  ll[0].find("temp") > -1:
					t = float(ll[1])
					if t < 0: continue
					if self.cpuTempUnit == "F": 
						t = t*9./5 +32
					try:      indigo.variables[ll[0]]
					except:   indigo.variable.create(ll[0])
					indigo.variable.updateValue(ll[0], self.cpuTempFormat%t)
				else:
					try:      indigo.variables[ll[0]]
					except:   indigo.variable.create(ll[0])
					indigo.variable.updateValue(ll[0], ll[1])

		except  Exception as e:
			self.exceptionHandler(40,e)


	#################################
	def writeJson(self, fName, data, sort_keys=False, indent=0):
		try:
			if indent != 0:
				out = json.dumps(data,sort_keys=sort_keys, indent=indent)
			else:
				out = json.dumps(data,sort_keys=sort_keys)
			#logger.log(10, u" writeJson-in:{}\nout: {}".format(data, out) )
		##print "writing json to "+fName, out
			f=open(fName,"w")
			f.write(out)
			f.close()
		except	Exception as e:
			self.exceptionHandler(40,e)
		return


	#################################
	def readJson(self, fName):
		data ={}
		raw = ""
		try:
			if not os.path.isfile(fName):
				indigo.server.log( u"no fname:{}".format(fName))
				return {},""
			f=open(fName,"r")
			raw = f.read()
			f.close()
			data = json.loads(raw)
		except	Exception as e:
			self.exceptionHandler(40,e)
			indigo.server.log(u"fname:{}, data:{}".format(fName, raw ))
			return {}, ""
		return data, raw

	####-----------------	 ---------
	def completePath(self,inPath):
		if len(inPath) == 0: return ""
		if inPath == " ":	 return ""
		if inPath[-1] !="/": inPath +="/"



####-------------------------------------------------------------------------####
	def readPopen(self, cmd):
		try:
			ret, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
			return ret.decode('utf_8'), err.decode('utf_8')
		except Exception as e:
			self.exceptionHandler(40,e)

####-----------------  exception logging ---------
	def exceptionHandler(self, level, exception_error_message):

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
				self.errorLog(log_message)
			return "'{}'".format(log_message )
		except Exception as e:
			indigo.server.log( "{}".format(e))




