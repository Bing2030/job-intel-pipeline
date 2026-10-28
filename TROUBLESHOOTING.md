# 常见问题与排错

## 1. HTTP 200 但业务失败

不要只看 HTTP 码：
- 百度：HTTP 200 + `{"status":"need-login"}`
- 快手：HTTP 200 + `{"code":-1,"message":"系统错误"}`
- 蚂蚁：HTTP 200 + `{"success":false,"errorMsg":"系统繁忙，请稍后重试"}`

先判业务 code/status，再判断成功。

## 2. BOSS 直聘

- `{"code":37,"message":"您的环境存在异常."}`：需要用户登录态 Chrome + CDP；不要用纯 headless API。
- 薪资数字乱码：BOSS 用自定义字体 PUA，映射 `U+E031–U+E03A = 0–9`（见 `boss_parse.py`）。
- 详情页串入相关岗位：主选择器 `.job-sec-text`、`.job-primary span.salary`、`h1`、`.brand-name`；清理 `直聘|boss` 水印。
- Chrome profile 锁/卡死：每次用独立 `--user-data-dir`，或用户手动启动专用 Chrome。

## 3. Moka（Moonshot/智谱/DeepSeek）

- 接口返回 `{"data":"<base64 密文>"}`：不要尝试解密；用 Headless Chrome 渲染 DOM，列表卡片通常已含全文。
- 渲染后的 DOM 会存到 `<data-dir>/raw/moka/`，页面结构变了（选择器失效）时先看这个文件。
- 无头 Chrome 空输出/卡住：
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --user-data-dir=/tmp/moka-profile \
  --virtual-time-budget=12000 --dump-dom "URL" > /tmp/dom.html
```
- 详情页慢：先采列表卡片全文；详情只对少量目标岗补。

## 4. 字节 / 腾讯 / 阿里

- 字节 API 限速明显：按关键词分页、限页；请求间隔 ≥0.4s；
- 腾讯 Requirement 常是"岗位要求详情请见上方岗位职责内说明"，补采价值低；以 Responsibility 为主；
- 阿里 `position/search` 需要自造 `XSRF-TOKEN` cookie + `x-xsrf-token` header（同值即可）；
- 阿里/字节返回多城市：city 归一化用 `/` 连接。

## 5. 小红书

- `pageSize` 被忽略，固定 10 条/页；只能 `pageNum` 递增；
- 有 `spider-tracker` / shield：≥2s/请求，见异常立即停。

## 6. 京东

- 列表路由必须 `/web/job/job_info_list/3`；
- 返回裸数组，无 total；`pageIndex` 递增到空；
- 真标题用 `positionNameOpen`，`positionName` 是职类名。

## 7. 快手 / 智谱 / 百度

- 快手：列表接口需 JS 现算 `sign`/`signTimestamp`；不逆向，改用无头 DOM；
- 智谱：Moka 加密；浏览器渲染；
- 百度：匿名 `getPostList` 返回 need-login，建议跳过或用内推。

## 8. 数据质量问题

- 官方薪资基本不披露：`salary_*` 留空，不编造；
- 过期岗位：投递前回源；`status` 记录；
- 去重：job_id 优先，再 company+title+city；
- JD 缺失：官方列表可能只有职责没有要求；`jd_text` 保留原文并标 `verification`。

## 9. 路径/环境

- 数据目录的选择顺序：`--data-dir` > `$JOBINTEL_DATA_DIR` > 默认 `./tmp-jobs-<yyyyMMddHHmm>`（见 README §3）。
- `No data dir found`：merge/filter/分析脚本在当前目录下找不到 `tmp-jobs-*`——传 `--data-dir`，或先跑一个采集脚本（它会新建目录）。
- 分步运行时每个采集脚本各建了一个目录：先 `export JOBINTEL_DATA_DIR=...` 或每步传同一个 `--data-dir`；或直接用 `run_pipeline.py`。
- merge 说没有来源文件：看它打印的 `[jobintel] data dir:`——没指定目录时它用的是"最新的 `tmp-jobs-*`"，可能不是你要的那个，传 `--data-dir` 指定。
- Chrome 路径：`official_moka_collect.py`、`official_moka_detail.py`、`meituan_scraper.py`、`chrome_collector.py` 顶部的 `CHROME` 常量是 macOS 默认路径，其他系统需要改。
- Python 3.10+；Node 22+（`cdp_*.mjs` 用全局 `WebSocket`）；Python 依赖：pandas/openpyxl/lxml。
