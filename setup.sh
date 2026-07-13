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
# Buttons on GPIO17/18. lgpio is the pin backend on Bookworm.
pip install gpiozero lgpio

echo
echo "Base install done. Seed the library and test in the terminal:"
echo "  cd device && python main.py --driver console --seed"
echo
echo "For the REAL Waveshare 4.2\" V2 panel (driver epd4in2_V2):"
echo "  1) Enable SPI:  sudo raspi-config nonint do_spi 0   (then reboot)"
echo "  2) Install the driver from Waveshare's repo:"
echo "       git clone https://github.com/waveshare/e-Paper"
echo "       pip install ./e-Paper/RaspberryPi_JetsonNano/python"
echo "  3) Run:  cd device && DISPLAY_DRIVER=waveshare python main.py"
echo "     (other panel? set EPD_MODEL, e.g. EPD_MODEL=epd7in5_V2)"
