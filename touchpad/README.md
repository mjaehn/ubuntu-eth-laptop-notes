# Collaboration Touchpad icons on the Dell Pro 14 Premium under Ubuntu 26.04

The Dell Pro 14 Premium (PA14250) has a Collaboration Touchpad: a strip at the
top of the touchpad shows Zoom/Teams icons (mute, camera, share, chat). On
Windows, Dell Optimizer switches these icons on during a call. Under Linux the
icons stay dark, and taps on the strip arrive as ordinary touches.

Status as of 2026-11-19: not working. The LED protocol is decoded and the
touchpad answers it under Linux, but the icons stay dark. Open questions for
the Windows side are listed at the end.

## Hardware

| Component | Value |
| --- | --- |
| Touchpad | `VEN_0488:00 0488:1083`, I2C HID, driver `hid-multitouch` |
| Vendor collection | Usage page `0xFF80`, usage `0x80`, report ID `0x16` |
| BIOS setting | `CollaborationTouchpad` = `Enabled` (via `dell-wmi-sysman`) |

## Report 0x16 layout

Decoded from the HID report descriptor:

- Input (2 bytes): 8 button bits (usages `0x40` to `0x47`), one status byte
  (usage `0x48`).
- Output (5 bytes): six 3-bit fields with values 0 to 4 (usages `0x20`,
  `0x21`, `0x22`, `0x24`, `0x26`, `0x27`), three flag bits (`0x30` to
  `0x32`), then two 4-bit fields (usages 1 to 4 and `0xA2`).
- Feature (12 bytes): three 16-bit durations in ms (`0x61`, `0xA0`, `0xA1`),
  four bytes (`0xA3`, `0xA4`, `0xA6`, `0xA7`), one 16-bit value (`0x62`).

## Findings so far

- Default feature report on Linux: `16 58 02 e8 03 e8 03 10 ff 13 26 00 00`
  (600 ms, 1000 ms, 1000 ms, 16, 255, 19, 38, 0).
- Output reports with flag `0x30` set are answered with input report
  `16 00 40` or `16 00 60`; the other two flags get no answer.
- No combination of icon states and flags lit the icons, also when the
  report was resent every 250 ms.
- The very first blind probe got `16 00 40` (SwipeOff clear). Every run since
  then got `16 00 60` (SwipeOff set). The later steps of that first probe
  (selector bits, `0xA2` nibble and all three flags at once) probably set it.

## Windows: reading the state

[`collab_win_dump.py`](collab_win_dump.py) reads report `0x16` on a Windows
laptop with the same touchpad while Dell Optimizer has the icons lit. It only
reads; it does not write to the device.

```sh
pip install hidapi
python collab_win_dump.py   # during a Zoom desktop call, tap each icon once
```

If the feature report differs from the Linux default above, writing that value
under Linux may switch the icons on.

### Result: the script cannot read while Dell Optimizer runs

On 2026-11-19 the script printed `No vendor collection 0xFF80/0x80 found`.
The collection is there: Device Manager lists `HID\VEN_0488&Col06` with
hardware ID `HID\VID_0488&UP:FF80_U:0080`. But `CreateFile` on it fails with
error 32 (sharing violation), even with zero access rights, so hidapi skips it.
Dell Optimizer holds it open exclusively, so nothing can sniff it in parallel.

### Result with Dell Optimizer stopped

Dell Optimizer is not a service of its own; the `DellTechHub` service starts
`DellOptimizer.exe`. After `Stop-Service DellTechHub` and killing
`DellOptimizer.exe`, the lock went away a few seconds later and the script ran
(the admin shell needs the full path to the per-user `python.exe`). During an
active Zoom call, with the icons lit just before:

- Feature `0x16`: `16 58 02 e8 03 e8 03 10 ff 13 26 00 00`, identical to the
  Linux default. The feature report does not switch the icons on; Dell
  Optimizer must do it with output reports.
- No input reports in 30 s.

### Protocol decoded from CTPAgent.dll

Disassembled with capstone (`UpdateLedCtrl`, `SendHeartbeat`,
`UpdateCTPState`, `HandleInputReport`). The byte layout below was then built
with Windows' own `HidP_SetUsageValue`/`HidP_SetUsages` on the device's
preparsed data, without sending anything to the touchpad.

Output report `0x16`, 6 bytes with the report ID:

| Bits (after ID) | Usage | Meaning |
| --- | --- | --- |
| 0-2 | `0x20` | camera LED, camera-off variant |
| 3-5 | `0x21` | camera LED, camera-on variant |
| 6-8 | `0x22` | share-screen LED |
| 9-11 | `0x24` | chat LED |
| 12-14 | `0x26` | mic LED, muted variant |
| 15-17 | `0x27` | mic LED, unmuted variant |
| 18 | `0x30` | REQUEST: touchpad answers with a status input report |
| 19 | `0x31` | HEARTBEAT |
| 20 | `0x32` | OVERRIDE: host controls the LEDs |
| byte 4 bits 0-3 | usages 1-4 | per-button selector: 1 camera, 2 share, 3 chat, 4 mic |
| byte 5 bits 0-3 | `0xA2` | chat breathing (Optimizer writes 8, `0xF` or 0) |

- Button IDs inside the agent: 0 camera, 1 mic, 2 chat, 3 share screen.
- Each LED field gets Optimizer's brightness setting (0 to 4). Camera and mic
  have two LEDs; the state picks which one gets the value, the other gets 0.
- The selector bit is set for a button when it is enabled.
- `0x32` OVERRIDE is set together with the LED values, but only while the
  host has the strip temporarily disabled (see Q2 below).
- Status input `16 00 xx`: bit 7 TouchpadDisable, bit 6 TouchpadEnable,
  bit 5 SwipeOff (log string: `CTP FW state: ...`). So `16 00 40` and
  `16 00 60` on Linux were status reports.
- The heartbeat is not on a timer. `SendHeartbeat` runs only from
  `HandleInputReport`: when a status report arrives and TemporaryDisable is set,
  the host answers with a report that has only bit `0x31` set.

Single-field examples, as built by `HidP_*`:

```text
REQUEST            16 00 00 04 00 00
HEARTBEAT          16 00 00 08 00 00
OVERRIDE           16 00 00 10 00 00
all on, level 4,   16 20 09 12 0f 00   (0x21, 0x22, 0x24, 0x27 = 4,
selectors+override                      selectors 1-4, override)
```

### Other strings in CTPAgent.dll

The native agent
`C:\Program Files\Dell\DellOptimizer\Plugins\Bootstrap\CollaborationTouchpadPlugin.CTPAgent.dll`
talks to the collection through `HidD_SetFeature`, `HidP_SetUsages`,
`HidP_SetUsageValue` and `WriteFile`. Log strings not yet mapped to code:

- `Activate HID`, `Enable HID`, `EnableFeature`, `SetButtonLight for BUTTON_ID`,
  `UpdateLedCtrl`, `EnableChatBreathing`.
- Output report handlers for `SYNC`, `GESTURE`, `enabled`, `disabled` and for
  the mic, camera, share-screen and chat buttons.
- Feature usages `USAGE_DBLTAP_DURATION_MAX` and `USAGE_INTENSITY`.

The managed wrapper `Dell.Optimizer.Plugin.CollaborationTouchpad.dll` only
calls into this native DLL.

## Linux: replaying the protocol

[`collab_linux_test.py`](collab_linux_test.py) replays the decoded protocol
over hidraw: REQUEST, then the LED report, then a heartbeat in reply to each
status report. Options:

| Option | Effect |
| --- | --- |
| `--hb-with-leds` | heartbeats (and timed REQUESTs) also carry LED, selector and OVERRIDE bits |
| `--hb-period N` | extra heartbeat every N s (default 0.5, 0 = only in reply to status) |
| `--req-period N` | REQUEST every N s, so status replies and heartbeats keep coming |
| `--no-selector`, `--no-override` | leave those bits out |
| `--no-heartbeat` | never send heartbeats (no reply, no timer) |
| `--plain` | Optimizer's normal path: `--no-override --no-heartbeat` |
| `--level N`, `--seconds N` | LED value 0 to 4, run time |

[`collab_status.py`](collab_status.py) sends one REQUEST and prints the
status reply, without touching the LEDs.

### Results on 2026-11-19

| Command | Result |
| --- | --- |
| `collab_linux_test.py` | one status reply, then silence; icons dark |
| `--hb-with-leds --hb-period 0` | one status reply, one heartbeat, then silence; icons dark |
| `--hb-with-leds --hb-period 0 --req-period 0.5` | stable loop for 30 s (REQUEST, status, heartbeat); icons dark |

Every status reply was `16 00 60`: TouchpadEnable and SwipeOff set. The
touchpad accepts and answers the protocol, so the keepalive is not what is
missing. Two candidates remain:

1. **SwipeOff.** If it means "collaboration strip switched off", the firmware
   may ignore LED requests while it is set. It may have been set by the first
   blind probe (see Findings). Test: power off fully, boot, run
   `sudo python3 collab_status.py` before anything else. If it shows
   `swipeoff=0`, run the replay with `--hb-with-leds --hb-period 0
   --req-period 0.5` at once.
2. **Init writes.** `Activate HID`, `Enable HID` and `EnableFeature` suggest a
   setup sequence (probably via `HidD_SetFeature`) before the first LED report.
   The feature report read after Optimizer was stopped equals the Linux
   default, so the write may be transient or use another report.

## Answers from the Windows laptop (2026-11-19, from CTPAgent.dll)

### Q1: init writes

There are none. Apart from logging, the agent writes to the collection in
exactly one place, `WriteOutputReportInternal`, which uses `WriteFile` with
output report `0x16`. `HidD_SetFeature` is only used by `SetClickMode` (the
double-tap durations in feature `0x16`) and by the haptic touchpad code.
`Activate` and `Enable` only change internal state and then call `Update`,
which builds the LED report. At startup the agent checks whether the output
report has usage `0x32` (stored at offset `0x448`, "override supported") and
`0x31` (offset `0x449`, "heartbeat supported"). Both are present on this
touchpad.

### Q2: SwipeOff and the OVERRIDE/HEARTBEAT path

The agent keeps two flags. The log string
`Can't update CTP state because TemporaryDisable (%d) or TabletModeDisable (%d)`
names them:

- `TabletModeDisable` = status bit 7 (TouchpadDisable).
- `TemporaryDisable` = status bit 5 (SwipeOff), but only on touchpads
  without OVERRIDE support. On this touchpad SwipeOff is logged and then
  ignored. `TemporaryDisable` is set only by the host (`Activate` with
  state 4).

The LED update (`Update`) is skipped while either flag is set. The two
special bits are used only in the `TemporaryDisable` case:

- `UpdateLedCtrl` sets `0x32` OVERRIDE only when override is supported and
  `TemporaryDisable` is set.
- `SendHeartbeat` (`0x31`) runs only when a status report arrives and
  `TemporaryDisable` is set.

In normal use, with the icons lit during a call, Optimizer therefore sends
**plain LED reports: LED values plus selector bits, no OVERRIDE, no
heartbeat**. OVERRIDE plus heartbeats seems to mean "host forces the strip
off". This would explain the dark icons in every Linux run so far: all of them
set OVERRIDE, and most sent heartbeats.

Note that the input path only reacts to status reports with no button bits
set. Button taps are handled separately (button IDs 0 camera, 1 mic, 2 chat,
3 share).

### Next test on Linux

Ideally after a full power-off, so no override is latched:

```sh
sudo python3 collab_status.py
sudo python3 collab_linux_test.py --plain
sudo python3 collab_linux_test.py --plain --req-period 0.5
```

If the icons stay dark, also try `--plain --level 2` and
`--plain --no-selector`.

## Still open on the Windows side

1. While Optimizer has the icons lit, what is the status byte? Either decode
   it from the agent's log (`CTP FW state: ...`, if logging can be enabled) or
   hook `ReadFile`/`WriteFile` in `DellOptimizer.exe` (API Monitor or Frida, as
   administrator) and log all report `0x16` traffic during a Zoom call.
2. After stopping `DellTechHub` and `DellOptimizer.exe`: do the icons go dark
   at once, after a delay, or not at all? Does swiping across the strip change
   them?

Feed the answers back into this file; the Linux side can then replay the
exact sequence with `collab_linux_test.py`.
