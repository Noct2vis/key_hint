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
侧边栏 (N-panel)。

* 顶部小工具：同步数据库 / 恢复默认显示。
* 搜索栏(在“我的快捷键”上方)：下拉按 功能名/按键 + 输入框。它同时做两件事：
    1) 过滤下方“我的快捷键”里显示的条目；
    2) 把匹配的 B 表(keyconfig)条目列成“加入”，点一下加进我的快捷键。
* 我的快捷键：按修饰键分组显示(功能名 | 按键 + ×隐藏)。默认=curated 内容，
  键已由 B 回填真实绑定。没有“只看基础组”，也没有“精选/全部”。
没有“是否显示 Key Hint”开关。
"""

import bpy
from bpy.props import EnumProperty, StringProperty

from . import hints
from . import engine
from . import runtime


def _tags(context):
    st = getattr(context, "area", None)
    st = getattr(st, "type", "VIEW_3D") if st else "VIEW_3D"
    return engine.active_tags(hints._context_mode(context), st)


# ---------------------------------------------------------------------------
# 算子
# ---------------------------------------------------------------------------
class KEYHINT_OT_hide(bpy.types.Operator):
    """从“我的快捷键”隐藏这条(不显示，仍在库里可再加回)"""
    bl_idname = "key_hint.hide"
    bl_label = "隐藏"
    bl_options = {"REGISTER"}
    rid: StringProperty(name="rid", default="")

    def execute(self, context):
        if self.rid:
            runtime.hide(self.rid)
        return {"FINISHED"}


class KEYHINT_OT_add(bpy.types.Operator):
    """把 B 表(keyconfig)里的这条加入“我的快捷键”"""
    bl_idname = "key_hint.add"
    bl_label = "加入"
    bl_options = {"REGISTER"}
    rid: StringProperty(name="rid", default="")

    def execute(self, context):
        ok = runtime.add_from_pool_rid(self.rid)
        self.report({"INFO"} if ok else {"WARNING"},
                    "已加入" if ok else "该条已在列表中")
        return {"FINISHED"}


class KEYHINT_OT_reload(bpy.types.Operator):
    """同步：重读 keyconfig，回填真实键并刷新候选池"""
    bl_idname = "key_hint.reload"
    bl_label = "同步数据库"
    bl_options = {"REGISTER"}

    def execute(self, context):
        runtime.refresh_pool()
        n = len(runtime.sync_now())
        self.report({"INFO"}, "已同步(%d 条显示)" % n)
        return {"FINISHED"}


class KEYHINT_OT_set_default(bpy.types.Operator):
    """“我的快捷键”恢复为默认(curated 内容)"""
    bl_idname = "key_hint.set_default"
    bl_label = "恢复默认显示"
    bl_options = {"REGISTER"}

    def execute(self, context):
        runtime.set_default()
        self.report({"INFO"}, "已恢复默认显示")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------
class KEYHINT_PT_panel(bpy.types.Panel):
    bl_label = "Key Hint"
    bl_idname = "KEYHINT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Key Hint"

    @classmethod
    def poll(cls, context):
        return context.area.type == "VIEW_3D"

    def _tools(self, layout):
        row = layout.row(align=True)
        row.operator("key_hint.reload", text="同步数据库", icon="FILE_REFRESH")
        row.operator("key_hint.set_default", text="", icon="LOOP_BACK",
                     emboss=False)

    def _search(self, layout, context):
        scene = context.scene
        layout.separator()
        row = layout.row(align=True)
        row.prop(scene, "key_hint_search_field", expand=True)
        layout.prop(scene, "key_hint_search_text", text="", icon="VIEWZOOM")

    def _shown(self, layout, context, tags):
        scene = context.scene
        q = (scene.key_hint_search_text or "").strip().lower()
        field = scene.key_hint_search_field

        recs = runtime.shown_records()
        header = layout.row()
        header.label(text="我的快捷键 · %d 条" % len(recs))

        groups = runtime.groups_shown(
            tags, sel_present=True, held=None, parent=None,
            search_field=(field if q else None), search_query=q,
            only_base=False)
        if not groups:
            layout.label(text="当前模式无匹配", icon="INFO")
            return
        for gname, rows in groups:
            col = layout.column(align=True)
            col.separator()
            box = col.box()
            box.label(text=gname)
            for r in rows[:200]:
                row = box.row(align=True)
                row.label(text=r.get("name") or r.get("op") or "?")
                sub = row.row(align=True)
                sub.alignment = "RIGHT"
                sub.label(text=engine.combo_text(r.get("mods"), r.get("key")))
                op = sub.operator("key_hint.hide", text="", icon="X",
                                  emboss=False)
                op.rid = r.get("rid", "")

    def _add_pool(self, layout, context, tags):
        scene = context.scene
        q = (scene.key_hint_search_text or "").strip().lower()
        field = scene.key_hint_search_field
        if not q:
            return
        shown_rids = {r.get("rid") for r in runtime.shown_records()}
        box = layout.box()
        box.label(text="数据库(B)里可加入")
        count = 0
        for r in runtime.pool():
            if not (set(r.get("tags") or ()) & set(tags)):
                continue
            if r.get("rid") in shown_rids:
                continue
            if field == "key":
                hay = engine.combo_text(r.get("mods"), r.get("key")).lower()
            else:
                hay = (r.get("name") or "").lower()
            if q not in hay:
                continue
            row = box.row(align=True)
            row.label(text=r.get("name") or r.get("op") or "?")
            ssub = row.row(align=True)
            ssub.alignment = "RIGHT"
            ssub.label(text=engine.combo_text(r.get("mods"), r.get("key")))
            op = ssub.operator("key_hint.add", text="加入")
            op.rid = r.get("rid", "")
            count += 1
            if count >= 60:
                break
        if not count:
            box.label(text="无匹配", icon="INFO")

    def draw(self, context):
        layout = self.layout
        tags = _tags(context)
        self._tools(layout)
        self._search(layout, context)
        self._shown(layout, context, tags)
        self._add_pool(layout, context, tags)


# ---------------------------------------------------------------------------
# 注册 / 注销
# ---------------------------------------------------------------------------
def _reg(cls):
    try:
        bpy.utils.register_class(cls)
    except (RuntimeError, ValueError):
        pass


def _unreg(cls):
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError:
        pass


def register_panel_props():
    _reg(KEYHINT_PT_panel)
    _reg(KEYHINT_OT_hide)
    _reg(KEYHINT_OT_add)
    _reg(KEYHINT_OT_reload)
    _reg(KEYHINT_OT_set_default)
    S = bpy.types.Scene
    if not hasattr(S, "key_hint_search_field"):
        S.key_hint_search_field = EnumProperty(
            name="按", items=[("NAME", "功能名", ""), ("KEY", "按键", "")],
            default="NAME")
    if not hasattr(S, "key_hint_search_text"):
        S.key_hint_search_text = StringProperty(name="搜索", default="")


def unregister_panel_props():
    for cls in (KEYHINT_OT_set_default, KEYHINT_OT_reload,
                KEYHINT_OT_add, KEYHINT_OT_hide, KEYHINT_PT_panel):
        _unreg(cls)
    S = bpy.types.Scene
    for name in ("key_hint_search_text", "key_hint_search_field",
                 "key_hint_only_base"):
        if hasattr(S, name):
            delattr(S, name)
