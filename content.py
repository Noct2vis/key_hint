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
默认内容 = 一份 curated 清单(Kurt 常用)。

它是“匹配项”：每条定义 显示哪条功能(function)、属于哪个模式(mode)、是否需要选中
(selection_state)。真正显示的 修饰键 + 按键 由 B(keyconfig)填入 —— 见 runtime /
builder 的真实键回填。这份清单作为默认显示表 A 的种子，而不是“全塞 B”。

load_content() 把清单转成 engine 记录(键为文档默认值；带 op 的条目运行时用真实
绑定覆盖)。
"""

from . import engine

# 每条的 op 尽量填上真实算子，让运行时能从 keyconfig 回填真实键。
# 拿不准/视图类(多条共享同一算子)留空 -> 显示文档默认键。
KURT_CONTENT = [
    # ---- global ----------------------------------------------------------
    {"mode": "global", "modifier_keys": "none", "key": "X",
     "function": "删除选中的物体", "selection_state": "selected",
     "op": "object.delete"},
    {"mode": "global", "modifier_keys": "none", "key": "DELETE",
     "function": "删除选中的物体", "selection_state": "selected",
     "op": "object.delete"},
    {"mode": "global", "modifier_keys": "ctrl", "key": "Z",
     "function": "撤销上一步操作", "selection_state": "any", "op": "ed.undo"},
    {"mode": "global", "modifier_keys": "shift_ctrl", "key": "Z",
     "function": "重做", "selection_state": "any", "op": "ed.redo"},
    # ---- 3d_viewport -----------------------------------------------------
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "MIDDLEMOUSE",
     "function": "旋转视图", "selection_state": "any", "op": "view3d.rotate"},
    {"mode": "3d_viewport", "modifier_keys": "shift", "key": "MIDDLEMOUSE",
     "function": "平移视图", "selection_state": "any", "op": "view3d.move"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "WHEEL",
     "function": "缩放视图", "selection_state": "any", "op": "view3d.zoom"},
    {"mode": "3d_viewport", "modifier_keys": "alt", "key": "MIDDLEMOUSE",
     "function": "切换视角（微调）", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_1",
     "function": "前视图", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "ctrl", "key": "NUMPAD_1",
     "function": "后视图", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_3",
     "function": "右视图", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "ctrl", "key": "NUMPAD_3",
     "function": "左视图", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_7",
     "function": "顶视图", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "ctrl", "key": "NUMPAD_7",
     "function": "底视图", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_9",
     "function": "反转当前视图", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_0",
     "function": "切换摄像机视角", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_5",
     "function": "切换透视/正交投影", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_2",
     "function": "视角下移", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_4",
     "function": "视角左移", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_6",
     "function": "视角右移", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_8",
     "function": "视角上移", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_PERIOD",
     "function": "聚焦选中的物体", "selection_state": "selected",
     "op": "view3d.view_selected"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_PLUS",
     "function": "视图放大", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "NUMPAD_MINUS",
     "function": "视图缩小", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "none", "key": "GRAVE",
     "function": "调出视图选项菜单", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "shift", "key": "C",
     "function": "游标恢复世界中心", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "shift", "key": "RIGHTMOUSE",
     "function": "移动3D游标", "selection_state": "any"},
    {"mode": "3d_viewport", "modifier_keys": "shift", "key": "S",
     "function": "吸附/对齐菜单", "selection_state": "any"},
    # ---- object ----------------------------------------------------------
    {"mode": "object", "modifier_keys": "shift", "key": "A",
     "function": "新建物体", "selection_state": "any"},
    {"mode": "object", "modifier_keys": "none", "key": "G",
     "function": "移动", "selection_state": "selected", "op": "transform.translate"},
    {"mode": "object", "modifier_keys": "none", "key": "R",
     "function": "旋转", "selection_state": "selected", "op": "transform.rotate"},
    {"mode": "object", "modifier_keys": "none", "key": "S",
     "function": "缩放", "selection_state": "selected", "op": "transform.resize"},
    {"mode": "object", "modifier_keys": "alt", "key": "G",
     "function": "位置归零", "selection_state": "selected",
     "op": "object.location_clear"},
    {"mode": "object", "modifier_keys": "alt", "key": "R",
     "function": "旋转归零", "selection_state": "selected",
     "op": "object.rotation_clear"},
    {"mode": "object", "modifier_keys": "alt", "key": "S",
     "function": "缩放归1", "selection_state": "selected",
     "op": "object.scale_clear"},
    {"mode": "object", "modifier_keys": "shift", "key": "D",
     "function": "复制并移动", "selection_state": "selected",
     "op": "object.duplicate_move"},
    {"mode": "object", "modifier_keys": "none", "key": "H",
     "function": "隐藏选中的物体", "selection_state": "selected",
     "op": "object.hide_view_set"},
    {"mode": "object", "modifier_keys": "alt", "key": "H",
     "function": "显示全部隐藏物体", "selection_state": "any",
     "op": "object.hide_view_clear"},
    {"mode": "object", "modifier_keys": "shift", "key": "H",
     "function": "隐藏未选中的物体", "selection_state": "selected",
     "op": "object.hide_view_set"},
    {"mode": "object", "modifier_keys": "none", "key": "C",
     "function": "刷选工具", "selection_state": "any"},
    {"mode": "object", "modifier_keys": "none", "key": "A",
     "function": "全选所有物体", "selection_state": "any", "op": "object.select_all"},
    {"mode": "object", "modifier_keys": "shift", "key": "LEFTMOUSE",
     "function": "加选/减选物体", "selection_state": "any"},
    {"mode": "object", "modifier_keys": "ctrl", "key": "SPACE",
     "function": "最大化当前窗口", "selection_state": "any"},
    {"mode": "object", "modifier_keys": "ctrl", "key": "L",
     "function": "关联材质", "selection_state": "selected"},
    {"mode": "object", "modifier_keys": "ctrl", "key": "A",
     "function": "应用变换", "selection_state": "selected",
     "op": "object.transform_apply"},
    {"mode": "object", "modifier_keys": "none", "key": "SLASH",
     "function": "孤立模式", "selection_state": "selected"},
    # ---- edit ------------------------------------------------------------
    {"mode": "edit", "modifier_keys": "none", "key": "1",
     "function": "点选择模式", "selection_state": "any"},
    {"mode": "edit", "modifier_keys": "none", "key": "2",
     "function": "边选择模式", "selection_state": "any"},
    {"mode": "edit", "modifier_keys": "none", "key": "3",
     "function": "面选择模式", "selection_state": "any"},
    {"mode": "edit", "modifier_keys": "none", "key": "W",
     "function": "切换选择工具（框/刷/套）", "selection_state": "any"},
    {"mode": "edit", "modifier_keys": "ctrl", "key": "I",
     "function": "反选", "selection_state": "any", "op": "mesh.select_all"},
    {"mode": "edit", "modifier_keys": "none", "key": "L",
     "function": "选择相连元素", "selection_state": "any"},
    {"mode": "edit", "modifier_keys": "alt", "key": "DOUBLE_CLICK",
     "function": "选择循环边", "selection_state": "any"},
    {"mode": "edit", "modifier_keys": "ctrl_alt", "key": "DOUBLE_CLICK",
     "function": "选择并排边", "selection_state": "any"},
    {"mode": "edit", "modifier_keys": "none", "key": "E",
     "function": "挤出", "selection_state": "selected",
     "op": "mesh.extrude_region_move"},
    {"mode": "edit", "modifier_keys": "none", "key": "I",
     "function": "内插面", "selection_state": "selected", "op": "mesh.inset"},
    {"mode": "edit", "modifier_keys": "ctrl", "key": "B",
     "function": "倒角", "selection_state": "selected", "op": "mesh.bevel"},
    {"mode": "edit", "modifier_keys": "ctrl", "key": "R",
     "function": "环切", "selection_state": "selected",
     "op": "mesh.loopcut_slide"},
    {"mode": "edit", "modifier_keys": "none", "key": "M",
     "function": "合并顶点", "selection_state": "selected", "op": "mesh.merge"},
    {"mode": "edit", "modifier_keys": "none", "key": "V",
     "function": "断开顶点", "selection_state": "selected", "op": "mesh.rip_move"},
    {"mode": "edit", "modifier_keys": "none", "key": "F",
     "function": "填充面", "selection_state": "selected"},
    {"mode": "edit", "modifier_keys": "none", "key": "K",
     "function": "切刀工具", "selection_state": "selected",
     "op": "mesh.knife_tool"},
    {"mode": "edit", "modifier_keys": "ctrl", "key": "E",
     "function": "边菜单 / 桥接循环边", "selection_state": "selected"},
    {"mode": "edit", "modifier_keys": "none", "key": "P",
     "function": "分离选中部分", "selection_state": "selected", "op": "mesh.split"},
    {"mode": "edit", "modifier_keys": "shift", "key": "N",
     "function": "重新计算法向（翻转）", "selection_state": "selected"},
    {"mode": "edit", "modifier_keys": "alt", "key": "Z",
     "function": "透视模式（穿透选择）", "selection_state": "any"},
    {"mode": "edit", "modifier_keys": "ctrl", "key": "J",
     "function": "合并两个物体（需选两个）", "selection_state": "selected"},
]

_MODE_TAGS = {
    "global": {engine.TAG_GLOBAL},
    "3d_viewport": {engine.TAG_3D},
    "object": {engine.TAG_OBJECT},
    "edit": {engine.TAG_EDIT},
}

# 键名显示兜底(少数 token 引擎格式化不够友好)
_KEY_OVERRIDE = {
    "WHEEL": "鼠标滚轮", "DOUBLE_CLICK": "双击", "GRAVE": "`",
    "SPACE": "Spacebar", "DELETE": "Delete", "SLASH": "/",
    "LEFTMOUSE": "鼠标左键", "RIGHTMOUSE": "鼠标右键", "MIDDLEMOUSE": "鼠标中键",
}


def _stable_rid(name, tags, mods, sel, key_token):
    import hashlib
    blob = "|".join([str(name or ""), ",".join(sorted(tags)),
                     ",".join(mods), str(sel or "any"), str(key_token or "")])
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def load_content():
    """把 curated 清单转成 engine 记录(文档默认键；每行有稳定 rid)."""
    out = []
    for row in KURT_CONTENT:
        raw_key = str(row.get("key") or "")
        key = _KEY_OVERRIDE.get(raw_key, engine.key_display_name(raw_key))
        tags = set(_MODE_TAGS.get(row.get("mode"), {engine.TAG_GLOBAL}))
        sel = row.get("selection_state", "any")
        mods = engine.canonical_mods_from_str(row.get("modifier_keys"))
        out.append({
            "rid": _stable_rid(row.get("function", ""), tags, mods, sel,
                               raw_key),
            "tags": tags,
            "sel": sel,
            "mods": mods,
            "key": key,
            "name": row.get("function", ""),
            "op": row.get("op") or "",
            "parent": None,
            "km": "",
        })
    return out
