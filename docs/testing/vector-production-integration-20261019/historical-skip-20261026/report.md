# 历史 SDK mock 测试解除 skip 私有候选

仅修改测试/helper；没有写入 C 工作树、生产代码、注册值或冻结输入。

根因：C1019 checkout 不含被忽略的历史 .tmp 数据。原测试从 checkout 相对定位并 skip；显式 GRAPHRAG_FROZEN_TEST_ROOT=D:/graghRAG-agent 可定位已登记历史输入。

候选冻结链：当前C永久receipt.registration_sha256 → D原registration原始bytes；receipt.runtime_snapshot_sha256 → registration字段；receipt.new_inputs_sha256 → registration治理derived-inputs原hash；D原prompts治理hash → 实际原始bytes；C永久prompts → JSON语义及registration三个prompt字段；当前C common_three_arm.verify_registration完整检查源码/KG/runtime/environment/governance。当前pilot/common模块各有 __file__ origin断言。任何missing/drift直接失败；无skip。

保留原9 units、147 source files、模型/预算、.env缺失、canonical及runtime drift全部断言。新4负例验证missing、registration字节漂移、独立临时登记fixture的prompt字节漂移、永久prompt语义漂移。SDK请求均走既有真实SDK MockTransport预检；无付费API调用。历史runtime按原协议在新进程中执行，不将它宣称为当前生产覆盖。

实际命令（PowerShell，cwd D:/graghRAG-agent）：
```
& .tmp/runtime-lock-20261022/.venv/Scripts/python.exe -B .tmp/historical-skip-20261026/run_candidate.py
& .tmp/runtime-lock-20261022/.venv/Scripts/python.exe -B .tmp/historical-skip-20261026/run_candidate.py C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend/tests/test_frozen_input_helpers.py
```
候选运行器把helper候选文本以当前C路径为__file__加载，确保CODE_ROOT为C，生产模块仍C原件；只在D运行候选测试，不是最终C快照验收。第一次sandbox临时路径权限失败；第一次escalated暴露真实registration无new_inputs_sha256字段，两失败均保留并已改正为治理derived-inputs hash绑定。

最终：final.log / junit.xml：16 passed，79.58秒，进程退出0，无skip；helper-regression.log / helper-junit.xml：原C helper 5 passed，进程退出0。当前结果是专项候选证据，不替代全后端双覆盖或新依赖快照复验。最终hash见hashes.json，diff见candidate.diff。须独立评审后由root发布C并复验。
