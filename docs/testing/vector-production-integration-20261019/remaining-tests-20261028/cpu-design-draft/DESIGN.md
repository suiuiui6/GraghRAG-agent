# Linux x86_64 CPU deployment profile — independent candidate

本设计只准备独立候选元数据、依赖锁和来源能力证据，待独立评审。正式C树pyproject/主锁/GPU行为不改；不复制当前待修backend源码、不部署服务、不读.env/真实卷，不开生产gate。CPU是假设性候选目标，不代表用户已改变正式设备选择。

## 方案与选择

1. **推荐：私有backend＋LangExtract元数据，Linux x86_64限定，Torch显式绑定官方CPU index。** 复用当前backend声明、dev分组及LangExtract1.5.0依赖元数据；额外明确`torch==2.14.0+cpu`。PyTorch index设置`explicit=true`且只在torch的source中引用，其余包仍从主PyPI来源解析，并用主锁精确版本约束控制漂移。生成单独uv.lock及runtime/dev两套完整集合差分。
2. 单独一张requirements替换torch：更短，但容易丢失本地LangExtract和dev分组/marker来源，机器复验和主锁对比更弱，仅作为最终导出物，不作唯一真相源。
3. 修改正式主项目为CPU/GPU双source：会改变正式默认和跨平台锁，需要产品判断，当前不采用。

CPU依赖图中不再需要CUDA工具链/NVIDIA/cu13/triton时，由真实CPU wheel依赖元数据及resolver自然移除；不手删锁节点或扫描范围。保留所有实际CPU直接/传递依赖并完整扫描。主锁179等历史计数不套用此Linux候选，候选集及runtime安装集各自实算。

## 固定基础与身份

来源基线mainlock SHA256 `6168a2319f7b2964b7f325ab700444c5974b7c2c6fbc4ee95bb0c5eefdca1b90`；backend pyproject `961a7f39035342cbfd09739f54e7f7a3dfe34fd005a02081c5f6675830d71ed8`，LangExtract元数据版本1.5.0、SHA `c115f537b2c915efc80c9177cd44393a13aa5a8a00b7c078b9955ca3b2c78a8e`。这只是元数据快照，未来正式源码待Gitmetadata问题修复和root冻结后再取。

运行库复用已审Python3.12.16＋SQLite3.54.0的固定Linux bookworm派生身份和readonly目录策略；单独CPU候选不得把目前未经正式批准的Linux数值桥作为已放行包。模型保持现有固定BAAI/bge-small-zh-v1.5所有文件hash/revision/512维与归一化身份；不下载替代模型，也不擅改正式device逻辑。

容器需求继承1019设计：runtime `/opt/graphrag-runtime`只读、模型`/app/models`只读、非root仅data目录可写，output与uploads及登记资产持久化；正常默认启动继续compatibility_not_approved。CPU候选在后续合成验收中显式确认torch版本带+cpu、cuda不可用、真实tensor和固定模型在CPU执行；不是现在改生产配置。

## 来源和锁验证出口

- 首先核实官方CPU索引存在精确cp312 manylinux_2_28 x86_64的torch2.14.0+cpu，并存官方HTML、发布SHA、METADATA发布摘要和Requires-Dist、实际HEAD可取性；存在性不等于完整wheel已取得。证书验证失败不得绕过，允许使用Windows系统信任而保留失败记录。
- 候选Torch source和本地LangExtract路径独立保存；其余包尽量精确保持主锁，任何不可满足约束形成明确差异和阻塞，不悄悄升降版本。
- 保存实际uv版本/可执行SHA、完整命令/env/退出码、输入前后SHA及候选锁摘要。分别导出CPU runtime、CPU所有分组的hash requirements，按Linux3.12环境计算闭包及官方wheel来源。
- 完整CPU候选包扫描覆盖实际全部直接/传递依赖；安全扫描未完成就明示未执行，不能把GPU节点合法删除冒称消除了其余包/native风险。
- 当前阶段不做全backend安装/功能结论。锁/来源独立审后，另行在独立venv/合成root验证全部实际安装、固定模型CPU I/O、正式backend全链及同快照门槛。

## 官方依据

[PyTorch官方CPU索引](https://download.pytorch.org/whl/cpu/torch/)用于精确wheel发布身份；[uv的PyTorch集成说明](https://docs.astral.sh/uv/guides/integration/pytorch/)支持命名index、explicit限制及source marker。上述方案不将传输镜像变成来源权威。
