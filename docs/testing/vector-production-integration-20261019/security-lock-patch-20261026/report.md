# 2026-10-26 安全补丁隔离候选验证

源：1019 工作树，只读；候选：本目录 `backend/`，未发布、未提交。

原始全锁审计确认 filelock 3.32.7 的 3 条公告、opentelemetry-api 1.44.0 与 setuptools 84.0.0 各 1 条。对应原始报告摘要在 `original-findings.json`。

`uv lock --upgrade-package filelock==4.2.1 --upgrade-package opentelemetry-api==1.45.1 --upgrade-package setuptools==84.1.0` exit 0，日志 `upgrade.log`。仅这三个锁版本发生变化。filelock 直接依赖下限同步 pyproject/requirements；两个间接包使用已有 uv constraint 机制，不增加顶层依赖。

lock-check/export/创建 Python 3.12.15 新 venv 均 exit 0。完整 hash requirements 安装因官方 watchfiles wheel 下载超时 exit 1；两个历史缓存的完整离线安装也 exit 1（分别缺 torch / absl-py）。所有失败保留原日志，未宣称从零重装成功。

独立新 env 的三个精确修补包下载及安装 exit 0 (`install-three.log`)。实际跨进程 FileLock 排他、thread_local=False 跨线程释放、释放后新进程重新获取探针 exit 0 (`lock-probe.log`)。

按 root 授权，使用旧已验证环境未变安装载荷作逐文件源 hash → 复制 → 目标 hash 校验；排除三个补丁包、本地 editable 包和 pyc。旧环境不改动。这个运行库属于“复制已验载荷后安装补丁”，不称为完整从零重装。

最终实测：

- `runtime-receipt-r2.exit` 为 0：32706 个未变文件源/新环境最终 hash 均与复制时相同，drift 0。完整安装集合 159（158 registry + 本地 LangExtract）与原 Windows 安装集合仅上述三版本变化；完整跨平台锁仍 179 registry。SQLite 3.54.0 / NumPy 2.5.4 真实 blob 读写 roundtrip 通过。
- `commands.json` 记录 local-install、pip-check、完整锁 pip-audit、安装集合 pip-audit、应用专项命令及 exit 0。两个 pip-audit 均无已知漏洞；机器报告为 `pip-audit-all-lock.json` / `pip-audit-installed.json`，不是只扫描三个包。
- `filelock-real-regression.log`：54 passed，42.89 秒；包含 test_vector_ingest_recovery、test_vector_publication_backup、test_vector_document_publication、test_vector_startup_recovery 四个完整模块。真实跨进程 lease、pin 死进程恢复、备份/恢复及启动恢复均在修补版 filelock 下运行，未修改测试。
- receipt 首轮仅因诊断脚本未按 PEP503 规范化 `boolean.py` 而断言失败，保留 `runtime-receipt.log` / `.exit`。规范化修复后重跑全部 hash 与运行库检查 exit 0；没有改依赖或弱化实际集合比较。

新 Python：`D:/graghRAG-agent/.tmp/security-lock-patch-20261026/.venv/Scripts/python.exe`。待 root 独立复核后可用于最终全量 R3；候选三文件位于 `backend/pyproject.toml`、`backend/requirements.txt`、`backend/uv.lock`，本任务未写 C 工作树。

完整后端双覆盖、Linux 原生运行、容器部署和生产准入仍由主任务独立核验；本候选专项不能代替整体验收。
