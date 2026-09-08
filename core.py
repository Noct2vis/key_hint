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
Lifecycle: 3D viewport HUD + shared state.

Two surfaces read the SAME two tables:
  * database B (full real bindings, rebuilt at the three refresh points) and
  * shown set A (the rows you actually keep showing),
both exposed through runtime.py.  The HUD payload is the A∩B subset that
matches the current context (mode tags × selection × held modifier × whether an
operation key like G/R/S is running).  A module-level bpy.app.timers loop keeps
rebuilding the payload and tagging areas for redraw, so the HUD tracks the user.
"""

import time

import bpy

from . import hints
from . import engine
from . import runtime
from . import constants
from . import store
from . import draw as hud_draw
from .prefs import get_prefs


def _blender_at_least(major, minor, patch=0):
    v = bpy.app.version
    return (v[0], v[1], v[2]) >= (major, minor, patch)


# How often to rescan keyconfig + redraw the HUD.
_RESCAN_INTERVAL = 1.0
_REDRAW_SECS = 0.3

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
_OP_HINT_TTL = 8.0

# Held modifier set (attribute names: ctrl/shift/alt/oskey).
_held_mods = set()

# Drag state (mouse dragging the HUD title bar).
_dragging = False
_drag_dx = 0.0
_drag_dy = 0.0

# Timestamp of the last event the watch modal actually received; used to
# detect a dead modal (Blender can silently drop it) and re-arm it.
_last_modal_evt_ts = 0.0


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


def _current_mode():
    """Best-effort current mode string (e.g. 'OBJECT', 'EDIT_MESH')."""
    try:
        return hints._context_mode(bpy.context)
    except Exception:                        # noqa: BLE001
        return "OBJECT"


def _mode_caption(mode):
    """Short Chinese caption for the HUD title based on the current mode."""
    mode = (mode or "").upper()
    if mode.startswith("EDIT_"):
        return "编辑模式"
    caption = {
        "OBJECT": "物体模式",
        "SCULPT": "雕刻模式",
        "POSE": "姿态模式",
        "VERTEX_PAINT": "顶点绘制",
        "WEIGHT_PAINT": "权重绘制",
        "TEXTURE_PAINT": "纹理绘制",
        "PARTICLE": "粒子模式",
    }
    return caption.get(mode, "快捷键")


_MOD_ATTR_DISPLAY = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt",
                     "oskey": "OS"}

# operation trigger (as tracked by the watch modal) -> its modal keymap name.
_OP_MODAL_MAP = {
    "G": "Transform Modal Map",
    "R": "Transform Modal Map",
    "S": "Transform Modal Map",
    "E": "Transform Modal Map",
    "CTRL_R": "Loop Cut Modal Map",
    "CTRL_B": "Bevel Modal Map",
    "K": "Knife Tool Modal Map",
}

_OP_TITLES = {
    "G": "移动（G）", "R": "旋转（R）", "S": "缩放（S）",
    "E": "挤出（E）", "I": "内插面（I）",
    "CTRL_R": "环切（Ctrl+R）", "CTRL_B": "倒角（Ctrl+B）",
    "K": "切刀（K）",
}


def _modal_map_lines(keymap_name):
    """Read the current follow-up sub-keys of a modal keymap from the keyconfig
    (so nothing is invented - only real modal bindings are shown).  Returns a
    list of (combo, label) or [] if the keymap / items can't be found."""
    if not keymap_name:
        return []
    try:
        wm = bpy.context.window_manager
        kc = getattr(wm.keyconfigs, "active", None) or wm.keyconfigs.get("Blender")
        if kc is None:
            return []
        for km in kc.keymaps:
            if getattr(km, "name", "") != keymap_name:
                continue
            rows = []
            for it in km.keymap_items:
                if not getattr(it, "active", True):
                    continue
                if getattr(it, "map_type", None) not in ("KEYBOARD",):
                    continue
                if getattr(it, "value", None) not in ("PRESS", "ANY"):
                    continue
                combo = hints.key_display_name(getattr(it, "type", None))
                rows.append((combo, getattr(it, "name", "") or ""))
            return rows
    except Exception:                        # noqa: BLE001
        return []
    return []


def _selection_present():
    """当前是否有选中的物体/点线面(供 engine 的 selected 语义使用)."""
    try:
        mode = hints._context_mode(bpy.context)
        if mode and mode != "OBJECT":
            obj = bpy.context.active_object
            if obj is not None:
                data = getattr(obj, "data", None)
                if data is not None and hasattr(data, "total_vert_sel"):
                    return bool(getattr(data, "total_vert_sel", 0)
                                or getattr(data, "total_edge_sel", 0)
                                or getattr(data, "total_face_sel", 0))
        return len(bpy.context.selected_objects) > 0
    except Exception:                        # noqa: BLE001
        return False


def _active_tags():
    ctx = bpy.context
    area = getattr(ctx, "area", None)
    st = getattr(area, "type", "VIEW_3D") if area else "VIEW_3D"
    mode = hints._context_mode(ctx)
    return engine.active_tags(mode, st)


def _build_payload():
    """Build the HUD payload from 显示表 A ∩ 数据库 B under the current context.

    Everything is under key detection (watch modal):
      1. an operation key is running (G/R/S/E/I/…) -> read that operation's
         modal sub-keys (live from keyconfig, GUI-only);
      2. a modifier is held (Shift/Ctrl/Alt) -> only shown A∩B entries for the
         current mode that carry that modifier;
      3. otherwise -> the shown A∩B entries for the current mode with no
         modifier (base group).
    Mode tags + real selection state gate which rows count.
    """
    tags = _active_tags()
    sel = _selection_present()
    title = ""
    lines = []

    op = _active_op
    if op is not None and (time.time() - _active_op_since) < _OP_HINT_TTL:
        ov = _modal_map_lines(_OP_MODAL_MAP.get(op, ""))
        if ov:
            title = _OP_TITLES.get(op, "操作")
            lines = ov
    if not lines and _held_mods:
        recs = runtime.query_shown(tags, sel, held=set(_held_mods),
                                   parent=None)
        names = [name for attr, name in _MOD_ATTR_DISPLAY.items()
                 if attr in _held_mods]
        title = " + ".join(names) + " +"
        lines = [(engine.combo_text(r.get("mods"), r.get("key")),
                  r.get("name", "") or r.get("op", "")) for r in recs]
    if not lines:
        recs = runtime.query_shown(tags, sel, held=set(), parent=None)
        title = "%s · 基础" % _mode_caption(hints._context_mode(bpy.context))
        lines = [(engine.combo_text(r.get("mods"), r.get("key")),
                  r.get("name", "") or r.get("op", "")) for r in recs]

    return {"title": title, "lines": lines,
            "locked": bool(get_prefs().hud_locked if get_prefs() else False)}


def current_reference():
    """Return (mode, bindings, entry_count) for status reports."""
    ctx = bpy.context
    mode = hints._context_mode(ctx)
    try:
        shown = runtime.shown_records()
    except Exception:                        # noqa: BLE001
        shown = []
    return mode, {}, len(shown)


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
        # Dead-modal watchdog: if the watch modal was registered but has not
        # seen any event for a while, Blender dropped it - reset the flag so
        # _ensure_watch_modal() re-invokes it.
        if KeyHintWatchOperator._added and \
                (time.time() - _last_modal_evt_ts) > 0.6:
            KeyHintWatchOperator._added = False
            KeyHintWatchOperator._timer = None
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
        global _held_mods, _last_modal_evt_ts

        if not _running:
            self._stop(context)
            return {"FINISHED"}

        _last_modal_evt_ts = time.time()

        evt_type = getattr(event, "type", None)
        value = getattr(event, "value", None)

        # --- held modifiers ----------------------------------------------
        # Rebuild from the event's boolean flags on EVERY event (including the
        # 0.1s TIMER). Isolated modifier key-down events are NOT dispatched to
        # a PASS_THROUGH modal, so tracking them via their own PRESS/RELEASE is
        # unreliable; the boolean flags, however, are set on every event and
        # reflect the physical state, so the group flips on press and reverts
        # on release within one timer tick. (Same approach as Screencast Keys.)
        _held_mods = set()
        if getattr(event, "ctrl", False):
            _held_mods.add("ctrl")
        if getattr(event, "shift", False):
            _held_mods.add("shift")
        if getattr(event, "alt", False):
            _held_mods.add("alt")
        if getattr(event, "oskey", False):
            _held_mods.add("oskey")
        if evt_type == "WINDOW_DEACTIVATE":
            _held_mods.clear()

        # --- operation hint (fires the moment the operation key is pressed) --
        ctrl = getattr(event, "ctrl", False)
        if value == "PRESS":
            # Combined modal tools first: Ctrl+R loop-cut, Ctrl+B bevel.
            if ctrl and evt_type in ("R", "B"):
                _active_op = "CTRL_" + evt_type
                _active_op_since = time.time()
            elif evt_type in ("G", "R", "S", "E", "K", "I"):
                _active_op = evt_type
                _active_op_since = time.time()
            elif evt_type in ("ESC", "RIGHTMOUSE", "LEFTMOUSE", "RET",
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
        evt_type = getattr(event, "type", None)
        value = getattr(event, "value", None)

        # Rects are exported in WINDOW coords; compare directly against the
        # window mouse position (no region math that can go wrong).
        mx = getattr(event, "mouse_x", None)
        my = getattr(event, "mouse_y", None)
        if mx is None or my is None:
            return

        if evt_type == "LEFTMOUSE" and value == "PRESS":
            # 1) Lock/unlock button?
            lx, ly, lw, lh = hud_draw.hud_lock_rect
            if lw > 0 and lh > 0 and lx <= mx <= lx + lw and \
                    ly <= my <= ly + lh:
                prefs.hud_locked = not prefs.hud_locked
                return
            # 2) Drag title bar (only when unlocked).
            if not prefs.hud_locked:
                tx, ty, tw, th = hud_draw.hud_title_rect
                if tw > 0 and th > 0 and tx <= mx <= tx + tw and \
                        ty <= my <= ty + th:
                    _dragging = True
                    _drag_dx = mx - tx
                    _drag_dy = my - ty
        elif evt_type == "LEFTMOUSE" and value == "RELEASE":
            _dragging = False
        elif evt_type == "MOUSEMOVE" and _dragging and not prefs.hud_locked:
            tx, ty, tw, th = hud_draw.hud_title_rect
            px, py, pw, ph = hud_draw.hud_panel_rect
            rx, ry, rw, rh = hud_draw.hud_region_info
            if tw <= 0 or pw <= 0 or rw <= 0:
                return
            new_tx = mx - _drag_dx          # window coords
            new_ty = my - _drag_dy
            title_to_bottom = ty - py
            new_py = new_ty - title_to_bottom
            new_px = new_tx - (tx - px)
            # Convert back to region-local for the anchor offsets.
            local_px = new_px - rx
            local_py = new_py - ry
            prefs.offset_x = max(0, int(rw - (local_px + pw)))
            prefs.offset_y = max(0, int(local_py))

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
    # A new/opened file clears Blender's modal operators but our class flags
    # still say the watcher is running. Reset them and re-arm, and force a
    # rescan because the mode/keymap context is now the new file's.
    KeyHintWatchOperator._added = False
    KeyHintWatchOperator._timer = None
    # Opening a project can invalidate the loaded CJK font id (text disappears,
    # only the GPU rects remain); reload it.
    hud_draw.reset_font()
    _scan_if_needed(force=True)
    register_auto_start()
    _ensure_watch_modal()


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
