#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Jobui (职友集) public job list scraper: salary-rich, server-rendered."""
import argparse
import csv
import re
import time
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from lxml import html as lxml_html

import jobintel_paths as jp

UA ="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"

CITY = {"上海": "%E4%B8%8A%E6%B5%B7", "北京": "%E5%8C%97%E4%BA%AC",
        "深圳": "%E6%B7%B1%E5%9C%B3", "杭州": "%E6%9D%AD%E5%B7%9E"}

FIELDS = [
    "job_id", "source_platform", "source_url", "company", "title", "role_family",
    "tags", "city", "salary_raw", "salary_min_cny", "salary_max_cny", "salary_months",
    "experience", "education", "company_size", "team_size", "reports_to",
    "jd_text", "jd_hash", "category_url", "collected_at", "verification", "status", "notes",
]


def fetch(url: str, cache: Path, retries: int = 2) -> str:
    if cache.exists() and cache.stat().st_size > 10000:
        return cache.read_text(errors="ignore")
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
            with urlopen(req, timeout=25) as r:
                text = r.read().decode("utf-8", errors="ignore")
            if len(text) > 10000:
                cache.write_text(text)
                time.sleep(3.0 + (attempt * 1.0))
                return text
        except Exception as e:
            print(f"  ! {url}: {e}", flush=True)
        time.sleep(2 + attempt * 2)
    return ""


def salary(text: str):
    t = text.replace(" ", "")
    m = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)[kK]·(\d+)薪", t)
    if m:
        return m.group(0), int(float(m.group(1)) * 1000 * int(m.group(3))), int(float(m.group(2)) * 1000 * int(m.group(3))), int(m.group(3))
    m = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)[kK]", t)
    if m:
        return m.group(0), int(float(m.group(1)) * 1000 * 12), int(float(m.group(2)) * 1000 * 12), 12
    m = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)万", t)
    if m:
        return m.group(0), int(float(m.group(1)) * 10000), int(float(m.group(2)) * 10000), 12
    m = re.search(r"(\d+)-(\d+)元/天", t)
    if m:
        return m.group(0), int(m.group(1)) * 22 * 12, int(m.group(2)) * 22 * 12, 12
    return "", None, None, None


def classify(title: str, desc: str):
    text = title + " " + desc
    low = text.lower()
    is_mgr = any(k in low for k in ["技术经理", "研发经理", "技术负责人", "研发负责人", "技术总监", "研发总监", "负责人"])
    is_agent = any(k in low for k in ["agent", "智能体", "mcp", "rag", "llm", "大模型", "langgraph"])
    is_ai = any(k in low for k in ["算法", "人工智能", "机器学习", "深度学习", "ai", "模型", "推理", "mlops", "多模态", "语音"])
    is_arch = any(k in low for k in ["架构师", "架构", "专家"])
    is_java = "java" in low
    is_backend = any(k in low for k in ["后端", "服务端", "分布式", "微服务", "中间件", "高并发", "spring"])
    is_pay = any(k in low for k in ["支付", "清结算", "风控", "合规", "金融", "交易"])
    if is_mgr: fam = "管理/负责人"
    elif is_agent: fam = "AI/Agent"
    elif is_ai: fam = "AI/算法/平台"
    elif is_arch: fam = "架构/专家"
    elif is_backend or is_java: fam = "Java/后端"
    elif is_pay: fam = "支付/风控"
    else: fam = "其他"
    tags = []
    for flag, name in [(is_agent, "Agent"), (is_ai, "AI"), (is_java, "Java"), (is_backend, "后端"),
                       (is_arch, "架构/专家"), (is_mgr, "管理"), (is_pay, "支付/风控")]:
        if flag: tags.append(name)
    return fam, "|".join(tags)


def parse_page(html: str, kw: str, city: str):
    tree = lxml_html.fromstring(html)
    rows = []
    for card in tree.xpath('//div[contains(@class,"c-job-list")]'):
        a = card.xpath('.//a[contains(@class,"job-name")]')
        if not a:
            continue
        href = a[0].get("href") or ""
        jid_m = re.search(r"/job/(\d+)/", href)
        if not jid_m:
            continue
        jid = jid_m.group(1)
        title = " ".join(card.xpath('.//a[contains(@class,"job-name")]//h3//text()')).strip()
        company = " ".join(card.xpath('.//a[contains(@class,"job-company-name")]//text()')).strip()
        desc = " ".join(card.xpath('.//div[contains(@class,"job-desc")]//text()')).strip()
        sal = " ".join(card.xpath('.//span[contains(@class,"job-pay-text")]//text()')).strip()
        sal_raw, smin, smax, months = salary(sal or desc)
        exp = ""
        edu = ""
        exp_m = re.search(r"(不限经验|\d+-\d+年|\d+年以上|应届|1年以内|\d+年)", desc)
        if exp_m: exp = exp_m.group(1)
        edu_m = re.search(r"(本科|大专|硕士|博士|学历不限|中专)", desc)
        if edu_m: edu = edu_m.group(1)
        fam, tags = classify(title, desc)
        rows.append({
            "job_id": f"jobui_{jid}", "source_platform": "jobui",
            "source_url": f"https://www.jobui.com/job/{jid}/",
            "company": company, "title": title, "role_family": fam, "tags": tags,
            "city": city, "salary_raw": sal_raw,
            "salary_min_cny": smin or "", "salary_max_cny": smax or "", "salary_months": months or "",
            "experience": exp, "education": edu, "company_size": "", "team_size": "", "reports_to": "",
            "jd_text": f"{title} {desc}", "jd_hash": str(abs(hash(title + desc)))[:16],
            "category_url": kw, "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "verification": "C", "status": "active", "notes": "Jobui list card; detail not fetched",
        })
    return rows


def append_rows(rows, out):
    exists = out.exists() and out.stat().st_size > 0
    with out.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists: w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", default="AI Agent,Agent平台,大模型,Java架构师,技术经理,技术总监,风控,支付")
    ap.add_argument("--cities", default="上海,北京,深圳,杭州")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--max-jobs", type=int, default=1200)
    ap.add_argument("--out", help="output CSV (default: <data-dir>/processed/jobs_jobui.csv)")
    jp.add_argument(ap)
    args = ap.parse_args()
    data = jp.resolve(args.data_dir, produce=True)
    proc, raw = data / "processed", data / "raw" / "jobui"
    proc.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else proc / "jobs_jobui.csv"
    total = 0
    seen = set()
    for city in [c.strip() for c in args.cities.split(",") if c.strip()]:
        city_slug = CITY.get(city)
        if not city_slug:
            continue
        for kw in [k.strip() for k in args.keywords.split(",") if k.strip()]:
            kw_slug = quote_plus(kw)
            base = f"https://www.jobui.com/jobs/l-{city_slug}-q-{kw_slug}/"
            for p in range(1, args.pages + 1):
                url = base if p == 1 else f"{base}p{p}/"
                cache = raw / f"{city}_{kw_slug}_p{p}.html"
                html = fetch(url, cache)
                if not html:
                    continue
                rows = [r for r in parse_page(html, kw, city) if r["job_id"] not in seen]
                for r in rows: seen.add(r["job_id"])
                append_rows(rows, out)
                total += len(rows)
                print(f"[{city}/{kw}] p{p}: +{len(rows)} total={total}", flush=True)
                if total >= args.max_jobs:
                    print("max reached", flush=True); return
    print(f"done total={total} -> {out}", flush=True)


if __name__ == "__main__":
    main()
