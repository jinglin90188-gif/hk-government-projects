"""Export only the self-contained public project, excluding hosting identities."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=['collect_projects.py','snapshot_tools.py','company_scope.py','project_identity.py','业务筛选规则.md','requirements.txt','README.md',
    '部署到GitHub看这里.md','周报运行规则.md','更新项目数据.command','预览项目库.command','.gitignore','采集核对报告.md','逐部门采集核查.md']
DIRECTORIES=['.github','scripts','tests','dist','state','history','reports']
SKIP={'__pycache__','failed-snapshot.json','projects.preview.json'}

def export():
    output=ROOT/'exports'/'香港政府项目库_GitHub版.zip'
    output.parent.mkdir(exist_ok=True)
    paths=[ROOT/f for f in FILES if (ROOT/f).is_file()]
    for directory in DIRECTORIES:
        target=ROOT/directory
        if target.exists():
            paths.extend(p for p in target.rglob('*') if p.is_file() and not SKIP.intersection(p.parts))
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(set(paths)):
            bundle.write(path,Path('hk-government-projects')/path.relative_to(ROOT))
    print(output)
    print(f'包含{len(set(paths))}个文件，不含登录信息、.git、.openai或本机运行环境。')
    return output

if __name__=='__main__':export()
