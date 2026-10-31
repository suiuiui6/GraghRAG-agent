# 独立静态产物评审（2026-10-29）

结论：**B 构建静态产物门条件通过，可准备有界私有 Windows 子进程 API smoke；正式 ABI/运行库替换门仍阻断。** 本结论不批准正式采纳、部署或长期维护。读取并适配 requesting-code-review 技能；本评审独立上下文，仅写本目录，未加载 DLL、运行 Windows EXE、构建、下载或修改 runtime/default/gate/C/R11。

`python .tmp/windows-libuv-artifact-static-review-20261029/review.py` 实际 exit0。独立原始字节 PE32+ 解析器覆盖 section/RVA、具名和无名 export ordinal、forwarder、普通 import thunk ordinal/name 与 delay descriptor；不是复用作者 PE JSON 作结论。B manifest **82 文件**逐 size/SHA 全匹配（不是委派中的约32）；B REPORT SHA46ad3a9ac9aed66f15b52ec121acb4052e4b9ae8d854b9504a18182fb9d8f9df。候选 SHA6f91cea90646d077b1bcb6372433ea048bac344e8eeb5e5c8ee4b163f02edf96、原 uv fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8、torch_cpu 0803ea116cd3e833b1b17515663734cbf7a78071ccd03dbcfa22d99517e1a134 的读前后 hash 相同，详 receipt.json。

五个 PE 均 AMD64。候选319具名导出完整覆盖原288以及 Torch25，新增31；285旧具名入口 ordinal 改变。全部五文件无 forwarder、delay descriptor；Torch uv.dll 的25导入全部 by name、0 ordinal，因此这25直接入口不存在 ordinal 变化造成的绑定失败，但不能推及其他消费者或 ABI。shared test 实际依赖 libuv.dll；static test 无该导入；两者仅构建，未运行，不是功能通过。候选名 libuv.dll 与 Torch uv.dll 不同，后续只能在新私有候选映射名称并核实际加载路径，禁止原位替换。

候选实际依赖 ADVAPI32/dbghelp/IPHLPAPI/KERNEL32/msvcrt/ole32/SHELL32/api-ms-win-core-synch-l1-2-0/USER32/USERENV/WS2_32；无 libgcc/libwinpthread 或未知旁载 DLL。系统名字不是所有 Windows 版本可用证明，动态阶段仍须核实际依赖路径。gcc-specs 实有 -lmingwex -lmsvcrt；实际链接记录有 -static-libgcc。原DLL导入 UCRT api-ms-win-crt-*（heap/runtime/stdio等），候选导入 msvcrt.dll，两者**不是 CRT 等价**。

CRT 风险应按 Torch25具体入口控制：该集合以 loop/TCP/timer/async、read/write、地址和错误字符串为主，没有 uv_fs/uv_pipe_open/uv_open_osfhandle 这类 CRT FD 入口，故 FD 表混用不是这25符号本身的已证失败；不得据此宣称全部 libuv 安全。uv_interface_addresses 与 uv_free_interface_addresses 必须同一 DLL 配对；uv_strerror 返回借用指针不得由消费者 free。uv_buf_init 按值返回 uv_buf_t，uv_read_start/uv_write 穿越 buffer/callback/req/handle 结构边界；即使 malloc/free 不跨 DLL，布局/对齐/成员偏移和回调生命周期仍可破坏内存。候选源码 uv/win.h uv_buf_t 使用 Windows WSABUF 排列，uv_file 是 int；thread.c 使用 _beginthreadex，候选连接 msvcrt，不能把线程CRT状态视为UCRT共享。回调内 Torch 的异常/线程状态和关闭后访问需要真实消费者检验。

源与27 deb签名链引用阶段A独立实际审，不重复无关 Linux/Rust 全审。B 82文件hash核验绑定实际 argv、image-binding、27 versions、source before/after。记录 image24.54s/compile96.89s exit0、base cd48...→derived25bfa...，CPU2/mem2G/nonroot1000/RO/networknone 是现有真实执行证据，本次未重跑 build；原 auto-review 拒绝保留不冒称不存在。工具许可/漏洞全审未完成，不称零漏洞。

## 阶段 C 必要检查及最小顺序

1. 先在新私有子进程以绝对路径加载单个候选、受控 DLL 搜索目录，核模块真实路径/SHA、uv_version=1.53.0、依赖加载来源。与原 public size baseline loop464/tcp320/timer160/async224/connect128/write176 比对；不匹配先停 Torch 载入。尺寸相同也不等于全 ABI。
2. 尚缺原 Torch 编译所用 libuv 头文件/构建映射，需还原 uv_loop_t/uv_tcp_t/uv_timer_t/uv_async_t/uv_connect_t/uv_write_t/uv_buf_t 的 sizeof、align、关键 offset、调用与回调签名；候选头自洽不能替代原 MSVC 消费者映射。可先做单DLL API smoke，但不能据此关闭正式ABI门。
3. bounded smoke：loop init/run/close、timer触发与取消、跨线程 async及线程join、TCP本机listen/connect/accept→write/read→EOF、错误/超时、close回调后释放、反复启动停止及新进程退出。用候选公开 size 分配时保留对齐；明确 callback 所有权、buffer lifespan、接口地址成对释放，不跨CRT free 或传递 FILE*/CRT FD。
4. 再跑同批候选 shared/static 上游适用 Windows 测试，逐项记录失败/跳过；shared实际模块须是本候选。然后新私有 Torch 载体显式 libuv TCPStore 后端，证实实际模块路径及使用路径，执行连接/set/get、wait/timeout、关闭/重连/多次新进程。Tensor/BGE单独成功不能替代 TCPStore。
5. 进入派生runtime门仍需新身份/完整文件hash/patch map/RECORD失配说明与既定真实全链验收、安全审计及最终快照全量双90。静态审不授予Git提交或正式runtime采纳；生产compatibility gate保持关闭。

局限：未执行动态/上游/Torch/项目测试、覆盖率或完整安全许可审。未提交/推送/发布/部署。读memory/index与现有设计/输入审；根master为dirty，未清理其他修改；根memory/2026-10-29.md不存在，本目录即本次交接记录，不越过文件所有权写公共memory。辅助读命令有两次路径不存在（compiler-specs应为gcc-specs、根当日memory缺失），不影响实际exit0独立核验。
