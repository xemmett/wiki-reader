# Pocket Knowledge

A distraction-free, **offline** knowledge device on a Raspberry Pi Zero 2 W with
an E Ink display. Read Wikipedia articles, books, manuals and docs with a
**two-button** interface. No browser, no notifications, no apps — boots straight
into reading.

You can build and prove the **entire device today with no hardware**: the same
code renders to a terminal or a windowed mock, driven by the keyboard. When the
panel and buttons arrive, you change one flag.

---

## Status

**Phase 1 + 2 are built** (see roadmap). The device runs end to end: library
scan, menus, Markdown reading, pagination, read-position persistence, two-button
control, three display drivers. Phase 3+ (backend, web portal, importers) is
scoped but not built — it's a separate service, not device code.

---

## The idea

The device reads **Markdown files**, not raw wiki dumps. Everything it shows is a
1-bit image the code generates, so swapping *where the image goes* is the only
difference between "testing on my laptop" and "running on the Pi".

```
library/*.md ──> SQLite ──> Markdown->text ──> paginated 1-bit image ──> DRIVER
                                                                          │
                        ┌──────────────────┬──────────────────────────────┤
                   ConsoleDisplay      MockDisplay              WaveshareDisplay
                   (terminal)          (Tkinter window)         (real e-ink)
```

Importing Wikipedia / EPUB / PDF is the **backend's** job (Phase 3): it converts
to Markdown and syncs files to the device. The device stays dumb and offline.

---

## Quick start (no hardware)

```bash
pip install Pillow
cd device

# headless — prints pages to the terminal, navigate with the keyboard:
python main.py --driver console --seed

# windowed preview at true panel size (needs a desktop):
python main.py --driver mock --seed

# run the logic self-checks (no display needed):
python main.py --selftest
```

`--seed` (re)imports `library/` into the SQLite DB. Drop it after the first run.

Keyboard maps to the same actions as the buttons: `p`=prev `n`=next `o`=open
`b`=back `h`=home `s`=sleep `q`=quit.

---

## Controls — two buttons

Left = **GPIO5** (header pin 29), Right = **GPIO6** (pin 31). Wire each between
its pin and a **GND** pin (internal pull-ups, no resistors).

> Do **not** use GPIO17/18 — the 4.2" panel uses those (RST/PWR), plus 24/25/8
> and SPI 9/10/11. Override with `LEFT_PIN`/`RIGHT_PIN` if you pick other pins.

| Gesture | Left | Right |
|---------|------|-------|
| **Tap** | Previous | Next |
| **Hold** (~0.6 s) | Back | Open |
| **Both tap** | — Sleep — | |
| **Both hold** | — Home — | |

The gesture engine (`buttons.py`) is a pure state machine, unit-tested without
GPIO. On the Pi it's driven by polling; with no `gpiozero` it falls back to the
keyboard, so console mode + real buttons both work.

---

## UI

```
Home                 Library            (category)         Reading
─────────            ────────           ──────────         ──────────────
→ Library            → History          → Roman Empire     Roman Empire
  Continue Reading     Programming        Apollo 11
  Recent               Science            Titanic          Page 14 / 48
  Random               Travel
  Settings                                                 The empire...
```

Tap to move the arrow, hold-Right to open, hold-Left to go back, hold-both for
Home. No status bars. Just text.

---

## Directory layout

```
device/
    main.py        UI state machine + boot
    config.py      pins, paths, panel size, timings (all env-overridable)
    display.py     drivers: console / mock / waveshare
    buttons.py     two-button gesture recognizer + GPIO/keyboard input
    renderer.py    Markdown->text, wrapping, pagination, page/menu images
    library.py     SQLite library: import, queries, read position
    battery.py     stub (needs a UPS HAT to report anything)
    db.sqlite      created on first run
library/
    history/  programming/  science/  travel/   ...one .md per article
```

Add articles by dropping `library/<category>/<name>.md` and re-running with
`--seed`. Title comes from the first `# heading`, else the filename.

---

## Hardware

| Part | Pick | Why |
|------|------|-----|
| Board | Pi Zero 2 W | quad-core, low power |
| Display | Waveshare 4.2" e-Paper V2 (400×300) | your panel; driver `epd4in2_V2` |
| Buttons | 2× momentary, to GPIO17/18 + GND | the whole UX |
| Storage | 16 GB+ microSD | Markdown is tiny; images later |

Other panels: set `EPD_MODEL` to the matching `waveshare_epd` module (e.g.
`epd7in5_V2`) — the driver reports its own size, so you don't touch the code.

---

## Running on the Pi with the real panel

```bash
./setup.sh
sudo raspi-config nonint do_spi 0 && sudo reboot

# GPIO/SPI backends (rpi-lgpio, not Waveshare's Jetson.GPIO):
pip install spidev rpi-lgpio lgpio gpiozero

# Vendor the driver: waveshare_epd is NOT on PyPI, and Waveshare's
# `pip install .../python` drags in Jetson.GPIO which crashes on a Pi.
# Copy just the two files we need instead:
git clone https://github.com/waveshare/e-Paper ~/e-Paper
mkdir -p device/waveshare_epd
cp ~/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epdconfig.py  device/waveshare_epd/
cp ~/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd4in2_V2.py device/waveshare_epd/
touch device/waveshare_epd/__init__.py

cd device && DISPLAY_DRIVER=waveshare python main.py
```

Another panel: copy its `epd*.py` too and set `EPD_MODEL` (e.g. `epd7in5_V2`).

Autostart on boot: a one-line systemd unit running that command is enough; left
out to keep this minimal.

---

## Configuration (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `DISPLAY_DRIVER` | `mock` | `mock` / `console` / `waveshare` |
| `EPD_MODEL` | `epd4in2_V2` | `waveshare_epd` driver module for your panel |
| `EPD_WIDTH` / `EPD_HEIGHT` | `400` / `300` | mock/console size (real driver self-reports) |
| `FONT_SIZE` | `18` | bigger = more readable, fewer lines |
| `FONT` | auto | path to a `.ttf` |
| `LEFT_PIN` / `RIGHT_PIN` | `5` / `6` | button BCM pins (keep off the panel's pins) |
| `HOLD_TIME` | `0.6` | seconds to count a press as a hold |
| `EPD_FULL_EVERY` | `8` | full (de-ghost) refresh every Nth update; between = partial/no-flash |
| `LIBRARY_DIR` / `DB_PATH` | repo paths | content + database location |

---

## Roadmap

- **Phase 1 — DONE.** Plain-text article rendering, two buttons, manual file copy.
- **Phase 2 — DONE.** Markdown, SQLite library, read-position persistence, sleep.
- **Phase 3 — next.** FastAPI backend + React portal: upload/import, Wikipedia
  downloader (HTML→Markdown), Wi-Fi sync (`GET /sync` hourly). Separate service.
- **Phase 4 — later.** EPUB/PDF import, collections/favourites, doc packs, better
  typography.

Each phase is usable on its own; nothing built now gets thrown away.

---

## Troubleshooting

**`Exception: Could not determine Jetson model`** — Waveshare's library installs
`Jetson.GPIO`, whose fake `RPi.GPIO` shim shadows the real one and crashes on a
Pi. Fix:

```bash
pip uninstall -y Jetson.GPIO RPi.GPIO
pip install rpi-lgpio      # Bookworm-friendly RPi.GPIO drop-in
```

Missing `spidev` or a blank panel → `pip install spidev` and enable SPI:
`sudo raspi-config nonint do_spi 0 && sudo reboot`.

---

## Known ceilings (deliberate simplifications)

- **Sleep sleeps the panel, not the Pi.** True weeks-long standby needs an
  RTC/PiSugar-style HAT to cut power and wake on a button. Marked in `main.py`.
- **Battery is a stub** — the bare Pi can't measure it; needs a fuel-gauge HAT.
- **Markdown renders to plain text** (bold/italic stripped, not styled). Fine for
  reading; add font-weight rendering only if you miss it.
- **Refresh:** page turns use partial refresh (fast, no flash); a full refresh
  every `EPD_FULL_EVERY` (default 8) updates clears ghosting. Lower it if ghosting
  bugs you, raise it for fewer flashes.
