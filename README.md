# utilities

Indigo plugin with a toolbox for maintaining the Indigo server itself. It prints what is inside your
Indigo installation (devices, variables, triggers, schedules, action groups, z-wave neighbors,
battery levels, running plugins), it queries and cleans up the **SQL logger database** (SQLite or
PostgreSQL), it backs up and repairs that database, it tracks the CPU used by Indigo and by every
plugin, it reads the Mac's temperatures and fan speeds, and it can monitor the health of the Mac
itself with a **macOS health** device. A **sumMeters** device adds up the power, current and energy of other devices.

The plugin creates Indigo devices only if you add a **macOS health** or a **sumMeters** device (see below). Everything
else is done from the plugin menu, from actions in triggers/schedules/action groups, and through a
handful of variables it writes.

- **Current version:** 2022.22.66 (2026-11-08)
- **Author:** Karl Wachs
- **Plugin ID:** `com.karlwachs.utilities`
- **Indigo Server API:** 3.0
- **Forum / support:** http://forums.indigodomo.com/viewforum.php?f=164
- **Change log:** see `Contents/changelist.txt`

## Requirements

- Indigo with python 3. The plugin picks the first of
  `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`, `/usr/local/bin/python`,
  `/usr/bin/python2.7` for the background SQL job, and logs which one it uses.
- `/usr/bin/sqlite3` — ships with macOS, used for all SQLite work.
- PostgreSQL client (`psql`, `pg_dump`) — **only** if your SQL logger uses postgres.
- Optional: `/usr/local/bin/dot` (Graphviz) to turn the generated `zWave.dot` into `zWave.svg`.
- Optional: your Mac password in the plugin config — needed only for **powermetrics** and for the
  **reboot server** action, both of which run `sudo`.
- No third party python packages.

## Where it puts things

- `~/indigo/utilities/` — everything the plugin produces: printed output files, `steps` and
  `retcodes` (progress of the background SQL job), `backup.log`, `squeezeSQL`, `zWave.dot` / `.svg`,
  `timeStats.txt`
- `<Indigo>/logs/indigo_history-1.sqlite` … `-N.sqlite` — the SQLite backups
- `<Indigo>/logs/indigo_history-fixed.sqlite` — the repaired database
- `~/indigo/utilities/postgresBackup.zip` — the postgres dump, previous one kept as `.zip-1`
- `~/indigo/utilities/databases/` and `Preferences/` — the indigo config backup
- `<Indigo>/Logs/Plugins/com.karlwachs.utilities/plugin.log` — optional plugin logfile
- `<Indigo>/Preferences/Plugins/com.karlwachs.utilities/PLUGINSusedForCPUlimts.json` — CPU
  threshold settings

## Menu items

**Ping / test network access** — tests whether *Indigo itself* can reach a host and tells why not. Enter the IP address,
pick the kind of test (this is the kind of test, not the port) and press `EXECUTE`:

- **ping** (ICMP, `/sbin/ping`), the ping output goes to the log
- **TCP connect** to `IP:port` (the port field appears for TCP and UDP; common ports are listed below it)
- **UDP / multicast send** to `IP:port`, the operation macOS blocks first when *Local Network* access is denied (mDNS: `224.0.0.251:5353`)

The test runs inside the Indigo process, so it uses Indigo's own macOS *Local Network* permission (a test in Terminal has a
separate permission and cannot show the block). It also checks the public internet. Host not reachable but internet reachable
with a socket error 65 or 51 means the Local Network block: enable Indigo in *System Settings > Privacy & Security > Local
Network* and reboot. Internet not reachable either is a general network problem. The verdict goes to the log and to the
Status line of the dialog.

**Print Stuff to log** — one dialog with a `PRINT` button per item:

- Devices and variables, IDs and names
- States of all devices and all variable values
- z-wave neighbors, plus a Graphviz `zWave.dot` (and `zWave.svg` if `dot` is installed)
- All triggers with the device / variable / plugin that fires them
- Number of SQL records stored for each device and variable
- Plugin names, IDs, memory, CPU, average CPU, sub processes and non-standard open files
- `powermetrics` info
- Mac CPU and fan temperatures (not for M1 Macs)
- Reflector status
- Info for one selected device / schedule / trigger / action group
- Battery levels of all devices, sorted by name, by level, or only below a threshold
- Detailed info for **one** selected plugin — see below

**Retrieve (records) from SQLite/postGRES** — pick a variable, or a device and up to 9 of its
states, optionally with `=` / `!=` / `not NULL` conditions on the first two states, and print the
last N records (or from a starting id, or all) to the Indigo log or to a file in
`~/indigo/utilities/`. The last record also lands in the variables `SQLLineOutput` and
`SQLValueOutput` (folder `SQLoutput`, both created at startup).

**Create and test a backup of the SQLITE db** — copies the history database, runs a test query
against the copy, then rotates it in as `indigo_history-1.sqlite`, keeping as many copies as the
config says. Runs as a background job (`mkbackup.py`); progress goes to `~/indigo/utilities/steps`
and `backup.log`. A failed backup fires the **SQL backup not successful** event.

**Create dumpfile.zip of the postgres db** — `pg_dump` + `gzip`, restore instructions are printed
to the log.

**Create a backup of the indigo config files and config database.**

**Fix SQLITE db** (and **Fix … CANCEL job**) — copy → dump → repair the dump (drops records with a
broken index / duplicate timestamps) → rebuild into `indigo_history-fixed.sqlite` → test it. It does
not touch your live database; the log tells you how to swap the fixed file in. This can take about
an hour for an 8 GB database. **Disable the SQL logger first.**

**Delete duplicate records in SQL Database** — removes records that share the same `HH:MM:SS`
timestamp, keeping the last one of each second. Test mode writes the SQL to
`~/indigo/utilities/squeezeSQLall` without executing anything. **Disable the SQL logger first when
using SQLite.**

**Prune individual devices and variables in SQLlogger** — delete the history of one device or one
variable older than N days. Has a TEST button that only prints the SQL it would run.

## Device: macOS health

Add a device of type **macOS health** (model *utilities → macOS health*) to watch the Mac that runs
the Indigo server. It measures **every 5 minutes**. Each measurement is the **average of 2 readings
45 seconds apart** (cpu, network and busiest apps; memory, disk, load and mounts are read at the end) and it writes the result into device states, so they can be used in triggers,
control pages and the SQL logger. One device is enough; the plugin does nothing for this feature
while no such device exists. With the config option **create the "macOS health" device automatically**
(default on) the plugin creates one device named *Mac health* at start if there is none. Untick the
option if you delete the device and do not want it back.

| States | What it is |
|---|---|
| `cpuAvg`, `cpuUser`, `cpuSystem` | cpu busy / used by apps / used by the system, in **% of all cores**, average over the measure interval (from the kernel tick counters, so nothing is missed between two measurements) |
| `cpuMax` | highest cpu of the 15 second readings the plugin takes between two measurements, so a short spike is not averaged away |
| `cpuAvg24h`, `cpuMax24h` | average and max over the last 24 hours |
| `load1`, `load5`, `load15`, `cpuCores` | load average and number of cores |
| `memUsedPct`, `memUsedGB`, `memTotalGB` | memory used **as Activity Monitor counts it**: app + wired + compressed memory. File cache is not counted, so the value does not sit near 100% all the time like the `PhysMem` line of `top` |
| `memAvg24h`, `memMax24h` | average and max of `memUsedPct` over the last 24 hours |
| `memPressure`, `swapUsedMB` | the system memory pressure (`normal` / `warning` / `critical`) and swap in use |
| `diskUsedPct`, `diskFreeGB` | the startup disk |
| `netInKBps`, `netOutKBps` | network received / sent, average KB/s over the measure interval, all ethernet and wifi interfaces (`en0`, `en1`, ..) or the ones listed in the dialog |
| `netInMax24h`, `netOutMax24h` | the highest interval average of the last 24 hours |
| `bridgeInKBps`, `bridgeOutKBps`, `bridgeInMax24h`, `bridgeOutMax24h` | the same for the **thunderbolt bridge** (`bridge0`), the fast link between two Macs used for screen sharing or file copies. It is counted separately and not in the network states and limits above, so a screen sharing session does not trip the network limits. The states exist only if the bridge exists |
| `topProcName`, `topProcCpu`, `topProcList` | the app with the highest cpu use in the interval, its cpu in **% of one core** (100 = one full core, as in `top`), and the top 3 as `WindowServer 42%, Indigo 26%, ..`. All processes with the same name count as one app, so the many helpers of a browser add up. The cpu is the cpu time each process used since the last measurement, not a momentary `%CPU` |
| `mountCount`, `tmSnapshotMounts`, `authdMemMB` | mounted volumes, how many of them are Time Machine snapshot volumes (`/Volumes/.timemachine/..`), and the resident memory of macOS' `authd` in MB (see *authd leak* below) |
| `uptimeHours` | hours since the Mac was started |
| `localNetworkMulticast` | **live** test each measurement: whether the Indigo process can send multicast right now — `ok` or `blocked (errno 65)`. This is the authoritative "can Indigo reach the LAN" signal (see *Local Network / multicast* below) |
| `multicastDeniedCount`, `multicastDeniedApps` | the **stored** macOS consent policy: how many apps have `DenyMulticast=true`, and Indigo's own ids if they are among them. Informational — the stored policy can lag the live state |
| `healthStatus`, `warnings`, `lastMeasured` | `starting` / `ok` / `warning`, which limits are exceeded (`cpu`, `mem`, `disk`) and when the last measurement ran |

The schedule is fixed: a cycle starts every 5 minutes with a first set of readings, 45 seconds later
the first reading is taken (what happened in these 45 seconds), 45 seconds after that the second one, and the
states show the average of the two. The first measurement is shown about 90 seconds after the device starts.
`cpuMax` still covers the whole 5 minutes (the cpu is read every 15 seconds in between). The 24 hour values are kept in memory and
start again after the plugin restarts.

### Limits

Tick **Print a warning to the log when a limit is exceeded** in the device dialog and fill in any of
the limits below. A field left empty is not checked. All fields are always visible in the dialog.

| Warning when .. | Unit |
|---|---|
| CPU average over the measure interval is above | % of all cores |
| CPU max (peak of the 15 second readings) is above | % of all cores |
| the busiest app uses more than | % of one core (100 = one core) |
| load average (5 min) is above | load |
| memory used is above | % |
| memory pressure reaches | `warning` (or `critical`) / `critical` |
| swap used is above | MB |
| startup disk used is above | % |
| startup disk free is below | GB |
| network in / network out (average of the 2 readings) is above | Mb/s (megabit per second; 1 Mb/s = 122 KByte/s) |
| mounted volumes is above (suggested 60) | number |
| Time Machine snapshot volumes mounted is above (suggested 20) | number |
| authd memory is above (suggested 500) | MB |

A limit is reported only when it is exceeded at two measurements in a row, so a single short peak gives no warning (with a 5 min window that means about 5 to 10 minutes). The warning is then printed at every measurement while the value stays beyond its limit, the cpu warnings
name the busiest apps, and a normal log line tells you when the value is back within the limit.
`healthStatus` is `warning` meanwhile, `warnings` lists the limits, and the device icon turns to the
tripped state, so a trigger on *device state changed* can send a notification as well.

```
macOsHealth 'Mac health': CPU average 93 % is above the limit of 90 % (average of 2 readings of 45 sec each)
    busiest apps:
      python3 [4711]                          720%  avg 3.1%  412 MB  up 2 h 5 min
      IndigoPluginHost3 piBeacon [27541]       31%  avg 2.0%  412 MB  up 1 d 11 h  com.karlwachs.piBeacon v2026.1.3; incl. 1 sub process 4%
      Chrome Helper x6 [2208]                  26%  avg 1.1%  1,950 MB  up 3 h 2 min
macOsHealth 'Mac health': memory used 91 % is above the limit of 90 %;  58.2 of 64 GB, pressure warning
```

In the busiest apps list the number in brackets is the process id (use it in Activity Monitor or `top -pid`). Processes with the same name are added up as one app, written `name xN [pid]` with N processes and the pid of the busiest one. Every Indigo plugin runs in its own `IndigoPluginHost3` process (the 3 is the Indigo plugin API version, not a counter), so these are listed one by one with the plugin name, e.g. `IndigoPluginHost3 piBeacon [27541] 30%`.

What the busiest apps entries tell (the same for every app, plugin hosts get the first two items too):

- `com.karlwachs.piBeacon v2026.1.3` plugin id and installed version, read from the `Info.plist` of the plugin.
- `average since start` the cpu the app used on average since it started: 30% now against 2% on average is a burst, 30% against 28% is its normal load.
- memory (real MB) and `up` its run time: a plugin that was just restarted shows `up 3 min`.
- `incl. N sub processes` the processes a plugin started (python, ping, ssh, ..) are added to the plugin, they are not listed as separate apps.
- the detailed report for all plugins, including their open files, stays in the menu *Print plugin id, names, cpu, ...*.

### In the device dialog

- The dialog explains every state in its own section.
- The **Print states** button writes all states of the saved device to the log, grouped (status, CPU,
  memory, disk, network, busiest apps), with unit and meaning, followed by the limits next to the
  current values. Save changes with OK first; the button shows the saved device.

### Which network interfaces are counted

- **Network states** (`netInKBps`, ..): by default all `en*` interfaces (ethernet, wifi) that are **not a member of a bridge**.
  Interfaces that belong to a bridge (for example `en2`..`en4` of the thunderbolt bridge `bridge0`) are left out because their
  traffic is counted by the bridge. The field *Network interfaces to add up* in the device dialog replaces this by a list you
  give, e.g. `en0`. Local traffic (`lo0`: the Indigo server talking to its plugin processes, MQTT, ..) is never counted
  unless you list `lo0` - it is often several MB/s on an Indigo Mac and is not network load.
- **Bridge states** (`bridgeInKBps`, ..): the interfaces in the field *Bridge (thunderbolt link) to count separately*,
  default `bridge0`; empty = off.

### authd leak (many mounted Time Machine backup volumes)

macOS checks an authorization for **every mounted volume twice a minute**, and its service `authd` leaks a
few hundred bytes with every check, so `authd` can grow over the weeks (an Indigo Mac with 297 mounts reached 22 GB after
68 days, a Mac with 81 mounts 8.7 GB). On a Mac that backs up to Time Machine the many mounts can come from Time Machine
itself: while it makes a backup it can mount its old backups as volumes (`/Volumes/.timemachine/<disk>/<date>.backup`, one per
backup) and may give them back only slowly. Whether that happens, and how fast, depends on the macOS version, on the number of
backups and on the destination disks. Example, measured on one Indigo Mac (macOS 26, two Time Machine disks, hourly backups):
about 100 volumes per minute during a backup, 300 after 3 minutes, and a few per minute given back afterwards, so there were
always a few hundred. Normal for a Mac without Time Machine is a handful of mounts and `authd` in the tens of MB. The states are
`tmSnapshotMounts` (backup volumes), `mountCount` (all volumes, also disk images and network shares) and `authdMemMB` (resident
size, it understates the real size once the pages are compressed). The measurement is one `/sbin/mount` and one `ps` per
measurement, no `sudo`.

**Device edit, "Time Machine backup volumes"** (explained there as well):

| choice | what the plugin does |
|---|---|
| **watch authd only** (default, recommended) | no warning for the number of mounted volumes (mount count and snapshot limits are not checked), only when `authd` is above its limit (500 MB). That first warning says how many backup volumes are mounted and gives the commands to unmount them by hand. |
| warn when more volumes than the limits are mounted | also warns at the two volume limits (dialog defaults 60 and 20). Set them above the number that is normal on this Mac, if Time Machine mounts its backups that is the number of backups or more. |

The plugin never unmounts anything. Version 2022.22.62 and 2022.22.63 could do that automatically (a sudo rule and a
launchd job); that was removed again, the volumes are only unmounted by hand. A device that had the old box or the removed
third choice is treated as "watch authd only".

**By hand.** The commands are short, so they can be copied from the log. In a terminal on the Mac that makes the backups:

```
sudo bash "/Library/Application Support/Perceptive Automation/Indigo 2026.1/Plugins/utilities.indigoPlugin/Contents/Server Plugin/tmUnmount/tm_unmount_snapshots.sh"
sudo killall authd
```

The first line starts the script `tmUnmount/tm_unmount_snapshots.sh`: it says what it found (also when nothing is mounted),
does nothing while a backup is running (run it again later), otherwise it unmounts all `/Volumes/.timemachine/*` volumes,
shows each one (`3/109 ..`) and ends with `unmounted 109 of 109 Time Machine backup volumes, 0 left`. About 5 seconds
per volume (on the example Mac 100 volumes took about 9 minutes). While the volumes are not mounted the backups may not show up
in the Time Machine window, Time Machine mounts them again when it needs them. `bash tm_unmount_snapshots.sh --dry` only shows what it would do and needs
no `sudo`. The second line gives the memory of `authd` back, a reboot does the same. The device option **Expert advice on/off**
(default on) switches the advice text in the warnings off.

### Local Network / multicast

macOS gates **Local Network** access per app. When an app (here the Indigo server / plugin host) is denied, its
**multicast and TCP/UDP to local devices fail with errno 65** while the public internet still works — so a plugin
like Hue Lights suddenly cannot reach its bridge, usually right after a macOS or Indigo upgrade.

Each measurement the device does a **live multicast send from the Indigo process** and stores the result in
`localNetworkMulticast` (`ok` / `blocked (errno 65)`). Because it runs inside Indigo, this is authoritative for
what Indigo can actually reach — a test in Terminal has its own separate Local Network grant and cannot see the
block. With the device option **Warn when an app is denied Local Network (multicast)** (default on), the device
logs one warning when this flips to blocked (not every measurement), and a normal line when it recovers.

It also reads the stored consent store (`/Library/Preferences/com.apple.networkextension.plist`, an
NSKeyedArchiver archive, read-only, no `sudo`) into `multicastDeniedCount` / `multicastDeniedApps` for information.
**The stored `DenyMulticast=true` policy can lag the live state** — a Mac can list `com.perceptiveautomation.indigo-server`
as denied while the live send still succeeds — so the warning uses the live test, not the stored policy.

Fix when it is really blocked: **System Settings → Privacy & Security → Local Network**, enable Indigo, then
reboot. A stuck case (toggle and `tccutil reset` both failing) was resolved by updating to **macOS 27.2** and
answering the "allow access to local devices" prompt **yes**, which let the OS clear the block.

### Self reporting

Measuring costs a little cpu itself (the plugin process and the short commands `ps`, `vm_stat`, `netstat`,
.. it starts). With the device option **Self reporting** off (default) that cpu is taken out of `cpuAvg`,
`cpuUser`, `cpuSystem` and `cpuMax` (read from the process' own resource usage) and the plugin process and
its commands are not listed as busiest app, so the device reports the load of everything else. Other plugins
keep showing up even though they run in processes with the same name. Switch it on to count the plugin like
any other program.

### Indigo folder

In the plugin config, **DEVICES folder** (default `utilities`) is the Indigo folder the macOS health
devices are moved into when they are started and are not in a folder yet. The folder is created if
needed. A device you put into another folder yourself stays there; empty = never move.

The code that reads the Mac is in `Contents/Server Plugin/macHealth/macHealth.py`. It uses no
third party packages: cpu comes from `host_statistics` through ctypes, the rest from `vm_stat`,
`sysctl`, `netstat` and `ps`, about four short commands per measurement.

## Device: sumMeters

Adds up power, current (amps) and energy from other Indigo devices, for example the phases and channels of several energy meters. Any device with numeric states works, from any plugin.

### Setup

1. Create a new Indigo device, type *utilities*, model *sumMeters*.
2. For power, current and energy, choose how many sources to add (0–8, default 1) and the unit of the sum.
3. For each source, choose a device, one of its states and the unit that state is in. The state menu shows each state's current value. When you pick a device, a state with a matching name (power, current/amp, energy) is preselected. If the state name ends in a unit, such as `energy_kWh`, that unit is preselected too. A slot left without a device is skipped.
4. Choose which sum the device list shows, then save.

Units: power mW, W, kW; current mA, A; energy Ws (J), Wh, kWh, MWh. The defaults are W, A and Wh. Each source value is converted to the unit of its sum.

### States

| State | Meaning |
|---|---|
| `power1`…`power8`, `current1`…`current8`, `energy1`…`energy8` | source values, in the unit of the sum |
| `powerSum`, `currentSum`, `energySum` | the totals |
| `powerSumMinToday`, `powerSumMinTodayAt` | lowest sum today and when (same for current and energy) |
| `powerSumMaxToday`, `powerSumMaxTodayAt` | highest sum today and when |
| `powerSumAveToday` | time-weighted average since midnight: each value counts for as long as it lasted |
| `…Yesterday`, `…YesterdayAt` | the same for yesterday, moved over at midnight |
| `source_Power`, `source_Current`, `source_Energy` | source device ids in slot order, e.g. `1378652208, 51092918` |
| `lastSumUpdate` | time of the last update |

The plugin creates these states only for the kinds and slots in use: a sum of 3 power sources has `power1`…`power3`, `powerSum`, its statistics and `source_Power`, and no current or energy states. Change the sources and save, and the states follow. The checkbox *daily min / max / ave* under each kind turns its statistics states off.

After a plugin restart, today's values continue from the states.

### Updates

The sums update as soon as a source state changes. If nothing has changed for 5 minutes, the device rereads all sources and writes its states anyway, including `lastSumUpdate`. A source that is missing or not a number counts as 0, and the plugin logs a warning once.

### Sum of sums

A sumMeters device can be a source of another one, for example phases → floor → building → site. Picking a sumMeters device as a source preselects its `powerSum`, `currentSum` or `energySum` and its unit. Saving refuses a loop, such as A adding up B while B adds up A, and the message shows the loop. Don't add the same meter both directly and through a lower-level sum, or it is counted twice.

## Actions

- Stop Indigo Client
- Reboot Indigo Server (needs the Mac password; stops client and server, waits, then reboots)
- Print battery levels of devices to logfile
- Print MAC cpu and fan temperatures to log
- Print plugin id, names, cpu, … to logfile
- Create and test a backup of the SQLITE db
- Create dumpfile of the postgres db
- Create a backup of the indigo config files and config database
- squeezeDatabase / squeezeDatabaseQuiet (delete duplicate records, quiet = less log output)
- Select variable or device and state to be retrieved from SQLite/postGRES
- Prune individual devices and variables in SQLlogger

## Events (triggers)

- **SQL backup not successful** — fires when the background backup or fix job reports an error, or
  when the expected backup file was not created.
- **CPU of plugin consumption is over threshold** — pick a plugin and a limit in *CPU seconds per
  100 seconds*; the event fires when that plugin goes over. Plugins are added/removed in the event
  dialog and stored in `PLUGINSusedForCPUlimts.json`.

## CPU tracking

Switch **enable CPU tracking for Indigo + plugins** on in the config and the plugin checks every
100 seconds and maintains one variable per plugin, `CPU_usage_<shortPluginId>`, plus
`CPU_usage_AllIndigoAndPlugins` for the total. The unit is **CPU seconds per 100 seconds of real
time**, so 100 means one fully busy CPU core. Indigo server, client, web server, postgres, VBox and
fing are tracked alongside the plugins. Sub-process CPU is added to the plugin that started it.

The variables hold the **average since the process started** — the same number as `ave_cpu` in
*print plugin names…*. They used to hold the rolling 100-second rate, which read `0.00` for most
plugins: `ps` reports cpu time with a resolution of 0.01 seconds, so within one 100-second check the
smallest value that can appear at all is `0.01`, and a plugin that sleeps through the window really
does measure zero. The average has no such floor.

The **cpu threshold event** still uses that rolling 100-second rate, because it has to react to a
plugin going busy now, which a long average would hide.

### The plugin table

*Print Stuff → Plugin Names, IDs, mem, cpu…* prints, for every running plugin and its sub processes:

```
ave_cpu = cpu seconds used per 100 seconds of run time, average since the process started (same unit as the CPU_usage_.. variables; 100 = one full cpu core)
    PID  CPU-total   run-time     ave_cpu    Mem-%    Virtual    Real  version      pluginName -------------------------------
   unix   hh:mm:ss   hh:mm:ss  cpu/100sec    of MAC        MB      MB  installed    .. + sub processes and non std open files
   1222    0:40:06    3:51:12       17.35    1.3      425,656     853  2025.2.0     someplugin
    575    0:00:51    3:51:39        0.37    0.1      425,369      92               SubProcess: /usr/libexec/logd
                                                                                    openFile:/Users/xx/indigo/utilities/steps
```

- **CPU-total** — cpu time used since the process started, from the `TIME` column of `ps`.
  `ps` prints that as `mm:ss.ff` with unlimited minutes (3 hours of cpu reads `180:00.00`), the
  plugin converts it to `hh:mm:ss` so it can be compared with run-time. Less than a second of cpu
  therefore shows as `0:00:00`.
- **run-time** — how long the process has been running (`etime` from `ps`). Hours are not wrapped at
  24, a plugin up for four days shows `98:12:44`.
- **ave_cpu** — `CPU-total / run-time`, in cpu seconds per 100 seconds, so all three columns are
  visible side by side.

After the table the same plugins are listed again, **sorted by cpu usage, highest first**, so the
busiest one is easy to spot:

```
plugins sorted by cpu usage, highest first;  ave_cpu in cpu seconds per 100 seconds of run time
  ave_cpu   incl.sub   pluginName -------------------------------
    16.99              someplugin
     4.96              anotherplugin
     0.52       0.90   pluginWithHelpers
```

`incl.sub` is only filled in when the plugin has sub processes; it is the plugin plus everything it
started. Plugins with no run time yet sort to the bottom with an empty `ave_cpu`.

`ave_cpu` uses the same unit as the `CPU_usage_*` variables, but it is a **lifetime** average rather
than a rolling one. A plugin that is busy right now but idle most of the day will show a small
`ave_cpu` next to a large `CPU_usage_*` — that difference is real. The header is repeated at the end
of the list.

### Detailed info for one plugin

Pick a running plugin from the list at the bottom of *Print Stuff* and press PRINT. The plugin
samples that one plugin (and its sub processes) **every 2 seconds for 2 minutes**, then prints:

- cpu as **ave / max** in percent of one core (there is no cpu-min column: over a 2 second sample an
  idle moment is always found, so it was always 0.00), from `ps` %CPU, which covers roughly the last
  2 seconds per sample, so short bursts show up here that a long term average hides
- real and virtual memory, also ave / min / max
- one line **per process**: the plugin itself, then each of its sub processes sorted by cpu, then a
  TOTAL line. So a plugin that looks busy can be traced to the helper that is actually doing it:

```
    PID  cpu-ave  cpu-max   mem-ave mem-min mem-max    virt-ave   process ------------------
  12103     0.20     1.10        94      94      95      425097   demoPlugin   (the plugin itself)
  12105    10.30    10.40        12      12      12      425093   SubProcess: /usr/bin/python3 helper.py
  12108     0.00     0.00         1       1       1      425097   SubProcess: sleep 4   (ended during sampling)
  TOTAL    10.50    11.50       107     107     108     1275287   plugin + its sub processes
```

The TOTAL line is computed from the summed samples, not by adding up the per process ave/min/max, so
its min and max are the real minimum and maximum of the whole plugin. Sub processes are the ones that
existed when sampling started; one that ends in between is marked and keeps the samples it had.
- pluginId, version, api version, pid, number of sub processes, run time, total cpu, enabled/running
- **disk** bytes read and written over the window, total and per second, from `proc_pid_rusage`.
  Exact to the byte, no password needed, but only for processes of the same user — which plugins are.
- **network** bytes in and out, listed separately, total and per second, from `nettop`. No password needed
  either, but `nettop` only reports processes that had traffic while it sampled, so a plugin with a
  permanent connection (websocket, MQTT, SSH) is measured well while a short request that opens and
  closes in between can be missed. It costs about 5 seconds per call, so it is read once before and
  once after the window, never in the sampling loop.
- its **devices**: how many, how many enabled, then `id / type / enabled / name` and the full
  `pluginProps` per device
- its **triggers**: the indigo event triggers belonging to that plugin, same columns
- its **actions**: read from the plugin's own `Actions.xml`
- its **variables**: indigo does **not** record which plugin owns a variable (a variable record only
  has id, name, value, folder and readOnly — no owner, unlike devices and triggers). So instead the
  plugin reads the selected plugin's own python files and looks for `indigo.variable.create/
  updateValue/delete`, then works out what the name actually is:
  - a literal name is shown with its current value
  - a name held in a variable of the plugin (`self.var_name`) is followed to where it is set. If it
    comes from a config setting (`self.pluginPrefs.get("var_name", DEFAULTS["var_name"])`) the
    default from the code is used and the line says which setting it came from. If that name is not
    among the live variables the line says so — the setting was probably changed.
  - a name built from a prefix (`"CPU_usage_"+pluginId`) is shown with every live variable starting
    with that prefix
  - calls whose name comes from another object at runtime — `indigo.variable.updateValue(var.name…)`
    inside a loop — are counted in one summary line, because those are somebody else's variables
    that the plugin merely writes to, not variables of the plugin

The sampling runs in the plugin's own thread, so the two minutes are spent in the background — the
log line telling you it started appears immediately, the report follows when sampling is done. All
devices are listed, with their complete `pluginProps` — nothing is truncated, so for a plugin with
many devices this becomes a long log entry.

Picking a second plugin while one is being sampled is fine: requests are **queued** and run one after
the other, and the log tells you how many reports run before yours. Picking the same plugin twice does
not queue it twice. Each report ends with the list of plugins still waiting.

## Configuration

- **Debug** — Logic, SQL queries, or all. Logs can go to the Indigo log or to
  `<Indigo>/Logs/Plugins/com.karlwachs.utilities/plugin.log` (rotated at 100 kB, two old copies kept).
- **Time tracking** — set the Indigo variable `enableTimeTracking_utilities` to `on`, `off` or
  `print` (optionally `print-cumtime`, `print-calls`, …) to profile the plugin with cProfile.
  Results go to `~/indigo/utilities/timeStats.txt` / `.dump`.
- **Mac password** — only for `powermetrics` and the reboot action.
- **Store the passwords encrypted** (default on) — the Mac and postgres passwords are stored in the plugin
  prefs as `enc1:...` (HMAC-SHA256 keystream + authentication tag, key derived from this Mac's hardware
  UUID, standard library only), so they are not readable in the prefs file. The checkbox is the flag that
  says whether the stored passwords are encrypted: prefs of older versions have no flag, their plain
  text passwords keep working and are encrypted once at the first start. Untick it to store plain text
  again. The password fields show the stored value: leave it to keep the password, type a new one to
  replace it. Encrypted passwords only work on the Mac that made them (restoring the prefs on another
  Mac: enter them again; the log says so). The passwords are also masked (`*****`) in the commands the
  plugin writes to the log.
- **Locale language / character set** — used when running `ps`; match what `locale` prints in a
  terminal.
- **CPU tracking** — see above.
- **Mac temperature and fan speeds** — set an update interval and the plugin fills one variable per
  sensor reported by the bundled `osx-temp-fan` helper; °C or °F, with a configurable format.
- **SQL** — SQLite or postgres, the postgres command string, user id and password, whether to add
  `ORDER by id` (should be on for postgres), and the maximum length of a generated delete statement.
- **Backup** — how many backup copies to keep.

## Notes

- Before **Fix SQLITE db** or **Delete duplicate records** on SQLite, disable Indigo's SQL logger;
  the plugin refuses to start if it sees a running `sqlite3` process.
- Only one background SQL job (`mkbackup.py`) runs at a time; starting a second one is refused with
  a message in the log.
- The plugin restarts itself when time tracking is switched on or off, and when no usable python is
  found it stops with an error in the log.
