import struct
import sys
import unittest
import zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from formats import take, extract_installer, rofs_decode, rofs_index, depack, korean_files, korean_rooms


class FormatsTest(unittest.TestCase):
    def test_bounds(self):
        for offset, size in ((-1, 1), (0, -1), (2, 3)):
            with self.assertRaises(ValueError):
                take(b'abc', offset, size)

    def test_installer_crc_and_duplicate(self):
        names = ('korean.dll', 'korean_rooms.bin', 'korean_files.bin', 'korean_bio3_pc.bin', 'korean_bio3_pc_mercenaries.bin', 'korean_text.txt')
        archive = bytearray(b'MZRE3KOPAT\x02\0\0\0')
        for name in names:
            payload = name.encode()
            path = ('japanese\\' + name).encode()
            archive += struct.pack('<H',len(path)) + path + struct.pack('<BIIIII',1,0,0,len(payload),zlib.crc32(payload),len(payload)) + payload
        archive += b'RE3KOEND'
        self.assertEqual(set(extract_installer(archive)),set(names))
        archive[-9] ^= 1
        with self.assertRaises(ValueError):
            extract_installer(archive)

    def test_compressed_literals_and_dictionary(self):
        def bits_to_bytes(bits):
            bits += '0' * (-len(bits) % 8)
            return bytes(int(bits[i:i+8],2) for i in range(0,len(bits),8))
        literal = bits_to_bytes(''.join('0'+format(x,'08b') for x in b'Hello'))
        self.assertEqual(depack(literal,5),b'Hello')
        # Initial dictionary has sixteen copies of every byte, so 0x410 holds A.
        backref = bits_to_bytes('1'+format(0x410,'012b')+format(3,'04b'))
        self.assertEqual(depack(backref,5),b'AAAAA')

    def test_uncompressed_rofs(self):
        key = 123
        from formats import decrypt
        original = b'Resident Evil 3 Korean'
        encrypted = decrypt(original,key)
        header = struct.pack('<HHI',24,1,len(original)) + b'NotComp\0' + struct.pack('<II',key,len(encrypted))
        self.assertEqual(rofs_decode(header+encrypted),original)
        with self.assertRaises(ValueError):
            rofs_decode(header+encrypted[:-1])

    def test_unknown_and_truncated(self):
        for reader, magic in ((korean_files,b'KRF2'), (korean_rooms,b'KRM3')):
            with self.assertRaises((ValueError,struct.error)):
                reader(magic+b'\xff'*8)
        with self.assertRaises(ValueError):
            rofs_index(bytes(64))


if __name__ == '__main__':
    unittest.main()


class TranslationCodecTest(unittest.TestCase):
    def test_text_round_trips_to_game_bytes(self):
        from translation import Codec
        codec = Codec(1)
        data = bytes.fromhex('fa02fc0000ed24f6ed3c3c3cf6ebe10000fe00')
        text = codec.decode(data)
        self.assertNotIn('{ED24}', text)  # glyphs are written as characters
        self.assertIn('{0000}', text)     # padding runs as one escape
        self.assertEqual(codec.encode(text), data)
