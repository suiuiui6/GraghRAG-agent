# Rust精确版本yanked与checksum独立验证 — 2026-10-28

**11/11官方metadata验证通过**：全部精确版本yanked=false，crates.io返回checksum与当前Cargo.lock逐项相等。当前锁前后SHA均4029ef11d930d910cf4e403134d8f0ade519c144b43eee54fc7ee93cbd880018。执行33.984秒，11次curl全部exit0、无重试、stderr均空；独立重新读取全部原始JSON并复核SHA/锁/版本/返回值也exit0。

范围：itoa1.0.11、memchr2.7.4、proc-macro2 1.0.86、quote1.0.36、serde/serde_core/serde_derive1.0.228、serde_json1.0.149、syn2.0.82、unicode-ident1.0.12、zmij1.0.21。root本地package不属registry，无yanked字段。

来源严格为`https://crates.io/api/v1/crates/<name>/<version>`；正常HTTPS/TLS，未禁证书验证/切换镜像。各请求URL、UTC时间、实际command/exit/耗时及原JSON SHA在receipt.json；原始小JSON、HTTP headers和stderr分别保留。执行器限制每请求20秒、一次重试、总180秒，实际均首次成功。未下载或执行crate、未取大索引、未编译、未改全局Cargo/Git或C输入。

这是**独立官方metadata补充证据**，关闭当前11项精确锁版本的yanked缺证据；不是原cargo-audit完整命令通过。原D:/graghRAG-agent/.tmp/native-current-audit-20261028含11项index missing的stderr保留，exit0陷阱不抹去。当日RustSec DB99670cfc0bc574433034b75876a4b791ccaa2efb的no-yanked公告扫描可与本证据组合表述为“当前数值桥锁的公告扫描0及11项独立yanked/checksum核验通过”，不能改称工具本身完成了正常yanked检查。

本轮不覆盖Torch uv.dll1.40.0、CPython/SQLite/BLAS/CRT或其他模型native，相关安全准入仍open，不改变compatibility_not_approved。原收据与归档未修改。

文件：check_metadata.py（下载和核验执行器）、receipt.json（逐请求证据）、run.exit/stdout/stderr（实际命令结果）、verify_artifacts.py与verification.json（二次本地核验）。使用verification-before-completion，结论绑定本轮实际输入与响应。
