import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import ingest as ig
import aggregate as ag
from negative_audit import AuditPolicy,selected
from search_core import make_task,run_task,task_id
from test_cluster import bank,source

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
        self.results=[run_task(make_task('c00',i*128)) for i in range(40)]
        self.policy=AuditPolicy(self.data,20);self.policy.eligible={'trusted'}
        self.calls=[]
    def tearDown(self):self.tmp.cleanup()
    def replay(self,task):self.calls.append(task);return run_task(task),1.0
    def submit(self,receipt,number=1,budget=None):
        return ig.process_receipt(receipt,source(number,'trusted'),self.data,budget or ig.Budget(),replay=self.replay,audit_policy=self.policy)
    def test_unreplayed_never_enters_credit_coverage_or_learning(self):
        receipt=bank(self.results)
        record=self.submit(receipt)
        self.assertEqual(record['status'],'sampled')
        self.assertGreater(len(record['unreplayed_tasks']),0)
        self.assertEqual(len(self.calls)+len(record['unreplayed_tasks']),40)
        report=ag.aggregate(self.data)
        self.assertEqual(report['totals']['verified_unique_tasks'],len(self.calls))
        self.assertEqual(report['totals']['unreplayed_claims'],len(record['unreplayed_tasks']))
        self.assertEqual(sum(int(x['verified_tasks']) for x in report['contributors']),len(self.calls))
        self.assertEqual(self.submit(receipt),record)
        # A later independent full replay is eligible for exact credit; an
        # earlier unverified claim did not reserve or certify this task.
        claim=record['unreplayed_tasks'][0]
        item=next(r for r in self.results if r['task']==claim['task'])
        self.policy.eligible.clear()
        full=self.submit(bank([item]),number=2)
        self.assertEqual(full['status'],'accepted')
        self.assertEqual(ag.aggregate(self.data)['totals']['verified_unique_tasks'],len(self.calls))
    def test_contribution_backfill_and_revocation_leave_verified_policy_unchanged(self):
        with patch('negative_audit.secrets.token_hex', return_value='00'*32):
            record=self.submit(bank(self.results))
        self.assertGreater(len(record['accepted_tasks']), 0)
        report=ag.aggregate(self.data)
        self.assertEqual(report['totals']['contributed_tasks'],40)
        self.assertEqual(int(report['contributors'][0]['contributed_computations']),sum(r['counters']['generators'] for r in self.results))
        verified=report['totals']['verified_computations']
        policy=(self.data/'strategy.json').read_bytes()
        bad=bank([run_task(make_task('c00',128*99))]);bad['tasks'][0]['digest']='0'*64
        with patch('negative_audit.selected',return_value=True):self.submit(bad,number=3)
        after=ag.aggregate(self.data)
        self.assertEqual(after['totals']['provisional_tasks'],0)
        self.assertEqual(after['totals']['verified_computations'],verified)
        self.assertEqual(after['totals']['contributed_computations'],verified)
        self.assertEqual((self.data/'strategy.json').read_bytes(),policy)

    def test_challenge_persisted_before_replay_and_fixed_on_resume(self):
        receipt=bank(self.results);first=self.submit(receipt,budget=ig.Budget(count=0))
        self.assertIn('negative_audit',first)
        with patch('negative_audit.secrets.token_hex',side_effect=AssertionError('must not reroll')):
            resumed=self.submit(receipt)
        self.assertEqual(first['negative_audit'],resumed['negative_audit'])
        for task in self.calls:self.assertTrue(selected(resumed['negative_audit'],resumed['body_sha256'],task_id(task)))
    def test_failed_sample_quarantines_account_without_promoting_others(self):
        receipt=bank(self.results)
        for item in receipt['tasks']:item['digest']='0'*64
        # Force selection to exercise failure, not random coverage of a fixture.
        with patch('negative_audit.selected',return_value=True):record=self.submit(receipt)
        self.assertTrue(record['audit_sample_failed'])
        self.assertNotIn('trusted',self.policy.eligible)
        self.assertNotIn('trusted',AuditPolicy(self.data,20).eligible)
        self.assertEqual(ag.aggregate(self.data)['totals']['verified_unique_tasks'],0)
    def test_new_account_full_replay_and_positive_tasks_never_sampled_out(self):
        self.policy.eligible.clear();receipt=bank(self.results[:2])
        record=self.submit(receipt);self.assertNotIn('negative_audit',record);self.assertEqual(len(self.calls),2)
        self.policy.eligible.add('trusted')
        receipt=bank(self.results[2:3]);receipt['tasks'][0]['hits']=[{'xyz':['1','2','3']}]
        with patch('negative_audit.selected',return_value=False):record=self.submit(receipt,number=2)
        self.assertEqual(len(self.calls),3)
        self.assertEqual(len(record.get('unreplayed_tasks',[])),0)
        self.assertTrue(record['audit_sample_failed'])
    def test_copy_of_retained_digest_cannot_steal_later_verified_credit(self):
        receipt=bank(self.results[:1])
        with patch('negative_audit.selected',return_value=False):first=self.submit(receipt)
        self.assertEqual(first['accepted_tasks'],[])
        # A new account gets full replay, but not ownership of the older claim.
        policy=AuditPolicy(self.data,20)
        copied=ig.process_receipt(receipt,source(2,'copier'),self.data,ig.Budget(),replay=self.replay,audit_policy=policy)
        self.assertEqual(copied['accepted_tasks'],[])
        self.assertEqual(len(copied['duplicate_tasks']),1)
        report=ag.aggregate(self.data)
        self.assertEqual(report['contributors'][0]['github'],'trusted')
        self.assertEqual(report['totals']['unreplayed_claims'],0)
        self.assertEqual(len(report['contributors']),1)

    def test_quarantine_also_disables_preplanned_pending_banks(self):
        receipt=bank(self.results)
        with patch('negative_audit.selected',return_value=True):
            pending=self.submit(receipt,budget=ig.Budget(count=0))
        self.assertFalse(pending['complete'])
        self.policy.eligible.clear()
        with patch('negative_audit.selected',return_value=False):
            complete=self.submit(receipt)
        self.assertEqual(len(self.calls),40)
        self.assertEqual(complete['unreplayed_tasks'],[])
        self.assertEqual(pending['negative_audit'],complete['negative_audit'])

    def test_sampling_decision_rate_and_bounds(self):
        plan={'one_in':20,'salt':'00'*32}
        count=sum(selected(plan,'body',str(i)) for i in range(10000))
        self.assertTrue(400<count<600,count)
        with self.assertRaises(ValueError):AuditPolicy(self.data,0)

if __name__=='__main__':unittest.main()
