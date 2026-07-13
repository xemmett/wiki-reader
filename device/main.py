#!/usr/bin/env python3
"""Piwi — offline knowledge reader. Boots straight into the library.

  Test with no hardware:   python main.py --driver console --seed
  Windowed preview:        python main.py --driver mock --seed
  On the Pi + panel:       DISPLAY_DRIVER=waveshare python main.py

Controls (two buttons):
  Tap  Left=prev  Right=next     Hold Left=back  Right=open
  Hold both=Home                 Tap both=Sleep
Keyboard fallback: p n o b h s q
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # arrows/bullets on any OS
except Exception:
    pass

import config
import library
import renderer
from display import get_display
from buttons import get_input


class App:
    def __init__(self, db, display):
        self.db = db
        self.display = display
        self.font = renderer.load_font()
        self.stack = []        # menu screens: {title, items:[(label, thunk)], sel}
        self.reading = None    # {row, pages, page, line_h}
        self.asleep = False
        self.home()

    # ---- screens ----
    def home(self):
        items = [
            ("Library", self.open_library),
            ("Continue Reading", self.open_continue),
            ("Recent", self.open_recent),
            ("Random", self.open_random),
            ("Settings", self.open_settings),
        ]
        self.stack = [{"title": "Piwi", "items": items, "sel": 0}]
        self.reading = None

    def push(self, title, items):
        self.stack.append({"title": title, "items": items or [("(empty)", None)], "sel": 0})

    def open_library(self):
        cats = library.categories(self.db)
        self.push("Library", [(c, lambda c=c: self.open_category(c)) for c in cats])

    def open_category(self, category):
        rows = library.articles(self.db, category)
        self.push(category, [(r["title"], lambda r=r: self.open_article(r)) for r in rows])

    def open_recent(self):
        rows = library.recent(self.db)
        self.push("Recent", [(r["title"], lambda r=r: self.open_article(r)) for r in rows])

    def open_continue(self):
        row = library.continue_reading(self.db)
        if row:
            self.open_article(row)

    def open_random(self):
        row = library.random_article(self.db)
        if row:
            self.open_article(row)

    def open_settings(self):
        import battery
        b = battery.read()
        info = f"Battery: {b}%" if b is not None else "Battery: n/a (no UPS HAT)"
        self.push("Settings", [(info, None),
                               (f"Font size: {config.FONT_SIZE}", None),
                               ("Piwi", None)])

    def open_article(self, row):
        text = renderer.markdown_to_text(row["body"])
        pages, line_h = renderer.paginate(text, self.font, self.display.width,
                                          self.display.height, reserve_lines=4)
        start = min(row["read_position"] or 0, len(pages) - 1)
        self.reading = {"row": row, "pages": pages, "page": start, "line_h": line_h}

    # ---- input ----
    def handle(self, action):
        if action == "quit":
            self.quit()
        if self.asleep:                 # any press wakes
            self.asleep = False
            self.display.wake()
            self.render()
            return
        if action == "sleep":
            self.sleep()
            return
        if action == "home":
            self.home()
            self.render()
            return
        if self.reading:
            self._reading_action(action)
        else:
            self._menu_action(action)
        self.render()

    def _reading_action(self, action):
        r = self.reading
        last = len(r["pages"]) - 1
        if action in ("next", "open"):
            r["page"] = min(r["page"] + 1, last)
        elif action == "prev":
            r["page"] = max(r["page"] - 1, 0)
        elif action == "back":
            self.reading = None
            return
        library.set_position(self.db, r["row"]["id"], r["page"])

    def _menu_action(self, action):
        scr = self.stack[-1]
        n = len(scr["items"])
        if action == "prev":
            scr["sel"] = (scr["sel"] - 1) % n
        elif action == "next":
            scr["sel"] = (scr["sel"] + 1) % n
        elif action == "open":
            thunk = scr["items"][scr["sel"]][1]
            if thunk:
                thunk()
        elif action == "back":
            if len(self.stack) > 1:
                self.stack.pop()

    # ---- output ----
    def render(self):
        W, H = self.display.width, self.display.height
        if self.asleep:
            img = renderer.render_page(["", "Sleeping.", "Press any button to wake."],
                                       self.font, W, H, header="Piwi")
            self.display.show(img, text=("Piwi", ["", "Sleeping — press to wake."]))
        elif self.reading:
            r = self.reading
            info = f"Page {r['page'] + 1} / {len(r['pages'])}"
            lines = [info, ""] + r["pages"][r["page"]]
            img = renderer.render_page(lines, self.font, W, H,
                                       line_h=r["line_h"], header=r["row"]["title"])
            self.display.show(img, text=(r["row"]["title"], lines))
        else:
            scr = self.stack[-1]
            labels = [lb for lb, _ in scr["items"]]
            marked = [("→ " if i == scr["sel"] else "   ") + lb for i, lb in enumerate(labels)]
            img = renderer.render_menu(labels, scr["sel"], self.font, W, H, title=scr["title"])
            self.display.show(img, text=(scr["title"], marked))

    def sleep(self):
        self.asleep = True
        self.render()
        self.display.sleep()
        # ponytail: this only sleeps the panel. True weeks-long standby needs an
        # RTC/PiSugar to cut Pi power and wake on button — add when you have the HAT.

    def quit(self):
        self.display.close()
        sys.exit(0)


def main():
    ap = argparse.ArgumentParser(description="Piwi reader")
    ap.add_argument("--driver", choices=["mock", "console", "waveshare"],
                    help="output driver (overrides DISPLAY_DRIVER)")
    ap.add_argument("--seed", action="store_true", help="(re)import library/ into the DB first")
    ap.add_argument("--selftest", action="store_true", help="run module self-checks and exit")
    args = ap.parse_args()

    if args.selftest:
        renderer._selftest()
        import buttons
        buttons._selftest()
        library._selftest()
        print("all selftests OK")
        return

    db = library.connect()
    if args.seed or not library.categories(db):
        n = library.import_dir(db)
        print(f"Imported {n} articles from {config.LIBRARY_DIR}")

    display = get_display(args.driver)
    app = App(db, display)
    app.render()

    if args.driver == "mock" or (args.driver is None and config.DRIVER == "mock"):
        display.on_action = app.handle
        display.run()                 # Tkinter mainloop
    else:
        get_input().run(app.handle)   # GPIO buttons, or keyboard fallback


if __name__ == "__main__":
    main()
