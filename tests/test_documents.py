import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_hd import build, install_documents, restore_install, png_texture_key, DEFAULT_FONT

GAME = Path(os.environ['RE3_HD_GAME']) if os.environ.get('RE3_HD_GAME') else None
LOCAL_SOURCE = ROOT / 'work/build/candidate-data'
SOURCE = Path(os.environ['RE3_HD_SOURCE']) if os.environ.get('RE3_HD_SOURCE') else LOCAL_SOURCE if LOCAL_SOURCE.is_dir() else None
PLAN = ROOT / 'translation/hd-reviewed.json'
MANIFEST = ROOT / 'translation/documents-reviewed.json'
STATUS_ROUTE = ROOT / 'translation/status-route.json'
DOCUMENT_ROUTE = ROOT / 'local/hd-inspect/document-route.json'


class DocumentManifestTest(unittest.TestCase):
    def test_coverage_unicode_and_source_metadata(self):
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        records = manifest['pages']
        self.assertEqual([row['id'] for row in records], [f'doc-{index:03}' for index in range(141)])
        self.assertEqual(sum(row.get('reviewed') is True for row in records), 141)
        self.assertEqual(sum(row.get('integration', {}).get('action') == 'retypeset' for row in records), 98)
        self.assertEqual(sum(row.get('integration', {}).get('action') == 'exclude_pc_superseded' for row in records), 4)
        self.assertEqual(sum(row.get('classification') == 'image_only_cover' for row in records), 31)
        self.assertEqual(sum(row.get('classification') == 'blank' for row in records), 8)
        self.assertTrue(all(row.get('source') == 'DATA_J/ETC2/FILEGJ.PIX' for row in records))
        self.assertEqual([row['offset'] for row in records], sorted({row['offset'] for row in records}))
        for row in records:
            self.assertRegex(row.get('source_sha256', ''), r'^[0-9a-f]{64}$')
            self.assertRegex(row.get('source_image_sha256', ''), r'^[0-9a-f]{64}$')
            self.assertGreaterEqual(row['offset'], 0)
        uncertain = [row['id'] for row in records if row.get('reviewed') is not True]
        self.assertEqual(uncertain, [])
        doc17 = next(row for row in records if row['id'] == 'doc-017')
        self.assertIn('VT-J98이', '\n'.join(line['text'] for line in doc17['lines']))
        self.assertEqual(len(json.loads(PLAN.read_text(encoding='utf-8'))['pages']), 5)


class DocumentCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = []
        if GAME is None or not GAME.is_dir():
            missing.append('set RE3_HD_GAME to the game directory')
        elif any(not (GAME / name).is_file() for name in ('ddraw.dll', 'BIOHAZARD(R) 3 PC.exe')):
            missing.append('RE3_HD_GAME must contain ddraw.dll and BIOHAZARD(R) 3 PC.exe')
        if SOURCE is None or not SOURCE.is_dir():
            missing.append('set RE3_HD_SOURCE to the extracted source-data directory')
        else:
            for name in ('DATA_J/ETC2/FILEGJ.PIX', 'DATA_J/ETC2/STMOJIJ.TIM',
                         'DATA_AJ/ETC2/FILEGJ03.TIM', 'DATA_AJ/ETC2/FILEGJ04.TIM',
                         'DATA_AJ/ETC2/FILEGJ05.TIM', 'DATA_AJ/ETC2/FILEGJ06.TIM'):
                if not (SOURCE / name).is_file():
                    missing.append(f'missing source asset: {name}')
        if not DOCUMENT_ROUTE.is_file() or not STATUS_ROUTE.is_file():
            missing.append('local native proof missing (document-route.json/status-route.json)')
        if missing:
            raise unittest.SkipTest('Full document HD integration requires ' + '; '.join(missing))
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.output = cls.root / 'build'
        cls.report = build(SOURCE, PLAN, cls.output, DEFAULT_FONT, GAME, MANIFEST, STATUS_ROUTE)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_reviewed_pages_accounted_for(self):
        coverage = self.report['documents']
        self.assertEqual((coverage['source_pages'], coverage['reviewed'], coverage['retypeset']), (141, 141, 98))
        self.assertEqual((coverage['pc_superseded'], coverage['image_only_retained'], coverage['blank_retained'], coverage['unreviewed']), (4, 31, 8, 0))
        ids = set(coverage['generated_ids'])
        self.assertEqual(len(ids), 98)
        self.assertIn('doc-017', ids)
        self.assertNotIn('doc-000', ids)
        self.assertEqual(len([row for row in self.report['pages'] if row.get('document') and not row['document'].get('pc_controls')]), 98)
        self.assertEqual(len([row for row in self.report['pages'] if (row.get('document') or {}).get('pc_controls')]), 4)

    def test_hd_pages_preserve_transparency_and_aspect(self):
        for page_id in ('doc-001', 'doc-050', 'doc-130'):
            row = next(row for row in self.report['pages'] if row['id'] == page_id)
            sd = Image.open(self.output / row['sd_png']).convert('RGBA')
            hd = Image.open(self.output / row['png']).convert('RGBA')
            self.assertEqual((sd.size, hd.size), ((256, 176), (1024, 704)))
            self.assertEqual(hd.getpixel((1023, 703))[3], 0)
            self.assertIsNotNone(hd.getchannel('A').getbbox())

    def test_status_keys_match_native_clut_proof(self):
        route = json.loads(STATUS_ROUTE.read_text(encoding='utf-8'))
        row = next(row for row in self.report['pages'] if row['id'] == 'status-labels')
        self.assertEqual([item['path'] for item in row['status_variants']], [item['path'] for item in route['palettes']])
        for variant, proof in zip(row['status_variants'], route['palettes']):
            self.assertEqual((variant['palette'], variant['native_rgba_sha256']), (proof['palette'], proof['native_rgba_sha256']))
            with Image.open(self.output / variant['asset']) as image:
                self.assertEqual(image.size, (1024, 288))

    def test_manifest_guard_and_full_install_restore(self):
        bad_manifest = self.root / 'bad.json'
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        manifest['pages'].pop()
        bad_manifest.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unique source pages'):
            build(SOURCE, PLAN, self.root / 'bad-build', DEFAULT_FONT, GAME, bad_manifest, STATUS_ROUTE)

        game = self.root / 'game'
        game.mkdir()
        for name in ('ddraw.dll', 'BIOHAZARD(R) 3 PC.exe'):
            (game / name).symlink_to(GAME / name)
        backup = self.root / 'backup'
        record = install_documents(self.output, game, backup)
        paths = {row['path'] for row in record['files']}
        self.assertEqual(len([path for path in paths if path.startswith('file/')]), 102)
        self.assertEqual(len([path for path in paths if path.startswith('hires/misc/')]), 9)
        memo_keys = {png_texture_key(Image.open(self.output / row['sd_png'])) for row in self.report['pages'] if row.get('document')}
        self.assertEqual(len([path for path in paths if path.startswith('hires/memo/')]), len(memo_keys))

        target = game / record['files'][-1]['path']
        installed = target.read_bytes()
        target.write_bytes(b'changed after install')
        with self.assertRaisesRegex(ValueError, 'changed since recorded'):
            restore_install(backup / 'install.json')
        target.write_bytes(installed)
        restored = restore_install(backup / 'install.json')
        self.assertEqual(restored['status'], 'restored; hashes verified')
        for row in record['files']:
            self.assertFalse((game / row['path']).exists())


if __name__ == '__main__':
    unittest.main()
