# 向量库生产集成及文档生命周期设计

状态：2026-10-20用户已确认设计和计划，实施中；2026-10-22用户明确以`codex/safe-snapshot-20261019`工作树继续。2026-10-19用户授权沿SQLite＋NumPy路线进行生产代码集成，并要求“入库→查询→更新→删除→重启恢复”整体验收。此文件不表示实现或生产切换已经完成。

## 范围与已确认约束

继承[总体路线](2026-10-13-vector-replacement-design.md)、[R8适配器](2026-10-16-sqlite-vector-adapter.md)及[隔离验证](../testing/2026-10-17-sqlite-vector-r8-final.md)。不重开已确认的非有限向量拒绝、合法数据规模保留、分批精确扫描、分页BM25和Chroma项目门面合同。不把精确扫描说成ANN逐ID等价；不通过缩小metadata数值支持范围消除反例。

目标是可交付的生产源码、独立锁定环境及真实本地验收。现有数据继续保留；真实生产资料迁移、线上部署及对外付费模型调用须分别按已有实际授权判断，本计划不自动执行。生产集成不能仅靠改VectorStore import或换包名完成。

## 设计起草时的代码缺口（非当前实施状态）

- `backend/vector_store.py`仍使用Chroma；`worker._run_local_parse_pipeline`写向量时没有可信document/revision身份，PDF路径仅建运行时索引。
- `routes.ingest._run_indexing`先保存DONE后登记文档；文档JSON、KG文件与向量分离提交。失败、重启和并发更新没有统一发布依据。
- `routes.rag_query._generate_scoped_rag`出于隔离要求只允许KG；`routes.documents.delete_document`不删除向量。全局BM25/Table缓存不能证明文档隔离或删除撤回。
- `routes.__init__`的JSON文档目录是进程内缓存，没有跨进程事务。当前没有对同一document_id上传新版本的HTTP契约。
- 2026-10-19只读运行库探针：backend quality环境Python3.12.8/SQLite3.45.3；R8独立环境Python3.12.15/SQLite3.54.0/NumPy2.5.4。两个连接均提供setconfig，但前者不能满足R8最低SQLite3.53.2。不能直接拷贝源码然后套用旧backend通过记录。

## 方案比较及选择

1. 仅替换存储门面：改动小，但保留DONE提前发布、旧版本混查及删除残留，不能满足验收链，排除。
2. **推荐：SQLite中统一管理向量与文档发布目录，文件资产不可变，单事务切换active revision。** 将新文档目录、版本和任务提交收据纳入同一权威数据库；保留旧JSON入口的只读兼容。避免在多个可写目录之间假装具备原子性。
3. 另建元数据数据库并协调向量库：需持久化协调日志及跨库补偿；本次没有收益，不采用。

R8低层记录、分片、数值与过滤实现复用已冻结源码，生产化拆分模块但不得改写历史包。新发布目录属于显式schema版本扩展，`validate_schema`、备份恢复、重开验证同步升级，禁止靠放宽严格schema检查接受任意表。

## 权威数据与接口

新SQLite schema包含现有collection/record/payload及受控document、revision、task receipt表。document保存服务端生成的稳定document_id、owner/org/project身份、active_revision及tombstone；revision保存embedding模型固定身份/维度、collection、原件/KG资产路径与hash、构建配置指纹和commit状态；向量关联document_id/revision。任务收据至少记录task_id、目标文档、预期修订、终态及提交修订。文件名不是身份，客户端metadata不能覆盖服务端身份。

revision从1开始单调增加；task_id唯一，重复执行只返回同一成功收据，不生成第二修订。另设持久化cleanup记录（document/revision、精确待清理清单、pending/blocked/done、失败安全码和重试状态）及受控资产pin/读取租约。物理清理只处理无有效pin的精确登记资产；跨进程pin到期/恢复策略须实际故障测试，不靠进程内计数证明安全。

现有`chunk_sections`每文档都从`c00001`生成ID，不能直接写共享collection。发布层使用无歧义编码的`(document_id, revision, local_chunk_id)`命名空间作为实际主键，保留原local ID作溯源字段；同名、同内容和同local ID的其他文档不得被INSERT OR IGNORE静默吞掉。重复发布同一task通过提交收据幂等识别，不能把主键碰撞当幂等成功。

对新向量管理文档，SQLite目录是查询、授权、列表及恢复的唯一权威。历史JSON只作为未迁移旧文档的兼容输入；同ID冲突不能合并或回退绕过tombstone。`routes.get_docs_snapshot/add_doc/remove_doc`通过目录服务适配，禁止继续双写两套权威。旧文档和旧KG不自动改归属；无可信身份的历史向量不准进入新检索。

合并读取严格SQLite优先，tombstone无条件遮蔽同ID legacy。删除仅在JSON登记的旧文档也必须先创建SQLite tombstone，旧JSON即使仍存在也不能恢复可见性。legacy文档没有可信active revision，显式更新返回409/migration_required，不默认推断revision0；受控归属迁移另行设计。

保留现有VectorStore公开门面与已验证where/metadata/score语义；新增内部发布服务承担prepare/commit/delete，低层add_chunks不隐式成为文档发布。模型标识、维度和配置写入manifest并在查询验证，禁止相同维度不同模型混用。

### 更新HTTP契约（新增，需确认）

沿用`POST /api/v1/ingest`的multipart接口，新增可选`replace_document_id`及`expected_revision`。普通上传仍创建独立文档；显式替换必须两字段同时存在，先核验写权限，未知/越权404，版本冲突409。原件仍由服务端生成存储键。客户端文件名相同不触发覆盖。新修订继承原owner/org/project，不能借更新改变归属；已删除文档不得被过期任务复活。

HTTP接收时与最终提交时都校验expected_revision和写权限；前者不代替后者。两个并发更新最多一个提交，冲突任务失败且保留旧active；业务错误不触发无限重试。首版不改变旧session409政策，不在本次新增多轮会话。

字段类型：`replace_document_id`为非空字符串、`expected_revision`为严格正整数，两字段缺一返回422。`GET /documents`的DocumentItem及成功任务TaskResult增加可选active_revision；新管理文档必须返回整数，legacy为null。`GET /status/{task_id}`保留原HTTP200状态协议：后台最终CAS冲突返回FAILED及稳定error.code=revision_conflict、http_status=409，不伪造一次异步失败为已经发出的HTTP409。同步接收阶段冲突直接HTTP409。客户端据列表或成功结果取得修订；不要求盲猜版本。

## 发布、查询、删除与恢复

1. **入库prepare：** 真实文件解析→chunks→本地embedding→向量及KG不可见暂存。DOCX/XLSX与PDF最终走相同发布服务；PDF复用已解析MinerU输出，不重复外发原件。解析/embedding/必需索引失败不得用degraded伪装向量已就绪。
2. **提交：** 资产写完、fsync并hash校验后，SQLite事务校验文档状态/修订CAS、写入版本引用、切换active、写任务成功收据。HTTP状态仅在此后暴露DONE。提交前失败无新可见版本；提交后崩溃通过收据恢复DONE，不能重复扣费重嵌入。文件系统和SQLite不宣称分布式原子事务：未提交资产是可辨识孤儿，先隔离，后显式回收。
3. **查询：** 服务端授权得到document_id/active_revision集合；新增内部`read_snapshot()`上下文，目录读取、向量search及iter_record_pages显式接收同一只读连接/事务，不能各自新开连接。向量与BM25/Table在此前置过滤快照中构建，禁止先全局top-k再裁剪。KG引用manifest固定资产版本并持有读取pin。生产门面、兼容_collection.get、管理员全局、CLI也只读取committed active记录，不暴露prepared/inactive版本；只有受控发布/管理内部接口可访问非活跃记录。多查询路径结果带实际doc/revision，不混代。
4. **更新：** 新修订prepare期间旧修订继续服务；commit后新请求只见新修订。缓存键含generation及授权范围。生成后关闭旧读事务，在新事务读取最新目录并重新通过实际tenant服务授权；外部权限不冒称与SQLite跨库原子。最后授权及可见性核验成功定义为允许返回的线性化点，此后网络在途字节无法撤回。此前发现删除/撤权返回404/403并丢弃旧结果；仅版本变化允许一次完整重取，丢弃旧答案、sources、trace和检索结果，仍冲突409。不能沿用旧事务复核撤权。
5. **删除：** 先授权，SQLite事务写tombstone并撤销所有版本可见性及活跃向量引用，创建精确cleanup记录，然后可重试清理无pin资产和索引。资产路径无法安全解析时标cleanup blocked，仍撤销可见性，禁止触碰不安全路径。逻辑删除提交后不因物理清理失败重新可查；DeleteResponse保留status=deleted，新增cleanup_status及cleanup_pending（未清完为true），不称物理擦除已完成；清理完成pending=false。未知文档404，不按文件名前缀删除。现有要求路径异常409且不删除的P0测试须按该经确认的语义修改为逻辑撤销/危险资产字节不变，不能直接删测试绕过冲突。
6. **重启：** 从权威目录和提交收据恢复；丢弃进程内缓存，按活跃授权版本分页重建。未提交prepare不自动发布，已删除数据不复活。执行中的无租约任务明确标interrupted/可安全重试，不冒称已有持久化队列自动续跑。数据库损坏/schema不符/运行库不符返回未就绪，不能创建空库伪装恢复成功。

## 运行库、旧数据及安全

生产VectorStore实现目标换为SQLite，main runtime锁去掉Chroma并显式声明NumPy。**兼容准入关闭前，默认生产启动返回compatibility_not_approved并禁止新生产库读写；仅专用合成数据集成配置可执行验收链，不能fallback Chroma。** 门槛解除须契约依据、独立评审及同快照复验，不由环境变量自行豁免。Chroma仅留独立离线迁移环境。默认目录检测旧chroma.sqlite3且无已确认新存储时返回migration_required；不能静默创建空库。新集成验收使用专用空目录，原生产目录不动。

Windows复用已审派生Python运行库组合的可重建配方及hash，不替换系统/用户其他Python DLL，不提交不明二进制。Linux容器必须另验证实际SQLite版本、setconfig、编译能力及安装锁；旧`python:3.12-slim`不是充分证据。启动探针按真实runtime能力fail closed，readiness和health不再探Chroma表。备份使用SQLite在线backup并绑定manifest和资产hash；禁止仅复制活跃DB主文件忽略WAL。

`services/catalog.py`的Chroma私有统计也必须改为存储公开探针；Docker同时持久化output数据库、uploads原件及登记的不可变资产，不能只挂数据库卷。重建容器恢复属于独立实际验收，未执行时保持部署未验证。错误链以合成敏感标记测HTTP、任务响应及真实日志，不仅检查异常str；旧全局索引快照没有generation/授权身份时应丢弃重建，不能视为可信缓存恢复。

统一配置由backend/config.py管理storage root：容器/app/output为数据库/派生索引、/app/uploads为原件、不可变KG/版本资产在output下，分别持久挂载；固定模型在只读/app/models，runtime在只读/opt/graphrag-runtime，应用非root仅有数据目录写权。实际镜像固定基础digest、runtime源/补丁/hash，最终非root用户实跑逐连接硬化/WAL/backup/重建恢复；不能把Windows成功外推Linux。

备份步骤固定目录/DB快照的资产清单并建立pin→在线backup及复制该清单资产→逐项hash校验→备份manifest封存→释放pin，任何失败不得发布备份成功。恢复先在隔离目标完整验证DB/schema/runtime与所有资产hash，包含tombstone/收据/cleanup，再原子启用恢复目标；不在活库上覆盖。backup期间更新/删除及cleanup并发必须真实验证。

2026-10-27数值准入更新：[入口合同](../contracts/2026-10-14-vector-ingress-semantics.md)最新节记录同源serde_json/Zmij原生桥、精确I64恒等及独立算法论证；原官方Windows wheel签名与完整声明依赖图的保守feature超集已独立核实。在明确采用官方签名构建正常执行声明source/lock/configuration的通常信任前提下，可关闭旧Python formatter近似和内置数值标量的parser-feature依据缺口。原workflow无显式--locked、浮动action及自托管runner和未取得实际rustc调用仍须披露；不外推全部原wheel/PyO3对象语义、Linux或可复现构建。**默认生产激活/迁移准入不得凭335组或本次单项关闭自行开放**；完整adapter及最终同快照验收、运行库/原生安全/模型部署条件仍分别核验。包audit不覆盖SQLite/CPython/OpenBLAS/CRT全部原生风险；原生SBOM和适用性审查另列，未完成不称安全清零。

## 整体验收出口

必须使用正式生产模块、真实FastAPI鉴权、SQLite磁盘文件、解析器及固定本地embedding模型，合成无敏感DOCX/XLSX和MinerU包；不mock存储/授权/发布/恢复。不允许联网下载替代固定模型身份。外部MinerU/生成API只在明确边界用本地HTTP契约服务验证；该层不称真实云供应商验收。完整云链未执行单列限制。

- 同一连续场景：A上传v1→HTTP向量/BM25查询只见v1→显式更新v2→只见v2→全新进程重启仍见v2→删除→重启仍404且其他文档可查；再单列备份恢复，tombstone不得丢失。用户要求的删除后重启必须保留，不能只测删除前重启。
- A/B同名文档、跨租户、项目撤权、管理员无权限默认值、相同chunk内容及ID碰撞；任何阶段都不串数据。显式向量请求失败503，不能成功空结果掩盖存储错误。
- 137条以上跨多页，最后页目标可召回；页大小1/17/256等价，生成器异常/早停释放事务；合法大记录/维度/k不新增限制。
- 在prepare、文件写完、DB commit前后、DONE前后、删除commit后各做真实子进程终止/重启；核验可见版本、终态、无重复发布、无复活和孤儿状态。
- 同文档并发更新、更新/删除竞争、查询/删除及撤权竞争；模型指纹不符、维度错、磁盘/锁故障、坏schema、错误备份hash均有可识别失败。
- v2后查询v1独有文本不得召回；legacy-only删除后保留原JSON并重启/备份恢复不得复活；最终检查前撤权、清理物理失败后新查询不可见、备份期间并发更新/删除均需单列断言。
- 最终全backend固定生产范围（包含新增未导入文件）行/分支分别≥90%、规定测试全部通过、锁检查及全依赖扫描；前端/rag_eval按固定影响策略复验或精确输入无漂移证明。独立设计及代码复核关闭阻断项，原生/部署未验项明确列出。

设计起草时未修改生产代码、依赖或现有资料；确认后开始隔离实现，当前进度及实际验证见[memory接续](../../memory/2026-10-25.md)。现有生产资料未迁移。实施步骤见[计划](../plans/2026-10-19-vector-production-integration.md)。

2026-10-28验收接续：Windows后端R7完整2157项及119全范围双90已独立核验，报告绑定当时315派生运行库与主锁，非跨平台生产批准。当日全锁扫描新检出msgpack1.2.2安全公告；原生审查确认CPython3.12.16具体安全修补与现有315未闭合项，项目可达性和位宽适用性分别记录。保持默认准入关闭，先在隔离候选修补依赖/runtime并验证，任何替换后重跑受影响完整验收。Linux316基础已取得但SQLite仍不达floor，私有SQLite/桥、非root容器重建及完整原生适用性尚未通过；见[本日记录](../../memory/2026-10-28.md)。此段为测试后规范进度回流，不改变R7归档原始输入或报告。


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
