# OctoSense component SDK for Rust

English | [简体中文](README.zh-CN.md)

Write an OctoSense app's own functions in ordinary Rust, and get a
WebAssembly component that the app's script calls as `wasm.<function>`
(OctoSense ADR 0014, proposed in
[OctoSense #436](https://github.com/OctoSense-org/OctoSense/pull/436)). There
is no WIT and no glue code to write. The guide is
[docs/RUST.md](../../docs/RUST.md); `tools/octo wasm new` starts a crate.

```rust
#[octosense_component::export]
pub mod functions {
    pub fn greet(name: &str) -> String {
        format!("Hello, {name}!")
    }
}
```

| Path | What it is |
| --- | --- |
| [octosense-component/](octosense-component/src/lib.rs) | The crate a component depends on. It re-exports the macro and `wit-bindgen` 0.62, and has `log(line)`, [`http`](octosense-component/src/http.rs) (HTTP requests to any host over `wasi:http`, with WASI 0.2's `wasi` crate) and [`host`](octosense-component/src/host.rs) (the app's host services over `octosense:host`, whose WIT is OctoSense's [`octosense-host.wit`](octosense-component/wit/octosense-host.wit)). A component imports either only when it calls it. |
| [octosense-component-macros/](octosense-component-macros/src/lib.rs) | `#[octosense_component::export]`. It writes the WIT world from the module's `pub fn`s, `pub struct`s and `pub enum`s (names in kebab case), generates the bindings with `wit_bindgen::generate!`, and converts between the module's types and the generated ones. A type it cannot map fails the build with what to use instead. |
| [examples/markdown-tools/](examples/markdown-tools/src/lib.rs) | An unmodified crate (`pulldown-cmark`), a record, an enum, files through `std::fs`, the clock and a log line. |
| [examples/type-tour/](examples/type-tour/src/lib.rs) | Every type mapping both ways, random numbers through `getrandom`, and state kept between calls. |
| [examples/template/](examples/template/src/lib.rs) | [templates/rust-component/src/lib.rs](../../templates/rust-component/src/lib.rs), which `tools/octo wasm new` copies, built as a member here. |
| [examples/http-client/](examples/http-client/src/lib.rs) | `GET` and `POST` with `octosense_component::http`, a header and a timeout through its request builder (ADR 0014 phase 3). |
| [examples/socket-client/](examples/socket-client/src/lib.rs) | Bounded TCP/UDP echo requests and DNS using `std::net`, without an SDK socket wrapper. Needs the forthcoming `wasm.sockets@1` host API; RC5 does not support it. |
| [examples/host-services/](examples/host-services/src/lib.rs) | Calls to the app's host services with `octosense_component::host` (ADR 0014 phase 3). |
| [e2e/](e2e/tests/components.rs) | Builds the examples with plain cargo for `wasm32-wasip2`, loads them in Wasmtime 49 with WASI 0.2 as ADR 0014's runtime does, and calls every function. It links `wasi:http` (`wasmtime-wasi-http` 49) and `octosense:host` as OctoSense's phase 3 runtime does, with copies of its hooks: requests reach any host (here a local HTTP/1.1 server) and end at the call's deadline, and host calls reach fake services. |

Run the tests from this folder; they need the target
(`rustup target add wasm32-wasip2`):

```sh
cargo test --locked --workspace
```

CI's `rust-sdk` job runs them on Ubuntu, with `cargo fmt --all -- --check`.

The socket tests compile the example for `wasm32-wasip2` and exercise TCP,
UDP, local name resolution, connection closure and a host without socket
support in Wasmtime 49. They cover the SDK transport; production socket
quotas, cancellation, device acceptance and a compatible release are separate
host responsibilities. `tools/octo wasm build` adds `host-api-v1` and
`host_api.required: {"wasm.sockets": 1}` to socket apps, in addition to
`wasm-components-v1`; it discloses network use with `net`.

The SDK is not on crates.io yet. ADR 0014 publishes it there with a
maintainer's approval; until then, a crate depends on it by a git commit of
this repository or by path, and `tools/octo wasm new` writes either.
OctoSense #453 merged component, HTTP and host-service source integration;
actual app acceptance and a compatible downloadable host remain separate.
Capability names are usage disclosures; ABI/import checks, app/account
scope, quotas, consent and native reviews still apply
([docs/RUST.md](../../docs/RUST.md)).
