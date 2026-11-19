#!/usr/bin/env python3
"""Linux: send one REQUEST to the Collaboration Touchpad and print its status reply. Run as root."""
import os, select, sys, time

fd = os.open(sys.argv[1] if len(sys.argv) > 1 else "/dev/hidraw1", os.O_RDWR)
os.write(fd, bytes([0x16, 0, 0, 0x04, 0, 0]))
end = time.time() + 1
while time.time() < end and select.select([fd], [], [], 0.1)[0]:
    r = os.read(fd, 64)
    if r[0] == 0x16:
        s = r[2]
        print(f"{r.hex(' ')}  disable={s >> 7 & 1} enable={s >> 6 & 1} swipeoff={s >> 5 & 1}")
        break
else:
    print("No status reply within 1 s.")
os.close(fd)
