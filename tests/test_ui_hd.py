import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_ui_hd import LAYOUT, PLAN, DEFAULT_FONT, build_ui, install_ui, render_atlas, restore_ui

SOURCE_DEFAULT = ROOT / 'work/build/candidate-data'
SOURCE = Path(os.environ['RE3_HD_SOURCE']) if os.environ.get('RE3_HD_SOURCE') else SOURCE_DEFAULT if SOURCE_DEFAULT.is_dir() else None
GAME = Path(os.environ['RE3_HD_GAME']) if os.environ.get('RE3_HD_GAME') else None
ROUTE = ROOT / 'translation/status-route.json'
EXE = Path(os.environ['RE3_HD_EXE']) if os.environ.get('RE3_HD_EXE') else None
EXE_SHA256 = 'b5215af19ea062770bc1c941ea1dd17670cd86362c43a31289ff5bb0bf7e2357'


def fixture_tim(layout):
    width, height, palette_rows = 256, 72, 9
    palette = [0] * (16 * palette_rows)
    for row in range(palette_rows):
        palette[row * 16 + 1] = 0x001f
    pixels = bytearray(width * height // 2)
    at = 2 * (width // 2) + 1
    pixels[at] = 0x01
    records = json.loads(layout.read_text(encoding='utf-8'))['texts']
    records += [{'cell': cell} for cell in json.loads(layout.read_text(encoding='utf-8'))['bottom_cells']]
    for record in records:
        x0, y0, x1, y1 = record['cell']
        x, y = (x0 + x1) // 2, (y0 + y1) // 2
        at = y * (width // 2) + x // 2
        pixels[at] = (pixels[at] & 0x0f) | (0x10 if x % 2 else 0x01)
    clut = struct.pack('<I4H', 12 + len(palette) * 2, 0, 0, 16, palette_rows) + struct.pack(f'<{len(palette)}H', *palette)
    image = struct.pack('<I4H', 12 + len(pixels), 0, 0, width // 4, height) + pixels
    return struct.pack('<II', 16, 8) + clut + image


class UIAtlasRasterTest(unittest.TestCase):
    def test_nine_label_cells_match_native_exe_records(self):
        if EXE is None or not EXE.is_file():
            self.skipTest('set RE3_HD_EXE to the verified SourceNext executable fixture')
        from build_hd import digest
        self.assertEqual(digest(EXE), EXE_SHA256)
        data = EXE.read_bytes()
        records = []
        for address, count in ((0x533F00, 3), (0x533F48, 6)):
            offset = address - 0x400000
            records.extend(struct.unpack_from('<6H', data, offset + index * 12)
                           for index in range(count))
        native_cells = [(u, v, u + width, v + height)
                        for u, v, width, height, _, _ in records]
        layout = json.loads(LAYOUT.read_text(encoding='utf-8'))
        label_rows = [row for row in layout['texts'] if row['text'] in
                      ('FILE', 'EXIT', 'MAP', 'Fine', 'Caution', 'Danger', 'Poison', 'VIRUS')
                      and row['cell'][1] in (32, 40)]
        self.assertEqual([row['cell'] for row in label_rows],
                         [list(cell) for cell in native_cells[3:] + [native_cells[0], native_cells[2], native_cells[1]]])

    def test_all_source_words_and_counts_fit_proven_cells(self):
        layout = json.loads(LAYOUT.read_text(encoding='utf-8'))
        plan = json.loads(PLAN.read_text(encoding='utf-8'))
        status = next(row for row in plan['pages'] if row.get('status'))
        background = Image.new('RGBA', (1024, 288), (0, 0, 0, 0))
        image, rendered = render_atlas(background, fixture_tim(LAYOUT), 0, layout, status['lines'], DEFAULT_FONT)
        self.assertEqual(image.size, (1024, 288))
        texts = [row['text'] for row in rendered]
        for text in ('EXIT', 'Fine', 'Caution', 'Danger', 'Poison', 'VIRUS', 'FILE', 'MAP', 'AUTO', 'MANUAL', '%', '∞', *'0123456789', *[row['text'] for row in status['lines']]):
            self.assertIn(text, texts)
        for row in rendered:
            x0, y0, x1, y1 = row['cell']
            left, top, right, bottom = row['bounds_hd']
            self.assertGreaterEqual(left, x0 * 4)
            self.assertGreaterEqual(top, y0 * 4)
            self.assertLessEqual(right, x1 * 4)
            self.assertLessEqual(bottom, y1 * 4)
            sx0, sy0, sx1, sy1 = row['source_ink_bounds']
            self.assertGreaterEqual(sx0, x0)
            self.assertGreaterEqual(sy0, y0)
            self.assertLessEqual(sx1, x1)
            self.assertLessEqual(sy1, y1)
            self.assertEqual(row['color'], [255, 0, 0])
        self.assertGreater(image.getpixel((8, 8))[3], 0)  # Original directional-arrow art remains.
        self.assertEqual(image.getpixel((1023, 287))[3], 0)
        with self.assertRaisesRegex(ValueError, 'source and 1024x288 background'):
            render_atlas(Image.new('RGBA', (256, 72)), fixture_tim(LAYOUT), 0, layout, status['lines'], DEFAULT_FONT)


class UIAtlasIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = []
        if GAME is None or not GAME.is_dir():
            missing.append('set RE3_HD_GAME to the game directory')
        if SOURCE is None or not SOURCE.is_dir():
            missing.append('set RE3_HD_SOURCE to the extracted source-data directory')
        if not ROUTE.is_file():
            missing.append('local native status-route.json is missing')
        if missing:
            raise unittest.SkipTest('Native UI integration requires ' + '; '.join(missing))
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.output = cls.root / 'build'
        cls.report = build_ui(SOURCE, GAME, cls.output, route_path=ROUTE)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_observed_key_dimensions_and_isolated_restore(self):
        route = json.loads(ROUTE.read_text(encoding='utf-8'))
        self.assertEqual(len(self.report['variants']), 9)
        self.assertEqual(self.report['review_sample']['size'], [2048, 640])
        self.assertTrue((self.output / self.report['review_sample']['path']).is_file())
        self.assertEqual([row['key'] for row in self.report['variants']], [row['key'] for row in route['palettes']])
        for row in self.report['variants']:
            self.assertEqual(row['path'], f"hires/misc/{row['key']}.webp")
            with Image.open(self.output / row['asset']) as image:
                self.assertEqual(image.size, (1024, 288))
                self.assertEqual(image.format, 'WEBP')
        palette1 = self.report['variants'][1]['rendered']
        fine = next(row for row in palette1 if row['text'] == 'Fine')
        file_label = next(row for row in palette1 if row['text'] == 'FILE')
        self.assertGreater(fine['color'][1], fine['color'][0])
        self.assertGreater(file_label['color'][0], file_label['color'][1])

        game = self.root / 'game'
        game.mkdir()
        for name in ('ddraw.dll', 'BIOHAZARD(R) 3 PC.exe'):
            (game / name).symlink_to(GAME / name)
        (game / 'hires/misc').mkdir(parents=True)
        originals = {}
        for row in self.report['variants']:
            path = game / row['path']
            originals[path] = f"old-{row['palette']}".encode()
            path.write_bytes(originals[path])
        record = install_ui(self.output, game, self.root / 'backup')
        self.assertEqual(len(record['files']), 9)
        target = game / record['files'][0]['path']
        installed = target.read_bytes()
        target.write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError, 'changed since recorded'):
            restore_ui(self.root / 'backup/install.json')
        target.write_bytes(installed)
        restored = restore_ui(self.root / 'backup/install.json')
        self.assertEqual(restored['status'], 'restored; hashes verified')
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)


if __name__ == '__main__':
    unittest.main()
