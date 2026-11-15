"""Mirror Action: swap left/right F-Curves without adding or moving any key.

Each pose-bone F-Curve is moved to the opposite-side bone (``bpy.utils.flip_name``)
and, for the channels that Blender's own Paste Pose Flipped negates, the key values
and both Bezier handles are negated. Key frames, interpolation, handle types, easing,
extrapolation and F-Curve modifiers stay exactly as they were, so the mirrored Action
has the same keys as the source, only on the other side. Custom properties (for
example Auto-Rig Pro's IK/FK switch) and constraint channels move with their bone.
"""

import bpy

from .action_api import (
    ensure_group,
    owner_channelbag,
    pose_bone_path,
    split_pose_bone_path,
)


# Channels Paste Pose Flipped negates (Blender: pose_transform / BKE_pose_flip rules).
NEGATED_INDICES = {
    ".location": {0},
    ".rotation_euler": {1, 2},
    ".rotation_quaternion": {2, 3},
    ".rotation_axis_angle": {2, 3},
}
ROTATION_SUFFIXES = {
    ".rotation_euler": "EULER",
    ".rotation_quaternion": "QUATERNION",
    ".rotation_axis_angle": "AXIS_ANGLE",
}
CONSTRAINT_PREFIX = '.constraints["'


def rotation_kind(pose_bone):
    mode = pose_bone.rotation_mode
    return mode if mode in {"QUATERNION", "AXIS_ANGLE"} else "EULER"


def flip_constraint_suffix(suffix, target_bone):
    """Map ``.constraints["IK.L"].influence`` to the flipped constraint name when it exists."""
    if not suffix.startswith(CONSTRAINT_PREFIX):
        return suffix
    end = suffix.find('"]', len(CONSTRAINT_PREFIX))
    if end < 0:
        return suffix
    name = bpy.utils.unescape_identifier(suffix[len(CONSTRAINT_PREFIX):end])
    flipped = bpy.utils.flip_name(name)
    if flipped != name and target_bone.constraints.get(flipped):
        return f'{CONSTRAINT_PREFIX}{bpy.utils.escape_identifier(flipped)}{suffix[end:]}'
    return suffix


def negate_fcurve(fcurve):
    for point in fcurve.keyframe_points:
        point.co.y = -point.co.y
        point.handle_left.y = -point.handle_left.y
        point.handle_right.y = -point.handle_right.y
    for modifier in fcurve.modifiers:
        if modifier.type == "FNGENERATOR":
            modifier.amplitude = -modifier.amplitude
            modifier.value_offset = -modifier.value_offset
        elif modifier.type == "GENERATOR":
            for i in range(len(modifier.coefficients)):
                modifier.coefficients[i] = -modifier.coefficients[i]


def mirror_plan(armature, channelbag):
    """Return [(fcurve, new_data_path, negate)] and a list of warnings."""
    bones = armature.pose.bones
    plan, warnings, mismatched = [], [], set()
    for fcurve in channelbag.fcurves:
        bone_name, suffix = split_pose_bone_path(fcurve.data_path)
        if bone_name is None:
            continue
        source_bone = bones.get(bone_name)
        target_name = bpy.utils.flip_name(bone_name)
        target_bone = bones.get(target_name)
        if source_bone is None or target_bone is None:
            warnings.append(f"{bone_name}: no opposite bone, left unchanged")
            continue
        kind = ROTATION_SUFFIXES.get(suffix)
        if kind and kind != rotation_kind(target_bone):
            mismatched.add(target_name)
        new_suffix = flip_constraint_suffix(suffix, target_bone)
        negate = fcurve.array_index in NEGATED_INDICES.get(suffix, ())
        plan.append((fcurve, target_name, pose_bone_path(target_name, new_suffix), negate))
    for name in sorted(mismatched):
        warnings.append(f"{name}: rotation mode differs from its opposite bone")
    return plan, warnings


def mirror_action(armature, source, new_name):
    """Create and assign a mirrored copy of ``source``. Returns (action, warnings)."""
    animation_data = armature.animation_data
    source_slot = animation_data.action_slot
    destination = source.copy()
    destination.name = new_name
    animation_data.action = destination
    if animation_data.action_slot is None and source_slot is not None:
        animation_data.action_slot = destination.slots.get(source_slot.identifier)
    channelbag = owner_channelbag(armature, destination)
    if channelbag is None:
        animation_data.action = source
        animation_data.action_slot = source_slot
        bpy.data.actions.remove(destination)
        return None, ["The Action has no channels for this Armature"]

    plan, warnings = mirror_plan(armature, channelbag)
    # Two passes so that hand.L -> hand.R and hand.R -> hand.L never collide.
    for number, (fcurve, _target, _path, _negate) in enumerate(plan):
        fcurve.data_path = f"__bau_mirror_{number}__"
    for fcurve, target_name, new_path, negate in plan:
        fcurve.data_path = new_path
        group = ensure_group(channelbag, target_name)
        if fcurve.group != group:
            fcurve.group = group
        if negate:
            negate_fcurve(fcurve)
    for group in list(channelbag.groups):
        if not group.channels:
            channelbag.groups.remove(group)
    return destination, warnings


class BAU_OT_mirror_action(bpy.types.Operator):
    """Create a left/right mirrored copy of the active Action. Keys stay on the same frames and channels, only moved to the opposite side"""

    bl_idname = "anim.bau_mirror_action"
    bl_label = "Mirror Action"
    bl_options = {"REGISTER", "UNDO"}

    new_action_name: bpy.props.StringProperty(name="New Action", default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(
            obj and obj.type == "ARMATURE"
            and obj.animation_data and obj.animation_data.action
        )

    def invoke(self, context, event):
        self.new_action_name = f"{context.object.animation_data.action.name}_Mirrored"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        armature = context.object
        source = armature.animation_data.action
        name = self.new_action_name.strip() or f"{source.name}_Mirrored"
        destination, warnings = mirror_action(armature, source, name)
        if destination is None:
            self.report({"ERROR"}, warnings[0])
            return {"CANCELLED"}
        for warning in warnings:
            self.report({"WARNING"}, warning)
        self.report({"INFO"}, f"Created mirrored Action: {destination.name}")
        return {"FINISHED"}


CLASSES = (BAU_OT_mirror_action,)
