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
Capture + lifecycle for Key Hint.

Rendering lifecycle (reliable across Blender versions) follows the pattern of
the Blender Foundation's ``space_view3d_math_vis`` add-on and Shortcut VUr:

  * we register ONE ``SpaceView3D`` ``POST_PIXEL`` draw handler for the
    ``WINDOW`` region;
  * a module-level ``bpy.app.timers`` loop calls ``area.tag_redraw()`` on the
    3D areas roughly every 0.1 s - this is what actually drives the draw
    handler to re-run, and it does NOT depend on a modal operator receiving
    events (a key reason the earlier build showed nothing);
  * an optional PASS_THROUGH modal operator reads which modifier key is held
    (to append the matching shortcut group).  Even if that modal never fires,
    the always-on base table still renders.

GPL note: Shortcut VUr is GPL-3.0; math_vis is GPL-2.0-or-later.  The
implementation below is written for Key Hint; where an architecture idea is
shared it is referenced above.
"""

import time

import bpy

from . import hints
from . import draw as hud_draw
from .prefs import get_prefs

_STALE_MODIFIER_SECS = 0.6
# How often the always-on overlay redraws (drives the draw handler).
_REDRAW_SECS = 0.1
# Minimum interval between full keymap rescans.
_RESCAN_INTERVAL = 1.0

_redraw_timer = None
_draw_handle = None

# Per-addon running flag + shared state.
_running = False

# Current held modifier attribute-names (from the passive modal, if it runs).
_held = set()
_held_since = 0.0

# Cached scan of current context.
_entries = []
_scan_key = None
_scan_at = 0.0
_mode_title = ""

# Diagnostics.
_modal_count = 0


def is_running():
    return _running


# ---------------------------------------------------------------------------
# Keymap scan ---------------------------------------------------------------
# ---------------------------------------------------------------------------
def _current_ctx(area=None):
    """Return a small namespace we can pass to hints.* helpers.

    hints.* only reads context.area, context.mode / active_object / object,
    context.window_manager.keyconfigs.  bpy.context usually provides all of
    these correctly inside a draw/timer callback.
    """
    return bpy.context


def _scan_if_needed(now, force=False):
    global _entries, _scan_key, _scan_at, _mode_title
    ctx = bpy.context
    area = getattr(ctx, "area", None)
    space_type = getattr(area, "type", None) if area else None
    mode = hints._context_mode(ctx)
    key = (space_type, mode)
    if not force and key == _scan_key and now - _scan_at < _RESCAN_INTERVAL:
        return
    try:
        _entries = hints.collect_entries(ctx)
    except Exception:                       # noqa: BLE001
        _entries = []
    _scan_key = key
    _scan_at = now
    _mode_title = hints.mode_display_name(ctx)


# ---------------------------------------------------------------------------
# Draw handler --------------------------------------------------------------
# ---------------------------------------------------------------------------
def _draw_callback_px():
    """POST_PIXEL draw handler. bpy.context points at the region being drawn."""
    area = getattr(bpy.context, "area", None)
    region = getattr(bpy.context, "region", None)
    if area is None or area.type != "VIEW_3D":
        return
    if region is None:
        return
    if not _running:
        return

    data = snapshot()
    # TEMP DEBUG banner so we can confirm drawing runs and where.
    hud_draw.draw_debug_banner(region)
    hud_draw.draw_hud(area, region, data)


def _redraw_loop():
    """Module timer: keep redrawing 3D areas while running."""
    global _redraw_timer
    if not _running:
        return None                        # stop
    try:
        _scan_if_needed(time.time())
        # Ensure the passive modifier probe is alive (some operators cancel
        # all window modals, which would silently end our probe).
        cls = KeyHintModifierProbe
        if not cls._modal_added:
            for win in bpy.context.window_manager.windows:
                for area in win.screen.areas:
                    if area.type == "VIEW_3D":
                        try:
                            with bpy.context.temp_override(window=win,
                                                           area=area):
                                bpy.ops.key_hint.modifier_probe(
                                    "INVOKE_DEFAULT")
                        except Exception:    # noqa: BLE001
                            pass
                        break
        wm = bpy.context.window_manager
        for win in wm.windows:
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
    global _running, _draw_handle, _redraw_timer, _held
    if _running:
        return True

    try:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback_px, (), "WINDOW", "POST_PIXEL")
    except Exception as exc:                 # noqa: BLE001
        print("[Key Hint] draw handler add failed:", exc)
        _draw_handle = None
        return False

    _held = set()
    _scan_if_needed(time.time(), force=True)

    # Drive redraws with a module timer (guaranteed, no modal dependency).
    try:
        _redraw_timer = bpy.app.timers.register(_redraw_loop)
    except Exception as exc:                 # noqa: BLE001
        print("[Key Hint] redraw timer failed:", exc)
        _redraw_timer = None

    _running = True

    # Refresh all 3D areas once.
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:                        # noqa: BLE001
        pass

    if verbose:
        print("[Key Hint] started")
    return True


def stop(verbose=True):
    global _running, _draw_handle, _redraw_timer, _held, _entries
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
    _held = set()
    _entries = []
    if verbose:
        print("[Key Hint] stopped")


def snapshot():
    """Plain dict describing the current HUD content (for the draw handler)."""
    prefs = get_prefs()
    base, _ = hints.split_base_and_modifier(_entries)
    extra = []
    if _held and (prefs is None or prefs.show_hints):
        extra = hints.entries_for_modifiers(_entries, _held)
    return {
        "running": _running,
        "mode": _mode_title,
        "base": base if (prefs is None or prefs.show_fundamentals) else [],
        "held": [hints_key_name(m) for m in sorted(_held)],
        "held_attrs": sorted(_held),
        "extra": extra,
        "pressed": [],
        "modal_count": _modal_count,
        "prefs": prefs,
    }


def hints_key_name(mod):
    return {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "oskey": "OS"} \
        .get(mod, mod or "")


# ---------------------------------------------------------------------------
# Operators -----------------------------------------------------------------
# ---------------------------------------------------------------------------
class KeyHintCaptureOperator(bpy.types.Operator):
    """Toggle the Key Hint always-on overlay on/off."""
    bl_idname = "key_hint.capture"
    bl_label = "Key Hint"
    bl_description = "Toggle the Key Hint reference HUD overlay"
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
    """Force a full restart and report state (visible in the sidebar)."""
    bl_idname = "key_hint.restart"
    bl_label = "Key Hint Restart / Show Status"
    bl_description = "Restart the Key Hint HUD and report its state"

    def execute(self, context):
        stop(verbose=False)
        ok = start(verbose=True)
        msg = ("[Key Hint] running=%s handler=%s timer=%s entries=%d mode=%r"
               % (ok, bool(_draw_handle), bool(_redraw_timer),
                  len(_entries), _mode_title))
        print(msg)
        try:
            context.window_manager.status_text_set(
                "[Key Hint] " + ("RUNNING entries=%d" % len(_entries)
                                 if ok else "NOT RUNNING"))
        except Exception:                    # noqa: BLE001
            pass
        self.report({"INFO"}, msg)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Passive modal (optional): reads which modifier is currently held ----------
# ---------------------------------------------------------------------------
class KeyHintModifierProbe(bpy.types.Operator):
    """PASS_THROUGH modal that only watches modifier keys.

    Not required for the always-on base table to render; it merely appends
    the matching modifier group while a modifier is held.
    """
    bl_idname = "key_hint.modifier_probe"
    bl_label = "Key Hint Modifier Probe"
    bl_options = {"REGISTER"}

    _timer_handle = None
    _modal_added = False

    @classmethod
    def poll(cls, context):
        return _running

    def _start_probe(self, context):
        cls = self.__class__
        if cls._modal_added:
            return
        if cls._timer_handle is None:
            try:
                cls._timer_handle = context.window_manager.event_timer_add(
                    0.1, window=context.window)
            except Exception:                # noqa: BLE001
                cls._timer_handle = None
        context.window_manager.modal_handler_add(self)
        cls._modal_added = True
        print("[Key Hint] modifier probe modal added")

    def _stop_probe(self, context):
        cls = self.__class__
        if cls._timer_handle is not None:
            try:
                context.window_manager.event_timer_remove(cls._timer_handle)
            except Exception:                # noqa: BLE001
                pass
            cls._timer_handle = None
        cls._modal_added = False

    def invoke(self, context, event):
        global _modal_count
        _modal_count += 1
        if _running:
            self._start_probe(context)
        else:
            self._stop_probe(context)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        global _held, _held_since
        if not _running:
            self._stop_probe(context)
            return {"FINISHED"}

        _modal_count += 1
        evt_type = getattr(event, "type", None)
        value = getattr(event, "value", None)
        flags = set()
        for attr in ("ctrl", "shift", "alt", "oskey"):
            if getattr(event, attr, False):
                flags.add(attr)

        mod = {"LEFT_SHIFT": "shift", "RIGHT_SHIFT": "shift",
               "LEFT_CTRL": "ctrl", "RIGHT_CTRL": "ctrl",
               "LEFT_ALT": "alt", "RIGHT_ALT": "alt",
               "OSKEY": "oskey"}.get(evt_type)
        if mod is not None:
            if value == "PRESS":
                flags.add(mod)
            elif value == "RELEASE":
                flags.discard(mod)
        if flags or mod is not None:
            _held = flags
            _held_since = time.time()
        if _held and (time.time() - _held_since) > _STALE_MODIFIER_SECS:
            _held = set()
        return {"PASS_THROUGH"}

    def cancel(self, context):
        self._stop_probe(context)


def _probe_loop():
    """Keep the modifier probe alive by re-invoking if the add-on runs but the
    modal ended (some operations cancel all window modals)."""
    if not _running:
        return None
    cls = KeyHintModifierProbe
    if not cls._modal_added:
        for win in bpy.data.window_managers:
            for w in win.windows:
                for area in w.screen.areas:
                    if area.type == "VIEW_3D":
                        try:
                            with bpy.context.temp_override(window=w,
                                                           area=area):
                                bpy.ops.key_hint.modifier_probe(
                                    "INVOKE_DEFAULT")
                        except Exception:    # noqa: BLE001
                            pass
                        break
    return 2.0


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
        description="Start / stop the Key Hint reference HUD overlay",
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
    if start(verbose):
        # Also start the optional modifier probe.
        _probe_loop()
        return True
    return False


def stop_capture(verbose=True):
    # Ensure the probe modal is gone.
    cls = KeyHintModifierProbe
    if cls._modal_added:
        try:
            bpy.ops.key_hint.modifier_probe("INVOKE_DEFAULT")
        except Exception:                    # noqa: BLE001
            pass
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
