"""Build dist/re3-korean-hd-<VERSION>.zip (REbirth mod) and dist/re3-korean-hd-<VERSION>-asi.zip (ASI),
packages players copy straight into the game folder.

Builds bin/korean_hd.dll and bin/RE3.KoreanHD.asi, runs setup.py in both modes on the given game folder,
then packs exactly the files setup installed (work/*-installed.txt) plus the HD textures.
"""
import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
HD_LISTS = {'hires/misc': ['font-hd-installed.txt', 'status-hd-installed.txt', 'doc-pages-installed.txt', 'texts-hd-installed.txt'],
            'hires/memo': ['doc-memo-installed.txt'],
            'hires/bgd': ['screens-hd-installed.txt']}
PACKAGES = {  # mode -> (zip suffix, installed list, readme, extra define, binary)
    'rebirth': ('', 'rebirth-installed.txt', 'packaging/README.txt', [], 'korean_hd.dll'),
    'asi': ('-asi', 'asi-installed.txt', 'packaging/README-ASI.txt', ['-DKOREAN_HD_ASI'], 'RE3.KoreanHD.asi'),
}


def build_binary(version, define, name):
    gcc = shutil.which('i686-w64-mingw32-gcc')
    if not gcc:
        raise SystemExit(f'i686-w64-mingw32-gcc is required to build bin/{name}')
    (ROOT / 'bin').mkdir(exist_ok=True)
    subprocess.run([gcc, '-shared', '-O2', '-s', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation', '-Wno-format-truncation', *define,
                    f'-DKOREAN_HD_VERSION="{version}"', str(ROOT / 'src/korean_hd.c'), '-ladvapi32', '-o', str(ROOT / 'bin' / name)], check=True)


def pack(game, version, mode):
    suffix, listing, readme, _, _ = PACKAGES[mode]
    out = ROOT / f'dist/re3-korean-hd-{version}{suffix}.zip'
    out.parent.mkdir(exist_ok=True)
    names = [('', n) for n in (WORK / listing).read_text().split()]
    names += [(folder, n) for folder, lists in HD_LISTS.items() for l in lists for n in (WORK / l).read_text().split()]
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for folder, name in sorted(names):
            z.write(game / folder / name, f'{folder}/{name}'.lstrip('/'))
        z.write(ROOT / readme, 'README-Korean-HD.txt')
        z.write(ROOT / 'LICENSE', 'mod_korean_hd/LICENSE.txt')
    print(f'{out.relative_to(ROOT)}: {len(names)} files ({out.stat().st_size // 1024} KiB)')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game', type=Path, required=True, help='SourceNext + Classic REbirth game folder with the HD pack (hires/)')
    args = parser.parse_args()
    version = (ROOT / 'VERSION').read_text().strip()
    for mode, (_, _, _, define, name) in PACKAGES.items():
        build_binary(version, define, name)
    for index, mode in enumerate(PACKAGES):  # HD textures are built once, by the first run
        cmd = [sys.executable, str(ROOT / 'tools/setup.py'), '--game', str(args.game), '--mode', mode] + (['--no-hd'] if index else [])
        subprocess.run(cmd, check=True)
    for mode in PACKAGES:
        pack(args.game, version, mode)


if __name__ == '__main__':
    main()
