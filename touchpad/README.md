# Collaboration Touchpad icons on the Dell Pro 14 Premium under Ubuntu 26.04

The Dell Pro 14 Premium (PA14250) has a Collaboration Touchpad: a strip at the
top of the touchpad shows Zoom/Teams icons (mute, camera, share, chat). On
Windows, Dell Optimizer switches these icons on during a call. Under Linux the
icons stay dark, and taps on the strip arrive as ordinary touches.

Status as of 2026-11-19: not working, under investigation.

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

## Next step: read the state on Windows

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

### What the Dell driver tells us

The native agent
`C:\Program Files\Dell\DellOptimizer\Plugins\Bootstrap\CollaborationTouchpadPlugin.CTPAgent.dll`
talks to the collection through `HidD_SetFeature`, `HidP_SetUsages`,
`HidP_SetUsageValue` and `WriteFile`. Its log strings name these concepts:

- Output usages `USAGE_HEARTBEAT`, `USAGE_REQUEST` and `USAGE_OVERRIDE`. These
  probably are the three flag bits `0x30` to `0x32`. A heartbeat flag would
  explain why the icons stay dark under Linux: the firmware may light them only
  while the host keeps sending heartbeats.
- `Activate HID`, `Enable HID`, `EnableFeature`, `SetButtonLight for BUTTON_ID`,
  `UpdateLedCtrl`, `EnableChatBreathing`.
- Output report handlers for `SYNC`, `GESTURE`, `enabled`, `disabled` and for
  the mic, camera, share-screen and chat buttons.
- Feature usages `USAGE_DBLTAP_DURATION_MAX` and `USAGE_INTENSITY`.

The managed wrapper `Dell.Optimizer.Plugin.CollaborationTouchpad.dll` only
calls into this native DLL.

### Options for the next step

1. Disassemble `CTPAgent.dll` (for example with Ghidra) and map the
   `USAGE_*` names to usage numbers and the order of the init writes.
2. Hook `HidD_SetFeature` and `WriteFile` in the Dell Optimizer process (API
   Monitor or Frida, as administrator) and log the bytes during a call.
3. Stop Dell Optimizer, then run `collab_win_dump.py` to compare the Windows
   default feature report with the Linux one.
