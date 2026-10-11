# Developing this OctoSense app

`CLAUDE.md` and `GEMINI.md` only import this file, so every coding agent reads
the same rules.

This repository is one OctoSense script app. `bundle/` is the app and the only
thing submitted to the App Hub; everything else stays outside it.

Follow the docs of OctoSense App Flow, the harness this app came from,
and do not invent requirements or APIs:

- Build, run and test: [QUICKSTART](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/QUICKSTART.md)
- The language and every API an app may use: [SCRIPT-API](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/SCRIPT-API.md)
- Capabilities: [CAPABILITIES](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/CAPABILITIES.md)
- Which host API families serve store apps, where and since when: [HOST-API-FAMILIES](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/HOST-API-FAMILIES.md)
- Final bundle, screenshots and human checkpoints: [PUBLISHING](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/PUBLISHING.md)
- Publisher proof and the submission issue: App Hub's [SUBMITTING](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md)

Set `OCTO=<path to OctoSense-App-Flow>/tools/octo`, then run this loop
from this directory. The CLI lives in the harness repository, not here; on
Windows, run it as `python $OCTO`.

1. Edit `bundle/main.splash`.
2. Run `$OCTO run bundle --port 8141 --hidden --detach`. It returns after
   `ready: first frame drawn`. If it exits 1, the port is taken: run the
   `curl … /quit` it prints, then try again.
3. Drive the app (`/click`, `/t`, `/snap`), then run `$OCTO shot 8141 out.png`
   and open the PNG.
4. Run `curl -s 127.0.0.1:8141/quit`.
5. Run `$OCTO check bundle`. Expect `— PASSED` with only the unsigned
   warning. Until `bundle/screenshots/01-main.png` exists
   (`$OCTO shot 8141 bundle/screenshots/01-main.png` in step 3), the gate
   refuses the listing; fix every other `[refused]` line before you go on.

If this app has its own Rust component (`components/<name>/`, built into
`bundle/fns/<name>.wasm` by `$OCTO wasm build --app .`), the loop above
covers the layout only: `card-host` answers every `wasm.*` call with
`no service answers "wasm" on this device`, and it refuses an app that
requires `host-api-v1`. Test the component's logic natively with
`cargo test --locked` in its crate, then drive the whole app in the
[compatible OctoSense release](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/README.md#compatible-shell-download)
with the shell's Makepad instrument, in a profile of its own
([RUST § Test it](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/RUST.md#6-test-it));
Repo Radar's [native acceptance](https://github.com/ymote/octosense-repo-radar/blob/main/tools/NATIVE-ACCEPTANCE.md) is a scripted example. Never
remove a `requires` entry to make a preview pass.

Follow these rules:

- Ask only for capabilities a screen uses; declare every `https://` host in
  `network.hosts`; never use `http://`.
- Before building on a host API, check that its family serves store apps on your platforms ([HOST-API-FAMILIES](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/HOST-API-FAMILIES.md)): `llm`, `news` and `calendar` answer only system apps, `clipboard` fails, and `mail` cannot send on RC1.
- Never collect or store a password, PIN, one-time code, API key or token;
  accounts go through a host service.
- Keep the id's last segment, after its final `.`, off App Hub's reserved
  names (`notes`, `weather`, `terminal` and others); the gate refuses them.
- Put only files the gate accepts in `bundle/`: no `.DS_Store`, no file
  without an extension, 8 MiB at most. Plain `.txt`/`.md` license and
  attribution URLs are allowed; keep required notices. Agent guidance and
  structured resources retain their host/resource checks.
- Capture screenshots from the unsigned bundle with `$OCTO shot`, and look at
  each one; never use a placeholder.
- Restamp editable unsigned source after every edit (`$OCTO check` does it).
  Never edit or restamp a sealed attested/signed release. Test and capture
  screenshots before the publishing workflow seals the bundle.
- Keys, `.local-state/`, `build/` and review packets never enter `bundle/` or Git.
- Keep `.gitattributes` (`bundle/** -text`) committed: the digest covers every
  byte, and a line-ending conversion breaks it.
- Review `.github/workflows/publish-app.yml` before releasing.
  `$OCTO publish-github .` installs it for an existing app; `new` copies it too.
  App Hub accepts only GitHub-attested releases, so no publisher key or
  repository signing secret is involved. Never create a publisher key, sign a
  manifest or pass `--publisher-key` to publish. Push a new
  `v<manifest.version>` tag of tested source to prepare, attest, verify and
  pack it. The tag source and sealed release pack are different artifacts.
- Opening the App Hub issue is the request to publish; provide repository,
  version/commit, screenshots and permissions, then add the verified release
  pack when ready. Until App Hub first publishes the app, post each new
  release on the same issue and update its title and Version field; after
  publication, open a new issue for each new version. A release alone does
  not submit or approve the app.
- Stop at human steps: publisher details, workflow review, platform claims,
  tag and submission, unless already authorized in this session. Respect
  actual approval; never fabricate it.
- `publisher-github-v1` needs contract 1.8.0 and a compatible host; older
  hosts and `card-host` refuse the sealed release. OctoSense desktop
  0.1.0-rc.1 and later install GitHub-attested apps (verified on macOS); no
  released phone build supports them yet. Follow the linked publishing guide for current evidence.

Add this app's own requirements, data sources and tests below.
