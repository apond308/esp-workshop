# hello-c3

Workshop-wide rules and the `esp.py` command reference are in the repo root `CLAUDE.md`. Read that first.

## Goal
Bring-up test for the workshop: prove build, flash, serial capture, crash decoding, core dump and JTAG debugging all
work on the board. Also verify the board facts in `docs/boards/tenstar-esp32c3-supermini-plus.md`.

## Hardware
- **Board:** TENSTAR ESP32-C3 SuperMini Plus (see `docs/boards/tenstar-esp32c3-supermini-plus.md`)
- **Chip:** esp32c3
- **USB:** built-in USB-Serial/JTAG (GPIO18/19), no bridge chip (to verify)
- **Wiring / pin map:**

| GPIO | Connected to | Notes |
|---|---|---|
| | | |

## Status
- 2026-11-10: builds on Windows (IDF v6.0.3). Not yet flashed; no board attached so far.
- Next: flash, check the `alive:` heartbeat, then test crash capture, `coredump` and `gdb`.

## Project-specific notes
- _Quirks, decisions, measurements. Move anything useful beyond this project into `docs/`._
