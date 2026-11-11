"""Build and install the Korean HD mod into a SourceNext RE3 + Classic REbirth game folder.

Everything is built from the mod's translation data (translation/) and the game's own files:
  1. --mode asi (default): RE3.KoreanHD.asi, mod_korean_hd/ (Korean data) and the patched graphics over the originals;
     --mode rebirth: mod_korean_hd/ only (DLL, Korean data, patched graphics, manifest),
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
MANIFEST = f'''[MOD]
Name = Resident Evil 3 - Korean HD {VERSION}
Title = BIOHAZARD 3 - Korean HD
Module = korean_hd.dll
ForceEng = 0
ConfigAltFont = 0
'''
MODULE_NAME = {'rebirth': 'korean_hd.dll', 'asi': 'RE3.KoreanHD.asi'}
ORIGINAL_DIRS = ('DATA/ETC/', 'DATA_J/ETC2/', 'DATA_AJ/ETC2/')  # graphics the HD builders read
def sha(data):
    return hashlib.sha256(data).hexdigest()


def fail(message):
    raise SystemExit(f'error: {message}')


def check_game(game):
    exe = game / EXE
    if not exe.exists() or sha(exe.read_bytes()) not in SOURCENEXT_SHA256:
        fail(f'{exe} is not the SourceNext BIOHAZARD(R) 3 PC.exe this mod supports')
    if not (game / 'dsound.dll').exists():
        print('warning: no Ultimate ASI Loader (dsound.dll) in the game folder; the .asi will not load')
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


def module_dll(mode):
    name = MODULE_NAME[mode]
    for candidate in (ROOT / 'bin' / name, WORK / name):
        if candidate.exists():
            return candidate
    gcc = shutil.which('i686-w64-mingw32-gcc')
    if not gcc:
        fail(f'bin/{name} is missing (use the release zip) and i686-w64-mingw32-gcc is not installed')
    WORK.mkdir(exist_ok=True)
    define = ['-DKOREAN_HD_ASI'] if mode == 'asi' else []
    subprocess.run([gcc, '-shared', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation', '-Wno-format-truncation', *define,
                    f'-DKOREAN_HD_VERSION="{VERSION}"', str(ROOT / 'src/korean_hd.c'), '-ladvapi32', '-o', str(WORK / name)], check=True)
    return WORK / name


def install_files(game, files, backup):
    """Write files under game/, copying anything it replaces to backup/ first."""
    for relative, data in files.items():
        dest = game / relative
        if dest.exists():
            if dest.read_bytes() == data:
                continue
            saved = backup / relative
            if not saved.exists():
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, saved)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game', type=Path, required=True, help='game folder with BIOHAZARD(R) 3 PC.exe and ddraw.dll')
    parser.add_argument('--mode', choices=sorted(MODULE_NAME), default='asi',
                        help='asi: RE3.KoreanHD.asi + loose graphics (needs an ASI loader); rebirth: REbirth mod folder mod_korean_hd/')
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
        'korean_rooms.bin': build_rooms(),
        'korean_files.bin': krf2,
        'korean_exe.bin': serialize(allocation, sites, writes, ddraw_sites(ddraw, sites)),
        'korean_rebirth.bin': build_rebirth(ddraw, load_json(ROOT / 'translation/rebirth-glyphs.json'), load_json(ROOT / 'translation/rebirth-ui.json')),
    }
    graphics = patched_graphics(originals, krf2)
    if args.mode == 'rebirth':  # REbirth overlays graphics from inside the mod folder
        files = {'korean_hd.dll': module_dll('rebirth').read_bytes(), 'manifest.txt': MANIFEST.encode(),
                 'description.txt': f'Korean text and HD fonts/documents, version {VERSION}.\n'.encode(), **files, **graphics}
        files = {f'mod_korean_hd/{n}': d for n, d in files.items()}
    else:  # ASI: data beside the exe, graphics loose over the originals (backed up first)
        files = {**{f'mod_korean_hd/{n}': d for n, d in files.items()}, 'RE3.KoreanHD.asi': module_dll('asi').read_bytes(), **graphics}
    backup = WORK / f'backups/setup-{time.strftime("%Y%m%d-%H%M%S")}'
    install_files(game, files, backup)
    (WORK / f'{args.mode}-installed.txt').write_text(''.join(f'{n}\n' for n in sorted(files)))  # make_release packs these
    print(f'installed: {len(files)} files')
    if args.no_hd:
        print('HD textures skipped (--no-hd)')
    elif not (game / 'hires').is_dir():
        print('HD textures skipped: no hires/ folder (install the Mulderland Enhancement Pack first)')
    else:
        subprocess.run([sys.executable, str(ROOT / 'tools/install_hd.py'), '--game', str(game)], check=True)
    if backup.exists():
        print(f'backup of replaced files: {backup.relative_to(ROOT)}')
    if args.mode == 'asi':
        print('done. Launch the game normally (Ultimate ASI Loader loads RE3.KoreanHD.asi).')
    else:
        print('done. Start the game with the -dev_korean_hd flag, or pick "Korean HD" in the REbirth mod list.')


if __name__ == '__main__':
    main()
