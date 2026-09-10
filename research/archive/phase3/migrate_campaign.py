#!/usr/bin/env python3
"""Copy a stopped, fully audited phase2 ledger into a new source epoch.

Coverage/job records are immutable. Execution timing is re-learned for the new
binary; the old source identity and timing model are retained as evidence.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import time

import campaign as c


def migrate(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or (destination/'campaign.sqlite3').exists():
        raise ValueError('Destination must be a new campaign directory')
    if not (source/'STOP').exists():
        raise ValueError('Source must have its STOP marker before migration')
    destination.mkdir(parents=True,exist_ok=True)
    with (source/'writer.lock').open('a+') as old_lock, (destination/'writer.lock').open('a+') as new_lock:
        fcntl.flock(old_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.flock(new_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if c.recover_journals(source):
            raise ValueError('Source contains a recovered discovery; migration unnecessary')
        old=sqlite3.connect(f"file:{source/'campaign.sqlite3'}?mode=ro",uri=True)
        old.row_factory=sqlite3.Row
        old.execute('BEGIN')
        temporary=destination/'migration.sqlite3.tmp'
        if temporary.exists():
            raise ValueError('Inspect an existing migration temporary file before retrying')
        new=None
        try:
            before=c.audit(old)
            if before['unfinished_tiles']:
                raise ValueError('Migration requires zero unfinished tiles')
            if old.execute('SELECT count(*) FROM solutions').fetchone()[0]:
                raise ValueError('Source already has a solution')
            old_config=json.loads(old.execute("SELECT value FROM meta WHERE key='config'").fetchone()[0])
            if old_config['contexts']!=c.contexts() or old_config['permutation_seed']!=1142:
                raise ValueError('Geometry/seed differs; this migration cannot certify coverage')
            old_root=source.parent.parent
            actual_old={name:c.digest(old_root/name) for name in old_config['sources']}
            if actual_old != old_config['sources']:
                raise ValueError('Old source files do not match the completed ledger identity')
            maximum=old.execute('SELECT coalesce(max(id),0) FROM jobs').fetchone()[0]
            cursors=[dict(r) for r in old.execute('SELECT key,spec,cursor FROM contexts ORDER BY key')]
            totals=[dict(r) for r in old.execute('SELECT * FROM totals ORDER BY key')]
            sources=c.source_identity()
            certificate=dict(version=1,created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                parent_directory=str(source),epoch_start_job=maximum,
                historical_jobs_sha256=c.job_digest(old,maximum),prior_config=old_config,
                prior_audit=before,cursors=cursors,totals=totals,new_sources=sources,
                reason='Same exact input mapping; optimized execution and durable discovery journals. New timing epoch.')
            new=sqlite3.connect(temporary)
            old.backup(new)
            new.close()
            new=c.connect(temporary)
            with new:
                # Archive the exact prior metadata before resetting only runtime learning.
                metadata={r['key']:json.loads(r['value']) for r in new.execute('SELECT * FROM meta')}
                new.execute("INSERT INTO meta VALUES('prior_epoch_metadata',?)",(c.canonical(metadata),))
                new.execute("DELETE FROM meta WHERE key IN ('model','learning_gate')")
                new.execute("INSERT INTO meta VALUES('epoch_start',?)",(str(maximum),))
                new.execute("INSERT INTO meta VALUES('migration',?)",(c.canonical(certificate),))
                config=dict(schema=c.SCHEMA,contexts=c.contexts(),sources=sources,permutation_seed=1142,
                    coverage='finite generator indices and quotient bands; not all curves or a height box')
                new.execute("UPDATE meta SET value=? WHERE key='config'",(c.canonical(config),))
                new.execute('DELETE FROM policies')
                new.execute('DELETE FROM allocations')
                new.execute('UPDATE contexts SET elapsed=0')
                c.event(new,'source_epoch_migrated',certificate)
            if ([dict(r) for r in new.execute('SELECT key,spec,cursor FROM contexts ORDER BY key')]!=cursors
                    or [dict(r) for r in new.execute('SELECT * FROM totals ORDER BY key')]!=totals):
                raise ValueError('Migration changed coverage cursors or totals')
            after=c.audit(new)
            new.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            new.close();new=None
            with temporary.open('rb') as inp:os.fsync(inp.fileno())
            os.replace(temporary,destination/'campaign.sqlite3')
            c.sync_directory(destination)
            certificate['post_migration_audit']=after
            c.atomic_json(destination/'migration-certificate.json',certificate)
            return dict(before=before,after=after,directory=str(destination),historical_jobs_sha256=certificate['historical_jobs_sha256'])
        finally:
            if new is not None:new.close()
            old.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=c.ROOT.parent/'phase2/runs/campaign')
    p.add_argument('--destination',type=Path,default=c.ROOT/'runs/campaign')
    a=p.parse_args()
    print(json.dumps(migrate(a.source,a.destination),indent=2))
