"""Build and install the Korean HD mod into a SourceNext RE3 + Classic REbirth game folder.

Everything is built from the mod's translation data (translation/) and the game's own files:
  1. writes mod_korean_hd/ (DLL, Korean data, patched graphics, manifest),
  2. builds and installs the HD font, status screen and document textures into hires/
     (skipped with --no-hd or when hires/ is missing).
Anything it overwrites is copied to work/backups/ first.
"""
import argparse
import configparser
import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_exe_text import SOURCENEXT_SHA256, ddraw_sites, serialize, sourcenext_sites  # noqa: E402
from build_rebirth_text import build as build_rebirth, load as load_json  # noqa: E402
from formats import korean_files, rofs_decode, rofs_index, take  # noqa: E402
from rebirth_profiles import profile  # noqa: E402
from translation import build_files, build_rooms, load_exe  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
VERSION = (ROOT / 'VERSION').read_text().strip()
EXE = 'BIOHAZARD(R) 3 PC.exe'
ORIGINAL_DIRS = ('DATA/ETC/', 'DATA_J/ETC2/', 'DATA_AJ/ETC2/')  # graphics the HD builders read
MANIFEST = f'''[MOD]
Name = Resident Evil 3 - Korean HD {VERSION}
Title = BIOHAZARD 3 - Korean HD
Module = korean_hd.dll
ForceEng = 0
ConfigAltFont = 0
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fail(message):
    raise SystemExit(f'error: {message}')


def check_game(game):
    exe = game / EXE
    if not exe.exists() or sha(exe.read_bytes()) not in SOURCENEXT_SHA256:
        fail(f'{exe} is not the SourceNext BIOHAZARD(R) 3 PC.exe this mod supports')
    if not (game / 'ddraw.dll').exists():
        fail('ddraw.dll (Classic REbirth) not found in the game folder')
    rebirth = profile((game / 'ddraw.dll').read_bytes())
    config = configparser.ConfigParser(strict=False)
    config.read(game / 'config.ini', encoding='utf-8')
    if config.get('DLL', 'JapaneseEnable', fallback='0').strip() != '1':
        print('warning: set JapaneseEnable = 1 under [DLL] in config.ini (Korean text uses the Japanese font route)')
    return rebirth


def extract_originals(game):
    """Original graphics from the ROFS archives (also the base for the patched files)."""
    originals = {}
    for archive in sorted(game.glob('[Rr]ofs*.dat')):
        data = archive.read_bytes()
        for name, offset, size in rofs_index(data):
            if name.startswith(ORIGINAL_DIRS):
                originals[name] = rofs_decode(take(data, offset, size))
    for name, data in originals.items():
        dest = WORK / 'original' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return originals


def patched_graphics(originals, krf2):
    file_runs, _ = korean_files(krf2)
    out = {}
    for name, original in originals.items():
        runs = file_runs.get(Path(name).name.lower())
        if runs:
            data = bytearray(original)
            for offset, length, source in runs:
                data[offset:offset + length] = take(krf2, source, length)
            out[name] = bytes(data)
    return out


def module_dll():
    for candidate in (ROOT / 'bin/korean_hd.dll', WORK / 'korean_hd.dll'):
        if candidate.exists():
            return candidate
    gcc = shutil.which('i686-w64-mingw32-gcc')
    if not gcc:
        fail('bin/korean_hd.dll is missing (use the release zip) and i686-w64-mingw32-gcc is not installed')
    WORK.mkdir(exist_ok=True)
    subprocess.run([gcc, '-shared', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation', '-Wno-format-truncation',
                    f'-DKOREAN_HD_VERSION="{VERSION}"', str(ROOT / 'src/korean_hd.c'), '-ladvapi32', '-o', str(WORK / 'korean_hd.dll')], check=True)
    return WORK / 'korean_hd.dll'


def install_mod(game, files, backup):
    mod = game / 'mod_korean_hd'
    for relative, data in files.items():
        dest = mod / relative
        if dest.exists():
            if dest.read_bytes() == data:
                continue
            saved = backup / 'mod_korean_hd' / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, saved)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game', type=Path, required=True, help='game folder with BIOHAZARD(R) 3 PC.exe and ddraw.dll')
    parser.add_argument('--no-hd', action='store_true', help='skip the HD texture build')
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep our lines ordered with install_hd.py's
    game = args.game.resolve()
    rebirth = check_game(game)
    print(f'game: SourceNext exe, Classic REbirth {rebirth["name"]}')
    originals = extract_originals(game)
    sn, ddraw = (game / EXE).read_bytes(), (game / 'ddraw.dll').read_bytes()
    allocation, tables, writes = load_exe()
    sites = sourcenext_sites(sn, tables, writes)
    krf2 = build_files()
    files = {
        'korean_hd.dll': module_dll().read_bytes(),
        'manifest.txt': MANIFEST.encode(),
        'description.txt': f'Korean text and HD fonts/documents, version {VERSION}.\n'.encode(),
        'korean_rooms.bin': build_rooms(),
        'korean_files.bin': krf2,
        'korean_exe.bin': serialize(allocation, sites, writes, ddraw_sites(ddraw, sites)),
        'korean_rebirth.bin': build_rebirth(ddraw, load_json(ROOT / 'translation/rebirth-glyphs.json'), load_json(ROOT / 'translation/rebirth-ui.json')),
        **patched_graphics(originals, krf2),
    }
    backup = WORK / f'backups/setup-{time.strftime("%Y%m%d-%H%M%S")}'
    install_mod(game, files, backup)
    (WORK / 'mod-installed.txt').write_text(''.join(f'{n}\n' for n in sorted(files)))  # make_release packs these
    print(f'mod_korean_hd: {len(files)} files')
    if args.no_hd:
        print('HD textures skipped (--no-hd)')
    elif not (game / 'hires').is_dir():
        print('HD textures skipped: no hires/ folder (install the Mulderland Enhancement Pack first)')
    else:
        subprocess.run([sys.executable, str(ROOT / 'tools/install_hd.py'), '--game', str(game)], check=True)
    if backup.exists():
        print(f'backup of replaced mod files: {backup.relative_to(ROOT)}')
    print('done. Start the game with the -dev_korean_hd flag, or pick "Korean HD" in the REbirth mod list.')


if __name__ == '__main__':
    main()
