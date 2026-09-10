import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from publish_snapshot_vps import validate_pair, ensure_newer, FILES
from export_mac import export


class PublishSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        campaign=root/'lab/phase3/runs/campaign'
        campaign.mkdir(parents=True)
        (campaign/'status.json').write_text(json.dumps({'state':'running','updated_utc':'2026-09-10T10:00:00Z',
            'totals':{'curve_checks':12345678901234567890},'jobs':{'complete':1,'running':1},'solutions':[]}))
        self.pair=dict(zip(FILES,export(root/'lab',root/'public')))

    def test_actual_export_validates(self):
        self.assertEqual(validate_pair(self.pair)[0]['totals']['curve_checks'],'12345678901234567890')

    def test_arbitrary_paths_rejected(self):
        with self.assertRaises(ValueError): validate_pair({**self.pair,'../../private':{}})

    def test_modified_or_mismatched_snapshot_rejected(self):
        for name,key,value in [(FILES[0],'snapshot_id','0'*64),(FILES[1],'snapshot_id','0'*64),
                               (FILES[0],'pid',777),(FILES[1],'samples',[])]:
            pair=copy.deepcopy(self.pair); pair[name][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): validate_pair(pair)

    def test_stale_time_and_regression_rejected(self):
        new=self.pair[FILES[0]]
        ensure_newer(new,new)
        for change in ({'updated_utc':'2026-09-09T10:00:00Z'}, {'totals':{'curve_checks':'1'}}):
            with self.assertRaises(ValueError): ensure_newer({**new,**change},new)
