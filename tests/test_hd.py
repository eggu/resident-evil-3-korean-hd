import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_hd import color555, tim, document_images, texture_key, load_font, render_lines, build, png_texture_key, install_documents, DEFAULT_FONT


def fixture_tim():
    palette = struct.pack('<16H', 0, 0x1f, 0x3e0, 0x7c00, *([0] * 12))
    return struct.pack('<II I4H',16,8,44,0,0,16,1) + palette + struct.pack('<I4H',14,0,0,1,1) + b'\x21\x03'


class HDTest(unittest.TestCase):
    def test_png_zero_rgb_sentinel_keeps_alpha(self):
        image=Image.new('RGBA',(3,1))
        image.putpixel((1,0),(0,0,0,255))
        image.putpixel((2,0),(10,20,30,255))
        expected=bytes((1,0,0,0,1,0,0,255,30,20,10,255))
        self.assertEqual(png_texture_key(image),f'{zlib.crc32(expected):08X}')

    def test_native_color_edge_cases(self):
        self.assertEqual(color555(0), (0,0,0,0))
        self.assertEqual(color555(0x8000), (1,0,0,255))
        self.assertEqual(color555(0x1f), (255,0,0,255))
        self.assertEqual(color555(0x4210), (132,132,132,255))

    def test_tim_index_order_and_bounds(self):
        image, end = tim(fixture_tim())
        self.assertEqual(image.size, (4,1))
        self.assertEqual([image.getpixel((x,0)) for x in range(4)], [(255,0,0,255),(0,255,0,255),(0,0,255,255),(0,0,0,0)])
        self.assertEqual(end, len(fixture_tim()))
        for raw in (b'', fixture_tim()[:-1], fixture_tim().replace(b'\x10\0\0\0',b'\x11\0\0\0',1)):
            with self.assertRaises((ValueError, struct.error)):
                tim(raw)
        with self.assertRaises(ValueError):
            tim(fixture_tim(), palette=1)

    def test_document_sector_alignment(self):
        raw = fixture_tim().ljust(2048,b'\0')
        self.assertEqual([o for o,_ in document_images(raw+raw)], [0,2048])
        with self.assertRaises(ValueError):
            document_images(raw[:-1])

    def test_hash_crop_excludes_pitch(self):
        image = Image.new('RGBA',(4,3))
        image.putpixel((2,1),(17,34,51,255))
        row = bytes((51,34,17,255,0,0,0,0))
        self.assertEqual(texture_key(image,(2,1,2,1)),f'{zlib.crc32(row):08X}')
        with self.assertRaises(ValueError):
            texture_key(image,(3,1,2,1))

    def test_font_override_and_bad_path_no_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);output=root/'output';plan=root/'plan.json'
            plan.write_text('{"pages": []}')
            with self.assertRaises(ValueError):
                build(root/'source',plan,output,root/'missing.ttf')
            self.assertFalse(output.exists())
            invalid=root/'invalid.ttf';invalid.write_bytes(b'bad font')
            with self.assertRaises(ValueError):
                load_font(invalid)
        self.assertEqual(load_font(DEFAULT_FONT).size,44)

    def test_missing_glyph_rejected(self):
        from fontTools.ttLib import TTFont
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'latin-only.ttf'
            with TTFont(str(DEFAULT_FONT)) as face:
                for table in face['cmap'].tables:
                    table.cmap.pop(ord('한'),None)
                face.save(path)
            with self.assertRaisesRegex(ValueError,'missing glyphs'):
                render_lines([{'text':'한글','position':[0,0]}],path)

    @unittest.skipUnless(Path('/System/Library/Fonts/Supplemental/AppleMyungjo.ttf').is_file(), 'alternate macOS font unavailable')
    def test_alternate_font_changes_pixels(self):
        alternate=Path('/System/Library/Fonts/Supplemental/AppleMyungjo.ttf')
        lines=[{'text':'한글 문서','position':[0,0]}]
        default,_=render_lines(lines,DEFAULT_FONT)
        custom,_=render_lines(lines,alternate)
        self.assertNotEqual(default.tobytes(),custom.tobytes())

    def test_actual_hd_raster_and_bounds(self):
        image, rows=render_lines([{'text':'긴급 회피','position':[0,0]}],DEFAULT_FONT)
        self.assertEqual(image.size,(1024,768))
        self.assertEqual(rows[0]['font_px'],44)
        self.assertEqual(image.getpixel((1023,767)),(0,0,0,0))
        backdrop=Image.new('RGBA',image.size,(30,90,150,255))
        composed=Image.alpha_composite(backdrop,image)
        self.assertEqual(composed.getpixel((1023,767)),(30,90,150,255))
        edge=next((image.getpixel((x,y)) for y in range(50) for x in range(200) if 0 < image.getpixel((x,y))[3] < 255),None)
        self.assertIsNotNone(edge)
        self.assertEqual(edge[:3],(255,255,255))
        self.assertGreater(len(set(image.tobytes())),2)  # Direct antialiased outlines.
        with self.assertRaises(ValueError):
            render_lines([{'text':'한글','position':[250,191]}],DEFAULT_FONT)


if __name__ == '__main__':
    unittest.main()
