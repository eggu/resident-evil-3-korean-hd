import json
import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_exe_text as B

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(os.environ.get('RE3_GAME', '/nonexistent'))  # folder with BIOHAZARD(R) 3 PC.exe and ddraw.dll
KRP = ROOT / 'work/extracted/korean_bio3_pc.bin'


PLAN = json.loads((ROOT / 'translation/exe-port-plan.json').read_text())


@unittest.skipUnless(KRP.exists() and (GAME / 'BIOHAZARD(R) 3 PC.exe').exists(), 'set RE3_GAME and run tools/setup.py first')
class ExeTextPortTest(unittest.TestCase):
    @unittest.skipUnless((GAME / 'Bio3_PC.exe').exists(), 'GOG/Steam Bio3_PC.exe absent')
    def test_plan_matches_content_port(self):
        sn = (GAME / 'BIOHAZARD(R) 3 PC.exe').read_bytes()
        steam = B.port(KRP.read_bytes(), (GAME / 'Bio3_PC.exe').read_bytes(), sn)
        self.assertEqual(steam[:3], B.port(KRP.read_bytes(), None, sn, PLAN)[:3])
        self.assertEqual(steam[3], PLAN)

    def test_port_redirects_item_lookup_to_korean_lighter(self):
        allocation, sites, writes, _ = B.port(KRP.read_bytes(), None, (GAME / 'BIOHAZARD(R) 3 PC.exe').read_bytes(), PLAN)
        self.assertEqual((len(sites), len(writes)), (100, 8))
        by_va = {va: (old, off) for va, old, off in sites}
        # SourceNext item lookup: mov ax,[esi*2+0x51E958]; add eax,0x51E28C
        self.assertEqual(by_va[0x431a53][0], 0x51e958)
        self.assertEqual(by_va[0x431a59][0], 0x51e28c)
        offsets, data = by_va[0x431a53][1], by_va[0x431a59][1]
        lighter = struct.unpack_from('<H', allocation, offsets + 66 * 2)[0]
        self.assertEqual(allocation[data + lighter:data + lighter + 7], bytes.fromhex('ed3eed25edcef7'))  # 라이터
        blob = B.serialize(allocation, sites, writes)
        self.assertEqual(blob[:4], b'KRX2')
        dd = B.ddraw_sites((GAME / 'ddraw.dll').read_bytes(), sites)
        self.assertEqual(len(dd), 15)  # REbirth re-writes and indexes these tables itself


if __name__ == '__main__':
    unittest.main()
