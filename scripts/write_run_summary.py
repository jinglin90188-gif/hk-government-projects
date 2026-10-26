import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/projects.json').read_text(encoding='utf-8'))
s=d['stats'];c=d['changes'];h=d['health']
print('# 香港政府项目库每日运行结果\n')
print(f"采集时间：{d['updated_at']}\n")
print('| 正在招标 | 有效时间预报 | 新增 | 内容变化 | 待补齐来源 |')
print('|---:|---:|---:|---:|---:|')
print(f"| {s['open']} | {s['forecast']} | {c['new_count']} | {c['updated_count']} | {h['sources_needing_review']} |\n")
print('项目适配评分已关闭。部分来源仍待解析，详见网站“采集情况”。')
