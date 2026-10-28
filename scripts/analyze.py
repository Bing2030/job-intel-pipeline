#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge/analyze collected job data -> CSV/XLSX + stage-1 snapshot.

Reads <data-dir>/processed/jobs_*.csv (third-party scrapers) and writes jobs_master_merged.csv / jobs_master.xlsx
there, plus <data-dir>/reports/00-stage1-snapshot.md. Every number in the snapshot is computed from the data.
"""
import argparse
from collections import Counter
from pathlib import Path

import pandas as pd

import jobintel_paths as jp

FILES = [
    ("meituan_detail_300", "jobs_meituan_detail_300.csv"),
    ("meituan_detail", "jobs_meituan_detail.csv"),
    ("meituan", "jobs_meituan.csv"),
    ("jobui", "jobs_jobui.csv"),
    ("jobui2", "jobs_jobui2.csv"),
    ("jobui3", "jobs_jobui3.csv"),
    ("boss", "jobs_boss.csv"),
    ("boss_batch", "jobs_boss_batch.csv"),
    ("boss_detail", "jobs_boss_detail.csv"),
    ("liepin", "jobs_master.csv"),
]

SKILLS = [
    "Agent", "智能体", "Multi-Agent", "MCP", "LangGraph", "RAG", "LLM", "大模型",
    "Prompt", "上下文", "Function Calling", "工具调用", "Harness", "Runtime",
    "评测", "Evaluation", "推理", "微调", "RLHF", "Java", "Spring", "JVM",
    "并发", "分布式", "微服务", "高并发", "MySQL", "Redis", "Kafka", "RocketMQ",
    "Elasticsearch", "团队管理", "架构", "支付", "清结算", "风控", "合规",
    "数据平台", "MLOps", "K8s", "云原生", "Python", "Go", "C++", "算法",
    "多模态", "语音", "搜索", "推荐", "广告", "营销", "国际化", "跨国",
]


def load_all(proc: Path) -> pd.DataFrame:
    frames = []
    for source, name in FILES:
        path = proc / name
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype=str).fillna("")
        df["_file"] = source
        frames.append(df)
    if not frames:
        raise SystemExit(f"no data files in {proc} (expected jobs_*.csv written by the third-party scrapers)")
    all_df = pd.concat(frames, ignore_index=True)
    # detail files should win over list for same job_id
    prio = {"meituan_detail_300": 0, "meituan_detail": 0, "meituan": 2, "liepin": 0,
            "boss_detail": 0, "boss_batch": 2, "boss": 2, "jobui": 1, "jobui2": 1, "jobui3": 1}
    all_df["_prio"] = all_df["_file"].map(prio).fillna(9)
    all_df = all_df.sort_values(["job_id", "_prio"])
    all_df = all_df.drop_duplicates("job_id", keep="first").drop(columns=["_prio"])
    # prefer full JD rows when duplicates
    all_df["jd_len"] = all_df["jd_text"].str.len()
    return all_df


def is_target(row) -> bool:
    title = str(row.get("title", ""))
    fam = str(row.get("role_family", ""))
    text = f"{title} {row.get('jd_text','')}".lower()
    bad = ["实习", "校招", "产品经理", "运营", "销售", "hr", "人力", "财务", "设计", "测试",
           "客服", "行政", "法务", "律师", "招聘", "采购", "供应链", "物流经理", "风控 法务"]
    if any(k in title.lower() for k in bad):
        return False
    if fam not in {"AI/Agent", "AI/算法/平台", "管理/负责人", "架构/专家", "Java/后端", "支付/风控"}:
        return False
    tech = ["java", "python", "后端", "服务端", "架构", "算法", "agent", "大模型", "ai", "平台",
            "系统", "研发", "开发", "数据", "风控引擎", "支付", "清结算", "技术", "模型", "推理"]
    return any(k in text for k in tech)


def snapshot_label(df: pd.DataFrame) -> str:
    col = df["collected_at"] if "collected_at" in df.columns else pd.Series([], dtype=str)
    d = col.astype(str).str[:10]
    d = d[d.str.fullmatch(r"\d{4}-\d{2}-\d{2}")]
    if not len(d):
        return "采集日期未知"
    return f"采集日期 {d.min()}" if d.min() == d.max() else f"采集日期 {d.min()} ~ {d.max()}"


def main():
    ap = argparse.ArgumentParser(description="Merge third-party job CSVs in <data-dir>/processed into jobs_master_merged.csv / "
                                             "jobs_master.xlsx and write reports/00-stage1-snapshot.md")
    jp.add_argument(ap)
    data = jp.resolve(ap.parse_args().data_dir, produce=False)
    proc, out_dir = data / "processed", data / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_all(proc)
    df["jd_len"] = df["jd_text"].str.len()
    df["is_target"] = df.apply(is_target, axis=1)
    def city_clean(c):
        c = str(c)
        for k in ["上海", "北京", "深圳", "杭州", "广州", "成都", "新加坡"]:
            if k in c:
                return k
        return c if c not in ("", "nan") else "未知"
    df["city_clean"] = df["city"].map(city_clean)
    # city split
    print("all rows:", len(df), "target:", int(df.is_target.sum()))
    print(df.role_family.value_counts().to_string())
    print("with jd>=200:", int((df.jd_len >= 200).sum()))
    print("salary rows:", int(pd.to_numeric(df.salary_min_cny, errors="coerce").notna().sum()))

    # skill frequency (target rows only)
    skill_counts = Counter()
    for t in df.loc[df.is_target, "jd_text"].fillna(""):
        low = str(t).lower()
        for s in SKILLS:
            if s.lower() in low:
                skill_counts[s] += 1
    skill_df = pd.DataFrame(skill_counts.most_common(), columns=["skill", "count"])
    skill_df["pct"] = (skill_df["count"] / max(1, int(df.is_target.sum())) * 100).round(1)

    # sheets
    all_out = proc / "jobs_master_merged.csv"
    df.to_csv(all_out, index=False, encoding="utf-8-sig")
    xlsx = proc / "jobs_master.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="all_jobs", index=False)
        df[df.is_target].to_excel(w, sheet_name="target_jobs", index=False)
        sal = df[pd.to_numeric(df.salary_min_cny, errors="coerce").notna()][
            ["job_id", "source_platform", "company", "title", "city", "salary_raw",
             "salary_min_cny", "salary_max_cny", "salary_months", "role_family", "verification"]
        ]
        sal.to_excel(w, sheet_name="salary", index=False)
        skill_df.to_excel(w, sheet_name="skills", index=False)
        src = df["source_platform"].value_counts().rename_axis("source").reset_index(name="count")
        src.to_excel(w, sheet_name="sources", index=False)

    # snapshot
    city = df[df.is_target]["city_clean"].value_counts().head(15)
    fam = df[df.is_target]["role_family"].value_counts()
    top_titles = df[df.is_target]["title"].value_counts().head(20)
    target = df[df.is_target].copy()
    target["_salary"] = pd.to_numeric(target["salary_min_cny"], errors="coerce")
    sources = " / ".join(f"{k} {v}" for k, v in df["source_platform"].value_counts().items()) or "—"
    lines = [
        f"# 招聘市场数据快照（{snapshot_label(df)}）",
        "",
        f"> 去重后总岗位：{len(df)} 条 ｜ 目标相关：{len(target)} 条 ｜ 目标岗有完整 JD（≥200 字）：{int((target.jd_len>=200).sum())} 条 ｜ 目标岗有薪资：{int(target._salary.notna().sum())} 条",
        f"> 来源构成（source_platform）：{sources}。样本取决于所选来源与关键词，不代表全市场比例。",
        "",
        "## 1. 岗位族分布（目标相关）",
        "",
        "| 岗位族 | 数量 |",
        "|---|---:|",
    ]
    for k, v in fam.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 2. 城市分布（目标相关，原始字段）", "", "| 城市 | 数量 |", "|---|---:|"]
    for k, v in city.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 3. 高频技能/要求（目标相关 JD 文本）", "", "| 技能/关键词 | 出现次数 | 占目标岗位比例 |", "|---|---:|---:|"]
    for _, r in skill_df.head(30).iterrows():
        lines.append(f"| {r['skill']} | {r['count']} | {r['pct']}% |")
    lines += ["", "## 4. 高频岗位标题（Top 20）", ""]
    for k, v in top_titles.items():
        lines.append(f"- {k}：{v}")
    names = dict(FILES)
    lines += ["", "## 5. 文件", "",
              f"- `{all_out.relative_to(data).as_posix()}`",
              f"- `{xlsx.relative_to(data).as_posix()}`"]
    for k, v in df["_file"].value_counts().items():
        lines.append(f"- `processed/{names[k]}`（去重后 {v} 条）")
    p = out_dir / "00-stage1-snapshot.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", p, "and", xlsx)


if __name__ == "__main__":
    main()
