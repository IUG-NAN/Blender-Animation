import bpy
import importlib.util
import sys


ADDON = r"F:\Blender_Dev\addon\ue_animation_utilities\__init__.py"


def activate(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def make_mirror_armature():
    bpy.ops.object.armature_add(enter_editmode=True)
    armature = bpy.context.object
    bones = armature.data.edit_bones
    bones[0].name = "hand.l"
    bones[0].head, bones[0].tail = (-1, 0, 0), (-1, 0, 1)
    right = bones.new("hand.r")
    right.head, right.tail = (1, 0, 0), (1, 0, 1)
    bpy.ops.object.mode_set(mode="POSE")
    armature.pose.bones["hand.l"].location.x = 0.25
    armature.pose.bones["hand.l"].keyframe_insert(data_path="location", frame=1)
    return armature


spec = importlib.util.spec_from_file_location("ue_animation_utilities", ADDON)
addon = importlib.util.module_from_spec(spec)
sys.modules["ue_animation_utilities"] = addon
spec.loader.exec_module(addon)
addon.register()
try:
    bpy.ops.object.empty_add(type="PLAIN_AXES")
    pelvis = bpy.context.object
    activate(pelvis)
    assert "FINISHED" in bpy.ops.anim.ue_setup_pelvis_bob(
        start_frame=0,
        cycle_length=20,
        height=0.5,
    )
    bob_constraint = pelvis.constraints[addon.PELVIS_BOB_CONSTRAINT_NAME]
    helper = bob_constraint.target
    helper_action = helper.animation_data.action
    helper_curves = addon.action_fcurves(helper_action, helper)
    assert any(curve.data_path == "location" and curve.array_index == 2 for curve in helper_curves)

    armature = make_mirror_armature()
    activate(armature)
    source = armature.animation_data.action
    source_curves = addon.action_fcurves(source, armature)
    assert source_curves

    assert "FINISHED" in bpy.ops.anim.ue_mirror_active_action(
        new_action_name="MirrorAction52"
    )
    destination = armature.animation_data.action
    assert destination.name == "MirrorAction52"
    assert destination != source
    assert addon.action_fcurves(destination, armature)
    assert addon.action_fcurves(source, armature)
    print("BLENDER52_ACTION_API_TEST_PASS")
finally:
    addon.unregister()
