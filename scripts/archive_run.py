"""Save compact daily deltas for the future daily/weekly briefing program."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'dist/changes.json').read_text(encoding='utf-8'))
target=ROOT/'history'/(data['updated_at'][:10]+'.json')
earlier=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
def union(name):
    records={r['id']:r for r in earlier.get(name,[])}
    records.update({r['id']:r for r in data.get(name,[])})
    return list(records.values())
payload={'date':data['updated_at'][:10],'last_run_at':data['updated_at'],
  'new':union('new'),'updated':union('updated'),
  'no_longer_seen_ids':sorted(set(earlier.get('no_longer_seen_ids',[])+data.get('no_longer_seen_ids',[]))),
  'note':'未再见到不等于取消或批出；需核实官方公告。'}
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('已保存每日变化：'+target.name)
