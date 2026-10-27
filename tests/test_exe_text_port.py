import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_exe_text as B
from translation import load_exe

GAME = Path(os.environ.get('RE3_GAME', '/nonexistent'))  # folder with BIOHAZARD(R) 3 PC.exe and ddraw.dll


@unittest.skipUnless((GAME / 'BIOHAZARD(R) 3 PC.exe').exists(), 'set RE3_GAME')
class ExeTextTest(unittest.TestCase):
    def test_item_lookup_points_at_korean_lighter(self):
        allocation, tables, writes = load_exe()
        sites = B.sourcenext_sites((GAME / 'BIOHAZARD(R) 3 PC.exe').read_bytes(), tables, writes)
        self.assertEqual((len(sites), len(writes)), (100, 8))
        by_va = {va: (old, off) for va, old, off in sites}
        # SourceNext item lookup: mov ax,[esi*2+0x51E958]; add eax,0x51E28C
        self.assertEqual(by_va[0x431a53][0], 0x51e958)
        self.assertEqual(by_va[0x431a59][0], 0x51e28c)
        offsets, data = by_va[0x431a53][1], by_va[0x431a59][1]
        lighter = struct.unpack_from('<H', allocation, offsets + 66 * 2)[0]
        self.assertEqual(allocation[data + lighter:data + lighter + 7], bytes.fromhex('ed3eed25edcef7'))  # 라이터
        self.assertEqual(B.serialize(allocation, sites, writes)[:4], b'KRX2')
        self.assertEqual(len(B.ddraw_sites((GAME / 'ddraw.dll').read_bytes(), sites)), 15)  # REbirth's own table operands


if __name__ == '__main__':
    unittest.main()
