"""HD versions of full-screen pictures the Korean patch writes text into (translation/screens.json).

REbirth keys a 320x240 screen by the CRC32 of its BGRA image (16-bit colour c -> c<<3 | c>>2,
pure black stored as B=1) and loads hires/bgd/<key>.webp. Each HD picture starts from the HD
pack's version of the screen, removes its text (from another language version where that one has
none, else by filling from the surroundings) and draws the Korean lines.
"""
import argparse
import json
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
TEXT_LUMA, GROW, SMOOTH = 110, 6, 150  # text pixels are bright; grow the mask over their dark outline/antialiasing
SD_GROW = 10  # HD text carries a drop shadow a few pixels beyond the SD glyph


def screen_key(raw, offset=20, width=320, height=240):
    """REbirth bgd320 key of a 16-bit TIM image."""
    px = np.frombuffer(raw, dtype='<u2', count=width * height, offset=offset).reshape(height, width)
    c = np.stack([px & 31, (px >> 5) & 31, (px >> 10) & 31], -1)
    rgb = ((c << 3) | (c >> 2)).astype(np.uint8)
    rgb[(rgb == 0).all(-1)] = (1, 0, 0)
    bgra = np.dstack([rgb[..., 2], rgb[..., 1], rgb[..., 0], np.full((height, width), 255, np.uint8)])
    return f'{zlib.crc32(bgra.tobytes()):08X}'


def grow(mask, n):
    out = mask.copy()
    for _ in range(n):
        out[1:] |= out[:-1].copy(); out[:-1] |= out[1:].copy()
        out[:, 1:] |= out[:, :-1].copy(); out[:, :-1] |= out[:, 1:].copy()
    return out


def text_mask(rgb, box):
    x0, y0, x1, y1 = box
    mask = np.zeros(rgb.shape[:2], bool)
    mask[y0:y1, x0:x1] = rgb[y0:y1, x0:x1].mean(-1) > TEXT_LUMA
    return grow(mask, GROW)


def sd_rgb(raw, offset):
    px = np.frombuffer(raw, dtype='<u2', count=320 * 240, offset=offset).reshape(240, 320)
    c = np.stack([px & 31, (px >> 5) & 31, (px >> 10) & 31], -1)
    return ((c << 3) | (c >> 2)).astype(np.uint8)


def replaced_text_mask(original, korean, offset):
    """HD mask of the original's white text pixels that the Korean patch painted over (SD x4)."""
    a, b = sd_rgb(original, offset), sd_rgb(korean, offset)
    white = (a.min(-1) > 150) & (a.max(-1).astype(int) - a.min(-1) < 60)
    mask = white & (a != b).any(-1)
    return grow(np.kron(mask, np.ones((4, 4), bool)), SD_GROW)


def fill_in(rgb, hole):
    """Fill hole pixels from their known neighbours, ring by ring."""
    out, known = rgb.astype(float), ~hole
    while not known.all():
        total, count = np.zeros_like(out), np.zeros(known.shape)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            k = np.roll(known, (dy, dx), (0, 1))
            total += np.roll(out, (dy, dx), (0, 1)) * k[..., None]
            count += k
        ring = ~known & (count > 0)
        out[ring] = total[ring] / count[ring][:, None]
        known = known | ring
    for _ in range(SMOOTH):  # relax the hole towards its border so fills read as soft shading
        avg = (np.roll(out, 1, 0) + np.roll(out, -1, 0) + np.roll(out, 1, 1) + np.roll(out, -1, 1)) / 4
        out[hole] = avg[hole]
    return out.astype(np.uint8)


def block_lines(block):
    """A left-aligned paragraph: one line per entry, `pitch` pixels apart from `y`."""
    if not block:
        return []
    return [{'text': text, 'x': block['x'], 'y': block['y'] + i * block['pitch'], 'size': block['size'], 'align': 'left'}
            for i, text in enumerate(block['lines'])]


def draw_lines(image, lines, font_path):
    draw = ImageDraw.Draw(image)
    for line in lines:
        font = ImageFont.truetype(str(font_path), line['size'])
        anchor = 'lm' if line.get('align') == 'left' else 'mm'
        draw.text((line['x'], line['y']), line['text'], font=font, anchor=anchor, fill=(255, 255, 255),
                  stroke_width=max(2, line['size'] // 14), stroke_fill=(0, 0, 0))


def build(screen, game, font_path):
    hd = lambda key: np.asarray(Image.open(game / f'hires/bgd/{key}.webp').convert('RGB'))  # noqa: E731
    base = hd(screen['base']).copy()
    alts = [hd(key) for key in screen.get('alts', [])]
    hole = np.zeros(base.shape[:2], bool)
    for box in screen.get('erase', []):
        mask = text_mask(base, box)
        for alt in alts:  # same picture, text elsewhere
            usable = mask & ~text_mask(alt, box)
            base[usable] = alt[usable]
            mask &= ~usable
        hole |= mask
    if screen.get('mask') == 'sd':
        original = (ROOT / 'work/original' / screen['source']).read_bytes()
        hole |= replaced_text_mask(original, (game / 'mod_korean_hd' / screen['source']).read_bytes(), screen.get('offset', 0) + 20)
    base = fill_in(base, hole)
    for x0, y0, x1, y1 in screen.get('fill', []):
        base[y0:y1, x0:x1] = 0
    image = Image.fromarray(base)
    draw_lines(image, screen.get('lines', []) + block_lines(screen.get('block')), font_path)
    key = screen.get('key') or screen_key((game / 'mod_korean_hd' / screen['source']).read_bytes(), screen.get('offset', 0) + 20)
    return key, image


def build_texture(texture, game, font_path):
    """A text texture (e.g. the ending news report) redrawn at 4x, saved under every key route it may
    take: the 256x256 VRAM page with the DLL-cleared rows below (as documents), the BGRA crop and
    the PNG sentinel key. Unused keys are never looked up."""
    from build_doc_pages import LOWER, bgra
    from build_hd import png_texture_key, tim
    sd = tim((game / 'mod_korean_hd' / texture['source']).read_bytes(), texture['offset'])[0].convert('RGBA')
    width, height = sd.size
    image = Image.new('RGBA', (width * 4, height * 4))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), texture['size'])
    for i, text in enumerate(texture['lines']):
        draw.text((texture['x'], texture['y'] + i * texture['pitch']), text, font=font, anchor='lm',
                  fill=tuple(texture['fill']), stroke_width=texture['stroke_width'], stroke_fill=tuple(texture['stroke']))
    rgba = np.asarray(sd)
    page = Image.new('RGBA', (1024, 1024))
    page.paste(image, (0, 0))
    images = {f'{zlib.crc32(bgra(rgba) + LOWER):08X}': page, f'{zlib.crc32(sd.tobytes("raw", "BGRA")):08X}': image,
              png_texture_key(sd): image}
    if texture.get('page'):
        captured = Image.open(ROOT / texture['page']).convert('RGBA')
        if captured.size != (256, 256) or captured.crop((0, 0, width, height)).tobytes() != sd.tobytes():
            raise ValueError('Captured text page does not match the installed SD texture')
        key = f'{zlib.crc32(captured.tobytes("raw", "BGRA")):08X}'
        # shortcut: one captured VRAM layout; add another capture if a different ending uses another key.
        replacement = captured.resize((1024, 1024), Image.Resampling.NEAREST)
        replacement.paste(image, (0, 0))
        images[key] = replacement
    return images


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--font', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    doc = json.loads((ROOT / 'translation/screens.json').read_text(encoding='utf-8'))
    (args.output / 'bgd').mkdir(exist_ok=True)
    (args.output / 'misc').mkdir(exist_ok=True)
    for screen in doc['screens']:
        key, image = build(screen, args.game, args.font)
        image.save(args.output / f'bgd/{key}.webp', lossless=True)
        print(f'{screen["name"]}: {key}')
    for texture in doc.get('textures', []):
        images = build_texture(texture, args.game, args.font)
        for key, image in images.items():
            image.save(args.output / f'misc/{key}.webp', lossless=True)
        print(f'{texture["name"]}: {", ".join(images)}')


if __name__ == '__main__':
    main()
