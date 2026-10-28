# Job Intelligence Pipeline

> 把"岗位搜索 → 官方/第三方采集 → 去重 → 过滤 → 结构化 → 报告/能力图谱"的整条链路沉淀在这里。
> 本目录只有代码和文档，不含采集数据、个人信息、cookie；数据在运行时写入"数据目录"（见 §3）。

---

## 1. 这个目录包含什么

| 文件/目录 | 作用 |
|---|---|
| `sources.csv` | 所有网站/API/官方招聘页 link、访问方式、状态 |
| `scripts.csv` | 每个脚本的用途、输入、输出、命令 |
| `scripts/` | 全部脚本（Python + Node）；`run_pipeline.py` 是官方链路的入口 |
| `WORKFLOW.md` | 端到端流程、命令、数据流向 |
| `DATA_SCHEMA.md` | 字段字典、A/B/C 验证、薪资口径、数据目录布局 |
| `COMPLIANCE.md` | 合规边界：只采公开信息、不绕过登录/验证码 |
| `TROUBLESHOOTING.md` | 常见坑：BOSS code 37、Moka 密文、HTTP 200 业务错误、数据目录 |
| `REVIEW.md` | 一次工程 review 的记录（2026-10-27；文中路径是旧布局） |
| `requirements.txt` | Python 依赖；Node/Chrome 另装 |

> 快速自检：`python3 job-intel-pipeline/scripts/validate_pipeline.py`

设计原则：
- **只采公开可见信息**，不采个人简历/HR 个人信息；
- **能官方 API 就官方 API**（A 级），第三方只做补充（C 级）；
- **薪资不编造**：官方不披露就留空；
- **可复现**：每个来源都有 URL/API/命令/验证级别。

---

## 2. 快速开始

下面的命令都在 `job-intel-pipeline/` 的**上一级目录**执行（默认的数据目录建在当前目录下）。

### 2.1 环境

```bash
python3 -m venv .venv && . .venv/bin/activate     # 建议用虚拟环境，不要装进系统 Python
pip install -r job-intel-pipeline/requirements.txt
```

- Python 3.10+（第三方抓取脚本用到 `X | None` 注解）
- Node.js 22+（只有 `scripts/cdp_*.mjs` 需要：它们用全局 `WebSocket`，没有 npm 依赖）
- Google Chrome（Moka/美团/猎聘渲染需要；脚本里的路径目前是 macOS 默认路径，其他系统要改各脚本顶部的 `CHROME` 常量；BOSS 需要人工登录态）
- curl（探测接口）

### 2.2 一键跑官方 A 级链路（推荐）

```bash
python3 job-intel-pipeline/scripts/run_pipeline.py
```

依次运行：腾讯/阿里/字节 → 蚂蚁/京东/小红书/DeepSeek → MiniMax/01.AI → 月之暗面（Moka，需 Chrome）→ merge → filter，全部写进**同一个数据目录**；结束时打印每个阶段的行数，任何阶段失败或采集为空则退出码为 1。

常用选项：`--data-dir DIR`、`--skip moka,feishu`（可跳过 `collect_v2` `collect_v3` `feishu` `moka` `merge` `filter`）、`--max-pages N`。

### 2.3 分步运行

```bash
export JOBINTEL_DATA_DIR="tmp-jobs-$(date +%Y%m%d%H%M)"     # 先定一个目录，所有步骤共用

python3 job-intel-pipeline/scripts/official_collect_v2.py --company all --max-pages 1   # 腾讯/阿里/字节
python3 job-intel-pipeline/scripts/official_collect_v3.py                               # 蚂蚁/京东/小红书/DeepSeek（可能较慢；蚂蚁有时系统繁忙）
python3 job-intel-pipeline/scripts/official_feishu_startups.py                          # MiniMax / 01.AI
python3 job-intel-pipeline/scripts/official_moka_collect.py                             # 月之暗面 Moonshot（Moka，Headless Chrome）

python3 job-intel-pipeline/scripts/merge_official.py
python3 job-intel-pipeline/scripts/filter_official.py
```

> 没指定目录时，每个**采集**脚本都会新建一个 `tmp-jobs-*`。所以分步运行请像上面这样先指定一个（或每步传同一个 `--data-dir`），否则各步的输出会落在不同目录里。

---

## 3. 数据目录

所有输入、输出、缓存都在**一个**数据目录里。选择顺序（先匹配先用）：

1. `--data-dir DIR`
2. 环境变量 `JOBINTEL_DATA_DIR`
3. 默认：当前目录下的 `tmp-jobs-<yyyyMMddHHmm>`（例如 `tmp-jobs-202610271530`）
   - **采集/抓取/解析类**脚本：新建一个目录，所以重跑不会覆盖上一次的结果
   - **merge / filter / 分析类**脚本：使用当前目录下**最新**的 `tmp-jobs-*`

目录布局：

```text
<data-dir>/
├── official/     官方采集器、merge_official、filter_official 的输出
├── processed/    第三方抓取与分析表（jobs_*.csv、岗位信息整理.xlsx …）
├── raw/          缓存/抓取的 HTML（含第三方内容，不要提交；BOSS 页面放 raw/boss/）
└── reports/      生成的 markdown 报告
```

- `tmp-` 表示临时目录：想长期保留就用 `--data-dir` 指到固定位置，或把整个目录挪走。
- `tmp-jobs-*/` 已写进 `.gitignore`，不会被误提交。
- 想沿用旧布局（`data/jobs/{official,processed,raw}`）：`--data-dir data/jobs`，子目录同名。

---

## 4. 关键资源

- 官方来源/API：[`sources.csv`](sources.csv)
- 脚本清单：[`scripts.csv`](scripts.csv)
- 端到端流程：[`WORKFLOW.md`](WORKFLOW.md)
- 字段字典：[`DATA_SCHEMA.md`](DATA_SCHEMA.md)
- 合规：[`COMPLIANCE.md`](COMPLIANCE.md)
- 排错：[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

## 5. 不要提交的内容

- `.browser/`（含登录 cookie）
- 数据目录（`tmp-jobs-*`；`raw/` 里的原始 HTML 可能含个人信息/版权内容）
- 任何 API key / cookie / 登录态
- `__pycache__/`（`.pyc` 里有构建机器的绝对路径）

推荐先提交改动，再用 `git archive` 打包：只含已提交的文件，不会带上数据目录和 `.pyc`。

```bash
git archive --format=zip -o job-intel-pipeline.zip HEAD job-intel-pipeline
python3 job-intel-pipeline/scripts/validate_pipeline.py     # 打包前自检
```

本目录只用于**本地研究 + 可复现实验**，不用于对外发布岗位数据或商业化转售。
