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
Key Hint - 基于“两表”的快捷键参考。

插件读取你真实键位(config)，但只在三个刷新点重建，而不是每帧扫描：
  * 数据库表 B：活动 keyconfig 的全量绑定(键盘+鼠标+特殊键+modal 子键)，
    功能名用界面语言算子名(builder.py 在 启动/增删键位/keymap变化 时重建)。
  * 显示表 A：你实际保留显示的子集(library.py，默认全显，可增删，持久化)。
核心查询(engine.py)：按 当前模式标签 × 选中状态 × 按住修饰键 × 是否已按操作键
决定显示哪些行。侧栏(panels.py)编辑 A + 按功能名/按键搜索 + 分组；3D 视口 HUD
(draw.py + core.py watch modal)实时反映。没有“是否显示 Key Hint”开关。
"""

import bpy

from . import prefs
from . import hints
from . import constants
from . import engine
from . import library
from . import content
from . import builder
from . import runtime
from . import core
from . import draw
from . import panels


def _reload_submodules():
    """Force-reload all submodules so a stale cached module (from an earlier
    addon version) never surfaces."""
    import importlib
    global prefs, hints, constants, engine, library, content, builder, runtime
    global core, draw, panels
    prefs = importlib.reload(prefs)
    hints = importlib.reload(hints)
    constants = importlib.reload(constants)
    engine = importlib.reload(engine)
    library = importlib.reload(library)
    content = importlib.reload(content)
    builder = importlib.reload(builder)
    runtime = importlib.reload(runtime)
    core = importlib.reload(core)
    draw = importlib.reload(draw)
    panels = importlib.reload(panels)


bl_info = {
    "name": "Key Hint",
    "author": "Noct2vis",
    "version": (2, 0, 1),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > Key Hint",
    "description": (
        "Two-table shortcut reference synced to your real keymap: shows the "
        "shortcuts you keep (sidebar) and a live 3D-viewport HUD that reacts "
        "to mode / selection / held modifiers / pressed operation keys."
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
    panels.register_panel_props()
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
    panels.unregister_panel_props()
    try:
        bpy.utils.unregister_class(prefs.KeyHintAddonPreferences)
    except RuntimeError:
        pass


if __name__ == "__main__":
    register()
