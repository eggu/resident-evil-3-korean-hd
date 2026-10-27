"""Build dist/re3-korean-hd-<VERSION>.zip, a package players copy straight into the game folder.

Builds bin/korean_hd.dll, runs setup.py on the given game folder, then packs exactly the files
setup installed (mod_korean_hd/ and the hires/ textures listed in work/*-installed.txt).
"""
import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
LISTS = {'mod_korean_hd': ['mod-installed.txt'],
         'hires/misc': ['font-hd-installed.txt', 'status-hd-installed.txt', 'doc-pages-installed.txt'],
         'hires/memo': ['doc-memo-installed.txt']}


def build_dll(version):
    gcc = shutil.which('i686-w64-mingw32-gcc')
    if not gcc:
        raise SystemExit('i686-w64-mingw32-gcc is required to build bin/korean_hd.dll')
    (ROOT / 'bin').mkdir(exist_ok=True)
    subprocess.run([gcc, '-shared', '-O2', '-s', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation', '-Wno-format-truncation',
                    f'-DKOREAN_HD_VERSION="{version}"', str(ROOT / 'src/korean_hd.c'), '-ladvapi32', '-o', str(ROOT / 'bin/korean_hd.dll')], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game', type=Path, required=True, help='SourceNext + Classic REbirth game folder with the HD pack (hires/)')
    args = parser.parse_args()
    version = (ROOT / 'VERSION').read_text().strip()
    build_dll(version)
    subprocess.run([sys.executable, str(ROOT / 'tools/setup.py'), '--game', str(args.game)], check=True)
    out = ROOT / f'dist/re3-korean-hd-{version}.zip'
    out.parent.mkdir(exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for folder, lists in LISTS.items():
            for name in sorted(n for listing in lists for n in (WORK / listing).read_text().split()):
                z.write(args.game / folder / name, f'{folder}/{name}')
                count += 1
        z.write(ROOT / 'packaging/README.txt', 'README-Korean-HD.txt')
        z.write(ROOT / 'LICENSE', 'mod_korean_hd/LICENSE.txt')
    print(f'{out.relative_to(ROOT)}: {count} files ({out.stat().st_size // 1024} KiB)')


if __name__ == '__main__':
    main()
