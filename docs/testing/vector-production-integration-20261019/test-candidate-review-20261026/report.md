# 私有测试候选独立复核 — 2026-10-26

结论：两组候选在本次限定范围内无阻断项，可以由 root 发布到 C1019 后冻结最终输入并继续完整验证。本结论不代表整体后端验收、双90、安全扫描、生产准入、提交或部署通过。

## 范围和身份

已读取项目 AGENTS.md、memory/index.md、C 工作树 memory/2026-10-26.md，以及实际安装的 requesting-code-review/SKILL.md。独立 reviewer 仅在 D `.tmp/test-candidate-review-20261026` 写入自己的执行器、证据与本报告；未改 C 源码、Git index、分支或提交。C HEAD 只读核实为 b1e300f1445c48f9f838bcc0d7b91cb39c1171b2，工作树包含现有修改，不能当作该提交原始干净代码。

评审输入最终 SHA256 逐文件见 before.json 与 after.json；两者完全相同。包含三份 A 候选、diff/report/作者hash、B 候选、R3 runner、当前 C 两份研究生产模块、原测试/helper、备份生产模块/夹具、永久 receipt/prompts/覆盖配置，以及 D 原 registration/prompts/冻结 snapshot。

## A：解除历史 skip

- 比较 candidate.diff 和当前 C 原测试：仅替换输入定位和 skip；保留 9 units、147 source_code_files、SDK transport/model、预算公式、无 .env、common budget，以及 runtime canonical 副本和原 canonical 两个 drift 拒绝断言。未删除或放弱原行为断言。
- frozen_prompt_root 先由 C 永久 receipt 约束 D registration 原字节 hash；核 receipt runtime/new-input 绑定；D 原 prompts 按原 registration governance hash 验证字节；再与 C 永久 prompts 比较 JSON 语义并逐 prompt 字段比对 registration。
- 最后确实调用当前 C research.common_three_arm.verify_registration；该原函数核 registration.sha256.json、contained runtime、全部 source/kg/source hashes、snapshot、依赖 environment、governance 与 kg provenance。没有替代/删减 verifier。pilot/common __file__ 均断言当前 C 模块身份。
- 新增四个失败用例实际拒绝 missing、registration bytes drift、prompt bytes drift、permanent prompt semantic drift。它们的临时 fixture/monkeypatch 不修改永久原件，不替代主正例的完整验证链。
- 当前 C prepare 编排及 verify_registration 被执行；其原有 prepare 子进程执行 hash-verified 历史冻结 runtime 的 SDK mock preflight。SDK网络由既有 mock transport 控制，不是付费供应商真实网络或当前生产代码全链证明。候选 docstring/report 明确这个边界；未把历史源码声明为当前源码覆盖。

## B：备份拒绝契约

- 新增49个参数化/独立行为用例，未修改原备份测试、生产实现或覆盖配置。导入 C 原 service/publish/backup_type 夹具，实际创建 SyntheticStorageConfig 隔离目录，调用真实 VectorStore/DocumentPublication/PublicationBackup/硬化 SQLite connect；没有 mock 掉数据库、备份、恢复或验证器。
- manifest damage 的 verify/restore 两操作均明确 ValueError（具错误前缀），并断言 archive 树逐文件字节不变、live assets 树逐文件字节不变、target 不存在、.restore-* staging 不存活、原 live query 仍 v1。
- 十种 catalog relationship 损坏修改实际封存 SQLite 后重新计算合法 database digest，因此拒绝实际依靠 catalog 关系验证，不是旧校验和误拒绝；断言归档 bytes 不变、target/stage 不存在、live query 保留。
- 无效 asset registration/create 拒绝实际断言无封存目录、无 publication stage、live assets bytes 不变、pins=0；冲突hash、缺失必需asset、已有destination、optional asset伪称缺失和空库roundtrip均有行为断言。
- 原件保留断言覆盖归档和 live assets；不是仅检查 raises。并非每个新增case都逐字节比较 live SQLite（合法 pin 生命周期会触碰库），报告未把 query 断言夸为完整数据库字节恒等。

## R3 runner（仅静态及只读枚举，未执行全量）

- 依照 runner 完全相同枚举规则核实当前生产范围为119份Python源码，完整清单见 r3-production-scope.json。coverage source=backend、branch=True，包含未导入文件；原配置无默认 pragma/partial-branch 豁免。
- production set 与 coverage report measured set 严格 missing/extra 比较；两项分别按 covered_lines*100 >= num_statements*90、covered_branches*100 >= num_branches*90 判断，未采用混合百分比或四舍五入。
- tests/export 任一失败使 command_gate 失败；超时为124；Junit 要求 collected>0 且 failure/error/skipped 均0；before/after input drift、scope 或任一覆盖指标失败均使 backend_gate/进程失败。未看到静默绕过、skip 放行或缩小当前119分母。
- 119是本次只读枚举值，runner通过动态快照推导范围，并非硬编码常量。本次没有运行 runner，不声称其最终报告或整体验收通过。

## 实际独立验证

Python：D:/graghRAG-agent/.tmp/runtime-lock-20261022/.venv/Scripts/python.exe。

1. `python -B D:/graghRAG-agent/.tmp/test-candidate-review-20261026/run_review.py`（执行器完整命令及环境见源码、commands.json）：A候选16 passed in72.85s，pytest exit0；B候选49 passed in88.27s，pytest exit0；总执行器 exit0；before==after true。分别见 historical.log/historical.xml、backup.log/backup.xml。
2. `python -B .tmp/test-candidate-review-20261026/run_helper.py`：对 C 原 helper 测试的私有逐字节复制执行候选 helper，5 passed in0.71s，exit0；helper.log/helper.xml。未变更该测试断言。
3. `python -B .tmp/test-candidate-review-20261026/check_scope.py`：exit0，119文件。
4. 初次把 C/D 两盘测试混合收集时 pytest 在 D:/WpSystem/__init__.py 报 WinError1337，A/B均 exit4且未进入用例；改为分别选择D候选后通过。首次失败原样保留 historical-attempt1.log、backup-attempt1.log、commands-attempt1.json，没有冒充成功，也未通过删弱测试修复该环境问题。

专项没有skip。未执行全后端、未生成新全量覆盖率，也未运行漏洞扫描。作者报告仅作定位，结论来自上面的独立代码检查及实际限定执行。需要 root 发布后对最终 C 输入快照重新跑规定完整检查；此前不允许据本报告 commit/push。

## 问题分级

- 阻断项：无（就两候选测试的允许发布范围）。
- 非阻断边界：A历史SDK子进程不是当前生产全链；B专项不是全量覆盖；R3全量未执行。这些边界已在候选及本报告清晰标注。
- 未发现削弱断言、忽略/skip逃避、mock冒充真实数据库、改写冻结资产原件或把作者专项自报当整体验收的情况。
