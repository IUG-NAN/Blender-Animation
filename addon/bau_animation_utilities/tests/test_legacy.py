"""Walk Setup saved by UE Animation Utilities 0.4 is carried over on load."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
from _support import addon  # noqa: E402


class OldLeg(bpy.types.PropertyGroup):
    goal_object: bpy.props.PointerProperty(type=bpy.types.Object)
    goal_bone: bpy.props.StringProperty()
    phase_group: bpy.props.IntProperty()
    path_object: bpy.props.PointerProperty(type=bpy.types.Object)


class OldProfile(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    action: bpy.props.PointerProperty(type=bpy.types.Action)
    start_frame: bpy.props.IntProperty()
    end_frame: bpy.props.IntProperty()
    cycle_length: bpy.props.IntProperty()
    phase_group_count: bpy.props.IntProperty()
    reverse_path: bpy.props.BoolProperty()
    legs: bpy.props.CollectionProperty(type=OldLeg)


class OldSetup(bpy.types.PropertyGroup):
    start_frame: bpy.props.IntProperty()
    end_frame: bpy.props.IntProperty()
    cycle_length: bpy.props.IntProperty()
    phase_group_count: bpy.props.IntProperty()
    reverse_path: bpy.props.BoolProperty()
    legs: bpy.props.CollectionProperty(type=OldLeg)
    profiles: bpy.props.CollectionProperty(type=OldProfile)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for cls in (OldLeg, OldProfile, OldSetup):
        bpy.utils.register_class(cls)
    bpy.types.Scene.ue_walk_setup = bpy.props.PointerProperty(type=OldSetup)
    scene = bpy.context.scene
    goal = bpy.data.objects.new("Goal", None)
    action = bpy.data.actions.new("Walk")
    old = scene.ue_walk_setup
    old.start_frame, old.end_frame, old.cycle_length, old.phase_group_count = 0, 30, 15, 2
    leg = old.legs.add()
    leg.goal_object, leg.phase_group = goal, 1
    profile = old.profiles.add()
    profile.name, profile.action = "Run", action
    profile.start_frame, profile.end_frame, profile.cycle_length = 0, 24, 8
    profile.legs.add().goal_object = goal
    del bpy.types.Scene.ue_walk_setup
    for cls in (OldSetup, OldProfile, OldLeg):
        bpy.utils.unregister_class(cls)

    addon.register()
    try:
        addon.legacy.migrate_on_load()
        new = scene.bau_walk_setup
        assert new.cycle_count == 2 and new.phase_group_count == 2
        assert new.legs[0].goal_object == goal and new.legs[0].phase_group == 1
        assert new.profiles[0].name == "Run" and new.profiles[0].action == action
        assert new.profiles[0].cycle_count == 3 and new.profiles[0].legs[0].goal_object == goal
        new.cycle_count = 4
        addon.legacy.migrate_on_load()  # Never overwrites data already in the new add-on.
        assert new.cycle_count == 4 and len(new.profiles) == 1
    finally:
        addon.unregister()
    print("test_legacy: PASS")


if __name__ == "__main__":
    main()
