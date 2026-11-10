---
name: new-project
description: Create a new ESP32 firmware project in this workshop from a template, fill in its CLAUDE.md, and prove it builds and boots. Use when the user wants to start a new project, board experiment or prototype.
---

# New project

1. Gather what's needed, asking only for what you can't infer:
   - **name**: lowercase, `-`/`_` allowed (e.g. `soil-sensor`)
   - **exact board** (e.g. "Seeed XIAO ESP32-C3"): this determines the LED pin, USB type and usable pins
   - **goal**: one or two sentences
   - **wiring**: what's connected to which GPIO, if anything yet
2. `python tools/esp.py list` to see the templates. Pick the one matching the chip (`esp32c3-idf` for the C3).
3. `python tools/esp.py new <name> --board "<board>" [--template <t>]`
4. Fill in `projects/<name>/CLAUDE.md`: goal, board, USB type, pin map table, and an initial Status.
   Check every pin against `docs/esp32c3.md` (strapping, flash and USB pins) and flag conflicts to the user.
5. `python tools/esp.py build <name>`. The build must pass and the config check must say all settings were applied.
6. If a board is attached: `python tools/esp.py flash <name> --until "alive:"`. Confirm the heartbeat line appears.
   If no board is attached, say so and stop after the build.
7. Tell the user the project is ready and suggest the first feature to build.
