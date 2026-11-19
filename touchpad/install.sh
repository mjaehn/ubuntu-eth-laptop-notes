#!/bin/sh
# Install the Dell Collaboration Touchpad service for Zoom and Teams meetings.
# Tested on a Dell Pro 14 Premium with Ubuntu 26.04; see README.md for other
# laptops and distributions.
#
# Run as your normal user:   ./install.sh
# It calls sudo for packages and udev rules.
#
#   SKIP_PACKAGES=1  do not install packages (install them yourself first)
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
LIB=$HOME/.local/lib/dell-collab-touchpad
UNIT_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
RULE=/etc/udev/rules.d/70-dell-collab-touchpad.rules
UINPUT_RULE=/etc/udev/rules.d/70-dell-collab-touchpad-uinput.rules

if [ "$(id -u)" = 0 ]; then
    echo "Run this as your normal user, not with sudo." >&2
    exit 1
fi

echo "== 1/4 Touchpad"
# The kernel names the HID device bus:vendor:product.instance, e.g. 0018:0488:1083.0002
HID=$(python3 -I -c '
import glob, os
sig = bytes.fromhex("0680ff0980a1018516")
for n in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
    try:
        if sig in open(n + "/device/report_descriptor", "rb").read():
            print(os.path.basename(os.path.realpath(n + "/device")).rsplit(".", 1)[0])
            break
    except OSError:
        pass
')
if [ -z "$HID" ]; then
    echo "No Collaboration Touchpad found (HID usage page 0xFF80, report 0x16)." >&2
    exit 1
fi
echo "  found HID device $HID"

echo "== 2/4 Packages"
if [ -n "${SKIP_PACKAGES:-}" ]; then
    echo "  skipped (SKIP_PACKAGES set)"
elif command -v apt-get >/dev/null; then
    sudo apt-get install -y python3-evdev python3-gi gir1.2-atspi-2.0 wireplumber pulseaudio-utils
elif command -v dnf >/dev/null; then
    sudo dnf install -y python3-evdev python3-gobject at-spi2-core wireplumber pulseaudio-utils
elif command -v pacman >/dev/null; then
    sudo pacman -S --needed --noconfirm python-evdev python-gobject at-spi2-core wireplumber libpulse
else
    echo "Unknown package manager. Install the packages listed in README.md," >&2
    echo "then run again with SKIP_PACKAGES=1." >&2
    exit 1
fi

echo "== 3/4 udev rules"
sed "s/0018:0488:1083/$HID/" "$HERE/config/70-dell-collab-touchpad.rules" | sudo tee "$RULE" >/dev/null
echo "  installed $RULE"
if [ ! -w /dev/uinput ]; then
    echo 'KERNEL=="uinput", TAG+="uaccess"' | sudo tee "$UINPUT_RULE" >/dev/null
    echo "  installed $UINPUT_RULE (log out and in if keys do not reach Zoom)"
fi
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw --action=change
sudo udevadm trigger --subsystem-match=misc --sysname-match=uinput --action=change

echo "== 4/4 Service (per user)"
# Firefox exposes web pages over AT-SPI only with this flag (needed for Teams);
# it applies to apps started afterwards and persists across logins.
gsettings set org.gnome.desktop.interface toolkit-accessibility true 2>/dev/null || true
busctl --user set-property org.a11y.Bus /org/a11y/bus org.a11y.Status IsEnabled b true 2>/dev/null || true
echo "  enabled the desktop accessibility flag (restart Firefox once for Teams)"
install -D -m 644 "$HERE/collab_touchpad.py" "$LIB/collab_touchpad.py"
echo "  installed $LIB/collab_touchpad.py"
install -D -m 644 "$HERE/config/dell-collab-touchpad.service" "$UNIT_DIR/dell-collab-touchpad.service"
echo "  installed $UNIT_DIR/dell-collab-touchpad.service"
systemctl --user daemon-reload
systemctl --user enable dell-collab-touchpad.service
systemctl --user restart dell-collab-touchpad.service
sleep 2
systemctl --user --no-pager status dell-collab-touchpad.service | head -5

echo
echo "Done. The icons light up during Zoom meetings and Teams meetings in Firefox."
echo "For taps in Zoom, enable the global shortcuts in Zoom and your desktop"
echo "(see README.md)."
