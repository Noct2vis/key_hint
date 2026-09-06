# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Key Hint is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation, version 3 of the License.
#
# ##### END GPL LICENSE BLOCK #####

"""Addon preferences for Key Hint."""

import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
)


def get_prefs():
    """Convenience accessor for this addon's preferences."""
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        return None


class KeyHintAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # --- Behaviour -------------------------------------------------------
    auto_start: BoolProperty(
        name="Auto start with Blender",
        description=(
            "Automatically start the capture / HUD overlay when a new file is "
            "loaded after enabling the addon"
        ),
        default=False,
    )

    show_pressed_keys: BoolProperty(
        name="Show pressed keys",
        description="Show the currently pressed keys / modifiers",
        default=True,
    )

    show_hints: BoolProperty(
        name="Show shortcut hints while a modifier is held",
        description=(
            "While Ctrl/Shift/Alt is held, list real shortcuts from your "
            "active keymap that start with that modifier"
        ),
        default=True,
    )

    # --- Visuals ---------------------------------------------------------
    offset_x: IntProperty(
        name="Offset X",
        description="Horizontal offset (pixels) from the chosen corner",
        default=24,
        min=0,
    )
    offset_y: IntProperty(
        name="Offset Y",
        description="Vertical offset (pixels) from the chosen corner",
        default=24,
        min=0,
    )

    font_size: IntProperty(
        name="Font size",
        default=14,
        min=8,
        max=48,
    )

    max_hints: IntProperty(
        name="Max hints",
        description="Maximum number of shortcut hints to draw at once",
        default=12,
        min=1,
        max=60,
    )

    background_opacity: FloatProperty(
        name="Panel opacity",
        default=0.55,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    accent_color: FloatVectorProperty(
        name="Accent",
        description="Colour used to highlight the currently held modifiers",
        default=(0.29, 0.68, 1.0, 1.0),
        size=4,
        subtype='COLOR',
        min=0.0,
        max=1.0,
    )

    text_color: FloatVectorProperty(
        name="Text",
        default=(1.0, 1.0, 1.0, 1.0),
        size=4,
        subtype='COLOR',
        min=0.0,
        max=1.0,
    )

    use_separate_accent: BoolProperty(
        name="Use accent colour",
        description="Draw held modifiers using the accent colour",
        default=True,
    )

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.prop(self, "auto_start")
        col.separator()

        col.label(text="Display")
        col.prop(self, "show_pressed_keys")
        col.prop(self, "show_hints")
        col.prop(self, "max_hints")
        col.separator()

        col.label(text="Style")
        col.prop(self, "font_size")
        col.prop(self, "offset_x")
        col.prop(self, "offset_y")
        col.prop(self, "background_opacity")
        col.prop(self, "use_separate_accent")
        if self.use_separate_accent:
            col.prop(self, "accent_color")
        col.prop(self, "text_color")
