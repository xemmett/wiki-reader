"""Two-button control. Tap / hold / both, decoded into actions.

  Tap  Left = prev       Right = next
  Hold Left = back        Right = open
  Hold both = home        Tap both = sleep

The recognizer is pure (no GPIO) so it can be unit-tested. GestureButtons wires
gpiozero to it; KeyboardInput is the no-hardware fallback.
"""
import sys
import time
import config

LEFT, RIGHT, BOTH = 1, 2, 3  # bitmask of pressed buttons


class Recognizer:
    """Feed it (state, now); it returns an action string or None.

    state is a bitmask: LEFT|RIGHT of currently-pressed buttons.
    A gesture spans from first press to full release. If both buttons are
    pressed at any point during it, it counts as "both".
    """

    def __init__(self, hold_time=None):
        self.hold = hold_time if hold_time is not None else config.HOLD_TIME
        self.start = None
        self.combo = 0
        self.fired = False

    def update(self, state, now):
        act = None
        if state and self.start is None:          # gesture begins
            self.start, self.combo, self.fired = now, state, False
        elif state:                               # gesture continues
            self.combo |= state
        if self.start is not None and not self.fired and state and now - self.start >= self.hold:
            act = self._hold(self.combo)          # crossed the hold threshold
            self.fired = True
        elif self.start is not None and state == 0:  # released
            if not self.fired:
                act = self._tap(self.combo)
            self.start, self.combo, self.fired = None, 0, False
        return act

    @staticmethod
    def _tap(combo):
        return {LEFT: "prev", RIGHT: "next", BOTH: "sleep"}.get(combo)

    @staticmethod
    def _hold(combo):
        return {LEFT: "back", RIGHT: "open", BOTH: "home"}.get(combo)


class GestureButtons:
    """gpiozero-backed. Polls both pins and drives the Recognizer."""

    def run(self, emit):
        from gpiozero import Button
        left = Button(config.LEFT_PIN, hold_time=config.HOLD_TIME)
        right = Button(config.RIGHT_PIN, hold_time=config.HOLD_TIME)
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
    r = Recognizer(hold_time=0.5)
    # quick tap left -> prev
    assert r.update(LEFT, 0.0) is None
    assert r.update(0, 0.1) == "prev"
    # hold right -> open (fires at threshold, release is a no-op)
    assert r.update(RIGHT, 1.0) is None
    assert r.update(RIGHT, 1.6) == "open"
    assert r.update(0, 1.7) is None
    # both tapped -> sleep
    assert r.update(LEFT, 2.0) is None
    assert r.update(BOTH, 2.05) is None
    assert r.update(0, 2.2) == "sleep"
    # both held -> home
    assert r.update(BOTH, 3.0) is None
    assert r.update(BOTH, 3.6) == "home"
    print("buttons selftest OK")


if __name__ == "__main__":
    _selftest()
