# UE Animation Utilities

Blender 5.2 LTS add-on package for game-animation utilities.

## Mirror Active Action

Works with an Armature active in Pose Mode. It preserves the source Action and
creates a mirrored Action using Blender native Paste Pose Flipped at only the
explicitly keyed transform frames.

## Walk Setup

Open **3D View > Sidebar > UE Anim > UE Animation Utilities**.

The Walk Setup is always visible. It is the single current set of controls that
generates Follow Path keys.

1. Set the Template Curve and animation range.
2. Select IK Goal Objects, or pose bones in Pose Mode.
3. Click **1. Add Selected IK Goals**.
4. Set each Goal Group.
5. Click **2. Generate / Update Animation Keys**.

For a six-legged creature split into three leg sets, set Phase Groups to 3 and
assign Groups 0, 1, and 2. Their phase offsets are 0.00, 0.33, and 0.67.

Animation Start and End define the Action length. Cycle Length defines one gait
cycle inside that range. For example, Start 0, End 30, and Cycle Length 15
creates a two-cycle walk. The utility sets the Action's manual frame range to
0--30 and creates a one-cycle Follow Path curve with a Cycles modifier, so ARP
can bake the whole range. It creates one shared-data Curve Object per IK Goal
in the UE Walk Paths collection and aligns each path on world Y only.

## Gait Profile Presets

Profiles are optional presets. They store the current Walk Setup values, IK
Goal registrations and phase groups, plus the current Action.

- **Save Current Walk Setup as Profile** creates a preset.
- Click a profile name to select it.
- **Load Selected Profile** copies its values into the always-visible Walk
  Setup and assigns its stored Action.
- Click **Generate / Update Animation Keys** after loading to apply the walk
  motion to that Action.
- **Remove Selected** deletes only the preset; it never deletes an Action,
  Curve, or generated Path.

Profiles do not create separate hidden path sets. The active Walk Setup reuses
the same per-leg paths, avoiding unbounded path duplication.

## Setup Pelvis World Bob

Select the Pelvis control Object, or its pose bone in Pose Mode, then choose
Setup Pelvis World Bob. The utility animates an unparented Empty on world Z and
uses a world-space Copy Location constraint affecting only Z.
