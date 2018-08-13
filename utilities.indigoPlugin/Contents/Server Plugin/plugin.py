#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# show sql data in logfile  Plugin
# Developed by Karl Wachs
# karlwachs@me.com

import os, sys, subprocess, pwd, copy, datetime, time
import plistlib
import versionCheck.versionCheck as VS


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
        self.indigoPath = self.pathToPlugin[:p]
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

        self.userName = pwd.getpwuid( os.getuid() )[ 0 ]
        self.debugLevel			= int(self.pluginPrefs.get(	"debugLevel",		255))
        self.liteOrPsql			= self.pluginPrefs.get(		"liteOrPsql",		"sqlite")
        self.liteOrPsqlString	= self.pluginPrefs.get(		"liteOrPsqlString",	"/Library/PostgreSQL/bin/psql indigo_history postgres ")
        self.orderByID			= self.pluginPrefs.get(		"orderByID",	"no")
        self.noOfBackupCopies	= self.pluginPrefs.get(		"noOfBackupCopies",	"2")
        self.maxSQLlength       = self.pluginPrefs.get(		"maxSQLlength",	"200000")
        self.devID 				= 0
        self.varID 				= 0
        self.quitNow			= "" # set to !="" when plugin should exit ie to restart, needed for subscription -> loop model
        self.printNumberOfRecords =0
        self.pythonPath="/usr/bin/python2.6"
        if   os.path.isfile("/usr/bin/python2.7"): self.pythonPath="/usr/bin/python2.7"
        elif os.path.isfile("/usr/bin/python2.6"): self.pythonPath="/usr/bin/python2.6"
        elif os.path.isfile("/usr/bin/python2.5"): self.pythonPath="/usr/bin/python2.5"

        self.fixSQLStarted=False
        self.fixSQLSteps=0
        self.backupStarted=False
        self.backupSteps=""
        self.triggerList=[]
        self.executeDatabaseSqueezeCommand = ""
        self.postgresBackupStarted =0
        self.lastVersionCheck = -1

        self.cpuTempFreq   = self.pluginPrefs.get(		"cpuTempFreq",	"0")
        self.cpuTempUnit   = self.pluginPrefs.get(		"cpuTempUnit",	"0")
        self.cpuTempFormat = self.pluginPrefs.get(		"cpuTempFormat",	"%.1f")
        self.lastcpuTemp   = 0

        
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


        home = os.path.expanduser("~")
        self.indigoUtilities = home + "/indigo/indigoUtilities/"

        if not os.path.exists(home + "/indigo/"):
            os.mkdir(home + "/indigo/")

        if not os.path.exists(self.indigoUtilities):
            os.mkdir(self.indigoUtilities)

        try:
            self.printDeviceStatesDictLast= self.pluginPrefs["printDeviceStates"]
        except:
            self.printDeviceStatesDictLast=indigo.Dict()



        self.myLog(255,u"initialized")
    
        return



    ########################################
    def deviceStartComm(self, dev):
        return
    
    ########################################
    def deviceStopComm(self, dev):
        return
    ########################################
    #def stopConcurrentThread(self):
    #    self.myLog(255,u"stopConcurrentThread called " + str(self.stopConcurrentCounter))
    #    self.stopConcurrentCounter +=1
    #    if self.stopConcurrentCounter ==1:
    #        self.stopThread = True




####-----------------  set the geneeral config parameters---------
    def validatePrefsConfigUi(self, valuesDict):

        self.debugLevel			= int(valuesDict[u"debugLevel"])
        self.liteOrPsql			= valuesDict["liteOrPsql"]
        self.liteOrPsqlString	= valuesDict["liteOrPsqlString"]
        self.orderByID			= valuesDict["orderByID"]
        self.noOfBackupCopies	= valuesDict["noOfBackupCopies"]
        try:
            self.maxSQLlength = str(int(valuesDict["maxSQLlength"]))
        except:    
            valuesDict["maxSQLlength"] = 200000
            self.maxSQLlength = 200000
            
        self.cpuTempFreq   = valuesDict["cpuTempFreq"]
        self.cpuTempUnit   = valuesDict["cpuTempUnit"]
        self.cpuTempFormat = valuesDict["cpuTempFormat"]
        
        return True, valuesDict

#	def		(self):
#		self.myLog(255,u"getPrefsConfigUiValues called " )


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
        xx = subprocess.Popen("/usr/sbin/lsof ",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0].strip("\n").split("\n")
        fileList ={}
        for m in xx:
            mm = m.split()
            try: int(mm[1])
            except: continue
            if len(mm) ==9:
                if mm[1] not in fileList: fileList[mm[1]] =[]
                if len(mm[8]) > 5:      ### exclude std files 
                    if mm[8].find("/Python.framework/") >-1:    continue
                    if mm[8].find("/CoreServices/") >-1:        continue
                    if mm[8].find("/com.apple.") >-1:           continue
                    if mm[8].find("/usr/lib/") >-1:             continue
                    if mm[8].find("/usr/share/") >-1:           continue
                    if mm[8].find("/private/var/db/") >-1:      continue
                    if mm[8].find("/dev/null") >-1:             continue
                    if mm[8].find("/dev/urandom") >-1:          continue
                    fileList[mm[1]].append(mm[8]) # file name
    
        return  fileList


    def getActivePlugins(self):

        plugList= []
        ret = subprocess.Popen("/bin/ps -ef | grep 'MacOS/IndigoPluginHost' | grep -v grep",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0]
        lines = ret.strip("\n").split("\n")
        version =" "
        for line in lines:
            #indigo.server.log(line)
            if len(line) < 40: continue
            items = line.split()
            if len(items) < 7: continue
            if line.find("indigoPlugin") ==-1: continue
            #self.myLog(-1,unicode(items))
            pCPU  = items[6]
            pID   = items[1]
            items = line.split(" -f")
            pName = items[1].split(".indigoPlugin")[0]
            try:
                plugId  = plistlib.readPlist(self.indigoPath+"Plugins/"+pName+".indigoPlugin/Contents/Info.plist")["CFBundleIdentifier"]
                version = plistlib.readPlist(self.indigoPath+"Plugins/"+pName+".indigoPlugin/Contents/Info.plist")["PluginVersion"]
            except  Exception, e:
                    self.myLog(-1," print plugin name  error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
                    version = " "
                    plugId  = " "
            plugList.append((pName,pCPU,pID,version,plugId))
                
        return plugList





####-----------------  print device / variable states .. ---------
    def printMACtemperaturesAction(self, action,typeId="",devId=""):
        self.printMACtemperatures()
        
####-----------------  print device / variable states .. ---------
    def printMACtemperatures(self):
        out ="\nTemperatures and fan speeds of indigo MAC \n"
        ll  = subprocess.Popen("'"+self.pathToPlugin+"osx-temp-fan'",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0].strip("\n")
        for line in ll.split("\n"):
            if line.find("-99") >-1: continue
            items = line.split(":")
            if len(items) !=2:       continue
            if items[0].find("fan") >-1: 
                val = items[1].split(".")[0]+"[r/m]" # only integer part
            else:                        
                val = items[1]+"[ºC]"
            out += (items[0]+":").ljust(30)+ val +"\n"
        indigo.server.log(out)
        return
        

####-----------------  print device / variable states .. ---------
    def printPluginidNamestoLogfileAction(self, action,typeId="",devId=""):
        self.printPluginidNamestoLogfile()
        
####-----------------  print device / variable states .. ---------
    def printPluginidNamestoLogfile(self):

        indigo.server.log("starting print plugin names, id, mem cpu  daughter proceesses . . . takes a little time")
        mem = subprocess.Popen("/bin/ps aux",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0].strip("\n").split("\n")
        memList ={}
        for m in mem:
            mm = m.split()
            try: int(mm[4])
            except: continue
            memList[mm[1]]= [mm[3],str(int(mm[4])/1024),str(int(mm[5])/1024)] # %mem,virt mem, real mem in MB

        fileList = self.getOpenFiles()
        plugList = self.getActivePlugins()
        
        out=["\n     ID    CPU-total  Mem-% -Virt -Real  version       pluginName ------------------------  .. + sub processes and non std open files \n"]
        for item in  plugList:
            try:
                pName   = item[0]
                pCPU    = item[1]
                pID     = item[2]
                version = item[3]
                if pID in memList:    mem = memList[pID][0].rjust(6)+memList[pID][1].rjust(6)+memList[pID][2].rjust(6)
                else:                 mem = " ".rjust(18)
                out.append(pID.rjust(7)+"  "+pCPU.rjust(11)+" "+mem+"  "+version.ljust(10)+"   "+ pName +"\n")
                ret2 = subprocess.Popen("/bin/ps -ef | grep ' "+pID+" ' | grep -v grep ",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0]
                lines2 = ret2.split("\n")
                #self.myLog(-1, unicode(lines) )s
                for line2 in lines2:
                    items2 = line2.split()
                    if len(items2) < 7: continue
                    if items2[1] == pID: continue
                    dPID = items2[1]
                    dCPU = items2[6]
                    d=""
                    for ii in range(7,len(items2)):
                        d +=  items2[ii]+" "
                    if len(d) < 5: continue
                    doughterProcess= "             SubProcess: "+d.replace("/Library/Application Support/Perceptive Automation/Indigo"," ...")
                    if pID in memList:    mem = memList[pID][0].rjust(6)+memList[pID][1].rjust(6)+memList[pID][2].rjust(6)
                    else:                 mem = " ".rjust(18)
                    out.append( dPID.rjust(7)+"  "+dCPU.rjust(11)+" "+mem+"   "+ doughterProcess+"\n")
                if pID in fileList and len(fileList[pID]) > 0:
                    for ff in fileList[pID]:
                        out.append(" ".ljust(7+2+11+1+19+2)+"             openFile:   "+ff+"\n")                
            except  Exception, e:
                self.myLog(-1," print plugin name  error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
        indigo.server.log("".join(out))



    def makepluginDateList(self):

            self.taskList =""
            plugList = self.getActivePlugins()
            tDay = datetime.datetime.now().day
            if self.lastVersionCheck == tDay:
                self.myLog(255,"plugin version check already ran today, try again tomorrow")
                return
            self.lastVersionCheck = tDay

            self.myLog(255,"Plugin name -------------------    installed Version   StoreVers ")
            for item in plugList:
                pName     = item[0]
                exVersion = item[3]
                plugId    = item[4]
                version =   VS.versionCheck(plugId,"0.0.0",indigo,0,0, printToLog="no",force =True)
                self.myLog(255,pName.ljust(35)+str(exVersion).ljust(20)+str(version))
                time.sleep(1.5)
            self.myLog(255,"Plugin name -------------------    END")


####-----------------  print device / variable states .. ---------
    def inpPrintTriggers(self):


        triggers={}
        for trig in indigo.triggers:
            #self.myLog(255,"tr id "+ unicode(trig.id))
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

        f=open(self.indigoUtilities+"zWave.dot","w")
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
        indigo.server.log(    u"Created graphviz input file:   \""+self.indigoUtilities+"zWave.dot\"")
        
        if os.path.isfile("/usr/local/bin/dot"):
            ret=subprocess.Popen("/usr/local/bin/dot -Tsvg "+self.indigoUtilities+"zWave.dot > "+self.indigoUtilities+"zWave.svg ",shell=True).communicate()
            indigo.server.log(u"Created graphviz outpout file: \""+self.indigoUtilities+"zWave.svg\"")

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
        cmd="cp -R  '"+self.indigoPath+"databases' '" +self.indigoUtilities+"'"
        self.myLog(1,u" indigo backup: " + cmd)
        subprocess.Popen(cmd, shell=True)
        cmd="cp -R  '"+self.indigoPath+"Preferences' '" +self.indigoUtilities+"'"
        self.myLog(1,u" indigo backup: " + cmd)
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
        if len(subprocess.Popen("ps -ef | grep '/pg_dump ' | grep -v grep ", stdout = subprocess.PIPE, shell = True).communicate()[0])>20:
            self.myLog(255,u"previous postgres backup dump  job still running, please wait until finished ")
            return 

        ## move last dump  to dump-1 file
        if os.path.isfile(self.indigoUtilities+"postgresBackup.zip-1"):
            os.remove(self.indigoUtilities+"postgresBackup.zip-1")
        if os.path.isfile(self.indigoUtilities+"postgresBackup.zip"):
            os.system("mv "+self.indigoUtilities+"postgresBackup.zip  "+self.indigoUtilities+"postgresBackup.zip-1")
            
        commandLineForDump = self.liteOrPsqlString.replace("psql","pg_dump")
        
        # add zip, doing dump and zip together eats too much CPU, need to do it in 2 steps , then remove temp file  ( dump && gzip && rm ... )
        cmd= commandLineForDump+"  > "+  self.indigoUtilities+"postgresBackup.dmp  &&  gzip "+ self.indigoUtilities+"postgresBackup.dmp  > " + self.indigoUtilities+"postgresBackup.zip  &&  rm "+ self.indigoUtilities+"postgresBackup.dmp  &"
        self.myLog(255,cmd)
        ret= subprocess.Popen(cmd, shell=True)
        self.myLog(255,'to restore: 1. in pgadmin: "DROP DATABASE indigo_history;"   "CREATE DATABASE indigo_history template = template0;"  2.unzip postgresBackup.zip ; 3. "pathtopostgresapp/psql indigo_history -U postgres < postgresBackup"' )
        self.postgresBackupStarted = time.time() 

             
        return valuesDict

####-----------------  ---------
    def executeSQL(self, valuesDict,typeId,devId,mode):
        if len(subprocess.Popen("ps -ef | grep 'Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' | grep -v grep ", stdout = subprocess.PIPE, shell = True).communicate()[0])>20:
            self.myLog(255,u"previous SQLite job still running, please wait until finished ")
            return (valuesDict, u"previous SQLite job still running, please wait until finished ")

        try:
            os.remove(self.indigoUtilities+"steps")
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
        self.myLog(255,u"starting SQLite job "+cmd )
        self.myLog(255,u"...                       started  at "+ str(datetime.datetime.now()) )
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



####-----------------   for menue aded --- lines          ---------
    def dummyCALLBACK(self):
        
        return

####-----------------   get number of records for each device / variable and print to logfile          ---------
        ## this needs to be done in batch as it might take some time
    def executePrintNumberOfRecords(self,valuesDict="",typeId="",devId=""):
        self.printNumberOfRecords =1
        self.myLog(255,"started print # of records for devices and variables ")
        return
####-----------------   devOrVarCALLBACK          ---------
    def devOrVarCALLBACKAction(self,action1,typeId="",devId=""):
        self.devOrVarCALLBACK(action1)
        return

####-----------------   devOrVarCALLBACK          ---------
    def devOrVarCALLBACK(self,valuesDict="",typeId=""):
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
        self.myLog(1,unicode(valuesDict))
        self.devID= int(valuesDict["device"])
        self.varID= 0
        valuesDict["msg"]="select states for device selected"
        
        return valuesDict
####-----------------   pickVariableCALLBACK          ---------
    def pickVariableCALLBACKAction(self,action1="",typeId="",devId=""):
        self.pickVariableCALLBACK(action1)
        return

####-----------------   pickVariableCALLBACK          ---------
    def pickVariableCALLBACK(self,valuesDict="",typeId=""):
        self.varID= int(valuesDict["variable"])
        self.devID= 0
        valuesDict["msg"]=""
        
        return valuesDict

####-----------------   ipnumberOfDeviceCallback          ---------
    def ipnumberOfDeviceCallback(self,valuesDict="",typeId=""):
        ipNumber= valuesDict["ipDevice"]
        indigo.server.log("\nping result for /sbin/ping -c 2 -W 2  "+ipNumber+"    -------------- START")
        ret = subprocess.Popen("/sbin/ping -c 2 -W 2  "+ipNumber,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
        indigo.server.log("\n"+ret[0],type=" ")
        if len(ret[1]) >2: indigo.server.log("ping error:"+ ret[1],type=" ")
        indigo.server.log("ping           ------------------ END",type=" ")
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
                self.myLog(255,"pruneDevsandVarsaction error  deleteBeforeThisDays missing ")
                return
            if "devOrVar" not in valuesDict:     
                self.myLog(255,"pruneDevsandVarsaction error  devOrVar missing ")
                return
            if valuesDict["devOrVar"] =="var" and  "variable" not in valuesDict:       
                self.myLog(255,"pruneDevsandVarsaction error  variable missing ")
                return
            if  valuesDict["devOrVar"] =="dev" and "device" not in valuesDict:       
                self.myLog(255,"pruneDevsandVarsaction error  device missing ")
                return

            if  valuesDict["devOrVar"] =="var":
                try:
                    id =    indigo.variables[int(valuesDict["variable"])]
                except:
                    try:
                        id =    indigo.variables[valuesDict["variable"]].id
                        valuesDict["variable"] = str(id)
                    except:
                        self.myLog(255,"pruneDevsandVarsaction  variable "+valuesDict["variable"]+ " does not exist")
                        return  

            if  valuesDict["devOrVar"] =="dev":
                try:
                    id =    indigo.variables[int(valuesDict["device"])]
                except:
                    try:
                        id =    indigo.devices[valuesDict["device"]].id
                        valuesDict["device"] = str(id)
                    except:
                        self.myLog(255,"pruneDevsandVarsaction  device "+valuesDict["device"]+ " does not exist")
                        return    

            self.myLog(1,"pruneDevsandVarsaction  "+unicode(valuesDict))
            self.executePruneDatabase(valuesDict,test=False)
        
        except Exception, e:
                self.myLog(-1, "executePruneDatabase error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e) )



####-----------------   collect all info and call print         ---------
    def executePruneDatabaseTEST(self,valuesDict="",typeId="",devId=""):
        self.executePruneDatabase(valuesDict,test=True)
        
####-----------------   collect all info and call print         ---------
    def executePruneDatabase(self,valuesDict="",typeId="",devId="",test=False):
        
        if test: loglevel=255
        else:    loglevel=2
        
        try:
            devOrVar         = valuesDict["devOrVar"]
            if devOrVar =="var":
                table         = "variable_history_"+valuesDict["variable"]
                name= indigo.variables[int(valuesDict["variable"])].name
            else:   
                table         = "device_history_"+valuesDict["device"]
                name= indigo.devices[int(valuesDict["device"])].name
            deleteBeforeThisDays = int(valuesDict["deleteBeforeThisDays"])
            nowTS =datetime.datetime.now() 
            dateCutOff = (nowTS-datetime.timedelta(deleteBeforeThisDays,hours=nowTS.hour,minutes=nowTS.minute,seconds=nowTS.second)).strftime("%Y%m%d%H%M%S")
            self.myLog(loglevel, "prune records for device / var = "+ name +" before "+ dateCutOff)
            
            orderby = ""
            if self.orderByID =="yes":
                orderby = " ORDER by id "

            
            if self.liteOrPsql =="sqlite":
                if len(subprocess.Popen("/bin/ps -ef | grep sqlite3 | grep -v grep ",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0]) > 10:
                    self.myLog(255, "SQLITE3 is still running please stop before using prune database")
                    return
                    
            if self.liteOrPsql =="sqlite": 
                cmd=    "/usr/bin/sqlite3  -separator \" \" '"+self.indigoPath+ "logs/indigo_history.sqlite' \"SELECT id,strftime('%Y%m%D%H%M%S',ts,'localtime') FROM "+table+orderby+";\"\n"
            else:    
                cmd= self.liteOrPsqlString+ " -t -A -F ' ' -c \"SELECT id, to_char(ts,'YYYYmmddHH24MIss') FROM "+table+orderby+";\"\n"

            #self.myLog(255,cmd)
            ret= subprocess.Popen(cmd, shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
            #self.myLog(255,"ret"+  ret[0][0:200]+"-\n"+ret[1])
            lines = ret[0].split("\n")
            
            firstIDtoKeep          = 0
            nn                     = 0
            timeWOmsec             = ""
            for line in lines:
                nn+=1
                #if nn < 100: self.myLog(255,"line# "+ str(nn)+"  "+ line)
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
                except  Exception, e:#
                     self.myLog(255, "executePruneDatabase error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e) )
                   
            self.myLog(loglevel, "first record found that is above cut off at "+ timeWOmsec+"; id: "+ str(firstIDtoKeep)+"; that is the "+str(nn) +"th record out of " +str(len(lines))+ " total records" )
            if self.liteOrPsql =="sqlite": 
                    sqlDeleteCommands=    "/usr/bin/sqlite3 '"+self.indigoPath+ "logs/indigo_history.sqlite' "
            else:    
                    sqlDeleteCommands= self.liteOrPsqlString+ "  -c "
                    
            sqlDeleteCommands+="\"DELETE FROM "+table+ " WHERE id < " +str(firstIDtoKeep)+";\""
            self.myLog(loglevel, "cmd= "+ sqlDeleteCommands)
            if not test: 
                ret= subprocess.Popen(sqlDeleteCommands, shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                self.myLog(2, "SQL returned: "+ ret[0]+"-"+ret[1])

        except Exception, e:
                self.myLog(-1, "executePruneDatabase error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e) )


####-----------------   squeeze postgres database         ---------
    def actionDatabaseSqueeze(self,valuesDict="",typeId="",devId=""):
        if self.executeDatabaseSqueezeCommand.find("EXECUTING") >-1:
            self.myLog(255, "delete duplicate SQL records still running, please wait until finished")
            return 
        self.executeDatabaseSqueeze({"execOrTest":"exec"},typeId="",devId="")

####-----------------   squeeze postgres database         ---------
    def actionDatabaseSqueezeQuiet(self,valuesDict="",typeId="",devId=""):
        if self.executeDatabaseSqueezeCommand.find("EXECUTING") >-1:
            self.myLog(255, "delete duplicate SQL records still running, please wait until finished")
            return 
        self.executeDatabaseSqueeze({"execOrTest":"execquiet"},typeId="",devId="")

####-----------------   squeeze postgres database         ---------
    def executeDatabaseSqueeze(self,valuesDict="",typeId="",devId=""):
        if  valuesDict["execOrTest"] =="stop":
            self.executeDatabaseSqueezeCommand = "stop"
            self.myLog(255, "delete duplicate SQL records stop requested, finishing current table")
            return
        if self.executeDatabaseSqueezeCommand.find("EXECUTING") >-1:
            self.myLog(255, "delete duplicate SQL records still running, please wait until finished")
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
            if len(subprocess.Popen("/bin/ps -ef | grep sqlite3 | grep -v grep ",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0]) > 10:
                self.myLog(255, "SQLITE3 is still running please stop before using delete duplicate records")
                self.executeDatabaseSqueezeCommand =""
                return

        self.executeDatabaseSqueezeCommand = "EXECUTING"


        if execOrTest == "test": 
            gg=open(self.indigoUtilities+"squeezeSQLall","w")
            
            
        
        self.myLog(255, "Starting to squeeze / delete records with same time stamp from data base, keep only last of each these record ... this can take SEVERAL minutes ..\n SQL  command in:  "+self.indigoUtilities+ "squeezeSQL(all)")
        nAllIn =0
        nAllDelete = 0
        devTables=[]
        for dd in indigo.devices:
            devTables.append(["device_history_" +str(dd.id),dd.name])
        nDEVS = len(devTables)
        nnn=0
        ndevsWdelete = 0
        if execOrTest == "exec": 
            self.myLog(255,"del-act/del-pot/totalRECS; SQL ==================----------............" ,type="#  Device Name " )
            
        for xx in devTables:
            if self.executeDatabaseSqueezeCommand.find("stop") >-1:
                self.myLog(255,"HARD stop requested" )
                self.executeDatabaseSqueezeCommand = ""
                break
            table   = xx[0] 
            name    = xx[1]
            #self.myLog(255," getting duplicate records " +name ,type="#  Device Name " )
            nnn+=1
            try:
                if self.liteOrPsql =="sqlite": 
                    cmd=    "/usr/bin/sqlite3  -separator \" \" '"+self.indigoPath+ "logs/indigo_history.sqlite' \"SELECT id,strftime('%H:%M:%S',ts,'localtime') FROM "+table+";\"\n"
                else:    
                    cmd= self.liteOrPsqlString+ " -t -A -F ' ' -c \"SELECT id, to_char(ts,'HH24:MI:ss') FROM "+table+";\"\n"
                #self.myLog(255,cmd)
                ret= subprocess.Popen(cmd, shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                lines = ret.communicate()[0].split("\n")
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
                                #self.myLog(255, line)
                                nDelete+=1
                        else:   
                            lasttimeWOmsec = timeWOmsec
                        lastId=id    
                    except  Exception, e:
                         self.myLog(-1, "executeDatabaseSqueeze error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e) )
                         
                if  nDelete == 0: continue

                if self.liteOrPsql =="sqlite": 
                    sqlDeleteCommands=    "/usr/bin/sqlite3 '"+self.indigoPath+ "logs/indigo_history.sqlite' "
                else:    
                    sqlDeleteCommands= self.liteOrPsqlString+ "  -c "
                sqlDeleteCommands+="\"DELETE FROM "+table+ " WHERE id IN ( " 
                iDstart = 0
                #if os.path.isfile(self.indigoUtilities+"steps"):
                #    os.remove(self.indigoUtilities+"squeezeSQL")  
                    
                while True:
                    if iDstart >= len(idsToDelete): break
                    idString=""
                    nIDs =0
                    for id in idsToDelete[iDstart:]:
                        if len(idString) > int(self.maxSQLlength)-300: 
                            self.myLog(255, table +" more than "+str(self.maxSQLlength)+" bytes in sql string, stopping at "+str(self.maxSQLlength),type=str(nnn)+"-"+name)
                            break
                        nIDs+=1
                        idString += id+ ","
                        
                    iDstart += nIDs    
                    cmd = sqlDeleteCommands +   idString.strip(",")+");\""
                
                    if execOrTest =="test":  
                        gg.write(cmd+"\n")
                        
                    elif execOrTest =="exec":  
                        self.myLog(255,str(nIDs).rjust(7)+"/"+str(nDelete).rjust(7)+ "/" + str(nIn).ljust(9)+"; "+cmd[0:min(len(cmd),170)]+ "..)\"; ",type=str(nnn)+"-"+name )

                    if execOrTest.find("exec")>-1:
                        f=open(self.indigoUtilities+"squeezeSQL","w")  
                        f.write(cmd+"\n")
                        f.close()
                        ret=subprocess.Popen("chmod +xxx "+ self.indigoUtilities+ "squeezeSQL", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

                    nAllIn       += nIn
                    nAllDelete   += nIDs
                    ndevsWdelete +=1
                    if execOrTest.find("exec") >-1:
                        ret= subprocess.Popen(self.indigoUtilities+ "squeezeSQL", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                        if execOrTest.find("quiet")==-1 :
                            self.myLog(255, ret[0].strip("\n")+"-"+ret[1].strip("\n"),type="... sql response:" )
                        if unicode(ret).lower().find("error")>-1:
                            self.myLog(255,"stopping due to error you might need to kill sqlite3 processes \n"+ ret[0].strip("\n")+"-"+ret[1].strip("\n"),type="... sql error:" )
                            break
                    
            except Exception, e:
                self.myLog(-1, "executeDatabaseSqueeze error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e) )
        if execOrTest.find("exec") >-1:
            self.myLog(255, "Number of devices:"+ str(nDEVS)+"; devices where records where deleted: " +str(ndevsWdelete)+"; TOTAL  # of records deleted: " +str(nAllDelete)+ ";  out of: " + str(nAllIn) +" records  ===============\n",type="================")

        if execOrTest == "test": 
            try:
                gg.close()
            except:
                pass    
            self.myLog(255, "Test run: Number of devices:"+ str(nDEVS)+"; devices where records should be deleted: " +str(ndevsWdelete)+"; TOTAL  # of records (to be) deleted: " +str(nAllDelete)+ " out of " + str(nAllIn) +" records  ===============\n check out:  "+self.indigoUtilities+"squeezeSQL",type="================")
        self.executeDatabaseSqueezeCommand = ""
        return    

####-----------------   collect all info and call print         ---------
    def printSQLaction(self,action):
        try:
            valuesDict=action.props
            self.myLog(1,"printSQLaction  "+unicode(valuesDict))


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
                self.myLog(-1," printSQLaction   numberOfRecords must not be 0")
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
                self.myLog(-1," printSQLaction   variable or dev not specified: "+valuesDict["devOrVar"])

            self.printDeviceStates(valuesDict)
        except  Exception, e:
                self.myLog(-1," printSQLaction  error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
        self.executeDatabaseSqueezeCommand = ""        
        return

####-----------------   collect all info and call print         ---------
    def executeprintDeviceStates(self,valuesDict="",typeId="",devId=""):
        self.printDeviceStatesDictLast= copy.copy(valuesDict)
        self.pluginPrefs["printDeviceStates"] =self.printDeviceStatesDictLast
        self.printDeviceStatesDictLast= copy.copy(valuesDict)
        self.printDeviceStates(valuesDict,typeId,devId)
    
####-----------------   collect all info and call print 2         ---------
    def printDeviceStates(self,valuesDict="",typeId="",devId=""):
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
            self.myLog(1,"executeCALLBACK valuesDict: "+unicode(valuesDict))
            if valuesDict["devOrVar"]=="dev":
                if self.devID !=0:
                    varId=0
                    try:
                        devId = int(devId)
                    except:
                        self.myLog(-2,"bad data selected, wrong device id "+str(devId))
                        valuesDict["msg"]="wrong device id"
                        return valuesDict
                    if valuesDict["state0"] =="*":
                        states=["*"]
                    else:
                        try:
                            states[0] = valuesDict["state0"]
                            xx=indigo.devices[devId].states[states[0]]
                        except:
                            self.myLog(-2,"bad data selected, wrong device state "+states[0])
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
                        self.myLog(-2,"bad data selected, wrong variable id "+str(varId))
                        valuesDict["msg"]="wrong variable id"
                        return valuesDict

                    states = ["value"]
            else:
                self.myLog(-2,"no device or variable selected")
                valuesDict["msg"]="no device or variable selected"
                return valuesDict


            numberOfRecords = str(valuesDict["numberOfRecords"])
            if valuesDict["printFile"] =="":
                try:
                    nr=int(numberOfRecords)
                    if nr > 1000:
                        self.myLog(-1," too many records requested for print to log file, please print to file for numberOfRecords >1000; requested: "+numberOfRecords)
                        return
                except:
                        self.myLog(-1," too many records requested for print to log file, please print to file for numberOfRecords >1000; requested: "+numberOfRecords)
                        return
                
            
            id = valuesDict["id"]
            try:
                x=int(id)
            except:
                id=""
                
            valuesDict= self.printSQL(devId,varId,states,numberOfRecords,id,valuesDict["separator"],valuesDict["header"],valuesDict)

        except  Exception, e:
                self.myLog(-1," executeCALLBACK  error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
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
                pgm	= postGrePGM
            
            if devId !=0:
                idStr=str(devId)
                self.myLog(2,"print SQL data for device "+idStr+"/"+indigo.devices[devId].name+" states: "  +  str(states))
                devOrVar ="device_history_"
            elif varId !=0:
                idStr=str(varId)
                self.myLog(2,"print SQL data for variable "+idStr+"/"+indigo.variables[varId].name)
                devOrVar ="variable_history_"
            else:
                self.myLog(-2,"print SQL data  no variable or device given")
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
            
            sqlCommandText=  pgm
            if states[0] =="*":
                if self.liteOrPsql =="sqlite":
                    sqlCommandText+=  " \"SELECT "+ts+" , * "
                    fixOutput = True
                else:
                    sqlCommandText+=  " \"SELECT * "
            else:
                sqlCommandText+=  " \"SELECT id, "+ts
                for st in states:
                    if st !="":
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
            
            self.myLog(2,sqlCommandText ,"SQL command= " )
            extraMsg =""
            out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
            if out[1].find("is locked")>-1:
                self.myLog(2,"error in querry data base looked trying again" )
                self.sleep(0.5)
                out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                if out[1].find("is locked")>-1:
                    self.myLog(2,"error in querry data base looked trying again" )
                    self.sleep(0.5)
                    out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()


            if len(out[1]) > 1:
                valuesDict["msg"]="error in querry, check logfile"
                self.myLog(-2,"error in querry:\n" +out[1] ,"OUTPUT: " )

            else:
                result=copy.copy(out[0])
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
                        self.myLog(1,"print to file '"+self.indigoUtilities+ valuesDict["printFile"]+"'")
                        fFile=True
                        try:
                            f=open(self.indigoUtilities+valuesDict["printFile"],"w")
                            f.write(result)
                            if extraMsg !="":
                                f.write(extraMsg+"\n")
                            f.close()
                            valuesDict["msg"]="check INDIGO logfile for output"
                        except:
                            valuesDict["msg"]="error in printing to file"+self.indigoUtilities+valuesDict["printFile"]
                            self.myLog(-1,"error in printing to file  "+self.indigoUtilities+valuesDict["printFile"])

                if not fFile:
                    valuesDict["msg"]="check INDIGO logfile for output"
                    self.myLog(255,"\n" +result ,"SQL-OUTPUT: " )
                    if extraMsg !="":
                        self.myLog(255,extraMsg ,"SQL-OUTPUT: " )


                lines = result.strip("\n").split("\n")
                error = True

                if len(str(id).strip(" ")) ==0:  ## put  last-1 record to variable
                    try:
                        nn= len(lines)-2
                        if self.liteOrPsql !="sqlite" and header=="yes" and separator =="":	nn-=1
                        nn = max(nn,0)
                        self.myLog(2," last -1 record:   "+lines[nn])
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
                    except  Exception, e:
                        self.myLog(-1,"printSQL error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
                else:							## put   record #id to variable
                    nn=0
                    if header =="yes": nn+=1
                    if separator =="" and header =="yes": nn+=1
                    if self.liteOrPsql !="sqlite":	nn+=1
                    if len(lines) >nn+1:
                        try:
                            self.myLog(2,"record id# "+str(id)+"  "+lines[nn])
                            if separator=="":
                                value1 = lines[nn].split()[2]
                            else:
                                value1 = lines[nn].split(separator)[2]
                            indigo.variable.updateValue("SQLValueOutput",value1)
                            indigo.variable.updateValue("SQLLineOutput",lines[nn])
                            error = False
                        except  Exception, e:
                            self.myLog(-1,"printSQL error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))

                if error:
                    self.myLog(-1,"printSQL error  sql output - no string returned for "+states[0]+"  number of lines returned: "+  str(len(lines)) +" \n"+out[0])
                    valuesDict["msg"]="printSQL error  sql output - no string returned for "+states[0]
    

        except  Exception, e:
                self.myLog(-1,"printSQL error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
        return valuesDict


####-----------------   create sql statement, execute it and print outpout to logfile          ---------
    def printnOfRecords(self):

        try:
            sqlitePGM	= "/usr/bin/sqlite3   '"+self.indigoPath+ "logs/indigo_history.sqlite'"
            postGrePGM	= self.liteOrPsqlString +" -t -c "


            if self.liteOrPsql =="sqlite":
                pgm	= sqlitePGM
            else:
                pgm	= postGrePGM
            devList=[]
            for dd in indigo.devices:
                        id = dd.id
                        name=dd.name
                        sqlCommandText= pgm+ " \"SELECT COUNT(*) FROM device_history_"+str(id)+";\""
                        self.myLog(2,sqlCommandText ,"SQL command= " )
                        out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                        #self.myLog(255,name+" "+ unicode(out))
                        if out[1].find("is locked")>-1:
                            self.myLog(2,"error in querry data base looked trying again" )
                            self.sleep(0.5)
                            out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                            if out[1].find("is locked")>-1:
                                self.myLog(2,"error in querry data base looked trying again" )
                                self.sleep(0.5)
                                out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                        if len(out[1]) >0:
                                self.myLog(2,"error in querry data base: "+ unicode(out[1]) )
                        try:
                            ii = int(out[0].strip("\n"))
                        except:
                            ii=0
                        devList.append([ii,str(id).rjust(12)+" / "+name])
            devList=sorted(devList)


            varList=[]
            for dd in indigo.variables:
                        id = dd.id
                        name=dd.name
                        sqlCommandText= pgm+ " \"SELECT COUNT(*) FROM variable_history_"+str(id)+";\""
                        self.myLog(2,sqlCommandText ,"SQL command= " )
                        out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                        if out[1].find("is locked")>-1:
                            self.myLog(2,"error in querry data base looked trying again" )
                            self.sleep(0.5)
                            out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                            if out[1].find("is locked")>-1:
                                self.myLog(2,"error in querry data base looked trying again" )
                                self.sleep(0.5)
                                out= subprocess.Popen(sqlCommandText,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                        if len(out[1]) >0:
                                self.myLog(2,"error in querry data base: "+ unicode(out[1]) )
                        
                        try:
                            ii = int(out[0].strip("\n"))
                        except:
                            ii=0
                        varList.append([ii,str(id).rjust(12)+" / "+name])
                        ## self.myLog(255,(out[0].strip("\n")).rjust(15) +"  records in  "+name+"/"+str(id)+" "+out[1].strip("\n"))
            varList=sorted(varList)
            self.myLog(255,"   # of records        devId /  Name             for DEVICES")
            for dd in devList:
                self.myLog(255,str(dd[0]).rjust(15)+" "+dd[1]  )
            self.myLog(255,"   # of records        varId /  Name             for VARIABLES")
            for dd in varList:
                self.myLog(255,str(dd[0]).rjust(15)+" "+dd[1]  )
            
        



        except  Exception, e:
                self.myLog(-1,"printSQL error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
        return


            


####-----------------   main loop, is dummy           ---------
    def runConcurrentThread(self):

        self.stopConcurrentCounter = 0
        self.myLog(255,"Utilities plugin initialized, ==> select  action from plugin menu" )
        nlines =0
        lastnlines=0
        if os.path.isfile(self.indigoUtilities+"steps"):os.remove(self.indigoUtilities+"steps")
        loopCounter=0
        self.taskList =""
        try:
            while self.quitNow =="":
                self.sleep(5)

                loopCounter+=1
                
                if self.taskList.find("makepluginDateList") > -1:
                    self.makepluginDateList()
                
                if self.printNumberOfRecords ==1:
                    self.printnOfRecords()
                    self.printNumberOfRecords =0

                if self.postgresBackupStarted !=0:
                    ret = subprocess.Popen("ps -ef | grep '/pg_dump ' | grep -v grep ", stdout = subprocess.PIPE, shell = True).communicate()[0]
                    if len(ret)<5:
                        self.myLog(255,u" postgres backup dump  finished after " + str(int(time.time()-self.postgresBackupStarted))+"  seconds" )
                        self.postgresBackupStarted =0

                if self.executeDatabaseSqueezeCommand != "":
                    self.executeDatabaseSqueezeDoitNOW()

                ##  print status of steps in sql python program
                if loopCounter %5 ==0:
                    VS.versionCheck(self.pluginId,self.pluginVersion,indigo,14,50,printToLog="log")
                    if os.path.isfile(self.indigoUtilities+"steps"):
                        ll= os.path.getsize(self.indigoUtilities+"steps")
                        if ll==0: continue
                        steps= subprocess.Popen("cat '"+self.indigoUtilities+"steps'" , stdout = subprocess.PIPE, shell = True).communicate()[0]
                        lines = steps.strip("\n").split("\n")
                        nlines = len(lines)
                        if nlines == lastnlines: continue
                        for n in range(lastnlines, nlines):
                            self.myLog(2,"SQL step: "+lines[n])
                        lastnlines = nlines
    
                if self.cpuTempFreq !="": 
                    self.cpuTempFanUpdate()
                ## if backup started check if finished
                if self.backupStarted:
                        if len(subprocess.Popen("ps -ef | grep 'Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' | grep -v grep ", stdout = subprocess.PIPE, shell = True).communicate()[0])>20: continue
                        if not os.path.isfile(self.indigoUtilities+"retcodes"): continue
                        if os.path.getsize(self.indigoUtilities+"retcodes") >1:
                            self.myLog(255,"BACKUP of SQLite failed, check logfile: "+self.indigoUtilities+"backup.log")
                            self.triggerEvent(u"badBackup")
                        else:
                            self.myLog(2,"BACKUP files are: ")
                            if os.path.isfile(self.indigoPath+"logs/indigo_history-1.sqlite"):
                                self.myLog(2,self.indigoPath+"logs/indigo_history-1.sqlite")
                                if os.path.isfile(self.indigoPath+"logs/indigo_history-2.sqlite"):
                                    self.myLog(2,self.indigoPath+"logs/indigo_history-2.sqlite")
                                    if os.path.isfile(self.indigoPath+"logs/indigo_history-3.sqlite"):
                                        self.myLog(2,self.indigoPath+"logs/indigo_history-3.sqlite")
                                        if os.path.isfile(self.indigoPath+"logs/indigo_history-4.sqlite"):
                                            self.myLog(2,self.indigoPath+"logs/indigo_history-4.sqlite")
                                self.myLog(255,"backup of SQLite finished at "+ str(datetime.datetime.now()))
                            else:
                                self.myLog(255,"BACKUP of SQLite failed, check logfile: "+self.indigoUtilities+"backup.log  SQLITE file  "+self.indigoPath+"logs/indigo_history-1.sqlite   not created")
                                self.triggerEvent(u"badBackup")
                
                        self.backupStarted = False
                        if os.path.isfile(self.indigoUtilities+"steps"):os.remove(self.indigoUtilities+"steps")


                ## if FIX SQL  started check if finished
                if self.fixSQLStarted >0:

                    if self.fixSQLStarted ==99: #  request to cancel
                        self.fixSQLStarted = 0
                        pids = subprocess.Popen("ps -ef | grep 'Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' | grep -v grep ", stdout = subprocess.PIPE, shell = True).communicate()[0] 
                        if len(pids) >20:
                            pid = pids.split()
                            if len(pid)> 2 and int(pid[1]) >100:
                               ret = subprocess.Popen("kill -9 "+str(pid[1]),stdout = subprocess.PIPE,stderr = subprocess.PIPE, shell = True).communicate()
                               if len(ret[1]) >0:
                                    self.myLog(255,"FIX of SQLite cancel reqquest job failed")
                                    continue
                               self.myLog(255,"FIX of SQLite cancel request done")
                        else:      
                            self.myLog(255,"FIX of SQLite cancel request: job is already gone")
                        continue
                               
                    if len(subprocess.Popen("ps -ef | grep 'Plugins/utilities.indigoPlugin/Contents/Server Plugin/mkbackup.py' | grep -v grep ", stdout = subprocess.PIPE, shell = True).communicate()[0])>20: 
                        if loopCounter %50 ==0:
                            self.myLog(255,"FIX of SQLite still running, check ~/Documents/indigoUtilities/backup.log/  for detailed info")
                        self.fixSQLStarted =2
                        continue
                    if self.fixSQLStarted ==1: #  request to start job 
                        if len(subprocess.Popen("ps -ef | grep 'SQL Logger.indigoPlugin' | grep -v grep ", stdout = subprocess.PIPE, shell = True).communicate()[0])>20: 
                            self.myLog(255,"FIX SQL not started, please shutdown sql logger first")
                            continue                    
                        self.executeSQL([],0,0,"fix")
                        self.myLog(255,"FIX SQL job submitted, check ~/Documents/indigoUtilities/backup.log/  for detailed info, this might take a long time (~ 1 hour for 8GByte on Mac-Mini 2014)")
                        self.fixSQLStarted =2
                        continue

                    if not os.path.isfile(self.indigoUtilities+"retcodes"): continue
                    if os.path.getsize(self.indigoUtilities+"retcodes") >1:
                        self.myLog(255,"FIX of SQLite failed, check logfile: "+self.indigoUtilities+"backup.log")
                        self.fixSQLStarted = 0
                    else:
                        if os.path.isfile(self.indigoPath+"logs/indigo_history-fixed.sqlite"):
                            self.myLog(255,"FIX of SQLite finished successfully, fixed file is : "+self.indigoPath+"logs/indigo_history-fixed.sqlite")
                            self.myLog(255," to use fixed database:")
                            self.myLog(255,"  -- make sure sqllogger is disabled")
                            self.myLog(255,"  -- rename indigo_history.sqlite file to eg indigo_history.backup")
                            self.myLog(255,"  -- rename indigo_history-fixed.sqlite to indigo_history.sqlite")
                            self.myLog(255,"  -- re-start SQLlogger")
                            self.myLog(255," if it does not work, stop sqllogger, delte indigo_history.sqlite and rename  indigo_history.backup to indigo_history.sqlite, re-start SQLlogger")
                        else:
                            self.myLog(255,"FIX of SQLite failed, check logfile: "+self.indigoUtilities+"backup.log  .. "+  self.indigoPath+"logs/indigo_history-fixed.sqlite file not created")
                    self.myLog(255,"FIX of SQLite finished at "+ str(datetime.datetime.now()))
                    self.fixSQLStarted = 0
                    if os.path.isfile(self.indigoUtilities+"steps"):os.remove(self.indigoUtilities+"steps")
                    
                    
        



            self.stopConcurrentCounter = 1
            #serverPlugin = indigo.server.getPlugin(self.pluginId)
            #serverPlugin.restart(waitUntilDone=False)
            #self.sleep(1)
        except  Exception, e:
            if len(unicode(e)) > 5:
                self.myLog(-1,"error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))
        self.quitNow =""
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
    #		self.myLog(4,u"<<-- entering triggerEvent: %s " % eventId)
        for trigId in self.triggerList:
            trigger = indigo.triggers[trigId]
            if trigger.pluginTypeId == eventId:
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
        
            data = (subprocess.Popen("'"+self.pathToPlugin+"osx-temp-fan'",shell=True,stdout=subprocess.PIPE).communicate()[0].strip("\n")).split("\n")
            for line in data:
                ll = line.split(":")
                if len(ll) < 2: continue
                if  ll[0].find("temp") > -1:
                    t = float(ll[1])
                    if t < 0: continue
                    if self.cpuTempUnit == "F": 
                        t = t*9./5/+32
                    try:      indigo.variables[ll[0]]
                    except:   indigo.variable.create(ll[0])
                    indigo.variable.updateValue(ll[0], self.cpuTempFormat%t)
                else:
                    try:      indigo.variables[ll[0]]
                    except:   indigo.variable.create(ll[0])
                    indigo.variable.updateValue(ll[0], ll[1])

        except  Exception, e:
            if len(unicode(e)) > 5:
                self.myLog(-1,"error in  Line '%s' ;  error='%s'" % (sys.exc_traceback.tb_lineno, e))

####----------------- logfile  ---------
    def myLog(self,msgLevel,text,type=""):
        if msgLevel ==0: return
        if msgLevel ==-1:
            indigo.server.log(u"--------------------------------------------------------------")
            indigo.server.log(text)
            indigo.server.log(u"--------------------------------------------------------------")
            return
        if msgLevel ==-2:
            self.errorLog(u"----------------------------------------------------------------------------------" )
            self.errorLog(text)
            self.errorLog(u"----------------------------------------------------------------------------------" )
            return
        if msgLevel ==255:
            if type =="": indigo.server.log(text)
            else:		  indigo.server.log(text,type=type)
            return
        if self.debugLevel ==255:
            if type =="": indigo.server.log(text)
            else:		  indigo.server.log(text,type=type)
            return
        if self.debugLevel&msgLevel >0:
            if type =="": indigo.server.log(text)
            else:		  indigo.server.log(text,type=type)
            return


