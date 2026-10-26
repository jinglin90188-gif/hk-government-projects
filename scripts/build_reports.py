"""Render immutable dated weekly evidence records, with a latest-report pointer.

This is not a keyword-to-news generator. New report JSON needs source checking
by the scheduled research task before publication. Old reports keep as-of dates.
"""
import html
import json
from datetime import date,datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def esc(value):return html.escape(str(value or ''))
def link(url,label):
    if not str(url).startswith(('https://','http://')):raise ValueError('来源必须为有效网址')
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)} ↗</a>'

def validate(report):
    start,end=date.fromisoformat(report['period_start']),date.fromisoformat(report['period_end'])
    verified=date.fromisoformat(report['verified_at'])
    if start>end or end>verified:raise ValueError('报告周期无效')
    if len(report['projects'])>5:raise ValueError('重点项目最多5项，不能凑数')
    keys=[]
    for row in report['projects']:
        keys.append((row['department'],row['reference_no'],row['title']))
        link(row['source_url'],'原文')
        if row['status']=='正在招标':
            if not row.get('closing_at') or datetime.fromisoformat(row['closing_at']).date()<verified:raise ValueError('在招项目截标时间缺失或过期')
        if not row.get('boundary') or not row.get('facts'):raise ValueError('缺少事实或范围限制')
    if len(keys)!=len(set(keys)):raise ValueError('重点项目重复')
    for item in report.get('news',[]):
        if not start<=date.fromisoformat(item['published_at'])<=end:raise ValueError('旧新闻不得冒充本周新闻')
        link(item['source_url'],'原文')
    return report

def render(report):
    validate(report)
    out=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
      '<title>香港政府项目商机周报 '+esc(report['publication_date'])+'</title>',
      '<style>body{font:16px/1.75 system-ui,-apple-system,sans-serif;color:#173c32;background:#f4f7f5;margin:0}main{max-width:1080px;margin:auto;padding:24px;background:white}h1{font-size:28px;line-height:1.4}h2{font-size:21px;margin-top:32px}h3{font-size:18px}a{color:#087457}small,.muted{color:#566b63}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;min-width:760px}th,td{border:1px solid #d9e2dd;padding:12px;vertical-align:top}th{background:#eaf1ee;text-align:left}th:first-child{width:16%}th:nth-child(2){width:18%}th:nth-child(3){width:38%}.news{padding:14px 0;border-bottom:1px solid #e1e8e3}.tag{display:inline-block;padding:2px 8px;background:#eef4f0;border-radius:4px;font-size:13px}p{margin:10px 0}.meta{font-size:14px}button{padding:8px 12px;background:#fff;border:1px solid #becfc5;border-radius:5px;color:#173c32}@media print{body{background:white}main{max-width:none;padding:0}button,.nav{display:none}.scroll{overflow:visible}table{min-width:0;font-size:10pt}a{color:black}tr{break-inside:avoid}h2,h3{break-after:avoid}}</style><main>',
      '<div class="nav"><a href="../index.html">项目库</a>　<a href="index.html">历期周报</a>　<button onclick="window.print()">打印或存为PDF</button></div>',
      '<h1>'+esc(report['title'])+'</h1>',
      '<p class="meta">新闻周期 '+esc(report['period_start'])+' 至 '+esc(report['period_end'])+'<br>项目状态核查截至 '+esc(report['verified_at'])+' 香港时间</p>',
      '<p>'+esc(report['summary'])+'</p>',
      '<p class="muted">本报告是按核查日形成的历史快照，不随时间自动改变。今日是否仍在招标，请核对项目库及官方最新修订。</p>',
      '<h2>重点项目</h2><div class="scroll"><table><thead><tr><th>部门及编号</th><th>项目及阶段</th><th>已核实内容与业务关联</th><th>时间及范围限制</th></tr></thead><tbody>']
    for r in report['projects']:
        closing=datetime.fromisoformat(r['closing_at']).strftime('%Y-%m-%d %H:%M')+' 截标' if r.get('closing_at') else '本次回应截止日期未在公开邀请中列明'
        out.append('<tr><td>'+esc(r['department'])+'<br><small>'+esc(r['reference_no'])+'</small></td><td>'+esc(r['title'])+'<p class="tag">'+esc(r['status'])+'</p></td><td>'+esc(r['facts'])+'<p>'+esc(r['relevance'])+'</p><small>'+esc(r['change_note'])+'</small></td><td><strong>'+esc(closing)+'</strong><p>'+esc(r['boundary'])+'</p>'+link(r['source_url'],'官方公告')+('　'+link(r['document_url'],'原始文件') if r.get('document_url') else '')+'</td></tr>')
    out.append('</tbody></table></div>')
    for r in report.get('deadline_alerts',[]):
        out.append('<h2>临近截标提醒</h2><p><strong>'+esc(r['department']+' '+r['reference_no']+' '+r['title'])+'</strong><br>'+esc(r['closing_at'].replace('T',' '))+'</p><p>'+esc(r['note'])+' '+link(r['source_url'],'官方公告')+'</p>')
    out.append('<h2>本周相关新闻</h2>')
    for r in report['news']:
        out.append('<section class="news"><h3>'+esc(r['title'])+'</h3><p class="meta">'+esc(r['published_at']+' · '+r['publisher'])+'　<span class="tag">'+esc(r['stage'])+'</span></p><p>'+esc(r['facts'])+'</p><p><strong>商机解读</strong> '+esc(r['analysis'])+'</p>'+link(r['source_url'],'新闻原文')+'</section>')
    if report.get('background'):
        out.append('<h2>背景资料 不计本周新增</h2>')
        for r in report['background']:out.append('<h3>'+esc(r['title'])+'</h3><p>'+esc(r['facts'])+'</p><p>'+esc(r['analysis'])+' '+link(r['source_url'],'官方介绍')+'</p>')
    out.append('<h2>重点部门覆盖情况</h2><div class="scroll"><table><tr><th>部门</th><th colspan="3">本期核查说明</th></tr>')
    for r in report['department_notes']:out.append('<tr><td>'+esc(r['department'])+'</td><td colspan="3">'+esc(r['note'])+'</td></tr>')
    out.append('</table></div><h2>口径说明</h2><p>'+esc(report['method'])+'</p><p><a href="../department-audit.html">查看全库逐部门采集核查</a></p></main></html>')
    return '\n'.join(out)

def build():
    output=ROOT/'dist/reports';output.mkdir(parents=True,exist_ok=True)
    records=[]
    for path in sorted((ROOT/'reports/weekly').glob('*.json')):
        report=validate(json.loads(path.read_text(encoding='utf-8')))
        page=render(report);name=report['publication_date']+'.html'
        (output/name).write_text(page,encoding='utf-8')
        (output/(report['publication_date']+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        records.append(report)
    if not records:raise ValueError('没有已核实的周报，禁止生成空白最新期')
    latest=max(records,key=lambda r:r['publication_date'])
    (output/'latest.html').write_text(render(latest),encoding='utf-8')
    items=''.join('<li><a href="'+esc(r['publication_date'])+'.html">'+esc(r['publication_date']+' '+r['title'])+'</a></li>' for r in reversed(records))
    (output/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>历期项目商机周报</title><body style="font:18px/1.8 system-ui;margin:24px"><a href="../index.html">返回项目库</a><h1>历期项目商机周报</h1><p>保留每期核查时间及原始依据；不把历史状态当作当前状态。</p><ul>'+items+'</ul></body></html>',encoding='utf-8')
    print('已生成周报 '+latest['publication_date']+'，共'+str(len(records))+'期；没有调用模型编造新闻。')

if __name__=='__main__':build()
