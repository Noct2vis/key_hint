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
Diagnostic script - run inside Blender's Python Console or Text Editor:

    import sys
    sys.path.insert(0, r"D:/blender")   # parent dir of the key_hint folder
    import key_hint.tests.diagnose as d   # if installed as addon:
    #   import key_hint.diagnose as d
    d.run()

Prints where the shortcut engine, keymap resolution and HUD are in their
lifecycle, to locate a "nothing shows up" problem.
"""

import bpy


def run():
    print("=" * 60)
    print("Key Hint diagnostic")
    print("=" * 60)

    print("[1] Blender:", bpy.app.version_string)
    print("[2] addon module registered:",
          "key_hint" in bpy.context.preferences.addons if
          hasattr(bpy.context.preferences, "addons") else "n/a")

    try:
        from . import constants
        from . import hints
        from . import core
        print("[3] import constants/hints/core: OK")
    except Exception as e:                 # noqa: BLE001
        print("[3] import FAILED:", e)
        return

    # Mode.
    mode = hints._context_mode(bpy.context)
    print("[4] context mode:", mode, "| display:", hints.mode_display_name(bpy.context))

    # Keyconfig.
    kc = hints._pick_keyconfig(bpy.context)
    if kc is None:
        print("[5] keyconfig: NONE")
    else:
        print("[5] keyconfig:", kc.name, "| keymaps:",
              len(kc.keymaps) if hasattr(kc, "keymaps") else "?")

    # Shortcut DB + resolution.
    entries = constants.relevant_shortcuts(mode)
    print("[6] relevant_shortcuts:", len(entries))
    try:
        bindings = constants.resolve_bindings(bpy.context, mode)
        found = sum(1 for b in bindings.values() if b.get("found"))
        custom = sum(1 for b in bindings.values() if b.get("custom"))
        print("[7] resolve_bindings:", len(bindings), "found=", found,
              "custom=", custom)
        # sample 5
        for e in entries[:5]:
            b = bindings.get(e["id"], {})
            print("      -", e["label"], "->", b.get("key"), b.get("mods"),
                  "custom" if b.get("custom") else "")
    except Exception as e:                 # noqa: BLE001
        print("[7] resolve FAILED:", e)

    # Lifecycle.
    print("[8] running:", core.is_running(),
          "| draw_handle:", bool(core._draw_handle),
          "| redraw_timer:", bool(core._redraw_timer))
    s = core.snapshot()
    print("[9] snapshot mode:", s.get("mode"), "| entries:", s.get("entries"))

    # Whether a 3D viewport + WINDOW region exists (for HUD).
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    r = next((r for r in area.regions if r.type == "WINDOW"),
                             None)
                    print("[10] 3D area", area.width, "x", area.height,
                          "| window region:", r.width if r else None, "x",
                          r.height if r else None)
    except Exception as e:                 # noqa: BLE001
        print("[10] no windows/areas:", e)

    print("=" * 60)


if __name__ == "__main__":
    run()
