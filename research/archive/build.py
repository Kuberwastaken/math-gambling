#!/usr/bin/env python3
"""Offline source build on this Apple Silicon Mac (Xcode command-line tools needed)."""
from pathlib import Path
import hashlib
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
BUILD=ROOT.parent.parent/'work'/'pari-rebuild'
ARCHIVE=ROOT/'vendor/pari-2.17.4.tar.gz'

def run(*args,cwd=None):subprocess.run(list(map(str,args)),cwd=cwd,check=True)

def main():
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()=='02651d99c391007d384b3fadbc20abc6916b77036f9e496c99e9ce8688ca4b53'
    BUILD.mkdir(parents=True,exist_ok=True)
    src=BUILD/'pari-2.17.4'
    if not src.exists():run('tar','-xzf',ARCHIVE,'-C',BUILD)
    run('./Configure','--without-gmp','--without-readline','--graphic=none',f'--prefix={BUILD / "install"}',cwd=src)
    run('make','-j2','gp',cwd=src)
    lib=next(src.glob('Odarwin-*/libpari.dylib'))
    out=ROOT/'bin';out.mkdir(exist_ok=True)
    shutil.copy2(src/'gp',out/'gp');shutil.copy2(lib,out/'libpari.dylib')
    run('install_name_tool','-id','@loader_path/libpari.dylib',out/'libpari.dylib')
    links=subprocess.check_output(['otool','-L',str(out/'gp')],text=True)
    for line in links.splitlines()[1:]:
        old=line.strip().split(' (',1)[0]
        if 'libpari' in old:run('install_name_tool','-change',old,'@executable_path/libpari.dylib',out/'gp')
    include=BUILD/'include'/'pari';include.mkdir(parents=True,exist_ok=True)
    for folder in [src/'src/headers',lib.parent]:
        for h in folder.glob('*.h'):shutil.copy2(h,include/h.name)
    names=['native_search','campaign_worker','plane_worker']
    for name in names:
        run('clang','-O3','-Wall','-Wextra','-I',include.parent,ROOT/(name+'.c'),'-L',out,'-lpari','-o',out/name)
    for path in [out/'gp',out/'libpari.dylib',*[out/name for name in names]]:run('codesign','--force','--sign','-',path)
    print('Build complete. Run python3 validate.py to verify.')

if __name__=='__main__':main()
