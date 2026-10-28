# 端到端采集流程

> 目标：从每个来源拿到可核验的 JD → 统一字段 → 去重 → 按目标岗位过滤 → 产出 Excel/报告。
> 数据流：`raw HTML/API → 分源 CSV → jobs_official_all → filtered → xlsx/report`

---

## 0. 环境与数据目录

命令都在 `job-intel-pipeline/` 的**上一级目录**执行。

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r job-intel-pipeline/requirements.txt
export JOBINTEL_DATA_DIR="tmp-jobs-$(date +%Y%m%d%H%M)"     # 本次运行的数据目录（也可以每步传 --data-dir）
```

- 数据目录的选择规则与布局见 [README §3](README.md)：没指定时，采集脚本会新建 `./tmp-jobs-<yyyyMMddHHmm>`，merge/filter/分析脚本使用最新的一个。
- Python 3.10+；Node 22+（`cdp_*.mjs`）；Chrome：无头渲染 Moka/JS 页面，BOSS 需要用户登录态；`curl`：探测 API。
- 不要提交或分享 `.browser/`、数据目录、任何 cookie。

---

## 1. 官方 A 级（优先）

一键运行：`python3 job-intel-pipeline/scripts/run_pipeline.py`（1.1–1.3 + 第 3 节的 merge/filter，写进同一个数据目录）。下面是分步。

### 1.1 腾讯 / 阿里 / 字节

```bash
python3 job-intel-pipeline/scripts/official_collect_v2.py --company all --max-pages 1
```

- 腾讯：列表含 Responsibility，Requirement 常为通用提示；
- 阿里：列表含 description + requirement；
- 字节：列表含完整 JD；API 限速明显，建议分关键词、限页。
- 输出：`<data-dir>/official/jobs_official_raw.csv`（三家合并）和 `jobs_official.csv`（按 公司+标题+城市 去重）。
- 同一数据目录里重复运行（包括 `--company` 只跑一家）会覆盖这两个文件；要保留上次结果请换数据目录。

### 1.2 蚂蚁 / 京东 / 小红书 / DeepSeek

```bash
python3 job-intel-pipeline/scripts/official_collect_v3.py
```

- 蚂蚁：`hrcareersweb.antgroup.com/api/social/position/search`；可能"系统繁忙"；
- 京东：form API；真标题用 `positionNameOpen`；无 total，翻页到空；
- 小红书：pageSize 被忽略，固定 10 条/页；建议 ≥2s；
- DeepSeek：从 `talent.deepseek.com/static/main.<hash>.js` 解析内联 JSON。
- 输出：`<data-dir>/official/_batch2_raw.csv`（merge 读取；重复运行会覆盖）。

### 1.3 AI 创业公司

```bash
python3 job-intel-pipeline/scripts/official_feishu_startups.py   # MiniMax / 01.AI
python3 job-intel-pipeline/scripts/official_moka_collect.py       # Moonshot
```

- MiniMax/01.AI：Feishu Jobs API → `official/jobs_official_startups.csv`；
- Moonshot：Moka 列表页，Headless Chrome 渲染 DOM 后抽取（列表卡片已含全文）→ `official/jobs_official_moonshot.csv`；渲染后的 DOM 另存 `raw/moka/moonshot_jobs.html`，选择器失效时先看它；
- 智谱/快手：同样思路，Moka/JS 签名需浏览器；
- 百度：登录墙，跳过。

---

## 2. 第三方补充（B/C 级）

### BOSS 直聘

1. 用户手动登录 Chrome（专用 profile，开 `--remote-debugging-port=9227`）；
2. 搜索目标关键词/城市，把页面保存进数据目录：

```bash
mkdir -p "$JOBINTEL_DATA_DIR/raw/boss/pages" "$JOBINTEL_DATA_DIR/raw/boss/details"
node job-intel-pipeline/scripts/cdp_fetch.mjs "<搜索页 URL>" 6000 9227 > "$JOBINTEL_DATA_DIR/raw/boss/pages/上海_Agent.html"   # 文件名：<城市>_<关键词>.html
# 详情页保存为 raw/boss/details/<job_id>.html，job_id 形如 boss_<id>（见 processed/jobs_boss_batch.csv）
```

3. 解析：

```bash
python3 job-intel-pipeline/scripts/boss_batch_parse.py      # raw/boss/pages → processed/jobs_boss_batch.csv
python3 job-intel-pipeline/scripts/boss_detail_parse.py     # raw/boss/details → processed/jobs_boss_detail.csv
python3 job-intel-pipeline/scripts/boss_parse.py page.html  # 单个页面 → processed/jobs_boss.csv
```

已知坑：`code 37 环境异常`、自定义薪资字体（PUA `U+E031–U+E03A` = 0–9）、详情页相关岗位噪音。

### Jobui / 猎聘 / 美团

```bash
python3 job-intel-pipeline/scripts/jobui_scraper.py
python3 job-intel-pipeline/scripts/liepin_scraper.py
python3 job-intel-pipeline/scripts/meituan_scraper.py
python3 job-intel-pipeline/scripts/meituan_detail.py
```

- Jobui：薪资样本；公开页面；
- 猎聘：安全中心会限流，只做小样本；
- 美团：官方搜索页，需要 Chrome；
- 输出（`<data-dir>/processed/`）：`jobs_jobui.csv`、`jobs_master.csv`（猎聘）、`jobs_meituan.csv`、`jobs_meituan_detail.csv`；
- 这些脚本是追加写入，缓存页（`raw/<source>/`）不会过期：复用同一个数据目录时，重采前先删对应的 `raw/<source>/`。

---

## 3. 合并 / 去重 / 过滤

### 官方

```bash
python3 job-intel-pipeline/scripts/merge_official.py
python3 job-intel-pipeline/scripts/filter_official.py
```

- merge：合并分源 → 目标城市/岗位族初筛 → `official/jobs_official_all.csv`（另有 `jobs_official_target.csv`、`jobs_official.xlsx`）。美团官方岗位来自 `processed/jobs_master_merged.csv`（第三方链路 `analyze.py` 的输出），没有就不含美团；
- filter：严格过滤 → `jobs_official_filtered.csv`（相关）+ `_target_level.csv`（senior/经理/架构）+ `_removed.csv`（含剔除原因）；
- `jobs_official_filtered.xlsx` 的 sheet：filtered_relevant / target_level / removed / company_family / removed_reasons。

### 第三方 / 全量 processed 数据集

```bash
python3 job-intel-pipeline/scripts/analyze.py
python3 job-intel-pipeline/scripts/report.py
python3 job-intel-pipeline/scripts/organize_jobs.py
python3 job-intel-pipeline/scripts/capability_map.py
```

- `analyze.py`：合并 `processed/jobs_*.csv`、去重、角色分类、薪资年化 → `jobs_master_merged.csv` / `jobs_master.xlsx` / `reports/00-stage1-snapshot.md`；
- `report.py`：生成 `reports/01–05`（所有数字都由数据算出，没有手写结论）；
- `organize_jobs.py`：生成 `processed/jobs_structured.csv` 和多 sheet `岗位信息整理.xlsx`（职责/要求/技能）。它还需要 `processed/jobs_filtered.csv`（可选 `jobs_removed.csv`）——这两个文件来自**本包之外**的过滤步骤（与 `filter_official.py` 同类、作用于 `jobs_master_merged.csv`），请自备或跳过这一步；
- `capability_map.py`：输入 `jobs_structured.csv` → `processed/能力图谱.xlsx` + `reports/10-技术与管理能力图谱.md`（各能力的市场需求频次）。
- 注意：这条链路只读 `processed/` 里的第三方数据，不读 `official/` 下的官方 filtered 结果。

---

## 4. 验证与质量

| 级别 | 含义 | 用法 |
|---|---|---|
| A | 官方招聘页/官方 API 全文 | 优先用于投递/分析 |
| B | 官方页可访问但正文未全/需浏览器 | 交叉核对 |
| C | 第三方公开页（Jobui/猎聘/BOSS） | 补充薪资/样本 |

规则：
- 薪资不编造：无薪数留空；
- 去重：`job_id` 优先，其次 company+title+city；
- 过期岗位标 `status`，投递前回源核对；
- 官方管理岗供给少，管理岗主要靠 BOSS/猎聘/内推。

---

## 5. 重跑

- 默认每次采集都新建 `tmp-jobs-<时间戳>`，所以重跑不会覆盖旧结果，也不会和旧缓存混在一起。
- 两次运行的差异（新增/下线岗位）没有现成工具，可按 `job_id` 对比两个目录里的 `official/jobs_official_filtered.csv`。
