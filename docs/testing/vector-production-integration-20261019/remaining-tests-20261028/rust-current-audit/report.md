# 当日Rust数值桥审计 — 2026-10-28

有限范围结论：当前实际数值桥锁（11 registry crates＋root）使用28日实际获取的官方RustSec DB，**已知公告0、warnings0**。**正常yanked检查未通过，不能称完整Cargo安全验收通过**。

锁SHA：4029ef11d930d910cf4e403134d8f0ade519c144b43eee54fc7ee93cbd880018，执行前后相同。工具cargo-audit0.22.2 SHA0157f5ce1ce9fd4fb0a1f7c79af1229771d1f80b6c2613ddb0d9200a8ba73946。旧工具/旧DB只读，新独立CARGO_HOME及DB在本目录，无全局Git/Cargo配置变更。

新DB从旧目录本地独立clone（--no-hardlinks），仅在新副本将origin设官方https://github.com/RustSec/advisory-db.git。受限fetch因代理拒绝exit128保留；正常获准网络fetch成功exit0，FETCH_HEAD固定99670cfc0bc574433034b75876a4b791ccaa2efb，commit时间2026-10-27T11:02:42+01:00；detached checkout，执行前后git status --porcelain均空。比旧25日21d909e...更新，非把旧DB重命名当新。DB当前1380条。平台web commits页面缓存停9月不用于证明当日HEAD，实际官方Git fetch是本报告freshness依据。

正常命令为`cargo-audit.exe audit --file <当前C锁> --db <本目录DB> --no-fetch --json --deny warnings`。受限及获准网络两次都exit0/JSON漏洞0 warnings{}，但stderr均有11条couldn't check if package is yanked / No such crate in crates.io index。这是工具局限，不能把exit0当yanked通过。

为正常获取索引，新目录registry-seed-crate复制原Cargo.toml/Cargo.lock，只加空main满足Cargo manifest，用独立CARGO_HOME执行`cargo fetch --locked --manifest-path <副本Cargo.toml>`，无编译。官方crates.io只停Updating index超过103秒。仅自有cargo进程用PID、可执行路径、启动时间三项核对后终止，原fetch退出-1；受限Stop-Process access denied后使用原网络权限终止。无外部测试/编译任务被停，未修改全局代理/SSL。registry-seed-timeout.txt记录真实终止；未宣称下载成功。

随后实际有限命令为`cargo-audit.exe audit --file <当前C锁> --db <本目录DB> --no-fetch --no-yanked --json --deny warnings`，exit0、stderr空、依赖12、漏洞0、warnings0，原始JSON/exit/log均保留。本命令明确跳过yanked，仅证明当日DB的RustSec公告/信息告警扫描。报告receipt把完整检查full_yanked_acceptance=false。

下一步仅需在正常官方crates.io索引可用时补11项yanked，再执行同锁同DB命令并同时检查stderr；不重编或改锁来制造成功。该结果不覆盖CPython、SQLite、OpenBLAS/CRT、Torch/libuv、tokenizers/safetensors内部全部native，也不开放compatibility_not_approved。

原报告与归档未修改，无C源码/测试/配置/锁/运行库改动，无commit/push/部署/迁移。详见receipt.json及本目录原始工件。
