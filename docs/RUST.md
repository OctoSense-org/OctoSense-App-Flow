# Run your own Rust code

English | [简体中文](RUST.zh-CN.md)

A store app's bundle holds no native code, but it can carry your Rust code
as WebAssembly in its `fns/` folder. The shell's `wasm` service runs that code
in a sandbox, and the app's script calls it by name. There are two kinds:

- A **component** ([ADR 0014](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0014-app-components-in-webassembly.md)):
  you write ordinary Rust with this repository's SDK, and
  `tools/octo wasm build` turns it into `fns/<name>.wasm`. The script calls
  each `pub fn` as `wasm.<function>` with JSON, so there is no WIT and no glue
  code to write. A component keeps its state between calls, and it has a
  clock and random numbers. With the `storage` capability, it also has the
  app's own files; with `net`, HTTP to any host ([Network](#network)); and it
  can call the host services the app is granted
  ([Host services](#host-services)).
- A **core module** ([ADR 0011](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0011-apps-own-functions-in-webassembly.md)):
  functions over bytes or JSON, written with a copied guest crate, and with
  nothing but their input. [Core modules](#core-modules-adr-0011) at the end
  of this page covers them.

**OctoSense `main` runs components; no release does yet.** The runtime
([OctoSense #436](https://github.com/OctoSense-org/OctoSense/pull/436)) and the `wasm` service that loads
components, with HTTP and host services ([OctoSense #451](https://github.com/OctoSense-org/OctoSense/pull/451)),
merged on 10 October 2026, and App Hub's gate admits them
([App Hub #186](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/186) and, for `wasi:http` and `octosense:host`,
[App Hub #188](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/188)). Desktop 0.1.0-rc.2 and Home 0.1.0-beta.2 pin
an App Hub that predates `wasm-components-v1`, so their stores refuse such an
app at install. The first desktop or Home release cut from OctoSense `main` at
or after `04100758` will be the first to run one. Verified here on 10 October
2026: this page's template component, built with `tools/octo wasm build` and
admitted by `hub check`, answered `wasm.count`, `wasm.greet` and
`wasm.parse_number` through the shell's `wasm` service, built from OctoSense
`main` (`80b27693`) and run in its test harness, which dispatches a call as
`host.request` does; its first load compiled in 14 ms. Still **unverified**:
a store install of a published app with components, an agent tool calling
one, and any phone.

| | Core module (ADR 0011) | Component (ADR 0014) |
| --- | --- | --- |
| Write and build it | Copy OctoSense's guest crate; `cargo build --target wasm32-unknown-unknown` | `tools/octo wasm new`, then `tools/octo wasm build` (this page) |
| What it reaches | Its input only | The clock, random numbers and, with `storage`, the app's storage folder; with `net`, the network, any host; and the host services the app is granted. |
| Between calls | Starts fresh every call | Keeps its state |
| The manifest | `wasm` | `wasm`, and `requires: ["wasm-components-v1"]`; `storage` for files; `net` for HTTP |
| App Hub's gate (`hub check`) | Admits it from app contract 1.7 | `main` admits it under `requires: ["wasm-components-v1"]` (App Hub #186), with `wasi:http` and `octosense:host` imports (App Hub #188), and says what each component reaches. A `hub` older than #186 answers `app <id> needs a newer host: wasm-components-v1` at `hub stamp`; without the requirement, it finds `not a WebAssembly core module (magic and version 1)`. |
| OctoSense `main` | Runs it on macOS, Linux and Android | Has run it since 10 October 2026 (OctoSense #451): the `wasm` service loads components from `fns/`, with HTTP to any host and `octosense:host`. Windows builds have included the service since the same change; a run there is **unverified**. Android and OpenHarmony builds link the runtime, but no component has run on a phone yet (**unverified**). |
| `card-host` | Admits the app; every call answers `no service answers "wasm" on this device` | Has no `wasm` service either. Built from App Hub `main`, it admits the manifest, since it runs the same contract check as `hub` (**unverified** by a run here). |
| Releases | Desktop 0.1.0-rc.2 runs it on macOS and Linux; no Home release does | None runs it. Desktop 0.1.0-rc.2 and Home 0.1.0-beta.2 refuse the manifest at install (`needs a newer host: wasm-components-v1`). |

Every command on this page was run on macOS (Apple silicon) with Rust
1.97.1, unless it is marked **unverified**. The examples use an app that
`tools/octo new` made in `~/apps/my-app`
([QUICKSTART §3](QUICKSTART.md#3-create-an-app)), with the id
`dev.example.texttools`.

## Choose a route

| You need | Route | Read |
| --- | --- | --- |
| Computation with crates.io crates: parsing, formats, scoring, crypto, image processing | A component | [Write a component](#write-a-component) |
| Pure computation in an app that must run today | A core module | [Core modules](#core-modules-adr-0011) |
| The camera, the microphone or the location | Host APIs: the `camera`, `microphone` and `location` capabilities, their permission methods and `location.get` | [HOST-API-V1 §3](HOST-API-V1.md#3-request-device-access-in-the-foreground) |
| The network | Splash's `net`, to the hosts in `network.hosts`. A component reaches any host with `octosense_component::http` and `net` (on OctoSense `main`; in no release yet): an app's network declarations are shown at install and not enforced while it runs. A core module reaches no network: fetch the data in Splash, then pass it in. | [SCRIPT-API § Network](SCRIPT-API.md#network), [Network](#network) |
| The app's host services, such as `runtime.list` | `host.request` in Splash, or `octosense_component::host` in a component (on OctoSense `main`; in no release yet) | [Host services](#host-services) |
| Files | The app's own storage, through `fs.*` in Splash, or through `std::fs` in a component when the app has `storage`. | [SCRIPT-API § Storage](SCRIPT-API.md#storage-fs) |
| Something a Rust crate already does | Not by calling the crate from Splash. Build it into a component ([Write a component](#write-a-component); first run `tools/octo wasm doctor`, which names the crates whose job OctoSense already does), or into a core module for pure computation; propose a shared host service in OctoSense and contribute its adapter, with method descriptors, app-scoped resources and tests ([HOST-SERVICES § Add a host service](HOST-SERVICES.md#add-a-host-service)); or run it in your own backend, reached through `net` or the authenticated backend API ([HOST-API-V1 §4](HOST-API-V1.md#4-connect-the-apps-backend)). A crate in a shell's `Cargo.lock` is not callable from Splash, and a `.so`, `.dylib` or `Cargo.toml` in a bundle adds nothing: the gate refuses it. | This page, [HOST-SERVICES](HOST-SERVICES.md), [HOST-API-V1 §4](HOST-API-V1.md#4-connect-the-apps-backend) |
| A native library, threads or OS calls | Not available to a store app. App Hub's gate refuses native libraries, and native code ships only inside a shell release. | App Hub's [delivery paths](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/DEVELOPMENT.md#choose-a-delivery-path) |

What a Splash app can call is the host API surface, not the Rust crates behind
it: [HOST-API-FAMILIES](HOST-API-FAMILIES.md) lists every `host.request` family
with who it serves, [RUNTIME-TYPES](RUNTIME-TYPES.md) every type name the
runtime resolves, [SCRIPT-API](SCRIPT-API.md) the supported subset, and
`runtime.list` on the installed host the methods it implements
([HOST-API-V1 §2](HOST-API-V1.md#2-discover-before-offering-an-optional-feature)).

## Write a component

### 1. Set up Rust

Components need Rust 1.88 or newer: Rust builds components for
`wasm32-wasip2` since 1.82, and `wit-bindgen`, which the SDK uses, builds
with crates (`wit-component`, `wit-parser` 0.259) that need 1.88. Add the target, then let `tools/octo` check the toolchain. Run these
from your App Flow checkout:

```sh
rustup target add wasm32-wasip2
tools/octo wasm doctor
```

On a machine that already has the target, `rustup` prints
`info: component rust-std for target wasm32-wasip2 is up to date`, and
`doctor` prints:

```text
octo wasm doctor
  [ok]   cargo: /Users/<you>/.cargo/bin/cargo
  [ok]   rustc 1.97.1 (8bab26f4f 2026-07-14)
  [ok]   target wasm32-wasip2 is installed
  [info] no crate checked: pass --crate DIR, or run it in an app directory with components/<name>/
```

Installing the target on a machine without it is **unverified** here.

### 2. Create the crate

```sh
tools/octo wasm new text-tools --app ~/apps/my-app
```

It prints `created …/my-app/components/text-tools` and writes a crate from
[templates/rust-component](../templates/rust-component/). Only the built
component goes into the bundle:

```text
~/apps/my-app/
  bundle/
    fns/text-tools.wasm      the component, after `tools/octo wasm build`
  components/text-tools/     your crate; not in the bundle
    Cargo.toml
    src/lib.rs
    .gitignore               /target/
```

The name, here `text-tools`, is the crate's and the file's: 1 to 64
characters of `[a-z0-9_-]`, starting with a letter. Without `--app`, the
command uses the current directory, which must hold `bundle/manifest.json`.

The crate gets the SDK, `octosense-component`, in one of two ways. A comment
in its `Cargo.toml` says which, and why:

| `--sdk` | `Cargo.toml` gets | When |
| --- | --- | --- |
| `auto` (the default) | The git form when it can, the path form otherwise | — |
| `git` | `octosense-component = { git = "https://github.com/OctoSense-org/OctoSense-App-Flow", rev = "<commit>" }`, where the commit is the newest one on App Flow's `main` (as last fetched) that your checkout has and that contains the SDK | It builds the same on any machine, so commit it with the app. To move to a newer SDK, change `rev`, then run `cargo update -p octosense-component`. |
| `path` | `octosense-component = { path = "<your App Flow checkout>/sdk/rust/octosense-component" }`, relative when the two share a folder | It needs no network and follows your checkout, but another machine needs App Flow in the same place. An absolute path names your machine, so keep it out of a public repository. |

The SDK is not on crates.io yet; ADR 0014 publishes it there once a
maintainer approves. Until this repository's `main` has the SDK, `auto`
writes the path form and says
`App Flow's main (origin/main, as last fetched) does not have the SDK yet`.
The git form was tested only against a local repository, so building with it
is **unverified**.

The crate has its own `[workspace]`, so a Cargo workspace around your app
does not claim it, and the release profile is set for size
(`opt-level = "s"`, `lto`, `strip`).

### 3. Write the functions

Put `#[octosense_component::export]` on an inline module. Every `pub fn` in
it becomes a function the app's script can call; every other item stays
ordinary Rust, and the rest of the crate, with any dependency, is yours. This
is the template's `src/lib.rs` without its comments:

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

The macro writes the component's WIT world from these signatures, generates
the `wit-bindgen` glue, and converts between your types and the generated
ones. A `pub struct` with named fields becomes a WIT record, a `pub enum` of
unit variants a WIT enum, and any other `pub enum` (each variant holding
nothing or one value) a WIT variant. [Types](#types) lists what a function may
take and return.

Names keep your Rust spelling in the script. WIT spells `parse_number` and a
field `word_count` in kebab case (`parse-number`, `word-count`), and the
`wasm` service accepts `wasm.parse_number` and returns `word_count`. The kebab
spellings are accepted on the way in too.

A type the macro cannot map fails the build with what to use instead. For
example, a `HashMap` parameter fails with
`maps and sets are not WIT types: use Vec<(K, V)>, Vec<T> or a pub struct`.
It also refuses `usize`, references other than a `&str` or `&[u8]`
parameter, generic and `async` functions, recursive types, two items with
one WIT name, and a function named `functions`, which `wasm.functions`
already is.

Two more things the SDK gives a function:

- `octosense_component::log(line)` writes a line to stderr, which ADR 0014
  makes one of the app's log lines; `println!` and `eprintln!` work the same.
- A `static`, such as a cache in a `Mutex` or an `AtomicU64`, lives as long as
  the component's instance, so it is still there at the next call
  ([State](#state)).

Test the functions natively, from `~/apps/my-app`:

```sh
cargo test --manifest-path components/text-tools/Cargo.toml
```

The output includes `test tests::counts_words_and_lines ... ok` and
`test tests::a_bad_number_is_an_error ... ok`.

### 4. Build it into the bundle

```sh
tools/octo wasm build --app ~/apps/my-app
```

For each crate in `components/` (or each `--crate DIR`), it:

1. runs `cargo build --release --target wasm32-wasip2`;
2. reads the component's imports, and stops without changing the bundle if
   one is outside `wasi:cli`, `wasi:clocks`, `wasi:filesystem`, `wasi:http`,
   `wasi:io`, `wasi:random` and `octosense:host`, the packages the `wasm`
   service gives a component;
3. records in the component the crates it is built from
   ([The crates it is built from](#the-crates-it-is-built-from));
4. copies it to `bundle/fns/<name>.wasm`;
5. adds `wasm` to the manifest's `capabilities` and `wasm-components-v1` to
   its `requires`, `storage` when a component imports `wasi:filesystem`,
   and `net` when one imports `wasi:http`, saying what it changed. It never
   adds a host to `network.hosts` or asks for one ([Network](#network));
6. warns about what the gate or the service would refuse later: more than 8
   files in `fns/`, two files exporting one function name, a bundle over
   8 MiB;
7. stamps the bundle when it finds `hub`.

For the template, after Cargo's own output, it prints:

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

The template's functions never read the time, but its component imports
`wasi:clocks/monotonic-clock`, as every component built with Rust's standard
library here does.

A function that opens a socket builds, but `tools/octo wasm build` refuses
the component. With `std::net::TcpStream::connect(addr)` in a function, it
prints:

```text
octo: text-tools imports what no host gives a component, so the wasm service would refuse to load it and App Hub's gate refuses the bundle:
  wasi:sockets/network@0.2.12, wasi:sockets/instance-network@0.2.12, wasi:sockets/udp@0.2.12, wasi:sockets/udp-create-socket@0.2.12, wasi:sockets/tcp@0.2.12, wasi:sockets/tcp-create-socket@0.2.12, wasi:sockets/ip-name-lookup@0.2.12:
    network sockets (std::net, or a crate such as reqwest, ureq or tokio's net, which open sockets): a component has none. It reaches the network over HTTP through wasi:http, with octosense_component::http, once the manifest has `net`.
```

To see what a built file holds, run `tools/octo wasm info`, here from
`~/apps/my-app`:

```sh
tools/octo wasm info bundle/fns/text-tools.wasm
```

It prints the file's kind, what it reaches, every import and every function
with its WIT signature, the crates it is built from, and what the manifest
needs. For this page's `api-client` component ([Network](#network)), it
says `reaches: the clock and the network, but no files or other app` and
`the manifest needs "wasm" in capabilities, "wasm-components-v1" in requires, "net" in capabilities (it imports wasi:http)`.
It asks App Hub's `hub component-info` when the
`hub` it finds has that command (App Hub #186), and otherwise reads the file
itself. Both give the same answer for the SDK's examples and the template,
and for this page's `api-client` and `host-calls` components; `--json` prints
it as `hub component-info` does, with the crate list as `"crates"`, which octo
always reads from the file itself.

### 5. Call it from the app

Verified through the `wasm` service's test harness, built from OctoSense
`main` on 10 October 2026 (see the top of this page), not from a running
app; no release runs it yet.

```splash
host.request("wasm.count", {text: "one two\nthree"}, fn(r){
    if r.is_ok { words = r.data.words } else { status = r.error }
})

host.request("wasm.parse_number", "2.5", fn(r){
    if r.is_ok { value = r.data } else { status = r.error }
})
```

The arguments are an object keyed by the parameter names, an array in
parameter order, or, for a function of one parameter, the value itself. The
result arrives in `r.data` as JSON ([Types](#types)), and an `Err` in
`r.error`: `wasm.parse_number` with `"two"` fails with
`"two" is not a number`. `wasm.functions` lists each function with its WIT
signature.

An agent tool maps to a component's function as to a module's, with
`host_method: "wasm.<function>"`
([Call it from an agent tool](#call-it-from-an-agent-tool)); that is
**unverified** for components.

### 6. Test it

- Test the logic natively with `cargo test`, as in step 3.
- `tools/octo wasm call <function> [JSON]` calls one function of the built
  component from the command line, through OctoSense's `wasm_call` example
  ([OctoSense #455](https://github.com/OctoSense-org/OctoSense/pull/455), in review; verified here against its head). It needs an
  OctoSense checkout that carries that change, its branch until it merges and
  then `main` (`OCTOSENSE_REPO`, or `OctoSense` beside this repository), and
  its first run compiles the runtime. Each call gets a fresh instance, and
  `octosense:host` calls fail with `needs a shell`; the rest runs as in the
  shell.
- `tools/octo run` starts the app in `card-host`, which has no `wasm`
  service, so every call answers `no service answers "wasm" on this device`.
  Use it for the layout and for what the app shows without its functions.
  Built from App Hub `main`, `card-host` admits the manifest (**unverified**
  by a run here; see the table at the top).
- `tools/octo check` runs App Hub's gate. With `hub` built from App Hub
  `main`, the gate admits the component and tells the reviewer what it
  reaches ([What the gate checks](#what-the-gate-checks)). A `hub` older than
  App Hub #186 stops at the stamp:
  `hub: app dev.example.texttools needs a newer host: wasm-components-v1`.
  A fresh `tools/octo new` app is refused until the screenshot its listing
  names exists; `tools/octo check` says how to capture one.
- Running the app's functions in OctoSense needs a shell built from `main` at
  or after OctoSense #451, since no release runs components yet. Test as for
  a module ([Test it](#test-it), steps 2 to 9). The desktop app was not run
  here (**unverified**); the service's own test harness was (see the top of
  this page).

The SDK's own tests build its examples and the template with plain cargo for
`wasm32-wasip2`, load them in Wasmtime 49 with WASI 0.2 as ADR 0014's
runtime does, and call every function. For HTTP and host services they link `wasi:http`
(`wasmtime-wasi-http` 49) and `octosense:host` as OctoSense's runtime does,
with copies of its hooks: the `http-client` example sends requests to a local
HTTP/1.1 server, by address and by name, with no grant, and one to a server
that never answers ends with the call; the `host-services` example calls fake
host services. Run them from `sdk/rust/`:

```sh
cargo test --locked --workspace
```

The output includes `test every_type_mapping_crosses_both_ways ... ok`,
`test the_exports_run_with_an_unmodified_crate_files_and_a_clock ... ok`,
`test the_template_octo_wasm_new_writes_runs_as_a_component ... ok`,
`test http_reaches_any_host ... ok`,
`test a_request_that_never_answers_ends_at_the_deadline ... ok`,
`test a_component_calls_its_apps_granted_host_services ... ok` and
`test a_component_imports_http_and_host_services_only_when_it_calls_them ... ok`.
CI runs them on Ubuntu, with the `tools/` tests, which build a new crate with
`tools/octo wasm new` and `tools/octo wasm build`.

### 7. Publish it

The release workflow that `tools/octo publish-github` installs builds every
crate in `components/` itself, from the tagged commit, with the Rust it pins
(1.97.1), records the crates each component is built from as `tools/octo wasm
build` does, and writes each component to `bundle/fns/<name>.wasm` before
GitHub attests the bundle. The release then carries binaries built from the
source it names, and you need not commit `fns/*.wasm`: `tools/octo wasm build`
makes them for your own runs, and the release replaces them. For each crate:

- Commit its `Cargo.lock`, since the release builds with `--locked`. Without
  one it stops:
  `::error::app/components/<name> has no Cargo.lock: commit it, so the release builds what you tested`.
- Depend on the SDK by git (`--sdk git`), since a path names your machine.
  With one it stops:
  `::error::app/components/<name> takes the SDK from a local path, which the release cannot build; depend on OctoSense App Flow by git (tools/octo wasm new --sdk git)`.

With the same Rust, the same crate and the same `Cargo.lock`, the release
writes what you wrote, crate list included. For the template's crate with the
SDK by git, at an App Flow commit, `tools/octo wasm build` wrote
`bundle/fns/text-tools.wasm` (83,061 bytes), and the workflow's step, run
from its own script on macOS, then printed
`unchanged: bundle/fns/text-tools.wasm, 83,061 bytes built from app/components/text-tools and the 6 crates its octosense-crates section lists`.
With the SDK by path, cargo built the same component, byte for byte, but its
crate list names the SDK's source as `path` instead of
`git+https://github.com/OctoSense-org/OctoSense-App-Flow#<commit>`, so the
file differs from the release's there (82,969 bytes). A release run on GitHub
is **unverified**. The publisher toolchain (`tools/publisher-toolchain.json`)
names App Hub `40abb23b`, the merge of App Hub #191: the App Hub revision
OctoSense `main` carries, whose gate admits components with `wasi:http` and
`octosense:host` imports (App Hub #186 and #188); it also includes App Hub
#190, shared components in the catalog. It predates App Hub #189, so this
`hub` prints no crate list and runs no advisory check; a `hub` built from
App Hub `main` at or after #189 does.

## What a component can use

### Types

What a function may take and return, its WIT type, and its JSON in the
script (ADR 0014):

| Rust | WIT | JSON in the script |
| --- | --- | --- |
| `bool` | `bool` | `true` or `false` |
| `u8`, `u16`, `u32`, `u64`, `i8`, `i16`, `i32`, `i64` | `u8` … `u64`, `s8` … `s64` | A number, range-checked |
| `f32`, `f64` | `f32`, `f64` | A number |
| `char` | `char` | A string of one character |
| `String`; a parameter may be `&str` | `string` | A string |
| `Vec<u8>`; a parameter may be `&[u8]` | `list<u8>` | Base64 text; an array of numbers is accepted too |
| `Vec<T>` | `list<T>` | An array |
| `Option<T>` | `option<T>` | `null` or the value |
| A tuple, such as `(u32, String)` | `tuple<u32, string>` | An array |
| A `pub struct` with named fields | `record` | An object keyed by the field names |
| A `pub enum` of unit variants | `enum` | The variant's name, such as `"short"` |
| Any other `pub enum` | `variant` | `"case"`, or `{"case": value}` for a variant with a value |
| `Result<T, String>`, `Result<(), String>` | `result<T, string>`, `result<_, string>` | The value; an `Err` is the call's error |
| No return value | No result | `null` |

The macro refuses `usize` and `isize` (use `u32`/`u64` or `i32`/`i64`),
maps and sets (use `Vec<(K, V)>`, `Vec<T>` or a `pub struct`), `Box`, `Rc`,
`Arc` and `Cow`, and an error type other than `String` (map it with
`.map_err(|e| e.to_string())`).

### What it reaches

ADR 0014 gives a component the WASI 0.2 interfaces below and
`octosense:host`. The SDK's tests use the same set in Wasmtime 49, and
OctoSense `main`'s `wasm` service gives the same (OctoSense #451).

| | A component |
| --- | --- |
| The clock and random numbers | Yes: `std::time`, and random numbers through crates such as `getrandom` 0.4, which the SDK's tests call |
| Files | Only with `storage`: the app's storage folder is `/`, read and write, through `std::fs`; nothing else of the device's files. Without `storage`, it has no folder. |
| stdout and stderr | They become the app's log lines |
| The environment, arguments and stdin | Empty |
| The network | Any host, over HTTPS or plain HTTP, through `wasi:http`, with `net` in the manifest ([Network](#network)). It has no sockets: `wasi:sockets` is refused. |
| Threads | No: `wasm32-wasip2` has none |
| Host services | The services the app is granted, as its script calls them, through `octosense:host` ([Host services](#host-services)) |
| Other apps | No |

### Network

On OctoSense `main` since OctoSense #451 (10 October 2026); in no release
yet. OctoSense's own tests send a component's requests to a local server, and
the SDK's tests do the same in Wasmtime 49, with a copy of OctoSense's runtime
hook. Not run in a shell here.

A component reaches the network only through `wasi:http`, and it reaches any
host. Under OctoSense's ruling of 8 October 2026, an app's network
declarations (`net`, `network.hosts`) are shown at install and not enforced
while the app runs: the OS and the host's API surface are the boundary. The
manifest still needs `net`, so that the app's permissions say it uses the
network (App Hub's gate refuses a component that imports `wasi:http`
without it; see [What the gate checks](#what-the-gate-checks)):

```json
"capabilities": ["wasm", "net"]
```

A component needs no `network.hosts`. The app's script keeps its own rule:
the Splash runtime still lets its `net` reach only the hosts listed there
([CAPABILITIES § Network](CAPABILITIES.md#network)).

Then send requests with the SDK's `octosense_component::http`. This crate,
`components/api-client` in the example app, builds into
`fns/api-client.wasm`:

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

| `octosense_component::http` | What it does |
| --- | --- |
| `get(url)` | Sends a `GET` and returns the [`Response`](../sdk/rust/octosense-component/src/http.rs) |
| `post(url, content_type, body)` | Sends a `POST` with that body, its `content-type` and its `content-length` |
| `Request::new(method, url)`, `Request::get(url)`, `Request::post(url)` | Builds any request: `.header(name, value)`, `.body(bytes)`, `.timeout(duration)`, then `.send()` |
| `Response` | `status`, `headers` and the whole `body`; `.text()` and `.header(name)` |

A request blocks until the whole response has arrived. Any status is a
response, so a `404` is `Ok`. An `Err` is a request that got no response,
as readable text, and `?` makes it the call's error in the script. The
component imports `wasi:http` only when it calls these functions, and a
crate that opens sockets, such as `reqwest`, `ureq` or `tokio`'s `net`,
still does not work.

OctoSense `main`'s runtime (OctoSense #451) handles every request this way:

- The request goes to whatever host its URL names, over HTTPS or plain HTTP,
  this device and its local network included. The runtime refuses no
  request and logs none.
- A call of a component that imports `wasi:http` gets a 10 s deadline
  instead of 2 s, and each request's connect, first-byte and between-bytes
  timeouts end with the call. A request to a server that never answers then
  fails inside the component; in the SDK's tests, the error reads
  `the request to http://127.0.0.1:<port>/ failed: the server did not answer in time (ErrorCode::ConnectionReadTimeout)`.

`tools/octo wasm build` adds `net` when a component imports `wasi:http`, and
it never adds a host or asks for one. In the example app, which has no `net`
yet, building `api-client` alone:

```sh
tools/octo wasm build --app ~/apps/my-app --crate ~/apps/my-app/components/api-client
```

prints, after Cargo's own output:

```text
wrote bundle/fns/api-client.wasm: 108,794 bytes, a component that reaches the clock and the network, but no files or other app
  wasm.fetch(url: string) -> result<record { status: u16, body: string }, string>
  built from 6 crates (tools/octo wasm info lists them)
bundle/manifest.json:
  added "net" to capabilities: api-client imports wasi:http, the network
```

### Host services

On OctoSense `main` since OctoSense #451 (10 October 2026); in no release
yet. The SDK's tests call fake host services in Wasmtime 49, held to a copy of
OctoSense's rules. Not run in a shell here.

`octosense_component::host::request(service, args)` calls one of the app's
host services as its script's `host.request` does: `service` is
`family.method`, and `args` is JSON text. It returns the service's JSON
answer as text, or why there is none as `Err`. Build the arguments and read
the answer with any JSON crate, such as `serde_json`. This crate,
`components/host-calls`, builds into `fns/host-calls.wasm`:

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

The component imports `octosense:host/services@0.1.0` only when it calls
`host::request`. The SDK carries the interface's WIT, OctoSense's
[`octosense-host.wit`](../sdk/rust/octosense-component/wit/octosense-host.wit).
OctoSense `main` holds every call to these rules
([OctoSense #452](https://github.com/OctoSense-org/OctoSense/pull/452), in review, drops the declared-families rule in the first item: a call then
reaches the dispatcher whatever the manifest declares, and a service that
needs a grant checks it itself):

- The import needs no grant of its own. A call reaches only the families the
  manifest grants in `capabilities` (a system app's own namespace too), so
  `runtime.list` needs `runtime`.
- The host makes the call as the app's script would, with the same app id,
  but never with a sheet or a prompt, so only the methods a background
  surface may call work.
- `wasm.*` is refused, and the arguments must be JSON text.
- The call's deadline bounds the wait.

What the host refuses reaches the function as its `Err`, for example
`dev.example.texttools was not granted the mail service, which mail.list needs`,
`a component cannot call wasm.*: its app's functions are already running it`,
`<service>: the arguments are not JSON: <why>`,
`<service> did not answer before the call's deadline`, or
`this host gives a component no host services`.

### State

One instance of each component lives for as long as the app's worker, so a
`static` (a parsed document, a cache, a model) is still there at the next
call. A trap or a deadline ends the instance, and the next call starts a new
one. An app update, a changed grant or a withdrawal discards it, as for
modules (ADR 0014). The SDK's tests show a `static` counter kept between two
calls on one instance; the shell keeps the instance while the app's worker
lives, and a worker that holds a component's instance exits after 60 idle
seconds (one that runs only modules, after 5). Keep what must survive in the
app's storage.

### What cannot build or run

`tools/octo wasm doctor --crate components/<name>` reads the crate's
dependencies with `cargo metadata --filter-platform wasm32-wasip2` and names
the ones it knows cannot build or run in a component. When a build fails,
`tools/octo wasm build` prints the same findings. For the template, it
reports `none of the 6 crates it links is known not to build or run in a component`.

| The crate | Why | Instead |
| --- | --- | --- |
| C libraries: `openssl-sys`, `libsqlite3-sys`, and crates that compile C with `cc` or `cmake` | They need a C compiler for WASI, such as wasi-sdk's clang | A pure-Rust crate or feature: RustCrypto's `sha2`, `hmac` or `aes-gcm` for cryptography; files in the app's storage, or the script's storage, for data |
| The network: `reqwest`, `hyper`, `ureq`, `curl`, `mio`, `socket2`, `tungstenite`, `native-tls` | They open sockets, and a component has none | `octosense_component::http`, with `net` ([Network](#network)), or fetch with `net` in Splash, then pass the data in |
| Threads: `rayon` | `wasm32-wasip2` has no threads | Plain iterators, or the crate without its parallel feature |
| `tokio` with `rt-multi-thread`, `net`, `fs`, `process` or `signal` | They need threads, the network or the device | Plain functions: a component's functions are ordinary calls, with no async runtime |
| JavaScript bindings: `wasm-bindgen`, `js-sys`, `web-sys` | A component has no JavaScript | The crate without its `js` or `wasm-bindgen` feature |
| Native code: `pyo3`, `jni`, `libloading`; Unix calls: `nix` | Neither exists in WASI | — |

The list is what `tools/octo` knows, not every crate that fails. A
dependency that builds can still import what no host gives; step 4 catches
that.

### What OctoSense already provides

OctoSense links many crates natively, such as `pulldown-cmark` for Makepad's
Markdown widget and the Markdown editor, but a component cannot call native
code: an app reaches them only through Splash's widgets and functions and the
host services it is granted. For a direct dependency whose usual job
OctoSense already does for a store app, `tools/octo wasm doctor` prints an
`info` line, which does not fail the check:

| The crate | What the app uses instead | Ship the crate | Source |
| --- | --- | --- | --- |
| `pulldown-cmark`, `comrak`, `markdown` | Splash's `Markdown` widget, which renders Markdown, tables included | Only to produce HTML or to read Markdown as data | [SCRIPT-API § Widgets](SCRIPT-API.md#widgets-available-to-an-app) |
| `feed-rs`, `rss`, `atom_syndication` | `text.parse_feed(style)` in the script: each RSS or Atom item's title, link, source, publication time, summary and image | Only for what `parse_feed` does not read | [SCRIPT-API § Data and strings](SCRIPT-API.md#data-and-strings) |
| `async-openai`, `genai`, `ollama-rs`, `openai-api-rs` | `model.complete`, with the `model` capability: one-shot, schema-checked requests to the person's own AI providers, within a daily budget | Never with a provider key: an app holds none | [AI-SERVICES § One-shot model calls](AI-SERVICES.md#one-shot-model-calls-model) |

For the SDK's `markdown-tools` example, which turns Markdown into HTML,
`tools/octo wasm doctor --crate sdk/rust/examples/markdown-tools` prints,
after its `[ok]` lines:

```text
  [info] pulldown-cmark 0.13.4: OctoSense renders Markdown itself: Splash's Markdown widget shows it, tables included. Ship the crate only to produce HTML or to read Markdown as data. (docs/SCRIPT-API.md#widgets-available-to-an-app)
```

The table holds only what this repository's docs say a store app may use.
Engine services such as `photo`, `pdf` or `word` are for system apps, so
`doctor` offers none of them. A crate that opens network sockets, such as
`reqwest` or `ureq`, is a failure rather than a hint: `doctor` says that a
component reaches the network with `octosense_component::http` instead
([What cannot build or run](#what-cannot-build-or-run), [Network](#network)).

### The crates it is built from

`tools/octo wasm build` records in each component the crates it is built
from, and the release workflow records the same list
([7. Publish it](#7-publish-it)). App Hub's gate shows the list to the
reviewers and checks it against the
[RustSec advisory database](https://rustsec.org/). App Hub `main` does both
since App Hub #189: `hub check` printed `is built from 6 crates: …` for the
template here, and `hub check --advisory-db <dir>` checks the list against the
database (not run here).

The list names every package whose code the component links: what the
crate's normal dependencies reach for `wasm32-wasip2`, as
`cargo metadata --filter-platform wasm32-wasip2` resolves them, without the
crate itself. Build and dev dependencies run on the build machine, and so do
proc macros, so neither a proc macro nor what only it uses is in the list.
The template's list has six crates, `bitflags`, `octosense-component`,
`wasi` and `wasip2` (for `octosense_component::http`) and two versions of
`wit-bindgen`, without `syn`, `wit-parser` and the other crates that the SDK's
and `wit-bindgen`'s macros use to write code. Each entry has:

| Field | What it holds |
| --- | --- |
| `name`, `version` | The package's name and version |
| `source` | `crates.io`; `git+<url>#<commit>` for a git dependency, without its `?rev=` or `?branch=`; `path` for a local one, such as the SDK with `--sdk path`; another registry's source as Cargo writes it |
| `checksum` | The package's SHA-256 from the crate's `Cargo.lock`, for a registry package. Git and path packages have none. |

The list is a WebAssembly custom section named `octosense-crates` at the very
end of the file. Its payload is UTF-8 JSON, with sorted keys and no spaces,
of `{"schema": 1, "crates": [...]}`, the crates sorted by name and version.
Building again replaces it, so a file holds one. Wasmtime 49 loads a
component with the section and runs it as before: the SDK's end-to-end tests
passed on a `markdown-tools` component that carried its list
(`OCTOSENSE_COMPONENT_WASM=<file> cargo test --locked -p octosense-component-e2e`,
in `sdk/rust/`).
The shell's `wasm` service loads one: this page's template, built with the
SDK by path, answered through it here.

`tools/octo wasm info` prints the list. For the template, built with the SDK
by path:

```text
built from 6 crates, as its octosense-crates section lists them:
  bitflags 2.13.2, crates.io
  octosense-component 0.1.0, path
  wasi 0.14.7+wasi-0.2.4, crates.io
  wasip2 1.0.4+wasi-0.2.12, crates.io
  wit-bindgen 0.57.1, crates.io
  wit-bindgen 0.62.0, crates.io
```

With `--json`, `"crates"` holds the entries, checksums included. A file built
another way says `crates: not recorded`.

### What the gate checks

These findings come from App Hub `main`: App Hub #186 and, for `wasi:http`
and `octosense:host`, App Hub #188, merged on 9 and 10 October 2026. A `hub`
older than #186 refuses a bundle that requires `wasm-components-v1` before
any check runs. On the example app, `tools/octo check` prints, besides its
other findings:

```text
  [warning] functions (fns/text-tools.wasm): fns/text-tools.wasm is a component that reaches the clock, but no files, network or other app
```

With the [Network](#network) and [Host services](#host-services)
components in the bundle, the lines for those two are:

```text
  [warning] functions (fns/api-client.wasm): fns/api-client.wasm is a component that reaches the clock and the network, but no files or other app
  [warning] functions (fns/host-calls.wasm): fns/host-calls.wasm is a component that reaches the clock and its app's host services, but no files, network or other app
```

| Finding | Fix |
| --- | --- |
| `[refused] functions: fns/text-tools.wasm is a WebAssembly component; the manifest must require wasm-components-v1` | Add it to `requires`, or run `tools/octo wasm build`. |
| `[refused] functions: fns/markdown.wasm imports wasi:filesystem, the app's own files, which needs the storage capability` | Add `storage`, or drop the file access. |
| `[refused] functions: fns/api-client.wasm imports wasi:http, the network, which the app must declare with the net capability` | Add `net` to `capabilities`, or run `tools/octo wasm build`, which adds it. No host list is needed ([Network](#network)). |
| `[refused] contents-invalid (fns/netprobe.wasm): the component imports wasi:sockets/network@0.2.9; a component may import only wasi:cli, wasi:clocks, wasi:filesystem, wasi:http, wasi:io, wasi:random and octosense:host` | Remove what opens sockets ([What cannot build or run](#what-cannot-build-or-run)). |

The rules for every file in `fns/` (its name, at most 8 files, the 8 MiB
bundle) are the same as for modules ([Build it](#build-it)).

## Core modules (ADR 0011)

A core module is what OctoSense `main` and desktop 0.1.0-rc.2 run today: a WebAssembly core module,
not a component, whose functions take and return bytes or JSON and reach
nothing but their input. The rest of this section is the guide to them.

### Where functions run

The shell's `wasm` host service runs the functions. OctoSense's
[ADR 0011](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0011-apps-own-functions-in-webassembly.md)
accepts the service with limited support: `wasm-functions`, an OctoSense
Cargo feature that is on by default, includes it in every standard desktop
and Home build on macOS, Linux and Android. `wasm-lab` is the feature's
former name and stays as an alias. Builds for Windows (RC2 leaves it out), iOS
(no code generation for apps) and OpenHarmony (policy unknown) leave the
runtime out.

| Build | Accepts an app that requests `wasm` | Runs its functions |
| --- | --- | --- |
| `desktop-v0.1.0-beta.2` | No. Its app contract, 1.5, refuses the capability: `app <id> requests unknown capability "wasm"`. | No |
| [OctoSense desktop 0.1.0-rc.1](../README.md#compatible-shell-download) default build | Yes | No. Every call answers `no service answers "wasm" on this device`. |
| [OctoSense desktop 0.1.0-rc.2](../README.md#compatible-shell-download) on macOS or Linux | Yes | Yes |
| OctoSense desktop 0.1.0-rc.2 on Windows | Yes | No. Every call answers `no service answers "wasm" on this device`. |
| OctoSense `main`, default build for macOS, Linux or Android: feature `wasm-functions`, formerly `wasm-lab` | Yes | Yes |
| OctoSense `main`, build for Windows, iOS or OpenHarmony | Yes | No. Every call answers `no service answers "wasm" on this device`. |
| `card-host`, built from App Hub `main` | Yes | No. Every call answers `no service answers "wasm" on this device`. |

Desktop 0.1.0-rc.2 is the first release with the service, on macOS and Linux
(its Windows build leaves it out); `desktop-v0.1.0-beta.2`, desktop RC1 and
`home-v0.1.0-beta.1` do not include it. No released Home build has it yet.

App Hub's gate (`hub check`) admits the `wasm` capability from app contract
1.7, with at most 8 modules per bundle ([Build it](#build-it)).

**Unverified:** no app from App Hub's public catalog has run its functions
yet. On a device, Wasm Lab (a system app) has, and so has OctoSense's phone
acceptance app: a signed test app, installed through normal store admission
on a OnePlus 6.

### How a call runs

1. The app's script calls `host.request("wasm.<function>", args, fn(r){…})`,
   or the app's agent calls a tool mapped to `wasm.<function>`.
2. On the app's first call, the `wasm` service loads every module in the
   app's own bundle (`fns/*.wasm`), never another app's. Wasmtime, the
   shell's WebAssembly runtime, compiles each module with its Cranelift
   compiler, or takes the compiled code from the shell's cache on disk.
3. The service passes the arguments to the function as bytes. The function
   runs on the app's own worker thread, so a slow function holds up only its
   own app. One app's calls run one at a time, in order. The worker exits
   after 5 idle seconds; the app's next call starts a new one, which loads
   the modules again.
4. The script's callback gets the output in `r.data`, or an error in
   `r.error`.

Every call gets a fresh **instance**: a running copy of the module with its
own memory. Nothing survives from one call to the next: a `static`, a cache
in memory or anything else written to the module's linear memory is gone at
the next call. Only the compiled code is reused. Keep state in the script,
and pass the function what it needs with each call. A **trap** aborts the
function on a panic, a stack overflow or memory over the 256 MiB cap. A trap
or the 2 s deadline ends the call with an error; the shell keeps running.

After an app update, a changed grant or a signed withdrawal, the service
discards the compiled code and the answer of a call that was running. That
call answers `wasm app admission changed; retry from the current app`, and
the next call loads the new modules, with no restart of the shell.

### Write a function

#### The guest crate

`octosense-guest` is a helper crate for the guest, the Rust code inside the
module. It implements [the ABI](#the-abi) for you. It is not on crates.io.
Copy it from
[`apps/wasmlab/guest/octosense-guest`](https://github.com/OctoSense-org/OctoSense/tree/main/apps/wasmlab/guest/octosense-guest)
in the OctoSense repository. It is licensed under Apache-2.0 and depends only
on `serde_json`.

| Item | What it does |
| --- | --- |
| `octosense_guest::abi!()` | Exports `octo_alloc` and `octo_free`. Invoke it once per crate. |
| `octosense_guest::export!(f)` | Exports `fn f(&[u8]) -> Result<Vec<u8>, String>` as `f`: bytes in, bytes out. |
| `octosense_guest::export_json!(f)` | Exports `fn f(In) -> Result<Out, String>` as `f`, where `In: Deserialize` and `Out: Serialize`. It parses the input as JSON into `In` and writes `Out` as JSON. Input that does not parse fails with `the input is not what f takes: <reason>`. |
| `octosense_guest::log(line)` | Writes `line` to the shell's log, as `wasm <app id>: <line>`. A native build prints it to stderr. |
| A panic hook, which `export!` and `export_json!` install | Logs the panic's message, as a `panic: …` line, before the call traps. |

#### A minimal example

These steps add functions to an app that `tools/octo new` made in
`~/apps/my-app` ([QUICKSTART §3](QUICKSTART.md#3-create-an-app)); the
examples give it the id `dev.example.texttools`. Keep the Rust crate beside
`bundle/`. Only the built module goes into the bundle:

```text
~/apps/my-app/
  bundle/
    fns/my_functions.wasm   the built module
  functions/                your Rust crate; not in the bundle
    Cargo.toml
    src/lib.rs
  octosense-guest/          copied from OctoSense; not in the bundle
```

1. Clone OctoSense into `<workspace>` as
   [PUBLISHING §4.2](PUBLISHING.md#42-install-and-open-the-app-in-the-desktop-shell)
   shows, then copy the guest crate:

   ```sh
   cp -R <workspace>/OctoSense/apps/wasmlab/guest/octosense-guest ~/apps/my-app/
   ```

2. Write `functions/Cargo.toml`. `cdylib` produces the `.wasm` file, and
   `rlib` lets other Rust code, such as integration tests, link the same
   functions natively. The release profile is Wasm Lab's
   ([Build it](#build-it)).

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

3. Write `functions/src/lib.rs`. It adapts two of Wasm Lab's functions:
   `md_to_html` takes text and returns text, and `rank` takes and returns
   JSON.

   ```rust
   //! The app's own functions, built for wasm32-unknown-unknown.
   use serde::{Deserialize, Serialize};

   // Exports octo_alloc and octo_free. Invoke it once per crate.
   octosense_guest::abi!();

   /// Text in, text out: CommonMark to HTML.
   pub fn md_to_html(input: &[u8]) -> Result<Vec<u8>, String> {
       let text = std::str::from_utf8(input).map_err(|_| "the text is not UTF-8".to_string())?;
       let mut html = String::new();
       pulldown_cmark::html::push_html(&mut html, pulldown_cmark::Parser::new(text));
       Ok(html.into_bytes())
   }
   octosense_guest::export!(md_to_html);

   /// JSON in, JSON out: the items that contain the query, earliest match first.
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

4. Test the logic natively, from `~/apps/my-app`:

   ```sh
   cargo test --manifest-path functions/Cargo.toml
   ```

   The output includes `test tests::the_earliest_match_comes_first ... ok`.

#### What the sandbox forbids

A function reaches nothing but its own memory and `octo.log`. Rust's
standard library still compiles for `wasm32-unknown-unknown`, but the calls
below fail or do nothing:

| Your code | What happens | Instead |
| --- | --- | --- |
| Reads the clock: `Instant::now()`, `SystemTime::now()` | Panics with `time not implemented on this platform`, so the call traps. | Pass the time in the input. Splash has `time_now()`. |
| Gets random bytes from `getrandom`, directly or through a crate such as `rand` with its default features | `getrandom` does not build for `wasm32-unknown-unknown`. With its JavaScript backend enabled, it imports `wasm-bindgen` functions, so the module does not load. | Pass a seed in the input. Splash has `random_u32()`. |
| Opens a file with `std::fs` | Returns `operation not supported on this platform`. | Read the file in Splash and pass its contents in. |
| Opens a socket with `std::net` | Returns `operation not supported on this platform`. | Fetch with `net` in Splash and pass the data in. |
| Starts a thread with `std::thread::spawn` | Panics, so the call traps. `thread::Builder::spawn` returns `operation not supported on this platform`. | Compute on one thread. |
| Reads an environment variable | `std::env::var` returns `Err(NotPresent)`. | Pass settings in the input. |
| Prints with `println!` or `eprintln!` | Writes nothing. | Call `octosense_guest::log`. |
| Imports a host function, such as WASI's or `wasm-bindgen`'s | The module does not load: `the module imports <name>; only octo.log is provided`. | Build for `wasm32-unknown-unknown` and drop the dependency that adds the import. |

#### Limits

| Limit | Value | When a function exceeds it |
| --- | --- | --- |
| Time per call | 2 s of wall-clock time, checked every 10 ms | `the call ran past its deadline` |
| Memory per instance | 256 MiB | `the function trapped: memory over its cap (…)` |
| Wasm stack per call | 512 KiB | `the function trapped: wasm trap: call stack exhausted` |
| Input and output of a call | 16 MiB each | `<n> bytes is over the input/output limit` |
| Module size | 8 MiB | `<file>: module exceeds the size limit` |
| Log | 64 lines per call, each cut to 1,024 bytes | Further lines are dropped. |

The `wasm` service adds its own limits to every request:

| Limit | Value | When a request exceeds it |
| --- | --- | --- |
| Serialized input | 1 MiB per request | `wasm input exceeds 1 MiB` |
| Queued requests | 4 per app | `wasm app queue is full; try again later` |
| Apps running functions at once | 4 | `wasm workers are busy; try again later` |
| Buffered input, all apps together | 16 MiB | `wasm input queue is full; try again later` |
| One request, including queueing and loading | 10 s, the service's timeout (App Hub's default is 60 s) | `the host service timed out` |

A full queue or no free worker fails the request at once instead of making
it wait. An app's calls run one at a time, in order, on its own worker
thread, and a worker exits after 5 idle seconds.

App Hub's general limits on host-service requests still apply too, but the
`wasm` service's own are stricter. A call from a script meets these caps
before the runtime's 16 MiB ones:

| Limit | Value | When a call exceeds it |
| --- | --- | --- |
| A script's arguments | 1 MiB of JSON | `the request's arguments exceed 1 MiB` |
| The answer | 4 MiB of JSON | `the service's answer exceeds 4 MiB` |
| Calls waiting per app | 32 | `too many host requests are waiting; try again when some have answered` |

Source: `Limits::default()` in OctoSense's `crates/wasm-host/src/lib.rs`,
which the `wasm` service uses, the constants in OctoSense's
`crates/shell/src/wasm_service.rs`, and `crates/appstore/src/services.rs` in
App Hub.

#### The ABI

The guest crate implements this ABI. Read it to write a module without the
crate, or to debug one. A module is a WebAssembly core module, not a
component. It has these exports and at most one import:

| Name | Kind | Type | Role |
| --- | --- | --- | --- |
| `memory` | Export | Memory | The module's linear memory. |
| `octo_alloc` | Export | `(len: i32) -> i32` | Allocates `len` bytes for the input and returns their address. |
| `octo_free` | Export | `(ptr: i32, len: i32)` | Frees a buffer that `octo_alloc` returned or that holds an output. |
| Each function | Export | `(ptr: i32, len: i32) -> i64` | Reads `len` input bytes at `ptr` and returns `(out_ptr << 32) \| out_len`: the address and length of an output buffer it allocated, which starts with a status byte (step 4 below). |
| `octo.log` | Import, optional | `(ptr: i32, len: i32)` | Writes one line to the shell's log. |

The shell makes each call in four steps:

1. It calls `octo_alloc(len)` and writes the input at the returned address.
2. It calls the function with that address and length, then frees the input
   with `octo_free`.
3. It copies the output buffer and frees it with `octo_free`.
4. It reads the buffer's first byte, the status: `0` means the rest is the
   output, and `1` means the rest is the error text in UTF-8. Any other
   value, or an empty buffer, is a trap.

Every export of type `(i32, i32) -> i64` is a function the app can call. The
shell ignores exports of other types. A module that lacks `memory`,
`octo_alloc` or `octo_free`, or imports anything besides `octo.log`, does not
load.

### Build it

Run these commands from `~/apps/my-app`.

1. Check that Rust has the WebAssembly target:

   ```sh
   rustup target list --installed
   ```

   The list includes `wasm32-unknown-unknown`. If it does not, add it
   (**unverified**):

   ```sh
   rustup target add wasm32-unknown-unknown
   ```

2. Build the module:

   ```sh
   cargo build --manifest-path functions/Cargo.toml --release --target wasm32-unknown-unknown
   ```

   A successful build ends with ``Finished `release` profile [optimized] target(s) in …``.
   If it fails while compiling `getrandom`, a dependency needs OS randomness:
   drop that dependency, or turn off the feature that pulls in `getrandom`
   ([What the sandbox forbids](#what-the-sandbox-forbids)).

3. Copy the module into the bundle. Cargo names the file after the package,
   with `-` turned into `_`:

   ```sh
   mkdir -p bundle/fns
   cp functions/target/wasm32-unknown-unknown/release/my_functions.wasm bundle/fns/
   ```

The gate holds the bundle to these rules:

| Rule | Value |
| --- | --- |
| Path | `fns/<name>.wasm`, directly in `fns/` |
| Name | 1 to 64 characters of `[a-z0-9_-]` |
| Header | The first 8 bytes: a WebAssembly core module, version 1 (App Hub #186 also admits a component) |
| Modules | At most 8 per bundle |
| Bundle size | 8 MiB (8,388,608 bytes) of files, not counting `manifest.json` |

The gate does not read a module's imports or exports. The shell checks them
when it loads the module, so a module that passes the gate can still fail to
load ([Errors the app sees](#errors-the-app-sees)). Each function name must
also be unique across the app's modules: the `wasm` service refuses to load
two modules that export the same name.

The example uses Wasm Lab's release profile:

| Setting | Effect |
| --- | --- |
| `opt-level = 3` | Optimizes for speed. |
| `lto = true`, `codegen-units = 1` | Optimizes across crates as one unit. |
| `panic = "abort"` | A panic traps at once, with no unwinding code. |
| `strip = true` | Drops symbols and debug information. |

Built with Rust 1.97, the example's module is 372,358 bytes with these
settings, and 430,973 bytes with Cargo's default release profile.

`target/` is in the `.gitignore` that `tools/octo new` writes, so the build
output stays out of Git. Commit `bundle/fns/my_functions.wasm` with
`functions/` and the copied `octosense-guest/`, which the crate needs to
build.

### Declare and call it

#### Declare the capability

1. Request `wasm` in `bundle/manifest.json`:

   ```json
   "capabilities": ["wasm"]
   ```

   For core modules, `wasm` needs no `requires` marker; it is an ordinary
   capability. (A component also needs `wasm-components-v1`:
   [Build it into the bundle](#4-build-it-into-the-bundle).) The store shows
   the person "Run its own sandboxed functions on this device".

2. Stamp and check the bundle, from your App Flow checkout:

   ```sh
   tools/octo check ~/apps/my-app/bundle
   ```

   With the rest of the bundle complete
   ([QUICKSTART §8](QUICKSTART.md#8-check-it)), it passes with only the
   unsigned warning, and the `grants:` line lists `wasm`. For the app
   `dev.example.texttools`, the output is:

   ```text
   dev.example.texttools 0.1.0 — PASSED
     [warning] publisher-signature: unsigned: accountability rests on the hub alone
     grants: capabilities {"wasm"}, hosts {}, storage none, agent none
   ```

   If the gate refuses the module, fix what the finding names:

   | Finding | Fix |
   | --- | --- |
   | `[refused] functions: the bundle carries 1 WebAssembly module(s) but does not declare the wasm capability` | Request `wasm` (step 1). |
   | `[refused] functions: the bundle carries 9 WebAssembly modules, over the 8 it may` | Put the functions in 8 modules or fewer. |
   | `[refused] contents-invalid (fns/MyFunctions.wasm): a function module is named fns/<name>.wasm, the name [a-z0-9_-] and at most 64 characters` | Rename the file, and keep it directly in `fns/`. |
   | `[refused] contents-invalid (lib/x.wasm): a WebAssembly module belongs in fns/, as fns/<name>.wasm` | Move the file into `fns/`. |
   | `[refused] contents-invalid (fns/x.wasm): not a WebAssembly core module (magic and version 1)` | Ship a core module built for `wasm32-unknown-unknown`. A component needs a `hub` at or after App Hub #186 ([What the gate checks](#what-the-gate-checks)). |
   | `[warning] functions: the bundle declares the wasm capability but carries no fns/*.wasm` | Copy the module into `bundle/fns/` ([Build it](#build-it), step 3). |
   | `hub: the bundle exceeds the size limit` | Bring the bundle's files under 8 MiB. |

#### Call it from Splash

Call `wasm.<function>`, where `<function>` is the exported name:

```splash
host.request("wasm.rank", {query: "cal" items: ["Local calls" "Calendar" "Mail"]}, fn(r){
    if r.is_ok { ranked = r.data.ranked } else { note = r.error }
})

host.request("wasm.md_to_html", "# Hello", fn(r){
    if r.is_ok { html = r.data.text } else { note = r.error }
})
```

Here `r.data.ranked` is `["Calendar", "Local calls"]`, and `r.data.text`
is `<h1>Hello</h1>` followed by a newline. The service converts the
arguments and the output like this:

| The script passes | The function receives |
| --- | --- |
| A string | Its text, as UTF-8 bytes. Implement the function with `export!`. |
| Anything else: an object, a list, a number or a boolean | Its JSON. Implement the function with `export_json!`. |

| The function returns | `r.data` is |
| --- | --- |
| Valid JSON | That value |
| Anything else | `{text: <the output as UTF-8>}` |

To pass binary data, such as an image that `fs.read_bytes` returns, pass the
byte list. It arrives as a JSON array of numbers, which `export_json!` reads
into a `Vec<u8>`. Each byte takes up to 4 characters, so the 1 MiB argument
limit holds at least 256 KiB of binary data (**unverified**).

#### Call it from an agent tool

Shipping `tools.json` gives the app its own agent, so declare the `agent`
block as well
([AI-SERVICES § An app's own agent](AI-SERVICES.md#an-apps-own-agent)). Add
this entry to the `tools` array of `bundle/tools.json`. Its `host_method`
maps the tool to the `rank` function:

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

The tool's name starts with the app's namespace, the last segment of its
id: `texttools` for `dev.example.texttools`. App Hub's
[`tools.json` rules](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#toolsjson-the-apps-tools)
apply. Four of them differ for `wasm.<function>`:

| Rule | Other `host_method` tools | `wasm.<function>` |
| --- | --- | --- |
| Method | One in App Hub's reviewed list | Any function the app exports: one segment after `wasm.`, of `[a-z0-9_]` |
| Minimum `risk` | Set per method | None; `read` fits a function that only computes |
| `private_data` | Must be `true` | Not required: the function sees only its arguments |
| Capability | The method's family | `wasm` |

A tool's arguments are a JSON object, so implement the function with
`export_json!`. Return an object as well, and declare an object
`output_schema`, because octos, OctoSense's agent kernel, accepts only
object schemas. That is why `rank` returns `{"ranked": […]}` rather than a
bare list. The agent receives `{"ok": true, "data": <output>}`, or
`{"ok": false, "error": {"kind": "app_error", "message": <error>}}`.

The gate's refusal names the rule it applies, such as
`[refused] tools: texttools.rank: host_method "wasm.rank" requires the declared "wasm" service capability`.

#### Check what loaded

Call `wasm.functions` with `{}` to learn whether the host runs functions,
and which ones loaded. Where no `wasm` service runs, the call fails with
`no service answers "wasm" on this device`. `runtime.list` and
`runtime.describe` do not list the `wasm` methods. `wasm.functions` answers
with:

| Field | Holds |
| --- | --- |
| `functions` | The names of the app's functions. |
| `modules` | One entry per module file: `file`, `bytes`, `load_ms`, `from_cache` (whether the compiled code came from the cache), `memory_bytes` (the most memory a call has used: a high-water mark only), `invocations` (the calls so far), `renewed` (`invocations - 1`: every call after the first got a fresh instance) and `instance_policy` (`"fresh-per-call"`). |
| `stats` | One entry per function called so far: `calls`, `errors`, `mean_us` and `max_us`. |

The counts start when the app's worker starts. A worker exits after 5 idle
seconds, and the counts start again with the next one.

Do not name a function `functions`: `wasm.functions` never calls it.

#### Errors the app sees

| `r.error` | Cause | Fix |
| --- | --- | --- |
| `this app was not granted "wasm", which "wasm.rank" needs` | The manifest does not request `wasm`. | Add `wasm` to `capabilities`. |
| `no service answers "wasm" on this device` | The host has no `wasm` service: `card-host`, a release, or an OctoSense build for Windows, iOS or OpenHarmony. | Test in a desktop shell built from OctoSense `main` on macOS or Linux ([Test it](#test-it)). |
| `<app id> has no function "rank"` | No module exports that name. | Compare the name with what `wasm.functions` lists. |
| `<app id>'s bundle has no fns directory` | The app requests `wasm` but ships no module. | Add `fns/<name>.wasm`. |
| `<file>: the module imports <name>; only octo.log is provided` | A dependency imports WASI or `wasm-bindgen` functions. | Build for `wasm32-unknown-unknown`, and drop that dependency. |
| `<file>: the module does not export <name>` | The crate does not invoke `octosense_guest::abi!()`. | Add it once. |
| `<file>: <function> is exported by another module too` | Two modules export the same name. | Rename one of the functions. |
| `the input is not what rank takes: <reason>` | The arguments do not match the function's input type. | Fix the arguments or the type. |
| The function's own text, such as `the query is empty` | The function returned `Err`. | Handle it in the script. |
| `the call ran past its deadline`, `the function trapped: …` | The call broke a [limit](#limits) or [the sandbox](#what-the-sandbox-forbids). | For a panic, read the `panic: …` line in the shell's log. For the deadline, do less work per call. |
| `wasm input exceeds 1 MiB` | The request's serialized input is over 1 MiB. | Pass less input per call. |
| `wasm app queue is full; try again later` | The app already has 4 requests queued. | Send fewer requests at once, for example each one from the previous one's callback. |
| `wasm workers are busy; try again later` | 4 other apps have a worker; a worker exits only after 5 idle seconds. | Try again later. |
| `wasm input queue is full; try again later` | The requests of all apps already buffer 16 MiB of input. | Try again later. |
| `wasm app admission changed; retry from the current app` | The app was updated, its grant changed or it was withdrawn while the call ran. | Call again. After an update, the next call loads the new modules. |
| `the host service timed out` | The request took more than 10 s, including queueing and loading. | Do less work per call, and queue fewer calls. |

The service loads an app's modules together. While any module fails to load,
every call answers that module's error. The service tries again on the next
call.

### Test it

Steps 3 to 9 test the functions in a shell that runs them, so they are
**unverified**.

1. Run the app in `card-host` with `tools/octo run`
   ([QUICKSTART §4](QUICKSTART.md#4-run-it-on-the-desktop)). `card-host`
   admits the bundle but has no `wasm` service, so every call answers
   `no service answers "wasm" on this device`. Use it to check the layout
   and what the app shows without its functions.
2. Set up the OctoSense clone from [A minimal example](#a-minimal-example),
   step 1, as
   [PUBLISHING §4.2](PUBLISHING.md#42-install-and-open-the-app-in-the-desktop-shell)
   shows.
3. Build and start the desktop shell with
   `desktop/system-apps-wasm-lab.json`, which lists the default system apps
   plus Wasm Lab. The default build includes the `wasm` service on macOS and
   Linux, so it needs no `--features wasm-lab`:

   ```sh
   cd <workspace>/OctoSense
   OCTOSENSE_SYSTEM_APPS="$PWD/desktop/system-apps-wasm-lab.json" \
     cargo run --release -p octosense
   ```

   OctoSense checked its plain default build with
   `OCTOSENSE_SYSTEM_APPS=$PWD/desktop/system-apps-wasm-lab.json cargo build --locked -p octosense`,
   then ran Wasm Lab with `--test-action launch-wasmlab`
   ([WebAssembly in OctoSense § Wasm Lab](https://github.com/OctoSense-org/OctoSense/blob/main/docs/wasm.md#wasm-lab)).

4. Open **Wasm Lab** from the dock or the **Apps** menu. Each card calls one
   function and shows the result and the round trip. When a module loads,
   the shell's log shows a line such as
   `wasm os.wasmlab: wasmlab.wasm (433 KiB) compiled in … ms: find_slots, fuzzy_rank, md_to_html, rogue, text_diff`.
5. Under **Misbehave**, click each button. A loop, endless allocation, a
   panic and runaway recursion each end in an error, and the next call still
   answers.
6. Publish your own app to a local mirror, as
   [PUBLISHING §4.1](PUBLISHING.md#41-publish-into-a-local-mirror) shows.
7. Quit the shell, and start it again with the command in
   [PUBLISHING §4.2](PUBLISHING.md#42-install-and-open-the-app-in-the-desktop-shell).
8. Install and open your app from **App Hub** in the dock.
9. Install a new version while the shell runs, then call a function again:
   the next call loads the new modules, with no restart. A call that runs
   during the update answers
   `wasm app admission changed; retry from the current app`.

Agent tools, Wasm Lab's or your app's, also need the octos kernel, staged
as the
[desktop README](https://github.com/OctoSense-org/OctoSense/blob/main/desktop/README.md#build-and-run)
describes, and an AI provider. Home, the phone shell, runs the service on
Android in its default build and has a `phone/system-apps-wasm-lab.json`
file; build it as OctoSense's
[phone README](https://github.com/OctoSense-org/OctoSense/blob/main/phone/README.md)
describes (**unverified**).

## Open items

OctoSense's [ADR 0011](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0011-apps-own-functions-in-webassembly.md)
records the design for modules, and
[ADR 0014](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0014-app-components-in-webassembly.md) the design for
components, with its phases. The state of each item:

| Item | Status |
| --- | --- |
| Components in a shell (ADR 0014, phase 2) | Merged in OctoSense #451 (10 October 2026): the `wasm` service loads components from `fns/`, with one instance per app, the storage grant and its quota, and a larger input limit than a module's. No release has it yet. |
| App Hub's gate for components | Merged: [App Hub #186](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/186) admits components under `wasm-components-v1` and adds `hub component-info`; [App Hub #188](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/188) admits `wasi:http` (with `net`) and `octosense:host`. |
| App Hub's use of the crate list | Merged in [App Hub #189](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/189): reviewers see a component's `octosense-crates` list, and `hub check --advisory-db` checks it against the RustSec advisory database ([The crates it is built from](#the-crates-it-is-built-from)). |
| The SDK on crates.io | Not yet. ADR 0014 publishes it there with a maintainer's approval; until then, a crate depends on it by a git commit or a path. |
| Outgoing HTTP and host services from a component (phase 3) | Merged in OctoSense #451: `wasi:http` reaches any host (network declarations are shown at install and not enforced while the app runs, by OctoSense's ruling of 8 October 2026), and `octosense:host` reaches the host services with `host.request`'s checks; [OctoSense #452](https://github.com/OctoSense-org/OctoSense/pull/452), in review, drops the check of the declared families. The SDK's `http` and `host` modules and `tools/octo wasm` support them; their tests run them in Wasmtime 49 against a local server and fake host services. |
| Compiling at install time, so a phone skips the first compile (phase 3) | Merged in OctoSense #451 for an installed app's functions, which are compiled into the disk cache when the app is installed or updated; a system app's are compiled at its first call. ADR 0011 measured a first compile at 27–33 ms on a desktop and 378–421 ms on a mid-range Android phone, and 5–11 ms for later loads from the cache on that phone. |
| Shared components in App Hub's catalog (phase 4) | [App Hub #190](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/190), merged, publishes them in the catalog; the `wasm` service loading an app's pinned shared components is [OctoSense #454](https://github.com/OctoSense-org/OctoSense/pull/454), a draft. No catalog has published one yet. |
| A CPU budget per app | Not yet. The limits apply per call, so an app can keep one core busy with back-to-back calls. |
| Agent tools with a live model | Unverified. OctoSense's tests call Wasm Lab's tools through the shell's tool executor, without a model. |
| Windows | Builds for Windows have included the service since OctoSense #451, with the runtime's tests in CI; a desktop run on Windows is **unverified**. Desktop 0.1.0-rc.2's Windows build leaves it out. |
| iOS | Not yet. Builds for iOS leave the runtime out. iOS allows no JIT for apps, so Wasmtime would have to use its Pulley interpreter, which OctoSense #451 added and tests for OpenHarmony, and which ADR 0014 measured at about 32 times slower than Cranelift. iOS also allows no downloaded native code, so a store app's functions cannot be compiled ahead of time there either. |
| OpenHarmony | Included since OctoSense #451, running in Pulley until its JIT policy is known; Home's OpenHarmony release build compiled with the service, and no device has run it (**unverified**). |
| Deterministic limits (fuel) | Not decided. |

## See also

- OctoSense's [WebAssembly in OctoSense](https://github.com/OctoSense-org/OctoSense/blob/main/docs/wasm.md):
  how the `wasm` service works on `main`, with its limits, platforms and
  tests.
- OctoSense's [ADR 0014](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0014-app-components-in-webassembly.md):
  components, their WASI subset, the JSON mapping and the phases.
- This repository's SDK, [sdk/rust/](../sdk/rust/README.md): the
  `octosense-component` crate with its macro and its `http` and `host`
  modules, the examples and their end-to-end tests. `tools/octo wasm` reads
  WebAssembly with [tools/wasm_component.py](../tools/wasm_component.py).
- [HOST-API-V1](HOST-API-V1.md): device permissions and `location.get`.
- [CAPABILITIES § Host services](CAPABILITIES.md#host-services): `wasm`
  beside the other host services.
- App Hub's [PUBLISHING § Findings](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#findings)
  and [§ Map a tool to a shared service](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#map-a-tool-to-a-shared-service-host_method):
  the gate's rules for `fns/` and `wasm.<function>`.
- App Hub's [SUBMITTING § What the Hub cannot do yet](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md#what-the-hub-cannot-do-yet):
  what a store app cannot do yet, native Rust code included.
- [Wasm Lab](https://github.com/OctoSense-org/OctoSense/tree/main/apps/wasmlab):
  the reference app for modules, its guest crate and its `build.sh`.
