"""What a WebAssembly function file is, what it imports and what it exports.

The same answer `hub component-info` prints (App Hub), for when no such hub
is at hand: `kind` (`component`, OctoSense ADR 0014, or `module`, ADR 0011),
`imports`, and `exports` with each function's parameters and result written
as WIT writes them (records, variants and enums by their shape). `tools/octo
wasm` uses it. Python 3.9+, no third-party packages.

It reads the binary format and does not validate it: App Hub's gate and the
host's `wasm` service do. A component's import and export names come from its
top-level import (10) and export (11) sections; each exported function's type
from the type (7), alias (6) and canon (8) sections that build the component's
type and function index spaces. A core module's come from its type (1),
import (2), function (3) and export (7) sections.

It also writes and reads the list of crates a component is built from: a
custom section named `octosense-crates` at the end of the file, for App Hub's
gate to show its reviewers and check against the RustSec advisory database.
`crate_inventory` asks cargo for the list, `with_crates` puts it in the file
and `recorded_crates` reads it back. The release workflow
(tools/publish-app.template.yml) writes the same bytes with its own copy of
these steps.
"""
import json
from pathlib import Path
import re
import subprocess

COMPONENT_PREAMBLE = b"\0asm\x0d\x00\x01\x00"
MODULE_PREAMBLE = b"\0asm\x01\x00\x00\x00"

# The packages a component may import (ADR 0014); the same list as App Hub's
# ALLOWED_COMPONENT_IMPORTS. Files stay in the app's bounded private folder;
# wasi:http and wasi:sockets reach the network. Capability and destination declarations
# disclose usage rather than authorize execution. octosense:host keeps the
# app identity, actual service authorization and background-surface limits.
# A package name is matched whole.
ALLOWED_IMPORTS = ("wasi:cli/", "wasi:clocks/", "wasi:filesystem/", "wasi:http/", "wasi:io/", "wasi:random/",
                   "wasi:sockets/", "octosense:host/")
FILESYSTEM = "wasi:filesystem/"
HTTP = "wasi:http/"
SOCKETS = "wasi:sockets/"
HOST_SERVICES = "octosense:host/"

PRIMITIVES = {
    0x7f: "bool", 0x7e: "s8", 0x7d: "u8", 0x7c: "s16", 0x7b: "u16", 0x7a: "s32",
    0x79: "u32", 0x78: "s64", 0x77: "u64", 0x76: "f32", 0x75: "f64", 0x74: "char",
    0x73: "string", 0x64: "error-context",
}
CORE_TYPES = {0x7f: "i32", 0x7e: "i64", 0x7d: "f32", 0x7c: "f64", 0x7b: "v128", 0x70: "funcref", 0x6f: "externref"}


class ReadError(ValueError):
    """The bytes are not what this reader understands."""


class Reader:
    def __init__(self, data, pos=0, end=None):
        self.data = data
        self.pos = pos
        self.end = len(data) if end is None else end

    def done(self):
        return self.pos >= self.end

    def peek(self):
        if self.pos >= self.end:
            raise ReadError("unexpected end of the file")
        return self.data[self.pos]

    def byte(self):
        value = self.peek()
        self.pos += 1
        return value

    def take(self, n):
        if n > self.end - self.pos:
            raise ReadError("unexpected end of the file")
        value = self.data[self.pos:self.pos + n]
        self.pos += n
        return value

    def uleb(self, bits=32):
        result = shift = 0
        while True:
            b = self.byte()
            result |= (b & 0x7f) << shift
            shift += 7
            if not b & 0x80:
                break
            if shift >= bits + 7:
                raise ReadError("an integer is too long")
        if result >> bits:
            raise ReadError("an integer is out of range")
        return result

    def u32(self):
        return self.uleb(32)

    def s33(self):
        result = shift = 0
        while True:
            b = self.byte()
            result |= (b & 0x7f) << shift
            shift += 7
            if not b & 0x80:
                break
            if shift > 35:
                raise ReadError("an integer is too long")
        if b & 0x40:
            result -= 1 << shift
        return result

    def string(self):
        raw = self.take(self.u32())
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ReadError("a name is not UTF-8")

    def flag(self):
        value = self.byte()
        if value not in (0, 1):
            raise ReadError(f"expected 0 or 1, found {value:#x}")
        return value == 1


def section_spans(data, preamble):
    """(id, start, contents' start, end) for each top-level section: its
    bytes are data[start:end], and its contents data[contents' start:end]."""
    r = Reader(data, len(preamble))
    while not r.done():
        start = r.pos
        sid = r.byte()
        size = r.u32()
        if size > r.end - r.pos:
            raise ReadError(f"section {sid} runs past the end of the file")
        yield sid, start, r.pos, r.pos + size
        r.pos += size


def sections(data, preamble):
    """(id, Reader over its contents) for each top-level section."""
    for sid, _, begin, end in section_spans(data, preamble):
        yield sid, Reader(data, begin, end)


def describe(data):
    """`hub component-info`'s answer as a dict: kind, imports, exports. A
    component whose function types this reader cannot follow still has its
    imports and export names, and `unresolved` says why its parameters are
    missing."""
    if data.startswith(COMPONENT_PREAMBLE):
        return describe_component(data)
    if data.startswith(MODULE_PREAMBLE):
        return describe_module(data)
    raise ReadError("not a WebAssembly core module or component")


# ------------------------------------------------------------------ component
def extern_name(r):
    """An import or export name (`importname'` / `exportname'`)."""
    tag = r.byte()
    if tag in (0x00, 0x01):  # 0x01: older binaries' interface-name marker
        return r.string()
    if tag != 0x02:
        raise ReadError(f"unknown name encoding {tag:#x}")
    name = r.string()
    implements = suffix = None
    for _ in range(r.u32()):
        option = r.byte()
        value = r.string()
        if option == 0x00:
            implements = value
        elif option == 0x01:
            suffix = value
        elif option != 0x02:
            raise ReadError(f"unknown name option {option:#x}")
    if suffix and not implements and "@" in name:
        name += suffix
    return name


def sort(r):
    """A sort: 'core' (with its core sort), 'func', 'value', 'type', 'component' or 'instance'."""
    b = r.byte()
    if b == 0x00:
        r.byte()
        return "core"
    names = {0x01: "func", 0x02: "value", 0x03: "type", 0x04: "component", 0x05: "instance"}
    if b not in names:
        raise ReadError(f"unknown sort {b:#x}")
    return names[b]


def valtype(r):
    b = r.peek()
    if b in PRIMITIVES:
        r.byte()
        return ("prim", PRIMITIVES[b])
    index = r.s33()
    if index < 0:
        raise ReadError(f"unknown value type {b:#x}")
    return ("idx", index)


def optional_valtype(r):
    return valtype(r) if r.flag() else None


def externdesc(r):
    b = r.byte()
    if b == 0x00:
        if r.byte() != 0x11:
            raise ReadError("unknown core extern kind")
        return ("module", r.u32())
    if b == 0x01:
        return ("func", r.u32())
    if b == 0x02:
        bound = r.byte()
        if bound == 0x00:
            return ("value", r.u32())
        if bound == 0x01:
            return ("value", valtype(r))
        raise ReadError("unknown value bound")
    if b == 0x03:
        bound = r.byte()
        if bound == 0x00:
            return ("type-eq", r.u32())
        if bound == 0x01:
            return ("type-sub",)
        raise ReadError("unknown type bound")
    if b == 0x04:
        return ("component", r.u32())
    if b == 0x05:
        return ("instance", r.u32())
    raise ReadError(f"unknown extern kind {b:#x}")


def alias(r):
    """(sort, target): target is ('export', instance, name), ('core-export', …) or ('outer', count, index)."""
    kind = sort(r)
    target = r.byte()
    if target == 0x00:
        return kind, ("export", r.u32(), r.string())
    if target == 0x01:
        return kind, ("core-export", r.u32(), r.string())
    if target == 0x02:
        return kind, ("outer", r.u32(), r.u32())
    raise ReadError(f"unknown alias target {target:#x}")


def declarations(r, component):
    """Skips an instance or component type's declarations."""
    for _ in range(r.u32()):
        tag = r.byte()
        if tag == 0x01:
            deftype(r)
        elif tag == 0x02:
            alias(r)
        elif tag == 0x04 or (tag == 0x03 and component):
            extern_name(r)
            externdesc(r)
        else:
            raise ReadError(f"unsupported declaration {tag:#x} in an instance or component type")


def deftype(r):
    b = r.byte()
    if b == 0x3f:  # resource (rep i32), with an optional destructor
        r.byte()
        if r.flag():
            r.u32()
        return ("resource",)
    if b in (0x40, 0x43):  # function, synchronous or async
        params = [(r.string(), valtype(r)) for _ in range(r.u32())]
        kind = r.byte()
        if kind == 0x00:
            result = valtype(r)
        elif kind == 0x01 and r.byte() == 0x00:
            result = None
        else:
            raise ReadError("unknown function result encoding")
        return ("func", params, result)
    if b in (0x41, 0x42):
        declarations(r, component=b == 0x41)
        return ("component",) if b == 0x41 else ("instance",)
    if b in PRIMITIVES:
        return ("prim", PRIMITIVES[b])
    if b == 0x72:
        return ("record", [(r.string(), valtype(r)) for _ in range(r.u32())])
    if b == 0x71:
        cases = []
        for _ in range(r.u32()):
            name, ty = r.string(), optional_valtype(r)
            if r.byte() != 0x00:
                raise ReadError("a variant case's refinement is not supported")
            cases.append((name, ty))
        return ("variant", cases)
    if b == 0x70:
        return ("list", valtype(r))
    if b == 0x67:
        return ("list", valtype(r), r.u32())
    if b == 0x63:
        return ("map", valtype(r), valtype(r))
    if b == 0x6f:
        return ("tuple", [valtype(r) for _ in range(r.u32())])
    if b == 0x6e:
        return ("flags", [r.string() for _ in range(r.u32())])
    if b == 0x6d:
        return ("enum", [r.string() for _ in range(r.u32())])
    if b == 0x6b:
        return ("option", valtype(r))
    if b == 0x6a:
        return ("result", optional_valtype(r), optional_valtype(r))
    if b in (0x69, 0x68):
        return ("handle", r.u32())
    if b in (0x66, 0x65):
        return ("async", optional_valtype(r))
    raise ReadError(f"unknown type {b:#x}")


def canon_options(r):
    for _ in range(r.u32()):
        option = r.byte()
        if option in (0x03, 0x04, 0x05, 0x07, 0x08):
            r.u32()
        elif option not in (0x00, 0x01, 0x02, 0x06, 0x09):
            raise ReadError(f"unknown canonical option {option:#x}")


def canon(r):
    """The type index of a lifted function, or None for the other canonical
    built-ins, which make core functions."""
    op = r.byte()
    if op == 0x00:
        if r.byte() != 0x00:
            raise ReadError("unknown lift encoding")
        r.u32()
        canon_options(r)
        return r.u32()
    if op == 0x01:
        if r.byte() != 0x00:
            raise ReadError("unknown lower encoding")
        r.u32()
        canon_options(r)
        return None
    if op in (0x02, 0x03, 0x04, 0x0e, 0x13, 0x14, 0x15, 0x1a, 0x1b, 0x2e, 0x2f, 0x40):
        r.u32()
        return None
    if op in (0x05, 0x0d, 0x1e, 0x1f, 0x22, 0x23, 0x24, 0x25, 0x26, 0x28, 0x42):
        return None
    if op in (0x0f, 0x10, 0x16, 0x17):
        r.u32()
        canon_options(r)
        return None
    if op in (0x11, 0x12, 0x18, 0x19):
        r.u32()
        r.byte()
        return None
    if op in (0x1c, 0x1d):
        canon_options(r)
        return None
    if op in (0x27, 0x41):
        r.u32()
        r.u32()
        return None
    # Async task and thread built-ins: a synchronous component has none.
    raise ReadError(f"unsupported canonical function {op:#x}")


def component_names(data):
    """The top-level import names (but `(type (eq …))` ones, a name for a
    type the component already has, which reaches nothing) and the function
    and instance export names, in order."""
    imports, exports = [], []
    for sid, r in sections(data, COMPONENT_PREAMBLE):
        if sid == 10:
            for _ in range(r.u32()):
                name = extern_name(r)
                if externdesc(r)[0] != "type-eq":
                    imports.append(name)
        elif sid == 11:
            for _ in range(r.u32()):
                name = extern_name(r)
                kind = sort(r)
                r.u32()
                if r.flag():
                    externdesc(r)
                if kind in ("func", "instance"):
                    exports.append((name, kind))
    return imports, exports


def component_signatures(data):
    """{export name: (params, result)} for the exported functions, from the
    component's type and function index spaces."""
    types = []  # ("def", deftype) | ("ref", index) | ("opaque",)
    funcs = []  # a function type's index, or None when not followed
    found = {}
    for sid, r in sections(data, COMPONENT_PREAMBLE):
        if sid == 7:
            for _ in range(r.u32()):
                types.append(("def", deftype(r)))
        elif sid == 6:
            for _ in range(r.u32()):
                kind, _target = alias(r)
                if kind == "type":
                    types.append(("opaque",))
                elif kind == "func":
                    funcs.append(None)
        elif sid == 8:
            for _ in range(r.u32()):
                lifted = canon(r)
                if lifted is not None:
                    funcs.append(lifted)
        elif sid == 10:
            for _ in range(r.u32()):
                extern_name(r)
                desc = externdesc(r)
                if desc[0] == "func":
                    funcs.append(desc[1])
                elif desc[0] == "type-eq":
                    types.append(("ref", desc[1]))
                elif desc[0] == "type-sub":
                    types.append(("opaque",))
        elif sid == 11:
            for _ in range(r.u32()):
                name = extern_name(r)
                kind = sort(r)
                index = r.u32()
                desc = externdesc(r) if r.flag() else None
                if kind == "func":
                    if desc and desc[0] == "func":
                        func_type = desc[1]
                    elif index < len(funcs):
                        func_type = funcs[index]
                    else:
                        raise ReadError(f"export {name!r} names function {index}, which is not defined")
                    funcs.append(func_type)
                    found[name] = func_type
                elif kind == "type":
                    types.append(("ref", desc[1] if desc and desc[0] == "type-eq" else index))
    return {name: function_type(types, index) for name, index in found.items()}


def resolve(types, index):
    for _ in range(len(types) + 1):
        if index is None or index >= len(types):
            return None
        entry = types[index]
        if entry[0] == "ref":
            index = entry[1]
            continue
        return entry[1] if entry[0] == "def" else None
    return None


def function_type(types, index):
    ty = resolve(types, index)
    if ty is None or ty[0] != "func":
        return None
    params = [[name, wit(types, t)] for name, t in ty[1]]
    return params, (wit(types, ty[2]) if ty[2] is not None else None)


def wit(types, vt, depth=0):
    """A value type as WIT writes it, as `hub component-info` and OctoSense's
    `wasm.functions` show it: records, variants and enums by their shape;
    a resource handle, a future, a stream or a map is `resource`."""
    if vt[0] == "prim":
        return vt[1]
    ty = resolve(types, vt[1])
    if ty is None or depth > 64:
        return "resource"
    sub = lambda t: wit(types, t, depth + 1)  # noqa: E731
    kind = ty[0]
    if kind == "prim":
        return ty[1]
    if kind == "record":
        return "record { " + ", ".join(f"{n}: {sub(t)}" for n, t in ty[1]) + " }"
    if kind == "variant":
        return "variant { " + ", ".join(f"{n}({sub(t)})" if t else n for n, t in ty[1]) + " }"
    if kind == "list":
        return f"list<{sub(ty[1])}>"
    if kind == "tuple":
        return "tuple<" + ", ".join(sub(t) for t in ty[1]) + ">"
    if kind == "flags":
        return "flags { " + ", ".join(ty[1]) + " }"
    if kind == "enum":
        return "enum { " + ", ".join(ty[1]) + " }"
    if kind == "option":
        return f"option<{sub(ty[1])}>"
    if kind == "result":
        ok, err = ty[1], ty[2]
        if ok and err:
            return f"result<{sub(ok)}, {sub(err)}>"
        if ok:
            return f"result<{sub(ok)}>"
        if err:
            return f"result<_, {sub(err)}>"
        return "result"
    return "resource"


def describe_component(data):
    imports, names = component_names(data)
    unresolved = None
    try:
        signatures = component_signatures(data)
    except ReadError as error:
        signatures, unresolved = {}, str(error)
    exports = []
    for name, kind in names:
        signature = signatures.get(name) if kind == "func" else None
        if signature is None and unresolved is None:
            unresolved = (f"{name} is an exported interface; octo's reader lists only a world's own functions"
                          if kind == "instance" else f"the type of {name} could not be followed")
        params, result = signature if signature else (None, None)
        exports.append({"name": name, "params": params, "result": result})
    exports.sort(key=lambda e: e["name"])
    info = {"kind": "component", "imports": imports, "exports": exports}
    if unresolved:
        info["unresolved"] = unresolved
    return info


# ---------------------------------------------------------------- core module
def core_valtype(r):
    b = r.byte()
    if b not in CORE_TYPES:
        raise ReadError(f"unsupported core value type {b:#x}")
    return CORE_TYPES[b]


def limits(r):
    flags = r.byte()
    if flags & ~0x0f:
        raise ReadError("unknown limits")
    bits = 64 if flags & 0x04 else 32
    r.uleb(bits)
    if flags & 0x01:
        r.uleb(bits)
    if flags & 0x08:
        r.u32()


def describe_module(data):
    """A core module's imports (`module.name`) and exported functions with
    their core types: parameters `p0`, `p1`, …."""
    imports, exports = [], []
    signatures, func_types = [], []
    unresolved = None
    for sid, r in sections(data, MODULE_PREAMBLE):
        try:
            if sid == 1:
                for _ in range(r.u32()):
                    if r.byte() != 0x60:
                        raise ReadError("a type other than a plain function type")
                    params = [core_valtype(r) for _ in range(r.u32())]
                    results = [core_valtype(r) for _ in range(r.u32())]
                    signatures.append((params, results))
            elif sid == 2:
                for _ in range(r.u32()):
                    module, name = r.string(), r.string()
                    imports.append(f"{module}.{name}")
                    kind = r.byte()
                    if kind == 0x00:
                        func_types.append(r.u32())
                    elif kind == 0x01:
                        if r.byte() not in (0x70, 0x6f):
                            raise ReadError("a table of an unsupported reference type")
                        limits(r)
                    elif kind == 0x02:
                        limits(r)
                    elif kind == 0x03:
                        core_valtype(r)
                        r.flag()
                    elif kind == 0x04:
                        r.byte()
                        r.u32()
                    else:
                        raise ReadError(f"unknown import kind {kind:#x}")
            elif sid == 3:
                func_types.extend(r.u32() for _ in range(r.u32()))
            elif sid == 7:
                for _ in range(r.u32()):
                    name, kind, index = r.string(), r.byte(), r.u32()
                    if kind == 0x00:
                        exports.append((name, index))
        except ReadError as error:
            if sid in (2, 7):
                raise
            unresolved = str(error)
    described = []
    for name, index in exports:
        params = result = None
        if unresolved is None and index < len(func_types) and func_types[index] < len(signatures):
            ps, rs = signatures[func_types[index]]
            params = [[f"p{i}", t] for i, t in enumerate(ps)]
            result = None if not rs else rs[0] if len(rs) == 1 else "(" + ", ".join(rs) + ")"
        described.append({"name": name, "params": params, "result": result})
    info = {"kind": "module", "imports": imports, "exports": described}
    if unresolved:
        info["unresolved"] = unresolved
    return info


# ------------------------------------------------------------------- policies
def refused_imports(imports):
    """The imports no host gives a component: anything outside ALLOWED_IMPORTS."""
    return [name for name in imports if not name.startswith(ALLOWED_IMPORTS)]


def uses_files(imports):
    """Whether it imports wasi:filesystem: the app's bounded storage folder."""
    return any(name.startswith(FILESYSTEM) for name in imports)


def uses_http(imports):
    """Whether it imports wasi:http: the network, which the app declares with `net`."""
    return any(name.startswith(HTTP) for name in imports)


def uses_sockets(imports):
    """TCP, UDP or DNS: requires the host's wasm.sockets@1 compatibility API."""
    return any(name.startswith(SOCKETS) for name in imports)


def uses_host_services(imports):
    """Whether it imports octosense:host: the public host services available to its app."""
    return any(name.startswith(HOST_SERVICES) for name in imports)


def reach(imports):
    """What a component reaches, in App Hub's words for its reviewers
    (`ComponentInfo::reach`): "the clock, files in its app folder and the
    network, but no other app"."""
    has = lambda prefix: any(name.startswith(prefix) for name in imports)  # noqa: E731
    files = uses_files(imports)
    network = uses_http(imports) or uses_sockets(imports)
    reaches = []
    if has("wasi:clocks/"):
        reaches.append("the clock")
    if has("wasi:random/"):
        reaches.append("random numbers")
    if files:
        reaches.append("files in its app folder")
    if network:
        reaches.append("the network")
    if uses_host_services(imports):
        reaches.append("its app's host services")
    nothing_else = {
        (True, True): "no other app",
        (True, False): "no network or other app",
        (False, True): "no files or other app",
        (False, False): "no files, network or other app",
    }[(files, network)]
    if not reaches:
        return "nothing but its input"
    if len(reaches) == 1:
        return f"{reaches[0]}, but {nothing_else}"
    return f"{', '.join(reaches[:-1])} and {reaches[-1]}, but {nothing_else}"


# ----------------------------------------------------------------- crate list
# The crates a component is built from, in a custom section at the very end of
# the file: id 0, the size of the rest, the name `octosense-crates`, then the
# payload. The payload is the UTF-8 JSON of {"schema": 1, "crates": [{"name",
# "version", "source", "checksum"}, …]}, keys sorted and without spaces, the
# crates sorted by name and version, for App Hub's gate to show its reviewers
# and check against the RustSec advisory database. The release workflow
# (tools/publish-app.template.yml) writes the same bytes with its own copy of
# these steps, and tools/test_octo.py compares the two.
CRATES_SECTION = "octosense-crates"
CRATES_SCHEMA = 1
CRATES_IO = ("registry+https://github.com/rust-lang/crates.io-index", "sparse+https://index.crates.io/")
TARGET = "wasm32-wasip2"


class CrateListError(ValueError):
    """cargo could not say which crates a component is built from."""


def crate_source(source):
    """Where a package comes from, as the crate list says it: `crates.io`,
    `git+<url>#<commit>` (without the URL's ?rev= or ?branch= query), `path`,
    or another registry's source as cargo writes it."""
    if source is None:
        return "path"
    if source in CRATES_IO:
        return "crates.io"
    if source.startswith("git+"):
        url, mark, commit = source.partition("#")
        return url.split("?")[0] + mark + commit
    return source


def lock_checksums(lockfile):
    """{(name, version, crate_source): checksum} from a Cargo.lock's
    [[package]] tables: registry packages have a checksum, git and path ones
    none. It reads only the `key = "value"` lines it needs, as Python before
    3.11 has no TOML reader."""
    tables, table = [], None
    text = lockfile.read_text(encoding="utf-8") if lockfile.is_file() else ""
    for line in text.splitlines():
        if line.startswith("["):
            table = {} if line.strip() == "[[package]]" else None
            if table is not None:
                tables.append(table)
        elif table is not None and re.match(r'(name|version|source|checksum) = "[^"]*"$', line):
            key, value = line.split(" = ", 1)
            table[key] = value[1:-1]
    return {(t.get("name"), t.get("version"), crate_source(t.get("source"))): t["checksum"]
            for t in tables if "checksum" in t}


def is_proc_macro(package):
    """A proc macro runs inside the compiler, so none of its code is in the
    binary. Any of its targets says so: a build script is a target too."""
    return any("proc-macro" in target.get("kind", []) for target in package.get("targets", []))


def linked_packages(meta, root):
    """The ids of the packages a component links, from `cargo metadata`
    filtered to its platform (`meta`): the root package (id `root`) and what
    its normal dependencies reach. Build and dev dependencies run on the build
    machine, and so do proc macros: the walk never goes into one, so their own
    dependencies (syn, quote, wit-parser, …) are not in the list either."""
    packages = {p["id"]: p for p in meta["packages"]}
    nodes = {node["id"]: node for node in meta["resolve"]["nodes"]}
    linked, todo = set(), [root]
    while todo:
        node = nodes.get(todo.pop())
        if node is None or node["id"] in linked or is_proc_macro(packages.get(node["id"], {})):
            continue
        linked.add(node["id"])
        todo += [d["pkg"] for d in node.get("deps", [])
                 if any(k.get("kind") is None for k in d.get("dep_kinds", [{"kind": None}]))]
    return linked


def root_package(meta, manifest):
    """The package whose Cargo.toml is `manifest`, or None for a workspace."""
    manifest = Path(manifest).resolve()
    return next((p for p in meta["packages"] if Path(p["manifest_path"]).resolve() == manifest), None)


def crates_from_metadata(meta, manifest):
    """The crate list of the package whose Cargo.toml is `manifest`: every
    package it links but itself, with the checksums from the workspace's
    Cargo.lock. `meta` is `cargo metadata --filter-platform wasm32-wasip2`."""
    root = root_package(meta, manifest)
    if root is None:
        raise CrateListError(f"{manifest} is a workspace, not a package; pass a component crate's own directory")
    packages = {p["id"]: p for p in meta["packages"]}
    checksums = lock_checksums(Path(meta["workspace_root"]) / "Cargo.lock")
    crates = []
    for package_id in linked_packages(meta, root["id"]) - {root["id"]}:
        package = packages[package_id]
        entry = {"name": package["name"], "version": package["version"], "source": crate_source(package.get("source"))}
        checksum = checksums.get((entry["name"], entry["version"], entry["source"]))
        if checksum:
            entry["checksum"] = checksum
        crates.append(entry)
    crates.sort(key=lambda c: (c["name"], c["version"], c["source"]))
    return {"schema": CRATES_SCHEMA, "crates": crates}


def crate_inventory(cargo, crate):
    """The crate list of the component crate in directory `crate`, once cargo
    has built it, so that its Cargo.lock is current."""
    crate = Path(crate).resolve()
    manifest = crate / "Cargo.toml"
    cmd = [cargo, "metadata", "--format-version", "1", "--filter-platform", TARGET, "--manifest-path", str(manifest)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=crate)
    if r.returncode != 0:
        raise CrateListError("cargo metadata failed: " + ((r.stderr or "").strip().splitlines() or ["no output"])[-1])
    return crates_from_metadata(json.loads(r.stdout), manifest)


def leb128(n):
    """`n` as an unsigned LEB128 integer, in its shortest form."""
    out = bytearray()
    while True:
        byte, n = n & 0x7F, n >> 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def preamble_of(data):
    for preamble in (COMPONENT_PREAMBLE, MODULE_PREAMBLE):
        if data.startswith(preamble):
            return preamble
    raise ReadError("not a WebAssembly core module or component")


def custom_sections(data):
    """(start, end, name as bytes, payload's start) for each top-level custom
    section, and only those: one inside a nested core module is not the
    component's."""
    for sid, start, begin, end in section_spans(data, preamble_of(data)):
        if sid == 0:
            r = Reader(data, begin, end)
            name = r.take(r.u32())
            yield start, end, name, r.pos


def with_crates(data, inventory):
    """`data` with `inventory` (crate_inventory's list) in an
    `octosense-crates` custom section at its very end. A section of that name
    already there is dropped, so the file never holds two."""
    name = CRATES_SECTION.encode()
    drop = [(start, end) for start, end, found, _ in custom_sections(data) if found == name]
    out, pos = bytearray(), 0
    for start, end in drop:
        out += data[pos:start]
        pos = end
    out += data[pos:]
    payload = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body = leb128(len(name)) + name + payload
    return bytes(out) + b"\x00" + leb128(len(body)) + body


def recorded_crates(data):
    """The crate list a file's `octosense-crates` section holds, as a dict
    ({"schema": 1, "crates": […]}), or None when it has no such section."""
    found = [data[begin:end] for _, end, name, begin in custom_sections(data) if name == CRATES_SECTION.encode()]
    if not found:
        return None
    if len(found) > 1:
        raise ReadError(f"it has {len(found)} {CRATES_SECTION} sections, where a component carries one")
    try:
        listed = json.loads(found[0].decode("utf-8"))
    except ValueError:  # UnicodeDecodeError and json.JSONDecodeError are ValueErrors
        raise ReadError(f"its {CRATES_SECTION} section is not UTF-8 JSON")
    if not isinstance(listed, dict) or listed.get("schema") != CRATES_SCHEMA or not isinstance(listed.get("crates"), list):
        raise ReadError(f"its {CRATES_SECTION} section is not a schema {CRATES_SCHEMA} crate list")
    return listed
