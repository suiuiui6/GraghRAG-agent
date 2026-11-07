# 完整后端最终验收 — R13（2026-11-07）

## 结论

在修复冻结测试夹具和 Rust stable MSVC 工具链后，固定 Windows Python 范围的实际完整后端门槛通过：

- 执行：2290 项；2290 passed、0 failed、0 errors、0 skipped。
- 原 R12 的 2223 个 node identity 全部保留；新增 67 项（构建脚本 19 项错误路径及既有专项）。
- 生产 Python 范围：121/121 文件，missing=[]、extra=[]。
- 行：16973/18166 = 93.43278652427612%，原始整数门槛通过。
- 分支：5599/6220 = 90.016077170418%，原始整数门槛通过。
- `backend/tests/test_torch_libuv_build_policy.py` 67 项通过；build.py 单独覆盖 304/318 行、93/106 分支。
- 输入及已存在运行库文件前后稳定；运行库漂移列表为空（74,897 个文件路径记录）。

这是 `audit-only-windows` 的完整 Python 测试/覆盖率证据。simple-output 原始 registration 已从历史生成链恢复，字节 SHA 精确匹配 receipt，full-r5 使用该原件，故本报告可作为 Python 提交门槛证据；仍不构成 Linux/原生安全或生产准入证明。

## 实际命令范围

测试入口：

```text
backend/tests
backend/research/test_deepseek_scope_pilot.py
```

覆盖率配置：

```text
docs/testing/coverage-backend-2026-10-12.ini
```

执行器为隔离的 CPython 3.12.16 私有运行库，含已验证的 libuv 候选、coverage 7.6.12、pyasn1 0.6.5。`GRAPHRAG_FROZEN_TEST_ROOT=D:\graghRAG-agent`，模型离线固定 receipt。实际 argv、退出码和耗时见 `commands.json`。

## 冻结夹具修复

- `public-dev-budget-20261015-r2/snapshot.json` 恢复为原始 SHA `f3f59076a62d11afa5acdb78335bc09a89341499d3c572107b3e1694a288446e`；145 个源文件逐一核验。
- `simple-output-20261016/runtime/snapshot.json` 恢复为原始 SHA `69908e99312d958ca17c40b15a76b06c9ab71f54a692715ab17c922bb2fa3fc9`；146 个源文件逐一核验。
- simple-output 原始 `registration.json` 已从历史 `prepare.py` 生成链恢复，最终字节 SHA 精确为 `32f5cb13cbe578e89df9375a80bb347fb4e69a4f3d99b095dd5afb85d916fedc`；derived-inputs、prompts、offline-preflight 和运行快照 SHA 也分别匹配原 receipt/登记。full-r5 使用该原件，不是重建登记。
- 恢复过程的输入、原始 receipt、prompts 和 common registration 备份位于 `D:\graghRAG-agent\.tmp\ra1105\`；原始 registration 的恢复字节已核验，不把过程备份提交 Git。

## 工具链修复

Rust stable MSVC 原工具链 manifest 损坏；从官方 rustup 重装 `stable-x86_64-pc-windows-msvc`，实际 `rustc 1.99.1`。native bridge 专项 36 项通过。

## 证据边界

- `junit-identities-only.xml` 只保留测试身份；原始 JUnit 和 raw logs 留在私有 `.tmp`。
- 未提交候选二进制、私有运行库或大型 runtime hash 文件。
- Linux 容器、原生闭包整体安全、正式 serving runtime 替换、生产 `compatibility_not_approved` 解除、部署和迁移仍开放。
- Windows 门禁为 audit-only-windows；CI/分支保护机械门禁尚未验证。

## 依赖审计

`uv lock --check --offline`、`pip check` 和去重后的 159 项唯一第三方已安装分发包审计均为 exit 0；审计输出 `No known vulnerabilities found`。原始审计、命令和范围摘要见 `security/`。锁文件 SHA-256 为 `d17320959f38250916c8033e741d29ded4c8e61d299d28942d38f1d820df9a06`。


