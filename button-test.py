"""
Connect green to GND
Connect red to GPIO5
Connect black to GPIO6
"""


from gpiozero import Button
from signal import pause

up = Button(5, bounce_time=0.1)
down = Button(6, bounce_time=0.1)

print("up.is_pressed:", up.is_pressed)
print("down.is_pressed:", down.is_pressed)

up.when_pressed = lambda: print("UP")
down.when_pressed = lambda: print("DOWN")
up.when_released = lambda: print("up released")
down.when_released = lambda: print("down released")

pause()