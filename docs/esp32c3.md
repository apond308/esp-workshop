# ESP32-C3 notes

Single-core 32-bit RISC-V @ 160 MHz, ~400 KB SRAM, Wi-Fi 4 (2.4 GHz) + BLE 5, 22 GPIOs (GPIO0–21).
ESP-IDF target name: `esp32c3`. Toolchain: `riscv32-esp-elf-*`. OpenOCD config: `board/esp32c3-builtin.cfg`.

## Pins to be careful with
| GPIO | Why |
|---|---|
| 2, 8, 9 | **Strapping pins**, sampled at reset. GPIO9 low at boot = download mode (that's the BOOT button). GPIO8 must be high for download mode. Many boards put the onboard LED on GPIO8; it works as an output, but keep it high at reset. |
| 12–17 | Connected to the SPI flash on most modules (and on in-package-flash chips like the ESP32-C3FH4). Don't use. |
| 18, 19 | USB D-/D+ for the built-in USB-Serial/JTAG. Using them as GPIO kills USB flashing/logging/debugging. |
| 20, 21 | UART0 RX/TX (default console on boards with a USB-UART bridge). |
| 0–4 | ADC1 channels 0–4. ADC2 (GPIO5) is unreliable while Wi-Fi is active. |

Any GPIO can be routed to I2C, SPI, UART, LEDC/PWM or RMT through the GPIO matrix.

## Console and USB
- Boards with only native USB (e.g. Seeed XIAO ESP32-C3, many "SuperMini" boards): logs come through the
  USB-Serial/JTAG *secondary console*, which ESP-IDF enables by default on the C3. Input (stdin) only works on the
  primary console (UART0) unless `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`.
- Boards with a CP210x/CH340 bridge (e.g. ESP32-C3-DevKitM-1): the bridge is UART0. JTAG still needs the native USB
  port (some devkits have a second USB connector, others need a cable to GPIO18/19).
- The native USB port re-enumerates when the chip resets, so the COM port vanishes briefly.

## Debugging
- JTAG goes over the same native USB cable (no probe needed). Hardware breakpoints: 8. Watchpoints: 8.
- `CONFIG_ESP_SYSTEM_USE_FRAME_POINTER=y` (on in the template) makes panics print a decodable `Backtrace:` line.
- Core dumps go to the `coredump` partition. `esp.py coredump` decodes them. A stale dump from an old crash stays
  there until a new crash overwrites it, so check the timestamp/app SHA in the output against the current build.
