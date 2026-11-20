"""Apply WebStreamrMBG source patches at build time.

Usage: python3 scripts/webstreamrmbg-patch.py <source-checkout>
"""
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
patch_root = Path(__file__).resolve().parent.parent / 'patches' / 'webstreamrmbg'

for subdir in ('source', 'utils', 'extractor'):
    for patch in sorted((patch_root / subdir).glob('*.ts')):
        target = root / 'src' / subdir / patch.name
        if not target.is_file():
            raise SystemExit(f'missing patch target: {target}')
        shutil.copyfile(patch, target)
        print(f'patched {subdir}/{target.name}')
