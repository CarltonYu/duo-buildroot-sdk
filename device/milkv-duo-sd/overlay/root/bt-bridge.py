#!/usr/bin/env python3
"""
Bluetooth serial bridge for Duo.
Reads lines from /dev/ttyS1 and forwards them as UDP datagrams to
127.0.0.1:25250 (gc9a01-face-daemon). Re-opens the serial port on errors.

Baud rate defaults to 9600; override with BT_BAUD environment variable.
"""
import serial
import socket
import os
import time
import datetime

SERIAL = "/dev/ttyS1"
BAUD = int(os.environ.get("BT_BAUD", "9600"))
UDP = ("127.0.0.1", 25250)
LOG = "/tmp/bt-bridge.log"


def log(msg):
    line = f"{datetime.datetime.now().isoformat()} {msg}"
    print(line)
    try:
        with open(LOG, "a", 1) as f:
            f.write(line + "\n")
    except Exception:
        pass


def open_serial():
    while True:
        try:
            ser = serial.Serial(SERIAL, BAUD, timeout=0.2)
            log(f"opened {SERIAL} @ {BAUD}")
            return ser
        except Exception as e:
            log(f"cannot open {SERIAL}: {e}, retry in 3s")
            time.sleep(3)


def main():
    log("bt-bridge starting")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ser = open_serial()
    while True:
        try:
            line = ser.readline()
            if not line:
                continue
            text = line.decode("utf-8", "ignore").strip()
            if not text:
                continue
            log(f"rx: {text!r}")
            sock.sendto(text.encode("utf-8"), UDP)
        except serial.SerialException as e:
            log(f"serial error: {e}, reopening")
            try:
                ser.close()
            except Exception:
                pass
            ser = open_serial()
        except Exception as e:
            log(f"unexpected error: {e}")
            time.sleep(0.5)


if __name__ == "__main__":
    main()
