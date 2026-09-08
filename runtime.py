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
运行时：显示表 A(内容) 与数据库 B(真实键回填)。

内容/显示：
  * 内容 = content.py 的 curated 清单(默认)，每条是“匹配项”(function/mode/sel)。
  * 显示的 修饰键+按键 = 该条 op 在活动 keyconfig 的真实绑定(builder.real_binding_for)；
    没有 op/读不到(如 headless)就用内容里的文档默认键。
  * 显示表 A = 有序 rid 列表(默认=curated 全显；可隐藏/重显)，持久化。

数据库 B 指用于回填真实键的 keyconfig(由 builder 提供)；它决定键，不决定“显示哪些”。
惰性加载：第一次真正需要时才构建；background 下不落盘、不读 keyconfig。
"""

import json
import os

import bpy

from . import engine
from . import library
from . import builder
from . import content


_DB = None          # 内容记录(带 rid；键=文档默认/已回填真实)
_A = None           # 显示表 A：有序 rid
_EXTRAS = None      # 用户从 B 加入并持久化的额外记录(带 rid)
_LOADED = False
_KEYED = False      # 是否已用真实 keyconfig 回填


def reset():
    global _DB, _A, _EXTRAS, _LOADED, _KEYED
    _DB = None
    _A = None
    _EXTRAS = None
    _LOADED = False
    _KEYED = False


def _extras_path():
    try:
        base = bpy.utils.user_resource("CONFIG", path="key_hint")
    except Exception:                        # noqa: BLE001
        base = os.path.join(os.path.expanduser("~"), ".config", "key_hint")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:                        # noqa: BLE001
        pass
    return os.path.join(base, "extras.json")


def _load_extras():
    p = _extras_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        recs = doc.get("records")
        return library.ensure_rids([
            {**dict(r), "tags": set(r.get("tags") or ()),
             "mods": list(r.get("mods") or [])} for r in (recs or [])
            if isinstance(r, dict)])
    except Exception:                        # noqa: BLE001
        return []


def _save_extras():
    if bpy.app.background:
        return
    try:
        plain = [dict(r, tags=sorted(r.get("tags") or ())) for r in _EXTRAS]
        with open(_extras_path(), "w", encoding="utf-8") as fh:
            json.dump({"records": plain}, fh, ensure_ascii=False, indent=2)
    except Exception:                        # noqa: BLE001
        pass


def _content_records():
    return library.ensure_rids(content.load_content())


def _apply_real_keys(records):
    """GUI：给带 op 的记录回填真实 keyconfig 绑定(改键即随)。"""
    for r in records:
        if not r.get("op"):
            continue
        try:
            b = builder.real_binding_for(r["op"])
        except Exception:                    # noqa: BLE001
            b = None
        if b and b[0] is not None:
            r["mods"] = b[0]
            r["key"] = b[1] or r["key"]


def _merge_extras(base):
    """content 记录 + 用户从 B 加入的额外记录(按 rid 去重，保序)."""
    out = list(base)
    seen = {library.rid_of(r) for r in out}
    for e in _EXTRAS or []:
        rid = library.rid_of(e)
        if rid not in seen:
            seen.add(rid)
            out.append(dict(e))
    return out


def ensure_loaded():
    global _DB, _A, _EXTRAS, _LOADED, _KEYED
    if _LOADED:
        return
    if _EXTRAS is None:
        _EXTRAS = _load_extras()
    _DB = _merge_extras(_content_records())
    if not bpy.app.background and not _KEYED:
        _apply_real_keys(_DB)
        _KEYED = True
    a = library.load_shown()
    if a is None:
        a = library.default_shown(_DB)
        if not bpy.app.background:
            _persist()
    else:
        db_rids = {library.rid_of(r) for r in _DB}
        a = [rid for rid in a if rid in db_rids]
        # 刚加入的 extras 若尚不在 A，补进去(保持用户“加入即显示”)
        for rid in [library.rid_of(r) for r in _EXTRAS]:
            if rid in db_rids and rid not in a:
                a = list(a) + [rid]
        _A = a
        if not bpy.app.background:
            _persist()
        return
    _A = a
    _LOADED = True


def reload():
    """重建内容+extras 并重新回填真实键；保留 A(仍存在的项)。"""
    global _DB, _A, _KEYED
    if _EXTRAS is None:
        _EXTRAS = _load_extras()
    _DB = _merge_extras(_content_records())
    if not bpy.app.background:
        _apply_real_keys(_DB)
        _KEYED = True
    a = _A if _A is not None else library.load_shown()
    if a is None:
        a = library.default_shown(_DB)
    else:
        db_rids = {library.rid_of(r) for r in _DB}
        a = [rid for rid in a if rid in db_rids]
        for rid in [library.rid_of(r) for r in _EXTRAS]:
            if rid in db_rids and rid not in a:
                a = list(a) + [rid]
    _A = a
    _persist()
    return _A


def sync_now():
    """侧栏“同步数据库”按钮：重建内容 + 真实键回填 + 合并 A。返回可见条数."""
    ensure_loaded()
    reload()
    return len(_A)


def database():
    ensure_loaded()
    return _DB


_POOL = None


def pool():
    """B 表候选池 = keyconfig 全量(builder)，供搜索“加入”。GUI 才有内容。"""
    global _POOL
    if _POOL is None:
        try:
            _POOL = library.ensure_rids(builder.sync_database())
        except Exception:                    # noqa: BLE001
            _POOL = []
    return _POOL


def refresh_pool():
    global _POOL
    _POOL = None


def pool_record(rid):
    return next((r for r in pool() if library.rid_of(r) == rid), None)


def add_from_pool_rid(rid):
    rec = pool_record(rid)
    if rec is None:
        return False
    return add_from_pool(rec)


def add_from_pool(rec):
    """把 B 候选池里的一条加入显示表 A(持久化到 extras)."""
    ensure_loaded()
    global _DB, _A, _EXTRAS
    rid = library.rid_of(rec)
    shown_rids = set(_A)
    if rid in shown_rids:
        return False
    _EXTRAS.append(dict(rec))
    _DB = _merge_extras(_DB)
    _A = list(_A) + [rid]
    _persist()
    _save_extras()
    return True


def shown():
    ensure_loaded()
    return _A


def shown_records():
    ensure_loaded()
    return library.resolve(_DB, _A)


def is_shown(rec):
    ensure_loaded()
    return library.rid_of(rec) in _A


def _persist():
    if not bpy.app.background:
        try:
            library.save_shown(_A)
        except Exception:                    # noqa: BLE001
            pass


def toggle(rec):
    ensure_loaded()
    global _A
    _A = library.toggle(_A, rec)
    _persist()


def hide(rid):
    ensure_loaded()
    global _A
    _A = library.remove(_A, rid)
    _persist()


def show_rid(rid):
    ensure_loaded()
    global _A
    db_rids = {library.rid_of(r) for r in _DB}
    if rid in db_rids and rid not in _A:
        _A = list(_A) + [rid]
        _persist()


def set_default():
    ensure_loaded()
    global _A
    _A = library.default_shown(_content_records())
    _persist()


def query_shown(active_tags, sel_present, held=None, parent=None):
    """A∩内容 在当前上下文下的命中(供 HUD)."""
    ensure_loaded()
    vis = library.resolve(_DB, _A)
    return engine.query(vis, active_tags, sel_present,
                        held=held, parent=parent, by_group=False)


def groups_shown(active_tags, sel_present, held=None, parent=None,
                 search_field=None, search_query="", only_base=False):
    ensure_loaded()
    held_for_filter = set() if only_base else None
    return library.visible_grouped(
        _DB, _A, active_tags, sel_present, held=held_for_filter,
        parent=parent, search_field=search_field, search_query=search_query)
