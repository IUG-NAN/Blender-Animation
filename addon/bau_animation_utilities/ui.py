"""Menus and the sidebar panel (3D View > Sidebar > Tool)."""

import bpy

from .mirror import BAU_OT_mirror_action
from .pelvis_bob import BAU_OT_remove_pelvis_bob, BAU_OT_setup_pelvis_bob
from .walk import (
    BAU_OT_add_selected_walk_goals,
    BAU_OT_apply_walk_setup,
    BAU_OT_load_walk_profile,
    BAU_OT_remove_walk_goal,
    BAU_OT_remove_walk_profile,
    BAU_OT_save_walk_profile,
    BAU_OT_select_walk_profile,
    active_walk_profile,
    cycle_length,
    walk_leg_label,
)


class BAU_MT_context_menu(bpy.types.Menu):
    bl_label = "Animation Utilities"
    bl_idname = "BAU_MT_context_menu"

    def draw(self, context):
        layout = self.layout
        layout.operator(BAU_OT_mirror_action.bl_idname, icon="MOD_MIRROR")
        layout.separator()
        layout.operator(BAU_OT_setup_pelvis_bob.bl_idname, text="Pelvis Bob...", icon="GRAPH")
        layout.operator(BAU_OT_remove_pelvis_bob.bl_idname, icon="X")


def draw_context_menu(self, context):
    self.layout.separator()
    self.layout.menu(BAU_MT_context_menu.bl_idname)


def draw_action_menu(self, context):
    self.layout.separator()
    self.layout.operator(BAU_OT_mirror_action.bl_idname, icon="MOD_MIRROR")


class BAU_PT_walk_setup(bpy.types.Panel):
    bl_label = "Walk Setup"
    bl_idname = "BAU_PT_walk_setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        setup = context.scene.bau_walk_setup
        layout = self.layout
        layout.prop(setup, "template_path")
        layout.prop(setup, "reverse_path")
        row = layout.row(align=True)
        row.prop(setup, "start_frame")
        row.prop(setup, "end_frame")
        row = layout.row(align=True)
        row.prop(setup, "cycle_count")
        period = cycle_length(setup.start_frame, setup.end_frame, setup.cycle_count)
        row.label(text=f"{period:g} frames / cycle")
        layout.prop(setup, "phase_group_count")
        layout.operator(BAU_OT_add_selected_walk_goals.bl_idname, text="1. Add Selected IK Goals", icon="ADD")
        layout.operator(BAU_OT_apply_walk_setup.bl_idname, text="2. Generate / Update Animation Keys", icon="FILE_REFRESH")
        layout.label(text="IK Goals and Phase Groups")
        for index, leg in enumerate(setup.legs):
            row = layout.row(align=True)
            row.label(text=walk_leg_label(leg))
            row.prop(leg, "phase_group", text="Group")
            row.operator(BAU_OT_remove_walk_goal.bl_idname, text="", icon="X").index = index


class BAU_PT_walk_profiles(bpy.types.Panel):
    bl_label = "Gait Profiles"
    bl_idname = "BAU_PT_walk_profiles"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_parent_id = BAU_PT_walk_setup.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        setup = context.scene.bau_walk_setup
        layout = self.layout
        for index, profile in enumerate(setup.profiles):
            row = layout.row(align=True)
            icon = "RADIOBUT_ON" if index == setup.active_profile_index else "RADIOBUT_OFF"
            row.operator(
                BAU_OT_select_walk_profile.bl_idname,
                text=profile.name or f"Profile {index + 1}", icon=icon,
            ).index = index
            row.label(text=profile.action.name if profile.action else "No Action")
        layout.operator(BAU_OT_save_walk_profile.bl_idname, text="Save Current Walk Setup as Profile", icon="ADD")
        profile = active_walk_profile(setup)
        if profile:
            layout.prop(profile, "name")
            layout.prop(profile, "action")
            row = layout.row(align=True)
            row.operator(BAU_OT_load_walk_profile.bl_idname, text="Load Selected Profile", icon="IMPORT")
            row.operator(BAU_OT_remove_walk_profile.bl_idname, text="Remove Selected", icon="TRASH")


CLASSES = (BAU_MT_context_menu, BAU_PT_walk_setup, BAU_PT_walk_profiles)

MENUS = (
    (bpy.types.VIEW3D_MT_pose_context_menu, draw_context_menu),
    (bpy.types.VIEW3D_MT_object_context_menu, draw_context_menu),
    (bpy.types.DOPESHEET_MT_action, draw_action_menu),
)


def register_menus():
    for menu, draw in MENUS:
        menu.append(draw)


def unregister_menus():
    for menu, draw in MENUS:
        menu.remove(draw)
