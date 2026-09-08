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
纯查询/格式化引擎（不依赖 bpy，可无头测试）。

一条“已知快捷键记录”(record) 是普通 dict：
  {
    "tags":      ["global","3d_viewport","object"],  # 命中的官方模式标签
    "sel":       "any" | "selected",                 # 是否需要选中
    "mods":      ["Ctrl","Shift",...],                 # 规范顺序修饰键
    "key":       "按键显示串", e.g. "G" / "Numpad 1" / "鼠标左键"
    "name":      "中文/界面语言功能名",
    "op":        "真实算子 idname"(可空，UI/菜单类无算子),
    "parent":    None 或 "该子键所属的父操作/键位上下文"(modal 子键专用),
    "rid":       稳定引用(用于“显示表”A 与“数据库”B 关联)
  }

数据库表 B 在三个刷新点由 keyconfig 全量重建(见 core.py / builder)。本模块提供
  1) 记录构建与键/修饰键的规范化、格式化;
  2) 当前上下文(mode + space)解析成一组官方模式标签;
  3) 查询：按 模式标签 x 选中状态 x 当前父操作 x 按住修饰键 过滤排序。
所有函数纯函数式，便于无头单测。
"""

import json
import os

# ---- 修饰键 ----
_MOD_ATTRS = (("ctrl", "Ctrl"), ("shift", "Shift"),
              ("alt", "Alt"), ("oskey", "OS"))
MOD_NAMES = tuple(n for _a, n in _MOD_ATTRS)
_ATTR_BY_NAME = {n: a for a, n in _MOD_ATTRS}
_NAME_BY_ATTR = dict(_MOD_ATTRS)

# ---- 官方表里的模式标签，与修饰键串 ----
TAG_GLOBAL = "global"
TAG_3D = "3d_viewport"
TAG_COMMON = "common_editor"
TAG_OBJECT = "object"
TAG_EDIT = "edit"

# context.mode 字符串 -> 官方模式标签
MODE_TO_TAG = {
    "OBJECT": TAG_OBJECT,
    "EDIT_MESH": TAG_EDIT,
    "EDIT_CURVE": TAG_EDIT,
    "EDIT_SURFACE": TAG_EDIT,
    "EDIT_FONT": TAG_EDIT,
    "EDIT_METABALL": TAG_EDIT,
    "EDIT_LATTICE": TAG_EDIT,
    "EDIT_ARMATURE": TAG_EDIT,
    "EDIT_GPENCIL": TAG_EDIT,
    "SCULPT": TAG_OBJECT,
    "VERTEX_PAINT": TAG_OBJECT,
    "WEIGHT_PAINT": TAG_OBJECT,
    "TEXTURE_PAINT": TAG_OBJECT,
}

# 修饰键串(官方表用) -> 规范修饰键显示列表
_MOD_STR = {
    "none": [], "ctrl": ["Ctrl"], "shift": ["Shift"], "alt": ["Alt"],
    "ctrl_shift": ["Ctrl", "Shift"],
    "ctrl_alt": ["Ctrl", "Alt"], "shift_alt": ["Shift", "Alt"],
    "ctrl_shift_alt": ["Ctrl", "Shift", "Alt"],
}


# ---------------------------------------------------------------------------
# 修饰键 / 按键格式化 -------------------------------------------------------
# ---------------------------------------------------------------------------
def mod_attrs_to_names(attrs):
    """{'ctrl','shift',...} -> ['Ctrl','Shift'](规范顺序)."""
    return [name for attr, name in _MOD_ATTRS if attr in (attrs or ())]


def key_display_name(token):
    """把 Blender 的 event type 字符串变成可读按键名."""
    token = str(token or "")
    if not token:
        return ""
    low = token.lower()
    if "leftmouse" in low:
        return "鼠标左键"
    if "rightmouse" in low:
        return "鼠标右键"
    if "middlemouse" in low or low == "wheelinmouse" or low == "wheeloutmouse":
        if "wheelin" in low:
            return "鼠标滚轮 ↑"
        if "wheelout" in low:
            return "鼠标滚轮 ↓"
        return "鼠标中键"
    if low in ("wheelupmouse", "wheeldownmouse"):
        return "鼠标滚轮"
    if low.startswith("numpad_"):
        return "Numpad " + token[len("NUMPAD_"):]
    if low.startswith("pad"):
        return "Numpad " + token[3:]
    if token in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9",
                 "F10", "F11", "F12"):
        return token
    for prefix in ("LEFT_", "RIGHT_"):
        if token.startswith(prefix):
            return token[len(prefix):].title()
    if token == "OSKEY":
        return "Super"
    if token == "SPACE":
        return "Spacebar"
    if token == "RET":
        return "回车"
    if token == "ESC":
        return "Esc"
    if len(token) == 1 and token.isalnum():
        return token
    return token.title()


def combo_text(mods, key):
    mods = mods or []
    key = str(key or "")
    if mods:
        return " + ".join(list(mods) + [key])
    return key


def canonical_mods_from_str(s):
    """'ctrl_shift' / 'Shift + Ctrl' / ['Shift','Ctrl'] -> ['Ctrl','Shift']."""
    if s is None:
        return []
    if isinstance(s, (list, tuple)):
        names = [str(x) for x in s]
    else:
        names = []
        for part in str(s).replace("_", "+").replace(" + ", "+").split("+"):
            part = part.strip()
            if part:
                names.append(part)
    out = []
    for canon in MOD_NAMES:
        for n in names:
            if n.strip().lower() == canon.lower() and canon not in out:
                out.append(canon)
    return out


# ---------------------------------------------------------------------------
# 上下文 -> 官方模式标签 -----------------------------------------------------
# ---------------------------------------------------------------------------
def active_tags(context_mode, space_type="VIEW_3D"):
    """当前 mode 字符串 + space -> 激活的官方标签集合(global 永远有)."""
    tags = {TAG_GLOBAL}
    st = (space_type or "").upper()
    if st == "VIEW_3D":
        tags.add(TAG_3D)
        tags.add(TAG_COMMON)
        tag = MODE_TO_TAG.get((context_mode or "").upper())
        if tag:
            tags.add(tag)
    else:
        # 其它编辑器至少算公共编辑环境。
        tags.add(TAG_COMMON)
    return tags


# ---------------------------------------------------------------------------
# 官方表读取 -----------------------------------------------------------------
# ---------------------------------------------------------------------------
def load_official_rows(path=None):
    """读 data/blender_default.json，返回规范 record 列表(纯数据，键为文档默认)."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "blender_default.json")
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    data = doc.get("blender_default_keymap", {}).get("keymap", doc)
    rows = []
    for group in data:
        tag = group.get("mode")
        mods = canonical_mods_from_str(group.get("modifier_keys", "none"))
        sel = group.get("selection_state", "any")
        for s in group.get("shortcuts", []):
            rows.append({
                "tags": {tag} if tag else set(),
                "sel": sel,
                "mods": list(mods),
                "key": s.get("key", ""),
                "name": s.get("function", ""),
                "op": None,
                "parent": None,
                "note": s.get("note", ""),
            })
    return rows


# ---------------------------------------------------------------------------
# 查询 -----------------------------------------------------------------------
# ---------------------------------------------------------------------------
def match_record(rec, active, sel_present, held=None, parent=None):
    """单条 record 是否在当前上下文命中.

    active    : 激活标签集合
    sel_present: 是否选中了物体/点线面(Blender 实测)
    held      : 当前按住的修饰键属性集合(如 {'shift'})；None = 不筛修饰键
    parent    : 当前运行的父操作/键位上下文(子键专用)；None=只看无父的基础项
    """
    # 1) 父操作过滤：默认只看基础项；子键只在对应父操作运行时显示。
    rec_parent = rec.get("parent")
    if parent is None:
        if rec_parent is not None:
            return False
    else:
        if rec_parent != parent:
            return False
    # 2) 标签命中(至少一个激活标签在记录标签里)。
    rec_tags = rec.get("tags") or set()
    if rec_tags and not (rec_tags & set(active or ())):
        return False
    # 3) 选中状态：仅对基础项(无父)生效；子键项意味着已先选中再进入操作。
    if rec.get("parent") is None and \
            rec.get("sel") == "selected" and not sel_present:
        return False
    # 4) 修饰键过滤(仅当传入 held 时才启用)。held 是修饰键 *属性*集合，如
    #    {'shift'}，与 core._held_mods 一致。
    if held is not None:
        rec_attrs = {_ATTR_BY_NAME.get(n, n.lower()) for n in (rec.get("mods") or [])}
        if held:
            if not rec_attrs.issuperset(set(held)):
                return False
        else:
            if rec_attrs:
                return False
    return True


def query(records, active, sel_present, held=None, parent=None,
          by_group=True):
    """对 records 过滤并返回 [record,...]，可选按修饰键分组。

    held 属性集合 e.g. {'shift'}；None = 不过滤修饰键(由调用方决定分组)。
    """
    out = [r for r in records if match_record(
        r, active, sel_present, held=held, parent=parent)]
    if by_group:
        out.sort(key=lambda r: _group_key(r.get("mods") or []))
    else:
        out.sort(key=lambda r: (r.get("name") or "", _groupless(r)))
    return out


def _group_key(mods):
    mods = mods or []
    if not mods:
        return (0, 0, "")
    name = mods[0]
    rank = {"Ctrl": 1, "Shift": 2, "Alt": 3}.get(name, 4)
    return (rank, len(mods), name)


def _groupless(r):
    return combo_text(r.get("mods"), r.get("key"))


def group_name(mods):
    mods = mods or []
    if not mods:
        return "无按键"
    if len(mods) == 1:
        return mods[0]
    return " + ".join(mods)
