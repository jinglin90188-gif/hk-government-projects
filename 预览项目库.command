#!/bin/zsh
cd "${0:A:h}"
print "请在浏览器打开 http://127.0.0.1:8766"
print "这是本地预览，不会重新采集。关闭这个窗口会停止预览。"
python3 -m http.server 8766 --bind 127.0.0.1 --directory dist
