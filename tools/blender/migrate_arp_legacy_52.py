"""One-shot migration for legacy Auto-Rig Pro rigs in Blender 5.2.

Run from Blender's Text Editor with the old ARP armature active, or:

    blender --background character.blend --python tools/blender/migrate_arp_legacy_52.py

The script saves a sibling ``*_pre_arp_legacy_migration.blend`` copy before
changing the current file. It never writes to the Auto-Rig Pro add-on files.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import bpy


SUPPORTED_BLENDER = (5, 2)
SUPPORTED_ARP_VERSIONS = {(3, 78, 45)}
LOG_TEXT_NAME = "ARP Legacy Migration Log"


def log(lines: list[str], message: str) -> None:
    lines.append(message)
    print(f"[ARP Legacy Migration] {message}")


def write_log(lines: list[str]) -> None:
    text = bpy.data.texts.get(LOG_TEXT_NAME)
    if text is None:
        text = bpy.data.texts.new(LOG_TEXT_NAME)
    text.clear()
    text.write("\n".join(lines) + "\n")


def command_line_options() -> set[str]:
    if "--" not in sys.argv:
        return set()
    return set(sys.argv[sys.argv.index("--") + 1 :])


def require_supported_blender() -> None:
    if bpy.app.version[:2] != SUPPORTED_BLENDER:
        raise RuntimeError(
            "This migration is validated only for Blender "
            f"{SUPPORTED_BLENDER[0]}.{SUPPORTED_BLENDER[1]}. "
            f"Current version: {bpy.app.version_string}"
        )


def active_armature() -> bpy.types.Object:
    rig = bpy.context.active_object
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError("Make the legacy Auto-Rig Pro armature the active object.")
    return rig


def load_arp_module() -> tuple[object, object, tuple[int, ...]]:
    module_names = (
        "bl_ext.user_default.auto_rig_pro.src.auto_rig",
        "auto_rig_pro.src.auto_rig",
    )
    errors = []
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            package_name = module.__package__.rsplit(".src", 1)[0]
            package = importlib.import_module(package_name)
            version = tuple(package.bl_info["version"])
            return module, package, version
        except (ImportError, AttributeError) as error:
            errors.append(f"{module_name}: {error}")

    raise RuntimeError(
        "Auto-Rig Pro is not enabled or could not be imported. Enable it first.\n"
        + "\n".join(errors)
    )


def require_arp_rig(rig: bpy.types.Object) -> None:
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    if not bpy.ops.arp.update_armature.poll():
        raise RuntimeError("The active armature is not recognised as an Auto-Rig Pro rig.")


def make_backup_copy() -> Path:
    if not bpy.data.filepath:
        raise RuntimeError("Save the current .blend file before running the migration.")

    source = Path(bpy.data.filepath)
    stem = f"{source.stem}_pre_arp_legacy_migration"
    backup = source.with_name(f"{stem}{source.suffix}")
    index = 1
    while backup.exists():
        backup = source.with_name(f"{stem}_{index:02d}{source.suffix}")
        index += 1

    bpy.ops.wm.save_as_mainfile(filepath=str(backup), copy=True)
    return backup


def action_groups_52(action: bpy.types.Action) -> list[object]:
    """Return legacy Action groups or their Blender 5.2 Channelbag equivalent."""
    if hasattr(action, "groups"):
        return list(action.groups)

    groups = []
    for layer in getattr(action, "layers", ()):
        for strip in getattr(layer, "strips", ()):
            for channelbag in getattr(strip, "channelbags", ()):
                groups.extend(channelbag.groups)
    return groups


def set_parent_if_present(bone: object | None, parent: object) -> None:
    """Old facial rigs can have no lower-eyelid reference bone."""
    if bone is not None:
        bone.parent = parent


def patched_update_function(arp_module: object):
    """Create a temporary Blender-5.2-compatible copy of ARP's updater."""
    source = inspect.getsource(arp_module._update_armature)
    replacements = {
        "for group in action.groups:": "for group in _arp_legacy_action_groups(action):",
        "eyelid_bot_eb.parent = eyelid_base_bot_eb": (
            "_arp_legacy_set_parent_if_present(eyelid_bot_eb, eyelid_base_bot_eb)"
        ),
    }
    applied = []
    for old, new in replacements.items():
        if old in source:
            source = source.replace(old, new)
            applied.append(old)

    namespace = arp_module.__dict__
    original = arp_module._update_armature
    namespace["_arp_legacy_action_groups"] = action_groups_52
    namespace["_arp_legacy_set_parent_if_present"] = set_parent_if_present
    exec(compile(source, arp_module.__file__, "exec"), namespace)
    return original, applied


def count_legacy_shape_scale_drivers(rig: bpy.types.Object) -> int:
    drivers = rig.animation_data.drivers if rig.animation_data else ()
    return sum(".custom_shape_scale[" in driver.data_path for driver in drivers)


def count_invalid_drivers(rig: bpy.types.Object) -> int:
    drivers = rig.animation_data.drivers if rig.animation_data else ()
    return sum(not driver.is_valid for driver in drivers)


def main() -> None:
    options = command_line_options()
    lines: list[str] = []

    try:
        require_supported_blender()
        rig = active_armature()
        arp_module, _arp_package, arp_version = load_arp_module()
        require_arp_rig(rig)

        log(lines, f"Blender: {bpy.app.version_string}")
        log(lines, f"Auto-Rig Pro: {'.'.join(map(str, arp_version))}")
        log(lines, f"Rig: {rig.name} ({len(rig.data.bones)} bones)")
        log(lines, f"Current ARP marker: {rig.data.get('arp_updated', '<none>')}")
        log(lines, f"Legacy custom-shape-scale drivers: {count_legacy_shape_scale_drivers(rig)}")

        if arp_version not in SUPPORTED_ARP_VERSIONS:
            if "--allow-unverified-arp" not in options:
                raise RuntimeError(
                    "Unsupported Auto-Rig Pro version. Update SUPPORTED_ARP_VERSIONS "
                    "after validating this script, or explicitly pass --allow-unverified-arp."
                )
            log(lines, "WARNING: running with an unverified ARP version.")

        if "--dry-run" in options:
            log(lines, "Dry run completed. No backup or rig changes were made.")
            return

        backup = make_backup_copy()
        log(lines, f"Backup copy: {backup}")

        original_update, applied_patches = patched_update_function(arp_module)
        try:
            update_args = type(
                "UpdateArgs", (), {"updated_features": [], "update_axes_consistent": False}
            )()
            arp_module._update_armature(update_args, bpy.context, required=True)
        finally:
            arp_module._update_armature = original_update
            arp_module.__dict__.pop("_arp_legacy_action_groups", None)
            arp_module.__dict__.pop("_arp_legacy_set_parent_if_present", None)

        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
        log(lines, f"Temporary compatibility patches applied: {len(applied_patches)}")
        log(lines, f"Updated features: {len(update_args.updated_features)}")
        for feature in update_args.updated_features:
            log(lines, f"  - {feature}")
        log(lines, f"Updated ARP marker: {rig.data.get('arp_updated', '<none>')}")
        log(lines, f"Legacy custom-shape-scale drivers: {count_legacy_shape_scale_drivers(rig)}")
        log(lines, f"Invalid drivers: {count_invalid_drivers(rig)}")
        log(lines, "Migration saved. Match to Rig was not run.")
    except Exception as error:
        log(lines, f"FAILED: {error}")
        raise
    finally:
        write_log(lines)


if __name__ == "__main__":
    main()
