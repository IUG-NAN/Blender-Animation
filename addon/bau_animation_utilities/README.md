# Animation Utilities (BAU)

Blender 5.2 LTS add-on package for game-animation utilities. See the repository README for details.

| Tool | Where | Writes |
| --- | --- | --- |
| Mirror Action | Pose / Object right-click > Animation Utilities, Dope Sheet > Action | A new Action. Same key frames and channels as the source, moved to the opposite side. |
| Walk Setup | Sidebar > Tool > Walk Setup | Follow Path constraints on the IK goals and their offset keys in the rig's Action. |
| Pelvis Bob | Pose / Object right-click > Animation Utilities | "Pelvis Bob" F-Curve modifiers in the current Action. No keys. |

## Modules

- `action_api.py`: Blender 5.2 Channelbag helpers (via `bpy_extras.anim_utils`).
- `mirror.py`, `walk.py`, `pelvis_bob.py`: one tool each.
- `ui.py`: menus and the Tool tab panels.
- `legacy.py`: carries Walk Setup data saved by UE Animation Utilities 0.4.
