# 独立有界评审 — 2026-10-27

结论：本次限定三组改动未发现阻断问题，同意 root 将两条准入回归及两条凭据传输 unit 测试发布到目标测试目录，再执行最终快照全量验证。本结论不是提交、生产准入或全量通过许可。

目标 C1019 HEAD b1e300f1445c48f9f838bcc0d7b91cb39c1171b2，codex/safe-snapshot-20261019；已有大量其他修改。只读 C，未改其任何文件、未执行全量、未读 R4 原始失败日志或进程 CommandLine。使用 requesting-code-review 技能的正确性/契约/测试质量检查方式；未再派生评审代理。

## 输入及机械差分

完整 SHA256 见 inputs-reviewed.json，运行后重新读取验证无漂移。

- 准入测试 a42428da3cdbe848fa9cfbf40cdcb6e74916f87a4fd90d8533f5b26de91195ac；十个受测生产文件与作者 inputs-before.json 一致。
- lifecycle 当前 C 与 D 候选精确同字节 f4b9b3475b53e15d33e5aa89e456fa95afb189562ef70c929055e71e4deb3528。仅反向三处 argv→stdin 的传输变更，即精确重建 R4 before.json 登记的旧文件 299a3fdbab8099958d5e7dabf20a947f6763a95e61da8ec69985c1aadbd91ffa。60/35/240 时限、生命周期测试及所有断言完全未变，差分见 lifecycle-reviewed.diff。R4 manifest 本身 SHA 是 9a47cd9a545ece66abbd02eb6ee12230da8c2951703719d33d8d5234724f3e51。
- 凭据 unit ef682a756a076ba3a2d2ed4e0e92d17676e81e0220b76475220441ef57428d6c。
- backup rejection ac3a851c46f754a1d45f8163c3ff4f913a1a90b9c30ddbddfae66a000169845f：仅反向完整包导入即可精确重建 R3 before.json 旧 hash；故所有原损坏矩阵、原件字节、恢复目录、查询保留、pin释放及空库往返断言均保持。作者 backup-package-20261026.log 为49 passed；此处未将该历史结果冒称独立重跑。

## 行为与证据判断

准入测试真实创建目录和匹配 SHA manifest，调用真实 create_pinned_embedding，准确断言 HTTP503/detail/ValueError('incomplete model identity')，避免把哈希失败或loader异常误当资产完整性准入证据；真实源码确认 required-assets 在 SentenceTransformer 导入之前执行。另一例通过真实 compose/VectorStore/DocumentPublication 创建旧publication，仅新输入revision不同且model/dimension相同，实际拒绝后新目录递归集合和marker原字节未变，旧publication和encoder对象保留，finally还原globals。SimpleNamespace 是本例准入输入，没有替换compose、存储、模型加载或socket，也没有覆盖率填充分支。

stdin改变使Authorization headers不再出现于subprocess命令参数，TimeoutExpired的标准命令诊断随之不包含其值；JSON文本输入与子进程json.load(sys.stdin)相匹配。两条unit明确mock subprocess.run边界，只证明传输选项与timeout诊断，不作为新进程/HTTP/真实模型生命周期证据。已核对作者transport-red-r2.log两失败到transport-green.log两通过；未读取含真实合成JWT的R4原日志。

独立运行同一最终快照：两真实准入例＋两明确unit，共4 passed、1 deprecation warning，exit0，1.78s。pytest.log/pytest.exit/junit3.xml保存原输出，commands.json保存实际成功入口。前两次入口配置错误在收集阶段退出2和4，完整保存在cwd-collection-error.*与ancestor-collection-error.*；没有删测试、改断言或修改候选。

## 范围限制与下一步

本组只有测试/测试helper变化，新增生产分母为0并不改变既定完整后端生产文件分母，不能据此缩小覆盖范围。没有验证全量双90、真实固定模型240秒链或安全扫描，不判断线程竞争根因，不提出自动放宽任何时限。root可发布测试后，以最终代码快照执行规定全量和覆盖门槛；保留正在进行的debugger独立测量。未提交/推送/部署。
