# 向量生产集成设计独立评审

评审者：独立上下文Agent `/root/vector_integration_contract_review`，fork_turns=none，仅只读。输入为项目AGENTS、R8设计/真实验证、R5异常合同及生产源码；未修改生产代码、未执行行为测试。root组织设计修订及文档检查，不将评审意见当实测。

最终结论：设计与计划可提交用户确认，已识别设计阻断均在文档层关闭；新增更新字段、删除语义与对应既有P0断言变更尚待确认，生产准入及实现未完成。

## 最终版本

- `docs/design/2026-10-19-vector-production-integration.md` SHA256 `83357a9f9909f008f564cbf482cad0cff64faa41d9b4d9170d1902b381e3f148`
- `docs/plans/2026-10-19-vector-production-integration.md` SHA256 `605123911e998a1798d8d831dfbcc7daae22124ade07adcc17639a8b73db6965`

独立评审和root重新读取hash一致。root UTF8/尾随空格/5个本地文档链接检查exit0，私有机器收据`.tmp/vector-production-design-20261019/final-checks.json`。新增未跟踪文件不能仅靠git diff --check证明已检查，故实际读取全部新文档。

## 发现与处理

| 设计阻断 | 文档修订 |
|---|---|
| 同库但search/pages新开连接，prepared记录可被旁路读出 | 明确共享read_snapshot连接、生产门面/CLI/admin active-only |
| legacy-only删除后JSON恢复，旧文档更新无预期版本 | tombstone优先遮蔽legacy，legacy更新409/migration_required |
| 客户端无法取得expected_revision，异步冲突不明 | 列表/TaskResult增加active_revision，1起单调递增、task收据唯一、422/409及FAILED错误码 |
| 旧事务看不到撤权，最终检查承诺超出网络能力 | 新事务及实际tenant服务复核、最后校验线性化；删除/撤权404/403，版本变化一次整组重取 |
| cleanup状态未持久化，坏路径阻止撤销，旧资产过早清除 | cleanup记录/pin、坏路径blocked但tombstone、明确删除响应待清理状态；原P0契约变更待确认 |
| 在线备份与资产复制竞争 | 固定DB/清单并pin、复制/hash、封存后释放，隔离验证恢复目标 |
| 默认换SQLite与formatter未准入冲突 | 未关闭兼容门槛默认compatibility_not_approved，仅合成测试配置允许隔离集成，不fallback |
| 运行库/持久卷/旁路统计遗漏 | config统一root，catalog/health/backup/compose纳入，uploads持久化、最终镜像非root实测 |
| 计划删除顺序与修订设计仍冲突 | 最终修正为先文档写权限、解析错误仅阻物理清理、持久tombstone+blocked，危险资产字节不变 |

另独立确认local chunk ID从c00001重置、PDF不写向量、删除不清向量/全局索引、缺模型指纹。设计加入可信doc/revision命名空间、统一入库发布、授权缓存、模型profile；R8的pickle只有未用import，没有反序列化调用，不误报为已存在漏洞。

运行库只读探针分别实际输出：quality Python3.12.8/SQLite3.45.3；R8 Python3.12.15/SQLite3.54.0/NumPy2.5.4；均提供setconfig。这是本机能力定位，不是全原生安全或生产镜像通过。

仍开放：用户确认新增契约；formatter准入依据、生产编码、TDD/连续真实验收、双90、安全及容器验证、真实资料迁移和线上部署。没有新提交或外部发布。
