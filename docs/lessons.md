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

- **2026-11-10, leftover GDB breakpoint makes the NEXT firmware panic with "Breakpoint"** (C3, OpenOCD): after a
  `gdb` session that set a hardware breakpoint, flashing a different program gave an endless
  `Guru Meditation Error: ... (Breakpoint)` loop with no backtrace. The RISC-V debug triggers live in the CPU and
  survive a core reset, so the stale trigger fires (ebreak) when the new code reaches that address with no debugger
  attached. A later session may also fail with "No hardware breakpoint support in the target" (all slots used).
  Fix: `esp.py gdb` now always runs `delete` before detaching. To recover a board already stuck in this state, run
  any `esp.py gdb <project> --ex "bt"` (OpenOCD re-initialises the triggers) or unplug/replug the board.

- **2026-11-10, early boot output is lost on native-USB boards**: the USB port drops on chip reset, so the first
  ~0.3 s of boot log (including bootloader lines) can be missed. `monitor --reset` recovers most of it. For the
  full boot sequence use JTAG, or log from `app_main` after a short delay.

- **2026-11-10, `--until` regexes**: `--until` stops at the first match, so a pattern that also matches an earlier
  healthy line (e.g. `alive:` when testing a crash that happens after the first heartbeats) ends the capture before
  the event you want. Use a pattern that only the target event prints.

- **2026-11-10, IDF v6 core dump config** (template): `CONFIG_ESP_COREDUMP_DATA_FORMAT_ELF` no longer exists in v6
  (ELF is the only format). It was silently ignored until `esp.py build`'s config check flagged it. Removed it from
  the template.
