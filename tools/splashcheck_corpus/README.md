# The splashcheck golden corpus

The Splash checker's findings over the twelve real apps, pinned as text. One
command re-runs the checker and compares:

```sh
python3 tools/splashcheck_golden.py                 # compare
python3 tools/splashcheck_golden.py --update        # re-record after an intended change
python3 tools/splashcheck_golden.py --only mail     # one app
```

Exit status: `0` every golden matches, `1` at least one differs (with a unified
diff on stdout), `2` a setup problem - no checker binary, no corpus app, no
golden file. A workspace that cannot run the corpus says so; it never passes
quietly.

## Where the apps and the checker are

Neither is in this repository, so the runner expects a workspace that holds the
sibling checkouts beside this one:

```text
<workspace>/
  OctoSense-App-Flow/    this repository
  OctoSense/             the shell and its system apps: apps/<app>/bundle
  OctoSense-AppCard/     the AppCard assistant: bundle
  makepad/ splash-probe/ where the checker is built
```

Where that workspace is, in order: `--corpus-root`, `$OCTOSENSE_WORKSPACE`, then
this repository's parent directory. The checker is `splashcheck`, built from the
OctoSense fork of Makepad - `cargo build -p makepad-widgets --bin splashcheck
--features maps` - and is found in `$SPLASHCHECK`, then `splash-probe`, `makepad`
or `Octoscript-Makepad` under the workspace root, then `$PATH`: the order and the
`os.X_OK` test `tools/octo` applies to the tools it wraps. Build it with the
features of the host it checks for; this corpus is recorded with `maps`, or the
maps app reports a `MapView` its host does have.

## Layout

| Path | What it is |
| --- | --- |
| `golden/<app>.txt` | One app's report: app id, a digest of the sources the checker read, and every finding with its line, column, code and message. |
| `fn-blindspot/` | The fn blind-spot fixture, shipped here so it is checked wherever the checker is. |

The twelve apps are the OctoSense shell's eleven system apps (`news`, `photos`,
`maps`, `camera`, `mail`, `calendar`, `ai-providers`, `youtube`, `quickdeck`,
`pdftools`, `writer`) plus the AppCard assistant. `wasmlab` also ships a bundle
but is a lab rather than a system app, so it is not in the corpus.

The digest covers the `.splash` files and the manifest and nothing else, because
those are the checker's whole input: an icon, a `tools.json` or a screenshot
cannot move a finding, and hashing them would make a screenshot update look like
a checker regression.

## What a golden does not show

Two reductions, both deliberate, both in the code with their reasons:

- **Findings are sorted**, not listed in report order, so a reordering is not a
  diff.
- **The VM's allocation counters are scrubbed** (`width(obj653)` becomes
  `width(obj)`). They are heap indices: they move when anything ahead of them in
  the registry moves, and a golden that kept them would churn on every unrelated
  refactor and bury the change a reader came to see.

## The fn blind spot

`fn-blindspot/main.splash` is one line: `fn broken(){ let x = nope }` - a fault
inside a function nothing calls at the top level. The checker evaluates
top-level code only, so its golden records no findings. That is the measurement
this corpus exists to make: when the checker starts evaluating every `fn`, this
golden gains a finding and the diff says so, rather than the change arriving as
a sentence in a changelog.

## Re-recording

`--update` writes what the checker says now, so it is also how an intended
change is accepted. [ADR 0002](../../docs/adr/0002-analysis-posture-and-one-suppression-rule.md)
§4 makes this corpus the regression gate for the analysis depth: the fixture's
expectation flips from "no findings" to "findings", and every other app's diff
must be empty or explained. So a re-record is not a silent refresh - name what
moved and why, in the commit and in the pull request, the way
[ADR 0001](../../docs/adr/0001-vm-query-api-two-functions.md) §4 asks of the
corpus it governs: a green local run nobody wrote down is not a promise.

## Boundary

CI does not run the corpus: no runner has the `splashcheck` binary or the two app
checkouts, so `tools/test_splashcheck_golden.py` asserts the honest exit 2 there
and compares for real on a prepared developer machine. The corpus is a local
regression net, and a machine that has not run it has not been checked - which
is why the runner says so instead of passing quietly.
