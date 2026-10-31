# Linux 数值桥正式离线构建缺口：候选详细设计与实施步骤

2026-10-29；planner 只读输入，输出仅本 scratch。未获独立设计复核或用户新增同意，不是实施授权、语义准入或生产批准。

## 结论与范围

这是已确认 `docs/design/2026-10-19-vector-production-integration.md`“Linux单独验证runtime/构建/hash/非root”和计划第5节“正式runtime构建/核验脚本位置独立评审”的实施细化，不新增主功能、组件或产品行为。正式路径目前明确拒绝Linux，而消费者已能识别GNU target；补全离线构建及审查SHA安装可在原计划内提出和独立评审。保留数值协议、Rust源码、GPU默认、CPU私有锁身份及 `compatibility_not_approved`，不需要为此重新决定架构。

但“把私有CPU候选作为正式产品profile”“接受Linux原wheel语义证据不足而开放默认”“接受尚未关闭native风险”均超出此细化；若实际实施需要这些变化，必须回到用户产品/风险决定，不能以planner输出代替同意。此候选本身不作上述选择。

优先方案：扩展现有 `backend/native/vector_numeric/build.py` 的固定平台分支，保留build→独立审查SHA→install两阶段；正式容器只复制安装后的固定包。另开Linux专用脚本会复制批准逻辑并造成双权威，不推荐。直接复制私有MVP的approved包不能满足正式构建流程，排除。

## 已读事实及当前限制

读取C工作树根AGENTS、memory/index和10月29日记录、设计/计划、build.py、vector_numeric.py、Dockerfile.backend、docker-compose.yml、Cargo.toml/rust-toolchain及两套numeric测试、coverage配置。C源工作树由委派任务指定为 `codex/safe-snapshot-20261019`；本agent的git status提示不在worktree，后续显式git -C权限拒绝，不能独立声称该工作树clean或HEAD已核验。只读文件内容成功；未写该工作树。R11/CPU恢复结论来自委派与工作记录，并非本agent重跑。

实际缺口：
- build硬编码Windows，使用 `+stable` 覆盖固定toolchain文件，事后才验1.94.0/host；tree未带target，只排两项禁止feature后写固定feature名。
- install只比源/binary/SHA，未对receipt的target/profile/features/compiler作相同严格校验；schema1 runtime只验固定源文件与binary、target/profile/features/approved，忽略toolchain/tree。
- Linux复制binary若沿用copyfile，不保执行位；当前未证明正式安装后非root可执行。
- 正式Dockerfile是浮动python:3.12-slim、联网uv sync，无固定runtime/model/桥安装环节；compose仅两个数据卷与配置RO。不能把私有CPU镜像恢复成功称此Dockerfile通过。

## 候选接口与数据流

保持命令 `build.py build` 和 `build.py install <reviewed-sha256>`，不接受任意target、命令、特性、工具链或环境覆盖选项。仅allowlist Windows amd64→MSVC/exe，Linux x86_64→GNU/无扩展；其他OS/架构在启动编译前拒绝。默认构建输出位置保持 `target/<fixed-target>/release/<fixed-name>`，安装位置保持 `bin/<fixed-target>/`，不改vector_numeric的查找策略。

构建先验rustc/cargo实际身份再编译，固定 `+1.94.0` 与release/明确target、`--offline --locked`。在已锁定隔离builder使用固定cargo/rustc/linker与本地vendor/cache；无缓存直接失败，不联网补齐。清除RUSTFLAGS/CARGO_ENCODED_RUSTFLAGS、RUSTC_WRAPPER/RUSTC_WORKSPACE_WRAPPER、target/linker及rustup override等外来覆盖，或发现时拒绝；固定CARGO_HOME内config需纳入审核和hash，不读取用户级不明cargo config。不以build CLI无参数推定环境无注入。

先后hash输入（四现有源文件、build.py、固定builder配置/镜像与vendor manifest），不一致拒绝生成receipt。cargo feature/tree/metadata取同target、同锁与同环境，记录完整解析节点及feature集合，并校验当前精确allowlist；仅“没出现两个坏feature”不足以确认启用身份。捕获实际rustc命令/verbose build和 `rustc -vV`、cargo版本、linker/libc身份，记录命令、exit、builder digest、profile与binary SHA。若clean构建、可复现性未证实，只声明一次实际构建身份，不声明字节可复现。

保持现schema1 runtime最小manifest <=8192 bytes，新增构建细节放独立build evidence sidecar；manifest新增可选字段若需runtime校验必须同步约定，不能让runtime暗中信任sidecar。receipt保留实际compiler/tree而非模板伪造，源和binary files保持现精确映射。`approved=True`仅表示经过审查SHA的包安装身份，不表示Linux语义或生产批准。

安装在受控builder/packager完成，非服务启动时执行。严格验证receipt是dict且schema/target/profile/features/compiler及源映射符合固定策略；SHA必须64位小写hex且等于实际binary。全部验证在修改destination前完成。临时同目录写binary/manifest后以固定目录原子发布，失败不留下可被runtime认可的半包；不得边写运行中的包。GNU ELF机器类型及动态依赖闭包在独立审查中核对，错误平台即便SHA匹配也不签收。Linux安装binary0555、manifest/source0444，目录0555；由root或镜像构建者拥有，服务uid无写权限。使用实际安装SHA在新非root容器执行protocol probe，再签收安装结果。

RO条件是威胁模型前提，hash不是防有写权攻击者的认证：同一攻击者可改binary与manifest；不声称schema1的批准标记是签名。镜像rootfs/包/runtime/model均RO，不把bin挂到output/uploads；仅这两个独立数据目录可写（临时目录若确实必要需显式最小tmpfs并验证）。验证uid、stat、实际写失败和实际执行成功；仅检查chmod配置不算通过。正式Dockerfile未来集成固定digest/runtime与桥包时，先单独提出最小diff供审，不能借本候选把私有CPU升为正式或改GPU默认。

## 语义和安全分离

包安装成功只解决“以受审SHA构建并执行同一GNU桥”。Linux原Chroma wheel的source/lock/features/toolchain声明及适用信任依据、原PyO3抽取语义和全域数值证明仍按入口合同独立关闭，有限差分/22HTTP/三容器恢复不能代替。native SBOM及适用性、Torch/libuv风险继续开放。默认gate测试必须仍返回compatibility_not_approved，普通配置不能绕过；合成集成配置继续与真实数据隔离。不生成Linux compatibility-approved常量或环境开关。

## 候选实施步骤（未执行）

执行方式使用原计划的executing-plans或受授权subagent-driven-development。文件归属：构建coder仅build.py和test_vector_numeric_build_policy.py；runtime测试coder仅test_vector_numeric_bridge.py（如确实需变runtime，再独立评审精确契约）；容器集成单独owned Dockerfile.backend/compose，先处理正式profile决定，当前不授权改动。Rust main.rs/Cargo锁/业务模块不属于此修订。

1. 冻结当前C输入清单与R11证据；另建隔离candidate，不在冻结C运行build/install。独立reviewer先核此详细设计和精确feature allowlist/builder配置；父任务确认属于既有授权再编码。未知的builder digest、vendor完整SHA和GNU动态依赖版本必须从已有私有MVP实际读取核验，不填猜测值。
2. RED测试写入现有build-policy套件：两受支持target正确命令，wrong OS/arch/compiler/cargo/config/env在编译前失败；offline缺缓存、locked drift/feature drift、前后源漂移、编译失败无receipt。保留Windows原行为断言并将+stable预期受控改为固定版本。实际命令：在候选隔离backend环境运行 `python -m pytest backend/tests/test_vector_numeric_build_policy.py -q --tb=short -p no:cacheprovider`；保存RED退出码与具体失败断言。
3. 最小build改动通过上述断言；真实GNU固定builder断网执行 `python backend/native/vector_numeric/build.py build`，必须exit0且receipt approved=false、bin不存在。断网缺vendor负例必须非0，不准重试在线。独立reviewer核输入SHA、实际命令、feature graph、ELF/依赖与receipt后返回该次具体binary SHA。不同重编译SHA重新审，不复制旧批准。
4. RED安装负例：错审批SHA、binary/source drift、receipt target/profile/features/toolchain/schema/形状/缺字段篡改、目标安装写失败均不产生可认可包；旧已安装包不被失败安装破坏。GREEN用审查SHA安装，核安装binary hash相同、manifest approved=true、权限及nonroot协议。该SHA是本次review artifact，不是产品批准。
5. 真实GNU protocol正例：i64边界、u64 where、负零、2**63附近formatter反例、有限极值与非法非有限拒绝；运行现有bridge契约/篡改/超时/洪泛/崩溃/slot回收行为。真实RO服务uid运行成功，服务uid对binary/manifest/source/目录写入失败；移除execute位、错误ELF/动态库缺失必须安全NumericBridgeUnavailable且不暴露敏感路径/marker。精确命令 `python -m pytest backend/tests/test_vector_numeric_bridge.py -q --tb=short -p no:cacheprovider`。包假批准marker测试只验fail-closed contract，不能替代真实签收。
6. 独立代码审查关闭正确性/环境注入/失败包/权限问题，再root复跑。复验默认factory仍compatibility_not_approved；容器候选仍用隔离数据，引用既有CPU158/model身份而非把它写入正式默认。
7. 任何生产Python/测试/config变化后，R11仅历史。按原driver在最终候选重新执行全backend规定测试与fixed coverage配置，收集既有2201身份并保证没有消失；新增病例另计。现build.py已在backend source覆盖分母，不排除新增Linux分支；Windows全量用政策行为测试覆盖平台分支，真实Linux编译和权限必须另有实际证据。两项分别原始计数≥90%，不可跨平台平均。Rust源码未变可绑定无漂移诊断历史，但不得称GNU release已被Windows诊断覆盖；若Rust变更，重新全范围原始LLVM file branch/line核验及消费者回归。前端/rag按固定影响策略执行/绑定无漂移，扫描与锁检查同最终快照。
8. 仅受影响权威设计/计划/入口合同回流实际构建能力和剩余门槛，更新memory及证据manifest；在适用门槛全过前不commit/push。Linux语义/native未闭合时即使构建已验，也明确总体生产未完成。当前本planner不改这些文件。

## 自检与交接

需求→对应步骤：离线/固定身份2–3；审SHA安装4；RO权限/真实protocol5；默认gate6；全量coverage7；权威回流8。无新核心组件、无总架构重开、无新增产品开关。需独立评审确认的细节是现有feature精确图与可信builder/config完整身份，不是用户替工程师选择。若发现当前schema1无法在8192 bytes内容纳最小receipt，可把详细feature/tree移到sidecar但不能删当前runtime必要字段；schema演进须受影响契约独立评审，不凭容量问题放宽检查。

本次验证只读命令和文件内容核实，无测试、build/install、容器启动、覆盖、安全扫描或代码修改。C Git权限未知保留；未改默认、gate、正式docs、源代码或memory。候选须由parent纳入接续记录，避免把scratch当权威规范。
