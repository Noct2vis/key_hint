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

Coordinate space: the draw handler uses region-local pixels with the origin
at the *bottom-left* of the region and y growing *upward* (same as ``blf``).

Layout (always-on reference), anchored to the top-left of the region:

    OBJECT MODE
    G   Grab / Move
    R   Rotate
    S   Scale
    CTRL +
    C   Copy          X   Delete   ...

The layout engine fills rows downward and wraps into columns when it would
run past the bottom of the usable area.  Text is drawn with the stable
``blf`` API; the rounded backdrop is best-effort GPU and fully guarded so a
draw handler can never raise.
"""

import bpy
import blf
import gpu

_FONT_ID = 0

# Reserve space below the very top so we do not collide with the gizmo /
# header overlap of the 3D viewport.
_TOP_RESERVE = 24.0


def _dpi():
    try:
        return bpy.context.preferences.system.dpi or 72
    except Exception:                       # noqa: BLE001
        return 72


def _measure(text, size):
    blf.size(_FONT_ID, size, _dpi())
    return blf.dimensions(_FONT_ID, text)


def _tw(text, size):
    return _measure(text, size)[0]


def _draw_text(x, y, text, color, size, shadow=True):
    """Draw text; ``x,y`` is bottom-left, in region-local pixels."""
    blf.size(_FONT_ID, size, _dpi())
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
    """Best-effort filled rounded box in region-local pixels (x,y bottom-left)."""
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
        n = 4
        pts = []

        def arc(cx, cy, start_ang):
            for i in range(n + 1):
                a = start_ang + math.pi * 0.5 * i / n
                pts.append((cx + radius * math.cos(a),
                            cy + radius * math.sin(a)))

        x0, y0 = x, y
        x1, y1 = x + w, y + h
        arc(x0 + radius, y0 + radius, math.pi)
        arc(x1 - radius, y0 + radius, -math.pi / 2)
        arc(x1 - radius, y1 - radius, 0.0)
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
# Entry -> text -------------------------------------------------------------
# ---------------------------------------------------------------------------
def _combo_text(mods, key):
    if mods:
        return " + ".join(mods + [key])
    return key


# ---------------------------------------------------------------------------
# Main entry ---------------------------------------------------------------
# ---------------------------------------------------------------------------
def draw_hud(area, region, data):
    try:
        _draw_hud_inner(area, region, data)
    except Exception:                       # noqa: BLE001
        pass


def _draw_hud_inner(area, region, data):
    prefs = data.get("prefs")
    if prefs is None or not data.get("running"):
        return

    font = prefs.font_size
    small = max(9, font - 2)
    text_color = tuple(prefs.text_color)
    accent = tuple(prefs.accent_color) if prefs.use_separate_accent \
        else text_color

    mx = float(prefs.offset_x)
    my = float(prefs.offset_y)
    pad = 8.0
    line_h = _measure("Ag", font)[1] + 6.0

    mode = data.get("mode") or "Blender"
    base = (data.get("base") or [])[: prefs.max_hints]
    extra = (data.get("extra") or [])[: prefs.max_hints]
    held_attrs = data.get("held_attrs") or []

    # ---- Flatten everything into a single styled line list ---------------
    # Each item: (kind, text)
    #   ("title", text)   accent, small font
    #   ("line", text)    body colour
    lines = [("title", mode)]
    if base:
        for e in base:
            lines.append(("line", _combo_text(e["mods"], e["key"]) +
                          "   " + (e["label"] or "")))
    if prefs.show_hints and extra:
        mod_title = " + ".join(
            {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "oskey": "OS"}
            .get(m, m) for m in held_attrs) + " +"
        lines.append(("title", mod_title))
        for e in extra:
            lines.append(("line", _combo_text(e["mods"], e["key"]) +
                          "   " + (e["label"] or "")))

    # Draw region: reserve the bottom of the panel too, then fill rows from
    # the *top* downward and wrap into columns left -> right.
    usable_h = region.height - _TOP_RESERVE - my
    rows_per_col = max(1, int(usable_h / line_h))
    if rows_per_col <= 1:
        return

    # Split the flattened lines into columns of at most rows_per_col.
    columns = []
    for i in range(0, len(lines), rows_per_col):
        columns.append(lines[i:i + rows_per_col])

    # Lay out each column: measure its width, place text.
    placed = []            # (x, y_bottom, text, size, color)
    col_gap = 26.0
    x = mx
    content_w = 0.0
    for col in columns:
        cw = 0.0
        for kind, text in col:
            size = small if kind == "title" else font
            cw = max(cw, _tw(text, size))
        # Stack the column's lines bottom-up so line 0 is at the top.
        top_px = region.height - _TOP_RESERVE - my
        for kind, text in col:
            size = small if kind == "title" else font
            color = accent if kind == "title" else text_color
            placed.append((x, top_px, text, size, color))
            top_px -= line_h
        x += cw + col_gap
        content_w = max(content_w, x - mx - col_gap + cw)

    # ---- backdrop --------------------------------------------------------
    panel_top = region.height - _TOP_RESERVE - my + line_h
    panel_h = min(usable_h, rows_per_col * line_h + line_h) + pad
    panel_y = panel_top - panel_h
    bg = (0.0, 0.0, 0.0, prefs.background_opacity)
    draw_rounded_box(region, mx - pad, panel_y,
                     content_w + pad * 2, panel_h, 6.0, bg)

    # ---- draw text -------------------------------------------------------
    for (px, py, text, size, color) in placed:
        _draw_text(px, py, text, color, size)
