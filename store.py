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
“保留集合”(kept set) —— 全局 JSON，引用真实快捷键，而不是文本。

用户勾选保留的每一项都是对**某个真实快捷键的引用**，不存手写功能名/按键文本：
  {
    "uid":  稳定 id
    "name": 显示用功能名（默认取自 Kurt 中文清单 / 搜索时取自算子的本地化名）
    "op":   真实算子 idname，例如 "transform.translate"
    "keymap": 所属 keymap 名（用于定位），可空 = 按模式扫描
    "mode": "ALL" | "OBJECT" | "EDIT" —— 该保留项在哪些模式展示
    "props": {算子属性:值,...}，用于在同 idname 里进一步定位（例如 view_axis 的 axis）
  }

显示的按键 **从不来自这里** —— 每个条目渲染时用 store.binding_for() 去实时扫描
keyconfig，得到当前真实绑定的修饰键+按键。所以用户改键后，HUD/侧栏自动跟随。

默认“拥有”条目从 Kurt 中文清单读取功能名（作为引用默认项），按键仍扫描。本模块的
纯函数（默认清单、判同/判在集合、按模式过滤、按修饰键分组）可在无头下测试；扫描
函数依赖真实 GUI keyconfig，仅在那里生效。
"""

import json
import os
import uuid

# 条目"属于"哪些当前模式组。ALL=任何模式都展示该保留项。
ALL = "ALL"
OBJECT = "OBJECT"
EDIT = "EDIT"
MODE_SCOPE = (ALL, OBJECT, EDIT)

# 修饰键显示文本规范顺序。
MOD_NAMES = ("Ctrl", "Shift", "Alt", "OS")
# 修饰键属性名 -> 显示文本。
_MOD_ATTR = (("ctrl", "Ctrl"), ("shift", "Shift"),
             ("alt", "Alt"), ("oskey", "OS"))

_GROUP_NO_MOD = "无按键"
_GROUP_SHIFT = "Shift"
_GROUP_CTRL = "Ctrl"
_GROUP_ALT = "Alt"


def _uid():
    return uuid.uuid4().hex


def _norm_mod_name(m):
    s = str(m or "").strip().lower()
    for canon in ("Ctrl", "Shift", "Alt", "OS"):
        if s.startswith(canon.lower()) or s in ("oskey", "super", "os"):
            return canon
    return str(m or "").strip()


def norm_mods(mods):
    """Dedup + canonical-order a modifier token list."""
    if not mods:
        return []
    out = []
    for canon in MOD_NAMES:
        for m in mods:
            if _norm_mod_name(m) == canon and canon not in out:
                out.append(canon)
    return out


def make_entry(name, op, mode=ALL, keymap="", props=None, uid=None):
    return {
        "uid": uid or _uid(),
        "name": str(name or "").strip(),
        "op": str(op or "").strip(),
        "keymap": str(keymap or "").strip(),
        "mode": mode if mode in MODE_SCOPE else ALL,
        "props": dict(props or {}),
    }


# ---------------------------------------------------------------------------
# 身份 / 判在集合 -----------------------------------------------------------
# ---------------------------------------------------------------------------
def identity(entry):
    """Structural key of an entry: same (op, mode, keymap, props) == same
    real shortcut, so search results can tell whether an item is already kept.
    """
    props = tuple(sorted((entry.get("props") or {}).items()))
    return (entry.get("op", ""), entry.get("mode", ALL),
            entry.get("keymap", ""), props)


def index_of(entries, entry):
    """Index of the kept entry whose identity matches *entry*, or -1."""
    want = identity(entry)
    for i, e in enumerate(entries):
        if identity(e) == want:
            return i
    return -1


def contains(entries, entry):
    return index_of(entries, entry) >= 0


def add(entries, entry):
    """Return a new list with *entry* appended at the end (no-op if kept)."""
    if contains(entries, entry):
        return entries
    return list(entries) + [make_entry(entry.get("name", ""), entry.get("op", ""),
                                       entry.get("mode", ALL),
                                       entry.get("keymap", ""),
                                       entry.get("props"))]


def remove(entries, uid):
    """Return a new list with the entry whose uid == *uid* removed entirely."""
    return [e for e in entries if e.get("uid") != uid]


def remove_matching(entries, entry):
    """Return a new list with the kept entry matching *entry*'s identity removed."""
    want = identity(entry)
    return [e for e in entries if identity(e) != want]


def contains_op(entries, op):
    """True if some kept entry references *op* (props-insensitive)."""
    op = op or ""
    return any(e.get("op", "") == op for e in entries)


def remove_op(entries, op):
    """Return a new list with all kept entries referencing *op* removed."""
    op = op or ""
    return [e for e in entries if e.get("op", "") != op]


# ---------------------------------------------------------------------------
# 默认“拥有”清单（Kurt 中文功能名 -> 真实算子引用；按键靠扫描）
# ---------------------------------------------------------------------------
DEFAULT_ITEMS = [
    # ---- 视图 / 视角（所有模式都常见）-----------------------------------
    dict(name="顶视图", op="view3d.view_axis", mode=ALL,
         props={"axis": "TOP"}),
    dict(name="前视图", op="view3d.view_axis", mode=ALL,
         props={"axis": "FRONT"}),
    dict(name="右视图", op="view3d.view_axis", mode=ALL,
         props={"axis": "RIGHT"}),
    dict(name="底视图", op="view3d.view_axis", mode=ALL,
         props={"axis": "BOTTOM"}),
    dict(name="后视图", op="view3d.view_axis", mode=ALL,
         props={"axis": "BACK"}),
    dict(name="左视图", op="view3d.view_axis", mode=ALL,
         props={"axis": "LEFT"}),
    dict(name="正交/透视切换", op="view3d.view_persportho", mode=ALL),
    dict(name="摄像机视角", op="view3d.view_camera", mode=ALL),
    dict(name="视角聚焦到所选", op="view3d.view_selected", mode=ALL),

    # ---- 物体 / 变换 -----------------------------------------------------
    dict(name="移动", op="transform.translate", mode=ALL),
    dict(name="旋转", op="transform.rotate", mode=ALL),
    dict(name="缩放", op="transform.resize", mode=ALL),
    dict(name="删除", op="object.delete", mode=ALL),
    dict(name="复制", op="object.duplicate_move", mode=OBJECT),
    dict(name="新建物体", op="object.collection_instance_add", mode=OBJECT),
    dict(name="全选/取消全选", op="object.select_all", mode=OBJECT),
    dict(name="隐藏", op="object.hide_view_set", mode=OBJECT),
    dict(name="编辑/物体切换", op="object.editmode_toggle", mode=ALL),

    # ---- 编辑（网格）----------------------------------------------------
    dict(name="挤出", op="mesh.extrude_region_move", mode=EDIT),
    dict(name="内插面", op="mesh.inset", mode=EDIT),
    dict(name="环切", op="mesh.loopcut_slide", mode=EDIT),
    dict(name="倒角", op="mesh.bevel", mode=EDIT),
    dict(name="合并", op="mesh.merge", mode=EDIT),
    dict(name="断开", op="mesh.rip_move", mode=EDIT),
    dict(name="切刀", op="mesh.knife_tool", mode=EDIT),
    dict(name="分离", op="mesh.split", mode=EDIT),

    # ---- 通用 ------------------------------------------------------------
    dict(name="渲染图像", op="render.render", mode=ALL),
]


def default_entries():
    return [make_entry(d["name"], d["op"], d.get("mode", ALL),
                       d.get("keymap", ""), d.get("props", {}))
            for d in DEFAULT_ITEMS]


# ---------------------------------------------------------------------------
# 模式相关（保留项在哪些当前模式展示）
# ---------------------------------------------------------------------------
def _is_edit(mode):
    mode = (mode or "").upper()
    return mode.startswith("EDIT_") or mode in ("EDIT",)


def shown_in(entry, mode):
    """Whether *entry* belongs to the given current *mode*."""
    scope = entry.get("mode", ALL)
    mode = (mode or "").upper()
    if scope == ALL:
        return True
    if scope == OBJECT:
        return mode == "OBJECT"
    if scope == EDIT:
        return _is_edit(mode)
    return True


def filter_mode(entries, mode):
    return [e for e in entries if shown_in(e, mode)]


# ---------------------------------------------------------------------------
# 修饰键相关（HUD “基础 / 按住修饰键” 分组）
# ---------------------------------------------------------------------------
def base_entries(entries):
    """Retained entries that are reachable with no modifier held.

    A shortcut is “base” if its binding carries no required modifier.  Binding
    data is scanned (see binding_for); if we cannot scan (headless / no item)
    we fall back to ``dkey/dmods`` carried as identity hints on the entry.
    """
    out = []
    for e in entries:
        mods = binding_mods(e)
        if not mods:
            out.append(e)
    return out


def modifier_entries(entries, held_attrs):
    """Retained entries whose binding requires *every* held modifier.

    ``held_attrs`` is a set of modifier attribute names currently held, e.g.
    {"shift"}.  Only entries whose scanned binding starts with those modifiers
    are returned (holding Shift shows Shift+... combos; holding Ctrl+Shift shows
    Ctrl+Shift+...).  This never fabricates impossible combos: it only reflects
    real bindings.
    """
    held = set(held_attrs or ())
    if not held:
        return []
    out = []
    for e in entries:
        mods = binding_mods(e)
        if not mods:
            continue
        attrs = _attrs_of(mods)
        if held.issubset(attrs):
            out.append(e)
    return out


def _attrs_of(mods):
    out = set()
    for attr, name in _MOD_ATTR:
        for m in mods:
            if m == name:
                out.add(attr)
    return out


def _scan_binding(entry):
    """Best-effort scan of *entry*'s current binding.

    Returns (mods_display_list, key_display).  In a real GUI session we scan the
    keyconfig via hints; headless (no items) returns (entry-hint, None) so the
    pure helpers still have something deterministic to work with.
    """
    import bpy
    from . import hints
    mode = entry.get("mode", ALL)
    # A keymap name is the most precise locator; else let the mode drive it.
    try:
        bind = hints.find_binding(entry)
    except Exception:                        # noqa: BLE001
        bind = None
    if bind is not None:
        return bind
    # Headless fallback: no real binding available.
    return (norm_mods(entry.get("dmods") or []), entry.get("dkey") or None)


_binding_cache = {}


def _binding(entry):
    key = identity(entry)
    b = _binding_cache.get(key)
    if b is None:
        b = _scan_binding(entry)
        _binding_cache[key] = b
    return b


def binding_mods(entry):
    return _binding(entry)[0] or []


def binding_key(entry):
    return _binding(entry)[1]


def combo_text(entry):
    """Display combo for *entry* using its scanned binding (mods + key)."""
    mods = binding_mods(entry)
    key = binding_key(entry) or "?"
    if mods:
        return " + ".join(list(mods) + [str(key)])
    return str(key)


def group_name_of(entry):
    """Group header for an entry based on its scanned modifiers."""
    mods = binding_mods(entry)
    if not mods:
        return _GROUP_NO_MOD
    if mods == ["Ctrl"]:
        return _GROUP_CTRL
    if mods == ["Shift"]:
        return _GROUP_SHIFT
    if mods == ["Alt"]:
        return _GROUP_ALT
    return " + ".join(mods)


# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------
_SCHEMA_VERSION = 2
_cache = {}


def entries_path():
    try:
        import bpy
        base = bpy.utils.user_resource("CONFIG", path="key_hint")
    except Exception:                        # noqa: BLE001
        base = os.path.join(os.path.expanduser("~"), ".config", "key_hint")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:                        # noqa: BLE001
        pass
    return os.path.join(base, "kept.json")


def _serialize(entries):
    return {"schema_version": _SCHEMA_VERSION,
            "entries": [make_entry(e.get("name", ""), e.get("op", ""),
                                   e.get("mode", ALL), e.get("keymap", ""),
                                   e.get("props"), e.get("uid"))
                        for e in entries]}


def _deserialize(data):
    raw = data.get("entries")
    if not isinstance(raw, list):
        return []
    out = []
    for e in raw:
        if not isinstance(e, dict):
            continue
        out.append(make_entry(e.get("name", ""), e.get("op", ""),
                              e.get("mode", ALL), e.get("keymap", ""),
                              e.get("props"), e.get("uid")))
    return out


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return -1


def load(path=None, seed=True):
    path = path or entries_path()
    hit = _cache.get(path)
    cur = _mtime(path)
    if hit and hit[0] == cur:
        return [dict(e) for e in hit[1]]
    data = None
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = _deserialize(json.load(fh))
        except Exception:                    # noqa: BLE001
            data = None
    if data is None:
        data = default_entries()
        if seed:
            try:
                save(data, path)
            except Exception:                # noqa: BLE001
                pass
    _cache[path] = (_mtime(path), [dict(e) for e in data])
    return [dict(e) for e in data]


def save(entries, path=None):
    path = path or entries_path()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_serialize(entries), fh, ensure_ascii=False, indent=2)
    _cache.pop(path, None)
    return path
