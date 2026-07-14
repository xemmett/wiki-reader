"""SQLite library, organised as collection -> category -> article.

On disk: library/<collection>/<category>/<slug>.md  (e.g. Wikipedia/History/titanic.md,
Books/Fiction/dune.md). EPUBs dropped in are converted to Markdown on import and the
.epub is deleted (same as wiki articles — text only, small on disk). Re-importing keeps
read positions (upsert on collection+category+title).
"""
import os
import re
import sqlite3
import time

import config


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "article"


def _cat_dir(collection, category):
    return os.path.join(config.LIBRARY_DIR, collection, category)


def image_file(collection, category, title):
    """Where an article's cover image lives (next to its .md), if any."""
    return os.path.join(_cat_dir(collection, category), slugify(title) + ".png")


def all_images():
    """Every cover .png, walking collection/category/*.png."""
    root = config.LIBRARY_DIR
    out = []
    for coll in os.listdir(root) if os.path.isdir(root) else []:
        cdir = os.path.join(root, coll)
        for cat in os.listdir(cdir) if os.path.isdir(cdir) else []:
            catdir = os.path.join(cdir, cat)
            if os.path.isdir(catdir):
                out += [os.path.join(catdir, fn) for fn in os.listdir(catdir)
                        if fn.endswith(".png")]
    return out


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    collection    TEXT NOT NULL DEFAULT 'Wikipedia',
    category      TEXT NOT NULL,
    read_position INTEGER DEFAULT 0,
    date_added    TEXT,
    last_read     TEXT,
    favourite     INTEGER DEFAULT 0,
    page_count    INTEGER,          -- cached total pages for `layout`
    layout        TEXT,             -- rotation:font:WxH the count was computed for
    UNIQUE(collection, category, title)
);
"""


def connect(path=None):
    db = sqlite3.connect(path or config.DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")   # reader + importer can share the DB
    db.execute(SCHEMA)
    _migrate(db)
    return db


def _migrate(db):
    """Old single-level DBs have no `collection` column and a UNIQUE(category,title)
    constraint. Rebuild into the new shape, preserving read positions."""
    cols = [r[1] for r in db.execute("PRAGMA table_info(articles)")]
    if "collection" in cols:
        return
    db.executescript(
        "ALTER TABLE articles RENAME TO articles_old;\n" + SCHEMA +
        "INSERT INTO articles (id, title, body, collection, category, read_position,"
        " date_added, last_read, favourite)"
        " SELECT id, title, body, 'Wikipedia', category, read_position,"
        " date_added, last_read, favourite FROM articles_old;\n"
        "DROP TABLE articles_old;")
    db.commit()


def _title_of(md, filename):
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return os.path.splitext(filename)[0].replace("_", " ").title()


def _migrate_legacy_layout(root):
    """Old flat layout library/<category>/*.md -> library/Wikipedia/<category>/."""
    if not os.path.isdir(root):
        return
    import shutil
    wiki = os.path.join(root, "Wikipedia")
    for name in list(os.listdir(root)):
        d = os.path.join(root, name)
        if not os.path.isdir(d) or name == "Wikipedia":
            continue
        entries = os.listdir(d)
        has_md = any(f.endswith(".md") for f in entries)
        has_sub = any(os.path.isdir(os.path.join(d, x)) for x in entries)
        if has_md and not has_sub:                 # a bare category -> Wikipedia collection
            os.makedirs(wiki, exist_ok=True)
            dest = os.path.join(wiki, name)
            if not os.path.exists(dest):
                shutil.move(d, dest)


def _convert_epubs(root):
    """Convert any .epub to <slug>.md (+ cover), then delete the .epub to save space."""
    if not os.path.isdir(root):
        return
    for coll in os.listdir(root):
        cdir = os.path.join(root, coll)
        if not os.path.isdir(cdir):
            continue
        for cat in os.listdir(cdir):
            catdir = os.path.join(cdir, cat)
            if not os.path.isdir(catdir):
                continue
            for fn in os.listdir(catdir):
                if fn.endswith(".epub"):
                    _convert_one_epub(os.path.join(catdir, fn), catdir)


def _convert_one_epub(path, catdir):
    import epub
    try:
        title, text = epub.read(path)
    except Exception:
        return                                     # leave an unreadable epub in place
    slug = slugify(title)
    with open(os.path.join(catdir, slug + ".md"), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{text}")
    try:
        data = epub.cover_bytes(path)
        if data:
            import io
            from PIL import Image
            Image.open(io.BytesIO(data)).convert("L").save(os.path.join(catdir, slug + ".png"))
    except Exception:
        pass
    os.remove(path)                                # destroy the epub — text lives in the .md now


def import_dir(db, root=None):
    """Scan library/<collection>/<category>/*.md into the DB. Returns files seen."""
    root = root or config.LIBRARY_DIR
    _migrate_legacy_layout(root)
    _convert_epubs(root)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    seen = 0
    for coll in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        cdir = os.path.join(root, coll)
        if not os.path.isdir(cdir):
            continue
        for cat in sorted(os.listdir(cdir)):
            catdir = os.path.join(cdir, cat)
            if not os.path.isdir(catdir):
                continue
            for fn in sorted(os.listdir(catdir)):
                if not fn.endswith(".md"):
                    continue
                with open(os.path.join(catdir, fn), encoding="utf-8") as f:
                    body = f.read()
                db.execute(
                    """INSERT INTO articles (title, body, collection, category, date_added)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(collection, category, title) DO UPDATE SET
                           body=excluded.body, page_count=NULL, layout=NULL""",
                    (_title_of(body, fn), body, coll, cat, now))
                seen += 1
    db.commit()
    return seen


# ---- queries ---------------------------------------------------------------
def collections(db):
    return [r[0] for r in db.execute(
        "SELECT DISTINCT collection FROM articles ORDER BY collection")]


def categories(db, collection):
    return [r[0] for r in db.execute(
        "SELECT DISTINCT category FROM articles WHERE collection=? ORDER BY category",
        (collection,))]


def articles(db, collection, category):
    return db.execute(
        "SELECT * FROM articles WHERE collection=? AND category=? ORDER BY title",
        (collection, category)).fetchall()


def get(db, article_id):
    return db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()


def all_articles(db):
    return db.execute(
        "SELECT id, title, collection, category FROM articles "
        "ORDER BY collection, category, title").fetchall()


def _delete_files(collection, category, title):
    """Remove an article's .md (and cover .png) from disk so a re-scan can't re-add it."""
    d = _cat_dir(collection, category)
    if not os.path.isdir(d):
        return
    slug = slugify(title)
    removed = False
    for ext in (".md", ".png"):
        p = os.path.join(d, slug + ext)
        if os.path.exists(p):
            os.remove(p)
            removed = removed or ext == ".md"
    if not removed:                                # fallback: hand-named .md by heading
        for fn in os.listdir(d):
            if not fn.endswith(".md"):
                continue
            fp = os.path.join(d, fn)
            try:
                if _title_of(open(fp, encoding="utf-8").read(), fn).strip().lower() \
                        == title.strip().lower():
                    os.remove(fp)
                    png = os.path.splitext(fp)[0] + ".png"
                    if os.path.exists(png):
                        os.remove(png)
                    break
            except OSError:
                continue
    for empty in (d, os.path.dirname(d)):          # tidy empty category, then collection
        try:
            os.rmdir(empty)
        except OSError:
            pass


def delete(db, article_id):
    row = get(db, article_id)
    if row:
        _delete_files(row["collection"], row["category"], row["title"])
    db.execute("DELETE FROM articles WHERE id=?", (article_id,))
    db.commit()


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


def cached_pages(db, article_id, layout):
    row = db.execute("SELECT page_count, layout FROM articles WHERE id=?",
                     (article_id,)).fetchone()
    if row and row["layout"] == layout and row["page_count"]:
        return row["page_count"]
    return None


def set_pages(db, article_id, layout, count):
    db.execute("UPDATE articles SET page_count=?, layout=? WHERE id=?",
               (count, layout, article_id))
    db.commit()


def set_position(db, article_id, page):
    db.execute("UPDATE articles SET read_position=?, last_read=? WHERE id=?",
               (page, time.strftime("%Y-%m-%d %H:%M:%S"), article_id))
    db.commit()


# ---- self-check ------------------------------------------------------------
def _selftest():
    db = connect(":memory:")
    db.execute("INSERT INTO articles (title, body, collection, category) VALUES (?,?,?,?)",
               ("Titanic", "# Titanic\n\nText.", "Wikipedia", "History"))
    db.commit()
    assert collections(db) == ["Wikipedia"]
    assert categories(db, "Wikipedia") == ["History"]
    row = articles(db, "Wikipedia", "History")[0]
    set_position(db, row["id"], 3)
    assert get(db, row["id"])["read_position"] == 3
    assert continue_reading(db)["title"] == "Titanic"

    # import two-level + delete removes files so a re-scan can't re-add
    import tempfile
    orig = config.LIBRARY_DIR
    config.LIBRARY_DIR = tempfile.mkdtemp()
    try:
        d = os.path.join(config.LIBRARY_DIR, "Books", "Fiction")
        os.makedirs(d)
        open(os.path.join(d, "dune.md"), "w", encoding="utf-8").write("# Dune\n\nText.")
        assert import_dir(db) == 1
        row = articles(db, "Books", "Fiction")[0]
        assert row["collection"] == "Books"
        delete(db, row["id"])
        assert import_dir(db) == 0, "deleted article must not re-appear"
        assert articles(db, "Books", "Fiction") == []
    finally:
        config.LIBRARY_DIR = orig
    print("library selftest OK")


if __name__ == "__main__":
    _selftest()
