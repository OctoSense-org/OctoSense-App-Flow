# L0 cards and host services

A script app calls a service itself — `host.request("mail.accounts", {}, fn(r){ … })`
([HOST-SERVICES](HOST-SERVICES.md#calling-a-service-from-an-app)). An **L0 card**
(`page.card`) has no statements, so it asks the same way in a different form: a
sibling `bindings.json` declares the calls, and the host makes them when the card
opens or when an event the card names arrives.

## Who runs the bindings

`bindings.json` is Rinx's L0 path. Rinx's bundle guide documents the **shape** of
the file — the `{service, args, target}` call, `events`, the
`{"is_ok": …, "data" | "error": …}` written to the target, the `$state` /
`$data` / `$value` argument references, and "declare each service in the
manifest's `capabilities`" — in
[`examples/miniapps/README.md`](https://github.com/hagency-org/Rinx/blob/main/examples/miniapps/README.md).
That guide covers `events`; `on_open` lives in Rinx's source only
(`src/miniapps/package.rs`, where `Bindings` defaults it to an empty list, so an
`events`-only bundle is a fully valid shape).

An OctoSense shell runs an app through the App Hub `CardModule` and its own
registered Rust services, and `card-host` registers none: a bundle carrying
`bindings.json` is admitted and drawn there as usual, and the calls simply do
not happen, so every target keeps the value `page.data.json` seeded and the card
draws its seeds. Everything below is about the host that **does** run them, and
it is why a card that uses a service is worth running in Rinx before you call it
done.

## Rule 0: a name the card reads must be declared

This one is not about the bindings at all, and it is the fault a card whose only
wiring is a `bindings.json` is most likely to hit. Every root a card reads must
be a **declaration** — a `source`, a `state`, a `copy`, a `for` binder or a
component param (`Scope::roots` in `crates/octoscript-ui-l0/src/lib.rs`). Any
other root is refused by `check_ui_l0`:

```
"read" is not a declared name
```

and App Hub admission refuses the bundle on that report (`crates/app-hub/src/
admission.rs`, `!report.valid` → `Err`), **before any host runs**, on either
lowering path.

A binding target does **not** declare a name. `page.data.json` writing
`data["read"]` and `bindings.json` naming `"target": "read"` are both invisible
to the checker: the card must say what it is reading.

```
state read { shape: record }     # the declaration
state reply { shape: text, initial: "" }
```

Rinx's own `matrix-octos` does exactly this — it declares `profile` and `answer`
for the two targets its `events` write.

## The three rules that fail closed

All three were found by running real bundles against the host. Rules 1 and 2
fail the **whole card**, but only on the native-Kit path; on the semantic path
the same fault draws an em dash and the card keeps drawing. Rule 3 fails the
**whole app**. None of them is visible to `hub check` — not because they are
missing from the manifest (rule 3's undeclared service is exactly a
manifest-vs-`bindings.json` mismatch), but because **`hub check` never reads
`bindings.json`**: it checks the manifest and the card, and the wiring lives in a
third file it does not open.

### Which lowering path a card takes

Rinx branches on whether the realized tree contains a Kit component
(`src/miniapps/presentation.rs`, `kit_pack::contains` — any node of kind `Kit`,
at any depth):

* **Kit path** — the tree contains a `Kit(component: …)` node, and the **root**
  itself is one. `kit_pack::lower` lowers it, and `tree()`'s visit requires the
  root to be a Kit ("native pack requires a Kit component"). A missing value
  there **errors**, and the card fails — this is the path rules 1 and 2 are
  written for. Argument order is free: `kit_pack` reads `component`/`instance`
  by name, so `Kit(instance: "t", component: "title")` is the same node as
  `Kit(component: "title", instance: "t")`.
* **Semantic path** — no Kit node anywhere. Semantic components (`TextBody`,
  `Chip`, `Field`, …) lower through `octoscript_makepad::l0::prepare_with_state
  → kit::lower`. There a missing argument renders as an em dash `—` and the card
  keeps drawing — the source comments the `Missing` declaration as "a silently
  empty field is how a card renders an em dash and looks fine".

A card reaches the Kit path one hop in: `view root Page(instance: "page")` where
`component Page(instance: text) { view Kit(component: "page", instance: instance) { slot } }`
realizes to a Kit root, and so it is on the Kit path. A simple card — Rinx's own
`matrix-octos`, whose root is `Surface` — is on the semantic path, which is why
it ships unguarded `profile.data.*` reads and still works. On that path rules 1
and 2 are a **hygiene** matter: seed the names and guard the reads, or the field
quietly shows `—`.

### 1. A declared name the card reads must be seeded before the first frame

A card is lowered before any call answers. On the native-Kit path, a path the
card evaluates that lands on a name with **no value** fails the entire card:

```
unresolved or unsupported kit property
```

A name is resolvable on the first frame when `page.data.json` carries it, when
its `state` declares an `initial:`, or when a `source` answers it — realization
looks in the store, then the injected data, then the declaration's initial
(`realize_with_state`). So `state reply { shape: record }` with
`text: reply.data.text` is not enough by itself unless something else seeds
`reply`: with no `initial:` and nothing in `page.data.json`, the first frame
finds nothing. Add the seed and the host's write replaces it when the call
answers.

The rule is about the names the card **reads**, not about every target. A target
the card never reads — a session handle opened only to establish the assistant's
context, say — needs no seed, because an unread name is never resolved. Both
directions verify the same way: seed nothing and leave the target unread, and the
card lowers; read it once, and the card fails until it is seeded.

### 2. A failed call needs a guard on every read

When a call fails, the host writes `{"is_ok": false, "error": "…"}` to the
target — there is **no `data`**. A line that reads `X.data.text` then has nothing
to resolve: on the native-Kit path the whole card fails to lower rather than the
one line, and on the semantic path it draws `—`. The form that survives either
way is a bare boolean guard around the read:

```
when read.is_ok { TextBody(text: read.data.text) }
```

(`when read.$state == .ready { … }` is the source-lifecycle form.) The line the
card always draws must sit outside the guard, so the card still reads as a card
when the service answers nothing.

The guard is on a **read**, not on a name for the whole card: a card with one
guarded read and a second unguarded `read.data.other` still fails that second
line on the Kit path. And the class of failure matters. By this page's own rule
3, a **dispatch-time** refusal — authorization refused, the assistant
unavailable, no adapter for the service — errs before anything is queued and
never writes `is_ok:false`; only a call that **dispatches and then fails** (a
network error, a turn that errors) writes it. So only that second class is rule
2's regime.

### 3. `on_open` failing keeps the app from opening

Every `service` in `bindings.json` must also be in the manifest's
`capabilities`, or the call is refused **before anything is queued** — and an
undeclared service does not merely skip the call, it aborts the whole import
(`load_inner`: "… is not declared in capabilities"), so the app never opens. A
failure in any `on_open` call keeps the app **not opening** the same way, and the
reason is **shown** — every `run()` caller lands it in the panel's notice line
(`src/miniapps/ui.rs`, the `self.notice(cx, &e)` on the run path), **except the
`open_board` path, which resets silently instead** (`action_room.rs:92-95` drops
the reason). Since
`on_open` runs on the way in, a binding that can fail — anything reaching an
assistant, a model or the network — belongs in `events`, or behind a line the
card can still draw without it.

Two failure classes are worth keeping apart:

* A **dispatch-time** refusal — the assistant is unavailable, authorization is
  refused, there is no adapter for the service — keeps the app from opening, and
  the reason is **shown** in the panel's notice line.
* A call that **dispatches and fails later** writes `is_ok: false` to its target
  and leaves the app open, drawing its seed. That is rule 2's regime, not a
  failure to open.

Also keep `on_open` targets distinct: two calls that share a target make the
dispatch refuse the second as "already running" (`src/miniapps/ui.rs`,
`dispatch`), which fails `run()` and keeps the app from opening.

## A worked example

Two cards, one per path. Both read the on-device assistant's answer; the first
is the semantic form, the second the native-Kit form.

### Semantic root

`view root Surface { … }` realizes with no Kit node, so this card lowers through
the semantic path: an unseeded name draws `—`, it does not fail the card.

```json
// bindings.json
{
  "on_open": [
    { "service": "octos.session.open", "target": "session" },
    { "service": "octos.turn.start", "target": "read",
      "args": { "text": "…what two things does this message still leave out?" } }
  ]
}
```

```json
// page.data.json — `read` is seeded; `session` is a target the card never
// reads, so it needs no seed. The seed is what the card draws if the turn never
// answers. (The theme comes from the card's own `theme` line: nothing reads
// `$kit.theme`.)
{ "read": { "is_ok": false, "error": "assistant has not answered yet" } }
```

```
# page.card — every root is declared, and the read is guarded
theme light
state session { shape: record }
state read { shape: record }

view root Surface {
  TextTitle(text: "What this message still leaves out")
  when read.is_ok { TextBody(text: read.data.text) }
}
```

`octos.session.open` and `octos.turn.start` are in the manifest's
`capabilities`; without them the calls are refused, and with the turn in
`on_open` a host that cannot answer leaves the app unopened (rule 3).

### Native-Kit root

The same wiring with a Kit root — `tree()` requires the **root** to be a `Kit`.
Unlike the semantic card, an unseeded read here fails the whole card.

```
# page.card
theme light
state read { shape: record }

view root Kit(component: "panel", instance: "panel") {
  Kit(component: "title", instance: "title", text: "What's still missing")
  when read.is_ok { Kit(component: "hint", instance: "hint", text: read.data.text) }
}
```

The `kit/native/light/kit.json` pack owns the components and tokens, and
`page.data.json` carries the `$kit.placements` the pack needs (`kit_pack::tree`
reads `$kit.placements[id]`, and `$kit.instances[id]` **only for `part:`
compounds** — `kit_pack.rs:92-103`; a plain component is placed without an
instance entry. Every `prop` the
component declares must be passed or the card fails with "… requires …").
`examples/miniapps/theme-reference` is this shape: the same `panel`/`title`/
`hint` components, a light kit pack, and the placements in its own `data.json`.

## Checking a bundle before a host runs it

[`tools/l0-bindings-lint.py`](../tools/l0-bindings-lint.py) implements rule 0 and
the three rules over the files — no L0 parser, no dependencies, and it writes
nothing:

```sh
python3 tools/l0-bindings-lint.py ./bundle
```

```
  ok   events[open]: service 'octos.turn.start' is granted
  ok   events[note]: service 'octos.session.open' is granted
  ok   page.card: 'read' is declared, seeded, guarded
  warn events[note]: target 'session' is neither referenced by page.card nor seeded — harmless today, since an unread name is never resolved, but seed it so a later reference cannot fail the whole card.
  ERR  page.card reads 'reply' but the card never declares it — a name a card reads must be a `source`, `state` or `copy` ('reply' is not a declared name), so `check_ui_l0` refuses and App Hub admission rejects the bundle. A binding target does not declare one: add `state reply { shape: record }`.
l0-bindings-lint: 3 ok, 1 warn, 1 error
```

It branches rules 1 and 2 on the card's lowering path — the same findings are an
**error** on the native-Kit path and a **warning** on the semantic path, while
rule 0 (an undeclared name) is an **error** either way — and it also catches a
target the card never declares, a target with a trailing newline, an unknown key
inside a call (Rinx's `Call` denies unknown fields), a `$data`/`$state`
reference that resolves to nothing, a duplicate `on_open` target, and a
malformed `bindings.json` (reported as an `ERR` line, not a traceback).

Exit 0 when the card will lower, 1 when it will not, 2 for a usage error or a
missing bundle file. It is not a gate and does not replace `hub check`: it
catches what `hub check` admits, which is exactly the class of fault this page
is about.

### What the scan deliberately does not read

The scan is lexical, so four things are out of its reach on purpose — each one
is a name or a token that only a parse can place, and reading any of them as
syntax produced findings that were wrong:

* **The text of a string literal.** A string is one token to the L0 lexer, so
  `TextBody(text: "wrap it in Kit(component: …)")` is not a Kit card and
  `text: "…profile.data.text"` is not a read of `profile`. String *content* is
  blanked before any pattern runs (quotes kept, offsets preserved).
* **The service namespace of a `source` query.** `source lead sys.news(count: 1)`
  names a service, not a card read: the query resolves it, the frame never does,
  so "add `state sys { … }`" is advice that cannot be followed.
* **A `for` binder or a component parameter as "unresolvable".** Both are scope
  roots while the loop realizes (`lib.rs`), so a read of either resolves on the
  first frame even with no seed. The two-binder form (`for s, i in feed key
  s.id`) is a binder pair, not two undeclared names.
* **A `view` inside a component body as the card's root.** The root is the
  **top-level** `view`; `component Side { view Col { … } }` above `view root
  Page` does not make `Col` the card's root.

A bare (undotted) name is not treated as a read — rule 0 stays a dotted-path
check — but it *is* counted as referenced, so the "target is neither referenced
nor seeded" line is not printed about a name the card does pass somewhere.
