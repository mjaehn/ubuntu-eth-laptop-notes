#!/usr/bin/env python3
"""Windows: dump the Dell Collaboration Touchpad vendor report 0x16 state. Requires: pip install hidapi"""
import time
import hid

RID, LEN, LISTEN_SECONDS = 0x16, 13, 30

devs = [d for d in hid.enumerate() if d["usage_page"] == 0xFF80 and d["usage"] == 0x80]
if not devs:
    raise SystemExit("No vendor collection 0xFF80/0x80 found. Is this the same touchpad?")

for d in devs:
    print(f"Device {d['vendor_id']:04x}:{d['product_id']:04x}  {d['product_string']}  {d['path']}")
    dev = hid.device()
    dev.open_path(d["path"])
    try:
        print("Feature 0x16:", bytes(dev.get_feature_report(RID, LEN)).hex(" "))
    except OSError as e:
        print("Feature read failed:", e)
    dev.set_nonblocking(True)
    print(f"Listening {LISTEN_SECONDS} s - tap each icon once, slowly, and note the order.")
    end = time.time() + LISTEN_SECONDS
    while time.time() < end:
        data = dev.read(64)
        if data:
            print(f"{time.strftime('%H:%M:%S')}  {bytes(data).hex(' ')}")
        time.sleep(0.01)
    print("Feature 0x16 after:", bytes(dev.get_feature_report(RID, LEN)).hex(" "))
    dev.close()
