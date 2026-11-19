'use strict';
// A presentation layer over dashboard.js; the source collectors remain unchanged.
const categoryDefs=[['all','全部类型'],['systems','系统与设备'],['consultancy','顾问研究'],['maintenance','保养运维'],['works','工程建设'],['services','其他服务']];
let family='all',directoryReady=false;
let savedProjects=new Set();
try{const saved=JSON.parse(localStorage.getItem('hk-projects-saved-v1')||'[]');if(Array.isArray(saved))savedProjects=new Set(saved.filter(x=>typeof x==='string'));}catch{}
function projectFamily(r){
 const t=[r.title,r.title_zh,r.notes].filter(Boolean).join(' ');
 if(/consultanc|feasibility|investigation|顧問|顾问|可行性|研究|勘查/i.test(t))return 'consultancy';
 if(/maintenance|operation and|repair|保養|保养|維修|维修|運維|运维/i.test(t))return 'maintenance';
 if(/system|software|platform|data|network|digital|CCTV|communication|computer|robot|系統|系统|平台|軟件|软件|數據|数据|網絡|网络|通信|電腦|电脑|機械人|机器人/i.test(t))return 'systems';
 if(/construction|works|building|工程|建造|土木/i.test(t))return 'works';
 return 'services';
}
const directorySelection=selection;
selection=function(){
 const days=Number($('#deadline').value),savedOnly=$('#savedOnly').checked;
 const now=Date.now(),end=now+days*86400000;
 return directorySelection().filter(r=>{
  const close=r.closing_at?Date.parse(r.closing_at):r.closing_date?Date.parse(r.closing_date+'T23:59:59+08:00'):NaN;
  return(family==='all'||projectFamily(r)===family)&&(!savedOnly||savedProjects.has(r.id))&&(!days||r.status==='正在招标'&&close>=now&&close<=end);
 });
};
function saveProject(id){
 savedProjects.has(id)?savedProjects.delete(id):savedProjects.add(id);
 try{localStorage.setItem('hk-projects-saved-v1',JSON.stringify([...savedProjects]));}catch{}
 renderProjects();
}
function updateDirectoryURL(){
 if(!globalThis.location||!globalThis.history)return;
 const url=new URL(location.href);
 for(const [k,v] of Object.entries({category:family==='all'?'':family,q:$('#search').value,department:$('#department').value,scope:activeScope==='business'?'business':'',status:activeKind==='all'?'':activeKind,page:page>1?String(page):'',days:$('#deadline').value,saved:$('#savedOnly').checked?'1':'',closed:$('#includeClosed').checked?'1':'',sort:$('#sort').value==='closing'?'':$('#sort').value}))v?url.searchParams.set(k,v):url.searchParams.delete(k);
 history.replaceState(null,'',url.href);
}
const directoryRender=renderProjects;
renderProjects=function(){
 if(!data)return;
 if(!directoryReady){
  directoryReady=true;
  if(globalThis.location){
   const q=new URL(location.href).searchParams;
   family=categoryDefs.some(([id])=>id===q.get('category'))?q.get('category'):'all';
   $('#search').value=q.get('q')||'';
   if([...$('#department').options].some(o=>o.value===q.get('department')))$('#department').value=q.get('department');
   activeScope=q.get('scope')==='business'?'business':'all';
   if(['tender','forecast','engagement','new','updated'].includes(q.get('status')))activeKind=q.get('status');
   $('#includeClosed').checked=q.get('closed')==='1';$('#savedOnly').checked=q.get('saved')==='1';
   $('#deadline').value=['7','14','30'].includes(q.get('days'))?q.get('days'):'';
   if(['recent','department'].includes(q.get('sort')))$('#sort').value=q.get('sort');
   page=Math.max(1,parseInt(q.get('page'),10)||1);renderKinds();
  }
 }
 directoryRender();
 const counts={all:0};for(const r of directorySelection()){counts.all++;const k=projectFamily(r);counts[k]=(counts[k]||0)+1;}
 $('#categoryFilters').innerHTML=categoryDefs.map(([id,label])=>`<button data-family="${id}" class="${id===family?'active':''}" aria-pressed="${id===family}">${label}<small>${counts[id]||0}</small></button>`).join('');
 document.querySelectorAll('[data-family]').forEach(b=>b.addEventListener('click',()=>{family=b.dataset.family;page=1;renderProjects();}));
 document.querySelectorAll('[data-project]').forEach(b=>{
  const r=data.projects.find(x=>x.id===b.dataset.project),card=b.closest('.project-card');
  const saved=savedProjects.has(r.id),button=document.createElement('button');button.className='save-project';button.textContent=saved?'★':'☆';button.setAttribute('aria-label',saved?'取消收藏':'收藏项目');button.setAttribute('aria-pressed',String(saved));button.addEventListener('click',()=>saveProject(r.id));card.append(button);
  const tag=document.createElement('span');tag.className='row-category';tag.textContent=categoryDefs.find(([id])=>id===projectFamily(r))[1];card.querySelector('.project-meta').append(tag);
 });
 updateDirectoryURL();
 if(globalThis.location?.hash.startsWith('#project=')){
  const id=new URL(location.href).hash.slice(9);if(data.projects.some(r=>r.id===id)&&!$('#projectDialog').open)showProject(id);
 }
};
const directoryShow=showProject;
showProject=function(id){
 directoryShow(id);
 const r=data.projects.find(x=>x.id===id);if(!r)return;
 const tools=document.createElement('div');tools.className='dialog-tools';
 const save=document.createElement('button');save.className='outline-button save-detail';save.textContent=savedProjects.has(id)?'取消收藏':'收藏项目';save.addEventListener('click',()=>{saveProject(id);save.textContent=savedProjects.has(id)?'取消收藏':'收藏项目';});tools.append(save);
 const copy=document.createElement('button');copy.className='outline-button';copy.textContent='复制项目链接';
 const message=document.createElement('p');message.className='share-status';message.setAttribute('role','status');
 copy.addEventListener('click',async()=>{
  const url=new URL(location.href);url.hash='project='+id;
  try{await navigator.clipboard.writeText(url.href);message.textContent='已复制，可转发给同事。';}catch{message.textContent='请复制此链接：'+url.href;}
 });tools.append(copy);$('#dialogContent').append(tools,message);
};
$('#closeDialog').addEventListener('click',()=>{if(globalThis.location?.hash.startsWith('#project=')){const u=new URL(location.href);u.hash='';history.replaceState(null,'',u.href);}});
$('#projectDialog').addEventListener('click',e=>{if(e.target===$('#projectDialog')&&globalThis.location?.hash.startsWith('#project=')){const u=new URL(location.href);u.hash='';history.replaceState(null,'',u.href);}});
$('#projectDialog').addEventListener('close',()=>{if(globalThis.location?.hash.startsWith('#project=')){const u=new URL(location.href);u.hash='';history.replaceState(null,'',u.href);}});
for(const id of ['deadline','savedOnly'])$('#'+id).addEventListener('change',()=>{page=1;renderProjects();});
$('#resetFilters').addEventListener('click',()=>{family='all';activeKind='all';activeScope='all';page=1;$('#search').value='';$('#department').value='';$('#sort').value='closing';$('#deadline').value='';$('#savedOnly').checked=false;$('#includeClosed').checked=false;renderKinds();renderProjects();});
