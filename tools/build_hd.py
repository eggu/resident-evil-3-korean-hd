"""Re-typeset reviewed RE3 Korean raster text at 4x; never upscale SD lettering."""
import argparse
import hashlib
import json
import shutil
import struct
import zlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageChops
from fontTools.ttLib import TTFont
from formats import take

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT = ROOT / 'assets/fonts/NotoSerifKR[wght].ttf'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_font(path, size=44):
    if not Path(path).is_file():
        raise ValueError(f'Font does not exist: {path}')
    try:
        return ImageFont.truetype(str(path), size)
    except OSError as exc:
        raise ValueError(f'Cannot load font: {path}') from exc


def color555(value):
    # REbirth 1.0.3 ddraw RVA 0x8bec0: 0x8000 is opaque near-black, zero transparent.
    if value == 0x8000:
        return (1, 0, 0, 255)
    rgb = tuple(((value >> s & 31) << 3) | (value >> s & 31) >> 2 for s in (0, 5, 10))
    return (*rgb, 255 if value else 0)


def tim(data, offset=0, palette=0):
    magic, flags = struct.unpack('<II', take(data, offset, 8))
    if magic != 16 or flags & ~15 or flags & 7 not in (0, 1, 2):
        raise ValueError('Unsupported TIM')
    pos, colors = offset + 8, None
    if flags & 8:
        size, _, _, pw, ph = struct.unpack('<I4H', take(data, pos, 12))
        if size != 12 + pw * ph * 2 or not 0 <= palette < ph:
            raise ValueError('Invalid TIM palette')
        colors = struct.unpack(f'<{pw}H', take(data, pos + 12 + palette * pw * 2, pw * 2))
        pos += size
    size, _, _, words, height = struct.unpack('<I4H', take(data, pos, 12))
    if not words or not height or size != 12 + words * height * 2:
        raise ValueError('Invalid TIM image block')
    raw, mode = take(data, pos + 12, size - 12), flags & 7
    if mode == 0:
        indices, width = [v for byte in raw for v in (byte & 15, byte >> 4)], words * 4
    elif mode == 1:
        indices, width = raw, words * 2
    else:
        indices, width = struct.unpack(f'<{words * height}H', raw), words
    if mode < 2 and (colors is None or max(indices) >= len(colors)):
        raise ValueError('Missing or short TIM palette')
    image = Image.new('RGBA', (width, height))
    image.putdata([color555(colors[v] if colors is not None else v) for v in indices])
    return image, pos + size


def document_images(data):
    result, offset = [], 0
    while offset < len(data):
        image, end = tim(data, offset)
        result.append((offset, image))
        offset = (end + 2047) // 2048 * 2048
    if offset != len(data):
        raise ValueError('Invalid FILEGJ sector alignment')
    return result


def texture_key(image, box=None, order='BGRA'):
    """bio3hd RVA 0x2280: CRC of cropped rows, excluding source pitch padding."""
    if order not in ('RGBA', 'BGRA'):
        raise ValueError('Unsupported pixel order')
    if box is not None:
        x, y, width, height = box
        if min(x, y) < 0 or min(width, height) <= 0 or x + width > image.width or y + height > image.height:
            raise ValueError('Texture crop outside image')
        image = image.crop((x, y, x + width, y + height))
    return f'{zlib.crc32(image.convert("RGBA").tobytes("raw", order)):08X}'


PLATE_ALPHA, FILL_MAX_SCALE, MARGIN = 100, 1.5, 12
# in game, plate grey 0 -> screen 6 and 26 -> 17; 9 matches the 10 around documents
PLATE_GREY = 9


def fill_scale(lines, font_path, logical_size, draw):
    """Shared scale for line positions and sizes so the text block fills the page."""
    right = max(row['position'][0] * 4 + draw.textlength(row['text'], font=load_font(font_path, row.get('size', 11) * 4))
                for row in lines)
    bottom = max(row['position'][1] * 4 + row.get('size', 11) * 4 * 1.25 for row in lines)
    return max(1.0, min((logical_size[0] * 4 - MARGIN) / right, (logical_size[1] * 4 - MARGIN) / bottom, FILL_MAX_SCALE))


def render_lines(lines, font_path, logical_size=(256, 192), background=None, erase=(), plate=None, centered=False, scale=None):
    """plate: None, 'line' / 'page' (translucent plate per line / over the page) or 'outline'
    (no plate, outlined text). Any style enlarges text to a shared fill size."""
    with TTFont(str(font_path), fontNumber=0) as face:
        cmap = face.getBestCmap() or {}
    missing = {c for row in lines for c in row['text'] if not c.isspace() and ord(c) not in cmap}
    if missing:
        raise ValueError(f'Font missing glyphs: {sorted(missing)}')
    canvas = Image.new('RGBA', tuple(v * 4 for v in logical_size), (0, 0, 0, 0))
    if background is not None:
        if background.size != canvas.size:
            raise ValueError('HD background dimensions differ from layout')
        canvas = background.convert('RGBA').copy()
    draw, used = ImageDraw.Draw(canvas), []
    plate_mask, strokes = Image.new('L', canvas.size, 0), []
    plates = ImageDraw.Draw(plate_mask)
    if scale is None:
        scale = fill_scale(lines, font_path, logical_size, draw) if plate and lines else 1.0
    if plate == 'page' and lines:
        plates.rectangle((0, 0, canvas.width - 1, canvas.height - 1), fill=PLATE_ALPHA)  # whole document quad
    for box in erase:
        draw.rectangle(tuple(v * 4 for v in box), fill=(0, 0, 0, 0))
    for row in lines:
        text, (x, y) = row['text'], row['position']
        x, y = x * scale, y * scale
        if not text or x < 0 or y < 0 or x >= logical_size[0] or y >= logical_size[1]:
            raise ValueError('Invalid text or position')
        size, available = round(row.get('size', 11) * 4 * scale), (logical_size[0] - x) * 4
        font = load_font(font_path, size)
        while draw.textlength(text, font=font) > available and size > 24:
            size -= 1
            font = load_font(font_path, size)
        if centered:  # title pages: keep the enlarged title centred on the page
            x = (canvas.width - draw.textlength(text, font=font)) / 8
            y = row['position'][1]  # keep the SD row
        bbox = draw.textbbox((x * 4, y * 4), text, font=font, anchor='lt')
        if bbox[2] > canvas.width or bbox[3] > canvas.height:
            raise ValueError(f'Text exceeds page: {text}')
        if plate:  # dark translucent plate + outline keeps text legible over artwork
            if plate == 'line':
                plates.rounded_rectangle((bbox[0] - 10, bbox[1] - 6, bbox[2] + 10, bbox[3] + 6), radius=10, fill=PLATE_ALPHA)
            strokes.append(((x * 4, y * 4), text, font))
        else:
            draw.text((x * 4, y * 4), text, font=font, fill='white', anchor='lt')
        used.append({'text': text, 'font_px': size, 'bounds': list(bbox)})
    if plate:
        shade = Image.new('RGBA', canvas.size, (PLATE_GREY,) * 3 + (0,))
        shade.putalpha(plate_mask)
        canvas.alpha_composite(shade)
        draw = ImageDraw.Draw(canvas)
        for xy, text, font in strokes:
            draw.text(xy, text, font=font, fill='white', anchor='lt',
                      stroke_width=5, stroke_fill=(0, 0, 0, 255))
    return canvas, used


def build(source, plan_path, output, font=DEFAULT_FONT, game=None,
          documents_path=None, status_route_path=None, plate=False):
    load_font(font)  # Fail before output creation; an explicit path never falls back.
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if output.exists() or output.resolve().is_relative_to(source.resolve()) or (game and output.resolve().is_relative_to(game.resolve())):
        raise ValueError('Choose a new output outside the source directory')
    pages = list(plan['pages'])
    coverage = None
    if documents_path:
        manifest = json.loads(documents_path.read_text(encoding='utf-8'))
        records = manifest['pages']
        ids = [row['id'] for row in records]
        if len(records) != 141 or len(set(ids)) != 141 or set(ids) != {f'doc-{i:03}' for i in range(141)}:
            raise ValueError('Document manifest must cover unique source pages doc-000..doc-140')
        source_file = source / 'DATA_J/ETC2/FILEGJ.PIX'
        if digest(source_file) != records[0]['source_sha256']:
            raise ValueError('Document source hash mismatch')
        images = document_images(source_file.read_bytes())
        if len(images) != 141:
            raise ValueError('Source PIX must contain exactly 141 document rasters')
        additions, counts = [], {'reviewed': 0, 'retypeset': 0, 'pc_superseded': 0,
                                 'retained': 0, 'unreviewed': 0}
        for row in records:
            index = int(row['id'][-3:])
            if row.get('source') != 'DATA_J/ETC2/FILEGJ.PIX' or row.get('source_sha256') != digest(source_file):
                raise ValueError(f'Changed document source provenance: {row["id"]}')
            if images[index][0] != row['offset']:  # rasters themselves are pinned by the PIX hash above
                raise ValueError(f'Document raster offset changed: {row["id"]}')
            if row.get('reviewed') is not True:
                counts['unreviewed'] += 1
                continue
            counts['reviewed'] += 1
            action = row.get('integration', {}).get('action')
            if action == 'exclude_pc_superseded':
                counts['pc_superseded'] += 1
                continue
            if action != 'retypeset':
                counts['retained'] += 1
                continue
            counts['retypeset'] += 1
            additions.append({**{key: row[key] for key in ('id', 'source', 'source_sha256', 'offset',
                                                             'lines', 'logical_size', 'document', 'classification')},
                               'reviewed': True})
        coverage = {'source_pages': len(records), **counts,
                    'image_only_retained': sum(row.get('classification') == 'image_only_cover' for row in records),
                    'blank_retained': sum(row.get('classification') == 'blank' for row in records),
                    'generated_ids': [row['id'] for row in additions]}
        pages = additions + [row for row in pages if row.get('status') or (row.get('document') and row['document'].get('pc_controls'))]
    status_route = json.loads(status_route_path.read_text(encoding='utf-8')) if status_route_path else None
    if status_route:
        if digest(source / 'DATA_J/ETC2/STMOJIJ.TIM') != status_route['source_sha256']:
            raise ValueError('Status TIM differs from native route proof')
        if game is None or digest(game / 'ddraw.dll') != status_route['ddraw_sha256'] or digest(game / 'BIOHAZARD(R) 3 PC.exe') != status_route['exe_sha256']:
            raise ValueError('Status route proof does not match the selected game binaries')
    # one scale per document so every body page shares the same text size
    probe, doc_scale = ImageDraw.Draw(Image.new('L', (1, 1))), {}
    for row in pages:
        if plate and row.get('reviewed') is True and row.get('lines') and not row.get('status') and row.get('classification') != 'title':
            key = (row.get('document') or {}).get('file_id', row['id'])
            page_scale = fill_scale(row['lines'], font, tuple(row.get('logical_size', [256, 192])), probe)
            doc_scale[key] = min(doc_scale.get(key, page_scale), page_scale)
    prepared = []
    for row in pages:
        if row.get('reviewed') is not True:
            continue
        path = source / row['source']
        if not path.resolve().is_relative_to(source.resolve()) or digest(path) != row['source_sha256']:
            raise ValueError(f'Unsafe or changed source: {path}')
        if Path(row['id']).name != row['id']:
            raise ValueError('Unsafe page id')
        sd, _ = tim(path.read_bytes(), row.get('offset', 0), row.get('palette', 0))
        base = row.get('background')
        if base:
            if game is None or not (game / base['path']).resolve().is_relative_to(game.resolve()):
                raise ValueError('HD background requires a safe --game path')
            if digest(game / base['path']) != base['sha256']:
                raise ValueError('HD background changed')
        background = Image.open(game / base['path']) if base else None
        mode = (None if not plate or row.get('status') else 'outline' if plate == 'outline'
                else 'outline' if row.get('classification') in ('title', 'caption') else 'page')
        high, layout = render_lines(row['lines'], font, tuple(row.get('logical_size', [256, 192])), background, row.get('erase', []), mode,
                                    centered=bool(plate) and row.get('classification') == 'title',
                                    scale=doc_scale.get((row.get('document') or {}).get('file_id', row['id'])) if row.get('classification') != 'title' else None)
        prepared.append((row, sd, high, layout))
    output.mkdir(parents=True)
    results = []
    for row, sd, high, layout in prepared:
        dest = output / (row['id'] + '.png')
        high.save(dest)
        variants = []
        if row.get('status'):
            raw = (source / row['source']).read_bytes()
            palette_rows, = struct.unpack('<H', take(raw, 18, 2))
            route_rows = status_route['palettes'] if status_route else None
            if route_rows and len(route_rows) != palette_rows:
                raise ValueError('Status route CLUT count differs from TIM')
            for index in range(palette_rows):
                colored_sd, _ = tim(raw, palette=index)
                key = texture_key(colored_sd, order='RGBA')
                if route_rows and (route_rows[index]['palette'] != index or route_rows[index]['key'] != key):
                    raise ValueError(f'Native status key mismatch for CLUT {index}')
                foreground = max(colored_sd.get_flattened_data(), key=lambda color: sum(color[:3]))
                colored = ImageChops.multiply(high, Image.new('RGBA', high.size, (*foreground[:3], 255)))
                name = f'{row["id"]}-palette-{index}.webp'
                target = output / name
                colored.save(target, lossless=True, exact=True)
                assert Image.open(target).convert('RGBA').tobytes() == colored.tobytes()
                variants.append({'palette': index, 'path': route_rows[index]['path'] if route_rows else f'hires/misc/{key}.webp', 'asset': name, 'sha256': digest(target), 'foreground': list(foreground[:3]), 'native_rgba_sha256': route_rows[index].get('native_rgba_sha256') if route_rows else None})
        sd.save(output / (row['id'] + '-sd.png'))
        results.append({'id': row['id'], 'source': row['source'], 'offset': row.get('offset', 0),
                        'source_sha256': row['source_sha256'], 'sd_size': list(sd.size),
                        'hd_size': list(high.size), 'png': dest.name, 'sha256': digest(dest),
                        'layout': layout, 'document': row.get('document'), 'sd_png': row['id'] + '-sd.png',
                        'sd_sha256': digest(output / (row['id'] + '-sd.png')), 'status_variants': variants})
    report = {'status': 'HD CANDIDATES; observed lookup required before installation',
              'font': {'path': str(Path(font).resolve()), 'sha256': digest(font)},
              'plan': str(plan_path), 'plan_sha256': digest(plan_path), 'pages': results,
              'documents': coverage, 'skipped_unreviewed': (coverage['unreviewed'] if coverage else 0) + sum(row.get('reviewed') is not True for row in plan['pages'])}
    if documents_path:
        report['documents']['manifest'] = str(documents_path)
        report['documents']['manifest_sha256'] = digest(documents_path)
    if status_route_path:
        report['status_route'] = {'path': str(status_route_path), 'sha256': digest(status_route_path)}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def png_texture_key(image):
    # Native PNG path (ddraw 1.0.3 RVA 0x67d80) keeps sentinel B=1 even at alpha=0.
    pixels = bytearray(image.convert('RGBA').tobytes('raw', 'BGRA'))
    for pos in range(0, len(pixels), 4):
        if pixels[pos:pos + 3] == b'\0\0\0':
            pixels[pos] = 1
    return f'{zlib.crc32(pixels):08X}'


def install_documents(output, game, backup):
    """Install verified document/status replacements with hash-guarded recovery."""
    import pefile
    if digest(game / 'ddraw.dll') != '8ef09511a5612574b240e602b19bd1692a2c33bd0c1a5fab1348738c70c64423' or digest(game / 'BIOHAZARD(R) 3 PC.exe') != 'b5215af19ea062770bc1c941ea1dd17670cd86362c43a31289ff5bb0bf7e2357':
        raise ValueError('Document route requires the verified SourceNext/REbirth 1.0.3 binaries')
    if backup.exists() or backup.resolve().is_relative_to(game.resolve()):
        raise ValueError('Choose a new backup directory outside game')
    report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    exe = pefile.PE(str(game / 'BIOHAZARD(R) 3 PC.exe'))
    starts = struct.unpack('<31H', exe.get_data(0x134f5c, 62))
    sizes = struct.unpack('<141I', exe.get_data(0x134d28, 564))
    ddraw = pefile.PE(str(game / 'ddraw.dll'))
    pending, keys, planned = [], {}, set()
    for row in report['pages']:
        for variant in row.get('status_variants', []):
            source = output / variant['asset']
            relative = Path(variant['path'])
            if relative in planned or not source.resolve().is_relative_to(output.resolve()) or digest(source) != variant['sha256']:
                raise ValueError('Invalid or changed status candidate')
            image = Image.open(source).convert('RGBA')
            if image.size != (1024, 288):
                raise ValueError('Status variant must be genuine 4x HD')
            planned.add(relative)
            pending.append((relative, source, image))
        mapping = row.get('document')
        if mapping is None:
            continue
        file_id, page = mapping['file_id'], mapping['page']
        if not 0 <= file_id < 31 or not 0 <= page < 100:
            raise ValueError('Invalid document index')
        index = starts[file_id] + page
        if mapping.get('pc_controls'):
            if file_id != 0 or not 2 <= index <= 5:
                raise ValueError('Invalid PC controls index')
            pointer, = struct.unpack('<I', ddraw.get_data(0x3f3b8c + index * 4, 4))
            native_name = ddraw.get_data(pointer - 0x10000000, 32).split(b'\0')[0].decode()
            if file_id != 0 or not 2 <= index <= 5 or Path(row['source']).name.lower() != native_name or row['offset'] != 0:
                raise ValueError('PC control page differs from native mapping')
        elif index >= 141 or row['offset'] != sum(sizes[:index]):
            raise ValueError('Document source offset does not match native table')
        sd_path, high_path = output / row['sd_png'], output / row['png']
        if not sd_path.resolve().is_relative_to(output.resolve()) or not high_path.resolve().is_relative_to(output.resolve()):
            raise ValueError('Unsafe candidate path')
        if digest(sd_path) != row['sd_sha256'] or digest(high_path) != row['sha256']:
            raise ValueError('Candidate changed')
        sd, high = Image.open(sd_path).convert('RGBA'), Image.open(high_path).convert('RGBA')
        if sd.size != (256, 176) or high.size != (1024, 704):
            raise ValueError('Document pair must retain exact 4x dimensions')
        key = png_texture_key(sd)
        if key in keys and keys[key] != high.tobytes():
            raise ValueError('CRC collision between document pages')
        relative = Path(f'file/file_{file_id:02X}{page:02d}.png')
        if relative in planned:
            raise ValueError('Duplicate document target')
        planned.add(relative)
        pending.append((relative, sd_path, None))
        if key not in keys:
            pending.append((Path(f'hires/memo/{key}.webp'), high_path, high))
        keys[key] = high.tobytes()
    if not pending:
        raise ValueError('No mapped document pairs')
    backup.mkdir(parents=True)
    record = {'game': str(game.resolve()), 'build': str(output.resolve()), 'backup': str(backup.resolve()), 'status': 'prepared', 'files': []}
    # Complete all backups before the first game mutation.
    for relative, source, high in pending:
        target = game / relative
        if not target.resolve().is_relative_to(game.resolve()):
            raise ValueError('Target symlink escapes game')
        old = digest(target) if target.exists() else None
        if old:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            assert digest(saved) == old
        record['files'].append({'path': str(relative), 'before': old, 'after': None})
    record_path = backup / 'install.json'
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    for (relative, source, high), row in zip(pending, record['files']):
        target = game / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if (digest(target) if target.exists() else None) != row['before']:
            raise ValueError('Target changed after backup')
        if high is None:
            shutil.copy2(source, target)
            assert digest(target) == digest(source)
        else:
            high.save(target, lossless=True, exact=True)
            assert Image.open(target).convert('RGBA').tobytes() == high.tobytes()
        row['after'] = digest(target)
        record_path.write_text(json.dumps(record, indent=2) + '\n')
    record['status'] = 'installed; live screen pending'
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    return record


def restore_install(record_path):
    """Restore only paths that still match this install's after-hash."""
    record_path = Path(record_path)
    record = json.loads(record_path.read_text(encoding='utf-8'))
    game, backup = Path(record['game']), Path(record.get('backup', record_path.parent))
    for row in reversed(record['files']):
        target = game / row['path']
        if not target.resolve().is_relative_to(game.resolve()):
            raise ValueError(f'Unsafe restore target: {row["path"]}')
        actual = digest(target) if target.is_file() else None
        if actual != row['after']:
            raise ValueError(f'Installed file changed since recorded: {row["path"]}')
        if row['before'] is None:
            target.unlink()
        else:
            saved = backup / row['path']
            if digest(saved) != row['before']:
                raise ValueError(f'Backup hash mismatch: {row["path"]}')
            shutil.copy2(saved, target)
            if digest(target) != row['before']:
                raise ValueError(f'Restore verification failed: {row["path"]}')
    record['status'] = 'restored; hashes verified'
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--font', type=Path, default=DEFAULT_FONT)
    parser.add_argument('--documents', type=Path, help='141-page reviewed transcription manifest')
    parser.add_argument('--text-style', choices=('outline', 'plate'), help='outlined text, or translucent plates (page for body, line for titles/captions); both enlarge text')
    parser.add_argument('--status-route', type=Path, help='Native CLUT/CRC proof JSON')
    parser.add_argument('--game', type=Path, help='Read installed HD backgrounds')
    parser.add_argument('--install-documents', action='store_true', help='Install mapped PNG/HD pairs after build')
    parser.add_argument('--backup', type=Path, help='New backup directory outside the game')
    parser.add_argument('--restore', type=Path, help='Restore a prior install.json after after-hash checks')
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(restore_install(args.restore), ensure_ascii=False))
        return
    if not args.source or not args.plan or not args.output:
        parser.error('--source, --plan, and --output are required for a build')
    if args.install_documents and (args.game is None or args.backup is None):
        parser.error('--install-documents requires --game and --backup')
    result = build(args.source, args.plan, args.output, args.font, args.game, args.documents, args.status_route, args.text_style)
    if args.install_documents:
        install_documents(args.output, args.game, args.backup)
    print(json.dumps({'pages': len(result['pages']), 'skipped_unreviewed': result['skipped_unreviewed'], 'font': result['font']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
