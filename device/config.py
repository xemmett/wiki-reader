"""All the knobs in one place. Override any with an env var."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)

LIBRARY_DIR = os.environ.get("LIBRARY_DIR", os.path.join(ROOT, "library"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "db.sqlite"))

# Panel = Waveshare 4.2" V2 (400x300, 1-bit). Mock/console use the same size;
# the real driver reports its own size and overrides these two.
EPD_MODEL = os.environ.get("EPD_MODEL", "epd4in2_V2")  # waveshare_epd module name
PANEL_W = int(os.environ.get("EPD_WIDTH", 400))
PANEL_H = int(os.environ.get("EPD_HEIGHT", 300))
FONT_SIZE = int(os.environ.get("FONT_SIZE", 18))       # smaller panel -> smaller font
FONT = os.environ.get("FONT")  # path to a .ttf, else auto-detected

# Two buttons. Left = prev/back, Right = next/open.
# AVOID the panel's pins: 17(RST) 18(PWR) 24(BUSY) 25(DC) 8(CS) + SPI 9/10/11.
# GPIO5 (header pin 29) and GPIO6 (pin 31) are free; wire each to a GND pin.
LEFT_PIN = int(os.environ.get("LEFT_PIN", 5))
RIGHT_PIN = int(os.environ.get("RIGHT_PIN", 13))
HOLD_TIME = float(os.environ.get("HOLD_TIME", 0.6))  # press >= this = "hold"
POLL = float(os.environ.get("POLL", 0.02))           # button poll interval (s)

DRIVER = os.environ.get("DISPLAY_DRIVER", "mock")     # mock | console | waveshare
# E-ink refresh. Default 1 = every frame a full refresh: reliable, but flashes.
# Raise it to use partial refresh between fulls (fast, flat) — BUT partial
# desyncs into static on some 4.2 V2 boards. If yours scrambles, keep this at 1.
FULL_EVERY = int(os.environ.get("EPD_FULL_EVERY", 1))
