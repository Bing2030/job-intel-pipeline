# job-intel-pipeline Review（2026-10-27）

> 这是 2026-10-27 的 review 记录。文中的路径（`data/jobs/...`）是**旧布局**：现在所有数据都写进数据目录，默认 `./tmp-jobs-<yyyyMMddHHmm>/`，见 [README §3](README.md)。

## 结论

可分享，但 v1 有 3 个会影响复现的问题；已修复 2 个 critical/high，剩余限制已写入文档。

---

## Findings

| 严重度 | 问题 | 处理 |
|---|---|---|
| **Critical** | `merge_official.py` 在没有任何官方 raw 时，仍会用美团 175 条生成 all/target；随后 `filter_official.py` 会覆盖 filtered 数据 | 已加 guard：`loaded_official==0` 直接退出；测试验证不会再写文件；filtered 已恢复 1,062/471 |
| **High** | 采集脚本输出与 merge 输入不一致：v2 输出 `jobs_official_raw.csv`、v3 输出 `_batch2_raw.csv`，但 merge 只读分源 `jobs_official_{tencent,alibaba,...}.csv` | merge 已支持 raw/batch2/startups/moonshot；docs/scripts.csv 已更新 |
| **High** | 文档/默认路径含本机用户目录绝对路径，分享不可复现 | README/WORKFLOW 改为 `/path/to/job-hunting`、`PY=python3`；`boss_batch_parse.py` 默认输出改为 repo-relative |
| Medium | 当前仓库是 filtered-only；README 的 end-to-end 命令需要先重新采集 raw | README/WORKFLOW 已明确先跑 collectors；`filter_official.py` 增加缺失 `jobs_official_all.csv` 的明确报错 |
| Medium | 文档/清单数量不一致（22/23/24） | `scripts/` 23 个脚本（20 py + 3 mjs），`scripts.csv` 23 行；README 已同步 |
| Medium | Chrome 路径、Moka 渲染、BOSS CDP 是平台相关且需要本地缓存 | 写入 TROUBLESHOOTING；分享包不含 raw/cookie |
| Low | Ant API 当前可能返回"系统繁忙"；快手需签名；智谱/月之暗面需浏览器 | sources.csv 已标注 A/B/— 状态 |

## 已测试

- `py_compile`：20 个 Python 脚本全部通过；
- `scripts/validate_pipeline.py`：目录/清单/编译/可移植性检查通过；
- `official_collect_v2.py --help`：CLI 正常；
- `merge_official.py` 无官方源：按预期退出，不再生成 all/target；
- `filtered` 数据仍为 **1,062 / 471**。

## 已知限制

1. 当前过滤后数据不是原始全量；想复现 end-to-end，需要重新跑 collectors 生成 `jobs_official_raw.csv`/`_batch2_raw.csv`。
2. 官方薪资基本不披露；不要用过滤数据做薪资结论。
3. Moka/Chrome/BOSS 依赖本地 Chrome 与缓存；分享包不包含 raw/HTML/cookie。
4. `official_moka_detail.py` 仍偏实验，详情页慢；优先用列表卡片全文。
5. `analyze.py`/`organize_jobs.py` 依赖全量 processed 文件；当前 filtered-only 下不要直接跑完整链路。

## 建议

- 每次改脚本后：`python3 job-intel-pipeline/scripts/validate_pipeline.py`
- 每次跑 merge 前：确认 `data/jobs/official/jobs_official_raw.csv` 或 `_batch2_raw.csv` 存在
- 分享时压缩 `job-intel-pipeline/`，不含 `data/`、`.browser/`、`raw/`
