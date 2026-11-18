'use strict';
(()=>{
 const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const safe=u=>/^https?:\/\//i.test(u||'')?esc(u):'';
 const preview=!!$('#newsPreview'),today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const display=t=>t?t.slice(0,16).replace('T',' '):'尚未成功采集';
 let current;
 function card(r){const url=safe(r.source_url);return `<article class="news-item"><div class="news-meta"><span class="news-topic">${esc(r.category)}</span><span>${esc(r.publisher)}</span><time datetime="${esc(r.published_at)}">${esc(display(r.published_at))}</time></div><h2>${url?`<a href="${url}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a>`:esc(r.title)}</h2><p class="news-summary"><span class="summary-label">${r.summary_kind==='ai'?'AI摘要':'原文提要'} · </span>${esc(r.summary||'请点击原文查看。')}</p>${url?`<a class="news-source" href="${url}" target="_blank" rel="noopener noreferrer">新闻原文 ↗</a>`:''}</article>`;}
 function render(){
  const d=current,term=preview?'':$('#newsSearch').value.trim().toLowerCase(),category=preview?'':$('#newsTopic').value;
  const rows=(d.items||[]).filter(r=>(!term||[r.title,r.summary,r.publisher].join(' ').toLowerCase().includes(term))&&(!category||r.category===category));
  const old=d.updated_at&&Date.now()-Date.parse(d.updated_at)>30*3600000;
  const status=d.status==='failed'?'本次采集未成功，以下如有内容为上次记录。':old?'新闻已超过30小时未成功更新。':d.message||`最近采集：${display(d.updated_at)}（香港时间）`;
  if(preview){$('#newsPreviewStatus').textContent=status;$('#newsPreviewList').innerHTML=rows.slice(0,3).map(card).join('')||'<p class="news-preview-status">暂无新收录的相关消息，未用旧闻补足。</p>';return;}
  $('#newsStatus').textContent=status+(d.status==='partial'?' 部分来源未成功读取，可在下方查看。':'')+(d.items?.some(r=>r.summary_kind!=='ai')?' 原文提要不是AI摘要。':'');
  $('#newsStatus').classList.toggle('warning',d.status==='failed'||!!old);
  $('#newsCount').textContent=`${d.date||'最新采集'} · ${rows.length} 条`;
  $('#newsList').innerHTML=rows.map(card).join('')||'<div class="news-empty">'+esc(d.status==='failed'?'新闻来源暂未成功读取，请稍后重试。':d.message||'当前筛选条件下没有新闻。')+'</div>';
  $('#newsSources').innerHTML='<ul>'+(d.sources||[]).map(s=>`<li>${safe(s.url)?`<a href="${safe(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.name)}</a>`:esc(s.name)}：${s.status==='parsed'?'已读取 '+esc(s.count)+' 条原始记录':'未成功读取或解析'} · ${esc(display(s.checked_at))}</li>`).join('')+'</ul>';
 }
 async function load(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw Error('新闻资料读取失败');const d=await r.json();if(!Array.isArray(d.items))throw Error('新闻资料格式错误');current=d;if(!preview){$('#newsTopic').innerHTML='<option value="">全部主题</option>'+[...new Set(d.items.map(x=>x.category))].map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');$('#newsTopic').value='';}render();}
 load('news.json').catch(()=>{if(preview)$('#newsPreviewStatus').textContent='新闻暂未读取成功，可稍后打开每日新闻页面查看。';else $('#newsStatus').textContent='新闻暂未读取成功，请刷新重试。';});
 if(!preview){
  for(const id of ['newsSearch','newsTopic'])$('#'+id).addEventListener('input',()=>current&&render());
  fetch('news-archive/index.json',{cache:'no-store'}).then(r=>r.json()).then(d=>{for(const date of d.dates||[]){if(!/^\d{4}-\d{2}-\d{2}$/.test(date))continue;const o=document.createElement('option');o.value=date;o.textContent=date;$('#newsDate').append(o);}}).catch(()=>{});
  $('#newsDate').addEventListener('change',()=>{const date=$('#newsDate').value;if(date&&!/^\d{4}-\d{2}-\d{2}$/.test(date))return;load(date?'news-archive/'+date+'.json':'news.json').catch(()=>{$('#newsStatus').textContent='所选日期的新闻未读取成功。';});});
 }
})();
