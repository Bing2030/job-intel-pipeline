#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch full Meituan JD detail pages for selected jobs (public pages, Chrome headless)."""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

from lxml import html as lxml_html

sys.path.insert(0, str(Path(__file__).resolve().parent))
from meituan_scraper import FIELDS, chrome_dom, raw_dir  # noqa: E402
import jobintel_paths as jp  # noqa: E402


def full_jd(dom: str) -> str:
    tree = lxml_html.fromstring(dom)
    for bad in tree.xpath("//script|//style|//noscript"):
        bad.drop_tree()
    text = re.sub(r"\s+", " ", tree.text_content())
    # choose the section after the last 岗位职责 (detail main content)
    starts = [m.start() for m in re.finditer("岗位职责", text)]
    if not starts:
        return ""
    start = starts[-1]
    tail = text[start:]
    ends = [tail.find(k) for k in ["岗位亮点", "公司介绍", "美团版权所有"] if tail.find(k) > 50]
    end = min(ends) if ends else min(len(tail), 6000)
    return tail[:end].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-jobs", type=int, default=300)
    ap.add_argument("--out", help="output CSV (default: <data-dir>/processed/jobs_meituan_detail.csv)")
    jp.add_argument(ap)
    args = ap.parse_args()
    data = jp.resolve(args.data_dir, produce=False)
    proc, raw = data / "processed", raw_dir(data)
    src = proc / "jobs_meituan.csv"
    if not src.exists():
        raise SystemExit(f"{src} not found: run meituan_scraper.py (same --data-dir) first")
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))
    # unique
    seen, uniq = set(), []
    for r in rows:
        jid = r.get("job_id", "")
        if jid and jid not in seen:
            seen.add(jid)
            uniq.append(r)
    # priority: AI/Agent, management, AI, architecture, Java, other
    prio = {"AI/Agent": 0, "管理/负责人": 1, "AI/算法/平台": 2, "架构/专家": 3, "Java/后端": 4}
    uniq.sort(key=lambda r: (prio.get(r.get("role_family", ""), 9), r.get("job_id", "")))
    uniq = uniq[: args.max_jobs]
    print(f"details: {len(uniq)}", flush=True)
    out = Path(args.out) if args.out else proc / "jobs_meituan_detail.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    exists = out.exists() and out.stat().st_size > 0
    f = out.open("a", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if not exists:
        w.writeheader()
    ok = bad = 0
    for i, r in enumerate(uniq, 1):
        jid = r.get("job_id", "").replace("meituan_", "")
        cache = raw / "details" / f"{jid}.html"
        dom = chrome_dom(r["source_url"], cache)
        jd = full_jd(dom) if dom else ""
        if not jd:
            bad += 1
            continue
        r = dict(r)
        r["jd_text"] = jd
        r["jd_hash"] = str(abs(hash(jd)))[:16]
        r["verification"] = "A"
        r["notes"] = (r.get("notes", "") + "; full JD detail").strip("; ")
        w.writerow({k: r.get(k, "") for k in FIELDS})
        ok += 1
        if i % 20 == 0:
            f.flush()
            print(f"  {i}/{len(uniq)} ok={ok} bad={bad}", flush=True)
    f.close()
    print(f"done ok={ok} bad={bad} -> {out}", flush=True)


if __name__ == "__main__":
    main()
