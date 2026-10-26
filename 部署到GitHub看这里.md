# 把项目库放到自己的GitHub账号

程序和定时配置已经准备好。账号授权和首次启用完成后，电脑关机也会每天采集。

## 你只需要先完成账号和仓库这一步

1. 用你打算使用的账号登录 [GitHub](https://github.com/login)。密码只在GitHub官网填写。
2. 打开 [新建仓库](https://github.com/new)，仓库名建议填 `hk-government-projects`。
3. 选择 **Public（公开）**，勾选 **Add a README file**，再创建仓库。
4. 把仓库网址发给我，并把当前应用的GitHub连接授权给该账号、该仓库。

仓库网址类似：`https://github.com/你的用户名/hk-government-projects`。

## 我来上传程序，你最后开启网站

在仓库里打开：**Settings → Pages → Build and deployment → Source → GitHub Actions**。

然后进入 **Actions**，打开“每日采集香港政府项目并发布网站”，点 **Run workflow**。第一次成功后，`publish`任务会显示实际的网站网址。

## 以后每天怎样运行

配置文件：`.github/workflows/daily-projects.yml`。

- 每天香港时间 **08:00启动采集**。完成采集和检查后发布，运行通常需要数分钟；GitHub排队时可能延迟。
- 重新获取官方数据，不调用大模型生成项目。
- 自动保存 `projects.json`、CSV及上次成功记录。
- 自动比较新增、修改、未再出现的记录，保存到 `history/`，给以后的日报、周报使用。
- 个别来源失败时保留上次成功资料，标为待核实。
- 关键来源大面积失败或结果异常时阻止发布，网站保留上一版。
- 网站会显示实际采集时间。超过30小时未更新会提示检查。

## 验证确实启用了每日更新

不能只看代码里有定时配置。要同时看到：

1. 目标账号的仓库里已上传程序；
2. Pages的Source已选GitHub Actions；
3. Actions中第一次运行的`collect`和`publish`都成功；
4. 打开实际Pages网址，可以看到对应这次运行的采集时间和运行记录；
5. 次日定时运行记录再次出现。

在这些步骤完成前，只能称“配置已准备”，不能称“云端自动更新已启用”。

参考：[GitHub Pages工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)、[定时任务说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。
