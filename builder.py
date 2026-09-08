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
数据库表 B 的构建器。

B 在三个刷新点(启动 / 增删键位 / keymap 变化)从 **活动 keyconfig** 全量读取重建：
  * 键盘 + 鼠标 + 特殊键 + modal(子键) 键位都覆盖；
  * 每条 keymap_item 转成 engine 记录：tags(模式)、sel、mods、key、name、op、
    parent(modal 键位里的条目标记为所属键位的子键)。

GUI 读取(read_keyconfig_snapshot)只在真实会话有数据(background 下 items 为空)。
为便于测试，把「原始绑定 dict -> 记录」的映射做成纯函数 items_to_records()，
可喂合成原始数据做无头单测。
"""

import json
import os

import bpy

from . import engine
from . import library


def maintained_path():
    """维护后 B 表的落盘位置(用户配置目录 key_hint/b_database.json)."""
    try:
        base = bpy.utils.user_resource("CONFIG", path="key_hint")
    except Exception:                        # noqa: BLE001
        base = os.path.join(os.path.expanduser("~"), ".config", "key_hint")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:                        # noqa: BLE001
        pass
    return os.path.join(base, "b_database.json")


def _to_plain(records):
    """把记录转成可 JSON 序列化的普通 dict(tags 集合->排序 list)."""
    out = []
    for r in library.ensure_rids([dict(x) for x in records]):
        out.append({
            "rid": r.get("rid", ""),
            "tags": sorted(r.get("tags") or ()),
            "sel": r.get("sel", "any"),
            "mods": list(r.get("mods") or []),
            "key": r.get("key", ""),
            "name": r.get("name", ""),
            "op": r.get("op", ""),
            "parent": r.get("parent"),
            "km": r.get("km"),
        })
    return out


def save_maintained(records, path=None):
    """把 B 表(带 rid 的 engine 记录)写入维护文件."""
    path = path or maintained_path()
    plain = _to_plain(records)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"schema": "key_hint_b", "count": len(plain),
                   "records": plain}, fh, ensure_ascii=False, indent=2)
    return path


def load_maintained(path=None):
    """读取维护文件里的 B 表；没有/损坏返回 None."""
    path = path or maintained_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        recs = doc.get("records")
        if not isinstance(recs, list):
            return None
        out = []
        for r in recs:
            if not isinstance(r, dict):
                continue
            r2 = dict(r)
            r2["tags"] = set(r2.get("tags") or ())
            r2["mods"] = list(r2.get("mods") or [])
            out.append(r2)
        return library.ensure_rids(out)
    except Exception:                        # noqa: BLE001
        return None

# keymap 名 -> 官方模式标签的启发式映射(够用即可，后续可按 Blender 内部 keymap
# 树再精化)。
_KEYMAP_TAG_HINT = {
    "Object Mode": {"object"},
    "Object Non-modal": {"object"},
    "Mesh": {"edit"},
    "Curve": {"edit"},
    "Surface": {"edit"},
    "Metaball": {"edit"},
    "Lattice": {"edit"},
    "Armature": {"edit"},
    "Font": {"edit"},
    "Pose": {"edit"},
    "3D View": {"3d_viewport"},
    "3D View Generic": {"3d_viewport"},
    "Grease Pencil": {"edit"},
    "Grease Pencil Stroke Edit Mode": {"edit"},
    "Sculpt": {"object"},
    "Vertex Paint": {"object"},
    "Weight Paint": {"object"},
    "Image Paint": {"object"},
    "Particle": {"object"},
    "Window": set(),
    "Screen": set(),
    "Screen Editing": set(),
    "Animation": set(),
    "Frames": set(),
    "Markers": set(),
    "User Interface": set(),
}

# 一些全局键位名也归入 global。
_GLOBAL_NAMES = {"Window", "Screen", "Screen Editing", "Animation", "Frames",
                 "Markers", "User Interface", "Global Map", "Property Editor",
                 "Outliner", "File Browser", "File Browser Main", "Console",
                 "Text", "Text Generic"}

# 鼠标键我们也展示(引擎能把它们格式化成中文)。
_MOUSE_TYPES = {"ACTIONMOUSE", "SELECTMOUSE", "EVT_TWEAK_L", "EVT_TWEAK_M",
                "EVT_TWEAK_R", "INBETWEEN_MOUSEMOVE"}

_VALID_MAP_TYPES = {"KEYBOARD", "MOUSE", "TWEAK", "TEXTINPUT", "KEYBOARD_MODIFIER"}


def _norm_value(value):
    return (value or "").upper() if isinstance(value, str) else value


def keymap_tags(km_name, is_modal=False):
    """按 keymap 名给出官方标签集合(启发式)."""
    if is_modal:
        # modal 键位的条目是“某个操作进行中的子键”：不给普通模式标签，由
        # 调用方按 parent 单独归组。
        return set()
    if km_name in _GLOBAL_NAMES or km_name in _KEYMAP_TAG_HINT and not \
            _KEYMAP_TAG_HINT[km_name]:
        return {engine.TAG_GLOBAL}
    tags = set(_KEYMAP_TAG_HINT.get(km_name, set()))
    # 名字含 "Object Mode"/"Mesh" 之类再兜底
    low = (km_name or "").lower()
    if not tags:
        if "object" in low:
            tags.add(engine.TAG_OBJECT)
        elif "edit" in low or "mesh" in low or "curve" in low:
            tags.add(engine.TAG_EDIT)
        if km_name and not _is_utility(km_name):
            tags.add(engine.TAG_COMMON)
    return tags or {engine.TAG_COMMON}


def _is_utility(km_name):
    low = (km_name or "").lower()
    return any(k in low for k in ("file", "console", "property", "outliner",
                                  "text", "ndof", "gesture", "clip", "uv",
                                  "node", "graph", "dopesheet", "nla",
                                  "image", "sequencer", "video", "spreadsheet",
                                  "preferences", "userpref", "frames",
                                  "animation"))


def _usable(it):
    """原始绑定是否可作为一条可展示快捷键."""
    mt = (it.get("map_type") or "").upper()
    if mt and mt not in _VALID_MAP_TYPES:
        return False
    if mt in ("MOUSE", "TWEAK"):
        # 鼠标类我们只留 ACTION/SELECT 左键触发，太碎的去重交给上层
        pass
    val = _norm_value(it.get("value"))
    if val not in ("PRESS", "ANY", ""):
        return False
    typ = it.get("type")
    if not typ or str(typ) in ("NONE", "TIMER", "MOUSEMOVE",
                               "INBETWEEN_MOUSEMOVE", "WINDOW_DEACTIVATE"):
        return False
    return True


def items_to_records(raw_items, label_fn=None):
    """把原始绑定 dict 列表转成 engine 记录列表(纯函数，可无头测试).

    每条 raw dict：
      {km_name, is_modal, op, name, type, value, map_type,
       mods:['ctrl','shift',...](属性名), props:{...}}
    """
    out = []
    seen = set()
    for it in raw_items:
        if not _usable(it):
            continue
        typ = it.get("type")
        mods = engine.mod_attrs_to_names(it.get("mods") or ())
        tags = keymap_tags(it.get("km_name"), it.get("is_modal", False))
        name = it.get("name") or it.get("op") or ""
        if label_fn and it.get("op"):
            name = label_fn(it.get("op"), fallback=name) or name
        key = engine.key_display_name(typ)
        if not key:
            continue
        parent = it.get("parent")
        if it.get("is_modal") and not parent:
            parent = it.get("km_name")        # modal 子键归属其父键位
        rec = {
            "tags": set(tags),
            "sel": "any",
            "mods": list(mods),
            "key": key,
            "name": name,
            "op": it.get("op") or "",
            "parent": parent,
            "km": it.get("km_name"),
        }
        dedupe = (rec["op"], rec["km"], tuple(mods), str(typ),
                  rec.get("parent"))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append(rec)
    return out


def read_keyconfig_snapshot():
    """GUI：读取活动 keyconfig 的全部绑定为原始 dict 列表。

    仅在正常图形会话有内容；background/headless 下 keymap_items 为空，返回 []。
    """
    wm = bpy.context.window_manager
    kc = getattr(wm.keyconfigs, "active", None)
    if kc is None:
        kc = getattr(wm.keyconfigs, "Blender", None)
    if kc is None:
        return []
    raw = []
    try:
        for km in kc.keymaps:
            is_modal = bool(getattr(km, "is_modal", False))
            km_name = getattr(km, "name", "")
            for it in km.keymap_items:
                op = getattr(it, "idname", "") or ""
                raw.append({
                    "km_name": km_name,
                    "is_modal": is_modal,
                    "op": op,
                    "name": getattr(it, "name", "") or "",
                    "type": getattr(it, "type", None),
                    "value": getattr(it, "value", None),
                    "map_type": getattr(it, "map_type", None),
                    "mods": [a for a, _n in (("ctrl", 0), ("shift", 0),
                                             ("alt", 0), ("oskey", 0))
                             if getattr(it, a, False)],
                    "active": bool(getattr(it, "active", True)),
                })
    except Exception:                            # noqa: BLE001
        pass
    return [r for r in raw if r.get("active", True)]


def _localized(op, fallback):
    """界面语言算子名(匹配不到回退 raw name)."""
    if not op:
        return fallback
    try:
        from . import hints
        return hints.localized_operator_label(op, fallback=fallback)
    except Exception:                        # noqa: BLE001
        return fallback


def sync_database(records_out=None):
    """三个刷新点调用：返回数据库表 B(engine 记录 + rid).

    先把 keyconfig 全量转记录(功能名用界面语言算子名，键为真实绑定)；当读不到
    真实键位(background/空)时回退到官方表种子，保证至少有内容。
    """
    snapshot = read_keyconfig_snapshot()
    items = items_to_records(
        snapshot, label_fn=lambda op, fallback: _localized(op, fallback))
    if items:
        return items
    # 回退：官方中文种子(记录用官方文档键)
    return engine.load_official_rows()


def real_binding_for(op):
    """GUI：查某算子当前在活动 keyconfig 的真实绑定 -> (mods_names, key) 或 None."""
    if not op:
        return None
    try:
        wm = bpy.context.window_manager
        kc = getattr(wm.keyconfigs, "active", None) or \
            getattr(wm.keyconfigs, "Blender", None)
        if kc is None:
            return None
        for km in kc.keymaps:
            if getattr(km, "is_modal", False):
                continue
            for it in km.keymap_items:
                if not getattr(it, "active", True):
                    continue
                if getattr(it, "idname", "") != op:
                    continue
                if getattr(it, "map_type", None) not in ("KEYBOARD", "MOUSE"):
                    continue
                if getattr(it, "value", None) not in ("PRESS", "ANY"):
                    continue
                attrs = [a for a, _n in (("ctrl", 0), ("shift", 0),
                                         ("alt", 0), ("oskey", 0))
                         if getattr(it, a, False)]
                return (engine.mod_attrs_to_names(attrs),
                        engine.key_display_name(getattr(it, "type", None)))
    except Exception:                        # noqa: BLE001
        pass
    return None


def sync_and_save(out=None):
    """正常流程里的同步动作：读 keyconfig → 全量转记录 → 写入 B 维护文件。

    返回写入条数；读不到真实键位(GUI 外/空)返回 0 且不落盘。
    """
    snapshot = read_keyconfig_snapshot()
    if not snapshot:
        return 0
    records = items_to_records(
        snapshot, label_fn=lambda op, fallback: _localized(op, fallback))
    if not records:
        return 0
    save_maintained(records, out)
    return len(records)
