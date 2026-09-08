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
两表(纯逻辑，可无头测试)：

  * 数据库表 B：完整记录列表(见 engine.py 的记录结构；来源=官方表种子，
    之后在三个刷新点由 keyconfig 全量重建并合并)。每条带稳定的 ``rid``。
  * 显示表 A：用户实际“增删过、实际显示”的有序 rid 集合(其余全表默认显示，
    用户可从中移除，也可从 B 搜索加入)。只持久化 A(rid 列表 + 顺序)。

rid 是“概念稳定标识”(不含 key)：同一概念在用户改键后仍指同一条，便于 B 重建后
A 仍然成立。默认 A = 全表(官方种子先全显示)。

提供：rid_of / ensure_rids / default_shown / resolve / add / remove / toggle /
search / 排序分组所需信息，以及 A 的 save/load。
"""

import json
import os

from . import engine


def rid_of(rec):
    """一条记录的稳定 rid：概念 = (功能名, 命中的模式标签, 修饰键, 是否需要选中,
    父操作)，不含 key——用户改键后仍指同一条。已有 rid 则直接返回."""
    r = rec.get("rid")
    if r:
        return r
    tags = sorted(rec.get("tags") or ())
    mods = list(rec.get("mods") or [])
    key = "|".join([
        str(rec.get("name") or ""),
        ",".join(tags),
        ",".join(mods),
        str(rec.get("sel") or "any"),
        str(rec.get("parent") or ""),
    ])
    return __import__("hashlib").sha1(key.encode("utf-8")).hexdigest()


def ensure_rids(records):
    """原地给没有 rid 的记录补上 rid，返回 records."""
    for r in records:
        r["rid"] = rid_of(r)
    return records


def default_shown(records):
    """默认显示表 A = 全表记录的有序 rid 列表."""
    return [rid_of(r) for r in records]


def resolve(records, a):
    """按 A 的顺序返回 A 中仍存在于 B 的记录(B 重建后会自动丢掉失效项)."""
    by_rid = {}
    order = []
    for r in records:
        rid = rid_of(r)
        if rid not in by_rid:
            by_rid[rid] = r
            order.append(rid)
    return [by_rid[rid] for rid in a if rid in by_rid]


def contains(a, rid):
    return rid in a


def add(a, rec):
    rid = rid_of(rec)
    if rid in a:
        return a
    return list(a) + [rid]


def remove(a, rid):
    return [x for x in a if x != rid]


def toggle(a, rec):
    rid = rid_of(rec)
    if rid in a:
        return [x for x in a if x != rid]
    return list(a) + [rid]


def filter_records(records, field, query):
    """search：field='name' 按功能名、'key' 按按键(串)模糊过滤."""
    q = (query or "").strip().lower()
    out = []
    for r in records:
        if field == "key":
            hay = (engine.combo_text(r.get("mods"), r.get("key"))).lower()
        else:
            hay = (r.get("name") or "").lower()
        if not q or q in hay:
            out.append(r)
    return out


def visible_grouped(records, a, active_tags, sel_present, held=None,
                    parent=None, search_field=None, search_query=""):
    """A 里能显示的记录，先搜索过滤，再按当前上下文过滤并按修饰键分组返回
    [(组名, [记录,...]), ...]."""
    visible = resolve(records, a)
    if search_field:
        visible = filter_records(visible, search_field, search_query)
    hit = engine.query(visible, active_tags, sel_present,
                       held=held, parent=parent, by_group=False)
    groups = {}
    for r in hit:
        g = engine.group_name(r.get("mods") or [])
        groups.setdefault(g, []).append(r)
    ordered = [g for g in ("无按键", "Ctrl", "Shift", "Alt") if g in groups]
    ordered += [g for g in groups if g not in ordered]
    return [(g, groups[g]) for g in ordered]


# ---------------------------------------------------------------------------
# A 持久化(仅存显示表 rid 顺序；B 每次同步重建)
# ---------------------------------------------------------------------------
def shown_path():
    try:
        import bpy
        base = bpy.utils.user_resource("CONFIG", path="key_hint")
    except Exception:                        # noqa: BLE001
        base = os.path.join(os.path.expanduser("~"), ".config", "key_hint")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:                        # noqa: BLE001
        pass
    return os.path.join(base, "shown.json")


def load_shown(path=None):
    path = path or shown_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict):
                return [str(x) for x in data.get("order", [])]
        except Exception:                    # noqa: BLE001
            pass
    return None


def save_shown(a, path=None):
    path = path or shown_path()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"order": list(a)}, fh, ensure_ascii=False, indent=2)
    return path
