import unittest
from bs4 import BeautifulSoup
from scripts.collect_institutions import mtr_invitation_links,parse_mtr_invitation

class InvitationTests(unittest.TestCase):
    def test_discovers_detail_not_just_procurement_plan(self):
        soup=BeautifulSoup('<a href="1075.html">Advertising (Contract No.: 1075)</a><a href="1855.html">Replacement (Contract No.: 1855)</a><a href="marketing.html">Marketing</a>','html.parser')
        self.assertEqual(len(mtr_invitation_links(soup,'https://www.mtr.com.hk/en/corporate/tenders/invitation.html')),2)
    def test_1075_is_prequalification_not_system_tender(self):
        soup=BeautifulSoup('<h1>Advertising Sales Agency Service for MTR In-train TV (Contract No.: 1075)</h1><p>Prequalification for services. Submit no later than 2:00 p.m. on 30 November 2026 (Hong Kong Time).</p><a href="q.pdf">Prequalification Questionnaire</a>','html.parser')
        r=parse_mtr_invitation(soup,'https://www.mtr.com.hk/en/corporate/tenders/1075.html')
        self.assertEqual(r['kind'],'prequalification')
        self.assertEqual(r['closing_at'],'2026-11-30T14:00:00+08:00')
        self.assertIn('广告销售',r['title_zh'])
        self.assertTrue(r['document_url'].endswith('/q.pdf'))
