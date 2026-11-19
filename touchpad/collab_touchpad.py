#!/usr/bin/env python3
"""Drive the Dell Collaboration Touchpad icons for Zoom, Teams and Webex meetings on Linux.

While a meeting runs, the four icons are lit: camera and mic white when on, red
when off/muted. Zoom: taps send Zoom's global shortcuts (Alt+V, Alt+S, Alt+H,
Alt+A), and the mute state is read from its mute button over AT-SPI. Teams in
Firefox and Webex: state and taps go through the meeting buttons over AT-SPI.
Without a readable mute button, the mic icon and tap use the system mute.
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
CAMERA, SHARE, CHAT, MIC = 0x02, 0x04, 0x08, 0x10  # button bits in the input report
ZOOM_KEYS = {CAMERA: e.KEY_V, SHARE: e.KEY_S, CHAT: e.KEY_H, MIC: e.KEY_A}  # Alt+key
# Meeting button labels per icon; for camera and mic, the first label means "on"
LABELS = {
    "teams": {CAMERA: ("Turn camera off", "Turn camera on"), SHARE: ("Share",),
              CHAT: ("Chat",), MIC: ("Mute mic", "Unmute mic")},
    "webex": {CAMERA: ("Stop video", "Start video"), SHARE: ("Share",),
              CHAT: ("Open chat panel", "Hide chat panel, selected"), MIC: ("Mute", "Unmute")},
}

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


def active_app():
    """Return "zoom", "teams" or "webex" while that app records from the microphone, else None."""
    out = subprocess.run(["pactl", "list", "source-outputs"], capture_output=True, text=True).stdout
    streams = out.split("Source Output #")[1:]
    # Zoom opens this stream only while connected to meeting audio
    if any('application.name = "ZOOM VoiceEngine"' in s for s in streams):
        return "zoom"
    # Firefox names the stream after the tab title, which ends in "Microsoft Teams"
    if any('application.name = "Firefox"' in s and "Microsoft Teams" in s for s in streams):
        return "teams"
    if any('application.name = "WebexAudioCapture_' in s for s in streams):
        return "webex"
    return None


def procs(name):
    for comm in glob.glob("/proc/[0-9]*/comm"):
        try:
            if open(comm).read().strip() == name:
                yield os.path.dirname(comm)
        except OSError:
            pass


def zoom_camera_on():
    for p in procs("zoom"):
        for fd in glob.glob(p + "/fd/*"):
            try:
                if os.readlink(fd).startswith("/dev/video"):
                    return True
            except OSError:
                pass
    return False


def children(o):
    return [c for k in range(o.get_child_count()) if (c := o.get_child_at_index(k)) is not None]


def atspi_apps(name):
    for app in children(Atspi.get_desktop(0)):
        if app.get_name() == name:
            app.clear_cache()  # names change while the app runs; do not trust cached ones
            yield app


def zoom_mute_button():
    """Return the text of Zoom's meeting toolbar mute button ("Mute" or "Unmute"), or None."""
    for app in atspi_apps("zoom"):
        stack = [f for f in children(app) if f.get_name() == "Meeting"]
        while stack:
            o = stack.pop()
            if o.get_name() in ("Mute", "Unmute") and o.get_role_name() in ("button", "push button"):
                return o.get_name()
            stack.extend(children(o))
    return None


def teams_buttons(names):
    """Return Teams' meeting toolbar buttons in Firefox with these names, keyed by name."""
    docs, stack = [], [f for app in atspi_apps("Firefox") for f in children(app)]
    while stack:  # each tab, also in the background, is one "document web"
        o = stack.pop()
        if o.get_role_name() == "document web":
            if "Microsoft Teams" in (o.get_name() or ""):
                docs.append(o)
        else:
            stack.extend(children(o))
    found = {}
    while docs:
        o = docs.pop()
        # Plain buttons only: the "Chat" toggle button in the app sidebar opens the Chat app
        if o.get_name() in names and o.get_role_name() == "button":
            found[o.get_name()] = o
        docs.extend(children(o))
    return found


def webex_buttons(names):
    """Return Webex's meeting window buttons with these names, keyed by name."""
    found, stack = {}, [f for app in atspi_apps("Webex") for f in children(app) if f.get_name() != "Webex"]
    while stack:  # skips the main window "Webex"; the meeting window is named after the meeting
        o = stack.pop()
        if o.get_name() in names and o.get_role_name() in ("button", "push button"):
            found[o.get_name()] = o
        stack.extend(children(o))
    return found


FINDERS = {"teams": teams_buttons, "webex": webex_buttons}


def buttons(app):
    return safe(lambda: FINDERS[app]({n for names in LABELS[app].values() for n in names}), {})


def safe(f, default=None):
    try:
        return f()
    except Exception:  # accessibility bus unavailable or app window closed
        return default


def system_mic_on():
    out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"], capture_output=True, text=True).stdout
    return "MUTED" not in out


def toggle_system_mic():
    subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"])


def state(app):
    """Return (camera_on, mic_on) for the active app."""
    if app == "zoom":
        button = safe(zoom_mute_button)
        return zoom_camera_on(), system_mic_on() if button is None else button == "Mute"
    found, labels = buttons(app), LABELS[app]
    mic = labels[MIC][0] in found if set(labels[MIC]) & found.keys() else system_mic_on()
    return labels[CAMERA][0] in found, mic


def press_alt(kbd, key):
    for code, value in ((e.KEY_LEFTALT, 1), (key, 1), (key, 0), (e.KEY_LEFTALT, 0)):
        kbd.write(e.EV_KEY, code, value)
        kbd.syn()


def tap(app, bits, kbd):
    if app == "zoom":
        for bit, key in ZOOM_KEYS.items():
            if bits & bit:
                if bit == MIC and safe(zoom_mute_button) is None:
                    toggle_system_mic()
                else:
                    press_alt(kbd, key)
        return
    found = buttons(app)
    for bit, names in LABELS[app].items():
        if bits & bit:
            button = next((found[n] for n in names if n in found), None)
            if button is not None:
                safe(lambda: button.get_action_iface().do_action(0))
            elif bit == MIC:
                toggle_system_mic()


def main():
    dev = find_hidraw()
    fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
    kbd = UInput({e.EV_KEY: [e.KEY_LEFTALT, *ZOOM_KEYS.values()]}, name="dell-collab-touchpad")
    print(f"Using {dev}", flush=True)

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # the finally block switches the icons off

    app, sent, sent_at, next_poll = None, None, 0.0, 0.0
    try:
        while True:
            now = time.monotonic()
            if now >= next_poll:
                app = active_app()
                report = led_report(*state(app)) if app else OFF
                if report != sent or (report != OFF and now - sent_at >= REFRESH):
                    os.write(fd, report)
                    sent, sent_at = report, now
                next_poll = now + POLL
            if not select.select([fd], [], [], max(0.0, next_poll - time.monotonic()))[0]:
                continue
            data = os.read(fd, 64)
            if len(data) < 2 or data[0] != RID or not data[1] or app is None or sent in (None, OFF):
                continue
            tap(app, data[1], kbd)
            next_poll = 0.0  # show the new state at once
    finally:
        try:
            os.write(fd, OFF)
        except OSError:
            pass


if __name__ == "__main__":
    main()
