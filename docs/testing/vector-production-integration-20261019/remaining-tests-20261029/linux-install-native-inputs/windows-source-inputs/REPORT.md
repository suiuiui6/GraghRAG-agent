# Windows libuv 交叉构建MVP — 阶段A输入准备（未构建）

依据独立设计评审 `.tmp/windows-libuv-mvp-design-review-20261029/REPORT.md` 条件继续，仅源身份、固定builder能力与工具闭包。**源身份/签名已核验，27包工具闭包已锁定；工具未下载/安装、未编译/加载Windows DLL、未创建派生runtime。** 原C/R11/source/gate/default保持未改。

## 1. libuv源与签名

- 官方发行页 `https://github.com/libuv/libuv/releases/tag/v1.53.0` 对应精确commit **840404ce8ba7cc0204be52389a6cfff9f2c90fb6**，保存完整发行页；不是浮动main。
- 官方 `https://dist.libuv.org/dist/v1.53.0/libuv-v1.53.0.tar.gz` 实得 **1,391,596字节**，SHA256 **cb0d6dd2128d5a95bd242c6cc982a24fe608fa93da57b6b4ec763b0018c53e64**；detached `.sign`833字节/SHA65ca5d646db151e403d9271202c609ff72c41781285bae310e635a90f7e28d08。
- v1.53.0官方MAINTAINERS列Santiago Gimeno完整指纹 **612F0EAD9401622379DF4402F28C3C8DA33C03BE**。官方公钥tag经GitHub ref→annotated tag→blob取得，blob f1beee0c8b030aec9c2863ebf884f8eb88d9ed6c；该历史2016自签已2017过期，尽管GPG exit0+VALIDSIG同时EXPKEYSIG，**未当通过**。
- 同官方MAINTAINERS关联维护者账户`https://github.com/santigimeno.gpg`取得更新公钥3174字节，SHA62c4bd6637d1946edfbfacd924241c96c24764209bf0f65d5377a86e314ea479。相同完整primary fingerprint，自签有效期延至Unix1908982478；导入同隔离keyring后detached验证 **exit0、GOODSIG、VALIDSIG完整指纹、无EXPKEYSIG/KEYEXPIRED**。TRUST_UNDEFINED代表未设置GPG web-of-trust，身份锚是官方MAINTAINERS完整fingerprint+官方维护者同key，不是把短key当信任或任意keyserver接受。
- 原tar536条成员，无绝对/..路径和links；只读取6个必要源/许可文件，不执行脚本/hook；version.h确认1.53.0，ChangeLog1023行包含GHSA-f74f-cvh7-c6q6修补记录。此公告修复下限1.48.0；当前官方已列公告依据由父任务核查，本轮只确认此具体修补包含，不宣称全部native安全清零。

## 2. 固定builder能力及APT签名链

固定builder **sha256:cd48c100f4e8c0297c2e1a558b7a93d95e41f79ba4f58d5f7d938a71192dff23**，network-none/read-only/nonroot1000/capdropALL/no-new-privileges只读预检。实际cmake/make/MinGW编译器均不存在；gpgv/apt-get/dpkg-deb存在。原builder不改。

复用已有 `linux-runtime-mvp-20261027/apt-lists` 及 `debian.sources`，snapshot **20261020T213255Z**，bookworm/main、updates、security。重新实际gpgv核三份InRelease均exit0；每个现有Packages.lz4用apt-helper解压，**未压缩SHA及Size逐项匹配签名InRelease的main/binary-amd64/Packages**。tools-closure.lock.json记录release本身SHA、lz4SHA、原始索引SHA/bytes、完整签名输出及每包Filename/版本/架构/Size/SHA256/Depends/Pre-Depends/Source/Installed-Size/精确snapshot URL；不是仅固定URL。

初次source挂载命名`/sources`导致APT将deb822误作传统格式，simulate exit100保留；修正只读target `/sources.sources` 后同配置simulate **exit0**。--no-install-recommends相对builder当前完整dpkg状态**27新包、0升级/0删除**，完整传递闭包由APT求解不是手挑几个编译器包。

## 3. 新增工具闭包及下载量（仅计划）

精确27包全记录在tools-closure.lock.json；主要工具：

- gcc-mingw-w64-x86-64-win32、其runtime及base：**12.2.0-14+deb12u1+25.2+b1**
- binutils-mingw-w64-x86-64：**2.40-2+10.4**
- mingw-w64-common/x86-64-dev：**10.0.0-3**
- cmake/cmake-data：**3.25.1-1**；make **4.3-4.1**
- 其余APT运行依赖libarchive/brotli/curl/expat/icu/jsoncpp/ldap/nghttp2/proc/psl/rhash/rtmp/sasl/ssh2/libuv1/xml2/procps皆在锁内，不漏分母。

预计deb净下载 **80,210,796字节（约76.50MiB）**，包声明Installed-Size合计 **436,363KiB**，不是实测安装空间。本轮工具deb下载量0。构建工具内libuv1 **1.44.2-1+deb12u1**是Debian回补发行身份，不等于未回补1.44.2，也不是拟部署WindowsDLL；其许可和当前已知漏洞尚需独立适用性核对，整个工具闭包不能宣称零漏洞。许可源与原DebianSource字段已定位，未下载deb版权文本或伪称已审。

Target明确 **x86_64-w64-mingw32，win32线程模型**，后续直接指定`x86_64-w64-mingw32-gcc-win32`而非自动alternatives。libuv自己Windows线程API不要求POSIX工具变体；CRT默认及额外runtime依赖仍要从实际编译结果验证，不把win32线程名等同MSVC。CMaketoolchain需固定Windows/AMD64、编译/资源工具绝对路径、Release、LIBUV_BUILD_SHARED=ON、BUILD_TESTING=ON及共享/测试同源配置；所有flags将随B计划明确，当前未编造编译命令通过。

## 4. 停止点及下一步

阶段A此输入准备已可供独立核：源tar/签名/fingerprint、三份索引签名→原始Packages→27deb SHA及实际builder dpkg基线完整。**还未取得/验证27工具deb字节、未安装新独立builder、未编译/检查ABI，故B尚未执行。** 先独立审核这些输入与工具适用性，再有界取锁定80.21MBdeb，逐个大小/SHA及包元数据核对，在全新独立镜像/路径离线安装。不得宿主apt或修改旧image。

后续B只有构建；288exports/25imports、ordinal/forwarder/delayimports、旧MSVC结构ABI来源及真实Windows线程/TCPStore消费者由后续门逐项验证。跨编译README本来标unsupported，不能跳过。原R11历史通过只证明未修改原runtime，不证明新候选。未来采用内部派生发行/正式长期维护责任需具体证据后另行产品决定，现不请求抽象二选一。

## 5. 失败及证据完整性

保留raw key两个404、Git抓公钥tag30秒timeout（实际subprocess清理44.79秒）、GPG sandbox MSYS命名对象拒绝、第一次绝对Windows路径不被MSYS识别、旧公钥EXPKEYSIG、首轮APT配置扩展名错误、首次源静态检查GBK解码失败；成功只依最终receipt，不将执行器exit0冒充每步成功。正常平台审批后运行相同权限路径，无ACL/安全配置修改。

所有输出仅本owned目录；公钥keyring含公开key而无私钥。没有密钥/Token/OSprocess CommandLine读取，没有对外联络/托管/发布/部署。原报告与18case Linux证据不修改。
