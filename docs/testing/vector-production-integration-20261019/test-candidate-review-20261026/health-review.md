# 健康统计候选独立静态增补评审 — 2026-10-26

结论：本次只读静态复核未发现阻断项，可由root按下述hash发布后验证最终快照。没有独立重跑本候选，作者24pass仅作为已检查的历史执行证据，不是本reviewer执行结果，更不代表全量双90或生产准入。

候选 `D:/graghRAG-agent/.tmp/health-artifacts-20261026/test_health_artifact_counts.py` SHA256：`662470e09b493ce307c0cf0218759ed30783ccaf4b4f9d0ff0070bc09250e92d`。
当前C health.py SHA256：`f8b4d22c17f3046167ae263b86e28c3355df97edc068abd9b7194c89d534d97e`。
独立重新计算作者 report.json 绑定的6份输入全部与当前字节一致，见 health-hashes.json（check_health_hashes.py exit0）。没有改候选、生产、原测试或覆盖配置。

## 真实行为与断言

- 14参数化/独立新case调用实际 FastAPI health.router 和真实 auth middleware，经 TestClient GET /api/v1/health；真实创建JSON文件/目录，未替换 JSON decoder、文件系统、HTTP handler 或 _count_kg_nodes/_count_kg_edges。
- fixture用实际 SyntheticStorageConfig、VectorStore、DocumentPublication、真实SQLite/磁盘资产，发布一份有hash资产和一个chunk的文档。stats完整字典精确比较，vector_store组件ok及真实依赖ready/documents=1/chunks=1明确断言，不能用空对象假装健全集成。
- SimpleNamespace只提供已登记模型profile元数据供真实get_embedding_client准入核对，本场景不需要远程embedding；未替换catalog快照、count或runtime_status。SyntheticStorageConfig明确是测试隔离准入，不是生产兼容批准。
- 目录缺失、空目录、杂文件、无产物子目录、flat旧图、两有边子图+flat大图不双计、单子图nodes/edges坏JSON/错误顶层类型独立降级、flat坏兄弟文件、空数组/缺键、连续请求读取更新文件都有实际数值断言。对照原 health.py 可覆盖对应正常与异常分支，而非只断言HTTP200。

## 隔离与污染

- KG_DIR、routes._docs_store/query_count、HealthChecker缓存实例及BM25/TABLE artifact路径通过monkeypatch恢复；当前模块对象不替换为伪实现。
- document_runtime._publication/_embedding_client先保存，finally中configure_publication(*previous)恢复；已核当前configure_publication只设置这两个字段，没有遗漏副作用。finally位于synthetic资源上下文内部，先恢复再删除隔离目录。
- 路由挂在测试私有FastAPI app，无全局app router变更；未见永久文件写入或共享资产覆盖。fixture未调用外部API/启动生产迁移。

## 语义边界及证据

当前生产代码对nodes以是否存在子目录nodes.json决定flat fallback，edges以总数是否为0决定fallback，确有预存不对称。候选两个有边子图不双计的断言无争议；零边子图更新用例没有flat文件，所以不锁死有flat时的争议行为。坏JSON独立降级用例也未混入flat fallback。HANDOFF明确披露未变更/未背书该争议，无须为本测试增量重开实现。

已检查作者report.json/HANDOFF/run_checks.py：绑定当前原件、真实24case（14新+10原），tests/export exit0、输入稳定；作者初次跨盘收集exit4保留，后用importlib/rootdir/confcutdir限制收集路径。其102/113行、24/26分支仅health文件专项信息，不能替代119生产源码后端门禁。作者runner不声称整体验收。

阻断项：无。非阻断限制：本增补为静态独立复核，没有独立重跑health；最终C发布后仍须在完整范围执行测试和独立双覆盖率门禁。A/B实际独立运行结果见同目录report.md。
