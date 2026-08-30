import bpy
import importlib.util
import sys

ADDON = r"F:\Blender_Dev\addon\ue_animation_utilities\__init__.py"


def make_curve():
    data = bpy.data.curves.new("WalkTemplateData", "CURVE")
    data.dimensions = "3D"
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(3)
    for point, co in zip(spline.bezier_points, ((0,-1,0),(.5,-.25,.8),(-.5,.25,.8),(0,1,0))):
        point.co = co
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new("WalkTemplate", data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def make_armature():
    bpy.ops.object.armature_add(enter_editmode=True)
    arm = bpy.context.object
    arm.name = "Creature"
    bones = arm.data.edit_bones
    bones[0].name = "IK_A"
    bones[0].head, bones[0].tail = (0,-2,0), (0,-2,1)
    for name, y in (("IK_B",0), ("IK_C",2)):
        bone = bones.new(name)
        bone.head, bone.tail = (0,y,0), (0,y,1)
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


spec = importlib.util.spec_from_file_location("ue_animation_utilities", ADDON)
addon = importlib.util.module_from_spec(spec)
sys.modules["ue_animation_utilities"] = addon
spec.loader.exec_module(addon)
addon.register()
try:
    arm = make_armature()
    setup = bpy.context.scene.ue_walk_setup
    setup.template_path = make_curve()
    setup.start_frame, setup.end_frame, setup.cycle_length = 0, 30, 15
    for phase, bone_name in enumerate(("IK_A", "IK_B", "IK_C")):
        leg = setup.legs.add()
        leg.goal_object, leg.goal_bone, leg.phase_group = arm, bone_name, phase

    assert "FINISHED" in bpy.ops.anim.ue_apply_walk_setup()
    assert arm.animation_data and arm.animation_data.action
    assert addon.action_fcurves(arm.animation_data.action, arm)
    action = arm.animation_data.action
    assert action.use_frame_range
    assert tuple(action.frame_range) == (0.0, 30.0)
    assert len(setup.legs) == 3
    assert all(leg.path_object for leg in setup.legs)
    for leg in setup.legs:
        goal, owner = addon.resolve_walk_goal(leg)
        constraint = goal.constraints[addon.MOTION_PATH_CONSTRAINT_NAME]
        _channelbag, curve = addon.find_action_fcurve(
            owner.animation_data.action,
            constraint.path_from_id("offset_factor"),
            index=0,
            owner=owner,
        )
        assert curve and any(mod.type == "CYCLES" for mod in curve.modifiers)
        assert abs(curve.evaluate(7.5) - curve.evaluate(22.5)) < 1e-6

    assert "FINISHED" in bpy.ops.anim.ue_save_walk_profile(name="Walk")
    profile = setup.profiles[0]
    assert profile.name == "Walk"
    assert len(profile.legs) == 3
    assert profile.action == arm.animation_data.action

    setup.cycle_length = 12
    setup.legs[0].phase_group = 2
    assert "FINISHED" in bpy.ops.anim.ue_load_walk_profile()
    assert setup.cycle_length == 15
    assert setup.legs[0].phase_group == 0
    assert arm.animation_data.action == profile.action

    assert "FINISHED" in bpy.ops.anim.ue_remove_walk_profile()
    assert len(setup.profiles) == 0
    print("REBUILT_WALK_PROFILE_TEST_PASS")
finally:
    addon.unregister()
