# 数据字段字典

## 1. 原始/官方 JD（jobs_official_filtered.csv）

| 字段 | 说明 |
|---|---|
| `job_id` | 稳定 ID；官方源为 `<source>_<id>` |
| `source_platform` | `tencent_official` / `alibaba_official` / `bytedance_official` / `jd_official` / `xhs_official` / `ant_official` / `deepseek_official` / `feishu_official` / `moka_official` / `meituan_official` |
| `source_url` | 官方职位/招聘页 URL |
| `company` | 公司名 |
| `title` | 岗位标题（京东用 `positionNameOpen`） |
| `role_family` | AI/Agent、Java/后端、架构/专家、支付/风控、管理/负责人 |
| `city` / `city_norm` | 城市；多城市用 `/` 连接 |
| `salary_raw` | 官方薪资原文；官方不披露则空 |
| `salary_min_cny` / `salary_max_cny` | 年化人民币；无数据留空，不编造 |
| `experience` | 经验要求原文 |
| `education` | 学历要求 |
| `jd_text` | **完整 JD**（职责 + 要求合并） |
| `jd_hash` | JD 文本 SHA1，用于去重/变更检测 |
| `verification` | A=官方全文；B=官方页未全；C=第三方 |
| `status` | active / expired / unknown |
| `notes` | 采集方式/限制 |
| `collected_at` | 采集时间（UTC ISO） |

## 2. 结构化 processed（jobs_structured.csv）

| 字段 | 说明 |
|---|---|
| `responsibilities` | 岗位职责 |
| `requirements_full` | 完整任职要求 |
| `hard_requirements` | 含必须/至少/精通/年以上等硬性句 |
| `must_have_skills` | 抽出的硬技能（Agent/RAG/Java/Python 等） |
| `management_scope` | 管理幅度/团队要求 |
| `years_required` / `education` | 年限/学历 |
| `nice_to_have` | 加分项 |
| `jd_quality` | 完整/部分/短缺失 |

## 3. 薪资口径

- 统一年化人民币；
- `salary_months` 缺省按 12 个月；
- 官方不披露 → 空；第三方样本单独标注来源；
- 不用推断/中位数填补单条岗位。

## 4. 验证级别

- **A**：官方招聘页/官方 API，全文；
- **B**：官方页面可访问但正文未完整/需浏览器；
- **C**：第三方公开页（BOSS/Jobui/猎聘），需回源核对。

## 5. 去重

1. `job_id` 相同 → 去重；
2. 跨源：`company + title + city` 归一化后去重；
3. 同公司同标题多城市 → 保留多城市记录；
4. 同名不同部门 → 保留（标题/URL 不同）。

## 6. 文件位置（数据目录）

所有文件都在数据目录 `<data-dir>/` 下（选择规则见 README §3）：

| 子目录 | 内容 |
|---|---|
| `official/` | 官方采集器输出（`jobs_official_raw.csv`、`_batch2_raw.csv`、`jobs_official_startups.csv`、`jobs_official_moonshot.csv`）、`jobs_official_all.csv`、`jobs_official_filtered*.csv/xlsx` |
| `processed/` | 第三方抓取输出（`jobs_jobui.csv`、`jobs_master.csv`（猎聘）、`jobs_meituan*.csv`、`jobs_boss*.csv`）、`jobs_master_merged.csv`、`jobs_structured.csv`、`岗位信息整理.xlsx`、`能力图谱.xlsx` |
| `raw/` | 缓存/抓取的 HTML（`raw/<source>/`、`raw/boss/pages`、`raw/boss/details`） |
| `reports/` | `00-stage1-snapshot.md`、`01–05-*.md`、`10-技术与管理能力图谱.md` |
