# Blender Animation Utilities (BAU)
BlenderでMotionPath（ベジェカーブ）を指定することでプロシージャルにアニメーションを作成できるアドオンです。
Blender 5.2 LTS tools for preparing game-animation Actions for Unreal Engine.

---
## Layout

- `addon/ue_animation_utilities/` — the installable add-on package.
	- アドオン本体：AutoRigProを始め、大抵のリグに対応できているはずです。
- `tools/blender/migrate_arp_legacy_52.py` — an opt-in migration script for
  legacy Auto-Rig Pro rigs.
	- ユーティリティ（スクリプト）古くなったAutoRigProのリグ構造を修正し、最新化するためのPythonスクリプトです。AutoRigProの古いリグ専用で、正常にUpdate Armatureできる場合は必要ありません。
- `docs/arp_legacy_migration.md` — migration requirements and operating notes.
- `references/` — local, ignored reference material. It includes Auto-Rig Pro only for compatibility research and is never committed.

---
## Utilities（アドオンの機能）

- **Mirror Active Action** 
	- 既存のアニメーション（Action）を左右反転させる機能です。ゲーム用の横歩き（Strafe）を作成する際に役立ちます。反転させたいActionを表示し、必要なキーが打たれたスケルトンまたはリググループを表示した状態にし、ボタンを押すと新しいActionを作成して左右反転したキーを自動で作成します。
	- duplicates the active Armature Action, then runs Blender's native **Paste Pose Flipped** operation at only the frames that have explicit pose-bone transform keys. It never samples or keys intervening frames, and it leaves the source Action unchanged.
- **Walk Setup** 
	- IKゴールを選択して登録し、歩行グループを設定します。MotionPathを作成し、同じく登録します。アニメーションのスタートフレーム（標準はゼロ）と最終フレームを指定します。これはアニメーションの全体の尺を定義します。次にCycle Lengthを指定します。こちらは1回の歩行サイクルを定義します。アニメーション全体と歩行サイクルの関係は整数で割り切れる必要があります。また、MotionPathは必ずトランスフォームを適用（フリーズ）しておきます。一連の登録が終わればボタンを押すだけでアニメーションが作成されます。登録内容はActionに紐づいたProfileとして登録できるので、複数のMotionPathをひとつのBlenderシーンファイルで管理することが可能です。
	- animates registered IK goals with Follow Path constraints. Animation Start and End define the Action range; Cycle Length defines the gait period repeated through that range for ARP baking and FBX export.
- **Setup Pelvis World Bob** 
	- 骨盤（Pelvis）を上下させるためのユーティリティーです。
	- creates a world-space Z bob through an unparented helper and Copy Location constraint.
- **ゲームエンジンへの出力**
	- AutoRigProなどのFBX出力を使ってください。開始から終了までのフレームでアニメーションがベイクされて出力されます。

Use the add-on from **3D View > Sidebar > UE Anim**.

---
## Local installation

Copy `addon/ue_animation_utilities` to Blender's user add-ons directory, then enable **UE Animation Utilities** from Blender Preferences. Development changes can be reloaded with Blender's add-on reload control.
