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
修饰键绑定（方案 A，keymaps.py）“到底会不会被 Blender 触发”的 GUI 验证脚本。

背景：HUD 不刷新的根因是 watch modal 收不到孤立修饰键的 key-down。修法是给修饰键
本身登记 PRESS/RELEASE 绑定（见 .scratch/modifier-hint-refresh/issues/01）。绑定形式
已经对齐 Blender 自己的做法，但“按下 Ctrl 时它是否真的被调用”必须在 GUI 里实按一次
才算数 —— 这就是本脚本要回答的唯一问题。

用法（Blender GUI 内，不是外部 python）：
    1. 先确认 Key Hint 正在运行（3D 视口能看到 HUD）；
    2. Text Editor 里粘贴运行本文件（也可以 `exec(open(...).read())` 后调 run()）；
    3. 按提示操作：按住 Ctrl 约 2 秒 → 松开；按住 Shift 约 2 秒 → 松开；
       最后按一次 Ctrl+Z（验证别的快捷键没被吃掉）；
    4. 把控制台里 [KEYHINT-MOD] 开头的行发回来。

判读：
    * 有 `registered:` 且按键时打出 PRESS / RELEASE（changed=True）→ 方案 A 成立；
    * 完全没有 PRESS/RELEASE 行 → 裸修饰键绑定没被触发，需要改绑定形式（再议）。
"""

import time

import bpy

_DURATION = 20.0


def _traced(orig):
    def wrapper(evt_type, value):
        changed = orig(evt_type, value)
        from key_hint import core
        print("[KEYHINT-MOD] type=%-12s value=%-8s changed=%s held=%r"
              % (evt_type, value, changed, sorted(core._held_mods)))
        return changed
    return wrapper


def _tick():
    from key_hint import core
    print("[KEYHINT-MOD][TICK] running=%s bindings=%s held=%r redraw_timer=%s"
          % (core.is_running(), _bindings_ok, sorted(core._held_mods),
             core._redraw_timer is not None))
    if time.time() - _start > _DURATION:
        _restore()
        print("[KEYHINT-MOD] --- 诊断结束（绑定已还原） ---")
        return None
    return 2.0


_start = 0.0
_bindings_ok = None
_orig_note = None


def _restore():
    global _orig_note
    if _orig_note is None:
        return
    from key_hint import core
    core.note_modifier_key = _orig_note
    _orig_note = None


def run():
    global _start, _bindings_ok, _orig_note
    from key_hint import core, keymaps

    print("[KEYHINT-MOD] running=%s" % core.is_running())
    try:
        bpy.utils.register_class(keymaps.KeyHintModifierWatchOperator)
    except (RuntimeError, ValueError):
        pass
    made = keymaps.register()
    _bindings_ok = made
    print("[KEYHINT-MOD] registered: %r" % (made,))
    if not made:
        print("[KEYHINT-MOD] 没有可用 keymap，方案 A 在这个环境里无法验证")
        return

    if _orig_note is None:
        _orig_note = core.note_modifier_key
        core.note_modifier_key = _traced(_orig_note)

    _start = time.time()
    print("[KEYHINT-MOD] --- 开始：按住 Ctrl 2 秒 → 松开；Shift 同理；再按一次 Ctrl+Z ---")
    bpy.app.timers.register(_tick)


if __name__ == "__main__":
    run()
