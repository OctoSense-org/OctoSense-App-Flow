# Flow: image to card

The contract every flow follows is in [flows/README.md](../README.md).
[README.md](README.md) explains each stage in depth.

## Use when

- You have, or will generate, **one image containing 8–12 related UX screens**
  of one service journey (an "atlas"), and you want native Makepad cards,
  independently owned service cards and a click-driven flow.
- You have **a single screen**: use the same library through its per-design
  route (see [Single screen](#single-screen)).

Do not use it for a text brief with no image (use
[script-app](../script-app/FLOW.md)) or for a Sketch kit (use
[kits/sketch](../kits/sketch/FLOW.md)).

## Inputs

| Input | Where it goes | Notes |
| --- | --- | --- |
| Project directory | `$FLOW_PROJECT` (for example `examples/<name>/`) | Owns every file below |
| Flow manifest | `$FLOW_PROJECT/image-to-appcard-flow.json` | Start from [examples/flow.template.json](examples/flow.template.json) |
| Exact submitted prompt | `source/prompt.txt` | Start from [examples/atlas-prompt.md](examples/atlas-prompt.md) |
| Original generated atlas | `source/atlas.png` | Original bytes; never upscaled or edited |
| Generator facts | manifest `generation.provider`, `generation.model` | The actual generator; omit `model` if unknown |
| Per-scene reviewed files | `cards/<design-id>/contract.json`, `mapped.json`, `semantic-map.json`, `service-actions.json` | Authored and reviewed; the flow never invents them |
| Service logic | `service/`, `wizard/*.mjs` (the manifest's `browser_modules`) | Reducer and bindings you write; not inferred from pixels |
| Fonts and artwork | `fonts/`, `artwork/` (manifest `artwork.root`) | Only assets you may redistribute |

## Prerequisites

- macOS with Xcode command-line tools (Apple Vision OCR in `observe`).
- Python 3.12 with the image library's environment:

  ```sh
  python3.12 -m venv flows/image-lib/.venv
  flows/image-lib/.venv/bin/pip install -r flows/image-lib/requirements.txt
  ```

- Node (service and browser checks).
- The shared native runtime beside this repository: `python3 tools/setup-native.py`
  (see [NATIVE-WORKSPACE.md](../../docs/NATIVE-WORKSPACE.md)).
- For native capture only: release Makepad Studio, its bridge and the artwork
  server, started as in [REPRODUCE.md](../core/REPRODUCE.md).

Check, from the repository root:

```sh
export BEAUTY_PYTHON="$PWD/flows/image-lib/.venv/bin/python"
export FLOW_PROJECT="$PWD/examples/aircon"     # your project
export FLOW_MANIFEST="$FLOW_PROJECT/image-to-appcard-flow.json"
python3 tools/setup-native.py --check >/dev/null \
  && "$BEAUTY_PYTHON" -c "import numpy, cv2, PIL, fontTools" \
  && xcrun swift --version >/dev/null \
  && node --version \
  && bash tools/image-to-appcard-flow.sh plan --project "$FLOW_PROJECT" --manifest "$FLOW_MANIFEST" >/dev/null \
  && echo "prerequisites: ok"
```

Pass when it prints `prerequisites: ok`. `plan` validates the manifest (8–12
scenes, artboard `[406, 776]`, locales `["en", "cn"]`, relative paths, a
declared generator) and prints each stage's exact argument arrays without
running them.

## Steps

`RUN` below stands for
`bash tools/image-to-appcard-flow.sh run --project "$FLOW_PROJECT" --manifest "$FLOW_MANIFEST"`.
Every `RUN` writes a receipt to `pipeline-output/runs/<id>/run.json`, prints
`{"receipt": ..., "status": ...}` last, and exits nonzero on the first failing
stage. Its pass check is always: exit code 0 and `"status": "completed"`.
`bash tools/image-to-appcard-flow.sh status --project "$FLOW_PROJECT" --manifest "$FLOW_MANIFEST"`
shows the latest receipt and whether its inputs still match.

| # | Command | Pass when | Human? |
| --- | --- | --- | --- |
| 1 | `mkdir -p "$FLOW_PROJECT/source" && cp flows/image-to-card/examples/flow.template.json "$FLOW_MANIFEST"`, then replace every placeholder (id, scenes, cards, checks) | the prerequisites check above passes | |
| 2 | Write `source/prompt.txt` from [atlas-prompt.md](examples/atlas-prompt.md): 8–12 states, one palette and type system, one fixture | the file is the exact text to submit | |
| 3 | Generate the atlas with the image generator; save the original output as `source/atlas.png`; record `generation.provider`, `model`, `requested_size` | the PNG is the untouched output; `plan` exits 0 | **HUMAN**: paid generator |
| 4 | Measure each screen's `[x, y, w, h]` in the atlas and write it as that scene's `crop` | `plan` exits 0 | |
| 5 | `RUN --stages intake` | exit 0; `pipeline-output/intake/` holds crops and letterboxed references | |
| 6 | `RUN --stages prepare` (new project only; refuses existing scene directories) | exit 0; each `cards/<design-id>/` has its reference, prompt and provenance | |
| 7 | Author `cards/<design-id>/contract.json` per scene (see [core/examples/image-contract.json](../core/examples/image-contract.json)), then `RUN --stages observe,measure,map` | exit 0; each scene has `observations.json`, `annotations.json`, `mapped.json` | |
| 8 | Review `observations.json`, `mapped.json`, `semantic-map.json` against the reference using [MAPPING-RULES.md](../image-lib/MAPPING-RULES.md); author `service-actions.json` | every region has a reviewed role; no invented text or data | **HUMAN**: semantic review |
| 9 | `RUN --stages semantic,compile` | exit 0; each scene has `page.card`, `page.data.json`, `kit/`, `mapping.json` | |
| 10 | `RUN --stages extract` (when the manifest declares `cards`) | exit 0; `pipeline-output/service-cards/<card-id>/` per declared card | |
| 11 | Write the reducer and bindings (`service/`, `wizard/service.mjs`, `render.mjs`, `wizard.mjs`) and their tests; declare them in `checks.service-test`; `RUN --stages service-test` | exit 0 | |
| 12a | Native evidence with Studio: `RUN --stages capture --launch`, complete the review packet ([REPRODUCE.md](../core/REPRODUCE.md#generated-image-input)), then `RUN --stages gate` | `gate` exits 0 | **HUMAN**: visual review |
| 12b | Native evidence without Studio: `"$BEAUTY_PYTHON" flows/image-to-card/compare_screens.py --project "$FLOW_PROJECT" --pages <page-images> --out "$FLOW_PROJECT/evidence/screenshots"` | side-by-sides written; read them per [VISUAL-CHECKS.md](VISUAL-CHECKS.md) | **HUMAN**: visual review |
| 13 | `RUN --stages bundle` | exit 0; `wizard/card-bundle/` holds `cards.bundle.json`, `cards.provenance.json`, `card-assets/` | |
| 14 | Optional web delivery: `RUN --stages wasm,integrate --website "$FLOW_SITE"`, then `RUN --stages web-test --website "$FLOW_SITE"` | exit 0 each | |

If a step fails, `RUN` exits nonzero at that stage; fix its input and rerun
with `--stages <that stage>`.

The default `--stages` is `intake,semantic,compile,bundle,service-test`, the
rerun set for an existing project. `run` never reruns `map` over reviewed
files; use a new design id for new measurements.

### Single screen

For one screen, use the image library directly (setup and review packets in
[REPRODUCE.md](../core/REPRODUCE.md#generated-image-input)):

```sh
"$BEAUTY_PYTHON" flows/image-lib/save_reference.py <design-id> /path/to/original.png \
  --provider "<actual generator>" --model "<actual model>"
"$BEAUTY_PYTHON" flows/image-lib/register.py <design-id>
BEAUTY_PYTHON="$BEAUTY_PYTHON" bash tools/beauty-pipeline.sh \
  --ux-image --design <design-id> --stages classify,observe,measure,map
# HUMAN: semantic review of observations/mapped/semantic-map
BEAUTY_PYTHON="$BEAUTY_PYTHON" bash tools/beauty-pipeline.sh \
  --ux-image --design <design-id> --stages compile,capture,gate,gallery --launch
```

The output is `flows/image-lib/<design-id>/page.card`, `page.data.json` and
`kit/`; package it as in the hand-off below with `SCENE=flows/image-lib/<design-id>`.

## Outputs

| Path (under `$FLOW_PROJECT`) | What |
| --- | --- |
| `cards/<design-id>/page.card`, `page.data.json`, `kit/`, `mapping.json` | One native L0 scene per screen, with its source-to-widget map |
| `pipeline-output/intake/` | Hash-bound crops, references and transforms |
| `pipeline-output/service-cards/<card-id>/` | Independently mountable service cards |
| `wizard/card-bundle/` | Scenes plus only their referenced, hashed artwork (`card-assets/<design-id>/assets/`) |
| `wizard/wasm-dist/` | Optional single-threaded Makepad WASM package |
| `pipeline-output/runs/<id>/run.json` | Receipt per run, listing stages not run |

## Hand-off: package as an OctoSense app and publish

**Not yet:** a `package` stage. Package one screen (or one extracted service
card) by hand. An App Hub card bundle holds **one** `page.card`.

```sh
export APP_REPO="/absolute/path/to/my-app"      # outside this repository
export DESIGN="aircon-01"                         # the scene to ship
export SCENE="$FLOW_PROJECT/cards/$DESIGN"        # or pipeline-output/service-cards/<card-id>

# 1. Start the bundle from App Hub's templates/app/bundle (this repository's
#    templates/card-app points there; templates/script-app shows the layout).
mkdir -p "$APP_REPO"
cp -R /path/to/OctoSense-App-Hub/templates/app/bundle "$APP_REPO/bundle"
#    Edit bundle/manifest.json (id, version, name, capabilities) and every
#    placeholder in bundle/listing.json.

# 2. Copy the card, its data and its kit.
cp "$SCENE/page.card" "$SCENE/page.data.json" "$APP_REPO/bundle/"
cp -R "$SCENE/kit" "$APP_REPO/bundle/kit"

# 3. Copy the artwork the card references and make every URL bundle-relative.
cp -R "$FLOW_PROJECT/wizard/card-bundle/card-assets/$DESIGN/assets/." "$APP_REPO/bundle/assets/"
perl -pi -e 's#https?://127\.0\.0\.1:8170/ux-images/[^/"]+/assets/#assets/#g' \
  "$APP_REPO/bundle/page.card" "$APP_REPO/bundle/page.data.json"

# 4. Nothing in the card, data or kit may point outside the bundle.
grep -rE 'https?://|file://|\.\./' "$APP_REPO/bundle/page.card" \
  "$APP_REPO/bundle/page.data.json" "$APP_REPO/bundle/kit"
```

Pass when the `grep` in step 4 prints nothing. (A plain
`grep -rE 'https?://|file://|\.\./' bundle` also lists SVG `xmlns` URLs and the
listing's https support and privacy links, which the gate allows.) The prefix
in step 3 is the manifest's `artwork.source_prefix`; adjust the pattern if you
changed it.

Create a distinct app icon before the hand-off, following App Hub's
[OctoSense icon format](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/ICONS.md#design-and-export-recommendations).
The extracted screen artwork is not automatically a launcher icon: author a
64-point square master, central 66% foreground and one illustrated object,
without baked platform corners or an outer shadow. Replace the starter icon,
declare its path in `listing.json`, and review 64/40/24 px plus platform frames.

Then run steps 2–9 of the
[common hand-off](../README.md#every-flow-follows-the-same-contract), which
sets `HUB_BIN` and `CARD_HOST_BIN`. Step 3 expects only the missing-screenshot
refusal and the unsigned warning. Step 5 captures the screenshot with
`tools/octo shot`, which waits for the card's widgets and a settled frame;
look at the PNG before you use it.

Rerun `hub stamp` after every change to `bundle/`; `card-host` refuses a
bundle whose digest does not match. Test the editable, unsigned bundle:
`card-host` has no publisher verifier, so it refuses a sealed release. Next:

- App Flow's [PUBLISHING.md](../../docs/PUBLISHING.md): the final bundle and
  screenshots.
- App Hub's [SUBMITTING.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.md):
  the GitHub release and the submission issue.
- App Hub's [PUBLISHING.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md):
  every gate rule.

## Limits

- **Logic in Python or JavaScript controllers is not a contained app.** The
  reducer in `service/` and the `wizard/*.mjs` browser controller run outside
  the card. A packaged `page.card` is one static screen with its data; the
  journey's state machine, undo and payments do not travel with it. An app
  whose behavior depends on those controllers must be rewritten for the
  contained runtime (a script app) before it is an OctoSense app.
- **One screen per bundle.** The flow produces 8–12 scenes and many service
  cards; a card bundle ships one `page.card`.
- **Fonts.** Kits name fonts as `self:resources/service/...`, runtime resources
  of the Makepad host. A full Noto Sans SC file (about 10.6 MB) exceeds the
  8 MiB (8.39 MB) bundle limit. The gate accepts one built-in font path,
  `makepad_widgets:resources/Inter.ttf`, and refuses a `font_src` that names
  any other built-in font; App Hub
  [#75](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/75) tracks
  allowing other built-in fonts. In a trial packaging of `examples/aircon`
  scene `aircon-01`, `card-host` rendered the artwork and Latin text
  but drew CJK text as missing glyphs; a bundled font subset referenced as
  `assets/fonts/...` did not change that.
  On a later runtime, OctoScript-Makepad `704a3ad7`, `card-host` loads a
  bundle-relative `font_src` and falls back to LXGW WenKai, Makepad's
  built-in Chinese font; `desktop-v0.1.0-beta.2` does not load a bundled
  font, and font loading in OctoSense desktop 0.1.0-rc.1 is unverified.
  Check text in the screenshot.
- **Artboard.** The native image adapter supports `[406, 776]` only.
- **Evidence.** A passing stage is not visual approval. Studio-backed
  `capture`/`gate` and instrument screenshots are separate evidence; neither
  is an App Hub admission.
