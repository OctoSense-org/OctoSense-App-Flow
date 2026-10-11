#!/usr/bin/env python3
"""Render a running script app's `/snap` widget tree to a PNG (no display needed).

On machines without a graphical session (headless CI, WSL2, remote boxes),
`tools/octo shot` cannot grab host pixels — the render backend has no frames
to read back. Review and iteration still need *some* picture of the running
app. This tool fills that gap honestly: it fetches the **live `/snap` widget
tree** from the running card-host and redraws what the tree says — labels,
buttons, text inputs at their real positions with their real text.

This is NOT a screenshot of host pixels. Text, hierarchy, positions and state
come from the running app; the painting itself is neutral. Anything the
virtualized list has scrolled out of the viewport is (correctly) absent, which
also makes the tool useful as a "what is on screen right now" probe.

Usage:
    python3 tools/snap-to-png.py --port 8141 --out shot.png [--width 412] [--height 892]
    python3 tools/snap-to-png.py --port 8141 --out shot.png --note "caption text"

Requires: Pillow (`pip install pillow`). CJK fonts are picked from the usual
system paths when available; text falls back to the default bitmap font.
"""

import argparse
import json
import urllib.request

from PIL import Image, ImageDraw, ImageFont

BG = (250, 248, 244)
INK = (43, 39, 34)
SECOND = (110, 103, 94)
ACCENT = (63, 81, 181)  # neutral accent; apps may theme differently
CARD = (241, 236, 228)
LINE = (223, 216, 205)

FONT_PATHS = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def load_font(size):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fetch(port, path, timeout=10):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def snap_widgets(port):
    return fetch(port, "/snap")["s"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, required=True, help="card-host remote port")
    ap.add_argument("--out", required=True, help="output PNG path")
    ap.add_argument("--width", type=int, default=412, help="canvas width (layout points)")
    ap.add_argument("--height", type=int, default=892, help="canvas height (layout points)")
    ap.add_argument("--note", default="", help="caption drawn under the top bar")
    args = ap.parse_args()

    widgets = [w for w in snap_widgets(args.port)
               if w.get("ty") not in ("Splash",) and "Card host [remote]" not in (w.get("t") or "")]
    widgets.sort(key=lambda w: (w.get("r") or [0, 0])[1])

    img = Image.new("RGB", (args.width, args.height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, args.width, 6], fill=ACCENT)
    f_title = load_font(20)
    f_body = load_font(14)
    f_small = load_font(12)

    y_top = 30
    if args.note:
        d.text((12, 10), args.note, fill=SECOND, font=f_small)

    for w in widgets:
        r = w.get("r") or [0, 0, 0, 0]
        x, y, ww, hh = r
        if ww <= 0 or hh <= 0 or y < y_top or y > args.height or x < -4:
            continue
        ty, text = w.get("ty"), (w.get("t") or "").strip()
        wid = w.get("i")
        if not text and ty != "TextInput":
            continue
        if ty == "Button":
            d.rounded_rectangle([x, y, x + ww, y + hh], radius=10, fill=CARD)
            d.text((x + 6, y + max(2, hh // 2 - 9)), text[:24], fill=ACCENT, font=f_body)
        elif ty == "TextInput":
            d.rounded_rectangle([x, y, x + ww, y + hh], radius=10,
                                fill=(255, 255, 255), outline=LINE)
            val = str(w.get("val") or "")
            shown = val if val else text
            d.text((x + 8, y + max(2, hh // 2 - 9)), shown[:40],
                   fill=INK if val else SECOND, font=f_body)
        elif wid in ("hint",) or text.startswith(("AI", "已", "把", "（")):
            d.text((x + 4, y), text[:60], fill=SECOND, font=f_small)
        elif y < y_top + 60 and hh >= 24:
            d.text((x + 4, y), text[:40], fill=INK, font=f_title)
        else:
            d.text((x + 4, y), text[:60], fill=INK, font=f_body)

    img.save(args.out)
    print(f"wrote {args.out} from live /snap of port {args.port} "
          f"({len(widgets)} widgets; widget-tree redraw, not host pixels)")


if __name__ == "__main__":
    main()
