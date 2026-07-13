"""Two-button control by press length — no chords.

  Tap        Left = prev        Right = next
  Hold       Left = back        Right = open
  Long-hold  Left = home        Right = sleep

Actions fire on release, classified by how long the button was held. Pressing
both buttons at once does nothing (avoids the fiddly chord timing). The
recognizer is pure (no GPIO) so it can be unit-tested.
"""
import sys
import time
import config

LEFT, RIGHT, BOTH = 1, 2, 3  # bitmask of pressed buttons

MAP = {
    (LEFT, "tap"): "prev",  (RIGHT, "tap"): "next",
    (LEFT, "hold"): "back", (RIGHT, "hold"): "open",
    (LEFT, "long"): "home", (RIGHT, "long"): "sleep",
}


class Recognizer:
    """Feed it (state, now); returns an action on release, else None.

    state is a bitmask LEFT|RIGHT of currently-pressed buttons. A gesture spans
    first press to full release. If both buttons are ever down together it's
    marked invalid and yields nothing.
    """

    def __init__(self, hold_time=None, long_time=None):
        self.hold = config.HOLD_TIME if hold_time is None else hold_time
        self.long = config.LONG_HOLD if long_time is None else long_time
        self.start = None
        self.btn = 0
        self.invalid = False

    def update(self, state, now):
        if state and self.start is None:            # gesture begins
            self.start, self.btn, self.invalid = now, state, (state == BOTH)
        elif state and state != self.btn:           # a second button joined
            self.btn |= state
            self.invalid = True
        if self.start is not None and state == 0:   # released -> classify
            dur = now - self.start
            act = None if self.invalid else MAP.get((self.btn, self._tier(dur)))
            self.start, self.btn, self.invalid = None, 0, False
            return act
        return None

    def _tier(self, dur):
        if dur >= self.long:
            return "long"
        if dur >= self.hold:
            return "hold"
        return "tap"


class GestureButtons:
    """gpiozero-backed. Polls both pins and drives the Recognizer."""

    def run(self, emit):
        from gpiozero import Button
        left = Button(config.LEFT_PIN)
        right = Button(config.RIGHT_PIN)
        rec = Recognizer()
        print(f"Buttons live: L=GPIO{config.LEFT_PIN}  R=GPIO{config.RIGHT_PIN}. Ctrl-C to quit.")
        while True:
            state = (LEFT if left.is_pressed else 0) | (RIGHT if right.is_pressed else 0)
            act = rec.update(state, time.monotonic())
            if act:
                emit(act)
            time.sleep(config.POLL)


class KeyboardInput:
    """No gpiozero? Drive the same actions from the keyboard."""
    KEYMAP = {"p": "prev", "n": "next", "o": "open", "b": "back",
              "h": "home", "s": "sleep", "q": "quit"}

    def run(self, emit):
        print("Keyboard: p=prev n=next o=open b=back h=home s=sleep q=quit")
        for raw in sys.stdin:
            act = self.KEYMAP.get(raw.strip().lower())
            if act:
                emit(act)


def get_input():
    try:
        import gpiozero  # noqa: F401
        return GestureButtons()
    except Exception:
        return KeyboardInput()


# ---- self-check ------------------------------------------------------------
def _selftest():
    r = Recognizer(hold_time=0.5, long_time=1.2)

    def gesture(state, press_at, release_at):
        assert r.update(state, press_at) is None
        return r.update(0, release_at)

    assert gesture(LEFT, 0.0, 0.1) == "prev"      # tap
    assert gesture(RIGHT, 1.0, 1.05) == "next"    # tap
    assert gesture(LEFT, 2.0, 2.7) == "back"      # hold (0.7s)
    assert gesture(RIGHT, 3.0, 3.7) == "open"     # hold
    assert gesture(LEFT, 4.0, 5.5) == "home"      # long-hold (1.5s)
    assert gesture(RIGHT, 6.0, 7.5) == "sleep"    # long-hold
    # both down -> nothing
    assert r.update(BOTH, 8.0) is None
    assert r.update(0, 8.1) is None
    print("buttons selftest OK")


if __name__ == "__main__":
    _selftest()
