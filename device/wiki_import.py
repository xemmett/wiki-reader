#!/usr/bin/env python3
"""Fetch a Wikipedia article -> Markdown -> library -> DB. Run on the Pi:

    python wiki_import.py "Titanic" --category history
    python wiki_import.py https://en.wikipedia.org/wiki/Apollo_11 -c science

Uses the MediaWiki plain-text extract API (stdlib only). The running reader picks
it up next time you open the Library — no restart needed.
"""
import argparse
import json
import os
import re
import urllib.parse
import urllib.request

import config
import library

UA = "Piwi/1.0 (personal offline e-reader)"


def title_from_arg(arg):
    if arg.startswith("http"):
        path = urllib.parse.urlparse(arg).path
        arg = urllib.parse.unquote(path.rsplit("/", 1)[-1])
    return arg.replace("_", " ").strip()


def fetch(title, lang="en"):
    params = {"action": "query", "prop": "extracts", "explaintext": 1,
              "redirects": 1, "format": "json", "titles": title}
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    page = next(iter(data["query"]["pages"].values()))
    if "missing" in page or not page.get("extract"):
        raise SystemExit(f"No article found for: {title}")
    return page["title"], page["extract"]


def to_markdown(title, extract):
    out = [f"# {title}", ""]
    for para in extract.split("\n"):
        s = para.strip()
        if not s:
            continue
        m = re.match(r"^(=+)\s*(.*?)\s*=+$", s)   # "== Section ==" -> "## Section"
        if m:
            out += ["", "#" * min(len(m.group(1)), 6) + " " + m.group(2), ""]
        else:
            out += [s, ""]
    return "\n".join(out)


def save(category, title, md):
    d = os.path.join(config.LIBRARY_DIR, category)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, library.slugify(title) + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path


def image_url(title, lang="en"):
    params = {"action": "query", "prop": "pageimages", "piprop": "thumbnail",
              "pithumbsize": 1000, "redirects": 1, "format": "json", "titles": title}
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        page = next(iter(json.load(r)["query"]["pages"].values()))
    thumb = page.get("thumbnail")
    return thumb["source"] if thumb else None


def save_image(category, title, lang="en"):
    """Download the article's lead image as grayscale <slug>.png. Best-effort."""
    try:
        url = image_url(title, lang)
        if not url:
            return None
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("L")
        im.thumbnail((1000, 1000))
        path = library.image_file(category, title)
        im.save(path)
        return path
    except Exception:
        return None    # image is optional; never block the import on it


def main():
    ap = argparse.ArgumentParser(description="Import a Wikipedia article into Piwi")
    ap.add_argument("article", help="title or full Wikipedia URL")
    ap.add_argument("-c", "--category", default="wikipedia", help="library folder")
    ap.add_argument("-l", "--lang", default="en", help="Wikipedia language code")
    args = ap.parse_args()

    title, extract = fetch(title_from_arg(args.article), args.lang)
    path = save(args.category, title, to_markdown(title, extract))
    save_image(args.category, title, args.lang)  # best-effort cover image
    db = library.connect()
    library.import_dir(db)                       # rescan; upsert keeps read positions
    print(f"Saved '{title}' -> {path} and imported into the library.")


if __name__ == "__main__":
    # ponytail: markdown/heading conversion is the only real logic; check it.
    assert to_markdown("T", "Intro.\n\n== A ==\n\nBody.").splitlines()[0] == "# T"
    assert "## A" in to_markdown("T", "== A ==")
    main()
