"""Public institutional sources. Registration pages are not tender records."""
from urllib.parse import urljoin

SOURCES = [
    dict(id='institution_airport',department='香港机场管理局',url='https://www.hongkongairport.com/en/airport-authority/tender-notices/',parser='airport'),
    dict(id='institution_mtr',department='港铁公司',url='https://www.mtr.com.hk/en/corporate/tenders/Latest_advertisement.html'),
    dict(id='institution_hkstp',department='香港科技园公司',url='https://www.hkstp.org/zh-hk/tender-notice'),
    dict(id='institution_hsitp',department='港深创新及科技园',url='https://www.hsitp.org/tc/tender-notices'),
    dict(id='institution_awe',department='亚洲国际博览馆',url='https://www.asiaworld-expo.com/zh-tc/about-us/tender-n-notices/'),
    dict(id='institution_westk',department='西九文化区管理局',url='https://www.westkowloon.hk/en/business-opportunities'),
    dict(id='institution_ura',department='市区重建局',url='https://www.ura.org.hk/tc/announcement-and-notices'),
]

def source_specs():
    return [dict(kind='tender',parser='html',max_pages=8,name=s['department']+'公开采购机会',**s)
            if 'parser' not in s else dict(kind='tender',max_pages=8,name=s['department']+'公开采购机会',**s)
            for s in SOURCES]

def parse_airport(soup, url, make_record):
    result=[]
    for node in soup.select('div.data'):
        def value(selector):
            found=node.select_one(selector)
            return found.get_text(' ',strip=True) if found else ''
        link=node.select_one('.titleData a[href]')
        if not link:continue
        title=value('.titleData'); ref=value('.contractData'); closing=value('.closingDateData')
        label=value('.typeData').lower()
        if not title or not ref or len(closing)!=10:continue
        kind='rfi' if 'request for information' in label else 'eoi' if 'expression of interest' in label else 'prequalification' if 'prequal' in label else 'rfq' if 'request for quotation' in label else 'rfp' if 'request for proposal' in label else 'tender' if 'invitation to tender' in label else 'unknown'
        row=make_record('香港机场管理局',title,kind,urljoin(url,link['href']).split('#')[0],
                        reference_no=ref,closing_date=closing,procurement_type=kind,
                        notes='信息征询不构成合约承诺；索取及回覆条件须查详情原文。' if kind=='rfi' else '')
        if row['status']=='正在招标' and kind!='tender':
            row['status']={'rfi':'信息征询中','eoi':'意向征集中','prequalification':'资格预审中','rfq':'报价邀请中','rfp':'方案邀请中','unknown':'阶段待核实'}[kind]
        result.append(row)
    return result
