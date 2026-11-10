# esp-workshop: agent guide

A workspace for ESP32 firmware projects, developed and debugged by AI agents. It runs on Windows, macOS and Linux:
the board is plugged into whichever machine you're on, and the commands are identical on all three.

- `templates/`: starting points. Each is a complete ESP-IDF project with debug-friendly config.
- `projects/<name>/`: one folder per firmware project. Each has its own `CLAUDE.md` (goal, board, pin map, status).
- `tools/esp.py`: **the only entry point you need.** It loads the pinned ESP-IDF itself (version in `.idf-version`).
- `docs/`: shared knowledge. Chip notes, `boards/<board>.md` (one per physical board model; verified pinout and
  quirks), and `lessons.md`, which is the workshop's long-term memory.

## Commands (run from the repo root; `python3` on macOS/Linux)
| Task | Command |
|---|---|
| Check this machine | `python tools/esp.py doctor` |
| New project | `python tools/esp.py new <name> --board "<exact board>"` |
| Build (+ config check) | `python tools/esp.py build <project>` |
| Build, flash, capture boot log | `python tools/esp.py flash <project> --until "alive:"` |
| Capture serial (non-interactive) | `python tools/esp.py monitor <project> --seconds 20 [--reset] [--until REGEX]` |
| Debug over JTAG (batch GDB) | `python tools/esp.py gdb <project> --break file.c:42 --ex "bt" --ex "p var"` |
| Read last crash from flash | `python tools/esp.py coredump <project>` |
| Memory usage | `python tools/esp.py size <project>` |
| Detected boards | `python tools/esp.py ports` |
| Anything else in idf.py | `python tools/esp.py idf <project> -- <args>` (e.g. `add-dependency "espressif/led_strip^3"`) |

**Never run** `idf.py monitor`, `idf.py gdb`, `menuconfig` or a bare `openocd`: they're interactive or never exit, and
they will hang your session. Use `monitor`, `gdb` and `sdkconfig.defaults` through `esp.py` instead.

Output of `monitor`, `flash`, `gdb` and `coredump` is also saved under `projects/<p>/logs/` (gitignored), so you can grep it.
Exit codes for `monitor`/`flash`: 0 ok, 2 no board / ambiguous port, 3 `--until` never matched, 4 **crash detected**.

## Workflow
1. Start in the project's `CLAUDE.md` and `docs/lessons.md`. Check the board and pin map before writing pin-related code.
2. Make small, testable changes. Build after each change. Fix every warning you introduced.
3. Flash and **verify on hardware from the serial log**: print a distinctive log line for each feature, and use
   `--until` on it. "It compiles" is not done.
4. On a crash, the capture prints decoded addresses. Then run `coredump` for every task's backtrace, or `gdb` to
   break before the fault. Fix the root cause; don't paper over it with delays or bigger stacks without evidence.
5. Before ending a session, update the project's `CLAUDE.md` Status section. Put anything reusable in `docs/lessons.md`.

## ESP-IDF conventions
- Pinned **ESP-IDF v6.0.x**. APIs changed a lot from v4/v5 (legacy drivers like `driver/adc.h`, `driver/i2c.h` and
  `driver/rmt.h` are gone), so don't trust memory. Check the headers in `$IDF_PATH/components/...` or the v6 docs
  (`https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32c3/`) and copy patterns from `$IDF_PATH/examples`.
- Check every `esp_err_t`: `ESP_ERROR_CHECK` during bring-up, or `ESP_RETURN_ON_ERROR` / handled errors in library code.
- Logging: `ESP_LOGx(TAG, ...)` with one `static const char *TAG` per file. No bare `printf`.
- Configuration lives in **`sdkconfig.defaults`**. The generated `sdkconfig` is gitignored and rebuilt automatically.
  The build warns if a key didn't take effect (renamed in v6, or an unmet dependency); treat that warning as an error.
- Third-party code comes through the component manager (`esp.py idf <p> -- add-dependency ...`). Commit the resulting
  `idf_component.yml` and `dependencies.lock`. Don't vendor copies.
- New source files must be added to `main/CMakeLists.txt` `SRCS`, or split into `components/<name>/`.
- ESP32-C3: single core, RISC-V, ~400 KB SRAM. Keep task stacks modest and check `min free` heap in the heartbeat.
  Pin hazards are in `docs/esp32c3.md`.

## Safety rules (hardware can be bricked; some of this is irreversible)
- **Never touch eFuses** (`espefuse`, `burn_efuse`, `burn_key`, flash encryption, secure boot). These are permanent.
  If a task seems to need them, stop and ask Andrew.
- **Ask before** `erase-flash`, changing `partitions.csv` on a board with data in NVS, writing raw flash regions, or
  changing flash size, voltage or `CONFIG_ESP_CONSOLE_*` (you can lose your own serial log).
- Don't drive a GPIO as an output until the pin map says nothing else is driving it.
- Avoid strapping pins (GPIO2, 8, 9) and the USB pins (GPIO18/19) unless the pin map says it's deliberate.
- If several boards are attached, always pass `--port`.
- Secrets (Wi-Fi passwords, API keys) go in a gitignored `main/secrets.h`. Commit a `secrets.example.h`. Never commit real values.

## When the board misbehaves
- **No port:** check for a charge-only cable or a different USB port, then `esp.py ports`.
- **Flash fails / chip wedged:** hold **BOOT** while tapping **RESET** (or while plugging in) to force download mode,
  then flash again.
- **Port disappears on reset:** normal with native USB (it re-enumerates). The capture tool reconnects, but the
  first ~0.5 s of boot output can be lost.
- **`gdb` says OpenOCD failed:** another program has the JTAG interface (or Windows needs the driver: `eim install-drivers`).
  Close other monitors and retry.
