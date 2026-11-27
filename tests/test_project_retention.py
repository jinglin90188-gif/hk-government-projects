import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from snapshot_tools import retain_missing_projects

NOW=datetime(2026,11,27,15,tzinfo=ZoneInfo('Asia/Hong_Kong'))
def row():return dict(id='one',department='运输署',title='交通系统',reference_no='TD/1',kind='tender',status='正在招标',closing_date='2026-12-01',verified_at='2026-11-26T15:00:00+08:00')
class RetentionTests(unittest.TestCase):
    def test_missing_notice_kept_not_inferred_awarded(self):
        old=row();r=retain_missing_projects([],{'projects':[old]},NOW)[0]
        self.assertEqual(r['status'],'状态待核实');self.assertTrue(r['retained_missing'])
        self.assertEqual(r['verified_at'],old['verified_at']);self.assertNotIn('stale',old)
    def test_closed_kept_and_forecast_not_counted_as_current(self):
        old=row();old.update(closing_date='2026-11-25')
        self.assertEqual(retain_missing_projects([],{'projects':[old]},NOW)[0]['status'],'已截标')
        old.update(kind='forecast',closing_date='')
        self.assertTrue(retain_missing_projects([],{'projects':[old]},NOW)[0]['outdated'])
    def test_reappearing_project_has_no_duplicate(self):
        old=row();fresh=row();fresh.update(id='changed',reference_no='TD 1')
        self.assertEqual(len(retain_missing_projects([fresh],{'projects':[old]},NOW)),1)
    def test_missing_since_stable_across_runs(self):
        first=retain_missing_projects([],{'projects':[row()]},NOW)
        second=retain_missing_projects([],{'projects':first},NOW)
        self.assertEqual(first[0]['missing_since'],second[0]['missing_since'])
        self.assertEqual(first[0]['review_note'],second[0]['review_note'])
