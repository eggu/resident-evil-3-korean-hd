"""Build and install every HD replacement (font pages, status atlas, documents).

Each step builds into work/hd/<step>, then copies into the game's hires/ folder.
Every file it overwrites or removes is first copied to work/backups/hd-<time>/, and the
installed file lists (work/*-installed.txt) are rewritten so the next run can clean up.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_hd import png_texture_key, tim  # noqa: E402

from PIL import Image  # noqa: E402

LOCAL = ROOT / 'work'
FONTS = LOCAL / 'fonts'
INSTANCES = {  # static instance -> (variable font, wght)
    'NotoSansKR-Regular.ttf': ('NotoSansKR[wght].ttf', 400),
    'NotoSansKR-Bold.ttf': ('NotoSansKR[wght].ttf', 700),
    'NotoSerifKR-SemiBold.ttf': ('NotoSerifKR[wght].ttf', 600),
}


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def static_fonts():
    """Variable Noto fonts default to Thin, so the builds use pinned static instances."""
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    FONTS.mkdir(parents=True, exist_ok=True)
    for name, (source, weight) in INSTANCES.items():
        if not (FONTS / name).exists():
            instantiateVariableFont(TTFont(ROOT / 'assets/fonts' / source), {'wght': weight}).save(FONTS / name)


class Installer:
    def __init__(self, game):
        self.game, self.backup = game, LOCAL / f'backups/hd-{time.strftime("%Y%m%d-%H%M%S")}'

    def _save(self, dest):
        if dest.exists():
            copy = self.backup / dest.relative_to(self.game)
            copy.parent.mkdir(parents=True, exist_ok=True)
            if not copy.exists():
                shutil.copy2(dest, copy)

    def put(self, source, dest):
        self._save(dest)
        shutil.copy(source, dest)

    def remove(self, dest):
        self._save(dest)
        dest.unlink(missing_ok=True)


def fresh(name):  # builders create the folder themselves (build_hd and build_ui_hd require a new one)
    out = LOCAL / 'hd' / name
    shutil.rmtree(out, ignore_errors=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def install_set(inst, folder, files, listing):
    """Replace the previously installed set listed in work/<listing> with files."""
    misc = inst.game / 'hires/misc'
    record = LOCAL / listing
    for name in (record.read_text().split() if record.exists() else []):
        if name not in files:
            inst.remove(misc / name)
    for name in files:
        inst.put(folder / name, misc / name)
    record.write_text(''.join(f'{n}\n' for n in sorted(files)))
    return len(files)


def fonts_step(inst, args):
    out = fresh('font')
    run('tools/build_font_hd.py', '--font', FONTS / 'NotoSansKR-Regular.ttf', '--output', out)
    return install_set(inst, out, sorted(p.name for p in out.glob('*.webp')), 'font-hd-installed.txt')


def status_step(inst, args):
    out = fresh('status')
    run('tools/build_ui_hd.py', '--source', args.game / 'mod_korean_hd', '--game', args.game,
        '--output', out, '--font', FONTS / 'NotoSansKR-Bold.ttf', '--fit')
    data = (args.game / 'mod_korean_hd/DATA_J/ETC2/STMOJIJ.TIM').read_bytes()
    files = {}
    for variant in json.loads((out / 'report.json').read_text())['variants']:
        rgba = tim(data, palette=variant['palette'])[0].convert('RGBA')
        key = f'{zlib.crc32(rgba.tobytes("raw", "BGRA")):08X}.webp'  # REbirth crop key
        shutil.copy(out / variant['asset'], out / key)
        files[key] = None
    return install_set(inst, out, sorted(files), 'status-hd-installed.txt')


def documents_step(inst, args):
    out = fresh('documents')
    run('tools/build_hd.py', '--source', args.game / 'mod_korean_hd', '--plan', 'translation/hd-reviewed.json',
        '--documents', 'translation/documents-reviewed.json', '--game', args.game,
        '--font', FONTS / 'NotoSerifKR-SemiBold.ttf', '--text-style', 'plate', '--output', out)
    replaced = []
    for row in json.loads((out / 'report.json').read_text())['pages']:
        if row.get('status'):
            continue
        dest = args.game / f'hires/memo/{png_texture_key(Image.open(out / row["sd_png"]))}.webp'
        if dest.exists():  # memo route: only keys REbirth already ships a document for
            inst._save(dest)
            Image.open(out / row['png']).convert('RGBA').save(dest, lossless=True, exact=True)
            replaced.append(dest.name)
    (LOCAL / 'doc-memo-installed.txt').write_text(''.join(f'{n}\n' for n in sorted(replaced)))
    # JapaneseEnable=1 keys whole VRAM pages; rebuild them from the memo images just written
    pages = fresh('doc-pages')
    run('tools/build_doc_pages.py', '--game', args.game, '--output', pages)
    return f'{len(replaced)} memo, {install_set(inst, pages, sorted(p.name for p in pages.glob("*.webp")), "doc-pages-installed.txt")} pages'


STEPS = {'fonts': fonts_step, 'status': status_step, 'documents': documents_step}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('steps', nargs='*', help=f'subset of {", ".join(STEPS)} (default: all)')
    args = parser.parse_args()
    args.steps = args.steps or list(STEPS)
    if set(args.steps) - set(STEPS):
        parser.error(f'unknown step: {", ".join(sorted(set(args.steps) - set(STEPS)))}')
    if subprocess.run(['pgrep', '-f', r'BIOHAZARD\(R\) 3 PC.exe'], capture_output=True).returncode == 0:
        print('note: the game is running; restart it to see the new textures')
    static_fonts()
    inst = Installer(args.game)
    for step in args.steps:
        print(f'{step}: {STEPS[step](inst, args)}')
    print(f'backup: {inst.backup.relative_to(ROOT) if inst.backup.exists() else "nothing overwritten"}')


if __name__ == '__main__':
    main()
