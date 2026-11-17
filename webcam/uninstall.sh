#!/bin/sh
# Remove the "Integrated Camera" virtual webcam again. Run as your normal
# user; it calls sudo for the system-wide parts.
#
# linux-modules-vision-generic is left installed: it is the kernel driver the
# sensor needs in any case.
set -eu

UNIT=v4l2-relayd@integrated-camera.service
DROPIN=/etc/systemd/system/v4l2-relayd@.service.d
WP_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/wireplumber/wireplumber.conf.d

sudo systemctl stop "$UNIT" || true
sudo rm -f /etc/v4l2-relayd.d/integrated-camera.conf \
    "$DROPIN/libcamera.conf" "$DROPIN/nosync.conf" "$DROPIN/wait-gpu.conf" \
    /etc/modprobe.d/v4l2-relayd.conf
sudo apt-get purge -y v4l2-relayd
sudo modprobe -r v4l2loopback || true
sudo systemctl daemon-reload

rm -f "$WP_DIR/50-disable-libcamera.conf" "$WP_DIR/51-hide-ipu7-raw-nodes.conf"
systemctl --user restart wireplumber pipewire pipewire-pulse

echo "Removed. Note: with libcamera enabled in PipeWire again, opening the"
echo "camera can crash PipeWire until the sensor driver is fixed (see README.md)."
