"""Where the pipeline reads and writes data (shared by every script).

Everything lives under ONE data dir, in the same sub-dirs the project used to keep under data/jobs/:

    <data-dir>/official/    official collectors, merge_official, filter_official
    <data-dir>/processed/   third-party scrapers and analysis tables
    <data-dir>/raw/         cached / captured HTML (third-party content; never share)
    <data-dir>/reports/     generated markdown reports

Which data dir is used (first match wins):
    1. --data-dir DIR
    2. $JOBINTEL_DATA_DIR
    3. ./tmp-jobs-<yyyyMMddHHmm> in the current directory
         - collectors / scrapers ("produce") start a NEW one, so a rerun never overwrites an earlier run
         - merge / filter / analysis ("consume") use the NEWEST existing one
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PREFIX = 'tmp-jobs-'
ENV_VAR = 'JOBINTEL_DATA_DIR'
_STAMPED = re.compile('^' + re.escape(PREFIX) + r'\d{12}$')


def add_argument(ap):
    ap.add_argument('--data-dir', metavar='DIR',
                    help=f'data directory (default: ${ENV_VAR}, else ./{PREFIX}<yyyyMMddHHmm>)')


def new_default_dir(now=None):
    return Path.cwd() / f'{PREFIX}{(now or datetime.now()):%Y%m%d%H%M}'


def newest_default_dir():
    found = sorted(p for p in Path.cwd().iterdir() if p.is_dir() and _STAMPED.match(p.name))
    return found[-1] if found else None


def resolve(cli_value=None, *, produce):
    """Return the absolute data-dir root and announce it on stderr.

    produce=True  creates the dir (a new default one when nothing is configured).
    produce=False needs an existing dir (the newest default one when nothing is configured).
    """
    configured = cli_value or os.environ.get(ENV_VAR)
    if configured:
        root, how = Path(configured).expanduser(), ('--data-dir' if cli_value else '$' + ENV_VAR)
    elif produce:
        root, how = new_default_dir(), 'new default'
    else:
        root, how = newest_default_dir(), 'newest default'
        if root is None:
            raise SystemExit(f'No data dir found. Pass --data-dir DIR or set ${ENV_VAR}; '
                             f'collectors create ./{PREFIX}<yyyyMMddHHmm> when none is configured.')
    if produce:
        root.mkdir(parents=True, exist_ok=True)
    elif not root.is_dir():
        raise SystemExit(f'Data dir not found: {root}')
    root = root.resolve()
    print(f'[jobintel] data dir: {root} ({how})', file=sys.stderr, flush=True)
    return root
