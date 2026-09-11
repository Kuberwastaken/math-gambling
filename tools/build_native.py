#!/usr/bin/env python3
"""Build the pinned Rust kernel locally or its WebAssembly artifact."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wasm',action='store_true')
    args=parser.parse_args()
    env={**os.environ,'CARGO_HTTP_USER_AGENT':'OpenAI File Downloader, XaiImageApiFetch/1.0'}
    command=['cargo','build','--locked','--release','--manifest-path',str(ROOT/'native/Cargo.toml')]
    if args.wasm:command+=['--target','wasm32-unknown-unknown','--lib']
    subprocess.run(command,check=True,env=env)
    if args.wasm:
        source=ROOT/'native/target/wasm32-unknown-unknown/release/math_gambling_kernel.wasm'
        dest=ROOT/'web/assets/kernel/math_gambling_kernel.wasm'
    else:
        name='math-gambling-kernel'+('.exe' if os.name=='nt' else '')
        source=ROOT/'native/target/release'/name
        dest=ROOT/'tools/bin'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)
    print('Built '+str(dest.relative_to(ROOT)))

if __name__=='__main__':main()
