# Windows libuv 修补路线评估 — 2026-10-29

状态：路线评估已通过独立设计审查；仅支持继续有界证据调查和制定实施计划。未实施安全 backport 或 Torch 重建，未批准正式运行库替换。

## 决策建议

优先进行“精确旧基线 + 相关安全修补集 + MSVC/UCRT”的有界可行性验证，先关闭补丁依赖审查，再决定是否编译。它最少扰动现有 Torch wheel，但只能作为自维护的过渡制品；不仅需2024修补，还须处理旧基线同一 IDNA 路径的2021越界读修补。若补丁集扩散、无法维护，或不能证明 ABI、修补行为或真实 TCPStore 稳定性，则停止此路线，转向匹配 libuv 1.53 的完整 Windows Torch wheel 重建。长期应优先恢复到上游支持的依赖组合。

不采用把新版 provider count 强改为 3、伪造 uv_loop_size、改版本号消除告警、仅换新版 DLL 或只编译单个 C++ 文件的方案。

## 已核实的起点

- 实物为 Torch 2.14.0+cpu，源码 commit `08187d9e0fba026dc8217405802ab5381dc88d90`。当前 uv.dll SHA256 `fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8`，公开版本 API 返回 1.40.0。
- 精确 Torch commit 的 Windows CI 使用 libuv-1.40.0-h8ffe710_0 包；已获取包中的 DLL 与实物逐字节一致，包内头文件与官方 1.40 头一致。这是强上游映射，不是该 wheel 专属的完整编译 attestation。
- `TCPStoreLibUvBackend.cpp:706` 按值内嵌 `uv_loop_t`，其后紧接 `tcpServer_`。源码没有通过 uv_loop_size 动态分配这一字段。
- 旧版公开 API 实测 loop464，新版候选实测 loop472；同一编译器的常量 COFF 实验证明 provider 数量 3→4 使 SOCKET 数组增加 8 字节，后续成员偏移随之增加。不能把差异归咎为仅编译器问题。
- 已完成的 libuv1.53 隔离 MinGW 构建可用作研究证据，不能作为此旧 wheel 的替换物；它另有 MSVCRT 与原 UCRT 差异。
- 官方公告包含 Windows 对应实现。当前固定模型未找到分布式入口，只是窄范围静态阴性证据，不能关闭漏洞。

## 路线 A：保留旧 ABI 的安全 backport

基线取精确旧依赖包对应的 1.40 源及发行布局补丁，分别保留源码、补丁、工具和产物身份。参考上游安全提交 `0f2d7e7`、`3530bcc`、`e0327e1`：修复输出结尾 NUL 的空间检查、拒绝空 IDNA 输入并同步测试期望。改动涉及内部 `src/idna.c` 和测试，不需要引入第四个 provider 或修改公开头文件。

这是源码级可行性判断；没有实际应用补丁、编译或证明 ABI。旧基线的上下文、错误传播和测试框架必须逐项适配并独立审查，不能盲目 cherry-pick 或仅复制新版整个文件。

新增安全前提：Node 官方2021公告记录 `CVE-2021-22918`，同一 IDNA 转换函数存在越界读。调查发现1.40与1.42的遍历/解码边界处理不同，因此只回补2024三提交不足以签收从1.40重建的候选。须定位并锁定2021对应修补及其测试依赖，检查 Windows 源码适用性，增加输入末端/截断UTF-8/空输入的无越界测试。此为新增必要调查项，尚未应用补丁或实物利用验证；没有把现有DLL仅凭版本直接认定为已复现漏洞。

使用锁定的 MSVC/UCRT 构建，核实 AMD64、发布模式、导出、调用约定、CRT 模式和依赖来源。原包配方声明 VS2017/VC14.1；本机现有 MSVC14.50 并非原工具链。较新 MSVC 可作为待验证候选，不能直接宣称完全等价。

最小验收顺序：

1. 审查旧源+补丁 diff、公开头零变化及合法输入行为边界；为2021/2024两项及其他已知公告建立明确适用性记录，2021修补依赖未闭合前不得进入候选签收。
2. 隔离编译，与旧基线对比所有消费者相关结构的 sizeof/align/offset、符号及回调签名，至少 loop/tcp/timer/async/connect/write/buf；loop 必须仍464，但仅同尺寸不足以通过。
3. 原版与补丁版运行相同 IDNA 测试，包含空输入、非 ASCII/非法 UTF-8、容量恰好边界、长输入、合法域名和哨兵内存；检查安全修补与错误传播，不连接外部目标。
4. 在受控本机边界验证 Windows resolver 拒绝路径及上游适用测试；记录异步/同步返回及回调约定，不向公网发送测试载荷。
5. 先做单库 loop/timer/async/TCP/关闭和超时，再以复制的私有完整 Torch 环境运行显式 libuv TCPStore 多进程 set/get/wait/timeout/关闭重启；核实真正加载的 DLL 路径和 SHA。
6. 完整固定 BGE 推理及入库→查询→更新→删除→全新进程恢复链；新运行库输入冻结后重跑固定生产范围测试与行/分支各90%、漏洞扫描和独立评审。

安全维护代价：1.40 不属于当前上游维护版本。即使本 CVE 的补丁验证通过，版本扫描仍可能报警。保留真实基线版本，使用单独补丁制品 ID、补丁清单/SBOM、实际二进制 SHA 和精确范围的 fixed 状态证据；不得以“not affected”泛化，不能删除告警或据此宣称全部 native 安全。

停止条件：需要改变公开布局或大范围依赖才能回补；无法建立可信工具/产物链；导出/CRT/消费者验证失败；回补不足以覆盖本公告的真实 Windows 路径。任何一种成立即不推进正式采用。

## 路线 B：针对 libuv1.53 重建 Torch 消费者

将新版 libuv 和所有实际链接、嵌入或访问其结构的消费者用一致头文件/工具链重建，以完整 Windows Torch wheel 为交付单元。不得把单个 TCPStore C++ 文件临时编成插件替换现有 libtorch_cpu.dll。

先核清完整 PE 导入闭包与构建配置，再锁定 Torch commit、子模块、Python3.12 AMD64、MSVC/SDK/CMake/Ninja、构建依赖和 libuv 源/头/CRT模式。验证构建确实使用1.53头/库，避免脚本重新下载旧1.40包或读取其他 LIB/INCLUDE 路径。

精确commit源码映射已核实：`build_variables.bzl` 的 `libtorch_distributed_base_sources` 经 `caffe2/CMakeLists.txt` 并入 `torch_cpu`，因此需要重新编译相关对象并重新链接该聚合库，完整wheel是建议交付单位，不是声称所有无关对象一定需要变化。当前构建脚本默认VS2022、可选2019，pyproject使用scikit-build-core及Windows Ninja，CMake要求C++20/C17并有显式CRT模式分支；旧README里的VS2017段落不能替代精确构建脚本。缺libuv时配置可能关闭distributed/Gloo：这种“成功构建”没有覆盖目标消费者，必须判为MVP失败。

先以 CPU wheel 做隔离 MVP，不改变项目正式 CPU/GPU 默认。GPU 交付需另有 CUDA/cuDNN 等匹配和实测，CPU构建成功不能替代。

验收要求除路线 A 的真实行为/最终项目门槛外，增加消费者布局一致性、完整 wheel 安装/pip check、所有 native 导入解析、Torch Tensor/推理功能和必要的分布式测试；检查新 wheel 其他原生依赖，不能仅检查 libuv。

本机只读盘点：MSVC14.50.35717 和 WindowsSDK10.0.26100.0 目录存在，VS自带CMake存在；cl/cmake/ninja未在普通PATH解析。可见逻辑处理器20，C盘剩余约9.84GiB、D盘约67.08GiB（本轮瞬时值）。CIM查询被拒，物理内存未知；完整源、子模块和构建峰值磁盘/内存尚未测量，不能承诺本机可完成或给出可靠构建耗时。不通过清理其他任务文件换空间。

## 隔离、失败与回滚

两路线均新建私有候选目录，保留旧 wheel/runtime 不动；依赖下载先锁身份，编译阶段断网且有资源/时间上限。只在结构和链接前置检查通过后进入消费者子进程，异常立即停止。正式采用应以新的可回退 wheel/runtime 制品交付，不能原地修改现有虚拟环境导致 RECORD 与字节不符。

当前授权仅为评估，不据此安装全局工具、发布 fork、构建新正式运行库或改变生产 gate。后续需在用户确认路线及局部设计/计划后实施。

## 来源

- libuv 公告：https://github.com/libuv/libuv/security/advisories/GHSA-f74f-cvh7-c6q6
- 上游三提交：https://github.com/libuv/libuv/commit/0f2d7e7 、https://github.com/libuv/libuv/commit/3530bcc 、https://github.com/libuv/libuv/commit/e0327e1
- 官方维护政策：https://github.com/libuv/libuv/security
- 2021官方安全公告：https://nodejs.org/en/blog/vulnerability/july-2021-security-releases
- 实物布局与消费者映射：`D:/graghRAG-agent/.tmp/windows-uv-loop-layout-debug-20261029/REPORT.md` 及 `torch-header-mapping/REPORT.md`
- MinGW 候选边界：`D:/graghRAG-agent/.tmp/windows-libuv-artifact-static-review-20261029/REPORT.md`

两条路线调查证据分别归入 `backport-route/` 和 `torch-route/`；独立设计审查单列。无生产源码/运行库修改，无提交/推送/部署。
