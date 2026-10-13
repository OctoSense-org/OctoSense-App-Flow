# Scenario files

One JSON file per behavior, kept in `<app>/tests/` beside `bundle/`. The runner
reads every `*.json` in the directory, in name order. Name them by contract
row: `01-first-screen.json`, `02-add-note.json`, `03-read-fails.json`. Files
whose names start with `_` are shared parts, not scenarios.

```json
{
  "name": "a message that arrived before sending is shown, and sending waits for a second confirmation",
  "use": "_room.json",
  "sizes": ["412x892", "954x448"],
  "host": {
    "matrix.read_messages": [
      {"data": {"messages": [{"sender": "ann", "sender_id": "@ann:example.org", "event_id": "$1", "body": "noon works", "ts": 1, "msgtype": "m.text"}]}},
      {"data": {"messages": []}, "delay": 1.5},
      {"error": "Mini-app authorization expired"}
    ],
    "matrix.send_message": {"data": {}}
  },
  "steps": [
    {"run": "_load.json"},
    {"scroll_to": {"id": "draft"}},
    {"type": {"into": {"id": "draft"}, "text": "see you at noon", "clear": true}},
    {"scroll_to": "Send"},
    {"click": "Send"},
    {"wait": {"text": ["Check the room and the text"]}, "timeout": 5},
    {"scroll_to": [{"contains": "see you at noon"}, {"text": "Confirm", "after": {"contains": "Room: Trip"}}]},
    {"expect": {"calls": [{"service": "matrix.send_message", "count": 0}]}}
  ]
}
```

## Top-level fields

| Field | Meaning | Default |
| --- | --- | --- |
| `name` | Shown in results and in `FEEDBACK.md` | the file name |
| `use` | A part (`"_room.json"`) or a list of them: their `host` replies, `storage` and shared fields fill in what this scenario does not set | none |
| `sizes` (or `size`) | Window sizes, `WxH` in layout points; the scenario runs once per size from a fresh launch. An empty list is refused: leave the key out for the default | `412x892`, card-host's default |
| `viewport` | `[x, y, w, h]` that must hold what `in_view` lists | the whole window |
| `storage` | Files written into the app's jail before it starts. A string is written as the file's text; any other JSON value (an object, an array, a number) is written as its JSON. A name is a path inside the jail: no absolute path, `..`, backslash or glob character | none |
| `host` | Replies for `host.request`, by service name; see below | every call answers `no service answers "<family>" on this device`, as card-host does |
| `host_profile` | What a request for a service the manifest does not declare gets: `octosense` answers it, as the current OctoSense hosts do (capability names are disclosures there), and the run lists it as undisclosed; `rinx` refuses it with Rinx's `Mini app was not granted <service>` | `octosense` |
| `fake_host` | `false` runs the bundle as it is, with card-host's real (empty) services | `true` |
| `startup_timeout` | Seconds to wait for the first widgets, at most 600 | 60 |
| `allow_runtime_errors` | `true` stops a runtime error in the log from failing the scenario | `false` |
| `description`, `note` | Free text for people; the runner ignores it | none |

Every key in a scenario, a step, a check and a selector is checked when the
scenarios load. An unknown key (`texts` for `text`, `servce` for `service`) or a
value of the wrong kind (`"text": "Kept."` instead of a list, `"false"` in quotes
where `false` is meant, `true` where a count is meant, a size that is not
`WxH`) stops the run with exit status 2 before any app starts: a check the
runner skipped, or a switch it read the wrong way, would otherwise pass
without testing anything. The same holds for what JSON allows but nothing
after it can use: `NaN` or `Infinity`, a lone surrogate escape such as
`\ud800`, nesting more than 64 deep, an empty text in a check or a selector
(every widget contains it). Every time (`sleep`, `timeout`,
`startup_timeout`, `delay`) is seconds from 0 to 600, since a larger number is
almost always milliseconds; a file name must fit the filesystem (255 bytes a
part) and hold no control character, and `<file name>@<size>`, the run's evidence
directory, must fit too. A bundle that contains a symbolic link is
refused too: the runner never writes through a link.

Size the app the way its hosts do. A shell that gives the app part of its
window gives it a smaller rectangle than the window: measure that rectangle
from a screenshot of the shell and test that size.

## Shared parts

A part is a JSON file whose name starts with `_`. A scenario takes its fixtures
with `"use"`, and its steps with a `{"run": "_part.json"}` step, which the
runner replaces by the part's `steps`. Keep one part for the host replies of
the normal path (`_room.json`) and one for each sequence many scenarios repeat
(`_load.json`, `_confirm.json`). A scenario then states only what differs:
the one reply that fails, the steps after it, the checks. A part may hold both
fixtures and steps; it cannot `use` another part, and its keys are checked like
a scenario's. A part's name is a path inside the directory of the file that
names it, with the `storage` name rules; a part that resolves outside it,
through `..`, an absolute path or a link, is refused.

## Host replies

A service maps to one reply, used for every call, or to a list, used in call
order with the last one repeating. `"*"` answers any service not listed.

| Reply | The app's callback gets |
| --- | --- |
| `{"data": …}` | `{is_ok: true, data: …, error: ""}` |
| `{"error": "text"}` | `{is_ok: false, data: nil, error: "text"}` |
| `{"never": true}` | No callback: test the app's own timeout or stop button |
| `"delay": seconds` | Wait before the callback (default 0.05, at most 600); use it to test a second click while a request is out |

A reply has exactly one of `data`, `error` and `never`, and may add `delay` and
a `"note"` for people. `error` is the text the app gets; `never` is `true`.

A host answers each request once ([SCRIPT-API](../../../docs/SCRIPT-API.md#host-services-hostrequest)),
so a reply is one callback.

A service the manifest does not declare is treated as `host_profile` says. On
current OctoSense hosts a capability name is a disclosure, not a gate (see
[CAPABILITIES](../../../docs/CAPABILITIES.md#current-source-policy-and-release-boundary)),
so the fixture answers and the run prints `called without declaring: …`. Rinx
still grants a mini-app only the services it was granted, so a Rinx mini-app's
scenarios set `"host_profile": "rinx"` (in their shared part), and an undeclared
call gets `Mini app was not granted <service>`, whatever the fixture says.

Copy reply shapes and error texts from the host's source or documentation, and
name the source in the contract. A fixture the real host could never send
tests nothing. Write the failure texts the host really produces, such as
`Mini-app authorization expired` or `no service answers "matrix" on this device`.

The fake `host` keeps `has` from the real one; `capabilities` returns the
manifest's list as written. The test copy differs from the bundle only in
`main.splash` (and loses a signature its new bytes would not match): the
runner adds no capability and writes nothing into the app's jail beyond the
scenario's `storage`.

Every call is printed to card-host's log as one line, with whether it was
declared; the `calls` check reads those lines. Each line carries a code that is
new for every run, so the app cannot print a line the runner would take for a
call, and the fake host prints a ready line before the app's first line runs.
A missing ready line, a call line that does not parse, a gap in the call
numbers or a record cut off at the end of the log is broken evidence (exit
status 2), never "no calls": a `"count": 0` or an `excludes` check cannot pass
on evidence the runner could not read. While the app runs, a record still being
written makes a check wait for it.

## Steps

| Step | Does |
| --- | --- |
| `{"click": SELECTOR}` | Clicks the centre of the matching widget's visible part. Fails when none is on screen or it lies outside the viewport |
| `{"type": {"into": SELECTOR, "text": "…", "clear": true}}` | Clicks the field, optionally deletes its current text, types |
| `{"key": "ReturnKey"}` | Presses and releases a key (`Escape`, `Tab`, `Backspace`, …) |
| `{"scroll_to": SELECTOR}` | Scrolls until the widget is wholly inside the viewport, at any size; a list scrolls to each in turn. Fails when it never appears or does not fit. `"on": SELECTOR` scrolls over that widget instead of the viewport's centre |
| `{"scroll": {"on": SELECTOR, "dy": 300}}` | Scrolls over a widget by a fixed amount; prefer `scroll_to` |
| `{"expect": CHECKS, "timeout": 2}` | The checks must hold within the timeout |
| `{"wait": CHECKS, "timeout": 10}` | The same, for slower changes |
| `{"sleep": 0.5}` | Waits; prefer `wait` |
| `{"run": "_part.json"}` | The part's steps, in place |

Any step but `run` may add `"allow_runtime_errors": true` (the log is checked
after every step), and any step a `"note"` that says why it is there.
`timeout` and `sleep` are seconds, at most 600; `scroll_to` tries at most
`"max"` scrolls (default 25, at most 1000).

A `SELECTOR` is a string, matched against a widget's whole text, or an object:

| Key | Matches |
| --- | --- |
| `id` | The widget's `name :=` id |
| `text` | Its whole text, trimmed |
| `contains` | Part of its text or of an input's value |
| `type` | Its widget type, such as `TextInput` |
| `after` | Only widgets listed after the one this selector picks (its own `nth` counts): the button in the same card as a text, in a list whose rows have no ids. At most 8 deep |
| `nth` | Which match, from 0, among those on screen now |

## Checks

| Check | Holds when |
| --- | --- |
| `"text": ["…"]` | Each text appears within one widget on screen, in its text or input value; a text is never matched across two widgets |
| `"absent": ["…" or SELECTOR]` | No widget on screen shows the text, or matches the selector (`{"type": "Button", "text": "Send"}` when the same words may appear in a sentence) |
| `"in_view": [SELECTOR]` | The widget is wholly inside the viewport and no scroll view cuts it off (see below) |
| `"enabled"` / `"disabled": [SELECTOR]` | The widget exists and is (not) enabled |
| `"count": [{"of": SELECTOR, "n": 3}]` | Exactly n widgets on screen match |
| `"calls": [{"service": "…", "count": 1, "contains": "…", "excludes": "…"}]` | The app made that many calls to the service; `contains` filters by the JSON of the arguments; without `count`, at least one, with or without `excludes`; `excludes` fails if any of those calls sends the text (a name that must not reach a model, say). To require that no call was made, write `"count": 0` |
| `"files": [{"name": "…", "contains": ["…"]}]` | The file at exactly that path in the jail exists and contains each text; `"missing": true` requires its absence. The name follows the `storage` rules; a file of the same name elsewhere (a backup) or a link does not count |

## What the runner sees

The runner reads `/snap`, which lists the widgets on screen, the way a person
sees the app:

- A widget inside a scroll view is listed only while it is scrolled into view,
  and a half-hidden one is reported by its visible part, so its cut edge lies
  on the scroll view's edge. A whole widget can also sit flush against that
  edge. When a widget touches a container's edge, `in_view` and `scroll_to`
  settle it by looking: they scroll that container a little toward the edge
  and snap again. If the widget grows, part of it was hidden; if it only moves,
  or nothing moves because the content ends there, it was whole. The probe is
  scrolled back afterwards.
- `text`, `absent` and `count` judge what is on screen now. Scroll to the part
  of the app first: an `absent` over an area that is off screen passes without
  testing anything.
- `nth` counts what is on screen, so it shifts when the view scrolls; use
  `after` or an `id`.
- A `TextInput`'s text is its value, or its placeholder while it is empty.

A widget can be drawn yet not readable this way (text clipped inside its own
box, colour, overlap); that is for the visual review.

A step also fails when the log shows the script failing: an error, a panic, a
parse error, or a stop on its instruction budget (older runtimes stop a script
there; current ones only count), or when card-host has exited.

After every run the runner copies the app's jail to `<out>/<scenario>@<size>/jail/`:
evidence of what the app wrote, and the seed for a restart scenario's `storage`.

`<out>/summary.json` belongs to one invocation. It is rewritten when a run
starts (`"status": "running"`) and after every scenario, and always ends as
`passed`, `failed`, `environment_error` (no display, a host that exited or would not
close, unreadable evidence; such a run writes `ENVIRONMENT.md`, not `FEEDBACK.md`) or `aborted` (a scenario file or the card-host
could not be used, or the run was interrupted), with a `finished` time. It carries a `run_id`, the runner version, digests of the
bundle and of the card-host binary, and each result carries the digest of the
scenario as it ran. A summary left by an earlier run is never mistaken for this
one.
