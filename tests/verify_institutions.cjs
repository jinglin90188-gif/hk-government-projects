const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {parseHTML}=require('../.runtime/node_modules/linkedom');
const {window}=parseHTML(fs.readFileSync('dist/institutions.html','utf8')),document=window.document;
for(const id of ['org','kind']){let value='';Object.defineProperty(document.getElementById(id),'value',{get:()=>value,set:v=>value=v});}
const feed=JSON.parse(fs.readFileSync('dist/institutions.json'));
const context={document,window,console,Date,Intl,fetch:async()=>({ok:true,json:async()=>feed})};
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/institutions.js','utf8'),context);
setImmediate(()=>{
 const business=document.getElementById('business');let category='relevant';Object.defineProperty(business,'value',{get:()=>category,set:v=>category=v});business.dispatchEvent(new window.Event('input'));
 assert.equal(document.getElementById('all'),null,'old core filter removed');
 assert.equal(document.querySelectorAll('#coverage article').length,9);
 assert.ok(document.querySelectorAll('#projects article').length>0);
 const q=document.getElementById('q');q.value='ACDM';q.dispatchEvent(new window.Event('input'));
 assert.equal(document.querySelectorAll('#projects article').length,1);
 assert.match(document.querySelector('#projects').textContent,/信息征询 RFI/);
 assert.match(document.querySelector('#projects').textContent,/16:30/);
 const kind=document.getElementById('kind');kind.value='tender';kind.dispatchEvent(new window.Event('input'));
 assert.equal(document.querySelectorAll('#projects article').length,0,'RFI must not appear in formal tender filter');
 q.value='';kind.value='';business.value='系统与数字化';business.dispatchEvent(new window.Event('input'));
 assert.ok([...document.querySelectorAll('#projects article')].every(a=>a.textContent.includes('系统与数字化')));
 business.value='工程与设备';business.dispatchEvent(new window.Event('input'));
 assert.ok([...document.querySelectorAll('#projects article')].every(a=>a.textContent.includes('工程与设备')));
 console.log('Institution page verified: nine coverage states, related projects, search, exact RFI deadline, separated stage filter.');
});
