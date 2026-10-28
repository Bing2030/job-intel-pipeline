#!/usr/bin/env python3
# Parse all saved BOSS search pages (<data-dir>/raw/boss/pages/<city>_<keyword>.html) into jobs_boss_batch.csv
import argparse, csv, re, sys, time
from pathlib import Path
from lxml import html as lxml_html
sys.path.insert(0, str(Path(__file__).resolve().parent))
from boss_parse import PUA, decode, salary, classify, FIELDS
import jobintel_paths as jp

ap = argparse.ArgumentParser(description='Parse saved BOSS search pages (<data-dir>/raw/boss/pages/<city>_<keyword>.html) into <data-dir>/processed/jobs_boss_batch.csv')
ap.add_argument('out', nargs='?', help='output CSV (default: <data-dir>/processed/jobs_boss_batch.csv)')
ap.add_argument('--src', help='directory of saved pages (default: <data-dir>/raw/boss/pages)')
jp.add_argument(ap); args = ap.parse_args()
DATA = jp.resolve(args.data_dir, produce=bool(args.src))
SRC = Path(args.src) if args.src else DATA / 'raw/boss/pages'
OUT = Path(args.out) if args.out else DATA / 'processed/jobs_boss_batch.csv'
if not SRC.is_dir():
    raise SystemExit(f'no saved BOSS pages: {SRC} does not exist (save search pages there, named <city>_<keyword>.html, or pass --src)')
OUT.parent.mkdir(parents=True, exist_ok=True)
rows, seen = [], set()
for f in sorted(SRC.glob('*.html')):
    stem = f.stem
    if '_' in stem:
        city, kw = stem.split('_', 1)
    else:
        city, kw = '', stem
    kw = kw.replace('_', ' ')
    dom = f.read_text(errors='ignore')
    tree = lxml_html.fromstring(dom)
    cards = tree.xpath('//div[contains(@class,"job-card-wrap")]') or tree.xpath('//li[contains(@class,"job-card-box")]')
    for c in cards:
        a = c.xpath('.//a[contains(@class,"job-name")]')
        if not a: continue
        href = a[0].get('href','')
        if not href or href in seen: continue
        seen.add(href)
        jid_m = re.search(r'/job_detail/([^.]+)\.html', href)
        jid = jid_m.group(1) if jid_m else str(abs(hash(href)))
        title = ' '.join(a[0].xpath('.//text()')).strip()
        sal_raw = decode(' '.join(c.xpath('.//span[contains(@class,"job-salary")]//text()')).strip())
        smin,smax,months=salary(sal_raw)
        tags=[t.strip() for t in c.xpath('.//ul[contains(@class,"tag-list")]//li//text()') if t.strip()]
        exp=tags[0] if tags else ''; edu=tags[1] if len(tags)>1 else ''
        company=' '.join(c.xpath('.//span[contains(@class,"boss-name")]//text()')).strip()
        city_raw=' '.join(c.xpath('.//span[contains(@class,"company-location")]//text()')).strip()
        fam,ftags=classify(title)
        jd=f"{title} {exp} {edu} {company} {city_raw}"
        rows.append({'job_id':f'boss_{jid}','source_platform':'boss','source_url':'https://www.zhipin.com'+href,
            'company':company,'title':title,'role_family':fam,'tags':ftags,'city':city_raw or city,
            'salary_raw':sal_raw,'salary_min_cny':smin or '','salary_max_cny':smax or '','salary_months':months or '',
            'experience':exp,'education':edu,'company_size':'','team_size':'','reports_to':'',
            'jd_text':jd,'jd_hash':str(abs(hash(jd)))[:16],'category_url':kw,'collected_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'verification':'C','status':'active','notes':'BOSS headed search; salary decoded'})
with OUT.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
print('files',len(list(SRC.glob('*.html'))),'rows',len(rows),'->',OUT)
