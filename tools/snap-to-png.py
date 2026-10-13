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

The artifact labels itself: every PNG carries a permanent bottom band reading
"widget-tree redraw · not host pixels". Screenshots are review evidence in this
repo's flow (docs/PUBLISHING.md), so the honesty label must travel with the
file — not just live in this docstring, the console output and the README.

Text inputs are drawn from the snapshot's display text only (`t`); the raw
value (`val`) is never painted, so a password field shows its `•••` mask.

Usage:
    python3 tools/snap-to-png.py --port 8141 --out shot.png [--width 412] [--height 892]
    python3 tools/snap-to-png.py --port 8141 --out shot.png --note "caption text"

Requires: Pillow (`pip install pillow`). CJK fonts are picked from the usual
Linux/macOS/Windows system paths when available; text falls back to the
default bitmap font.
"""

import argparse
import json
import os
import sys
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
    "/System/Library/Fonts/PingFang.ttc",        # macOS
    "/System/Library/Fonts/STHeiti Light.ttc",   # macOS fallback
    "C:\\Windows\\Fonts\\msyh.ttc",              # Windows
    "C:\\Windows\\Fonts\\simhei.ttf",            # Windows fallback
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

WATERMARK = "widget-tree redraw · not host pixels"
BAND_H = 20  # permanent bottom band; content at or below it is skipped


def load_font(size):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fail(msg):
    """One-line actionable error, like the octo tool family (no tracebacks)."""
    print(f"snap-to-png: {msg}", file=sys.stderr)
    sys.exit(2)


def snap_widgets(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/snap", timeout=10) as r:
            payload = json.loads(r.read())
    except Exception as e:
        fail(f"cannot read /snap from 127.0.0.1:{port} "
             f"({e.__class__.__name__}: {e}) — is card-host running with --remote {port}?")
    if not isinstance(payload, dict) or not isinstance(payload.get("s"), list):
        fail(f"unexpected reply from port {port} (no \"s\" widget list) — "
             f"is a card-host listening on it?")
    return payload["s"]


def fit_text(d, text, font, max_w):
    """Width-based truncation with an ellipsis (never a silent hard cut)."""
    if max_w <= 0:
        return ""
    if d.textlength(text, font=font) <= max_w:
        return text
    while text and d.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…" if text else ""


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
    y_floor = args.height - BAND_H
    if args.note:
        d.text((12, 10), fit_text(d, args.note, f_small, args.width - 24), fill=SECOND, font=f_small)

    drawn = 0
    for w in widgets:
        r = w.get("r") or [0, 0, 0, 0]
        x, y, ww, hh = r
        if ww <= 0 or hh <= 0 or y < y_top or y >= y_floor or x < -4:
            continue
        ty, text = w.get("ty"), (w.get("t") or "").strip()
        if not text and ty != "TextInput":
            continue
        if ty == "Button":
            d.rounded_rectangle([x, y, x + ww, y + hh], radius=10, fill=CARD)
            d.text((x + 6, y + max(2, hh // 2 - 9)), fit_text(d, text, f_body, ww - 12),
                   fill=ACCENT, font=f_body)
        elif ty == "TextInput":
            d.rounded_rectangle([x, y, x + ww, y + hh], radius=10,
                                fill=(255, 255, 255), outline=LINE)
            # The snapshot's `t` is the widget's *display* text
            # (widget_tree.rs: text = display_text()) — for a password input
            # that is the `•` mask. `val` holds the raw text and is never
            # drawn; it serves only as an "is it empty?" flag for the ink.
            filled = bool(str(w.get("val") or "").strip())
            d.text((x + 8, y + max(2, hh // 2 - 9)), fit_text(d, text, f_body, ww - 16),
                   fill=INK if filled else SECOND, font=f_body)
        elif y < y_top + 60 and hh >= 24:
            d.text((x + 4, y), fit_text(d, text, f_title, args.width - x - 8), fill=INK, font=f_title)
        else:
            # Fit to the widget's own rect: a label the host clipped to a
            # narrow strip should not paint its full text here either.
            d.text((x + 4, y), fit_text(d, text, f_body, ww), fill=INK, font=f_body)
        drawn += 1

    # Watermark last, so no content can overpaint it.
    d.rectangle([0, y_floor, args.width, args.height], fill=CARD)
    d.text((8, y_floor + 4), WATERMARK, fill=SECOND, font=f_small)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    img.save(args.out)
    print(f"wrote {args.out} from live /snap of port {args.port} "
          f"({drawn} drawn of {len(widgets)} widgets; {WATERMARK})")


if __name__ == "__main__":
    main()
