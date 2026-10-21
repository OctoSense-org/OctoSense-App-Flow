# Script app template

English | [简体中文](README.zh-CN.md)

This template is a runnable OctoSense script app, **My Notes**. You type a
note, the app keeps it in its own storage, and a tap removes it.
`tools/octo new <dir> --platform macos` copies this template, sets the id and
name, and writes the platforms into the listing;
`tools/octo run <dir>/bundle` runs it.

```text
script-app/
  README.md        this file (not copied)
  README.zh-CN.md  the Chinese version of this file (not copied)
  AGENTS.md        instructions for a coding agent in the new app's repository (copied)
  CLAUDE.md        imports AGENTS.md for Claude Code (copied)
  GEMINI.md        imports AGENTS.md for Gemini CLI (copied)
  .gitignore       keeps keys, build output and .local-state out of Git (copied)
  .gitattributes   keeps Git from rewriting the bundle's bytes (copied)
  bundle/          the app; the only thing ever submitted (copied)
    manifest.json  id my-notes, version 0.1.0, capability storage
    listing.json   store text: publisher values and part of the description are placeholders
    main.splash    the program
    assets/icon.svg
```

## What it demonstrates

All of these work in `card-host`:

- state in top-level `let`s, loaded by a function scheduled with
  `start_timeout(0.05, …)`;
- `fs.exists`, `fs.read` and `fs.write` in the app's jail (its private data
  directory), with `parse_json` and `to_json`;
- `ui.<id>.text()`, `set_text()` and `render()`;
- an `on_render` list with an empty state, a `ButtonFlat{on_click}` button and
  `GestureView{on_tap}` rows.

The empty state is a separate `if` before the `for`. Do not write
`if … else for …` inside `on_render`: in testing, the empty branch drew
nothing and stale rows stayed on screen.

## What you finish before you publish

The template is incomplete on purpose, so that a copy cannot be published by
accident:

- `listing.json` names `screenshots/01-main.png`, which does not exist. The
  gate refuses the bundle until you capture a real screenshot with
  `tools/octo shot`. Never add a placeholder image.
- The publisher name, support URL and privacy-policy URL are placeholders,
  and so is the description's last sentence ("Replace this with …").
  `tools/octo check` reports them. A person replaces the publisher fields.
- `assets/icon.svg` demonstrates the approved OctoSense family format. Replace
  its identity with this app's own illustrated object: 64-point square master,
  central 66% foreground and restrained ivory/ink materials and accents, with
  no baked platform corners or outer shadow. Review 64/40/24 px and platform
  frames; App Hub's [ICONS.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/ICONS.md) owns the packaging and review rules.
- `platforms` is empty, and the gate refuses an empty list
  (`listing names no platforms`). `tools/octo new` requires `--platform` and
  writes the platforms you pass; repeat the option for each one. Passing a
  platform is a claim, not a test: before you publish, keep only the
  platforms you ran the app on, and have a person confirm the claim. A
  `card-host` run on a Mac tests `macos`, not Android.
- If you change the id, keep its last segment off App Hub's reserved names
  (`notes`, `weather`, `terminal` and others). `tools/octo new` refuses them
  when it creates the app, and the gate refuses them in an id you change
  later.

## Publishing the finished app

`new` also installs `.github/workflows/publish-app.yml` from the harness's
reviewed publishing template; that workflow is outside `bundle/` and is not
shown as a template source file above. For an existing app, run
`tools/octo publish-github <app-directory>`. It does not push or submit anything.

Open an App Hub issue to request publication, with repo/version/commit,
screenshots and permissions. Review/commit tested source and the workflow, then
push a new `v<manifest.version>` tag. GitHub prepares, attests, verifies and packs
the release; App Hub accepts only GitHub-attested releases, so you need no
signing key. Add the successful release to the issue; administrator approval
still controls catalog publication. Until App Hub first publishes the app, post
each new release on the same issue and update the issue title and Version
field; after publication, open a new issue for each new version. Routine updates use new versions/tags under the same
repository/owner/workflow identity.

This path requires `publisher-github-v1` / contract 1.8.0 and a compatible
host: OctoSense desktop 0.1.0-rc.1 installs GitHub-attested apps on macOS.
[PUBLISHING](../../docs/PUBLISHING.md) has the evidence and limits.

Next: [docs/QUICKSTART.md](../../docs/QUICKSTART.md).
