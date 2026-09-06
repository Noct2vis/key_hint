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


def _on_auto_start_change(_prefs, _context):
    # Imported lazily to avoid a circular import between prefs and core.
    from . import core
    core.handle_auto_start_change(_prefs, _context)


class KeyHintAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # --- Behaviour -------------------------------------------------------
    auto_start: BoolProperty(
        name="Auto start with Blender",
        description=(
            "Automatically start the capture / HUD overlay when a new file is "
            "loaded after enabling the addon"
        ),
        default=True,
        update=lambda self, ctx: _on_auto_start_change(self, ctx),
    )

    show_pressed_keys: BoolProperty(
        name="Show pressed keys row",
        description="Show the currently pressed keys / modifiers",
        default=False,
    )

    show_fundamentals: BoolProperty(
        name="Always show base shortcuts",
        description=(
            "Always display the current mode's no-modifier shortcuts "
            "(G move, R rotate, S scale, ...) in the corner"
        ),
        default=True,
    )

    show_hud: BoolProperty(
        name="Show HUD in 3D viewport",
        description="Draw the shortcut reference overlay in the 3D viewport",
        default=True,
    )

    show_hints: BoolProperty(
        name="Append modifier group while held",
        description=(
            "While Ctrl/Shift/Alt is held, additionally list the shortcuts "
            "that start with that modifier, below the base shortcuts"
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
        name="Max entries",
        description="Maximum number of shortcut entries shown per group",
        default=40,
        min=1,
        max=120,
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
        col.prop(self, "show_fundamentals")
        col.prop(self, "show_hud")
        col.prop(self, "show_hints")
        col.prop(self, "show_pressed_keys")
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
