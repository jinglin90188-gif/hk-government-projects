"""Anonymous institutional procurement feed; no login or access-control bypass."""
import concurrent.futures
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from dateutil.parser import parse as parse_date
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from institution_sources import SOURCES, parse_airport
from company_scope import classify
from snapshot_tools import retain_missing_projects
NOW=datetime.now(ZoneInfo('Asia/Hong_Kong'))
PATH=ROOT/'dist/institutions.json'
NOTES={
 'institution_airport':'公开列表可匿名查看；RFI按公告邮件索取文件，部分投标操作需ePROS。',
 'institution_mtr':'同时检查六类采购计划及独立招标／意向邀请栏目；计划、资格预审及正式招标分开记录，递交可能需供应商平台。',
 'institution_hkstp':'官网说明可访客登入招标平台；当前官网只覆盖少量公告，访客平台本次返回503，清单不完整。',
 'institution_hsitp':'公开页可见项目、编号、刊登及截止日期，并有部分文件链接。',
 'institution_awe':'公开页当前为ePROS供应商入口，未取得公开项目清单，不表示无采购。',
 'institution_westk':'公开商机入口存在；自动请求被拒绝，未提取项目，未尝试绕过。',
 'institution_ura':'公开意向及招标栏目存在；自动请求被拒绝时保留覆盖缺口。',
 'institution_link':'尚未确认可匿名采集的项目清单，供应商采购渠道需人工核实。',
 'institution_ocean':'此前招标页请求返回403，未继续尝试；公开入口及授权渠道待人工核实。',
}

def get(url):
    r=requests.get(url,timeout=25)
    r.raise_for_status()
    return BeautifulSoup(r.content,'html.parser')

def make_record(dep,title,kind,url,**fields):
    r=dict(department=dep,title=title,kind=kind,source_url=url,reference_no='',closing_date='',forecast_date='',document_url='',verified_at=NOW.isoformat(),status='状态待核实')
    r.update(fields)
    date=r['closing_date']
    if date:r['status']='已截标' if date<NOW.date().isoformat() else '正在招标'
    return r

def parse_mtr(soup,url):
    rows=[]
    for box in soup.select('.reference_info'):
        ref=box.select_one('.reference_info_title')
        values={c[0].get_text(' ',strip=True):c[1].get_text(' ',strip=True) for tr in box.select('tr') if len(c:=tr.find_all('td',recursive=False))==2}
        title=values.get('Title or Scope','')
        if not ref or not title:continue
        period=values.get('Anticipated Date for Invitation to Tender','')
        r=make_record('港铁公司',title,'forecast',url,reference_no=ref.get_text(' ',strip=True).replace('Reference No.','').strip(),forecast_date=period,
                      notes='采购计划，不能推定仍接受申请；预审提交：'+values.get('Anticipated Date of Prequalification Submission or Category of Work in Approved List','未注明'))
        q=re.search(r'([1-4])Q/(20\d{2})',period)
        r['status']='计划日期已过／需核实' if q and (int(q[2]),int(q[1]))<(NOW.year,(NOW.month-1)//3+1) else '采购计划' if q else '历史／阶段待核实'
        rows.append(r)
    return rows

def mtr_invitation_links(soup,url):
    result={}
    for a in soup.find_all('a',href=True):
        target=urljoin(url,a['href']).split('#')[0]
        if re.fullmatch(r'https://www\.mtr\.com\.hk/en/corporate/tenders/[A-Za-z0-9_-]+\.html',target) and re.search(r'Contract No|Agreement No|Consultancy|Prequalification|Simulator|Replacement',a.get_text(' ',strip=True),re.I):
            result[target]=a.get_text(' ',strip=True)
    return result

def parse_mtr_invitation(soup,url):
    text=soup.get_text(' ',strip=True)
    heading=soup.find(['h1','h2'])
    title=heading.get_text(' ',strip=True) if heading else ''
    ref=re.search(r'(?:Contract|(?:Consultancy\s+)?Agreement)\s+No\.?\s*[:：]\s*([A-Z0-9][A-Z0-9/-]*)',title or text,re.I)
    if not ref:return None
    kind='prequalification' if re.search(r'prequalif',text,re.I) else 'eoi' if re.search(r'expressions? of interest',text,re.I) else 'tender'
    dates=list(re.finditer(r'(?:no later than|not later than|on or before|by)\s+(?:(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*(?:on)?\s*)?(\d{1,2}\s+[A-Za-z]+\s+20\d{2})',text,re.I))
    closing='';closing_at=''
    if dates:
        d=dates[-1];closing=parse_date(d[4]).date().isoformat()
        if d[1]:
            hour=int(d[1])%12+(12 if d[3].lower()=='p' else 0)
            closing_at=f'{closing}T{hour:02}:{int(d[2] or 0):02}:00+08:00'
    link=next((a for a in soup.find_all('a',href=True) if re.search(r'questionnaire|tender document|application',a.get_text(' ',strip=True),re.I)),None)
    r=make_record('港铁公司',title or ref[0],kind,url,reference_no=ref[1],closing_date=closing,closing_at=closing_at,
                  document_url=urljoin(url,link['href']) if link else '',notes='独立招标／意向邀请公告；资格、服务范围及时间以详情原文为准。')
    r['status']='已截标' if closing and (closing<NOW.date().isoformat() or closing_at and datetime.fromisoformat(closing_at)<=NOW) else {'prequalification':'资格预审中','eoi':'意向征集中','tender':'正在招标'}[kind] if closing else '状态待核实'
    if ref[1]=='1075':
        r.update(title_zh='港铁车厢电视广告销售代理服务（资格预审）',title_source='中文译述',eligibility_note='核心工作为新闻资讯内容、广告销售及媒体运营；不是列车电视系统建设或软件采购，不能仅凭TV或数据分析字眼判定为对口系统项目。')
    return r

def parse_hsitp(soup,url):
    rows=[]
    for table in soup.find_all('table'):
        if '邀請截止日期' not in table.get_text():continue
        for tr in table.find_all('tr'):
            c=tr.find_all('td',recursive=False)
            if len(c)!=4:continue
            text=c[0].get_text(' ',strip=True)
            ref=re.search(r'招標編號\s*[:：]\s*(.+)',text)
            date=re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日',c[3].get_text())
            if not ref or not date:continue
            link=c[1].find('a',href=True)
            rows.append(make_record('港深创新及科技园',text[:ref.start()].strip(),'tender',url,reference_no=ref[1],closing_date=f'{int(date[1]):04}-{int(date[2]):02}-{int(date[3]):02}',closing_at=f'{int(date[1]):04}-{int(date[2]):02}-{int(date[3]):02}T12:00:00+08:00' if '12:00' in c[3].get_text() else '',document_url=urljoin(url,link['href']) if link else ''))
    return rows

def collect(spec):
    report=dict(spec,note=NOTES[spec['id']],checked_at=NOW.isoformat(),status='待深入核查',count=0)
    rows=[]
    if spec.get('manual'):return report,rows
    try:
        soup=get(spec['url']); sid=spec['id']
        if sid=='institution_airport':
            rows=parse_airport(soup,spec['url'],make_record)
            if not rows:raise ValueError('未识别机场列表结构，不能判定暂无项目')
            try:
                chinese=get(spec['url'].replace('/en/','/tc/'))
                for box in chinese.select('div.data'):
                    ref=box.select_one('.contractData');title=box.select_one('.titleData')
                    if not ref or not title:continue
                    text=title.get_text(' ',strip=True)
                    if not re.search(r'[\u4e00-\u9fff]',text):continue
                    for r in rows:
                        if r['reference_no']==ref.get_text(' ',strip=True):r.update(title_zh=text,title_source='机构中文原文')
            except Exception:report['chinese_note']='中文页暂不可用，保留已核实译述及英文原题'
        elif sid=='institution_mtr':
            errors=[]
            invitation_url='https://www.mtr.com.hk/en/corporate/tenders/invitation.html'
            try:
                invitations=mtr_invitation_links(get(invitation_url),invitation_url)
                if not invitations:raise ValueError('独立邀请栏目未识别项目链接')
                report['invitation_links']=len(invitations)
                for detail_url in invitations:
                    try:
                        entry=parse_mtr_invitation(get(detail_url),detail_url)
                        if entry:rows.append(entry)
                        else:errors.append('详情待解析：'+detail_url)
                    except Exception:errors.append('详情读取失败：'+detail_url)
            except Exception:errors.append('独立招标／意向邀请栏目未成功读取')
            for name in ['or','new_projects','property_services','marketing','others','sales']:
                url='https://www.mtr.com.hk/en/corporate/tenders/'+name+'.html'
                try:
                    found=parse_mtr(get(url),url)
                    try:
                        chinese=get(url.replace('/en/','/ch/'))
                        titles={b.select_one('.reference_info_title').get_text(' ',strip=True).replace('編號','').strip():b.select_one('table td:nth-of-type(2)').get_text(' ',strip=True) for b in chinese.select('.reference_info') if b.select_one('.reference_info_title') and b.select_one('table td:nth-of-type(2)')}
                        for r in found:
                            if r['reference_no'] in titles:
                                r.update(title_zh=titles[r['reference_no']],title_source='机构中文原文',source_url=url.replace('/en/','/ch/'))
                    except Exception as e:errors.append('中文标题核查失败：'+str(e)[:100])
                    rows.extend(found)
                except Exception as e:errors.append(str(e)[:150])
            if errors:report['errors']=errors
            if not rows:raise ValueError('未取得港铁采购计划')
        elif sid=='institution_hsitp':rows=parse_hsitp(soup,spec['url'])
        report['status']='已提取公开记录（非全覆盖）' if rows else '公开入口可见／清单待核查'
        if report.get('errors'):report['status']='部分提取／部分请求失败'
    except Exception as e:report.update(status='访问或解析失败／需人工核查',error=str(e)[:250])
    report['count']=len(rows)
    for r in rows:
        r['id']=hashlib.sha256((r['department']+'|'+r['reference_no']).encode()).hexdigest()[:18]
        r['source_id']=spec['id'];r['access_note']=report['note']
        r['company_fit']=classify(r)
        if spec['id']=='institution_mtr' and r['reference_no']=='1075':
            r['company_fit'].update(decision='review',reason='广告销售及媒体运营为主，不是电视系统建设采购；需另核合作范围')
        if re.search('ACDM|AWMS|Digital Displays|DESFire',r['title'],re.I):r['company_fit'].update(decision='include',reason='机场业务系统、数字显示或身份识别设备相关，具体资格待核实')
        if re.search(r'Smart Dynamic Train Inspection System|Cab Simulator|Emergency Communication System',r['title'],re.I):
            r['company_fit'].update(decision='include',reason='明确涉及智能检测、仿真训练或通信系统，资质及实际阶段须核实')
        translations={
            'PRO/T586/26/NC':'香港国际机场机场工作管理系统（AWMS）改造：设计、实施、支援及保养',
            'E5002 & ME5002':'机场二号客运大楼数字显示系统设计、供应、安装及综合保养',
            'E5003 & ME5003':'机场二号客运大楼客运廊数字显示系统设计、供应、安装及综合保养',
            'PRO/T637/26/CA':'机场禁区通行证DESFire卡供应及交付框架协议',
            'Q118570':'港铁智能动态列车检测系统采购计划',
            'Q118440':'港铁新列车驾驶室模拟器及车站、车务人员培训设施采购计划',
            'Q121245':'港铁高铁紧急通信系统更换采购计划',
            'Q119427':'供应电动私家车',
        }
        if r['reference_no'] in translations and not r.get('title_zh'):r.update(title_zh=translations[r['reference_no']],title_source='中文译述')
        if r['reference_no']=='ACDM/RFI/2026':
            # Verify exact deadline against the public detail, never infer a time from a date-only list.
            try:
                text=get(r['source_url']).get_text(' ',strip=True)
                if re.search(r'4:30\s*p\.?m\.?\s+on\s+1 December 2026',text,re.I):r['closing_at']='2026-12-01T16:30:00+08:00'
            except Exception: r['detail_unverified']=True
            r['title_zh']='香港国际机场协同决策系统（ACDM）供应、实施及综合保养服务信息征询'
        if r.get('closing_at') and datetime.fromisoformat(r['closing_at'])<=NOW:r['status']='已截标'
        if spec['id']=='institution_airport' and not r.get('title_zh'):
            airport_titles={
                'RAD/26-027 & RAD/26-028':'烟酒产品及香水与化妆品经营牌照',
                'RAD/ 26-032':'生活精品经营牌照', 'RAD/ 26-026':'二号客运大楼客运廊咖啡店经营牌照',
                'RAD/ 26-031':'玩具及生活精品／包装食品经营牌照',
                'PRO/T569/26/SW':'机场一般土木工程保养、改善及翻新定期合约',
                'RAD/ 26-029':'西式快餐经营牌照','RAD/ 26-030':'美食广场经营牌照',
                'PRO/T594/26/TC':'香港国际机场媒体投放服务框架协议',
                'Contract E3010':'机场城市海湾区海滨长廊工程（含标志性行人桥）资格预审',
            }
            if r['reference_no'] in airport_titles:r.update(title_zh=airport_titles[r['reference_no']],title_source='中文译述')
        r['business_categories']=business_categories(r)
        r['forecast_display']=re.sub(r'([1-4])Q/(20\d{2})',lambda m:f'{m[2]}年第{m[1]}季',r.get('forecast_date','')).replace('Completed','已完成').replace('Not Applicable','不适用').replace('TBA','待公布')
        r['notes']=r.get('notes','').replace('Completed','已完成').replace('Not Applicable','不适用')
    return report,rows

def business_categories(row):
    text=' '.join(str(row.get(k,'') or '') for k in ['title','title_zh'])
    categories=[]
    if re.search(r'系统|系統|软件|軟件|數據|数据|數碼|数字|網絡|网络|通信|通訊|智能|智慧|仿真|模擬|模拟|信息|資訊|system|software|platform|network|digital|data|cyber|simulator|telemetry|IoT|DESFire',text,re.I):categories.append('系统与数字化')
    if re.search(r'工程|建造|土木|建筑|建築|設備|设备|裝置|装置|機械|机械|列車|列车|車輛|车辆|供電|供电|安装|安裝|翻新|冷氣|空調|work[s]?\b|construction|equipment|installation|machine|train|vehicle|electrical',text,re.I):categories.append('工程与设备')
    return categories or ['其他采购与服务']

def main():
    specs=[dict(s) for s in SOURCES]
    specs += [dict(id='institution_link',department='领展',url='https://www.linkreit.com/en/contact-us/',manual=True),dict(id='institution_ocean',department='海洋公园',url='https://www.oceanpark.com.hk/en',manual=True)]
    previous=json.loads(PATH.read_text()) if PATH.exists() else {}
    reports=[];rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for report,found in pool.map(collect,specs):
            if '失败' in report['status']:
                current_ids={r['id'] for r in found}
                retained=[dict(r,stale=True) for r in previous.get('projects',[]) if r.get('source_id')==report['id'] and r['id'] not in current_ids]
                found.extend(retained)
                report['retained_count']=len(retained)
            reports.append(report);rows.extend(found)
    unique={}
    for r in rows:
        old=unique.get(r['id'])
        if old and old['kind']!='forecast' and r['kind']=='forecast':continue
        unique[r['id']]=r
    kept=retain_missing_projects(list(unique.values()),previous,NOW)
    data=dict(updated_at=NOW.isoformat(),scope='仅匿名公开资料；不使用供应商账号；访问失败不等于无项目；未检出项目保留历史记录',sources=reports,projects=kept)
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'sources':len(reports),'records':len(unique),'related':sum(r['company_fit']['decision']=='include' for r in unique.values())},ensure_ascii=False))

if __name__=='__main__':main()
