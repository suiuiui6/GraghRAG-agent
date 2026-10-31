# Linux CPU backend candidate preparation — 2026-10-28

结论：**CPU profile设计、精确官方TorchCPU发布身份和完整静态依赖差异草案已准备；CPU uv.lock尚未生成，未安装或部署。** 当前剩余阻塞是resolver所需TorchCPU内部metadata缓存缺失及先前网络取元数据失败，不是torch2.14.0+cpu不存在或已证实的版本冲突。按根的有限重试要求停止额外联网。此准备不阻挡Windows最终验收，不改变用户未确认的正式CPU/GPU选择。

本目录仅拥有新候选文件；正式C树、真实.env、现有卷、服务、GPU默认行为、runtime/bridge冻结包和生产gate均未改。不复制待修backend实现。桥目录仅另外按根授权新增两个明确事后COMMAND-ADDENDUM文件，原REPORT/manifest未变；此CPU包不混入桥证据。

## 当前基线与工具

仅复制backend pyproject/主锁及LangExtract静态pyproject元数据至`baseline/`：

| 输入 | SHA256 |
|---|---|
| backend/uv.lock | `6168a2319f7b2964b7f325ab700444c5974b7c2c6fbc4ee95bb0c5eefdca1b90` |
| backend/pyproject.toml | `961a7f39035342cbfd09739f54e7f7a3dfe34fd005a02081c5f6675830d71ed8` |
| langextract/pyproject.toml | `c115f537b2c915efc80c9177cd44393a13aa5a8a00b7c078b9955ca3b2c78a8e` |

工作结束前再次读C树两主文件hash，仍完全相同。LangExtract版本1.5.0；backend虚拟项目版本0.1.0，未把应用源码复制固化。主锁包含179个唯一registry包，是来源全集，**不是此CPU profile的包数**。

resolver工具：`D:/Python/Scripts/uv.exe` 0.11.16，SHA256 `c5a583d5f1f6d055fc1c32c87d8eceee90edc69a5b9af5da70811befdfc04880`。host元数据解析选用已存在Python3.12.8；这不声称host成为目标runtime，目标仍是已审Linux Python3.12.16/SQLite3.54.0派生身份。固定输入见`baseline-inputs.json`。

## 官方CPU wheel事实

[PyTorch官方CPU索引](https://download.pytorch.org/whl/cpu/torch/)正常Windows原生TLS读取exit0；HTML414325bytes，SHA256 `afbb7e04f36d5c3d8b7141bcf10682954f05bb4d5f0297876127ffbb93f015f8`。

- 精确文件：`torch-2.14.0+cpu-cp312-cp312-manylinux_2_28_x86_64.whl`。
- 官方索引指向：[官方wheel URL](https://download-r2.pytorch.org/whl/cpu/torch-2.14.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl)。**官方发布SHA256**：`a09987c95ec4cffdb6df798d3d641558110a334cfccce22f2f046d83142bc260`。
- 官方PEP658 METADATA实际下载exit0，SHA256 `6e6cbfdc8067a91fe9fa5068191574caef6d04c743da805707b849396a8834f6`与索引data-core-metadata/data-dist-info-metadata发布值一致。
- wheel HEAD正常TLS实测200，Content-Length196253793。**没有下载196MB完整wheel或独立重算其文件摘要**，不能把发布SHA冒称本地完整原件已核。
- METADATA name=torch、version=2.14.0+cpu、Requires-Python>=3.10。常规依赖为filelock、typing-extensions>=4.10.0、setuptools>=77.0.3、sympy>=1.13.3、networkx>=2.5.1、jinja2、fsspec>=0.8.5；optree/opt-einsum/pyyaml为明确extras，无默认CUDA/NVIDIA/triton依赖。泛化summary中的GPU字样不是此CPU依赖图的依据。

精确来源记录在`torch-cpu-index-receipt.json`，原HTML、METADATA和HEAD均保留。最初Docker urllib因self-signed证书校验失败退出；没有禁用证书检查或修改全局信任，改用Windows系统信任的正常TLS成功取得官方资料。

## 设计和隔离候选元数据

`DESIGN.md`比较三种方式，推荐私有backend＋LangExtract metadata，`tool.uv.environments`限定Linux x86_64，明确直接pin`torch==2.14.0+cpu`，torch单独source绑定官方命名CPU index，`explicit=true`防止普通包从该index漂移。其余179主锁版本全部作为版本约束保留（torch替换为+cpu）；**约束不是要求安装的分母**，GPU节点应由真实CPU图自然不再依赖，而非人工删扫描行。

`candidate/backend/pyproject.toml`及`candidate/langextract/pyproject.toml`为待独立评审metadata，不是已通过的正式配置。候选pyproject SHA见`candidate-preparation-receipt.json`。未修改正式主锁或GPU行为；CPU只是独立候选，不擅自改变正式模型device策略。

来源策略参考[uv官方PyTorch说明](https://docs.astral.sh/uv/guides/integration/pytorch/)。曾尝试Aliyun普通PyPI镜像作为传输，未产出新锁；正式基线registry实际是`https://pypi.org/simple`，不能把该镜像尝试称“恢复原registry”。保留包摘要仍须回映基线官方artifact SHA，镜像不成为来源权威。

## 实际resolver尝试与阻断

所有尝试使用本目录私有cache，禁自动Python下载、未安装包或运行后端：

1. 官方PyPI，system-certs，HTTP20秒/0重试：`candidate-uv-lock.exit=2`，apscheduler simple请求超时；不是版本不可满足。
2. Aliyun普通PyPI传输、Torch仍explicit官方CPU：`candidate-uv-lock-mirror.exit=2`，aiohttp响应TLS提前关闭。未禁证书。
3. 仅复制公开缓存metadata（160个simple索引、199个wheel metadata、oss2/crcmod的revision/metadata；未复制wheel、archive或包源码）后离线检查，保留全部失败日志。复制来源/目标逐SHA见`copied-*-metadata-receipt.json`。
4. 根允许的一次最终官方源有界尝试在启动前保存精确argv/env到`candidate-uv-lock-final.command.json`；180秒进程deadline，socket20秒、1次retry、并发4、system-certs。我额外加的`--no-build`导致sdist-only oss2无可用wheel，exit1，**这是此检查额外wheel-only限制，不是CPU依赖冲突**，也没有修改/排除oss2来制造通过。
5. 只做不联网修正核对，去掉额外wheel-only限制，既有oss2 metadata已可用，但`candidate-uv-lock-offline-corrected.exit=1`明确Torch2.14.0+cpu的UV registry metadata缓存仍缺。手工已取得且核SHA的PEP658文件不能冒充UV内部缓存或新锁。到此停止联网，没有继续扩大重试。

因此原`candidate/backend/uv.lock`始终仍是完全未变的正式主锁seed。为避免被误当CPU锁，已保存为`uv.lock.seed-main`（同6168...SHA），并放置`LOCK-NOT-GENERATED.md`。当前**不存在经resolver生成/核验的CPU uv.lock**。不手工伪造UV锁、注入其私有缓存格式或为可下载换版本。

## 静态差异草案（非UV锁、非安装清单）

`compute_static_cpu_diff.py`从基线主锁依赖边、root runtime/dev声明以及已核官方CPU METADATA计算完整闭包，显式使用Linux/x86_64/CPython3.12.16环境，逐PEP508 marker和extras展开。`static-cpu-lock-diff.exit=0`；JSON显式标注`static dependency-graph draft ... NOT resolver-generated uv.lock or installed-package inventory`。

| 范围 | 基线Linux闭包 | CPU图草案 | registry | 本地LangExtract |
|---|---:|---:|---:|---:|
| runtime | 152 | 133 | 132 | 1 |
| all_groups | 177 | 158 | 157 | 1 |

没有套用Windows159或主锁179计数。两个范围均只将torch2.14.0替换为2.14.0+cpu，其余包版本不变、无新名称；自然移除相同19个GPU图节点：cuda-bindings、cuda-pathfinder、cuda-toolkit，nvidia-cublas/cuda-cupti/cuda-nvrtc/cuda-runtime/cudnn-cu13/cufft/cufile/curand/cusolver/cusparse/cusparselt-cu13/nccl-cu13/nvjitlink/nvshmem-cu13/nvtx，以及triton。

`static-cpu-lock-diff.json`完整列出两个范围的每个包版本、source、主锁sdist/wheels/hash、active extras、候选依赖边、本地LangExtract版本及base runtime映射。两个`cpu-*.requirements.draft.txt`带完整候选registry集合及既有原件hash，**仍是草案，不能冒称通过UV/安装验收**。CPU图删除GPU包是设备profile的真实需求，不代表其余包或native风险已清零。

## 下一步与未执行

先独立评审metadata设计、Torch官方发布身份和静态差异算法；恢复已授权的精确官方Torch metadata到UV可用正常缓存/完整同SHA原wheel后，再运行正常resolver并逐包对比，保持版本与GPU删除理由。不要用手写图草案代替UV lock check。

生成锁后，按实际CPU runtime/all_groups两套完整集合扫描；Torch+cpu的advisory版本映射和native组件单列，不能忽略不支持版本查询来称安全通过。base CPython/SQLite/OpenBLAS/libc/安装工具和本地LangExtract/source身份另外映射，不能从registry计数排除实际安装的包制造通过。

未执行：完整CPU wheel下载/SHA复核、CPU完整UV锁、全部实际Linux安装/RECORD、CPU torch/tensor/固定模型真实运行、CPU全包及native扫描、正式backend快照/全链、部署或生产激活。上述未完成不阻挡既有Windows验证，也不由本报告放宽正式准入。
