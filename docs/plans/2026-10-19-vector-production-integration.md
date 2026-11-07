# 向量库生产集成实施计划



> 执行技能：设计确认后使用subagent-driven-development或executing-plans；逐任务TDD并独立复核，不因专项通过跳过整体验收。



Goal：在生产源码接入SQLite＋NumPy，形成入库、授权查询、显式更新、删除及进程重启恢复闭环。



Architecture：复用R8分片向量实现，扩展严格版本化schema提供权威文档发布目录；不可变资产先prepare，单SQLite事务切换active revision及成功收据；查询服务端授权并固定快照。



状态：用户于2026-10-20确认设计和计划，实施中；2026-10-22明确在`codex/safe-snapshot-20261019`继续。依据[设计](../design/2026-10-19-vector-production-integration.md)。无commit/push/部署步骤；不得把历史通过结果套用新代码。未勾选条目仍须最终同快照验收，阶段实现与失败证据见[接续记录](../../memory/2026-10-27.md)。



## 0. 隔离及输入基线



2026-10-28接续：数值标量条件性源码依据已独立审查，按入口合同回流，未开放生产gate。Windows R7完整2157通过/零失败错误跳过，119全范围行16456/17653、分支5440/6044双90，255输入SHA稳定且独立核验；此前R3-R6失败均保留。证据见[本日记录](../../memory/2026-10-28.md)及[独立报告](../testing/vector-production-integration-20261019/final-backend-evidence-review-20261028/final-r7.md)。当日全锁扫描新检出msgpack1.2.2公告，CPython原生安全补丁、Linux运行库/桥及容器重建仍需闭合；候选依赖/runtime变化须重新验收，不能套旧R7。以下未勾选条目保留完整生产验收含义，不以单平台或有限差分替代。



- [ ] 复用最新安全提交b1e300f的独立工作树，记录实际路径、分支和Git状态；根master dirty及子仓库不动。需写越工作区权限时正常提权，不绕过。



- [ ] 校验R8冻结42适配器文件、66消费者文件及最终独立修订SHA；恢复到新工作目录而不是修改历史归档。



- [ ] 记录backend源码/测试/config/lock、前端49及rag22输入基线；读取相关子目录AGENTS及现有模块规范。



## 1. 生产运行库与门面（文件归属：存储coder）



文件：`backend/vector_store.py`、新增`backend/vector_errors.py`、`backend/sqlite_vector_store.py`、`backend/sqlite_vector_payload.py`、`backend/vector_numeric.py`、`backend/vector_runtime.py`；正式tests下新增对应行为套件。文件拆分以评审后单责任为准，不复制临时绝对路径。



- [ ] RED：默认工厂不导入Chroma；错误SQLite版本/缺硬化能力、旧库未迁移、坏schema及维度/模型冲突显式失败，不静默镜像/空结果。



- [ ] 绑定R8源码实施，复跑全部门面、过滤/舍入、资源及并发页面测试，保存实际命令、exit、前后hash与差分反例。



- [ ] 核实formatter准入矛盾并关闭或明确阻塞；独立审查后才允许正式激活。实现不自动把有限差分写成全域证明。



## 2. 文档发布目录（文件归属：生命周期coder）



文件：新增`backend/services/document_catalog.py`、`backend/services/document_publication.py`；修改`backend/routes/__init__.py`、`backend/services/document_snapshot.py`及受控schema/备份验证；新增`backend/tests/test_vector_document_publication.py`。



- [ ] RED：prepare不可见、publish原子、expected_revision CAS、tombstone防复活、未知旧身份拒绝、权威目录与legacy同ID冲突拒绝回退。



- [ ] 实现document/revision/task receipt事务、不可变资产manifest和兼容目录入口；资产hash验证失败保留旧active，DB失败不得更新进程缓存。



- [ ] legacy-only删除写tombstone且遮蔽仍存在的JSON，legacy更新409/migration_required；持久cleanup及跨进程资产pin，损坏路径仅blocked而不触碰。



- [ ] 真实双连接并发与全新子进程重开测试；备份含目录及删除状态，严格schema升级/恢复测试。



## 3. 入库及显式更新（生命周期coder在存储评审后执行）



文件：`backend/worker.py`、`backend/routes/ingest.py`、`backend/models.py`、`backend/doc_processor.py`，必要时新增`backend/services/vector_ingest.py`；新增`backend/tests/test_vector_ingest_lifecycle.py`。



- [ ] RED：同名新上传不覆盖、显式更新权限/预期版本必需、任务DONE晚于可查询提交、失败不发布、PDF/本地路径都有可信身份向量。



- [ ] 向两个worker路径传递不可伪造发布上下文；取消必需向量失败的成功降级；prepare后统一commit，提交前再次授权/CAS。



- [ ] 列表及TaskResult暴露active_revision，异步CAS冲突保留status API200但FAILED/error revision_conflict与http_status409；缺字段422、首版revision1、任务收据幂等均有测试。



- [ ] 生产存储ID编码绑定document/revision/local chunk ID，同名跨租户文档不冲突；重复task按收据幂等，测试总数与全部记录身份而不只检查未抛异常。



- [ ] 不再用各次入库的局部BM25/Table覆盖全集权威，运行时索引是按授权活跃版本可重建的派生物。



- [ ] 用合成真实文件+本地固定embedding模型验证解析/嵌入/SQLite；供应商本地HTTP边界另列，避免付费和资料外发。



## 4. 查询、删除及分页消费者（文件归属：检索coder）



文件：`backend/routes/rag_query.py`、`backend/routes/documents.py`、`backend/retrieval.py`、`backend/index_registry.py`、`backend/build_indices.py`、`backend/run_evaluation.py`、`backend/services/bot_handler.py`、`backend/services/resource_access.py`，新增`backend/services/scoped_vector_snapshot.py`及对应测试。



- [ ] RED：A/B同名、跨租户/撤权无泄漏；显式vector不再因未绑定身份固定503，但实际库故障仍503；删除后缓存和在途结果均不返回旧文档。



- [ ] 接入R8三个分页消费者，保留主动close及最后页；BM25/Table先按可信活跃doc/revision过滤，缓存键包含generation及授权范围。



- [ ] 目录/search/pages共享显式read_snapshot连接；生产_collection.get/CLI/admin不暴露prepared/inactive；最终新事务重新授权，旧答案/trace整组丢弃，删除/撤权404/403、版本变动最多重取一次。



- [ ] HTTP删除先验证文档写权限；资产安全解析失败仅阻止物理清理，事务持久化tombstone和blocked精确清理记录。该删除语义及原P0断言变化经用户确认后实施，危险资产字节必须保持不变。清理失败可恢复且不复活；版本/删除/撤权最终复核及状态码遵循设计。



- [ ] 验证非HTTP机器人/CLI不能绕过发布身份；旧KG仅兼容读取，旧未归属向量不自动开放。



## 5. 重启、探针、配置及锁



文件：`backend/server.py`、`backend/config.py`、`backend/services/health_checker.py`、`backend/services/catalog.py`、`backend/routes/health.py`、`backend/services/backup.py`、`backend/pyproject.toml`、`backend/requirements.txt`、`backend/uv.lock`、`Dockerfile.backend`、`docker-compose.yml`及实际有效部署配置；新增正式runtime构建/核验脚本位置须由独立评审确认。



- [ ] RED：commit后DONE前进程中止、删除后清理前中止、坏schema、旧库未迁移、库锁、备份错误hash、模型不同维度相同均不会伪健康。



- [ ] 接入真实runtime gate，恢复任务提交收据，未提交任务标interrupted；SQLite在线备份、准确readiness、重启重建分页索引。



- [ ] 全链日志合成敏感标记不得出现在HTTP/任务/traceback输出；output、uploads及manifest资产均有持久卷，真实容器重建验证或如实记录未执行。



- [ ] 主锁移除Chroma、显式NumPy，原生runtime版本/hash可重建；Windows验正式隔离环境，Linux容器单独验实际运行库。不能只修改Dockerfile后宣称容器已通过。



- [ ] 未关闭兼容准入时默认启动compatibility_not_approved，专用合成环境与生产路径严格隔离；固定DB清单pin/backup/资产复制/hash/封存/释放，恢复隔离目标完整验证后启用。



- [ ] 全锁pip-audit及原生SBOM/适用性独立审计；保留扫描退出码和所有未修项，不忽略公告制造通过。



## 6. 连续整体验收与交付



- [ ] 新增`backend/tests/test_vector_lifecycle_integration.py`：HTTP上传v1→查询→HTTP更新v2→只见v2→重启仍v2→删除→再次重启404且B正常；真实权限、解析、SQLite和本地模型执行，真实子进程恢复。



- [ ] 真实故障注入覆盖prepare、资产完成、commit前后及DONE前后；并发更新/删除/撤权，任务状态、引用版本、磁盘记录分别断言。



- [ ] 增加v1独有内容在v2后不命中、legacy tombstone重启及备份恢复、最终检查前撤权、物理清理失败但不可查、备份期间更新/删除；分别核验预期状态码与原件安全。



- [ ] TDD实际命令`<integration-python> -m pytest backend/tests/test_vector_* -q --tb=short -p no:cacheprovider`，以实际正式测试路径为准，失败及绿结果均存`docs/testing/vector-production-integration-20261019/`。



- [ ] 专项之外重新运行全部受影响既有P0/auth/ingest/index/runtime/health/backup测试，最终完整backend测试为正式门槛；用实际收集列表确认新测试全部被执行，不以glob命令代替范围核验。



- [ ] 独立reviewer读取新上下文/最终hash，自行增加新输入；关闭正确性、安全、契约、测试质量阻断项后root复跑适用验证。



- [ ] 全量固定backend生产范围coverage run/json（使用`docs/testing/coverage-backend-2026-10-12.ini`）、规定全测试、两指标原始计数各≥90%；新增模块必须进入分母。跨子项目按固定策略逐项核验，代码变化后重新跑受影响检查。



- [ ] 回流API蓝图、向量设计/契约、拓扑与测试规范，保存源码/锁/模型/runtime/hash、命令、exit、机器报告与限制；更新memory，明确已实现/已验证/已提交/已部署。



完成标准：连续验收链与故障场景真实通过、全量双90、安全及兼容门槛关闭；缺任一项不得宣称生产就绪。设计确认前仅做只读核实与评审，不修改生产代码/旧数据。



### 2026-10-28 当前验证状态（R8之后）



主锁已将msgpack更新为1.2.3；新隔离Windows候选为Python3.12.16＋SQLite3.54.0＋Expat2.9.0＋OpenSSL3.5.9＋NumPy2.5.4。该候选完整锁179项和实际安装159项pip-audit均exit0、漏洞0、skip0，不能替代全部原生组件安全结论。



新环境R8完整后端测试exit1，Git元数据读取无界等待触发原60秒用例时限；coverage导出也exit1，因此当前没有新快照双90通过证据。旧R7通过仅作历史记录。修复候选需独立复核、发布后重新全量；不得提高原测试时限或移除旧2157用例。



Linux SQLite＋NumPy及数值桥仅完成隔离MVP和独立复验，桥两次构建SHA不同，不能称字节可复现或正式批准。CPU profile仅私有设计/官方metadata及静态图草案，resolver锁与完整安装未完成；正式默认设备策略不变。Rust11项yanked/checksum已通过官方元数据独立补验，原cargo-audit正常索引检查失败记录保留；Torch捆绑libuv完整native调用闭包/回补及第一方Rust覆盖测量仍开放，生产compatibility_not_approved保持。证据见[当前归档](../testing/vector-production-integration-20261019/remaining-tests-20261028/archive-manifest.json)及[工作记录](../../memory/2026-10-28.md)。无提交、推送、部署或真实数据迁移。



### 2026-10-29 验证接续（更新上述R8之后的历史状态）



R10最终Windows代码快照完整2201测试通过且零skip，120/120第一方Python文件：行16624/17802、分支5481/6086，分别超过90%；原2157及2187用例身份保留。独立审查及输入SHA核验已归档。该结论绑定R10快照，不由本次文档状态更新扩展为Linux验收。



第一方Rust仅数值桥main.rs，独立离线重编译与61项/122进程复验后，诊断profile唯一物理行59/60、原始分支23/24分别通过90%；额外LLVM行实例61/62仅补充说明。原49项分支21/24失败及未覆盖项保留，LLVM死函数summary遗漏限制由原始file分支数组与全部映射函数执行核对。诊断二进制不同于release，不声称发布二进制覆盖身份。



Linux CPU候选现在有真实resolver锁d1434b9b8b46f3d9c061098e15ddaada44e8d0a2d3dfb55d4db4c425a8f60b36，标准在线uv lock --check退出0且前后SHA一致；完整依赖图经独立审查：runtime133、含dev158（不含backend虚拟根）。私有方案以官方Torch精确PEP508 URL及发布hash替代此前命名index草案，只有Torch版本改为2.14.0+cpu，其余选中版本、来源及工件为主锁对应子集；GPU节点依真实CPU闭包自然消失。原离线canonical缓存miss失败保留，当前不声称离线可安装。实际Linux完整安装、wheel实际校验、oss2/crcmod隔离源码构建和固定模型/backend容器整链仍待执行。



本次是文档与证据接续，不改正式默认/GPU行为，不启用compatibility准入；Windows Torch libuv适用性/完整native来源与Linux正式生产集成仍未关闭。生产compatibility_not_approved保持，未提交/推送/部署/迁移。证据见[当日归档](../testing/vector-production-integration-20261019/remaining-tests-20261029/archive-manifest.json)及[工作记录](../../memory/2026-10-29.md)。



### 2026-10-29 安全修补后快照说明



新扫描发现CVE-2026-118667/GHSA-3fx2-cqw9-xr3c后，正式依赖已受控升级LangGraph1.2.14/SDK0.4.6；pyproject/uv.lock/requirements三个输入均经独立差分审查，其他第三方包记录保持。实际SDK四调用点×11标识44项补丁行为通过，旧版40项编码差异保留。主179项锁扫描零公告/零skip；CPU157项PyPI Torch skip保留，另精确CPU和public-base OSV补充均无公告，不能代替native闭包安全。



CPU canonical私有锁SHA8a8ef5c4e9327e7f22529eec5f90ea204db3238d19948634da75e4954ed2f786，普通offline resolver/check通过。仅将PEP508 exact官方URL的fragment身份改为canonical URL，原Torch版本/官方URL/wheel SHA整记录保持，完整158项hash安装要求不减；不改变正式默认/GPU策略。私有依赖镜像f4e637023bdc366728472bcaa271002d2d69ad6065c6bd6e7b706ed9c4d1df83离线安装、pipcheck、158唯一分发包/路径通过；固定11文件模型512维与归一化及CPU Tensor探针通过。数值桥GNU包仅私有合成MVP build identity获限定评审，不等于Linux原Chroma语义契约/正式安装或生产准入。



正式依赖变化后旧R10仅历史证据，必须重跑R11完整第一方双指标与原2201用例，不能借旧报告签收。真实HTTP生命周期与重建恢复、原生安全及Linux正式生产整合仍按计划逐项核验。测试结果写入testing证据与memory；本段不是完成声明，compatibility_not_approved保持，未提交/推送/部署/迁移。



### 2026-10-29 Linux 数值桥构建入口集成



固定 x86_64 MSVC/GNU 的 `backend/native/vector_numeric/build.py` 现支持离线构建和审查 SHA 后向 fresh、非服务 staging 安装。前提是已安装 rustup 及固定 1.94.0 工具链；全部编译器/Cargo调用使用不带 `--install` 的 `rustup run 1.94.0`，缺工具链直接失败，Cargo依赖命令继续 `--offline --locked`。schema1 features 保留 requested labels，真实 graph/compiled cfg 单独记录；安装身份批准不等于数值语义或生产批准。Linux可执行位及只读源/包由安装和受控镜像打包分别落实。



候选经历有效RED/GREEN、独立32策略用例、真实断网GNU构建及缺工具链负例；未改Rust源码/锁、数值协议或runtime verifier。未改的installer另有真实审SHA安装、非root只读执行/权限负例和root三个新容器复验。Linux Chroma1.5.9 ABI3 wheel SHA cc09b3df76e5a5cb386aed2715a2eea152e3949f9e1ba93c7119505377749929 已由作者与独立reviewer分别实际验签，绑定既定源码commit/tag；37原manifest与51全target消费者闭包通过，接受与Windows相同通常上游信任条件下的内置标量source/build前提，不外推任意PyO3/全部predicate或全部native安全。



证据见 `docs/testing/vector-production-integration-20261019/remaining-tests-20261029/linux-build-provenance/`、`linux-install-native-inputs/` 及 `linux-build-v2-publication/`。本次正式源码/测试变化后R11仅历史，须执行新最终快照全量回归与分别双90。正式Dockerfile/生产runtime和CPU/GPU默认未切换；Windows libuv修补仅获私有离线构建及静态检查授权、尚未验证ABI或替换运行库。`compatibility_not_approved` 保持，无提交/推送/部署/资料迁移。



### 2026-11-04 Windows 旧 ABI 路线进度



- [x] 在独立工作树以 libuv v1.40.0 精确 commit 为基线，按原顺序应用四个官方 IDNA 回补提交；冻结补丁且差分检查通过。



- [x] 保留有效 RED：`utf8_decode1_overrun` 与空 `idna_toascii` 在旧实现上均非零退出；候选动态 402/402、静态 405/405，exit 0。



- [x] 对基线、候选、原 Torch DLL 核 288 导出 ordinal/name、loop/handle/request 尺寸、x64 与依赖集合，均一致；候选保持 `uv_loop_size=464`。



- [x] 重建哈希绑定的 CPython 3.12.16/SQLite 3.54.0 私有运行库，Torch 加载候选 DLL；固定模型“上传→查询→更新→重启恢复→删除→再次重启”实际 1 passed、零失败/错误/跳过。



- [x] 记录能力边界：原始与候选 Torch 都未编译 libuv TCPStore；该入口不属于当前 GraphRAG 合同，不能作为回补回归，也不能声称已验其动态路径。



- [ ] 将冻结补丁、工具链、输入哈希、构建、ABI 核验、安装与回滚写成仓库内项目自有正式配方；不得提交候选二进制或依赖 `.tmp`。



- [ ] 对正式配方与安装边界做独立代码复核；替换正式 runtime 后重跑完整 backend、固定全量行/分支双 90、锁检查和既定扫描。



- [ ] 只有上述项关闭后才评估解除 Windows runtime 阻塞；Linux、部署与整体 `compatibility_not_approved` 仍按原计划独立关闭。



本轮证据见[Windows 旧 ABI 回补报告](../testing/vector-production-integration-20261019/remaining-tests-20261104/windows-old-abi-backport/REPORT.md)。未提交、未推送、未部署、未迁移资料。



### 2026-11-05 Route A 配方实施状态



- [x] 在 `backend/native/torch_libuv/manifest.json` 锁定精确源码 commit、四个上游提交、补丁 SHA、CMake/MSVC/NMake 工具链、ABI 目标与 402/405 测试契约。



- [x] 在 `build.py` 提供 `recipe`、`build`、`verify-existing`、`install`、`rollback` 与 `_abi` 入口；`build` 强制精确且干净 checkout、全新 staging、离线 CMake 配置、CMake/MSVC/NMake 版本和唯一候选产物，未通过验证不生成批准收据。



- [x] 安装收据绑定 manifest/patch/build 脚本/源码合同/工具链/候选字节和 recipe command provenance，回滚对安装目录和收据做完整身份检查；新增专项测试 27/27 通过。



- [ ] 在新的、可复核的 libuv 精确 checkout 上实际执行 `build`→`verify-existing`，保存命令、工具链输出、候选/参考 PE 与 ABI 收据；当前工作树没有该源 checkout，不能把命令清单当成实际构建证据。



- [ ] 对配方和安装/回滚边界做独立代码复核；候选替换正式 runtime 后重跑完整 backend、固定全量行/分支双 90、锁检查和既定扫描。



- [ ] 只有上述项关闭后才评估解除 Windows runtime 阻塞；Linux、部署与整体 `compatibility_not_approved` 仍按原计划独立关闭。



本轮未提交、未推送、未部署、未迁移资料；候选二进制继续留在私有临时目录，不进入 Git。



### 2026-11-06 执行结果



- [x] Route A 实际 build/verify-existing、独立 PE/ABI 复核及私有 install/rollback 演示完成；正式 serving runtime 未替换。



- [x] pyasn1 安全下限与锁文件定向更新完成；patched lock check、pip check、去重安装审计 exit 0。



- [ ] full-r3 完整后端门槛未通过：2271 项中 2253 passed、6 failed、12 errors；冻结夹具、Rust toolchain manifest 和 Windows socket 资源问题需解决后重跑。



- [ ] 121 文件行覆盖率 16886/18166，分支 5561/6220 未达 90%。



- [ ] Linux/native aggregate、正式 runtime 替换、生产 compatibility gate、提交/推送/部署/迁移仍未完成。



### 2026-11-06 最终结果（R13）



- [x] public-dev 与 simple-output runtime snapshot 恢复为原始 SHA；simple-output registration 已从历史生成链恢复并精确匹配 receipt，full-r5 使用原件。



- [x] Rust stable MSVC 1.99.1 工具链恢复；native bridge 36 项通过。



- [x] 构建脚本新增 19 项行为测试；完整后端 2290 项 0 failed/error/skip，原 2223 项身份全部保留。



- [x] full-r5 完整运行的 121/121 文件，行 16973/18166（93.4328%）、分支 5599/6220（90.0161%），原始整数双 90% 通过；可作为 Python 提交门槛证据。



- [ ] Linux/原生整体安全、正式 runtime 替换、生产 compatibility gate、部署和数据迁移仍开放；不得把本结果外推为生产就绪。
