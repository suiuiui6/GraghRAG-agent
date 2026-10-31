# R11 独立证据复核 — 2026-10-29

结论：指定最终快照的 R11 Windows 后端 Python 证据通过。本结论为 `audit-only-windows`，不是 Linux 正式生产准入、全部 native 安全清零或整套代码复审结论。未重跑 pytest，未提交、推送、部署或修改源/config/设计计划/runtime。

## 方法和输入

独立读取指定 C 工作树 AGENTS.md、docs/testing/README.md、固定 coverage 配置及 R11 driver；直接解析原始 coverage.json、JUnit、collection log/nodeids、R10 JUnit Counter。未使用 summary/root-recomputed 作为判定替代。执行本目录 review.py、compare.py、checknames.py、model.py（最终均 exit 0）；首轮 review.py 因 collect.log 非 UTF-8 字节失败，改为与执行器一致的 errors=replace 后重跑。没有输出 JUnit captured output、读取 .env 或进程 CommandLine。

普通 Git 读取 Permission denied，正常 require_escalated 的只读 Git 命令成功：HEAD b1e300f1445c48f9f838bcc0d7b91cb39c1171b2，分支 codex/safe-snapshot-20261019；工作树有未提交修改，本报告绑定当前文件 SHA，不将 HEAD 当成全部代码身份。

## 核实结果

- 独立走目录核算固定生产范围 120 Python 文件；coverage missing/extra 均空。source=backend，namespace 纳入；omit 仅环境、测试、缓存、输出等，exclude_lines/partial_branches 显式为空。零覆盖 oss_uploader.py、scripts/check_imports.py 仍在分母，未发现为了过线遗漏未导入文件。
- 逐文件 summary 求和：行 16624/17802=93.382766%，分支 5481/6086=90.059152%。分别以整数交叉乘法判断，两项均满足 90%，没有混合总分或四舍五入过线。
- 原始 JUnit 2201 cases，failure/error/skipped 均 0。R10→R11 的 (classname,name) 多重集完全相等；原始 collection log 与 nodeid 清单一致，唯一且与 JUnit Counter 完全一致。collect/tests/export 记录退出码均 0，测试命令 580.953 秒，在 1200 秒上限内。
- 258 输入 before/after 完全相等，独立当前逐 SHA 重读零漂移。R10→R11 输入仅三份依赖清单/锁及设计/计划变化；所有已绑定 Python 测试、生产源码和 coverage 配置一致，因此未发现本轮删弱测试/pragma/缩范围。此项不能替代对既有全部断言质量的代码复审。
- 独立重新枚举 fixed-base Python 全文件、coverage 工具非缓存文件、新 venv 全部非 pyc/非 __pycache__ 文件、本地 runtime backend 和 12 个装配收据，加 driver，集合恰为 36682；missing/extra 均空。before/after 相等，全部 36682 实际文件再次计算 SHA，零漂移，最终一轮约 9.28 秒。包括 driver、pyvenv.cfg、新 LangGraph/SDK 实际包文件、Python/SQLite DLL、工具及源码已绑定的 native EXE/approved-build。
- 实际读取新 venv 159 份 METADATA，按 Python 分发名规范归一化后 name/version/METADATA SHA 与审计输入完全相同。LangGraph=1.2.14、langgraph-sdk=0.4.6、msgpack=1.2.3 实际安装且文件绑定。初版自写名称比较只替换下划线，造成点号包名假差异；修正 [-_.]+ 规范化后重新全量复核，最终 receipt 为 true。
- 原始 audit.json 158 第三方条目与实际安装版本集合精确一致（仅排除 local LangExtract 1.5.0）；0 已知公告、0 skipped。receipt exit 0；attempt0-network-denied 的失败目录和文件仍保留并已 hash。公告扫描不审本地 LangExtract 或全部 bundled native 成分。

## 真实模型身份和限制

原始 JUnit 包含 tests.test_vector_http_lifecycle::test_fixed_local_model_http_upload_update_delete_restart，44.479 秒，无跳过。读取用例确认真实 create_pinned_embedding、上传/查询/更新、fresh 子进程重开、删除后 fresh 子进程 404 断言，模型为 BAAI/bge-small-zh-v1.5，revision 7999e1d3359715c523056ef9478215996d62a620，512 维。独立实际重 hash receipt 的 11 模型文件全部一致。

该测试使用本地 provider_boundary HTTP 替身及 SyntheticStorageConfig 的隔离开发环境，证明离线 embedding/本地 HTTP 生命周期，不证明真实远端 LLM/生产部署或模型质量。driver 明确 offline 环境；bootstrap 在 coverage 内、pytest 收集前仅准备 SentenceTransformers 库，日志准备耗时 118.578 秒，不加载模型。生命周期 marker 240 秒、真实子进程 60 秒/合成 35 秒未改；不能与旧父进程冷启动时间混为性能改进。模型文件不在 36682 runtime 快照内，已另外独立当前 hash；R11 运行时由真实加载入口核对 profile 文件 SHA。

## 交接与界限

本目录 receipt.json 和 hashmanifest.json 保留可机器复算结果与逐文件 SHA。报告只关闭本轮 Windows Python 全量测试/双90及已安装 Python 包公告证据绑定，不授权提交或生产，不替代其他子项目、Rust覆盖、Linux/native 安全和生产兼容性各自验收。根任务正在更新的 testing/memory 归档不属于 258 输入，不造成被测源码漂移；后续任一绑定文件变化必须重验适用证据。
