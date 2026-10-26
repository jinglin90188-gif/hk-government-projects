#!/usr/bin/env python3
"""Collect official public tender records without relevance filtering.

Each source has its own fetch/parse outcome. HTTP success alone never means
that all records were parsed; unresolved sources stay visible in coverage.
"""
import argparse
import base64
import csv
import hashlib
import html
import io
import json
import re
import subprocess
import sys
import threading
import time
import warnings
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from opencc import OpenCC
from pypdf import PdfReader
warnings.filterwarnings('ignore', module='urllib3')
warnings.filterwarnings('ignore', module='bs4')

ROOT = Path(__file__).resolve().parent
NOW = datetime.now(ZoneInfo('Asia/Hong_Kong'))
CC = OpenCC('t2s')
LOCK = threading.Lock()
USER_AGENT = 'HKTenderDirectory/2.0 (public procurement research; daily update)'
CACHE = ROOT / 'cache'
STATE = ROOT / 'state' / 'sources'
SESSIONS = threading.local()
CACHE_MAX_AGE = 3600

def clean(value):
    text=CC.convert(re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ',html.unescape(str(value or ''))))).strip()
    return re.sub(r'(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])','',text).replace('衞','卫')

def fetch(url,_depth=0):
    if _depth>5:raise RuntimeError('网页重定向次数超过5次，请检查官方入口')
    key = hashlib.sha256(url.encode()).hexdigest()
    target = CACHE / key
    meta = CACHE / (key + '.json')
    if target.exists() and meta.exists() and time.time() - target.stat().st_mtime < CACHE_MAX_AGE:
        payload=target.read_bytes();final=json.loads(meta.read_text())['url']
        if len(payload)<8000:
            redirect=BeautifulSoup(payload,'html.parser').find('meta',attrs={'http-equiv':re.compile('refresh',re.I)})
            if redirect:
                match=re.search(r'url\s*=\s*[\'"]?([^\'";]+)',redirect.get('content',''),re.I)
                if match:
                    dest=urljoin(final,match.group(1).strip())
                    if dest!=url and urlparse(dest).scheme in ['http','https']:return fetch(dest,_depth+1)
        return payload,final
    import requests
    if not hasattr(SESSIONS, 'session'):
        SESSIONS.session = requests.Session()
        SESSIONS.session.headers['User-Agent'] = USER_AGENT
    try:
        response = SESSIONS.session.get(url, timeout=(10, 25))
        response.raise_for_status()
        payload, final = response.content, response.url
    except requests.RequestException:
        # Use configured system transport when Python's trust store differs.
        result = subprocess.run(['curl','--fail','--location','--silent','--show-error','--max-time','25',url], capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace')[-300:])
        payload, final = result.stdout, url
    if len(payload)<8000 and b'<meta' in payload.lower():
        redirect=BeautifulSoup(payload,'html.parser').find('meta',attrs={'http-equiv':re.compile('refresh',re.I)})
        if redirect:
            match=re.search(r'url\s*=\s*[\'"]?([^\'";]+)',redirect.get('content',''),re.I)
            if match:
                target_url=urljoin(final,match.group(1).strip())
                if target_url!=url and urlparse(target_url).scheme in ['http','https']:return fetch(target_url,_depth+1)
    CACHE.mkdir(exist_ok=True)
    target.write_bytes(payload)
    meta.write_text(json.dumps({'url': final}), encoding='utf-8')
    return payload, final

def soup_from(payload):
    return BeautifulSoup(payload, 'html.parser', from_encoding='utf-8')

def date_value(text):
    value = clean(text)
    value = re.sub(r'(星期|周)[一二三四五六日天]|[(（][^()（）]*[)）]', ' ', value)
    match = re.search(r'(20\d{2})\s*[年/.-]\s*(\d{1,2})\s*[月/.-]\s*(\d{1,2})',value)
    if match:
        try:
            return datetime(*map(int,match.groups()),tzinfo=NOW.tzinfo).date().isoformat()
        except ValueError:
            return ''
    match = re.search(r'(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(20\d{2})',value)
    if match:
        try:
            d,m,y=map(int,match.groups())
            return datetime(y,m,d,tzinfo=NOW.tzinfo).date().isoformat()
        except ValueError:
            return ''
    if re.search(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b',value,re.I) and re.search(r'20\d{2}', value):
        try:
            return dateparser.parse(value, fuzzy=True,dayfirst=True).date().isoformat()
        except (ValueError, OverflowError):
            pass
    return ''

def department(value):
    value = clean(value).split('——')[0]
    if re.fullmatch(r'发展局\s*[（(]工务科[）)]',value):return '发展局'
    return {'香港海关':'香港海关','海关':'香港海关','机电工程署营运基金':'机电工程署',
        '房委会/房屋署':'房屋委员会及房屋署','房委会／房屋署':'房屋委员会及房屋署',
        '财经事务及库务局——库务科':'财经事务及库务局'}.get(value,value)

def record(dept,title,kind,url,**fields):
    row = dict(department=department(dept),title=clean(title),kind=kind,
        reference_no='',closing_date='',closing_text='',forecast_date='',publish_date='',
        source_url=url,document_url='',source_ids=[],review_note='',verified_at=NOW.isoformat(timespec='seconds'))
    row.update(fields)
    for field in ['source_url','document_url']:
        # Some official HTML omits escaping '&notice_no'; HTML parsers decode
        # the '&not' prefix as a negation entity. Restore this known query key.
        row[field]=row.get(field,'').replace('¬ice_no=','&notice_no=')
    time_match=re.search(r'(?<!\d)(\d{1,2})\s*[:：]\s*(\d{2})',row.get('closing_text',''))
    if not time_match:time_match=re.search(r'(?<!\d)(\d{1,2})\s*[时時]\s*(\d{2})?',row.get('closing_text',''))
    if row['closing_date'] and time_match:
        hour,minute=int(time_match.group(1)),int(time_match.group(2) or 0)
        if 0<=hour<24 and 0<=minute<60:
            row['closing_at']=row['closing_date']+f'T{hour:02}:{minute:02}:00+08:00'
    if row['closing_date'] and (row['closing_date'] < NOW.date().isoformat() or row.get('closing_at') and datetime.fromisoformat(row['closing_at'])<=NOW):
        row['status']='已截标'
    elif kind=='forecast':
        row['status']='招标预报'
        q=re.search(r'(20\d{2})\s*(?:Q\s*|年第?)([1-4])\s*(?:季|(?=\b|$))',clean(row.get('forecast_date','')),re.I)
        year=re.search(r'20\d{2}',clean(row.get('forecast_date','')))
        month=re.search(r'(20\d{2})年(\d{1,2})月',clean(row.get('forecast_date','')))
        if q and (int(q.group(1)),int(q.group(2)))<(NOW.year,(NOW.month-1)//3+1) or year and int(year.group())<NOW.year or month and (int(month.group(1)),int(month.group(2)))<(NOW.year,NOW.month):
            row['outdated']=True
            row['review_note']='原预报时间已过；需核实是否已招标、延期或取消'
    elif row['closing_date']:
        row['status']='正在招标'
    else:
        row['status']='状态待核实'
    return row

def get_etb(url):
    payload,_=fetch(url)
    root=ET.fromstring(payload)
    nodes=root.findall('.//TenderNoticeRecord')
    if not nodes:
        raise ValueError('XML没有TenderNoticeRecord，需检查源格式')
    out=[]
    for n in nodes:
        text=lambda key:(n.findtext(key) or '').strip()
        r=record(text('ReqDepartmentNameChinese') or text('ReqDepartmentNameEnglish'),
          text('SubjectChinese') or text('SubjectEnglish'),'tender',text('Link') or url,
          reference_no=text('TenderNo'),closing_date=date_value(text('ClosingDateTime')),
          closing_text=text('ClosingDateTime'),publish_date=date_value(text('IssueDateTime')),
          notes=clean(text('ETApplicationChinese')),source_ids=['etb_xml'])
        # A non-inviting source status must never be presented as open.
        if text('Status') and text('Status')!='I':
            r['status']='状态待核实';r['review_note']='中央平台状态代码：'+text('Status')
        out.append(r)
    return out

def get_gld_forecast(url,central=False):
    payload,_=fetch(url); groups=json.loads(payload.decode('utf-8-sig'))
    if not isinstance(groups,list): raise ValueError('采购预报JSON结构发生变化')
    out=[]
    for group in groups:
        name=clean(group.get('title')); dept=name.rpartition(' - ')[0] or name
        for cells in group.get('rows',[]):
            cells=[clean(c) for c in cells]
            if len(cells)<(5 if central else 4) or not cells[0]:continue
            out.append(record(cells[4] if central else dept,cells[0],'forecast',
                'https://www.gld.gov.hk/zh-hk/our-services/procurement/forecast-purchase/',
                forecast_date=cells[3] if central else cells[2],notes=cells[1],document_url=url))
    return out

def get_archsd(url):
    payload,_=fetch(url)
    try:data=json.loads(payload.decode('utf-8-sig'))
    except json.JSONDecodeError:
        # The resource can contain broken quotation marks in long descriptions.
        # Extract only individually well-formed identity/date fields; never
        # attempt to infer the contents of a damaged description string.
        data=[]
        for block in re.split(r'(?=\{\s*"Reference"\s*:)',payload.decode('utf-8-sig')):
            fields={}
            for field in ['Reference','Subject','Closing date/time']:
                m=re.search('"'+re.escape(field)+r'"\s*:\s*("(?:\\.|[^"\\])*")',block)
                if m:fields[field]=json.loads(m.group(1))
            if fields.get('Subject') and fields.get('Closing date/time'):data.append(fields)
        if not data:raise ValueError('建筑署JSON格式异常，无法提取编号、名称及截标日期')
    if not isinstance(data,list):raise ValueError('建筑署JSON结构变化')
    out=[]
    for entry in data:
        if not entry.get('Subject'):continue
        out.append(record('建筑署',entry['Subject'],'tender','https://www.archsd.gov.hk/tc/tenders-notices.html',
            reference_no=clean(entry.get('Reference')),closing_text=clean(entry.get('Closing date/time')),
            closing_date=date_value(entry.get('Closing date/time')),document_url=url))
    return out

def get_hyd_csv(url):
    payload,_=fetch(url)
    rows=list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    out=[]
    for row in rows:
        vals=list(row.values());keys=list(row.keys())
        title=next((v for k,v in row.items() if re.search(r'项目|工程名称|合约名称|顾问研究|Title|Description|Subject',clean(k),re.I)), '')
        ref=next((v for k,v in row.items() if re.search(r'编号|number|reference',clean(k),re.I)), '')
        quarter=next((v for k,v in row.items() if re.search(r'日期|季度|quarter|date|invitation',clean(k),re.I)), '')
        if not title and len(vals)>1:title=max((clean(v) for v in vals), key=len)
        if title:out.append(record('路政署',title,'forecast',url,reference_no=clean(ref),forecast_date=clean(quarter),document_url=url))
    return out

def get_emsd_rss(url):
    payload,_=fetch(url);root=ET.fromstring(payload.decode('utf-8-sig'));out=[]
    for item in root.findall('.//item'):
        link=(item.findtext('link') or '').replace('http:','https:')
        p,final=fetch(link);soup=soup_from(p)
        text=clean(soup.get_text(' ',strip=True))
        match=re.search(r'(?:截标日期|截止日期)\s*[:：]?\s*(.{5,110})',text)
        closing=match.group(1) if match else ''
        ref=clean(item.findtext('title')).split('：')[-1]
        out.append(record('机电工程署',item.findtext('description'),'tender',final,reference_no=ref,
          closing_date=date_value(closing),closing_text=closing,publish_date=date_value(item.findtext('pubDate'))))
    return out

def get_hkma(url):
    payload,_=fetch(url);data=json.loads(payload)
    out=[]
    for item in data['result']['records']:
        out.append(record('香港金融管理局',item['title'],'tender',item['link'],publish_date=item['date'],review_note='API未提供截标日，需查公告'))
    return out

def tender_pdf(url,dept,title=''):
    payload,_=fetch(url);reader=PdfReader(io.BytesIO(payload))
    text=clean('\n'.join((p.extract_text() or '') for p in reader.pages[:6]))
    closing=re.search(r'(?:截止(?:投标)?日期(?:及时间)?|截标(?:日期|时间)?|Closing Date(?: and Time)?)\s*[:：]?\s*(.{5,100})',text,re.I)
    if not closing:
        closing=re.search(r'(?:于|on or before|before|not later than)\s*((?:20\d{2}年\s*\d{1,2}月\s*\d{1,2}日|\d{1,2}\s+[A-Za-z]+\s+20\d{2}).{0,35})',text,re.I)
    ref=re.search(r'(?:招标编号|标书编号|合约编号|Tender Reference|Tender No\.?)\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9 /()._-]{2,45})',text,re.I)
    if not title:
        m=re.search(r'招标承投(.{8,120}?)(?:现|截|招标编号|采购部门)',text)
        title='招标承投'+m.group(1) if m else ''
    if len(title)<8:return []
    ct=closing.group(1) if closing else ''
    eoi=bool(re.search(r'expression of interest|意向征集|意向书',title,re.I))
    row=record(dept,title,'forecast' if eoi else 'tender',url,document_url=url,reference_no=ref.group(1).strip() if ref else '',closing_text=ct,closing_date=date_value(ct),document_verified=True)
    if eoi:
        row['procurement_type']='eoi'
        if row['status']!='已截标':row['status']='意向征集'
        row['forecast_date']='正式招标日期尚未公布'
        if re.search(r'not.{0,80}(?:a tender exercise|tender exercise)',text,re.I):
            row['review_note']='原公告明确本次为意向征集，并非正式招标'
        available=re.search(r'From.{0,40}?on\s+(\d{1,2}\s+[A-Za-z]+\s+20\d{2})',text,re.I)
        if available:row['document_available_from']=date_value(available.group(1))
        service_start=re.search(r'commence.{0,140}?on\s+(\d{1,2}\s+[A-Za-z]+\s+20\d{2})',text,re.I)
        if service_start:row['contract_start']=date_value(service_start.group(1))
        years=re.search(r'for a period of\s*[A-Za-z\s]*\(?(\d+)\)?\s*years?',text,re.I)
        if years:row['contract_years']=int(years.group(1))
        if 'HKeToll' in title and re.search('Toll Collection and Maintenance',title,re.I):
            row['title_zh']='易通行（HKeToll）收费及系统保养服务意向征集'
            row['translation_note']='中文工作译名，原始公告仅提供英文'
        notes=[]
        if row.get('document_available_from'):notes.append('意向征集文件自'+row['document_available_from']+'起可按原公告方式申请领取')
        if row.get('contract_start'):notes.append('原文预计服务开始日期：'+row['contract_start'])
        if row.get('contract_years'):notes.append('预计服务期：'+str(row['contract_years'])+'年')
        row['notes']='；'.join(notes)
    return [row]

def project_link(label,url):
    if not valid_project_title(label):return False
    return len(label)>=12 and bool(re.search(r'^(?:为|更换|供应|提供|采购|设计|建造|Provision|Supply|Replacement|Tender for|Invitation for|Expression of Interest|Request for)|提供.{3,}|系统.{3,}(?:服务|工程)',label,re.I)) and not re.search(r'须知|条款|指引|名单|申请表|报价邀请函|政府采购卡|通知名单|已批准|已批出|中标|award|注意|政府由|未来.*项目',label,re.I)

def valid_project_title(title):
    if re.search(r'局长.*(?:致辞|会见传媒|谈话内容|开场发言)|立法会：.*议案',title):return False
    if re.search(r'^(?:投标申请表格及其他资料|招标增补文件|标书投递及截止日期|Category Code|现时没有招标项目|目前没有项目|邀请提交意向书通知|Tender for the Procurements of New Vessels|土木工程一般规格|工务工程合约的电子采购|工务技术通告|机电工程署出版的技术规格|标准合约文件|标准顾问协议文件)',title,re.I):return False
    if re.search(r'^(?:\(\d\)|为确保成功递交|投标者必须|在递交电子标书|以唯读光碟|批出合约的详情|香港特别行政区政府不一定|是次招标|本局将会就此招标|另外，本局将会|招标文件.{0,15}(?:只有英文|可从))',title):return False
    if len(title)>220 and re.search(r'投标者|电子投标系统|使用手册|实体支票|香港身份证',title):return False
    return True

def parse_official_client_data(soup,dept,url):
    """Read public data files used by the official page, without executing JS."""
    arrays=[];out=[]
    for script in soup.find_all('script'):
        if not script.get('src'):
            for match in re.finditer(r'\b(?:var|let|const)\s+(?:tenderNoticeJSON|consultancyJSON|tenderData)\s*=\s*(\[)',script.get_text()):
                try:
                    value,_=json.JSONDecoder().raw_decode(script.get_text()[match.start(1):])
                    arrays.append(value)
                except json.JSONDecodeError:continue
        elif 'dsd.gov.hk' in url and '-data-compress.js' in script['src']:
            payload,_=fetch(urljoin(url,script['src']))
            match=re.search(rb"=\s*['\"]([A-Za-z0-9+/=]+)['\"]",payload)
            if match:
                value=json.loads(zlib.decompress(base64.b64decode(match.group(1)),-15))
                if isinstance(value,list):arrays.append(value)
    for array in arrays:
        for item in array:
            if 'titleTC' in item and 'tenderOfflineDatetime' in item:
                title=item.get('titleTC') or item.get('titleEN');ct=item.get('tenderOfflineDatetime','')
                out.append(record(dept,title,'tender',urljoin(url,'/tc/'+item.get('detailLink','')),
                  reference_no=item.get('referenceTC') or item.get('id',''),closing_text=ct,closing_date=date_value(ct),publish_date=date_value(item.get('tenderOnlineDatetime'))))
            elif 'reference_no' in item and 'deadline' in item and item.get('title'):
                begin=date_value(item.get('begin_date'))
                if begin and begin>NOW.date().isoformat():continue
                out.append(record(dept,item['title'],'tender',urljoin(url,item.get('link','')),
                  reference_no=clean(item['reference_no']),closing_text=clean(item['deadline']),closing_date=date_value(item['deadline']),publish_date=date_value(item.get('begin_date'))))
    return out

def pdf_forecast(url,dept,page_url):
    payload,_=fetch(url);reader=PdfReader(io.BytesIO(payload));out=[]
    if dept=='机电工程署' and 'Forecast_Invitations_to_Works_Tender' in url:
        plain='\n'.join(p.extract_text() or '' for p in reader.pages)
        pattern=re.compile(r'Contract No\.\s*:\s*(.*?)\s+(20\d{2}\s+Q[1-4])\s*\n(.*?)(?=\nContract No\.\s*:|\Z)',re.S|re.I)
        for match in pattern.finditer(plain):
            ref,quarter,body=match.groups()
            chinese=re.search(r'合[約约](?:編號|编号)\s*:\s*[^\n]*\n(.*?)(?=\n\s*20\d{2}\s*年\s*\n?\s*第\s*[1-4]\s*季)',body,re.S)
            if not chinese:continue
            title=clean(''.join(chinese.group(1).splitlines()))
            title=re.split(r'[（(]新工程合约',title,maxsplit=1)[0].strip()
            ref=clean(ref)
            if ref.lower() in ['tbc','-']:ref=''
            out.append(record(dept,title,'forecast',page_url,reference_no=ref,forecast_date=' '.join(quarter.split()),document_url=url))
        if out:return out
    for page in reader.pages:
        text=(page.extract_text(extraction_mode='layout') or '').replace('\r','')
        lines=text.splitlines()
        works='Contract No. & Title' in text
        if works:
            header=next((l for l in lines if 'Contract No. & Title' in l),'')
            left=min((l.find('Contract No.:') for l in lines if 'Contract No.:' in l),default=-1)
            if left<0:left=min((l.find('Contract No. :') for l in lines if 'Contract No. :' in l),default=-1)
            right=header.find('Probable')
            if left<0 or right<0:continue
        else:
            header=next((l for l in lines if 'Title & Description' in l),'')
            left=0;right=header.find('Type of')
            if right<0:continue
        anchors=[]
        for i,line in enumerate(lines):
            q=re.search(r'(20\d{2})\s*Q([1-4])',line)
            if q and q.start()>=right-3 and clean(line[left:right]) and not re.search('FORECAST|INVITATION|ASSOCIATED|Title &',line):
                start=i
                # A wrapped title may begin before the line containing its quarter.
                while start>0 and lines[start-1].strip() and clean(lines[start-1][left:right]) and not re.search('Department|工程|顾问|顧問|運輸署|署$',clean(lines[start-1])):
                    start-=1
                anchors.append((start,i,f'{q.group(1)} Q{q.group(2)}'))
        for n,(start,at,quarter) in enumerate(anchors):
            end=anchors[n+1][0] if n+1<len(anchors) else len(lines)
            parts=[clean(l[left:right]) for l in lines[start:end] if clean(l[left:right])]
            ref='';title_parts=[]
            chinese_ref=next((j for j,v in enumerate(parts) if re.search('合约编号|合約編號',v)),None)
            if chinese_ref is not None:
                ref=re.split('[:：]',parts[chinese_ref],maxsplit=1)[-1].strip()
                title_parts=parts[chinese_ref+1:]
            else:
                title_parts=parts
                if works:
                    en=next((v for v in parts if 'Contract No.' in v),'')
                    ref=re.sub(r'^.*?Contract No\.?\s*[:：]\s*','',en)
                    title_parts=[v for v in parts if 'Contract No.' not in v]
            # Prefer the source's Chinese project title when present.
            first_zh=next((j for j,v in enumerate(title_parts) if re.match('[\u3400-\u9fff]',v) and not re.match(r'^(?:可行性研|勘查研|设计及建|设计及施工|工程及相关|初步|顾问|合约类别)',v)),None)
            if first_zh is not None:title_parts=title_parts[first_zh:]
            cut=next((j for j,v in enumerate(title_parts) if v.startswith(('(','（')) or re.search(r'^\d+\s*/\s*\d+$|^Note|^注[释釋]',v)),len(title_parts))
            title=''.join(title_parts[:cut]) if first_zh is not None else ' '.join(title_parts[:cut])
            title=clean(title)
            if len(title)<8:continue
            if ref.lower() in ['-','tbc','n/a']:ref=''
            out.append(record(dept,title,'forecast',page_url,reference_no=ref,forecast_date=quarter,document_url=url))
    return out

EMPTY=re.compile(r'(?:目前|现时|现在|本处)?(?:没有|未有|暂无|并无)(?:任何|进行|现正进行|未完结|新的|供招标|可供投标|有效|正在进行的|公开){0,3}(?:招标|采购|投标)|no (?:outstanding|current|open) tender|no tenders? (?:are |is )?(?:available|invited)|暂无进行招标',re.I)
EXPLICIT_EMPTY=re.compile(r'目前没有项目|目前没有未来的(?:非)?资讯科技项目|现时尚未有最新的.{0,20}预报可以公布|没有任何.{0,45}招标项目进行|(?:There is|There.s) no outstanding invitation at the moment',re.I)
TITLE_HEADERS=re.compile(r'^(?:项目|内容|简介)$|项目名称|合约名称|工程名称|招标项目|投标项目|招标事项|招标内容|采购项目|标书项目|招标详情|招标说明|项目详情|服务名称|工程项目|title|subject|description|particulars|details',re.I)
REF_HEADERS=re.compile(r'编号|标书号码|合约号码|contract no|tender no|reference|ref\.',re.I)
CLOSE_HEADERS=re.compile(r'截标|截止|closing|deadline|递交.*日期|提交.*日期',re.I)
FORECAST_HEADERS=re.compile(r'预计|暂定|预定|季度|quarter|tentative|forecast|invitation|预计招标',re.I)
REF_PATTERN=re.compile(r'(?<!\w)(?:\d{3,5}EM\d{2}[TW]|(?:CE|HY|DC|ND|NE|GE|ST|YL|CV|KL|TW|TC|SS|AS|RF|AP|TD)[ /（(\w.-]{0,18}[/-]\d{2,4}[\w()/ .-]{0,12})(?!\w)',re.I)

def safe_links(node,base):
    out=[]
    for a in node.select('a[href]'):
        href=a.get('href','')
        if href.lower().startswith('javascript:'):
            match=re.search(r'(?:openWindow|window.open)\(\s*[\'"]([^\'"]+)',href,re.I)
            if not match:continue
            href=match.group(1)
        url=urljoin(base,href)
        if urlparse(url).scheme in ('http','https'):
            out.append((clean(a.get_text(' ',strip=True)),url))
    return out

def parse_tables_page(soup,dept,kind,url):
    out=[]
    if dept=='食物环境卫生署':
        last_date=''
        for tr in soup.find_all('tr'):
            vals=[clean(td.get_text(' ',strip=True)) for td in tr.find_all('td',recursive=False)]
            if len(vals)<3:continue
            if date_value(vals[0]):last_date=vals.pop(0)
            if len(vals)==3 and re.search(r'FEHQ\s*\d+',vals[1],re.I) and last_date:
                links=safe_links(tr,url)
                out.append(record(dept,vals[2],kind,links[0][1] if links else url,reference_no=vals[1],closing_text=last_date,closing_date=date_value(last_date)))
        if out:return out
    if dept=='康乐及文化事务署' and 'Tender.do' in url:
        for tr in soup.find_all('tr'):
            cells=tr.find_all('td',recursive=False)
            if len(cells)==3:
                ct=clean(cells[0].get_text());cd=date_value(ct)
                if not cd:continue
                links=safe_links(tr,url)
                out.append(record(dept,cells[1].get_text(' ',strip=True),kind,links[0][1] if links else url,
                  reference_no=clean(cells[2].get_text()),closing_date=cd,closing_text=ct))
        if out:return out
    if dept=='廉政公署':
        for tr in soup.find_all('tr'):
            cells=tr.find_all(['td','th'],recursive=False)
            if len(cells)==2 and '即将进行' in clean(cells[0].get_text()):
                title=clean(cells[1].get_text(' ',strip=True))
                if len(title)>7:out.append(record(dept,title,'forecast',url,forecast_date='官方未注明'))
        if out:return out
    # CEDD uses "Details" for the reference column in its bilingual table.
    # An explicit table adapter avoids mistaking the contract number for title.
    for table in soup.select('table.tenderTbl'):
        for tr in table.find_all('tr'):
            cells=tr.find_all(['td','th'],recursive=False)
            if len(cells)<3 or cells[0].name=='th':continue
            first=clean(cells[0].get_text(' ',strip=True))
            if not re.match(r'^(?:Contract No|合约编号)',first,re.I):continue
            ref=re.sub(r'^(?:Contract No\.?|合约编号)\s*[:：]\s*','',first,flags=re.I)
            title=clean(cells[1].get_text(' ',strip=True));ct=clean(cells[2].get_text(' ',strip=True))
            links=safe_links(cells[1],url)
            out.append(record(dept,title,kind,url,reference_no=ref,closing_text=ct,closing_date=date_value(ct),document_url=links[0][1] if links else ''))
    if out:return out
    for table in soup.find_all('table'):
        trs=table.find_all('tr')
        headers=[]; header_at=-1
        for i,tr in enumerate(trs[:8]):
            vals=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
            joined=' '.join(vals)
            if (any(TITLE_HEADERS.search(v) for v in vals) or REF_HEADERS.search(joined)) and (CLOSE_HEADERS.search(joined) or FORECAST_HEADERS.search(joined)):
                headers=vals; header_at=i;break
        if header_at<0: continue
        title_idx=next((i for i,h in enumerate(headers) if TITLE_HEADERS.search(h)),None)
        ref_idx=next((i for i,h in enumerate(headers) if REF_HEADERS.search(h)),None)
        close_idx=next((i for i,h in enumerate(headers) if CLOSE_HEADERS.search(h)),None)
        forecast_idx=next((i for i,h in enumerate(headers) if FORECAST_HEADERS.search(h) and i!=title_idx),None)
        for tr in trs[header_at+1:]:
            cells=tr.find_all(['td','th'],recursive=False)
            vals=[clean(c.get_text(' ',strip=True)) for c in cells]
            if len(vals)<2:continue
            val=lambda idx: vals[idx] if idx is not None and idx<len(vals) else ''
            title=val(title_idx)
            if not title or len(title)<7 or TITLE_HEADERS.fullmatch(title):continue
            if any(re.search(r'批出日期|承兑函|Award Date|承办商',h,re.I) for h in headers):continue
            if re.fullmatch(r'(?:\d+\.?|N/?A|不适用|无|没有)',title,re.I):continue
            ref=val(ref_idx);ct=val(close_idx);ft=val(forecast_idx)
            if '取消' in ' '.join(vals):continue
            links=safe_links(tr,url)
            # A header has been recognized; retaining missing dates as uncertain is deliberate.
            doc=next((u for label,u in links if re.search(r'\.pdf(?:\?|$)',u,re.I)), '')
            detail=next((u for label,u in links if not re.search(r'\.pdf(?:\?|$)',u,re.I)),url)
            out.append(record(dept,title,kind,detail,reference_no=ref,closing_text=ct,
              closing_date=date_value(ct),forecast_date=ft if kind=='forecast' else '',document_url=doc))
    return out

def parse_detail(soup,dept,kind,url):
    if dept=='土木工程拓展署' and '/consultancy-agreements/' in url:
        sections={}
        main=soup.select_one('#content') or soup
        for heading in main.find_all(['h2','h3']):
            values=[]
            for sibling in heading.next_siblings:
                if getattr(sibling,'name',None) in ['h2','h3']:break
                values.append(sibling.get_text(' ',strip=True) if hasattr(sibling,'get_text') else str(sibling))
            sections[clean(heading.get_text())]=clean(' '.join(values))
        title=sections.get('Agreement Title') or sections.get('顾问合约名称')
        ref=sections.get('Consultancy Agreement No.') or sections.get('顾问合约编号')
        ct=sections.get('Closing Date and Time') or sections.get('截止日期及时间')
        if title and ref and ct and date_value(ct):
            # These are consultancy proposal invitations, not construction contracts.
            ct=re.sub(r'12:00 noon','12:00',ct,flags=re.I)
            row=record(dept,title,'tender',url,reference_no=ref,closing_text=ct,closing_date=date_value(ct),
                publish_date=date_value(sections.get('Invitation Date','')),procurement_type='consultancy_proposal',
                eligibility_note=sections.get('Consultants Invited',''),notes=sections.get('Details of Consultancy',''))
            if re.search(r'Group 3',row['eligibility_note'],re.I):
                row['eligibility_summary']='顾问服务建议书邀请；须核对工程及有关顾问遴选委员会（EACSB）相应服务类别第3组及受邀名单，并非任何公司均可直接投标。'
            return [row]
    pairs={}
    for tr in soup.find_all('tr'):
        cells=tr.find_all(['td','th'],recursive=False)
        if len(cells) in (2,3):
            label=clean(cells[0].get_text(' ',strip=True)).rstrip('：:')
            value=clean(cells[-1].get_text(' ',strip=True))
            if len(label)<35:pairs[label]=value
    title=next((v for k,v in pairs.items() if re.fullmatch(r'招标项目|投标项目|项目|Subject|Title',k,re.I)), '')
    ref=next((v for k,v in pairs.items() if REF_HEADERS.search(k)), '')
    closing=next((v for k,v in pairs.items() if CLOSE_HEADERS.search(k)), '')
    if title and ref and closing and len(title)>=7:
        return [record(dept,title,kind,url,reference_no=ref,closing_text=closing,closing_date=date_value(closing))]
    main=soup.select_one('main, #content, #main-content, .main-content, #contentArea') or soup
    text=clean(main.get_text(' ',strip=True))
    close=re.search(r'(?:截标日期|截止日期|Closing Date(?: and Time)?|Tender Closing Date)\s*[:：]?\s*(.{8,140})',text,re.I)
    ref=re.search(r'(?:招标编号|标书编号|合约编号|Tender Reference|Tender No\.?|Contract No\.?)\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9 /()._-]{2,60})',text,re.I)
    # Detail pages need both a genuine tender identifier and a closing date label.
    if kind!='tender' or not close or not ref:return []
    title_node=main.select_one('h1') or soup.select_one('h1') or soup.select_one('title')
    title=clean(title_node.get_text()) if title_node else ''
    if len(title)<8 or title in ['招标公告','招标','Tender Notices']:return []
    ct=close.group(1);cd=date_value(ct)
    if not cd:return []
    return [record(dept,title,kind,url,reference_no=ref.group(1).strip(),closing_text=ct,closing_date=cd)]

def crawl_source(spec):
    started=time.monotonic();sid=spec['id'];url=spec['url'];kind=spec['kind'];dept=spec.get('department','全政府')
    report=dict(spec,checked_at=NOW.isoformat(timespec='seconds'),status='pending',count=0,documents=[],errors=[],pages=0)
    items=[]
    try:
        mode=spec.get('parser','html')
        if mode=='etb':items=get_etb(url)
        elif mode=='gld_bd':items=get_gld_forecast(url)
        elif mode=='gld_central':items=get_gld_forecast(url,True)
        elif mode=='archsd':items=get_archsd(url)
        elif mode=='hyd_csv':items=get_hyd_csv(url)
        elif mode=='emsd_rss':items=get_emsd_rss(url)
        elif mode=='hkma':items=get_hkma(url)
        else:
            queue=[(url,0)];visited=set();empty_found=False;link_titles={}
            while queue and len(visited)<spec.get('max_pages',10):
                current,depth=queue.pop(0)
                if current in visited:continue
                visited.add(current)
                try:
                    payload,final=fetch(current)
                    if payload[:4]==b'%PDF':
                        report['documents'].append({'name':'官方项目文件','url':current})
                        if kind=='tender':items.extend(tender_pdf(current,dept))
                        continue
                    soup=soup_from(payload)
                    if b'CF_APP_WAF' in payload or b'waf-nc-h5-mask' in payload:
                        raise RuntimeError('官方页面触发访问验证，本次无法采集；未尝试绕过验证')
                    report['pages']+=1
                    client_records=parse_official_client_data(soup,dept,final) if kind=='tender' else []
                    for tag in soup.select('nav,header,footer,script,style,.breadcrumb'):tag.decompose()
                    main=soup.select_one('main,#content,#main-content,.main-content,#contentArea') or soup
                    text=clean(main.get_text(' ',strip=True))
                    if EMPTY.search(text) or EXPLICIT_EMPTY.search(text):empty_found=True
                    parsed=client_records or parse_tables_page(soup,dept,kind,final)
                    if not parsed:parsed=parse_detail(soup,dept,kind,final)
                    for row in parsed:
                        label=link_titles.get(current,'')
                        if len(label)>=10:
                            row['title_aliases']=sorted(set(row.get('title_aliases',[])+[row['title'],label]))
                            if len(re.findall(r'[\u4e00-\u9fff]',label))>=3:row['title_zh']=label
                    items.extend(parsed)
                    links=safe_links(main,final)
                    for label,link in links:
                        if len(label)>=10 and re.search(r'/index-id-\d+',link):link_titles[link]=label
                    # Some CEDD Chinese detail pages contain only a title, with
                    # no link or notice saying that the actual details are English.
                    if not parsed and dept=='土木工程拓展署' and '/tc/' in final and re.search(r'/index-id-\d+',final):
                        alt=final.replace('/tc/','/eng/')
                        label=link_titles.get(current) or clean((main.select_one('h2') or main).get_text(' ',strip=True))
                        link_titles[alt]=label
                        if alt not in visited:queue.append((alt,depth+1))
                    if re.search(r'暂时只有英文|不提供中文版本|只以英文编制|只提供英文',text):
                        alt=next((u for label,u in links if re.search('英文版本|English version',label,re.I)),None)
                        if not alt:alt=final.replace('/tc/','/eng/' if 'cedd.gov.hk' in final else '/en/').replace('/TC/','/EN/')
                        if alt!=final and alt not in visited:
                            link_titles[alt]=link_titles.get(current,'')
                            queue.append((alt,depth+1))
                    candidates=[]
                    for label,link in links:
                        combined=label+' '+link
                        if not parsed and kind=='tender' and project_link(label,link) and not re.search('award|archive',link,re.I):
                            # Capture the named official notice even if its detail parser
                            # has not yet found a deadline. It remains visibly uncertain.
                            items.append(record(dept,label,'tender',link,document_url=link if '.pdf' in link.lower() else '',review_note='需从原公告核实截标日期'))
                        if re.search(r'\.pdf(?:\?|$)|\.xlsx?(?:\?|$)',link,re.I):
                            if re.search(r'forecast|预报|采购|招标|tender|consult|works|20(?:26|27)',combined,re.I) and not re.search(r'notes|指引|条款|须知|data.?dict',combined,re.I):
                                report['documents'].append({'name':label or '官方文件','url':link})
                            if not parsed and kind=='tender' and project_link(label,link) and '.pdf' in link.lower():
                                try:items.extend(tender_pdf(link,dept,label))
                                except Exception as exc:report['errors'].append({'url':link,'error':str(exc)[:200]})
                            continue
                        link=link.split('#')[0]
                        if urlparse(link).hostname!=urlparse(final).hostname or depth>=2:continue
                        if re.search(r'archive|award|批出|历史|过往|closed|past|login|登入|email|javascript',combined,re.I):continue
                        if kind=='tender':
                            good=project_link(label,link) or re.search(r'招标公告|投标邀请|现正招标|公开招标|tender.?notice|invitation|prequalifications|tender_[a-z0-9]|\d{4}EM\d|tender_con|tender_it|提供服务|供应货品|合约$|工程合约|顾问合约|/progress\.|non-it|general\.htm|/others\.html|tender/transport/notice|tendernotices|/tenders/details/|tn-ps|tn-roadside|tn-wc\.html|tn-consultancy\.html|tn-s[gs]\.html|WorkContracts|ConsultancyAgreements|Current_Tenders|notice_tender|英文网页|此页|tender_agr|tender_fis|tender_cou|tender_qua|tender_con',combined,re.I)
                            if re.search(r'forecast|预报',combined,re.I):good=False
                        else:
                            good=re.search(r'forecast|预报|采购预览',combined,re.I)
                        if kind=='tender' and re.search(r'/tenders?[-_ /]+notices?/|/works\.html|/consultancies\.html',link,re.I):good=True
                        if not parsed and good and link not in visited:
                            candidates.append((link,depth+1))
                    queue.extend(candidates[:8])
                except Exception as exc:
                    report['errors'].append({'url':current,'error':str(exc)[:250]})
            if kind=='forecast':
                documents=list({d['url']:d for d in report['documents']}.values())
                for document in documents[:5]:
                    if not re.search(r'\.pdf(?:\?|$)',document['url'],re.I):continue
                    try:
                        found=pdf_forecast(document['url'],dept,url);items.extend(found)
                        if not found:
                            p,_=fetch(document['url'])
                            first=clean(PdfReader(io.BytesIO(p)).pages[0].extract_text() or '')
                            if re.search('没有研究预报|没有.*预报|No Forecast of',first,re.I):empty_found=True
                    except Exception as exc:report['errors'].append({'url':document['url'],'error':str(exc)[:200]})
            report['status']='parsed' if items else 'empty' if empty_found else 'documents' if report['documents'] else 'unparsed'
            if not report['pages'] and report['errors']:report['status']='failed'
            if report['errors'] and items:report['status']='partial'
        if mode!='html':report['status']='parsed' if items else 'empty'
    except Exception as exc:
        report['status']='failed';report['errors'].append({'url':url,'error':str(exc)[:350]})
    original_count=len(items)
    items=deduplicate(items)
    report['discarded_non_projects']=original_count-len(items)
    if original_count and not items and report['status'] in ['parsed','partial']:
        report['status']='unparsed'
        report['errors'].append({'url':url,'error':'只识别到栏目、须知或新闻，未确认真实项目记录'})
    items=deduplicate(preserve_source_state(sid,items,report))
    for row in items:
        row['source_ids']=list(set(row.get('source_ids',[])+[sid]))
    report['count']=len(items);report['elapsed_seconds']=round(time.monotonic()-started,1)
    if items and all(r.get('outdated') or r['status']=='已截标' for r in items):report['historical_only']=True
    report['documents']=list({d['url']:d for d in report['documents']}.values())
    with LOCK:print(f"[{report['status']}] {sid}: {len(items)}",flush=True)
    return items,report

def source_specs():
    links=json.loads((ROOT/'dist/links.json').read_text())['items']; specs=[]
    specs += [
      dict(id='etb_xml',name='中央电子投标箱（pcms2）',department='全政府',kind='tender',parser='etb',url='https://pcms2.gld.gov.hk/iportal/TenderNotice.xml'),
      dict(id='gld_bd_json',name='全政府货品及一般服务采购预报',department='全政府',kind='forecast',parser='gld_bd',url='https://www.gld.gov.hk/assets/gld/download-files/forecast-of-major-purchases/Major_Purchases_by_BDs-zh-hk.json'),
      dict(id='gld_central_json',name='物流署集中采购预报',department='全政府',kind='forecast',parser='gld_central',url='https://www.gld.gov.hk/assets/gld/download-files/forecast-of-major-purchases/Major_Purchases_by_GLD-zh-hk.json'),
      dict(id='archsd_json',name='建筑署工程招标开放数据',department='建筑署',kind='tender',parser='archsd',url='https://www.archsd.gov.hk/tc/psi/tender.json'),
      dict(id='emsd_rss',name='机电署最新招标订阅源',department='机电工程署',kind='tender',parser='emsd_rss',url='https://www.emsd.gov.hk/filemanager/tendernotice/tc/tender_notices.xml'),
      dict(id='hkma_api',name='金管局官方招标API',department='香港金融管理局',kind='tender',parser='hkma',url='https://api.hkma.gov.hk/public/tender-invitations?lang=tc&segment=tender'),
    ]
    for what in ['tender','consultancies']:
        specs.append(dict(id='hyd_csv_'+what,name='路政署'+('工程' if what=='tender' else '顾问')+'预报开放数据',department='路政署',kind='forecast',parser='hyd_csv',url=f'https://www.hyd.gov.hk/datagovhk/TAF/resource/Forecast_of_{what}_tc.csv'))
    for l in links:
        if l['category'] not in ['部门招标','政策局及机构','招标预报']:continue
        if l['category']=='招标预报' and ('全政府' in l['name'] or '政府物流' in l['name'] or '各政策局' in l['name']):continue
        specs.append(dict(id='directory_'+str(l['id']),name=l['name'],department=department(l['name']),kind='forecast' if l['category']=='招标预报' else 'tender',parser='html',url=l['url']))
    corrections={
      '运输署':'https://www.td.gov.hk/tc/tender_notices/tender_notices/',
      '土木工程拓展署':'https://www.cedd.gov.hk/tc/tender-notices/contracts/tender-notices/index.html',
      '路政署':'https://www.hyd.gov.hk/tc/tender_notices/contracts/prequalifications_and_tender_notices/index.html',
      '机电工程署':'https://www.emsd.gov.hk/tc/tenders_contracts_and_consultancies/tender_notices/tender_notices/index.html',
      '渠务署':'https://www.dsd.gov.hk/TC/Tender_Notices/TenderNotices/index.html',
      '海事处':'https://www.mardep.gov.hk/tc/tender/government-new-vessels/index.html',
      '土地注册处':'https://www.landreg.gov.hk/tc/tender/progress.htm',
      '运输及物流局':'https://www.tlb.gov.hk/tc/service/tender/transport/notice.html',
      '房屋局':'https://www.hb.gov.hk/tc/service/tender/tendernotices.html',
      '渠务署':'https://www.dsd.gov.hk/TC/Tender_Notices/Current_Tenders/index.html',
      '康乐及文化事务署':'https://www.lcsd.gov.hk/clpss/tc/webApp/Tender.do',
      '香港天文台':'https://www.hko.gov.hk/en/tender/notice_tender.html',
      '建筑署':'https://www.archsd.gov.hk/tc/tenders-notices/works.html',
    }
    for s in specs:
        if s['kind']=='tender' and s['name'] in corrections:s['url']=corrections[s['name']]
    extras=[
      ('dsd_consult_tenders','渠务署','tender','https://www.dsd.gov.hk/TC/Tender_Notices/Invitation_for_Expression_of_Interest_for_Consultancy_Agreements/index.html'),
      ('fehd_forecast','食物环境卫生署','forecast','https://www.fehd.gov.hk/tc_chi/tenders/forecast1.html'),
      ('landreg_forecast','土地注册处','forecast','https://www.landreg.gov.hk/tc/tender/projects.htm'),
      ('landreg_nonit_forecast','土地注册处','forecast','https://www.landreg.gov.hk/tc/tender/non-it-projects.htm'),
      ('education_works_forecast','教育局','forecast','https://www.edb.gov.hk/tc/public-admin/tender-notices/works/forecast-works/index.html'),
      ('lands_works_forecast','地政总署','forecast','https://www.landsd.gov.hk/tc/whats-new/on-going-tenders/tender-goods-services-consultancies/tn-wc-forecast.html'),
      ('lands_consult_forecast','地政总署','forecast','https://www.landsd.gov.hk/tc/whats-new/on-going-tenders/tender-goods-services-consultancies/tn-consultancy-forecast.html'),
      ('td_consult_tenders','运输署','tender','https://www.td.gov.hk/tc/tender_notices/notices_of_inviting_expression_of_interest/index.html'),
      ('td_consult_proposals','运输署','tender','https://www.td.gov.hk/tc/tender_notices/invitation_for_technical_and_fee_proposal/index.html'),
      ('cedd_consult_tenders','土木工程拓展署','tender','https://www.cedd.gov.hk/tc/tender-notices/consultancy-agreements/invitation-for-expression-of-interest/index.html'),
      ('cedd_consult_proposals','土木工程拓展署','tender','https://www.cedd.gov.hk/tc/tender-notices/consultancy-agreements/invitation-for-technical-and-fee-proposals/index.html'),
      ('hyd_consult_tenders','路政署','tender','https://www.hyd.gov.hk/tc/tender_notices/consultancies/expression_of_interest/index.html'),
      ('hyd_consult_proposals','路政署','tender','https://www.hyd.gov.hk/tc/tender_notices/consultancies/technical_and_fee_proposal/index.html'),
    ]
    for sid,dep,kind,url in extras:
        specs.append(dict(id=sid,name=dep+('补充采购预报' if kind=='forecast' else '顾问服务邀请'),department=dep,kind=kind,parser='html',url=url))
        if sid.startswith('cedd_consult'):specs[-1]['max_pages']=40
    # Compare the supplied list against the government's own cross-department
    # tender directory. New departments get registered without hand editing.
    official_directory='https://www.fstb.gov.hk/tc/treasury/gov_procurement/tender-notices.htm'
    try:
        payload,base=fetch(official_directory)
        known={department(s['department']) for s in specs}
        for label,url in safe_links(soup_from(payload),base):
            dep=department(label)
            if dep in known or not re.search(r'(?:署|局|处|办公室|委员会秘书处|服务队)$',dep) or not urlparse(url).hostname.endswith('.gov.hk'):continue
            if not re.search(r'tender|quotation',url,re.I):continue
            known.add(dep)
            specs.append(dict(id='fstb_'+hashlib.sha256(dep.encode()).hexdigest()[:10],name=dep,department=dep,kind='tender',parser='html',url=url.replace('http:','https:')))
    except Exception as exc:
        print('政府部门总目录未能刷新：'+str(exc),file=sys.stderr)
    return specs

def preserve_source_state(sid,items,report):
    """Keep recoverable source history across cloud runs; do not relabel it as fresh."""
    STATE.mkdir(parents=True,exist_ok=True)
    checkpoint=STATE/(sid+'.json')
    previous={}
    if checkpoint.exists():
        try:previous=json.loads(checkpoint.read_text(encoding='utf-8'))
        except (OSError,json.JSONDecodeError):pass
    for row in items:row['source_ids']=sorted(set(row.get('source_ids',[])+[sid]))
    if report['status'] in ['parsed','empty']:
        # An explicit empty statement is a valid change. A broken page is not.
        payload={'checked_at':report['checked_at'],'items':deduplicate(items)}
        atomic_json(checkpoint,payload)
    elif not items and previous and report['status'] in ['failed','unparsed','documents','partial']:
        report['previous_success_at']=previous['checked_at']
        for original in previous.get('items',[]):
            row=dict(original)
            if row.get('closing_date') and row['closing_date']<NOW.date().isoformat():
                row['status']='已截标'
            else:row['status']='状态待核实'
            row['stale']=True
            row['last_success_at']=previous['checked_at']
            row['review_note']='本次来源未能完整提取，保留上次成功记录；当前状态待核实'
            items.append(row)
    return items

def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)

def deduplicate(rows):
    from project_identity import apply_identity,normalized_title
    rows=[apply_identity(dict(row)) for row in rows]
    for row in rows:row['department']=department(row['department'])
    # Bilingual labels from the same official notice form verified aliases.
    # Only an unambiguous exact alias can give a reference to an unnumbered
    # forecast. Similar wording alone must not merge different procurements.
    aliases={}
    for row in rows:
        if row.get('reference_no'):
            for label in [row['title']]+row.get('title_aliases',[]):
                aliases.setdefault((row['department'],normalized_title(label)),set()).add(row['reference_no'])
    for row in rows:
        if not row.get('reference_no'):
            refs=aliases.get((row['department'],normalized_title(row['title'])),set())
            if len(refs)==1:row['reference_no']=next(iter(refs))
    merged={};titles={}
    for row in sorted(rows,key=lambda r:(not bool(r.get('reference_no')),not bool(r.get('closing_date')),bool(r.get('stale')),
            'etb_xml' not in r.get('source_ids',[]),r.get('department',''),r.get('title',''),r.get('source_url',''))):
        row['reference_no']=re.sub(r'\(\s*[\d.]+\s*(?:KB|MB)\s*\)','',clean(row['reference_no']),flags=re.I).strip()
        row['reference_no']=re.sub(r'^(?:合约编号|招标编号|Contract No\.?)[：: ]*','',row['reference_no'],flags=re.I)
        if not valid_project_title(row['title']):continue
        ref=re.sub(r'\s+','',row['reference_no']).upper()
        # A shared reference indicates a notice; forecast without a ref is matched only by exact normalized title.
        title=normalized_title(row['title'])
        key=(row['department'],ref or title)
        if not row['title'] or len(row['title'])<7:continue
        if row['status']=='已截标' and row['closing_date']<f'{NOW.year}-01-01':continue
        if not ref and (row['department'],title) in titles:key=titles[(row['department'],title)]
        if key in merged:
            old=merged[key];ids=sorted(set(old['source_ids']+row['source_ids']))
            conflict=old['kind']==row['kind']=='tender' and old.get('closing_date') and row.get('closing_date') and old['closing_date']!=row['closing_date']
            if old['kind']=='forecast' and row['kind']=='tender' and row.get('closing_date') or row.get('document_verified') and not old.get('document_verified') or not old.get('document_verified') and row['kind']=='tender' and (old['kind']=='forecast' or (row['closing_date'] and not old['closing_date'])):
                old,row=row,old
            old['title_aliases']=sorted(set(old.get('title_aliases',[])+row.get('title_aliases',[])+[old['title'],row['title']]))
            if old['kind']=='tender' and row['kind']=='forecast':
                old['previous_forecast_date']=row.get('forecast_date','')
                old['stage_note']='已找到正式邀请公告，旧预报合并至此，不再作为独立预报展示'
            for field in ['document_url','closing_date','closing_text','closing_at','forecast_date','reference_no','publish_date','title_zh','eligibility_note','eligibility_summary','procurement_type','notes']:
                if not old.get(field):old[field]=row.get(field,'')
            old['source_ids']=ids
            if conflict:
                old['status']='状态待核实'
                old['review_note']='不同官方来源的截标日期不一致，需核对最新修订公告'
                old['deadline_options']=sorted(set(old.get('deadline_options',[])+[old['closing_date'],row['closing_date']]))
            merged[key]=old
        else:merged[key]=row
        titles[(row['department'],title)]=key
    for key,row in merged.items():
        row['id']=hashlib.sha256('|'.join(key).encode()).hexdigest()[:18]
        if not row.get('title_zh'):
            chinese=next((label for label in row.get('title_aliases',[]) if len(re.findall(r'[\u4e00-\u9fff]',label))>=3),'')
            if chinese:row['title_zh']=chinese
    return sorted(merged.values(),key=lambda r:(r['department'],r['kind'],r['reference_no'],r['title']))

def main():
    global CACHE_MAX_AGE,NOW
    NOW=datetime.now(ZoneInfo('Asia/Hong_Kong'))
    parser=argparse.ArgumentParser();parser.add_argument('--only',default='');parser.add_argument('--workers',type=int,default=8);parser.add_argument('--fresh',action='store_true')
    args=parser.parse_args()
    if args.fresh:CACHE_MAX_AGE=0
    specs=source_specs()
    if args.only:specs=[s for s in specs if re.search(args.only,s['id']+' '+s['name'])]
    CACHE.mkdir(exist_ok=True)
    previous_path=ROOT/'dist/projects.json'
    previous=json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
    rows=[];reports=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(crawl_source,s) for s in specs]
        for future in as_completed(futures):
            batch,report=future.result();rows.extend(batch);reports.append(report)
    rows=deduplicate(rows)
    departments=sorted(set([department(s['department']) for s in specs if s['department']!='全政府']+[r['department'] for r in rows]))
    coverage=[]
    for dep in departments:
        sources=[s for s in reports if department(s['department'])==dep]
        selected=[r for r in rows if r['department']==dep]
        coverage.append(dict(name=dep,open=sum(r['status']=='正在招标' for r in selected),forecast=sum(r['kind']=='forecast' and not r.get('outdated') and r['status']!='已截标' for r in selected),
          closed=sum(r['status']=='已截标' for r in selected),uncertain=sum(r['status']=='状态待核实' for r in selected),
          sources=[s['id'] for s in sources],needs_review=any(s['status'] in ['failed','unparsed','documents','partial'] for s in sources)))
    from snapshot_tools import enrich_changes,validate_snapshot
    rows,changes=enrich_changes(rows,previous,NOW)
    data=dict(updated_at=NOW.isoformat(timespec='seconds'),scoring_enabled=False,
      scope='按已登记官方来源采集；部门接入情况可查，未解析或失败不表示没有项目。',
      stats=dict(records=len(rows),open=sum(r['status']=='正在招标' for r in rows),forecast=sum(r['kind']=='forecast' and not r.get('outdated') and r['status']!='已截标' for r in rows),departments=len(departments),
      sources=len(reports),source_status=dict(Counter(s['status'] for s in reports))),
      departments=coverage,sources=sorted(reports,key=lambda s:s['id']),projects=rows,changes=changes)
    import os
    on_github=os.environ.get('GITHUB_ACTIONS')=='true'
    data['automation']={'provider':'GitHub Actions','active':on_github,'timezone':'Asia/Hong_Kong','schedule':'每天08:00启动采集',
       'run_url':f"{os.environ.get('GITHUB_SERVER_URL','https://github.com')}/{os.environ.get('GITHUB_REPOSITORY','')}/actions/runs/{os.environ.get('GITHUB_RUN_ID','')}" if on_github else ''}
    data['health']=validate_snapshot(data,production=not bool(args.only))
    from company_scope import annotate
    annotate(data)
    if args.only:
        atomic_json(ROOT/'dist/projects.preview.json',data)
        print('单源检查已写入 projects.preview.json，主项目库未被覆盖。')
        return
    if not data['health']['publish_allowed']:
        atomic_json(ROOT/'state/failed-snapshot.json',data)
        print('质量检查未通过，原项目清单未被覆盖：'+'；'.join(data['health']['errors']),file=sys.stderr)
        return 2
    atomic_json(ROOT/'dist/projects.json',data)
    atomic_json(ROOT/'dist/changes.json',{'updated_at':data['updated_at'],**changes,
      'new':[r for r in rows if r['change']=='new'],'updated':[r for r in rows if r['change']=='updated']})
    fields=['department','status','reference_no','title','publish_date','closing_date','forecast_date','source_url','document_url','review_note']
    with (ROOT/'dist/projects.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    audit=['# 部门项目采集核对','',f'本次运行：{NOW.isoformat(timespec="seconds")}','',
      f'登记 {len(departments)} 个部门／机构，检查 {len(reports)} 个来源。',
      f'取得 {data["stats"]["open"]} 条尚未截标记录、{data["stats"]["forecast"]} 条预报时间未过的采购预报。','',
      '分数筛选已关闭。未提取或失败不表示部门没有项目；已提取也不等于已验证全部页码。','',
      '| 部门 | 正在招标 | 预报时间未过 | 待核实 | 来源需补齐 |','|---|---:|---:|---:|---|']
    audit.extend(f'| {d["name"]} | {d["open"]} | {d["forecast"]} | {d["uncertain"]} | {"是" if d["needs_review"] else "查看来源记录"} |' for d in coverage)
    audit.extend(['','## 需继续处理的来源',''])
    audit.extend(f'- {s["name"]}：{s["status"]} — {s["url"]}' for s in reports if s['status'] in ['failed','unparsed','documents','partial'])
    (ROOT/'采集核对报告.md').write_text('\n'.join(audit)+'\n',encoding='utf-8')
    atomic_json(ROOT/'state/last-run.json',{'updated_at':data['updated_at'],'stats':data['stats'],'health':data['health'],'changes':changes})
    print(f"质量检查：{data['health']['status']}；新增 {changes['new_count']}，变化 {changes['updated_count']}")
    print(json.dumps(data['stats'],ensure_ascii=False,indent=2))

if __name__=='__main__':sys.exit(main() or 0)
