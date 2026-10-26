'use strict';
let data,links=[],activeKind='all',sourceFilter='all',page=1;
const PAGE_SIZE=30,$=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statuses={parsed:'已提取',partial:'部分提取',empty:'页面声明暂无招标',documents:'文件待解析',unparsed:'页面待解析',failed:'连接或解析失败',pending:'待检查'};
const external=(url,label)=>/^https?:\/\//.test(url||'')?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`:'';
const badge=r=>r.status==='正在招标'?'open':r.kind==='forecast'?'forecast':'uncertain';
const inScope=r=>r.company_fit?.decision==='include';
function applyCompanyScope(d){
 const selected=d.projects.filter(inScope);
 d.stats.open=selected.filter(r=>r.status==='正在招标').length;
 d.stats.forecast=selected.filter(r=>r.kind==='forecast'&&!r.outdated&&r.status!=='已截标').length;
 d.departments.forEach(dep=>{const rows=selected.filter(r=>r.department===dep.name);dep.open=rows.filter(r=>r.status==='正在招标').length;dep.forecast=rows.filter(r=>r.kind==='forecast'&&!r.outdated&&r.status!=='已截标').length;dep.uncertain=rows.filter(r=>r.status==='状态待核实').length;});
}
function refreshTimeStatuses(d){
 const now=new Date(),today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
 d.projects.forEach(r=>{if(r.status==='正在招标'&&(r.closing_at&&new Date(r.closing_at)<=now||r.closing_date&&r.closing_date<today))r.status='已截标';});
 d.stats.open=d.projects.filter(r=>r.status==='正在招标').length;
 d.departments.forEach(dep=>dep.open=d.projects.filter(r=>r.department===dep.name&&r.status==='正在招标').length);
 applyCompanyScope(d);
}
function renderUpdateNote(){
 const c=data.changes||{},a=data.automation||{},old=(Date.now()-new Date(data.updated_at).getTime())>30*3600000;
 const changes=c.baseline?'本次为首次建库。':`与上次相比：新收录 ${c.new_count||0} 条，内容变化 ${c.updated_count||0} 条。`;
 const schedule=a.active?'每日香港时间08:00启动采集，完成后更新网站。':'每日自动更新配置已准备，等待接入正确的GitHub账号后启用。';
 const counts={};data.projects.filter(r=>r.status!=="已截标"&&!r.outdated).forEach(r=>{const k=r.company_fit?.decision||"review";counts[k]=(counts[k]||0)+1;});
 $('#updateNote').innerHTML=`正在招标从宽、预报从严（不评分）：${counts.include||0}条相关、${counts.review||0}条待确认、${counts.exclude||0}条明显无关已隐藏。业务相关不等于已满足投标资格。 <a href="department-audit.html" target="_blank" rel="noopener">逐部门核查表 ↗</a> ${esc(schedule)} ${esc(changes)}${old?' <strong>已超过30小时未成功更新，请检查采集任务。</strong>':''}${a.run_url?' '+external(a.run_url,'查看运行记录'):''}`;
 $('#updateNote').classList.toggle('warning',old);
}
function switchView(view){document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==`view-${view}`);document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));if(!data)return;if(view==='departments')renderDepartments();if(view==='coverage')renderCoverage();if(view==='links')renderLinks();}
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
function selection(){
 const term=$('#search').value.trim().toLowerCase(),dept=$('#department').value,closed=$('#includeClosed').checked;
 return data.projects.filter(r=>(activeKind==='business_review'?r.company_fit?.decision==='review':inScope(r))&&(!dept||r.department===dept)&&(!term||`${r.title} ${r.title_zh||""} ${(r.title_aliases||[]).join(" ")} ${r.reference_no} ${r.department}`.toLowerCase().includes(term))&&(closed||r.status!=='已截标'&&!r.outdated)&&(activeKind==='all'||activeKind==='business_review'||activeKind==='tender'&&r.status==='正在招标'||activeKind==='forecast'&&r.kind==='forecast'||activeKind==='uncertain'&&r.status==='状态待核实'||activeKind==='new'&&r.change==='new'||activeKind==='updated'&&r.change==='updated')).sort((a,b)=>{
  if($('#sort').value==='department')return a.department.localeCompare(b.department,'zh-CN')||a.title.localeCompare(b.title,'zh-CN');
  if($('#sort').value==='recent')return(b.publish_date||'').localeCompare(a.publish_date||'');
  const priority=r=>r.status==='正在招标'?0:r.kind==='forecast'?1:r.status==='状态待核实'?2:3;
  return priority(a)-priority(b)||(a.closing_date||a.forecast_date||'9999').localeCompare(b.closing_date||b.forecast_date||'9999');
 });
}
function renderProjects(){
 if(!data)return;const rows=selection(),pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE));page=Math.min(page,pages);
 $('#resultCount').textContent=`${$('#department').value||'全部部门'} · ${rows.length} 条记录 · 点击项目名称查看详情`;
 $('#projectList').innerHTML=rows.slice((page-1)*PAGE_SIZE,page*PAGE_SIZE).map(r=>`<article class="project-card"><div><div class="project-meta"><span class="department-label">${esc(r.department)}</span><span class="badge ${badge(r)}">${esc(r.status)}</span>${r.source_ids.includes('etb_xml')?'<span>中央平台</span>':''}</div><h3 class="project-title"><button data-project="${r.id}">${esc(r.title_zh||r.title)}</button></h3><div class="project-ref">编号：<code>${esc(r.reference_no||'原始清单未提供')}</code> · ${r.source_ids.length} 个来源</div>${r.review_note?`<p class="review-note">${esc(r.review_note)}</p>`:''}</div><div class="project-right"><div class="project-date"><small>${r.kind==='forecast'?'预计招标':'截标日期'}</small><strong>${esc(r.kind==='forecast'?r.forecast_date||'未注明':r.closing_date||'待核实')}</strong></div><div class="project-links">${external(r.source_url,'政府原文')}${external(r.document_url,/\.pdf(?:\?|$)/i.test(r.document_url)?'项目文件':'原始资料')}</div></div></article>`).join('')||'<div class="empty">当前筛选条件下没有已采集项目。<br>这不代表该部门没有招标，请检查采集情况。<a href="#" id="emptyCoverage">查看采集情况 →</a></div>';
 document.querySelectorAll('[data-project]').forEach(b=>{
  const fit=data.projects.find(r=>r.id===b.dataset.project)?.company_fit;
  if(fit){const note=document.createElement('p');note.className='review-note';note.textContent=fit.reason+'；投标资格另核。';b.closest('.project-card').append(note);}
  b.addEventListener('click',()=>{
   showProject(b.dataset.project);
   const row=data.projects.find(r=>r.id===b.dataset.project);
   for(const text of [row?.stage_note,row?.eligibility_summary,row?.eligibility_note])if(text){const p=document.createElement('p');p.className='review-note';p.textContent=text;$('#dialogContent').append(p);}
  });
 });
 $('#emptyCoverage')?.addEventListener('click',e=>{e.preventDefault();switchView('coverage');});
 $('#pageInfo').textContent=`第 ${page} / ${pages} 页`;$('#prev').disabled=page===1;$('#next').disabled=page===pages;
}
function renderKinds(){const defs=[['all','业务相关项目'],['tender','正在招标'],['forecast','招标预报'],['new','本轮新收录'],['updated','本轮有变化'],['uncertain','状态待核实'],['business_review','业务范围待确认']];$('#statusFilters').innerHTML=defs.map(([id,label])=>`<button class="chip ${id===activeKind?'active':''}" data-kind="${id}" aria-pressed="${id===activeKind}">${label}</button>`).join('');document.querySelectorAll('[data-kind]').forEach(b=>b.addEventListener('click',()=>{activeKind=b.dataset.kind;page=1;renderKinds();renderProjects();}));}
function renderDepartments(){const term=$('#departmentSearch').value.trim();$('#departmentGrid').innerHTML=data.departments.filter(d=>d.name.includes(term)).map(d=>`<button class="department-card" data-department="${esc(d.name)}"><h3>${esc(d.name)}</h3><div class="department-numbers"><span><b>${d.open}</b>正在招标</span><span><b>${d.forecast}</b>招标预报</span><span><b>${d.uncertain}</b>待核实</span></div><div class="department-status">${d.needs_review?'部分来源待补齐 · 查看项目 →':'查看已采集项目 →'}</div></button>`).join('');document.querySelectorAll('[data-department]').forEach(b=>b.addEventListener('click',()=>{$('#department').value=b.dataset.department;activeKind='all';page=1;$('#search').value='';renderKinds();renderProjects();switchView('projects');window.scrollTo({top:280,behavior:'smooth'});}));}
function renderCoverage(){const opts=[['all','全部来源'],['parsed','已提取'],['needs','需补齐'],['empty','页面声明暂无']];$('#coverageFilters').innerHTML=opts.map(([id,label])=>`<button class="chip ${sourceFilter===id?'active':''}" data-source-filter="${id}">${label}</button>`).join('');document.querySelectorAll('[data-source-filter]').forEach(b=>b.addEventListener('click',()=>{sourceFilter=b.dataset.sourceFilter;renderCoverage();}));const rows=data.sources.filter(s=>sourceFilter==='all'||sourceFilter==='needs'&&['failed','unparsed','partial','documents'].includes(s.status)||sourceFilter===s.status);$('#coverageList').innerHTML=rows.map(s=>`<article class="source-card"><div class="source-head"><div><h3>${esc(s.name)}</h3><p>${s.kind==='forecast'?'招标预报':'招标公告'} · 取得 ${s.count} 条记录${s.pages?` · 检查 ${s.pages} 个网页`:''}</p></div><span class="badge ${s.status}">${statuses[s.status]||s.status}</span></div><div class="source-url">${external(s.url,'打开官方来源')}</div>${s.documents.length?`<details><summary>${s.documents.length} 份官方文件</summary><ul>${s.documents.map(d=>`<li>${external(d.url,d.name)}</li>`).join('')}</ul></details>`:''}${s.errors.length?`<details><summary>查看未完成项</summary><ul>${s.errors.map(e=>`<li>${external(e.url,'对应页面')}<div class="source-error">${esc(e.error)}</div></li>`).join('')}</ul></details>`:''}</article>`).join('');}
function renderLinks(){const term=$('#linkSearch').value.trim();$('#linkGrid').innerHTML=links.filter(l=>`${l.name} ${l.category}`.includes(term)).map(l=>`<article class="department-card link-card"><h3>${esc(l.name)}</h3><small>${esc(l.category)}</small>${external(l.url,'打开官网')}</article>`).join('');}
function showProject(id){const r=data.projects.find(x=>x.id===id);if(!r)return;$('#dialogContent').innerHTML=`<span class="badge ${badge(r)}">${esc(r.status)}</span><h2>${esc(r.title_zh||r.title)}</h2><dl><dt>政府部门</dt><dd>${esc(r.department)}</dd><dt>招标编号</dt><dd>${esc(r.reference_no||'原始清单未提供')}</dd><dt>发布日期</dt><dd>${esc(r.publish_date||'未注明')}</dd><dt>截标日期</dt><dd>${esc(r.closing_date||'未注明')}${r.closing_text?`<br><small>${esc(r.closing_text)}</small>`:''}</dd><dt>预计招标</dt><dd>${esc(r.forecast_date||'未注明')}</dd>${r.notes?`<dt>原文补充</dt><dd>${esc(r.notes)}</dd>`:''}${r.review_note?`<dt>核对提示</dt><dd>${esc(r.review_note)}</dd>`:''}<dt>采集时间</dt><dd>${esc(r.verified_at.replace('T',' ').slice(0,19))}</dd><dt>来源</dt><dd>${r.source_ids.map(s=>esc(data.sources.find(x=>x.id===s)?.name||s)).join('<br>')}</dd></dl><div class="project-links">${external(r.source_url,'打开政府原文')}${external(r.document_url,'打开项目文件')}</div>`;$('#projectDialog').showModal();}
$('#closeDialog').addEventListener('click',()=>$('#projectDialog').close());$('#projectDialog').addEventListener('click',e=>{if(e.target===$('#projectDialog'))$('#projectDialog').close();});
for(const id of ['search','department','sort','includeClosed'])$('#'+id).addEventListener(id==='search'?'input':'change',()=>{page=1;renderProjects();});
$('#departmentSearch').addEventListener('input',()=>data&&renderDepartments());$('#linkSearch').addEventListener('input',()=>data&&renderLinks());$('#prev').addEventListener('click',()=>{page--;renderProjects();});$('#next').addEventListener('click',()=>{page++;renderProjects();});
$('#export').addEventListener('click',()=>{if(!data)return;const keys=['department','status','reference_no','title','closing_date','forecast_date','source_url','document_url'],titles=['政府部门','状态','编号','项目名称','截标日期','预计招标','官方原文','项目文件'],cell=v=>'"'+String(v??'').replace(/"/g,'""')+'"';const body='\ufeff'+[titles,...selection().map(r=>keys.map(k=>r[k]))].map(r=>r.map(cell).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([body],{type:'text/csv;charset=utf-8;'}));const a=document.createElement('a');a.href=url;a.download=`香港政府项目_${data.updated_at.slice(0,10)}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
Promise.all([fetch('projects.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('项目数据读取失败');return r.json();}),fetch('links.json').then(r=>r.json())]).then(([d,l])=>{data=d;refreshTimeStatuses(data);renderUpdateNote();links=l.items;$('#timestamp').textContent='本次采集：'+d.updated_at.replace('T',' ').slice(0,16)+'（香港时间）';const st=d.stats;$('#stats').innerHTML=[[st.open,'正在招标','已取得截标日期且尚未过期'],[st.forecast,'招标预报','业务相关的预报及意向征集'],[st.departments,'部门 / 机构','可按部门逐项核对'],[st.sources,'官方来源','采集结果公开可查']].map(([n,label,note])=>`<div class="stat"><span>${label}</span><strong>${n.toLocaleString()}</strong><small>${note}</small></div>`).join('');$('#reviewCount').textContent=d.sources.filter(s=>['failed','unparsed','documents','partial'].includes(s.status)).length;d.departments.forEach(dep=>{const o=document.createElement('option');o.value=dep.name;o.textContent=dep.name;$('#department').append(o);});renderKinds();renderProjects();}).catch(error=>{$('#loadError').hidden=false;$('#loadError').textContent='无法载入项目资料：'+error.message+'。请刷新网页重试。';$('#timestamp').textContent='资料载入失败';});
