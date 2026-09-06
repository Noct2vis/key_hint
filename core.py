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
Passive event capture.

Technical note / attribution
----------------------------
Key Hint observes keys the same non-destructive way the well known
"Screencast Keys" add-on (GPL-2.0-or-later, by nutti and contributors) does:

  * a modal operator is added to the window manager
    (``WindowManager.modal_handler_add``);
  * its ``modal()`` method returns ``{'PASS_THROUGH'}`` so every event it
    inspects still reaches the normal keymap handling - Key Hint never eats a
    shortcut;
  * short-interval ``Timer`` events are used to keep the overlay refreshing;
  * text is drawn through a ``POST_PIXEL`` space draw handler.

The implementation below is written from scratch and only borrows the
architecture *idea*; no code is copied.  See the add-on README for the full
credits.
"""

import time

import bpy

from . import hints
from . import draw as hud_draw
from .prefs import get_prefs

# Time in seconds a modifier stays "fresh" if we stop seeing updates.
_STALE_MODIFIER_SECS = 0.6
# How often the overlay refreshes / rescans the keymap.
_TIMER_STEP = 0.15
# Minimum interval between full keymap rescans (they walk many items).
_RESCAN_INTERVAL = 1.0


def _blender_at_least(major, minor, patch=0):
    v = bpy.app.version
    return (v[0], v[1], v[2]) >= (major, minor, patch)


class KeyHintState:
    """Global state shared between the running operator and draw callbacks."""

    def __init__(self):
        self.running = False
        self.handlers = []          # draw handler handles
        self.timers = []            # timer handles
        self.last_event = 0.0

        # Currently held modifier attribute-names, e.g. {"ctrl"}.
        self.held = set()
        self.held_since = 0.0

        # Last pressed non-modifier keys, newest first:
        #   (time, [mod attrs], key_display, event_type)
        self.pressed = []

        # Cached scan of the current context (list of entry dicts) + context
        # signature it was computed for + when.
        self.entries = []
        self.scan_key = None        # (area.type, mode)
        self.scan_at = 0.0
        self.mode_title = ""


def _canonical_modifier(event_type):
    if event_type in ("LEFT_SHIFT", "RIGHT_SHIFT"):
        return "shift"
    if event_type in ("LEFT_CTRL", "RIGHT_CTRL"):
        return "ctrl"
    if event_type in ("LEFT_ALT", "RIGHT_ALT"):
        return "alt"
    if event_type == "OSKEY":
        return "oskey"
    return None


def _event_modifier_flags(event):
    flags = set()
    for attr in ("ctrl", "shift", "alt", "oskey"):
        if getattr(event, attr, False):
            flags.add(attr)
    return flags


# Tap types we do not want to show as "a key was pressed".
_IGNORED_PRESS_TYPES = {
    "NONE", "", "MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "TIMER",
    "WINDOW_DEACTIVATE", "TEXTINPUT",
}


def hints_key_name(mod):
    return {
        "ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "oskey": "OS",
    }.get(mod, mod or "")


class KeyHintCaptureOperator(bpy.types.Operator):
    """Passive modal observer that keeps the HUD alive and refreshed."""

    bl_idname = "key_hint.capture"
    bl_label = "Key Hint"
    bl_description = "Always-on shortcut reference HUD for Key Hint"
    bl_options = {"REGISTER", "MODAL_PRIORITY"} \
        if _blender_at_least(4, 2, 0) else {"REGISTER"}

    state = KeyHintState()

    # --- lifecycle --------------------------------------------------------
    def _start(self, context):
        st = self.__class__.state
        if st.running:
            return
        wm = context.window_manager
        timer = wm.event_timer_add(_TIMER_STEP, window=context.window)
        st.timers.append(timer)
        wm.modal_handler_add(self)
        self._add_draw_handlers(context)
        st.running = True
        st.held = set()
        st.pressed = []
        self._scan_if_needed(context, time.time(), force=True)
        if context.area:
            context.area.tag_redraw()

    def _stop(self, context):
        st = self.__class__.state
        if not st.running:
            return
        wm = context.window_manager
        try:
            wm.status_text_set(None)
        except Exception:                    # noqa: BLE001
            pass
        for t in st.timers:
            try:
                wm.event_timer_remove(t)
            except Exception:       # noqa: BLE001
                pass
        st.timers.clear()
        self._remove_draw_handlers(context)
        st.held.clear()
        st.pressed.clear()
        st.entries = []
        st.running = False
        if context.area:
            context.area.tag_redraw()

    def _add_draw_handlers(self, context):
        st = self.__class__.state
        for area in context.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type == "WINDOW":
                    handle = bpy.types.SpaceView3D.draw_handler_add(
                        _draw_callback_px, (area.as_pointer(),),
                        "WINDOW", "POST_PIXEL")
                    st.handlers.append(handle)

    def _remove_draw_handlers(self, context):
        st = self.__class__.state
        for h in st.handlers:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(h, "WINDOW")
            except Exception:       # noqa: BLE001
                pass
        st.handlers.clear()

    def _scan_if_needed(self, context, now, force=False):
        st = self.__class__.state
        area = getattr(context, "area", None)
        space_type = getattr(area, "type", None) if area else None
        mode = hints._context_mode(context)
        key = (space_type, mode)
        if not force and key == st.scan_key and now - st.scan_at < _RESCAN_INTERVAL:
            return
        try:
            st.entries = hints.collect_entries(context)
        except Exception:           # noqa: BLE001
            st.entries = []
        st.scan_key = key
        st.scan_at = now
        st.mode_title = hints.mode_display_name(context)

    # --- modal body -------------------------------------------------------
    def modal(self, context, event):
        st = self.__class__.state
        if not st.running:
            return {"FINISHED"}

        if event.type == "WINDOW_DEACTIVATE":
            st.held.clear()
            self._schedule_redraw(context)
            return {"PASS_THROUGH"}

        now = time.time()
        flags = _event_modifier_flags(event)
        event_type = getattr(event, "type", None)
        mod = _canonical_modifier(event_type)
        value = getattr(event, "value", None)
        if mod is not None:
            if value == "PRESS":
                flags.add(mod)
            elif value == "RELEASE":
                flags.discard(mod)

        if flags or mod is not None:
            st.held = flags
            st.held_since = now

        if st.held and (now - st.held_since) > _STALE_MODIFIER_SECS:
            st.held = set()

        if mod is None and value == "PRESS" and event_type not in _IGNORED_PRESS_TYPES:
            key_name = hints.key_display_name(event_type)
            st.pressed.insert(0, (now, sorted(st.held), key_name, event_type))
            st.pressed = st.pressed[:6]

        # Periodically keep the reference in sync with mode/tool changes.
        self._scan_if_needed(context, now)
        self._schedule_redraw(context)

        # Status-bar indicator (very visible, no console required).
        try:
            count = len(st.entries)
            wm = context.window_manager
            held_txt = " + ".join(hints_key_name(m) for m in sorted(st.held))
            sub = (" | holding " + held_txt) if held_txt else ""
            wm.status_text_set(
                "[Key Hint] active · entries=%d%s" % (count, sub))
        except Exception:                    # noqa: BLE001
            pass
        return {"PASS_THROUGH"}    

    def _schedule_redraw(self, context):
        screen = getattr(context, "screen", None)
        if screen is None:
            return
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def invoke(self, context, event):
        st = self.__class__.state
        if st.running:
            self._stop(context)
        else:
            self._start(context)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        st = self.__class__.state
        if st.running:
            self._stop(context)
        else:
            self._start(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Public helpers used by the draw module ------------------------------------
# ---------------------------------------------------------------------------
def snapshot():
    """Return a plain dict describing the current HUD content."""
    st = KeyHintCaptureOperator.state
    prefs = get_prefs()

    entries = st.entries
    base, _ = hints.split_base_and_modifier(entries)

    # Which modifier group is currently held (None when idle).
    held_attrs = set(st.held)
    extra = []
    if held_attrs and (prefs is None or prefs.show_hints):
        extra = hints.entries_for_modifiers(entries, held_attrs)

    return {
        "running": st.running,
        "mode": st.mode_title,
        "base": base if (prefs is None or prefs.show_fundamentals) else [],
        "held": [hints_key_name(m) for m in sorted(st.held)],
        "held_attrs": sorted(st.held),
        "extra": extra,
        "pressed": [
            {"mods": [hints_key_name(m) for m in mods],
             "key": key, "event_type": etype}
            for (_t, mods, key, etype) in st.pressed
        ],
        "prefs": prefs,
    }


def register_enable_property():
    if hasattr(bpy.types.WindowManager, "key_hint_enabled"):
        return

    def get_enabled(_self):
        return KeyHintCaptureOperator.state.running

    def set_enabled(_self, value):
        if value and not KeyHintCaptureOperator.state.running:
            start_capture(verbose=True)
        elif (not value) and KeyHintCaptureOperator.state.running:
            stop_capture(verbose=True)

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
# Draw callback -------------------------------------------------------------
# ---------------------------------------------------------------------------
def _draw_callback_px(area_ptr):
    area = _find_area(area_ptr)
    if area is None:
        return
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    if region is None:
        return
    data = snapshot()
    if not data["running"]:
        return
    hud_draw.draw_hud(area, region, data)


def _find_area(area_ptr):
    for wm in bpy.data.window_managers:
        for win in wm.windows:
            for area in win.screen.areas:
                if area.as_pointer() == area_ptr:
                    return area
    return None


# ---------------------------------------------------------------------------
# Public start / stop helpers + auto start ----------------------------------
# ---------------------------------------------------------------------------
def is_running():
    return KeyHintCaptureOperator.state.running


def _find_view3d_override():
    for wm in bpy.data.window_managers:
        for win in wm.windows:
            screen = getattr(win, "screen", None)
            if screen is None:
                continue
            for area in screen.areas:
                if area.type != "VIEW_3D":
                    continue
                region = next((r for r in area.regions if r.type == "WINDOW"),
                              None)
                if region is None:
                    continue
                return {"window": win, "screen": screen,
                        "area": area, "region": region}
    return None


class KeyHintRestartOperator(bpy.types.Operator):
    """Force a full restart of the capture / HUD. Exists so a user who sees
    nothing can restart from the N-panel without touching the Python console.
    It prints a short diagnostic and shows the live state in the status bar."""

    bl_idname = "key_hint.restart"
    bl_label = "Key Hint Restart / Show Status"
    bl_description = "Force restart the Key Hint HUD and report its state"

    def execute(self, context):
        if is_running():
            stop_capture(verbose=True)
        ok = start_capture(verbose=True)
        st = KeyHintCaptureOperator.state
        msg = ("[Key Hint] running=%s handlers=%d timers=%d entries=%d mode=%r"
               % (ok, len(st.handlers), len(st.timers), len(st.entries),
                  st.mode_title))
        print(msg)
        if context.window_manager is not None:
            try:
                context.window_manager.status_text_set(
                    "[Key Hint] " + ("RUNNING entries=%d" % len(st.entries)
                                     if ok else "NOT RUNNING"))
            except Exception:                    # noqa: BLE001
                pass
        self.report({"INFO"}, msg)
        return {"FINISHED"}


def start_capture(verbose=True):
    if is_running():
        return True
    override = _find_view3d_override()
    if override is None:
        if verbose:
            print("[Key Hint] No 3D viewport found - cannot start yet.")
        return False
    try:
        with bpy.context.temp_override(**override):
            bpy.ops.key_hint.capture("INVOKE_DEFAULT")
    except Exception as exc:             # noqa: BLE001
        print("[Key Hint] start failed:", exc)
        return False
    if verbose and is_running():
        print("[Key Hint] capture started")
    return is_running()


def stop_capture(verbose=True):
    if not is_running():
        return True
    override = _find_view3d_override()
    if override is None:
        return False
    try:
        with bpy.context.temp_override(**override):
            bpy.ops.key_hint.capture("INVOKE_DEFAULT")
    except Exception as exc:             # noqa: BLE001
        print("[Key Hint] stop failed:", exc)
        return False
    if verbose and not is_running():
        print("[Key Hint] capture stopped")
    return not is_running()


# --- auto start -----------------------------------------------------------
def _auto_start_loop():
    if is_running():
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
    except Exception:                  # noqa: BLE001
        _AUTO_TIMER = None


def unregister_auto_start():
    global _AUTO_TIMER
    if _AUTO_TIMER is not None:
        try:
            bpy.app.timers.unregister(_AUTO_TIMER)
        except Exception:              # noqa: BLE001
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
