# Lessons learned

Shared memory for every project and every agent session. Add an entry when something cost real time to figure out:
a quirk, a fix, a working config, or a measurement. Newest first. Be specific: chip, board, IDF version, and what
the symptom looked like, so a future search finds it.

Format: `- **YYYY-MM-DD, <topic>** (<board/project>): symptom → cause → fix.`

---

- **2026-11-10, Windows: OpenOCD `LIBUSB_ERROR_NOT_FOUND` on the C3's built-in JTAG** (SuperMini Plus, IDF v6.0.3):
  flashing, serial and core dumps worked, but `esp.py gdb` failed with `libusb_open() failed with LIBUSB_ERROR_NOT_FOUND`.
  Cause: Windows auto-bound its generic `winusb.inf` to the JTAG interface (`MI_02`) with no DeviceInterfaceGUID, so
  libusb can't open it, even though Device Manager shows WinUSB and status OK. Not a firmware or board problem.
  Fix: `eim install-drivers` from an **elevated** shell (un-elevated it fails with exit code 5), then rebind. Replugging
  was NOT enough, because Windows kept the old binding. Remove the device node and rescan, elevated:
  `pnputil /remove-device "USB\VID_303A&PID_1001&MI_02\<instance>"` then `pnputil /scan-devices`. Check with
  `esp.py doctor` (it now tests for this) or `DEVPKEY_Device_DriverInfPath` = `oem*.inf` (libwdi/Espressif), not `winusb.inf`.

- **2026-11-10, Windows: serial `--reset` silently did nothing on the C3's native USB** (SuperMini Plus): `monitor
  --reset` showed uptime still counting (`I (466283) ...`) because the DTR/RTS reset pulse never reached the chip.
  Measured over 5 tries each: plain `rts=True; sleep; rts=False` (esptool's own HardReset) rebooted 0/5; re-writing
  DTR=False around each RTS change plus a settle delay after release rebooted 5/5. The earlier resets that "worked"
  only did so right after esptool had flashed. Fixed in `serial_capture.hard_reset`. Check a reset really happened
  by looking for uptime near zero (`I (1281) ...`), not just for the absence of errors.

- **2026-11-10, killing OpenOCD makes the NEXT firmware panic with "Breakpoint"** (C3, IDF v6.0.3): after a `gdb`
  session, flashing/running any firmware gave an endless `Guru Meditation Error: ... (Breakpoint)` loop. The serial
  log shows `Setting breakpoint at 0x4201xxxx and returning...`, and addr2line puts that address in
  `esp_cpu_set_watchpoint` (cpu.c:156, a `semihosting_call_noerrno`). Cause: on the C3, `esp_cpu_dbgr_is_attached()`
  reads the debug module's "active" bit. If OpenOCD is killed (not shut down) that bit stays set across core resets,
  so IDF believes a debugger is attached and asks it, via an `ebreak` semihosting call, to set the stack-end
  watchpoint (`CONFIG_FREERTOS_WATCHPOINT_END_OF_STACK`). Nobody answers, so it panics. Only the debug module
  being deactivated (graceful OpenOCD `shutdown`) or a full power cycle clears it.
  Fix: `esp.py gdb` now stops OpenOCD with `shutdown` over its telnet port (and also runs `delete` first). If the
  fallback kill path ever triggers, `esp.py` warns; recover by running one more `gdb` session or by replugging.
  (My first diagnosis, stale hardware breakpoint triggers, was wrong. The `delete` only treats a related symptom.)

- **2026-11-10, early boot output is lost on native-USB boards**: the USB port drops on chip reset, so the first
  ~0.3 s of boot log (including bootloader lines) can be missed. `monitor --reset` recovers most of it. For the
  full boot sequence use JTAG, or log from `app_main` after a short delay.

- **2026-11-10, `--until` regexes**: `--until` stops at the first match, so a pattern that also matches an earlier
  healthy line (e.g. `alive:` when testing a crash that happens after the first heartbeats) ends the capture before
  the event you want. Use a pattern that only the target event prints.

- **2026-11-10, IDF v6 core dump config** (template): `CONFIG_ESP_COREDUMP_DATA_FORMAT_ELF` no longer exists in v6
  (ELF is the only format). It was silently ignored until `esp.py build`'s config check flagged it. Removed it from
  the template.
