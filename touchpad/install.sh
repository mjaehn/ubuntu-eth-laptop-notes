#!/bin/sh
# Install the Dell Collaboration Touchpad service for Zoom meetings on the
# Dell Pro 14 Premium (Ubuntu 26.04). See README.md for the background.
#
# Run as your normal user:   ./install.sh
# It calls sudo for the udev rule.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
LIB=$HOME/.local/lib/dell-collab-touchpad
UNIT_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
RULE=/etc/udev/rules.d/70-dell-collab-touchpad.rules

if [ "$(id -u)" = 0 ]; then
    echo "Run this as your normal user, not with sudo." >&2
    exit 1
fi

echo "== 1/3 Packages and udev rule"
sudo apt-get install -y python3-evdev python3-gi gir1.2-atspi-2.0 wireplumber pulseaudio-utils
sudo install -D -m 644 "$HERE/config/70-dell-collab-touchpad.rules" "$RULE"
echo "  installed $RULE"
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw --action=change

echo "== 2/3 Service files (per user)"
install -D -m 644 "$HERE/collab_touchpad.py" "$LIB/collab_touchpad.py"
echo "  installed $LIB/collab_touchpad.py"
install -D -m 644 "$HERE/config/dell-collab-touchpad.service" "$UNIT_DIR/dell-collab-touchpad.service"
echo "  installed $UNIT_DIR/dell-collab-touchpad.service"

echo "== 3/3 Starting the service"
systemctl --user daemon-reload
systemctl --user enable dell-collab-touchpad.service
systemctl --user restart dell-collab-touchpad.service
sleep 2
systemctl --user --no-pager status dell-collab-touchpad.service | head -5

echo
echo "Done. The icons light up during Zoom meetings. For camera, share and chat"
echo "taps, enable the global shortcuts in Zoom and KDE (see README.md)."
