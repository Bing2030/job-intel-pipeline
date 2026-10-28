#!/usr/bin/env python3
# Collect official JDs from AI startups using public Feishu Jobs APIs.
import argparse,json,csv,re,time,hashlib,urllib.request,urllib.parse
from datetime import datetime,timezone
from collections import Counter
import jobintel_paths as jp
ap=argparse.ArgumentParser(description='Collect MiniMax / 01.AI official JDs (Feishu Jobs API) into <data-dir>/official/jobs_official_startups.csv'); jp.add_argument(ap); args=ap.parse_args()
OUT=jp.resolve(args.data_dir,produce=True)/'official'; OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
KEYWORDS=['Agent','智能体','大模型','LLM','RAG','AI平台','Java','后端','架构师','技术专家','技术经理','技术总监']
CITIES=['上海','北京','深圳','杭州','新加坡','远程']
TENANTS=[('vrfi1sk8a0.jobs.feishu.cn','MiniMax'),('01ai.jobs.feishu.cn','01.AI 零一万物')]
NEG=re.compile(r'产品经理|产品专家|产品总监|产品运营|运营|销售|商务|渠道|市场|品牌|客户|客服|支持|行政|hr|人力|招聘|财务|会计|审计|法务|律师|合规|实习|校招|兼职|应届|助理|专员|初级|管培',re.I)
TECH=re.compile(r'agent|智能体|大模型|llm|rag|mcp|java|后端|后台|服务端|架构|技术专家|技术经理|技术负责人|技术总监|研发|平台|算法|ai',re.I)
FIELDS=['job_id','source_platform','source_url','company','title','role_family','tags','city','salary_raw','salary_min_cny','salary_max_cny','salary_months','experience','education','company_size','team_size','reports_to','jd_text','jd_hash','category_url','collected_at','verification','status','notes']
def fetch(url,headers,data,timeout=15):
 h={'User-Agent':UA,'Accept':'application/json, text/plain, */*'}; h.update(headers)
 req=urllib.request.Request(url,data=data,headers=h,method='POST')
 with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode('utf-8','ignore'))
def city_ok(s): return any(c in str(s) for c in CITIES)
def title_ok(t):
 t=str(t or ''); return bool(TECH.search(t)) and not bool(NEG.search(t))
def fam(t):
 low=t.lower()
 if any(k in t for k in ['技术总监','研发总监','技术负责人','研发负责人','CTO','技术经理','研发经理','技术管理']): return '管理/负责人'
 if '架构' in t: return '架构/专家'
 if re.search(r'agent|智能体|大模型|llm|rag|mcp|ai平台|ai应用|ai开发|ai服务端',low): return 'AI/Agent'
 if re.search(r'java|后端|后台|服务端|分布式',low): return 'Java/后端'
 if '算法' in t: return 'AI/算法/平台'
 return '其他'
rows=[]
for host,company in TENANTS:
 for kw in KEYWORDS:
  body=json.dumps({'keyword':kw,'limit':100,'offset':0,'portal_type':3,'portal_entrance':1,'language':'zh','recruitment_id_list':['101']}).encode()
  headers={'Content-Type':'application/json','portal-channel':'society','portal-platform':'pc','website-path':'index','Origin':f'https://{host}','Referer':f'https://{host}/index/'}
  try: d=fetch(f'https://{host}/api/v1/search/job/posts',headers,body)
  except Exception as e: print(company,kw,'ERR',e,flush=True); continue
  posts=(d.get('data') or {}).get('job_post_list') or []
  for p in posts:
   title=p.get('title',''); cities=[c.get('name','') for c in (p.get('city_list') or [p.get('city_info') or {}])]; loc='/'.join([x for x in cities if x])
   if not title_ok(title) or not city_ok(loc): continue
   jd='\n'.join([str(x) for x in [p.get('description',''),p.get('requirement','')] if x])
   if not jd: continue
   rows.append({'job_id':f"{company.split()[0].lower()}_{p.get('id')}",'source_platform':'feishu_official','source_url':f'https://{host}/index/','company':company,
    'title':title,'role_family':fam(title),'tags':'AI创业公司官方','city':loc,'salary_raw':'','salary_min_cny':'','salary_max_cny':'','salary_months':'',
    'experience':'','education':'','company_size':'','team_size':'','reports_to':'','jd_text':jd[:8000],'jd_hash':hashlib.sha1(jd.encode()).hexdigest(),
    'category_url':'','collected_at':datetime.now(timezone.utc).isoformat(),'verification':'A','status':'active','notes':f'Feishu jobs API {host}'})
  print(company,kw,'kept',len(rows),flush=True); time.sleep(0.35)
# dedupe
ded={r['job_id']:r for r in rows}; rows=list(ded.values())
with open(OUT/'jobs_official_startups.csv','w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
print('TOTAL',len(rows),Counter(r['company'] for r in rows),Counter(r['role_family'] for r in rows),flush=True)
