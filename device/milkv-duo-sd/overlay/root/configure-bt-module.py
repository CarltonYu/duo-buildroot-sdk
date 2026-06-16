#!/usr/bin/env python3
"""
Duo-side MX-01PS / generic BLE-SPP module diagnostic + auto-configure helper.
Tries many baud rates and AT command formats, prints raw replies, then
optionally sets the module to 9600 baud and a friendly name.

Run manually on the Duo (stops bt-bridge.py first if running):
    /root/configure-bt-module.py

The script exits with code 0 if the module answered AT.
"""
import serial
import time
import sys

SERIAL = "/dev/ttyS1"
BAUD_CANDIDATES = [9600, 115200, 38400, 19200, 57600, 4800, 128000]
TIMEOUT = 0.5
TARGET_BAUD = 9600
SET_NAME = "AIStatusHub-BT"


def log(msg):
    print(f"[bt-config] {msg}")


def open_port(baud):
    try:
        return serial.Serial(SERIAL, baud, timeout=TIMEOUT)
    except Exception as e:
        log(f"cannot open {SERIAL} @ {baud}: {e}")
        return None


def drain(ser):
    ser.reset_input_buffer()
    ser.reset_output_buffer()


def raw_exchange(ser, cmd, wait=1.2):
    drain(ser)
    ser.write(cmd)
    ser.flush()
    time.sleep(wait)
    n = ser.in_waiting or 0
    return ser.read(n)


def probe_variant(ser, cmd_bytes, wait=1.2):
    raw = raw_exchange(ser, cmd_bytes, wait)
    text = raw.decode("utf-8", "ignore").strip()
    return raw, text


def detect_module():
    """Try to get any AT-style response from the module."""
    line_endings = [b"\r\n", b"\n", b"\r"]
    probes = [b"AT", b"at", b"AT+", b"at+", b"+++"]
    for baud in BAUD_CANDIDATES:
        ser = open_port(baud)
        if not ser:
            continue
        log(f"probing @ {baud} ...")
        try:
            for le in line_endings:
                for p in probes:
                    raw, text = probe_variant(ser, p + le)
                    if text:
                        log(f"  -> '{p.decode()}{le.decode()!r}' reply: {text!r} hex={raw.hex()}")
                        if "OK" in text.upper() or "+OK" in text.upper():
                            return ser, baud, text
                    else:
                        log(f"  -> '{p.decode()}{le.decode()!r}' no reply")
            # Some modules wake up only after any traffic; try twice at this baud.
            raw, text = probe_variant(ser, b"AT\r\n", wait=2.0)
            if "OK" in text.upper():
                return ser, baud, text
        except Exception as e:
            log(f"exception @ {baud}: {e}")
        finally:
            ser.close()
    return None, None, None


def at_cmd(ser, cmd_str):
    raw, text = probe_variant(ser, (cmd_str + "\r\n").encode())
    log(f"{cmd_str!r} -> {text!r} hex={raw.hex()}")
    return text


def query_info(ser):
    for cmd in ["AT+VERSION", "AT+VER", "AT+NAME", "AT+NAME?", "AT+BAUD", "AT+BAUD?", "AT+UART?", "AT+ROLE", "AT+ROLE?", "AT+ADDR", "AT+ADDR?"]:
        at_cmd(ser, cmd)


def try_set_name(ser, name):
    for cmd in [f"AT+NAME={name}", f"AT+NAME{name}"]:
        text = at_cmd(ser, cmd)
        if "OK" in text.upper():
            return True
    return False


def try_set_baud(ser, baud):
    # JDY-style index
    idx_map = {1200: "1", 2400: "2", 4800: "3", 9600: "4",
               19200: "5", 38400: "6", 57600: "7", 115200: "8"}
    if baud in idx_map:
        text = at_cmd(ser, f"AT+BAUD={idx_map[baud]}")
        if "OK" in text.upper():
            return True
    # HC-05 style
    text = at_cmd(ser, f"AT+UART={baud},0,0")
    if "OK" in text.upper():
        return True
    return False


def main():
    log(f"scanning for Bluetooth module on {SERIAL}")
    log("(make sure bt-bridge.py is stopped and the module is powered)")

    ser, baud, probe_resp = detect_module()
    if ser is None:
        log("ERROR: module did not answer any probe at any baud.")
        log("Troubleshooting:")
        log("  1. Verify VCC/GND: module LED should blink when powered.")
        log("  2. Verify TX/RX direction: module TX -> Duo RX (GP1), module RX -> Duo TX (GP0).")
        log("  3. Some modules need a KEY/EN pin held high for AT mode.")
        log("  4. Try power-cycling the module while this script waits.")
        sys.exit(1)

    log(f"module answered at {baud} baud, reopening for config ...")
    ser = open_port(baud)
    if not ser:
        log("ERROR: could not reopen port at detected baud")
        sys.exit(1)
    query_info(ser)

    if baud != TARGET_BAUD:
        log(f"changing baud from {baud} to {TARGET_BAUD} ...")
        if try_set_baud(ser, TARGET_BAUD):
            log("baud set OK; power-cycle the module to apply 9600 baud.")
        else:
            log("WARNING: failed to change baud.")
    else:
        log(f"baud already {TARGET_BAUD}")

    log(f"setting name to {SET_NAME} ...")
    if try_set_name(ser, SET_NAME):
        log("name set OK")
    else:
        log("WARNING: failed to set name.")

    try:
        ser.close()
    except Exception:
        pass
    log("done.")
    sys.exit(0)


if __name__ == "__main__":
    main()
