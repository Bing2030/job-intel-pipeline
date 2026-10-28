#!/usr/bin/env python3
# Bounded official JD collector: Tencent / Alibaba / ByteDance public APIs.
import json, csv, re, time, hashlib, uuid, urllib.request, urllib.parse
from datetime import datetime, timezone
from collections import Counter

import jobintel_paths as jp

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
KEYWORDS=['Agent','智能体','大模型','LLM','AI平台','RAG','Java','后端','架构师','技术专家','技术经理','技术总监']
CITIES=['上海','北京','深圳','杭州','新加坡','远程']
NEG=re.compile(r'产品经理|产品专家|产品总监|产品运营|运营|销售|商务|渠道|市场|品牌|客户|客服|支持|行政|hr|人力|招聘|财务|会计|审计|法务|律师|合规|实习|校招|兼职|应届|助理|专员|初级|管培',re.I)
TECH=re.compile(r'agent|智能体|大模型|llm|rag|mcp|java|后端|后台|服务端|架构|技术专家|技术经理|技术负责人|技术总监|研发|平台|算法|ai',re.I)
FIELDS=['job_id','source_platform','source_url','company','title','role_family','tags','city','salary_raw','salary_min_cny','salary_max_cny','salary_months','experience','education','company_size','team_size','reports_to','jd_text','jd_hash','category_url','collected_at','verification','status','notes']

def fetch(url, headers=None, data=None, timeout=15):
    h={'User-Agent':UA,'Accept':'application/json, text/plain, */*'}
    if headers: h.update(headers)
    req=urllib.request.Request(url,data=data,headers=h,method='POST' if data else 'GET')
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode('utf-8','ignore'))
def city_ok(s): return any(c in str(s) for c in CITIES)
def title_ok(t):
    t=str(t or '')
    return bool(TECH.search(t)) and not bool(NEG.search(t))
def fam(t):
    low=t.lower()
    if any(k in t for k in ['技术总监','研发总监','技术负责人','研发负责人','CTO','技术经理','研发经理','技术管理']): return '管理/负责人'
    if '架构' in t: return '架构/专家'
    if re.search(r'agent|智能体|大模型|llm|rag|mcp|ai平台|ai应用|ai开发',low): return 'AI/Agent'
    if re.search(r'java|后端|后台|服务端|分布式',low): return 'Java/后端'
    if '算法' in t: return 'AI/算法/平台'
    return '其他'
def add(rows, **kw):
    jd=str(kw.get('jd_text','')).strip()
    if not jd: return
    rows.append(dict(job_id=kw['job_id'],source_platform=kw['source_platform'],source_url=kw.get('source_url',''),company=kw['company'],
        title=kw['title'],role_family=fam(kw['title']),tags=kw.get('tags',''),city=kw.get('city',''),salary_raw='',salary_min_cny='',salary_max_cny='',
        salary_months='',experience=kw.get('experience',''),education='',company_size='',team_size='',reports_to='',jd_text=jd[:8000],
        jd_hash=hashlib.sha1(jd.encode()).hexdigest(),category_url='',collected_at=datetime.now(timezone.utc).isoformat(),
        verification='A',status='active',notes=kw.get('notes','official API')))

def tencent(max_pages=1):
    rows=[]
    for kw in KEYWORDS:
        for page in range(1,max_pages+1):
            url=f'https://careers.tencent.com/tencentcareer/api/post/Query?timestamp={int(time.time())}&keyword={urllib.parse.quote(kw)}&pageIndex={page}&pageSize=100&language=zh-cn&area=cn'
            try: d=fetch(url)
            except Exception as e: print('tencent err',kw,page,e,flush=True); break
            posts=(d.get('Data') or {}).get('Posts') or []
            if not posts: break
            for p in posts:
                title=p.get('RecruitPostName',''); loc='-'.join([p.get('CountryName') or '',p.get('LocationName') or ''])
                if not title_ok(title) or not city_ok(loc): continue
                add(rows, job_id='tencent_'+str(p.get('PostId')), source_platform='tencent_official',
                    source_url=p.get('PostURL') or 'https://careers.tencent.com/jobdesc.html?postId='+str(p.get('PostId')),
                    company='腾讯', title=title, city=loc, experience=p.get('RequireWorkYearsName',''), jd_text=p.get('Responsibility',''),
                    tags='腾讯官方', notes='Tencent Query API')
            print('tencent',kw,'page',page,'kept',len(rows),flush=True); time.sleep(0.4)
    return rows

def alibaba(max_pages=1):
    rows=[]; token=str(uuid.uuid4())
    for kw in KEYWORDS:
        for page in range(1,max_pages+1):
            body=json.dumps({'channel':'group_official_site','language':'zh','batchId':'','categories':'','deptCodes':[],'key':kw,'pageIndex':page,'pageSize':100,'regions':'','subCategories':''}).encode()
            try:
                d=fetch('https://talent.alibaba.com/position/search',headers={'Content-Type':'application/json','Cookie':f'XSRF-TOKEN={token}','x-xsrf-token':token},data=body)
            except Exception as e: print('ali err',kw,page,e,flush=True); break
            data=(d.get('content') or {}).get('datas') or []
            if not data: break
            for p in data:
                title=p.get('name',''); loc='/'.join(p.get('workLocations') or [])
                if not title_ok(title) or not city_ok(loc): continue
                jd='\n'.join([str(x) for x in [p.get('description',''),p.get('requirement','')] if x])
                exp=p.get('experience') or {}
                ex=f"{exp.get('from','')}-{exp.get('to','')}年" if exp else ''
                add(rows, job_id='alibaba_'+str(p.get('id')), source_platform='alibaba_official',
                    source_url='https://talent.alibaba.com/off-campus/position-detail?positionId='+str(p.get('id')),
                    company='阿里巴巴', title=title, city=loc, experience=ex, jd_text=jd, tags='阿里官方', notes='Alibaba position/search API')
            print('alibaba',kw,'page',page,'kept',len(rows),flush=True); time.sleep(0.4)
    return rows

def bytedance(max_pages=1):
    rows=[]
    headers={'Content-Type':'application/json','portal-channel':'society','portal-platform':'pc','website-path':'society','Origin':'https://jobs.bytedance.com','Referer':'https://jobs.bytedance.com/experienced/position'}
    for kw in KEYWORDS:
        for page in range(1,max_pages+1):
            body=json.dumps({'keyword':kw,'limit':100,'offset':(page-1)*100,'portal_type':3,'portal_entrance':1,'language':'zh','recruitment_id_list':['101'],'location_code_list':['CT_125','CT_11','CT_128','CT_52','CT_163']}).encode()
            try: d=fetch('https://jobs.bytedance.com/api/v1/search/job/posts',headers=headers,data=body)
            except Exception as e: print('bd err',kw,page,e,flush=True); break
            data=(d.get('data') or {}).get('job_post_list') or []
            if not data: break
            for p in data:
                title=p.get('title',''); cities=[c.get('name','') for c in (p.get('city_list') or [p.get('city_info') or {}])]; loc='/'.join([x for x in cities if x])
                if not title_ok(title) or not city_ok(loc): continue
                jd='\n'.join([str(x) for x in [p.get('description',''),p.get('requirement','')] if x])
                add(rows, job_id='bytedance_'+str(p.get('id')), source_platform='bytedance_official',
                    source_url=f"https://jobs.bytedance.com/experienced/position/{p.get('id')}/detail",
                    company='字节跳动', title=title, city=loc, jd_text=jd, tags='字节官方', notes='ByteDance society API')
            print('bytedance',kw,'page',page,'kept',len(rows),flush=True); time.sleep(0.4)
    return rows

def main():
    import argparse
    ap=argparse.ArgumentParser(description='Collect Tencent / Alibaba / ByteDance official JDs into <data-dir>/official'); ap.add_argument('--company',default='all'); ap.add_argument('--max-pages',type=int,default=1); jp.add_argument(ap); a=ap.parse_args()
    OUT=jp.resolve(a.data_dir,produce=True)/'official'; OUT.mkdir(parents=True,exist_ok=True)
    jobs=[]
    if a.company in ('all','tencent'): jobs+=tencent(a.max_pages)
    if a.company in ('all','alibaba'): jobs+=alibaba(a.max_pages)
    if a.company in ('all','bytedance'): jobs+=bytedance(a.max_pages)
    ded={}
    for r in jobs: ded.setdefault(r['job_id'],r)
    jobs=list(ded.values())
    # dedupe by company/title/city
    seen=set(); out=[]
    for r in jobs:
        k=(r['company'],r['title'],r['city'])
        if k not in seen: seen.add(k); out.append(r)
    raw=OUT/'jobs_official_raw.csv'
    with raw.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(jobs)
    filt=OUT/'jobs_official.csv'
    with filt.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(out)
    print('RAW',len(jobs),'FILTERED',len(out),flush=True)
    print('by company',Counter(r['company'] for r in out),flush=True)
    print('by family',Counter(r['role_family'] for r in out),flush=True)
    print('by city',Counter(r['city'] for r in out).most_common(10),flush=True)

if __name__=='__main__': main()
