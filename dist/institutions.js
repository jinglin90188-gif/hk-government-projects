'use strict';
const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const link=(u,t)=>/^https:\/\//.test(u||'')?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)} ↗</a>`:'';
const types={tender:'正式招标',rfi:'信息征询 RFI',eoi:'意向征集 EOI',prequalification:'资格预审',forecast:'采购计划'};
Object.assign(types,{rfq:'报价邀请 RFQ',rfp:'方案邀请 RFP',unknown:'阶段待核实'});
for(const value of ['rfq','rfp']){const option=document.createElement('option');option.value=value;option.textContent=types[value];$('#kind').append(option);}
let data;
const business=document.createElement('select');business.id='business';business.setAttribute('aria-label','按业务类型筛选');
for(const [value,label] of [['relevant','系统与工程'],['系统与数字化','系统与数字化'],['工程与设备','工程与设备'],['其他采购与服务','其他采购与服务'],['','全部业务']]){const o=document.createElement('option');o.value=value;o.textContent=label;business.append(o);}
$('#all').parentElement.replaceWith(business);
const categories=r=>r.business_categories||['其他采购与服务'];
const businessMatch=r=>!business.value||business.value==='relevant'&&categories(r).some(c=>['系统与数字化','工程与设备'].includes(c))||categories(r).includes(business.value);
function stage(r){const now=Date.now(),today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());if(r.closing_at&&Date.parse(r.closing_at)<=now||r.closing_date&&r.closing_date<today)return '已截标';return r.status;}
function render(){
 const term=$('#q').value.trim().toLowerCase();
 const rows=data.projects.filter(r=>(!$('#org').value||r.department===$('#org').value)&&(!$('#kind').value||r.kind===$('#kind').value)&&(!term||[r.title,r.title_zh,r.reference_no,r.department].join(' ').toLowerCase().includes(term))&&businessMatch(r)&&($('#history').checked||!['已截标','历史／阶段待核实','计划日期已过／需核实'].includes(stage(r)))).sort((a,b)=>(a.closing_date||'9999').localeCompare(b.closing_date||'9999'));
 $('#count').textContent=`当前显示 ${rows.length} 条；清单仅代表已提取的公开范围。`;
 $('#projects').innerHTML=rows.map(r=>`<article>
 <span class="tag">${esc(types[r.kind]||r.kind)}</span> <span class="muted">${esc(r.department)}</span>
 <h3>${esc(r.title_zh||r.title)}</h3><p class="muted">${esc(categories(r).join(' · '))} · ${esc(r.title_source||'机构原文')}</p>
 ${r.title_zh&&r.title_zh!==r.title?`<details><summary>查看原题</summary>${esc(r.title)}</details>`:''}
 <p><strong>${esc(r.reference_no)}</strong><br>${esc(stage(r))}${r.stale?' · 上次记录，本次未成功核实':''}<br>
 ${r.kind==='forecast'?'预计招标：':'回覆／截标：'}${esc(r.closing_at?.replace('T',' ').replace('+08:00','（香港时间）')||r.closing_date||r.forecast_display||r.forecast_date||'未注明')}${r.closing_date&&!r.closing_at?'（具体时分须查原文）':''}</p>
 <p class="muted">${esc(r.notes||'参与资格及文件获取要求须深入查看。')}</p><p class="muted">${esc(r.access_note)}</p>
 ${link(r.source_url,'机构原文')} ${link(r.document_url,'公开文件')}<p class="muted">核查：${esc(r.verified_at?.slice(0,16).replace('T',' '))}</p></article>`).join('')||'<div class="empty">当前条件下没有已提取记录，不代表没有采购。可切换其他业务分类，或查看下方覆盖状态。</div>';
}
fetch('institutions.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('数据尚未生成');return r.json();}).then(d=>{data=d;$('#time').textContent='最近公开资料检查：'+d.updated_at.slice(0,16).replace('T',' ')+'（香港时间）';if(Date.now()-Date.parse(d.updated_at)>30*3600000)$('#error').textContent='本页已超过30小时未成功更新，请核查运行记录。';for(const s of d.sources){const o=document.createElement('option');o.value=s.department;o.textContent=s.department;$('#org').append(o);}$('#coverage').innerHTML=d.sources.map(s=>`<article><h3>${esc(s.department)}</h3><p class="warn">${esc(s.status)}</p><p>本次提取 ${s.count||0} 条${s.retained_count?`；保留历史 ${s.retained_count} 条`:''}</p><p class="muted">${esc(s.note)}</p>${s.error?`<details><summary>检查记录</summary>${esc(s.error)}</details>`:''}${link(s.url,'公开入口')}</article>`).join('');render();}).catch(e=>{$('#error').textContent='机构数据读取失败：'+e.message+'，不能据此判断没有项目。';});
for(const s of ['#q','#org','#kind','#business','#history'])$(s).addEventListener('input',()=>{if(data)render();});
