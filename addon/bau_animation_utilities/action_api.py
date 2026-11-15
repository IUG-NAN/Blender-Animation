"""Blender 5.2 layered-Action helpers shared by every tool."""

import re

import bpy
from bpy_extras import anim_utils


POSE_BONE_PATH = re.compile(r'^pose\.bones\["((?:[^"\\]|\\.)*)"\](.*)$')


def owner_channelbag(owner, action=None, create=False):
    """Return the Channelbag that ``owner`` reads from ``action`` (default: its assigned Action)."""
    animation_data = owner.animation_data_create() if create else owner.animation_data
    if animation_data is None:
        return None
    if action is None:
        action = animation_data.action
    if action is None:
        return None
    slot = animation_data.action_slot if animation_data.action == action else None
    if slot is None:
        slot = next(iter(action.slots), None)
    if slot is None:
        return None
    if create:
        return anim_utils.action_ensure_channelbag_for_slot(action, slot)
    return anim_utils.action_get_channelbag_for_slot(action, slot)


def owner_fcurves(owner, action=None):
    channelbag = owner_channelbag(owner, action)
    return list(channelbag.fcurves) if channelbag else []


def ensure_action(owner, name):
    animation_data = owner.animation_data_create()
    if animation_data.action is None:
        animation_data.action = bpy.data.actions.new(name)
    return animation_data.action


def ensure_group(channelbag, name):
    return channelbag.groups.get(name) or channelbag.groups.new(name)


def ensure_fcurve(channelbag, data_path, index, group_name=None):
    fcurve = channelbag.fcurves.find(data_path, index=index)
    if fcurve is None:
        fcurve = channelbag.fcurves.new(data_path, index=index)
        if group_name:
            fcurve.group = ensure_group(channelbag, group_name)
    return fcurve


def remove_fcurve(channelbag, data_path, index):
    fcurve = channelbag.fcurves.find(data_path, index=index) if channelbag else None
    if fcurve:
        channelbag.fcurves.remove(fcurve)
    return fcurve is not None


def ensure_cycles_modifier(fcurve):
    for modifier in fcurve.modifiers:
        if modifier.type == "CYCLES":
            return modifier
    cycles = fcurve.modifiers.new("CYCLES")
    cycles.mode_before = "REPEAT"
    cycles.mode_after = "REPEAT"
    return cycles


def set_frame(scene, frame):
    whole = int(frame // 1)
    scene.frame_set(whole, subframe=frame - whole)


def pose_bone_path(bone_name, suffix):
    return f'pose.bones["{bpy.utils.escape_identifier(bone_name)}"]{suffix}'


def split_pose_bone_path(data_path):
    """``pose.bones["X"].location`` -> (``X``, ``.location``); other paths -> (None, None)."""
    match = POSE_BONE_PATH.match(data_path)
    if not match:
        return None, None
    return bpy.utils.unescape_identifier(match.group(1)), match.group(2)
