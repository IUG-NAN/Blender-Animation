"""Carry Walk Setup data saved by UE Animation Utilities 0.4 into this add-on."""

import bpy
from bpy.app.handlers import persistent


LEGACY_KEY = "ue_walk_setup"
SETTING_KEYS = ("template_path", "start_frame", "end_frame", "phase_group_count", "reverse_path")


def _get(group, key, default=None):
    try:
        return group[key]
    except (KeyError, TypeError):
        return default


def _cycle_count(old):
    start, end = _get(old, "start_frame", 0), _get(old, "end_frame", 30)
    length = _get(old, "cycle_length", 30) or 1
    return max(1, round((end - start) / length))


def _copy_legs(old_legs, legs):
    for old_leg in old_legs or ():
        leg = legs.add()
        leg.goal_object = _get(old_leg, "goal_object")
        leg.goal_bone = _get(old_leg, "goal_bone", "")
        leg.phase_group = _get(old_leg, "phase_group", 0)
        leg.path_object = _get(old_leg, "path_object")


def _copy_settings(old, new):
    for key in SETTING_KEYS:
        value = _get(old, key)
        if value is not None:
            setattr(new, key, value)
    new.cycle_count = _cycle_count(old)
    _copy_legs(_get(old, "legs"), new.legs)


def migrate_scene(scene):
    system = scene.bl_system_properties_get()
    old = _get(system, LEGACY_KEY) if system is not None else None
    new = scene.bau_walk_setup
    if old is None or len(new.legs) or len(new.profiles):
        return False
    if not _get(old, "legs") and not _get(old, "profiles"):
        return False
    _copy_settings(old, new)
    for old_profile in _get(old, "profiles") or ():
        profile = new.profiles.add()
        profile.name = _get(old_profile, "name", "Walk")
        profile.action = _get(old_profile, "action")
        _copy_settings(old_profile, profile)
    new.active_profile_index = _get(old, "active_profile_index", 0)
    return True


@persistent
def migrate_on_load(_dummy=None):
    for scene in bpy.data.scenes:
        migrate_scene(scene)
