# 模型准入真实行为专项（2026-10-27）

只新增本目录 `test_vector_model_admission_failures.py` 两例，未修改生产代码或 C 目标。目标工作树已有其他任务修改，未覆盖、清理或提交。只读 git 核验 HEAD 为 `b1e300f1445c48f9f838bcc0d7b91cb39c1171b2`，分支 `codex/safe-snapshot-20261019`。

1. 真实临时模型目录仅包含 `config.json`，manifest 的唯一 SHA256 实际匹配。调用真实 `create_pinned_embedding`，断言 HTTP 503、公共 detail，以及准确的 `ValueError('incomplete model identity')` 原因。这明确命中 required-assets 校验（在模型 import/加载之前），并且文件原字节和目录内容不变。没有 mock 主函数、模型加载器、socket 或 import，也没有全局追踪钩子。
2. 先通过真实 `compose_synthetic_runtime` 创建已有 publication；另开真实 `SyntheticStorageConfig.create()` 新目录，入参 encoder 与目标 profile 的 model/dimension 一致，仅 revision 不同。真实 compose 必须以 `model_profile_mismatch` 拒绝，新目录全递归路径仍只有原 marker，marker 字节不变，原 publication 与 encoder 对象仍保留；finally 恢复调用前全局配置，真实 context manager 清理专用合成临时目录。

最终验证使用隔离 fullenv Python 3.12.15 / SQLite 3.54.0，实际命令和环境见 `commands.json`。最终结果 `2 passed in 0.82s`、exit 0，见 `pytest.log`、`pytest.exit`、`junit.xml`、`verification.json`。测试 SHA256：`a42428da3cdbe848fa9cfbf40cdcb6e74916f87a4fd90d8533f5b26de91195ac`。`inputs-before.json` 和 `inputs-after.json` 绑定测试及十个受测路径生产文件，运行前后漂移 0。

期间一次 PowerShell JUnit 参数构造错误导致 exit 4、未运行测试，原错误日志保存在 `argument-error-*`，随后修正参数复跑成功。这里仅为两个新增真实行为回归，不代表全量测试、覆盖率门槛、安全扫描、生产模型支持域或生产准入通过；未 commit/push/deploy。独立评审由 root 接续。
