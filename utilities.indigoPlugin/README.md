# utilities

Indigo plugin with a toolbox for maintaining the Indigo server itself. It prints what is inside your
Indigo installation (devices, variables, triggers, schedules, action groups, z-wave neighbors,
battery levels, running plugins), it queries and cleans up the **SQL logger database** (SQLite or
PostgreSQL), it backs up and repairs that database, it tracks the CPU used by Indigo and by every
plugin, and it reads the Mac's temperatures and fan speeds.

The plugin creates **no Indigo devices**. Everything is done from the plugin menu, from actions in
triggers/schedules/action groups, and through a handful of variables it writes.

- **Current version:** 2022.22.48 (2026-08-26)
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

**Ping an IP device** — pings an IP or hostname, result to the log.

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
