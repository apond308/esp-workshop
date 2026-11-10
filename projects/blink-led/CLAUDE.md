# blink-led

Workshop-wide rules and the `esp.py` command reference are in the repo root `CLAUDE.md`. Read that first.

## Goal
Blink the SuperMini Plus's onboard LED at 1 Hz. This is the simplest "hello hardware" project and the reference for
GPIO output on this board. (It started as a probe that found the LED is on GPIO8 and active-high.)

## Hardware
- **Board:** TENSTAR ESP32-C3 SuperMini Plus
- **Chip:** esp32c3
- **USB:** _built-in USB-Serial/JTAG (GPIO18/19), or a USB-UART bridge chip (CP210x / CH340)?_
- **Wiring / pin map:**

| GPIO | Connected to | Notes |
|---|---|---|
| 8 | Onboard LED | Active-HIGH (HIGH = on). Strapping pin, but fine as an output after boot |

## Status
- 2026-11-10: LED wiring verified by eye with the probe version (on when GPIO8 HIGH). 1 Hz blink version flashed;
  serial log shows `alive: blink N` every 5 blinks.

## Project-specific notes
- _Quirks, decisions, measurements. Move anything useful beyond this project into `docs/`._
