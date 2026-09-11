"""Post-submission random audits. Unreplayed claims NEVER become verified work."""
import hashlib
import secrets
from collections import Counter
from pathlib import Path
import json
from search_core import task_id

class AuditPolicy:
    def __init__(self, data, one_in=20):
        if type(one_in) is not int or not 1 <= one_in <= 100:
            raise ValueError('audit denominator must be 1..100')
        self.one_in=one_in
        counts=Counter()
        for path in (Path(data)/'receipts/tasks').glob('*/*.json'):
            item=json.loads(path.read_text())
            if item.get('schema')=='math-gambling-verified-task-v1' and item.get('source',{}).get('kind')=='issue':
                counts[item['source'].get('submitter','').casefold()]+=1
        quarantined=set()
        self.claims={}
        for path in (Path(data)/'receipts/issues').glob('*/*.json'):
            item=json.loads(path.read_text())
            for claim in item.get('unreplayed_tasks', []):
                self.remember(claim,item['source'],item['contributor'],item.get('processed_at',''))
            if item.get('audit_sample_failed'):
                quarantined.add(item.get('source',{}).get('submitter','').casefold())
        self.eligible={name for name,n in counts.items() if name and n>=256 and name not in quarantined}

    def remember(self, claim, source, contributor, fallback_stamp=''):
        key=(task_id(claim['task']),claim['digest'])
        order=(claim.get('received_at',fallback_stamp),source.get('number',0),source['id'])
        prior=self.claims.get(key)
        if prior is None or order<prior['order']:
            self.claims[key]={'order':order,'source':source,'contributor':contributor}

    def attribution(self, identifier, digest, source, contributor):
        prior=self.claims.get((identifier,digest))
        return (prior['source'],prior['contributor']) if prior else (source,contributor)

    def plan(self, receipt, source):
        if (self.one_in==1 or source.get('kind')!='issue' or source.get('submitter','').casefold() not in self.eligible
                or not isinstance(receipt,dict) or receipt.get('schema')!='math-gambling-bank-v1'):
            return None
        return {'schema':'math-gambling-negative-audit-v1','one_in':self.one_in,
                'salt':secrets.token_hex(32),'probation_verified_tasks':256,
                'unreplayed_is_verified':False}


def selected(plan, body_hash, identifier):
    if plan is None:return True
    # Draw only after this immutable body was received; do not give clients a
    # predictable task-ID partition they can avoid. Persist before any replay.
    digest=hashlib.sha256((plan['salt']+':'+body_hash+':'+identifier).encode()).digest()
    return int.from_bytes(digest,'big') < (1<<256)//plan['one_in']
