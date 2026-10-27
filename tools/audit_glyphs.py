"""Report Korean glyph tokens in game text that have no HD glyph (they stay SD).

Room tables use the font of their own stage; executable strings (items, files, prompts)
can show in any stage, so they are checked against every stage. With --inherit, a token
known in stage 1 is copied into a stage map when that stage's cell bitmap is identical.
"""
import argparse
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_font_hd as F  # noqa: E402
from formats import korean_rooms, message_glyphs, room_messages  # noqa: E402
from translation import build_files  # noqa: E402

ROOT = F.ROOT
TOKENS, STAGE_TOKENS = ROOT / 'translation/glyph-tokens.json', ROOT / 'translation/glyph-stage-tokens.json'
STAGE_LEADS = (0xEB, 0xEC, 0xEF, 0xF0)  # tpage 0x1D, replaced per stage; ED/EE are always TEXJ
LAYER = {0xEB: (1, 0, 0), 0xEC: (1, 0, 14), 0xEF: (1, 2, 0), 0xF0: (1, 2, 14)}  # page, shift, row base


def tokens_in(data):
    i = 0
    while i + 1 < len(data):
        if 0xEB <= data[i] <= 0xF0:
            yield f'{data[i]:02X}{data[i + 1]:02X}'
            i += 2
        else:
            i += 1


def stage_pages(texj, krf2):
    """Stage number -> nibble page for tpage 0x1D (stage 1 is TEXJ itself)."""
    words, _ = F.load_texj(texj.read_bytes())
    words = F.apply_font_runs(words, krf2)
    pages = {1: F.nibbles(words, 1)}
    for n in range(2, 8):
        variant = words.copy()
        variant[:, 64:128] = F.tim_words(F.patched_file((texj.parent / f'FONTST{n}J.TIM').read_bytes(), krf2, f'fontst{n}j.tim'))
        pages[n] = F.nibbles(variant, 1)
    return pages


def cell(page, token):
    lead, code = int(token[:2], 16), int(token[2:], 16)
    _, shift, base = LAYER[lead]
    u, v = (code % 18) * F.CELL, ((code // 18 + base) * F.CELL) & 255
    return ((page[[(v + i) & 255 for i in range(F.CELL)], u:u + F.CELL] >> shift) & 3).tobytes()


def inherit(base, stages, pages):
    added = 0
    for n, mapping in stages.items():
        for token, text in base.items():
            if int(token[:2], 16) in STAGE_LEADS and token not in mapping:
                sd = cell(pages[1], token)
                if any(sd) and cell(pages[int(n)], token) == sd:
                    mapping[token] = text
                    added += 1
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--texj', type=Path, default=ROOT / 'work/original/DATA_J/ETC2/TEXJ.TIM')
    parser.add_argument('--inherit', action='store_true', help='copy identical-bitmap stage 1 tokens into stage maps')
    args = parser.parse_args()
    table = json.loads(TOKENS.read_text(encoding='utf-8'))
    stage_doc = json.loads(STAGE_TOKENS.read_text(encoding='utf-8'))
    base, stages = table['tokens'], stage_doc['stages']
    pages = stage_pages(args.texj, build_files())
    if args.inherit:
        print(f'inherited {inherit(base, stages, pages)} tokens')
        STAGE_TOKENS.write_text(json.dumps(stage_doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    def known(token, stage):
        if len(token) == 2:
            return token in table['plain']
        mapping = base if stage == 1 or int(token[:2], 16) not in STAGE_LEADS else stages[str(stage)]
        return token in mapping

    missing = defaultdict(set)
    mod = args.game / 'mod_korean_hd'
    rooms = (mod / 'korean_rooms.bin').read_bytes()
    for entry in korean_rooms(rooms):
        messages = rooms[entry[4]:entry[4] + entry[5]]
        for start, end in room_messages(messages):
            for _, token in message_glyphs(messages, start, end):
                if token != '00' and not known(token, entry[0]):
                    missing[('room', entry[0])].add(token)
    exe = (mod / 'korean_exe.bin').read_bytes()
    exe_text = exe[20:20 + struct.unpack_from('<I', exe, 4)[0]]  # unparsed: offset tables give false hits
    for token in set(tokens_in(exe_text)):
        for stage in range(1, 8):
            if not known(token, stage):
                missing[('exe', stage)].add(token)
    for (source, stage), tokens in sorted(missing.items()):
        print(f'{source} stage {stage}: {len(tokens)} {" ".join(sorted(tokens))}')
    print(f'total {sum(map(len, missing.values()))}')


if __name__ == '__main__':
    main()
