"""Output drivers: where the rendered page goes.

  mock       Tkinter window (needs a desktop / X). Also feeds keyboard input.
  console    Plain text to the terminal (headless Pi over SSH).
  waveshare  The real 7.5" e-ink panel.

Input for console/waveshare is handled separately in buttons.py.
"""
import sys
import config


class Display:
    rotate = config.ROTATE
    # Portrait (90/270) swaps the logical canvas that everything renders to.
    if config.ROTATE in (90, 270):
        width, height = config.PANEL_H, config.PANEL_W
    else:
        width, height = config.PANEL_W, config.PANEL_H
    on_action = None  # mock sets this to app.handle

    def show(self, image, text=None):
        raise NotImplementedError

    def sleep(self):    # e-ink low power; no-op elsewhere
        pass

    def wake(self):
        pass

    def close(self):
        pass

    def run(self):      # only the mock owns its own event loop
        pass


class MockDisplay(Display):
    KEYMAP = {"Left": "prev", "Up": "prev", "Right": "next", "Down": "next",
              "Return": "open", "o": "open", "b": "back", "h": "home",
              "s": "sleep", "q": "quit", "Escape": "quit"}

    def __init__(self):
        import tkinter as tk
        from PIL import ImageTk
        self._ImageTk = ImageTk
        self.root = tk.Tk()
        self.root.title(f"Pocket Knowledge (mock {self.width}x{self.height})")
        self.root.resizable(False, False)
        self.label = tk.Label(self.root, bg="white")
        self.label.pack()
        self.root.bind("<Key>", self._key)
        self._photo = None

    def _key(self, e):
        action = self.KEYMAP.get(e.keysym, self.KEYMAP.get(e.char))
        if action and self.on_action:
            self.on_action(action)

    def show(self, image, text=None):
        self._photo = self._ImageTk.PhotoImage(image.convert("L"))
        self.label.config(image=self._photo)
        self.root.update()

    def run(self):
        self.root.mainloop()

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


class ConsoleDisplay(Display):
    """Prints the current screen as text. Headless-friendly."""

    def show(self, image, text=None):
        sys.stdout.write("\033[2J\033[H")
        if text:
            title, lines = text
            print("=" * 60)
            print(title)
            print("=" * 60)
            for ln in lines:
                print(ln)
        sys.stdout.flush()


class WaveshareDisplay(Display):
    def __init__(self):
        import importlib
        mod = importlib.import_module(f"waveshare_epd.{config.EPD_MODEL}")
        self.epd = mod.EPD()
        self.epd.init()
        self.epd.Clear()
        nw, nh = self.epd.width, self.epd.height   # native panel size
        if self.rotate in (90, 270):               # logical (rendered) size
            self.width, self.height = nh, nw
        else:
            self.width, self.height = nw, nh
        self._count = 0                # updates since last full refresh
        self._partial = hasattr(self.epd, "display_Partial")

    def show(self, image, text=None):
        img = image.convert("1")
        if self.rotate:                            # rotate back to native layout
            img = img.rotate(-self.rotate, expand=True, fillcolor=255)
        buf = self.epd.getbuffer(img)
        # First frame is always a full refresh. After that, a full (de-ghost)
        # refresh every FULL_EVERY updates; FULL_EVERY=0 disables it (all partial,
        # no self-refresh flash — but ghosting may build up over time).
        full = self._count == 0 or (config.FULL_EVERY > 0
                                    and self._count % config.FULL_EVERY == 0)
        if not self._partial or full:
            self.epd.display(buf)
        else:
            self.epd.display_Partial(buf)
        self._count += 1

    def sleep(self):
        try:
            self.epd.sleep()
        except Exception:
            pass

    def wake(self):
        self.epd.init()
        self._count = 0  # force a clean full refresh after waking

    def close(self):
        self.sleep()


def get_display(driver=None):
    kind = driver or config.DRIVER
    return {"waveshare": WaveshareDisplay,
            "console": ConsoleDisplay,
            "mock": MockDisplay}.get(kind, MockDisplay)()
