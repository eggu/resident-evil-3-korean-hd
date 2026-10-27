"""Hangul syllables the Korean patch font lacks, added for translation fixes.

translation/glyph-additions.json maps each added syllable's token to the syllable. Its cell is an
ED/EE cell (TEXJ page 0, field 2) that no Korean text used: it still held a Japanese kanji. The SD
bitmap is composed from the patch font itself, the initial+vowel part of a glyph with the same
initial and vowel over the final-consonant part of a glyph with the same vowel and final, and
written as extra font rows. The tokens are also in glyph-tokens.json, so the encoder, the HD font
and the audit treat them like the patch's own glyphs.

usage: glyph_additions.py add <syllable>...   picks free cells and records them
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ADDITIONS, TOKENS = ROOT / 'translation/glyph-additions.json', ROOT / 'translation/glyph-tokens.json'
TEXJ = ROOT / 'work/original/DATA_J/ETC2/TEXJ.TIM'
CELL, SHIFT, ROWS = 14, 2, ((0xED, 0), (0xEE, 14))


def decompose(ch):
    n = ord(ch) - 0xAC00
    return n // 588, (n % 588) // 28, n % 28


def cells():
    """(token, u, v) of every ED/EE cell on page 0."""
    for lead, base in ROWS:
        for code in range(256):
            u, v = (code % 18) * CELL, (code // 18 + base) * CELL
            if u + CELL <= 256:
                yield f'{lead:02X}{code:02X}', u, v


def bitmap(page, u, v):
    return (page[[(v + k) & 255 for k in range(CELL)], u:u + CELL] >> SHIFT) & 3


def vowel_class(jung):
    """Vowels that place the final consonant alike: vertical, horizontal, combined."""
    return 0 if jung in (0, 1, 2, 3, 4, 5, 6, 7, 20) else 1 if jung in (8, 12, 13, 17, 18) else 2


def split_col(glyph):
    """First column of the vowel in the top part of a vertical-vowel glyph (blank column before it)."""
    ink = glyph[:split_row(glyph) - 1].any(0)
    for c in range(4, 12):
        if not ink[c] and ink[:c].any() and ink[c + 1:].any():
            return c + 1
    raise ValueError('no gap between initial and vowel')


def splits_cols(glyph):
    try:
        split_col(glyph)
        return True
    except ValueError:
        return False


def split_row(glyph):
    """First row of the final consonant: just below the blank row between vowel and final."""
    ink = glyph.any(1)
    for r in range(5, 11):
        if not ink[r] and ink[:r].any() and ink[r + 1:].any():
            return r + 1
    raise ValueError('no gap between vowel and final consonant')


def splittable(glyph):
    try:
        split_row(glyph)
        return True
    except ValueError:
        return False


def top_part(glyph):
    out = glyph.copy()
    out[split_row(glyph) - 1:] = 0
    return out


def compose(ch, glyphs):
    """SD bitmap for ch from {syllable: bitmap} of the patch font: the initial+vowel part of a glyph
    with the same initial and vowel (or, for a vertical vowel, the initial of one glyph and the vowel
    of another) over the final consonant of a glyph with the same vowel (or vowel class) and final."""
    cho, jung, jong = decompose(ch)
    if not jong:
        raise ValueError(f'{ch}: only syllables with a final consonant are composed')
    has = lambda pick: [g for s, g in glyphs.items() if decompose(s)[2] and pick(*decompose(s)) and splittable(g)]  # noqa: E731
    tops = [top_part(g) for g in has(lambda c, j, f: (c, j) == (cho, jung))]
    if not tops and vowel_class(jung) == 0:
        cols = lambda gs: [g for g in gs if splits_cols(g)]  # noqa: E731
        lefts = cols(has(lambda c, j, f: c == cho and vowel_class(j) == 0))
        rights = cols(has(lambda c, j, f: j == jung))
        if lefts and rights:
            top = top_part(rights[0])
            col = split_col(rights[0])
            top[:, :col] = top_part(lefts[0])[:, :col]
            tops = [top]
    bottoms = has(lambda c, j, f: (j, f) == (jung, jong)) + has(lambda c, j, f: f == jong and vowel_class(j) == vowel_class(jung))
    if not tops or not bottoms:
        raise ValueError(f'{ch}: no glyph to take the {"initial+vowel" if not tops else "final"} from')
    out, bottom = tops[0], bottoms[0]
    b = split_row(bottom)
    out[b:] = bottom[b:]
    return out


def additions():
    return json.loads(ADDITIONS.read_text(encoding='utf-8'))['glyphs'] if ADDITIONS.exists() else {}


def font_rows(words):
    """Extra font rows (x, y, width, data) drawing the additions into TEXJ words that already carry
    the patch's runs. Bitmaps come from the patch's own Hangul glyphs (the additions excluded)."""
    from build_font_hd import FONT_X, FONT_Y, nibbles
    added = additions()
    if not added:
        return []
    page = nibbles(words, 0)
    tokens = json.loads(TOKENS.read_text(encoding='utf-8'))['tokens']
    where = {t: (u, v) for t, u, v in cells()}
    page1 = nibbles(words, 1)  # stage 1 page (EB/EC field 0, EF/F0 field 2): more donors, same font
    layers = {0xEB: (0, 0), 0xEC: (0, 14), 0xEF: (2, 0), 0xF0: (2, 14)}
    glyphs = {}
    for t, s in tokens.items():
        if t in added or len(s) != 1 or not '가' <= s <= '힣':
            continue
        if t in where:
            glyphs.setdefault(s, bitmap(page, *where[t]))
        elif int(t[:2], 16) in layers:
            shift, base = layers[int(t[:2], 16)]
            code = int(t[2:], 16)
            u, v = (code % 18) * CELL, (code // 18 + base) * CELL
            glyphs.setdefault(s, (page1[[(v + k) & 255 for k in range(CELL)], u:u + CELL] >> shift) & 3)
    words = words.copy()
    rows = []
    for token, ch in sorted(added.items()):
        u, v = where[token]
        glyph = compose(ch, glyphs)
        for k in range(CELL):
            y = (v + k) & 255
            for x in range(u, u + CELL):
                word, nib = divmod(x, 4)
                shift = nib * 4 + SHIFT
                words[y, word] = (int(words[y, word]) & ~(3 << shift)) | (int(glyph[k, x - u]) << shift)
            first, last = u // 4, (u + CELL - 1) // 4
            rows.append((FONT_X + first, FONT_Y + y, last - first + 1, words[y, first:last + 1].astype('<u2').tobytes()))
    return rows


def add(syllables):
    tokens_doc = json.loads(TOKENS.read_text(encoding='utf-8'))
    tokens = tokens_doc['tokens']
    added = additions()
    taken = set(tokens.values())
    used = {(u, v & 255) for t, u, v in cells() if t in tokens}  # EE rows past 256 wrap onto ED rows
    free = [t for t, u, v in cells() if t not in tokens and (u, v & 255) not in used]
    for s in syllables:
        if s in taken:
            print(f'{s} already has a glyph')
            continue
        token = free.pop(0)
        added[token] = tokens[token] = s
        taken.add(s)
        print(f'{s} -> {token}')
    ADDITIONS.write_text(json.dumps({'_note': 'Hangul syllables added to the patch font (see tools/glyph_additions.py).',
                                     'glyphs': dict(sorted(added.items()))}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    TOKENS.write_text(json.dumps(tokens_doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1:2] != ['add']:
        sys.exit(__doc__)
    add(sys.argv[2:])
