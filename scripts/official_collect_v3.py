#!/usr/bin/env python3
# Batch 2 official collectors: Ant / JD / Xiaohongshu / DeepSeek.
import json,csv,re,time,hashlib,urllib.request,urllib.parse
from datetime import datetime,timezone
from collections import Counter

import jobintel_paths as jp

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
KEYWORDS=['Agent','智能体','大模型','LLM','AI平台','RAG','Java','后端','架构师','技术专家','技术经理','技术总监','支付','风控']
CITIES=['上海','北京','深圳','杭州','新加坡','远程']
POS=re.compile(r'agent|智能体|llm|大模型|rag|mcp|harness|ai|java|后端|后台|服务端|架构|技术专家|技术经理|技术负责人|技术总监|平台|infra|推理|支付|风控|算法|研发|开发|工程师',re.I)
NEG=re.compile(r'产品|运营|销售|商务|市场|品牌|客户|客服|支持|行政|hr|人力|招聘|财务|会计|审计|法务|律师|合规|投资|设计|策划|采购|供应链|物流|测试|测开|qa|前端|客户端|android|ios|实习|校招|intern|应届|助理|专员|初级|管培',re.I)
FIELDS=['job_id','source_platform','source_url','company','title','role_family','tags','city','salary_raw','salary_min_cny','salary_max_cny','salary_months','experience','education','company_size','team_size','reports_to','jd_text','jd_hash','category_url','collected_at','verification','status','notes']
def fetch(url,headers=None,data=None,timeout=20):
 h={'User-Agent':UA,'Accept':'application/json, text/plain, */*'}; h.update(headers or {})
 req=urllib.request.Request(url,data=data,headers=h,method='POST' if data else 'GET')
 with urllib.request.urlopen(req,timeout=timeout) as r: return r.read().decode('utf-8','ignore')
def city_ok(s): return any(c in str(s) for c in CITIES)
def title_ok(t):
 t=str(t or ''); return bool(POS.search(t)) and not bool(NEG.search(t))
def fam(t):
 low=t.lower()
 if any(k in t for k in ['技术总监','研发总监','技术负责人','研发负责人','CTO','技术经理','研发经理','技术管理']): return '管理/负责人'
 if '架构' in t: return '架构/专家'
 if re.search(r'agent|智能体|llm|大模型|rag|mcp|ai平台|ai应用|ai开发|ai架构|infra|推理',low): return 'AI/Agent'
 if re.search(r'java|后端|后台|服务端|分布式',low): return 'Java/后端'
 if '算法' in t: return 'AI/算法/平台'
 if re.search(r'支付|清结算|风控',low): return '支付/风控'
 return '其他'
def add(rows, **kw):
 jd=str(kw.get('jd_text','')).strip()
 if not jd: return
 rows.append(dict(job_id=kw['job_id'],source_platform=kw['source_platform'],source_url=kw.get('source_url',''),company=kw['company'],
  title=kw['title'],role_family=fam(kw['title']),tags=kw.get('tags',''),city=kw.get('city',''),salary_raw='',salary_min_cny='',salary_max_cny='',salary_months='',
  experience=kw.get('experience',''),education=kw.get('education',''),company_size='',team_size='',reports_to='',jd_text=jd[:8000],
  jd_hash=hashlib.sha1(jd.encode()).hexdigest(),category_url='',collected_at=datetime.now(timezone.utc).isoformat(),verification='A',status='active',notes=kw.get('notes','official API')))

def collect_ant():
 rows=[]
 headers={'Content-Type':'application/json','Origin':'https://talent.antgroup.com','Referer':'https://talent.antgroup.com/off-campus-position'}
 for kw in KEYWORDS:
  for page in range(1,4):
   body=json.dumps({'language':'zh','pageSize':100,'pageIndex':page,'keyword':kw,'channel':'group_official_site'}).encode()
   try: d=json.loads(fetch('https://hrcareersweb.antgroup.com/api/social/position/search',headers,body))
   except Exception as e: print('ant err',kw,page,e,flush=True); break
   if d.get('success') is not True: print('ant business err',d.get('errorMsg'),flush=True); break
   arr=d.get('content') or []
   if not arr: break
   for p in arr:
    title=p.get('name',''); loc='/'.join(p.get('workLocations') or [])
    if not title_ok(title) or not city_ok(loc): continue
    jd='\n'.join([str(x) for x in [p.get('description',''),p.get('requirement','')] if x])
    exp=p.get('experience') or {}
    ex=f"{exp.get('from','')}-{exp.get('to','')}年" if exp else ''
    add(rows,job_id='ant_'+str(p.get('id')),source_platform='ant_official',source_url='https://talent.antgroup.com/off-campus-position',
     company='蚂蚁集团',title=title,city=loc,experience=ex,jd_text=jd,tags='蚂蚁官方',notes='Ant social position/search API')
   print('ant',kw,'page',page,'kept',len(rows),flush=True); time.sleep(1.2)
 return rows

def collect_jd():
 rows=[]
 headers={'Content-Type':'application/x-www-form-urlencoded','Referer':'https://zhaopin.jd.com/web/job/job_info_list/3','Origin':'https://zhaopin.jd.com'}
 for kw in KEYWORDS:
  for page in range(1,6):
   form={'pageIndex':str(page),'pageSize':'20','workCityJson':'[]','jobTypeJson':'[]','jobSearch':kw,'depTypeJson':'[]'}
   try: txt=fetch('https://zhaopin.jd.com/web/job/job_list',headers,urllib.parse.urlencode(form).encode())
   except Exception as e: print('jd err',kw,page,e,flush=True); break
   try: arr=json.loads(txt)
   except Exception: print('jd non-json',txt[:100],flush=True); break
   if not isinstance(arr,list) or not arr: break
   for p in arr:
    title=p.get('positionNameOpen') or p.get('positionName') or ''; loc=p.get('workCity','')
    if not title_ok(title) or not city_ok(loc): continue
    jd='\n'.join([str(x) for x in [p.get('workContent',''),p.get('qualification','')] if x])
    add(rows,job_id='jd_'+str(p.get('id') or p.get('positionId')),source_platform='jd_official',
     source_url='https://zhaopin.jd.com/web/job/job_info_list/3',company='京东',title=title,city=loc,jd_text=jd,
     experience=p.get('workExperience',''),tags='京东官方',notes='JD job_list API')
   print('jd',kw,'page',page,'kept',len(rows),flush=True); time.sleep(0.8)
 return rows

def collect_xhs():
 rows=[]
 headers={'Content-Type':'application/json','Origin':'https://job.xiaohongshu.com','Referer':'https://job.xiaohongshu.com/social/position'}
 for kw in KEYWORDS:
  for page in range(1,6):
   body=json.dumps({'positionName':kw,'pageNum':page,'pageSize':10,'recruitType':'social'}).encode()
   try: d=json.loads(fetch('https://job.xiaohongshu.com/websiterecruit/position/pageQueryPosition',headers,body))
   except Exception as e: print('xhs err',kw,page,e,flush=True); break
   data=d.get('data') or {}; arr=data.get('list') or []
   if not arr: break
   for p in arr:
    title=p.get('positionName',''); loc=p.get('workplace','')
    if not title_ok(title) or not city_ok(loc): continue
    jd='\n'.join([str(x) for x in [p.get('duty',''),p.get('qualification','')] if x])
    add(rows,job_id='xhs_'+str(p.get('positionId')),source_platform='xhs_official',
     source_url='https://job.xiaohongshu.com/social/position',company='小红书',title=title,city=loc,jd_text=jd,
     tags='小红书官方',notes='XHS pageQueryPosition API')
   print('xhs',kw,'page',page,'kept',len(rows),flush=True); time.sleep(2.0)
 return rows

def collect_deepseek():
 rows=[]; home=fetch('https://talent.deepseek.com/')
 m=re.search(r'src="(/static/main\.[a-f0-9]+\.js)"',home)
 if not m: print('deepseek bundle not found',flush=True); return rows
 js=fetch('https://talent.deepseek.com'+m.group(1))
 dec=json.JSONDecoder(); pos=0; objs=[]
 while True:
  i=js.find('{"id":"',pos)
  if i<0: break
  try:
   o,end=dec.raw_decode(js[i:]); objs.append(o); pos=i+end
  except Exception: pos=i+1
 for p in objs:
  title=p.get('title',''); locs=p.get('locations') or []
  loc='/'.join(locs) if isinstance(locs,list) else str(locs)
  if not title_ok(title) or not city_ok(loc): continue
  jd=re.sub(r'<[^>]+>',' ',str(p.get('descriptionHtml','')))
  jd=re.sub(r'\s+',' ',jd)
  add(rows,job_id='deepseek_'+str(p.get('id')),source_platform='deepseek_official',
   source_url='https://talent.deepseek.com/',company='DeepSeek 深度求索',title=title,city=loc,jd_text=jd,
   tags='DeepSeek官方',notes='talent.deepseek.com inline bundle')
 print('deepseek objects',len(objs),'kept',len(rows),flush=True)
 return rows

def main():
 import argparse
 ap=argparse.ArgumentParser(description='Collect Ant / JD / Xiaohongshu / DeepSeek official JDs into <data-dir>/official/_batch2_raw.csv'); jp.add_argument(ap); a=ap.parse_args()
 D=jp.resolve(a.data_dir,produce=True)/'official'; D.mkdir(parents=True,exist_ok=True)
 rows=[]
 for fn in [collect_ant,collect_jd,collect_xhs,collect_deepseek]:
  try: rows+=fn()
  except Exception as e: print('collector failed',fn.__name__,e,flush=True)
 ded={r['job_id']:r for r in rows}; rows=list(ded.values())
 with open(D/'_batch2_raw.csv','w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
 print('TOTAL',len(rows),Counter(r['company'] for r in rows),flush=True)

if __name__=='__main__': main()
