import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import collect_projects as c
from company_scope import classify
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

class StageScopeTests(unittest.TestCase):
    def test_boilerplate_and_news_are_not_projects(self):
        for title in ['投标者必须于截标日期正午12时前提交标书','文化体育及旅游局局长出席开幕式致辞全文','Category Code 类别编号','标准合约文件 (只提供英文版)']:
            self.assertFalse(c.valid_project_title(title))
        self.assertTrue(c.valid_project_title('为数字政策办公室供应备份系统并提供相关服务'))

    def test_explicit_no_invitation_message(self):
        self.assertTrue(c.EXPLICIT_EMPTY.search("There's no outstanding invitation at the moment."))
        self.assertTrue(c.EXPLICIT_EMPTY.search('目前没有未来的资讯科技项目'))

    def test_adjacent_open_tender_included_but_forecast_not(self):
        for title in ['优化港岛北维多利亚港海滨 – 设计及建造','Enhancement of Victoria Harbour Waterfront on Hong Kong Island North – Design and Construction','Replacement of Tunnel Ventilation System']:
            self.assertEqual(classify({'title':title,'kind':'tender','status':'正在招标'})['decision'],'include')
            self.assertEqual(classify({'title':title,'kind':'forecast','status':'招标预报'})['decision'],'exclude')

    def test_mixed_open_scope_is_included(self):
        self.assertEqual(classify({'title':'保安员服务及CCTV系统维护','kind':'tender','status':'正在招标'})['decision'],'include')

    def test_official_bilingual_alias_links_other_forecast(self):
        title='Road Works for Smart and Green Mass Transit System Remaining Phase'
        chinese='洪水桥新发展区智慧绿色集体运输系统道路工程'
        tender=c.record('土木工程拓展署',title,'tender','https://www.cedd.gov.hk/test/',reference_no='CE 39/2026 (HY)',closing_date='2026-12-04',title_aliases=[title,chinese])
        forecast=c.record('土木工程拓展署',chinese,'forecast','https://www.cedd.gov.hk/forecast/',forecast_date='2026 Q4')
        self.assertEqual(len(c.deduplicate([tender,forecast])),1)

    def test_cedd_heading_detail_and_bilingual_forecast_merge(self):
        title='Enhancement of Victoria Harbour Waterfront on Hong Kong Island North – Design and Construction'
        html=f'<div id="content"><h3>Consultancy Agreement No.</h3>CE 43/2026 (CE)<h3>Agreement Title</h3>{title}<h3>Invitation Date</h3>09/10/2026<h3>Closing Date and Time</h3>12:00 noon, Friday, 4 Dec 2026<h3>Consultants Invited</h3>Consultants in Group 3</div>'
        with patch.object(c,'NOW',datetime(2026,10,26,tzinfo=ZoneInfo('Asia/Hong_Kong'))):
            tender=c.parse_detail(c.soup_from(html.encode()),'土木工程拓展署','tender','https://www.cedd.gov.hk/eng/tender-notices/consultancy-agreements/test.html')[0]
            forecast=c.record('土木工程拓展署','优化港岛北维多利亚港海滨 – 设计及建造','forecast','https://www.cedd.gov.hk/forecast/',forecast_date='2026 Q4',source_ids=['forecast'])
            rows=c.deduplicate([forecast,tender])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['kind'],'tender')
        self.assertEqual(rows[0]['closing_date'],'2026-12-04')
        self.assertEqual(rows[0]['closing_at'],'2026-12-04T12:00:00+08:00')
        self.assertIn('Group 3',rows[0]['eligibility_note'])
        self.assertEqual(rows[0]['previous_forecast_date'],'2026 Q4')

if __name__=='__main__':unittest.main()
