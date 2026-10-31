# Windows 原生公告窄范围适用性接续 — 2026-10-28

结论：**安全准入未闭合**。本轮有了具体待处理公告及实际二进制身份，不能继续把所有原生项仅写作笼统未知；也没有证据支持把每项公告写成已证远程可利用。未修改产品、配置、锁、运行库或测试，未编译、跑全量测试或遍历32706安装文件。仅写本报告目录。

## 实际输入与执行

工作树：C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent；委派基线 b1e300f，现有dirty工作属于root。已读根AGENTS、memory/index与2026-10-27、1019设计安全节、22日运行库及26日安全补丁收据。

`D:/graghRAG-agent/.tmp/security-lock-patch-20261026/.venv/Scripts/python.exe -B D:/graghRAG-agent/.tmp/native-advisory-triage-20261027/probe_metadata.py`：exit0，约3.2秒。只导stdlib及NumPy，查询选定分发metadata；只hash 6个指定runtime文件和NumPy的2个DLL。实际收据在 actual-metadata.json；未导入Torch/模型，未执行模型推理。

实测：CPython3.12.15/MSC1944/AMD64；base_prefix为D:/graghRAG-agent/.tmp/vector-runtime-20261020/derived/python；SQLite3.54.0；OpenSSL3.5.9；Expat2.8.5；zlib1.3.2；NumPy2.5.4。26日pip双扫描0和bridge Cargo audit0并不覆盖这些二进制的全部原生依赖。

## 公告判断（截至2026-10-28查询，公告均已在27日前出现）

|组件/公告|实际证据及结论|最小闭合动作|
|---|---|---|
|CPython3.12.16安全发行|Python.org 2026-10-25明确列出eMudhra/Expat/mimetypes/tarfile及另3项安全修复；当前是14日构建3.12.15。不是因版本较旧就推断漏洞。|验证已固定来源的3.12.16派生候选，或逐项出具回补/适用性证据；不能直接替换当前已测runtime。|
|CVE-2026-115557 eMudhra|官方说明ssl新增拒绝已泄露公钥。当前_ssl.pyd身份已记录、构建早于21日补丁，未见回补凭据。OpenSSL3.5.9并不自动提供该CPython denylist；certifi已更新也不能证明所有平台/捆绑信任库统一修复。|核发行补丁/denylist或完整信任链处置证据。当前为明确安全闭合阻断；未主动连恶意服务器，未证明实际可利用。|
|Expat CVE-2026-77214|当前pyexpat报2.8.5；上游2.9.0明确修复XML_ParseBuffer的len容量校验。上游PR要求调用方提供超过内部容量的len。尚未核CPython绑定是否允许不可信输入触发该违反C API契约的条件。|证明所用绑定及其调用链不满足触发条件，或验证包含修复的新runtime。此项不能报“XML输入已证远程越界”。|
|Expat CVE-2026-102633|上游明确仅32bit expat_realloc整数溢出，当前AMD64。|对当前Windows64位profile排除此条；不能外推32位目标。|
|CVE-2024-3220 Windows mimetypes|实际Lib/mimetypes.py init(files=None)仍files=knownfiles，再遍历本地文件；与官方issue描述的Windows用户可写knownfiles问题相符。|runtime修复或完整调用方初始化/路径权限证据。未核整个产品可达性，不能声称所有API受影响。|
|CVE-2026-114583 tarfile|官方描述tar_filter链接替换目标。publication恢复手工检查dir/regular再extractfile；legacy备份使用filter=data。不能将tar_filter标题直接套为data_filter可利用。|核对应3.12补丁与data_filter复用关系，必要时最小隔离反例；本轮不执行恶意归档或新增测试。|
|其余CPython安全条目|header refolding、TemporaryDirectory cleanup race、负cookie version：官方发行页列有修复，当前是否回补/可达未知。|采用已验证修复runtime，或定点适用性评审；不无限扩大为所有stdlib审计。|
|SQLite3.54.1新增heap overflow|SQLite官方news及changes明确仅32位，64位不受影响；当前3.54.0 AMD64。SQLite表中11822/11824在3.53.2已修。|上述具体公告对当前profile排除；不把“有3.54.1”当成当前存在漏洞。其余3.54.1未分类fix不作全安全结论。|
|OpenSSL3.5.9|官方3.5公告页最新列CVE-2026-35189的受影响范围before3.5.9，当前不落入该范围。|仅关闭该具体版本区间条目；不把它当全部TLS或eMudhra处置证明。|

## 数值/模型原生边界

- NumPy实际build config为scipy-openblas0.3.34.106.0（ILP64）。DLL ed4f167a... 与旧existing-numpy-build.json相同；msvcp140-a4c222...也相同。旧证据可用于身份关联，不能当新公告全面审结。
- OpenBLAS官方安全政策指出CVE-2021-4048涉及0.3.18之前；当前NumPy0.3.34系列不落入该区间。官方公开advisory列表为空只能说明该渠道未发布条目。不能由此断言所有BLAS/LAPACK或CRT无漏洞。
- **SciPy1.18.1自己的__config__.py为另一个OpenBLAS0.3.31.dev**，DLL libscipy_openblas-197ee2fc9b4d071f7e048078cac74115.dll。不是NumPy的0.3.34.106.0；尚缺该dev构建精确来源commit/补丁及公告映射。旧NumPy证明不可覆盖此组件。
- torch/version.py表明2.14.0+cpu，git_version08187d9e0fba026dc8217405802ab5381dc88d90，cuda/hip/rocm/xpu均None。torch/lib有torch_cpu/c10/libiomp5md/uv等DLL。此轮未导入Torch，无精确实际加载闭包或静态库SBOM；MKL/oneDNN等静态依赖不能凭DLL目录有无排除。
- Intel libiomp5md：FileVersion20260213，ProductVersion5.0；不足以与oneAPI产品公告逐一映射。NumPy msvcp140版本14.40.33810.0；sklearn/.libs里的msvcp140及vcomp140为14.51.36247.0；应分别记录，不能以一份系统VC运行库覆盖wheel私带DLL。
- 官方PyTorch GHSA-2rj9-7h5r-q4h8（libuv）受影响<=2.8.0，修2.9.0；GHSA-63cw-57p8-fm3p受影响<=2.9.1，修>=2.10.0；GHSA-g6v3-crfc-cggj受影响<2.1.0。当前2.14.0不在这三条区间内，仅关闭这三条，不证明uv.dll自身新公告、全部CPU native或模型解析器全审。
- safetensors0.8.0/tokenizers0.23.2/SentenceTransformers6.0.1仅核安装metadata；本轮没有它们的原生SBOM/静态依赖映射。Cargo桥audit只审桥自己的锁，不覆盖这些轮子。

## 最小剩余清单与交接

1. CPython3.12.16安全补丁闭合（优先eMudhra、实际Expat、Windows mimetypes）；补丁存在与项目可达性分别记录。新runtime只能先独立MVP再整链重验，不能沿用旧runtime全量2157作为新runtime证据。
2. SciPy独立OpenBLAS dev来源/补丁、Torch CPU静态组件与libiomp/uv身份、wheel私带CRT及模型native解析依赖的有界SBOM和公告映射；明确固定模型执行所需闭包，不扫描整个Python生态。
3. Linux隔离profile及最终容器的实际runtime/native另行验证；本报告仅Windows。默认compatibility_not_approved继续关闭。

已证可排除的是具体公告范围，不是全安全；未发现足以宣称项目已可远程利用的新增实证。已发现足以阻止“完整原生安全审查通过”的具体未闭合安全补丁和原生构建身份缺口。需root回流权威设计/记忆，本子任务按只写私有目录约束未编辑memory。

## 权威原始来源

- [Python3.12.16安全发行](https://www.python.org/downloads/release/python-31216/)
- [CPython eMudhra issue](https://github.com/python/cpython/issues/160040)
- [CPython mimetypes issue](https://github.com/python/cpython/issues/159428)
- [CPython tar_filter issue](https://github.com/python/cpython/issues/160097)
- [Expat2.9.0 Changes](https://github.com/libexpat/libexpat/blob/R_2_9_0/expat/Changes)
- [Expat77214上游修复与调用条件](https://github.com/libexpat/libexpat/pull/1393)
- [SQLite变更](https://www.sqlite.org/changes.html) / [SQLite公告表](https://www.sqlite.org/cves.html)
- [OpenSSL3.5公告](https://openssl-library.org/news/vulnerabilities-3.5/index.html)
- [OpenBLAS政策](https://github.com/OpenMathLib/OpenBLAS/blob/develop/SECURITY.md) / [公开公告](https://github.com/OpenMathLib/OpenBLAS/security/advisories)
- [PyTorch libuv](https://github.com/pytorch/pytorch/security/advisories/GHSA-2rj9-7h5r-q4h8)
- [PyTorch checkpoint](https://github.com/pytorch/pytorch/security/advisories/GHSA-63cw-57p8-fm3p)
- [PyTorch flatbuffer](https://github.com/pytorch/pytorch/security/advisories/GHSA-g6v3-crfc-cggj)

来源由平台web工具直接检索/打开；未把搜索摘要或第三方漏洞聚合页当最终证据。两个猜测的scipy-openblas GitHub地址不可取回，未据此下结论。rg首次几个不存在路径glob失败已改为backend范围定点检索，不是验收测试失败。所有产品功能验证由root独立记录，本轮不宣称测试通过。

## 28日追加：固定候选取得路径（只读，未安装）

Windows可信候选来自[PBS immutable release20261026的官方资产元数据](https://github.com/astral-sh/python-build-standalone/releases/expanded_assets/20261026)，发行说明明确将3.12.15升级3.12.16。该tag源码入口为https://github.com/astral-sh/python-build-standalone/tree/20261026 ，release显示提交前缀fa506e0。本次未取full源码/实际构建manifest，不能宣称可复现构建。

|资产名|官方SHA256|
|---|---|
|cpython-3.12.16+20261026-x86_64-pc-windows-msvc-install_only_stripped.tar.gz|1f2ab53880fc67ea323398c6388e05af28addc99a8e389209f08a51fdff4b149|
|cpython-3.12.16+20261026-x86_64-pc-windows-msvc-install_only.tar.gz|590dfcbe3a34c07301e6332e13e2188b98655cd072b08afa45a7998dc4c22bc5|
|cpython-3.12.16+20261026-x86_64-pc-windows-msvc-pgo-full.tar.zst|37b4eb2818fee605fefa75ed156c4f2e1aaeaebaf662f9b30177c842ee16c48f|

精确下载URL为`https://github.com/astral-sh/python-build-standalone/releases/download/20261026/`加上上述资产名（+可编码%2B）。后续仅向新隔离目录下载，对官方release资产digest比对，解析full包PYTHON.json/native依赖，再用install_only候选实测stdlib/实际Expat/OpenSSL/SQLite。3.12.16核心源码改变不保证PBS外部Expat链接已经更新：应专门看实际pyexpat版本或回补，而不能只查sys.version。SQLite应先观察候选自带版本，满足3.54.0及逐连接硬化后再判断是否仍需既有DLL派生配方，禁止盲目叠补丁。

Linux官方候选：`docker.io/library/python:3.12.16-slim-trixie`。官方[tags源码映射](https://raw.githubusercontent.com/docker-library/official-images/master/library/python)指定docker-library/python的GitCommit `3d7e95597e56a415d9e4abc0f15877e005d2cb2e`，目录`3.12/slim-trixie`；[固定Dockerfile](https://raw.githubusercontent.com/docker-library/python/3d7e95597e56a415d9e4abc0f15877e005d2cb2e/3.12/slim-trixie/Dockerfile)可读。候选镜像已发布不等于本机具备受验可重建profile；镜像本身SQLite及系统Expat等仍须实测。官方CPython[3.12.16 source](https://www.python.org/ftp/python/3.12.16/Python-3.12.16.tar.xz) SHA256=`b5796915dc45ff745cfb4e990a7e7c93d6f546328a102ce31448d69ebc37575c`。

未取得可信镜像完整digest：`docker buildx imagetools inspect python:3.12.16-slim-trixie` exit1（本地buildx .lock读写权限拒绝）；`docker manifest inspect --verbose python:3.12.16-slim-trixie` exit1（受限网络代理127.0.0.1:9拒绝）。不凭短digest或标签伪造。后续在已有合法网络环境执行这两个只读metadata命令，保存manifest-list digest、linux/amd64子manifest digest及raw JSON，固定`python@sha256:...`；不得只固定tag，源映射commit也不能替代镜像digest。未通过其他目录或清Git/代理配置绕过本限制。

本轮只确认候选可在官方源定位，**未证明本机已有3.12.16重建profile**，没有下载/解包/运行新候选。旧3.12.15派生profile不能自动批准新版本。官方release资产metadata未以本地原始JSON落盘，hash为web页面所列值，实际下载必须再通过官方API/资产页面元数据交叉核验并校验文件。

## Root最终候选选择接续

Windows stripped精确链接（官方页面asset160 href，web点击回显精确地址但二进制cache miss，未下载）：https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.12.16%2B20261026-x86_64-pc-windows-msvc-install_only_stripped.tar.gz 。已保存`pbs-expanded-assets-excerpt.txt`，SHA256=`45e156ff00e5b368cb517edaaa184e3d657650993a06faf57a2f3c319d624d4d`；明确为平台web页面的派生摘录，非原始HTTP完整响应。候选包SHA与摘录文件SHA是两种不同对象。

按root后续决策，Linux**优先`python:3.12.16-slim-bookworm`**复用已测ABI；官方tags映射确认此tag存在、支持amd64，GitCommit同为`3d7e95597e56a415d9e4abc0f15877e005d2cb2e`，目录`3.12/slim-bookworm`，固定源码URL为https://raw.githubusercontent.com/docker-library/python/3d7e95597e56a415d9e4abc0f15877e005d2cb2e/3.12/slim-bookworm/Dockerfile 。前述trixie只为已确认存在的额外候选，不是建议变更发行版。根将通过获准docker pull取得daemon digest，本agent不再尝试客户端权限操作。
