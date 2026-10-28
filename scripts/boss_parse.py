#!/usr/bin/env python3
# Parse a saved BOSS search-results DOM (from CDP) into <data-dir>/processed/jobs_boss.csv.
import argparse, csv, re, time
from pathlib import Path
from lxml import html as lxml_html
import jobintel_paths as jp

PUA = {0xE031+i: str(i) for i in range(10)}
FIELDS = ["job_id","source_platform","source_url","company","title","role_family","tags","city",
          "salary_raw","salary_min_cny","salary_max_cny","salary_months","experience","education",
          "company_size","team_size","reports_to","jd_text","jd_hash","category_url","collected_at",
          "verification","status","notes"]

def decode(s):
    return ''.join(PUA.get(ord(c), c) for c in s)

def salary(raw):
    t = raw.replace(' ', '')
    m = re.search(r'(\d+)-(\d+)K·(\d+)薪', t)
    if m:
        return int(m.group(1))*1000*int(m.group(3)), int(m.group(2))*1000*int(m.group(3)), int(m.group(3))
    m = re.search(r'(\d+)-(\d+)K', t)
    if m:
        return int(m.group(1))*1000*12, int(m.group(2))*1000*12, 12
    m = re.search(r'(\d+)K', t)
    if m:
        return int(m.group(1))*1000*12, int(m.group(1))*1000*12, 12
    return None, None, None

def classify(title):
    low = title.lower()
    if any(k in title for k in ['技术经理','研发经理','技术负责人','研发负责人','技术总监','研发总监','负责人']): fam='管理/负责人'
    elif any(k in low for k in ['agent','智能体','大模型','llm','rag']): fam='AI/Agent'
    elif any(k in low for k in ['算法','ai','模型','多模态','语音','推荐']): fam='AI/算法/平台'
    elif any(k in title for k in ['架构师','架构','专家']): fam='架构/专家'
    elif any(k in low for k in ['java','后端','服务端','分布式','微服务']): fam='Java/后端'
    elif any(k in title for k in ['风控','支付','清结算','合规']): fam='支付/风控'
    else: fam='其他'
    tags=[x for x in ['Agent' if 'agent' in low else '', 'AI' if any(k in low for k in ['ai','算法','大模型','llm']) else '', 'Java' if 'java' in low else '', '管理' if '经理' in title or '负责人' in title or '总监' in title else '', '架构/专家' if '架构' in title or '专家' in title else ''] if x]
    return fam, '|'.join(tags)

def main():
    ap = argparse.ArgumentParser(description='Parse a saved BOSS search-results DOM into <data-dir>/processed/jobs_boss.csv')
    ap.add_argument('html', help='saved search-results HTML (e.g. captured with cdp_fetch.mjs)')
    jp.add_argument(ap); args = ap.parse_args()
    out = jp.resolve(args.data_dir, produce=True) / 'processed' / 'jobs_boss.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    dom = Path(args.html).read_text(errors='ignore')
    tree = lxml_html.fromstring(dom)
    cards = tree.xpath('//div[contains(@class,"job-card-wrap")]') or tree.xpath('//li[contains(@class,"job-card-box")]')
    rows=[]
    seen=set()
    for c in cards:
        a = c.xpath('.//a[contains(@class,"job-name")]')
        if not a: continue
        href = a[0].get('href','')
        if not href or href in seen: continue
        seen.add(href)
        jid = re.search(r'/job_detail/([^.]+)\.html', href)
        jid = jid.group(1) if jid else href
        title=' '.join(a[0].xpath('.//text()')).strip()
        sal_raw = decode(' '.join(c.xpath('.//span[contains(@class,"job-salary")]//text()')).strip())
        smin,smax,months=salary(sal_raw)
        tags=[t.strip() for t in c.xpath('.//ul[contains(@class,"tag-list")]//li//text()') if t.strip()]
        exp=tags[0] if tags else ''; edu=tags[1] if len(tags)>1 else ''
        company=' '.join(c.xpath('.//span[contains(@class,"boss-name")]//text()')).strip()
        city=' '.join(c.xpath('.//span[contains(@class,"company-location")]//text()')).strip()
        fam,ftags=classify(title)
        jd=f"{title} {exp} {edu} {company} {city}"
        rows.append({'job_id':f'boss_{jid}','source_platform':'boss','source_url':'https://www.zhipin.com'+href,
            'company':company,'title':title,'role_family':fam,'tags':ftags,'city':city,
            'salary_raw':sal_raw,'salary_min_cny':smin or '','salary_max_cny':smax or '','salary_months':months or '',
            'experience':exp,'education':edu,'company_size':'','team_size':'','reports_to':'',
            'jd_text':jd,'jd_hash':'','category_url':'','collected_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'verification':'C','status':'active','notes':'BOSS search page; salary decoded from kanzhun-mix font'})
    with out.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print('rows',len(rows),'->',out)

if __name__=='__main__': main()
