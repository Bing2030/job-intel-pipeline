#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liepin public job scraper (local research only).

- Public pages only; no login/CAPTCHA bypass.
- Rate-limited, cached raw HTML under <data-dir>/raw/liepin/ (never share).
- Outputs <data-dir>/processed/jobs_master.csv and a links JSONL under <data-dir>/raw/liepin/.

Example:
  python3 job-intel-pipeline/scripts/liepin_scraper.py --city sh --max-categories 8 --max-jobs 120 [--data-dir DIR]
"""
import argparse
import csv
import hashlib
import html as html_lib
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lxml import html as lxml_html

import jobintel_paths as jp


def raw_dir(data: Path) -> Path:
    return data / "raw" / "liepin"


CITY_SLUG = {
    "sh": "city-sh",
    "bj": "city-bj",
    "sz": "city-sz",
    "hz": "city-hz",
}
CITY_LABEL = {"sh": "上海", "bj": "北京", "sz": "深圳", "hz": "杭州"}

# Categories worth crawling for the candidate. Slugs from Liepin city pages.
CATEGORY_WHITELIST = {
    # AI / Agent / LLM
    "rengongzhineng", "damoxingsuanfa", "suanfakaifa", "jiqixuexi",
    "sousuosuanfa", "tuijiansuanfa", "tuxiangsuanfa", "yuyinshibie",
    "ziranyuyanchulinlp", "shujukexuejia", "shujuwajue", "shujufenxi",
    "shujukaifa", "dashujujiagou", "dashujuzongjian",
    # Java / backend / platform
    "java", "python", "golang", "quanzhan", "c2", "c3", "node.js",
    "xitongjicheng", "yunweijishuzhichi", "yunweijl", "erpjishukaifa",
    # management / architect
    "itjingli", "yanfajl", "yanfagcs", "cto", "ctociojishuvp",
    "director", "vp", "jishuzongjian",
    # payment / risk / fintech
    "zhifuqingsuan", "fengxianguanli", "hegui",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")



CATEGORY_PRIORITY = [
    "rengongzhineng", "damoxingsuanfa", "suanfakaifa", "jiqixuexi",
    "sousuosuanfa", "tuijiansuanfa", "ziranyuyanchulinlp", "shujukexuejia",
    "java", "quanzhan", "python", "golang", "xitongjicheng", "yunweijishuzhichi",
    "cto", "ctociojishuvp", "director", "vp", "jishuzongjian", "itjingli",
    "yanfajl", "yanfagcs", "zhifuqingsuan", "fengxianguanli",
    "dashujujiagou", "shujufenxi", "shujukaifa", "shujuwajue", "erpjishukaifa",
]

def fetch(url: str, cache: Path | None = None, retries: int = 2, timeout: int = 20) -> str:
    if cache and cache.exists() and cache.stat().st_size > 1000:
        return cache.read_text(errors="ignore")
    last = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                text = data.decode("utf-8", errors="ignore")
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(text)
            time.sleep(0.6 + random.random() * 0.6)
            return text
        except (HTTPError, URLError, TimeoutError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def extract_category_urls(city_html: str, city_slug: str) -> list[str]:
    # City pages contain links like https://www.liepin.com/city-sh/career/java/
    pat = re.compile(rf'https://www\.liepin\.com/{re.escape(city_slug)}/career/[^"\s<]+', re.I)
    urls = []
    seen = set()
    for m in pat.finditer(city_html):
        u = html_lib.unescape(m.group(0)).rstrip("/") + "/"
        if u in seen:
            continue
        seen.add(u)
        slug = u.rstrip("/").split("/")[-1].lower()
        if slug in CATEGORY_WHITELIST:
            urls.append(u)
    rank = {k: i for i, k in enumerate(CATEGORY_PRIORITY)}
    return sorted(urls, key=lambda u: (rank.get(u.rstrip('/').split('/')[-1].lower(), 999), u))


def extract_job_links(page_html: str) -> list[str]:
    pat = re.compile(r'https://www\.liepin\.com/job/(\d+)\.shtml')
    out, seen = [], set()
    for m in pat.finditer(page_html):
        jid = m.group(1)
        if jid not in seen:
            seen.add(jid)
            out.append(f"https://www.liepin.com/job/{jid}.shtml")
    return out


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = html_lib.unescape(s)
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_salary(text: str) -> tuple[str, int | None, int | None, int | None]:
    """Return raw, min_annual, max_annual, months."""
    if not text:
        return "", None, None, None
    t = text.replace(" ", "")
    # e.g. 60-90k·16薪
    m = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)k[·•\*xX×](\d+)薪", t)
    if m:
        lo, hi, months = float(m.group(1)), float(m.group(2)), int(m.group(3))
        return m.group(0), int(lo * 1000 * months), int(hi * 1000 * months), months
    # e.g. 60-90k
    m = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)k", t)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return m.group(0), int(lo * 1000 * 12), int(hi * 1000 * 12), 12
    # e.g. 60k
    m = re.search(r"(\d+(?:\.\d+)?)k", t)
    if m:
        v = float(m.group(1))
        return m.group(0), int(v * 1000 * 12), int(v * 1000 * 12), 12
    # e.g. 60-90万
    m = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)万", t)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return m.group(0), int(lo * 10000), int(hi * 10000), 12
    return "", None, None, None


def parse_detail(page_html: str, url: str, city_label: str, category_url: str) -> dict:
    title_m = re.search(r"<title>(.*?)</title>", page_html, re.S | re.I)
    title_raw = clean_text(title_m.group(1)) if title_m else ""
    # 【上海 企业效率技术负责人招聘】-得物上海招聘信息-猎聘
    title = title_raw
    m = re.search(r"【[^】]*?\s+(.+?)招聘】", title_raw)
    if m:
        title = m.group(1).strip()
    else:
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.S | re.I)
        if h1:
            title = clean_text(h1.group(1))

    meta_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', page_html, re.I)
    desc = html_lib.unescape(meta_m.group(1)) if meta_m else ""

    # company: "，得物公司规模10000人以上" or title suffix
    company = ""
    cm = re.search(r"[，,]([^，,。]{2,40}?)公司规模", desc)
    if cm:
        company = cm.group(1).strip()
    if not company:
        cm2 = re.search(r"】-(.+?)(?:上海|北京|深圳|杭州|苏州|广州)?招聘信息", title_raw)
        if cm2:
            company = cm2.group(1).strip()

    salary_raw, smin, smax, months = parse_salary(desc + " " + title_raw)
    exp_m = re.search(r"岗位要求(.{0,20}?)学历[，,]\s*([^，,。]{0,20}?)相关经验", desc)
    education = exp_m.group(1).strip() if exp_m else ""
    experience = exp_m.group(2).strip() if exp_m else ""
    size_m = re.search(r"公司规模([^，,。]{2,30})", desc)
    company_size = size_m.group(1).strip() if size_m else ""

    # full JD from job-intro dd
    jd = ""
    jm = re.search(r'<dd[^>]*data-selector="job-intro-content"[^>]*>(.*?)</dd>', page_html, re.S | re.I)
    if jm:
        jd = clean_text(jm.group(1))
    if not jd:
        # fallback: section around 岗位职责/任职要求
        jm2 = re.search(r"(岗位职责.{0,3000}?)(?:公司简介|猎聘温馨提示)", page_html, re.S)
        if jm2:
            jd = clean_text(jm2.group(1))

    job_id_m = re.search(r"/job/(\d+)\.shtml", url)
    job_id = job_id_m.group(1) if job_id_m else hashlib.md5(url.encode()).hexdigest()[:12]

    # classify flags
    text = f"{title} {jd}"
    low = text.lower()
    is_agent = any(k in low for k in [
        "agent", "智能体", "multi-agent", "多智能体", "mcp", "langgraph",
        "rag", "llm应用", "llm 应用", "大模型应用", "agent平台", "agent 平台",
        "agent infra", "ai agent", "context engineering",
    ])
    is_ai = any(k in low for k in [
        "人工智能", "机器学习", "大模型", "算法", "ai平台", "ai 平台", "mlops",
        "推理平台", "模型平台", "ai工程", "ai 工程", "深度学习", "nlp",
    ])
    is_java = "java" in low
    is_backend = any(k in low for k in [
        "后端", "服务端", "分布式", "微服务", "中间件", "高并发", "spring",
        "go语言", "golang", "python", "c++",
    ])
    is_architect = any(k in low for k in ["架构师", "架构", "技术专家", "资深专家", "staff", "principal"])
    is_manager = any(k in low for k in [
        "技术经理", "研发经理", "技术负责人", "研发负责人", "技术总监",
        "研发总监", "工程总监", "团队管理", "管理过", "带团队",
    ])
    is_payment_risk = any(k in low for k in [
        "支付", "清结算", "风控", "合规", "反洗钱", "交易", "金融", "aml", "kyc",
    ])
    is_singapore = "新加坡" in text or "singapore" in low
    is_remote = any(k in text for k in ["远程", "remote", "居家办公"])

    # primary family: management > agent > ai > architect > backend > payment > other
    if is_manager:
        family = "管理/负责人"
    elif is_agent:
        family = "AI/Agent"
    elif is_ai:
        family = "AI/算法/平台"
    elif is_architect:
        family = "架构/专家"
    elif is_backend or is_java:
        family = "Java/后端"
    elif is_payment_risk:
        family = "支付/风控"
    else:
        family = "其他"

    tags = []
    for flag, name in [
        (is_agent, "Agent"), (is_ai, "AI"), (is_java, "Java"),
        (is_backend, "后端"), (is_architect, "架构/专家"),
        (is_manager, "管理"), (is_payment_risk, "支付/风控"),
        (is_remote, "远程"),
    ]:
        if flag:
            tags.append(name)

    jd_norm = re.sub(r"\s+", "", jd)
    return {
        "job_id": f"liepin_{job_id}",
        "source_platform": "liepin",
        "source_url": url,
        "company": company,
        "title": title,
        "role_family": family,
        "tags": "|".join(tags),
        "city": city_label,
        "salary_raw": salary_raw,
        "salary_min_cny": smin,
        "salary_max_cny": smax,
        "salary_months": months,
        "experience": experience,
        "education": education,
        "company_size": company_size,
        "team_size": "",
        "reports_to": "",
        "jd_text": jd,
        "jd_hash": hashlib.sha1(jd_norm.encode("utf-8")).hexdigest()[:16] if jd_norm else "",
        "category_url": category_url,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verification": "C",
        "status": "unknown",
        "notes": "",
    }


FIELDS = [
    "job_id", "source_platform", "source_url", "company", "title", "role_family",
    "tags", "city", "salary_raw", "salary_min_cny", "salary_max_cny", "salary_months",
    "experience", "education", "company_size", "team_size", "reports_to",
    "jd_text", "jd_hash", "category_url", "collected_at", "verification", "status", "notes",
]


def append_rows(rows: list[dict], out_csv: Path):
    exists = out_csv.exists() and out_csv.stat().st_size > 0
    with out_csv.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="sh", choices=list(CITY_SLUG))
    ap.add_argument("--max-categories", type=int, default=10)
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--max-jobs", type=int, default=100)
    ap.add_argument("--list-categories", action="store_true")
    ap.add_argument("--out", help="output CSV (default: <data-dir>/processed/jobs_master.csv)")
    ap.add_argument("--links-only", action="store_true")
    jp.add_argument(ap)
    args = ap.parse_args()
    data = jp.resolve(args.data_dir, produce=True)
    raw, proc = raw_dir(data), data / "processed"
    raw.mkdir(parents=True, exist_ok=True)
    proc.mkdir(parents=True, exist_ok=True)

    city_slug = CITY_SLUG[args.city]
    city_label = CITY_LABEL[args.city]
    city_url = f"https://www.liepin.com/{city_slug}/"
    city_cache = raw / f"{args.city}_city.html"
    city_html = fetch(city_url, city_cache)
    cats = extract_category_urls(city_html, city_slug)
    print(f"[{args.city}] categories matched: {len(cats)}", flush=True)
    if args.list_categories:
        for u in cats:
            print(u)
        return
    cats = cats[: args.max_categories]
    print(f"[{args.city}] crawling {len(cats)} categories", flush=True)

    links: list[str] = []
    seen = set()
    for ci, cat in enumerate(cats, 1):
        for pn in range(args.max_pages):
            page_url = cat if pn == 0 else f"{cat}pn{pn}/"
            cache = raw / args.city / f"{cat.rstrip('/').split('/')[-1]}_pn{pn}.html"
            try:
                ph = fetch(page_url, cache)
            except Exception as e:
                print(f"  ! {page_url}: {e}", flush=True)
                continue
            found = extract_job_links(ph)
            new = 0
            for u in found:
                jid = re.search(r"/job/(\d+)\.shtml", u).group(1)
                if jid not in seen:
                    seen.add(jid)
                    links.append(u)
                    new += 1
            print(f"  cat {ci}/{len(cats)} pn{pn}: +{new} (total {len(links)})", flush=True)
            if new < 3:
                break
    links_file = raw / f"links_{args.city}.jsonl"
    with links_file.open("w", encoding="utf-8") as f:
        for u in links:
            jid = re.search(r"/job/(\d+)\.shtml", u).group(1)
            f.write(json.dumps({"job_id": f"liepin_{jid}", "url": u, "city": city_label}, ensure_ascii=False) + "\n")
    print(f"[{args.city}] unique links: {len(links)} -> {links_file}", flush=True)
    if args.links_only:
        return
    links = links[: args.max_jobs] if args.max_jobs else links
    print(f"[{args.city}] detail jobs to fetch: {len(links)}", flush=True)

    out_csv = Path(args.out) if args.out else proc / "jobs_master.csv"
    rows, bad = [], 0
    for i, url in enumerate(links, 1):
        jid = re.search(r"/job/(\d+)\.shtml", url).group(1)
        cache = raw / args.city / f"job_{jid}.html"
        try:
            ph = fetch(url, cache)
            row = parse_detail(ph, url, city_label, "")
            if not row["title"] or not row["jd_text"]:
                bad += 1
                continue
            rows.append(row)
        except Exception as e:
            bad += 1
            print(f"  ! detail {url}: {e}", flush=True)
        if i % 10 == 0:
            print(f"  detail {i}/{len(links)} (ok={len(rows)}, bad={bad})", flush=True)
    append_rows(rows, out_csv)
    print(f"[{args.city}] done: rows={len(rows)} bad={bad} -> {out_csv}", flush=True)


if __name__ == "__main__":
    main()
