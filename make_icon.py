"""Run once to generate icon.ico — requires Pillow."""
import io, os, struct
from PIL import Image, ImageDraw, ImageFont

SIZES = [16, 32, 48, 64, 128, 256]

def make_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = max(1, size // 10)
    r   = max(1, size // 6)

    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=r, fill="#1a1a2e")

    bar_h = max(2, size // 20)
    d.rounded_rectangle([pad, pad, size - pad, pad + bar_h], radius=r, fill="#5a8fff")

    font_size = max(6, int(size * 0.38))
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    text = "PZ"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] + max(1, size // 20)
    d.text((tx, ty), text, font=font, fill="#5a8fff")

    sub_size = max(4, int(size * 0.18))
    try:
        sub_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", sub_size)
    except Exception:
        sub_font = ImageFont.load_default()

    sub = "MM"
    sbbox = d.textbbox((0, 0), sub, font=sub_font)
    sw = sbbox[2] - sbbox[0]
    sx = (size - sw) // 2 - sbbox[0]
    sy = ty + th + max(1, size // 24)
    d.text((sx, sy), sub, font=sub_font, fill="#3a5abf")

    return img


def save_ico(frames: list[Image.Image], path: str):
    """Manually build a valid ICO file with multiple sizes."""
    png_datas = []
    for frame in frames:
        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        png_datas.append(buf.getvalue())

    n = len(frames)
    # ICO header: reserved(2) + type(2) + count(2)
    header = struct.pack("<HHH", 0, 1, n)
    # Each directory entry is 16 bytes
    dir_entry_size = 16
    header_size = 6 + n * dir_entry_size
    offset = header_size

    entries = b""
    for frame, png in zip(frames, png_datas):
        w, h = frame.size
        w_byte = 0 if w == 256 else w   # 0 means 256 in ICO spec
        h_byte = 0 if h == 256 else h
        entries += struct.pack("<BBBBHHII",
            w_byte, h_byte,
            0,          # color count (0 = no palette)
            0,          # reserved
            1,          # color planes
            32,         # bits per pixel
            len(png),   # size of image data
            offset,     # offset of image data
        )
        offset += len(png)

    with open(path, "wb") as f:
        f.write(header)
        f.write(entries)
        for png in png_datas:
            f.write(png)


frames = [make_frame(s) for s in SIZES]
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
save_ico(frames, out)

# Verify
check = Image.open(out)
print(f"icon.ico written -> {out}")
print(f"sizes: {check.info.get('sizes', check.size)}")
