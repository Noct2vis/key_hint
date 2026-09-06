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


def _blender_at_least(major, minor, patch=0):
    v = bpy.app.version
    return (v[0], v[1], v[2]) >= (major, minor, patch)


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

# Currently active operation hint (e.g. "G") set by the key watcher, or None.
_active_op = None
_active_op_since = 0.0
# How long an operation hint stays before reverting to base (seconds).
_OP_HINT_TTL = 30.0

# Held modifier set (attribute names: ctrl/shift/alt/oskey).
_held_mods = set()

# Drag state (mouse dragging the HUD title bar).
_dragging = False
_drag_dx = 0.0
_drag_dy = 0.0


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


def _current_mode_key():
    ctx = bpy.context
    area = getattr(ctx, "area", None)
    space_type = getattr(area, "type", None) if area else None
    return space_type, hints._context_mode(ctx)


def _build_payload():
    """Build the HUD payload: title + lines (combo, label)."""
    _, mode_key = _current_mode_key()
    title = constants.base_title_for_mode(mode_key)
    lines = []

    op = _active_op
    if op is not None and (time.time() - _active_op_since) < _OP_HINT_TTL:
        h = constants.operation_hint_for(op, mode_key)
        if h is not None:
            title = h["title"]
            for it in h["items"]:
                combo = it.get("key", "?")
                lines.append((combo, it.get("label", "")))
    elif _held_mods:
        # A modifier is held -> show shortcuts that start with it.
        names = [constants._MOD_NAME[m] for m in
                 ("ctrl", "shift", "alt", "oskey") if m in _held_mods]
        title = " + ".join(names) + " +"
        lines = constants.modifier_hint_lines(mode_key, _held_mods)
    else:
        # Base: mode-aware no-modifier shortcuts.
        lines = constants.base_hint_lines(mode_key)

    return {"title": title, "lines": lines,
            "locked": bool(get_prefs().hud_locked if get_prefs() else False)}


def current_reference():
    """Return (mode, bindings, entries) for the sidebar panel."""
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
    if not prefs.show_hud:
        return
    payload = _build_payload()
    hud_draw.draw_hud(region, prefs, payload)


def _redraw_loop():
    if not _running:
        return None
    try:
        _scan_if_needed()
        _ensure_watch_modal()
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
    _ensure_watch_modal()
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
    global _running, _draw_handle, _redraw_timer, _active_op
    if not _running:
        return True
    _active_op = None
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
# Key watcher + drag modal (PASS_THROUGH) -----------------------------------
# ---------------------------------------------------------------------------
class KeyHintWatchOperator(bpy.types.Operator):
    """Passive watcher: reads key presses (to switch the operation hint) and
    mouse drags on the HUD title bar (to move the window). Never consumes the
    event - it always returns PASS_THROUGH, so Blender keeps working normally.
    """

    bl_idname = "key_hint.watch"
    bl_label = "Key Hint Watcher"
    bl_options = {"REGISTER", "MODAL_PRIORITY"} \
        if _blender_at_least(4, 2, 0) else {"REGISTER"}

    _timer = None
    _added = False

    @classmethod
    def poll(cls, context):
        return _running

    def invoke(self, context, event):
        cls = self.__class__
        if not _running:
            return {"CANCELLED"}
        if cls._timer is None:
            try:
                cls._timer = context.window_manager.event_timer_add(
                    0.1, window=context.window)
            except Exception:               # noqa: BLE001
                cls._timer = None
        context.window_manager.modal_handler_add(self)
        cls._added = True
        return {"RUNNING_MODAL"}

    def _stop(self, context):
        cls = self.__class__
        if cls._timer is not None:
            try:
                context.window_manager.event_timer_remove(cls._timer)
            except Exception:               # noqa: BLE001
                pass
            cls._timer = None
        cls._added = False

    def modal(self, context, event):
        global _active_op, _active_op_since, _dragging, _drag_dx, _drag_dy
        global _held_mods

        if not _running:
            self._stop(context)
            return {"FINISHED"}

        evt_type = getattr(event, "type", None)
        value = getattr(event, "value", None)
        ctrl = getattr(event, "ctrl", False)
        shift = getattr(event, "shift", False)
        alt = getattr(event, "alt", False)
        oskey = getattr(event, "oskey", False)

        # --- held modifiers (from event flags + explicit key events) -----
        if evt_type in ("LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT",
                        "LEFT_ALT", "RIGHT_ALT", "OSKEY"):
            mod = {"LEFT_CTRL": "ctrl", "RIGHT_CTRL": "ctrl",
                   "LEFT_SHIFT": "shift", "RIGHT_SHIFT": "shift",
                   "LEFT_ALT": "alt", "RIGHT_ALT": "alt",
                   "OSKEY": "oskey"}.get(evt_type)
            if mod:
                if value == "PRESS":
                    _held_mods.add(mod)
                elif value == "RELEASE":
                    _held_mods.discard(mod)
        else:
            # Rebuild from event flags (authoritative for non-modifier events).
            flags = set()
            if ctrl:
                flags.add("ctrl")
            if shift:
                flags.add("shift")
            if alt:
                flags.add("alt")
            if oskey:
                flags.add("oskey")
            _held_mods = flags

        # --- key: switch operation hint ---------------------------------
        if value == "PRESS" and evt_type in constants.TRIGGER_KEYS:
            # Ctrl+R / Ctrl+B are special combined triggers.
            if ctrl and evt_type in ("R", "B"):
                _active_op = "CTRL_" + evt_type
                _active_op_since = time.time()
            elif evt_type in ("G", "R", "S", "E", "K", "I"):
                _active_op = evt_type
                _active_op_since = time.time()
        elif value == "PRESS" and evt_type in ("ESC", "RIGHTMOUSE",
                                               "LEFTMOUSE", "RET",
                                               "NUMPAD_ENTER"):
            # Confirm/cancel returns to base hints.
            _active_op = None

        # Expire stale op hint.
        if _active_op is not None and \
                (time.time() - _active_op_since) > _OP_HINT_TTL:
            _active_op = None

        # --- mouse: drag title bar / click lock icon ---------------------
        prefs = get_prefs()
        self._handle_mouse(context, event, prefs)

        return {"PASS_THROUGH"}

    def _handle_mouse(self, context, event, prefs):
        global _dragging, _drag_dx, _drag_dy
        if prefs is None:
            return
        x = getattr(event, "mouse_region_x", None)
        y = getattr(event, "mouse_region_y", None)
        if x is None or y is None:
            return

        evt_type = getattr(event, "type", None)
        value = getattr(event, "value", None)
        region = getattr(context, "region", None)
        if region is None:
            return

        # region-local y with origin at BOTTOM (same as draw).
        y_bottom_up = region.height - y

        if evt_type == "LEFTMOUSE" and value == "PRESS":
            # 1) Lock/unlock icon (right end of the title bar)?
            lx, ly, lw, lh = hud_draw.hud_lock_rect
            if lw > 0 and lh > 0 and lx <= x <= lx + lw and \
                    ly <= y_bottom_up <= ly + lh:
                prefs.hud_locked = not prefs.hud_locked
                return
            # 2) Drag title bar (only when unlocked).
            if not prefs.hud_locked:
                tx, ty, tw, th = hud_draw.hud_title_rect
                if tw > 0 and th > 0 and tx <= x <= tx + tw and \
                        ty <= y_bottom_up <= ty + th:
                    _dragging = True
                    _drag_dx = x - tx
                    _drag_dy = y_bottom_up - ty
        elif evt_type == "LEFTMOUSE" and value == "RELEASE":
            _dragging = False
        elif evt_type == "MOUSEMOVE" and _dragging and not prefs.hud_locked:
            tx, ty, tw, th = hud_draw.hud_title_rect
            px, py, pw, ph = hud_draw.hud_panel_rect
            if tw <= 0 or pw <= 0:
                return
            new_tx = x - _drag_dx
            new_ty = y_bottom_up - _drag_dy
            title_to_bottom = ty - py
            new_py = new_ty - title_to_bottom
            new_px = new_tx - (tx - px)
            prefs.offset_x = max(0, int(region.width - (new_px + pw)))
            prefs.offset_y = max(0, int(new_py))

    def cancel(self, context):
        self._stop(context)


def _ensure_watch_modal():
    if not _running:
        return
    cls = KeyHintWatchOperator
    if cls._added:
        return
    for wm in bpy.data.window_managers:
        for win in wm.windows:
            screen = getattr(win, "screen", None)
            if screen is None:
                continue
            area = next((a for a in screen.areas if a.type == "VIEW_3D"), None)
            if area is None:
                continue
            try:
                with bpy.context.temp_override(window=win, screen=screen,
                                               area=area):
                    bpy.ops.key_hint.watch("INVOKE_DEFAULT")
            except Exception:               # noqa: BLE001
                pass
            return


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
    if _load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_handler)


def unregister_app_handlers():
    if _load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_handler)
