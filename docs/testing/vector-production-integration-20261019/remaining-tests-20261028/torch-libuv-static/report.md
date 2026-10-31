# 固定本地Bert链的Torch/libuv静态可达性审查 — 2026-10-28

结论：**uv.dll存在且版本1.40.0落已知公告区间；当前固定本地单进程Bert/encode链未找到分布式入口或向libuv传入外部hostname的显式调用链。完整native调用闭包未证明，风险仍open，不能据本报告自动接受风险或开启gate。**

本轮只读C冻结输入与已安装包源码，未加载模型/执行推理、创建TCPStore/网络连接对象、运行攻击输入、改DLL/配置/锁或生产准入。输出仅在本目录；新旧原始收据未改。使用实际文件hash、完整小模型配置和明确静态检索范围，不以“rg未命中”替代全域不可达证明。

## 公告条件与实际载荷

沿用实际version API收据：torch/lib/uv.dll `uv_version_string()=1.40.0`，SHAfa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8，Torch2.14.0+cpu commit08187d9e0fba026dc8217405802ab5381dc88d90。[libuv官方GHSA-f74f-cvh7-c6q6/CVE-2024-24806](https://github.com/libuv/libuv/security/advisories/GHSA-f74f-cvh7-c6q6)列受影响>=1.24.0、补丁1.48.0，包含Windows uv_getaddrinfo实现。实际攻击要求不可信超长hostname进入该API，配合地址检查/内部目标访问等条件；DLL被加载、内存中有该代码或输入文本看起来像域名，分别都不足以证明触发。

本轮未取得该DLL回补证据；不得以Torch包>=2.9自动排除它，也未证项目SSRF可利用。

## 固定模型绑定

唯一输入收据：D:/graghRAG-agent/.tmp/vector-backend-runtime-20261020/model-encode-receipt.json。固定revision `7999e1d3359715c523056ef9478215996d62a620`、BAAI/bge-small-zh-v1.5。只读取config.json/modules.json/tokenizer_config.json/sentence_bert_config.json/1_Pooling/config.json五个小文件，逐项SHA均与收据相等；没有重hash或改95MB权重。

config声明model_type=bert、architectures=[BertModel]。modules依次内置Transformer、Pooling、Normalize；未出现自定义remote module。上述事实及receipt SHA保存在model-config-evidence.json。当前R9的HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE=1来自root明确给定的运行输入说明，本轮不枚举进程环境，不把它当全部网络动态证明。

## 已找到的明确应用链

1. backend/services/document_runtime.py:22起先检查固定manifest及每项hash、路径和必需文件；45-47以本地root构造SentenceTransformer，local_files_only=True、trust_remote_code=False、use_safetensors=True。不是从用户输入解析模型ID。
2. 同文件66-67仅传texts及normalize_embeddings=True/show_progress_bar=False/batch_size=32。调用方没有转发device列表、pool、master address、RPC后端或rendezvous URL。
3. 安装SentenceTransformers6.0.1的sentence_transformer/model.py:754-774默认device=None、pool=None、backend构造默认torch。881-913只有显式pool或非空device列表走_multi_process；当前参数走917-946单设备self.to(device)/eval/preprocess/batch_to_device/self(features)。base/model.py:554-571顺序调用子模块。实际BertModel源码594-610/650-683为embeddings→encoder→pooler路径。保存完整相关行与源SHA于static-excerpts.json。
4. get_device_name静态逻辑会检查加速器、已有distributed状态，必要时读取LOCAL_RANK；这些“读取已有状态”的语句不是创建process group。当前CPU wheel build身份及固定模型背景支持单进程推理判断，但本轮未动态测device或所有可导入扩展，不把默认选择证明成全域环境不可干预。

数据流能支持的窄结论是：用户query/文档chunk以文本输入进入tokenize/tensor forward，当前应用没有把它们显式用于分布式主机地址参数。尚无逐native函数完整数据流证明，不能进一步声明任意文本永远到不了uv_getaddrinfo。

## 已找到的libuv相关发行包入口

- torch/__init__.py:280-299在Windows导入时glob并LoadLibrary torch/lib下DLL。此行为解释uv.dll可被加载，不证明uv_getaddrinfo被调用。
- 安装torch/distributed/rendezvous.py:198-222能构造TCPStore，TCP URL/env handlers可从hostname/MASTER_ADDR/MASTER_PORT构造store；这些是已找到的地址来源入口。64-70有Windows默认use_libuv=0代码，但它不证明编译选项、直接TCPStore调用、其他路径或本机实际运行后端，所以不据此关闭问题。
- 安装include/.../TCPStore.hpp:20-28描述LibUVTCPStoreBackend，70的C++options默认useLibUV=true。PythonWindows默认和C++通用默认不是同一个层面；不能选择有利注释覆盖其余入口。
- 安装torch/distributed/rpc/backend_registry.py:344-395会初始化process group并创建TensorPipeAgent。上游已知TensorPipe/libuv关系可参考[PyTorch官方相关安全公告](https://github.com/pytorch/pytorch/security/advisories/GHSA-2rj9-7h5r-q4h8)，但本轮未取得此Windows wheel TensorPipe编译/链接闭包，不把该关系当实际启用证明。
- [PyTorch官方TCPStore教程](https://docs.pytorch.org/tutorials/intermediate/TCPStore_libuv_backend.html)说明分布式训练控制面使用libuv TCPStore，可由直接TCPStore或process group初始化进入。教程泛化默认并不覆盖当前Windows实物配置。

以上只定位已知调用者类别，不代表libuv只有这些消费者，也未证明这些入口最终会调用漏洞所处uv_getaddrinfo。

## 静态检索范围与阴性证据

项目命令与范围保存在project-distributed-search-command.json、project-search-file-scope.json：backend下遵循项目ignore规则的121个非tests Python文件，搜索TCPStore/init_process_group/torchrun/torch.distributed/tensorpipe/init_rpc/multiprocess encode/DataParallel/DDP/MASTER_ADDR/USE_LIBUV/WORLD_SIZE/LOCAL_RANK；rg exit1、stdout空、stderr空。另查docker-compose.yml、Dockerfile.backend、deploy/docker-compose.monitoring.yml同类入口，exit1无命中。

这明确表示**该范围未找到显式入口**；不涵盖所有第三方依赖、任意动态import/getattr、外部启动器、环境注入、恶意替换资产或未来新模型/分布式选项。不是模型全生态不可达证明，更不是风险接受授权。

## 获取失败与不可外推边界

为了核native入口，尝试从固定官方Torch commit只取TCPStoreLibUvBackend.cpp、TCPStore.cpp、socket.cpp三份小源。实际时间、URL、command、各自exit28及SHA/缺失在official-source-receipt.json；三次耗时约7.063/20.062/20.063秒。socket.cpp只有1378字节残片，**不作为完整source或调用闭包证据**。source-fetch.exit为下载执行器正常退出0，不是三次HTTP成功；真实每项exit28必须保留。现停止网络追闭包，不下载大repo或新SBOM。

足够的证据：固定模型身份/应用固定参数、已安装Python分支、已找到分布式入口以及明确范围的静态未命中。仍缺的证据：当前Windows完整native消费者闭包、uv_getaddrinfo真实数据流/回补，及对其他扩展/外部启动配置的排除。下一步若需关闭需另行审定有针对性证据或修补候选；本报告不建议原地替换DLL、不改变compatibility_not_approved。

本任务完成的是上述**具体静态审查证据交付**；不是完整原生安全验收完成。没有产品源码修改、测试执行、提交或部署。
