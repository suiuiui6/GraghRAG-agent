# Windows 旧 ABI 回补与生产消费者验证 — 2026-11-04

结论：Route A（保留 libuv 1.40.0 ABI，回补官方 IDNA 修复）已从方案评估推进到**私有候选可行**。候选通过补丁前 RED、补丁后 libuv 动态/静态全套测试、旧 Torch DLL 的导出/布局/依赖比较、Torch 加载与张量/BGE 使用，以及 GraphRAG 固定模型 HTTP 生命周期链。候选仍只位于忽略的私有目录，尚未装入正式运行库；生产 `compatibility_not_approved` 继续保持。

## 输入与补丁

- 基线：libuv v1.40.0，commit `4e69e333252693bd82d6338d6124f0416538dbfc`。
- 按原顺序无提交应用四个官方上游提交：`b7466e31…`、`0f2d7e78…`、`3530bcc3…`、`e0327e1d…`。
- 仅变更 `src/idna.c`、`test/test-idna.c`、`test/test-list.h`，69 insertions / 16 deletions；`git diff --cached --check` 退出 0。
- 冻结补丁为 `libuv-candidate.patch`，SHA-256 `a20128ca27cf079ae3ed8d449a4daecaed45b14f41a142a09592eada918444e1`。没有公共头、ABI 结构、CMake 或 Makefile 变化。

## RED / GREEN

补丁前的 test-only 构建重放两个回归用例，均按预期非零退出：

- `utf8_decode1_overrun`：exit `-1073740791`；旧实现把单字节输入指针推进到缓冲区之外。
- `idna_toascii`：exit `-1073740791`；旧实现接受空输入，违反回补后的 `UV_EINVAL` 合同。

补丁后 MSVC/NMake 候选：

- 动态 `uv_run_tests.exe`：402/402，exit 0，日志 SHA-256 `75b42c50…59a8`。
- 静态 `uv_run_tests_a.exe`：405/405，exit 0，日志 SHA-256 `486afe4c…c2ef`。
- 工具链：MSVC 19.50.35728 / VC Tools 14.50.35717 / CMake 4.2.3 / NMake。

## ABI、PE 与 Torch 消费者

候选 `uv.dll` SHA-256 为 `174a9af583dd7f8317e3e17c440b4b09e820cb8f5e21719fe05ad90d3a9f3a0c`；原 Torch 捆绑 DLL 为 `fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8`。

- 基线、候选和原 Torch DLL 都报告 libuv 1.40.0、`uv_loop_size=464`。
- 16 类 handle 与 10 类 request 的全部尺寸相等。
- 三者均为 x64，288 个导出名称及 ordinal/name 对完全一致；依赖 DLL 集合一致。
- `torch_cpu.dll` 静态导入 25 个 `uv_*` 符号；导入 Torch 后实际加载的是私有候选 DLL。
- Torch 2.14.0+cpu 张量乘法通过；固定 11 文件 BGE 模型执行并由最终 HTTP 链再次使用。

`TCPStore(use_libuv=True)` 在原始和候选 Torch 上都返回相同 `DistStoreError`：当前 wheel 构建时未启用 libuv TCPStore。它不是本次回补造成的回归，也不能作为实际 libuv TCPStore 执行证据。项目生产链验证覆盖实际 GraphRAG 消费者及候选 DLL 加载，不能外推为 25 个导入函数全部动态路径均已执行。

## 最终 Windows 运行库与生命周期链

重新取得收据锁定的官方 CPython 3.12.16 Windows 产物，压缩包 SHA-256 `1f2ab53880fc67ea323398c6388e05af28addc99a8e389209f08a51fdff4b149`。安全解包 3348 个普通文件，复制清单一致；派生副本仅替换 `python/DLLs/sqlite3.dll`，其 SHA-256 为 `5ca6a16bdd2c5a5037b1e3a942d9ac1c66efe2def902b202d44774680a8a4656`。

实际运行身份：CPython 3.12.16、SQLite 3.54.0、Expat 2.9.0、OpenSSL 3.5.9、Torch 2.14.0+cpu、候选 libuv 1.40.0。SQLite 三个硬化状态为 defensive=true、trusted_schema=false、load_extension=false。

最终执行 `tests/test_vector_http_lifecycle.py::test_fixed_local_model_http_upload_update_delete_restart`：1 passed、0 failure/error/skip、113.191 秒、exit 0。用例包含上传 v1、查询 v1、更新 v2、仅见 v2、新进程重启仍见 v2、删除、第二个新进程返回 404。模型离线且逐文件哈希绑定，未下载替代模型。

两项环境失败如实保留：系统 Python 的 SQLite 3.45.3 被运行库门槛拒绝；恢复工作树长路径触发 WinError 206。最终命令未降低门槛或改变用例，只将 pytest/TEMP 放到短的私有临时目录。

## 未关闭项

1. 将补丁、基线/上游提交、工具链、构建和安装/回滚校验转成仓库内可重复执行的正式运行库配方；正式产物不得依赖本轮 `.tmp`。
2. 对项目自有构建/安装代码做独立复核；候选进入正式 runtime 后重新执行最终完整 backend 测试、固定全量行/分支双 90、锁检查及既定扫描。
3. 当前 Torch wheel 没有可执行的 libuv TCPStore 路径。若未来生产配置要求该能力，必须重建 Torch 消费者；本次结果不授权该能力。
4. 未提交、未推送、未部署、未迁移现有数据；候选二进制不进入 Git。

机器收据见 `receipt.json`；原始 RED/GREEN、最终 JUnit、失败 JUnit 和冻结补丁与本报告同目录。

## 2026-11-05 配方复核接续

仓库新增的 `backend/native/torch_libuv/manifest.json` 与 `build.py` 将上述输入转为项目自有、网络禁用的执行边界：`build` 只接受精确且干净的基线 checkout，复制到新 staging 后应用冻结 patch，使用锁定 CMake/NMake 配置和 `FETCHCONTENT_FULLY_DISCONNECTED=ON` 构建；`verify-existing` 生成未批准收据，`install` 做完整身份绑定，`rollback` 仅移除精确匹配目录，`_abi` 提供 PE 检查所需的子进程入口。

新增并执行：

```text
python -m pytest backend/tests/test_torch_libuv_build_policy.py -q --tb=short -p no:cacheprovider
```

结果：27 passed，0 failed，0 error，0 skipped，exit 0。该命令包含 manifest、源码门禁、CMake/MSVC/NMake 版本门禁、离线构建命令、recipe command provenance、收据漂移、安装和回滚行为。出现的既有 `RequestsDependencyWarning` 与 pytest `timeout` 配置警告已记录，未吞掉失败。

本轮没有可供执行的 libuv 源 checkout，因此没有伪造 `build`/`verify-existing` 的实际构建结果；正式源构建、独立代码复核、候选替换后的完整 backend 双 90 与安全扫描仍是开放门槛。候选二进制和工具链临时目录仍不进入 Git，生产 `compatibility_not_approved` 不变。
## 2026-11-06 更正

后续精确 checkout 的最终私有 build/verify-existing 已完成：动态 402 枚举中 394 执行通过、8 条件性 Windows skip；静态 405 枚举中 397 执行通过、8 条件性 Windows skip。独立 reviewer 复核候选 SHA 7c6aa0dea69979c9e62af531d22094262dbbee5c9d47db967d2d95bc2b79a0de、288 exports、16 handle、10 request 和 loop 464。私有 install、错误回滚和匹配回滚演示完成，正式 runtime 未改。

patched full-r3 backend 仍失败：2271 项为 2253 passed、6 failed、12 errors、0 skipped；行 16886/18166、分支 5561/6220，分支未达 90%。失败涉及历史冻结 registration/snapshot 缺失、Rust stable MSVC manifest 缺失及 Windows socket 资源耗尽。

