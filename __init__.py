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
Key Hint - Flowkeys-style shortcut reference for Blender.

Two surfaces share one shortcut engine (constants.py + keymap resolution):
  * a sidebar N-panel (panels.py) with categories, instant search, a custom-
    binding marker (✱) and per-shortcut notes stored in the .blend;
  * an optional always-on HUD in the 3D viewport (draw.py).

Both read the user's *real* keyconfig (bpy.context.window_manager.keyconfigs),
so re-bound shortcuts are shown with the user's key and flagged.
"""

import bpy

from . import prefs
from . import hints
from . import constants
from . import core
from . import draw
from . import panels


def _reload_submodules():
    """Force-reload all submodules so a stale cached module (from an earlier
    addon version) never surfaces.  This fixes the classic Blender issue where
    installing a new version over an old one leaves the old module object in
    ``sys.modules`` and `register()` then hits 'has no attribute X'."""
    import importlib
    global prefs, hints, constants, core, draw, panels
    prefs = importlib.reload(prefs)
    hints = importlib.reload(hints)
    constants = importlib.reload(constants)
    core = importlib.reload(core)
    draw = importlib.reload(draw)
    panels = importlib.reload(panels)


bl_info = {
    "name": "Key Hint",
    "author": "Noct2vis",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > Key Hint",
    "description": (
        "Flowkeys-style shortcut reference: categorized list in the sidebar "
        "and 3D-viewport HUD, synced to your keymap (custom bindings marked ✱)"
    ),
    "warning": "",
    "doc_url": "https://github.com/Noct2vis/key_hint",
    "tracker_url": "https://github.com/Noct2vis/key_hint/issues",
    "category": "3D View",
}


def _register_class(cls):
    """Register a class, tolerating 'already registered' (idempotent)."""
    try:
        bpy.utils.register_class(cls)
    except (RuntimeError, ValueError):
        pass


def register():
    _reload_submodules()
    _register_class(prefs.KeyHintAddonPreferences)
    panels.register_notes()
    _register_class(panels.KEYHINT_PT_panel)
    _register_class(core.KeyHintCaptureOperator)
    _register_class(core.KeyHintRestartOperator)
    _register_class(core.KeyHintWatchOperator)
    core.register_enable_property()
    core.register_app_handlers()
    core.register_auto_start()


def unregister():
    core.stop(verbose=False)
    core.unregister_auto_start()
    core.unregister_app_handlers()
    core.unregister_enable_property()
    try:
        bpy.utils.unregister_class(core.KeyHintWatchOperator)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(core.KeyHintRestartOperator)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(core.KeyHintCaptureOperator)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(panels.KEYHINT_PT_panel)
    except RuntimeError:
        pass
    panels.unregister_notes()
    try:
        bpy.utils.unregister_class(prefs.KeyHintAddonPreferences)
    except RuntimeError:
        pass


if __name__ == "__main__":
    register()
