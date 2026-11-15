bl_info = {
    "name": "Animation Utilities (BAU)",
    "author": "IUG-NAN",
    "version": (0, 5, 0),
    "blender": (5, 2, 0),
    "location": "3D View > right-click > Animation Utilities / Sidebar > Tool > Walk Setup / Dope Sheet > Action",
    "description": "Action mirroring, procedural walk cycles on motion paths and pelvis bob for game animation",
    "category": "Animation",
}

if "bpy" in locals():
    import importlib

    for _module in (action_api, mirror, walk, pelvis_bob, legacy, ui):  # noqa: F821
        importlib.reload(_module)
else:
    from . import action_api, mirror, walk, pelvis_bob, legacy, ui

import bpy


CLASSES = (*mirror.CLASSES, *walk.CLASSES, *pelvis_bob.CLASSES, *ui.CLASSES)


def _migrate_after_register():
    legacy.migrate_on_load()
    return None


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bau_walk_setup = bpy.props.PointerProperty(type=walk.BAU_PG_walk_setup)
    ui.register_menus()
    bpy.app.handlers.load_post.append(legacy.migrate_on_load)
    bpy.app.timers.register(_migrate_after_register, first_interval=0.1)


def unregister():
    if legacy.migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(legacy.migrate_on_load)
    if bpy.app.timers.is_registered(_migrate_after_register):
        bpy.app.timers.unregister(_migrate_after_register)
    ui.unregister_menus()
    del bpy.types.Scene.bau_walk_setup
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
