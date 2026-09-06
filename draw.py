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
  * blf text - blf.size takes (font_id, size) on Blender >= 4.0.
  * Chinese text: load a CJK-capable system font via blf.load() and fall back
    to the built-in font if none is found.

The panel is a small "window" with a title bar (mode + lock icon).  Its title
bar is draggable; core.py owns the drag/lock interaction and reads the title
bar rectangle back through ``hud_title_rect``.
"""

import os

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

_FONT_ID = 0          # built-in (fallback)
_cjk_font_id = None
_cjk_loaded = False

_shader = None
_shader_tried = False

# Hit-test rectangles are exported in *window* pixel coords (origin
# bottom-left of the whole window) so core can compare them directly against
# event.mouse_x / event.mouse_y without depending on a modal's context.region.
# Each rect: (x, y_bottom, w, h).
hud_title_rect = (0.0, 0.0, 0.0, 0.0)
hud_panel_rect = (0.0, 0.0, 0.0, 0.0)
hud_lock_rect = (0.0, 0.0, 0.0, 0.0)
# Region bounds for offset math: (region_x, region_y, region_w, region_h).
hud_region_info = (0, 0, 0, 0)


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


# Candidate CJK-capable font files (Windows / macOS / Linux).
_CJK_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",          # 微软雅黑
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\simhei.ttf",        # 黑体
    r"C:\Windows\Fonts\simsun.ttc",        # 宋体
    "/System/Library/Fonts/PingFang.ttc",  # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]


def _font_id():
    """Return the font id to use (CJK-capable if available)."""
    global _cjk_font_id, _cjk_loaded
    if not _cjk_loaded:
        _cjk_loaded = True
        for path in _CJK_CANDIDATES:
            if os.path.exists(path):
                try:
                    _cjk_font_id = blf.load(path)
                    break
                except Exception:           # noqa: BLE001
                    _cjk_font_id = None
    return _cjk_font_id if _cjk_font_id is not None else _FONT_ID


def reset_font():
    """Re-load the CJK font.  Blender can invalidate the font id when a new
    file/project is opened, which makes every blf text call silently draw
    nothing (only the GPU rectangles remain).  Call this on load_post."""
    global _cjk_font_id, _cjk_loaded
    _cjk_loaded = False
    _cjk_font_id = None


def _set_size(fid, size):
    if bpy.app.version >= (4, 0, 0):
        blf.size(fid, size)
    else:
        try:
            dpi = bpy.context.preferences.system.dpi or 72
            blf.size(fid, size, dpi)
        except Exception:                   # noqa: BLE001
            blf.size(fid, size)


def _tw(fid, text, size):
    _set_size(fid, size)
    try:
        return blf.dimensions(fid, text)[0]
    except Exception:                       # noqa: BLE001
        return 0.0


def _th(fid, text, size):
    _set_size(fid, size)
    try:
        return blf.dimensions(fid, text)[1]
    except Exception:                       # noqa: BLE001
        return 0.0


def _draw_text(fid, x, y, text, color, size):
    try:
        _set_size(fid, size)
        blf.color(fid, *color)
        blf.position(fid, x, y, 0)
        blf.draw(fid, text)
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


def draw_hud(region, prefs, payload):
    """Draw the reference window in the bottom-right corner.

    payload = {
        "title": str,
        "lines": [(combo, label), ...],
        "locked": bool,
    }

    offset_x/offset_y are measured from the *right* and *bottom* edges of the
    region respectively.  The title bar rect (for dragging) is exported to
    ``hud_title_rect`` in region-local pixel coords (x, y, w, h) with y being
    the bottom of the title bar.
    """
    global hud_title_rect, hud_panel_rect, hud_lock_rect, hud_region_info
    if prefs is None or region is None:
        return

    fid = _font_id()
    font = prefs.font_size
    small = max(9, font - 2)
    text_color = tuple(prefs.text_color)
    accent = tuple(prefs.accent_color) if prefs.use_separate_accent \
        else text_color

    mx = float(prefs.offset_x)      # distance from right edge
    my = float(prefs.offset_y)      # distance from bottom edge
    pad = 8.0
    line_h = 14.0 if font < 14 else (font + 4)

    title = payload.get("title", "Key Hint")
    locked = payload.get("locked", False)
    lines = payload.get("lines", [])

    # Title text and lock indicator are separate (no overlap).
    title_text = title
    lock_text = "锁定" if locked else "解锁"

    body = lines

    # Measure width: title + body lines.
    panel_w = _tw(fid, title_text, small)
    lock_w = _tw(fid, lock_text, small) + 10.0
    for combo, label in body:
        panel_w = max(panel_w, _tw(fid, combo + "  " + label, font))
    panel_w += pad * 2 + lock_w

    # Title bar height: measured from the actual title/lock glyph height,
    # plus generous vertical padding so the title text never clips or touches
    # the content below.
    small_h = max(_th(fid, title_text, small), _th(fid, lock_text, small))
    title_h = small_h + 20.0

    usable = region.height - my - 24
    line_px = line_h + 2.0
    # Reserve the title bar in the usable height for the body.
    body_rows = max(0, int((usable - title_h) / line_px))
    body = body[: body_rows]

    total_h = title_h + len(body) * line_px + pad

    # Panel is anchored bottom-right.
    x_right = region.width - mx
    y_bottom = my
    x0 = x_right - panel_w
    y_top = y_bottom + total_h

    # Window-space offsets (region coords are region-local; add region.x/y).
    wx = region.x
    wy = region.y
    hud_region_info = (region.x, region.y, region.width, region.height)
    hud_panel_rect = (wx + x0, wy + y_bottom, panel_w, total_h)

    # Backdrop.
    _draw_rect(region, x0, y_bottom, panel_w, total_h,
               (0.0, 0.0, 0.0, prefs.background_opacity))

    # Title bar (top strip) + export its rect (window coords) for hit-testing.
    title_y = y_top - title_h
    _draw_rect(region, x0, title_y, panel_w, title_h,
               (0.12, 0.16, 0.24, 0.85))
    hud_title_rect = (wx + x0, wy + title_y, panel_w, title_h)

    # Title text (left), vertically centered in the title bar.
    title_ty = title_y + (title_h - small_h) / 2.0
    _draw_text(fid, x0 + pad, title_ty, title_text, accent, small)

    # Lock/unlock button (right end of the title bar).
    lock_x = x0 + panel_w - pad - lock_w
    hud_lock_rect = (wx + lock_x - 4, wy + title_y, lock_w + 8, title_h)
    _draw_rect(region, lock_x - 4, title_y, lock_w + 8, title_h,
               (0.9, 0.7, 0.1, 0.9) if locked else (0.3, 0.5, 0.3, 0.9))
    _draw_text(fid, lock_x, title_ty, lock_text, (0.0, 0.0, 0.0, 1.0), small)

    # Body lines (below the title bar, with a clear gap).
    y = title_y - 8.0
    for combo, label in body:
        _draw_text(fid, x0 + pad, y, combo, text_color, font)
        _draw_text(fid, x0 + pad + panel_w * 0.42, y, label, text_color, font)
        y -= line_px
