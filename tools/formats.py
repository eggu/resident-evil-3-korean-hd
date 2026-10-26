"""Read-only RE3 ROFS and Korean installer readers. ROFS algorithm: RE3-Mod-SDK/unpacker/Rofs.cpp."""
import re
import struct
import zlib
from pathlib import PureWindowsPath


def take(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError(f'Out of bounds: {offset:#x}+{size:#x}/{len(data):#x}')
    return data[offset:offset + size]


def extract_installer(data):
    if data[:2] != b'MZ' or b'RE3KOPAT\x02\0\0\0' not in data or data[-8:] != b'RE3KOEND':
        raise ValueError('Unsupported Korean installer')
    result = {}
    for match in re.finditer(rb'japanese\\korean[a-z_3]*\.(?:dll|bin|txt)', data):
        name = PureWindowsPath(match.group().decode()).name
        kind, old_size, old_crc, size, crc, stored = struct.unpack('<BIIIII', take(data, match.end(), 21))
        if (kind, old_size, old_crc) != (1, 0, 0) or size != stored:
            raise ValueError(f'Unsupported record: {name}')
        payload = take(data, match.end() + 21, stored)
        if zlib.crc32(payload) != crc or name in result:
            raise ValueError(f'Bad CRC or duplicate: {name}')
        result[name] = payload
    if len(result) != 6:
        raise ValueError('Expected six Korean payloads')
    return result


def rofs_index(data):
    if take(data, 0, 20) != struct.pack('<5I', 3, 1, 4, 0x10100, 0x400):
        raise ValueError('Unsupported ROFS header')
    def string(pos):
        end = data.index(b'\0', pos)
        return data[pos:end].decode('ascii'), end + 1
    root, pos = string(21)
    offset, _ = struct.unpack('<II', take(data, pos, 8))
    directory, _ = string(pos + 8)
    pos = offset * 8
    count, = struct.unpack('<I', take(data, pos, 4))
    pos += 4
    entries = []
    for _ in range(count):
        offset, size = struct.unpack('<II', take(data, pos, 8))
        name, pos = string(pos + 8)
        path = PureWindowsPath(root, directory, name)
        if path.is_absolute() or '..' in path.parts or ':' in str(path):
            raise ValueError('Unsafe ROFS path')
        take(data, offset * 8, size)
        entries.append((path.as_posix(), offset * 8, size))
    return entries


BASE = (0xe6,0x1a4,0xe6,0x1c5,0x130,0xe8,0x3db,0x8b,0x141,0x18e,0x3ae,0x139,0xf0,0x27a,0x2c9,0x1b0,0x1f7,0x81,0x138,0x285,0x25a,0x15b,0x30f,0x335,0x2e4,0x1f6,0x143,0xd1,0x337,0x385,0x7b,0xc6,0x335,0x141,0x186,0x2a1,0x24d,0x342,0x1fb,0x3e5,0x1b0,0x6d,0x140,0xc0,0x386,0x16b,0x20b,0x9a,0x241,0xde,0x15e,0x35a,0x25b,0x154,0x68,0x2e8,0x321,0x71,0x1b0,0x232,0x2d9,0x263,0x164,0x290)


def decrypt(data, key):
    def next_key():
        nonlocal key
        key = (key * 0x5d588b65 + 0x8000000b) & 0xffffffff
        return key >> 24
    xor = next_key()
    base = next_key() % 63
    block = 0
    out = bytearray()
    for value in data:
        if block > BASE[base]:
            base = next_key() % 63
            xor = next_key()
            block = 0
        out.append(value ^ xor)
        block += 1
    return bytes(out)


def depack(data, limit):
    window = bytearray(v for v in range(256) for _ in range(16)) + bytearray(256)
    bit = pos = cursor = 0
    out = bytearray()
    def read8():
        nonlocal pos
        value = (data[pos] << bit) & 255
        if bit:
            value |= (data[pos + 1] if pos + 1 < len(data) else 0) >> (8 - bit)
        pos += 1
        return value
    while pos < len(data) and len(out) < limit:
        bit += 1
        value = data[pos] << bit
        value |= (data[pos + 1] if pos + 1 < len(data) else 0) >> (8 - bit)
        pos += 1
        if bit == 8:
            pos += 1
            bit = 0
        if value & 256:
            value2 = read8()
            length = (value2 & 15) + 2
            start = ((value & 255) << 4) | (value2 >> 4)
            chunk = window[start:start + length]
        else:
            chunk = bytes([value & 255])
        out.extend(chunk)
        window[cursor:cursor + len(chunk)] = chunk
        cursor += len(chunk)
        if cursor >= 4096:
            cursor = 0
        if len(out) > limit + 4096:
            raise ValueError('ROFS output exceeds declared size')
    return bytes(out[:limit])


def rofs_decode(data):
    offset, count, size = struct.unpack('<HHI', take(data, 0, 8))
    ident = bytes(v ^ data[15] for v in take(data, 8, 8))
    if ident not in (b'NotComp\0', b'Hi_Comp\0'):
        raise ValueError(f'Unknown compression: {ident!r}')
    keys = struct.unpack(f'<{count}I', take(data, 16, count * 4))
    lengths = struct.unpack(f'<{count}I', take(data, 16 + count * 4, count * 4))
    result = bytearray()
    for key, length in zip(keys, lengths):
        block = decrypt(take(data, offset, length), key)
        result.extend(depack(block, min(32768, size - len(result))) if ident == b'Hi_Comp\0' else block)
        offset += length
    if len(result) != size:
        raise ValueError(f'ROFS size mismatch {len(result)} != {size}')
    return bytes(result)


def korean_files(data):
    if take(data, 0, 4) != b'KRF2':
        raise ValueError('Expected KRF2')
    count, font_count = struct.unpack('<II', take(data, 4, 8))
    entries = []
    for i in range(count):
        raw, start, length = struct.unpack('<32sII', take(data, 12 + i * 40, 40))
        entries.append((raw.split(b'\0')[0].decode('ascii'), start, length))
    run_count = max(start + length for _, start, length in entries)
    pos = 12 + 40 * count
    runs = [struct.unpack('<III', take(data, pos + i * 12, 12)) for i in range(run_count)]
    pos += run_count * 12
    fonts = [struct.unpack('<HHHHI', take(data, pos + i * 12, 12)) for i in range(font_count)]
    for offset, size, source in runs:
        take(data, source, size)
    for x, y, width, reserved, source in fonts:
        if not (0x300 <= x < x + width <= 0x380 and 0x100 <= y < 0x200):
            raise ValueError('Invalid font VRAM run')
        take(data, source, width * 2)
    return {name: runs[start:start+length] for name, start, length in entries}, fonts


def korean_rooms(data):
    if take(data, 0, 4) != b'KRM3':
        raise ValueError('Expected KRM3')
    count, = struct.unpack('<I', take(data, 4, 4))
    entries = [struct.unpack('<8I', take(data, 8 + i * 32, 32)) for i in range(count)]
    for stage, checksum, size, offset_hash, offset, length, dynamic, dynamic_count in entries:
        take(data, offset, length)
        take(data, dynamic, dynamic_count * 4)
    return entries
