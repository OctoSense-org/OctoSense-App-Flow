# Publishing an OctoSense app to the App Hub

English | [简体中文](PUBLISHING.zh-CN.md)

Take a working script app through local checks to a GitHub-attested release
and App Hub review. Finish the manifest, listing, real screenshots and review
answers first; the tag workflow then prepares and verifies the sealed release.
App Hub accepts only GitHub-attested releases, so you need no signing key. See
§3.6 for the current implementation limits.

**Opening an App Hub submission issue is the request to publish.** Include the
repository, version/commit, screenshots and requested permissions. You can open
it before the release is ready; add the tag, workflow result and release pack
when available. A reviewer runs the gate on the exact release and reports
missing items or refusals in the issue. An App Hub admin then approves the
exact candidate, and the Hub publishes its catalog entry. Creating a GitHub
release alone does not submit or approve an app.

Two App Hub documents own the rest:

| You need | Read |
| --- | --- |
| The gate's rules, capability names, reserved ids, manifest and listing fields, signing | App Hub [PUBLISHING.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md) |
| Release provenance, tagging, the submission issue, what reviewers check, common refusals | App Hub [SUBMITTING.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md) |

- Start here when [QUICKSTART](QUICKSTART.md) §1–6 pass: the app runs in
  `card-host`, and you have tested its interactions.
- **HUMAN** marks a checkpoint requiring the person’s authorization: the
  publisher identity and privacy text, the platforms claimed, the
  release tag and the submission. An agent stops, reports and waits.

## 1. What gets published

Only `bundle/`. Everything else in the app repository (`AGENTS.md`, notes,
tools, keys, logs, `.local-state/`, `build/review.json`) stays outside it.

```text
my-app/
  AGENTS.md  README.md  .gitignore        not submitted
  .github/workflows/publish-app.yml       release workflow; outside the bundle
  .gitattributes                         copied by tools/octo new: bundle/** -text, so Git never rewrites the bundle
  build/review.json                      not submitted (hub scan output)
  .local-state/                          not submitted (card-host jail)
  bundle/                                THE SUBMISSION
    manifest.json      id, version, name, integrity, capabilities, hosts
    listing.json       what the store shows
    main.splash        the program (a card app has page.card + kit/ instead)
    assets/icon.svg    the icon the listing names (PNG or SVG, square)
    screenshots/01-main.png   real captures, PNG, 1 to 8, named by the listing
```

`bundle/` holds only file types the gate knows. macOS Finder adds
`.DS_Store` files to folders you open, and the gate refuses them; delete them
before you stamp. The published reference apps keep `PRIVACY.md`, a
`review/` folder and their release workflow beside `bundle/`:
[SUBMITTING §1](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md#1-lay-out-the-repository)
shows that layout.

## 2. The rules the gate enforces

`hub check` is the gate: the same code App Hub runs on your submission. It
prints `<id> <version> — PASSED` or `<id> <version> — REFUSED`, then one line
per finding. A `[refused]` line blocks admission; a `[warning]` line does
not, but the reviewer sees it. The rule-by-rule reference is
App Hub's
[rules the gate enforces](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#rules-the-gate-enforces).
The fixes for the refusals people hit most are in
[Common refusals and how to fix them](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md#common-refusals-and-how-to-fix-them).

The gate does not judge whether the screenshots are real captures of this
app, whether the listing text is true, whether the icon reads at small
sizes, or whether the privacy policy says something true. Reviewers do.

## 3. Step by step

Set these once per shell:

```sh
export HUB=/path/to/hub                # tools/octo doctor prints it
export APP=~/apps/my-app               # the app repository
export B="$APP/bundle"
```

### 3.1 Finalize the manifest

Edit `$B/manifest.json`:

- `id`: final. Its last segment is not a reserved name
  ([QUICKSTART §3](QUICKSTART.md#3-create-an-app)).
- `version`: new for every submission (`0.1.0`, then `0.1.1`, …). The gate
  refuses a version already in the catalog, and the release tag carries the
  same number.
- `capabilities`: only what the implemented app uses ([CAPABILITIES](CAPABILITIES.md)),
  and only families that serve store apps on your platforms
  ([HOST-API-FAMILIES](HOST-API-FAMILIES.md)).
- `network.hosts`: every host the program names, bare (`api.example.com`).
- Leave `integrity` to `hub stamp`.

App Hub's [The manifest](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#the-manifest)
lists every field.

### 3.2 Finalize the listing

Edit **every** value in `$B/listing.json`. The template's publisher name,
`example.com` URLs and description are placeholders. The gate accepts them, a
reviewer does not, and `tools/octo check` prints a note while they remain.

- `platforms`: only the platforms you ran the app on (**HUMAN** confirms). A
  `card-host` run on a Mac is `macos`. `tools/octo new` wrote the ones you
  passed with `--platform`; remove any you did not test.
- `category`, `age_rating` and the other fields take the values in App Hub's
  [The listing](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#the-listing).
- `publisher.privacy_policy_url`: an HTTPS URL that exists (**HUMAN**: the
  publisher owns this text). If the bundle ships `tools.json`, the app has an
  agent; say so in the listing and the privacy text.
- The icon: replace the starter identity with this app's own object following
  App Hub's [approved OctoSense format](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/ICONS.md#design-and-export-recommendations).
  Use a 64-point square master, central 66% foreground and no baked platform
  corners or outer shadow. Inspect 64/40/24 px and Android/macOS/iOS frames,
  then verify the target shell; a gate pass alone does not check the design.

The listing is part of the attested release: changing its text later takes a
new version.

### 3.3 Capture real screenshots

Run the unsigned app, bring it to the state you want to show by real input,
capture it, look at the PNG, and quit:

```sh
tools/octo run "$B" --port 8141 --hidden --detach
curl -s "127.0.0.1:8141/click?x=150&y=140&wait=1"      # focus the input
curl -s "127.0.0.1:8141/t?t=Call%20the%20dentist&wait=1"
curl -s "127.0.0.1:8141/click?x=366&y=140&wait=1"      # press Add
tools/octo shot 8141 "$B/screenshots/01-main.png"
curl -s 127.0.0.1:8141/quit
```

`shot` prints `wrote …/01-main.png (824x1784, … bytes). Look at it before you
ship it.` It waits for the app's widgets and a settled frame, then saves
`GET /g?raw=1`. A plain `curl -s "127.0.0.1:8141/g?raw=1" -o out.png` saves
whatever frame is current, which can be half drawn. The capture is at the
window's pixel size: 412x892 points at 2x on a Retina Mac.

- Capture the editable bundle: `card-host` refuses a sealed release.
- Name up to 8 screenshots in `listing.json`.
- Never ship an error frame, an empty first frame, a mock-up, or an image
  redrawn from `/snap`.

### 3.4 Stamp and check

```sh
tools/octo check "$B"
# the same by hand:
"$HUB" stamp "$B"
"$HUB" check "$B" --allow-unsigned
```

On the template-built app with its screenshot:

```text
my-notes 0.1.0 — PASSED
  [warning] publisher-signature: unsigned: accountability rests on the hub alone
  grants: capabilities {"storage"}, hosts {}, storage 16777216 bytes, agent none
```

The same app before `screenshots/01-main.png` existed (exit status 1):

```text
my-notes 0.1.0 — REFUSED
  [warning] publisher-signature: unsigned: accountability rests on the hub alone
  [refused] listing: screenshots/01-main.png is named by the listing but is not in the bundle
  grants: capabilities {"storage"}, hosts {}, storage 16777216 bytes, agent none
hub: the bundle was refused
```

The recorded output above is unchanged. Current Hub prints `declarations:`
for usage metadata; compare it with what the app visibly does. Every admitted
app gets private storage, even without `storage`. Its default store ceiling
is 16 MiB; `storage.max_bytes` can request less. This does not grant access
to another app's data or host files.

To check the version against the published catalog, add
`--catalog <App Hub checkout>/catalog-v2.json` to either command. A version
that is already published is refused:

```text
  [refused] version: version 0.1.0 of org.octosense.samples.githubnotes is already published; publish a new version
```

`tools/octo check` restamps an unsigned bundle before it checks, so it passes
even when the digest you committed is stale. Run it as the last step before
every source commit. The tag workflow prepares and verifies the sealed release
pack separately (§3.7); a source check alone is not publisher-proof verification.

### 3.5 Answer the review questions

```sh
mkdir -p "$APP/build"
"$HUB" scan "$B" --packet "$APP/build/review.json"
```

```text
wrote the review packet to …/build/review.json
no --reviewer given; the packet holds 7 questions for one
```

The packet holds the manifest, the listing, the grants, the program, any
agent files and the questions. It holds no screenshots, so attach them to the
issue yourself. There are seven questions, and an eighth about the agent
files when the bundle ships `tools.json`, `AGENT.md` or skills. Answer each one in writing,
for example in `$APP/review/ANSWERS.md`; the reviewer asks the same ones
([SUBMITTING §8](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md#8-what-reviewers-check)).
Answer the questions on the editable source.

<a id="36-publisher-key--human"></a>

### 3.6 GitHub publisher identity — HUMAN

Every app proves its publisher with its public GitHub repository and a GitHub
Actions attestation: App Hub accepts only GitHub-attested releases. You do not
generate `publisher.key` or add a signing secret to the repository. Review the
publisher details and the workflow before releasing under your account.

**Availability:** this path requires app contract 1.8.0 and
`publisher-github-v1`. Two real GitHub releases passed attestation and the native
Store's install, verified-launch, update, withdrawal and tamper checks
([acceptance receipt](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/reviews/github-publisher-v1/acceptance.json)).
Those Store checks used an isolated test catalog; the fixture has no Hub
submission or admission.
[Desktop RC4](../README.md#compatible-shell-download) is the current download;
RC1 and RC2 also supported this publisher identity. Public sample installation/update on macOS and isolated
phone-fixture acceptance have separate release evidence; those do not prove
your app's UX or provider effects.
Older hosts refuse this requirement. `publisher-toolchain.json` must name a
reviewed, immutable App Hub revision; the installer refuses a missing or moving pin.

For an existing editable app directory, install the workflow from App Flow:

```sh
tools/octo publish-github "$APP"
```

`tools/octo new` also installs `.github/workflows/publish-app.yml`. The command
only writes that file: it does not push, release, submit or approve the app.
It refuses to overwrite a different workflow unless you explicitly use
`--replace`. No developer signing secret is required; the workflow uses GitHub's
short-lived job token and OIDC permissions for attestation and release creation.

An existing generated workflow keeps its original Hub pin when App Flow is
updated. To refresh it, first preserve any local workflow customizations, then
explicitly run `tools/octo publish-github "$APP" --replace` and review
`git -C "$APP" diff -- .github/workflows/publish-app.yml` before committing.
Replacement writes this generated file in full; it does not merge custom steps.
Do not replace unrelated workflows. The current pin, App Hub `38635915`, admits
HTTP and host-service component imports and shared components under the
declaration-only policy; the older `769e9ee3` publisher does not. ABI requirements,
bundle integrity and GitHub publisher-proof checks still apply.

This pin also includes [App Hub #209](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/209):
ordinary WASI TCP/UDP/DNS imports require `host-api-v1` and
`host_api.required: {"wasm.sockets": 1}`, which `tools/octo wasm build` adds.
RC5 can read the catalog but cannot install or run these socket apps.
[Published desktop RC6](../README.md#compatible-shell-download) provides that API.
A publisher check does not establish that the chosen host supports the app
([Rust sockets](RUST.md#tcp-udp-and-dns)).

CI builds the exact [publisher pin](../tools/publisher-toolchain.json) and runs
[the native CLI regression](../tools/check-publisher-toolchain.py) against real
SDK components. It checks structural admission and publisher preparation,
including missing-ABI, malformed-component and missing-proof refusals. This does
not attest or publish an app, run its guests, or prove shell/device behavior.

Keep the tested, unsigned `bundle/` as source. Review and commit the workflow,
source, real screenshots and `.gitattributes` in the public app repository.
Create and push a **new** `v<manifest.version>` tag for that commit, for example
`v0.1.0` when the manifest says `0.1.0`. Do not move or recreate a released tag.

<a id="37-sign-the-final-bytes--human"></a>

### 3.7 Attest the final bytes in GitHub Actions

The tag-push workflow performs this sequence with a pinned App Hub toolchain:

1. `hub publisher-prepare` checks the bundle, binds the repository name and
   immutable repository/owner IDs, workflow path, tag and commit, and writes
   the canonical manifest outside `bundle/`.
2. GitHub's `actions/attest` attests that canonical manifest. The native
   verifier checks the GitHub-hosted tag-push identity and source commit.
3. `hub publisher-attach` embeds the proof at `integrity.github.attestation`;
   `hub publisher-verify` validates it.
4. `hub publisher-pack` verifies again and produces `app.bundle.pack.json`
   without restamping. The release also contains `octosense-app-manifest.json`
   and `release-receipt.json`.

These stages run in the workflow, not on your machine. An attested bundle is
sealed: do not edit, restamp or strip its proof. `card-host` cannot
run it because it has no publisher-proof verifier. Test the editable source
before release, then test the admitted release in a compatible Store host.
A tag's source archive and its sealed release pack are different artifacts;
checking the source alone does not verify the published proof.

For a routine update, edit and test the source, increment `manifest.version`,
and push a new matching tag from the same repository/owner/workflow identity.
The gate checks continuity. A release receipt records the release inputs and
pack digest; it is not App Hub approval.

### 3.8 Submit — HUMAN

Open a `Submit <app id> <version>` issue on OctoSense-App-Hub to request
publication. Include the repository, version/commit, screenshots, requested
permissions and review answers. The issue can be opened before the release is
ready. Add the release URL, tag, successful workflow run and exact pack/digest
when the workflow succeeds; the Hub needs these verified bytes before admission. Follow App Hub's
[SUBMITTING.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md)
for the current issue fields.

- A GitHub release is not automatic admission to App Hub.
- Do not hand-edit the Hub's catalog, index or admitted artifacts in a pull
  request. Its protected review/publishing workflow admits the exact bundle.
- Until App Hub first publishes the app, post each new release on the same
  issue, as a comment with its tag, full commit SHA and workflow-run link, and
  update the issue title and Version field. After publication, open a new
  issue for each new version.
- An agent may prepare the workflow and draft the issue in
  `build/SUBMISSION.md`. It must not claim a release, review or approval it
  did not observe. Respect the person's authorization for external actions.

### 3.9 What the App Hub does next

A reviewer verifies the publisher proof and bundle, runs the gate and posts
any refusals in the issue. An App Hub admin then approves the exact release,
and the Hub publishes it in its signed catalog, where a compatible host,
such as [RC4](../README.md#compatible-shell-download), can install it. If
changes are needed, release a new version with a new tag and post it as §3.8
describes; never replace old bytes.

## 4. Rehearse the store path locally

Install a release of your app in the desktop shell from a local catalog, to
see what a device does before App Hub publishes the app. The rehearsal runs
the app's host services, which `card-host` cannot. It publishes nothing to App
Hub: you sign the local catalog with your own throwaway trust anchor in place
of App Hub's. Keep the mirror and its keys under `build/`, never in `bundle/`.

A store refuses an unsigned app, so rehearse the release pack that your tag
workflow built (§3.7), not the editable source. The local
catalog uses the legacy format: set `OCTOSENSE_HUB_CATALOG=legacy` and use a
fresh app-data directory, because a library that already cached the v2
catalog refuses a legacy downgrade.

**Unverified for these legacy-catalog commands:** a GitHub-attested release.
RC4's separate administrator-attested catalog rehearsal is in the
[download evidence](../README.md#compatible-shell-download). The commands below
are source-reviewed for an attested release; the recorded results come from a
key-signed test app and an earlier App Hub.

### 4.1 Publish into a local mirror

Unpack the release pack, publish it into a mirror with throwaway catalog keys,
then verify the mirror. `hub publish` needs the publisher as
`github:<repository id>`, plus the exact repository and commit that the
release manifest records in `integrity.github`; the `read` line takes them
from there. A rerun needs fresh directories, because `keygen` refuses an
existing file, `publisher-unpack` needs a new directory and a new anchor
cannot authenticate the old mirror. Remove `$APP/build/keys`,
`$APP/build/rehearsal` and `$APP/build/mirror` (throwaway files only) before
you run this block again:

```bash
M="$APP/build/mirror"; R="$APP/build/rehearsal"; mkdir -p "$M" "$APP/build/keys"
"$HUB" publisher-unpack app.bundle.pack.json --out "$R"   # the pack from your GitHub release
read -r ID REPO COMMIT < <(python3 -c 'import json, sys; g = json.load(open(sys.argv[1]))["integrity"]["github"]; print(g["repository_id"], g["repository"], g["commit"])' "$R/manifest.json")
ANCHOR=$("$HUB" keygen "$APP/build/keys/anchor.key")        # throwaway, never App Hub's
"$HUB" keygen "$APP/build/keys/working.key" >/dev/null
CERT=$("$HUB" certify --anchor "$APP/build/keys/anchor.key" --working "$APP/build/keys/working.key")
"$HUB" publish "$R" --catalog "$M/catalog.json" --key "$APP/build/keys/working.key" \
  --anchor-cert "$CERT" --publisher "github:$ID" \
  --repo "https://github.com/$REPO" --commit "$COMMIT" --out "$M"
"$HUB" verify "$M/catalog.json" --anchor "$ANCHOR"
```

`publish` prints the gate report, then
`published <app id> <version> (catalog sequence 1)`; `verify` prints
`catalog sequence 1 verified, 1 entries`. On macOS, with an earlier App Hub,
the key-signed test app Test Notes (`my-test-notes`) printed these lines.

### 4.2 Install and open the app in the desktop shell

Point the OctoSense desktop shell at the mirror. Clone
[OctoSense](https://github.com/OctoSense-org/OctoSense) into your workspace
and set it up as its [README](https://github.com/OctoSense-org/OctoSense#set-up)
describes. `tools/setup.py` puts pinned copies of Makepad, OctoScript and
OctoScript-Makepad in `OctoSense/.sources/`, with OctoSense's reviewed
patches applied to Makepad, so the shell does not reuse the workspace's
checkouts; `--cache ..` reuses their Git objects. Setup takes under a minute;
a cold `cargo build --release -p octosense` takes 5 to 9 minutes:

```sh
cd <workspace> && git clone https://github.com/OctoSense-org/OctoSense.git
cd OctoSense && python3 tools/setup.py --cache ..
```

```sh
cd <workspace>/OctoSense
OCTOSENSE_HUB_CATALOG=legacy OCTOSENSE_HUB="$M" OCTOSENSE_HUB_ANCHOR="$ANCHOR" \
  OCTOSENSE_HOME="$APP/build/desktop-home" OCTOSENSE_APP_DATA="$APP/build/desktop-apps" \
  MAKEPAD_REMOTE=8399 cargo run --release -p octosense
```

`OCTOSENSE_HOME` and `OCTOSENSE_APP_DATA` keep this test out of your own
`~/.octosense`. Add `MAKEPAD_HIDE_WINDOWS=1` to keep the window off screen
while you drive it over the bridge. Then:

1. Open **App Hub** in the dock. Your app is listed.
2. Click **Get**, then **Install**.
3. Click **Open**. The app runs in its own window, and the log shows
   `card: <app id> running under …`.
4. Drive the app, then end with `curl -s 127.0.0.1:8399/gq`.

Verified on macOS with the key-signed test app: the app's interactions,
storage and requests to its declared host behave as in `card-host`.

- An `icon.svg` drawn with `<text>` showed as a blank tile in the store.
  Draw icons with shapes and paths, as the template does.
- An app that declares `auth` needs a shell built from OctoSense `main`
  or an [RC release](../README.md#compatible-shell-download); use RC4 for
  current GitHub-attested apps. A beta.1 store refuses the capability.
  The shell you build here has no provider registrations until you supply
  them, and they never go in the app. Either set the build variables, such as
  `OCTOSENSE_GITHUB_CLIENT_ID`, when `cargo` compiles the shell
  ([configure a release](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.md#configure-a-release-maintainers)), or write
  `$OCTOSENSE_APP_DATA/.host/oauth/clients.json` (here
  `$APP/build/desktop-apps/.host/oauth/clients.json`), which replaces the
  compiled set ([advanced operator override](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.md#advanced-operator-override)).
  Live use with the real providers is largely unverified
  ([CAPABILITIES § Limits](CAPABILITIES.md#limits)).
- This is a rehearsal with your own trust anchor. A stock build trusts only
  App Hub's anchor.

### 4.3 Optional: install with the standalone store

App Hub's standalone `appstore` installs from the same mirror without the
shell, but it cannot open apps: only the shell's Card runner runs an
installed app.

`octosense-appstore-app` keeps App Hub's `text-input-state-query` feature
on, so it builds only against OctoSense's patched Makepad. On plain Makepad it
stops with `no variant … TextInputStateQuery`. Keep your working workspace
plain, because `tools/setup-native.py --check` refuses a patched Makepad
tree, and build the store in a second workspace:

1. Lay out a second workspace as in
   [QUICKSTART §1](QUICKSTART.md#1-prerequisites).
2. Apply OctoSense's Makepad patches to its `makepad/` in the order that
   `runtime-patches.lock.json` lists them: its `patch` first, then each
   `stacked` entry. With the OctoSense checkout from §4.2:

   ```sh
   cd <second-workspace>
   python3 - <workspace>/OctoSense <<'EOF'
   import json, subprocess, sys
   octosense = sys.argv[1]
   lock = json.load(open(f"{octosense}/runtime-patches.lock.json"))["makepad"]
   for patch in [lock["patch"]] + [s["patch"] for s in lock["stacked"]]:
       subprocess.run(["git", "-C", "makepad", "apply", f"{octosense}/{patch}"], check=True)
   EOF
   ```

3. Build the store in that workspace's App Hub checkout. The `appstore`
   binary lands in its `target/release/`:

   ```sh
   cd <second-workspace>/OctoSense-App-Hub
   cargo build --release -p octosense-appstore-app
   ```

4. Open the mirror in the store:

   ```sh
   OCTOSENSE_HUB_CATALOG=legacy OCTOSENSE_HUB="$M" OCTOSENSE_HUB_ANCHOR="$ANCHOR" OCTOSENSE_APP_DATA="$APP/build/store-data" \
     MAKEPAD_REMOTE=8143 <second-workspace>/OctoSense-App-Hub/target/release/appstore
   ```

Expected result, recorded on macOS with an earlier App Hub and the key-signed
test app: the store lists
"1 app(s) from …/mirror" and shows the listing. Its buttons are labelled in
capitals. **GET** installs the app
(`Installed Test Notes 0.1.0 — 1 capability(ies)`) and unpacks the bundle
under `store-data/my-test-notes/bundle`; **OPEN** does not show the app.

## 5. Human checkpoints

| Checkpoint | Why an agent stops |
| --- | --- |
| GitHub publisher identity and release workflow (3.6, 3.7) | The release binds the public repository, owner, workflow, tag and commit; the person authorizes publication under that identity. |
| Publisher name, support contact, privacy policy text (3.2) | Legal and personal statements only the publisher can make. |
| Platforms claimed (3.2) | A platform claim must match a run that a person did or recorded; an agent cannot vouch for one. |
| Tagging the release (3.6) | The tag names the exact bytes reviewers check; it never moves. |
| Opening the submission issue (3.8) | It acts under the publisher's name. |
| Approving a submission or merging in OctoSense-App-Hub | Only an App Hub admin approves a submission, and only App Hub's maintainers merge. |

## 6. Checklist (copy, then run top to bottom)

`tools/octo package-help` prints a shorter version; this one adds the
`--hidden`, `.DS_Store` and release-proof checks.

```text
[ ] tools/octo doctor                                   -> hub and card-host [ok]
[ ] manifest.json: id final (last segment not reserved), version NEW, capabilities minimal, every host declared
[ ] listing.json: no placeholders; category/platforms/age_rating valid; privacy URL HTTPS and real (HUMAN)
[ ] distinct app icon in the OctoSense family format at the listing path; central 66% safe area; no baked corners/shadow; 64/40/24 px and platform-frame review (App Hub docs/ICONS.md)
[ ] tools/octo run "$B" --port 8141 --hidden --detach   -> "admitted" line
[ ] every interaction driven natively (click/type/tap) and its effect observed (screenshot or /snap or jail file)
[ ] screenshots captured from the unsigned bundle with tools/octo shot, each opened and looked at; listed in listing.json
[ ] curl -s 127.0.0.1:8141/quit                         -> {"ok":1}
[ ] find "$B" -name .DS_Store -delete                    -> only known file types in bundle/
[ ] tools/octo check "$B"                               -> "— PASSED" (only the unsigned warning)
[ ] tools/octo check "$B" --catalog <App Hub catalog-v2.json>   -> no version or continuity refusal
[ ] mkdir -p "$APP/build"; hub scan "$B" --packet "$APP/build/review.json"   -> 7 questions answered in writing (8 with tools.json, AGENT.md or skills)
[ ] git -C "$APP" check-attr text -- "$B/manifest.json"   -> "text: unset" (QUICKSTART §3)
[ ] git status: only app sources and reviewed workflow; no secrets, .local-state or build/
[ ] tools/octo publish-github "$APP" -> reviewed .github/workflows/publish-app.yml; no signing key
[ ] HUMAN: commit tested source/workflow, then push a NEW tag v<manifest.version>
[ ] GitHub workflow succeeds; publisher-verify and publisher-pack pass on the attested release
[ ] release pack, canonical manifest and receipt exist; compatible-host installation separately verified or marked pending
[ ] HUMAN: submission issue requests publication; attach repo/version/commit, screenshots and permissions (may open earlier)
[ ] Add the successful workflow and exact release pack to that issue; until first publication, post each new release there as a comment and update the issue title and Version field
[ ] Hub checks, admin approval and catalog publication are separate; after publication, each new version gets a new issue
[ ] report: what was verified, on which platform, and what was not
```
