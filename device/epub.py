"""Read an EPUB with the standard library: title, plain text (spine order), cover.

An EPUB is a zip of XHTML. We can't render HTML on the e-ink, so we pull the text
out — same idea as the Wikipedia importer. library.py calls this to convert a
dropped-in .epub to Markdown, then deletes the .epub.
"""
import os
import posixpath
import re
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

_CONTAINER = "META-INF/container.xml"


class _Text(HTMLParser):
    SKIP = {"script", "style", "head"}
    BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr", "blockquote"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if self.skip == 0:
            self.parts.append(data)


def _html_to_text(data):
    p = _Text()
    try:
        p.feed(data.decode("utf-8", "replace"))
    except Exception:
        return ""
    text = re.sub(r"[ \t]+", " ", "".join(p.parts))
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _opf(z):
    """Return (opf_tree_no_ns, base_dir)."""
    root = ET.fromstring(z.read(_CONTAINER))
    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    full = root.find(".//c:rootfile", ns).get("full-path")
    tree = ET.fromstring(z.read(full))
    for e in tree.iter():
        e.tag = e.tag.split("}")[-1]               # strip namespaces
    return tree, posixpath.dirname(full)


def read(path):
    """(title, text) — chapters concatenated in spine order."""
    with zipfile.ZipFile(path) as z:
        tree, base = _opf(z)
        title = next((t.text.strip() for t in tree.iter("title") if t.text and t.text.strip()),
                     None)
        manifest = {it.get("id"): it.get("href") for it in tree.iter("item")}
        chunks = []
        for ref in tree.iter("itemref"):
            href = manifest.get(ref.get("idref"))
            if not href:
                continue
            full = posixpath.normpath(posixpath.join(base, href))
            try:
                txt = _html_to_text(z.read(full))
            except KeyError:
                continue
            if txt:
                chunks.append(txt)
    title = title or os.path.splitext(os.path.basename(path))[0].replace("_", " ").title()
    return title, "\n\n".join(chunks)


def cover_bytes(path):
    """Raw bytes of the cover image, or None."""
    with zipfile.ZipFile(path) as z:
        tree, base = _opf(z)
        items = {it.get("id"): (it.get("href"), it.get("properties") or "")
                 for it in tree.iter("item")}
        cid = next((i for i, (h, props) in items.items() if "cover-image" in props), None)
        if not cid:
            cid = next((m.get("content") for m in tree.iter("meta")
                        if m.get("name") == "cover"), None)
        if not cid:
            cid = next((i for i in items if "cover" in i.lower()), None)
        if cid and cid in items:
            full = posixpath.normpath(posixpath.join(base, items[cid][0]))
            try:
                return z.read(full)
            except KeyError:
                return None
    return None


# ---- self-check ------------------------------------------------------------
def _make_epub(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(_CONTAINER,
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
                   '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>My Test Book</dc:title></metadata>'
                   '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                   '</manifest><spine><itemref idref="c1"/></spine></package>')
        z.writestr("OEBPS/c1.xhtml",
                   "<html><body><h1>Chapter 1</h1><p>Hello book world.</p></body></html>")


def _selftest():
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "t.epub")
    _make_epub(p)
    title, text = read(p)
    assert title == "My Test Book", title
    assert "Hello book world." in text, text
    print("epub selftest OK")


if __name__ == "__main__":
    _selftest()
