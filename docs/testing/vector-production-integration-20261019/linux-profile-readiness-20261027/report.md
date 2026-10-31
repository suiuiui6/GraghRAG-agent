# Linux profile readiness — 2026-10-27

本报告为独立只读核对和下一步配方，不是 Linux 执行/批准收据。只写本目录；未修改目标树源码、配置、测试、运行库或 Git 配置，未操作 Docker，未启动重负载，未执行历史 Chroma。未读取 R4 原始失败日志或进程 CommandLine。

## 输入及核对范围

- 目标树：`C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent`。
- 实际只读 Git 命令确认分支 `codex/safe-snapshot-20261019`，HEAD `b1e300f1445c48f9f838bcc0d7b91cb39c1171b2`。有大量现行未提交向量集成修改；HEAD 不能单独代表被测代码。报告行号指本轮读取的工作区文件。
- 已读根 `AGENTS.md`、`memory/index.md`、`memory/2026-10-27.md`、1019 设计/计划以及相关实现/证据。`backend/AGENTS.md`本轮路径检查不存在，继承根规则。
- `memory/2026-10-27.md:33-41`明确 R6 正在执行、119 文件固定生产覆盖范围、2157 项收集，Linux engine 缺失。此为阅读到的记录，不是本报告独立 Docker 探针，也不预报 R6 结果。

## 已核实事实及能力边界

1. 生产准入仍关闭。`backend/vector_runtime.py:48-69`仅接受严格类型和标记的合成配置；没有环境变量生产豁免。`:10-15,71-101`要求 SQLite ≥3.53.2，并在每个连接设置及读回 defensive=true、trusted_schema=false、extension=false，以及外键开启。仅换新 `libsqlite3` 版本号不能代替 Python `_sqlite3` 编译常量/接口及逐连接实测。
2. Linux 运行库设计已经明确。`docs/design/2026-10-19-vector-production-integration.md:62,66`要求单独验证 SQLite/setconfig/编译能力/安装锁，固定基础 digest、runtime 源/补丁/hash，在只读 `/opt/graphrag-runtime`、只读 `/app/models` 和非 root 用户下做 WAL/backup/重建恢复。无需重开整体架构设计。
3. 当前镜像未提供该 profile。`Dockerfile.backend:4-5`用未 digest 固定的 `python:3.12-slim` 和 uv 镜像标签；`:18-20`确有 `uv sync --locked --no-dev --no-install-project`，`:23`复制 backend，`:26,39`建立数据目录并切非 root，但没有安装派生 SQLite/runtime 或 Linux 桥，也没有固定模型挂载。`:36-37` readiness 路由已正确。不能仅凭 Docker build 成功宣称 runtime 合格。
4. compose 的数据库和原件卷已存在：`docker-compose.yml:18-21,74-76`挂载 `/app/output`、`/app/uploads`，配置为 ro。只读模型/runtime 及实际销毁重建容器恢复仍需验证。不要为验收使用其真实 `backend/.env`、固定生产容器名和现有生产卷；创建专用合成验收配置/卷即可，不需要启动整个监控栈。
5. Linux 桥目标映射存在，但批准构建不存在。`backend/vector_numeric.py:32-39`仅认可 x86_64/amd64，Linux target 为 `x86_64-unknown-linux-gnu`；`:50-72`必须校验平台匹配、release、features、源/锁/二进制 SHA 和 approved=true。`:4-5`明确可信目录及 manifest 对服务账户只读，包身份不等于原生审计。当前 `bin/`实际仅 Windows EXE 与 Windows approved-build.json。
6. 当前构建器有意禁止 Linux：`backend/native/vector_numeric/build.py:16-17,25-40`固定 Windows target/name，非 Windows 明确退出，且 Windows 使用 `cargo +stable`后检查 rustc=1.94.0。`backend/tests/test_vector_numeric_build_policy.py:54-61`明确断言 Linux/posix 不启动编译。因此不能把移植 Linux 实现描述成“现成命令已支持”，也不能直接删除此断言制造通过。需要独立批准一个保持原有失败关闭语义的 Linux 构建/安装路径及对应有效测试；可先在隔离副本完成候选。
7. 源、依赖及语义可复用：`Cargo.toml:7-9`锁 serde_json=1.0.149(std、无默认 features)和 zmij=1.0.21；`rust-toolchain.toml:1-3`固定1.94.0。`src/main.rs:34-59`记录精确 f64 bits→同源 serializer/parser、I64及where分类；`:64-82`有界单次协议。`vector_numeric.py:75-120`有并发槽/超时/回收，不能推论硬资源沙箱。`:84-88`子进程只有精简环境，Linux二进制不能依赖父进程的 LD_LIBRARY_PATH 找非标准 runtime，必须验证实际链接/加载路径。
8. 已关闭的数值论据仅限合同声明域：`docs/contracts/2026-10-14-vector-ingress-semantics.md:64-74`保留原 Python/宽整数路径，不将 Windows wheel 来源依据外推 Linux；Linux 若要声称与原 Linux wheel 完全相同仍需 target 来源依据。可以用已批准同源算法依据验证新平台候选，不能宣称已审查一个未取得的原 Linux wheel。
9. 原生扫描仍不完整。`docs/testing/vector-production-integration-20261019/native-audit-20261025/current-receipt.json:16-21`为桥 Cargo.lock 的 exit0，数据库 commit `21d909e4c8bd4e14c7aea58bf980c881a0053ab1`，明确 `--no-yanked`、非完整原生runtime。包层双扫描为历史 Windows 证据；`runtime-20261022/README.md:17`及`security-lock-patch-20261026/runtime-receipt.json:189`均限制 Windows。不能以0公告替代 Linux ELF、libc、CPython、SQLite、OpenSSL、NumPy/OpenBLAS及模型依赖原生库的盘点/适用性审查。

## 可直接复用的固定输入

| 输入 | 已有依据 | 可以复用与不能外推 |
|---|---|---|
| CPython 3.12.15 同一 PBS release 的 Linux x86_64 GNU安装包 | `docs/testing/sqlite-runtime-r7-20261015/release.json:5911,5937`，`cpython-3.12.15+20261013-x86_64-unknown-linux-gnu-install_only.tar.gz`，SHA256 `5d546fc004fc2435fa142eb8f42ed8de5eb4725963dc22f7e6671014a80eb560` | 已有官方 release 元数据，可直接用作精确来源候选；未取得/执行 Linux原件，不能声称已安装或 SQLite动态可替换。 |
| SQLite 3.54.0 源 | 同目录 `sqlite-official/download.html:130-136` | 官方归档页面已记录 amalgamation SHA3-256 `7b670a62fdfbd672b75fef004cb703c8a3e87d3a5cc7d675b4a08337004a2d93`，autoconf SHA3-256 `f5e3e724e9c9b3b5d512c76b02082091a59eeea9becd169a9fbf4d376403acce`。URL候选 `https://sqlite.org/2026/sqlite-autoconf-3540000.tar.gz`；须取得原件并匹配后才构建。Windows DLL receipt 不能用作Linux ELF身份。 |
| NumPy 2.5.4 cp312 manylinux x86_64 | `backend/uv.lock:1396` | SHA256 `fbde6962867ee75b48b0ee29b2b9372ec5d617799dbaf38e82dc0596f2f7738a`；可与现行主锁一致安装。不能外推Windows OpenBLAS DLL版本/摘要到该wheel；须实际读取 `np.show_config()`及ELF依赖。 |
| 桥源码/Cargo.lock/toolchain | `backend/native/vector_numeric/`；当前Cargo.lock SHA256 `4029ef11d930d910cf4e403134d8f0ade519c144b43eee54fc7ee93cbd880018` | 保持不变复制到隔离候选。Linux要新二进制/收据/manifest及独立审，不复制Windows approved标志。 |
| 固定模型 | `backend/services/document_runtime.py:21-43`；`tests/test_vector_pinned_embedding.py:32-37`；`tests/test_vector_http_lifecycle.py:454-466` | 复用既存模型所有文件 SHA、revision、512维和归一化profile；仅将 receipt 的本地 snapshot 路径映射为容器只读路径，不改模型身份。未提供receipt会 skip，不能当验收成功。 |
| 安全与运行探针方法 | `runtime-20261022/runtime_probe.py`、R7 `derived_probe.py`及身份归档 | 可复用安装版本/RECORD核验、真实SQLite/NumPy blob roundtrip、加载库摘要方法；脚本中Windows DLL枚举、绝对路径和平台计数不能原样作为Linux证据。 |

Linux原件的本地存在情况：本轮列出 `D:/graghRAG-agent/.tmp/sqlite-runtime-r7-20261015/`，见已有Windows原件/派生目录；没有在该已知目录见Linux Python或SQLite源归档。未全盘搜索，不能声明全机器均不存在。现有release/download元数据已经足够先准备精确下载清单，不缺总体方案。

## 最小实施顺序（待执行；不改变生产gate）

1. **等R6结束并冻结输入。** 保存最终源码/测试/配置/主锁/桥/模型清单SHA和R6结果。Linux尝试使用新隔离目录、新构建上下文、新容器名和合成卷；禁止修改正在运行输入。主代理负责本地Docker启动及`docker info`/Linux架构探针；本报告未执行。
2. **先运行库最小真实I/O，而非整backend。** 固定`linux/amd64`和GNU/glibc基础镜像digest，固定uv二进制摘要和工具包版本。先获取上表Linux PBS原件、匹配已有官方SHA，检查其`_sqlite3`版本、常量、`setconfig/getconfig`、实际ELF依赖。如果已达floor且硬化成立，可直接作为候选，不要为“派生”而无理由替换组件。若SQLite不足，先检查其SQLite是否静态链接，不能假设设置LD_LIBRARY_PATH就能替换。
3. **不足时按现有3.54.0源建立派生profile。** 获取/校验上表autoconf原件，在独立builder以固定编译器构建共享SQLite到`/opt/graphrag-runtime/sqlite`，启用线程安全，保留extension接口并让运行时每连接关闭；使用真正Python3.12 `_sqlite3`。动态可替换时用项目私有稳定加载路径安装；若PBS静态链接，改用**官方CPython3.12.15源重编译候选**，先取得并核验官方源SHA/签名，不能借WindowsPython包摘要当源摘要。可用`CPPFLAGS=-I/opt/graphrag-runtime/sqlite/include`、`LDFLAGS=-L/opt/graphrag-runtime/sqlite/lib -Wl,-rpath,/opt/graphrag-runtime/sqlite/lib`、`PKG_CONFIG_PATH=/opt/graphrag-runtime/sqlite/lib/pkgconfig`让configure选新SQLite；保留configure/make日志、compiler、源hash及全部模块自测。此CPython源原件与SHA是新增待取输入，不伪造已有。此为局部runtime实现路径，不是新架构。
4. **运行库MVP断言。** 新私有venv只安装锁定NumPy2.5.4 Linuxwheel；记录`sys.version`、`sqlite3.sqlite_version`和`sqlite_source_id()`、`PRAGMA compile_options`、`_sqlite3.__file__`、`readelf`/`ldd`或实际`/proc/self/maps`加载库路径与hash、`np.show_config()`。以最终非root账户真实运行生产`probe_runtime()`、两个独立硬化连接、磁盘事务/rollback/WAL写读、跨新进程重开、在线backup/restore及NumPy blob/余弦小输入。MVP保留精确命令/exit/报告，不借原型行为代替正式adapter验收。所有失败先定位，不降低floor/常量要求。
5. **Linux桥独立最小构建。** 在与runtime同GNU目标的隔离builder预取并校验Cargo.lock依赖及rustc1.94.0，再离线执行`cargo +1.94.0 build --offline --locked --release --target x86_64-unknown-linux-gnu`、相同toolchain的`rustc --version --verbose`和`cargo tree --offline --locked -e features`，保留精确命令、features及ELF依赖/源/锁/二进制SHA；拒绝float_roundtrip/arbitrary_precision。这是候选命令，**不能通过现行Windows build.py执行**。先用候选CLI合成finite f64/I64/U64/负零及formatter反例真实I/O；独立审Linux源码feature/目标前提、协议和安装收据后才安装Linux批准包到隔离候选树。批准机制须保持构建收据默认unapproved、明确SHA批准、源/锁漂移拒绝，服务账户不可改二进制/manifest/源。当前builder限制对应测试需经评审改为批准平台矩阵，不能删失败断言。production gate仍关闭。
6. **扩展到最终后端安装和部署候选。** 用现行backend主锁在Linux `uv sync --locked`，保留实际选用wheel、RECORD/hash、安装全清单与平台marker结果，核对local LangExtract；不得复用Windows159包计数，Linux含不同依赖。复制固定模型只读挂载，receipt仅改snapshot路径，设置离线标志。最小候选先验证数值桥/生产storage/runtime/readiness/model suites，再同一输入运行真实HTTP连续生命周期和backup suites；此阶段必须显式提供合成配置，正常默认startup仍返回compatibility_not_approved。
7. **实际非root容器重建验收。** 只用专用合成卷，连续v1→v2→新容器仍v2→删除→再次新容器404且B正常，独立backup/restore及tombstone/cleanup/receipt/hash验证；保留原件/不可变资产及output卷。进程重启测试不能替代删除重建容器。检查非root对runtime、model、bridge及manifest无写权限，仅数据目录可写，Docker实际mount为ro。不要使用environment变量开放生产gate。独立关闭受影响契约与代码问题，最终相关全量双90/安全验证绑定新快照；如果修改production构建器/测试，先前R6不再是那些修改的最终证据。
8. **完整原生清单与适用性。** 固定镜像OS包清单、所有实际ELF/加载库、CPython/SQLite/openssl/libffi/zlib/libc、桥Rust依赖及rust std/compiler/系统链接、NumPy及实际OpenBLAS/GFortran/OpenMP、模型栈Torch/其它native包；记录版本、来源/构建flag、hash、ownership、许可证、扫描数据库与时点。执行Python包全锁和Linux实际安装扫描、Cargo锁扫描及系统/native公告适用性审查，保留未修/未知项。只扫描Cargo.lock不包含glibc或rust std；只扫描pip不等于native清零。此项未闭合前报告安全未完成。

## 阻断分类及可以先准备的内容

- **执行环境缺失：** 依据memory记录Docker Linux engine当前缺失；主代理可在R6结束后正常CLI启动。仅此不阻止固定下载清单、构建配方、审查检查表准备。
- **原件缺失/待核：** 已有LinuxPython、SQLite源及NumPy的版本/摘要元数据；已知runtime目录未见相应Linux原件。固定base digest、Linux工具链原件及完整SBOM、必要时官方CPython源码摘要仍需取得；不能编造。
- **实现/批准缺失：** 当前build.py不支持Linux且测试刻意拒绝；需要局部候选实现、真实Linux运行、独立批准。不能手填approved=true绕过既有身份合同。
- **验收缺失：** Linux实际硬化/MVP、桥ELF、模型离线身份、全链/容器重建、native适用性和权限未执行。本报告没有将其中任一项标为通过。
- **已有设计可复用：** 1019设计/计划已覆盖runtime/只读模型/非root/卷/恢复/审计；不需要改变兼容参考定义、合法数值域、资源容量、生命周期或拓扑。

## 只读官方资料核对

本轮浏览官方Python/PBS文档验证构建和能力边界，没有以可变网页替换固定归档版本：

- [Python3.12 sqlite3文档](https://docs.python.org/3.12/library/sqlite3.html)：setconfig/getconfig为3.12接口，SQLITE_DBCONFIG常量是否可用取决于编译时SQLite；因此必须实际验证常量与加载库。
- [Python3.12 configure文档](https://docs.python.org/3.12/using/configure.html)：说明编译要求与SQLite加载扩展构建选项。页面当前标题为3.12.16，不代表本报告已把候选3.12.15升级。
- [PBS Distribution Archives](https://gregoryszorc.com/docs/python-build-standalone/main/distributions.html)：full archive提供`PYTHON.json`描述目标及构建/安装产物，若需判定静态链接应读取精确发行原件/ELF，不据名称猜测。

本轮只执行Get-Content/rg/目录枚举和Git分支/HEAD/status读取及上述网页读取。正常读取命令完成；一个含不存在猜测路径的rg批次exit1（`.../runtime/python/include/python3.12/pyconfig.h`不存在），这不构成runtime编译实测失败。本轮没有运行pytest、编译、安装、扫描或容器命令；不提供虚构exit0。
