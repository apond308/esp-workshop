# TENSTAR ESP32-C3 SuperMini Plus

✅ = verified on this board (date, how). Anything without ✅ is from community reports for the SuperMini family and
still unverified on the Plus: confirm it before relying on it.

| Item | Fact | Verified |
|---|---|---|
| Chip | ESP32-C3, silicon rev v0.4, 1 core, 4 MB flash (DIO, 80 MHz) | ✅ 2026-11-10, boot log |
| USB | Native USB-Serial/JTAG only (no CP210x/CH340), USB-C on GPIO18/19, VID:PID 303A:1001 | ✅ 2026-11-10, Windows device list |
| Onboard LED | **GPIO8, active-HIGH** (HIGH = on, LOW = off). Many plain SuperMini boards are active-low, so don't assume | ✅ 2026-11-10, blink-led probe, observed by Andrew |
| BOOT button | GPIO9 (hold while tapping RESET to enter download mode) | |
| Exposed GPIOs | 0–10, 20, 21 (flash pins 12–17 not broken out) | |
| Antenna | "Plus" variants advertise an improved antenna over the plain SuperMini, whose Wi-Fi was notoriously weak | |
| RGB / second LED | None seen: the only LED observed was the GPIO8 one | |

## Known SuperMini-family quirks (from community reports; check whether they apply to the Plus)
- Weak or unstable Wi-Fi on the plain SuperMini. A common workaround is lowering TX power
  (`esp_wifi_set_max_tx_power(34)`, about 8.5 dBm).
- No USB-UART bridge, so the serial port disappears whenever the chip resets. `esp.py` handles this, but the first
  moments of boot output can be missed.
- GPIO8 (LED) and GPIO9 (BOOT) are strapping pins. Don't load them in a way that pulls GPIO8 low or GPIO9 low at
  reset. The LED on GPIO8 is fine as an output because the pin is driven by firmware only after boot.
