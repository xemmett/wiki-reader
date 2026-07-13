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
LEFT_PIN = int(os.environ.get("LEFT_PIN", 17))
RIGHT_PIN = int(os.environ.get("RIGHT_PIN", 18))
HOLD_TIME = float(os.environ.get("HOLD_TIME", 0.6))  # press >= this = "hold"
POLL = float(os.environ.get("POLL", 0.02))           # button poll interval (s)

DRIVER = os.environ.get("DISPLAY_DRIVER", "mock")     # mock | console | waveshare
