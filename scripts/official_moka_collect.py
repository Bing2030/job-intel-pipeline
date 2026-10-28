#!/usr/bin/env python3
# Render public Moka career page with headless Chrome, parse job cards.
import argparse, subprocess, re, csv, hashlib, shutil, tempfile
from datetime import datetime, timezone
import lxml.html as LH
import jobintel_paths as jp
CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
TARGET_CITIES=['上海','北京','深圳','杭州','新加坡','远程']
# Moonshot selected target technical roles (exclude product/ops/PR/HR/design/test/investment)
INCLUDE=re.compile(r'Agent|智能体|大模型|LLM|后端|服务端|架构|Infra|RL|全栈|平台',re.I)
EXCLUDE=re.compile(r'产品|运营|销售|商务|市场|品牌|PR|HR|人力|招聘|投资|设计|测试|研究科学家|算法研究员|算法工程师|Post-Training|Data|创作者|Taste|Business|Vertical|Head of|Manager',re.I)

def render(url,dump):
    prof=tempfile.mkdtemp(prefix='moka-profile-')
    try:
        r=subprocess.run([CHROME,'--headless=new','--no-sandbox','--disable-gpu','--user-data-dir='+prof,'--virtual-time-budget=12000','--dump-dom',url],
                         capture_output=True,timeout=45)
    finally:
        shutil.rmtree(prof,ignore_errors=True)
    html=r.stdout.decode('utf-8',errors='ignore')
    dump.parent.mkdir(parents=True,exist_ok=True); dump.write_text(html,encoding='utf-8')
    return html

def main():
    ap=argparse.ArgumentParser(description='Collect Moonshot official JDs from the public Moka page (headless Chrome) into <data-dir>/official/jobs_official_moonshot.csv'); jp.add_argument(ap); args=ap.parse_args()
    data=jp.resolve(args.data_dir,produce=True); OUT=data/'official'; OUT.mkdir(parents=True,exist_ok=True)
    url='https://app.mokahr.com/apply/moonshot/148506#/jobs'
    html=render(url,data/'raw/moka/moonshot_jobs.html'); doc=LH.fromstring(html)
    rows=[]; seen=set()
    for a in doc.xpath('//a[contains(@href,"#/job/")]'):
        href=a.get('href','')
        if href in seen: continue
        seen.add(href)
        title_nodes=a.xpath('.//span[contains(@class,"title-")]/text()')
        title=title_nodes[0].strip() if title_nodes else ''
        text=a.text_content().strip()
        if not title: continue
        if EXCLUDE.search(title) or not INCLUDE.search(title): continue
        # city: first Chinese target city in text, or target city anywhere
        city=next((c for c in TARGET_CITIES if c in text),'')
        jd=text
        jid=href.split('#/job/')[-1]
        rows.append({'job_id':'moonshot_'+jid,'source_platform':'moka_official','source_url':f'https://app.mokahr.com/apply/moonshot/148506#/job/{jid}',
            'company':'月之暗面 Moonshot','title':title.replace('急','').strip(),'role_family':'AI/Agent' if re.search(r'agent|智能体|大模型|llm',title,re.I) else ('Java/后端' if re.search(r'后端|服务端|java',title,re.I) else '架构/专家'),
            'tags':'AI创业公司官方','city':city,'salary_raw':'','salary_min_cny':'','salary_max_cny':'','salary_months':'','experience':'','education':'','company_size':'','team_size':'','reports_to':'',
            'jd_text':jd[:8000],'jd_hash':hashlib.sha1(jd.encode()).hexdigest(),'category_url':'','collected_at':datetime.now(timezone.utc).isoformat(),'verification':'A','status':'active','notes':'Moka public careers page via headless Chrome'})
    fields=['job_id','source_platform','source_url','company','title','role_family','tags','city','salary_raw','salary_min_cny','salary_max_cny','salary_months','experience','education','company_size','team_size','reports_to','jd_text','jd_hash','category_url','collected_at','verification','status','notes']
    with open(OUT/'jobs_official_moonshot.csv','w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    print('moonshot rows',len(rows)); [print(r['title'],r['city']) for r in rows]

if __name__=='__main__': main()
