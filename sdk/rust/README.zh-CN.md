# 面向 Rust 的 OctoSense 组件 SDK

[English](README.md) | 简体中文

用普通的 Rust 编写 OctoSense 应用自带的函数，得到一个 WebAssembly 组件，应用的脚本以 `wasm.<function>` 调用它（OctoSense ADR 0014，在 [OctoSense #436](https://github.com/OctoSense-org/OctoSense/pull/436) 中提议）。不需要编写 WIT，也不需要胶水代码。指南见 [docs/RUST.zh-CN.md](../../docs/RUST.zh-CN.md)；`tools/octo wasm new` 用来创建 crate。

```rust
#[octosense_component::export]
pub mod functions {
    pub fn greet(name: &str) -> String {
        format!("Hello, {name}!")
    }
}
```

| 路径 | 内容 |
| --- | --- |
| [octosense-component/](octosense-component/src/lib.rs) | 组件依赖的 crate。它重新导出宏和 `wit-bindgen` 0.62，并提供 `log(line)`、[`http`](octosense-component/src/http.rs)（经 `wasi:http` 向任何主机发 HTTP 请求，使用 WASI 0.2 的 `wasi` crate）和 [`host`](octosense-component/src/host.rs)（经 `octosense:host` 调用应用的宿主服务，其 WIT 即 OctoSense 的 [`octosense-host.wit`](octosense-component/wit/octosense-host.wit)）。只有调用了它们的组件才会导入对应的接口。 |
| [octosense-component-macros/](octosense-component-macros/src/lib.rs) | `#[octosense_component::export]`。它根据模块中的 `pub fn`、`pub struct` 和 `pub enum` 写出 WIT world（名称用 kebab 形式），用 `wit_bindgen::generate!` 生成绑定，并在模块自己的类型与生成的类型之间转换。无法映射的类型会让构建失败，并说明改用什么。 |
| [examples/markdown-tools/](examples/markdown-tools/src/lib.rs) | 一个未作修改的 crate（`pulldown-cmark`）、一个记录、一个枚举、经由 `std::fs` 访问的文件、时钟和一行日志。 |
| [examples/type-tour/](examples/type-tour/src/lib.rs) | 双向的每一种类型映射、经由 `getrandom` 获取的随机数，以及在调用之间保留的状态。 |
| [examples/template/](examples/template/src/lib.rs) | `tools/octo wasm new` 复制的 [templates/rust-component/src/lib.rs](../../templates/rust-component/src/lib.rs)，在这里作为成员构建。 |
| [examples/http-client/](examples/http-client/src/lib.rs) | 用 `octosense_component::http` 发送 `GET` 和 `POST`，并通过它的请求构建器设置请求头和超时（ADR 0014 第 3 阶段）。 |
| [examples/socket-client/](examples/socket-client/src/lib.rs) | 用 `std::net` 发送有界的 TCP/UDP 回显请求并解析 DNS，不增加 SDK 套接字封装。要求 `wasm.sockets@1`，[已发布的桌面 RC6](../../README.zh-CN.md#下载兼容-shell) 提供该 API。RC5 不支持。 |
| [examples/host-services/](examples/host-services/src/lib.rs) | 用 `octosense_component::host` 调用应用的宿主服务（ADR 0014 第 3 阶段）。 |
| [e2e/](e2e/tests/components.rs) | 用普通的 cargo 为 `wasm32-wasip2` 构建这些示例，像 ADR 0014 的运行时一样在 Wasmtime 49 中以 WASI 0.2 加载，并调用每个函数。它像 OctoSense 第 3 阶段的运行时一样链接 `wasi:http`（`wasmtime-wasi-http` 49）和 `octosense:host`，并照搬其钩子：请求可以访问任何主机（这里是本机的 HTTP/1.1 服务器），并随这次调用的截止时间结束；宿主调用由模拟的服务答复。 |

在本目录中运行测试，需要先安装目标（`rustup target add wasm32-wasip2`）：

```sh
cargo test --locked --workspace
```

CI 的 `rust-sdk` 作业在 Ubuntu 上运行它们，并运行 `cargo fmt --all -- --check`。

套接字测试把示例编译为 `wasm32-wasip2`，在 Wasmtime 49 中验证 TCP、UDP、
本机名称解析、连接关闭和宿主未提供套接字的情形。它们验证 SDK 传输；生产环境的
套接字配额、取消、设备验收及兼容发布版由宿主另行负责。对于套接字应用，
`tools/octo wasm build` 除了加入 `wasm-components-v1`，还会加入
`host-api-v1` 和 `host_api.required: {"wasm.sockets": 1}`，并用 `net` 披露网络用途。

SDK 尚未发布到 crates.io。ADR 0014 会在维护者批准后发布它；在此之前，crate 通过本仓库的 git 提交或路径依赖它，`tools/octo wasm new` 两种都能写。OctoSense #453 已合并组件、HTTP 和宿主服务的源码集成；[已发布的桌面 RC6](../../README.zh-CN.md#下载兼容-shell) 增加套接字支持；每个应用仍须在其声明的平台上单独测试。能力名称仅披露用途；ABI/导入检查、应用与账户作用域、配额、实际同意及原生审核仍生效（见 [docs/RUST.zh-CN.md](../../docs/RUST.zh-CN.md)）。
