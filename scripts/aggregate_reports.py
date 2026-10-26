"""Calendar roll-ups retain evidence and status histories, not concatenated prose."""
import argparse
import json
import re
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def bounds(kind,key):
    if kind=='monthly':
        year,month=map(int,key.split('-'));start=date(year,month,1)
        end=date(year+int(month==12),1 if month==12 else month+1,1)
    elif kind=='quarterly':
        year,q=map(int,key.replace('Q','').split('-'));month=(q-1)*3+1
        if q not in range(1,5):raise ValueError('季度错误')
        start=date(year,month,1);end=date(year+int(q==4),1 if q==4 else month+3,1)
    else:
        year=int(key);start=date(year,1,1);end=date(year+1,1,1)
    return start,end

def aggregate(reports,kind,key):
    start,end=bounds(kind,key);projects={};news={};included=[]
    for report in reports:
        verified=date.fromisoformat(report['verified_at'])
        if start<=verified<end:
            included.append(report['publication_date'])
            for row in report['projects']:
                identity=row['department']+'|'+(row['reference_no'] if '未列' not in row['reference_no'] else re.sub(r'\W','',row['title']))
                item=projects.setdefault(identity,{'department':row['department'],'reference_no':row['reference_no'],'title':row['title'],'snapshots':[]})
                item['snapshots'].append({'as_of':report['verified_at'],**row})
        for row in report.get('news',[]):
            if start<=date.fromisoformat(row['published_at'])<end:news[row['source_url']]=row
    return {'kind':kind,'period':key,'period_start':start.isoformat(),'period_end_exclusive':end.isoformat(),
        'included_report_dates':sorted(set(included)),
        'coverage_note':'仅汇总已留存且核查日期落在本期的重点项目快照，以及发布日期落在本期的新闻；不代表全市场或完整自然期覆盖。跨期新闻按发布日期归属。',
        'distinct_tracked_projects':len(projects),'projects':list(projects.values()),'news':list(news.values()),
        'interpretation_rules':['跟踪项目数不等于本期新增招标数','意向征集不计作正式招标或已获批项目','同一项目跨周重复出现只计一项，但保留状态变化','没有披露的金额保持未知，不能记0或相加','历史快照不代表当前仍可投标，需另查最新项目库','月报按自然月，季报按自然季度，年报按自然年，而非固定四周拼接']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['monthly','quarterly','annual'],required=True);parser.add_argument('--period',required=True)
    args=parser.parse_args();reports=[json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'reports/weekly').glob('*.json')]
    payload=aggregate(reports,args.kind,args.period)
    target=ROOT/'dist/reports'/args.kind/(args.period+'.json');target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(str(target)+'：'+str(payload['distinct_tracked_projects'])+'项已跟踪项目；不等于本期新增数。')

if __name__=='__main__':main()
