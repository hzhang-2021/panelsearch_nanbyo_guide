# PanelSearch nanbyo ガイド一式

## 読み方

- `PanelSearch_nanbyo_User_Guide.html`：オフラインで開ける日本語ガイド。左の目次・本文検索、画像拡大、印刷を利用できます。画像はすべてファイル内に埋め込んであります。
- `PanelSearch_nanbyo_User_Guide.pdf`：印刷・共有用の日本語ガイド。HTML と同じ 28 章、249 機能・確認項目、48 図を含みます。
- `PanelSearch_nanbyo_Implementation_Analysis.md`：画面構成、権限、データ、版管理、Ontology、メール、画面ごとの機能。
- `PanelSearch_nanbyo_Feature_Catalog.csv`：全説明項目と画面・利用対象・実装参照の対応。
- `PanelSearch_nanbyo_API_Routes.csv`：app.py から抽出した nanbyo 関連ルート。共通 Nanbyo のサンプル・別名も含みます。
- `PanelSearch_nanbyo_Source_Index.csv`：81 関連ファイルのパス、サイズ、SHA256。
- `PanelSearch_nanbyo_Backend_Functions.csv`：共通認証を含む164 関数の位置。
- `PanelSearch_nanbyo_Screenshot_Index.csv`：図番号、内容、出所、更新日、画像サイズ。
- `refresh_screenshots.py`：更新済みの3役の認証状態を使って読み取り中心の画面を再撮影する補助スクリプト。

CSV は UTF-8 BOM 付きです。Excel で開く場合も日本語の文字化けを避けられます。

## 検証の範囲

ローカルコード・テンプレート・SQL・E2Eテストの照合と、公開ページの閲覧を行いました。ブラウザーで HTML の目次、章数、画像埋め込み、検索・拡大を確認し、PDF は全ページをレンダリングして版面を確認しました。

今回取得した公開画面の画像と、リポジトリに保存されていた E2E 画像を併用しています。図注で区別しています。既存画像の「ファイル更新日」は撮影日時を保証しません。公開サイトとローカルコードのバージョンが同じであることも未確認です。

管理者・Curator・Reviewer のローカル storage_state ファイルは存在とサイズを確認しましたが、Windows 実行環境が Playwright の子プロセス起動を WinError 5 / EPERM で拒否したため、今回それらを使った管理ページの再撮影は未完了です。現在のガイドでは既存画像を使用しています。更新操作・メール送信・権限変更の実行テストは行っていません。

ログイン状態、Cookie、トークン、認証ファイル、ソースコード本体は配布パッケージに含めていません。元のプロジェクト、ログイン状態、Codex 設定は変更していません。

## スクリーンショットの再取得

Playwright を起動できるユーザーの PowerShell で以下を実行します。スクリプトは元リポジトリの日本語 E2E 設定と認証状態を読み込みます。

```powershell
& "G:\visualstudio_code_workspace\pubcasefinder_pcf\tests\e2e_psn\.venv\Scripts\python.exe" ".\refresh_screenshots.py"
```

画像・manifest.json・blocked.json はスクリプトの隣の `captures` に出力します。HTML/PDF は自動上書きしません。manifest を確認して、新しい画像を次のガイド更新に使用してください。

スクリプトは GET/HEAD/OPTIONS と特定の読み込み POST のみを許可し、それ以外の書き込み要求をブロックします。ログインダイアログ・タブ・入力フォーム等を開きますが、保存、削除、承認、メール送信、Ontology 更新を確定しません。password 入力はスクリーンショット上でマスクします。データの閲覧に伴う認証・アクセスログはサービス側で記録される場合があります。

この補助スクリプトは構文確認済みですが、現在の環境では実行確認を完了できていません。セッション失効や UI 更新、表示要素の不足は manifest の error / unavailable に記録されます。すべての動的状態を必ず撮影できるという保証ではありません。
