# scripts

- 这里是 pipeline 的**唯一源码**。
- `jobintel_paths.py`：数据目录解析，被所有脚本 import；`run_pipeline.py`：官方链路入口；`validate_pipeline.py`：分享前自检。
- 每个脚本用 `--data-dir DIR` 或环境变量 `JOBINTEL_DATA_DIR` 指定数据目录；都不指定时的规则见 [`../README.md`](../README.md) §3（默认 `./tmp-jobs-<yyyyMMddHHmm>`）。
- `--help` 只打印用法，不会运行脚本（`validate_pipeline.py` 只读，无副作用）。
- BOSS 的页面由人工登录后用 `cdp_fetch.mjs` 保存到 `<data-dir>/raw/boss/pages|details/`，再跑 `boss_*_parse.py`，详见 [`../WORKFLOW.md`](../WORKFLOW.md)。
- 每个脚本的输入/输出见 [`../scripts.csv`](../scripts.csv)。
