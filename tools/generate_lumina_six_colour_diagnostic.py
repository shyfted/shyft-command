#!/usr/bin/env python3
"""Generate the deterministic source artwork for the Lumina palette check."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1600
HEIGHT = 1200
BLOCKS = (
    ("BLACK", (0, 0, 0), (255, 255, 255)),
    ("WHITE", (255, 255, 255), (0, 0, 0)),
    ("RED", (255, 0, 0), (255, 255, 255)),
    ("YELLOW", (255, 255, 0), (0, 0, 0)),
    ("BLUE", (0, 0, 255), (255, 255, 255)),
    ("GREEN", (0, 255, 0), (0, 0, 0)),
)


def font(size):
    path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def main():
    output = Path(__file__).resolve().parents[1] / "static/uploads/original/lumina-six-colour-diagnostic.png"
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    label_font = font(76)
    detail_font = font(28)
    block_width = WIDTH // 3
    block_height = HEIGHT // 2

    for index, (name, fill, text_colour) in enumerate(BLOCKS):
        column = index % 3
        row = index // 3
        left = column * block_width
        top = row * block_height
        right = WIDTH if column == 2 else left + block_width
        bottom = HEIGHT if row == 1 else top + block_height
        draw.rectangle((left, top, right, bottom), fill=fill)
        bounds = draw.textbbox((0, 0), name, font=label_font)
        x = left + ((right - left) - (bounds[2] - bounds[0])) // 2
        y = top + ((bottom - top) - (bounds[3] - bounds[1])) // 2 - 18
        draw.text((x, y), name, font=label_font, fill=text_colour)
        draw.text((left + 18, bottom - 48), "SHYFTED · LUMINA 6", font=detail_font, fill=text_colour)

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=False)
    print(output)


if __name__ == "__main__":
    main()
