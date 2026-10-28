#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate job-market reports 01-05 from <data-dir>/processed/jobs_master_merged.csv into <data-dir>/reports/.

Every number comes from the data; there are no hand-written conclusions.
"""
import argparse
from collections import Counter
from pathlib import Path

import pandas as pd

import jobintel_paths as jp

SKILLS = [
    "Agent", "智能体", "Multi-Agent", "MCP", "LangGraph", "RAG", "LLM", "大模型",
    "Prompt", "上下文", "Function Calling", "工具调用", "Harness", "Runtime",
    "评测", "Evaluation", "推理", "微调", "RLHF", "Java", "Spring", "JVM",
    "并发", "分布式", "微服务", "高并发", "MySQL", "Redis", "Kafka", "RocketMQ",
    "Elasticsearch", "团队管理", "架构", "支付", "清结算", "风控", "合规",
    "数据平台", "MLOps", "K8s", "云原生", "Python", "Go", "C++", "算法",
    "多模态", "语音", "搜索", "推荐", "广告", "营销", "国际化", "跨国",
]
MONEY = lambda x: f"{x/10000:.0f}万"
CAVEAT = "样本取决于所选来源与关键词，不代表全市场比例。"


def load(proc: Path) -> pd.DataFrame:
    path = proc / "jobs_master_merged.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found: run analyze.py (same --data-dir) first")
    df = pd.read_csv(path, dtype=str).fillna("")
    df["is_target"] = df["is_target"].astype(str).str.lower() == "true"
    df["smin"] = pd.to_numeric(df["salary_min_cny"], errors="coerce")
    df["smax"] = pd.to_numeric(df["salary_max_cny"], errors="coerce")
    df["mid"] = (df["smin"] + df["smax"]) / 2
    df["jd_len"] = df["jd_text"].str.len()
    return df


def snapshot_label(df):
    col = df["collected_at"] if "collected_at" in df.columns else pd.Series([], dtype=str)
    d = col.astype(str).str[:10]
    d = d[d.str.fullmatch(r"\d{4}-\d{2}-\d{2}")]
    if not len(d):
        return "采集日期未知"
    return f"采集日期 {d.min()}" if d.min() == d.max() else f"采集日期 {d.min()} ~ {d.max()}"


def source_mix(df):
    return " / ".join(f"{k} {v}" for k, v in df["source_platform"].value_counts().items()) or "—"


def skill_counts(df, top=30):
    c = Counter()
    for t in df["jd_text"].fillna(""):
        low = str(t).lower()
        for s in SKILLS:
            if s.lower() in low:
                c[s] += 1
    rows = []
    n = max(1, len(df))
    for s, v in c.most_common(top):
        rows.append((s, v, round(v / n * 100, 1)))
    return rows


def tiers(rows):
    bands = [("第一梯队（>20%）", 20, None), ("第二梯队（10–20%）", 10, 20), ("第三梯队（5–10%）", 5, 10), ("第四梯队（≤5%）", 0, 5)]
    return [(name, [s for s, _, pct in rows if pct > lo and (hi is None or pct <= hi)]) for name, lo, hi in bands]


def top_titles(df, n=15):
    return df["title"].value_counts().head(n)


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def write(out_dir, name, lines):
    (out_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Generate job-market reports 01-05 from <data-dir>/processed/jobs_master_merged.csv "
                                             "into <data-dir>/reports/")
    jp.add_argument(ap)
    data = jp.resolve(ap.parse_args().data_dir, produce=False)
    out_dir = data / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load(data / "processed")
    snap, mix = snapshot_label(df), source_mix(df)
    t = df[df.is_target].copy()
    full = t[t.jd_len >= 200]
    sal = t[t.mid.notna()].copy()
    sen = sal[sal.title.str.contains("经理|总监|负责人|架构师|专家|资深|高级|Staff|Principal", case=False, na=False)]

    fam = t.role_family.value_counts()
    skills = skill_counts(t)

    # 01 AI/Agent
    ai = t[t.role_family.isin(["AI/Agent", "AI/算法/平台"])]
    write(out_dir, "01-ai-agent-roles.md", [
        f"# AI / Agent 岗位分析（{snap}）",
        "",
        f"> 样本：目标相关 {len(t)} 条，其中 AI/Agent + AI/算法/平台 **{len(ai)} 条**；有完整 JD（≥200 字）{int((ai.jd_len>=200).sum())} 条。",
        f"> 来源构成：{mix}。{CAVEAT}",
        "",
        "## 1. 岗位族",
        "",
        table(["岗位族", "数量"], [(k, v) for k, v in fam.items()]),
        "",
        "## 2. 高频技能（AI/Agent + AI/算法/平台）",
        "",
        table(["技能", "出现次数", "占 AI 岗比例"], skill_counts(ai)[:18]),
        "",
        "## 3. 高频标题",
        "",
        table(["标题", "数量"], [(k, v) for k, v in top_titles(ai).items()]),
    ])

    # 02 Java/backend
    jb = t[t.role_family.isin(["Java/后端"])]
    jb_skills = skill_counts(jb) if len(jb) else []
    write(out_dir, "02-java-backend-roles.md", [
        f"# Java / 后端岗位分析（{snap}）",
        "",
        f"> 样本：Java/后端 **{len(jb)} 条**（占目标相关 {round(len(jb) / max(1, len(t)) * 100, 1)}%）。{CAVEAT}",
        "",
        "## 1. 现有样本",
        "",
        table(["指标", "值"], [("Java/后端岗位数", len(jb)), ("有完整 JD", int((jb.jd_len >= 200).sum())), ("有薪资", int(jb.mid.notna().sum()))]),
        "",
        "## 2. 高频技能（样本内）",
        "",
        table(["技能", "次数", "占比"], jb_skills[:15]) if jb_skills else "样本不足",
        "",
        "## 3. 高频标题",
        "",
        table(["标题", "数量"], [(k, v) for k, v in top_titles(jb).items()]),
    ])

    # 03 manager/architect
    mg = t[t.role_family == "管理/负责人"]
    ar = t[t.role_family == "架构/专家"]
    write(out_dir, "03-manager-architect-roles.md", [
        f"# 管理 / 架构岗位分析（{snap}）",
        "",
        f"> 样本：管理/负责人 **{len(mg)} 条**；架构/专家 **{len(ar)} 条**。{CAVEAT}",
        "",
        "## 1. 数量与薪资",
        "",
        table(["岗位族", "数量", "薪资样本", "中位年薪"], [
            ("管理/负责人", len(mg), int(mg.mid.notna().sum()), MONEY(mg.mid.median()) if mg.mid.notna().any() else "—"),
            ("架构/专家", len(ar), int(ar.mid.notna().sum()), MONEY(ar.mid.median()) if ar.mid.notna().any() else "—"),
        ]),
        "",
        "## 2. 管理岗高频标题",
        "",
        table(["标题", "数量"], [(k, v) for k, v in top_titles(mg).items()]),
        "",
        "## 3. 架构岗高频标题",
        "",
        table(["标题", "数量"], [(k, v) for k, v in top_titles(ar).items()]),
    ])

    # 04 salary
    if len(sal):
        by_role = sal.groupby("role_family")["mid"].agg(["count", "median", "min", "max"]).sort_values("count", ascending=False)
        by_city = sal.groupby("city_clean")["mid"].agg(["count", "median"]).sort_values("count", ascending=False).head(10)
        by_src = sal["source_platform"].value_counts()
        lines = [
            f"# 薪资 benchmark（{snap}）",
            "",
            f"> 薪资样本：**{len(sal)} 条**；整体中位 **{MONEY(sal.mid.median())}**，P25 {MONEY(sal.mid.quantile(.25))}，P75 {MONEY(sal.mid.quantile(.75))}。",
            (f"> 高级/管理/架构标题样本：**{len(sen)} 条**，中位 **{MONEY(sen.mid.median())}**，P25 {MONEY(sen.mid.quantile(.25))}，P75 {MONEY(sen.mid.quantile(.75))}。"
             if len(sen) else "> 高级/管理/架构标题样本：0 条。"),
            "",
            "## 1. 按岗位族",
            "",
            table(["岗位族", "样本", "中位年薪", "最低", "最高"], [
                (i, int(r["count"]), MONEY(r["median"]), MONEY(r["min"]), MONEY(r["max"]))
                for i, r in by_role.iterrows()
            ]),
            "",
            "## 2. 按城市",
            "",
            table(["城市", "样本", "中位年薪"], [(i, int(r["count"]), MONEY(r["median"])) for i, r in by_city.iterrows()]),
            "",
            "## 3. 薪资样本来源",
            "",
            table(["来源", "样本"], [(k, v) for k, v in by_src.items()]),
            "",
            "> 薪资来自公开页面标注，覆盖不均；官方来源通常不披露薪资，不用推断值填补。",
        ]
    else:
        lines = [
            f"# 薪资 benchmark（{snap}）",
            "",
            "> 目标相关岗位中没有薪资样本（官方来源通常不披露薪资；第三方来源才可能有）。",
        ]
    write(out_dir, "04-salary-benchmarks.md", lines)

    # 05 skills
    all_rows = skill_counts(t, top=None)
    write(out_dir, "05-skill-frequency.md", [
        f"# 技能频率总表（{snap}）",
        "",
        f"> 目标相关岗位 {len(t)} 条；有完整 JD {len(full)} 条。频率 = 提及该词的岗位数 / 目标岗位数。",
        "> 关键词匹配较粗（如“算法”包含算法岗与“算法能力”），用于方向判断，不用于精确统计。",
        "",
        table(["技能/关键词", "次数", "占目标岗位比例"], skills),
        "",
        "## 分档（按占比）",
        "",
    ] + [f"- **{name}**：{'、'.join(names)}" for name, names in tiers(all_rows) if names])

    print("written reports 01-05 ->", out_dir)
    print("target", len(t), "fulljd", len(full), "salary", len(sal), "senior", len(sen))


if __name__ == "__main__":
    main()
