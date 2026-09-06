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
Key Hint - game-style dynamic shortcut hints for Blender.

While you hold a modifier key (Ctrl / Shift / Alt / OS-key) in the 3D
Viewport, Key Hint scans your *actual* active keymap configuration and draws a
small game-like HUD listing the real shortcuts that start with the modifier
you are holding (e.g. holding Ctrl shows "Ctrl + X -> Delete", ...).

It also keeps a lightweight, non-destructive display of the keys you are
pressing.  Key Hint never eats the input it observes: it runs as a passive
PASS_THROUGH modal handler, so every shortcut keeps working exactly as before.
"""

# The reload-detection idiom below must run BEFORE `import bpy` so that on a
# first import "bpy" is not yet in this module's namespace and we take the
# initial-import branch (which is what actually imports the sub-modules).
if "bpy" in locals():
    import importlib
    for _mod_name in ("prefs", "hints", "draw", "core", "ui"):
        if _mod_name in locals():
            importlib.reload(locals()[_mod_name])
else:
    import bpy
    from . import prefs
    from . import hints
    from . import draw
    from . import core
    from . import ui

import bpy  # noqa: E402  (guarantee bpy is in scope for bl_info consumers)

bl_info = {
    "name": "Key Hint",
    "author": "Noct2vis",
    "version": (0, 1, 1),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > Key Hint",
    "description": (
        "Game-style dynamic shortcut hints: hold Ctrl/Shift/Alt to see the "
        "real keymap shortcuts that start with that modifier"
    ),
    "warning": "",
    "doc_url": "https://github.com/Noct2vis/key_hint",
    "tracker_url": "https://github.com/Noct2vis/key_hint/issues",
    "category": "3D View",
}


def register():
    # Order matters: preferences first, then the capture operator + UI.
    bpy.utils.register_class(prefs.KeyHintAddonPreferences)
    bpy.utils.register_class(core.KeyHintCaptureOperator)
    bpy.utils.register_class(ui.KEYHINT_PT_panel)
    core.register_enable_property()
    core.register_app_handlers()
    # Auto start if the user opted in (default on), after context is ready.
    core.register_auto_start()


def unregister():
    core.unregister_auto_start()
    core.unregister_app_handlers()
    core.unregister_enable_property()
    try:
        bpy.utils.unregister_class(ui.KEYHINT_PT_panel)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(core.KeyHintCaptureOperator)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(prefs.KeyHintAddonPreferences)
    except RuntimeError:
        pass


if __name__ == "__main__":
    register()
