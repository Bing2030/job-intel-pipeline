#!/usr/bin/env python3
# Strict review/filter for official JDs (A-level) against candidate target roles.
import argparse, re
import pandas as pd
import jobintel_paths as jp
ap=argparse.ArgumentParser(description='Filter <data-dir>/official/jobs_official_all.csv into jobs_official_filtered.csv / _target_level.csv / _removed.csv / .xlsx'); jp.add_argument(ap); args=ap.parse_args()
D=jp.resolve(args.data_dir,produce=False)/'official'
if not (D/'jobs_official_all.csv').exists():
    raise SystemExit(f'{D/"jobs_official_all.csv"} not found: run merge_official.py (same --data-dir) first.')
a=pd.read_csv(D/'jobs_official_all.csv',dtype=str).fillna('')
TARGET_CITIES=['上海','北京','深圳','杭州','新加坡','远程']

def city_norm(s):
    found=[c for c in TARGET_CITIES if c in str(s)]
    return '/'.join(found) if found else str(s)

NON_TECH=re.compile(r'产品|运营|销售|商务|bd|渠道|市场|品牌|客户|客服|支持|行政|hr|人力|招聘|财务|会计|审计|法务|律师|合规|投资|金融|量化|ir|pr|公关|设计|策划|叙事|采购|供应链|物流|仓储|门店|督导|商业分析|战略|分析师|咨询|助理|专员|初级|管培|实习|校招|intern|trainee|应届|兼职',re.I)
ROLE_NOISE=re.compile(r'测试|测开|qa|质量|前端|客户端|android|ios|桌面端|electron|嵌入式|硬件|运维|sre|安全|solution|解决方案|售前|交付|顾问|实施|技术支持|行业云|业务架构|产品架构|数据安全',re.I)
RESEARCH=re.compile(r'研究员|科学家|预训练|训练|rlhf|cv|视觉|语音|推荐|广告|搜索算法|多模态|自动驾驶|感知|决策规划|机器人|slam|世界模型|具身',re.I)
HARDWARE=re.compile(r'操作系统|内核|驱动|虚拟化|芯片|硬件|整机|服务器结构|服务器研发|服务器系统|数字后端|pcb|光互联|idc|给排水|暖通|电气|建筑|光子集成|noc|网络系统|网络架构|通信|桌面端|electron|risc|cot|基础软件|cpu|机房|数据中心',re.I)
SOLUTION=re.compile(r'解决方案|售前|交付|咨询|fde|tam|技术服务|迁移|talent|招聘|项目经理',re.I)
SECURITY=re.compile(r'安全|反爬虫',re.I)
ARCH_DOMAIN=re.compile(r'软件|系统|平台|分布式|云原生|数据|存储|数据库|后端|java|ai|agent|llm|大模型|基础设施|infra|推理|框架|jvm|中间件|微服务|可观测|aigc|数字人',re.I)
JUNIOR=re.compile(r'实习|校招|intern|trainee|应届|兼职|助理|专员|初级|管培',re.I)
SENIOR=re.compile(r'架构|专家|经理|负责人|总监|cto|首席|资深|高级|staff|principal|lead|leader',re.I)
AI=re.compile(r'agent|智能体|llm|大模型|rag|mcp|harness|mlops|推理|ai平台|ai\s*平台|ai应用|ai\s*应用|ai开发|ai架构|ai工程|agent平台|agent\s*平台|agent\s*infra|基础设施|infra',re.I)
JB=re.compile(r'java|后端|后台|服务端|分布式|微服务|中间件|高并发',re.I)
ARCH=re.compile(r'架构师|架构|技术专家',re.I)
MGR=re.compile(r'技术总监|技术经理|技术负责人|研发负责人|研发总监|工程总监|cto|技术管理',re.I)
PAY=re.compile(r'支付|清结算|风控|决策引擎|规则引擎|反欺诈|交易系统',re.I)
TECH_DOMAIN=re.compile(r'agent|智能体|大模型|llm|rag|mcp|java|后端|服务端|架构|平台|系统|分布式|基础设施|infra|支付|风控|数据|算法|研发|技术',re.I)

def decide(r):
    title=str(r.title); low=title.lower(); text=(title+' '+str(r.jd_text)).lower()
    city=city_norm(r.city)
    if not any(c in city for c in TARGET_CITIES): return False,'city'
    if JUNIOR.search(title): return False,'junior'
    if NON_TECH.search(title) and not (re.search(r'开发|研发|工程师|架构师|技术专家|agent|智能体',title,re.I) and not re.search(r'产品经理|产品专家|产品负责人|产品运营|运营|销售|商务|人力|招聘|财务|法务',title,re.I)):
        return False,'non_tech_title'
    if HARDWARE.search(title) and not re.search(r'agent|智能体|ai\s*infra|agent\s*infra|平台研发',title,re.I): return False,'hardware_or_idc'
    if SOLUTION.search(title): return False,'solution_or_delivery'
    if SECURITY.search(title) and not re.search(r'agent|智能体|大模型|llm|infra|平台|研发',title,re.I): return False,'security'
    if re.search(r'全栈',title,re.I) and not re.search(r'agent|智能体|大模型|llm|ai应用|ai开发|ai平台|infra',title,re.I): return False,'fullstack_non_target'
    if re.search(r'评测',title,re.I) and not re.search(r'agent|智能体|大模型|llm',title,re.I): return False,'non_target_role'
    if ROLE_NOISE.search(title): return False,'non_target_role'
    if re.search(r'稳定性方向',title,re.I) and not re.search(r'agent|智能体|infra|平台|架构',title,re.I): return False,'generic_stability'
    if re.search(r'后训练|预训练|post-training|rlhf|训练框架',title,re.I) and not re.search(r'infra|平台|工程',title,re.I):
        return False,'research_role'
    if re.search(r'研究员|科学家|算法',title,re.I) and not re.search(r'agent|智能体|llm应用|大模型应用|rag|ai平台|agent平台|agent\s*infra|mlops|ai\s*infra|应用开发|应用工程|平台|架构',title,re.I):
        return False,'pure_research_or_algo'
    if re.search(r'视觉|语音|多模态|推荐|广告|搜索|自动驾驶|感知|决策规划|机器人|slam|世界模型|具身',title,re.I) and not re.search(r'开发|研发|工程师|后端|服务端|平台|架构|infra|agent',title,re.I):
        return False,'pure_research_or_algo'
    is_ai=bool(AI.search(title+' '+str(r.jd_text)))
    is_jb=bool(JB.search(title))
    is_arch=bool(ARCH.search(title)) and bool(ARCH_DOMAIN.search(title))
    is_mgr=bool(MGR.search(title)) and bool(TECH_DOMAIN.search(title))
    is_pay=bool(PAY.search(title)) and bool(re.search(r'技术|架构|平台|系统|研发|开发|引擎|模型|数据',title,re.I))
    # pure AI/algorithm with no engineering/application/platform signal
    if re.search(r'算法',title) and not re.search(r'agent|智能体|llm应用|大模型应用|rag|ai平台|agent平台|agent\s*infra|mlops|ai\s*infra|应用开发|应用工程|架构',title,re.I):
        return False,'generic_algo'
    if is_arch and re.search(r'解决方案|行业|业务|产品|售前|交付|运维',title,re.I):
        return False,'solution_or_ops_arch'
    if is_mgr and re.search(r'供应链|android|ios|前端|客户端|数据安全|安全',title,re.I):
        return False,'non_target_mgmt_domain'
    if not any([is_ai,is_jb,is_arch,is_mgr,is_pay]):
        return False,'not_target_domain'
    if not TECH_DOMAIN.search(title+' '+str(r.jd_text)):
        return False,'no_tech_signal'
    senior=bool(SENIOR.search(title))
    return True, ('target_senior' if senior else 'target_mid')

res=a.apply(decide,axis=1)
a['keep']=[x[0] for x in res]; a['filter_reason']=[x[1] for x in res]
a['city_norm']=a.city.map(city_norm)
a['senior_fit']=a.filter_reason.eq('target_senior')
keep=a[a.keep].copy(); removed=a[~a.keep].copy()
# dedupe company/title/city
keep=keep.drop_duplicates(['company','title','city_norm'])
def newfam(t):
    t=str(t); low=t.lower()
    if MGR.search(t): return '管理/负责人'
    if ARCH.search(t): return '架构/专家'
    if AI.search(t): return 'AI/Agent'
    if JB.search(t): return 'Java/后端'
    if PAY.search(t): return '支付/风控'
    return '其他'
keep['role_family']=keep.title.map(newfam)
keep=keep[keep.role_family!='其他'].copy()
# target level: senior title only; mid kept in relevant but not target-level
target=keep[keep.senior_fit].copy()
keep.to_csv(D/'jobs_official_filtered.csv',index=False,encoding='utf-8-sig')
target.to_csv(D/'jobs_official_filtered_target_level.csv',index=False,encoding='utf-8-sig')
removed.to_csv(D/'jobs_official_removed.csv',index=False,encoding='utf-8-sig')
with pd.ExcelWriter(D/'jobs_official_filtered.xlsx',engine='openpyxl') as w:
    keep.to_excel(w,sheet_name='filtered_relevant',index=False)
    target.to_excel(w,sheet_name='target_level',index=False)
    removed[['company','title','role_family','city','filter_reason','source_platform','source_url']].to_excel(w,sheet_name='removed',index=False)
    keep.groupby(['company','role_family']).size().reset_index(name='count').to_excel(w,sheet_name='company_family',index=False)
    removed.filter_reason.value_counts().rename_axis('reason').reset_index(name='count').to_excel(w,sheet_name='removed_reasons',index=False)
print('all',len(a),'KEEP relevant',len(keep),'TARGET level',len(target),'REMOVED',len(removed))
print('\nkeep family'); print(keep.role_family.value_counts().to_string())
print('\nremoved reasons'); print(removed.filter_reason.value_counts().to_string())
print('\nkeep sample:'); print(keep[['company','title','role_family','city_norm']].sample(min(25,len(keep)),random_state=1).to_string())
print('\nremoved sample:'); print(removed[['company','title','filter_reason']].sample(min(25,len(removed)),random_state=2).to_string())
