# 精确官方构建来源映射（有界补充）

仅追加新目录，原REPORT.md及运行库未变。

取得以下精确、非浮动官方来源链：

- 实际torch git08187d9e0fba026dc8217405802ab5381dc88d90的`cmake/Dependencies.cmake`1222起：当USE_DISTRIBUTED且USE_TENSORPIPE开启、非MSVC时，强制TP_BUILD_LIBUV=ON，include第三方TensorPipe/libuv并静态构建TensorPipe。此为条件构建路线，不等于最终wheel构建证明。
- 同commit官方GitHub contents API给出TensorPipe gitlink **2b4cd91092d335a697416b2a3cb398283246849d**，已保存second-0.txt。
- 该TensorPipe精确commit官方third_party目录HTML包含libuv submodule链接 **5152db2cbfeb5582e9c27c5ea1dba2cd9e10759b**；保存完整页面及匹配文本fetch-final.json，非从branch=v1.x推算。
- 该libuv精确commit官方`include/uv/version.h`声明 **1.51.0**，已高于本公告1.48.0修补版本。
- 同commit官方`src/idna.c:318`签名`ssize_t uv__idna_toascii(const char* s, const char* se, char* d, char* de)`；362起明确d>=de返回UV_EINVAL，否则写终止null。保存源文件/SHA。

**可降低的未知**：Linux这条精确官方源码pin是libuv1.51.0，不能沿用Windows DLL1.40.0断言Linux也命中相同公告版本范围。**仍未关闭的未知**：没有最终官方wheel构建attestation/SBOM将实物SHA a09987...直接映射到这条子模块/开关/编译产物；动态符号探针只证存在符号。所以只能记“精确官方源码路线已修补，wheel载荷映射待验证”，不能宣布Linux整套native清零。Windows实物1.40.0结论不变，MSVC根本不走这条TensorPipe构建路线。

有界下载约少量100KB级文本，全部timeout10–12秒，未下载源码archive/大wheel；包含404（猜测路径/跨子模块raw不可直接访问）、sandbox socket10013、API403限流原始失败。限流后从精确官方目录页定位gitlink，不请求浮动main。fetch*.json保存成功文件字节数/SHA及失败，日志不含凭据。

## 下一步是否值得执行纯转换测试

值得，且可独立验证精确公告修补行为，但必须单独授权任务/代码审查后执行。官方签名现已取得，建议在隔离child中只调用`uv__idna_toascii`，以已分配buffer首/尾地址传指针，d末端设为恰好256字节，检查长度255/256/257及带suffix的ASCII hostname是否拒绝溢出并保留边界canary；无DNS调用、network-none、进程timeout及崩溃捕获。对比官方旧/新转换实现预期，只有已验证正确ABI和边界的结果可用于公告专项佐证。它不替代wheel来源映射、完整SSRF链或其他CVE/native组件审计。本轮**未执行此C ABI调用**。

主源URL均在fetch收据：pytorch精确commit raw/API、tensorpipe精确commit官方目录HTML、libuv精确commit raw。不引用浮动main或第三方博客。
