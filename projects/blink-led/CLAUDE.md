# blink-led

Workshop-wide rules and the `esp.py` command reference are in the repo root `CLAUDE.md`. Read that first.

## Goal
Find out how the onboard LED on the SuperMini Plus is wired (which GPIO, active-low or active-high). The firmware
drives GPIO8 low for 2 s, then high for 2 s, forever, logging each level (`alive: cycle N GPIO8 = LOW|HIGH`).

## Hardware
- **Board:** TENSTAR ESP32-C3 SuperMini Plus
- **Chip:** esp32c3
- **USB:** _built-in USB-Serial/JTAG (GPIO18/19), or a USB-UART bridge chip (CP210x / CH340)?_
- **Wiring / pin map:**

| GPIO | Connected to | Notes |
|---|---|---|
| | | |

## Status
- _What works, what's next, known issues. Keep this current at the end of each session._

## Project-specific notes
- _Quirks, decisions, measurements. Move anything useful beyond this project into `docs/`._
