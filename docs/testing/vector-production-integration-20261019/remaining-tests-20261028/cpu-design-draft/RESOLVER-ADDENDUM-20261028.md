# 单次官方 UV 检查与离线 resolver 补记

本补记晚于初始 REPORT.md/evidence-manifest.json；保留旧尝试，不覆盖旧报告。时间2026-10-28。本次仅更新私有候选目录，C 输入/正式默认 GPU/生产准入和冻结 runtime/bridge 完全不改。

为避免新的 sdist 代码执行，本次把一次官方联网额度用于 `uv pip install --dry-run --no-deps --no-build` 精确 Torch CPU 检查，随后离线执行正常 `uv lock`。精确 argv/env 在 `torch-metadata-once.command.json` 和 `candidate-uv-lock-after-torch.command.json`，执行脚本保留为 `torch-metadata-once.ps1`。这与直接联网 uv lock 的流程不同，未冒称执行了该命令。

- 联网单包检查：exit0，UV报告 `Resolved 1 package in 2.43s`、`Would download 1 package`、`Would install 1 package`、`torch==2.14.0+cpu`。正常系统 TLS，HTTP timeout20秒、retry1、并发4，外部进程总限180秒。没有安装包或构建 sdist。
- 重要边界：`--no-deps` 的 dry-run 并不需要完整包依赖元数据。实际 cache 新增官方 simple index，未产生 Torch wheel `.msgpack` 元数据；仅有0byte wheel lock（名称为linux_s390x）。不能把该选择结果称为指定x86_64包元数据已取得，也不能把 dry-run 成功当锁成功。已手工取得、核SHA的x86_64 PEP658文件仍是先前独立证据。
- 随后离线正常 uv lock（不带额外 `--no-build`）exit1，仍只报告Torch registry metadata 缺失；没有运行新 sdist。缓存oss2/crcmod metadata保持原件。
- 离线退出后 uv.lock SHA仍为主锁seed `6168a2319f7b2964b7f325ab700444c5974b7c2c6fbc4ee95bb0c5eefdca1b90`。保存为`candidate/backend/uv.lock.after-torch-unchanged-seed`，避免被误当 CPU lock。当前仍无实际生成的 CPU uv.lock。

## 与旧静态草案的差异

没有resolver-generated lock，因此不能声称真实锁与静态图一致，也没有有效的“新锁包集合”可比较。旧静态草案完全保持：runtime133（132registry+1本地），all_groups158（157registry+1本地），自然删除19 GPU节点，仅Torch2.14.0→2.14.0+cpu。这些均仍标记 draft，不是解析、安装或审计通过。

## 阻断与下一步

本次没有新增网络故障证据；阻断是安全限定的单包dry-run未填充完整resolver元数据，后续离线解析缺输入。未追加网络重试、未构建sdist、未下载完整196MB Torch wheel、未改依赖版本、未造锁。

若获下一步授权，正确最小方式应是直接联网正常`uv lock`使用已验证缓存，并以明确机制阻止任何新sdist构建，或使用能实际缓存精确x86_64 PEP658的UV操作；不能再重复把no-deps dry-run当metadata导入。完整候选锁生成后才逐包比较旧静态草案并扫描实际完整CPU集合。
