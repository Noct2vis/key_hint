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

Key Hint shows an always-on reference of the shortcuts that *actually* exist
in your current keymap configuration, relevant to the active editor + mode.

Blender does not expose "which keymap is active right now" through the public
Python API, so we approximate the active context from the current editor type
and mode, then scan the matching keymaps in the keyconfig that is really in
use (the ``active`` keyconfig, falling back to ``user`` / defaults).

Entries are returned as one flat list; the caller splits them into groups
(e.g. "no modifier" base group, or "starts with Ctrl" group) for display.
All functions in this module are pure (read-only, return plain dicts) so the
engine can be unit-tested without a GUI session.
"""

import bpy


# ---------------------------------------------------------------------------
# Public data model ---------------------------------------------------------
# ---------------------------------------------------------------------------
# An "entry" is a plain dict:
#   { "mods": ["Ctrl"], "key": "X", "label": "Some Operation" }
# "mods" are the *required* modifiers (in canonical order Ctrl, Shift, Alt,
# OS).  A key with no modifier has mods == [].


MOD_ORDER = (
    ("ctrl", "Ctrl"),
    ("shift", "Shift"),
    ("alt", "Alt"),
    ("oskey", "OS"),
)

# Mouse / pen / misc bindings we never present as a keyboard shortcut.
_IGNORED_KEY_TYPES = {
    "NONE", "", "ACTIONMOUSE", "EVT_TWEAK_L", "EVT_TWEAK_M",
    "EVT_TWEAK_R", "TIMER", "WINDOW_DEACTIVATE", "MOUSEMOVE",
    "INBETWEEN_MOUSEMOVE", "TEXTINPUT", "LEFTMOUSE", "RIGHTMOUSE",
    "MIDDLEMOUSE", "BUTTON4MOUSE", "BUTTON5MOUSE", "BUTTON6MOUSE",
    "BUTTON7MOUSE", "PEN", "UNDO", "REDO",
}
_VALID_MAP_TYPES = {"KEYBOARD"}

# Context-independent (global) keymaps that apply in basically every editor.
_GLOBAL_KEYMAPS = (
    "Window", "Screen", "Screen Editing", "Animation", "Animation Channels",
    "Frames", "Markers", "User Interface",
)

# Map object mode (context.mode) to the keymap(s) that carry its bindings.
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

# Editor space type -> keymap name(s) that apply while that editor is active.
_EDITOR_KEYMAPS = {
    "VIEW_3D": ("3D View", "3D View Generic"),
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


def _modifier_set(item):
    """Return frozenset of modifier attribute-names an item requires."""
    return frozenset(attr for attr, _name in MOD_ORDER
                     if getattr(item, attr, False))


def _modifier_names_from_attrs(attrs):
    """Map a set of modifier attribute-names to ordered display names."""
    return [name for attr, name in MOD_ORDER if attr in attrs]


def held_modifier_attrs(event):
    """Modifier attribute-names currently reported by an event."""
    return [attr for attr, _name in MOD_ORDER if getattr(event, attr, False)]


def held_modifier_names(event):
    """Modifier display names currently reported held by an event."""
    return _modifier_names_from_attrs(set(held_modifier_attrs(event)))


# ---------------------------------------------------------------------------
# Context -> relevant keymap names -----------------------------------------
# ---------------------------------------------------------------------------
def _context_mode(context):
    """Best-effort current mode string, or a reasonable default."""
    try:
        mode = getattr(context, "mode", None)
    except Exception:                    # noqa: BLE001
        mode = None
    if mode:
        return mode
    obj = getattr(context, "active_object", None) or \
        getattr(context, "object", None)
    if obj is not None:
        try:
            return obj.mode or "OBJECT"
        except Exception:                # noqa: BLE001
            return "OBJECT"
    return "OBJECT"


def relevant_keymap_names(context):
    """Ordered list of keymap names relevant for the current context."""
    names = list(_GLOBAL_KEYMAPS)

    area = getattr(context, "area", None)
    space_type = getattr(area, "type", None) if area else None

    if space_type == "VIEW_3D":
        names += list(_EDITOR_KEYMAPS.get("VIEW_3D", ()))
        mode = _context_mode(context)
        names += list(_MODE_KEYMAPS.get(mode, ()))
        # Grease-pencil / object edit maps share a generic namespace too.
        names += ["Object Non-modal"]
    elif space_type:
        names += list(_EDITOR_KEYMAPS.get(space_type, ()))

    return names


def mode_display_name(context):
    """Short human label for the current context, e.g. 'Object Mode'."""
    area = getattr(context, "area", None)
    space_type = getattr(area, "type", None) if area else None
    if space_type != "VIEW_3D":
        return space_type.replace("_", " ").title() if space_type else "Blender"
    mode = _context_mode(context)
    pretty = {
        "OBJECT": "Object Mode", "EDIT_MESH": "Edit (Mesh)",
        "EDIT_CURVE": "Edit (Curve)", "EDIT_SURFACE": "Edit (Surface)",
        "EDIT_FONT": "Edit (Text)", "EDIT_METABALL": "Edit (Metaball)",
        "EDIT_LATTICE": "Edit (Lattice)", "EDIT_ARMATURE": "Edit (Armature)",
        "EDIT_GPENCIL": "Edit (Grease Pencil)", "SCULPT": "Sculpt Mode",
        "VERTEX_PAINT": "Vertex Paint", "WEIGHT_PAINT": "Weight Paint",
        "TEXTURE_PAINT": "Texture Paint", "POSE": "Pose Mode",
        "PAINT_GPENCIL": "GP Draw", "SCULPT_GPENCIL": "GP Sculpt",
        "WEIGHT_GPENCIL": "GP Weight", "VERTEX_GPENCIL": "GP Vertex",
        "PARTICLE": "Particle Mode", "OBJECT_GPENCIL": "Grease Pencil",
    }
    return pretty.get(mode, mode.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Key / label helpers -------------------------------------------------------
# ---------------------------------------------------------------------------
def key_display_name(event_or_item_type):
    """Return a short, human readable name for a Blender key *type* string."""
    name = str(event_or_item_type)
    for prefix in ("LEFT_", "RIGHT_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    if name == "OSKEY":
        return "Super"
    if name.startswith("NUMPAD_"):
        return "Numpad " + name[len("NUMPAD_"):]
    if name.startswith("PAD"):
        return "Numpad " + name[3:]
    if len(name) == 1 and name.isalnum():
        return name
    return name.title()


def operator_label(idname, fallback=""):
    """Human readable label for an operator idname ('' -> fallback).

    Uses the operator's own display label so the text follows Blender's
    language the same way the operator name is shown in Blender itself.
    """
    if not idname:
        return fallback
    try:
        cls = bpy.types.Operator.bl_rna_get_subclass(idname)
    except Exception:                    # noqa: BLE001
        cls = None
    if cls is not None:
        label = getattr(cls, "bl_label", "")
        if label:
            return label
    return fallback or idname


def localized_operator_label(idname, fallback=""):
    """Operator label localised to the running UI language where possible.

    ``bl_label`` is English; if the UI has translations loaded (e.g. Chinese
    language pack) this asks Blender for the translated label so the shown
    name follows the interface language.
    """
    base = operator_label(idname, fallback)
    try:
        trans = bpy.app.translations
        ctx = getattr(trans, "context", None)
        pgettext = getattr(trans, "pgettext_iface", None) or \
            getattr(trans, "pgettext", None)
        if pgettext is not None:
            # Operator labels live in the "Operator" context.
            local = pgettext(base, "Operator")
            if local and local != base:
                return local
    except Exception:                    # noqa: BLE001
        pass
    return base


def _props_match(item, wanted):
    """True if *item*'s operator properties match every (name, value) in
    *wanted*.  Lets us disambiguate operators that share an idname but differ
    by a property (e.g. view3d.view_axis by its 'axis')."""
    if not wanted:
        return True
    props = getattr(item, "properties", None)
    if props is None:
        return False
    try:
        for name, value in wanted.items():
            if not hasattr(props, name):
                return False
            if getattr(props, name) != value:
                return False
    except Exception:                        # noqa: BLE001
        return False
    return True


def find_binding(entry):
    """Return the current (mods_display, key_display) binding for a retained
    *entry* ({'op': idname, 'keymap': name or '', 'props': {...}}), or None.

    Scans the active keyconfig for an active, usable item whose idname (and
    property subset) match.  A matching keymap name (if given) wins; otherwise
    the first matching item found is returned.  Needs a real GUI keyconfig to
    see any bindings (keymap items are empty headless).
    """
    kc = _pick_keyconfig(bpy.context)
    if kc is None:
        return None
    op = (entry or {}).get("op", "") or ""
    if not op:
        return None
    wanted = (entry or {}).get("props") or {}
    target_km = (entry or {}).get("keymap", "") or ""
    best = None
    try:
        for km in kc.keymaps:
            if getattr(km, "is_modal", False):
                continue
            for it in km.keymap_items:
                if not _item_usable(it):
                    continue
                if getattr(it, "idname", "") != op:
                    continue
                if not _props_match(it, wanted):
                    continue
                mods = _modifier_names_from_attrs(_modifier_set(it))
                combo = (mods, key_display_name(getattr(it, "type", None)))
                if target_km and km.name == target_km:
                    return combo
                if best is None:
                    best = combo
    except Exception:                        # noqa: BLE001
        return None
    return best


# ---------------------------------------------------------------------------
# The scan ------------------------------------------------------------------
# ---------------------------------------------------------------------------
def _pick_keyconfig(context):
    """Return the keyconfig that is actually in use, or None."""
    wm = getattr(context, "window_manager", None)
    if wm is None:
        return None
    kcs = getattr(wm, "keyconfigs", None)
    if kcs is None:
        return None
    for key in ("active", "user"):
        try:
            kc = getattr(kcs, key, None)
        except Exception:                # noqa: BLE001
            kc = None
        if kc is not None and kc.name not in ("", "Blender addon"):
            return kc
    for kc in kcs:
        if kc is not None and kc.name not in ("", "Blender addon"):
            return kc
    return None


def _item_usable(item):
    """True if the item is a single-tap keyboard binding we can show."""
    if not getattr(item, "active", True):
        return False
    if getattr(item, "map_type", None) not in _VALID_MAP_TYPES:
        return False
    key_type = getattr(item, "type", None)
    if key_type in _IGNORED_KEY_TYPES:
        return False
    if getattr(item, "value", None) not in ("PRESS", "ANY"):
        return False
    return True


def collect_entries(context):
    """Return the flat, deduplicated list of keyboard shortcut entries that
    are relevant to the current editor + mode.

    Each entry is: {"mods": [...display names...], "key": str, "label": str}.
    Sorted by key, then label.
    """
    kc = _pick_keyconfig(context)
    if kc is None:
        return []

    by_name = {}
    try:
        for km in kc.keymaps:
            by_name[km.name] = km
    except Exception:                    # noqa: BLE001
        return []

    names = [n for n in relevant_keymap_names(context) if n in by_name]

    seen = {}
    for name in names:
        km = by_name.get(name)
        if km is None or getattr(km, "is_modal", False):
            continue
        try:
            items = list(km.keymap_items)
        except Exception:                # noqa: BLE001
            continue
        for it in items:
            if not _item_usable(it):
                continue
            attrs = _modifier_set(it)
            key_type = getattr(it, "type", None)
            key_disp = key_display_name(key_type)
            mods_tuple = tuple(sorted(attrs))
            dedupe = (mods_tuple, key_disp)
            idname = getattr(it, "idname", "") or ""
            entry = {
                "mods": _modifier_names_from_attrs(attrs),
                "key": key_disp,
                "label": localized_operator_label(
                    idname, fallback=getattr(it, "name", "")),
                "op": idname,
            }
            # Relevant keymaps are ordered from generic -> context/mode
            # specific, so a later entry with the same key is the more useful
            # (mode-specific) binding and should win over a generic one.
            seen[dedupe] = entry

    entries = list(seen.values())
    entries.sort(key=lambda e: (tuple(e["mods"]), e["key"], e["label"]))
    return entries


# ---------------------------------------------------------------------------
# Grouping helpers ----------------------------------------------------------
# ---------------------------------------------------------------------------
def split_base_and_modifier(entries):
    """Split a flat entry list into (base, others).

    base    : entries with no modifier (the always-on fundamentals).
    others  : entries that require at least one modifier.
    """
    base = [e for e in entries if not e["mods"]]
    others = [e for e in entries if e["mods"]]
    return base, others


def entries_for_modifiers(entries, held_mods):
    """Entries whose required modifier set *starts with* the held modifiers.

    ``held_mods`` is a list/set of modifier attribute-names currently held,
    e.g. {"ctrl"}.  An entry qualifies if every held modifier is required by
    the entry (so holding Ctrl also reveals Ctrl+Shift+X, clearly showing that
    Shift is still needed).  Base (no-modifier) entries are excluded.
    """
    held = set(held_mods or ())
    out = []
    for e in entries:
        required_attrs = _attrs_from_names(e["mods"])
        if not required_attrs:
            continue                       # no base entries in a modifier view
        if held and held.issubset(required_attrs):
            out.append(e)
        elif not held:
            out.append(e)
    return out


def _attrs_from_names(names):
    out = set()
    for attr, disp in MOD_ORDER:
        if disp in names:
            out.add(attr)
    return out
