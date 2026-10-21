# Card app template (pointer)

English | [简体中文](README.zh-CN.md)

A **card app** is a `page.card` written in L0, the declarative card language,
with its `page.data.json` and `kit/`; the host converts it to widgets. You
generate it rather than write it: use the
[image-to-card flow](../../flows/image-to-card/FLOW.md) (or the
[Sketch kit flow](../../flows/kits/sketch/FLOW.md) for a kit), then finish it
with the common hand-off in
[flows/README.md](../../flows/README.md#every-flow-follows-the-same-contract);
the bundle carries `page.card` and `kit/` instead of `main.splash`.

App Hub's [`templates/app/`](https://github.com/OctoSense-org/OctoSense-App-Hub/tree/main/templates/app)
is the metadata scaffold for a card bundle: manifest, listing, icon and agent
instructions. It has no entry file (`page.card`) and no screenshot, so the
gate refuses it even after `hub stamp`, with `entry` and `listing` refusals. Add the
flow's `page.card` and `kit/` and a real capture, and replace its placeholder
`platforms` with the platforms you tested. Replace the starter icon with your
own identity following App Hub's [OctoSense icon format](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/ICONS.md#design-and-export-recommendations):
64-point square, central 66% foreground, restrained illustrated object and no
baked platform corners or outer shadow. The card's extracted screen artwork
does not replace this icon-authoring step.

To use a font of your own, put the `.ttf` or `.otf` file in the bundle and
name it in `font_src` with a bundle-relative path, such as
`"font_src": "assets/Body.ttf"`. A bundled font counts toward the 8 MiB
limit, so bundle a subset of a large CJK font. Text the font lacks, such as
Chinese, falls back to LXGW WenKai, Makepad's built-in Chinese font. The built-in
fonts a kit may name are `makepad_widgets:resources/Inter.ttf`,
`makepad_widgets:resources/LXGWWenKaiRegular.ttf` and
`makepad_widgets:resources/LXGWWenKaiBold.ttf`
([App Hub PUBLISHING § Fonts](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#fonts)).
Check the text with `MAKEPAD_SYSTEM_FONTS=0`, so that a system font cannot
hide a missing glyph.

`desktop-v0.1.0-beta.2` predates this font loading: it installs an app with a
bundled font, but its cards do not load the font. For Chinese text there,
build the card from the plain L0 role kit (`Surface`, `TextTitle`,
`TextBody`, …) and set no `font_src`; LXGW WenKai draws the Chinese text.
Font loading in OctoSense desktop 0.1.0-rc.1 is unverified.

For an app with its own logic, state and requests, use the
[script-app template](../script-app/README.md) instead.
