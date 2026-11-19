#!/bin/sh
# Remove the Dell Collaboration Touchpad service again. Run as your normal
# user; it calls sudo for the udev rules. Packages are left installed.
set -eu

UNIT_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user

systemctl --user disable --now dell-collab-touchpad.service || true
rm -f "$UNIT_DIR/dell-collab-touchpad.service"
rm -rf "$HOME/.local/lib/dell-collab-touchpad"
systemctl --user daemon-reload

sudo rm -f /etc/udev/rules.d/70-dell-collab-touchpad.rules \
    /etc/udev/rules.d/70-dell-collab-touchpad-uinput.rules
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw --action=change

echo "Removed."
