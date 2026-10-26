"""Build 4x HD texture pages for Korean documents in Japanese mode.

With JapaneseEnable=1 a document (256x176) is uploaded to the top of a 256x256 VRAM
page and REbirth keys the whole page (CRC32 of the BGRA page, ddraw 0x1008C880). The
80 rows below would hold VRAM leftovers that change with game state, so korean_hd.dll
clears them before each document upload; the key is then CRC32(document + zero rows).
The document part reuses the document HD (hires/memo, keyed by the file/*.png route); the
lower rows are never shown, so they stay transparent.
"""
import argparse
import glob
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_hd import document_images, png_texture_key, tim

ROOT = Path(__file__).resolve().parents[1]
SCALE, PAGE, DOC_H = 4, 256, 176
LOWER = bytes((PAGE - DOC_H) * PAGE * 4)  # rows the DLL clears under the document


def bgra(rgba):
    return np.ascontiguousarray(rgba[..., [2, 1, 0, 3]]).tobytes()


def documents(game):
    data_j = game / 'mod_korean_hd/DATA_J/ETC2/FILEGJ.PIX'
    docs = [np.asarray(image.convert('RGBA')) for _, image in document_images(data_j.read_bytes())]
    docs += [np.asarray(tim((game / f'mod_korean_hd/DATA_AJ/ETC2/FILEGJ0{n}.TIM').read_bytes())[0].convert('RGBA'))
             for n in range(3, 7)]  # PC play manual pages
    return [d for d in docs if d.shape == (DOC_H, PAGE, 4) and d[..., 3].any()]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    hd_index = {Path(p).stem: p for p in glob.glob(str(args.game / 'hires/*/*.webp'))}
    docs = documents(args.game)
    args.output.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    for doc in docs:
        source = hd_index.get(png_texture_key(Image.fromarray(doc, 'RGBA')))
        if source is None:
            skipped += 1
            continue
        top = Image.open(source).convert('RGBA')
        if top.size != (PAGE * SCALE, DOC_H * SCALE):
            raise ValueError(f'{source} is not a 4x document')
        hd = Image.new('RGBA', (PAGE * SCALE,) * 2)
        hd.paste(top, (0, 0))
        hd.save(args.output / f'{zlib.crc32(bgra(doc) + LOWER):08X}.webp', lossless=True)
        written += 1
    print(f'{len(docs)} documents: {written} pages, {skipped} documents without HD')


if __name__ == '__main__':
    main()
