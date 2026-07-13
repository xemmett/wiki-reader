"""Two-button control, mouse style: single-click / double-click.

  Single  Left = prev       Right = next       Both = sleep
  Double  Left = back        Right = open       Both = home

A "click" is one press-and-release (both buttons latch if pressed together). Two
clicks of the same kind within DOUBLE_GAP = a double-click; otherwise the single
fires once the window passes. The recognizer is pure (no GPIO), unit-tested.
"""
import sys
import time
import config

LEFT, RIGHT, BOTH = 1, 2, 3  # bitmask of pressed buttons

SINGLE = {LEFT: "prev", RIGHT: "next", BOTH: "sleep"}
DOUBLE = {LEFT: "back", RIGHT: "open", BOTH: "home"}


class Recognizer:
    """Feed it (state, now) every tick; returns an action or None.

    state is a bitmask LEFT|RIGHT of currently-pressed buttons.
    """

    def __init__(self, double_gap=None):
        self.gap = config.DOUBLE_GAP if double_gap is None else double_gap
        self.start = None       # press-in-progress start time
        self.combo = 0          # buttons latched during the current press
        self.pending = None     # (click_type, time) awaiting a possible 2nd click

    def update(self, state, now):
        # 1) detect a completed click (press -> full release)
        click = None
        if state and self.start is None:
            self.start, self.combo = now, state
        elif state:
            self.combo |= state
        if self.start is not None and state == 0:
            click = self.combo
            self.start, self.combo = None, 0

        # 2) turn clicks into single/double
        if click is not None:
            if self.pending and self.pending[0] == click and now - self.pending[1] <= self.gap:
                self.pending = None
                return DOUBLE[click]            # matched -> double
            flushed = SINGLE[self.pending[0]] if self.pending else None
            self.pending = (click, now)          # this click now waits for a partner
            return flushed                       # a different pending click resolves as single

        # 3) a lone click whose window expired resolves as a single
        if self.pending and now - self.pending[1] > self.gap:
            t = self.pending[0]
            self.pending = None
            return SINGLE[t]
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
    r = Recognizer(double_gap=0.3)

    def click(combo, t):
        assert r.update(combo, t) is None      # press
        return r.update(0, t + 0.02)           # release

    # single left -> prev (after the window)
    assert click(LEFT, 0.0) is None
    assert r.update(0, 0.5) == "prev"
    # double right -> open
    assert click(RIGHT, 1.0) is None
    assert click(RIGHT, 1.1) == "open"
    # double both -> home
    assert click(BOTH, 2.0) is None
    assert click(BOTH, 2.1) == "home"
    # different buttons in quick succession resolve as two singles
    assert click(LEFT, 3.0) is None
    assert click(RIGHT, 3.1) == "prev"         # left flushed when right clicks
    assert r.update(0, 3.6) == "next"          # right's window expires
    print("buttons selftest OK")


if __name__ == "__main__":
    _selftest()
