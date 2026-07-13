"""Markdown -> text, text -> paginated 1-bit images. Pure Pillow, no hardware."""
import os
import re
from PIL import Image, ImageDraw, ImageFont

import config


# ---- Markdown -> plain text ------------------------------------------------
def markdown_to_text(md):
    out = []
    for line in md.splitlines():
        s = line.rstrip()
        if s.startswith("```"):                       # code-fence markers: drop
            continue
        s = re.sub(r"^#{1,6}\s*", "", s)              # headings -> plain text
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)        # bold
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"\1", s)  # italic
        s = re.sub(r"`([^`]+)`", r"\1", s)            # inline code
        s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)  # links/images -> text
        s = re.sub(r"^\s*[-*+]\s+", "• ", s)     # bullets
        s = re.sub(r"^\s*>\s?", "", s)                # blockquote marker
        out.append(s)
    return "\n".join(out)


# ---- fonts -----------------------------------------------------------------
def load_font(size=None):
    size = size or config.FONT_SIZE
    for c in (config.FONT,
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "C:/Windows/Fonts/arial.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if c and os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()  # ponytail: bitmap fallback, ignores size


# ---- pagination ------------------------------------------------------------
def wrap_line(text, font, max_w):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines  # ponytail: one word wider than the panel overflows; fine for a reader


def paginate(text, font, width, height, margin=14, line_gap=6, reserve_lines=0):
    max_w = width - 2 * margin
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + line_gap
    per_page = max(1, (height - 2 * margin) // line_h - reserve_lines)
    wrapped = []
    for para in text.split("\n"):
        wrapped.extend(wrap_line(para, font, max_w) if para.strip() else [""])
    pages = [wrapped[i:i + per_page] for i in range(0, len(wrapped), per_page)]
    return (pages or [[""]]), line_h


def render_page(lines, font, width, height, margin=14, line_h=None, header=None):
    img = Image.new("L", (width, height), 255)
    d = ImageDraw.Draw(img)
    if line_h is None:
        a, de = font.getmetrics()
        line_h = a + de + 6
    y = margin
    if header:
        d.text((margin, y), header, font=font, fill=0)
        y += line_h
        d.line((margin, y, width - margin, y), fill=0)
        y += 8
    for ln in lines:
        d.text((margin, y), ln, font=font, fill=0)
        y += line_h
    return img


def render_menu(labels, selected, font, width, height, margin=14, title="Menu"):
    img = Image.new("L", (width, height), 255)
    d = ImageDraw.Draw(img)
    a, de = font.getmetrics()
    line_h = a + de + 12
    y = margin
    d.text((margin, y), title, font=font, fill=0)
    y += line_h
    d.line((margin, y, width - margin, y), fill=0)
    y += 8
    for i, lb in enumerate(labels):
        prefix = "→ " if i == selected else "   "   # arrow on the selected row
        d.text((margin, y), prefix + lb, font=font, fill=0)
        y += line_h
        if y > height - line_h:
            break
    return img


# ---- self-check ------------------------------------------------------------
def _selftest():
    t = markdown_to_text("# Title\n\n**bold** and *it* and `x` and [a](u)\n- one")
    assert "Title" in t and "**" not in t and "• one" in t, t
    f = load_font(20)
    pages, lh = paginate("word " * 300, f, 400, 300)
    assert len(pages) >= 2 and lh > 0
    print("renderer selftest OK")


if __name__ == "__main__":
    _selftest()
