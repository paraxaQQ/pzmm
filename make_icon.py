"""Generate pzmm icon assets (ICO + preview PNG) — requires Pillow.

Usage:
  python make_icon.py                 # writes icon.ico (default style)
  python make_icon.py --all           # writes icon-*.ico + icon-preview.png
  python make_icon.py --style bolt    # writes icon.ico in selected style
"""
from __future__ import annotations

import argparse
import io
import os
import struct
from PIL import Image, ImageDraw, ImageFont

SIZES = [16, 32, 48, 64, 128, 256]
STYLES = ("clean", "bolt", "grid")


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _load_font(size: int):
    for fp in (
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ):
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _base_panel(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(1, size // 12)
    r = max(2, size // 5)

    top = (18, 22, 38)
    bot = (8, 10, 20)
    for y in range(size):
        t = y / max(1, size - 1)
        col = (_lerp(top[0], bot[0], t), _lerp(top[1], bot[1], t), _lerp(top[2], bot[2], t), 255)
        d.line([(0, y), (size, y)], fill=col)

    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=r,
        outline=(86, 128, 255, 210),
        width=max(1, size // 28),
    )
    strip_h = max(2, size // 14)
    d.rounded_rectangle([pad, pad, size - pad, pad + strip_h], radius=r, fill=(86, 143, 255, 255))
    return img, d, pad


def _draw_clean(size: int) -> Image.Image:
    img, d, pad = _base_panel(size)
    cx0 = pad + max(1, size // 7)
    cy0 = pad + max(1, size // 5)
    cx1 = size - pad - max(1, size // 7)
    cy1 = size - pad - max(1, size // 7)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=max(2, size // 8), fill=(20, 28, 54, 230))
    font = _load_font(max(6, int(size * 0.33)))
    if size >= 96:
        text = "PZMM"
    elif size >= 48:
        text = "PZM"
    else:
        text = "PZ"
    bbox = d.textbbox((0, 0), text, font=font)
    tx = (size - (bbox[2] - bbox[0])) // 2 - bbox[0]
    ty = (size - (bbox[3] - bbox[1])) // 2 - bbox[1] + max(1, size // 28)
    d.text((tx, ty), text, font=font, fill=(129, 180, 255, 255))
    return img


def _draw_bolt(size: int) -> Image.Image:
    img, d, pad = _base_panel(size)
    cx0 = pad + max(1, size // 6)
    cy0 = pad + max(1, size // 5)
    cx1 = size - pad - max(1, size // 6)
    cy1 = size - pad - max(1, size // 6)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=max(2, size // 8), fill=(16, 24, 52, 235))
    bolt = [
        (size * 0.55, size * 0.25),
        (size * 0.42, size * 0.52),
        (size * 0.58, size * 0.52),
        (size * 0.45, size * 0.80),
        (size * 0.64, size * 0.45),
        (size * 0.49, size * 0.45),
    ]
    d.polygon(bolt, fill=(98, 246, 183, 255))
    return img


def _draw_grid(size: int) -> Image.Image:
    img, d, pad = _base_panel(size)
    box = [pad + size // 6, pad + size // 5, size - pad - size // 6, size - pad - size // 6]
    d.rounded_rectangle(box, radius=max(2, size // 10), fill=(20, 28, 54, 235))
    cell = max(2, size // 8)
    gap = max(1, size // 26)
    start_x = box[0] + (box[2] - box[0] - (cell * 2 + gap)) // 2
    start_y = box[1] + (box[3] - box[1] - (cell * 2 + gap)) // 2
    cols = [(129, 180, 255, 255), (96, 239, 175, 255), (129, 180, 255, 255), (96, 239, 175, 255)]
    i = 0
    for ry in range(2):
        for rx in range(2):
            x = start_x + rx * (cell + gap)
            y = start_y + ry * (cell + gap)
            d.rounded_rectangle([x, y, x + cell, y + cell], radius=max(1, size // 40), fill=cols[i])
            i += 1
    return img


def make_frame(size: int, style: str) -> Image.Image:
    if style == "bolt":
        return _draw_bolt(size)
    if style == "grid":
        return _draw_grid(size)
    return _draw_clean(size)


def save_ico(frames: list[Image.Image], path: str):
    png_datas = []
    for frame in frames:
        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        png_datas.append(buf.getvalue())

    n = len(frames)
    header = struct.pack("<HHH", 0, 1, n)
    dir_entry_size = 16
    header_size = 6 + n * dir_entry_size
    offset = header_size

    entries = b""
    for frame, png in zip(frames, png_datas):
        w, h = frame.size
        entries += struct.pack(
            "<BBBBHHII",
            0 if w == 256 else w,
            0 if h == 256 else h,
            0,
            0,
            1,
            32,
            len(png),
            offset,
        )
        offset += len(png)

    with open(path, "wb") as f:
        f.write(header)
        f.write(entries)
        for png in png_datas:
            f.write(png)


def save_preview(path: str):
    preview_size = 256
    gutter = 16
    w = preview_size * len(STYLES) + gutter * (len(STYLES) + 1)
    h = preview_size + 72
    out = Image.new("RGBA", (w, h), (14, 16, 28, 255))
    d = ImageDraw.Draw(out)
    font = _load_font(24)
    sub = _load_font(16)

    for i, st in enumerate(STYLES):
        icon = make_frame(preview_size, st)
        x = gutter + i * (preview_size + gutter)
        out.paste(icon, (x, 16), icon)
        d.text((x + 8, preview_size + 28), st, font=font, fill=(190, 208, 255, 255))
        d.text((x + 8, preview_size + 52), f"icon-{st}.ico", font=sub, fill=(128, 148, 192, 255))

    out.save(path, format="PNG")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", choices=STYLES, default="clean")
    ap.add_argument("--all", action="store_true", help="Generate all variants and preview sheet.")
    args = ap.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))

    if args.all:
        for st in STYLES:
            frames = [make_frame(s, st) for s in SIZES]
            out = os.path.join(root, f"icon-{st}.ico")
            save_ico(frames, out)
            print(f"wrote {out}")
        # Keep default build target as icon.ico -> clean.
        save_ico([make_frame(s, "clean") for s in SIZES], os.path.join(root, "icon.ico"))
        save_preview(os.path.join(root, "icon-preview.png"))
        print(f"wrote {os.path.join(root, 'icon-preview.png')}")
        return

    frames = [make_frame(s, args.style) for s in SIZES]
    out = os.path.join(root, "icon.ico")
    save_ico(frames, out)
    print(f"icon.ico written -> {out} ({args.style})")


if __name__ == "__main__":
    main()

