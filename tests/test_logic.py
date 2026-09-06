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

"""Headless logic tests for Key Hint.

Run with:
    blender --background --factory-startup --python tests/test_logic.py
Exits non-zero if a check fails.
"""

import os
import sys

# Allow running from inside the tests/ dir or the repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import bpy  # noqa: E402

import key_hint  # noqa: E402
from key_hint import hints  # noqa: E402


def check(name, ok):
    print(("PASS" if ok else "FAIL"), "-", name)
    if not ok:
        _failures.append(name)


_failures = []


def _fake_context(space_type="VIEW_3D"):
    class _Area:
        type = space_type

    class _Ctx:
        window_manager = bpy.context.window_manager
        area = _Area()

        def __getattr__(self, item):
            return None

    return _Ctx()


def main():
    # 1. Full register / unregister cycle must not raise.
    try:
        key_hint.register()
        check("register()", True)
    except Exception as e:                      # noqa: BLE001
        check("register() (raised %r)" % e, False)

    check("operator registered",
          hasattr(bpy.ops.key_hint, "capture"))
    check("panel registered",
          hasattr(bpy.types, "KEYHINT_PT_panel"))
    check("wm enable property",
          hasattr(bpy.types.WindowManager, "key_hint_enabled"))

    try:
        key_hint.unregister()
        check("unregister()", True)
    except Exception as e:                      # noqa: BLE001
        check("unregister() (raised %r)" % e, False)

    # 2. Pure helpers.
    check("key_display_name LEFT_CTRL -> Ctrl",
          hints.key_display_name("LEFT_CTRL") == "Ctrl")
    check("key_display_name A -> A",
          hints.key_display_name("A") == "A")
    check("key_display_name NUMPAD_1 -> Numpad 1",
          hints.key_display_name("NUMPAD_1") == "Numpad 1")
    check("key_display_name OSKEY -> Super",
          hints.key_display_name("OSKEY") == "Super")

    # 3. Context -> relevant keymap names should include obvious ones.
    ctx = _fake_context("VIEW_3D")
    names = hints.relevant_keymap_names(ctx)
    for want in ("Window", "3D View", "3D View Generic", "Object Mode"):
        check("relevant includes %s" % want, want in names)

    # 4. Hint scan must be safe (return list) even headless / no items.
    res = hints.collect_hints(ctx, ["ctrl"])
    check("collect_hints returns list", isinstance(res, list))
    # held modifiers subset logic
    check("empty held -> []", hints.collect_hints(ctx, []) == [])

    # 5. Modifier name helper.
    class _Ev:
        ctrl = True
        shift = False
        alt = True
        oskey = False
    hm = hints.held_modifier_names(_Ev())
    check("held_modifier_names -> ['Alt','Ctrl']", sorted(hm) == ["Alt", "Ctrl"])

    print("\n%d failures" % len(_failures))
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
