#!/usr/bin/env python3
# Render selected public Moka job detail pages and capture JD text.
import argparse,subprocess,re,csv,hashlib,shutil,tempfile
from datetime import datetime,timezone
import lxml.html as LH
import jobintel_paths as jp
CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
BASE='https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/'
JOBS=[
 ('2eb2e75d-29f3-47b5-bb10-39f12547d398','服务端开发工程师','Java/后端','北京市 杭州市'),
 ('bae809fb-1978-4401-b209-34067b26569d','Agent 弹性计算研发工程师','AI/Agent','北京市 杭州市'),
 ('1df4597d-6039-4392-9954-0df72510f415','AI 搜索算法 / 架构工程师','架构/专家','北京市'),
 ('8d40c764-d2b2-49b1-826c-e3f2adb75c01','Agent Harness 团队','AI/Agent','北京市 杭州市'),
 ('f763320c-7136-4d6e-9a0c-df4d25d1faa6','AI 云服务解决方案架构师','架构/专家','北京市 杭州市'),
 ('a63f2346-b672-4c48-af43-0a64bfe97a41','研发基础设施工程师','Java/后端','北京市 杭州市'),
 ('a7355097-fd57-4219-99a5-8963745d362f','高性能分布式存储工程师','Java/后端','杭州市'),
]
FIELDS=['job_id','source_platform','source_url','company','title','role_family','tags','city','salary_raw','salary_min_cny','salary_max_cny','salary_months','experience','education','company_size','team_size','reports_to','jd_text','jd_hash','category_url','collected_at','verification','status','notes']
def render(url,dump):
 prof=tempfile.mkdtemp(prefix='moka-detail-')
 try:
  r=subprocess.run([CHROME,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--user-data-dir='+prof,'--virtual-time-budget=12000','--dump-dom',url],capture_output=True,timeout=60)
 finally:
  shutil.rmtree(prof,ignore_errors=True)
 html=r.stdout.decode('utf-8',errors='ignore')
 dump.parent.mkdir(parents=True,exist_ok=True); dump.write_text(html,encoding='utf-8')
 return html
ap=argparse.ArgumentParser(description='Render selected Moka detail pages (headless Chrome) into <data-dir>/official/jobs_official_deepseek.csv (experimental)'); jp.add_argument(ap); args=ap.parse_args()
DATA=jp.resolve(args.data_dir,produce=True); OUT=DATA/'official'; OUT.mkdir(parents=True,exist_ok=True)
rows=[]
for i,(jid,title,fam,city) in enumerate(JOBS):
 try:
  html=render(BASE+jid,DATA/'raw/moka'/f'detail_{jid}.html')
  doc=LH.fromstring(html); text=doc.text_content()
  text=re.sub(r'\s+',' ',text)
  pos=min([p for p in [text.find('岗位职责'),text.find('职位描述'),text.find('工作职责')] if p>=0] or [-1])
  jd=text[pos:pos+6000] if pos>=0 else text[:6000]
  if len(jd)<100:
   print('short',title,len(jd)); continue
  # clean leading nav text up to role title
  rows.append({'job_id':'deepseek_'+jid,'source_platform':'moka_official','source_url':BASE+jid,'company':'DeepSeek 深度求索','title':title,'role_family':fam,
   'tags':'AI创业公司官方','city':city,'salary_raw':'','salary_min_cny':'','salary_max_cny':'','salary_months':'','experience':'','education':'','company_size':'','team_size':'','reports_to':'',
   'jd_text':jd,'jd_hash':hashlib.sha1(jd.encode()).hexdigest(),'category_url':'','collected_at':datetime.now(timezone.utc).isoformat(),'verification':'A','status':'active','notes':'Moka public job detail via headless Chrome'})
  print('kept',title,len(jd))
 except Exception as e: print('ERR',title,e)
with open(OUT/'jobs_official_deepseek.csv','w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
print('total',len(rows))
