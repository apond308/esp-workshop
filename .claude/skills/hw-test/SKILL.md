---
name: hw-test
description: Flash a workshop project to the attached ESP board and verify behaviour from its serial output. Use after any firmware change that should be checked on real hardware, or when the user says flash, upload, run it, or test it on the board.
---

# Flash and verify on hardware

1. Decide what "working" looks like *before* flashing: one or more distinctive log lines (add `ESP_LOGI` lines to
   the code if they don't exist yet), and anything that must NOT appear.
2. `python tools/esp.py ports`. If no board shows up, stop and ask the user to plug it in. If there are several,
   ask which one and pass `--port` from then on.
3. `python tools/esp.py flash <project> --until "<regex for the success line>" --seconds 20`
   - exit 0: matched. Read the rest of the log anyway, looking for warnings, `E (` error lines, or reboot loops.
   - exit 3: success line never appeared. Read the log, form a hypothesis, then add logging or use `gdb`.
   - exit 4: crash. Switch to the `debug-crash` skill.
   - exit 2: port problem. See "When the board misbehaves" in the root CLAUDE.md.
4. For behaviour that develops over time (leaks, Wi-Fi reconnects, sensor drift), also run
   `python tools/esp.py monitor <project> --seconds 120` and compare `min free` heap across heartbeats.
5. Report what you saw, quoting the key log lines. If something physical needs checking (an LED lit, a motor
   turned), ask the user to confirm it. Don't claim it.
