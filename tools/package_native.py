#!/usr/bin/env python3
"""Add the locally tested native binary to the portable archive for this host."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from native_kernel import binary_path
ROOT=Path(__file__).resolve().parents[1]
def main():
    version=json.loads((ROOT/'data/runner-release.json').read_text())['version']
    system={'Linux':'linux','Darwin':'macos','Windows':'windows'}[platform.system()]
    arch={'AMD64':'x86_64','x86_64':'x86_64','arm64':'arm64','aarch64':'arm64'}[platform.machine()]
    out=ROOT/'native-assets';out.mkdir(exist_ok=True)
    dest=out/f'math-gambling-runner-v{version}-{system}-{arch}.zip'
    shutil.copyfile(ROOT/'dist/math-gambling/downloads/math-gambling-runner.zip',dest)
    with zipfile.ZipFile(dest,'a',zipfile.ZIP_DEFLATED) as archive:
        info=zipfile.ZipInfo('math-gambling/tools/bin/'+binary_path().name,date_time=(1980,1,1,0,0,0))
        info.create_system=3;info.external_attr=0o100755<<16;info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,binary_path().read_bytes())
    # Smoke-test the actual assembled archive, not merely the source checkout.
    with tempfile.TemporaryDirectory(prefix='mg-native-release-') as tmp:
        tmp=Path(tmp)
        with zipfile.ZipFile(dest) as archive: archive.extractall(tmp)
        root=tmp/'math-gambling'
        executable=root/'tools/bin'/binary_path().name
        if os.name!='nt':executable.chmod(0o755)
        if executable.read_bytes()!=binary_path().read_bytes():raise RuntimeError('Native archive differs from tested binary')
        subprocess.run([sys.executable,'tools/runner.py','--kernel','rust','--offline','--name','Release fixture',
                        '--github','release-fixture','--workers','1','--minutes','1','--max-tasks','2','--output',str(tmp/'results')],cwd=root,check=True,timeout=60)
    print(dest)
if __name__=='__main__':main()
