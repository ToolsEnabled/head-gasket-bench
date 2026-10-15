#!/usr/bin/env python3
"""Codex stdio entry; run records must survive plugin-cache replacement."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'env'))


def serve(env=None):
    env = os.environ if env is None else env
    value = env.get('HEADGASKET_RUN_DIR', '')
    if not value or not Path(value).is_absolute() or any(ord(c) < 32 for c in value):
        raise ValueError('Set HEADGASKET_RUN_DIR to a new absolute private run folder outside the plugin installation.')
    run = Path(value).resolve()
    if run == ROOT or ROOT in run.parents or run in ROOT.parents:
        raise ValueError('HEADGASKET_RUN_DIR overlaps the plugin installation; choose an external run folder.')
    variant = env.get('HEADGASKET_VARIANT', 'V1')
    # The canonical CLI validates the variant, interpreter, ownership, writer
    # exclusion and record custody. Do not bypass its source-bound loader.
    from headgasket.cli import main
    return main(['serve', '--variant', variant, '--out', value])


if __name__ == '__main__':
    try:
        sys.exit(serve())
    except (ValueError, OSError) as error:
        print(f'Head Gasket Bench Codex launch refused: {error}', file=sys.stderr)
        sys.exit(1)
