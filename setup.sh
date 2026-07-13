#!/usr/bin/env bash
# Device setup for Raspberry Pi OS (64-bit Bookworm recommended).
set -euo pipefail

sudo apt update
sudo apt install -y python3-venv python3-pip fonts-dejavu libopenjp2-7

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Buttons (lgpio backend on Bookworm) + Piwi Connect web portal.
pip install gpiozero lgpio fastapi uvicorn python-multipart

echo
echo "Base install done. Seed the library and test in the terminal:"
echo "  cd device && python main.py --driver console --seed"
echo
echo "For the REAL Waveshare 4.2\" V2 panel (driver epd4in2_V2):"
echo "  1) Enable SPI:  sudo raspi-config nonint do_spi 0   (then reboot)"
echo "  2) GPIO/SPI backends (rpi-lgpio, NOT Waveshare's Jetson.GPIO):"
echo "       pip install spidev rpi-lgpio lgpio gpiozero"
echo "  3) Vendor the two driver files (skips Waveshare's setup.py + Jetson.GPIO):"
echo "       git clone https://github.com/waveshare/e-Paper ~/e-Paper"
echo "       mkdir -p device/waveshare_epd"
echo "       cp ~/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epdconfig.py  device/waveshare_epd/"
echo "       cp ~/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd4in2_V2.py device/waveshare_epd/"
echo "       touch device/waveshare_epd/__init__.py"
echo "  4) Run:  cd device && DISPLAY_DRIVER=waveshare python main.py"
echo "     (other panel? copy that epd*.py too and set EPD_MODEL, e.g. epd7in5_V2)"
