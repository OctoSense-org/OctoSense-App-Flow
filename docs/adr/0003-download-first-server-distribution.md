# ADR 0003: Download-first distribution: a pinned server, one notice, and an activation that never fails

- **Date:** 2026-10-13
- **Status:** Accepted (2026-10-13). Not yet implemented: the release assets are issue #2 and the resolver with its download is issue #7, both in this repository.
- **Scope:** How the Splash language server reaches a person who installs the editor plugin — where the binary comes from, how its version is pinned, what happens when it cannot be fetched, and which part of that is a pure function with tests. It does not decide the server's behaviour (ADR 0002) or its query API (ADR 0001), and it does not cover embedding platform binaries in the `.vsix`, which is a separate spec.
- **Relates to:** [ADR 0001](0001-vm-query-api-two-functions.md), [ADR 0002](0002-analysis-posture-and-one-suppression-rule.md); App Flow #1 (the spec), #2, #7, #8.

## Context

Today the server exists only for its author. To use it, a person checks out the makepad fork, runs `cargo build` on it by hand, and points the plugin at the result. For everyone else the plugin does not exist: they get syntax highlighting, which is the one capability that needs no binary. The spec's third problem statement is exactly this, and its acceptance is a fresh VS Code on any of the three desktop platforms, with nothing built locally.

Two facts, both measured, decide what the distribution can and cannot be:

### What shaped this decision (measured)

- **The fork has no CI.** `gh api repos/OctoSense-org/makepad/actions/workflows` answers `{"total_count": 0}`, and `gh api repos/OctoSense-org/makepad/contents/.github` answers 404. No workflow builds the server, so no release assets exist to point at, and a distribution plan that assumes the fork will produce them is a plan that waits on work nobody has scheduled. The assets are therefore produced here, where CI does run: `.github/workflows/ci.yml` already builds on `ubuntu-latest`, `windows-latest` and `macos-14`, which is the platform matrix the plugin needs (issue #2).
- **A Windows path with single backslashes does not survive JSON.** Node 24, today:

  ```
  $ node -e 'JSON.parse(String.raw`"C:\Users\me"`)'
  SyntaxError: Bad escaped character in JSON at position 4 (line 1 column 5)
  ```

  A server path typed the way a Windows person types it either fails to parse or, once it has round-tripped through a JSON layer that escaped it once, arrives with its separators eaten. The symptom is the worst kind: the extension activates, finds nothing where the path points, and silently falls back to highlighting. That is why the discovery and download strategy is a pure function with every input injected and node tests over the whole priority chain (issue #7), and why the stale-value cases — a setting mangled by escaping, a host that cached a resolved path earlier in its session — each get a named test rather than a bug report.

## Decision

### 1. Download-first, as the model for a new user

A person who installs the plugin and opens a `.splash` file gets the server without building anything: on first use the extension downloads the platform binary for its host and starts it. "Download-first" describes the model, not the resolver's order — see §2.

### 2. The resolver is one pure function, and the download is its last source

Discovery and download are a single pure function whose inputs are all injected: the workspace setting, the environment, `PATH`, the sibling checkouts, and a downloader. It returns either a resolved server path with the reason it was chosen, or "not found" with the reason it was not.

The order is setting → environment variable → `PATH` → sibling checkout → download. The download is last because everything before it is a local statement of intent: a person who set a path, exported a variable, or has the fork checked out beside the plugin means that build, and a download that shadowed it would be a support problem with no diagnostic. The download is what the person who has none of those gets, which is the case this ADR exists for.

The existing chain's behaviour does not change (issue #7's last criterion): a setting still wins, an environment variable still wins over `PATH`, and a sibling checkout is still found. The function is additive — the download is a new last source, not a rewrite of the four.

### 3. The version is pinned, and moves only by a pull request

The version is a constant in the plugin's manifest. It is overridable by a workspace setting, for a person testing a local build of the server against a released plugin. Nothing floats: no "latest", no range, no resolution at install time against a moving tag.

The pin moves when a pull request moves it, and that pull request names what changed in the server. Each release asset records the makepad revision it was built from, and the output channel prints that revision beside the server's own version — so "which binary is this, from which source" is answerable from inside the editor instead of by bisecting a fork.

### 4. Failure is one notice, one explanation, and a fallback — never a dead plugin

When the server cannot be fetched:

- **One notification**, once per session per reason, saying the server is unavailable. Not one per document, not one per retry.
- **One output-channel line** with the cause (network, HTTP status, checksum, unsupported platform) and the manual build path — the `cargo build` command and the setting that points at its result — so the person who wants to self-serve can.
- **Then the plugin carries on in degraded mode**: syntax highlighting, and whatever capabilities survive without a server. `activate()` does not throw, does not reject, and does not leave a half-registered client behind. A download failure is a missing feature, not a broken install.

### 5. Three platforms, named assets, checksums

The assets are named by platform and architecture and are checksummed, so a resolver can refuse a truncated or wrong download instead of starting a corrupt binary. A platform with no asset says so in the notice — "no server for this platform yet" is a different sentence from "download failed", and the person needs to know which one they got.

## Consequences

- A fresh install works with no local toolchain, which is the whole point; the cost is one download per version per platform, and a version bump re-downloads.
- The extension's activation path gains a network call, contained behind the resolver: the pure function decides, the caller performs. That seam is also where the "only highlighting left" failures are tested (issue #7), which is why it is the only new seam on the extension side.
- The plugin now ships a version of the server that can be older than the makepad revision a person has checked out. The pin's output-channel line is what keeps that visible.
- A person behind a proxy or offline gets highlighting plus one notice. That is the intended degraded mode, not a bug to be fixed by retrying harder.

## Alternatives considered

- **Embed the platform binaries in the `.vsix`.** Rejected for now, and named as out of scope in the spec: it triples the package every person downloads to serve the one platform they use, and it makes the server's version the package's version. It is the right answer later, when there is a release process worth embedding.
- **Depend on the fork's CI to publish assets.** Rejected on the measurement above: there is no CI in the fork, so this would be a distribution plan that cannot start.
- **Resolve "latest" at install time.** Rejected: a plugin and a server that can drift apart inside one session produce findings nobody can reproduce, and the spec's requirement is that the pair is pinned and overridable.
- **Try the download before the local chain.** Rejected: a person who set a path or exported a variable means it, and a download that wins over an explicit setting turns a configuration into a mystery.
- **Retry the download with backoff, then give up.** Rejected: a failure that is not reachable in one attempt is not reachable in five, and each retry is another chance to notify. One attempt, one notice, one explanation.

## Measurements

Windows, 2026-10-13:

```
$ gh api repos/OctoSense-org/makepad/actions/workflows --jq .total_count
0
$ gh api repos/OctoSense-org/makepad/contents/.github
{"message":"Not Found", ... "status":"404"}
$ node -e 'JSON.parse(String.raw`"C:\Users\me"`)'
SyntaxError: Bad escaped character in JSON at position 4 (line 1 column 5)
```

The platform matrix is `.github/workflows/ci.yml` in this repository: `ubuntu-latest`, `windows-latest`, `macos-14`.
