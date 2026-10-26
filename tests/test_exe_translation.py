import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from exe_translation import parse_krp1, pe_read_va


ROOT = Path(__file__).resolve().parents[1]


class ExeTranslationTest(unittest.TestCase):
    def test_installer_payloads_parse_all_210_records_to_eof(self):
        for name in ('korean_bio3_pc.bin', 'korean_bio3_pc_mercenaries.bin'):
            parsed = parse_krp1((ROOT / 'work/extracted' / name).read_bytes())
            self.assertEqual(parsed['allocation_size'], 0x4458)
            self.assertEqual(parsed['preferred_base'], 0x10000000)
            self.assertEqual(len(parsed['relocations']), 100)
            self.assertEqual(len(parsed['writes']), 109)
            self.assertEqual(len(parsed['records']), 210)
            self.assertEqual(parsed['allocation']['offset'], 0x52c)
            self.assertEqual(len(parsed['allocation']['data']), 0x4458)
            self.assertEqual(parsed['end_offset'], 0x574d)
            self.assertEqual(parsed['records'][-1]['offset'] + 15, len((ROOT / 'work/extracted' / name).read_bytes()))
            self.assertIn(parsed['writes'][0]['target'], (0x42d5d0, 0x42d620))
            self.assertEqual(parsed['writes'][0]['expected'], bytes.fromhex('447e5100'))
            self.assertEqual(parsed['writes'][0]['payload_kind'], 'allocation-reference')
            self.assertEqual(parsed['writes'][0]['allocation_source_offset'], 0)
            self.assertEqual(len(parsed['writes'][0]['reference_entries']), 1)
            self.assertEqual(len(parsed['writes'][0]['reference_entries'][0]), 6)
            self.assertEqual(parsed['writes'][-1]['payload_kind'], 'paired-data')
            self.assertEqual(parsed['writes'][-1]['payload'][-4:], b'\0' * 4)

    def test_header_and_relocation_bounds_reject_corruption(self):
        data = bytearray((ROOT / 'work/extracted/korean_bio3_pc.bin').read_bytes())
        for offset, value in ((0, 0), (4, 2), (24 + 5, 0xff), (0x52c + 6, 0)):
            damaged = bytearray(data)
            damaged[offset] = value
            with self.assertRaises(ValueError):
                parse_krp1(damaged)
        with self.assertRaises(ValueError):
            parse_krp1(data[:40])
        with self.assertRaises(ValueError):
            parse_krp1(data[:-1])
        damaged = bytearray(data)
        damaged[0x4992] = 0xff
        with self.assertRaises(ValueError):
            parse_krp1(damaged)
        damaged = bytearray(data)
        struct.pack_into('<I', damaged, 0x499f, 0x10004457)
        with self.assertRaises(ValueError):
            parse_krp1(damaged)

    def test_pe_va_mapping_and_raw_bounds(self):
        image = bytearray(0x300)
        image[:2] = b'MZ'
        struct.pack_into('<I', image, 0x3c, 0x80)
        image[0x80:0x84] = b'PE\0\0'
        struct.pack_into('<HH', image, 0x84, 0x14c, 1)
        struct.pack_into('<H', image, 0x94, 0xe0)
        struct.pack_into('<H', image, 0x98, 0x10b)
        struct.pack_into('<I', image, 0xb4, 0x400000)
        section = 0x178
        struct.pack_into('<IIII', image, section + 8, 0x100, 0x1000, 0x100, 0x200)
        image[0x210:0x214] = b'\x44\x7e\x51\x00'
        self.assertEqual(pe_read_va(image, 0x401010, 4), b'\x44\x7e\x51\x00')
        with self.assertRaises(ValueError):
            pe_read_va(image, 0x4010ff, 4)


if __name__ == '__main__':
    unittest.main()
