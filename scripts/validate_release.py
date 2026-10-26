"""Fail before replacing the live site with a damaged or incomplete snapshot."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from snapshot_tools import validate_snapshot

data=json.loads((ROOT/'dist/projects.json').read_text(encoding='utf-8'))
health=validate_snapshot(data)
if not health['publish_allowed']:
    raise SystemExit('禁止发布：'+'；'.join(health['errors']))
for name in ['index.html','dashboard.html','dashboard.js','dashboard.css','links.json','projects.csv','changes.json']:
    if not (ROOT/'dist'/name).is_file():raise SystemExit('缺少网站文件：'+name)
print(f"发布检查通过：{len(data['projects'])}条记录，状态{health['status']}")
