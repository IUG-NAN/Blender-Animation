bl_info = {
    "name": "UE Animation Utilities",
    "author": "IUG-NAN",
    "version": (0, 4, 0),
    "blender": (5, 2, 0),
    "location": "3D View > Sidebar > UE Anim",
    "description": "Pose mirroring and procedural walk setup for game animation",
    "category": "Animation",
}

import math
import re
from collections import defaultdict

import bpy


POSE_TRANSFORM_PATH = re.compile(
    r'^pose\.bones\["([^"]+)"\]\.'
    r'(location|rotation_euler|rotation_quaternion|rotation_axis_angle|scale)$'
)

MOTION_PATH_CONSTRAINT_NAME = "UE Motion Path"
PELVIS_BOB_CONSTRAINT_NAME = "UE Pelvis World Bob"
WALK_PATH_COLLECTION_NAME = "UE Walk Paths"


def action_channelbags(action, owner=None):
    """Return Blender 5.2 F-Curve containers for an Action and optional owner."""
    if hasattr(action, "fcurves"):
        return (action,)

    slot_handle = None
    if owner and owner.animation_data and owner.animation_data.action == action:
        slot_handle = owner.animation_data.action_slot_handle

    channelbags = []
    for layer in action.layers:
        for strip in layer.strips:
            if strip.type != "KEYFRAME":
                continue
            for channelbag in strip.channelbags:
                if slot_handle is None or channelbag.slot_handle == slot_handle:
                    channelbags.append(channelbag)
    return channelbags


def action_fcurves(action, owner=None):
    return [
        fcurve
        for channelbag in action_channelbags(action, owner)
        for fcurve in channelbag.fcurves
    ]


def find_action_fcurve(action, data_path, index, owner=None):
    for channelbag in action_channelbags(action, owner):
        fcurve = channelbag.fcurves.find(data_path, index=index)
        if fcurve:
            return channelbag, fcurve
    return None, None


def remove_action_fcurve(action, data_path, index, owner=None):
    channelbag, fcurve = find_action_fcurve(action, data_path, index, owner)
    if fcurve:
        channelbag.fcurves.remove(fcurve)
    return fcurve


def keyed_bones_by_frame(action, owner):
    keyed = defaultdict(set)
    for fcurve in action_fcurves(action, owner):
        match = POSE_TRANSFORM_PATH.match(fcurve.data_path)
        if not match:
            continue
        for point in fcurve.keyframe_points:
            keyed[float(point.co.x)].add(match.group(1))
    return keyed


def set_frame(scene, frame):
    whole_frame = math.floor(frame)
    scene.frame_set(whole_frame, subframe=frame - whole_frame)


def select_bones(armature, names, active_name=None):
    names = set(names)
    for pose_bone in armature.pose.bones:
        pose_bone.select = pose_bone.name in names
    active = armature.data.bones.get(active_name) if active_name else None
    armature.data.bones.active = active or next(
        (bone for bone in armature.data.bones if bone.name in names), None
    )


def insert_transform_keys(pose_bone, frame):
    pose_bone.keyframe_insert(data_path="location", frame=frame, group=pose_bone.name)
    pose_bone.keyframe_insert(data_path="scale", frame=frame, group=pose_bone.name)
    rotation_path = {
        "QUATERNION": "rotation_quaternion",
        "AXIS_ANGLE": "rotation_axis_angle",    }.get(pose_bone.rotation_mode, "rotation_euler")
    pose_bone.keyframe_insert(data_path=rotation_path, frame=frame, group=pose_bone.name)



def curve_object_poll(_operator, obj):
    return obj.type == "CURVE"


def selected_motion_path_goals(context, path):
    if context.mode == "POSE":
        return list(context.selected_pose_bones or [])
    return [obj for obj in context.selected_objects if obj != path]


def find_or_create_motion_path_constraint(goal):
    named_constraint = goal.constraints.get(MOTION_PATH_CONSTRAINT_NAME)
    if named_constraint and named_constraint.type == "FOLLOW_PATH":
        return named_constraint

    constraint = goal.constraints.new("FOLLOW_PATH")
    constraint.name = MOTION_PATH_CONSTRAINT_NAME
    return constraint


def ensure_action(owner):
    animation_data = owner.animation_data_create()
    if animation_data.action is None:
        animation_data.action = bpy.data.actions.new(f"{owner.name}_MotionPath")
    return animation_data.action


def ensure_cycles_modifier(fcurve):
    for modifier in fcurve.modifiers:
        if modifier.type == "CYCLES":
            return modifier

    cycles = fcurve.modifiers.new("CYCLES")
    cycles.mode_before = "REPEAT"
    cycles.mode_after = "REPEAT"
    return cycles


def clear_motion_path_animation(owner, constraint):
    if not owner.animation_data or not owner.animation_data.action:
        return
    data_path = constraint.path_from_id("offset_factor")
    remove_action_fcurve(owner.animation_data.action, data_path, index=0, owner=owner)


def replace_motion_path_animation(owner, constraint, start_frame, end_frame,
                                  cycle_length, phase_offset, reverse_path):
    action = ensure_action(owner)
    action.use_frame_range = True
    action.frame_start = start_frame
    action.frame_end = end_frame
    data_path = constraint.path_from_id("offset_factor")
    clear_motion_path_animation(owner, constraint)

    start_value = phase_offset + (1.0 if reverse_path else 0.0)
    end_value = phase_offset + (0.0 if reverse_path else 1.0)
    constraint.offset_factor = start_value
    constraint.keyframe_insert(data_path="offset_factor", frame=start_frame)
    constraint.offset_factor = end_value
    constraint.keyframe_insert(
        data_path="offset_factor", frame=start_frame + cycle_length
    )

    _channelbag, fcurve = find_action_fcurve(action, data_path, index=0, owner=owner)
    if not fcurve:
        raise RuntimeError("Could not create the Follow Path animation curve")

    for point in fcurve.keyframe_points:
        point.interpolation = "LINEAR"
    cycles = fcurve.modifiers.new("CYCLES")
    cycles.mode_before = "REPEAT"
    cycles.mode_after = "REPEAT"


class ANIM_PG_walk_leg(bpy.types.PropertyGroup):
    goal_object: bpy.props.PointerProperty(type=bpy.types.Object)
    goal_bone: bpy.props.StringProperty()
    phase_group: bpy.props.IntProperty(name="Group", default=0, min=0)
    path_object: bpy.props.PointerProperty(type=bpy.types.Object)


class ANIM_PG_walk_profile(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Profile Name", default="Walk")
    action: bpy.props.PointerProperty(name="Action", type=bpy.types.Action)
    template_path: bpy.props.PointerProperty(type=bpy.types.Object, poll=curve_object_poll)
    start_frame: bpy.props.IntProperty(default=0)
    end_frame: bpy.props.IntProperty(default=30)
    cycle_length: bpy.props.IntProperty(default=30, min=1)
    phase_group_count: bpy.props.IntProperty(default=3, min=1, max=8)
    reverse_path: bpy.props.BoolProperty(default=True)
    legs: bpy.props.CollectionProperty(type=ANIM_PG_walk_leg)


class ANIM_PG_walk_setup(bpy.types.PropertyGroup):
    template_path: bpy.props.PointerProperty(name="Template Curve", type=bpy.types.Object, poll=curve_object_poll)
    start_frame: bpy.props.IntProperty(name="Animation Start", default=0)
    end_frame: bpy.props.IntProperty(name="Animation End", default=30)
    cycle_length: bpy.props.IntProperty(name="Cycle Length", default=30, min=1)
    phase_group_count: bpy.props.IntProperty(name="Phase Groups", default=3, min=1, max=8)
    reverse_path: bpy.props.BoolProperty(name="Reverse Curve Direction", default=True)
    legs: bpy.props.CollectionProperty(type=ANIM_PG_walk_leg)
    active_leg_index: bpy.props.IntProperty(default=0)
    profiles: bpy.props.CollectionProperty(type=ANIM_PG_walk_profile)
    active_profile_index: bpy.props.IntProperty(default=0)


def active_walk_profile(setup):
    if len(setup.profiles) == 0:
        return None
    setup.active_profile_index = max(0, min(setup.active_profile_index, len(setup.profiles) - 1))
    return setup.profiles[setup.active_profile_index]


def copy_legs(source_legs, destination_legs):
    destination_legs.clear()
    for source_leg in source_legs:
        leg = destination_legs.add()
        leg.goal_object = source_leg.goal_object
        leg.goal_bone = source_leg.goal_bone
        leg.phase_group = source_leg.phase_group


def copy_setup_to_profile(setup, profile):
    profile.template_path = setup.template_path
    profile.start_frame = setup.start_frame
    profile.end_frame = setup.end_frame
    profile.cycle_length = setup.cycle_length
    profile.phase_group_count = setup.phase_group_count
    profile.reverse_path = setup.reverse_path
    copy_legs(setup.legs, profile.legs)
    owner = action_owner(profile.legs)
    profile.action = owner.animation_data.action if owner and owner.animation_data else None


def copy_profile_to_setup(profile, setup):
    setup.template_path = profile.template_path
    setup.start_frame = profile.start_frame
    setup.end_frame = profile.end_frame
    setup.cycle_length = profile.cycle_length
    setup.phase_group_count = profile.phase_group_count
    setup.reverse_path = profile.reverse_path
    copy_legs(profile.legs, setup.legs)


def resolve_walk_goal(leg):
    owner = leg.goal_object
    if not owner:
        return None, None
    if leg.goal_bone:
        if owner.type != "ARMATURE":
            return None, None
        return owner.pose.bones.get(leg.goal_bone), owner
    return owner, owner


def action_owner(legs):
    owners = {owner for leg in legs for _goal, owner in [resolve_walk_goal(leg)] if owner}
    return next(iter(owners)) if len(owners) == 1 else None


def walk_leg_label(leg):
    if not leg.goal_object:
        return "Missing IK Goal"
    return f"{leg.goal_object.name} : {leg.goal_bone}" if leg.goal_bone else leg.goal_object.name


def get_walk_path_collection(scene):
    collection = bpy.data.collections.get(WALK_PATH_COLLECTION_NAME)
    if not collection:
        collection = bpy.data.collections.new(WALK_PATH_COLLECTION_NAME)
        scene.collection.children.link(collection)
    return collection


def walk_path_name(owner, goal):
    return f"UE Walk Path - {owner.name} - {goal.name}"


def find_or_create_walk_path(scene, setup, leg, goal, owner):
    path = leg.path_object
    if not path or path.type != "CURVE":
        path = bpy.data.objects.get(walk_path_name(owner, goal))
    if not path or path.type != "CURVE":
        path = setup.template_path.copy()
        path.name = walk_path_name(owner, goal)
        get_walk_path_collection(scene).objects.link(path)
    path.data = setup.template_path.data
    path.matrix_world = setup.template_path.matrix_world.copy()
    leg.path_object = path
    return path


def align_walk_path(path, goal, owner, constraint, factor, desired_position):
    constraint.target = path
    constraint.use_fixed_location = True
    constraint.offset_factor = factor
    bpy.context.view_layer.update()
    current_position = world_location(goal, owner)
    path.location.y += desired_position.y - current_position.y
    bpy.context.view_layer.update()


class ANIM_OT_select_walk_profile(bpy.types.Operator):
    bl_idname = "anim.ue_select_walk_profile"
    bl_label = "Select Gait Profile"
    index: bpy.props.IntProperty(min=0)

    def execute(self, context):
        setup = context.scene.ue_walk_setup
        if self.index >= len(setup.profiles):
            return {"CANCELLED"}
        setup.active_profile_index = self.index
        return {"FINISHED"}


class ANIM_OT_save_walk_profile(bpy.types.Operator):
    bl_idname = "anim.ue_save_walk_profile"
    bl_label = "Save Current Walk Setup as Profile"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(name="Profile Name", default="Walk")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        setup = context.scene.ue_walk_setup
        profile = setup.profiles.add()
        profile.name = self.name.strip() or "Walk"
        copy_setup_to_profile(setup, profile)
        setup.active_profile_index = len(setup.profiles) - 1
        return {"FINISHED"}


class ANIM_OT_load_walk_profile(bpy.types.Operator):
    bl_idname = "anim.ue_load_walk_profile"
    bl_label = "Load Selected Profile into Walk Setup"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        setup = context.scene.ue_walk_setup
        profile = active_walk_profile(setup)
        if not profile:
            return {"CANCELLED"}
        copy_profile_to_setup(profile, setup)
        owner = action_owner(setup.legs)
        if owner and profile.action:
            owner.animation_data_create().action = profile.action
        self.report({"INFO"}, f"Loaded Profile: {profile.name}. Generate keys to apply it.")
        return {"FINISHED"}


class ANIM_OT_remove_walk_profile(bpy.types.Operator):
    bl_idname = "anim.ue_remove_walk_profile"
    bl_label = "Remove Selected Profile"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        setup = context.scene.ue_walk_setup
        if not active_walk_profile(setup):
            return {"CANCELLED"}
        setup.profiles.remove(setup.active_profile_index)
        setup.active_profile_index = min(setup.active_profile_index, max(0, len(setup.profiles) - 1))
        return {"FINISHED"}


class ANIM_OT_add_selected_walk_goals(bpy.types.Operator):
    bl_idname = "anim.ue_add_selected_walk_goals"
    bl_label = "Add Selected IK Goals"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        setup = context.scene.ue_walk_setup
        candidates = [(context.object, bone.name) for bone in (context.selected_pose_bones or [])] if context.mode == "POSE" else [(obj, "") for obj in context.selected_objects if obj != setup.template_path]
        added = 0
        for obj, bone_name in candidates:
            if any(leg.goal_object == obj and leg.goal_bone == bone_name for leg in setup.legs):
                continue
            leg = setup.legs.add()
            leg.goal_object = obj
            leg.goal_bone = bone_name
            leg.phase_group = (len(setup.legs) - 1) % setup.phase_group_count
            added += 1
        if not added:
            self.report({"WARNING"}, "No new IK Goals were selected")
            return {"CANCELLED"}
        setup.active_leg_index = len(setup.legs) - 1
        return {"FINISHED"}


class ANIM_OT_remove_walk_goal(bpy.types.Operator):
    bl_idname = "anim.ue_remove_walk_goal"
    bl_label = "Remove IK Goal"
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()

    def execute(self, context):
        setup = context.scene.ue_walk_setup
        if self.index < 0 or self.index >= len(setup.legs):
            return {"CANCELLED"}
        setup.legs.remove(self.index)
        return {"FINISHED"}


class ANIM_OT_apply_walk_setup(bpy.types.Operator):
    bl_idname = "anim.ue_apply_walk_setup"
    bl_label = "Generate / Update Animation Keys"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        setup = scene.ue_walk_setup
        if not setup.template_path or setup.template_path.type != "CURVE":
            self.report({"ERROR"}, "Choose a Template Curve")
            return {"CANCELLED"}
        if not setup.legs or setup.end_frame < setup.start_frame:
            self.report({"ERROR"}, "Register IK Goals and check Animation Start / End")
            return {"CANCELLED"}
        original_frame, valid_count = scene.frame_current_final, 0
        try:
            scene.frame_set(setup.start_frame)
            setup.template_path.data.use_path = True
            scene.frame_start, scene.frame_end = setup.start_frame, setup.end_frame
            for leg in setup.legs:
                goal, owner = resolve_walk_goal(leg)
                if not goal:
                    continue
                phase = (leg.phase_group % setup.phase_group_count) / setup.phase_group_count
                factor = phase + (1.0 if setup.reverse_path else 0.0)
                desired_position = world_location(goal, owner)
                path = find_or_create_walk_path(scene, setup, leg, goal, owner)
                constraint = find_or_create_motion_path_constraint(goal)
                clear_motion_path_animation(owner, constraint)
                align_walk_path(path, goal, owner, constraint, factor, desired_position)
                replace_motion_path_animation(
                    owner,
                    constraint,
                    setup.start_frame,
                    setup.end_frame,
                    setup.cycle_length,
                    phase,
                    setup.reverse_path,
                )
                valid_count += 1
        finally:
            set_frame(scene, original_frame)
        if not valid_count:
            self.report({"ERROR"}, "No registered IK Goals could be resolved")
            return {"CANCELLED"}
        return {"FINISHED"}


def draw_walk_setup(layout, context):
    setup = context.scene.ue_walk_setup
    walk = layout.box()
    walk.label(text="Walk Setup", icon="CON_FOLLOWPATH")
    walk.prop(setup, "template_path")
    walk.prop(setup, "reverse_path")
    row = walk.row(align=True)
    row.prop(setup, "start_frame")
    row.prop(setup, "end_frame")
    walk.prop(setup, "cycle_length")
    walk.prop(setup, "phase_group_count")
    walk.operator(ANIM_OT_add_selected_walk_goals.bl_idname, text="1. Add Selected IK Goals", icon="ADD")
    walk.operator(ANIM_OT_apply_walk_setup.bl_idname, text="2. Generate / Update Animation Keys", icon="FILE_REFRESH")
    walk.label(text="IK Goals and Phase Groups")
    for index, leg in enumerate(setup.legs):
        row = walk.row(align=True)
        row.label(text=walk_leg_label(leg))
        row.prop(leg, "phase_group", text="Group")
        remove = row.operator(ANIM_OT_remove_walk_goal.bl_idname, text="", icon="X")
        remove.index = index

    profiles = layout.box()
    profiles.label(text="Gait Profile Presets", icon="ACTION")
    profiles.label(text="Profiles save Action and Walk Setup values. Load one, then generate keys.", icon="INFO")
    for index, profile in enumerate(setup.profiles):
        row = profiles.row(align=True)
        icon = "RADIOBUT_ON" if index == setup.active_profile_index else "RADIOBUT_OFF"
        select = row.operator(ANIM_OT_select_walk_profile.bl_idname, text=profile.name or f"Profile {index + 1}", icon=icon)
        select.index = index
        row.label(text=profile.action.name if profile.action else "No Action")
    profiles.operator(ANIM_OT_save_walk_profile.bl_idname, text="Save Current Walk Setup as Profile", icon="ADD")
    profile = active_walk_profile(setup)
    if profile:
        profiles.prop(profile, "name")
        profiles.prop(profile, "action")
        row = profiles.row(align=True)
        row.operator(ANIM_OT_load_walk_profile.bl_idname, text="Load Selected Profile", icon="IMPORT")
        row.operator(ANIM_OT_remove_walk_profile.bl_idname, text="Remove Selected", icon="TRASH")


def world_location(target, owner):
    if isinstance(target, bpy.types.PoseBone):
        return (owner.matrix_world @ target.matrix).translation.copy()
    return target.matrix_world.translation.copy()


def bob_target_name(owner, target):
    return f"UE Pelvis Bob Target - {owner.name} - {target.name}"


def find_or_create_pelvis_bob_target(target, owner):
    constraint = target.constraints.get(PELVIS_BOB_CONSTRAINT_NAME)
    if constraint and constraint.type == "COPY_LOCATION" and constraint.target:
        return constraint, constraint.target

    helper = bpy.data.objects.get(bob_target_name(owner, target))
    if not helper or helper.type != "EMPTY":
        helper = bpy.data.objects.new(bob_target_name(owner, target), None)
        helper.empty_display_type = "SPHERE"
        helper.empty_display_size = 0.25
        bpy.context.collection.objects.link(helper)
    if not constraint or constraint.type != "COPY_LOCATION":
        constraint = target.constraints.new("COPY_LOCATION")
        constraint.name = PELVIS_BOB_CONSTRAINT_NAME
    return constraint, helper


def replace_world_bob_animation(helper, start_frame, cycle_length, height):
    action = ensure_action(helper)
    remove_action_fcurve(action, "location", index=2, owner=helper)

    baseline = helper.location.z
    middle_frame = start_frame + cycle_length / 2.0
    end_frame = start_frame + cycle_length
    for frame, value in (
        (start_frame, baseline),
        (middle_frame, baseline + height),
        (end_frame, baseline),
    ):
        helper.location.z = value
        helper.keyframe_insert(data_path="location", index=2, frame=frame)

    _channelbag, fcurve = find_action_fcurve(action, "location", index=2, owner=helper)
    if not fcurve:
        raise RuntimeError("Could not create the world-Z Pelvis Bob F-Curve")
    for point in fcurve.keyframe_points:
        point.interpolation = "BEZIER"
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    ensure_cycles_modifier(fcurve)


class ANIM_OT_setup_pelvis_bob(bpy.types.Operator):
    """Drive the active Pelvis element vertically in Blender world space"""

    bl_idname = "anim.ue_setup_pelvis_bob"
    bl_label = "Setup Pelvis World Bob"
    bl_options = {"REGISTER", "UNDO"}

    start_frame: bpy.props.IntProperty(name="Cycle Start", default=1)
    cycle_length: bpy.props.IntProperty(name="Cycle Length", default=20, min=1)
    height: bpy.props.FloatProperty(
        name="World Z Height",
        description="World-space Z rise from the Pelvis position at the cycle start",
        default=0.25,
        subtype="DISTANCE",
    )
    @classmethod
    def poll(cls, context):
        if context.mode == "POSE":
            return context.active_pose_bone is not None
        return context.active_object is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "start_frame")
        layout.prop(self, "cycle_length")
        layout.prop(self, "height")

    def execute(self, context):
        target = context.active_pose_bone if context.mode == "POSE" else context.active_object
        owner = context.object if isinstance(target, bpy.types.PoseBone) else target
        scene = context.scene
        original_frame = scene.frame_current_final
        try:
            scene.frame_set(self.start_frame)
            constraint, helper = find_or_create_pelvis_bob_target(target, owner)
            helper.location = world_location(target, owner)
            constraint.target = helper
            constraint.target_space = "WORLD"
            constraint.owner_space = "WORLD"
            constraint.use_offset = False
            constraint.use_x = False
            constraint.use_y = False
            constraint.use_z = True
            replace_world_bob_animation(
                helper,
                self.start_frame,
                self.cycle_length,
                self.height,
            )
        finally:
            scene.frame_set(math.floor(original_frame), subframe=original_frame % 1.0)

        self.report({"INFO"}, f"Set up world-Z bob on {target.name}")
        return {"FINISHED"}

class ANIM_OT_mirror_active_action(bpy.types.Operator):
    """Mirror an Action with Blender's native Paste Pose Flipped operation"""
    bl_idname = "anim.ue_mirror_active_action"
    bl_label = "Mirror Active Action"
    bl_options = {"REGISTER", "UNDO"}

    new_action_name: bpy.props.StringProperty(name="New Action", default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(
            obj and obj.type == "ARMATURE" and obj.mode == "POSE"
            and obj.animation_data and obj.animation_data.action
        )

    def invoke(self, context, event):
        self.new_action_name = f"{context.object.animation_data.action.name}_Mirrored"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        armature = context.object
        animation_data = armature.animation_data
        source = animation_data.action
        keyed = keyed_bones_by_frame(source, armature)
        if not keyed:
            self.report({"ERROR"}, "The active Action has no pose-bone transform keys")
            return {"CANCELLED"}

        original_frame = context.scene.frame_current_final
        original_selection = {bone.name: bone.select for bone in armature.pose.bones}
        original_active = armature.data.bones.active
        destination = source.copy()
        destination.name = self.new_action_name.strip() or f"{source.name}_Mirrored"
        succeeded = False
        try:
            for frame in sorted(keyed):
                keyed_names = {
                    name for name in keyed[frame] if armature.pose.bones.get(name)
                }
                if not keyed_names:
                    continue
                source_names = keyed_names | {
                    bpy.utils.flip_name(name) for name in keyed_names
                    if armature.pose.bones.get(bpy.utils.flip_name(name))
                }
                animation_data.action = source
                set_frame(context.scene, frame)
                select_bones(armature, source_names)
                context.view_layer.update()
                bpy.ops.pose.copy()

                animation_data.action = destination
                set_frame(context.scene, frame)
                context.view_layer.update()
                bpy.ops.pose.paste(flipped=True)

                target_names = {
                    bpy.utils.flip_name(name) for name in source_names
                    if armature.pose.bones.get(bpy.utils.flip_name(name))
                }
                select_bones(armature, target_names)
                for name in target_names:
                    insert_transform_keys(armature.pose.bones[name], frame)
            animation_data.action = destination
            succeeded = True
        finally:
            set_frame(context.scene, original_frame)
            select_bones(
                armature,
                (name for name, selected in original_selection.items() if selected),
                original_active.name if original_active else None,
            )
            if not succeeded:
                animation_data.action = source
                bpy.data.actions.remove(destination)

        self.report({"INFO"}, f"Created mirrored Action: {destination.name}")
        return {"FINISHED"}


class ANIM_PT_ue_animation_utilities(bpy.types.Panel):
    bl_label = "UE Animation Utilities"
    bl_idname = "ANIM_PT_ue_animation_utilities"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "UE Anim"

    def draw(self, context):
        layout = self.layout
        layout.operator(ANIM_OT_mirror_active_action.bl_idname, icon="MOD_MIRROR")
        layout.label(text="Processes only explicitly keyed frames.", icon="INFO")
        layout.separator()
        draw_walk_setup(layout, context)
        layout.separator()
        layout.label(text="Pelvis World Bob", icon="GRAPH")
        layout.operator(ANIM_OT_setup_pelvis_bob.bl_idname, icon="ANIM_DATA")


CLASSES = (
    ANIM_PG_walk_leg,
    ANIM_PG_walk_profile,
    ANIM_PG_walk_setup,
    ANIM_OT_select_walk_profile,
    ANIM_OT_save_walk_profile,
    ANIM_OT_load_walk_profile,
    ANIM_OT_remove_walk_profile,
    ANIM_OT_add_selected_walk_goals,
    ANIM_OT_remove_walk_goal,
    ANIM_OT_apply_walk_setup,
    ANIM_OT_mirror_active_action,
    ANIM_OT_setup_pelvis_bob,
    ANIM_PT_ue_animation_utilities,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ue_walk_setup = bpy.props.PointerProperty(
        type=ANIM_PG_walk_setup
    )


def unregister():
    del bpy.types.Scene.ue_walk_setup
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
