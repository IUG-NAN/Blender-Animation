import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
from _support import run  # noqa: E402
from bau_animation_utilities import walk  # noqa: E402
from bau_animation_utilities.action_api import owner_channelbag  # noqa: E402


def make_curve(cyclic=True):
    data = bpy.data.curves.new("WalkTemplateData", "CURVE")
    data.dimensions = "3D"
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(3)
    for point, co in zip(spline.bezier_points, ((0, -1, 0), (0.5, -0.25, 0.8), (-0.5, 0.25, 0.8), (0, 1, 0))):
        point.co = co
        point.handle_left_type = point.handle_right_type = "AUTO"
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new("WalkTemplate", data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def make_armature():
    bpy.ops.object.armature_add(enter_editmode=True)
    arm = bpy.context.object
    arm.name = "Creature"
    bones = arm.data.edit_bones
    bones[0].name = "IK_A"
    bones[0].head, bones[0].tail = (0, -2, 0), (0, -2, 1)
    for name, y in (("IK_B", 0), ("IK_C", 2)):
        bone = bones.new(name)
        bone.head, bone.tail = (0, y, 0), (0, y, 1)
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def offset_curve(arm, leg):
    goal, owner = walk.resolve_walk_goal(leg)
    constraint = goal.constraints[walk.MOTION_PATH_CONSTRAINT_NAME]
    return owner_channelbag(owner).fcurves.find(constraint.path_from_id("offset_factor"), index=0)


def test():
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 250
    arm = make_armature()
    setup = scene.bau_walk_setup
    setup.template_path = make_curve()
    # 25 frames split into 2 cycles: 12.5 frames each, no divisibility required.
    setup.start_frame, setup.end_frame, setup.cycle_count = 0, 25, 2
    for phase, bone_name in enumerate(("IK_A", "IK_B", "IK_C")):
        leg = setup.legs.add()
        leg.goal_object, leg.goal_bone, leg.phase_group = arm, bone_name, phase

    for reverse in (True, False):
        setup.reverse_path = reverse
        assert "FINISHED" in bpy.ops.anim.bau_apply_walk_setup()
        action = arm.animation_data.action
        assert action.use_frame_range and tuple(action.frame_range) == (0.0, 25.0)
        assert (scene.frame_start, scene.frame_end) == (1, 250), "scene range must not change"
        for leg in setup.legs:
            curve = offset_curve(arm, leg)
            assert any(mod.type == "CYCLES" for mod in curve.modifiers)
            values = [curve.evaluate(t / 4) for t in range(0, 101)]
            assert all(-1e-6 <= v <= 1 + 1e-6 for v in values), "offset must stay in 0..1"
            # Loop closes at End: same position every 12.5 frames.
            for t in (0.0, 3.0, 7.25, 11.0):
                a, b = curve.evaluate(t) % 1.0, curve.evaluate(t + 12.5) % 1.0
                assert min(abs(a - b), 1 - abs(a - b)) < 1e-5
            phase = leg.phase_group / setup.phase_group_count
            start = curve.evaluate(0.0) % 1.0
            assert min(abs(start - phase), 1 - abs(start - phase)) < 1e-5, (reverse, phase, start)
            step = (curve.evaluate(1.0) - curve.evaluate(0.5)) % 1.0
            assert (step > 0.5) == reverse, "direction"

    # Re-applying does not move the paths (goal sampled with the constraint muted).
    locations = [leg.path_object.location.copy() for leg in setup.legs]
    assert "FINISHED" in bpy.ops.anim.bau_apply_walk_setup()
    assert all((leg.path_object.location - loc).length < 1e-6 for leg, loc in zip(setup.legs, locations))

    assert "FINISHED" in bpy.ops.anim.bau_save_walk_profile(name="Walk")
    profile = setup.profiles[0]
    assert profile.name == "Walk" and len(profile.legs) == 3
    assert profile.cycle_count == 2 and profile.action == arm.animation_data.action
    setup.cycle_count = 5
    setup.legs[0].phase_group = 2
    assert "FINISHED" in bpy.ops.anim.bau_load_walk_profile()
    assert setup.cycle_count == 2 and setup.legs[0].phase_group == 0
    assert "FINISHED" in bpy.ops.anim.bau_remove_walk_profile()
    assert len(setup.profiles) == 0


if __name__ == "__main__":
    run("test_walk", test)
