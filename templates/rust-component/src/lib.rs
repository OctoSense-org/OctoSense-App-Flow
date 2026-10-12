//! The app's own functions, in ordinary Rust.
//!
//! Every `pub fn` of the module below is a function the app's script can
//! call once `tools/octo wasm build` has put the component in the bundle:
//!
//! ```text
//! host.request("wasm.count", {text: "one two"}, fn(r){
//!     if r.is_ok { words = r.data.words } else { note = r.error }
//! })
//! ```
//!
//! Use any crate that builds for `wasm32-wasip2` (`tools/octo wasm doctor`
//! checks known dependencies; a successful build still needs runtime tests).
//! Its code has the clock, random numbers and bounded private storage as `/`
//! through `std::fs`. `octosense_component::http` sends HTTP requests.
//! Ordinary `std::net` TCP/UDP/DNS requires a host advertising wasm.sockets@1,
//! which released RC5 does not provide. `wasm build` adds that compatibility
//! requirement automatically. Disclose file/network use with `storage`/`net`.
//! Name socket exports `tcp_connect`, not `connect`: a bare `connect` export
//! collides with wasi-libc and the SDK rejects it before linking.
//!
//! `octosense_component::host` calls the host services the app is granted.
//! What a function may take and return is in OctoSense App Flow's
//! docs/RUST.md.

#[octosense_component::export]
pub mod functions {
    /// A `pub struct` is a WIT record: an object in the script.
    pub struct Counts {
        pub words: u32,
        pub lines: u32,
    }

    /// Text in, text out: `wasm.greet` with `{name: "Ada"}`, or just `"Ada"`.
    pub fn greet(name: &str) -> String {
        format!("Hello, {name}!")
    }

    /// Text in, an object out: `{words: 2, lines: 1}`.
    pub fn count(text: &str) -> Counts {
        Counts {
            words: text.split_whitespace().count() as u32,
            lines: text.lines().count() as u32,
        }
    }

    /// An `Err` reaches the script as the call's error, `r.error`.
    pub fn parse_number(text: &str) -> Result<f64, String> {
        text.trim()
            .parse()
            .map_err(|_| format!("{text:?} is not a number"))
    }
}

// The same functions, tested natively: `cargo test`.
#[cfg(test)]
mod tests {
    use super::functions::*;

    #[test]
    fn counts_words_and_lines() {
        let counts = count("one two\nthree");
        assert_eq!((counts.words, counts.lines), (3, 2));
    }

    #[test]
    fn a_bad_number_is_an_error() {
        assert_eq!(parse_number(" 2.5 "), Ok(2.5));
        assert!(parse_number("two").is_err());
    }
}
