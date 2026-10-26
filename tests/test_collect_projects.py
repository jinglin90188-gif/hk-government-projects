import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect_projects as c

class CollectorRegressionTests(unittest.TestCase):
    def setUp(self):
        timer=patch.object(c,'NOW',datetime(2026,10,26,13,0,tzinfo=ZoneInfo('Asia/Hong_Kong')))
        timer.start();self.addCleanup(timer.stop)

    def test_spaced_chinese_headers(self):
        page='<table><tr><th>截 标 日 期</th><th>投 标 书 编 号</th><th>项 目</th></tr><tr><td>11.12.2026</td><td>TD(T) 2/2026 (193 KB)</td><td>管理、营运及维修大老山隧道的合约</td></tr></table>'
        rows=c.parse_tables_page(c.soup_from(page.encode()),'运输署','tender','https://www.td.gov.hk/')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['closing_date'],'2026-12-11')

    def test_same_day_already_closed(self):
        with patch.object(c,'NOW',datetime(2026,10,26,13,0,tzinfo=ZoneInfo('Asia/Hong_Kong'))):
            row=c.record('运输署','交通系统的供应及维护服务','tender','https://www.td.gov.hk/',closing_date='2026-10-26',closing_text='2026-10-26 12:00:00')
            self.assertEqual(row['status'],'已截标')

    def test_missing_deadline_never_open(self):
        row=c.record('运输署','交通系统的供应及维护服务','tender','https://www.td.gov.hk/')
        self.assertEqual(row['status'],'状态待核实')

    def test_eoi_is_not_a_formal_tender(self):
        class Page:
            def extract_text(self):
                return 'This is not a tender exercise. From 12 noon on 26 October 2026. Services commence on 7 May 2029 for a period of six (6) years.'
        class Reader:
            pages=[Page()]
        title='Invitation for Expression of Interest for Toll Collection and Maintenance of HKeToll'
        with patch.object(c,'fetch',return_value=(b'%PDF','https://www.td.gov.hk/test.pdf')),patch.object(c,'PdfReader',return_value=Reader()):
            row=c.tender_pdf('https://www.td.gov.hk/test.pdf','运输署',title)[0]
        self.assertEqual(row['status'],'意向征集')
        self.assertEqual(row['kind'],'forecast')
        self.assertEqual(row['contract_start'],'2029-05-07')
        self.assertEqual(row['contract_years'],6)
        self.assertEqual(row['document_available_from'],'2026-10-26')

    def test_old_forecast_flagged(self):
        row=c.record('路政署','公共照明系统的管理及保养','forecast','https://www.hyd.gov.hk/',forecast_date='2021年第1季')
        self.assertTrue(row['outdated'])

    def test_future_month_not_misread_as_quarter(self):
        row=c.record('医务卫生局','内视镜显像系统及检查椅子','forecast','https://www.gld.gov.hk/',forecast_date='2026年12月')
        self.assertFalse(row.get('outdated',False))

    def test_dedup_reference_file_size(self):
        a=c.record('运输署','交通系统的供应及维护服务','tender','https://www.td.gov.hk/',reference_no='TD(T) 2/2026 (193 KB)',closing_date='2026-12-11',source_ids=['department'])
        b=c.record('运输署','交通系统的供应及维护服务','tender','https://pcms2.gld.gov.hk/',reference_no='TD(T) 2/2026',closing_date='2026-12-11',source_ids=['etb'])
        rows=c.deduplicate([a,b])
        self.assertEqual(len(rows),1)
        self.assertEqual(set(rows[0]['source_ids']),{'department','etb'})

    def test_awarded_table_not_imported(self):
        page='<table><tr><th>合约编号</th><th>项目名称</th><th>截标日期</th><th>承办商</th></tr><tr><td>T/1/2026</td><td>交通系统的供应及维护服务</td><td>2026年12月11日</td><td>某公司</td></tr></table>'
        self.assertEqual(c.parse_tables_page(c.soup_from(page.encode()),'运输署','tender','https://www.td.gov.hk/'),[])

    def test_forecast_pdf_complete_archsd_title(self):
        # The centered column heading is not the left edge of the data column.
        # Use a compact layout fixture to guard against losing the first half of titles.
        layout='''FORECAST OF INVITATIONS TO TENDER
                   Contract No. & Title of Contract                 Probable Date
    22GB  Contract No.:SS R504                                      2026 Q4
          Design and Construction of Sha Tau Kok Control Point
          合約編號 : SS R504
          設計及建造沙頭角口岸與相關工程
          (新工程合約工程建造合約香港版C選項)
'''
        class Page:
            def extract_text(self,**kwargs):return layout
        class Reader:
            pages=[Page()]
        with patch.object(c,'fetch',return_value=(b'%PDF','https://www.archsd.gov.hk/test.pdf')),patch.object(c,'PdfReader',return_value=Reader()):
            rows=c.pdf_forecast('https://www.archsd.gov.hk/test.pdf','建筑署','https://www.archsd.gov.hk/')
        self.assertEqual(rows[0]['reference_no'],'SS R504')
        self.assertEqual(rows[0]['title'],'设计及建造沙头角口岸与相关工程')

if __name__=='__main__':unittest.main()
