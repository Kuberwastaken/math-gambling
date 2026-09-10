#!/usr/bin/env python3
"""Build only the isolated shell experiment using existing local PARI files."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
LAB=ROOT.parent.parent
HEADERS=LAB.parent.parent/'work/pari-include'

def main():
    if not (HEADERS/'pari/pari.h').exists() or not (LAB/'bin/libpari.dylib').exists():
        raise SystemExit('Prepared PARI headers/library missing; this script does not rebuild production.')
    link=ROOT/'libpari.dylib'
    if not link.exists():
        link.symlink_to('../../bin/libpari.dylib')
    if link.resolve()!=(LAB/'bin/libpari.dylib').resolve():
        raise SystemExit('Experimental library link points somewhere unexpected.')
    subprocess.run(['clang','-O3','-Wall','-Wextra','-I',str(HEADERS),
                    str(ROOT/'shell_worker.c'),'-L',str(LAB/'bin'),'-lpari',
                    '-o',str(ROOT/'shell_worker')],check=True)

if __name__=='__main__':main()
