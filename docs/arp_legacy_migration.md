# Auto-Rig Pro旧リグのBlender 5.2移行

`tools/blender/migrate_arp_legacy_52.py` は、古いAuto-Rig ProリグをBlender 5.2で移行するための任意実行スクリプトである。Animation Utilities (BAU) アドオンの機能には含めない。ARP本体を頻繁に更新しても、移行ロジックと検証結果を独立して保守できるようにするためである。

## 検証済み範囲

- Blender 5.2.1 LTS
- Auto-Rig Pro 3.78.45
- 2020年頃の旧ARPリグ。`arp_updated` マーカーを持たず、旧`custom_shape_scale`ドライバーを含むもの。

この構成では、ARPの公式 `Update Armature` が以下の2点で停止した。

1. Blender 5.2で廃止された `Action.groups` を参照する。
2. 一部の旧顔リグで下まぶた参照骨が存在しないにもかかわらず、親子付けを試みる。

スクリプトはARPの更新関数を実行時だけ差し替え、ActionのChannelbag Groupsを参照し、存在しない下まぶた骨はスキップする。ARPのアドオンファイルは変更しない。更新処理後は元の関数を復元する。

## 実行手順

1. 対象`.blend`を別名保存し、Auto-Rig Proを有効化する。
2. 旧ARPアーマチュアをアクティブにする。
3. BlenderのText Editorからスクリプトを実行する。バックグラウンド実行時は次のようにする。

   ```powershell
   blender --background character.blend --python tools/blender/migrate_arp_legacy_52.py
   ```

4. 実行直前に、同じフォルダへ`*_pre_arp_legacy_migration.blend`が作成される。
5. 成否と適用機能は`ARP Legacy Migration Log`テキストデータブロックに記録される。

`--dry-run`を付けると、対象・Blender版・ARP版を検査するだけで変更しない。未検証のARP版を明示的に試す場合だけ`--allow-unverified-arp`を指定する。

## 実行後の確認

- `arp_updated`、旧`custom_shape_scale`ドライバー数、無効ドライバー数をログで確認する。
- 必要なアクションを再生し、IK/FK、追加肢、顔コントローラーをUI上で確認する。
- `Match to Rig`は自動実行しない。ボーンの見た目・回転に問題がある場合にだけ、保存済みコピーで手動実行する。
- 依存サイクル警告は移行前から存在するリグ制御に由来する場合がある。無効ドライバー数が0でも、実再生で確認する。

## ARP更新時の保守

Auto-Rig Pro更新後は、まず`--dry-run`で版数を確認する。`SUPPORTED_ARP_VERSIONS`へ追加する前に、検証用コピーで実行し、ARPの更新関数内で検索する次の旧APIが残っていないか確認する。

- `action.groups`
- `eyelid_bot_eb.parent = eyelid_base_bot_eb`

公式ARP側で修正済みなら、対応する実行時パッチを削除して検証結果をこの文書へ追記する。
