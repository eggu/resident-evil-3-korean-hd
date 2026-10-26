"""Read-only parser for the verified KRP1 installer stream."""
import struct


HEADER = struct.Struct('<4sIIIII')
RELOCATION = struct.Struct('<BIII')


def parse_krp1(data):
    if len(data) < HEADER.size:
        raise ValueError('Truncated KRP1 header')
    magic, version, allocation_size, reserved, image_base, count_field = HEADER.unpack_from(data)
    if magic != b'KRP1' or version != 1 or reserved != 0:
        raise ValueError('Unsupported KRP1 header')
    if not allocation_size or allocation_size > 16 * 1024 * 1024 or image_base != 0x10000000:
        raise ValueError('Invalid KRP1 allocation metadata')
    records = []
    pos = HEADER.size
    for index in range(count_field):
        if pos >= len(data):
            raise ValueError(f'Truncated KRP1 record {index} at {pos:#x}')
        kind = data[pos]
        if kind == 1:
            if pos + RELOCATION.size > len(data):
                raise ValueError(f'Truncated kind-1 record at {pos:#x}')
            _, target, size, expected = RELOCATION.unpack_from(data, pos)
            if size != 4 or target < 0x400000:
                raise ValueError(f'Invalid kind-1 record at {pos:#x}')
            record = {'kind': kind, 'offset': pos, 'target': target, 'size': size,
                      'expected': struct.pack('<I', expected)}
            pos += RELOCATION.size
        elif kind == 3:
            end = pos + 10 + allocation_size + 4
            if end > len(data) or data[pos + 1:pos + 6] != b'\0' * 5:
                raise ValueError(f'Invalid kind-3 allocation record at {pos:#x}')
            declared = struct.unpack_from('<I', data, pos + 6)[0]
            if declared != allocation_size or data[end - 4:end] != b'\0' * 4:
                raise ValueError(f'Invalid kind-3 allocation bounds at {pos:#x}')
            record = {'kind': kind, 'offset': pos, 'size': declared,
                      'data': data[pos + 10:pos + 10 + declared]}
            pos = end
        elif kind == 2:
            if pos + 9 > len(data):
                raise ValueError(f'Truncated kind-2 record at {pos:#x}')
            target, size = struct.unpack_from('<II', data, pos + 1)
            if target < 0x400000 or size == 0 or size > 0x10000:
                raise ValueError(f'Invalid kind-2 record at {pos:#x}')
            expected_end = pos + 9 + size
            if expected_end > len(data):
                raise ValueError(f'Truncated kind-2 expected bytes at {pos:#x}')
            paired_end = expected_end + size
            paired = paired_end + 4 <= len(data) and data[paired_end:paired_end + 4] == b'\0' * 4
            if paired:
                end = paired_end + 4
                payload = data[expected_end:end]
                payload_kind = 'paired-data'
                source_offset = None
                entries = []
            else:
                if expected_end + 8 > len(data):
                    raise ValueError(f'Truncated kind-2 allocation reference at {pos:#x}')
                source, count = struct.unpack_from('<II', data, expected_end)
                if source < image_base or source + size > image_base + allocation_size:
                    raise ValueError(f'Invalid kind-2 allocation reference at {pos:#x}')
                if not count or count > 0x10000:
                    raise ValueError(f'Invalid kind-2 reference count at {pos:#x}')
                end = expected_end + 8 + count * 6
                if end > len(data):
                    raise ValueError(f'Truncated kind-2 reference entries at {pos:#x}')
                payload = data[expected_end:end]
                payload_kind = 'allocation-reference'
                source_offset = source - image_base
                entries = [data[expected_end + 8 + i * 6:expected_end + 14 + i * 6] for i in range(count)]
            record = {'kind': kind, 'offset': pos, 'target': target, 'size': size,
                      'expected': data[pos + 9:expected_end],
                      'payload': payload, 'payload_kind': payload_kind,
                      'allocation_source_offset': source_offset, 'reference_entries': entries}
            pos = end
        else:
            raise ValueError(f'Unsupported KRP1 record kind {kind} at {pos:#x}')
        records.append(record)
    if pos != len(data):
        raise ValueError(f'KRP1 trailing or unparsed bytes at {pos:#x}')
    guards = [record for record in records if record['kind'] == 1]
    allocation = [record for record in records if record['kind'] == 3]
    writes = [record for record in records if record['kind'] == 2]
    if len(guards) != 100 or len(allocation) != 1 or len(writes) != 109:
        raise ValueError('Unexpected KRP1 record inventory')
    return {
        'version': version,
        'allocation_size': allocation_size,
        'preferred_base': image_base,
        'count_field': count_field,
        'records': records,
        'relocations': guards,
        'writes': writes,
        'allocation': allocation[0],
        'relocation_end': guards[-1]['offset'] + RELOCATION.size,
        'end_offset': pos,
    }


def pe_read_va(image, va, size):
    """Read bytes at a PE32 virtual address, rejecting unmapped/virtual-only data."""
    def take(offset, length):
        if offset < 0 or length < 0 or offset + length > len(image):
            raise ValueError('PE read outside file')
        return image[offset:offset + length]

    if take(0, 2) != b'MZ':
        raise ValueError('Not a PE image')
    pe = struct.unpack('<I', take(0x3c, 4))[0]
    if take(pe, 4) != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    count = struct.unpack('<H', take(pe + 6, 2))[0]
    optional_size = struct.unpack('<H', take(pe + 20, 2))[0]
    optional = pe + 24
    if struct.unpack('<H', take(optional, 2))[0] != 0x10b:
        raise ValueError('Expected PE32')
    base = struct.unpack('<I', take(optional + 28, 4))[0]
    rva = va - base
    for i in range(count):
        section = optional + optional_size + i * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack('<IIII', take(section + 8, 16))
        span = max(virtual_size, raw_size)
        if virtual_address <= rva and rva + size <= virtual_address + span:
            delta = rva - virtual_address
            if delta + size > raw_size:
                raise ValueError('PE address has no on-disk bytes')
            return take(raw_offset + delta, size)
    raise ValueError(f'Unmapped PE VA {va:#x}')
