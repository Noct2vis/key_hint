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
3D viewport HUD (POST_PIXEL) for the shortcut reference.

Rendering follows Blender's own space_view3d_math_vis:
  * draw handler registered on SpaceView3D once;
  * UNIFORM_COLOR shader with region pixel coords (>= 4.0);
  * blf text - NOTE: blf.size takes (font_id, size) on Blender >= 4.0.
"""

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

_FONT_ID = 0
_shader = None
_shader_tried = False


def _shader_2d():
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


def _set_size(size):
    if bpy.app.version >= (4, 0, 0):
        blf.size(_FONT_ID, size)
    else:
        try:
            dpi = bpy.context.preferences.system.dpi or 72
            blf.size(_FONT_ID, size, dpi)
        except Exception:                   # noqa: BLE001
            blf.size(_FONT_ID, size)


def _tw(text, size):
    _set_size(size)
    try:
        return blf.dimensions(_FONT_ID, text)[0]
    except Exception:                       # noqa: BLE001
        return 0.0


def _draw_text(x, y, text, color, size):
    try:
        _set_size(size)
        blf.color(_FONT_ID, *color)
        blf.position(_FONT_ID, x, y, 0)
        blf.draw(_FONT_ID, text)
    except Exception:                       # noqa: BLE001
        pass


def _draw_rect(region, x, y, w, h, color):
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


def draw_hud(region, prefs, mode, bindings, entries):
    """Draw the reference list in the top-left corner of the region."""
    if prefs is None:
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

    lines = [("title", mode)]
    for e in entries[: prefs.max_hints]:
        b = bindings.get(e["id"], {})
        key = b.get("key", e.get("key", "?"))
        mods = b.get("mods", [])
        combo = (" + ".join(mods + [key])) if mods else key
        mark = " *" if b.get("custom") else ""
        lines.append(("line", combo + "  " + (e.get("label") or "") + mark))

    usable = region.height - my - 24
    line_px = line_h + 2.0
    visible = lines[: max(1, int(usable / line_px))]

    panel_w = 0.0
    for kind, text in visible:
        size = small if kind == "title" else font
        panel_w = max(panel_w, _tw(text, size))

    x0 = mx
    y_top = region.height - my
    total_h = len(visible) * line_px + pad * 2
    _draw_rect(region, x0, y_top - total_h, panel_w + pad * 2, total_h,
               (0.0, 0.0, 0.0, prefs.background_opacity))

    y = y_top - pad
    for kind, text in visible:
        size = small if kind == "title" else font
        color = accent if kind == "title" else text_color
        _draw_text(x0 + pad, y - line_h, text, color, size)
        y -= line_px
