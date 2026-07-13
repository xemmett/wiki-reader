"""Output drivers: where the rendered page goes.

  mock       Tkinter window (needs a desktop / X). Also feeds keyboard input.
  console    Plain text to the terminal (headless Pi over SSH).
  waveshare  The real 7.5" e-ink panel.

Input for console/waveshare is handled separately in buttons.py.
"""
import sys
import config


class Display:
    width = config.PANEL_W
    height = config.PANEL_H
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
        self.width = self.epd.width    # driver reports the true panel size
        self.height = self.epd.height
        self._fast = (config.REFRESH == "fast"
                      and hasattr(self.epd, "display_Fast")
                      and hasattr(self.epd, "init_fast"))
        if self._fast:
            self._fast_mode = getattr(self.epd, config.FAST_MODE, 0)
            self.epd.init_fast(self._fast_mode)   # load the fast LUT once

    def show(self, image, text=None):
        buf = self.epd.getbuffer(image.convert("1"))
        if self._fast:
            self.epd.display_Fast(buf)   # quick, low-flash, no scramble
        else:
            self.epd.display(buf)        # slow full refresh

    def sleep(self):
        try:
            self.epd.sleep()
        except Exception:
            pass

    def wake(self):
        self.epd.init()
        self.epd.Clear()
        if self._fast:
            self.epd.init_fast(self._fast_mode)

    def close(self):
        self.sleep()


def get_display(driver=None):
    kind = driver or config.DRIVER
    return {"waveshare": WaveshareDisplay,
            "console": ConsoleDisplay,
            "mock": MockDisplay}.get(kind, MockDisplay)()
