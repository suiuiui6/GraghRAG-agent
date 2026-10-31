# Linux numeric bridge isolated MVP — 2026-10-28

结论：**同四份原始源码的Linux数值桥候选已完成锁定离线构建，并在已审运行库中通过30项原始CLI I/O。** 这只是候选MVP，不是正式包批准、全域兼容证明或生产激活。本目录未创建任何approved=true，没有改C生产树、正式Windows build.py、生产gate、真实.env、现有卷或项目服务；上一runtime证据目录保持冻结未写。

## 固定输入

官方Rust镜像经独立inspect核实Linux/amd64：`rust@sha256:a86cada82e36ebd7a9bffed7548792c55a952fdb20718eea9278a936bcb76e62`。实际工具：

- rustc1.94.0，commit `4a4ef493e3a1488c6e321570238084b38948f6db`，LLVM21.1.8，host/target `x86_64-unknown-linux-gnu`。
- Cargo1.94.0，commit `85eff7c80277b57f78b11e28d14154ab12fcf643`。
- 系统cc GCC12.2.0-14+deb12u1，GNU ld2.40；工具探针1–5的实际命令均exit0，OS包清单在`rust-toolchain-probe-5.log`。
- rustc/Cargo/cc/as/ld实际ELF SHA在`build-tool-elf-sha256.txt`，目标Rust std/sysroot库逐文件SHA在`rust-std-target-file-sha256.txt`。这些是固定镜像和实际文件身份，不声称全部原生组件安全已审。

四源构建前后完全不变（`source-before.json`、`source-after.json`及最终build identity核验）：

| 文件 | SHA256 |
|---|---|
| Cargo.toml | `02105d1df940431d92ff91bb536eb65aee8e2ba3a7fc19f21e9e0ee624842c2c` |
| Cargo.lock | `4029ef11d930d910cf4e403134d8f0ade519c144b43eee54fc7ee93cbd880018` |
| rust-toolchain.toml | `4cb550734bd94d0591c8a84b561c654dd58ddc3b0d67464c2ddeb2962a4cd826` |
| src/main.rs | `eee79631cc3e7ee8acd2d48485be9a811374d7d04426a49f1368e7b260f65dfe` |

## 依赖原件与vendor

Cargo.lock的11个registry crate全部按官方checksum验证，未换版本或features。6个原件来自现有正确缓存；缺失proc-macro2、quote、serde、serde_derive、unicode-ident通过rsproxy取得，逐SHA匹配后才写入本任务私有Cargo缓存。`all-crate-receipt.json`及各`crate-*.receipt.json`保留官方原件URL、传输/重定向URL、时间、bytes和摘要；镜像只作传输，Cargo.lock的官方registry checksum仍是来源权威。

没有改全局Cargo/git配置；只复制需要的公开crate和sparse索引缓存到本目录的`cargo-home/`。根先前host offline缺包和online timeout exit101日志保留，不抹去失败。

真实命令在固定Rust镜像、断网、1CPU/512MB执行，`/source`为只读四源、`CARGO_HOME=/cargo-home`为本任务私有挂载：

`cargo +1.94.0 vendor --locked --offline /vendor`

`vendor-linux.exit=0`。随后独立验证每个`.crate`完整checksum、每个vendor的`.cargo-checksum.json` package checksum及447个文件SHA，`vendor-integrity.exit=0`。实际vendor输出的source replacement配置仅写入私有`cargo-home/config.toml`，追加`[net] offline=true`；build时vendor挂载只读。

## features与构建

`cargo +1.94.0 tree --locked --offline --target x86_64-unknown-linux-gnu -e features` exit0，保持根依赖请求`serde_json/std`、`zmij/default`，无float_roundtrip/arbitrary_precision。metadata原件另保留，不能把其完整resolved graph等同某次release实际cfg。

实际编译用固定Rust镜像、`--network none --cpus=1 --memory=512m`，源码和vendor只读，`CARGO_TARGET_DIR=/target-linux`仅挂本目录的target-linux：

`cargo +1.94.0 build --offline --locked --release --jobs 1 --target x86_64-unknown-linux-gnu`

`linux-release-build.exit=0`，日志报告25.23秒。候选位于`target-linux/x86_64-unknown-linux-gnu/release/vector-numeric-bridge`，SHA256：

`20d2166cd218fdd0dff2914939c07e400fa38231f06139b91689ee45279418d0`

补充核对中曾出现一次**检查脚本自身的假设错误**：我要求Zmij resolved features包含命名default，命令exit1。保留`metadata-assertion-initial-failure.json`；这不是构建或CLI失败，也没有改依赖制造通过。按systematic-debugging核实锁定Cargo.toml、metadata与实际release fingerprint后发现：Zmij未声明`[features] default`，tree显示的默认请求可对应空实际feature集合。更正核对对象后，`build-identity-verify.exit=0`，实际release fingerprints：serde_json仅std、serde_core仅std、Zmij空集合，各rustflags均空；binary SHA与30项CLI报告一致。原metadata中serde_core还列result，实际release fingerprint仅std，报告分别保留，避免把更宽metadata图冒称实际编译cfg。

源依据：锁定`vendor/zmij/Cargo.toml`、三个实际release `lib-*.json`、`feature-tree.log`及[Cargo官方features文档](https://doc.rust-lang.org/cargo/reference/features.html)；文档说明具名feature在包中声明、默认请求及tree的检查方式。本次未为了检查方便修改任何源/锁/feature。

## 原始CLI真实I/O

最终测试运行于上一轮已独立审查的immutable组合runtime实际ID：`sha256:ca19e0667a83656165ad4c7edd07ef50b97429fa7aa5932453dac1dc4c16ebe1`（Python3.12.16、SQLite3.54.0、NumPy2.5.4）。只读rootfs、断网、1CPU/512MB、uid65534，候选目录只读bind到`/candidate`，仅本新目录可写证据。

`python -B /evidence/test_candidate_cli.py`实际exit0（`cli-mvp.exit`），每一候选进程`subprocess.run(timeout=3)`、清空环境、固定候选路径；`cli-mvp-receipt.json`逐项保存原始ASCII输入、预期与实际stdout、stderr、exit和时间。30项全部精确匹配，全部stderr空、protocol响应≤64bytes，包括：

- record_i64零、I64上下端点精确恒等、超端点及非规范零拒绝。
- record_f64以精确bits输入正/负零、±1、最小正/负次正规、最大有限值；保留已知formatter反例`43dfffffffffffff → 43e0000000000000`，不是假设parse(format(f))全域恒等。Inf/NaN明确invalid_input。
- where负零、整数正/负1、I64正端点的raw U64分类、I64负端点、U64上端、超U64和低于I64的有限f64转换；非有限JSON、非number、坏operation及额外tab拒绝。

**原始桥与Python门面边界分开：** raw record_f64负零输出仍是`8000000000000000`，正式Python门面在SQLite兼容入口另外将浮点负零规范为正零；本MVP没有加载/绕过`_verified_binary()`或把raw CLI当作门面已批准。正整数raw where U64结果也不直接等同后续应用guard结论。

## ELF与运行库边界

`binary-elf-1..4.txt/.exit`记录readelf头、动态段、版本需求和program headers，四命令均exit0；ELF x86_64，解释器`/lib64/ld-linux-x86-64.so.2`，声明NEEDED为libgcc_s.so.1、libc.so.6和loader，版本需求最高出现GLIBC2.34。实际runtime的ldd exit0且无缺失库，30个独立进程正常执行，说明**所测固定bookworm runtime**可运行此候选；不外推任意Linux、musl、arm64或不同glibc。

未执行：正式Linux构建/安装配方设计及独立批准、Linux原始Chroma wheel来源/完整feature归因、Python包身份批准机制、全量adapter/消费者/生命周期、完整native SBOM与公告适用性、正式模型/CPU-CUDA选择、生产激活/迁移/发布。没有创建批准manifest，所有报告明确candidate_only/approved=false。

下一步由根安排独立MVP复核与正式Linux构建配方设计，再按同快照准入流程决定后续；不得仅凭这30项或本候选来源身份开放生产gate。
