"""Produce an explicit per-department audit; unresolved never means no work."""
import json
import html
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def audit():
    data=json.loads((ROOT/'dist/projects.json').read_text(encoding='utf-8'))
    rows=[]
    for department in data['departments']:
        name=department['name']
        sources=[s for s in data['sources'] if s['department']==name]
        projects=[r for r in data['projects'] if r['department']==name]
        incomplete=[s for s in sources if s['status'] in ['failed','unparsed','documents','partial']]
        issues=[]
        if not any(s['kind']=='tender' for s in sources):issues.append('未登记独立招标入口，仅能依赖中央平台覆盖')
        if not any(s['kind']=='forecast' for s in sources):issues.append('未登记独立预报入口，仅能依赖中央采购预报覆盖')
        if incomplete:issues.append('存在连接失败、待解析或部分解析来源')
        open_rows=[r for r in projects if r['status']=='正在招标']
        missing_dates=[r for r in projects if r['kind']=='tender' and r['status']=='状态待核实']
        if missing_dates:issues.append(f'{len(missing_dates)}项尚未核实截标日期或当前状态')
        counts=Counter(r['company_fit']['decision'] for r in projects)
        rows.append(dict(department=name,issues=issues,
            tender_sources=sum(s['kind']=='tender' for s in sources),forecast_sources=sum(s['kind']=='forecast' for s in sources),
            source_status=dict(Counter(s['status'] for s in sources)),
            open=len(open_rows),related_open=sum(r['company_fit']['decision']=='include' for r in open_rows),
            related_forecast=sum(r['kind']=='forecast' and r['company_fit']['decision']=='include' and not r.get('outdated') for r in projects),
            scope_counts=dict(counts),unresolved_sources=[dict(id=s['id'],url=s['url'],status=s['status']) for s in incomplete]))
    report=dict(updated_at=data['updated_at'],departments=rows,
        note='逐部门检查已登记来源、解析结果和当前状态；不等于每份招标文件已经人工逐页核实。中央平台不能代替部门来源补齐。')
    (ROOT/'dist/department-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 逐部门采集核查','',report['note'],'',f"采集时间：{data['updated_at']}",'',
        '| 部门 | 招标/预报入口 | 正在招标（相关） | 相关预报 | 待处理事项 |','|---|---:|---:|---:|---|']
    lines.extend(f"| {r['department']} | {r['tender_sources']}/{r['forecast_sources']} | {r['open']}（{r['related_open']}） | {r['related_forecast']} | {'；'.join(r['issues']) or '本轮已登记来源检查通过，仍须留意新增入口'} |" for r in rows)
    (ROOT/'逐部门采集核查.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    cells=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [r['department'],str(r['tender_sources'])+'/'+str(r['forecast_sources']),str(r['open'])+'（'+str(r['related_open'])+'）',r['related_forecast'],'；'.join(r['issues']) or '本轮已登记来源检查通过，仍须留意新增入口'])+'</tr>' for r in rows)
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>逐部门采集核查</title><style>body{font:16px/1.6 system-ui;margin:24px;color:#183b32}table{border-collapse:collapse;width:100%;min-width:700px}td,th{border:1px solid #ccdcd6;padding:10px;text-align:left}th{background:#edf5f1}.scroll{overflow:auto}a{color:#087354}</style><a href="index.html">← 返回项目库</a><h1>逐部门采集核查</h1><p>'+html.escape(report['note'])+'</p><p>采集时间：'+html.escape(data['updated_at'])+'</p><p>入口数为“招标/预报”；无独立入口不等于没有项目，中央平台仍提供补充覆盖。</p><div class="scroll"><table><thead><tr><th>部门</th><th>入口</th><th>正在招标（相关）</th><th>相关预报</th><th>待处理事项</th></tr></thead><tbody>'+cells+'</tbody></table></div></html>'
    (ROOT/'dist/department-audit.html').write_text(page,encoding='utf-8')
    print(f"已核查{len(rows)}个部门/机构；{sum(bool(r['issues']) for r in rows)}个仍有待处理事项，详见逐部门采集核查。")
    return report

if __name__=='__main__':audit()
