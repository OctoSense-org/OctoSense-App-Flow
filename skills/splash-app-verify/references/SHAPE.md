# The narrow shape of a script app

Write every script app in this shape. Each rule closes off one class of bug
that otherwise turns up late: on a phone, in review, or after a person has lost
their text. The worked example is [examples/titled-notes](../examples/titled-notes/bundle/main.splash);
read it once, it is short.

```text
1. state        top-level lets only
2. decisions    plain functions: data in, data out, no ui
3. storage      one versioned file, validated on read
4. actions      change state, then sync once
5. host calls   one function per service; every reply handled; stale replies ignored
6. sync         the only functions that write to the screen
   root view    named widgets; lists in the documented empty-state form
```

## Rules and what each one prevents

| Rule | Prevents | Source |
| --- | --- | --- |
| Keep state in top-level `let`s. Name the request token, the busy flag and the status text there, not in closures. | A handler that reads a value an older closure captured; a busy flag that never resets | [SCRIPT-API: shape of a program](../../../docs/SCRIPT-API.md#shape-of-a-program) |
| Put decisions in plain functions that take and return data and never touch `ui`. | Logic that can only be reached by clicking; a rule changed in one handler and not another | Scenarios can then check one rule through one action |
| Write to the screen only from a few `sync_*` functions, called after state changes. | Two handlers updating the same label differently; a list that is not re-rendered after a change | [MODEL-VALIDATION: partial start-up counted as success](../../../docs/MODEL-VALIDATION.md#recover-from-observed-model-weaknesses) |
| Keep one function per host service. It sets busy, sends, and handles each reply in the contract: `is_ok` false with each documented error, a reply after the request was replaced, no reply at all (a timer that ends the wait). | The spinner that never stops; a late reply overwriting newer work; an English host error shown to a Chinese user; "Send" that never sends | [SCRIPT-API: host services](../../../docs/SCRIPT-API.md#host-services-hostrequest), [HOST-SERVICES](../../../docs/HOST-SERVICES.md) |
| Map each host error to a sentence the person can act on, and keep the app usable without the service. | A dead end when the host has no model, no account or no permission | [AGENTS: every AI feature is optional](../../../AGENTS.md#rules-for-every-app) |
| Translate host errors in one function that takes the service as well as the text. The failing service is the sentence's subject; an error it does not know keeps a prefix that names that service. Include rate limits (`429`, `rate limit`, `too many requests`). | A model failure reported as "could not read the chat"; a raw English error or rate-limit message | OnCue 0.5.2, tested with this skill on 2026-10-10: one shared mapper with a chat-read fallback mislabelled model and send errors |
| Keep that function pure. A side effect of an error (dropping a consent, ending a session) happens in the caller, followed by a sync. | State that changed without the screen showing it: "Allowed" still displayed after the grant was dropped | OnCue 0.5.2, the same run |
| Derive every place that shows a state from the same variable, and clear them together. | A status line still saying "press Confirm" after the confirmation was cancelled | OnCue 0.5.2, the same run |
| Store one versioned file. Validate it on read; if it fails, say so, change nothing, and write nothing over it until the person decides. Write only after the in-memory state is valid. | A corrupt or older file wiping the person's data; a half-written state | — |
| Give every widget a scenario or function touches a `name :=` id, and keep button texts stable. | Tests that break on a reworded label; `ui.x` not found after a wrapper was added | [SCRIPT-API: `ui.<id>`](../../../docs/SCRIPT-API.md#uiid-reading-and-changing-widgets) |
| Draw lists as `if list.len() == 0 { Empty }` then `for …`, two statements. | An empty state that never shows, stale rows that stay | [SCRIPT-API: gotchas](../../../docs/SCRIPT-API.md#gotchas) |
| Lay out with `Fill`/`Fit`, rows that wrap (`flow: Right{wrap: true}`) and one scroll container. Write a height budget per region for the smallest size in the brief. No fixed heights around text. | Buttons pushed off the first screen; text clipped at a narrow width; a layout that only works at the size it was written at | Scenarios with `in_view` at each size |
| Use only documented APIs; `//` comments; `#x` colors; no reserved word as a name; no top-level `tick`. | Invented methods (`contains`, `map`, `range`), init stopped halfway by a `#` line, a parse error | [SCRIPT-API: data and strings, gotchas](../../../docs/SCRIPT-API.md#data-and-strings) |
| Declare every capability the app uses, and only those; no secrets. | An undisclosed call (OctoSense treats the list as a disclosure) or a refused one (Rinx grants only what it lists); a store listing that asks for more than the app uses | [CAPABILITIES](../../../docs/CAPABILITIES.md) |

## Order of work

Build in the order of the contract, and keep each step green before the next:

1. the root view and the first screen, with its data loaded (`01-first-screen`);
2. the main action and its saved result;
3. that action's failures, one scenario each;
4. restart and the stored state;
5. the next action.

A model that writes the whole app in one pass and then debugs it spends its
turns on failures that interact. One path at a time keeps each failure small
and its `FEEDBACK.md` precise.
