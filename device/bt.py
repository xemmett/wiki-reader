"""Bluetooth via bluetoothctl (pair + trust + connect an audio device).

Pi-only; best-effort subprocess wrapper. No Bluetooth stack in dev, so the pure
parsing is unit-tested and the subprocess calls are thin.
"""
import re
import subprocess

_DEV_RE = re.compile(r"Device\s+([0-9A-Fa-f:]{17})\s+(.*)$")


def _run(args, timeout=15):
    return subprocess.run(["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout)


def _parse_devices(text):
    out = []
    for line in text.splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()   # strip ANSI colour
        m = _DEV_RE.search(line)
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def scan(seconds=8):
    """Power on, scan for `seconds`, return [(mac, name), ...] (known + newly seen)."""
    subprocess.run(["bluetoothctl", "power", "on"], capture_output=True, text=True, timeout=10)
    try:
        subprocess.run(["bluetoothctl", "--timeout", str(seconds), "scan", "on"],
                       capture_output=True, text=True, timeout=seconds + 8)
    except subprocess.TimeoutExpired:
        pass
    return _parse_devices(_run(["devices"]).stdout)


def connect(mac):
    """Pair (if needed), trust, and connect. True on a successful connect."""
    subprocess.run(["bluetoothctl", "power", "on"], capture_output=True, text=True, timeout=10)
    _run(["pair", mac], timeout=25)      # no-op / harmless if already paired
    _run(["trust", mac], timeout=10)
    r = _run(["connect", mac], timeout=25)
    return r.returncode == 0 and "successful" in r.stdout.lower()


# ---- self-check ------------------------------------------------------------
def _selftest():
    sample = ("Device AA:BB:CC:DD:EE:FF JBL Speaker\n"
              "\x1b[0;94m[bluetooth]\x1b[0m Device 11:22:33:44:55:66 Sony WH-1000XM4\n"
              "junk line\n")
    got = _parse_devices(sample)
    assert got == [("AA:BB:CC:DD:EE:FF", "JBL Speaker"),
                   ("11:22:33:44:55:66", "Sony WH-1000XM4")], got
    print("bt selftest OK")


if __name__ == "__main__":
    _selftest()
