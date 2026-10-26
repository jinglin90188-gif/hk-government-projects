# 香港政府项目库

这是一个可在手机打开的香港政府公开招标及采购预报项目库。项目评分已暂停。网站显示每条记录的部门、名称、编号、时间、原文及文件，并公开各个来源的采集结果。

## 查看网站

目标部署方式：GitHub Actions每天采集，GitHub Pages展示。首次启用步骤见[部署说明](部署到GitHub看这里.md)，实际网址由首次成功的Pages发布任务提供。

网页包含四个栏目：项目清单、按部门查看、采集情况、官方入口。点击“导出当前清单”可下载用Excel打开的CSV。当前网站是最近一次采集的快照，刷新浏览器不会重新向各政府部门采集。

## 本地更新项目

双击“更新项目数据.command”可重新采集；也可以执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python collect_projects.py --fresh
```

生成文件：

- `dist/projects.json`：网页项目数据、部门目录及采集结果。
- `dist/projects.csv`：完整清单，包括历史和待核实记录。
- `采集核对报告.md`：各部门的数量和未完成来源。
- `cache/`：临时原始资料和各来源最近一次成功结果，不上传网站。

本地更新只修改本地文件。云端部署启用后，`.github/workflows/daily-projects.yml`每天香港时间08:00启动采集，检查通过后发布网站。GitHub定时任务可能排队，08:00是启动时间。

## 每日自动更新

1. GitHub Actions读取上次成功的数据及`state/sources/`。
2. Python重新采集全部来源，生成`dist/projects.json`、`dist/projects.csv`和`dist/changes.json`。
3. 比较新增、内容变化、未再见到的记录，写入`history/日期.json`。
4. 通过数据检查后，把结果和来源状态提交回仓库。
5. GitHub Pages发布`dist/`。个别来源失败会明确显示；核心来源大面积失败时停止发布，保留原站。

普通采集不调用大模型。只检查一个来源时请加`--only 关键词`，结果会写到`projects.preview.json`，不会覆盖主项目库。

## 采集原则

- 使用中央电子投标箱官方XML、物流署采购预报JSON、金管局API、路政署CSV及各部门公开网页和文件。
- 与财政库务局的政府招标网址总目录比较，新增部门自动登记。
- 对建筑署内嵌JSON、渠务署公开压缩数据文件等动态页面单独解析。
- 尽量优先采用政府原文的中文名称；只有英文原文的项目保留英文。
- 没有有效截标日期的记录列为“状态待核实”，不认定正在招标。
- 日期已过的正式招标与计划时间已过的预报默认不在当前清单显示，可勾选查看。
- HTTP成功但未取得结构化项目时列为待解析，不用“零项目”掩盖失败。
- 某个来源失败时保留上次成功数据，并将其项目列为待核实。
- 当前目录覆盖的是已登记的公开招标来源；“已提取”不等于已证明该部门所有采购都已抓全。

所有解析代码均已放在这个项目内。GitHub运行不依赖本地旧文件夹、WorkBuddy或任何本机路径。

## 检查

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

`tests/verify_frontend.cjs`用于在具有linkedom的本地Node环境检查实际数据载入、搜索、筛选、部门、来源及详情交互。

## 更新网址清单

`dist/links.json`保存官网导航条目。原始清单仍在时，可通过`build_links.py`重新生成。

网站文件位于 `dist/`，可用于任何支持静态网页的免费托管服务。
