"""Wi-Fi via nmcli (NetworkManager — default on Raspberry Pi OS Bookworm).

Scan/connect, plus a setup hotspot that Piwi Connect brings up when the Pi is
offline so you can enter your real network from a phone. Best-effort; pure parsing
is unit-tested, subprocess calls are thin.
"""
import subprocess

import config
import net


def online():
    return net.connected()


def _parse_ssids(text):
    seen, out = set(), []
    for line in text.splitlines():
        ssid = line.split(":")[0].strip()      # -t -f SSID,SIGNAL -> "SSID:SIGNAL"
        if ssid and ssid not in seen:
            seen.add(ssid)
            out.append(ssid)
    return out


def scan():
    try:
        r = subprocess.run(["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list"],
                           capture_output=True, text=True, timeout=25)
        return _parse_ssids(r.stdout)
    except Exception:
        return []


def connect(ssid, password):
    args = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=50).returncode == 0
    except Exception:
        return False


def start_hotspot():
    subprocess.run(["nmcli", "dev", "wifi", "hotspot", "ssid", config.HOTSPOT_SSID,
                    "password", config.HOTSPOT_PASS],
                   capture_output=True, text=True, timeout=30)


def stop_hotspot():
    subprocess.run(["nmcli", "connection", "down", "Hotspot"],
                   capture_output=True, text=True, timeout=15)


# ---- self-check ------------------------------------------------------------
def _selftest():
    sample = "HomeNet:82\nHomeNet:60\n:0\nCafe WiFi:44\n"
    assert _parse_ssids(sample) == ["HomeNet", "Cafe WiFi"]
    print("wifi selftest OK")


if __name__ == "__main__":
    _selftest()
