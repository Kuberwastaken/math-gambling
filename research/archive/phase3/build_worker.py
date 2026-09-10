#!/usr/bin/env python3
"""Build phase3 only, using frozen phase1 PARI headers/library read-only."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
LAB=ROOT.parent
HEADERS=LAB.parent.parent/'work/pari-include'

def main():
    out=ROOT/'bin';out.mkdir(exist_ok=True)
    if not (HEADERS/'pari/pari.h').exists():
        raise SystemExit('Prepared PARI headers missing; no production rebuild was attempted.')
    link=out/'libpari.dylib'
    if not link.exists():link.symlink_to('../../bin/libpari.dylib')
    if link.resolve()!=(LAB/'bin/libpari.dylib').resolve():
        raise SystemExit('Unexpected phase3 PARI link')
    subprocess.run(['clang','-O3','-Wall','-Wextra','-I',str(HEADERS),str(ROOT/'offset_worker.c'),
                    '-L',str(LAB/'bin'),'-lpari','-o',str(out/'offset_worker')],check=True)

if __name__=='__main__':main()
