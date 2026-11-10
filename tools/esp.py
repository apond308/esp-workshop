#!/usr/bin/env python3
"""esp.py: one cross-platform entry point for building, flashing, monitoring and debugging.

Same commands on Windows, macOS and Linux. Uses only the standard library; everything
that needs ESP-IDF runs inside the pinned ESP-IDF environment (version in .idf-version),
which this script loads by itself, so no "export.sh / export.ps1" step is needed.

  python tools/esp.py doctor                 check this machine
  python tools/esp.py setup                  install the pinned ESP-IDF via EIM
  python tools/esp.py new <name> [--board B] [--template T]
  python tools/esp.py list                   projects and templates
  python tools/esp.py build   <project>
  python tools/esp.py flash   <project> [--port P] [--seconds N] [--until REGEX] [--no-monitor]
  python tools/esp.py monitor <project> [--port P] [--seconds N] [--until REGEX] [--reset]
  python tools/esp.py gdb     <project> [--break LOC]... [--ex CMD]... [--attach] [--timeout N]
  python tools/esp.py coredump <project> [--port P]
  python tools/esp.py size    <project>
  python tools/esp.py ports
  python tools/esp.py idf     <project> -- <any idf.py args>

<project> is a folder name under projects/, a path, or omitted when run from inside a project.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
TEMPLATES = ROOT / "templates"
STATE = ROOT / ".workshop"
IS_WIN = os.name == "nt"

RISCV = {"esp32c2", "esp32c3", "esp32c5", "esp32c6", "esp32c61", "esp32h2", "esp32p4"}
OPENOCD_BOARD = {
    "esp32c3": "board/esp32c3-builtin.cfg",
    "esp32c6": "board/esp32c6-builtin.cfg",
    "esp32h2": "board/esp32h2-builtin.cfg",
    "esp32s3": "board/esp32s3-builtin.cfg",
    "esp32": "board/esp32-wrover-kit-3.3v.cfg",
}


# ----------------------------------------------------------------------------- utils
def say(msg: str) -> None:
    print(f"[esp] {msg}", flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"[esp] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def pinned_version() -> str:
    return (ROOT / ".idf-version").read_text().strip()


def eim_json_path() -> Path:
    if os.environ.get("ESP_IDF_JSON"):
        return Path(os.environ["ESP_IDF_JSON"])
    return Path(r"C:\Espressif\tools\eim_idf.json") if IS_WIN else Path.home() / ".espressif/tools/eim_idf.json"


def find_eim() -> str | None:
    exe = shutil.which("eim")
    if exe:
        return exe
    try:
        p = json.loads(eim_json_path().read_text()).get("eimPath")
        return p if p and Path(p).exists() else None
    except Exception:  # noqa: BLE001
        return None


def installed_idf(version: str) -> dict | None:
    try:
        data = json.loads(eim_json_path().read_text())
    except Exception:  # noqa: BLE001
        return None
    for inst in data.get("idfInstalled", []):
        if inst.get("name") == version and inst.get("status", "installed") != "in_progress":
            return inst
    return None


# ----------------------------------------------------------------------------- IDF environment
def _capture_env(script: Path) -> dict:
    """Run an ESP-IDF activation script in a child shell and return the resulting environment."""
    dump = "import os,json,sys; sys.stdout.write('@@ENV@@'+json.dumps(dict(os.environ)))"
    if script.suffix.lower() == ".ps1":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
               f". '{script}' *> $null; python -c \"{dump}\""]
    else:
        cmd = ["bash", "-c", f'. "$1" >/dev/null 2>&1; python3 -c "{dump}"', "_", str(script)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if "@@ENV@@" not in out.stdout:
        die(f"could not load ESP-IDF environment from {script}\n{out.stdout[-2000:]}\n{out.stderr[-2000:]}")
    return json.loads(out.stdout.split("@@ENV@@", 1)[1])


def activation_script(inst: dict) -> Path:
    for key in ("activationScript", "activation_script"):
        if inst.get(key) and Path(inst[key]).exists():
            return Path(inst[key])
    idf = Path(inst["path"])
    for name in (["export.ps1"] if IS_WIN else ["export.sh"]):
        if (idf / name).exists():
            return idf / name
    die(f"no activation script found for ESP-IDF at {idf}")
    raise AssertionError


def idf_env(refresh: bool = False) -> dict:
    version = pinned_version()
    inst = installed_idf(version)
    if not inst:
        die(f"ESP-IDF {version} is not installed (or still installing). Run: python tools/esp.py setup")
    script = activation_script(inst)
    cache = STATE / f"idf-env-{platform.node()}-{version}.json"
    stamp = f"{script}|{script.stat().st_mtime}"
    if cache.exists() and not refresh:
        c = json.loads(cache.read_text())
        if c.get("stamp") == stamp:
            return c["env"]
    say(f"loading ESP-IDF {version} environment (cached after the first time)...")
    env = _capture_env(script)
    STATE.mkdir(exist_ok=True)
    cache.write_text(json.dumps({"stamp": stamp, "env": env}))
    return env


def idf_python(env: dict) -> str:
    venv = env.get("IDF_PYTHON_ENV_PATH")
    if venv:
        p = Path(venv) / ("Scripts/python.exe" if IS_WIN else "bin/python")
        if p.exists():
            return str(p)
    exe = shutil.which("python", path=env.get("PATH")) or shutil.which("python3", path=env.get("PATH"))
    if not exe:
        die("python not found in the ESP-IDF environment")
    return exe


def tool(env: dict, name: str) -> str | None:
    return shutil.which(name, path=env.get("PATH"))


def run(cmd: list, env: dict | None = None, cwd: Path | None = None, check: bool = True, **kw) -> int:
    say("$ " + " ".join(str(c) for c in cmd))
    rc = subprocess.run([str(c) for c in cmd], env=env, cwd=cwd, **kw).returncode
    if check and rc != 0:
        die(f"command failed with exit code {rc}", rc)
    return rc


def idf_py(env: dict, project: Path, *args, check: bool = True) -> int:
    return run([idf_python(env), Path(env["IDF_PATH"]) / "tools" / "idf.py", "-C", project,
                "-B", project / "build", *args], env=env, check=check)


# ----------------------------------------------------------------------------- projects
def resolve_project(arg: str | None) -> Path:
    if arg:
        for cand in (PROJECTS / arg, Path(arg)):
            if (cand / "CMakeLists.txt").exists():
                return cand.resolve()
        die(f"no project '{arg}' (looked in {PROJECTS} and as a path). `esp.py list` shows projects.")
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if (p / "CMakeLists.txt").exists() and (p / "main").is_dir():
            return p
        if p == ROOT:
            break
    die("no project given and the current directory is not inside one")
    raise AssertionError


def read_kconfig(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("CONFIG_") and "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
            m = re.match(r"# (CONFIG_\w+) is not set", line)
            if m:
                out[m.group(1)] = "n"
    return out


def project_target(project: Path) -> str:
    return read_kconfig(project / "sdkconfig.defaults").get("CONFIG_IDF_TARGET", '"esp32c3"').strip('"')


def project_elf(project: Path) -> Path | None:
    desc = project / "build" / "project_description.json"
    if desc.exists():
        d = json.loads(desc.read_text())
        p = Path(d.get("build_dir", project / "build")) / d.get("app_elf", "")
        if p.is_file():
            return p
    elfs = list((project / "build").glob("*.elf"))
    return elfs[0] if elfs else None


def prepare_config(project: Path) -> None:
    """Keep the gitignored sdkconfig in sync with sdkconfig.defaults (the usual IDF trap)."""
    sdk, defaults = project / "sdkconfig", project / "sdkconfig.defaults"
    if not sdk.exists():
        return
    target = project_target(project)
    current_target = read_kconfig(sdk).get("CONFIG_IDF_TARGET", "").strip('"')
    if current_target and current_target != target:
        say(f"target changed {current_target} -> {target}: removing sdkconfig and build/")
        sdk.unlink()
        shutil.rmtree(project / "build", ignore_errors=True)
        return
    newer = [f.name for f in (defaults, project / "partitions.csv") if f.exists() and f.stat().st_mtime > sdk.stat().st_mtime]
    if newer:
        say(f"{', '.join(newer)} changed since sdkconfig was generated: regenerating sdkconfig")
        sdk.unlink()


def verify_config(project: Path) -> None:
    want = read_kconfig(project / "sdkconfig.defaults")
    have = read_kconfig(project / "sdkconfig")
    bad = [(k, v, have.get(k, "<missing>")) for k, v in want.items() if have.get(k, "n" if v == "n" else None) != v]
    if bad:
        say("WARNING: these sdkconfig.defaults settings did NOT take effect (unknown name, unmet dependency, or overridden):")
        for k, v, h in bad:
            print(f"    {k}: wanted {v}, got {h}")
    else:
        say(f"config check: all {len(want)} sdkconfig.defaults settings applied")


# ----------------------------------------------------------------------------- ports
def detect(env: dict) -> list[dict]:
    out = subprocess.run([idf_python(env), ROOT / "tools" / "serial_capture.py", "--list"],
                         env=env, capture_output=True, text=True)
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        die(f"port detection failed:\n{out.stderr}")
        raise


def pick_port(env: dict, explicit: str | None) -> str:
    if explicit or os.environ.get("ESP_PORT"):
        return explicit or os.environ["ESP_PORT"]
    found = detect(env)
    if len(found) == 1:
        say(f"board: {found[0]['port']} ({found[0]['kind']})")
        return found[0]["port"]
    if not found:
        die("no ESP board detected. Plug it in with a data USB cable (`esp.py ports` to check), or pass --port.", 2)
    die("several boards detected, pass --port:\n" + "\n".join(f"  {c['port']}  {c['kind']}" for c in found), 2)
    raise AssertionError


def log_path(project: Path, kind: str) -> Path:
    d = project / "logs"
    d.mkdir(exist_ok=True)
    return d / f"{kind}-{dt.datetime.now():%Y%m%d-%H%M%S}.log"


def capture(env: dict, project: Path, port: str, seconds: float, until: str | None, reset: bool) -> int:
    target = project_target(project)
    a2l = f"{'riscv32-esp-elf' if target in RISCV else 'xtensa-esp-elf'}-addr2line"
    cmd = [idf_python(env), ROOT / "tools" / "serial_capture.py", "--port", port, "--seconds", seconds,
           "--log", log_path(project, "serial")]
    elf = project_elf(project)
    if elf:
        cmd += ["--elf", elf, "--addr2line", tool(env, a2l) or a2l]
    if until:
        cmd += ["--until", until]
    if reset:
        cmd.append("--reset")
    return run(cmd, env=env, check=False)


# ----------------------------------------------------------------------------- commands
def windows_jtag_driver_ok() -> bool:
    """True if every Espressif USB-JTAG interface (MI_02) has a device-interface GUID (what libusb needs)."""
    import winreg
    base = r"SYSTEM\CurrentControlSet\Enum\USB\VID_303A&PID_1001&MI_02"
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
    except OSError:
        return True  # no such device known (e.g. a different PID): nothing to judge
    ok = True
    for i in range(winreg.QueryInfoKey(root)[0]):
        inst = winreg.EnumKey(root, i)
        try:
            with winreg.OpenKey(root, inst + r"\Device Parameters") as k:
                guid = winreg.QueryValueEx(k, "DeviceInterfaceGUIDs")[0]
                ok = ok and bool(guid)
        except OSError:
            ok = False
    return ok


def cmd_doctor(a) -> int:
    ok = True

    def check(cond: bool, good: str, bad: str):
        nonlocal ok
        print(("  OK    " if cond else "  FAIL  ") + (good if cond else bad))
        ok &= cond

    version = pinned_version()
    print(f"esp-workshop doctor ({platform.system()} {platform.machine()}, Python {platform.python_version()})")
    check(sys.version_info >= (3, 9), "Python >= 3.9", "Python 3.9+ required to run esp.py")
    check(bool(shutil.which("git")), "git found", "git not found")
    eim = find_eim()
    check(bool(eim), f"EIM found: {eim}", "EIM (ESP-IDF Installation Manager) not found. See README.md 'One-time setup'")
    inst = installed_idf(version)
    check(bool(inst), f"ESP-IDF {version} installed at {inst and inst.get('path')}",
          f"ESP-IDF {version} not installed: run `python tools/esp.py setup`")
    if inst:
        env = idf_env(refresh=a.refresh)
        rc = subprocess.run([idf_python(env), Path(env["IDF_PATH"]) / "tools" / "idf.py", "--version"],
                            env=env, capture_output=True, text=True)
        check(rc.returncode == 0 and version.lstrip("v") in rc.stdout,
              f"idf.py runs: {rc.stdout.strip()}", f"idf.py failed: {rc.stdout} {rc.stderr}")
        for t in ("cmake", "ninja", "riscv32-esp-elf-gcc", "riscv32-esp-elf-gdb", "openocd"):
            check(bool(tool(env, t)), f"{t}: {tool(env, t)}", f"{t} missing from the ESP-IDF environment (try `eim fix`)")
        boards = detect(env)
        if boards:
            for b in boards:
                print(f"  OK    board: {b['port']} ({b['kind']}, {b['vid']}:{b['pid']})")
            if IS_WIN and any(b["vid"] == "303A" for b in boards):
                check(windows_jtag_driver_ok(),
                      "Windows JTAG driver: Espressif driver bound (GDB/OpenOCD can open the device)",
                      "JTAG interface uses Windows' generic WinUSB, so OpenOCD fails with LIBUSB_ERROR_NOT_FOUND. "
                      "Run `eim install-drivers` from an elevated shell, then replug. If it's still generic, remove the device "
                      "node (`pnputil /remove-device <MI_02 instance>` + `pnputil /scan-devices`, elevated). See docs/lessons.md")
        else:
            print("  --    no board plugged in (fine for building)")
    if platform.system() == "Linux":
        import grp
        groups = {grp.getgrgid(g).gr_name for g in os.getgroups()}
        check(bool(groups & {"dialout", "uucp"}), "user is in the dialout group",
              "add yourself to dialout: `sudo usermod -aG dialout $USER`, then log out/in")
        check(any(Path(p).exists() for p in ("/etc/udev/rules.d/60-openocd.rules", "/etc/udev/rules.d/99-esp.rules")),
              "udev rules for OpenOCD/JTAG present",
              "JTAG needs udev rules (see README 'Linux'): copy contrib/60-openocd.rules from the openocd-esp32 tool to /etc/udev/rules.d/")
    print("ALL GOOD" if ok else "Some checks failed (see above).")
    return 0 if ok else 1


def cmd_setup(a) -> int:
    version = pinned_version()
    if installed_idf(version):
        say(f"ESP-IDF {version} already installed. (`eim fix` repairs a broken install.)")
        return 0
    eim = find_eim()
    if not eim:
        die("EIM is not installed. See README.md 'One-time setup' for this OS, then re-run `esp.py setup`.")
    targets = sorted({project_target(p.parent) for p in TEMPLATES.glob("*/sdkconfig.defaults")} | {"esp32c3"})
    args = [eim, "install", "-i", version, "-t", ",".join(targets), "-n", "true", "--do-not-track", "true", "--cleanup", "true"]
    if IS_WIN:
        args += ["-p", r"C:\Espressif"]
    return run(args, check=False)


def cmd_list(a) -> int:
    print("templates:")
    for t in sorted(TEMPLATES.iterdir()):
        if (t / "CMakeLists.txt").exists():
            print(f"  {t.name}  (target {project_target(t)})")
    print("projects:")
    for p in sorted(PROJECTS.iterdir()) if PROJECTS.exists() else []:
        if (p / "CMakeLists.txt").exists():
            built = "built" if project_elf(p) else "not built"
            print(f"  {p.name}  (target {project_target(p)}, {built})")
    return 0


def cmd_new(a) -> int:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", a.name):
        die("project names: lowercase letters, digits, '-' and '_'")
    src, dst = TEMPLATES / a.template, PROJECTS / a.name
    if not (src / "CMakeLists.txt").exists():
        die(f"no template '{a.template}'. `esp.py list` shows templates.")
    if dst.exists():
        die(f"{dst} already exists")
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("build", "sdkconfig", "sdkconfig.old", "logs", "managed_components"))
    subs = {"__PROJECT_NAME__": a.name, "__BOARD__": a.board, "__TARGET__": project_target(src)}
    for f in dst.rglob("*"):
        if f.is_file() and f.suffix in {".c", ".h", ".cpp", ".txt", ".md", ".csv", ".defaults", ".yml", ".json", ""}:
            text = f.read_text(encoding="utf-8")
            new = text
            for k, v in subs.items():
                new = new.replace(k, v)
            if new != text:
                f.write_text(new, encoding="utf-8", newline="\n")
    say(f"created {dst.relative_to(ROOT)} from {a.template}. Next: fill in its CLAUDE.md, then `esp.py build {a.name}`")
    return 0


def cmd_build(a) -> int:
    project = resolve_project(a.project)
    env = idf_env()
    prepare_config(project)
    env = {**env, "IDF_TARGET": project_target(project)}
    t0 = time.monotonic()
    rc = idf_py(env, project, "build", check=False)
    if rc != 0:
        die("build failed (see compiler output above)", rc)
    verify_config(project)
    say(f"build OK in {time.monotonic() - t0:.0f}s: {project_elf(project)}")
    return 0


def cmd_flash(a) -> int:
    cmd_build(a)
    project = resolve_project(a.project)
    env = {**idf_env(), "IDF_TARGET": project_target(project)}
    port = pick_port(env, a.port)
    idf_py(env, project, "-p", port, "flash")
    if a.no_monitor:
        return 0
    time.sleep(0.5)
    return capture(env, project, port, a.seconds, a.until, reset=True)


def cmd_monitor(a) -> int:
    project = resolve_project(a.project)
    env = idf_env()
    port = pick_port(env, a.port)
    return capture(env, project, port, a.seconds, a.until, reset=a.reset)


def stop_openocd(ocd: subprocess.Popen) -> None:
    """Shut OpenOCD down gracefully (its `shutdown` command over the telnet port).

    Killing it instead leaves the chip's debug module active. ESP-IDF reads that bit as "a debugger is attached",
    so the NEXT firmware to run asks the (absent) debugger for watchpoints via semihosting `ebreak` and panics
    with "Breakpoint", even after a core reset. Graceful shutdown deactivates the debug module.
    """
    import socket
    try:
        with socket.create_connection(("127.0.0.1", 4444), timeout=3) as s:
            s.sendall(b"shutdown\n")
            time.sleep(0.3)
    except OSError:
        pass
    try:
        ocd.wait(timeout=8)
        return
    except subprocess.TimeoutExpired:
        say("WARNING: OpenOCD did not shut down gracefully; killing it. The chip may still think a debugger is "
            "attached: if the next firmware panics with 'Breakpoint', unplug and replug the board.")
        ocd.terminate()
        try:
            ocd.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ocd.kill()


def cmd_gdb(a) -> int:
    project = resolve_project(a.project)
    env = idf_env()
    target = project_target(project)
    elf = project_elf(project)
    if not elf:
        die("project is not built; run `esp.py build` first (and flash that build, or symbols won't match)")
    gdb = tool(env, f"{'riscv32-esp-elf' if target in RISCV else 'xtensa-esp-elf'}-gdb")
    openocd = tool(env, "openocd")
    if not (gdb and openocd):
        die("gdb/openocd not found in the ESP-IDF environment")
    board_cfg = a.openocd_cfg or OPENOCD_BOARD.get(target)
    if not board_cfg:
        die(f"no default OpenOCD config for {target}; pass --openocd-cfg")

    log = log_path(project, "gdb")
    ocd_log = log.with_name(log.stem + "-openocd.log")
    say(f"starting OpenOCD ({board_cfg}), log: {ocd_log}")
    ocd = subprocess.Popen([openocd, "-f", board_cfg], env=env, stdout=open(ocd_log, "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            time.sleep(0.2)
            if ocd.poll() is not None:
                die(f"OpenOCD exited early (board not connected, or port busy?):\n{ocd_log.read_text()[-3000:]}")
            if "Listening on port 3333" in ocd_log.read_text(errors="replace"):
                break
        else:
            die(f"OpenOCD did not start listening:\n{ocd_log.read_text()[-3000:]}")

        ex = ["set pagination off", "set confirm off", "set print pretty on",
              "target extended-remote :3333"]
        if a.attach:
            ex += ["monitor halt", "maintenance flush register-cache"]
        else:
            ex += ["monitor reset halt", "maintenance flush register-cache"]
            for b in a.break_ or ["app_main"]:
                ex.append(f"thbreak {b}" if not a.break_ else f"break {b}")
            ex.append("continue")
        ex += a.ex or ["bt", "info threads", "info locals"]
        # Always clear hardware breakpoints/watchpoints before detaching: the CPU's debug triggers survive a core reset,
        # so a leftover one makes whatever firmware runs next panic with "Breakpoint" (ebreak) and no debugger attached.
        ex.append("delete")
        if not a.leave_halted:
            ex.append("monitor reset run" if not a.attach else "monitor resume")
        cmd = [gdb, "-q", "-batch", "-nx"] + sum((["-ex", e] for e in ex), []) + [str(elf)]
        say(f"gdb log: {log}")
        try:
            out = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=a.timeout)
            text = out.stdout + out.stderr
        except subprocess.TimeoutExpired as e:
            text = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
            text += f"\n### gdb timed out after {a.timeout}s (breakpoint never hit?)"
        log.write_text(text, encoding="utf-8")
        print(text)
        return 0
    finally:
        stop_openocd(ocd)


def cmd_coredump(a) -> int:
    project = resolve_project(a.project)
    env = idf_env()
    port = pick_port(env, a.port)
    log = log_path(project, "coredump")
    say(f"reading core dump from flash; saved to {log}")
    out = subprocess.run([idf_python(env), Path(env["IDF_PATH"]) / "tools" / "idf.py", "-C", project, "-B", project / "build",
                          "-p", port, "coredump-info"], env=env, capture_output=True, text=True)
    text = out.stdout + out.stderr
    log.write_text(text, encoding="utf-8")
    print(text)
    return out.returncode


def cmd_size(a) -> int:
    project = resolve_project(a.project)
    return idf_py(idf_env(), project, "size", check=False)


def cmd_ports(a) -> int:
    print(json.dumps(detect(idf_env()), indent=2))
    return 0


def cmd_idf(a) -> int:
    project = resolve_project(a.project)
    env = {**idf_env(), "IDF_TARGET": project_target(project)}
    args = a.args[1:] if a.args[:1] == ["--"] else a.args
    # eFuse writes are permanent and can brick the chip. Only the read-only summary is allowed through here.
    blocked = [x for x in args if x.startswith(("efuse-", "secure-")) and x != "efuse-summary"]
    if blocked:
        die(f"refusing {blocked}: eFuse/secure-boot operations are irreversible. Run them by hand if you really mean it.")
    return idf_py(env, project, *args, check=False)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="esp.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="check this machine's setup")
    s.add_argument("--refresh", action="store_true", help="reload the cached ESP-IDF environment")
    s.set_defaults(fn=cmd_doctor)
    sub.add_parser("setup", help="install the pinned ESP-IDF via EIM").set_defaults(fn=cmd_setup)
    sub.add_parser("list", help="list templates and projects").set_defaults(fn=cmd_list)

    s = sub.add_parser("new", help="create a project from a template")
    s.add_argument("name")
    s.add_argument("--template", default="esp32c3-idf")
    s.add_argument("--board", default="_unknown: fill in_")
    s.set_defaults(fn=cmd_new)

    for name, fn, hlp in (("build", cmd_build, "build a project"), ("size", cmd_size, "memory usage")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("project", nargs="?")
        s.set_defaults(fn=fn)

    s = sub.add_parser("flash", help="build, flash, then capture serial output")
    s.add_argument("project", nargs="?")
    s.add_argument("--port")
    s.add_argument("--seconds", type=float, default=12)
    s.add_argument("--until", help="stop capturing when a line matches this regex")
    s.add_argument("--no-monitor", action="store_true")
    s.set_defaults(fn=cmd_flash)

    s = sub.add_parser("monitor", help="capture serial output (non-interactive)")
    s.add_argument("project", nargs="?")
    s.add_argument("--port")
    s.add_argument("--seconds", type=float, default=15)
    s.add_argument("--until")
    s.add_argument("--reset", action="store_true", help="reset the chip first to see boot output")
    s.set_defaults(fn=cmd_monitor)

    s = sub.add_parser("gdb", help="batch GDB session over JTAG (OpenOCD started and stopped for you)")
    s.add_argument("project", nargs="?")
    s.add_argument("--break", dest="break_", action="append", help="breakpoint location (repeatable); default: app_main")
    s.add_argument("--ex", action="append", help="gdb command to run once stopped (repeatable); default: bt, info threads, info locals")
    s.add_argument("--attach", action="store_true", help="halt the running program instead of resetting")
    s.add_argument("--leave-halted", action="store_true")
    s.add_argument("--timeout", type=float, default=60)
    s.add_argument("--openocd-cfg")
    s.set_defaults(fn=cmd_gdb)

    s = sub.add_parser("coredump", help="read and decode the last crash's core dump from flash")
    s.add_argument("project", nargs="?")
    s.add_argument("--port")
    s.set_defaults(fn=cmd_coredump)

    sub.add_parser("ports", help="list detected boards").set_defaults(fn=cmd_ports)

    s = sub.add_parser("idf", help="run any idf.py command inside the pinned environment")
    s.add_argument("project")
    s.add_argument("args", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_idf)

    a = ap.parse_args()
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
