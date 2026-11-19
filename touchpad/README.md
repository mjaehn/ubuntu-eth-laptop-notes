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
