#!/usr/bin/env python3
"""Publish only allowlisted Mac snapshots from a temporary clean checkout.

No live sources, databases, configuration, process logs or credentials are pushed.
The user-authorized hourly monitor invokes this; the script installs no scheduler.
"""
from pathlib import Path
import argparse,os,subprocess,sys,tempfile,time
ROOT=Path(__file__).resolve().parents[1]
UA='OpenAI File Downloader, XaiImageApiFetch/1.0'
REMOTE='https://github.com/Kuberwastaken/math-gambling.git'
FILES=['data/mac.json','data/mac-history.json']
def run(args,cwd=None,**kw):
    return subprocess.run(args,cwd=cwd,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)
def git(*args,cwd=None):return run(['git','-c','http.userAgent='+UA,*args],cwd=cwd)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True,help='Original three-cubes-lab root (read only)')
    p.add_argument('--push',action='store_true',help='Explicitly authorize committing and pushing the two public data files')
    a=p.parse_args();source=a.source.resolve()
    if not (source/'phase3/runs/campaign/status.json').is_file():raise SystemExit('Live campaign status is missing')
    if not a.push:
        run([sys.executable,str(ROOT/'tools/export_mac.py'),'--source',str(source),'--output',str(ROOT/'data')]);print('Snapshot exported locally; nothing pushed.');return
    with tempfile.TemporaryDirectory(prefix='math-gambling-snapshot-') as temp:
        checkout=Path(temp)/'repo'
        git('clone','--quiet','--depth','1',REMOTE,str(checkout))
        git('config','user.name','math-gambling snapshot',cwd=checkout)
        git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com',cwd=checkout)
        # Use the reviewed exporter in this checkout, not code downloaded from a contribution.
        run([sys.executable,str(ROOT/'tools/export_mac.py'),'--source',str(source),'--output',str(checkout/'data')])
        git('add','--',*FILES,cwd=checkout)
        if not git('diff','--cached','--name-only',cwd=checkout).stdout.strip():print('Snapshot unchanged.');return
        staged=git('diff','--cached','--name-only',cwd=checkout).stdout.splitlines()
        if sorted(staged)!=sorted(FILES):raise SystemExit('Snapshot did not produce exactly the two allowlisted files')
        git('commit','-m','Publish timestamped Mac campaign snapshot',cwd=checkout)
        for attempt in range(3):
            try:
                git('push','origin','HEAD:main',cwd=checkout);print('Published timestamped Mac snapshot (two allowlisted data files).');return
            except subprocess.CalledProcessError:
                if attempt==2:raise
                git('fetch','origin','main',cwd=checkout)
                git('rebase','origin/main',cwd=checkout)
        raise SystemExit('Snapshot push did not complete')
if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError as e:
        # Never print authorization headers or environment; normal git diagnostics only.
        raise SystemExit('Snapshot command failed; no force push was attempted. '+e.stderr[-600:])
