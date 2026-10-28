#!/usr/bin/env python3
# Merge the per-source official CSVs in <data-dir>/official into jobs_official_all / _target + xlsx.
import argparse, re
import pandas as pd
import jobintel_paths as jp
ap=argparse.ArgumentParser(description='Merge per-source official CSVs in <data-dir>/official into jobs_official_all.csv / jobs_official_target.csv / jobs_official.xlsx'); jp.add_argument(ap); args=ap.parse_args()
DATA=jp.resolve(args.data_dir,produce=False); D=DATA/'official'
NO_SOURCES=f'No official source files with rows in {D}. Run run_pipeline.py (or official_collect_v2.py --company all, official_collect_v3.py, official_feishu_startups.py, official_moka_collect.py with the same --data-dir) first.'
FILES=['jobs_official_raw.csv','_batch2_raw.csv','jobs_official_tencent.csv','jobs_official_alibaba.csv','jobs_official_bytedance.csv','jobs_official_startups.csv','jobs_official_moonshot.csv']
frames=[]; loaded_official=0
for f in FILES:
 p=D/f
 if p.exists():
  d=pd.read_csv(p,dtype=str).fillna('')
  if len(d):
   d['source_file']=f; frames.append(d); loaded_official+=1
if loaded_official==0:
 raise SystemExit(NO_SOURCES)
# meituan official rows (optional): they come from the third-party chain's processed/jobs_master_merged.csv
mp=DATA/'processed/jobs_master_merged.csv'
if mp.exists():
 m=pd.read_csv(mp,dtype=str).fillna('')
 m=m[m.source_platform=='meituan'].copy()
 if len(m):
  m['company']='美团'; m['source_platform']='meituan_official'; m['verification']='A'; m['source_file']='jobs_master_merged:meituan'
  frames.append(m)
if not frames:
 raise SystemExit(NO_SOURCES)
d=pd.concat(frames,ignore_index=True).drop_duplicates('job_id')
TARGET=['上海','北京','深圳','杭州','新加坡','远程']
def norm_city(s):
 found=[c for c in TARGET if c in str(s)]
 return '/'.join(found) if found else str(s)
d['city_norm']=d.city.map(norm_city)
# target only
target_fams=['AI/Agent','Java/后端','架构/专家','管理/负责人','支付/风控','AI/算法/平台']
d['is_target']=d.role_family.isin(target_fams) & d.city_norm.str.contains('|'.join(TARGET),na=False)
# basic seniority excludes for target
NEG=re.compile(r'实习|校招|兼职|应届|助理|专员|初级|管培|intern|trainee',re.I)
d['is_target']=d.is_target & ~d.title.str.contains(NEG,na=False)
d.to_csv(D/'jobs_official_all.csv',index=False,encoding='utf-8-sig')
t=d[d.is_target].copy().drop_duplicates(['company','title','city_norm'])
t.to_csv(D/'jobs_official_target.csv',index=False,encoding='utf-8-sig')
print('ALL',len(d),'TARGET',len(t))
print('\nby company'); print(t.company.value_counts().to_string())
print('\nby family'); print(t.role_family.value_counts().to_string())
print('\nby city'); print(t.city_norm.value_counts().head(10).to_string())
print('\nby source'); print(t.source_file.value_counts().to_string())
print('\nJD len >=200', (t.jd_text.str.len()>=200).sum(), '/',len(t))
# excel
with pd.ExcelWriter(D/'jobs_official.xlsx',engine='openpyxl') as w:
 d.to_excel(w,sheet_name='all_official',index=False)
 t.to_excel(w,sheet_name='target_official',index=False)
 t.groupby(['company','role_family']).size().reset_index(name='count').to_excel(w,sheet_name='company_family',index=False)
 t.groupby('city_norm').size().reset_index(name='count').sort_values('count',ascending=False).to_excel(w,sheet_name='city',index=False)
print('\nsample:'); print(t[['company','title','role_family','city_norm']].head(25).to_string())
