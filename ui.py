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

"""Sidebar UI for Key Hint (3D Viewport > Sidebar > Key Hint)."""

import bpy


class KEYHINT_PT_panel(bpy.types.Panel):
    bl_label = "Key Hint"
    bl_idname = "KEYHINT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Key Hint"

    def draw(self, context):
        layout = self.layout

        # Live enable toggle (drives the passive capture operator).
        row = layout.row()
        row.prop(context.window_manager, "key_hint_enabled", text="Enabled")

        layout.separator()

        prefs = context.preferences.addons.get(__package__)
        if prefs is None:
            layout.label(text="Preferences not loaded.")
            return
        prefs = prefs.preferences

        col = layout.column(align=True)
        col.label(text="Reference")
        col.prop(prefs, "show_fundamentals")
        col.prop(prefs, "show_hints")
        col.prop(prefs, "max_hints")
        col.prop(prefs, "show_pressed_keys")

        col.separator()
        col.label(text="Style")
        col.prop(prefs, "font_size")
        col.prop(prefs, "background_opacity")

        # Link to the add-on preferences.
        layout.separator()
        layout.operator(
            "preferences.addon_show",
            text="Key Hint Preferences...",
        ).module = __package__
