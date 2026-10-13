# ADR 0001: The VM query API: two functions, and nothing else

- **Date:** 2026-10-13
- **Status:** Accepted (2026-10-13). Implemented as issue #9, in [OctoSense-org/makepad](https://github.com/OctoSense-org/makepad), `platform/script` (crate `makepad-script`, version 1.0.0), commit `136e775`: `query::object_keys` and `query::module_object`; the fixture corpus `platform/script/tests/query_corpus.txt` with a runner per installing crate (`cargo test -p makepad-script` for the modules the crate itself installs, `cargo test -p makepad-widgets` for the isolate's widget-facing modules); and the checked-in surface file `platform/script/tests/query_api_surface.txt`, which `tests/query_api_surface.rs` enforces — the semver check's equivalent, since there is no CI and no crates.io. The chain-walk proof §2 asks for is `tests/query_api.rs::the_prototype_chain_is_walkable_from_outside_with_the_existing_accessors`.
- **Scope:** How an editor-facing consumer asks the Splash VM which names exist — what the query API contains, what it deliberately leaves out, and how its stability is promised. It does not decide what the language server does with the answer; that is [ADR 0002](0002-analysis-posture-and-one-suppression-rule.md) and issue #8. This record lives in App Flow, where the spec and every ticket that cites it live; the code it governs lands in the makepad fork.
- **Relates to:** [ADR 0002](0002-analysis-posture-and-one-suppression-rule.md), [ADR 0003](0003-download-first-server-distribution.md); App Flow #1 (the spec), #8, #9; OctoSense [ADR 0005](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0005-app-contract.md), whose stability discipline this copies because it solved the same problem for a shared crate.

## Context

Completion has one rule that decides the whole design: **a suggestion must be a name that exists.** A wrong suggestion is worse than no suggestion, so the data cannot be a hand-written schema or a generated one — it has to be the registry the app itself runs against. That registry is a live `ScriptVm`: widget families in `mod.prelude.widgets`, the `sys`, `host`, `fs` and `agent` modules an isolate installs, and the standard library's `net`, `std`, `math`, `pod` and `shader` (`widgets/src/lib.rs:303`, `widgets/src/lib.rs:363`, `widgets/src/splash.rs:1315`, `widgets/src/splash.rs:1347`, `widgets/src/splash_host.rs:243`, `widgets/src/splash_storage.rs:243`).

Every completion in the spec is one of two questions:

1. **What names does this object have?** Widget names in the registry; the properties the current widget accepts, including the ones it inherits; an enum's values, which are the keys of the enum object; a module's members.
2. **Give me the object called X.** The module named `sys`; the widget proto named `Label`; the enum object a field's type points at.

Everything the VM needs to answer both is already public, which is why this API is a wrapper and not a mechanism:

| Existing accessor | What it gives |
| --- | --- |
| `ScriptHeap::map_ref` (`platform/script/src/object_heap.rs:1105`) with `ScriptObjectMap::keys()` (`platform/script/src/value_map.rs:262`) | an object's own entries |
| `ScriptHeap::iter_key_value` (`object_heap.rs:1193`) with `iter_len` (`object_heap.rs:1186`) | the same, spanning an object's vec and map entries |
| `ScriptHeap::module` / `ScriptVm::module` (`heap.rs:569`, `vm.rs:1418`) | the module object for a name |
| `ScriptVm::proto_map_iter_mut_with` (`vm.rs:1437`) | a prototype chain walked root to leaf |

A wrapper that grows is how a shared crate loses its shape, so this ADR fixes the count and the semantics before the first caller exists.

### What shaped this decision (measured)

- **The fork has no CI.** `gh api repos/OctoSense-org/makepad/actions/workflows` answers `{"total_count": 0}`, and `gh api repos/OctoSense-org/makepad/contents/.github` answers 404. Nothing runs the tests on a push, so "CI will catch a breaking change" is not available as a stability mechanism for this API.
- **`makepad-script` is not published.** The crates.io API answers `crate 'makepad-script' does not exist`, so "semver on crates.io" is not available either. The `1.0.0` in `platform/script/Cargo.toml` is a promise this repository keeps by hand, exactly the position ADR 0005 §3 describes for a contract taken from a git revision.
- **Map order is not a contract.** `ValueMap` is a `Vec` up to 16 entries and a `HashMap` past that, and says so: "Key order is not part of the map contract (callers track ordering via ScriptMapTag::order)" (`value_map.rs:61-64`). A query API that returned keys in map order would hand a consumer an order that changes when an object grows past the spill threshold, and a golden fixture built on it would flake for no reason a reader could see.

## Decision

### 1. Two functions, and the count is the decision

1. **Enumerate an object's own keys.** `object_keys(object) -> [name]`: the object's own entries, each name once, in a deterministic order (sorted), without values. Not the prototype chain — see §2.
2. **Get a module object by name.** `module_object(name) -> object | nil`. A name the VM does not have is nil. It is never a trap and never a panic.

These two, because every question above reduces to one of them, and because each addition to a shared crate's public surface is a promise someone has to keep for as long as the crate is at that major version. The exact spelling is issue #9's to choose; the count and the semantics are fixed here. Issue #9 chose a `query` module holding `object_keys(heap, object) -> Vec<String>` and `module_object(heap, name) -> Option<ScriptObject>`, so the promised surface is one small file a reviewer can read in a sitting.

### 2. Prototype-chain traversal is not in the API

`object_keys` returns own keys only. A widget's inherited properties — `draw_bg` on a `Label`, which comes from `View` — are the consumer's business, walked with the accessors that already exist: `ScriptVm::proto_map_iter_mut_with` (`vm.rs:1437`), or the object's own `proto` field.

The reason is not minimalism for its own sake. A `keys` that walked the chain would have to answer, inside the VM, questions the VM has no business deciding: does a shadowed name appear once or twice, in which order, and does a native type's getter table count as a key? Those are policy, and policy belongs to the one consumer that has a use for it. Issue #9's fourth acceptance criterion is a test proving the chain is walkable from outside with the existing accessors — that test is what makes leaving it out safe rather than merely tidy.

### 3. Read-only, and never a trap

Neither function mutates the heap, runs script, or charges an instruction budget: they are reads an editor performs per keystroke. Neither traps. The default type getter traps with `no getter for field {:?} on type {:?}` (`platform/script/src/native.rs:326-334`), so a query API that inherited that behaviour would turn a completion request into a script error — and the one place a language server must not produce an error is the path it takes while the person is typing.

### 4. The stability promise: a corpus and an additive-only rule, because there is no CI and no crates.io

ADR 0005 pins the app contract with a fixture corpus of real manifests that every release must accept, plus additive-only within `1.x`. The same two mechanisms, and nothing that needs a CI runner:

- **Additive only within `1.x`.** New functions and new optional results are `1.x`; removing or reinterpreting either function, or changing the order `object_keys` returns, is `2.0` and is called out in the fork's release notes.
- **A fixture corpus of real objects.** A checked-in corpus naming the modules and objects a real isolate installs — `mod.prelude.widgets`, `mod.host`, `mod.fs`, `mod.sys`, `mod.net`, `mod.std` — with the key sets each must answer. It lives with the crate (`platform/script/tests/`, which already holds the crate's behaviour tests) so it runs with one command anyone can type: `cargo test -p makepad-script`. A consumer that links the crate links the corpus. Issue #9 kept the file there and added a second runner in the widgets crate, because three of those six modules are installed by the isolate setup in `makepad-widgets` rather than by this crate: one corpus file, checked by `cargo test -p makepad-script` for the entries the crate itself installs and by `cargo test -p makepad-widgets` for the rest, each entry naming its runner.
- **The corpus is the review artifact.** Because no CI runs it, a change to either function names the corpus diff in its pull request. A green local run that nobody wrote down is not a promise.

### 5. Where it lives

In `makepad-script` (`platform/script`), the shared VM crate, not in `makepad-widgets` where the language server sits. The query is about the VM's own objects; a host that is not an editor has the same question, and a second copy in the widgets crate would be a second thing to keep stable.

## Consequences

- The completion provider (issue #8) becomes a reader: it asks for keys, walks protos itself, and formats. It cannot be wrong about whether a name exists, which was the whole point.
- A consumer cannot ask the VM "what properties does type X have", "what are this enum's variants as a list", or "where is this name declared". Those are either derivable from the two functions or are a separate decision with its own stability cost. If a third function is ever needed, this ADR is amended, not quietly extended.
- Every consumer pays for the corpus: a change to a module's members is a visible diff in a checked-in file, which is the intended friction.

## Alternatives considered

- **Expose the heap (`ScriptValue`, `ScriptObject`, `ScriptObjectMap`) directly.** Rejected: it publishes the heap's representation, so no internal change to it is possible without a breaking change, and it hands a caller the ability to mint values in a heap it does not own.
- **Emit a JSON schema of the registry.** Rejected: a schema is a snapshot that drifts from the code that produced it, and the failure mode is exactly the one the spec forbids — a suggestion for a name that no longer exists.
- **Put a "complete at position" function in the VM.** Rejected: that is parser and cursor policy, it belongs to the language server, and it would make every editor behaviour change a change to the shared crate's public API.
- **Walk the prototype chain inside `object_keys`.** Rejected; see §2.

## Measurements

Run on Windows, 2026-10-13:

```
$ gh api repos/OctoSense-org/makepad/actions/workflows --jq .total_count
0
$ gh api repos/OctoSense-org/makepad/contents/.github
{"message":"Not Found", ... "status":"404"}
$ curl -s -H "User-Agent: adr-research" https://crates.io/api/v1/crates/makepad-script
{"errors":[{"detail":"crate `makepad-script` does not exist"}]}
```
