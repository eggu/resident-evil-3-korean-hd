"""Classic REbirth ddraw.dll builds the tools know, keyed by SHA256.

Mirrors rebirth_profiles[] in src/korean_hd.c; a new REbirth build needs a row in both.
"""
import hashlib

PROFILES = {
    '8ef09511a5612574b240e602b19bd1692a2c33bd0c1a5fab1348738c70c64423': {
        'name': '1.0.3',
        'store_message': 0x100ab490,            # fastcall message store (ecx text, edx id)
        'table_globals': (0x70190c, 0x701910),  # exe table bases REbirth keeps in its own globals
    },
}


def profile(ddraw_bytes):
    digest = hashlib.sha256(ddraw_bytes).hexdigest()
    if digest not in PROFILES:
        known = ', '.join(p['name'] for p in PROFILES.values())
        raise SystemExit(f'Unsupported Classic REbirth ddraw.dll (sha256 {digest[:16]}...); supported: {known}')
    return PROFILES[digest]
