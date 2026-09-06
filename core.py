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
Lifecycle for Key Hint.

Display target: Blender's *window status bar* (the bottom strip that is
normally always visible).  Key Hint drives it through the native
``WindowManager.status_text_set()`` API, which Blender itself renders - no
custom GPU drawing, so there is no "drawn off screen" or overlay problem.

While the add-on runs we keep a PASS_THROUGH modal operator alive and, on a
short timer, push the current mode's shortcut reference to the status text.
The status text disappears automatically once the modal ends.

GPL note: PASS_THROUGH-modal observation is the architecture idea shared with
Screencast Keys (GPL-2.0-or-later) and Shortcut VUr (GPL-3.0); the code below
is written for Key Hint.
"""

import time

import bpy

from . import hints
from .prefs import get_prefs

_STALE_MODIFIER_SECS = 0.6
# How often the status text refreshes / rescans the keymap.
_LOOP_SECS = 0.15
_RESCAN_INTERVAL = 1.0

# Running flag shared by the panel / operator.
_running = False

# Current held modifier attribute-names (set by the modal on key events).
_held = set()
_held_since = 0.0

# Cached scan of current context.
_entries = []
_scan_key = None
_scan_at = 0.0
_mode_title = ""

_last_push = ""

# Module-level keepalive timer that re-arms the status modal and re-scans.
_keepalive = None


def is_running():
    return _running


# ---------------------------------------------------------------------------
# Keymap scan ---------------------------------------------------------------
# ---------------------------------------------------------------------------
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
# Text assembly -------------------------------------------------------------
# ---------------------------------------------------------------------------
def hints_key_name(mod):
    return {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "oskey": "OS"} \
        .get(mod, mod or "")


def _combo_text(mods, key):
    if mods:
        return " + ".join(mods + [key])
    return key


def build_status_text(prefs):
    """Build the one-line status-bar reference for the current context."""
    if not _running:
        return ""
    base, _ = hints.split_base_and_modifier(_entries)

    parts = []
    title = ("[%s] " % _mode_title) if _mode_title else ""

    # Always-on fundamentals (no modifier).
    show_base = prefs is None or prefs.show_fundamentals
    if show_base and base:
        shown = base[: (prefs.max_hints if prefs else 20)]
        joined = "   ".join(
            "%s %s" % (_combo_text(e["mods"], e["key"]), e["label"])
            for e in shown)
        parts.append(joined)

    # Held modifier group (appended).
    if (prefs is None or prefs.show_hints) and _held:
        extra = hints.entries_for_modifiers(_entries, _held)
        if extra:
            held_names = " + ".join(hints_key_name(m) for m in sorted(_held))
            extra_shown = extra[: (prefs.max_hints if prefs else 20)]
            extra_txt = "   ".join(
                "%s %s" % (_combo_text(e["mods"], e["key"]), e["label"])
                for e in extra_shown)
            parts.append("[" + held_names + " +]  " + extra_txt)

    body = ("   ||   ".join(p for p in parts if p)).strip()
    return title + body


# ---------------------------------------------------------------------------
# Status bar modal ----------------------------------------------------------
# ---------------------------------------------------------------------------
class KeyHintStatusOperator(bpy.types.Operator):
    """Passive modal that keeps the shortcut reference in the status bar."""
    bl_idname = "key_hint.status"
    bl_label = "Key Hint"
    bl_description = "Show Key Hint reference in the status bar"
    bl_options = {"REGISTER"}

    _timer = None

    @classmethod
    def poll(cls, context):
        return True

    # --- lifecycle ------------------------------------------------------
    def invoke(self, context, event):
        cls = self.__class__
        if not _running:
            return {"CANCELLED"}
        if cls._timer is None:
            try:
                cls._timer = context.window_manager.event_timer_add(
                    _LOOP_SECS, window=context.window)
            except Exception:                # noqa: BLE001
                cls._timer = None
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _stop(self, context):
        cls = self.__class__
        if cls._timer is not None:
            try:
                context.window_manager.event_timer_remove(cls._timer)
            except Exception:                # noqa: BLE001
                pass
            cls._timer = None
        try:
            context.window_manager.status_text_set(None)
        except Exception:                    # noqa: BLE001
            pass

    def modal(self, context, event):
        global _held, _held_since
        if not _running:
            self._stop(context)
            return {"FINISHED"}

        evt_type = getattr(event, "type", None)
        value = getattr(event, "value", None)
        now = time.time()

        # Track held modifiers from event boolean flags + explicit key events.
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
            _held_since = now
        if _held and (now - _held_since) > _STALE_MODIFIER_SECS:
            _held = set()

        self._scan_if_needed_now(now)
        self._push_status(context)
        return {"PASS_THROUGH"}

    def _scan_if_needed_now(self, now):
        _scan_if_needed(now)

    def _push_status(self, context):
        global _last_push
        prefs = get_prefs()
        text = build_status_text(prefs)
        if not text:
            try:
                context.window_manager.status_text_set(None)
            except Exception:                # noqa: BLE001
                pass
            return
        try:
            context.window_manager.status_text_set(text)
            _last_push = text
        except Exception:                    # noqa: BLE001
            pass

    def cancel(self, context):
        self._stop(context)


# ---------------------------------------------------------------------------
# Lifecycle -----------------------------------------------------------------
# ---------------------------------------------------------------------------
def _keepalive_loop():
    """Re-arm the status modal if it got cancelled, and keep it updated."""
    global _keepalive
    if not _running:
        return None                        # stop
    try:
        _scan_if_needed(time.time())
        _ensure_status_modal()
        # Re-push current text if no modal is active to own the status bar.
        if not KeyHintStatusOperator._timer:
            _push_status_now()
    except Exception:                       # noqa: BLE001
        pass
    return _LOOP_SECS


def _push_status_now():
    """Push status text using the current window context (fallback)."""
    global _last_push
    try:
        wm = bpy.context.window_manager
        if wm is None:
            return
        text = build_status_text(get_prefs())
        if text:
            wm.status_text_set(text)
            _last_push = text
        else:
            wm.status_text_set(None)
    except Exception:                       # noqa: BLE001
        pass


def start(verbose=True):
    global _running, _keepalive
    if _running:
        return True
    _scan_if_needed(time.time(), force=True)
    _running = True
    if verbose:
        print("[Key Hint] started (status bar mode)")
    _ensure_status_modal()
    if _keepalive is None:
        try:
            _keepalive = bpy.app.timers.register(_keepalive_loop)
        except Exception:                    # noqa: BLE001
            _keepalive = None
    return True


def _ensure_status_modal():
    """Invoke the status modal against the first usable 3D viewport window."""
    if not _running:
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
                    bpy.ops.key_hint.status("INVOKE_DEFAULT")
            except Exception:                # noqa: BLE001
                pass
            return


def stop(verbose=True):
    global _running, _held, _entries, _keepalive
    if not _running:
        return True
    _running = False
    _held = set()
    _entries = []
    if _keepalive is not None:
        try:
            bpy.app.timers.unregister(_keepalive)
        except Exception:                    # noqa: BLE001
            pass
        _keepalive = None
    # Kill the status modal.
    try:
        bpy.ops.key_hint.status("INVOKE_DEFAULT")
    except Exception:                        # noqa: BLE001
        pass
    if verbose:
        print("[Key Hint] stopped")
    return True


def snapshot():
    """Plain dict describing current state (used by panel/tests)."""
    prefs = get_prefs()
    return {
        "running": _running,
        "mode": _mode_title,
        "entries": len(_entries),
        "held": [hints_key_name(m) for m in sorted(_held)],
        "held_attrs": sorted(_held),
        "last": _last_push,
        "prefs": prefs,
    }


# ---------------------------------------------------------------------------
# Operators -----------------------------------------------------------------
# ---------------------------------------------------------------------------
class KeyHintCaptureOperator(bpy.types.Operator):
    """Toggle the Key Hint status-bar reference on/off."""
    bl_idname = "key_hint.capture"
    bl_label = "Key Hint"
    bl_description = "Toggle the Key Hint status-bar reference"
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
    """Force a full restart and report state."""
    bl_idname = "key_hint.restart"
    bl_label = "Key Hint Restart / Show Status"
    bl_description = "Restart the Key Hint reference and report its state"

    def execute(self, context):
        stop(verbose=False)
        ok = start(verbose=True)
        msg = ("[Key Hint] running=%s entries=%d mode=%r"
               % (ok, len(_entries), _mode_title))
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
        description="Start / stop the Key Hint status-bar reference",
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
