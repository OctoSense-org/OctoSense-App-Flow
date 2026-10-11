---
name: splash-app-verify
description: Build or change an OctoSense Splash script app (main.splash) so it is right by construction and verified like backend code - write observable scenarios before the code, keep the app in a narrow testable shape, and run the scenarios in card-host with faked host services after every edit. Use when creating or changing a script app, when a model keeps breaking its UI, or before hand-off.
---

# Splash app verify

A UI app is hard for a model to check: its logic lives in the screen, it calls
host services that a development machine does not have, and seeing it means
starting a whole window. So models write blind and a person finds the bugs
later, when they cost the most. This skill moves the work to the front:

- **Prevent first.** Fix what "done" looks like, and the shape the code may
  take, before writing it. Most UI bugs come from an open-ended process: a
  layout nobody budgeted, a host reply nobody planned for, logic spread through
  click handlers. A narrow process leaves less room for them.
- **Test like a backend.** Each behavior is a scenario file. A runner starts the
  real app in `card-host`, answers its `host.request` calls from the scenario,
  clicks and types through the remote bridge, and checks what the screen, the
  storage jail and the log show. Run it after every edit.
- **Repair one thing at a time.** A failed scenario writes `FEEDBACK.md`: the
  steps, what was expected, what the screen had, the evidence and the scope of
  the fix, in the shape [MODEL-VALIDATION](../../docs/MODEL-VALIDATION.md)
  asks for. Hand it to the author, a person or a model, unchanged.

This skill adds to the chosen flow ([script-app](../../flows/script-app/FLOW.md));
it does not replace the gate, the visual review or publishing.

## 0. Set up once

```sh
skills/splash-app-verify/scripts/setup.sh          # Linux: Xvfb + Mesa; builds card-host if missing
python3 skills/splash-app-verify/scripts/uitest.py doctor
```

`doctor` must print `[ok]` for `card-host` and the display. `setup.sh` records
the `card-host` it finds or builds, so later shells need no variable;
`--card-host` and `OCTO_CARD_HOST` still win. Build `card-host` from current
App Hub `main`: it carries the Splash runtime the current hosts run. On a
machine with no display the runner starts its own Xvfb; nothing appears on
anyone's screen.

## 1. Write the contract before any code

Write `BRIEF.md` (outside `bundle/`) with these tables. Every later step checks
against them, so a gap here becomes a gap in the app.

| Table | One row per | Columns |
| --- | --- | --- |
| Screens and states | screen × state: first open with data, empty, loading, ready, each failure | what the person sees: the exact texts that must and must not show |
| Actions | button, input or gesture | widget id (`name :=`), visible text, what changes, what is saved |
| Host services | `host.request` service | capability, the documented reply shape, every failure the app must show: not granted, no service, an error, no answer, an authorization that ended. Name the host: on OctoSense a capability is a disclosure; Rinx refuses a mini-app what it was not granted |
| Storage | file in the jail | format, version, what happens when it is missing or corrupt |
| Sizes | size the app is given: a phone, and the rectangle each shell gives it inside its own window | what must be on the first screen without scrolling; what may need a scroll |

Cite where each host service and API comes from ([SCRIPT-API](../../docs/SCRIPT-API.md),
[HOST-SERVICES](../../docs/HOST-SERVICES.md), the runtime source). If nothing
documents it, the app cannot use it.

Then turn the tables into scenarios, **before** `main.splash` exists or before
you change it. At least:

1. the first screen with its data loaded;
2. the main path, end to end;
3. the empty state;
4. each host-service failure from the table;
5. a restart: storage seeded, the saved state comes back;
6. the main path at the smallest and the largest size.

The format is in [references/SCENARIOS.md](references/SCENARIOS.md). Put the
normal host replies and repeated sequences (load, confirm) in shared `_parts`,
so each scenario states only what differs; a Rinx mini-app's shared part sets
`"host_profile": "rinx"`. Run them once on the old source,
or on the bare template. A new scenario must fail first; one that passes
before the feature exists tests nothing.

## 2. Keep the app in a narrow shape

Write the app in the shape [references/SHAPE.md](references/SHAPE.md) shows. Each
rule there closes off a class of bug:

- State in top-level `let`s. Decisions in plain functions that take and return
  data. The screen updated only from a few `sync_*` functions.
- One function per host service, handling every reply in the contract, and
  ignoring a reply that arrives after its request was replaced.
- A `name :=` id on every widget a scenario or a function touches.
- Lists drawn with the documented empty-state form: `if list.len() == 0 { … }`
  then `for …`, never in an `else`.
- Layout from `Fill`/`Fit`, wrapping rows and one scroll container, with a
  budget per region for the smallest size. No fixed heights around text.
- Only documented APIs; `//` comments; `#x` colors; no reserved words as names.

## 3. Build one path at a time; test after every edit

1. Pick the next red scenario in contract order: first screen, then the main
   action, then its failures, then the next action.
2. Make the smallest change that can turn it green.
3. Run all scenarios:
   ```sh
   python3 skills/splash-app-verify/scripts/uitest.py run <app>/bundle <app>/tests
   ```
4. Green: commit, take the next one. Red: read `FEEDBACK.md`, fix only what it
   names, run again. If a scenario that was green turns red, undo the last edit
   before anything else.

Keep exactly one scenario you are working on red. Do not edit a scenario to
make it pass unless the brief changed, and then say so in the commit.

## 4. Sizes, then look at it

When all scenarios pass at every size, take the screenshots the flow asks for
(`tools/octo shot`) and have a person, or a model that can read images, review
them against the brief. The runner checks text, placement inside the viewport,
enablement, counts, host calls, files and runtime errors. It does not judge
looks, and a clipped glyph inside a widget that is itself in view can pass.

## 5. Real host, last

The fixtures cover every reply in the contract, including the ones a real host
makes hard to produce: another person posting, a grant that expired, a
switched account, a rate limit. A real host is for acceptance, not discovery:
one pass of the main path and the failures you can trigger safely.

- **Prepare it before you need it.** List the accounts, rooms and permissions
  each real check needs. Set them up a day ahead and try each once with a
  request that changes nothing.
- **Diagnose before you work around.** When the host does something the
  contract does not say, shrink it to the smallest request that shows it, read
  the client and server source for that request, and write the cause down with
  file and line before changing anything. Report it under "Gaps found" with
  the reproduction. If it is the host's bug, keep the app's contract.
- **No unattended effects.** A scheduled check may probe and notify. Sending,
  creating rooms, inviting and anything else that changes the world waits for
  a person.
- **Bind evidence to source.** Record the `main.splash` SHA-256 each real run
  used. A run on an earlier source is history, not proof of the current one.

## 6. Hand off

Report, from `build/uitest/summary.json` and the flow's checks:

- which scenarios pass, at which sizes, against which `main.splash` SHA-256;
- what the fixtures stood in for and was not run for real: the host services,
  permission sheets, a phone keyboard, provider behavior;
- what ran on a real host, against which source;
- anything a person must still look at.

## What the runner does

`scripts/uitest.py run <bundle> <scenario.json | dir>`:

1. copies the bundle and prepends a fake `host` to the copy's `main.splash`, so
   `host.request` gets the scenario's replies; the code under test is otherwise
   unchanged, and the bundle under test is never edited;
2. starts `card-host` on the copy (hidden; under a private Xvfb on a headless
   Linux machine) at each size the scenario lists;
3. performs the steps through the remote routes and checks each expectation;
   a runtime error in the log fails the step;
4. stops at the first failure and writes `snap.json`, `screen.png`,
   `card-host.log`, `calls.json` and `FEEDBACK.md` under `build/uitest/`;
   every run also keeps the app's jail files there.

Exit status: 0 all passed, 1 a scenario failed, 2 the environment, the
evidence or a scenario file is broken (not the app's fault). Scenario files
are checked when they load: an unknown key, a value of the wrong kind or a
file name that leaves the jail stops the run before any app starts. The test
copy keeps the bundle's capabilities and storage as written; the fake host
reports calls through card-host's log. Under each result the runner notes what
is true of the run but not a failure, such as a service called without being
declared. `summary.json` is rewritten by every run and names its `run_id` and
`status`.

It sees what `/snap` lists, which is what is on screen; scroll to a part of
the app before checking it ([what the runner sees](references/SCENARIOS.md#what-the-runner-sees)).

Examples: [examples/notes](examples/notes) tests the App Flow template app;
[examples/titled-notes](examples/titled-notes) is a small app in the shape,
with its scenarios.
