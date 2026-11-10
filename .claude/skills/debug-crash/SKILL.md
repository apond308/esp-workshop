---
name: debug-crash
description: Diagnose ESP32 crashes, panics, watchdog resets, hangs and boot loops using decoded backtraces, core dumps and batch GDB over JTAG. Use when a capture reports CRASH DETECTED (exit code 4), the board keeps rebooting, or firmware hangs.
---

# Debug a crash or hang

Work from evidence. Each step narrows the cause; don't skip to guessing.

1. **Read the panic.** The capture summary shows the panic reason (e.g. `Load access fault`, `Stack protection
   fault`, `Task watchdog`, `abort()`) and addr2line-decoded addresses: function plus `file:line`. MEPC is where it
   faulted, and RA is the caller. Usually that's enough to find the bug. Read that code.
2. **Core dump** for full context: `python tools/esp.py coredump <project>`. It shows every task's backtrace, the
   crashing task's registers and the task list. Check the app SHA in it matches the current build (stale dumps stay
   in flash until the next crash overwrites them).
3. **GDB over JTAG** (same USB cable on the C3) to stop just before the fault and inspect state:
   `python tools/esp.py gdb <project> --break main.c:57 --ex "bt" --ex "info locals" --ex "p *cfg"`
   - `--attach` halts a running/hung program without resetting it. Use it for hangs and deadlocks:
     `--attach --ex "info threads" --ex "thread apply all bt"`.
   - Watch a variable being corrupted: `--ex "watch some_global" --ex "continue" --ex "bt"`.
   - The ELF must match what's on the chip. Rebuild and re-flash first if in doubt.
4. **Common causes by symptom:**
   - Stack protection fault / canary: task stack too small. Find the deepest call, then size the stack with
     `uxTaskGetStackHighWaterMark`. Don't just double it.
   - Load/Store access fault at a small address: NULL pointer (or NULL + struct offset).
   - `CORRUPT HEAP`: buffer overrun or use-after-free near the reported block. Temporarily set
     `CONFIG_HEAP_POISONING_COMPREHENSIVE=y` to catch it sooner.
   - Task watchdog: a task spinning without yielding, or a blocked mutex. Use `--attach` + `thread apply all bt`.
   - `ESP_ERROR_CHECK failed`: the log prints the error name and line. Look the error up in the API's docs.
   - Brownout: power, not code (USB port or cable, or Wi-Fi TX current spikes). Tell the user.
5. Fix the root cause, re-flash with `hw-test`, and confirm the crash is gone across at least one reset.
6. If it took real effort, add a line to `docs/lessons.md`.
