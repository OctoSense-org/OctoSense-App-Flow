# ADR 0002: The analysis posture: answer the host, re-run every top-level `fn`, suppress exactly one shape

- **Date:** 2026-10-13
- **Status:** Accepted (2026-10-13). Not yet implemented: answering host requests is issue #5 and the `fn` re-run is issue #6, both in [OctoSense-org/makepad](https://github.com/OctoSense-org/makepad) (`widgets/src/splashcheck.rs`, `widgets/src/splash.rs`).
- **Scope:** How deep the validator looks during a check, and which of the findings that depth produces it is allowed to dismiss. It covers the two blind spots the checker documents about itself, the shape of the answer stub, the single suppression rule, and the code that makes stub findings grep-able. It does not cover the discovery chain or the download (ADR 0003) or the completion data source (ADR 0001). This record lives in App Flow, where the spec and every ticket that cites it live; the code it governs lands in the makepad fork.
- **Relates to:** [ADR 0001](0001-vm-query-api-two-functions.md), [ADR 0003](0003-download-first-server-distribution.md); App Flow #1 (the spec), #4 (golden corpus), #5, #6.

## Context

The checker evaluates an app's body in a throwaway isolate — the same VM, the same widget registry, the same host bridge a real host installs (`widgets/src/splash.rs:580`, `validate_splash_body_records`) — and it is honest about two holes in that, in its own module docs (`widgets/src/splashcheck.rs:22-33`):

> * Only top-level code is evaluated. A `fn` nothing calls at the top level is compiled but never run, so a fault inside it is not reported …
> * `host.request` calls queue and are never answered, so a callback's body does not run and a fault inside one is not reported.

Both are measured below, and both are the difference between an error a person sees in their editor and an error their users see on a device. The fix for each is the same kind of thing: run more of the app during the check.

Running more of an app during a check is also how a checker starts lying. A `fn` re-run has no arguments, so every parameter is `nil`; a stub answer to a host request is not the answer the real host would give. The findings that depth invents are the cost of the depth, so this ADR fixes the posture **and** the one rule that pays for it, together. A posture without its suppression rule is a tool that drowns people in false positives until they turn it off.

### What shaped this decision (measured)

Every run below was made on Windows, 2026-10-13, with the fork's prebuilt release binary (`target/release/splashcheck.exe`) over a one-file app. The body is evaluated inside the harness prefix (`widgets/src/splash.rs:158-162`), so the reported line is the app's own.

**The `fn` blind spot.** `fn broken(){ let x = nope }`, with a `View{…}` root:

```
$ splashcheck .
  ok   .\main.splash — 101 bytes
        note: no manifest.json above this file: capability checks skipped
splashcheck: 1 ok, 0 warn, 0 error
```

**The callback blind spot.** `fn load(){ host.request("news.list", {}, fn(r){ if r.is_ok { let bad = missing_name } }) }` called at the top level:

```
$ splashcheck .
  ok   .\main.splash — 203 bytes
        note: no manifest.json above this file: capability checks skipped
splashcheck: 1 ok, 0 warn, 0 error
```

The request is queued and nothing drains it: `take_splash_host_requests` (`widgets/src/splash_host.rs:135`) is the host's call, and a validation run has no host.

**A no-argument call binds parameters to `nil`, and `nil` only traps on a field.** One function, three uses of its parameter, called with no arguments:

```splash
fn f(a){
    let b = a.field
    let c = a * 2
    let d = "x" + a
}
f()
```

```
$ splashcheck .
  ERR  .\main.splash — 142 bytes
        2:15 no getter for field field on type nil
splashcheck: 0 ok, 0 warn, 1 error
```

`a * 2` and `"x" + a` are silent, because the VM coerces rather than traps: `cast_to_f64` maps `nil` to `0.0` (`platform/script/src/heap.rs:703-705`) and `cast_to_string` appends nothing for `nil` (`platform/script/src/string_heap.rs:649-651`). A field access is the one operation with no coercion, because it falls through to the type's default getter, which traps (`platform/script/src/native.rs:326-334`). The same three lines at the top level, with `let a = nil`, give the same result: `nil * 2` and `"hi " + nil` are clean, `n.field` is `no getter for field field on type nil`.

So the false-positive surface of a no-argument re-run is **one message shape**, and it is a shape the person can read: it names the field and says the value is `nil`.

## Decision

### 1. The posture: answer the host, then re-run every top-level `fn`

During a check, in the same isolate that evaluates the body:

1. **Host requests are answered deterministically.** After the body evaluates, the requests it queued are drained and each is answered once, with a success. The answer's shape is the one the bridge already builds — `{is_ok, data, error}` (`widgets/src/splash_host.rs:186-193`) — and the stub answers `is_ok` true, so the `if r.is_ok` branch runs. The success path is the one worth checking: it is where an app's real work is, and a checker that only ever exercised the failure branch would miss most of the code.
2. **Every top-level `fn` is re-run once with no arguments**, after the body and after the answers. The result is discarded; only the errors are collected.

Only top-level `fn`. A `fn` nested inside another `fn`, or inside a proto, exists only when its enclosing code runs, so reaching it means evaluating the app rather than checking it — that is a different tool, and it is out of scope for this spec. The checker already says which checks it skipped (`report.notes`), and "nested `fn` not evaluated" joins that list rather than being left as silence.

### 2. One suppression rule, and it is the one measured above

`no getter for field <name> on type nil`, produced while running a stub, is **downgraded to a note** — a line in the output channel, not a squiggle in the file. Nothing else is suppressed. Not `nil` arithmetic, which does not error; not a missing name, which is a real fault; not a type error in a callback, which is exactly what the posture exists to find.

The rule is written as narrowly as the measurement allows: the message, the `nil`, and the stub mode. A finding that matches the words but arrives from top-level code is still an error, because top-level `let n = nil` followed by `n.field` is the app's own doing.

### 3. Stub findings carry their own code

Findings that exist only because of the stub carry `splash.fnstub`, beside the existing `splash.eval`, `splash.capability`, `splash.known` and `splash.io` (`widgets/src/splashcheck.rs:114-115`). That is what makes them greppable, baseline-able through the existing mechanism, and demotable in one move if the false-positive rate ever justifies it — a decision taken with data, rather than by deleting the posture.

### 4. The golden corpus is the regression gate

Issue #4 puts twelve real apps and the `fn` blind-spot fixture under golden files. The fixture's expectation flips from "no findings" to "findings", which is the measurable delivery of this posture; every other app's diff must be empty or explained. A posture that changes what a real app reports is a change a person must see.

## Consequences

- A fault inside any top-level `fn`, including one nothing calls, is reported at its own line. Dead code stops being a place to hide.
- A `host.request` callback's body runs during a check, so its faults are reported — and the checker now depends on the host bridge's answer shape. If that shape changes, the stub changes with it, in one place.
- The check costs more: one extra call per top-level `fn`, one answer per queued request, all inside the isolate's instruction budget (`SPLASH_EVAL_INSTRUCTION_LIMIT`, `widgets/src/splash.rs:162`). A pathological app can spend the budget in a stub re-run, which surfaces as the existing "crashed its isolate during validation" record rather than as a new failure mode.
- The one suppression rule will be wrong sometimes. A real `nil` field access inside a re-run `fn` is a real fault and will be a note. That is the trade, taken deliberately: rather miss a fault than invent a rule, because an invented rule suppresses shapes nobody has measured.

## Alternatives considered

- **Answer host requests with a failure instead of a success.** Rejected: it exercises the `else` branch and leaves the success path — the one carrying the app's work — unchecked. Double-answering (once ok, once failed) is out of scope for this spec; it is worth revisiting once there is real data on what the success pass finds.
- **Suppress every finding whose message mentions `nil`.** Rejected on the measurement: it would also suppress a real `nil` dereference the app performs itself, and it is the kind of broad rule that grows.
- **Give stub `fn`s synthetic arguments instead of `nil`.** Rejected: inventing a value per parameter type is a generator, and a generator is wrong in ways nobody can predict. `nil` is what the VM already does, it is visible in the message, and its false-positive surface is one shape.
- **Re-run `fn`s in a fresh isolate.** Rejected: the findings would come from a heap that never saw the app's own top-level state, and a `fn` that reads a `mod.state` its caller set would report faults that do not exist.

## Measurements

Windows, 2026-10-13, `C:\Users\Administrator\Desktop\makepad\target\release\splashcheck.exe`, over one-file apps in a temp directory. Quoted in full under [What shaped this decision](#what-shaped-this-decision-measured) above: the `fn` blind spot (`ok`, 0 findings), the callback blind spot (`ok`, 0 findings), the no-argument call (`a * 2` and `"x" + a` silent, `a.field` reporting `no getter for field field on type nil`), and the same three operations at the top level with `let a = nil`.

Source evidence for the coercion, cited so a reader can check it without running anything: `platform/script/src/heap.rs:703-705` (`nil` → `0.0`), `platform/script/src/string_heap.rs:649-651` (`nil` → no text), `platform/script/src/native.rs:326-334` (the default getter's trap).
