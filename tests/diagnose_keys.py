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
Key Hint 事件诊断脚本 (Blender GUI 内运行)。

目的:确定“修饰键按下/松开是否被插件检测到”问题出在哪一环。

用法(Blender 内,不是外部 python):
    1. 在 Text Editor 粘贴并运行本文件(或 `key_hint.tests.diagnose_keys.run()`);
    2. 运行后它会持续 10 秒,期间:
        第 1 秒内:什么都不按;
        第 2~4 秒:按住 Ctrl,再松开;
        第 5~7 秒:按住 Shift,再松开;
        最后:随便按一下 G;
    3. 结束后把控制台输出(或 `[KEYHINT-DIAG]` 开头的行)发给开发者。

它打印三组信息:
    [STATE]  插件内部状态:running / watch modal 是否注册 / held_mods 等。
    [EVENT]  模态收到的每个事件的 type/value + 修饰键布尔值。
    [TICK]   每 0.5s 一次的心跳,证明 TIMER 在持续派发。
"""

import time

import bpy


def _fmt_bool(b):
    return "1" if b else "0"


def _run_once(context):
    """10 秒内记录事件并周期性打印摘要。"""
    wm = context.window_manager

    # 1) 插件内部状态。
    try:
        from key_hint import core
        print("[KEYHINT-DIAG][STATE] running=%s" % core.is_running())
        print("[KEYHINT-DIAG][STATE] watch._added=%s watch._timer=%s"
              % (core.KeyHintWatchOperator._added,
                 core.KeyHintWatchOperator._timer is not None))
        print("[KEYHINT-DIAG][STATE] _held_mods=%r _active_op=%r"
              % (core._held_mods, core._active_op))
        print("[KEYHINT-DIAG][STATE] _last_modal_evt_ts=%.1f"
              % core._last_modal_evt_ts)
        print("[KEYHINT-DIAG][STATE] _draw_handle=%s _redraw_timer=%s"
              % (core._draw_handle is not None, core._redraw_timer is not None))
    except Exception as e:                  # noqa: BLE001
        print("[KEYHINT-DIAG][STATE] import key_hint.core failed:", e)

    # 2) 添加一个与插件相同的 PASS_THROUGH modal,记录每个事件。
    events = []
    start = time.time()

    class _DiagModal(bpy.types.Operator):
        bl_idname = "keyhint.diag_modal"
        bl_label = "Key Hint Diag"
        bl_options = {"REGISTER", "MODAL_PRIORITY"} \
            if bpy.app.version >= (4, 2, 0) else {"REGISTER"}

        _last_tick = 0.0

        def invoke(self, context, event):
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}

        def modal(self, context, event):
            now = time.time()
            if now - start > 10.0:
                return {"FINISHED"}
            if event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "NONE"}:
                print("[KEYHINT-DIAG][EVENT] t=%5.2f type=%-16s val=%-8s "
                      "ctrl=%s shift=%s alt=%s oskey=%s"
                      % (now - start, event.type, event.value,
                         _fmt_bool(event.ctrl), _fmt_bool(event.shift),
                         _fmt_bool(event.alt), _fmt_bool(event.oskey)))
            if now - self._last_tick > 0.5:
                self._last_tick = now
                print("[KEYHINT-DIAG][TICK] t=%4.1fs  ctrl=%s shift=%s alt=%s"
                      % (now - start, _fmt_bool(event.ctrl),
                         _fmt_bool(event.shift), _fmt_bool(event.alt)))
            return {"PASS_THROUGH"}

    try:
        bpy.utils.register_class(_DiagModal)
    except ValueError:
        pass

    print("[KEYHINT-DIAG] --- 诊断开始,按提示操作:不按 → 按住Ctrl→松开 → 按住Shift→松开 → 按G ---")
    bpy.ops.keyhint.diag_modal("INVOKE_DEFAULT")


def run():
    _run_once(bpy.context)


if __name__ == "__main__":
    run()
