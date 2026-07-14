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

# Screen rotation, degrees clockwise: 0/180 = landscape, 90/270 = portrait.
# Flip 90<->270 (or 0<->180) if it comes out upside down for your mounting.
ROTATE = int(os.environ.get("EPD_ROTATE", 0))
if ROTATE not in (0, 90, 180, 270):
    ROTATE = 0

# Two buttons. Left = prev/back, Right = next/open.
# AVOID the panel's pins: 17(RST) 18(PWR) 24(BUSY) 25(DC) 8(CS) + SPI 9/10/11.
# GPIO5 (header pin 29) and GPIO13 (pin 33) are free; wire each to a GND pin.
LEFT_PIN = int(os.environ.get("LEFT_PIN", 5))
RIGHT_PIN = int(os.environ.get("RIGHT_PIN", 13))
# Press < HOLD_TIME = tap, >= HOLD_TIME = hold. Actions fire on release.
HOLD_TIME = float(os.environ.get("HOLD_TIME", 0.5))
POLL = float(os.environ.get("POLL", 0.02))           # button poll interval (s)

DRIVER = os.environ.get("DISPLAY_DRIVER", "mock")     # mock | console | waveshare

# AI Recommend: pick a provider + supply an API key via env. Model defaults to the
# cheapest small model for the provider; override with PIWI_AI_MODEL.
AI_PROVIDER = os.environ.get("PIWI_AI_PROVIDER", "anthropic")  # anthropic | openai | grok
AI_MODEL = os.environ.get("PIWI_AI_MODEL")                     # optional override
AI_KEY = os.environ.get("PIWI_AI_KEY")                         # API key (env fallback)
# Piwi Connect writes provider/model/key here; it overrides the env values above.
AI_CONFIG_PATH = os.environ.get("PIWI_AI_CONFIG", os.path.join(BASE, "ai.json"))

# Setup hotspot: brought up by Piwi Connect when the Pi is offline, so you can
# join it from a phone and enter your real Wi-Fi. nmcli requires an 8+ char pass.
HOTSPOT_SSID = os.environ.get("PIWI_HOTSPOT_SSID", "Piwi-Setup")
HOTSPOT_PASS = os.environ.get("PIWI_HOTSPOT_PASS", "piwisetup")
# E-ink: partial refresh (no flash) between full refreshes. Full every Nth update
# clears ghosting. 0 = never (all partial after the first frame, no self-refresh
# flash, but ghosting can build up). Lower = cleaner; higher/0 = fewer flashes.
FULL_EVERY = int(os.environ.get("EPD_FULL_EVERY", 8))
