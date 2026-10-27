"""The mod's own translation data (translation/text, translation/graphics) and the runtime
files built from it.

Text is stored as readable strings. Glyphs come from the glyph maps (glyph-tokens.json,
glyph-stage-tokens.json); F6 is a space, FC a line break, and every other byte (control codes,
00 padding, glyphs without a unique character) is written as {hex}. Encoding a string gives the
exact game bytes back.
"""
import json
import re
import struct
from pathlib import Path

from formats import text_units

ROOT = Path(__file__).resolve().parents[1]
TEXT, GRAPHICS = ROOT / 'translation/text', ROOT / 'translation/graphics'
STAGE_LEADS = (0xEB, 0xEC, 0xEF, 0xF0)  # tpage 0x1D, replaced per stage; ED/EE always come from TEXJ
ESCAPE = re.compile(r'\{([0-9A-F]+)\}')


class Codec:
    """Glyph text <-> bytes for one stage (exe strings use stage 1)."""

    def __init__(self, stage):
        tokens = json.loads((ROOT / 'translation/glyph-tokens.json').read_text(encoding='utf-8'))
        stages = json.loads((ROOT / 'translation/glyph-stage-tokens.json').read_text(encoding='utf-8'))['stages']
        glyphs = {bytes.fromhex(k): v for k, v in tokens['plain'].items()}
        for k, v in tokens['tokens'].items():
            if stage == 1 or int(k[:2], 16) not in STAGE_LEADS:
                glyphs[bytes.fromhex(k)] = v
        if stage != 1:
            glyphs.update({bytes.fromhex(k): v for k, v in stages[str(stage)].items()})
        by_text = {}
        for code, text in glyphs.items():
            by_text.setdefault(text, []).append(code)
        # a character shared by several glyphs is written as itself only for its first code
        # (plain, then ED/EE, then the stage page); the others stay {hex}
        rank = lambda code: (len(code), code[0] in STAGE_LEADS, code)  # noqa: E731
        self.code_of = {t: min(codes, key=rank) for t, codes in by_text.items() if not set(t) & set('{} \n')}
        self.text_of = {c: t for t, c in self.code_of.items()}
        self.longest = max(map(len, self.code_of))

    def units(self, data):
        return (unit for _, unit in text_units(data))

    def decode(self, data, literal=()):
        out = []
        for unit in self.units(data):
            if unit == b'\xf6':
                out.append(' ')
            elif unit == b'\xfc':
                out.append('\n')
            elif unit in self.text_of and unit not in literal:
                out.append(self.text_of[unit])
            else:
                out.append('{' + unit.hex().upper() + '}')
        text = re.sub(r'(?:\{00\})+', lambda m: '{' + '00' * (len(m.group()) // 4) + '}', ''.join(out))  # padding runs
        if self.encode(text) != data:  # a multi-character glyph (S., (를) was split differently
            multi = {u for u in self.units(data) if len(self.text_of.get(u, '')) > 1}
            if multi - set(literal):
                return self.decode(data, set(literal) | multi)
            raise ValueError(f'Cannot write {data.hex()} as text')
        return text

    def encode(self, text):
        out, i = bytearray(), 0
        while i < len(text):
            m = ESCAPE.match(text, i)
            if m:
                out += bytes.fromhex(m.group(1))
                i = m.end()
            elif text[i] == ' ':
                out.append(0xF6)
                i += 1
            elif text[i] == '\n':
                out.append(0xFC)
                i += 1
            else:
                for n in range(min(self.longest, len(text) - i), 0, -1):
                    if text[i:i + n] in self.code_of:
                        out += self.code_of[text[i:i + n]]
                        i += n
                        break
                else:
                    raise ValueError(f'No glyph for {text[i]!r} in {text!r}')
        return bytes(out)


def room_table(messages):
    """Room message table: little-endian offsets, then the messages."""
    offsets, pos = [], 2 * len(messages)
    for m in messages:
        offsets.append(pos)
        pos += len(m)
    return struct.pack(f'<{len(offsets)}H', *offsets) + b''.join(messages)


def build_rooms():
    """korean_rooms.bin (KRM3) from translation/text/rooms.json."""
    rooms = json.loads((TEXT / 'rooms.json').read_text(encoding='utf-8'))['rooms']
    codecs = {}
    tables = []
    for room in rooms:
        codec = codecs.setdefault(room['stage'], Codec(room['stage']))
        tables.append(room_table([codec.encode(m) for m in room['messages']]))
    header = b'KRM3' + struct.pack('<I', len(rooms))
    pos, entries, body = len(header) + 32 * len(rooms), b'', b''
    for room, table in zip(rooms, tables):
        entries += struct.pack('<8I', room['stage'], room['checksum'], room['size'], room['offset_hash'],
                               pos + len(body), len(table), pos + len(body) + len(table), 0)
        body += table
    return header + entries + body


def load_exe():
    """(allocation, tables, writes) from translation/text/exe.json: tables are (SourceNext table VA,
    allocation offset, operand count), writes (SourceNext VA, expected, new bytes)."""
    doc = json.loads((TEXT / 'exe.json').read_text(encoding='utf-8'))
    codec = Codec(1)
    allocation = b''
    for segment in doc['allocation']:
        data = codec.encode(''.join(segment['text']))
        if len(data) != segment['size']:
            raise ValueError(f'exe text at {segment["offset"]:#x} must stay {segment["size"]} bytes (now {len(data)})')
        if len(allocation) != segment['offset']:
            raise ValueError(f'exe text segments are not contiguous at {segment["offset"]:#x}')
        allocation += data
    tables = [(int(t['sourcenext'], 16), t['offset'], t['operands']) for t in doc['tables']]
    writes = [(int(w['sourcenext'], 16), bytes.fromhex(w['expected']), bytes.fromhex(w['new'])) for w in doc['writes']]
    return allocation, tables, writes


def build_files():
    """korean_files.bin (KRF2) from translation/graphics: Korean pixel runs per game file and the
    Hangul font rows uploaded to VRAM."""
    index = json.loads((GRAPHICS / 'index.json').read_text())
    data = (GRAPHICS / 'data.bin').read_bytes()
    files = sorted(index['files'].items())
    runs = [run for _, file_runs in files for run in file_runs]
    head = 12 + 40 * len(files) + 12 * len(runs) + 12 * len(index['fonts'])
    out = bytearray(b'KRF2' + struct.pack('<II', len(files), len(index['fonts'])))
    start = 0
    for name, file_runs in files:
        out += struct.pack('<32sII', name.encode('ascii'), start, len(file_runs))
        start += len(file_runs)
    for offset, size, source in runs:
        out += struct.pack('<III', offset, size, head + source)
    for x, y, width, reserved, source in index['fonts']:
        out += struct.pack('<HHHHI', x, y, width, reserved, head + source)
    return bytes(out + data)
