import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from public_reports import project_cluster, BYTE_LIMIT


class PublicReportsTests(unittest.TestCase):
    def test_large_history_is_bounded_without_changing_evidence(self):
        entry={'weights':{f'c{i:02}':1/81 for i in range(81)}}
        report={'totals':{'verified_unique_tasks':1000000},'contributors':[{'name':'A'}],
                'banks':[{'id':'bank'}], 'calibration_history':[{**entry,'epoch':i+1} for i in range(15625)]}
        raw=project_cluster(report); result=json.loads(raw)
        self.assertLess(len(raw),BYTE_LIMIT)
        self.assertEqual(len(result['calibration_history']),128)
        self.assertEqual(result['calibration_history'][0]['epoch'],1)
        self.assertEqual(result['calibration_history'][-1]['epoch'],15625)
        for key in ('totals','contributors','banks'):self.assertEqual(result[key],report[key])
        self.assertEqual(len(report['calibration_history']),15625)
    def test_small_and_empty_history(self):
        for n in (0,1,100):
            h=[{'epoch':i} for i in range(n)]
            self.assertEqual(json.loads(project_cluster({'calibration_history':h}))['calibration_history'],h)
