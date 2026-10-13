# Titled Notes

A small script app in the [narrow shape](../../references/SHAPE.md): notes kept
on the device, and a "Suggest a title" button that asks the host's
`model.complete` once. Its scenarios cover the first screen and the main action
at two sizes, an empty input, a restart, a corrupt store, a title from the
model, the model refusing on budget, no model service at all, a model that
never answers, and a host that has not granted the model (`10-model-not-granted`,
written the way a Rinx mini-app's scenario is: `"host_profile": "rinx"`).

```sh
python3 skills/splash-app-verify/scripts/uitest.py run \
  skills/splash-app-verify/examples/titled-notes/bundle \
  skills/splash-app-verify/examples/titled-notes/tests --out /tmp/uitest-titled --keep-going
```

Recorded on 2026-10-13 (Linux x86_64, 2 cores, Xvfb with Mesa llvmpipe, card-host
built from App Hub `8d3853c` with the Splash runtime Octoscript-Makepad `6cf2d90a`):
all 12 runs pass. After the first launch each takes 0.6–1.1 s, except the "never
answers" scenario, which waits out the app's own 20-second timer. card-host's peak
resident memory was 241–244 MB in every run. With the `not granted` line removed
from `model_message`, `10-model-not-granted` fails, as it should.

`05-corrupt-store` keeps a note after the unreadable file is reported and checks
that the file is still the original. Before the app locked writes, that step
replaced the file with the new note; the scenario failed then and passes now.

## The braced `else` in `on_render`

Change the list to `if notes.len() == 0 { Label{…} } else { for … }` and run the
same scenarios: `01-first-screen` fails at both sizes and `05-corrupt-store`
fails, each with `text "No notes yet." is shown` / `not on screen`. That is the
documented `else for` gotcha in its braced form; see
[SCRIPT-API](../../../../docs/SCRIPT-API.md#gotchas).
