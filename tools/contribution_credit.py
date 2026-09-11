"""Provisional participation credit, deliberately separate from exact coverage."""
from collections import Counter
from negative_audit import selected
from search_core import BLOCK_SIZE, ROWS_PER_TASK, CONTEXT_BY_ID, validate_task, task_id


def input_count(task):
    task = validate_task(task)
    context = CONTEXT_BY_ID[task['context']]
    rows = min(ROWS_PER_TASK, int(context['totalRows']) - int(task['row']))
    first = context['tlo'] + BLOCK_SIZE * task['block']
    return rows * min(BLOCK_SIZE, context['thi'] - first + 1)


def provisional_credit(receipts, verified_ids):
    """First retained claim owns a task provisionally, at most once worldwide.

    Only complete banks with a matched random challenge qualify. No-challenge
    banks wait for verification. Any failed sample revokes the account's entire
    provisional balance; its exact replays remain untouched.
    """
    failed = {r.get('source', {}).get('submitter', '').casefold() for r in receipts if r.get('audit_sample_failed')}
    first = {}
    for record in receipts:
        source = record.get('source', {})
        account = source.get('submitter', '').casefold()
        if source.get('kind') != 'issue' or not account or account in failed:
            continue
        plan = record.get('negative_audit')
        checked = set(record.get('accepted_tasks', [])) | set(record.get('duplicate_tasks', []))
        passed = (plan and record.get('complete') is True and record.get('status') == 'sampled'
                  and not record.get('rejected_tasks') and not record.get('operational_error')
                  and any(selected(plan, record['body_sha256'], tid) for tid in checked))
        for claim in record.get('unreplayed_tasks', []):
            task = validate_task(claim['task']); identifier = task_id(task)
            if identifier in verified_ids: continue
            order = (claim.get('received_at', record.get('processed_at', '')), source.get('number', 0), source['id'])
            if identifier not in first or order < first[identifier][0]:
                first[identifier] = (order, account, record, task, bool(passed))
    people = {}
    for order, account, record, task, passed in first.values():
        if not passed: continue
        entry = people.setdefault(account, {'tasks':0, 'inputs':0, 'record':record, 'profile_at':order[0]})
        entry['tasks'] += 1; entry['inputs'] += input_count(task)
        if order[0] > entry['profile_at']:
            entry.update(record=record, profile_at=order[0])
    return people
