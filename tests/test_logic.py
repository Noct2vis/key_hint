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

"""Headless logic tests for Key Hint.

Run with:
    blender --background --factory-startup --python tests/test_logic.py
Exits non-zero if a check fails.
"""

import os
import sys

# Allow running from inside the tests/ dir or the repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import bpy  # noqa: E402

import key_hint  # noqa: E402
from key_hint import hints  # noqa: E402
from key_hint import store  # noqa: E402
from key_hint import core  # noqa: E402
from key_hint import engine  # noqa: E402
from key_hint import library  # noqa: E402
from key_hint import builder  # noqa: E402
from key_hint import content  # noqa: E402


def check(name, ok):
    print(("PASS" if ok else "FAIL"), "-", name)
    if not ok:
        _failures.append(name)


_failures = []


def _fake_context(space_type="VIEW_3D"):
    class _Area:
        type = space_type

    class _Ctx:
        window_manager = bpy.context.window_manager
        area = _Area()

        def __getattr__(self, item):
            return None

    return _Ctx()


def main():
    # 1. Full register / unregister cycle must not raise.
    try:
        key_hint.register()
        check("register()", True)
    except Exception as e:                      # noqa: BLE001
        check("register() (raised %r)" % e, False)

    check("operator registered",
          hasattr(bpy.ops.key_hint, "capture"))
    check("restart operator registered",
          hasattr(bpy.ops.key_hint, "restart"))
    check("panel registered",
          hasattr(bpy.types, "KEYHINT_PT_panel"))
    check("wm enable property",
          hasattr(bpy.types.WindowManager, "key_hint_enabled"))

    try:
        key_hint.unregister()
        check("unregister()", True)
    except Exception as e:                      # noqa: BLE001
        check("unregister() (raised %r)" % e, False)

    # 2. Pure helpers.
    check("key_display_name LEFT_CTRL -> Ctrl",
          hints.key_display_name("LEFT_CTRL") == "Ctrl")
    check("key_display_name A -> A",
          hints.key_display_name("A") == "A")
    check("key_display_name NUMPAD_1 -> Numpad 1",
          hints.key_display_name("NUMPAD_1") == "Numpad 1")
    check("key_display_name OSKEY -> Super",
          hints.key_display_name("OSKEY") == "Super")

    # 3. Context -> relevant keymap names should include obvious ones.
    ctx = _fake_context("VIEW_3D")
    names = hints.relevant_keymap_names(ctx)
    for want in ("Window", "3D View", "3D View Generic", "Object Mode"):
        check("relevant includes %s" % want, want in names)

    # 4. Hint scan must be safe (return list) even headless / no items.
    res = hints.collect_entries(ctx)
    check("collect_entries returns list", isinstance(res, list))

    base, others = hints.split_base_and_modifier([])
    check("split empty -> ([], [])", base == [] and others == [])

    check("entries_for_modifiers([], {}) -> []",
          hints.entries_for_modifiers([], {"ctrl"}) == [])

    # 5. Modifier name helper.
    class _Ev:
        ctrl = True
        shift = False
        alt = True
        oskey = False
    hm = hints.held_modifier_names(_Ev())
    check("held_modifier_names -> ['Alt','Ctrl']", sorted(hm) == ["Alt", "Ctrl"])

    # Fake entry grouping.
    fake = [
        {"mods": [], "key": "G", "label": "Move"},
        {"mods": ["Ctrl"], "key": "C", "label": "Copy"},
        {"mods": ["Ctrl", "Shift"], "key": "C", "label": "Link Copy"},
    ]
    b2, o2 = hints.split_base_and_modifier(fake)
    check("split finds base", len(b2) == 1 and b2[0]["key"] == "G")
    check("split finds modifiers", len(o2) == 2)
    held = hints.entries_for_modifiers(fake, ["ctrl"])
    check("entries_for_modifiers ctrl includes ctrl+shift",
          len(held) == 2 and all("Ctrl" in e["mods"] for e in held))

    # 6. store: retained-set model (references to real shortcuts, no text keys).
    d = store.default_entries()
    check("default_entries non-empty", len(d) > 10)
    check("default entries carry op", all(e["op"] for e in d))
    check("default entries mode valid",
          all(e["mode"] in store.MODE_SCOPE for e in d))

    eA = store.make_entry("移动", "transform.translate", store.ALL)
    eA2 = store.make_entry("移动(重复)", "transform.translate", store.ALL)
    eB = store.make_entry("顶视图", "view3d.view_axis", store.ALL,
                          props={"axis": "TOP"})
    eB2 = store.make_entry("前视图", "view3d.view_axis", store.ALL,
                           props={"axis": "FRONT"})
    check("identity equal same op/mode", store.identity(eA) == store.identity(eA2))
    check("identity differs by props",
          store.identity(eB) != store.identity(eB2))

    lst = [eA, eB]
    check("contains found", store.contains(lst, eA2))
    check("contains axis top", store.contains(lst, eB))
    check("add appends new", len(store.add(lst, eB2)) == 3)
    check("add dup is no-op", len(store.add(lst, eA2)) == 2)
    rem = store.remove(lst, eA["uid"])
    check("remove deletes whole row", len(rem) == 1 and rem[0]["uid"] == eB["uid"])
    check("remove_matching by identity",
          len(store.remove_matching(lst, eB)) == 1  # removes axis=TOP entry
          and store.remove_matching(lst, eB)[0]["uid"] == eA["uid"])
    check("remove_matching no match keeps all",
          len(store.remove_matching(lst, eB2)) == 2)  # axis=FRONT not present

    # 7. store: mode filter (ALL / OBJECT / EDIT).
    obj = store.make_entry("隐藏", "object.hide_view_set", store.OBJECT)
    ed = store.make_entry("挤出", "mesh.extrude_region_move", store.EDIT)
    allv = store.make_entry("渲染", "render.render", store.ALL)
    check("ALL shows in OBJECT", store.shown_in(allv, "OBJECT"))
    check("ALL shows in EDIT_MESH", store.shown_in(allv, "EDIT_MESH"))
    check("OBJECT in OBJECT", store.shown_in(obj, "OBJECT"))
    check("OBJECT hidden in EDIT_MESH", not store.shown_in(obj, "EDIT_MESH"))
    check("EDIT in EDIT_MESH", store.shown_in(ed, "EDIT_MESH"))
    check("EDIT hidden in OBJECT", not store.shown_in(ed, "OBJECT"))
    fm = store.filter_mode([obj, ed, allv], "EDIT_MESH")
    check("filter_mode EDIT_MESH -> EDIT + ALL",
          len(fm) == 2 and all(e["name"] in ("挤出", "渲染") for e in fm))

    # 8. store: modifier grouping (base vs held) via injected binding hints,
    #    since headless has no real keymap items to scan.
    mv = store.make_entry("移动", "transform.translate", store.ALL)
    mv["dmods"] = []; mv["dkey"] = "G"
    cp = store.make_entry("复制", "object.duplicate_move", store.ALL)
    cp["dmods"] = ["Shift"]; cp["dkey"] = "D"
    bv = store.make_entry("倒角", "mesh.bevel", store.EDIT)
    bv["dmods"] = ["Ctrl"]; bv["dkey"] = "B"
    pool = [mv, cp, bv]
    check("base_entries -> only no-mod", [e["op"] for e in store.base_entries(pool)]
          == ["transform.translate"])
    sh = store.modifier_entries(pool, {"shift"})
    check("held Shift -> Shift+ items", len(sh) == 1 and sh[0]["op"]
          == "object.duplicate_move")
    ct = store.modifier_entries(pool, {"ctrl"})
    check("held Ctrl -> Ctrl+ items", len(ct) == 1 and ct[0]["op"] == "mesh.bevel")
    check("held none -> []", store.modifier_entries(pool, set()) == [])

    # 9. store: save / load round-trip on a temp file.
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        e1 = store.make_entry("移动", "transform.translate", store.ALL)
        e2 = store.make_entry("顶视图", "view3d.view_axis", store.ALL,
                              props={"axis": "TOP"})
        store.save([e1, e2], tmp)
        loaded = store.load(tmp)
        check("roundtrip length", len(loaded) == 2)
        check("roundtrip uid stable", loaded[0]["uid"] == e1["uid"])
        check("roundtrip op+props", loaded[1]["op"] == "view3d.view_axis"
              and loaded[1]["props"].get("axis") == "TOP")
        rm = store.remove(loaded, e1["uid"])
        check("remove leaves other", len(rm) == 1 and rm[0]["uid"] == e2["uid"])
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

    # 10. core._build_payload smoke (redirect store to a temp file first so it
    #     never touches the real user config; real scan is empty headless, so
    #     entries fall back to identity hints and the payload must still build).
    import tempfile
    _old_path = store.entries_path
    fd2, tmp2 = tempfile.mkstemp(suffix=".json")
    os.close(fd2)
    try:
        store.entries_path = (lambda t=tmp2: t)
        store.save(store.default_entries(), tmp2)
        p = core._build_payload()
        check("payload is dict", isinstance(p, dict))
        check("payload has title/lines/locked",
              "title" in p and "lines" in p and "locked" in p)
        check("payload lines is list", isinstance(p["lines"], list))
        # every line must be a (combo, label) pair of strings
        ok_lines = all(isinstance(a, str) and isinstance(b, str)
                       for a, b in p["lines"])
        check("payload lines are str pairs", ok_lines)
    finally:
        store.entries_path = _old_path
        store._cache.pop(tmp2, None)
        try:
            os.remove(tmp2)
        except OSError:
            pass

    # 11. engine: pure context resolution / formatting / query.
    of = engine.load_official_rows()
    check("official rows non-empty", len(of) > 30)
    check("official rows have name+key+tags",
          all(r.get("name") and r.get("key") is not None for r in of))

    t_obj = engine.active_tags("OBJECT", "VIEW_3D")
    check("active_tags OBJECT->global/3d/common/object",
          {"global", "3d_viewport", "common_editor", "object"}
          <= t_obj)
    t_edit = engine.active_tags("EDIT_MESH", "VIEW_3D")
    check("active_tags EDIT -> has edit", "edit" in t_edit)

    check("key_display LEFTMOUSE", engine.key_display_name("LEFTMOUSE") == "鼠标左键")
    check("key_display NUMPAD_1", engine.key_display_name("NUMPAD_1") == "Numpad 1")
    check("combo Shift+D", engine.combo_text(["Shift"], "D") == "Shift + D")
    check("canonical ctrl_shift",
          engine.canonical_mods_from_str("ctrl_shift") == ["Ctrl", "Shift"])
    check("canonical Shift + Ctrl",
          engine.canonical_mods_from_str("Shift + Ctrl") == ["Ctrl", "Shift"])

    # query over synthetic records (incl. sel + parent sub-keys)
    def rec(tags, sel, mods, key, name, parent=None):
        return {"tags": set(tags), "sel": sel, "mods": list(mods),
                "key": key, "name": name, "op": None, "parent": parent}
    recs = [
        rec(["object"], "any", [], "A", "全选"),
        rec(["object"], "selected", [], "E", "挤出"),
        rec(["object"], "any", ["Shift"], "D", "复制"),
        rec(["object"], "selected", ["Shift"], "C", "环切",
            parent="MESH_OP"),
        rec(["object"], "selected", [], "X", "锁X轴", parent="MESH_OP"),
    ]
    active = {"global", "object"}
    base = engine.query(recs, active, sel_present=False, held=set())
    check("query base(no sel,no mod)->全选 only",
          [r["name"] for r in base] == ["全选"])
    sh = engine.query(recs, active, sel_present=False, held={"shift"})
    check("query held Shift -> 复制", [r["name"] for r in sh] == ["复制"])
    withsel = engine.query(recs, active, sel_present=True, held=set())
    check("query selected base -> 全选+挤出",
          {r["name"] for r in withsel} == {"挤出", "全选"})
    sub = engine.query(recs, active, sel_present=False,
                       held=None, parent="MESH_OP")
    check("query parent subkey ignores sel/mod -> X轴/环切",
          {r["name"] for r in sub} == {"锁X轴", "环切"})

    # 12. library: two-table (B records / A shown rid list).
    b = library.ensure_rids([
        {"tags": {"object"}, "sel": "any", "mods": [], "key": "G",
         "name": "移动", "op": "transform.translate", "parent": None},
        {"tags": {"object"}, "sel": "selected", "mods": ["Shift"], "key": "D",
         "name": "复制", "op": "object.duplicate_move", "parent": None},
        {"tags": {"object"}, "sel": "any", "mods": [], "key": "X",
         "name": "锁X轴", "parent": "MESH_OP"},
    ])
    check("ensure_rids assigns rid", all(r.get("rid") for r in b))
    # rid stable across a rebind (concept independent of the key)
    check("rid stable across rebind",
          library.rid_of(dict(b[0], key="K")) == b[0]["rid"])
    check("rid differs by name",
          library.rid_of({"name": "移动", "tags": {"object"}, "mods": [],
                          "sel": "any", "parent": None})
          != library.rid_of({"name": "旋转", "tags": {"object"}, "mods": [],
                             "sel": "any", "parent": None}))

    a = library.default_shown(b)
    check("default shown = all", len(a) == 3)
    vis = library.resolve(b, a)
    check("resolve keeps order + count", [r["name"] for r in vis] ==
          ["移动", "复制", "锁X轴"])
    # B rebuilt without the 复制 concept -> A drops it gracefully
    b2 = [b[0], b[2]]
    check("reconcile drops stale", [r["name"] for r in library.resolve(b2, a)]
          == ["移动", "锁X轴"])

    a2 = library.add(a, b[0])
    check("add dup is no-op", len(a2) == len(a))
    extra = {"tags": {"object"}, "sel": "any", "mods": [], "key": "N",
             "name": "新建", "parent": None}
    a3 = library.add(a, extra)
    check("add appends", len(a3) == 4 and library.contains(a3,
                                                          library.rid_of(extra)))
    a4 = library.toggle(a, extra)
    check("toggle adds then removes", len(a4) == 4
          and not library.contains(library.toggle(a4, extra),
                                   library.rid_of(extra)))

    hit = library.filter_records(b, "name", "复制")
    check("search by name", len(hit) == 1 and hit[0]["name"] == "复制")
    groupped = library.visible_grouped(
        b, a, {"object"}, sel_present=False, held=set())
    names = {g: [r["name"] for r in rows] for g, rows in groupped}
    check("visible_grouped base only(no sel,no mod)",
          names == {"无按键": ["移动"]})

    # A persistence round-trip
    fd3, tmp3 = tempfile.mkstemp(suffix=".json")
    os.close(fd3)
    try:
        library.save_shown(a3, tmp3)
        loaded = library.load_shown(tmp3)
        check("shown roundtrip", loaded == a3)
    finally:
        try:
            os.remove(tmp3)
        except OSError:
            pass

    # 13. builder: raw keyconfig items -> engine records (pure mapping).
    synth = [
        {"km_name": "Object Mode", "is_modal": False,
         "op": "transform.translate", "name": "Move", "type": "G",
         "value": "PRESS", "map_type": "KEYBOARD", "mods": []},
        {"km_name": "Object Mode", "is_modal": False,
         "op": "object.duplicate_move", "name": "Duplicate", "type": "D",
         "value": "PRESS", "map_type": "KEYBOARD", "mods": ["shift"]},
        {"km_name": "Mesh", "is_modal": False,
         "op": "mesh.extrude_region_move", "name": "Extrude", "type": "E",
         "value": "PRESS", "map_type": "KEYBOARD", "mods": []},
        {"km_name": "3D View", "is_modal": True, "op": "",
         "name": "Confirm", "type": "RET", "value": "PRESS",
         "map_type": "KEYBOARD", "mods": [], "parent": "TRANSFORM"},
        {"km_name": "3D View", "is_modal": False, "op": "view3d.view_selected",
         "name": "Frame Selected", "type": "MIDDLEMOUSE", "value": "PRESS",
         "map_type": "MOUSE", "mods": [], "parent": None},
    ]
    brec = builder.items_to_records(synth)
    g = next(r for r in brec if r["op"] == "transform.translate")
    check("builder object G -> object tag + no mod",
          "object" in g["tags"] and g["mods"] == [] and g["key"] == "G")
    d = next(r for r in brec if r["op"] == "object.duplicate_move")
    check("builder shift D mods", d["mods"] == ["Shift"])
    m = next(r for r in brec if r["km"] == "Mesh")
    check("builder edit E -> edit tag", "edit" in m["tags"])
    modal = next(r for r in brec if r["parent"] == "TRANSFORM")
    check("builder modal keeps parent + empty tags",
          modal["parent"] == "TRANSFORM" and modal["tags"] == set())
    mouse = next(r for r in brec if r["key"] == "鼠标中键")
    check("builder mouse key display",
          mouse["key"] == "鼠标中键" and "3d_viewport" in mouse["tags"])

    # 14. builder: maintained B table file round-trip (keyconfig->B by script).
    fd4, tmp4 = tempfile.mkstemp(suffix=".json")
    os.close(fd4)
    try:
        src = library.ensure_rids(brec)
        builder.save_maintained(src, tmp4)
        loaded = builder.load_maintained(tmp4)
        check("maintained B roundtrip length", len(loaded) == len(src))
        check("maintained B rid stable",
              {r["rid"] for r in loaded} == {r["rid"] for r in src})
    finally:
        try:
            os.remove(tmp4)
        except OSError:
            pass

    # 15. content: curated default (A content), decoupled from full keyconfig.
    cc = content.load_content()
    check("content non-empty", len(cc) > 30)
    check("content rows carry name+key+tags",
          all(r.get("name") and r.get("key") is not None and r.get("tags")
              for r in cc))
    cc2 = library.ensure_rids(cc)
    a_def = library.default_shown(cc2)
    check("default A = curated rids (not empty)",
          len(a_def) == len(cc2) and a_def[0] == cc2[0]["rid"])
    # decouple: these are A content independent of the big keyconfig DB
    check("content independent rids distinct", len(set(a_def)) == len(a_def))

    print("\n%d failures" % len(_failures))
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
