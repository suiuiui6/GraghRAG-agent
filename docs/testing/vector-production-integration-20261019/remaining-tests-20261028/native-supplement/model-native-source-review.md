# 模型数值 native 来源补充核对 — 2026-10-28

范围：现役Windows security-lock-patch-20261026 venv；只核SciPy/OpenBLAS、Torch CPU及tokenizers/safetensors。未改C工作树/环境/锁/gate；未下载候选运行库；未编译或加载模型/推理；不扩展全轮子生态。**本报告修正report.md中仅凭Torch版本排除私带libuv的过宽推断。**

## 实测与工件

`probe_model_native.py`通过父进程55秒硬上界执行，exit0，import计时12.0秒；只导NumPy/SciPy/Torch，OMP/MKL/OpenBLAS线程均1。结果保存`model-native-probe.json/.stdout/.stderr`。没有调用任何张量运算或模型。threadpoolctl仅记录其识别的线程池，不能当全部loaded-module闭包。

`probe_native_versions.py`调用SciPy OpenBLAS及Torch uv DLL各自的只读版本API，exit0/约0.69秒。`probe_parser_static.py`只读取tokenizers和safetensors两个pyd的hash与嵌入crate路径，exit0/约0.94秒；路径仅作身份线索，80条上界，不能当完整SBOM或所有启用features。

|组件|实测身份|来源进展与仍缺证据|
|---|---|---|
|SciPy|1.18.1；__config__与DLL导出scipy_openblas_get_config均报OpenBLAS0.3.31.dev；实际DLL SHA197ee2fc9b4d071f7e048078cac741151a6585d871061cf5f88c0c73e31963a5|不是NumPy的BLAS。官方v1.18.1 requirement精确钉scipy-openblas32==0.3.31.22.0，build脚本按该文件安装并vendoring DLL。|
|Torch|2.14.0+cpu，COMMIT_SHA08187d9e0fba026dc8217405802ab5381dc88d90，USE_CUDA=0/USE_MKL=ON/USE_MKLDNN=ON/USE_OPENMP=ON|实际config提供比目录枚举更准确的静态数值身份；官方同commit .gitmodules可定位ideep、tensorpipe、mimalloc等源码项目，但.gitmodules仅URL不是子模块精确gitlink或实际构建收据。|
|MKL|Intel oneAPI MKL2026.1 ProductBuild20260612|实测build身份足够定向查公告；本轮未取得实际发行包digest、所有静态组件清单或Intel公告逐项映射，不能称安全已验。|
|oneDNN|MKL-DNN3.12.0，git80afa71049cd69a3df32adcccb623b12cd7baa22|官方oneDNN对应commit可定位；身份显著收窄，实际wheel构建/链接证明及完整公告映射仍未取得。|
|libiomp|torch/lib/libiomp5md.dll，Windows资源FileVersion20260213/ProductVersion5.0；threadpoolctl实际识别，version null，线程1|缺Intel具体运行库发行/补丁标识，OpenMP2019是规范/编译配置而非安全补丁版本。不能以MKL2026.1代替libiomp的独立映射。|
|libuv|torch/lib/uv.dll导出uv_version_string=**1.40.0**，SHAfa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8|这份实际载荷未因Torch2.14就升级至1.48。无回补证据；不执行恶意DNS或网络PoC。|
|tokenizers|0.23.2；tokenizers.pyd SHA05848a2a85e1466d19242499ed6b8c016a886db79aca020792aa5598ded77ef9；字符串含pyo3.29.2、serde_json1.0.151|官方tag v0.23.2/commit前缀88a4498；Python bindings Cargo.lock及release workflow公开可得。PyPI该Windows wheel标Without provenance，缺artifact→实际build source/lock/features的可信绑定。|
|safetensors|0.8.0；_safetensors_rust.pyd SHA80a2b3f7658854ade855c5fb6192ee38fe2c7fbfd38d1c7c1f4d2c44f67125e4；字符串含pyo3.28.3、serde_json1.0.150、memmap2.9.10|官方迁至safetensors/safetensors，tag v0.8.0/commit前缀a406ca3。Python/core Cargo.toml公开可得；根及bindings/python两处Cargo.lock返回404，不能据此断言所有渠道均不存在。PyPI该Windows wheel标Without provenance。|

## SciPy/OpenBLAS来源链：已收窄，但不能伪称实物全绑定

[PyPI SciPy1.18.1](https://pypi.org/project/scipy/1.18.1/)给Windows cp312 wheel SHA=`5e4d44984abc0020154ea81b247adeddcc3ac5527b975ff798bd1ba0adc513c2`，并显示PyPI验证的publish attestation，发布workflow为scipy/scipy-release提交`f2dbbd50e96f2e0b78024ef271dd072a4a0636c6`。发布workflow取maintenance/1.18.x再检查tag；publish attestation证明发布身份，不能自动证明实际每个native build输入。

[固定SciPy requirement](https://raw.githubusercontent.com/scipy/scipy/v1.18.1/requirements/openblas.txt)钉0.3.31.22.0；[build脚本](https://raw.githubusercontent.com/scipy/scipy/v1.18.1/tools/wheels/cibw_before_build.sh)按该文件安装并拷贝DLL。安装DELVEWHEEL记录也指向scipy_openblas32/lib，形成一致性佐证。

[OpenBLAS build分发](https://pypi.org/project/scipy-openblas32/0.3.31.22.0/)的Windows wheel SHA=`c45f36fbfd6a20245c4a0dc18ef95ed4557e28089736c6aa51b40f8bb9a3405f`，明确Without provenance/非TrustedPublishing。固定MacPython/openblas-libs tag v0.3.31.22.0的[openblas_commit.txt](https://raw.githubusercontent.com/MacPython/openblas-libs/v0.3.31.22.0/openblas_commit.txt)=`v0.3.31-22-g5ffbf38b`，[github_commit.txt](https://raw.githubusercontent.com/MacPython/openblas-libs/v0.3.31.22.0/github_commit.txt)=`v0.3.30-392-g5aff62eb`。对应[OpenBLAS commit](https://github.com/OpenMathLib/OpenBLAS/commit/5ffbf38b)存在。

剩余缺口具体为：未取得并核对该build wheel内DLL和实际已安装SciPy DLL的逐字身份、构建时patch集合和锁定source链。现有git-describe不是完整原始build收据。版本来源已足以停止泛搜，不应继续称“所有OpenBLAS来源全未知”，也不能称native安全全审通过。

## libuv公告：必须重开当前载荷适用性

官方[GHSA-f74f-cvh7-c6q6 / CVE-2024-24806](https://github.com/libuv/libuv/security/advisories/GHSA-f74f-cvh7-c6q6)列受影响>=1.24.0、补丁1.48.0；明确涉及Windows uv_getaddrinfo对应实现。攻击需要不可信超长hostname进入该解析器，并结合调用方基于域名的安全检查/访问内部目标条件。**实际1.40.0落入未修版本区间**，但版本API不能排除发行方回补，且本轮未证明项目模型链向该函数传递用户hostname。

因此：这是具体**载荷补丁/可达性未闭合阻断**，不是已证项目SSRF。原report.md对Torch官方GHSA-2rj9-7h5r-q4h8的包范围比较仅能表达“PyTorch2.14不落上游所列旧torch版本”，不能用于排除实际uv.dll。root应核uv实际build/patch或证明对应路径不可达/移除不需要组件，再走隔离候选与受影响验收；不得随意原地替换DLL。

## parser边界与真正上游证据缺口

[Tokenizers bindings锁](https://raw.githubusercontent.com/huggingface/tokenizers/v0.23.2/bindings/python/Cargo.lock)可读；[release workflow](https://raw.githubusercontent.com/huggingface/tokenizers/v0.23.2/.github/workflows/python-release.yml)要求该lock存在。但PyPI[Windows wheel](https://pypi.org/project/tokenizers/0.23.2/)无provenance，tag当前锁不自动等于已安装wheel实际resolved/features。其core manifest默认onig/esaxx_fast，不能凭默认项就断言所有Windows构建feature。无新Cargo audit执行，不得借bridge audit0代替。

[Safetensors Python manifest](https://raw.githubusercontent.com/safetensors/safetensors/v0.8.0/bindings/python/Cargo.toml)及[core manifest](https://raw.githubusercontent.com/safetensors/safetensors/v0.8.0/safetensors/Cargo.toml)可读，实际pyd嵌入版本与声明范围一致；PyPI[0.8.0 Windows wheel](https://pypi.org/project/safetensors/0.8.0/)无provenance。缺该wheel真实lock/build graph；重新按现今semver解析一个新lock会制造新依赖图，不能称原wheel审计完成。

## 有界下一步

1. 当前1.40.0 uv.dll：优先核官方构建/补丁与项目调用可达性，这是本轮新增具体阻断。不要用包版本或pip扫描消掉组件证据。
2. SciPy：用已保存原轮子或已授权取得的官方wheel核DLL相等，并固定MacPython build tag/source与patch；不必再搜其他全部科学计算轮子。
3. Torch：已有MKL/oneDNN精确build身份，可做对应Intel/oneDNN定点公告映射；libiomp/uv回补及实际wheel链接/SBOM仍缺上游证据。没有找到证据不等于上游从未提供。
4. Parser：需要实际wheel可绑定的resolved graph/构建证明或自建锁定候选；当前仅有tag/manifest/static路径线索，不可声称“全原生安全清零”。

截至本报告未新证模型链远程可利用；明确阻断仍为具体已知公告的实际载荷适用性与构建证据未闭合。默认compatibility_not_approved保持。Windows316候选及Linux修订由root另行负责；本报告不改原metadata收据。
