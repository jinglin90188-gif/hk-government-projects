const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const {parseHTML}=require('../.runtime/node_modules/linkedom');
const root=path.join(__dirname,'..');
const {window}=parseHTML(fs.readFileSync(path.join(root,'dist/index.html'),'utf8'));
const document=window.document,storage=new Map(),location=new URL('https://example.com/hk-government-projects/');
for(const id of ['department','sort','deadline']){
 const element=document.getElementById(id);let value=id==='sort'?'closing':'';
 Object.defineProperty(element,'value',{get:()=>value,set:v=>{value=v;},configurable:true});
 Object.defineProperty(element,'options',{get:()=>[...element.querySelectorAll('option')],configurable:true});
}
document.getElementById('projectDialog').showModal=function(){this.open=true;};
document.getElementById('projectDialog').close=function(){this.open=false;};
window.scrollTo=()=>{};
const context={document,window,console,Blob,URL,URLSearchParams,setTimeout,location,structuredClone,
 history:{replaceState:(_,__,url)=>{location.href=url;}},
 localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
 navigator:{clipboard:{writeText:async text=>{context.copied=text;}}},
 fetch:async url=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'dist',url)))})};
vm.createContext(context);
for(const f of ['institution-merge.js','dashboard.js','directory.js'])vm.runInContext(fs.readFileSync(path.join(root,'dist',f),'utf8'),context);
setImmediate(async()=>{
 assert.equal(document.querySelectorAll('.stat').length,4);
 assert.equal(document.querySelectorAll('[data-family]').length,6);
 const count=()=>document.querySelectorAll('.project-card').length;
 assert.ok(count()>0);
 assert.ok([...document.querySelectorAll('#department option')].some(n=>n.value==='港铁公司'));
 document.querySelector('#search').value='ACDM/RFI/2026';document.querySelector('#search').dispatchEvent(new window.Event('input'));
 assert.equal(count(),1);assert.equal(document.querySelector('.project-card .badge').textContent,'信息征询中');
 document.querySelector('[data-kind="tender"]').click();assert.equal(count(),0);
 document.querySelector('[data-kind="engagement"]').click();assert.equal(count(),1);
 document.querySelector('[data-project]').click();assert.ok(document.querySelector('#dialogContent').textContent.includes('香港机场管理局'));
 document.querySelector('#closeDialog').click();document.querySelector('#resetFilters').click();
 document.querySelector('[data-family="systems"]').click();
 assert.equal(location.searchParams.get('category'),'systems');
 assert.ok([...document.querySelectorAll('.row-category')].every(n=>n.textContent==='系统与设备'));
 document.querySelector('#resetFilters').click();
 const first=document.querySelector('[data-project]').dataset.project;
 document.querySelector('.save-project').click();
 assert.ok(JSON.parse(storage.get('hk-projects-saved-v1')).includes(first));
 document.querySelector('#savedOnly').checked=true;document.querySelector('#savedOnly').dispatchEvent(new window.Event('change'));
 assert.equal(count(),1);assert.equal(document.querySelector('[data-project]').dataset.project,first);
 document.querySelector('[data-project]').click();
 assert.equal(document.querySelectorAll('.dialog-tools').length,1);
 document.querySelector('.dialog-tools button:last-child').click();await new Promise(r=>setImmediate(r));
 assert.ok(context.copied.endsWith('#project='+first));
 document.querySelector('#closeDialog').click();
 document.querySelector('#resetFilters').click();
 document.querySelector('#deadline').value='7';document.querySelector('#deadline').dispatchEvent(new window.Event('change'));
 assert.ok([...document.querySelectorAll('.project-card .badge')].every(n=>n.textContent==='正在招标'));
 document.querySelector('#resetFilters').click();
 document.querySelector('#search').value='NO-MATCH-123456';document.querySelector('#search').dispatchEvent(new window.Event('input'));
 assert.equal(count(),0);assert.ok(document.querySelector('#emptyCoverage'));
 assert.equal(location.searchParams.get('q'),'NO-MATCH-123456');
 document.querySelector('#resetFilters').click();assert.ok(count()>0);
 assert.equal(location.searchParams.get('q'),null);
 assert.ok(document.querySelector('[href="institutions.html"]'));
 assert.equal(document.querySelector('#loadError').hidden,true);
 console.log('Directory verified: categories, saved projects, deadline filter, share links, query state, reset, official links and original views.');
});
