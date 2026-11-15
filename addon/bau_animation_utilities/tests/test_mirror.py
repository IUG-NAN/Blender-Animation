import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
from mathutils import Quaternion  # noqa: E402
from _support import activate, addon, run  # noqa: E402
from bau_animation_utilities.action_api import owner_fcurves  # noqa: E402

PAIRS = {"hand.L": "QUATERNION", "foot.L": "XYZ"}


def make_rig():
    bpy.ops.object.armature_add(enter_editmode=True)
    arm = bpy.context.object
    bones = arm.data.edit_bones
    bones[0].name = "spine"
    bones[0].head, bones[0].tail = (0, 0, 1), (0, 0, 2)
    for name, z in (("hand.L", 1.5), ("foot.L", 0.1)):
        for side, x in (("L", 1.0), ("R", -1.0)):
            bone = bones.new(name[:-1] + side)
            bone.head, bone.tail = (x, 0, z), (x * 1.5, 0, z)
            bone.roll = 0.3 if side == "L" else -0.3
    bpy.ops.object.mode_set(mode="POSE")
    for name, mode in PAIRS.items():
        for side in "LR":
            bone = arm.pose.bones[name[:-1] + side]
            bone.rotation_mode = mode
            bone["ik_fk"] = 0.0
    bone = arm.pose.bones["hand.L"].constraints.new("COPY_ROTATION")
    bone.name = "Follow.L"
    arm.pose.bones["hand.R"].constraints.new("COPY_ROTATION").name = "Follow.R"
    return arm


def animate(arm):
    pb = arm.pose.bones
    hl, hr, fl, fr, spine = pb["hand.L"], pb["hand.R"], pb["foot.L"], pb["foot.R"], pb["spine"]
    hl.location = (0.2, 0.1, -0.1); hl.keyframe_insert("location", frame=1)
    hl.location = (0.4, 0.0, 0.1); hl.keyframe_insert("location", frame=9)
    hl.rotation_quaternion = Quaternion((0.9, 0.1, 0.3, -0.2)).normalized(); hl.keyframe_insert("rotation_quaternion", frame=1)
    hl.rotation_quaternion = Quaternion((0.8, -0.2, 0.1, 0.4)).normalized(); hl.keyframe_insert("rotation_quaternion", frame=13)
    hl["ik_fk"] = 1.0; hl.keyframe_insert('["ik_fk"]', frame=1)
    hl["ik_fk"] = 0.0; hl.keyframe_insert('["ik_fk"]', frame=9)
    hl.constraints["Follow.L"].influence = 0.25
    hl.constraints["Follow.L"].keyframe_insert("influence", frame=4)
    hr.rotation_quaternion = Quaternion((0.95, 0.0, -0.2, 0.1)).normalized(); hr.keyframe_insert("rotation_quaternion", frame=5)
    fr.rotation_euler = (0.2, 0.3, -0.4); fr.keyframe_insert("rotation_euler", index=2, frame=3)
    fr.rotation_euler = (0.1, -0.3, 0.5); fr.keyframe_insert("rotation_euler", index=2, frame=11)
    fl.rotation_euler = (0.3, 0.2, 0.1); fl.keyframe_insert("rotation_euler", index=0, frame=7)
    spine.location = (0.1, 0.2, 0.0); spine.keyframe_insert("location", frame=2)
    spine.location = (-0.3, 0.0, 0.2); spine.keyframe_insert("location", frame=12)
    # Hand-shaped handles on one curve to check they are carried over.
    for fcurve in owner_fcurves(arm):
        if fcurve.data_path == 'pose.bones["hand.L"].location' and fcurve.array_index == 0:
            point = fcurve.keyframe_points[0]
            point.handle_left_type = point.handle_right_type = "FREE"
            point.handle_right.y += 0.3
    return arm.animation_data.action


def snapshot(arm, action):
    return {
        (fc.data_path, fc.array_index): [
            (p.co.x, p.co.y, p.handle_left.y, p.handle_right.y, p.interpolation, p.handle_right_type)
            for p in fc.keyframe_points
        ]
        for fc in owner_fcurves(arm, action)
    }


def flipped(path):
    return path.replace(".L", ".#").replace(".R", ".L").replace(".#", ".R")


def animated_values(arm, action):
    """Current pose value of every transform channel the Action animates."""
    values = {}
    for fc in owner_fcurves(arm, action):
        if fc.data_path.endswith(("location", "rotation_quaternion", "rotation_euler", "scale")):
            value = arm.path_resolve(fc.data_path)
            if fc.data_path.endswith("rotation_quaternion"):
                value = Quaternion(value).normalized()  # Paste Pose normalizes quaternions.
            values[(fc.data_path, fc.array_index)] = value[fc.array_index]
    return values


def test():
    arm = make_rig()
    activate(arm)
    source = animate(arm)
    before = snapshot(arm, source)

    assert "FINISHED" in bpy.ops.anim.bau_mirror_action(new_action_name="Mirrored")
    mirrored = arm.animation_data.action
    assert mirrored.name == "Mirrored" and mirrored != source
    assert snapshot(arm, source) == before, "source Action changed"

    after = snapshot(arm, mirrored)
    # 1. Same channels and same key frames, only on the opposite side.
    assert set(after) == {(flipped(path), index) for path, index in before}, sorted(after)
    for (path, index), keys in before.items():
        mirrored_keys = after[(flipped(path), index)]
        assert [k[0] for k in mirrored_keys] == [k[0] for k in keys]
        assert [k[4:] for k in mirrored_keys] == [k[4:] for k in keys]
    # Constraint channel follows the flipped constraint name.
    assert ('pose.bones["hand.R"].constraints["Follow.R"].influence', 0) in after
    # 2. Custom property keys moved to the other side.
    assert [k[1] for k in after[('pose.bones["hand.R"]["ik_fk"]', 0)]] == [1.0, 0.0]
    assert ('pose.bones["hand.L"]["ik_fk"]', 0) not in after
    # Hand-made handle is negated with the value on a negated channel.
    src = before[('pose.bones["hand.L"].location', 0)][0]
    dst = after[('pose.bones["hand.R"].location', 0)][0]
    assert abs(dst[1] + src[1]) < 1e-6 and abs(dst[3] + src[3]) < 1e-6

    # Every frame matches Blender's own Paste Pose Flipped of the source pose.
    scene = bpy.context.scene
    for frame in range(0, 15):
        arm.animation_data.action = mirrored
        scene.frame_set(frame)
        expected = animated_values(arm, mirrored)
        arm.animation_data.action = source
        scene.frame_set(frame)
        for pb in arm.pose.bones:
            pb.select = True
        bpy.ops.pose.copy()
        arm.animation_data.action = mirrored
        scene.frame_set(frame)
        bpy.ops.pose.paste(flipped=True)
        pasted = animated_values(arm, mirrored)
        for channel, value in expected.items():
            assert abs(value - pasted[channel]) < 1e-5, (frame, channel, value, pasted[channel])
    arm.animation_data.action = mirrored


if __name__ == "__main__":
    run("test_mirror", test)
