"""Snapshot history and release checks shared by local and scheduled runs."""
import re
import copy
from datetime import datetime

NEEDS_REVIEW={'failed','unparsed','documents','partial'}
CORE_SOURCES={'etb_xml','gld_bd_json','gld_central_json'}
BUSINESS_FIELDS=('department','title','kind','reference_no','closing_date','closing_at','forecast_date','status','notes','document_url')

def title_key(row):
    return row.get('department',''),re.sub(r'[\W_]','',row.get('title','')).casefold()

def retain_missing_projects(rows,previous,now):
    """A disappeared listing is not evidence that a project ceased to exist."""
    stamp=now.isoformat(timespec='seconds')
    def refkey(r):
        ref=re.sub(r'[\W_]','',r.get('reference_no','')).casefold()
        return (r.get('department',''),ref) if ref else None
    ids={r.get('id') for r in rows};titles={title_key(r) for r in rows}
    refs={refkey(r) for r in rows if refkey(r)}
    for r in rows:
        if not r.get('stale'):
            r['last_seen_at']=stamp
            r.pop('retained_missing',None);r.pop('missing_since',None)
    result=list(rows)
    for old in previous.get('projects',[]):
        if old.get('id') in ids or title_key(old) in titles or refkey(old) is not None and refkey(old) in refs:
            continue
        r=copy.deepcopy(old)
        r.update(stale=True,retained_missing=True,missing_since=old.get('missing_since') or stamp,
                 last_seen_at=old.get('last_seen_at') or old.get('verified_at') or previous.get('updated_at',''))
        expired=bool(r.get('closing_date') and r['closing_date']<now.date().isoformat())
        if r.get('closing_at'):
            try:expired=expired or datetime.fromisoformat(r['closing_at'])<=now
            except ValueError:pass
        if old.get('status')=='已截标' or expired:r['status']='已截标'
        else:r['status']='状态待核实'
        if r.get('kind')=='forecast':r['outdated']=True
        note='本次未检出，保留历史记录；未据此判定项目取消或合约批出。'
        if note not in r.get('review_note',''):r['review_note']=' '.join(filter(None,[r.get('review_note'),note]))
        result.append(r)
    return result

def enrich_changes(rows,previous,now):
    timestamp=now.isoformat(timespec='seconds')
    earlier=previous.get('projects',[])
    by_id={r.get('id'):r for r in earlier}
    by_title={title_key(r):r for r in earlier}
    new_ids=[];updated_ids=[];unchanged=0
    for row in rows:
        old=by_id.get(row.get('id')) or by_title.get(title_key(row))
        row['first_seen_at']=(old.get('first_seen_at') or previous.get('updated_at') or timestamp) if old else timestamp
        if not earlier:
            row['change']='baseline'
        elif old is None:
            row['change']='new';new_ids.append(row['id'])
        elif any(row.get(field,'')!=old.get(field,'') for field in BUSINESS_FIELDS):
            row['change']='updated';updated_ids.append(row['id'])
        else:
            row['change']='unchanged';unchanged+=1
        row['last_changed_at']=timestamp if row['change'] in ['new','updated','baseline'] else old.get('last_changed_at',old.get('verified_at',timestamp))
    seen_ids={r['id'] for r in rows};seen_titles={title_key(r) for r in rows}
    missing=[r['id'] for r in earlier if r.get('id') not in seen_ids and title_key(r) not in seen_titles]
    # Missing notices are not labelled cancelled/awarded without official evidence.
    return rows,{'baseline':not bool(earlier),'compared_with':previous.get('updated_at'),
      'new_count':len(new_ids),'updated_count':len(updated_ids),'unchanged_count':unchanged,
      'no_longer_seen_count':len(missing),'new_ids':new_ids,'updated_ids':updated_ids,
      'no_longer_seen_ids':missing}

def validate_snapshot(data,production=True):
    errors=[];warnings=[]
    rows=data.get('projects',[]);sources=data.get('sources',[])
    ids=[r.get('id') for r in rows]
    if any(not v for v in ids) or len(ids)!=len(set(ids)):errors.append('项目ID缺失或重复')
    timestamp=datetime.fromisoformat(data['updated_at'])
    for row in rows:
        if not row.get('title') or not row.get('department'):errors.append('项目名称或部门缺失')
        if not row.get('source_url','').startswith(('https://','http://')):errors.append('项目缺少有效官方来源')
        if row.get('status')=='正在招标':
            if not row.get('closing_date'):errors.append('正在招标项目没有截标日期')
            elif row['closing_date']<timestamp.date().isoformat():errors.append('已过期项目错误列为正在招标')
            elif row.get('closing_at') and datetime.fromisoformat(row['closing_at'])<=timestamp:errors.append('截标时刻已过的项目错误列为正在招标')
            if row.get('stale'):errors.append('历史保留数据错误列为正在招标')
    computed={'records':len(rows),'open':sum(r.get('status')=='正在招标' for r in rows),
      'forecast':sum(r.get('kind')=='forecast' and not r.get('outdated') and r.get('status')!='已截标' for r in rows),'sources':len(sources)}
    for key,value in computed.items():
        if data.get('stats',{}).get(key)!=value:errors.append('统计数量不一致：'+key)
    core=[s for s in sources if s['id'] in CORE_SOURCES and s['status'] in ['parsed','empty']]
    if production:
        if len(sources)<70:errors.append('全量来源数量不足，禁止用不完整测试覆盖主站')
        if len(core)<2:errors.append('三个中央核心来源至少两个必须采集成功')
        if len(rows)<25:errors.append('项目数量异常偏少，需要人工核对')
    pending=[s for s in sources if s['status'] in NEEDS_REVIEW]
    if pending:warnings.append(f'{len(pending)}个来源需继续核对；来源明细已列出')
    return {'status':'failed' if errors else 'partial' if warnings else 'ok','publish_allowed':not errors,
      'errors':list(dict.fromkeys(errors)),'warnings':warnings,'sources_needing_review':len(pending),
      'core_sources_ok':len(core),'checked_at':data['updated_at']}
