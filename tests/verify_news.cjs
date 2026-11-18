const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {parseHTML}=require('../.runtime/node_modules/linkedom');
const {window}=parseHTML(fs.readFileSync('dist/news.html','utf8')),document=window.document;
for(const id of ['newsTopic','newsDate']){let value='';Object.defineProperty(document.getElementById(id),'value',{get:()=>value,set:v=>value=v});}
const fixture={date:'2026-11-18',updated_at:new Date().toISOString(),status:'partial',sources:[{name:'政府新闻',url:'https://www.info.gov.hk/',status:'parsed',count:20}],items:[
 {title:'无人机监管平台试点',category:'低空与无人驾驶',publisher:'政府新闻',published_at:'2026-11-18T11:00:00+08:00',source_url:'https://www.info.gov.hk/news',summary:'已核实原文的中文摘要。',summary_kind:'ai'},
 {title:'港铁通信系统更新 <script>bad()</script>',category:'机场与铁路',publisher:'港铁',published_at:'2026-11-18T10:00:00+08:00',source_url:'javascript:bad()',summary:'消息提要',summary_kind:'excerpt'}]};
const context={document,window,console,Date,Intl,fetch:async url=>({ok:true,json:async()=>url.endsWith('index.json')?{dates:['2026-11-17','bad-date']}:{...fixture,status:url.includes('2026-11-17')?'failed':'partial'}})};
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/news.js','utf8'),context);
setImmediate(async()=>{
 assert.equal(document.querySelectorAll('.news-item').length,2);
 assert.equal(document.querySelectorAll('.news-item h2 a').length,1);
 assert.equal(document.querySelectorAll('.news-item script').length,0);
 assert.equal(document.querySelectorAll('#newsDate option').length,2);
 assert.ok(document.querySelector('#newsList').textContent.includes('AI摘要'));
 assert.ok(document.querySelector('#newsStatus').textContent.includes('原文提要不是AI摘要'));
 document.querySelector('#newsSearch').value='无人机';document.querySelector('#newsSearch').dispatchEvent(new window.Event('input'));
 assert.equal(document.querySelectorAll('.news-item').length,1);
 document.querySelector('#newsSearch').value='不存在';document.querySelector('#newsSearch').dispatchEvent(new window.Event('input'));
 assert.equal(document.querySelectorAll('.news-item').length,0);assert.ok(document.querySelector('.news-empty'));
 document.querySelector('#newsSearch').value='';document.querySelector('#newsDate').value='2026-11-17';document.querySelector('#newsDate').dispatchEvent(new window.Event('change'));
 await new Promise(r=>setImmediate(r));assert.ok(document.querySelector('#newsStatus').textContent.includes('上次记录'));
 const home=parseHTML(fs.readFileSync('dist/index.html','utf8'));
 const h={...context,document:home.document,window:home.window};vm.createContext(h);vm.runInContext(fs.readFileSync('dist/news.js','utf8'),h);
 await new Promise(r=>setImmediate(r));assert.equal(home.document.querySelectorAll('#newsPreviewList .news-item').length,2);
 console.log('News UI verified: latest news, archive selector, search, AI/excerpt labels, official links, failed-source warning, XSS escaping and homepage preview.');
});
