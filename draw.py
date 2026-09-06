# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Key Hint is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation, version 3 of the License.
#
#  Key Hint is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Key Hint.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

"""
HUD renderer.

Draws the Key Hint overlay into a 3D viewport ``WINDOW`` region using
``POST_PIXEL`` drawing.

Design constraint: the *text* is drawn with the ``blf`` API which is stable
across every supported Blender version and never depends on a GPU shader.
The optional rounded backdrop is best-effort GPU and every call is guarded, so
on a platform/driver where it misbehaves the worst that can happen is that the
backdrop is simply not drawn - the readable text is always there and a draw
handler can never raise.
"""

import bpy
import blf
import gpu

_FONT_ID = 0


def _dpi():
    try:
        return bpy.context.preferences.system.dpi or 72
    except Exception:                       # noqa: BLE001
        return 72


def _set_size(size):
    blf.size(_FONT_ID, size, _dpi())


def _measure(text, size):
    _set_size(size)
    return blf.dimensions(_FONT_ID, text)


def _text_width(text, size):
    return _measure(text, size)[0]


def _draw_text(x, y, text, color, size, shadow=True):
    """Draw text; ``x,y`` is the *bottom-left* in region-local pixels."""
    _set_size(size)
    blf.color(_FONT_ID, *color)
    if shadow:
        blf.enable(_FONT_ID, blf.SHADOW)
        blf.shadow_offset(_FONT_ID, 1, -1)
        blf.shadow(_FONT_ID, 3, 0.0, 0.0, 0.0, 0.85)
    blf.position(_FONT_ID, x, y, 0)
    blf.draw(_FONT_ID, text)
    if shadow:
        blf.disable(_FONT_ID, blf.SHADOW)


# ---------------------------------------------------------------------------
# Best-effort GPU rounded rectangle -----------------------------------------
# ---------------------------------------------------------------------------
_shader = None


def _shader_2d():
    global _shader
    if _shader is not None:
        return _shader
    for name in ("2D_UNIFORM_COLOR", "UNIFORM_COLOR"):
        try:
            _shader = gpu.shader.from_builtin(name)
            return _shader
        except Exception:                   # noqa: BLE001
            continue
    return None


def draw_rounded_box(region, x, y, w, h, radius, color):
    """Best-effort filled rounded box in *region-local* pixels.

    ``x,y`` is bottom-left. Converts to clip space (NDC) and draws a
    triangle fan from the rectangle centre. Fully guarded.
    """
    try:
        shader = _shader_2d()
        if shader is None:
            return
        import math
        from gpu_extras.batch import batch_for_shader

        rw, rh = region.width, region.height
        if rw <= 0 or rh <= 0:
            return

        def to_ndc(px, py):
            return (px / rw * 2.0 - 1.0, py / rh * 2.0 - 1.0)

        radius = max(0.0, min(radius, w / 2.0, h / 2.0))
        n = 5  # points per rounded corner

        # Build the rounded-rect outline (CCW), starting bottom-left.
        pts = []
        # helper to push an arc around corner centre (cx, cy)
        def arc(cx, cy, start_ang):
            for i in range(n + 1):
                a = start_ang + math.pi * 0.5 * i / n
                pts.append((cx + radius * math.cos(a),
                            cy + radius * math.sin(a)))

        x0, y0 = x, y
        x1, y1 = x + w, y + h
        # bottom-left corner centre (x0+r, y0+r), arc from pi..pi*1.5
        arc(x0 + radius, y0 + radius, math.pi)
        # bottom-right corner centre (x1-r, y0+r), arc from -pi/2..0
        arc(x1 - radius, y0 + radius, -math.pi / 2)
        # top-right corner centre (x1-r, y1-r), arc 0..pi/2
        arc(x1 - radius, y1 - radius, 0.0)
        # top-left corner centre (x0+r, y1-r), arc pi/2..pi
        arc(x0 + radius, y1 - radius, math.pi / 2)

        cx, cy = to_ndc(x + w / 2.0, y + h / 2.0)
        verts = [(cx, cy)] + [to_ndc(px, py) for (px, py) in pts]
        batch = batch_for_shader(shader, "TRI_FAN", {"pos": verts})
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set("NONE")
    except Exception:                       # noqa: BLE001
        try:
            gpu.state.blend_set("NONE")
        except Exception:                   # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Main entry ---------------------------------------------------------------
# ---------------------------------------------------------------------------
def draw_hud(area, region, data):
    """Render the HUD for a 3D viewport region. ``data`` is core.snapshot().

    ``region.x/region.y`` are window coordinates; for overlay drawing we use
    region-local coordinates (origin bottom-left of the region).
    """
    try:
        _draw_hud_inner(area, region, data)
    except Exception:                       # noqa: BLE001
        # Never let a draw handler raise - it would spam the console.
        pass


def _draw_hud_inner(area, region, data):
    prefs = data.get("prefs")
    if prefs is None:
        return

    held = data.get("held", [])
    pressed = data.get("pressed", [])
    hints_list = data.get("hints", [])
    running = data.get("running", False)

    font = prefs.font_size
    text_color = tuple(prefs.text_color)
    accent = tuple(prefs.accent_color) if prefs.use_separate_accent \
        else text_color

    show_keys = prefs.show_pressed_keys
    show_hints = prefs.show_hints

    # Even when idle (nothing held / pressed), draw a small idle hint so the
    # user gets immediate feedback that the overlay is alive.
    if not show_keys and not show_hints:
        return
    if not (show_keys or (show_hints and bool(held)) or bool(pressed)):
        if not running:
            return

    margin_x = prefs.offset_x
    margin_y = prefs.offset_y
    pad = 8.0
    line_h = _measure("Ag", font)[1] + 8.0

    # ---- Build rows ------------------------------------------------------
    # rows: list of lines.  Each line is a list of "segments":
    #   ("mod", "Ctrl")  -> styled with accent
    #   ("key", "X")     -> plain text color
    #   ("lbl", "Save")  -> action label column (drawn right of the combo)
    rows = []

    if show_keys:
        for entry in pressed:
            segs = [("mod", m) for m in entry["mods"]]
            segs.append(("key", entry["key"]))
            rows.append(segs)
        if held and not rows:
            rows.append([("mod", m) for m in held])
        elif held:
            rows.insert(0, [("mod", m) for m in held])
    elif held:
        rows.append([("mod", m) for m in held])

    if show_hints:
        for combo in hints_list:
            segs = [("mod", m) for m in combo["mods"]]
            segs.append(("key", combo["key"]))
            segs.append(("lbl", combo["label"]))
            rows.append(segs)

    if not rows and running:
        # Idle state: give the user feedback that the HUD is on.
        rows.append([("hint", "Hold Ctrl / Shift / Alt to reveal shortcuts")])

    if not rows:
        return

    def seg_text(seg):
        return seg[1]

    def seg_color(seg):
        if seg[0] == "hint":
            return (*text_color[:3], 0.75)   # dim idle text
        return accent if seg[0] == "mod" else text_color

    def seg_glue(a, b):
        # space between segments inside one row
        return 0.0 if a[0] == "lbl" else max(4.0, font * 0.4)

    # ---- layout in region-local pixels (origin bottom-left) --------------
    # We draw rows bottom-up starting at margin_y.
    label_col = False
    for r in rows:
        if any(s[0] == "lbl" for s in r):
            label_col = True

    # Determine the width of the key-combo column so labels line up.
    combo_w = 0.0
    for r in rows:
        w = 0.0
        for i, seg in enumerate(r):
            if seg[0] == "lbl":
                break
            w += _text_width(seg_text(seg), font)
            if i + 1 < len(r) and r[i + 1][0] != "lbl":
                w += seg_glue(seg, r[i + 1])
        combo_w = max(combo_w, w)

    label_w = max((_text_width(seg_text(s), font)
                   for r in rows for s in r if s[0] == "lbl"),
                  default=0.0)

    content_w = combo_w + label_w
    col_gap = 18.0 if label_col else 0.0

    panel_w = content_w + col_gap + pad * 2
    panel_h = len(rows) * line_h + pad

    panel_x = margin_x
    panel_y = margin_y

    # Optional backdrop (best effort).
    bg = (0.0, 0.0, 0.0, prefs.background_opacity)
    draw_rounded_box(region, panel_x, panel_y, panel_w, panel_h, 6.0, bg)

    # ---- draw text rows bottom-up ----------------------------------------
    row_y = panel_y + pad
    for r in rows:
        cx = panel_x + pad
        for i, seg in enumerate(r):
            if seg[0] == "lbl":
                break
            _draw_text(cx, row_y, seg_text(seg), seg_color(seg), font)
            cx += _text_width(seg_text(seg), font)
            if i + 1 < len(r) and r[i + 1][0] != "lbl":
                cx += seg_glue(seg, r[i + 1])
        # Draw label (if any) after the key combo, right-aligned group.
        lbl_segs = [s for s in r if s[0] == "lbl"]
        if lbl_segs:
            lx = panel_x + pad + combo_w + col_gap
            for s in lbl_segs:
                _draw_text(lx, row_y, seg_text(s), seg_color(s), font)
                lx += _text_width(seg_text(s), font) + 6.0
        row_y += line_h
