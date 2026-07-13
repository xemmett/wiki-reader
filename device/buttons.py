"""Two-button control: tap / hold / both.

  Tap   Left = prev       Right = next       Both = sleep
  Hold  Left = back       Right = open       Both = home

Actions fire on release. During a gesture (first press to full release) we latch
every button that was down at any point, so "both" registers reliably even if you
hit the second button slightly late — nothing is decided until you let go.

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

    def update(self, state, now):
        if state and self.start is None:        # gesture begins
            self.start, self.combo = now, state
        elif state:                             # latch any button that joins
            self.combo |= state
        if self.start is not None and state == 0:   # full release -> classify
            tier = "hold" if now - self.start >= self.hold else "tap"
            act = MAP.get((self.combo, tier))
            self.start, self.combo = None, 0
            return act
        return None


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

    # single tap / hold
    assert r.update(LEFT, 0.0) is None
    assert r.update(0, 0.1) == "prev"
    assert r.update(RIGHT, 1.0) is None
    assert r.update(0, 1.7) == "open"          # 0.7s hold

    # both, joined late, still latches -> sleep (tap) / home (hold)
    assert r.update(LEFT, 2.0) is None         # left down first
    assert r.update(BOTH, 2.2) is None         # right joins 200ms later
    assert r.update(0, 2.3) == "sleep"         # released quick -> tap-both
    assert r.update(RIGHT, 3.0) is None
    assert r.update(BOTH, 3.1) is None
    assert r.update(0, 4.0) == "home"          # held -> hold-both
    print("buttons selftest OK")


if __name__ == "__main__":
    _selftest()
