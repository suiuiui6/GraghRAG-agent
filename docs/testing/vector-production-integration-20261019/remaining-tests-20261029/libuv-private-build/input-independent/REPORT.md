# Windows libuv 阶段 A 独立输入审（完成）

2026-10-29。独立上下文，读取项目 AGENTS、memory/index、设计评审及 requesting-code-review 技能。本目录为唯一写入范围，无编译、DLL加载、runtime/C/R11修改。

已实际验证：作者 REPORT SHA256 30bc4f07ceed13da3fee1fcdf9878c9b2b92f4deab10af75624a1c756bc42be8 及 evidence-manifest 70文件全部size/SHA匹配；libuv1.53.0 tar为1391596B/SHA cb0d6dd2128d5a95bd242c6cc982a24fe608fa93da57b6b4ec763b0018c53e64。536成员无link/路径穿越，6源码切片与tar逐hash一致。官方发行页固定commit840404ce8ba7cc0204be52389a6cfff9f2c90fb6，MAINTAINERS关联维护者与完整primary fingerprint一致。

全新owned GNUPGHOME 实际导入 maintainer-current.gpg.asc、fingerprint和detached verify均exit0；GOODSIG/VALIDSIG 612F0EAD9401622379DF4402F28C3C8DA33C03BE，无EXPKEYSIG/KEYEXPIRED，公开key自签到期1908982478。TRUST_UNDEFINED未冒充web-of-trust；身份依据仍是官方MAINTAINERS完整指纹+维护者官方账户同key。历史2017过期key结果保留且不当通过。本次首次MSYS反斜线路径失败保留 import-initial.stderr，规范化路径后重验通过；未读取用户私钥/.env。

三份实际InRelease、Packages.lz4 SHA与lock匹配；签名正文中的原始Packages SHA/size引用匹配lock；27包精确URL、版本集合、80210796B与作者APT模拟相符。27实际deb已独立逐包hash/size全匹配，见static-receipt.json。该静态检查不冒称独立实际重跑签名或依赖求解。

独立工具重跑已完成：fixed builder sha256:cd48c100f4e8c0297c2e1a558b7a93d95e41f79ba4f58d5f7d938a71192dff23，network-none/read-only/nonroot1000/capdropALL/no-new-privileges，实际三gpgv均exit0。每份Packages.lz4实际解压后逐SHA/size匹配签名InRelease；27包全部字段（版本、架构、Filename、Size、SHA256、Depends、Pre-Depends、Source、Installed-Size）与原始索引一致，snapshot URL精确匹配。独立APT模拟exit0，27新增/0升级/0删除，精确包版本集合与lock一致。完整dpkg基线和gpgv输出保存在tools.stdout.json，实际argv/exit见tools-run.json。

失败完整保留：初次Docker daemon缺失见tools-run-initial.json/tools-initial.stderr；恢复后只读根文件系统导致APT无法在/tmp创建clearsigned临时文件（exit100），见tools-readonly-tmp.stderr。仅添加内存tmpfs /tmp:rw,nosuid,nodev,size=128m后重跑exit0。宿主输入仍只读、禁网，无安装/编译。该修正是执行环境需要，不降低签名或依赖门槛。

x86_64-w64-mingw32-gcc-win32 显式AMD64/win32线程模型与方案相容；win32不证明MSVC ABI/CRT等价，实际额外依赖须B/C门检查。工具libuv1 Debian回补版与拟部署Windows源码身份分开；未完成工具许可与安全适用性核验，不宣称工具零漏洞。

当前结论：A中所委派的源码、固定builder/工具闭包输入审核通过；工具实际字节门27/27通过。即使A通过也仅输入通过，不等于交叉ABI通过、正式替换或生产批准。源码/工具身份成功不能代替后续Windows真实消费者和完整验收。未提交/推送/发布/部署。

验证命令：python verify_source.py（正常平台审批）、python verify_static.py、python run_tools.py（正常平台审批）；最终三命令均exit0。源签名与工具链是本次独立实际验证，报告不是仅parse作者status。全项目测试/覆盖率/漏洞与许可全审未执行，本报告不授予Git提交或生产准入；最终证据清单见manifest.json。
