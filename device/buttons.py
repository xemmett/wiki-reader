"""Two-button control: tap / hold / both.

  Tap   Left = prev       Right = next       Both = sleep
  Hold  Left = back       Right = open       Both = home

A hold fires the moment it crosses HOLD_TIME (while still pressed); a tap fires on
release. Buttons down together latch as "both" — for a hold-both, both must be
down by the time the threshold hits.

The recognizer is pure (no GPIO) so it can be unit-tested.
"""
import sys
import time
import config

LEFT, RIGHT, BOTH = 1, 2, 3  # bitmask of pressed buttons

MAP = {
    (LEFT, "tap"): "prev",  (RIGHT, "tap"): "next",  (BOTH, "tap"): "sleep",
    (LEFT, "hold"): "back", (RIGHT, "hold"): "open", (BOTH, "hold"): "home",
}


class Recognizer:
    """Feed it (state, now); returns an action on release, else None.

    state is a bitmask LEFT|RIGHT of currently-pressed buttons.
    """

    def __init__(self, hold_time=None):
        self.hold = config.HOLD_TIME if hold_time is None else hold_time
        self.start = None
        self.combo = 0
        self.fired = False      # hold already fired for this gesture

    def update(self, state, now):
        act = None
        if state and self.start is None:            # gesture begins
            self.start, self.combo, self.fired = now, state, False
        elif state:                                 # latch any button that joins
            self.combo |= state
        if self.start is not None and not self.fired and state and now - self.start >= self.hold:
            act = MAP.get((self.combo, "hold"))     # fire hold as soon as held long enough
            self.fired = True
        elif self.start is not None and state == 0:  # released
            if not self.fired:
                act = MAP.get((self.combo, "tap"))
            self.start, self.combo, self.fired = None, 0, False
        return act


class GestureButtons:
    """gpiozero-backed. Polls both pins and drives the Recognizer."""

    def run(self, emit):
        from gpiozero import Button
        left = Button(config.LEFT_PIN, bounce_time=0.05)
        right = Button(config.RIGHT_PIN, bounce_time=0.05)
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

    # tap fires on release
    assert r.update(LEFT, 0.0) is None
    assert r.update(0, 0.1) == "prev"
    # hold fires at the threshold, not on release
    assert r.update(RIGHT, 1.0) is None
    assert r.update(RIGHT, 1.6) == "open"      # crossed HOLD_TIME while held
    assert r.update(0, 1.7) is None            # release: no double fire
    # tap-both -> sleep (on release)
    assert r.update(LEFT, 2.0) is None
    assert r.update(BOTH, 2.1) is None
    assert r.update(0, 2.2) == "sleep"
    # hold-both -> home (both down by the threshold)
    assert r.update(LEFT, 3.0) is None
    assert r.update(BOTH, 3.1) is None
    assert r.update(BOTH, 3.6) == "home"
    assert r.update(0, 3.7) is None
    print("buttons selftest OK")


if __name__ == "__main__":
    _selftest()
