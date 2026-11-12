import importlib.util
from pathlib import Path
import unittest
from bs4 import BeautifulSoup

spec=importlib.util.spec_from_file_location('feed',Path(__file__).resolve().parents[1]/'scripts/collect_institutions.py')
feed=importlib.util.module_from_spec(spec);spec.loader.exec_module(feed)

class FeedTests(unittest.TestCase):
    def test_completed_mtr_is_not_open_or_future(self):
        soup=BeautifulSoup('<div class="reference_info"><div class="reference_info_title">Reference No. Q1</div><table><tr><td>Title or Scope</td><td>Smart Dynamic Train Inspection System</td></tr><tr><td>Anticipated Date for Invitation to Tender</td><td>Completed</td></tr></table></div>','html.parser')
        rows=feed.parse_mtr(soup,'https://www.mtr.com.hk/')
        self.assertEqual(rows[0]['status'],'历史／阶段待核实')
        self.assertEqual(rows[0]['kind'],'forecast')

    def test_awards_not_mixed_into_hsitp_tenders(self):
        soup=BeautifulSoup('<table><tr><td>WC/011</td><td>智能运营平台</td><td>2026年8月20日</td><td>承建商</td></tr></table>','html.parser')
        self.assertEqual(feed.parse_hsitp(soup,'https://www.hsitp.org/'),[])
