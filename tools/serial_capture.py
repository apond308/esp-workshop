"""Non-interactive serial capture for ESP boards, built for agents.

Runs inside the ESP-IDF Python environment (needs pyserial). Normally called via
`esp.py monitor` / `esp.py flash`, not directly.

- Auto-detects the board (Espressif native USB first, then common USB-UART bridges).
- Survives the port disappearing/reappearing (native USB re-enumerates on reset).
- Opens the port without toggling DTR/RTS, so opening it never resets or wedges the chip.
- Stops after --seconds, or early when --until REGEX matches.
- Flags panics / aborts / watchdog resets, and decodes code addresses with addr2line.
- Writes the full log to a file and prints it as it streams.

Exit codes: 0 ok (or --until matched), 2 no/ambiguous port, 3 --until not matched,
4 crash detected (takes priority over 3).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

import serial
from serial.tools import list_ports

ESPRESSIF_VID = 0x303A
BRIDGE_VIDS = {0x10C4: "CP210x", 0x1A86: "CH340/CH343", 0x0403: "FTDI"}

CRASH_PATTERNS = [
    r"Guru Meditation Error",
    r"abort\(\) was called",
    r"assert failed",
    r"ESP_ERROR_CHECK failed",
    r"Stack (canary watchpoint triggered|protection fault|smashing protect)",
    r"CORRUPT HEAP",
    r"Task watchdog got triggered",
    r"rst:0x[0-9a-f]+ \((TG\dWDT|RTCWDT|.*WDT)",
    r"Brownout detector was triggered",
]
CRASH_RE = re.compile("|".join(CRASH_PATTERNS))
# Code addresses on ESP32-C3 (IRAM 0x403xxxxx, flash-mapped 0x420xxxxx)
ADDR_RE = re.compile(r"0x4[02][0-9a-fA-F]{6}")


def candidates():
    found = []
    for p in list_ports.comports():
        if p.vid is None:
            continue
        if p.vid == ESPRESSIF_VID:
            kind = "Espressif native USB"
        elif p.vid in BRIDGE_VIDS:
            kind = BRIDGE_VIDS[p.vid] + " USB-UART bridge"
        else:
            continue
        found.append({"port": p.device, "kind": kind, "vid": f"{p.vid:04X}", "pid": f"{p.pid:04X}",
                      "serial": p.serial_number or "", "desc": p.description or ""})
    # Native USB first
    found.sort(key=lambda c: (c["vid"] != f"{ESPRESSIF_VID:04X}", c["port"]))
    return found


def resolve_port(explicit: str | None) -> str:
    port = explicit or os.environ.get("ESP_PORT")
    if port:
        return port
    found = candidates()
    if len(found) == 1:
        return found[0]["port"]
    if not found:
        print("ERROR: no ESP board found. Plug it in (data-capable USB cable), or pass --port.", file=sys.stderr)
        print("All serial ports:", [p.device for p in list_ports.comports()], file=sys.stderr)
    else:
        print("ERROR: several possible boards; pass --port (or set ESP_PORT):", file=sys.stderr)
        for c in found:
            print(f"  {c['port']}  {c['kind']}  {c['desc']}", file=sys.stderr)
    sys.exit(2)


def open_port(port: str, baud: int) -> serial.Serial:
    s = serial.Serial()
    s.port = port
    s.baudrate = baud
    s.timeout = 0.2
    # De-assert before open: pyserial asserts both by default, which can hold the chip in reset/boot mode.
    s.dtr = False
    s.rts = False
    s.open()
    return s


def hard_reset(s: serial.Serial) -> None:
    # EN/reset via RTS with IO9/IO0 released (DTR low): works for native USB-Serial/JTAG and for
    # the usual two-transistor auto-reset circuit on USB-UART boards.
    s.dtr = False
    s.rts = True
    time.sleep(0.2)
    s.rts = False


def decode(addresses, elf, addr2line):
    if not (elf and addr2line and os.path.exists(elf) and shutil.which(addr2line)):
        return None
    try:
        out = subprocess.run([addr2line, "-pfiaC", "-e", elf, *addresses],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception as e:  # noqa: BLE001
        return f"(addr2line failed: {e})"
    lines = [l for l in out.splitlines() if "?? ??:0" not in l]
    return "\n".join(lines) if lines else None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--until", help="regex; stop as soon as a line matches")
    ap.add_argument("--reset", action="store_true", help="hard-reset the chip after opening the port")
    ap.add_argument("--log", help="write the capture to this file")
    ap.add_argument("--elf", help="app ELF, for decoding crash addresses")
    ap.add_argument("--addr2line", help="target addr2line executable")
    ap.add_argument("--list", action="store_true", help="print detected boards as JSON and exit")
    a = ap.parse_args()

    if a.list:
        print(json.dumps(candidates(), indent=2))
        return 0

    port = resolve_port(a.port)
    until_re = re.compile(a.until) if a.until else None
    deadline = time.monotonic() + a.seconds
    logf = open(a.log, "w", encoding="utf-8") if a.log else None

    def emit(line: str):
        print(line, flush=True)
        if logf:
            logf.write(line + "\n")
            logf.flush()

    emit(f"### capture {port} @ {a.baud} for {a.seconds:g}s" + (f", until /{a.until}/" if a.until else ""))
    s = None
    did_reset = False
    matched = False
    crash_lines: list[str] = []
    crash_addrs: list[str] = []
    in_crash = False
    buf = b""
    reconnects = 0

    while time.monotonic() < deadline and not matched:
        if s is None:
            try:
                s = open_port(port, a.baud)
                if reconnects:
                    emit(f"### reconnected to {port}")
                if a.reset and not did_reset:
                    did_reset = True
                    hard_reset(s)
            except (serial.SerialException, OSError):
                s = None
                time.sleep(0.25)
                continue
        try:
            chunk = s.read(4096)
        except (serial.SerialException, OSError):
            # Native USB drops off the bus on chip reset; wait for it to come back.
            try:
                s.close()
            except Exception:  # noqa: BLE001
                pass
            s = None
            reconnects += 1
            emit(f"### {port} disconnected (chip reset / re-enumeration), waiting for it to return...")
            continue
        if not chunk:
            continue
        buf += chunk
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            line = raw.decode("utf-8", errors="replace").rstrip("\r")
            emit(line)
            if CRASH_RE.search(line):
                in_crash = True
            if in_crash:
                crash_lines.append(line)
                crash_addrs.extend(m for m in ADDR_RE.findall(line) if m not in crash_addrs)
                if "Rebooting..." in line or line.startswith("ESP-ROM:"):
                    in_crash = False
            if until_re and until_re.search(line):
                matched = True
                break

    if buf:
        emit(buf.decode("utf-8", errors="replace"))
    if s:
        s.close()

    code = 0
    emit("### ---- summary ----")
    if crash_lines:
        code = 4
        emit(f"### CRASH DETECTED: {crash_lines[0].strip()}")
        dec = decode(crash_addrs[:40], a.elf, a.addr2line)
        if dec:
            emit("### decoded addresses (addr2line):")
            for l in dec.splitlines():
                emit("    " + l)
        elif crash_addrs:
            emit("### (no ELF/addr2line available to decode addresses)")
        emit("### next steps: `esp.py coredump <project>` for full task backtraces, or `esp.py gdb`.")
    if until_re:
        emit(f"### until /{a.until}/: {'MATCHED' if matched else 'NOT matched before timeout'}")
        if not matched and code == 0:
            code = 3
    if reconnects:
        emit(f"### port reconnects: {reconnects}")
    if a.log:
        emit(f"### log saved: {a.log}")
    if logf:
        logf.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
