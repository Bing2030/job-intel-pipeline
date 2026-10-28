#!/usr/bin/env python3
"""Run the official chain end to end in ONE data dir: collectors -> merge -> filter.

  python3 job-intel-pipeline/scripts/run_pipeline.py [--data-dir DIR] [--skip moka,feishu] [--max-pages N]

Without --data-dir (and $JOBINTEL_DATA_DIR) a new ./tmp-jobs-<yyyyMMddHHmm> is created once and shared by all stages.
Stages: collect_v2 (Tencent/Alibaba/ByteDance), collect_v3 (Ant/JD/Xiaohongshu/DeepSeek),
        feishu (MiniMax/01.AI), moka (Moonshot; needs Chrome), merge, filter.
Exit code is 1 if any stage failed or a collector produced no rows.
"""
import argparse
import csv
import subprocess
import sys
from pathlib import Path

import jobintel_paths as jp

HERE = Path(__file__).resolve().parent
# key, script, extra args, file in <data-dir>/official that must end up with rows
STAGES = [
    ('collect_v2', 'official_collect_v2.py', ['--company', 'all'], 'jobs_official_raw.csv'),
    ('collect_v3', 'official_collect_v3.py', [], '_batch2_raw.csv'),
    ('feishu', 'official_feishu_startups.py', [], 'jobs_official_startups.csv'),
    ('moka', 'official_moka_collect.py', [], 'jobs_official_moonshot.csv'),
    ('merge', 'merge_official.py', [], 'jobs_official_all.csv'),
    ('filter', 'filter_official.py', [], 'jobs_official_filtered.csv'),
]
KEYS = [s[0] for s in STAGES]


def count_rows(path):
    if not path.exists():
        return None
    with path.open(newline='', encoding='utf-8-sig') as f:
        return sum(1 for _ in csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description='Run the official chain (collectors -> merge -> filter) in one data dir')
    ap.add_argument('--skip', default='', help='comma-separated stages to skip: ' + ','.join(KEYS))
    ap.add_argument('--max-pages', type=int, default=1, help='pages per keyword for collect_v2 (default 1)')
    jp.add_argument(ap)
    a = ap.parse_args()
    skip = {s.strip() for s in a.skip.split(',') if s.strip()}
    if skip - set(KEYS):
        ap.error('unknown stage(s) in --skip: ' + ','.join(sorted(skip - set(KEYS))))
    data = jp.resolve(a.data_dir, produce=True)
    status = {}
    for key, script, extra, out in STAGES:
        if key in skip:
            status[key] = ('skipped', None)
            continue
        if key == 'filter' and status['merge'][0].startswith(('FAILED', 'EMPTY')):
            status[key] = ('skipped (merge produced nothing)', None)
            continue
        cmd = [sys.executable, str(HERE / script), *extra, '--data-dir', str(data)]
        if key == 'collect_v2':
            cmd += ['--max-pages', str(a.max_pages)]
        print(f'\n=== {key}: {script} ===', flush=True)
        rc = subprocess.run(cmd).returncode
        rows = count_rows(data / 'official' / out)
        status[key] = (f'FAILED (exit {rc})' if rc else ('ok' if rows else 'EMPTY'), rows)
    print('\n=== summary ===')
    for key in KEYS:
        st, rows = status[key]
        print(f'{key:11s} {st:34s}' + ('' if rows is None else f'{rows} rows'))
    print(f'data dir: {data}')
    sys.exit(0 if all(st == 'ok' or st.startswith('skipped') for st, _ in status.values()) else 1)


if __name__ == '__main__':
    main()
