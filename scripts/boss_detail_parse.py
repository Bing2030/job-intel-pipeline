#!/usr/bin/env python3
# Parse captured BOSS detail pages (<data-dir>/raw/boss/details/<job_id>.html) into jobs_boss_detail.csv
import argparse, csv, re, sys, time
from pathlib import Path
from lxml import html as lxml_html
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from boss_parse import salary, classify, FIELDS
import jobintel_paths as jp

ap = argparse.ArgumentParser(description='Parse captured BOSS detail pages (<data-dir>/raw/boss/details/<job_id>.html, job_id as in jobs_boss_batch.csv) into <data-dir>/processed/jobs_boss_detail.csv')
ap.add_argument('--src', help='directory of captured detail pages (default: <data-dir>/raw/boss/details)')
jp.add_argument(ap); args = ap.parse_args()
DATA = jp.resolve(args.data_dir, produce=False)
PROC = DATA/'processed'
DETAILS = Path(args.src) if args.src else DATA/'raw/boss/details'
OUT = PROC/'jobs_boss_detail.csv'
if not (PROC/'jobs_boss_batch.csv').exists():
    raise SystemExit(f'{PROC/"jobs_boss_batch.csv"} not found: run boss_batch_parse.py (same --data-dir) first')
if not DETAILS.is_dir():
    raise SystemExit(f'no captured detail pages: {DETAILS} does not exist (save pages there, named <job_id>.html, or pass --src)')
BASE = pd.read_csv(PROC/'jobs_boss_batch.csv', dtype=str).fillna('')
base = {r['job_id']: r for _, r in BASE.iterrows()}
rows=[]
for f in sorted(DETAILS.glob('*.html')):
    jid=f.stem
    b=base.get(jid, {})
    dom=lxml_html.fromstring(f.read_text(errors='ignore'))
    # main detail header (job-primary) — avoid related-job salaries
    title=' '.join(dom.xpath('//div[contains(@class,"job-primary")]//h1//text() | //h1//text()')).strip() or b.get('title','')
    sal_raw=' '.join(dom.xpath('//div[contains(@class,"job-primary")]//span[contains(@class,"salary") and not(contains(@class,"similar"))]//text()')).strip() or b.get('salary_raw','')
    from boss_parse import decode
    sal_raw=decode(sal_raw)
    smin,smax,months=salary(sal_raw) if sal_raw else (None,None,None)
    company=' '.join(dom.xpath('//div[contains(@class,"job-primary")]//span[contains(@class,"brand-name")]//text() | //div[contains(@class,"company-info")]//span[contains(@class,"company-name")]//text()')).strip()
    if not company: company=b.get('company','')
    exp=' '.join(dom.xpath('//div[contains(@class,"job-primary")]//span[contains(@class,"text-experiece")]//text()')).strip() or b.get('experience','')
    edu=' '.join(dom.xpath('//div[contains(@class,"job-primary")]//span[contains(@class,"text-degree")]//text()')).strip() or b.get('education','')
    city=' '.join(dom.xpath('//div[contains(@class,"job-primary")]//a[contains(@class,"text-city")]//text()')).strip() or b.get('city','')
    # JD: longest job-sec-text node
    cands=[' '.join(n.text_content().split()) for n in dom.xpath('//div[contains(@class,"job-sec-text")]')]
    jd=max(cands, key=len) if cands else ''
    if not jd:
        text=' '.join(dom.text_content().split())
        m=re.search(r'职位描述(.*?)(?:竞争力分析|公司介绍|工作地址)',text)
        jd=m.group(1).strip() if m else ''
    # clean watermark artifacts
    jd=re.sub(r'boss\s*直聘|BOSS\s*直聘','',jd,flags=re.I)
    jd=re.sub(r'直聘|boss','',jd,flags=re.I)
    jd=re.sub(r'\s+',' ',jd).strip()
    fam,ftags=classify(title)
    rows.append({'job_id':jid,'source_platform':'boss','source_url':b.get('source_url',f'https://www.zhipin.com/job_detail/{jid.replace("boss_","")}.html'),
        'company':company,'title':title,'role_family':fam,'tags':ftags,'city':city,
        'salary_raw':sal_raw,'salary_min_cny':smin or b.get('salary_min_cny',''),'salary_max_cny':smax or b.get('salary_max_cny',''),'salary_months':months or b.get('salary_months',''),
        'experience':exp,'education':edu,'company_size':'','team_size':'','reports_to':'',
        'jd_text':jd,'jd_hash':str(abs(hash(jd)))[:16],'category_url':b.get('category_url',''),'collected_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'verification':'C','status':'active','notes':'BOSS detail page; full JD'})
with OUT.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
print('details',len(rows),'with jd>=200',sum(1 for r in rows if len(r['jd_text'])>=200),'->',OUT)
