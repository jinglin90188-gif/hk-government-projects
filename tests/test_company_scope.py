import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from company_scope import classify

class CompanyScopeTests(unittest.TestCase):
    def check(self,title,decision):
        fit=classify({'title':title})
        self.assertEqual(fit['decision'],decision,fit)
        self.assertNotIn('score',fit)
        self.assertTrue(fit['reason'])

    def test_compute_and_cloud(self):
        for title in ['智能算力中心建设','Supply of GPU servers','私有云永久数据备份系统扩充','数据中心UPS及冷却配套系统建设']:
            self.check(title,'include')
    def test_transport_and_clearance(self):
        for title in ['更换红隧交通管制及监察系统','车辆自动清关系统维护','Provision of mobile CCTV maintenance services','Design and Maintenance of the Information System for Taxis']:
            self.check(title,'include')
    def test_other_departments_count(self):
        self.check('医院预约信息系统升级','include')
        self.check('电力充储放一张网平台','include')
        self.check('为皇岗口岸供应及安装私家车分析与检测系统工程','include')
        self.check('为香港警务处提供第三代指挥及控制系统维修服务','include')
    def test_unrelated(self):
        for title in ['运输署办公室清洁服务','供应医院病床及检查椅子','道路重铺工程','保安员服务']:
            self.check(title,'exclude')
    def test_generic_system_not_automatically_relevant(self):
        self.check('Supply of a new system','review')
    def test_mixed_scope_needs_review(self):
        self.check('保安员服务及CCTV系统维护','review')
    def test_eligibility_not_an_exclusion(self):
        self.check('车辆自动清关系统（BURG类别）','include')

if __name__=='__main__':unittest.main()
