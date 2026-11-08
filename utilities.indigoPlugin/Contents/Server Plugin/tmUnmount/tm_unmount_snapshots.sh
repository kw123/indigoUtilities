#!/bin/bash
# Unmounts the Time Machine backup volumes that stay mounted under /Volumes/.timemachine/ after a backup.
# Run it by hand, in a terminal on the Mac that makes the backups:
#
#   sudo bash tm_unmount_snapshots.sh           unmounts them, shows each volume and how many are left
#   bash tm_unmount_snapshots.sh --dry          only shows what it would do (no sudo needed)
#
# Why: while Time Machine (backupd) makes a backup it can mount its old backups as volumes, one per backup, and may give
# them back only slowly. macOS checks an authorization for every mounted volume twice a minute and authd leaks memory with
# each check, so hundreds of mounts can make authd grow over the weeks. Which Macs and macOS versions do this varies.
#
# What it does:
#   - says what it found, also when nothing is mounted
#   - does nothing while a backup is running or when its state is unknown (tmutil status must say "Running = 0"), run it again later
#   - otherwise unmounts all of them, a few seconds each, and stops at once if a backup starts meanwhile
# Time Machine mounts them again when it needs them, and while they are not mounted the backups may not show up in the
# Time Machine window. Afterwards  sudo killall authd  gives the memory of authd back (a reboot does the same).

PATH=/usr/bin:/bin:/usr/sbin:/sbin
DRY=0
[ "$1" = "--dry" ] && DRY=1

say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*"; }

# mount points of the backup volumes (can contain spaces)
list() {
	/sbin/mount | sed -n 's/^.* on \(\/Volumes\/\.timemachine\/[^(]*\) (.*/\1/p' | sed 's/ *$//'
}

# true only when tmutil says that no backup is running
idle() {
	/usr/bin/tmutil status 2>/dev/null | grep -q "Running = 0"
}

[ "$DRY" = "1" ] || [ "$(id -u)" = "0" ] || { say "run it with sudo:  sudo bash $0   (or add --dry to only look)"; exit 1; }

MOUNTS="$(list)"
N=$(printf '%s\n' "$MOUNTS" | grep -c .)
if [ "$N" -eq 0 ]; then
	say "no Time Machine backup volumes are mounted, nothing to do"
	exit 0
fi

if ! idle; then
	say "a backup is running (or its state is unknown): $N backup volumes are mounted and left alone, run it again later"
	exit 0
fi

if [ "$DRY" = "1" ]; then
	say "dry run: $N backup volumes are mounted, no backup is running; it would unmount:"
	printf '%s\n' "$MOUNTS" | sed -n '1,5p;$p' | sed 's/^/    /'
	[ "$N" -gt 6 ] && echo "    (.. $((N - 6)) more between the first 5 and the last one)"
	exit 0
fi

say "$N Time Machine backup volumes are mounted, unmounting them (a few seconds each) .."
OK=0
I=0
STOPPED=""
while IFS= read -r m; do
	[ -z "$m" ] && continue
	# a backup may start while this runs: look again every 20 volumes
	if [ $((I % 20)) -eq 0 ] && [ "$I" -gt 0 ] && ! idle; then STOPPED=", stopped because a backup started"; break; fi
	I=$((I + 1))
	echo "$I/$N  $m"
	if /sbin/umount "$m" 2>/dev/null || /usr/sbin/diskutil unmount force "$m" >/dev/null 2>&1; then OK=$((OK + 1)); fi
done <<< "$MOUNTS"

LEFT=$(list | grep -c .)
say "unmounted $OK of $N Time Machine backup volumes, $LEFT left${STOPPED}"
exit 0
