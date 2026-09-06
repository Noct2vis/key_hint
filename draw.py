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
HUD renderer (POST_PIXEL).

Rendering approach follows the Blender Foundation's own ``space_view3d_math_vis``
(GPL-2.0-or-later) and the GPL-3.0 Shortcut VUr add-on:

  * the draw handler is registered on ``SpaceView3D`` once, for the ``WINDOW``
    region and ``POST_PIXEL`` pass;
  * inside the callback ``bpy.context`` already points at the region being
    drawn, so we read ``context.area`` / ``context.region`` there (no pointer
    chasing);
  * geometry uses *region pixel coordinates* (origin bottom-left) passed
    straight to the ``UNIFORM_COLOR`` built-in shader on Blender >= 4.0
    (``2D_UNIFORM_COLOR`` before that);
  * text is drawn with ``blf``.

All GPU calls are guarded so a draw handler can never raise.
"""

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

_FONT_ID = 0

_shader = None
_shader_tried = False


def _shader_2d():
    """UNIFORM_COLOR builtin; resolved once. Returns None if unavailable."""
    global _shader, _shader_tried
    if _shader_tried:
        return _shader
    _shader_tried = True
    name = "UNIFORM_COLOR" if bpy.app.version >= (4, 0, 0) \
        else "2D_UNIFORM_COLOR"
    try:
        _shader = gpu.shader.from_builtin(name)
    except Exception:                       # noqa: BLE001
        _shader = None
    return _shader


def _dpi():
    try:
        return bpy.context.preferences.system.dpi or 72
    except Exception:                       # noqa: BLE001
        return 72


def _tw(text, size):
    blf.size(_FONT_ID, size, _dpi())
    try:
        return blf.dimensions(_FONT_ID, text)[0]
    except Exception:                       # noqa: BLE001
        return 0.0


def _draw_text(x, y, text, color, size):
    """blf text; (x, y) is the bottom-left of the text, region pixels."""
    try:
        blf.size(_FONT_ID, size, _dpi())
        blf.color(_FONT_ID, *color)
        blf.position(_FONT_ID, x, y, 0)
        blf.draw(_FONT_ID, text)
    except Exception:                       # noqa: BLE001
        pass


def draw_rect(region, x, y, w, h, color):
    """Filled rectangle in region pixel coords (x,y bottom-left)."""
    shader = _shader_2d()
    if shader is None:
        return
    try:
        verts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
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


def _draw_hud(region, data):
    """Main HUD: mode title + always-on base shortcuts (+ extra when held)."""
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
    line_h = 14.0 if font < 14 else (font + 4)

    mode = data.get("mode") or "Blender"
    base = (data.get("base") or [])[: prefs.max_hints]
    extra = (data.get("extra") or [])[: prefs.max_hints]

    lines = [("title", mode)]
    for e in base:
        lines.append(("line", _combo_text(e["mods"], e["key"]) +
                      "  " + (e["label"] or "")))
    if prefs.show_hints and extra:
        mod_title = " + ".join(
            {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "oskey": "OS"}
            .get(m, m) for m in (data.get("held_attrs") or [])) + " +"
        lines.append(("title", mod_title))
        for e in extra:
            lines.append(("line", _combo_text(e["mods"], e["key"]) +
                          "  " + (e["label"] or "")))

    rw = region.width
    rh = region.height

    # Usable rows per column.
    line_h_px = line_h + 2.0
    rows_per_col = max(1, int((rh - my - 24) / line_h_px))

    # Simple single-column layout from the top-left, wrapping is unnecessary
    # for a compact table; but keep it capped and readable.
    visible = lines[: rows_per_col + 1]

    # Measure width.
    panel_w = 0.0
    for kind, text in visible:
        size = small if kind == "title" else font
        panel_w = max(panel_w, _tw(text, size))

    # Backdrop near top-left.
    x0 = mx
    y_top = rh - my
    total_h = len(visible) * line_h_px + pad * 2
    draw_rect(region, x0, y_top - total_h, panel_w + pad * 2,
              total_h, (0.0, 0.0, 0.0, prefs.background_opacity))

    # Draw each line downward from the top.
    y = y_top - pad
    for kind, text in visible:
        size = small if kind == "title" else font
        color = accent if kind == "title" else text_color
        _draw_text(x0 + pad, y - line_h, text, color, size)
        y -= line_h_px


def _combo_text(mods, key):
    if mods:
        return " + ".join(mods + [key])
    return key


# ---------------------------------------------------------------------------
# Public entry used by core (called from the draw handler).
# ---------------------------------------------------------------------------
def draw_hud(area, region, data):
    try:
        _draw_hud(region, data)
    except Exception:                       # noqa: BLE001
        pass


# TEMP DEBUG banner so we can see where / whether drawing happens at all.
def draw_debug_banner(region):
    try:
        x = 20
        y = region.height - 60
        draw_rect(region, 0, region.height - 90, region.width, 90,
                  (0.9, 0.05, 0.05, 0.85))
        _draw_text(x, y, "KEY HINT drawing works  [region %dx%d]" %
                   (region.width, region.height), (1.0, 1.0, 0.0, 1.0), 30)
    except Exception:                       # noqa: BLE001
        pass
