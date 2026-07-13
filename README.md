# Piwi

A distraction-free, **offline** knowledge device on a Raspberry Pi Zero 2 W with
an E Ink display. Read Wikipedia articles, books, manuals and docs with a
**two-button** interface. No browser, no notifications, no apps — boots straight
into reading.

You can build and prove the **entire device today with no hardware**: the same
code renders to a terminal or a windowed mock, driven by the keyboard. When the
panel and buttons arrive, you change one flag.

---

## Status

**Phase 1–3 are built** (see roadmap). The device runs end to end: library scan,
menus, Markdown reading, pagination, read-position persistence, two-button
control, three display drivers, a wifi/clock status indicator, and **Piwi
Connect** — an on-device toggle that starts a FastAPI web portal for adding
articles over wifi. Phase 4 (EPUB/PDF, collections) is scoped but not built.

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

| Gesture | Left | Right | Both |
|---------|------|-------|------|
| **Tap** (< `HOLD_TIME`) | Previous | Next | Sleep |
| **Hold** (≥ `HOLD_TIME`) | Back | Open | Home |

A hold fires the instant you cross `HOLD_TIME` (no need to release); a tap fires on
release. Buttons pressed together latch as "both" — for hold-both, get both down
before the threshold hits. Default `HOLD_TIME`=0.5 s.

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
Home. Menu screens show a wifi icon + clock top-right; reading stays clean text.

---

## Piwi Connect — add articles over wifi

On the device: **Settings → Piwi Connect**. It starts a small web portal and
shows the Pi's address, e.g. `http://192.168.1.42:8000`, as text **and a QR code** —
scan it with a phone to jump straight there. Open that on any phone or laptop on
the same wifi to:

- add a Wikipedia article by title or URL (fetched, converted to Markdown),
- upload a `.md` file,
- browse and delete the library.

Each imported article also grabs its **lead image** (saved as `<slug>.png` next to
the `.md`). It shows as a cover photo on the article's first page, and the sleep
screen becomes a **photo frame** cycling a random cover. Images fit cover-style
(fill + crop) unless that would trim more than 20%, in which case they're shown
whole (letterboxed on the long edge). Drop your own `<slug>.png` next to any `.md`
to give it a cover.

Anything added shows up on the device next time you open the Library (no restart —
the DB uses WAL so the portal and reader share it). Press **Back** on the device to
stop the server.

Needs `fastapi uvicorn python-multipart` (installed by `setup.sh`). You can also
import straight from the Pi's shell without the portal:

```bash
python wiki_import.py "Apollo 11" --category science
```

The portal is a single self-contained HTML page (`device/web/index.html`) served
by `device/connect.py` — no React build step.

---

## AI Recommend — auto-fill your library

**Home → AI Recommend → pick a folder** (`All`, or one category). Piwi samples up to
10 titles already in that folder, asks a cheap LLM for ~10 related Wikipedia
articles you don't have, drops duplicates, and downloads them. Progress shows on
screen; **Back** cancels.

Filing: a **specific folder** puts everything there. **`All`** asks the AI to file
each article into a folder — reusing an existing folder when it fits, otherwise
creating a sensible new one (so a mix comes back sorted into `History`,
`Science`, etc. rather than one dump).

**Set the provider + API key from Piwi Connect** (Settings → Piwi Connect → open the
portal → *AI Recommend settings*). It's saved to `device/ai.json` (gitignored); the
key is write-only over the API and never sent back to the browser. Leave the key
field blank to change provider/model without re-entering it.

Env vars are the fallback if you'd rather not use the portal (`ai.json` overrides
them):

| Var | Default | Meaning |
|-----|---------|---------|
| `PIWI_AI_PROVIDER` | `anthropic` | `anthropic` / `openai` / `grok` |
| `PIWI_AI_KEY` | — | your API key for that provider |
| `PIWI_AI_MODEL` | cheapest small per provider | override the model |

Default models (cheapest small tier): Anthropic `claude-haiku-4-5`, OpenAI
`gpt-4o-mini`, Grok `grok-3-mini`. No extra Python packages — the call is plain HTTPS.

---

## Listen (text-to-speech)

**Home → Listen → pick a folder → article.** Piper synthesizes the current page,
plays it, and synthesizes the next page while that one plays — so playback starts
after page 1 without converting the whole article up front. Tap Left/Right to skip
pages, hold Left to stop. Audio goes to the default sink (a Bluetooth speaker once
paired — see below). Uses a small `low`-quality voice; TTS on a Pi Zero is not
instant, so expect a short "Converting" beat on the first page.

Not disk-cached — each Listen re-synthesizes on demand (WAV is large on an SD card).

## Bluetooth

**Settings → Bluetooth** scans (~8 s) and lists nearby devices; select one to pair
+ trust + connect (via `bluetoothctl`). Connect a speaker/headphones here before
using Listen. `emmett` must be in the `bluetooth` group.

## Wi-Fi setup (via the setup hotspot)

If the Pi is **offline** when you open **Piwi Connect**, it starts a setup hotspot.
The Connect screen shows the network name + password and `http://10.42.0.1:8000`.
Join that Wi-Fi from a phone, open the portal, and use the **Wi-Fi** section to pick
your network and enter its password. The Pi joins it and the hotspot drops — then
reach the reader on your normal Wi-Fi. Uses `nmcli` (NetworkManager); `emmett`
needs permission to manage connections (the `netdev` group / polkit, default on
Bookworm).

---

## Directory layout

```
device/
    main.py        UI state machine + boot
    config.py      pins, paths, panel size, timings (all env-overridable)
    display.py     drivers: console / mock / waveshare
    buttons.py     two-button gesture recognizer + GPIO/keyboard input
    renderer.py    Markdown->text, wrapping, pagination, page/menu images, wifi icon
    library.py     SQLite library: import, queries, read position
    net.py         local IP + connectivity (status icon, Piwi Connect)
    connect.py     Piwi Connect FastAPI web portal
    wiki_import.py Wikipedia -> Markdown importer (CLI + used by the portal)
    ai_recommend.py LLM suggestions (Anthropic/OpenAI/Grok, raw HTTPS)
    audio.py       piper TTS, page-by-page player (Listen)
    bt.py          Bluetooth pair/connect via bluetoothctl
    wifi.py        Wi-Fi connect + setup hotspot via nmcli
    voices/        piper voice model (downloaded by setup.sh, gitignored)
    web/index.html self-contained portal page
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

### Autostart on boot (systemd)

A ready unit is in `device/piwi.service` (edit `User`, paths, and the
`Environment=` lines for your setup):

```bash
cd ~/wiki-reader/device
sudo cp piwi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now piwi
```

Manage it:

```bash
journalctl -u piwi -f      # live logs
sudo systemctl stop piwi   # stop before running manually (else GPIO pin-in-use)
sudo systemctl restart piwi
sudo systemctl disable piwi # stop starting on boot
```

The panel holds its last image after a stop/shutdown (e-ink physics); the next
launch's `Clear()` wipes it.

---

## Configuration (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `DISPLAY_DRIVER` | `mock` | `mock` / `console` / `waveshare` |
| `EPD_MODEL` | `epd4in2_V2` | `waveshare_epd` driver module for your panel |
| `EPD_WIDTH` / `EPD_HEIGHT` | `400` / `300` | mock/console size (real driver self-reports) |
| `EPD_ROTATE` | `0` | `0`/`180` landscape, `90`/`270` portrait (flip if upside down) |
| `FONT_SIZE` | `18` | bigger = more readable, fewer lines |
| `FONT` | auto | path to a `.ttf` |
| `LEFT_PIN` / `RIGHT_PIN` | `5` / `13` | button BCM pins (keep off the panel's pins) |
| `HOLD_TIME` | `0.5` | tap→hold threshold (seconds) |
| `EPD_FULL_EVERY` | `8` | full (de-ghost) refresh every Nth update; `0` = never (no self-refresh flash) |
| `LIBRARY_DIR` / `DB_PATH` | repo paths | content + database location |

---

## Roadmap

- **Phase 1 — DONE.** Plain-text article rendering, two buttons, manual file copy.
- **Phase 2 — DONE.** Markdown, SQLite library, read-position persistence, sleep.
- **Phase 3 — DONE.** Piwi Connect: FastAPI portal (add-by-URL/title, upload,
  browse, delete), Wikipedia→Markdown importer, on-device start/stop, wifi/clock
  status icon. (Portal is one HTML page, not a React app; hourly auto-sync not
  built — you add on demand.)
- **Phase 4 — in progress.** Listen (piper TTS), Bluetooth audio, Wi-Fi setup via
  hotspot — **done, untested on hardware**. Still later: EPUB/PDF import,
  collections/favourites, disk-cached audio, doc packs, better typography.

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
- **Audio under systemd:** PipeWire runs in the user session, so a `User=emmett`
  *system* service may have no audio sink. If Listen is silent under the service but
  works when you run `python main.py` in your logged-in session, run Piwi as a
  **user** service (`systemctl --user`) or set `XDG_RUNTIME_DIR=/run/user/$(id -u emmett)`
  in the unit. Bluetooth/Wi-Fi likewise need `emmett` in the `bluetooth`/`netdev`
  groups. These hardware paths are untested in this repo — verify on the device.
- **Markdown renders to plain text** (bold/italic stripped, not styled). Fine for
  reading; add font-weight rendering only if you miss it.
- **Big articles paginate in the background.** Opening shows page 0 instantly and
  keeps wrapping the rest in a thread. The total page count is cached in the DB per
  layout (rotation + font + panel size), so it shows `Page 5 / 270` immediately on
  every open after the first. The very first open of an uncached article shows just
  `Page 5` until the count is known, then caches it. Changing orientation or font
  recomputes it once. Resuming deep into a long article shows "Loading page N…"
  briefly, since pagination is sequential.
- **Refresh:** page turns use partial refresh (fast, no flash); a full refresh
  every `EPD_FULL_EVERY` (default 8) updates clears ghosting. Lower it if ghosting
  bugs you, raise it for fewer flashes.
