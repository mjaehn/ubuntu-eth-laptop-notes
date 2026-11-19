#!/usr/bin/env python3
"""Drive the Dell Collaboration Touchpad icons for Zoom meetings on Linux.

While a Zoom meeting runs, the four icons are lit: camera and mic white when
on, red when off/muted. Taps send Zoom's global shortcuts (Alt+V, Alt+S, Alt+H,
Alt+A). Zoom's mute state is read from its mute button over AT-SPI; without
it, the mic icon and tap fall back to the system microphone mute.
"""
import glob, os, select, signal, subprocess, sys, time

import gi
from evdev import UInput, ecodes as e

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

RID = 0x16
LEVEL = int(os.environ.get("COLLAB_LEVEL", "3"))  # icon brightness 1..4
POLL = 1.0                                         # state check interval in s
REFRESH = 10.0                                     # resend LEDs at least this often (touchpad may reset on resume)
KEYS = {0x02: e.KEY_V, 0x04: e.KEY_S, 0x08: e.KEY_H}  # camera, share, chat -> Alt+key; mic -> Alt+A
MIC = 0x10

# Usage page 0xFF80, usage 0x80, collection, report ID 0x16: Dell's collaboration icon interface
SIGNATURE = bytes.fromhex("0680ff0980a1018516")


def find_hidraw():
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            desc = open(node + "/device/report_descriptor", "rb").read()
        except OSError:
            continue
        if SIGNATURE in desc:
            return "/dev/" + os.path.basename(node)
    sys.exit("No Collaboration Touchpad (HID usage page 0xFF80, report 0x16) found.")


def led_report(camera_on, mic_on, level=LEVEL):
    v = level << (0 if camera_on else 3)  # 0x20 white / 0x21 red
    v |= level << 6 | level << 9          # 0x22 share, 0x24 chat
    v |= level << (12 if mic_on else 15)  # 0x26 white / 0x27 red
    return bytes([RID]) + v.to_bytes(3, "little") + bytes([0x0F, 0])


OFF = bytes([RID, 0, 0, 0, 0, 0])


def procs(name):
    for comm in glob.glob("/proc/[0-9]*/comm"):
        try:
            if open(comm).read().strip() == name:
                yield os.path.dirname(comm)
        except OSError:
            pass


def meeting_active():
    # Zoom records from the microphone only while it is connected to meeting audio
    out = subprocess.run(["pactl", "list", "source-outputs"], capture_output=True, text=True).stdout
    return 'application.name = "ZOOM VoiceEngine"' in out


def camera_on():
    for p in procs("zoom"):
        for fd in glob.glob(p + "/fd/*"):
            try:
                if os.readlink(fd).startswith("/dev/video"):
                    return True
            except OSError:
                pass
    return False


def zoom_mute_button():
    """Return the text of Zoom's meeting toolbar mute button ("Mute" or "Unmute"), or None."""
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app is None or app.get_name() != "zoom":
            continue
        app.clear_cache()  # names change while Zoom runs; do not trust cached ones
        stack = [app.get_child_at_index(j) for j in range(app.get_child_count())]
        stack = [f for f in stack if f is not None and f.get_name() == "Meeting"]
        while stack:
            o = stack.pop()
            if o.get_name() in ("Mute", "Unmute") and o.get_role_name() in ("button", "push button"):
                return o.get_name()
            stack.extend(c for k in range(o.get_child_count()) if (c := o.get_child_at_index(k)) is not None)
    return None


def system_mic_on():
    out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"], capture_output=True, text=True).stdout
    return "MUTED" not in out


def mic_on():
    try:
        button = zoom_mute_button()
    except Exception:  # accessibility bus unavailable
        button = None
    return system_mic_on() if button is None else button == "Mute"


def press_alt(kbd, key):
    for code, value in ((e.KEY_LEFTALT, 1), (key, 1), (key, 0), (e.KEY_LEFTALT, 0)):
        kbd.write(e.EV_KEY, code, value)
        kbd.syn()


def main():
    dev = find_hidraw()
    fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
    kbd = UInput({e.EV_KEY: [e.KEY_LEFTALT, e.KEY_A, *KEYS.values()]}, name="dell-collab-touchpad")
    print(f"Using {dev}", flush=True)

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # the finally block switches the icons off

    sent, sent_at, next_poll = None, 0.0, 0.0
    try:
        while True:
            now = time.monotonic()
            if now >= next_poll:
                report = led_report(camera_on(), mic_on()) if meeting_active() else OFF
                if report != sent or (report != OFF and now - sent_at >= REFRESH):
                    os.write(fd, report)
                    sent, sent_at = report, now
                next_poll = now + POLL
            if not select.select([fd], [], [], max(0.0, next_poll - time.monotonic()))[0]:
                continue
            data = os.read(fd, 64)
            if len(data) < 2 or data[0] != RID or not data[1] or sent in (None, OFF):
                continue
            if data[1] & MIC:
                try:
                    in_zoom = zoom_mute_button() is not None
                except Exception:
                    in_zoom = False
                if in_zoom:
                    press_alt(kbd, e.KEY_A)
                else:
                    subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"])
            for bit, key in KEYS.items():
                if data[1] & bit:
                    press_alt(kbd, key)
            next_poll = 0.0  # show the new state at once
    finally:
        try:
            os.write(fd, OFF)
        except OSError:
            pass


if __name__ == "__main__":
    main()
