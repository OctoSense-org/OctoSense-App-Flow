# Capabilities

English | [简体中文](CAPABILITIES.zh-CN.md)

A capability is a permission an app requests in `manifest.json`. A script gets
only what its manifest requests and the gate admits.

App Hub's [PUBLISHING § The manifest](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#the-manifest)
is the reference for the gate's rules and for the words the store shows the
person. [HOST-SERVICES](HOST-SERVICES.md) says which shell answers each host
service.

## Request capabilities

```json
"capabilities": ["storage", "net"],
"network": { "hosts": ["api.open-meteo.com"] }
```

- **The list is closed.** `KNOWN_CAPABILITIES` in App Hub
  `crates/app-contract/src/manifest.rs` holds 105 names: 27 broad
  capabilities, such as `storage` and `glance`, and 78 exact service names,
  such as `octos.turn.start`. The gate refuses any other name, such as
  `contacts`, and any bare prefix, such as `octos.`:

  ```text
  [refused] policy: app dev.example.myapp requests unknown capability "contacts"
  ```

- **Nothing is implied.** An app gets no capability it does not request, and
  no capability grants another.
- **Request the least the app needs.** Reviewers flag any grant that nothing
  on screen uses.
- **The store shows the manifest, not the listing.** Before install, the
  person sees one permission line per capability and a privacy summary, both
  derived from `manifest.json`. Listing text cannot soften them.

## Device and data

| Capability | What the script gets | Without it |
| --- | --- | --- |
| `storage` | The app's own storage jail, one directory per app id: [`fs.*`](SCRIPT-API.md#storage-fs), camera captures, and local files a widget reads, such as a map archive. | No jail. Every `fs.*` call errors with `storage not available in this context`, a capture saves nothing, and a widget reads no local file. |
| `camera` | `CameraPreview`: preview, photo and video. Captures land in the jail as `DCIM/IMG_<ms>.jpg` and `DCIM/VID_<ms>.mp4`, so request `storage` too. Served since RC1 on Android and macOS. | `CameraPreview` refuses: `this app was not granted the camera`. The operating system's own camera prompt applies either way. |
| `microphone` | Sound in camera videos, and, since RC2, `microphone.record_start/record_status/record_stop/record_cancel`: a short foreground recording (mono WAV, at most 30 seconds) saved into the app's storage, so request `storage` too; consent comes through `microphone.permission.request` and the OS prompt. Served since RC1 on Android and macOS; hardware acceptance of recording is pending. | Videos record without sound, and recording is refused. |
| `library` | Each capture is also offered to the system photo library, where other apps can see it. | Captures stay in the app's jail. |
| `location` | The device position: `sys.gps(...)` and the follow camera of `MapView`. The operating system's location prompt still applies. Served since RC1 on Android and macOS; `location.get` is Android only, and RC2 adds `location.sample`, a fresh fix for a foreground app, on both. | `sys.gps("ok")` reads 0, meaning no fix. |
| `files` | Since RC2: `files.import` and `files.export` move one document between the native file dialog and the app's storage (request `storage` too), `files.pick_photo` imports a PNG, JPEG or WebP, and `files.share` hands text to the Android share sheet; 1 MiB per file, foreground only. Served on macOS, Windows and Android; Linux needs zenity, qarma, matedialog or kdialog; chooser acceptance is pending. | Every `files.*` call is refused. |
| `audio` | Since RC2: `audio.play`, `audio.status` and `audio.stop` play one WAV, MP3, FLAC or Ogg file (at most 1 MiB and 60 seconds) from the app's storage while the app is in the foreground, so request `storage` too. Served on macOS and Android; hardware acceptance is pending. | `audio.play` is refused. |

Without `storage`, the `grants:` line of `hub check` says `storage none`, and
the gate warns about each script that calls `fs.*` and about a `camera` grant:

```text
[warning] storage: main.splash calls fs.read, fs.write, fs.exists, which fail without the storage capability
```

## Network

| Capability | What the script gets | Without it |
| --- | --- | --- |
| `net` | `net.http_request` and `net.web_socket`, to exactly the hosts in `network.hosts`. A host is a bare, exact, lowercase name: no scheme, path, port or wildcard. A component's `wasi:http` requests need `net` too, but reach any host: an app's network declarations are shown at install and not enforced while it runs (OctoSense's ruling of 8 October 2026; on OctoSense `main`, in no release yet; see [RUST § Network](RUST.md#network)). | No `net` in the script at all: `variable net not found in scope`. The same holds for `net` with an empty host list. |
| `images` | Pictures (`Image{src: http_resource(url)}`) from any public `https://` host, beyond `network.hosts`: a feed reader's thumbnails. It does not widen `net.http_request`. | Pictures load only from listed hosts. |
| `web` | `WebReader` opens any public `https://` page in the system web view. The page has no way back into the app. Availability follows the [host and platform limits](../README.md#compatible-shell-download). | `WebReader.open` works only for listed hosts and refuses others: ``refused <url>: not on this app's host list, and no `web` grant``. |

Desktop RC1 and RC2 embed ordinary pages on Windows with WebView2 and on Linux
X11/XWayland with GTK 3/WebKitGTK. These engines are not bundled; native
Wayland embedding and Windows/Linux embedded backend sign-in are unsupported
([requirements](../README.md#compatible-shell-download)). Historically,
`card-host` and the Linux and Windows builds of `desktop-v0.1.0-beta.1`
return `true` from `open`, show no page and log
`Not implemented on this platform: CxOsOp::SpawnSystemBrowser`.
`desktop-v0.1.0-beta.2` ships for macOS only.

The runtime and the gate refuse these:

| Request | Answer |
| --- | --- |
| A `net` request to an unlisted host | `this app may not reach <url>` |
| A private or internal address, with any capability | `host not permitted (private/internal): <host>` |
| Hosts listed without `net` | The gate refuses: `lists hosts but does not request the net capability` |
| A host with a scheme or path, such as `https://x` | The gate refuses: `host "https://x" must be a bare host name, with no scheme or path` |
| `main.splash` naming an `https://` host that is not listed | The gate refuses under `assets` (`main.splash reaches <host>, which the manifest does not declare in network.hosts`), unless the app requests `images` or `web` |
| Any `http://` URL in the source | The gate refuses under `assets`, with or without `web` |

The script-side rules are in [SCRIPT-API § Network](SCRIPT-API.md#network).

## Host services

A host service does work in the shell that the app must never do itself, such
as holding a password or a token. The script calls it with
`host.request("<family>.<method>", args, fn(r){…})`
([SCRIPT-API](SCRIPT-API.md#host-services-hostrequest)). Each call needs the
capability `<family>`. Without it, the callback runs at once with `r.is_ok`
false and this error:

```text
this app was not granted "mail", which "mail.accounts" needs
```

| Capability | What the script gets |
| --- | --- |
| `mail` | Mail accounts the person signs in to on a host sheet: folders, messages and sync. Since RC2 a store app can also send: `mail.compose` and `mail.compose_status` keep a draft, and `mail.review_send` (or `mail.send`, which opens the same review) shows the message on the host's native review, where the person approves it with a physical press. That review exists on macOS and Android; on Windows and Linux it fails with `Physical Mail send approval is unavailable on this platform`, and SMTP delivery is unverified. On RC1 a store app had no send path ([OctoSense #409](https://github.com/OctoSense-org/OctoSense/issues/409)). The methods are in [HOST-SERVICES § Mail](HOST-SERVICES.md#mail-the-worked-example). |
| `auth` | Connections to GitHub and Google that the person approves on a host sheet, and, since desktop RC1, sign-in to the app's own backend. The app receives handles, never tokens. `auth` alone identifies the person but reads none of their data. See [Use a connected account](#use-a-connected-account). |
| `github` | Repository reads, and saves the person approves on a host sheet. Needs `auth`. |
| `gcalendar` | Google Calendar reads and sync, and writes the person approves on a host sheet. Needs `auth`. |
| `gmail` | Gmail reads, versioned reply drafts, sending after the person approves it in the host's send review, and new-mail events for the app's agent. Needs `auth`. |
| `glance` | `glance.publish`, `glance.withdraw` and `glance.list`: cards on the Glance screen that open only this app. See [AI-SERVICES § Publishing to the Glance screen](AI-SERVICES.md#publishing-to-the-glance-screen). |
| `model` | `model.complete` and `model.budget`: one-shot model calls on the person's own AI providers, checked against the app's JSON Schema, within a daily budget. See [one-shot calls](AI-SERVICES.md#one-shot-model-calls-model). [Media and embeddings](AI-SERVICES.md#media-and-embeddings-model) use the same capability in OctoSense #368, included since [desktop RC1](../README.md#compatible-shell-download); beta.2 and `card-host` do not serve them. Provider entitlement and live validation are separate. |
| `runtime` | `runtime.list` and `runtime.describe`: the host APIs this build implements, with no account data. Desktop RC1, RC2 and `card-host` answer them; desktop-v0.1.0-beta.2 refuses the capability. See [HOST-API-V1 §2](HOST-API-V1.md#2-discover-before-offering-an-optional-feature). |
| `wasm` | The app's own functions: WebAssembly modules in the bundle's `fns/` (at most 8), which the host's `wasm` service runs in a sandbox with a deadline and a memory cap. A function gets only its input and reaches no file, network, clock or other app. An agent tool can run one with `host_method: "wasm.<function>"`. The store says "Run its own sandboxed functions on this device". Desktop RC2 serves it, with limited support, on macOS and Linux, as do standard Home source builds on Android; builds for Windows, iOS and OpenHarmony leave it out, and RC1 did not serve it. A WebAssembly component (OctoSense ADR 0014; on OctoSense `main` since 10 October 2026, in no release yet) also reaches the clock, random numbers and, with `storage`, the app's storage folder, and needs `requires: ["wasm-components-v1"]`; with `net` it reaches the network (any host: `network.hosts` is shown at install, not enforced), and it can call the host services the app is granted. To write, build and call a function, see [RUST](RUST.md). |
| `device_calendar` | Since RC2: the calendars configured in the OS. `device_calendar.permission.request` asks the person's consent and the OS permission, `calendars.list` and `calendars.select` pick a calendar and return a handle, `events.list` and `events.get` read (recurrence and attendees read-only), and `events.create`, `events.update` and `events.delete` wait for the person's physical press on a native review. Needs `requires: ["host-api-v1"]`. Served on macOS (EventKit) and Android Home; the OS-calendar interaction is pending acceptance. Separate from `calendar` (Calendar's own service) and `gcalendar` (Google). |

Apart from `runtime`, none of these services runs in `card-host`. There
every call answers `no service answers "<family>" on this device`. Test them
in an OctoSense shell.

## Capabilities a store app gains nothing from

No shell serves these names to a store app. The gate admits all but the
engine names, which it refuses. Do not request them.

| Capability | What happens |
| --- | --- |
| `calendar` | The `calendar` service answers only the Calendar system app: `calendar is Calendar's own service`. For a person's Google Calendar, use `gcalendar`. |
| `photos`, `youtube` | The only service for each answers the matching system app's `notify` call: `photos.notify serves os.photos only`. |
| `llm` | The service manages the device's AI providers and answers only system apps: `llm is for OctoSense's own apps.` For model calls, use `model`. |
| `news` | The service answers only system apps: `The news service serves system apps only.` |
| `research`, `crawl` | The system toolbox for an app's agent. The shells grant it only to system apps, and only in builds with the `toolbox-peers` feature. The gate still requires a top-level `research` scope: `requests research but declares no research scope`. Not yet for store apps: [OctoSense#64](https://github.com/OctoSense-org/OctoSense/issues/64). |
| `prompt` | Not yet: no host reads it, and `host.prompt` does not exist. An app's agent asks the person questions with `ask_user_question`, declared in `agent.tools`. |
| `ledger.read`, `clipboard` | No host serves them through `host.request` on any release: every call fails. The `clipboard` grant only unlocks a WebCard's write-only clipboard bridge. |
| `sheet`, `photo`, `word`, `deck`, `cad`, `light`, `sound`, `design`, `film`, `effect`, `vector`, `pdf` | Craft engines behind host services for system apps ([ADR 0013](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0013-craft-engines-as-pinned-services.md)), shipped in desktop RC2 for the system assistant. App Hub `main`'s contract now lists the twelve names as declarable capabilities, but RC2's admission (contract 1.10.0) refuses a manifest that names one, and the services answer no store app on any build. |

The per-family summary, with platforms and since-versions, is [HOST-API-FAMILIES](HOST-API-FAMILIES.md).

## Use a connected account

An app reaches a person's GitHub or Google data through host services. The
shell holds the provider credentials; the app holds only a connection handle.

1. Declare `auth`, the provider family and per-account storage. Leave the
   provider's API hosts out of `network.hosts`: the host service makes the
   requests.

   ```json
   "capabilities": ["storage", "auth", "github"],
   "network": { "hosts": [] },
   "storage": { "accounts": true }
   ```

   `hub check` then shows:

   ```text
   grants: capabilities {"auth", "github", "storage"}, hosts {}, storage 16777216 bytes, agent none
   ```

2. Ask the person to connect, from one of the app's own screens:

   ```splash
   host.request("auth.connect", {provider: "github" scopes: ["public_repo"]}, fn(r){
       if !r.is_ok { ui.status.set_text(r.error) }
   })
   ```

   The host raises its own sign-in sheet. On success, `r.data` is the new
   connection: `handle` names it, and `subject` and `label` identify the
   account. Each scope needs a capability. The identity scopes need only
   `auth`, so an app can identify the person without reading their data:

   | Provider | Scopes | Needs |
   | --- | --- | --- |
   | `github` | `read:user` | `auth` |
   | `github` | `public_repo`, `repo` | `auth` and `github` |
   | `google` | `openid`, `email`, `profile` | `auth` |
   | `google` | `calendar.list`, `calendar.events` | `auth` and `gcalendar` |
   | `google` | `mail.read`, `mail.send` | `auth` and `gmail` |

   If the call fails, `r.error` says why:

   | Error | Cause |
   | --- | --- |
   | `Requested scopes exceed this app's granted services` | A scope's family is missing from `capabilities`. |
   | `Open the app to connect an account` | The call came from a Glance card or an agent's tool. |
   | `OAuth is not configured. Add provider registrations in the host's oauth/clients.json` | A beta.2 host has no `clients.json` ([Limits](#limits)). |
   | `This provider is not configured in OctoSense` | A beta.2 host's `clients.json` has no registration for the provider. |
   | `GitHub sign-in is unavailable in this build. Check for an OctoSense update or contact its distributor.` (or `Google sign-in …`) | A desktop RC1 or later build has no registration for the provider; the public RC packages include none ([Limits](#limits)). |

3. Call the provider family. Pass the connection's `handle` as `connection`,
   such as `{connection: <handle> page: 1}` for `github.repositories`.

   | Service | Methods |
   | --- | --- |
   | `auth` | `connect`, `accounts`, `active`, `select`, `disconnect`; since desktop RC1 also `backend.me` and `backend.request` ([below](#sign-in-to-your-own-backend)) |
   | `github` | `repositories`, `files`, `read`, `review_save` |
   | `gcalendar` | `calendars`, `cached`, `refresh`, `get`, `prepare`, `review_save`; `sync` on desktop-v0.1.0-beta.2 only ([Limits](#limits)) |
   | `gmail` | `labels`, `messages`, `message`, `draft.open`, `draft.get`, `draft.edit`, `draft.review`, `events.status`, `event.status`, `event.decide` |

   OctoSense's
   [`crates/oauth-service/README.md`](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.md#app-facing-contract)
   gives each method's arguments and answers.

4. Have the person approve every write. `github.review_save` and
   `gcalendar.review_save` freeze the change and show it on a host sheet,
   where the person approves it. On desktop-v0.1.0-beta.2, that sheet does not
   check for a physical press. Desktop RC1 and later require a physical press on
   its native **Approve & Save** control; protected writes remain unsupported
   and fail closed on Windows/Linux.
   `gmail.draft.review` opens the host's send review, which needs a physical
   press on every build: no script, agent or remote click can send mail.

The three [connected reference apps](../examples/connected-apps/README.md),
published in the App Hub catalog, use exactly this. App Hub's
[SUBMITTING](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md#the-three-reference-apps)
summarizes them.

### Sign in to your own backend

Since [desktop RC1](../README.md#compatible-shell-download), the host can sign the
person in to the app's own backend and call its declared operations, within
the documented platform limits. Historical `desktop-v0.1.0-beta.2` predates it.

1. Declare `auth` and `storage.accounts: true`, and register the backend in
   one of two ways:
   - Declare it in the manifest's `backend` block, with `backend-api-v1`
     in `requires`, as [HOST-API-V1 §4](HOST-API-V1.md#4-connect-the-apps-backend)
     shows. The host reads it from the admitted signed bundle.
   - Have the host's operator register it in
     `<apps root>/.host/oauth/backends.json`. The host reads this file only
     for a bundle that declares no `backend`.
2. Connect with the `backend` provider and its one scope:

   ```splash
   host.request("auth.connect", {provider: "backend" scopes: ["app.session"]}, fn(r){
       if !r.is_ok { ui.status.set_text(r.error) }
   })
   ```

   On macOS and Android 9 or later, the host opens the backend's login page
   in a WebView it owns, and the person registers or signs in there; the app
   cannot open or read that page. On macOS, `presentation: "browser"` uses
   the system browser instead; on Windows and Linux, the browser is the only
   mode, reachable since RC2 added the native link openers: a Windows fixture
   built from RC2's source completed a sign-in against a synthetic backend;
   Linux is untested.
3. Call `auth.backend.me` with `{connection: <handle>}`. It answers
   `{connection, backend_id, identity: {sub, label}}`, the identity the
   backend verified.
4. Call a declared operation with `auth.backend.request`
   ([HOST-API-V1 §4](HOST-API-V1.md#4-connect-the-apps-backend)). A write
   runs only after the person approves it on a host sheet with a physical
   press.

Without a registration, `auth.connect` answers
`This app's backend sign-in is unavailable. Contact the app's distributor.`
The backend must offer an OAuth authorization-code flow with S256 PKCE and a
`/me` endpoint, all on one HTTPS origin. OctoSense's
[developer backend contract](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.md#developer-backend-contract)
gives the details. iOS has no backend sign-in. Windows/Linux use the
external browser; embedded sign-in and protected writes are unsupported.
Live provider sign-in is not established by the synthetic backend checks.

### Limits

- **Builds.** Use [desktop RC2](../README.md#compatible-shell-download) for
  current GitHub-attested apps; RC1 also installs them. Historical desktop-v0.1.0-beta.2 (macOS, Apple silicon) serves
  `auth`, `github`, `gcalendar` and `gmail`. The beta.1 stores
  (desktop-v0.1.0-beta.1 and home-v0.1.0-beta.1) list such apps but refuse to
  install them, because their contract does not know `auth`. No released phone
  build installs them.
- **Provider registrations.** Public RC packages (RC1, RC2) contain no Google/GitHub
  registrations; the host distributor/operator must supply them. Beta.2 reads the GitHub and Google
  registrations only from `<apps root>/.host/oauth/clients.json`, and its
  downloads contain none, so whoever runs beta.2 supplies that file. A build
  of an RC can compile a distributor's registrations in instead;
  there, `clients.json` is an optional operator override that replaces the
  whole compiled-in set
  ([OctoSense: configure a release](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.md#configure-a-release-maintainers),
  [advanced operator override](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.md#advanced-operator-override)).
- **Calendar sync.** On desktop-v0.1.0-beta.2, `gcalendar.refresh` syncs the
  whole calendar and returns it oldest first, and `gcalendar.sync` returns
  Google's raw event pages. OctoSense desktop RC1 and later sync
  only from 30 days before today to 366 days after, with recurring events
  expanded, and returns that range as `window: {time_min, time_max}`. It
  refuses `gcalendar.sync` with
  `Use gcalendar.refresh for the bounded agenda; raw history synchronization is not exposed`.
- **Unverified:** most live use of the real GitHub and Google services,
  including repository writes and Gmail sends. OctoSense `main` records two
  macOS checks: identity-only GitHub and Google sign-in through the native
  host (Google with a test account), and one manual Google Calendar session
  that listed calendars and saved an event
  ([current delivery boundary](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.md#current-delivery-boundary)).
- **Not yet:** Google sign-in on Android. `auth.connect` answers
  `Google authorization needs the Android host adapter; desktop login is not supported on this device`.
- **Backend platform limits:** RC1 and RC2 support the host-run paths
  [above](#sign-in-to-your-own-backend); Windows/Linux embedded login and
  protected writes remain unavailable, and the Windows/Linux browser sign-in
  that RC2 makes reachable has been exercised only by a Windows fixture.

## Exact service names

Besides the 27 broad capabilities, `KNOWN_CAPABILITIES` holds 78 exact service names.
Each is its own consent; a prefix grants nothing.

| Names | What they grant | Who serves them |
| --- | --- | --- |
| `octos.session.open`, `octos.session.history`, `octos.turn.start`, `octos.turn.interrupt` | The app's own conversation with the device's assistant. See [AI-SERVICES](AI-SERVICES.md#the-assistant-capabilities). | An OctoSense shell that hosts the octos kernel, once the person allows the app's agent. Until then a call answers `Waiting for the person to allow this app's agent (OctoSense asks the first time)`. Rinx, a Matrix client, also serves them to bundles imported into it as mini-apps. |
| `matrix.*` (45 names, such as `matrix.read_messages`) | One operation each on the person's Matrix account. | Not served by any OctoSense shell. Only the Rinx app serves `matrix.*`, through its own host, to the mini-apps a person imports into it; that is not the App Hub install path. |
| `palpo.*` (29 names, such as `palpo.inbox.list`) | One operation each on Palpo, a Matrix server, for the person's account. | No OctoSense shell. Do not request them. |

## Storage, compute and agent limits

| Field | Meaning | Ceiling: store app / system app |
| --- | --- | --- |
| `storage.max_bytes` | The whole jail's quota | 16 MiB / 64 MiB |
| `storage.accounts` | `true`: data and one agent per account. Default: one `device` folder | – |
| `storage.agent_workspace` | `"account"` (default): the agent reads its account's folder. `"none"`: no files | – |
| `storage.cache_max_bytes` | The ceiling for the jail's `cache/` | – |
| `compute.instruction_budget` | Script instructions per session, cumulative | 20,000,000 / 4,000,000,000 |
| `compute.memory_bytes` | The isolate's heap | 64 MiB / 128 MiB |
| `agent.max_iterations`, `agent.token_budget` | Model turns and tokens the app's agent may spend per request | 8 turns and 200,000 tokens / the same |
| `research` (top level) | The scope of `research` and `crawl`; required with either | – |

The gate clamps a value above its ceiling instead of refusing it, and gives
an absent value the ceiling. The `grants:` line of `hub check` shows the
result. A manifest asking for 100 MiB of storage gets:

```text
grants: capabilities {"storage"}, hosts {}, storage 16777216 bytes, agent none
```

The rest of the `agent` block (profile, tools, model needs, triggers,
`AGENT.md` and skills) is in
[AI-SERVICES § The manifest's agent](AI-SERVICES.md#the-manifests-agent).

## Names an app cannot use

- **Reserved last segments.** The last segment of an app id becomes its tool
  namespace, so 23 names are reserved (`RESERVED_NAMES` in App Hub
  `crates/app-contract/src/manifest.rs`), among them `notes`, `weather` and
  `terminal`:

  ```text
  [refused] identity: app id "dev.example.notes" ends in "notes", which is reserved: its tools would be notes.*, a native app's or the host's
  ```

- **`os.*` ids** belong to system apps that ship with the device. The gate
  refuses them (`[refused] identity: os.mything is under os., which is reserved for system apps that ship with the device`),
  and no store installs one. `card-host --system` runs one for development.
- **`profile` and `agent`** are runtime checks, not capabilities. Profile-backed
  `sys.*` helpers read empty without `profile`, and the runtime refuses
  `agent.notify` without `agent`. Neither name is in the list, so no store app holds them.

## Add a capability

A new capability is an App Hub change: the name in `KNOWN_CAPABILITIES`, its
permission and privacy lines, and the service or runtime code that enforces
it, reviewed together. An app cannot invent one. For a new host service, see
[HOST-SERVICES § Add a host service](HOST-SERVICES.md#add-a-host-service).
