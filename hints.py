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
Dynamic hint engine.

The purpose is the "game style" part of Key Hint: while a modifier key is
held, show the shortcuts that *actually* exist in your current keymap
configuration and start with the held modifier.

Blender does not expose "which keymap is active right now" through the public
Python API, so we approximate the active context from the current editor type
and mode, then scan the items of the matching keymaps in the keyconfig that is
really in use (the ``user`` keyconfig, falling back to the Blender defaults).

All functions in this module are pure (they only read data and return lists of
plain dicts) so the whole engine can be unit-tested without a GUI session.
"""

import bpy


# ---------------------------------------------------------------------------
# Public data model ---------------------------------------------------------
# ---------------------------------------------------------------------------
# A "combo" is what we ultimately draw:
#   { "mods": ["Ctrl"], "key": "X", "label": "Some Operation" }
#
# A keymap item matches a held modifier set if:
#   * the item is a keyboard binding (map_type == 'KEYBOARD'),
#   * it is bound to a value we treat as a tap (PRESS / ANY),
#   * it is not disabled (item.active),
#   * the set of modifiers the user is holding is contained in the set the
#     binding requires (so holding Ctrl also reveals Ctrl+Shift+X, and shows
#     that Shift is still needed).


# Modifier identifiers -> Blender item boolean attribute.
MOD_ATTR = (
    ("ctrl", "Ctrl"),
    ("shift", "Shift"),
    ("alt", "Alt"),
    ("oskey", "OS"),
)

# Keys we never want to present as a "next key" hint.
_IGNORED_KEY_TYPES = {
    "NONE", "", "ACTIONMOUSE", "EVT_TWEAK_L", "EVT_TWEAK_M",
    "EVT_TWEAK_R", "TIMER", "WINDOW_DEACTIVATE", "MOUSEMOVE",
    "INBETWEEN_MOUSEMOVE", "TEXTINPUT", "LEFTMOUSE", "RIGHTMOUSE",
    "MIDDLEMOUSE", "BUTTON4MOUSE", "BUTTON5MOUSE", "BUTTON6MOUSE",
    "BUTTON7MOUSE", "PEN", "UNDO", "REDO",
}
# Mouse / pen bindings have map_type 'MOUSE'/'NDOF'; we only care about keys.
_VALID_MAP_TYPES = {"KEYBOARD"}


def _modifier_set(item):
    """Return frozenset of modifier names a keymap item requires."""
    out = []
    for attr, name in MOD_ATTR:
        if getattr(item, attr, False):
            out.append(name)
    return frozenset(out)


def held_modifier_names(event):
    """Names of modifiers currently reported held by *event*.

    These mirror the item booleans (ctrl/shift/alt/oskey) so that filtering is
    consistent whether the information came from an event or an item.
    """
    out = []
    for attr, name in MOD_ATTR:
        if getattr(event, attr, False):
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# Context -> relevant keymap names -----------------------------------------
# ---------------------------------------------------------------------------
# EMPTY-space keymaps that are mode/tool specific are only relevant while that
# object mode / tool is active. VIEW_3D/IMAGE_EDITOR/... keymaps apply while
# that editor is active. The global ones below apply basically everywhere.
_GLOBAL_KEYMAPS = (
    "Window", "Screen", "Screen Editing", "Animation", "Animation Channels",
    "Frames", "Markers", "User Interface",
)

# Map object mode (context.mode) to the keymap name that carries its bindings.
# context.mode values used by Blender in a 3D viewport, e.g. 'OBJECT',
# 'EDIT_MESH', 'SCULPT', 'POSE', 'PAINT_*', 'EDIT_GPENCIL', ...
_MODE_KEYMAPS = {
    "OBJECT": ("Object Mode", "Object Non-modal"),
    "EDIT_MESH": ("Mesh",),
    "EDIT_CURVE": ("Curve",),
    "EDIT_SURFACE": ("Curve",),
    "EDIT_FONT": ("Font",),
    "EDIT_METABALL": ("Metaball",),
    "EDIT_LATTICE": ("Lattice",),
    "EDIT_ARMATURE": ("Armature",),
    "POSE": ("Pose", "Armature"),
    "EDIT_GPENCIL": ("Grease Pencil Edit Mode", "Grease Pencil Selection"),
    "PAINT_GPENCIL": ("Grease Pencil Draw Mode", "Grease Pencil"),
    "SCULPT_GPENCIL": ("Grease Pencil Sculpt Mode", "Grease Pencil"),
    "WEIGHT_GPENCIL": ("Grease Pencil Weight Paint", "Grease Pencil"),
    "VERTEX_GPENCIL": ("Grease Pencil Vertex Paint", "Grease Pencil"),
    "SCULPT": ("Sculpt",),
    "VERTEX_PAINT": ("Vertex Paint", "Paint Vertex Selection (Weight, Vertex)"),
    "WEIGHT_PAINT": ("Weight Paint", "Paint Vertex Selection (Weight, Vertex)"),
    "TEXTURE_PAINT": ("Image Paint", "Paint Face Mask (Weight, Vertex, Texture)"),
    "PARTICLE": ("Particle",),
    "OBJECT_GPENCIL": ("Grease Pencil", "Grease Pencil Selection"),
}

# In object mode the keymap also depends on the active object type (the edit
# keymaps of Mesh/Curve/... carry nothing, but Armature/Lattice edit share).
# For a non-edit object mode we generally want Object Mode/Non-modal above.


def _context_mode(context):
    """Best-effort current mode string, or None when not determinable."""
    try:
        mode = getattr(context, "mode", None)
    except Exception:          # noqa: BLE001 - property access can raise
        mode = None
    if mode:
        return mode
    # Fallback based on the active object's interaction mode.
    obj = getattr(context, "active_object", None) or getattr(context, "object", None)
    if obj is not None:
        try:
            om = obj.mode
        except Exception:      # noqa: BLE001
            return None
        if om == "OBJECT":
            return "OBJECT"
        # obj.mode returns generic 'EDIT', 'SCULPT', 'POSE', 'WEIGHT_PAINT'...
        return om
    return "OBJECT"


def _editor_keymap_names(space_type):
    """Name(s) of the keymap that apply while a given editor is active."""
    mapping = {
        "VIEW_3D": ("3D View", "3D View Generic", "Object Non-modal"),
        "IMAGE_EDITOR": ("Image", "Image Generic"),
        "UV": ("UV Editor",),
        "NODE_EDITOR": ("Node Editor", "Node Generic"),
        "SEQUENCE_EDITOR": ("Sequencer", "Preview", "Video Sequence Editor"),
        "DOPESHEET_EDITOR": ("Dopesheet", "Dopesheet Generic"),
        "GRAPH_EDITOR": ("Graph Editor", "Graph Editor Generic"),
        "NLA_EDITOR": ("NLA Editor", "NLA Tracks", "NLA Generic"),
        "CLIP_EDITOR": ("Clip Editor", "Clip"),
        "OUTLINER": ("Outliner",),
        "PROPERTIES": ("Property Editor",),
        "FILE_BROWSER": ("File Browser", "File Browser Main"),
        "TEXT_EDITOR": ("Text", "Text Generic"),
        "CONSOLE": ("Console",),
        "SPREADSHEET": ("Spreadsheet Generic",),
    }
    return mapping.get(space_type, ())


def relevant_keymap_names(context):
    """Ordered list of keymap names relevant for the current context."""
    names = list(_GLOBAL_KEYMAPS)

    area = getattr(context, "area", None)
    space_type = getattr(area, "type", None) if area else None

    if space_type == "VIEW_3D":
        names += list(_editor_keymap_names("VIEW_3D"))
        mode = _context_mode(context)
        # Include mode-specific (edit / sculpt / paint / pose) bindings.
        mode_maps = _MODE_KEYMAPS.get(mode, ())
        names += list(mode_maps)
        # In an edit-like mode we should also show its matching editor maps.
        if mode == "POSE":
            names += ["3D View"]
    elif space_type:
        names += list(_editor_keymap_names(space_type))

    return names


# ---------------------------------------------------------------------------
# Key name / label helpers --------------------------------------------------
# ---------------------------------------------------------------------------
def key_display_name(event_or_item_type):
    """Return a short, human readable name for a Blender key *type* string."""
    name = str(event_or_item_type)
    # Strip the LEFT/RIGHT modifier duplication handled separately.
    for prefix in ("LEFT_", "RIGHT_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    if name == "OSKEY":
        return "Super"
    # NUMPAD_0 ... => Numpad0 / keep readable.
    if name.startswith("NUMPAD_"):
        return "Numpad " + name[len("NUMPAD_"):]
    if name.startswith("PAD"):
        return "Numpad " + name[3:]
    # Single letters / digits stay as-is.
    if len(name) == 1 and name.isalnum():
        return name
    return name.title()


def operator_label(idname, fallback=""):
    """Human readable label for an operator idname ('' -> fallback).

    Resolves builtin (C) operators too, via ``bl_rna_get_subclass``, which is
    available even for non-python operators.
    """
    if not idname:
        return fallback
    try:
        cls = bpy.types.Operator.bl_rna_get_subclass(idname)
    except Exception:           # noqa: BLE001
        cls = None
    if cls is not None:
        label = getattr(cls, "bl_label", "")
        if label:
            return label
    return fallback or idname


# ---------------------------------------------------------------------------
# The scan ----------------------------------------------------------------
# ---------------------------------------------------------------------------
def _keymaps_in_keyconfig(kc):
    """Return dict keymap-name -> KeyMap from a keyconfig."""
    out = {}
    try:
        for km in kc.keymaps:
            out[km.name] = km
    except Exception:           # noqa: BLE001
        return {}
    return out


def _pick_keyconfig(context):
    """Return the keyconfig that is actually being used.

    Prefers the addon-visible 'user' keyconfig, then 'active', then any of the
    loaded ones.
    """
    wm = getattr(context, "window_manager", None)
    if wm is None:
        return None
    kcs = getattr(wm, "keyconfigs", None)
    if kcs is None:
        return None
    # Prefer the actually-active keyconfig, then the user override set.
    for key in ("active", "user"):
        try:
            kc = getattr(kcs, key, None)
        except Exception:       # noqa: BLE001
            kc = None
        if kc is not None and kc.name not in ("", "Blender addon"):
            return kc
    for kc in kcs:
        if kc is not None and kc.name not in ("", "Blender addon"):
            return kc
    return None


def _item_matches(item, held_mods):
    """True if *item* is a usable key that extends the held modifiers."""
    if not getattr(item, "active", True):
        return False
    if getattr(item, "map_type", None) not in _VALID_MAP_TYPES:
        return False
    if getattr(item, "type", None) in _IGNORED_KEY_TYPES:
        return False
    value = getattr(item, "value", None)
    if value not in ("PRESS", "ANY"):
        return False
    required = _modifier_set(item)
    # held modifiers must be a subset of what this binding needs
    if not held_mods.issubset(required):
        return False
    return True


def collect_hints(context, held_mods):
    """Return sorted list of combo dicts for the current context.

    ``held_mods`` is an iterable of modifier names, e.g. ("ctrl",).  The result
    is a list of dicts:

        {"mods": ["Ctrl", "Shift"], "key": "S", "label": "Save As..."}

    sorted first by how many extra modifiers are needed, then by key label.
    """
    held_mods = frozenset(held_mods)

    kc = _pick_keyconfig(context)
    if kc is None:
        return []

    by_name = _keymaps_in_keyconfig(kc)
    names = [n for n in relevant_keymap_names(context) if n in by_name]

    found = {}          # key + required-modifiers -> (label, extra mods)
    # Avoid repeating the same combo that appears in several keymaps.
    seen = set()

    for name in names:
        km = by_name.get(name)
        if km is None:
            continue
        if getattr(km, "is_modal", False):
            # modal maps (gizmo/tweak/transform...) aren't single-tap combos.
            continue
        try:
            items = list(km.keymap_items)
        except Exception:       # noqa: BLE001
            continue
        for it in items:
            if not _item_matches(it, held_mods):
                continue
            req = _modifier_set(it)
            key_type = getattr(it, "type", None)
            if key_type is None:
                continue
            key_disp = key_display_name(key_type)
            dedupe = (key_disp, tuple(sorted(req)))
            if dedupe in seen:
                continue
            seen.add(dedupe)

            # Modifier names in canonical display order (Ctrl, Shift, Alt, OS).
            mod_names = [m[1] for m in MOD_ATTR if m[0] in req]

            found[dedupe] = {
                "mods": mod_names,
                "key": key_disp,
                "label": operator_label(getattr(it, "idname", ""),
                                        fallback=getattr(it, "name", "")),
                "_extra": len(req - held_mods),
            }

    results = [v for v in found.values()]
    results.sort(key=lambda d: (d["_extra"], d["key"], d["mods"], d["label"]))
    return results
