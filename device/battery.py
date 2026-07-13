"""Battery percentage, if the hardware can report it.

The Pi Zero itself has NO way to read battery level — you need a fuel-gauge/UPS
HAT (PiSugar, Waveshare UPS, MAX17048, etc.). Returns None until you wire one in.

ponytail: stubbed. When you pick a HAT, implement read() over I2C here; nothing
else in the app needs to change (only the Settings screen reads this).
"""


def read():
    return None  # percent 0-100, or None if unknown
