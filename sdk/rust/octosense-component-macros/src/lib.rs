//! `#[octosense_component::export]`: ordinary Rust in, a WebAssembly
//! component's WIT world and its glue out (OctoSense ADR 0014).
//!
//! Put it on an inline module. Every `pub fn` in the module becomes an
//! export of the component, every `pub struct` with named fields a WIT
//! record, every `pub enum` of unit variants a WIT enum, and every other
//! `pub enum` (unit or one-field tuple variants) a WIT variant. Names are
//! kebab-cased for WIT: `to_html` is exported as `to-html`. Private items
//! stay private helpers.
//!
//! The macro writes the WIT world as text, invokes `wit_bindgen::generate!`
//! on it through `octosense_component`'s re-export, implements the
//! generated `Guest` trait by calling the module's functions, and converts
//! between the module's own types and the generated ones.

use std::collections::HashMap;

use heck::{ToKebabCase, ToSnakeCase, ToUpperCamelCase};
use proc_macro::TokenStream;
use proc_macro2::{Span, TokenStream as TokenStream2};
use quote::{format_ident, quote};
use syn::spanned::Spanned;
use syn::{
    Fields, FnArg, GenericArgument, Ident, Item, ItemFn, ItemMod, Pat, PathArguments, ReturnType,
    Type, Visibility,
};

/// Exports a module's public functions as a WebAssembly component. See the
/// crate docs of `octosense-component`.
#[proc_macro_attribute]
pub fn export(attr: TokenStream, item: TokenStream) -> TokenStream {
    if !attr.is_empty() {
        return syn::Error::new(
            Span::call_site(),
            "#[export] takes no arguments: put it on an inline `mod` of pub functions",
        )
        .to_compile_error()
        .into();
    }
    let module = match syn::parse::<ItemMod>(item) {
        Ok(module) => module,
        Err(_) => {
            return syn::Error::new(
                Span::call_site(),
                "#[export] goes on an inline module: `#[octosense_component::export] mod tools { pub fn … }`",
            )
            .to_compile_error()
            .into()
        }
    };
    match expand(module) {
        Ok(tokens) => tokens.into(),
        Err(error) => error.to_compile_error().into(),
    }
}

/// A value type, as the module's Rust names it.
#[derive(Clone, Debug)]
enum Ty {
    /// bool, numbers and char: the same in Rust, WIT and the bindings.
    Prim(&'static str, Ident),
    Str,
    List(Box<Ty>),
    Option(Box<Ty>),
    /// `Result<T, String>`; `None` for `Result<(), String>`.
    Result(Option<Box<Ty>>),
    Tuple(Vec<Ty>),
    /// A `pub struct` or `pub enum` of the module, by index.
    User(usize),
}

/// How a function takes one parameter.
enum Param {
    Owned(Ty),
    /// `&str`: the binding's `String`, borrowed.
    StrRef,
    /// `&[u8]`: the binding's `Vec<u8>`, borrowed.
    BytesRef,
}

enum Shape {
    Record(Vec<(Ident, String, Ty)>),
    Enum(Vec<(Ident, String)>),
    Variant(Vec<(Ident, String, Option<Ty>)>),
}

struct UserType {
    ident: Ident,
    wit: String,
    binding: Ident,
    shape: Shape,
}

struct Function {
    ident: Ident,
    wit: String,
    binding: Ident,
    params: Vec<(Ident, String, Param)>,
    result: Option<Ty>,
}

const PRIMS: &[(&str, &str)] = &[
    ("bool", "bool"),
    ("u8", "u8"),
    ("u16", "u16"),
    ("u32", "u32"),
    ("u64", "u64"),
    ("i8", "s8"),
    ("i16", "s16"),
    ("i32", "s32"),
    ("i64", "s64"),
    ("f32", "f32"),
    ("f64", "f64"),
    ("char", "char"),
];

const SUPPORTED: &str = "use bool, numbers (u8–u64, i8–i64, f32, f64), char, String, Vec<T>, \
Option<T>, Result<T, String>, tuples, or a pub struct or pub enum of this module";

fn expand(module: ItemMod) -> syn::Result<TokenStream2> {
    let Some((_, items)) = &module.content else {
        return Err(syn::Error::new(
            module.span(),
            "#[export] needs the module's items inline: `mod tools { … }`, not `mod tools;`",
        ));
    };
    let module_ident = module.ident.clone();

    // The module's public types first, so signatures can name them.
    let mut names: HashMap<String, usize> = HashMap::new();
    let mut pending = Vec::new();
    for item in items {
        match item {
            Item::Struct(s) if is_public(&s.vis) => {
                check_generics(&s.generics, s.ident.span())?;
                names.insert(s.ident.to_string(), pending.len());
                pending.push(item.clone());
            }
            Item::Enum(e) if is_public(&e.vis) => {
                check_generics(&e.generics, e.ident.span())?;
                names.insert(e.ident.to_string(), pending.len());
                pending.push(item.clone());
            }
            _ => {}
        }
    }
    let mut types = Vec::new();
    let mut wit_names: HashMap<String, Span> = HashMap::new();
    for item in &pending {
        let user = match item {
            Item::Struct(s) => {
                let Fields::Named(fields) = &s.fields else {
                    return Err(syn::Error::new(
                        s.ident.span(),
                        format!("`{}` needs named fields to become a WIT record", s.ident),
                    ));
                };
                if fields.named.is_empty() {
                    return Err(syn::Error::new(
                        s.ident.span(),
                        format!(
                            "`{}` has no fields; a WIT record needs at least one",
                            s.ident
                        ),
                    ));
                }
                let mut out = Vec::new();
                for field in &fields.named {
                    let ident = field.ident.clone().expect("named field");
                    if !is_public(&field.vis) {
                        return Err(syn::Error::new(
                            ident.span(),
                            format!(
                                "make `{}.{ident}` pub: the glue builds and reads it",
                                s.ident
                            ),
                        ));
                    }
                    let wit = wit_name(&ident)?;
                    out.push((ident, wit, ty(&field.ty, &names)?));
                }
                unique(out.iter().map(|(ident, wit, _)| (ident, wit)))?;
                UserType {
                    wit: wit_name(&s.ident)?,
                    binding: binding_type(&s.ident)?,
                    ident: s.ident.clone(),
                    shape: Shape::Record(out),
                }
            }
            Item::Enum(e) => {
                if e.variants.is_empty() {
                    return Err(syn::Error::new(
                        e.ident.span(),
                        format!("`{}` has no variants", e.ident),
                    ));
                }
                let unit = e.variants.iter().all(|v| matches!(v.fields, Fields::Unit));
                let shape = if unit {
                    let cases: Vec<(Ident, String)> = e
                        .variants
                        .iter()
                        .map(|v| Ok((v.ident.clone(), wit_name(&v.ident)?)))
                        .collect::<syn::Result<_>>()?;
                    unique(cases.iter().map(|(ident, wit)| (ident, wit)))?;
                    Shape::Enum(cases)
                } else {
                    let mut cases = Vec::new();
                    for v in &e.variants {
                        let payload = match &v.fields {
                            Fields::Unit => None,
                            Fields::Unnamed(f) if f.unnamed.len() == 1 => {
                                Some(ty(&f.unnamed[0].ty, &names)?)
                            }
                            _ => {
                                return Err(syn::Error::new(
                                    v.ident.span(),
                                    format!(
                                        "`{}::{}`: a variant holds nothing or one value; \
                                         put several values in a struct",
                                        e.ident, v.ident
                                    ),
                                ))
                            }
                        };
                        cases.push((v.ident.clone(), wit_name(&v.ident)?, payload));
                    }
                    unique(cases.iter().map(|(ident, wit, _)| (ident, wit)))?;
                    Shape::Variant(cases)
                };
                UserType {
                    wit: wit_name(&e.ident)?,
                    binding: binding_type(&e.ident)?,
                    ident: e.ident.clone(),
                    shape,
                }
            }
            _ => unreachable!(),
        };
        if let Some(previous) = wit_names.insert(user.wit.clone(), user.ident.span()) {
            let _ = previous;
            return Err(syn::Error::new(
                user.ident.span(),
                format!("two items are both `{}` in WIT; rename one", user.wit),
            ));
        }
        types.push(user);
    }

    let mut functions = Vec::new();
    for item in items {
        if let Item::Fn(f) = item {
            if is_public(&f.vis) {
                let function = function(f, &names)?;
                if function.wit == "functions" {
                    return Err(syn::Error::new(
                        f.sig.ident.span(),
                        "`functions` is the wasm service's own method (`wasm.functions` lists the \
                         app's functions); rename this one",
                    ));
                }
                // wit-bindgen emits a bare C-linkage export for a world
                // function. `connect` then replaces wasi-libc's connect(),
                // so std::net recurses into the incompatible guest ABI and
                // can trap even when another export opens the socket.
                if function.wit == "connect" {
                    return Err(syn::Error::new(
                        f.sig.ident.span(),
                        "`connect` collides with wasi-libc's socket symbol; rename the exported \
                         function to `tcp_connect` or another prefixed name",
                    ));
                }
                if wit_names
                    .insert(function.wit.clone(), f.sig.ident.span())
                    .is_some()
                {
                    return Err(syn::Error::new(
                        f.sig.ident.span(),
                        format!("two items are both `{}` in WIT; rename one", function.wit),
                    ));
                }
                functions.push(function);
            }
        }
    }
    if functions.is_empty() {
        return Err(syn::Error::new(
            module.ident.span(),
            "#[export] found no pub fn in this module; exports are its pub functions",
        ));
    }

    let order = topological(&types)?;
    let wit = world(&types, &order, &functions);
    let bindings = format_ident!("__octosense_component_bindings");
    let guest = format_ident!("__OctosenseComponent");

    let conversions = types
        .iter()
        .map(|t| conversion(t, &types, &module_ident, &bindings));
    let methods = functions
        .iter()
        .map(|f| method(f, &types, &module_ident, &bindings));
    let wit_lit = syn::LitStr::new(&wit, Span::call_site());

    Ok(quote! {
        #module

        #[doc(hidden)]
        #[allow(clippy::all, unused, non_camel_case_types)]
        mod #bindings {
            ::octosense_component::wit_bindgen::generate!({
                inline: #wit_lit,
                world: "component",
                runtime_path: "::octosense_component::wit_bindgen::rt",
            });
        }

        #(#conversions)*

        #[doc(hidden)]
        struct #guest;

        impl #bindings::Guest for #guest {
            #(#methods)*
        }

        #bindings::export!(#guest with_types_in #bindings);
    })
}

fn is_public(vis: &Visibility) -> bool {
    !matches!(vis, Visibility::Inherited)
}

fn check_generics(generics: &syn::Generics, span: Span) -> syn::Result<()> {
    if generics.params.is_empty() && generics.where_clause.is_none() {
        Ok(())
    } else {
        Err(syn::Error::new(
            span,
            "exported types and functions cannot be generic: WIT types are concrete",
        ))
    }
}

/// A Rust name as a WIT identifier (kebab case), checked.
fn wit_name(ident: &Ident) -> syn::Result<String> {
    let text = ident.to_string();
    if text.starts_with("r#") {
        return Err(syn::Error::new(
            ident.span(),
            "raw identifiers cannot be exported; rename it",
        ));
    }
    let kebab = text.to_kebab_case();
    let valid = !kebab.is_empty()
        && kebab.split('-').all(|word| {
            word.chars().next().is_some_and(|c| c.is_ascii_lowercase())
                && word
                    .chars()
                    .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit())
        });
    if !valid {
        return Err(syn::Error::new(
            ident.span(),
            format!(
                "`{text}` is `{kebab}` in WIT, which is not a WIT name: every part must start \
                 with a letter (rename `get_2d` to `get_two_d`, say)"
            ),
        ));
    }
    Ok(kebab)
}

/// Refuses two members (fields, cases or parameters) with one WIT name,
/// such as `a_b` and `a__b`, which are both `a-b`.
fn unique<'a>(members: impl Iterator<Item = (&'a Ident, &'a String)>) -> syn::Result<()> {
    let mut seen = HashMap::new();
    for (ident, wit) in members {
        if let Some(first) = seen.insert(wit, ident) {
            return Err(syn::Error::new(
                ident.span(),
                format!("`{first}` and `{ident}` are both `{wit}` in WIT; rename one"),
            ));
        }
    }
    Ok(())
}

/// The name wit-bindgen gives a WIT type.
fn binding_type(ident: &Ident) -> syn::Result<Ident> {
    Ok(format_ident!("{}", wit_name(ident)?.to_upper_camel_case()))
}

/// The name wit-bindgen gives a WIT function, parameter or field.
fn binding_member(wit: &str) -> Ident {
    let snake = wit.to_snake_case();
    if syn::parse_str::<Ident>(&snake).is_ok() {
        format_ident!("{}", snake)
    } else {
        format_ident!("{}_", snake)
    }
}

fn ty(ty: &Type, names: &HashMap<String, usize>) -> syn::Result<Ty> {
    match ty {
        Type::Path(path) if path.qself.is_none() => {
            let segment = path.path.segments.last().expect("a path has a segment");
            let name = segment.ident.to_string();
            let args: Vec<&Type> = match &segment.arguments {
                PathArguments::AngleBracketed(a) => a
                    .args
                    .iter()
                    .filter_map(|g| match g {
                        GenericArgument::Type(t) => Some(t),
                        _ => None,
                    })
                    .collect(),
                PathArguments::None => Vec::new(),
                PathArguments::Parenthesized(_) => {
                    return Err(syn::Error::new(ty.span(), format!("unsupported type; {SUPPORTED}")))
                }
            };
            if let Some((_, wit)) = PRIMS.iter().find(|(rust, _)| *rust == name) {
                return Ok(Ty::Prim(wit, segment.ident.clone()));
            }
            match (name.as_str(), args.as_slice()) {
                ("String", []) => Ok(Ty::Str),
                ("Vec", [item]) => Ok(Ty::List(Box::new(self::ty(item, names)?))),
                ("Option", [item]) => Ok(Ty::Option(Box::new(self::ty(item, names)?))),
                ("Result", [ok, err]) => {
                    let is_string = matches!(err, Type::Path(p) if p.path.segments.last().is_some_and(|s| s.ident == "String"));
                    if !is_string {
                        return Err(syn::Error::new(
                            err.span(),
                            "a component's error is text: return Result<T, String> \
                             (map your error with .map_err(|e| e.to_string()))",
                        ));
                    }
                    match ok {
                        Type::Tuple(t) if t.elems.is_empty() => Ok(Ty::Result(None)),
                        ok => Ok(Ty::Result(Some(Box::new(self::ty(ok, names)?)))),
                    }
                }
                ("usize" | "isize", _) => Err(syn::Error::new(
                    ty.span(),
                    "WIT numbers have fixed widths: use u32 or u64 (i32 or i64) instead",
                )),
                ("HashMap" | "BTreeMap" | "HashSet" | "BTreeSet" | "IndexMap", _) => Err(syn::Error::new(
                    ty.span(),
                    "maps and sets are not WIT types: use Vec<(K, V)>, Vec<T> or a pub struct",
                )),
                ("Box" | "Rc" | "Arc" | "Cow", _) => Err(syn::Error::new(
                    ty.span(),
                    "take and return plain owned values (String, Vec<T>, a struct)",
                )),
                (other, []) if names.contains_key(other) => Ok(Ty::User(names[other])),
                _ => Err(syn::Error::new(ty.span(), format!("unsupported type; {SUPPORTED}"))),
            }
        }
        Type::Tuple(t) if !t.elems.is_empty() => Ok(Ty::Tuple(
            t.elems
                .iter()
                .map(|e| self::ty(e, names))
                .collect::<syn::Result<_>>()?,
        )),
        Type::Tuple(_) => Err(syn::Error::new(
            ty.span(),
            "`()` is only a return type (or Result<(), String>)",
        )),
        Type::Reference(_) => Err(syn::Error::new(
            ty.span(),
            "references are not WIT values: use String or Vec<T> (a parameter may be &str or &[u8])",
        )),
        Type::Slice(_) | Type::Array(_) => Err(syn::Error::new(ty.span(), "use Vec<T> for a list")),
        _ => Err(syn::Error::new(ty.span(), format!("unsupported type; {SUPPORTED}"))),
    }
}

fn function(f: &ItemFn, names: &HashMap<String, usize>) -> syn::Result<Function> {
    let sig = &f.sig;
    if let Some(asyncness) = &sig.asyncness {
        return Err(syn::Error::new(
            asyncness.span(),
            "exported functions cannot be async yet",
        ));
    }
    if let Some(unsafety) = &sig.unsafety {
        return Err(syn::Error::new(
            unsafety.span(),
            "exported functions cannot be unsafe",
        ));
    }
    if sig.variadic.is_some() {
        return Err(syn::Error::new(
            sig.span(),
            "exported functions cannot be variadic",
        ));
    }
    check_generics(&sig.generics, sig.ident.span())?;
    let mut params = Vec::new();
    for input in &sig.inputs {
        let FnArg::Typed(arg) = input else {
            return Err(syn::Error::new(
                input.span(),
                "exported functions are free functions, without self",
            ));
        };
        let Pat::Ident(pat) = &*arg.pat else {
            return Err(syn::Error::new(
                arg.pat.span(),
                "name each parameter plainly (`name: Type`): WIT keeps the name",
            ));
        };
        let wit = wit_name(&pat.ident)?;
        let param = match &*arg.ty {
            Type::Reference(r) => {
                if r.mutability.is_some() {
                    return Err(syn::Error::new(
                        r.span(),
                        "a parameter cannot be &mut; take it by value",
                    ));
                }
                match &*r.elem {
                    Type::Path(p) if p.path.is_ident("str") => Param::StrRef,
                    Type::Slice(s) if matches!(&*s.elem, Type::Path(p) if p.path.is_ident("u8")) => {
                        Param::BytesRef
                    }
                    _ => {
                        return Err(syn::Error::new(
                            r.span(),
                            "a parameter may borrow only &str or &[u8]; take other values owned",
                        ))
                    }
                }
            }
            other => Param::Owned(ty(other, names)?),
        };
        params.push((pat.ident.clone(), wit, param));
    }
    unique(params.iter().map(|(ident, wit, _)| (ident, wit)))?;
    let result = match &sig.output {
        ReturnType::Default => None,
        ReturnType::Type(_, t) => match &**t {
            Type::Tuple(tuple) if tuple.elems.is_empty() => None,
            other => Some(ty(other, names)?),
        },
    };
    let wit = wit_name(&sig.ident)?;
    Ok(Function {
        ident: sig.ident.clone(),
        binding: binding_member(&wit),
        wit,
        params,
        result,
    })
}

/// The module's types in an order where each comes after what it uses.
fn topological(types: &[UserType]) -> syn::Result<Vec<usize>> {
    fn uses(ty: &Ty, out: &mut Vec<usize>) {
        match ty {
            Ty::User(i) => out.push(*i),
            Ty::List(t) | Ty::Option(t) => uses(t, out),
            Ty::Result(Some(t)) => uses(t, out),
            Ty::Tuple(ts) => ts.iter().for_each(|t| uses(t, out)),
            _ => {}
        }
    }
    let deps: Vec<Vec<usize>> = types
        .iter()
        .map(|t| {
            let mut out = Vec::new();
            match &t.shape {
                Shape::Record(fields) => fields.iter().for_each(|(_, _, ty)| uses(ty, &mut out)),
                Shape::Variant(cases) => cases
                    .iter()
                    .filter_map(|(_, _, ty)| ty.as_ref())
                    .for_each(|ty| uses(ty, &mut out)),
                Shape::Enum(_) => {}
            }
            out
        })
        .collect();
    let mut state = vec![0u8; types.len()]; // 0 new, 1 visiting, 2 done
    let mut order = Vec::new();
    fn visit(
        i: usize,
        deps: &[Vec<usize>],
        state: &mut [u8],
        order: &mut Vec<usize>,
        types: &[UserType],
    ) -> syn::Result<()> {
        match state[i] {
            2 => return Ok(()),
            1 => {
                return Err(syn::Error::new(
                    types[i].ident.span(),
                    format!(
                        "`{}` refers to itself; WIT types cannot be recursive",
                        types[i].ident
                    ),
                ))
            }
            _ => {}
        }
        state[i] = 1;
        for &d in &deps[i] {
            visit(d, deps, state, order, types)?;
        }
        state[i] = 2;
        order.push(i);
        Ok(())
    }
    for i in 0..types.len() {
        visit(i, &deps, &mut state, &mut order, types)?;
    }
    Ok(order)
}

fn wit_ty(ty: &Ty, types: &[UserType]) -> String {
    match ty {
        Ty::Prim(wit, _) => wit.to_string(),
        Ty::Str => "string".into(),
        Ty::List(t) => format!("list<{}>", wit_ty(t, types)),
        Ty::Option(t) => format!("option<{}>", wit_ty(t, types)),
        Ty::Result(Some(t)) => format!("result<{}, string>", wit_ty(t, types)),
        Ty::Result(None) => "result<_, string>".into(),
        Ty::Tuple(ts) => format!(
            "tuple<{}>",
            ts.iter()
                .map(|t| wit_ty(t, types))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Ty::User(i) => format!("%{}", types[*i].wit),
    }
}

fn world(types: &[UserType], order: &[usize], functions: &[Function]) -> String {
    let mut out = String::from("package octosense:component;\n\nworld component {\n");
    for &i in order {
        let t = &types[i];
        match &t.shape {
            Shape::Record(fields) => {
                out += &format!("  record %{} {{\n", t.wit);
                for (_, wit, ty) in fields {
                    out += &format!("    %{wit}: {},\n", wit_ty(ty, types));
                }
                out += "  }\n";
            }
            Shape::Enum(cases) => {
                out += &format!("  enum %{} {{\n", t.wit);
                for (_, wit) in cases {
                    out += &format!("    %{wit},\n");
                }
                out += "  }\n";
            }
            Shape::Variant(cases) => {
                out += &format!("  variant %{} {{\n", t.wit);
                for (_, wit, ty) in cases {
                    match ty {
                        Some(ty) => out += &format!("    %{wit}({}),\n", wit_ty(ty, types)),
                        None => out += &format!("    %{wit},\n"),
                    }
                }
                out += "  }\n";
            }
        }
    }
    for f in functions {
        let params = f
            .params
            .iter()
            .map(|(_, wit, param)| {
                let ty = match param {
                    Param::Owned(ty) => wit_ty(ty, types),
                    Param::StrRef => "string".into(),
                    Param::BytesRef => "list<u8>".into(),
                };
                format!("%{wit}: {ty}")
            })
            .collect::<Vec<_>>()
            .join(", ");
        match &f.result {
            Some(ty) => {
                out += &format!(
                    "  export %{}: func({params}) -> {};\n",
                    f.wit,
                    wit_ty(ty, types)
                )
            }
            None => out += &format!("  export %{}: func({params});\n", f.wit),
        }
    }
    out += "}\n";
    out
}

/// The Rust type wit-bindgen generates for a value type.
fn binding_rust(ty: &Ty, types: &[UserType], bindings: &Ident) -> TokenStream2 {
    match ty {
        Ty::Prim(_, ident) => quote!(#ident),
        Ty::Str => quote!(::std::string::String),
        Ty::List(t) => {
            let t = binding_rust(t, types, bindings);
            quote!(::std::vec::Vec<#t>)
        }
        Ty::Option(t) => {
            let t = binding_rust(t, types, bindings);
            quote!(::std::option::Option<#t>)
        }
        Ty::Result(Some(t)) => {
            let t = binding_rust(t, types, bindings);
            quote!(::std::result::Result<#t, ::std::string::String>)
        }
        Ty::Result(None) => quote!(::std::result::Result<(), ::std::string::String>),
        Ty::Tuple(ts) => {
            let ts = ts.iter().map(|t| binding_rust(t, types, bindings));
            quote!((#(#ts,)*))
        }
        Ty::User(i) => {
            let b = &types[*i].binding;
            quote!(#bindings::#b)
        }
    }
}

fn conversion(t: &UserType, types: &[UserType], module: &Ident, bindings: &Ident) -> TokenStream2 {
    let _ = types;
    let user = &t.ident;
    let binding = &t.binding;
    let convert = quote!(::octosense_component::Convert::convert);
    match &t.shape {
        Shape::Record(fields) => {
            let to_binding = fields.iter().map(|(ident, wit, _)| {
                let b = binding_member(wit);
                quote!(#b: #convert(value.#ident))
            });
            let from_binding = fields.iter().map(|(ident, wit, _)| {
                let b = binding_member(wit);
                quote!(#ident: #convert(value.#b))
            });
            quote! {
                impl ::octosense_component::Convert<#bindings::#binding> for #module::#user {
                    fn convert(self) -> #bindings::#binding {
                        let value = self;
                        #bindings::#binding { #(#to_binding,)* }
                    }
                }
                impl ::octosense_component::Convert<#module::#user> for #bindings::#binding {
                    fn convert(self) -> #module::#user {
                        let value = self;
                        #module::#user { #(#from_binding,)* }
                    }
                }
            }
        }
        Shape::Enum(cases) => {
            let to_binding = cases.iter().map(|(ident, wit)| {
                let b = format_ident!("{}", wit.to_upper_camel_case());
                quote!(#module::#user::#ident => #bindings::#binding::#b)
            });
            let from_binding = cases.iter().map(|(ident, wit)| {
                let b = format_ident!("{}", wit.to_upper_camel_case());
                quote!(#bindings::#binding::#b => #module::#user::#ident)
            });
            quote! {
                impl ::octosense_component::Convert<#bindings::#binding> for #module::#user {
                    fn convert(self) -> #bindings::#binding {
                        match self { #(#to_binding,)* }
                    }
                }
                impl ::octosense_component::Convert<#module::#user> for #bindings::#binding {
                    fn convert(self) -> #module::#user {
                        match self { #(#from_binding,)* }
                    }
                }
            }
        }
        Shape::Variant(cases) => {
            let to_binding = cases.iter().map(|(ident, wit, ty)| {
                let b = format_ident!("{}", wit.to_upper_camel_case());
                match ty {
                    Some(_) => {
                        quote!(#module::#user::#ident(v) => #bindings::#binding::#b(#convert(v)))
                    }
                    None => quote!(#module::#user::#ident => #bindings::#binding::#b),
                }
            });
            let from_binding = cases.iter().map(|(ident, wit, ty)| {
                let b = format_ident!("{}", wit.to_upper_camel_case());
                match ty {
                    Some(_) => {
                        quote!(#bindings::#binding::#b(v) => #module::#user::#ident(#convert(v)))
                    }
                    None => quote!(#bindings::#binding::#b => #module::#user::#ident),
                }
            });
            quote! {
                impl ::octosense_component::Convert<#bindings::#binding> for #module::#user {
                    fn convert(self) -> #bindings::#binding {
                        match self { #(#to_binding,)* }
                    }
                }
                impl ::octosense_component::Convert<#module::#user> for #bindings::#binding {
                    fn convert(self) -> #module::#user {
                        match self { #(#from_binding,)* }
                    }
                }
            }
        }
    }
}

fn method(f: &Function, types: &[UserType], module: &Ident, bindings: &Ident) -> TokenStream2 {
    let name = &f.binding;
    let user = &f.ident;
    let convert = quote!(::octosense_component::Convert::convert);
    let params = f.params.iter().map(|(_, wit, param)| {
        let ident = binding_member(wit);
        let ty = match param {
            Param::Owned(ty) => binding_rust(ty, types, bindings),
            Param::StrRef => quote!(::std::string::String),
            Param::BytesRef => quote!(::std::vec::Vec<u8>),
        };
        quote!(#ident: #ty)
    });
    let args = f.params.iter().map(|(_, wit, param)| {
        let ident = binding_member(wit);
        match param {
            Param::Owned(_) => quote!(#convert(#ident)),
            Param::StrRef | Param::BytesRef => quote!(&#ident),
        }
    });
    match &f.result {
        Some(ty) => {
            let ret = binding_rust(ty, types, bindings);
            quote! {
                fn #name(#(#params),*) -> #ret {
                    #convert(#module::#user(#(#args),*))
                }
            }
        }
        None => quote! {
            fn #name(#(#params),*) {
                #module::#user(#(#args),*);
            }
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn expand_str(source: &str) -> Result<String, String> {
        let module: ItemMod = syn::parse_str(source).expect("test module parses");
        expand(module)
            .map(|t| t.to_string())
            .map_err(|e| e.to_string())
    }

    #[test]
    fn the_world_is_derived_from_rust_names_and_types() {
        let out = expand_str(
            r#"mod tools {
                pub struct Stats { pub word_count: u32, pub headings: Vec<String>, pub ratio: Option<f64> }
                pub enum Mode { Fast, Careful }
                pub enum Shape { Circle(f64), Pair((u8, i64)), Empty }
                pub fn to_html(markdown: &str, mode: Mode) -> Result<String, String> { todo!() }
                pub fn count_stats(data: &[u8]) -> Stats { todo!() }
                pub fn shapes(items: Vec<Shape>) -> Result<(), String> { todo!() }
                pub fn ping() {}
                fn private_helper() {}
            }"#,
        )
        .unwrap();
        for wit in [
            "record %stats {\\n    %word-count: u32,\\n    %headings: list<string>,\\n    %ratio: option<f64>,\\n  }",
            "enum %mode {\\n    %fast,\\n    %careful,\\n  }",
            "variant %shape {\\n    %circle(f64),\\n    %pair(tuple<u8, s64>),\\n    %empty,\\n  }",
            "export %to-html: func(%markdown: string, %mode: %mode) -> result<string, string>;",
            "export %count-stats: func(%data: list<u8>) -> %stats;",
            "export %shapes: func(%items: list<%shape>) -> result<_, string>;",
            "export %ping: func();",
        ] {
            assert!(out.contains(wit), "missing {wit} in {out}");
        }
        assert!(!out.contains("private-helper"));
    }

    #[test]
    fn unsupported_types_say_what_to_use_instead() {
        for (source, hint) in [
            ("mod m { pub fn f(n: usize) {} }", "use u32 or u64"),
            (
                "mod m { pub fn f(m: std::collections::HashMap<String, u32>) {} }",
                "maps and sets are not WIT types",
            ),
            (
                "mod m { pub fn f() -> Result<u32, std::io::Error> { todo!() } }",
                "return Result<T, String>",
            ),
            (
                "mod m { pub fn f(v: &Vec<u8>) {} }",
                "a parameter may borrow only &str or &[u8]",
            ),
            (
                "mod m { pub fn f() -> &'static str { todo!() } }",
                "references are not WIT values",
            ),
            ("mod m { pub fn f<T>(t: T) {} }", "cannot be generic"),
            ("mod m { pub async fn f() {} }", "cannot be async"),
            (
                "mod m { pub struct S { x: u32 } pub fn f(s: S) {} }",
                "make `S.x` pub",
            ),
            (
                "mod m { pub struct S { pub next: Option<Vec<S>> } pub fn f(s: S) {} }",
                "cannot be recursive",
            ),
            (
                "mod m { pub enum Len { A } pub fn len() -> Len { todo!() } }",
                "two items are both `len`",
            ),
            (
                "mod m { pub fn get_2d() {} }",
                "every part must start with a letter",
            ),
            (
                "mod m { pub fn functions() {} }",
                "the wasm service's own method",
            ),
            (
                "mod m { pub fn connect(addr: &str) -> String { addr.into() } }",
                "`connect` collides with wasi-libc's socket symbol",
            ),
            (
                "mod m { pub fn f(a_b: u8, a__b: u8) {} }",
                "`a_b` and `a__b` are both `a-b`",
            ),
            (
                "mod m { pub enum E { A_b, A__b } pub fn f(e: E) {} }",
                "are both `a-b`",
            ),
            ("mod m { fn hidden() {} }", "found no pub fn"),
            ("mod m;", "items inline"),
        ] {
            let error = expand_str(source).unwrap_err();
            assert!(error.contains(hint), "{source}: {error}");
        }
    }

    #[test]
    fn prefixed_socket_exports_and_private_helpers_do_not_collide() {
        let out =
            expand_str("mod m { fn connect() {} pub fn tcp_connect() { connect() } }").unwrap();
        assert!(out.contains("export %tcp-connect: func();"));
        assert!(!out.contains("export %connect:"));
    }
}
