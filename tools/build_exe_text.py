"""Executable text for the SourceNext executable as KRX2 (korean_exe.bin).

translation/text/exe.json holds the Korean string allocation and, for each string table, its
SourceNext address and how many code operands point at it. Every such .text operand is
redirected into the allocation; REbirth's own copies of the operands are found in ddraw.dll.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rebirth_profiles import profile  # noqa: E402

SOURCENEXT_SHA256 = {  # same code and data; the second only sets the 4 GB flag in the PE header
    'b5215af19ea062770bc1c941ea1dd17670cd86362c43a31289ff5bb0bf7e2357',  # SourceNext (Mulderland GOG pack)
    'f36c3e47b70f707350bbcac1a5804661dcf48b63323d609c5f0043523067b1b3',  # 4 GB patched (Mulderland BH3Launcher.exe)
}


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


def text_operands(pe, value):
    start, end = pe.text()
    needle = struct.pack('<I', value)
    found, pos = [], pe.data.find(needle, start, end)
    while pos >= 0:
        found.append(pos)
        pos = pe.data.find(needle, pos + 1, end)
    return found


def sourcenext_sites(sn_bytes, tables, writes):
    """(va, table VA, allocation offset) for every operand pointing at a translated table."""
    sn, sites = Pe(sn_bytes), []
    for va, offset, operands in tables:
        found = text_operands(sn, va)
        if len(found) != operands:
            raise ValueError(f'Operand count differs for {va:#x}: {len(found)} vs {operands}')
        sites += [(sn.va(off), va, offset) for off in found]
    for va, old, _ in writes:
        if sn.read(va, len(old)) != old:
            raise ValueError(f'Data write {va:#x} does not match the SourceNext executable')
    return sorted(sites)


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
