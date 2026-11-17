#!/bin/sh
# Install the "Integrated Camera" virtual webcam for the Dell Pro 14 Premium
# (Intel IPU7 + OV08X40) on Ubuntu 26.04. See README.md for the background.
#
# Run as your normal user:   ./install.sh
# It calls sudo for the system-wide parts.
#
# Testing aids:
#   DESTDIR=/some/dir  write all files below that directory instead of /
#   DRY_RUN=1          print system commands instead of running them
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
DESTDIR=${DESTDIR:-}
DRY_RUN=${DRY_RUN:-}
UNIT=v4l2-relayd@integrated-camera.service
DROPIN=/etc/systemd/system/v4l2-relayd@.service.d
PACKAGED_UNIT=${PACKAGED_UNIT:-/usr/lib/systemd/system/v4l2-relayd@.service}
WP_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/wireplumber/wireplumber.conf.d

if [ "$(id -u)" = 0 ] && [ -z "$DESTDIR" ]; then
    echo "Run this as your normal user, not with sudo." >&2
    exit 1
fi

# With DESTDIR set, nothing needs root.
if [ -n "$DESTDIR" ]; then SUDO=""; else SUDO="sudo"; fi

run() {  # run a system command, or print it in dry-run mode
    if [ -n "$DRY_RUN" ]; then echo "  [dry-run] $*"; else "$@"; fi
}

put() {  # put <source file> <absolute target path>   (system file)
    $SUDO install -D -m 644 "$1" "$DESTDIR$2"
    echo "  installed $2"
}

echo "== 1/5 Packages"
run $SUDO apt-get install -y \
    linux-modules-vision-generic \
    v4l2-relayd v4l-utils \
    gstreamer1.0-libcamera gstreamer1.0-plugins-good gstreamer1.0-plugins-extra

echo "== 2/5 System configuration"
put "$HERE/config/modprobe.d/v4l2-relayd.conf" /etc/modprobe.d/v4l2-relayd.conf
put "$HERE/config/v4l2-relayd.d/integrated-camera.conf" /etc/v4l2-relayd.d/integrated-camera.conf
put "$HERE/config/systemd/libcamera.conf" "$DROPIN/libcamera.conf"
put "$HERE/config/systemd/wait-gpu.conf" "$DROPIN/wait-gpu.conf"

# nosync.conf is the packaged ExecStart line with sync=false added to
# v4l2sink. It is generated from the installed unit so that it follows
# changes in the v4l2-relayd package.
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
if [ -r "$PACKAGED_UNIT" ]; then
    {
        echo "# v4l2sink must not sync to the clock: frames arrive a little after their"
        echo "# capture timestamp, so a syncing sink drops them as late (about 1 fps left)."
        echo "[Service]"
        echo "ExecStart="
        grep '^ExecStart=' "$PACKAGED_UNIT" |
            sed 's/v4l2sink name=v4l2sink device=/v4l2sink name=v4l2sink sync=false device=/'
    } > "$TMP"
    if ! grep -q 'sync=false' "$TMP"; then
        echo "ERROR: could not add sync=false; the packaged unit has changed:" >&2
        echo "  $PACKAGED_UNIT" >&2
        exit 1
    fi
    put "$TMP" "$DROPIN/nosync.conf"
else
    echo "  skipped nosync.conf: $PACKAGED_UNIT not found (dry run without the package?)"
fi

echo "== 3/5 PipeWire configuration (per user)"
mkdir -p "$DESTDIR$WP_DIR"
for f in 50-disable-libcamera.conf 51-hide-ipu7-raw-nodes.conf; do
    install -m 644 "$HERE/config/wireplumber/$f" "$DESTDIR$WP_DIR/$f"
    echo "  installed $WP_DIR/$f"
done

echo "== 4/5 Starting the relay"
run $SUDO systemctl daemon-reload
run $SUDO systemctl stop "$UNIT"
run $SUDO modprobe -r v4l2loopback
run $SUDO modprobe v4l2loopback
run $SUDO systemctl enable v4l2-relayd.service
run $SUDO systemctl restart "$UNIT"

echo "== 5/5 Restarting PipeWire (sound drops out for a second)"
# PipeWire only notices the virtual camera once the relay is attached to it.
run sleep 2
run systemctl --user restart wireplumber pipewire pipewire-pulse

echo
echo "Done. If linux-modules-vision-generic was newly installed, reboot now."
echo "Then run ./check.sh, and choose 'Integrated Camera' in your apps."
