"""Build dist/re3-korean-hd-<VERSION>.zip: tracked files plus a fresh bin/korean_hd.dll."""
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = (ROOT / 'VERSION').read_text().strip()
    gcc = shutil.which('i686-w64-mingw32-gcc')
    if not gcc:
        raise SystemExit('i686-w64-mingw32-gcc is required to build bin/korean_hd.dll')
    (ROOT / 'bin').mkdir(exist_ok=True)
    dll = ROOT / 'bin/korean_hd.dll'
    subprocess.run([gcc, '-shared', '-O2', '-s', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation', '-Wno-format-truncation',
                    f'-DKOREAN_HD_VERSION="{version}"', str(ROOT / 'src/korean_hd.c'), '-ladvapi32', '-o', str(dll)], check=True)
    files = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split('\n')
    name = f're3-korean-hd-{version}'
    out = ROOT / f'dist/{name}.zip'
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in filter(None, files):
            z.write(ROOT / f, f'{name}/{f}')
        z.write(dll, f'{name}/bin/korean_hd.dll')
    print(f'{out.relative_to(ROOT)} ({out.stat().st_size // 1024} KiB)')


if __name__ == '__main__':
    main()
