# Host services

English | [简体中文](HOST-SERVICES.zh-CN.md)

Host-held credentials and device authority stay in the shell. An app uses
a **host service** for these operations: Rust code that checks identity,
account scope and consent, and returns the result. This does not prohibit
public network requests through the app's network module.

App Hub owns the dispatcher (`crates/appstore/src/services.rs` in
[OctoSense-App-Hub](https://github.com/OctoSense-org/OctoSense-App-Hub)).
OctoSense owns the services: `crates/shell`, `crates/ai-host`,
`crates/oauth-service` and `apps/*/host-service` in
[OctoSense](https://github.com/OctoSense-org/OctoSense). Paths below are
OctoSense's unless marked.

[OctoSense desktop 0.1.0-rc.1](../README.md#compatible-shell-download) (RC1) and
later also implement Host API v1: version requirements, discovery, signed backend
operations, device consent and script tools, within the platform limits in
App Hub's
[Host API compatibility](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/HOST-API.md#limits).
[Host API v1](HOST-API-V1.md) shows how to use them. `desktop-v0.1.0-beta.2`
has none of them.

## Current source policy and release boundary

Capability names and `network.hosts` are usage disclosures, not permission
gates. [Desktop RC4](../README.md#compatible-shell-download), with App Hub
contract 1.11.0, makes public APIs, the network module and bounded app storage available
without a matching declaration. Keep declarations accurate for users and
reviewers. RC2 and older installed tools do not acquire this behavior from a
documentation update; use matching host, Hub and runtime revisions.

Actual consent remains: device and OS permission, connected-account ownership
and provider scopes, native review of external writes, agent opt-in and
inter-app sharing. Required host API versions, component ABI/import checks,
provenance, exact digests, platform availability and quotas also remain.
Use `runtime.list` and `runtime.describe` to discover implementations; neither
method needs a `runtime` usage declaration in the corrected host. Internal
host profile data and unowned `agent.notify` are not public app APIs.
A plain `card-host` has no device-consent broker and does not expose private
device reads; test those in a compatible shell with `host-api-v1`.


## Which shell serves which service

Both OctoSense shells register every service below in their standard
builds: the desktop (`desktop/`) and Home, the phone shell (`phone/`). They
include `wasm` in current macOS, Windows, Linux, Android and OpenHarmony
source builds (Pulley on OpenHarmony), not iOS. This is build inclusion, not
OpenHarmony device acceptance; RC2 had core modules on macOS/Linux.
`register_host_services` in `crates/shell/src/apps.rs` registers the
app-facing services; `crates/ai-host/src/lib.rs` registers `llm`, `model`
and `octos`. App Hub's `card-host` registers none; it answers only `runtime`
discovery, which App Hub's dispatcher handles itself.

The per-family summary, with platforms and since-versions, is
[HOST-API-FAMILIES](HOST-API-FAMILIES.md).

| Family | Who may call it | Service code |
| --- | --- | --- |
| `mail` | Any admitted app with an authorized Mail account | `apps/mail/host-service` |
| `auth` | Any admitted app. Provider data requires an app-owned connection with approved provider scopes; identity-only and backend sign-in use their own scopes. Family declarations are disclosures. | `crates/oauth-service/src/host.rs`, `host_backend.rs` |
| `github`, `gcalendar` | Admitted apps, through a connection made with `auth`. Since RC1, the save review is the shell's, as for `gmail`. | `crates/oauth-service/src/host_api.rs`; since RC1, also `crates/shell/src/connected_review.rs` |
| `gmail` | Admitted apps, through a connection made with `auth`. The send review is the shell's. | `crates/oauth-service/src/host_inbox.rs`, `crates/shell/src/connected_review.rs` |
| `glance` | Any admitted app | `crates/shell/src/glance.rs` |
| `model` | Any admitted app, within a per-app daily budget | `apps/ai-providers/host-service/src/complete/` |
| `octos` | Admitted apps with an opted-in agent, once the person allows it, where the shell hosts the octos kernel (every platform but iOS) | `crates/ai-host/src/contained.rs` |
| `llm` | System apps only | `apps/ai-providers/host-service` |
| `news` | System apps only | `apps/news/host-service` |
| `calendar` | Calendar (`os.calendar`) only | `apps/calendar/host-service` |
| `photos`, `youtube` | Only the matching system app's `notify` | `crates/shell/src/glance_notice.rs` |
| `wasm` | Admitted apps, in current macOS, Windows, Linux, Android and OpenHarmony source builds (feature `wasm-functions`, formerly `wasm-lab`); RC2 has core modules on macOS/Linux and RC1 did not ([Run your own Rust code](RUST.md)) | `crates/shell/src/wasm_service.rs` |
| `files` | Admitted apps; import/export and `pick_photo` use the app's bounded storage; since RC2, on macOS, Windows and Android, and on Linux with a dialog helper; `share` on Android only | `crates/shell/src/files_service` |
| `audio` | Admitted apps playing files in their own bounded storage, declaring `requires: ["host-api-v1"]`; since RC2, on macOS and Android, in the foreground only | `crates/shell/src/audio_service` |
| `device_calendar` | Admitted apps that declare `requires: ["host-api-v1"]`, after the person's consent and the OS permission; since RC2, on macOS and Android Home | `crates/shell/src/device_calendar` |
| `sheet`, `photo`, `word`, `deck`, `cad`, `light`, `sound`, `design`, `film`, `effect`, `vector`, `pdf` | System apps only: craft engines behind host services ([ADR 0013](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0013-craft-engines-as-pinned-services.md)), shipped in desktop RC2 for the system assistant. App Hub `main` now admits the twelve names as declarable capabilities, but RC2's admission does not know them and no store app is served. | `apps/<engine>/host-service` |

`glance_notice.rs` also answers `<namespace>.notify` for every other system
app without a service of its own, such as Maps and Camera.

No OctoSense shell serves `prompt`, `ledger.read`, `clipboard`, `matrix.*`
or `palpo.*` to an installed app; `maps.*` and `ai-providers.*` belong to
those system apps alone. Rinx, a Matrix client that OctoSense ships as a native
app, serves `octos.*` and `matrix.*` through its own host to bundles a person
imports into it as mini-apps, which is not the App Hub install path. Request
`matrix.*` only for a Rinx mini-app.
`research` and `crawl` describe toolbox use; exact tools need a host offer,
`agent.tools` selection, agent consent and research scope. They are not a
`host.request` family
([AI-SERVICES § The system toolbox](AI-SERVICES.md#the-system-toolbox)).

Some services work only after setup, and not every build has them:

| Service | Needs | Builds |
| --- | --- | --- |
| `auth`, `github`, `gcalendar`, `gmail` | GitHub and Google registrations. Beta.2 reads them only from `<apps root>/.host/oauth/clients.json`, which its operator supplies; RC1 and later builds can compile them in, but the public RC packages, including RC4, include none ([CAPABILITIES § Limits](CAPABILITIES.md#limits)). | RC1 and later builds (on Windows and Linux they cannot approve protected writes), and the desktop-v0.1.0-beta.2 release (macOS, Apple silicon). Not yet: Google sign-in on Android. |
| `auth` with the `backend` provider | The app's backend registration: the `backend` block of the admitted signed bundle ([backend guide](HOST-API-V1.md#4-connect-the-apps-backend)), or, when the bundle declares none, the operator's `<apps root>/.host/oauth/backends.json`. | RC1 and later builds; beta.2 has no backend sign-in. The login uses a host WebView on macOS and on Android 9 or later, and the system browser on Windows and Linux, reachable since RC2's native link openers (a Windows fixture completed a sign-in; Linux untested). Not on iOS. |
| `octos`, `model` | An AI provider the person adds in the AI providers app. | Every standard build; `octos` only where the shell hosts the kernel. |
| `mail` | An account the person signs in to on Mail's sheet. | Every standard build. |

Unverified: most use of the connected-account services against the real
GitHub and Google, and GitHub sign-in on a phone.
[CAPABILITIES § Limits](CAPABILITIES.md#limits) lists what has run, and
OctoSense's
[`crates/oauth-service/README.md`](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.md#current-delivery-boundary)
gives each platform's status, including how it stores credentials.

If no service does what your app needs, [add a host service](#add-a-host-service)
to the shells; do not work around it in the bundle. For what a store app gets
when it requests a capability nobody serves for it, see
[CAPABILITIES](CAPABILITIES.md#capabilities-a-store-app-gains-nothing-from).

## Call a service from an app

An L0 card has no statements, so it declares its calls in a sibling
`bindings.json` rather than calling `host.request` itself. The card side of
that — which names must be seeded, and the three ways it fails closed — is
[L0 cards and host services](L0-CARDS-AND-HOST-SERVICES.md). A script app calls
the service directly:

```splash
host.request("mail.accounts", {}, fn(r){
    if r.is_ok && r.data.len() > 0 {
        ui.address.set_text(r.data[0].address)
    } else {
        ui.note.set_text(r.error)
    }
})
```

- The service name is `<family>.<method>`. Family declarations disclose
  expected use; they do not deny supported public requests. The receiving
  host still checks app identity, account scopes, consent and availability.

- `args` is any value that serializes to JSON; the service receives it as
  JSON.
- The callback runs later, on the UI thread, with `r.is_ok`, `r.data` (the
  service's JSON answer) and `r.error` (a string, when not ok).
- If no service answers the family on this shell, the callback gets
  `no service answers "<family>" on this device` at once. In `card-host`,
  every call answers this.

For argument shapes, time limits and refusals, see
[SCRIPT-API § Host services](SCRIPT-API.md#host-services-hostrequest). For
what each capability gives a script, see
[CAPABILITIES](CAPABILITIES.md#host-services).

## The sheet

Only the person may give some input: a password, an account approval, a send.
A service raises a **sheet** for it: a Splash program the shell draws over the
app, in an isolate of its own, under no app's policy. The app cannot open a
sheet; only a service can (`ServiceHost::open_sheet`).

The sheet calls the same `host.request`, and its calls arrive marked
`from_sheet`. The dispatcher refuses any `<family>.sheet.*` call from an app
before a service sees it. In `card-host` (**✓ run**):

```text
mail.sheet.submit is for the host's sheet, not an app
```

So a service takes a password only from its own sheet. Each opening starts a
fresh program, so a password typed into a cancelled sign-in does not survive.

A sheet appears only over an app in the foreground. A call from a Glance card
in the feed or from an agent's tool cannot raise one, so a service refuses it
with a sentence that tells the person to open the app, such as Mail's
`Signing in needs Mail open: open Mail to add an account.`

A call marked `from_sheet` proves only that the sheet's program made it, not
that the person pressed anything. So a send or save that must come from the
person goes through a native control that checks Makepad's
`trusted_user_input()` on both the press and the click. Gmail's send review
works this way on every build. GitHub and Calendar saves do since RC1, where a
`sheet.save` call gets
`Saving requires a physical activation of the native host review. Script and agent requests cannot approve it.`
On Windows and Linux, no release approves these saves or a Gmail send:
protected writes fail closed. On desktop-v0.1.0-beta.2, the GitHub and Calendar services still
accept `sheet.save` from their sheet without that check.

## Secrets are the host's

An app never collects a password, a PIN or a one-time code, not even to pass
it on. Three rules keep it that way:

- The runtime makes a password field inert in a policed isolate
  ([SCRIPT-API § Gotchas](SCRIPT-API.md#gotchas)).
- The gate refuses a bundle that declares a password or one-time-code field
  (the `secrets` check in
  [PUBLISHING](PUBLISHING.md#2-the-rules-the-gate-enforces)).
- The service that needs a credential asks for it on its own sheet and keeps
  it in the platform's secret store, outside every app's jail.

Mail keeps passwords in the keychain on macOS and iOS. On Android and
elsewhere it keeps one file per account in the host's secrets folder,
`<home>/secrets/os.mail/`, encrypted with an Android Keystore key on Android
and owner-only everywhere (`apps/mail/host-service/src/vault.rs`). The
connected-account services keep provider tokens in Mail's stores on macOS,
iOS and Android, under a namespace of their own. On Windows and Linux they
use the system's credential service (Windows Credential Manager, Secret
Service) and never fall back to a file (`crates/oauth-service/src/host.rs`).

An app's agent never reaches these either: it works in the app's account
folder ([AI-SERVICES](AI-SERVICES.md#where-the-agent-works-storage)).

If your app needs an account on some service, it needs a host service for
that service, not a login form. GitHub and Google already have one
([CAPABILITIES § Use a connected account](CAPABILITIES.md#use-a-connected-account)).
An app with an account system of its own can use the host's backend sign-in.
The bundle declares its backend in the manifest's `backend` block, or the
host's operator registers it
([CAPABILITIES § Sign in to your own backend](CAPABILITIES.md#sign-in-to-your-own-backend)).
[Desktop RC4](../README.md#compatible-shell-download) includes it within
the backend platform limits above; release inclusion does not verify a real
provider or your backend ([App Hub#16](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/16)).

## Mail, the worked example

The Mail system app (`apps/mail/bundle/main.splash`) uses the `mail` family,
with `mail` disclosed for review and account authorization checked by the host:

| Method | Args | Answer (`r.data`) |
| --- | --- | --- |
| `mail.accounts` | – | `[{id, address}]`, the accounts this app may use |
| `mail.add_account` | – | `{id, address}` once the person signs in on Mail's sheet. From a Glance card or a tool, it fails with `Signing in needs Mail open: open Mail to add an account.` |
| `mail.remove_account` | `{account}` | `{}` |
| `mail.folders` | `{account}` | `[{id, name, role}]`, the inbox first |
| `mail.sync` | `{account, folder?}` | `{new, total}` |
| `mail.list` | `{account, folder?, offset?, limit?}` | `{folder, total, messages: [{id, sender, address, subject, preview, time, unread}]}` |
| `mail.message` | `{account, folder?, message}` | `{id, sender, address, subject, body, html, attachments, date, time}` |
| `mail.mark_read` | `{account, folder?, message}` | `{}` |
| `mail.compose` | `{account, to, subject, body, compose_id?, expected_revision?, folder?, message?}` | Since RC2, for admitted apps with an authorized Mail account: a saved draft with its `compose_id`, `revision` and status; no prompt, nothing sent. Keep the id and revision. |
| `mail.compose_status` | `{account, compose_id}` | Since RC2: this app and account's draft with its last attempt and receipt. Read it before retrying an uncertain send. |
| `mail.review_send` | the `mail.compose` fields | Since RC2, for admitted apps with an authorized Mail account, in the foreground: opens the host's native send review; the callback settles after the person's physical press on **Approve & Send** or a cancellation. The review exists on macOS and Android; on Windows and Linux it fails with `Physical Mail send approval is unavailable on this platform`. Real SMTP acceptance is unverified. On RC1 only Mail itself (`os.mail`) could call it; other apps got `Only Mail owns reply drafts`. |
| `mail.send` | the `mail.compose` fields | Since RC2 a compatibility entry that opens the same review as `mail.review_send`; never direct SMTP. On RC1 and beta.2 it always answered `approval_required: use mail.review_send with Mail open, …`, naming a method a store app could not call ([OctoSense #409](https://github.com/OctoSense-org/OctoSense/issues/409)). |
| `mail.notify` | `{title, body, card_id?, priority?}` (title 1–80, body 1–600 characters) | `{card_id, replaced, expires_at}` once Mail's notice card is on the Glance screen, with a notification. Mail's agent calls it as a tool. |
| `mail.sheet.submit` | sign-in fields | sheet only |
| `mail.sheet.cancel` | – | sheet only |

Mail's agent has tools of its own on the same service (`peek`, `draft`,
`propose_reply`, `skip_event`, `publish_card` and others);
`apps/mail/bundle/tools.json` lists them all.

How `mail.add_account` works:

1. The app calls `mail.add_account` and waits.
2. The service raises its sign-in sheet.
3. The person types into the sheet, which calls `mail.sheet.submit`.
4. The service tests the account, puts the password in the platform's
   secret store and the account, without the password, in
   `<host_dir>/mail/accounts.json`.
5. The service closes the sheet (`close_sheet_later`) and answers the app's
   original request with `{id, address}`.

An account is available only to the apps that signed in to it.

## Add a host service

A new service is a change to the shells and to App Hub, not to an app bundle.
Make all four changes together:

1. **Add a capability** for its family in `KNOWN_CAPABILITIES` (App Hub
   `crates/app-contract/src/manifest.rs`, the app contract), with its privacy
   line in `crates/app-policy/src/listing.rs` (`privacy_summary`) and its
   permission line in `crates/app-hub/src/index.rs` (`permissions_summary`).
   A test in `crates/app-hub/src/index.rs` fails when a capability has no
   plain-words line. The list is closed on purpose; adding a name is a
   reviewed App Hub change.
2. **Write the service**, a Rust crate implementing `HostService`
   (`octosense_appstore::services`). This sketch is not compiled; Mail's
   `lib.rs` is the complete, tested reference:

   ```rust
   use octosense_appstore::services::{HostService, Replier, ServiceCall, ServiceHost};

   struct Weather;
   impl HostService for Weather {
       fn family(&self) -> &'static str { "weather" }
       fn call(&mut self, call: ServiceCall, reply: Replier, host: &mut dyn ServiceHost) {
           match call.method() {
               "today" => reply.send(Ok(serde_json::json!({"temp": 21}))),
               other => reply.send(Err(format!("weather has no method {other:?}"))),
           }
       }
   }
   ```

   | Item | What it does |
   | --- | --- |
   | `call.app_id` | The calling app's manifest id. Scope any state per app. |
   | `call.host_dir` | A directory only the host can reach, outside every jail: `<apps root>/.host` in the shells, `<app data>/.host` in `card-host`. |
   | `call.may_prompt` | `false` where no sheet may appear: a Glance card in the feed, an agent's tool call. Answer with a sentence that tells the person to open the app; App Hub refuses the sheet there anyway. |
   | `reply` | May move to a worker thread and `send` later. A `send` after the timeout is dropped. |
   | `host.open_sheet(source)`, `host.close_sheet()` | Raise and drop the sheet. From a worker thread, use `close_sheet_later(app_id)`. Put any method that takes a secret under `sheet.`. |
   | `HostService::timeout` | 60 s by default; the clock stops while the sheet is up. Override it for a slow service: `model` allows 2 × 120 s + 30 s. |

   A service method can also be an app agent's tool. A `tools.json` tool with
   `implemented_by: "host-service"` reaches the service as a normal
   `ServiceCall` from that app, with `may_prompt` false, so one method serves
   the app's screen and its agent
   ([AI-SERVICES § The app's tools](AI-SERVICES.md#the-apps-tools-and-peer-tools)).
   A system app's tool reaches the service of its own namespace directly. A
   store app's tool reaches a method through a `host_method`, and App Hub
   admits only the methods on its reviewed list, so a new method needs an App
   Hub change as well.
3. **Register it in the shells.** Call
   `octosense_appstore::services::register_host_service(Box::new(Weather))` from
   `register_host_services` in `crates/shell/src/apps.rs`. The Card runner
   then pumps the service (`services::pump`). Mail's crate wraps this call
   in `octosense_mail_service::register()`, which `apps.rs` calls.
4. **Test it** in the service crate. Mail's tests run from an OctoSense
   checkout (not run):

   ```sh
   cargo test -p octosense-mail-service
   ```

Apps then declare the capability and call `host.request("weather.today", …)`.
