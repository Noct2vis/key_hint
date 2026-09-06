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
快捷键数据库 + 键位解析 + 上下文提示表。

* SHORTCUTS —— 侧边栏参考用的分类快捷键数据库（中文标签）。
* BASE_HINTS —— 初始（未按任何操作键）时 HUD 显示的基础/文件操作。
* OPERATION_HINTS —— 按下某个“操作触发键”后，HUD 替换成的后续操作提示表。

所有“实际按键”仍由 resolve_bindings() 从用户 keyconfig 动态解析，自定义键位
用 ✱ 标记。OPERATION_HINTS 里的按键是“进入该操作后”的引导键，属于该操作的
后续子操作（例如按 G 后按 X/Y/Z 锁轴、数字吸附、LMB 确认），用静态中文说明。
"""

import bpy

MOD_ORDER = (("ctrl", "Ctrl"), ("shift", "Shift"), ("alt", "Alt"),
             ("oskey", "OS"))


def mods_of_item(item):
    out = []
    for attr, name in MOD_ORDER:
        if getattr(item, attr, False):
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# 侧边栏参考数据库（中文标签） ----------------------------------------------
# ---------------------------------------------------------------------------
SHORTCUTS = [
    # ---- 变换 ------------------------------------------------------------
    dict(id="move", label="移动", op="transform.translate", key="G", mods=(), cat="变换", modes=None),
    dict(id="rotate", label="旋转", op="transform.rotate", key="R", mods=(), cat="变换", modes=None),
    dict(id="scale", label="缩放", op="transform.resize", key="S", mods=(), cat="变换", modes=None),
    dict(id="move_dup", label="复制并移动", op="object.duplicate_move", key="D", mods=("Shift",), cat="变换", modes={"OBJECT"}),
    dict(id="snap", label="吸附切换", op="transform.snap_type", key="TAB", mods=("Shift",), cat="变换", modes={"OBJECT", "EDIT_MESH", "POSE"}),
    dict(id="apply_transform", label="应用变换", op="object.transform_apply", key="A", mods=("Ctrl",), cat="变换", modes={"OBJECT"}),

    # ---- 视图 ------------------------------------------------------------
    dict(id="view_selected", label="框选所选", op="view3d.view_selected", key="PERIOD", mods=("Shift",), cat="视图", modes=None),
    dict(id="view_all", label="框选全部", op="view3d.view_all", key="HOME", mods=(), cat="视图", modes=None),
    dict(id="toggle_local", label="局部/全局视图", op="view3d.localview", key="SLASH", mods=(), cat="视图", modes=None),
    dict(id="orbit", label="旋转视角", op="view3d.rotate", key="MIDDLEMOUSE", mods=(), cat="视图", modes=None, mouse=True),
    dict(id="pan", label="平移视角", op="view3d.move", key="MIDDLEMOUSE", mods=("Shift",), cat="视图", modes=None, mouse=True),
    dict(id="zoom", label="缩放视角", op="view3d.zoom", key="MIDDLEMOUSE", mods=("Ctrl",), cat="视图", modes=None, mouse=True),
    dict(id="front_view", label="前视图", op="view3d.view_axis", key="NUMPAD_1", mods=(), cat="视图", modes=None),
    dict(id="right_view", label="右视图", op="view3d.view_axis", key="NUMPAD_3", mods=(), cat="视图", modes=None),
    dict(id="top_view", label="顶视图", op="view3d.view_axis", key="NUMPAD_7", mods=(), cat="视图", modes=None),
    dict(id="camera_view", label="摄像机视图", op="view3d.view_camera", key="NUMPAD_0", mods=(), cat="视图", modes=None),
    dict(id="persp_ortho", label="透视/正交", op="view3d.view_persportho", key="NUMPAD_5", mods=(), cat="视图", modes=None),

    # ---- 物体模式 --------------------------------------------------------
    dict(id="select_all", label="全选/取消全选", op="object.select_all", key="A", mods=(), cat="物体", modes={"OBJECT"}),
    dict(id="add_object", label="添加物体", op="object.modifier_add", key="A", mods=("Shift",), cat="物体", modes={"OBJECT"}),
    dict(id="delete_object", label="删除", op="object.delete", key="X", mods=(), cat="物体", modes={"OBJECT"}),
    dict(id="duplicate_object", label="复制", op="object.duplicate", key="D", mods=("Shift",), cat="物体", modes={"OBJECT"}),
    dict(id="join", label="合并物体", op="object.join", key="J", mods=("Ctrl",), cat="物体", modes={"OBJECT"}),
    dict(id="parent", label="设置父级", op="object.parent_set", key="P", mods=("Ctrl",), cat="物体", modes={"OBJECT"}),
    dict(id="hide", label="隐藏物体", op="object.hide_view_set", key="H", mods=(), cat="物体", modes={"OBJECT"}),
    dict(id="unhide", label="全部取消隐藏", op="object.hide_view_clear", key="H", mods=("Alt",), cat="物体", modes={"OBJECT"}),
    dict(id="move_to_collection", label="移到集合", op="object.move_to_collection", key="M", mods=(), cat="物体", modes={"OBJECT"}),

    # ---- 编辑（网格） ----------------------------------------------------
    dict(id="edit_toggle", label="编辑/物体模式", op="object.editmode_toggle", key="TAB", mods=(), cat="模式", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="loopcut", label="环切", op="mesh.loopcut_slide", key="R", mods=("Ctrl",), cat="网格", modes={"EDIT_MESH"}),
    dict(id="extrude", label="挤出", op="mesh.extrude_region_move", key="E", mods=(), cat="网格", modes={"EDIT_MESH"}),
    dict(id="inset", label="内插面", op="mesh.inset", key="I", mods=(), cat="网格", modes={"EDIT_MESH"}),
    dict(id="bevel", label="倒角", op="mesh.bevel", key="B", mods=("Ctrl",), cat="网格", modes={"EDIT_MESH"}),
    dict(id="merge", label="合并顶点", op="mesh.merge", key="M", mods=(), cat="网格", modes={"EDIT_MESH"}),
    dict(id="knife", label="切割", op="mesh.knife_tool", key="K", mods=(), cat="网格", modes={"EDIT_MESH"}),
    dict(id="select_loop", label="选择循环边", op="mesh.loop_multi_select", key="L", mods=("Alt",), cat="网格", modes={"EDIT_MESH"}),
    dict(id="subdivide", label="细分", op="mesh.subdivide", key="E", mods=("Ctrl",), cat="网格", modes={"EDIT_MESH"}),
    dict(id="flip_normals", label="翻转法线", op="mesh.flip_normals", key="N", mods=("Shift", "Alt"), cat="网格", modes={"EDIT_MESH"}),
    dict(id="rip", label="撕裂", op="mesh.rip_move", key="V", mods=(), cat="网格", modes={"EDIT_MESH"}),
    dict(id="dissolve", label="溶解", op="mesh.dissolve_mode", key="X", mods=("Ctrl",), cat="网格", modes={"EDIT_MESH"}),

    # ---- 选择 ------------------------------------------------------------
    dict(id="select_more", label="扩大选择", op="mesh.select_more", key="PADPLUSKEY", mods=("Ctrl",), cat="选择", modes={"EDIT_MESH"}),
    dict(id="select_less", label="缩小选择", op="mesh.select_less", key="PADMINUS", mods=("Ctrl",), cat="选择", modes={"EDIT_MESH"}),
    dict(id="select_invert", label="反选", op="mesh.select_all", key="I", mods=("Ctrl",), cat="选择", modes={"EDIT_MESH"}),
    dict(id="box_select", label="框选", op="view3d.select_box", key="B", mods=(), cat="选择", modes={"OBJECT", "EDIT_MESH"}),

    # ---- 雕刻 ------------------------------------------------------------
    dict(id="sculpt_mode", label="雕刻模式", op="object.mode_set", key="TAB", mods=("Ctrl",), cat="模式", modes={"OBJECT"}),
    dict(id="brush_size", label="笔刷大小", op="wm.radial_control", key="F", mods=(), cat="雕刻", modes={"SCULPT"}),
    dict(id="brush_strength", label="笔刷强度", op="wm.radial_control", key="F", mods=("Shift",), cat="雕刻", modes={"SCULPT"}),
    dict(id="smooth_brush", label="平滑笔刷", op="sculpt.smooth", key="S", mods=("Shift",), cat="雕刻", modes={"SCULPT"}),
    dict(id="mask_brush", label="遮罩笔刷", op="sculpt.mask_filter", key="M", mods=("Ctrl",), cat="雕刻", modes={"SCULPT"}),

    # ---- 姿态 ------------------------------------------------------------
    dict(id="pose_mode", label="姿态模式", op="object.mode_set", key="TAB", mods=("Ctrl",), cat="模式", modes={"OBJECT"}),
    dict(id="pose_clear", label="清除姿态", op="pose.rot_clear", key="R", mods=("Alt",), cat="姿态", modes={"POSE"}),

    # ---- 文件/通用 -------------------------------------------------------
    dict(id="save", label="保存", op="wm.save_mainfile", key="S", mods=("Ctrl",), cat="文件", modes=None),
    dict(id="save_as", label="另存为", op="wm.save_as_mainfile", key="S", mods=("Ctrl", "Shift"), cat="文件", modes=None),
    dict(id="open", label="打开", op="wm.open_mainfile", key="O", mods=("Ctrl",), cat="文件", modes=None),
    dict(id="new_file", label="新建", op="wm.read_homefile", key="N", mods=("Ctrl",), cat="文件", modes=None),
    dict(id="undo", label="撤销", op="ed.undo", key="Z", mods=("Ctrl",), cat="文件", modes=None),
    dict(id="redo", label="重做", op="ed.redo", key="Z", mods=("Ctrl", "Shift"), cat="文件", modes=None),
    dict(id="search_menu", label="搜索菜单", op="wm.search_menu", key="F3", mods=(), cat="文件", modes=None),
    dict(id="quick_favorites", label="快速收藏", op="wm.call_menu", key="Q", mods=(), cat="文件", modes=None),

    # ---- 左侧工具栏（Toolbar） -----------------------------------------
    # 物体模式工具栏
    dict(id="tool_box", label="框选", op="view3d.select_box", key="W", mods=(), cat="工具栏", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="tool_circle", label="圆形选择", op="view3d.select_circle", key="C", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_lasso", label="套索选择", op="view3d.select_lasso", key="L", mods=("Ctrl",), cat="工具栏", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="tool_cursor", label="游标", key="SPACE", mods=("Shift",), cat="工具栏", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="tool_move", label="移动", op="transform.translate", key="G", mods=(), cat="工具栏", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="tool_rotate", label="旋转", op="transform.rotate", key="R", mods=(), cat="工具栏", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="tool_scale", label="缩放", op="transform.resize", key="S", mods=(), cat="工具栏", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="tool_transform", label="变换", op="transform.transform", key="G", mods=("Alt",), cat="工具栏", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="tool_annotate", label="标注", op="gpencil.annotate", key="D", mods=(), cat="工具栏", modes=None),
    dict(id="tool_measure", label="测量", op="view3d.measure", key="M", mods=(), cat="工具栏", modes=None),
    # 编辑模式工具栏
    dict(id="tool_extrude", label="挤出区域", op="mesh.extrude_region_move", key="E", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_extrude_normals", label="沿法线挤出", op="mesh.extrude_region_move", key="E", mods=("Alt",), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_inset", label="内插面", op="mesh.inset", key="I", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_bevel", label="倒角", op="mesh.bevel", key="B", mods=("Ctrl",), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_loopcut", label="环切", op="mesh.loopcut_slide", key="R", mods=("Ctrl",), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_knife", label="切割", op="mesh.knife_tool", key="K", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_poly_build", label="多边形构建", key="NONE", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_spin", label="旋转体", key="NONE", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_smooth", label="平滑顶点", op="mesh.vertices_smooth", key="S", mods=("Ctrl",), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_edge_slide", label="边滑动", op="transform.edge_slide", key="G G", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_vertex_slide", label="顶点滑动", op="transform.vert_slide", key="V", mods=("Shift",), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_shrink_fatten", label="收缩/膨胀", op="transform.shrink_fatten", key="S", mods=("Alt",), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_push_pull", label="推拉", key="NONE", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_shear", label="斜切", op="transform.shear", key="S", mods=("Ctrl", "Alt", "Shift"), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_rip_region", label="撕裂区域", op="mesh.rip_move", key="V", mods=(), cat="工具栏", modes={"EDIT_MESH"}),
    dict(id="tool_rip_edge", label="撕裂边", op="mesh.rip_edge_move", key="V", mods=("Alt",), cat="工具栏", modes={"EDIT_MESH"}),
    # 雕刻工具栏笔刷（4.x 起多数笔刷已无快捷键，用 1-9 快速访问收藏笔刷）
    dict(id="tool_brush_fav", label="收藏笔刷 1-9", key="1-9", mods=(), cat="工具栏", modes={"SCULPT"}),
    dict(id="tool_smooth_brush", label="平滑笔刷", op="sculpt.smooth", key="NONE", mods=(), cat="工具栏", modes={"SCULPT"}),
    dict(id="tool_mask", label="遮罩笔刷", op="sculpt.mask_filter", key="NONE", mods=(), cat="工具栏", modes={"SCULPT"}),
]


# ---------------------------------------------------------------------------
# 初始 HUD：基础/文件操作 ---------------------------------------------------
# ---------------------------------------------------------------------------
# 未按任何操作键时，HUD 显示这几条简单/文件操作。
BASE_HINTS = [
    {"key": "G", "mods": [], "label": "移动"},
    {"key": "R", "mods": [], "label": "旋转"},
    {"key": "S", "mods": [], "label": "缩放"},
    {"key": "A", "mods": [], "label": "全选"},
    {"key": "X", "mods": [], "label": "删除"},
    {"key": "D", "mods": ["Shift"], "label": "复制"},
    {"key": "S", "mods": ["Ctrl"], "label": "保存"},
    {"key": "O", "mods": ["Ctrl"], "label": "打开"},
    {"key": "Z", "mods": ["Ctrl"], "label": "撤销"},
    {"key": "Z", "mods": ["Ctrl", "Shift"], "label": "重做"},
]

_MOD_NAME = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "oskey": "OS"}


def base_hint_lines(mode):
    """Base HUD lines (combo, label) for *mode* — mode-aware, richer than the
    tiny hard-coded BASE_HINTS, reading the real user keyconfig."""
    ctx = bpy.context
    bindings = resolve_bindings(ctx, mode)
    lines = []
    for e in SHORTCUTS:
        m = e.get("modes")
        if m is not None and mode not in m:
            continue
        if e.get("mouse"):
            continue
        b = bindings.get(e["id"], {})
        key = b.get("key", e.get("key", "?"))
        if key in ("NONE", "?"):
            continue
        mods = b.get("mods", e.get("mods", []))
        if not mods:
            lines.append((key, e.get("label", "")))
    if lines:
        return lines
    # Fallback to hard-coded list.
    out = []
    for e in BASE_HINTS:
        key = e.get("key_extra") or e.get("key")
        mods = e.get("mods") or []
        combo = (" + ".join(mods + [key])) if mods else key
        out.append((combo, e.get("label", "")))
    return out


def modifier_hint_lines(mode, mods):
    """Lines (combo, label) whose required modifiers include every held one.

    ``mods`` is a set of modifier attribute names, e.g. {"ctrl"}.  Holding
    Ctrl also reveals Ctrl+Shift+... entries.
    """
    ctx = bpy.context
    bindings = resolve_bindings(ctx, mode)
    held = set(mods or ())
    lines = []
    for e in SHORTCUTS:
        m = e.get("modes")
        if m is not None and mode not in m:
            continue
        if e.get("mouse"):
            continue
        b = bindings.get(e["id"], {})
        key = b.get("key", e.get("key", "?"))
        if key in ("NONE", "?"):
            continue
        emods = b.get("mods", e.get("mods", []))
        if not emods:
            continue
        req = set()
        for attr, disp in MOD_ORDER:
            if disp in emods:
                req.add(attr)
        if held and held.issubset(req):
            combo = " + ".join(emods + [key])
            lines.append((combo, e.get("label", "")))
    return lines


# 初始 HUD 标题（按当前模式区分）
BASE_TITLES = {
    "OBJECT": "物体模式 · 基础",
    "EDIT_MESH": "编辑模式 · 基础",
    "SCULPT": "雕刻模式 · 基础",
    "POSE": "姿态模式 · 基础",
    "VERTEX_PAINT": "顶点绘制 · 基础",
    "WEIGHT_PAINT": "权重绘制 · 基础",
    "TEXTURE_PAINT": "纹理绘制 · 基础",
}

# 操作触发键 -> 该操作进入后的后续引导键（中文）。
# 触发键用 Blender 的 event.type 字符串（单键）或修饰组合。
OPERATION_HINTS = {
    "G": {
        "title": "移动（G）",
        "items": [
            {"key": "X", "mods": [], "label": "锁定 X 轴"},
            {"key": "Y", "mods": [], "label": "锁定 Y 轴"},
            {"key": "Z", "mods": [], "label": "锁定 Z 轴"},
            {"key": "Shift+X", "mods": ["Shift"], "key_extra": "X", "label": "锁定 YZ 平面"},
            {"key": "Shift+Y", "mods": ["Shift"], "key_extra": "Y", "label": "锁定 XZ 平面"},
            {"key": "Shift+Z", "mods": ["Shift"], "key_extra": "Z", "label": "锁定 XY 平面"},
            {"key": "0-9", "mods": [], "label": "按比例吸附"},
            {"key": "Ctrl", "mods": ["Ctrl"], "label": "微调（按住）"},
            {"key": "Alt", "mods": ["Alt"], "label": "吸附顶点/边（按住）"},
            {"key": "LMB", "mods": [], "label": "确认"},
            {"key": "RMB", "mods": [], "label": "取消"},
            {"key": "ESC", "mods": [], "label": "取消"},
        ],
    },
    "R": {
        "title": "旋转（R）",
        "items": [
            {"key": "X/Y/Z", "mods": [], "label": "锁定轴向"},
            {"key": "R", "mods": [], "label": "切换轨道/局部旋转"},
            {"key": "0-9", "mods": [], "label": "输入角度（度）"},
            {"key": "LMB", "mods": [], "label": "确认"},
            {"key": "RMB / ESC", "mods": [], "label": "取消"},
        ],
    },
    "S": {
        "title": "缩放（S）",
        "items": [
            {"key": "X/Y/Z", "mods": [], "label": "锁定轴向"},
            {"key": "0-9", "mods": [], "label": "输入比例"},
            {"key": "LMB", "mods": [], "label": "确认"},
            {"key": "RMB / ESC", "mods": [], "label": "取消"},
        ],
    },
    "E": {
        "title": "挤出（E）",
        "modes": {"EDIT_MESH"},
        "items": [
            {"key": "X/Y/Z", "mods": [], "label": "锁定轴向"},
            {"key": "E", "mods": [], "label": "挤出单个体"},
            {"key": "Alt+E", "mods": ["Alt"], "key_extra": "E", "label": "挤出选项菜单"},
            {"key": "LMB", "mods": [], "label": "确认"},
            {"key": "RMB / ESC", "mods": [], "label": "取消"},
        ],
    },
    "CTRL_R": {
        "title": "环切（Ctrl+R）",
        "modes": {"EDIT_MESH"},
        "items": [
            {"key": "滚轮", "mods": [], "label": "增加/减少段数"},
            {"key": "0-9", "mods": [], "label": "输入段数"},
            {"key": "F", "mods": [], "label": "翻转切口"},
            {"key": "LMB", "mods": [], "label": "确认"},
            {"key": "RMB / ESC", "mods": [], "label": "取消"},
        ],
    },
    "CTRL_B": {
        "title": "倒角（Ctrl+B）",
        "modes": {"EDIT_MESH"},
        "items": [
            {"key": "滚轮", "mods": [], "label": "增加段数"},
            {"key": "P", "mods": [], "label": "切换轮廓"},
            {"key": "LMB", "mods": [], "label": "确认"},
            {"key": "RMB / ESC", "mods": [], "label": "取消"},
        ],
    },
    "K": {
        "title": "切割（K）",
        "modes": {"EDIT_MESH"},
        "items": [
            {"key": "LMB", "mods": [], "label": "添加切割点"},
            {"key": "回车", "mods": [], "label": "确认"},
            {"key": "E", "mods": [], "label": "新建切"},
            {"key": "C", "mods": [], "label": "角度约束"},
            {"key": "ESC / RMB", "mods": [], "label": "取消"},
        ],
    },
    "I": {
        "title": "内插面（I）",
        "modes": {"EDIT_MESH"},
        "items": [
            {"key": "I", "mods": [], "label": "各自内插"},
            {"key": "B", "mods": [], "label": "边界模式"},
            {"key": "LMB", "mods": [], "label": "确认"},
            {"key": "RMB / ESC", "mods": [], "label": "取消"},
        ],
    },
}


# 触发键名 -> OPERATION_HINTS 的键。
# 用于把 modal 捕获到的 event 序列映射到 OPERATION_HINTS。
TRIGGER_KEYS = {
    "G": "G",
    "R": "R",
    "S": "S",
    "E": "E",
    "K": "K",
    "I": "I",
}


def _op_list(entry):
    op = entry.get("op")
    if isinstance(op, str):
        return [op]
    return list(op or [])


def relevant_shortcuts(mode):
    out = []
    for e in SHORTCUTS:
        m = e.get("modes")
        if m is None or mode in m:
            out.append(e)
    return out


def base_title_for_mode(mode):
    return BASE_TITLES.get(mode, "基础操作")


def operation_hint_for(trigger, mode):
    """Return OPERATION_HINTS[trigger] if it applies in *mode*, else None."""
    h = OPERATION_HINTS.get(trigger)
    if h is None:
        return None
    modes = h.get("modes")
    if modes is not None and mode not in modes:
        return None
    return h


# ---------------------------------------------------------------------------
# 键位解析 ------------------------------------------------------------------
# ---------------------------------------------------------------------------
def resolve_bindings(context, mode):
    from . import hints

    entries = relevant_shortcuts(mode)
    kc = hints._pick_keyconfig(context)
    if kc is None:
        return {e["id"]: {"key": e.get("key", "?"), "mods": list(e.get("mods", ())),
                          "custom": False, "found": False}
                for e in entries}

    by_name = {}
    try:
        for km in kc.keymaps:
            by_name[km.name] = km
    except Exception:                    # noqa: BLE001
        by_name = {}

    names = [n for n in hints.relevant_keymap_names(context) if n in by_name]

    bindings = {}
    for name in names:
        km = by_name.get(name)
        if km is None or getattr(km, "is_modal", False):
            continue
        try:
            items = list(km.keymap_items)
        except Exception:                # noqa: BLE001
            continue
        for it in items:
            if not getattr(it, "active", True):
                continue
            if getattr(it, "map_type", None) not in ("KEYBOARD", "KEYBOARD_MODIFIER"):
                continue
            if getattr(it, "value", None) not in ("PRESS", "ANY"):
                continue
            idname = getattr(it, "idname", None)
            if not idname:
                continue
            bindings[idname] = (getattr(it, "type", None), mods_of_item(it))

    out = {}
    for e in entries:
        key = e.get("key", "?")
        mods = list(e.get("mods", ()))
        found = False
        custom = False
        for op in _op_list(e):
            if op in bindings:
                k, m = bindings[op]
                key = hints.key_display_name(k) if k else key
                mods = m
                found = True
                custom = (hints.key_display_name(k) if k else key) != \
                    hints.key_display_name(e.get("key", "?")) or tuple(m) != \
                    tuple(e.get("mods", ()))
                break
        out[e["id"]] = {"key": key, "mods": mods, "custom": custom,
                        "found": found}
    return out
