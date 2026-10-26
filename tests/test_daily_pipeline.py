import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import collect_projects as collector
from snapshot_tools import enrich_changes,validate_snapshot

NOW=datetime(2026,10,26,13,0,tzinfo=ZoneInfo('Asia/Hong_Kong'))

def row(reference='TD/2026/1'):
    with patch.object(collector,'NOW',NOW):
        r=collector.record('运输署','交通系统供应及维护服务','tender','https://www.td.gov.hk/',
            reference_no=reference,closing_date='2026-12-01',source_ids=['etb_xml'])
        return collector.deduplicate([r])[0]

class DailyPipelineTests(unittest.TestCase):
    def setUp(self):
        timer=patch.object(collector,'NOW',NOW)
        timer.start();self.addCleanup(timer.stop)

    def test_identical_data_has_no_fabricated_news(self):
        old=row();new=copy.deepcopy(old);new['verified_at']='2026-10-27T08:01:00+08:00'
        rows,changes=enrich_changes([new],{'updated_at':NOW.isoformat(),'projects':[old]},NOW)
        self.assertEqual(changes['new_count'],0)
        self.assertEqual(changes['updated_count'],0)
        self.assertEqual(rows[0]['change'],'unchanged')

    def test_deadline_change_is_update_not_new_project(self):
        old=row();new=copy.deepcopy(old);new['closing_date']='2026-12-15'
        rows,changes=enrich_changes([new],{'updated_at':NOW.isoformat(),'projects':[old]},NOW)
        self.assertEqual(changes['new_count'],0)
        self.assertEqual(changes['updated_count'],1)

    def test_first_run_is_baseline(self):
        rows,changes=enrich_changes([row()],{},NOW)
        self.assertTrue(changes['baseline'])
        self.assertEqual(changes['new_count'],0)
        self.assertEqual(rows[0]['change'],'baseline')

    def test_missing_notice_is_not_inferred_to_be_awarded(self):
        _,changes=enrich_changes([],{'updated_at':NOW.isoformat(),'projects':[row()]},NOW)
        self.assertEqual(changes['no_longer_seen_count'],1)
        self.assertNotIn('awarded',changes)

    def test_tender_reference_added_does_not_create_false_new_notice(self):
        old=row();new=copy.deepcopy(old);new['id']='another-reference-id'
        _,changes=enrich_changes([new],{'updated_at':NOW.isoformat(),'projects':[old]},NOW)
        self.assertEqual(changes['new_count'],0)

    def test_source_failure_keeps_last_good_but_not_as_fresh_open(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(collector,'STATE',Path(tmp)),patch.object(collector,'NOW',NOW):
            report={'status':'parsed','checked_at':NOW.isoformat()}
            collector.preserve_source_state('one',[row()],report)
            report={'status':'failed','checked_at':'2026-10-27T08:00:00+08:00'}
            restored=collector.preserve_source_state('one',[],report)
            self.assertEqual(len(restored),1)
            self.assertEqual(restored[0]['status'],'状态待核实')
            self.assertTrue(restored[0]['stale'])
            self.assertEqual(restored[0]['verified_at'],NOW.isoformat(timespec='seconds'))

    def test_broken_200_page_keeps_last_good(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(collector,'STATE',Path(tmp)):
            collector.preserve_source_state('one',[row()],{'status':'parsed','checked_at':NOW.isoformat()})
            restored=collector.preserve_source_state('one',[],{'status':'unparsed','checked_at':NOW.isoformat()})
            self.assertTrue(restored[0]['stale'])

    def test_explicit_empty_source_does_not_resurrect_old_notice(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(collector,'STATE',Path(tmp)):
            collector.preserve_source_state('one',[row()],{'status':'parsed','checked_at':NOW.isoformat()})
            self.assertEqual(collector.preserve_source_state('one',[],{'status':'empty','checked_at':NOW.isoformat()}),[])
            self.assertEqual(json.loads((Path(tmp)/'one.json').read_text())['items'],[])

    def test_failed_critical_sources_prevent_publication(self):
        rows=[row('TD/2026/'+str(i)) for i in range(26)]
        data={'updated_at':NOW.isoformat(),'projects':rows,'sources':[
            {'id':'source'+str(i),'status':'unparsed'} for i in range(70)],
            'stats':{'records':26,'open':26,'forecast':0,'sources':70}}
        result=validate_snapshot(data)
        self.assertFalse(result['publish_allowed'])
        self.assertTrue(any('中央核心来源' in error for error in result['errors']))

    def test_partial_sources_do_not_stop_valid_daily_publication(self):
        rows=[row('TD/2026/'+str(i)) for i in range(26)]
        sources=[{'id':sid,'status':'parsed'} for sid in ['etb_xml','gld_bd_json','gld_central_json']]
        sources.extend({'id':'source'+str(i),'status':'unparsed'} for i in range(67))
        result=validate_snapshot({'updated_at':NOW.isoformat(),'projects':rows,'sources':sources,
            'stats':{'records':26,'open':26,'forecast':0,'sources':70}})
        self.assertTrue(result['publish_allowed'])
        self.assertEqual(result['status'],'partial')

    def test_conflicting_deadlines_are_not_advertised_as_confirmed_open(self):
        a=row();b=copy.deepcopy(a);b['closing_date']='2026-12-10';b['source_ids']=['department']
        merged=collector.deduplicate([a,b])
        self.assertEqual(merged[0]['status'],'状态待核实')
        self.assertEqual(merged[0]['deadline_options'],['2026-12-01','2026-12-10'])

    def test_source_completion_order_does_not_change_output(self):
        a=row();b=copy.deepcopy(a);b['source_ids']=['department'];b['title']='交通系统供应及维护服务（修订）'
        self.assertEqual(collector.deduplicate(copy.deepcopy([a,b])),collector.deduplicate(copy.deepcopy([b,a])))

    def test_single_source_preview_does_not_overwrite_main_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'dist').mkdir();original={'updated_at':NOW.isoformat(),'projects':[]}
            (root/'dist/projects.json').write_text(json.dumps(original))
            spec={'id':'test','name':'test','department':'运输署','kind':'tender','url':'https://www.td.gov.hk/'}
            report={**spec,'status':'parsed','count':1,'pages':1,'documents':[],'errors':[]}
            with patch.object(collector,'ROOT',root),patch.object(collector,'CACHE',root/'cache'),patch.object(collector,'source_specs',return_value=[spec]),patch.object(collector,'crawl_source',return_value=([row()],report)),patch.object(sys,'argv',['collect_projects.py','--only','test']):
                collector.main()
            self.assertEqual(json.loads((root/'dist/projects.json').read_text()),original)
            self.assertTrue((root/'dist/projects.preview.json').exists())

if __name__=='__main__':unittest.main()
