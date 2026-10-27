"""One-time import of the Korean patch v1.0.15 into the mod's own translation data.

Writes translation/text/rooms.json, translation/text/exe.json and translation/graphics/, and
checks that rebuilding from them gives the patch's bytes back. Build scripts read only these.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exe_translation import parse_krp1  # noqa: E402
from formats import extract_installer, korean_files, korean_rooms  # noqa: E402
from translation import GRAPHICS, ROOT, TEXT, Codec, build_files, build_rooms, load_exe, room_table  # noqa: E402

PATCH_PAYLOADS = {  # Korean patch v1.0.15
    'korean_files.bin': '64c709967abf63fd4bb16bbbb2b95c256a6506abfc6c86334b1f4b9d3347f1c9',
    'korean_rooms.bin': '42067376de0d3a2e37830b4cbc3152d01c3894374fa6247a346a4bee8f61896b',
    'korean_bio3_pc.bin': 'e400f32c02669b2124fb91b7b430d733ac635b54f5fba0d48153998a16e3d1a3',
}
SKIPPED_CODE_WRITES = {0x43069b}  # event-skip key C->M; gameplay, not text
PLAN = ROOT / 'translation/exe-port-plan.json'  # Steam -> SourceNext addresses (no game bytes)


def write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def lines(text):
    """Split at line breaks and message ends so the JSON reads one line at a time."""
    ends = [m.end() for m in re.finditer(r'\n|\{F7\}|\{FE(?:[0-9A-F]{2})?\}', text)]
    return [text[a:b] for a, b in zip([0] + ends, ends + [len(text)]) if a < b]


def import_rooms(krm3):
    rooms = []
    for stage, checksum, size, offset_hash, offset, length, _, dynamic_count in korean_rooms(krm3):
        if dynamic_count:
            raise ValueError('KRM3 dynamic records are not supported')
        table = krm3[offset:offset + length]
        count = struct.unpack_from('<H', table)[0] // 2
        offsets = list(struct.unpack_from(f'<{count}H', table)) + [length]
        messages = [table[a:b] for a, b in zip(offsets, offsets[1:])]
        if room_table(messages) != table:
            raise ValueError(f'Room table {checksum:#x} is not a plain offset table')
        codec = Codec(stage)
        rooms.append({'stage': stage, 'checksum': checksum, 'size': size, 'offset_hash': offset_hash,
                      'messages': [codec.decode(m) for m in messages]})
    return rooms


def import_exe(krp_bytes):
    krp, plan = parse_krp1(krp_bytes), json.loads(PLAN.read_text())
    allocation = krp['allocation']['data']
    tables = {}
    for record in krp['writes']:
        if record['payload_kind'] == 'allocation-reference':
            old = struct.unpack('<I', record['expected'])[0]
            table = tables.setdefault(old, {'offset': record['allocation_source_offset'], 'operands': 0})
            table['operands'] += 1
    table_list = [{'sourcenext': plan['tables'][f'{old:#x}'], **tables[old]} for old in sorted(tables)]
    writes = [{'sourcenext': plan['writes'][f'{r["target"]:#x}'], 'expected': r['expected'].hex(), 'new': r['payload'][:r['size']].hex()}
              for r in krp['writes'] if r['payload_kind'] == 'paired-data' and r['target'] not in SKIPPED_CODE_WRITES]
    cuts = sorted({0, *(t['offset'] for t in table_list), len(allocation)})
    codec = Codec(1)
    segments = [{'offset': a, 'size': b - a, 'text': lines(codec.decode(allocation[a:b]))} for a, b in zip(cuts, cuts[1:])]
    doc = {'_note': 'Executable strings (items, files, prompts). Each segment must keep its byte size; '
                    'tables point into the allocation at fixed offsets.',
           'allocation': segments, 'tables': table_list, 'writes': writes}
    return doc, allocation


def import_graphics(krf2):
    file_runs, fonts = korean_files(krf2)
    data, index = bytearray(), {'files': {}, 'fonts': []}
    for name, runs in sorted(file_runs.items()):
        index['files'][name] = []
        for offset, size, source in runs:
            index['files'][name].append([offset, size, len(data)])
            data += krf2[source:source + size]
    for x, y, width, reserved, source in fonts:
        index['fonts'].append([x, y, width, reserved, len(data)])
        data += krf2[source:source + width * 2]
    return index, bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--patch', type=Path, required=True, help='BIOHAZARD3_Korean_Patch.exe (v1.0.15)')
    args = parser.parse_args()
    payloads = extract_installer(args.patch.read_bytes())
    for name, digest in PATCH_PAYLOADS.items():
        if hashlib.sha256(payloads[name]).hexdigest() != digest:
            raise SystemExit(f'error: {args.patch.name} is not Korean patch v1.0.15 ({name} differs)')
    rooms = import_rooms(payloads['korean_rooms.bin'])
    write_json(TEXT / 'rooms.json', {'_note': 'Room dialogue per RDT message table (stage, CRC32 and size of the '
                                     'Japanese table). Messages may change length.', 'rooms': rooms})
    exe, allocation = import_exe(payloads['korean_bio3_pc.bin'])
    write_json(TEXT / 'exe.json', exe)
    index, data = import_graphics(payloads['korean_files.bin'])
    GRAPHICS.mkdir(parents=True, exist_ok=True)
    rows = [f' {json.dumps(name)}: {json.dumps(runs)}' for name, runs in index['files'].items()]
    (GRAPHICS / 'index.json').write_text('{"_note": "Korean pixel runs [offset in the game file, size, offset in data.bin] and Hangul '
                                         'font rows [x, y, width, reserved, offset] uploaded to VRAM.",\n"files": {\n' + ',\n'.join(rows)
                                         + '\n},\n"fonts": ' + json.dumps(index['fonts']) + '}\n')
    (GRAPHICS / 'data.bin').write_bytes(data)
    # the build must give the patch's bytes back
    original = korean_rooms(payloads['korean_rooms.bin'])
    rebuilt = build_rooms()
    for a, b in zip(original, korean_rooms(rebuilt)):
        if a[:4] != b[:4] or payloads['korean_rooms.bin'][a[4]:a[4] + a[5]] != rebuilt[b[4]:b[4] + b[5]]:
            raise SystemExit(f'error: room {a[1]:#x} does not round-trip')
    if load_exe()[0] != allocation:
        raise SystemExit('error: executable text does not round-trip')
    if rebased(build_files()) != rebased(payloads['korean_files.bin']):
        raise SystemExit('error: graphics do not round-trip')
    print(f'{len(rooms)} rooms, {len(exe["allocation"])} exe segments, {len(index["files"])} graphics files, {len(index["fonts"])} font rows')


def rebased(krf2):
    """KRF2 content with sources replaced by the bytes they point at (layout-independent)."""
    file_runs, fonts = korean_files(krf2)
    return ({n: [(o, s, krf2[src:src + s]) for o, s, src in runs] for n, runs in file_runs.items()},
            [(x, y, w, r, krf2[src:src + w * 2]) for x, y, w, r, src in fonts])


if __name__ == '__main__':
    main()
