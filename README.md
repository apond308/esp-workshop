# esp-workshop

A workspace for ESP32 firmware, built for AI coding agents (Claude Code) and for humans. The same commands work on
Windows, macOS and Linux, so you can clone it on any machine, plug the board in there, and carry on.

```
esp-workshop/
├─ CLAUDE.md            agent guide: commands, workflow, safety rules
├─ .claude/             skills (new-project, hw-test, debug-crash) + permission rules
├─ .idf-version         pinned ESP-IDF version, used by tools and CI
├─ tools/esp.py         the one CLI: doctor, setup, new, build, flash, monitor, gdb, coredump, ...
├─ tools/serial_capture.py   non-interactive serial logger with crash detection + address decoding
├─ templates/           project templates (esp32c3-idf)
├─ projects/            your firmware projects, one folder each
├─ docs/                chip notes + lessons learned (shared memory)
└─ .github/workflows/   CI: builds every project on push
```

## One-time setup per machine

You need Python 3.9+ and git, then the **ESP-IDF Installation Manager (EIM)**, then the pinned ESP-IDF.

**Windows**
```powershell
winget install Espressif.EIM-CLI
python tools/esp.py setup        # installs the pinned ESP-IDF into C:\Espressif (several GB)
```
If the board isn't recognised for JTAG, run `eim install-drivers` once.

**macOS**
```bash
brew tap espressif/eim && brew install eim
python3 tools/esp.py setup
```

**Linux (Debian/Ubuntu)**
```bash
sudo apt install git wget flex bison gperf python3 python3-venv cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
# EIM apt repo (from https://docs.espressif.com/projects/idf-im-ui/en/latest/)
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://dl.espressif.com/dl/eim/eim.gpg -o /etc/apt/keyrings/eim.gpg
sudo curl -fsSL https://dl.espressif.com/dl/eim/eim.sources -o /etc/apt/sources.list.d/espressif.sources
sudo apt update && sudo apt install eim-cli
python3 tools/esp.py setup
# serial + JTAG access without sudo:
sudo usermod -aG dialout $USER                      # then log out and back in
sudo cp ~/.espressif/tools/openocd-esp32/*/openocd-esp32/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```
WSL2 is not recommended: USB has to be forwarded with `usbipd`, and native-USB chips like the C3 drop the
forwarding every time they reset.

**Then on every OS:**
```
python tools/esp.py doctor
```
Every line should say OK.

## Everyday use
```
python tools/esp.py new soil-sensor --board "Seeed XIAO ESP32-C3"
python tools/esp.py build soil-sensor
python tools/esp.py flash soil-sensor --until "alive:"
python tools/esp.py monitor soil-sensor --seconds 30 --reset
python tools/esp.py gdb soil-sensor --break main.c:40 --ex "info locals"
python tools/esp.py coredump soil-sensor
```
Or just tell Claude what you want ("start a new project for a XIAO C3 that reads a DHT22"). It follows `CLAUDE.md`
and the skills in `.claude/skills/`.

For interactive tools (`idf.py monitor`, `menuconfig`), use `python tools/esp.py idf <project> -- monitor`.
These are for humans only; agents use the non-interactive commands above.

## Upgrading ESP-IDF
1. Edit `.idf-version` (e.g. `v6.0.4`).
2. Run `python tools/esp.py setup` on each machine.
3. Build every project. The config check flags any `sdkconfig.defaults` keys that were renamed.

CI picks up the new version automatically.

## Adding a template for another chip
Copy `templates/esp32c3-idf` to `templates/<chip>-idf`. Then:
- change `CONFIG_IDF_TARGET` in its `sdkconfig.defaults`
- check the partition sizes
- add the chip's OpenOCD board config to `OPENOCD_BOARD` in `tools/esp.py`
- install the target: `eim install -i <version> -t esp32c3,<chip>`, or re-run `setup` after adding the template
