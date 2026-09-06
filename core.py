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

_MODIFIER_KEY_TYPES = (
    "LEFT_SHIFT", "RIGHT_SHIFT",
    "LEFT_CTRL", "RIGHT_CTRL",
    "LEFT_ALT", "RIGHT_ALT",
    "OSKEY",
)

# Time in seconds a modifier stays "fresh" if we stop seeing updates,
# so the panel does not blink while the user is idle.
_STALE_MODIFIER_SECS = 1.2

# How often the overlay refreshes.
_TIMER_STEP = 0.1


def _blender_at_least(major, minor, patch=0):
    v = bpy.app.version
    return (v[0], v[1], v[2]) >= (major, minor, patch)


class KeyHintState:
    """Global state shared between the running operator and draw callbacks.

    Kept as a small plain object on the operator so add-on re-registration
    (F8 style reload) does not leak stale references.
    """

    def __init__(self):
        self.running = False
        self.handlers = []          # (space, region_type, handle)
        self.timers = []            # timer handles
        self.last_event = 0.0

        # Currently held modifiers (canonical names, e.g. {"ctrl"}).
        self.held = set()
        self.held_since = 0.0

        # Last pressed non-modifier keys, newest first. Each item:
        #   (time, [modifier names], key_display_name)
        self.pressed = []

        # Cached dynamic hints for the current context.
        self.hints = []
        self.hints_as_of = 0.0


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
    """Set of modifiers reported by the event's own boolean flags."""
    flags = set()
    for attr, name in (("ctrl", "ctrl"), ("shift", "shift"),
                       ("alt", "alt"), ("oskey", "oskey")):
        if getattr(event, attr, False):
            flags.add(name)
    return flags


class KeyHintCaptureOperator(bpy.types.Operator):
    """Passive modal observer: watches keys without consuming them."""

    bl_idname = "key_hint.capture"
    bl_label = "Key Hint"
    bl_description = "Capture keys for the Key Hint HUD"
    # On Blender >= 4.2 MODAL_PRIORITY lets a passive observer run cleanly
    # alongside other modal operators; PASS_THROUGH still forwards everything.
    bl_options = {"REGISTER", "MODAL_PRIORITY"} \
        if _blender_at_least(4, 2, 0) else {"REGISTER"}

    state = KeyHintState()

    # --- registration convenience -----------------------------------------
    @classmethod
    def poll(cls, context):
        return context.area is not None

    # --- lifecycle --------------------------------------------------------
    def _start(self, context):
        st = self.__class__.state
        if st.running:
            return
        wm = context.window_manager

        # Recurring timer so the overlay keeps refreshing even when idle.
        timer = wm.event_timer_add(_TIMER_STEP, window=context.window)
        st.timers.append(timer)

        # Register the modal handler (this is what feeds us events).
        wm.modal_handler_add(self)

        # Register the POST_PIXEL draw handler for every 3D viewport.
        self._add_draw_handlers(context)

        st.running = True
        st.held = set()
        st.pressed = []
        st.hints = []
        if context.area:
            context.area.tag_redraw()

    def _stop(self, context):
        st = self.__class__.state
        if not st.running:
            return
        wm = context.window_manager
        for t in st.timers:
            try:
                wm.event_timer_remove(t)
            except Exception:       # noqa: BLE001
                pass
        st.timers.clear()

        self._remove_draw_handlers(context)
        st.held.clear()
        st.pressed.clear()
        st.hints.clear()
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

        # Track held modifiers from the event's boolean flags...
        flags = _event_modifier_flags(event)
        # ...and also react to explicit modifier key press/release events,
        # which is what happens right when the user presses/releases a mod key.
        event_type = getattr(event, "type", None)
        mod = _canonical_modifier(event_type)
        value = getattr(event, "value", None)
        if mod is not None:
            if value == "PRESS":
                flags.add(mod)
            elif value == "RELEASE":
                flags.discard(mod)

        # Merge: the boolean flags are authoritative when present.
        if flags or mod is not None:
            st.held = flags
            st.held_since = now

        # Forget held modifiers that went stale without a release event
        # (Blender does not always send RELEASE, e.g. after focus changes).
        if st.held and (now - st.held_since) > _STALE_MODIFIER_SECS:
            st.held = set()

        # Record a clean tap of a non-modifier key (for the "pressed keys"
        # section of the HUD).
        if mod is None and value == "PRESS":
            key_name = hints.key_display_name(event_type)
            if event_type not in _IGNORED_PRESS_TYPES:
                st.pressed.insert(0, (now, sorted(st.held),
                                      key_name, event_type))
                st.pressed = st.pressed[:8]

        self._update_hints(context, st, now)
        self._schedule_redraw(context)
        return {"PASS_THROUGH"}

    def _update_hints(self, context, st, now):
        prefs = get_prefs()
        if prefs is None or not prefs.show_hints:
            st.hints = []
            return
        # Only rescan when the held modifiers or the area actually changed.
        cache_key = (frozenset(st.held),
                     getattr(context.area, "type", None))
        if (st.hints and cache_key == getattr(st, "_cache_key", None)
                and now - st.hints_as_of < 1.0):
            return
        if not st.held:
            st.hints = []
        else:
            try:
                combos = hints.collect_hints(context, st.held)
            except Exception:       # noqa: BLE001 - never break the observer
                combos = []
            st.hints = combos[: prefs.max_hints if prefs else 12]
        st.hints_as_of = now
        st._cache_key = cache_key

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
        # Allow bpy.ops.key_hint.capture() (no event available) to toggle too.
        st = self.__class__.state
        if st.running:
            self._stop(context)
        else:
            self._start(context)
        return {"FINISHED"}


# Tap types we do not want to show as "a key was pressed".
_IGNORED_PRESS_TYPES = {
    "NONE", "", "MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "TIMER",
    "WINDOW_DEACTIVATE", "TEXTINPUT",
}


# ---------------------------------------------------------------------------
# Public helpers used by the draw module ------------------------------------
# ---------------------------------------------------------------------------
def snapshot():
    """Return a plain dict describing the current HUD content.

    Used by the draw callback so it does not need to reach into the operator
    state directly.
    """
    st = KeyHintCaptureOperator.state
    prefs = get_prefs()
    return {
        "running": st.running,
        "held": [hints_key_name(m) for m in sorted(st.held)],
        "pressed": [
            {"mods": [hints_key_name(m) for m in mods],
             "key": key, "event_type": etype}
            for (_t, mods, key, etype) in st.pressed
        ],
        "hints": st.hints,
        "prefs": prefs,
    }


def hints_key_name(mod):
    return {
        "ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "oskey": "OS",
    }.get(mod, mod or "")


def register_enable_property():
    """Expose a boolean on WindowManager that toggles the capture.

    This lets the UI show a check-box that reflects the live state and can be
    driven from scripts, similar to how many Blender tools expose an "enabled"
    toggle.
    """
    if hasattr(bpy.types.WindowManager, "key_hint_enabled"):
        return

    def get_enabled(_self):
        return KeyHintCaptureOperator.state.running

    def set_enabled(_self, value):
        # Modal operators can only start/stop from a real UI context.
        for wm in bpy.data.window_managers:
            for win in wm.windows:
                for area in win.screen.areas:
                    if area.type == "VIEW_3D":
                        override = {
                            "window": win, "screen": win.screen,
                            "area": area,
                            "region": next(
                                (r for r in area.regions
                                 if r.type == "WINDOW"), None),
                        }
                        op = bpy.ops.key_hint.capture
                        if value and not KeyHintCaptureOperator.state.running:
                            op(override, "INVOKE_DEFAULT")
                        elif (not value and
                              KeyHintCaptureOperator.state.running):
                            op(override, "INVOKE_DEFAULT")
                        return
        # If no 3D viewport is present, nothing to do.

    bpy.types.WindowManager.key_hint_enabled = bpy.props.BoolProperty(
        name="Key Hint",
        description="Start / stop the Key Hint HUD overlay",
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
    """POST_PIXEL draw handler: args is the target 3D area pointer.

    The pointer lets us find the correct region even if several windows exist.
    """
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
    """Return an override context pointing at the first usable 3D viewport."""
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
                return {
                    "window": win,
                    "screen": screen,
                    "area": area,
                    "region": region,
                }
    return None


def start_capture(verbose=True):
    """Try to start the capture overlay. Returns True on success."""
    if is_running():
        return True
    override = _find_view3d_override()
    if override is None:
        if verbose:
            print("[Key Hint] No 3D viewport found - cannot start yet.")
        return False
    try:
        bpy.ops.key_hint.capture(override, "INVOKE_DEFAULT")
    except Exception as exc:             # noqa: BLE001
        print("[Key Hint] start failed:", exc)
        return False
    if verbose and is_running():
        print("[Key Hint] capture started")
    return is_running()


def stop_capture(verbose=True):
    """Try to stop the capture overlay."""
    if not is_running():
        return True
    override = _find_view3d_override()
    if override is None:
        return False
    try:
        bpy.ops.key_hint.capture(override, "INVOKE_DEFAULT")
    except Exception as exc:             # noqa: BLE001
        print("[Key Hint] stop failed:", exc)
        return False
    if verbose and not is_running():
        print("[Key Hint] capture stopped")
    return not is_running()


# --- auto start -----------------------------------------------------------
# Screencast-Keys-style auto start: when the add-on is enabled (or a file is
# loaded) and the user asked for auto start, keep trying to open the capture
# until a 3D viewport is usable.  We use an app timer so the attempt happens
# after Blender's context is ready.
def _auto_start_loop():
    if is_running():
        return None                    # done
    prefs = get_prefs()
    if prefs is not None and not prefs.auto_start:
        return None                    # disabled
    if start_capture(verbose=False):
        return None
    return 1.0                         # retry once a second


_AUTO_TIMER = None


def register_auto_start():
    """Start the auto-start timer (no-op if already running / background)."""
    global _AUTO_TIMER
    if bpy.app.background:
        return
    if _AUTO_TIMER is not None:
        return
    try:
        _AUTO_TIMER = bpy.app.timers.register(_auto_start_loop)
    except Exception:                  # noqa: BLE001  (already registered)
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
    # Re-arm auto start after every new/loaded file.
    register_auto_start()


def handle_auto_start_change(self, context):
    """Update callback wired to the auto_start preference."""
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
