# 原始构建命令补充记录（事后整理）

本补充晚于构建执行，依据本对话保留的`functions.exec → tools.exec_command`实际调用参数及完成结果整理，**不是当时同步生成的命令收据**。不修改原REPORT.md、evidence-manifest.json、源码、vendor、target或任何批准状态。对应机器记录见同名JSON。

原调用的Docker argv精确如下（每行只是便于阅读的分隔，JSON中逐参数保存）：

```text
docker run --rm --network none --cpus=1 --memory=512m
  --env CARGO_HOME=/cargo-home
  --env CARGO_TARGET_DIR=/target-linux
  --mount type=bind,source=D:/graghRAG-agent/.tmp/linux-vector-bridge-20261028/source,target=/source,readonly
  --mount type=bind,source=D:/graghRAG-agent/.tmp/linux-vector-bridge-20261028/cargo-home,target=/cargo-home
  --mount type=bind,source=D:/graghRAG-agent/.tmp/linux-vector-bridge-20261028/vendor,target=/vendor,readonly
  --mount type=bind,source=D:/graghRAG-agent/.tmp/linux-vector-bridge-20261028/target-linux,target=/target-linux
  --workdir /source
  rust@sha256:a86cada82e36ebd7a9bffed7548792c55a952fdb20718eea9278a936bcb76e62
  cargo +1.94.0 build --offline --locked --release --jobs 1 --target x86_64-unknown-linux-gnu
```

因此四份源只读于`/source`，vendor只读于`/vendor`，Cargo home和编译目标分别仅写本任务私有目录。私有`cargo-home/config.toml`是实际`cargo vendor`输出的directory source replacement，directory=`/vendor`，并追加`[net] offline=true`。`--network none`由Docker隔离网络，`--offline/--locked`由Cargo同时约束。没有传入RUSTFLAGS；实际release fingerprints另记录`rustflags=[]`。镜像自身的PATH、RUSTUP_HOME等默认环境由固定digest和`rust-image-inspect.json`绑定，不把它们误称Docker CLI额外传入参数。

原PowerShell在执行前创建本任务target-linux目录，标准输出与标准错误经`*>`写入`linux-release-build.log`，捕获`$LASTEXITCODE`到`linux-release-build.exit`并以同码退出。实际completion报告exit0，日志为release25.23秒；最终binary SHA256为`20d2166cd218fdd0dff2914939c07e400fa38231f06139b91689ee45279418d0`。这些绑定由原工具调用、build log、最终fingerprints及CLI receipt交叉支持；构建的精确开始UTC未在当时单独持久化，不补造时间戳。

工具记录定位：外层exec返回running cell10；实际编译`exec_command`返回session17830；后续write_stdin完成输出chunk`ba68f8`，exit0。上述标识用于定位当前会话记录，不视为独立签名或持久外部证明。

若评审者需要重新确认实际编译，应自行分配**新的空目标目录**，保持相同四源/vendor只读、同Cargo私有配置和同固定Rust镜像，将该空目录映射到`/target-linux`后运行相同Cargo argv，再记录自己的命令/退出码和binary摘要。直接在旧target-linux运行可能仅得到Fresh，不是独立干净重建。本补充没有请求或执行新构建/测试；是否重建由独立评审者决定。
