#!/usr/bin/env python3
"""Linux: try to light the Dell Collaboration Touchpad icons over hidraw.

Replays the protocol decoded from Dell Optimizer's CollaborationTouchpadPlugin.CTPAgent.dll
(see README.md). Stdlib only. Run as root (or with access to the hidraw node):

    sudo python3 collab_linux_test.py                 # all four icons on, brightness 4
    sudo python3 collab_linux_test.py --level 2 --seconds 60
    sudo python3 collab_linux_test.py --no-selector   # leave byte 4 at 0
    sudo python3 collab_linux_test.py --hb-with-leds  # heartbeat reports also carry the LED bits
"""
import argparse, glob, os, select, sys, time

RID = 0x16
REQUEST, HEARTBEAT, OVERRIDE = 0x04, 0x08, 0x10            # byte 3 flag bits (usages 0x30, 0x31, 0x32)
SEL = {"camera": 0x01, "share": 0x02, "chat": 0x04, "mic": 0x08}  # byte 4 (usages 1..4)


def find_hidraw():
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(node + "/device/uevent").read()
            desc = open(node + "/device/report_descriptor", "rb").read()
        except OSError:
            continue
        if "00000488:00001083" in uevent.upper() and b"\x06\x80\xff" in desc:
            return "/dev/" + os.path.basename(node)
    sys.exit("No hidraw node for 0488:1083 with usage page 0xFF80 found.")


def led_report(level, selector=True, flags=0):
    v = 0
    v |= level << 3    # usage 0x21: camera on      (0x20, bits 0-2: camera off)
    v |= level << 6    # usage 0x22: share screen
    v |= level << 9    # usage 0x24: chat
    v |= level << 15   # usage 0x27: mic unmuted    (0x26, bits 12-14: mic muted)
    v |= flags << 16   # 0x30/0x31/0x32 live at bits 18-20, i.e. byte 3 bits 2-4
    b = v.to_bytes(3, "little")
    sel = sum(SEL.values()) if selector else 0
    return bytes([RID, b[0], b[1], b[2], sel, 0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev")
    ap.add_argument("--level", type=int, default=4, help="LED value 0..4 (Optimizer uses its brightness setting)")
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--no-selector", action="store_true")
    ap.add_argument("--no-override", action="store_true")
    ap.add_argument("--hb-with-leds", action="store_true")
    ap.add_argument("--hb-period", type=float, default=0.5, help="also send a heartbeat every N s (0 = only on status reports)")
    ap.add_argument("--req-period", type=float, default=0, help="also send REQUEST every N s to keep status replies coming")
    a = ap.parse_args()

    dev = a.dev or find_hidraw()
    fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
    print("Using", dev)

    def send(rep, why):
        os.write(fd, rep)
        print(f"{time.strftime('%H:%M:%S')}  -> {rep.hex(' ')}  {why}")

    leds = led_report(a.level, not a.no_selector, 0 if a.no_override else OVERRIDE)
    hb = led_report(a.level, not a.no_selector, HEARTBEAT | (0 if a.no_override else OVERRIDE)) if a.hb_with_leds \
        else bytes([RID, 0, 0, HEARTBEAT, 0, 0])
    req = led_report(a.level, not a.no_selector, REQUEST | (0 if a.no_override else OVERRIDE)) if a.hb_with_leds \
        else bytes([RID, 0, 0, REQUEST, 0, 0])

    send(bytes([RID, 0, 0, REQUEST, 0, 0]), "REQUEST state")
    send(leds, "LEDs + selector + OVERRIDE")
    end, last_hb = time.time() + a.seconds, time.time()
    last_req = last_hb
    try:
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                data = os.read(fd, 64)
                note = ""
                if len(data) >= 3 and data[0] == RID:
                    st = data[2]
                    note = f"buttons={data[1]:08b} disable={st >> 7 & 1} enable={st >> 6 & 1} swipeoff={st >> 5 & 1}"
                print(f"{time.strftime('%H:%M:%S')}  <- {data.hex(' ')}  {note}")
                if data and data[0] == RID and data[1] == 0:
                    send(hb, "HEARTBEAT (reply to status)")
                    last_hb = time.time()
            if a.hb_period and time.time() - last_hb >= a.hb_period:
                send(hb, "HEARTBEAT (timer)")
                last_hb = time.time()
            if a.req_period and time.time() - last_req >= a.req_period:
                send(req, "REQUEST (timer)")
                last_req = time.time()
    finally:
        os.write(fd, bytes([RID, 0, 0, 0, 0, 0]))  # icons off, override released
        os.close(fd)


if __name__ == "__main__":
    main()
