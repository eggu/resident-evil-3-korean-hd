"""Build KRB2: Korean glyphs and UI strings for Classic REbirth's own menus.

REbirth stores menu text as UTF-16 and encodes it through a codepoint lookup
(binary search over its own vector); codes >= 0xEA00 are emitted as two
bytes. The runtime hooks that lookup for Hangul (KRF2 font tokens) and feeds Korean
UTF-16 to REbirth's own message store instead of the Japanese text.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_exe_text import Pe
from rebirth_profiles import profile

# Non-Hangul characters that REbirth's base table already encodes.
BASE_CHARS = set(' ()/')


def message_ids(dd, store_message):
    """(id, VA) pairs from `mov edx, id; mov ecx, text; call store_message` sequences."""
    start, end = next((roff, roff + rsize) for name, _, rsize, roff in dd.sections if name == b'.text')
    found, pos = {}, dd.data.find(b'\xba', start, end)  # VA -> (id, RVA of the text imm32)
    while 0 <= pos < end - 15:
        if dd.data[pos + 5] == 0xb9 and dd.data[pos + 10] == 0xe8:
            call = dd.va(pos + 10)
            if call + 5 + struct.unpack_from('<i', dd.data, pos + 11)[0] == store_message:
                found[struct.unpack_from('<I', dd.data, pos + 6)[0]] = (struct.unpack_from('<I', dd.data, pos + 1)[0],
                                                                         dd.va(pos + 6) - dd.base)
        pos = dd.data.find(b'\xba', pos + 1, end)
    return found


def utf16_at(dd, va):
    off, chars = dd.off(va), []
    while (c := struct.unpack_from('<H', dd.data, off + 2 * len(chars))[0]):
        chars.append(chr(c))
    return ''.join(chars)


def build(ddraw_bytes, glyphs, ui):
    dd = Pe(ddraw_bytes)
    by_text = {utf16_at(dd, va): (mid, imm, va - dd.base) for va, (mid, imm) in message_ids(dd, profile(ddraw_bytes)['store_message']).items()}
    strings = []
    for source, korean in ui.items():
        if source not in by_text:
            raise ValueError(f'REbirth message not found: {source}')
        missing = {c for c in korean if c not in glyphs and c not in BASE_CHARS}
        if missing:
            raise ValueError(f'No font token for {sorted(missing)} in {korean}')
        strings.append((*by_text[source], (korean + '\0').encode('utf-16-le')))
    out = bytearray(b'KRB2' + struct.pack('<I', len(glyphs)))
    for ch, token in sorted(glyphs.items()):
        code = int(token, 16)
        if not 0xeb00 <= code <= 0xf0ff:
            raise ValueError(f'Bad token {token} for {ch}')
        out += struct.pack('<HH', ord(ch), code)
    out += struct.pack('<I', len(strings))
    for mid, imm, text_rva, text in sorted(strings):
        out += struct.pack('<IIII', mid, imm, text_rva, len(text) // 2) + text
    return bytes(out)


def load(path):
    return {k: v for k, v in json.loads(Path(path).read_text(encoding='utf-8')).items() if not k.startswith('_')}


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--ddraw', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    ddraw = args.ddraw.read_bytes()
    blob = build(ddraw, load(root / 'translation/rebirth-glyphs.json'), load(root / 'translation/rebirth-ui.json'))
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes, sha256 {hashlib.sha256(blob).hexdigest()}')


if __name__ == '__main__':
    main()
