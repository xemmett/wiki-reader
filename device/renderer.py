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


def paginate_iter(text, font, width, height, margin=14, line_gap=6, reserve_lines=0):
    """Yield (page_lines, line_h) one page at a time — cheap to start, so a caller
    can show page 0 immediately and keep paginating a big article in the background."""
    max_w = width - 2 * margin
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + line_gap
    per_page = max(1, (height - 2 * margin) // line_h - reserve_lines)
    buf = []
    for para in text.split("\n"):
        for ln in (wrap_line(para, font, max_w) if para.strip() else [""]):
            buf.append(ln)
            if len(buf) >= per_page:
                yield buf, line_h
                buf = []
    if buf:
        yield buf, line_h


def paginate(text, font, width, height, margin=14, line_gap=6, reserve_lines=0):
    pages, line_h = [], None
    for lines, lh in paginate_iter(text, font, width, height, margin, line_gap, reserve_lines):
        pages.append(lines)
        line_h = lh
    if line_h is None:
        a, de = font.getmetrics()
        line_h = a + de + line_gap
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


def _qr_image(data):
    try:
        import qrcode
    except Exception:
        return None                    # qrcode not installed -> caller shows text only
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("L")


def render_connect(ip, W, H, font, margin=14, hotspot=None):
    """Piwi Connect screen: title, URL, and a QR code of the URL. When `hotspot`
    is (ssid, password), also show how to join the setup network."""
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    a, de = font.getmetrics()
    lh = a + de + 6
    y = margin
    d.text((margin, y), "Piwi Connect", font=font, fill=0)
    y += lh
    d.line((margin, y, W - margin, y), fill=0)
    y += 10
    if not ip:
        for t in ("", "Connect the Pi to wifi first.", "", "Back to stop."):
            d.text((margin, y), t, font=font, fill=0)
            y += lh
        return img
    if hotspot:
        d.text((margin, y), f"Join Wi-Fi: {hotspot[0]}", font=font, fill=0)
        y += lh
        d.text((margin, y), f"Password: {hotspot[1]}", font=font, fill=0)
        y += lh + 4
    url = f"http://{ip}:8000"
    d.text((margin, y), "Scan, or open:", font=font, fill=0)
    y += lh
    d.text((margin, y), url, font=font, fill=0)
    y += lh + 6
    qr = _qr_image(url)
    if qr:
        size = min(H - y - margin - lh, W - 2 * margin)   # leave room for footer
        if size > 40:
            img.paste(qr.resize((size, size), Image.NEAREST), ((W - size) // 2, y))
    d.text((margin, H - lh - 2), "Back to stop.", font=font, fill=0)
    return img


def fit_image(img, W, H, trim_max=0.20):
    """Photo-frame fit to a W×H panel (grayscale). Cover (fill, crop) if <= trim_max
    of the image would be cropped; otherwise contain (whole photo, letterboxed)."""
    img = img.convert("L")
    iw, ih = img.size
    if iw == 0 or ih == 0:
        return Image.new("L", (W, H), 255)
    cover = max(W / iw, H / ih)
    scaled_area = (iw * cover) * (ih * cover)
    trimmed = 1 - (W * H) / scaled_area if scaled_area else 1.0
    scale = cover if trimmed <= trim_max else min(W / iw, H / ih)
    nw, nh = max(1, round(iw * scale)), max(1, round(ih * scale))
    resized = img.resize((nw, nh))
    canvas = Image.new("L", (W, H), 255)
    canvas.paste(resized, ((W - nw) // 2, (H - nh) // 2))   # negative offsets clip (cover)
    return canvas


def draw_wifi(d, x, y, on=True):
    """Small wifi glyph (~16 wide) at top-left corner (x, y)."""
    cx, base = x + 8, y + 13
    if on:
        for r in (3, 7, 11):
            d.arc([cx - r, base - r, cx + r, base + r], 225, 315, fill=0)
        d.ellipse([cx - 1, base - 1, cx + 1, base + 1], fill=0)
    else:                                  # not connected: little X
        d.line([x + 1, y + 1, x + 13, y + 12], fill=0)
        d.line([x + 13, y + 1, x + 1, y + 12], fill=0)


def render_menu(labels, selected, font, width, height, margin=14, title="Menu",
                status=None):
    img = Image.new("L", (width, height), 255)
    d = ImageDraw.Draw(img)
    a, de = font.getmetrics()
    line_h = a + de + 12
    y = margin
    d.text((margin, y), title, font=font, fill=0)
    if status:                             # wifi icon + clock, top-right
        connected, timestr = status
        tw = d.textlength(timestr, font=font)
        tx = width - margin - tw
        d.text((tx, y), timestr, font=font, fill=0)
        draw_wifi(d, int(tx - 24), y, connected)
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
