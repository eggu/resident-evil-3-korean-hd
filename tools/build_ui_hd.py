"""Build verified 4x status-atlas text replacements and reversible installs."""
import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

from build_hd import DEFAULT_FONT, digest, load_font, texture_key, tim

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / 'translation/ui-hd-reviewed.json'
PLAN = ROOT / 'translation/hd-reviewed.json'
SCALE = 4


def _font_characters(font_path, rows):
    chars = {char for row in rows for char in row['text'] if not char.isspace()}
    with TTFont(str(font_path), fontNumber=0) as face:
        cmap = face.getBestCmap() or {}
    missing = sorted(char for char in chars if ord(char) not in cmap)
    if missing:
        raise ValueError(f'Font missing glyphs: {missing}')


def _color_for_cell(source, cell):
    x0, y0, x1, y1 = cell
    colors = Counter(pixel[:3] for y in range(y0, y1) for x in range(x0, x1)
                     if (pixel := source.getpixel((x, y)))[3])
    if not colors:
        raise ValueError(f'No source glyph pixels in cell {cell}')
    # Prefer the original glyph's brightest palette color; TIM palette rows
    # retain separate health-state hues and dark edge colors.
    return max(colors, key=lambda color: sum(color))


def _source_bounds(source, cell):
    x0, y0, x1, y1 = cell
    bounds = source.crop(cell).getchannel('A').getbbox()
    if bounds is None:
        raise ValueError(f'No source glyph pixels in cell {cell}')
    return [bounds[0] + x0, bounds[1] + y0, bounds[2] + x0, bounds[3] + y0]


def render_atlas(background, source_tim, palette, layout, bottom_lines, font_path, fit=False):
    source, _ = tim(source_tim, palette=palette)
    if source.size != (256, 72) or background.size != (1024, 288):
        raise ValueError('Status atlas must be 256x72 source and 1024x288 background')
    rows = layout['texts'] + [dict(line, cell=cell) for line, cell in zip(bottom_lines, layout['bottom_cells'])]
    _font_characters(font_path, rows)
    image = background.convert('RGBA').copy()
    source_hd = source.resize((1024, 288), Image.Resampling.NEAREST)
    image.alpha_composite(source_hd)
    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in layout['erase']:
        if min(x0, y0) < 0 or x1 <= x0 or y1 <= y0 or x1 > 256 or y1 > 72:
            raise ValueError(f'Invalid text erase box {(x0, y0, x1, y1)}')
        draw.rectangle((x0 * SCALE, y0 * SCALE, x1 * SCALE - 1, y1 * SCALE - 1), fill=(0, 0, 0, 0))
    rendered = []
    cells = [row['cell'] for row in rows]
    line_sizes = {}
    for row in rows if fit else ():
        # Largest size keeping a 10% margin in the cell; labels on one line share the smallest.
        x0, y0, x1, y1 = row['cell']
        size = row['size'] * SCALE
        while True:
            b = draw.textbbox((0, 0), row['text'], font=load_font(font_path, size + 1), anchor='lt')
            if b[2] - b[0] > (x1 - x0) * SCALE * 0.9 or b[3] - b[1] > (y1 - y0) * SCALE * 0.9:
                break
            size += 1
        line_sizes[(y0, y1)] = min(size, line_sizes.get((y0, y1), size))
    for row in rows:
        text, cell = row['text'], row['cell']
        x0, y0, x1, y1 = cell
        if min(x0, y0) < 0 or x1 <= x0 or y1 <= y0 or x1 > 256 or y1 > 72:
            raise ValueError(f'Invalid glyph cell {cell}')
        if not text or row['size'] <= 0:
            raise ValueError('Invalid UI glyph row')
        source_bounds = _source_bounds(source, cell)
        cell_width, cell_height = (x1 - x0) * SCALE, (y1 - y0) * SCALE
        size = line_sizes[(y0, y1)] if fit else row['size'] * SCALE
        font = load_font(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font, anchor='lt')
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if width > cell_width or height > cell_height:
            raise ValueError(f'Font text exceeds source cell {cell}: {text}')
        # Centre on the SD glyph ink: the game crops each label around where it was drawn.
        sx0, sy0, sx1, sy1 = source_bounds
        x = (sx0 + sx1) * SCALE // 2 - width // 2 - bbox[0]
        y = (sy0 + sy1) * SCALE // 2 - height // 2 - bbox[1]
        x = min(max(x, x0 * SCALE - bbox[0]), x1 * SCALE - width - bbox[0]) + layout.get('nudge_x_hd', {}).get(text, 0)
        y = min(max(y, y0 * SCALE - bbox[1]), y1 * SCALE - height - bbox[1])
        color = _color_for_cell(source, cell)
        draw.text((x, y), text, font=font, fill=(*color, 255), anchor='lt')
        rendered.append({'text': text, 'cell': cell, 'source_ink_bounds': source_bounds,
                         'bounds_hd': [x + bbox[0], y + bbox[1], x + bbox[2], y + bbox[3]],
                         'font_px': size, 'color': list(color)})
    for x0, y0, x1, y1 in layout['erase']:
        for y in range(y0, y1):
            for x in range(x0, x1):
                if source.getpixel((x, y))[3] and not any(cx0 <= x < cx1 and cy0 <= y < cy1
                                                         for cx0, cy0, cx1, cy1 in cells):
                    raise ValueError(f'Erased source glyph pixel outside reviewed cells: {(x, y)}')
    return image, rendered


def review_sample(source_path, output, variants, font_path):
    canvas = Image.new('RGBA', (2048, 640), (20, 24, 36, 255))
    draw = ImageDraw.Draw(canvas)
    caption = ImageFont.truetype(str(font_path), 18)
    raw = Path(source_path).read_bytes()
    for row_index, palette in enumerate((1, 6)):
        y = row_index * 320
        sd, _ = tim(raw, palette=palette)
        sd = sd.resize((1024, 288), Image.Resampling.NEAREST)
        hd = Image.open(output / variants[palette]['asset']).convert('RGBA')
        left = Image.alpha_composite(Image.new('RGBA', sd.size, (20, 24, 36, 255)), sd)
        right = Image.alpha_composite(Image.new('RGBA', hd.size, (20, 24, 36, 255)), hd)
        canvas.alpha_composite(left, (0, y + 32))
        canvas.alpha_composite(right, (1024, y + 32))
        draw.text((8, y + 6), f'CLUT {palette}: source enlarged 4x', font=caption, fill='white')
        draw.text((1032, y + 6), f'CLUT {palette}: 4x font atlas', font=caption, fill='white')
    path = output / 'review-sd-vs-hd.png'
    canvas.save(path)
    return {'path': path.name, 'sha256': digest(path), 'size': list(canvas.size)}


def build_ui(source, game, output, font=DEFAULT_FONT, layout_path=LAYOUT,
             plan_path=PLAN, route_path=None, fit=False):
    load_font(font)
    route_path = route_path or ROOT / 'translation/status-route.json'
    layout = json.loads(Path(layout_path).read_text(encoding='utf-8'))
    route = json.loads(Path(route_path).read_text(encoding='utf-8'))
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    status_plan = next(row for row in plan['pages'] if row.get('status'))
    source_path = Path(source) / layout['source']
    background_path = Path(game) / layout['background']['path']
    if output.exists() or output.resolve().is_relative_to(Path(game).resolve()):
        raise ValueError('Choose a new output directory outside the game')
    if digest(source_path) != route['source_sha256']:
        raise ValueError('Status TIM differs from native route proof')
    if digest(Path(game) / 'ddraw.dll') != route['ddraw_sha256'] or digest(Path(game) / 'BIOHAZARD(R) 3 PC.exe') != route['exe_sha256']:
        raise ValueError('Native status proof does not match selected game binaries')
    if digest(background_path) != layout['background']['sha256']:
        raise ValueError('Status HD background differs from reviewed source')
    background = Image.open(background_path).convert('RGBA')
    if len(route['palettes']) != 9:
        raise ValueError('Expected nine emulated status CLUT candidates')
    output.mkdir(parents=True)
    variants = []
    for index, proof in enumerate(route['palettes']):
        if proof['palette'] != index:
            raise ValueError('Native status CLUT rows are not in source order')
        source_palette, _ = tim(source_path.read_bytes(), palette=index)
        key = texture_key(source_palette, order='RGBA')
        if key != proof['key']:
            raise ValueError(f'Native status key mismatch for CLUT {index}')
        high, rows = render_atlas(background, source_path.read_bytes(), index, layout,
                                  status_plan['lines'], font, fit)
        name = f'status-ui-palette-{index}.webp'
        path = output / name
        high.save(path, lossless=True, exact=True)
        if Image.open(path).convert('RGBA').tobytes() != high.tobytes():
            raise ValueError(f'WebP pixel round trip failed for CLUT {index}')
        variants.append({'palette': index, 'key': key, 'path': proof['path'], 'asset': name,
                         'source_sha256': route['source_sha256'], 'native_rgba_sha256': proof['native_rgba_sha256'],
                         'sha256': digest(path), 'rendered': rows})
    sample = review_sample(source_path, output, variants, font)
    report = {'status': 'candidate; emulated CLUT keys only, live lookup unverified',
              'font': {'path': str(Path(font).resolve()), 'sha256': digest(font)},
              'layout': {'path': str(layout_path), 'sha256': digest(layout_path)},
              'route': {'path': str(route_path), 'sha256': digest(route_path)},
              'background': {'path': layout['background']['path'], 'sha256': digest(background_path)},
              'source': {'path': str(source_path), 'sha256': digest(source_path)},
              'review_sample': sample,
              'variants': variants}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def install_ui(output, game, backup):
    output, game, backup = Path(output), Path(game), Path(backup)
    if backup.exists() or backup.resolve().is_relative_to(game.resolve()):
        raise ValueError('Choose a new backup directory outside the game')
    report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    route_info = report['route']
    route_path = Path(route_info['path'])
    if digest(route_path) != route_info['sha256']:
        raise ValueError('Native status route proof changed after build')
    route = json.loads(route_path.read_text(encoding='utf-8'))
    if digest(game / 'ddraw.dll') != '8ef09511a5612574b240e602b19bd1692a2c33bd0c1a5fab1348738c70c64423' or digest(game / 'BIOHAZARD(R) 3 PC.exe') != 'b5215af19ea062770bc1c941ea1dd17670cd86362c43a31289ff5bb0bf7e2357':
        raise ValueError('UI replacement requires the verified SourceNext/REbirth 1.0.3 binaries')
    pending = []
    for row in report['variants']:
        source = output / row['asset']
        relative = Path(row['path'])
        image = Image.open(source).convert('RGBA')
        if (not source.resolve().is_relative_to(output.resolve()) or digest(source) != row['sha256']
                or image.size != (1024, 288) or relative != Path(f'hires/misc/{row["key"]}.webp')):
            raise ValueError('Invalid or changed native status candidate')
        pending.append((relative, source, image))
    if len(pending) != 9:
        raise ValueError('Expected nine emulated CLUT candidates')
    backup.mkdir(parents=True)
    record = {'game': str(game.resolve()), 'build': str(output.resolve()), 'backup': str(backup.resolve()),
              'status': 'prepared', 'files': []}
    for relative, _, _ in pending:
        target = game / relative
        if not target.resolve().is_relative_to(game.resolve()):
            raise ValueError(f'Unsafe target: {relative}')
        before = digest(target) if target.is_file() else None
        if before:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            if digest(saved) != before:
                raise ValueError(f'Backup verification failed: {relative}')
        record['files'].append({'path': str(relative), 'before': before, 'after': None})
    record_path = backup / 'install.json'
    record_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    for (relative, source, image), row in zip(pending, record['files']):
        target = game / relative
        actual = digest(target) if target.is_file() else None
        if actual != row['before']:
            raise ValueError(f'Target changed after backup: {relative}')
        image.save(target, lossless=True, exact=True)
        if Image.open(target).convert('RGBA').tobytes() != image.tobytes():
            raise ValueError(f'Installed pixels differ: {relative}')
        row['after'] = digest(target)
        record_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    record['status'] = 'installed; live screen pending restart'
    record_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record


def restore_ui(record_path):
    record_path = Path(record_path)
    record = json.loads(record_path.read_text(encoding='utf-8'))
    game = Path(record['game'])
    backup = Path(record['backup'])
    for row in record['files']:
        target = game / row['path']
        if not target.resolve().is_relative_to(game.resolve()) or not target.is_file() or digest(target) != row['after']:
            raise ValueError(f'Installed file changed since recorded: {row["path"]}')
        saved = backup / row['path']
        if row['before'] is not None and digest(saved) != row['before']:
            raise ValueError(f'Backup hash mismatch: {row["path"]}')
    for row in reversed(record['files']):
        target = game / row['path']
        saved = backup / row['path']
        if row['before'] is None:
            target.unlink()
        else:
            shutil.copy2(saved, target)
            if digest(target) != row['before']:
                raise ValueError(f'Restore verification failed: {row["path"]}')
    record['status'] = 'restored; hashes verified'
    record_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=False)
    parser.add_argument('--game', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--font', type=Path, default=DEFAULT_FONT)
    parser.add_argument('--fit', action='store_true', help='enlarge each label to fill its source cell')
    parser.add_argument('--layout', type=Path, default=LAYOUT)
    parser.add_argument('--plan', type=Path, default=PLAN)
    parser.add_argument('--status-route', type=Path, default=ROOT / 'translation/status-route.json')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--restore', type=Path)
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(restore_ui(args.restore), ensure_ascii=False))
        return
    if not args.source or not args.game or not args.output:
        parser.error('--source, --game, and --output are required for a build')
    if args.install and not args.backup:
        parser.error('--install requires --backup')
    report = build_ui(args.source, args.game, args.output, args.font, args.layout, args.plan, args.status_route, args.fit)
    record = install_ui(args.output, args.game, args.backup) if args.install else None
    print(json.dumps({'variants': len(report['variants']), 'font': report['font'], 'install': record}, ensure_ascii=False))


if __name__ == '__main__':
    main()
