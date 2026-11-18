'use strict';
// Merge the two official-source feeds in memory; never overwrite either archive.
function mergeInstitutionFeed(base, feed) {
 const d=structuredClone(base);
 d.institution_feed={updated_at:feed?.updated_at||'',error:feed?null:'机构资料暂未读到，请查看机构采购页面。'};
 if(!feed)return d;
 const historical=new Set(['历史／阶段待核实','计划日期已过／需核实','已截标']);
 const normal=s=>String(s||'').normalize('NFKC').toUpperCase().replace(/[^\p{L}\p{N}]/gu,'');
 const key=r=>normal(r.department)+'|'+(r.reference_no?normal(r.reference_no):r.source_url||r.id);
 const rank=r=>r.kind==='forecast'?0:r.kind==='tender'?3:2;
 const seen=new Map(d.projects.map(r=>[key(r),r]));
 for(const p of feed.projects||[]){
  const r={...p,source_ids:[...new Set([...(p.source_ids||[]),p.source_id].filter(Boolean))],
   verified_at:p.verified_at||feed.updated_at||'',publish_date:p.publish_date||'',
   review_note:[p.review_note,p.stale?'保留上次记录，本次未成功核实。':'',p.access_note].filter(Boolean).join(' '),
   outdated:!!p.outdated||historical.has(p.status)&&p.status!=='已截标'};
  if(p.stale&&!historical.has(p.status))r.status='状态待核实';
  const old=seen.get(key(r));
  if(old){
   const ids=[...new Set([...(old.source_ids||[]),...r.source_ids])];
   if(rank(r)>rank(old))Object.assign(old,r);
   old.source_ids=ids;
  }else{d.projects.push(r);seen.set(key(r),r);}
 }
 for(const s of feed.sources||[]){
  if(!d.sources.some(x=>x.id===s.id))d.sources.push({...s,name:s.department+' · 机构采购',kind:'institution',
   status:s.error?'failed':s.count?'partial':'unparsed',documents:[],errors:s.error?[{url:s.url,error:s.error}]:[],
   coverage_note:s.note,reported_status:s.status});
  if(!d.departments.some(x=>x.name===s.department))d.departments.push({name:s.department,open:0,forecast:0,uncertain:0,needs_review:true});
 }
 d.stats.departments=d.departments.length;d.stats.sources=d.sources.length;
 return d;
}
