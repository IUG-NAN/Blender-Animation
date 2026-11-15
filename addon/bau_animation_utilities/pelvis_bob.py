"""Pelvis Bob: a world-Z up/down cycle stored inside the Action as F-Curve modifiers.

The bob is a Built-In Function (cosine) modifier named "Pelvis Bob" on the target's
location F-Curves. It adds to the existing keys, inserts no keyframes, and switches
with the Action. World Z is converted to the target's local location axes using its
orientation at Cycle Start.
"""

import math

import bpy
from mathutils import Vector

from .action_api import ensure_action, ensure_fcurve, owner_channelbag, set_frame


BOB_MODIFIER_NAME = "Pelvis Bob"
LEGACY_BOB_CONSTRAINT_NAME = "UE Pelvis World Bob"
AXIS_EPSILON = 1e-5


def bob_target(context):
    if context.mode == "POSE":
        bone = context.active_pose_bone
        return (bone, context.object) if bone else (None, None)
    obj = context.active_object
    return obj, obj


def location_path(target):
    return target.path_from_id("location") if isinstance(target, bpy.types.PoseBone) else "location"


def world_z_in_local(target, owner):
    """Local location vector that moves the target by +1 on world Z."""
    if isinstance(target, bpy.types.PoseBone):
        parent_space = owner.matrix_world @ target.matrix @ target.matrix_basis.inverted()
    else:
        parent_space = target.matrix_world @ target.matrix_basis.inverted()
    return parent_space.to_3x3().inverted() @ Vector((0.0, 0.0, 1.0))


def remove_legacy_bob(target):
    """Remove the Copy Location constraint and helper Empty made by UE Animation Utilities 0.4."""
    constraint = target.constraints.get(LEGACY_BOB_CONSTRAINT_NAME)
    if not constraint:
        return False
    helper = constraint.target
    target.constraints.remove(constraint)
    if helper and helper.type == "EMPTY" and helper.name.startswith("UE Pelvis Bob Target") and helper.users <= 1:
        bpy.data.objects.remove(helper)
    return True


def remove_bob(channelbag, target, data_path):
    if channelbag is None:
        return
    for index in range(3):
        fcurve = channelbag.fcurves.find(data_path, index=index)
        if fcurve is None:
            continue
        ours = [m for m in fcurve.modifiers if m.name == BOB_MODIFIER_NAME]
        if ours and not fcurve.keyframe_points and not ours[0].use_additive:
            # Channel had no keys: put back the value it had before the bob.
            target.location[index] = ours[0].amplitude + ours[0].value_offset
        for modifier in ours:
            fcurve.modifiers.remove(modifier)
        if ours and not fcurve.keyframe_points and not fcurve.modifiers:
            channelbag.fcurves.remove(fcurve)


def add_bob(channelbag, target, data_path, local_axis, start_frame, cycle_length, height):
    omega = 2.0 * math.pi / cycle_length
    group = target.name
    for index in range(3):
        rise = height * local_axis[index]
        if abs(rise) < AXIS_EPSILON * max(1.0, abs(height)):
            continue
        existing = channelbag.fcurves.find(data_path, index=index)
        has_keys = bool(existing and existing.keyframe_points)
        fcurve = existing or ensure_fcurve(channelbag, data_path, index, group)
        modifier = fcurve.modifiers.new("FNGENERATOR")
        modifier.name = BOB_MODIFIER_NAME
        modifier.function_type = "COS"
        # rise * (1 - cos(omega * (t - start))) / 2: base value at Cycle Start, peak mid-cycle.
        modifier.amplitude = -rise / 2.0
        modifier.phase_multiplier = omega
        modifier.phase_offset = -omega * start_frame
        if has_keys:
            modifier.use_additive = True
            modifier.value_offset = rise / 2.0
        else:
            # No keys on this channel: keep its current value as the base instead of adding a key.
            modifier.use_additive = False
            modifier.value_offset = target.location[index] + rise / 2.0


class BAU_OT_setup_pelvis_bob(bpy.types.Operator):
    """Add a world-Z up/down cycle to the active Pelvis control inside its Action (no keys are added)"""

    bl_idname = "anim.bau_setup_pelvis_bob"
    bl_label = "Pelvis Bob"
    bl_options = {"REGISTER", "UNDO"}

    start_frame: bpy.props.IntProperty(name="Cycle Start", default=1)
    cycle_length: bpy.props.FloatProperty(name="Cycle Length", default=20.0, min=1.0)
    height: bpy.props.FloatProperty(
        name="World Z Height",
        description="World-space Z rise at mid-cycle from the position at Cycle Start",
        default=0.25,
        subtype="DISTANCE",
    )

    @classmethod
    def poll(cls, context):
        target, _owner = bob_target(context)
        return target is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        target, owner = bob_target(context)
        scene = context.scene
        original_frame = scene.frame_current_final
        try:
            set_frame(scene, self.start_frame)
            if remove_legacy_bob(target):
                context.view_layer.update()
                self.report({"INFO"}, "Removed the old Pelvis World Bob constraint and Empty")
            action = ensure_action(owner, f"{owner.name}Action")
            channelbag = owner_channelbag(owner, action, create=True)
            data_path = location_path(target)
            remove_bob(channelbag, target, data_path)
            context.view_layer.update()
            add_bob(
                channelbag, target, data_path, world_z_in_local(target, owner),
                self.start_frame, self.cycle_length, self.height,
            )
        finally:
            set_frame(scene, original_frame)
        self.report({"INFO"}, f"Pelvis Bob added to {target.name} in {action.name}")
        return {"FINISHED"}


class BAU_OT_remove_pelvis_bob(bpy.types.Operator):
    """Remove the Pelvis Bob from the active control in the current Action"""

    bl_idname = "anim.bau_remove_pelvis_bob"
    bl_label = "Remove Pelvis Bob"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        target, owner = bob_target(context)
        return bool(target and owner.animation_data and owner.animation_data.action)

    def execute(self, context):
        target, owner = bob_target(context)
        remove_bob(owner_channelbag(owner), target, location_path(target))
        return {"FINISHED"}


CLASSES = (BAU_OT_setup_pelvis_bob, BAU_OT_remove_pelvis_bob)
