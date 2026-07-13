"""SQLite library. Scans library/<category>/<name>.md into a table and tracks
read position. Re-importing keeps your read positions (upsert on category+title).
"""
import os
import sqlite3
import time

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    category      TEXT NOT NULL,
    read_position INTEGER DEFAULT 0,
    date_added    TEXT,
    last_read     TEXT,
    favourite     INTEGER DEFAULT 0,
    UNIQUE(category, title)
);
"""


def connect(path=None):
    db = sqlite3.connect(path or config.DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")   # reader + importer can share the DB
    db.execute(SCHEMA)
    return db


def _title_of(md, filename):
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return os.path.splitext(filename)[0].replace("_", " ").title()


def import_dir(db, root=None):
    """Scan the library folder into the DB. Returns number of files seen."""
    root = root or config.LIBRARY_DIR
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    seen = 0
    for category in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        cdir = os.path.join(root, category)
        if not os.path.isdir(cdir):
            continue
        for fn in sorted(os.listdir(cdir)):
            if not fn.endswith(".md"):
                continue
            with open(os.path.join(cdir, fn), encoding="utf-8") as f:
                body = f.read()
            db.execute(
                """INSERT INTO articles (title, body, category, date_added)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(category, title) DO UPDATE SET body=excluded.body""",
                (_title_of(body, fn), body, category, now))
            seen += 1
    db.commit()
    return seen


# ---- queries ---------------------------------------------------------------
def categories(db):
    return [r[0] for r in db.execute(
        "SELECT DISTINCT category FROM articles ORDER BY category")]


def articles(db, category):
    return db.execute(
        "SELECT * FROM articles WHERE category=? ORDER BY title", (category,)).fetchall()


def get(db, article_id):
    return db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()


def all_articles(db):
    return db.execute(
        "SELECT id, title, category FROM articles ORDER BY category, title").fetchall()


def delete(db, article_id):
    db.execute("DELETE FROM articles WHERE id=?", (article_id,))
    db.commit()   # ponytail: leaves the .md file; re-seeding would re-add it


def recent(db, n=10):
    return db.execute(
        "SELECT * FROM articles WHERE last_read IS NOT NULL "
        "ORDER BY last_read DESC LIMIT ?", (n,)).fetchall()


def continue_reading(db):
    return db.execute(
        "SELECT * FROM articles WHERE last_read IS NOT NULL AND read_position > 0 "
        "ORDER BY last_read DESC LIMIT 1").fetchone()


def random_article(db):
    return db.execute("SELECT * FROM articles ORDER BY RANDOM() LIMIT 1").fetchone()


def set_position(db, article_id, page):
    db.execute("UPDATE articles SET read_position=?, last_read=? WHERE id=?",
               (page, time.strftime("%Y-%m-%d %H:%M:%S"), article_id))
    db.commit()


# ---- self-check ------------------------------------------------------------
def _selftest():
    db = connect(":memory:")
    db.execute("INSERT INTO articles (title, body, category) VALUES (?,?,?)",
               ("Titanic", "# Titanic\n\nText.", "History"))
    db.commit()
    assert categories(db) == ["History"]
    row = articles(db, "History")[0]
    set_position(db, row["id"], 3)
    assert get(db, row["id"])["read_position"] == 3
    assert continue_reading(db)["title"] == "Titanic"
    print("library selftest OK")


if __name__ == "__main__":
    _selftest()
