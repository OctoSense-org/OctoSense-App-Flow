# Flow: script app from a text brief

Turn a written description of an app into a contained script app
(`main.splash`) that runs in `card-host`, passes the App Hub gate, and is
ready for the publishing steps a person takes.

## Use when

- The input is text: what the app does, its screens, its data, who it is for.
- The app's behavior fits a contained isolate: its own storage, requests to
  declared hosts, and existing host services ([HOST-SERVICES](../../docs/HOST-SERVICES.md)).

Use another flow when the input is a design image or atlas
([image-to-card](../image-to-card/FLOW.md)) or a Sketch file
([kits/sketch](../kits/sketch/FLOW.md)). If the app needs new native code or a
new host service, no flow applies: that is a shell change, not a bundle.
[flows/README.md](../README.md) lists every flow.

## Inputs

| Input | Required | Notes |
| --- | --- | --- |
| Brief | yes | Purpose, screens, actions, data sources, what is stored, error and empty states. |
| App id and name | yes | id `[a-z0-9.-]{1,64}`, not `os.*`, and its last segment not a reserved name such as `notes` or `weather` ([QUICKSTART §3](../../docs/QUICKSTART.md#3-create-an-app)). `tools/octo new` refuses both. |
| Target platforms | yes | The platforms you will run and test the app on, each passed to `tools/octo new` as `--platform` (`macos` for `card-host` on a Mac). The listing claims them; a person confirms the claim (step 10). |
| Hosts the app will call | if any | Exact host names; each becomes an entry in `network.hosts`. |
| Publisher details | for publishing | Name, support contact, privacy-policy URL: **HUMAN** supplies them. |

## Prerequisites

```sh
tools/octo doctor        # pass: "[ok]" for python, hub and card-host, then "ready: …"
```

If it fails, follow its printed fix, or [QUICKSTART §1–2](../../docs/QUICKSTART.md#1-prerequisites).
Step 5 onward needs a graphical session.

## Steps

Set `A=<app dir>` (it must not exist yet, or be empty), `B=$A/bundle`,
`P=<port>` (for example 8141) and `HUB=<the hub path that tools/octo doctor prints>`.

For model-assisted work, follow the
[development and validation loop](../../docs/MODEL-VALIDATION.md) in steps
4–9: start with one populated screen and one working action, and after each
fix, check startup, send real input and inspect the pixels. Keep the failed
runs, and tie the final evidence to the tested source.

| # | Do (exact command or action) | Pass when | Human? |
| --- | --- | --- | --- |
| 1 | `tools/octo new $A --platform <target> --id <id> --name "<Name>"`, with one `--platform` per target platform. It refuses a directory that already holds files, so run it before you write anything into `$A`. | Prints `created …`, `bundle stamped` and `target platforms: …`. | no |
| 2 | Write the brief into `$A/BRIEF.md` (outside `bundle/`): screens, actions, data, states, hosts, capabilities you think it needs and why. | Every screen and action has a line; every capability has a reason. | Confirm the brief with the requester if it was ambiguous. |
| 3 | Edit `$B/manifest.json`: capabilities and `network.hosts` from the brief, nothing more ([CAPABILITIES](../../docs/CAPABILITIES.md)). | Every capability maps to a line of the brief. | no |
| 4 | Write `$B/main.splash` using only APIs in [SCRIPT-API](../../docs/SCRIPT-API.md) or found in the runtime source; start from the template's structure (state `let`s, `fn`s, `start_timeout(0.05, …)` loader, one root view). | The file is saved, and you can cite a source for every API it uses. | no |
| 5 | `tools/octo run $B --port $P --hidden --detach` (exits 1 if `$P` is taken: quit the old instance with the `curl … /quit` it prints) | Prints the `admitted` and `ready: first frame drawn` lines, and no line that `grep -nE '\[E\]\|splash:[0-9]+:\|refused\|on_render closure failed\|callback error' $A/.local-state/card-host.log` prints comes after the `[SPLASH] eval:` line (do not grep for "error": healthy runs log Metal's `MTLCompilerError` in `[ui-hang]` lines). | no |
| 6 | `tools/octo shot $P /tmp/first.png` (right away is fine: `run --detach` returns once the UI is drawn, and `shot` waits for a settled frame), then open it. | The first screen is drawn and its initial fields are filled after loading; an admitted app whose fields have not loaded does not pass. | no |
| 7 | Drive every action in the brief with `curl -s "127.0.0.1:$P/click?x=&y=&wait=1"`, `curl -s "127.0.0.1:$P/t?t=…&wait=1"` and `curl -s "127.0.0.1:$P/k?k=down&c=ReturnKey"`. After each action, check a screenshot, `/snap?q=…` or the jail file under `$A/.local-state/<id>/`. Click a `TextInput` again before each `/t`, because a button click takes its focus. On a Retina Mac, divide screenshot pixels by 2 to get click points. | Each action's effect is observed and recorded (command + what changed). | no |
| 8 | Test states: empty, error (for example network off or bad input), restart persistence (`curl -s 127.0.0.1:$P/quit`, rerun step 5). | Each state shows its intended message or data; stored data survives a restart when the brief says so. | no |
| 9 | Give the author of `main.splash` (a person or a model) the reproduction, source revision, PNG and log findings; make one focused fix and repeat steps 4–8. Keep the failed runs in their own folder. | Every action the brief requires passes on the final source, in both the behavior checks and a direct visual review. Screenshots taken before the last edit do not count. | no |
| 10 | Edit `$B/listing.json`: subtitle, description (what it does, truthfully), category, keywords, the platforms you ran it on (`macos` for a `card-host` run on a Mac), release notes. Leave the publisher fields to the person if you do not know them. Create a distinct `$B/assets/icon.svg` using the [OctoSense family format](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/ICONS.md#design-and-export-recommendations): 64-point square, central 66% foreground, restrained illustrated object, no baked platform corners or outer shadow. | Listing parses (step 12) and says only what the app does; the icon was inspected at 64/40/24 px, on light/dark grounds and with Android/macOS/iOS frames. A gate pass does not assess its design. | Publisher name, support and privacy URL, platform claims: **HUMAN**. |
| 11 | Drive the unsigned app to its best real state; `tools/octo shot $P $B/screenshots/01-main.png` (add `02-…png` for more screens, at most 8, and list them in `listing.json`); open each; `curl -s 127.0.0.1:$P/quit`. | Each PNG is a real capture you looked at. | no |
| 12 | `find $B -name .DS_Store -delete && tools/octo check $B` | `<id> <version> — PASSED`, only the unsigned warning; no placeholder note, or only placeholders that wait for the person's publisher details. | no |
| 13 | `mkdir -p $A/build $A/review && "$HUB" scan $B --packet $A/build/review.json`, then write answers to its questions into `$A/review/ANSWERS.md`. | Packet written; every question answered honestly: seven, or eight when the bundle ships `tools.json`, `AGENT.md` or skills. | no |
| 14 | Report (see [AGENTS.md](../../AGENTS.md#reporting)): commands run and their results, screenshots, what was not verified. **Stop.** | Report delivered. | Hand-off to a person. |

## Outputs

- `$A/bundle/`: `manifest.json` (stamped), `listing.json`, `main.splash`,
  `assets/icon.svg`, `screenshots/*.png`. This is the submission candidate.
- `$A/BRIEF.md`, `$A/build/review.json`, `$A/review/ANSWERS.md` and
  `$A/AGENTS.md`: outside the bundle, not submitted.
- The `tools/octo check` output, verbatim.

## Hand-off

Continue with [docs/PUBLISHING.md §3.6](../../docs/PUBLISHING.md#36-github-publisher-identity--human).
Open the App Hub submission issue to request publication; provide the
repository, version/commit, screenshots and permissions. It can precede the
release. `tools/octo publish-github "$A"` installs the tag workflow (`new`
already copies it); review/commit tested source and push a new version tag.
GitHub produces the attested release without a developer key. Add its successful
workflow and exact pack to the issue. Hub checks and administrator approval
control catalog publication, as App Hub's
[SUBMITTING](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md)
describes. Workflow review, public release and submission are **HUMAN** steps
unless already authorized. Live keyless publishing and compatible-host
installation remain unverified; see the publishing guide's status.
