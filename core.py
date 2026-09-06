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
Lifecycle: 3D viewport HUD reference + shared state.

Two surfaces use the same shortcut engine:
  * the sidebar N-panel (panels.py) - native UI, always works;
  * an optional 3D-viewport HUD (draw.py) driven by a module redraw timer.

A module-level bpy.app.timers loop keeps re-scanning the keyconfig and
calling area.tag_redraw() - this does NOT depend on a modal operator receiving
events (a modal is not used here at all), so the HUD reliably refreshes.
"""

import time

import bpy

from . import hints
from . import constants
from . import draw as hud_draw
from .prefs import get_prefs

# How often to rescan keyconfig + redraw the HUD.
_RESCAN_INTERVAL = 1.0
_REDRAW_SECS = 0.1

_running = False

# Cached scan of the current context (mode + bindings).
_mode = "OBJECT"
_bindings = {}
_scan_at = 0.0
_scan_key = None

# Draw handle + redraw timer.
_draw_handle = None
_redraw_timer = None


def is_running():
    return _running


# ---------------------------------------------------------------------------
# Scan / resolution ---------------------------------------------------------
# ---------------------------------------------------------------------------
def _scan_if_needed(force=False):
    global _bindings, _mode, _scan_at, _scan_key
    ctx = bpy.context
    area = getattr(ctx, "area", None)
    space_type = getattr(area, "type", None) if area else None
    mode = hints._context_mode(ctx)
    key = (space_type, mode)
    now = time.time()
    if not force and key == _scan_key and now - _scan_at < _RESCAN_INTERVAL:
        return
    try:
        _bindings = constants.resolve_bindings(ctx, mode)
    except Exception:                       # noqa: BLE001
        _bindings = {}
    _mode = hints.mode_display_name(ctx)
    _scan_key = key
    _scan_at = now


def current_reference():
    """Return (mode, bindings, entries) for the current context."""
    ctx = bpy.context
    mode = hints._context_mode(ctx)
    entries = constants.relevant_shortcuts(mode)
    return _mode, _bindings, entries


# ---------------------------------------------------------------------------
# Draw handler --------------------------------------------------------------
# ---------------------------------------------------------------------------
def _draw_callback_px():
    if not _running:
        return
    area = getattr(bpy.context, "area", None)
    region = getattr(bpy.context, "region", None)
    if area is None or area.type != "VIEW_3D" or region is None:
        return
    prefs = get_prefs()
    if prefs is None:
        return
    mode, bindings, entries = current_reference()
    if not prefs.show_hud:
        return
    hud_draw.draw_hud(region, prefs, mode, bindings, entries)


def _redraw_loop():
    if not _running:
        return None
    try:
        _scan_if_needed()
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:                       # noqa: BLE001
        pass
    return _REDRAW_SECS


# ---------------------------------------------------------------------------
# Lifecycle -----------------------------------------------------------------
# ---------------------------------------------------------------------------
def start(verbose=True):
    global _running, _draw_handle, _redraw_timer
    if _running:
        return True
    _scan_if_needed(force=True)
    try:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback_px, (), "WINDOW", "POST_PIXEL")
    except Exception as exc:                 # noqa: BLE001
        print("[Key Hint] draw handler add failed:", exc)
        _draw_handle = None
    try:
        _redraw_timer = bpy.app.timers.register(_redraw_loop)
    except Exception as exc:                 # noqa: BLE001
        print("[Key Hint] redraw timer failed:", exc)
        _redraw_timer = None
    _running = True
    # Refresh once.
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:                        # noqa: BLE001
        pass
    if verbose:
        print("[Key Hint] started (panel + HUD)")
    return True


def stop(verbose=True):
    global _running, _draw_handle, _redraw_timer
    if not _running:
        return True
    if _draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        except Exception:                    # noqa: BLE001
            pass
        _draw_handle = None
    if _redraw_timer is not None:
        try:
            bpy.app.timers.unregister(_redraw_timer)
        except Exception:                    # noqa: BLE001
            pass
        _redraw_timer = None
    _running = False
    if verbose:
        print("[Key Hint] stopped")


def snapshot():
    mode, bindings, entries = current_reference()
    return {
        "running": _running,
        "mode": mode,
        "entries": len(entries),
        "bindings": bindings,
        "prefs": get_prefs(),
    }


# ---------------------------------------------------------------------------
# Operators -----------------------------------------------------------------
# ---------------------------------------------------------------------------
class KeyHintCaptureOperator(bpy.types.Operator):
    """Toggle the Key Hint reference (panel + HUD) on/off."""
    bl_idname = "key_hint.capture"
    bl_label = "Key Hint"
    bl_description = "Toggle the Key Hint reference overlay"
    bl_options = {"REGISTER"}

    def execute(self, context):
        if _running:
            stop()
        else:
            start()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class KeyHintRestartOperator(bpy.types.Operator):
    """Force a full rescan / restart and report state."""
    bl_idname = "key_hint.restart"
    bl_label = "Key Hint Rescan"
    bl_description = "Re-scan the keymap and report state"

    def execute(self, context):
        stop(verbose=False)
        ok = start(verbose=True)
        mode, bindings, entries = current_reference()
        msg = ("[Key Hint] running=%s mode=%r entries=%d bindings=%d"
               % (ok, mode, len(entries), len(bindings)))
        print(msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# WindowManager enable property ---------------------------------------------
# ---------------------------------------------------------------------------
def register_enable_property():
    if hasattr(bpy.types.WindowManager, "key_hint_enabled"):
        return

    def get_enabled(_self):
        return _running

    def set_enabled(_self, value):
        if value and not _running:
            start()
        elif not value and _running:
            stop()

    bpy.types.WindowManager.key_hint_enabled = bpy.props.BoolProperty(
        name="Key Hint",
        description="Start / stop the Key Hint reference (panel + HUD)",
        get=get_enabled,
        set=set_enabled,
    )


def unregister_enable_property():
    if hasattr(bpy.types.WindowManager, "key_hint_enabled"):
        del bpy.types.WindowManager.key_hint_enabled


# ---------------------------------------------------------------------------
# Auto start ----------------------------------------------------------------
# ---------------------------------------------------------------------------
def start_capture(verbose=True):
    return start(verbose)


def stop_capture(verbose=True):
    return stop(verbose)


def _auto_start_loop():
    if _running:
        return None
    prefs = get_prefs()
    if prefs is not None and not prefs.auto_start:
        return None
    if start_capture(verbose=False):
        return None
    return 1.0


_AUTO_TIMER = None


def register_auto_start():
    global _AUTO_TIMER
    if bpy.app.background:
        return
    if _AUTO_TIMER is not None:
        return
    try:
        _AUTO_TIMER = bpy.app.timers.register(_auto_start_loop)
    except Exception:                        # noqa: BLE001
        _AUTO_TIMER = None


def unregister_auto_start():
    global _AUTO_TIMER
    if _AUTO_TIMER is not None:
        try:
            bpy.app.timers.unregister(_AUTO_TIMER)
        except Exception:                    # noqa: BLE001
            pass
        _AUTO_TIMER = None


@bpy.app.handlers.persistent
def _load_post_handler(_dummy):
    register_auto_start()


def handle_auto_start_change(self, context):
    prefs = get_prefs()
    if prefs is not None and prefs.auto_start:
        register_auto_start()
    else:
        unregister_auto_start()


def register_app_handlers():
    bpy.app.handlers.load_post.append(_load_post_handler)


def unregister_app_handlers():
    if _load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_handler)
