import copy
import importlib.util
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
builder=module('report_builder',ROOT/'scripts/build_reports.py')
rollup=module('report_rollup',ROOT/'scripts/aggregate_reports.py')

class ReportTests(unittest.TestCase):
    def setUp(self):self.report=json.loads((ROOT/'reports/weekly/2026-10-26.json').read_text(encoding='utf-8'))
    def test_first_report_valid(self):builder.validate(self.report)
    def test_report_renders_with_source_links(self):
        page=builder.render(self.report)
        self.assertIn('官方公告',page)
        self.assertIn('原始文件',page)
        self.assertIn('重点部门覆盖情况',page)
    def test_old_news_is_rejected(self):
        self.report['news'][0]['published_at']='2026-08-01'
        with self.assertRaises(ValueError):builder.validate(self.report)
    def test_closed_tender_is_rejected(self):
        self.report['projects'][0]['closing_at']='2026-10-23T12:00:00+08:00'
        with self.assertRaises(ValueError):builder.validate(self.report)
    def test_eoi_is_not_forced_to_have_tender_deadline(self):
        self.assertIsNone(self.report['projects'][2]['closing_at']);builder.validate(self.report)
    def test_cross_week_projects_not_double_counted(self):
        second=copy.deepcopy(self.report);second['publication_date']='2026-10-27';second['verified_at']='2026-10-27'
        result=rollup.aggregate([self.report,second],'monthly','2026-10')
        self.assertEqual(result['distinct_tracked_projects'],3)
        self.assertEqual(len(result['projects'][0]['snapshots']),2)
        self.assertEqual(len(result['news']),2)
    def test_calendar_month_not_four_weeks(self):
        start,end=rollup.bounds('monthly','2026-10');self.assertEqual((end-start).days,31)

if __name__=='__main__':unittest.main()
