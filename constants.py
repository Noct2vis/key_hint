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
Shortcut database and keymap resolution.

The curated reference table of common Blender shortcuts, organised by
category and by the context they apply to.  The *actual* key shown to the
user is resolved live from their keyconfig (see resolve()), so a re-bound
shortcut is displayed with the user's key and flagged as custom (✱).

Each entry:
  id       - stable key used for notes / dedupe
  label    - human friendly action name
  op       - operator idname(s) (string or list) used to find the binding
  key      - Blender default key type (e.g. 'G', 'NUMPAD_1', 'SPACE')
  mods     - tuple of default modifier names ('Ctrl','Shift','Alt','OS')
  cat      - category label
  modes    - set of context modes this applies to; None = everywhere
  tool     - optional: only show when this tool/context flag is set (unused)
"""

import bpy

# ---------------------------------------------------------------------------
# Modifier order / display helpers ------------------------------------------
# ---------------------------------------------------------------------------
MOD_ORDER = (("ctrl", "Ctrl"), ("shift", "Shift"), ("alt", "Alt"),
             ("oskey", "OS"))


def mods_of_item(item):
    """Display modifier names a keymap item requires."""
    out = []
    for attr, name in MOD_ORDER:
        if getattr(item, attr, False):
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# Database ----------------------------------------------------------------
# ---------------------------------------------------------------------------
# Modes use the same strings as context.mode in a 3D viewport, e.g.:
# OBJECT, EDIT_MESH, EDIT_CURVE, SCULPT, POSE, VERTEX_PAINT, ...
# None means the entry is shown regardless of mode.

_E = None  # everywhere

SHORTCUTS = [
    # ---- Transform ------------------------------------------------------
    dict(id="move", label="Move", op="transform.translate", key="G", mods=(), cat="Transform", modes=None),
    dict(id="rotate", label="Rotate", op="transform.rotate", key="R", mods=(), cat="Transform", modes=None),
    dict(id="scale", label="Scale", op="transform.resize", key="S", mods=(), cat="Transform", modes=None),
    dict(id="move_dup", label="Duplicate and move", op="object.duplicate_move", key="D", mods=("Shift",), cat="Transform", modes={"OBJECT"}),
    dict(id="snap", label="Snap", op="transform.snap_type", key="TAB", mods=("Shift",), cat="Transform", modes={"OBJECT", "EDIT_MESH", "POSE"}),
    dict(id="apply_transform", label="Apply (transform)", op="object.transform_apply", key="A", mods=("Ctrl",), cat="Transform", modes={"OBJECT"}),

    # ---- Navigation / view ----------------------------------------------
    dict(id="view_selected", label="Frame selected", op="view3d.view_selected", key="PERIOD", mods=("Shift",), cat="View", modes=None),
    dict(id="view_all", label="Frame all", op="view3d.view_all", key="HOME", mods=(), cat="View", modes=None),
    dict(id="toggle_local", label="Toggle local/global view", op="view3d.localview", key="SLASH", mods=(), cat="View", modes=None),
    dict(id="orbit", label="Orbit viewport", op="view3d.rotate", key="MIDDLEMOUSE", mods=(), cat="View", modes=None, mouse=True),
    dict(id="pan", label="Pan viewport", op="view3d.move", key="MIDDLEMOUSE", mods=("Shift",), cat="View", modes=None, mouse=True),
    dict(id="zoom", label="Zoom viewport", op="view3d.zoom", key="MIDDLEMOUSE", mods=("Ctrl",), cat="View", modes=None, mouse=True),
    dict(id="front_view", label="Front view", op="view3d.view_axis", key="NUMPAD_1", mods=(), cat="View", modes=None),
    dict(id="right_view", label="Right view", op="view3d.view_axis", key="NUMPAD_3", mods=(), cat="View", modes=None),
    dict(id="top_view", label="Top view", op="view3d.view_axis", key="NUMPAD_7", mods=(), cat="View", modes=None),
    dict(id="camera_view", label="Camera view", op="view3d.view_camera", key="NUMPAD_0", mods=(), cat="View", modes=None),
    dict(id="persp_ortho", label="Perspective / Orthographic", op="view3d.view_persportho", key="NUMPAD_5", mods=(), cat="View", modes=None),

    # ---- Object mode -----------------------------------------------------
    dict(id="select_all", label="Select all / none", op="object.select_all", key="A", mods=(), cat="Object", modes={"OBJECT"}),
    dict(id="add_object", label="Add object", op="object.modifier_add", key="A", mods=("Shift",), cat="Object", modes={"OBJECT"}),
    dict(id="delete_object", label="Delete", op="object.delete", key="X", mods=(), cat="Object", modes={"OBJECT"}),
    dict(id="duplicate_object", label="Duplicate", op="object.duplicate", key="D", mods=("Shift",), cat="Object", modes={"OBJECT"}),
    dict(id="join", label="Join objects", op="object.join", key="J", mods=("Ctrl",), cat="Object", modes={"OBJECT"}),
    dict(id="parent", label="Set parent", op="object.parent_set", key="P", mods=("Ctrl",), cat="Object", modes={"OBJECT"}),
    dict(id="hide", label="Hide object", op="object.hide_view_set", key="H", mods=(), cat="Object", modes={"OBJECT"}),
    dict(id="unhide", label="Unhide all", op="object.hide_view_clear", key="H", mods=("Alt",), cat="Object", modes={"OBJECT"}),
    dict(id="move_to_collection", label="Move to collection", op="object.move_to_collection", key="M", mods=(), cat="Object", modes={"OBJECT"}),

    # ---- Edit mesh -------------------------------------------------------
    dict(id="edit_toggle", label="Edit / Object mode", op="object.editmode_toggle", key="TAB", mods=(), cat="Mode", modes={"OBJECT", "EDIT_MESH"}),
    dict(id="loopcut", label="Loop cut", op="mesh.loopcut_slide", key="R", mods=("Ctrl",), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="extrude", label="Extrude", op="mesh.extrude_region_move", key="E", mods=(), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="inset", label="Inset", op="mesh.inset", key="I", mods=(), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="bevel", label="Bevel", op="mesh.bevel", key="B", mods=("Ctrl",), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="merge", label="Merge vertices", op="mesh.merge", key="M", mods=(), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="knife", label="Knife", op="mesh.knife_tool", key="K", mods=(), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="select_loop", label="Select edge loop", op="mesh.loop_multi_select", key="L", mods=("Alt",), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="subdivide", label="Subdivide", op="mesh.subdivide", key="E", mods=("Ctrl",), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="flip_normals", label="Flip normals", op="mesh.flip_normals", key="N", mods=("Shift", "Alt"), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="rip", label="Rip", op="mesh.rip_move", key="V", mods=(), cat="Mesh", modes={"EDIT_MESH"}),
    dict(id="dissolve", label="Dissolve", op="mesh.dissolve_mode", key="X", mods=("Ctrl",), cat="Mesh", modes={"EDIT_MESH"}),

    # ---- Selection / general edit ---------------------------------------
    dict(id="select_more", label="Grow selection", op="mesh.select_more", key="PADPLUSKEY", mods=("Ctrl",), cat="Selection", modes={"EDIT_MESH"}),
    dict(id="select_less", label="Shrink selection", op="mesh.select_less", key="PADMINUS", mods=("Ctrl",), cat="Selection", modes={"EDIT_MESH"}),
    dict(id="select_invert", label="Invert selection", op="mesh.select_all", key="I", mods=("Ctrl",), cat="Selection", modes={"EDIT_MESH"}),
    dict(id="box_select", label="Box select", op="view3d.select_box", key="B", mods=(), cat="Selection", modes={"OBJECT", "EDIT_MESH"}),

    # ---- Sculpt ----------------------------------------------------------
    dict(id="sculpt_mode", label="Sculpt mode", op="object.mode_set", key="TAB", mods=("Ctrl",), cat="Mode", modes={"OBJECT"}),
    dict(id="brush_size", label="Brush size", op="wm.radial_control", key="F", mods=(), cat="Sculpt", modes={"SCULPT"}),
    dict(id="brush_strength", label="Brush strength", op="wm.radial_control", key="F", mods=("Shift",), cat="Sculpt", modes={"SCULPT"}),
    dict(id="smooth_brush", label="Smooth brush", op="sculpt.smooth", key="S", mods=("Shift",), cat="Sculpt", modes={"SCULPT"}),
    dict(id="mask_brush", label="Mask brush", op="sculpt.mask_filter", key="M", mods=("Ctrl",), cat="Sculpt", modes={"SCULPT"}),

    # ---- Pose / armature -------------------------------------------------
    dict(id="pose_mode", label="Pose mode", op="object.mode_set", key="TAB", mods=("Ctrl",), cat="Mode", modes={"OBJECT"}),
    dict(id="pose_clear", label="Clear pose", op="pose.rot_clear", key="R", mods=("Alt",), cat="Pose", modes={"POSE"}),

    # ---- File / general --------------------------------------------------
    dict(id="save", label="Save file", op="wm.save_mainfile", key="S", mods=("Ctrl",), cat="General", modes=None),
    dict(id="save_as", label="Save as", op="wm.save_as_mainfile", key="S", mods=("Ctrl", "Shift"), cat="General", modes=None),
    dict(id="open", label="Open file", op="wm.open_mainfile", key="O", mods=("Ctrl",), cat="General", modes=None),
    dict(id="new_file", label="New file", op="wm.read_homefile", key="N", mods=("Ctrl",), cat="General", modes=None),
    dict(id="undo", label="Undo", op="ed.undo", key="Z", mods=("Ctrl",), cat="General", modes=None),
    dict(id="redo", label="Redo", op="ed.redo", key="Z", mods=("Ctrl", "Shift"), cat="General", modes=None),
    dict(id="search_menu", label="Search menu", op="wm.search_menu", key="F3", mods=(), cat="General", modes=None),
    dict(id="quick_favorites", label="Quick favorites", op="wm.call_menu", key="Q", mods=(), cat="General", modes=None),
]


def _op_list(entry):
    op = entry.get("op")
    if isinstance(op, str):
        return [op]
    return list(op or [])


def relevant_shortcuts(mode):
    """Shortcuts whose modes includes *mode* (None == everywhere)."""
    out = []
    for e in SHORTCUTS:
        m = e.get("modes")
        if m is None or mode in m:
            out.append(e)
    return out


# ---------------------------------------------------------------------------
# Keymap resolution ---------------------------------------------------------
# ---------------------------------------------------------------------------
def resolve_bindings(context, mode):
    """Return dict id -> {"key": str, "mods": [..], "custom": bool}.

    Scans the active/user keyconfig's relevant keymaps for the operator(s)
    named in each entry.  If the user has re-bound the operator, the resulting
    key/mods differ from the entry defaults and are flagged ``custom=True``.
    """
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

    # op idname -> (key_type, [mod names]) ; later (mode-specific) wins.
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
