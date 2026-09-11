"""Generate build/logo.ico from scratch with Pillow.

The repository has no original artwork, so the build pipeline synthesises a
simple brand mark (rounded dark tile with a "play/download" arrow) instead of
depending on a hand-made asset.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "build" / "logo.ico"
SIZE = 256


def _draw_logo() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = 8
    d.rounded_rectangle(
        [margin, margin, SIZE - margin, SIZE - margin],
        radius=48,
        fill=(20, 20, 26, 255),
    )

    cx, cy = SIZE / 2, SIZE / 2
    bar_w, bar_h = 36, 104
    tri = 72
    d.rounded_rectangle(
        [cx - bar_w / 2, cy - bar_h / 2, cx + bar_w / 2, cy + bar_h / 2],
        radius=18,
        fill=(255, 45, 85, 255),
    )
    d.polygon(
        [
            (cx + bar_w / 2 + 6, cy - tri * 0.45),
            (cx + bar_w / 2 + 6 + tri * 0.55, cy),
            (cx + bar_w / 2 + 6, cy + tri * 0.45),
        ],
        fill=(255, 45, 85, 255),
    )
    return img


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img = _draw_logo()

    sizes = [256, 128, 64, 48, 32, 16]
    frames = [img.resize((s, s), Image.LANCZOS) for s in sizes]
    frames[0].save(
        OUT,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"[icon] written {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())