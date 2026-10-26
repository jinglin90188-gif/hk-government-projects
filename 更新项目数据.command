#!/bin/zsh
cd "${0:A:h}"
task_python=".venv/bin/python"
if [[ ! -x "$task_python" ]]; then
  python3 -m venv .venv
  task_python=".venv/bin/python"
  "$task_python" -m pip install -r requirements.txt
fi
if "$task_python" collect_projects.py --fresh; then
  print "本地项目数据已更新。网页公开版本需要重新发布后才会同步。"
else
  print "本次采集未通过检查，请查看错误信息；原网页不会被覆盖。"
fi
read "?按回车关闭"
