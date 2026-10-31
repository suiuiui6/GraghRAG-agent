# Torch native/libuv 独立边界审查 — 2026-10-29

结论：**Windows uv.dll 命中公告版本范围且未取得回补证据，维持 open；Linux CPU wheel 虽没有单独 libuv.so，实际动态符号查找可找到 uv_getaddrinfo 和 uv__idna_toascii，不能据此清除风险，版本/回补仍待验证。** 未证明项目存在可利用 SSRF，也未证明完整 native 安全通过。无生产源码、依赖、冻结运行库或镜像变更。

## 主源与触发条件

[libuv 官方公告 GHSA-f74f-cvh7-c6q6 / CVE-2024-24806](https://github.com/libuv/libuv/security/advisories/GHSA-f74f-cvh7-c6q6)：受影响从1.24.0开始，1.48.0修补；Unix及Windows的 uv_getaddrinfo 在 hostname 转换处理中可能截断超长名称。需要不可信hostname进入该原生接口，并结合地址访问/过滤逻辑才构成公告描述的攻击链。DLL存在、符号存在、普通文本推理成功分别不能证明该攻击链。此次先访问 github.com/advisories/GHSA-f74f-cvh7-c6q6 得404，随后定位上述正确维护者公告；404不是公告不存在。

旧静态报告 D:/graghRAG-agent/.tmp/torch-libuv-reachability-20261028/report.md 的121个非tests Python文件检索阴性和固定Bert单设备调用链仍只支持其明确范围。用户文本传tokenize/forward不等同于传hostname；未发现显式分布式入口不能替代native闭包证明。

## Windows 实物

只读重hash当前R11环境 `.tmp/backend-runtime-20261029/.venv/Lib/site-packages/torch/lib/uv.dll`：SHA256 fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8，与旧独立version API收据 `.tmp/native-advisory-triage-20261027/native-version-api.json` 完全相同；该实物 uv_version_string 为1.40.0。此次不重新import冻结环境。未取得供应商回补/编译源映射；版本范围命中不能标已修复或非受影响。

## Linux 实物及新证据

固定镜像 sha256:f4e637023bdc366728472bcaa271002d2d69ad6065c6bd6e7b706ed9c4d1df83，Torch2.14.0+cpu / commit08187d9e0fba026dc8217405802ab5381dc88d90。只读新容器probe实际exit0；容器NetworkMode=none、只读根、uid65534、2CPU/2GiB/PIDs64、drop ALL/no-new-privileges，仅脚本RO挂载。保留原sandbox Docker pipe permission denied退出1，正常审批后同命令成功，不绕过权限。此探针没有调用DNS解析函数或运行攻击输入。

`probe_linux.py` 对libtorch_cpu.so/libtorch_python.so句柄使用ctypes动态符号查找：uv_getaddrinfo、uv__idna_toascii可解析，uv_version/uv_version_string不可解析；libc10.so四符号均不可解析。注意 dlsym 可搜索依赖，因此这只证明相关已装载链接闭包内存在符号，不能单凭此确定符号定义在哪个ELF、实际libuv版本或是否回补。没有单独libuv.so不足以清除内嵌组件。

`linux-probe-r1.json` 保存11个Torch native文件实际大小/SHA、torch.__config__.show及/proc/self/maps映射。其配置证实CPU CUDA=0、GLOO=ON/MPI=OFF/NCCL=OFF，并列MKL/MKLDNN等其他原生组件；本轮不是这些组件全部CVE审计。完整CPU模型probe已有158包和真实512维输出，本轮未重复跑模型或HTTP验收。

## 可落实的最小后续路线

1. 首选取得**固定官方wheel对应构建源/SBOM及libuv回补证明**，能把当前DLL/ELF SHA映射到修补提交，并针对hostname长度拒绝/转换边界做隔离回归。仅提高Python torch版本号、pip-audit无告警或设置USE_LIBUV=0均不足以清除已携带组件问题。
2. 无回补证据时，准备独立候选：供应商正式修补wheel，或从锁定源构建Torch并将libuv固定到已审定修补版本/修补提交，保存编译选项、链接依赖、产物SHA及RECORD/SBOM，真实固定BGE模型/SQLite生命周期/重启恢复/完整双覆盖率重新验收。自编Torch成本显著，应先小型构建能力MVP，不能直接替换当前R11实物。
3. 不原地单换uv.dll：需要先验证ABI、Torch导入及所有链接消费者；裸DLL替换还会破坏已锁wheel与RECORD身份。不能通过删除DLL、关闭分布式入口、network-none测试条件来宣称生产载荷已修补。
4. 应用当前本地离线推理限制可作为**明确范围的暴露面证据**，不能自动当作风险接受或“非受影响”。若正式产品只保留此路径，应独立设计并审定运行边界，再用动态调用/链接来源与输入数据流证据验证；此次不擅自改变需求或默认部署。

因此此轮可以关闭“Linux只是没有单独libuv.so所以安全”的错误假设，不能关闭CVE或全部native验收。生产准入维持原状态；提交报告时必须如实列为open/待验证，交由既有验收规则处理。本报告无用户额外风险接受请求。

## 原始证据

本目录windows-uv-current-hash.json、probe_linux.py、linux-probe-r1.json/.stderr/.exit、container-inspect.json；旧linux-probe.stderr/.exit保留失败。旧两份native/security审计按只读查看，Rust和Python包扫描不能覆盖此libuv问题。
