"""Port the Steam KRP1 executable-text patch to the SourceNext executable as KRX1.

The Steam installer relocates Japanese string tables into a Korean allocation and
rewrites the code operands that point at them. The same Japanese tables exist
byte-for-byte in SourceNext, so each table is matched by content, every SourceNext
.text operand pointing at it is redirected, and the count/opcode context must match
the Steam sites exactly. Gameplay code patches (the event-skip key byte) are skipped.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exe_translation import parse_krp1
from rebirth_profiles import profile

STEAM_SHA256 = '2a06b5d2d0fac49adb746a9c6e6512bfef1a9e43cb34fcdb3dd273775fc1b4c8'
SOURCENEXT_SHA256 = 'b5215af19ea062770bc1c941ea1dd17670cd86362c43a31289ff5bb0bf7e2357'
SKIPPED_CODE_WRITES = {0x43069b}  # event-skip key C->M; gameplay, not text
CONTEXT = 16


class Pe:
    def __init__(self, data):
        self.data = data
        pe = struct.unpack_from('<I', data, 0x3c)[0]
        count = struct.unpack_from('<H', data, pe + 6)[0]
        optional = struct.unpack_from('<H', data, pe + 20)[0]
        self.base = struct.unpack_from('<I', data, pe + 24 + 28)[0]
        self.sections = []
        for i in range(count):
            o = pe + 24 + optional + 40 * i
            name = data[o:o + 8].rstrip(b'\0')
            vsize, va, rsize, roff = struct.unpack_from('<IIII', data, o + 8)
            self.sections.append((name, va, rsize, roff))

    def off(self, va, size=1):
        rva = va - self.base
        for _, sva, rsize, roff in self.sections:
            if sva <= rva and rva + size <= sva + rsize:
                return roff + rva - sva
        raise ValueError(f'Unmapped VA {va:#x}')

    def va(self, off):
        for _, sva, rsize, roff in self.sections:
            if roff <= off < roff + rsize:
                return self.base + sva + off - roff
        raise ValueError(f'Unmapped offset {off:#x}')

    def read(self, va, size):
        o = self.off(va, size)
        return self.data[o:o + size]

    def text(self):
        for name, sva, rsize, roff in self.sections:
            if name == b'.text':
                return roff, roff + rsize
        raise ValueError('No .text section')


def find_unique(data, needle):
    first = data.find(needle)
    if first < 0 or data.find(needle, first + 1) >= 0:
        return None
    return first


def text_operands(pe, value):
    start, end = pe.text()
    needle = struct.pack('<I', value)
    found, pos = [], pe.data.find(needle, start, end)
    while pos >= 0:
        found.append(pos)
        pos = pe.data.find(needle, pos + 1, end)
    return found


def operand_form(ctx):
    """Instruction form owning an imm32 operand; register choice may differ between builds."""
    if ctx[1] == 0x05 or ctx[0] == 0x81 and 0xc0 <= ctx[1] <= 0xc7:
        return 'add r32,imm32'
    return ctx.hex()


def port(krp_bytes, steam_bytes, sn_bytes, plan=None):
    """Returns (allocation, sites, writes, plan). Without the Steam exe, plan (the Steam->SourceNext
    addresses an earlier run produced, no game bytes) places the tables and paired writes."""
    krp = parse_krp1(krp_bytes)
    steam, sn = (Pe(steam_bytes) if steam_bytes else None), Pe(sn_bytes)
    allocation = krp['allocation']['data']
    tables = {}
    for record in krp['writes']:
        if record['payload_kind'] != 'allocation-reference':
            continue
        old = struct.unpack('<I', record['expected'])[0]
        entry = tables.setdefault(old, {'alloc': record['allocation_source_offset'], 'sites': []})
        if entry['alloc'] != record['allocation_source_offset']:
            raise ValueError(f'Conflicting allocation offsets for {old:#x}')
        entry['sites'].append(record['target'])
    ordered = sorted(tables)
    if steam is None:
        return port_with_plan(krp, tables, sn, plan)
    # Match each Steam table in SourceNext by content; resolve misses via the neighbour delta.
    mapped = {}
    for i, old in enumerate(ordered):
        span = min((ordered[i + 1] if i + 1 < len(ordered) else old + 64) - old, 64)
        k = find_unique(sn.data, steam.read(old, max(span, 8)))
        if k is not None:
            mapped[old] = sn.va(k)
    for i, old in enumerate(ordered):
        if old in mapped:
            continue
        near = [o for o in ordered if o in mapped]
        prev = max((o for o in near if o < old), default=None)
        nxt = min((o for o in near if o > old), default=None)
        if prev is None or nxt is None or mapped[prev] - prev != mapped[nxt] - nxt:
            raise ValueError(f'Cannot place Steam table {old:#x}')
        candidate = old + mapped[prev] - prev
        if sn.read(candidate, 2) != steam.read(old, 2):
            raise ValueError(f'Neighbour-delta placement mismatch for {old:#x}')
        mapped[old] = candidate
    sites = []
    for old in ordered:
        new = mapped[old]
        steam_ctx = {operand_form(steam.read(t - 2, 2)) for t in tables[old]['sites']}
        found = text_operands(sn, new)
        if len(found) != len(tables[old]['sites']):
            raise ValueError(f'Operand count differs for {old:#x}->{new:#x}: {len(found)} vs {len(tables[old]["sites"])}')
        for off in found:
            if operand_form(sn.data[off - 2:off]) not in steam_ctx:
                raise ValueError(f'Opcode context differs at SourceNext {sn.va(off):#x}')
            sites.append((sn.va(off), new, tables[old]['alloc']))
    writes, write_map = [], {}
    for record in krp['writes']:
        if record['payload_kind'] != 'paired-data' or record['target'] in SKIPPED_CODE_WRITES:
            continue
        size, old = record['size'], record['expected']
        new_bytes = record['payload'][:size]
        k = find_unique(sn.data, steam.read(record['target'] - CONTEXT, CONTEXT) + old)
        if k is None:
            raise ValueError(f'Paired write {record["target"]:#x} has no unique SourceNext context')
        writes.append((sn.va(k + CONTEXT), old, new_bytes))
        write_map[record['target']] = sn.va(k + CONTEXT)
    plan = {'tables': {f'{o:#x}': f'{mapped[o]:#x}' for o in ordered}, 'writes': {f'{t:#x}': f'{v:#x}' for t, v in write_map.items()}}
    return allocation, sorted(sites), writes, plan


def port_with_plan(krp, tables, sn, plan):
    mapped = {int(k, 16): int(v, 16) for k, v in plan['tables'].items()}
    if set(mapped) != set(tables):
        raise ValueError('Port plan does not cover this KRP1 patch')
    sites = []
    for old, entry in tables.items():
        found = text_operands(sn, mapped[old])
        if len(found) != len(entry['sites']):
            raise ValueError(f'Operand count differs for {old:#x}->{mapped[old]:#x}')
        sites += [(sn.va(off), mapped[old], entry['alloc']) for off in found]
    writes = []
    for record in krp['writes']:
        if record['payload_kind'] != 'paired-data' or record['target'] in SKIPPED_CODE_WRITES:
            continue
        va, old = int(plan['writes'][f'{record["target"]:#x}'], 16), record['expected']
        if sn.read(va, len(old)) != old:
            raise ValueError(f'Paired write {va:#x} does not match the SourceNext executable')
        writes.append((va, old, record['payload'][:record['size']]))
    return krp['allocation']['data'], sorted(sites), writes, plan


def ddraw_sites(ddraw_bytes, sites):
    """REbirth re-writes EXE table operands and indexes tables itself; redirect its imm32s too."""
    dd = Pe(ddraw_bytes)
    alloc_of = {expected: offset for _, expected, offset in sites}
    found = []
    for value, offset in sorted(alloc_of.items()):
        for off in text_operands(dd, value):
            ctx = dd.data[off - 2:off]
            if not (ctx[1] == 0x05 or ctx[0] == 0xc7 and ctx[1] == 0x05 or
                    dd.data[off - 6:off - 4] == b'\xc7\x05'):
                raise ValueError(f'Unexpected DDraw operand form at {dd.va(off):#x}: {ctx.hex()}')
            found.append((dd.va(off) - dd.base, value, offset))
    # Globals are zero until REbirth's initializer runs; the runtime patches them only on a value match.
    for rva in profile(ddraw_bytes)['table_globals']:  # REbirth keeps some table bases in its globals
        writer = next((r for r, v, _ in found if struct.unpack_from('<I', ddraw_bytes, dd.off(dd.base + r - 4))[0] == dd.base + rva), None)
        if writer is None:
            raise ValueError(f'No DDraw writer for global {rva:#x}')
        value = next(v for r, v, _ in found if r == writer)
        found.append((rva, value, alloc_of[value]))
    return sorted(found)


# Typos in the Steam patch's own strings: (wrong, right, expected count); same length only,
# because allocation offsets are fixed.
TYPO_FIXES = [
    (bytes.fromhex('ebd6edb3'), bytes.fromhex('ebd6ed46'), 1),  # 켄드 -> 켄도 (Kendo gun shop fax)
    # leading space on the ink-ribbon typewriter prompt (Japanese has none); moved after 다 where it is invisible
    (bytes.fromhex('f6eb15ed3cf6eb39ed42ed2ced2400'), bytes.fromhex('eb15ed3cf6eb39ed42ed2ced24f600'), 1),
]


def fix_typos(allocation):
    fixed = bytes(allocation)
    for wrong, right, count in TYPO_FIXES:
        if len(wrong) != len(right) or fixed.count(wrong) != count:
            raise ValueError(f'Typo fix {wrong.hex()} does not match the allocation')
        fixed = fixed.replace(wrong, right)
    return fixed


def serialize(allocation, sites, writes, dd_sites=()):
    out = bytearray(struct.pack('<4sIIII', b'KRX2', len(allocation), len(sites), len(writes), len(dd_sites)))
    out += allocation
    for va, expected, offset in sites:
        out += struct.pack('<III', va, expected, offset)
    for va, old, new in writes:
        out += struct.pack('<II', va, len(old)) + old + new
    for rva, expected, offset in dd_sites:
        out += struct.pack('<III', rva, expected, offset)
    return bytes(out)


def main():
    import hashlib
    parser = argparse.ArgumentParser()
    parser.add_argument('--krp', type=Path, default=Path('work/extracted/korean_bio3_pc.bin'))
    parser.add_argument('--steam-exe', type=Path, help='GOG/Steam Bio3_PC.exe; refreshes the port plan (optional)')
    parser.add_argument('--plan', type=Path, default=Path(__file__).resolve().parents[1] / 'translation/exe-port-plan.json')
    parser.add_argument('--sourcenext-exe', type=Path, required=True)
    parser.add_argument('--ddraw', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    steam, sn = (args.steam_exe.read_bytes() if args.steam_exe else None), args.sourcenext_exe.read_bytes()
    if steam is not None and hashlib.sha256(steam).hexdigest() != STEAM_SHA256 or hashlib.sha256(sn).hexdigest() != SOURCENEXT_SHA256:
        raise SystemExit('Unexpected executable hash (needs the SourceNext BIOHAZARD(R) 3 PC.exe)')
    ddraw = args.ddraw.read_bytes()
    plan = None if steam else json.loads(args.plan.read_text())
    allocation, sites, writes, plan = port(args.krp.read_bytes(), steam, sn, plan)
    if steam:
        args.plan.write_text(json.dumps(plan, indent=1) + '\n')
    allocation = fix_typos(allocation)
    dd_sites = ddraw_sites(ddraw, sites)
    blob = serialize(allocation, sites, writes, dd_sites)
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(sites)} operand sites, {len(writes)} data writes, {len(dd_sites)} ddraw sites, '
          f'{len(blob)} bytes, sha256 {hashlib.sha256(blob).hexdigest()}')


if __name__ == '__main__':
    main()
