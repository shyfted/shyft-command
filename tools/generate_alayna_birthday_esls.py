#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SIZE = (1600, 1200)
PALETTE = [(255, 255, 255), (0, 0, 0), (255, 0, 0), (255, 255, 0), (0, 0, 255), (0, 128, 0)]
FONT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
OUT = Path(__file__).resolve().parents[1] / "generated_media"


def fit_background(path):
    image = Image.open(path).convert("RGB")
    scale = max(SIZE[0] / image.width, SIZE[1] / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - SIZE[0]) // 2
    top = (resized.height - SIZE[1]) // 2
    return resized.crop((left, top, left + SIZE[0], top + SIZE[1]))


def quantize(image):
    palette = Image.new("P", (1, 1))
    raw = [channel for colour in PALETTE for channel in colour] + [0] * (768 - len(PALETTE) * 3)
    palette.putpalette(raw)
    return image.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")


def centered(draw, text, y, font, fill, stroke=3):
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    x = (SIZE[0] - (box[2] - box[0])) // 2
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill="white")


def showroom_1(background):
    image = fit_background(background)
    draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(FONT, 92)
    body = ImageFont.truetype(FONT, 61)
    centered(draw, "Happy Birthday Alayna!", 285, title, "#ff0000", 5)
    lines = [
        "Just because you're turning 11,",
        "doesn't mean you're a bro.",
        "Are you good?",
    ]
    colours = ["#0000ff", "#008000", "#000000"]
    for index, (line, colour) in enumerate(zip(lines, colours)):
        centered(draw, line, 440 + index * 105, body, colour, 4)
    return quantize(image)


def showroom_2(background):
    image = fit_background(background)
    draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(FONT, 78)
    body = ImageFont.truetype(FONT, 48)
    signoff = ImageFont.truetype(FONT, 44)
    centered(draw, "Happy Birthday Alayna!", 230, title, "#ff0000", 5)
    lines = [
        "We can't believe you're 11 years old already!",
        "You are such a blessing in our lives.",
        "We love you so, so much!",
        "We hope and pray God's richest blessings for you.",
    ]
    colours = ["#0000ff", "#008000", "#ff0000", "#0000ff"]
    for index, (line, colour) in enumerate(zip(lines, colours)):
        centered(draw, line, 355 + index * 80, body, colour, 3)
    centered(draw, "Love and God Bless,", 705, signoff, "#008000", 3)
    centered(draw, "Mum, Dad, Johnny, Eliana & Daphne", 772, signoff, "#000000", 3)
    centered(draw, "X0X0X", 842, ImageFont.truetype(FONT, 54), "#ff0000", 3)
    return quantize(image)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    generated = Path("/Users/katmeintjes/.codex/generated_images/01a02e7b-7394-7ff0-b61b-df8711259155")
    first = showroom_1(generated / "exec-2d6fa653-1e66-42ce-a830-a2d2705fc80b.png")
    second = showroom_2(generated / "exec-fe5e7ac3-8d3e-4bd2-85df-6545ecf18f9f.png")
    first.save(OUT / "Alayna_11th_Birthday_Showroom_1.png", optimize=True)
    second.save(OUT / "Alayna_11th_Birthday_Showroom_2.png", optimize=True)


if __name__ == "__main__":
    main()
