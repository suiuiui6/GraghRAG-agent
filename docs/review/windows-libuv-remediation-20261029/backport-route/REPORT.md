# 保留 libuv 1.40 Windows ABI 的安全回补路线（只读评估）

日期：2026-10-29。结论：**有条件可行的候选设计，尚未实现或验证，不准替换现役 DLL。** 精确旧 ABI 上仅改内部 IDNA 函数有希望避开 1.53 的 loop 布局冲突；仅回补 CVE-2024-24806 三提交不足以宣称“安全版 1.40”。

## 事实及绑定基线

复读 ../.. 的 windows-uv-loop-layout-debug-20261029/torch-header-mapping/REPORT.md、包 meta、头文件及收据：旧包 libuv 1.40.0/h8ffe710_0，归档 SHA256 e22158feea790e9c4e9f14a3dd85d9fdba8dcdc9b4a7b998e6adadfe8dee3865；旧 DLL fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8。同包 uv.h / uv/win.h 匹配官方 v1.40.0；recipe 源为 v1.40.0、SHA256 70fe1c9ba4f2c509e8166c0ca2351000237da573bb6c82092339207a9715ba6b，并声明 MSVC 安装目录补丁 0001-Use-Unix-install-logic-for-MSVC.patch。该补丁原文未在本轮获取，不可假定已复现整个包配方。

Torch 2.14.0+cpu 的精确源码 commit 08187d9e0fba026dc8217405802ab5381dc88d90 在 TCPStore 内按值嵌入 uv_loop_t。父证据映射旧 loop 464 字节、新 1.53 loop 472；改 DLL 工具链或版本号不能使旧对象多出 8 字节。证据不包含此 wheel 的完整编译输入证明/PDB，仍须保留该限制。

## 完整官方三提交与旧源码核对

完整 .diff 已逐一读取，文件字节/hash/URL/UTC 见 sources-success.json；原 socket 权限失败保留 sources.json。三份 diff 共2054字节，不是只读提交标题。

| 提交 | 完整改动范围 | 对旧源适配判断 |
| --- | --- | --- |
| 0f2d7e7 | src/idna.c +3/-2；test/test-idna.c +4 | 将尾部条件写 NUL 改为容量耗尽返回 UV_EINVAL，否则写 NUL；测试增加1字节输出不足场景 |
| 3530bcc | src/idna.c +3；test/test-idna.c +1 | 输入 s==se 返回 UV_EINVAL；新增零长度输入断言 |
| e0327e1 | test/test-idna.c +1/-1 | 将空字符串由转换成功改为 UV_EINVAL 期望 |

三者均不修改 include/ 公开头、导出声明、结构体、字段数量或布局；生产改动只在已有内部函数体内，无新库/新OS API/新公开符号依赖。**这是源码事实，未证明构建后ABI一致。**

v1.40.0/src/idna.c:250 的函数返回 long，上游2024上下文为 ssize_t；旧循环及位置也不同，不应机械 cherry-pick/复制整个新版文件。保留旧内部声明及long返回类型，按语义引入两项保护、适配旧测试辅助宏，是可评审的最小方案推断。旧函数尾部确实是可选写 NUL，缓冲耗尽仍返回长度。Windows v1.40 getaddrinfo.c:263 使用256字节 hostname_ascii，283-288调用转换并对负返回值立即返回，随后289起才使用 MultiByteToWideChar(...,-1,...)。故修补负返回可阻止未终止缓冲进入Windows宽字符转换；无需为该修补修改公开 getaddrinfo 契约或loop布局。这是控制流推断，尚未运行。

注意新空字符串拒绝改变既有行为；node==NULL且service非NULL走另一分支，应保留。不能把失败输出缓冲当作有效字符串使用；即便函数可能写入部分内容，调用者仍必须遵守负返回。

## 安全覆盖与维护责任

官方 GHSA-f74f-cvh7-c6q6/CVE-2024-24806 声明影响 >=1.24.0，修于1.48.0：https://github.com/libuv/libuv/security/advisories/GHSA-f74f-cvh7-c6q6 。本轮官方仓库 advisory API 只返回该项；这不是历史漏洞全集。官方 SECURITY.md 仅支持最新1.x；自维护1.40不是官方支持分支，后续公告监测和回补责任在派生构建维护方。

另一个明确必须核对的IDNA问题：Node官方 https://nodejs.org/en/blog/vulnerability/july-2021-security-releases 记载 CVE-2021-22918 为 libuv IDNA 越界读。旧1.40源码foreach_codepoint宏在*p<=pe条件下调用解码器；官方1.42源码移除宏并使用不同遍历和assert(*p<pe)。2024两项生产保护没有修改该宏/解码路径，不能证明已覆盖2021问题。**因此仅三提交的安全充分性不成立；必须先识别2021上游修复的精确提交及最小依赖，再独立评审与回归。** 本轮未下载该精确修复提交、未证明旧DLL是否另有二进制补丁，不将源码差异等同已执行漏洞复现。

官方 https://github.com/libuv/libuv/issues/4416 讨论 CVE-2024-22017 的 Linux io_uring/setuid 问题；对当前Windows构建推断无对应执行路径，可列平台不适用候选，仍需随SBOM记录平台依据。不能因此扩大成1.40全域无漏洞。公告检索有界，不构造完整CVE零风险声明。

## 最小隔离 MVP 与出口（以下全为待做）

1. 冻结精确旧源、同包公开头、包配方补丁、构建脚本及补丁集hash；先补齐2021依赖审查，不搬入新版win.h。独立评审确认没有额外结构布局/公开ABI改动。
2. 锁定x64 MSVC、SDK/UCRT、编译/链接flags、/MD或/MT和DLL导出机制。包meta声明VS2017 19.16.27038/VC14.1、vs2015_runtime14.16.27012；本机据父Agent盘点存在MSVC14.50.35717及SDK10.0.26100.0，不在PATH不代表缺工具。可在私有命令环境初始化，不需安装，但新旧编译器兼容、CRT依赖、运行时分配/释放边界尚未证明；优先MSVC路线不自动等于可替换。
3. 只在独立目录构建；比较原/候选PE machine、导出名称/序号/调用约定、导入依赖、CRT与所有Torch消费的结构sizeof/alignof/offsetof。464字节loop及所有字段偏移、handle/req布局须精确一致，不能仅检查uv_loop_size。
4. 官方旧基线测试＋三提交测试适配；增加IDNA输出容量0/1、恰好容纳NUL/差1、ASCII/Unicode及Punycode、空输入、非法UTF8、截断多字节输入、分隔符/末尾点、2021越界读专用测试。可用guard page/工具支持的内存检查验证边界，不以“不崩溃”作为唯一断言。
5. Windows uv_getaddrinfo同步/异步分别验证合法域名、IPv4/IPv6、空node与service、空字符串拒绝、过长/恶意形态返回错误且不解析到非预期地址；确认失败路径回调/请求生命周期、取消/清理及无资源泄漏。明确旧基线与修补后预期差异。
6. 经前述门槛后，在隔离子进程和候选DLL目录中验证精确Torch consumer：实际TCPStore server/client、set/get/wait/multiGet、关闭与重复创建、多客户端及超时异常；从已验证路径加载并记录候选hash。测试不触碰现役环境。全部通过仍仅支持已定义场景，不足以宣称所有libuv消费者兼容。

## 版本扫描、SBOM、VEX

保留真实1.40基线身份，不伪造1.48/1.53版本。普通版本匹配扫描继续报告CVE-2024-24806是预期情况；不能删除告警证明修好。SBOM同时记录上游1.40 purl/源hash、派生包唯一build/revision、全部补丁commit+内容hash、编译器/SDK/CRT、构建flags、最终DLLhash和许可证。明确派生名称与upstream版本区别。

VEX必须绑定派生构建及精确DLLhash和单独漏洞：当前仅能under_investigation；评审和回归完成后，按所用VEX规范表示修复状态并附回补/测试证据，不能对原始旧DLL标fixed。其他CVE分别平台/可达性评估；未知项不能继承fixed。版本扫描例外应有证据链接、范围、所有者、失效/复核条件，不做全包永久忽略。

## 本轮执行与限制

仅下载官方小文件并写本报告/收据；没有编译、应用补丁、修改C代码、安装依赖、加载DLL或运行Torch。已读取完整三diff、两个1.40源、1.42对照及安全政策；没有实现测试结果、构建结果或已替换声明。初次直接网络因WinError10013失败，随后经工具批准的bounded下载成功。一个误调用不存在fetch.py退出1，无文件执行；一次未核实完整commit URL打开失败未作为证据。后续最小决策是是否授权隔离MVP；实施前仍须补齐2021精确补丁依赖及构建配方来源。
