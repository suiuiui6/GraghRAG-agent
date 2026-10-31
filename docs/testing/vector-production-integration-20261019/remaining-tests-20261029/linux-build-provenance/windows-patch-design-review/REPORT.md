# Windows bundled libuv 隔离MVP独立设计评审

日期：2026-10-29。技能：已读取 requesting-code-review/SKILL.md，按项目独立设计检查表适配。评审者独立上下文，仅写本目录；未下载、编译、执行候选、修改C工作树或正式R11。

结论：**隔离准备可继续；条件通过仅针对能力MVP，不批准替换、正式依赖或生产准入。** 预检方案覆盖需求与回退边界，跨编译是可测试假设。以下具体输入/检查须在对应阶段出口补齐，不能把尚未成功的方案写成已修复。未发现必须先向用户索取抽象产品选择才能准备的阻断项。

## 核实范围及事实

读取C工作树AGENTS、memory/index.md及2026-10-29相关记录、2026-10-19总体设计与计划的runtime/native/验收条款；读取预检REPORT、tools、pe-summary及pe-import-export。预检REPORT SHA256与委派值7954373c8df9b685c36f05c57aa0fd0ba8a66c59f15a70906933e9074bac2994一致。PE数据给出AMD64原uv.dll SHA fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8，288具名导出和torch_cpu.dll 25直接入口。未再次加载原DLL；1.40.0/CVE结论沿用已有证据，不声称本次独立重新执行漏洞适用性扫描。tools PATH空与后续MSBuild/SDK磁盘证据不冲突。

C工作树git status/rev-parse因平台Permission denied未执行成功，未伪报HEAD或clean；本任务无任何C写操作。父任务应把当前源码/runtime冻结清单绑定后续MVP，不依靠本报告推断C状态。

独立在线核查[固定v1.51.0官方README](https://github.com/libuv/libuv/blob/v1.51.0/README.md)：Windows正常构建依赖Visual C++，跨编译示例明确为“unsupported but generally works”。该例是i686，不能照抄为本次AMD64参数。1.x ABI声明不保证MinGW/MSVC结构布局、CRT与回调兼容；不将交叉编译称为MSVC等价支持。

## 重要检查点（阶段阻断，而非准备阻断）

1. **源/修补身份尚未确定。** 不能仅以1.48.0修复下限或Linux gitlink 1.51.0决定安全版本。先定具体官方tag/commit、完整tarball SHA、签名与可信维护者key fingerprint、公告检索日期及适用矩阵；若回补，逐一记录patch SHA/顺序/修改范围/对应回归。源码身份与安全依据无法建立则停止构建验收，不接受“当前未扫描到”替代已知CVE修复。
2. **构建闭包缺精确输入。** 固定已验证Linux builder digest；新增Debian snapshot时间、InRelease签名/keyring、Packages索引hash、所有MinGW/CMake及传递deb版本/SHA、target triplet/thread/CRT模型、CMake toolchain和编译链接flags。签名链必须抵达deb SHA；只固定下载URL不够。新增依赖许可/已知漏洞单列。仅在独立新镜像/目录安装，固定输入取得后构建禁网。工具执行受平台网络权限约束，安全整改授权不自动绕过平台审批。
3. **288名称/25导入不充分。** 补ordinal/forwarder及delay-import检查（现解析器未覆盖）；全表比较并分类兼容新增，所有旧入口必须存在且签名兼容，不因新版本多导出而机械失败。系统DLL/api-set与新增CRT须解释，禁止未知libgcc/libwinpthread旁载。获得原Torch对应libuv头文件/构建配置映射；对Torch实际分配/传递的uv_loop_t、uv_tcp_t、uv_timer_t、uv_async_t、uv_connect_t、uv_write_t、uv_buf_t等逐个给出sizeof/align/关键offset依据。候选头自洽不代表与旧MSVC消费者一致。若旧布局无法还原，记录ABI证据不足并停止正式候选批准，不能靠Tensor成功抹平。
4. **必须实际驱动libuv消费者。** BGE/Tensor可能不触发c10d TCPStore，不能单独证明uv兼容。用Windows原生独立子进程运行候选上游适用测试、loop/timer/跨线程async/关闭与取消、本机TCP读写/EOF/错误和线程join；再用现Torch实际libuv TCPStore后端（显式选用并证明实际路径）驱动连接、超时/重连、反复启停及新进程退出。全程本机fixture，失败/跳过原因完整保留，不把Wine/Linux构建测试当Windows运行验收。CRT跨边界对象须按真实分配/释放方验证，禁止跨不同堆随意free。
5. **派生身份须可重建和可核验。** 私有runtime可以作为首个MVP载体，须全新目录、独立身份、原wheel/保留文件全hash、patch-map及实际文件清单；原wheel RECORD对被改文件应明确标为失配，不得伪称原包完整校验通过。另建派生manifest为有效核验依据。若采取新wheel，METADATA/.dist-info/WHEEL/RECORD、文件名/版本/锁及旧签名处理一起核验；pipcheck不足以证明身份正确。原R11和原runtime前后hash无漂移是每阶段不变量。

## 有界、可执行的最小验收顺序

A. 输入冻结：在新D隔离目录登记上述源、builder和工具闭包；原R11/runtime只读hash与模型固定11文件、Python/SQLite/Torch/测试快照收据。停止条件为签名/源/安全映射失败。准备阶段不要求全项目测试。

B. 仅构建：以x86_64-w64-mingw32明确AMD64目标，Release shared与Windows测试可执行文件使用同一源和配置生成；保存完整命令、版本、stdout/stderr/exit、SHA。构建失败保留证据，仅修改受影响配置，不能转成全native重编。无须为本轮建立通用供应链系统或证明字节级可复现。

C. DLL候选门：静态PE/ABI差分先通过，再在受控Windows新子进程以绝对路径/受控搜索目录加载，记录实际GetModuleFileName路径和SHA及uv_version；加载后核模块依赖实际来源，避免悄悄加载原R11 uv.dll。执行上游适用测试和第4项真实消费者专项；若unsupported差异未闭合只保留研究产物。

D. 新派生runtime门：只复制到全新私有候选或从新身份wheel安装，核全hash/身份/加载路径/pipcheck；真实Tensor和固定BGE encode的512维/归一化/有限性，随后真实FastAPI权限、SQLite磁盘目录、v1入库→查询→CAS v2→新进程恢复→删除→再恢复404且其他文档仍可查。单列并发撤权/删除、commit前后故障、备份更新删除竞态及恢复。不mock核心依赖，不以改超时/删旧用例获取通过。

E. 最终候选验收：在最终代码+测试+lock+runtime快照重新全backend既定完整生产范围和全部规定测试，行/分支原始计数各≥90%，包含新增文件；前端/rag按既定影响策略复验或固定输入无漂移证明，第一方Rust保持既定独立范围。新runtime触发适用全锁/实际安装审计和native适用性复核。独立评审自行加反例，root复跑适用检查；失败不套R11历史通过。归档命令/时间/退出码/机器报告/前后hash后，才形成可供用户决定的具体候选。

## 授权与决定边界

在父任务所述既有安全整改授权内，可继续固定源/工具输入、隔离下载验证、构建及合成数据MVP；本报告自身未执行这些操作。无需为了可逆准备先问“装VS还是MinGW”。本机全局VS安装、外部发布/托管、部署、真实资料迁移均不在这次MVP授权范围。

即使MVP全部通过，采用unsupported交叉编译派生Torch作为正式长期维护依赖前，须呈现具体ABI/全链/安全报告及维护责任、更新渠道/支持平台，再取得所缺产品决定。若失败且需换正式平台/功能取舍或风险接受，必须另行决定，不能自行接受风险。生产compatibility gate持续关闭。正式集成的设计/计划回流与独立复核保留；没有理由扩大到全native重编或无限兼容证明。

本次仅完成独立设计评审，运行/构建/双90未执行，未提交、推送、发布、部署。
