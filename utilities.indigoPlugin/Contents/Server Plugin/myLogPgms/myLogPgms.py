######################################################################################
# .logfile handling 
######################################################################################
import indigo
import os 
import sys
import datetime
import time


class MLX():

	def __init__(self):
		self.logFile		= ""
		self.logFileActive	= False
		self.debugLevel		= []
		self.maxFileSize	= 5000000
		self.lastCheck		= time.time()


####-----------------  set paramete rs ---------
	def myLogSet(self, debugLevel, logFileActive, logFile , pluginSelf):# eg (debugLevel = "abc",logFileActive=True/False ,logFile = "pathToLogFile",	 maxFileSize = 10000000)
		try:
			self.logFileActive	 = logFileActive
			self.logFile		= logFile
			self.debugLevel		= debugLevel
			self.maxFileSize	= 100000
			self.plugin			= pluginSelf
		except	Exception as e:
			if len(str(e)) > 5:
				indigo.server.log("in Line '%s' has error='%s'" % (sys.exc_info()[2].tb_lineno, e))
		self.myLog( text="myLogSet setting parameters -- logFileActive= "+ str(self.logFileActive) + "; logFile= "+ str(self.logFile)+ ";  debugLevel= "+ str(self.debugLevel) +"; maxFileSize= "+ str(self.maxFileSize), destination="standard")


####-----------------  check logfile sizes ---------
	def checkLogFiles(self):
		try:
			self.lastCheck = time.time()
			if self.logFileActive =="standard": return 
			
			fn = self.logFile.split(".log")[0]
			if os.path.isfile(fn + ".log"):
				fs = os.path.getsize(fn + ".log")
				if fs > self.maxFileSize:
					self.myLog(text=" reset logfile due to size > " +str(self.maxFileSize))
					if os.path.isfile(fn + "-2.log"):
						os.remove(fn + "-2.log")
					if os.path.isfile(fn + "-1.log"):
						os.rename(fn + "-1.log", fn + "-2.log")
					os.rename(fn + ".log", fn + "-1.log")
		except	Exception as e:
			if len(str(e)) > 5:
				indigo.server.log( "checkLogFiles in Line '%s' has error='%s'" % (sys.exc_info()[2].tb_lineno, e))
			
			
####-----------------	 ---------
	def decideMyLog(self, msgLevel):
		try:
			if msgLevel	 == "all" or "all" in self.debugLevel:	 return True
			if msgLevel	 == ""	 and "all" not in self.debugLevel:	 return False
			if msgLevel in self.debugLevel:							 return True
			return False
		except	Exception as e:
			if len(str(e)) > 5:
				indigo.server.log( "decideMyLog in Line '%s' has error='%s'" % (sys.exc_info()[2].tb_lineno, e))
		return False

####-----------------  print to logfile or indigo log  ---------
	def myLog(self,	 text="", mType="", errorType="", showDate=True, destination=""):
		   
	
		if	time.time() - self.lastCheck > 100:
			 self.checkLogFiles()

		try:
			if	self.logFileActive =="standard" or destination.find("standard") >-1:
				if errorType == "smallErr":
					self.plugin.errorLog("------------------------------------------------------------------------------")
					self.plugin.errorLog(text)
					self.plugin.errorLog("------------------------------------------------------------------------------")

				elif errorType == "bigErr":
					self.plugin.errorLog("==================================================================================")
					self.plugin.errorLog(text)
					self.plugin.errorLog("==================================================================================")

				elif mType == "":
					indigo.server.log(text)
				else:
					indigo.server.log(text, type=mType)


			if	self.logFileActive !="standard":

				ts =""
				try:
					if len(self.logFile) < 3: return # not properly defined
					f =	 open(self.logFile,"a")
				except	Exception as e:
					indigo.server.log("in Line '%s' has error='%s'" % (sys.exc_info()[2].tb_lineno, e))
					try:
						f.close()
					except:
						pass
					return

				if errorType == "smallErr":
					if showDate: ts = datetime.datetime.now().strftime("%m-%d %H:%M:%S")
					f.write("----------------------------------------------------------------------------------\n")
					f.write(ts+" ".ljust(12)+"-"+text+"\n")
					f.write("----------------------------------------------------------------------------------\n")
					f.close()
					return

				if errorType == "bigErr":
					if showDate: ts = datetime.datetime.now().strftime("%m-%d %H:%M:%S")
					ts = datetime.datetime.now().strftime("%m-%d %H:%M:%S")
					f.write("==================================================================================\n")
					f.write(ts+" "+" ".ljust(12)+"-"+text+"\n")
					f.write("==================================================================================\n")
					f.close()
					return

				if showDate: ts = datetime.datetime.now().strftime("%m-%d %H:%M:%S")
				if mType == "":
					f.write(ts+" " +" ".ljust(25)  +"-" + text + "\n")
				else:
					f.write(ts+" " +mType.ljust(25) +"-" + text + "\n")
				f.close()
				return


		except	Exception as e:
			if len(str(e)) > 5:
				indigo.server.log("myLog in Line '%s' has error='%s'" % (sys.exc_info()[2].tb_lineno, e))
				indigo.server.log(text)
				try: f.close()
				except: pass


