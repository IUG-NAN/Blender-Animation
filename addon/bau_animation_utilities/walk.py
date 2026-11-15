"""Walk Setup: drive IK goals along a looping template curve with Follow Path.

The offset of each goal's Follow Path constraint is keyed in the owner's Action, so
the walk switches with the Action. Animation Start / End is split into Cycle Count
equal cycles (the cycle may be fractional), so the loop always closes at End.
"""

import bpy

from .action_api import (
    ensure_action,
    ensure_cycles_modifier,
    owner_channelbag,
    remove_fcurve,
    set_frame,
)


MOTION_PATH_CONSTRAINT_NAME = "BAU Motion Path"
LEGACY_MOTION_PATH_CONSTRAINT_NAMES = ("UE Motion Path",)
WALK_PATH_COLLECTION_NAME = "Walk Paths"
LEGACY_WALK_PATH_COLLECTION_NAMES = ("UE Walk Paths",)


def curve_object_poll(_self, obj):
    return obj.type == "CURVE"


def cycle_length(start_frame, end_frame, cycle_count):
    return (end_frame - start_frame) / max(1, cycle_count)


class BAU_PG_walk_leg(bpy.types.PropertyGroup):
    goal_object: bpy.props.PointerProperty(type=bpy.types.Object)
    goal_bone: bpy.props.StringProperty()
    phase_group: bpy.props.IntProperty(name="Group", default=0, min=0)
    path_object: bpy.props.PointerProperty(type=bpy.types.Object)


class BAU_PG_walk_profile(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Profile Name", default="Walk")
    action: bpy.props.PointerProperty(name="Action", type=bpy.types.Action)
    template_path: bpy.props.PointerProperty(type=bpy.types.Object, poll=curve_object_poll)
    start_frame: bpy.props.IntProperty(default=0)
    end_frame: bpy.props.IntProperty(default=30)
    cycle_count: bpy.props.IntProperty(default=1, min=1)
    phase_group_count: bpy.props.IntProperty(default=3, min=1, max=8)
    reverse_path: bpy.props.BoolProperty(default=True)
    legs: bpy.props.CollectionProperty(type=BAU_PG_walk_leg)


class BAU_PG_walk_setup(bpy.types.PropertyGroup):
    template_path: bpy.props.PointerProperty(
        name="Template Curve", type=bpy.types.Object, poll=curve_object_poll
    )
    start_frame: bpy.props.IntProperty(name="Animation Start", default=0)
    end_frame: bpy.props.IntProperty(name="Animation End", default=30)
    cycle_count: bpy.props.IntProperty(
        name="Cycle Count", default=1, min=1,
        description="Number of gait cycles between Animation Start and End. "
                    "One cycle lasts (End - Start) / Cycle Count frames",
    )
    phase_group_count: bpy.props.IntProperty(name="Phase Groups", default=3, min=1, max=8)
    reverse_path: bpy.props.BoolProperty(name="Reverse Curve Direction", default=True)
    legs: bpy.props.CollectionProperty(type=BAU_PG_walk_leg)
    active_leg_index: bpy.props.IntProperty(default=0)
    profiles: bpy.props.CollectionProperty(type=BAU_PG_walk_profile)
    active_profile_index: bpy.props.IntProperty(default=0)


SETTING_NAMES = (
    "template_path", "start_frame", "end_frame", "cycle_count",
    "phase_group_count", "reverse_path",
)


def copy_legs(source_legs, destination_legs):
    destination_legs.clear()
    for source_leg in source_legs:
        leg = destination_legs.add()
        leg.goal_object = source_leg.goal_object
        leg.goal_bone = source_leg.goal_bone
        leg.phase_group = source_leg.phase_group


def copy_settings(source, destination):
    for name in SETTING_NAMES:
        setattr(destination, name, getattr(source, name))
    copy_legs(source.legs, destination.legs)


def active_walk_profile(setup):
    if len(setup.profiles) == 0:
        return None
    setup.active_profile_index = max(0, min(setup.active_profile_index, len(setup.profiles) - 1))
    return setup.profiles[setup.active_profile_index]


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


def world_location(target, owner):
    if isinstance(target, bpy.types.PoseBone):
        return (owner.matrix_world @ target.matrix).translation.copy()
    return target.matrix_world.translation.copy()


def find_motion_path_constraint(goal):
    for name in (MOTION_PATH_CONSTRAINT_NAME, *LEGACY_MOTION_PATH_CONSTRAINT_NAMES):
        constraint = goal.constraints.get(name)
        if constraint and constraint.type == "FOLLOW_PATH":
            return constraint
    return None


def get_walk_path_collection(scene):
    for name in (WALK_PATH_COLLECTION_NAME, *LEGACY_WALK_PATH_COLLECTION_NAMES):
        collection = bpy.data.collections.get(name)
        if collection:
            return collection
    collection = bpy.data.collections.new(WALK_PATH_COLLECTION_NAME)
    scene.collection.children.link(collection)
    return collection


def find_or_create_walk_path(scene, template, leg, goal, owner):
    path = leg.path_object
    name = f"Walk Path - {owner.name} - {goal.name}"
    if not path or path.type != "CURVE":
        path = bpy.data.objects.get(name) or bpy.data.objects.get(f"UE {name}")
    if not path or path.type != "CURVE":
        path = template.copy()
        path.name = name
        get_walk_path_collection(scene).objects.link(path)
    path.data = template.data
    path.matrix_world = template.matrix_world.copy()
    leg.path_object = path
    return path


def phase_factor(phase):
    """Follow Path offset at Animation Start, kept inside 0..1 for both directions."""
    return phase % 1.0


def key_motion_path(owner, constraint, start_frame, end_frame, period, phase, reverse):
    """Key one linear 0..1 sweep per cycle, shifted in time by the phase; Cycles repeats it."""
    action = ensure_action(owner, f"{owner.name}Action")
    action.use_frame_range = True
    action.frame_start = start_frame
    action.frame_end = end_frame
    data_path = constraint.path_from_id("offset_factor")
    remove_fcurve(owner_channelbag(owner, action), data_path, 0)

    # Forward: offset = phase + t/period. Reverse: offset = phase - t/period (mod 1).
    # The 0 -> 1 (or 1 -> 0) sweep starts where that value wraps, inside the first cycle.
    shift = ((1.0 - phase) % 1.0) * period if not reverse else (phase % 1.0) * period
    first, second = (1.0, 0.0) if reverse else (0.0, 1.0)
    for value, frame in ((first, start_frame + shift), (second, start_frame + shift + period)):
        constraint.offset_factor = value
        constraint.keyframe_insert(data_path="offset_factor", frame=frame)

    fcurve = owner_channelbag(owner, action).fcurves.find(data_path, index=0)
    if fcurve is None:
        raise RuntimeError("Could not create the Follow Path animation curve")
    for point in fcurve.keyframe_points:
        point.interpolation = "LINEAR"
    ensure_cycles_modifier(fcurve)


def template_is_closed(template):
    splines = template.data.splines
    return bool(splines) and all(spline.use_cyclic_u for spline in splines)


class BAU_OT_select_walk_profile(bpy.types.Operator):
    bl_idname = "anim.bau_select_walk_profile"
    bl_label = "Select Gait Profile"
    bl_options = {"INTERNAL"}
    index: bpy.props.IntProperty(min=0)

    def execute(self, context):
        setup = context.scene.bau_walk_setup
        if self.index >= len(setup.profiles):
            return {"CANCELLED"}
        setup.active_profile_index = self.index
        return {"FINISHED"}


class BAU_OT_save_walk_profile(bpy.types.Operator):
    bl_idname = "anim.bau_save_walk_profile"
    bl_label = "Save Current Walk Setup as Profile"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(name="Profile Name", default="Walk")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        setup = context.scene.bau_walk_setup
        profile = setup.profiles.add()
        profile.name = self.name.strip() or "Walk"
        copy_settings(setup, profile)
        owner = action_owner(profile.legs)
        profile.action = owner.animation_data.action if owner and owner.animation_data else None
        setup.active_profile_index = len(setup.profiles) - 1
        return {"FINISHED"}


class BAU_OT_load_walk_profile(bpy.types.Operator):
    bl_idname = "anim.bau_load_walk_profile"
    bl_label = "Load Selected Profile into Walk Setup"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        setup = context.scene.bau_walk_setup
        profile = active_walk_profile(setup)
        if not profile:
            return {"CANCELLED"}
        copy_settings(profile, setup)
        owner = action_owner(setup.legs)
        if owner and profile.action:
            owner.animation_data_create().action = profile.action
        self.report({"INFO"}, f"Loaded Profile: {profile.name}. Generate keys to apply it.")
        return {"FINISHED"}


class BAU_OT_remove_walk_profile(bpy.types.Operator):
    bl_idname = "anim.bau_remove_walk_profile"
    bl_label = "Remove Selected Profile"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        setup = context.scene.bau_walk_setup
        if not active_walk_profile(setup):
            return {"CANCELLED"}
        setup.profiles.remove(setup.active_profile_index)
        setup.active_profile_index = min(setup.active_profile_index, max(0, len(setup.profiles) - 1))
        return {"FINISHED"}


class BAU_OT_add_selected_walk_goals(bpy.types.Operator):
    bl_idname = "anim.bau_add_selected_walk_goals"
    bl_label = "Add Selected IK Goals"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        setup = context.scene.bau_walk_setup
        if context.mode == "POSE":
            candidates = [(context.object, bone.name) for bone in (context.selected_pose_bones or [])]
        else:
            candidates = [(obj, "") for obj in context.selected_objects if obj != setup.template_path]
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


class BAU_OT_remove_walk_goal(bpy.types.Operator):
    bl_idname = "anim.bau_remove_walk_goal"
    bl_label = "Remove IK Goal"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    index: bpy.props.IntProperty()

    def execute(self, context):
        setup = context.scene.bau_walk_setup
        if self.index < 0 or self.index >= len(setup.legs):
            return {"CANCELLED"}
        setup.legs.remove(self.index)
        return {"FINISHED"}


class BAU_OT_apply_walk_setup(bpy.types.Operator):
    bl_idname = "anim.bau_apply_walk_setup"
    bl_label = "Generate / Update Animation Keys"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        setup = scene.bau_walk_setup
        template = setup.template_path
        if not template or template.type != "CURVE":
            self.report({"ERROR"}, "Choose a Template Curve")
            return {"CANCELLED"}
        if not setup.legs or setup.end_frame <= setup.start_frame:
            self.report({"ERROR"}, "Register IK Goals and check Animation Start / End")
            return {"CANCELLED"}
        if not template_is_closed(template):
            self.report({"WARNING"}, "Template Curve is not closed (Cyclic): the goal jumps at every loop")

        period = cycle_length(setup.start_frame, setup.end_frame, setup.cycle_count)
        original_frame, valid_count = scene.frame_current_final, 0
        try:
            scene.frame_set(setup.start_frame)
            template.data.use_path = True
            for leg in setup.legs:
                goal, owner = resolve_walk_goal(leg)
                if not goal:
                    continue
                phase = (leg.phase_group % setup.phase_group_count) / setup.phase_group_count
                constraint = find_motion_path_constraint(goal)
                # Sample the goal where the rig puts it, not where a previous walk path put it.
                if constraint:
                    constraint.mute = True
                    context.view_layer.update()
                desired_position = world_location(goal, owner)
                if constraint is None:
                    constraint = goal.constraints.new("FOLLOW_PATH")
                    constraint.name = MOTION_PATH_CONSTRAINT_NAME
                constraint.mute = False

                path = find_or_create_walk_path(scene, template, leg, goal, owner)
                constraint.target = path
                constraint.use_fixed_location = True
                constraint.offset_factor = phase_factor(phase)
                context.view_layer.update()
                path.location.y += desired_position.y - world_location(goal, owner).y
                context.view_layer.update()

                key_motion_path(
                    owner, constraint, setup.start_frame, setup.end_frame,
                    period, phase, setup.reverse_path,
                )
                valid_count += 1
        finally:
            set_frame(scene, original_frame)
        if not valid_count:
            self.report({"ERROR"}, "No registered IK Goals could be resolved")
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (
    BAU_PG_walk_leg,
    BAU_PG_walk_profile,
    BAU_PG_walk_setup,
    BAU_OT_select_walk_profile,
    BAU_OT_save_walk_profile,
    BAU_OT_load_walk_profile,
    BAU_OT_remove_walk_profile,
    BAU_OT_add_selected_walk_goals,
    BAU_OT_remove_walk_goal,
    BAU_OT_apply_walk_setup,
)
