#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# sumMeters device: adds up power, current, energy states of other (any) indigo devices
# per kind up to 8 sources (device + state + unit), sums in a selectable unit,
# min / max (w date time) / time weighted average for today and yesterday, sum of sums w loop check
# updates when a source state changes (indigo device change subscription), at least every 5 minutes

import time, datetime
import indigo

devType			= "sumMeters"
_slots			= 8
_forcedUpdate	= 300		# secs, a sum device is updated at least this often
_dateFormat		= "%Y-%m-%d %H:%M:%S"
_categories		= {	"power":	{"default":"W",  "match":["power", "watt"],			"units":{"mW":0.001, "W":1., "kW":1000.}},
					"current":	{"default":"A",  "match":["current", "amp"],		"units":{"mA":0.001, "A":1.}},
					"energy":	{"default":"Wh", "match":["energy", "kwh", "wh"],	"units":{"Ws":1./3600., "Wh":1., "kWh":1000., "MWh":1000000.}} }
_unitDecimals	= {"mW":0, "W":1, "kW":3, "mA":0, "A":3, "Ws":0, "Wh":1, "kWh":3, "MWh":6}
_stringStates	= ["lastSumUpdate", "source_Power", "source_Current", "source_Energy"]
_statsSuffixes	= ["MinToday", "MinTodayAt", "MaxToday", "MaxTodayAt", "AveToday", "MinYesterday", "MinYesterdayAt", "MaxYesterday", "MaxYesterdayAt", "AveYesterday"]


####-------------------------------------------------------------------------####
class SumMeters(object):

	def __init__(self, plugin):
		self.plugin			= plugin
		self.devs			= {}	# {sumDevId:{"sources":{slot:(srcDevId, state, unit, factor)}, "sumUnit":{}, "values":{}, "missing":{}, "stats":{}, "lastUpdate":0}}
		self.sourceIndex	= {}	# {srcDevId:[sumDevIds]}
		self.subscribed		= False
		self.devScan		= []
		self.devScanTime	= 0

	def log(self, level, text, exc=False):
		try:	self.plugin.logger.log(level, text, exc_info=exc)
		except:	indigo.server.log(text)

	####-------------------------------------------------------------------------####
	def number(self, value):
		# numeric value of a source state, None if not a number
		if isinstance(value, bool): return None
		if isinstance(value, (int, float)): return float(value)
		try:	return float("{}".format(value).strip().split(" ")[0])
		except: return None

	####-------------------------------------------------------------------------####
	# device edit
	####-------------------------------------------------------------------------####
	def filterSourceDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
		# all indigo devices that have at least one numeric state, devices with a matching state name first
		# scanning all devices is slow: done once, the 24 device menus of one dialog use the cached scan (30 secs)
		try:
			if time.time() - self.devScanTime > 30:
				scan = []
				for dev in indigo.devices:
					names = ""
					for state, value in dev.states.items():
						if state.endswith(".ui"): continue
						if self.number(value) is None: continue
						names += state.lower() + " "
					if names != "": scan.append((dev.id, dev.name, names))
				self.devScan = scan
				self.devScanTime = time.time()
			match = _categories.get(filter, {}).get("match", [])
			xList = []
			for devId, name, names in self.devScan:
				if devId == targetId: continue
				xList.append([str(devId), ("" if any(mm in names for mm in match) else "~ ") + name])
			xList.sort(key=lambda x: x[1].lower())
		except Exception:
			self.log(40, "", exc=True)
			xList = []
		return [["0", "select device"]] + xList

	####-------------------------------------------------------------------------####
	def filterSourceStates(self, filter="", valuesDict=None, typeId="", targetId=0):
		# numeric states of the device selected in field filter (eg powerDev3)
		xList = []
		try:
			if valuesDict is None: return [["0", "select device first"]]
			srcId = int(valuesDict.get(filter, "0") or 0)
			if srcId <= 0 or srcId not in indigo.devices: return [["0", "select device first"]]
			dev = indigo.devices[srcId]
			for state in sorted(dev.states, key=lambda x: x.lower()):
				if state.endswith(".ui"): continue
				value = dev.states[state]
				if self.number(value) is None: continue
				xList.append([state, "{} = {}".format(state, value)])
		except Exception:
			self.log(40, "", exc=True)
		if xList == []: return [["0", "no numeric state"]]
		return xList

	####-------------------------------------------------------------------------####
	def sourceDevCallback(self, valuesDict, typeId="", devId=0):
		# a source device was selected: pick a matching state and unit if the current state does not fit
		try:
			for cat in _categories:
				for slot in range(1, _slots + 1):
					try:	srcId = int(valuesDict.get("{}Dev{}".format(cat, slot), "0") or 0)
					except: srcId = 0
					stateField = "{}State{}".format(cat, slot)
					if srcId <= 0 or srcId not in indigo.devices: continue
					srcDev = indigo.devices[srcId]
					states = srcDev.states
					if valuesDict.get(stateField, "0") in states: continue
					valuesDict[stateField] = "0"
					if srcDev.deviceTypeId == devType and cat + "Sum" in states:
						# sum of sums: take the sum of the same kind in the unit of that device
						valuesDict[stateField] = cat + "Sum"
						valuesDict["{}Unit{}".format(cat, slot)] = srcDev.pluginProps.get(cat + "SumUnit", _categories[cat]["default"])
						continue
					for state in sorted(states):
						if state.endswith(".ui") or self.number(states[state]) is None: continue
						if any(mm in state.lower() for mm in _categories[cat]["match"]):
							valuesDict[stateField] = state
							for unit in sorted(_categories[cat]["units"], key=len, reverse=True): # guess unit from state name, eg energy_kWh
								if state.lower().endswith(unit.lower()):
									valuesDict["{}Unit{}".format(cat, slot)] = unit
									break
							break
		except Exception:
			self.log(40, "", exc=True)
		return valuesDict

	####-------------------------------------------------------------------------####
	def sourceIds(self, props):
		# dev ids used as sources in the props of a sum device
		ids = []
		for cat in _categories:
			try:	count = int(props.get(cat + "Count", "0"))
			except: count = 0
			for slot in range(1, count + 1):
				try:	srcId = int(props.get("{}Dev{}".format(cat, slot), "0") or 0)
				except: srcId = 0
				if srcId > 0 and srcId not in ids: ids.append(srcId)
		return ids

	####-------------------------------------------------------------------------####
	def loopCheck(self, devId, valuesDict):
		# sum of sums: a sum device must not end up as its own source (A uses B, B uses A); returns the loop as text or ""
		try:
			def name(i):
				try:	return indigo.devices[i].name
				except: return str(i)
			todo = [(srcId, [devId, srcId]) for srcId in self.sourceIds(valuesDict)]
			seen = set()
			while todo:
				srcId, path = todo.pop()
				if srcId == devId: return " -> ".join(name(i) for i in path)
				if srcId in seen or srcId not in indigo.devices: continue
				seen.add(srcId)
				srcDev = indigo.devices[srcId]
				if srcDev.deviceTypeId != devType: continue
				for nextId in self.sourceIds(srcDev.pluginProps):
					todo.append((nextId, path + [nextId]))
		except Exception:
			self.log(40, "", exc=True)
		return ""

	####-------------------------------------------------------------------------####
	def validate(self, valuesDict, devId):
		errorDict = indigo.Dict()
		try:
			for cat in _categories:
				try:	count = int(valuesDict.get(cat + "Count", "0"))
				except: count = 0
				for slot in range(1, count + 1):
					devField, stateField = "{}Dev{}".format(cat, slot), "{}State{}".format(cat, slot)
					try:	srcId = int(valuesDict.get(devField, "0") or 0)
					except: srcId = 0
					if srcId <= 0:
						continue # empty slot, skipped
					elif srcId == int(devId):
						errorDict[devField] = "can not use itself"
					elif valuesDict.get(stateField, "0") in ["", "0"]:
						errorDict[stateField] = "select a state"
			if len(errorDict) == 0:
				loop = self.loopCheck(int(devId), valuesDict)
				if loop != "":
					valuesDict["MSG"] = "ERROR: loop " + loop
					errorDict["MSG"] = valuesDict["MSG"]
					return (False, valuesDict, errorDict)
			if len(errorDict) > 0:
				valuesDict["MSG"] = "ERROR: select a state for each source device"
				errorDict["MSG"] = valuesDict["MSG"]
				return (False, valuesDict, errorDict)
			valuesDict["MSG"] = "OK"
			valuesDict["address"] = ""
		except Exception:
			self.log(40, "", exc=True)
		return (True, valuesDict, errorDict)

	####-------------------------------------------------------------------------####
	def printPropsStates(self, valuesDict, typeId="", devId=0):
		try:
			dev = indigo.devices[int(devId)]
			out = "\n===== device: {}, id:{}, type:{}".format(dev.name, dev.id, dev.deviceTypeId)
			out += "\n----- properties:"
			props = dev.pluginProps
			for key in sorted(props):
				out += "\n  {:35s}: {!r:30}  {}".format(key, props[key], type(props[key]).__name__)
			out += "\n----- states:"
			for key in sorted(dev.states):
				out += "\n  {:35s}: {!r:30}  {}".format(key, dev.states[key], type(dev.states[key]).__name__)
			self.log(20, out)
		except Exception:
			self.log(40, "", exc=True)
		return valuesDict

	####-------------------------------------------------------------------------####
	# running
	####-------------------------------------------------------------------------####
	def usedSlots(self, props):
		# {cat:[slot numbers with a source device]}, only kinds with at least one source
		used = {}
		for cat in _categories:
			try:	count = int(props.get(cat + "Count", "0"))
			except: count = 0
			for slot in range(1, min(count, _slots) + 1):
				if "{}".format(props.get("{}Dev{}".format(cat, slot), "0")) not in ["", "0"]:
					used.setdefault(cat, []).append(slot)
		return used

	####-------------------------------------------------------------------------####
	def statsEnabled(self, dev, cat):
		# device edit checkbox "<cat>_EnableMinMax", default on
		return "{}".format(dev.pluginProps.get(cat + "_EnableMinMax", True)).lower() not in ["false", "0", "no"]

	####-------------------------------------------------------------------------####
	def deviceStateList(self, dev, stateList):
		# states only for the kinds (power, current, energy) and slots in use, called from plugin.getDeviceStateList
		try:
			have = set(st.get("Key", "") for st in stateList)
			def add(sid, number=True):
				if sid in have: return
				have.add(sid)
				if number:	stateList.append(self.plugin.getDeviceStateDictForNumberType(sid, sid, sid))
				else:		stateList.append(self.plugin.getDeviceStateDictForStringType(sid, sid, sid))
			for cat, slots in self.usedSlots(dev.pluginProps).items():
				add(cat + "Sum")
				for slot in slots: add("{}{}".format(cat, slot))
				if self.statsEnabled(dev, cat):
					for suf in _statsSuffixes: add(cat + "Sum" + suf, number=not suf.endswith("At"))
				add("source_" + cat.capitalize(), number=False)
		except Exception:
			self.log(40, "", exc=True)
		return stateList

	####-------------------------------------------------------------------------####
	def initTypedStates(self, dev):
		# first write must have the right type, not "": the sql logger creates the column type from it
		try:
			chList = []
			for state in dev.states:
				if state in _stringStates or state.endswith("At") or state.endswith(".ui"): continue
				if dev.states[state] in ["", None]: chList.append({"key":state, "value":0.0})
			if chList != []: dev.updateStatesOnServer(chList)
		except Exception:
			self.log(40, "", exc=True)
		return

	####-------------------------------------------------------------------------####
	def start(self, dev):
		try:
			try:	dev.stateListOrDisplayStateIdChanged()
			except:	pass
			dev = indigo.devices[dev.id]
			self.initTypedStates(dev)
			dev = indigo.devices[dev.id]
			props = dev.pluginProps
			sources = {}
			sumUnit = {}
			for cat in _categories:
				units = _categories[cat]["units"]
				sumUnit[cat] = props.get(cat + "SumUnit", _categories[cat]["default"])
				if sumUnit[cat] not in units: sumUnit[cat] = _categories[cat]["default"]
				try:	count = int(props.get(cat + "Count", "0"))
				except: count = 0
				for slot in range(1, count + 1):
					try:	srcId = int(props.get("{}Dev{}".format(cat, slot), "0") or 0)
					except: srcId = 0
					state = props.get("{}State{}".format(cat, slot), "")
					unit = props.get("{}Unit{}".format(cat, slot), _categories[cat]["default"])
					if unit not in units: unit = _categories[cat]["default"]
					if srcId > 0 and state not in ["", "0"]:
						# factor converts the source value to the unit of the sum
						sources["{}{}".format(cat, slot)] = (srcId, state, unit, units[unit] / units[sumUnit[cat]])
			self.devs[dev.id] = {"sources":sources, "sumUnit":sumUnit, "values":{}, "missing":{}, "stats":self.statsRestore(dev, time.time()), "lastUpdate":0}
			self.buildSourceIndex()
			if sources != {} and not self.subscribed:
				indigo.devices.subscribeToChanges()  # needed to get deviceUpdated for devices of other plugins
				self.subscribed = True
			self.update(dev.id)
			self.log(20, "sumMeters device {} started, adding up {} sources".format(dev.name, len(sources)))
		except Exception:
			self.log(40, "", exc=True)
		return

	####-------------------------------------------------------------------------####
	def stop(self, devId):
		try:
			self.devs.pop(devId, None)
			self.buildSourceIndex()
		except Exception:
			self.log(40, "", exc=True)
		return

	####-------------------------------------------------------------------------####
	def buildSourceIndex(self):
		index = {}
		for sumId in self.devs:
			for slot, (srcId, state, unit, factor) in self.devs[sumId]["sources"].items():
				index.setdefault(srcId, [])
				if sumId not in index[srcId]: index[srcId].append(sumId)
		self.sourceIndex = index
		return

	####-------------------------------------------------------------------------####
	def deviceUpdated(self, origDev, newDev):
		try:
			if newDev.id not in self.sourceIndex: return
			for sumId in list(self.sourceIndex[newDev.id]):
				self.update(sumId, srcDev=newDev)
		except Exception:
			self.log(40, "", exc=True)
		return

	####-------------------------------------------------------------------------####
	def periodic(self):
		# called from the main loop: a sum device w/o update for 5 minutes rereads all sources and writes its states
		# (midnight roll over, average and lastSumUpdate also when no source changes)
		for sumId in list(self.devs):
			if time.time() - self.devs[sumId].get("lastUpdate", 0) >= _forcedUpdate:
				self.update(sumId, force=True)
		return

	####-------------------------------------------------------------------------####
	def update(self, sumId, srcDev=None, now=None, force=False):
		# read the source states (all, or only the ones of srcDev), add them up and write the states that changed
		try:
			if now is None: now = time.time()
			if sumId not in self.devs or sumId not in indigo.devices: return
			sumData = self.devs[sumId]
			sumDev = indigo.devices[sumId]
			changed = False
			for slot, (srcId, state, unit, factor) in sumData["sources"].items():
				if srcDev is not None and srcId != srcDev.id: continue
				raw = None
				if srcDev is not None:
					raw = srcDev.states.get(state, None)
				elif srcId in indigo.devices:
					raw = indigo.devices[srcId].states.get(state, None)
				value = self.number(raw)
				if value is None:
					if raw != "" and not sumData["missing"].get(slot, False): # "" = no data yet, eg a lower level sum device not started yet
						self.log(30, "sumMeters device {}: source {} dev id:{} state:{} not found or not a number, using 0".format(sumDev.name, slot, srcId, state))
						sumData["missing"][slot] = True
					value = 0.
				else:
					sumData["missing"][slot] = False
					value *= factor
				if sumData["values"].get(slot, None) != value:
					sumData["values"][slot] = value
					changed = True
			if not changed and srcDev is not None: return

			chList = []
			sums = {}
			for cat in _categories:
				unit = sumData["sumUnit"][cat]
				dec = _unitDecimals.get(unit, 3)
				total = 0.
				for slot in range(1, _slots + 1):
					key = "{}{}".format(cat, slot)
					value = round(sumData["values"].get(key, 0.), dec)
					total += value
					if key in sumDev.states and sumDev.states[key] != value:
						chList.append({"key":key, "value":value, "decimalPlaces":dec})
				total = round(total, dec)
				sums[cat] = total
				if cat + "Sum" not in sumDev.states: continue # kind not used, no states
				if sumDev.states[cat + "Sum"] != total:
					chList.append({"key":cat + "Sum", "value":total, "decimalPlaces":dec, "uiValue":"{:.{}f} {}".format(total, dec, unit)})
				if any(slot.startswith(cat) for slot in sumData["sources"]):
					self.stats(sumDev, cat, total, now, dec, unit, chList)

			for cat in _categories:
				# source dev ids in slot order, eg source_Power = "1378652208, 51092918"
				key = "source_" + cat.capitalize()
				ids = ", ".join("{}".format(sumData["sources"][cat + str(slot)][0]) for slot in range(1, _slots + 1) if cat + str(slot) in sumData["sources"])
				if key in sumDev.states and sumDev.states[key] != ids: chList.append({"key":key, "value":ids})

			display = sumDev.pluginProps.get("displaySelect", "powerSum")
			cat = display.replace("Sum", "")
			if cat in sums:
				unit = sumData["sumUnit"][cat]
				dec = _unitDecimals.get(unit, 3)
				if sumDev.states.get("sensorValue", None) != sums[cat]:
					chList.append({"key":"sensorValue", "value":sums[cat], "decimalPlaces":dec, "uiValue":"{:.{}f} {}".format(sums[cat], dec, unit)})

			if chList == [] and not force: return
			chList.append({"key":"lastSumUpdate", "value":datetime.datetime.fromtimestamp(now).strftime(_dateFormat)})
			sumDev.updateStatesOnServer(chList)
			sumData["lastUpdate"] = now
		except Exception:
			self.log(40, "", exc=True)
		return

	####-------------------------------------------------------------------------####
	def statsRestore(self, sumDev, now):
		# after a restart: continue today's min / max / average from the states, if they are from today
		stats = {}
		today = datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d")
		midnight = time.mktime(datetime.datetime.strptime(today, "%Y-%m-%d").timetuple())
		try:	lastUpdate = time.mktime(datetime.datetime.strptime(sumDev.states["lastSumUpdate"], _dateFormat).timetuple())
		except: lastUpdate = 0
		for cat in _categories:
			try:
				if "{}".format(sumDev.states[cat + "SumMinTodayAt"])[:10] != today or lastUpdate < midnight: continue
				seconds = max(0., min(now, lastUpdate) - midnight)
				stats[cat] = {"day":today, "min":float(sumDev.states[cat + "SumMinToday"]), "minAt":sumDev.states[cat + "SumMinTodayAt"],
							"max":float(sumDev.states[cat + "SumMaxToday"]), "maxAt":sumDev.states[cat + "SumMaxTodayAt"],
							"integral":float(sumDev.states[cat + "SumAveToday"]) * seconds, "seconds":seconds,
							"lastValue":float(sumDev.states[cat + "Sum"]), "lastTime":now}
			except Exception:
				pass
		return stats

	####-------------------------------------------------------------------------####
	def stats(self, sumDev, cat, value, now, dec, unit, chList):
		# min, max (w time) and time weighted average of the sum for today; at midnight today --> yesterday
		try:
			if cat + "SumAveToday" not in sumDev.states: return
			allStats = self.devs[sumDev.id].setdefault("stats", {})
			nowDT = datetime.datetime.fromtimestamp(now)
			today = nowDT.strftime("%Y-%m-%d")
			nowStr = nowDT.strftime(_dateFormat)
			pre = cat + "Sum"
			st = allStats.get(cat, None)
			if st is None:
				st = {"day":today, "min":value, "minAt":nowStr, "max":value, "maxAt":nowStr, "integral":0., "seconds":0., "lastValue":value, "lastTime":now}
				allStats[cat] = st

			if st["day"] != today:
				# close the old day at midnight, the last value is valid until then
				midnight = time.mktime(datetime.datetime.strptime(today, "%Y-%m-%d").timetuple())
				dt = max(0., midnight - st["lastTime"])
				st["integral"] += st["lastValue"] * dt
				st["seconds"]  += dt
				ave = st["integral"] / st["seconds"] if st["seconds"] > 0 else st["lastValue"]
				chList.append({"key":pre + "MinYesterday",   "value":round(st["min"], dec), "decimalPlaces":dec, "uiValue":"{:.{}f} {}".format(st["min"], dec, unit)})
				chList.append({"key":pre + "MinYesterdayAt", "value":st["minAt"]})
				chList.append({"key":pre + "MaxYesterday",   "value":round(st["max"], dec), "decimalPlaces":dec, "uiValue":"{:.{}f} {}".format(st["max"], dec, unit)})
				chList.append({"key":pre + "MaxYesterdayAt", "value":st["maxAt"]})
				chList.append({"key":pre + "AveYesterday",   "value":round(ave, dec), "decimalPlaces":dec, "uiValue":"{:.{}f} {}".format(ave, dec, unit)})
				midnightStr = today + " 00:00:00"
				st.update({"day":today, "min":st["lastValue"], "minAt":midnightStr, "max":st["lastValue"], "maxAt":midnightStr,
								"integral":0., "seconds":0., "lastTime":midnight})

			dt = max(0., now - st["lastTime"])
			st["integral"] += st["lastValue"] * dt
			st["seconds"]  += dt
			st["lastValue"] = value
			st["lastTime"]  = now
			if value < st["min"]: st["min"], st["minAt"] = value, nowStr
			if value > st["max"]: st["max"], st["maxAt"] = value, nowStr
			ave = st["integral"] / st["seconds"] if st["seconds"] > 0 else value

			for key, val in [("MinToday", st["min"]), ("MaxToday", st["max"]), ("AveToday", ave)]:
				val = round(val, dec)
				if sumDev.states[pre + key] != val: chList.append({"key":pre + key, "value":val, "decimalPlaces":dec, "uiValue":"{:.{}f} {}".format(val, dec, unit)})
			for key, val in [("MinTodayAt", st["minAt"]), ("MaxTodayAt", st["maxAt"])]:
				if sumDev.states[pre + key] != val: chList.append({"key":pre + key, "value":val})
		except Exception:
			self.log(40, "", exc=True)
		return
