import copy
from pathlib import Path
import sys
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
from contribution_credit import provisional_credit,input_count
from negative_audit import selected
from search_core import CONTEXTS, make_task, task_id, run_task

class CreditTests(unittest.TestCase):
    def record(self,number=1,user='Alice'):
        plan={'salt':'00'*32,'one_in':20}
        results=[make_task('c00',i*128) for i in range(256)]
        checked=[task_id(t) for t in results if selected(plan,'body',task_id(t))]
        claims=[{'task':t,'digest':'a'*64,'received_at':f'2026-09-11T00:00:{number:02d}Z'} for t in results if task_id(t) not in checked]
        return {'negative_audit':plan,'source':{'id':str(number),'number':number,'submitter':user,'kind':'issue'},
                'contributor':{'name':user,'github':user},'body_sha256':'body','complete':True,'status':'sampled',
                'accepted_tasks':checked,'duplicate_tasks':[],'rejected_tasks':[],'unreplayed_tasks':claims}
    def test_inputs_from_bounds_match_exact_engine_including_partial_rows_blocks(self):
        for c in CONTEXTS:
            for row,block in [(0,0),((int(c['totalRows'])-1)//128*128,c['blocks']-1)]:
                task=make_task(c['id'],row,block)
                self.assertEqual(input_count(task),run_task(task)['counters']['generators'])
    def test_full_passed_bank_credit_is_unique_across_banks_and_users(self):
        first=self.record();second=self.record(2,'Bob')
        people=provisional_credit([second,first,copy.deepcopy(first)],set())
        self.assertEqual(set(people),{'alice'})
        self.assertEqual(people['alice']['tasks'],len(first['unreplayed_tasks']))
        self.assertEqual(people['alice']['inputs'],sum(input_count(c['task']) for c in first['unreplayed_tasks']))
    def test_verification_replaces_provisional_credit(self):
        row=self.record();identifier=task_id(row['unreplayed_tasks'][0]['task'])
        before=provisional_credit([row],set())['alice']['inputs']
        after=provisional_credit([row],{identifier})['alice']['inputs']
        self.assertEqual(before-after,input_count(row['unreplayed_tasks'][0]['task']))
    def test_no_sample_partial_rejection_and_operational_error_do_not_qualify(self):
        for changes in [{'accepted_tasks':[]}, {'complete':False}, {'rejected_tasks':[{}]}, {'operational_error':'timeout'}, {'status':'rejected'}]:
            row=self.record();row.update(changes)
            self.assertEqual(provisional_credit([row],set()),{})
    def test_any_failed_account_audit_revokes_all_provisional_credit(self):
        good=self.record();bad=self.record(2,'ALICE');bad['audit_sample_failed']=True
        self.assertEqual(provisional_credit([good,bad],set()),{})
    def test_pending_earlier_claim_is_not_stealable(self):
        early=self.record();early['complete']=False
        self.assertEqual(provisional_credit([early,self.record(2,'Bob')],set()),{})

if __name__=='__main__':unittest.main()
