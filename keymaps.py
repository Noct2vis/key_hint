# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Key Hint is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation, version 3 of the License.
#
#  Key Hint is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Key Hint.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

"""
修饰键事件源：给左右 Ctrl / Shift / Alt / OS 登记真实的按下 / 松开绑定。

为什么要有这一层（见 .scratch/modifier-hint-refresh/issues/01 的诊断）：
    watch modal 收不到“孤立修饰键”的 key-down，所以“按住 Ctrl → HUD 立刻切换”
    过去完全押在 modal 的 0.1s TIMER 事件上，而合成 TIMER 事件的修饰位并不保证
    反映物理按键。这里改走 Blender 的 keymap：给修饰键**本身**登记 PRESS/RELEASE，
    命中后原样放行（PASS_THROUGH，不吞事件），由 core.note_modifier_key() 更新
    held 状态并立刻重绘。

这只是“第二路”之上的主力，不替代 watch modal：modal 继续负责操作提示
（G/R/S/E/I、Ctrl+R/B、K）、鼠标拖拽移动 HUD 与窗口失焦清零。
"""

import bpy

from . import core


# 绑定的事件类型 → held 状态里的属性名（左右修饰键是不同键码，都要绑）。
MODIFIER_KEYS = (
    ("LEFT_CTRL", "ctrl"),
    ("RIGHT_CTRL", "ctrl"),
    ("LEFT_SHIFT", "shift"),
    ("RIGHT_SHIFT", "shift"),
    ("LEFT_ALT", "alt"),
    ("RIGHT_ALT", "alt"),
    ("OSKEY", "oskey"),
)

# 值的两种形态：按下与松开，各自一条绑定。
VALUES = ("PRESS", "RELEASE")

# 绑到 window 级 keymap（"Window" 覆盖所有区域），再补一份 3D 视图 keymap。
# 多绑一份只是让同一个幂等更新多被叫到一次，不会互相打架。
TARGET_KEYMAPS = (("Window", "EMPTY"), ("3D View", "VIEW_3D"))

_items = []          # [(keymap, keymap_item)]，注销时逐个摘掉


def event_to_attr(evt_type):
    """事件类型 → held 属性名；不是修饰键就返回 None。"""
    for name, attr in MODIFIER_KEYS:
        if name == evt_type:
            return attr
    return None


def _get_or_add_keymap(kc, name, space_type):
    for km in kc.keymaps:
        if km.name == name:
            return km
    return kc.keymaps.new(name=name, space_type=space_type)


def register():
    """挂上修饰键绑定。返回 [(keymap 名, 条数)]；没有 addon keyconfig 时返回 []。"""
    global _items
    if _items:
        return []
    wm = getattr(bpy.context, "window_manager", None)
    kc = getattr(wm.keyconfigs, "addon", None) if wm is not None else None
    if kc is None:
        # background / 无 addon keyconfig：不是错误，HUD 本来就只在 GUI 里跑。
        print("[Key Hint] modifier bindings skipped: no addon keyconfig")
        return []
    idname = KeyHintModifierWatchOperator.bl_idname
    made = []
    for name, space_type in TARGET_KEYMAPS:
        try:
            km = _get_or_add_keymap(kc, name, space_type)
        except Exception as exc:            # noqa: BLE001
            print("[Key Hint] keymap %r unavailable:" % name, exc)
            continue
        count = 0
        for evt_type, _attr in MODIFIER_KEYS:
            for value in VALUES:
                try:
                    # any=True：修饰位用 ANY，和 Blender 自己的
                    # "Generic Gizmo Tweak Modal Map" 绑裸修饰键的写法一致 ——
                    # 否则按钮事件自带的 ctrl/shift 位会把它挡掉。
                    try:
                        kmi = km.keymap_items.new(idname, evt_type, value,
                                                  any=True)
                    except TypeError:
                        kmi = km.keymap_items.new(idname, evt_type, value)
                except Exception as exc:    # noqa: BLE001
                    print("[Key Hint] binding %s/%s failed:" % (evt_type, value),
                          exc)
                    continue
                _items.append((km, kmi))
                count += 1
        made.append((name, count))
    return made


def unregister():
    """摘掉全部修饰键绑定（插件停用/重载时必须调用，别留残留）。"""
    global _items
    for km, kmi in _items:
        try:
            km.keymap_items.remove(kmi)
        except Exception:                   # noqa: BLE001
            pass
    _items = []


def is_registered():
    return bool(_items)


class KeyHintModifierWatchOperator(bpy.types.Operator):
    """修饰键自己的轻量监听：把 PRESS/RELEASE 转给 core，然后原样放行。"""

    bl_idname = "key_hint.mod_watch"
    bl_label = "Key Hint Modifier Watch"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        # 只读取状态，任何时候都是安全的；HUD 没开时不必干活。
        return core.is_running()

    def invoke(self, context, event):
        core.note_modifier_key(getattr(event, "type", None),
                               getattr(event, "value", None))
        # 永远不消费事件：Ctrl+Z 之类照常走 Blender 自己的键位。
        return {"PASS_THROUGH"}

    def execute(self, context):
        return {"PASS_THROUGH"}
