#!/bin/sh
# Health check for the "Integrated Camera" virtual webcam. Needs no root.
# Opens the camera for a few seconds (the camera LED comes on) and reports
# the frame rate and whether the frames contain a real picture.
set -u

LABEL="Integrated Camera"
UNIT=v4l2-relayd@integrated-camera.service
SECONDS_TO_MEASURE=${1:-8}
rc=0

say() { printf '%-28s %s\n' "$1" "$2"; }

# 1. Kernel side
if ls /sys/bus/i2c/devices/ 2>/dev/null | grep -q OVTI08F4; then
    say "sensor (ov08x40):" "present"
else
    say "sensor (ov08x40):" "MISSING - is linux-modules-vision-generic installed?"; rc=1
fi

# 2. Relay service
state=$(systemctl is-active "$UNIT" 2>/dev/null)
say "relay service:" "$state"
[ "$state" = active ] || rc=1

# 3. Virtual device
DEV=""
for n in /sys/devices/virtual/video4linux/*/name; do
    [ -e "$n" ] && [ "$(cat "$n")" = "$LABEL" ] && DEV=/dev/$(basename "$(dirname "$n")")
done
if [ -n "$DEV" ]; then
    say "virtual device:" "$DEV"
else
    say "virtual device:" "MISSING - is v4l2loopback loaded?"
    exit 1
fi

# 4. PipeWire
if command -v pw-dump >/dev/null 2>&1; then
    cams=$(pw-dump 2>/dev/null | grep '"node.description"' | grep -c "$LABEL")
    raw=$(pw-dump 2>/dev/null | grep '"node.description"' | grep -c 'ipu7')
    say "PipeWire camera nodes:" "$cams x '$LABEL', $raw x raw ipu7"
    if [ "$cams" != 1 ] || [ "$raw" != 0 ]; then
        echo "    -> try: systemctl --user restart wireplumber pipewire pipewire-pulse"
        rc=1
    fi
fi

# 5. Frames
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
timeout "$SECONDS_TO_MEASURE" v4l2-ctl -d "$DEV" --stream-mmap \
    --stream-count=100000 --stream-to="$TMP" >/dev/null 2>&1
python3 -I - "$TMP" "$SECONDS_TO_MEASURE" <<'EOF' || rc=1
import os, sys
path, secs = sys.argv[1], float(sys.argv[2])
frame = 1280 * 720 * 2                      # YUY2
n = os.path.getsize(path) // frame
if n == 0:
    print("%-28s %s" % ("frames:", "NONE - see: journalctl -b -u 'v4l2-relayd@*'"))
    sys.exit(1)
with open(path, "rb") as f:
    f.seek((n - 1) * frame)
    y = f.read(frame)[0::2][::53]           # luma samples of the last frame
lo, hi, mean = min(y), max(y), round(sum(y) / len(y))
fps = n / secs
print("%-28s %d in %.0f s (about %.0f fps)" % ("frames:", n, secs, fps))
print("%-28s min %d, max %d, mean %d" % ("last frame brightness:", lo, hi, mean))
ok = True
if hi - lo <= 20:
    print("    -> the picture is uniform (black?)"); ok = False
if fps < 20:
    print("    -> the frame rate is too low"); ok = False
sys.exit(0 if ok else 1)
EOF

if [ "$rc" = 0 ]; then echo "RESULT: OK"; else echo "RESULT: PROBLEM"; fi
exit "$rc"
