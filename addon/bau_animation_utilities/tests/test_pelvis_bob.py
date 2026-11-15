import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
from _support import activate, run  # noqa: E402
from bau_animation_utilities.action_api import owner_fcurves  # noqa: E402


def make_rig():
    bpy.ops.object.armature_add(enter_editmode=True)
    arm = bpy.context.object
    root = arm.data.edit_bones[0]
    root.name = "c_root_master.x"
    # Bone lying along +Y, rolled: its local axes are not world axes.
    root.head, root.tail = (0, 0, 1), (0, 0.5, 1)
    root.roll = 0.7
    bpy.ops.object.mode_set(mode="POSE")
    arm.rotation_euler.z = 0.4
    pelvis = arm.pose.bones["c_root_master.x"]
    for frame, x in ((0, 0.0), (10, 0.2), (20, 0.0)):
        pelvis.location.x = x
        pelvis.keyframe_insert("location", index=0, frame=frame)
    return arm, pelvis


def world_z(arm, pelvis, frame):
    bpy.context.scene.frame_set(frame)
    return (arm.matrix_world @ pelvis.matrix).translation.z


def key_frames(arm):
    return {(fc.data_path, fc.array_index): [p.co.x for p in fc.keyframe_points] for fc in owner_fcurves(arm)}


def test():
    arm, pelvis = make_rig()
    activate(arm)
    arm.data.bones.active = arm.data.bones[pelvis.name]
    action = arm.animation_data.action
    baseline = {f: world_z(arm, pelvis, f) for f in (0, 5, 10, 15, 20)}
    keys_before = key_frames(arm)

    # Old 0.4 setup on the same control: Copy Location from a helper Empty.
    helper = bpy.data.objects.new("UE Pelvis Bob Target - Armature - c_root_master.x", None)
    bpy.context.scene.collection.objects.link(helper)
    helper_name = helper.name
    legacy = pelvis.constraints.new("COPY_LOCATION")
    legacy.name = "UE Pelvis World Bob"
    legacy.target = helper

    for _ in range(2):  # Running twice replaces the bob, never stacks it.
        assert "FINISHED" in bpy.ops.anim.bau_setup_pelvis_bob(start_frame=0, cycle_length=20, height=0.3)
    assert "UE Pelvis World Bob" not in pelvis.constraints
    assert bpy.data.objects.get(helper_name) is None

    # No keys were added or moved: only F-Curve modifiers inside this Action.
    keys_after = key_frames(arm)
    assert all(keys_after.get(k) == v for k, v in keys_before.items())
    assert all(not v for k, v in keys_after.items() if k not in keys_before)
    bob_mods = [m for fc in owner_fcurves(arm) for m in fc.modifiers if m.name == "Pelvis Bob"]
    assert bob_mods and len(bob_mods) <= 3

    for frame in (0, 5, 10, 15, 20):
        rise = 0.3 * (1 - math.cos(2 * math.pi * frame / 20)) / 2
        got = world_z(arm, pelvis, frame) - baseline[frame]
        assert abs(got - rise) < 1e-4, (frame, got, rise)

    # The bob lives in the Action: another Action has no bob.
    other = bpy.data.actions.new("Idle")
    arm.animation_data.action = other
    assert world_z(arm, pelvis, 10) - baseline[0] < 1e-6
    arm.animation_data.action = action
    assert world_z(arm, pelvis, 10) - baseline[10] > 0.29

    assert "FINISHED" in bpy.ops.anim.bau_remove_pelvis_bob()
    assert not [m for fc in owner_fcurves(arm) for m in fc.modifiers if m.name == "Pelvis Bob"]
    assert key_frames(arm) == keys_before
    assert abs(world_z(arm, pelvis, 10) - baseline[10]) < 1e-6


if __name__ == "__main__":
    run("test_pelvis_bob", test)
