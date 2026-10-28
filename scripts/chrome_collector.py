#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome-headless based collector for Liepin public pages.

Use when plain HTTP gets the security page. Public pages only; no login bypass.
Runs one Chrome headless process per URL (simple, slower, reliable).

Modes:
  links:   city page -> categories -> pagination -> links jsonl
  details: links jsonl -> full JD details -> CSV

Examples (use the same --data-dir for both steps):
  python3 job-intel-pipeline/scripts/chrome_collector.py --mode links --city sh --max-categories 24 --max-pages 2 --data-dir DIR
  python3 job-intel-pipeline/scripts/chrome_collector.py --mode details --max-jobs 300 --data-dir DIR
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import shutil
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from liepin_scraper import (  # noqa: E402
    CITY_LABEL, CITY_SLUG, append_rows, extract_category_urls,
    extract_job_links, parse_detail, raw_dir,
)
import jobintel_paths as jp  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = Path(tempfile.gettempdir()) / "chrome-prof-jobintel"


def chrome_dom(url: str, cache: Path | None = None, timeout: int = 55, retries: int = 2) -> str:
    if cache and cache.exists() and cache.stat().st_size > 20000:
        return cache.read_text(errors="ignore")
    for attempt in range(retries + 1):
        profile = Path(tempfile.mkdtemp(prefix="chrome-jobintel-"))
        cmd = [
            CHROME, "--headless", "--disable-gpu", "--no-sandbox",
            "--disable-dev-shm-usage", "--no-first-run", "--disable-extensions",
            "--disable-background-networking",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=3000",
            "--dump-dom", url,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout)
            text = r.stdout.decode("utf-8", errors="ignore")
            if len(text) > 20000 and "猎聘安全中心" not in text:
                if cache:
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_text(text)
                time.sleep(0.8 + random.random() * 0.6)
                return text
            print(f"  ! blocked/short ({len(text)}) {url}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"  ! chrome timeout {url}", flush=True)
        finally:
            shutil.rmtree(profile, ignore_errors=True)
        time.sleep(2 + attempt * 2)
    return ""


def collect_links(raw: Path, city: str, max_categories: int, max_pages: int):
    slug = CITY_SLUG[city]
    label = CITY_LABEL[city]
    city_url = f"https://www.liepin.com/{slug}/"
    city_cache = raw / f"{city}_city_chrome.html"
    city_html = chrome_dom(city_url, city_cache)
    if not city_html:
        raise SystemExit(f"city page failed: {city}")
    cats = extract_category_urls(city_html, slug)[:max_categories]
    print(f"[{city}] categories: {len(cats)}", flush=True)
    links, seen = [], set()
    for ci, cat in enumerate(cats, 1):
        for pn in range(max_pages):
            page_url = cat if pn == 0 else f"{cat}pn{pn}/"
            cache = raw / city / f"{cat.rstrip('/').split('/')[-1]}_chrome_pn{pn}.html"
            dom = chrome_dom(page_url, cache)
            if not dom:
                continue
            found = extract_job_links(dom)
            new = 0
            for u in found:
                jid = re.search(r"/job/(\d+)\.shtml", u).group(1)
                if jid not in seen:
                    seen.add(jid)
                    links.append(u)
                    new += 1
            print(f"  cat {ci}/{len(cats)} pn{pn}: +{new} total={len(links)}", flush=True)
    links_file = raw / f"links_{city}_chrome.jsonl"
    with links_file.open("w", encoding="utf-8") as f:
        for u in links:
            jid = re.search(r"/job/(\d+)\.shtml", u).group(1)
            f.write(json.dumps({"job_id": f"liepin_{jid}", "url": u, "city": label}, ensure_ascii=False) + "\n")
    print(f"[{city}] unique links={len(links)} -> {links_file}", flush=True)


def collect_details(raw: Path, max_jobs: int, out: Path):
    links = []
    for p in sorted(raw.glob("links_*_chrome.jsonl")):
        for line in p.read_text().splitlines():
            try:
                links.append(json.loads(line))
            except Exception:
                pass
    # stable de-dupe by URL
    seen, uniq = set(), []
    for x in links:
        u = x.get("url")
        if u and u not in seen:
            seen.add(u)
            uniq.append(x)
    uniq = uniq[:max_jobs]
    print(f"details: {len(uniq)} jobs", flush=True)
    rows, bad = [], 0
    for i, x in enumerate(uniq, 1):
        jid = x["job_id"].replace("liepin_", "")
        cache = raw / "details_chrome" / f"{jid}.html"
        dom = chrome_dom(x["url"], cache)
        if not dom:
            bad += 1
            continue
        try:
            row = parse_detail(dom, x["url"], x.get("city", ""), "")
            if not row["title"] or not row["jd_text"]:
                bad += 1
                continue
            rows.append(row)
        except Exception as e:
            bad += 1
            print(f"  ! parse {x['url']}: {e}", flush=True)
        if i % 10 == 0:
            print(f"  detail {i}/{len(uniq)} ok={len(rows)} bad={bad}", flush=True)
            append_rows(rows, out)
            rows = []
    if rows:
        append_rows(rows, out)
    print(f"done: ok={len(rows)} bad={bad} -> {out}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["links", "details"], required=True)
    ap.add_argument("--city", default="sh", choices=list(CITY_SLUG))
    ap.add_argument("--max-categories", type=int, default=24)
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--max-jobs", type=int, default=300)
    ap.add_argument("--out", help="details CSV (default: <data-dir>/processed/jobs_chrome.csv)")
    jp.add_argument(ap)
    args = ap.parse_args()
    data = jp.resolve(args.data_dir, produce=(args.mode == "links"))
    raw = raw_dir(data)
    if args.mode == "links":
        raw.mkdir(parents=True, exist_ok=True)
        collect_links(raw, args.city, args.max_categories, args.max_pages)
    else:
        if not list(raw.glob("links_*_chrome.jsonl")):
            raise SystemExit(f"no links_*_chrome.jsonl in {raw}: run --mode links (same --data-dir) first")
        out = Path(args.out) if args.out else data / "processed" / "jobs_chrome.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        collect_details(raw, args.max_jobs, out)


if __name__ == "__main__":
    main()
