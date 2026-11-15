"""Load the add-on from this repository for the tests.

Run a test with Blender (``blender --background --factory-startup --python <test>``)
or with the ``bpy`` module from PyPI (``python <test>``).
"""

import sys
from pathlib import Path

import bpy

ADDON_PARENT = Path(__file__).resolve().parents[2]
if str(ADDON_PARENT) not in sys.path:
    sys.path.insert(0, str(ADDON_PARENT))

import bau_animation_utilities as addon  # noqa: E402


def activate(obj):
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def run(name, test):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon.register()
    try:
        test()
    finally:
        addon.unregister()
    print(f"{name}: PASS")
