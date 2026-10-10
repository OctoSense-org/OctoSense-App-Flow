//! The example components, built with plain cargo for wasm32-wasip2, loaded
//! in Wasmtime 49 with WASI 0.2 the way OctoSense's `wasm` service loads them
//! (ADR 0014): their exports, their WIT signatures and their results.
//!
//! Each test builds its component first (`cargo build --release --target
//! wasm32-wasip2` into `target/e2e-wasm`, which does nothing when it is up to
//! date), or for markdown-tools takes the file `OCTOSENSE_COMPONENT_WASM`
//! names.
//!
//! Phase 3's two imports are linked as OctoSense links them, with its hooks
//! copied here: `wasi:http`, whose requests reach any host and end with the
//! call's deadline ([`Network`]), and `octosense:host`, whose calls reach
//! fake host services ([`Services`]).

use std::future::Future;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

use wasmtime::component::types::{ComponentItem, Type};
use wasmtime::component::{Component, Func, Instance, Linker, ResourceTable, Val};
use wasmtime::{Config, Engine, Store, StoreContextMut};
use wasmtime_wasi::p2::pipe::MemoryOutputPipe;
use wasmtime_wasi::{FsPerms, WasiCtx, WasiCtxBuilder, WasiCtxView, WasiView};
use wasmtime_wasi_http::{
    RequestOptions, WasiBody, WasiHttpCtx, WasiHttpCtxView, WasiHttpHooks, WasiHttpView,
};

struct State {
    wasi: WasiCtx,
    table: ResourceTable,
    http: WasiHttpCtx,
    /// The running call's deadline, for the requests it sends.
    network: Network,
    /// Its app's host services (`octosense:host`), when the test gives some.
    services: Option<Services>,
}

impl WasiView for State {
    fn ctx(&mut self) -> WasiCtxView<'_> {
        WasiCtxView {
            ctx: &mut self.wasi,
            table: &mut self.table,
        }
    }
}

impl WasiHttpView for State {
    fn http(&mut self) -> WasiHttpCtxView<'_> {
        WasiHttpCtxView {
            ctx: &mut self.http,
            table: &mut self.table,
            hooks: &mut self.network,
        }
    }
}

/// OctoSense's hook for a component's requests (ADR 0014 phase 3, its
/// `crates/wasm-host/src/component/net.rs`). It refuses nothing: an app's
/// network declarations (`net`, `network.hosts`) are shown at install and
/// not enforced while it runs (OctoSense's ruling of 8 October 2026), so a
/// request reaches any host, over HTTPS or plain HTTP. A request waits for
/// the network outside the guest, where the deadline's epoch check cannot
/// end it, so its timeouts are clamped to what is left of the call.
#[derive(Debug, Default)]
struct Network {
    /// The running call's deadline, set for every call.
    deadline: Option<Instant>,
}

type Io = Box<dyn Future<Output = Result<(), wasmtime_wasi_http::Error>> + Send>;
type Sent = Box<
    dyn Future<Output = Result<(http::Response<WasiBody>, Io), wasmtime_wasi_http::Error>> + Send,
>;

impl WasiHttpHooks for Network {
    fn send_request(
        &mut self,
        request: http::Request<WasiBody>,
        options: Option<RequestOptions>,
        fut: Io,
    ) -> Sent {
        _ = fut;
        let left = self
            .deadline
            .map(|deadline| deadline.saturating_duration_since(Instant::now()));
        Box::new(async move {
            let options = clamped(options.unwrap_or_default(), left);
            let (response, io) =
                wasmtime_wasi_http::default_send_request(request, Some(options)).await?;
            Ok((
                response.map(http_body_util::BodyExt::boxed_unsync),
                Box::new(io) as Io,
            ))
        })
    }
}

/// `options` with no timeout longer than `left` (and `left` where it sets
/// none).
fn clamped(options: RequestOptions, left: Option<Duration>) -> RequestOptions {
    let clamp = |asked: Option<Duration>| match (asked, left) {
        (Some(asked), Some(left)) => Some(asked.min(left)),
        (asked, left) => asked.or(left),
    };
    RequestOptions {
        connect_timeout: clamp(options.connect_timeout),
        first_byte_timeout: clamp(options.first_byte_timeout),
        between_bytes_timeout: clamp(options.between_bytes_timeout),
    }
}

/// Each call's deadline here, which ends the requests it sends: what
/// OctoSense gives a call of a component that imports `wasi:http` (others
/// get 2 s, and send no request).
const NETWORK_DEADLINE: Duration = Duration::from_secs(10);

/// Fake host services behind `octosense:host`, held to OctoSense's rules
/// (ADR 0014 phase 3, its `crates/shell/src/wasm_service.rs`): a call reaches
/// the dispatcher whatever the manifest declares (OctoSense #452; a service
/// that needs a grant checks the manifest itself), never `wasm.*`, with JSON
/// arguments. These answer `runtime.list` and echo `notes.get`; a family no
/// service answers is refused as the dispatcher refuses it.
struct Services {
    app: String,
    calls: Vec<(String, String)>,
}

impl Services {
    fn new(app: &str) -> Services {
        Services {
            app: app.into(),
            calls: Vec::new(),
        }
    }

    fn request(&mut self, service: &str, args: &str) -> Result<String, String> {
        self.calls.push((service.into(), args.into()));
        let family = service.split('.').next().unwrap_or("");
        if family == "wasm" {
            return Err(
                "a component cannot call wasm.*: its app's functions are already running it".into(),
            );
        }
        if !matches!(family, "runtime" | "notes") {
            return Err(format!("no service answers \"{family}\" on this device"));
        }
        let args: serde_json::Value = serde_json::from_str(args)
            .map_err(|e| format!("{service}: the arguments are not JSON: {e}"))?;
        match service {
            "runtime.list" => Ok(r#"{"methods":["runtime.list","runtime.describe"]}"#.into()),
            "notes.get" => Ok(serde_json::json!({"app": self.app, "args": args}).to_string()),
            _ => Err(format!("the fake services do not answer {service}")),
        }
    }
}

/// Links WASI 0.2, `wasi:http` and `octosense:host/services`, as OctoSense's
/// runtime does.
fn linker(engine: &Engine) -> Linker<State> {
    let mut linker = Linker::new(engine);
    wasmtime_wasi::p2::add_to_linker_sync(&mut linker).unwrap();
    wasmtime_wasi_http::p2::add_only_http_to_linker_sync(&mut linker).unwrap();
    linker
        .instance("octosense:host/services@0.1.0")
        .unwrap()
        .func_wrap(
            "request",
            |mut store: StoreContextMut<'_, State>,
             (service, args): (String, String)|
             -> wasmtime::Result<(Result<String, String>,)> {
                let answer = match store.data_mut().services.as_mut() {
                    Some(services) => services.request(&service, &args),
                    None => Err("this host gives a component no host services".into()),
                };
                Ok((answer,))
            },
        )
        .unwrap();
    linker
}

fn workspace() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}

/// An example component (`package`, whose file is `file`), built now, in a
/// target directory of its own so the outer `cargo test` lock is not
/// contended. `OCTOSENSE_COMPONENT_WASM` overrides markdown-tools' file.
fn component_bytes(package: &str, file: &str) -> Vec<u8> {
    if package == "markdown-tools" {
        if let Ok(path) = std::env::var("OCTOSENSE_COMPONENT_WASM") {
            return std::fs::read(&path).unwrap_or_else(|e| panic!("{path}: {e}"));
        }
    }
    let target_dir = workspace().join("target/e2e-wasm");
    let status = Command::new(std::env::var("CARGO").unwrap_or_else(|_| "cargo".into()))
        .current_dir(workspace())
        .args([
            "build",
            "--locked",
            "--release",
            "--target",
            "wasm32-wasip2",
            "-p",
            package,
            "--target-dir",
        ])
        .arg(&target_dir)
        .status()
        .expect("cargo runs");
    assert!(
        status.success(),
        "building {package} for wasm32-wasip2 failed (rustup target add wasm32-wasip2)"
    );
    std::fs::read(target_dir.join("wasm32-wasip2/release").join(file)).unwrap()
}

struct Loaded {
    store: Store<State>,
    instance: Instance,
    component: Component,
    engine: Engine,
    stderr: MemoryOutputPipe,
    /// How long each call may take, which also ends its requests.
    deadline: Duration,
}

fn load(storage: &Path) -> Loaded {
    load_component(storage, "markdown-tools", "markdown_tools.wasm")
}

fn load_component(storage: &Path, package: &str, file: &str) -> Loaded {
    load_with(storage, package, file, None)
}

/// A component compiled for a fresh engine.
fn compile(package: &str, file: &str) -> (Engine, Component) {
    let mut config = Config::new();
    config.wasm_component_model(true);
    let engine = Engine::new(&config).unwrap();
    let bytes = component_bytes(package, file);
    assert_eq!(
        &bytes[4..8],
        &[0x0d, 0x00, 0x01, 0x00],
        "a component, not a core module"
    );
    let component = Component::new(&engine, &bytes).unwrap();
    (engine, component)
}

/// Loads a component whose host services are `services`.
fn load_with(storage: &Path, package: &str, file: &str, services: Option<Services>) -> Loaded {
    let (engine, component) = compile(package, file);
    let stderr = MemoryOutputPipe::new(64 << 10);
    let mut wasi = WasiCtxBuilder::new();
    wasi.stderr(stderr.clone())
        .allow_tcp(false)
        .allow_udp(false)
        .allow_ip_name_lookup(false);
    wasi.preopened_dir(storage, "/", FsPerms::ReadWrite)
        .unwrap();
    let mut store = Store::new(
        &engine,
        State {
            wasi: wasi.build(),
            table: ResourceTable::new(),
            http: WasiHttpCtx::new(),
            network: Network::default(),
            services,
        },
    );
    let instance = linker(&engine).instantiate(&mut store, &component).unwrap();
    Loaded {
        store,
        instance,
        component,
        engine,
        stderr,
        deadline: NETWORK_DEADLINE,
    }
}

fn call(loaded: &mut Loaded, name: &str, args: &[Val]) -> Val {
    let func: Func = loaded
        .instance
        .get_func(&mut loaded.store, name)
        .unwrap_or_else(|| panic!("no export {name}"));
    // As OctoSense sets it for every call.
    loaded.store.data_mut().network.deadline = Some(Instant::now() + loaded.deadline);
    let mut results = vec![Val::Bool(false)];
    func.call(&mut loaded.store, args, &mut results).unwrap();
    results.remove(0)
}

/// A fresh folder standing in for the app's storage, one per test.
fn storage() -> PathBuf {
    static NEXT: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
    let dir = std::env::temp_dir().join(format!(
        "octosense-component-e2e-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn ordinary_rust_becomes_typed_exports_with_kebab_names() {
    let dir = storage();
    let loaded = load(&dir);
    let mut exports: Vec<(String, Vec<String>, Vec<String>)> = Vec::new();
    for (name, ext) in loaded.component.component_type().exports(&loaded.engine) {
        if let ComponentItem::ComponentFunc(func) = ext.ty {
            let params = func.params().map(|(n, _)| n.to_string()).collect();
            let results = func
                .results()
                .map(|t| match t {
                    Type::Record(r) => format!(
                        "record {}",
                        r.fields().map(|f| f.name).collect::<Vec<_>>().join(",")
                    ),
                    Type::Enum(e) => format!("enum {}", e.names().collect::<Vec<_>>().join(",")),
                    Type::Result(_) => "result".into(),
                    Type::String => "string".into(),
                    Type::U64 => "u64".into(),
                    other => format!("{other:?}"),
                })
                .collect();
            exports.push((name.to_string(), params, results));
        }
    }
    exports.sort();
    assert_eq!(
        exports,
        [
            (
                "analyze".into(),
                vec!["markdown".into()],
                vec!["record words,lines,headings".into()]
            ),
            (
                "measure".into(),
                vec!["markdown".into()],
                vec!["enum short,medium,long".into()]
            ),
            ("now-ms".into(), vec![], vec!["u64".into()]),
            (
                "save-html".into(),
                vec!["markdown".into(), "path".into()],
                vec!["result".into()]
            ),
            (
                "to-html".into(),
                vec!["markdown".into()],
                vec!["string".into()]
            ),
        ]
    );
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn the_exports_run_with_an_unmodified_crate_files_and_a_clock() {
    let dir = storage();
    let mut loaded = load(&dir);
    assert_eq!(
        call(
            &mut loaded,
            "to-html",
            &[Val::String("# Hi\n\nThere *you*".into())]
        ),
        Val::String("<h1>Hi</h1>\n<p>There <em>you</em></p>\n".into())
    );
    let Val::Record(fields) = call(
        &mut loaded,
        "analyze",
        &[Val::String("# Title\n## Part\nsome words".into())],
    ) else {
        panic!("a record")
    };
    assert_eq!(
        fields,
        vec![
            ("words".to_string(), Val::U32(6)),
            ("lines".to_string(), Val::U32(3)),
            (
                "headings".to_string(),
                Val::List(vec![
                    Val::String("Title".into()),
                    Val::String("Part".into())
                ])
            ),
        ]
    );
    assert_eq!(
        call(&mut loaded, "measure", &[Val::String("two words".into())]),
        Val::Enum("short".into())
    );
    assert_eq!(
        call(
            &mut loaded,
            "save-html",
            &[
                Val::String("# Saved".into()),
                Val::String("out.html".into())
            ]
        ),
        Val::Result(Ok(Some(Box::new(Val::U64(15)))))
    );
    assert_eq!(
        std::fs::read_to_string(dir.join("out.html")).unwrap(),
        "<h1>Saved</h1>\n"
    );
    let Val::Result(Err(Some(error))) = call(
        &mut loaded,
        "save-html",
        &[
            Val::String("x".into()),
            Val::String("missing/dir/x.html".into()),
        ],
    ) else {
        panic!("an error result")
    };
    assert!(matches!(*error, Val::String(_)));
    let Val::U64(now) = call(&mut loaded, "now-ms", &[]) else {
        panic!("a number")
    };
    assert!(now > 1_700_000_000_000, "{now}");
    let log = String::from_utf8_lossy(&loaded.stderr.contents()).into_owned();
    assert!(log.contains("saved 15 bytes to out.html"), "{log}");
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn the_template_octo_wasm_new_writes_runs_as_a_component() {
    let dir = storage();
    let mut c = load_component(&dir, "component-template", "component_template.wasm");
    assert_eq!(call(&mut c, "greet", &[s("Ada")]), s("Hello, Ada!"));
    assert_eq!(
        call(&mut c, "count", &[s("one two\nthree")]),
        Val::Record(vec![
            ("words".into(), Val::U32(3)),
            ("lines".into(), Val::U32(2))
        ])
    );
    assert_eq!(
        call(&mut c, "parse-number", &[s(" 2.5 ")]),
        Val::Result(Ok(Some(Box::new(Val::Float64(2.5)))))
    );
    assert_eq!(
        call(&mut c, "parse-number", &[s("two")]),
        Val::Result(Err(Some(Box::new(s("\"two\" is not a number")))))
    );
    let _ = std::fs::remove_dir_all(dir);
}

fn s(text: &str) -> Val {
    Val::String(text.into())
}

fn point(x: i32, y: i32, label: Option<&str>) -> Val {
    Val::Record(vec![
        ("x".into(), Val::S32(x)),
        ("y".into(), Val::S32(y)),
        ("label".into(), Val::Option(label.map(|l| Box::new(s(l))))),
    ])
}

#[test]
fn every_type_mapping_crosses_both_ways() {
    let dir = storage();
    let mut c = load_component(&dir, "type-tour", "type_tour.wasm");
    // A record in and out, with an option inside.
    assert_eq!(
        call(&mut c, "mirror", &[point(3, -4, Some("ab"))]),
        point(-3, 4, Some("ba"))
    );
    // Variants with a number, a record and nothing; and back out.
    assert_eq!(
        call(
            &mut c,
            "area",
            &[Val::Variant(
                "rect".into(),
                Some(Box::new(point(2, 5, None)))
            )]
        ),
        Val::Float64(10.0)
    );
    assert_eq!(
        call(&mut c, "area", &[Val::Variant("nothing".into(), None)]),
        Val::Float64(0.0)
    );
    assert_eq!(
        call(
            &mut c,
            "grow",
            &[Val::Variant(
                "circle".into(),
                Some(Box::new(Val::Float64(1.5)))
            )]
        ),
        Val::Variant("circle".into(), Some(Box::new(Val::Float64(3.0))))
    );
    // An enum argument.
    assert_eq!(
        call(
            &mut c,
            "convert",
            &[Val::Float64(10.0), Val::Enum("metric".into())]
        ),
        Val::Float64(25.4)
    );
    // Bytes in (&[u8] and Vec<u8>), a tuple and bytes out.
    let bytes = Val::List(vec![Val::U8(1), Val::U8(2), Val::U8(250)]);
    assert_eq!(
        call(&mut c, "checksum", std::slice::from_ref(&bytes)),
        Val::Tuple(vec![Val::U32(3), Val::U64(253)])
    );
    assert_eq!(
        call(&mut c, "reverse-bytes", &[bytes]),
        Val::List(vec![Val::U8(250), Val::U8(2), Val::U8(1)])
    );
    // Option out, both ways.
    assert_eq!(
        call(&mut c, "first-word", &[s("  hello world")]),
        Val::Option(Some(Box::new(s("hello"))))
    );
    assert_eq!(call(&mut c, "first-word", &[s("   ")]), Val::Option(None));
    // Result<(), String>.
    assert_eq!(
        call(&mut c, "check", &[Val::Bool(true)]),
        Val::Result(Ok(None))
    );
    assert_eq!(
        call(&mut c, "check", &[Val::Bool(false)]),
        Val::Result(Err(Some(Box::new(s("not ok")))))
    );
    // Small numbers, char and bool in a tuple.
    assert_eq!(
        call(
            &mut c,
            "widen",
            &[
                Val::U8(200),
                Val::S8(-100),
                Val::Char('é'),
                Val::Bool(false)
            ]
        ),
        Val::Tuple(vec![
            Val::U16(400),
            Val::S16(-200),
            Val::U32('é' as u32),
            Val::Bool(true)
        ])
    );
    // Random numbers through getrandom.
    let random = |c: &mut Loaded| match call(c, "random-u64", &[]) {
        Val::Result(Ok(Some(value))) => *value,
        other => panic!("{other:?}"),
    };
    assert_ne!(random(&mut c), random(&mut c));
    // State kept in the instance between calls.
    assert_eq!(call(&mut c, "tally", &[Val::U64(2)]), Val::U64(2));
    assert_eq!(call(&mut c, "tally", &[Val::U64(3)]), Val::U64(5));
    // A list of records in, a list of strings out.
    assert_eq!(
        call(
            &mut c,
            "labels",
            &[Val::List(vec![
                point(0, 0, Some("a")),
                point(1, 1, None),
                point(2, 2, Some("c"))
            ])]
        ),
        Val::List(vec![s("a"), s("c")])
    );
    let _ = std::fs::remove_dir_all(dir);
}

// ------------------------------------------------- phase 3: HTTP and host calls

/// A local HTTP/1.1 server, one request per connection: `POST` echoes its
/// body with its content type; `GET /missing` answers 404; any other `GET`
/// answers 200 with its request line and its `x-test` header as text.
fn serve() -> SocketAddr {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    std::thread::spawn(move || {
        for stream in listener.incoming().flatten() {
            std::thread::spawn(move || answer(stream));
        }
    });
    address
}

/// A local server that takes every connection and never answers it.
fn serve_nothing() -> SocketAddr {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    std::thread::spawn(move || {
        let mut held = Vec::new();
        for stream in listener.incoming().flatten() {
            held.push(stream);
        }
    });
    address
}

fn answer(mut stream: TcpStream) {
    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let mut line = String::new();
    reader.read_line(&mut line).unwrap();
    let mut headers = Vec::new();
    loop {
        let mut header = String::new();
        if reader.read_line(&mut header).unwrap_or(0) == 0 || header == "\r\n" {
            break;
        }
        if let Some((name, value)) = header.trim_end().split_once(':') {
            headers.push((name.trim().to_ascii_lowercase(), value.trim().to_string()));
        }
    }
    let header = |name: &str| {
        headers
            .iter()
            .find(|(n, _)| n == name)
            .map(|(_, v)| v.clone())
    };
    let mut body = vec![0; header("content-length").map_or(0, |n| n.parse().unwrap())];
    reader.read_exact(&mut body).unwrap();
    let request_line = line.trim_end().trim_end_matches(" HTTP/1.1").to_string();
    let (status, content_type, body) = if request_line.starts_with("POST ") {
        ("200 OK", header("content-type").unwrap_or_default(), body)
    } else if request_line == "GET /missing" {
        ("404 Not Found", "text/plain".into(), b"not here".to_vec())
    } else {
        let test = header("x-test").map_or(String::new(), |v| format!(" x-test: {v}"));
        (
            "200 OK",
            "text/plain".into(),
            format!("{request_line}{test}").into_bytes(),
        )
    };
    let head = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(&body);
}

/// The http-client example's `page` record.
fn page(status: u16, content_type: &str, body: &str) -> Val {
    Val::Result(Ok(Some(Box::new(Val::Record(vec![
        ("status".into(), Val::U16(status)),
        (
            "content-type".into(),
            Val::Option(Some(Box::new(s(content_type)))),
        ),
        ("body".into(), s(body)),
    ])))))
}

/// The error text of a `result<_, string>` that failed.
fn error(val: Val) -> String {
    match val {
        Val::Result(Err(Some(error))) => match *error {
            Val::String(text) => text,
            other => panic!("{other:?}"),
        },
        other => panic!("not an error: {other:?}"),
    }
}

/// `wasi:http` reaches any host, as in OctoSense's runtime: an app's network
/// declarations are shown at install and not enforced while it runs
/// (OctoSense's ruling of 8 October 2026), so no grant names a host.
#[test]
fn http_reaches_any_host() {
    let server = serve();
    let url = |path: &str| format!("http://{server}{path}");
    let dir = storage();
    let mut c = load_component(&dir, "http-client", "http_client.wasm");
    // A GET: its status, content type and body, with the path and query.
    assert_eq!(
        call(&mut c, "fetch", &[s(&url("/items?page=2"))]),
        page(200, "text/plain", "GET /items?page=2")
    );
    // A 404 is a response, not an error.
    assert_eq!(
        call(&mut c, "fetch", &[s(&url("/missing"))]),
        page(404, "text/plain", "not here")
    );
    // A header from the request builder reaches the server.
    assert_eq!(
        call(
            &mut c,
            "fetch-with",
            &[s(&url("/items")), s("x-test"), s("yes")]
        ),
        page(200, "text/plain", "GET /items x-test: yes")
    );
    // The host sets the hop-by-hop headers itself.
    assert_eq!(
        error(call(
            &mut c,
            "fetch-with",
            &[s(&url("/items")), s("connection"), s("close")]
        )),
        "the host sets the header \"connection\" itself"
    );
    // A body larger than one 4096-byte write arrives whole, with its type.
    let json = format!(r#"{{"text":"{}"}}"#, "x".repeat(10_000));
    assert_eq!(
        call(&mut c, "post-json", &[s(&url("/echo")), s(&json)]),
        page(200, "application/json", &json)
    );
    // The same server under another name is reached too: this device, over
    // plain HTTP, by address (above) and by name.
    let port = server.port();
    assert_eq!(
        call(
            &mut c,
            "fetch",
            &[s(&format!("http://localhost:{port}/items"))]
        ),
        page(200, "text/plain", "GET /items")
    );
    // A URL the SDK cannot send never reaches the host.
    let bad = error(call(&mut c, "fetch", &[s("ftp://api.example.com/x")]));
    assert_eq!(
        bad,
        "\"ftp://api.example.com/x\" is not an https:// or http:// URL"
    );
    let _ = std::fs::remove_dir_all(dir);
}

/// A request waits outside the guest, where the deadline's epoch check
/// cannot end it: its timeouts are clamped to the call's deadline, so a
/// server that never answers ends the call instead of holding it.
#[test]
fn a_request_that_never_answers_ends_at_the_deadline() {
    let silent = serve_nothing();
    let dir = storage();
    let mut c = load_component(&dir, "http-client", "http_client.wasm");
    c.deadline = Duration::from_millis(800);
    let started = Instant::now();
    let failed = error(call(&mut c, "fetch", &[s(&format!("http://{silent}/"))]));
    assert_eq!(
        failed,
        format!(
            "the request to http://{silent}/ failed: the server did not answer in time \
             (ErrorCode::ConnectionReadTimeout)"
        )
    );
    assert!(
        started.elapsed() < Duration::from_secs(5),
        "ended after {:?}",
        started.elapsed()
    );
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn a_component_calls_its_apps_host_services_as_its_script_does() {
    let dir = storage();
    let services = Services::new("dev.example.texttools");
    let mut c = load_with(&dir, "host-services", "host_services.wasm", Some(services));
    let ok = |text: &str| Val::Result(Ok(Some(Box::new(s(text)))));
    assert_eq!(
        call(&mut c, "host-apis", &[]),
        ok(r#"{"methods":["runtime.list","runtime.describe"]}"#)
    );
    assert_eq!(
        call(&mut c, "call", &[s("notes.get"), s(r#"{"id": 1}"#)]),
        ok(r#"{"app":"dev.example.texttools","args":{"id":1}}"#)
    );
    // What the host refuses reaches the component as its error: the manifest
    // declares no `mail`, and the call still reaches the dispatcher, which
    // has no mail service here (OctoSense #452).
    assert_eq!(
        error(call(&mut c, "call", &[s("mail.list"), s("{}")])),
        "no service answers \"mail\" on this device"
    );
    assert_eq!(
        error(call(&mut c, "call", &[s("wasm.functions"), s("{}")])),
        "a component cannot call wasm.*: its app's functions are already running it"
    );
    let not_json = error(call(&mut c, "call", &[s("notes.get"), s("id=1")]));
    assert!(
        not_json.starts_with("notes.get: the arguments are not JSON"),
        "{not_json}"
    );
    let calls = &c.store.data().services.as_ref().unwrap().calls;
    assert_eq!(calls.len(), 5);
    assert_eq!(calls[1], ("notes.get".into(), r#"{"id": 1}"#.into()));
    // A host that gives a component no services.
    let mut alone = load_component(&dir, "host-services", "host_services.wasm");
    assert_eq!(
        error(call(&mut alone, "host-apis", &[])),
        "this host gives a component no host services"
    );
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn a_component_imports_http_and_host_services_only_when_it_calls_them() {
    let imports = |package: &str, file: &str| -> Vec<String> {
        let (engine, component) = compile(package, file);
        let names = component
            .component_type()
            .imports(&engine)
            .map(|(name, _)| name.to_string())
            .collect();
        names
    };
    let has = |names: &[String], prefix: &str| names.iter().any(|n| n.starts_with(prefix));
    let client = imports("http-client", "http_client.wasm");
    assert!(has(&client, "wasi:http/outgoing-handler@"), "{client:?}");
    assert!(!has(&client, "octosense:host/"), "{client:?}");
    let services = imports("host-services", "host_services.wasm");
    assert!(
        services.contains(&"octosense:host/services@0.1.0".to_string()),
        "{services:?}"
    );
    assert!(!has(&services, "wasi:http/"), "{services:?}");
    for (package, file) in [
        ("markdown-tools", "markdown_tools.wasm"),
        ("component-template", "component_template.wasm"),
        ("type-tour", "type_tour.wasm"),
    ] {
        let names = imports(package, file);
        assert!(
            !has(&names, "wasi:http/") && !has(&names, "octosense:host/"),
            "{package}: {names:?}"
        );
    }
}
