# 运行自己的 Rust 代码

[English](RUST.md) | 简体中文

未注明中文版的链接指向英文文档。

商店应用的应用包不能带原生代码，但可以把你的 Rust 代码编译成 WebAssembly，放在应用包的 `fns/` 文件夹中带上。Shell 的 `wasm` 服务在沙盒中运行这些代码，应用的脚本按名称调用它们。共有两种形式：

- **组件**（[ADR 0014](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0014-app-components-in-webassembly.zh-CN.md)）：用本仓库的 SDK 编写普通的 Rust，`tools/octo wasm build` 把它变成 `fns/<name>.wasm`。脚本以 `wasm.<function>` 加 JSON 调用每个 `pub fn`，因此不需要编写 WIT，也不需要胶水代码。组件在调用之间保留状态，能用时钟和随机数；应用有 `storage` 能力时，还能访问应用自己的文件；有 `net` 时，能经 HTTP 访问任何主机（见[网络](#网络)）；还能调用应用获授权的宿主服务（见[宿主服务](#宿主服务)）。
- **核心模块**（[ADR 0011](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0011-apps-own-functions-in-webassembly.zh-CN.md)）：处理字节或 JSON 的函数，用复制来的客体 crate 编写，只能看到自己的输入。本页末尾的[核心模块](#核心模块adr-0011)介绍它们。

**OctoSense `main` 已能运行组件；目前还没有任何发布版本运行它**。运行时（[OctoSense #436](https://github.com/OctoSense-org/OctoSense/pull/436)）以及加载组件、支持 HTTP 和宿主服务的 `wasm` 服务（[OctoSense #451](https://github.com/OctoSense-org/OctoSense/pull/451)）已于 2026 年 10 月 10 日合并，App Hub 的准入检查也接受组件（[App Hub #186](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/186)；`wasi:http` 和 `octosense:host` 由 [App Hub #188](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/188) 接受）。桌面版 0.1.0-rc.2 和 Home 0.1.0-beta.2 固定的 App Hub 早于 `wasm-components-v1`，因此它们的商店会在安装时拒绝这样的应用。从 OctoSense `main` 上不早于 `04100758` 的提交切出的第一个桌面版或 Home 发布版本，将是第一个能运行组件的发布版本。2026 年 10 月 10 日在此验证：本页的模板组件用 `tools/octo wasm build` 构建、经 `hub check` 接受后，通过 Shell 的 `wasm` 服务应答了 `wasm.count`、`wasm.greet` 和 `wasm.parse_number`；该服务基于 OctoSense `main`（`80b27693`）构建，在它自带的测试框架中运行，该框架分派调用的方式与 `host.request` 相同；首次加载的编译耗时 14 毫秒。仍属**未验证**的有：通过商店安装带组件的已发布应用、Agent 工具调用组件，以及在任何手机上运行。

| | 核心模块（ADR 0011） | 组件（ADR 0014） |
| --- | --- | --- |
| 编写和构建 | 复制 OctoSense 的客体 crate；`cargo build --target wasm32-unknown-unknown` | `tools/octo wasm new`，然后 `tools/octo wasm build`（本页） |
| 能访问什么 | 只有自己的输入 | 时钟、随机数，有 `storage` 时还有应用的存储文件夹；有 `net` 时还有网络（任何主机）；以及应用获授权的宿主服务。 |
| 两次调用之间 | 每次调用都从头开始 | 保留状态 |
| 清单 | `wasm` | `wasm`，以及 `requires: ["wasm-components-v1"]`；访问文件还需要 `storage`；发 HTTP 请求还需要 `net` |
| App Hub 的准入检查（`hub check`） | 从应用契约 1.7 起接受 | `main` 在 `requires: ["wasm-components-v1"]` 下接受它（App Hub #186），也接受 `wasi:http` 和 `octosense:host` 导入（App Hub #188），并说明每个组件能访问什么。早于 #186 的 `hub` 在 `hub stamp` 这一步就回答 `app <id> needs a newer host: wasm-components-v1`；不带这项要求时，它报告 `not a WebAssembly core module (magic and version 1)`。 |
| OctoSense `main` | 在 macOS、Linux 和 Android 上运行它 | 自 2026 年 10 月 10 日起运行它（OctoSense #451）：`wasm` 服务从 `fns/` 加载组件，支持经 HTTP 访问任何主机以及 `octosense:host`。Windows 构建自同一改动起包含这项服务，在那里运行属于**未验证**。Android 和 OpenHarmony 构建链接了运行时，但还没有组件在手机上运行过（**未验证**）。 |
| `card-host` | 接受应用；每次调用都返回 `no service answers "wasm" on this device` | 同样没有 `wasm` 服务。基于 App Hub `main` 构建时，它接受这份清单，因为它与 `hub` 做同样的契约检查（此处没有实际运行，属于**未验证**）。 |
| 发布版本 | 桌面版 0.1.0-rc.2 在 macOS 和 Linux 上运行它；还没有 Home 发布版本运行它 | 都不运行它。桌面版 0.1.0-rc.2 和 Home 0.1.0-beta.2 在安装时拒绝这份清单（`needs a newer host: wasm-components-v1`）。 |

本页每条命令都在 macOS（Apple 芯片）上用 Rust 1.97.1 运行过，标注为**未验证**的除外。示例使用 `tools/octo new` 在 `~/apps/my-app` 创建的应用（见 [QUICKSTART §3](QUICKSTART.zh-CN.md#3-创建应用)），id 为 `dev.example.texttools`。

## 选择途径

| 你需要 | 途径 | 参阅 |
| --- | --- | --- |
| 借助 crates.io 上的 crate 做计算：解析、格式转换、打分、密码学运算、图像处理 | 组件 | [编写组件](#编写组件) |
| 在今天就要能运行的应用中做纯计算 | 核心模块 | [核心模块](#核心模块adr-0011) |
| 相机、麦克风或位置 | 宿主 API：`camera`、`microphone` 和 `location` 能力及其权限方法，以及 `location.get` | [HOST-API-V1 §3](HOST-API-V1.zh-CN.md#3-在前台申请设备访问) |
| 网络 | Splash 的 `net`，只能访问 `network.hosts` 中的主机。组件有 `net` 时，可以用 `octosense_component::http` 访问任何主机（已在 OctoSense `main` 上，尚无发布版本包含）：应用的网络声明在安装时展示，运行时不强制。核心模块访问不了网络：先在 Splash 中取回数据，再传进去。 | [SCRIPT-API § Network](SCRIPT-API.md#network)、[网络](#网络) |
| 应用的宿主服务，例如 `runtime.list` | Splash 中的 `host.request`，或组件中的 `octosense_component::host`（已在 OctoSense `main` 上，尚无发布版本包含） | [宿主服务](#宿主服务) |
| 文件 | 应用自己的存储：在 Splash 中通过 `fs.*`，或者在应用有 `storage` 时，在组件中通过 `std::fs`。 | [SCRIPT-API § Storage](SCRIPT-API.md#storage-fs) |
| Rust crate 已经实现的功能 | 不能在 Splash 中直接调用这个 crate。可以把它构建成组件（见[编写组件](#编写组件)；先运行 `tools/octo wasm doctor`，它会指出哪些 crate 的功能 OctoSense 已经提供），纯计算也可以编译成核心模块；向 OctoSense 提议一项共享宿主服务并贡献它的适配层，连同方法描述、按应用隔离的资源和测试（[HOST-SERVICES § 新增宿主服务](HOST-SERVICES.zh-CN.md#新增宿主服务)）；或者放在你自己的后端里，通过 `net` 或经过认证的后端 API 调用（[HOST-API-V1 §4](HOST-API-V1.zh-CN.md#4-连接应用自己的后端)）。Shell 的 `Cargo.lock` 里有某个 crate，不等于 Splash 能调用它；把 `.so`、`.dylib` 或 `Cargo.toml` 放进应用包也没有任何用处，准入检查会直接拒绝。 | 本页、[HOST-SERVICES](HOST-SERVICES.zh-CN.md)、[HOST-API-V1 §4](HOST-API-V1.zh-CN.md#4-连接应用自己的后端) |
| 原生库、线程或系统调用 | 商店应用无法使用。App Hub 的准入检查会拒绝原生库，原生代码只能随 Shell 的发布版本分发。 | App Hub 的[交付路径](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/DEVELOPMENT.zh-CN.md#选择合适的交付路径) |

Splash 应用能调用的是宿主 API 表面，而不是它背后的 Rust crate：[HOST-API-FAMILIES](HOST-API-FAMILIES.zh-CN.md) 列出每个 `host.request` 能力族以及它响应哪些应用，[RUNTIME-TYPES](RUNTIME-TYPES.zh-CN.md) 列出运行时能解析的全部类型名，[SCRIPT-API](SCRIPT-API.md) 记录受支持的子集，已安装宿主上的 `runtime.list` 则给出它实现的方法（[HOST-API-V1 §2](HOST-API-V1.zh-CN.md#2-提供可选功能前先查询)）。

## 编写组件

### 1. 准备 Rust

组件需要 Rust 1.88 或更新版本：Rust 从 1.82 起能为 `wasm32-wasip2` 构建组件，而 SDK 使用的 `wit-bindgen` 构建时依赖的 crate（`wit-component`、`wit-parser` 0.259）需要 1.88。先添加目标，再让 `tools/octo` 检查工具链。在你的 App Flow 仓库中运行：

```sh
rustup target add wasm32-wasip2
tools/octo wasm doctor
```

在已经装有该目标的机器上，`rustup` 输出 `info: component rust-std for target wasm32-wasip2 is up to date`，`doctor` 输出：

```text
octo wasm doctor
  [ok]   cargo: /Users/<you>/.cargo/bin/cargo
  [ok]   rustc 1.97.1 (8bab26f4f 2026-07-14)
  [ok]   target wasm32-wasip2 is installed
  [info] no crate checked: pass --crate DIR, or run it in an app directory with components/<name>/
```

在没有该目标的机器上安装它，本文**未验证**。

### 2. 创建 crate

```sh
tools/octo wasm new text-tools --app ~/apps/my-app
```

它输出 `created …/my-app/components/text-tools`，并根据 [templates/rust-component](../templates/rust-component/) 写出一个 crate。只有构建出的组件会放进应用包：

```text
~/apps/my-app/
  bundle/
    fns/text-tools.wasm      `tools/octo wasm build` 之后的组件
  components/text-tools/     你的 crate；不在应用包中
    Cargo.toml
    src/lib.rs
    .gitignore               /target/
```

名称（这里是 `text-tools`）既是 crate 的名称，也是文件的名称：1 到 64 个 `[a-z0-9_-]` 字符，以字母开头。不带 `--app` 时，命令使用当前目录，该目录必须含有 `bundle/manifest.json`。

crate 以两种方式之一获得 SDK `octosense-component`。它的 `Cargo.toml` 中有一段注释，说明用的是哪一种以及原因：

| `--sdk` | `Cargo.toml` 写入 | 适用场景 |
| --- | --- | --- |
| `auto`（默认） | 能用 git 形式时用 git 形式，否则用路径形式 | — |
| `git` | `octosense-component = { git = "https://github.com/OctoSense-org/OctoSense-App-Flow", rev = "<commit>" }`，其中的提交是你的仓库所拥有的、App Flow `main`（以最近一次 fetch 为准）上含有 SDK 的最新提交 | 在任何机器上构建结果都相同，可以随应用一起提交。要换用更新的 SDK，修改 `rev`，再运行 `cargo update -p octosense-component`。 |
| `path` | `octosense-component = { path = "<你的 App Flow 仓库>/sdk/rust/octosense-component" }`，两者在同一个文件夹下时写相对路径 | 不需要网络，并跟随你的仓库；但其他机器需要把 App Flow 放在同样的位置。绝对路径会暴露你的机器，不要放进公开仓库。 |

SDK 尚未发布到 crates.io；ADR 0014 会在维护者批准后发布它。在本仓库的 `main` 含有 SDK 之前，`auto` 写入路径形式，并说明 `App Flow's main (origin/main, as last fetched) does not have the SDK yet`。git 形式只在本地仓库上测试过，因此用它构建属于**未验证**。

这个 crate 有自己的 `[workspace]`，所以应用外层的 Cargo 工作区不会把它当成成员；release 配置针对体积优化（`opt-level = "s"`、`lto`、`strip`）。

### 3. 编写函数

把 `#[octosense_component::export]` 放在一个内联模块上。模块中的每个 `pub fn` 都成为应用脚本可以调用的函数；其他条目仍是普通的 Rust，crate 的其余部分以及任何依赖都由你决定。下面是去掉注释的模板 `src/lib.rs`：

```rust
#[octosense_component::export]
pub mod functions {
    pub struct Counts {
        pub words: u32,
        pub lines: u32,
    }

    pub fn greet(name: &str) -> String {
        format!("Hello, {name}!")
    }

    pub fn count(text: &str) -> Counts {
        Counts {
            words: text.split_whitespace().count() as u32,
            lines: text.lines().count() as u32,
        }
    }

    pub fn parse_number(text: &str) -> Result<f64, String> {
        text.trim()
            .parse()
            .map_err(|_| format!("{text:?} is not a number"))
    }
}
```

宏根据这些签名写出组件的 WIT world，生成 `wit-bindgen` 胶水代码，并在你的类型与生成的类型之间转换。带具名字段的 `pub struct` 成为 WIT 记录，只有单元变体的 `pub enum` 成为 WIT 枚举，其他 `pub enum`（每个变体不带值或带一个值）成为 WIT 变体。函数能接收和返回的类型见[类型](#类型)。

在脚本中，名称保持你在 Rust 中的写法。WIT 把 `parse_number` 和字段 `word_count` 写成 kebab 形式（`parse-number`、`word-count`），`wasm` 服务则接受 `wasm.parse_number`，并以 `word_count` 返回。传入时也接受 kebab 写法。

宏无法映射的类型会让构建失败，并说明改用什么。例如，`HashMap` 参数会以 `maps and sets are not WIT types: use Vec<(K, V)>, Vec<T> or a pub struct` 失败。宏还拒绝 `usize`、除 `&str` 或 `&[u8]` 参数之外的引用、泛型函数和 `async` 函数、递归类型、两个 WIT 名称相同的条目，以及名为 `functions` 的函数（`wasm.functions` 已被占用）。

SDK 还给函数提供两样东西：

- `octosense_component::log(line)` 把一行写到 stderr，ADR 0014 让它成为应用的一行日志；`println!` 和 `eprintln!` 效果相同。
- `static`（例如放在 `Mutex` 或 `AtomicU64` 中的缓存）与组件实例的寿命相同，下次调用时仍然在（见[状态](#状态)）。

在 `~/apps/my-app` 中以本机方式测试这些函数：

```sh
cargo test --manifest-path components/text-tools/Cargo.toml
```

输出包含 `test tests::counts_words_and_lines ... ok` 和 `test tests::a_bad_number_is_an_error ... ok`。

### 4. 构建进应用包

```sh
tools/octo wasm build --app ~/apps/my-app
```

对 `components/` 中的每个 crate（或每个 `--crate DIR`），它会：

1. 运行 `cargo build --release --target wasm32-wasip2`；
2. 读取组件的导入，如果有导入不属于 `wasi:cli`、`wasi:clocks`、`wasi:filesystem`、`wasi:http`、`wasi:io`、`wasi:random` 和 `octosense:host` 这几个 `wasm` 服务提供给组件的包，就停下来，不改动应用包；
3. 在组件中记录构建它所用的 crate（见[构建所用的 crate](#构建所用的-crate)）；
4. 把它复制到 `bundle/fns/<name>.wasm`；
5. 在清单的 `capabilities` 中加入 `wasm`、在 `requires` 中加入 `wasm-components-v1`；组件导入 `wasi:filesystem` 时再加入 `storage`；组件导入 `wasi:http` 时再加入 `net`，并说明改了什么。它从不往 `network.hosts` 中添加主机，也不要求你添加（见[网络](#网络)）；
6. 对准入检查或服务之后会拒绝的情况发出警告：`fns/` 中超过 8 个文件、两个文件导出同名函数、应用包超过 8 MiB；
7. 找到 `hub` 时为应用包写入摘要。

对模板，在 Cargo 自己的输出之后，它输出：

```text
wrote bundle/fns/text-tools.wasm: 82,969 bytes, a component that reaches the clock, but no files, network or other app
  wasm.count(text: string) -> record { words: u32, lines: u32 }
  wasm.greet(name: string) -> string
  wasm.parse_number(text: string) -> result<f64, string>
  built from 6 crates (tools/octo wasm info lists them)
bundle/manifest.json:
  added "wasm" to capabilities: the app runs its own sandboxed functions
  added "wasm-components-v1" to requires: a host that runs only core modules refuses the app at install, instead of failing at its first call
```

模板的函数从不读取时间，但它的组件导入了 `wasi:clocks/monotonic-clock`；本文用 Rust 标准库构建的每个组件都是如此。

打开套接字的函数能通过编译，但 `tools/octo wasm build` 会拒绝这个组件。函数中有 `std::net::TcpStream::connect(addr)` 时，它输出：

```text
octo: text-tools imports what no host gives a component, so the wasm service would refuse to load it and App Hub's gate refuses the bundle:
  wasi:sockets/network@0.2.12, wasi:sockets/instance-network@0.2.12, wasi:sockets/udp@0.2.12, wasi:sockets/udp-create-socket@0.2.12, wasi:sockets/tcp@0.2.12, wasi:sockets/tcp-create-socket@0.2.12, wasi:sockets/ip-name-lookup@0.2.12:
    network sockets (std::net, or a crate such as reqwest, ureq or tokio's net, which open sockets): a component has none. It reaches the network over HTTP through wasi:http, with octosense_component::http, once the manifest has `net`.
```

要查看构建出的文件含有什么，运行 `tools/octo wasm info`，这里在 `~/apps/my-app` 中运行：

```sh
tools/octo wasm info bundle/fns/text-tools.wasm
```

它输出文件的种类、能访问什么、每个导入、每个函数及其 WIT 签名、构建它所用的 crate，以及清单需要什么。对本页的 `api-client` 组件（见[网络](#网络)），它输出 `reaches: the clock and the network, but no files or other app` 和 `the manifest needs "wasm" in capabilities, "wasm-components-v1" in requires, "net" in capabilities (it imports wasi:http)`。如果它找到的 `hub` 有 `hub component-info` 命令（App Hub #186），就交给这条命令；否则自己读取文件。对 SDK 的示例和模板，以及本页的 `api-client` 和 `host-calls` 组件，两者给出相同的答案；`--json` 以 `hub component-info` 的格式输出，并把 crate 清单放在 `"crates"` 中，这份清单总是由 octo 自己从文件中读取。

### 5. 在应用中调用

已于 2026 年 10 月 10 日通过基于 OctoSense `main` 构建的 `wasm` 服务测试框架验证（见页首），而不是在运行中的应用里验证；目前还没有任何发布版本运行它。

```splash
host.request("wasm.count", {text: "one two\nthree"}, fn(r){
    if r.is_ok { words = r.data.words } else { status = r.error }
})

host.request("wasm.parse_number", "2.5", fn(r){
    if r.is_ok { value = r.data } else { status = r.error }
})
```

参数可以是按参数名作键的对象、按参数顺序排列的数组；函数只有一个参数时，也可以直接传值。结果以 JSON 形式放在 `r.data` 中（见[类型](#类型)），`Err` 则放在 `r.error` 中：以 `"two"` 调用 `wasm.parse_number` 会失败，错误为 `"two" is not a number`。`wasm.functions` 列出每个函数及其 WIT 签名。

Agent 工具映射到组件函数的方式与映射到模块函数相同，用 `host_method: "wasm.<function>"`（见[从 Agent 工具调用](#从-agent-工具调用)）；对组件而言这属于**未验证**。

### 6. 测试

- 像第 3 步那样用 `cargo test` 以本机方式测试逻辑。
- `tools/octo wasm call <function> [JSON]` 借助 OctoSense 的 `wasm_call` 示例（[OctoSense #455](https://github.com/OctoSense-org/OctoSense/pull/455)，评审中；此处已针对它的最新提交验证），在命令行调用已构建组件的一个函数。它需要一个带有该改动的 OctoSense 检出目录，合并前是它的分支，合并后是 `main`（由 `OCTOSENSE_REPO` 指定，或者是与本仓库并列的 `OctoSense` 目录），首次运行会编译运行时。每次调用都得到一个新实例，`octosense:host` 调用会以 `needs a shell` 失败；其余行为与在 Shell 中相同。
- `tools/octo run` 在 `card-host` 中启动应用。`card-host` 没有 `wasm` 服务，每次调用都返回 `no service answers "wasm" on this device`。用它检查布局，以及应用在没有函数时显示什么。基于 App Hub `main` 构建的 `card-host` 接受这份清单（此处没有实际运行，属于**未验证**；见页首的表格）。
- `tools/octo check` 运行 App Hub 的准入检查。用基于 App Hub `main` 构建的 `hub` 时，准入检查接受组件，并告诉审核者它能访问什么（见[准入检查查看什么](#准入检查查看什么)）。早于 App Hub #186 的 `hub` 在写入摘要这一步就停止：`hub: app dev.example.texttools needs a newer host: wasm-components-v1`。刚用 `tools/octo new` 创建的应用会被拒绝，直到商店信息中写明的截图存在为止；`tools/octo check` 会说明如何截取。
- 在 OctoSense 中运行应用的函数，需要基于 `main` 上不早于 OctoSense #451 的提交构建的 Shell，因为目前还没有任何发布版本运行组件。按模块的方式测试（见[测试](#测试)第 2 到 9 步）。桌面应用在此没有运行过（**未验证**）；运行过的是这项服务自带的测试框架（见页首）。

SDK 自己的测试用普通的 cargo 为 `wasm32-wasip2` 构建示例和模板，像 ADR 0014 的运行时一样在 Wasmtime 49 中以 WASI 0.2 加载它们，并调用每个函数。对 HTTP 和宿主服务，测试像 OctoSense 的运行时一样链接 `wasi:http`（`wasmtime-wasi-http` 49）和 `octosense:host`，并照搬它的钩子：`http-client` 示例不经任何授权，按地址和按名称向本机的 HTTP/1.1 服务器发请求，发往从不应答的服务器的请求随这次调用结束；`host-services` 示例调用模拟的宿主服务。在 `sdk/rust/` 中运行：

```sh
cargo test --locked --workspace
```

输出包含 `test every_type_mapping_crosses_both_ways ... ok`、`test the_exports_run_with_an_unmodified_crate_files_and_a_clock ... ok`、`test the_template_octo_wasm_new_writes_runs_as_a_component ... ok`、`test http_reaches_any_host ... ok`、`test a_request_that_never_answers_ends_at_the_deadline ... ok`、`test a_component_calls_its_apps_granted_host_services ... ok` 和 `test a_component_imports_http_and_host_services_only_when_it_calls_them ... ok`。CI 在 Ubuntu 上运行它们，同时运行 `tools/` 的测试；这些测试用 `tools/octo wasm new` 和 `tools/octo wasm build` 构建一个新 crate。

### 7. 发布

`tools/octo publish-github` 安装的发布工作流会自己构建 `components/` 中的每个 crate：从打了标签的提交出发，
使用它固定的 Rust（1.97.1），像 `tools/octo wasm build` 一样记录每个组件构建所用的 crate，并在 GitHub
为应用包出具证明之前把每个组件写入 `bundle/fns/<name>.wasm`。
这样发布版携带的是由它所指明的源码构建的二进制文件，你不必提交 `fns/*.wasm`：`tools/octo wasm build`
为你自己的运行生成它们，发布时会替换它们。对每个 crate：

- 提交它的 `Cargo.lock`，因为发布时以 `--locked` 构建。没有它时发布会停止：
  `::error::app/components/<name> has no Cargo.lock: commit it, so the release builds what you tested`。
- 通过 git 依赖 SDK（`--sdk git`），因为路径指向的是你的机器。使用路径时发布会停止：
  `::error::app/components/<name> takes the SDK from a local path, which the release cannot build; depend on OctoSense App Flow by git (tools/octo wasm new --sdk git)`。

使用同一个 Rust、同一个 crate 和同一份 `Cargo.lock` 时，发布写出的就是你写出的文件，crate 清单也相同。对以 git（App Flow 的某个提交）依赖 SDK 的模板 crate，`tools/octo wasm build` 写出了 `bundle/fns/text-tools.wasm`（83,061 字节），随后在 macOS 上用工作流自己的脚本运行的工作流步骤输出 `unchanged: bundle/fns/text-tools.wasm, 83,061 bytes built from app/components/text-tools and the 6 crates its octosense-crates section lists`。以路径依赖 SDK 时，cargo 构建出逐字节相同的组件，但 crate 清单把 SDK 的来源记为 `path`，而不是 `git+https://github.com/OctoSense-org/OctoSense-App-Flow#<commit>`，因此文件在这一处与发布的不同（82,969 字节）。在 GitHub 上运行发布**未验证**。发布工具链（`tools/publisher-toolchain.json`）指向 App Hub `40abb23b`，即 App Hub #191 的合并提交：这是 OctoSense `main` 所固定的 App Hub 修订版，它的准入检查接受带 `wasi:http` 和 `octosense:host` 导入的组件（App Hub #186 和 #188）；它也包含 App Hub #190，即签名目录中的共享组件。它早于 App Hub #189，因此这个 `hub` 不输出 crate 清单，也不做安全公告检查；基于 App Hub `main` 且不早于 #189 构建的 `hub` 则会做。

## 组件能用什么

### 类型

函数能接收和返回的类型、对应的 WIT 类型，以及它在脚本中的 JSON 形式（ADR 0014）：

| Rust | WIT | 脚本中的 JSON |
| --- | --- | --- |
| `bool` | `bool` | `true` 或 `false` |
| `u8`、`u16`、`u32`、`u64`、`i8`、`i16`、`i32`、`i64` | `u8` … `u64`、`s8` … `s64` | 数字，会检查范围 |
| `f32`、`f64` | `f32`、`f64` | 数字 |
| `char` | `char` | 只含一个字符的字符串 |
| `String`；参数也可以是 `&str` | `string` | 字符串 |
| `Vec<u8>`；参数也可以是 `&[u8]` | `list<u8>` | base64 文本；也接受数字数组 |
| `Vec<T>` | `list<T>` | 数组 |
| `Option<T>` | `option<T>` | `null` 或该值 |
| 元组，例如 `(u32, String)` | `tuple<u32, string>` | 数组 |
| 带具名字段的 `pub struct` | `record` | 以字段名作键的对象 |
| 只有单元变体的 `pub enum` | `enum` | 变体的名称，例如 `"short"` |
| 其他 `pub enum` | `variant` | `"case"`；带值的变体为 `{"case": 值}` |
| `Result<T, String>`、`Result<(), String>` | `result<T, string>`、`result<_, string>` | 该值；`Err` 是这次调用的错误 |
| 没有返回值 | 没有结果 | `null` |

宏拒绝 `usize` 和 `isize`（改用 `u32`/`u64` 或 `i32`/`i64`）、映射和集合（改用 `Vec<(K, V)>`、`Vec<T>` 或 `pub struct`）、`Box`、`Rc`、`Arc` 和 `Cow`，以及 `String` 之外的错误类型（用 `.map_err(|e| e.to_string())` 转换）。

### 能访问什么

ADR 0014 给组件提供下列 WASI 0.2 接口和 `octosense:host`。SDK 的测试在 Wasmtime 49 中使用同样的集合，OctoSense `main` 的 `wasm` 服务提供的也是同一集合（OctoSense #451）。

| | 组件 |
| --- | --- |
| 时钟和随机数 | 可以：`std::time`，以及通过 `getrandom` 0.4 等 crate 获取随机数（SDK 的测试调用了它） |
| 文件 | 仅在有 `storage` 时：应用的存储文件夹作为 `/`，可读写，通过 `std::fs` 访问；设备上的其他文件一概不可见。没有 `storage` 时，没有任何文件夹。 |
| stdout 和 stderr | 成为应用的日志行 |
| 环境变量、参数和 stdin | 都为空 |
| 网络 | 通过 `wasi:http`，经 HTTPS 或普通 HTTP 访问任何主机，清单中需要有 `net`（见[网络](#网络)）。组件没有套接字：`wasi:sockets` 会被拒绝。 |
| 线程 | 没有：`wasm32-wasip2` 没有线程 |
| 宿主服务 | 通过 `octosense:host`，像应用的脚本那样调用应用获授权的宿主服务（见[宿主服务](#宿主服务)） |
| 其他应用 | 没有 |

### 网络

自 OctoSense #451（2026 年 10 月 10 日）起已在 OctoSense `main` 上，尚无发布版本包含。OctoSense 自己的测试把组件的请求发往本机服务器，SDK 的测试在 Wasmtime 49 中做同样的事，并照搬了 OctoSense 运行时的钩子。此处没有在 Shell 中运行过。

组件只能通过 `wasi:http` 访问网络，而且可以访问任何主机。按 OctoSense 2026 年 10 月 8 日的裁定，应用的网络声明（`net`、`network.hosts`）在安装时展示，运行时不强制：边界是操作系统和宿主的 API 表面。清单仍然需要 `net`，这样应用的权限会说明它使用网络（App Hub 的准入检查会拒绝导入了 `wasi:http` 却没有 `net` 的组件，见[准入检查查看什么](#准入检查查看什么)）：

```json
"capabilities": ["wasm", "net"]
```

组件不需要 `network.hosts`。应用的脚本仍遵守自己的规则：Splash 运行时仍然只让脚本的 `net` 访问其中列出的主机（见 [CAPABILITIES § 网络](CAPABILITIES.zh-CN.md#网络)）。

然后用 SDK 的 `octosense_component::http` 发请求。下面这个 crate 是示例应用中的 `components/api-client`，构建为 `fns/api-client.wasm`：

```rust
#[octosense_component::export]
pub mod functions {
    use octosense_component::http;

    /// What `fetch` returns: an object in the script.
    pub struct Page {
        pub status: u16,
        pub body: String,
    }

    /// `GET` `url`, on any host.
    pub fn fetch(url: &str) -> Result<Page, String> {
        let response = http::get(url)?;
        Ok(Page {
            status: response.status,
            body: response.text(),
        })
    }
}
```

| `octosense_component::http` | 作用 |
| --- | --- |
| `get(url)` | 发送 `GET`，返回 [`Response`](../sdk/rust/octosense-component/src/http.rs) |
| `post(url, content_type, body)` | 发送带该请求体的 `POST`，附上 `content-type` 和 `content-length` |
| `Request::new(method, url)`、`Request::get(url)`、`Request::post(url)` | 构建任意请求：`.header(name, value)`、`.body(bytes)`、`.timeout(duration)`，最后 `.send()` |
| `Response` | `status`、`headers` 和完整的 `body`；`.text()` 和 `.header(name)` |

请求会阻塞，直到完整的响应到达。任何状态码都算响应，所以 `404` 也是 `Ok`。`Err` 表示请求没有得到响应，内容是可读的文本，`?` 会把它变成脚本中这次调用的错误。只有调用了这些函数的组件才会导入 `wasi:http`；会打开套接字的 crate，例如 `reqwest`、`ureq` 或 `tokio` 的 `net`，仍然无法使用。

OctoSense `main` 的运行时（OctoSense #451）这样处理每个请求：

- 请求发往 URL 指定的任何主机，经 HTTPS 或普通 HTTP，包括设备本身及其本地网络。运行时不拒绝任何请求，也不为请求记录日志。
- 导入 `wasi:http` 的组件，每次调用的截止时间是 10 秒而不是 2 秒；每个请求的连接、首字节和字节间隔超时都随这次调用结束。因此，发往从不应答的服务器的请求会在组件内失败；在 SDK 的测试中，错误是 `the request to http://127.0.0.1:<port>/ failed: the server did not answer in time (ErrorCode::ConnectionReadTimeout)`。

组件导入 `wasi:http` 时，`tools/octo wasm build` 会加入 `net`；它从不添加主机，也不要求你添加。示例应用还没有 `net`，单独构建 `api-client`：

```sh
tools/octo wasm build --app ~/apps/my-app --crate ~/apps/my-app/components/api-client
```

在 Cargo 自己的输出之后，它输出：

```text
wrote bundle/fns/api-client.wasm: 108,794 bytes, a component that reaches the clock and the network, but no files or other app
  wasm.fetch(url: string) -> result<record { status: u16, body: string }, string>
  built from 6 crates (tools/octo wasm info lists them)
bundle/manifest.json:
  added "net" to capabilities: api-client imports wasi:http, the network
```

### 宿主服务

自 OctoSense #451（2026 年 10 月 10 日）起已在 OctoSense `main` 上，尚无发布版本包含。SDK 的测试在 Wasmtime 49 中调用模拟的宿主服务，并照搬了 OctoSense 的规则。此处没有在 Shell 中运行过。

`octosense_component::host::request(service, args)` 像应用脚本的 `host.request` 那样调用应用的一个宿主服务：`service` 写作 `family.method`，`args` 是 JSON 文本。它以文本返回服务的 JSON 答复，或以 `Err` 返回没有答复的原因。可以用任何 JSON crate（例如 `serde_json`）构造参数、读取答复。下面这个 crate 是 `components/host-calls`，构建为 `fns/host-calls.wasm`：

```rust
#[octosense_component::export]
pub mod functions {
    use octosense_component::host;

    /// The host APIs this build implements: `runtime.list`, which needs
    /// the app's `runtime` capability.
    pub fn host_apis() -> Result<String, String> {
        host::request("runtime.list", "{}")
    }
}
```

只有调用了 `host::request` 的组件才会导入 `octosense:host/services@0.1.0`。SDK 带有这个接口的 WIT，即 OctoSense 的 [`octosense-host.wit`](../sdk/rust/octosense-component/wit/octosense-host.wit)。OctoSense `main` 对每次调用执行下列规则（评审中的 [OctoSense #452](https://github.com/OctoSense-org/OctoSense/pull/452) 去掉第一条中关于已声明能力族的规则：此后无论清单如何声明，调用都会到达分派器，需要授权的服务自行检查授权）：

- 这个导入本身不需要授权。调用只能访问清单在 `capabilities` 中授予的能力族（系统应用自己的命名空间也算），所以 `runtime.list` 需要 `runtime`。
- 宿主以应用的身份、像应用的脚本那样发出调用，但绝不打开面板，也绝不询问用户，因此只有后台界面可以调用的方法才能用。
- 拒绝 `wasm.*`，参数必须是 JSON 文本。
- 等待时间受这次调用的截止时间约束。

宿主拒绝的调用以函数的 `Err` 返回，例如 `dev.example.texttools was not granted the mail service, which mail.list needs`、`a component cannot call wasm.*: its app's functions are already running it`、`<service>: the arguments are not JSON: <why>`、`<service> did not answer before the call's deadline` 或 `this host gives a component no host services`。

### 状态

每个组件有一个实例，与应用的 worker 存活同样长的时间，因此 `static`（已解析的文档、缓存、模型）在下次调用时仍然在。陷阱（trap）或超时会结束实例，下一次调用会得到新实例。应用更新、授权变更或撤回时实例会被丢弃，与模块相同（ADR 0014）。SDK 的测试展示了一个 `static` 计数器在同一实例上的两次调用之间得以保留；Shell 在应用的 worker 存活期间一直保留实例，而持有组件实例的 worker 在空闲 60 秒后退出（只运行模块的 worker 则是 5 秒）。必须保留下来的内容，请存进应用的存储。

### 无法构建或运行的依赖

`tools/octo wasm doctor --crate components/<name>` 用 `cargo metadata --filter-platform wasm32-wasip2` 读取 crate 的依赖，并指出其中已知无法在组件中构建或运行的那些。构建失败时，`tools/octo wasm build` 也会输出同样的结论。对模板，它报告 `none of the 6 crates it links is known not to build or run in a component`。

| crate | 原因 | 替代方案 |
| --- | --- | --- |
| C 库：`openssl-sys`、`libsqlite3-sys`，以及用 `cc` 或 `cmake` 编译 C 代码的 crate | 它们需要面向 WASI 的 C 编译器，例如 wasi-sdk 的 clang | 纯 Rust 的 crate 或特性：密码学用 RustCrypto 的 `sha2`、`hmac` 或 `aes-gcm`；数据存为应用存储中的文件，或交给脚本的存储 |
| 网络：`reqwest`、`hyper`、`ureq`、`curl`、`mio`、`socket2`、`tungstenite`、`native-tls` | 它们会打开套接字，而组件没有套接字 | 有 `net` 时用 `octosense_component::http`（见[网络](#网络)），或在 Splash 中用 `net` 取回数据，再传进去 |
| 线程：`rayon` | `wasm32-wasip2` 没有线程 | 普通迭代器，或关闭该 crate 的并行特性 |
| 带 `rt-multi-thread`、`net`、`fs`、`process` 或 `signal` 的 `tokio` | 它们需要线程、网络或设备 | 普通函数：组件的函数就是普通调用，不需要异步运行时 |
| JavaScript 绑定：`wasm-bindgen`、`js-sys`、`web-sys` | 组件里没有 JavaScript | 关闭该 crate 的 `js` 或 `wasm-bindgen` 特性 |
| 原生代码：`pyo3`、`jni`、`libloading`；Unix 调用：`nix` | WASI 中都不存在 | — |

这份列表是 `tools/octo` 所知道的，并非所有会失败的 crate。能通过编译的依赖仍可能导入宿主不提供的接口，第 4 步会发现这种情况。

### OctoSense 已经提供的功能

OctoSense 以原生方式链接了许多 crate，例如 Makepad 的 Markdown 控件和 Markdown 编辑器所用的 `pulldown-cmark`；但组件无法调用原生代码，应用只能通过 Splash 的控件和函数，以及授予它的宿主服务用到它们。对于 OctoSense 已经替商店应用完成其常见用途的直接依赖，`tools/octo wasm doctor` 会输出一行 `info`，它不会让检查失败：

| crate | 应用改用什么 | 何时仍值得带上该 crate | 依据 |
| --- | --- | --- | --- |
| `pulldown-cmark`、`comrak`、`markdown` | Splash 的 `Markdown` 控件，它渲染 Markdown，包括表格 | 只在生成 HTML，或把 Markdown 当作数据读取时 | [SCRIPT-API § Widgets](SCRIPT-API.md#widgets-available-to-an-app) |
| `feed-rs`、`rss`、`atom_syndication` | 脚本中的 `text.parse_feed(style)`：每个 RSS 或 Atom 条目的标题、链接、来源、发布时间、摘要和图片 | 只在需要 `parse_feed` 不读取的内容时 | [SCRIPT-API § Data and strings](SCRIPT-API.md#data-and-strings) |
| `async-openai`、`genai`、`ollama-rs`、`openai-api-rs` | `model.complete`（需要 `model` 能力）：在每日预算内，向用户自己的 AI 提供商发出一次性、按 schema 校验的请求 | 绝不带着提供商密钥：应用不持有任何密钥 | [AI-SERVICES § 一次性模型调用](AI-SERVICES.zh-CN.md#一次性模型调用model) |

对 SDK 的 `markdown-tools` 示例（它把 Markdown 转成 HTML），`tools/octo wasm doctor --crate sdk/rust/examples/markdown-tools` 在 `[ok]` 行之后输出：

```text
  [info] pulldown-cmark 0.13.4: OctoSense renders Markdown itself: Splash's Markdown widget shows it, tables included. Ship the crate only to produce HTML or to read Markdown as data. (docs/SCRIPT-API.md#widgets-available-to-an-app)
```

这张表只收录本仓库文档说明商店应用可以使用的功能。`photo`、`pdf`、`word` 等引擎服务只供系统应用使用，因此 `doctor` 一个也不推荐。会打开网络套接字的 crate（例如 `reqwest` 或 `ureq`）属于失败而不是提示：`doctor` 会说明组件应改用 `octosense_component::http` 访问网络（见[无法构建或运行的依赖](#无法构建或运行的依赖)和[网络](#网络)）。

### 构建所用的 crate

`tools/octo wasm build` 在每个组件中记录构建它所用的 crate，发布工作流也记录同样的清单（见[7. 发布](#7-发布)）。App Hub 的准入检查把这份清单展示给审核者，并对照 [RustSec 安全公告数据库](https://rustsec.org/)检查它。App Hub `main` 自 App Hub #189 起两者都已实现：`hub check` 在此对模板输出了 `is built from 6 crates: …`，`hub check --advisory-db <dir>` 则对照数据库检查这份清单（此处没有运行）。

清单列出组件链接了其代码的每个包：即 crate 的普通依赖在 `wasm32-wasip2` 上能到达的包（由 `cargo metadata --filter-platform wasm32-wasip2` 解析），不包括 crate 自身。构建依赖和开发依赖在构建机器上运行，过程宏也是如此，因此清单中既没有过程宏，也没有只被过程宏使用的 crate。模板的清单有六个 crate：`bitflags`、`octosense-component`、`wasi` 和 `wasip2`（供 `octosense_component::http` 使用），以及两个版本的 `wit-bindgen`；不包括 `syn`、`wit-parser` 以及 SDK 和 `wit-bindgen` 的宏用来生成代码的其他 crate。每一项包含：

| 字段 | 内容 |
| --- | --- |
| `name`、`version` | 包的名称和版本 |
| `source` | `crates.io`；git 依赖为 `git+<url>#<commit>`，去掉 `?rev=` 或 `?branch=`；本地依赖（例如用 `--sdk path` 引入的 SDK）为 `path`；其他注册表则照 Cargo 写出的来源原样记录 |
| `checksum` | 注册表包在 crate 的 `Cargo.lock` 中的 SHA-256。git 和路径包没有。 |

这份清单是文件末尾一个名为 `octosense-crates` 的 WebAssembly 自定义段。它的内容是 `{"schema": 1, "crates": [...]}` 的 UTF-8 JSON，键已排序、不含空格，crate 按名称和版本排序。再次构建会替换它，因此一个文件只有一份。Wasmtime 49 加载带这个段的组件，并像以前一样运行它：SDK 的端到端测试在一个带清单的 `markdown-tools` 组件上通过了（在 `sdk/rust/` 中运行 `OCTOSENSE_COMPONENT_WASM=<file> cargo test --locked -p octosense-component-e2e`）。Shell 的 `wasm` 服务能加载带这个段的组件：本页的模板以路径依赖 SDK 构建后，在此通过它给出了应答。

`tools/octo wasm info` 输出这份清单。对以路径依赖 SDK 构建的模板：

```text
built from 6 crates, as its octosense-crates section lists them:
  bitflags 2.13.2, crates.io
  octosense-component 0.1.0, path
  wasi 0.14.7+wasi-0.2.4, crates.io
  wasip2 1.0.4+wasi-0.2.12, crates.io
  wit-bindgen 0.57.1, crates.io
  wit-bindgen 0.62.0, crates.io
```

带 `--json` 时，`"crates"` 中是各项内容，包括校验和。用其他方式构建的文件会显示 `crates: not recorded`。

### 准入检查查看什么

下列结论来自 App Hub `main`：即 App Hub #186，以及与 `wasi:http` 和 `octosense:host` 有关的 App Hub #188，分别于 2026 年 10 月 9 日和 10 日合并。早于 #186 的 `hub` 在任何检查运行之前就拒绝要求 `wasm-components-v1` 的应用包。对示例应用运行 `tools/octo check`，除其他结论外还会输出：

```text
  [warning] functions (fns/text-tools.wasm): fns/text-tools.wasm is a component that reaches the clock, but no files, network or other app
```

应用包中带有[网络](#网络)和[宿主服务](#宿主服务)两节的组件时，这两个组件的结论是：

```text
  [warning] functions (fns/api-client.wasm): fns/api-client.wasm is a component that reaches the clock and the network, but no files or other app
  [warning] functions (fns/host-calls.wasm): fns/host-calls.wasm is a component that reaches the clock and its app's host services, but no files, network or other app
```

| 结论 | 处理办法 |
| --- | --- |
| `[refused] functions: fns/text-tools.wasm is a WebAssembly component; the manifest must require wasm-components-v1` | 把它加入 `requires`，或运行 `tools/octo wasm build`。 |
| `[refused] functions: fns/markdown.wasm imports wasi:filesystem, the app's own files, which needs the storage capability` | 加入 `storage`，或去掉文件访问。 |
| `[refused] functions: fns/api-client.wasm imports wasi:http, the network, which the app must declare with the net capability` | 在 `capabilities` 中加入 `net`，或运行会加入它的 `tools/octo wasm build`。不需要主机列表（见[网络](#网络)）。 |
| `[refused] contents-invalid (fns/netprobe.wasm): the component imports wasi:sockets/network@0.2.9; a component may import only wasi:cli, wasi:clocks, wasi:filesystem, wasi:http, wasi:io, wasi:random and octosense:host` | 去掉打开套接字的部分（见[无法构建或运行的依赖](#无法构建或运行的依赖)）。 |

`fns/` 中每个文件都要遵守的规则（文件名、最多 8 个文件、应用包 8 MiB）与模块相同（见[构建](#构建)）。

## 核心模块（ADR 0011）

核心模块是 OctoSense `main` 和桌面版 0.1.0-rc.2 目前运行的形式：WebAssembly 核心模块，不是组件；它的函数接收和返回字节或 JSON，除了自己的输入什么也接触不到。本节其余部分是核心模块的指南。

### 函数在哪里运行

函数由 Shell 的 `wasm` 宿主服务运行。OctoSense 的 [ADR 0011](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0011-apps-own-functions-in-webassembly.zh-CN.md) 已接受这项服务，属于有限支持：OctoSense 的 Cargo 特性 `wasm-functions` 默认开启，让 macOS、Linux 和 Android 上的每个标准桌面端和 Home 构建都包含这项服务。`wasm-lab` 是这项特性以前的名字，仍保留为别名。Windows（RC2 未包含）、iOS（不允许应用生成代码）和 OpenHarmony（策略未知）的构建不包含这个运行时。

| 构建 | 是否接受申请 `wasm` 的应用 | 是否运行它的函数 |
| --- | --- | --- |
| `desktop-v0.1.0-beta.2` | 否。它的应用契约是 1.5，会拒绝这项能力：`app <id> requests unknown capability "wasm"`。 | 否 |
| [OctoSense 桌面版 0.1.0-rc.1](../README.zh-CN.md#下载兼容-shell) 的默认构建 | 是 | 否。每次调用都返回 `no service answers "wasm" on this device`。 |
| [OctoSense 桌面版 0.1.0-rc.2](../README.zh-CN.md#下载兼容-shell)，macOS 或 Linux | 是 | 是 |
| OctoSense 桌面版 0.1.0-rc.2，Windows | 是 | 否。每次调用都返回 `no service answers "wasm" on this device`。 |
| OctoSense `main` 面向 macOS、Linux 或 Android 的默认构建（特性 `wasm-functions`，旧名 `wasm-lab`） | 是 | 是 |
| OctoSense `main` 面向 Windows、iOS 或 OpenHarmony 的构建 | 是 | 否。每次调用都返回 `no service answers "wasm" on this device`。 |
| 基于 App Hub `main` 构建的 `card-host` | 是 | 否。每次调用都返回 `no service answers "wasm" on this device`。 |

桌面版 0.1.0-rc.2 是第一个包含这项服务的发布版本，在 macOS 和 Linux 上提供（其 Windows 构建不包含）；`desktop-v0.1.0-beta.2`、桌面端 RC1 和 `home-v0.1.0-beta.1` 都不包含。目前还没有任何 Home 发布版本包含它。

App Hub 的准入检查（`hub check`）从应用契约 1.7 起接受 `wasm` 能力，每个应用包最多带 8 个模块（见[构建](#构建)）。

**未验证**：App Hub 公开目录中的应用还没有运行过自己的函数。在设备上运行过函数的有系统应用 Wasm Lab，以及 OctoSense 的手机验收应用：一个经由正常商店准入、安装在 OnePlus 6 上的已签名测试应用。

### 一次调用的过程

1. 应用的脚本调用 `host.request("wasm.<function>", args, fn(r){…})`，或者应用的 Agent 调用映射到 `wasm.<function>` 的工具。
2. 应用第一次调用时，`wasm` 服务从该应用自己的应用包中加载全部模块（`fns/*.wasm`），绝不加载其他应用的模块。Shell 的 WebAssembly 运行时 Wasmtime 用自带的 Cranelift 编译器编译每个模块，或者直接从 Shell 的磁盘缓存中取出编译好的代码。
3. 服务把参数以字节形式传给函数。函数在该应用专属的工作线程上运行，所以一个慢函数只会拖慢它自己的应用。同一个应用的调用按顺序逐个执行。工作线程空闲 5 秒后退出；应用的下一次调用会启动新的工作线程，重新加载模块。
4. 脚本的回调从 `r.data` 拿到输出，或从 `r.error` 拿到错误。

每次调用都使用一个全新的**实例**，即拥有独立内存的模块运行副本。任何数据都不会从一次调用保留到下一次：`static`、内存中的缓存，以及写进模块线性内存的其他任何数据，到下一次调用时都已不在。只有编译好的代码会被复用。请把状态保存在脚本中，每次调用时把函数需要的数据传给它。**陷阱**（trap）指函数因 panic、栈溢出或内存超出 256 MiB 上限而中止。发生陷阱或超过 2 秒截止时间时，只有这次调用以错误结束，Shell 照常运行。

应用更新、授权变化或签名撤回之后，服务会丢弃编译好的代码，以及正在运行的那次调用的结果。那次调用返回 `wasm app admission changed; retry from the current app`，下一次调用会加载新的模块，Shell 不需要重启。

### 编写函数

#### 客体 crate

`octosense-guest` 是客体（guest，即模块内部的 Rust 代码）一侧的辅助 crate，替你实现 [ABI](#abi)。它不在 crates.io 上，请从 OctoSense 仓库的 [`apps/wasmlab/guest/octosense-guest`](https://github.com/OctoSense-org/OctoSense/tree/main/apps/wasmlab/guest/octosense-guest) 复制。它采用 Apache-2.0 许可，只依赖 `serde_json`。

| 项目 | 作用 |
| --- | --- |
| `octosense_guest::abi!()` | 导出 `octo_alloc` 和 `octo_free`。每个 crate 调用一次。 |
| `octosense_guest::export!(f)` | 以 `f` 为名导出 `fn f(&[u8]) -> Result<Vec<u8>, String>`：字节进，字节出。 |
| `octosense_guest::export_json!(f)` | 以 `f` 为名导出 `fn f(In) -> Result<Out, String>`，其中 `In: Deserialize`、`Out: Serialize`。它把输入按 JSON 解析成 `In`，再把 `Out` 写成 JSON。输入解析失败时返回 `the input is not what f takes: <reason>`。 |
| `octosense_guest::log(line)` | 把 `line` 写进 Shell 的日志，格式为 `wasm <app id>: <line>`。原生构建会把它打印到 stderr。 |
| panic 钩子（由 `export!` 和 `export_json!` 安装） | 在调用因陷阱结束之前，把 panic 信息记为一行 `panic: …`。 |

#### 最小示例

下面的步骤为 `tools/octo new` 在 `~/apps/my-app` 中创建的应用添加函数（见 [QUICKSTART §3](QUICKSTART.zh-CN.md#3-创建应用)），示例中应用的 id 是 `dev.example.texttools`。把 Rust crate 放在 `bundle/` 旁边，只有构建出的模块进入应用包：

```text
~/apps/my-app/
  bundle/
    fns/my_functions.wasm   构建出的模块
  functions/                你的 Rust crate；不放进应用包
    Cargo.toml
    src/lib.rs
  octosense-guest/          从 OctoSense 复制而来；不放进应用包
```

1. 按 [PUBLISHING §4.2](PUBLISHING.zh-CN.md#42-在桌面端-shell-中安装并打开应用) 的说明把 OctoSense 克隆到 `<workspace>`，然后复制客体 crate：

   ```sh
   cp -R <workspace>/OctoSense/apps/wasmlab/guest/octosense-guest ~/apps/my-app/
   ```

2. 编写 `functions/Cargo.toml`。`cdylib` 生成 `.wasm` 文件；`rlib` 让其他 Rust 代码（例如集成测试）以原生方式链接同一批函数。release profile 沿用 Wasm Lab 的设置（见[构建](#构建)）。

   ```toml
   [package]
   name = "my-functions"
   version = "0.1.0"
   edition = "2021"
   publish = false

   [lib]
   crate-type = ["cdylib", "rlib"]

   [dependencies]
   octosense-guest = { path = "../octosense-guest" }
   serde = { version = "1", features = ["derive"] }
   pulldown-cmark = { version = "0.13", default-features = false, features = ["html"] }

   [profile.release]
   opt-level = 3
   lto = true
   codegen-units = 1
   panic = "abort"
   strip = true
   ```

3. 编写 `functions/src/lib.rs`。其中的两个函数改编自 Wasm Lab：`md_to_html` 接收文本、返回文本，`rank` 接收并返回 JSON。

   ```rust
   //! 应用自己的函数，为 wasm32-unknown-unknown 构建。
   use serde::{Deserialize, Serialize};

   // 导出 octo_alloc 和 octo_free。每个 crate 调用一次。
   octosense_guest::abi!();

   /// 文本进，文本出：把 CommonMark 转成 HTML。
   pub fn md_to_html(input: &[u8]) -> Result<Vec<u8>, String> {
       let text = std::str::from_utf8(input).map_err(|_| "the text is not UTF-8".to_string())?;
       let mut html = String::new();
       pulldown_cmark::html::push_html(&mut html, pulldown_cmark::Parser::new(text));
       Ok(html.into_bytes())
   }
   octosense_guest::export!(md_to_html);

   /// JSON 进，JSON 出：找出包含查询词的条目，匹配位置越靠前排得越前。
   #[derive(Deserialize)]
   pub struct RankRequest {
       pub query: String,
       pub items: Vec<String>,
       #[serde(default = "ten")]
       pub limit: usize,
   }

   #[derive(Serialize)]
   pub struct Ranking {
       pub ranked: Vec<String>,
   }

   fn ten() -> usize {
       10
   }

   pub fn rank(req: RankRequest) -> Result<Ranking, String> {
       let query = req.query.to_lowercase();
       if query.is_empty() {
           return Err("the query is empty".into());
       }
       let mut hits: Vec<(usize, &String)> = req
           .items
           .iter()
           .filter_map(|item| item.to_lowercase().find(&query).map(|at| (at, item)))
           .collect();
       hits.sort();
       let ranked = hits.into_iter().take(req.limit).map(|(_, item)| item.clone()).collect();
       Ok(Ranking { ranked })
   }
   octosense_guest::export_json!(rank);

   #[cfg(test)]
   mod tests {
       use super::*;

       #[test]
       fn the_earliest_match_comes_first() {
           let req = RankRequest {
               query: "cal".into(),
               items: vec!["Local calls".into(), "Calendar".into(), "Mail".into()],
               limit: 10,
           };
           assert_eq!(rank(req).unwrap().ranked, ["Calendar", "Local calls"]);
       }
   }
   ```

4. 在 `~/apps/my-app` 中以原生方式测试逻辑：

   ```sh
   cargo test --manifest-path functions/Cargo.toml
   ```

   输出中包含 `test tests::the_earliest_match_comes_first ... ok`。

#### 沙盒禁止的操作

函数只能接触自己的内存和 `octo.log`。Rust 标准库照样能为 `wasm32-unknown-unknown` 编译，但下列调用会失败，或者什么也不做：

| 你的代码 | 结果 | 替代做法 |
| --- | --- | --- |
| 读取时钟：`Instant::now()`、`SystemTime::now()` | panic，信息为 `time not implemented on this platform`，调用因此触发陷阱。 | 把时间放在输入中传入。Splash 有 `time_now()`。 |
| 直接调用 `getrandom`，或经由启用默认特性的 `rand` 等 crate 获取随机字节 | `getrandom` 无法为 `wasm32-unknown-unknown` 构建。启用它的 JavaScript 后端后，它会导入 `wasm-bindgen` 的函数，模块因此无法加载。 | 把随机种子放在输入中传入。Splash 有 `random_u32()`。 |
| 用 `std::fs` 打开文件 | 返回 `operation not supported on this platform`。 | 在 Splash 中读取文件，再把内容传入函数。 |
| 用 `std::net` 打开套接字 | 返回 `operation not supported on this platform`。 | 在 Splash 中用 `net` 取回数据，再传入函数。 |
| 用 `std::thread::spawn` 启动线程 | panic，调用因此触发陷阱。`thread::Builder::spawn` 返回 `operation not supported on this platform`。 | 在单个线程上完成计算。 |
| 读取环境变量 | `std::env::var` 返回 `Err(NotPresent)`。 | 把设置放在输入中传入。 |
| 用 `println!` 或 `eprintln!` 输出 | 没有任何输出。 | 调用 `octosense_guest::log`。 |
| 导入宿主函数，例如 WASI 或 `wasm-bindgen` 的函数 | 模块无法加载：`the module imports <name>; only octo.log is provided`。 | 为 `wasm32-unknown-unknown` 构建，并去掉带来这个导入的依赖。 |

#### 上限

| 上限 | 数值 | 函数超出时 |
| --- | --- | --- |
| 每次调用的时间 | 2 秒（按墙钟时间计），每 10 毫秒检查一次 | `the call ran past its deadline` |
| 每个实例的内存 | 256 MiB | `the function trapped: memory over its cap (…)` |
| 每次调用的 Wasm 栈 | 512 KiB | `the function trapped: wasm trap: call stack exhausted` |
| 每次调用的输入和输出 | 各 16 MiB | `<n> bytes is over the input/output limit` |
| 模块大小 | 8 MiB | `<file>: module exceeds the size limit` |
| 日志 | 每次调用 64 行，每行截断到 1,024 字节 | 多出的行会丢弃。 |

`wasm` 服务还为每个请求设了自己的上限：

| 上限 | 数值 | 请求超出时 |
| --- | --- | --- |
| 序列化后的输入 | 每个请求 1 MiB | `wasm input exceeds 1 MiB` |
| 排队的请求 | 每个应用 4 个 | `wasm app queue is full; try again later` |
| 同时运行函数的应用 | 4 个 | `wasm workers are busy; try again later` |
| 所有应用合计缓冲的输入 | 16 MiB | `wasm input queue is full; try again later` |
| 一个请求的时间，包括排队和加载 | 10 秒，即服务自己的超时时间（App Hub 的默认值是 60 秒） | `the host service timed out` |

队列已满或没有空闲的工作线程时，请求会立即失败，不会等待。同一个应用的调用在它专属的工作线程上按顺序逐个执行，工作线程空闲 5 秒后退出。

App Hub 为宿主服务请求设的通用上限同样适用，不过 `wasm` 服务自己的上限更严。来自脚本的调用会先碰到这些上限，然后才轮到运行时 16 MiB 的上限：

| 上限 | 数值 | 调用超出时 |
| --- | --- | --- |
| 脚本请求的参数 | 1 MiB 的 JSON | `the request's arguments exceed 1 MiB` |
| 返回结果 | 4 MiB 的 JSON | `the service's answer exceeds 4 MiB` |
| 每个应用同时等待的调用 | 32 个 | `too many host requests are waiting; try again when some have answered` |

来源：OctoSense `crates/wasm-host/src/lib.rs` 中的 `Limits::default()`（`wasm` 服务使用这组上限）、OctoSense `crates/shell/src/wasm_service.rs` 中的常量，以及 App Hub 的 `crates/appstore/src/services.rs`。

#### ABI

客体 crate 实现了这套 ABI。不用这个 crate 编写模块，或者排查模块的问题时，需要了解它。模块是 WebAssembly 核心模块，不是组件。它包含下列导出，以及最多一个导入：

| 名称 | 类别 | 类型 | 作用 |
| --- | --- | --- | --- |
| `memory` | 导出 | 内存 | 模块的线性内存。 |
| `octo_alloc` | 导出 | `(len: i32) -> i32` | 为输入分配 `len` 字节，返回其地址。 |
| `octo_free` | 导出 | `(ptr: i32, len: i32)` | 释放 `octo_alloc` 返回的缓冲区，或存放输出的缓冲区。 |
| 每个函数 | 导出 | `(ptr: i32, len: i32) -> i64` | 读取 `ptr` 处的 `len` 字节输入，返回 `(out_ptr << 32) \| out_len`，即输出缓冲区（由函数自行分配）的地址和长度；这个缓冲区以状态字节开头（见下面第 4 步）。 |
| `octo.log` | 导入，可选 | `(ptr: i32, len: i32)` | 向 Shell 的日志写一行。 |

Shell 分四步完成一次调用：

1. 调用 `octo_alloc(len)`，把输入写到返回的地址。
2. 用这个地址和长度调用函数，再用 `octo_free` 释放输入。
3. 复制输出缓冲区，再用 `octo_free` 释放它。
4. 读取缓冲区的第一个字节，即状态字节：`0` 表示其余部分是输出，`1` 表示其余部分是 UTF-8 编码的错误文本。其他值或空缓冲区都按陷阱处理。

类型为 `(i32, i32) -> i64` 的导出都是应用可以调用的函数，其他类型的导出 Shell 一概忽略。模块缺少 `memory`、`octo_alloc` 或 `octo_free`，或者除 `octo.log` 外还有其他导入，都无法加载。

### 构建

在 `~/apps/my-app` 中运行下列命令。

1. 确认 Rust 已安装 WebAssembly 目标平台：

   ```sh
   rustup target list --installed
   ```

   列表中应有 `wasm32-unknown-unknown`。如果没有，添加它（**未验证**）：

   ```sh
   rustup target add wasm32-unknown-unknown
   ```

2. 构建模块：

   ```sh
   cargo build --manifest-path functions/Cargo.toml --release --target wasm32-unknown-unknown
   ```

   构建成功时，最后一行是 ``Finished `release` profile [optimized] target(s) in …``。如果构建在编译 `getrandom` 时失败，说明某个依赖需要系统随机数：去掉这个依赖，或者关闭引入 `getrandom` 的特性（见[沙盒禁止的操作](#沙盒禁止的操作)）。

3. 把模块复制进应用包。Cargo 用包名给文件命名，并把 `-` 换成 `_`：

   ```sh
   mkdir -p bundle/fns
   cp functions/target/wasm32-unknown-unknown/release/my_functions.wasm bundle/fns/
   ```

准入检查要求应用包遵守下列规则：

| 规则 | 要求 |
| --- | --- |
| 路径 | `fns/<name>.wasm`，直接放在 `fns/` 下 |
| 名称 | 1 到 64 个字符，取自 `[a-z0-9_-]` |
| 文件头 | 前 8 个字节：WebAssembly 核心模块，版本 1（App Hub #186 也接受组件） |
| 模块数 | 每个应用包最多 8 个 |
| 应用包大小 | 文件合计 8 MiB（8,388,608 字节），不计 `manifest.json` |

准入检查不读取模块的导入和导出，由 Shell 在加载模块时检查，所以通过准入检查的模块仍可能加载失败（见[应用看到的错误](#应用看到的错误)）。此外，函数名在应用的所有模块中必须唯一：两个模块导出同名函数时，`wasm` 服务会拒绝加载。

示例沿用 Wasm Lab 的 release profile：

| 设置 | 效果 |
| --- | --- |
| `opt-level = 3` | 按速度优化。 |
| `lto = true`、`codegen-units = 1` | 把所有 crate 当作一个整体来优化。 |
| `panic = "abort"` | panic 立即触发陷阱，不生成栈展开代码。 |
| `strip = true` | 去掉符号和调试信息。 |

用 Rust 1.97 构建时，示例模块在这些设置下是 372,358 字节，在 Cargo 默认的 release profile 下是 430,973 字节。

`tools/octo new` 写入的 `.gitignore` 已包含 `target/`，所以构建输出不会进入 Git。把 `bundle/fns/my_functions.wasm` 和 `functions/`、复制来的 `octosense-guest/` 一起 commit，构建 crate 需要它们。

### 声明并调用

#### 声明能力

1. 在 `bundle/manifest.json` 中申请 `wasm`：

   ```json
   "capabilities": ["wasm"]
   ```

   对核心模块而言，`wasm` 不需要 `requires` 标记，它是一项普通能力。（组件还需要 `wasm-components-v1`，见[构建进应用包](#4-构建进应用包)。）商店向用户显示的说明是“Run its own sandboxed functions on this device”。

2. 在你的 App Flow 检出目录中写入摘要并检查应用包：

   ```sh
   tools/octo check ~/apps/my-app/bundle
   ```

   应用包的其余部分齐全时（见 [QUICKSTART §8](QUICKSTART.zh-CN.md#8-检查应用包)），检查会通过，只有未签名的警告，`grants:` 行列出 `wasm`。以 `dev.example.texttools` 应用为例，输出如下：

   ```text
   dev.example.texttools 0.1.0 — PASSED
     [warning] publisher-signature: unsigned: accountability rests on the hub alone
     grants: capabilities {"wasm"}, hosts {}, storage none, agent none
   ```

   如果准入检查拒绝模块，按检查结果指出的问题修复：

   | 检查结果 | 修复方法 |
   | --- | --- |
   | `[refused] functions: the bundle carries 1 WebAssembly module(s) but does not declare the wasm capability` | 申请 `wasm`（第 1 步）。 |
   | `[refused] functions: the bundle carries 9 WebAssembly modules, over the 8 it may` | 把函数合并到 8 个以内的模块中。 |
   | `[refused] contents-invalid (fns/MyFunctions.wasm): a function module is named fns/<name>.wasm, the name [a-z0-9_-] and at most 64 characters` | 给文件改名，并让它直接位于 `fns/` 下。 |
   | `[refused] contents-invalid (lib/x.wasm): a WebAssembly module belongs in fns/, as fns/<name>.wasm` | 把文件移到 `fns/` 中。 |
   | `[refused] contents-invalid (fns/x.wasm): not a WebAssembly core module (magic and version 1)` | 改用针对 `wasm32-unknown-unknown` 构建的核心模块。组件需要不早于 App Hub #186 的 `hub`（见[准入检查查看什么](#准入检查查看什么)）。 |
   | `[warning] functions: the bundle declares the wasm capability but carries no fns/*.wasm` | 把模块复制到 `bundle/fns/`（见[构建](#构建)第 3 步）。 |
   | `hub: the bundle exceeds the size limit` | 把应用包的文件压到 8 MiB 以内。 |

#### 从 Splash 调用

调用 `wasm.<function>`，其中 `<function>` 是导出的函数名：

```splash
host.request("wasm.rank", {query: "cal" items: ["Local calls" "Calendar" "Mail"]}, fn(r){
    if r.is_ok { ranked = r.data.ranked } else { note = r.error }
})

host.request("wasm.md_to_html", "# Hello", fn(r){
    if r.is_ok { html = r.data.text } else { note = r.error }
})
```

这里 `r.data.ranked` 是 `["Calendar", "Local calls"]`，`r.data.text` 是 `<h1>Hello</h1>` 加一个换行符。服务按下表转换参数和输出：

| 脚本传入 | 函数收到 |
| --- | --- |
| 字符串 | 字符串的 UTF-8 字节。用 `export!` 实现函数。 |
| 其他值：对象、列表、数字或布尔值 | 该值的 JSON。用 `export_json!` 实现函数。 |

| 函数返回 | `r.data` |
| --- | --- |
| 有效的 JSON | 就是这个值 |
| 其他内容 | `{text: <按 UTF-8 解码的输出>}` |

要传入二进制数据（例如 `fs.read_bytes` 读出的图像），直接传字节列表。它以数字组成的 JSON 数组送到函数，`export_json!` 会把它读成 `Vec<u8>`。每个字节最多占 4 个字符，所以 1 MiB 的参数上限至少能容纳 256 KiB 二进制数据（**未验证**）。

#### 从 Agent 工具调用

附带 `tools.json` 的应用会得到自己的 Agent，因此还要声明 `agent` 块（见 [AI-SERVICES § 应用自己的 Agent](AI-SERVICES.zh-CN.md#应用自己的-agent)）。在 `bundle/tools.json` 的 `tools` 数组中加入下面这一项。它的 `host_method` 把工具映射到 `rank` 函数：

```json
{
  "name": "texttools.rank",
  "description": "Rank names against a query, earliest match first. Computes only.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "maxLength": 200 },
      "items": { "type": "array", "items": { "type": "string" }, "maxItems": 1000 },
      "limit": { "type": "integer", "minimum": 1, "maximum": 100 }
    },
    "required": ["query", "items"],
    "additionalProperties": false
  },
  "output_schema": {
    "type": "object",
    "properties": { "ranked": { "type": "array", "items": { "type": "string" } } },
    "required": ["ranked"]
  },
  "risk": "read",
  "background": true,
  "shareable": true,
  "implemented_by": "host-service",
  "host_method": "wasm.rank"
}
```

工具名以应用的命名空间开头，命名空间就是应用 id 的最后一段：`dev.example.texttools` 的命名空间是 `texttools`。App Hub 的 [`tools.json` 规则](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#toolsjson应用的工具)照常适用，但其中四条对 `wasm.<function>` 另有规定：

| 规则 | 其他 `host_method` 工具 | `wasm.<function>` |
| --- | --- | --- |
| 方法 | App Hub 审核过的列表中的方法 | 应用导出的任何函数：`wasm.` 之后只有一段，由 `[a-z0-9_]` 组成 |
| 最低 `risk` | 每个方法各有规定 | 没有；只做计算的函数用 `read` 即可 |
| `private_data` | 必须为 `true` | 不要求：函数只看得到自己的参数 |
| 能力 | 该方法的能力族 | `wasm` |

工具的参数是 JSON 对象，因此要用 `export_json!` 实现函数。函数也要返回对象，并声明对象类型的 `output_schema`，因为 OctoSense 的 Agent 内核 octos 只接受对象 schema。`rank` 因此返回 `{"ranked": […]}`，而不是单独一个列表。Agent 收到的是 `{"ok": true, "data": <output>}`，或 `{"ok": false, "error": {"kind": "app_error", "message": <error>}}`。

准入检查拒绝时会说明依据的规则，例如 `[refused] tools: texttools.rank: host_method "wasm.rank" requires the declared "wasm" service capability`。

#### 查看加载结果

用 `{}` 调用 `wasm.functions`，可以知道宿主能不能运行函数，以及加载了哪些函数。在没有 `wasm` 服务的宿主上，这次调用会返回 `no service answers "wasm" on this device`。`runtime.list` 和 `runtime.describe` 不会列出 `wasm` 的方法。`wasm.functions` 的返回结果包含：

| 字段 | 内容 |
| --- | --- |
| `functions` | 应用的函数名。 |
| `modules` | 每个模块文件一项：`file`、`bytes`、`load_ms`、`from_cache`（编译好的代码是否来自缓存）、`memory_bytes`（单次调用用到的最大内存，仅为高水位记录）、`invocations`（目前为止的调用次数）、`renewed`（等于 `invocations - 1`：第一次之后的每次调用都换上了新实例），以及 `instance_policy`（`"fresh-per-call"`）。 |
| `stats` | 每个已调用过的函数一项：`calls`、`errors`、`mean_us` 和 `max_us`。 |

这些计数从应用的工作线程启动时开始。工作线程空闲 5 秒后退出，计数从下一个工作线程重新开始。

不要把函数命名为 `functions`：`wasm.functions` 永远不会调用它。

#### 应用看到的错误

| `r.error` | 原因 | 修复方法 |
| --- | --- | --- |
| `this app was not granted "wasm", which "wasm.rank" needs` | 清单没有申请 `wasm`。 | 在 `capabilities` 中加入 `wasm`。 |
| `no service answers "wasm" on this device` | 宿主没有 `wasm` 服务：`card-host`、发布版本，或面向 Windows、iOS 或 OpenHarmony 的 OctoSense 构建。 | 在 macOS 或 Linux 上从 OctoSense `main` 构建的桌面端 Shell 中测试（见[测试](#测试)）。 |
| `<app id> has no function "rank"` | 没有模块导出这个名称。 | 与 `wasm.functions` 列出的名称核对。 |
| `<app id>'s bundle has no fns directory` | 应用申请了 `wasm`，却没有带模块。 | 加入 `fns/<name>.wasm`。 |
| `<file>: the module imports <name>; only octo.log is provided` | 某个依赖导入了 WASI 或 `wasm-bindgen` 的函数。 | 为 `wasm32-unknown-unknown` 构建，并去掉这个依赖。 |
| `<file>: the module does not export <name>` | crate 没有调用 `octosense_guest::abi!()`。 | 在 crate 中调用一次。 |
| `<file>: <function> is exported by another module too` | 两个模块导出了同名函数。 | 给其中一个函数改名。 |
| `the input is not what rank takes: <reason>` | 参数与函数的输入类型不符。 | 修正参数或类型。 |
| 函数自己的错误文本，例如 `the query is empty` | 函数返回了 `Err`。 | 在脚本中处理。 |
| `the call ran past its deadline`、`the function trapped: …` | 调用超出了[上限](#上限)，或触犯了[沙盒的限制](#沙盒禁止的操作)。 | 如果是 panic，到 Shell 的日志中查看 `panic: …` 一行；如果超时，减少每次调用的工作量。 |
| `wasm input exceeds 1 MiB` | 请求序列化后的输入超过 1 MiB。 | 每次调用少传一些输入。 |
| `wasm app queue is full; try again later` | 该应用已有 4 个请求在排队。 | 减少同时发出的请求，例如在上一个请求的回调中再发下一个。 |
| `wasm workers are busy; try again later` | 已有 4 个其他应用占用了工作线程；工作线程空闲 5 秒后才会退出。 | 稍后重试。 |
| `wasm input queue is full; try again later` | 所有应用的请求合计已缓冲 16 MiB 输入。 | 稍后重试。 |
| `wasm app admission changed; retry from the current app` | 调用运行期间，应用被更新、授权发生变化或被撤回。 | 重新调用。应用更新之后，下一次调用会加载新的模块。 |
| `the host service timed out` | 请求连同排队和加载用时超过 10 秒。 | 减少每次调用的工作量，并减少排队的调用。 |

服务会一并加载一个应用的全部模块。只要有一个模块加载失败，每次调用都返回这个模块的错误；下次调用时，服务会重新加载。

### 测试

第 3 到第 9 步在能运行函数的 Shell 中测试函数，因此都**未验证**。

1. 用 `tools/octo run` 在 `card-host` 中运行应用（见 [QUICKSTART §4](QUICKSTART.zh-CN.md#4-在桌面上运行)）。`card-host` 会接受应用包，但它没有 `wasm` 服务，每次调用都返回 `no service answers "wasm" on this device`。用它检查布局，以及缺少函数时应用显示什么。
2. 按 [PUBLISHING §4.2](PUBLISHING.zh-CN.md#42-在桌面端-shell-中安装并打开应用) 的说明，准备好[最小示例](#最小示例)第 1 步克隆的 OctoSense。
3. 构建并启动桌面端 Shell，系统应用改用 `desktop/system-apps-wasm-lab.json`，即默认的系统应用加上 Wasm Lab。默认构建在 macOS 和 Linux 上已包含 `wasm` 服务，不再需要 `--features wasm-lab`：

   ```sh
   cd <workspace>/OctoSense
   OCTOSENSE_SYSTEM_APPS="$PWD/desktop/system-apps-wasm-lab.json" \
     cargo run --release -p octosense
   ```

   OctoSense 用 `OCTOSENSE_SYSTEM_APPS=$PWD/desktop/system-apps-wasm-lab.json cargo build --locked -p octosense` 检查过不加任何特性的默认构建，再用 `--test-action launch-wasmlab` 运行了 Wasm Lab（见 [OctoSense 中的 WebAssembly § Wasm Lab](https://github.com/OctoSense-org/OctoSense/blob/main/docs/wasm.zh-CN.md#wasm-lab)）。

4. 从 dock 或 **Apps** 菜单打开 **Wasm Lab**。每张卡片调用一个函数，显示结果和往返耗时。模块加载时，Shell 的日志会出现类似这样的一行：`wasm os.wasmlab: wasmlab.wasm (433 KiB) compiled in … ms: find_slots, fuzzy_rank, md_to_html, rogue, text_diff`。
5. 点击 **Misbehave** 下的每个按钮。死循环、无休止的内存分配、panic 和失控递归都以错误结束，下一次调用照常返回结果。
6. 按 [PUBLISHING §4.1](PUBLISHING.zh-CN.md#41-发布到本地镜像) 的说明，把你自己的应用发布到本地镜像。
7. 退出 Shell，再用 [PUBLISHING §4.2](PUBLISHING.zh-CN.md#42-在桌面端-shell-中安装并打开应用) 中的命令重新启动它。
8. 从 dock 中的 **App Hub** 安装并打开你的应用。
9. 在 Shell 运行期间安装新版本，然后再调用一次函数：不必重启，下一次调用就会加载新的模块。更新时正在运行的调用会返回 `wasm app admission changed; retry from the current app`。

Agent 工具（无论是 Wasm Lab 的还是你的应用的）还需要 octos 内核（按[桌面端 README](https://github.com/OctoSense-org/OctoSense/blob/main/desktop/README.zh-CN.md#构建与运行) 的说明部署）和一个 AI 提供商。手机 Shell（即 Home）的默认构建在 Android 上同样运行这项服务，也有 `phone/system-apps-wasm-lab.json` 文件；构建方法见 OctoSense 的[手机端 README](https://github.com/OctoSense-org/OctoSense/blob/main/phone/README.zh-CN.md)（**未验证**）。

## 未决事项

OctoSense 的 [ADR 0011](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0011-apps-own-functions-in-webassembly.zh-CN.md) 记录了模块的设计，[ADR 0014](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0014-app-components-in-webassembly.zh-CN.md) 记录了组件的设计及其各个阶段。各事项的状态如下：

| 事项 | 状态 |
| --- | --- |
| 在 Shell 中运行组件（ADR 0014 第 2 阶段） | 已在 OctoSense #451 中合并（2026 年 10 月 10 日）：`wasm` 服务从 `fns/` 加载组件、每个应用一个实例、存储授权及其配额，以及比模块更大的输入上限。目前还没有任何发布版本包含它。 |
| App Hub 对组件的准入检查 | 已合并：[App Hub #186](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/186) 在 `wasm-components-v1` 下接受组件，并新增 `hub component-info`；[App Hub #188](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/188) 接受 `wasi:http`（需要 `net`）和 `octosense:host`。 |
| App Hub 对 crate 清单的使用 | 已在 [App Hub #189](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/189) 中合并：审核者能看到组件的 `octosense-crates` 清单，`hub check --advisory-db` 对照 RustSec 安全公告数据库检查它（见[构建所用的 crate](#构建所用的-crate)）。 |
| 把 SDK 发布到 crates.io | 尚未实现。ADR 0014 会在维护者批准后发布；在此之前，crate 通过 git 提交或路径依赖它。 |
| 组件的出站 HTTP 和宿主服务（第 3 阶段） | 已在 OctoSense #451 中合并：`wasi:http` 可以访问任何主机（按 OctoSense 2026 年 10 月 8 日的裁定，网络声明在安装时展示，运行时不强制），`octosense:host` 则经过与 `host.request` 相同的检查访问宿主服务；评审中的 [OctoSense #452](https://github.com/OctoSense-org/OctoSense/pull/452) 去掉对已声明能力族的检查。SDK 的 `http` 和 `host` 模块以及 `tools/octo wasm` 已支持它们；它们的测试在 Wasmtime 49 中针对本机服务器和模拟的宿主服务运行。 |
| 安装时编译，让手机跳过首次编译（第 3 阶段） | 已在 OctoSense #451 中合并，适用于已安装应用的函数：应用安装或更新时，函数被编译进磁盘缓存；系统应用的函数则在第一次调用时编译。ADR 0011 测得首次编译在桌面上需要 27–33 毫秒，在中端 Android 手机上需要 378–421 毫秒；之后在同一部手机上从缓存加载需要 5–11 毫秒。 |
| App Hub 目录中的共享组件（第 4 阶段） | 已合并的 [App Hub #190](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/190) 把它们发布到签名目录；`wasm` 服务加载应用所固定的共享组件，由 [OctoSense #454](https://github.com/OctoSense-org/OctoSense/pull/454) 实现，目前还是草稿。还没有任何签名目录发布过共享组件。 |
| 每个应用的 CPU 预算 | 尚未实现。上限按调用计算，所以一个应用可以用连续调用占满一个核心。 |
| 用真实模型调用 Agent 工具 | 未验证。OctoSense 的测试通过 Shell 的工具执行器调用 Wasm Lab 的工具，没有用到模型。 |
| Windows | Windows 构建自 OctoSense #451 起包含这项服务，运行时的测试也在 CI 中运行；在 Windows 上运行桌面版属于**未验证**。桌面版 0.1.0-rc.2 的 Windows 构建不包含它。 |
| iOS | 尚未实现。iOS 构建不包含这个运行时。iOS 不允许应用使用 JIT，Wasmtime 将只能改用自带的 Pulley 解释器；OctoSense #451 已为 OpenHarmony 加入并测试了 Pulley，ADR 0014 测得它的速度约为 Cranelift 的 1/32。iOS 也不允许应用下载原生代码，因此商店应用的函数在 iOS 上同样无法预先编译。 |
| OpenHarmony | 自 OctoSense #451 起包含，以 Pulley 运行，直到它的 JIT 策略明确为止；Home 的 OpenHarmony 发布构建已连同这项服务编译通过，但还没有设备运行过它（**未验证**）。 |
| 确定性的限制（fuel） | 尚未决定。 |

## 另请参阅

- OctoSense 的 [OctoSense 中的 WebAssembly](https://github.com/OctoSense-org/OctoSense/blob/main/docs/wasm.zh-CN.md)：`wasm` 服务在 `main` 上如何工作，包括它的上限、平台和测试。
- OctoSense 的 [ADR 0014](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0014-app-components-in-webassembly.zh-CN.md)：组件、它的 WASI 子集、JSON 映射和各个阶段。
- 本仓库的 SDK [sdk/rust/](../sdk/rust/README.zh-CN.md)：`octosense-component` crate 及其宏和 `http`、`host` 模块，示例和端到端测试。`tools/octo wasm` 用 [tools/wasm_component.py](../tools/wasm_component.py) 读取 WebAssembly。
- [HOST-API-V1](HOST-API-V1.zh-CN.md)：设备权限和 `location.get`。
- [CAPABILITIES § 宿主服务](CAPABILITIES.zh-CN.md#宿主服务)：`wasm` 与其他宿主服务。
- App Hub 的 [PUBLISHING § 检查结果](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#检查结果)和 [§ 把工具映射到共享服务](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#把工具映射到共享服务host_method)：准入检查对 `fns/` 和 `wasm.<function>` 的规则。
- App Hub 的 [SUBMITTING § Hub 目前做不到的事](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md#hub-目前做不到的事)：商店应用目前做不到的事，包括附带原生 Rust 代码。
- [Wasm Lab](https://github.com/OctoSense-org/OctoSense/tree/main/apps/wasmlab)：模块的参考应用，含它的客体 crate 和 `build.sh`。
