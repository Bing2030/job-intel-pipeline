#!/usr/bin/env python3
"""Validate the pipeline package: required files, manifests, syntax, portability, leaks.

Read-only. Syntax is checked with ast, so no .pyc is written (a .pyc embeds the absolute path of the machine it was built on).
"""
import ast, csv, os, re, sys
from pathlib import Path
sys.dont_write_bytecode=True
PKG=Path(__file__).resolve().parents[1]  # job-intel-pipeline/
REQ=['README.md','sources.csv','scripts.csv','WORKFLOW.md','DATA_SCHEMA.md','COMPLIANCE.md','TROUBLESHOOTING.md','requirements.txt']
TEXT=('.md','.py','.mjs','.csv','.txt')
SKIP_DIRS={'.git','.venv','venv','node_modules'}
HOME_PATH=re.compile(r"/Users/[^/\s'\"`]+|/home/[^/\s'\"`]+|[A-Za-z]:\\Users\\")   # absolute home dirs
PERSONAL=re.compile(r'现包|年包|总包|直接汇报')                                       # compensation / career-plan wording
SECRETISH=re.compile(r'^\.env|cookie|token|secret|credential|\.(pem|key|har|sqlite|db)$',re.I)
errs=[]; warns=[]
for f in REQ:
    if not (PKG/f).exists(): errs.append(f'missing {f}')
# manifest <-> scripts (both directions)
listed=set()
try:
    rows=list(csv.DictReader(open(PKG/'scripts.csv',encoding='utf-8-sig')))
    listed={r['script'] for r in rows}
    for name in sorted(listed):
        if not (PKG/'scripts'/name).exists(): errs.append(f'manifest missing script: {name}')
except Exception as e:
    errs.append(f'scripts.csv parse: {e}')
scripts=sorted(p for p in (PKG/'scripts').iterdir() if p.is_file() and p.suffix in ('.py','.mjs'))
for p in scripts:
    if listed and p.name not in listed: errs.append(f'script not in scripts.csv: {p.name}')
# syntax (ast only: nothing is written)
for p in scripts:
    if p.suffix!='.py': continue
    try: ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    except (SyntaxError,UnicodeDecodeError) as e: errs.append(f'syntax {p.name}: {e}')
# leaks / hygiene
pyc=False; data_dirs=[]
for dirpath,dirs,files in os.walk(PKG):
    for d in list(dirs):
        if d=='__pycache__': pyc=True
        if d.startswith('tmp-jobs-'): data_dirs.append(str((Path(dirpath)/d).relative_to(PKG)))
    dirs[:]=[d for d in dirs if d not in SKIP_DIRS and d!='__pycache__' and not d.startswith('tmp-jobs-')]
    for fn in files:
        p=Path(dirpath)/fn; rel=p.relative_to(PKG)
        if p.suffix=='.pyc': pyc=True; continue
        if SECRETISH.search(fn): errs.append(f'secret/cookie/raw-data file in package: {rel}')
        elif p.suffix.lower() in ('.html','.htm'): warns.append(f'raw/cache file in package: {rel}')
        if p.stat().st_size>10*1024*1024: warns.append(f'large file: {rel}')
        if not p.stat().st_mode&0o044: warns.append(f'not readable by other users (mode {oct(p.stat().st_mode&0o777)}): {rel}')
        if p.suffix.lower() not in TEXT or p.name=='validate_pipeline.py': continue
        try: t=p.read_text(encoding='utf-8',errors='ignore')
        except OSError: continue
        if HOME_PATH.search(t): errs.append(f'user-specific absolute path in {rel}')
        if PERSONAL.search(t): errs.append(f'personal compensation/career wording in {rel}')
if pyc: warns.append('bytecode present (.pyc files embed absolute paths): delete every __pycache__ before zipping, or share with `git archive`')
for d in data_dirs: warns.append(f'data directory inside the package: {d} (scraped data; do not share)')
print(f'package: {PKG}')
print(f'docs: {len(REQ)}, scripts: {sum(p.suffix==".py" for p in scripts)} py + {sum(p.suffix==".mjs" for p in scripts)} mjs')
if warns: print('WARN:'); [print(' -',w) for w in warns]
if errs: print('FAIL:'); [print(' -',e) for e in errs]; sys.exit(1)
print('OK: package structure, manifests, syntax, portability and leak checks passed')
