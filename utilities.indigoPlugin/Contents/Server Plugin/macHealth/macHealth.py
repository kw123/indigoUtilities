#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# measures the health of the mac that runs indigo: cpu, memory, disk, network, busiest processes
# no indigo dependency, every function returns plain python values or None if a value is not available
# cpu is read from the kernel with ctypes (no subprocess), the rest with short lived system commands

import os, re, subprocess, time, ctypes, resource, plistlib, socket


####-------------------------------------------------------------------------####
def run(args, timeout=20):
	try:
		return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout).stdout.decode("utf_8", "replace")
	except Exception:
		return ""


####-------------------------------------------------------------------------####
def hmsToSecs(text):
	## ps prints [dd-][[hh:]mm:]ss[.ff], minutes can be > 59 for cpu time
	try:
		days = 0
		if text.find("-") > -1:
			d, text = text.split("-", 1)
			days = int(d)
		secs = 0.
		for part in text.split(":"):
			secs = secs*60. + float(part)
		return days*86400. + secs
	except Exception:
		return 0.


####-------------------------------------------------------------------------####
class MacHealth(object):

	def __init__(self):
		self.nCPUs = os.cpu_count() or 1
		self.indigoPath  = ""      # set by the plugin, where the Plugins folder of indigo is: to read plugin id and version
		self.pluginCache = {}
		self.libSystem = None
		try:
			lib = ctypes.CDLL("/usr/lib/libSystem.dylib")
			lib.mach_host_self.restype  = ctypes.c_uint
			lib.host_statistics.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
			lib.host_statistics.restype  = ctypes.c_int
			self.libSystem = lib
		except Exception:
			pass

	####-----------------  cpu: kernel tick counters = user, system, idle, nice; they are 32 bit and wrap ---------
	def cpuTicks(self):
		if self.libSystem is None: return None
		try:
			buf   = (ctypes.c_uint * 4)()
			count = ctypes.c_uint(4)
			if self.libSystem.host_statistics(self.libSystem.mach_host_self(), 3, ctypes.byref(buf), ctypes.byref(count)) != 0:  # 3 = HOST_CPU_LOAD_INFO
				return None
			return (buf[0], buf[1], buf[2], buf[3])
		except Exception:
			return None

	####-----------------  busy / user / system in % of the capacity of all cores between two tick readings ---------
	def cpuPercent(self, ticksOld, ticksNew):
		if ticksOld is None or ticksNew is None: return None
		d = [(n - o) % 4294967296 for o, n in zip(ticksOld, ticksNew)]
		total = sum(d)
		if total <= 0: return None
		user = (d[0] + d[3]) * 100. / total
		sys_ = d[1] * 100. / total
		return {"busy": user + sys_, "user": user, "system": sys_}

	####-----------------  cpu seconds used so far by this process and by the commands it started (user, system) ---------
	def ownCpu(self):
		try:
			a = resource.getrusage(resource.RUSAGE_SELF)
			b = resource.getrusage(resource.RUSAGE_CHILDREN)
			return (a.ru_utime + b.ru_utime, a.ru_stime + b.ru_stime)
		except Exception:
			return None

	####-----------------  what this process used between two ownCpu readings, in % of the capacity of all cores ---------
	def ownPercent(self, old, new, secs):
		if old is None or new is None or secs <= 0: return None
		cap = secs * self.nCPUs / 100.
		user, system = max(0., new[0] - old[0]) / cap, max(0., new[1] - old[1]) / cap
		return {"busy": user + system, "user": user, "system": system}

	####-----------------  the cpu values without what this process used ---------
	def cpuWithout(self, cpu, own):
		if cpu is None or own is None: return cpu
		user, system = max(0., cpu["user"] - own["user"]), max(0., cpu["system"] - own["system"])
		return {"busy": user + system, "user": user, "system": system}

	####-----------------  memory the way activity monitor counts it: app + wired + compressed, file cache is not "used" ---------
	def memory(self):
		out   = run(["/usr/bin/vm_stat"])
		pages = {}
		pageSize = 16384
		for line in out.split("\n"):
			if line.find("page size of") > -1:
				try:	pageSize = int(line.split("page size of")[1].split()[0])
				except Exception: pass
				continue
			if ":" not in line: continue
			key, val = line.rsplit(":", 1)
			try:	pages[key.strip().strip('"')] = int(val.strip().strip("."))
			except Exception: pass
		try:
			total = int(run(["/usr/sbin/sysctl", "-n", "hw.memsize"]).strip())
			app   = max(0, pages["Anonymous pages"] - pages.get("Pages purgeable", 0))
			used  = (app + pages["Pages wired down"] + pages["Pages occupied by compressor"]) * pageSize
		except Exception:
			return None
		return {"total": total, "used": min(used, total), "wired": pages["Pages wired down"] * pageSize, "compressed": pages["Pages occupied by compressor"] * pageSize}

	####-----------------  swap in MB, memory pressure normal / warning / critical, seconds since boot ---------
	def system(self):
		res = {"swapUsedMB": None, "pressure": None, "uptime": None}
		lines = run(["/usr/sbin/sysctl", "-n", "vm.swapusage", "kern.memorystatus_vm_pressure_level", "kern.boottime"]).strip("\n").split("\n")
		try:
			used = lines[0].split("used =")[1].split()[0]
			res["swapUsedMB"] = float(used.rstrip("MGK")) * (1024. if used.endswith("G") else 1.)
		except Exception: pass
		try:	res["pressure"] = {"1": "normal", "2": "warning", "4": "critical"}.get(lines[1].strip(), lines[1].strip())
		except Exception: pass
		try:	res["uptime"] = time.time() - int(lines[2].split("sec =")[1].split(",")[0])
		except Exception: pass
		return res

	####-----------------  mounted volumes and, of them, the Time Machine snapshot browse mounts: macOS checks an authorization for every
	####-----------------  mounted volume twice a minute and authd (the service that does it) leaks memory with every check ---------
	def mounts(self):
		lines = [line for line in run(["/sbin/mount"]).split("\n") if line.strip() != ""]
		if len(lines) == 0: return None
		return {"total": len(lines), "timeMachine": sum(1 for line in lines if "/Volumes/.timemachine/" in line)}

	####-----------------  resident memory of authd in MB; the full path is matched so coreauthd, akd .. do not count ---------
	def authdMemMB(self):
		for line in run(["/bin/ps", "-axo", "rss=,comm="]).split("\n"):
			items = line.strip().split(None, 1)
			if len(items) == 2 and items[1].endswith("/authd.xpc/Contents/MacOS/authd"):
				try:	return float(items[0]) / 1024.
				except Exception: return None
		return None

	####-----------------  apps macOS denies Local Network / multicast access (DenyMulticast=true in the consent store) ---------
	####-----------------  a denied app (e.g. an Indigo server) cannot reach the LAN: multicast and TCP/UDP to local
	####-----------------  devices fail with errno 65 while the internet still works. Read-only, no sudo; if the file is
	####-----------------  not readable the result says so. plutil -convert json -o - prints to stdout, never writes the file.
	def multicastDenied(self):
		# The file is an NSKeyedArchiver archive ($objects + CF$UID refs), read with plistlib (plutil
		# -convert json fails on it - it holds data/date objects). Each rule object carries a
		# SigningIdentifier (bundle id, e.g. com.apple.Terminal) / Path and a DenyMulticast bool.
		path = "/Library/Preferences/com.apple.networkextension.plist"
		res = {"readable": False, "denied": [], "allowed": 0, "note": ""}
		try:
			if not os.path.exists(path):
				res["note"] = "no consent store file"
				return res
			with open(path, "rb") as f:
				data = plistlib.load(f)
			objs = data.get("$objects")
			if not isinstance(objs, list):
				res["note"] = "unexpected plist format"
				return res
			res["readable"] = True
			def val(u):
				try:    return objs[u.data] if isinstance(u, plistlib.UID) else u
				except Exception: return u
			skip   = {"$null", "", "PathRuleDefaultNonSystemIdentifier", "PathRuleDefaultSystemIdentifier"}
			denied = []
			allowed = 0
			for o in objs:
				if isinstance(o, dict) and "DenyMulticast" in o:
					sid = val(o.get("SigningIdentifier"))
					p   = val(o.get("Path"))
					ident = sid if (isinstance(sid, str) and sid not in skip) else (p if isinstance(p, str) and p not in ("$null", "") else None)
					if ident is None: continue        # skip the generic default-rule objects
					if bool(val(o.get("DenyMulticast"))): denied.append(ident)
					else: allowed += 1
			res["denied"]  = sorted(set(denied))
			res["allowed"] = allowed
		except PermissionError:
			res["note"] = "not readable (needs sudo)"
		except Exception as e:
			res["note"] = "read error: {}".format(e)
		return res

	####-----------------  LIVE multicast test: can THIS process send a multicast datagram right now? This is the
	####-----------------  operation macOS Local Network blocks first (errno 65). Authoritative for the running
	####-----------------  process, unlike the stored DenyMulticast policy which can lag / be stale. ---------
	def multicastTest(self):
		s = None
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
			try:    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
			except Exception: pass
			s.sendto(b"\x00", ("224.0.0.251", 5353))
			return {"ok": True, "errno": None}
		except Exception as e:
			return {"ok": False, "errno": getattr(e, "errno", None)}
		finally:
			if s is not None:
				try:    s.close()
				except Exception: pass

	####-----------------  startup volume ---------
	def disk(self):
		for path in ("/System/Volumes/Data", "/"):
			try:
				st    = os.statvfs(path)
				total = st.f_blocks * st.f_frsize
				free  = st.f_bavail * st.f_frsize
				if total <= 0: continue
				return {"total": total, "free": free, "usedPct": (total - free) * 100. / total}
			except Exception:
				continue
		return None

	####-----------------  bytes in / out since boot, summed over the interfaces; no names given = all en* (ethernet, wifi) ---------
	def bridgeMembers(self):
		members = set()
		for line in run(["/sbin/ifconfig", "-a"]).split("\n"):
			line = line.strip()
			if line.startswith("member:"):
				try:	members.add(line.split()[1])
				except Exception: pass
		return members

	####-----------------  no names given = the en* interfaces that are not a member of a bridge (their traffic is counted by the bridge,
	####-----------------  e.g. the thunderbolt link between two macs), if there are none the members too ---------
	def netCounters(self, interfaces=None):
		if not interfaces:
			res = self._netCounters(None, self.bridgeMembers())
			if res is not None: return res
		return self._netCounters(interfaces, set())

	def _netCounters(self, interfaces, skip):
		lines = run(["/usr/sbin/netstat", "-ibn"]).strip("\n").split("\n")
		if len(lines) < 2: return None
		header = lines[0].split()
		try:
			iIn  = header.index("Ibytes") - len(header)
			iOut = header.index("Obytes") - len(header)
		except ValueError:
			return None
		bytesIn = bytesOut = 0
		found   = False
		for line in lines[1:]:
			items = line.split()
			if len(items) < len(header) - 1 or items[2].find("<Link#") != 0: continue   # one counter row per interface
			name = items[0].rstrip("*")
			if interfaces:
				if name not in interfaces: continue
			elif not (name.startswith("en") and name[2:].isdigit()) or name in skip:
				continue
			try:
				bytesIn  += int(items[iIn])
				bytesOut += int(items[iOut])
				found = True
			except Exception:
				continue
		if not found: return None
		return (bytesIn, bytesOut)

	####-----------------  rates in kbyte/sec between two readings ---------
	def netRates(self, old, new, secs):
		if old is None or new is None or secs <= 0: return None
		return {"in": max(0, new[0] - old[0]) / 1024. / secs, "out": max(0, new[1] - old[1]) / 1024. / secs}

	####-----------------  all processes: pid -> name, cpu seconds used so far, age, memory, ps %cpu ---------
	def processes(self):
		procs = {}
		for line in run(["/bin/ps", "-A", "-c", "-o", "pid=,ppid=,pcpu=,etime=,time=,rss=,comm="]).split("\n"):
			items = line.split(None, 6)
			if len(items) < 7: continue
			try:
				procs[items[0]] = {"name": items[6].strip(), "ppid": items[1], "cpuSecs": hmsToSecs(items[4]), "age": hmsToSecs(items[3]), "pcpu": float(items[2]), "rss": int(items[5])}
			except Exception:
				continue
		## every indigo plugin runs in its own IndigoPluginHost3 process, only the command line tells which plugin: "... IndigoPluginHost3 -p1176 -fpiBeacon.indigoPlugin"
		if any(p["name"].startswith("IndigoPluginHost") for p in procs.values()):
			for line in run(["/bin/ps", "-A", "-o", "pid=,command="]).split("\n"):
				if line.find("IndigoPluginHost") == -1: continue
				items = line.split(None, 1)
				if len(items) < 2 or items[0] not in procs: continue
				m = re.search(r" -f(.+?)\.indigoPlugin", items[1])
				if m is None: m = re.search(r" -e(\S+)", items[1])
				if m is not None:
					procs[items[0]]["pluginFile"] = m.group(1)            # as in the Plugins folder, hidden plugins start with a .
					procs[items[0]]["plugin"]     = m.group(1).lstrip(".")
		return procs

	####-----------------  plugin id and version from the Info.plist of the plugin, read again when the file changes ---------
	def pluginInfo(self, pluginFile):
		if not self.indigoPath or not pluginFile: return None
		path = os.path.join(self.indigoPath, "Plugins", pluginFile + ".indigoPlugin", "Contents", "Info.plist")
		try:
			mtime = os.path.getmtime(path)
			if path in self.pluginCache and self.pluginCache[path][0] == mtime: return self.pluginCache[path][1]
			text = open(path, "r", encoding="utf-8").read()
			def value(key):
				t = text.split(key + "</key>")
				return t[1].split("</string>")[0].split("<string>")[1].strip() if len(t) > 1 and "<string>" in t[1].split("</string>")[0] else ""
			info = {"id": value("CFBundleIdentifier"), "version": value("PluginVersion")}
			self.pluginCache[path] = (mtime, info)
			return info
		except Exception:
			return None

	####-----------------  cpu use of every app between two process readings: dict key -> details; 100 = one full core as in top ---------
	# same name = one app, except plugin hosts: one per plugin, and the processes a plugin host started count to it (sub processes)
	def processUse(self, old, new, secs, skipSelf=False):
		if not new: return {}
		me     = str(os.getpid())
		skip   = set()
		kids   = {}
		pct    = {}
		for pid, p in new.items():
			if skipSelf and (pid == me or p.get("ppid") == me):        # this process and the commands it started
				skip.add(pid)
				continue
			kids.setdefault(p.get("ppid"), []).append(pid)
			if old is not None and secs > 0:
				if pid in old and old[pid]["name"] == p["name"] and p["cpuSecs"] >= old[pid]["cpuSecs"]:
					pct[pid] = (p["cpuSecs"] - old[pid]["cpuSecs"]) / secs * 100.
				elif p["age"] <= secs:         # started after the last reading: everything it used is new
					pct[pid] = p["cpuSecs"] / max(p["age"], 1.) * 100.
				else:
					pct[pid] = 0.
			else:
				pct[pid] = p["pcpu"]                 # no earlier reading: ps own short time average
		sub = {}                                   # plugin host pid -> pids of everything it started
		for pid, p in new.items():
			if pid in skip or "plugin" not in p: continue
			found, todo = [], list(kids.get(pid, []))
			while todo:
				k = todo.pop()
				if k in found or k == pid: continue
				found.append(k)
				todo.extend(kids.get(k, []))
			sub[pid] = found
		counted = set(k for found in sub.values() for k in found)
		use = {}
		for pid, p in new.items():
			if pid in skip or pid in counted: continue
			key = p["name"] + " " + p["plugin"] if "plugin" in p else p["name"]
			u   = use.setdefault(key, {"pct": 0., "n": 0, "pid": pid, "topPct": -1., "plugin": p.get("plugin"), "pluginFile": p.get("pluginFile"),
			                           "rss": 0, "cpuSecs": 0., "age": 0., "subN": 0, "subPct": 0.})
			mine = pct.get(pid, 0.)
			subPct = sum(pct.get(k, 0.) for k in sub.get(pid, []))
			u["pct"]    += mine + subPct
			u["n"]      += 1
			u["rss"]    += p.get("rss", 0) + sum(new[k].get("rss", 0) for k in sub.get(pid, []))
			u["subN"]   += len(sub.get(pid, []))
			u["subPct"] += subPct
			if mine + subPct > u["topPct"]:         # age and cpu time are those of the busiest process of the app
				u["pid"], u["topPct"], u["age"] = pid, mine + subPct, p["age"]
				u["cpuSecs"] = p["cpuSecs"] + sum(new[k]["cpuSecs"] for k in sub.get(pid, []))
		return use

	####-----------------  average of several readings of processUse, an app that was not busy in a reading counts 0 there ---------
	def mergeUse(self, uses):
		total = sum(secs for use, secs in uses) or 1.
		merged = {}
		for use, secs in uses:
			for key, u in use.items():
				m = merged.setdefault(key, dict(u, pct=0., subPct=0.))
				m.update({k: v for k, v in u.items() if k not in ("pct", "subPct")})    # the details of the last reading
				m["pct"]    += u["pct"] * secs / total
				m["subPct"] += u["subPct"] * secs / total
		return merged

	####-----------------  the n busiest: [(label, percent, details)], label = name [xN processes] [pid of the busiest] ---------
	def topEntries(self, use, n=3):
		out = [(key + (" x{}".format(u["n"]) if u["n"] > 1 else "") + " [{}]".format(u["pid"]), u["pct"], u) for key, u in use.items()]
		return sorted(out, key=lambda x: -x[1])[:n]

	def topProcesses(self, old, new, secs, n=3, skipSelf=False):
		return [(label, pct) for label, pct, u in self.topEntries(self.processUse(old, new, secs, skipSelf), n)]

	####-----------------  seconds as 3 min / 5 h 20 min / 1 d 11 h ---------
	def upText(self, secs):
		secs = int(secs)
		if secs < 120:   return "{} sec".format(secs)
		if secs < 7200:  return "{} min".format(secs // 60)
		if secs < 172800: return "{} h {} min".format(secs // 3600, (secs % 3600) // 60)
		return "{} d {} h".format(secs // 86400, (secs % 86400) // 3600)

	####-----------------  the busy apps as a table, one line each, columns lined up:  name [pid]  cpu  average since start  memory  run time  plugin id, version, sub processes ---------
	def describeTable(self, entries, indent="      "):
		rows = []
		for label, pct, u in entries:
			avg = u["cpuSecs"] / u["age"] * 100. if u["age"] > 0 else None
			extra = []
			info = self.pluginInfo(u.get("pluginFile")) if u.get("plugin") else None
			if info and (info["id"] or info["version"]): extra.append((info["id"] + " v" + info["version"]).strip())
			if u["subN"] > 0: extra.append("incl. {} sub process{} {:.0f}%".format(u["subN"], "" if u["subN"] == 1 else "es", u["subPct"]))
			rows.append((label, "{:.0f}%".format(pct), "" if avg is None else "avg " + ("{:.1f}%" if avg < 10 else "{:.0f}%").format(avg),
			             "{:,.0f} MB".format(u["rss"] / 1024.) if u["rss"] > 0 else "", "up " + self.upText(u["age"]) if u["age"] > 0 else "", "; ".join(extra)))
		if not rows: return []
		w = [max(len(r[i]) for r in rows) for i in range(6)]
		out = []
		for r in rows:
			out.append((indent + "{:<{w0}}  {:>{w1}}  {:>{w2}}  {:>{w3}}  {:<{w4}}  {}".format(r[0], r[1], r[2], r[3], r[4], r[5], w0=w[0], w1=w[1], w2=w[2], w3=w[3], w4=w[4])).rstrip())
		return out
