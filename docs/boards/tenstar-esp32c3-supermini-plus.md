# TENSTAR ESP32-C3 SuperMini Plus

Status: **pinout details below are unverified.** Confirm each item on real hardware, then mark it ✅ with the date.

| Item | Believed | Verified |
|---|---|---|
| Chip | ESP32-C3 with 4 MB in-package flash (ESP32-C3FN4/FH4) | |
| USB | Native USB-Serial/JTAG only (no CP210x/CH340), USB-C on GPIO18/19 | |
| Onboard LED | Plain SuperMini: blue LED on GPIO8, active-low. "Plus" variants may have an RGB (WS2812) LED instead/as well. Check the silkscreen / seller page | |
| BOOT button | GPIO9 (hold while tapping RESET to enter download mode) | |
| Exposed GPIOs | 0–10, 20, 21 (flash pins 12–17 not broken out) | |
| Antenna | "Plus" variants advertise an improved antenna over the plain SuperMini, whose Wi-Fi was notoriously weak | |

## Known SuperMini-family quirks (from community reports; check whether they apply to the Plus)
- Weak or unstable Wi-Fi on the plain SuperMini. A common workaround is lowering TX power
  (`esp_wifi_set_max_tx_power(34)`, about 8.5 dBm).
- No USB-UART bridge, so the serial port disappears whenever the chip resets. `esp.py` handles this, but the first
  moments of boot output can be missed.
- GPIO8 (LED) and GPIO9 (BOOT) are strapping pins. Don't load them in a way that pulls GPIO8 low or GPIO9 low at reset.
