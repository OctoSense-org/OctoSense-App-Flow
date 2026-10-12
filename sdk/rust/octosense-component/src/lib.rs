//! Write an OctoSense app component in ordinary Rust (OctoSense ADR 0014).
//!
//! ```ignore
//! #[octosense_component::export]
//! mod tools {
//!     pub struct Stats {
//!         pub words: u32,
//!         pub headings: Vec<String>,
//!     }
//!
//!     pub fn to_html(markdown: &str) -> String {
//!         // any crate, any Rust
//!     }
//!
//!     pub fn analyze(markdown: &str) -> Stats {
//!         // …
//!     }
//! }
//! ```
//!
//! `cargo build --target wasm32-wasip2 --release` then makes a WebAssembly
//! component, and the app's script calls it with
//! `host.request("wasm.to_html", {markdown: text}, fn(r) { … })`.
//!
//! [`export`] turns every `pub fn` of the module into an export, and every
//! `pub struct` (named fields) or `pub enum` into a WIT type. It writes the
//! WIT world, the `wit-bindgen` glue and the conversions, so there is no WIT
//! file and no binding code to write.
//!
//! What a function may take and return:
//! - `bool`, the numbers `u8`–`u64`, `i8`–`i64`, `f32` and `f64`, and `char`;
//! - `String` (a parameter may also be `&str`), and `Vec<T>` (a parameter may
//!   also be `&[u8]`);
//! - `Option<T>` and tuples;
//! - `Result<T, String>` or `Result<(), String>`: the error reaches the
//!   script as the call's error;
//! - a `pub struct` or `pub enum` of the same module.
//!
//! Maps, references, generics, `usize` and `async` are refused at compile
//! time, with what to use instead.
//!
//! A world export named `connect` would replace wasi-libc's C socket symbol
//! and corrupt `std::net` calls. Use `tcp_connect` or another prefixed name;
//! the macro refuses the colliding export before linking:
//!
//! ```compile_fail
//! #[octosense_component::export]
//! mod tools {
//!     pub fn connect(address: &str) -> String { address.into() }
//! }
//! ```
//!
//! The component runs in the OctoSense `wasm` service. It has clocks and
//! randomness, and the app's bounded private folder as
//! `/` through `std::fs`. Its stdout and stderr ([`log`]) become log lines.
//! ADR 0014's phase 3 adds two more, each imported only by a component that
//! calls it:
//! - [`http`]: HTTP requests to any host, in an app that declares the `net`
//!   capability (an app's network declarations are shown at install and not
//!   enforced while it runs);
//! - [`host`]: the host services the app is granted, as its script calls
//!   them with `host.request`.
//!
//! Ordinary `std::net` TCP/UDP/DNS needs a host advertising `wasm.sockets@1`;
//! released RC5 does not provide it. `tools/octo wasm build` records that
//! required host ABI automatically when the component imports `wasi:sockets`.
//! There is no separate SDK socket wrapper. The environment is empty, and
//! native libraries or arbitrary OS APIs remain unavailable.

pub mod host;
pub mod http;

pub use octosense_component_macros::export;

/// The bindings generator the glue uses; not needed in your own code.
#[doc(hidden)]
pub use wit_bindgen;

/// Writes one line to stderr, which the `wasm` service makes one of the
/// app's log lines (ADR 0014).
pub fn log(line: &str) {
    eprintln!("{line}");
}

/// The conversion between a module's own types and the types `wit-bindgen`
/// generates. The glue calls it; your code does not need it.
#[doc(hidden)]
pub trait Convert<T> {
    fn convert(self) -> T;
}

macro_rules! identity {
    ($($t:ty),*) => {
        $(impl Convert<$t> for $t {
            #[inline]
            fn convert(self) -> $t {
                self
            }
        })*
    };
}

identity!(
    bool,
    u8,
    u16,
    u32,
    u64,
    i8,
    i16,
    i32,
    i64,
    f32,
    f64,
    char,
    String,
    ()
);

impl<A: Convert<B>, B> Convert<Vec<B>> for Vec<A> {
    fn convert(self) -> Vec<B> {
        self.into_iter().map(Convert::convert).collect()
    }
}

impl<A: Convert<B>, B> Convert<Option<B>> for Option<A> {
    fn convert(self) -> Option<B> {
        self.map(Convert::convert)
    }
}

impl<A: Convert<B>, B> Convert<Result<B, String>> for Result<A, String> {
    fn convert(self) -> Result<B, String> {
        self.map(Convert::convert)
    }
}

macro_rules! tuple {
    ($(($a:ident, $b:ident, $i:tt)),+) => {
        impl<$($a: Convert<$b>, $b),+> Convert<($($b,)+)> for ($($a,)+) {
            fn convert(self) -> ($($b,)+) {
                ($(self.$i.convert(),)+)
            }
        }
    };
}

tuple!((A0, B0, 0));
tuple!((A0, B0, 0), (A1, B1, 1));
tuple!((A0, B0, 0), (A1, B1, 1), (A2, B2, 2));
tuple!((A0, B0, 0), (A1, B1, 1), (A2, B2, 2), (A3, B3, 3));
tuple!(
    (A0, B0, 0),
    (A1, B1, 1),
    (A2, B2, 2),
    (A3, B3, 3),
    (A4, B4, 4)
);
tuple!(
    (A0, B0, 0),
    (A1, B1, 1),
    (A2, B2, 2),
    (A3, B3, 3),
    (A4, B4, 4),
    (A5, B5, 5)
);
