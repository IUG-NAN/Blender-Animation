# Blender Animation Utilities (BAU)
BlenderでMotionPath（ベジェカーブ）を指定することでプロシージャルにアニメーションを作成できるアドオンです。ゲーム用アニメーションの制作向けで、特定のゲームエンジン専用ではありません。
Blender 5.2 LTS tools for game-animation Actions (Unreal Engine, Unity or any FBX pipeline).

---
## Layout

- `addon/bau_animation_utilities/` — the installable add-on package.
	- アドオン本体：AutoRigProを始め、大抵のリグに対応できているはずです。
- `tools/blender/migrate_arp_legacy_52.py` — an opt-in migration script for
  legacy Auto-Rig Pro rigs.
	- ユーティリティ（スクリプト）古くなったAutoRigProのリグ構造を修正し、最新化するためのPythonスクリプトです。AutoRigProの古いリグ専用で、正常にUpdate Armatureできる場合は必要ありません。
- `docs/arp_legacy_migration.md` — migration requirements and operating notes.
- `references/` — local, ignored reference material. It includes Auto-Rig Pro only for compatibility research and is never committed.

---
## Utilities（アドオンの機能）

- **Mirror Action**（ポーズモード／オブジェクトモードの右クリック > Animation Utilities、Dope Sheet > Action）
	- 既存のアニメーション（Action）を左右反転した新しいActionを作ります。ゲーム用の横歩き（Strafe）を作成する際に役立ちます。元のActionは変わりません。
	- キーは元のActionと同じコマ・同じチャンネルにだけあり、反対側の骨へ移るだけです。キーの無いコマや、元に無かったチャンネル（scaleなど）にはキーを打ちません。補間・ハンドル・Cyclesなどのモディファイアもそのまま引き継ぎます。値はBlender標準の Paste Pose Flipped と同じ規則で反転します（左右対称のリグが前提）。
	- カスタムプロパティ（Auto-Rig ProのIK/FK切替など）とコンストレイントのチャンネルも反対側へ移ります。骨コレクションを表示しておく必要はありません。
	- creates a mirrored copy of the active Armature Action by moving every pose-bone F-Curve to the opposite-side bone and negating the channels Paste Pose Flipped negates. No key is added, removed or moved.
- **Walk Setup**（サイドバー > Tool > Walk Setup）
	- IKゴールを選択して登録し、歩行グループを設定します。MotionPathを作成し、同じく登録します。アニメーションのスタートフレーム（標準はゼロ）と最終フレームを指定します。これはアニメーションの全体の尺を定義します。次にCycle Count（尺の中の歩行サイクルの回数）を指定します。1サイクルの長さは「尺÷回数」で自動に決まり、割り切れなくても（小数のコマ数でも）最終フレームでループが閉じます。MotionPathは必ずトランスフォームを適用（フリーズ）し、閉じたカーブ（Cyclic）にしておきます。一連の登録が終わればボタンを押すだけでアニメーションが作成されます。登録内容はActionに紐づいたProfileとして登録できるので、複数のMotionPathをひとつのBlenderシーンファイルで管理することが可能です。
	- animates registered IK goals with Follow Path constraints. Animation Start and End define the Action range; Cycle Count splits that range into equal gait cycles for baking and FBX export. The scene frame range is left unchanged.
- **Pelvis Bob**（右クリック > Animation Utilities > Pelvis Bob...）
	- 骨盤（Pelvis）をワールドZで上下させるためのユーティリティーです。上下の動きはActionの中（骨盤の位置のFカーブのモディファイア）に入るので、Actionを切り替えると一緒に切り替わります。キーは打たず、骨盤の既存のキーに足し合わされます。Remove Pelvis Bobで外せます。
	- adds a world-Z cosine bob as "Pelvis Bob" F-Curve modifiers on the control's location channels in its Action. Re-running replaces it; the 0.4 helper Empty and Copy Location constraint are removed.
- **ゲームエンジンへの出力**
	- AutoRigProなどのFBX出力を使ってください。開始から終了までのフレームでアニメーションがベイクされて出力されます。

---
## インストール方法

1. [Releases](https://github.com/IUG-NAN/Blender-Animation/releases) から、最新版の **bau_animation_utilities-x.x.x.zip** をダウンロードします。
	- 「Code > Download ZIP」や、Releaseの「Source code (zip)」はリポジトリ全体なので、そのままではインストールできません。
2. Blender 5.2 で **Edit > Preferences > Add-ons** を開き、右上の **∨** から **Install from Disk...** を選んで、ダウンロードしたzipを指定します。
3. 一覧に出た **Animation Utilities (BAU)** にチェックを入れて有効にします。
4. Preferencesの左下のメニューから **Save Preferences** を押します（保存しないと、Blenderが落ちたときに無効へ戻ることがあります）。

使う場所:
- Mirror Action / Pelvis Bob: 3Dビューの右クリック（ポーズモード・オブジェクトモード） > Animation Utilities。Mirror ActionはDope Sheetの Action メニューにもあります。
- Walk Setup: 3Dビューのサイドバー（N） > Tool タブ > Walk Setup

### 0.4以前（UE Animation Utilities）からの更新

先に旧「UE Animation Utilities」を無効にしてから、上の手順で新しいアドオンを入れてください。.blendに保存されたWalk SetupとProfileは、ファイルを開いたときに引き継がれます（Cycle LengthはCycle Countに換算）。旧Pelvis World BobのEmptyとコンストレイントは、同じ骨盤にPelvis Bobを掛け直したときに取り除かれます。

### 開発用（リポジトリから直接入れる場合）

`addon/bau_animation_utilities` フォルダをBlenderのユーザーアドオンのフォルダへコピーし、Preferencesで有効にします。

## Tests

```
python addon/bau_animation_utilities/tests/run_all.py path/to/blender
```

Each test also runs on its own with `blender --background --factory-startup --python <test>` or with the `bpy` module from PyPI.

## License

GPL-3.0
