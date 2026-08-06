"""
EarshotCI Slack app icon.

The mark is a quotation mark, because that is literally what /vs returns: the
competitor's own words, quoted, with a link and a capture date. Two slabs —
the second one cut short and in amber, for the half of the product that is
"no evidence found on their pages". Evidence, or honestly less than you hoped.

Rejected on the way: arcs radiating from a bar (read as a volume/speaker icon —
"earshot" is a metaphor, and taking it literally sold the wrong product), and a
magnifying glass (every search tool has one).

Sized for the real constraint — a Slack app avatar renders at ~36px in a
channel — so it is two shapes, no text, no thin strokes, and it has to hold on
both the light and dark Slack themes.

Run:  python3 design/slack_icon.py        (writes design/earshot_icon*.png)
"""

from PIL import Image, ImageDraw

S = 512
SS = 4  # supersample: Pillow's edges are aliased, so draw 4x and shrink

INK = (11, 43, 40)        # deep teal-ink — the page the evidence came from
CHALK = (244, 255, 249)   # the quote
AMBER = (255, 194, 75)    # the one that stops short

TILT = 16                 # degrees; a printer's quote leans, a pause mark doesn't
SLAB_W = 88
# Second slab deliberately shorter: the product abstains as often as it answers.
SLABS = [(147, 300, CHALK), (277, 214, AMBER)]
TOP = 110                 # x/y tuned so the tilted group sits optically centred


def _slab(x: int, height: int, colour) -> None:
    """One quote stroke: a rounded slab, tilted. Drawn on its own layer so the
    rotation antialiases against transparency rather than the background."""
    pad = 60 * SS
    w, h = SLAB_W * SS, height * SS
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    # Rounded head, squared tail — a quote glyph carries its weight at the top.
    # Inverted (flat top, round bottom) it reads as a test tube; fully rounded
    # it reads as a pill. This cut is the one that says "quotation mark".
    ImageDraw.Draw(layer).rounded_rectangle(
        [pad, pad, pad + w, pad + h], radius=(SLAB_W // 2) * SS, fill=colour + (255,),
        corners=(True, True, False, False),
    )
    layer = layer.rotate(-TILT, resample=Image.BICUBIC, expand=False)
    img.paste(layer, (x * SS - pad, TOP * SS - pad), layer)


MARK_SPAN = 0.60  # mark's longest side, as a fraction of the icon


def build(bg=INK) -> Image.Image:
    """Draw the mark on transparency, then measure and centre it. Tilted shapes
    make hand-tuned coordinates drift, and a Slack avatar is small enough that
    a few px of optical offset shows — so let the pixels decide."""
    global img
    img = Image.new("RGBA", (S * SS, S * SS), (0, 0, 0, 0))
    for x, height, colour in SLABS:
        _slab(x, height, colour)

    mark = img.crop(img.getbbox())
    scale = (S * SS * MARK_SPAN) / max(mark.size)
    mark = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)

    canvas = Image.new("RGB", (S * SS, S * SS), bg)
    canvas.paste(mark, ((S * SS - mark.width) // 2, (S * SS - mark.height) // 2), mark)
    return canvas.resize((S, S), Image.LANCZOS)


if __name__ == "__main__":
    import os
    out = os.path.dirname(os.path.abspath(__file__))

    icon = build()
    icon.save(f"{out}/earshot_icon.png")

    # Contact sheet at the sizes Slack actually renders, light and dark, so the
    # 36px case is judged rather than assumed.
    sizes = (256, 128, 64, 36, 20)
    width = 20 + sum(p + 20 for p in sizes)
    sheet = Image.new("RGB", (width, 592), (255, 255, 255))
    for band_y, bg in ((0, (255, 255, 255)), (296, (26, 29, 33))):
        band = Image.new("RGB", (width, 296), bg)
        x = 20
        for px in sizes:
            band.paste(icon.resize((px, px), Image.LANCZOS), (x, 20))
            x += px + 20
        sheet.paste(band, (0, band_y))
    sheet.save(f"{out}/earshot_icon_preview.png")

    print(f"wrote {out}/earshot_icon.png ({icon.size[0]}x{icon.size[1]})")
    print(f"wrote {out}/earshot_icon_preview.png")
