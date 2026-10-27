import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_font_hd as F

TEXJ = F.ROOT / 'work/original/DATA_J/ETC2/TEXJ.TIM'


@unittest.skipUnless(TEXJ.exists(), 'run tools/setup.py first (extracts the original TEXJ.TIM)')
class FontHdTest(unittest.TestCase):
    def test_page_keys_match_rebirth_dump(self):
        words, clut = F.load_texj(TEXJ.read_bytes())
        page0 = F.nibbles(F.apply_font_runs(words, F.build_files()), 0)
        # Keys REbirth dumped (HDTexturesDump=1) for tpage 0x1C with CLUT rows 490 and 500.
        self.assertEqual(F.page_key(page0, clut[10, :16])[0], 'A4F04896')
        self.assertEqual(F.page_key(page0, clut[20, :16])[0], '3FE55B77')
        self.assertEqual(F.exposed_shift(clut[20, :16]), 2)


if __name__ == '__main__':
    unittest.main()
