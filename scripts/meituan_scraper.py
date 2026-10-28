#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meituan official careers search collector (public pages, Chrome headless).

Search page exposes job cards (title/city/dept/duties/update date) and data-jobunionid.
Source: https://zhaopin.meituan.com/web/position?keyword=...&pageNo=N
"""
import argparse
import csv
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from lxml import html as lxml_html

import jobintel_paths as jp

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"

FIELDS = [
    "job_id", "source_platform", "source_url", "company", "title", "role_family",
    "tags", "city", "salary_raw", "salary_min_cny", "salary_max_cny", "salary_months",
    "experience", "education", "company_size", "team_size", "reports_to",
    "jd_text", "jd_hash", "category_url", "collected_at", "verification", "status", "notes",
]


def raw_dir(data: Path) -> Path:
    return data / "raw" / "meituan"


def chrome_dom(url: str, cache: Path, timeout: int = 60, retries: int = 2) -> str:
    if cache.exists() and cache.stat().st_size > 50000:
        return cache.read_text(errors="ignore")
    for attempt in range(retries + 1):
        profile = Path(tempfile.mkdtemp(prefix="chrome-meituan-"))
        cmd = [
            CHROME, "--headless", "--disable-gpu", "--no-sandbox",
            "--disable-dev-shm-usage", "--no-first-run", "--disable-extensions",
            f"--user-data-dir={profile}", "--virtual-time-budget=3000",
            "--dump-dom", url,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout)
            text = r.stdout.decode("utf-8", errors="ignore")
            if len(text) > 50000:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(text)
                time.sleep(0.5 + random.random() * 0.4)
                return text
            print(f"  ! short page {len(text)} {url}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"  ! timeout {url}", flush=True)
        finally:
            shutil.rmtree(profile, ignore_errors=True)
        time.sleep(1.5 + attempt * 2)
    return ""


def classify(title: str, jd: str) -> tuple[str, str]:
    text = f"{title} {jd}"
    low = text.lower()
    is_mgr = any(k in low for k in ["技术经理", "研发经理", "技术负责人", "研发负责人", "技术总监", "研发总监", "负责人", "团队管理"])
    is_agent = any(k in low for k in ["agent", "智能体", "multi-agent", "mcp", "rag", "llm", "大模型", "智能"])
    is_ai = any(k in low for k in ["算法", "人工智能", "机器学习", "深度学习", "ai", "模型", "推理", "mlops"])
    is_arch = any(k in low for k in ["架构师", "架构", "技术专家", "专家"])
    is_java = "java" in low
    is_backend = any(k in low for k in ["后端", "服务端", "分布式", "微服务", "中间件", "高并发"])
    is_pay = any(k in low for k in ["支付", "清结算", "风控", "合规", "金融", "交易"])
    if is_mgr:
        fam = "管理/负责人"
    elif is_agent:
        fam = "AI/Agent"
    elif is_ai:
        fam = "AI/算法/平台"
    elif is_arch:
        fam = "架构/专家"
    elif is_backend or is_java:
        fam = "Java/后端"
    elif is_pay:
        fam = "支付/风控"
    else:
        fam = "其他"
    tags = []
    for flag, name in [(is_agent, "Agent"), (is_ai, "AI"), (is_java, "Java"), (is_backend, "后端"),
                       (is_arch, "架构/专家"), (is_mgr, "管理"), (is_pay, "支付/风控")]:
        if flag:
            tags.append(name)
    return fam, "|".join(tags)


def parse_cards(dom: str, keyword: str) -> list[dict]:
    tree = lxml_html.fromstring(dom)
    out = []
    for card in tree.xpath('//div[contains(@class,"position_list_item")]'):
        jid = (card.get("data-jobunionid") or "").strip()
        if not jid:
            continue
        title = " ".join(card.xpath('.//div[contains(@class,"postion_name")]//div[contains(@class,"title")]//text()')).strip()
        spans = [" ".join(x.split()) for x in card.xpath('.//div[contains(@class,"split_line_box")]//span//text()') if x.strip()]
        city = next((x for x in spans if re.search(r"[市省区]", x) and "更新于" not in x and "社招" not in x and "校招" not in x), "")
        upd = next((x for x in spans if "更新于" in x), "")
        dept = ""
        if upd:
            try:
                dept = spans[spans.index(upd) + 1]
            except Exception:
                dept = ""
        duties = [" ".join(x.split()) for x in card.xpath('.//div[contains(@class,"position_duty")]//div[contains(@class,"desc")]//text()') if x.strip()]
        jd = " ".join(duties)
        fam, tags = classify(title, jd)
        out.append({
            "job_id": f"meituan_{jid}",
            "source_platform": "meituan",
            "source_url": f"https://zhaopin.meituan.com/web/position/detail?jobUnionId={jid}",
            "company": "美团",
            "title": title,
            "role_family": fam,
            "tags": tags,
            "city": city,
            "salary_raw": "",
            "salary_min_cny": "",
            "salary_max_cny": "",
            "salary_months": "",
            "experience": "",
            "education": "",
            "company_size": "",
            "team_size": "",
            "reports_to": "",
            "jd_text": jd,
            "jd_hash": str(abs(hash(jd)))[:16] if jd else "",
            "category_url": keyword,
            "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "verification": "A",
            "status": "active" if upd else "unknown",
            "notes": f"更新于 {upd}; 部门 {dept}" if upd else f"部门 {dept}",
        })
    return out


def append_rows(rows: list[dict], out: Path):
    exists = out.exists() and out.stat().st_size > 0
    with out.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", default="AI Agent,大模型,Agent平台,Java,后端架构,架构师,技术经理,技术负责人,技术总监,风控,支付")
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--max-jobs", type=int, default=200)
    ap.add_argument("--out", help="output CSV (default: <data-dir>/processed/jobs_meituan.csv)")
    jp.add_argument(ap)
    args = ap.parse_args()
    data = jp.resolve(args.data_dir, produce=True)
    raw, proc = raw_dir(data), data / "processed"
    raw.mkdir(parents=True, exist_ok=True)
    proc.mkdir(parents=True, exist_ok=True)
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    out = Path(args.out) if args.out else proc / "jobs_meituan.csv"
    all_rows, seen = [], set()
    for kw in keywords:
        for page in range(1, args.max_pages + 1):
            url = f"https://zhaopin.meituan.com/web/position?keyword={quote(kw)}&pageNo={page}"
            cache = raw / f"{quote(kw, safe='')}_p{page}.html"
            dom = chrome_dom(url, cache)
            if not dom:
                continue
            rows = parse_cards(dom, kw)
            new = [r for r in rows if r["job_id"] not in seen]
            for r in new:
                seen.add(r["job_id"])
            append_rows(new, out)
            all_rows.extend(new)
            print(f"[{kw}] page {page}: +{len(new)} total={len(all_rows)}", flush=True)
            if len(all_rows) >= args.max_jobs:
                print(f"reach max_jobs={args.max_jobs}", flush=True)
                return
    print(f"done: {len(all_rows)} jobs -> {out}", flush=True)


if __name__ == "__main__":
    main()
