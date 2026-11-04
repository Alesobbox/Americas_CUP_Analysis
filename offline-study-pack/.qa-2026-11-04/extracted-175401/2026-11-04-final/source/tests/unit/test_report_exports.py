"""Canonical report serialization retains unavailable values and source evidence."""
import csv
import io
import json
import tempfile
import unittest
from scripts.build_report_exports import export_report_files
class ReportExportTests(unittest.TestCase):
    def detail(self):
        return {'race': {'id':'race','date':'2026-09-22'},'method_version':'historical-2',
          'definitions': {'sog_mean_kt': {'window':'active race','denominator':'valid seconds','source':'recorded SOG'}},
          'boats':[{'id':'boat','team_code':'GBR B','classification':'RET','official_rank':None,'official_elapsed_s':None,'source_conflicts':['start state conflict'],
          'metrics':{'sog_mean_kt':{'value':None,'unit':'kt','quality':'unavailable','coverage_s':None,'reason':'no valid racing window'}},
          'performance':{'method_version':'performance-1','dimensions':[{'id':'upwind_vmg','value':18.75,'unit':'kt','index':109.9671,'peer_mean':17.31,'peer_count':2,'quality':'derived','coverage_s':120,'sample_count':2,'window':'matched legs','denominator':'equal legs','source':'source timing',
          'leg_evidence':[{'leg':1,'value':20.5,'index':127.0241,'peer_mean':16.1,'peer_count':2,'peer_ids':['peer1','peer2'],'coverage_s':60,'sample_count':1,'start_ms':1000,'end_ms':61000}]}]}}]}
    def test_nulls_provenance_and_per_leg_values_survive_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            summary,performance=export_report_files(self.detail(),folder)
            row=list(csv.DictReader(io.StringIO(summary.read_text())))[0]
            for field in ('value','coverage_s','reconstructed_elapsed_s'):self.assertEqual(row[field],'')
            self.assertEqual(row['reason'],'no valid racing window');self.assertEqual(row['source_conflicts'],'start state conflict');self.assertEqual(row['window'],'active race')
            values=list(csv.DictReader(io.StringIO(performance.read_text())))
            self.assertEqual(values[0]['index'],'109.9671');self.assertEqual(values[1]['index'],'127.0241');self.assertEqual(values[1]['peer_ids'],'peer1;peer2');self.assertEqual(values[1]['start_ms'],'1000');self.assertEqual(values[1]['quality'],'derived')
    def test_repeated_serialization_is_byte_identical_and_preserves_input(self):
        detail=self.detail(); original=json.dumps(detail)
        with tempfile.TemporaryDirectory() as folder:
            paths=export_report_files(detail,folder);before=[p.read_bytes() for p in paths];export_report_files(detail,folder);self.assertEqual(before,[p.read_bytes() for p in paths])
        self.assertEqual(json.dumps(detail),original)
if __name__=='__main__':unittest.main()
