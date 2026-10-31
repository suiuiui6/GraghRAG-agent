# 实际 Linux CPU wheel 纯转换边界专项 — 2026-10-29

结论：固定实际Linux CPU wheel内可解析的`uv__idna_toascii`，**18/18输入满足预先写入探针的官方修补语义，所有边界canary保持不变**。这直接补齐“实际wheel是否仍对256字节缓冲区成功返回被截断超长hostname”的专项未知：本组输入未重现该错误，实际返回拒绝。不是完整SSRF利用链、所有IDNA输入、全部native/CVE清零或官方wheel attestation。

## 静态 ABI 与 oracle

依据上一目录保存的官方精确libuv5152db2... `src/idna.c:318`：`ssize_t uv__idna_toascii(const char* s,const char* se,char* d,char* de)`，se/de均为exclusive end，成功返回包含结尾null的写入字节数；输入为空、UTF8非法或剩余输出空间无法容纳终止null时负值。源码允许失败前修改输出区，因此只要求**输出区外canary不变**，没有错误要求失败区完全不变。

ctypes静态声明restype=c_ssize_t、argtypes四个c_void_p；运行时断言signed ssize_t/void pointer均8字节。使用已分配source/destination的真实整数地址传首尾，不使用会自动转换/拷贝的c_char_p。输入<=512字节、output cap<=256、左右各32字节0xA5 canary。未调用uv_getaddrinfo或任何DNS函数。

预期在调用被测函数之前由probe.py计算：ASCII保持原字节；三个官方识别的Unicode句号映射ASCII点；“例子”用Python独立RFC3492 punycode codec产生xn--标签oracle。该codec不是被测函数。能容纳expected+null则要求准确return和完整expected/null字节相等；否则要求负值。所有输入/约束先构造case，再调用函数，无按实际结果修改oracle。

## 实际结果

- ASCII输出长度1/254/255成功返回2/255/256；256/257/512拒绝-22。
- 公告相关0x数字hostname加suffix共268字节：拒绝-22，而非成功返回截断前缀。未做DNS解析或地址访问。
- 实际多字节UTF8“例子”IDNA输出边界254/255成功，256/257拒绝-22。
- 三种句号U+3002/U+FF0E/U+FF61转换准确。
- 非法UTF8、空输入拒绝；cap2字节下1字节ASCII成功、2字节ASCII拒绝。
- 18次调用所有canary完整，正确成功结果有null。无异常、崩溃、OOM或timeout。

固定镜像sha256:f4e637023bdc366728472bcaa271002d2d69ad6065c6bd6e7b706ed9c4d1df83，torch2.14.0+cpu；实物ELF SHA保存stdout.json。动态查找可能搜索链接依赖，本轮不据句柄名称伪造符号定义归属。

30秒父进程超时，实际3.168秒退出0；docker inspect确认container退出0、network=none、只读root、uid65534、2CPU/2GiB/PIDs64、drop ALL/no-new-privileges，仅probe.py只读挂载。无可写生产挂载、无C源码/runtime/RECORD改变，无WindowsR11环境import。只运行Linux；未假称Windows旧baseline执行过。

## 已闭合及剩余

已闭合：已确认ABI后，实际Linux载荷的本组精确长度/UTF8/IDNA边界行为与官方修补逻辑一致；不再只能凭源码pin猜测该转换边界。

剩余：Windows1.40.0实物专项/回补仍open；Linux缺官方wheel完整源/构建attestation，`uv_getaddrinfo`及所有消费者完整数据流未测；其他原生组件/CVE不在本专项范围。可以将Linux此CVE备注升级为“已取得精确源码pin及实物修补行为佐证；完整产物映射/整体安全仍待验证”，不能改为所有native完成。

证据：probe.py、run.py、command.json（timeout/exit/时间/argv）、stdout.json（18个原始结果）、stderr.log、inspect.json。未重新下载大产物、未改原已hash报告。
