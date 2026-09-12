#!/usr/bin/env python3
"""Label project conversations without treating compute banks as support issues."""
import argparse
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO='Kuberwastaken/math-gambling'
LABEL='project-issue'
UA='OpenAI File Downloader, XaiImageApiFetch/1.0'


def api(method,path,body=None):
    request=Request('https://api.github.com/repos/'+REPO+'/'+path,method=method,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],
                             'User-Agent':UA,'Accept':'application/vnd.github+json',
                             'Content-Type':'application/json'})
    with urlopen(request,timeout=30) as response:
        raw=response.read()
        return json.loads(raw) if raw else None


def is_project_issue(issue):
    return 'pull_request' not in issue and not issue.get('title','').lower().startswith(('[bank]','[compute]'))


def classify(number,dry_run=False):
    # Fetch current state: an older queued edit event must not restore stale labels.
    issue=api('GET',f'issues/{number}')
    if 'pull_request' in issue:return
    wanted=is_project_issue(issue)
    present=any(label['name']==LABEL for label in issue['labels'])
    if wanted==present:return
    print(f'#{number}: {"add" if wanted else "remove"} {LABEL}',flush=True)
    if not dry_run:
        if wanted:api('POST',f'issues/{number}/labels',{'labels':[LABEL]})
        else:
            try:api('DELETE',f'issues/{number}/labels/{LABEL}')
            except HTTPError as exc:
                if exc.code!=404:raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issue',type=int)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if args.issue is not None and args.issue<1:parser.error('issue must be positive')
    if not args.dry_run:
        try:api('GET','labels/'+LABEL)
        except HTTPError as exc:
            if exc.code!=404:raise
            try:api('POST','labels',{'name':LABEL,'color':'5319e7','description':'Bugs, questions and project requests; excludes compute bank submissions.'})
            except HTTPError as race:
                if race.code!=422:raise
                api('GET','labels/'+LABEL)
    if args.issue is not None:
        classify(args.issue,args.dry_run);return
    # Manual reconciliation scans open issues only. Most banks need no writes.
    page=1;scanned=0
    while True:
        issues=api('GET',f'issues?state=open&per_page=100&page={page}&sort=created&direction=asc')
        for issue in issues:
            if 'pull_request' in issue:continue
            scanned+=1
            if is_project_issue(issue) or any(label['name']==LABEL for label in issue['labels']):
                classify(issue['number'],args.dry_run)
        if len(issues)<100:break
        page+=1
    print(f'Checked {scanned} open issues.',flush=True)


if __name__=='__main__':main()
