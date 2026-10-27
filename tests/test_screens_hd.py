import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_screens_hd import build_texture, ROOT


class NewsPageTest(unittest.TestCase):
    def test_captured_page_preserves_other_graphics(self):
        captured = Image.open(ROOT / 'assets/screens/631B0DF5.webp').convert('RGBA')
        sd = captured.crop((0, 0, 256, 176))
        font = ROOT / 'assets/fonts/NotoSansKR[wght].ttf'
        texture = dict(source='news.tim', offset=0, x=6, y=28, pitch=64, size=46,
                       fill=[255]*4, stroke=[0, 0, 0, 255], stroke_width=4,
                       lines=['뉴스'], page='assets/screens/631B0DF5.webp')
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            (game / 'mod_korean_hd').mkdir()
            (game / 'mod_korean_hd/news.tim').write_bytes(b'fixture')
            with patch('build_hd.tim', return_value=(sd, 0)):
                images = build_texture(texture, game, font)
            out = images['631B0DF5']
            original = captured.resize((1024, 1024), Image.Resampling.NEAREST)
            self.assertEqual(out.crop((0, 704, 1024, 1024)).tobytes(),
                             original.crop((0, 704, 1024, 1024)).tobytes())
            self.assertNotEqual(out.crop((0, 0, 1024, 704)).tobytes(),
                                original.crop((0, 0, 1024, 704)).tobytes())
            with patch('build_hd.tim', return_value=(Image.new('RGBA', (256, 176)), 0)):
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    build_texture(texture, game, font)
