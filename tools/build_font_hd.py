"""Build 4x HD replacements for the Korean font page (TEXJ, VRAM 768,256).

REbirth hashes each 256x256 texture page together with the CLUT row it is drawn
with (CRC32 of the BGRA-decoded page) and looks the key up under hires/. The
Korean glyphs are 2-bit fields stacked in the 4bpp page; a CLUT row exposes one
field, so each (page, CLUT row) pair gets its own image. Known tokens
(translation/glyph-tokens.json) are redrawn with the chosen font; everything
else is a nearest-neighbour upscale of the SD page.
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_hd import color555
from formats import korean_files
from translation import build_files

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT = ROOT / 'assets/fonts/NotoSansKR[wght].ttf'
SCALE, CELL = 4, 14
FONT_X, FONT_Y = 768, 256          # VRAM origin of TEXJ
CLUT_Y = 480
# (page, field shift) -> {lead: row base}; page 0 = tpage 0x1C, page 1 = 0x1D.
# Lead None is the plain one-byte route (Latin, digits, punctuation), rows from 2.
LAYERS = {(0, 0): {None: 2}, (0, 2): {0xED: 0, 0xEE: 14}, (1, 0): {0xEB: 0, 0xEC: 14}, (1, 2): {0xEF: 0, 0xF0: 14}}


def layer_cells(layer, tokens, plain):
    """(u, v, text) for every mapped cell of a layer."""
    for lead, base in LAYERS[layer].items():
        for code in range(256):
            text = plain.get(f'{code:02X}') if lead is None else tokens.get(f'{lead:02X}{code:02X}')
            if text:
                yield (code % 18) * CELL, ((code // 18 + base) * CELL) & 255, text


def load_texj(data):
    """TEXJ.TIM -> (256x256 u16 words, 30x32 u16 CLUT)."""
    if struct.unpack_from('<II', data, 0) != (16, 8):
        raise ValueError('TEXJ must be a 4bpp TIM with CLUT')
    size, _, _, cw, ch = struct.unpack_from('<I4H', data, 8)
    clut = np.frombuffer(data, '<u2', cw * ch, 20).reshape(ch, cw)
    pos = 8 + size
    _, x, y, w, h = struct.unpack_from('<I4H', data, pos)
    if (w, h) != (256, 256):
        raise ValueError('Unexpected TEXJ size')
    return np.frombuffer(data, '<u2', w * h, pos + 12).reshape(h, w).copy(), clut


def apply_font_runs(words, krf2):
    """Overlay the Korean patch's VRAM font runs, as the runtime upload hook does."""
    _, runs = korean_files(krf2)
    for x, y, width, _, source in runs:
        words[y - FONT_Y, x - FONT_X:x - FONT_X + width] = np.frombuffer(krf2, '<u2', width, source)
    return words


def patched_file(original, krf2, name):
    """A game file with the Korean patch's byte runs applied (formats.korean_files)."""
    files, _ = korean_files(krf2)
    data = bytearray(original)
    for offset, size, source in files[name]:
        data[offset:offset + size] = krf2[source:source + size]
    return bytes(data)


def tim_words(data):
    """64x256 u16 pixel words of a 4bpp stage font TIM (FONTSTnJ)."""
    pos = 8 + struct.unpack_from('<I', data, 8)[0]
    _, _, _, w, h = struct.unpack_from('<I4H', data, pos)
    if (w, h) != (64, 256):
        raise ValueError('Unexpected stage font size')
    return np.frombuffer(data, '<u2', w * h, pos + 12).reshape(h, w)


def nibbles(words, page):
    sub = words[:, page * 64:(page + 1) * 64]
    out = np.zeros((256, 256), np.uint8)
    for k in range(4):
        out[:, k::4] = (sub >> (4 * k)) & 15
    return out


def page_key(page_nibbles, palette):
    rgba = np.array([color555(int(c)) for c in palette], np.uint8)[page_nibbles]
    return f'{zlib.crc32(np.ascontiguousarray(rgba[..., [2, 1, 0, 3]]).tobytes()):08X}', rgba


def exposed_shift(palette):
    """Field shift shown by this palette, or None when it is not a single 2-bit field."""
    opaque = [bool(c) for c in palette]
    for shift in (0, 2):
        if all(opaque[v] == bool((v >> shift) & 3) for v in range(16)):
            return shift
    return None


def is_syllable(text):
    return len(text) == 1 and '\uac00' <= text <= '\ud7a3'


def draw_glyph(image, font, text, u, v, color, ink):
    """Draw text into the 4x cell at SD (u, v); rows wrap at the page edge.

    Everything uses one font size on the syllable baseline, so Latin, digits and
    punctuation keep their natural size next to Hangul. Non-syllables are centred on
    the SD glyph's ink and shrunk only when wider than the cell (composites like "(를").
    """
    side = CELL * SCALE
    tile = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    l, t, r, b = ImageDraw.Draw(tile).textbbox((0, 0), text, font=font)
    rl, rt, rr, rb = ImageDraw.Draw(tile).textbbox((0, 0), '가', font=font)
    oy = (side - (rb - rt)) / 2 - rt  # syllable baseline
    if is_syllable(text) or ink is None:
        ImageDraw.Draw(tile).text(((side - (r - l)) / 2 - l, oy), text, font=font, fill=color)
    else:
        glyph = Image.new('RGBA', (r - l + 2, side), (0, 0, 0, 0))
        ImageDraw.Draw(glyph).text((1 - l, oy), text, font=font, fill=color)
        if glyph.width > side:
            k = side / glyph.width
            glyph = glyph.resize((side, max(1, round(side * k))), Image.Resampling.LANCZOS)
        cx = (ink[0] + ink[2]) * SCALE / 2
        x = min(max(0, round(cx - glyph.width / 2)), side - glyph.width)
        tile.alpha_composite(glyph, (x, (side - glyph.height) // 2))
    size = 256 * SCALE
    x, y = u * SCALE, v * SCALE
    top = min(side, size - y)
    image.paste(tile.crop((0, 0, side, top)), (x, y))
    if top < side:
        image.paste(tile.crop((0, top, side, side)), (x, 0))


def ink_box(page_nibbles, shift, u, v):
    """SD ink bounds (x0, y0, x1, y1) of the field inside a cell, or None if empty."""
    rows = [(v + i) & 255 for i in range(CELL)]
    mask = ((page_nibbles[rows, u:u + CELL] >> shift) & 3) != 0
    if not mask.any():
        return None
    ys, xs = mask.any(1).nonzero()[0], mask.any(0).nonzero()[0]
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


def build(texj, krf2, tokens, plain, font_path, weight, font_size, output, stages=()):
    """stages: (FONTSTnJ bytes, token map) per stage 2..7; each replaces tpage 0x1D."""
    words, clut = load_texj(texj)
    words = apply_font_runs(words, krf2)
    pages = [(0, words, tokens), (1, words, tokens)]
    for stage_words, stage_tokens in stages:
        variant = words.copy()
        variant[:, 64:128] = stage_words
        pages.append((1, variant, stage_tokens))  # cells inherit only via identical bitmaps
    font = ImageFont.truetype(str(font_path), font_size)
    try:
        font.set_variation_by_axes([weight])
    except OSError:
        pass  # static font: weight is fixed by the file
    output.mkdir(parents=True, exist_ok=True)
    written = {}
    for page, page_words, page_tokens in pages:
        page_nibbles = nibbles(page_words, page)
        for row in range(clut.shape[0]):
            palette = clut[row, :16]
            shift = exposed_shift(palette)
            if (page, shift) not in LAYERS:
                continue
            key, rgba = page_key(page_nibbles, palette)
            hd = Image.fromarray(rgba, 'RGBA').resize((256 * SCALE,) * 2, Image.Resampling.NEAREST)
            color = color555(int(palette[1 << shift]))
            drawn = 0
            for u, v, text in layer_cells((page, shift), page_tokens, plain):
                ink = ink_box(page_nibbles, shift, u, v)
                hd.paste((0, 0, 0, 0), (u * SCALE, v * SCALE, (u + CELL) * SCALE, min(v + CELL, 256) * SCALE))
                if v + CELL > 256:
                    hd.paste((0, 0, 0, 0), (u * SCALE, 0, (u + CELL) * SCALE, (v + CELL - 256) * SCALE))
                draw_glyph(hd, font, text, u, v, color, ink)
                drawn += 1
            if not drawn:
                continue  # nothing mapped on this field; leave the page to REbirth
            hd.save(output / f'{key}.webp', lossless=True)
            written[key] = {'page': 0x1C + page, 'clut_row': CLUT_Y + row, 'field_shift': shift, 'glyphs': drawn}
    (output / 'font-hd.json').write_text(json.dumps(written, indent=1))
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--texj', type=Path, default=ROOT / 'work/original/DATA_J/ETC2/TEXJ.TIM')
    parser.add_argument('--tokens', type=Path, default=ROOT / 'translation/glyph-tokens.json')
    parser.add_argument('--font', type=Path, default=DEFAULT_FONT, help='TTF/OTF used for Hangul (default: Noto Sans KR)')
    parser.add_argument('--weight', type=float, default=400, help='wght axis for variable fonts (default 400 = Regular)')
    parser.add_argument('--size', type=int, default=46, help='font size in 4x pixels')
    parser.add_argument('--stage-tokens', type=Path, default=ROOT / 'translation/glyph-stage-tokens.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    table = json.loads(args.tokens.read_text(encoding='utf-8'))
    krf2 = build_files()
    stage_maps = json.loads(args.stage_tokens.read_text(encoding='utf-8'))['stages']
    stages = [(tim_words(patched_file((args.texj.parent / f'FONTST{n}J.TIM').read_bytes(), krf2, f'fontst{n}j.tim')), stage_maps[str(n)])
              for n in range(2, 8)]
    written = build(args.texj.read_bytes(), krf2, table['tokens'], table['plain'], args.font, args.weight, args.size, args.output, stages)
    print(f'{args.output}: {len(written)} page images, {sum(w["glyphs"] for w in written.values())} glyphs')


if __name__ == '__main__':
    main()
