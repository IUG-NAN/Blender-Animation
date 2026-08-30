# Blender Animation Utilities (BAU)

Blender 5.2 LTS tools for preparing game-animation Actions for Unreal Engine.

## Layout

- `addon/ue_animation_utilities/` — the installable add-on package.
- `tools/blender/migrate_arp_legacy_52.py` — an opt-in migration script for
  legacy Auto-Rig Pro rigs.
- `docs/arp_legacy_migration.md` — migration requirements and operating notes.
- `references/` — local, ignored reference material. It includes Auto-Rig Pro only for compatibility research and is never committed.

## Utilities

- **Mirror Active Action** duplicates the active Armature Action, then runs
  Blender's native **Paste Pose Flipped** operation at only the frames that
  have explicit pose-bone transform keys. It never samples or keys intervening
  frames, and it leaves the source Action unchanged.
- **Walk Setup** animates registered IK goals with Follow Path constraints.
  Animation Start and End define the Action range; Cycle Length defines the
  gait period repeated through that range for ARP baking and FBX export.
- **Setup Pelvis World Bob** creates a world-space Z bob through an unparented
  helper and Copy Location constraint.

Use the add-on from **3D View > Sidebar > UE Anim**.

## Local installation

Copy `addon/ue_animation_utilities` to Blender's user add-ons directory, then enable **UE Animation Utilities** from Blender Preferences. Development changes can be reloaded with Blender's add-on reload control.
