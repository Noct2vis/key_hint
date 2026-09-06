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
Sidebar (N-panel) UI - the Flowkeys-style reference list.

Shows the current mode's shortcuts grouped by category, with a search box,
custom-binding marker (✱), and per-shortcut personal notes.  Notes are stored
in the .blend file via a Scene CollectionProperty (persist with the file).
"""

import bpy
from bpy.props import StringProperty, CollectionProperty

from . import constants
from . import hints


# ---------------------------------------------------------------------------
# Notes storage (persisted in the .blend) -----------------------------------
# ---------------------------------------------------------------------------
class KeyHintNote(bpy.types.PropertyGroup):
    sid: StringProperty(name="Shortcut id")
    text: StringProperty(name="Note")


def _notes(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return None
    return scene.key_hint_notes


def get_note(context, sid):
    notes = _notes(context)
    if notes is None:
        return None
    for n in notes:
        if n.sid == sid:
            return n
    return None


def set_note(context, sid, text):
    notes = _notes(context)
    if notes is None:
        return
    n = get_note(context, sid)
    if n is None:
        n = notes.add()
        n.sid = sid
    n.text = text


class KeyHintEditNoteOperator(bpy.types.Operator):
    """Add / edit the personal note for one shortcut."""
    bl_idname = "key_hint.edit_note"
    bl_label = "Key Hint Note"
    bl_options = {"REGISTER"}

    sid: StringProperty()
    text: StringProperty()

    def invoke(self, context, event):
        n = get_note(context, self.sid)
        self.text = n.text if n is not None else ""
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        set_note(context, self.sid, self.text)
        return {"FINISHED"}

    def draw(self, context):
        self.layout.prop(self, "text", text="Note")


# ---------------------------------------------------------------------------
# Panel ---------------------------------------------------------------------
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

    def draw(self, context):
        layout = self.layout

        # Enable toggle.
        layout.prop(context.window_manager, "key_hint_enabled", text="Enabled")
        layout.operator("key_hint.restart", text="Restart / rescan")

        # Search box.
        search = context.scene.key_hint_search
        layout.prop(context.scene, "key_hint_search", text="", icon="VIEWZOOM")

        mode = hints._context_mode(context)
        entries = constants.relevant_shortcuts(mode)
        bindings = constants.resolve_bindings(context, mode)

        q = (search or "").strip().lower()

        # Group by category, preserving category order of first appearance.
        order = []
        by_cat = {}
        for e in entries:
            cat = e.get("cat") or "Other"
            if cat not in by_cat:
                by_cat[cat] = []
                order.append(cat)
            by_cat[cat].append(e)

        shown_any = False
        for cat in order:
            cat_entries = by_cat[cat]
            if q:
                cat_entries = [e for e in cat_entries
                               if q in (e.get("label", "").lower()) or
                               q in (e.get("id", "").lower())]
            if not cat_entries:
                continue
            shown_any = True
            box = layout.box()
            box.label(text=cat)
            for e in cat_entries:
                b = bindings.get(e["id"], {})
                key = b.get("key", e.get("key", "?"))
                mods = b.get("mods", [])
                combo = (" + ".join(mods + [key])) if mods else key
                mark = " ✱" if b.get("custom") else ""

                row = box.row(align=True)
                row.label(text=combo)
                row.label(text=(e.get("label") or "") + mark)

                note = get_note(context, e["id"])
                if note and note.text:
                    row.label(text="N", icon="TEXT")
                op = row.operator("key_hint.edit_note", text="", icon="GREASEPENCIL")
                op.sid = e["id"]

        if not shown_any:
            layout.label(text="No matching shortcuts", icon="INFO")


def register_notes():
    def _reg(cls):
        try:
            bpy.utils.register_class(cls)
        except (RuntimeError, ValueError):
            pass
    _reg(KeyHintNote)
    _reg(KeyHintEditNoteOperator)
    if not hasattr(bpy.types.Scene, "key_hint_notes"):
        bpy.types.Scene.key_hint_notes = CollectionProperty(type=KeyHintNote)
    if not hasattr(bpy.types.Scene, "key_hint_search"):
        bpy.types.Scene.key_hint_search = StringProperty(
            name="Search", description="Filter shortcuts by name or key",
            default="")


def unregister_notes():
    if hasattr(bpy.types.Scene, "key_hint_notes"):
        del bpy.types.Scene.key_hint_notes
    if hasattr(bpy.types.Scene, "key_hint_search"):
        del bpy.types.Scene.key_hint_search
    try:
        bpy.utils.unregister_class(KeyHintEditNoteOperator)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(KeyHintNote)
    except RuntimeError:
        pass
