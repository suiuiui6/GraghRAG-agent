# Windows libuv 最小修补能力与候选设计预检

结论：**当前环境未具备已验证Windows C/CMake构建链，不能立即承诺成功构建替代DLL；具备可准备的独立候选路线。** 本轮仅只读能力/PE检查，没有build、下载完整源、重封装wheel、修改R11/runtime或外部发布。

## 实际能力

- Get-Command逐一检查cl/clang-cl/clang/gcc/cmake/ninja/dumpbin/llvm-readobj/link/rc/msbuild/vswhere：均不在当前PATH，保留tools.json。PATH未命中不等于磁盘未安装，因此继续查官方VS安装器。
- 官方vswhere实际找到VS18 Community18.11.12315.225；`-requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64`返回空；已安装目录不存在`VC/Tools/MSVC`。限定VS安装根的文件搜索仅找到两个MSBuild.exe，未找到cl/cmake/ninja/dumpbin/link/clang-cl。
- WindowsSDK10.0.26100.0存在，包括rc.exe、ucrt/stdio.h、x64 kernel32.lib。MSBuild独立存在不提供缺失的C编译器、linker和CMake。
- 已知.tmp顶层缓存名检索未发现完整libuv源缓存；此前build-mapping只有固定官方版本头/idna.c等片段，不足以完整构建。该结论限于所列受控路径，不声明全磁盘不存在。
- 第一次工具检查PowerShell管道语法失败、后续修正执行；未把失败当作安装缺失证据。未读取OS进程CommandLine。

## 实物与最小 ABI 输入

自有只读PE32+解析器mmap读取现R11 Torch/lib/*.dll，没有加载执行：uv.dll AMD64(0x8664)、288个具名导出、SHA fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8。其正常PE依赖包含Windows API、VCRUNTIME140、UCRT，详情pe-import-export.json。

扫描Torch/lib DLL正常导入表：torch_cpu.dll导入uv.dll的25个函数，含uv_loop_init/uv_run/uv_tcp_*/uv_timer_*/uv_async_*/uv_close等，名单已保存。未在该正常导入表找到uv_getaddrinfo，**不排除动态GetProcAddress、转发或其他消费者，不证明全native不可达**。此解析器未声称覆盖delay-import/任意外部扩展。候选必须保留实际25入口并比较全部288导出、架构、CRT/调用约定/ABI，静态清单一致仍不能替代运行兼容测试。

## 版本与官方构建边界

[libuv v1.51.0 官方README](https://github.com/libuv/libuv/blob/v1.51.0/README.md)说明libuv1.x具有稳定ABI承诺；Windows支持CMake构建，需Visual C++工具链和WindowsSDK。官方示例为`cmake -B build -DBUILD_TESTING=ON`、`cmake --build build`、`ctest -C Debug --output-on-failure`。ABI承诺是设计依据，不是当前Torch候选通过的证据。

当前明确公告CVE-2024-24806修复下限1.48.0；Linux精确Torch源码gitlink是libuv1.51.0，可作为**候选研究锚点**。本轮没有核完1.51.0之后全部公告，因此不把1.51.0定为最终安全版本，也不擅自选择未来最新版。进入候选前需按当前已知CVE清单核对目标具体版本/修补提交，固定官方release签名/源SHA和工具链/配置。Windows原实物1.40.0未修结论不变。

## 最小私有候选设计（尚未实施）

1. 准备独立构建根/venv与锁定MSVC或已审定等价工具链、CMake、WindowsSDK；当前缺工具不是靠更换PATH可解决。优先复用已验证独立构建机/CI，避免污染既有R11。机器级安装编译工具若必要须单独走平台授权。
2. 取得核定官方libuv源/签名与所有修补来源，构建x64 Release shared DLL并执行上游测试；保留命令、退出、工具版本、源/产物SHA、PE依赖与导出对比。测试若涉及网络应限制为明确本机fixture，不默默放开外网。当前没有可报通过的构建/ABI数据。
3. 在独立候选目录复制原官方Torch wheel内容，保留原wheel SHA/签名来源及每个保留文件SHA，替换项仅限已验证候选uv.dll；重建**新的内部发行身份**（例如明确local版本/构建标识，最终按packaging/解析器规则核定），正确更新METADATA/WHEEL/RECORD及RECORD.jws/p7s处理，不复用上游wheel名称/原hash冒充官方产物。新wheel SHA/依赖锁/离线hash requirements需一致并独立评审。不得在现安装目录裸换DLL或手改原RECORD。
4. 新独立运行环境仅从hash锁定候选wheel安装，pipcheck/RECORD验证/PE与实际加载路径验证；uv_version API、纯转换边界、Torch tensor、固定BGE encode/归一化、实际文档入库→授权查询→CAS更新→删除→新进程恢复全链，完整第一方双覆盖率与适用安全扫描都重新执行。由于native发生变更，现R11不是候选验收证明。
5. 独立评审候选ABI/封装/测试和供应链记录后，才能决定正式依赖引用；保持现有默认GPU/CPU选择与生产准入不变，回滚引用已知原wheel+锁，不共享可写原运行库。

## 决策、权限与风险

私有候选设计和能力验证属于已授权安全整改准备，无需本轮再问产品问题。若需要引入内部重封装Torch作为正式长期维护依赖，要在候选证据具体可审阅后明确维护责任/更新渠道及支持平台；这比一次DLL替换增加供应链维护成本。机器级工具安装、外部wheel托管/发布或部署需要对应授权；本轮均未执行。无权凭“1.x ABI稳定”直接承诺兼容，更不能扩大为全部native重编。

可行性当前标记：**方案可准备，构建工具/完整已验证源缺失，构建与ABI/全链未验证**。若选用具备工具的独立builder可消除此本机能力阻塞，不能省略新wheel身份和完整验收。

## 备选：固定Linux builder交叉编译（仅评估、未执行）

可以作为**可逆隔离MVP的备选能力路线**，无需先全局安装VisualStudio。上述官方README明确列出CMake Windows cross-compile示例，同时标注unsupported but generally works；因此不是官方保证与MSVC等价。可沿既有固定Linuxbuilder，为该独立候选引入经官方签名Debian仓库/快照验证的MinGW-w64 x86_64工具包，固定每个deb SHA/版本/源与编译flags，再交叉编译核定修补libuv源。此轮没有列取/下载/安装APT包、编译或改镜像。

MVP必须先解决的差异：x64 PE架构、C导出名称/调用约定、默认CRT(UCRT/MSVCRT)、线程与结构布局/对齐、异常/运行库兼容、导出ordinal/forwarder及额外依赖。尤其不得默默引入libgcc_s_seh-1.dll/libwinpthread-1.dll等新未锁依赖；可评估静态链接相关编译器runtime，但也需许可证/漏洞及线程行为验证，不能只靠链接flags宣称无风险。原uv.dll依赖VCRUNTIME140/UCRT，MinGW产物可能不同，必须实测PE依赖和加载链。

候选首阶段只在新Windows子进程加载/版本/288原exports与25直接imports/结构与回调线程专项/纯转换检查，再实际Torch Tensor及固定BGE；再扩展全链和双覆盖率。单独DLL加载成功或25名称存在都不足以认定ABI等价。由独立评审核对这条跨编译路线后再推进真实验证。

封装可选新的内部wheel，或**明确项目派生runtime**：后者必须以独立artifact manifest记录原官方wheel与所有保留文件hash、派生DLL源/工具链/完整patch-map、实际安装文件SHA及新的runtime身份；不可继续宣称未修改的原锁wheel/RECORD完整通过。原RECORD与改动不一致必须在派生身份验证中明确处理，不能手改报告掩盖。若后续需要标准pip分发/可复现安装，完整新wheel身份更合适。两者都不允许覆盖当前R11，也不自动构成部署或外部发布授权。

**产品选择判断**：继续独立交叉编译能力MVP属于已有安全整改范围内可逆准备，可先形成具体证据，不必先让用户在“装全局VS”和“交叉编译”间做抽象决定。全局工具安装需要机器修改授权；采用长期内部派生产物作为正式依赖/支持策略，应在候选通过独立设计/ABI与真实链验证后呈现具体取舍。当前不把工具缺失夸大成整个整改必须停工，也不把MinGW路线描述为已验证可行。
