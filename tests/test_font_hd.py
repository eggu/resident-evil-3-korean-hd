import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_font_hd as F

TEXJ = F.ROOT / 'work/original/DATA_J/ETC2/TEXJ.TIM'


@unittest.skipUnless(TEXJ.exists(), 'run tools/setup.py first (extracts the original TEXJ.TIM)')
class FontHdTest(unittest.TestCase):
    def test_page_keys_match_rebirth_dump(self):
        words, clut = F.load_texj(TEXJ.read_bytes())
        from translation import pack_files
        index = json.loads((F.ROOT / 'translation/graphics/index.json').read_text())
        original = pack_files(index, (F.ROOT / 'translation/graphics/data.bin').read_bytes())
        page0 = F.nibbles(F.apply_font_runs(words, original), 0)
        # Keys REbirth dumped (HDTexturesDump=1) for tpage 0x1C with CLUT rows 490 and 500.
        self.assertEqual(F.page_key(page0, clut[10, :16])[0], 'A4F04896')
        self.assertEqual(F.page_key(page0, clut[20, :16])[0], '3FE55B77')
        self.assertEqual(F.exposed_shift(clut[20, :16]), 2)

    def test_added_syllables_preserve_every_other_font_pixel(self):
        import numpy as np
        from translation import pack_files, Codec
        from glyph_additions import additions, cells
        from formats import korean_files
        index = json.loads((F.ROOT / 'translation/graphics/index.json').read_text())
        original = pack_files(index, (F.ROOT / 'translation/graphics/data.bin').read_bytes())
        words, _ = F.load_texj(TEXJ.read_bytes())
        before = F.apply_font_runs(words, original)
        after = F.apply_font_runs(words, F.build_files())
        old_page, new_page = F.nibbles(before, 0), F.nibbles(after, 0)
        allowed = np.zeros(old_page.shape, dtype=bool)
        coords = {t: (u, v) for t, u, v in cells()}
        for token, char in additions().items():
            u, v = coords[token]
            self.assertFalse(allowed[v:v + 14, u:u + 14].any())
            allowed[v:v + 14, u:u + 14] = True
            self.assertTrue(((new_page[v:v + 14, u:u + 14] >> 2) & 3).any())
            for stage in range(1, 8):
                self.assertEqual(Codec(stage).encode(char), bytes.fromhex(token))
        np.testing.assert_array_equal(old_page[~allowed], new_page[~allowed])
        np.testing.assert_array_equal(old_page & 3, new_page & 3)
        np.testing.assert_array_equal(before[:, 64:], after[:, 64:])
        updated = F.build_files()
        def file_bytes(blob):
            return {name: [(offset, blob[source:source + size]) for offset, size, source in runs]
                    for name, runs in korean_files(blob)[0].items()}
        self.assertEqual(file_bytes(original), file_bytes(updated))
        self.assertEqual(Codec(1).text_of[bytes.fromhex('EE35')], '줄')


if __name__ == '__main__':
    unittest.main()
