import unittest
from bs4 import BeautifulSoup
from institution_sources import parse_airport, source_specs

class InstitutionTests(unittest.TestCase):
    def test_rfi_is_not_formal_tender(self):
        html='<div class="data"><div class="typeData">Request for Information</div><div class="contractData">ACDM/RFI/2026</div><div class="titleData"><a href="/en/airport-authority/tender-notices/ACDM_RFI_2026#it">Airport Collaborative Decision Making System</a></div><div class="closingDateData">2026-12-01</div></div>'
        def factory(dep,title,kind,url,**fields):
            return dict(department=dep,title=title,kind=kind,source_url=url,status='正在招标',**fields)
        rows=parse_airport(BeautifulSoup(html,'html.parser'),'https://www.hongkongairport.com/',factory)
        self.assertEqual(rows[0]['kind'],'rfi')
        self.assertEqual(rows[0]['status'],'信息征询中')
        self.assertNotIn('#',rows[0]['source_url'])

    def test_navigation_is_not_project(self):
        self.assertEqual(parse_airport(BeautifulSoup('<a>Supplier registration</a>','html.parser'),'https://example.com',None),[])

    def test_sources_are_unique(self):
        rows=source_specs()
        self.assertEqual(len(rows),len({r['id'] for r in rows}))
